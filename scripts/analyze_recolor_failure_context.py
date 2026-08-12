#!/usr/bin/env python3.11
"""Phase 1: Deep failure analysis of 12 rejected real ARC recolor tasks.

For each rejected task, extracts the full color context:
- Which objects are recolored
- Source and target colors
- Candidate color sources (nearest kept, neighbor, marker, same-shape, paired, etc.)
- Classifies the actual recolor pattern

Outputs:
  outputs/operator_reasoning_phase/recolor_context/failure_taxonomy.csv
  outputs/operator_reasoning_phase/recolor_context/failure_taxonomy.md
  outputs/operator_reasoning_phase/recolor_context/color_source_candidate_summary.json
"""
from __future__ import annotations

import csv
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reasoning_project.reasoning_engine import (
    _extract_objects_with_properties,
    _get_property_value,
    _classify_object_changes,
)


def load_recolor_candidates(gap_csv: str) -> List[Dict[str, str]]:
    candidates = []
    with open(gap_csv) as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            if len(row) > 9 and "recolor_in_place" in row[9]:
                candidates.append({
                    "task_id": row[0],
                    "best_property": row[1],
                })
    return candidates


def load_arc_task(task_id: str, arc_root: str) -> Dict:
    with open(os.path.join(arc_root, "arc-agi_training_challenges.json")) as f:
        challenges = json.load(f)
    with open(os.path.join(arc_root, "arc-agi_training_solutions.json")) as f:
        solutions = json.load(f)

    raw = challenges[task_id]
    train_pairs = [
        (np.array(ex["input"], dtype=int), np.array(ex["output"], dtype=int))
        for ex in raw["train"]
    ]
    test_inputs = [np.array(ex["input"], dtype=int) for ex in raw["test"]]
    test_outputs = [np.array(s, dtype=int) for s in solutions.get(task_id, [])]
    return {
        "train_pairs": train_pairs,
        "test_inputs": test_inputs,
        "test_outputs": test_outputs,
    }


def _object_distance(o1: Dict, o2: Dict) -> float:
    return abs(o1["center_r"] - o2["center_r"]) + abs(o1["center_c"] - o2["center_c"])


def _obj_nonbg_colors(obj: Dict, grid: np.ndarray) -> List[int]:
    return sorted(set(int(v) for v in grid[obj["mask"]].ravel() if v != 0))


def analyze_task(task_id: str, best_property: str, task_data: Dict) -> Dict:
    """Deep analysis of one rejected recolor task."""
    result = {
        "task_id": task_id,
        "best_property": best_property,
        "n_train_pairs": len(task_data["train_pairs"]),
        "per_pair": [],
        "recolor_type_votes": Counter(),
        "classified_type": "unknown",
    }

    for pi, (inp, out) in enumerate(task_data["train_pairs"]):
        objects = _extract_objects_with_properties(inp)
        occ = _classify_object_changes(objects, inp, out, bg=0)
        if occ is None:
            result["per_pair"].append({"pair_idx": pi, "error": "no_object_changes"})
            continue

        pair_analysis = {
            "pair_idx": pi,
            "n_objects": len(objects),
            "recolored_objects": [],
            "kept_objects": [],
            "color_maps": {},
        }

        kept_indices = []
        recolored_indices = []

        for ch in occ.changes:
            obj = objects[ch.object_idx]
            if ch.change_type == "kept":
                kept_indices.append(ch.object_idx)
                pair_analysis["kept_objects"].append({
                    "idx": ch.object_idx,
                    "color": obj["primary_color"],
                    "area": obj["area"],
                    "center": (round(obj["center_r"], 1), round(obj["center_c"], 1)),
                })
            elif ch.change_type == "recolored":
                recolored_indices.append(ch.object_idx)

                in_vals = inp[obj["mask"]]
                out_vals = out[obj["mask"]]
                per_pixel_map = {}
                for iv, ov in zip(in_vals.ravel(), out_vals.ravel()):
                    iv, ov = int(iv), int(ov)
                    if iv != 0:
                        per_pixel_map.setdefault(iv, set()).add(ov)

                color_map = {}
                is_one_to_one = True
                for old_c, new_cs in per_pixel_map.items():
                    if len(new_cs) == 1:
                        color_map[old_c] = list(new_cs)[0]
                    else:
                        is_one_to_one = False
                        color_map[old_c] = sorted(new_cs)

                target_colors = set()
                for v in color_map.values():
                    if isinstance(v, list):
                        target_colors.update(v)
                    else:
                        target_colors.add(v)

                # Find candidate color sources
                candidates = {}

                # Nearest kept object color
                if kept_indices:
                    kept_dists = [
                        (_object_distance(obj, objects[ki]), objects[ki]["primary_color"], ki)
                        for ki in kept_indices
                    ]
                    kept_dists.sort()
                    candidates["nearest_kept_color"] = kept_dists[0][1]
                    candidates["nearest_kept_dist"] = round(kept_dists[0][0], 1)
                    candidates["nearest_kept_idx"] = kept_dists[0][2]
                    if len(kept_dists) > 1:
                        candidates["second_nearest_kept_color"] = kept_dists[1][1]

                # Same-shape objects
                same_shape = [
                    i for i in range(len(objects))
                    if i != ch.object_idx
                    and objects[i]["local_mask"].shape == obj["local_mask"].shape
                    and np.array_equal(objects[i]["local_mask"], obj["local_mask"])
                ]
                if same_shape:
                    same_shape_colors = [objects[i]["primary_color"] for i in same_shape]
                    candidates["same_shape_colors"] = same_shape_colors
                    candidates["same_shape_indices"] = same_shape

                # Same-size objects
                same_size = [
                    i for i in range(len(objects))
                    if i != ch.object_idx and objects[i]["area"] == obj["area"]
                ]
                if same_size:
                    candidates["same_size_colors"] = [objects[i]["primary_color"] for i in same_size]

                # Neighbor objects (adjacent/touching)
                obj_dilated = ndimage.binary_dilation(obj["mask"])
                touching = [
                    i for i in range(len(objects))
                    if i != ch.object_idx and np.any(obj_dilated & objects[i]["mask"])
                ]
                if touching:
                    candidates["neighbor_colors"] = [objects[i]["primary_color"] for i in touching]
                    candidates["neighbor_indices"] = touching

                # Container/contained
                if obj.get("is_contained"):
                    for i in range(len(objects)):
                        if i == ch.object_idx:
                            continue
                        ir1, ic1, ir2, ic2 = obj["bbox"]
                        jr1, jc1, jr2, jc2 = objects[i]["bbox"]
                        if jr1 <= ir1 and jc1 <= ic1 and jr2 >= ir2 and jc2 >= ic2:
                            candidates["container_color"] = objects[i]["primary_color"]
                            break

                # Same row/column objects
                same_row = [
                    i for i in range(len(objects))
                    if i != ch.object_idx
                    and abs(objects[i]["center_r"] - obj["center_r"]) < 1.5
                ]
                same_col = [
                    i for i in range(len(objects))
                    if i != ch.object_idx
                    and abs(objects[i]["center_c"] - obj["center_c"]) < 1.5
                ]
                if same_row:
                    candidates["same_row_colors"] = [objects[i]["primary_color"] for i in same_row]
                if same_col:
                    candidates["same_col_colors"] = [objects[i]["primary_color"] for i in same_col]

                # Check if target color matches any source
                target_color_single = list(target_colors)[0] if len(target_colors) == 1 else None
                source_match = None
                if target_color_single is not None:
                    if candidates.get("nearest_kept_color") == target_color_single:
                        source_match = "nearest_kept"
                    elif target_color_single in candidates.get("neighbor_colors", []):
                        source_match = "neighbor"
                    elif target_color_single in candidates.get("same_shape_colors", []):
                        source_match = "same_shape"
                    elif target_color_single in candidates.get("same_row_colors", []):
                        source_match = "same_row"
                    elif target_color_single in candidates.get("same_col_colors", []):
                        source_match = "same_col"
                    elif candidates.get("container_color") == target_color_single:
                        source_match = "container"

                # Check for color swap
                is_swap = all(
                    isinstance(v, int)
                    and color_map.get(v) == k
                    for k, v in color_map.items()
                    if isinstance(v, int)
                ) and len(color_map) >= 2

                pair_analysis["recolored_objects"].append({
                    "idx": ch.object_idx,
                    "area": obj["area"],
                    "source_color": obj["primary_color"],
                    "color_map": {str(k): v for k, v in color_map.items()},
                    "is_one_to_one": is_one_to_one,
                    "target_colors": sorted(target_colors),
                    "is_swap": is_swap,
                    "candidates": candidates,
                    "source_match": source_match,
                    "center": (round(obj["center_r"], 1), round(obj["center_c"], 1)),
                })

                pair_analysis["color_maps"][str(ch.object_idx)] = color_map

        result["per_pair"].append(pair_analysis)

    # Classify the recolor type across all pairs
    result["classified_type"] = _classify_recolor_type(result)
    return result


def _classify_recolor_type(result: Dict) -> str:
    """Classify the overall recolor pattern from per-pair analysis."""
    all_maps = []
    all_source_matches = []
    all_is_swap = []
    all_is_one_to_one = []
    all_target_color_sets = []

    for pair in result["per_pair"]:
        if "error" in pair:
            continue
        for robj in pair.get("recolored_objects", []):
            all_maps.append(robj["color_map"])
            all_source_matches.append(robj.get("source_match"))
            all_is_swap.append(robj.get("is_swap", False))
            all_is_one_to_one.append(robj.get("is_one_to_one", True))
            all_target_color_sets.append(tuple(sorted(robj.get("target_colors", []))))

    if not all_maps:
        return "no_recolored_objects"

    # Check for constant single-target across all
    all_single = all(len(t) == 1 for t in all_target_color_sets)
    if all_single:
        targets = set(t[0] for t in all_target_color_sets)
        if len(targets) == 1:
            return "constant_color"

    # Check consistent map
    if all_maps and all(m == all_maps[0] for m in all_maps):
        return "fixed_global_map"

    # Check all swaps
    if all(all_is_swap):
        return "color_swap"

    # Check consistent source match across pairs
    source_match_set = set(m for m in all_source_matches if m is not None)
    if len(source_match_set) == 1:
        match = source_match_set.pop()
        return f"color_from_{match}"

    # Check if NOT one-to-one (position-dependent recolor)
    if not all(all_is_one_to_one):
        return "position_within_object_recolor"

    # Check for per-pair varying target colors
    if len(set(all_target_color_sets)) > 1:
        # Different target colors per pair — context dependent
        if any(m is not None for m in all_source_matches):
            partial_matches = [m for m in all_source_matches if m is not None]
            match_counts = Counter(partial_matches)
            dominant = match_counts.most_common(1)[0]
            if dominant[1] >= len(all_maps) * 0.5:
                return f"color_from_{dominant[0]}_partial"
        return "context_dependent_recolor"

    return "unknown"


def main():
    os.chdir(Path(__file__).resolve().parent.parent)

    gap_csv = "outputs/operator_gap_analysis_v3/operator_gap_trace.csv"
    arc_root = "data/arc"
    out_dir = Path("outputs/operator_reasoning_phase/recolor_context")
    out_dir.mkdir(parents=True, exist_ok=True)

    candidates = load_recolor_candidates(gap_csv)
    print(f"Analyzing {len(candidates)} rejected recolor tasks...\n")

    analyses = []
    type_counts = Counter()

    for cand in candidates:
        task_id = cand["task_id"]
        best_property = cand["best_property"]
        task_data = load_arc_task(task_id, arc_root)
        analysis = analyze_task(task_id, best_property, task_data)
        analyses.append(analysis)
        ctype = analysis["classified_type"]
        type_counts[ctype] += 1

        n_recolored = sum(
            len(p.get("recolored_objects", []))
            for p in analysis["per_pair"]
            if "error" not in p
        )
        source_matches = set()
        swap_count = 0
        o2o_fails = 0
        for p in analysis["per_pair"]:
            if "error" in p:
                continue
            for ro in p.get("recolored_objects", []):
                if ro.get("source_match"):
                    source_matches.add(ro["source_match"])
                if ro.get("is_swap"):
                    swap_count += 1
                if not ro.get("is_one_to_one"):
                    o2o_fails += 1

        print(f"{task_id}: type={ctype}")
        print(f"  recolored_objs={n_recolored}, source_matches={source_matches or 'none'}, "
              f"swaps={swap_count}, one2one_fails={o2o_fails}")

    # Write taxonomy CSV
    csv_path = out_dir / "failure_taxonomy.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "task_id", "best_property", "classified_type", "n_pairs",
            "n_recolored_objs", "consistent_map", "has_swap",
            "source_matches", "one_to_one",
        ])
        for a in analyses:
            n_rc = sum(len(p.get("recolored_objects", [])) for p in a["per_pair"] if "error" not in p)
            maps = []
            has_swap = False
            sources = set()
            o2o = True
            for p in a["per_pair"]:
                if "error" in p:
                    continue
                for ro in p.get("recolored_objects", []):
                    maps.append(ro["color_map"])
                    if ro.get("is_swap"):
                        has_swap = True
                    if ro.get("source_match"):
                        sources.add(ro["source_match"])
                    if not ro.get("is_one_to_one"):
                        o2o = False

            consistent = len(maps) > 1 and all(m == maps[0] for m in maps) if maps else False
            writer.writerow([
                a["task_id"], a["best_property"], a["classified_type"],
                a["n_train_pairs"], n_rc, consistent, has_swap,
                ";".join(sorted(sources)) if sources else "none", o2o,
            ])

    # Write taxonomy markdown
    md_path = out_dir / "failure_taxonomy.md"
    with open(md_path, "w") as f:
        f.write("# Recolor Failure Taxonomy\n\n")
        f.write(f"Tasks analyzed: {len(analyses)}\n\n")
        f.write("## Type Distribution\n\n")
        f.write("| Type | Count |\n|------|-------|\n")
        for t, c in type_counts.most_common():
            f.write(f"| {t} | {c} |\n")

        f.write("\n## Per-Task Analysis\n\n")
        for a in analyses:
            f.write(f"### {a['task_id']}\n\n")
            f.write(f"- Selector: `{a['best_property']}`\n")
            f.write(f"- Classified type: **{a['classified_type']}**\n")
            f.write(f"- Training pairs: {a['n_train_pairs']}\n\n")

            for p in a["per_pair"]:
                if "error" in p:
                    f.write(f"  Pair {p['pair_idx']}: {p['error']}\n")
                    continue
                f.write(f"  **Pair {p['pair_idx']}** ({len(p.get('recolored_objects', []))} recolored, "
                        f"{len(p.get('kept_objects', []))} kept):\n\n")
                for ro in p.get("recolored_objects", []):
                    f.write(f"  - Object {ro['idx']}: area={ro['area']}, "
                            f"map={ro['color_map']}, swap={ro['is_swap']}, "
                            f"source_match={ro.get('source_match', 'none')}\n")
                    cands = ro.get("candidates", {})
                    if cands.get("nearest_kept_color") is not None:
                        f.write(f"    - nearest_kept: color={cands['nearest_kept_color']}, "
                                f"dist={cands.get('nearest_kept_dist')}\n")
                    if cands.get("neighbor_colors"):
                        f.write(f"    - neighbors: {cands['neighbor_colors']}\n")
                    if cands.get("same_shape_colors"):
                        f.write(f"    - same_shape: {cands['same_shape_colors']}\n")
                f.write("\n")

    # Write summary JSON
    summary = {
        "total_tasks": len(analyses),
        "type_distribution": dict(type_counts.most_common()),
        "per_task": [],
    }
    for a in analyses:
        task_sum = {
            "task_id": a["task_id"],
            "best_property": a["best_property"],
            "classified_type": a["classified_type"],
            "n_pairs": a["n_train_pairs"],
        }
        # Collect source matches
        sources = set()
        for p in a["per_pair"]:
            if "error" in p:
                continue
            for ro in p.get("recolored_objects", []):
                if ro.get("source_match"):
                    sources.add(ro["source_match"])
        task_sum["source_matches"] = sorted(sources)
        summary["per_task"].append(task_sum)

    summary_path = out_dir / "color_source_candidate_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))

    print(f"\n{'='*60}")
    print("RECOLOR FAILURE TAXONOMY")
    print(f"{'='*60}")
    for t, c in type_counts.most_common():
        print(f"  {t}: {c}")
    print(f"\nOutputs:")
    print(f"  {csv_path}")
    print(f"  {md_path}")
    print(f"  {summary_path}")


if __name__ == "__main__":
    main()
