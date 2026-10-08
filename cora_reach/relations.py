"""Growth relations: the bounded, human-designed, generic construction
grammar of the reach v1 mechanism (docs/CORA_REAL_TASK_REACH_DEV_v1.md).

A relation maps an object's cells O and the input scene G (a 2-D int array)
to a set of added cells. Every family is a pure function of the object and
the scene; none reads a task identifier, an output or a label. Background
is colour 0 (the ARC convention; stated as a limitation). The colour of the
added cells is not part of the relation: the engine's own colour-expression
grammar supplies it when the relation is installed.
"""
from __future__ import annotations

import itertools

BG = 0


def bbox(cells):
    rs = [r for r, _ in cells]
    cs = [c for _, c in cells]
    return min(rs), max(rs), min(cs), max(cs)


def window_fill(O, G, k):
    """Background cells covered by k x k all-background windows inside bbox(O)."""
    r0, r1, c0, c1 = bbox(O)
    out = set()
    for r in range(r0, r1 - k + 2):
        for c in range(c0, c1 - k + 2):
            win = G[r:r + k, c:c + k]
            if win.shape == (k, k) and (win == BG).all():
                out |= {(r + i, c + j) for i in range(k) for j in range(k)}
    return out


def empty_square(O, G, k):
    """Background 4-connected regions inside bbox(O) that are exactly k x k squares."""
    r0, r1, c0, c1 = bbox(O)
    seen, out = set(), set()
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            if G[r, c] != BG or (r, c) in seen:
                continue
            comp, stack = set(), [(r, c)]
            while stack:
                x = stack.pop()
                if x in comp or not (r0 <= x[0] <= r1 and c0 <= x[1] <= c1) or G[x] != BG:
                    continue
                comp.add(x)
                stack += [(x[0] + 1, x[1]), (x[0] - 1, x[1]), (x[0], x[1] + 1), (x[0], x[1] - 1)]
            seen |= comp
            if len(comp) == k * k:
                rs = [y for y, _ in comp]
                cs = [z for _, z in comp]
                if max(rs) - min(rs) == k - 1 and max(cs) - min(cs) == k - 1:
                    out |= comp
    return out


def bbox_fill(O, G):
    r0, r1, c0, c1 = bbox(O)
    return {(r, c) for r in range(r0, r1 + 1) for c in range(c0, c1 + 1) if G[r, c] == BG and (r, c) not in O}


def bbox_ring(O, G):
    r0, r1, c0, c1 = bbox(O)
    H, W = G.shape
    return {(r, c) for r in range(r0 - 1, r1 + 2) for c in range(c0 - 1, c1 + 2)
            if (r in (r0 - 1, r1 + 1) or c in (c0 - 1, c1 + 1)) and 0 <= r < H and 0 <= c < W and G[r, c] == BG}


def band(O, G, axis):
    r0, r1, c0, c1 = bbox(O)
    H, W = G.shape
    rows = set(range(r0, r1 + 1)) if axis in ("rows", "cross") else set()
    cols = set(range(c0, c1 + 1)) if axis in ("cols", "cross") else set()
    return {(r, c) for r in range(H) for c in range(W)
            if (r in rows or c in cols) and G[r, c] == BG and (r, c) not in O}


def dilate(O, G, m):
    H, W = G.shape
    return {(r, c) for r in range(H) for c in range(W)
            if G[r, c] == BG and (r, c) not in O
            and sum((r + dr, c + dc) in O for dr in (-1, 0, 1) for dc in (-1, 0, 1) if dr or dc) >= m}


def connect(O, G):
    """Background cells strictly between two object cells on one row or column, only background between."""
    out = set()
    by_row, by_col = {}, {}
    for r, c in O:
        by_row.setdefault(r, []).append(c)
        by_col.setdefault(c, []).append(r)
    for r, cs in by_row.items():
        cs.sort()
        for a, b in zip(cs, cs[1:]):
            seg = [(r, c) for c in range(a + 1, b)]
            if seg and all(G[x] == BG for x in seg):
                out |= set(seg)
    for c, rs in by_col.items():
        rs.sort()
        for a, b in zip(rs, rs[1:]):
            seg = [(r, c) for r in range(a + 1, b)]
            if seg and all(G[x] == BG for x in seg):
                out |= set(seg)
    return out


def copies(O, G, dr, dc, until_border):
    H, W = G.shape
    out, k = set(), 1
    while k <= 30:
        inside = {(r + k * dr, c + k * dc) for r, c in O}
        inside = {x for x in inside if 0 <= x[0] < H and 0 <= x[1] < W}
        if not inside:
            break
        out |= inside - O
        if not until_border:
            break
        k += 1
    return out


def copies_bbox(O, G, sr, sc, gap, until_border):
    r0, r1, c0, c1 = bbox(O)
    return copies(O, G, sr * (r1 - r0 + 1 + gap), sc * (c1 - c0 + 1 + gap), until_border)


#: the families, their parameter domains (finite) and functions
FAMILIES = {
    "window_fill": ({"k": (2, 3, 4, 5)}, window_fill),
    "empty_square": ({"k": (2, 3, 4, 5)}, empty_square),
    "bbox_fill": ({}, bbox_fill),
    "bbox_ring": ({}, bbox_ring),
    "band": ({"axis": ("rows", "cols", "cross")}, band),
    "dilate": ({"m": (1, 2, 3, 4)}, dilate),
    "connect": ({}, connect),
    "copies_bbox": ({"sr": (1, -1, 0), "sc": (1, -1, 0), "gap": (0, 1), "until_border": (False, True)}, copies_bbox),
    "copies_offset": ({"dr": tuple(range(-4, 5)), "dc": tuple(range(-4, 5)), "until_border": (False, True)}, copies),
}


def settings(families=None):
    """Every (family, params) in deterministic order, within the finite domains."""
    for fam in (families or FAMILIES):
        domain, _fn = FAMILIES[fam]
        keys = sorted(domain)
        for values in itertools.product(*(domain[k] for k in keys)):
            params = dict(zip(keys, values))
            if fam == "copies_bbox" and params["sr"] == 0 and params["sc"] == 0:
                continue
            if fam == "copies_offset" and params["dr"] == 0 and params["dc"] == 0:
                continue
            yield fam, params


def apply(family, params, O, G):
    _domain, fn = FAMILIES[family]
    return fn(set(O), G, **params)
