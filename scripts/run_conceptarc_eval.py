#!/usr/bin/env python3
"""Phase C3: ConceptARC evaluation — run reasoning pipeline on 160 ConceptARC tasks."""
import argparse
import csv
import json
import numpy as np
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reasoning_project.arc_adapter import load_conceptarc_tasks
from reasoning_project.reasoning_engine import (
    StructuralReasoner, GridDomainAdapter, solve_task_reasoning,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="outputs/deep_project_completion/conceptarc_eval")
    parser.add_argument("--conceptarc-root", default="data/conceptarc")
    parser.add_argument("--max-tasks", type=int, default=200)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=== Phase C3: ConceptARC Evaluation ===")

    tasks = load_conceptarc_tasks(args.conceptarc_root, max_tasks=args.max_tasks)
    print(f"Loaded {len(tasks)} ConceptARC tasks")

    adapter = GridDomainAdapter()
    reasoner = StructuralReasoner(adapter)

    results = []
    solved_structural = 0
    solved_standalone = 0
    total = 0

    for i, task in enumerate(tasks):
        tid = task.task_id
        t0 = time.time()
        total += 1

        train_pairs_np = [(ex.input_grid, ex.output_grid) for ex in task.train]
        test_inputs_np = [ex.input_grid for ex in task.test]
        test_outputs_np = [ex.output_grid for ex in task.test if ex.output_grid is not None]

        solved = False
        method = "none"

        try:
            result = reasoner.solve(train_pairs_np, test_inputs_np)
            if result is not None:
                preds, meta = result
                if preds and test_outputs_np:
                    for pred, expected in zip(preds, test_outputs_np):
                        if np.array_equal(pred, expected):
                            solved = True
                            method = "structural_reasoner"
                            solved_structural += 1
                            break
        except Exception:
            pass

        if not solved:
            try:
                standalone = solve_task_reasoning(train_pairs_np, test_inputs_np)
                if standalone is not None:
                    preds, meta = standalone
                    if preds and test_outputs_np:
                        for pred, expected in zip(preds, test_outputs_np):
                            if np.array_equal(pred, expected):
                                solved = True
                                method = "standalone_reasoning"
                                solved_standalone += 1
                                break
            except Exception:
                pass

        rt = time.time() - t0
        concept_group = task.metadata.get("concept_group", "unknown")
        results.append({
            "task_id": tid,
            "concept_group": concept_group,
            "solved": solved,
            "method": method,
            "runtime": round(rt, 2),
        })

        if (i + 1) % 20 == 0:
            print(f"  [{i+1}/{len(tasks)}] solved={solved_structural + solved_standalone}")

    with open(output_dir / "conceptarc_results.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()) if results else [])
        writer.writeheader()
        for r in results:
            writer.writerow(r)

    by_group = {}
    for r in results:
        g = r["concept_group"]
        by_group.setdefault(g, {"total": 0, "solved": 0})
        by_group[g]["total"] += 1
        if r["solved"]:
            by_group[g]["solved"] += 1

    total_solved = solved_structural + solved_standalone
    lines = [
        "# ConceptARC Evaluation Summary",
        f"\nGenerated: {datetime.now().isoformat()}",
        f"\n## Overall: {total_solved}/{total} solved ({total_solved/max(total,1)*100:.1f}%)",
        f"- Structural reasoner: {solved_structural}",
        f"- Standalone reasoning: {solved_standalone}",
        "",
        "## By Concept Group",
        "",
        "| Group | Solved | Total | Rate |",
        "|-------|--------|-------|------|",
    ]
    for g in sorted(by_group.keys()):
        s, t = by_group[g]["solved"], by_group[g]["total"]
        lines.append(f"| {g} | {s} | {t} | {s/max(t,1)*100:.0f}% |")

    with open(output_dir / "conceptarc_summary.md", "w") as f:
        f.write("\n".join(lines) + "\n")

    with open(output_dir / "status.json", "w") as f:
        json.dump({
            "status": "completed",
            "total": total,
            "solved": total_solved,
            "structural": solved_structural,
            "standalone": solved_standalone,
        }, f)

    print(f"\nResults: {total_solved}/{total} solved (structural={solved_structural}, standalone={solved_standalone})")


if __name__ == "__main__":
    main()
