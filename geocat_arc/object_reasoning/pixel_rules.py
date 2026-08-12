"""Pixel-level program family (round 12): cellular-automaton-style rules.

The object engine assumes per-object correspondence (input object X ->
output object Y via delta D).  ~191 unsolved same-shape tasks operate at
the CELL level: each output cell is a function of its input neighborhood.
This family induces that function.

A PixelRuleProgram maps each cell to an output color based on:
  - the cell's own input color
  - the colors of its 4-connected (or 8-connected) neighbors
  - its position relative to non-background connected components
  - global grid properties (size, color palette)

The rule is a DECISION TABLE: for each observed neighborhood signature
(abstracted to a canonical form), the output color.  Zero-conflict
across all train pairs.  LOO-by-reinduction validates the table the
same way it validates object programs.

Neighborhood abstraction levels (cheapest first, MDL-ordered):
  1. identity: output = input (KEEP equivalent, free)
  2. color_swap: output = f(input_color) globally (color map, cheap)
  3. neighbor_count: output = f(count of non-bg neighbors) (generic)
  4. neighbor_pattern: output = f(which neighbors are non-bg) (richer)
  5. neighbor_colors: output = f(color tuple of neighbors) (richest)

Only same-shape tasks where the object engine scored < 0.5 try this
family (no competition with the object engine on its home turf).
"""
from __future__ import annotations
from typing import Optional
from geocat_arc.perception.grid import Grid

BG = 0


def _neighbors_4(grid, r, c, h, w):
    out = []
    for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        nr, nc = r + dr, c + dc
        if 0 <= nr < h and 0 <= nc < w:
            out.append(grid[nr][nc])
        else:
            out.append(-1)  # border sentinel
    return tuple(out)


def _neighbor_count(grid, r, c, h, w):
    return sum(1 for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1))
               if 0 <= r + dr < h and 0 <= c + dc < w
               and grid[r + dr][c + dc] != BG)


def _try_color_swap(pairs):
    """Global color map: output_color = f(input_color), same everywhere."""
    mapping = {}
    for gi, go in pairs:
        h, w = len(gi), len(gi[0])
        for r in range(h):
            for c in range(w):
                k, v = gi[r][c], go[r][c]
                if mapping.get(k, v) != v:
                    return None
                mapping[k] = v
    if all(k == v for k, v in mapping.items()):
        return None  # identity
    return {"mode": "color_swap", "table": {str(k): v for k, v in
                                             sorted(mapping.items())}}


def _try_neighbor_count(pairs):
    """Output = f(input_color, count of non-bg 4-neighbors)."""
    table = {}
    for gi, go in pairs:
        h, w = len(gi), len(gi[0])
        for r in range(h):
            for c in range(w):
                key = (gi[r][c], _neighbor_count(gi, r, c, h, w))
                val = go[r][c]
                if table.get(str(key), val) != val:
                    return None
                table[str(key)] = val
    if all(eval(k)[0] == v for k, v in table.items()):
        return None  # just identity under the key
    return {"mode": "neighbor_count", "table": table}


def _try_neighbor_pattern(pairs):
    """Output = f(input_color, which of 4 neighbors are non-bg)."""
    table = {}
    for gi, go in pairs:
        h, w = len(gi), len(gi[0])
        for r in range(h):
            for c in range(w):
                nbrs = _neighbors_4(gi, r, c, h, w)
                key = (gi[r][c], tuple(1 if n > 0 else (0 if n == 0 else -1)
                                       for n in nbrs))
                val = go[r][c]
                if table.get(str(key), val) != val:
                    return None
                table[str(key)] = val
    return {"mode": "neighbor_pattern", "table": table}


def induce_pixel_rule(train_pairs) -> Optional[dict]:
    """Try pixel-rule abstractions in MDL order. Returns the program dict
    or None.  `train_pairs` are (Grid, Grid) pairs."""
    pairs = [(gi.to_list(), go.to_list()) for gi, go in train_pairs]
    if not all(len(gi) == len(go) and len(gi[0]) == len(go[0])
               for gi, go in pairs):
        return None

    for inducer in (_try_color_swap, _try_neighbor_count,
                    _try_neighbor_pattern):
        result = inducer(pairs)
        if result is not None:
            return result
    return None


def render_pixel_rule(program: dict, input_grid: Grid) -> Grid:
    """Execute a pixel-rule program."""
    gi = input_grid.to_list()
    h, w = len(gi), len(gi[0])
    go = [row[:] for row in gi]
    mode = program["mode"]
    table = program["table"]

    if mode == "color_swap":
        for r in range(h):
            for c in range(w):
                k = str(gi[r][c])
                if k in table:
                    go[r][c] = table[k]

    elif mode == "neighbor_count":
        for r in range(h):
            for c in range(w):
                key = str((gi[r][c], _neighbor_count(gi, r, c, h, w)))
                if key in table:
                    go[r][c] = table[key]

    elif mode == "neighbor_pattern":
        for r in range(h):
            for c in range(w):
                nbrs = _neighbors_4(gi, r, c, h, w)
                key = str((gi[r][c], tuple(1 if n > 0 else (0 if n == 0 else -1)
                                           for n in nbrs)))
                if key in table:
                    go[r][c] = table[key]

    return Grid.from_list(go)
