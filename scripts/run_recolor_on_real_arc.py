#!/usr/bin/env python3.11
"""Run recolor-in-place operator on real ARC tasks identified by gap analysis v3.

Loads the 12 tasks classified as needing recolor_in_place, runs the full
trace-driven operator invention pipeline, and reports promotions/rejections.
"""
from __future__ import annotations

import csv
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reasoning_project.trace_operator_invention import TraceDrivenOperatorInventor
from reasoning_project.events import ReasoningEventLog


def load_recolor_candidates(
    gap_csv: str,
) -> List[Dict[str, str]]:
    candidates = []
    with open(gap_csv) as f:
        reader = csv.reader(f)
        header = next(reader)
        for row in reader:
            if len(row) > 9 and "recolor_in_place" in row[9]:
                candidates.append({
                    "task_id": row[0],
                    "best_property": row[1],
                    "discrimination": row[2],
                })
    return candidates


def load_arc_task(task_id: str, arc_root: str) -> Dict[str, Any]:
    challenges_path = os.path.join(arc_root, "arc-agi_training_challenges.json")
    solutions_path = os.path.join(arc_root, "arc-agi_training_solutions.json")
    with open(challenges_path) as f:
        challenges = json.load(f)
    with open(solutions_path) as f:
        solutions = json.load(f)

    raw = challenges[task_id]
    train_pairs = [
        (np.array(ex["input"], dtype=int), np.array(ex["output"], dtype=int))
        for ex in raw["train"]
    ]
    test_inputs = [np.array(ex["input"], dtype=int) for ex in raw["test"]]
    test_outputs = None
    if task_id in solutions:
        test_outputs = [np.array(s, dtype=int) for s in solutions[task_id]]

    return {
        "train_pairs": train_pairs,
        "test_inputs": test_inputs,
        "test_outputs": test_outputs,
    }


def main():
    os.chdir(Path(__file__).resolve().parent.parent)

    gap_csv = "outputs/operator_gap_analysis_v3/operator_gap_trace.csv"
    arc_root = "data/arc"
    out_dir = Path("outputs/operator_reasoning_phase/recolor_real")
    out_dir.mkdir(parents=True, exist_ok=True)

    candidates = load_recolor_candidates(gap_csv)
    print(f"Loaded {len(candidates)} recolor candidates from gap analysis")

    results = []
    promotions = 0
    rejections = 0
    t0 = time.time()

    for cand in candidates:
        task_id = cand["task_id"]
        best_property = cand["best_property"]

        print(f"\n{'='*60}")
        print(f"Task: {task_id} | Selector: {best_property}")

        task_data = load_arc_task(task_id, arc_root)
        trace = {
            "best_property": best_property,
            "needed_operator_family": "recolor_in_place",
        }

        event_log = ReasoningEventLog()
        inventor = TraceDrivenOperatorInventor(event_log=event_log)

        result = inventor.run_full_pipeline(
            task_id=task_id,
            train_pairs=task_data["train_pairs"],
            test_inputs=task_data["test_inputs"],
            trace=trace,
            test_outputs=task_data["test_outputs"],
        )

        promoted = result.get("promoted", False)
        rejection = result.get("rejection_reason")
        op_id = result.get("operator_id", "")

        if promoted:
            promotions += 1
            family = "recolor_in_place" if "rcl_" in str(op_id) else "other"
            print(f"  PROMOTED via {family} (op_id={op_id})")

            cert = result.get("certificate")
            if cert:
                cert_path = out_dir / f"{task_id}_certificate.json"
                cert_path.write_text(json.dumps(cert, indent=2, default=str))
            cert_md = result.get("certificate_md")
            if cert_md:
                md_path = out_dir / f"{task_id}_certificate.md"
                md_path.write_text(cert_md)
        else:
            rejections += 1
            print(f"  REJECTED: {rejection}")

        results.append({
            "task_id": task_id,
            "selector": best_property,
            "promoted": promoted,
            "operator_id": op_id,
            "rejection_reason": rejection,
            "train_consistent": result.get("train_consistent", False),
            "loo_passed": result.get("loo_passed", False),
        })

    elapsed = time.time() - t0

    print(f"\n{'='*60}")
    print("REAL ARC RECOLOR RESULTS")
    print(f"{'='*60}")
    print(f"Tasks:      {len(candidates)}")
    print(f"Promotions: {promotions}")
    print(f"Rejections: {rejections}")
    print(f"Elapsed:    {elapsed:.1f}s")

    summary = {
        "total": len(candidates),
        "promotions": promotions,
        "rejections": rejections,
        "elapsed_s": round(elapsed, 1),
        "results": results,
    }
    summary_path = out_dir / "recolor_real_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, default=str))
    print(f"Summary:    {summary_path}")

    # Also write a markdown report
    report_lines = [
        "# Real ARC Recolor Operator Results\n",
        f"Tasks analyzed: {len(candidates)}",
        f"Promotions: {promotions}",
        f"Rejections: {rejections}",
        f"Elapsed: {elapsed:.1f}s\n",
        "| Task | Selector | Promoted | Rejection |",
        "|------|----------|----------|-----------|",
    ]
    for r in results:
        status = "YES" if r["promoted"] else "no"
        rej = r.get("rejection_reason", "") or ""
        report_lines.append(f"| {r['task_id']} | {r['selector']} | {status} | {rej} |")

    report_path = out_dir / "recolor_real_report.md"
    report_path.write_text("\n".join(report_lines) + "\n")
    print(f"Report:     {report_path}")


if __name__ == "__main__":
    main()
