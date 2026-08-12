"""Quick test: evaluate new fill strategies on ARC + ConceptARC."""
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from reasoning_project.arc_adapter import load_arc_tasks, load_conceptarc_tasks
from reasoning_project.fill_solver import solve_task_fill


def test_fill_on_tasks(tasks, label):
    solved = []
    false_positives = []
    t0 = time.time()

    for i, task in enumerate(tasks):
        train_pairs = [
            (np.asarray(ex.input_grid, dtype=int), np.asarray(ex.output_grid, dtype=int))
            for ex in task.train
        ]
        test_inputs = [np.asarray(ex.input_grid, dtype=int) for ex in task.test]
        test_outputs = [
            np.asarray(ex.output_grid, dtype=int) for ex in task.test
            if ex.output_grid is not None
        ]

        result = solve_task_fill(train_pairs, test_inputs)
        if result is not None:
            preds, meta = result
            if test_outputs:
                correct = all(
                    np.array_equal(p, t) for p, t in zip(preds, test_outputs)
                )
                if correct:
                    solved.append((task.task_id, meta.get("strategy", "unknown")))
                else:
                    false_positives.append((task.task_id, meta.get("strategy", "unknown")))

    elapsed = time.time() - t0
    print(f"\n=== {label} ===")
    print(f"  Total tasks: {len(tasks)}")
    print(f"  Fill solver solved: {len(solved)}")
    print(f"  False positives: {len(false_positives)}")
    print(f"  Elapsed: {elapsed:.1f}s")

    if solved:
        print(f"\n  Solved tasks:")
        by_strategy = {}
        for tid, strat in solved:
            by_strategy.setdefault(strat, []).append(tid)
        for strat, tids in sorted(by_strategy.items()):
            print(f"    {strat}: {len(tids)}")
            for tid in tids:
                print(f"      - {tid}")

    if false_positives:
        print(f"\n  FALSE POSITIVES:")
        for tid, strat in false_positives:
            print(f"    - {tid} ({strat})")

    return solved, false_positives


def main():
    print("Loading tasks...")
    arc_tasks = load_arc_tasks("data/arc")
    carc_tasks = load_conceptarc_tasks("data/conceptarc")
    print(f"Loaded {len(arc_tasks)} ARC, {len(carc_tasks)} ConceptARC tasks")

    arc_solved, arc_fp = test_fill_on_tasks(arc_tasks, "ARC Training")
    carc_solved, carc_fp = test_fill_on_tasks(carc_tasks, "ConceptARC")

    print(f"\n=== SUMMARY ===")
    print(f"ARC: {len(arc_solved)} solved, {len(arc_fp)} FP")
    print(f"ConceptARC: {len(carc_solved)} solved, {len(carc_fp)} FP")


if __name__ == "__main__":
    main()
