"""Property gap analysis: audit current properties, analyze failures, build taxonomy."""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reasoning_project.reasoning_engine import (
    BOOLEAN_PROPERTIES,
    DERIVED_PREDICATES,
    GridDomainAdapter,
    StructuralReasoner,
    _all_property_names,
    _classify_kept_removed,
    _get_property_value,
)


def load_arc_tasks(root: str):
    tasks = []
    challenges_path = os.path.join(root, "arc-agi_training_challenges.json")
    solutions_path = os.path.join(root, "arc-agi_training_solutions.json")
    if not os.path.isfile(challenges_path):
        return tasks
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
        test_outputs = []
        if task_id in solutions:
            test_outputs = [np.array(o) for o in solutions[task_id]]
        elif data["test"] and "output" in data["test"][0]:
            test_outputs = [np.array(ex["output"]) for ex in data["test"]]
        test_inputs = [np.array(ex["input"]) for ex in data["test"]]
        if test_outputs:
            tasks.append({
                "task_id": task_id,
                "train_pairs": train_pairs,
                "test_inputs": test_inputs,
                "test_outputs": test_outputs,
            })
    return tasks


def analyze_property_failures(tasks, out_dir, max_analyze=200):
    """For tasks where no existing property discriminates, analyze why."""
    adapter = GridDomainAdapter()
    all_props = _all_property_names()

    results = []
    for task in tasks[:max_analyze]:
        tid = task["task_id"]
        train_pairs = task["train_pairs"]

        best_prop = None
        best_score = 0.0
        n_objects_list = []
        colors_set = set()

        for inp, out in train_pairs:
            objects = adapter.extract_objects(inp)
            n_objects_list.append(len(objects))
            for o in objects:
                colors_set.add(o["primary_color"])

        for prop in all_props:
            n_consistent = 0
            n_classifiable = 0
            for inp, out in train_pairs:
                objects = adapter.extract_objects(inp)
                cls = _classify_kept_removed(objects, inp, out)
                if cls is None:
                    continue
                n_classifiable += 1
                kept, removed = cls
                kept_vals = [_get_property_value(objects[k], prop) for k in kept]
                removed_vals = [_get_property_value(objects[r], prop) for r in removed]
                if kept_vals and removed_vals:
                    if all(kept_vals) and not any(removed_vals):
                        n_consistent += 1
                    elif not any(kept_vals) and all(removed_vals):
                        n_consistent += 1
            if n_classifiable > 0:
                score = n_consistent / n_classifiable
                if score > best_score:
                    best_score = score
                    best_prop = prop

        results.append({
            "task_id": tid,
            "n_objects_mean": np.mean(n_objects_list) if n_objects_list else 0,
            "n_colors": len(colors_set),
            "colors": sorted(colors_set),
            "best_property": best_prop or "none",
            "best_score": best_score,
            "same_size": all(
                inp.shape == out.shape for inp, out in train_pairs
            ),
        })

    with open(os.path.join(out_dir, "property_failure_analysis.csv"), "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "task_id", "n_objects_mean", "n_colors", "colors",
            "best_property", "best_score", "same_size",
        ])
        writer.writeheader()
        for r in results:
            r["colors"] = str(r["colors"])
            writer.writerow(r)

    return results


def write_current_language_md(out_dir):
    lines = ["# Current Property Language\n"]
    lines.append(f"Total properties: {len(_all_property_names())}\n")
    lines.append(f"## Base Boolean Properties ({len(BOOLEAN_PROPERTIES)})\n")
    for p in BOOLEAN_PROPERTIES:
        lines.append(f"- `{p}`")
    lines.append(f"\n## Derived Predicates ({len(DERIVED_PREDICATES)})\n")
    for name, _ in DERIVED_PREDICATES:
        lines.append(f"- `{name}`")
    with open(os.path.join(out_dir, "current_property_language.md"), "w") as f:
        f.write("\n".join(lines))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--arc-root", default="data/arc")
    parser.add_argument("--output-dir", default="outputs/property_gap_analysis")
    parser.add_argument("--max-analyze", type=int, default=200)
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    write_current_language_md(args.output_dir)

    tasks = load_arc_tasks(args.arc_root)
    print(f"Loaded {len(tasks)} ARC tasks", flush=True)

    # Load oracle diagnoses to identify property_language_failure tasks
    diag_path = "outputs/oracle_candidate_analysis/task_diagnoses.csv"
    pf_task_ids = set()
    if os.path.isfile(diag_path):
        with open(diag_path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("category") == "property_language_failure":
                    pf_task_ids.add(row["task_id"])
        print(f"Found {len(pf_task_ids)} property_language_failure tasks", flush=True)

    pf_tasks = [t for t in tasks if t["task_id"] in pf_task_ids]
    if not pf_tasks:
        pf_tasks = tasks
        print("No oracle diagnoses found, analyzing all tasks", flush=True)

    print(f"Analyzing {min(len(pf_tasks), args.max_analyze)} tasks...", flush=True)
    results = analyze_property_failures(pf_tasks, args.output_dir, args.max_analyze)

    n_no_disc = sum(1 for r in results if r["best_score"] == 0)
    n_partial = sum(1 for r in results if 0 < r["best_score"] < 1.0)
    print(f"\nResults:")
    print(f"  No discrimination at all: {n_no_disc}")
    print(f"  Partial discrimination: {n_partial}")
    print(f"  Perfect (should be solved): {sum(1 for r in results if r['best_score'] == 1.0)}")
    print(f"\nWrote to {args.output_dir}/", flush=True)


if __name__ == "__main__":
    main()
