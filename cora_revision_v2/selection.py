"""CORA reasoning v2: SELECTION, the first slice of a typed scene transformation (DEVELOPMENT).

A typed scene transformation separates:
- object SELECTION (which objects act);
- the SPATIAL transformation (here, a G-grow geometry, which encodes native's growth modes);
- COLOUR assignment (v2's colour policies);
- grid COMPOSITION (here, overlay onto the input).

The unguarded v2 class applies one geometry to every object of a view. This module adds selection: the geometry acts
only on the objects a feature guard selects. Unselected objects add nothing, i.e. the null-else guard of
`cora_fhr/ggrow_guard.py`. Segmentation views and features are native's; nothing native is modified.

**Researcher-designed language expansion, not grammar induction.**

- `demo_fits_selectively(pair, view)`: does some single expression reproduce ONE demonstration's added cells when
  applied to a subset of the objects? Objects whose additions would overreach are left unselected. This is the
  observable test that separates "selection is missing" from "the geometry or the representation is outside the
  class".
- `version_space(pairs)`: every (view, geometry, guard, colour policy) that reproduces every training output exactly.
  The guard is a feature test, feature == value or feature in a value set, true on every object that must act and
  false on every object whose additions would be wrong. Hypotheses are dicts compatible with `scene_reasoner`.
- `predict(h, grid)`.

Only training pairs and test inputs are read.
"""
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from cora_fhr import ggrow as GG                                        # noqa: E402

FEATURES = ("size", "colours", "h", "w", "n_colours")
GEOM_CAP = 200


def _feat(x, f):
    return {"size": len(x.O), "colours": tuple(sorted(set(x.O.values()))), "h": x.h, "w": x.w,
            "n_colours": x.n_colours}[f]


class _Cache:
    """Per-object depth-1 results, shared by every expression (as in `oracle_expressibility._fits`)."""

    def __init__(self, ctxs):
        self.ctxs, self.r = ctxs, [{} for _ in ctxs]

    def r1(self, j, s, t):
        k = (s, t)
        if k not in self.r[j]:
            x = self.ctxs[j]
            self.r[j][k] = GG.transform(GG.TRANSFORMS[t], GG.source(GG.SOURCES[s], x), x)
        return self.r[j][k]

    def cells(self, e, j):
        x = self.ctxs[j]
        if e[0] == "d1":
            return GG.finalize(self.r1(j, e[1], e[2]), x)
        if e[0] == "d2":
            return GG.finalize(GG.transform(GG.TRANSFORMS[e[3]], self.r1(j, e[1], e[2]), x), x)
        return GG.finalize(self.r1(j, e[1], e[2]) | self.r1(j, e[1], e[3]), x)


def _demo(pair, view):
    from cora_revision_v2.scene_reasoner import _objects
    A, B = np.asarray(pair[0]), np.asarray(pair[1])
    if A.shape != B.shape:
        return None
    ctxs = [GG.Ctx(o, A) for o in _objects(pair[0], view)]
    return A, B, ctxs, {(int(r), int(c)) for r, c in zip(*np.nonzero(A != B))}


def _split(e, cache, changed):
    """Objects that must act (additions inside the change), must not (additions overreach), and the covered cells."""
    pos, neg, cover = [], [], set()
    for j in range(len(cache.ctxs)):
        s = cache.cells(e, j)
        if not s:
            continue
        if s <= changed:
            pos.append(j)
            cover |= s
        else:
            neg.append(j)
    return pos, neg, cover


def demo_fits_selectively(pair, view, deadline=None):
    """True / False, or None if the CPU deadline (time.process_time) passed first."""
    d = _demo(pair, view)
    if d is None or not d[3]:
        return False
    A, B, ctxs, changed = d
    cache = _Cache(ctxs)
    for n, e in enumerate(GG.expressions()):
        if deadline is not None and n % 500 == 0 and time.process_time() > deadline:
            return None
        pos, _neg, cover = _split(e, cache, changed)
        if pos and cover == changed:
            return True
    return False


def _guards(pos_x, neg_x):
    """Feature tests true on every positive and false on every negative (simplest first)."""
    out = []
    for f in FEATURES:
        pv = {_feat(x, f) for x in pos_x}
        nv = {_feat(x, f) for x in neg_x}
        if pv & nv:
            continue
        out.append((f, tuple(sorted(pv, key=str))))
    return sorted(out, key=lambda g: (len(g[1]), FEATURES.index(g[0])))


def version_space(pairs, views=None, geom_cap=GEOM_CAP, deadline=None):
    """(view, geometry, guard, colour policy) hypotheses reproducing every pair exactly; unguarded fits excluded (they
    belong to the base class). Returns (hyps, n_selective_geometries, complete)."""
    from geocat_arc.object_reasoning.types import SegmentationVariant as V
    from cora_revision_v2 import scene_reasoner as SR
    hyps, nsel = [], 0
    for view in (views or list(V)):
        demos = [_demo(p, view) for p in pairs]
        if any(d is None for d in demos):
            return [], 0, True
        caches = [_Cache(d[2]) for d in demos]
        found = 0
        for n, e in enumerate(GG.expressions()):
            if deadline is not None and n % 500 == 0 and time.process_time() > deadline:
                return hyps, nsel, False
            pos_x, neg_x, ok, uniform = [], [], True, True
            for (A, B, ctxs, changed), cache in zip(demos, caches):
                pos, neg, cover = _split(e, cache, changed)
                if cover != changed:
                    ok = False
                    break
                uniform = uniform and not neg
                pos_x += [ctxs[j] for j in pos]
                neg_x += [ctxs[j] for j in neg]
            if not ok or uniform or not pos_x:
                continue
            gs = _guards(pos_x, neg_x)
            if not gs:
                continue
            nsel += 1
            found += 1
            for f, vals in gs[:2]:
                data = [(A, B, [x for x in ctxs if _feat(x, f) in vals]) for A, B, ctxs, _c in demos]
                for pol, table, const in SR.fit_policies(data, e):
                    hyps.append({"family": "select", "view": view.value, "expr": e, "guard": [f, list(vals)],
                                 "policy": pol, "table": table, "const": const,
                                 "complexity": (2 if e[0] == "d1" else 3, SR.POLICIES.index(pol))})
            if found >= geom_cap:
                break
    return hyps, nsel, True


def predict(h, test_input):
    from geocat_arc.object_reasoning.types import SegmentationVariant as V
    from cora_revision_v2 import scene_reasoner as SR
    A = np.asarray(test_input)
    f, vals = h["guard"][0], h["guard"][1]
    vals = {tuple(v) if isinstance(v, list) else v for v in vals}
    ctxs = [x for x in (GG.Ctx(o, A) for o in SR._objects(test_input, V(h["view"]))) if _feat(x, f) in vals]
    out = SR._predict([(A, ctxs)], h["expr"], h["policy"], h["table"], h["const"])
    return None if out is None else out[0].tolist()
