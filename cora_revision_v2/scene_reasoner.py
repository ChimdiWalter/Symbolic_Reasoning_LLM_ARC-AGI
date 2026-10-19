"""CORA reasoning v2, Phase 1: a hypothesis-aware scene reasoner that separates geometry from colour (DEVELOPMENT).

RESEARCHER-DESIGNED LANGUAGE EXPANSION (directive action D), not automatic grammar induction and not a new primitive.

A hypothesis is (representation R, geometry h, colour policy c):
- R: one of native CORA's 7 segmentation views;
- h: one G-grow v1 expression (the 37,750 single unguarded expressions), applied to every object;
- c: how each added cell is coloured:
  - CONST: one colour learned from the demonstrations;
  - OBJ_MAJ / OBJ_MIN: the object's majority or minority colour;
  - ORIGIN: the colour of the source cell the geometry came from, tracked through every transform;
  - NEAREST: the colour of the nearest cell of the object (a unique colour is required);
  - TABLE:f: a table from an object feature f (size, colour set, h, w) to colour, learned from the
    demonstrations.

The reasoner (`reason`):
1. Keeps the VERSION SPACE of every hypothesis that reproduces every training output EXACTLY, as a full grid.
2. Predicts the test with every member. Distinct predictions mean MANY_CONSISTENT_DISAGREE: it abstains,
   and the two best-supported distinct predictions are offered as the two attempts.
3. Re-runs the whole search inside every omitted-demonstration fold (FOLD_FRAGILITY if any fold fails or
   disagrees).
4. CERTIFIES only a unique, fold-robust prediction.

Its diagnoses (NO_CONSISTENT_HYPOTHESIS with GEOMETRY_GAP or COLOUR_POLICY_GAP, MANY_CONSISTENT_DISAGREE,
FOLD_FRAGILITY, CERTIFIED) use the training pairs and test inputs only. No answer is read here.
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from cora_fhr import ggrow as GG                                        # noqa: E402

POLICIES = ("CONST", "OBJ_MAJ", "OBJ_MIN", "ORIGIN", "NEAREST", "TABLE:size", "TABLE:colours", "TABLE:h", "TABLE:w")
GEOM_CAP = 400


# ---------------------------------------------------------------- provenance-aware geometry
def _tprov(t, X, x):
    """GG.transform with provenance: X maps cell -> frozenset(source cells). Same positions as GG.transform."""
    op = t[0]
    out = {}

    def put(c, p):
        out[c] = out.get(c, frozenset()) | p
    if op in ("shift", "repeat"):
        dr, dc = GG._vec(t[1], t[2], x)
        if op == "shift":
            for (r, c), p in X.items():
                put((r + dr, c + dc), p)
        else:
            for k in range(1, GG.REPEAT_CAP + 1):
                moved = {(r + k * dr, c + k * dc): p for (r, c), p in X.items()}
                if not any(x.inside(r, c) for r, c in moved):
                    break
                for cell, p in moved.items():
                    put(cell, p)
    elif op == "ray":
        dr, dc = GG._DIR[t[1]]
        for (r, c), p in X.items():
            r, c = r + dr, c + dc
            while x.inside(r, c):
                if t[2] == "obstacle" and x.G[r, c] != x.bg and (r, c) not in x.O:
                    break
                put((r, c), p)
                r, c = r + dr, c + dc
    elif op == "reflect":
        a = t[1]
        f = {"N": lambda r, c: (2 * x.r0 - 1 - r, c), "S": lambda r, c: (2 * x.r1 + 1 - r, c),
             "W": lambda r, c: (r, 2 * x.c0 - 1 - c), "E": lambda r, c: (r, 2 * x.c1 + 1 - c),
             "H": lambda r, c: (x.r0 + x.r1 - r, c), "V": lambda r, c: (r, x.c0 + x.c1 - c)}[a]
        for (r, c), p in X.items():
            put(f(r, c), p)
    elif op == "ring":
        nb = ((-1, 0), (1, 0), (0, -1), (0, 1)) if t[1] == 4 else \
             tuple((i, j) for i in (-1, 0, 1) for j in (-1, 0, 1) if (i, j) != (0, 0))
        for (r, c), p in X.items():
            for i, j in nb:
                if (r + i, c + j) not in X:
                    put((r + i, c + j), p)
    else:                                                            # hull / interior: cells come from the set as a whole
        cells = GG.transform(t, set(X), x)
        allp = frozenset().union(*X.values()) if X else frozenset()
        for cell in cells:
            put(cell, allp)
    return out


def geometry_prov(expr, x):
    """Added cells -> provenance (source cells), finalized exactly as GG.evaluate."""
    cls, s = expr[0], expr[1]
    S = {cell: frozenset([cell]) for cell in GG.source(GG.SOURCES[s], x)}
    if cls == "d1":
        out = _tprov(GG.TRANSFORMS[expr[2]], S, x)
    elif cls == "d2":
        out = _tprov(GG.TRANSFORMS[expr[3]], _tprov(GG.TRANSFORMS[expr[2]], S, x), x)
    else:
        a, b = _tprov(GG.TRANSFORMS[expr[2]], S, x), _tprov(GG.TRANSFORMS[expr[3]], S, x)
        out = dict(a)
        for c, p in b.items():
            out[c] = out.get(c, frozenset()) | p
    return {c: p for c, p in out.items() if c in x.free}


def _feature(x, f):
    return {"size": len(x.O), "colours": tuple(sorted(set(x.O.values()))), "h": x.h, "w": x.w}[f]


def _nearest(cell, x):
    best, cols = None, set()
    for (r, c), v in x.O.items():
        d = max(abs(r - cell[0]), abs(c - cell[1]))
        if best is None or d < best:
            best, cols = d, {v}
        elif d == best:
            cols.add(v)
    return next(iter(cols)) if len(cols) == 1 else None


def cell_colours(policy, x, added, table=None, const=None):
    """Colour per added cell under a policy, or None if the policy is undefined for this object."""
    if policy == "CONST":
        return {c: const for c in added} if const is not None else None
    if policy == "OBJ_MAJ":
        return {c: x.majority for c in added}
    if policy == "OBJ_MIN":
        return {c: x.minority for c in added} if x.n_colours >= 2 else None
    if policy == "ORIGIN":
        out = {}
        for c, p in added.items():
            cols = {x.O.get(q) for q in p}
            if None in cols or len(cols) != 1:
                return None
            out[c] = next(iter(cols))
        return out
    if policy == "NEAREST":
        out = {c: _nearest(c, x) for c in added}
        return None if any(v is None for v in out.values()) else out
    if policy.startswith("TABLE:"):
        key = _feature(x, policy.split(":")[1])
        if table is None or key not in table:
            return None
        return {c: table[key] for c in added}
    raise ValueError(policy)


# ---------------------------------------------------------------- scene-level fitting
def _objects(grid, view):
    from cora_fhr.oracle_expressibility import _objects as obj
    return [o for o in obj(grid, view) if o]


def _scene(pairs, view):
    data = []
    for a, b in pairs:
        A, B = np.asarray(a), np.asarray(b)
        if A.shape != B.shape:
            return None
        data.append((A, B, [GG.Ctx(o, A) for o in _objects(a, view)]))
    return data


def _predict(data_inputs, expr, policy, table, const):
    """Full predicted grids (or None) for a list of (A, ctxs)."""
    outs = []
    for A, ctxs in data_inputs:
        P = A.copy()
        written = {}
        for x in ctxs:
            added = geometry_prov(expr, x)
            if not added:
                continue
            cols = cell_colours(policy, x, added, table, const)
            if cols is None:
                return None
            for c, v in cols.items():
                if written.get(c, v) != v:
                    return None                                        # two objects disagree on a cell
                written[c] = v
                P[c] = v
        outs.append(P)
    return outs


def fit_policies(data, expr):
    """Colour policies (with learned parameters) under which `expr` reproduces every training output exactly."""
    found = []
    added_cols, per_obj = set(), []
    for A, B, ctxs in data:
        for x in ctxs:
            add = geometry_prov(expr, x)
            cs = {int(B[c]) for c in add}
            added_cols |= cs
            per_obj.append((x, cs))
    const = next(iter(added_cols)) if len(added_cols) == 1 else None
    for pol in POLICIES:
        table = None
        if pol.startswith("TABLE:"):
            table, ok = {}, True
            for x, cs in per_obj:
                if not cs:
                    continue
                if len(cs) != 1:
                    ok = False
                    break
                k = _feature(x, pol.split(":")[1])
                if table.setdefault(k, next(iter(cs))) != next(iter(cs)):
                    ok = False
                    break
            if not ok or len(set(table.values())) < 2:              # a constant table is CONST, not a table
                continue
        if pol == "CONST" and const is None:
            continue
        preds = _predict([(A, ctxs) for A, B, ctxs in data], expr, pol, table, const)
        if preds is not None and all(np.array_equal(P, B) for P, (A, B, c) in zip(preds, data)):
            found.append((pol, table, const))
    return found


def version_space(pairs, views=None, geom_cap=GEOM_CAP):
    """All (view, expr, policy) hypotheses reproducing every pair exactly. Returns (hyps, n_positional)."""
    from geocat_arc.object_reasoning.types import SegmentationVariant as V
    from cora_fhr.oracle_expressibility import _fits
    hyps, npos = [], 0
    for view in (views or list(V)):
        data = _scene(pairs, view)
        if data is None:
            return [], 0
        for expr in _fits(pairs, view, cap=geom_cap):
            npos += 1
            for pol, table, const in fit_policies(data, expr):
                hyps.append({"view": view.value, "expr": expr, "policy": pol, "table": table, "const": const,
                             "complexity": (0 if expr[0] == "d1" else 1, POLICIES.index(pol))})
    return hyps, npos


def predict(h, test_input):
    from geocat_arc.object_reasoning.types import SegmentationVariant as V
    A = np.asarray(test_input)
    ctxs = [GG.Ctx(o, A) for o in _objects(test_input, V(h["view"]))]
    out = _predict([(A, ctxs)], h["expr"], h["policy"], h["table"], h["const"])
    return None if out is None else out[0].tolist()


def _decide(hyps, test_input):
    preds = {}
    for h in sorted(hyps, key=lambda h: h["complexity"]):
        p = predict(h, test_input)
        if p is None:
            continue
        preds.setdefault(str(p), {"pred": p, "support": 0, "first": h})["support"] += 1
    ranked = sorted(preds.values(), key=lambda d: (-d["support"], d["first"]["complexity"]))
    return ranked


def reason(train, test_inputs):
    """train: [(input, output)], test_inputs: [input]. Returns a decision record (no answers read)."""
    hyps, npos = version_space(train)
    rec = {"n_hypotheses": len(hyps), "n_positional": npos}
    if not hyps:
        rec["diagnosis"] = "NO_CONSISTENT_HYPOTHESIS:" + ("COLOUR_POLICY_GAP" if npos else "GEOMETRY_GAP")
        return rec
    attempts, unique = [], True
    for t in test_inputs:
        ranked = _decide(hyps, t)
        if not ranked:
            rec["diagnosis"] = "NO_CONSISTENT_HYPOTHESIS:UNPREDICTABLE_TEST"
            return rec
        unique = unique and len(ranked) == 1
        attempts.append([d["pred"] for d in ranked[:2]])
    rec["attempts"] = attempts
    rec["top"] = {k: (v if k != "expr" else GG.pretty(v)) for k, v in sorted(hyps, key=lambda h: h["complexity"])[0].items()
                  if k in ("view", "expr", "policy")}
    if not unique:
        rec["diagnosis"] = "MANY_CONSISTENT_DISAGREE"
        return rec
    folds = []
    for i in range(len(train)):
        rest = [p for j, p in enumerate(train) if j != i]
        fh, _n = version_space(rest)
        r = _decide(fh, train[i][0]) if fh else []
        ok = len(r) == 1 and np.array_equal(np.asarray(r[0]["pred"]), np.asarray(train[i][1]))
        folds.append("SUCCESS" if ok else ("ABSTAIN_TIE" if len(r) > 1 else "LOO_FAILURE"))
    rec["folds"] = folds
    rec["diagnosis"] = "CERTIFIED" if all(f == "SUCCESS" for f in folds) else "FOLD_FRAGILITY"
    rec["certified"] = rec["diagnosis"] == "CERTIFIED"
    return rec
