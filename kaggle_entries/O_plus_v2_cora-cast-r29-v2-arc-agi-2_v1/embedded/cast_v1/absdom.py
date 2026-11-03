"""M3 abstract domain: a reduced product of cheap domains over sets of grids.

An abstract value `Abs` describes a SET of grids (its concretization gamma):
    shapes    finite set of (h, w) the grid may have, or None = any shape with h >= shape_lo[0], w >= shape_lo[1]
    cells     (only when exactly one shape is possible) an (h, w) array of 10-bit masks: the colours cell p may take.
              This one domain subsumes the write footprint (cells whose mask is not the singleton of the reference
              grid's value may change; all others are protected) and the per-cell palette.
    pal       may-palette: every colour that occurs is in pal
    need      must-palette: every colour in need occurs
    lo, hi    per-colour cell-count intervals
gamma(A) = {y : shape(y) in shapes (or >= shape_lo), y[p] in cells[p] for all p, colours(y) <= pal,
            need <= colours(y), lo[k] <= count_k(y) <= hi[k]}.
`bottom` is the empty set. join over-approximates the union; meet is exact on each component (the product is
reduced by `normalize`, which only removes grids that cannot be in gamma).

Soundness obligation of every operator contract (cast/ops.py): for an abstract input A and parameter theta,
    {op(theta, z) : z in gamma(A), op defined on z} is a subset of gamma(fwd(A, theta)),
and for a target y, {w : op(theta, w) = y} is a subset of gamma(bwd(y, theta)). Tests: tests/test_contracts_*.py.
"""
import numpy as np

ALL = (1 << 10) - 1
MAXC = 900
BITS = np.array([1 << k for k in range(10)], dtype=np.uint16)
POPC = np.array([bin(i).count("1") for i in range(1 << 10)], dtype=np.int64)


def bit(c):
    return 1 << int(c)


def mask_of(colours):
    m = 0
    for c in colours:
        m |= 1 << int(c)
    return m


def colours_of(m):
    return [k for k in range(10) if m >> k & 1]


class Abs:
    __slots__ = ("shapes", "shape_lo", "cells", "pal", "need", "lo", "hi", "bottom")

    def __init__(self, shapes=None, shape_lo=(1, 1), cells=None, pal=ALL, need=0, lo=None, hi=None, bottom=False):
        self.shapes = None if shapes is None else frozenset(shapes)
        self.shape_lo = tuple(shape_lo)
        self.cells = cells
        self.pal = int(pal)
        self.need = int(need)
        self.lo = np.zeros(10, dtype=np.int64) if lo is None else np.asarray(lo, dtype=np.int64).copy()
        self.hi = np.full(10, MAXC, dtype=np.int64) if hi is None else np.asarray(hi, dtype=np.int64).copy()
        self.bottom = bottom
        if not bottom:
            normalize(self)

    def __repr__(self):
        if self.bottom:
            return "Abs(BOTTOM)"
        sh = "any>=%s" % (self.shape_lo,) if self.shapes is None else sorted(self.shapes)[:4]
        return (f"Abs(shapes={sh}{'...' if self.shapes and len(self.shapes) > 4 else ''}, "
                f"cells={'yes' if self.cells is not None else 'no'}, pal={colours_of(self.pal)}, "
                f"need={colours_of(self.need)})")

    def copy(self):
        if self.bottom:
            return BOTTOM()
        return Abs(self.shapes, self.shape_lo, None if self.cells is None else self.cells.copy(), self.pal,
                   self.need, self.lo, self.hi)

    @property
    def single_shape(self):
        if self.shapes is not None and len(self.shapes) == 1:
            return next(iter(self.shapes))
        return None

    def footprint(self, ref):
        """Cells that may differ from the reference grid `ref` (None if not aligned)."""
        if self.cells is None or self.cells.shape != np.asarray(ref).shape:
            return None
        return self.cells != BITS[np.asarray(ref)]


def BOTTOM():
    a = Abs.__new__(Abs)
    a.shapes, a.shape_lo, a.cells, a.pal, a.need = frozenset(), (1, 1), None, 0, 0
    a.lo, a.hi, a.bottom = np.zeros(10, dtype=np.int64), np.zeros(10, dtype=np.int64), True
    return a


def TOP():
    return Abs()


LOG2 = np.zeros(1 << 10, dtype=np.int64)
for _k in range(10):
    LOG2[1 << _k] = _k
KS = np.arange(10)


def _bits(m):
    return (int(m) >> KS) & 1


def normalize(a):
    """Tighten the reduced product in place; set bottom when gamma is provably empty."""
    if a.shapes is not None:
        a.shapes = frozenset(s for s in a.shapes if s[0] >= a.shape_lo[0] and s[1] >= a.shape_lo[1]
                             and 1 <= s[0] <= 30 and 1 <= s[1] <= 30)
        if not a.shapes:
            return _bot(a)
        if len(a.shapes) > 1:
            a.cells = None
    if a.cells is not None:
        if a.shapes is None or len(a.shapes) != 1 or a.cells.shape != next(iter(a.shapes)):
            a.cells = None
    if a.cells is not None:
        a.cells = (a.cells & np.uint16(a.pal)).astype(np.uint16)
        flat = a.cells.ravel().astype(np.int64)
        if (flat == 0).any():
            return _bot(a)
        a.pal &= int(np.bitwise_or.reduce(flat))
        single = POPC[flat] == 1
        fixed = np.bincount(LOG2[flat[single]], minlength=10)[:10]
        may = ((flat[:, None] >> KS) & 1).sum(0)
        a.lo = np.maximum(a.lo, fixed)
        a.hi = np.minimum(a.hi, may)
    a.hi = np.where(_bits(a.pal) == 1, a.hi, 0)
    a.lo = np.where(_bits(a.need) == 1, np.maximum(a.lo, 1), a.lo)
    pos = np.nonzero(a.lo > 0)[0]
    for k in pos:
        a.need |= 1 << int(k)
    if a.need & ~a.pal or (a.lo > a.hi).any():
        return _bot(a)
    if a.shapes is not None:
        nmax = max(h * w for h, w in a.shapes)
        nmin = min(h * w for h, w in a.shapes)
        if a.lo.sum() > nmax or a.hi.sum() < nmin:
            return _bot(a)
    return a


def _bot(a):
    b = BOTTOM()
    for s in Abs.__slots__:
        setattr(a, s, getattr(b, s))
    return a


BITW = np.array([1 << k for k in range(10)], dtype=np.int64)


def alpha(g):
    """Exact abstraction of one concrete grid (already reduced; built without normalize)."""
    g = np.asarray(g, dtype=np.int64)
    cnt = np.bincount(g.ravel(), minlength=10)[:10]
    m = int(BITW[cnt > 0].sum())
    a = Abs.__new__(Abs)
    a.shapes, a.shape_lo, a.cells = frozenset([g.shape]), (1, 1), BITS[g]
    a.pal = a.need = m
    a.lo, a.hi, a.bottom = cnt.copy(), cnt.copy(), False
    return a


def contains(a, y):
    """y in gamma(a)."""
    if a.bottom:
        return False
    y = np.asarray(y, dtype=np.int64)
    if a.shapes is not None and y.shape not in a.shapes:
        return False
    if a.shapes is None and (y.shape[0] < a.shape_lo[0] or y.shape[1] < a.shape_lo[1]):
        return False
    cnt = np.bincount(y.ravel(), minlength=10)[:10]
    cy = int(BITW[cnt > 0].sum())
    if cy & ~a.pal or a.need & ~cy:
        return False
    if (cnt < a.lo).any() or (cnt > a.hi).any():
        return False
    if a.cells is not None and not ((a.cells & BITS[y]) != 0).all():
        return False
    return True


def join(a, b):
    if a.bottom:
        return b.copy()
    if b.bottom:
        return a.copy()
    if a.shapes is None or b.shapes is None:
        shapes = None
        lo_a = a.shape_lo if a.shapes is None else (min(s[0] for s in a.shapes), min(s[1] for s in a.shapes))
        lo_b = b.shape_lo if b.shapes is None else (min(s[0] for s in b.shapes), min(s[1] for s in b.shapes))
        shape_lo = (min(lo_a[0], lo_b[0]), min(lo_a[1], lo_b[1]))
    else:
        shapes = a.shapes | b.shapes
        shape_lo = (1, 1)
    cells = None
    if (a.cells is not None and b.cells is not None and a.cells.shape == b.cells.shape and shapes is not None
            and len(shapes) == 1):
        cells = a.cells | b.cells
    return Abs(shapes, shape_lo, cells, a.pal | b.pal, a.need & b.need, np.minimum(a.lo, b.lo),
               np.maximum(a.hi, b.hi))


def meet(a, b):
    if a.bottom or b.bottom:
        return BOTTOM()
    if a.shapes is None and b.shapes is None:
        shapes = None
    elif a.shapes is None:
        shapes = b.shapes
    elif b.shapes is None:
        shapes = a.shapes
    else:
        shapes = a.shapes & b.shapes
    shape_lo = (max(a.shape_lo[0], b.shape_lo[0]), max(a.shape_lo[1], b.shape_lo[1]))
    cells = None
    if a.cells is not None and b.cells is not None:
        if a.cells.shape != b.cells.shape:
            return BOTTOM()
        cells = a.cells & b.cells
    elif a.cells is not None:
        cells = a.cells.copy()
    elif b.cells is not None:
        cells = b.cells.copy()
    return Abs(shapes, shape_lo, cells, a.pal & b.pal, a.need | b.need, np.maximum(a.lo, b.lo),
               np.minimum(a.hi, b.hi))


def join_all(items):
    out = BOTTOM()
    for x in items:
        out = join(out, x)
    return out


def is_concrete(a):
    return (not a.bottom and a.cells is not None and bool((POPC[a.cells] == 1).all()))


def concretize_one(a):
    """The single grid of a concrete abstract value."""
    assert is_concrete(a)
    return np.log2(a.cells.astype(np.float64)).round().astype(np.int64)


def sample(a, rng, tries=50):
    """A random member of gamma(a) when cells are known (rejection on the count/need constraints); else None."""
    if a.bottom or a.cells is None:
        return None
    opts = [[k for k in range(10) if m >> k & 1] for m in a.cells.ravel()]
    for _ in range(tries):
        y = np.array([rng.choice(o) for o in opts], dtype=np.int64).reshape(a.cells.shape)
        if contains(a, y):
            return y
    return None
