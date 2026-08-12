#!/usr/bin/env python3
"""Train GuideNet on the synthetic corpus (guide/data/dreams_*.jsonl).

Task-level 90/10 split. BCE on action kinds + CE on family.
Per-epoch checkpoints to guide/checkpoints/ (resumable).

Usage: train_guide.py [epochs=15] [batch=64] [device=auto]
"""
import glob
import json
import os
import sys

import numpy as np
import torch
import torch.nn.functional as F

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from guide.model import GuideNet, CANVAS, count_params

EPOCHS = int(sys.argv[1]) if len(sys.argv) > 1 else 15
BATCH = int(sys.argv[2]) if len(sys.argv) > 2 else 64
DEV = sys.argv[3] if len(sys.argv) > 3 else (
    "cuda" if torch.cuda.is_available() else "cpu")
MAXP = 4
CKPT = os.path.join(os.path.dirname(__file__), "checkpoints")
PAD = 10


def pad_grid(g):
    a = np.full((CANVAS, CANVAS), PAD, dtype=np.int64)
    h, w = min(len(g), CANVAS), min(len(g[0]), CANVAS)
    a[:h, :w] = np.asarray(g, dtype=np.int64)[:h, :w]
    return a


def load_corpus():
    rows = []
    for fp in sorted(glob.glob(os.path.join(
            os.path.dirname(__file__), "data", "dreams_*.jsonl"))):
        with open(fp) as f:
            for line in f:
                d = json.loads(line)
                rows.append((d["task"]["train"], d["meta"]))
    kinds = sorted({k for _, m in rows for k in m["action_kinds"]})
    fams = sorted({m["family"] for _, m in rows})
    ki = {k: i for i, k in enumerate(kinds)}
    fi = {f: i for i, f in enumerate(fams)}
    X_in = np.full((len(rows), MAXP, CANVAS, CANVAS), PAD, dtype=np.int64)
    X_out = np.full_like(X_in, PAD)
    NP = np.zeros(len(rows), dtype=np.int64)
    Yk = np.zeros((len(rows), len(kinds)), dtype=np.float32)
    Yf = np.zeros(len(rows), dtype=np.int64)
    for r, (pairs, meta) in enumerate(rows):
        for p, pr in enumerate(pairs[:MAXP]):
            X_in[r, p] = pad_grid(pr["input"])
            X_out[r, p] = pad_grid(pr["output"])
        NP[r] = min(len(pairs), MAXP)
        for k in meta["action_kinds"]:
            Yk[r, ki[k]] = 1.0
        Yf[r] = fi[meta["family"]]
    return (torch.from_numpy(X_in), torch.from_numpy(X_out),
            torch.from_numpy(NP), torch.from_numpy(Yk),
            torch.from_numpy(Yf), kinds, fams)


def main():
    X_in, X_out, NP, Yk, Yf, kinds, fams = load_corpus()
    n = len(NP)
    g = torch.Generator().manual_seed(7)
    perm = torch.randperm(n, generator=g)
    nva = n // 10
    va, tr = perm[:nva], perm[nva:]
    print(f"corpus {n} tasks | {len(kinds)} kinds {len(fams)} families | "
          f"train {len(tr)} val {len(va)} | device={DEV}", flush=True)
    model = GuideNet(len(kinds), len(fams)).to(DEV)
    print(f"GuideNet params {count_params(model)/1e6:.2f}M", flush=True)
    opt = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=0.01)
    os.makedirs(CKPT, exist_ok=True)
    latest = os.path.join(CKPT, "latest.pt")
    start_ep = 0
    if os.path.exists(latest):
        ck = torch.load(latest, map_location=DEV)
        model.load_state_dict(ck["model"]); opt.load_state_dict(ck["opt"])
        start_ep = ck["epoch"] + 1
        print(f"resumed from epoch {start_ep}", flush=True)

    def batches(idx, shuffle):
        order = idx[torch.randperm(len(idx))] if shuffle else idx
        for i in range(0, len(order), BATCH):
            j = order[i:i + BATCH]
            yield (X_in[j].to(DEV), X_out[j].to(DEV), NP[j].to(DEV),
                   Yk[j].to(DEV), Yf[j].to(DEV))

    for ep in range(start_ep, EPOCHS):
        model.train()
        tot = seen = 0
        for xi, xo, np_, yk, yf in batches(tr, True):
            lk, lf = model(xi, xo, np_)
            loss = (F.binary_cross_entropy_with_logits(lk, yk)
                    + F.cross_entropy(lf, yf))
            opt.zero_grad(set_to_none=True)
            loss.backward()
            opt.step()
            tot += loss.item(); seen += 1
        # val
        model.eval()
        hits1 = hits3 = nv = 0
        kind_probs, kind_true = [], []
        with torch.no_grad():
            for xi, xo, np_, yk, yf in batches(va, False):
                lk, lf = model(xi, xo, np_)
                top3 = lf.topk(3, dim=-1).indices
                hits1 += (top3[:, 0] == yf).sum().item()
                hits3 += (top3 == yf[:, None]).any(1).sum().item()
                nv += len(yf)
                kind_probs.append(torch.sigmoid(lk).cpu())
                kind_true.append(yk.cpu())
        kp = torch.cat(kind_probs); kt = torch.cat(kind_true)
        # micro precision/recall @0.5 + per-kind AP-lite (prec at recall>=.5)
        pred = kp > 0.5
        prec = (pred & kt.bool()).sum() / pred.sum().clamp(min=1)
        rec = (pred & kt.bool()).sum() / kt.sum().clamp(min=1)
        print(f"EPOCH {ep}: loss {tot/max(1,seen):.4f} "
              f"family top1 {hits1/nv:.3f} top3 {hits3/nv:.3f} "
              f"kinds P {prec:.3f} R {rec:.3f}", flush=True)
        torch.save({"model": model.state_dict(), "opt": opt.state_dict(),
                    "epoch": ep, "kinds": kinds, "families": fams},
                   latest)
    print("GUIDE TRAINING COMPLETE", flush=True)


if __name__ == "__main__":
    main()
