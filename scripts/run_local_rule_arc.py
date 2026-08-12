"""Run local-rule synthesis on ARC tasks and report results."""
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from reasoning_project.arc_adapter import load_arc_tasks
from reasoning_project.local_rules import (
    solve_task_local_rules,
    multi_pass_local_rule,
    apply_local_rule,
    apply_local_rule_with_fallback,
    STRATEGY_REGISTRY,
)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--arc-root", default="data/arc")
    parser.add_argument("--output-dir", default="outputs/local_rule_arc")
    parser.add_argument("--max-tasks", type=int, default=None)
    parser.add_argument("--multi-pass", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    tasks = load_arc_tasks(args.arc_root)
    if args.max_tasks:
        tasks = tasks[:args.max_tasks]
    print(f"Loaded {len(tasks)} tasks")

    solved = []
    solved_multi = []
    per_task = []
    t0 = time.time()

    for i, task in enumerate(tasks):
        if i % 100 == 0:
            print(f"  {i}/{len(tasks)} ({time.time()-t0:.0f}s, solved={len(solved)})", flush=True)

        train_pairs = [
            (np.asarray(ex.input_grid, dtype=int), np.asarray(ex.output_grid, dtype=int))
            for ex in task.train
        ]
        test_inputs = [np.asarray(ex.input_grid, dtype=int) for ex in task.test]
        test_outputs = [np.asarray(ex.output_grid, dtype=int) for ex in task.test]

        same_size = all(inp.shape == out.shape for inp, out in train_pairs)

        result = solve_task_local_rules(train_pairs, test_inputs) if same_size else None
        task_solved = False
        strategy_used = ""

        if result is not None:
            predictions, rule = result
            all_correct = True
            for pred, expected in zip(predictions, test_outputs):
                if pred.shape != expected.shape or not np.array_equal(pred, expected):
                    all_correct = False
                    break
            if all_correct:
                solved.append(task.task_id)
                task_solved = True
                strategy_used = rule.strategy_name

        if not task_solved and same_size and args.multi_pass:
            mp_result = multi_pass_local_rule(train_pairs, max_passes=3)
            if mp_result is not None:
                n_passes, rule = mp_result
                all_correct = True
                for test_inp, expected in zip(test_inputs, test_outputs):
                    current = test_inp.copy()
                    for _ in range(n_passes):
                        r = apply_local_rule(current, rule)
                        if r is None:
                            r = apply_local_rule_with_fallback(current, rule)
                        if np.array_equal(r, current):
                            break
                        current = r
                    if current.shape != expected.shape or not np.array_equal(current, expected):
                        all_correct = False
                        break
                if all_correct:
                    solved_multi.append(task.task_id)
                    task_solved = True
                    strategy_used = f"multi_{n_passes}x_{rule.strategy_name}"

        per_task.append({
            "task_id": task.task_id,
            "solved": task_solved,
            "strategy": strategy_used,
            "same_size": same_size,
        })

    elapsed = time.time() - t0
    print(f"\nLocal-rule synthesis solved {len(solved)}/{len(tasks)} (single-pass) in {elapsed:.0f}s")
    if args.multi_pass:
        print(f"Multi-pass added: {len(solved_multi)} more")
    print(f"Total: {len(solved) + len(solved_multi)}")

    for tid in solved:
        s = next(p for p in per_task if p["task_id"] == tid)
        print(f"  {tid}: {s['strategy']}")
    for tid in solved_multi:
        s = next(p for p in per_task if p["task_id"] == tid)
        print(f"  {tid}: {s['strategy']} (multi-pass)")

    summary = {
        "total_tasks": len(tasks),
        "single_pass_solved": len(solved),
        "multi_pass_solved": len(solved_multi),
        "total_solved": len(solved) + len(solved_multi),
        "elapsed_seconds": round(elapsed, 1),
        "solved_ids_single": solved,
        "solved_ids_multi": solved_multi,
        "strategies_available": list(STRATEGY_REGISTRY.keys()),
    }
    with open(output_dir / "summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    with open(output_dir / "per_task.json", "w") as f:
        json.dump(per_task, f, indent=2)

    print(f"\nWrote {output_dir / 'summary.json'}")


if __name__ == "__main__":
    main()
