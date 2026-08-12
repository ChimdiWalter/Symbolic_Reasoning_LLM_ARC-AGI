"""Operator gap audit after ViewProgram lifting.

For each failed task and each applicable ViewProgram, computes residual
features between lifted input and expected output. Classifies the missing
operator family needed to close the gap.

Input:
    adaptergenesis_zero_proposal_audit_detail.json
    selected_replay_tasks.csv

Output:
    operator_gap_after_lift.csv
    operator_gap_after_lift_summary.md

Usage:
    source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate
    PYTHONPATH=src python3.11 scripts/audit_operator_gap_after_lift.py
"""
from __future__ import annotations

import csv
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy import ndimage

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from reasoning_project.view_programs import (
    enumerate_view_programs,
    IdentityView,
    CropNonBackgroundView,
    CropBoundingBoxView,
    RemoveFrameView,
    ExtractInteriorView,
    SplitColorLayerView,
    ForegroundBackgroundView,
    NormalizeObjectBBoxView,
    SymmetryQuotientView,
    RepeatedMotifView,
    LineAnchorView,
)
from reasoning_project.reasoning_engine import (
    _extract_objects_with_properties,
)

ROOT = Path(__file__).resolve().parent.parent
FDAG_OUT = ROOT / "outputs" / "full_novel_reasoning_pipeline_v2" / "failure_driven_adaptergenesis_v2_2026_06_21"
OUT = ROOT / "outputs" / "full_novel_reasoning_pipeline_v2" / "operator_genesis_v1_2026_06_21"
ARC_CHALLENGES = ROOT / "data" / "arc" / "arc-agi_training_challenges.json"
ARC_SOLUTIONS = ROOT / "data" / "arc" / "arc-agi_training_solutions.json"


def load_arc_data():
    with open(ARC_CHALLENGES) as f:
        challenges = json.load(f)
    with open(ARC_SOLUTIONS) as f:
        solutions = json.load(f)
    return challenges, solutions


def load_task(task_id, challenges, solutions):
    task = challenges[task_id]
    sol = solutions.get(task_id, [])
    train_pairs = [(np.array(p["input"], dtype=int), np.array(p["output"], dtype=int))
                   for p in task["train"]]
    test_inputs = [np.array(t["input"], dtype=int) for t in task["test"]]
    test_outputs = [np.array(sol[i], dtype=int) for i in range(len(sol))] if sol else None
    return train_pairs, test_inputs, test_outputs


def count_connected_components(grid: np.ndarray) -> int:
    _, n = ndimage.label(grid != 0)
    return n


def count_colors(grid: np.ndarray) -> int:
    return len(set(grid.flatten().tolist()) - {0})


def classify_residual(
    inp: np.ndarray, out: np.ndarray,
) -> Dict[str, Any]:
    """Classify the pixel residual between input and output."""
    result: Dict[str, Any] = {}

    same_shape = inp.shape == out.shape
    result["input_shape"] = list(inp.shape)
    result["output_shape"] = list(out.shape)
    result["same_shape"] = same_shape

    n_obj_in = count_connected_components(inp)
    n_obj_out = count_connected_components(out)
    result["n_objects_before"] = n_obj_in
    result["n_objects_after"] = n_obj_out
    result["object_count_change"] = n_obj_out - n_obj_in

    c_in = count_colors(inp)
    c_out = count_colors(out)
    result["color_count_in"] = c_in
    result["color_count_out"] = c_out
    result["color_count_change"] = c_out - c_in

    result["cc_in"] = n_obj_in
    result["cc_out"] = n_obj_out
    result["connected_component_change"] = n_obj_out - n_obj_in

    if same_shape:
        diff = inp != out
        n_changed = int(diff.sum())
        n_total = inp.size
        result["pixels_changed"] = n_changed
        result["pixel_change_fraction"] = round(n_changed / max(n_total, 1), 4)

        # Bounding box of changed region
        if n_changed > 0:
            rows, cols = np.where(diff)
            bbox = (int(rows.min()), int(cols.min()), int(rows.max()), int(cols.max()))
            result["change_bbox"] = bbox
            bbox_area = (bbox[2] - bbox[0] + 1) * (bbox[3] - bbox[1] + 1)
            result["bbox_change_area"] = bbox_area
        else:
            result["change_bbox"] = None
            result["bbox_change_area"] = 0
    else:
        result["pixels_changed"] = None
        result["pixel_change_fraction"] = None
        result["change_bbox"] = None
        result["bbox_change_area"] = None

    # Classify residual type flags
    result["crop_like"] = False
    result["copy_like"] = False
    result["extend_line_like"] = False
    result["fill_hole_like"] = False
    result["recolor_like"] = False
    result["move_like"] = False
    result["reflect_like"] = False
    result["repeat_like"] = False
    result["count_like"] = False
    result["composition_needed"] = False

    # Crop detection
    if not same_shape:
        if out.shape[0] <= inp.shape[0] and out.shape[1] <= inp.shape[1]:
            result["crop_like"] = True
        elif out.shape[0] >= inp.shape[0] and out.shape[1] >= inp.shape[1]:
            result["repeat_like"] = True

    if same_shape and result["pixels_changed"] is not None:
        if result["pixels_changed"] == 0:
            pass
        else:
            # Recolor: same objects, different colors
            labeled_in, n_in = ndimage.label(inp != 0)
            labeled_out, n_out = ndimage.label(out != 0)
            if n_in == n_out and n_in > 0:
                shapes_match = True
                for label in range(1, n_in + 1):
                    mask_in = labeled_in == label
                    mask_out = labeled_out == label
                    if mask_in.shape != mask_out.shape or not np.array_equal(mask_in, mask_out):
                        shapes_match = False
                        break
                if shapes_match:
                    result["recolor_like"] = True

            # Fill hole: output has fewer zeros inside objects
            zeros_in = int((inp == 0).sum())
            zeros_out = int((out == 0).sum())
            if zeros_out < zeros_in and n_obj_out <= n_obj_in:
                result["fill_hole_like"] = True

            # Move detection: object count same but positions differ
            if n_in == n_out and n_in > 0 and not result["recolor_like"]:
                centroids_in = ndimage.center_of_mass(inp != 0, labeled_in, range(1, n_in + 1))
                centroids_out = ndimage.center_of_mass(out != 0, labeled_out, range(1, n_out + 1))
                if len(centroids_in) == len(centroids_out):
                    # Check if any centroid moved
                    moved = any(
                        abs(ci[0] - co[0]) > 0.5 or abs(ci[1] - co[1]) > 0.5
                        for ci, co in zip(centroids_in, centroids_out)
                    )
                    if moved:
                        result["move_like"] = True

            # Copy: output has more objects than input
            if n_obj_out > n_obj_in:
                result["copy_like"] = True

            # Reflection: check if output is a reflection of input
            if np.array_equal(out, np.fliplr(inp)) or np.array_equal(out, np.flipud(inp)):
                result["reflect_like"] = True

            # Line extension: check if changed pixels form a line
            if result["pixels_changed"] and result["pixels_changed"] > 0:
                rows, cols = np.where(diff)
                if len(rows) > 2:
                    row_range = rows.max() - rows.min()
                    col_range = cols.max() - cols.min()
                    if row_range <= 1 or col_range <= 1:
                        result["extend_line_like"] = True

            # Multi-step composition heuristic
            flags = [result["recolor_like"], result["move_like"],
                     result["fill_hole_like"], result["copy_like"],
                     result["extend_line_like"]]
            if sum(flags) >= 2:
                result["composition_needed"] = True

    # Output object count relative to input
    if n_obj_out == 1 and n_obj_in > 1:
        result["count_like"] = True

    return result


def classify_operator_family(residual: Dict[str, Any]) -> str:
    """Classify the missing operator family from residual features."""
    if residual.get("crop_like"):
        return "crop_extract"
    if residual.get("move_like") and residual.get("copy_like"):
        return "copy_translate"
    if residual.get("move_like"):
        return "object_move"
    if residual.get("extend_line_like"):
        return "line_extend"
    if residual.get("fill_hole_like"):
        return "hole_fill"
    if residual.get("reflect_like"):
        return "symmetry_complete"
    if residual.get("repeat_like"):
        return "pattern_complete"
    if residual.get("recolor_like"):
        return "conditional_recolor"
    if residual.get("copy_like"):
        return "copy_translate"
    if residual.get("count_like"):
        return "count_objects"
    if residual.get("composition_needed"):
        return "multi_step_composition"

    # Fallback heuristics
    if not residual.get("same_shape"):
        out_h, out_w = residual["output_shape"]
        in_h, in_w = residual["input_shape"]
        if out_h < in_h or out_w < in_w:
            return "crop_extract"
        return "pattern_complete"

    if residual.get("pixels_changed") and residual["pixels_changed"] > 0:
        frac = residual.get("pixel_change_fraction", 0)
        if frac < 0.1:
            return "conditional_recolor"
        elif frac < 0.3:
            return "object_correspondence"
        else:
            return "multi_step_composition"

    return "unknown"


def get_applicable_views(grid: np.ndarray) -> List[Tuple[str, Any]]:
    """Get all applicable view programs for a grid."""
    views = []
    candidates = [
        ("identity", IdentityView()),
        ("crop_non_background", CropNonBackgroundView()),
        ("crop_bbox", CropBoundingBoxView()),
        ("remove_frame", RemoveFrameView()),
        ("extract_interior", ExtractInteriorView()),
        ("foreground_background", ForegroundBackgroundView()),
        ("normalize_bbox", NormalizeObjectBBoxView()),
    ]

    for color in range(1, 10):
        if color in set(grid.flatten().tolist()):
            candidates.append((f"color_layer_{color}", SplitColorLayerView(color)))

    for name, view in candidates:
        try:
            if view.can_apply(grid):
                views.append((name, view))
        except Exception:
            pass

    return views


def main():
    os.makedirs(OUT, exist_ok=True)
    challenges, solutions = load_arc_data()

    # Load task IDs from both sources
    task_ids = set()

    # From audit detail
    audit_path = FDAG_OUT / "adaptergenesis_zero_proposal_audit_detail.json"
    if audit_path.exists():
        with open(audit_path) as f:
            audit_data = json.load(f)
        for entry in audit_data:
            task_ids.add(entry["task_id"])

    # From selected replay tasks
    replay_path = FDAG_OUT / "selected_replay_tasks.csv"
    if replay_path.exists():
        with open(replay_path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                task_ids.add(row["task_id"])

    task_ids = sorted(task_ids)
    print(f"Operator gap audit: {len(task_ids)} tasks")

    rows = []
    for i, task_id in enumerate(task_ids):
        if task_id not in challenges:
            continue

        train_pairs, test_inputs, test_outputs = load_task(task_id, challenges, solutions)

        # Get applicable views
        inp0 = train_pairs[0][0]
        views = get_applicable_views(inp0)

        for view_name, view in views:
            try:
                lifted = view.lift_train_pairs(train_pairs)
                if lifted is None or len(lifted) == 0:
                    continue

                lift_succeeds = True
            except Exception:
                lift_succeeds = False
                lifted = None

            if not lift_succeeds or lifted is None:
                continue

            # Analyze residual on first lifted pair
            lifted_inp, lifted_out = lifted[0]
            residual = classify_residual(lifted_inp, lifted_out)
            op_family = classify_operator_family(residual)

            # Aggregate across all pairs for consistency check
            all_families = []
            for li, lo in lifted:
                r = classify_residual(li, lo)
                all_families.append(classify_operator_family(r))

            consistent_family = all_families[0] if len(set(all_families)) == 1 else "mixed"

            row = {
                "task_id": task_id,
                "view_program": view_name,
                "lift_succeeds": lift_succeeds,
                "n_objects_before": residual["n_objects_before"],
                "n_objects_after_lift": residual["n_objects_after"],
                "input_output_shape_relation": "same" if residual["same_shape"] else "different",
                "pixel_residual_type": op_family,
                "object_count_change": residual["object_count_change"],
                "color_count_change": residual["color_count_change"],
                "connected_component_change": residual["connected_component_change"],
                "bbox_change": str(residual.get("change_bbox", "")),
                "crop_like": residual["crop_like"],
                "copy_like": residual["copy_like"],
                "extend_line_like": residual["extend_line_like"],
                "fill_hole_like": residual["fill_hole_like"],
                "recolor_like": residual["recolor_like"],
                "move_like": residual["move_like"],
                "reflect_like": residual["reflect_like"],
                "repeat_like": residual["repeat_like"],
                "count_like": residual["count_like"],
                "composition_needed": residual["composition_needed"],
                "consistent_family": consistent_family,
            }
            rows.append(row)

        if (i + 1) % 20 == 0:
            print(f"  [{i+1}/{len(task_ids)}] processed", flush=True)

    # Write CSV
    csv_path = OUT / "operator_gap_after_lift.csv"
    if rows:
        keys = list(rows[0].keys())
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(rows)
    print(f"Saved {len(rows)} rows to {csv_path}")

    # Summary
    family_counts = Counter(r["consistent_family"] for r in rows)
    per_task_families = {}
    for r in rows:
        tid = r["task_id"]
        if tid not in per_task_families:
            per_task_families[tid] = set()
        per_task_families[tid].add(r["consistent_family"])

    # Best family per task (first non-unknown)
    best_family_per_task = Counter()
    for tid, families in per_task_families.items():
        families_no_unknown = families - {"unknown", "mixed"}
        if families_no_unknown:
            best_family_per_task[sorted(families_no_unknown)[0]] += 1
        elif "mixed" in families:
            best_family_per_task["multi_step_composition"] += 1
        else:
            best_family_per_task["unknown"] += 1

    md_path = OUT / "operator_gap_after_lift_summary.md"
    with open(md_path, "w") as f:
        f.write("# Operator Gap After Lift — Audit Summary\n\n")
        f.write(f"**Date:** 2026-06-21\n")
        f.write(f"**Tasks audited:** {len(task_ids)}\n")
        f.write(f"**Total view-task pairs:** {len(rows)}\n\n")

        f.write("## Missing Operator Family Distribution (all view-task pairs)\n\n")
        f.write("| Operator Family | Count | % |\n")
        f.write("|----------------|-------|---|\n")
        for fam, cnt in family_counts.most_common():
            pct = 100 * cnt / max(len(rows), 1)
            f.write(f"| {fam} | {cnt} | {pct:.1f}% |\n")

        f.write(f"\n## Best Missing Operator per Task\n\n")
        f.write("| Operator Family | Tasks | % |\n")
        f.write("|----------------|-------|---|\n")
        for fam, cnt in best_family_per_task.most_common():
            pct = 100 * cnt / max(len(task_ids), 1)
            f.write(f"| {fam} | {cnt} | {pct:.1f}% |\n")

        f.write(f"\n## Residual Feature Prevalence\n\n")
        flags = ["crop_like", "copy_like", "extend_line_like", "fill_hole_like",
                 "recolor_like", "move_like", "reflect_like", "repeat_like",
                 "count_like", "composition_needed"]
        f.write("| Feature | Count | % |\n")
        f.write("|---------|-------|---|\n")
        for flag in flags:
            cnt = sum(1 for r in rows if r.get(flag))
            pct = 100 * cnt / max(len(rows), 1)
            f.write(f"| {flag} | {cnt} | {pct:.1f}% |\n")

        f.write("\n## Interpretation\n\n")
        f.write("This audit classifies what operator family is needed for each\n")
        f.write("task-view pair where lifting succeeds but no operator is found.\n")
        f.write("The distribution guides which operator families to implement\n")
        f.write("first in OperatorGenesis.\n")

    print(f"Saved summary to {md_path}")


if __name__ == "__main__":
    main()
