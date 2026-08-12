"""Adaptive Synthesizer: delta-guided recursive program synthesis.

Uses TaskDelta from delta_engine to constrain which primitive operations
to try, enabling depth-3+ compositional search without combinatorial
explosion. Instead of enumerating all programs, the delta tells us:
  - "output is smaller" → try crop/extract
  - "colors changed but positions didn't" → try recolor/color_map
  - "objects moved consistently" → try translate
  - "none of the above" → recursive decomposition

For composition, we use top-down decomposition:
  1. Identify the outermost operation from delta
  2. Invert it to compute intermediate targets
  3. Recursively synthesize the inner program on (input → intermediate)

Output: List[SynthesizedOperator] compatible with the orchestrator pipeline.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

from reasoning_project.delta_engine import (
    TaskDelta,
    PairDelta,
    compute_task_delta,
    compute_pair_delta,
    score_partial_correctness,
    compute_residual,
)
from reasoning_project.operator_genesis import SynthesizedOperator


def _check_train_consistency(
    fn: Callable[[np.ndarray], np.ndarray],
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> bool:
    for inp, out in train_pairs:
        try:
            pred = fn(inp)
            if pred is None:
                return False
            if not isinstance(pred, np.ndarray):
                return False
            if pred.shape != out.shape:
                return False
            if not np.array_equal(pred, out):
                return False
        except Exception:
            return False
    return True


def _check_loo(
    fn: Callable[[np.ndarray], np.ndarray],
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> bool:
    if len(train_pairs) < 2:
        return True
    for i in range(len(train_pairs)):
        held_out_inp, held_out_out = train_pairs[i]
        try:
            pred = fn(held_out_inp)
            if pred is None or pred.shape != held_out_out.shape:
                return False
            if not np.array_equal(pred, held_out_out):
                return False
        except Exception:
            return False
    return True


# ---------------------------------------------------------------------------
# Primitive operations library
# ---------------------------------------------------------------------------

def _try_reflection(train_pairs, delta: TaskDelta) -> List[SynthesizedOperator]:
    if not delta.consistent_reflection:
        return []
    axis = delta.consistent_reflection
    def make_fn(ax):
        def fn(grid, _ax=ax):
            if _ax == "vertical":
                return grid[::-1, :].copy()
            elif _ax == "horizontal":
                return grid[:, ::-1].copy()
            elif _ax == "both":
                return grid[::-1, ::-1].copy()
            return grid.copy()
        return fn
    fn = make_fn(axis)
    if _check_train_consistency(fn, train_pairs):
        return [SynthesizedOperator(
            operator_id=f"adap_reflect_{uuid.uuid4().hex[:8]}",
            operator_family="reflection",
            parameters={"axis": axis},
            preconditions=[],
            execute=fn,
            explanation=f"Reflect {axis}",
            source_failure_signature={},
        )]
    return []


def _try_rotation(train_pairs, delta: TaskDelta) -> List[SynthesizedOperator]:
    if not delta.consistent_rotation:
        return []
    angle = delta.consistent_rotation
    def make_fn(a):
        def fn(grid, _a=a):
            return np.rot90(grid, k=_a // 90).copy()
        return fn
    fn = make_fn(angle)
    if _check_train_consistency(fn, train_pairs):
        return [SynthesizedOperator(
            operator_id=f"adap_rotate_{uuid.uuid4().hex[:8]}",
            operator_family="rotation",
            parameters={"angle": angle},
            preconditions=[],
            execute=fn,
            explanation=f"Rotate {angle}°",
            source_failure_signature={},
        )]
    return []


def _try_transpose(train_pairs, delta: TaskDelta) -> List[SynthesizedOperator]:
    if not all(pd.evidence.get("is_transpose") for pd in delta.pair_deltas):
        return []
    def fn(grid):
        return grid.T.copy()
    if _check_train_consistency(fn, train_pairs):
        return [SynthesizedOperator(
            operator_id=f"adap_transpose_{uuid.uuid4().hex[:8]}",
            operator_family="transpose",
            parameters={},
            preconditions=[],
            execute=fn,
            explanation="Transpose",
            source_failure_signature={},
        )]
    return []


def _try_color_map(train_pairs, delta: TaskDelta) -> List[SynthesizedOperator]:
    if not delta.consistent_color_map:
        return []
    cmap = delta.consistent_color_map
    def make_fn(cm):
        def fn(grid, _cm=cm):
            out = grid.copy()
            for src, dst in _cm.items():
                out[grid == src] = dst
            return out
        return fn
    fn = make_fn(cmap)
    if _check_train_consistency(fn, train_pairs):
        return [SynthesizedOperator(
            operator_id=f"adap_colormap_{uuid.uuid4().hex[:8]}",
            operator_family="color_map",
            parameters={"mapping": cmap},
            preconditions=[],
            execute=fn,
            explanation=f"Color map: {cmap}",
            source_failure_signature={},
        )]
    return []


def _try_crop_to_content(train_pairs, delta: TaskDelta) -> List[SynthesizedOperator]:
    if delta.consistent_same_size is not False:
        return []
    if not all(pd.is_crop for pd in delta.pair_deltas):
        return []

    results = []
    bg_candidates = [0]
    pd0 = delta.pair_deltas[0]
    if pd0.bg_color not in bg_candidates:
        bg_candidates.append(pd0.bg_color)

    for bg in bg_candidates:
        def make_fn(b):
            def fn(grid, _bg=b):
                nonbg = np.argwhere(grid != _bg)
                if len(nonbg) == 0:
                    return grid.copy()
                r0, c0 = nonbg.min(axis=0)
                r1, c1 = nonbg.max(axis=0)
                return grid[r0:r1+1, c0:c1+1].copy()
            return fn
        fn = make_fn(bg)
        if _check_train_consistency(fn, train_pairs):
            results.append(SynthesizedOperator(
                operator_id=f"adap_crop_content_{uuid.uuid4().hex[:8]}",
                operator_family="crop_to_content",
                parameters={"bg": bg},
                preconditions=[],
                execute=fn,
                explanation=f"Crop to non-background content (bg={bg})",
                source_failure_signature={},
            ))
    return results


def _try_crop_to_color(train_pairs, delta: TaskDelta) -> List[SynthesizedOperator]:
    if delta.consistent_same_size is not False:
        return []
    results = []
    for color in range(10):
        def make_fn(c):
            def fn(grid, _c=c):
                mask = grid == _c
                if not mask.any():
                    return grid.copy()
                rows, cols = np.where(mask)
                r0, c0 = rows.min(), cols.min()
                r1, c1 = rows.max(), cols.max()
                return grid[r0:r1+1, c0:c1+1].copy()
            return fn
        fn = make_fn(color)
        if _check_train_consistency(fn, train_pairs):
            results.append(SynthesizedOperator(
                operator_id=f"adap_crop_color_{color}_{uuid.uuid4().hex[:8]}",
                operator_family="crop_to_color",
                parameters={"color": color},
                preconditions=[],
                execute=fn,
                explanation=f"Crop to bounding box of color {color}",
                source_failure_signature={},
            ))
    return results


def _try_tile(train_pairs, delta: TaskDelta) -> List[SynthesizedOperator]:
    if not all(pd.is_tile and pd.tile_factor for pd in delta.pair_deltas):
        return []
    factors = [pd.tile_factor for pd in delta.pair_deltas]
    if len(set(factors)) != 1:
        return []
    th, tw = factors[0]
    def make_fn(h, w):
        def fn(grid, _h=h, _w=w):
            return np.tile(grid, (_h, _w))
        return fn
    fn = make_fn(th, tw)
    if _check_train_consistency(fn, train_pairs):
        return [SynthesizedOperator(
            operator_id=f"adap_tile_{uuid.uuid4().hex[:8]}",
            operator_family="tile",
            parameters={"factor": (th, tw)},
            preconditions=[],
            execute=fn,
            explanation=f"Tile {th}x{tw}",
            source_failure_signature={},
        )]
    return []


def _try_consistent_translation(train_pairs, delta: TaskDelta) -> List[SynthesizedOperator]:
    if not delta.consistent_translation:
        return []
    dr, dc = delta.consistent_translation
    def make_fn(r, c):
        def fn(grid, _dr=r, _dc=c):
            H, W = grid.shape
            out = np.zeros_like(grid)
            for ro in range(H):
                for co in range(W):
                    nr, nc = ro + _dr, co + _dc
                    if 0 <= nr < H and 0 <= nc < W:
                        out[nr, nc] = grid[ro, co]
            return out
        return fn
    fn = make_fn(dr, dc)
    if _check_train_consistency(fn, train_pairs):
        return [SynthesizedOperator(
            operator_id=f"adap_translate_{uuid.uuid4().hex[:8]}",
            operator_family="translation",
            parameters={"dr": dr, "dc": dc},
            preconditions=[],
            execute=fn,
            explanation=f"Translate by ({dr}, {dc})",
            source_failure_signature={},
        )]
    return []


def _try_fill_changed_cells(train_pairs, delta: TaskDelta) -> List[SynthesizedOperator]:
    """If cells that change share a common input property, learn that property."""
    if delta.consistent_same_size is not True:
        return []
    if not all(pd.changed_mask is not None for pd in delta.pair_deltas):
        return []
    results = []

    # Discover what the changed cells have in common across training pairs
    # Strategy 1: changed cells are exactly the bg (0) cells
    # Strategy 2: changed cells are exactly the cells with a specific color
    # Strategy 3: positional mask consistent across all pairs
    for fill_color in range(10):
        # Strategy 1: fill all bg cells with fill_color
        def make_bg_fill(fc):
            def fn(grid, _fc=fc):
                out = grid.copy()
                out[grid == 0] = _fc
                return out
            return fn
        fn = make_bg_fill(fill_color)
        if _check_train_consistency(fn, train_pairs):
            results.append(SynthesizedOperator(
                operator_id=f"adap_fill_bg_{fill_color}_{uuid.uuid4().hex[:8]}",
                operator_family="fill_changed",
                parameters={"fill_color": fill_color, "strategy": "bg_fill"},
                preconditions=[],
                execute=fn,
                explanation=f"Fill bg cells with color {fill_color}",
                source_failure_signature={},
            ))

        # Strategy 2: fill cells matching a specific input color
        for src_color in range(10):
            if src_color == fill_color:
                continue
            def make_color_fill(sc, fc):
                def fn(grid, _sc=sc, _fc=fc):
                    out = grid.copy()
                    out[grid == _sc] = _fc
                    return out
                return fn
            fn = make_color_fill(src_color, fill_color)
            if _check_train_consistency(fn, train_pairs):
                results.append(SynthesizedOperator(
                    operator_id=f"adap_fill_color_{src_color}to{fill_color}_{uuid.uuid4().hex[:8]}",
                    operator_family="fill_changed",
                    parameters={"src_color": src_color, "fill_color": fill_color,
                                "strategy": "color_replace"},
                    preconditions=[],
                    execute=fn,
                    explanation=f"Replace color {src_color} with {fill_color}",
                    source_failure_signature={},
                ))

    # Strategy 3: positional mask — only if the mask is identical across ALL pairs
    masks = []
    for inp, out in train_pairs:
        masks.append(inp != out)
    if len(masks) >= 2 and all(np.array_equal(masks[0], m) for m in masks[1:]):
        consistent_mask = masks[0]
        for fill_color in range(10):
            def make_pos_fill(m, fc):
                def fn(grid, _m=m, _fc=fc):
                    if grid.shape != _m.shape:
                        return grid.copy()
                    out = grid.copy()
                    out[_m] = _fc
                    return out
                return fn
            fn = make_pos_fill(consistent_mask, fill_color)
            if _check_train_consistency(fn, train_pairs):
                results.append(SynthesizedOperator(
                    operator_id=f"adap_fill_posmask_{fill_color}_{uuid.uuid4().hex[:8]}",
                    operator_family="fill_changed",
                    parameters={"fill_color": fill_color, "strategy": "positional_mask"},
                    preconditions=[],
                    execute=fn,
                    explanation=f"Fill fixed positional mask with color {fill_color}",
                    source_failure_signature={},
                ))
    return results


def _try_gravity(train_pairs, delta: TaskDelta) -> List[SynthesizedOperator]:
    """Try gravity (objects fall in a direction)."""
    if delta.consistent_same_size is not True:
        return []
    results = []
    for direction in ["down", "up", "left", "right"]:
        def make_fn(d):
            def fn(grid, _d=d):
                H, W = grid.shape
                out = np.zeros_like(grid)
                bg = 0
                if _d == "down":
                    for c in range(W):
                        col = [grid[r, c] for r in range(H) if grid[r, c] != bg]
                        for i, v in enumerate(col):
                            out[H - len(col) + i, c] = v
                elif _d == "up":
                    for c in range(W):
                        col = [grid[r, c] for r in range(H) if grid[r, c] != bg]
                        for i, v in enumerate(col):
                            out[i, c] = v
                elif _d == "right":
                    for r in range(H):
                        row = [grid[r, c] for c in range(W) if grid[r, c] != bg]
                        for i, v in enumerate(row):
                            out[r, W - len(row) + i] = v
                elif _d == "left":
                    for r in range(H):
                        row = [grid[r, c] for c in range(W) if grid[r, c] != bg]
                        for i, v in enumerate(row):
                            out[r, i] = v
                return out
            return fn
        fn = make_fn(direction)
        if _check_train_consistency(fn, train_pairs):
            results.append(SynthesizedOperator(
                operator_id=f"adap_gravity_{direction}_{uuid.uuid4().hex[:8]}",
                operator_family="gravity",
                parameters={"direction": direction},
                preconditions=[],
                execute=fn,
                explanation=f"Gravity {direction}",
                source_failure_signature={},
            ))
    return results


def _try_sort_rows_cols(train_pairs, delta: TaskDelta) -> List[SynthesizedOperator]:
    """Try sorting rows or columns by some property."""
    if delta.consistent_same_size is not True:
        return []
    results = []
    for mode in ["sort_rows_by_count", "sort_cols_by_count"]:
        def make_fn(m):
            def fn(grid, _m=m):
                if _m == "sort_rows_by_count":
                    counts = [(np.count_nonzero(grid[r, :]), r) for r in range(grid.shape[0])]
                    counts.sort()
                    return np.array([grid[r, :] for _, r in counts])
                else:
                    counts = [(np.count_nonzero(grid[:, c]), c) for c in range(grid.shape[1])]
                    counts.sort()
                    return np.array([grid[:, c] for _, c in counts]).T
            return fn
        fn = make_fn(mode)
        if _check_train_consistency(fn, train_pairs):
            results.append(SynthesizedOperator(
                operator_id=f"adap_{mode}_{uuid.uuid4().hex[:8]}",
                operator_family="sort",
                parameters={"mode": mode},
                preconditions=[],
                execute=fn,
                explanation=f"Sort: {mode}",
                source_failure_signature={},
            ))
    return results


def _try_downscale(train_pairs, delta: TaskDelta) -> List[SynthesizedOperator]:
    """If output is consistently smaller by integer factor, try downscaling."""
    if delta.consistent_same_size is not False:
        return []
    results = []
    ratios = set()
    for pd in delta.pair_deltas:
        ih, iw = pd.input_shape
        oh, ow = pd.output_shape
        if ih % oh == 0 and iw % ow == 0:
            ratios.add((ih // oh, iw // ow))
    if len(ratios) != 1:
        return []
    rh, rw = ratios.pop()
    if rh < 2 and rw < 2:
        return []
    for mode in ["majority", "top_left"]:
        def make_fn(h, w, m):
            def fn(grid, _rh=h, _rw=w, _m=m):
                H, W = grid.shape
                oh, ow = H // _rh, W // _rw
                out = np.zeros((oh, ow), dtype=grid.dtype)
                for r in range(oh):
                    for c in range(ow):
                        patch = grid[r*_rh:(r+1)*_rh, c*_rw:(c+1)*_rw]
                        if _m == "top_left":
                            out[r, c] = patch[0, 0]
                        else:
                            vals, counts = np.unique(patch, return_counts=True)
                            out[r, c] = vals[counts.argmax()]
                return out
            return fn
        fn = make_fn(rh, rw, mode)
        if _check_train_consistency(fn, train_pairs):
            results.append(SynthesizedOperator(
                operator_id=f"adap_downscale_{mode}_{uuid.uuid4().hex[:8]}",
                operator_family="downscale",
                parameters={"ratio": (rh, rw), "mode": mode},
                preconditions=[],
                execute=fn,
                explanation=f"Downscale {rh}x{rw} ({mode})",
                source_failure_signature={},
            ))
    return results


def _try_upscale(train_pairs, delta: TaskDelta) -> List[SynthesizedOperator]:
    """If output is consistently larger by integer factor, try upscaling."""
    if delta.consistent_same_size is not False:
        return []
    ratios = set()
    for pd in delta.pair_deltas:
        ih, iw = pd.input_shape
        oh, ow = pd.output_shape
        if oh % ih == 0 and ow % iw == 0:
            ratios.add((oh // ih, ow // iw))
    if len(ratios) != 1:
        return []
    rh, rw = ratios.pop()
    if rh < 2 and rw < 2:
        return []
    def make_fn(h, w):
        def fn(grid, _rh=h, _rw=w):
            return np.repeat(np.repeat(grid, _rh, axis=0), _rw, axis=1)
        return fn
    fn = make_fn(rh, rw)
    if _check_train_consistency(fn, train_pairs):
        return [SynthesizedOperator(
            operator_id=f"adap_upscale_{uuid.uuid4().hex[:8]}",
            operator_family="upscale",
            parameters={"ratio": (rh, rw)},
            preconditions=[],
            execute=fn,
            explanation=f"Upscale {rh}x{rw}",
            source_failure_signature={},
        )]
    return []


def _try_identity_subgrid(train_pairs, delta: TaskDelta) -> List[SynthesizedOperator]:
    """Output is a specific subgrid of input (fixed offset across pairs)."""
    if delta.consistent_same_size is not False:
        return []
    results = []
    oh, ow = delta.pair_deltas[0].output_shape
    if any(pd.output_shape != (oh, ow) for pd in delta.pair_deltas):
        return []

    offsets = set()
    for inp, out in train_pairs:
        ih, iw = inp.shape
        if oh > ih or ow > iw:
            return []
        found = False
        for r in range(ih - oh + 1):
            for c in range(iw - ow + 1):
                if np.array_equal(inp[r:r+oh, c:c+ow], out):
                    offsets.add((r, c))
                    found = True
                    break
            if found:
                break
        if not found:
            return []

    if len(offsets) == 1:
        ro, co = offsets.pop()
        def make_fn(r, c, h, w):
            def fn(grid, _r=r, _c=c, _h=h, _w=w):
                return grid[_r:_r+_h, _c:_c+_w].copy()
            return fn
        fn = make_fn(ro, co, oh, ow)
        if _check_train_consistency(fn, train_pairs):
            results.append(SynthesizedOperator(
                operator_id=f"adap_subgrid_{uuid.uuid4().hex[:8]}",
                operator_family="subgrid_extract",
                parameters={"offset": (ro, co), "size": (oh, ow)},
                preconditions=[],
                execute=fn,
                explanation=f"Extract subgrid at ({ro},{co}) size {oh}x{ow}",
                source_failure_signature={},
            ))
    return results


def _try_mask_by_color(train_pairs, delta: TaskDelta) -> List[SynthesizedOperator]:
    """Replace all instances of one color with another."""
    if delta.consistent_same_size is not True:
        return []
    results = []
    for src in range(10):
        for dst in range(10):
            if src == dst:
                continue
            def make_fn(s, d):
                def fn(grid, _s=s, _d=d):
                    out = grid.copy()
                    out[grid == _s] = _d
                    return out
                return fn
            fn = make_fn(src, dst)
            if _check_train_consistency(fn, train_pairs):
                results.append(SynthesizedOperator(
                    operator_id=f"adap_recolor_{src}_{dst}_{uuid.uuid4().hex[:8]}",
                    operator_family="single_recolor",
                    parameters={"src": src, "dst": dst},
                    preconditions=[],
                    execute=fn,
                    explanation=f"Recolor {src} → {dst}",
                    source_failure_signature={},
                ))
                if len(results) > 3:
                    return results
    return results


def _try_border_fill(train_pairs, delta: TaskDelta) -> List[SynthesizedOperator]:
    """Fill the border of the grid with a specific color."""
    if delta.consistent_same_size is not True:
        return []
    results = []
    for color in range(10):
        def make_fn(c):
            def fn(grid, _c=c):
                out = grid.copy()
                out[0, :] = _c
                out[-1, :] = _c
                out[:, 0] = _c
                out[:, -1] = _c
                return out
            return fn
        fn = make_fn(color)
        if _check_train_consistency(fn, train_pairs):
            results.append(SynthesizedOperator(
                operator_id=f"adap_border_fill_{color}_{uuid.uuid4().hex[:8]}",
                operator_family="border_fill",
                parameters={"color": color},
                preconditions=[],
                execute=fn,
                explanation=f"Fill border with color {color}",
                source_failure_signature={},
            ))
    return results


def _try_flood_fill_bg(train_pairs, delta: TaskDelta) -> List[SynthesizedOperator]:
    """Fill all background-connected regions with a specific color."""
    if delta.consistent_same_size is not True:
        return []
    from scipy.ndimage import label as ndlabel
    results = []
    for fill_color in range(1, 10):
        for bg in [0]:
            def make_fn(fc, b):
                def fn(grid, _fc=fc, _bg=b):
                    from scipy.ndimage import label as ndlabel
                    out = grid.copy()
                    mask = grid == _bg
                    labeled, n = ndlabel(mask)
                    for comp_id in range(1, n + 1):
                        comp = labeled == comp_id
                        rows, cols = np.where(comp)
                        touches_border = (rows.min() == 0 or rows.max() == grid.shape[0]-1 or
                                         cols.min() == 0 or cols.max() == grid.shape[1]-1)
                        if not touches_border:
                            out[comp] = _fc
                    return out
                return fn
            fn = make_fn(fill_color, bg)
            if _check_train_consistency(fn, train_pairs):
                results.append(SynthesizedOperator(
                    operator_id=f"adap_flood_fill_{fill_color}_{uuid.uuid4().hex[:8]}",
                    operator_family="flood_fill_enclosed",
                    parameters={"fill_color": fill_color, "bg": bg},
                    preconditions=[],
                    execute=fn,
                    explanation=f"Fill enclosed bg regions with color {fill_color}",
                    source_failure_signature={},
                ))
    return results


def _try_replace_bg_with_output_pattern(train_pairs, delta: TaskDelta) -> List[SynthesizedOperator]:
    """If output replaces bg cells with values from a fixed pattern, learn that pattern."""
    if delta.consistent_same_size is not True:
        return []
    if len(train_pairs) < 2:
        return []
    results = []

    inp0, out0 = train_pairs[0]
    changed = inp0 != out0
    if not changed.any():
        return []
    fill_vals = out0[changed]
    if len(set(fill_vals.flat)) > 2:
        return []
    unique_fill = set(int(v) for v in fill_vals)
    if len(unique_fill) != 1:
        return []
    fill_val = unique_fill.pop()

    for condition in ["is_bg", "equals_0"]:
        def make_fn(fv, cond):
            def fn(grid, _fv=fv, _cond=cond):
                out = grid.copy()
                if _cond == "is_bg":
                    out[grid == 0] = _fv
                elif _cond == "equals_0":
                    out[grid == 0] = _fv
                return out
            return fn
        fn = make_fn(fill_val, condition)
        if _check_train_consistency(fn, train_pairs):
            results.append(SynthesizedOperator(
                operator_id=f"adap_replace_bg_{fill_val}_{uuid.uuid4().hex[:8]}",
                operator_family="replace_bg",
                parameters={"fill_value": fill_val},
                preconditions=[],
                execute=fn,
                explanation=f"Replace background with color {fill_val}",
                source_failure_signature={},
            ))
    return results


def _try_max_color_per_row_col(train_pairs, delta: TaskDelta) -> List[SynthesizedOperator]:
    """Try extracting max/min/most-frequent color per row or column."""
    if delta.consistent_same_size is False:
        return []
    results = []

    for mode in ["max_row", "max_col", "most_freq_row", "most_freq_col"]:
        def make_fn(m):
            def fn(grid, _m=m):
                H, W = grid.shape
                if _m == "max_row":
                    out = np.zeros((H, 1), dtype=grid.dtype)
                    for r in range(H):
                        out[r, 0] = grid[r, :].max()
                    return out
                elif _m == "max_col":
                    out = np.zeros((1, W), dtype=grid.dtype)
                    for c in range(W):
                        out[0, c] = grid[:, c].max()
                    return out
                elif _m == "most_freq_row":
                    out = np.zeros((H, 1), dtype=grid.dtype)
                    for r in range(H):
                        vals, counts = np.unique(grid[r, :], return_counts=True)
                        nonzero = vals != 0
                        if nonzero.any():
                            out[r, 0] = vals[nonzero][counts[nonzero].argmax()]
                    return out
                elif _m == "most_freq_col":
                    out = np.zeros((1, W), dtype=grid.dtype)
                    for c in range(W):
                        vals, counts = np.unique(grid[:, c], return_counts=True)
                        nonzero = vals != 0
                        if nonzero.any():
                            out[0, c] = vals[nonzero][counts[nonzero].argmax()]
                    return out
                return grid.copy()
            return fn
        fn = make_fn(mode)
        if _check_train_consistency(fn, train_pairs):
            results.append(SynthesizedOperator(
                operator_id=f"adap_{mode}_{uuid.uuid4().hex[:8]}",
                operator_family=mode,
                parameters={"mode": mode},
                preconditions=[],
                execute=fn,
                explanation=f"Extract {mode} from grid",
                source_failure_signature={},
            ))
    return results


def _try_unique_color_per_row_col(train_pairs, delta: TaskDelta) -> List[SynthesizedOperator]:
    """Extract the unique non-background color from each row or column."""
    results = []
    for axis_name, axis in [("row", 1), ("col", 0)]:
        def make_fn(ax, ax_name):
            def fn(grid, _ax=ax, _ax_name=ax_name):
                H, W = grid.shape
                if _ax == 1:
                    out = np.zeros((H, 1), dtype=grid.dtype)
                    for r in range(H):
                        nonzero = grid[r, grid[r, :] != 0]
                        unique = np.unique(nonzero)
                        if len(unique) == 1:
                            out[r, 0] = unique[0]
                    return out
                else:
                    out = np.zeros((1, W), dtype=grid.dtype)
                    for c in range(W):
                        nonzero = grid[grid[:, c] != 0, c]
                        unique = np.unique(nonzero)
                        if len(unique) == 1:
                            out[0, c] = unique[0]
                    return out
            return fn
        fn = make_fn(axis, axis_name)
        if _check_train_consistency(fn, train_pairs):
            results.append(SynthesizedOperator(
                operator_id=f"adap_unique_color_{axis_name}_{uuid.uuid4().hex[:8]}",
                operator_family=f"unique_color_{axis_name}",
                parameters={"axis": axis_name},
                preconditions=[],
                execute=fn,
                explanation=f"Unique non-bg color per {axis_name}",
                source_failure_signature={},
            ))
    return results


def _try_output_equals_input_mask(train_pairs, delta: TaskDelta) -> List[SynthesizedOperator]:
    """Output is a binary mask of where input has non-bg cells."""
    if delta.consistent_same_size is not True:
        return []
    results = []
    for marker_color in range(1, 10):
        def make_fn(mc):
            def fn(grid, _mc=mc):
                out = np.zeros_like(grid)
                out[grid != 0] = _mc
                return out
            return fn
        fn = make_fn(marker_color)
        if _check_train_consistency(fn, train_pairs):
            results.append(SynthesizedOperator(
                operator_id=f"adap_mask_{marker_color}_{uuid.uuid4().hex[:8]}",
                operator_family="binary_mask",
                parameters={"marker_color": marker_color},
                preconditions=[],
                execute=fn,
                explanation=f"Binary mask of non-bg cells (color {marker_color})",
                source_failure_signature={},
            ))
    return results


def _try_diagonal_flip(train_pairs, delta: TaskDelta) -> List[SynthesizedOperator]:
    """Try flipping along diagonals."""
    results = []
    for mode in ["main_diagonal", "anti_diagonal"]:
        def make_fn(m):
            def fn(grid, _m=m):
                if _m == "main_diagonal":
                    return grid.T.copy()
                else:
                    return np.flip(np.flip(grid, 0).T, 0).copy()
            return fn
        fn = make_fn(mode)
        if _check_train_consistency(fn, train_pairs):
            results.append(SynthesizedOperator(
                operator_id=f"adap_diag_flip_{mode}_{uuid.uuid4().hex[:8]}",
                operator_family=f"diagonal_flip_{mode}",
                parameters={"mode": mode},
                preconditions=[],
                execute=fn,
                explanation=f"Flip along {mode}",
                source_failure_signature={},
            ))
    return results


def _try_count_colors(train_pairs, delta: TaskDelta) -> List[SynthesizedOperator]:
    """Output might be a 1x1 grid with the count of non-bg colors, or number of objects."""
    results = []
    for mode in ["count_nonbg_colors", "count_objects", "count_nonbg_cells"]:
        def make_fn(m):
            def fn(grid, _m=m):
                from scipy.ndimage import label as ndlabel
                if _m == "count_nonbg_colors":
                    n = len([c for c in np.unique(grid) if c != 0])
                    return np.array([[n]])
                elif _m == "count_objects":
                    _, n = ndlabel(grid != 0)
                    return np.array([[n]])
                elif _m == "count_nonbg_cells":
                    return np.array([[int(np.count_nonzero(grid))]])
                return grid.copy()
            return fn
        fn = make_fn(mode)
        if _check_train_consistency(fn, train_pairs):
            results.append(SynthesizedOperator(
                operator_id=f"adap_{mode}_{uuid.uuid4().hex[:8]}",
                operator_family=mode,
                parameters={"mode": mode},
                preconditions=[],
                execute=fn,
                explanation=f"Count: {mode}",
                source_failure_signature={},
            ))
    return results


def _try_keep_largest_object(train_pairs, delta: TaskDelta) -> List[SynthesizedOperator]:
    """Keep only the largest connected component."""
    results = []
    from scipy.ndimage import label as ndlabel
    for keep in ["largest", "smallest"]:
        def make_fn(k):
            def fn(grid, _k=k):
                from scipy.ndimage import label as ndlabel
                out = np.zeros_like(grid)
                labeled, n = ndlabel(grid != 0)
                if n == 0:
                    return out
                sizes = []
                for i in range(1, n+1):
                    sizes.append((labeled == i).sum())
                if _k == "largest":
                    best = np.argmax(sizes) + 1
                else:
                    best = np.argmin(sizes) + 1
                out[labeled == best] = grid[labeled == best]
                return out
            return fn
        fn = make_fn(keep)
        if _check_train_consistency(fn, train_pairs):
            results.append(SynthesizedOperator(
                operator_id=f"adap_keep_{keep}_{uuid.uuid4().hex[:8]}",
                operator_family=f"keep_{keep}_object",
                parameters={"keep": keep},
                preconditions=[],
                execute=fn,
                explanation=f"Keep {keep} object only",
                source_failure_signature={},
            ))
    return results


def _try_remove_color(train_pairs, delta: TaskDelta) -> List[SynthesizedOperator]:
    """Remove all instances of a specific color (set to 0)."""
    if delta.consistent_same_size is not True:
        return []
    results = []
    for color in range(1, 10):
        def make_fn(c):
            def fn(grid, _c=c):
                out = grid.copy()
                out[grid == _c] = 0
                return out
            return fn
        fn = make_fn(color)
        if _check_train_consistency(fn, train_pairs):
            results.append(SynthesizedOperator(
                operator_id=f"adap_remove_color_{color}_{uuid.uuid4().hex[:8]}",
                operator_family="remove_color",
                parameters={"color": color},
                preconditions=[],
                execute=fn,
                explanation=f"Remove color {color}",
                source_failure_signature={},
            ))
    return results


def _try_bitwise_ops(train_pairs, delta: TaskDelta) -> List[SynthesizedOperator]:
    """Try AND/OR/XOR between halves of the input grid."""
    if delta.consistent_same_size is False:
        return []
    results = []
    for split in ["horizontal", "vertical"]:
        for op_name in ["and", "or", "xor"]:
            def make_fn(s, o):
                def fn(grid, _s=s, _o=o):
                    H, W = grid.shape
                    if _s == "horizontal":
                        if H % 2 != 0:
                            return grid.copy()
                        half = H // 2
                        top = grid[:half, :]
                        bot = grid[half:, :]
                        a = (top != 0).astype(int)
                        b = (bot != 0).astype(int)
                    else:
                        if W % 2 != 0:
                            return grid.copy()
                        half = W // 2
                        left = grid[:, :half]
                        right = grid[:, half:]
                        a = (left != 0).astype(int)
                        b = (right != 0).astype(int)
                    if _o == "and":
                        mask = a & b
                    elif _o == "or":
                        mask = a | b
                    else:
                        mask = a ^ b
                    if _s == "horizontal":
                        result = np.where(mask, top, 0)
                    else:
                        result = np.where(mask, grid[:, :W//2], 0)
                    return result
                return fn
            fn = make_fn(split, op_name)
            if _check_train_consistency(fn, train_pairs):
                results.append(SynthesizedOperator(
                    operator_id=f"adap_bitwise_{split}_{op_name}_{uuid.uuid4().hex[:8]}",
                    operator_family=f"bitwise_{op_name}",
                    parameters={"split": split, "op": op_name},
                    preconditions=[],
                    execute=fn,
                    explanation=f"Split {split}, {op_name} halves",
                    source_failure_signature={},
                ))
    return results


# ---------------------------------------------------------------------------
# Residual-based refinement
# ---------------------------------------------------------------------------

def _find_best_partial(
    candidates: List[SynthesizedOperator],
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    min_accuracy: float = 0.5,
) -> List[Tuple[SynthesizedOperator, float, List[np.ndarray]]]:
    """Score candidates by partial correctness and return those above threshold."""
    scored = []
    for op in candidates:
        total_acc = 0.0
        preds = []
        valid = True
        for inp, out in train_pairs:
            try:
                pred = op.execute(inp)
                if pred is None:
                    valid = False
                    break
                sc = score_partial_correctness(pred, out)
                total_acc += sc["score"]
                preds.append(pred)
            except Exception:
                valid = False
                break
        if not valid:
            continue
        avg_acc = total_acc / len(train_pairs)
        if avg_acc >= min_accuracy:
            scored.append((op, avg_acc, preds))
    scored.sort(key=lambda x: -x[1])
    return scored


def _try_residual_correction(
    partial_op: SynthesizedOperator,
    partial_preds: List[np.ndarray],
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> List[SynthesizedOperator]:
    """Given a partial solution, compute residual and search for correction."""
    correction_pairs = []
    for pred, (_, expected) in zip(partial_preds, train_pairs):
        if pred.shape != expected.shape:
            return []
        correction_pairs.append((pred, expected))

    correction_delta = compute_task_delta(correction_pairs)

    correction_ops = []
    for try_fn in [_try_color_map, _try_mask_by_color, _try_fill_changed_cells,
                   _try_reflection, _try_gravity, _try_sort_rows_cols,
                   _try_border_fill]:
        correction_ops.extend(try_fn(correction_pairs, correction_delta))

    results = []
    for corr_op in correction_ops:
        def make_composed(base, correction):
            def fn(grid, _b=base.execute, _c=correction.execute):
                intermediate = _b(grid)
                return _c(intermediate)
            return fn
        composed_fn = make_composed(partial_op, corr_op)
        if _check_train_consistency(composed_fn, train_pairs):
            results.append(SynthesizedOperator(
                operator_id=f"adap_refined_{uuid.uuid4().hex[:8]}",
                operator_family=f"refined_{partial_op.operator_family}",
                parameters={
                    "base": partial_op.operator_family,
                    "correction": corr_op.operator_family,
                },
                preconditions=[],
                execute=composed_fn,
                explanation=f"Refine: {partial_op.explanation} then {corr_op.explanation}",
                source_failure_signature={},
            ))
    return results


# ---------------------------------------------------------------------------
# Depth-2 compositional search
# ---------------------------------------------------------------------------

def _try_depth2_compositions(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    single_ops: List[SynthesizedOperator],
    delta: TaskDelta,
    max_pairs: int = 20,
) -> List[SynthesizedOperator]:
    """Try composing pairs of single-step operators, pruned by delta hints."""
    if not single_ops:
        return []

    results = []
    ops_to_try = single_ops[:10]

    for i, op1 in enumerate(ops_to_try):
        for j, op2 in enumerate(ops_to_try):
            if i == j:
                continue
            if len(results) >= max_pairs:
                return results

            def make_composed(f1, f2):
                def fn(grid, _f1=f1, _f2=f2):
                    return _f2(_f1(grid))
                return fn
            composed = make_composed(op1.execute, op2.execute)
            if _check_train_consistency(composed, train_pairs):
                results.append(SynthesizedOperator(
                    operator_id=f"adap_d2_{uuid.uuid4().hex[:8]}",
                    operator_family=f"compose_{op1.operator_family}_{op2.operator_family}",
                    parameters={
                        "step1": op1.operator_family,
                        "step2": op2.operator_family,
                    },
                    preconditions=[],
                    execute=composed,
                    explanation=f"Compose: {op1.explanation} → {op2.explanation}",
                    source_failure_signature={},
                ))
    return results


def _try_inverse_decomposition(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    delta: TaskDelta,
) -> List[SynthesizedOperator]:
    """Top-down decomposition: identify outer operation, invert to get sub-problem."""
    results = []

    if delta.consistent_same_size is False:
        oh, ow = delta.pair_deltas[0].output_shape
        ih, iw = delta.pair_deltas[0].input_shape

        if oh < ih or ow < iw:
            for inp, out in train_pairs:
                for r in range(ih - oh + 1):
                    for c in range(iw - ow + 1):
                        subgrid = inp[r:r+oh, c:c+ow]
                        if subgrid.shape == out.shape:
                            inner_pairs = []
                            valid = True
                            for inp2, out2 in train_pairs:
                                oh2, ow2 = out2.shape
                                sg = inp2[r:r+oh2, c:c+ow2]
                                if sg.shape != out2.shape:
                                    valid = False
                                    break
                                inner_pairs.append((sg, out2))
                            if valid and inner_pairs:
                                inner_delta = compute_task_delta(inner_pairs)
                                inner_ops = _synthesize_single_step(inner_pairs, inner_delta)
                                for iop in inner_ops:
                                    def make_crop_then(crop_r, crop_c, crop_h, crop_w, inner_fn):
                                        def fn(grid, _r=crop_r, _c=crop_c, _h=crop_h, _w=crop_w, _fn=inner_fn):
                                            sg = grid[_r:_r+_h, _c:_c+_w]
                                            return _fn(sg)
                                        return fn
                                    composed = make_crop_then(r, c, oh, ow, iop.execute)
                                    if _check_train_consistency(composed, train_pairs):
                                        results.append(SynthesizedOperator(
                                            operator_id=f"adap_crop_inner_{uuid.uuid4().hex[:8]}",
                                            operator_family=f"crop_then_{iop.operator_family}",
                                            parameters={"crop_offset": (r, c), "inner": iop.operator_family},
                                            preconditions=[],
                                            execute=composed,
                                            explanation=f"Crop at ({r},{c}) then {iop.explanation}",
                                            source_failure_signature={},
                                        ))
                    if results:
                        return results

    return results


# ---------------------------------------------------------------------------
# Main synthesis entry point
# ---------------------------------------------------------------------------

def _synthesize_single_step(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    delta: TaskDelta,
) -> List[SynthesizedOperator]:
    """Try all single-step primitives guided by delta hints."""
    candidates = []

    hint_strategies = {h["strategy"] for h in delta.synthesis_hints}

    if "reflection" in hint_strategies or delta.consistent_reflection:
        candidates.extend(_try_reflection(train_pairs, delta))
    if "rotation" in hint_strategies or delta.consistent_rotation:
        candidates.extend(_try_rotation(train_pairs, delta))
    if "transpose" in hint_strategies:
        candidates.extend(_try_transpose(train_pairs, delta))
    if "color_map" in hint_strategies or delta.consistent_color_map:
        candidates.extend(_try_color_map(train_pairs, delta))

    if "crop" in hint_strategies or delta.consistent_same_size is False:
        candidates.extend(_try_crop_to_content(train_pairs, delta))
        candidates.extend(_try_crop_to_color(train_pairs, delta))
        candidates.extend(_try_identity_subgrid(train_pairs, delta))
        candidates.extend(_try_downscale(train_pairs, delta))
        candidates.extend(_try_upscale(train_pairs, delta))

    if "tile" in hint_strategies:
        candidates.extend(_try_tile(train_pairs, delta))

    if "move_objects" in hint_strategies or delta.consistent_translation:
        candidates.extend(_try_consistent_translation(train_pairs, delta))
        candidates.extend(_try_gravity(train_pairs, delta))

    if "recolor" in hint_strategies or "fill_regions" in hint_strategies:
        candidates.extend(_try_mask_by_color(train_pairs, delta))
        candidates.extend(_try_fill_changed_cells(train_pairs, delta))
        candidates.extend(_try_border_fill(train_pairs, delta))
        candidates.extend(_try_flood_fill_bg(train_pairs, delta))
        candidates.extend(_try_replace_bg_with_output_pattern(train_pairs, delta))
        candidates.extend(_try_remove_color(train_pairs, delta))
        candidates.extend(_try_output_equals_input_mask(train_pairs, delta))

    if "filter_objects" in hint_strategies:
        candidates.extend(_try_keep_largest_object(train_pairs, delta))

    candidates.extend(_try_sort_rows_cols(train_pairs, delta))
    candidates.extend(_try_diagonal_flip(train_pairs, delta))
    candidates.extend(_try_bitwise_ops(train_pairs, delta))

    if delta.consistent_same_size is False:
        candidates.extend(_try_count_colors(train_pairs, delta))
        candidates.extend(_try_max_color_per_row_col(train_pairs, delta))
        candidates.extend(_try_unique_color_per_row_col(train_pairs, delta))

    if not candidates:
        candidates.extend(_try_reflection(train_pairs, delta))
        candidates.extend(_try_rotation(train_pairs, delta))
        candidates.extend(_try_transpose(train_pairs, delta))
        candidates.extend(_try_color_map(train_pairs, delta))
        candidates.extend(_try_crop_to_content(train_pairs, delta))
        candidates.extend(_try_mask_by_color(train_pairs, delta))
        candidates.extend(_try_gravity(train_pairs, delta))
        candidates.extend(_try_downscale(train_pairs, delta))
        candidates.extend(_try_upscale(train_pairs, delta))
        candidates.extend(_try_flood_fill_bg(train_pairs, delta))
        candidates.extend(_try_keep_largest_object(train_pairs, delta))
        candidates.extend(_try_remove_color(train_pairs, delta))
        candidates.extend(_try_bitwise_ops(train_pairs, delta))
        candidates.extend(_try_count_colors(train_pairs, delta))
        candidates.extend(_try_diagonal_flip(train_pairs, delta))

    return candidates


def _generate_all_candidates_unfiltered(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    delta: TaskDelta,
) -> List[SynthesizedOperator]:
    """Generate ALL candidate operations, even imperfect ones.

    Unlike _synthesize_single_step which only returns train-consistent ops,
    this returns everything that produces valid output shapes, regardless of
    whether it matches perfectly. This feeds the partial-program search layer.
    """
    candidates = []

    all_try_fns = [
        _try_reflection, _try_rotation, _try_transpose, _try_color_map,
        _try_crop_to_content, _try_crop_to_color, _try_identity_subgrid,
        _try_downscale, _try_upscale, _try_tile,
        _try_consistent_translation, _try_gravity,
        _try_mask_by_color, _try_fill_changed_cells, _try_border_fill,
        _try_flood_fill_bg, _try_replace_bg_with_output_pattern,
        _try_remove_color, _try_output_equals_input_mask,
        _try_keep_largest_object, _try_sort_rows_cols,
        _try_diagonal_flip, _try_bitwise_ops,
        _try_count_colors, _try_max_color_per_row_col,
        _try_unique_color_per_row_col,
    ]

    for try_fn in all_try_fns:
        try:
            ops = try_fn(train_pairs, delta)
            candidates.extend(ops)
        except Exception:
            continue

    return candidates


def _generate_partial_candidates(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    delta: TaskDelta,
) -> List[Tuple[SynthesizedOperator, float, List[np.ndarray]]]:
    """Generate candidates that are NOT perfect but produce correct-shaped output.

    For each primitive, even if it doesn't pass full train consistency,
    apply it and score how close it gets. Returns (op, accuracy, predictions)
    sorted by accuracy descending.
    """
    scored = []

    all_simple_ops = _build_simple_op_library(train_pairs, delta)

    for op_fn, op_family, op_explanation, op_params in all_simple_ops:
        total_acc = 0.0
        preds = []
        valid = True
        for inp, out in train_pairs:
            try:
                pred = op_fn(inp)
                if pred is None or not isinstance(pred, np.ndarray):
                    valid = False
                    break
                sc = score_partial_correctness(pred, out)
                total_acc += sc["score"]
                preds.append(pred)
            except Exception:
                valid = False
                break
        if not valid or not preds:
            continue
        avg_acc = total_acc / len(train_pairs)
        if avg_acc >= 0.3:
            op = SynthesizedOperator(
                operator_id=f"partial_{uuid.uuid4().hex[:8]}",
                operator_family=op_family,
                parameters=op_params,
                preconditions=[],
                execute=op_fn,
                explanation=op_explanation,
                source_failure_signature={},
            )
            scored.append((op, avg_acc, preds))

    scored.sort(key=lambda x: -x[1])
    return scored


def _build_simple_op_library(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    delta: TaskDelta,
) -> List[Tuple[Callable, str, str, Dict]]:
    """Build a library of simple operations (not train-consistency filtered).

    Returns (callable, family_name, explanation, params) tuples.
    These are tried even when they don't perfectly match — the partial
    accuracy scorer decides if they're worth refining.
    """
    ops = []
    inp0, out0 = train_pairs[0]

    for axis_name, axis_fn in [
        ("vertical", lambda g: g[::-1, :].copy()),
        ("horizontal", lambda g: g[:, ::-1].copy()),
        ("both", lambda g: g[::-1, ::-1].copy()),
    ]:
        ops.append((axis_fn, "reflection", f"Reflect {axis_name}", {"axis": axis_name}))

    for angle in [90, 180, 270]:
        def make_rot(a):
            return lambda g, _a=a: np.rot90(g, k=_a // 90).copy()
        ops.append((make_rot(angle), "rotation", f"Rotate {angle}°", {"angle": angle}))

    ops.append((lambda g: g.T.copy(), "transpose", "Transpose", {}))

    if delta.consistent_color_map:
        cm = delta.consistent_color_map
        def make_cm(m):
            def fn(g, _m=m):
                o = g.copy()
                for s, d in _m.items():
                    o[g == s] = d
                return o
            return fn
        ops.append((make_cm(cm), "color_map", f"Color map: {cm}", {"mapping": cm}))

    for src in range(10):
        for dst in range(10):
            if src == dst:
                continue
            def make_rc(s, d):
                def fn(g, _s=s, _d=d):
                    o = g.copy()
                    o[g == _s] = _d
                    return o
                return fn
            ops.append((make_rc(src, dst), "single_recolor",
                       f"Recolor {src} → {dst}", {"src": src, "dst": dst}))

    for color in range(1, 10):
        def make_rm(c):
            def fn(g, _c=c):
                o = g.copy()
                o[g == _c] = 0
                return o
            return fn
        ops.append((make_rm(color), "remove_color",
                   f"Remove color {color}", {"color": color}))

    for direction in ["down", "up", "left", "right"]:
        def make_grav(d):
            def fn(grid, _d=d):
                H, W = grid.shape
                out = np.zeros_like(grid)
                if _d == "down":
                    for c in range(W):
                        col = [grid[r, c] for r in range(H) if grid[r, c] != 0]
                        for i, v in enumerate(col):
                            out[H - len(col) + i, c] = v
                elif _d == "up":
                    for c in range(W):
                        col = [grid[r, c] for r in range(H) if grid[r, c] != 0]
                        for i, v in enumerate(col):
                            out[i, c] = v
                elif _d == "right":
                    for r in range(H):
                        row = [grid[r, c] for c in range(W) if grid[r, c] != 0]
                        for i, v in enumerate(row):
                            out[r, W - len(row) + i] = v
                elif _d == "left":
                    for r in range(H):
                        row = [grid[r, c] for c in range(W) if grid[r, c] != 0]
                        for i, v in enumerate(row):
                            out[r, i] = v
                return out
            return fn
        ops.append((make_grav(direction), "gravity",
                   f"Gravity {direction}", {"direction": direction}))

    if inp0.shape == out0.shape:
        for fill_color in range(10):
            def make_fill_bg(fc):
                def fn(g, _fc=fc):
                    o = g.copy()
                    o[g == 0] = _fc
                    return o
                return fn
            ops.append((make_fill_bg(fill_color), "fill_bg",
                       f"Fill bg with {fill_color}", {"color": fill_color}))

    return ops


def _try_residual_correction_deep(
    partial_op: SynthesizedOperator,
    partial_preds: List[np.ndarray],
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    original_delta: TaskDelta,
) -> List[SynthesizedOperator]:
    """Deep residual correction: compute what's still wrong, synthesize a fix.

    This is the core of multi-step reasoning: if a candidate gets 70% right,
    the residual (predicted vs expected) is a simpler sub-problem that we can
    solve with another primitive.
    """
    correction_pairs = []
    for pred, (_, expected) in zip(partial_preds, train_pairs):
        if pred.shape != expected.shape:
            return []
        correction_pairs.append((pred, expected))

    residual_delta = compute_task_delta(correction_pairs)

    if residual_delta.consistency_score <= 0:
        return []

    correction_ops = _synthesize_single_step(correction_pairs, residual_delta)

    results = []
    for corr_op in correction_ops:
        def make_composed(base_fn, correction_fn):
            def fn(grid, _b=base_fn, _c=correction_fn):
                intermediate = _b(grid)
                return _c(intermediate)
            return fn
        composed_fn = make_composed(partial_op.execute, corr_op.execute)
        if _check_train_consistency(composed_fn, train_pairs):
            results.append(SynthesizedOperator(
                operator_id=f"adap_residual_{uuid.uuid4().hex[:8]}",
                operator_family=f"residual_{partial_op.operator_family}_then_{corr_op.operator_family}",
                parameters={
                    "base": partial_op.operator_family,
                    "correction": corr_op.operator_family,
                    "base_accuracy": None,
                },
                preconditions=[],
                execute=composed_fn,
                explanation=f"Partial: {partial_op.explanation} → Fix: {corr_op.explanation}",
                source_failure_signature={},
            ))
    return results


def _try_existing_solvers_as_inner(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs_proxy: List[np.ndarray],
) -> List[SynthesizedOperator]:
    """Try calling existing portfolio solvers and wrapping successful ones."""
    results = []
    solvers = []

    try:
        from reasoning_project.local_rules import solve_task_local_rules
        solvers.append(("local_rule", solve_task_local_rules))
    except ImportError:
        pass

    try:
        from reasoning_project.separator_decompose import solve_task_separator_decompose
        solvers.append(("separator_decompose", solve_task_separator_decompose))
    except ImportError:
        pass

    try:
        from reasoning_project.crop_extract import solve_task_crop_extract
        solvers.append(("crop_extract", solve_task_crop_extract))
    except ImportError:
        pass

    try:
        from reasoning_project.color_solver import solve_task_color
        solvers.append(("color_solver", solve_task_color))
    except ImportError:
        pass

    for solver_name, solver_fn in solvers:
        try:
            result = solver_fn(train_pairs, test_inputs_proxy)
            if result is None:
                continue
            preds, metadata = result[0], result[1] if len(result) > 1 else {}
            if not isinstance(preds, list):
                preds = [preds]

            all_train_match = True
            for inp, out in train_pairs:
                try:
                    p = solver_fn(train_pairs, [inp])
                    if p is None:
                        all_train_match = False
                        break
                    pred = p[0][0] if isinstance(p[0], list) else p[0]
                    if not isinstance(pred, np.ndarray):
                        all_train_match = False
                        break
                    if pred.shape != out.shape or not np.array_equal(pred, out):
                        all_train_match = False
                        break
                except Exception:
                    all_train_match = False
                    break

            if not all_train_match:
                continue

            def make_solver_fn(sf, tp):
                def fn(grid, _sf=sf, _tp=tp):
                    r = _sf(_tp, [grid])
                    if r is None:
                        return grid.copy()
                    p = r[0][0] if isinstance(r[0], list) else r[0]
                    return p
                return fn
            solver_exec = make_solver_fn(solver_fn, train_pairs)

            if _check_train_consistency(solver_exec, train_pairs):
                results.append(SynthesizedOperator(
                    operator_id=f"adap_solver_{solver_name}_{uuid.uuid4().hex[:8]}",
                    operator_family=f"solver_{solver_name}",
                    parameters={"solver": solver_name},
                    preconditions=[],
                    execute=solver_exec,
                    explanation=f"Existing solver: {solver_name}",
                    source_failure_signature={},
                ))
        except Exception:
            continue

    return results


def synthesize_adaptive(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    max_depth: int = 2,
    timeout_seconds: float = 60.0,
) -> List[SynthesizedOperator]:
    """Main entry point: delta-guided adaptive program synthesis.

    Flow:
    1. Compute delta (what changed between I/O pairs)
    2. Try single-step primitives (delta-guided)
    3. Generate partial candidates (don't require perfect match)
    4. For best partials, compute residual and search for correction
    5. Try inverse decomposition (outer op → sub-problem)
    6. Try depth-2 compositions of successful single-step ops
    7. Try existing portfolio solvers as composable inner programs
    """
    import time
    start = time.time()

    def _elapsed():
        return time.time() - start

    delta = compute_task_delta(train_pairs)
    all_candidates: List[SynthesizedOperator] = []

    # Step 1: Single-step primitives (fast, delta-guided)
    single_step = _synthesize_single_step(train_pairs, delta)
    all_candidates.extend(single_step)

    if _elapsed() > timeout_seconds:
        return _deduplicate(all_candidates)

    # Step 2: Inverse decomposition (crop-then-transform, etc.)
    if max_depth >= 2:
        decomposed = _try_inverse_decomposition(train_pairs, delta)
        all_candidates.extend(decomposed)

    if _elapsed() > timeout_seconds:
        return _deduplicate(all_candidates)

    # Step 3: Partial-program search — THE KEY MULTI-STEP REASONING LAYER
    # Generate all candidates (even imperfect), score by partial accuracy,
    # then search for corrections on the best partials.
    partial_candidates = _generate_partial_candidates(train_pairs, delta)

    for partial_op, acc, preds in partial_candidates[:5]:
        if acc >= 1.0 - 1e-9:
            continue
        if acc < 0.3:
            break
        corrections = _try_residual_correction_deep(
            partial_op, preds, train_pairs, delta
        )
        all_candidates.extend(corrections)

        if _elapsed() > timeout_seconds:
            return _deduplicate(all_candidates)

    # Step 4: Depth-2 compositions of single-step ops
    if max_depth >= 2 and single_step:
        d2_comps = _try_depth2_compositions(train_pairs, single_step, delta)
        all_candidates.extend(d2_comps)

    if _elapsed() > timeout_seconds:
        return _deduplicate(all_candidates)

    # Step 5: Try existing portfolio solvers
    if not all_candidates:
        test_proxy = [inp for inp, _ in train_pairs[:1]]
        solver_ops = _try_existing_solvers_as_inner(train_pairs, test_proxy)
        all_candidates.extend(solver_ops)

    return _deduplicate(all_candidates)


def _deduplicate(ops: List[SynthesizedOperator]) -> List[SynthesizedOperator]:
    seen_families = set()
    unique = []
    for op in ops:
        key = (op.operator_family, op.explanation)
        if key not in seen_families:
            seen_families.add(key)
            unique.append(op)
    return unique[:100]
