"""Expressivity atlas of the v1 typed language on EXPOSED real ARC development tasks (dev60). This is a measurement,
not a score.

    python scripts/neural_cora_v1_atlas.py solve   # solver side: demonstrations and test inputs only (no answers)
    python scripts/neural_cora_v1_atlas.py score   # evaluator side: the only stage that reads answers

It lives outside cora_neural_v1/ so that the pilot's frozen code (records/NEURAL_CORA_V1_FREEZE_MANIFEST.json) stays
unchanged; the pilot never imports it.

The dev60 tasks are 60 public ARC-AGI-2 training tasks, already examined in development (claim ledger rows 1-5 and
11), so nothing here is a generalization claim.

**Solve stage.** For each task it runs C+H, the strong symbolic order, over the v1 language `ncv1-g0` for 3000
candidates on the demonstrations. It records:
- whether any program fits every demonstration (*compile coverage*);
- the distinct test predictions;
- the observable diagnoses;
- a coarse, demonstration-derived transformation profile: shape change; cells added, removed or recoloured; object
  count change; more than one output colour per object.

**Score stage.** It adds:
- *correct-query coverage*: a consistent prediction equals the first test output;
- first-attempt correctness;
- pass@2.

Only the first test input is used; that is what the v1 search reads.
"""
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
OUT = os.path.join(HERE, "outputs", "neural_cora_v1", "atlas")
BUDGET = 3000


def profile(train):
    """Coarse transformation profile from the demonstrations only."""
    from cora_neural_v1 import space as SP
    shape = any(np.asarray(a).shape != np.asarray(b).shape for a, b in train)
    add = rem = rec = 0
    dobj = []
    multicolour_obj = False
    for a, b in train:
        A, B = np.asarray(a), np.asarray(b)
        if A.shape == B.shape:
            add += int(((A == 0) & (B != 0)).sum())
            rem += int(((A != 0) & (B == 0)).sum())
            rec += int(((A != 0) & (B != 0) & (A != B)).sum())
        try:
            oa, ob = SP._objects(A), SP._objects(B)
            dobj.append(len(ob) - len(oa))
        except Exception:                                           # noqa: BLE001
            pass
        if A.shape == B.shape:
            for o in SP._objects(A) if A.size <= 900 else []:
                cells = getattr(o, "cells", None)
                if cells is not None and len({int(B[r, c]) for r, c in cells} - {0}) > 1:
                    multicolour_obj = True
                    break
    kinds = []
    if shape:
        kinds.append("size_change")
    else:
        kinds += [k for k, n in (("adds_cells", add), ("removes_cells", rem), ("recolours_cells", rec)) if n]
    if dobj and any(d != 0 for d in dobj):
        kinds.append("object_count_changes")
    if multicolour_obj:
        kinds.append("object_gets_several_colours")
    return {"size_change": shape, "added": add, "removed": rem, "recoloured": rec, "object_count_delta": dobj,
            "kinds": kinds}


def solve():
    from cora_funnel.run import load
    from cora_neural_v1 import search as S
    from cora_neural_v1 import space as SP
    os.makedirs(OUT, exist_ok=True)
    rows = []
    t0 = time.process_time()
    for key, task in load("dev60"):
        train = [(p["input"], p["output"]) for p in task["train"]]
        t = {"task_id": key, "train": train, "test_inputs": [task["test"][0]["input"]]}
        prof = profile(train)
        if prof["size_change"]:                                     # ncv1-g0 cannot express a shape change
            r = {"attempts": [], "predictions": [], "pred_at": [], "n_consistent": 0, "state": {"diagnoses": ["NO_FIT_OBSERVED"]},
                 "skipped": "output shape differs from input shape: outside ncv1-g0 by construction"}
        else:
            doms = SP.domains(train)
            r = S.search_typed(t, SP.heuristic_scores(doms, train), BUDGET)
            r.pop("kept", None)
        rows.append({"task_id": key, "profile": prof, "result": r})
        print(key, prof["kinds"], r.get("n_consistent"), flush=True)
    with open(os.path.join(OUT, "dev60_solve.jsonl"), "w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")
    print("solve cpu_s", round(time.process_time() - t0, 1), flush=True)


def score():
    from cora_funnel.evaluate import answers
    ans = answers("dev60")                                          # the evaluator-only, sha-pinned key map
    rows = [json.loads(l) for l in open(os.path.join(OUT, "dev60_solve.jsonl"))]

    def first_answer(a):                                            # answers(): {key: ([test outputs], stratum)}
        return np.asarray(a[0][0])

    def eq(p, A):
        P = np.asarray(p)
        return P.shape == A.shape and bool((P == A).all())
    out, by_kind = [], {}
    for r in rows:
        A = first_answer(ans[r["task_id"]])
        res = r["result"]
        cov = any(eq(p, A) for p in res.get("predictions", []))
        p2 = any(eq(p, A) for p in res.get("attempts", [])[:2])
        fit = res.get("n_consistent", 0) > 0
        out.append({"task_id": r["task_id"], "kinds": r["profile"]["kinds"], "fits": fit, "correct_coverage": cov,
                    "pass@2": p2, "diagnoses": res.get("state", {}).get("diagnoses", [])})
        for k in r["profile"]["kinds"] or ["no_change_detected"]:
            d = by_kind.setdefault(k, {"n": 0, "fits": 0, "correct_coverage": 0, "pass@2": 0})
            d["n"] += 1
            d["fits"] += fit
            d["correct_coverage"] += cov
            d["pass@2"] += p2
    summ = {"n": len(out), "fits": sum(o["fits"] for o in out), "correct_coverage": sum(o["correct_coverage"] for o in out),
            "pass@2": sum(o["pass@2"] for o in out), "fits_but_wrong": sum(o["fits"] and not o["correct_coverage"] for o in out),
            "size_change_tasks": sum("size_change" in o["kinds"] for o in out), "by_kind": by_kind,
            "note": "exposed development tasks; an expressivity measurement of ncv1-g0 under C+H@3000, not a score"}
    json.dump({"summary": summ, "tasks": out}, open(os.path.join(OUT, "dev60_atlas.json"), "w"), indent=1)
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    {"solve": solve, "score": score}[sys.argv[1]]()
