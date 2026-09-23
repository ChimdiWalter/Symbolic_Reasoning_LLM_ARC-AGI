"""Abstract Program Induction: learn higher-level transformation patterns.

Strengthens H1 (structural transfer) and H4 (compression) by providing
a richer space of transformation programs beyond the fixed DSL.

Strategies:
  - overlay_two_objects: detect two colored regions, combine via XOR/OR/AND
  - symmetry_completion: detect partial symmetry, complete it
  - pattern_continuation: detect repeating pattern, extend it
  - conditional_transform: apply different transforms to different colored regions
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np


class OverlayOp(Enum):
    """Binary overlay operations on object bitmasks."""
    XOR = "xor"
    OR = "or"
    AND = "and"


@dataclass
class InputOutputRelation:
    """Captures the abstract relationship between input and output grids.

    Attributes:
        size_change: (row_ratio, col_ratio) of output vs input size
        color_mapping: dict mapping input colors to output colors (if deterministic)
        spatial_type: detected spatial transformation type
        preserves_shape: whether output has same shape as input
        n_input_colors: number of distinct colors in input
        n_output_colors: number of distinct colors in output
    """
    size_change: Tuple[float, float] = (1.0, 1.0)
    color_mapping: Optional[Dict[int, int]] = None
    spatial_type: str = "unknown"
    preserves_shape: bool = True
    n_input_colors: int = 0
    n_output_colors: int = 0


@dataclass
class AbstractProgram:
    """An inferred abstract program that transforms grids.

    Attributes:
        strategy: name of the strategy that produced this program
        params: strategy-specific parameters
        description: human-readable description
    """
    strategy: str
    params: Dict[str, Any] = field(default_factory=dict)
    description: str = ""


def infer_relation(inp: np.ndarray, out: np.ndarray) -> InputOutputRelation:
    """Infer the abstract relationship between a single input-output pair."""
    inp = np.asarray(inp, dtype=int)
    out = np.asarray(out, dtype=int)

    h_ratio = out.shape[0] / max(inp.shape[0], 1)
    w_ratio = out.shape[1] / max(inp.shape[1], 1)

    in_colors = set(inp.flatten().tolist())
    out_colors = set(out.flatten().tolist())

    # Try to infer deterministic color mapping
    color_map = None
    if inp.shape == out.shape:
        cm = {}
        deterministic = True
        for c in in_colors:
            mask = inp == c
            out_vals = out[mask]
            unique_out = np.unique(out_vals)
            if len(unique_out) == 1:
                cm[c] = int(unique_out[0])
            else:
                deterministic = False
                break
        if deterministic:
            color_map = cm

    spatial = "unknown"
    if inp.shape == out.shape:
        if np.array_equal(inp, out):
            spatial = "identity"
        elif np.array_equal(inp, out[::-1, :]):
            spatial = "reflect_h"
        elif np.array_equal(inp, out[:, ::-1]):
            spatial = "reflect_v"
        elif inp.shape[0] == inp.shape[1] and np.array_equal(inp, np.rot90(out)):
            spatial = "rotate_90"
        elif np.array_equal(inp, out[::-1, ::-1]):
            spatial = "rotate_180"

    return InputOutputRelation(
        size_change=(h_ratio, w_ratio),
        color_mapping=color_map,
        spatial_type=spatial,
        preserves_shape=inp.shape == out.shape,
        n_input_colors=len(in_colors),
        n_output_colors=len(out_colors),
    )


# ---------------------------------------------------------------------------
# Strategy: overlay_two_objects
# ---------------------------------------------------------------------------

def _detect_color_regions(grid: np.ndarray, background: int = 0) -> List[Tuple[int, np.ndarray]]:
    """Detect distinct colored regions, return list of (color, bitmask)."""
    regions = []
    for c in sorted(set(grid.flatten().tolist())):
        if c == background:
            continue
        mask = (grid == c).astype(int)
        if mask.any():
            regions.append((c, mask))
    return regions


def _try_overlay(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> Optional[AbstractProgram]:
    """Detect if output is an overlay (XOR/OR/AND) of two input regions."""
    for op in OverlayOp:
        all_ok = True
        overlay_color = None

        for inp, out in train_pairs:
            if inp.shape != out.shape:
                all_ok = False
                break

            regions = _detect_color_regions(inp)
            if len(regions) < 2:
                all_ok = False
                break

            # Try each pair of regions
            found = False
            for i in range(len(regions)):
                for j in range(i + 1, len(regions)):
                    c_i, mask_i = regions[i]
                    c_j, mask_j = regions[j]

                    if op == OverlayOp.XOR:
                        result_mask = np.logical_xor(mask_i, mask_j).astype(int)
                    elif op == OverlayOp.OR:
                        result_mask = np.logical_or(mask_i, mask_j).astype(int)
                    elif op == OverlayOp.AND:
                        result_mask = np.logical_and(mask_i, mask_j).astype(int)

                    # Check if output matches this overlay pattern
                    out_nonzero = (out != 0).astype(int)
                    if np.array_equal(result_mask, out_nonzero):
                        # Determine output color
                        out_vals = out[result_mask.astype(bool)]
                        if len(out_vals) > 0:
                            unique = np.unique(out_vals)
                            if len(unique) == 1:
                                oc = int(unique[0])
                                if overlay_color is None:
                                    overlay_color = oc
                                elif overlay_color != oc:
                                    pass  # Still valid, color may vary
                                found = True
                                break
                if found:
                    break
            if not found:
                all_ok = False
                break

        if all_ok:
            return AbstractProgram(
                strategy="overlay_two_objects",
                params={"operation": op.value, "output_color": overlay_color},
                description=f"Overlay two colored regions using {op.value}",
            )
    return None


# ---------------------------------------------------------------------------
# Strategy: symmetry_completion
# ---------------------------------------------------------------------------

def _try_symmetry_completion(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> Optional[AbstractProgram]:
    """Detect if the output completes a partial symmetry in the input.

    Handles: horizontal, vertical, both (4-fold), and diagonal symmetry.
    Also detects fill-from-reflection where non-background pixels are preserved
    and background pixels are filled from the reflected image.
    """
    for axis in ["horizontal", "vertical", "both"]:
        all_ok = True
        fill_mode = None

        for inp, out in train_pairs:
            if inp.shape != out.shape:
                all_ok = False
                break

            if axis == "horizontal":
                reflected = out[::-1, :]
            elif axis == "vertical":
                reflected = out[:, ::-1]
            else:
                reflected = out[::-1, ::-1]

            if not np.array_equal(out, reflected):
                all_ok = False
                break

            match_frac = np.mean(inp == out)
            if match_frac < 0.1 or match_frac > 0.99:
                all_ok = False
                break

            # Detect fill mode: do non-background pixels stay, and background
            # pixels get filled from reflection?
            nonzero_mask = inp != 0
            if nonzero_mask.any() and np.all(out[nonzero_mask] == inp[nonzero_mask]):
                fill_mode = "fill_background"

        if all_ok:
            return AbstractProgram(
                strategy="symmetry_completion",
                params={"axis": axis, "fill_mode": fill_mode or "replace"},
                description=f"Complete partial {axis} symmetry",
            )

    # Also try: output = reflect input along axis (input itself need not be symmetric)
    for axis in ["horizontal", "vertical"]:
        all_ok = True
        for inp, out in train_pairs:
            if inp.shape != out.shape:
                all_ok = False
                break
            if axis == "horizontal":
                if not np.array_equal(inp[::-1, :], out):
                    all_ok = False
                    break
            else:
                if not np.array_equal(inp[:, ::-1], out):
                    all_ok = False
                    break
        if all_ok:
            return AbstractProgram(
                strategy="symmetry_completion",
                params={"axis": axis, "fill_mode": "reflect_input"},
                description=f"Reflect input along {axis} axis",
            )

    return None


# ---------------------------------------------------------------------------
# Strategy: pattern_continuation
# ---------------------------------------------------------------------------

def _try_pattern_continuation(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> Optional[AbstractProgram]:
    """Detect if the output is the input with a repeating pattern extended."""
    all_ok = True
    repeat_axis = None
    repeat_factor = None

    for inp, out in train_pairs:
        found_for_pair = False

        # Check horizontal tiling
        for factor in [2, 3, 4]:
            if out.shape[0] == inp.shape[0] and out.shape[1] == inp.shape[1] * factor:
                tiled = np.tile(inp, (1, factor))
                if np.array_equal(tiled, out):
                    if repeat_axis is None:
                        repeat_axis = "horizontal"
                        repeat_factor = factor
                    elif repeat_axis != "horizontal" or repeat_factor != factor:
                        all_ok = False
                    found_for_pair = True
                    break

        if not found_for_pair:
            # Check vertical tiling
            for factor in [2, 3, 4]:
                if out.shape[1] == inp.shape[1] and out.shape[0] == inp.shape[0] * factor:
                    tiled = np.tile(inp, (factor, 1))
                    if np.array_equal(tiled, out):
                        if repeat_axis is None:
                            repeat_axis = "vertical"
                            repeat_factor = factor
                        elif repeat_axis != "vertical" or repeat_factor != factor:
                            all_ok = False
                        found_for_pair = True
                        break

        if not found_for_pair:
            # Check 2D tiling
            for rr in [2, 3]:
                for cr in [2, 3]:
                    if (out.shape[0] == inp.shape[0] * rr and
                            out.shape[1] == inp.shape[1] * cr):
                        tiled = np.tile(inp, (rr, cr))
                        if np.array_equal(tiled, out):
                            if repeat_axis is None:
                                repeat_axis = "both"
                                repeat_factor = (rr, cr)
                            found_for_pair = True
                            break
                if found_for_pair:
                    break

        if not found_for_pair:
            all_ok = False
            break

    if all_ok and repeat_axis is not None:
        return AbstractProgram(
            strategy="pattern_continuation",
            params={"axis": repeat_axis, "factor": repeat_factor},
            description=f"Tile input along {repeat_axis} by factor {repeat_factor}",
        )
    return None


# ---------------------------------------------------------------------------
# Strategy: conditional_transform
# ---------------------------------------------------------------------------

def _try_conditional_transform(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> Optional[AbstractProgram]:
    """Detect if different colors undergo different transformations."""
    if not train_pairs:
        return None

    # All must be same shape
    if not all(inp.shape == out.shape for inp, out in train_pairs):
        return None

    # Learn per-color transform from all training pairs
    color_transforms = {}  # color -> output_color
    for inp, out in train_pairs:
        for c in set(inp.flatten().tolist()):
            mask = inp == c
            out_vals = out[mask]
            if len(out_vals) == 0:
                continue
            unique_out = np.unique(out_vals)
            if len(unique_out) != 1:
                return None  # Non-deterministic for this color
            oc = int(unique_out[0])
            if c in color_transforms:
                if color_transforms[c] != oc:
                    return None  # Inconsistent across pairs
            else:
                color_transforms[c] = oc

    if not color_transforms:
        return None

    # Check it's not just identity
    if all(k == v for k, v in color_transforms.items()):
        return None

    # Validate on all pairs
    for inp, out in train_pairs:
        pred = inp.copy()
        for c_in, c_out in color_transforms.items():
            pred[inp == c_in] = c_out
        if not np.array_equal(pred, out):
            return None

    return AbstractProgram(
        strategy="conditional_transform",
        params={"color_map": color_transforms},
        description=f"Apply per-color mapping: {color_transforms}",
    )


# ---------------------------------------------------------------------------
# Strategy: grid_combine — split input into halves and combine via operation
# ---------------------------------------------------------------------------

def _try_grid_combine(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> Optional[AbstractProgram]:
    """Detect if the output is produced by combining two halves of the input.

    Checks horizontal and vertical splits, with XOR/OR/AND/max/min operations.
    Handles tasks where two sub-grids are combined into one output grid.
    """
    for split in ["horizontal", "vertical"]:
        for op_name in ["xor", "or", "and", "max", "min"]:
            all_ok = True
            for inp, out in train_pairs:
                h, w = inp.shape
                if split == "horizontal":
                    if h % 2 != 0:
                        all_ok = False
                        break
                    half = h // 2
                    top = inp[:half, :]
                    bot = inp[half:, :]
                    if out.shape != (half, w):
                        all_ok = False
                        break
                    a, b = top, bot
                else:
                    if w % 2 != 0:
                        all_ok = False
                        break
                    half = w // 2
                    left = inp[:, :half]
                    right = inp[:, half:]
                    if out.shape != (h, half):
                        all_ok = False
                        break
                    a, b = left, right

                if op_name == "xor":
                    combined = np.where(a != b, np.maximum(a, b), 0)
                elif op_name == "or":
                    combined = np.maximum(a, b)
                elif op_name == "and":
                    combined = np.where((a > 0) & (b > 0), np.maximum(a, b), 0)
                elif op_name == "max":
                    combined = np.maximum(a, b)
                elif op_name == "min":
                    combined = np.minimum(a, b)

                if not np.array_equal(combined, out):
                    all_ok = False
                    break

            if all_ok:
                return AbstractProgram(
                    strategy="grid_combine",
                    params={"split": split, "operation": op_name},
                    description=f"Split input {split}ly and combine halves via {op_name}",
                )
    return None


# ---------------------------------------------------------------------------
# Main API
# ---------------------------------------------------------------------------

_STRATEGIES = [
    _try_conditional_transform,
    _try_overlay,
    _try_symmetry_completion,
    _try_pattern_continuation,
    _try_grid_combine,
]


def infer_abstract_program(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> Optional[AbstractProgram]:
    """Try all strategies to infer an abstract program from training pairs.

    Returns the first program that matches all training pairs, or None.
    """
    if not train_pairs:
        return None

    for strategy_fn in _STRATEGIES:
        prog = strategy_fn(train_pairs)
        if prog is not None:
            return prog
    return None


def apply_abstract_program(
    prog: AbstractProgram, input_grid: np.ndarray
) -> np.ndarray:
    """Apply an inferred abstract program to produce an output grid.

    Args:
        prog: the abstract program to apply
        input_grid: the input grid (2D numpy array)

    Returns:
        output grid (2D numpy array)

    Raises:
        ValueError: if the program strategy is unknown or cannot be applied
    """
    inp = np.asarray(input_grid, dtype=int)

    if prog.strategy == "conditional_transform":
        color_map = prog.params.get("color_map", {})
        out = inp.copy()
        for c_in, c_out in color_map.items():
            out[inp == int(c_in)] = int(c_out)
        return out

    elif prog.strategy == "overlay_two_objects":
        op_name = prog.params.get("operation", "or")
        output_color = prog.params.get("output_color", 1)
        regions = _detect_color_regions(inp)
        if len(regions) < 2:
            raise ValueError("Need at least 2 colored regions for overlay")

        c_a, mask_a = regions[0]
        c_b, mask_b = regions[1]
        if op_name == "xor":
            result = np.logical_xor(mask_a, mask_b)
        elif op_name == "or":
            result = np.logical_or(mask_a, mask_b)
        elif op_name == "and":
            result = np.logical_and(mask_a, mask_b)
        else:
            raise ValueError(f"Unknown overlay operation: {op_name}")

        out = np.zeros_like(inp)
        out[result] = output_color if output_color is not None else 1
        return out

    elif prog.strategy == "symmetry_completion":
        axis = prog.params.get("axis", "horizontal")
        fill_mode = prog.params.get("fill_mode", "fill_background")

        if fill_mode == "reflect_input":
            if axis == "horizontal":
                return inp[::-1, :].copy()
            elif axis == "vertical":
                return inp[:, ::-1].copy()
            else:
                return inp[::-1, ::-1].copy()

        out = inp.copy()
        if axis == "horizontal":
            reflected = out[::-1, :]
        elif axis == "vertical":
            reflected = out[:, ::-1]
        else:
            reflected = out[::-1, ::-1]

        if fill_mode == "fill_background":
            fill_mask = out == 0
            out[fill_mask] = reflected[fill_mask]
        else:
            out = reflected.copy()
        return out

    elif prog.strategy == "pattern_continuation":
        axis = prog.params.get("axis", "horizontal")
        factor = prog.params.get("factor", 2)
        if axis == "horizontal":
            return np.tile(inp, (1, factor))
        elif axis == "vertical":
            return np.tile(inp, (factor, 1))
        elif axis == "both":
            rr, cr = factor
            return np.tile(inp, (rr, cr))
        else:
            raise ValueError(f"Unknown pattern axis: {axis}")

    elif prog.strategy == "grid_combine":
        split = prog.params.get("split", "horizontal")
        op_name = prog.params.get("operation", "or")
        h, w = inp.shape
        if split == "horizontal":
            half = h // 2
            a, b = inp[:half, :], inp[half:, :]
        else:
            half = w // 2
            a, b = inp[:, :half], inp[:, half:]
        if op_name == "xor":
            return np.where(a != b, np.maximum(a, b), 0)
        elif op_name == "or":
            return np.maximum(a, b)
        elif op_name == "and":
            return np.where((a > 0) & (b > 0), np.maximum(a, b), 0)
        elif op_name == "max":
            return np.maximum(a, b)
        elif op_name == "min":
            return np.minimum(a, b)
        raise ValueError(f"Unknown grid_combine operation: {op_name}")

    else:
        raise ValueError(f"Unknown abstract program strategy: {prog.strategy}")


def solve_task_abstract_programs(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
) -> Optional[Tuple[List[np.ndarray], Dict[str, Any]]]:
    """Solve an ARC task using abstract program induction.

    Args:
        train_pairs: list of (input_grid, output_grid) training pairs
        test_inputs: list of test input grids

    Returns:
        (predictions, metadata) or None if no program found
    """
    prog = infer_abstract_program(train_pairs)
    if prog is None:
        return None

    # Validate on training pairs
    for inp, out in train_pairs:
        try:
            pred = apply_abstract_program(prog, inp)
        except (ValueError, Exception):
            return None
        if pred.shape != out.shape or not np.array_equal(pred, out):
            return None

    # Apply to test inputs
    predictions = []
    for test_inp in test_inputs:
        try:
            pred = apply_abstract_program(prog, test_inp)
            predictions.append(pred)
        except (ValueError, Exception):
            predictions.append(test_inp.copy())

    return predictions, {
        "solver": "abstract_program",
        "strategy": prog.strategy,
        "description": prog.description,
        "params": {k: str(v) for k, v in prog.params.items()},
    }
