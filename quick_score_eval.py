# quick_score_eval.py
import json, numpy as np

def to_arr(x):
    if isinstance(x, dict) and "output" in x: x = x["output"]
    return np.array(x, dtype=int)

pred_path = "submission_eval.json"
ch_path   = "data/challenges_eval.json"
sol_path  = "data/arc-agi_evaluation_solutions.json"

pred = json.load(open(pred_path))
ch   = json.load(open(ch_path))
sol  = json.load(open(sol_path))

hit = tot = 0
for tid, spec in ch.items():
    golds = sol[tid]["test"] if isinstance(sol[tid], dict) else sol[tid]
    golds = [to_arr(g) for g in golds]
    guesses = pred.get(tid, [])
    for i, g in enumerate(golds):
        if i >= len(guesses):
            tot += 1; continue
        a1 = np.array(guesses[i]["attempt_1"], int)
        a2 = np.array(guesses[i]["attempt_2"], int)
        ok = (a1.shape == g.shape and np.array_equal(a1, g)) or \
             (a2.shape == g.shape and np.array_equal(a2, g))
        hit += int(ok); tot += 1
print(f"local eval (either attempt exact): {hit}/{tot} = {hit/tot:.2%}")
