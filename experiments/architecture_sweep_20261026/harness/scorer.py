"""Separate scorer process for ARC_eval_dev (the only reader of the evaluation answers in this campaign).

    python -m harness.scorer --pred runs/<run>/predictions.json --out runs/<run>/score.json

predictions.json: {"task_id": [[attempt_1, attempt_2] per test output, ...], ...} (an attempt may be null).
Writes exact per-output pass@2, strict all-query task success, and per-task rows. Policy code never imports this
module (tests/test_harness.py checks that), and the policy's decisions are written before this process starts.
"""
import argparse
import json

import numpy as np

from harness import paths as P


def score(pred, sol, missing_wrong=False):
    """missing_wrong: every task of `sol` is scored; a task without predictions counts as wrong (cohort-complete)."""
    rows, n_out, n_ok, n_task_ok = {}, 0, 0, 0
    for tid, outs in sol.items():
        if tid not in pred and not missing_wrong:
            continue
        per = []
        for j, truth in enumerate(outs):
            T = np.asarray(truth)
            atts = pred[tid][j] if (tid in pred and j < len(pred[tid])) else []
            per.append(any(a is not None and np.asarray(a).shape == T.shape and np.array_equal(np.asarray(a), T)
                           for a in atts[:2]))
        rows[tid] = per
        n_out += len(per)
        n_ok += sum(per)
        n_task_ok += all(per)
    return {"outputs": n_out, "pass2_outputs": n_ok, "tasks": len(rows), "tasks_all_correct": n_task_ok,
            "rows": rows}


def reach(path, sol):
    """ARC_eval_dev reachability from the label-free build record: which action's resulting attempts, and which
    version-space behaviour anywhere in the one-step successors, would be exactly correct (diagnostic only)."""
    from harness.reach import classify
    rows, cls = {}, {}
    with P.open_allowed(path) as f:
        for line in f:
            r = json.loads(line)
            truth = sol[r["task_id"]]

            def ok(att):
                pr = {"t": [[r["behaviours"].get(q, [None] * len(truth))[j] if q in r["behaviours"] else None
                             for q in att] for j in range(len(truth))]}
                return all(score(pr, {"t": truth})["rows"]["t"])
            beh_ok = any(all(np.array_equal(np.asarray(p[j]), np.asarray(t)) for j, t in enumerate(truth))
                         for p in r["behaviours"].values() if p is not None)
            y2 = [ok(x["att"] if "att" in x else x["attempts"]) for x in r["rows"]]
            c = classify([x["a"][0] for x in r["rows"]], y2, ok(r["base_attempts"]))
            rows[r["task_id"]] = {"class": c, "any_behaviour_correct": beh_ok, "n_vs": r["n_vs"],
                                  "reaching": sorted({x["a"][0] for x, y in zip(r["rows"], y2) if y})}
            cls[c] = cls.get(c, 0) + 1
    return {"tasks": len(rows), "classes": cls, "rows": rows,
            "tasks_with_any_correct_behaviour": sum(v["any_behaviour_correct"] for v in rows.values())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pred")
    ap.add_argument("--reach")
    ap.add_argument("--out", required=True)
    ap.add_argument("--all", action="store_true", help="score the whole ARC_eval_dev cohort; missing = wrong")
    a = ap.parse_args()
    if a.reach:
        with P.open_allowed(P.EVAL_SOLUTIONS, role="scorer") as f:
            sol = json.load(f)
        res = reach(a.reach, sol)
        with P.open_allowed(a.out, mode="w") as f:
            json.dump(res, f, indent=1)
        print(json.dumps({k: v for k, v in res.items() if k != "rows"}))
        return
    with P.open_allowed(a.pred) as f:
        pred = json.load(f)
    with P.open_allowed(P.EVAL_SOLUTIONS, role="scorer") as f:
        sol = json.load(f)
    if a.all:
        from harness import data as D
        res = score(pred, {k: sol[k] for k in D.split_ids("ARC_eval_dev")}, missing_wrong=True)
    else:
        res = score(pred, {k: v for k, v in sol.items() if k in pred})
    with P.open_allowed(a.out, mode="w") as f:
        json.dump(res, f, indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != "rows"}))


if __name__ == "__main__":
    main()
