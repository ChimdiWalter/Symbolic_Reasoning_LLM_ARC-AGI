"""Composed frontier operators: select-then-transform patterns.

These operators combine property-based object selection (including extended
properties) with output transformations beyond simple filtering. Each operator
follows the standard frontier operator interface: trigger/propose/execute.

Implemented families:
  - SelectThenRecolorOperator: select by property, recolor survivors
  - SelectThenCropExtractOperator: select by property, crop to bounding box
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

import numpy as np

from reasoning_project.frontier_operator_registry import FrontierOperator, _to_list
from reasoning_project.reasoning_engine import (
    GridDomainAdapter,
    _extract_objects_with_properties,
    _add_relational_properties,
    _classify_kept_removed,
    _get_property_value,
    _all_property_names,
)
from reasoning_project.property_expansion import PropertyExpansionEngine

if TYPE_CHECKING:
    from reasoning_project.adaptive_orchestrator import TaskAnalysis


def _get_all_properties_including_expanded(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> List[str]:
    core_props = _all_property_names()
    try:
        engine = PropertyExpansionEngine()
        expanded = engine.get_all_property_names()
        base = list(dict.fromkeys(core_props + expanded))
    except Exception:
        base = core_props

    conj = _find_useful_conjunctions(train_pairs, base)
    return base + conj


def _find_useful_conjunctions(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    props: List[str],
) -> List[str]:
    """Pre-filter conjunction candidates that have discriminative potential."""
    from reasoning_project.reasoning_engine import (
        _extract_objects_with_properties,
        _classify_kept_removed,
        _get_property_value,
    )

    pair_data = []
    for inp, out in train_pairs:
        objects = _extract_objects_full(inp)
        result = _classify_kept_removed(objects, inp, out)
        if result is None:
            return []
        kept_idx, removed_idx = result
        pvecs = {}
        for p in props:
            pvecs[p] = [_get_property_value(objects[i], p) for i in range(len(objects))]
        pair_data.append((kept_idx, removed_idx, pvecs))

    useful = []
    for p in props:
        has_t = has_f = False
        for _, _, pv in pair_data:
            for v in pv[p]:
                if v:
                    has_t = True
                else:
                    has_f = True
                if has_t and has_f:
                    break
            if has_t and has_f:
                break
        if has_t and has_f:
            useful.append(p)

    conjunctions = []
    for i, p1 in enumerate(useful):
        for p2 in useful[i + 1:]:
            for pol1 in [True, False]:
                for pol2 in [True, False]:
                    ok = True
                    n_match = n_no = 0
                    for kept_idx, removed_idx, pvecs in pair_data:
                        for ki in kept_idx:
                            v = (pvecs[p1][ki] == pol1) and (pvecs[p2][ki] == pol2)
                            if v:
                                n_match += 1
                            else:
                                n_no += 1
                        for ri in removed_idx:
                            v = (pvecs[p1][ri] == pol1) and (pvecs[p2][ri] == pol2)
                            if v:
                                n_match += 1
                            else:
                                n_no += 1

                    if n_match < 2 or n_no < 2:
                        continue

                    p1s = p1 if pol1 else f"!{p1}"
                    p2s = p2 if pol2 else f"!{p2}"
                    conjunctions.append(f"{p1s}&{p2s}")

    return conjunctions


def _extract_objects_full(grid: np.ndarray) -> List[Dict[str, Any]]:
    objects = _extract_objects_with_properties(grid)
    _add_relational_properties(objects, grid, grid.shape[0], grid.shape[1])
    return objects


def _infer_recolor_map(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    prop: str,
    keep_when_true: bool,
) -> Optional[Dict[int, int]]:
    recolor_map: Dict[int, int] = {}

    for inp, out in train_pairs:
        if inp.shape != out.shape:
            return None

        objects = _extract_objects_full(inp)
        if len(objects) < 2:
            return None

        kept_objs = []
        removed_count = 0
        for obj in objects:
            val = _get_property_value(obj, prop)
            if val == keep_when_true:
                kept_objs.append(obj)
            else:
                removed_count += 1

        if not kept_objs or removed_count == 0:
            return None

        for obj in kept_objs:
            mask = obj["mask"]
            out_vals = out[mask]
            nz = out_vals[out_vals != 0]
            if len(nz) == 0:
                continue
            out_color = int(np.bincount(nz).argmax())
            in_color = obj["primary_color"]
            if in_color == out_color:
                continue
            if in_color in recolor_map and recolor_map[in_color] != out_color:
                return None
            recolor_map[in_color] = out_color

        for obj in objects:
            val = _get_property_value(obj, prop)
            if val != keep_when_true:
                mask = obj["mask"]
                out_at_removed = out[mask]
                if np.any(out_at_removed != 0):
                    return None

    return recolor_map if recolor_map else None


def _execute_select_recolor(
    grid: np.ndarray,
    prop: str,
    keep_when_true: bool,
    recolor_map: Dict[int, int],
) -> Optional[np.ndarray]:
    objects = _extract_objects_full(grid)
    if len(objects) < 2:
        return None

    result = grid.copy()
    kept = 0
    removed = 0
    for obj in objects:
        val = _get_property_value(obj, prop)
        if val == keep_when_true:
            kept += 1
            old_color = obj["primary_color"]
            if old_color in recolor_map:
                result[obj["mask"]] = recolor_map[old_color]
        else:
            removed += 1
            result[obj["mask"]] = 0

    if kept == 0 or removed == 0:
        return None
    return result


def _execute_select_crop(
    grid: np.ndarray,
    prop: str,
    keep_when_true: bool,
) -> Optional[np.ndarray]:
    objects = _extract_objects_full(grid)
    if len(objects) < 2:
        return None

    kept_masks = []
    removed_count = 0
    for obj in objects:
        val = _get_property_value(obj, prop)
        if val == keep_when_true:
            kept_masks.append(obj["mask"])
        else:
            removed_count += 1

    if not kept_masks or removed_count == 0:
        return None

    combined = np.zeros_like(grid, dtype=bool)
    for m in kept_masks:
        combined |= m

    rows, cols = np.where(combined)
    if len(rows) == 0:
        return None

    r_min, r_max = int(rows.min()), int(rows.max())
    c_min, c_max = int(cols.min()), int(cols.max())

    cropped = np.zeros((r_max - r_min + 1, c_max - c_min + 1), dtype=grid.dtype)
    crop_mask = combined[r_min:r_max+1, c_min:c_max+1]
    cropped[crop_mask] = grid[r_min:r_max+1, c_min:c_max+1][crop_mask]
    return cropped


class SelectThenRecolorOperator(FrontierOperator):
    """Select objects by property (including expanded properties), recolor survivors.

    Solves tasks where: objects are selected by a discriminative property,
    removed objects become background, and kept objects change color according
    to a consistent mapping.
    """
    name = "select_then_recolor"

    def trigger(self, analysis: "TaskAnalysis") -> bool:
        if analysis.property_trace.get("has_discriminative_property"):
            return True
        pairs = analysis.object_trace.get("pairs", [])
        if pairs and all(not p.get("size_change") for p in pairs):
            return True
        return False

    def propose(self, analysis, train_pairs, test_inputs):
        proposals = []
        all_props = _get_all_properties_including_expanded(train_pairs)

        for prop in all_props:
            for keep_when_true in [True, False]:
                recolor_map = _infer_recolor_map(train_pairs, prop, keep_when_true)
                if recolor_map is None:
                    continue

                consistent = True
                for inp, out in train_pairs:
                    pred = _execute_select_recolor(inp, prop, keep_when_true, recolor_map)
                    if pred is None or not np.array_equal(pred, out):
                        consistent = False
                        break

                if not consistent:
                    continue

                loo_ok = True
                for i in range(len(train_pairs)):
                    held_inp, held_out = train_pairs[i]
                    pred = _execute_select_recolor(held_inp, prop, keep_when_true, recolor_map)
                    if pred is None or not np.array_equal(pred, held_out):
                        loo_ok = False
                        break

                if not loo_ok:
                    continue

                def make_execute(p=prop, k=keep_when_true, rm=recolor_map):
                    def execute_fn(grid):
                        return _execute_select_recolor(grid, p, k, rm)
                    return execute_fn

                proposals.append({
                    "operator": "select_then_recolor",
                    "operator_family": "select_then_recolor",
                    "family": "select_then_recolor",
                    "confidence": 0.65,
                    "selector": prop,
                    "parameters": {
                        "property": prop,
                        "keep_when_true": keep_when_true,
                        "recolor_map": {str(k): v for k, v in recolor_map.items()},
                    },
                    "execute": make_execute(),
                    "source": "operator_coverage_gap_repair",
                    "proof_obligations": [],
                })
                return proposals

        return proposals


class SelectThenCropExtractOperator(FrontierOperator):
    """Select objects by extended property, crop to bounding box.

    Solves tasks where: output is a smaller grid containing only the
    selected objects cropped to their bounding box. Uses extended properties
    not just the core 59.
    """
    name = "select_then_crop_extract"

    def trigger(self, analysis: "TaskAnalysis") -> bool:
        pairs = analysis.object_trace.get("pairs", [])
        has_size_change = any(p.get("size_change") for p in pairs)
        if has_size_change:
            return True
        return False

    def propose(self, analysis, train_pairs, test_inputs):
        proposals = []
        all_props = _get_all_properties_including_expanded(train_pairs)

        for prop in all_props:
            for keep_when_true in [True, False]:
                consistent = True
                for inp, out in train_pairs:
                    pred = _execute_select_crop(inp, prop, keep_when_true)
                    if pred is None or not np.array_equal(pred, out):
                        consistent = False
                        break

                if not consistent:
                    continue

                loo_ok = True
                for i in range(len(train_pairs)):
                    held_inp, held_out = train_pairs[i]
                    pred = _execute_select_crop(held_inp, prop, keep_when_true)
                    if pred is None or not np.array_equal(pred, held_out):
                        loo_ok = False
                        break

                if not loo_ok:
                    continue

                def make_execute(p=prop, k=keep_when_true):
                    def execute_fn(grid):
                        return _execute_select_crop(grid, p, k)
                    return execute_fn

                proposals.append({
                    "operator": "select_then_crop_extract",
                    "operator_family": "select_then_crop_extract",
                    "family": "select_then_crop_extract",
                    "confidence": 0.65,
                    "selector": prop,
                    "parameters": {
                        "property": prop,
                        "keep_when_true": keep_when_true,
                    },
                    "execute": make_execute(),
                    "source": "operator_coverage_gap_repair",
                    "proof_obligations": [],
                })
                return proposals

        return proposals
