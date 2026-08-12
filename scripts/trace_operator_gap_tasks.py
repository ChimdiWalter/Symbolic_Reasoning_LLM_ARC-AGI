"""Operator gap trace: for tasks where a property discriminates but reconstruction fails,
classify the missing operator and log detailed evidence.

For each task, logs:
    task_id, best_property, property_discrimination_score, target_objects,
    old_reconstruction_mode, old_reconstruction_output_similarity,
    LOO_failure_reason, needed_operator_family, operator_evidence,
    closest_existing_operator, why_existing_operator_failed,
    suggested_parameterization

Outputs:
    outputs/operator_gap_analysis/operator_gap_trace.csv
    outputs/operator_gap_analysis/operator_gap_report.md
    outputs/operator_gap_analysis/operator_family_counts.json
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reasoning_project.reasoning_engine import (
    GridDomainAdapter,
    ReasoningMemory,
    StructuralReasoner,
    _all_property_names,
    _extract_objects_with_properties,
    _classify_kept_removed,
    _classify_object_changes,
    _find_discriminative_property,
    _find_discriminative_property_extended,
)

OPERATOR_FAMILIES = [
    "copy_to_position",
    "marker_directed_move",
    "gravity_or_drop",
    "line_extend_until_collision",
    "hole_fill_multicolor",
    "region_fill_from_boundary",
    "object_match_transfer_color",
    "shape_completion",
    "pattern_repetition_fill",
    "separator_cell_compose",
    "grid_reshape",
    "multi_step_program",
    "recolor_in_place",
    "move_to_position",
    "object_changed",
    "unknown",
]

EXISTING_OPERATORS = [
    "MarkerTargetTransform",
    "ContainerContentExtract",
    "SeparatorCellCompose",
    "SymmetryCompletion",
    "PatternRepetitionFill",
    "LineExtendUntilBoundary",
    "ObjectMatchTransferColor",
    "FilterCropRecolor",
    "MarkerDirectedMove",
    "ShapeCompleteFromBoundary",
    "SeparatorCellComposeAdvanced",
    "fill_removed_constant",
    "marker_projection",
    "fill_removed_nearest_kept_color",
    "stamp_kept_at_removed",
    "color_mapping_fill",
    "recolor_by_relationship",
]


def load_arc_tasks(arc_root: str, max_tasks: int = 0) -> List[Dict]:
    tasks = []
    challenges_path = os.path.join(arc_root, "arc-agi_training_challenges.json")
    solutions_path = os.path.join(arc_root, "arc-agi_training_solutions.json")
    if not os.path.isfile(challenges_path):
        return tasks
    with open(challenges_path) as f:
        challenges = json.load(f)
    solutions = {}
    if os.path.isfile(solutions_path):
        with open(solutions_path) as f:
            solutions = json.load(f)
    for task_id in sorted(challenges.keys()):
        data = challenges[task_id]
        train_pairs = [
            (np.array(ex["input"]), np.array(ex["output"]))
            for ex in data["train"]
        ]
        test_inputs = [np.array(ex["input"]) for ex in data["test"]]
        test_outputs = []
        if task_id in solutions:
            test_outputs = [np.array(o) for o in solutions[task_id]]
        elif data["test"] and "output" in data["test"][0]:
            test_outputs = [np.array(ex["output"]) for ex in data["test"]]
        tasks.append({
            "task_id": task_id,
            "train_pairs": train_pairs,
            "test_inputs": test_inputs,
            "test_outputs": test_outputs,
        })
        if max_tasks > 0 and len(tasks) >= max_tasks:
            break
    return tasks


def compute_pixel_similarity(a: np.ndarray, b: np.ndarray) -> float:
    if a.shape != b.shape:
        return 0.0
    return float(np.mean(a == b))


def detect_displacement(
    objects: List[Dict],
    removed_idx: List[int],
    inp: np.ndarray,
    out: np.ndarray,
) -> List[Dict]:
    """Detect if removed objects appear at new positions in the output."""
    displacements = []
    for ri in removed_idx:
        obj = objects[ri]
        obj_shape = obj["local_mask"]
        oh, ow = obj_shape.shape
        obj_colors = inp[obj["mask"]]

        best_sim = 0.0
        best_pos = None
        h, w = out.shape
        for r in range(h - oh + 1):
            for c in range(w - ow + 1):
                region = out[r:r+oh, c:c+ow]
                if obj_shape.shape != region.shape:
                    continue
                match_pixels = region[obj_shape]
                orig_pixels = obj_colors
                if len(match_pixels) != len(orig_pixels):
                    continue
                sim = float(np.mean(match_pixels == orig_pixels))
                if sim > best_sim and sim > 0.5:
                    best_sim = sim
                    best_pos = (r, c)

        if best_pos is not None:
            orig_r, orig_c = obj["bbox"][0], obj["bbox"][1]
            dr = best_pos[0] - orig_r
            dc = best_pos[1] - orig_c
            if abs(dr) > 0 or abs(dc) > 0:
                displacements.append({
                    "object_label": obj["label"],
                    "from": (orig_r, orig_c),
                    "to": best_pos,
                    "displacement": (dr, dc),
                    "similarity": best_sim,
                })
    return displacements


def detect_line_extension(
    objects: List[Dict],
    kept_idx: List[int],
    removed_idx: List[int],
    inp: np.ndarray,
    out: np.ndarray,
) -> bool:
    """Check if output has lines extending from kept objects."""
    diff = (out != inp).astype(int)
    if diff.sum() == 0:
        return False

    for ki in kept_idx:
        obj = objects[ki]
        cr, cc = int(obj["center_r"]), int(obj["center_c"])
        color = obj["primary_color"]
        for dr, dc in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            r, c = cr + dr, cc + dc
            line_len = 0
            while 0 <= r < out.shape[0] and 0 <= c < out.shape[1]:
                if out[r, c] == color and inp[r, c] != color:
                    line_len += 1
                else:
                    break
                r += dr
                c += dc
            if line_len >= 2:
                return True
    return False


def detect_hole_fill(
    objects: List[Dict],
    removed_idx: List[int],
    inp: np.ndarray,
    out: np.ndarray,
) -> bool:
    """Check if output fills holes in objects."""
    from scipy import ndimage
    for ri in removed_idx:
        obj = objects[ri]
        bbox = obj["bbox"]
        region_in = inp[bbox[0]:bbox[2]+1, bbox[1]:bbox[3]+1]
        region_out = out[bbox[0]:bbox[2]+1, bbox[1]:bbox[3]+1]
        if not np.array_equal(region_in, region_out):
            local_mask = obj["local_mask"]
            holes = ~local_mask
            border_labels = set()
            bg_labeled, n_bg = ndimage.label(holes)
            border_labels.update(bg_labeled[0, :].tolist())
            border_labels.update(bg_labeled[-1, :].tolist())
            border_labels.update(bg_labeled[:, 0].tolist())
            border_labels.update(bg_labeled[:, -1].tolist())
            border_labels.discard(0)
            interior_holes = sum(1 for lb in range(1, n_bg + 1) if lb not in border_labels)
            if interior_holes > 0:
                return True
    return False


def detect_color_transfer(
    objects: List[Dict],
    kept_idx: List[int],
    removed_idx: List[int],
    inp: np.ndarray,
    out: np.ndarray,
) -> bool:
    """Check if removed objects' colors change to match a kept object."""
    kept_colors = set()
    for ki in kept_idx:
        kept_colors.add(objects[ki]["primary_color"])
    for ri in removed_idx:
        obj = objects[ri]
        out_colors = set(out[obj["mask"]].tolist()) - {0}
        if out_colors and out_colors.issubset(kept_colors):
            if obj["primary_color"] not in kept_colors:
                return True
    return False


def detect_pattern_repetition(
    inp: np.ndarray,
    out: np.ndarray,
) -> bool:
    """Check if output tiles/repeats a pattern from input."""
    ih, iw = inp.shape
    oh, ow = out.shape
    if oh > ih and ow >= iw:
        if oh % ih == 0 and ow % iw == 0:
            tile_ok = True
            for r in range(0, oh, ih):
                for c in range(0, ow, iw):
                    region = out[r:r+ih, c:c+iw]
                    if region.shape == inp.shape and not np.array_equal(region, inp):
                        tile_ok = False
                        break
            if tile_ok:
                return True
    return False


def classify_operator_family(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    prop_name: str,
    keep_when_true: bool,
) -> Tuple[str, Dict[str, Any]]:
    """Classify the needed operator family from input/output correspondences."""
    evidence: Dict[str, Any] = {}
    all_displacements = []
    has_line_ext = False
    has_hole_fill = False
    has_color_transfer = False
    has_pattern_rep = False
    removed_present_count = 0
    removed_absent_count = 0
    total_removed = 0

    used_rich_classifier = False
    rich_change_types: Dict[str, int] = {}

    for inp, out in train_pairs:
        objects = _extract_objects_with_properties(inp)
        kr = _classify_kept_removed(objects, inp, out)

        if kr is None:
            # Fall back to rich object-change classifier
            occ = _classify_object_changes(objects, inp, out)
            if occ is not None and occ.has_two_groups:
                used_rich_classifier = True
                kept_idx = occ.group_a
                removed_idx = occ.group_b
                for ch in occ.changes:
                    rich_change_types[ch.change_type] = rich_change_types.get(ch.change_type, 0) + 1
            else:
                return "unknown", evidence
        else:
            kept_idx, removed_idx = kr

        total_removed += len(removed_idx)

        for ri in removed_idx:
            obj = objects[ri]
            out_region = out[obj["mask"]]
            if np.any(out_region != 0):
                removed_present_count += 1
            else:
                removed_absent_count += 1

        displacements = detect_displacement(objects, removed_idx, inp, out)
        all_displacements.extend(displacements)

        if detect_line_extension(objects, kept_idx, removed_idx, inp, out):
            has_line_ext = True

        if detect_hole_fill(objects, removed_idx, inp, out):
            has_hole_fill = True

        if detect_color_transfer(objects, kept_idx, removed_idx, inp, out):
            has_color_transfer = True

        if detect_pattern_repetition(inp, out):
            has_pattern_rep = True

    evidence = {
        "displacements": all_displacements[:10],
        "has_line_extension": has_line_ext,
        "has_hole_fill": has_hole_fill,
        "has_color_transfer": has_color_transfer,
        "has_pattern_repetition": has_pattern_rep,
        "removed_present_count": removed_present_count,
        "removed_absent_count": removed_absent_count,
        "total_removed": total_removed,
        "used_rich_classifier": used_rich_classifier,
        "rich_change_types": rich_change_types,
    }

    # If rich classifier detected specific change types, route accordingly
    if used_rich_classifier and rich_change_types:
        n_recolored = rich_change_types.get("recolored", 0)
        n_moved = rich_change_types.get("moved", 0)
        n_moved_recolored = rich_change_types.get("moved_recolored", 0)
        n_changed = rich_change_types.get("changed", 0)

        if n_recolored > 0 and n_moved == 0 and n_moved_recolored == 0:
            return "recolor_in_place", evidence
        if n_moved > 0 or n_moved_recolored > 0:
            return "move_to_position", evidence
        if n_changed > 0:
            return "object_changed", evidence

    if all_displacements:
        drs = [d["displacement"][0] for d in all_displacements]
        dcs = [d["displacement"][1] for d in all_displacements]
        if all(dr == drs[0] for dr in drs) and all(dc == dcs[0] for dc in dcs):
            evidence["consistent_displacement"] = (drs[0], dcs[0])
            return "marker_directed_move", evidence
        if all(dc == 0 for dc in dcs) and all(dr > 0 for dr in drs):
            return "gravity_or_drop", evidence
        return "copy_to_position", evidence

    if has_line_ext:
        return "line_extend_until_collision", evidence

    if has_hole_fill:
        return "hole_fill_multicolor", evidence

    if has_color_transfer:
        return "object_match_transfer_color", evidence

    if has_pattern_rep:
        return "pattern_repetition_fill", evidence

    if removed_present_count > 0 and removed_present_count == total_removed:
        return "region_fill_from_boundary", evidence

    if removed_absent_count == total_removed and total_removed > 0:
        return "shape_completion", evidence

    return "unknown", evidence


def find_closest_existing_operator(family: str) -> Tuple[str, str]:
    """Find the closest existing operator schema and why it fails."""
    mapping = {
        "copy_to_position": ("MarkerTargetTransform", "only removes/recolors targets, does not copy to new positions"),
        "marker_directed_move": ("MarkerDirectedMove", "schema exists but may lack parameterization for this displacement pattern"),
        "gravity_or_drop": ("MarkerTargetTransform", "no gravity/drop operator exists; MarkerTargetTransform only does in-place transforms"),
        "line_extend_until_collision": ("LineExtendUntilBoundary", "schema exists but may not match exact collision targets"),
        "hole_fill_multicolor": ("fill_removed_constant", "only fills with single constant color, not boundary-adaptive multicolor"),
        "region_fill_from_boundary": ("fill_removed_nearest_kept_color", "nearest-color heuristic is too coarse"),
        "object_match_transfer_color": ("ObjectMatchTransferColor", "schema exists but matching criteria may differ"),
        "shape_completion": ("SymmetryCompletion", "only handles symmetric completion, not arbitrary shape continuation"),
        "pattern_repetition_fill": ("PatternRepetitionFill", "schema exists but tile detection may miss this pattern"),
        "separator_cell_compose": ("SeparatorCellCompose", "schema exists, may need different composition rule"),
        "grid_reshape": ("FilterCropRecolor", "only crops/recolors, does not reshape grid"),
        "multi_step_program": ("FilterCropRecolor", "no multi-step composition operator exists"),
        "recolor_in_place": ("recolor_by_relationship", "exists but may not match this recolor rule"),
        "move_to_position": ("MarkerTargetTransform", "only removes/recolors, does not move objects"),
        "object_changed": ("none", "object changes without clear move/recolor pattern"),
        "unknown": ("none", "no matching operator family identified"),
    }
    return mapping.get(family, ("none", "unknown family"))


def suggest_parameterization(family: str, evidence: Dict) -> str:
    """Suggest how to parameterize the operator from evidence."""
    if family == "copy_to_position" and "displacements" in evidence:
        disps = evidence["displacements"]
        if disps:
            return f"displacement_vector=({disps[0]['displacement'][0]},{disps[0]['displacement'][1]})"
    if family == "marker_directed_move" and "consistent_displacement" in evidence:
        d = evidence["consistent_displacement"]
        return f"direction=({'down' if d[0]>0 else 'up'},{('right' if d[1]>0 else 'left') if d[1]!=0 else 'none'}), magnitude=({abs(d[0])},{abs(d[1])})"
    if family == "gravity_or_drop":
        return "direction=down, stop_condition=collision_or_boundary"
    if family == "line_extend_until_collision":
        return "direction=all_cardinal, stop_condition=boundary_or_object_collision"
    if family == "hole_fill_multicolor":
        return "fill_source=boundary_color_per_hole"
    if family == "object_match_transfer_color":
        return "match_by=shape_similarity, transfer=color_from_matched"
    if family == "pattern_repetition_fill":
        return "pattern_source=input_subgrid, repeat_mode=tile"
    return "requires_analysis"


def main():
    parser = argparse.ArgumentParser(
        description="Trace operator gaps for property-sufficient tasks")
    parser.add_argument("--arc-root", default="data/arc")
    parser.add_argument("--output-dir", default="outputs/operator_gap_analysis")
    parser.add_argument("--max-tasks", type=int, default=0)
    parser.add_argument("--use-cache", default="",
                        help="Load fast cache to skip static solve pass")
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    print("=" * 60)
    print("OPERATOR GAP TRACE")
    print("=" * 60)

    tasks = load_arc_tasks(args.arc_root, max_tasks=args.max_tasks)
    print(f"Loaded {len(tasks)} ARC tasks\n", flush=True)

    # Identify property-sufficient tasks
    print("=== Finding property-sufficient tasks ===", flush=True)
    gap_tasks = []

    if args.use_cache:
        cache_dir = Path(args.use_cache)
        traces_path = cache_dir / "object_traces.jsonl"
        if traces_path.exists():
            task_lookup = {t["task_id"]: t for t in tasks}
            with open(traces_path) as f:
                for line in f:
                    tr = json.loads(line.strip())
                    if tr["failure_type"] == "property_found_reconstruction_fails":
                        tid = tr["task_id"]
                        if tid in task_lookup:
                            gap_tasks.append(task_lookup[tid])
            print(f"  Loaded {len(gap_tasks)} property-sufficient tasks from cache")
        else:
            print(f"  [WARN] No cache traces at {traces_path}, scanning all tasks")
            args.use_cache = ""

    if not args.use_cache:
        for i, task in enumerate(tasks):
            tp = task["train_pairs"]
            if len(tp) < 2:
                continue
            if not all(i.shape == o.shape for i, o in tp):
                continue

            # Try classic classifier first, then rich classifier as fallback
            classifiable = True
            used_rich = False
            for inp_i, out_i in tp:
                objs = _extract_objects_with_properties(inp_i)
                kr = _classify_kept_removed(objs, inp_i, out_i)
                if kr is not None:
                    continue
                occ = _classify_object_changes(objs, inp_i, out_i)
                if occ is not None and occ.has_two_groups:
                    used_rich = True
                    continue
                classifiable = False
                break
            if not classifiable:
                continue

            disc = _find_discriminative_property_extended(tp)
            if disc is None:
                continue
            prop_name, keep_when_true = disc
            adapter = GridDomainAdapter()
            all_match = True
            for inp, out in tp:
                objects = adapter.extract_objects(inp)
                keep_mask = [adapter.get_property(o, prop_name) == keep_when_true
                             for o in objects]
                pred = adapter.reconstruct_filtered(inp, objects, keep_mask)
                if pred is not None and adapter.scenes_equal(pred, out):
                    continue
                all_match = False
                break
            if not all_match:
                task["_disc_prop"] = prop_name
                task["_disc_keep"] = keep_when_true
                task["_used_rich_classifier"] = used_rich
                gap_tasks.append(task)
            if (i + 1) % 200 == 0:
                print(f"  {i+1}/{len(tasks)} scanned, {len(gap_tasks)} gap tasks found",
                      flush=True)

    print(f"\nFound {len(gap_tasks)} property-sufficient tasks with reconstruction gap\n",
          flush=True)

    # Detailed trace for each gap task
    print("=== Tracing operator gaps ===", flush=True)
    traces = []
    family_counts = Counter()

    for i, task in enumerate(gap_tasks):
        tid = task["task_id"]
        tp = task["train_pairs"]

        prop_name = task.get("_disc_prop")
        keep_when_true = task.get("_disc_keep")
        if prop_name is None:
            disc = _find_discriminative_property(tp)
            if disc is None:
                continue
            prop_name, keep_when_true = disc

        adapter = GridDomainAdapter()
        sims = []
        for inp, out in tp:
            objects = adapter.extract_objects(inp)
            keep_mask = [adapter.get_property(o, prop_name) == keep_when_true
                         for o in objects]
            pred = adapter.reconstruct_filtered(inp, objects, keep_mask)
            if pred is not None:
                sims.append(compute_pixel_similarity(pred, out))
            else:
                sims.append(0.0)

        mean_sim = float(np.mean(sims)) if sims else 0.0

        # Try alternative reconstruction modes
        reasoner = StructuralReasoner(adapter, memory=ReasoningMemory(), min_train=2)
        alt_result = reasoner._try_discriminative_marker_target(
            tp, task["test_inputs"])
        alt_mode = "none"
        if alt_result is not None:
            alt_mode = alt_result[1].get("sub_strategy", "unknown")

        family, evidence = classify_operator_family(tp, prop_name, keep_when_true)
        family_counts[family] += 1

        closest_op, why_fails = find_closest_existing_operator(family)
        param_suggestion = suggest_parameterization(family, evidence)

        n_kept = sum(
            len(_classify_kept_removed(_extract_objects_with_properties(i), i, o)[0])
            for i, o in tp
            if _classify_kept_removed(_extract_objects_with_properties(i), i, o) is not None
        )
        n_removed = sum(
            len(_classify_kept_removed(_extract_objects_with_properties(i), i, o)[1])
            for i, o in tp
            if _classify_kept_removed(_extract_objects_with_properties(i), i, o) is not None
        )

        trace = {
            "task_id": tid,
            "best_property": prop_name,
            "property_discrimination_score": 1.0,
            "target_objects_kept": n_kept,
            "target_objects_removed": n_removed,
            "old_reconstruction_mode": "zero_removed",
            "old_reconstruction_output_similarity": round(mean_sim, 4),
            "alt_reconstruction_mode": alt_mode,
            "LOO_failure_reason": "reconstruction_mismatch" if mean_sim < 1.0 else "none",
            "needed_operator_family": family,
            "operator_evidence": json.dumps({
                k: v for k, v in evidence.items()
                if k not in ("displacements",)
            }),
            "displacement_summary": str(evidence.get("displacements", [])[:3]),
            "closest_existing_operator": closest_op,
            "why_existing_operator_failed": why_fails,
            "suggested_parameterization": param_suggestion,
        }
        traces.append(trace)

        if (i + 1) % 20 == 0:
            print(f"  {i+1}/{len(gap_tasks)} traced", flush=True)

    # Write CSV
    if traces:
        fieldnames = list(traces[0].keys())
        with open(out_dir / "operator_gap_trace.csv", "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(traces)

    # Write family counts
    with open(out_dir / "operator_family_counts.json", "w") as f:
        json.dump(dict(family_counts), f, indent=2)

    # Write report
    elapsed = time.time() - t0
    lines = [
        "# Operator Gap Analysis Report\n",
        f"- Tasks analyzed: {len(tasks)}",
        f"- Property-sufficient tasks (reconstruction fails): {len(gap_tasks)}",
        f"- Traces generated: {len(traces)}",
        f"- Elapsed: {elapsed:.0f}s",
        "",
        "## Operator Family Distribution\n",
        "| Family | Count | % |",
        "|--------|-------|---|",
    ]
    total = sum(family_counts.values()) or 1
    for family in OPERATOR_FAMILIES:
        count = family_counts.get(family, 0)
        if count > 0:
            lines.append(f"| {family} | {count} | {100*count/total:.1f}% |")
    lines.append("")

    lines.append("## Dominant Missing Layer\n")
    if family_counts:
        top_family = family_counts.most_common(1)[0]
        lines.append(f"The dominant missing operator family is **{top_family[0]}** "
                      f"({top_family[1]} tasks, {100*top_family[1]/total:.0f}%).\n")
        if top_family[0] in ("copy_to_position", "marker_directed_move", "gravity_or_drop"):
            lines.append("This indicates the primary barrier is **spatial movement/relocation** — "
                          "the property correctly identifies WHICH objects to transform, but the "
                          "system lacks operators to MOVE them to the correct position.\n")
        elif top_family[0] in ("line_extend_until_collision", "region_fill_from_boundary",
                                "hole_fill_multicolor"):
            lines.append("This indicates the primary barrier is **region fill/extension** — "
                          "the system needs operators that fill or extend based on "
                          "boundary/collision constraints.\n")
        elif top_family[0] in ("object_match_transfer_color",):
            lines.append("This indicates the primary barrier is **color transfer** — "
                          "the system needs to match objects and transfer properties.\n")
    else:
        lines.append("No operator gaps classified.\n")

    lines.append("## Sample Traces\n")
    for trace in traces[:10]:
        lines.append(f"### {trace['task_id']}")
        lines.append(f"- Property: `{trace['best_property']}` (disc=1.0)")
        lines.append(f"- Reconstruction similarity: {trace['old_reconstruction_output_similarity']}")
        lines.append(f"- Needed operator: **{trace['needed_operator_family']}**")
        lines.append(f"- Closest existing: {trace['closest_existing_operator']} "
                      f"({trace['why_existing_operator_failed']})")
        lines.append(f"- Suggested params: {trace['suggested_parameterization']}")
        lines.append("")

    with open(out_dir / "operator_gap_report.md", "w") as f:
        f.write("\n".join(lines) + "\n")

    print(f"\nDone in {elapsed:.0f}s")
    print(f"  Gap tasks: {len(gap_tasks)}")
    print(f"  Family distribution: {dict(family_counts)}")
    print(f"\nOutputs: {out_dir}")


if __name__ == "__main__":
    main()
