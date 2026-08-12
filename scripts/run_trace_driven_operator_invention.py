#!/usr/bin/env python3.11
"""Run trace-driven operator invention on real ARC tasks.

Reads operator-gap traces and near-solved cache, then attempts the full
failure-derived operator invention pipeline on each copy_to_position task.

Usage:
    # Standard CTP run
    python3.11 scripts/run_trace_driven_operator_invention.py \
      --operator-family copy_to_position \
      --trace outputs/operator_gap_analysis/operator_gap_trace.csv \
      --use-cache outputs/cache_fast \
      --max-tasks 31 \
      --output-dir outputs/operator_reasoning_phase/copy_to_position_real

    # Correspondence CTP run on rejected tasks only
    python3.11 scripts/run_trace_driven_operator_invention.py \
      --operator-family correspondence_copy_to_position \
      --input-subset outputs/operator_reasoning_phase/copy_to_position_real/rejected_tasks.jsonl \
      --max-tasks 28
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reasoning_project.arc_adapter import load_arc_tasks
from reasoning_project.trace_operator_invention import (
    TraceDrivenOperatorInventor,
)
from reasoning_project.events import ReasoningEventLog
from reasoning_project.certificates import certificate_to_json, certificate_to_markdown


def load_traces(trace_path: str, family_filter: str) -> list[dict]:
    traces = []
    with open(trace_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("needed_operator_family") == family_filter:
                traces.append(row)
    return traces


def _load_input_subset(path: str) -> set[str]:
    """Load a JSONL file of {task_id: ...} records and return the set of task IDs."""
    task_ids: set[str] = set()
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            task_ids.add(rec["task_id"])
    return task_ids


def _default_output_dir(family: str) -> str:
    """Return the default output directory for a given operator family."""
    if family == "correspondence_copy_to_position":
        return "outputs/operator_reasoning_phase/correspondence/real"
    return "outputs/operator_reasoning_phase/copy_to_position_real"


def main():
    parser = argparse.ArgumentParser(description="Trace-driven operator invention on real ARC")
    parser.add_argument("--operator-family", default="copy_to_position")
    parser.add_argument("--trace", default="outputs/operator_gap_analysis/operator_gap_trace.csv")
    parser.add_argument("--use-cache", default="outputs/cache_fast")
    parser.add_argument("--max-tasks", type=int, default=31)
    parser.add_argument("--output-dir", default=None,
                        help="Output directory (default: auto-selected by --operator-family)")
    parser.add_argument("--data-dir", default="data/arc")
    parser.add_argument("--input-subset", default=None,
                        help="Path to a JSONL file of task IDs to filter to (e.g. rejected_tasks.jsonl)")
    args = parser.parse_args()

    # Resolve output directory: explicit flag > family-specific default
    if args.output_dir is not None:
        output_dir = Path(args.output_dir)
    else:
        output_dir = Path(_default_output_dir(args.operator_family))
    output_dir.mkdir(parents=True, exist_ok=True)
    cert_dir = output_dir / "certificates"
    cert_dir.mkdir(exist_ok=True)

    # Load the input subset filter if provided
    input_subset: set[str] | None = None
    if args.input_subset is not None:
        input_subset = _load_input_subset(args.input_subset)
        print(f"Input subset filter: {len(input_subset)} task IDs from {args.input_subset}")

    # For correspondence_copy_to_position, we load *all* copy_to_position traces
    # (since those are the tasks that need the correspondence fallback).
    # The pipeline itself (run_full_pipeline) handles the CTP -> MR -> corr chain.
    trace_family = args.operator_family
    if trace_family == "correspondence_copy_to_position":
        trace_family = "copy_to_position"

    print(f"Loading traces from {args.trace}...")
    traces = load_traces(args.trace, trace_family)
    print(f"  Found {len(traces)} {trace_family} traces")

    # Apply input-subset filter
    if input_subset is not None:
        traces = [t for t in traces if t["task_id"] in input_subset]
        print(f"  After input-subset filter: {len(traces)} traces")

    if args.max_tasks:
        traces = traces[:args.max_tasks]

    print(f"Loading ARC tasks from {args.data_dir}...")
    all_tasks = load_arc_tasks(args.data_dir, split="training")
    print(f"  Loaded {len(all_tasks)} tasks")

    task_lookup = {t.task_id: t for t in all_tasks}

    event_log = ReasoningEventLog()
    inventor = TraceDrivenOperatorInventor(event_log=event_log)

    results = []
    t0 = time.time()

    for i, trace in enumerate(traces):
        task_id = trace["task_id"]
        task = task_lookup.get(task_id)
        if task is None:
            print(f"  [{i+1}/{len(traces)}] {task_id}: SKIP (not found)")
            results.append({
                "task_id": task_id,
                "operator_proposed": False,
                "rejection_reason": "task_not_found",
            })
            continue

        train_pairs = [
            (ex.input_grid, ex.output_grid)
            for ex in task.train
        ]
        test_inputs = [ex.input_grid for ex in task.test]
        test_outputs = [ex.output_grid for ex in task.test if ex.output_grid is not None]
        if not test_outputs or len(test_outputs) != len(test_inputs):
            test_outputs = None

        print(f"  [{i+1}/{len(traces)}] {task_id} "
              f"(prop={trace.get('best_property', '?')}, "
              f"train={len(train_pairs)}, test={len(test_inputs)})...", end=" ")

        result = inventor.run_full_pipeline(
            task_id=task_id,
            train_pairs=train_pairs,
            test_inputs=test_inputs,
            trace=trace,
            test_outputs=test_outputs,
        )

        status = "PROMOTED" if result["promoted"] else result.get("rejection_reason", "unknown")
        print(status)

        cert_data = result.get("certificate")
        if cert_data:
            cert_path = cert_dir / f"{task_id}.json"
            with open(cert_path, "w") as f:
                json.dump(cert_data, f, indent=2)
            cert_md = result.get("certificate_md", "")
            with open(cert_dir / f"{task_id}.md", "w") as f:
                f.write(cert_md)
            result["certificate_path"] = str(cert_path)

        results.append({
            k: v for k, v in result.items()
            if k not in ("predictions", "certificate_md", "certificate")
        })

    elapsed = time.time() - t0

    n_proposed = sum(1 for r in results if r.get("operator_proposed"))
    n_parameterized = sum(1 for r in results if r.get("parameterized"))
    n_train = sum(1 for r in results if r.get("train_consistent"))
    n_loo = sum(1 for r in results if r.get("loo_passed"))
    n_promoted = sum(1 for r in results if r.get("promoted"))
    n_fp = sum(1 for r in results if r.get("false_positive"))

    rejection_counts: dict[str, int] = {}
    for r in results:
        reason = r.get("rejection_reason")
        if reason:
            rejection_counts[reason] = rejection_counts.get(reason, 0) + 1

    with open(output_dir / "results.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "task_id", "operator_proposed", "parameterized", "train_consistent",
            "loo_passed", "falsification_status", "replay_status", "promoted",
            "false_positive", "rejection_reason", "operator_id", "certificate_path",
        ])
        writer.writeheader()
        for r in results:
            writer.writerow({k: r.get(k, "") for k in writer.fieldnames})

    with open(output_dir / "promoted_tasks.jsonl", "w") as f:
        for r in results:
            if r.get("promoted"):
                f.write(json.dumps({"task_id": r["task_id"]}) + "\n")

    with open(output_dir / "rejected_tasks.jsonl", "w") as f:
        for r in results:
            if not r.get("promoted") and r.get("rejection_reason"):
                f.write(json.dumps({
                    "task_id": r["task_id"],
                    "reason": r["rejection_reason"],
                }) + "\n")

    inventor.write_artifacts(str(output_dir))
    event_log.export_jsonl(str(output_dir / "events.jsonl"))

    summary_lines = [
        "# Real ARC Copy-to-Position Operator Invention",
        "",
        f"- Tasks attempted: {len(traces)}",
        f"- Operators proposed: {n_proposed}",
        f"- Parameterized: {n_parameterized}",
        f"- Train-consistent: {n_train}",
        f"- LOO-validated: {n_loo}",
        f"- **Promoted: {n_promoted}**",
        f"- False positives: {n_fp}",
        f"- Elapsed: {elapsed:.1f}s",
        "",
        "## Rejection Reasons (ranked)",
        "",
        "| Reason | Count |",
        "|--------|-------|",
    ]
    for reason, count in sorted(rejection_counts.items(), key=lambda x: -x[1]):
        summary_lines.append(f"| {reason} | {count} |")

    summary_lines.extend([
        "",
        "## Interpretation",
        "",
    ])
    if n_promoted > 0:
        summary_lines.append(
            f"**{n_promoted} real ARC task(s) promoted** by failure-derived "
            f"copy_to_position operator, with {n_fp} false positives. "
            "This demonstrates bounded real-task cumulative reasoning."
        )
    else:
        summary_lines.append(
            "0 real ARC tasks promoted. The operator invention pipeline "
            "proposes and validates operators from traces, but the inferred "
            "spatial transformations do not yet produce exact matches on "
            "real ARC test outputs. See rejection reasons above."
        )

    with open(output_dir / "summary.md", "w") as f:
        f.write("\n".join(summary_lines) + "\n")

    print(f"\n{'='*60}")
    print(f"REAL ARC: {n_promoted} promoted, {n_fp} FP, {elapsed:.1f}s")
    print(f"{'='*60}")


def _load_arc_raw(data_dir: str) -> list[dict]:
    """Fallback ARC loader."""
    tasks = []
    data_path = Path(data_dir)
    if not data_path.exists():
        for alt in [
            Path("data/arc/training"),
            Path("/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project/data/arc/training"),
        ]:
            if alt.exists():
                data_path = alt
                break
    for f in sorted(data_path.glob("*.json")):
        with open(f) as fh:
            data = json.load(fh)
        tasks.append({"task_id": f.stem, **data})
    return tasks


if __name__ == "__main__":
    main()
