"""Grid utilities and pixel-grounded views for CAST (numpy, deterministic, no background-0 assumption).

Conventions (declared once, used everywhere):
- A grid is a 2-D numpy int array with values 0..9. Coordinates are (row, col), row 0 at the top.
- Background of a grid = its majority colour; ties go to the smallest colour value. Never assumed to be 0.
- Connectivity: 4 = edge neighbours; 8 = edge or corner neighbours. A "mono" object is a connected set of cells of one
  colour; a "multi" object is a connected set of non-background cells of any colours.
- An enclosed region (hole) of a mask M is a 4-connected component of the complement of M that does not touch the
  grid border. With 8-connected objects, holes use 4-connectivity of the complement (the standard digital-topology
  pairing (8, 4)); with 4-connected objects the pairing is (4, 8). Both are offered; callers state which.
Every entity keeps its source mask, its box and its cells, so rendering back to a grid is exact.
"""
from dataclasses import dataclass, field

import numpy as np
from . import _nd as ndimage

S4 = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], dtype=bool)
S8 = np.ones((3, 3), dtype=bool)


def A(g):
    return np.asarray(g, dtype=np.int64)


def bg_of(g):
    """Majority colour; ties -> smallest colour value."""
    cnt = np.bincount(A(g).ravel(), minlength=10)
    return int(np.argmax(cnt))


def palette(g):
    return frozenset(int(v) for v in np.unique(A(g)))


def counts(g):
    return np.bincount(A(g).ravel(), minlength=10)[:10]


def label(mask, conn=4):
    lab, n = ndimage.label(mask, structure=S4 if conn == 4 else S8)
    return lab, n


@dataclass
class Obj:
    """A connected entity: its mask on the source grid, box (r0, c0, r1, c1) inclusive, colours and cell values."""
    mask: np.ndarray
    box: tuple
    colours: frozenset
    size: int
    idx: int = 0
    tags: dict = field(default_factory=dict)

    @property
    def h(self):
        return self.box[2] - self.box[0] + 1

    @property
    def w(self):
        return self.box[3] - self.box[1] + 1

    def patch(self, g, fill=-1):
        """The object's box cut from g, cells outside the mask set to `fill`."""
        r0, c0, r1, c1 = self.box
        p = A(g)[r0:r1 + 1, c0:c1 + 1].copy()
        p[~self.mask[r0:r1 + 1, c0:c1 + 1]] = fill
        return p

    def shape_key(self):
        r0, c0, r1, c1 = self.box
        return self.mask[r0:r1 + 1, c0:c1 + 1].tobytes() + bytes([self.h, self.w])

    @property
    def colour(self):
        return min(self.colours) if len(self.colours) == 1 else -1


def _box(mask):
    rows = np.where(mask.any(1))[0]
    cols = np.where(mask.any(0))[0]
    return (int(rows[0]), int(cols[0]), int(rows[-1]), int(cols[-1]))


def objects(g, bg=None, conn=4, mono=True):
    """Objects of g under a declared view; bg defaults to the grid's majority colour."""
    g = A(g)
    if bg is None:
        bg = bg_of(g)
    out = []
    if mono:
        for c in sorted(set(np.unique(g).tolist()) - {bg}):
            lab, n = label(g == c, conn)
            for i in range(1, n + 1):
                m = lab == i
                out.append(Obj(m, _box(m), frozenset([c]), int(m.sum())))
    else:
        lab, n = label(g != bg, conn)
        for i in range(1, n + 1):
            m = lab == i
            out.append(Obj(m, _box(m), frozenset(int(v) for v in np.unique(g[m])), int(m.sum())))
    out.sort(key=lambda o: (o.box[0], o.box[1], o.colour, o.size))
    for i, o in enumerate(out):
        o.idx = i
    return out


def holes_of_mask(mask, conn_bg=4):
    """Enclosed regions of the complement of mask (components not touching the border)."""
    comp = ~mask
    lab, n = label(comp, conn_bg)
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]])).tolist())
    return [lab == i for i in range(1, n + 1) if i not in border]


def hole_count(obj, conn_bg=4):
    r0, c0, r1, c1 = obj.box
    m = np.pad(obj.mask[r0:r1 + 1, c0:c1 + 1], 1)
    return len(holes_of_mask(m, conn_bg))


def enclosed_background(g, bg=None, conn_bg=4):
    """Background cells not connected (conn_bg) to the border through background cells."""
    g = A(g)
    if bg is None:
        bg = bg_of(g)
    lab, n = label(g == bg, conn_bg)
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]])).tolist())
    keep = np.zeros(g.shape, dtype=bool)
    for i in range(1, n + 1):
        if i not in border:
            keep |= lab == i
    return keep


def separators(g):
    """Full rows/columns of one non-background-or-background colour that cut the grid into panels.
    Returns (colour, row indices, col indices) for the colour with the most full lines, or None."""
    g = A(g)
    h, w = g.shape
    best = None
    for c in np.unique(g).tolist():
        rows = [r for r in range(h) if (g[r] == c).all()]
        cols = [k for k in range(w) if (g[:, k] == c).all()]
        if (rows or cols) and len(rows) < h and len(cols) < w:
            score = len(rows) + len(cols)
            if best is None or score > best[0]:
                best = (score, c, rows, cols)
    if best is None:
        return None
    return best[1], best[2], best[3]


def panels(g):
    """Panels cut by the separator lines (row-major order), as (r0, c0, r1, c1) inclusive boxes; [] if none."""
    g = A(g)
    s = separators(g)
    if s is None:
        return []
    _, rows, cols = s
    h, w = g.shape

    def spans(lines, n):
        out, start = [], 0
        for x in sorted(lines) + [n]:
            if x > start:
                out.append((start, x - 1))
            start = x + 1
        return out
    rs, cs = spans(rows, h), spans(cols, w)
    if len(rs) * len(cs) < 2:
        return []
    return [(a, b, c, d) for a, c in rs for b, d in cs]


def crop(g, box):
    r0, c0, r1, c1 = box
    return A(g)[r0:r1 + 1, c0:c1 + 1].copy()


def bbox_of(mask):
    if not mask.any():
        return None
    return _box(mask)


def grid_key(g):
    g = A(g)
    return g.shape, g.tobytes()


def valid_grid(g):
    if g is None:
        return False
    g = np.asarray(g)
    return g.ndim == 2 and 1 <= g.shape[0] <= 30 and 1 <= g.shape[1] <= 30 and g.min() >= 0 and g.max() <= 9
