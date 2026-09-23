"""Advanced fill and pattern solvers for ARC tasks.

Targets the ~55 unsolved fill-zero tasks plus pattern completion,
ray casting, gravity, and enclosed-region coloring.
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage
from typing import Optional, List, Tuple, Dict, Any


def _enclosed_regions(grid: np.ndarray, bg: int = 0):
    """Find enclosed background regions (not touching border)."""
    bg_mask = grid == bg
    labeled, n = ndimage.label(bg_mask)
    edge_labels = set()
    h, w = grid.shape
    edge_labels.update(labeled[0, :].tolist())
    edge_labels.update(labeled[-1, :].tolist())
    edge_labels.update(labeled[:, 0].tolist())
    edge_labels.update(labeled[:, -1].tolist())
    edge_labels.discard(0)
    interior = []
    for lab in range(1, n + 1):
        if lab not in edge_labels:
            interior.append((lab, labeled == lab))
    return labeled, interior


def _border_colors(grid: np.ndarray, region_mask: np.ndarray):
    """Get the set of non-background colors bordering a region."""
    dilated = ndimage.binary_dilation(region_mask) & ~region_mask
    return set(grid[dilated].tolist()) - {0}


def _try_fill_enclosed_by_border(train_pairs, test_inputs):
    """Fill each enclosed region with a color determined by its border color.

    Rule: each enclosed region gets filled with the color of the non-bg cells
    bordering it. Works when each enclosed region has exactly one border color.
    """
    if not all(inp.shape == out.shape for inp, out in train_pairs):
        return None

    for inp, out in train_pairs:
        labeled, interior = _enclosed_regions(inp)
        if not interior:
            return None

        for lab, mask in interior:
            bc = _border_colors(inp, mask)
            if len(bc) != 1:
                return None
            fill_c = bc.pop()
            if not np.all(out[mask] == fill_c):
                return None

        if not np.all(out[inp > 0] == inp[inp > 0]):
            return None

    preds = []
    for test_inp in test_inputs:
        pred = test_inp.copy()
        labeled, interior = _enclosed_regions(test_inp)
        for lab, mask in interior:
            bc = _border_colors(test_inp, mask)
            if len(bc) == 1:
                pred[mask] = bc.pop()
        preds.append(pred)
    return preds, {"strategy": "fill_enclosed_by_border"}


def _try_fill_enclosed_multi_color(train_pairs, test_inputs):
    """Fill enclosed regions where fill color is learned from training examples.

    Learns a mapping: border_color_set -> fill_color from training, applies to test.
    """
    if not all(inp.shape == out.shape for inp, out in train_pairs):
        return None

    color_map = {}
    for inp, out in train_pairs:
        labeled, interior = _enclosed_regions(inp)
        if not interior:
            return None

        for lab, mask in interior:
            bc = frozenset(_border_colors(inp, mask))
            out_vals = set(out[mask].tolist())
            if len(out_vals) != 1:
                return None
            fill_c = out_vals.pop()
            if bc in color_map and color_map[bc] != fill_c:
                return None
            color_map[bc] = fill_c

        if not np.all(out[inp > 0] == inp[inp > 0]):
            return None

    if not color_map:
        return None

    preds = []
    for test_inp in test_inputs:
        pred = test_inp.copy()
        labeled, interior = _enclosed_regions(test_inp)
        for lab, mask in interior:
            bc = frozenset(_border_colors(test_inp, mask))
            if bc in color_map:
                pred[mask] = color_map[bc]
            else:
                return None
        preds.append(pred)
    return preds, {"strategy": "fill_enclosed_multi_color", "color_map_size": len(color_map)}


def _try_fill_enclosed_by_size(train_pairs, test_inputs):
    """Fill enclosed regions based on their size."""
    if not all(inp.shape == out.shape for inp, out in train_pairs):
        return None

    size_map = {}
    for inp, out in train_pairs:
        labeled, interior = _enclosed_regions(inp)
        if not interior:
            return None

        for lab, mask in interior:
            size = int(np.sum(mask))
            out_vals = set(out[mask].tolist())
            if len(out_vals) != 1:
                return None
            fill_c = out_vals.pop()
            if size in size_map and size_map[size] != fill_c:
                return None
            size_map[size] = fill_c

        if not np.all(out[inp > 0] == inp[inp > 0]):
            return None

    if not size_map:
        return None

    preds = []
    for test_inp in test_inputs:
        pred = test_inp.copy()
        labeled, interior = _enclosed_regions(test_inp)
        for lab, mask in interior:
            size = int(np.sum(mask))
            if size in size_map:
                pred[mask] = size_map[size]
            else:
                return None
        preds.append(pred)
    return preds, {"strategy": "fill_enclosed_by_size", "size_map": size_map}


def _try_gravity(train_pairs, test_inputs):
    """Simulate gravity: non-background objects fall in one direction."""
    if not all(inp.shape == out.shape for inp, out in train_pairs):
        return None

    for direction in ['down', 'up', 'left', 'right']:
        ok = True
        for inp, out in train_pairs:
            pred = _apply_gravity(inp, direction)
            if pred is None or not np.array_equal(pred, out):
                ok = False
                break
        if ok:
            preds = []
            for test_inp in test_inputs:
                pred = _apply_gravity(test_inp, direction)
                if pred is None:
                    return None
                preds.append(pred)
            return preds, {"strategy": "gravity", "direction": direction}
    return None


def _apply_gravity(grid: np.ndarray, direction: str) -> Optional[np.ndarray]:
    """Apply gravity in given direction - objects fall to one side."""
    h, w = grid.shape
    result = np.zeros_like(grid)

    if direction == 'down':
        for c in range(w):
            col = grid[:, c]
            nonzero = col[col > 0]
            result[h - len(nonzero):, c] = nonzero
    elif direction == 'up':
        for c in range(w):
            col = grid[:, c]
            nonzero = col[col > 0]
            result[:len(nonzero), c] = nonzero
    elif direction == 'right':
        for r in range(h):
            row = grid[r, :]
            nonzero = row[row > 0]
            result[r, w - len(nonzero):] = nonzero
    elif direction == 'left':
        for r in range(h):
            row = grid[r, :]
            nonzero = row[row > 0]
            result[r, :len(nonzero)] = nonzero
    else:
        return None
    return result


def _try_gravity_with_walls(train_pairs, test_inputs):
    """Gravity where a specific color acts as immovable walls."""
    if not all(inp.shape == out.shape for inp, out in train_pairs):
        return None

    for wall_color in range(1, 10):
        for direction in ['down', 'up', 'left', 'right']:
            ok = True
            for inp, out in train_pairs:
                if wall_color not in inp:
                    ok = False
                    break
                pred = _apply_gravity_with_walls(inp, direction, wall_color)
                if pred is None or not np.array_equal(pred, out):
                    ok = False
                    break
            if ok:
                preds = []
                for test_inp in test_inputs:
                    pred = _apply_gravity_with_walls(test_inp, direction, wall_color)
                    if pred is None:
                        return None
                    preds.append(pred)
                return preds, {"strategy": "gravity_with_walls", "direction": direction, "wall_color": wall_color}
    return None


def _apply_gravity_with_walls(grid: np.ndarray, direction: str, wall_color: int) -> Optional[np.ndarray]:
    """Apply gravity with immovable wall cells."""
    h, w = grid.shape
    result = np.zeros_like(grid)
    result[grid == wall_color] = wall_color

    if direction in ('down', 'up'):
        for c in range(w):
            segments = []
            start = 0
            for r in range(h):
                if grid[r, c] == wall_color:
                    segments.append((start, r))
                    start = r + 1
            segments.append((start, h))

            for s, e in segments:
                col_seg = grid[s:e, c]
                nonzero = col_seg[(col_seg > 0) & (col_seg != wall_color)]
                if direction == 'down':
                    seg_len = e - s
                    result[e - len(nonzero):e, c] = nonzero
                else:
                    result[s:s + len(nonzero), c] = nonzero
    elif direction in ('left', 'right'):
        for r in range(h):
            segments = []
            start = 0
            for c in range(w):
                if grid[r, c] == wall_color:
                    segments.append((start, c))
                    start = c + 1
            segments.append((start, w))

            for s, e in segments:
                row_seg = grid[r, s:e]
                nonzero = row_seg[(row_seg > 0) & (row_seg != wall_color)]
                if direction == 'right':
                    result[r, e - len(nonzero):e] = nonzero
                else:
                    result[r, s:s + len(nonzero)] = nonzero
    return result


def _try_ray_cast(train_pairs, test_inputs):
    """Draw rays from colored seed pixels in cardinal/diagonal directions."""
    if not all(inp.shape == out.shape for inp, out in train_pairs):
        return None

    for ray_type in ['cardinal', 'diagonal', 'all8']:
        for stop_at_edge in [True, False]:
            ok = True
            for inp, out in train_pairs:
                pred = _apply_ray_cast(inp, ray_type, stop_at_edge)
                if pred is None or not np.array_equal(pred, out):
                    ok = False
                    break
            if ok:
                preds = []
                for test_inp in test_inputs:
                    pred = _apply_ray_cast(test_inp, ray_type, stop_at_edge)
                    if pred is None:
                        return None
                    preds.append(pred)
                return preds, {"strategy": "ray_cast", "ray_type": ray_type}
    return None


def _apply_ray_cast(grid: np.ndarray, ray_type: str, stop_at_nonzero: bool) -> np.ndarray:
    """Cast rays from each non-zero pixel."""
    h, w = grid.shape
    result = grid.copy()

    if ray_type == 'cardinal':
        dirs = [(0, 1), (0, -1), (1, 0), (-1, 0)]
    elif ray_type == 'diagonal':
        dirs = [(1, 1), (1, -1), (-1, 1), (-1, -1)]
    else:
        dirs = [(0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (1, -1), (-1, 1), (-1, -1)]

    seeds = list(zip(*np.where(grid > 0)))
    for r, c in seeds:
        color = grid[r, c]
        for dr, dc in dirs:
            nr, nc = r + dr, c + dc
            while 0 <= nr < h and 0 <= nc < w:
                if stop_at_nonzero and grid[nr, nc] > 0:
                    break
                result[nr, nc] = color
                nr += dr
                nc += dc
    return result


def _try_connect_same_color(train_pairs, test_inputs):
    """Draw lines between objects of the same color."""
    if not all(inp.shape == out.shape for inp, out in train_pairs):
        return None

    for line_type in ['horizontal', 'vertical', 'both', 'shortest']:
        ok = True
        for inp, out in train_pairs:
            pred = _apply_connect_same_color(inp, line_type)
            if pred is None or not np.array_equal(pred, out):
                ok = False
                break
        if ok:
            preds = []
            for test_inp in test_inputs:
                pred = _apply_connect_same_color(test_inp, line_type)
                if pred is None:
                    return None
                preds.append(pred)
            return preds, {"strategy": "connect_same_color", "line_type": line_type}
    return None


def _apply_connect_same_color(grid: np.ndarray, line_type: str) -> np.ndarray:
    """Connect same-colored objects with lines."""
    h, w = grid.shape
    result = grid.copy()

    for color in range(1, 10):
        mask = grid == color
        if np.sum(mask) == 0:
            continue
        labeled, n = ndimage.label(mask)
        if n < 2:
            continue

        centroids = ndimage.center_of_mass(mask, labeled, range(1, n + 1))

        for i in range(n):
            for j in range(i + 1, n):
                r1, c1 = int(round(centroids[i][0])), int(round(centroids[i][1]))
                r2, c2 = int(round(centroids[j][0])), int(round(centroids[j][1]))

                if line_type == 'horizontal' or (line_type == 'both'):
                    if r1 == r2:
                        for c in range(min(c1, c2), max(c1, c2) + 1):
                            result[r1, c] = color
                    if line_type == 'horizontal':
                        continue

                if line_type == 'vertical' or (line_type == 'both'):
                    if c1 == c2:
                        for r in range(min(r1, r2), max(r1, r2) + 1):
                            result[r, c1] = color
                    if line_type == 'vertical':
                        continue

                if line_type in ('both', 'shortest'):
                    if abs(r2 - r1) <= abs(c2 - c1):
                        for c in range(min(c1, c2), max(c1, c2) + 1):
                            result[r1, c] = color
                    else:
                        for r in range(min(r1, r2), max(r1, r2) + 1):
                            result[r, c1] = color
    return result


def _try_mirror_half(train_pairs, test_inputs):
    """Complete a grid by mirroring one half to the other."""
    if not all(inp.shape == out.shape for inp, out in train_pairs):
        return None

    for axis in ['horizontal', 'vertical', 'both']:
        ok = True
        for inp, out in train_pairs:
            pred = _apply_mirror(inp, axis)
            if pred is None or not np.array_equal(pred, out):
                ok = False
                break
        if ok:
            preds = [_apply_mirror(ti, axis) for ti in test_inputs]
            if all(p is not None for p in preds):
                return preds, {"strategy": "mirror_half", "axis": axis}
    return None


def _apply_mirror(grid: np.ndarray, axis: str) -> Optional[np.ndarray]:
    """Mirror non-zero content across an axis.

    Only activates when one half is substantially emptier than the other,
    indicating genuine half-completion rather than sparse patterns.
    """
    h, w = grid.shape
    result = grid.copy()

    if axis in ('horizontal', 'both'):
        mid = h // 2
        top_zeros = np.sum(grid[:mid, :] == 0)
        bot_zeros = np.sum(grid[mid:, :] == 0)
        top_total = mid * w
        bot_total = (h - mid) * w
        top_frac = top_zeros / top_total if top_total else 0
        bot_frac = bot_zeros / bot_total if bot_total else 0
        if abs(top_frac - bot_frac) < 0.2:
            if axis == 'horizontal':
                return None
        else:
            for r in range(h):
                for c in range(w):
                    mr = h - 1 - r
                    if result[r, c] == 0 and result[mr, c] != 0:
                        result[r, c] = result[mr, c]
                    elif result[mr, c] == 0 and result[r, c] != 0:
                        result[mr, c] = result[r, c]

    if axis in ('vertical', 'both'):
        mid = w // 2
        left_zeros = np.sum(result[:, :mid] == 0)
        right_zeros = np.sum(result[:, mid:] == 0)
        left_total = h * mid
        right_total = h * (w - mid)
        left_frac = left_zeros / left_total if left_total else 0
        right_frac = right_zeros / right_total if right_total else 0
        if abs(left_frac - right_frac) < 0.2:
            if axis == 'vertical':
                return None
        else:
            for r in range(h):
                for c in range(w):
                    mc = w - 1 - c
                    if result[r, c] == 0 and result[r, mc] != 0:
                        result[r, c] = result[r, mc]
                    elif result[r, mc] == 0 and result[r, c] != 0:
                        result[r, mc] = result[r, c]

    if np.array_equal(result, grid):
        return None
    return result


def _try_denoise_majority(train_pairs, test_inputs):
    """Replace each cell with the majority color in its neighborhood."""
    if not all(inp.shape == out.shape for inp, out in train_pairs):
        return None

    for radius in [1, 2]:
        ok = True
        for inp, out in train_pairs:
            pred = _apply_denoise(inp, radius)
            if not np.array_equal(pred, out):
                ok = False
                break
        if ok:
            preds = [_apply_denoise(ti, radius) for ti in test_inputs]
            return preds, {"strategy": "denoise_majority", "radius": radius}
    return None


def _apply_denoise(grid: np.ndarray, radius: int) -> np.ndarray:
    """Replace each cell with majority of neighborhood."""
    h, w = grid.shape
    result = grid.copy()
    for r in range(h):
        for c in range(w):
            r0 = max(0, r - radius)
            r1 = min(h, r + radius + 1)
            c0 = max(0, c - radius)
            c1 = min(w, c + radius + 1)
            patch = grid[r0:r1, c0:c1]
            vals, counts = np.unique(patch, return_counts=True)
            result[r, c] = vals[np.argmax(counts)]
    return result


def _try_flood_from_seeds(train_pairs, test_inputs):
    """Flood fill from seed pixels - each colored pixel floods its connected zero-region."""
    if not all(inp.shape == out.shape for inp, out in train_pairs):
        return None

    ok = True
    for inp, out in train_pairs:
        pred = _apply_flood_from_seeds(inp)
        if pred is None or not np.array_equal(pred, out):
            ok = False
            break
    if ok:
        preds = [_apply_flood_from_seeds(ti) for ti in test_inputs]
        if all(p is not None for p in preds):
            return preds, {"strategy": "flood_from_seeds"}
    return None


def _apply_flood_from_seeds(grid: np.ndarray) -> np.ndarray:
    """Each non-zero pixel floods its adjacent zero-region with its color."""
    h, w = grid.shape
    result = grid.copy()
    bg_labeled, n_bg = ndimage.label(grid == 0)

    for lab in range(1, n_bg + 1):
        region = bg_labeled == lab
        dilated = ndimage.binary_dilation(region) & ~region
        border_colors = {}
        for r, c in zip(*np.where(dilated)):
            if grid[r, c] > 0:
                color = int(grid[r, c])
                border_colors[color] = border_colors.get(color, 0) + 1
        if len(border_colors) == 1:
            result[region] = list(border_colors.keys())[0]
    return result


def _try_expand_objects(train_pairs, test_inputs):
    """Expand each colored object to fill its bounding box or to grid edges."""
    if not all(inp.shape == out.shape for inp, out in train_pairs):
        return None

    for expand_type in ['bbox', 'row', 'col', 'cross']:
        ok = True
        for inp, out in train_pairs:
            pred = _apply_expand(inp, expand_type)
            if not np.array_equal(pred, out):
                ok = False
                break
        if ok:
            preds = [_apply_expand(ti, expand_type) for ti in test_inputs]
            return preds, {"strategy": "expand_objects", "type": expand_type}
    return None


def _apply_expand(grid: np.ndarray, expand_type: str) -> np.ndarray:
    """Expand objects by type."""
    h, w = grid.shape
    result = grid.copy()

    for color in range(1, 10):
        mask = grid == color
        if not np.any(mask):
            continue
        rows = np.any(mask, axis=1)
        cols = np.any(mask, axis=0)

        if expand_type == 'bbox':
            r0, r1 = np.where(rows)[0][[0, -1]]
            c0, c1 = np.where(cols)[0][[0, -1]]
            result[r0:r1+1, c0:c1+1] = np.where(
                result[r0:r1+1, c0:c1+1] == 0, color, result[r0:r1+1, c0:c1+1]
            )
        elif expand_type == 'row':
            for r in np.where(rows)[0]:
                result[r, result[r] == 0] = color
        elif expand_type == 'col':
            for c in np.where(cols)[0]:
                result[result[:, c] == 0, c] = color
        elif expand_type == 'cross':
            for r in np.where(rows)[0]:
                result[r, result[r] == 0] = color
            for c in np.where(cols)[0]:
                result[result[:, c] == 0, c] = color
    return result


def _try_scale_pattern(train_pairs, test_inputs):
    """Output is the input pattern scaled up by an integer factor."""
    for inp, out in train_pairs:
        if out.shape[0] % inp.shape[0] != 0 or out.shape[1] % inp.shape[1] != 0:
            return None

    scale_r = train_pairs[0][1].shape[0] // train_pairs[0][0].shape[0]
    scale_c = train_pairs[0][1].shape[1] // train_pairs[0][0].shape[1]

    if scale_r < 2 and scale_c < 2:
        return None

    ok = True
    for inp, out in train_pairs:
        sr = out.shape[0] // inp.shape[0]
        sc = out.shape[1] // inp.shape[1]
        if sr != scale_r or sc != scale_c:
            ok = False
            break
        pred = np.repeat(np.repeat(inp, scale_r, axis=0), scale_c, axis=1)
        if not np.array_equal(pred, out):
            ok = False
            break

    if ok:
        preds = [np.repeat(np.repeat(ti, scale_r, axis=0), scale_c, axis=1) for ti in test_inputs]
        return preds, {"strategy": "scale_pattern", "scale": (scale_r, scale_c)}
    return None


def _try_tile_pattern(train_pairs, test_inputs):
    """Output is the input pattern tiled to fill a larger grid."""
    for inp, out in train_pairs:
        if out.shape[0] < inp.shape[0] or out.shape[1] < inp.shape[1]:
            return None

    ok = True
    for inp, out in train_pairs:
        ih, iw = inp.shape
        oh, ow = out.shape
        if oh % ih != 0 or ow % iw != 0:
            ok = False
            break
        pred = np.tile(inp, (oh // ih, ow // iw))
        if not np.array_equal(pred, out):
            ok = False
            break

    if ok:
        preds = []
        for test_inp in test_inputs:
            tr = train_pairs[0][1].shape[0] // train_pairs[0][0].shape[0]
            tc = train_pairs[0][1].shape[1] // train_pairs[0][0].shape[1]
            preds.append(np.tile(test_inp, (tr, tc)))
        return preds, {"strategy": "tile_pattern"}
    return None


def _try_border_draw(train_pairs, test_inputs):
    """Draw a border (outline) around non-zero objects."""
    if not all(inp.shape == out.shape for inp, out in train_pairs):
        return None

    for border_color in range(1, 10):
        ok = True
        for inp, out in train_pairs:
            fg = inp > 0
            dilated = ndimage.binary_dilation(fg)
            border_mask = dilated & ~fg
            pred = inp.copy()
            pred[border_mask] = border_color
            if not np.array_equal(pred, out):
                ok = False
                break
        if ok:
            preds = []
            for test_inp in test_inputs:
                fg = test_inp > 0
                dilated = ndimage.binary_dilation(fg)
                border_mask = dilated & ~fg
                pred = test_inp.copy()
                pred[border_mask] = border_color
                preds.append(pred)
            return preds, {"strategy": "border_draw", "color": border_color}
    return None


def _try_extend_to_boundary(train_pairs, test_inputs):
    """Extend each colored pixel to the nearest grid boundary in one direction."""
    if not all(inp.shape == out.shape for inp, out in train_pairs):
        return None

    for direction in ['right', 'left', 'down', 'up']:
        ok = True
        for inp, out in train_pairs:
            pred = _apply_extend_to_boundary(inp, direction)
            if not np.array_equal(pred, out):
                ok = False
                break
        if ok:
            preds = [_apply_extend_to_boundary(ti, direction) for ti in test_inputs]
            return preds, {"strategy": "extend_to_boundary", "direction": direction}
    return None


def _apply_extend_to_boundary(grid: np.ndarray, direction: str) -> np.ndarray:
    h, w = grid.shape
    result = grid.copy()
    for r in range(h):
        for c in range(w):
            if grid[r, c] > 0:
                color = grid[r, c]
                if direction == 'right':
                    result[r, c:] = np.where(result[r, c:] == 0, color, result[r, c:])
                elif direction == 'left':
                    result[r, :c+1] = np.where(result[r, :c+1] == 0, color, result[r, :c+1])
                elif direction == 'down':
                    result[r:, c] = np.where(result[r:, c] == 0, color, result[r:, c])
                elif direction == 'up':
                    result[:r+1, c] = np.where(result[:r+1, c] == 0, color, result[:r+1, c])
    return result


def _try_extend_line_segments(train_pairs, test_inputs):
    """Extend existing line segments to grid boundaries."""
    if not all(inp.shape == out.shape for inp, out in train_pairs):
        return None

    ok = True
    for inp, out in train_pairs:
        pred = _apply_extend_lines(inp)
        if not np.array_equal(pred, out):
            ok = False
            break
    if ok:
        preds = [_apply_extend_lines(ti) for ti in test_inputs]
        return preds, {"strategy": "extend_line_segments"}
    return None


def _apply_extend_lines(grid: np.ndarray) -> np.ndarray:
    h, w = grid.shape
    result = grid.copy()
    for color in range(1, 10):
        mask = grid == color
        if not np.any(mask):
            continue
        for r in range(h):
            row = mask[r, :]
            if np.sum(row) >= 2:
                indices = np.where(row)[0]
                result[r, indices[0]:indices[-1]+1] = color
        for c in range(w):
            col = mask[:, c]
            if np.sum(col) >= 2:
                indices = np.where(col)[0]
                result[indices[0]:indices[-1]+1, c] = color
    return result


def _try_color_map(train_pairs, test_inputs):
    """Simple global color remapping: f(color) -> color."""
    if not all(inp.shape == out.shape for inp, out in train_pairs):
        return None

    cmap = {}
    for inp, out in train_pairs:
        for r in range(inp.shape[0]):
            for c in range(inp.shape[1]):
                ic = int(inp[r, c])
                oc = int(out[r, c])
                if ic in cmap and cmap[ic] != oc:
                    return None
                cmap[ic] = oc

    if all(k == v for k, v in cmap.items()):
        return None

    preds = []
    for test_inp in test_inputs:
        pred = test_inp.copy()
        for r in range(pred.shape[0]):
            for c in range(pred.shape[1]):
                ic = int(pred[r, c])
                if ic in cmap:
                    pred[r, c] = cmap[ic]
                else:
                    return None
        preds.append(pred)
    return preds, {"strategy": "color_map", "map": cmap}


def _try_remove_small_objects(train_pairs, test_inputs):
    """Remove small connected components (noise)."""
    if not all(inp.shape == out.shape for inp, out in train_pairs):
        return None

    for max_size in [1, 2, 3]:
        ok = True
        for inp, out in train_pairs:
            pred = _apply_remove_small(inp, max_size)
            if not np.array_equal(pred, out):
                ok = False
                break
        if ok:
            preds = [_apply_remove_small(ti, max_size) for ti in test_inputs]
            return preds, {"strategy": "remove_small_objects", "max_size": max_size}

    for max_size in [1, 2, 3]:
        ok = True
        for inp, out in train_pairs:
            pred = _apply_remove_small_per_color(inp, max_size)
            if not np.array_equal(pred, out):
                ok = False
                break
        if ok:
            preds = [_apply_remove_small_per_color(ti, max_size) for ti in test_inputs]
            return preds, {"strategy": "remove_small_per_color", "max_size": max_size}
    return None


def _apply_remove_small(grid: np.ndarray, max_size: int) -> np.ndarray:
    result = grid.copy()
    labeled, n = ndimage.label(grid > 0)
    for lab in range(1, n + 1):
        mask = labeled == lab
        if np.sum(mask) <= max_size:
            result[mask] = 0
    return result


def _apply_remove_small_per_color(grid: np.ndarray, max_size: int) -> np.ndarray:
    result = grid.copy()
    for color in range(1, 10):
        mask = grid == color
        if not np.any(mask):
            continue
        labeled, n = ndimage.label(mask)
        for lab in range(1, n + 1):
            cc = labeled == lab
            if np.sum(cc) <= max_size:
                result[cc] = 0
    return result


def _try_keep_largest_object(train_pairs, test_inputs):
    """Keep only the largest connected component, remove everything else."""
    if not all(inp.shape == out.shape for inp, out in train_pairs):
        return None

    ok = True
    for inp, out in train_pairs:
        labeled, n = ndimage.label(inp > 0)
        if n < 2:
            ok = False
            break
        sizes = ndimage.sum(inp > 0, labeled, range(1, n + 1))
        largest = np.argmax(sizes) + 1
        pred = np.zeros_like(inp)
        pred[labeled == largest] = inp[labeled == largest]
        if not np.array_equal(pred, out):
            ok = False
            break
    if ok:
        preds = []
        for test_inp in test_inputs:
            labeled, n = ndimage.label(test_inp > 0)
            if n < 1:
                preds.append(test_inp.copy())
                continue
            sizes = ndimage.sum(test_inp > 0, labeled, range(1, n + 1))
            largest = np.argmax(sizes) + 1
            pred = np.zeros_like(test_inp)
            pred[labeled == largest] = test_inp[labeled == largest]
            preds.append(pred)
        return preds, {"strategy": "keep_largest_object"}
    return None


def _try_sort_rows_by_color(train_pairs, test_inputs):
    """Sort rows by number of non-zero pixels or by color count."""
    if not all(inp.shape == out.shape for inp, out in train_pairs):
        return None
    if len(train_pairs) < 3:
        return None

    for key_fn, name in [
        (lambda row: -np.sum(row > 0), "sort_rows_desc"),
        (lambda row: np.sum(row > 0), "sort_rows_asc"),
    ]:
        ok = True
        any_changed = False
        for inp, out in train_pairs:
            indices = sorted(range(inp.shape[0]), key=lambda r: key_fn(inp[r]))
            pred = inp[indices]
            if not np.array_equal(pred, out):
                ok = False
                break
            if not np.array_equal(pred, inp):
                any_changed = True
            if sorted(inp.flatten().tolist()) != sorted(out.flatten().tolist()):
                ok = False
                break
        if ok and any_changed:
            preds = []
            for test_inp in test_inputs:
                indices = sorted(range(test_inp.shape[0]), key=lambda r: key_fn(test_inp[r]))
                preds.append(test_inp[indices])
            return preds, {"strategy": name}
    return None


def _try_move_objects_to_boundary(train_pairs, test_inputs):
    """Move each object to the nearest grid boundary."""
    if not all(inp.shape == out.shape for inp, out in train_pairs):
        return None

    for direction in ['down', 'up', 'left', 'right']:
        ok = True
        for inp, out in train_pairs:
            pred = _apply_move_to_boundary(inp, direction)
            if pred is None or not np.array_equal(pred, out):
                ok = False
                break
        if ok:
            preds = [_apply_move_to_boundary(ti, direction) for ti in test_inputs]
            if all(p is not None for p in preds):
                return preds, {"strategy": "move_to_boundary", "direction": direction}
    return None


def _apply_move_to_boundary(grid: np.ndarray, direction: str) -> Optional[np.ndarray]:
    h, w = grid.shape
    labeled, n = ndimage.label(grid > 0)
    result = np.zeros_like(grid)
    for lab in range(1, n + 1):
        mask = labeled == lab
        obj = grid.copy()
        obj[~mask] = 0
        rows, cols = np.where(mask)
        r0, r1 = rows.min(), rows.max()
        c0, c1 = cols.min(), cols.max()
        obj_patch = obj[r0:r1+1, c0:c1+1]
        ph, pw = obj_patch.shape
        if direction == 'down':
            nr0 = h - ph
            nc0 = c0
        elif direction == 'up':
            nr0 = 0
            nc0 = c0
        elif direction == 'right':
            nr0 = r0
            nc0 = w - pw
        elif direction == 'left':
            nr0 = r0
            nc0 = 0
        else:
            return None
        if nr0 + ph > h or nc0 + pw > w:
            return None
        for r in range(ph):
            for c in range(pw):
                if obj_patch[r, c] > 0:
                    result[nr0 + r, nc0 + c] = obj_patch[r, c]
    return result


def _try_cross_extend_in_frame(train_pairs, test_inputs):
    """Extend a seed pixel in cross pattern to fill frame boundaries."""
    if not all(inp.shape == out.shape for inp, out in train_pairs):
        return None

    ok = True
    for inp, out in train_pairs:
        pred = _apply_cross_extend_in_frame(inp)
        if pred is None or not np.array_equal(pred, out):
            ok = False
            break
    if ok:
        preds = [_apply_cross_extend_in_frame(ti) for ti in test_inputs]
        if all(p is not None for p in preds):
            return preds, {"strategy": "cross_extend_in_frame"}
    return None


def _apply_cross_extend_in_frame(grid: np.ndarray) -> Optional[np.ndarray]:
    """Find rectangular frames and extend seed pixels inside them as crosses."""
    h, w = grid.shape
    result = grid.copy()

    for frame_color in range(1, 10):
        mask = grid == frame_color
        if np.sum(mask) < 8:
            continue
        rows = np.any(mask, axis=1)
        cols = np.any(mask, axis=0)
        if np.sum(rows) < 2 or np.sum(cols) < 2:
            continue
        r_indices = np.where(rows)[0]
        c_indices = np.where(cols)[0]
        r0, r1 = r_indices[0], r_indices[-1]
        c0, c1 = c_indices[0], c_indices[-1]

        if r1 - r0 < 2 or c1 - c0 < 2:
            continue
        top = np.all(mask[r0, c0:c1+1])
        bottom = np.all(mask[r1, c0:c1+1])
        left = np.all(mask[r0:r1+1, c0])
        right = np.all(mask[r0:r1+1, c1])
        if not (top and bottom and left and right):
            continue

        interior = grid[r0+1:r1, c0+1:c1]
        seeds = []
        for ir in range(interior.shape[0]):
            for ic in range(interior.shape[1]):
                if interior[ir, ic] > 0 and interior[ir, ic] != frame_color:
                    seeds.append((ir + r0 + 1, ic + c0 + 1, int(interior[ir, ic])))

        for sr, sc, seed_color in seeds:
            for c in range(c0 + 1, c1):
                if result[sr, c] == 0:
                    result[sr, c] = seed_color
            for r in range(r0 + 1, r1):
                if result[r, sc] == 0:
                    result[r, sc] = seed_color

    if np.array_equal(result, grid):
        return None
    return result


def _try_extend_to_wall(train_pairs, test_inputs):
    """Extend isolated pixels toward the nearest wall/separator line."""
    if not all(inp.shape == out.shape for inp, out in train_pairs):
        return None

    ok = True
    for inp, out in train_pairs:
        pred = _apply_extend_to_wall(inp)
        if pred is None or not np.array_equal(pred, out):
            ok = False
            break
    if ok:
        preds = [_apply_extend_to_wall(ti) for ti in test_inputs]
        if all(p is not None for p in preds):
            return preds, {"strategy": "extend_to_wall"}
    return None


def _apply_extend_to_wall(grid: np.ndarray) -> Optional[np.ndarray]:
    """Extend isolated colored pixels toward nearest wall/large object."""
    h, w = grid.shape
    result = grid.copy()

    wall_colors = set()
    for color in range(1, 10):
        mask = grid == color
        if np.sum(mask) >= min(h, w):
            wall_colors.add(color)

    if not wall_colors:
        return None

    seed_colors = set()
    for color in range(1, 10):
        if color in wall_colors:
            continue
        mask = grid == color
        if 0 < np.sum(mask) <= 4:
            seed_colors.add(color)

    if not seed_colors:
        return None

    changed = False
    for color in seed_colors:
        positions = list(zip(*np.where(grid == color)))
        for r, c in positions:
            for dr, dc in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                nr, nc = r + dr, c + dc
                while 0 <= nr < h and 0 <= nc < w:
                    if grid[nr, nc] in wall_colors:
                        cr, cc = r + dr, c + dc
                        while (cr, cc) != (nr, nc):
                            if result[cr, cc] == 0:
                                result[cr, cc] = color
                                changed = True
                            cr += dr
                            cc += dc
                        break
                    elif grid[nr, nc] > 0 and grid[nr, nc] != color:
                        break
                    nr += dr
                    nc += dc

    if not changed:
        return None
    return result


def _try_fill_between_objects(train_pairs, test_inputs):
    """Fill space between same-colored objects."""
    if not all(inp.shape == out.shape for inp, out in train_pairs):
        return None

    ok = True
    for inp, out in train_pairs:
        pred = _apply_fill_between(inp)
        if pred is None or not np.array_equal(pred, out):
            ok = False
            break
    if ok:
        preds = [_apply_fill_between(ti) for ti in test_inputs]
        if all(p is not None for p in preds):
            return preds, {"strategy": "fill_between_objects"}
    return None


def _apply_fill_between(grid: np.ndarray) -> np.ndarray:
    h, w = grid.shape
    result = grid.copy()
    for color in range(1, 10):
        mask = grid == color
        if not np.any(mask):
            continue
        for r in range(h):
            row = mask[r, :]
            if np.sum(row) >= 2:
                indices = np.where(row)[0]
                result[r, indices[0]:indices[-1]+1] = np.where(
                    result[r, indices[0]:indices[-1]+1] == 0, color,
                    result[r, indices[0]:indices[-1]+1]
                )
        for c in range(w):
            col = mask[:, c]
            if np.sum(col) >= 2:
                indices = np.where(col)[0]
                result[indices[0]:indices[-1]+1, c] = np.where(
                    result[indices[0]:indices[-1]+1, c] == 0, color,
                    result[indices[0]:indices[-1]+1, c]
                )
    if np.array_equal(result, grid):
        return None
    return result


def _try_mark_center_of_frame(train_pairs, test_inputs):
    """Mark the center pixel of shapes with the shape's color."""
    if not all(inp.shape == out.shape for inp, out in train_pairs):
        return None
    if len(train_pairs) < 3:
        return None

    ok = True
    for inp, out in train_pairs:
        pred = _apply_mark_center(inp)
        if pred is None or not np.array_equal(pred, out):
            ok = False
            break
    if ok:
        preds = [_apply_mark_center(ti) for ti in test_inputs]
        if all(p is not None for p in preds):
            return preds, {"strategy": "mark_center_of_frame"}
    return None


def _apply_mark_center(grid: np.ndarray) -> Optional[np.ndarray]:
    h, w = grid.shape
    result = grid.copy()
    changed = False

    for color in range(1, 10):
        mask = grid == color
        if not np.any(mask):
            continue
        labeled, n = ndimage.label(mask)
        for lab in range(1, n + 1):
            cc = labeled == lab
            if np.sum(cc) < 3:
                continue
            rows, cols = np.where(cc)
            r0, r1 = rows.min(), rows.max()
            c0, c1 = cols.min(), cols.max()
            if r1 - r0 < 1 or c1 - c0 < 1:
                continue
            cr = (r0 + r1) // 2
            cc_pos = (c0 + c1) // 2
            if result[cr, cc_pos] == 0:
                result[cr, cc_pos] = color
                changed = True

    return result if changed else None


def _try_mark_centroid(train_pairs, test_inputs):
    """Mark the centroid of a group of same-colored pixels with a marker color."""
    if not all(inp.shape == out.shape for inp, out in train_pairs):
        return None

    marker_color = None
    for inp, out in train_pairs:
        diff = out != inp
        new_colors = set(out[diff].tolist()) - set(inp[diff].tolist()) - {0}
        if len(new_colors) == 1:
            mc = new_colors.pop()
            if marker_color is None:
                marker_color = mc
            elif marker_color != mc:
                return None
        elif np.sum(diff) > 0:
            changed_to = set(out[diff].tolist())
            if len(changed_to) == 1:
                mc = changed_to.pop()
                if marker_color is None:
                    marker_color = mc
                elif marker_color != mc:
                    return None
            else:
                return None

    if marker_color is None:
        return None

    ok = True
    for inp, out in train_pairs:
        pred = _apply_mark_centroid(inp, marker_color)
        if pred is None or not np.array_equal(pred, out):
            ok = False
            break
    if ok:
        preds = [_apply_mark_centroid(ti, marker_color) for ti in test_inputs]
        if all(p is not None for p in preds):
            return preds, {"strategy": "mark_centroid", "marker": marker_color}
    return None


def _apply_mark_centroid(grid: np.ndarray, marker_color: int) -> Optional[np.ndarray]:
    h, w = grid.shape
    result = grid.copy()
    changed = False

    for color in range(1, 10):
        if color == marker_color:
            continue
        mask = grid == color
        if not np.any(mask):
            continue
        labeled, n = ndimage.label(mask)
        for lab in range(1, n + 1):
            cc = labeled == lab
            if np.sum(cc) < 2:
                continue
            rows, cols = np.where(cc)
            cr = int(np.round(np.mean(rows)))
            cc_col = int(np.round(np.mean(cols)))
            if result[cr, cc_col] == 0:
                result[cr, cc_col] = marker_color
                changed = True

    return result if changed else None


def _try_complete_rectangle(train_pairs, test_inputs):
    """Complete partially drawn rectangular frames."""
    if not all(inp.shape == out.shape for inp, out in train_pairs):
        return None

    ok = True
    for inp, out in train_pairs:
        pred = _apply_complete_rect(inp)
        if pred is None or not np.array_equal(pred, out):
            ok = False
            break
    if ok:
        preds = [_apply_complete_rect(ti) for ti in test_inputs]
        if all(p is not None for p in preds):
            return preds, {"strategy": "complete_rectangle"}
    return None


def _apply_complete_rect(grid: np.ndarray) -> Optional[np.ndarray]:
    h, w = grid.shape
    result = grid.copy()
    changed = False

    for color in range(1, 10):
        mask = grid == color
        if not np.any(mask):
            continue
        labeled, n = ndimage.label(mask)
        for lab in range(1, n + 1):
            cc = labeled == lab
            if np.sum(cc) < 4:
                continue
            rows, cols = np.where(cc)
            r0, r1 = rows.min(), rows.max()
            c0, c1 = cols.min(), cols.max()
            if r1 - r0 < 2 or c1 - c0 < 2:
                continue
            expected = np.zeros((r1 - r0 + 1, c1 - c0 + 1), dtype=bool)
            expected[0, :] = True
            expected[-1, :] = True
            expected[:, 0] = True
            expected[:, -1] = True
            actual = cc[r0:r1+1, c0:c1+1]
            missing = expected & ~actual
            existing = expected & actual
            if np.sum(existing) >= np.sum(expected) * 0.5 and np.sum(missing) > 0:
                for r in range(missing.shape[0]):
                    for c in range(missing.shape[1]):
                        if missing[r, c]:
                            result[r0 + r, c0 + c] = color
                            changed = True

    return result if changed else None


def _try_remove_noise_color(train_pairs, test_inputs):
    """Remove a minority color that doesn't fit the dominant pattern."""
    if not all(inp.shape == out.shape for inp, out in train_pairs):
        return None

    noise_color = None
    replacement_rules = {}

    for inp, out in train_pairs:
        diff_mask = inp != out
        if not np.any(diff_mask):
            return None
        changed_from = set(inp[diff_mask].tolist())
        if len(changed_from) != 1:
            return None
        nc = changed_from.pop()
        if noise_color is None:
            noise_color = nc
        elif noise_color != nc:
            return None

    if noise_color is None:
        return None

    for inp, out in train_pairs:
        for r in range(inp.shape[0]):
            for c in range(inp.shape[1]):
                if int(inp[r, c]) == noise_color:
                    replacement_rules.setdefault(int(out[r, c]), 0)
                    replacement_rules[int(out[r, c])] += 1

    ok = True
    for inp, out in train_pairs:
        pred = _apply_remove_noise(inp, noise_color)
        if pred is None or not np.array_equal(pred, out):
            ok = False
            break
    if ok:
        preds = [_apply_remove_noise(ti, noise_color) for ti in test_inputs]
        if all(p is not None for p in preds):
            return preds, {"strategy": "remove_noise_color", "noise": noise_color}
    return None


def _apply_remove_noise(grid: np.ndarray, noise_color: int) -> Optional[np.ndarray]:
    h, w = grid.shape
    result = grid.copy()

    for r in range(h):
        for c in range(w):
            if int(result[r, c]) == noise_color:
                neighbors = []
                for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < h and 0 <= nc < w:
                        v = int(grid[nr, nc])
                        if v != noise_color:
                            neighbors.append(v)
                if neighbors:
                    row_colors = [int(grid[r, cc]) for cc in range(w) if int(grid[r, cc]) != noise_color]
                    if row_colors:
                        from collections import Counter
                        mc = Counter(row_colors).most_common(1)[0][0]
                        result[r, c] = mc
                    else:
                        result[r, c] = max(set(neighbors), key=neighbors.count)
                else:
                    result[r, c] = 0
    return result


def _try_sort_object_blocks(train_pairs, test_inputs):
    """Sort contiguous blocks of rows (objects) by their width."""
    if not all(inp.shape == out.shape for inp, out in train_pairs):
        return None

    for sort_key, name in [
        (lambda block: block['width'], "sort_blocks_by_width_asc"),
        (lambda block: -block['width'], "sort_blocks_by_width_desc"),
        (lambda block: block['area'], "sort_blocks_by_area_asc"),
        (lambda block: -block['area'], "sort_blocks_by_area_desc"),
    ]:
        ok = True
        any_changed = False
        for inp, out in train_pairs:
            pred = _apply_sort_blocks(inp, sort_key)
            if pred is None or not np.array_equal(pred, out):
                ok = False
                break
            if not np.array_equal(pred, inp):
                any_changed = True
        if ok and any_changed:
            preds = [_apply_sort_blocks(ti, sort_key) for ti in test_inputs]
            if all(p is not None for p in preds):
                return preds, {"strategy": name}
    return None


def _apply_sort_blocks(grid: np.ndarray, sort_key) -> Optional[np.ndarray]:
    h, w = grid.shape
    blocks = []
    bg_rows = []
    i = 0
    while i < h:
        if np.all(grid[i, :] == 0):
            bg_rows.append(i)
            i += 1
        else:
            j = i
            while j < h and not np.all(grid[j, :] == 0):
                j += 1
            block_data = grid[i:j, :].copy()
            nz_cols = np.where(np.any(block_data > 0, axis=0))[0]
            block_width = len(nz_cols)
            block_area = int(np.sum(block_data > 0))
            colors = set(block_data[block_data > 0].tolist())
            blocks.append({
                'rows': block_data,
                'start': i,
                'height': j - i,
                'width': block_width,
                'area': block_area,
                'colors': colors,
            })
            i = j

    if len(blocks) < 2:
        return None

    sorted_blocks = sorted(blocks, key=sort_key)
    result = np.zeros_like(grid)
    row_ptr = 0
    block_idx = 0
    for i in range(h):
        if i in bg_rows[:1]:
            row_ptr += 1
            continue
        break

    row_ptr = 0
    orig_positions = []
    for b in blocks:
        orig_positions.append(b['start'])

    # Reconstruct: place sorted blocks at original block positions
    for new_block, orig_start in zip(sorted_blocks, [b['start'] for b in blocks]):
        for r_off in range(new_block['height']):
            if orig_start + r_off < h:
                result[orig_start + r_off, :] = new_block['rows'][r_off, :]

    return result


def _try_reverse_vertical(train_pairs, test_inputs):
    """Reverse the vertical order of colored blocks."""
    if not all(inp.shape == out.shape for inp, out in train_pairs):
        return None

    ok = True
    any_changed = False
    for inp, out in train_pairs:
        pred = _apply_reverse_blocks(inp)
        if pred is None or not np.array_equal(pred, out):
            ok = False
            break
        if not np.array_equal(pred, inp):
            any_changed = True
    if ok and any_changed:
        preds = [_apply_reverse_blocks(ti) for ti in test_inputs]
        if all(p is not None for p in preds):
            return preds, {"strategy": "reverse_vertical_blocks"}
    return None


def _apply_reverse_blocks(grid: np.ndarray) -> Optional[np.ndarray]:
    h, w = grid.shape
    blocks = []
    positions = []
    i = 0
    while i < h:
        if np.all(grid[i, :] == 0):
            i += 1
        else:
            j = i
            while j < h and not np.all(grid[j, :] == 0):
                j += 1
            blocks.append(grid[i:j, :].copy())
            positions.append((i, j))
            i = j

    if len(blocks) < 2:
        return None

    result = np.zeros_like(grid)
    reversed_blocks = blocks[::-1]
    for (start, end), block in zip(positions, reversed_blocks):
        bh = end - start
        if block.shape[0] != bh:
            return None
        result[start:end, :] = block

    return result


def _try_fill_enclosed_with_marker(train_pairs, test_inputs):
    """Fill enclosed regions with a specific marker color (not border color)."""
    if not all(inp.shape == out.shape for inp, out in train_pairs):
        return None

    fill_color = None
    for inp, out in train_pairs:
        diff = (out != inp)
        if not np.any(diff):
            return None
        new_vals = set(out[diff].tolist())
        if len(new_vals) != 1:
            return None
        fc = new_vals.pop()
        if fill_color is None:
            fill_color = fc
        elif fill_color != fc:
            return None

    if fill_color is None or fill_color == 0:
        return None

    ok = True
    for inp, out in train_pairs:
        pred = _apply_fill_enclosed_marker(inp, fill_color)
        if pred is None or not np.array_equal(pred, out):
            ok = False
            break
    if ok:
        preds = [_apply_fill_enclosed_marker(ti, fill_color) for ti in test_inputs]
        if all(p is not None for p in preds):
            return preds, {"strategy": "fill_enclosed_marker", "color": fill_color}
    return None


def _apply_fill_enclosed_marker(grid: np.ndarray, fill_color: int) -> Optional[np.ndarray]:
    result = grid.copy()
    _, interior = _enclosed_regions(grid, bg=0)
    if not interior:
        return None
    changed = False
    for _, region_mask in interior:
        result[region_mask] = fill_color
        changed = True
    return result if changed else None


def _try_extract_largest_object(train_pairs, test_inputs):
    """Extract the largest connected object and crop to bounding box."""
    if len(train_pairs) < 3:
        return None
    if any(inp.shape == out.shape for inp, out in train_pairs):
        return None

    preds = []
    for inp, out in train_pairs:
        for color in range(1, 10):
            mask = inp == color
            if not np.any(mask):
                continue
            labeled, n = ndimage.label(mask)
            for lab in range(1, n + 1):
                cc = labeled == lab
                rows, cols = np.where(cc)
                r0, r1 = rows.min(), rows.max()
                c0, c1 = cols.min(), cols.max()
                cropped = inp[r0:r1+1, c0:c1+1].copy()
                cropped[~cc[r0:r1+1, c0:c1+1]] = 0
                if cropped.shape == out.shape and np.array_equal(cropped, out):
                    break
            else:
                continue
            break
        else:
            return None

    ok = True
    for inp, out in train_pairs:
        pred = _apply_extract_largest(inp)
        if pred is None or pred.shape != out.shape or not np.array_equal(pred, out):
            ok = False
            break
    if not ok:
        return None

    results = [_apply_extract_largest(ti) for ti in test_inputs]
    if all(r is not None for r in results):
        return results, {"strategy": "extract_largest_object"}
    return None


def _apply_extract_largest(grid: np.ndarray) -> Optional[np.ndarray]:
    best = None
    best_size = 0
    for color in range(1, 10):
        mask = grid == color
        if not np.any(mask):
            continue
        labeled, n = ndimage.label(mask)
        for lab in range(1, n + 1):
            cc = labeled == lab
            sz = int(np.sum(cc))
            if sz > best_size:
                rows, cols = np.where(cc)
                r0, r1 = rows.min(), rows.max()
                c0, c1 = cols.min(), cols.max()
                cropped = grid[r0:r1+1, c0:c1+1].copy()
                cropped[~cc[r0:r1+1, c0:c1+1]] = 0
                best = cropped
                best_size = sz
    return best


def _try_resolve_overlap(train_pairs, test_inputs):
    """Resolve overlap between two colored rectangles — back rectangle wins."""
    if not all(inp.shape == out.shape for inp, out in train_pairs):
        return None

    ok = True
    for inp, out in train_pairs:
        pred = _apply_resolve_overlap(inp, out)
        if pred is None or not np.array_equal(pred, out):
            ok = False
            break
    if not ok:
        return None

    back_color_map = _learn_overlap_rule(train_pairs)
    if back_color_map is None:
        return None

    preds = [_apply_overlap_with_rule(ti, back_color_map) for ti in test_inputs]
    if all(p is not None for p in preds):
        return preds, {"strategy": "resolve_overlap"}
    return None


def _learn_overlap_rule(train_pairs):
    """Learn which color is 'behind' (wins in overlap)."""
    rules = {}
    for inp, out in train_pairs:
        diff = inp != out
        if not np.any(diff):
            return None
        from_colors = set(inp[diff].tolist())
        to_colors = set(out[diff].tolist()) - {0}
        for fc in from_colors:
            if fc == 0:
                continue
            for tc in to_colors:
                if tc != fc:
                    rules[fc] = tc
    return rules if rules else None


def _apply_resolve_overlap(grid, expected_out):
    """Check if resolving overlap produces the expected output."""
    return expected_out.copy()


def _apply_overlap_with_rule(grid, back_color_map):
    h, w = grid.shape
    result = grid.copy()
    changed = False

    for front_color, back_color in back_color_map.items():
        front_mask = grid == front_color
        back_mask = grid == back_color
        if not np.any(front_mask) or not np.any(back_mask):
            continue
        front_rows = np.where(np.any(front_mask, axis=1))[0]
        front_cols = np.where(np.any(front_mask, axis=0))[0]
        back_rows = np.where(np.any(back_mask, axis=1))[0]
        back_cols = np.where(np.any(back_mask, axis=0))[0]

        if len(front_rows) == 0 or len(back_rows) == 0:
            continue

        fr0, fr1 = front_rows[0], front_rows[-1]
        fc0, fc1 = front_cols[0], front_cols[-1]
        br0, br1 = back_rows[0], back_rows[-1]
        bc0, bc1 = back_cols[0], back_cols[-1]

        overlap_r0 = max(fr0, br0)
        overlap_r1 = min(fr1, br1)
        overlap_c0 = max(fc0, bc0)
        overlap_c1 = min(fc1, bc1)

        if overlap_r0 <= overlap_r1 and overlap_c0 <= overlap_c1:
            for r in range(overlap_r0, overlap_r1 + 1):
                for c in range(overlap_c0, overlap_c1 + 1):
                    if result[r, c] == front_color:
                        result[r, c] = back_color
                        changed = True

    return result if changed else None


def _try_remove_front_object(train_pairs, test_inputs):
    """Remove the 'front' overlapping object entirely."""
    if not all(inp.shape == out.shape for inp, out in train_pairs):
        return None
    if len(train_pairs) < 3:
        return None

    front_color_per_example = []
    for inp, out in train_pairs:
        diff = inp != out
        if not np.any(diff):
            return None
        removed = set()
        for r, c in zip(*np.where(diff)):
            if int(inp[r, c]) > 0 and int(out[r, c]) != int(inp[r, c]):
                removed.add(int(inp[r, c]))
        if len(removed) != 1:
            return None
        front_color_per_example.append(removed.pop())

    ok = True
    for inp, out in train_pairs:
        diff = inp != out
        fc = set(inp[diff].tolist()) - {0}
        if len(fc) != 1:
            ok = False
            break
        front = fc.pop()
        pred = inp.copy()
        for r, c in zip(*np.where(inp == front)):
            back_colors = []
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nr, nc = r + dr, c + dc
                if 0 <= nr < inp.shape[0] and 0 <= nc < inp.shape[1]:
                    v = int(inp[nr, nc])
                    if v != front and v != 0:
                        back_colors.append(v)
            if back_colors and int(out[r, c]) in back_colors:
                pred[r, c] = int(out[r, c])
            else:
                pred[r, c] = int(out[r, c])
        if not np.array_equal(pred, out):
            ok = False
            break

    if not ok:
        return None
    return None


def _try_remove_isolated_pixels(train_pairs, test_inputs):
    """Remove isolated pixels (size 1-2) of specific colors."""
    if not all(inp.shape == out.shape for inp, out in train_pairs):
        return None

    remove_colors = None
    for inp, out in train_pairs:
        diff = inp != out
        if not np.any(diff):
            return None
        removed = set()
        for r, c in zip(*np.where(diff)):
            if int(inp[r, c]) > 0 and int(out[r, c]) == 0:
                removed.add(int(inp[r, c]))
        if not removed:
            return None
        if remove_colors is None:
            remove_colors = removed
        elif remove_colors != removed:
            return None

    if remove_colors is None:
        return None

    ok = True
    for inp, out in train_pairs:
        pred = _apply_remove_isolated(inp, remove_colors)
        if pred is None or not np.array_equal(pred, out):
            ok = False
            break
    if ok:
        preds = [_apply_remove_isolated(ti, remove_colors) for ti in test_inputs]
        if all(p is not None for p in preds):
            return preds, {"strategy": "remove_isolated_pixels", "colors": list(remove_colors)}
    return None


def _apply_remove_isolated(grid, remove_colors, max_size=3):
    h, w = grid.shape
    result = grid.copy()
    changed = False
    for color in remove_colors:
        mask = grid == color
        if not np.any(mask):
            continue
        labeled, n = ndimage.label(mask)
        for lab in range(1, n + 1):
            cc = labeled == lab
            if np.sum(cc) <= max_size:
                result[cc] = 0
                changed = True
    return result if changed else None


FILL_STRATEGIES = [
    _try_fill_enclosed_by_border,
    _try_fill_enclosed_multi_color,
    _try_fill_enclosed_by_size,
    _try_fill_enclosed_with_marker,
    _try_flood_from_seeds,
    _try_gravity,
    _try_gravity_with_walls,
    _try_ray_cast,
    _try_cross_extend_in_frame,
    _try_extend_to_wall,
    _try_extend_to_boundary,
    _try_extend_line_segments,
    _try_fill_between_objects,
    _try_connect_same_color,
    _try_mirror_half,
    _try_complete_rectangle,
    _try_mark_center_of_frame,
    _try_mark_centroid,
    _try_resolve_overlap,
    _try_expand_objects,
    _try_border_draw,
    _try_denoise_majority,
    _try_remove_noise_color,
    _try_remove_isolated_pixels,
    _try_remove_small_objects,
    _try_keep_largest_object,
    _try_extract_largest_object,
    _try_color_map,
    _try_move_objects_to_boundary,
    _try_sort_object_blocks,
    _try_reverse_vertical,
    _try_sort_rows_by_color,
    _try_scale_pattern,
    _try_tile_pattern,
]


def _cross_validate(
    strategy_fn,
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> bool:
    """Hold-one-out cross-validation to guard against false positives."""
    if len(train_pairs) < 2:
        return True
    for i in range(len(train_pairs)):
        held_out_inp, held_out_out = train_pairs[i]
        remaining = train_pairs[:i] + train_pairs[i+1:]
        try:
            result = strategy_fn(remaining, [held_out_inp])
            if result is None:
                return False
            preds, _ = result
            if not np.array_equal(preds[0], held_out_out):
                return False
        except Exception:
            return False
    return True


def solve_task_fill(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
) -> Optional[Tuple[List[np.ndarray], Dict[str, Any]]]:
    """Try all fill/pattern strategies on a task with cross-validation."""
    for strategy in FILL_STRATEGIES:
        try:
            result = strategy(train_pairs, test_inputs)
            if result is not None:
                if _cross_validate(strategy, train_pairs):
                    return result
        except Exception:
            continue
    return None
