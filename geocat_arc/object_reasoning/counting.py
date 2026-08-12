"""Counting/summary program family: output is a small grid encoding
properties of the input (color counts, object counts, feature aggregates).

From the deep analysis (642d658d: 22x22 input -> 1x1 output = the most
common non-bg color; 31aa019c: find the unique cell and frame it).

This family covers shrink tasks where the output size is COMPUTED from
the input's content, not from panel geometry.  The output is typically
very small (1x1 to 5x5) and encodes a census or summary.

Modes (MDL-ordered):
  - majority_color: output = 1x1 grid of the most common non-bg color
  - color_count: output = Nx1 grid where each cell is a distinct non-bg
    color, sorted by frequency
  - object_count_as_size: output = KxK grid filled with a single color,
    where K = number of objects of a specific type
  - unique_color: output = 1x1 grid of the color that appears exactly once
"""
from __future__ import annotations
from typing import Optional
from collections import Counter
from geocat_arc.perception.grid import Grid

BG = 0


def _color_census(grid_list):
    counts = Counter()
    for row in grid_list:
        for c in row:
            if c != BG:
                counts[c] += 1
    return counts


def _try_majority_color(pairs):
    for gi, go in pairs:
        if len(go) != 1 or len(go[0]) != 1:
            return None
        census = _color_census(gi)
        if not census:
            return None
        majority = census.most_common(1)[0][0]
        if go[0][0] != majority:
            return None
    return {"mode": "majority_color"}


def _try_unique_color(pairs):
    for gi, go in pairs:
        if len(go) != 1 or len(go[0]) != 1:
            return None
        census = _color_census(gi)
        uniques = [c for c, n in census.items() if n == 1]
        if len(uniques) != 1 or go[0][0] != uniques[0]:
            return None
    return {"mode": "unique_color"}


def _try_color_count_row(pairs):
    """Output = 1-row grid listing distinct non-bg colors sorted by frequency."""
    for gi, go in pairs:
        if len(go) != 1:
            return None
        census = _color_census(gi)
        sorted_colors = [c for c, _ in census.most_common()]
        if list(go[0]) != sorted_colors:
            return None
    return {"mode": "color_count_row"}


def _try_color_histogram(pairs):
    """Output = Nx2 or Nx1 grid encoding color frequencies."""
    for gi, go in pairs:
        census = _color_census(gi)
        ho, wo = len(go), len(go[0])
        if wo == 1 and ho == len(census):
            sorted_colors = [c for c, _ in census.most_common()]
            if [go[r][0] for r in range(ho)] == sorted_colors:
                return {"mode": "color_histogram_col"}
    return None


def _surrounding_of_unique(gi):
    """The majority color of the 8-neighborhood of the cell whose color
    occurs exactly once in the grid (the anomaly).  None if no unique
    color or ambiguous."""
    census = _color_census(gi)
    uniques = [c for c, n in census.items() if n == 1]
    if len(uniques) != 1:
        return None
    uc = uniques[0]
    h, w = len(gi), len(gi[0])
    pos = next((r, c) for r in range(h) for c in range(w)
               if gi[r][c] == uc)
    r0, c0 = pos
    nbrs = Counter()
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == dc == 0:
                continue
            r, c = r0 + dr, c0 + dc
            if 0 <= r < h and 0 <= c < w and gi[r][c] != BG:
                nbrs[gi[r][c]] += 1
    if not nbrs:
        return None
    return nbrs.most_common(1)[0][0]


def _try_surrounding_of_unique(pairs):
    """642d658d family: 1x1 output = the color surrounding the grid's
    unique anomaly cell."""
    for gi, go in pairs:
        if len(go) != 1 or len(go[0]) != 1:
            return None
        val = _surrounding_of_unique(gi)
        if val is None or go[0][0] != val:
            return None
    return {"mode": "surrounding_of_unique"}


def induce_counting_program(train_pairs) -> Optional[dict]:
    """Try counting/summary abstractions. Returns program dict or None."""
    pairs = [(gi.to_list(), go.to_list()) for gi, go in train_pairs]
    for inducer in (_try_majority_color, _try_unique_color,
                    _try_surrounding_of_unique,
                    _try_color_count_row, _try_color_histogram):
        result = inducer(pairs)
        if result is not None:
            return result
    return None


def render_counting(program: dict, input_grid: Grid) -> Grid:
    gi = input_grid.to_list()
    census = _color_census(gi)
    mode = program["mode"]

    if mode == "majority_color":
        return Grid.from_list([[census.most_common(1)[0][0]]])

    if mode == "unique_color":
        uniques = [c for c, n in census.items() if n == 1]
        return Grid.from_list([[uniques[0] if uniques else 0]])

    if mode == "surrounding_of_unique":
        val = _surrounding_of_unique(gi)
        return Grid.from_list([[val if val is not None else 0]])

    if mode == "color_count_row":
        return Grid.from_list([[c for c, _ in census.most_common()]])

    if mode == "color_histogram_col":
        return Grid.from_list([[c] for c, _ in census.most_common()])

    raise ValueError(f"unknown counting mode: {mode}")
