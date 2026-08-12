"""Analogical Transfer (H6): recognize shared abstract structure between tasks.

Tasks that look different on the surface (different colors, grid sizes, shapes)
may share the same underlying transformation rule. This module computes abstract
task signatures and finds analogous tasks to enable solution transfer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np


@dataclass
class TaskSignature:
    """Abstract properties of a task that capture its transformation structure,
    independent of surface features like specific colors or exact grid sizes.

    Fields:
        size_relation: ratio of output size to input size (area ratio), averaged
        color_count_change: average change in number of distinct colors (out - in)
        symmetry_h_in: fraction of training inputs with horizontal symmetry
        symmetry_v_in: fraction of training inputs with vertical symmetry
        symmetry_h_out: fraction of training outputs with horizontal symmetry
        symmetry_v_out: fraction of training outputs with vertical symmetry
        component_count_change: average change in connected component count
        same_shape: whether input and output always have the same shape
        color_preservation_rate: fraction of colors preserved from input to output
        spatial_overlap: average fraction of non-background pixels that overlap
    """
    size_relation: float = 1.0
    color_count_change: float = 0.0
    symmetry_h_in: float = 0.0
    symmetry_v_in: float = 0.0
    symmetry_h_out: float = 0.0
    symmetry_v_out: float = 0.0
    component_count_change: float = 0.0
    same_shape: bool = True
    color_preservation_rate: float = 1.0
    spatial_overlap: float = 0.0


def _has_horizontal_symmetry(grid: np.ndarray) -> bool:
    """Check if grid is symmetric about its horizontal axis."""
    return bool(np.array_equal(grid, grid[::-1, :]))


def _has_vertical_symmetry(grid: np.ndarray) -> bool:
    """Check if grid is symmetric about its vertical axis."""
    return bool(np.array_equal(grid, grid[:, ::-1]))


def _count_connected_components(grid: np.ndarray, background: int = 0) -> int:
    """Count connected components (4-connected) excluding background."""
    try:
        from scipy import ndimage
    except ImportError:
        # Fallback: count unique non-background colors as proxy
        return len(set(grid.flatten().tolist()) - {background})
    mask = grid != background
    if not mask.any():
        return 0
    labeled, n = ndimage.label(mask)
    return int(n)


def compute_task_signature(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> TaskSignature:
    """Compute an abstract task signature from training input-output pairs.

    Args:
        train_pairs: list of (input_grid, output_grid) numpy arrays

    Returns:
        TaskSignature capturing abstract transformation properties
    """
    if not train_pairs:
        return TaskSignature()

    size_ratios = []
    color_changes = []
    sym_h_in_vals = []
    sym_v_in_vals = []
    sym_h_out_vals = []
    sym_v_out_vals = []
    comp_changes = []
    shapes_match = True
    color_preserved = []
    overlaps = []

    for inp, out in train_pairs:
        inp = np.asarray(inp, dtype=int)
        out = np.asarray(out, dtype=int)

        # Size relation
        in_area = max(inp.shape[0] * inp.shape[1], 1)
        out_area = max(out.shape[0] * out.shape[1], 1)
        size_ratios.append(out_area / in_area)

        # Color count change
        in_colors = set(inp.flatten().tolist())
        out_colors = set(out.flatten().tolist())
        color_changes.append(len(out_colors) - len(in_colors))

        # Symmetry
        sym_h_in_vals.append(float(_has_horizontal_symmetry(inp)))
        sym_v_in_vals.append(float(_has_vertical_symmetry(inp)))
        sym_h_out_vals.append(float(_has_horizontal_symmetry(out)))
        sym_v_out_vals.append(float(_has_vertical_symmetry(out)))

        # Connected component count change
        in_comps = _count_connected_components(inp)
        out_comps = _count_connected_components(out)
        comp_changes.append(out_comps - in_comps)

        # Same shape
        if inp.shape != out.shape:
            shapes_match = False

        # Color preservation
        shared = in_colors & out_colors
        all_colors = in_colors | out_colors
        if all_colors:
            color_preserved.append(len(shared) / len(all_colors))
        else:
            color_preserved.append(1.0)

        # Spatial overlap (only if same shape)
        if inp.shape == out.shape:
            in_mask = inp != 0
            out_mask = out != 0
            union = np.logical_or(in_mask, out_mask)
            inter = np.logical_and(in_mask, out_mask)
            if union.sum() > 0:
                overlaps.append(float(inter.sum()) / float(union.sum()))
            else:
                overlaps.append(1.0)
        else:
            overlaps.append(0.0)

    return TaskSignature(
        size_relation=float(np.mean(size_ratios)),
        color_count_change=float(np.mean(color_changes)),
        symmetry_h_in=float(np.mean(sym_h_in_vals)),
        symmetry_v_in=float(np.mean(sym_v_in_vals)),
        symmetry_h_out=float(np.mean(sym_h_out_vals)),
        symmetry_v_out=float(np.mean(sym_v_out_vals)),
        component_count_change=float(np.mean(comp_changes)),
        same_shape=shapes_match,
        color_preservation_rate=float(np.mean(color_preserved)),
        spatial_overlap=float(np.mean(overlaps)) if overlaps else 0.0,
    )


def signature_similarity(sig_a: TaskSignature, sig_b: TaskSignature) -> float:
    """Compute similarity between two task signatures.

    Returns a float in [0, 1] where 1 means identical signatures.
    Uses weighted feature comparison across all signature dimensions.
    """
    diffs = []

    # Size relation: log-scale difference (ratio of ratios)
    ratio_a = max(sig_a.size_relation, 1e-6)
    ratio_b = max(sig_b.size_relation, 1e-6)
    size_diff = abs(np.log(ratio_a) - np.log(ratio_b))
    diffs.append(1.0 / (1.0 + size_diff))

    # Color count change
    cc_diff = abs(sig_a.color_count_change - sig_b.color_count_change)
    diffs.append(1.0 / (1.0 + cc_diff))

    # Symmetry properties (4 comparisons)
    for attr in ["symmetry_h_in", "symmetry_v_in", "symmetry_h_out", "symmetry_v_out"]:
        diff = abs(getattr(sig_a, attr) - getattr(sig_b, attr))
        diffs.append(1.0 - diff)

    # Component count change
    comp_diff = abs(sig_a.component_count_change - sig_b.component_count_change)
    diffs.append(1.0 / (1.0 + comp_diff))

    # Same shape (boolean match)
    diffs.append(1.0 if sig_a.same_shape == sig_b.same_shape else 0.0)

    # Color preservation rate
    cp_diff = abs(sig_a.color_preservation_rate - sig_b.color_preservation_rate)
    diffs.append(1.0 - cp_diff)

    # Spatial overlap
    so_diff = abs(sig_a.spatial_overlap - sig_b.spatial_overlap)
    diffs.append(1.0 - so_diff)

    return float(np.mean(diffs))


def find_analogous_tasks(
    target_signature: TaskSignature,
    solved_tasks: Dict[str, TaskSignature],
    threshold: float = 0.7,
) -> List[Tuple[str, float]]:
    """Find solved tasks whose signatures are analogous to the target.

    Args:
        target_signature: signature of the unsolved task
        solved_tasks: dict mapping task_id -> TaskSignature for solved tasks
        threshold: minimum similarity to be considered analogous

    Returns:
        List of (task_id, similarity) tuples, sorted by similarity descending
    """
    matches = []
    for task_id, sig in solved_tasks.items():
        sim = signature_similarity(target_signature, sig)
        if sim >= threshold:
            matches.append((task_id, sim))
    matches.sort(key=lambda x: x[1], reverse=True)
    return matches


def transfer_solution(
    source_train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    source_predictions: List[np.ndarray],
    target_train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    target_test_inputs: List[np.ndarray],
) -> Optional[List[np.ndarray]]:
    """Try to transfer a source task's solution strategy to a target task.

    Attempts to infer a color mapping and spatial transformation that adapts
    the source solution to work on the target task.

    Args:
        source_train_pairs: training pairs of the solved source task
        source_predictions: predictions made by the source solver
        target_train_pairs: training pairs of the unsolved target task
        target_test_inputs: test inputs for the target task

    Returns:
        List of predicted output grids, or None if transfer fails
    """
    if not source_train_pairs or not target_train_pairs:
        return None

    # Strategy 1: Try to find a color remapping that makes the source
    # transformation work on target examples
    source_inp, source_out = source_train_pairs[0]
    target_inp, target_out = target_train_pairs[0]

    # Check if shapes are compatible
    src_size_ratio = (source_out.shape[0] * source_out.shape[1]) / max(
        source_inp.shape[0] * source_inp.shape[1], 1
    )
    tgt_size_ratio = (target_out.shape[0] * target_out.shape[1]) / max(
        target_inp.shape[0] * target_inp.shape[1], 1
    )
    if abs(src_size_ratio - tgt_size_ratio) > 0.1:
        return None  # Incompatible size transformations

    # Try to learn color mapping from source to target
    src_in_colors = sorted(set(source_inp.flatten().tolist()))
    tgt_in_colors = sorted(set(target_inp.flatten().tolist()))
    src_out_colors = sorted(set(source_out.flatten().tolist()))
    tgt_out_colors = sorted(set(target_out.flatten().tolist()))

    if len(src_in_colors) != len(tgt_in_colors):
        return None  # Different color count, hard to map

    # Build color mapping by frequency ordering
    def _color_freq(grid):
        unique, counts = np.unique(grid, return_counts=True)
        return sorted(zip(unique, counts), key=lambda x: -x[1])

    src_in_freq = _color_freq(source_inp)
    tgt_in_freq = _color_freq(target_inp)
    src_out_freq = _color_freq(source_out)
    tgt_out_freq = _color_freq(target_out)

    # Map source colors to target colors by frequency rank
    in_color_map = {}
    for (sc, _), (tc, _) in zip(src_in_freq, tgt_in_freq):
        in_color_map[sc] = tc

    out_color_map = {}
    if len(src_out_freq) == len(tgt_out_freq):
        for (sc, _), (tc, _) in zip(src_out_freq, tgt_out_freq):
            out_color_map[sc] = tc

    # Infer per-color transform on source, then map to target
    src_transform = {}
    if source_inp.shape == source_out.shape:
        for sc in src_in_colors:
            mask = source_inp == sc
            if mask.any():
                out_vals = source_out[mask]
                if len(out_vals) > 0:
                    most_common = int(np.bincount(out_vals.astype(int).clip(0, 10)).argmax())
                    src_transform[sc] = most_common

    tgt_transform = {}
    for sc, tc in in_color_map.items():
        if sc in src_transform:
            src_out_color = src_transform[sc]
            if src_out_color in out_color_map:
                tgt_transform[tc] = out_color_map[src_out_color]
            elif src_out_color in in_color_map:
                tgt_transform[tc] = in_color_map[src_out_color]
            else:
                tgt_transform[tc] = tc

    # Validate on target training pair
    if target_inp.shape == target_out.shape and tgt_transform:
        test_pred = target_inp.copy()
        for c_in, c_out in tgt_transform.items():
            test_pred[target_inp == c_in] = c_out

        if np.array_equal(test_pred, target_out):
            # Transfer works -- apply to all test inputs
            predictions = []
            for test_inp in target_test_inputs:
                pred = test_inp.copy()
                for c_in, c_out in tgt_transform.items():
                    pred[test_inp == c_in] = c_out
                predictions.append(pred)
            return predictions

    # Validate on all training pairs
    if tgt_transform and all(
        inp.shape == out.shape for inp, out in target_train_pairs
    ):
        all_ok = True
        for inp, out in target_train_pairs:
            test_pred = inp.copy()
            for c_in, c_out in tgt_transform.items():
                test_pred[inp == c_in] = c_out
            if not np.array_equal(test_pred, out):
                all_ok = False
                break
        if all_ok:
            predictions = []
            for test_inp in target_test_inputs:
                pred = test_inp.copy()
                for c_in, c_out in tgt_transform.items():
                    pred[test_inp == c_in] = c_out
                predictions.append(pred)
            return predictions

    return None
