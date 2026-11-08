"""The scorer of the specification-reading guide test (after the GO; once). The only module that reads the held
solutions.

    python -s -B run.py score

Order: the GO and every frozen digest; the sealed predictions' digest (runs/SEALED_PREDICTIONS) must equal the
current predictions files' digest; the exclusive marker runs/SCORED; then runs/held/solutions.jsonl.
A task is correct for an arm at a budget when its true test output is one of the arm's two attempts (pass at 2).
Statistics are study A's (`ngrow.analysis.compare`): exact two-sided sign test on the tasks that differ, and a
95% bootstrap interval of the total difference with tasks clustered by the generating edit type (10,000 draws).
Primary (PROTOCOL.md): at 125 operations the guide beats EACH of the hand-set order, the frequency table and the
linear model (p < 0.05 and the interval above 0, for all three); 500 operations is the second budget point.
Secondaries, Holm over three: the guide against its shuffled-specification control and against the small guide at
125; the linear probe (5-fold cross-validated softmax regression of the generating edit type on the encoder's
summary, trained encoder against the same architecture with random weights; paired sign test over tasks).
"""
import hashlib
import json
import os
import random

import numpy as np

from sgd import env as E, gate as GT
from ngrow import analysis as AN

HELD = os.path.join(E.STUDY, "runs", "rehearsal_held" if GT.REHEARSAL else "held")
SEALED = os.path.join(E.STUDY, "runs", "REHEARSAL_SEALED" if GT.REHEARSAL else "SEALED_PREDICTIONS")
SIMPLE = ("hand", "frequency", "linear")


def predictions_digest():
    files = sorted(fn for fn in os.listdir(HELD) if fn.startswith("predictions.") and fn.endswith(".jsonl"))
    digs = {fn: E.sha_file(os.path.join(HELD, fn)) for fn in files}
    return hashlib.sha256("".join(f"{p} {h}\n" for p, h in sorted(digs.items())).encode()).hexdigest(), digs


def probe(Z, y, folds=5, iters=300, lr=0.5, l2=1e-3, seed=20261108):
    """Per-task correctness of a cross-validated softmax regression (standardised inputs)."""
    Z = np.asarray(Z, dtype=np.float64)
    classes = sorted(set(y))
    Y = np.array([classes.index(v) for v in y])
    n, k = len(Y), len(classes)
    order = list(range(n))
    random.Random(seed).shuffle(order)
    fold = np.zeros(n, dtype=int)
    for i, j in enumerate(order):
        fold[j] = i % folds
    ok = np.zeros(n, dtype=bool)
    for f in range(folds):
        tr, te = fold != f, fold == f
        mu, sd = Z[tr].mean(0), Z[tr].std(0) + 1e-8
        A, B = (Z[tr] - mu) / sd, (Z[te] - mu) / sd
        W = np.zeros((Z.shape[1], k))
        b = np.zeros(k)
        T = np.eye(k)[Y[tr]]
        for _ in range(iters):
            L = A @ W + b
            L -= L.max(1, keepdims=True)
            P = np.exp(L)
            P /= P.sum(1, keepdims=True)
            G = (P - T) / len(A)
            W -= lr * (A.T @ G + l2 * W)
            b -= lr * G.sum(0)
        ok[te] = (B @ W + b).argmax(1) == Y[te]
    return ok


def main():
    salt = GT.require_go()
    fc = None
    if not GT.REHEARSAL:
        salt, fc = GT.git_checks()
    joint, digs = predictions_digest()
    sealed = E.load(SEALED)
    if sealed["joint_sha256"] != joint:
        raise GT.GateRefused("the predictions differ from the sealed ones")
    fd = GT.take_marker()
    os.write(fd, json.dumps({"sealed_predictions": joint}).encode())
    os.close(fd)
    c = E.load(os.path.join(E.STUDY, "config", "CONFIG.json"))
    preds = {}
    for fn in sorted(digs):
        with open(os.path.join(HELD, fn), encoding="utf-8") as f:
            for x in f:
                if x.strip():
                    r = json.loads(x)
                    preds[r["task"]] = r
    sols = {}
    for fn in sorted(f for f in os.listdir(HELD) if f.startswith("solutions.") and f.endswith(".jsonl")):
        with open(os.path.join(HELD, fn), encoding="utf-8") as f:
            for x in f:
                if x.strip():
                    s = json.loads(x)
                    sols[s["task"]] = s
    if sorted(preds) != sorted(sols):
        raise RuntimeError("predictions and solutions name different tasks")
    arms = sorted({k.split("@")[0] for r in preds.values() for k in r["arms"]})
    budgets = c["budgets"]
    rows = []
    for t in sorted(preds):
        truth = [list(r) for r in sols[t]["test_output"]]
        d = {"task": t, "bench": "held", "cluster": sols[t]["edit"], "edit": sols[t]["edit"]}
        for a in arms:
            for B in budgets:
                att = preds[t]["arms"][f"{a}@{B}"]["attempts"]
                d[f"{a}@{B}"] = int(any([list(r) for r in g] == truth for g in att))
        rows.append(d)
    res = {"n_tasks": len(rows), "sealed_predictions": joint, "salt": salt, "freeze_commit": fc,
           "rehearsal": GT.REHEARSAL}
    prim = {}
    for B in budgets:
        prim[str(B)] = {s: AN.compare(rows, f"spec_guide@{B}", f"{s}@{B}") for s in SIMPLE}
    first = budgets[0]
    beats = [prim[str(first)][s]["decision"] == f"spec_guide@{first} beats {s}@{first}" for s in SIMPLE]
    res["primary"] = {"budget": first, "versus": prim[str(first)], "beats_all_three": all(beats)}
    res["second_budget"] = {"budget": budgets[1], "versus": prim[str(budgets[1])],
                            "beats_all_three": all(prim[str(budgets[1])][s]["decision"] ==
                                                   f"spec_guide@{budgets[1]} beats {s}@{budgets[1]}" for s in SIMPLE)}
    sec = {"1_versus_shuffled": AN.compare(rows, f"spec_guide@{first}", f"shuffled_spec@{first}"),
           "2_versus_small_guide": AN.compare(rows, f"spec_guide@{first}", f"small_guide@{first}")}
    Zt = [preds[t]["z_trained"] for t in sorted(preds)]
    Zr = [preds[t]["z_random"] for t in sorted(preds)]
    y = [sols[t]["edit"] for t in sorted(preds)]
    ok_t, ok_r = probe(Zt, y), probe(Zr, y)
    prow = [{"bench": "held", "cluster": e, "trained": int(a), "random": int(b)} for e, a, b in zip(y, ok_t, ok_r)]
    sec["3_probe_trained_versus_random"] = dict(AN.compare(prow, "trained", "random"),
                                               accuracy_trained=round(float(ok_t.mean()), 4),
                                               accuracy_random=round(float(ok_r.mean()), 4),
                                               majority=round(max(y.count(v) for v in set(y)) / len(y), 4))
    adj = AN.holm({k: v["exact_mcnemar_p"] for k, v in sec.items()})
    for k, v in sec.items():
        v["holm_p"] = adj[k]
    res["secondaries"] = sec
    res["table"] = {a: {str(B): sum(r[f"{a}@{B}"] for r in rows) for B in budgets} for a in arms}
    edits = sorted({r["edit"] for r in rows})
    res["edit_balanced_share"] = {a: {str(B): round(float(np.mean([np.mean([r[f"{a}@{B}"] for r in rows
                                                                            if r["edit"] == e]) for e in edits])), 4)
                                      for B in budgets} for a in arms}
    res["by_edit"] = {e: {"n": sum(1 for r in rows if r["edit"] == e),
                          **{f"{a}@{first}": sum(r[f"{a}@{first}"] for r in rows if r["edit"] == e) for a in arms}}
                      for e in edits}
    res["work"] = {f"{a}@{B}": {"ops": sum(preds[t]["arms"][f"{a}@{B}"]["ops"] for t in preds),
                                "edit_applications": sum(preds[t]["arms"][f"{a}@{B}"]["edit"] for t in preds),
                                "cpu_s": round(sum(preds[t]["arms"][f"{a}@{B}"]["cpu_s"] for t in preds), 3)}
                   for a in arms for B in budgets}
    res["setup_cpu_s"] = round(sum(preds[t]["setup_cpu_s"] for t in preds), 3)
    res["per_task"] = rows
    E.dump(os.path.join(HELD, "RESULTS.json"), res, indent=1)
    print(json.dumps({"primary_beats_all_three": res["primary"]["beats_all_three"], "table": res["table"]}))
