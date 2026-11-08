"""CAST operator library L0 with declared contracts (M3) and the task context that sets parameter domains.

Every operator class declares:
    domain(ctx)        finite parameter domain for a task (built from the demonstrations' colours and shapes only:
                       an OBSERVED_DEMONSTRATION_CONSTRAINT that defines the grammar instance; never from queries'
                       outputs, which the solver cannot read)
    apply(g, th)       concrete semantics; returns a grid or None (undefined); deterministic, bounded, no I/O
    fwd(a, th)         cheap forward contract (PROVED_OPERATOR_CONTRACT): gamma(fwd(a, th)) contains apply(z, th) for
                       every z in gamma(a) where apply is defined. It must not run the operator's expensive part.
    bwd(y, th)         predecessor relation: gamma(bwd(y, th)) contains every w with apply(w, th) == y
    cost               nominal execution cost unit (CPU is measured separately)
Contracts are validated exhaustively on tiny grids and by randomized property tests (tests/test_contracts_*.py);
the declared scope is the finite parameter domain and grids up to 30 x 30.
Overlap semantics: every L0 operator is a whole-grid function (one synchronous write of the full output).
"""
import numpy as np

from cast import absdom as D
from cast import grids as G

GEO = ("fliplr", "flipud", "rot90", "rot180", "rot270", "transpose", "antitranspose")


def geo_apply(g, t):
    g = np.asarray(g)
    return {"fliplr": lambda x: x[:, ::-1], "flipud": lambda x: x[::-1, :], "rot90": lambda x: np.rot90(x, 1),
            "rot180": lambda x: np.rot90(x, 2), "rot270": lambda x: np.rot90(x, 3), "transpose": lambda x: x.T,
            "antitranspose": lambda x: np.rot90(x, 2).T}[t](g).copy()


GEO_INV = {"fliplr": "fliplr", "flipud": "flipud", "rot90": "rot270", "rot180": "rot180", "rot270": "rot90",
           "transpose": "transpose", "antitranspose": "antitranspose"}


def geo_shape(s, t):
    return (s[1], s[0]) if t in ("rot90", "rot270", "transpose", "antitranspose") else s


class TaskCtx:
    """What a grammar instance may depend on: demonstrations (inputs and outputs) and query INPUTS only."""

    def __init__(self, train, test_inputs=()):
        self.train = [(np.asarray(x, dtype=np.int64), np.asarray(y, dtype=np.int64)) for x, y in train]
        self.test_inputs = [np.asarray(x, dtype=np.int64) for x in test_inputs]
        self.in_pal = sorted(set().union(*[G.palette(x) for x, _ in self.train]))
        self.out_pal = sorted(set().union(*[G.palette(y) for _, y in self.train]))
        self.all_pal = sorted(set(self.in_pal) | set(self.out_pal))
        self.same_shape = all(x.shape == y.shape for x, y in self.train)


class Op:
    name = "op"
    cost = 1
    evidence = "PROVED_OPERATOR_CONTRACT"
    scope = "grids up to 30x30, the listed parameter domain"
    same_shape = True

    def domain(self, ctx):
        return [()]

    def apply(self, g, th):
        raise NotImplementedError

    def fwd(self, a, th):
        return D.TOP()

    def bwd(self, y, th):
        return D.TOP()

    def label(self, th):
        return f"{self.name}{th}"


def _same_shape_cells_or_top(a, newbits_fn):
    """Helper: per-cell transfer when cells are known; otherwise only shapes and palette are kept."""
    if a.bottom:
        return D.BOTTOM()
    if a.cells is None:
        return D.Abs(a.shapes, a.shape_lo, None, D.ALL)
    return D.Abs(a.shapes, a.shape_lo, newbits_fn(a.cells), D.ALL)


class Identity(Op):
    name = "id"

    def apply(self, g, th):
        return np.asarray(g).copy()

    def fwd(self, a, th):
        return a.copy()

    def bwd(self, y, th):
        return D.alpha(y)


class Geo(Op):
    name = "geo"
    same_shape = False

    def domain(self, ctx):
        return [(t,) for t in GEO]

    def apply(self, g, th):
        return geo_apply(g, th[0])

    def fwd(self, a, th):
        t = th[0]
        if a.bottom:
            return D.BOTTOM()
        shapes = None if a.shapes is None else {geo_shape(s, t) for s in a.shapes}
        lo = geo_shape(a.shape_lo, t)
        cells = None if a.cells is None else geo_apply(a.cells, t)
        return D.Abs(shapes, lo, cells, a.pal, a.need, a.lo, a.hi)

    def bwd(self, y, th):
        return D.alpha(geo_apply(y, GEO_INV[th[0]]))


class Recolor(Op):
    """Every cell of colour a becomes b (a != b)."""
    name = "recolor"

    def domain(self, ctx):
        return [(a, b) for a in ctx.in_pal for b in ctx.out_pal if a != b]

    def apply(self, g, th):
        a, b = th
        g = np.asarray(g).copy()
        g[g == a] = b
        return g

    def fwd(self, x, th):
        a, b = th
        if x.bottom:
            return D.BOTTOM()

        def mp(m):
            return (m & ~D.bit(a)) | (D.bit(b) if m >> a & 1 else 0)
        lo, hi = x.lo.copy(), x.hi.copy()
        lo[b], hi[b] = lo[b] + lo[a], hi[b] + hi[a]
        lo[a] = hi[a] = 0
        cells = None
        if x.cells is not None:
            has = (x.cells >> a) & 1
            cells = ((x.cells & ~np.uint16(D.bit(a))) | (has * np.uint16(D.bit(b)))).astype(np.uint16)
        return D.Abs(x.shapes, x.shape_lo, cells, mp(x.pal), mp(x.need), lo, hi)

    def bwd(self, y, th):
        a, b = th
        y = np.asarray(y)
        if (y == a).any():
            return D.BOTTOM()
        cells = D.BITS[y].astype(np.uint16)
        cells[y == b] = D.bit(a) | D.bit(b)
        return D.Abs({y.shape}, (1, 1), cells, D.ALL)


SELECTORS = ("nonbg", "largest4", "smallest4", "largest8", "smallest8", "largest_multi8", "colour")


def select_box(g, sel):
    g = np.asarray(g)
    bg = G.bg_of(g)
    if sel[0] == "nonbg":
        return G.bbox_of(g != bg)
    if sel[0] == "colour":
        return G.bbox_of(g == sel[1])
    conn = 8 if sel[0].endswith("8") else 4
    objs = G.objects(g, bg, conn=conn, mono=not sel[0].startswith("largest_multi"))
    if not objs:
        return None
    sizes = [o.size for o in objs]
    target = max(sizes) if sel[0].startswith("largest") else min(sizes)
    cand = [o for o in objs if o.size == target]
    if len(cand) != 1:
        return None                                   # ambiguous extremum: undefined (no tie-break by position)
    return cand[0].box


class CropBox(Op):
    """Crop to the box of a selected region: the non-background cells, one colour, or the unique largest/smallest
    object under a declared view."""
    name = "crop"
    same_shape = False

    def domain(self, ctx):
        return [(s,) for s in SELECTORS if s != "colour"] + [("colour", c) for c in ctx.in_pal]

    def apply(self, g, th):
        box = select_box(g, th)
        if box is None:
            return None
        return G.crop(g, box)

    def fwd(self, a, th):
        if a.bottom:
            return D.BOTTOM()
        if a.shapes is None:
            return D.Abs(None, (1, 1), None, a.pal, 0, None, a.hi)
        if D.is_concrete(a) and th[0] == "colour":            # cheap and exact: the box of one colour
            g = D.concretize_one(a)
            out = self.apply(g, th)
            return D.BOTTOM() if out is None else D.alpha(out)
        shapes = {(h, w) for H, W in a.shapes for h in range(1, H + 1) for w in range(1, W + 1)}
        return D.Abs(shapes, (1, 1), None, a.pal, 0, None, a.hi)

    def bwd(self, y, th):
        y = np.asarray(y)
        cnt = G.counts(y)
        need = D.mask_of(np.unique(y).tolist())
        return D.Abs(None, y.shape, None, D.ALL, need, cnt, None)


class Scale(Op):
    name = "scale"
    same_shape = False

    def domain(self, ctx):
        return [(k,) for k in (2, 3, 4, 5)]

    def apply(self, g, th):
        k = th[0]
        g = np.asarray(g)
        if g.shape[0] * k > 30 or g.shape[1] * k > 30:
            return None
        return np.kron(g, np.ones((k, k), dtype=g.dtype))

    def fwd(self, a, th):
        k = th[0]
        if a.bottom:
            return D.BOTTOM()
        shapes = None if a.shapes is None else {(h * k, w * k) for h, w in a.shapes}
        cells = None if a.cells is None else np.kron(a.cells, np.ones((k, k), dtype=np.uint16)).astype(np.uint16)
        return D.Abs(shapes, (a.shape_lo[0] * k, a.shape_lo[1] * k), cells, a.pal, a.need, a.lo * k * k,
                     np.minimum(a.hi * k * k, D.MAXC))

    def bwd(self, y, th):
        k = th[0]
        y = np.asarray(y)
        h, w = y.shape
        if h % k or w % k:
            return D.BOTTOM()
        small = y[::k, ::k]
        if not np.array_equal(np.kron(small, np.ones((k, k), dtype=y.dtype)), y):
            return D.BOTTOM()
        return D.alpha(small)


class Downscale(Op):
    """Exact block downscale: defined only when the grid is constant on every k x k block."""
    name = "down"
    same_shape = False

    def domain(self, ctx):
        return [(k,) for k in (2, 3, 4, 5)]

    def apply(self, g, th):
        k = th[0]
        g = np.asarray(g)
        h, w = g.shape
        if h % k or w % k:
            return None
        small = g[::k, ::k]
        if not np.array_equal(np.kron(small, np.ones((k, k), dtype=g.dtype)), g):
            return None
        return small.copy()

    def fwd(self, a, th):
        k = th[0]
        if a.bottom:
            return D.BOTTOM()
        if a.shapes is None:
            return D.Abs(None, (1, 1), None, a.pal, a.need)
        shapes = {(h // k, w // k) for h, w in a.shapes if h % k == 0 and w % k == 0 and h >= k and w >= k}
        if not shapes:
            return D.BOTTOM()
        cells = None
        if a.cells is not None and a.cells.shape[0] % k == 0 and a.cells.shape[1] % k == 0:
            h, w = a.cells.shape
            cells = np.bitwise_and.reduce(a.cells.reshape(h // k, k, w // k, k).transpose(0, 2, 1, 3)
                                          .reshape(h // k, w // k, k * k), axis=2).astype(np.uint16)
        return D.Abs(shapes, (1, 1), cells, a.pal, a.need, (a.lo + k * k - 1) // (k * k), a.hi // (k * k))

    def bwd(self, y, th):
        k = th[0]
        y = np.asarray(y)
        if y.shape[0] * k > 30 or y.shape[1] * k > 30:
            return D.BOTTOM()
        return D.alpha(np.kron(y, np.ones((k, k), dtype=y.dtype)))


class Tile(Op):
    name = "tile"
    same_shape = False

    def domain(self, ctx):
        return [(n, m) for n in range(1, 5) for m in range(1, 5) if (n, m) != (1, 1)]

    def apply(self, g, th):
        n, m = th
        g = np.asarray(g)
        if g.shape[0] * n > 30 or g.shape[1] * m > 30:
            return None
        return np.tile(g, (n, m))

    def fwd(self, a, th):
        n, m = th
        if a.bottom:
            return D.BOTTOM()
        shapes = None if a.shapes is None else {(h * n, w * m) for h, w in a.shapes}
        cells = None if a.cells is None else np.tile(a.cells, (n, m)).astype(np.uint16)
        return D.Abs(shapes, (a.shape_lo[0] * n, a.shape_lo[1] * m), cells, a.pal, a.need, a.lo * n * m,
                     np.minimum(a.hi * n * m, D.MAXC))

    def bwd(self, y, th):
        n, m = th
        y = np.asarray(y)
        h, w = y.shape
        if h % n or w % m:
            return D.BOTTOM()
        u = y[:h // n, :w // m]
        if not np.array_equal(np.tile(u, (n, m)), y):
            return D.BOTTOM()
        return D.alpha(u)


class Concat(Op):
    """g next to t(g): side 'h' (left|right) or 'v' (top/bottom), t a same-shape symmetry."""
    name = "concat"
    same_shape = False
    TS = ("id", "fliplr", "flipud", "rot180")

    def domain(self, ctx):
        return [(s, t) for s in "hv" for t in self.TS]

    @staticmethod
    def _t(g, t):
        return np.asarray(g).copy() if t == "id" else geo_apply(g, t)

    def apply(self, g, th):
        s, t = th
        g = np.asarray(g)
        if (s == "h" and g.shape[1] * 2 > 30) or (s == "v" and g.shape[0] * 2 > 30):
            return None
        return np.concatenate([g, self._t(g, t)], axis=1 if s == "h" else 0)

    def fwd(self, a, th):
        s, t = th
        if a.bottom:
            return D.BOTTOM()
        f = (lambda h, w: (h, 2 * w)) if s == "h" else (lambda h, w: (2 * h, w))
        shapes = None if a.shapes is None else {f(*sh) for sh in a.shapes}
        cells = None
        if a.cells is not None:
            cells = np.concatenate([a.cells, self._t(a.cells, t)], axis=1 if s == "h" else 0).astype(np.uint16)
        return D.Abs(shapes, f(*a.shape_lo), cells, a.pal, a.need, a.lo * 2, np.minimum(a.hi * 2, D.MAXC))

    def bwd(self, y, th):
        s, t = th
        y = np.asarray(y)
        h, w = y.shape
        if (s == "h" and w % 2) or (s == "v" and h % 2):
            return D.BOTTOM()
        p, q = (y[:, :w // 2], y[:, w // 2:]) if s == "h" else (y[:h // 2], y[h // 2:])
        inv = q if t == "id" else geo_apply(q, GEO_INV[t])
        return D.meet(D.alpha(p), D.alpha(inv))


class FillEnclosed(Op):
    """Background cells that cannot reach the border through background (4-connected) become colour c."""
    name = "fill_enclosed"

    def domain(self, ctx):
        return [(c,) for c in ctx.out_pal]

    def apply(self, g, th):
        g = np.asarray(g).copy()
        m = G.enclosed_background(g)
        if not m.any():
            return None
        g[m] = th[0]
        return g

    def fwd(self, a, th):
        c = th[0]
        if a.bottom:
            return D.BOTTOM()
        if a.cells is None:
            return D.Abs(a.shapes, a.shape_lo, None, a.pal | D.bit(c))
        cells = a.cells.copy()
        inner = np.zeros(cells.shape, dtype=bool)
        inner[1:-1, 1:-1] = True                        # border cells can never be enclosed
        cells[inner] |= np.uint16(D.bit(c))
        return D.Abs(a.shapes, a.shape_lo, cells, a.pal | D.bit(c))

    def bwd(self, y, th):
        y = np.asarray(y)
        cells = D.BITS[y].astype(np.uint16)
        cells[y == th[0]] = D.ALL
        return D.Abs({y.shape}, (1, 1), cells, D.ALL)


class Outline(Op):
    """Background cells 4- or 8-adjacent to a non-background cell become colour c."""
    name = "outline"

    def domain(self, ctx):
        return [(c, k) for c in ctx.out_pal for k in (4, 8)]

    def apply(self, g, th):
        c, k = th
        g = np.asarray(g)
        bg = G.bg_of(g)
        from scipy import ndimage
        fg = g != bg
        if not fg.any():
            return None
        near = ndimage.binary_dilation(fg, structure=G.S4 if k == 4 else G.S8) & ~fg
        out = g.copy()
        out[near] = c
        return out

    def fwd(self, a, th):
        c = th[0]
        if a.bottom:
            return D.BOTTOM()
        if a.cells is None:
            return D.Abs(a.shapes, a.shape_lo, None, a.pal | D.bit(c))
        return D.Abs(a.shapes, a.shape_lo, (a.cells | np.uint16(D.bit(c))).astype(np.uint16), a.pal | D.bit(c))

    def bwd(self, y, th):
        y = np.asarray(y)
        cells = D.BITS[y].astype(np.uint16)
        cells[y == th[0]] = D.ALL
        return D.Abs({y.shape}, (1, 1), cells, D.ALL)


class Gravity(Op):
    """Cell gravity: in every column (up/down) or row (left/right) the non-background cells slide to that side,
    keeping their order (one synchronous write of the full grid)."""
    name = "gravity"

    def domain(self, ctx):
        return [(d,) for d in ("down", "up", "left", "right")]

    def apply(self, g, th):
        d = th[0]
        g = np.asarray(g)
        bg = G.bg_of(g)
        x = g if d in ("down", "up") else g.T
        out = np.full_like(x, bg)
        for j in range(x.shape[1]):
            col = x[:, j]
            fg = col[col != bg]
            if d in ("down", "right"):
                out[x.shape[0] - len(fg):, j] = fg
            else:
                out[:len(fg), j] = fg
        return out if d in ("down", "up") else out.T

    def fwd(self, a, th):
        d = th[0]
        if a.bottom:
            return D.BOTTOM()
        if a.cells is None:
            return D.Abs(a.shapes, a.shape_lo, None, a.pal, a.need, a.lo, a.hi)
        x = a.cells if d in ("down", "up") else a.cells.T
        u = np.bitwise_or.reduce(x, axis=0)
        out = np.broadcast_to(u, x.shape).copy()
        out = out if d in ("down", "up") else out.T
        return D.Abs(a.shapes, a.shape_lo, out.astype(np.uint16), a.pal, a.need, a.lo, a.hi)

    def bwd(self, y, th):
        d = th[0]
        y = np.asarray(y)
        x = y if d in ("down", "up") else y.T
        u = np.bitwise_or.reduce(D.BITS[x], axis=0)
        out = np.broadcast_to(u, x.shape).copy()
        out = out if d in ("down", "up") else out.T
        cnt = G.counts(y)
        return D.Abs({y.shape}, (1, 1), out.astype(np.uint16), D.ALL, D.mask_of(np.unique(y).tolist()), cnt, cnt)


L0 = [Geo(), Recolor(), CropBox(), Scale(), Downscale(), Tile(), Concat(), FillEnclosed(), Outline(), Gravity()]


def by_name(name, lib=None):
    for op in (lib or L0):
        if op.name == name:
            return op
    raise KeyError(name)
