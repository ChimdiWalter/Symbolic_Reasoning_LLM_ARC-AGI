"""Failure Diagnosis — analyzes WHY a prediction doesn't match expected output.

When a solution attempt fails, this module identifies the error pattern and
generates targeted corrections. This enables iterative reasoning: try → diagnose
→ fix → retry.
"""
from __future__ import annotations

import uuid
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy.ndimage import label as ndlabel

from reasoning_project.operator_genesis import SynthesizedOperator


@dataclass
class FailureDiagnosis:
    pixel_accuracy: float
    wrong_pixels: List[Tuple[int, int, int, int]]  # (r, c, pred_val, expected_val)
    error_pattern: str
    suggested_corrections: List[str]
    error_region_mask: np.ndarray
    residual_grid: np.ndarray


def diagnose_failure(
    predicted: np.ndarray,
    expected: np.ndarray,
    input_grid: np.ndarray,
) -> FailureDiagnosis:
    """Analyze what's wrong with a prediction."""
    if predicted.shape != expected.shape:
        return FailureDiagnosis(
            pixel_accuracy=0.0,
            wrong_pixels=[],
            error_pattern="shape_mismatch",
            suggested_corrections=["output_shape_predictor"],
            error_region_mask=np.ones(expected.shape, dtype=bool),
            residual_grid=expected.copy(),
        )

    H, W = expected.shape
    match = predicted == expected
    accuracy = float(match.sum()) / max(H * W, 1)
    error_mask = ~match

    wrong = []
    for r, c in zip(*np.where(error_mask)):
        wrong.append((int(r), int(c), int(predicted[r, c]), int(expected[r, c])))

    residual = np.zeros_like(expected)
    residual[error_mask] = expected[error_mask]

    if not wrong:
        return FailureDiagnosis(
            pixel_accuracy=1.0, wrong_pixels=[], error_pattern="none",
            suggested_corrections=[], error_region_mask=error_mask,
            residual_grid=residual,
        )

    pattern = _classify_error_pattern(predicted, expected, input_grid, wrong, error_mask)
    corrections = _suggest_corrections(pattern)

    return FailureDiagnosis(
        pixel_accuracy=accuracy,
        wrong_pixels=wrong,
        error_pattern=pattern,
        suggested_corrections=corrections,
        error_region_mask=error_mask,
        residual_grid=residual,
    )


def _classify_error_pattern(
    pred: np.ndarray,
    exp: np.ndarray,
    inp: np.ndarray,
    wrong: List[Tuple[int, int, int, int]],
    error_mask: np.ndarray,
) -> str:
    """Classify the type of error."""
    pred_vals = [w[2] for w in wrong]
    exp_vals = [w[3] for w in wrong]

    # Check: consistent color swap?
    swap_map = {}
    is_swap = True
    for pv, ev in zip(pred_vals, exp_vals):
        if pv in swap_map:
            if swap_map[pv] != ev:
                is_swap = False
                break
        else:
            swap_map[pv] = ev
    if is_swap and len(swap_map) <= 3:
        return "color_swap"

    # Check: shifted version?
    for dr in range(-3, 4):
        for dc in range(-3, 4):
            if dr == 0 and dc == 0:
                continue
            H, W = pred.shape
            shifted = np.zeros_like(pred)
            for r in range(H):
                for c in range(W):
                    sr, sc = r - dr, c - dc
                    if 0 <= sr < H and 0 <= sc < W:
                        shifted[r, c] = pred[sr, sc]
            if np.array_equal(shifted, exp):
                return "shifted"

    # Check: partial fill (errors are bg in pred, non-bg in expected)?
    pred_bg = all(pv == 0 for pv in pred_vals)
    exp_nonbg = all(ev != 0 for ev in exp_vals)
    if pred_bg and exp_nonbg:
        return "partial_fill"

    # Check: partial clear (errors are non-bg in pred, bg in expected)?
    pred_nonbg = all(pv != 0 for pv in pred_vals)
    exp_bg = all(ev == 0 for ev in exp_vals)
    if pred_nonbg and exp_bg:
        return "partial_clear"

    # Check: reflection residual
    H, W = pred.shape
    for transform_fn in [np.fliplr, np.flipud, lambda x: np.rot90(x, 1)]:
        transformed = transform_fn(pred)
        if transformed.shape == exp.shape:
            overlap = np.sum(transformed == exp)
            if overlap > np.sum(pred == exp):
                return "reflection_residual"

    # Check: object misplacement (same colors, different positions)
    pred_colors = Counter(int(v) for v in pred.flat if v != 0)
    exp_colors = Counter(int(v) for v in exp.flat if v != 0)
    if pred_colors == exp_colors and len(wrong) > 0:
        return "object_misplace"

    return "scattered"


def _suggest_corrections(pattern: str) -> List[str]:
    """Suggest correction strategies for each error pattern."""
    return {
        "color_swap": ["color_remap", "color_swap"],
        "shifted": ["translation", "gravity"],
        "partial_fill": ["fill_bg", "flood_fill", "neighbor_fill"],
        "partial_clear": ["remove_color", "object_filter"],
        "reflection_residual": ["reflection", "rotation", "overlay"],
        "object_misplace": ["gravity", "sort", "translation"],
        "scattered": ["context_rule", "local_rule", "reasoner"],
        "shape_mismatch": ["output_shape_predictor"],
        "none": [],
    }.get(pattern, ["context_rule"])


def suggest_correction_ops(
    diagnosis: FailureDiagnosis,
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> List[SynthesizedOperator]:
    """Generate correction operators based on diagnosis."""
    results = []
    pattern = diagnosis.error_pattern

    if pattern == "color_swap":
        results.extend(_build_color_remap_corrections(diagnosis, train_pairs))
    elif pattern == "partial_fill":
        results.extend(_build_fill_corrections(diagnosis, train_pairs))
    elif pattern == "partial_clear":
        results.extend(_build_clear_corrections(diagnosis, train_pairs))
    elif pattern == "shifted":
        results.extend(_build_shift_corrections(diagnosis, train_pairs))
    elif pattern == "reflection_residual":
        results.extend(_build_reflection_corrections(diagnosis, train_pairs))

    return results


def _build_color_remap_corrections(diagnosis, train_pairs):
    """Build color remapping corrections."""
    results = []
    swap_map = {}
    for _, _, pv, ev in diagnosis.wrong_pixels:
        if pv not in swap_map:
            swap_map[pv] = ev
        elif swap_map[pv] != ev:
            return results

    if swap_map:
        def make_remap(m):
            def fn(grid, _m=m):
                out = grid.copy()
                for src, tgt in _m.items():
                    out[grid == src] = tgt
                return out
            return fn

        fn = make_remap(swap_map)
        if _verify(fn, train_pairs):
            results.append(SynthesizedOperator(
                operator_id=f"diag_remap_{uuid.uuid4().hex[:8]}",
                operator_family="diagnosed_color_remap",
                parameters={"remap": swap_map},
                preconditions=[],
                execute=fn,
                explanation=f"[Diagnosed] Color remap: {swap_map}",
                source_failure_signature={},
            ))
    return results


def _build_fill_corrections(diagnosis, train_pairs):
    """Fill bg pixels that should be non-bg."""
    results = []
    exp_vals = [ev for _, _, _, ev in diagnosis.wrong_pixels]
    if len(set(exp_vals)) == 1:
        fill_color = exp_vals[0]

        def make_fill(fc, mask):
            def fn(grid, _fc=fc, _m=mask):
                out = grid.copy()
                if grid.shape == _m.shape:
                    out[_m & (grid == 0)] = _fc
                return out
            return fn

        fn = make_fill(fill_color, diagnosis.error_region_mask)
        if _verify(fn, train_pairs):
            results.append(SynthesizedOperator(
                operator_id=f"diag_fill_{uuid.uuid4().hex[:8]}",
                operator_family="diagnosed_fill",
                parameters={"fill_color": fill_color},
                preconditions=[],
                execute=fn,
                explanation=f"[Diagnosed] Fill missing regions with {fill_color}",
                source_failure_signature={},
            ))

    # Neighbor fill: fill bg from nearest non-bg neighbor
    def make_neighbor_fill():
        def fn(grid):
            out = grid.copy()
            H, W = grid.shape
            changed = True
            iterations = 0
            while changed and iterations < 5:
                changed = False
                iterations += 1
                for r in range(H):
                    for c in range(W):
                        if out[r, c] != 0:
                            continue
                        neighbors = []
                        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                            nr, nc = r + dr, c + dc
                            if 0 <= nr < H and 0 <= nc < W and out[nr, nc] != 0:
                                neighbors.append(int(out[nr, nc]))
                        if neighbors:
                            out[r, c] = Counter(neighbors).most_common(1)[0][0]
                            changed = True
            return out
        return fn

    fn = make_neighbor_fill()
    if _verify(fn, train_pairs):
        results.append(SynthesizedOperator(
            operator_id=f"diag_neighfill_{uuid.uuid4().hex[:8]}",
            operator_family="diagnosed_neighbor_fill",
            parameters={},
            preconditions=[],
            execute=fn,
            explanation="[Diagnosed] Fill bg from nearest neighbors",
            source_failure_signature={},
        ))
    return results


def _build_clear_corrections(diagnosis, train_pairs):
    """Clear non-bg pixels that should be bg."""
    results = []
    pred_vals = [pv for _, _, pv, _ in diagnosis.wrong_pixels]
    colors_to_clear = set(pred_vals)

    for color in colors_to_clear:
        def make_clear(c):
            def fn(grid, _c=c):
                out = grid.copy()
                out[grid == _c] = 0
                return out
            return fn
        fn = make_clear(color)
        if _verify(fn, train_pairs):
            results.append(SynthesizedOperator(
                operator_id=f"diag_clear_{color}_{uuid.uuid4().hex[:8]}",
                operator_family="diagnosed_clear",
                parameters={"color": color},
                preconditions=[],
                execute=fn,
                explanation=f"[Diagnosed] Clear color {color}",
                source_failure_signature={},
            ))
    return results


def _build_shift_corrections(diagnosis, train_pairs):
    """Translate the grid to fix shifted errors."""
    results = []
    if not diagnosis.wrong_pixels:
        return results

    for dr in range(-3, 4):
        for dc in range(-3, 4):
            if dr == 0 and dc == 0:
                continue

            def make_shift(dr_, dc_):
                def fn(grid, _dr=dr_, _dc=dc_):
                    H, W = grid.shape
                    out = np.zeros_like(grid)
                    for r in range(H):
                        for c in range(W):
                            sr, sc = r - _dr, c - _dc
                            if 0 <= sr < H and 0 <= sc < W:
                                out[r, c] = grid[sr, sc]
                    return out
                return fn

            fn = make_shift(dr, dc)
            if _verify(fn, train_pairs):
                results.append(SynthesizedOperator(
                    operator_id=f"diag_shift_{dr}_{dc}_{uuid.uuid4().hex[:8]}",
                    operator_family="diagnosed_shift",
                    parameters={"dr": dr, "dc": dc},
                    preconditions=[],
                    execute=fn,
                    explanation=f"[Diagnosed] Shift by ({dr}, {dc})",
                    source_failure_signature={},
                ))
                return results
    return results


def _build_reflection_corrections(diagnosis, train_pairs):
    """Apply reflection/rotation to fix reflection residual errors."""
    results = []
    for name, transform in [
        ("fliplr", np.fliplr),
        ("flipud", np.flipud),
        ("rot90", lambda x: np.rot90(x, 1)),
        ("rot180", lambda x: np.rot90(x, 2)),
        ("rot270", lambda x: np.rot90(x, 3)),
    ]:
        def make_transform(t):
            def fn(grid, _t=t):
                return _t(grid)
            return fn
        fn = make_transform(transform)
        if _verify(fn, train_pairs):
            results.append(SynthesizedOperator(
                operator_id=f"diag_{name}_{uuid.uuid4().hex[:8]}",
                operator_family=f"diagnosed_{name}",
                parameters={},
                preconditions=[],
                execute=fn,
                explanation=f"[Diagnosed] Apply {name}",
                source_failure_signature={},
            ))
    return results


def _verify(fn, train_pairs):
    for inp, out in train_pairs:
        try:
            pred = fn(inp)
            if pred is None or not isinstance(pred, np.ndarray):
                return False
            if pred.shape != out.shape or not np.array_equal(pred, out):
                return False
        except Exception:
            return False
    return True
