"""Arms, failure features, the learned router's model and the statistics of the failure-guided choice test.

The arms are executed only through the strong full-bank contract (fgc/contract.py: one bank, one meter, arms that
differ only in order). Router overheads: the failure record and the routers' features use no search (no calls).
"""
import hashlib
import json
import math
import os
import random

from fgc.contract import BANK as INTERVENTIONS                              # noqa: E402  (one bank)
ARMS = ("A", "B", "C", "D", "E", "F", "G", "H")
ARM_NAMES = {"A": "base only", "B": "base plus extra search", "C": "static full bank, fixed pre-declared order",
             "D": "random intervention order", "E": "shuffled diagnosis (the fixed router on another task's record)",
             "F": "fixed evidence-based router (hand-written rules)", "G": "learned router (trained on source)",
             "H": "oracle router (the generator's cause; upper bound)"}
CAUSE_FIX = {"search": "search", "operation": "construct"}
BUDGET_MULTS = (0.25, 0.5, 1.0, 2.0, 4.0)


def h(s):
    return hashlib.sha256(s.encode()).hexdigest()


def other(iv):
    return INTERVENTIONS[1 - INTERVENTIONS.index(iv)]


# ------------------------------------------------------------------ failure features (system side)
SHAPE_CLASSES = (("equals", "same"), ("transposed", "transposed"), ("times", "scale_up"), ("divided", "scale_down"),
                 ("fewer rows", "trim_fixed"), ("half", "half"), ("always", "fixed"), ("never larger", "shrink"),
                 ("no simple", "none"))


def features(m):
    rec, base = m["record"], m["base"]
    sr = rec["shape_relation"]
    shape = next((c for k, c in SHAPE_CLASSES if k in sr), "none")
    sk = rec["sketches"]
    ident = next((s["score"] for s in sk if s["form"] == "?(I)"), 0.0)
    others = [s["score"] for s in sk if s["form"] != "?(I)"]
    cl = rec["closest"]
    frac = (cl["cells_correct"] / cl["cells_total"]) if cl and cl["cells_total"] else 0.0
    ins, outs = rec["sizes"]["in"], rec["sizes"]["out"]
    area_ratio = sum(o[0] * o[1] for o in outs) / max(1, sum(i[0] * i[1] for i in ins))
    return {"shape": shape, "identity_sketch": ident, "best_other_sketch": max(others) if others else 0.0,
            "closest_fraction": frac, "level_complete": base["level_complete"] or 0, "bank": base["bank"] or 0,
            "n_demos": rec["n_demos"], "area_ratio": area_ratio,
            "colours_in": sum(rec["colours"]["in"]) / len(rec["colours"]["in"]),
            "colours_out": sum(rec["colours"]["out"]) / len(rec["colours"]["out"])}


NUMERIC = ("identity_sketch", "best_other_sketch", "closest_fraction", "level_complete", "bank", "n_demos",
           "area_ratio", "colours_in", "colours_out")
SHAPES = tuple(c for _, c in SHAPE_CLASSES)


def vector(f):
    return [float(f[k]) for k in NUMERIC] + [1.0 if f["shape"] == s else 0.0 for s in SHAPES]


# ------------------------------------------------------------------ learned router (logistic regression, numpy)
def train_logistic(X, y, l2=1.0, iters=3000, lr=0.1):
    import numpy as np
    X = np.asarray(X, float)
    y = np.asarray(y, float)
    mu, sd = X.mean(0), X.std(0)
    sd[sd == 0] = 1.0
    Z = (X - mu) / sd
    Z = np.hstack([Z, np.ones((len(Z), 1))])
    w = np.zeros(Z.shape[1])
    for _ in range(iters):
        p = 1 / (1 + np.exp(-Z @ w))
        grad = Z.T @ (p - y) / len(y) + l2 * np.r_[w[:-1], 0.0] / len(y)
        w -= lr * grad
    return {"mu": mu.tolist(), "sd": sd.tolist(), "w": w.tolist()}


def predict_logistic(model, x):
    z = [(xi - m) / s for xi, m, s in zip(x, model["mu"], model["sd"])] + [1.0]
    t = sum(a * b for a, b in zip(z, model["w"]))
    return 1 / (1 + math.exp(-t))


# ------------------------------------------------------------------ statistics (evaluator side)
def mcnemar_exact(b, c):
    n, k = b + c, min(b, c)
    if n == 0:
        return 1.0
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def cluster_boot(rows, a, b, n=10000, seed=7):
    """Percentile 95% interval of the mean paired difference (a minus b), resampling families with replacement."""
    fams = sorted({r["family"] for r in rows})
    by = {f: [int(r[a]) - int(r[b]) for r in rows if r["family"] == f] for f in fams}
    rng = random.Random(seed)
    means = []
    for _ in range(n):
        d = [x for f in (rng.choice(fams) for _ in fams) for x in by[f]]
        if d:
            means.append(sum(d) / len(d))
    means.sort()
    return [round(means[int(0.025 * len(means))], 4), round(means[int(0.975 * len(means))], 4)] if means else None


def contrast(rows, a, b):
    both = sum(1 for r in rows if r[a] and r[b])
    only_a = sum(1 for r in rows if r[a] and not r[b])
    only_b = sum(1 for r in rows if r[b] and not r[a])
    n = len(rows)
    return {"tasks": n, "both": both, "only_" + a: only_a, "only_" + b: only_b, "neither": n - both - only_a - only_b,
            "difference": round((only_a - only_b) / n, 4) if n else None, "mcnemar_p": mcnemar_exact(only_a, only_b),
            "family_ci95": cluster_boot(rows, a, b), "families": len({r["family"] for r in rows})}


def holm(ps):
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    adj, run = [None] * len(ps), 0.0
    for rank, i in enumerate(order):
        run = max(run, min(1.0, (len(ps) - rank) * ps[i]))
        adj[i] = run
    return adj
