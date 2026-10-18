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


def native_all_records(train, obj_dir, budget_s):
    """Control C' (proposed Amendment 2): the SAME identity-frame native induction as arm E, observed the same
    way, but recording EVERY growth correspondence native built (any mode, not only the `pattern` fallbacks).
    The object correspondence source and the extraction compute equal E's. Only the failure filter (which
    correspondences native could not explain and memorized) is withheld."""
    import contextlib
    import hashlib
    import json as _json
    import geocat_arc.object_reasoning.correspondence as CO
    import geocat_arc.object_reasoning.inducer as I
    from geocat_arc.object_reasoning.engine import ObjectReasoningEngine
    from geocat_arc.object_reasoning.inducer import InductionConfig, induce_program
    from geocat_arc.object_reasoning.types import to_grid_pairs
    from cora_reach.instances import _cells, _grid_list

    @contextlib.contextmanager
    def observed_all():
        orig, orig_ev = CO.detect_grow, I.enumerate_labeled_tables
        seen, cur = [], {"v": None}

        def detect_grow(in_cc, out_cc, bounds, grid=None):
            res = orig(in_cc, out_cc, bounds, grid)
            if res is not None and any(c not in in_cc for c in out_cc):
                seen.append((in_cc, out_cc, bounds, grid, cur["v"], res.get("mode")))
            return res

        def enumerate_labeled_tables(seg, *args, **kwargs):
            prev = cur["v"]
            cur["v"] = getattr(getattr(seg, "variant", None), "value", None)
            try:
                yield from orig_ev(seg, *args, **kwargs)
            finally:
                cur["v"] = prev
        CO.detect_grow, I.enumerate_labeled_tables = detect_grow, enumerate_labeled_tables
        try:
            yield seen
        finally:
            CO.detect_grow, I.enumerate_labeled_tables = orig, orig_ev
    eng = ObjectReasoningEngine(obj_dir, use_library=True, config=InductionConfig(budget_s=budget_s))
    cfg = eng._config_with_library()
    with observed_all() as seen:
        induce_program(to_grid_pairs(train), cfg)
    inputs = {hashlib.sha256(_json.dumps(np.asarray(a).astype(int).tolist()).encode()).hexdigest(): d
              for d, (a, _b) in enumerate(train)}
    uniq = {}
    for in_cc, out_cc, bounds, grid, variant, mode in seen:
        key = (variant, tuple(sorted(in_cc.items())), tuple(sorted(out_cc.items())))
        if key in uniq:
            continue
        g = _grid_list(grid)
        gh = hashlib.sha256(_json.dumps(g).encode()).hexdigest() if g is not None else None
        uniq[key] = {"variant": variant, "in": _cells(in_cc), "out": _cells(out_cc), "bounds": list(bounds),
                     "demo": inputs.get(gh), "grid": g, "native_mode": mode}
    return list(uniq.values())


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


def propose_guarded(groups, classify=True) -> dict:
    """Guard-probe arms only (records/CORA_FHR_GUARD_PROBE_PROTOCOL_20261018.md). This is propose(), except
    that a supported view with no joint G-grow fit may yield a guarded operator (ggrow_guard): one object
    feature selecting between two G-grow expressions. An unguarded fit always wins."""
    from cora_fhr import ggrow_guard as GU
    t0 = time.time()
    proposals, tried_total = [], 0
    for view, insts in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        insts = insts[:MAX_INSTANCES]
        demos = sorted({d for *_x, d, _c in insts if d is not None})
        if len(demos) < SUPPORT_DEMOS:
            continue
        trip = [(O, A, G) for O, A, G, _d, _c in insts]
        expr, n_fit, tried = GG.search(trip, first_only=False, count_cap=500)
        tried_total += tried
        if expr is not None:
            ext, pretty, guarded = GG.make(expr), GG.pretty(expr), False
        else:
            found = GU.search(trip)
            if not found:
                continue
            g = found[0]
            ext = GU.make({"guard": g["guard"], "then": g["then"], "else": g["else"]})
            pretty, guarded, n_fit = GU.pretty(g), True, len(found)
        nov = BL.classify(trip, [c for *_x, c in insts]) if classify else None
        proposals.append({"ext": ext, "pretty": pretty, "view": view, "instances": len(insts), "demos": demos,
                          "n_fitting": n_fit, "novelty": nov, "guarded": guarded})
        if len(proposals) >= MAX_PROPOSALS:
            break
    return {"proposals": proposals, "views": {v: len(x) for v, x in groups.items()},
            "expressions_tried": tried_total, "seconds": round(time.time() - t0, 3)}
