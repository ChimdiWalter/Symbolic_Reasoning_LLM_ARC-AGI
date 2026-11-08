"""M4, first item: general symmetry completion (a whole-grid program class with a declared contract).

Semantics of SymComplete(c, crop), for an input grid g of shape (h, w) and a mask colour c (a task-level parameter;
never assumed to be 0 and never a background guess):
  1. Known cells K = {p : g[p] != c}; masked cells M = {p : g[p] == c}. Undefined if M is empty.
  2. Candidate symmetries are lattice isometries with ANY centre or axis (no centroid, no cell-count cap):
     reflections about every row axis and column axis at half-integer steps, 180-degree rotations about every
     half-integer centre, 90-degree rotations about every centre that maps the lattice to itself, and reflections
     about every main and anti diagonal offset.
  3. A candidate sigma is VALID on g when (i) at least theta_inside * h * w cells p have sigma(p) inside the grid,
     (ii) at least theta_known * |K| known cells p have sigma(p) known, and (iii) g[p] == g[sigma(p)] for every
     known p with sigma(p) known (exact agreement; background included, so it adapts to any background).
  4. Orbits: the connected components of the graph on cells with an edge p -- sigma(p) for every valid sigma.
     If one orbit holds two different known colours the operator is UNDEFINED on g (returns None). Otherwise every
     masked cell takes its orbit's known colour; masked cells in orbits without a known cell keep colour c
     (undetermined; counted in the trace). The result is independent of the order of symmetries.
  5. crop=False returns the completed grid; crop=True returns the completed grid restricted to the box of M.
Thresholds theta_inside and theta_known are frozen on source-selection data (CAST_select), never on evaluation
outcomes. Defaults 0.5 / 0.5 follow the synthesis review's probe.

Contract (PROVED_OPERATOR_CONTRACT; argument: only cells of M are written, each with a colour copied from a known
cell, i.e. from palette(g) minus c; tests/test_symmetry.py validates it exhaustively on tiny grids):
  crop=False: shape unchanged; footprint subset of M; written colours subset of palette(g) - {c};
              count_c does not increase; count_k (k != c) does not decrease; total cell count unchanged.
  crop=True:  shape == shape of box(M); every output cell outside M keeps g's colour; cells of M take a colour in
              palette(g) - {c} or keep c.
Predecessor relation (crop=False): w[p] in {y[p], c} for every p (and w[p] == c wherever y[p] == c).
"""
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

from cast import absdom as D
from cast import grids as G
from cast.ops import Op

THETA_INSIDE = 0.5
THETA_KNOWN = 0.5


def _maps(h, w, min_inside):
    """Candidate symmetries as (name, (Y', X')) index arrays; analytic overlap pre-filter."""
    Y, X = np.mgrid[0:h, 0:w]
    out = []
    for a in range(0, 2 * w - 1):                         # column axis at a / 2
        if h * (w - abs(a - (w - 1))) >= min_inside:
            out.append((f"flip_lr@{a / 2}", Y, a - X))
    for a in range(0, 2 * h - 1):
        if w * (h - abs(a - (h - 1))) >= min_inside:
            out.append((f"flip_ud@{a / 2}", a - Y, X))
    for a in range(0, 2 * h - 1):
        for b in range(0, 2 * w - 1):
            if (h - abs(a - (h - 1))) * (w - abs(b - (w - 1))) >= min_inside:
                out.append((f"rot180@{a / 2},{b / 2}", a - Y, b - X))
                if (a - b) % 2 == 0:
                    d, s = (a - b) // 2, (a + b) // 2
                    out.append((f"rot90@{a / 2},{b / 2}", X + d, s - Y))
    for k in range(-(h - 1), w):                           # (y, x) -> (x - k, y + k): reflection about y = x - k
        out.append((f"transpose@{k}", X - k, Y + k))
    for s in range(0, h + w - 1):                          # (y, x) -> (s - x, s - y)
        out.append((f"antitranspose@{s}", s - X, s - Y))
    return out


_MAP_CACHE = {}


def maps_for(h, w, theta_inside=THETA_INSIDE):
    key = (h, w, theta_inside)
    if key not in _MAP_CACHE:
        if len(_MAP_CACHE) > 16:
            _MAP_CACHE.clear()
        min_inside = theta_inside * h * w
        res = []
        for name, YY, XX in _maps(h, w, min_inside):
            inside = (YY >= 0) & (YY < h) & (XX >= 0) & (XX < w)
            n_in = int(inside.sum())
            if n_in < min_inside or n_in == 0:
                continue
            src = np.flatnonzero(inside).astype(np.int32)
            dst = (YY[inside] * w + XX[inside]).astype(np.int32)
            if np.array_equal(src, dst):                    # the identity is not a symmetry candidate
                continue
            res.append((name, src, dst))
        _MAP_CACHE[key] = res
    return _MAP_CACHE[key]


def valid_symmetries(g, c, theta_inside=THETA_INSIDE, theta_known=THETA_KNOWN):
    g = np.asarray(g)
    h, w = g.shape
    flat = g.ravel()
    known = flat != c
    nk = int(known.sum())
    if nk == 0:
        return []
    out = []
    for name, src, dst in maps_for(h, w, theta_inside):
        both = known[src] & known[dst]
        nb = int(both.sum())
        if nb < theta_known * nk:
            continue
        if np.array_equal(flat[src[both]], flat[dst[both]]):
            out.append((name, src, dst))
    return out


def complete(g, c, theta_inside=THETA_INSIDE, theta_known=THETA_KNOWN):
    """(completed grid or None, trace dict)."""
    g = np.asarray(g, dtype=np.int64)
    h, w = g.shape
    flat = g.ravel()
    masked = flat == c
    trace = {"mask_colour": int(c), "masked": int(masked.sum())}
    if not masked.any():
        trace["status"] = "UNDEFINED_NO_MASK"
        return None, trace
    syms = valid_symmetries(g, c, theta_inside, theta_known)
    trace["symmetries"] = [s[0] for s in syms]
    if not syms:
        trace["status"] = "UNDEFINED_NO_SYMMETRY"
        return None, trace
    n = h * w
    rows = np.concatenate([s[1] for s in syms])
    cols = np.concatenate([s[2] for s in syms])
    graph = coo_matrix((np.ones(len(rows), dtype=np.int8), (rows, cols)), shape=(n, n))
    ncomp, lab = connected_components(graph, directed=False)
    known = ~masked
    kl, kc = lab[known], flat[known]
    colour_of = np.full(ncomp, -1, dtype=np.int64)
    pairs = np.unique(np.stack([kl, kc], 1), axis=0) if len(kl) else np.zeros((0, 2), dtype=np.int64)
    if len(pairs) and len(np.unique(pairs[:, 0])) != len(pairs):
        trace["status"] = "UNDEFINED_CONFLICT"
        return None, trace
    colour_of[pairs[:, 0]] = pairs[:, 1]
    out = flat.copy()
    fill = colour_of[lab]
    sel = masked & (fill >= 0)
    out[sel] = fill[sel]
    trace["undetermined"] = int((masked & (fill < 0)).sum())
    trace["status"] = "COMPLETE" if trace["undetermined"] == 0 else "PARTIAL"
    return out.reshape(h, w), trace


class SymComplete(Op):
    name = "symcomplete"
    cost = 20
    scope = ("grids up to 30x30; mask colour in the demonstrations' input palette; thresholds frozen on "
             "CAST_select")

    def __init__(self, theta_inside=THETA_INSIDE, theta_known=THETA_KNOWN):
        self.theta_inside, self.theta_known = theta_inside, theta_known
        self.last_trace = None

    @property
    def same_shape(self):
        return False

    def domain(self, ctx):
        return [(c, crop) for c in ctx.in_pal for crop in (False, True)]

    def apply(self, g, th):
        c, crop = th
        out, tr = complete(g, c, self.theta_inside, self.theta_known)
        self.last_trace = tr
        if out is None:
            return None
        if crop:
            box = G.bbox_of(np.asarray(g) == c)
            return G.crop(out, box)
        return out

    # ---- contract
    def _cells_same(self, a, c):
        others = a.pal & ~D.bit(c)
        has_c = ((a.cells >> c) & 1).astype(bool)
        cells = a.cells.copy()
        cells[has_c] |= np.uint16(others)
        return cells

    def fwd(self, a, th):
        c, crop = th
        if a.bottom or not (a.pal >> c & 1):
            return D.BOTTOM()
        lo, hi = a.lo.copy(), a.hi.copy()
        lo_c, hi_c = lo[c], hi[c]
        lo[c] = 0
        for k in range(10):
            if k != c and (a.pal >> k & 1):
                hi[k] = hi[k] + hi_c
        others = a.pal & ~D.bit(c)
        if not crop:
            if a.cells is None:
                return D.Abs(a.shapes, a.shape_lo, None, a.pal, 0, lo, hi)
            return D.Abs(a.shapes, a.shape_lo, self._cells_same(a, c), a.pal, 0, lo, hi)
        if D.is_concrete(a):
            g = D.concretize_one(a)
            box = G.bbox_of(g == c)
            if box is None:
                return D.BOTTOM()
            cells = G.crop(self._cells_same(a, c), box).astype(np.uint16)
            return D.Abs({cells.shape}, (1, 1), cells, a.pal)
        if a.shapes is None:
            return D.Abs(None, (1, 1), None, a.pal)
        shapes = {(hh, ww) for H, W in a.shapes for hh in range(1, H + 1) for ww in range(1, W + 1)}
        return D.Abs(shapes, (1, 1), None, a.pal | others)

    def bwd(self, y, th):
        c, crop = th
        y = np.asarray(y)
        if crop:
            return D.Abs(None, y.shape, None, D.ALL, D.bit(c))
        cells = (D.BITS[y] | np.uint16(D.bit(c))).astype(np.uint16)
        cells[y == c] = D.bit(c)
        return D.Abs({y.shape}, (1, 1), cells, D.ALL, D.bit(c))
