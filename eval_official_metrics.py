import json, sys, numpy as np
from pathlib import Path

def arr(x):
    if isinstance(x, dict) and "output" in x:
        x = x["output"]
    return np.array(x, dtype=np.int16)

def load_json(p):
    with open(p, "r") as f: return json.load(f)

def per_grid_pixel_acc(pred, gold):
    if pred.shape != gold.shape:
        # zero score if wrong shape (consistent with typical ARC scoring)
        return 0.0
    return float((pred == gold).sum()) / float(pred.size)

def task_exact_ok(task_preds, task_golds):
    # exact = every test grid matches on shape + pixels
    if len(task_preds) != len(task_golds): return False
    for (p, g) in zip(task_preds, task_golds):
        if p.shape != g.shape: return False
        if not (p == g).all(): return False
    return True

def main(submission_json, solutions_json):
    sub = load_json(submission_json)
    sol = load_json(solutions_json)

    # normalize solutions dict structure
    # sol[tid] is either {"test":[{output:...}, ...]} or a list of outputs
    gold_by_tid = {}
    for tid, v in sol.items():
        if isinstance(v, dict) and "test" in v:
            gold_by_tid[tid] = [arr(x) for x in v["test"]]
        else:
            gold_by_tid[tid] = [arr(x) for x in v]

    task_ids = sorted(set(sub.keys()) & set(gold_by_tid.keys()))
    exact_hits = 0
    pixel_scores = []
    wrong_shape_pairs = 0
    grids = 0

    for tid in task_ids:
        # submission format: list of test guesses with attempt_1/attempt_2
        preds = sub[tid]
        # choose best attempt per test by pixel acc (local eval convenience)
        chosen = []
        golds  = gold_by_tid[tid]
        if len(preds) != len(golds):
            # skip mismatch
            continue
        for rec, g in zip(preds, golds):
            a1 = np.array(rec["attempt_1"], dtype=np.int16)
            a2 = np.array(rec["attempt_2"], dtype=np.int16)
            # pick the higher pixel-acc attempt (this doesn’t change task-exact,
            # just a friendlier local report)
            p1 = per_grid_pixel_acc(a1, g)
            p2 = per_grid_pixel_acc(a2, g)
            best = a1 if p1 >= p2 else a2
            chosen.append(best)

        # task exact
        if task_exact_ok(chosen, golds): exact_hits += 1

        # pixel correctness
        for p,g in zip(chosen, golds):
            grids += 1
            if p.shape != g.shape:
                wrong_shape_pairs += 1
            pixel_scores.append(per_grid_pixel_acc(p, g))

    total_tasks = len(task_ids)
    avg_pixel = 100.0 * (sum(pixel_scores) / max(1, len(pixel_scores)))
    print(f"tasks exact: {exact_hits}/{total_tasks} = {100.0*exact_hits/max(1,total_tasks):.2f}%")
    print(f"pixel accuracy: {avg_pixel:.2f}%  (pairs wrong shape: {wrong_shape_pairs})")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: python eval_official_metrics.py submission.json solutions.json")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
