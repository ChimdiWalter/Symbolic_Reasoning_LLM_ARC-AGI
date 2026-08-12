#!/usr/bin/env python3.11
"""Phase 8: Run color-transfer operator invention on real ARC recolor tasks.

Loads the 12 rejected recolor tasks from the gap analysis and runs the full
trace-driven operator invention pipeline on each. The pipeline's fallback
chain includes color_transfer_recolor as the final family.

Outputs:
  outputs/operator_reasoning_phase/color_transfer/real/summary.md
  outputs/operator_reasoning_phase/color_transfer/real/results.csv
  outputs/operator_reasoning_phase/color_transfer/real/promoted_tasks.jsonl
  outputs/operator_reasoning_phase/color_transfer/real/rejected_tasks.jsonl
  outputs/operator_reasoning_phase/color_transfer/real/certificates/
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


_ARC_CACHE: Optional[Dict] = None
_ARC_SOLUTIONS_CACHE: Optional[Dict] = None

def _load_arc_data() -> Tuple[Dict, Dict]:
    global _ARC_CACHE, _ARC_SOLUTIONS_CACHE
    if _ARC_CACHE is None:
        with open("data/arc/arc-agi_training_challenges.json") as f:
            _ARC_CACHE = json.load(f)
        sol_path = Path("data/arc/arc-agi_training_solutions.json")
        if sol_path.exists():
            with open(sol_path) as f:
                _ARC_SOLUTIONS_CACHE = json.load(f)
        else:
            _ARC_SOLUTIONS_CACHE = {}
    return _ARC_CACHE, _ARC_SOLUTIONS_CACHE

def load_arc_task(task_id: str) -> Optional[Dict]:
    challenges, solutions = _load_arc_data()
    if task_id not in challenges:
        return None
    task = challenges[task_id]
    sol = solutions.get(task_id, [])
    if sol:
        for i, s in enumerate(sol):
            if i < len(task["test"]):
                task["test"][i]["output"] = s
    return task


def load_recolor_tasks() -> List[Dict[str, Any]]:
    """Load the 12 recolor tasks from gap analysis and recolor real results."""
    gap_csv = Path("outputs/operator_gap_analysis_v3/operator_gap_trace.csv")
    recolor_summary = Path("outputs/operator_reasoning_phase/recolor_real/recolor_real_summary.json")
    context_summary = Path("outputs/operator_reasoning_phase/recolor_context/color_source_candidate_summary.json")

    recolor_task_ids = []
    if recolor_summary.exists():
        with open(recolor_summary) as f:
            data = json.load(f)
        recolor_task_ids = [r["task_id"] for r in data["results"]]

    if not recolor_task_ids and gap_csv.exists():
        with open(gap_csv) as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("needed_operator_family") == "recolor_in_place":
                    recolor_task_ids.append(row["task_id"])

    context_info = {}
    if context_summary.exists():
        with open(context_summary) as f:
            data = json.load(f)
        for entry in data.get("per_task", []):
            context_info[entry["task_id"]] = entry

    tasks = []
    for tid in recolor_task_ids:
        arc_task = load_arc_task(tid)
        if arc_task is None:
            print(f"  WARNING: task {tid} not found in data/arc/training/")
            continue

        train_pairs = [
            (np.array(p["input"], dtype=int), np.array(p["output"], dtype=int))
            for p in arc_task["train"]
        ]
        test_inputs = [np.array(p["input"], dtype=int) for p in arc_task["test"]]
        test_outputs = [np.array(p["output"], dtype=int) for p in arc_task["test"]]

        ctx = context_info.get(tid, {})
        best_property = ctx.get("best_property", "")

        if not best_property:
            with open(gap_csv) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row["task_id"] == tid:
                        best_property = row.get("best_property", "")
                        break

        tasks.append({
            "task_id": tid,
            "train_pairs": train_pairs,
            "test_inputs": test_inputs,
            "test_outputs": test_outputs,
            "trace": {
                "best_property": best_property,
                "needed_operator_family": "recolor_in_place",
            },
            "classified_type": ctx.get("classified_type", "unknown"),
            "source_matches": ctx.get("source_matches", []),
        })

    return tasks


def main():
    os.chdir(Path(__file__).resolve().parent.parent)

    out_dir = Path("outputs/operator_reasoning_phase/color_transfer/real")
    cert_dir = out_dir / "certificates"
    out_dir.mkdir(parents=True, exist_ok=True)
    cert_dir.mkdir(parents=True, exist_ok=True)

    tasks = load_recolor_tasks()
    print(f"Loaded {len(tasks)} recolor tasks")

    results = []
    promoted_tasks = []
    rejected_tasks = []
    t0 = time.time()

    for task in tasks:
        tid = task["task_id"]
        train_pairs = task["train_pairs"]
        test_inputs = task["test_inputs"]
        test_outputs = task["test_outputs"]
        trace = task["trace"]

        print(f"\n{'=' * 50}")
        print(f"Task: {tid}")
        print(f"  Selector: {trace['best_property']}")
        print(f"  Classified type: {task['classified_type']}")
        print(f"  Source matches: {task['source_matches']}")

        event_log = ReasoningEventLog()
        inventor = TraceDrivenOperatorInventor(event_log=event_log)

        result = inventor.run_full_pipeline(
            task_id=tid,
            train_pairs=train_pairs,
            test_inputs=test_inputs,
            trace=trace,
            test_outputs=test_outputs,
        )

        proposed = result.get("operator_proposed", False)
        promoted = result.get("promoted", False)
        op_id = result.get("operator_id", "")
        family = result.get("family", "")
        if not family and op_id:
            if "ctr_" in op_id:
                family = "color_transfer_recolor"
            elif "rcl_" in op_id:
                family = "recolor_in_place"
            else:
                family = op_id.split("_")[0]

        rejection = result.get("rejection_reason", "")
        rule_type = ""
        if family == "color_transfer_recolor" and op_id:
            parts = op_id.split("_")
            if len(parts) >= 3:
                rule_type = parts[2] if len(parts) > 3 else ""

        task_result = {
            "task_id": tid,
            "selector": trace["best_property"],
            "classified_type": task["classified_type"],
            "proposed": proposed,
            "promoted": promoted,
            "family": family,
            "rule_type": rule_type,
            "operator_id": op_id,
            "rejection_reason": rejection,
            "train_consistent": result.get("train_consistent", False),
            "loo_passed": result.get("loo_passed", False),
        }
        results.append(task_result)

        if promoted:
            promoted_tasks.append(task_result)
            print(f"  PROMOTED via {family} (rule: {rule_type})")

            cert = result.get("certificate")
            cert_md = result.get("certificate_md")
            if cert is not None:
                cert_path = cert_dir / f"{tid}_certificate.json"
                cert_path.write_text(json.dumps(cert, indent=2, default=str))
                if cert_md:
                    md_path = cert_dir / f"{tid}_certificate.md"
                    md_path.write_text(cert_md)
                print(f"  Certificate: {cert_path}")
        else:
            rejected_tasks.append(task_result)
            print(f"  Rejected: {rejection}")

    elapsed = time.time() - t0

    # Write results CSV
    csv_path = out_dir / "results.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "task_id", "selector", "classified_type", "proposed", "promoted",
            "family", "rule_type", "operator_id", "rejection_reason",
            "train_consistent", "loo_passed",
        ])
        writer.writeheader()
        for r in results:
            writer.writerow(r)

    # Write promoted tasks
    promoted_path = out_dir / "promoted_tasks.jsonl"
    with open(promoted_path, "w") as f:
        for t in promoted_tasks:
            f.write(json.dumps(t, default=str) + "\n")

    # Write rejected tasks
    rejected_path = out_dir / "rejected_tasks.jsonl"
    with open(rejected_path, "w") as f:
        for t in rejected_tasks:
            f.write(json.dumps(t, default=str) + "\n")

    # Write summary
    n_promoted = len(promoted_tasks)
    n_rejected = len(rejected_tasks)

    # Classify rejection reasons
    rejection_types = {}
    for t in rejected_tasks:
        reason = t.get("rejection_reason", "unknown")
        cat = reason.split("=")[0] if "=" in reason else reason
        rejection_types[cat] = rejection_types.get(cat, 0) + 1

    summary_path = out_dir / "summary.md"
    with open(summary_path, "w") as f:
        f.write("# Real ARC Color-Transfer Results\n\n")
        f.write(f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"Tasks analyzed: {len(results)}\n")
        f.write(f"Promotions: {n_promoted}\n")
        f.write(f"Rejections: {n_rejected}\n")
        f.write(f"Elapsed: {elapsed:.1f}s\n\n")

        f.write("## Per-Task Results\n\n")
        f.write("| Task | Classified Type | Selector | Promoted | Family | Rejection |\n")
        f.write("|------|----------------|----------|----------|--------|-----------|\n")
        for r in results:
            f.write(f"| {r['task_id']} | {r['classified_type']} | {r['selector']} | "
                    f"{'yes' if r['promoted'] else 'no'} | {r['family']} | {r['rejection_reason']} |\n")

        f.write("\n## Rejection Taxonomy\n\n")
        f.write("| Category | Count |\n|----------|-------|\n")
        for cat, cnt in sorted(rejection_types.items(), key=lambda x: -x[1]):
            f.write(f"| {cat} | {cnt} |\n")

        if n_promoted > 0:
            f.write(f"\n## Promoted Tasks\n\n")
            for t in promoted_tasks:
                f.write(f"- **{t['task_id']}**: {t['family']} ({t['rule_type']})\n")
        else:
            f.write("\n## Analysis\n\n")
            f.write("No tasks promoted. The color-transfer inference engine covers 7 rule types:\n")
            f.write("nearest_kept, same_shape, same_size, neighbor, container, same_row, same_col, swap.\n\n")
            f.write("Real ARC recolor failures require richer context-dependent color policies\n")
            f.write("beyond the tested transfer/swap families.\n")

    print(f"\n{'=' * 50}")
    print(f"RESULTS: {n_promoted}/{len(results)} promoted, {n_rejected} rejected")
    print(f"Elapsed: {elapsed:.1f}s")
    print(f"Summary: {summary_path}")

    return n_promoted, len(results)


if __name__ == "__main__":
    promotions, total = main()
    sys.exit(0)
