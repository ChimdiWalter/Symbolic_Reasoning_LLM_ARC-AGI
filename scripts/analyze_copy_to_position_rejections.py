"""Analyze rejected copy-to-position ARC tasks to determine anchor types.

For each of the ~30 rejected copy-to-position tasks, this script:
1. Loads the actual ARC task data and the rejection metadata.
2. Extracts objects and classifies them as kept/removed using the best_property.
3. Finds where each removed object appears in the output via sliding-window matching.
4. Computes displacement vectors and determines the anchor type:
   - constant_displacement_failure
   - marker_relative_destination
   - converge_to_point
   - same_color_object_correspondence
   - same_shape_object_correspondence
   - boundary_or_corner_anchored_destination
   - separator_cell_relative_destination
   - unknown

Outputs:
  - rejection_taxonomy.csv
  - rejection_taxonomy.md
  - anchor_candidate_summary.json
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# Make the project importable
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reasoning_project.arc_adapter import load_arc_tasks
from reasoning_project.reasoning_engine import (
    _extract_objects_with_properties,
    _get_property_value,
)


# ───────────────────────────────────────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────────────────────────────────────

def _find_object_in_output(
    obj: Dict[str, Any],
    inp: np.ndarray,
    out: np.ndarray,
) -> Optional[Tuple[int, int, float]]:
    """Slide the object's local mask over the output grid and return
    (dest_r, dest_c, similarity) for the best match, or None."""
    local = obj["local_mask"]
    oh, ow = local.shape
    pixels_in = inp[obj["bbox"][0]:obj["bbox"][2] + 1,
                     obj["bbox"][1]:obj["bbox"][3] + 1].copy()
    pixels_in[~local] = -1

    best_sim = 0.0
    best_pos: Optional[Tuple[int, int]] = None
    out_h, out_w = out.shape

    for r in range(out_h - oh + 1):
        for c in range(out_w - ow + 1):
            region = out[r:r + oh, c:c + ow]
            match_pixels = pixels_in[local]
            region_pixels = region[local]
            if len(match_pixels) == 0:
                continue
            sim = float(np.mean(match_pixels == region_pixels))
            if sim > best_sim and sim > 0.5:
                best_sim = sim
                best_pos = (r, c)

    if best_pos is None:
        return None
    return (*best_pos, best_sim)


def _displacement(obj: Dict, dest_r: int, dest_c: int) -> Tuple[int, int]:
    """Compute displacement from object bbox top-left to dest."""
    return (dest_r - obj["bbox"][0], dest_c - obj["bbox"][1])


def _bbox_center(obj: Dict) -> Tuple[float, float]:
    return (obj["center_r"], obj["center_c"])


def _dest_center(obj: Dict, dest_r: int, dest_c: int) -> Tuple[float, float]:
    oh, ow = obj["local_mask"].shape
    return (dest_r + oh / 2.0, dest_c + ow / 2.0)


def _shapes_match(obj_a: Dict, obj_b: Dict) -> bool:
    """Check if two objects have the same local mask shape."""
    if obj_a["local_mask"].shape != obj_b["local_mask"].shape:
        return False
    return bool(np.array_equal(obj_a["local_mask"], obj_b["local_mask"]))


def _near_boundary(dest_r: int, dest_c: int, oh: int, ow: int,
                   grid_h: int, grid_w: int, margin: int = 2) -> bool:
    """Check if the destination is near a grid boundary or corner."""
    near_top = dest_r <= margin
    near_bottom = (dest_r + oh) >= grid_h - margin
    near_left = dest_c <= margin
    near_right = (dest_c + ow) >= grid_w - margin
    return near_top or near_bottom or near_left or near_right


def _detect_separator(grid: np.ndarray) -> Optional[Dict[str, Any]]:
    """Detect a full-row or full-column separator (constant non-background color
    spanning the entire width or height)."""
    h, w = grid.shape
    # Check rows
    for r in range(h):
        row = grid[r, :]
        vals = set(row.tolist())
        if len(vals) == 1 and 0 not in vals:
            return {"type": "row", "index": r, "color": row[0]}
    # Check columns
    for c in range(w):
        col = grid[:, c]
        vals = set(col.tolist())
        if len(vals) == 1 and 0 not in vals:
            return {"type": "col", "index": c, "color": col[0]}
    return None


# ───────────────────────────────────────────────────────────────────────────
# Per-task analysis
# ───────────────────────────────────────────────────────────────────────────

def analyze_task(
    task,
    best_property: str,
    keep_when_true: bool,
) -> Dict[str, Any]:
    """Analyze a single rejected task and return anchor evidence."""
    all_displacements: List[List[Tuple[int, int]]] = []  # per example
    all_dest_positions: List[List[Tuple[int, int]]] = []  # per example
    all_kept_objects: List[List[Dict]] = []
    all_removed_objects: List[List[Dict]] = []
    all_movements: List[List[Dict]] = []  # per example

    for ex in task.train:
        inp = ex.input_grid
        out = ex.output_grid
        if out is None:
            continue

        objects = _extract_objects_with_properties(inp)
        if len(objects) < 2:
            continue

        kept = [o for o in objects if _get_property_value(o, best_property) == keep_when_true]
        removed = [o for o in objects if _get_property_value(o, best_property) != keep_when_true]

        if not kept or not removed:
            continue

        ex_displacements = []
        ex_dest_positions = []
        ex_movements = []

        for robj in removed:
            result = _find_object_in_output(robj, inp, out)
            if result is not None:
                dest_r, dest_c, sim = result
                dr, dc = _displacement(robj, dest_r, dest_c)
                ex_displacements.append((dr, dc))
                ex_dest_positions.append((dest_r, dest_c))
                ex_movements.append({
                    "src_bbox": robj["bbox"],
                    "dest": (dest_r, dest_c),
                    "displacement": (dr, dc),
                    "similarity": sim,
                    "primary_color": robj["primary_color"],
                    "shape_group_id": robj.get("shape_group_id", -1),
                    "local_mask_shape": robj["local_mask"].shape,
                    "obj": robj,
                })
            else:
                ex_movements.append({
                    "src_bbox": robj["bbox"],
                    "dest": None,
                    "displacement": None,
                    "similarity": 0.0,
                    "primary_color": robj["primary_color"],
                    "shape_group_id": robj.get("shape_group_id", -1),
                    "local_mask_shape": robj["local_mask"].shape,
                    "obj": robj,
                })

        all_displacements.append(ex_displacements)
        all_dest_positions.append(ex_dest_positions)
        all_kept_objects.append(kept)
        all_removed_objects.append(removed)
        all_movements.append(ex_movements)

    if not all_movements:
        return {
            "anchor_type": "unknown",
            "anchor_evidence": "no_training_examples_analyzable",
            "n_removed": 0,
            "n_kept": 0,
            "displacements_consistent_across_examples": False,
        }

    # Flatten displacements across all examples
    flat_disp = [d for ex_d in all_displacements for d in ex_d]
    flat_dest = [d for ex_d in all_dest_positions for d in ex_d]
    total_removed = sum(len(ex) for ex in all_removed_objects)
    total_kept = sum(len(ex) for ex in all_kept_objects)
    total_found = len(flat_disp)

    # Check 1: Are all displacements constant?
    displacements_consistent = False
    if flat_disp and len(set(flat_disp)) == 1:
        displacements_consistent = True

    # Check cross-example consistency
    cross_example_consistent = True
    if len(all_displacements) > 1:
        disp_sets = [set(ex_d) for ex_d in all_displacements if ex_d]
        if len(disp_sets) > 1:
            cross_example_consistent = all(s == disp_sets[0] for s in disp_sets[1:])

    # ---- Anchor classification ----

    anchor_type = "unknown"
    anchor_evidence = ""

    # 1. Constant displacement (already tried and failed)
    if displacements_consistent and total_found > 0:
        anchor_type = "constant_displacement_failure"
        anchor_evidence = f"all_displacements={flat_disp[0]}, but train_fit failed"

    # 2. Converge to single point
    elif flat_dest and len(set(flat_dest)) == 1:
        anchor_type = "converge_to_point"
        anchor_evidence = f"all_destinations={flat_dest[0]}"

    # 3. Marker-relative destination: check if dest is near a kept object's bbox
    elif total_found > 0:
        marker_hits = 0
        marker_details = []
        for ex_idx, ex_mvts in enumerate(all_movements):
            kept = all_kept_objects[ex_idx] if ex_idx < len(all_kept_objects) else []
            for mvt in ex_mvts:
                if mvt["dest"] is None:
                    continue
                dest_r, dest_c = mvt["dest"]
                oh, ow = mvt["local_mask_shape"]
                dest_cr = dest_r + oh / 2.0
                dest_cc = dest_c + ow / 2.0
                for kobj in kept:
                    kcr, kcc = _bbox_center(kobj)
                    kr1, kc1, kr2, kc2 = kobj["bbox"]
                    # Check if destination is within the kept object's bbox
                    # (expanded by a small margin)
                    margin = max(oh, ow, kobj["bbox_h"], kobj["bbox_w"]) + 2
                    if (abs(dest_cr - kcr) <= margin and
                            abs(dest_cc - kcc) <= margin):
                        marker_hits += 1
                        marker_details.append({
                            "removed_color": mvt["primary_color"],
                            "kept_color": kobj["primary_color"],
                            "kept_center": (kcr, kcc),
                            "dest_center": (dest_cr, dest_cc),
                            "offset": (dest_cr - kcr, dest_cc - kcc),
                        })
                        break

        if marker_hits >= total_found * 0.8 and marker_hits > 0:
            # Sub-classify: color or shape correspondence?
            color_match = sum(
                1 for d in marker_details
                if d["removed_color"] == d["kept_color"]
            )
            shape_match_count = 0
            for ex_idx, ex_mvts in enumerate(all_movements):
                kept = all_kept_objects[ex_idx] if ex_idx < len(all_kept_objects) else []
                for mvt in ex_mvts:
                    if mvt["dest"] is None or mvt["obj"] is None:
                        continue
                    for kobj in kept:
                        if _shapes_match(mvt["obj"], kobj):
                            shape_match_count += 1
                            break

            if color_match >= total_found * 0.8:
                anchor_type = "same_color_object_correspondence"
                anchor_evidence = (
                    f"{color_match}/{total_found} moved objects share color with "
                    f"their nearest kept object"
                )
            elif shape_match_count >= total_found * 0.8:
                anchor_type = "same_shape_object_correspondence"
                anchor_evidence = (
                    f"{shape_match_count}/{total_found} moved objects share shape "
                    f"with their nearest kept object"
                )
            else:
                # Check if the offsets from kept objects are consistent
                offsets = [
                    (round(d["offset"][0], 1), round(d["offset"][1], 1))
                    for d in marker_details
                ]
                if offsets and len(set(offsets)) <= 2:
                    anchor_type = "marker_relative_destination"
                    anchor_evidence = (
                        f"destinations near kept objects with consistent "
                        f"offset(s): {sorted(set(offsets))}"
                    )
                else:
                    anchor_type = "marker_relative_destination"
                    anchor_evidence = (
                        f"{marker_hits}/{total_found} destinations near kept "
                        f"objects; offsets vary: {sorted(set(offsets))[:5]}"
                    )

    # 4. Boundary/corner anchored
    if anchor_type == "unknown" and total_found > 0:
        boundary_hits = 0
        for ex_idx, ex_mvts in enumerate(all_movements):
            inp = task.train[ex_idx].input_grid
            grid_h, grid_w = inp.shape
            for mvt in ex_mvts:
                if mvt["dest"] is None:
                    continue
                dest_r, dest_c = mvt["dest"]
                oh, ow = mvt["local_mask_shape"]
                if _near_boundary(dest_r, dest_c, oh, ow, grid_h, grid_w):
                    boundary_hits += 1
        if boundary_hits >= total_found * 0.8:
            anchor_type = "boundary_or_corner_anchored_destination"
            anchor_evidence = (
                f"{boundary_hits}/{total_found} destinations near grid boundaries"
            )

    # 5. Separator-relative
    if anchor_type == "unknown" and total_found > 0:
        separator_hits = 0
        for ex_idx in range(len(all_movements)):
            inp = task.train[ex_idx].input_grid
            sep = _detect_separator(inp)
            if sep is None:
                continue
            for mvt in all_movements[ex_idx]:
                if mvt["dest"] is None:
                    continue
                dest_r, dest_c = mvt["dest"]
                if sep["type"] == "row" and abs(dest_r - sep["index"]) <= 3:
                    separator_hits += 1
                elif sep["type"] == "col" and abs(dest_c - sep["index"]) <= 3:
                    separator_hits += 1
        if separator_hits >= total_found * 0.5 and separator_hits > 0:
            anchor_type = "separator_cell_relative_destination"
            anchor_evidence = (
                f"{separator_hits}/{total_found} destinations near separator "
                f"structure"
            )

    # 6. Converge to point (looser check across examples)
    if anchor_type == "unknown" and flat_dest:
        mean_r = np.mean([d[0] for d in flat_dest])
        mean_c = np.mean([d[1] for d in flat_dest])
        max_dist = max(
            abs(d[0] - mean_r) + abs(d[1] - mean_c) for d in flat_dest
        )
        if max_dist <= 3:
            anchor_type = "converge_to_point"
            anchor_evidence = (
                f"destinations cluster around ({mean_r:.1f}, {mean_c:.1f}), "
                f"max_deviation={max_dist:.1f}"
            )

    return {
        "anchor_type": anchor_type,
        "anchor_evidence": anchor_evidence,
        "n_removed": total_removed,
        "n_kept": total_kept,
        "n_found_in_output": total_found,
        "displacements_consistent_across_examples": cross_example_consistent,
        "flat_displacements": [list(d) for d in flat_disp],
        "flat_destinations": [list(d) for d in flat_dest],
    }


# ───────────────────────────────────────────────────────────────────────────
# Main
# ───────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze rejected copy-to-position tasks to determine anchor types.",
    )
    parser.add_argument(
        "--data-dir",
        default="data/arc",
        help="Root directory for ARC dataset (default: data/arc)",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs/operator_reasoning_phase/marker_relative",
        help="Output directory (default: outputs/operator_reasoning_phase/marker_relative)",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    data_dir = project_root / args.data_dir
    output_dir = project_root / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    # ---- Load data ----
    cases_csv_path = project_root / "outputs" / "operator_reasoning_phase" / "copy_to_position_cases.csv"
    rejected_jsonl_path = (
        project_root / "outputs" / "operator_reasoning_phase"
        / "copy_to_position_real" / "rejected_tasks.jsonl"
    )

    # Load cases CSV
    cases_by_id: Dict[str, Dict[str, str]] = {}
    with open(cases_csv_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cases_by_id[row["task_id"]] = dict(row)

    # Load rejected tasks
    rejected: Dict[str, str] = {}
    with open(rejected_jsonl_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            rejected[rec["task_id"]] = rec["reason"]

    print(f"Loaded {len(cases_by_id)} cases and {len(rejected)} rejected tasks.")

    # Load ARC tasks
    print(f"Loading ARC tasks from {data_dir} ...")
    all_tasks = load_arc_tasks(str(data_dir), split="training")
    tasks_dict = {t.task_id: t for t in all_tasks}
    print(f"Loaded {len(tasks_dict)} ARC tasks.")

    # ---- Analyze each rejected task ----
    taxonomy_rows: List[Dict[str, Any]] = []
    anchor_candidates: Dict[str, Any] = {}

    for task_id, reason in sorted(rejected.items()):
        case = cases_by_id.get(task_id)
        if case is None:
            print(f"  WARNING: task {task_id} not in cases CSV, skipping.")
            continue
        task = tasks_dict.get(task_id)
        if task is None:
            print(f"  WARNING: task {task_id} not found in ARC dataset, skipping.")
            continue

        best_property = case["best_property"]

        # Determine keep_when_true: the property value that selects "kept" objects.
        # In the CSV, "kept" is the count of objects where property=True that are
        # retained.  We need to figure out the polarity.  The convention is that
        # best_property=True → kept (selector side).  But we verify by checking the
        # first training example.
        keep_when_true = True  # default assumption
        ex0 = task.train[0]
        objects_0 = _extract_objects_with_properties(ex0.input_grid)
        if ex0.output_grid is not None and len(objects_0) >= 2:
            true_objs = [o for o in objects_0 if _get_property_value(o, best_property)]
            false_objs = [o for o in objects_0 if not _get_property_value(o, best_property)]
            if true_objs and false_objs:
                # Check which set is "kept" in the output
                true_in_output = 0
                false_in_output = 0
                for o in true_objs:
                    out_vals = ex0.output_grid[o["mask"]]
                    if np.any(out_vals != 0):
                        true_in_output += 1
                for o in false_objs:
                    out_vals = ex0.output_grid[o["mask"]]
                    if np.any(out_vals != 0):
                        false_in_output += 1
                # The side with more surviving objects is "kept"
                if false_in_output > true_in_output:
                    keep_when_true = False

        print(f"  Analyzing {task_id} (property={best_property}, "
              f"keep_when_true={keep_when_true}) ...")

        result = analyze_task(task, best_property, keep_when_true)

        taxonomy_rows.append({
            "task_id": task_id,
            "rejection_reason": reason,
            "anchor_type": result["anchor_type"],
            "n_removed": result["n_removed"],
            "n_kept": result["n_kept"],
            "best_property": best_property,
            "movement_pattern": case.get("movement_pattern", ""),
            "displacements_consistent_across_examples": result[
                "displacements_consistent_across_examples"
            ],
            "anchor_evidence": result["anchor_evidence"],
        })

        anchor_candidates[task_id] = {
            "rejection_reason": reason,
            "best_property": best_property,
            "keep_when_true": keep_when_true,
            "anchor_type": result["anchor_type"],
            "anchor_evidence": result["anchor_evidence"],
            "n_removed": result["n_removed"],
            "n_kept": result["n_kept"],
            "n_found_in_output": result.get("n_found_in_output", 0),
            "displacements": result.get("flat_displacements", []),
            "destinations": result.get("flat_destinations", []),
            "cross_example_consistent": result[
                "displacements_consistent_across_examples"
            ],
        }

    # ---- Write outputs ----

    # 1. CSV
    csv_path = output_dir / "rejection_taxonomy.csv"
    csv_fields = [
        "task_id", "rejection_reason", "anchor_type", "n_removed", "n_kept",
        "best_property", "movement_pattern",
        "displacements_consistent_across_examples", "anchor_evidence",
    ]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields)
        writer.writeheader()
        for row in taxonomy_rows:
            writer.writerow(row)
    print(f"\nWrote {len(taxonomy_rows)} rows to {csv_path}")

    # 2. JSON
    json_path = output_dir / "anchor_candidate_summary.json"
    with open(json_path, "w") as f:
        json.dump(anchor_candidates, f, indent=2, default=str)
    print(f"Wrote {json_path}")

    # 3. Markdown summary
    md_path = output_dir / "rejection_taxonomy.md"
    anchor_counts = Counter(r["anchor_type"] for r in taxonomy_rows)
    total = len(taxonomy_rows)

    lines = [
        "# Rejected Copy-to-Position: Anchor Type Taxonomy",
        "",
        f"**Total rejected tasks analyzed:** {total}",
        "",
        "## Anchor Type Distribution",
        "",
        "| Anchor Type | Count | % |",
        "|---|---|---|",
    ]
    for atype, cnt in anchor_counts.most_common():
        pct = 100.0 * cnt / max(total, 1)
        lines.append(f"| {atype} | {cnt} | {pct:.1f}% |")

    lines.append("")
    lines.append("## Per-Task Details")
    lines.append("")

    for row in taxonomy_rows:
        lines.append(f"### {row['task_id']}")
        lines.append(f"- **Rejection reason:** {row['rejection_reason']}")
        lines.append(f"- **Anchor type:** {row['anchor_type']}")
        lines.append(f"- **Best property:** {row['best_property']}")
        lines.append(f"- **Movement pattern:** {row['movement_pattern']}")
        lines.append(f"- **Kept/Removed:** {row['n_kept']}/{row['n_removed']}")
        lines.append(
            f"- **Cross-example consistent:** "
            f"{row['displacements_consistent_across_examples']}"
        )
        lines.append(f"- **Evidence:** {row['anchor_evidence']}")
        lines.append("")

    lines.append("## Analysis Notes")
    lines.append("")
    lines.append(
        "Tasks classified as `marker_relative_destination` are strong candidates "
        "for a marker-relative copy-to-position operator that anchors the "
        "destination to a kept object's position rather than using an absolute "
        "or constant displacement."
    )
    lines.append("")
    lines.append(
        "Tasks classified as `same_color_object_correspondence` or "
        "`same_shape_object_correspondence` suggest the destination is "
        "determined by matching removed objects to kept objects via color or "
        "shape, respectively."
    )
    lines.append("")

    with open(md_path, "w") as f:
        f.write("\n".join(lines))
    print(f"Wrote {md_path}")

    # Final summary to stdout
    print("\n" + "=" * 60)
    print("ANCHOR TYPE SUMMARY")
    print("=" * 60)
    for atype, cnt in anchor_counts.most_common():
        print(f"  {atype:45s} {cnt:3d}  ({100.0 * cnt / max(total, 1):.0f}%)")
    print(f"  {'TOTAL':45s} {total:3d}")


if __name__ == "__main__":
    main()
