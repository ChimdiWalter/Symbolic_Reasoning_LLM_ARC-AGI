"""Reversible, fold-local adapter: constructed grouping views for the unchanged
native object engine (records/CORA_REP_GROWTH_PLAN_20261013.md, sections 3-5).

    with rep_growth("E") as ev:
        res = inducer.induce_program(pairs, cfg)
        ... render with program_apply_fn(res.program) inside the block ...

Modes:
- "off": the wrapper passes everything through (identity test);
- "D": failure-blind, ungated, ranked in canonical order;
- "E": failure-conditioned; gated on REPRESENTATION_LANGUAGE_INSUFFICIENT;
  ranked by the failure stage;
- "E-shuf": E's procedure with the gate decision and stage taken from
  another task (`shuffle=(diagnosis, stage)`).

At every `_induce_candidate(T, ...)` call, including leave-one-out folds and
internal re-searches:
1. the native attempt runs unchanged, and a train-perfect native attempt is
   returned as is;
2. otherwise the call is diagnosed from T, and the constructor proposes at
   most k novel, coherent programs computed from T's demonstrations alone;
3. each program is a pseudo-variant: an enum value-map entry plus a
   SEGMENTERS entry. It is prepended to the trial order for one re-run
   with its own explicit time slice (slice_s, default 8 s) beyond the
   native deadline. Arm B's larger budget matches this.

Everything is restored on exit.
"""
import contextlib
import time
from collections import Counter

import numpy as np

from cora_rep_growth import grammar as G

LANG_STAGES = ("segmentation", "matching", "selector")
# Search-insufficiency rule applied when the native deadline was reached: set by
# plan amendment 1 after the development measurement. Until then: never.
SEARCH_RULE = lambda att: False


def _np(grid):
    return np.asarray(grid.to_numpy())


def make_segmenter(prog):
    from geocat_arc.object_reasoning.types import MultiColorObject
    from geocat_arc.perception.objects import ARCObject

    def seg(grid, background=None):
        g = _np(grid)
        bg = 0 if background is None else background
        out = []
        for i, cells in enumerate(G.apply(prog, g, bg)):
            cols = {x: int(g[x]) for x in cells}
            r0, c0, r1, c1 = G._bbox(cells)
            bbox = (r0, c0, r1 + 1, c1 + 1)
            if len(set(cols.values())) == 1:
                out.append(ARCObject(id=i, cells=frozenset(cells), color=next(iter(cols.values())), bounding_box=bbox))
            else:
                maj = sorted(Counter(cols.values()).items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
                out.append(MultiColorObject(id=i, cells=frozenset(cells), color=maj, bounding_box=bbox, cell_colors=cols))
        return out
    return seg


class _Registry:
    def __init__(self):
        from geocat_arc.object_reasoning.types import SegmentationVariant as SV
        import geocat_arc.object_reasoning.segmentation as S
        self.SV, self.S, self.made = SV, S, []

    def get(self, prog):
        val = "G:" + G.name(prog)
        m = self.SV._value2member_map_.get(val)
        if m is None:
            m = object.__new__(self.SV)
            m._value_, m._name_ = val, "GROWN_" + str(len(self.made))
            self.SV._value2member_map_[val] = m
            self.S.SEGMENTERS[m] = make_segmenter(prog)
            self.made.append(m)
        return m

    def clear(self):
        for m in self.made:
            self.SV._value2member_map_.pop(m._value_, None)
            self.S.SEGMENTERS.pop(m, None)
        self.made = []


def native_view_info(train_pairs):
    """Coherent / kept / cut native views on T (the inducer's own admission rule)."""
    import geocat_arc.object_reasoning.inducer as I
    import geocat_arc.object_reasoning.segmentation as S
    order = [v for v in I.SEGMENTATION_TRIAL_ORDER if not str(v.value).startswith("G:")]
    res = {v: S.evaluate_variant(v, train_pairs) for v in order}
    cands = [v for v in order if res[v].coherent]
    cands.sort(key=lambda v: 1 if res[v].create_orphan_relaxed else 0)
    kept = cands[:I.MAX_SEG_VARIANTS_TRIED]
    return res, cands, kept, [v for v in cands if v not in kept]


def diagnose(att, train_pairs, deadline=None):
    _, _, _, cut = native_view_info(train_pairs)
    if cut:
        return "REPRESENTATION_EXCLUDED", None
    stage = getattr(getattr(att, "stage", None), "value", None)
    if stage in LANG_STAGES:
        return "REPRESENTATION_LANGUAGE_INSUFFICIENT", stage
    if stage == "parameter":
        return "EXECUTABLE_OPERATION_MISSING", stage
    return "UNKNOWN", stage


def _native_partitions(train_pairs):
    import geocat_arc.object_reasoning.inducer as I
    import geocat_arc.object_reasoning.segmentation as S
    out = []
    for gi, _ in train_pairs:
        out.append({G.partition_key([frozenset(o.cells) for o in S.segment(gi, v, S.background_for(gi, v))])
                    for v in I.SEGMENTATION_TRIAL_ORDER if not str(v.value).startswith("G:")})
    return out


def _stage_score(prog, stage, pairs_np):
    if stage == "matching":
        cnt = [(len(G.apply(prog, a)), len(G.apply(prog, b))) for a, b in pairs_np]
        same = all(i == o for i, o in cnt)
        const = len({o for _, o in cnt}) == 1
        ratio = len({(o / i) if i else None for i, o in cnt}) == 1
        return float(same or const or ratio)
    if stage == "selector":
        feats = {"size": [], "colour": [], "shape": []}
        for a, b in pairs_np:
            if a.shape != b.shape:
                return 0.0
            for cells in G.apply(prog, a):
                ch = any(a[x] != b[x] for x in cells)
                feats["size"].append((len(cells), ch))
                feats["colour"].append((frozenset(int(a[x]) for x in cells), ch))
                feats["shape"].append((G._shape_key(cells), ch))
        sep = 0
        for vals in feats.values():
            chv, unv = {v for v, c in vals if c}, {v for v, c in vals if not c}
            sep += bool(chv) and bool(unv) and not (chv & unv)
        return float(sep)
    return 0.0


def construct(mode, train_pairs, stage, k, reg, budget_left=None):
    """Up to k novel, coherent programs for T. Uses only T's own pairs."""
    import geocat_arc.object_reasoning.segmentation as S
    t0 = time.monotonic()
    pairs_np = [(_np(a), _np(b)) for a, b in train_pairs]
    native = _native_partitions(train_pairs)
    seen, novel = set(), []
    for prog in G.programs():
        parts = [G.partition_key(G.apply(prog, a)) for a, _ in pairs_np]
        sig = tuple(parts)
        if sig in seen:
            continue
        seen.add(sig)
        if all(p not in nat for p, nat in zip(parts, native)):
            novel.append(prog)
    if mode in ("E", "E-shuf") and stage in ("matching", "selector"):
        novel.sort(key=lambda p: -_stage_score(p, stage, pairs_np))     # stable: canonical order breaks ties
    chosen, coh = [], {}
    for prog in novel:
        if budget_left is not None and time.monotonic() - t0 > budget_left:
            break
        r = S.evaluate_variant(reg.get(prog), train_pairs)
        if r.coherent:
            coh[G.name(prog)] = (float(r.coherence), float(r.pixel_coverage))
            chosen.append(prog)
            if len(chosen) >= k and not (mode in ("E", "E-shuf") and stage == "segmentation"):
                break
    if mode in ("E", "E-shuf") and stage == "segmentation":
        chosen.sort(key=lambda p: (-coh[G.name(p)][0], -coh[G.name(p)][1]))
    return chosen[:k], {"novel": len(novel), "coherent_checked": len(coh)}


@contextlib.contextmanager
def rep_growth(mode, k=2, shuffle=None, slice_s=8.0):
    import geocat_arc.object_reasoning.inducer as I
    orig, order0 = I._induce_candidate, I.SEGMENTATION_TRIAL_ORDER
    reg = _Registry()
    ev = {"mode": mode, "calls": 0, "failed_calls": 0, "diagnoses": Counter(), "constructed_calls": 0,
          "programs_tried": 0, "wins": [], "novel_seen": 0, "calls_log": []}

    def wrapper(train_pairs, config, deadline, meta, partial_sink=None, explore_all=False):
        ev["calls"] += 1
        t_call = time.monotonic()
        att = orig(train_pairs, config, deadline, meta, partial_sink, explore_all)
        if att.programs:
            ev["calls_log"].append({"pairs": len(train_pairs), "ok": True, "s": round(time.monotonic() - t_call, 2)})
            return att
        ev["failed_calls"] += 1
        deadline_hit = deadline is not None and time.monotonic() >= deadline
        diag, stage = diagnose(att, train_pairs)   # logged in every mode, "off" included
        if deadline_hit and diag == "REPRESENTATION_LANGUAGE_INSUFFICIENT" and SEARCH_RULE(att):
            diag = "SEARCH_INSUFFICIENT"
        ev["diagnoses"][diag] += 1
        ev["calls_log"].append({"pairs": len(train_pairs), "ok": False, "s": round(time.monotonic() - t_call, 2),
                                "deadline_hit": deadline_hit, "diag": diag, "stage": stage,
                                "fit_objects": round(float(getattr(att, "fit_objects", 0.0)), 3)})
        if mode == "off":
            return att
        if mode == "E-shuf" and shuffle is not None:
            diag, stage = shuffle
        if mode in ("E", "E-shuf") and diag != "REPRESENTATION_LANGUAGE_INSUFFICIENT":
            return att
        progs, info = construct(mode, train_pairs, stage, k, reg, budget_left=slice_s)
        ev["novel_seen"] += info["novel"]
        if progs:
            ev["constructed_calls"] += 1
        for prog in progs:
            pv = reg.get(prog)
            ev["programs_tried"] += 1
            d2 = max(deadline if deadline is not None else time.monotonic(), time.monotonic()) + slice_s
            I.SEGMENTATION_TRIAL_ORDER = (pv,) + tuple(order0)
            try:
                att2 = orig(train_pairs, config, d2, meta, partial_sink, explore_all)
            finally:
                I.SEGMENTATION_TRIAL_ORDER = order0
            if att2.programs:
                ev["wins"].append({"pairs": len(train_pairs), "program": G.name(prog)})
                return att2
        return att

    I._induce_candidate = wrapper
    try:
        yield ev
    finally:
        I._induce_candidate, I.SEGMENTATION_TRIAL_ORDER = orig, order0
        reg.clear()
