"""Analyze rejected executable proposals from v2 focused eval.

For each rejected proposal that had an executable hypothesis, compute
the residual between predicted and gold output, classify what transformation
is missing, and produce a structured taxonomy of operator coverage gaps.
"""
from __future__ import annotations

import csv
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from reasoning_project.adaptive_orchestrator import (
    GatedAdaptiveReasoningOrchestrator,
    OrchestratorConfig,
    TaskAnalysis,
    ModuleProposal,
)
from reasoning_project.arc_adapter import load_arc_tasks, ARCTask
from reasoning_project.proposal_verifier import ProposalVerifier

ARC_ROOT = Path(__file__).parent.parent / "data" / "arc"
OUTPUT_DIR = "outputs/full_novel_reasoning_pipeline_v2/operator_coverage_gap_analysis"
RESULTS_CSV = "outputs/full_novel_reasoning_pipeline_v2/focused_eval_after_executable_repair/results.csv"


def load_rejected_task_ids() -> List[str]:
    rejected = []
    if not os.path.exists(RESULTS_CSV):
        return rejected
    with open(RESULTS_CSV) as f:
        reader = csv.DictReader(f)
        for row in reader:
            if (row.get("config") == "v2_full_gated_orchestrator"
                    and row.get("final_status") == "all_proposals_rejected"):
                rejected.append(row["task_id"])
    return rejected


def compute_residual(predicted: np.ndarray, gold: np.ndarray) -> Dict[str, Any]:
    if predicted is None:
        return {"type": "no_prediction", "diff_cells": -1, "diff_fraction": 1.0}
    if predicted.shape != gold.shape:
        return {
            "type": "shape_mismatch",
            "predicted_shape": list(predicted.shape),
            "gold_shape": list(gold.shape),
            "diff_cells": -1,
            "diff_fraction": 1.0,
        }
    diff_mask = predicted != gold
    diff_cells = int(diff_mask.sum())
    total_cells = gold.size
    diff_fraction = diff_cells / max(total_cells, 1)

    changed_positions = list(zip(*np.where(diff_mask)))
    pred_colors_at_diff = set(int(predicted[r, c]) for r, c in changed_positions)
    gold_colors_at_diff = set(int(gold[r, c]) for r, c in changed_positions)

    return {
        "type": "cell_diff",
        "diff_cells": diff_cells,
        "diff_fraction": round(diff_fraction, 4),
        "pred_colors_at_diff": sorted(pred_colors_at_diff),
        "gold_colors_at_diff": sorted(gold_colors_at_diff),
        "n_changed_positions": len(changed_positions),
    }


def classify_residual(
    inp: np.ndarray,
    predicted: Optional[np.ndarray],
    gold: np.ndarray,
    residual: Dict[str, Any],
    proposal_info: Dict[str, Any],
) -> str:
    if residual["type"] == "no_prediction":
        return "unknown"

    if residual["type"] == "shape_mismatch":
        pred_shape = tuple(residual.get("predicted_shape", []))
        gold_shape = tuple(residual.get("gold_shape", []))
        if gold_shape < pred_shape:
            return "needs_object_crop_or_extract"
        return "needs_canvas_resize"

    diff_frac = residual.get("diff_fraction", 1.0)
    diff_cells = residual.get("diff_cells", 0)

    if diff_cells == 0:
        return "correct"

    pred_colors = set(residual.get("pred_colors_at_diff", []))
    gold_colors = set(residual.get("gold_colors_at_diff", []))

    if predicted is not None and predicted.shape == gold.shape:
        pred_nonzero = set(zip(*np.where(predicted != 0)))
        gold_nonzero = set(zip(*np.where(gold != 0)))

        if pred_nonzero and gold_nonzero:
            overlap = pred_nonzero & gold_nonzero
            pred_only = pred_nonzero - gold_nonzero
            gold_only = gold_nonzero - pred_nonzero

            if len(overlap) > 0.5 * len(gold_nonzero) and pred_only and gold_only:
                dr_set = set()
                dc_set = set()
                for r, c in gold_only:
                    for r2, c2 in pred_only:
                        dr_set.add(r - r2)
                        dc_set.add(c - c2)
                if len(dr_set) == 1 and len(dc_set) == 1:
                    return "needs_translation"

        pred_colors_grid = set(int(v) for v in predicted.flat if v != 0)
        gold_colors_grid = set(int(v) for v in gold.flat if v != 0)
        if pred_colors_grid != gold_colors_grid and np.array_equal(
            predicted != 0, gold != 0
        ):
            return "needs_recolor"

        pred_obj_mask = predicted != 0
        gold_obj_mask = gold != 0
        if not np.array_equal(pred_obj_mask, gold_obj_mask):
            pred_count = pred_obj_mask.sum()
            gold_count = gold_obj_mask.sum()
            if gold_count > pred_count * 1.3:
                return "needs_shape_completion_or_fill"
            if gold_count < pred_count * 0.7:
                return "wrong_object_selected"

    if inp.shape != gold.shape:
        gold_area = gold.shape[0] * gold.shape[1]
        inp_area = inp.shape[0] * inp.shape[1]
        if gold_area < inp_area:
            return "needs_object_crop_or_extract"
        return "needs_canvas_resize"

    if 0 < diff_frac <= 0.15:
        if pred_colors == {0} or gold_colors == {0}:
            return "needs_shape_completion_or_fill"
        return "needs_recolor"

    if 0.15 < diff_frac <= 0.4:
        return "needs_spatial_transform"

    if diff_frac > 0.4:
        strategy = proposal_info.get("strategy", "")
        if "filter" in strategy or "extract" in strategy:
            return "right_property_wrong_output_canvas"
        return "needs_multi_step_composition"

    return "unknown"


def analyze_task(
    task: ARCTask,
    orchestrator: GatedAdaptiveReasoningOrchestrator,
) -> List[Dict[str, Any]]:
    train_pairs = [
        (ex.input_grid, ex.output_grid) for ex in task.train if ex.output_grid is not None
    ]
    test_inputs = [ex.input_grid for ex in task.test]
    test_outputs = [ex.output_grid for ex in task.test if ex.output_grid is not None]

    trace = orchestrator.solve_task(task.task_id, train_pairs, test_inputs, test_outputs or None)

    records = []
    for proposal in trace.proposals:
        hyp = proposal.hypothesis
        executable = None
        was_executable = False

        if callable(hyp):
            executable = hyp
            was_executable = True
        elif isinstance(hyp, dict):
            for key in ("execute", "operator", "prediction_fn"):
                if key in hyp and callable(hyp[key]):
                    executable = hyp[key]
                    was_executable = True
                    break

        train_consistent = False
        loo_status = "not_tested"
        proof_status = "not_tested"
        falsification_status = "not_tested"
        rejection_reason = "not_executable"
        predicted_test = None

        if executable is not None:
            try:
                all_match = True
                for inp, out in train_pairs:
                    pred = executable(inp)
                    if pred is None or not isinstance(pred, np.ndarray):
                        pred = np.array(pred) if pred is not None else None
                    if pred is None or pred.shape != out.shape or not np.array_equal(pred, out):
                        all_match = False
                        break
                train_consistent = all_match
            except Exception:
                train_consistent = False

            if train_consistent:
                loo_ok = True
                for i in range(len(train_pairs)):
                    try:
                        held_inp, held_out = train_pairs[i]
                        pred = executable(held_inp)
                        if pred is None:
                            loo_ok = False
                            break
                        if not isinstance(pred, np.ndarray):
                            pred = np.array(pred)
                        if not np.array_equal(pred, held_out):
                            loo_ok = False
                            break
                    except Exception:
                        loo_ok = False
                        break
                loo_status = "passed" if loo_ok else "failed"
                if not loo_ok:
                    rejection_reason = "loo_failed"
                else:
                    rejection_reason = "falsification_or_test_mismatch"
            else:
                rejection_reason = "train_inconsistent"

            if test_outputs:
                try:
                    predicted_test = executable(test_inputs[0])
                    if predicted_test is not None and not isinstance(predicted_test, np.ndarray):
                        predicted_test = np.array(predicted_test)
                except Exception:
                    predicted_test = None

        gold_test = test_outputs[0] if test_outputs else None
        residual = {}
        residual_class = "unknown"
        if gold_test is not None:
            if predicted_test is not None:
                residual = compute_residual(predicted_test, gold_test)
            elif executable is not None and train_consistent:
                try:
                    predicted_test = executable(test_inputs[0])
                    if predicted_test is not None and not isinstance(predicted_test, np.ndarray):
                        predicted_test = np.array(predicted_test)
                    residual = compute_residual(predicted_test, gold_test)
                except Exception:
                    residual = compute_residual(None, gold_test)
            else:
                residual = compute_residual(None, gold_test)

            proposal_info = {
                "strategy": proposal.operator_family or "",
                "module": proposal.module_name,
            }
            residual_class = classify_residual(
                train_pairs[0][0], predicted_test, gold_test, residual, proposal_info
            )

        record = {
            "task_id": task.task_id,
            "proposal_module": proposal.module_name,
            "operator_family": proposal.operator_family or "",
            "selector": proposal.selector or "",
            "hypothesis_type": proposal.proposal_type,
            "was_executable": was_executable,
            "train_consistent": train_consistent,
            "loo_status": loo_status,
            "rejection_reason": rejection_reason,
            "residual_type": residual.get("type", "unknown"),
            "diff_cells": residual.get("diff_cells", -1),
            "diff_fraction": residual.get("diff_fraction", -1),
            "residual_class": residual_class,
            "confidence": proposal.confidence,
        }
        records.append(record)

        if predicted_test is not None and gold_test is not None:
            example = {
                "task_id": task.task_id,
                "proposal_module": proposal.module_name,
                "operator_family": proposal.operator_family or "",
                "residual_class": residual_class,
                "input_shape": list(test_inputs[0].shape),
                "gold_shape": list(gold_test.shape),
                "predicted_shape": list(predicted_test.shape) if predicted_test is not None else None,
                "diff_cells": residual.get("diff_cells", -1),
                "diff_fraction": residual.get("diff_fraction", -1),
            }
            records[-1]["_example"] = example

    return records


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=OUTPUT_DIR)
    parser.add_argument("--max-tasks", type=int, default=0)
    args = parser.parse_args()
    output_dir = args.output_dir
    os.makedirs(output_dir, exist_ok=True)

    print("=" * 60)
    print("  Rejected Executable Proposal Residual Analyzer")
    print("=" * 60)

    print("\nLoading ARC tasks...")
    arc_tasks = load_arc_tasks(ARC_ROOT)
    task_map = {t.task_id: t for t in arc_tasks}
    print(f"  Loaded {len(task_map)} tasks")

    rejected_ids = load_rejected_task_ids()
    print(f"  Found {len(rejected_ids)} rejected task IDs from focused eval")

    if args.max_tasks > 0:
        rejected_ids = rejected_ids[:args.max_tasks]
        print(f"  Limited to {len(rejected_ids)} tasks")

    config = OrchestratorConfig(timeout_per_task=300.0)
    orchestrator = GatedAdaptiveReasoningOrchestrator(config=config)

    all_records = []
    examples = []

    for i, task_id in enumerate(rejected_ids):
        task = task_map.get(task_id)
        if task is None:
            print(f"  SKIP {task_id}: not in ARC data")
            continue

        try:
            records = analyze_task(task, orchestrator)
            for r in records:
                ex = r.pop("_example", None)
                if ex:
                    examples.append(ex)
            all_records.extend(records)
        except Exception as e:
            print(f"  ERROR {task_id}: {e}")
            continue

        if (i + 1) % 5 == 0:
            exec_count = sum(1 for r in all_records if r["was_executable"])
            print(f"  [{i+1}/{len(rejected_ids)}] {len(all_records)} proposals analyzed, "
                  f"{exec_count} executable")

    csv_path = os.path.join(output_dir, "rejected_proposals.csv")
    if all_records:
        fieldnames = [
            "task_id", "proposal_module", "operator_family", "selector",
            "hypothesis_type", "was_executable", "train_consistent",
            "loo_status", "rejection_reason", "residual_type",
            "diff_cells", "diff_fraction", "residual_class", "confidence",
        ]
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_records)
        print(f"\n  Wrote {len(all_records)} records to {csv_path}")

    taxonomy = defaultdict(int)
    for r in all_records:
        if r["was_executable"]:
            taxonomy[r["residual_class"]] += 1

    tax_path = os.path.join(output_dir, "residual_taxonomy.csv")
    with open(tax_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["residual_class", "count"])
        for cls, count in sorted(taxonomy.items(), key=lambda x: -x[1]):
            writer.writerow([cls, count])
    print(f"  Wrote taxonomy to {tax_path}")

    ex_path = os.path.join(output_dir, "residual_examples.jsonl")
    with open(ex_path, "w") as f:
        for ex in examples:
            f.write(json.dumps(ex) + "\n")
    print(f"  Wrote {len(examples)} examples to {ex_path}")

    summary_lines = [
        "# Rejected Executable Proposal Residual Analysis\n\n",
        f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n",
        f"## Overview\n\n",
        f"- Rejected tasks analyzed: {len(rejected_ids)}\n",
        f"- Total proposals: {len(all_records)}\n",
        f"- Executable proposals: {sum(1 for r in all_records if r['was_executable'])}\n",
        f"- Non-executable (metadata-only): {sum(1 for r in all_records if not r['was_executable'])}\n\n",
        "## Rejection Reasons (executable proposals only)\n\n",
        "| Reason | Count |\n|--------|-------|\n",
    ]
    exec_records = [r for r in all_records if r["was_executable"]]
    reason_counts = defaultdict(int)
    for r in exec_records:
        reason_counts[r["rejection_reason"]] += 1
    for reason, count in sorted(reason_counts.items(), key=lambda x: -x[1]):
        summary_lines.append(f"| {reason} | {count} |\n")

    summary_lines.append("\n## Residual Taxonomy (executable proposals only)\n\n")
    summary_lines.append("| Residual Class | Count |\n|----------------|-------|\n")
    for cls, count in sorted(taxonomy.items(), key=lambda x: -x[1]):
        summary_lines.append(f"| {cls} | {count} |\n")

    summary_lines.append("\n## Module Breakdown\n\n")
    summary_lines.append("| Module | Total | Executable | Train Consistent |\n")
    summary_lines.append("|--------|-------|------------|------------------|\n")
    module_stats = defaultdict(lambda: {"total": 0, "exec": 0, "consistent": 0})
    for r in all_records:
        mod = r["proposal_module"]
        module_stats[mod]["total"] += 1
        if r["was_executable"]:
            module_stats[mod]["exec"] += 1
        if r["train_consistent"]:
            module_stats[mod]["consistent"] += 1
    for mod, stats in sorted(module_stats.items(), key=lambda x: -x[1]["total"]):
        summary_lines.append(
            f"| {mod} | {stats['total']} | {stats['exec']} | {stats['consistent']} |\n"
        )

    summary_path = os.path.join(output_dir, "summary.md")
    with open(summary_path, "w") as f:
        f.writelines(summary_lines)
    print(f"  Wrote summary to {summary_path}")

    print(f"\n{'='*60}")
    print(f"  RESIDUAL ANALYSIS COMPLETE")
    print(f"{'='*60}")
    print(f"  Tasks analyzed: {len(rejected_ids)}")
    print(f"  Total proposals: {len(all_records)}")
    print(f"  Executable: {sum(1 for r in all_records if r['was_executable'])}")
    print(f"  Residual taxonomy:")
    for cls, count in sorted(taxonomy.items(), key=lambda x: -x[1]):
        print(f"    {cls}: {count}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
