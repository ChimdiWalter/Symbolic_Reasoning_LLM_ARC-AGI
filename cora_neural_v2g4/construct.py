"""ncv2-g4 evidence-driven construction of part, region and ray rules (proposal C3-C5). Demonstrations only.

1. **Rule shapes from evidence.** For every native object of every demonstration input, and every
   - part kind (parts.py: whole, border, interior, endpoints, corners, contact, holes, bbox_background), and
   - ray shape: a direction set (one of 8 directions, an opposite pair, the 4 orthogonal, the 4 diagonal or all 8)
     and a stop rule (obstacle or through),
   whose cells all take one colour in the output and at least one of them changes, the shape with that colour is a
   candidate. The colour is an int, or "own" (the object's colour) for regions and rays.
2. **Partition.** Under a candidate, an object is a MEMBER when its cells all take the colour and some change, a
   DON'T-CARE when they all already have it (or there are none, such as a ray from an object at the edge), and
   excluded otherwise. invert.induce_selectors finds selectors that pick every member and no excluded object, and
   native execution confirms them. A confirmed rule therefore writes, on every demonstration, only cells the output
   has, and the cells it changes are exactly the members' changed cells.
3. **Cover.** Because no confirmed rule writes a wrong cell, rules never conflict on the demonstrations, and a set of
   them fits exactly when together they change every changed cell. Rules that change the same cells on every
   demonstration are rivals (the demonstrations cannot separate them), ordered by a simplicity prior. Programs are
   greedy covers (the largest first, with two choices of first rule, at most 3 rules): the simplest rules in both
   orders, then each with one rival substituted, of
   - the changed cells: the rules alone;
   - the cells a partial inversion program leaves wrong (invert.py; it writes no wrong cell): that program, then the
     rules, so that objects that change whole (moves, recolourings) and objects that change in part are explained
     together.
Everything here only proposes: the g4 executor and the fit check decide. Native runs spent on construction
(selector checks, partial-program checks) are counted in invert.RUNS: they are not candidate evaluations, so
protocols report them and match compute in CPU time as well.
"""
from typing import NamedTuple

import numpy as np

from cora_neural_v2 import search as G1S
from cora_neural_v2.rast import ASTError
from cora_neural_v2g3 import delta as D
from cora_neural_v2g3 import scene as SC
from cora_neural_v2g4 import invert as INV
from cora_neural_v2g4 import parts as PT
from cora_neural_v2g4 import program as PG

KINDS = PT.KINDS
REGION_KINDS = ("holes", "bbox_background")
R, L, DN, UP = (0, 1), (0, -1), (1, 0), (-1, 0)
DIR_SETS = [(d,) for d in PG.DIRS8] + [(R, L), (DN, UP), ((1, 1), (-1, -1)), ((1, -1), (-1, 1)),
                                         PG.DIRS8[:4], PG.DIRS8[4:], PG.DIRS8]
STOPS = ("obstacle", "through")
MAX_SEL = 2
MAX_RIVALS = 4
MAX_COVER = 3
MAX_BASES = 4
MAX_PROGRAMS = 64


class Demo(NamedTuple):
    A: np.ndarray
    B: np.ndarray
    bg: int
    objs: list                 # [(cells, colour)]


class Candidate(NamedTuple):
    rules: list                # rival rules that change exactly these cells on every demonstration, simplest first
    cover: list                # per demonstration: the changed cells the rules change


def _demos(train, view):
    out = []
    for a, b in train:
        A, B = np.asarray(a), np.asarray(b)
        if A.shape != B.shape:
            return None
        objs, bg = SC.native_objects(a, view)
        out.append(Demo(A, B, bg, [(frozenset(o.cells), int(o.color)) for o in objs]))
    return out


def _uniform(B, cells):
    vals = {int(B[x]) for x in cells}
    return next(iter(vals)) if len(vals) == 1 else None


def _part_cells(kind):
    return lambda cells, d: PT.part(cells, kind, d.A, d.bg)


def _ray_cells(dirs, stop):
    return lambda cells, d: PG.ray_cells(cells, dirs, stop, d.A, d.bg)


def shapes(demos):
    """[(cells_fn, colour, make_rule)]: every rule shape that some object's output supports (step 1)."""
    parts, rays = set(), set()
    for d in demos:
        for cells, col in d.objs:
            for k in KINDS:
                xs = PT.part(cells, k, d.A, d.bg)
                c = _uniform(d.B, xs)
                if c is not None and any(d.A[x] != c for x in xs):
                    parts.add((k, c))
                    if c == col and k in REGION_KINDS:
                        parts.add((k, "own"))
            for dr in PG.DIRS8:
                for stop in STOPS:
                    c = _uniform(d.B, PG.ray_cells(cells, (dr,), stop, d.A, d.bg))
                    if c is not None and c != d.bg:              # ray cells are background in the input
                        rays.add((dr, stop, c))
                        if c == col:
                            rays.add((dr, stop, "own"))
    out = [(_part_cells(k), c, lambda s, k=k, c=c: PG.PartRule(s, k, c)) for k, c in sorted(parts, key=repr)]
    for stop in STOPS:
        for c in sorted({c for _, s, c in rays if s == stop}, key=repr):
            for dirs in DIR_SETS:                              # every direction of the set is supported somewhere
                if all((dr, stop, c) in rays for dr in dirs):
                    out.append((_ray_cells(dirs, stop), c, lambda s, dirs=dirs, stop=stop, c=c: PG.RayRule(s, dirs, stop, c)))
    return out


def partition(demos, cells_fn, colour):
    """Per demonstration: members, don't-care objects, and the changed cells the members' rule cells cover (step 2)."""
    must, may, cover = [], [], []
    for d in demos:
        m, y, cv = set(), set(), set()
        for j, (cells, col) in enumerate(d.objs):
            c = col if colour == "own" else colour
            xs = cells_fn(cells, d)
            if all(d.B[x] == c for x in xs):
                ch = {x for x in xs if d.A[x] != c}
                (m if ch else y).add(j)
                cv |= ch
        must.append(frozenset(m))
        may.append(frozenset(y))
        cover.append(frozenset(cv))
    return must, may, cover


def simplicity(rule):
    """The rival order: the cheaper selector, then the part kind in parts.KINDS order (rays after parts, fewer
    directions first, obstacle before through), then int colours before "own"."""
    shape = (KINDS.index(rule.kind),) if isinstance(rule, PG.PartRule) else \
        (len(KINDS), len(rule.dirs), STOPS.index(rule.stop))
    return (INV._cost(rule.sel),) + shape + (rule.colour == "own",)


def candidates(train, view, stats=None):
    """[Candidate] for one view, the most changed cells first. Rules that change the same cells on every
    demonstration are rivals in one candidate: the demonstrations cannot tell them apart, the test inputs may."""
    demos = _demos(train, view)
    if demos is None:
        return []
    tables = INV.feature_tables(train, view)
    tests = INV.single_tests(tables)
    groups = {}
    for cells_fn, colour, mk in shapes(demos):
        must, may, cover = partition(demos, cells_fn, colour)
        if not any(must):
            continue
        sels = INV.induce_selectors(view, train, tables, tests, must, may)[:MAX_SEL]
        if stats is not None:
            stats["shapes"] = stats.get("shapes", 0) + 1
        if sels:
            groups.setdefault(tuple(cover), []).extend(mk(s) for s in sels)
    out = [Candidate(sorted(rs, key=simplicity)[:MAX_RIVALS], list(cov)) for cov, rs in groups.items()]
    out.sort(key=lambda c: -sum(map(len, c.cover)))
    return out


def covers(cands, need):
    """Greedy covers of `need` (per demonstration), as lists of candidate indices: the largest gain first, with the
    two best choices of first rule, at most MAX_COVER rules."""
    def gain(i, left):
        return sum(len(l & c) for l, c in zip(left, cands[i].cover))

    out = []
    if not any(need):
        return out
    firsts = sorted(range(len(cands)), key=lambda i: -gain(i, need))[:2]
    for first in firsts:
        chosen, left = [first], [l - c for l, c in zip(need, cands[first].cover)]
        while any(left) and len(chosen) < MAX_COVER:
            best = max((i for i in range(len(cands)) if i not in chosen), key=lambda i: gain(i, left), default=None)
            if best is None or gain(best, left) == 0:
                break
            chosen.append(best)
            left = [l - c for l, c in zip(left, cands[best].cover)]
        if not any(left) and chosen not in out:
            out.append(chosen)
    return out


def _safe_bases(task):
    """Inversion programs that write no wrong cell and fix some but not all changed cells: (program, cells left)."""
    out = []
    for prog, _ in INV.invert(task):
        INV.RUNS["native"] += len(task["train"])
        try:
            ds = D.deltas(prog, task["train"])
        except ASTError:
            continue
        if all(d.shape_ok and d.fixed is not None for d in ds) and not any(int(d.broken.sum()) for d in ds) and \
                any(int(d.fixed.sum()) for d in ds) and any(int(d.remaining.sum()) for d in ds):
            out.append((prog, [frozenset(zip(*map(lambda a: a.tolist(), np.nonzero(d.remaining)))) for d in ds]))
        if len(out) == MAX_BASES:
            break
    return out


def programs(task, stats=None):
    """G4 programs, in order: covers by the rules alone, then partial inversion programs followed by covers."""
    stats = {} if stats is None else stats
    train = task["train"]
    if not all(np.asarray(a).shape == np.asarray(b).shape for a, b in train):
        return []
    changed = [frozenset(zip(*map(lambda a: a.tolist(), np.nonzero(np.asarray(a) != np.asarray(b))))) for a, b in train]
    per_view = [(v, candidates(train, v, stats)) for v in G1S.distinct_views(task)]
    out, seen = [], set()

    def emit(view, base, cands, cover):
        best = [cands[i].rules[0] for i in cover]
        variants = [best] + ([best[::-1]] if len(best) > 1 else []) + \
            [best[:g] + [r] + best[g + 1:] for g, i in enumerate(cover) for r in cands[i].rules[1:]]
        for rules in variants:                                     # the simplest rules (both orders), then one rival
            p = PG.make(view, base, rules)
            if p not in seen and len(out) < MAX_PROGRAMS:
                seen.add(p)
                out.append(p)
    for view, cands in per_view:
        for cover in covers(cands, changed):
            emit(view, None, cands, cover)
    if any(cands for _, cands in per_view):
        for base, left in _safe_bases(task):
            for view, cands in per_view:
                for cover in covers(cands, left):
                    emit(view, base, cands, cover)
    return out


def sexpr(prog):
    """A readable S-expression for a g4 program."""
    from cora_neural_v2.rast import to_sexpr

    def rule(r):
        if isinstance(r, PG.PartRule):
            return f"(part_rule {to_sexpr(r.sel)} {r.kind} {r.colour})"
        dirs = " ".join(f"({a} {b})" for a, b in r.dirs)
        return f"(ray_rule {to_sexpr(r.sel)} (list {dirs}) {r.stop} {r.colour})"
    base = to_sexpr(prog.base) if prog.base is not None else "(identity)"
    return f"(g4program {prog.view} {base} (list {' '.join(rule(r) for r in prog.rules)}))"
