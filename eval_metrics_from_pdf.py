# =============================
# eval_metrics_from_pdf.py
# (task-level exact + pixel accuracy as in the PDF you shared)
# =============================
import json, numpy as np, sys

def _arr(x):
    if isinstance(x, dict) and "output" in x: x = x["output"]
    return np.array(x, dtype=int)

# Usage: python3 eval_metrics_from_pdf.py submission.json solutions.json
if __name__ == "__main__" and len(sys.argv) >= 3:
    sub = json.load(open(sys.argv[1]))
    sol_raw = json.load(open(sys.argv[2]))

    # solutions may be {task_id: [test_outputs...]} or {task_id: {"test":[{output:..}, ...]}}
    def gold_tests(tid):
        v = sol_raw[tid]
        if isinstance(v, dict) and "test" in v:
            return [_arr(g) for g in v["test"]]
        else:
            return [_arr(g) for g in v]

    total_tasks = 0
    exact = 0
    pix_correct = 0
    pix_total = 0
    bad_shape_pairs = 0

    for tid, preds in sub.items():
        golds = gold_tests(tid)
        if len(golds) != len(preds):
            # skip mismatched (shouldn't happen for ARC JSON)
            continue
        all_exact = True
        for g, rec in zip(golds, preds):
            a1 = np.array(rec["attempt_1"], int)
            a2 = np.array(rec["attempt_2"], int)
            # exact attempt if shapes match and values identical
            ok = False
            best = None
            for a in (a1, a2):
                if a.shape == g.shape and (a == g).all():
                    ok = True; best = a; break
            if not ok:
                all_exact = False
            # pixel accuracy contribution: use the attempt with higher per-pixel match; if shapes differ, count as 0
            accs = []
            for a in (a1, a2):
                if a.shape == g.shape:
                    accs.append((a == g).sum())
                else:
                    accs.append(0)
            pix_correct += max(accs)
            pix_total += int(g.size)
            if a1.shape != g.shape and a2.shape != g.shape:
                bad_shape_pairs += 1
        total_tasks += 1
        if all_exact:
            exact += 1

    print(f"tasks exact: {exact}/{total_tasks} = {100.0*exact/max(1,total_tasks):.2f}%")
    print(f"pixel accuracy: {100.0*pix_correct/max(1,pix_total):.2f}%  (pairs wrong shape: {bad_shape_pairs})")
