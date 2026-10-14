"""Instances and proposals for the construction arms (protocol sections 3-4; grammar section 5; Amendment 1).

Instance = (O: cell -> colour, A: added cells, G: input grid, demo index, colour of A).

- E authentic: native's own `pattern` fallbacks during an identity-frame induction on the demonstrations
  (cora_reach.instances.extract, unchanged), grouped by the segmentation view native was in.
- C failure-blind, with object access matched to E (Amendment 1): for each of native's seven segmentation
  views, every demonstration input is segmented by native's own segment(); the added cells (background in
  the input, non-background in the output, with no input cell changed) are attributed to the nearest
  object (Chebyshev distance to its cells; a tie discards that view for that demonstration). No trace of
  the reasoner's failure is read.
- D shuffled: arm E's instances of a donor task.

propose(): per view (most instances first, then name), at least SUPPORT_DEMOS demonstrations, at most
MAX_INSTANCES instances, the canonical-first G-grow expression that reproduces every instance exactly;
at most MAX_PROPOSALS across views. Nothing reads a target, a test input or a task id.
"""
import time

import numpy as np

from cora_reach import construct as CN

from cora_fhr import baseline as BL
from cora_fhr import ggrow as GG

SUPPORT_DEMOS, MAX_INSTANCES, MAX_PROPOSALS = CN.SUPPORT_DEMOS, CN.MAX_INSTANCES, CN.MAX_PROPOSALS


def group_reach_records(raw):
    """cora_reach instance records -> {view: [instance]} (single-colour, non-empty added cells)."""
    out = {}
    for i in raw:
        if i.get("grid") is None:
            continue
        G = np.asarray(i["grid"], dtype=int)
        O = {tuple(c): int(col) for c, col in i["in"]}
        out_cc = {tuple(c): int(col) for c, col in i["out"]}
        A = {c: col for c, col in out_cc.items() if c not in O}
        if not A or len(set(A.values())) != 1:
            continue
        out.setdefault(str(i.get("variant")), []).append((O, set(A), G, i.get("demo"), next(iter(set(A.values())))))
    return out


def authentic_records(train, obj_dir, budget_s):
    """Native's identity-frame induction on the demonstrations, observed (no answer, no test input)."""
    from cora_reach import instances as INST
    _ind, raw = INST.extract(train, obj_dir, budget_s=budget_s)
    return raw


def blind_groups(train):
    """Amendment 1: native's views, nearest-object attribution, no failure trace."""
    import geocat_arc.object_reasoning.inducer as I
    import geocat_arc.object_reasoning.segmentation as S
    from geocat_arc.object_reasoning.types import cell_colors_of
    from geocat_arc.perception.grid import Grid
    demos = []
    for a, b in train:
        a, b = np.asarray(a, dtype=int), np.asarray(b, dtype=int)
        if a.shape != b.shape:
            return {}, "shape_change"
        bg = int(min(zip(*np.unique(a, return_counts=True)), key=lambda vc: (-vc[1], vc[0]))[0])
        if ((a != bg) & (a != b)).any():
            return {}, "input_cell_changes"
        demos.append((a, b, bg, {(int(r), int(c)) for r, c in zip(*np.nonzero((a == bg) & (b != bg)))}))
    groups = {}
    for v in I.SEGMENTATION_TRIAL_ORDER:
        for d, (a, b, bg, added) in enumerate(demos):
            if not added:
                continue
            g = Grid(a)
            objs = [cell_colors_of(o) for o in S.segment(g, v, S.background_for(g, v))]
            objs = [o for o in objs if o]
            if not objs:
                continue
            owner, tie = {}, False
            for p in added:
                dist = [min(max(abs(p[0] - r), abs(p[1] - c)) for r, c in o) for o in objs]
                m = min(dist)
                if dist.count(m) > 1:
                    tie = True
                    break
                owner.setdefault(dist.index(m), set()).add(p)
            if tie:
                continue
            for k, cells in owner.items():
                cols = {int(b[p]) for p in cells}
                if len(cols) == 1:
                    groups.setdefault(v.value, []).append((objs[k], cells, a, d, next(iter(cols))))
    return groups, None


def propose(groups, classify=True) -> dict:
    t0 = time.time()
    proposals, tried_total = [], 0
    for view, insts in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        insts = insts[:MAX_INSTANCES]
        demos = sorted({d for *_x, d, _c in insts if d is not None})
        if len(demos) < SUPPORT_DEMOS:
            continue
        expr, n_fit, tried = GG.search([(O, A, G) for O, A, G, _d, _c in insts], first_only=False, count_cap=500)
        tried_total += tried
        if expr is None:
            continue
        ext = GG.make(expr)
        nov = BL.classify([(O, A, G) for O, A, G, _d, _c in insts], [c for *_x, c in insts]) if classify else None
        proposals.append({"ext": ext, "pretty": GG.pretty(expr), "view": view, "instances": len(insts),
                          "demos": demos, "n_fitting": n_fit, "novelty": nov})
        if len(proposals) >= MAX_PROPOSALS:
            break
    return {"proposals": proposals, "views": {v: len(x) for v, x in groups.items()},
            "expressions_tried": tried_total, "seconds": round(time.time() - t0, 3)}
