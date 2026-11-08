"""Development on the SOURCE set only (before the freeze): constants, the learned router, and the evidence used to
write the fixed router's rules.

    python -m fgc.develop table              per-task failure features beside each intervention's outcome
    python -m fgc.develop constants          K_S, T_STAR and the static order, by the pre-declared formulas
    python -m fgc.develop learn              trains the learned router and writes it into config/ROUTERS.json

Pre-declared formulas (PROTOCOL.md section 5):
- K_S (search's cap inside the bank) = the 90th percentile of the search's calls at its correct first fit over the
  source depth tasks, rounded up to the next 250,000 calls;
- T_STAR (the binding budget) = the 75th percentile of the oracle arm's spent calls over the source tasks the
  oracle solves within 20,000,000 calls, rounded up to the next 250,000 calls;
- STATIC_ORDER = the order of the bank with more correct source tasks at T_STAR (ties: fewer mean calls; then
  search first).
- the learned router: one L2-regularised logistic regression per intervention (fgc/arms.py), on the source tasks'
  failure features, predicting that the intervention alone commits a correct answer (search within K_S;
  construction within its own calls), trained once with fixed settings.
"""
import json
import math
import os
import sys

from fgc import arms as A
from fgc import contract as K
from fgc.pipeline import measurements, load, dump, correct

STUDY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EV = os.path.join(STUDY, "runs", "source", "evaluator_only", "SOURCE_EVAL.json")
MEAS = os.environ.get("FGC_MEASURE", os.path.join(STUDY, "runs", "source", "measure"))
ROUTERS = os.path.join(STUDY, "config", "ROUTERS.json")
STEP = 250_000


def up(x):
    return int(math.ceil(x / STEP) * STEP)


def pct(xs, q):
    xs = sorted(xs)
    if not xs:
        return None
    k = (len(xs) - 1) * q
    lo, hi = int(math.floor(k)), int(math.ceil(k))
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def rows():
    ev, ms = load(EV), measurements(MEAS)
    out = []
    for t in sorted(ms):
        e, m = ev[t], ms[t]
        outs = e["test_outputs"]
        f = A.features(m)
        out.append({"task": t, "family": e["family"], "cause": e["cause"], "f": f,
                    "base_correct": m["base"]["fit"] and correct(m["base"]["preds"], outs),
                    "search_correct": m["search"]["fit"] and correct(m["search"]["preds"], outs),
                    "search_calls": m["search"]["calls"], "search_fit": m["search"]["fit"],
                    "construct_correct": m["construct"]["fit"] and correct(m["construct"]["preds"], outs),
                    "construct_fit": m["construct"]["fit"], "construct_calls": m["construct"]["calls"],
                    "base_calls": m["base"]["calls"]})
    return out, ms, ev


def table():
    rs, _, _ = rows()
    for r in rs:
        f = r["f"]
        print(json.dumps({"family": r["family"], "cause": r["cause"], "shape": f["shape"],
                          "ident": round(f["identity_sketch"], 2), "other": round(f["best_other_sketch"], 2),
                          "closest": round(f["closest_fraction"], 2), "level": f["level_complete"],
                          "bank": f["bank"], "area": round(f["area_ratio"], 2),
                          "S": [r["search_correct"], r["search_fit"], r["search_calls"]],
                          "Cn": [r["construct_correct"], r["construct_fit"], r["construct_calls"]]}))
    print(json.dumps({"tasks": len(rs), "by_cause": {c: sum(1 for r in rs if r["cause"] == c) for c in
                                                     sorted({r["cause"] for r in rs})}}))


def constants():
    rs, ms, ev = rows()
    depth = [r["search_calls"] for r in rs if r["cause"] == "search" and r["search_correct"]]
    k_s = up(pct(depth, 0.9))
    spent = []
    for r in rs:
        fix = A.CAUSE_FIX[r["cause"]]
        preds, by, s = K.run_arm(ms[r["task"]], (fix, A.other(fix)), 20_000_000, k_s)
        if preds and correct(preds, ev[r["task"]]["test_outputs"]):
            spent.append(s)
    t_star = up(pct(spent, 0.75))
    score = {}
    for order in (("search", "construct"), ("construct", "search")):
        ok, calls = 0, 0
        for r in rs:
            preds, by, s = K.run_arm(ms[r["task"]], order, t_star, k_s)
            ok += bool(preds and correct(preds, ev[r["task"]]["test_outputs"]))
            calls += s
        score[order] = (ok, -calls / len(rs), order == ("search", "construct"))
    static = max(score, key=lambda o: score[o])
    out = {"K_S": k_s, "T_STAR": t_star, "static_order": list(static),
           "evidence": {"depth_success_calls": sorted(depth), "oracle_spent_calls": sorted(spent),
                        "static_order_scores": {"/".join(o): [v[0], round(-v[1])] for o, v in score.items()}}}
    print(json.dumps(out, indent=1))
    return out


def learn(k_s, l2=1.0):
    rs, ms, _ = rows()
    X = [A.vector(r["f"]) for r in rs]
    y_s = [1 if (r["search_correct"] and r["search_calls"] <= k_s) else 0 for r in rs]
    y_c = [1 if r["construct_correct"] else 0 for r in rs]
    model = {"search": A.train_logistic(X, y_s, l2=l2), "construct": A.train_logistic(X, y_c, l2=l2),
             "features": list(A.NUMERIC) + [f"shape={s}" for s in A.SHAPES],
             "training": {"tasks": len(rs), "search_positive": sum(y_s), "construct_positive": sum(y_c),
                          "l2": l2, "iterations": 3000, "learning_rate": 0.1,
                          "target": "the intervention alone commits a correct answer (search within K_S)"}}
    return model


def power(n_sims=2000, seed=3):
    """Optimistic power: resample source families (missing-operation and depth families separately, to the held
    set's 6 and 3 families) with their tasks' F and C outcomes at T_STAR, and count how often the primary succeeds.
    F was written on the source set, so this is an upper bound for the held set."""
    import random
    from fgc.pipeline import route_fixed
    rs, ms, ev = rows()
    R = load(ROUTERS)
    out = {}
    for r in rs:
        o_f = route_fixed(r["f"], R["fixed"])
        pf, _, _ = K.run_arm(ms[r["task"]], o_f, R["T_STAR"], R["K_S"])
        pc, _, _ = K.run_arm(ms[r["task"]], tuple(R["static_order"]), R["T_STAR"], R["K_S"])
        out[r["task"]] = (bool(pf and correct(pf, ev[r["task"]]["test_outputs"])),
                          bool(pc and correct(pc, ev[r["task"]]["test_outputs"])), r["family"], r["cause"])
    fam = {}
    for t, (f, c, fa, ca) in out.items():
        fam.setdefault((ca, fa), []).append((f, c))
    op = [v for (ca, _), v in fam.items() if ca == "operation"]
    dp = [v for (ca, _), v in fam.items() if ca == "search"]
    rng = random.Random(seed)
    wins = 0
    for _ in range(n_sims):
        fams = [rng.choice(op) for _ in range(6)] + [rng.choice(dp) for _ in range(3)]
        rows_ = [{"family": str(k), "F": f, "C": c} for k, fl in enumerate(fams)
                 for (f, c) in [rng.choice(fl) for _ in range(6)]]
        cst = A.contrast(rows_, "F", "C")
        wins += cst["mcnemar_p"] < 0.05 and cst["family_ci95"] and cst["family_ci95"][0] > 0
    src = A.contrast([{"family": v[2], "F": v[0], "C": v[1]} for v in out.values()], "F", "C")
    print(json.dumps({"source_F_vs_C": src, "optimistic_power": round(wins / n_sims, 3), "sims": n_sims}))


if __name__ == "__main__":
    if sys.argv[1] == "table":
        table()
    elif sys.argv[1] == "constants":
        constants()
    elif sys.argv[1] == "learn":
        R = load(ROUTERS)
        R["learned"] = learn(R["K_S"])
        dump(ROUTERS, R)
        print(json.dumps(R["learned"]["training"]))
    elif sys.argv[1] == "power":
        power(int(sys.argv[2]) if len(sys.argv) > 2 else 2000)
