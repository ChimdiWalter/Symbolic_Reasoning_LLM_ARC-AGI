#!/usr/bin/env python3
"""Phase E: Microcycle tests for many-to-few grouping operators."""
import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reasoning_project.many_to_few_grouping import solve_many_to_few, falsify_grouping


def make_color_collapse_task():
    """Objects of same color collapse into one block."""
    inp = [[0,0,0,0,0],[0,1,0,1,0],[0,0,0,0,0],[0,1,0,0,0],[0,0,0,0,0]]
    out = [[0,0,0,0,0],[0,1,1,1,0],[0,0,0,0,0],[0,1,0,0,0],[0,0,0,0,0]]
    return {"train": [{"input": inp, "output": out}], "test": [{"input": inp, "output": out}]}


def make_proximity_group_task():
    """Fragments grouped by proximity form one object."""
    inp = [[0,0,0,0,0,0],[0,2,2,0,0,0],[0,2,0,0,0,0],[0,0,0,0,3,0],[0,0,0,3,3,0],[0,0,0,0,0,0]]
    out = [[0,0,0,0,0,0],[0,2,2,0,0,0],[0,2,0,0,0,0],[0,0,0,0,3,0],[0,0,0,3,3,0],[0,0,0,0,0,0]]
    return {"train": [{"input": inp, "output": out}], "test": [{"input": inp, "output": out}]}


def make_row_group_task():
    """Objects grouped by row map to one output row."""
    inp = [[0,0,0,0],[1,0,1,0],[0,0,0,0],[2,0,2,0]]
    out = [[0,0,0,0],[1,1,1,0],[0,0,0,0],[2,2,2,0]]
    return {"train": [{"input": inp, "output": out}], "test": [{"input": inp, "output": out}]}


def make_frame_group_task():
    """Objects grouped by enclosing frame."""
    inp = [[3,3,3,0,0],[3,1,3,0,0],[3,3,3,0,0],[0,0,0,4,4],[0,0,0,4,4]]
    out = [[3,3,3,0,0],[3,1,3,0,0],[3,3,3,0,0],[0,0,0,4,4],[0,0,0,4,4]]
    return {"train": [{"input": inp, "output": out}], "test": [{"input": inp, "output": out}]}


def make_ambiguous_task():
    """Ambiguous grouping: should reject or return None."""
    inp = [[1,2,3],[4,5,6],[7,8,9]]
    out = [[0,0,0],[0,0,0],[0,0,0]]
    return {"train": [{"input": inp, "output": out}], "test": [{"input": inp, "output": out}]}


MICROCYCLE_TASKS = [
    ("color_collapse", make_color_collapse_task),
    ("proximity_group", make_proximity_group_task),
    ("row_group", make_row_group_task),
    ("frame_group", make_frame_group_task),
    ("ambiguous_reject", make_ambiguous_task),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="outputs/deep_project_completion/many_to_few_grouping")
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=== Phase E: Many-to-Few Grouping Microcycle ===")
    results = []

    for name, make_fn in MICROCYCLE_TASKS:
        task = make_fn()
        train_pairs = [(ex["input"], ex["output"]) for ex in task["train"]]
        result = solve_many_to_few(train_pairs)
        solved = result is not None and result.train_fit == len(train_pairs)
        is_ambiguous = name == "ambiguous_reject"
        correct = (not solved) if is_ambiguous else solved

        entry = {
            "task": name,
            "solved": solved,
            "expected_reject": is_ambiguous,
            "correct": correct,
            "family": result.rule.family.name if result else None,
            "loo": result.loo_passed if result else False,
        }
        results.append(entry)
        print(f"  {name}: {'CORRECT' if correct else 'WRONG'} (solved={solved})")

    with open(output_dir / "microcycle_results.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        for r in results:
            writer.writerow(r)

    passed = sum(1 for r in results if r["correct"])
    lines = [
        "# Many-to-Few Grouping Microcycle Summary",
        f"\nGenerated: {datetime.now().isoformat()}",
        f"\n## Results: {passed}/{len(results)} correct",
        "",
        "| Task | Solved | Correct | Family | LOO |",
        "|------|--------|---------|--------|-----|",
    ]
    for r in results:
        lines.append(f"| {r['task']} | {r['solved']} | {r['correct']} | {r['family']} | {r['loo']} |")

    with open(output_dir / "microcycle_summary.md", "w") as f:
        f.write("\n".join(lines) + "\n")

    with open(output_dir / "status.json", "w") as f:
        json.dump({"status": "completed", "microcycle_passed": passed, "microcycle_total": len(results)}, f)

    print(f"\n{passed}/{len(results)} microcycle tests correct")


if __name__ == "__main__":
    main()
