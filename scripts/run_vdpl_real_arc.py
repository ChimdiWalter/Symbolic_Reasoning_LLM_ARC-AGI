#!/usr/bin/env python3.11
"""Run Variable Destination Policy Learning (VDPL) on rejected ARC tasks.

Phase 9: applies the full CTP -> MR -> CORR -> VDPL fallback chain to the 28
correspondence-rejected tasks.  Includes a many-to-few pre-filter that skips
tasks where len(removed) > len(kept) across training pairs, since injective
matching cannot work there.

Usage:
    python3.11 scripts/run_vdpl_real_arc.py
    python3.11 scripts/run_vdpl_real_arc.py --max-tasks 10
    python3.11 scripts/run_vdpl_real_arc.py --skip-many-to-few
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reasoning_project.arc_adapter import load_arc_tasks
from reasoning_project.trace_operator_invention import TraceDrivenOperatorInventor
from reasoning_project.events import ReasoningEventLog
from reasoning_project.certificates import certificate_to_json, certificate_to_markdown
from reasoning_project.reasoning_engine import (
    _extract_objects_with_properties,
    _classify_kept_removed,
)


# ═══════════════════════════════════════════════════════════════════════════
# REJECTION TAXONOMY
# ═══════════════════════════════════════════════════════════════════════════

BARRIER_CATEGORIES = [
    "many_to_few",
    "perception_failure",
    "parameter_inference_failed",
    "train_fit_failed",
    "loo_failed",
    "ambiguity_rejected",
    "proof_obligation_failed",
    "promotion_failed",
    "task_not_found",
]


def classify_rejection(result: Dict[str, Any], is_many_to_few: bool) -> str:
    """Map a pipeline result dict to a barrier taxonomy category."""
    if is_many_to_few:
        return "many_to_few"

    reason = result.get("rejection_reason", "") or ""

    if "parameter_inference_failed" in reason:
        return "parameter_inference_failed"
    if "perception" in reason.lower():
        return "perception_failure"
    if "train_fit" in reason or "vdp_train_fit" in reason:
        return "train_fit_failed"
    if "loo" in reason.lower():
        return "loo_failed"
    if "ambiguity" in reason.lower():
        return "ambiguity_rejected"
    if "proof" in reason.lower() or "obligation" in reason.lower():
        return "proof_obligation_failed"
    if "promotion" in reason.lower() or "replay" in reason.lower():
        return "promotion_failed"
    if "task_not_found" in reason:
        return "task_not_found"

    # Fallback: map train_fit=0.000 style reasons
    if reason.startswith("train_fit="):
        return "train_fit_failed"
    if reason.startswith("vdp_train_fit="):
        return "train_fit_failed"

    return reason if reason else "unknown"


# ═══════════════════════════════════════════════════════════════════════════
# MANY-TO-FEW PRE-FILTER
# ═══════════════════════════════════════════════════════════════════════════

def check_many_to_few(train_pairs: List[Tuple[np.ndarray, np.ndarray]]) -> bool:
    """Return True if removed > kept in ANY training pair (many-to-few)."""
    for inp, out in train_pairs:
        objects = _extract_objects_with_properties(inp)
        result = _classify_kept_removed(objects, inp, out)
        if result is None:
            continue
        kept_idx, removed_idx = result
        if len(removed_idx) > len(kept_idx):
            return True
    return False


def get_kept_removed_counts(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> List[Dict[str, int]]:
    """Return per-example kept/removed counts for diagnostics."""
    counts = []
    for inp, out in train_pairs:
        objects = _extract_objects_with_properties(inp)
        result = _classify_kept_removed(objects, inp, out)
        if result is None:
            counts.append({"kept": 0, "removed": 0, "total": len(objects)})
        else:
            kept_idx, removed_idx = result
            counts.append({
                "kept": len(kept_idx),
                "removed": len(removed_idx),
                "total": len(objects),
            })
    return counts


# ═══════════════════════════════════════════════════════════════════════════
# LOADING HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def load_rejected_task_ids(results_csv: str) -> List[str]:
    """Load rejected task IDs from the correspondence results CSV."""
    task_ids = []
    with open(results_csv) as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("promoted", "").lower() in ("false", "0", ""):
                task_ids.append(row["task_id"])
    return task_ids


def load_traces(trace_path: str, family_filter: str = "copy_to_position") -> Dict[str, Dict]:
    """Load operator gap traces and index by task_id."""
    traces: Dict[str, Dict] = {}
    with open(trace_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("needed_operator_family") == family_filter:
                traces[row["task_id"]] = row
    return traces


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Run VDPL on correspondence-rejected ARC tasks (Phase 9)",
    )
    parser.add_argument(
        "--rejected-csv",
        default="outputs/operator_reasoning_phase/correspondence/real/results.csv",
        help="Path to correspondence results CSV with rejected tasks",
    )
    parser.add_argument(
        "--trace",
        default="outputs/operator_gap_analysis/operator_gap_trace.csv",
        help="Path to operator gap trace CSV",
    )
    parser.add_argument(
        "--data-dir",
        default="data/arc",
        help="ARC data directory",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs/operator_reasoning_phase/variable_destination/real",
        help="Output directory for VDPL results",
    )
    parser.add_argument(
        "--max-tasks",
        type=int,
        default=None,
        help="Maximum number of tasks to process",
    )
    parser.add_argument(
        "--skip-many-to-few",
        action="store_true",
        help="Skip the many-to-few pre-filter (run VDPL on all tasks)",
    )
    args = parser.parse_args()

    # ── Setup output directories ──────────────────────────────────────
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    cert_dir = output_dir / "certificates"
    cert_dir.mkdir(exist_ok=True)

    # ── Load rejected task IDs ────────────────────────────────────────
    print(f"Loading rejected task IDs from {args.rejected_csv}...")
    rejected_ids = load_rejected_task_ids(args.rejected_csv)
    print(f"  Found {len(rejected_ids)} rejected tasks")

    # ── Load traces (indexed by task_id) ──────────────────────────────
    print(f"Loading traces from {args.trace}...")
    trace_lookup = load_traces(args.trace)
    print(f"  Found {len(trace_lookup)} copy_to_position traces")

    # ── Load ARC tasks ────────────────────────────────────────────────
    print(f"Loading ARC tasks from {args.data_dir}...")
    all_tasks = load_arc_tasks(args.data_dir, split="training")
    task_lookup = {t.task_id: t for t in all_tasks}
    print(f"  Loaded {len(all_tasks)} tasks")

    # ── Prepare task list ─────────────────────────────────────────────
    task_ids = [tid for tid in rejected_ids if tid in trace_lookup]
    missing_trace = [tid for tid in rejected_ids if tid not in trace_lookup]
    if missing_trace:
        print(f"  Warning: {len(missing_trace)} rejected tasks have no trace: {missing_trace}")

    if args.max_tasks:
        task_ids = task_ids[:args.max_tasks]
    print(f"  Processing {len(task_ids)} tasks")

    # ── Many-to-few pre-filter ────────────────────────────────────────
    many_to_few_ids: Set[str] = set()
    many_to_few_details: Dict[str, List[Dict[str, int]]] = {}

    if not args.skip_many_to_few:
        print("\nRunning many-to-few pre-filter...")
        for tid in task_ids:
            task = task_lookup.get(tid)
            if task is None:
                continue
            train_pairs = [
                (np.array(ex.input_grid), np.array(ex.output_grid))
                for ex in task.train
            ]
            if check_many_to_few(train_pairs):
                many_to_few_ids.add(tid)
                many_to_few_details[tid] = get_kept_removed_counts(train_pairs)
        print(f"  Many-to-few tasks: {len(many_to_few_ids)} / {len(task_ids)}")
        if many_to_few_ids:
            print(f"  IDs: {sorted(many_to_few_ids)}")

    # ── Run the pipeline ──────────────────────────────────────────────
    event_log = ReasoningEventLog()
    inventor = TraceDrivenOperatorInventor(event_log=event_log)

    results: List[Dict[str, Any]] = []
    t0 = time.time()

    for i, tid in enumerate(task_ids):
        task = task_lookup.get(tid)
        trace = trace_lookup.get(tid)

        if task is None:
            print(f"  [{i+1}/{len(task_ids)}] {tid}: SKIP (task not found)")
            results.append({
                "task_id": tid,
                "promoted": False,
                "rejection_reason": "task_not_found",
                "operator_id": None,
                "barrier_category": "task_not_found",
                "is_many_to_few": False,
            })
            continue

        # Many-to-few: skip VDPL entirely
        if tid in many_to_few_ids:
            print(f"  [{i+1}/{len(task_ids)}] {tid}: SKIP (many-to-few)")
            results.append({
                "task_id": tid,
                "promoted": False,
                "rejection_reason": "many_to_few",
                "operator_id": None,
                "barrier_category": "many_to_few",
                "is_many_to_few": True,
                "kept_removed_counts": many_to_few_details.get(tid, []),
            })
            continue

        train_pairs = [
            (np.array(ex.input_grid), np.array(ex.output_grid))
            for ex in task.train
        ]
        test_inputs = [np.array(ex.input_grid) for ex in task.test]
        test_outputs = [
            np.array(ex.output_grid) for ex in task.test
            if ex.output_grid is not None
        ]
        if not test_outputs or len(test_outputs) != len(test_inputs):
            test_outputs = None

        print(
            f"  [{i+1}/{len(task_ids)}] {tid} "
            f"(prop={trace.get('best_property', '?')}, "
            f"train={len(train_pairs)}, test={len(test_inputs)})...",
            end=" ",
        )

        result = inventor.run_full_pipeline(
            task_id=tid,
            train_pairs=train_pairs,
            test_inputs=test_inputs,
            trace=trace,
            test_outputs=test_outputs,
        )

        # Classify the barrier
        barrier = classify_rejection(result, is_many_to_few=False)
        result["barrier_category"] = barrier
        result["is_many_to_few"] = False

        status = "PROMOTED" if result.get("promoted") else result.get("rejection_reason", "unknown")
        print(status)

        # Write certificate if promoted
        cert_data = result.get("certificate")
        if cert_data:
            cert_path = cert_dir / f"{tid}.json"
            with open(cert_path, "w") as f:
                json.dump(cert_data, f, indent=2)
            cert_md = result.get("certificate_md", "")
            with open(cert_dir / f"{tid}.md", "w") as f:
                f.write(cert_md)
            result["certificate_path"] = str(cert_path)

        # Strip non-serializable fields before storing
        results.append({
            k: v for k, v in result.items()
            if k not in ("predictions", "certificate_md", "certificate")
        })

    elapsed = time.time() - t0

    # ── Compute summary statistics ────────────────────────────────────
    n_total = len(results)
    n_many_to_few = sum(1 for r in results if r.get("is_many_to_few"))
    n_pipeline_run = n_total - n_many_to_few
    n_promoted = sum(1 for r in results if r.get("promoted"))
    n_operator_proposed = sum(1 for r in results if r.get("operator_proposed"))
    n_train_consistent = sum(1 for r in results if r.get("train_consistent"))
    n_loo_passed = sum(1 for r in results if r.get("loo_passed"))
    n_fp = sum(1 for r in results if r.get("false_positive"))

    # Barrier taxonomy
    barrier_counts: Dict[str, int] = {}
    for r in results:
        cat = r.get("barrier_category", "unknown")
        barrier_counts[cat] = barrier_counts.get(cat, 0) + 1

    # Rejection reasons (raw, from pipeline)
    rejection_counts: Dict[str, int] = {}
    for r in results:
        reason = r.get("rejection_reason")
        if reason:
            rejection_counts[reason] = rejection_counts.get(reason, 0) + 1

    # ── Write results.csv ─────────────────────────────────────────────
    csv_fields = [
        "task_id", "promoted", "rejection_reason", "operator_id",
        "barrier_category", "is_many_to_few",
        "operator_proposed", "parameterized", "train_consistent",
        "loo_passed", "falsification_status", "replay_status",
        "false_positive", "certificate_path",
    ]
    with open(output_dir / "results.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields)
        writer.writeheader()
        for r in results:
            writer.writerow({k: r.get(k, "") for k in csv_fields})

    # ── Write promoted_tasks.jsonl ────────────────────────────────────
    with open(output_dir / "promoted_tasks.jsonl", "w") as f:
        for r in results:
            if r.get("promoted"):
                f.write(json.dumps({"task_id": r["task_id"]}) + "\n")

    # ── Write rejected_tasks.jsonl ────────────────────────────────────
    with open(output_dir / "rejected_tasks.jsonl", "w") as f:
        for r in results:
            if not r.get("promoted"):
                rec = {
                    "task_id": r["task_id"],
                    "reason": r.get("rejection_reason", "unknown"),
                    "barrier_category": r.get("barrier_category", "unknown"),
                }
                if r.get("is_many_to_few"):
                    rec["kept_removed_counts"] = r.get("kept_removed_counts", [])
                f.write(json.dumps(rec) + "\n")

    # ── Write operator artifacts (proposed/validated/rejected) ────────
    inventor.write_artifacts(str(output_dir))

    # ── Write events.jsonl ────────────────────────────────────────────
    event_log.export_jsonl(str(output_dir / "events.jsonl"))

    # ── Write summary.md ──────────────────────────────────────────────
    summary_lines = [
        "# VDPL Phase 9: Variable Destination Policy Learning on Rejected Tasks",
        "",
        f"**Date**: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Elapsed**: {elapsed:.1f}s",
        "",
        "## Pipeline Summary",
        "",
        f"- Total tasks: {n_total}",
        f"- Many-to-few (pre-filtered): {n_many_to_few}",
        f"- Pipeline-run tasks: {n_pipeline_run}",
        f"- Operators proposed: {n_operator_proposed}",
        f"- Train-consistent: {n_train_consistent}",
        f"- LOO-validated: {n_loo_passed}",
        f"- **Promoted: {n_promoted}**",
        f"- False positives: {n_fp}",
        "",
        "## Barrier Taxonomy",
        "",
        "| Barrier Stage | Count | Pct |",
        "|---------------|-------|-----|",
    ]
    for cat in BARRIER_CATEGORIES:
        count = barrier_counts.get(cat, 0)
        pct = 100 * count / max(n_total, 1)
        summary_lines.append(f"| {cat} | {count} | {pct:.1f}% |")
    other_count = sum(v for k, v in barrier_counts.items() if k not in BARRIER_CATEGORIES)
    if other_count:
        pct = 100 * other_count / max(n_total, 1)
        summary_lines.append(f"| other | {other_count} | {pct:.1f}% |")

    summary_lines.extend([
        "",
        "## Raw Rejection Reasons",
        "",
        "| Reason | Count |",
        "|--------|-------|",
    ])
    for reason, count in sorted(rejection_counts.items(), key=lambda x: -x[1]):
        summary_lines.append(f"| {reason} | {count} |")

    summary_lines.extend([
        "",
        "## Interpretation",
        "",
    ])
    if n_promoted > 0:
        summary_lines.append(
            f"**{n_promoted} real ARC task(s) promoted** via the full "
            f"CTP->MR->CORR->VDPL fallback chain. "
            f"{n_many_to_few} tasks were pre-filtered as many-to-few "
            f"(removed > kept, no injective match possible)."
        )
    else:
        summary_lines.append(
            f"0 real ARC tasks promoted. {n_many_to_few} tasks were "
            f"pre-filtered as many-to-few. The remaining {n_pipeline_run} "
            f"tasks ran through the full VDPL fallback chain but did not "
            f"produce exact test matches. See barrier taxonomy above for "
            f"where each task failed."
        )

    summary_lines.extend([
        "",
        "## Many-to-Few Details",
        "",
    ])
    if many_to_few_ids:
        summary_lines.append("| Task ID | Example | Kept | Removed | Total |")
        summary_lines.append("|---------|---------|------|---------|-------|")
        for tid in sorted(many_to_few_ids):
            counts = many_to_few_details.get(tid, [])
            for j, c in enumerate(counts):
                summary_lines.append(
                    f"| {tid} | train[{j}] | {c['kept']} | {c['removed']} | {c['total']} |"
                )
    else:
        summary_lines.append("No many-to-few tasks detected.")

    with open(output_dir / "summary.md", "w") as f:
        f.write("\n".join(summary_lines) + "\n")

    # ── Console summary ───────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"VDPL PHASE 9 RESULTS")
    print(f"{'='*60}")
    print(f"  Total tasks:      {n_total}")
    print(f"  Many-to-few:      {n_many_to_few}")
    print(f"  Pipeline-run:     {n_pipeline_run}")
    print(f"  Promoted:         {n_promoted}")
    print(f"  False positives:  {n_fp}")
    print(f"  Elapsed:          {elapsed:.1f}s")
    print()
    print("Barrier taxonomy:")
    for cat in BARRIER_CATEGORIES:
        count = barrier_counts.get(cat, 0)
        if count:
            print(f"  {cat}: {count}")
    print(f"{'='*60}")
    print(f"Results written to {output_dir}/")


if __name__ == "__main__":
    main()
