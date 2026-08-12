"""Phase 2: Selector-target oracle analysis for unsolved tasks.

For each unsolved task in the focused eval full-orchestrator config:
  1. Load train input/output pairs
  2. Compute changed pixels and map to input objects
  3. Infer candidate target objects/regions
  4. Check all properties (single, conjunction, negation, rank, relational)
  5. Classify the selector gap

Answers: Can the correct target be identified with the current 107 properties?
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from collections import defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from reasoning_project.arc_adapter import load_arc_tasks, ARCTask
from reasoning_project.reasoning_engine import (
    _extract_objects_with_properties,
    _add_relational_properties as _add_rel_props_raw,
    _get_property_value,
    _all_property_names,
    _classify_kept_removed,
    _classify_object_changes,
)


def _add_relational_properties(objects, grid):
    h, w = grid.shape[:2]
    _add_rel_props_raw(objects, grid, h, w)
    return objects

ARC_ROOT = Path(__file__).parent.parent / "data" / "arc"
OUTPUT_DIR = "outputs/full_novel_reasoning_pipeline_v2/full_pipeline_activation_repair"

FAILURE_CATEGORIES = [
    "single_property_sufficient",
    "conjunction_needed",
    "negation_needed",
    "rank_property_needed",
    "marker_relation_needed",
    "frame_relation_needed",
    "anchor_relation_needed",
    "color_count_relation_needed",
    "shape_match_relation_needed",
    "pattern_membership_needed",
    "boundary_interior_relation_needed",
    "output_change_relation_needed",
    "object_representation_failure",
    "multi_object_target",
    "region_not_object",
    "size_change_task",
    "unknown",
]


def load_v1_results(path: str = "outputs/full_arc1000_novel_pipeline/progress.jsonl") -> Dict[str, Dict]:
    results = {}
    if not os.path.exists(path):
        return results
    with open(path) as f:
        for line in f:
            if line.strip():
                row = json.loads(line)
                row["solved"] = (
                    row.get("final_config_that_solved") is not None
                    or row.get("operator_promoted", False)
                    or row.get("solved_by_static", False)
                )
                results[row.get("task_id", "")] = row
    return results


def load_v2_results(
    path: str = "outputs/full_novel_reasoning_pipeline_v2/focused_eval_after_operator_coverage_repair/results.csv",
) -> Dict[str, Dict]:
    results = {}
    if not os.path.exists(path):
        return results
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("config") == "v2_full_gated_orchestrator":
                results[row["task_id"]] = row
    return results


def get_unsolved_task_ids(v2_results: Dict[str, Dict]) -> List[str]:
    return [
        tid for tid, r in v2_results.items()
        if r.get("v2_solved", "False") in (False, "False", "false", "0", "")
    ]


def infer_target_objects(
    inp: np.ndarray, out: np.ndarray, objects: List[Dict]
) -> Optional[Dict[str, Any]]:
    """Infer which input objects are the targets of the transformation.

    Returns dict with target_indices, target_type, change_map.
    """
    if inp.shape != out.shape:
        return {"target_type": "size_change", "target_indices": [],
                "change_map": {}, "reason": "input and output shapes differ"}

    diff = inp != out
    if not diff.any():
        return None

    changed_indices = []
    unchanged_indices = []
    for i, obj in enumerate(objects):
        mask = obj["mask"]
        obj_changed = diff[mask].any()
        if obj_changed:
            changed_indices.append(i)
        else:
            unchanged_indices.append(i)

    bg_diff = diff.copy()
    for obj in objects:
        bg_diff[obj["mask"]] = False
    bg_changed = bg_diff.any()

    kr = _classify_kept_removed(objects, inp, out)
    if kr is not None:
        kept, removed = kr
        return {
            "target_type": "kept_removed",
            "target_indices": removed,
            "kept_indices": kept,
            "changed_indices": changed_indices,
            "bg_changed": bg_changed,
            "change_map": {"kept": kept, "removed": removed},
        }

    changes = _classify_object_changes(objects, inp, out)
    if changes is not None:
        change_groups = defaultdict(list)
        for i, (ct, conf) in enumerate(zip(changes.per_object_type, changes.per_object_confidence)):
            change_groups[ct].append(i)

        if len(change_groups) > 1:
            largest_unchanged = []
            largest_changed = []
            for ct, indices in change_groups.items():
                if ct == "kept":
                    largest_unchanged = indices
                else:
                    largest_changed.extend(indices)
            return {
                "target_type": "object_changes",
                "target_indices": largest_changed,
                "kept_indices": largest_unchanged,
                "changed_indices": changed_indices,
                "bg_changed": bg_changed,
                "change_groups": {k: v for k, v in change_groups.items()},
                "change_map": {"changed": largest_changed, "unchanged": largest_unchanged},
            }

    return {
        "target_type": "pixel_diff_only",
        "target_indices": changed_indices,
        "changed_indices": changed_indices,
        "bg_changed": bg_changed,
        "change_map": {},
    }


def check_single_property(
    target_indices: List[int],
    non_target_indices: List[int],
    objects: List[Dict],
    all_props: List[str],
) -> Optional[Tuple[str, bool]]:
    if not target_indices or not non_target_indices:
        return None

    for prop in all_props:
        target_vals = [_get_property_value(objects[i], prop) for i in target_indices]
        non_target_vals = [_get_property_value(objects[i], prop) for i in non_target_indices]

        if all(target_vals) and not any(non_target_vals):
            return (prop, True)
        if not any(target_vals) and all(non_target_vals):
            return (prop, False)
    return None


def check_conjunction(
    target_indices: List[int],
    non_target_indices: List[int],
    objects: List[Dict],
    all_props: List[str],
    max_conjuncts: int = 2,
) -> Optional[Tuple[str, bool]]:
    if not target_indices or not non_target_indices:
        return None

    for p1, p2 in combinations(all_props, max_conjuncts):
        conj_name = f"{p1}&{p2}"
        target_vals = [_get_property_value(objects[i], conj_name) for i in target_indices]
        non_target_vals = [_get_property_value(objects[i], conj_name) for i in non_target_indices]
        if all(target_vals) and not any(non_target_vals):
            return (conj_name, True)
        if not any(target_vals) and all(non_target_vals):
            return (conj_name, False)
    return None


def check_negation(
    target_indices: List[int],
    non_target_indices: List[int],
    objects: List[Dict],
    all_props: List[str],
) -> Optional[Tuple[str, bool]]:
    if not target_indices or not non_target_indices:
        return None

    for p1 in all_props:
        for p2 in all_props:
            if p1 == p2:
                continue
            neg_name = f"{p1}&!{p2}"
            target_vals = [_get_property_value(objects[i], neg_name) for i in target_indices]
            non_target_vals = [_get_property_value(objects[i], neg_name) for i in non_target_indices]
            if all(target_vals) and not any(non_target_vals):
                return (neg_name, True)
            if not any(target_vals) and all(non_target_vals):
                return (neg_name, False)
    return None


def analyze_task(
    task_id: str,
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    all_props: List[str],
) -> Dict[str, Any]:
    result = {
        "task_id": task_id,
        "n_train_pairs": len(train_pairs),
        "category": "unknown",
        "selector_found": False,
        "selector_expression": None,
        "selector_type": None,
        "n_objects_per_pair": [],
        "target_type": None,
        "notes": [],
    }

    per_pair_analyses = []
    for idx, (inp, out) in enumerate(train_pairs):
        objects = _extract_objects_with_properties(inp)
        objects = _add_relational_properties(objects)

        for i, obj in enumerate(objects):
            obj["_obj_idx"] = i
            obj["_n_objects"] = len(objects)

        result["n_objects_per_pair"].append(len(objects))

        if len(objects) < 2:
            result["category"] = "object_representation_failure"
            result["notes"].append(f"pair {idx}: only {len(objects)} objects")
            return result

        target_info = infer_target_objects(inp, out, objects)
        if target_info is None:
            result["notes"].append(f"pair {idx}: no change detected")
            continue

        if target_info["target_type"] == "size_change":
            result["category"] = "size_change_task"
            result["target_type"] = "size_change"
            result["notes"].append(f"pair {idx}: input shape {inp.shape} != output shape {out.shape}")
            per_pair_analyses.append(target_info)
            continue

        per_pair_analyses.append({
            "pair_idx": idx,
            "target_info": target_info,
            "n_objects": len(objects),
            "objects": objects,
        })

    if result["category"] == "size_change_task":
        # For size-change tasks, check if we can identify target via crop logic
        # (still useful even though shapes differ)
        return result

    if not per_pair_analyses:
        result["category"] = "unknown"
        result["notes"].append("no analyzable pairs")
        return result

    # Check if selector works across ALL pairs
    valid_pairs = [a for a in per_pair_analyses if isinstance(a, dict) and "objects" in a]
    if not valid_pairs:
        return result

    # Try single property across all pairs
    for prop in all_props:
        works_all = True
        for pa in valid_pairs:
            ti = pa["target_info"]
            target_idx = ti.get("target_indices") or ti.get("changed_indices", [])
            all_idx = list(range(pa["n_objects"]))
            non_target_idx = [i for i in all_idx if i not in target_idx]
            if not target_idx or not non_target_idx:
                works_all = False
                break
            sp = check_single_property(target_idx, non_target_idx, pa["objects"], [prop])
            if sp is None:
                works_all = False
                break
        if works_all:
            result["selector_found"] = True
            result["selector_expression"] = prop
            result["selector_type"] = "single_property"
            result["category"] = "single_property_sufficient"
            return result

    # Try conjunction across all pairs (limited search)
    top_props = all_props[:40]  # limit for combinatorial reasons
    for p1, p2 in combinations(top_props, 2):
        conj = f"{p1}&{p2}"
        works_all = True
        for pa in valid_pairs:
            ti = pa["target_info"]
            target_idx = ti.get("target_indices") or ti.get("changed_indices", [])
            all_idx = list(range(pa["n_objects"]))
            non_target_idx = [i for i in all_idx if i not in target_idx]
            if not target_idx or not non_target_idx:
                works_all = False
                break

            target_vals = [_get_property_value(pa["objects"][i], conj) for i in target_idx]
            non_target_vals = [_get_property_value(pa["objects"][i], conj) for i in non_target_idx]
            if not (all(target_vals) and not any(non_target_vals)):
                if not (not any(target_vals) and all(non_target_vals)):
                    works_all = False
                    break
        if works_all:
            result["selector_found"] = True
            result["selector_expression"] = conj
            result["selector_type"] = "conjunction"
            result["category"] = "conjunction_needed"
            return result

    # Try negation across all pairs
    for p1 in top_props[:20]:
        for p2 in top_props[:20]:
            if p1 == p2:
                continue
            neg = f"{p1}&!{p2}"
            works_all = True
            for pa in valid_pairs:
                ti = pa["target_info"]
                target_idx = ti.get("target_indices") or ti.get("changed_indices", [])
                all_idx = list(range(pa["n_objects"]))
                non_target_idx = [i for i in all_idx if i not in target_idx]
                if not target_idx or not non_target_idx:
                    works_all = False
                    break
                target_vals = [_get_property_value(pa["objects"][i], neg) for i in target_idx]
                non_target_vals = [_get_property_value(pa["objects"][i], neg) for i in non_target_idx]
                if not (all(target_vals) and not any(non_target_vals)):
                    if not (not any(target_vals) and all(non_target_vals)):
                        works_all = False
                        break
            if works_all:
                result["selector_found"] = True
                result["selector_expression"] = neg
                result["selector_type"] = "negation"
                result["category"] = "negation_needed"
                return result

    # Classify the failure type based on what's happening in the pairs
    has_multi_target = any(
        len(pa.get("target_info", {}).get("target_indices", [])) > 1
        for pa in valid_pairs if isinstance(pa, dict) and "target_info" in pa
    )
    has_bg_change = any(
        pa.get("target_info", {}).get("bg_changed", False)
        for pa in valid_pairs if isinstance(pa, dict) and "target_info" in pa
    )
    has_region_target = has_bg_change and not any(
        pa.get("target_info", {}).get("target_indices", [])
        for pa in valid_pairs if isinstance(pa, dict) and "target_info" in pa
    )

    # Check for per-pair selectors that exist but aren't consistent
    per_pair_selectors = []
    for pa in valid_pairs:
        ti = pa["target_info"]
        target_idx = ti.get("target_indices") or ti.get("changed_indices", [])
        all_idx = list(range(pa["n_objects"]))
        non_target_idx = [i for i in all_idx if i not in target_idx]
        if target_idx and non_target_idx:
            sp = check_single_property(target_idx, non_target_idx, pa["objects"], all_props)
            per_pair_selectors.append(sp)
        else:
            per_pair_selectors.append(None)

    if all(s is not None for s in per_pair_selectors) and len(set(s[0] for s in per_pair_selectors if s)) > 1:
        result["category"] = "pattern_membership_needed"
        result["notes"].append(f"per-pair selectors differ: {[s[0] if s else None for s in per_pair_selectors]}")
    elif has_region_target:
        result["category"] = "region_not_object"
    elif has_multi_target:
        result["category"] = "multi_object_target"
    else:
        result["category"] = "unknown"
        result["notes"].append("no single/conjunction/negation selector found across all pairs")

    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=OUTPUT_DIR)
    parser.add_argument("--max-tasks", type=int, default=0)
    args = parser.parse_args()
    output_dir = args.output_dir

    print("=" * 60)
    print("  Selector-Target Gap Analysis")
    print("=" * 60)

    os.makedirs(output_dir, exist_ok=True)

    print("\nLoading ARC tasks...")
    arc_task_list = load_arc_tasks(ARC_ROOT)
    tasks = {t.task_id: t for t in arc_task_list}
    print(f"  Loaded {len(tasks)} tasks")

    print("\nLoading v2 results...")
    v2_results = load_v2_results()
    unsolved_ids = get_unsolved_task_ids(v2_results)
    print(f"  {len(unsolved_ids)} unsolved tasks in focused eval")

    if args.max_tasks > 0:
        unsolved_ids = unsolved_ids[:args.max_tasks]
        print(f"  Limited to {len(unsolved_ids)} tasks")

    all_props = _all_property_names()
    print(f"  {len(all_props)} properties in language")

    results = []
    for i, task_id in enumerate(unsolved_ids):
        if task_id not in tasks:
            continue
        task = tasks[task_id]
        train_pairs = [
            (ex.input_grid, ex.output_grid) for ex in task.train
            if ex.output_grid is not None
        ]
        if not train_pairs:
            continue

        analysis = analyze_task(task_id, train_pairs, all_props)
        results.append(analysis)

        if (i + 1) % 10 == 0:
            found = sum(1 for r in results if r["selector_found"])
            print(f"  [{i+1}/{len(unsolved_ids)}] selector found: {found}/{len(results)}")

    # Write outputs
    csv_path = os.path.join(output_dir, "selector_target_gap.csv")
    csv_fields = [
        "task_id", "category", "selector_found", "selector_expression",
        "selector_type", "n_train_pairs", "target_type",
    ]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)

    # JSONL with full details
    jsonl_path = os.path.join(output_dir, "selector_target_examples.jsonl")
    with open(jsonl_path, "w") as f:
        for r in results:
            row = {k: v for k, v in r.items() if k != "n_objects_per_pair" or True}
            f.write(json.dumps(row, default=str) + "\n")

    # Summary
    category_counts = defaultdict(int)
    for r in results:
        category_counts[r["category"]] += 1

    md_path = os.path.join(output_dir, "selector_target_gap_summary.md")
    lines = [
        "# Selector-Target Gap Analysis\n\n",
        f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n",
        f"Total unsolved tasks analyzed: {len(results)}\n",
        f"Properties in language: {len(all_props)}\n\n",
        "## Category Breakdown\n\n",
        "| Category | Count | % |\n",
        "|----------|-------|---|\n",
    ]
    for cat in FAILURE_CATEGORIES:
        count = category_counts.get(cat, 0)
        pct = 100 * count / max(len(results), 1)
        lines.append(f"| {cat} | {count} | {pct:.1f}% |\n")

    total_found = sum(1 for r in results if r["selector_found"])
    lines.append(f"\n## Key Finding\n\n")
    lines.append(f"- Selector found for {total_found}/{len(results)} unsolved tasks ({100*total_found/max(len(results),1):.1f}%)\n")
    lines.append(f"- Selector NOT found for {len(results)-total_found}/{len(results)} tasks\n\n")

    lines.append("## Tasks Where Selector Exists But System Failed\n\n")
    for r in results:
        if r["selector_found"]:
            lines.append(f"- **{r['task_id']}**: `{r['selector_expression']}` ({r['selector_type']})\n")

    lines.append("\n## Actionable Gap Categories\n\n")
    actionable = {
        "single_property_sufficient": "Property exists but system failed to use it -- wiring bug",
        "conjunction_needed": "Need conjunction selector support in proposal pipeline",
        "negation_needed": "Need negation selector support in proposal pipeline",
        "size_change_task": "Need size-aware operators (crop, extract, completion)",
        "object_representation_failure": "Need alternative object extraction (AdapterGenesis)",
        "region_not_object": "Target is a region, not a connected component",
        "multi_object_target": "Multiple target objects with different properties",
        "pattern_membership_needed": "Selector varies per pair -- need pattern abstraction",
    }
    for cat, desc in actionable.items():
        count = category_counts.get(cat, 0)
        if count > 0:
            lines.append(f"- **{cat}** ({count}): {desc}\n")

    with open(md_path, "w") as f:
        f.writelines(lines)

    print(f"\n{'='*60}")
    print(f"  ANALYSIS COMPLETE")
    print(f"{'='*60}")
    print(f"  Total analyzed: {len(results)}")
    print(f"  Selector found: {total_found}")
    for cat, count in sorted(category_counts.items(), key=lambda x: -x[1]):
        print(f"    {cat}: {count}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
