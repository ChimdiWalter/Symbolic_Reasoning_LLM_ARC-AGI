"""Rule-language version 5 programs (internal label ncv2-g5): version 4's programs (an ncv2 base program or the
identity, then part and ray rules) plus four rule types over the INPUT grid's native objects of one view:

- `StampRule(src, anchors, scope, align, recolour)`: the pattern of the one object `src` picks (its own cells, or every
  non-background cell of its box) is copied onto each object `anchors` picks, aligned by the boxes' top-left corners,
  their centres, or a marker (the anchor is one cell and the pattern holds exactly one cell of the anchor's colour);
  `recolour="anchor"` paints the copy in the anchor's colour;
- `Ray2Rule(sel, dirs, mode, hit, colour)`: rays as in version 4, which also act on the obstacle they reach (`hit`:
  paint the cell they hit, or the whole object they hit) and may turn once, clockwise or anticlockwise, at it;
- `SegmentRule(sel, axes, colour)`: for every pair of picked objects, every row (or column) in which both have cells is
  joined across the background between their facing cells, when that gap is all background;
- `FillRule(sel, kind, colour)`: background regions closed off from the grid edge whose neighbouring objects are all
  picked ("enclosed"), or the background box between two picked objects that face each other ("between").

`colour` is an int or "own" (the picked object's colour; for pairs and regions, the colour the objects share).
Which objects a selector picks is decided by native CORA, as in version 4, so selector semantics are never
re-implemented. Version 4's rules are executed exactly as version 4 executes them (the tests check parity).

Level: L1, an engineering extension of version 4's rule vocabulary (records/CORA_NOVELTY_AND_IMPROVEMENT_LEDGER_20261022.md).
"""
import functools
import itertools
from typing import NamedTuple

import numpy as np

from cora_neural_v2.rast import ASTError
from cora_neural_v2g3 import delta as D
from cora_neural_v2g4 import program as PG

DIRS8 = PG.DIRS8
N4 = ((0, 1), (0, -1), (1, 0), (-1, 0))
TURN = {"turn_cw": lambda d: (d[1], -d[0]), "turn_ccw": lambda d: (-d[1], d[0])}
RUNS = {"checks": 0}                   # rule-alone executions spent by construction (reported, not candidates)


class StampRule(NamedTuple):
    src: object
    anchors: object
    scope: str          # "object" | "box"
    align: str          # "topleft" | "centre" | "marker"
    recolour: str       # "keep" | "anchor"


class Ray2Rule(NamedTuple):
    sel: object
    dirs: tuple
    mode: str           # "stop" | "turn_cw" | "turn_ccw"
    hit: str            # "none" | "cell" | "object"
    colour: object


class SegmentRule(NamedTuple):
    sel: object
    axes: str           # "h" | "v" | "hv"
    colour: object


class FillRule(NamedTuple):
    sel: object
    kind: str           # "enclosed" | "between"
    colour: object


G5_RULES = (StampRule, Ray2Rule, SegmentRule, FillRule)


class G5Program(NamedTuple):
    op: str             # always "g5program"
    view: str
    base: object        # an ncv2 program AST, or None for the identity
    rules: tuple        # version 4 rules (PartRule, RayRule) and version 5 rules, applied in order


def make(view, base, rules):
    return G5Program("g5program", view, base, tuple(rules))


@functools.lru_cache(maxsize=512)
def _layout(view, gkey):
    """Object cells, colours and background (native), each cell's object, and the background regions that do not
    touch the grid edge (4-connected)."""
    cells, colours, bg = PG._objects(view, gkey)
    A = np.array(gkey)
    h, w = A.shape
    obj_of = {}
    for j, cs in enumerate(cells):
        for x in cs:
            obj_of[x] = j
    seen, enclosed = set(), []
    for r in range(h):
        for c in range(w):
            if A[r, c] != bg or (r, c) in seen:
                continue
            comp, stack, edge = [], [(r, c)], False
            seen.add((r, c))
            while stack:
                y, x = stack.pop()
                comp.append((y, x))
                edge |= y in (0, h - 1) or x in (0, w - 1)
                for dy, dx in N4:
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and (ny, nx) not in seen and A[ny, nx] == bg:
                        seen.add((ny, nx))
                        stack.append((ny, nx))
            if not edge:
                enclosed.append(frozenset(comp))
    return cells, colours, bg, obj_of, tuple(enclosed)


def _box(cells):
    rs = [r for r, _ in cells]
    cs = [c for _, c in cells]
    return min(rs), max(rs), min(cs), max(cs)


def _colour(rule_colour, own):
    return own if rule_colour == "own" else int(rule_colour)


def stamp_writes(rule, A, cells, colours, bg, src, anchors):
    if len(src) != 1:
        return None
    s = next(iter(src))
    r0, r1, c0, c1 = _box(cells[s])
    if rule.scope == "object":
        pattern = {x: int(A[x]) for x in cells[s]}
    else:
        pattern = {(r, c): int(A[r, c]) for r in range(r0, r1 + 1) for c in range(c0, c1 + 1) if A[r, c] != bg}
    h, w = A.shape
    out = {}
    for j in sorted(anchors - {s}):
        ar0, ar1, ac0, ac1 = _box(cells[j])
        if rule.align == "topleft":
            off = (ar0 - r0, ac0 - c0)
        elif rule.align == "centre":
            off = ((ar0 + ar1) // 2 - (r0 + r1) // 2, (ac0 + ac1) // 2 - (c0 + c1) // 2)
        else:                                                   # marker
            m = [x for x, v in pattern.items() if v == colours[j]]
            if len(cells[j]) != 1 or len(m) != 1:
                continue
            (ar, ac), = tuple(cells[j])
            off = (ar - m[0][0], ac - m[0][1])
        for (r, c), v in pattern.items():
            rr, cc = r + off[0], c + off[1]
            if 0 <= rr < h and 0 <= cc < w:
                out[(rr, cc)] = colours[j] if rule.recolour == "anchor" else v
    return out


def ray2_object_writes(rule, A, cells, colours, bg, obj_of, j, out):
    h, w = A.shape
    own = cells[j]
    col = _colour(rule.colour, colours[j])
    for d in rule.dirs:
        for r, c in sorted(own):
            if (r + d[0], c + d[1]) in own:
                continue
            cur, dd, turned = (r, c), d, False
            while True:
                nr, nc = cur[0] + dd[0], cur[1] + dd[1]
                if not (0 <= nr < h and 0 <= nc < w):
                    break
                if A[nr, nc] != bg:
                    if rule.hit == "cell":
                        out[(nr, nc)] = col
                    elif rule.hit == "object" and (nr, nc) in obj_of:
                        for x in sorted(cells[obj_of[(nr, nc)]]):
                            out[x] = col
                    if rule.mode in TURN and not turned:
                        dd, turned = TURN[rule.mode](dd), True
                        continue
                    break
                out[(nr, nc)] = col
                cur = (nr, nc)
    return out


def _facing_gaps(a, b, axes):
    """Background-candidate gaps between objects a and b (cell sets): per shared row (h) or column (v), the cells
    strictly between their facing cells."""
    gaps = []
    for axis in axes:
        key = (lambda x: x[0]) if axis == "h" else (lambda x: x[1])
        other = (lambda x: x[1]) if axis == "h" else (lambda x: x[0])
        la, lb = {}, {}
        for x in a:
            la.setdefault(key(x), []).append(other(x))
        for x in b:
            lb.setdefault(key(x), []).append(other(x))
        for k in sorted(set(la) & set(lb)):
            ma, mb = max(la[k]), min(lb[k])
            if ma < mb:
                lo, hi = ma, mb
            elif max(lb[k]) < min(la[k]):
                lo, hi = max(lb[k]), min(la[k])
            else:
                continue
            gap = [(k, t) if axis == "h" else (t, k) for t in range(lo + 1, hi)]
            if gap:
                gaps.append(gap)
    return gaps


def segment_writes(rule, A, cells, colours, bg, picks):
    out = {}
    for a, b in itertools.combinations(sorted(picks), 2):
        if rule.colour == "own" and colours[a] != colours[b]:
            continue
        col = _colour(rule.colour, colours[a])
        for gap in _facing_gaps(cells[a], cells[b], rule.axes):
            if all(A[x] == bg for x in gap):
                for x in gap:
                    out[x] = col
    return out


def fill_writes(rule, A, cells, colours, bg, obj_of, enclosed, picks):
    out = {}
    if rule.kind == "enclosed":
        h, w = A.shape
        for comp in enclosed:
            nb = {obj_of[(y + dy, x + dx)] for y, x in comp for dy, dx in N4
                  if 0 <= y + dy < h and 0 <= x + dx < w and (y + dy, x + dx) in obj_of}
            if not nb or not nb <= picks:
                continue
            shared = {colours[k] for k in nb}
            if rule.colour == "own" and len(shared) != 1:
                continue
            col = _colour(rule.colour, next(iter(shared)))
            for x in sorted(comp):
                out[x] = col
        return out
    for a, b in itertools.combinations(sorted(picks), 2):           # "between": the box between facing objects
        if rule.colour == "own" and colours[a] != colours[b]:
            continue
        col = _colour(rule.colour, colours[a])
        ar0, ar1, ac0, ac1 = _box(cells[a])
        br0, br1, bc0, bc1 = _box(cells[b])
        boxes = []
        r_lo, r_hi = max(ar0, br0), min(ar1, br1)
        if r_lo <= r_hi:
            lo, hi = (ac1, bc0) if ac1 < bc0 else (bc1, ac0) if bc1 < ac0 else (None, None)
            if lo is not None:
                boxes.append([(r, c) for r in range(r_lo, r_hi + 1) for c in range(lo + 1, hi)])
        c_lo, c_hi = max(ac0, bc0), min(ac1, bc1)
        if c_lo <= c_hi:
            lo, hi = (ar1, br0) if ar1 < br0 else (br1, ar0) if br1 < ar0 else (None, None)
            if lo is not None:
                boxes.append([(r, c) for r in range(lo + 1, hi) for c in range(c_lo, c_hi + 1)])
        for box in boxes:
            if box and all(A[x] == bg for x in box):
                for x in box:
                    out[x] = col
    return out


def rule_writes(rule, view, A, gkey=None):
    """{cell: colour} that one rule writes on input grid A (numpy), or None when it cannot apply (a selector native
    cannot evaluate, or a stamp source that is not exactly one object)."""
    gkey = PG._key(A) if gkey is None else gkey
    cells, colours, bg, obj_of, enclosed = _layout(view, gkey)
    if isinstance(rule, StampRule):
        src, anc = PG._picks(view, rule.src, gkey), PG._picks(view, rule.anchors, gkey)
        return None if src is None or anc is None else stamp_writes(rule, A, cells, colours, bg, src, anc)
    picks = PG._picks(view, rule.sel, gkey)
    if picks is None:
        return None
    out = {}
    if isinstance(rule, (PG.PartRule, PG.RayRule)):                 # exactly version 4's execution
        for j in sorted(picks):
            col = colours[j] if rule.colour == "own" else int(rule.colour)
            for x in PG.rule_cells(rule, cells[j], A, bg):
                out[x] = col
        return out
    if isinstance(rule, Ray2Rule):
        for j in sorted(picks):
            ray2_object_writes(rule, A, cells, colours, bg, obj_of, j, out)
        return out
    if isinstance(rule, SegmentRule):
        return segment_writes(rule, A, cells, colours, bg, picks)
    if isinstance(rule, FillRule):
        return fill_writes(rule, A, cells, colours, bg, obj_of, enclosed, picks)
    raise ValueError(f"unknown rule type {type(rule).__name__}")


def execute(prog, grid):
    """The output grid, or None (no output, a shape change, or a rule that cannot apply)."""
    A = np.asarray(grid)
    out = A.copy() if prog.base is None else D.execute(prog.base, grid)
    if out is None or np.asarray(out).shape != A.shape:
        return None
    out = np.array(out)
    gkey = PG._key(A)
    for rule in prog.rules:
        W = rule_writes(rule, prog.view, A, gkey)
        if W is None:
            return None
        for x, v in W.items():
            out[x] = v
    return out


def deltas(prog, train, stop_early=False):
    """delta.DemoDelta per demonstration, as ncv2-g3 computes them, through this executor."""
    out = []
    for a, b in train:
        A, B = np.asarray(a), np.asarray(b)
        try:
            res = execute(prog, a)
        except ASTError:
            raise
        except Exception:                                  # noqa: BLE001
            res = None
        if res is None or res.shape != B.shape:
            out.append(D.DemoDelta(False, B.shape, None if res is None else res.shape))
        else:
            wrong = res != B
            diff = A != B
            out.append(D.DemoDelta(True, B.shape, res.shape, wrong, diff & ~wrong, ~diff & wrong, diff & wrong))
        if stop_early and out[-1].n_wrong != 0:
            break
    return out


def fits(prog, train):
    return D.fits(deltas(prog, train, stop_early=True), len(train))
