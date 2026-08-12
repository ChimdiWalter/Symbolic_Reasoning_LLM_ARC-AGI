#!/usr/bin/env python3.11
"""Analyze solver overlap and generate UpSet-style data for visualization.

Reads per_task.json from portfolio output to determine which solvers
proposed correct candidates for each task, regardless of which solver
won the final selection.
"""
import json
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def load_per_task(path):
    with open(path) as f:
        return json.load(f)


def compute_upset_data(per_task):
    """Compute UpSet-style intersection sizes."""
    winning_solvers = {}
    for entry in per_task:
        if not entry.get("solved", False):
            continue
        task_id = entry["task_id"]
        winning_solver = entry.get("solver_used", "unknown")
        winning_solvers[task_id] = winning_solver

    solver_names = sorted(set(winning_solvers.values()))

    solver_to_tasks = defaultdict(set)
    for task_id, solver in winning_solvers.items():
        solver_to_tasks[solver].add(task_id)

    print("=" * 70)
    print("SOLVER OVERLAP ANALYSIS (winning solver per task)")
    print("=" * 70)
    print()
    print(f"Total solved: {len(winning_solvers)}")
    print()

    print("=== Per-Solver Task Counts ===\n")
    for solver in sorted(solver_to_tasks, key=lambda s: -len(solver_to_tasks[s])):
        tasks = solver_to_tasks[solver]
        print(f"  {solver:<25} {len(tasks):>4} tasks")
    print()

    print("=== Pairwise Overlap Matrix ===\n")
    header = f"{'':>25}"
    for s in solver_names:
        header += f" {s[:6]:>6}"
    print(header)

    for s1 in solver_names:
        row = f"{s1:>25}"
        for s2 in solver_names:
            overlap = len(solver_to_tasks[s1] & solver_to_tasks[s2])
            row += f" {overlap:>6}"
        print(row)
    print()

    print("=== Unique Contributions (tasks solved by ONLY this family) ===\n")
    all_tasks_by_solver = {}
    for solver in solver_names:
        all_tasks_by_solver[solver] = solver_to_tasks[solver]

    for solver in sorted(solver_names, key=lambda s: -len(all_tasks_by_solver[s])):
        others = set()
        for s2 in solver_names:
            if s2 != solver:
                others |= all_tasks_by_solver[s2]
        unique = all_tasks_by_solver[solver] - others
        print(f"  {solver:<25} {len(unique):>4} unique  (of {len(all_tasks_by_solver[solver]):>4} total)")
        if unique:
            for tid in sorted(unique):
                print(f"    {tid}")
    print()

    return solver_to_tasks


def generate_upset_text(solver_to_tasks):
    """Generate text-based UpSet plot data."""
    solver_names = sorted(solver_to_tasks.keys(), key=lambda s: -len(solver_to_tasks[s]))

    all_solved = set()
    for tasks in solver_to_tasks.values():
        all_solved |= tasks

    print("=== UpSet-Style Intersection Sizes ===\n")
    intersection_counts = {}

    for r in range(1, len(solver_names) + 1):
        for combo in combinations(solver_names, r):
            tasks_in_all = set(all_solved)
            for solver in combo:
                tasks_in_all &= solver_to_tasks[solver]
            for solver in solver_names:
                if solver not in combo:
                    tasks_in_all -= solver_to_tasks[solver]
            if tasks_in_all:
                key = " ∩ ".join(combo)
                intersection_counts[key] = len(tasks_in_all)

    for key, count in sorted(intersection_counts.items(), key=lambda x: -x[1]):
        print(f"  {key:<50} {count:>4}")


def main():
    per_task_path = REPO / "outputs" / "portfolio_v10_full" / "per_task.json"
    if not per_task_path.exists():
        print(f"Not found: {per_task_path}")
        sys.exit(1)

    per_task = load_per_task(per_task_path)
    solver_to_tasks = compute_upset_data(per_task)
    generate_upset_text(solver_to_tasks)

    outdir = REPO / "outputs" / "baselines"
    outdir.mkdir(parents=True, exist_ok=True)

    export = {solver: sorted(tasks) for solver, tasks in solver_to_tasks.items()}
    with open(outdir / "solver_overlap.json", "w") as f:
        json.dump(export, f, indent=2)
    print(f"\nSaved overlap data to {outdir / 'solver_overlap.json'}")


if __name__ == "__main__":
    main()
