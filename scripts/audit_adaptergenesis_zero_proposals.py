"""Root-cause audit: why AdapterGenesis produced 0 proposals on 50 triage tasks.

Traces each adapter on each task through the full pipeline to classify
exactly where failure occurs.

Usage:
    source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate
    PYTHONPATH=src python3.11 scripts/audit_adaptergenesis_zero_proposals.py
"""
from __future__ import annotations

import csv
import json
import os
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from reasoning_project.view_adapters import (
    FrameInteriorAdapter,
    ColorLayerAdapter,
    ObjectInObjectAdapter,
    SymmetryAxisAdapter,
    RepeatedMotifAdapter,
)
from reasoning_project.reasoning_engine import (
    GridDomainAdapter,
    _extract_objects_with_properties,
    _add_relational_properties,
    _classify_kept_removed,
    _find_discriminative_property_extended,
    _apply_filter,
    _apply_filter_recolor,
    _apply_filter_extract,
)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs" / "full_novel_reasoning_pipeline_v2" / "failure_driven_adaptergenesis_v2_2026_06_21"
ARC_CHALLENGES = ROOT / "data" / "arc" / "arc-agi_training_challenges.json"
ARC_SOLUTIONS = ROOT / "data" / "arc" / "arc-agi_training_solutions.json"
TRIAGE_CSV = (ROOT / "outputs" / "full_novel_reasoning_pipeline_v2"
              / "adaptergenesis_arc1000_rejected_triage_2026_06_20"
              / "rejected_task_triage_set.csv")

FAILURE_CLASSES = [
    "no_adapter_can_apply",
    "adapter_can_apply_but_lift_failed",
    "lift_succeeds_but_no_operator_found",
    "operator_found_but_projection_failed",
    "projection_succeeds_but_train_mismatch",
    "train_passes_but_LOO_fails",
    "LOO_passes_but_proof_fails",
    "proof_passes_but_falsification_fails",
    "test_mismatch",
    "timeout",
    "unknown",
]

ALL_ADAPTERS = [
    ("frame_interior", FrameInteriorAdapter()),
    ("color_layer", ColorLayerAdapter()),
    ("object_in_object", ObjectInObjectAdapter()),
    ("symmetry_axis", SymmetryAxisAdapter()),
    ("repeated_motif", RepeatedMotifAdapter()),
]


def load_arc_data():
    with open(ARC_CHALLENGES) as f:
        challenges = json.load(f)
    with open(ARC_SOLUTIONS) as f:
        solutions = json.load(f)
    return challenges, solutions


def load_triage_ids():
    ids = []
    with open(TRIAGE_CSV) as f:
        reader = csv.DictReader(f)
        for row in reader:
            ids.append(row["task_id"])
    return ids


def load_task(task_id, challenges, solutions):
    task = challenges[task_id]
    sol = solutions.get(task_id, [])
    train_pairs = []
    for pair in task["train"]:
        inp = np.array(pair["input"], dtype=int)
        out = np.array(pair["output"], dtype=int)
        train_pairs.append((inp, out))
    test_inputs = []
    test_outputs = []
    for i, t in enumerate(task["test"]):
        test_inputs.append(np.array(t["input"], dtype=int))
        if i < len(sol):
            test_outputs.append(np.array(sol[i], dtype=int))
        elif "output" in t:
            test_outputs.append(np.array(t["output"], dtype=int))
    return train_pairs, test_inputs, test_outputs if test_outputs else None


def trace_adapter_on_task(
    adapter_name: str,
    adapter,
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
    test_outputs: Optional[List[np.ndarray]],
) -> Dict[str, Any]:
    """Trace exactly where adapter pipeline fails for one task."""
    result = {
        "adapter": adapter_name,
        "can_apply_all_inputs": False,
        "can_apply_all_outputs": False,
        "can_apply_counts": {"inputs": 0, "outputs": 0, "total_inputs": len(train_pairs)},
        "lift_succeeded": False,
        "lifted_objects_per_pair": [],
        "discriminative_property_found": False,
        "property_name": None,
        "filter_train_consistent": False,
        "recolor_train_consistent": False,
        "extract_train_consistent": False,
        "filter_pixel_errors": [],
        "recolor_pixel_errors": [],
        "extract_pixel_errors": [],
        "failure_class": "unknown",
        "failure_detail": "",
    }

    # Step 1: can_apply on all train inputs?
    apply_input_count = 0
    apply_output_count = 0
    for inp, out in train_pairs:
        try:
            if adapter.can_apply(inp):
                apply_input_count += 1
        except Exception as e:
            result["failure_detail"] = f"can_apply error: {e}"
        try:
            if adapter.can_apply(out):
                apply_output_count += 1
        except Exception:
            pass

    result["can_apply_counts"]["inputs"] = apply_input_count
    result["can_apply_counts"]["outputs"] = apply_output_count
    result["can_apply_all_inputs"] = (apply_input_count == len(train_pairs))
    result["can_apply_all_outputs"] = (apply_output_count == len(train_pairs))

    if apply_input_count == 0:
        result["failure_class"] = "no_adapter_can_apply"
        result["failure_detail"] = f"adapter {adapter_name} cannot apply to any input"
        return result

    # Step 2: lift train pairs
    try:
        lifted = adapter.lift_train_pairs(train_pairs)
        if not lifted or len(lifted) != len(train_pairs):
            result["failure_class"] = "adapter_can_apply_but_lift_failed"
            result["failure_detail"] = f"lift returned {len(lifted) if lifted else 0} pairs, expected {len(train_pairs)}"
            return result
        for li, lo in lifted:
            if li is None or lo is None:
                result["failure_class"] = "adapter_can_apply_but_lift_failed"
                result["failure_detail"] = "lift returned None pair"
                return result
            if not isinstance(li, np.ndarray) or not isinstance(lo, np.ndarray):
                result["failure_class"] = "adapter_can_apply_but_lift_failed"
                result["failure_detail"] = "lift returned non-array"
                return result
        result["lift_succeeded"] = True
    except Exception as e:
        result["failure_class"] = "adapter_can_apply_but_lift_failed"
        result["failure_detail"] = f"lift exception: {e}"
        return result

    # Step 3: extract objects from lifted view and check discrimination
    obj_counts = []
    classification_ok = True
    for linp, lout in lifted:
        try:
            objs = _extract_objects_with_properties(linp)
            objs = _add_relational_properties(objs, linp)
            obj_counts.append(len(objs))
            if len(objs) < 2:
                classification_ok = False
                continue
            kept, removed = _classify_kept_removed(linp, lout, objs)
            if not kept and not removed:
                classification_ok = False
        except Exception:
            obj_counts.append(0)
            classification_ok = False
    result["lifted_objects_per_pair"] = obj_counts

    if not classification_ok or max(obj_counts) < 2:
        result["failure_class"] = "lift_succeeds_but_no_operator_found"
        result["failure_detail"] = f"objects per pair: {obj_counts}, classification_ok={classification_ok}"
        # Still try to find discriminative property on first pair
        pass

    # Step 4: find discriminative property
    prop_name = None
    keep_when_true = None
    try:
        first_linp, first_lout = lifted[0]
        first_objs = _extract_objects_with_properties(first_linp)
        first_objs = _add_relational_properties(first_objs, first_linp)
        if len(first_objs) >= 2:
            kept, removed = _classify_kept_removed(first_linp, first_lout, first_objs)
            if kept or removed:
                prop_result = _find_discriminative_property_extended(
                    first_objs, kept, removed
                )
                if prop_result is not None:
                    prop_name, keep_when_true = prop_result
                    result["discriminative_property_found"] = True
                    result["property_name"] = prop_name
    except Exception:
        pass

    if prop_name is None:
        if result["failure_class"] == "unknown":
            result["failure_class"] = "lift_succeeds_but_no_operator_found"
            result["failure_detail"] = f"no discriminative property found, obj_counts={obj_counts}"
        return result

    # Step 5: try filter/recolor/extract on lifted views and check train consistency
    for strategy_name, apply_fn in [
        ("filter", _apply_filter),
        ("recolor", _apply_filter_recolor),
        ("extract", _apply_filter_extract),
    ]:
        pixel_errors = []
        all_match = True
        for linp, lout in lifted:
            try:
                objs = _extract_objects_with_properties(linp)
                objs = _add_relational_properties(objs, linp)
                if len(objs) < 2:
                    all_match = False
                    pixel_errors.append(-1)
                    continue
                applied = apply_fn(linp, objs, prop_name, keep_when_true)
                if applied is None:
                    all_match = False
                    pixel_errors.append(-2)
                    continue
                if applied.shape != lout.shape:
                    all_match = False
                    pixel_errors.append(-3)
                    continue
                n_wrong = int(np.sum(applied != lout))
                pixel_errors.append(n_wrong)
                if n_wrong > 0:
                    all_match = False
            except Exception:
                all_match = False
                pixel_errors.append(-4)

        result[f"{strategy_name}_pixel_errors"] = pixel_errors
        result[f"{strategy_name}_train_consistent"] = all_match

    # Step 6: if any strategy is train-consistent, try projection
    any_train_ok = (result["filter_train_consistent"]
                    or result["recolor_train_consistent"]
                    or result["extract_train_consistent"])

    if not any_train_ok:
        result["failure_class"] = "lift_succeeds_but_no_operator_found"
        best_errors = []
        for sn in ("filter", "recolor", "extract"):
            errs = result[f"{sn}_pixel_errors"]
            if errs and all(e >= 0 for e in errs):
                best_errors.append(f"{sn}:{sum(errs)}px")
        if best_errors:
            result["failure_detail"] = f"property={prop_name}, closest: {', '.join(best_errors)}"
        else:
            result["failure_detail"] = f"property={prop_name}, no strategy produced valid output on lifted view"
        return result

    # Step 7: check full pipeline (lift → operate → project → compare to original output)
    for strategy_name, apply_fn in [
        ("filter", _apply_filter),
        ("recolor", _apply_filter_recolor),
        ("extract", _apply_filter_extract),
    ]:
        if not result[f"{strategy_name}_train_consistent"]:
            continue

        full_pipeline_ok = True
        for idx, (inp, out) in enumerate(train_pairs):
            try:
                lp = adapter.lift_train_pairs([(inp, inp)])
                view = lp[0][0]
                objs = _extract_objects_with_properties(view)
                objs = _add_relational_properties(objs, view)
                applied = apply_fn(view, objs, prop_name, keep_when_true)
                if applied is None:
                    full_pipeline_ok = False
                    break
                projected = adapter.project(applied, inp)
                if projected is None:
                    result["failure_class"] = "operator_found_but_projection_failed"
                    result["failure_detail"] = f"{strategy_name} projection returned None on pair {idx}"
                    return result
                if projected.shape != out.shape:
                    result["failure_class"] = "projection_succeeds_but_train_mismatch"
                    result["failure_detail"] = f"{strategy_name} shape mismatch after projection: {projected.shape} vs {out.shape}"
                    full_pipeline_ok = False
                    break
                if not np.array_equal(projected, out):
                    n_wrong = int(np.sum(projected != out))
                    result["failure_class"] = "projection_succeeds_but_train_mismatch"
                    result["failure_detail"] = f"{strategy_name} {n_wrong}px wrong after projection on pair {idx}"
                    full_pipeline_ok = False
                    break
            except Exception as e:
                result["failure_class"] = "operator_found_but_projection_failed"
                result["failure_detail"] = f"{strategy_name} projection exception: {e}"
                full_pipeline_ok = False
                break

        if full_pipeline_ok:
            result["failure_class"] = "train_passes_but_LOO_fails"
            result["failure_detail"] = f"{strategy_name} with {prop_name} passes train on full pipeline"
            return result

    if result["failure_class"] == "unknown":
        result["failure_class"] = "lift_succeeds_but_no_operator_found"
        result["failure_detail"] = "train consistent on lifted view but projection breaks"

    return result


def audit_task(
    task_id: str,
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
    test_outputs: Optional[List[np.ndarray]],
) -> Dict[str, Any]:
    """Audit all adapters on one task."""
    task_result = {
        "task_id": task_id,
        "n_train_pairs": len(train_pairs),
        "input_shapes": [f"{inp.shape[0]}x{inp.shape[1]}" for inp, _ in train_pairs],
        "output_shapes": [f"{out.shape[0]}x{out.shape[1]}" for _, out in train_pairs],
        "size_changes": any(inp.shape != out.shape for inp, out in train_pairs),
        "n_colors_input": len(set(train_pairs[0][0].flatten().tolist())),
        "adapters": {},
        "best_adapter": None,
        "deepest_failure_class": "no_adapter_can_apply",
        "deepest_failure_detail": "",
    }

    failure_depth = {fc: i for i, fc in enumerate(FAILURE_CLASSES)}
    deepest = 0

    for adapter_name, adapter in ALL_ADAPTERS:
        trace = trace_adapter_on_task(
            adapter_name, adapter, train_pairs, test_inputs, test_outputs
        )
        task_result["adapters"][adapter_name] = trace

        depth = failure_depth.get(trace["failure_class"], 0)
        if depth > deepest:
            deepest = depth
            task_result["best_adapter"] = adapter_name
            task_result["deepest_failure_class"] = trace["failure_class"]
            task_result["deepest_failure_detail"] = trace["failure_detail"]

    return task_result


def main():
    os.makedirs(OUT, exist_ok=True)
    challenges, solutions = load_arc_data()
    triage_ids = load_triage_ids()
    print(f"Auditing {len(triage_ids)} tasks")

    all_results = []
    for i, task_id in enumerate(triage_ids):
        train_pairs, test_inputs, test_outputs = load_task(task_id, challenges, solutions)
        result = audit_task(task_id, train_pairs, test_inputs, test_outputs)
        all_results.append(result)

        print(f"[{i+1}/{len(triage_ids)}] {task_id}: {result['deepest_failure_class']}"
              f" (best={result['best_adapter']})")

    # Write CSV summary
    csv_path = OUT / "adaptergenesis_zero_proposal_root_cause.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "task_id", "n_train_pairs", "input_shapes", "output_shapes",
            "size_changes", "n_colors_input",
            "deepest_failure_class", "best_adapter", "deepest_failure_detail",
            "frame_can_apply", "frame_failure",
            "color_layer_can_apply", "color_layer_failure",
            "object_in_object_can_apply", "object_in_object_failure",
            "symmetry_can_apply", "symmetry_failure",
            "motif_can_apply", "motif_failure",
        ])
        for r in all_results:
            adapters = r["adapters"]
            writer.writerow([
                r["task_id"], r["n_train_pairs"],
                ";".join(r["input_shapes"]), ";".join(r["output_shapes"]),
                r["size_changes"], r["n_colors_input"],
                r["deepest_failure_class"], r["best_adapter"],
                r["deepest_failure_detail"],
                adapters["frame_interior"]["can_apply_all_inputs"],
                adapters["frame_interior"]["failure_class"],
                adapters["color_layer"]["can_apply_all_inputs"],
                adapters["color_layer"]["failure_class"],
                adapters["object_in_object"]["can_apply_all_inputs"],
                adapters["object_in_object"]["failure_class"],
                adapters["symmetry_axis"]["can_apply_all_inputs"],
                adapters["symmetry_axis"]["failure_class"],
                adapters["repeated_motif"]["can_apply_all_inputs"],
                adapters["repeated_motif"]["failure_class"],
            ])

    # Write markdown summary
    from collections import Counter
    failure_dist = Counter(r["deepest_failure_class"] for r in all_results)
    adapter_dist = Counter(r["best_adapter"] for r in all_results if r["best_adapter"])

    md_path = OUT / "adaptergenesis_zero_proposal_root_cause.md"
    with open(md_path, "w") as f:
        f.write("# AdapterGenesis Zero-Proposal Root Cause Audit\n\n")
        f.write(f"**Date:** 2026-06-21\n")
        f.write(f"**Tasks audited:** {len(triage_ids)}\n\n")

        f.write("## Failure Distribution (deepest reached per task)\n\n")
        f.write("| Failure Class | Count | % |\n")
        f.write("|---------------|-------|---|\n")
        for fc in FAILURE_CLASSES:
            cnt = failure_dist.get(fc, 0)
            pct = 100 * cnt / len(all_results) if all_results else 0
            f.write(f"| {fc} | {cnt} | {pct:.1f}% |\n")

        f.write("\n## Best Adapter per Task\n\n")
        f.write("| Adapter | Count |\n")
        f.write("|---------|-------|\n")
        for ad, cnt in adapter_dist.most_common():
            f.write(f"| {ad} | {cnt} |\n")
        no_adapter = sum(1 for r in all_results if r["best_adapter"] is None)
        if no_adapter:
            f.write(f"| (none) | {no_adapter} |\n")

        f.write("\n## Per-Adapter can_apply Summary\n\n")
        f.write("| Adapter | Tasks Where can_apply=True (all inputs) | % |\n")
        f.write("|---------|---------------------------------------|---|\n")
        for aname, _ in ALL_ADAPTERS:
            cnt = sum(1 for r in all_results
                      if r["adapters"][aname]["can_apply_all_inputs"])
            pct = 100 * cnt / len(all_results) if all_results else 0
            f.write(f"| {aname} | {cnt} | {pct:.1f}% |\n")

        f.write("\n## Key Bottleneck Analysis\n\n")
        lift_ok = sum(1 for r in all_results
                      if any(r["adapters"][a]["lift_succeeded"] for a, _ in ALL_ADAPTERS))
        prop_found = sum(1 for r in all_results
                         if any(r["adapters"][a]["discriminative_property_found"]
                                for a, _ in ALL_ADAPTERS))
        any_train_ok = sum(1 for r in all_results
                           if any(r["adapters"][a]["filter_train_consistent"]
                                  or r["adapters"][a]["recolor_train_consistent"]
                                  or r["adapters"][a]["extract_train_consistent"]
                                  for a, _ in ALL_ADAPTERS))
        f.write(f"- Tasks where at least 1 adapter can_apply: {lift_ok + sum(1 for r in all_results if any(r['adapters'][a]['can_apply_all_inputs'] for a, _ in ALL_ADAPTERS)) - lift_ok}\n")
        f.write(f"- Tasks where at least 1 adapter lifts successfully: {lift_ok}\n")
        f.write(f"- Tasks where discriminative property found on lifted view: {prop_found}\n")
        f.write(f"- Tasks where any strategy train-consistent on lifted view: {any_train_ok}\n")

        f.write("\n## Per-Task Details\n\n")
        f.write("| Task | Deepest Class | Best Adapter | Detail |\n")
        f.write("|------|---------------|-------------|--------|\n")
        for r in all_results:
            detail = r["deepest_failure_detail"][:80] if r["deepest_failure_detail"] else ""
            f.write(f"| {r['task_id']} | {r['deepest_failure_class']} | "
                    f"{r['best_adapter'] or '-'} | {detail} |\n")

        # Near-miss analysis
        near_misses = [r for r in all_results
                       if any(r["adapters"][a]["discriminative_property_found"]
                              for a, _ in ALL_ADAPTERS)]
        if near_misses:
            f.write(f"\n## Near Misses ({len(near_misses)} tasks found discriminative property on lifted view)\n\n")
            for r in near_misses:
                for aname, _ in ALL_ADAPTERS:
                    ad = r["adapters"][aname]
                    if ad["discriminative_property_found"]:
                        f.write(f"- **{r['task_id']}** via {aname}: property={ad['property_name']}, "
                                f"filter_errors={ad['filter_pixel_errors']}, "
                                f"recolor_errors={ad['recolor_pixel_errors']}, "
                                f"extract_errors={ad['extract_pixel_errors']}\n")

    # Write detailed JSON
    json_path = OUT / "adaptergenesis_zero_proposal_audit_detail.json"
    with open(json_path, "w") as f:
        json.dump(all_results, f, indent=2, default=str)

    print(f"\nDone. Results in {OUT}")
    print(f"\nFailure distribution:")
    for fc in FAILURE_CLASSES:
        cnt = failure_dist.get(fc, 0)
        if cnt > 0:
            print(f"  {fc}: {cnt}")


if __name__ == "__main__":
    main()
