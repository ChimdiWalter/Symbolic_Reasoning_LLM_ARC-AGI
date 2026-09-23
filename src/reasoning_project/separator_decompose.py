"""Separator-based decomposition solver for ARC tasks.

Handles grids divided by separator lines (full rows/columns of a single color)
into regions that are then combined, compared, or selectively extracted.
"""
from __future__ import annotations

import numpy as np
from typing import Optional, List, Tuple, Dict, Any
from itertools import product


def _find_separator_rows(grid: np.ndarray) -> List[Tuple[int, int]]:
    """Find rows that are entirely one color. Returns [(row_idx, color), ...]."""
    seps = []
    for r in range(grid.shape[0]):
        vals = set(grid[r, :].tolist())
        if len(vals) == 1:
            seps.append((r, vals.pop()))
    return seps


def _find_separator_cols(grid: np.ndarray) -> List[Tuple[int, int]]:
    """Find columns that are entirely one color. Returns [(col_idx, color), ...]."""
    seps = []
    for c in range(grid.shape[1]):
        vals = set(grid[:, c].tolist())
        if len(vals) == 1:
            seps.append((c, vals.pop()))
    return seps


def _split_by_single_separator(
    grid: np.ndarray,
) -> Optional[Tuple[np.ndarray, np.ndarray, str, int]]:
    """Split grid into exactly two halves by a single separator row or column.

    Returns (half_a, half_b, direction, sep_color) or None.
    """
    row_seps = _find_separator_rows(grid)
    for r, color in row_seps:
        above = grid[:r, :]
        below = grid[r + 1:, :]
        if above.size > 0 and below.size > 0 and above.shape == below.shape:
            return above, below, "row", color

    col_seps = _find_separator_cols(grid)
    for c, color in col_seps:
        left = grid[:, :c]
        right = grid[:, c + 1:]
        if left.size > 0 and right.size > 0 and left.shape == right.shape:
            return left, right, "col", color

    return None


def _binarize(half: np.ndarray) -> np.ndarray:
    """Convert a grid to binary (nonzero → 1)."""
    return (half != 0).astype(int)


def _try_binary_combine(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
) -> Optional[Tuple[List[np.ndarray], Dict[str, Any]]]:
    """Split by separator and combine two halves via binary operation.

    Tries AND, OR, XOR, NOR, NAND, A_AND_NOT_B, B_AND_NOT_A on binarized halves,
    with learned output color mapping.
    """
    ops = {
        "and": lambda a, b: a & b,
        "or": lambda a, b: a | b,
        "xor": lambda a, b: a ^ b,
        "nor": lambda a, b: ~a & ~b,
        "nand": lambda a, b: ~(a & b),
        "a_not_b": lambda a, b: a & ~b,
        "b_not_a": lambda a, b: b & ~a,
    }

    split0 = _split_by_single_separator(train_pairs[0][0])
    if split0 is None:
        return None

    _, _, direction0, sep_color0 = split0

    for op_name, op_fn in ops.items():
        ok = True
        out_color_learned = None

        for inp, out in train_pairs:
            split = _split_by_single_separator(inp)
            if split is None:
                ok = False
                break
            half_a, half_b, direction, sep_color = split
            if direction != direction0 or sep_color != sep_color0:
                ok = False
                break

            bin_a = _binarize(half_a)
            bin_b = _binarize(half_b)
            result_mask = op_fn(bin_a, bin_b) & 1

            if out.shape != half_a.shape:
                ok = False
                break

            out_nonzero = set(out[out != 0].flatten().tolist())
            if len(out_nonzero) > 1:
                ok = False
                break
            out_color = out_nonzero.pop() if out_nonzero else 0

            if out_color_learned is None:
                out_color_learned = out_color
            elif out_color != out_color_learned:
                ok = False
                break

            expected = np.where(result_mask, out_color_learned, 0)
            if not np.array_equal(expected, out):
                ok = False
                break

        if not ok or out_color_learned is None:
            continue

        predictions = []
        for ti in test_inputs:
            split = _split_by_single_separator(ti)
            if split is None:
                return None
            half_a, half_b, direction, sep_color = split
            bin_a = _binarize(half_a)
            bin_b = _binarize(half_b)
            result_mask = op_fn(bin_a, bin_b) & 1
            pred = np.where(result_mask, out_color_learned, 0)
            predictions.append(pred)

        return predictions, {
            "strategy": "binary_combine",
            "op": op_name,
            "direction": direction0,
            "sep_color": sep_color0,
            "out_color": out_color_learned,
        }

    return None


def _try_binary_combine_preserve_colors(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
) -> Optional[Tuple[List[np.ndarray], Dict[str, Any]]]:
    """Like binary_combine but output preserves colors from one half (or both).

    Handles cases where the output isn't a single new color but retains the
    original pixel colors from half_a, half_b, or a merge of both.
    """
    split0 = _split_by_single_separator(train_pairs[0][0])
    if split0 is None:
        return None
    _, _, direction0, sep_color0 = split0

    sources = {
        "a_where_both": lambda a, b: np.where((a != 0) & (b != 0), a, 0),
        "b_where_both": lambda a, b: np.where((a != 0) & (b != 0), b, 0),
        "a_where_a_only": lambda a, b: np.where((a != 0) & (b == 0), a, 0),
        "b_where_b_only": lambda a, b: np.where((b != 0) & (a == 0), b, 0),
        "overlay_a_on_b": lambda a, b: np.where(a != 0, a, b),
        "overlay_b_on_a": lambda a, b: np.where(b != 0, b, a),
        "a_where_either": lambda a, b: np.where((a != 0) | (b != 0), np.where(a != 0, a, b), 0),
        "max_ab": lambda a, b: np.maximum(a, b),
    }

    for src_name, src_fn in sources.items():
        ok = True
        for inp, out in train_pairs:
            split = _split_by_single_separator(inp)
            if split is None:
                ok = False
                break
            half_a, half_b, direction, sep_color = split
            if direction != direction0 or sep_color != sep_color0:
                ok = False
                break
            if out.shape != half_a.shape:
                ok = False
                break
            expected = src_fn(half_a, half_b)
            if not np.array_equal(expected, out):
                ok = False
                break

        if not ok:
            continue

        predictions = []
        for ti in test_inputs:
            split = _split_by_single_separator(ti)
            if split is None:
                return None
            half_a, half_b, _, _ = split
            predictions.append(src_fn(half_a, half_b))

        return predictions, {
            "strategy": "binary_combine_preserve",
            "source": src_name,
            "direction": direction0,
            "sep_color": sep_color0,
        }

    return None


def _try_binary_combine_multi_color(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
) -> Optional[Tuple[List[np.ndarray], Dict[str, Any]]]:
    """Binary combine where output uses different colors for different overlap types.

    E.g. color X where both halves nonzero, color Y where only A nonzero,
    color Z where only B nonzero.
    """
    split0 = _split_by_single_separator(train_pairs[0][0])
    if split0 is None:
        return None
    _, _, direction0, sep_color0 = split0

    color_both = None
    color_a_only = None
    color_b_only = None
    color_neither = None

    for inp, out in train_pairs:
        split = _split_by_single_separator(inp)
        if split is None:
            return None
        half_a, half_b, direction, sep_color = split
        if direction != direction0 or sep_color != sep_color0:
            return None
        if out.shape != half_a.shape:
            return None

        a_nz = half_a != 0
        b_nz = half_b != 0

        regions = {
            "both": a_nz & b_nz,
            "a_only": a_nz & ~b_nz,
            "b_only": ~a_nz & b_nz,
            "neither": ~a_nz & ~b_nz,
        }

        for region_name, mask in regions.items():
            if not mask.any():
                continue
            vals = set(out[mask].flatten().tolist())
            if len(vals) != 1:
                return None
            val = vals.pop()
            if region_name == "both":
                if color_both is None:
                    color_both = val
                elif color_both != val:
                    return None
            elif region_name == "a_only":
                if color_a_only is None:
                    color_a_only = val
                elif color_a_only != val:
                    return None
            elif region_name == "b_only":
                if color_b_only is None:
                    color_b_only = val
                elif color_b_only != val:
                    return None
            elif region_name == "neither":
                if color_neither is None:
                    color_neither = val
                elif color_neither != val:
                    return None

    if color_both is None and color_a_only is None and color_b_only is None:
        return None

    if color_both is None:
        color_both = 0
    if color_a_only is None:
        color_a_only = 0
    if color_b_only is None:
        color_b_only = 0
    if color_neither is None:
        color_neither = 0

    for inp, out in train_pairs:
        split = _split_by_single_separator(inp)
        half_a, half_b, _, _ = split
        a_nz = half_a != 0
        b_nz = half_b != 0
        expected = np.full(half_a.shape, color_neither, dtype=int)
        expected[a_nz & b_nz] = color_both
        expected[a_nz & ~b_nz] = color_a_only
        expected[~a_nz & b_nz] = color_b_only
        if not np.array_equal(expected, out):
            return None

    predictions = []
    for ti in test_inputs:
        split = _split_by_single_separator(ti)
        if split is None:
            return None
        half_a, half_b, _, _ = split
        a_nz = half_a != 0
        b_nz = half_b != 0
        pred = np.full(half_a.shape, color_neither, dtype=int)
        pred[a_nz & b_nz] = color_both
        pred[a_nz & ~b_nz] = color_a_only
        pred[~a_nz & b_nz] = color_b_only
        predictions.append(pred)

    return predictions, {
        "strategy": "binary_combine_multi_color",
        "color_both": color_both,
        "color_a_only": color_a_only,
        "color_b_only": color_b_only,
        "color_neither": color_neither,
        "direction": direction0,
        "sep_color": sep_color0,
    }


def _extract_object_bbox(region: np.ndarray) -> Optional[np.ndarray]:
    """Extract the bounding box of non-zero pixels in a region."""
    nz = np.argwhere(region != 0)
    if len(nz) == 0:
        return None
    r0, c0 = nz.min(axis=0)
    r1, c1 = nz.max(axis=0) + 1
    return region[r0:r1, c0:c1].copy()


def _get_quadrants(
    grid: np.ndarray,
) -> Optional[Tuple[List[np.ndarray], int, int, int]]:
    """Split a grid into 4 quadrants using one row and one column separator.

    Returns (quadrants_list, row_sep, col_sep, sep_color) or None.
    The quadrants are ordered: top-left, top-right, bottom-left, bottom-right.
    """
    row_seps = _find_separator_rows(grid)
    col_seps = _find_separator_cols(grid)

    for r_idx, r_color in row_seps:
        for c_idx, c_color in col_seps:
            if r_color != c_color:
                continue
            tl = grid[:r_idx, :c_idx]
            tr = grid[:r_idx, c_idx + 1:]
            bl = grid[r_idx + 1:, :c_idx]
            br = grid[r_idx + 1:, c_idx + 1:]
            if all(q.size > 0 for q in [tl, tr, bl, br]):
                return [tl, tr, bl, br], r_idx, c_idx, r_color

    return None


def _try_quadrant_compose(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
) -> Optional[Tuple[List[np.ndarray], Dict[str, Any]]]:
    """Split into 4 quadrants, extract object bboxes, tile into 2x2 output."""
    for inp, out in train_pairs:
        quad_result = _get_quadrants(inp)
        if quad_result is None:
            return None
        quads, _, _, _ = quad_result

        objects = [_extract_object_bbox(q) for q in quads]
        if any(o is None for o in objects):
            return None

        obj_shapes = set(o.shape for o in objects)
        if len(obj_shapes) != 1:
            return None
        oh, ow = objects[0].shape

        expected = np.zeros((oh * 2, ow * 2), dtype=int)
        expected[:oh, :ow] = objects[0]
        expected[:oh, ow:] = objects[1]
        expected[oh:, :ow] = objects[2]
        expected[oh:, ow:] = objects[3]

        if not np.array_equal(expected, out):
            return None

    predictions = []
    for ti in test_inputs:
        quad_result = _get_quadrants(ti)
        if quad_result is None:
            return None
        quads, _, _, _ = quad_result
        objects = [_extract_object_bbox(q) for q in quads]
        if any(o is None for o in objects):
            return None
        obj_shapes = set(o.shape for o in objects)
        if len(obj_shapes) != 1:
            return None
        oh, ow = objects[0].shape
        pred = np.zeros((oh * 2, ow * 2), dtype=int)
        pred[:oh, :ow] = objects[0]
        pred[:oh, ow:] = objects[1]
        pred[oh:, :ow] = objects[2]
        pred[oh:, ow:] = objects[3]
        predictions.append(pred)

    return predictions, {"strategy": "quadrant_compose"}


def _split_into_cells(
    grid: np.ndarray,
    sep_color: int,
) -> Optional[Tuple[List[List[np.ndarray]], List[int], List[int]]]:
    """Split grid into a regular grid of cells delimited by separator lines.

    Returns (cells_2d, row_boundaries, col_boundaries) where cells_2d[r][c]
    is the cell content, or None if separators don't form a regular grid.
    """
    row_seps = [r for r, c in _find_separator_rows(grid) if c == sep_color]
    col_seps = [c for c, cc in _find_separator_cols(grid) if cc == sep_color]

    if not row_seps and not col_seps:
        return None

    row_bounds = []
    prev = 0
    for r in sorted(row_seps):
        if r > prev:
            row_bounds.append((prev, r))
        prev = r + 1
    if prev < grid.shape[0]:
        row_bounds.append((prev, grid.shape[0]))

    col_bounds = []
    prev = 0
    for c in sorted(col_seps):
        if c > prev:
            col_bounds.append((prev, c))
        prev = c + 1
    if prev < grid.shape[1]:
        col_bounds.append((prev, grid.shape[1]))

    if not row_bounds or not col_bounds:
        return None

    cells = []
    for r0, r1 in row_bounds:
        row_cells = []
        for c0, c1 in col_bounds:
            row_cells.append(grid[r0:r1, c0:c1].copy())
        cells.append(row_cells)

    return cells, row_bounds, col_bounds


def _try_unique_cell_extract(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
) -> Optional[Tuple[List[np.ndarray], Dict[str, Any]]]:
    """Grid of uniform cells with one unique cell; extract the unique one."""
    for inp, out in train_pairs:
        found = False
        all_colors = set(inp.flatten().tolist())
        for sep_color in sorted(all_colors):
            result = _split_into_cells(inp, sep_color)
            if result is None:
                continue
            cells, _, _ = result
            flat_cells = [c for row in cells for c in row]
            if len(flat_cells) < 3:
                continue

            cell_shapes = set(c.shape for c in flat_cells)
            if len(cell_shapes) != 1:
                continue

            cell_strs = [c.tobytes() for c in flat_cells]
            from collections import Counter
            counts = Counter(cell_strs)
            if len(counts) < 2:
                continue

            minority_key = min(counts, key=counts.get)
            if counts[minority_key] != 1:
                continue

            unique_idx = cell_strs.index(minority_key)
            unique_cell = flat_cells[unique_idx]

            if unique_cell.shape == out.shape and np.array_equal(unique_cell, out):
                found = True
                break

        if not found:
            return None

    sep_color_learned = None
    for inp, out in train_pairs:
        all_colors = set(inp.flatten().tolist())
        for sep_color in sorted(all_colors):
            result = _split_into_cells(inp, sep_color)
            if result is None:
                continue
            cells, _, _ = result
            flat_cells = [c for row in cells for c in row]
            if len(flat_cells) < 3:
                continue
            cell_shapes = set(c.shape for c in flat_cells)
            if len(cell_shapes) != 1:
                continue
            cell_strs = [c.tobytes() for c in flat_cells]
            from collections import Counter
            counts = Counter(cell_strs)
            if len(counts) < 2:
                continue
            minority_key = min(counts, key=counts.get)
            if counts[minority_key] != 1:
                continue
            unique_idx = cell_strs.index(minority_key)
            unique_cell = flat_cells[unique_idx]
            if unique_cell.shape == out.shape and np.array_equal(unique_cell, out):
                if sep_color_learned is None:
                    sep_color_learned = sep_color
                elif sep_color_learned != sep_color:
                    return None
                break

    if sep_color_learned is None:
        return None

    predictions = []
    for ti in test_inputs:
        result = _split_into_cells(ti, sep_color_learned)
        if result is None:
            return None
        cells, _, _ = result
        flat_cells = [c for row in cells for c in row]
        if len(flat_cells) < 3:
            return None
        cell_shapes = set(c.shape for c in flat_cells)
        if len(cell_shapes) != 1:
            return None
        cell_strs = [c.tobytes() for c in flat_cells]
        from collections import Counter
        counts = Counter(cell_strs)
        minority_key = min(counts, key=counts.get)
        if counts[minority_key] != 1:
            return None
        unique_idx = cell_strs.index(minority_key)
        predictions.append(flat_cells[unique_idx])

    return predictions, {"strategy": "unique_cell_extract", "sep_color": sep_color_learned}


def _try_cell_select_by_content(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
) -> Optional[Tuple[List[np.ndarray], Dict[str, Any]]]:
    """Grid of cells; select one based on content criteria (most colors, most nonzero, etc.)."""
    selectors = {
        "most_colors": lambda cells: max(range(len(cells)),
            key=lambda i: len(set(cells[i].flatten().tolist()))),
        "fewest_colors": lambda cells: min(range(len(cells)),
            key=lambda i: len(set(cells[i].flatten().tolist()))),
        "most_nonzero": lambda cells: max(range(len(cells)),
            key=lambda i: int(np.count_nonzero(cells[i]))),
        "fewest_nonzero": lambda cells: min(range(len(cells)),
            key=lambda i: int(np.count_nonzero(cells[i]))),
    }

    all_colors = set()
    for inp, _ in train_pairs:
        all_colors.update(inp.flatten().tolist())

    for sep_color in sorted(all_colors):
        for sel_name, sel_fn in selectors.items():
            ok = True
            for inp, out in train_pairs:
                result = _split_into_cells(inp, sep_color)
                if result is None:
                    ok = False
                    break
                cells, _, _ = result
                flat_cells = [c for row in cells for c in row]
                if len(flat_cells) < 2:
                    ok = False
                    break
                cell_shapes = set(c.shape for c in flat_cells)
                if len(cell_shapes) != 1:
                    ok = False
                    break
                idx = sel_fn(flat_cells)
                if flat_cells[idx].shape != out.shape or not np.array_equal(flat_cells[idx], out):
                    ok = False
                    break

            if not ok:
                continue

            predictions = []
            for ti in test_inputs:
                result = _split_into_cells(ti, sep_color)
                if result is None:
                    return None
                cells, _, _ = result
                flat_cells = [c for row in cells for c in row]
                if len(flat_cells) < 2:
                    return None
                idx = sel_fn(flat_cells)
                predictions.append(flat_cells[idx])

            return predictions, {
                "strategy": "cell_select",
                "selector": sel_name,
                "sep_color": sep_color,
            }

    return None


def _try_cell_difference(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
) -> Optional[Tuple[List[np.ndarray], Dict[str, Any]]]:
    """Grid of cells; output marks where the unique cell differs from the majority."""
    all_colors = set()
    for inp, _ in train_pairs:
        all_colors.update(inp.flatten().tolist())

    for sep_color in sorted(all_colors):
        ok = True
        out_color_learned = None

        for inp, out in train_pairs:
            result = _split_into_cells(inp, sep_color)
            if result is None:
                ok = False
                break
            cells, _, _ = result
            flat_cells = [c for row in cells for c in row]
            if len(flat_cells) < 3:
                ok = False
                break
            cell_shapes = set(c.shape for c in flat_cells)
            if len(cell_shapes) != 1:
                ok = False
                break

            cell_strs = [c.tobytes() for c in flat_cells]
            from collections import Counter
            counts = Counter(cell_strs)
            majority_key = max(counts, key=counts.get)
            majority_cell = flat_cells[cell_strs.index(majority_key)]

            found_match = False
            for i, cs in enumerate(cell_strs):
                if cs == majority_key:
                    continue
                diff_mask = flat_cells[i] != majority_cell
                diff_out = np.zeros_like(flat_cells[i])
                nonzero_vals = set(out[out != 0].flatten().tolist())
                if len(nonzero_vals) != 1:
                    continue
                oc = nonzero_vals.pop()
                diff_out[diff_mask] = oc

                if diff_out.shape == out.shape and np.array_equal(diff_out, out):
                    if out_color_learned is None:
                        out_color_learned = oc
                    elif out_color_learned != oc:
                        ok = False
                        break
                    found_match = True
                    break

            if not found_match:
                ok = False
                break

        if not ok or out_color_learned is None:
            continue

        predictions = []
        for ti in test_inputs:
            result = _split_into_cells(ti, sep_color)
            if result is None:
                return None
            cells, _, _ = result
            flat_cells = [c for row in cells for c in row]
            cell_strs = [c.tobytes() for c in flat_cells]
            from collections import Counter
            counts = Counter(cell_strs)
            majority_key = max(counts, key=counts.get)
            majority_cell = flat_cells[cell_strs.index(majority_key)]

            unique_found = False
            for i, cs in enumerate(cell_strs):
                if cs != majority_key:
                    diff_mask = flat_cells[i] != majority_cell
                    pred = np.zeros_like(flat_cells[i])
                    pred[diff_mask] = out_color_learned
                    predictions.append(pred)
                    unique_found = True
                    break
            if not unique_found:
                return None

        return predictions, {
            "strategy": "cell_difference",
            "sep_color": sep_color,
            "out_color": out_color_learned,
        }

    return None


def _try_half_transform(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
) -> Optional[Tuple[List[np.ndarray], Dict[str, Any]]]:
    """Split by separator; output is one half with a learned per-color remap."""
    split0 = _split_by_single_separator(train_pairs[0][0])
    if split0 is None:
        return None
    _, _, direction0, sep_color0 = split0

    for half_label in ["a", "b"]:
        color_map_learned = None
        ok = True

        for inp, out in train_pairs:
            split = _split_by_single_separator(inp)
            if split is None:
                ok = False
                break
            half_a, half_b, direction, sep_color = split
            if direction != direction0 or sep_color != sep_color0:
                ok = False
                break

            source = half_a if half_label == "a" else half_b
            if source.shape != out.shape:
                ok = False
                break

            cmap = {}
            for sv, ov in zip(source.flatten(), out.flatten()):
                sv, ov = int(sv), int(ov)
                if sv in cmap:
                    if cmap[sv] != ov:
                        ok = False
                        break
                else:
                    cmap[sv] = ov
            if not ok:
                break

            if color_map_learned is None:
                color_map_learned = cmap
            else:
                for k, v in cmap.items():
                    if k in color_map_learned:
                        if color_map_learned[k] != v:
                            ok = False
                            break
                    else:
                        color_map_learned[k] = v
            if not ok:
                break

        if not ok or color_map_learned is None:
            continue

        for inp, out in train_pairs:
            split = _split_by_single_separator(inp)
            half_a, half_b, _, _ = split
            source = half_a if half_label == "a" else half_b
            remapped = np.vectorize(lambda x: color_map_learned.get(int(x), int(x)))(source)
            if not np.array_equal(remapped, out):
                ok = False
                break
        if not ok:
            continue

        predictions = []
        for ti in test_inputs:
            split = _split_by_single_separator(ti)
            if split is None:
                return None
            half_a, half_b, _, _ = split
            source = half_a if half_label == "a" else half_b
            pred = np.vectorize(lambda x: color_map_learned.get(int(x), int(x)))(source)
            predictions.append(pred)

        return predictions, {
            "strategy": "half_transform",
            "half": half_label,
            "color_map": {str(k): v for k, v in color_map_learned.items()},
            "direction": direction0,
            "sep_color": sep_color0,
        }

    return None


def _find_best_sep_color(grid: np.ndarray) -> Optional[Tuple[int, int]]:
    """Find the separator color that produces the most cells in a grid.

    Returns (sep_color, n_sections) or None.
    """
    all_colors = set(grid.flatten().tolist())
    best = None
    for sc in sorted(all_colors):
        result = _split_into_cells(grid, sc)
        if result is None:
            continue
        cells, rb, cb = result
        n = len(rb) * len(cb)
        if n >= 2 and (best is None or n > best[1]):
            best = (sc, n)
    return best


def _try_grid_dimensions(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
) -> Optional[Tuple[List[np.ndarray], Dict[str, Any]]]:
    """Output shape = (n_row_sections, n_col_sections) filled with background color.

    The separator color and background color may vary per example; what's
    consistent is the structural pattern.
    """
    for inp, out in train_pairs:
        found = False
        all_colors = set(inp.flatten().tolist())
        for sep_color in sorted(all_colors):
            result = _split_into_cells(inp, sep_color)
            if result is None:
                continue
            _, rb, cb = result
            if out.shape == (len(rb), len(cb)):
                out_vals = set(out.flatten().tolist())
                if len(out_vals) == 1:
                    found = True
                    break
        if not found:
            return None

    predictions = []
    for ti in test_inputs:
        all_colors = set(ti.flatten().tolist())
        found = False
        for sep_color in sorted(all_colors):
            result = _split_into_cells(ti, sep_color)
            if result is None:
                continue
            cells, rb, cb = result
            if len(rb) >= 2 or len(cb) >= 2:
                flat_cells = [c for row in cells for c in row]
                cell_vals = set()
                for c in flat_cells:
                    cell_vals.update(c.flatten().tolist())
                bg_colors = cell_vals - {sep_color}
                if len(bg_colors) == 1:
                    bg = bg_colors.pop()
                elif len(bg_colors) == 0:
                    bg = 0
                else:
                    continue
                pred = np.full((len(rb), len(cb)), bg, dtype=int)
                predictions.append(pred)
                found = True
                break
        if not found:
            return None

    for (inp, out), pred in zip(train_pairs, []):
        pass

    check_preds = []
    for inp, out in train_pairs:
        all_colors = set(inp.flatten().tolist())
        for sep_color in sorted(all_colors):
            result = _split_into_cells(inp, sep_color)
            if result is None:
                continue
            cells, rb, cb = result
            if out.shape != (len(rb), len(cb)):
                continue
            out_vals = set(out.flatten().tolist())
            if len(out_vals) != 1:
                continue
            bg = out_vals.pop()
            expected = np.full((len(rb), len(cb)), bg, dtype=int)
            if np.array_equal(expected, out):
                check_preds.append(True)
                break
        else:
            return None

    return predictions, {"strategy": "grid_dimensions"}


SEPARATOR_STRATEGIES = [
    _try_binary_combine,
    _try_binary_combine_preserve_colors,
    _try_binary_combine_multi_color,
    _try_quadrant_compose,
    _try_unique_cell_extract,
    _try_cell_select_by_content,
    _try_cell_difference,
    _try_grid_dimensions,
    _try_half_transform,
]


def _try_cell_overlay(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
) -> Optional[Tuple[List[np.ndarray], Dict[str, Any]]]:
    """Overlay non-background content from multiple separator-delimited cells.

    Pattern: grid split into panels by separators; output merges non-background
    pixels from each panel into a single output-sized region.
    """
    for sep_color_fn in [_find_best_sep_color]:
        result = sep_color_fn(train_pairs[0][0])
        if result is None:
            continue
        sep_color, _ = result

        for inp, out in train_pairs:
            split_result = _split_into_cells(inp, sep_color)
            if split_result is None:
                return None
            cells, _, _ = split_result

            flat = [c for row in cells for c in row]
            if not flat:
                return None

            cell_h, cell_w = flat[0].shape
            if any(c.shape != (cell_h, cell_w) for c in flat):
                return None

            if out.shape != (cell_h, cell_w):
                return None

            bg_colors = set()
            for c in flat:
                vals = set(c.flat)
                if len(vals) == 1:
                    bg_colors |= vals

            if not bg_colors:
                all_vals = set()
                for c in flat:
                    all_vals |= set(c.flat)
                bg_colors = {min(all_vals)}

            merged = np.full((cell_h, cell_w), list(bg_colors)[0], dtype=int)
            for c in flat:
                mask = np.ones((cell_h, cell_w), dtype=bool)
                for bg in bg_colors:
                    mask &= (c != bg)
                merged[mask] = c[mask]

            if not np.array_equal(merged, out):
                return None

        predictions = []
        for ti in test_inputs:
            split_result = _split_into_cells(ti, sep_color)
            if split_result is None:
                return None
            cells, _, _ = split_result
            flat = [c for row in cells for c in row]
            if not flat:
                return None
            cell_h, cell_w = flat[0].shape

            bg_colors_t = set()
            for c in flat:
                vals = set(c.flat)
                if len(vals) == 1:
                    bg_colors_t |= vals
            if not bg_colors_t:
                all_vals = set()
                for c in flat:
                    all_vals |= set(c.flat)
                bg_colors_t = {min(all_vals)}

            merged = np.full((cell_h, cell_w), list(bg_colors_t)[0], dtype=int)
            for c in flat:
                mask = np.ones((cell_h, cell_w), dtype=bool)
                for bg in bg_colors_t:
                    mask &= (c != bg)
                merged[mask] = c[mask]
            predictions.append(merged)

        return predictions, {"strategy": "cell_overlay", "sep_color": int(sep_color)}

    return None


def _try_cell_marker_position(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
) -> Optional[Tuple[List[np.ndarray], Dict[str, Any]]]:
    """Map marker pixel positions within a regular cell grid to output grid.

    Pattern: NxN grid of uniform cells, each with at most 1 marker pixel.
    Output is (n_row_cells x n_col_cells) grid where the marker color fills the
    cell's position, background elsewhere.
    """
    for inp, out in train_pairs:
        for sep_color in range(10):
            split_result = _split_into_cells(inp, sep_color)
            if split_result is None:
                continue
            cells, _, _ = split_result
            n_rows = len(cells)
            n_cols = len(cells[0]) if cells else 0

            if out.shape != (n_rows, n_cols):
                continue

            bg_color = sep_color
            ok = True
            for ri in range(n_rows):
                for ci in range(n_cols):
                    cell = cells[ri][ci]
                    non_bg = cell[cell != bg_color]
                    unique_non_bg = set(non_bg.tolist()) - {0}

                    if len(unique_non_bg) == 0:
                        expected = 0 if out[ri, ci] == 0 else bg_color
                        if out[ri, ci] != 0 and out[ri, ci] != bg_color:
                            ok = False
                            break
                    elif len(unique_non_bg) == 1:
                        marker = unique_non_bg.pop()
                        if out[ri, ci] != marker:
                            ok = False
                            break
                    else:
                        ok = False
                        break
                if not ok:
                    break

            if not ok:
                continue

            all_ok = True
            for inp2, out2 in train_pairs[1:]:
                split2 = _split_into_cells(inp2, sep_color)
                if split2 is None:
                    all_ok = False
                    break
                cells2, _, _ = split2
                nr2 = len(cells2)
                nc2 = len(cells2[0]) if cells2 else 0
                if out2.shape != (nr2, nc2):
                    all_ok = False
                    break
                for ri in range(nr2):
                    for ci in range(nc2):
                        cell = cells2[ri][ci]
                        non_bg = set(cell[cell != sep_color].tolist()) - {0}
                        if len(non_bg) == 0:
                            if out2[ri, ci] != 0 and out2[ri, ci] != sep_color:
                                all_ok = False
                                break
                        elif len(non_bg) == 1:
                            if out2[ri, ci] != non_bg.pop():
                                all_ok = False
                                break
                        else:
                            all_ok = False
                            break
                    if not all_ok:
                        break
                if not all_ok:
                    break

            if not all_ok:
                continue

            predictions = []
            for ti in test_inputs:
                split_t = _split_into_cells(ti, sep_color)
                if split_t is None:
                    return None
                cells_t, _, _ = split_t
                nr_t = len(cells_t)
                nc_t = len(cells_t[0]) if cells_t else 0
                pred = np.zeros((nr_t, nc_t), dtype=int)
                for ri in range(nr_t):
                    for ci in range(nc_t):
                        cell = cells_t[ri][ci]
                        non_bg = set(cell[cell != sep_color].tolist()) - {0}
                        if len(non_bg) == 1:
                            pred[ri, ci] = non_bg.pop()
                predictions.append(pred)

            return predictions, {"strategy": "cell_marker_position",
                                 "sep_color": int(sep_color)}

    return None


def _try_separator_color_extract(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
) -> Optional[Tuple[List[np.ndarray], Dict[str, Any]]]:
    """Extract the unique separator colors as output.

    Pattern: grid has separator lines of different colors; output is a 1D
    array of those colors (sorted by position).
    """
    orient = None  # "row" = (1, N) or "col" = (N, 1)
    for inp, out in train_pairs:
        if out.size > max(inp.shape):
            return None

        row_seps = _find_separator_rows(inp)
        col_seps = _find_separator_cols(inp)

        n_sep_rows = len(row_seps)
        n_sep_cols = len(col_seps)
        if n_sep_rows > inp.shape[0] // 3 or n_sep_cols > inp.shape[1] // 3:
            return None

        all_seps = []
        for r, c in row_seps:
            all_seps.append(("row", r, c))
        for c_idx, c in col_seps:
            all_seps.append(("col", c_idx, c))

        unique_colors = []
        seen = set()
        for kind, idx, color in sorted(all_seps, key=lambda x: x[1]):
            if color not in seen:
                unique_colors.append(color)
                seen.add(color)

        if len(unique_colors) == 0:
            return None

        target = out.flatten().tolist()
        if unique_colors == target:
            pass
        elif unique_colors[::-1] == target:
            unique_colors = unique_colors[::-1]
        else:
            return None

        if out.shape[0] == 1:
            orient = "row"
        elif out.shape[1] == 1:
            orient = "col"
        else:
            return None

    predictions = []
    for ti in test_inputs:
        row_seps = _find_separator_rows(ti)
        col_seps = _find_separator_cols(ti)
        all_seps = []
        for r, c in row_seps:
            all_seps.append(("row", r, c))
        for c_idx, c in col_seps:
            all_seps.append(("col", c_idx, c))

        colors = []
        seen = set()
        for kind, idx, color in sorted(all_seps, key=lambda x: x[1]):
            if color not in seen:
                colors.append(color)
                seen.add(color)

        arr = np.array(colors, dtype=int)
        if orient == "row":
            pred = arr.reshape(1, -1)
        else:
            pred = arr.reshape(-1, 1)
        predictions.append(pred)

    return predictions, {"strategy": "separator_color_extract"}


def _try_cell_majority_vote(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
) -> Optional[Tuple[List[np.ndarray], Dict[str, Any]]]:
    """Output cell = pixel-wise majority vote across corresponding cell positions.

    Pattern: grid split into N same-shape cells; output = majority pixel at
    each position across all cells.
    """
    for inp, out in train_pairs:
        for sep_color in range(10):
            split_result = _split_into_cells(inp, sep_color)
            if split_result is None:
                continue
            cells, _, _ = split_result
            flat = [c for row in cells for c in row]
            if len(flat) < 2:
                continue

            cell_h, cell_w = flat[0].shape
            if any(c.shape != (cell_h, cell_w) for c in flat):
                continue
            if out.shape != (cell_h, cell_w):
                continue

            stack = np.stack(flat, axis=0)
            voted = np.zeros((cell_h, cell_w), dtype=int)
            for r in range(cell_h):
                for c in range(cell_w):
                    vals = stack[:, r, c].tolist()
                    counts = {}
                    for v in vals:
                        if v != sep_color:
                            counts[v] = counts.get(v, 0) + 1
                    if counts:
                        voted[r, c] = max(counts, key=counts.get)

            if not np.array_equal(voted, out):
                continue

            all_ok = True
            for inp2, out2 in train_pairs[1:]:
                split2 = _split_into_cells(inp2, sep_color)
                if split2 is None:
                    all_ok = False
                    break
                cells2 = [c for row in split2[0] for c in row]
                if not cells2 or cells2[0].shape != out2.shape:
                    all_ok = False
                    break
                stack2 = np.stack(cells2, axis=0)
                voted2 = np.zeros(out2.shape, dtype=int)
                for r in range(out2.shape[0]):
                    for c in range(out2.shape[1]):
                        vals = stack2[:, r, c].tolist()
                        cts = {}
                        for v in vals:
                            if v != sep_color:
                                cts[v] = cts.get(v, 0) + 1
                        if cts:
                            voted2[r, c] = max(cts, key=cts.get)
                if not np.array_equal(voted2, out2):
                    all_ok = False
                    break
            if not all_ok:
                continue

            predictions = []
            for ti in test_inputs:
                split_t = _split_into_cells(ti, sep_color)
                if split_t is None:
                    return None
                cells_t = [c for row in split_t[0] for c in row]
                ch, cw = cells_t[0].shape
                stack_t = np.stack(cells_t, axis=0)
                pred = np.zeros((ch, cw), dtype=int)
                for r in range(ch):
                    for c in range(cw):
                        vals = stack_t[:, r, c].tolist()
                        cts = {}
                        for v in vals:
                            if v != sep_color:
                                cts[v] = cts.get(v, 0) + 1
                        if cts:
                            pred[r, c] = max(cts, key=cts.get)
                predictions.append(pred)

            return predictions, {"strategy": "cell_majority_vote",
                                 "sep_color": int(sep_color)}

    return None


SEPARATOR_STRATEGIES = [
    _try_binary_combine,
    _try_binary_combine_preserve_colors,
    _try_binary_combine_multi_color,
    _try_quadrant_compose,
    _try_unique_cell_extract,
    _try_cell_select_by_content,
    _try_cell_difference,
    _try_cell_overlay,
    _try_cell_majority_vote,
    _try_cell_marker_position,
    _try_separator_color_extract,
    _try_grid_dimensions,
    _try_half_transform,
]


def solve_task_separator_decompose(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
) -> Optional[Tuple[List[np.ndarray], Dict[str, Any]]]:
    """Try all separator decomposition strategies."""
    for strategy_fn in SEPARATOR_STRATEGIES:
        try:
            result = strategy_fn(train_pairs, test_inputs)
            if result is not None:
                return result
        except Exception:
            continue
    return None
