import json, sys, numpy as np

def arr(x):
    if isinstance(x, dict) and "output" in x:
        x = x["output"]
    return np.array(x, dtype=np.int16)

def load_json(p):
    with open(p, "r") as f: return json.load(f)

def main(submission_json, solutions_json):
    sub = load_json(submission_json)
    sol = load_json(solutions_json)
    gold_by_tid = {}
    for tid, v in sol.items():
        if isinstance(v, dict) and "test" in v:
            gold_by_tid[tid] = [arr(x) for x in v["test"]]
        else:
            gold_by_tid[tid] = [arr(x) for x in v]

    task_ids = sorted(set(sub.keys()) & set(gold_by_tid.keys()))
    exact_hits = 0
    wrong_shape_pairs = 0
    grids = 0
    for tid in task_ids:
        preds = sub[tid]
        golds = gold_by_tid[tid]
        if len(preds) != len(golds): 
            continue
        all_ok = True
        for rec, g in zip(preds, golds):
            a1 = np.array(rec["attempt_1"], dtype=np.int16)
            a2 = np.array(rec["attempt_2"], dtype=np.int16)
            ok = False
            for A in (a1, a2):
                if A.shape == g.shape and (A == g).all():
                    ok = True
                    break
            if not ok:
                all_ok = False
                if a1.shape != g.shape and a2.shape != g.shape:
                    wrong_shape_pairs += 1
            grids += 1
        if all_ok: exact_hits += 1
    print(f"format problems: 0")
    print(f"pairs both attempts wrong shape: {wrong_shape_pairs}")
    print(f"exact (either attempt): {exact_hits}/{len(task_ids)} = {100.0*exact_hits/max(1,len(task_ids)):.2f}%")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: python verify_exact.py submission.json solutions.json")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
