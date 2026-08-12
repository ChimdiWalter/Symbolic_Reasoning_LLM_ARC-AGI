#!/usr/bin/env python3
"""Phase G: Microcycle tests for position-within-object recolor operators."""
import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reasoning_project.position_within_object_recolor import solve_position_recolor


def make_boundary_recolor():
    inp = [[0,0,0,0,0],[0,1,1,1,0],[0,1,1,1,0],[0,1,1,1,0],[0,0,0,0,0]]
    out = [[0,0,0,0,0],[0,2,2,2,0],[0,2,1,2,0],[0,2,2,2,0],[0,0,0,0,0]]
    return [{"input": inp, "output": out}]


def make_interior_recolor():
    inp = [[0,0,0,0,0],[0,3,3,3,0],[0,3,3,3,0],[0,3,3,3,0],[0,0,0,0,0]]
    out = [[0,0,0,0,0],[0,3,3,3,0],[0,3,5,3,0],[0,3,3,3,0],[0,0,0,0,0]]
    return [{"input": inp, "output": out}]


def make_endpoint_recolor():
    inp = [[0,0,0,0,0],[0,0,4,0,0],[0,0,4,0,0],[0,0,4,0,0],[0,0,0,0,0]]
    out = [[0,0,0,0,0],[0,0,6,0,0],[0,0,4,0,0],[0,0,6,0,0],[0,0,0,0,0]]
    return [{"input": inp, "output": out}]


def make_corner_recolor():
    inp = [[0,0,0,0,0],[0,7,7,7,0],[0,7,7,7,0],[0,7,7,7,0],[0,0,0,0,0]]
    out = [[0,0,0,0,0],[0,8,7,8,0],[0,7,7,7,0],[0,8,7,8,0],[0,0,0,0,0]]
    return [{"input": inp, "output": out}]


def make_contact_recolor():
    inp = [[0,0,0,0,0],[0,1,1,0,0],[0,1,1,2,0],[0,0,0,2,0],[0,0,0,0,0]]
    out = [[0,0,0,0,0],[0,1,1,0,0],[0,1,9,2,0],[0,0,0,2,0],[0,0,0,0,0]]
    return [{"input": inp, "output": out}]


def make_ambiguous_recolor():
    inp = [[1,2,3],[4,5,6],[7,8,9]]
    out = [[9,8,7],[6,5,4],[3,2,1]]
    return [{"input": inp, "output": out}]


TASKS = [
    ("boundary_recolor", make_boundary_recolor, False),
    ("interior_recolor", make_interior_recolor, False),
    ("endpoint_recolor", make_endpoint_recolor, False),
    ("corner_recolor", make_corner_recolor, False),
    ("contact_recolor", make_contact_recolor, False),
    ("ambiguous_reject", make_ambiguous_recolor, True),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="outputs/deep_project_completion/position_within_object_recolor")
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=== Phase G: Position-Within-Object Recolor Microcycle ===")
    results = []

    for name, make_fn, expect_reject in TASKS:
        examples = make_fn()
        train_pairs = [(ex["input"], ex["output"]) for ex in examples]
        result = solve_position_recolor(train_pairs)
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
        "# Position-Within-Object Recolor Microcycle Summary",
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
