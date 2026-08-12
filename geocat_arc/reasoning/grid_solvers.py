"""Grid-level solvers for tasks that can't be solved cell-by-cell.

Handles: crop, tile, subgrid operations, fill, gravity, symmetry completion,
color permutation, and object-level transforms.
"""
from __future__ import annotations
from collections import Counter, deque
from typing import Callable
import numpy as np


def _bg_color(grid: np.ndarray) -> int:
    return int(Counter(grid.flatten().tolist()).most_common(1)[0][0])


def try_color_permutation(
    train_pairs: list[tuple[np.ndarray, np.ndarray]],
) -> Callable | None:
    mapping: dict[int, int] = {}
    for inp, out in train_pairs:
        if inp.shape != out.shape:
            return None
        h, w = inp.shape
        for r in range(h):
            for c in range(w):
                ic, oc = int(inp[r, c]), int(out[r, c])
                if ic in mapping:
                    if mapping[ic] != oc:
                        return None
                else:
                    mapping[ic] = oc

    is_identity = all(k == v for k, v in mapping.items())
    if is_identity:
        return None

    for inp, out in train_pairs:
        result = np.vectorize(lambda x: mapping.get(int(x), int(x)))(inp)
        if not np.array_equal(result, out):
            return None

    def apply_fn(grid: np.ndarray) -> np.ndarray:
        return np.vectorize(lambda x: mapping.get(int(x), int(x)))(grid)

    return apply_fn


def try_crop_to_object(
    train_pairs: list[tuple[np.ndarray, np.ndarray]],
) -> Callable | None:
    offsets = []
    for inp, out in train_pairs:
        oh, ow = out.shape
        ih, iw = inp.shape
        if oh > ih or ow > iw:
            return None
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
            return None

    if not offsets:
        return None

    if len(set((r, c) for r, c, _, _ in offsets)) == 1:
        r0, c0, h, w = offsets[0]

        def apply_fn(grid: np.ndarray) -> np.ndarray:
            return grid[r0:r0 + h, c0:c0 + w].copy()
        return apply_fn

    return None


def try_crop_nonbackground(
    train_pairs: list[tuple[np.ndarray, np.ndarray]],
) -> Callable | None:
    for inp, out in train_pairs:
        bg = _bg_color(inp)
        rows = np.any(inp != bg, axis=1)
        cols = np.any(inp != bg, axis=0)
        if not np.any(rows) or not np.any(cols):
            return None
        r0, r1 = np.where(rows)[0][[0, -1]]
        c0, c1 = np.where(cols)[0][[0, -1]]
        cropped = inp[r0:r1 + 1, c0:c1 + 1]
        if not np.array_equal(cropped, out):
            return None

    def apply_fn(grid: np.ndarray) -> np.ndarray:
        bg = _bg_color(grid)
        rows = np.any(grid != bg, axis=1)
        cols = np.any(grid != bg, axis=0)
        if not np.any(rows) or not np.any(cols):
            return grid.copy()
        r0, r1 = np.where(rows)[0][[0, -1]]
        c0, c1 = np.where(cols)[0][[0, -1]]
        return grid[r0:r1 + 1, c0:c1 + 1].copy()

    return apply_fn


def try_tile(
    train_pairs: list[tuple[np.ndarray, np.ndarray]],
) -> Callable | None:
    factors = []
    for inp, out in train_pairs:
        ih, iw = inp.shape
        oh, ow = out.shape
        if oh % ih != 0 or ow % iw != 0:
            return None
        reps_h, reps_w = oh // ih, ow // iw
        for r in range(0, oh, ih):
            for c in range(0, ow, iw):
                if not np.array_equal(out[r:r + ih, c:c + iw], inp):
                    return None
        factors.append((reps_h, reps_w))

    if len(set(factors)) == 1:
        rh, rw = factors[0]

        def apply_fn(grid: np.ndarray) -> np.ndarray:
            return np.tile(grid, (rh, rw))
        return apply_fn

    return None


def try_fill_enclosed(
    train_pairs: list[tuple[np.ndarray, np.ndarray]],
) -> Callable | None:
    fill_colors = []

    for inp, out in train_pairs:
        if inp.shape != out.shape:
            return None
        bg = _bg_color(inp)
        h, w = inp.shape

        reachable = np.zeros((h, w), dtype=bool)
        queue = deque()
        for r in range(h):
            for c in [0, w - 1]:
                if inp[r, c] == bg and not reachable[r, c]:
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

        enclosed = set()
        for r in range(h):
            for c in range(w):
                if inp[r, c] == bg and not reachable[r, c]:
                    enclosed.add((r, c))

        if not enclosed:
            return None

        expected = inp.copy()
        fc_set = set()
        for r, c in enclosed:
            fc_set.add(int(out[r, c]))
            expected[r, c] = out[r, c]
        if not np.array_equal(expected, out):
            return None
        if len(fc_set) == 1:
            fill_colors.append(next(iter(fc_set)))
        else:
            return None

    if len(set(fill_colors)) == 1:
        fc = fill_colors[0]

        def apply_fn(grid: np.ndarray) -> np.ndarray:
            bg = _bg_color(grid)
            h, w = grid.shape
            reachable = np.zeros((h, w), dtype=bool)
            queue = deque()
            for r in range(h):
                for c in [0, w - 1]:
                    if grid[r, c] == bg and not reachable[r, c]:
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

    return None


def try_fill_enclosed_adaptive(
    train_pairs: list[tuple[np.ndarray, np.ndarray]],
) -> Callable | None:
    for inp, out in train_pairs:
        if inp.shape != out.shape:
            return None
        bg = _bg_color(inp)
        h, w = inp.shape

        reachable = np.zeros((h, w), dtype=bool)
        queue = deque()
        for r in range(h):
            for c in [0, w - 1]:
                if inp[r, c] == bg and not reachable[r, c]:
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

        regions = []
        visited = np.zeros((h, w), dtype=bool)
        for r in range(h):
            for c in range(w):
                if inp[r, c] == bg and not reachable[r, c] and not visited[r, c]:
                    region = set()
                    rq = deque([(r, c)])
                    while rq:
                        cr, cc = rq.popleft()
                        if (cr, cc) in region:
                            continue
                        if 0 <= cr < h and 0 <= cc < w and inp[cr, cc] == bg and not reachable[cr, cc] and not visited[cr, cc]:
                            region.add((cr, cc))
                            visited[cr, cc] = True
                            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                                rq.append((cr + dr, cc + dc))
                    regions.append(region)

        for region in regions:
            border_colors = Counter()
            for rr, rc in region:
                for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nr, nc = rr + dr, rc + dc
                    if 0 <= nr < h and 0 <= nc < w and (nr, nc) not in region and inp[nr, nc] != bg:
                        border_colors[int(inp[nr, nc])] += 1
            if not border_colors:
                continue
            expected_fill = border_colors.most_common(1)[0][0]
            for rr, rc in region:
                if int(out[rr, rc]) != expected_fill:
                    return None

    def apply_fn(grid: np.ndarray) -> np.ndarray:
        bg = _bg_color(grid)
        h, w = grid.shape
        reachable = np.zeros((h, w), dtype=bool)
        queue = deque()
        for r in range(h):
            for c in [0, w - 1]:
                if grid[r, c] == bg and not reachable[r, c]:
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
                        fill_c = border_colors.most_common(1)[0][0]
                        for rr, rc in region:
                            result[rr, rc] = fill_c
        return result

    return apply_fn


def try_horizontal_mirror(
    train_pairs: list[tuple[np.ndarray, np.ndarray]],
) -> Callable | None:
    for inp, out in train_pairs:
        if inp.shape != out.shape:
            return None
        if not np.array_equal(np.flipud(inp), out):
            return None

    def apply_fn(grid: np.ndarray) -> np.ndarray:
        return np.flipud(grid).copy()
    return apply_fn


def try_vertical_mirror(
    train_pairs: list[tuple[np.ndarray, np.ndarray]],
) -> Callable | None:
    for inp, out in train_pairs:
        if inp.shape != out.shape:
            return None
        if not np.array_equal(np.fliplr(inp), out):
            return None

    def apply_fn(grid: np.ndarray) -> np.ndarray:
        return np.fliplr(grid).copy()
    return apply_fn


def try_rotate_90(
    train_pairs: list[tuple[np.ndarray, np.ndarray]],
) -> Callable | None:
    for angle in [1, 2, 3]:
        matches = True
        for inp, out in train_pairs:
            if not np.array_equal(np.rot90(inp, angle), out):
                matches = False
                break
        if matches:
            a = angle

            def apply_fn(grid: np.ndarray) -> np.ndarray:
                return np.rot90(grid, a).copy()
            return apply_fn
    return None


def try_transpose(
    train_pairs: list[tuple[np.ndarray, np.ndarray]],
) -> Callable | None:
    for inp, out in train_pairs:
        if not np.array_equal(inp.T, out):
            return None

    def apply_fn(grid: np.ndarray) -> np.ndarray:
        return grid.T.copy()
    return apply_fn


def try_subgrid_operations(
    train_pairs: list[tuple[np.ndarray, np.ndarray]],
) -> Callable | None:
    for n_rows in range(2, 5):
        for n_cols in range(2, 5):
            fn = _try_subgrid_op(train_pairs, n_rows, n_cols)
            if fn is not None:
                return fn
    return None


def _try_subgrid_op(
    train_pairs: list[tuple[np.ndarray, np.ndarray]],
    n_rows: int,
    n_cols: int,
) -> Callable | None:
    for inp, out in train_pairs:
        ih, iw = inp.shape
        if ih % n_rows != 0 or iw % n_cols != 0:
            return None

    cell_h = train_pairs[0][0].shape[0] // n_rows
    cell_w = train_pairs[0][0].shape[1] // n_cols

    for op_name, op_fn in [("and", np.minimum), ("or", np.maximum), ("xor", lambda a, b: (a != b).astype(int))]:
        matches = True
        for inp, out in train_pairs:
            subgrids = []
            for r in range(n_rows):
                for c in range(n_cols):
                    sg = inp[r * cell_h:(r + 1) * cell_h, c * cell_w:(c + 1) * cell_w]
                    subgrids.append(sg)
            if not subgrids:
                matches = False
                break

            bg = _bg_color(inp)
            binary_sgs = [(sg != bg).astype(int) for sg in subgrids]
            result = binary_sgs[0]
            for bsg in binary_sgs[1:]:
                result = op_fn(result, bsg)

            if op_name == "xor":
                result_grid = np.where(result, subgrids[0], bg)
            else:
                result_grid = np.where(result, subgrids[0], bg)
                for sg in subgrids[1:]:
                    mask = (result > 0) & (sg != bg)
                    result_grid[mask] = sg[mask]

            if out.shape == result_grid.shape and np.array_equal(result_grid, out):
                continue
            else:
                matches = False
                break

        if matches:
            nr, nc, ch, cw, op = n_rows, n_cols, cell_h, cell_w, op_fn

            def apply_fn(grid: np.ndarray) -> np.ndarray:
                bg = _bg_color(grid)
                sgs = []
                for r in range(nr):
                    for c in range(nc):
                        sg = grid[r * ch:(r + 1) * ch, c * cw:(c + 1) * cw]
                        sgs.append(sg)
                binary = [(s != bg).astype(int) for s in sgs]
                res = binary[0]
                for b in binary[1:]:
                    res = op(res, b)
                out = np.full((ch, cw), bg, dtype=grid.dtype)
                for s in sgs:
                    mask = (s != bg)
                    out[mask] = s[mask]
                return out

            return apply_fn

    return None


def try_gravity(
    train_pairs: list[tuple[np.ndarray, np.ndarray]],
) -> Callable | None:
    for direction in ["down", "up", "left", "right"]:
        fn = _try_gravity_dir(train_pairs, direction)
        if fn is not None:
            return fn
    return None


def _try_gravity_dir(
    train_pairs: list[tuple[np.ndarray, np.ndarray]],
    direction: str,
) -> Callable | None:
    for inp, out in train_pairs:
        if inp.shape != out.shape:
            return None
        result = _apply_gravity(inp, direction)
        if not np.array_equal(result, out):
            return None

    d = direction

    def apply_fn(grid: np.ndarray) -> np.ndarray:
        return _apply_gravity(grid, d)
    return apply_fn


def _apply_gravity(grid: np.ndarray, direction: str) -> np.ndarray:
    bg = _bg_color(grid)
    result = np.full_like(grid, bg)
    h, w = grid.shape

    if direction == "down":
        for c in range(w):
            non_bg = [int(grid[r, c]) for r in range(h) if grid[r, c] != bg]
            for i, v in enumerate(reversed(non_bg)):
                result[h - 1 - i, c] = v
    elif direction == "up":
        for c in range(w):
            non_bg = [int(grid[r, c]) for r in range(h) if grid[r, c] != bg]
            for i, v in enumerate(non_bg):
                result[i, c] = v
    elif direction == "right":
        for r in range(h):
            non_bg = [int(grid[r, c]) for c in range(w) if grid[r, c] != bg]
            for i, v in enumerate(reversed(non_bg)):
                result[r, w - 1 - i] = v
    elif direction == "left":
        for r in range(h):
            non_bg = [int(grid[r, c]) for c in range(w) if grid[r, c] != bg]
            for i, v in enumerate(non_bg):
                result[r, i] = v

    return result


def try_remove_color(
    train_pairs: list[tuple[np.ndarray, np.ndarray]],
) -> Callable | None:
    for remove_color in range(10):
        matches = True
        for inp, out in train_pairs:
            if inp.shape != out.shape:
                return None
            bg = _bg_color(inp)
            expected = inp.copy()
            expected[expected == remove_color] = bg
            if not np.array_equal(expected, out):
                matches = False
                break
        if matches:
            rc = remove_color

            def apply_fn(grid: np.ndarray) -> np.ndarray:
                bg = _bg_color(grid)
                result = grid.copy()
                result[result == rc] = bg
                return result
            return apply_fn
    return None


def try_keep_only_color(
    train_pairs: list[tuple[np.ndarray, np.ndarray]],
) -> Callable | None:
    for keep_color in range(10):
        matches = True
        for inp, out in train_pairs:
            if inp.shape != out.shape:
                return None
            bg = _bg_color(inp)
            expected = np.full_like(inp, bg)
            expected[inp == keep_color] = keep_color
            if not np.array_equal(expected, out):
                matches = False
                break
        if matches:
            kc = keep_color

            def apply_fn(grid: np.ndarray) -> np.ndarray:
                bg = _bg_color(grid)
                result = np.full_like(grid, bg)
                result[grid == kc] = kc
                return result
            return apply_fn
    return None


def try_recolor_by_size_rank(
    train_pairs: list[tuple[np.ndarray, np.ndarray]],
) -> Callable | None:
    def _extract_components(grid):
        bg = _bg_color(grid)
        h, w = grid.shape
        visited = np.zeros((h, w), dtype=bool)
        components = []
        for r in range(h):
            for c in range(w):
                if not visited[r, c] and grid[r, c] != bg:
                    color = int(grid[r, c])
                    cells = set()
                    queue = deque([(r, c)])
                    while queue:
                        cr, cc = queue.popleft()
                        if (cr, cc) in cells:
                            continue
                        if 0 <= cr < h and 0 <= cc < w and not visited[cr, cc] and grid[cr, cc] == color:
                            cells.add((cr, cc))
                            visited[cr, cc] = True
                            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                                queue.append((cr + dr, cc + dc))
                    components.append((color, cells))
        return components

    all_rank_maps = []
    for inp, out in train_pairs:
        if inp.shape != out.shape:
            return None
        comps = _extract_components(inp)
        sizes = sorted(set(len(c[1]) for c in comps), reverse=True)
        size_to_rank = {s: i for i, s in enumerate(sizes)}

        rank_map = {}
        for color, cells in comps:
            rank = size_to_rank[len(cells)]
            for r, c in cells:
                out_color = int(out[r, c])
                if rank not in rank_map:
                    rank_map[rank] = out_color
                elif rank_map[rank] != out_color:
                    return None
        all_rank_maps.append(rank_map)

    if not all_rank_maps:
        return None
    ref = all_rank_maps[0]
    if not all(m == ref for m in all_rank_maps):
        return None
    if all(v == k for k, v in ref.items()):
        return None

    rm = dict(ref)

    def apply_fn(grid: np.ndarray) -> np.ndarray:
        bg = _bg_color(grid)
        comps = _extract_components(grid)
        sizes = sorted(set(len(c[1]) for c in comps), reverse=True)
        size_to_rank = {s: i for i, s in enumerate(sizes)}
        result = grid.copy()
        for color, cells in comps:
            rank = size_to_rank[len(cells)]
            if rank in rm:
                for r, c in cells:
                    result[r, c] = rm[rank]
        return result
    return apply_fn


def try_half_mirror(
    train_pairs: list[tuple[np.ndarray, np.ndarray]],
) -> Callable | None:
    for mode in ["top_to_bottom", "bottom_to_top", "left_to_right", "right_to_left"]:
        matches = True
        for inp, out in train_pairs:
            if inp.shape != out.shape:
                return None
            h, w = inp.shape
            result = inp.copy()
            if mode == "top_to_bottom":
                half = h // 2
                result[h - half:, :] = np.flipud(result[:half, :])
            elif mode == "bottom_to_top":
                half = h // 2
                result[:half, :] = np.flipud(result[h - half:, :])
            elif mode == "left_to_right":
                half = w // 2
                result[:, w - half:] = np.fliplr(result[:, :half])
            elif mode == "right_to_left":
                half = w // 2
                result[:, :half] = np.fliplr(result[:, w - half:])
            if not np.array_equal(result, out):
                matches = False
                break
        if matches:
            m = mode

            def apply_fn(grid: np.ndarray) -> np.ndarray:
                h, w = grid.shape
                result = grid.copy()
                if m == "top_to_bottom":
                    half = h // 2
                    result[h - half:, :] = np.flipud(result[:half, :])
                elif m == "bottom_to_top":
                    half = h // 2
                    result[:half, :] = np.flipud(result[h - half:, :])
                elif m == "left_to_right":
                    half = w // 2
                    result[:, w - half:] = np.fliplr(result[:, :half])
                elif m == "right_to_left":
                    half = w // 2
                    result[:, :half] = np.fliplr(result[:, w - half:])
                return result
            return apply_fn
    return None


def try_scale_up(
    train_pairs: list[tuple[np.ndarray, np.ndarray]],
) -> Callable | None:
    for scale in [2, 3, 4, 5]:
        matches = True
        for inp, out in train_pairs:
            ih, iw = inp.shape
            oh, ow = out.shape
            if oh != ih * scale or ow != iw * scale:
                matches = False
                break
            expected = np.repeat(np.repeat(inp, scale, axis=0), scale, axis=1)
            if not np.array_equal(expected, out):
                matches = False
                break
        if matches:
            s = scale

            def apply_fn(grid: np.ndarray) -> np.ndarray:
                return np.repeat(np.repeat(grid, s, axis=0), s, axis=1)
            return apply_fn
    return None


def try_scale_down(
    train_pairs: list[tuple[np.ndarray, np.ndarray]],
) -> Callable | None:
    for scale in [2, 3, 4, 5]:
        matches = True
        for inp, out in train_pairs:
            ih, iw = inp.shape
            oh, ow = out.shape
            if ih != oh * scale or iw != ow * scale:
                matches = False
                break
            expected = inp[::scale, ::scale]
            if not np.array_equal(expected, out):
                matches = False
                break
        if matches:
            s = scale

            def apply_fn(grid: np.ndarray) -> np.ndarray:
                return grid[::s, ::s].copy()
            return apply_fn
    return None


def try_majority_vote_subgrids(
    train_pairs: list[tuple[np.ndarray, np.ndarray]],
) -> Callable | None:
    for n_rows in range(2, 5):
        for n_cols in range(2, 5):
            matches = True
            cell_h = cell_w = 0
            for inp, out in train_pairs:
                ih, iw = inp.shape
                if ih % n_rows != 0 or iw % n_cols != 0:
                    matches = False
                    break
                ch, cw = ih // n_rows, iw // n_cols
                if cell_h == 0:
                    cell_h, cell_w = ch, cw
                if out.shape != (ch, cw):
                    matches = False
                    break

                subgrids = []
                for r in range(n_rows):
                    for c in range(n_cols):
                        sg = inp[r * ch:(r + 1) * ch, c * cw:(c + 1) * cw]
                        subgrids.append(sg)

                result = np.zeros((ch, cw), dtype=np.int32)
                for rr in range(ch):
                    for cc in range(cw):
                        votes = Counter(int(sg[rr, cc]) for sg in subgrids)
                        result[rr, cc] = votes.most_common(1)[0][0]

                if not np.array_equal(result, out):
                    matches = False
                    break

            if matches and cell_h > 0:
                nr, nc = n_rows, n_cols

                def apply_fn(grid: np.ndarray) -> np.ndarray:
                    ih, iw = grid.shape
                    ch, cw = ih // nr, iw // nc
                    subgrids = []
                    for r in range(nr):
                        for c in range(nc):
                            sg = grid[r * ch:(r + 1) * ch, c * cw:(c + 1) * cw]
                            subgrids.append(sg)
                    result = np.zeros((ch, cw), dtype=np.int32)
                    for rr in range(ch):
                        for cc in range(cw):
                            votes = Counter(int(sg[rr, cc]) for sg in subgrids)
                            result[rr, cc] = votes.most_common(1)[0][0]
                    return result
                return apply_fn
    return None


ALL_GRID_SOLVERS = [
    ("color_permutation", try_color_permutation),
    ("fill_enclosed", try_fill_enclosed),
    ("fill_enclosed_adaptive", try_fill_enclosed_adaptive),
    ("horizontal_mirror", try_horizontal_mirror),
    ("vertical_mirror", try_vertical_mirror),
    ("half_mirror", try_half_mirror),
    ("rotate", try_rotate_90),
    ("transpose", try_transpose),
    ("crop_nonbackground", try_crop_nonbackground),
    ("crop_to_object", try_crop_to_object),
    ("tile", try_tile),
    ("scale_up", try_scale_up),
    ("scale_down", try_scale_down),
    ("gravity", try_gravity),
    ("subgrid_ops", try_subgrid_operations),
    ("majority_vote_subgrids", try_majority_vote_subgrids),
    ("remove_color", try_remove_color),
    ("keep_only_color", try_keep_only_color),
    ("recolor_by_size_rank", try_recolor_by_size_rank),
]
