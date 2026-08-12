#!/usr/bin/env python3
"""Phase F: Microcycle tests for shape completion operators."""
import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reasoning_project.shape_completion import solve_shape_completion


def make_line_extension_task():
    inp = [[0,0,0,0,0],[0,0,0,0,0],[1,1,1,0,0],[0,0,0,0,0],[0,0,0,0,0]]
    out = [[0,0,0,0,0],[0,0,0,0,0],[1,1,1,1,1],[0,0,0,0,0],[0,0,0,0,0]]
    return [{"input": inp, "output": out}]


def make_symmetry_task():
    inp = [[0,0,0,0,0],[0,2,2,0,0],[0,2,0,0,0],[0,0,0,0,0],[0,0,0,0,0]]
    out = [[0,0,0,0,0],[0,2,2,0,0],[0,2,2,0,0],[0,0,0,0,0],[0,0,0,0,0]]
    return [{"input": inp, "output": out}]


def make_hole_fill_task():
    inp = [[0,0,0,0,0],[0,3,3,3,0],[0,3,0,3,0],[0,3,3,3,0],[0,0,0,0,0]]
    out = [[0,0,0,0,0],[0,3,3,3,0],[0,3,3,3,0],[0,3,3,3,0],[0,0,0,0,0]]
    return [{"input": inp, "output": out}]


def make_boundary_task():
    inp = [[0,0,0,0,0],[0,4,4,0,0],[0,4,4,4,0],[0,0,4,4,0],[0,0,0,0,0]]
    out = [[0,0,0,0,0],[0,4,4,4,0],[0,4,4,4,0],[0,4,4,4,0],[0,0,0,0,0]]
    return [{"input": inp, "output": out}]


def make_ambiguous_task():
    inp = [[1,0,2],[0,3,0],[4,0,5]]
    out = [[9,9,9],[9,9,9],[9,9,9]]
    return [{"input": inp, "output": out}]


TASKS = [
    ("line_extension", make_line_extension_task, False),
    ("symmetry_completion", make_symmetry_task, False),
    ("hole_completion", make_hole_fill_task, False),
    ("boundary_completion", make_boundary_task, False),
    ("ambiguous_reject", make_ambiguous_task, True),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="outputs/deep_project_completion/shape_completion")
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=== Phase F: Shape Completion Microcycle ===")
    results = []

    for name, make_fn, expect_reject in TASKS:
        examples = make_fn()
        train_pairs = [(ex["input"], ex["output"]) for ex in examples]
        result = solve_shape_completion(train_pairs)
        solved = result is not None and result.train_fit == len(train_pairs)
        correct = (not solved) if expect_reject else solved

        entry = {
            "task": name,
            "solved": solved,
            "expected_reject": expect_reject,
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
        "# Shape Completion Microcycle Summary",
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
        json.dump({"status": "completed", "passed": passed, "total": len(results)}, f)

    print(f"\n{passed}/{len(results)} correct")


if __name__ == "__main__":
    main()
