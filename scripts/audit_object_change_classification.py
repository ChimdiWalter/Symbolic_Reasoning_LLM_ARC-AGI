#!/usr/bin/env python3.11
"""Audit object-change classification across ARC tasks.

Reports WHY _classify_kept_removed returns None and what the actual
object-level changes are (recolor, move, copy, shape-change, etc.).

Usage:
    python3.11 scripts/audit_object_change_classification.py \
      --max-tasks 200 \
      --output-dir outputs/object_change_classification
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reasoning_project.arc_adapter import load_arc_tasks
from reasoning_project.reasoning_engine import (
    _extract_objects_with_properties,
    _classify_kept_removed,
    _classify_unchanged_changed,
    _classify_kept_removed_extended,
)


def _detect_object_fate(
    obj: dict,
    inp: np.ndarray,
    out: np.ndarray,
    bg: int = 0,
) -> dict:
    """Classify what happened to a single input object in the output.

    Returns dict with change_type, evidence fields.
    """
    mask = obj["mask"]
    in_vals = inp[mask]
    out_vals = out[mask]

    same_pixels = np.array_equal(in_vals, out_vals)
    all_bg = np.all(out_vals == bg)
    any_nonzero = np.any(out_vals != bg)

    if same_pixels:
        return {"change_type": "kept", "evidence": "identical_pixels"}

    if all_bg:
        return {"change_type": "removed", "evidence": "all_background"}

    in_colors = set(int(v) for v in np.unique(in_vals) if v != bg)
    out_colors = set(int(v) for v in np.unique(out_vals) if v != bg)

    if in_colors != out_colors and any_nonzero:
        shape_preserved = True
        in_nonzero_mask = in_vals != bg
        out_nonzero_mask = out_vals != bg
        if np.array_equal(in_nonzero_mask, out_nonzero_mask):
            return {
                "change_type": "recolored",
                "evidence": "same_shape_different_colors",
                "in_colors": sorted(in_colors),
                "out_colors": sorted(out_colors),
            }
        else:
            return {
                "change_type": "changed",
                "evidence": "colors_and_shape_differ",
                "in_colors": sorted(in_colors),
                "out_colors": sorted(out_colors),
            }

    return {
        "change_type": "changed",
        "evidence": "pixel_differences",
        "n_diff": int(np.sum(in_vals != out_vals)),
        "n_total": int(mask.sum()),
    }


def _find_object_in_output(
    obj: dict,
    inp: np.ndarray,
    out: np.ndarray,
    bg: int = 0,
    sim_threshold: float = 0.7,
) -> dict | None:
    """Try to find this input object somewhere else in the output.

    Returns displacement info if found, None otherwise.
    """
    mask = obj["mask"]
    rows, cols = np.where(mask)
    if len(rows) == 0:
        return None
    r0, c0 = int(rows.min()), int(cols.min())
    r1, c1 = int(rows.max()), int(cols.max())
    sh, sw = r1 - r0 + 1, c1 - c0 + 1

    local_mask = mask[r0:r0 + sh, c0:c0 + sw]
    local_colors = inp[r0:r0 + sh, c0:c0 + sw]

    H, W = out.shape
    best_sim = 0.0
    best_pos = None

    for r in range(max(0, r0 - 10), min(H - sh + 1, r0 + 11)):
        for c in range(max(0, c0 - 10), min(W - sw + 1, c0 + 11)):
            if r == r0 and c == c0:
                continue
            patch = out[r:r + sh, c:c + sw]
            n = int(local_mask.sum())
            if n == 0:
                continue
            matched = int(np.sum((patch == local_colors) & local_mask))
            sim = matched / n
            if sim > best_sim:
                best_sim = sim
                best_pos = (r, c)

    if best_pos is None:
        for r in range(H - sh + 1):
            for c in range(W - sw + 1):
                if r == r0 and c == c0:
                    continue
                patch = out[r:r + sh, c:c + sw]
                n = int(local_mask.sum())
                if n == 0:
                    continue
                matched = int(np.sum((patch == local_colors) & local_mask))
                sim = matched / n
                if sim > best_sim:
                    best_sim = sim
                    best_pos = (r, c)

    if best_pos is not None and best_sim >= sim_threshold:
        dr = best_pos[0] - r0
        dc = best_pos[1] - c0
        return {
            "dest": best_pos,
            "displacement": (dr, dc),
            "similarity": round(best_sim, 3),
            "exact": best_sim >= 0.99,
        }

    # Try color-blind match (shape only, any colors)
    best_shape_sim = 0.0
    best_shape_pos = None
    for r in range(H - sh + 1):
        for c in range(W - sw + 1):
            if r == r0 and c == c0:
                continue
            patch = out[r:r + sh, c:c + sw]
            n = int(local_mask.sum())
            if n == 0:
                continue
            patch_nonzero = patch != bg
            shape_matched = int(np.sum(patch_nonzero & local_mask))
            sim = shape_matched / n
            if sim > best_shape_sim:
                best_shape_sim = sim
                best_shape_pos = (r, c)

    if best_shape_pos is not None and best_shape_sim >= sim_threshold:
        dr = best_shape_pos[0] - r0
        dc = best_shape_pos[1] - c0
        return {
            "dest": best_shape_pos,
            "displacement": (dr, dc),
            "similarity": round(best_shape_sim, 3),
            "exact": False,
            "color_blind": True,
        }

    return None


def _detect_bg(grid: np.ndarray) -> int:
    vals, counts = np.unique(grid, return_counts=True)
    return int(vals[np.argmax(counts)])


def audit_task_pair(
    task_id: str,
    pair_idx: int,
    inp: np.ndarray,
    out: np.ndarray,
) -> dict:
    """Audit one training pair for object-change classification."""
    result = {
        "task_id": task_id,
        "pair_index": pair_idx,
        "same_size": inp.shape == out.shape,
    }

    if not result["same_size"]:
        result["classifier_result"] = "size_change"
        result["failure_reason"] = "different_grid_sizes"
        result["category"] = "size_change"
        result["kr_result"] = "None"
        result["uc_result"] = "None"
        result["ext_result"] = "None"
        result["n_objects_in"] = 0
        result["n_objects_out"] = 0
        result["n_kept"] = 0
        result["n_removed"] = 0
        result["n_recolored"] = 0
        result["n_changed"] = 0
        result["n_moved"] = 0
        result["n_moved_recolored"] = 0
        result["n_copied"] = 0
        result["n_disappeared"] = 0
        return result

    bg = _detect_bg(inp)
    objects = _extract_objects_with_properties(inp, bg=bg)
    result["n_objects_in"] = len(objects)

    out_objects = _extract_objects_with_properties(out, bg=bg)
    result["n_objects_out"] = len(out_objects)

    # Run existing classifiers
    kr = _classify_kept_removed(objects, inp, out)
    result["kr_result"] = "success" if kr is not None else "None"

    uc = _classify_unchanged_changed(objects, inp, out)
    result["uc_result"] = "success" if uc is not None else "None"

    ext = _classify_kept_removed_extended(objects, inp, out)
    result["ext_result"] = ext[2] if ext is not None else "None"

    # Per-object fate analysis
    fates = []
    for i, obj in enumerate(objects):
        fate = _detect_object_fate(obj, inp, out, bg)
        fate["obj_idx"] = i
        fates.append(fate)

    type_counts = Counter(f["change_type"] for f in fates)
    result["n_kept"] = type_counts.get("kept", 0)
    result["n_removed"] = type_counts.get("removed", 0)
    result["n_recolored"] = type_counts.get("recolored", 0)
    result["n_changed"] = type_counts.get("changed", 0)

    # For removed/changed objects, try to find them elsewhere in output
    n_moved = 0
    n_moved_recolored = 0
    n_copied = 0
    n_disappeared = 0
    for fate in fates:
        if fate["change_type"] in ("removed", "changed"):
            obj = objects[fate["obj_idx"]]
            found = _find_object_in_output(obj, inp, out, bg)
            if found is not None:
                if fate["change_type"] == "removed":
                    # Object removed from original position but found elsewhere
                    out_at_orig = out[obj["mask"]]
                    if np.all(out_at_orig == bg):
                        n_moved += 1
                        fate["change_type"] = "moved"
                        fate["displacement"] = found["displacement"]
                    else:
                        n_copied += 1
                        fate["change_type"] = "copied"
                        fate["displacement"] = found["displacement"]
                elif found.get("color_blind"):
                    n_moved_recolored += 1
                    fate["change_type"] = "moved_recolored"
                    fate["displacement"] = found["displacement"]
                else:
                    n_moved += 1
                    fate["change_type"] = "moved"
                    fate["displacement"] = found["displacement"]
            else:
                if fate["change_type"] == "removed":
                    n_disappeared += 1

    result["n_moved"] = n_moved
    result["n_moved_recolored"] = n_moved_recolored
    result["n_copied"] = n_copied
    result["n_disappeared"] = n_disappeared

    # Classify the overall pair change category
    if result["kr_result"] == "success":
        result["category"] = "zeroing_case"
    elif n_moved > 0 and result["n_removed"] > 0:
        result["category"] = "move_case"
    elif n_moved_recolored > 0:
        result["category"] = "copy_and_recolor_case"
    elif n_copied > 0:
        result["category"] = "copy_case"
    elif result["n_recolored"] > 0 and result["n_removed"] == 0:
        result["category"] = "recolor_case"
    elif result["n_recolored"] > 0 and result["n_removed"] > 0:
        result["category"] = "mixed_recolor_remove"
    elif result["n_changed"] > 0:
        if result["n_kept"] > 0:
            result["category"] = "partial_change_case"
        else:
            result["category"] = "global_color_map_case"
    elif result["n_objects_in"] == 0:
        result["category"] = "perception_failure"
    elif len(objects) < 2:
        result["category"] = "single_object"
    else:
        result["category"] = "unknown"

    result["failure_reason"] = _diagnose_kr_failure(result, fates)

    return result


def _diagnose_kr_failure(result: dict, fates: list) -> str | None:
    if result["kr_result"] == "success":
        return None
    if not result["same_size"]:
        return "different_grid_sizes"
    if result["n_objects_in"] == 0:
        return "no_objects_extracted"
    if result["n_objects_in"] == 1:
        return "single_object"

    n_kept = result["n_kept"]
    n_removed = result["n_removed"]
    n_recolored = result["n_recolored"]
    n_changed = result["n_changed"]

    if n_removed == 0 and n_kept == result["n_objects_in"]:
        return "all_objects_present_in_output"
    if n_removed == result["n_objects_in"]:
        return "all_objects_removed"
    if n_recolored > 0 and n_removed == 0:
        return "objects_recolored_not_removed"
    if n_changed > 0 and n_removed == 0 and n_recolored == 0:
        return "objects_changed_not_removed_or_recolored"
    if n_kept == 0 and n_removed == 0:
        return "no_clean_kept_removed_split"

    return "mixed_fates"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-tasks", type=int, default=200)
    parser.add_argument("--output-dir", default="outputs/object_change_classification")
    parser.add_argument("--data-dir", default="data/arc")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    tasks = load_arc_tasks(args.data_dir, split="training")
    tasks = tasks[:args.max_tasks]
    print(f"Auditing {len(tasks)} tasks...")

    all_results = []
    t0 = time.time()

    for ti, task in enumerate(tasks):
        for pi, ex in enumerate(task.train):
            result = audit_task_pair(task.task_id, pi, ex.input_grid, ex.output_grid)
            all_results.append(result)
        if (ti + 1) % 50 == 0:
            print(f"  [{ti+1}/{len(tasks)}] processed...")

    elapsed = time.time() - t0

    # Write CSV
    fieldnames = [
        "task_id", "pair_index", "same_size", "n_objects_in", "n_objects_out",
        "kr_result", "uc_result", "ext_result",
        "n_kept", "n_removed", "n_recolored", "n_changed",
        "n_moved", "n_moved_recolored", "n_copied", "n_disappeared",
        "category", "failure_reason",
    ]
    with open(output_dir / "audit.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in all_results:
            writer.writerow(r)

    # Aggregate stats
    n_total = len(all_results)
    n_kr_none = sum(1 for r in all_results if r.get("kr_result", "None") == "None")
    n_uc_none = sum(1 for r in all_results if r.get("uc_result", "None") == "None")
    n_ext_none = sum(1 for r in all_results if r.get("ext_result", "None") == "None")

    category_counts = Counter(r["category"] for r in all_results)
    failure_counts = Counter(r.get("failure_reason") for r in all_results if r.get("failure_reason"))

    # Task-level aggregation
    task_categories = {}
    for r in all_results:
        tid = r["task_id"]
        if tid not in task_categories:
            task_categories[tid] = []
        task_categories[tid].append(r["category"])

    task_kr_none = sum(
        1 for tid, cats in task_categories.items()
        if all(c != "zeroing_case" for c in cats)
    )

    # Write summary
    with open(output_dir / "audit_summary.md", "w") as f:
        f.write("# Object-Change Classification Audit\n\n")
        f.write(f"- Tasks audited: {len(tasks)}\n")
        f.write(f"- Training pairs audited: {n_total}\n")
        f.write(f"- Elapsed: {elapsed:.1f}s\n\n")
        f.write("## Existing Classifier Results (per pair)\n\n")
        f.write(f"- `_classify_kept_removed` returns None: **{n_kr_none}/{n_total} ({100*n_kr_none/n_total:.1f}%)**\n")
        f.write(f"- `_classify_unchanged_changed` returns None: {n_uc_none}/{n_total} ({100*n_uc_none/n_total:.1f}%)\n")
        f.write(f"- `_classify_kept_removed_extended` returns None: {n_ext_none}/{n_total} ({100*n_ext_none/n_total:.1f}%)\n\n")
        f.write(f"## Task-Level: kr=None for all pairs: **{task_kr_none}/{len(tasks)} ({100*task_kr_none/len(tasks):.1f}%)**\n\n")
        f.write("## Pair-Level Change Categories\n\n")
        f.write("| Category | Count | % |\n")
        f.write("|----------|-------|---|\n")
        for cat, cnt in category_counts.most_common():
            f.write(f"| {cat} | {cnt} | {100*cnt/n_total:.1f}% |\n")
        f.write(f"\n## Failure Reasons (why kr=None)\n\n")
        f.write("| Reason | Count | % of failures |\n")
        f.write("|--------|-------|---------------|\n")
        for reason, cnt in failure_counts.most_common():
            f.write(f"| {reason} | {cnt} | {100*cnt/n_kr_none:.1f}% |\n")

    # Write taxonomy JSON
    taxonomy = {
        "total_pairs": n_total,
        "total_tasks": len(tasks),
        "kr_none_pairs": n_kr_none,
        "kr_none_tasks": task_kr_none,
        "categories": dict(category_counts),
        "failure_reasons": dict(failure_counts),
    }
    with open(output_dir / "failure_taxonomy.json", "w") as f:
        json.dump(taxonomy, f, indent=2)

    print(f"\nDone in {elapsed:.1f}s. Results in {output_dir}/")
    print(f"  kr=None: {n_kr_none}/{n_total} pairs ({100*n_kr_none/n_total:.1f}%)")
    print(f"  kr=None tasks: {task_kr_none}/{len(tasks)} ({100*task_kr_none/len(tasks):.1f}%)")
    print(f"\nTop categories:")
    for cat, cnt in category_counts.most_common(8):
        print(f"  {cat}: {cnt} ({100*cnt/n_total:.1f}%)")


if __name__ == "__main__":
    main()
