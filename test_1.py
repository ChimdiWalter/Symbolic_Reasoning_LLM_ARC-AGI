# audit_preds.py
import json, numpy as np

pred = json.load(open("submission_eval_small.json"))
sol  = json.load(open("data/arc-agi_evaluation_solutions.json"))

def to_arr(x):
    if isinstance(x, dict) and "output" in x:
        return np.array(x["output"], dtype=int)
    return np.array(x, dtype=int)

def load_gold(sol_entry):
    if isinstance(sol_entry, dict) and "test" in sol_entry:
        return [to_arr(t) for t in sol_entry["test"]]
    elif isinstance(sol_entry, list):
        return [to_arr(t) for t in sol_entry]
    raise ValueError("Unexpected solutions format")

bad = []
all_zero = 0
total = 0

for tid, sols in sol.items():
    gold_tests = load_gold(sols)
    preds = pred.get(tid, [])
    for i, gold in enumerate(gold_tests):
        total += 1
        guess = None
        if i < len(preds) and isinstance(preds[i], dict) and "attempt_1" in preds[i]:
            guess = np.array(preds[i]["attempt_1"], dtype=int)
        if guess is None or guess.shape != gold.shape:
            bad.append((tid, i, "missing_or_shape_mismatch"))
            continue
        if np.all(guess == 0):
            all_zero += 1
        if not np.array_equal(guess, gold):
            bad.append((tid, i, "mismatch"))

print("total tests:", total)
print("num all-zero grids:", all_zero)
print("num bad (missing/shape/mismatch):", len(bad))
print("sample bad:", bad[:10])
