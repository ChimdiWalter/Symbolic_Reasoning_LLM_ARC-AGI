#!/usr/bin/env python3
"""Phase G: Run position-within-object recolor on real ARC tasks."""
import argparse
import csv
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reasoning_project.position_within_object_recolor import solve_position_recolor
from reasoning_project.arc_adapter import load_arc_tasks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="outputs/deep_project_completion/position_within_object_recolor")
    parser.add_argument("--arc-root", default="data/arc")
    parser.add_argument("--max-tasks", type=int, default=1000)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "certificates").mkdir(exist_ok=True)

    print("=== Phase G: Position-Within-Object Recolor on Real ARC ===")
    arc_tasks = load_arc_tasks(args.arc_root)
    task_list = arc_tasks[:args.max_tasks]
    print(f"Loaded {len(task_list)} tasks")

    results = []
    promoted = []
    rejected = []

    for i, task in enumerate(task_list):
        tid = task.task_id
        t0 = time.time()
        train_pairs = [(ex.input_grid.tolist(), ex.output_grid.tolist()) for ex in task.train]
        result = solve_position_recolor(train_pairs)
        rt = time.time() - t0
        entry = {
            "task_id": tid,
            "solved": result is not None and result.train_fit == len(train_pairs),
            "family": result.rule.family.name if result else None,
            "loo_passed": result.loo_passed if result else False,
            "train_fit": result.train_fit if result else 0,
            "runtime": round(rt, 2),
        }
        results.append(entry)
        if entry["solved"] and entry["loo_passed"]:
            promoted.append(entry)
        elif result is not None and not entry["loo_passed"]:
            rejected.append(entry)
        if (i + 1) % 100 == 0:
            print(f"  [{i+1}/{len(task_list)}] solved={sum(1 for r in results if r['solved'])}")

    with open(output_dir / "real_arc_results.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()) if results else [])
        writer.writeheader()
        for r in results:
            writer.writerow(r)
    with open(output_dir / "promoted_tasks.jsonl", "w") as f:
        for r in promoted:
            f.write(json.dumps(r) + "\n")
    with open(output_dir / "rejected_tasks.jsonl", "w") as f:
        for r in rejected:
            f.write(json.dumps(r) + "\n")

    print(f"\nResults: {sum(1 for r in results if r['solved'])}/{len(results)} solved, {len(promoted)} promoted, {len(rejected)} rejected")


if __name__ == "__main__":
    main()
