#!/usr/bin/env python3.11
"""False-positive audit: run promoted operators on the rejected candidate pool.

For each promoted operator, run it on the tasks that were rejected by that
same pipeline run. Verify that no false positives are produced.

Outputs:
  outputs/operator_reasoning_phase/final_false_positive_audit.md
"""
from __future__ import annotations

import csv
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reasoning_project.trace_operator_invention import TraceDrivenOperatorInventor
from reasoning_project.events import ReasoningEventLog


def load_arc_data():
    with open("data/arc/arc-agi_training_challenges.json") as f:
        challenges = json.load(f)
    with open("data/arc/arc-agi_training_solutions.json") as f:
        solutions = json.load(f)
    return challenges, solutions


def get_rejected_tasks(csv_path: str) -> List[Dict]:
    """Load rejected task IDs and traces from a results CSV."""
    tasks = []
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            promoted = row.get("promoted", "False")
            if promoted in ("True", "true", True):
                continue
            tasks.append({
                "task_id": row.get("task_id", ""),
                "selector": row.get("selector", row.get("best_property", "")),
            })
    return tasks


def main():
    os.chdir(Path(__file__).resolve().parent.parent)

    challenges, solutions = load_arc_data()

    # Gather rejected task pools from both CTP and color-transfer runs
    ctp_csv = "outputs/operator_reasoning_phase/copy_to_position_real/results.csv"
    ct_csv = "outputs/operator_reasoning_phase/color_transfer/real/results.csv"
    gap_csv = "outputs/operator_gap_analysis_v3/operator_gap_trace.csv"

    rejected_pool = set()

    for csv_path in [ctp_csv, ct_csv]:
        if Path(csv_path).exists():
            tasks = get_rejected_tasks(csv_path)
            for t in tasks:
                rejected_pool.add(t["task_id"])

    if Path(gap_csv).exists():
        with open(gap_csv) as f:
            reader = csv.DictReader(f)
            for row in reader:
                rejected_pool.add(row["task_id"])

    # Remove the 4 promoted tasks
    promoted_ids = {"d89b689b", "e9ac8c9e", "a48eeaf7", "2a5f8217"}
    rejected_pool -= promoted_ids

    print(f"Rejected candidate pool: {len(rejected_pool)} tasks")

    results = []
    t0 = time.time()
    fp_count = 0
    prediction_count = 0

    for tid in sorted(rejected_pool):
        if tid not in challenges:
            continue

        task = challenges[tid]
        train_pairs = [
            (np.array(p["input"], dtype=int), np.array(p["output"], dtype=int))
            for p in task["train"]
        ]
        test_inputs = [np.array(p["input"], dtype=int) for p in task["test"]]

        sol = solutions.get(tid, [])
        if not sol:
            continue
        test_outputs = [np.array(s) for s in sol]

        # Try to find best property from gap trace
        best_property = ""
        if Path(gap_csv).exists():
            with open(gap_csv) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row["task_id"] == tid:
                        best_property = row.get("best_property", "")
                        break

        if not best_property:
            continue

        trace = {
            "best_property": best_property,
            "needed_operator_family": "copy_to_position",
        }

        event_log = ReasoningEventLog()
        inventor = TraceDrivenOperatorInventor(event_log=event_log)
        result = inventor.run_full_pipeline(
            task_id=tid,
            train_pairs=train_pairs,
            test_inputs=test_inputs,
            trace=trace,
            test_outputs=test_outputs,
        )

        promoted = result.get("promoted", False)
        predictions = result.get("predictions")
        has_prediction = predictions is not None

        if has_prediction:
            prediction_count += 1

        is_correct = False
        if promoted and has_prediction:
            is_correct = all(
                np.array_equal(predictions[i], test_outputs[i])
                for i in range(min(len(predictions), len(test_outputs)))
                if predictions[i] is not None
            )
            if not is_correct:
                fp_count += 1

        results.append({
            "task_id": tid,
            "promoted": promoted,
            "has_prediction": has_prediction,
            "correct": is_correct if promoted else None,
            "false_positive": promoted and not is_correct,
            "rejection": result.get("rejection_reason", ""),
        })

        if promoted:
            status = "CORRECT" if is_correct else "FALSE POSITIVE"
            print(f"  {tid}: PROMOTED — {status}")

    elapsed = time.time() - t0

    n_total = len(results)
    n_promoted = sum(1 for r in results if r["promoted"])
    n_correct = sum(1 for r in results if r["correct"] is True)
    n_rejected = sum(1 for r in results if not r["promoted"])
    n_fp = sum(1 for r in results if r["false_positive"])

    out_path = Path("outputs/operator_reasoning_phase/final_false_positive_audit.md")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, "w") as f:
        f.write("# False-Positive Audit\n\n")
        f.write(f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Elapsed: {elapsed:.1f}s\n\n")
        f.write("## Summary\n\n")
        f.write(f"| Metric | Value |\n|--------|-------|\n")
        f.write(f"| Tasks attempted | {n_total} |\n")
        f.write(f"| Predictions emitted | {prediction_count} |\n")
        f.write(f"| Promoted | {n_promoted} |\n")
        f.write(f"| Correct promotions | {n_correct} |\n")
        f.write(f"| Rejected | {n_rejected} |\n")
        f.write(f"| **False positives** | **{n_fp}** |\n")

        if n_promoted > 0:
            f.write(f"\n## Promoted Tasks (unexpected)\n\n")
            for r in results:
                if r["promoted"]:
                    status = "correct" if r["correct"] else "FALSE POSITIVE"
                    f.write(f"- {r['task_id']}: {status}\n")

        f.write(f"\n## Conclusion\n\n")
        if n_fp == 0:
            f.write(f"Zero false positives across {n_total} rejected candidate tasks. "
                    f"The trace-driven operator invention pipeline correctly rejects "
                    f"all tasks outside its operator expressiveness boundary.\n")
        else:
            f.write(f"WARNING: {n_fp} false positive(s) detected. "
                    f"These represent operators that produced incorrect predictions "
                    f"but passed validation.\n")

    print(f"\n{'=' * 50}")
    print(f"FALSE-POSITIVE AUDIT")
    print(f"Tasks: {n_total}, Promoted: {n_promoted}, FP: {n_fp}")
    print(f"Output: {out_path}")


if __name__ == "__main__":
    main()
