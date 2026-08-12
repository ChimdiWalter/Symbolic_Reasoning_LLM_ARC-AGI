#!/usr/bin/env python3.11
"""Analyze many-to-few grouping structure in rejected ARC tasks.

For tasks where len(removed) > len(kept) across training pairs, VDPL cannot
find an injective (1-to-1) source->destination mapping. This script diagnoses
the grouping structure of those tasks to inform potential future strategies:

- Do the removed objects share a common color?
- Do they share a common shape?
- Are they spatially grouped (same row/column, proximity cluster)?
- Are they enclosed by a frame / separator?
- Are they connected components of a larger pattern?

Usage:
    python3.11 scripts/analyze_many_to_few_grouping_failures.py
    python3.11 scripts/analyze_many_to_few_grouping_failures.py --rejected-csv <path>
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reasoning_project.arc_adapter import load_arc_tasks
from reasoning_project.reasoning_engine import (
    _extract_objects_with_properties,
    _classify_kept_removed,
)


# ═══════════════════════════════════════════════════════════════════════════
# GROUPING ANALYZERS
# ═══════════════════════════════════════════════════════════════════════════

def analyze_color_grouping(
    objects: List[Dict[str, Any]],
    removed_idx: List[int],
    kept_idx: List[int],
) -> Dict[str, Any]:
    """Check if removed objects share a common color or color pattern."""
    removed_colors = [objects[i]["primary_color"] for i in removed_idx]
    kept_colors = [objects[i]["primary_color"] for i in kept_idx]

    removed_color_set = set(removed_colors)
    kept_color_set = set(kept_colors)

    removed_counter = Counter(removed_colors)
    dominant_removed = removed_counter.most_common(1)[0] if removed_counter else (None, 0)

    return {
        "removed_colors": sorted(removed_color_set),
        "kept_colors": sorted(kept_color_set),
        "color_overlap": sorted(removed_color_set & kept_color_set),
        "removed_unique_colors": sorted(removed_color_set - kept_color_set),
        "all_same_color": len(removed_color_set) == 1,
        "dominant_color": dominant_removed[0],
        "dominant_count": dominant_removed[1],
        "n_removed": len(removed_idx),
    }


def analyze_shape_grouping(
    objects: List[Dict[str, Any]],
    removed_idx: List[int],
    kept_idx: List[int],
) -> Dict[str, Any]:
    """Check if removed objects share a common shape."""
    # Group by shape (local_mask equality)
    shape_groups: Dict[int, List[int]] = {}
    shape_id_map: Dict[int, int] = {}
    next_id = 0

    for idx in removed_idx:
        obj = objects[idx]
        lm = obj.get("local_mask")
        if lm is None:
            continue
        found = False
        for sid, members in shape_groups.items():
            ref_lm = objects[members[0]].get("local_mask")
            if ref_lm is not None and lm.shape == ref_lm.shape and np.array_equal(lm, ref_lm):
                shape_groups[sid].append(idx)
                shape_id_map[idx] = sid
                found = True
                break
        if not found:
            shape_groups[next_id] = [idx]
            shape_id_map[idx] = next_id
            next_id += 1

    all_same_shape = len(shape_groups) == 1
    largest_group = max(len(v) for v in shape_groups.values()) if shape_groups else 0

    # Check if removed share shape with kept
    shared_shapes = 0
    for idx in removed_idx:
        obj = objects[idx]
        lm = obj.get("local_mask")
        if lm is None:
            continue
        for kidx in kept_idx:
            klm = objects[kidx].get("local_mask")
            if klm is not None and lm.shape == klm.shape and np.array_equal(lm, klm):
                shared_shapes += 1
                break

    return {
        "n_shape_groups": len(shape_groups),
        "all_same_shape": all_same_shape,
        "largest_shape_group": largest_group,
        "shape_group_sizes": sorted([len(v) for v in shape_groups.values()], reverse=True),
        "removed_sharing_shape_with_kept": shared_shapes,
    }


def analyze_spatial_grouping(
    objects: List[Dict[str, Any]],
    removed_idx: List[int],
    kept_idx: List[int],
    grid_shape: Tuple[int, int],
) -> Dict[str, Any]:
    """Analyze spatial relationships among removed objects."""
    removed_centers = [
        (objects[i]["center_r"], objects[i]["center_c"]) for i in removed_idx
    ]
    kept_centers = [
        (objects[i]["center_r"], objects[i]["center_c"]) for i in kept_idx
    ]

    if len(removed_centers) < 2:
        return {
            "same_row": False,
            "same_col": False,
            "row_spread": 0,
            "col_spread": 0,
            "mean_pairwise_dist": 0,
            "in_one_quadrant": True,
            "proximity_cluster": True,
        }

    rows = [c[0] for c in removed_centers]
    cols = [c[1] for c in removed_centers]
    row_spread = max(rows) - min(rows)
    col_spread = max(cols) - min(cols)

    # Approximate "same row" / "same col" (within 2 cells tolerance)
    same_row = row_spread <= 2
    same_col = col_spread <= 2

    # Mean pairwise distance
    dists = []
    for i in range(len(removed_centers)):
        for j in range(i + 1, len(removed_centers)):
            d = abs(removed_centers[i][0] - removed_centers[j][0]) + \
                abs(removed_centers[i][1] - removed_centers[j][1])
            dists.append(d)
    mean_dist = sum(dists) / max(len(dists), 1)

    # Check if all in one quadrant
    mid_r, mid_c = grid_shape[0] / 2, grid_shape[1] / 2
    quadrants = set()
    for r, c in removed_centers:
        q = (0 if r < mid_r else 1, 0 if c < mid_c else 1)
        quadrants.add(q)
    in_one_quadrant = len(quadrants) == 1

    # Proximity cluster: all within 2*mean_object_size of each other
    mean_area = np.mean([objects[i]["area"] for i in removed_idx])
    threshold = max(2 * np.sqrt(mean_area), 3)
    proximity_cluster = all(d <= threshold for d in dists) if dists else True

    return {
        "same_row": same_row,
        "same_col": same_col,
        "row_spread": float(row_spread),
        "col_spread": float(col_spread),
        "mean_pairwise_dist": float(mean_dist),
        "in_one_quadrant": in_one_quadrant,
        "proximity_cluster": proximity_cluster,
    }


def analyze_containment(
    objects: List[Dict[str, Any]],
    removed_idx: List[int],
    kept_idx: List[int],
) -> Dict[str, Any]:
    """Check if removed objects are enclosed/contained by kept objects."""
    contained_count = 0
    container_ids = set()

    for ridx in removed_idx:
        r_bbox = objects[ridx]["bbox"]
        for kidx in kept_idx:
            k_bbox = objects[kidx]["bbox"]
            # Check if removed is inside kept's bbox
            if (k_bbox[0] <= r_bbox[0] and k_bbox[1] <= r_bbox[1] and
                    k_bbox[2] >= r_bbox[2] and k_bbox[3] >= r_bbox[3]):
                contained_count += 1
                container_ids.add(kidx)
                break

    return {
        "removed_contained_by_kept": contained_count,
        "n_containers": len(container_ids),
        "all_contained": contained_count == len(removed_idx),
    }


def analyze_size_pattern(
    objects: List[Dict[str, Any]],
    removed_idx: List[int],
    kept_idx: List[int],
) -> Dict[str, Any]:
    """Check if removed/kept are distinguished by size."""
    removed_sizes = sorted([objects[i]["area"] for i in removed_idx])
    kept_sizes = sorted([objects[i]["area"] for i in kept_idx])

    # Are all removed smaller than all kept?
    if removed_sizes and kept_sizes:
        all_removed_smaller = max(removed_sizes) < min(kept_sizes)
        all_removed_larger = min(removed_sizes) > max(kept_sizes)
    else:
        all_removed_smaller = False
        all_removed_larger = False

    return {
        "removed_sizes": removed_sizes,
        "kept_sizes": kept_sizes,
        "all_removed_smaller": all_removed_smaller,
        "all_removed_larger": all_removed_larger,
        "removed_mean_size": float(np.mean(removed_sizes)) if removed_sizes else 0,
        "kept_mean_size": float(np.mean(kept_sizes)) if kept_sizes else 0,
    }


def analyze_boundary_pattern(
    objects: List[Dict[str, Any]],
    removed_idx: List[int],
    kept_idx: List[int],
) -> Dict[str, Any]:
    """Check if removed objects touch boundaries more/less than kept."""
    removed_boundary = sum(1 for i in removed_idx if objects[i].get("touches_boundary", False))
    kept_boundary = sum(1 for i in kept_idx if objects[i].get("touches_boundary", False))

    return {
        "removed_touching_boundary": removed_boundary,
        "kept_touching_boundary": kept_boundary,
        "removed_pct_boundary": removed_boundary / max(len(removed_idx), 1),
        "kept_pct_boundary": kept_boundary / max(len(kept_idx), 1),
    }


# ═══════════════════════════════════════════════════════════════════════════
# TASK-LEVEL ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════

def analyze_task(
    task_id: str,
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> Dict[str, Any]:
    """Run all grouping analyses on a single task."""
    per_example = []
    for ex_idx, (inp, out) in enumerate(train_pairs):
        objects = _extract_objects_with_properties(inp)
        result = _classify_kept_removed(objects, inp, out)
        if result is None:
            per_example.append({
                "example": ex_idx,
                "status": "classification_failed",
                "n_objects": len(objects),
            })
            continue

        kept_idx, removed_idx = result
        is_many_to_few = len(removed_idx) > len(kept_idx)

        analysis = {
            "example": ex_idx,
            "n_objects": len(objects),
            "n_kept": len(kept_idx),
            "n_removed": len(removed_idx),
            "is_many_to_few": is_many_to_few,
            "grid_shape": list(inp.shape),
        }

        if removed_idx:
            analysis["color"] = analyze_color_grouping(objects, removed_idx, kept_idx)
            analysis["shape"] = analyze_shape_grouping(objects, removed_idx, kept_idx)
            analysis["spatial"] = analyze_spatial_grouping(
                objects, removed_idx, kept_idx, inp.shape,
            )
            analysis["containment"] = analyze_containment(objects, removed_idx, kept_idx)
            analysis["size"] = analyze_size_pattern(objects, removed_idx, kept_idx)
            analysis["boundary"] = analyze_boundary_pattern(objects, removed_idx, kept_idx)

        per_example.append(analysis)

    # Aggregate grouping signals across examples
    grouping_signals = []
    for ex in per_example:
        if "color" not in ex:
            continue
        if ex["color"]["all_same_color"]:
            grouping_signals.append("color_uniform")
        if ex["shape"]["all_same_shape"]:
            grouping_signals.append("shape_uniform")
        if ex["spatial"]["same_row"]:
            grouping_signals.append("same_row")
        if ex["spatial"]["same_col"]:
            grouping_signals.append("same_col")
        if ex["spatial"]["proximity_cluster"]:
            grouping_signals.append("proximity_cluster")
        if ex["containment"]["all_contained"]:
            grouping_signals.append("contained_by_kept")
        if ex["size"]["all_removed_smaller"]:
            grouping_signals.append("all_smaller")
        if ex["size"]["all_removed_larger"]:
            grouping_signals.append("all_larger")

    signal_counts = Counter(grouping_signals)

    return {
        "task_id": task_id,
        "n_examples": len(train_pairs),
        "per_example": per_example,
        "grouping_signals": dict(signal_counts),
        "dominant_signal": signal_counts.most_common(1)[0][0] if signal_counts else "none",
    }


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


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Analyze many-to-few grouping structure in rejected ARC tasks",
    )
    parser.add_argument(
        "--rejected-csv",
        default="outputs/operator_reasoning_phase/correspondence/real/results.csv",
        help="Path to correspondence results CSV",
    )
    parser.add_argument(
        "--data-dir",
        default="data/arc",
        help="ARC data directory",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs/operator_reasoning_phase/many_to_few",
        help="Output directory",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── Load tasks ────────────────────────────────────────────────────
    print(f"Loading rejected task IDs from {args.rejected_csv}...")
    rejected_ids = load_rejected_task_ids(args.rejected_csv)
    print(f"  Found {len(rejected_ids)} rejected tasks")

    print(f"Loading ARC tasks from {args.data_dir}...")
    all_tasks = load_arc_tasks(args.data_dir, split="training")
    task_lookup = {t.task_id: t for t in all_tasks}
    print(f"  Loaded {len(all_tasks)} tasks")

    # ── Classify many-to-few ──────────────────────────────────────────
    print("\nClassifying kept/removed for each task...")
    many_to_few_tasks = []
    one_to_one_tasks = []

    for tid in rejected_ids:
        task = task_lookup.get(tid)
        if task is None:
            print(f"  {tid}: not found")
            continue

        train_pairs = [
            (np.array(ex.input_grid), np.array(ex.output_grid))
            for ex in task.train
        ]

        is_m2f = False
        for inp, out in train_pairs:
            objects = _extract_objects_with_properties(inp)
            result = _classify_kept_removed(objects, inp, out)
            if result is not None:
                kept_idx, removed_idx = result
                if len(removed_idx) > len(kept_idx):
                    is_m2f = True
                    break

        if is_m2f:
            many_to_few_tasks.append(tid)
        else:
            one_to_one_tasks.append(tid)

    print(f"\n  Many-to-few tasks: {len(many_to_few_tasks)}")
    print(f"  One-to-one tasks:  {len(one_to_one_tasks)}")

    # ── Analyze many-to-few tasks ─────────────────────────────────────
    print("\nAnalyzing many-to-few grouping structure...")
    analyses: List[Dict[str, Any]] = []

    for tid in many_to_few_tasks:
        task = task_lookup[tid]
        train_pairs = [
            (np.array(ex.input_grid), np.array(ex.output_grid))
            for ex in task.train
        ]
        print(f"  {tid}...", end=" ")
        analysis = analyze_task(tid, train_pairs)
        analyses.append(analysis)
        print(f"signal={analysis['dominant_signal']}")

    # ── Write grouping_taxonomy.csv ───────────────────────────────────
    csv_fields = [
        "task_id", "n_examples", "dominant_signal",
        "color_uniform", "shape_uniform", "same_row", "same_col",
        "proximity_cluster", "contained_by_kept", "all_smaller", "all_larger",
        "avg_kept", "avg_removed",
    ]
    with open(output_dir / "grouping_taxonomy.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields)
        writer.writeheader()
        for a in analyses:
            signals = a.get("grouping_signals", {})
            per_ex = a.get("per_example", [])
            avg_kept = np.mean([e.get("n_kept", 0) for e in per_ex if "n_kept" in e])
            avg_removed = np.mean([e.get("n_removed", 0) for e in per_ex if "n_removed" in e])
            writer.writerow({
                "task_id": a["task_id"],
                "n_examples": a["n_examples"],
                "dominant_signal": a.get("dominant_signal", "none"),
                "color_uniform": signals.get("color_uniform", 0),
                "shape_uniform": signals.get("shape_uniform", 0),
                "same_row": signals.get("same_row", 0),
                "same_col": signals.get("same_col", 0),
                "proximity_cluster": signals.get("proximity_cluster", 0),
                "contained_by_kept": signals.get("contained_by_kept", 0),
                "all_smaller": signals.get("all_smaller", 0),
                "all_larger": signals.get("all_larger", 0),
                "avg_kept": f"{avg_kept:.1f}",
                "avg_removed": f"{avg_removed:.1f}",
            })

    # ── Write grouping_taxonomy.md ────────────────────────────────────
    lines = [
        "# Many-to-Few Grouping Taxonomy",
        "",
        f"**Date**: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Summary",
        "",
        f"- Total rejected tasks: {len(rejected_ids)}",
        f"- Many-to-few tasks (removed > kept): {len(many_to_few_tasks)}",
        f"- One-to-one tasks: {len(one_to_one_tasks)}",
        "",
        "## Grouping Signal Distribution",
        "",
    ]

    # Aggregate signals across all many-to-few tasks
    all_signals: Dict[str, int] = {}
    for a in analyses:
        for sig, count in a.get("grouping_signals", {}).items():
            all_signals[sig] = all_signals.get(sig, 0) + count

    lines.append("| Signal | Tasks with Signal |")
    lines.append("|--------|-------------------|")
    for sig, count in sorted(all_signals.items(), key=lambda x: -x[1]):
        lines.append(f"| {sig} | {count} |")

    lines.extend([
        "",
        "## Per-Task Analysis",
        "",
    ])

    for a in analyses:
        tid = a["task_id"]
        lines.append(f"### {tid}")
        lines.append("")
        lines.append(f"- Examples: {a['n_examples']}")
        lines.append(f"- Dominant signal: {a.get('dominant_signal', 'none')}")
        lines.append(f"- Grouping signals: {a.get('grouping_signals', {})}")
        lines.append("")

        for ex in a.get("per_example", []):
            ex_idx = ex.get("example", "?")
            if "n_kept" not in ex:
                lines.append(f"  - train[{ex_idx}]: classification failed ({ex.get('n_objects', 0)} objects)")
                continue

            lines.append(
                f"  - train[{ex_idx}]: {ex['n_kept']} kept, {ex['n_removed']} removed "
                f"(grid {ex.get('grid_shape', '?')})"
            )

            if "color" in ex:
                c = ex["color"]
                lines.append(
                    f"    - Color: all_same={c['all_same_color']}, "
                    f"removed={c['removed_colors']}, kept={c['kept_colors']}"
                )
            if "shape" in ex:
                s = ex["shape"]
                lines.append(
                    f"    - Shape: all_same={s['all_same_shape']}, "
                    f"groups={s['n_shape_groups']}, "
                    f"shared_with_kept={s['removed_sharing_shape_with_kept']}"
                )
            if "spatial" in ex:
                sp = ex["spatial"]
                lines.append(
                    f"    - Spatial: same_row={sp['same_row']}, same_col={sp['same_col']}, "
                    f"proximity={sp['proximity_cluster']}, "
                    f"quadrant={sp['in_one_quadrant']}"
                )
            if "containment" in ex:
                ct = ex["containment"]
                lines.append(
                    f"    - Containment: all_contained={ct['all_contained']}, "
                    f"n_containers={ct['n_containers']}"
                )
            if "size" in ex:
                sz = ex["size"]
                lines.append(
                    f"    - Size: all_smaller={sz['all_removed_smaller']}, "
                    f"all_larger={sz['all_removed_larger']}, "
                    f"removed_mean={sz['removed_mean_size']:.1f}, "
                    f"kept_mean={sz['kept_mean_size']:.1f}"
                )

        lines.append("")

    lines.extend([
        "## Implications for VDPL",
        "",
        "Many-to-few tasks cannot use injective source->destination matching. ",
        "Potential strategies:",
        "",
        "1. **Group-then-move**: cluster removed objects by color/shape, treat each "
        "cluster as a single composite object, then apply VDPL to the composite.",
        "2. **Template expansion**: if removed objects are copies of kept objects, "
        "the transform is a replication (stamp) pattern, not copy-to-position.",
        "3. **Hierarchical decomposition**: if removed objects are contained within "
        "kept objects (e.g., filling a frame), treat the container as the operative "
        "unit and the contents as a fill rule.",
        "4. **Many-to-one collapse**: multiple removed objects map to a single "
        "destination (merge/overlay). Requires a merge policy.",
        "",
    ])

    with open(output_dir / "grouping_taxonomy.md", "w") as f:
        f.write("\n".join(lines) + "\n")

    # ── Write raw analysis JSON for downstream use ────────────────────
    # Strip numpy arrays for JSON serialization
    def clean_for_json(obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, dict):
            return {k: clean_for_json(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [clean_for_json(v) for v in obj]
        return obj

    with open(output_dir / "grouping_analysis.json", "w") as f:
        json.dump(clean_for_json(analyses), f, indent=2)

    # ── Console summary ───────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"MANY-TO-FEW GROUPING ANALYSIS")
    print(f"{'='*60}")
    print(f"  Many-to-few tasks: {len(many_to_few_tasks)}")
    print(f"  One-to-one tasks:  {len(one_to_one_tasks)}")
    print()
    print("Grouping signals across all many-to-few tasks:")
    for sig, count in sorted(all_signals.items(), key=lambda x: -x[1]):
        print(f"  {sig}: {count}")
    print(f"{'='*60}")
    print(f"Results written to {output_dir}/")


if __name__ == "__main__":
    main()
