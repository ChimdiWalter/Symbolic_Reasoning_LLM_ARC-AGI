"""Different-Shape Reasoning Engine.

Handles ARC tasks where input and output grids have different dimensions.
Two sub-problems: (1) predict output shape, (2) generate output content.
Pure algorithmic reasoning — no ML.
"""
from __future__ import annotations

import time
import uuid
from collections import Counter, defaultdict
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import numpy as np
from scipy.ndimage import label as ndlabel

from reasoning_project.operator_genesis import SynthesizedOperator


# ===================================================================
# Helpers
# ===================================================================

def _verify_on_train(fn: Callable, train_pairs) -> bool:
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


def _make_op(family: str, fn: Callable, explanation: str) -> SynthesizedOperator:
    return SynthesizedOperator(
        operator_id=f"{family}_{uuid.uuid4().hex[:8]}",
        operator_family=family,
        parameters={},
        preconditions=[],
        execute=fn,
        explanation=explanation,
        source_failure_signature={},
    )


def _bg_color(grid: np.ndarray) -> int:
    counts = np.bincount(grid.flatten().astype(int), minlength=10)
    return int(np.argmax(counts))


def _find_separators(grid: np.ndarray) -> Tuple[List[int], List[int], Optional[int]]:
    """Find horizontal and vertical separator lines (full row/col of one color)."""
    h, w = grid.shape
    h_seps: List[int] = []
    v_seps: List[int] = []
    sep_color = None

    for r in range(h):
        vals = set(grid[r, :].tolist())
        if len(vals) == 1:
            c = vals.pop()
            if sep_color is None:
                sep_color = c
            if c == sep_color:
                h_seps.append(r)

    for c in range(w):
        vals = set(grid[:, c].tolist())
        if len(vals) == 1:
            v = vals.pop()
            if sep_color is None:
                sep_color = v
            if v == sep_color:
                v_seps.append(c)

    return h_seps, v_seps, sep_color


def _extract_regions(
    grid: np.ndarray,
    h_seps: List[int],
    v_seps: List[int],
) -> List[np.ndarray]:
    """Extract rectangular regions between separator lines."""
    h, w = grid.shape
    row_bounds = [0] + [s + 1 for s in h_seps] + [h] if h_seps else [0, h]
    col_bounds = [0] + [s + 1 for s in v_seps] + [w] if v_seps else [0, w]

    # Deduplicate bounds and ensure valid ranges
    row_bounds = sorted(set(b for b in row_bounds if 0 <= b <= h))
    col_bounds = sorted(set(b for b in col_bounds if 0 <= b <= w))

    regions = []
    for i in range(len(row_bounds) - 1):
        for j in range(len(col_bounds) - 1):
            r0, r1 = row_bounds[i], row_bounds[i + 1]
            c0, c1 = col_bounds[j], col_bounds[j + 1]
            if r1 > r0 and c1 > c0:
                # Skip if this region IS a separator
                sub = grid[r0:r1, c0:c1]
                if sub.size > 0:
                    regions.append(sub)
    return regions


# ===================================================================
# Phase 1: Shape Prediction
# ===================================================================

def _predict_shapes(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> List[Tuple[str, Callable[[np.ndarray], Tuple[int, int]]]]:
    """Return shape prediction strategies that are correct on ALL training pairs."""
    valid: List[Tuple[str, Callable]] = []

    out_shapes = [out.shape for _, out in train_pairs]
    inp_shapes = [inp.shape for inp, _ in train_pairs]

    # 1. Constant output shape
    if len(set(out_shapes)) == 1:
        oh, ow = out_shapes[0]
        valid.append(("constant", lambda g, _h=oh, _w=ow: (_h, _w)))

    # 2. Integer scale up
    for fh in range(1, 10):
        for fw in range(1, 10):
            if fh == 1 and fw == 1:
                continue
            if all(out.shape[0] == inp.shape[0] * fh and
                   out.shape[1] == inp.shape[1] * fw
                   for inp, out in train_pairs):
                valid.append((f"scale_{fh}x{fw}",
                              lambda g, _fh=fh, _fw=fw: (g.shape[0] * _fh, g.shape[1] * _fw)))

    # 3. Integer scale down
    for fh in range(2, 10):
        for fw in range(2, 10):
            if all(inp.shape[0] % fh == 0 and inp.shape[1] % fw == 0 and
                   out.shape[0] == inp.shape[0] // fh and
                   out.shape[1] == inp.shape[1] // fw
                   for inp, out in train_pairs):
                valid.append((f"downscale_{fh}x{fw}",
                              lambda g, _fh=fh, _fw=fw: (g.shape[0] // _fh, g.shape[1] // _fw)))

    # 4. Transpose
    if all(out.shape == (inp.shape[1], inp.shape[0]) for inp, out in train_pairs):
        valid.append(("transpose", lambda g: (g.shape[1], g.shape[0])))

    # 5. Crop to non-bg content bbox
    def _content_shape(g):
        bg = _bg_color(g)
        nz = np.argwhere(g != bg)
        if len(nz) == 0:
            return g.shape
        r0, c0 = nz.min(axis=0)
        r1, c1 = nz.max(axis=0)
        return (r1 - r0 + 1, c1 - c0 + 1)

    if all(_content_shape(inp) == out.shape for inp, out in train_pairs):
        valid.append(("crop_content", _content_shape))

    # 6. Crop to specific color bbox
    for color in range(10):
        def _color_shape(g, _c=color):
            mask = g == _c
            if not mask.any():
                return (-1, -1)
            rows, cols = np.where(mask)
            return (rows.max() - rows.min() + 1, cols.max() - cols.min() + 1)

        if all(_color_shape(inp) == out.shape for inp, out in train_pairs):
            valid.append((f"crop_color_{color}", _color_shape))

    # 7. Object count determines size
    for dim_formula in ("n_objects", "n_colors"):
        def _count_shape(g, _f=dim_formula):
            bg = _bg_color(g)
            if _f == "n_objects":
                labeled, n = ndlabel(g != bg)
                return n
            else:
                return len(set(g.flatten().tolist()) - {bg})

        # Output is NxN where N = count
        counts = [_count_shape(inp) for inp, _ in train_pairs]
        if all(c > 0 and out.shape == (c, c) for c, (_, out) in zip(counts, train_pairs)):
            valid.append((f"square_{dim_formula}",
                          lambda g, _f=dim_formula: (
                              _count_shape(g, _f), _count_shape(g, _f))))

        # Output is Nx1 or 1xN
        if all(c > 0 and out.shape == (c, 1) for c, (_, out) in zip(counts, train_pairs)):
            valid.append((f"col_{dim_formula}",
                          lambda g, _f=dim_formula: (_count_shape(g, _f), 1)))
        if all(c > 0 and out.shape == (1, c) for c, (_, out) in zip(counts, train_pairs)):
            valid.append((f"row_{dim_formula}",
                          lambda g, _f=dim_formula: (1, _count_shape(g, _f))))

    # 8. Formula-based: output = f(input_h, input_w)
    for name, fn in [
        ("max", lambda h, w: (max(h, w), max(h, w))),
        ("min", lambda h, w: (min(h, w), min(h, w))),
        ("h_only", lambda h, w: (h, h)),
        ("w_only", lambda h, w: (w, w)),
        ("diff", lambda h, w: (abs(h - w), abs(h - w))),
        ("sum_sq", lambda h, w: (h, w)),  # identity, skip
    ]:
        if name == "sum_sq":
            continue
        pred_shapes = [fn(inp.shape[0], inp.shape[1]) for inp, _ in train_pairs]
        if all(ps == out.shape for ps, (_, out) in zip(pred_shapes, train_pairs)):
            valid.append((f"formula_{name}",
                          lambda g, _fn=fn: _fn(g.shape[0], g.shape[1])))

    # 9. Separator-based: output = one region between separators
    region_shapes = []
    for inp, out in train_pairs:
        h_seps, v_seps, sep_c = _find_separators(inp)
        if h_seps or v_seps:
            regions = _extract_regions(inp, h_seps, v_seps)
            region_shapes.append([(r.shape, r) for r in regions])
        else:
            region_shapes.append([])

    if region_shapes and all(len(rs) > 0 for rs in region_shapes):
        # Check if all outputs match a region shape at the same index
        for idx in range(max(len(rs) for rs in region_shapes)):
            if all(idx < len(rs) and rs[idx][0] == out.shape
                   for rs, (_, out) in zip(region_shapes, train_pairs)):
                valid.append((f"separator_region_{idx}",
                              lambda g, _idx=idx: _extract_regions(
                                  g, *_find_separators(g)[:2])[_idx].shape
                              if _idx < len(_extract_regions(g, *_find_separators(g)[:2]))
                              else g.shape))

    # 10. Padding/trimming
    for pad_r in range(-5, 6):
        for pad_c in range(-5, 6):
            if pad_r == 0 and pad_c == 0:
                continue
            if all(out.shape[0] == inp.shape[0] + pad_r and
                   out.shape[1] == inp.shape[1] + pad_c and
                   out.shape[0] > 0 and out.shape[1] > 0
                   for inp, out in train_pairs):
                valid.append((f"pad_{pad_r}_{pad_c}",
                              lambda g, _pr=pad_r, _pc=pad_c: (
                                  g.shape[0] + _pr, g.shape[1] + _pc)))

    # 11. Output shape = largest object bbox
    def _largest_obj_shape(g):
        bg = _bg_color(g)
        labeled, n = ndlabel(g != bg)
        best_size = 0
        best_shape = g.shape
        for i in range(1, n + 1):
            mask = labeled == i
            rows, cols = np.where(mask)
            h = rows.max() - rows.min() + 1
            w = cols.max() - cols.min() + 1
            if h * w > best_size:
                best_size = h * w
                best_shape = (h, w)
        return best_shape

    if all(_largest_obj_shape(inp) == out.shape for inp, out in train_pairs):
        valid.append(("largest_obj_bbox", _largest_obj_shape))

    # 12. Output shape = smallest object bbox
    def _smallest_obj_shape(g):
        bg = _bg_color(g)
        labeled, n = ndlabel(g != bg)
        best_size = float('inf')
        best_shape = g.shape
        for i in range(1, n + 1):
            mask = labeled == i
            rows, cols = np.where(mask)
            h = rows.max() - rows.min() + 1
            w = cols.max() - cols.min() + 1
            if h * w < best_size:
                best_size = h * w
                best_shape = (h, w)
        return best_shape

    if all(_smallest_obj_shape(inp) == out.shape for inp, out in train_pairs):
        valid.append(("smallest_obj_bbox", _smallest_obj_shape))

    # 13. Non-uniform factoring of rows/cols
    # output_h = number of unique row patterns, output_w = input_w (or vice versa)
    def _unique_rows_shape(g):
        unique = len(set(tuple(g[r, :].tolist()) for r in range(g.shape[0])))
        return (unique, g.shape[1])

    if all(_unique_rows_shape(inp) == out.shape for inp, out in train_pairs):
        valid.append(("unique_rows", _unique_rows_shape))

    def _unique_cols_shape(g):
        unique = len(set(tuple(g[:, c].tolist()) for c in range(g.shape[1])))
        return (g.shape[0], unique)

    if all(_unique_cols_shape(inp) == out.shape for inp, out in train_pairs):
        valid.append(("unique_cols", _unique_cols_shape))

    return valid


# ===================================================================
# Phase 2: Content Generation
# ===================================================================

def _crop_content(grid: np.ndarray) -> np.ndarray:
    bg = _bg_color(grid)
    nz = np.argwhere(grid != bg)
    if len(nz) == 0:
        return grid.copy()
    r0, c0 = nz.min(axis=0)
    r1, c1 = nz.max(axis=0)
    return grid[r0:r1 + 1, c0:c1 + 1].copy()


def _crop_color(grid: np.ndarray, color: int) -> np.ndarray:
    mask = grid == color
    if not mask.any():
        return grid.copy()
    rows, cols = np.where(mask)
    r0, c0 = rows.min(), cols.min()
    r1, c1 = rows.max(), cols.max()
    return grid[r0:r1 + 1, c0:c1 + 1].copy()


def _crop_largest_object(grid: np.ndarray) -> np.ndarray:
    bg = _bg_color(grid)
    labeled, n = ndlabel(grid != bg)
    best_mask = None
    best_size = 0
    for i in range(1, n + 1):
        mask = labeled == i
        s = int(mask.sum())
        if s > best_size:
            best_size = s
            best_mask = mask
    if best_mask is None:
        return grid.copy()
    rows, cols = np.where(best_mask)
    r0, c0 = rows.min(), cols.min()
    r1, c1 = rows.max(), cols.max()
    return grid[r0:r1 + 1, c0:c1 + 1].copy()


def _crop_smallest_object(grid: np.ndarray) -> np.ndarray:
    bg = _bg_color(grid)
    labeled, n = ndlabel(grid != bg)
    best_mask = None
    best_size = float('inf')
    for i in range(1, n + 1):
        mask = labeled == i
        s = int(mask.sum())
        if 0 < s < best_size:
            best_size = s
            best_mask = mask
    if best_mask is None:
        return grid.copy()
    rows, cols = np.where(best_mask)
    r0, c0 = rows.min(), cols.min()
    r1, c1 = rows.max(), cols.max()
    return grid[r0:r1 + 1, c0:c1 + 1].copy()


def _tile(grid: np.ndarray, fh: int, fw: int) -> np.ndarray:
    return np.tile(grid, (fh, fw))


def _tile_with_flip(grid: np.ndarray, fh: int, fw: int) -> np.ndarray:
    """Tile with alternating flips (kaleidoscope)."""
    rows = []
    for r in range(fh):
        row_blocks = []
        for c in range(fw):
            block = grid.copy()
            if r % 2 == 1:
                block = block[::-1, :]
            if c % 2 == 1:
                block = block[:, ::-1]
            row_blocks.append(block)
        rows.append(np.concatenate(row_blocks, axis=1))
    return np.concatenate(rows, axis=0)


def _block_scale(grid: np.ndarray, fh: int, fw: int) -> np.ndarray:
    """Each pixel becomes a fh×fw block."""
    h, w = grid.shape
    out = np.zeros((h * fh, w * fw), dtype=grid.dtype)
    for r in range(h):
        for c in range(w):
            out[r * fh:(r + 1) * fh, c * fw:(c + 1) * fw] = grid[r, c]
    return out


def _block_downscale(grid: np.ndarray, fh: int, fw: int) -> np.ndarray:
    """Take majority color from each fh×fw block."""
    h, w = grid.shape
    oh, ow = h // fh, w // fw
    out = np.zeros((oh, ow), dtype=grid.dtype)
    for r in range(oh):
        for c in range(ow):
            block = grid[r * fh:(r + 1) * fh, c * fw:(c + 1) * fw]
            counts = np.bincount(block.flatten().astype(int), minlength=10)
            out[r, c] = int(np.argmax(counts))
    return out


def _block_downscale_minority(grid: np.ndarray, fh: int, fw: int, bg: int) -> np.ndarray:
    """Take non-bg color from each block if present, else bg."""
    h, w = grid.shape
    oh, ow = h // fh, w // fw
    out = np.full((oh, ow), bg, dtype=grid.dtype)
    for r in range(oh):
        for c in range(ow):
            block = grid[r * fh:(r + 1) * fh, c * fw:(c + 1) * fw]
            non_bg = block[block != bg]
            if len(non_bg) > 0:
                counts = np.bincount(non_bg.astype(int), minlength=10)
                out[r, c] = int(np.argmax(counts))
    return out


def _separator_overlay(regions: List[np.ndarray], op: str = "or") -> np.ndarray:
    """Combine regions with an operation."""
    if not regions:
        return np.array([[0]])
    target_shape = regions[0].shape
    result = np.zeros(target_shape, dtype=int)
    bg = 0

    compatible = [r for r in regions if r.shape == target_shape]
    if not compatible:
        return regions[0].copy()

    if op == "or":
        for r in compatible:
            mask = r != bg
            result[mask] = r[mask]
    elif op == "and":
        result = compatible[0].copy()
        for r in compatible[1:]:
            mask = r == bg
            result[mask] = bg
    elif op == "xor":
        for r in compatible:
            mask = r != bg
            xor_mask = mask & (result == bg)
            cancel_mask = mask & (result != bg) & (result == r)
            result[xor_mask] = r[xor_mask]
            result[cancel_mask] = bg
    elif op == "majority":
        stack = np.stack(compatible, axis=0)
        for i in range(target_shape[0]):
            for j in range(target_shape[1]):
                vals = stack[:, i, j]
                non_bg = vals[vals != bg]
                if len(non_bg) > 0:
                    counts = np.bincount(non_bg.astype(int), minlength=10)
                    result[i, j] = int(np.argmax(counts))
    return result


def _unique_rows_content(grid: np.ndarray) -> np.ndarray:
    """Keep only unique rows, in order."""
    seen = set()
    rows = []
    for r in range(grid.shape[0]):
        key = tuple(grid[r, :].tolist())
        if key not in seen:
            seen.add(key)
            rows.append(grid[r, :])
    if not rows:
        return grid.copy()
    return np.stack(rows, axis=0)


def _unique_cols_content(grid: np.ndarray) -> np.ndarray:
    """Keep only unique columns, in order."""
    seen = set()
    cols = []
    for c in range(grid.shape[1]):
        key = tuple(grid[:, c].tolist())
        if key not in seen:
            seen.add(key)
            cols.append(grid[:, c])
    if not cols:
        return grid.copy()
    return np.stack(cols, axis=1)


def _color_histogram(grid: np.ndarray, bg: int) -> np.ndarray:
    """Build a color histogram as a column vector."""
    counts = np.bincount(grid.flatten().astype(int), minlength=10)
    non_bg = [(c, cnt) for c, cnt in enumerate(counts) if c != bg and cnt > 0]
    if not non_bg:
        return np.array([[bg]])
    non_bg.sort(key=lambda x: -x[1])
    result = np.array([[c] for c, _ in non_bg], dtype=int)
    return result


def _object_inventory(grid: np.ndarray, target_shape: Tuple[int, int]) -> np.ndarray:
    """Build an inventory grid of objects sorted by property."""
    bg = _bg_color(grid)
    labeled, n = ndlabel(grid != bg)
    oh, ow = target_shape

    obj_info = []
    for i in range(1, n + 1):
        mask = labeled == i
        rows, cols = np.where(mask)
        colors = grid[mask]
        dominant = int(np.argmax(np.bincount(colors.astype(int), minlength=10)))
        area = int(mask.sum())
        obj_info.append((dominant, area, i))

    obj_info.sort(key=lambda x: (-x[1], x[0]))

    result = np.full(target_shape, bg, dtype=int)
    for idx, (color, area, _) in enumerate(obj_info):
        if idx < oh * ow:
            r, c = divmod(idx, ow)
            if r < oh and c < ow:
                result[r, c] = color
    return result


# ===================================================================
# Phase 3: Compositional Shape+Content Search
# ===================================================================

def _try_all_content_strategies(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    shape_strategy: str,
    shape_fn: Callable,
    deadline: float,
) -> List[SynthesizedOperator]:
    """Given a valid shape prediction, try all content-generation strategies."""
    results: List[SynthesizedOperator] = []
    if time.time() > deadline:
        return results

    # Strategy 1: Crop to non-bg content
    def s_crop_content(g):
        return _crop_content(g)

    if _verify_on_train(s_crop_content, train_pairs):
        results.append(_make_op("shape_crop", s_crop_content,
                                f"Crop to content (shape: {shape_strategy})"))

    if time.time() > deadline:
        return results

    # Strategy 2: Crop to specific color bbox
    for color in range(10):
        def s_crop_color(g, _c=color):
            return _crop_color(g, _c)

        if _verify_on_train(s_crop_color, train_pairs):
            results.append(_make_op("shape_crop", s_crop_color,
                                    f"Crop to color {color} bbox"))

    if time.time() > deadline:
        return results

    # Strategy 3: Crop to largest/smallest object
    if _verify_on_train(_crop_largest_object, train_pairs):
        results.append(_make_op("shape_crop", _crop_largest_object,
                                "Crop to largest object"))

    if _verify_on_train(_crop_smallest_object, train_pairs):
        results.append(_make_op("shape_crop", _crop_smallest_object,
                                "Crop to smallest object"))

    if time.time() > deadline:
        return results

    # Strategy 4: Block scale up
    for fh in range(2, 6):
        for fw in range(2, 6):
            oh = train_pairs[0][0].shape[0] * fh
            ow = train_pairs[0][0].shape[1] * fw
            if (oh, ow) != train_pairs[0][1].shape:
                continue

            def s_block(g, _fh=fh, _fw=fw):
                return _block_scale(g, _fh, _fw)

            if _verify_on_train(s_block, train_pairs):
                results.append(_make_op("shape_scale", s_block,
                                        f"Block scale {fh}x{fw}"))

    if time.time() > deadline:
        return results

    # Strategy 5: Block downscale (majority and minority)
    for fh in range(2, 6):
        for fw in range(2, 6):
            if not all(inp.shape[0] % fh == 0 and inp.shape[1] % fw == 0
                       for inp, _ in train_pairs):
                continue

            def s_down_maj(g, _fh=fh, _fw=fw):
                return _block_downscale(g, _fh, _fw)

            if _verify_on_train(s_down_maj, train_pairs):
                results.append(_make_op("shape_scale", s_down_maj,
                                        f"Downscale {fh}x{fw} (majority)"))

            def s_down_min(g, _fh=fh, _fw=fw):
                bg = _bg_color(g)
                return _block_downscale_minority(g, _fh, _fw, bg)

            if _verify_on_train(s_down_min, train_pairs):
                results.append(_make_op("shape_scale", s_down_min,
                                        f"Downscale {fh}x{fw} (minority non-bg)"))

    if time.time() > deadline:
        return results

    # Strategy 6: Tile
    for fh in range(2, 6):
        for fw in range(2, 6):
            oh = train_pairs[0][0].shape[0] * fh
            ow = train_pairs[0][0].shape[1] * fw
            if (oh, ow) != train_pairs[0][1].shape:
                continue

            def s_tile(g, _fh=fh, _fw=fw):
                return _tile(g, _fh, _fw)

            if _verify_on_train(s_tile, train_pairs):
                results.append(_make_op("shape_tile", s_tile,
                                        f"Tile {fh}x{fw}"))

            def s_tile_flip(g, _fh=fh, _fw=fw):
                return _tile_with_flip(g, _fh, _fw)

            if _verify_on_train(s_tile_flip, train_pairs):
                results.append(_make_op("shape_tile", s_tile_flip,
                                        f"Tile {fh}x{fw} with flip"))

    if time.time() > deadline:
        return results

    # Strategy 7: Separator decomposition — output = one region
    for inp, _ in train_pairs[:1]:
        h_seps, v_seps, sep_c = _find_separators(inp)
        if not h_seps and not v_seps:
            break

        regions = _extract_regions(inp, h_seps, v_seps)
        if not regions:
            break

        # Try returning specific region
        for idx in range(min(len(regions), 10)):
            def s_region(g, _idx=idx):
                hs, vs, _ = _find_separators(g)
                regs = _extract_regions(g, hs, vs)
                if _idx < len(regs):
                    return regs[_idx]
                return g.copy()

            if _verify_on_train(s_region, train_pairs):
                results.append(_make_op("shape_separator", s_region,
                                        f"Extract separator region {idx}"))

    if time.time() > deadline:
        return results

    # Strategy 8: Separator overlay operations
    for inp, _ in train_pairs[:1]:
        h_seps, v_seps, sep_c = _find_separators(inp)
        if not h_seps and not v_seps:
            break

        regions = _extract_regions(inp, h_seps, v_seps)
        if len(regions) < 2:
            break

        for op_name in ("or", "and", "xor", "majority"):
            def s_overlay(g, _op=op_name):
                hs, vs, _ = _find_separators(g)
                regs = _extract_regions(g, hs, vs)
                if len(regs) < 2:
                    return g.copy()
                return _separator_overlay(regs, _op)

            if _verify_on_train(s_overlay, train_pairs):
                results.append(_make_op("shape_separator", s_overlay,
                                        f"Separator overlay ({op_name})"))

    if time.time() > deadline:
        return results

    # Strategy 9: Unique rows / unique cols
    if _verify_on_train(_unique_rows_content, train_pairs):
        results.append(_make_op("shape_construct", _unique_rows_content,
                                "Keep unique rows"))

    if _verify_on_train(_unique_cols_content, train_pairs):
        results.append(_make_op("shape_construct", _unique_cols_content,
                                "Keep unique columns"))

    if time.time() > deadline:
        return results

    # Strategy 10: Transpose
    def s_transpose(g):
        return g.T.copy()

    if _verify_on_train(s_transpose, train_pairs):
        results.append(_make_op("shape_rearrange", s_transpose,
                                "Transpose grid"))

    if time.time() > deadline:
        return results

    # Strategy 11: Color inventory / histogram
    def s_histogram(g):
        bg = _bg_color(g)
        return _color_histogram(g, bg)

    if _verify_on_train(s_histogram, train_pairs):
        results.append(_make_op("shape_construct", s_histogram,
                                "Color histogram"))

    if time.time() > deadline:
        return results

    # Strategy 12: Object inventory
    target_shape = train_pairs[0][1].shape

    def s_inventory(g, _ts=target_shape):
        return _object_inventory(g, _ts)

    if len(set(out.shape for _, out in train_pairs)) == 1:
        if _verify_on_train(s_inventory, train_pairs):
            results.append(_make_op("shape_construct", s_inventory,
                                    "Object inventory grid"))

    if time.time() > deadline:
        return results

    # Strategy 13: Padding with bg color
    for pad_r in range(-3, 4):
        for pad_c in range(-3, 4):
            if pad_r == 0 and pad_c == 0:
                continue

            def s_pad(g, _pr=pad_r, _pc=pad_c):
                bg = _bg_color(g)
                h, w = g.shape
                nh, nw = h + _pr, w + _pc
                if nh <= 0 or nw <= 0:
                    return g.copy()
                if _pr >= 0 and _pc >= 0:
                    out = np.full((nh, nw), bg, dtype=g.dtype)
                    out[:h, :w] = g
                elif _pr < 0 and _pc < 0:
                    return g[:nh, :nw].copy()
                elif _pr >= 0:
                    out = np.full((nh, nw), bg, dtype=g.dtype)
                    out[:h, :nw] = g[:, :nw]
                else:
                    out = np.full((nh, nw), bg, dtype=g.dtype)
                    out[:nh, :w] = g[:nh, :]
                return out

            if _verify_on_train(s_pad, train_pairs):
                results.append(_make_op("shape_construct", s_pad,
                                        f"Pad/trim ({pad_r},{pad_c})"))

    if time.time() > deadline:
        return results

    # Strategy 14: Extract inside of a border/frame
    def s_remove_border(g):
        if g.shape[0] < 3 or g.shape[1] < 3:
            return g.copy()
        return g[1:-1, 1:-1].copy()

    if _verify_on_train(s_remove_border, train_pairs):
        results.append(_make_op("shape_crop", s_remove_border,
                                "Remove 1-pixel border"))

    for n in range(2, 4):
        def s_remove_n(g, _n=n):
            if g.shape[0] < 2 * _n + 1 or g.shape[1] < 2 * _n + 1:
                return g.copy()
            return g[_n:-_n, _n:-_n].copy()

        if _verify_on_train(s_remove_n, train_pairs):
            results.append(_make_op("shape_crop", s_remove_n,
                                    f"Remove {n}-pixel border"))

    if time.time() > deadline:
        return results

    # Strategy 15: Rotate 90/180/270
    for rot in (1, 2, 3):
        def s_rot(g, _r=rot):
            return np.rot90(g, _r).copy()

        if _verify_on_train(s_rot, train_pairs):
            results.append(_make_op("shape_rearrange", s_rot,
                                    f"Rotate {rot * 90} degrees"))

    # Strategy 16: Flip then crop
    for flip_axis in (0, 1):
        def s_flip_crop(g, _ax=flip_axis):
            flipped = np.flip(g, axis=_ax).copy()
            return _crop_content(flipped)

        if _verify_on_train(s_flip_crop, train_pairs):
            results.append(_make_op("shape_rearrange", s_flip_crop,
                                    f"Flip axis={flip_axis} then crop"))

    if time.time() > deadline:
        return results

    # Strategy 17: Stack subregions of specific color bboxes
    # Find two non-bg colors and stack their bboxes
    for c1 in range(10):
        for c2 in range(c1 + 1, 10):
            for stack_dir in ("v", "h"):
                def s_stack(g, _c1=c1, _c2=c2, _sd=stack_dir):
                    m1 = g == _c1
                    m2 = g == _c2
                    if not m1.any() or not m2.any():
                        return g.copy()
                    r1 = np.where(m1)
                    r2 = np.where(m2)
                    s1 = g[r1[0].min():r1[0].max() + 1, r1[1].min():r1[1].max() + 1]
                    s2 = g[r2[0].min():r2[0].max() + 1, r2[1].min():r2[1].max() + 1]
                    try:
                        if _sd == "v":
                            return np.concatenate([s1, s2], axis=0)
                        else:
                            return np.concatenate([s1, s2], axis=1)
                    except ValueError:
                        return g.copy()

                if _verify_on_train(s_stack, train_pairs):
                    results.append(_make_op("shape_rearrange", s_stack,
                                            f"Stack color {c1}+{c2} bboxes ({stack_dir})"))

            if time.time() > deadline:
                return results

    # Strategy 18: Row/column summary — one output row per unique value in a column
    def s_row_summary(g):
        bg = _bg_color(g)
        summary_rows = []
        for c in range(g.shape[1]):
            col = g[:, c]
            non_bg = [v for v in col if v != bg]
            if non_bg:
                summary_rows.append(non_bg[0])
            else:
                summary_rows.append(bg)
        return np.array([summary_rows], dtype=int)

    if _verify_on_train(s_row_summary, train_pairs):
        results.append(_make_op("shape_construct", s_row_summary,
                                "Column-wise summary row"))

    def s_col_summary(g):
        bg = _bg_color(g)
        summary_cols = []
        for r in range(g.shape[0]):
            row = g[r, :]
            non_bg = [v for v in row if v != bg]
            if non_bg:
                summary_cols.append(non_bg[0])
            else:
                summary_cols.append(bg)
        return np.array([[v] for v in summary_cols], dtype=int)

    if _verify_on_train(s_col_summary, train_pairs):
        results.append(_make_op("shape_construct", s_col_summary,
                                "Row-wise summary column"))

    return results


# ===================================================================
# Main Entry Point
# ===================================================================

def reason_different_shape(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    timeout_seconds: float = 10.0,
    task_id: str = "",
) -> List[SynthesizedOperator]:
    """Reason about tasks where input and output have different shapes."""
    deadline = time.time() + timeout_seconds
    results: List[SynthesizedOperator] = []

    # Only apply to different-shape tasks
    same_shape = all(inp.shape == out.shape for inp, out in train_pairs)
    if same_shape:
        return results

    try:
        # Get valid shape predictions
        shape_strategies = _predict_shapes(train_pairs)

        if not shape_strategies:
            # Even if we can't predict shape, try direct content strategies
            shape_strategies = [("unknown", lambda g: g.shape)]

        # For each valid shape, try content strategies
        seen_explanations: Set[str] = set()
        for shape_name, shape_fn in shape_strategies:
            if time.time() > deadline:
                break

            remaining = deadline - time.time()
            ops = _try_all_content_strategies(
                train_pairs, shape_name, shape_fn,
                time.time() + min(remaining * 0.5, remaining / max(len(shape_strategies), 1)),
            )
            for op in ops:
                if op.explanation not in seen_explanations:
                    seen_explanations.add(op.explanation)
                    results.append(op)

    except Exception:
        pass

    return results
