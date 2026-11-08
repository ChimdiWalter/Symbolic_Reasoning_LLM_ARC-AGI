"""A2 compact abstraction ranker (trained module; GPU 0 under the project lock, fp32).

Input: a candidate definition's body tokens (pre-order heads; parameters tokenized with the annotation of the slot
they fill) and numeric features measured on the INDUCTION programs only (size, primitives, depth, constants,
function leaves, induction utility, programs matched). Target: log(1 + description-length savings on HELD-OUT
S_train folds' verified programs), i.e. whether a definition generalizes beyond the programs it was mined from.
No failure feature enters the ranker, so one ranker orders the authentic, shuffled and blind pools alike.
Training: folds 0-2, early stopping on fold 3 (Spearman); 3 seeds; deployment score = mean of the 3 seeds.
Saved: checkpoints (weights, optimizer, RNG states), vocabulary, normalization, finite-gradient and
changed-parameter checks.
"""
import json
import os
import random
import time

import numpy as np
import torch
from torch import nn

from a2 import runlog as RL
from a2.run_a2 import CFG, OUT, STATUS, resume_cmd

MAXLEN = 2 * 12 + 2


class Ranker(nn.Module):
    def __init__(self, vocab, nnum, d=128, layers=2, heads=4):
        super().__init__()
        self.emb = nn.Embedding(vocab, d, padding_idx=0)
        self.pos = nn.Embedding(MAXLEN, d)
        layer = nn.TransformerEncoderLayer(d, heads, 2 * d, dropout=0.1, batch_first=True)
        self.enc = nn.TransformerEncoder(layer, layers, enable_nested_tensor=False)
        self.num = nn.Sequential(nn.Linear(nnum, d), nn.ReLU())
        self.head = nn.Sequential(nn.Linear(2 * d, d), nn.ReLU(), nn.Linear(d, 1))

    def forward(self, tok, x):
        pos = torch.arange(tok.shape[1], device=tok.device)
        h = self.emb(tok) + self.pos(pos)[None]
        h = self.enc(h, src_key_padding_mask=tok.eq(0))
        return self.head(torch.cat([h[:, 0], self.num(x)], -1)).squeeze(-1)


def spearman(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    ra, rb = a.argsort().argsort().astype(float), b.argsort().argsort().astype(float)
    if ra.std() == 0 or rb.std() == 0:
        return 0.0
    return float(np.corrcoef(ra, rb)[0, 1])


def encode(rows, vocab):
    T = np.zeros((len(rows), MAXLEN), dtype=np.int64)
    for i, r in enumerate(rows):
        ids = [1] + [vocab.get(t, 2) for t in r["tokens"]][:MAXLEN - 1]
        T[i, :len(ids)] = ids
    X = np.array([r["x"] for r in rows], dtype=np.float32)
    return T, X


def run():
    with RL.P.open_allowed(os.path.join(OUT, "labels.json")) as f:
        rows = json.load(f)["rows"]
    dev = torch.device(os.environ.get("A2_DEVICE", "cuda:0"))      # cpu only when the GPU lock wait timed out
    torch.set_num_threads(1)
    rec = RL.Run("a2", "ranker", STATUS, dict(CFG, model="Ranker d128 L2", device=str(dev)), resume_cmd("ranker"),
                 gpu=dev.type == "cuda").start()
    t_gpu0 = time.time()
    train = [r for r in rows if "y" in r and r["fold"] != "3"]
    val = [r for r in rows if "y" in r and r["fold"] == "3"]
    dep = [r for r in rows if r["fold"] == "all"]
    toks = sorted({t for r in train for t in r["tokens"]})
    vocab = {t: i + 3 for i, t in enumerate(toks)}                  # 0 pad, 1 CLS, 2 unknown
    Ttr, Xtr = encode(train, vocab)
    mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-6
    ytr = np.array([r["y"] for r in train], dtype=np.float32)
    Tva, Xva = encode(val, vocab)
    yva = np.array([r["y"] for r in val], dtype=np.float32)
    Tde, Xde = encode(dep, vocab)
    base_val = spearman([r["u_ind"] for r in val], yva)
    ckdir = os.path.join(OUT, "ranker")
    os.makedirs(ckdir, exist_ok=True)
    per_seed, dep_scores = [], []
    for seed in (0, 1, 2):
        random.seed(seed)
        np.random.seed(seed)
        torch.manual_seed(seed)
        m = Ranker(len(vocab) + 3, Xtr.shape[1]).to(dev)
        init = {k: v.detach().clone() for k, v in m.state_dict().items()}
        opt = torch.optim.AdamW(m.parameters(), lr=1e-3, weight_decay=1e-4)
        tt, xx, yy = (torch.tensor(Ttr, device=dev), torch.tensor((Xtr - mu) / sd, device=dev),
                      torch.tensor(ytr, device=dev))
        tv, xv = torch.tensor(Tva, device=dev), torch.tensor((Xva - mu) / sd, device=dev)
        best, best_state, curve, finite = -2.0, None, [], True
        for ep in range(40):
            m.train()
            perm = torch.randperm(len(tt), device=dev)
            for i in range(0, len(perm), 256):
                b = perm[i:i + 256]
                loss = nn.functional.mse_loss(m(tt[b], xx[b]), yy[b])
                opt.zero_grad()
                loss.backward()
                finite &= all(torch.isfinite(p.grad).all().item() for p in m.parameters() if p.grad is not None)
                opt.step()
            m.eval()
            with torch.no_grad():
                pv = m(tv, xv).cpu().numpy()
            rho = spearman(pv, yva)
            curve.append(round(rho, 4))
            if rho > best:
                best = rho
                best_state = {k: v.detach().clone() for k, v in m.state_dict().items()}
                best_ep = ep
        m.load_state_dict(best_state)
        changed = sum(1 for k in init if not torch.equal(init[k].cpu(), best_state[k].cpu()))
        torch.save({"state_dict": best_state, "optimizer": opt.state_dict(), "torch_rng": torch.get_rng_state(),
                    "cuda_rng": torch.cuda.get_rng_state(dev) if dev.type == "cuda" else None, "numpy_rng": np.random.get_state(),
                    "python_rng": random.getstate(), "vocab": vocab, "mu": mu, "sd": sd, "epoch": best_ep},
                   os.path.join(ckdir, f"seed{seed}.pt"))
        with torch.no_grad():
            sc = m(torch.tensor(Tde, device=dev), torch.tensor((Xde - mu) / sd, device=dev)).cpu().numpy()
        dep_scores.append(sc)
        per_seed.append({"seed": seed, "val_spearman": round(best, 4), "best_epoch": best_ep, "curve": curve,
                         "finite_grads": bool(finite), "tensors_changed": changed, "tensors": len(init)})
    nparams = sum(p.numel() for p in m.parameters())
    mean = np.mean(dep_scores, 0)
    scores = {json.dumps(r["body"]): float(s) for r, s in zip(dep, mean)}
    top = lambda s: set(np.argsort(-s)[:200].tolist())                 # noqa: E731
    overlap = [len(top(dep_scores[0]) & top(dep_scores[i])) / 200 for i in (1, 2)]
    doc = {"scores": scores, "per_seed": per_seed, "params": int(nparams), "val_rows": len(val),
           "train_rows": len(train), "deploy_rows": len(dep), "baseline_val_spearman_u_ind": round(base_val, 4),
           "top200_overlap_seed0_vs_1_2": overlap, "gpu_wall_s": round(time.time() - t_gpu0, 1),
           "device": torch.cuda.get_device_name(dev) if dev.type == "cuda" else "cpu", "torch": torch.__version__}
    with RL.P.open_allowed(os.path.join(OUT, "ranker_scores.json"), mode="w") as f:
        json.dump(doc, f)
    rec.extra = {k: v for k, v in doc.items() if k != "scores"}
    rec.finish("OK")
