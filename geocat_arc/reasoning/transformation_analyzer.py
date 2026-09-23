"""Transformation analyzer — classifies what kind of transform a task requires.

Analyzes training pairs to determine:
  - same shape vs different shape
  - what fraction of cells change
  - color transformations present
  - structural patterns (crop, tile, fill, symmetry)
"""
from __future__ import annotations
from dataclasses import dataclass
from collections import Counter
import numpy as np


@dataclass
class TransformationProfile:
    same_shape: bool
    cell_change_rate: float
    is_identity: bool
    color_mapping: dict[int, int] | None
    has_new_colors: bool
    has_removed_colors: bool
    input_colors: set[int]
    output_colors: set[int]
    output_is_subgrid: bool
    output_is_tile: bool
    is_symmetric_completion: bool
    dominant_pattern: str


def analyze_pair(inp: np.ndarray, out: np.ndarray) -> dict:
    same_shape = inp.shape == out.shape
    in_colors = set(int(x) for x in np.unique(inp))
    out_colors = set(int(x) for x in np.unique(out))

    if same_shape:
        changed = int(np.sum(inp != out))
        total = inp.size
        change_rate = changed / total if total > 0 else 0.0
    else:
        change_rate = 1.0

    color_map = _detect_color_permutation(inp, out) if same_shape else None

    return {
        "same_shape": same_shape,
        "change_rate": change_rate,
        "in_colors": in_colors,
        "out_colors": out_colors,
        "new_colors": out_colors - in_colors,
        "removed_colors": in_colors - out_colors,
        "color_map": color_map,
        "input_shape": inp.shape,
        "output_shape": out.shape,
    }


def _detect_color_permutation(inp: np.ndarray, out: np.ndarray) -> dict[int, int] | None:
    if inp.shape != out.shape:
        return None
    mapping: dict[int, set[int]] = {}
    h, w = inp.shape
    for r in range(h):
        for c in range(w):
            ic = int(inp[r, c])
            oc = int(out[r, c])
            if ic not in mapping:
                mapping[ic] = set()
            mapping[ic].add(oc)

    result = {}
    for ic, ocs in mapping.items():
        if len(ocs) == 1:
            result[ic] = next(iter(ocs))
        else:
            return None
    return result


def _check_subgrid(inp: np.ndarray, out: np.ndarray) -> bool:
    oh, ow = out.shape
    ih, iw = inp.shape
    if oh > ih or ow > iw:
        return False
    for r in range(ih - oh + 1):
        for c in range(iw - ow + 1):
            if np.array_equal(inp[r:r + oh, c:c + ow], out):
                return True
    return False


def _check_tile(inp: np.ndarray, out: np.ndarray) -> bool:
    ih, iw = inp.shape
    oh, ow = out.shape
    if oh < ih or ow < iw:
        return False
    if oh % ih != 0 or ow % iw != 0:
        return False
    for r in range(0, oh, ih):
        for c in range(0, ow, iw):
            if not np.array_equal(out[r:r + ih, c:c + iw], inp):
                return False
    return True


def _check_symmetric_completion(inp: np.ndarray, out: np.ndarray) -> bool:
    if inp.shape != out.shape:
        return False
    h, w = out.shape
    h_sym = np.array_equal(out, np.flipud(out))
    v_sym = np.array_equal(out, np.fliplr(out))
    if not (h_sym or v_sym):
        return False
    return not (np.array_equal(inp, np.flipud(inp)) and np.array_equal(inp, np.fliplr(inp)))


def analyze_task(
    train_pairs: list[tuple[np.ndarray, np.ndarray]],
) -> TransformationProfile:
    pair_analyses = [analyze_pair(inp, out) for inp, out in train_pairs]

    same_shape = all(a["same_shape"] for a in pair_analyses)
    change_rates = [a["change_rate"] for a in pair_analyses]
    avg_change = float(np.mean(change_rates))
    is_identity = avg_change == 0.0

    all_in_colors = set()
    all_out_colors = set()
    for a in pair_analyses:
        all_in_colors |= a["in_colors"]
        all_out_colors |= a["out_colors"]

    has_new = bool(all_out_colors - all_in_colors)
    has_removed = bool(all_in_colors - all_out_colors)

    color_maps = [a["color_map"] for a in pair_analyses]
    global_color_map = color_maps[0] if all(m == color_maps[0] for m in color_maps) and color_maps[0] else None

    is_subgrid = all(
        _check_subgrid(inp, out)
        for inp, out in train_pairs
    ) if not same_shape else False

    is_tile = all(
        _check_tile(inp, out)
        for inp, out in train_pairs
    ) if not same_shape else False

    is_sym = all(
        _check_symmetric_completion(inp, out)
        for inp, out in train_pairs
    ) if same_shape else False

    if is_identity:
        pattern = "identity"
    elif global_color_map and all(k != v for k, v in global_color_map.items() if k != v):
        pattern = "color_permutation"
    elif is_subgrid:
        pattern = "crop"
    elif is_tile:
        pattern = "tile"
    elif is_sym:
        pattern = "symmetric_completion"
    elif same_shape and avg_change < 0.3:
        pattern = "local_edit"
    elif same_shape:
        pattern = "global_transform"
    else:
        pattern = "shape_change"

    return TransformationProfile(
        same_shape=same_shape,
        cell_change_rate=avg_change,
        is_identity=is_identity,
        color_mapping=global_color_map,
        has_new_colors=has_new,
        has_removed_colors=has_removed,
        input_colors=all_in_colors,
        output_colors=all_out_colors,
        output_is_subgrid=is_subgrid,
        output_is_tile=is_tile,
        is_symmetric_completion=is_sym,
        dominant_pattern=pattern,
    )
