"""Trace the 12 property-sufficient tasks through operator needs.

For each task: identify best_property, show why reconstruction fails,
try every operator schema, and map each failure to a concrete missing operator family.

Outputs:
    outputs/operator_gap_analysis/property_sufficient_12_operator_trace.csv
    outputs/operator_gap_analysis/property_sufficient_12_operator_report.md
"""
from __future__ import annotations

import csv
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reasoning_project.reasoning_engine import (
    GridDomainAdapter,
    ReasoningMemory,
    StructuralReasoner,
    _extract_objects_with_properties,
    _add_relational_properties,
    _classify_kept_removed,
)
from reasoning_project.operator_schemas import ALL_SCHEMAS, SchemaEvaluator


TASK_IDS = [
    "03560426", "05f2a901", "0e206a2e", "184a9768", "1a07d186", "1caeab9d",
    "2c737e39", "305b1341", "56dc2b01", "6855a6e4", "6a1e5592", "73c3b0d8",
]


def load_arc_tasks(arc_root: str = "data/arc") -> Dict[str, Dict]:
    tasks = {}
    chal = Path(arc_root) / "arc-agi_training_challenges.json"
    sol = Path(arc_root) / "arc-agi_training_solutions.json"
    if not chal.exists():
        return tasks
    with open(chal) as f:
        challenges = json.load(f)
    solutions = {}
    if sol.exists():
        with open(sol) as f:
            solutions = json.load(f)
    for tid in TASK_IDS:
        if tid not in challenges:
            continue
        data = challenges[tid]
        train_pairs = [(np.array(e["input"]), np.array(e["output"])) for e in data["train"]]
        test_inputs = [np.array(e["input"]) for e in data["test"]]
        test_outputs = []
        if tid in solutions:
            test_outputs = [np.array(o) for o in solutions[tid]]
        elif data["test"] and "output" in data["test"][0]:
            test_outputs = [np.array(e["output"]) for e in data["test"]]
        tasks[tid] = {
            "task_id": tid,
            "train_pairs": train_pairs,
            "test_inputs": test_inputs,
            "test_outputs": test_outputs,
        }
    return tasks


def analyze_reconstruction_diff(inp, out, adapter, prop, keep):
    """Analyze what the reconstruction does wrong and classify the gap."""
    objects = adapter.extract_objects(inp)
    if len(objects) < 2:
        return {"error": "too_few_objects"}

    result = _classify_kept_removed(objects, inp, out)
    if result is None:
        return {"error": "classify_none"}
    kept_idx, removed_idx = result

    pred = adapter.reconstruct_filtered(inp, objects, [i in kept_idx for i in range(len(objects))])
    if pred is None:
        return {"error": "reconstruct_none"}

    diff_mask = pred != out
    n_diff = int(diff_mask.sum())
    total = int(pred.size)

    pred_is_zero_where_diff = (pred[diff_mask] == 0).sum() if n_diff > 0 else 0
    out_nonzero_where_diff = (out[diff_mask] != 0).sum() if n_diff > 0 else 0

    removed_colors = set()
    for ri in removed_idx:
        rc = objects[ri].get("primary_color", -1)
        if rc >= 0:
            removed_colors.add(int(rc))

    diff_colors = set()
    if n_diff > 0:
        for v in out[diff_mask]:
            if v != 0:
                diff_colors.add(int(v))

    new_pixels_match_removed = diff_colors.issubset(removed_colors | {0})

    kept_positions = set()
    for ki in kept_idx:
        mask = objects[ki]["mask"]
        for r in range(mask.shape[0]):
            for c in range(mask.shape[1]):
                if mask[r, c]:
                    kept_positions.add((r, c))

    diff_positions = set()
    for r in range(diff_mask.shape[0]):
        for c in range(diff_mask.shape[1]):
            if diff_mask[r, c]:
                diff_positions.add((r, c))

    diff_near_kept = 0
    for dr, dc in diff_positions:
        for kr, kc in kept_positions:
            if abs(dr - kr) <= 2 and abs(dc - kc) <= 2:
                diff_near_kept += 1
                break

    removed_positions = set()
    for ri in removed_idx:
        mask = objects[ri]["mask"]
        for r in range(mask.shape[0]):
            for c in range(mask.shape[1]):
                if mask[r, c]:
                    removed_positions.add((r, c))

    diff_at_removed = len(diff_positions & removed_positions)
    diff_at_new = len(diff_positions - removed_positions - kept_positions)

    out_is_smaller = out.shape[0] < inp.shape[0] or out.shape[1] < inp.shape[1]
    out_is_cropped = out_is_smaller

    return {
        "n_diff_pixels": n_diff,
        "total_pixels": total,
        "pct_diff": round(100 * n_diff / total, 1),
        "pred_zero_where_diff": int(pred_is_zero_where_diff),
        "out_nonzero_where_diff": int(out_nonzero_where_diff),
        "removed_colors": sorted(removed_colors),
        "diff_colors": sorted(diff_colors),
        "new_pixels_match_removed": new_pixels_match_removed,
        "diff_near_kept_objects": diff_near_kept,
        "diff_at_removed_positions": diff_at_removed,
        "diff_at_new_positions": diff_at_new,
        "out_is_cropped": out_is_cropped,
    }


def classify_operator_need(diff_info: Dict) -> str:
    """Classify what operator family the task needs based on reconstruction diff."""
    if "error" in diff_info:
        return f"error_{diff_info['error']}"

    if diff_info.get("out_is_cropped"):
        return "crop_extract_advanced"

    if diff_info.get("diff_at_new_positions", 0) > diff_info.get("diff_at_removed_positions", 0):
        if diff_info.get("new_pixels_match_removed"):
            return "copy_or_project_removed_to_new_location"
        else:
            return "generate_new_pattern"

    if diff_info.get("pred_zero_where_diff", 0) > 0 and diff_info.get("out_nonzero_where_diff", 0) > 0:
        if diff_info.get("diff_near_kept_objects", 0) > diff_info.get("n_diff_pixels", 1) * 0.5:
            return "fill_or_extend_near_kept"
        if diff_info.get("new_pixels_match_removed"):
            return "relocate_removed_objects"
        return "spatial_transform_of_removed"

    return "unknown_operator_need"


def map_to_schema(need: str) -> Tuple[str, str]:
    """Map operator need to closest existing schema and suggested new schema."""
    mapping = {
        "copy_or_project_removed_to_new_location": ("CopyToPosition", "CopyToPosition or MarkerDirectedMove — removed objects reappear at new spatial locations"),
        "relocate_removed_objects": ("MarkerDirectedMove", "MarkerDirectedMove or GravityDrop — removed objects move to new positions"),
        "fill_or_extend_near_kept": ("LineExtendUntilCollision", "LineExtendUntilCollision or RegionColorPropagation — new pixels appear adjacent to kept objects"),
        "spatial_transform_of_removed": ("MarkerTargetTransform", "MarkerTargetTransform — removed objects undergo spatial transformation"),
        "generate_new_pattern": ("PatternRepetitionFill", "PatternRepetitionFill or ShapeCompleteFromBoundary — new pattern generated"),
        "crop_extract_advanced": ("ContainerContentExtract", "ContainerContentExtract or FilterCropRecolor — output is cropped subgrid"),
        "unknown_operator_need": ("FrameContentTransform", "Unclassified — needs manual inspection"),
    }
    closest, suggestion = mapping.get(need, ("unknown", "Manual investigation needed"))
    return closest, suggestion


def try_all_schemas(train_pairs, test_inputs, test_outputs):
    """Try every schema individually and report results."""
    results = []
    for schema in ALL_SCHEMAS:
        t0 = time.perf_counter()
        try:
            match = schema.detect(train_pairs)
            detected = match.matched
            if detected:
                val = schema.loo_validate(train_pairs, match)
                loo_passed = val.loo_passed
                loo_score = val.loo_score
                if loo_passed and test_inputs:
                    preds = [schema.apply(ti, match.bindings) for ti in test_inputs]
                    correct = test_outputs and all(
                        np.array_equal(p, e) for p, e in zip(preds, test_outputs)
                    )
                else:
                    correct = False
            else:
                loo_passed = False
                loo_score = 0.0
                correct = False
        except Exception as e:
            detected = False
            loo_passed = False
            loo_score = 0.0
            correct = False
        elapsed = time.perf_counter() - t0
        results.append({
            "schema": schema.name,
            "detected": detected,
            "loo_passed": loo_passed,
            "loo_score": round(loo_score, 3),
            "correct": correct,
            "time": round(elapsed, 2),
        })
    return results


def main():
    print("Loading ARC tasks...", flush=True)
    tasks = load_arc_tasks()
    print(f"Loaded {len(tasks)} tasks", flush=True)

    adapter = GridDomainAdapter()
    memory = ReasoningMemory()
    out_dir = Path("outputs/operator_gap_analysis")
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    report_lines = [
        "# Operator Gap Analysis: 12 Property-Sufficient Tasks\n",
        f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n",
        "## Summary\n",
    ]

    for tid in TASK_IDS:
        if tid not in tasks:
            print(f"  {tid}: not found", flush=True)
            continue
        task = tasks[tid]
        train_pairs = task["train_pairs"]
        test_inputs = task["test_inputs"]
        test_outputs = task.get("test_outputs", [])

        print(f"  Tracing {tid}...", end="", flush=True)
        t0 = time.perf_counter()

        # 1. Find best discriminative property
        reasoner = StructuralReasoner(adapter, memory=memory, min_train=2)
        best_prop = None
        best_keep = None
        props = adapter.property_names()
        for prop in props:
            all_match = True
            for inp, out in train_pairs:
                objects = adapter.extract_objects(inp)
                result = _classify_kept_removed(objects, inp, out)
                if result is None:
                    continue
                kept_idx, removed_idx = result
                for ki in kept_idx:
                    if not adapter.get_property(objects[ki], prop):
                        all_match = False
                        break
                for ri in removed_idx:
                    if adapter.get_property(objects[ri], prop):
                        all_match = False
                        break
                if not all_match:
                    break
            if all_match:
                best_prop = prop
                best_keep = True
                break

        # 2. Analyze reconstruction diffs
        diff_infos = []
        for inp, out in train_pairs:
            di = analyze_reconstruction_diff(inp, out, adapter, best_prop, best_keep)
            diff_infos.append(di)

        # 3. Classify operator need
        needs = [classify_operator_need(di) for di in diff_infos]
        dominant_need = max(set(needs), key=needs.count) if needs else "unknown"

        # 4. Try all schemas
        schema_results = try_all_schemas(train_pairs, test_inputs, test_outputs)
        any_schema_correct = any(s["correct"] for s in schema_results)
        any_schema_detected = any(s["detected"] for s in schema_results)
        detected_schemas = [s["schema"] for s in schema_results if s["detected"]]
        loo_schemas = [s["schema"] for s in schema_results if s["loo_passed"]]
        correct_schemas = [s["schema"] for s in schema_results if s["correct"]]

        # 5. Map to operator family
        closest, suggestion = map_to_schema(dominant_need)

        elapsed = time.perf_counter() - t0
        print(f" {dominant_need} ({elapsed:.1f}s)", flush=True)

        row = {
            "task_id": tid,
            "best_property": best_prop or "none",
            "property_discrimination_score": 1.0 if best_prop else 0.0,
            "loo_failure_mode": "reconstruction_mismatch",
            "old_reconstruction_attempted": "zeroing",
            "needed_operator_family": dominant_need,
            "closest_existing_operator": closest,
            "why_existing_failed": f"detected={any_schema_detected}, loo={len(loo_schemas)>0}, correct={any_schema_correct}",
            "suggested_operator_schema": suggestion,
            "detected_schemas": ";".join(detected_schemas),
            "loo_schemas": ";".join(loo_schemas),
            "correct_schemas": ";".join(correct_schemas),
            "n_diff_pct_pair0": diff_infos[0].get("pct_diff", -1) if diff_infos else -1,
        }
        rows.append(row)

        # Report detail
        report_lines.append(f"\n### {tid}\n")
        report_lines.append(f"- **Best property**: `{best_prop}` (keep={best_keep})")
        report_lines.append(f"- **Needed operator family**: `{dominant_need}`")
        report_lines.append(f"- **Closest existing schema**: `{closest}`")
        report_lines.append(f"- **Suggestion**: {suggestion}")
        report_lines.append(f"- **Schemas detected**: {detected_schemas or 'none'}")
        report_lines.append(f"- **Schemas LOO-passed**: {loo_schemas or 'none'}")
        report_lines.append(f"- **Schemas correct**: {correct_schemas or 'none'}")
        for i, di in enumerate(diff_infos):
            if "error" in di:
                report_lines.append(f"- **Recon diff pair {i}**: {di['error']}")
            else:
                report_lines.append(
                    f"- **Recon diff pair {i}**: {di['n_diff_pixels']}/{di['total_pixels']} "
                    f"({di['pct_diff']}%), pred_zero={di['pred_zero_where_diff']}, "
                    f"out_nonzero={di['out_nonzero_where_diff']}, "
                    f"diff_near_kept={di['diff_near_kept_objects']}, "
                    f"diff_at_removed={di['diff_at_removed_positions']}, "
                    f"diff_at_new={di['diff_at_new_positions']}, "
                    f"removed_colors={di['removed_colors']}, diff_colors={di['diff_colors']}, "
                    f"match_removed={di['new_pixels_match_removed']}"
                )

        for sr in schema_results:
            if sr["detected"]:
                report_lines.append(
                    f"  - `{sr['schema']}`: detected={sr['detected']}, "
                    f"loo={sr['loo_passed']} ({sr['loo_score']}), correct={sr['correct']}"
                )

    # Write CSV
    csv_path = out_dir / "property_sufficient_12_operator_trace.csv"
    if rows:
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

    # Write report
    report_path = out_dir / "property_sufficient_12_operator_report.md"
    report_lines.insert(3, "\n| Task | Property | Operator Need | Closest Schema | Any Correct |\n|------|----------|---------------|----------------|-------------|")
    for row in rows:
        report_lines.insert(4 + rows.index(row),
            f"| {row['task_id']} | {row['best_property']} | {row['needed_operator_family']} | "
            f"{row['closest_existing_operator']} | {row['correct_schemas'] or 'none'} |")

    with open(report_path, "w") as f:
        f.write("\n".join(report_lines) + "\n")

    # Summary
    need_dist = {}
    for r in rows:
        need = r["needed_operator_family"]
        need_dist[need] = need_dist.get(need, 0) + 1

    print(f"\nCSV: {csv_path}")
    print(f"Report: {report_path}")
    print(f"\nOperator need distribution:")
    for need, count in sorted(need_dist.items(), key=lambda x: -x[1]):
        print(f"  {need}: {count}")
    n_correct = sum(1 for r in rows if r["correct_schemas"])
    print(f"\nAny schema correct: {n_correct}/{len(rows)}")


if __name__ == "__main__":
    main()
