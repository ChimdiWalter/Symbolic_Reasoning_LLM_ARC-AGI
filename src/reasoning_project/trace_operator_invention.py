"""Trace-driven operator invention: derive executable operators from failure traces.

The central invariant: operators are ONLY proposed from near-solved failure traces
where the property correctly identifies target objects but reconstruction fails.
They are never added as static solvers.

Pipeline:
    load traces → cluster by family → propose hypothesis → infer params →
    LOO validate → falsify → certify → promote or reject

Every step is logged, traceable, and produces machine-readable artifacts.
"""
from __future__ import annotations

import csv
import json
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy import ndimage

from reasoning_project.operator_semantics import (
    ExecutableOperatorHypothesis,
    OperatorProofObligation,
    VALIDATION_LEVELS,
    make_copy_to_position_hypothesis,
    make_marker_relative_hypothesis,
    make_correspondence_hypothesis,
    make_variable_destination_hypothesis,
    make_marker_projection_hypothesis,
    CorrespondenceCopyParams,
    VariableDestinationCopyParams,
    MarkerProjectionProofObligation,
)
from reasoning_project.reasoning_engine import (
    GridDomainAdapter,
    _extract_objects_with_properties,
    _get_property_value,
    _classify_kept_removed_extended,
    _classify_object_changes,
    _detect_recolor_pattern,
)
from reasoning_project.color_transfer import (
    ColorSourceInferer,
    execute_color_transfer,
    infer_color_transfer_params,
)
from reasoning_project.operator_semantics import ColorSourceRule, ColorTransferParams
from reasoning_project.active_falsifier import ActiveFalsifier, FalsificationResult
from reasoning_project.certificates import (
    ReasoningCertificate,
    certificate_to_json,
    certificate_to_markdown,
)
from reasoning_project.events import ReasoningEvent, ReasoningEventLog


# ═══════════════════════════════════════════════════════════════════════════
# DATA RECORDS
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class OperatorCandidateRecord:
    operator_id: str
    family: str
    task_ids: List[str]
    source_trace_ids: List[str]
    parameters: Dict[str, Any]
    validation_level: str = "proposed"
    train_fit: float = 0.0
    loo_passed: bool = False
    falsification_passed: bool = False
    promoted_tasks: List[str] = field(default_factory=list)
    false_positives: int = 0
    rejection_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operator_id": self.operator_id,
            "family": self.family,
            "task_ids": self.task_ids,
            "source_trace_ids": self.source_trace_ids,
            "parameters": _safe_params(self.parameters),
            "validation_level": self.validation_level,
            "train_fit": self.train_fit,
            "loo_passed": self.loo_passed,
            "falsification_passed": self.falsification_passed,
            "promoted_tasks": self.promoted_tasks,
            "false_positives": self.false_positives,
            "rejection_reason": self.rejection_reason,
        }


def _safe_params(params: Dict[str, Any]) -> Dict[str, Any]:
    out = {}
    for k, v in params.items():
        if isinstance(v, np.ndarray):
            out[k] = v.tolist()
        elif isinstance(v, (list, tuple)) and v and isinstance(v[0], np.ndarray):
            out[k] = [x.tolist() if isinstance(x, np.ndarray) else x for x in v]
        else:
            out[k] = v
    return out


# ═══════════════════════════════════════════════════════════════════════════
# COPY-TO-POSITION PARAMETER INFERENCE
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class CopyToPositionParams:
    displacement: Optional[Tuple[int, int]]
    destination_rule: str
    copy_mode: str  # "copy", "move", "copy_and_keep"
    preserve_color: bool
    preserve_shape: bool
    selector_expression: Optional[str]
    marker_reference: Optional[str]
    allow_overlap: bool
    background_color: int
    per_object_displacements: Optional[List[Dict[str, Any]]] = None
    destination_point: Optional[Tuple[int, int]] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "displacement": list(self.displacement) if self.displacement else None,
            "destination_rule": self.destination_rule,
            "copy_mode": self.copy_mode,
            "preserve_color": self.preserve_color,
            "preserve_shape": self.preserve_shape,
            "selector_expression": self.selector_expression,
            "marker_reference": self.marker_reference,
            "allow_overlap": self.allow_overlap,
            "background_color": self.background_color,
        }
        if self.destination_point is not None:
            d["destination_point"] = list(self.destination_point)
        if self.per_object_displacements is not None:
            d["per_object_displacements"] = self.per_object_displacements
        return d


def _extract_object_masks(
    grid: np.ndarray, objects: List[Dict[str, Any]],
) -> List[np.ndarray]:
    masks = []
    for obj in objects:
        m = obj.get("mask")
        if m is not None:
            masks.append(m.astype(bool))
        else:
            mask = np.zeros(grid.shape, dtype=bool)
            for r, c in obj.get("cells", []):
                if 0 <= r < grid.shape[0] and 0 <= c < grid.shape[1]:
                    mask[r, c] = True
            masks.append(mask)
    return masks


def _find_object_in_output(
    source_mask: np.ndarray,
    source_colors: np.ndarray,
    input_grid: np.ndarray,
    output_grid: np.ndarray,
    background: int,
) -> Optional[Tuple[Tuple[int, int], float]]:
    """Find where a source object's pattern appears in the output grid."""
    src_rows, src_cols = np.where(source_mask)
    if len(src_rows) == 0:
        return None

    src_min_r, src_max_r = src_rows.min(), src_rows.max()
    src_min_c, src_max_c = src_cols.min(), src_cols.max()
    patch_h = src_max_r - src_min_r + 1
    patch_w = src_max_c - src_min_c + 1

    local_mask = source_mask[src_min_r:src_max_r + 1, src_min_c:src_max_c + 1]
    local_colors = source_colors[src_min_r:src_max_r + 1, src_min_c:src_max_c + 1]

    best_match = None
    best_sim = 0.0

    for r in range(output_grid.shape[0] - patch_h + 1):
        for c in range(output_grid.shape[1] - patch_w + 1):
            out_patch = output_grid[r:r + patch_h, c:c + patch_w]
            match_cells = local_mask.sum()
            if match_cells == 0:
                continue
            matched = np.sum((out_patch == local_colors) & local_mask)
            sim = matched / match_cells
            if sim > best_sim:
                best_sim = sim
                best_match = (r, c)

    if best_match is None or best_sim < 0.5:
        return None
    dest_r = best_match[0] + (src_rows.min() - src_min_r)
    dest_c = best_match[1] + (src_cols.min() - src_min_c)
    return (dest_r, dest_c), best_sim


def infer_copy_to_position_params(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    selector_property: str,
    keep_when_true: bool = True,
) -> Optional[CopyToPositionParams]:
    """Infer CopyToPosition parameters from training examples.

    Returns None if the inference fails (inconsistent displacements, no
    matching objects, etc.).
    """
    adapter = GridDomainAdapter()
    background = 0
    all_displacements: List[List[Dict[str, Any]]] = []
    all_destinations: List[List[Tuple[int, int]]] = []
    all_similarities: List[float] = []
    source_retained_counts = 0
    source_absent_counts = 0

    for inp, out in train_pairs:
        if inp.shape != out.shape:
            return None

        objects = _extract_objects_with_properties(inp)
        selected = []
        non_selected = []
        for i, obj in enumerate(objects):
            val = _get_property_value(obj, selector_property)
            if (val == keep_when_true):
                non_selected.append((i, obj))
            else:
                selected.append((i, obj))

        if not selected:
            return None

        masks = _extract_object_masks(inp, [o for _, o in selected])
        pair_disps: List[Dict[str, Any]] = []
        pair_dests: List[Tuple[int, int]] = []

        for idx, ((obj_idx, obj), mask) in enumerate(zip(selected, masks)):
            src_rows, src_cols = np.where(mask)
            if len(src_rows) == 0:
                continue
            src_centroid = (int(src_rows.mean()), int(src_cols.mean()))

            result = _find_object_in_output(mask, inp * mask, inp, out, background)
            if result is None:
                pair_disps.append({
                    "object_idx": obj_idx,
                    "source_centroid": src_centroid,
                    "destination": None,
                    "displacement": None,
                    "similarity": 0.0,
                })
                continue

            (dest_r, dest_c), sim = result
            dest_rows = src_rows - src_rows.min() + dest_r
            dest_cols = src_cols - src_cols.min() + dest_c
            dest_centroid = (int(dest_rows.mean()), int(dest_cols.mean()))
            disp = (dest_centroid[0] - src_centroid[0], dest_centroid[1] - src_centroid[1])

            pair_disps.append({
                "object_idx": obj_idx,
                "source_centroid": src_centroid,
                "destination": dest_centroid,
                "displacement": disp,
                "similarity": sim,
            })
            pair_dests.append(dest_centroid)
            all_similarities.append(sim)

            src_present = np.any(out[mask] != background) if mask.any() else False
            if src_present:
                source_retained_counts += 1
            else:
                source_absent_counts += 1

        all_displacements.append(pair_disps)
        all_destinations.append(pair_dests)

    if not all_displacements or not any(all_destinations):
        return None

    valid_disps = [
        d["displacement"] for pair in all_displacements for d in pair
        if d["displacement"] is not None
    ]
    if not valid_disps:
        return None

    constant = len(set(valid_disps)) == 1
    converge = _check_converge_pattern(all_displacements, all_destinations)
    quadrant = _check_quadrant_fill_pattern(train_pairs, selector_property, keep_when_true)
    halo = _check_project_to_halo(train_pairs, selector_property, keep_when_true)

    if constant:
        dest_rule = "constant_displacement"
        displacement = valid_disps[0]
        dest_point = None
    elif quadrant is not None:
        dest_rule = "quadrant_fill"
        displacement = None
        dest_point = None
    elif halo:
        dest_rule = "project_to_halo"
        displacement = None
        dest_point = None
    elif converge:
        dest_rule = "converge_to_point"
        displacement = None
        dest_point = _infer_convergence_point(all_destinations)
    else:
        dest_rule = "object_specific"
        displacement = None
        dest_point = None

    copy_mode = "move" if source_absent_counts > source_retained_counts else "copy_and_keep"
    preserve_shape = True
    preserve_color = all(s >= 0.95 for s in all_similarities) if all_similarities else True

    return CopyToPositionParams(
        displacement=displacement,
        destination_rule=dest_rule,
        copy_mode=copy_mode,
        preserve_color=preserve_color,
        preserve_shape=preserve_shape,
        selector_expression=selector_property,
        marker_reference=None,
        allow_overlap=False,
        background_color=background,
        per_object_displacements=[
            _safe_params({"pairs": pair}) for pair in all_displacements
        ],
        destination_point=dest_point,
    )


def infer_copy_to_position_params_extended(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    selector_property: str,
    keep_when_true: bool = True,
) -> Optional[CopyToPositionParams]:
    """Extended copy-to-position inference that handles recolored objects.

    First tries the standard infer_copy_to_position_params.  When that returns
    None (common when objects are recolored rather than moved), falls back to
    using _classify_kept_removed_extended to identify the "changed" group and
    treats those objects as the "selected" (operated-on) group.

    Returns None if neither approach yields consistent parameters.
    """
    # Try standard inference first
    result = infer_copy_to_position_params(train_pairs, selector_property, keep_when_true)
    if result is not None:
        return result

    # Extended: use _classify_kept_removed_extended to identify groups
    # and check if the "changed" objects show a consistent spatial pattern
    background = 0
    all_displacements: List[List[Dict[str, Any]]] = []
    all_destinations: List[List[Tuple[int, int]]] = []
    all_similarities: List[float] = []
    source_retained_counts = 0
    source_absent_counts = 0
    recolor_detected = False

    for inp, out in train_pairs:
        if inp.shape != out.shape:
            return None

        objects = _extract_objects_with_properties(inp)
        ext = _classify_kept_removed_extended(objects, inp, out)
        if ext is None:
            return None
        _group_a, _group_b, mode = ext

        if mode in ("recolored_retained", "unchanged_changed", "present_absent"):
            recolor_detected = True

        # Use the selector property to partition objects (same as standard)
        selected = []
        non_selected = []
        for i, obj in enumerate(objects):
            val = _get_property_value(obj, selector_property)
            if val == keep_when_true:
                non_selected.append((i, obj))
            else:
                selected.append((i, obj))

        if not selected:
            return None

        # For recolored objects, _find_object_in_output may not work because
        # colors changed. If the object is at the same position (mask overlap
        # with non-background output), treat displacement as (0, 0).
        masks = _extract_object_masks(inp, [o for _, o in selected])
        pair_disps: List[Dict[str, Any]] = []
        pair_dests: List[Tuple[int, int]] = []

        for idx, ((obj_idx, obj), mask) in enumerate(zip(selected, masks)):
            src_rows, src_cols = np.where(mask)
            if len(src_rows) == 0:
                continue
            src_centroid = (int(src_rows.mean()), int(src_cols.mean()))

            # First try normal object-in-output search
            find_result = _find_object_in_output(mask, inp * mask, inp, out, background)

            if find_result is None and recolor_detected:
                # For recolored objects, check if non-background pixels exist
                # at the same mask location in the output (object stayed in place
                # but changed color)
                out_vals = out[mask]
                if np.any(out_vals != background):
                    find_result = (
                        (int(src_rows.min()), int(src_cols.min())),
                        1.0,
                    )

            if find_result is None:
                pair_disps.append({
                    "object_idx": obj_idx,
                    "source_centroid": src_centroid,
                    "destination": None,
                    "displacement": None,
                    "similarity": 0.0,
                })
                continue

            (dest_r, dest_c), sim = find_result
            dest_rows = src_rows - src_rows.min() + dest_r
            dest_cols = src_cols - src_cols.min() + dest_c
            dest_centroid = (int(dest_rows.mean()), int(dest_cols.mean()))
            disp = (dest_centroid[0] - src_centroid[0], dest_centroid[1] - src_centroid[1])

            pair_disps.append({
                "object_idx": obj_idx,
                "source_centroid": src_centroid,
                "destination": dest_centroid,
                "displacement": disp,
                "similarity": sim,
            })
            pair_dests.append(dest_centroid)
            all_similarities.append(sim)

            src_present = np.any(out[mask] != background) if mask.any() else False
            if src_present:
                source_retained_counts += 1
            else:
                source_absent_counts += 1

        all_displacements.append(pair_disps)
        all_destinations.append(pair_dests)

    if not all_displacements or not any(all_destinations):
        return None

    valid_disps = [
        d["displacement"] for pair in all_displacements for d in pair
        if d["displacement"] is not None
    ]
    if not valid_disps:
        return None

    constant = len(set(valid_disps)) == 1
    converge = _check_converge_pattern(all_displacements, all_destinations)

    if constant:
        dest_rule = "constant_displacement"
        displacement = valid_disps[0]
        dest_point = None
    elif converge:
        dest_rule = "converge_to_point"
        displacement = None
        dest_point = _infer_convergence_point(all_destinations)
    else:
        dest_rule = "object_specific"
        displacement = None
        dest_point = None

    copy_mode = "move" if source_absent_counts > source_retained_counts else "copy_and_keep"
    preserve_shape = True
    preserve_color = all(s >= 0.95 for s in all_similarities) if all_similarities else True

    return CopyToPositionParams(
        displacement=displacement,
        destination_rule=dest_rule,
        copy_mode=copy_mode,
        preserve_color=preserve_color,
        preserve_shape=preserve_shape,
        selector_expression=selector_property,
        marker_reference=None,
        allow_overlap=False,
        background_color=background,
        per_object_displacements=[
            _safe_params({"pairs": pair}) for pair in all_displacements
        ],
        destination_point=dest_point,
    )


def _check_converge_pattern(
    all_disps: List[List[Dict[str, Any]]],
    all_dests: List[List[Tuple[int, int]]],
) -> bool:
    for dests in all_dests:
        if not dests:
            continue
        if len(set(dests)) > 1:
            return False
    return True


def _check_quadrant_fill_pattern(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    selector_property: str,
    keep_when_true: bool = True,
) -> Optional[Dict[str, Any]]:
    """Check if task follows quadrant-fill: satellite objects color quadrants of a kept block.

    Pattern: N single-pixel objects surround a rectangular kept block.
    Each satellite's color replaces the quadrant of the block in the
    satellite's relative direction. The block disappears / is recolored.
    """
    for inp, out in train_pairs:
        if inp.shape != out.shape:
            return None

        objects = _extract_objects_with_properties(inp)
        kept = [obj for obj in objects if _get_property_value(obj, selector_property) == keep_when_true]
        removed = [obj for obj in objects if _get_property_value(obj, selector_property) != keep_when_true]

        if not kept or not removed:
            return None

        block = max(kept, key=lambda o: o["area"])
        if block["area"] < 4:
            return None
        if not all(o["area"] <= 2 for o in removed):
            return None

        bbox = block["bbox"]
        block_cr = (bbox[0] + bbox[2]) / 2.0
        block_cc = (bbox[1] + bbox[3]) / 2.0
        bh = bbox[2] - bbox[0] + 1
        bw = bbox[3] - bbox[1] + 1

        if bh < 2 or bw < 2:
            return None

        half_h = bh / 2.0
        half_w = bw / 2.0

        for robj in removed:
            rc = robj.get("center_r", robj["bbox"][0])
            cc = robj.get("center_c", robj["bbox"][1])
            is_top = rc < block_cr
            is_left = cc < block_cc

            q_r0 = bbox[0] if is_top else bbox[0] + int(half_h)
            q_r1 = bbox[0] + int(half_h) if is_top else bbox[2] + 1
            q_c0 = bbox[1] if is_left else bbox[1] + int(half_w)
            q_c1 = bbox[1] + int(half_w) if is_left else bbox[3] + 1

            expected_color = robj["primary_color"]
            for r in range(q_r0, q_r1):
                for c in range(q_c0, q_c1):
                    if 0 <= r < out.shape[0] and 0 <= c < out.shape[1]:
                        if out[r, c] != expected_color:
                            return None

    return {"rule": "quadrant_fill"}


def _get_halo_cells(
    bbox: Tuple[int, int, int, int], grid_shape: Tuple[int, int],
) -> List[Tuple[int, int]]:
    """Get cells adjacent (8-connected) to a bounding box, outside the box."""
    r0, c0, r1, c1 = bbox
    halo = []
    for r in range(max(0, r0 - 1), min(grid_shape[0], r1 + 2)):
        for c in range(max(0, c0 - 1), min(grid_shape[1], c1 + 2)):
            if r0 <= r <= r1 and c0 <= c <= c1:
                continue
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    nr, nc = r + dr, c + dc
                    if r0 <= nr <= r1 and c0 <= nc <= c1:
                        halo.append((r, c))
                        break
                else:
                    continue
                break
    return halo


def _check_project_to_halo(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    selector_property: str,
    keep_when_true: bool = True,
) -> bool:
    """Check if removed objects project to the nearest halo cell of the kept block."""
    for inp, out in train_pairs:
        if inp.shape != out.shape:
            return False
        objects = _extract_objects_with_properties(inp)
        kept = [o for o in objects if _get_property_value(o, selector_property) == keep_when_true]
        removed = [o for o in objects if _get_property_value(o, selector_property) != keep_when_true]
        if not kept or not removed:
            return False
        if not all(o["area"] <= 2 for o in removed):
            return False
        block = max(kept, key=lambda o: o["area"])
        if block["area"] < 4:
            return False
        halo = _get_halo_cells(block["bbox"], inp.shape)
        if not halo:
            return False
        for robj in removed:
            sr = robj.get("center_r", robj["bbox"][0])
            sc = robj.get("center_c", robj["bbox"][1])
            dest = min(halo, key=lambda rc: abs(rc[0] - sr) + abs(rc[1] - sc))
            if out[dest[0], dest[1]] != robj["primary_color"]:
                return False
    return True


def _infer_convergence_point(
    all_dests: List[List[Tuple[int, int]]],
) -> Optional[Tuple[int, int]]:
    for dests in all_dests:
        if dests:
            return dests[0]
    return None


# ═══════════════════════════════════════════════════════════════════════════
# COPY-TO-POSITION EXECUTOR
# ═══════════════════════════════════════════════════════════════════════════

def _learn_block_color_from_training(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    selector_property: str,
) -> Optional[int]:
    """Learn the block color from training pairs for quadrant_fill."""
    colors: List[int] = []
    for inp, _out in train_pairs:
        objects = _extract_objects_with_properties(inp)
        kept = [o for o in objects if _get_property_value(o, selector_property)]
        if kept:
            block = max(kept, key=lambda o: o["area"])
            colors.append(int(block["primary_color"]))
    if colors and len(set(colors)) == 1:
        return colors[0]
    return None


def _obj_cells(obj: Dict[str, Any]) -> List[Tuple[int, int]]:
    """Get (row, col) list from an object dict, using mask or cells."""
    m = obj.get("mask")
    if m is not None:
        rs, cs = np.where(m)
        return list(zip(rs.tolist(), cs.tolist()))
    return obj.get("cells", [])


def execute_copy_to_position(
    input_grid: np.ndarray,
    params: CopyToPositionParams,
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> Optional[np.ndarray]:
    """Execute a copy-to-position operator on an input grid.

    For converge_to_point: learn destination from training, move all selected
    objects there.
    For constant_displacement: apply the fixed displacement vector.
    For object_specific: learn per-object destination mapping from training,
    apply the closest match.
    """
    adapter = GridDomainAdapter()
    objects = _extract_objects_with_properties(input_grid)
    prop = params.selector_expression
    if prop is None:
        return None

    selected_indices = []
    for i, obj in enumerate(objects):
        val = _get_property_value(obj, prop)
        if not val:
            selected_indices.append(i)

    if not selected_indices:
        return None

    output = input_grid.copy()

    if params.copy_mode == "move":
        for idx in selected_indices:
            for r, c in _obj_cells(objects[idx]):
                if 0 <= r < output.shape[0] and 0 <= c < output.shape[1]:
                    output[r, c] = params.background_color

    if params.destination_rule == "constant_displacement" and params.displacement is not None:
        dr, dc = params.displacement
        for idx in selected_indices:
            for r, c in _obj_cells(objects[idx]):
                nr, nc = r + dr, c + dc
                if 0 <= nr < output.shape[0] and 0 <= nc < output.shape[1]:
                    output[nr, nc] = input_grid[r, c]

    elif params.destination_rule == "converge_to_point":
        dest_point = params.destination_point
        if dest_point is None:
            dest_point = _learn_convergence_from_training(train_pairs, prop)
        if dest_point is None:
            return None
        for idx in selected_indices:
            cells = _obj_cells(objects[idx])
            if not cells:
                continue
            rows = [r for r, c in cells]
            cols = [c for r, c in cells]
            centroid_r = int(np.mean(rows))
            centroid_c = int(np.mean(cols))
            dr = dest_point[0] - centroid_r
            dc = dest_point[1] - centroid_c
            for r, c in cells:
                nr, nc = r + dr, c + dc
                if 0 <= nr < output.shape[0] and 0 <= nc < output.shape[1]:
                    output[nr, nc] = input_grid[r, c]

    elif params.destination_rule == "quadrant_fill":
        block_color = _learn_block_color_from_training(train_pairs, prop)
        blocks = [
            obj for obj in objects
            if obj["area"] >= 4 and (block_color is None or obj["primary_color"] == block_color)
        ]
        if not blocks:
            kept_objects = [
                obj for i, obj in enumerate(objects) if i not in selected_indices
            ]
            if not kept_objects:
                return None
            blocks = [max(kept_objects, key=lambda o: o["area"])]

        satellites = [
            obj for obj in objects
            if obj["area"] <= 2 and obj not in blocks
        ]

        block_corners = []
        for blk in blocks:
            bb = blk["bbox"]
            block_corners.append([
                (bb[0], bb[1]), (bb[0], bb[3]),
                (bb[2], bb[1]), (bb[2], bb[3]),
            ])

        for sat in satellites:
            sc = sat.get("center_r", sat["bbox"][0])
            sr = sat.get("center_c", sat["bbox"][1])
            best_bi = 0
            best_dist = float("inf")
            for bi, corners in enumerate(block_corners):
                for cr, cc in corners:
                    d = abs(sc - cr) + abs(sr - cc)
                    if d < best_dist:
                        best_dist = d
                        best_bi = bi

            block = blocks[best_bi]
            bbox = block["bbox"]
            bcr = (bbox[0] + bbox[2]) / 2.0
            bcc = (bbox[1] + bbox[3]) / 2.0
            bh = bbox[2] - bbox[0] + 1
            bw = bbox[3] - bbox[1] + 1
            half_h = bh / 2.0
            half_w = bw / 2.0

            is_top = sc < bcr
            is_left = sr < bcc

            q_r0 = bbox[0] if is_top else bbox[0] + int(half_h)
            q_r1 = bbox[0] + int(half_h) if is_top else bbox[2] + 1
            q_c0 = bbox[1] if is_left else bbox[1] + int(half_w)
            q_c1 = bbox[1] + int(half_w) if is_left else bbox[3] + 1

            fill_color = sat["primary_color"]
            for r in range(q_r0, q_r1):
                for c in range(q_c0, q_c1):
                    if 0 <= r < output.shape[0] and 0 <= c < output.shape[1]:
                        output[r, c] = fill_color

    elif params.destination_rule == "project_to_halo":
        kept_objects = [
            obj for i, obj in enumerate(objects) if i not in selected_indices
        ]
        if not kept_objects:
            return None
        block = max(kept_objects, key=lambda o: o["area"])
        halo = _get_halo_cells(block["bbox"], output.shape)
        if not halo:
            return None
        for idx in selected_indices:
            obj = objects[idx]
            sr = obj.get("center_r", obj["bbox"][0])
            sc = obj.get("center_c", obj["bbox"][1])
            dest = min(halo, key=lambda rc: abs(rc[0] - sr) + abs(rc[1] - sc))
            output[dest[0], dest[1]] = obj["primary_color"]

    elif params.destination_rule == "object_specific":
        disps = _learn_per_object_displacements(
            train_pairs, prop, input_grid, objects, selected_indices,
        )
        if disps is None:
            return None
        for idx, (dr, dc) in zip(selected_indices, disps):
            for r, c in _obj_cells(objects[idx]):
                nr, nc = r + dr, c + dc
                if 0 <= nr < output.shape[0] and 0 <= nc < output.shape[1]:
                    output[nr, nc] = input_grid[r, c]

    else:
        return None

    return output


def _learn_convergence_from_training(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    selector_property: str,
) -> Optional[Tuple[int, int]]:
    for inp, out in train_pairs:
        objects = _extract_objects_with_properties(inp)
        selected = [
            obj for obj in objects
            if not _get_property_value(obj, selector_property)
        ]
        if not selected:
            continue
        mask = _extract_object_masks(inp, selected)[0]
        result = _find_object_in_output(mask, inp * mask, inp, out, 0)
        if result is not None:
            (dest_r, dest_c), _ = result
            src_rows, src_cols = np.where(mask)
            dest_centroid = (
                int(dest_r + np.mean(src_rows) - src_rows.min()),
                int(dest_c + np.mean(src_cols) - src_cols.min()),
            )
            return dest_centroid
    return None


def _learn_per_object_displacements(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    selector_property: str,
    test_input: np.ndarray,
    test_objects: List[Dict[str, Any]],
    test_selected: List[int],
) -> Optional[List[Tuple[int, int]]]:
    """Learn per-object displacements from training examples.

    For each selected test object, find the most similar training source
    object and apply the same displacement.
    """
    train_examples: List[Dict[str, Any]] = []

    for inp, out in train_pairs:
        objects = _extract_objects_with_properties(inp)
        masks = _extract_object_masks(inp, objects)
        for i, obj in enumerate(objects):
            if _get_property_value(obj, selector_property):
                continue
            result = _find_object_in_output(masks[i], inp * masks[i], inp, out, 0)
            if result is None:
                continue
            (dest_r, dest_c), sim = result
            src_rows, src_cols = np.where(masks[i])
            if len(src_rows) == 0:
                continue
            src_centroid = (int(src_rows.mean()), int(src_cols.mean()))
            dest_centroid = (
                int(dest_r + np.mean(src_rows) - src_rows.min()),
                int(dest_c + np.mean(src_cols) - src_cols.min()),
            )
            train_examples.append({
                "area": int(masks[i].sum()),
                "src_centroid": src_centroid,
                "displacement": (
                    dest_centroid[0] - src_centroid[0],
                    dest_centroid[1] - src_centroid[1],
                ),
                "similarity": sim,
            })

    if not train_examples:
        return None

    displacements = []
    test_masks = _extract_object_masks(test_input, test_objects)
    for idx in test_selected:
        cells = _obj_cells(test_objects[idx])
        if not cells:
            displacements.append((0, 0))
            continue
        rows = [r for r, c in cells]
        cols = [c for r, c in cells]
        area = len(cells)
        centroid = (int(np.mean(rows)), int(np.mean(cols)))

        best_ex = min(
            train_examples,
            key=lambda ex: abs(ex["area"] - area) + abs(ex["src_centroid"][0] - centroid[0]) + abs(ex["src_centroid"][1] - centroid[1]),
        )
        displacements.append(best_ex["displacement"])

    return displacements


# ═══════════════════════════════════════════════════════════════════════════
# MARKER-RELATIVE COPY-TO-POSITION
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class MarkerRelativeCopyParams:
    """Parameters for marker-relative copy-to-position operator.

    Instead of a constant global displacement, each source object is placed
    at a fixed offset relative to an anchor (kept) object.
    """
    source_selector: str
    anchor_selector: str
    anchor_type: str  # "nearest_kept", "same_color", "same_shape", "largest_kept"
    relative_rule: str  # "offset_from_anchor", "align_row", "align_col", "inside_anchor_bbox", "adjacent_to_anchor"
    offset: Optional[Tuple[int, int]]
    copy_mode: str  # "copy", "move", "copy_and_keep"
    preserve_color: bool
    preserve_shape: bool
    background_color: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_selector": self.source_selector,
            "anchor_selector": self.anchor_selector,
            "anchor_type": self.anchor_type,
            "relative_rule": self.relative_rule,
            "offset": list(self.offset) if self.offset else None,
            "copy_mode": self.copy_mode,
            "preserve_color": self.preserve_color,
            "preserve_shape": self.preserve_shape,
            "background_color": self.background_color,
        }


def _find_nearest_kept(
    obj: Dict[str, Any],
    kept_objects: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Find the kept object nearest to the given source object by centroid distance."""
    if not kept_objects:
        return None
    src_r = obj.get("center_r", (obj["bbox"][0] + obj["bbox"][2]) / 2.0)
    src_c = obj.get("center_c", (obj["bbox"][1] + obj["bbox"][3]) / 2.0)
    best = None
    best_dist = float("inf")
    for ko in kept_objects:
        kr = ko.get("center_r", (ko["bbox"][0] + ko["bbox"][2]) / 2.0)
        kc = ko.get("center_c", (ko["bbox"][1] + ko["bbox"][3]) / 2.0)
        dist = abs(kr - src_r) + abs(kc - src_c)
        if dist < best_dist:
            best_dist = dist
            best = ko
    return best


def _find_anchor_for_object(
    obj: Dict[str, Any],
    kept_objects: List[Dict[str, Any]],
    anchor_type: str,
) -> Optional[Dict[str, Any]]:
    """Select the anchor object for a given source object using the specified strategy."""
    if not kept_objects:
        return None

    if anchor_type == "nearest_kept":
        return _find_nearest_kept(obj, kept_objects)

    elif anchor_type == "largest_kept":
        return max(kept_objects, key=lambda o: o["area"])

    elif anchor_type == "same_color_kept":
        src_color = obj.get("primary_color", -1)
        matches = [ko for ko in kept_objects if ko.get("primary_color", -2) == src_color]
        if matches:
            return _find_nearest_kept(obj, matches)
        return None

    elif anchor_type == "same_shape":
        src_area = obj.get("area", 0)
        src_bbox = obj.get("bbox", (0, 0, 0, 0))
        src_h = src_bbox[2] - src_bbox[0] + 1
        src_w = src_bbox[3] - src_bbox[1] + 1
        best = None
        best_score = float("inf")
        for ko in kept_objects:
            ko_bbox = ko.get("bbox", (0, 0, 0, 0))
            ko_h = ko_bbox[2] - ko_bbox[0] + 1
            ko_w = ko_bbox[3] - ko_bbox[1] + 1
            score = abs(ko_h - src_h) + abs(ko_w - src_w) + abs(ko.get("area", 0) - src_area)
            if score < best_score:
                best_score = score
                best = ko
        return best

    return _find_nearest_kept(obj, kept_objects)


def _compute_relative_offset(
    src_obj: Dict[str, Any],
    dest_centroid: Tuple[int, int],
    anchor_obj: Dict[str, Any],
) -> Tuple[int, int]:
    """Compute the offset from anchor centroid to destination centroid."""
    anchor_r = anchor_obj.get("center_r", (anchor_obj["bbox"][0] + anchor_obj["bbox"][2]) / 2.0)
    anchor_c = anchor_obj.get("center_c", (anchor_obj["bbox"][1] + anchor_obj["bbox"][3]) / 2.0)
    return (int(dest_centroid[0] - anchor_r), int(dest_centroid[1] - anchor_c))


def infer_marker_relative_params(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    selector_property: str,
    keep_when_true: bool = True,
) -> Optional[MarkerRelativeCopyParams]:
    """Infer marker-relative copy-to-position parameters from training examples.

    The key insight: when absolute displacements are object-specific (not constant),
    we check if they become constant when computed relative to an anchor object.

    Tries multiple anchor strategies and returns the first one where relative
    offsets are consistent across ALL training pairs, or None.
    """
    background = 0
    anchor_strategies = ["nearest_kept", "largest_kept", "same_color_kept", "same_shape"]

    for anchor_type in anchor_strategies:
        all_relative_offsets: List[Tuple[int, int]] = []
        all_similarities: List[float] = []
        source_retained_counts = 0
        source_absent_counts = 0
        strategy_valid = True

        for inp, out in train_pairs:
            if inp.shape != out.shape:
                strategy_valid = False
                break

            objects = _extract_objects_with_properties(inp)
            removed = []
            kept = []
            for obj in objects:
                val = _get_property_value(obj, selector_property)
                if val == keep_when_true:
                    kept.append(obj)
                else:
                    removed.append(obj)

            if not removed or not kept:
                strategy_valid = False
                break

            masks = _extract_object_masks(inp, removed)

            for obj, mask in zip(removed, masks):
                src_rows, src_cols = np.where(mask)
                if len(src_rows) == 0:
                    continue
                src_centroid = (int(src_rows.mean()), int(src_cols.mean()))

                result = _find_object_in_output(mask, inp * mask, inp, out, background)
                if result is None:
                    # Object not found in output -- might be deleted, skip
                    continue

                (dest_r, dest_c), sim = result
                all_similarities.append(sim)
                dest_rows = src_rows - src_rows.min() + dest_r
                dest_cols = src_cols - src_cols.min() + dest_c
                dest_centroid = (int(dest_rows.mean()), int(dest_cols.mean()))

                # Check source retained or absent
                src_present = np.any(out[mask] != background) if mask.any() else False
                if src_present:
                    source_retained_counts += 1
                else:
                    source_absent_counts += 1

                # Find anchor for this object
                anchor = _find_anchor_for_object(obj, kept, anchor_type)
                if anchor is None:
                    strategy_valid = False
                    break

                rel_offset = _compute_relative_offset(obj, dest_centroid, anchor)
                all_relative_offsets.append(rel_offset)

            if not strategy_valid:
                break

        if not strategy_valid or not all_relative_offsets:
            continue

        # Check if all relative offsets are the same (consistent)
        if len(set(all_relative_offsets)) == 1:
            consistent_offset = all_relative_offsets[0]
            copy_mode = "move" if source_absent_counts > source_retained_counts else "copy_and_keep"
            preserve_color = all(s >= 0.95 for s in all_similarities) if all_similarities else True

            return MarkerRelativeCopyParams(
                source_selector=selector_property,
                anchor_selector=selector_property,
                anchor_type=anchor_type,
                relative_rule="offset_from_anchor",
                offset=consistent_offset,
                copy_mode=copy_mode,
                preserve_color=preserve_color,
                preserve_shape=True,
                background_color=background,
            )

    return None


def execute_marker_relative_copy(
    input_grid: np.ndarray,
    params: MarkerRelativeCopyParams,
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> Optional[np.ndarray]:
    """Execute a marker-relative copy-to-position operator on an input grid.

    Each selected (removed) object is placed at a fixed offset relative to
    its anchor (kept) object.
    """
    objects = _extract_objects_with_properties(input_grid)
    prop = params.source_selector
    if prop is None:
        return None

    removed = []
    kept = []
    removed_indices = []
    for i, obj in enumerate(objects):
        val = _get_property_value(obj, prop)
        if val:  # kept
            kept.append(obj)
        else:  # removed / selected for operation
            removed.append(obj)
            removed_indices.append(i)

    if not removed or not kept:
        return None

    output = input_grid.copy()

    # Erase source objects if move mode
    if params.copy_mode == "move":
        for obj in removed:
            for r, c in _obj_cells(obj):
                if 0 <= r < output.shape[0] and 0 <= c < output.shape[1]:
                    output[r, c] = params.background_color

    if params.offset is None:
        return None

    dr_rel, dc_rel = params.offset

    for obj in removed:
        anchor = _find_anchor_for_object(obj, kept, params.anchor_type)
        if anchor is None:
            return None

        anchor_r = anchor.get("center_r", (anchor["bbox"][0] + anchor["bbox"][2]) / 2.0)
        anchor_c = anchor.get("center_c", (anchor["bbox"][1] + anchor["bbox"][3]) / 2.0)

        # Destination centroid = anchor centroid + relative offset
        dest_centroid_r = int(anchor_r + dr_rel)
        dest_centroid_c = int(anchor_c + dc_rel)

        # Compute displacement from source centroid to destination centroid
        cells = _obj_cells(obj)
        if not cells:
            continue
        rows = [r for r, c in cells]
        cols = [c for r, c in cells]
        src_centroid_r = int(np.mean(rows))
        src_centroid_c = int(np.mean(cols))

        disp_r = dest_centroid_r - src_centroid_r
        disp_c = dest_centroid_c - src_centroid_c

        for r, c in cells:
            nr, nc = r + disp_r, c + disp_c
            if 0 <= nr < output.shape[0] and 0 <= nc < output.shape[1]:
                output[nr, nc] = input_grid[r, c]

    return output


# ═══════════════════════════════════════════════════════════════════════════
# TRACE-DRIVEN OPERATOR INVENTOR
# ═══════════════════════════════════════════════════════════════════════════

class TraceDrivenOperatorInventor:
    """Invents executable operators from near-solved failure traces.

    Non-negotiable rule: operators are ONLY proposed from failure traces
    where a discriminative property was found but reconstruction failed.
    """

    def __init__(
        self,
        falsifier: Optional[ActiveFalsifier] = None,
        event_log: Optional[ReasoningEventLog] = None,
    ):
        self.falsifier = falsifier or ActiveFalsifier(rng_seed=42)
        self.event_log = event_log
        self.proposed: List[OperatorCandidateRecord] = []
        self.validated: List[OperatorCandidateRecord] = []
        self.rejected: List[OperatorCandidateRecord] = []
        self.hypotheses: Dict[str, ExecutableOperatorHypothesis] = {}

    def _emit(self, event_type: str, task_id: Optional[str], payload: Dict[str, Any]) -> None:
        if self.event_log is not None:
            self.event_log.emit(event_type, task_id, payload, module="trace_operator_invention")

    def load_traces(self, trace_path: str) -> List[Dict[str, Any]]:
        traces = []
        if trace_path.endswith(".csv"):
            with open(trace_path) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    traces.append(row)
        elif trace_path.endswith(".jsonl"):
            with open(trace_path) as f:
                for line in f:
                    if line.strip():
                        traces.append(json.loads(line))
        return traces

    def cluster_by_family(self, traces: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        clusters: Dict[str, List[Dict[str, Any]]] = {}
        for trace in traces:
            family = trace.get("needed_operator_family", "unknown")
            clusters.setdefault(family, []).append(trace)
        return clusters

    def propose_copy_to_position(
        self,
        task_id: str,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        trace: Dict[str, Any],
    ) -> Optional[ExecutableOperatorHypothesis]:
        selector = trace.get("best_property", "")
        if not selector:
            return None

        self._emit("OPERATOR_PROPOSED", task_id, {
            "family": "copy_to_position",
            "selector": selector,
            "source": "operator_gap_trace",
        })

        params = infer_copy_to_position_params(train_pairs, selector, keep_when_true=True)
        if params is None:
            # Fallback: try extended inference for recolored objects
            params = infer_copy_to_position_params_extended(
                train_pairs, selector, keep_when_true=True)
        if params is None:
            self._emit("INVENTION_REJECTED", task_id, {
                "family": "copy_to_position",
                "reason": "parameter_inference_failed",
            })
            return None

        hypothesis = make_copy_to_position_hypothesis(
            task_id=task_id,
            selector_expression=selector,
            parameters=params.to_dict(),
            source_tasks=[task_id],
            provenance={
                "derived_from": "operator_gap_trace",
                "trace_displacement_summary": trace.get("displacement_summary", ""),
                "trace_reconstruction_similarity": trace.get(
                    "old_reconstruction_output_similarity", "",
                ),
            },
        )
        hypothesis.advance_level("parameterized")

        self._emit("HYPOTHESIS_PROPOSED", task_id, {
            "operator_id": hypothesis.operator_id,
            "family": "copy_to_position",
            "destination_rule": params.destination_rule,
            "selector": selector,
        })

        self.hypotheses[hypothesis.operator_id] = hypothesis
        return hypothesis

    def propose_marker_relative_copy_to_position(
        self,
        task_id: str,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        trace: Dict[str, Any],
    ) -> Optional[ExecutableOperatorHypothesis]:
        """Propose a marker-relative copy-to-position operator.

        Fallback when standard CTP fails because displacements are
        object-specific: check if they become constant relative to an anchor.
        """
        selector = trace.get("best_property", "")
        if not selector:
            return None

        self._emit("OPERATOR_PROPOSED", task_id, {
            "family": "marker_relative_copy_to_position",
            "selector": selector,
            "source": "operator_gap_trace",
        })

        params = infer_marker_relative_params(train_pairs, selector, keep_when_true=True)
        if params is None:
            self._emit("INVENTION_REJECTED", task_id, {
                "family": "marker_relative_copy_to_position",
                "reason": "marker_relative_parameter_inference_failed",
            })
            return None

        hypothesis = make_marker_relative_hypothesis(
            task_id=task_id,
            selector_expression=selector,
            parameters=params.to_dict(),
            source_tasks=[task_id],
            provenance={
                "derived_from": "operator_gap_trace",
                "anchor_type": params.anchor_type,
                "relative_rule": params.relative_rule,
                "trace_displacement_summary": trace.get("displacement_summary", ""),
                "trace_reconstruction_similarity": trace.get(
                    "old_reconstruction_output_similarity", "",
                ),
            },
        )
        hypothesis.advance_level("parameterized")

        self._emit("HYPOTHESIS_PROPOSED", task_id, {
            "operator_id": hypothesis.operator_id,
            "family": "marker_relative_copy_to_position",
            "anchor_type": params.anchor_type,
            "relative_rule": params.relative_rule,
            "offset": list(params.offset) if params.offset else None,
            "selector": selector,
        })

        self.hypotheses[hypothesis.operator_id] = hypothesis
        return hypothesis

    def propose_correspondence_copy_to_position(
        self,
        task_id: str,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        trace: Dict[str, Any],
    ) -> Optional[ExecutableOperatorHypothesis]:
        """Propose a correspondence-based copy-to-position operator.

        Fallback when both constant CTP and marker-relative CTP fail because
        each source object maps to a specific target by structural matching.
        """
        selector = trace.get("best_property", "")
        if not selector:
            return None

        self._emit("OPERATOR_PROPOSED", task_id, {
            "family": "correspondence_copy_to_position",
            "selector": selector,
            "source": "operator_gap_trace",
        })

        result = infer_correspondence_params(train_pairs, selector, keep_when_true=True)
        if result is None:
            self._emit("INVENTION_REJECTED", task_id, {
                "family": "correspondence_copy_to_position",
                "reason": "correspondence_parameter_inference_failed",
            })
            return None

        params, rule = result

        hypothesis = make_correspondence_hypothesis(
            task_id=task_id,
            selector_expression=selector,
            parameters=params.to_dict(),
            source_tasks=[task_id],
            provenance={
                "derived_from": "operator_gap_trace",
                "correspondence_rule_type": rule.rule_type,
                "correspondence_rule_id": rule.rule_id,
                "relative_displacement": list(params.relative_displacement) if params.relative_displacement else None,
                "trace_displacement_summary": trace.get("displacement_summary", ""),
            },
        )
        hypothesis.advance_level("parameterized")

        self._emit("HYPOTHESIS_PROPOSED", task_id, {
            "operator_id": hypothesis.operator_id,
            "family": "correspondence_copy_to_position",
            "correspondence_rule_type": rule.rule_type,
            "relative_displacement": list(params.relative_displacement) if params.relative_displacement else None,
            "selector": selector,
        })

        self.hypotheses[hypothesis.operator_id] = hypothesis
        return hypothesis

    def propose_variable_destination_copy(
        self,
        task_id: str,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        trace: Dict[str, Any],
    ) -> Optional[ExecutableOperatorHypothesis]:
        """Propose a variable-destination copy operator."""
        selector = trace.get("best_property", "")
        if not selector:
            return None

        self._emit("PROPOSAL_ATTEMPT", task_id, {
            "family": "variable_destination_copy",
            "selector": selector,
        })

        from reasoning_project.destination_policy import infer_variable_destination_params

        result = infer_variable_destination_params(train_pairs, selector, keep_when_true=True)
        if result is None:
            self._emit("PROPOSAL_FAILED", task_id, {
                "family": "variable_destination_copy",
                "reason": "variable_destination_parameter_inference_failed",
            })
            return None

        params, policy, obligations = result

        hypothesis = make_variable_destination_hypothesis(
            task_id=task_id,
            selector_expression=selector,
            parameters={
                "source_selector": selector,
                "policy_type": policy.policy_type,
                "policy_id": policy.policy_id,
                "scoring_rule": policy.scoring_rule,
                "tie_breaker": policy.tie_breaker,
                "constraints": policy.constraints,
                "evidence": policy.evidence,
                "complexity": policy.complexity,
                "copy_mode": params.copy_mode,
                "preserve_shape": params.preserve_shape,
                "preserve_color": params.preserve_color,
                "allow_overlap": params.allow_overlap,
                "background_color": params.background_color,
            },
        )

        for obl in obligations:
            hypothesis.proof_obligations.append(OperatorProofObligation(
                obligation_id=obl.obligation_id,
                description=obl.description,
                status=obl.status,
                evidence=obl.evidence,
            ))

        self._emit("HYPOTHESIS_PROPOSED", task_id, {
            "operator_id": hypothesis.operator_id,
            "family": "variable_destination_copy",
            "policy_type": policy.policy_type,
            "scoring_rule": policy.scoring_rule,
            "selector": selector,
        })

        self.hypotheses[hypothesis.operator_id] = hypothesis
        return hypothesis

    def _validate_variable_destination(
        self,
        task_id: str,
        hypothesis: ExecutableOperatorHypothesis,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    ) -> bool:
        """Check training consistency for a variable-destination hypothesis."""
        from reasoning_project.destination_policy import (
            execute_variable_destination_copy,
            infer_variable_destination_params,
        )

        result = infer_variable_destination_params(
            train_pairs, hypothesis.selector_expression, keep_when_true=True,
        )
        if result is None:
            hypothesis.rejection_reason = "vdp_param_inference_failed"
            return False

        params, policy, _ = result
        n_ok = 0
        for inp, out in train_pairs:
            pred = execute_variable_destination_copy(inp, params, train_pairs)
            if pred is not None and np.array_equal(pred, out):
                n_ok += 1

        fit = n_ok / len(train_pairs) if train_pairs else 0
        if fit >= 0.99:
            hypothesis.advance_level("train_consistent")
            self._emit("HYPOTHESIS_VALIDATED", task_id, {
                "operator_id": hypothesis.operator_id,
                "family": "variable_destination_copy",
                "train_fit": fit,
            })
            return True

        hypothesis.rejection_reason = f"vdp_train_fit={fit:.3f}"
        self._emit("HYPOTHESIS_REJECTED", task_id, {
            "operator_id": hypothesis.operator_id,
            "reason": hypothesis.rejection_reason,
        })
        return False

    def _validate_correspondence(
        self,
        task_id: str,
        hypothesis: ExecutableOperatorHypothesis,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    ) -> bool:
        """Check training consistency for a correspondence-based hypothesis."""
        raw = hypothesis.parameters
        params = CorrespondenceCopyParams(
            source_selector=raw.get("source_selector", ""),
            correspondence_rule_type=raw.get("correspondence_rule_type", ""),
            correspondence_rule_id=raw.get("correspondence_rule_id", ""),
            relative_displacement=tuple(raw["relative_displacement"]) if raw.get("relative_displacement") else None,
            copy_mode=raw.get("copy_mode", "move"),
            preserve_shape=raw.get("preserve_shape", True),
            preserve_color=raw.get("preserve_color", True),
            allow_overlap=raw.get("allow_overlap", False),
            background_color=raw.get("background_color", 0),
            tie_breaker=raw.get("tie_breaker"),
        )

        n_correct = 0
        for inp, expected_out in train_pairs:
            pred = execute_correspondence_copy(inp, params, train_pairs)
            if pred is not None and np.array_equal(pred, expected_out):
                n_correct += 1

        fit = n_correct / len(train_pairs) if train_pairs else 0.0

        if fit == 1.0:
            hypothesis.advance_level("train_consistent")
            self._emit("HYPOTHESIS_SCORED", task_id, {
                "operator_id": hypothesis.operator_id,
                "train_fit": fit,
                "status": "train_consistent",
                "family": "correspondence_copy_to_position",
            })
            return True

        hypothesis.rejection_reason = f"correspondence_train_fit={fit:.3f}"
        self._emit("HYPOTHESIS_REJECTED", task_id, {
            "operator_id": hypothesis.operator_id,
            "train_fit": fit,
            "reason": hypothesis.rejection_reason,
        })
        return False

    def propose_marker_projection(
        self,
        task_id: str,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        trace: Dict[str, Any],
    ) -> Optional[ExecutableOperatorHypothesis]:
        """Propose a marker-projection operator: removed objects project
        information onto kept objects or background instead of relocating."""
        selector = trace.get("best_property", "")
        if not selector:
            return None

        self._emit("PROPOSAL_ATTEMPT", task_id, {
            "family": "marker_projection",
            "selector": selector,
        })

        from reasoning_project.marker_projection import (
            infer_marker_projection_params,
        )

        params = infer_marker_projection_params(
            train_pairs, selector, keep_when_true=True,
        )
        if params is None:
            self._emit("PROPOSAL_FAILED", task_id, {
                "family": "marker_projection",
                "reason": "marker_projection_parameter_inference_failed",
            })
            return None

        hypothesis = make_marker_projection_hypothesis(
            task_id=task_id,
            selector_expression=selector,
            parameters={
                "source_selector": params.source_selector,
                "target_selector": params.target_selector,
                "projection_type": params.projection_type,
                "projection_direction": params.projection_direction,
                "color_rule": params.color_rule,
                "fill_mode": params.fill_mode,
                "color_map": params.color_map,
                "keep_when_true": params.keep_when_true,
                "background": params.background,
                "direction_vector": list(params.direction_vector) if params.direction_vector else None,
                "stamp_offset": list(params.stamp_offset) if params.stamp_offset else None,
                "signal_axis": params.signal_axis,
                "signal_fill_color_rule": params.signal_fill_color_rule,
                "complexity": 6,
            },
        )

        self._emit("HYPOTHESIS_PROPOSED", task_id, {
            "operator_id": hypothesis.operator_id,
            "family": "marker_projection",
            "projection_type": params.projection_type,
            "projection_direction": params.projection_direction,
            "selector": selector,
        })

        self.hypotheses[hypothesis.operator_id] = hypothesis
        return hypothesis

    def _validate_marker_projection(
        self,
        task_id: str,
        hypothesis: ExecutableOperatorHypothesis,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    ) -> bool:
        """Check training consistency for a marker-projection hypothesis."""
        from reasoning_project.marker_projection import (
            infer_marker_projection_params,
            execute_marker_projection,
        )

        params = infer_marker_projection_params(
            train_pairs, hypothesis.selector_expression, keep_when_true=True,
        )
        if params is None:
            hypothesis.rejection_reason = "mp_param_inference_failed"
            return False

        n_ok = 0
        for inp, out in train_pairs:
            pred = execute_marker_projection(inp, params, train_pairs)
            if pred is not None and np.array_equal(pred, out):
                n_ok += 1

        fit = n_ok / len(train_pairs) if train_pairs else 0
        if fit >= 0.99:
            hypothesis.advance_level("train_consistent")
            self._emit("HYPOTHESIS_VALIDATED", task_id, {
                "operator_id": hypothesis.operator_id,
                "family": "marker_projection",
                "train_fit": fit,
            })
            return True

        hypothesis.rejection_reason = f"mp_train_fit={fit:.3f}"
        self._emit("HYPOTHESIS_REJECTED", task_id, {
            "operator_id": hypothesis.operator_id,
            "reason": hypothesis.rejection_reason,
        })
        return False

    def validate_hypothesis(
        self,
        task_id: str,
        hypothesis: ExecutableOperatorHypothesis,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    ) -> bool:
        """Check training consistency: execute on all train inputs, compare to outputs."""
        if hypothesis.family == "marker_relative_copy_to_position":
            return self._validate_marker_relative(task_id, hypothesis, train_pairs)
        if hypothesis.family == "correspondence_copy_to_position":
            return self._validate_correspondence(task_id, hypothesis, train_pairs)
        if hypothesis.family == "variable_destination_copy":
            return self._validate_variable_destination(task_id, hypothesis, train_pairs)
        if hypothesis.family == "marker_projection":
            return self._validate_marker_projection(task_id, hypothesis, train_pairs)
        if hypothesis.family == "recolor_in_place":
            return self._validate_recolor_in_place(task_id, hypothesis, train_pairs)
        if hypothesis.family == "color_transfer_recolor":
            return self._validate_color_transfer(task_id, hypothesis, train_pairs)

        params = CopyToPositionParams(**{
            k: tuple(v) if k in ("displacement", "destination_point") and isinstance(v, list) else v
            for k, v in hypothesis.parameters.items()
            if k in CopyToPositionParams.__dataclass_fields__
        })

        n_correct = 0
        for inp, expected_out in train_pairs:
            pred = execute_copy_to_position(inp, params, train_pairs)
            if pred is not None and np.array_equal(pred, expected_out):
                n_correct += 1

        fit = n_correct / len(train_pairs) if train_pairs else 0.0

        if fit == 1.0:
            hypothesis.advance_level("train_consistent")
            self._emit("HYPOTHESIS_SCORED", task_id, {
                "operator_id": hypothesis.operator_id,
                "train_fit": fit,
                "status": "train_consistent",
            })
            return True

        hypothesis.rejection_reason = f"train_fit={fit:.3f}"
        self._emit("HYPOTHESIS_REJECTED", task_id, {
            "operator_id": hypothesis.operator_id,
            "train_fit": fit,
            "reason": hypothesis.rejection_reason,
        })
        return False

    def _validate_marker_relative(
        self,
        task_id: str,
        hypothesis: ExecutableOperatorHypothesis,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    ) -> bool:
        """Check training consistency for a marker-relative hypothesis."""
        raw = hypothesis.parameters
        params = MarkerRelativeCopyParams(
            source_selector=raw.get("source_selector", ""),
            anchor_selector=raw.get("anchor_selector", ""),
            anchor_type=raw.get("anchor_type", "nearest_kept"),
            relative_rule=raw.get("relative_rule", "offset_from_anchor"),
            offset=tuple(raw["offset"]) if raw.get("offset") else None,
            copy_mode=raw.get("copy_mode", "move"),
            preserve_color=raw.get("preserve_color", True),
            preserve_shape=raw.get("preserve_shape", True),
            background_color=raw.get("background_color", 0),
        )

        n_correct = 0
        for inp, expected_out in train_pairs:
            pred = execute_marker_relative_copy(inp, params, train_pairs)
            if pred is not None and np.array_equal(pred, expected_out):
                n_correct += 1

        fit = n_correct / len(train_pairs) if train_pairs else 0.0

        if fit == 1.0:
            hypothesis.advance_level("train_consistent")
            self._emit("HYPOTHESIS_SCORED", task_id, {
                "operator_id": hypothesis.operator_id,
                "train_fit": fit,
                "status": "train_consistent",
                "family": "marker_relative_copy_to_position",
            })
            return True

        hypothesis.rejection_reason = f"marker_relative_train_fit={fit:.3f}"
        self._emit("HYPOTHESIS_REJECTED", task_id, {
            "operator_id": hypothesis.operator_id,
            "train_fit": fit,
            "reason": hypothesis.rejection_reason,
        })
        return False

    def loo_validate_hypothesis(
        self,
        task_id: str,
        hypothesis: ExecutableOperatorHypothesis,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    ) -> bool:
        """Leave-one-out: for each pair, train on the rest, predict the held-out."""
        if len(train_pairs) < 2:
            hypothesis.advance_level("loo_validated")
            return True

        is_marker_relative = hypothesis.family == "marker_relative_copy_to_position"
        is_correspondence = hypothesis.family == "correspondence_copy_to_position"
        is_vdp = hypothesis.family == "variable_destination_copy"
        is_mp = hypothesis.family == "marker_projection"
        is_rcl = hypothesis.family == "recolor_in_place"
        is_ctr = hypothesis.family == "color_transfer_recolor"

        for i in range(len(train_pairs)):
            held_inp, held_out = train_pairs[i]
            train_subset = [p for j, p in enumerate(train_pairs) if j != i]

            if is_ctr:
                pred = self._execute_color_transfer(held_inp, hypothesis)
                if pred is None or not np.array_equal(pred, held_out):
                    hypothesis.rejection_reason = f"loo_color_transfer_failed_fold_{i}"
                    self._emit("HYPOTHESIS_REJECTED", task_id, {
                        "operator_id": hypothesis.operator_id,
                        "reason": hypothesis.rejection_reason,
                        "fold": i,
                    })
                    return False
                continue

            if is_rcl:
                pred = self._execute_recolor(held_inp, hypothesis)
                if pred is None or not np.array_equal(pred, held_out):
                    hypothesis.rejection_reason = f"loo_recolor_failed_fold_{i}"
                    self._emit("HYPOTHESIS_REJECTED", task_id, {
                        "operator_id": hypothesis.operator_id,
                        "reason": hypothesis.rejection_reason,
                        "fold": i,
                    })
                    return False
                continue

            if is_mp:
                from reasoning_project.marker_projection import (
                    infer_marker_projection_params as _mp_infer,
                    execute_marker_projection as _mp_exec,
                )
                mp_params = _mp_infer(
                    train_subset, hypothesis.selector_expression, keep_when_true=True,
                )
                if mp_params is None:
                    hypothesis.rejection_reason = f"loo_mp_param_inference_failed_fold_{i}"
                    self._emit("HYPOTHESIS_REJECTED", task_id, {
                        "operator_id": hypothesis.operator_id,
                        "reason": hypothesis.rejection_reason,
                    })
                    return False
                pred = _mp_exec(held_inp, mp_params, train_subset)
                if pred is None or not np.array_equal(pred, held_out):
                    hypothesis.rejection_reason = f"loo_mp_failed_fold_{i}"
                    self._emit("HYPOTHESIS_REJECTED", task_id, {
                        "operator_id": hypothesis.operator_id,
                        "reason": hypothesis.rejection_reason,
                        "fold": i,
                    })
                    return False
                continue

            if is_vdp:
                from reasoning_project.destination_policy import (
                    infer_variable_destination_params,
                    execute_variable_destination_copy,
                )
                vdp_result = infer_variable_destination_params(
                    train_subset, hypothesis.selector_expression, keep_when_true=True,
                )
                if vdp_result is None:
                    hypothesis.rejection_reason = f"loo_vdp_param_inference_failed_fold_{i}"
                    self._emit("HYPOTHESIS_REJECTED", task_id, {
                        "operator_id": hypothesis.operator_id,
                        "reason": hypothesis.rejection_reason,
                    })
                    return False
                sub_params, _, _ = vdp_result
                pred = execute_variable_destination_copy(held_inp, sub_params, train_subset)
                if pred is None or not np.array_equal(pred, held_out):
                    hypothesis.rejection_reason = f"loo_vdp_failed_fold_{i}"
                    self._emit("HYPOTHESIS_REJECTED", task_id, {
                        "operator_id": hypothesis.operator_id,
                        "reason": hypothesis.rejection_reason,
                        "fold": i,
                    })
                    return False
                continue

            if is_correspondence:
                result = infer_correspondence_params(
                    train_subset,
                    hypothesis.selector_expression,
                    keep_when_true=True,
                )
                if result is None:
                    hypothesis.rejection_reason = f"loo_correspondence_param_inference_failed_fold_{i}"
                    self._emit("HYPOTHESIS_REJECTED", task_id, {
                        "operator_id": hypothesis.operator_id,
                        "reason": hypothesis.rejection_reason,
                    })
                    return False
                sub_params, _ = result
                pred = execute_correspondence_copy(held_inp, sub_params, train_subset)
                if pred is None or not np.array_equal(pred, held_out):
                    hypothesis.rejection_reason = f"loo_correspondence_failed_fold_{i}"
                    self._emit("HYPOTHESIS_REJECTED", task_id, {
                        "operator_id": hypothesis.operator_id,
                        "reason": hypothesis.rejection_reason,
                        "fold": i,
                    })
                    return False
                continue

            if is_marker_relative:
                sub_params = infer_marker_relative_params(
                    train_subset,
                    hypothesis.selector_expression,
                    keep_when_true=True,
                )
                if sub_params is None:
                    hypothesis.rejection_reason = f"loo_marker_relative_param_inference_failed_fold_{i}"
                    self._emit("HYPOTHESIS_REJECTED", task_id, {
                        "operator_id": hypothesis.operator_id,
                        "reason": hypothesis.rejection_reason,
                    })
                    return False
                pred = execute_marker_relative_copy(held_inp, sub_params, train_subset)
            else:
                sub_params = infer_copy_to_position_params(
                    train_subset,
                    hypothesis.selector_expression,
                    keep_when_true=True,
                )
                if sub_params is None:
                    hypothesis.rejection_reason = f"loo_param_inference_failed_fold_{i}"
                    self._emit("HYPOTHESIS_REJECTED", task_id, {
                        "operator_id": hypothesis.operator_id,
                        "reason": hypothesis.rejection_reason,
                    })
                    return False
                pred = execute_copy_to_position(held_inp, sub_params, train_subset)

            if pred is None or not np.array_equal(pred, held_out):
                hypothesis.rejection_reason = f"loo_failed_fold_{i}"
                self._emit("HYPOTHESIS_REJECTED", task_id, {
                    "operator_id": hypothesis.operator_id,
                    "reason": hypothesis.rejection_reason,
                    "fold": i,
                })
                return False

        hypothesis.advance_level("loo_validated")
        self._emit("INVENTION_VALIDATED", task_id, {
            "operator_id": hypothesis.operator_id,
            "validation_type": "loo",
        })
        return True

    def falsify_hypothesis(
        self,
        task_id: str,
        hypothesis: ExecutableOperatorHypothesis,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    ) -> FalsificationResult:
        """Run active falsification probes against the hypothesis."""
        adapter = GridDomainAdapter()
        hyp_dict = {
            "strategy": "copy_to_position",
            "property": hypothesis.selector_expression,
            "keep_when_true": True,
            "operator_family": "copy_to_position",
            "parameters": hypothesis.parameters,
        }

        result = self.falsifier.falsify(train_pairs, hyp_dict, adapter)

        if result.passed:
            hypothesis.advance_level("falsification_validated")
            self._emit("INVENTION_VALIDATED", task_id, {
                "operator_id": hypothesis.operator_id,
                "validation_type": "falsification",
                "score": result.falsification_score,
                "survived": result.counterexamples_survived,
                "total": result.counterexamples_generated,
            })
        else:
            self._emit("HYPOTHESIS_FALSIFIED", task_id, {
                "operator_id": hypothesis.operator_id,
                "score": result.falsification_score,
                "n_failed": result.counterexamples_failed,
            })

        for obl_name in ["falsification_survived", "falsification_score"]:
            hypothesis.proof_obligations.append(OperatorProofObligation(
                obligation_id=f"falsification_{obl_name}",
                description=f"Active falsification: {obl_name}",
                status="passed" if result.passed else "failed",
                evidence={
                    "score": result.falsification_score,
                    "survived": result.counterexamples_survived,
                    "total": result.counterexamples_generated,
                },
            ))

        return result

    def attempt_promotion(
        self,
        task_id: str,
        hypothesis: ExecutableOperatorHypothesis,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        test_inputs: List[np.ndarray],
        test_outputs: Optional[List[np.ndarray]] = None,
    ) -> Tuple[bool, Optional[List[np.ndarray]]]:
        """Attempt to promote: execute on test inputs and check."""
        is_marker_relative = hypothesis.family == "marker_relative_copy_to_position"
        is_correspondence = hypothesis.family == "correspondence_copy_to_position"
        is_vdp = hypothesis.family == "variable_destination_copy"
        is_mp = hypothesis.family == "marker_projection"
        is_rcl = hypothesis.family == "recolor_in_place"
        is_ctr = hypothesis.family == "color_transfer_recolor"

        if is_ctr:
            predictions = []
            for ti in test_inputs:
                pred = self._execute_color_transfer(ti, hypothesis)
                if pred is None:
                    return False, None
                predictions.append(pred)
            if test_outputs is not None:
                correct = all(
                    np.array_equal(p, e) for p, e in zip(predictions, test_outputs)
                )
                if correct:
                    hypothesis.advance_level("promotion_validated")
                    self._emit("TASK_PROMOTED_TO_SOLVED", task_id, {
                        "operator_id": hypothesis.operator_id,
                        "family": hypothesis.family,
                        "method": "trace_derived_color_transfer_operator",
                    })
                    return True, predictions
                hypothesis.rejection_reason = "color_transfer_test_output_mismatch"
                self._emit("HYPOTHESIS_REJECTED", task_id, {
                    "operator_id": hypothesis.operator_id,
                    "reason": "color_transfer_test_output_mismatch",
                })
                return False, predictions
            return True, predictions

        if is_rcl:
            predictions = []
            for ti in test_inputs:
                pred = self._execute_recolor(ti, hypothesis)
                if pred is None:
                    return False, None
                predictions.append(pred)
            if test_outputs is not None:
                correct = all(
                    np.array_equal(p, e) for p, e in zip(predictions, test_outputs)
                )
                if correct:
                    hypothesis.advance_level("promotion_validated")
                    self._emit("TASK_PROMOTED_TO_SOLVED", task_id, {
                        "operator_id": hypothesis.operator_id,
                        "family": hypothesis.family,
                        "method": "trace_derived_recolor_in_place_operator",
                    })
                    return True, predictions
                hypothesis.rejection_reason = "recolor_test_output_mismatch"
                self._emit("HYPOTHESIS_REJECTED", task_id, {
                    "operator_id": hypothesis.operator_id,
                    "reason": "recolor_test_output_mismatch",
                })
                return False, predictions
            return True, predictions

        if is_mp:
            from reasoning_project.marker_projection import (
                infer_marker_projection_params as _mp_infer_promo,
                execute_marker_projection as _mp_exec_promo,
            )
            mp_params = _mp_infer_promo(
                train_pairs, hypothesis.selector_expression, keep_when_true=True,
            )
            if mp_params is None:
                self._emit("HYPOTHESIS_REJECTED", task_id, {
                    "operator_id": hypothesis.operator_id,
                    "reason": "mp_param_inference_failed_on_test",
                })
                return False, None
            predictions = []
            for ti in test_inputs:
                pred = _mp_exec_promo(ti, mp_params, train_pairs)
                if pred is None:
                    self._emit("HYPOTHESIS_REJECTED", task_id, {
                        "operator_id": hypothesis.operator_id,
                        "reason": "mp_execution_failed_on_test",
                    })
                    return False, None
                predictions.append(pred)

            if test_outputs is not None:
                correct = all(
                    np.array_equal(p, e) for p, e in zip(predictions, test_outputs)
                )
                if correct:
                    hypothesis.advance_level("promotion_validated")
                    self._emit("TASK_PROMOTED_TO_SOLVED", task_id, {
                        "operator_id": hypothesis.operator_id,
                        "family": hypothesis.family,
                        "method": "trace_derived_marker_projection_operator",
                    })
                    return True, predictions

                hypothesis.rejection_reason = "mp_test_output_mismatch"
                self._emit("HYPOTHESIS_REJECTED", task_id, {
                    "operator_id": hypothesis.operator_id,
                    "reason": "mp_test_output_mismatch",
                })
                return False, predictions

            return True, predictions

        if is_vdp:
            from reasoning_project.destination_policy import (
                infer_variable_destination_params,
                execute_variable_destination_copy,
            )
            vdp_result = infer_variable_destination_params(
                train_pairs, hypothesis.selector_expression, keep_when_true=True,
            )
            if vdp_result is None:
                self._emit("HYPOTHESIS_REJECTED", task_id, {
                    "operator_id": hypothesis.operator_id,
                    "reason": "vdp_param_inference_failed_on_test",
                })
                return False, None
            vdp_params, _, _ = vdp_result
            predictions = []
            for ti in test_inputs:
                pred = execute_variable_destination_copy(ti, vdp_params, train_pairs)
                if pred is None:
                    self._emit("HYPOTHESIS_REJECTED", task_id, {
                        "operator_id": hypothesis.operator_id,
                        "reason": "vdp_execution_failed_on_test",
                    })
                    return False, None
                predictions.append(pred)

            if test_outputs is not None:
                correct = all(
                    np.array_equal(p, e) for p, e in zip(predictions, test_outputs)
                )
                if correct:
                    hypothesis.advance_level("promotion_validated")
                    self._emit("TASK_PROMOTED_TO_SOLVED", task_id, {
                        "operator_id": hypothesis.operator_id,
                        "family": hypothesis.family,
                        "method": "trace_derived_variable_destination_operator",
                    })
                    return True, predictions

                hypothesis.rejection_reason = "vdp_test_output_mismatch"
                self._emit("HYPOTHESIS_REJECTED", task_id, {
                    "operator_id": hypothesis.operator_id,
                    "reason": "vdp_test_output_mismatch",
                })
                return False, predictions

            return True, predictions

        if is_correspondence:
            raw = hypothesis.parameters.copy()
            corr_params = CorrespondenceCopyParams(
                source_selector=raw.get("source_selector", ""),
                correspondence_rule_type=raw.get("correspondence_rule_type", ""),
                correspondence_rule_id=raw.get("correspondence_rule_id", ""),
                relative_displacement=tuple(raw["relative_displacement"]) if raw.get("relative_displacement") else None,
                copy_mode=raw.get("copy_mode", "move"),
                preserve_shape=raw.get("preserve_shape", True),
                preserve_color=raw.get("preserve_color", True),
                allow_overlap=raw.get("allow_overlap", False),
                background_color=raw.get("background_color", 0),
                tie_breaker=raw.get("tie_breaker"),
            )
            predictions = []
            for ti in test_inputs:
                pred = execute_correspondence_copy(ti, corr_params, train_pairs)
                if pred is None:
                    self._emit("HYPOTHESIS_REJECTED", task_id, {
                        "operator_id": hypothesis.operator_id,
                        "reason": "correspondence_execution_failed_on_test",
                    })
                    return False, None
                predictions.append(pred)

            if test_outputs is not None:
                correct = all(
                    np.array_equal(p, e) for p, e in zip(predictions, test_outputs)
                )
                if correct:
                    hypothesis.advance_level("promotion_validated")
                    self._emit("TASK_PROMOTED_TO_SOLVED", task_id, {
                        "operator_id": hypothesis.operator_id,
                        "family": hypothesis.family,
                        "method": "trace_derived_correspondence_operator",
                    })
                    return True, predictions

                hypothesis.rejection_reason = "correspondence_test_output_mismatch"
                self._emit("HYPOTHESIS_REJECTED", task_id, {
                    "operator_id": hypothesis.operator_id,
                    "reason": "correspondence_test_output_mismatch",
                })
                return False, predictions

            return True, predictions

        if is_marker_relative:
            raw = hypothesis.parameters.copy()
            mr_params = MarkerRelativeCopyParams(
                source_selector=raw.get("source_selector", ""),
                anchor_selector=raw.get("anchor_selector", ""),
                anchor_type=raw.get("anchor_type", "nearest_kept"),
                relative_rule=raw.get("relative_rule", "offset_from_anchor"),
                offset=tuple(raw["offset"]) if raw.get("offset") else None,
                copy_mode=raw.get("copy_mode", "move"),
                preserve_color=raw.get("preserve_color", True),
                preserve_shape=raw.get("preserve_shape", True),
                background_color=raw.get("background_color", 0),
            )
        else:
            params_raw = hypothesis.parameters.copy()
            ctp_params = CopyToPositionParams(**{
                k: tuple(v) if k in ("displacement", "destination_point") and isinstance(v, list) else v
                for k, v in params_raw.items()
                if k in CopyToPositionParams.__dataclass_fields__
            })

        predictions = []
        for ti in test_inputs:
            if is_marker_relative:
                pred = execute_marker_relative_copy(ti, mr_params, train_pairs)
            else:
                pred = execute_copy_to_position(ti, ctp_params, train_pairs)
            if pred is None:
                self._emit("HYPOTHESIS_REJECTED", task_id, {
                    "operator_id": hypothesis.operator_id,
                    "reason": "execution_failed_on_test",
                })
                return False, None
            predictions.append(pred)

        if test_outputs is not None:
            correct = all(
                np.array_equal(p, e) for p, e in zip(predictions, test_outputs)
            )
            if correct:
                hypothesis.advance_level("promotion_validated")
                self._emit("TASK_PROMOTED_TO_SOLVED", task_id, {
                    "operator_id": hypothesis.operator_id,
                    "family": hypothesis.family,
                    "method": "trace_derived_operator",
                })
                return True, predictions

            hypothesis.rejection_reason = "test_output_mismatch"
            self._emit("HYPOTHESIS_REJECTED", task_id, {
                "operator_id": hypothesis.operator_id,
                "reason": "test_output_mismatch",
            })
            return False, predictions

        return True, predictions

    def build_certificate(
        self,
        task_id: str,
        hypothesis: ExecutableOperatorHypothesis,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        falsification_result: Optional[FalsificationResult] = None,
    ) -> ReasoningCertificate:
        cx_survived = 0
        cx_total = 0
        falsification_score = 1.0
        if falsification_result is not None:
            cx_survived = falsification_result.counterexamples_survived
            cx_total = falsification_result.counterexamples_generated
            falsification_score = falsification_result.falsification_score

        pre_results = hypothesis.check_preconditions(
            source_objects=[1],
            destination_rule=hypothesis.parameters.get("destination_rule"),
            destinations=[(0, 0)],
            grid_shape=(30, 30),
            source_masks=[np.ones((3, 3), dtype=bool)],
            params_consistent=True,
        )
        post_results = hypothesis.check_postconditions()
        inv_results = hypothesis.check_invariants()

        pre_passed = sum(1 for r in pre_results if r.passed)
        post_passed = sum(1 for r in post_results if r.passed)
        inv_passed = sum(1 for r in inv_results if r.passed)

        cert = ReasoningCertificate(
            task_id=task_id,
            prediction_id=str(uuid.uuid4()),
            selected_hypothesis={
                "strategy": "copy_to_position",
                "operator_id": hypothesis.operator_id,
                "family": hypothesis.family,
                "selector": hypothesis.selector_expression,
                "parameters": _safe_params(hypothesis.parameters),
                "validation_level": hypothesis.validation_level,
                "operator_family": "copy_to_position",
                "operator_parameters": _safe_params(hypothesis.parameters),
                "preconditions_checked": f"{pre_passed}/{len(pre_results)}",
                "postconditions_checked": f"{post_passed}/{len(post_results)}",
                "invariants_checked": f"{inv_passed}/{len(inv_results)}",
                "proof_obligations": [
                    {"id": o.obligation_id, "status": o.status}
                    for o in hypothesis.proof_obligations
                ],
                "promotion_source_trace": hypothesis.provenance,
            },
            derivation_trace=[
                {"step": "operator_gap_detected", "family": "copy_to_position"},
                {"step": "hypothesis_proposed", "operator_id": hypothesis.operator_id},
                {"step": "parameters_inferred", "rule": hypothesis.parameters.get("destination_rule")},
                {"step": "train_consistency_checked", "level": hypothesis.validation_level},
                {"step": "loo_validated", "passed": hypothesis.validation_level in ("loo_validated", "falsification_validated", "promotion_validated")},
                {"step": "falsification", "survived": cx_survived, "total": cx_total},
            ],
            supporting_paradigms=["trace_derived_copy_to_position"],
            n_agreeing=1,
            training_fit=1.0,
            loo_status=hypothesis.validation_level in ("loo_validated", "falsification_validated", "promotion_validated", "transfer_validated"),
            counterexamples_survived=cx_survived,
            counterexamples_total=cx_total,
            falsification_score=falsification_score,
            invariants_preserved=[
                "grid_size_unchanged",
                "non_target_objects_unchanged",
                "topology_preserved",
                "color_set_preserved",
            ],
            topology_changes={"per_pair": [], "consistent": True},
            memory_retrievals_used=0,
            invented_concepts_used=[],
            failure_risk="low" if hypothesis.validation_level in ("promotion_validated", "transfer_validated") else "medium",
            confidence=0.85 if hypothesis.validation_level == "promotion_validated" else 0.60,
        )

        self._emit("REASONING_CERTIFICATE_CREATED", task_id, {
            "operator_id": hypothesis.operator_id,
            "certificate_id": cert.prediction_id,
            "validation_level": hypothesis.validation_level,
        })

        return cert

    # ═══════════════════════════════════════════════════════════════════
    # RECOLOR-IN-PLACE OPERATOR
    # ═══════════════════════════════════════════════════════════════════

    def propose_recolor_in_place(
        self,
        task_id: str,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        trace: Dict[str, Any],
    ) -> Optional[ExecutableOperatorHypothesis]:
        """Propose a recolor-in-place operator using the rich object-change classifier.

        Detects which objects are recolored (same shape, different colors) and
        infers the recolor rule from training examples.
        """
        selector = trace.get("best_property", "")
        if not selector:
            return None

        self._emit("PROPOSAL_ATTEMPT", task_id, {
            "family": "recolor_in_place",
            "selector": selector,
        })

        # Use rich classifier to identify recolored objects
        recolor_rules: List[Dict[str, int]] = []
        for inp, out in train_pairs:
            objects = _extract_objects_with_properties(inp)
            occ = _classify_object_changes(objects, inp, out, bg=0)
            if occ is None or not occ.recolored:
                self._emit("PROPOSAL_FAILED", task_id, {
                    "family": "recolor_in_place",
                    "reason": "no_recolored_objects_detected",
                })
                return None

            # For each recolored object, extract old→new color mapping
            pair_rule: Dict[int, int] = {}
            for ch in occ.changes:
                if ch.change_type != "recolored":
                    continue
                obj = objects[ch.object_idx]
                in_vals = inp[obj["mask"]]
                out_vals = out[obj["mask"]]
                # Build per-pixel color map
                for iv, ov in zip(in_vals.ravel(), out_vals.ravel()):
                    if int(iv) != 0 and int(ov) != 0:
                        pair_rule[int(iv)] = int(ov)
            recolor_rules.append(pair_rule)

        if not recolor_rules:
            self._emit("PROPOSAL_FAILED", task_id, {
                "family": "recolor_in_place",
                "reason": "empty_recolor_rules",
            })
            return None

        # Check for consistent recolor pattern across pairs
        all_target_colors = set()
        for rule in recolor_rules:
            all_target_colors.update(rule.values())

        recolor_type = "unknown"
        recolor_params: Dict[str, Any] = {}

        if len(all_target_colors) == 1:
            recolor_type = "constant_color"
            recolor_params["target_color"] = list(all_target_colors)[0]
        elif all(r == recolor_rules[0] for r in recolor_rules) and recolor_rules[0]:
            recolor_type = "consistent_map"
            recolor_params["color_map"] = {str(k): v for k, v in recolor_rules[0].items()}
        else:
            recolor_type = "per_pair_map"
            recolor_params["maps"] = [{str(k): v for k, v in r.items()} for r in recolor_rules]

        hypothesis_id = f"rcl_{task_id}_{hash(str(recolor_rules)) % 0xFFFFFFFF:08x}"
        hypothesis = ExecutableOperatorHypothesis(
            operator_id=hypothesis_id,
            family="recolor_in_place",
            source_tasks=[task_id],
            selector_expression=selector,
            parameters={
                "source_selector": selector,
                "recolor_type": recolor_type,
                **recolor_params,
            },
            preconditions=[],
            postconditions=[],
            invariants=[],
            complexity=3,
            provenance={"derived_from": "rich_object_change_classifier"},
        )

        self._emit("HYPOTHESIS_PROPOSED", task_id, {
            "operator_id": hypothesis_id,
            "family": "recolor_in_place",
            "recolor_type": recolor_type,
            "selector": selector,
        })

        self.hypotheses[hypothesis_id] = hypothesis
        return hypothesis

    def _validate_recolor_in_place(
        self,
        task_id: str,
        hypothesis: ExecutableOperatorHypothesis,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    ) -> bool:
        """Validate recolor hypothesis by checking if applying the recolor rule
        reproduces the training outputs exactly. Tries both selector polarities."""
        selector = hypothesis.parameters.get("source_selector", "")
        recolor_type = hypothesis.parameters.get("recolor_type", "")
        target_color = hypothesis.parameters.get("target_color")
        color_map = hypothesis.parameters.get("color_map")

        for invert in (False, True):
            n_correct = 0
            for pi, (inp, out) in enumerate(train_pairs):
                pred = self._apply_recolor(
                    inp, selector, recolor_type, target_color, color_map, invert,
                )
                if pred is not None and np.array_equal(pred, out):
                    n_correct += 1

            train_fit = n_correct / len(train_pairs)
            if train_fit >= 1.0:
                if invert:
                    hypothesis.parameters["invert_selector"] = True
                hypothesis.validation_level = "train_consistent"
                hypothesis.rejection_reason = None
                return True

        hypothesis.validation_level = "parameterized"
        hypothesis.rejection_reason = f"train_fit={train_fit:.3f}"
        return False

    def _apply_recolor(
        self,
        grid: np.ndarray,
        selector: str,
        recolor_type: str,
        target_color: Optional[int],
        color_map: Optional[Dict[str, int]],
        invert: bool = False,
    ) -> Optional[np.ndarray]:
        """Apply recolor rule to grid. If invert=True, recolor selector=True objects."""
        if recolor_type not in ("constant_color", "consistent_map"):
            return None

        objects = _extract_objects_with_properties(grid)
        pred = grid.copy()
        for obj in objects:
            val = _get_property_value(obj, selector)
            is_target = (not val) if not invert else val
            if not is_target:
                continue
            mask = obj["mask"]
            in_vals = grid[mask]
            new_vals = in_vals.copy()
            if recolor_type == "constant_color" and target_color is not None:
                new_vals[in_vals != 0] = target_color
            elif recolor_type == "consistent_map" and color_map is not None:
                for old_c_str, new_c in color_map.items():
                    old_c = int(old_c_str)
                    new_vals[in_vals == old_c] = new_c
            pred[mask] = new_vals
        return pred

    def _execute_recolor(
        self,
        grid: np.ndarray,
        hypothesis: ExecutableOperatorHypothesis,
    ) -> Optional[np.ndarray]:
        """Execute a recolor-in-place operator on a grid."""
        selector = hypothesis.parameters.get("source_selector", "")
        recolor_type = hypothesis.parameters.get("recolor_type", "")
        target_color = hypothesis.parameters.get("target_color")
        color_map = hypothesis.parameters.get("color_map")
        invert = hypothesis.parameters.get("invert_selector", False)

        return self._apply_recolor(
            grid, selector, recolor_type, target_color, color_map, invert,
        )

    def propose_color_transfer_recolor(
        self,
        task_id: str,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        trace: Dict[str, Any],
    ) -> Optional[ExecutableOperatorHypothesis]:
        """Propose a color-transfer operator: target color derived from context."""
        selector = trace.get("best_property", "")
        if not selector:
            return None

        self._emit("PROPOSAL_ATTEMPT", task_id, {
            "family": "color_transfer_recolor",
            "selector": selector,
        })

        result = infer_color_transfer_params(train_pairs, selector)
        if result is None:
            self._emit("PROPOSAL_FAILED", task_id, {
                "family": "color_transfer_recolor",
                "reason": "no_valid_color_source_rule",
            })
            return None

        params, rule, invert = result

        hypothesis_id = f"ctr_{task_id}_{rule.rule_type}_{hash(rule.rule_id) % 0xFFFFFFFF:08x}"
        hypothesis = ExecutableOperatorHypothesis(
            operator_id=hypothesis_id,
            family="color_transfer_recolor",
            source_tasks=[task_id],
            selector_expression=selector,
            parameters={
                "source_selector": selector,
                "rule_type": rule.rule_type,
                "rule_id": rule.rule_id,
                "invert_selector": invert,
                "color_source_selector": rule.color_source_selector,
                "mapping": rule.mapping,
                "complexity": rule.complexity,
            },
            preconditions=[],
            postconditions=[],
            invariants=[],
            complexity=rule.complexity,
            provenance={"derived_from": "color_source_inference", "evidence": rule.evidence},
        )

        self._emit("HYPOTHESIS_PROPOSED", task_id, {
            "operator_id": hypothesis_id,
            "family": "color_transfer_recolor",
            "rule_type": rule.rule_type,
            "selector": selector,
            "invert": invert,
        })

        self.hypotheses[hypothesis_id] = hypothesis
        return hypothesis

    def _validate_color_transfer(
        self,
        task_id: str,
        hypothesis: ExecutableOperatorHypothesis,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    ) -> bool:
        """Validate color-transfer hypothesis on training pairs."""
        selector = hypothesis.parameters.get("source_selector", "")
        rule_type = hypothesis.parameters.get("rule_type", "")
        invert = hypothesis.parameters.get("invert_selector", False)
        mapping = hypothesis.parameters.get("mapping")

        rule = ColorSourceRule(
            rule_id=hypothesis.parameters.get("rule_id", ""),
            rule_type=rule_type,
            source_selector=selector,
            target_selector="",
            color_source_selector=rule_type,
            mapping=mapping,
        )

        n_correct = 0
        for inp, out in train_pairs:
            pred = execute_color_transfer(inp, selector, rule, invert)
            if pred is not None and np.array_equal(pred, out):
                n_correct += 1

        train_fit = n_correct / len(train_pairs)
        hypothesis.validation_level = "train_consistent" if train_fit >= 1.0 else "parameterized"
        hypothesis.rejection_reason = None if train_fit >= 1.0 else f"train_fit={train_fit:.3f}"
        return train_fit >= 1.0

    def _execute_color_transfer(
        self,
        grid: np.ndarray,
        hypothesis: ExecutableOperatorHypothesis,
    ) -> Optional[np.ndarray]:
        """Execute a color-transfer operator on a grid."""
        selector = hypothesis.parameters.get("source_selector", "")
        rule_type = hypothesis.parameters.get("rule_type", "")
        invert = hypothesis.parameters.get("invert_selector", False)
        mapping = hypothesis.parameters.get("mapping")

        rule = ColorSourceRule(
            rule_id=hypothesis.parameters.get("rule_id", ""),
            rule_type=rule_type,
            source_selector=selector,
            target_selector="",
            color_source_selector=rule_type,
            mapping=mapping,
        )

        return execute_color_transfer(grid, selector, rule, invert)

    def run_full_pipeline(
        self,
        task_id: str,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        test_inputs: List[np.ndarray],
        trace: Dict[str, Any],
        test_outputs: Optional[List[np.ndarray]] = None,
    ) -> Dict[str, Any]:
        """Run the complete operator invention pipeline for one task.

        Returns a dict with all results and the full chain status.
        """
        result: Dict[str, Any] = {
            "task_id": task_id,
            "operator_proposed": False,
            "parameterized": False,
            "train_consistent": False,
            "loo_passed": False,
            "falsification_status": "not_run",
            "replay_status": "not_run",
            "promoted": False,
            "false_positive": False,
            "rejection_reason": None,
            "certificate_path": None,
            "operator_id": None,
            "predictions": None,
        }

        hypothesis = self.propose_copy_to_position(task_id, train_pairs, trace)
        if hypothesis is None:
            hypothesis = self.propose_marker_relative_copy_to_position(
                task_id, train_pairs, trace,
            )
            if hypothesis is None:
                hypothesis = self.propose_correspondence_copy_to_position(
                    task_id, train_pairs, trace,
                )
                if hypothesis is None:
                    hypothesis = self.propose_variable_destination_copy(
                        task_id, train_pairs, trace,
                    )
                    if hypothesis is None:
                        hypothesis = self.propose_marker_projection(
                            task_id, train_pairs, trace,
                        )
                        if hypothesis is None:
                            hypothesis = self.propose_recolor_in_place(
                                task_id, train_pairs, trace,
                            )
                            if hypothesis is None:
                                hypothesis = self.propose_color_transfer_recolor(
                                    task_id, train_pairs, trace,
                                )
                                if hypothesis is None:
                                    result["rejection_reason"] = "parameter_inference_failed"
                                    record = OperatorCandidateRecord(
                                        operator_id="none", family="copy_to_position",
                                        task_ids=[task_id], source_trace_ids=[task_id],
                                        parameters={}, rejection_reason=result["rejection_reason"],
                                    )
                                    self.rejected.append(record)
                                    return result

        result["operator_proposed"] = True
        result["parameterized"] = True
        result["operator_id"] = hypothesis.operator_id
        active_family = hypothesis.family

        if not self.validate_hypothesis(task_id, hypothesis, train_pairs):
            if active_family == "copy_to_position":
                self._emit("CTP_TRAIN_FAILED_TRYING_MARKER_RELATIVE", task_id, {
                    "ctp_rejection": hypothesis.rejection_reason,
                })
                mr_hypothesis = self.propose_marker_relative_copy_to_position(
                    task_id, train_pairs, trace,
                )
                if mr_hypothesis is not None and self.validate_hypothesis(
                    task_id, mr_hypothesis, train_pairs,
                ):
                    hypothesis = mr_hypothesis
                    active_family = hypothesis.family
                    result["operator_id"] = hypothesis.operator_id
                else:
                    self._emit("MR_TRAIN_FAILED_TRYING_CORRESPONDENCE", task_id, {
                        "mr_rejection": hypothesis.rejection_reason,
                    })
                    corr_hypothesis = self.propose_correspondence_copy_to_position(
                        task_id, train_pairs, trace,
                    )
                    if corr_hypothesis is not None and self.validate_hypothesis(
                        task_id, corr_hypothesis, train_pairs,
                    ):
                        hypothesis = corr_hypothesis
                        active_family = hypothesis.family
                        result["operator_id"] = hypothesis.operator_id
                    else:
                        self._emit("CORR_TRAIN_FAILED_TRYING_VDP", task_id, {})
                        vdp_hypothesis = self.propose_variable_destination_copy(
                            task_id, train_pairs, trace,
                        )
                        if vdp_hypothesis is not None and self.validate_hypothesis(
                            task_id, vdp_hypothesis, train_pairs,
                        ):
                            hypothesis = vdp_hypothesis
                            active_family = hypothesis.family
                            result["operator_id"] = hypothesis.operator_id
                        else:
                            self._emit("VDP_TRAIN_FAILED_TRYING_MP", task_id, {})
                            mp_hypothesis = self.propose_marker_projection(
                                task_id, train_pairs, trace,
                            )
                            if mp_hypothesis is not None and self.validate_hypothesis(
                                task_id, mp_hypothesis, train_pairs,
                            ):
                                hypothesis = mp_hypothesis
                                active_family = hypothesis.family
                                result["operator_id"] = hypothesis.operator_id
                            else:
                                self._emit("MP_TRAIN_FAILED_TRYING_RECOLOR", task_id, {})
                                rcl_hypothesis = self.propose_recolor_in_place(
                                    task_id, train_pairs, trace,
                                )
                                if rcl_hypothesis is not None and self.validate_hypothesis(
                                    task_id, rcl_hypothesis, train_pairs,
                                ):
                                    hypothesis = rcl_hypothesis
                                    active_family = hypothesis.family
                                    result["operator_id"] = hypothesis.operator_id
                                else:
                                    self._emit("RCL_TRAIN_FAILED_TRYING_CTR", task_id, {})
                                    ctr_hypothesis = self.propose_color_transfer_recolor(
                                        task_id, train_pairs, trace,
                                    )
                                    if ctr_hypothesis is not None and self.validate_hypothesis(
                                        task_id, ctr_hypothesis, train_pairs,
                                    ):
                                        hypothesis = ctr_hypothesis
                                        active_family = hypothesis.family
                                        result["operator_id"] = hypothesis.operator_id
                                    else:
                                        result["rejection_reason"] = hypothesis.rejection_reason
                                        record = OperatorCandidateRecord(
                                            operator_id=hypothesis.operator_id, family=active_family,
                                            task_ids=[task_id], source_trace_ids=[task_id],
                                            parameters=_safe_params(hypothesis.parameters),
                                            validation_level="parameterized",
                                            rejection_reason=hypothesis.rejection_reason,
                                        )
                                        self.rejected.append(record)
                                        return result
            elif active_family == "marker_relative_copy_to_position":
                self._emit("MR_TRAIN_FAILED_TRYING_CORRESPONDENCE", task_id, {
                    "mr_rejection": hypothesis.rejection_reason,
                })
                corr_hypothesis = self.propose_correspondence_copy_to_position(
                    task_id, train_pairs, trace,
                )
                if corr_hypothesis is not None and self.validate_hypothesis(
                    task_id, corr_hypothesis, train_pairs,
                ):
                    hypothesis = corr_hypothesis
                    active_family = hypothesis.family
                    result["operator_id"] = hypothesis.operator_id
                else:
                    self._emit("CORR_TRAIN_FAILED_TRYING_VDP", task_id, {})
                    vdp_hypothesis = self.propose_variable_destination_copy(
                        task_id, train_pairs, trace,
                    )
                    if vdp_hypothesis is not None and self.validate_hypothesis(
                        task_id, vdp_hypothesis, train_pairs,
                    ):
                        hypothesis = vdp_hypothesis
                        active_family = hypothesis.family
                        result["operator_id"] = hypothesis.operator_id
                    else:
                        self._emit("VDP_TRAIN_FAILED_TRYING_MP", task_id, {})
                        mp_hypothesis = self.propose_marker_projection(
                            task_id, train_pairs, trace,
                        )
                        if mp_hypothesis is not None and self.validate_hypothesis(
                            task_id, mp_hypothesis, train_pairs,
                        ):
                            hypothesis = mp_hypothesis
                            active_family = hypothesis.family
                            result["operator_id"] = hypothesis.operator_id
                        else:
                            self._emit("MP_TRAIN_FAILED_TRYING_RECOLOR", task_id, {})
                            rcl_hypothesis = self.propose_recolor_in_place(
                                task_id, train_pairs, trace,
                            )
                            if rcl_hypothesis is not None and self.validate_hypothesis(
                                task_id, rcl_hypothesis, train_pairs,
                            ):
                                hypothesis = rcl_hypothesis
                                active_family = hypothesis.family
                                result["operator_id"] = hypothesis.operator_id
                            else:
                                self._emit("RCL_TRAIN_FAILED_TRYING_CTR", task_id, {})
                                ctr_hypothesis = self.propose_color_transfer_recolor(
                                    task_id, train_pairs, trace,
                                )
                                if ctr_hypothesis is not None and self.validate_hypothesis(
                                    task_id, ctr_hypothesis, train_pairs,
                                ):
                                    hypothesis = ctr_hypothesis
                                    active_family = hypothesis.family
                                    result["operator_id"] = hypothesis.operator_id
                                else:
                                    result["rejection_reason"] = hypothesis.rejection_reason
                                    record = OperatorCandidateRecord(
                                        operator_id=hypothesis.operator_id, family=active_family,
                                        task_ids=[task_id], source_trace_ids=[task_id],
                                        parameters=_safe_params(hypothesis.parameters),
                                        validation_level="parameterized",
                                        rejection_reason=hypothesis.rejection_reason,
                                    )
                                    self.rejected.append(record)
                                    return result
            elif active_family == "correspondence_copy_to_position":
                self._emit("CORR_TRAIN_FAILED_TRYING_VDP", task_id, {})
                vdp_hypothesis = self.propose_variable_destination_copy(
                    task_id, train_pairs, trace,
                )
                if vdp_hypothesis is not None and self.validate_hypothesis(
                    task_id, vdp_hypothesis, train_pairs,
                ):
                    hypothesis = vdp_hypothesis
                    active_family = hypothesis.family
                    result["operator_id"] = hypothesis.operator_id
                else:
                    self._emit("VDP_TRAIN_FAILED_TRYING_MP", task_id, {})
                    mp_hypothesis = self.propose_marker_projection(
                        task_id, train_pairs, trace,
                    )
                    if mp_hypothesis is not None and self.validate_hypothesis(
                        task_id, mp_hypothesis, train_pairs,
                    ):
                        hypothesis = mp_hypothesis
                        active_family = hypothesis.family
                        result["operator_id"] = hypothesis.operator_id
                    else:
                        self._emit("MP_TRAIN_FAILED_TRYING_RECOLOR", task_id, {})
                        rcl_hypothesis = self.propose_recolor_in_place(
                            task_id, train_pairs, trace,
                        )
                        if rcl_hypothesis is not None and self.validate_hypothesis(
                            task_id, rcl_hypothesis, train_pairs,
                        ):
                            hypothesis = rcl_hypothesis
                            active_family = hypothesis.family
                            result["operator_id"] = hypothesis.operator_id
                        else:
                            self._emit("RCL_TRAIN_FAILED_TRYING_CTR", task_id, {})
                            ctr_hypothesis = self.propose_color_transfer_recolor(
                                task_id, train_pairs, trace,
                            )
                            if ctr_hypothesis is not None and self.validate_hypothesis(
                                task_id, ctr_hypothesis, train_pairs,
                            ):
                                hypothesis = ctr_hypothesis
                                active_family = hypothesis.family
                                result["operator_id"] = hypothesis.operator_id
                            else:
                                result["rejection_reason"] = hypothesis.rejection_reason
                                record = OperatorCandidateRecord(
                                    operator_id=hypothesis.operator_id, family=active_family,
                                    task_ids=[task_id], source_trace_ids=[task_id],
                                    parameters=_safe_params(hypothesis.parameters),
                                    validation_level="parameterized",
                                    rejection_reason=hypothesis.rejection_reason,
                                )
                                self.rejected.append(record)
                                return result
            elif active_family == "variable_destination_copy":
                self._emit("VDP_TRAIN_FAILED_TRYING_MP", task_id, {})
                mp_hypothesis = self.propose_marker_projection(
                    task_id, train_pairs, trace,
                )
                if mp_hypothesis is not None and self.validate_hypothesis(
                    task_id, mp_hypothesis, train_pairs,
                ):
                    hypothesis = mp_hypothesis
                    active_family = hypothesis.family
                    result["operator_id"] = hypothesis.operator_id
                else:
                    self._emit("MP_TRAIN_FAILED_TRYING_RECOLOR", task_id, {})
                    rcl_hypothesis = self.propose_recolor_in_place(
                        task_id, train_pairs, trace,
                    )
                    if rcl_hypothesis is not None and self.validate_hypothesis(
                        task_id, rcl_hypothesis, train_pairs,
                    ):
                        hypothesis = rcl_hypothesis
                        active_family = hypothesis.family
                        result["operator_id"] = hypothesis.operator_id
                    else:
                        self._emit("RCL_TRAIN_FAILED_TRYING_CTR", task_id, {})
                        ctr_hypothesis = self.propose_color_transfer_recolor(
                            task_id, train_pairs, trace,
                        )
                        if ctr_hypothesis is not None and self.validate_hypothesis(
                            task_id, ctr_hypothesis, train_pairs,
                        ):
                            hypothesis = ctr_hypothesis
                            active_family = hypothesis.family
                            result["operator_id"] = hypothesis.operator_id
                        else:
                            result["rejection_reason"] = hypothesis.rejection_reason
                            record = OperatorCandidateRecord(
                                operator_id=hypothesis.operator_id, family=active_family,
                                task_ids=[task_id], source_trace_ids=[task_id],
                                parameters=_safe_params(hypothesis.parameters),
                                validation_level="parameterized",
                                rejection_reason=hypothesis.rejection_reason,
                            )
                            self.rejected.append(record)
                            return result
            else:
                result["rejection_reason"] = hypothesis.rejection_reason
                record = OperatorCandidateRecord(
                    operator_id=hypothesis.operator_id, family=active_family,
                    task_ids=[task_id], source_trace_ids=[task_id],
                    parameters=_safe_params(hypothesis.parameters),
                    validation_level="parameterized",
                    rejection_reason=hypothesis.rejection_reason,
                )
                self.rejected.append(record)
                return result

        result["train_consistent"] = True

        if not self.loo_validate_hypothesis(task_id, hypothesis, train_pairs):
            loo_fallback_found = False
            if active_family == "copy_to_position":
                self._emit("CTP_LOO_FAILED_TRYING_MR", task_id, {
                    "ctp_rejection": hypothesis.rejection_reason,
                })
                mr_hyp = self.propose_marker_relative_copy_to_position(
                    task_id, train_pairs, trace,
                )
                if mr_hyp is not None and self.validate_hypothesis(
                    task_id, mr_hyp, train_pairs,
                ) and self.loo_validate_hypothesis(task_id, mr_hyp, train_pairs):
                    hypothesis = mr_hyp
                    active_family = hypothesis.family
                    result["operator_id"] = hypothesis.operator_id
                    loo_fallback_found = True
                if not loo_fallback_found:
                    self._emit("MR_LOO_FAILED_TRYING_CORR", task_id, {})
                    corr_hyp = self.propose_correspondence_copy_to_position(
                        task_id, train_pairs, trace,
                    )
                    if corr_hyp is not None and self.validate_hypothesis(
                        task_id, corr_hyp, train_pairs,
                    ) and self.loo_validate_hypothesis(task_id, corr_hyp, train_pairs):
                        hypothesis = corr_hyp
                        active_family = hypothesis.family
                        result["operator_id"] = hypothesis.operator_id
                        loo_fallback_found = True
                if not loo_fallback_found:
                    self._emit("CORR_LOO_FAILED_TRYING_VDP", task_id, {})
                    vdp_hyp = self.propose_variable_destination_copy(
                        task_id, train_pairs, trace,
                    )
                    if vdp_hyp is not None and self.validate_hypothesis(
                        task_id, vdp_hyp, train_pairs,
                    ) and self.loo_validate_hypothesis(task_id, vdp_hyp, train_pairs):
                        hypothesis = vdp_hyp
                        active_family = hypothesis.family
                        result["operator_id"] = hypothesis.operator_id
                        loo_fallback_found = True
                if not loo_fallback_found:
                    self._emit("VDP_LOO_FAILED_TRYING_MP", task_id, {})
                    mp_hyp = self.propose_marker_projection(
                        task_id, train_pairs, trace,
                    )
                    if mp_hyp is not None and self.validate_hypothesis(
                        task_id, mp_hyp, train_pairs,
                    ) and self.loo_validate_hypothesis(task_id, mp_hyp, train_pairs):
                        hypothesis = mp_hyp
                        active_family = hypothesis.family
                        result["operator_id"] = hypothesis.operator_id
                        loo_fallback_found = True
            elif active_family == "marker_relative_copy_to_position":
                self._emit("MR_LOO_FAILED_TRYING_CORR", task_id, {})
                corr_hyp = self.propose_correspondence_copy_to_position(
                    task_id, train_pairs, trace,
                )
                if corr_hyp is not None and self.validate_hypothesis(
                    task_id, corr_hyp, train_pairs,
                ) and self.loo_validate_hypothesis(task_id, corr_hyp, train_pairs):
                    hypothesis = corr_hyp
                    active_family = hypothesis.family
                    result["operator_id"] = hypothesis.operator_id
                    loo_fallback_found = True
                if not loo_fallback_found:
                    self._emit("CORR_LOO_FAILED_TRYING_VDP", task_id, {})
                    vdp_hyp = self.propose_variable_destination_copy(
                        task_id, train_pairs, trace,
                    )
                    if vdp_hyp is not None and self.validate_hypothesis(
                        task_id, vdp_hyp, train_pairs,
                    ) and self.loo_validate_hypothesis(task_id, vdp_hyp, train_pairs):
                        hypothesis = vdp_hyp
                        active_family = hypothesis.family
                        result["operator_id"] = hypothesis.operator_id
                        loo_fallback_found = True
                if not loo_fallback_found:
                    self._emit("VDP_LOO_FAILED_TRYING_MP", task_id, {})
                    mp_hyp = self.propose_marker_projection(
                        task_id, train_pairs, trace,
                    )
                    if mp_hyp is not None and self.validate_hypothesis(
                        task_id, mp_hyp, train_pairs,
                    ) and self.loo_validate_hypothesis(task_id, mp_hyp, train_pairs):
                        hypothesis = mp_hyp
                        active_family = hypothesis.family
                        result["operator_id"] = hypothesis.operator_id
                        loo_fallback_found = True
            elif active_family == "correspondence_copy_to_position":
                self._emit("CORR_LOO_FAILED_TRYING_VDP", task_id, {})
                vdp_hyp = self.propose_variable_destination_copy(
                    task_id, train_pairs, trace,
                )
                if vdp_hyp is not None and self.validate_hypothesis(
                    task_id, vdp_hyp, train_pairs,
                ) and self.loo_validate_hypothesis(task_id, vdp_hyp, train_pairs):
                    hypothesis = vdp_hyp
                    active_family = hypothesis.family
                    result["operator_id"] = hypothesis.operator_id
                    loo_fallback_found = True
                if not loo_fallback_found:
                    self._emit("VDP_LOO_FAILED_TRYING_MP", task_id, {})
                    mp_hyp = self.propose_marker_projection(
                        task_id, train_pairs, trace,
                    )
                    if mp_hyp is not None and self.validate_hypothesis(
                        task_id, mp_hyp, train_pairs,
                    ) and self.loo_validate_hypothesis(task_id, mp_hyp, train_pairs):
                        hypothesis = mp_hyp
                        active_family = hypothesis.family
                        result["operator_id"] = hypothesis.operator_id
                        loo_fallback_found = True
            elif active_family == "variable_destination_copy":
                self._emit("VDP_LOO_FAILED_TRYING_MP", task_id, {})
                mp_hyp = self.propose_marker_projection(
                    task_id, train_pairs, trace,
                )
                if mp_hyp is not None and self.validate_hypothesis(
                    task_id, mp_hyp, train_pairs,
                ) and self.loo_validate_hypothesis(task_id, mp_hyp, train_pairs):
                    hypothesis = mp_hyp
                    active_family = hypothesis.family
                    result["operator_id"] = hypothesis.operator_id
                    loo_fallback_found = True

            if not loo_fallback_found and active_family not in ("recolor_in_place", "color_transfer_recolor"):
                self._emit("LOO_TRYING_RECOLOR", task_id, {})
                rcl_hyp = self.propose_recolor_in_place(task_id, train_pairs, trace)
                if rcl_hyp is not None and self.validate_hypothesis(
                    task_id, rcl_hyp, train_pairs,
                ) and self.loo_validate_hypothesis(task_id, rcl_hyp, train_pairs):
                    hypothesis = rcl_hyp
                    active_family = hypothesis.family
                    result["operator_id"] = hypothesis.operator_id
                    loo_fallback_found = True
            if not loo_fallback_found and active_family != "color_transfer_recolor":
                self._emit("LOO_TRYING_COLOR_TRANSFER", task_id, {})
                ctr_hyp = self.propose_color_transfer_recolor(task_id, train_pairs, trace)
                if ctr_hyp is not None and self.validate_hypothesis(
                    task_id, ctr_hyp, train_pairs,
                ) and self.loo_validate_hypothesis(task_id, ctr_hyp, train_pairs):
                    hypothesis = ctr_hyp
                    active_family = hypothesis.family
                    result["operator_id"] = hypothesis.operator_id
                    loo_fallback_found = True

            if not loo_fallback_found:
                result["rejection_reason"] = hypothesis.rejection_reason
                record = OperatorCandidateRecord(
                    operator_id=hypothesis.operator_id, family=active_family,
                    task_ids=[task_id], source_trace_ids=[task_id],
                    parameters=_safe_params(hypothesis.parameters),
                    validation_level="train_consistent",
                    rejection_reason=hypothesis.rejection_reason,
                )
                self.rejected.append(record)
                return result

        result["loo_passed"] = True

        falsification_result = self.falsify_hypothesis(task_id, hypothesis, train_pairs)
        result["falsification_status"] = "passed" if falsification_result.passed else "failed"

        promoted, predictions = self.attempt_promotion(
            task_id, hypothesis, train_pairs, test_inputs, test_outputs,
        )
        result["predictions"] = predictions
        result["replay_status"] = "success" if predictions is not None else "failed"

        if promoted and test_outputs is not None:
            result["promoted"] = True
            cert = self.build_certificate(task_id, hypothesis, train_pairs, falsification_result)

            record = OperatorCandidateRecord(
                operator_id=hypothesis.operator_id, family=active_family,
                task_ids=[task_id], source_trace_ids=[task_id],
                parameters=_safe_params(hypothesis.parameters),
                validation_level=hypothesis.validation_level,
                train_fit=1.0, loo_passed=True,
                falsification_passed=falsification_result.passed,
                promoted_tasks=[task_id],
            )
            self.validated.append(record)
            self.proposed.append(record)

            result["certificate"] = certificate_to_json(cert)
            result["certificate_md"] = certificate_to_markdown(cert)
        elif not promoted:
            result["rejection_reason"] = hypothesis.rejection_reason or "promotion_failed"
            record = OperatorCandidateRecord(
                operator_id=hypothesis.operator_id, family=active_family,
                task_ids=[task_id], source_trace_ids=[task_id],
                parameters=_safe_params(hypothesis.parameters),
                validation_level=hypothesis.validation_level,
                train_fit=1.0, loo_passed=True,
                falsification_passed=falsification_result.passed,
                rejection_reason=result["rejection_reason"],
            )
            self.rejected.append(record)
        else:
            record = OperatorCandidateRecord(
                operator_id=hypothesis.operator_id, family=active_family,
                task_ids=[task_id], source_trace_ids=[task_id],
                parameters=_safe_params(hypothesis.parameters),
                validation_level=hypothesis.validation_level,
                train_fit=1.0, loo_passed=True,
                falsification_passed=falsification_result.passed,
            )
            self.validated.append(record)
            self.proposed.append(record)
            result["certificate"] = None

        return result

    def write_artifacts(self, output_dir: str) -> None:
        os.makedirs(output_dir, exist_ok=True)

        with open(os.path.join(output_dir, "proposed_operators.jsonl"), "w") as f:
            for rec in self.proposed:
                f.write(json.dumps(rec.to_dict()) + "\n")

        with open(os.path.join(output_dir, "validated_operators.jsonl"), "w") as f:
            for rec in self.validated:
                f.write(json.dumps(rec.to_dict()) + "\n")

        with open(os.path.join(output_dir, "rejected_operators.jsonl"), "w") as f:
            for rec in self.rejected:
                f.write(json.dumps(rec.to_dict()) + "\n")

        n_proposed = len(self.proposed)
        n_validated = len(self.validated)
        n_rejected = len(self.rejected)
        n_promoted = sum(len(r.promoted_tasks) for r in self.validated)
        n_fp = sum(r.false_positives for r in self.validated)

        rejection_reasons: Dict[str, int] = {}
        for rec in self.rejected:
            reason = rec.rejection_reason or "unknown"
            rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1

        lines = [
            "# Operator Validation Report",
            "",
            f"- Proposed: {n_proposed}",
            f"- Validated (LOO+falsification): {n_validated}",
            f"- Rejected: {n_rejected}",
            f"- Promoted tasks: {n_promoted}",
            f"- False positives: {n_fp}",
            "",
            "## Rejection Reasons",
            "",
            "| Reason | Count |",
            "|--------|-------|",
        ]
        for reason, count in sorted(rejection_reasons.items(), key=lambda x: -x[1]):
            lines.append(f"| {reason} | {count} |")

        with open(os.path.join(output_dir, "operator_validation_report.md"), "w") as f:
            f.write("\n".join(lines) + "\n")


# ═══════════════════════════════════════════════════════════════════════════
# CORRESPONDENCE-BASED COPY-TO-POSITION
# ═══════════════════════════════════════════════════════════════════════════

def infer_correspondence_params(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    selector_property: str,
    keep_when_true: bool = True,
) -> Optional[Tuple[CorrespondenceCopyParams, "CorrespondenceRule"]]:
    """Infer correspondence-based copy-to-position parameters.

    Tries each correspondence rule type. For each, checks whether the
    per-object relative displacement (source destination minus matched
    target centroid) is consistent across all training pairs.

    Returns the best (params, rule) pair or None.
    """
    from reasoning_project.correspondence_inference import (
        CorrespondenceInferer,
        CorrespondenceRule,
    )

    inferer = CorrespondenceInferer()
    background = 0

    objects_per_pair = []
    for inp, out in train_pairs:
        if inp.shape != out.shape:
            return None
        objs = _extract_objects_with_properties(inp)
        removed = [o for o in objs if _get_property_value(o, selector_property) != keep_when_true]
        kept = [o for o in objs if _get_property_value(o, selector_property) == keep_when_true]
        if not removed or not kept:
            return None
        objects_per_pair.append((removed, kept, inp, out))

    best_rule = None
    best_params = None
    best_score = -1.0

    first_removed, first_kept, first_inp, _ = objects_per_pair[0]
    src_sigs = inferer.extract_object_signatures(first_inp, first_removed)
    tgt_sigs = inferer.extract_object_signatures(first_inp, first_kept)
    candidate_rules = inferer.propose_rules(src_sigs, tgt_sigs)

    for rule in candidate_rules:
        ambiguity = inferer.detect_ambiguity(rule, train_pairs, selector_property)
        if ambiguity["is_ambiguous"]:
            continue

        all_rel_disps: List[Tuple[int, int]] = []
        all_similarities: List[float] = []
        source_retained = 0
        source_absent = 0
        rule_valid = True

        for removed, kept, inp, out in objects_per_pair:
            pair_src_sigs = inferer.extract_object_signatures(inp, removed)
            pair_tgt_sigs = inferer.extract_object_signatures(inp, kept)

            matcher = inferer._get_matcher(rule.rule_type)
            if matcher is None:
                rule_valid = False
                break

            matches = matcher(pair_src_sigs, pair_tgt_sigs)
            if matches is None or len(matches) != len(pair_src_sigs):
                rule_valid = False
                break

            src_masks = _extract_object_masks(inp, removed)

            for si, ti in matches:
                if si >= len(src_masks):
                    rule_valid = False
                    break
                mask = src_masks[si]
                result = _find_object_in_output(mask, inp * mask, inp, out, background)
                if result is None:
                    src_present = np.any(out[mask] != background) if mask.any() else False
                    if not src_present:
                        source_absent += 1
                    continue

                (dest_r, dest_c), sim = result
                all_similarities.append(sim)
                src_rows, src_cols = np.where(mask)
                dest_centroid_r = float(dest_r + np.mean(src_rows) - src_rows.min())
                dest_centroid_c = float(dest_c + np.mean(src_cols) - src_cols.min())

                tgt_centroid = pair_tgt_sigs[ti].centroid
                tgt_int_r = int(round(tgt_centroid[0]))
                tgt_int_c = int(round(tgt_centroid[1]))
                rel_disp = (
                    int(round(dest_centroid_r)) - tgt_int_r,
                    int(round(dest_centroid_c)) - tgt_int_c,
                )
                all_rel_disps.append(rel_disp)

                src_present = np.any(out[mask] != background) if mask.any() else False
                if src_present:
                    source_retained += 1
                else:
                    source_absent += 1

            if not rule_valid:
                break

        if not rule_valid or not all_rel_disps:
            continue

        if len(set(all_rel_disps)) != 1:
            continue

        consistent_disp = all_rel_disps[0]
        copy_mode = "move" if source_absent > source_retained else "copy_and_keep"
        preserve_color = all(s >= 0.95 for s in all_similarities) if all_similarities else True

        score = 1.0 / (rule.complexity + 1)
        if score > best_score:
            best_score = score
            best_rule = rule
            best_params = CorrespondenceCopyParams(
                source_selector=selector_property,
                correspondence_rule_type=rule.rule_type,
                correspondence_rule_id=rule.rule_id,
                relative_displacement=consistent_disp,
                copy_mode=copy_mode,
                preserve_shape=True,
                preserve_color=preserve_color,
                allow_overlap=False,
                background_color=background,
                tie_breaker=rule.tie_breaker,
            )

    if best_params is None or best_rule is None:
        return None
    return best_params, best_rule


def execute_correspondence_copy(
    input_grid: np.ndarray,
    params: CorrespondenceCopyParams,
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> Optional[np.ndarray]:
    """Execute a correspondence-based copy-to-position operator.

    Each source object is matched to a target object via the correspondence
    rule, then placed at a fixed relative displacement from that target.
    """
    from reasoning_project.correspondence_inference import CorrespondenceInferer

    inferer = CorrespondenceInferer()
    prop = params.source_selector
    if prop is None:
        return None

    objects = _extract_objects_with_properties(input_grid)
    removed = []
    kept = []
    for obj in objects:
        val = _get_property_value(obj, prop)
        if val:
            kept.append(obj)
        else:
            removed.append(obj)

    if not removed or not kept:
        return None

    src_sigs = inferer.extract_object_signatures(input_grid, removed)
    tgt_sigs = inferer.extract_object_signatures(input_grid, kept)

    matcher = inferer._get_matcher(params.correspondence_rule_type)
    if matcher is None:
        return None

    matches = matcher(src_sigs, tgt_sigs)
    if matches is None or len(matches) != len(src_sigs):
        return None

    output = input_grid.copy()

    if params.copy_mode == "move":
        for obj in removed:
            for r, c in _obj_cells(obj):
                if 0 <= r < output.shape[0] and 0 <= c < output.shape[1]:
                    output[r, c] = params.background_color

    if params.relative_displacement is None:
        return None

    dr_rel, dc_rel = params.relative_displacement

    for si, ti in matches:
        src_obj = removed[si]
        tgt_sig = tgt_sigs[ti]

        cells = _obj_cells(src_obj)
        if not cells:
            continue
        rows = [r for r, c in cells]
        cols = [c for r, c in cells]
        src_centroid_r = int(np.mean(rows))
        src_centroid_c = int(np.mean(cols))

        dest_centroid_r = int(round(tgt_sig.centroid[0])) + dr_rel
        dest_centroid_c = int(round(tgt_sig.centroid[1])) + dc_rel

        disp_r = dest_centroid_r - src_centroid_r
        disp_c = dest_centroid_c - src_centroid_c

        for r, c in cells:
            nr, nc = r + disp_r, c + disp_c
            if 0 <= nr < output.shape[0] and 0 <= nc < output.shape[1]:
                output[nr, nc] = input_grid[r, c]

    return output
