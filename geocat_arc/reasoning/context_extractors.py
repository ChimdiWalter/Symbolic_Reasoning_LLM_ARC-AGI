"""Context extractors — different ways to view a grid cell for rule induction.

Each extractor maps (grid, row, col) -> hashable context key.
A rule is a consistent mapping: context_key -> output_color.
If the same key maps to different output colors across training pairs,
the extractor is rejected for this task.
"""
from __future__ import annotations
import numpy as np
from collections import Counter


def _get(grid: np.ndarray, r: int, c: int, default: int = -1) -> int:
    h, w = grid.shape
    if 0 <= r < h and 0 <= c < w:
        return int(grid[r, c])
    return default


def cell_color(grid: np.ndarray, r: int, c: int) -> tuple:
    return (int(grid[r, c]),)


def cell_color_and_position(grid: np.ndarray, r: int, c: int) -> tuple:
    return (int(grid[r, c]), r, c)


def cell_color_and_relative_position(grid: np.ndarray, r: int, c: int) -> tuple:
    h, w = grid.shape
    return (int(grid[r, c]), round(r / max(h - 1, 1), 2), round(c / max(w - 1, 1), 2))


def neighborhood_3x3(grid: np.ndarray, r: int, c: int) -> tuple:
    return tuple(_get(grid, r + dr, c + dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1))


def neighborhood_3x3_with_pos(grid: np.ndarray, r: int, c: int) -> tuple:
    h, w = grid.shape
    nbr = tuple(_get(grid, r + dr, c + dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1))
    return nbr + (r, c)


def neighborhood_cross(grid: np.ndarray, r: int, c: int) -> tuple:
    return (
        _get(grid, r - 1, c),
        _get(grid, r, c - 1), int(grid[r, c]), _get(grid, r, c + 1),
        _get(grid, r + 1, c),
    )


def neighborhood_5x5(grid: np.ndarray, r: int, c: int) -> tuple:
    return tuple(_get(grid, r + dr, c + dc) for dr in range(-2, 3) for dc in range(-2, 3))


def cell_with_row_col_dominant(grid: np.ndarray, r: int, c: int) -> tuple:
    row = grid[r, :]
    col = grid[:, c]
    row_dom = int(Counter(row.tolist()).most_common(1)[0][0])
    col_dom = int(Counter(col.tolist()).most_common(1)[0][0])
    return (int(grid[r, c]), row_dom, col_dom)


def cell_with_border_distance(grid: np.ndarray, r: int, c: int) -> tuple:
    h, w = grid.shape
    border_dist = min(r, c, h - 1 - r, w - 1 - c)
    return (int(grid[r, c]), border_dist)


def cell_modular_2x2(grid: np.ndarray, r: int, c: int) -> tuple:
    return (int(grid[r, c]), r % 2, c % 2)


def cell_modular_3x3(grid: np.ndarray, r: int, c: int) -> tuple:
    return (int(grid[r, c]), r % 3, c % 3)


def cell_modular_4x4(grid: np.ndarray, r: int, c: int) -> tuple:
    return (int(grid[r, c]), r % 4, c % 4)


def cross_with_modular(grid: np.ndarray, r: int, c: int) -> tuple:
    cross = (
        _get(grid, r - 1, c),
        _get(grid, r, c - 1), int(grid[r, c]), _get(grid, r, c + 1),
        _get(grid, r + 1, c),
    )
    return cross + (r % 2, c % 2)


def cell_with_neighbor_count(grid: np.ndarray, r: int, c: int) -> tuple:
    h, w = grid.shape
    bg = int(Counter(grid.flatten().tolist()).most_common(1)[0][0])
    count = 0
    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        nr, nc = r + dr, c + dc
        if 0 <= nr < h and 0 <= nc < w and grid[nr, nc] != bg:
            count += 1
    return (int(grid[r, c]), count)


def cell_with_8neighbor_count(grid: np.ndarray, r: int, c: int) -> tuple:
    h, w = grid.shape
    bg = int(Counter(grid.flatten().tolist()).most_common(1)[0][0])
    count = 0
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            nr, nc = r + dr, c + dc
            if 0 <= nr < h and 0 <= nc < w and grid[nr, nc] != bg:
                count += 1
    return (int(grid[r, c]), count)


def cell_with_region_size(grid: np.ndarray, r: int, c: int) -> tuple:
    h, w = grid.shape
    color = int(grid[r, c])
    visited = set()
    stack = [(r, c)]
    while stack:
        cr, cc = stack.pop()
        if (cr, cc) in visited:
            continue
        if 0 <= cr < h and 0 <= cc < w and grid[cr, cc] == color:
            visited.add((cr, cc))
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                stack.append((cr + dr, cc + dc))
    size_bin = min(len(visited), 50)
    return (color, size_bin)


def cell_color_with_global_freq(grid: np.ndarray, r: int, c: int) -> tuple:
    color = int(grid[r, c])
    total = grid.size
    freq = int(np.sum(grid == color))
    freq_bin = round(freq / total, 1)
    return (color, freq_bin)


def neighborhood_binary_3x3(grid: np.ndarray, r: int, c: int) -> tuple:
    center = int(grid[r, c])
    bits = []
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            v = _get(grid, r + dr, c + dc, -1)
            bits.append(1 if v == center else 0)
    return (center,) + tuple(bits)


def cell_with_symmetry_partner(grid: np.ndarray, r: int, c: int) -> tuple:
    h, w = grid.shape
    mirror_r = h - 1 - r
    mirror_c = w - 1 - c
    return (
        int(grid[r, c]),
        _get(grid, mirror_r, c),
        _get(grid, r, mirror_c),
        _get(grid, mirror_r, mirror_c),
    )


def row_pattern_hash(grid: np.ndarray, r: int, c: int) -> tuple:
    row = tuple(int(x) for x in grid[r, :])
    return (int(grid[r, c]), hash(row) % 10000, c)


def col_pattern_hash(grid: np.ndarray, r: int, c: int) -> tuple:
    col = tuple(int(x) for x in grid[:, c])
    return (int(grid[r, c]), hash(col) % 10000, r)


def cell_is_boundary(grid: np.ndarray, r: int, c: int) -> tuple:
    """Is cell on the boundary of its connected component?"""
    h, w = grid.shape
    color = int(grid[r, c])
    on_boundary = False
    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        nr, nc = r + dr, c + dc
        if nr < 0 or nr >= h or nc < 0 or nc >= w or grid[nr, nc] != color:
            on_boundary = True
            break
    return (color, int(on_boundary))


def cell_neighbor_color_set(grid: np.ndarray, r: int, c: int) -> tuple:
    """Color + sorted set of distinct neighbor colors."""
    h, w = grid.shape
    center = int(grid[r, c])
    nbr_colors = set()
    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        nr, nc = r + dr, c + dc
        if 0 <= nr < h and 0 <= nc < w:
            nbr_colors.add(int(grid[nr, nc]))
        else:
            nbr_colors.add(-1)
    return (center,) + tuple(sorted(nbr_colors))


def cell_8neighbor_color_set(grid: np.ndarray, r: int, c: int) -> tuple:
    """Color + sorted set of distinct 8-neighbor colors."""
    h, w = grid.shape
    center = int(grid[r, c])
    nbr_colors = set()
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            nr, nc = r + dr, c + dc
            if 0 <= nr < h and 0 <= nc < w:
                nbr_colors.add(int(grid[nr, nc]))
            else:
                nbr_colors.add(-1)
    return (center,) + tuple(sorted(nbr_colors))


def cell_has_specific_neighbor(grid: np.ndarray, r: int, c: int) -> tuple:
    """Color + bitmask of which colors exist in 4-neighborhood."""
    h, w = grid.shape
    center = int(grid[r, c])
    present = [0] * 10
    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        nr, nc = r + dr, c + dc
        if 0 <= nr < h and 0 <= nc < w:
            nc_val = int(grid[nr, nc])
            if 0 <= nc_val <= 9:
                present[nc_val] = 1
    return (center,) + tuple(present)


def cell_distance_to_nearest_nonbg(grid: np.ndarray, r: int, c: int) -> tuple:
    """Color + Manhattan distance to nearest non-background cell."""
    h, w = grid.shape
    bg = int(Counter(grid.flatten().tolist()).most_common(1)[0][0])
    color = int(grid[r, c])
    if color != bg:
        return (color, 0)
    min_dist = h + w
    for rr in range(h):
        for cc in range(w):
            if grid[rr, cc] != bg:
                dist = abs(r - rr) + abs(c - cc)
                if dist < min_dist:
                    min_dist = dist
    return (color, min(min_dist, 15))


def cell_color_and_border_type(grid: np.ndarray, r: int, c: int) -> tuple:
    """Color + type of border (corner, edge, interior, grid-edge)."""
    h, w = grid.shape
    color = int(grid[r, c])
    bg = int(Counter(grid.flatten().tolist()).most_common(1)[0][0])

    on_grid_edge = (r == 0 or r == h - 1 or c == 0 or c == w - 1)
    if color == bg:
        return (color, 0, int(on_grid_edge))

    same_count = 0
    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        nr, nc = r + dr, c + dc
        if 0 <= nr < h and 0 <= nc < w and grid[nr, nc] == color:
            same_count += 1
    return (color, same_count, int(on_grid_edge))


def cell_local_pattern_type(grid: np.ndarray, r: int, c: int) -> tuple:
    """Classify the local 3x3 pattern type (not raw values)."""
    h, w = grid.shape
    center = int(grid[r, c])
    bg = int(Counter(grid.flatten().tolist()).most_common(1)[0][0])

    same = 0
    diff = 0
    bg_count = 0
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            nr, nc = r + dr, c + dc
            if 0 <= nr < h and 0 <= nc < w:
                v = int(grid[nr, nc])
                if v == center:
                    same += 1
                elif v == bg:
                    bg_count += 1
                else:
                    diff += 1
            else:
                bg_count += 1

    return (center, same, diff, bg_count)


def cell_row_col_rank(grid: np.ndarray, r: int, c: int) -> tuple:
    """Color + rank of color within its row and column."""
    color = int(grid[r, c])
    row = grid[r, :]
    col = grid[:, c]

    row_counts = Counter(int(x) for x in row)
    col_counts = Counter(int(x) for x in col)

    row_rank = sorted(row_counts.keys(), key=lambda k: -row_counts[k]).index(color) if color in row_counts else -1
    col_rank = sorted(col_counts.keys(), key=lambda k: -col_counts[k]).index(color) if color in col_counts else -1

    return (color, row_rank, col_rank)


def cell_neighbor_count_by_color(grid: np.ndarray, r: int, c: int) -> tuple:
    """Color + count of each distinct neighbor color (sorted)."""
    h, w = grid.shape
    center = int(grid[r, c])
    counts = Counter()
    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        nr, nc = r + dr, c + dc
        if 0 <= nr < h and 0 <= nc < w:
            counts[int(grid[nr, nc])] += 1
    return (center,) + tuple(sorted(counts.items()))


def _extractor_bg(grid: np.ndarray) -> int:
    return int(Counter(grid.flatten().tolist()).most_common(1)[0][0])


def _flood_fill_component(grid: np.ndarray, r: int, c: int) -> set[tuple[int, int]]:
    """4-connected flood fill for cells of the same color."""
    h, w = grid.shape
    color = int(grid[r, c])
    visited = set()
    stack = [(r, c)]
    while stack:
        cr, cc = stack.pop()
        if (cr, cc) in visited:
            continue
        if 0 <= cr < h and 0 <= cc < w and grid[cr, cc] == color:
            visited.add((cr, cc))
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                stack.append((cr + dr, cc + dc))
    return visited


def cell_object_color_and_size(grid: np.ndarray, r: int, c: int) -> tuple:
    """Color + connected component size (binned)."""
    color = int(grid[r, c])
    bg = _extractor_bg(grid)
    if color == bg:
        return (color, 0)
    comp = _flood_fill_component(grid, r, c)
    return (color, min(len(comp), 30))


def cell_row_col_color_projection(grid: np.ndarray, r: int, c: int) -> tuple:
    """Color + non-bg presence in same row/col (for intersection detection)."""
    h, w = grid.shape
    color = int(grid[r, c])
    bg = _extractor_bg(grid)
    row_nonbg = sum(1 for cc in range(w) if cc != c and grid[r, cc] != bg)
    col_nonbg = sum(1 for rr in range(h) if rr != r and grid[rr, c] != bg)
    return (color, row_nonbg > 0, col_nonbg > 0, min(row_nonbg, 10), min(col_nonbg, 10))


def cell_between_objects(grid: np.ndarray, r: int, c: int) -> tuple:
    """Detects bg cells between non-bg cells in row/col."""
    h, w = grid.shape
    color = int(grid[r, c])
    bg = _extractor_bg(grid)
    if color != bg:
        return (color, False, False, -1, -1)
    left_c = right_c = top_c = bottom_c = -1
    for cc in range(c - 1, -1, -1):
        if grid[r, cc] != bg:
            left_c = int(grid[r, cc])
            break
    for cc in range(c + 1, w):
        if grid[r, cc] != bg:
            right_c = int(grid[r, cc])
            break
    for rr in range(r - 1, -1, -1):
        if grid[rr, c] != bg:
            top_c = int(grid[rr, c])
            break
    for rr in range(r + 1, h):
        if grid[rr, c] != bg:
            bottom_c = int(grid[rr, c])
            break
    between_row = left_c >= 0 and right_c >= 0
    between_col = top_c >= 0 and bottom_c >= 0
    return (color, between_row, between_col, left_c, right_c)


def cell_object_shape_signature(grid: np.ndarray, r: int, c: int) -> tuple:
    """Color + object shape properties (rectangular, line, dimensions)."""
    color = int(grid[r, c])
    bg = _extractor_bg(grid)
    if color == bg:
        return (color, False, 0, 0, False, False)
    comp = _flood_fill_component(grid, r, c)
    rows = [p[0] for p in comp]
    cols = [p[1] for p in comp]
    min_r, max_r = min(rows), max(rows)
    min_c, max_c = min(cols), max(cols)
    bh = max_r - min_r + 1
    bw = max_c - min_c + 1
    is_rect = len(comp) == bh * bw
    is_hline = bh == 1 and bw > 1
    is_vline = bw == 1 and bh > 1
    return (color, is_rect, min(bw, 10), min(bh, 10), is_hline, is_vline)


def cell_color_run_lengths(grid: np.ndarray, r: int, c: int) -> tuple:
    """Color + horizontal/vertical run length of same-colored cells."""
    h, w = grid.shape
    color = int(grid[r, c])
    hrun = 1
    for cc in range(c - 1, -1, -1):
        if grid[r, cc] == color:
            hrun += 1
        else:
            break
    for cc in range(c + 1, w):
        if grid[r, cc] == color:
            hrun += 1
        else:
            break
    vrun = 1
    for rr in range(r - 1, -1, -1):
        if grid[rr, c] == color:
            vrun += 1
        else:
            break
    for rr in range(r + 1, h):
        if grid[rr, c] == color:
            vrun += 1
        else:
            break
    return (color, min(hrun, 10), min(vrun, 10))


ALL_EXTRACTORS = [
    # Tier 1: Coarse structural (small key space, high generalization)
    ("cell_color", cell_color),
    ("cell_with_neighbor_count", cell_with_neighbor_count),
    ("cell_with_8neighbor_count", cell_with_8neighbor_count),
    ("cell_is_boundary", cell_is_boundary),
    ("cell_with_border_distance", cell_with_border_distance),
    ("cell_modular_2x2", cell_modular_2x2),
    ("cell_modular_3x3", cell_modular_3x3),
    ("cell_local_pattern_type", cell_local_pattern_type),
    ("cell_color_and_border_type", cell_color_and_border_type),
    ("cell_neighbor_color_set", cell_neighbor_color_set),
    ("cell_8neighbor_color_set", cell_8neighbor_color_set),
    ("cell_has_specific_neighbor", cell_has_specific_neighbor),
    ("cell_with_symmetry_partner", cell_with_symmetry_partner),
    ("cell_row_col_rank", cell_row_col_rank),
    # Tier 2: Medium (moderate key space)
    ("neighborhood_cross", neighborhood_cross),
    ("cell_with_region_size", cell_with_region_size),
    ("cross_with_modular", cross_with_modular),
    ("cell_with_row_col_dominant", cell_with_row_col_dominant),
    ("neighborhood_binary_3x3", neighborhood_binary_3x3),
    ("cell_neighbor_count_by_color", cell_neighbor_count_by_color),
    ("cell_color_with_global_freq", cell_color_with_global_freq),
    # Tier 2b: Object-aware (captures object-level properties)
    ("cell_object_color_and_size", cell_object_color_and_size),
    ("cell_row_col_color_projection", cell_row_col_color_projection),
    ("cell_between_objects", cell_between_objects),
    ("cell_object_shape_signature", cell_object_shape_signature),
    ("cell_color_run_lengths", cell_color_run_lengths),
    # Tier 3: Fine-grained (large key space, need fuzzy matching)
    ("neighborhood_3x3", neighborhood_3x3),
    ("neighborhood_5x5", neighborhood_5x5),
    # Tier 4: Position-dependent (only as last resort)
    ("cell_color_and_position", cell_color_and_position),
    ("cell_color_and_relative_position", cell_color_and_relative_position),
    ("neighborhood_3x3_with_pos", neighborhood_3x3_with_pos),
    ("cell_modular_4x4", cell_modular_4x4),
    ("row_pattern_hash", row_pattern_hash),
    ("col_pattern_hash", col_pattern_hash),
    ("cell_distance_to_nearest_nonbg", cell_distance_to_nearest_nonbg),
]
