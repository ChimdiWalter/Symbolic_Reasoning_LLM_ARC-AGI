"""Oracle Candidate Analysis: generation vs selection bottleneck.

For every task, determines whether:
1. Any solver generated the correct answer (oracle reachable)
2. The portfolio selected the correct answer (selection success)
3. If not selected, where in the ranking the correct answer sits

Categories:
  - generation_failure: no solver generated the correct output
  - selection_failure: correct output was generated but not selected
  - perception_failure: object extraction failed
  - property_language_failure: no discriminative property found
  - timeout_failure: solver timed out before finding answer
  - solved: correct answer was generated and selected
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from collections import Counter

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reasoning_project.reasoning_engine import (
    GridDomainAdapter,
    StructuralReasoner,
    ReasoningMemory,
    solve_task_reasoning,
)
from reasoning_project.portfolio import (
    PortfolioSolver,
    compute_task_features,
    heuristic_route,
)


def load_arc_tasks(root: str) -> List[Dict[str, Any]]:
    tasks = []

    challenges_path = os.path.join(root, "arc-agi_training_challenges.json")
    solutions_path = os.path.join(root, "arc-agi_training_solutions.json")

    if os.path.isfile(challenges_path):
        with open(challenges_path) as f:
            challenges = json.load(f)
        solutions = {}
        if os.path.isfile(solutions_path):
            with open(solutions_path) as f:
                solutions = json.load(f)

        for task_id in sorted(challenges.keys()):
            data = challenges[task_id]
            train_pairs = [
                (np.array(ex["input"]), np.array(ex["output"]))
                for ex in data["train"]
            ]
            test_inputs = [np.array(ex["input"]) for ex in data["test"]]
            test_outputs = []
            if task_id in solutions:
                test_outputs = [np.array(o) for o in solutions[task_id]]
            elif data["test"] and "output" in data["test"][0]:
                test_outputs = [np.array(ex["output"]) for ex in data["test"]]

            if test_outputs:
                tasks.append({
                    "task_id": task_id,
                    "train_pairs": train_pairs,
                    "test_inputs": test_inputs,
                    "test_outputs": test_outputs,
                })
        return tasks

    training_dir = os.path.join(root, "training")
    if not os.path.isdir(training_dir):
        training_dir = root
    for fn in sorted(os.listdir(training_dir)):
        if not fn.endswith(".json"):
            continue
        with open(os.path.join(training_dir, fn)) as f:
            data = json.load(f)
        task_id = fn.replace(".json", "")
        train_pairs = [
            (np.array(ex["input"]), np.array(ex["output"]))
            for ex in data["train"]
        ]
        test_pairs = [
            (np.array(ex["input"]), np.array(ex["output"]))
            for ex in data["test"]
        ]
        tasks.append({
            "task_id": task_id,
            "train_pairs": train_pairs,
            "test_inputs": [t[0] for t in test_pairs],
            "test_outputs": [t[1] for t in test_pairs],
        })
    return tasks


def build_solvers() -> Dict[str, Any]:
    """Build the solver dict used by PortfolioSolver."""
    from reasoning_project.local_rules import solve_task_local_rules
    from reasoning_project.color_solver import solve_task_color
    from reasoning_project.separator_decompose import solve_task_separator_decompose
    from reasoning_project.crop_extract import solve_task_crop_extract
    from reasoning_project.object_graph import solve_task_object_graph
    from reasoning_project.abstract_programs import solve_task_abstract_programs
    from reasoning_project.fill_solver import solve_task_fill
    from reasoning_project.relation_solver import solve_task_relation

    return {
        "local_rule": solve_task_local_rules,
        "color_solver": solve_task_color,
        "separator_decompose": solve_task_separator_decompose,
        "crop_extract": solve_task_crop_extract,
        "object_graph": solve_task_object_graph,
        "abstract_program": solve_task_abstract_programs,
        "fill_solver": solve_task_fill,
        "rule_induction": solve_task_reasoning,
        "relation_solver": solve_task_relation,
    }


def analyze_task(
    task: Dict,
    solvers: Dict[str, Any],
) -> Dict[str, Any]:
    """Analyze one task: run all solvers and classify the bottleneck."""
    train_pairs = task["train_pairs"]
    test_inputs = task["test_inputs"]
    test_outputs = task["test_outputs"]

    all_candidates = []
    correct_candidates = []
    errors = {}

    for solver_name, solver_fn in solvers.items():
        try:
            result = solver_fn(train_pairs, test_inputs)
        except Exception as e:
            errors[solver_name] = str(e)
            continue

        if result is None:
            continue

        predictions, metadata = result
        if predictions is None:
            continue

        is_correct = all(
            np.array_equal(p, e)
            for p, e in zip(predictions, test_outputs)
        )
        entry = {
            "solver": solver_name,
            "correct": is_correct,
            "metadata": metadata if isinstance(metadata, dict) else {"info": str(metadata)},
        }
        all_candidates.append(entry)
        if is_correct:
            correct_candidates.append(entry)

    # Run portfolio selection
    portfolio = PortfolioSolver(solvers=solvers, mode="collect_all")
    portfolio_result = portfolio.solve(
        task["task_id"], train_pairs, test_inputs, test_outputs,
    )

    portfolio_correct = portfolio_result.solved

    # Classify bottleneck
    if portfolio_correct:
        category = "solved"
    elif correct_candidates:
        rank = next(
            (i for i, c in enumerate(all_candidates) if c["correct"]),
            len(all_candidates),
        )
        category = "selection_failure"
    elif all_candidates:
        category = "generation_failure_with_proposals"
    else:
        adapter = GridDomainAdapter()
        inp0 = train_pairs[0][0]
        objects = adapter.extract_objects(inp0)
        if len(objects) < 2:
            category = "perception_failure"
        else:
            re_result = solve_task_reasoning(train_pairs, test_inputs)
            if re_result is None:
                category = "property_language_failure"
            else:
                category = "generation_failure"

    return {
        "task_id": task["task_id"],
        "category": category,
        "n_candidates": len(all_candidates),
        "n_correct_candidates": len(correct_candidates),
        "correct_solvers": [c["solver"] for c in correct_candidates],
        "portfolio_selected": portfolio_result.solver_used,
        "portfolio_correct": portfolio_correct,
        "errors": errors,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--arc-root", default="data/arc")
    parser.add_argument("--output-dir", default="outputs/oracle_candidate_analysis")
    parser.add_argument("--max-tasks", type=int, default=0)
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    tasks = load_arc_tasks(args.arc_root)
    if args.max_tasks > 0:
        tasks = tasks[:args.max_tasks]

    print(f"Loaded {len(tasks)} ARC tasks")
    solvers = build_solvers()
    print(f"Built {len(solvers)} solvers")

    results = []
    categories = Counter()
    t0 = time.perf_counter()

    for i, task in enumerate(tasks):
        r = analyze_task(task, solvers)
        results.append(r)
        categories[r["category"]] += 1

        if (i + 1) % 50 == 0:
            elapsed = time.perf_counter() - t0
            print(f"  {i+1}/{len(tasks)} ({elapsed:.0f}s) "
                  f"solved={categories['solved']} "
                  f"sel_fail={categories['selection_failure']} "
                  f"gen_fail={categories.get('generation_failure', 0) + categories.get('generation_failure_with_proposals', 0)}")

    elapsed = time.perf_counter() - t0

    print(f"\n{'='*60}")
    print("ORACLE CANDIDATE ANALYSIS")
    print(f"{'='*60}")
    for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
        print(f"  {cat:<40} {count:>5} ({count/len(tasks)*100:.1f}%)")
    print(f"  {'TOTAL':<40} {len(tasks):>5}")
    print(f"\n  Elapsed: {elapsed:.0f}s")

    # Selection failures: which solver had the correct answer?
    sel_failures = [r for r in results if r["category"] == "selection_failure"]
    if sel_failures:
        solver_could_have = Counter()
        for r in sel_failures:
            for s in r["correct_solvers"]:
                solver_could_have[s] += 1
        print(f"\n  Selection failures: correct candidate from:")
        for s, c in solver_could_have.most_common():
            print(f"    {s}: {c}")

    # Write outputs
    with open(os.path.join(args.output_dir, "task_diagnoses.csv"), "w") as f:
        f.write("task_id,category,n_candidates,n_correct,correct_solvers,portfolio_selected\n")
        for r in results:
            f.write(f"{r['task_id']},{r['category']},{r['n_candidates']},"
                    f"{r['n_correct_candidates']},{'|'.join(r['correct_solvers'])},"
                    f"{r['portfolio_selected']}\n")

    summary = {
        "n_tasks": len(tasks),
        "categories": dict(categories),
        "elapsed_s": elapsed,
        "selection_failure_details": [
            {"task_id": r["task_id"], "correct_solvers": r["correct_solvers"]}
            for r in sel_failures
        ],
    }
    with open(os.path.join(args.output_dir, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2, default=str)

    print(f"\nWrote results to {args.output_dir}/")


if __name__ == "__main__":
    main()
