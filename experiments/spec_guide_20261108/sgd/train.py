"""Train the specification-reading guide (development; GPU 0 only, under the project's lock; never GPU 1).

    python -s -B run.py train OUT_DIR CONFIG_JSON

CONFIG_JSON (a file) sets: cheap (training files), cheap_val, traced (training files), traced_val, natural
(true/false), d, layers, heads, ff, epochs, batch, lr, aug (true/false), key_weight, seed, max_minutes.
Writes OUT_DIR/model.pt, OUT_DIR/train_log.json (per epoch: losses, validation top-1 and top-3 of the edit type on
the validation families, key-head average precision on traced validation tasks).
"""
import json
import math
import os
import random
import sys
import time

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from sgd import env as E, net as NT, data as DA

TOKW = 16          # token columns: 14 embedded fields, then the cell's grid height and width (for symmetries)


def tok_array(pairs):
    rows = NT.tokens(pairs)
    out = np.zeros((len(rows), TOKW), dtype=np.int16)
    out[:, :14] = np.array(rows, dtype=np.int16)
    # grid sizes for the symmetries: cell tokens take their grid's size from their pair's header
    hdr = {}
    for i, r in enumerate(rows):
        if r[0] == 1:
            hdr[r[9]] = (r[10], r[11], r[12], r[13])
    for i, r in enumerate(rows):
        if r[0] == 2:
            H, W, H2, W2 = hdr[r[9]]
            out[i, 14], out[i, 15] = (H2, W2) if r[8] == 2 else (H, W)
    return out


def augment(a, rng):
    """A colour permutation of 1..9 and one of the eight symmetries of the square, applied to a token array."""
    a = a.copy()
    perm = np.arange(11)
    p = list(range(1, 10))
    rng.shuffle(p)
    perm[1:10] = p
    a[:, 1] = perm[a[:, 1]]
    a[:, 2] = perm[a[:, 2]]
    k = rng.randrange(8)
    cell = a[:, 0] == 2
    hdr = a[:, 0] == 1
    r, c, H, W = a[:, 3].astype(np.int32), a[:, 4].astype(np.int32), a[:, 14].astype(np.int32), a[:, 15].astype(np.int32)
    h1, w1, h2, w2 = (a[:, 10].astype(np.int32), a[:, 11].astype(np.int32), a[:, 12].astype(np.int32),
                      a[:, 13].astype(np.int32))
    if k >= 4:
        r, c, H, W = c, r, W, H
        h1, w1, h2, w2 = w1, h1, w2, h2
    for _ in range(k % 4):
        r, c, H, W = c, H - 1 - r, W, H
        h1, w1, h2, w2 = w1, h1, w2, h2
    a[cell, 3] = np.clip(r[cell], 0, 29)
    a[cell, 4] = np.clip(c[cell], 0, 29)
    a[cell, 14], a[cell, 15] = H[cell], W[cell]
    a[hdr, 10], a[hdr, 11], a[hdr, 12], a[hdr, 13] = h1[hdr], w1[hdr], h2[hdr], w2[hdr]
    return a


def pad(arrs, device):
    n = max(len(a) for a in arrs)
    t = np.zeros((len(arrs), n, 14), dtype=np.int64)
    m = np.ones((len(arrs), n), dtype=bool)
    for i, a in enumerate(arrs):
        t[i, :len(a)] = a[:, :14]
        m[i, :len(a)] = False
    return torch.from_numpy(t).to(device), torch.from_numpy(m).to(device)


def onehot(i, n):
    v = np.zeros(n, dtype=np.float32)
    v[i] = 1.0
    return v


def load_cheap(paths):
    out = []
    for p in paths:
        with open(E.check_read(p), encoding="utf-8") as f:
            for x in f:
                if not x.strip():
                    continue
                t = json.loads(x)
                pairs = [(DA.grid(a), DA.grid(b)) for a, b in t["train"]]
                out.append({"tok": tok_array(pairs), "edit": onehot(NT.EDITS.index(t["edit"]), len(NT.EDITS)),
                            "view": onehot(NT.VIEWS.index(t["view"]), len(NT.VIEWS)), "family": t["family"]})
    return out


LABEL = {"mode": "success"}


def load_traced(paths, admitted_only=False):
    """Traced tasks with a trace (every uncapped one: the same block-level data the frequency table, the linear
    model and the small guide are trained on); admitted_only for validation."""
    out = []
    for p in paths:
        with open(E.check_read(p), encoding="utf-8") as f:
            for x in f:
                if not x.strip():
                    continue
                t = json.loads(x)
                if t.get("trace") is None or (admitted_only and not t.get("admitted")):
                    continue
                pairs = [(DA.grid(a), DA.grid(b)) for a, b in t["train"]]
                pk = t["pk_true"] if LABEL["mode"] == "correct" else None
                keys = DA.success_keys(t, pk)
                ev, vv = DA.edit_view_targets(keys)
                out.append(dict({"tok": tok_array(pairs), "edit": np.array(ev, dtype=np.float32),
                                 "view": np.array(vv, dtype=np.float32),
                                 "key": np.array(DA.key_targets(keys), dtype=np.float32), "gen_edit": t["edit"]},
                                **block_arrays(t, pk)))
    return out


def block_arrays(hole, pk_true=None):
    """The traced blocks of a hole: features, key indices, label (success, or correct with pk_true) and
    log(1 + operations)."""
    xb = {tuple(b["block"]): b for b in hole["blocks"]}
    F_, K_, S_, C_ = [], [], [], []
    for tb in hole["trace"]["blocks"]:
        b = xb[tuple(tb["block"])]
        k = NT.KEY_INDEX.get(tuple(b["key"]))
        if k is None:
            continue
        F_.append(b["x"])
        K_.append(k)
        S_.append(1.0 if DA.block_good(tb, pk_true) else 0.0)
        C_.append(math.log1p(tb["n"]))
    return {"bf": np.array(F_, dtype=np.float32).reshape(-1, NT.NFEAT), "bk": np.array(K_, dtype=np.int64),
            "bs": np.array(S_, dtype=np.float32), "bc": np.array(C_, dtype=np.float32)}


def load_natural(split):
    out = []
    for h in DA.natural_holes():
        if h["split"] != split:
            continue
        keys = DA.success_keys(h["hole"])
        ev, vv = DA.edit_view_targets(keys)
        out.append(dict({"tok": tok_array(h["pairs"]), "edit": np.array(ev, dtype=np.float32),
                         "view": np.array(vv, dtype=np.float32),
                         "key": np.array(DA.key_targets(keys), dtype=np.float32),
                         "bench": h["bench"], "task": h["task"], "rank": h["rank"]}, **block_arrays(h["hole"])))
    return out


def topk_acc(model, items, device, field="edit", k=(1, 3), bs=256):
    """Share of items whose top-k predicted classes contain a positive class (items with a positive only)."""
    model.eval()
    hits = {kk: 0 for kk in k}
    n = 0
    with torch.no_grad():
        for s in range(0, len(items), bs):
            chunk = [it for it in items[s:s + bs] if it[field].sum() > 0]
            if not chunk:
                continue
            t, m = pad([it["tok"] for it in chunk], device)
            logits = model(t, m)[field].float().cpu().numpy()
            for it, lg in zip(chunk, logits):
                order = np.argsort(-lg)
                for kk in k:
                    if it[field][order[:kk]].sum() > 0:
                        hits[kk] += 1
                n += 1
    model.train()
    return {f"top{kk}": round(hits[kk] / max(1, n), 4) for kk in k} | {"n": n}


def key_ap(model, items, device, bs=256):
    """Mean over items of the average precision of the key head's ranking of the successful keys."""
    model.eval()
    aps = []
    with torch.no_grad():
        for s in range(0, len(items), bs):
            chunk = [it for it in items[s:s + bs] if it["key"].sum() > 0]
            if not chunk:
                continue
            t, m = pad([it["tok"] for it in chunk], device)
            logits = model(t, m)["key"].float().cpu().numpy()
            for it, lg in zip(chunk, logits):
                order = np.argsort(-lg)
                y = it["key"][order]
                hits = np.cumsum(y)
                prec = hits / (np.arange(len(y)) + 1)
                aps.append(float((prec * y).sum() / y.sum()))
    model.train()
    return round(float(np.mean(aps)) if aps else 0.0, 4)


def main(out_dir, cfg_path):
    cfg = E.load(cfg_path)
    LABEL["mode"] = cfg.get("label", "success")
    seed = int(cfg.get("seed", 20261108))
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    t0 = time.time()
    cheap = load_cheap(cfg["cheap"])
    cheap_val = load_cheap(cfg["cheap_val"])
    traced = load_traced(cfg.get("traced", []))
    traced_val = load_traced(cfg.get("traced_val", []), admitted_only=True)
    nat_tr = load_natural("train") if cfg.get("natural", True) else []
    nat_val = load_natural("val") if cfg.get("natural", True) else []
    keyed = traced + nat_tr
    allf = np.concatenate([it["bf"] for it in keyed]) if keyed else np.zeros((1, NT.NFEAT), np.float32)
    allc = np.concatenate([it["bc"] for it in keyed]) if keyed else np.zeros(1, np.float32)
    f_mu, f_sd = allf.mean(0), allf.std(0)
    f_sd = np.where(f_sd > 0, f_sd, 1.0).astype(np.float32)
    c_mu, c_sd = float(allc.mean()), float(allc.std() or 1.0)
    f_mu_t = torch.from_numpy(f_mu.astype(np.float32)).to(device)
    f_sd_t = torch.from_numpy(f_sd).to(device)
    print(json.dumps({"cheap": len(cheap), "cheap_val": len(cheap_val), "traced": len(traced),
                      "traced_val": len(traced_val), "natural_train": len(nat_tr), "natural_val": len(nat_val),
                      "load_s": round(time.time() - t0, 1), "device": str(device)}), flush=True)
    model = NT.SpecNet(d=cfg.get("d", 128), layers=cfg.get("layers", 4), heads=cfg.get("heads", 4),
                       ff=cfg.get("ff", 256), dropout=cfg.get("dropout", 0.1)).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=cfg.get("lr", 3e-4), weight_decay=cfg.get("wd", 0.01))
    bs = cfg.get("batch", 64)
    epochs = cfg.get("epochs", 6)
    steps_per_epoch = math.ceil(len(cheap) / bs)
    total = epochs * steps_per_epoch
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=cfg.get("lr", 3e-4), total_steps=total, pct_start=0.05)
    rng = random.Random(seed)
    kw = cfg.get("key_weight", 1.0)
    log = []
    best = None
    step = 0
    for ep in range(epochs):
        order = list(range(len(cheap)))
        rng.shuffle(order)
        tot = {"edit": 0.0, "view": 0.0, "key": 0.0}
        for s in range(0, len(order), bs):
            idx = order[s:s + bs]
            arrs = [augment(cheap[i]["tok"], rng) if cfg.get("aug", True) else cheap[i]["tok"] for i in idx]
            t, m = pad(arrs, device)
            out = model(t, m)
            ye = torch.from_numpy(np.stack([cheap[i]["edit"] for i in idx])).to(device)
            yv = torch.from_numpy(np.stack([cheap[i]["view"] for i in idx])).to(device)
            loss = F.cross_entropy(out["edit"], ye.argmax(1)) + F.cross_entropy(out["view"], yv.argmax(1))
            tot["edit"] += float(loss.detach())
            if keyed and (step % cfg.get("key_every", 2) == 0):
                kidx = [rng.randrange(len(keyed)) for _ in range(bs)]
                t2, m2 = pad([augment(keyed[i]["tok"], rng) if cfg.get("aug_keyed", False) else keyed[i]["tok"]
                              for i in kidx], device)
                o2 = model(t2, m2)
                yk = torch.from_numpy(np.stack([keyed[i]["key"] for i in kidx])).to(device)
                ye2 = torch.from_numpy(np.stack([keyed[i]["edit"] for i in kidx])).to(device)
                yv2 = torch.from_numpy(np.stack([keyed[i]["view"] for i in kidx])).to(device)
                l2 = (kw * F.binary_cross_entropy_with_logits(o2["key"], yk) * len(NT.KEYS) / 20 +
                      F.binary_cross_entropy_with_logits(o2["edit"], ye2) + F.binary_cross_entropy_with_logits(
                          o2["view"], yv2))
                if cfg.get("block_head", True):
                    owner = torch.from_numpy(np.concatenate([np.full(len(keyed[i]["bk"]), j, dtype=np.int64)
                                                             for j, i in enumerate(kidx)])).to(device)
                    bf = torch.from_numpy(np.concatenate([keyed[i]["bf"] for i in kidx])).to(device)
                    bk = torch.from_numpy(np.concatenate([keyed[i]["bk"] for i in kidx])).to(device)
                    bsy = torch.from_numpy(np.concatenate([keyed[i]["bs"] for i in kidx])).to(device)
                    bcy = torch.from_numpy((np.concatenate([keyed[i]["bc"] for i in kidx]) - c_mu) / c_sd).to(device)
                    lg, cp = model.blocks(o2["z"], owner, (bf - f_mu_t) / f_sd_t, bk)
                    l2 = l2 + cfg.get("block_weight", 1.0) * (F.binary_cross_entropy_with_logits(lg, bsy) +
                                                               F.mse_loss(cp, bcy.float()))
                loss = loss + l2
                tot["key"] += float(l2.detach())
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            sched.step()
            step += 1
            if (time.time() - t0) / 60 > cfg.get("max_minutes", 50):
                break
        ev = {"epoch": ep, "loss": {k: round(v / steps_per_epoch, 4) for k, v in tot.items()},
              "cheap_val_edit": topk_acc(model, cheap_val, device, "edit"),
              "cheap_val_view": topk_acc(model, cheap_val, device, "view"),
              "traced_val_edit": topk_acc(model, traced_val, device, "edit"),
              "natural_val_edit": topk_acc(model, nat_val, device, "edit"),
              "traced_val_key_ap": key_ap(model, traced_val, device),
              "natural_val_key_ap": key_ap(model, nat_val, device),
              "minutes": round((time.time() - t0) / 60, 1)}
        log.append(ev)
        print(json.dumps(ev), flush=True)
        score = ev["cheap_val_edit"]["top1"] + ev["traced_val_key_ap"]
        if best is None or score > best:
            best = score
            torch.save({"state": model.state_dict(), "cfg": cfg, "epoch": ep, "f_mu": f_mu.tolist(),
                        "f_sd": f_sd.tolist(), "c_mu": c_mu, "c_sd": c_sd}, os.path.join(out_dir, "model.pt"))
        if (time.time() - t0) / 60 > cfg.get("max_minutes", 50):
            break
    E.dump(os.path.join(out_dir, "train_log.json"), {"cfg": cfg, "log": log, "params": NT.n_params(model)},
           indent=1)
