"""Development evaluation on validation families (never held): every arm's order simulated from the frozen step's
traces at 125, 500 and 2,000 counted operations.

    python -s -B run.py devsim MODEL_DIR OUT_JSON TRAIN_TRACED[,..] VAL_TRACED[,..] [natural]

Arms: hand-set order; frequency table, linear model and small guide (the learned search-order test's models,
retrained here on the same development training data: traced training tasks and the natural training units);
the specification-reading guide (key head, its probability times exp(-c) with c the frequency table's mean log
operations of the key; also without the cost term and through the edit and view heads); the shuffled control (the
same model fed another validation task's specification). Synthetic tasks: correct when the true test output is one
of the first two distinct test predictions of the multi-pair candidates (pass at 2), as in gen.answer_from_top.
"""
import json
import math
import os
import sys
import time

import numpy as np
import torch

from sgd import env as E, net as NT, data as DA, train as TR, gen as GN
from gcon import model as MD, policy as PO, sim as SM

BUDGETS = (125, 500, 2000)


def load_traced(paths, admitted=True):
    out = []
    for p in paths:
        with open(E.check_read(p), encoding="utf-8") as f:
            for x in f:
                if not x.strip():
                    continue
                t = json.loads(x)
                if t.get("trace") is None:
                    continue
                if admitted and not t.get("admitted"):
                    continue
                out.append(t)
    return out


def block_rows(holes, label="success"):
    """Block-level training rows; label "correct" uses the true test output on generated tasks (pk_true) and
    "success" elsewhere (natural units have no test output in development)."""
    X, ys, yc, keys = [], [], [], []
    for h in holes:
        xb = {tuple(b["block"]): b for b in h["blocks"]}
        pk = h.get("pk_true") if label == "correct" else None
        for t in h["trace"]["blocks"]:
            b = xb[tuple(t["block"])]
            X.append(b["x"])
            ys.append(1 if DA.block_good(t, pk) else 0)
            yc.append(math.log1p(t["n"]))
            keys.append(b["key"])
    return X, ys, yc, keys


def block_models(train_t, nat_tr, train_paths, label="success"):
    """The frequency table, the linear model and the small guide, trained on the traced training tasks and the
    natural training units (cached in dev/block_models.<digest of the training file list>.json)."""
    import hashlib
    tag = hashlib.sha256((train_paths + "|" + label).encode()).hexdigest()[:12]
    path = os.path.join(E.STUDY, "dev", f"block_models.{tag}.json")
    if os.path.exists(path):
        d = E.load(path)
        return (MD.Frequency.from_json(d["frequency"]), MD.Model.from_json(d["linear"]),
                MD.Model.from_json(d["small_guide"]))
    X, ys, yc, keys = block_rows(train_t + nat_tr, label)
    freq = MD.Frequency().fit(keys, ys, yc)
    lin = MD.Model(hidden=()).fit(X, ys, yc)
    guide = MD.Model().fit(X, ys, yc)
    E.dump(path, {"frequency": freq.to_json(), "linear": lin.to_json(), "small_guide": guide.to_json(),
                  "train_paths": train_paths, "label": label, "rows": len(X), "successes": int(sum(ys))})
    return freq, lin, guide


def spec_probs(model, pairs_list, device, bs=128):
    model.eval()
    out = []
    with torch.no_grad():
        for s in range(0, len(pairs_list), bs):
            arrs = [TR.tok_array(p) for p in pairs_list[s:s + bs]]
            t, m = TR.pad(arrs, device)
            o = model(t, m)
            pk = torch.sigmoid(o["key"]).cpu().numpy()
            pe = torch.softmax(o["edit"], -1).cpu().numpy()
            pv = torch.softmax(o["view"], -1).cpu().numpy()
            for i in range(len(arrs)):
                out.append((pk[i], pe[i], pv[i]))
    return out


def block_scores(model, ck, pairs_list, tasks, device, shift=0, bs=64):
    """The block head's p x exp(-c) for every block of every task (shift: take the specification of task i+shift)."""
    f_mu = torch.tensor(ck["f_mu"], dtype=torch.float32, device=device)
    f_sd = torch.tensor(ck["f_sd"], dtype=torch.float32, device=device)
    n = len(tasks)
    out = []
    model.eval()
    with torch.no_grad():
        for s in range(0, n, bs):
            idx = list(range(s, min(n, s + bs)))
            arrs = [TR.tok_array(pairs_list[(i + shift) % n]) for i in idx]
            t, m = TR.pad(arrs, device)
            z = model(t, m)["z"]
            for j, i in enumerate(idx):
                bl = tasks[i]["blocks"]
                feats = torch.tensor([b["x"] for b in bl], dtype=torch.float32, device=device)
                keys = torch.tensor([NT.KEY_INDEX.get(tuple(b["key"]), 0) for b in bl], device=device)
                owner = torch.full((len(bl),), j, dtype=torch.long, device=device)
                lg, cp = model.blocks(z, owner, (feats - f_mu) / f_sd, keys)
                p = torch.sigmoid(lg).cpu().numpy()
                c = cp.cpu().numpy() * ck["c_sd"] + ck["c_mu"]
                out.append([float(a) * math.exp(-float(b)) for a, b in zip(p, c)])
    return out


def key_scores(blocks, probs, freq, cost=True, mode="key"):
    pk, pe, pv = probs
    out = []
    for b in blocks:
        k = tuple(b["key"])
        c = freq.table.get(k, freq.pooled)[1]
        if mode == "key":
            p = float(pk[NT.KEY_INDEX[k]]) if k in NT.KEY_INDEX else 0.0
        else:
            if k[0] == "S":
                p = float(pe[NT.EDITS.index(k[2])]) * float(pv[NT.VIEWS.index(k[1])]) if k[2] in NT.EDITS else 0.0
            elif k[0] == "W":
                p = float(pe[NT.EDITS.index("crop")]) * float(pv[NT.VIEWS.index(k[1])])
            else:
                p = 0.0
        out.append(p * math.exp(-c) if cost else p)
    return out


def correct(top, pk_true):
    return GN.answer_from_top([(c["pk"], bool(c["loo"]), bool(c["valid"])) for c in top], pk_true)


def evaluate(tasks, arms_seq):
    res = {}
    for arm, seqf in arms_seq.items():
        row = {}
        for B in BUDGETS:
            flags = []
            for i, t in enumerate(tasks):
                top, info = SM.simulate(t, seqf(i, t), B)
                flags.append(bool(correct(top, t["pk_true"])))
            row[B] = flags
        res[arm] = row
    return res


def paired(a, b):
    ga = sum(1 for x, y in zip(a, b) if x and not y)
    gb = sum(1 for x, y in zip(a, b) if y and not x)
    from ngrow import analysis as AN
    return {"first_only": ga, "second_only": gb, "p": round(AN.binom_two_sided(ga, ga + gb), 6)}


def main(model_dir, out_json, train_paths, val_paths, *flags):
    t0 = time.time()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    train_t = load_traced(train_paths.split(","), admitted=False)
    val_t = load_traced(val_paths.split(","), admitted=True)
    nat = DA.natural_holes()
    nat_tr = [h["hole"] for h in nat if h["split"] == "train"]
    ck = torch.load(os.path.join(model_dir, "model.pt"), map_location=device, weights_only=False)
    c = ck["cfg"]
    freq, lin, guide = block_models(train_t, nat_tr, train_paths, c.get("label", "success"))
    model = NT.SpecNet(d=c.get("d", 128), layers=c.get("layers", 4), heads=c.get("heads", 4), ff=c.get("ff", 256),
                       dropout=0.0).to(device)
    model.load_state_dict(ck["state"])
    pairs = [[(DA.grid(a), DA.grid(b)) for a, b in t["train"]] for t in val_t]
    probs = spec_probs(model, pairs, device)
    n = len(val_t)
    bsc = block_scores(model, ck, pairs, val_t, device)
    bsc_shuf = block_scores(model, ck, pairs, val_t, device, shift=n // 2)

    def blocks_of(t):
        return [tuple(b["block"]) for b in t["blocks"]]
    arms = {
        "hand": lambda i, t: PO.hand(blocks_of(t)),
        "frequency": lambda i, t: PO.by_scores(blocks_of(t), freq.scores_keys([b["key"] for b in t["blocks"]])),
        "linear": lambda i, t: PO.by_scores(blocks_of(t), lin.scores([b["x"] for b in t["blocks"]])),
        "small_guide": lambda i, t: PO.by_scores(blocks_of(t), guide.scores([b["x"] for b in t["blocks"]])),
        "spec_key": lambda i, t: PO.by_scores(blocks_of(t), key_scores(t["blocks"], probs[i], freq)),
        "spec_key_nocost": lambda i, t: PO.by_scores(blocks_of(t), key_scores(t["blocks"], probs[i], freq, False)),
        "spec_family": lambda i, t: PO.by_scores(blocks_of(t), key_scores(t["blocks"], probs[i], freq, True,
                                                                          "family")),
        "shuffled": lambda i, t: PO.by_scores(blocks_of(t), key_scores(t["blocks"], probs[(i + n // 2) % n], freq)),
        "spec_block": lambda i, t: PO.by_scores(blocks_of(t), bsc[i]),
        "spec_block_shuffled": lambda i, t: PO.by_scores(blocks_of(t), bsc_shuf[i]),
    }
    res = evaluate(val_t, arms)
    table = {arm: {B: sum(v) for B, v in row.items()} for arm, row in res.items()}
    comp = {B: {arm: paired(res[arm][B], res["frequency"][B]) for arm in res if arm != "frequency"}
            for B in BUDGETS}
    # the bar: the strongest simple order (hand-set, frequency, linear) at each budget
    simple = ("hand", "frequency", "linear")
    best = {B: max(simple, key=lambda a: sum(res[a][B])) for B in BUDGETS}
    versus_best = {B: {arm: dict(paired(res[arm][B], res[best[B]][B]), best=best[B])
                       for arm in res if arm.startswith("spec") or arm == "small_guide"} for B in BUDGETS}
    # edit-balanced view: every edit type weighted equally (share correct, averaged over edit types)
    edits = sorted({t["edit"] for t in val_t})
    balanced = {arm: {B: round(float(np.mean([np.mean([res[arm][B][i] for i, t in enumerate(val_t) if t["edit"] == e])
                                                for e in edits])), 4) for B in BUDGETS} for arm in res}
    by_edit = {}
    for i, t in enumerate(val_t):
        e = t["edit"]
        d = by_edit.setdefault(e, {"n": 0, "spec_key_500": 0, "spec_block_500": 0, "frequency_500": 0})
        d["n"] += 1
        d["spec_key_500"] += int(res["spec_key"][500][i])
        d["spec_block_500"] += int(res["spec_block"][500][i])
        d["frequency_500"] += int(res["frequency"][500][i])
    flags = {arm: {B: "".join("1" if x else "0" for x in v) for B, v in row.items()} for arm, row in res.items()}
    out = {"n_val": n, "n_train_traced": len(train_t), "n_natural_train_holes": len(nat_tr), "table": table,
           "flags": flags, "val_edits": [t["edit"] for t in val_t],
           "versus_frequency": comp, "best_simple": best, "versus_best_simple": versus_best,
           "edit_balanced_share": balanced, "by_edit_at_500": by_edit, "minutes": round((time.time() - t0) / 60, 2)}
    E.dump(out_json, out, indent=1)
    print(json.dumps({"n_val": n, "table": table, "best_simple": best,
                      "versus_best_125": versus_best[125], "minutes": out["minutes"]}))
