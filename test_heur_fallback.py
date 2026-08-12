# test_heur_fallback.py
import json, numpy as np, itertools
from components import Grid
from solver_plus import SolverPlus, SolverPlusConfig

with open('data/challenges_eval.json') as f:
    chall = json.load(f)

# run on a handful of tasks for speed
task_ids = list(itertools.islice(chall.keys(), 8))

sv = SolverPlus(SolverPlusConfig(
    beam=64, max_depth=2,
    use_prune=True,
    use_repair=False,
    use_heuristic_fallback=True,   # <-- ON
    use_llm_fallback=False,        # keep off unless you really want it
))

for tid in task_ids:
    task = chall[tid]
    train_pairs = [
        (Grid(np.array(p['input'], dtype=int)),
         Grid(np.array(p['output'], dtype=int)))
        for p in task['train']
    ]
    tests = [Grid(np.array(t['input'], dtype=int)) for t in task['test']]

    outs = sv.solve_task(train_pairs, tests)
    print(f"\nTask {tid}")
    for i, preds in enumerate(outs):
        if not preds:
            print(f"  test[{i}]: <no preds>")
            continue
        a1, a2 = preds[:2]
        nz1 = int((a1.data != 0).sum())
        nz2 = int((a2.data != 0).sum())
        print(f"  test[{i}]: a1 shape={a1.data.shape} nz={nz1} | a2 shape={a2.data.shape} nz={nz2}")
