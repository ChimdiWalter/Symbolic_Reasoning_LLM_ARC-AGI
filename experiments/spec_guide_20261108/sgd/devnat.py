"""Development evaluation on the natural VALIDATION units (source halves; families split by DESIGN_NOTE.md): every
arm's order simulated on the stored traces at 125, 500 and 2,000 counted operations; a unit is fitted when one of
its first 3 multi-pair candidates (holes in rank order) fits its demonstrations when retried (the earlier tests'
answer rule; demonstrations only, no test output). Retries come from the learned search-order test's cache and,
when missing, are computed once with the seed-independent builder and cached in dev/retries_natural.jsonl.

    python -s -B run.py devnat MODEL_DIR OUT_JSON TRAIN_TRACED[,..]
"""
import json
import math
import os
import time

import torch

from sgd import env as E, net as NT, data as DA, train as TR, devsim as DS
from gcon import model as MD, policy as PO, sim as SM, units as UN

BUDGETS = (125, 500, 2000)


def main(model_dir, out_json, train_paths):
    t0 = time.time()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    train_t = DS.load_traced(train_paths.split(","), admitted=False)
    nat = DA.natural_holes()
    nat_tr = [h["hole"] for h in nat if h["split"] == "train"]
    X, ys, yc, keys = DS.block_rows(train_t + nat_tr)
    freq = MD.Frequency().fit(keys, ys, yc)
    lin = MD.Model(hidden=()).fit(X, ys, yc)
    guide = MD.Model().fit(X, ys, yc)
    ck = torch.load(os.path.join(model_dir, "model.pt"), map_location=device, weights_only=False)
    c = ck["cfg"]
    model = NT.SpecNet(d=c.get("d", 128), layers=c.get("layers", 4), heads=c.get("heads", 4), ff=c.get("ff", 256),
                       dropout=0.0).to(device)
    model.load_state_dict(ck["state"])
    val = [h for h in nat if h["split"] == "val"]
    units = {}
    for h in val:
        units.setdefault((h["bench"], h["task"]), []).append(h)
    holes = [h["hole"] for h in val]
    pairs = [h["pairs"] for h in val]
    probs = DS.spec_probs(model, pairs, device)
    bsc = DS.block_scores(model, ck, pairs, holes, device)
    n = len(holes)
    bsc_shuf = DS.block_scores(model, ck, pairs, holes, device, shift=n // 2)
    index = {id(hh): i for i, hh in enumerate(holes)}

    def blocks_of(h):
        return [tuple(b["block"]) for b in h["blocks"]]
    arms = {
        "hand": lambda i, h: PO.hand(blocks_of(h)),
        "frequency": lambda i, h: PO.by_scores(blocks_of(h), freq.scores_keys([b["key"] for b in h["blocks"]])),
        "linear": lambda i, h: PO.by_scores(blocks_of(h), lin.scores([b["x"] for b in h["blocks"]])),
        "small_guide": lambda i, h: PO.by_scores(blocks_of(h), guide.scores([b["x"] for b in h["blocks"]])),
        "spec_key": lambda i, h: PO.by_scores(blocks_of(h), DS.key_scores(h["blocks"], probs[i], freq)),
        "spec_block": lambda i, h: PO.by_scores(blocks_of(h), bsc[i]),
        "spec_block_shuffled": lambda i, h: PO.by_scores(blocks_of(h), bsc_shuf[i]),
    }
    from objgrow import grow as GR
    setups = {b: GR.setup(b) for b in ("concept_arc", "mini_arc", "1d_arc")}
    R = UN.Retrier(E.GE.g0_builder(), path=None)          # the cache is written below, through this study's guard
    mine = os.path.join(E.STUDY, "dev", "retries_natural.jsonl")
    if os.path.exists(mine):
        with open(mine, encoding="utf-8") as f:
            for x in f:
                if x.strip():
                    r = json.loads(x)
                    R.cache.setdefault((r["task"], r["sid"]), r)
    seed_path = os.path.join(E.GC_STUDY, "dev", "retries.jsonl")
    with open(seed_path, encoding="utf-8") as f:
        for x in f:
            if x.strip():
                r = json.loads(x)
                R.cache.setdefault((r["task"], r["sid"]), r)
    table = {}
    perunit = {}
    for arm, seqf in arms.items():
        for B in BUDGETS:
            fits = {}
            for (b, t), hs in sorted(units.items()):
                tops = []
                for h in sorted(hs, key=lambda x: x["rank"]):
                    top, _ = SM.simulate(h["hole"], seqf(index[id(h["hole"])], h["hole"]), B)
                    tops.append(top)
                a = UN.answer(tops, t, setups[b]["tasks"][t], R)
                fits[t] = bool(a["fit"])
            table.setdefault(arm, {})[B] = sum(fits.values())
            perunit.setdefault(arm, {})[B] = fits
    comp = {B: {arm: DS.paired([perunit[arm][B][t] for t in sorted(perunit[arm][B])],
                               [perunit["frequency"][B][t] for t in sorted(perunit["frequency"][B])])
                for arm in perunit if arm != "frequency"} for B in BUDGETS}
    with E.open_write(mine, "a") as f:
        for (task, sid), r in R.cache.items():
            if not r.get("seeded") and r.get("cpu_s") is not None and "_written" not in r:
                f.write(json.dumps(dict(r, task=task, sid=sid), sort_keys=True, default=list) + "\n")
    out = {"units": len(units), "holes": n, "table": table, "versus_frequency": comp, "new_retries": R.new,
           "minutes": round((time.time() - t0) / 60, 2)}
    E.dump(out_json, out, indent=1)
    print(json.dumps({k: out[k] for k in ("units", "table", "new_retries", "minutes")}))
