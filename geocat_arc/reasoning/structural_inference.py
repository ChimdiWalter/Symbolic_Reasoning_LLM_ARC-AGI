"""Structural inference — discovers the structural relationship between input and output.

Instead of hardcoded solvers, this module INFERS the transform by:
1. Computing structural features of input and output
2. Searching for a mapping (rotation, permutation, crop offsets) that explains the data
3. Constructing the transform function from the discovered mapping

The key difference from grid_solvers: nothing here is task-specific.
Everything is discovered from the input/output pairs.
"""
from __future__ import annotations
from collections import Counter
from typing import Callable
import numpy as np
from itertools import permutations


def _bg(grid: np.ndarray) -> int:
    return int(Counter(grid.flatten().tolist()).most_common(1)[0][0])


def infer_structural_transform(
    train_pairs: list[tuple[np.ndarray, np.ndarray]],
) -> Callable | None:
    """Master function: tries to infer ANY structural transform from data."""
    strategies = [
        _infer_numpy_transform,
        _infer_color_mapping,
        _infer_shape_relationship,
        _infer_positional_crop,
        _infer_cell_value_from_structure,
    ]

    for strategy in strategies:
        fn = strategy(train_pairs)
        if fn is not None:
            return fn
    return None


def _infer_numpy_transform(
    train_pairs: list[tuple[np.ndarray, np.ndarray]],
) -> Callable | None:
    """Discover if output is a standard numpy transform of input."""
    transforms = {
        "flipud": lambda g: np.flipud(g),
        "fliplr": lambda g: np.fliplr(g),
        "rot90_1": lambda g: np.rot90(g, 1),
        "rot90_2": lambda g: np.rot90(g, 2),
        "rot90_3": lambda g: np.rot90(g, 3),
        "transpose": lambda g: g.T.copy(),
    }
    for name, tfn in transforms.items():
        if all(np.array_equal(tfn(inp), out) for inp, out in train_pairs):
            return tfn

    for s in [2, 3, 4, 5]:
        if all(
            np.array_equal(np.repeat(np.repeat(inp, s, axis=0), s, axis=1), out)
            for inp, out in train_pairs
        ):
            scale = s
            return lambda g, sc=scale: np.repeat(np.repeat(g, sc, axis=0), sc, axis=1)

        if all(
            inp.shape[0] == out.shape[0] * s and inp.shape[1] == out.shape[1] * s
            and np.array_equal(inp[::s, ::s], out)
            for inp, out in train_pairs
        ):
            scale = s
            return lambda g, sc=scale: g[::sc, ::sc].copy()

    rh, rw = None, None
    for inp, out in train_pairs:
        ih, iw = inp.shape
        oh, ow = out.shape
        if oh % ih != 0 or ow % iw != 0:
            break
        crh, crw = oh // ih, ow // iw
        if rh is None:
            rh, rw = crh, crw
        elif rh != crh or rw != crw:
            rh = None
            break
    else:
        if rh is not None and rh > 0 and rw > 0 and (rh > 1 or rw > 1):
            if all(np.array_equal(np.tile(inp, (rh, rw)), out) for inp, out in train_pairs):
                rr, rc = rh, rw
                return lambda g, r=rr, c=rc: np.tile(g, (r, c))

    return None


def _infer_color_mapping(
    train_pairs: list[tuple[np.ndarray, np.ndarray]],
) -> Callable | None:
    """Discover if output is a color permutation of input."""
    if not all(inp.shape == out.shape for inp, out in train_pairs):
        return None

    mapping: dict[int, set[int]] = {}
    for inp, out in train_pairs:
        for ic, oc in zip(inp.flatten(), out.flatten()):
            ic, oc = int(ic), int(oc)
            if ic not in mapping:
                mapping[ic] = set()
            mapping[ic].add(oc)

    resolved = {}
    for ic, ocs in mapping.items():
        if len(ocs) != 1:
            return None
        resolved[ic] = next(iter(ocs))

    if all(k == v for k, v in resolved.items()):
        return None

    m = dict(resolved)
    return lambda g, mp=m: np.vectorize(lambda x: mp.get(int(x), int(x)))(g)


def _infer_shape_relationship(
    train_pairs: list[tuple[np.ndarray, np.ndarray]],
) -> Callable | None:
    """Discover if output is a half-mirror, quarter, or other shape relationship."""
    if not all(inp.shape == out.shape for inp, out in train_pairs):
        return None

    for axis_name, flipfn in [("h", np.flipud), ("v", np.fliplr)]:
        for source in ["top", "bottom", "left", "right"]:
            matches = True
            for inp, out in train_pairs:
                h, w = inp.shape
                result = inp.copy()
                if source == "top" and axis_name == "h":
                    half = h // 2
                    result[h - half:, :] = flipfn(result[:half, :])
                elif source == "bottom" and axis_name == "h":
                    half = h // 2
                    result[:half, :] = flipfn(result[h - half:, :])
                elif source == "left" and axis_name == "v":
                    half = w // 2
                    result[:, w - half:] = flipfn(result[:, :half])
                elif source == "right" and axis_name == "v":
                    half = w // 2
                    result[:, :half] = flipfn(result[:, w - half:])
                else:
                    matches = False
                    break
                if not np.array_equal(result, out):
                    matches = False
                    break
            if matches:
                an, src = axis_name, source

                def apply_fn(grid, a=an, s=src):
                    h, w = grid.shape
                    result = grid.copy()
                    ff = np.flipud if a == "h" else np.fliplr
                    if s == "top":
                        half = h // 2
                        result[h - half:, :] = ff(result[:half, :])
                    elif s == "bottom":
                        half = h // 2
                        result[:half, :] = ff(result[h - half:, :])
                    elif s == "left":
                        half = w // 2
                        result[:, w - half:] = ff(result[:, :half])
                    elif s == "right":
                        half = w // 2
                        result[:, :half] = ff(result[:, w - half:])
                    return result
                return apply_fn

    return None


def _infer_positional_crop(
    train_pairs: list[tuple[np.ndarray, np.ndarray]],
) -> Callable | None:
    """Discover if output is a crop of input, and find the cropping rule."""
    if all(inp.shape == out.shape for inp, out in train_pairs):
        return None

    offsets = []
    for inp, out in train_pairs:
        oh, ow = out.shape
        ih, iw = inp.shape
        if oh > ih or ow > iw:
            offsets = None
            break
        found = False
        for r in range(ih - oh + 1):
            for c in range(iw - ow + 1):
                if np.array_equal(inp[r:r + oh, c:c + ow], out):
                    offsets.append((r, c, oh, ow))
                    found = True
                    break
            if found:
                break
        if not found:
            offsets = None
            break

    if offsets is None:
        return None

    if len(set((r, c) for r, c, _, _ in offsets)) == 1 and len(set((oh, ow) for _, _, oh, ow in offsets)) == 1:
        r0, c0, h, w = offsets[0]
        return lambda g, rr=r0, cc=c0, hh=h, ww=w: g[rr:rr + hh, cc:cc + ww].copy()

    bgs = []
    for inp, out in train_pairs:
        bg = _bg(inp)
        h, w = inp.shape
        rows = np.any(inp != bg, axis=1)
        cols = np.any(inp != bg, axis=0)
        if not np.any(rows) or not np.any(cols):
            return None
        r0, r1 = np.where(rows)[0][[0, -1]]
        c0, c1 = np.where(cols)[0][[0, -1]]
        cropped = inp[r0:r1 + 1, c0:c1 + 1]
        if np.array_equal(cropped, out):
            bgs.append(bg)
        else:
            return None

    def apply_fn(grid):
        bg = _bg(grid)
        rows = np.any(grid != bg, axis=1)
        cols = np.any(grid != bg, axis=0)
        if not np.any(rows) or not np.any(cols):
            return grid.copy()
        r0, r1 = np.where(rows)[0][[0, -1]]
        c0, c1 = np.where(cols)[0][[0, -1]]
        return grid[r0:r1 + 1, c0:c1 + 1].copy()
    return apply_fn


def _infer_cell_value_from_structure(
    train_pairs: list[tuple[np.ndarray, np.ndarray]],
) -> Callable | None:
    """Discover if output cell values are determined by structural
    relationships in the input (enclosed regions, gravity, etc.)

    This infers these transforms from data rather than hardcoding them.
    """
    from collections import deque

    if not all(inp.shape == out.shape for inp, out in train_pairs):
        return None

    # Check: is the output = input with enclosed background regions filled?
    for fill_strategy in ["constant", "border_color"]:
        matches = True
        learned_fill_color = None

        for inp, out in train_pairs:
            bg = _bg(inp)
            h, w = inp.shape
            reachable = np.zeros((h, w), dtype=bool)
            queue = deque()
            for r in range(h):
                for c in [0, w - 1]:
                    if inp[r, c] == bg:
                        reachable[r, c] = True
                        queue.append((r, c))
            for c in range(w):
                for r in [0, h - 1]:
                    if inp[r, c] == bg and not reachable[r, c]:
                        reachable[r, c] = True
                        queue.append((r, c))
            while queue:
                cr, cc = queue.popleft()
                for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nr, nc = cr + dr, cc + dc
                    if 0 <= nr < h and 0 <= nc < w and not reachable[nr, nc] and inp[nr, nc] == bg:
                        reachable[nr, nc] = True
                        queue.append((nr, nc))

            expected = inp.copy()
            enclosed_cells = []
            for r in range(h):
                for c in range(w):
                    if inp[r, c] == bg and not reachable[r, c]:
                        enclosed_cells.append((r, c))

            if not enclosed_cells:
                matches = False
                break

            if fill_strategy == "constant":
                fill_vals = set(int(out[r, c]) for r, c in enclosed_cells)
                if len(fill_vals) != 1:
                    matches = False
                    break
                fc = next(iter(fill_vals))
                if learned_fill_color is None:
                    learned_fill_color = fc
                elif learned_fill_color != fc:
                    matches = False
                    break
                for r, c in enclosed_cells:
                    expected[r, c] = fc

            elif fill_strategy == "border_color":
                visited_enclosed = np.zeros((h, w), dtype=bool)
                for r, c in enclosed_cells:
                    if visited_enclosed[r, c]:
                        continue
                    region = set()
                    rq = deque([(r, c)])
                    while rq:
                        cr, cc = rq.popleft()
                        if (cr, cc) in region:
                            continue
                        if 0 <= cr < h and 0 <= cc < w and inp[cr, cc] == bg and not reachable[cr, cc] and not visited_enclosed[cr, cc]:
                            region.add((cr, cc))
                            visited_enclosed[cr, cc] = True
                            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                                rq.append((cr + dr, cc + dc))
                    border_colors = Counter()
                    for rr, rc in region:
                        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                            nr, nc = rr + dr, rc + dc
                            if 0 <= nr < h and 0 <= nc < w and (nr, nc) not in region and inp[nr, nc] != bg:
                                border_colors[int(inp[nr, nc])] += 1
                    if not border_colors:
                        matches = False
                        break
                    fc = border_colors.most_common(1)[0][0]
                    for rr, rc in region:
                        expected[rr, rc] = fc

            if not np.array_equal(expected, out):
                matches = False
                break

        if matches:
            if fill_strategy == "constant":
                lfc = learned_fill_color

                def apply_fn(grid, fc=lfc):
                    bg = _bg(grid)
                    h, w = grid.shape
                    reachable = np.zeros((h, w), dtype=bool)
                    queue = deque()
                    for r in range(h):
                        for c in [0, w - 1]:
                            if grid[r, c] == bg:
                                reachable[r, c] = True
                                queue.append((r, c))
                    for c in range(w):
                        for r in [0, h - 1]:
                            if grid[r, c] == bg and not reachable[r, c]:
                                reachable[r, c] = True
                                queue.append((r, c))
                    while queue:
                        cr, cc = queue.popleft()
                        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                            nr, nc = cr + dr, cc + dc
                            if 0 <= nr < h and 0 <= nc < w and not reachable[nr, nc] and grid[nr, nc] == bg:
                                reachable[nr, nc] = True
                                queue.append((nr, nc))
                    result = grid.copy()
                    for r in range(h):
                        for c in range(w):
                            if grid[r, c] == bg and not reachable[r, c]:
                                result[r, c] = fc
                    return result
                return apply_fn

            elif fill_strategy == "border_color":
                def apply_fn(grid):
                    bg = _bg(grid)
                    h, w = grid.shape
                    reachable = np.zeros((h, w), dtype=bool)
                    queue = deque()
                    for r in range(h):
                        for c in [0, w - 1]:
                            if grid[r, c] == bg:
                                reachable[r, c] = True
                                queue.append((r, c))
                    for c in range(w):
                        for r in [0, h - 1]:
                            if grid[r, c] == bg and not reachable[r, c]:
                                reachable[r, c] = True
                                queue.append((r, c))
                    while queue:
                        cr, cc = queue.popleft()
                        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                            nr, nc = cr + dr, cc + dc
                            if 0 <= nr < h and 0 <= nc < w and not reachable[nr, nc] and grid[nr, nc] == bg:
                                reachable[nr, nc] = True
                                queue.append((nr, nc))
                    result = grid.copy()
                    visited = np.zeros((h, w), dtype=bool)
                    for r in range(h):
                        for c in range(w):
                            if grid[r, c] == bg and not reachable[r, c] and not visited[r, c]:
                                region = set()
                                rq = deque([(r, c)])
                                while rq:
                                    cr, cc = rq.popleft()
                                    if (cr, cc) in region:
                                        continue
                                    if 0 <= cr < h and 0 <= cc < w and grid[cr, cc] == bg and not reachable[cr, cc] and not visited[cr, cc]:
                                        region.add((cr, cc))
                                        visited[cr, cc] = True
                                        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                                            rq.append((cr + dr, cc + dc))
                                border_colors = Counter()
                                for rr, rc in region:
                                    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                                        nr, nc = rr + dr, rc + dc
                                        if 0 <= nr < h and 0 <= nc < w and (nr, nc) not in region and grid[nr, nc] != bg:
                                            border_colors[int(grid[nr, nc])] += 1
                                if border_colors:
                                    fc = border_colors.most_common(1)[0][0]
                                    for rr, rc in region:
                                        result[rr, rc] = fc
                    return result
                return apply_fn

    # Check: gravity (non-background cells fall in some direction)
    for direction in ["down", "up", "left", "right"]:
        matches = True
        for inp, out in train_pairs:
            bg = _bg(inp)
            h, w = inp.shape
            result = np.full_like(inp, bg)
            if direction in ("down", "up"):
                for c in range(w):
                    vals = [int(inp[r, c]) for r in range(h) if inp[r, c] != bg]
                    if direction == "down":
                        for i, v in enumerate(reversed(vals)):
                            result[h - 1 - i, c] = v
                    else:
                        for i, v in enumerate(vals):
                            result[i, c] = v
            else:
                for r in range(h):
                    vals = [int(inp[r, c]) for c in range(w) if inp[r, c] != bg]
                    if direction == "right":
                        for i, v in enumerate(reversed(vals)):
                            result[r, w - 1 - i] = v
                    else:
                        for i, v in enumerate(vals):
                            result[r, i] = v
            if not np.array_equal(result, out):
                matches = False
                break
        if matches:
            d = direction

            def apply_fn(grid, dr=d):
                bg = _bg(grid)
                h, w = grid.shape
                result = np.full_like(grid, bg)
                if dr in ("down", "up"):
                    for c in range(w):
                        vals = [int(grid[r, c]) for r in range(h) if grid[r, c] != bg]
                        if dr == "down":
                            for i, v in enumerate(reversed(vals)):
                                result[h - 1 - i, c] = v
                        else:
                            for i, v in enumerate(vals):
                                result[i, c] = v
                else:
                    for r in range(h):
                        vals = [int(grid[r, c]) for c in range(w) if grid[r, c] != bg]
                        if dr == "right":
                            for i, v in enumerate(reversed(vals)):
                                result[r, w - 1 - i] = v
                        else:
                            for i, v in enumerate(vals):
                                result[r, i] = v
                return result
            return apply_fn

    # Check: extract specific colored object (crop to bounding box of a color)
    fn = _infer_extract_object(train_pairs)
    if fn is not None:
        return fn

    # Check: subgrid decomposition + majority vote
    for nr in range(2, 5):
        for nc in range(2, 5):
            if not all(
                inp.shape[0] % nr == 0 and inp.shape[1] % nc == 0
                for inp, _ in train_pairs
            ):
                continue

            ch = train_pairs[0][0].shape[0] // nr
            cw = train_pairs[0][0].shape[1] // nc

            if not all(out.shape == (ch, cw) for _, out in train_pairs):
                continue

            matches = True
            for inp, out in train_pairs:
                sgs = []
                for r in range(nr):
                    for c in range(nc):
                        sgs.append(inp[r * ch:(r + 1) * ch, c * cw:(c + 1) * cw])
                result = np.zeros((ch, cw), dtype=np.int32)
                for rr in range(ch):
                    for cc in range(cw):
                        result[rr, cc] = Counter(int(sg[rr, cc]) for sg in sgs).most_common(1)[0][0]
                if not np.array_equal(result, out):
                    matches = False
                    break

            if matches:
                nnr, nnc = nr, nc

                def apply_fn(grid, r=nnr, c=nnc):
                    ch, cw = grid.shape[0] // r, grid.shape[1] // c
                    sgs = []
                    for rr in range(r):
                        for cc in range(c):
                            sgs.append(grid[rr * ch:(rr + 1) * ch, cc * cw:(cc + 1) * cw])
                    result = np.zeros((ch, cw), dtype=np.int32)
                    for rrr in range(ch):
                        for ccc in range(cw):
                            result[rrr, ccc] = Counter(int(sg[rrr, ccc]) for sg in sgs).most_common(1)[0][0]
                    return result
                return apply_fn

    # Check: subgrid boolean ops (AND/OR/XOR)
    fn = _infer_subgrid_boolean_op(train_pairs)
    if fn is not None:
        return fn

    return None


def _infer_extract_object(
    train_pairs: list[tuple[np.ndarray, np.ndarray]],
) -> Callable | None:
    """Discover if output is the bounding box of a specific colored object."""
    from scipy.ndimage import label as ndlabel

    if all(inp.shape == out.shape for inp, out in train_pairs):
        return None

    for selector in ["unique_color", "smallest", "largest", "specific_color"]:
        colors_to_try = range(10) if selector == "specific_color" else [None]
        for try_color in colors_to_try:
            matches = True
            for inp, out in train_pairs:
                bg = _bg(inp)
                target = _select_and_crop(inp, bg, selector, try_color)
                if target is None or target.shape != out.shape or not np.array_equal(target, out):
                    matches = False
                    break
            if matches:
                sel, tc = selector, try_color
                def apply_fn(grid, s=sel, c=tc):
                    bg = _bg(grid)
                    result = _select_and_crop(grid, bg, s, c)
                    return result if result is not None else grid
                return apply_fn

    return None


def _select_and_crop(grid: np.ndarray, bg: int, selector: str, color: int | None) -> np.ndarray | None:
    """Select an object by criterion and crop to its bounding box."""
    from scipy.ndimage import label as ndlabel

    objects = []
    for c in range(10):
        if c == bg:
            continue
        mask = (grid == c)
        if not np.any(mask):
            continue
        labeled, n = ndlabel(mask)
        for obj_id in range(1, n + 1):
            obj_mask = (labeled == obj_id)
            rows, cols = np.where(obj_mask)
            r0, r1 = int(rows.min()), int(rows.max())
            c0, c1 = int(cols.min()), int(cols.max())
            objects.append({
                "color": c, "size": int(np.sum(obj_mask)),
                "r0": r0, "r1": r1, "c0": c0, "c1": c1,
            })

    if not objects:
        return None

    chosen = None
    if selector == "unique_color":
        color_counts = Counter(o["color"] for o in objects)
        unique = [o for o in objects if color_counts[o["color"]] == 1]
        if len(unique) == 1:
            chosen = unique[0]
    elif selector == "smallest":
        chosen = min(objects, key=lambda o: o["size"])
    elif selector == "largest":
        chosen = max(objects, key=lambda o: o["size"])
    elif selector == "specific_color" and color is not None:
        colored = [o for o in objects if o["color"] == color]
        if len(colored) == 1:
            chosen = colored[0]

    if chosen is None:
        return None

    return grid[chosen["r0"]:chosen["r1"] + 1, chosen["c0"]:chosen["c1"] + 1].copy()


def _infer_subgrid_boolean_op(
    train_pairs: list[tuple[np.ndarray, np.ndarray]],
) -> Callable | None:
    """Discover if output is an AND/OR/XOR of subgrids from input."""
    if all(inp.shape == out.shape for inp, out in train_pairs):
        return None

    for nr in range(2, 5):
        for nc in range(2, 5):
            valid = True
            for inp, out in train_pairs:
                ih, iw = inp.shape
                if ih % nr != 0 or iw % nc != 0:
                    valid = False
                    break
                tch, tcw = ih // nr, iw // nc
                if out.shape != (tch, tcw):
                    valid = False
                    break
            if not valid:
                continue

            for op_name in ["and", "or", "xor"]:
                matches = True
                for inp, out in train_pairs:
                    bg = _bg(inp)
                    tch, tcw = inp.shape[0] // nr, inp.shape[1] // nc
                    sgs = []
                    for r in range(nr):
                        for c in range(nc):
                            sgs.append(inp[r * tch:(r + 1) * tch, c * tcw:(c + 1) * tcw])

                    binary = [(sg != bg).astype(int) for sg in sgs]
                    if op_name == "and":
                        result = binary[0]
                        for b in binary[1:]:
                            result = np.minimum(result, b)
                    elif op_name == "or":
                        result = binary[0]
                        for b in binary[1:]:
                            result = np.maximum(result, b)
                    else:
                        result = binary[0]
                        for b in binary[1:]:
                            result = (result != b).astype(int)

                    out_grid = np.full((tch, tcw), bg, dtype=inp.dtype)
                    for sg in sgs:
                        mask = (sg != bg)
                        out_grid[mask] = sg[mask]
                    out_grid[result == 0] = bg

                    if not np.array_equal(out_grid, out):
                        matches = False
                        break

                if matches:
                    r_nr, r_nc, r_op = nr, nc, op_name

                    def apply_fn(grid, nnr=r_nr, nnc=r_nc, oop=r_op):
                        bg = _bg(grid)
                        tch, tcw = grid.shape[0] // nnr, grid.shape[1] // nnc
                        sgs = []
                        for r in range(nnr):
                            for c in range(nnc):
                                sgs.append(grid[r * tch:(r + 1) * tch, c * tcw:(c + 1) * tcw])
                        binary = [(sg != bg).astype(int) for sg in sgs]
                        if oop == "and":
                            result = binary[0]
                            for b in binary[1:]:
                                result = np.minimum(result, b)
                        elif oop == "or":
                            result = binary[0]
                            for b in binary[1:]:
                                result = np.maximum(result, b)
                        else:
                            result = binary[0]
                            for b in binary[1:]:
                                result = (result != b).astype(int)
                        out_grid = np.full((tch, tcw), bg, dtype=grid.dtype)
                        for sg in sgs:
                            mask = (sg != bg)
                            out_grid[mask] = sg[mask]
                        out_grid[result == 0] = bg
                        return out_grid

                    return apply_fn

    return None
