"""Generic operator-schema language SIGMA for Test S1 (frozen with protocols/TEST_S1_PROTOCOL.md).

An operator is one STRUCTURE from four families, plus (for some structures) one integer parameter k in {2, 3, 4}.
Grids are tuples of tuples of colours 0..9; an operator returns a grid or None (undefined).
bg(g) = the most common colour of g (ties to the smallest colour).

SEL(rp, cp)      keep the rows whose row predicate holds and the columns whose column predicate holds.
                 Predicates (on one line of cells, with its index t and the line count n):
                   all        always
                   multi      the line holds at least two different colours
                   fore       the line holds at least one cell different from bg(g)
                   inner      0 < t < n - 1
                   mod        t % k == 0                  (uses k)
                 Undefined if no row or no column is kept. (all, all) is excluded (identity).
MAP(rr, cr, tr)  out[i][j] = src[rho(i)][gam(j)], src = g transposed if tr else g; n = the source's row (column)
                 count; rules give the output size and the source index:
                   same       size n,          index t
                   flip       size n,          index n - 1 - t
                   spread     size n * k,      index t // k   (uses k)
                   sample     size ceil(n / k), index t * k   (uses k)
                   core       size n - 2,      index t + 1    (undefined if n < 3)
                 (same, same, False) is excluded (identity). Both axes share k.
BLOCK(red)       cut g into k x k blocks (the last ones may be smaller), one output cell per block:
                   first      the block's top-left cell
                   mode       the block's most common colour (ties to the smallest)
                   fore       the block's first cell different from bg(g) in row-major order, else bg(g)
COLOUR(a, b, s)  s = False: every cell of colour a becomes b; s = True: colours a and b are exchanged (a < b).

Enumeration order (fixed): SEL (rp, cp in predicate order), MAP (rr, cr in rule order, tr False then True), BLOCK,
COLOUR (a, b ascending; replace before exchange). Each structure is identified by a string such as
"MAP:sample:sample:0". Seeded orders are random permutations of this list (random.Random(seed).shuffle).

CAST interface (cast/contract_check.py): domain(ctx) -> [(k,), ...] or [()], apply(g, th) on numpy arrays,
fwd(A, th) and bwd(y, th) on cast.absdom values. The transformers are sound over-approximations: shapes and
palettes are propagated exactly where they are determined; per-cell masks are propagated for MAP when the input
has one known shape; everything else is widened to TOP.
"""
import math
import random

KS = (2, 3, 4)
PRED = ("all", "multi", "fore", "inner", "mod")
RULE = ("same", "flip", "spread", "sample", "core")
RED = ("first", "mode", "fore")


def bg(g):
    cnt = [0] * 10
    for r in g:
        for v in r:
            cnt[v] += 1
    return max(range(10), key=lambda c: (cnt[c], -c))


def _pred(name, line, t, n, k, b):
    if name == "all":
        return True
    if name == "multi":
        return len(set(line)) > 1
    if name == "fore":
        return any(v != b for v in line)
    if name == "inner":
        return 0 < t < n - 1
    if name == "mod":
        return t % k == 0
    raise ValueError(name)


def _rule_size(rule, n, k):
    if rule in ("same", "flip"):
        return n
    if rule == "spread":
        return n * k
    if rule == "sample":
        return -(-n // k)
    if rule == "core":
        return n - 2
    raise ValueError(rule)


def _rule_idx(rule, t, n, k):
    if rule == "same":
        return t
    if rule == "flip":
        return n - 1 - t
    if rule == "spread":
        return t // k
    if rule == "sample":
        return t * k
    if rule == "core":
        return t + 1
    raise ValueError(rule)


class Structure:
    __slots__ = ("sid", "family", "args", "param")

    def __init__(self, family, args):
        self.family, self.args = family, tuple(args)
        self.sid = family + ":" + ":".join(str(int(a)) if isinstance(a, bool) else str(a) for a in args)
        if family == "SEL":
            self.param = "mod" in args
        elif family == "MAP":
            self.param = any(a in ("spread", "sample") for a in args[:2])
        elif family == "BLOCK":
            self.param = True
        else:
            self.param = False

    def thetas(self):
        return [(k,) for k in KS] if self.param else [()]

    def __call__(self, g, *th):
        k = th[0] if th else None
        if not g or not g[0]:
            return None
        H, W = len(g), len(g[0])
        if self.family == "SEL":
            rp, cp = self.args
            b = bg(g)
            rows = [i for i in range(H) if _pred(rp, g[i], i, H, k, b)]
            cols = [j for j in range(W) if _pred(cp, tuple(g[i][j] for i in range(H)), j, W, k, b)]
            if not rows or not cols:
                return None
            return tuple(tuple(g[i][j] for j in cols) for i in rows)
        if self.family == "MAP":
            rr, cr, tr = self.args
            src = tuple(zip(*g)) if tr else g
            h, w = len(src), len(src[0])
            oh, ow = _rule_size(rr, h, k), _rule_size(cr, w, k)
            if oh < 1 or ow < 1 or oh > 30 or ow > 30:
                return None
            ri = [_rule_idx(rr, i, h, k) for i in range(oh)]
            ci = [_rule_idx(cr, j, w, k) for j in range(ow)]
            return tuple(tuple(src[a][c] for c in ci) for a in ri)
        if self.family == "BLOCK":
            red, = self.args
            b = bg(g)
            out = []
            for i0 in range(0, H, k):
                row = []
                for j0 in range(0, W, k):
                    cells = [g[i][j] for i in range(i0, min(H, i0 + k)) for j in range(j0, min(W, j0 + k))]
                    if red == "first":
                        row.append(cells[0])
                    elif red == "mode":
                        row.append(max(range(10), key=lambda c: (cells.count(c), -c)))
                    else:
                        row.append(next((v for v in cells if v != b), b))
                out.append(tuple(row))
            return tuple(out)
        if self.family == "COLOUR":
            a, b2, s = self.args
            if s:
                return tuple(tuple(b2 if v == a else (a if v == b2 else v) for v in r) for r in g)
            return tuple(tuple(b2 if v == a else v for v in r) for r in g)
        raise ValueError(self.family)


def structures():
    out = []
    for rp in PRED:
        for cp in PRED:
            if (rp, cp) != ("all", "all"):
                out.append(Structure("SEL", (rp, cp)))
    for rr in RULE:
        for cr in RULE:
            for tr in (False, True):
                if (rr, cr, tr) != ("same", "same", False):
                    out.append(Structure("MAP", (rr, cr, tr)))
    for red in RED:
        out.append(Structure("BLOCK", (red,)))
    for a in range(10):
        for b in range(10):
            if a != b:
                out.append(Structure("COLOUR", (a, b, False)))
    for a in range(10):
        for b in range(a + 1, 10):
            out.append(Structure("COLOUR", (a, b, True)))
    return out


def seeded_order(seed):
    s = structures()
    random.Random(f"s1-order-{seed}").shuffle(s)
    return s


def by_sid():
    return {s.sid: s for s in structures()}


def consistent(st, pairs):
    """Parameter values theta for which the structure maps every hole input to its target."""
    out = []
    for th in st.thetas():
        ok = True
        for x, y in pairs:
            try:
                v = st(x, *th)
            except (IndexError, ValueError, ZeroDivisionError):
                v = None
            if v != y:
                ok = False
                break
        if ok:
            out.append(th)
    return out


# ------------------------------------------------------------------ CAST adapter (numpy; cast.absdom values)
class CastOp:
    """A SIGMA structure with CAST's operator interface, for cast.contract_check.check_operator."""
    evidence = "SCHEMA_CONTRACT"
    scope = "grids up to 30x30, k in {2, 3, 4}"
    cost = 1

    def __init__(self, st, D, np):
        self.st, self.D, self.np = st, D, np
        self.name = "sigma_" + st.sid.replace(":", "_")
        self.same_shape = st.family == "COLOUR"

    def domain(self, ctx):
        return self.st.thetas()

    def label(self, th):
        return f"{self.name}{th}"

    def apply(self, g, th):
        y = self.st(tuple(tuple(int(v) for v in r) for r in self.np.asarray(g).tolist()), *th)
        return None if y is None else self.np.asarray(y, dtype=self.np.int64)

    def _out_shapes(self, shp, th):
        k = th[0] if th else None
        h, w = shp
        f = self.st.family
        if f == "COLOUR":
            return {(h, w)}
        if f == "BLOCK":
            return {(-(-h // k), -(-w // k))}
        if f == "MAP":
            rr, cr, tr = self.st.args
            sh, sw = (w, h) if tr else (h, w)
            oh, ow = _rule_size(rr, sh, k), _rule_size(cr, sw, k)
            return {(oh, ow)} if oh >= 1 and ow >= 1 and oh <= 30 and ow <= 30 else set()
        return {(a, b) for a in range(1, h + 1) for b in range(1, w + 1)}       # SEL

    def fwd(self, a, th):
        D, np = self.D, self.np
        if a.bottom:
            return D.BOTTOM()
        f = self.st.family
        if f == "COLOUR":
            return D.Abs(a.shapes, a.shape_lo, None, D.ALL)
        if a.shapes is None:
            return D.Abs(None, (1, 1), None, a.pal if f != "COLOUR" else D.ALL)
        shapes = set()
        for s in a.shapes:
            shapes |= self._out_shapes(s, th)
        if not shapes:
            return D.BOTTOM()
        cells = None
        if f == "MAP" and a.cells is not None and len(a.shapes) == 1:
            (h, w), = a.shapes
            rr, cr, tr = self.st.args
            k = th[0] if th else None
            src = a.cells.T if tr else a.cells
            sh, sw = src.shape
            oh, ow = _rule_size(rr, sh, k), _rule_size(cr, sw, k)
            ri = [_rule_idx(rr, i, sh, k) for i in range(oh)]
            ci = [_rule_idx(cr, j, sw, k) for j in range(ow)]
            cells = np.array([[src[x][c] for c in ci] for x in ri], dtype=np.uint16)
        return D.Abs(shapes, (1, 1), cells, a.pal)

    def bwd(self, y, th):
        D = self.D
        y = self.np.asarray(y)
        need = D.mask_of(set(int(v) for v in y.ravel()))
        f = self.st.family
        if f == "COLOUR":
            return D.Abs({y.shape}, y.shape, None, D.ALL)
        if f == "SEL":
            return D.Abs(None, y.shape, None, D.ALL, need)
        h, w = y.shape
        if f == "BLOCK":
            k = th[0]
            shapes = {(a, b) for a in range(k * (h - 1) + 1, k * h + 1) for b in range(k * (w - 1) + 1, k * w + 1)
                      if a <= 30 and b <= 30}
            return D.Abs(shapes, (1, 1), None, D.ALL, need) if shapes else D.BOTTOM()
        shapes = set()
        for a in range(1, 31):
            for b in range(1, 31):
                if (h, w) in self._out_shapes((a, b), th):
                    shapes.add((a, b))
        return D.Abs(shapes, (1, 1), None, D.ALL, need) if shapes else D.BOTTOM()
