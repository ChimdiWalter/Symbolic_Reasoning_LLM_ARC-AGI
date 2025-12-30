# eval_curveball_metrics.py
# usage:
#   python3 eval_curveball_metrics.py data/curveball_solutions submission_curveball.json
from __future__ import annotations
import os, sys, json, numpy as np

def to_np(x): return np.array(x, dtype=np.int16)

def main(solutions_dir, pred_json):
    pred = json.load(open(pred_json))
    task_exact = 0; task_total = 0
    pix_correct = 0; pix_total = 0
    wrong_shape = 0

    for stem, rec in pred.items():
        sol_path = os.path.join(solutions_dir, f"{stem}.json")
        if not os.path.isfile(sol_path):
            continue
        sol = json.load(open(sol_path))
        y_hat = to_np(rec["test"][0]["output"])
        y_true = to_np(sol["test"][0]["output"])
        task_total += 1
        if y_hat.shape != y_true.shape:
            wrong_shape += 1
            # count nothing correct if shape mismatch
        else:
            eq = (y_hat == y_true)
            pix_correct += int(eq.sum())
            pix_total   += int(eq.size)
            if eq.all(): task_exact += 1

    if task_total == 0:
        print("No overlapping tasks with solutions; cannot score.")
        return

    task_acc = 100.0 * task_exact / task_total
    pix_acc  = 100.0 * (pix_correct / max(1, pix_total))
    print(f"tasks exact: {task_exact}/{task_total} = {task_acc:.2f}%")
    print(f"pixel accuracy: {pix_acc:.2f}%  (wrong-shape tasks: {wrong_shape})")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: python3 eval_curveball_metrics.py data/curveball_solutions submission_curveball.json")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])

