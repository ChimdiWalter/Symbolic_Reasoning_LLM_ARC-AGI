"""CORA reasoning v2: a TYPED SCENE TRANSFORMATION in two stages (DEVELOPMENT; researcher-designed, not induced).

The diagnosis found that 32 of the 60 development tasks change cells in ways the additive class cannot express:
- 25 combine several kinds of change (adds, deletes, recolours);
- 7 recolour or delete only.

This family composes typed stages:
- **Stage 1, selection and colour, in place.** Each object of a segmentation view is KEPT, DELETED or RECOLOURED as a
  whole, by a table from one object feature to the action. The table is learned from the demonstrations: the
  observable, typed object deltas native also uses.
- **Stage 2, spatial.** v2's growth hypotheses (`scene_reasoner`, optionally `selection`) are fitted to the stage-1
  result, which must account for every remaining change as an addition.
- **Composition:** sequential overlay.

The stage-1 result on a demonstration is fixed by its output: every non-background cell takes its output value. So
stage 2 is fitted once per task. On a test input, stage 1 is predicted by the learned rule, so different rules can
disagree, and that disagreement is kept.

Only training pairs and test inputs are read. Segmentations are native's; nothing native is modified.
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from cora_fhr import ggrow as GG                                        # noqa: E402

FEATURES = ("all", "colours", "size", "h", "w", "n_colours", "size_rank", "border",
            "colours*size_rank", "colours*border", "size_rank*border", "colours*size")   # pairs = two-literal selectors
MAX_HYPS = 4000


def _bg(A):
    vals, cnt = np.unique(A, return_counts=True)
    return int(min(zip(vals, cnt), key=lambda vc: (-vc[1], vc[0]))[0])


def _ctxs(grid, view):
    from cora_revision_v2.scene_reasoner import _objects
    A = np.asarray(grid)
    return [GG.Ctx(o, A) for o in _objects(grid, view)]


def _feat(x, f, sizes):
    if "*" in f:
        a, b = f.split("*")
        return (_feat(x, a, sizes), _feat(x, b, sizes))
    if f == "all":
        return "*"
    if f == "size_rank":
        return "largest" if len(x.O) == max(sizes) else ("smallest" if len(x.O) == min(sizes) else "middle")
    if f == "border":
        return x.r0 == 0 or x.c0 == 0 or x.r1 == x.H - 1 or x.c1 == x.W - 1
    return {"size": len(x.O), "colours": tuple(sorted(set(x.O.values()))), "h": x.h, "w": x.w,
            "n_colours": x.n_colours}[f]


def _delta(x, B, bg):
    """The whole-object action an output shows: ("KEEP",), ("DELETE",), ("RECOLOR", c); None if partial or mixed."""
    outs = {int(B[c]) for c in x.O}
    if all(int(B[c]) == v for c, v in x.O.items()):
        return ("KEEP",)
    if len(outs) != 1:
        return None
    c = next(iter(outs))
    return ("DELETE",) if c == bg else ("RECOLOR", c)


LITERAL_FEATURES = ("colours", "size_rank", "border", "size", "n_colours", "h", "w")


def _decision_lists(rows, max_len=2):
    """Ordered (feature == value -> action) rules plus a default action, consistent with every object: each rule's
    literal, applied to the objects no earlier rule took, selects only objects with that action, and the objects left
    over share the default. An object whose value no rule names takes the default."""
    lits = sorted({(f, _feat(x, f, s)) for x, s, _d in rows for f in LITERAL_FEATURES}, key=str)
    out = []

    def grow(rest, prefix):
        acts = {d for _x, _s, d in rest}
        if prefix and len(acts) == 1:
            out.append(([[f, v, list(a)] for f, v, a in prefix], next(iter(acts))))
            return
        if len(prefix) >= max_len or not rest:
            return
        for f, v in lits:
            sel = [r for r in rest if _feat(r[0], f, r[1]) == v]
            if not sel or len(sel) == len(rest):
                continue
            a = {d for _x, _s, d in sel}
            if len(a) == 1:
                grow([r for r in rest if _feat(r[0], f, r[1]) != v], prefix + [(f, v, next(iter(a)))])
    grow(rows, [])
    return out


def stage1_rules(pairs, views=None):
    """Consistent (view, feature, table) rules explaining every change to a non-background input cell."""
    from geocat_arc.object_reasoning.types import SegmentationVariant as V
    rules = []
    for view in (views or list(V)):
        rows, ok = [], True
        for a, b in pairs:
            A, B = np.asarray(a), np.asarray(b)
            bg = _bg(A)
            xs = _ctxs(a, view)
            sizes = [len(x.O) for x in xs] or [0]
            for x in xs:
                d = _delta(x, B, bg)
                if d is None:
                    ok = False
                    break
                rows.append((x, sizes, d))
            if not ok:
                break
        if not ok or not any(d != ("KEEP",) for _x, _s, d in rows):
            continue
        for dl in _decision_lists(rows):
            rules.append({"view": view.value, "feature": "decision_list", "rules": dl[0], "default": list(dl[1])})
        for f in FEATURES:
            table, good = {}, True
            for x, sizes, d in rows:
                if table.setdefault(_feat(x, f, sizes), d) != d:
                    good = False
                    break
            if good and (f == "all" or len(set(table.values())) > 1):
                rules.append({"view": view.value, "feature": f,
                              "table": [[k, list(v)] for k, v in table.items()]})
    return rules


def _tup(k):
    return tuple(_tup(i) for i in k) if isinstance(k, list) else k


def apply_stage1(rule, grid):
    """The rule's in-place result on a grid, or None if an object's feature value is not in its table."""
    from geocat_arc.object_reasoning.types import SegmentationVariant as V
    A = np.asarray(grid)
    bg = _bg(A)
    xs = _ctxs(grid, V(rule["view"]))
    sizes = [len(x.O) for x in xs] or [0]
    if rule["feature"] == "decision_list":
        rl = [(f, _tup(v), tuple(a)) for f, v, a in rule["rules"]]

        def act(x):
            return next((a for f, v, a in rl if _feat(x, f, sizes) == v), tuple(rule["default"]))
    else:
        table = {_tup(k): tuple(v) for k, v in rule["table"]}

        def act(x):
            return table.get(_feat(x, rule["feature"], sizes))
    P = A.copy()
    for x in xs:
        d = act(x)
        if d is None:
            return None
        if d[0] == "DELETE":
            for c in x.O:
                P[c] = bg
        elif d[0] == "RECOLOR":
            for c in x.O:
                P[c] = d[1]
    return P


def _stage1_target(a, b):
    """A demonstration's stage-1 result: every non-background input cell takes its output value."""
    A, B = np.asarray(a), np.asarray(b)
    P = A.copy()
    m = A != _bg(A)
    P[m] = B[m]
    return P


def _rank(r):
    return len(r["rules"]) if r["feature"] == "decision_list" else 3 + FEATURES.index(r["feature"])


def version_space(pairs, families=("grow",), select_cpu=60.0):
    """Two-stage hypotheses reproducing every pair exactly. Returns (hyps, info)."""
    from cora_revision_v2 import scene_reasoner as SR
    info = {"stage1_rules": 0, "stage2": None}
    if any(np.asarray(a).shape != np.asarray(b).shape for a, b in pairs):
        return [], info
    if not any((np.asarray(a) != np.asarray(b))[np.asarray(a) != _bg(np.asarray(a))].any() for a, b in pairs):
        return [], info                                            # additions only: the base family's domain
    rules = stage1_rules(pairs)
    info["stage1_rules"] = len(rules)
    if not rules:
        return [], info
    mid = [(_stage1_target(a, b).tolist(), b) for a, b in pairs]
    hyps = []
    if all(np.array_equal(np.asarray(m), np.asarray(b)) for m, b in mid):
        info["stage2"] = "identity"
        for r in rules:
            hyps.append({"family": "tst", "rule": r, "stage2": None, "complexity": (4, _rank(r))})
        return hyps, info
    s2, _n = SR._hypotheses(mid, tuple(f for f in families if f in ("grow", "select")), select_cpu)
    info["stage2"] = len(s2)
    for r in rules:
        for h2 in s2:
            hyps.append({"family": "tst", "rule": r, "stage2": h2,
                         "complexity": (5 + h2["complexity"][0], _rank(r))})
            if len(hyps) >= MAX_HYPS:
                info["capped"] = True
                return hyps, info
    return hyps, info


def predict(h, grid):
    from cora_revision_v2 import scene_reasoner as SR
    P = apply_stage1(h["rule"], grid)
    if P is None:
        return None
    if h["stage2"] is None:
        return P.tolist()
    return SR.predict(h["stage2"], P.tolist())
