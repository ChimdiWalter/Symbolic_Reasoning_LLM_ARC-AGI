"""The specification-augmented guide (development): the small guide's learner with the specification encoder's
summary (z) appended to every block's features, against the same learner on the features alone.

Both are trained by one PyTorch implementation of the small guide's recipe (inputs standardised on the training rows;
two hidden layers of 32 ReLU units; a success logit with cross-entropy and a standardised log(1 + operations) with
squared error, summed; Adam with learning rate 0.003, mini-batches of 512, 40 passes, weight decay 0.0001 on the
weights; seed 20261108), on the same rows (traced training tasks and natural training units), so the only difference
is whether z is in the input. The encoder is frozen (MODEL_DIR/model.pt). Score p x exp(-c).

    python -s -B run.py augguide MODEL_DIR OUT_JSON TRAIN_TRACED[,..] VAL_TRACED[,..] [label]
"""
import json
import math
import os
import time

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from sgd import env as E, net as NT, data as DA, train as TR, devsim as DS
from gcon import policy as PO, sim as SM

SEED = 20261108


class Guide(nn.Module):
    def __init__(self, n_in, hidden=(32, 32)):
        super().__init__()
        layers, a = [], n_in
        for h in hidden:
            layers += [nn.Linear(a, h), nn.ReLU()]
            a = h
        self.body = nn.Sequential(*layers)
        self.head = nn.Linear(a, 2)

    def forward(self, x):
        o = self.head(self.body(x))
        return o[:, 0], o[:, 1]


def fit(X, ys, yc, device, hidden=(32, 32), epochs=40, bs=512, lr=0.003, wd=1e-4):
    torch.manual_seed(SEED)
    X = np.asarray(X, dtype=np.float32)
    mu, sd = X.mean(0), X.std(0)
    keep = (sd > 0).astype(np.float32)
    sd = np.where(sd > 0, sd, 1.0).astype(np.float32)
    yc = np.asarray(yc, dtype=np.float32)
    c_mu, c_sd = float(yc.mean()), float(yc.std() or 1.0)
    Z = torch.from_numpy((X - mu) / sd * keep).to(device)
    S = torch.tensor(ys, dtype=torch.float32, device=device)
    C = torch.from_numpy((yc - c_mu) / c_sd).to(device)
    m = Guide(X.shape[1], hidden).to(device)
    decay = [p for n, p in m.named_parameters() if n.endswith("weight")]
    rest = [p for n, p in m.named_parameters() if not n.endswith("weight")]
    opt = torch.optim.Adam([{"params": decay, "weight_decay": wd}, {"params": rest, "weight_decay": 0.0}], lr=lr)
    g = torch.Generator(device="cpu").manual_seed(SEED)
    n = len(Z)
    for _ in range(epochs):
        perm = torch.randperm(n, generator=g).to(device)
        for s in range(0, n, bs):
            idx = perm[s:s + bs]
            lg, cp = m(Z[idx])
            loss = F.binary_cross_entropy_with_logits(lg, S[idx]) + F.mse_loss(cp, C[idx])
            opt.zero_grad()
            loss.backward()
            opt.step()
    m.eval()
    return {"m": m, "mu": mu, "sd": sd, "keep": keep, "c_mu": c_mu, "c_sd": c_sd}


def scores(G, X, device):
    X = np.asarray(X, dtype=np.float32)
    with torch.no_grad():
        Z = torch.from_numpy((X - G["mu"]) / G["sd"] * G["keep"]).to(device)
        lg, cp = G["m"](Z)
        p = torch.sigmoid(lg).cpu().numpy()
        c = cp.cpu().numpy() * G["c_sd"] + G["c_mu"]
    return [float(a) * math.exp(-float(b)) for a, b in zip(p, c)]


def encode(model, pairs_list, device, bs=128):
    out = []
    model.eval()
    with torch.no_grad():
        for s in range(0, len(pairs_list), bs):
            t, m = TR.pad([TR.tok_array(p) for p in pairs_list[s:s + bs]], device)
            out.append(model(t, m)["z"].cpu().numpy())
    return np.concatenate(out) if out else np.zeros((0, model.d), np.float32)


def rows(holes, zs, label):
    X, ys, yc = [], [], []
    for h, z in zip(holes, zs):
        xb = {tuple(b["block"]): b for b in h["blocks"]}
        pk = h.get("pk_true") if label == "correct" else None
        for tb in h["trace"]["blocks"]:
            b = xb[tuple(tb["block"])]
            X.append(list(b["x"]) + ([] if z is None else [float(v) for v in z]))
            ys.append(1.0 if DA.block_good(tb, pk) else 0.0)
            yc.append(math.log1p(tb["n"]))
    return X, ys, yc


def main(model_dir, out_json, train_paths, val_paths, label="success"):
    t0 = time.time()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ck = torch.load(os.path.join(model_dir, "model.pt"), map_location=device, weights_only=False)
    c = ck["cfg"]
    enc = NT.SpecNet(d=c.get("d", 128), layers=c.get("layers", 4), heads=c.get("heads", 4), ff=c.get("ff", 256),
                     dropout=0.0).to(device)
    enc.load_state_dict(ck["state"])
    train_t = DS.load_traced(train_paths.split(","), admitted=False)
    nat = DA.natural_holes()
    nat_tr = [h for h in nat if h["split"] == "train"]
    tr_holes = train_t + [h["hole"] for h in nat_tr]
    tr_pairs = [[(DA.grid(a), DA.grid(b)) for a, b in t["train"]] for t in train_t] + [h["pairs"] for h in nat_tr]
    z_tr = encode(enc, tr_pairs, device)
    val_t = DS.load_traced(val_paths.split(","), admitted=True)
    val_pairs = [[(DA.grid(a), DA.grid(b)) for a, b in t["train"]] for t in val_t]
    z_val = encode(enc, val_pairs, device)
    n = len(val_t)
    Xf, ys, yc = rows(tr_holes, [None] * len(tr_holes), label)
    Xa, _, _ = rows(tr_holes, list(z_tr), label)
    G_feat = fit(Xf, ys, yc, device)
    G_aug = fit(Xa, ys, yc, device)
    freq, lin, guide_np = DS.block_models(train_t, [h["hole"] for h in nat_tr], train_paths, label)

    def blocks_of(t):
        return [tuple(b["block"]) for b in t["blocks"]]
    s_feat = [scores(G_feat, [b["x"] for b in t["blocks"]], device) for t in val_t]
    s_aug = [scores(G_aug, [list(b["x"]) + [float(v) for v in z_val[i]] for b in t["blocks"]], device)
             for i, t in enumerate(val_t)]
    s_shuf = [scores(G_aug, [list(b["x"]) + [float(v) for v in z_val[(i + n // 2) % n]] for b in t["blocks"]],
                     device) for i, t in enumerate(val_t)]
    arms = {
        "hand": lambda i, t: PO.hand(blocks_of(t)),
        "frequency": lambda i, t: PO.by_scores(blocks_of(t), freq.scores_keys([b["key"] for b in t["blocks"]])),
        "linear": lambda i, t: PO.by_scores(blocks_of(t), lin.scores([b["x"] for b in t["blocks"]])),
        "small_guide": lambda i, t: PO.by_scores(blocks_of(t), guide_np.scores([b["x"] for b in t["blocks"]])),
        "features_guide_torch": lambda i, t: PO.by_scores(blocks_of(t), s_feat[i]),
        "spec_aug_guide": lambda i, t: PO.by_scores(blocks_of(t), s_aug[i]),
        "spec_aug_guide_shuffled": lambda i, t: PO.by_scores(blocks_of(t), s_shuf[i]),
    }
    res = DS.evaluate(val_t, arms)
    table = {a: {B: sum(v) for B, v in r.items()} for a, r in res.items()}
    simple = ("hand", "frequency", "linear")
    best = {B: max(simple, key=lambda a: sum(res[a][B])) for B in DS.BUDGETS}
    comp = {B: {a: DS.paired(res[a][B], res[best[B]][B]) for a in res if a not in simple} for B in DS.BUDGETS}
    vs_feat = {B: DS.paired(res["spec_aug_guide"][B], res["features_guide_torch"][B]) for B in DS.BUDGETS}
    vs_shuf = {B: DS.paired(res["spec_aug_guide"][B], res["spec_aug_guide_shuffled"][B]) for B in DS.BUDGETS}
    edits = sorted({t["edit"] for t in val_t})
    balanced = {a: {B: round(float(np.mean([np.mean([res[a][B][i] for i, t in enumerate(val_t) if t["edit"] == e])
                                            for e in edits])), 4) for B in DS.BUDGETS} for a in res}
    flags = {a: {B: "".join("1" if x else "0" for x in v) for B, v in r.items()} for a, r in res.items()}
    out = {"n_val": n, "label": label, "table": table, "flags": flags, "best_simple": best,
           "versus_best_simple": comp,
           "spec_aug_vs_features": vs_feat, "spec_aug_vs_shuffled": vs_shuf, "edit_balanced_share": balanced,
           "train_rows": len(Xf), "minutes": round((time.time() - t0) / 60, 2)}
    E.dump(out_json, out, indent=1)
    print(json.dumps({"table": table, "spec_aug_vs_features": vs_feat, "spec_aug_vs_shuffled": vs_shuf,
                      "minutes": out["minutes"]}))
