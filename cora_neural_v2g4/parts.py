"""ncv2-g4 sub-object units (proposal C3, C4). A part is a set of cells derived from one native object of the INPUT grid.

| kind | cells |
|---|---|
| whole | every cell of the object (for parity with native object rules) |
| border | object cells with a 4-neighbour outside the object or off the grid |
| interior | object cells that are not border cells |
| endpoints | object cells with exactly one 4-neighbour in the object |
| corners | object cells at the corners of the object's bounding box |
| contact | object cells 4-adjacent to a cell of another non-background colour |
| holes | background cells enclosed by the object: not 4-connected to the grid edge through background (negative space) |
| bbox_background | background cells inside the object's bounding box |

`holes` and `bbox_background` are regions outside the object's own cells, so a rule over them adds cells.
"""
import numpy as np

KINDS = ("whole", "border", "interior", "endpoints", "corners", "contact", "holes", "bbox_background")
N4 = ((0, 1), (0, -1), (1, 0), (-1, 0))


def _inside(shape, r, c):
    return 0 <= r < shape[0] and 0 <= c < shape[1]


def part(cells, kind, grid, bg):
    """The cells of `kind` for the object with `cells` in `grid` (numpy), as a frozenset."""
    cells = frozenset(cells)
    G = np.asarray(grid)
    if kind == "whole":
        return cells
    nb = lambda r, c: [(r + dr, c + dc) for dr, dc in N4]                                   # noqa: E731
    if kind == "border":
        return frozenset(x for x in cells if any(y not in cells for y in nb(*x)))
    if kind == "interior":
        return frozenset(x for x in cells if all(y in cells for y in nb(*x)))
    if kind == "endpoints":
        return frozenset(x for x in cells if sum(y in cells for y in nb(*x)) == 1)
    rs, cs = zip(*cells)
    r0, r1, c0, c1 = min(rs), max(rs), min(cs), max(cs)
    if kind == "corners":
        return frozenset(x for x in ((r0, c0), (r0, c1), (r1, c0), (r1, c1)) if x in cells)
    if kind == "contact":
        return frozenset(x for x in cells if any(_inside(G.shape, *y) and y not in cells and G[y] != bg for y in nb(*x)))
    if kind == "bbox_background":
        return frozenset((r, c) for r in range(r0, r1 + 1) for c in range(c0, c1 + 1) if (r, c) not in cells and G[r, c] == bg)
    if kind == "holes":
        return frozenset(x for x in holes(cells, G.shape) if G[x] == bg)
    raise ValueError(f"unknown part kind {kind}")


def holes(cells, shape):
    """Cells not in the object that cannot reach the grid edge without crossing the object (4-connectivity)."""
    cells = frozenset(cells)
    rs, cs = zip(*cells)
    r0, r1, c0, c1 = min(rs), max(rs), min(cs), max(cs)
    box = {(r, c) for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)} - cells
    if not box:
        return frozenset()
    # flood from the bounding box's frame (cells just outside it count as reaching the edge)
    seen, stack = set(), [x for x in box if x[0] in (r0, r1) or x[1] in (c0, c1)]
    while stack:
        x = stack.pop()
        if x in seen:
            continue
        seen.add(x)
        for dr, dc in N4:
            y = (x[0] + dr, x[1] + dc)
            if y in box and y not in seen:
                stack.append(y)
    return frozenset(box - seen)
