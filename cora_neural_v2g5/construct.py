"""Version 5 construction: evidence-driven stamp, obstacle-aware ray, segment and fill rules, with version 4's
mechanism (cora_neural_v2g4/construct.py). Demonstrations only.

1. Shapes from evidence. For every rule family and parameter setting, each object of each demonstration input is
   given the cells the rule would write for it alone (for a stamp: for each source and anchor pair).
2. Partition. An object is a MEMBER when all its writes take the output's colour and some change a cell, a DON'T-CARE
   when all its writes already hold that colour (or there are none), and EXCLUDED otherwise. Selectors are induced
   with invert.induce_selectors (members exact, don't-care objects optional) and confirmed by native execution.
3. Execution check. Each constructed rule is executed alone on every demonstration (program.rule_writes, the same
   executor programs use) and kept only if it writes no cell the output does not have; its cover is the set of
   changed cells it writes.
4. Programs: covers of the changed cells by version 5 and version 4 rules together (each cover holds at least one
   version 5 rule; version 4's own programs come from version 4's construction), alone or after a partial inversion
   program, with demonstration-equivalent rules kept as rivals.
Everything here only proposes; the executor and the fit check decide. Rule-alone executions are counted in
program.RUNS["checks"] and selector checks in invert.RUNS["native"]; neither is a candidate evaluation.

Level: L1 (an engineering extension of version 4's vocabulary).
"""
import time
from typing import NamedTuple

import numpy as np

from cora_neural_v2 import search as G1S
from cora_neural_v2g4 import construct as C4
from cora_neural_v2g4 import invert as INV
from cora_neural_v2g4 import program as PG
from cora_neural_v2g5 import program as P5

VIEWS = ("S1", "S2", "S3", "S6")       # construction runs on these views when they are distinct for the task
MAX_OBJECTS = 30
MAX_SEL = 2
MAX_RIVALS = 4
MAX_COVER = 3
MAX_PROGRAMS = 64
STAMP_MODES = [(scope, align, rec) for scope in ("object", "box") for align in ("topleft", "centre", "marker")
               for rec in ("keep", "anchor")]
RAY2_MODES = [("stop", "cell"), ("stop", "object"), ("turn_cw", "none"), ("turn_ccw", "none"),
              ("turn_cw", "cell"), ("turn_ccw", "cell")]
TYPE_RANK = {"PartRule": 0, "RayRule": 1, "Ray2Rule": 2, "SegmentRule": 3, "FillRule": 4, "StampRule": 5}


class Demo(NamedTuple):
    A: np.ndarray
    B: np.ndarray
    bg: int
    cells: tuple
    colours: tuple
    obj_of: dict
    enclosed: tuple


def _demos(train, view):
    out = []
    for a, b in train:
        A, B = np.asarray(a), np.asarray(b)
        if A.shape != B.shape:
            return None
        cells, colours, bg, obj_of, enclosed = P5._layout(view, PG._key(A))
        if len(cells) > MAX_OBJECTS:
            return None
        out.append(Demo(A, B, bg, cells, colours, obj_of, enclosed))
    return out


def _check(W, d):
    """(consistent, changed cells) of writes W on demonstration d."""
    if W is None or not all(d.B[x] == v for x, v in W.items()):
        return False, None
    return True, {x for x, v in W.items() if d.A[x] != v}


def _partition(demos, f):
    must, may = [], []
    for d in demos:
        m, y = set(), set()
        for j in range(len(d.cells)):
            ok, ch = _check(f(d, j), d)
            if ok:
                (m if ch else y).add(j)
        must.append(frozenset(m))
        may.append(frozenset(y))
    return must, may


def _out_colours(demos):
    return sorted({int(d.B[x]) for d in demos for x in zip(*np.nonzero(d.A != d.B))} - {d.bg for d in demos})


def _ray2_shapes(demos):
    colours = _out_colours(demos) + ["own"]
    supported = set()
    for mode, hit in RAY2_MODES:
        for dr in PG.DIRS8:
            for c in colours:
                rule = P5.Ray2Rule(None, (dr,), mode, hit, c)
                for d in demos:
                    if any(_check(P5.ray2_object_writes(rule, d.A, d.cells, d.colours, d.bg, d.obj_of, j, {}), d)[1]
                           for j in range(len(d.cells))):
                        supported.add((mode, hit, dr, c))
                        break
    out = []
    for mode, hit in RAY2_MODES:
        for c in colours:
            for dirs in C4.DIR_SETS:
                if all((mode, hit, dr, c) in supported for dr in dirs):
                    rule = P5.Ray2Rule(None, dirs, mode, hit, c)
                    out.append((lambda d, j, rule=rule: P5.ray2_object_writes(rule, d.A, d.cells, d.colours, d.bg,
                                                                              d.obj_of, j, {}),
                                lambda s, rule=rule: rule._replace(sel=s)))
    return out


def _pair_writes(d, j, colour, gaps_fn):
    out = {}
    for k in range(len(d.cells)):
        if k == j or (colour == "own" and d.colours[k] != d.colours[j]):
            continue
        col = d.colours[j] if colour == "own" else int(colour)
        for gap in gaps_fn(d, j, k):
            if all(d.A[x] == d.bg for x in gap):
                for x in gap:
                    out[x] = col
    return out


def _segment_shapes(demos):
    out = []
    for axes in ("h", "v", "hv"):
        for c in _out_colours(demos) + ["own"]:
            gaps = lambda d, j, k, axes=axes: P5._facing_gaps(d.cells[j], d.cells[k], axes)   # noqa: E731
            out.append((lambda d, j, c=c, gaps=gaps: _pair_writes(d, j, c, gaps),
                        lambda s, axes=axes, c=c: P5.SegmentRule(s, axes, c)))
    return out


def _fill_shapes(demos):
    out = []
    for c in _out_colours(demos) + ["own"]:
        def enclosed(d, j, c=c):
            W = {}
            h, w = d.A.shape
            for comp in d.enclosed:
                nb = {d.obj_of[(y + dy, x + dx)] for y, x in comp for dy, dx in P5.N4
                      if 0 <= y + dy < h and 0 <= x + dx < w and (y + dy, x + dx) in d.obj_of}
                if j not in nb or (c == "own" and len({d.colours[k] for k in nb}) != 1):
                    continue
                col = d.colours[j] if c == "own" else int(c)
                for x in comp:
                    W[x] = col
            return W
        out.append((enclosed, lambda s, c=c: P5.FillRule(s, "enclosed", c)))

        def between(d, j, c=c):
            W = {}
            for k in range(len(d.cells)):
                if k == j:
                    continue
                probe = P5.FillRule(None, "between", c)
                Wk = P5.fill_writes(probe, d.A, d.cells, d.colours, d.bg, d.obj_of, d.enclosed, frozenset({j, k}))
                W.update(Wk)
            return W
        out.append((between, lambda s, c=c: P5.FillRule(s, "between", c)))
    return out


def _stamp_rules(view, train, demos, tables, tests):
    """Stamp rules from evidence: per mode, per demonstration, the source whose copies explain the most changed cells."""
    rules = []
    for scope, align, rec in STAMP_MODES:
        probe = P5.StampRule(None, None, scope, align, rec)
        srcs, musts, mays = [], [], []
        for d in demos:
            best = None
            for s in range(len(d.cells)):
                m, y, cov = set(), set(), set()
                for j in range(len(d.cells)):
                    if j == s:
                        continue
                    ok, ch = _check(P5.stamp_writes(probe, d.A, d.cells, d.colours, d.bg, {s}, {j}), d)
                    if ok:
                        (m if ch else y).add(j)
                        cov |= ch or set()
                if m and (best is None or len(cov) > best[0]):
                    best = (len(cov), s, frozenset(m), frozenset(y | {s}))
            if best is None:
                break
            srcs.append(frozenset({best[1]}))
            musts.append(best[2])
            mays.append(best[3])
        if len(srcs) != len(demos):
            continue
        src_sels = INV.induce_selectors(view, train, tables, tests, srcs)[:MAX_SEL]
        anc_sels = INV.induce_selectors(view, train, tables, tests, musts, mays)[:MAX_SEL] if src_sels else []
        rules += [P5.StampRule(s, a, scope, align, rec) for s in src_sels for a in anc_sels]
    return rules


def simplicity(rule):
    sel_cost = INV._cost(rule.src) + INV._cost(rule.anchors) if isinstance(rule, P5.StampRule) else INV._cost(rule.sel)
    return (sel_cost, TYPE_RANK[type(rule).__name__], repr(rule[1:]))


def candidates(train, view, stats=None, deadline=None):
    """[C4.Candidate] of version 5 rules for one view, the most changed cells first; each rule executed alone on
    every demonstration writes only cells the output has."""
    demos = _demos(train, view)
    if demos is None:
        return []
    tables = INV.feature_tables(train, view)
    tests = INV.single_tests(tables)
    built = []
    for shapes in (_ray2_shapes, _segment_shapes, _fill_shapes):
        for f, mk in shapes(demos):
            if deadline is not None and time.process_time() > deadline:
                break
            must, may = _partition(demos, f)
            if not any(must):
                continue
            if stats is not None:
                stats["shapes5"] = stats.get("shapes5", 0) + 1
            built += [mk(s) for s in INV.induce_selectors(view, train, tables, tests, must, may)[:MAX_SEL]]
    if deadline is None or time.process_time() <= deadline:
        built += _stamp_rules(view, train, demos, tables, tests)
    groups = {}
    for rule in built:                                            # step 3: the execution check
        cov = []
        for a, b in train:
            P5.RUNS["checks"] += 1
            A, B = np.asarray(a), np.asarray(b)
            ok, ch = _check(P5.rule_writes(rule, view, A), Demo(A, B, 0, (), (), {}, ()))
            if not ok:
                cov = None
                break
            cov.append(frozenset(ch))
        if cov and any(cov):
            groups.setdefault(tuple(cov), []).append(rule)
    out = [C4.Candidate(sorted(set(rs), key=simplicity)[:MAX_RIVALS], list(cov)) for cov, rs in groups.items()]
    out.sort(key=lambda c: -sum(map(len, c.cover)))
    return out


def _covers(cands, need, new_idx):
    """Greedy covers of `need` that use at least one version 5 candidate: the two best first rules overall and the
    two best version 5 rules as first choices, then the largest gain, at most MAX_COVER rules."""
    def gain(i, left):
        return sum(len(l & c) for l, c in zip(left, cands[i].cover))
    out = []
    if not any(need):
        return out
    by_gain = sorted(range(len(cands)), key=lambda i: -gain(i, need))
    firsts = list(dict.fromkeys(by_gain[:2] + [i for i in by_gain if i in new_idx][:2]))
    for first in firsts:
        chosen, left = [first], [l - c for l, c in zip(need, cands[first].cover)]
        while any(left) and len(chosen) < MAX_COVER:
            best = max((i for i in range(len(cands)) if i not in chosen), key=lambda i: gain(i, left), default=None)
            if best is None or gain(best, left) == 0:
                break
            chosen.append(best)
            left = [l - c for l, c in zip(left, cands[best].cover)]
        if not any(left) and set(chosen) & new_idx and chosen not in out:
            out.append(chosen)
    return out


def programs(task, stats=None, cpu_budget_s=60.0):
    """Version 5 programs, in order: covers by rules alone, then partial inversion programs followed by covers.
    Construction stops proposing new shapes after `cpu_budget_s` CPU seconds."""
    stats = {} if stats is None else stats
    train = task["train"]
    if not all(np.asarray(a).shape == np.asarray(b).shape for a, b in train):
        return []
    deadline = time.process_time() + cpu_budget_s
    changed = [frozenset(zip(*map(lambda a: a.tolist(), np.nonzero(np.asarray(a) != np.asarray(b))))) for a, b in train]
    views = [v for v in G1S.distinct_views(task) if v in VIEWS]
    per_view = []
    for v in views:
        new = candidates(train, v, stats, deadline)
        if new:
            per_view.append((v, new + C4.candidates(train, v), set(range(len(new)))))
    out, seen = [], set()

    def emit(view, base, cands, cover):
        best = [cands[i].rules[0] for i in cover]
        variants = [best] + ([best[::-1]] if len(best) > 1 else []) + \
            [best[:g] + [r] + best[g + 1:] for g, i in enumerate(cover) for r in cands[i].rules[1:]]
        for rules in variants:
            p = P5.make(view, base, rules)
            if p not in seen and len(out) < MAX_PROGRAMS:
                seen.add(p)
                out.append(p)
    for view, cands, new_idx in per_view:
        for cover in _covers(cands, changed, new_idx):
            emit(view, None, cands, cover)
    if per_view:
        for base, left in C4._safe_bases(task):
            for view, cands, new_idx in per_view:
                for cover in _covers(cands, left, new_idx):
                    emit(view, base, cands, cover)
    return out


def sexpr(prog):
    """A readable S-expression for a version 5 program."""
    from cora_neural_v2.rast import to_sexpr

    def rule(r):
        if isinstance(r, (PG.PartRule, PG.RayRule)):
            return C4.sexpr(PG.make(prog.view, None, [r]))[len(f"(g4program {prog.view} (identity) (list "):-2]
        if isinstance(r, P5.StampRule):
            return f"(stamp_rule {to_sexpr(r.src)} {to_sexpr(r.anchors)} {r.scope} {r.align} {r.recolour})"
        if isinstance(r, P5.Ray2Rule):
            dirs = " ".join(f"({a} {b})" for a, b in r.dirs)
            return f"(ray2_rule {to_sexpr(r.sel)} (list {dirs}) {r.mode} {r.hit} {r.colour})"
        if isinstance(r, P5.SegmentRule):
            return f"(segment_rule {to_sexpr(r.sel)} {r.axes} {r.colour})"
        return f"(fill_rule {to_sexpr(r.sel)} {r.kind} {r.colour})"
    base = to_sexpr(prog.base) if prog.base is not None else "(identity)"
    return f"(g5program {prog.view} {base} (list {' '.join(rule(r) for r in prog.rules)}))"
