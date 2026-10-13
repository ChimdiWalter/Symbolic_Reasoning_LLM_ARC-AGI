"""CORA-RG adapter v1 (plan amendment 1): fold-local, reversible, in-process.

    with rep_growth(arm, unlabelled=[...], shuffle=obs_of_another_task) as ev:
        res = inducer.induce_program(pairs, cfg)
        ... render inside the block ...

Arms:
- A and B: pass-through. B differs only by budget. Every failed call is
  observed and logged.
- C (EXISTING_VIEW_CORRECTION): at a failed call with coherent views cut
  by the cap, re-run with the cut views first. No construction.
- D (FAILURE_BLIND_CONSTRUCTOR): construct at every failed call; k
  programs in canonical order; first success wins. No probes, no
  ambiguity check.
- E (SHUFFLED_FAILURE_CONSTRUCTOR): F's decision path driven by another
  task's observations (`shuffle`). The probes still act on this task's own
  T.
- F (FAILURE_CONDITIONED_CONSTRUCTOR), the intervention-based controller:
  1. the search probe, if the deadline was hit and fit ≥ 0.9;
  2. the existing-view probe, if cut views exist;
  3. construction, if the stage is segmentation, matching or selector,
     with abstention when two or more successful constructed programs
     disagree on the unlabelled inputs;
  4. otherwise abstain: EXECUTABLE_LANGUAGE_INSUFFICIENT or UNKNOWN.

Every probe is a real engine re-run on T, with its own time slice
(slice_s). A constructed view is a pseudo-variant: an enum value-map entry
plus a SEGMENTERS entry, prepended to the trial order for one re-run. The
cap, coherence test, ranking and leave-one-out are unchanged. Everything is
restored on exit.
"""
import contextlib
import time
from collections import Counter

import numpy as np

from cora_rep_growth import grammar as G

LANG_STAGES = ("segmentation", "matching", "selector")
SEARCH_FIT = 0.9


def _np(grid):
    return np.asarray(grid.to_numpy())


def make_segmenter(prog):
    from geocat_arc.object_reasoning.types import MultiColorObject
    from geocat_arc.perception.objects import ARCObject

    def seg(grid, background=None):
        g = _np(grid)
        out = []
        for i, cells in enumerate(G.apply(prog, g, 0 if background is None else background)):
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


def native_views():
    import geocat_arc.object_reasoning.inducer as I
    return [v for v in I.SEGMENTATION_TRIAL_ORDER if not str(v.value).startswith("G:")]


def view_info(train_pairs):
    """The inducer's own admission rule on T: the native views coherent but cut by the cap."""
    import geocat_arc.object_reasoning.inducer as I
    import geocat_arc.object_reasoning.segmentation as S
    order = native_views()
    res = {v: S.evaluate_variant(v, train_pairs) for v in order}
    cands = [v for v in order if res[v].coherent]
    cands.sort(key=lambda v: 1 if res[v].create_orphan_relaxed else 0)
    kept = cands[:I.MAX_SEG_VARIANTS_TRIED]
    return [v for v in cands if v not in kept]


def observe(att, train_pairs, deadline):
    stage = getattr(getattr(att, "stage", None), "value", None)
    return {"deadline_hit": bool(deadline is not None and time.monotonic() >= deadline),
            "fit_objects": round(float(getattr(att, "fit_objects", 0.0)), 3),
            "stage": stage, "cut": [v.value for v in view_info(train_pairs)]}


def _task_grids(train_pairs, unlabelled):
    grids = []
    for a, b in train_pairs:
        grids += [_np(a), _np(b)]
    return grids + [np.asarray(u) for u in (unlabelled or [])]


def _native_signatures(grids):
    """Per native view, its partitions of every task grid: the bounded old language."""
    import geocat_arc.object_reasoning.segmentation as S
    from geocat_arc.object_reasoning.types import to_grid_pairs
    gp = [to_grid_pairs([(g, g)])[0][0] for g in grids]
    return {v.value: tuple(G.partition_key([frozenset(o.cells) for o in S.segment(x, v, S.background_for(x, v))]) for x in gp)
            for v in native_views()}


def _stage_score(prog, stage, pairs_np):
    if stage == "matching":
        cnt = [(len(G.apply(prog, a)), len(G.apply(prog, b))) for a, b in pairs_np]
        return float(all(i == o for i, o in cnt) or len({o for _, o in cnt}) == 1
                     or len({(o / i) if i else None for i, o in cnt}) == 1)
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


def candidates(train_pairs, unlabelled, stage, conditioned, k, reg, budget_s):
    """Up to k NOVEL and coherent programs, built from T's demonstrations and
    the unlabelled inputs only. Novel means no native view equals the
    program's partitions on all task grids (exhaustive over S1-S7)."""
    import geocat_arc.object_reasoning.segmentation as S
    t0 = time.monotonic()
    grids = _task_grids(train_pairs, unlabelled)
    native = set(_native_signatures(grids).values())
    pairs_np = [(_np(a), _np(b)) for a, b in train_pairs]
    seen, novel = set(), []
    for prog in G.programs():
        sig = tuple(G.partition_key(G.apply(prog, g)) for g in grids)
        if sig in seen or sig in native:
            continue
        seen.add(sig)
        novel.append(prog)
    if conditioned and stage in ("matching", "selector"):
        novel.sort(key=lambda p: -_stage_score(p, stage, pairs_np))      # stable: canonical order breaks ties
    chosen, coh = [], {}
    for prog in novel:
        if time.monotonic() - t0 > budget_s:
            break
        r = S.evaluate_variant(reg.get(prog), train_pairs)
        if r.coherent:
            coh[G.name(prog)] = (float(r.coherence), float(r.pixel_coverage))
            chosen.append(prog)
            if len(chosen) >= k and not (conditioned and stage == "segmentation"):
                break
    if conditioned and stage == "segmentation":
        chosen.sort(key=lambda p: (-coh[G.name(p)][0], -coh[G.name(p)][1]))
    return chosen[:k], len(novel)


@contextlib.contextmanager
def rep_growth(arm, k=2, slice_s=8.0, unlabelled=None, shuffle=None, n_top=None):
    import geocat_arc.object_reasoning.inducer as I
    from geocat_arc.object_reasoning.actions import program_apply_fn
    orig, order0 = I._induce_candidate, I.SEGMENTATION_TRIAL_ORDER
    reg = _Registry()
    ev = {"arm": arm, "calls": 0, "failed_calls": 0, "decisions": Counter(), "probe_runs": 0,
          "constructed_tried": 0, "novel_seen": 0, "wins": [], "calls_log": [],
          "top_candidate": None}   # the first train-exact program at the task-level call (n_top pairs), before leave-one-out

    def rerun(train_pairs, config, deadline, meta, ps, ea, order):
        ev["probe_runs"] += 1
        d2 = max(deadline if deadline is not None else time.monotonic(), time.monotonic()) + slice_s
        I.SEGMENTATION_TRIAL_ORDER = tuple(order)
        try:
            return orig(train_pairs, config, d2, meta, ps, ea)
        finally:
            I.SEGMENTATION_TRIAL_ORDER = order0

    def renders(att):
        try:
            fn = program_apply_fn(att.programs[0])
            return tuple(np.asarray(fn(np.asarray(u))).tobytes() for u in (unlabelled or []))
        except Exception:                                              # noqa: BLE001
            return None

    def construct_and_run(train_pairs, config, deadline, meta, ps, ea, stage, conditioned, ambiguity):
        progs, n_novel = candidates(train_pairs, unlabelled, stage, conditioned, k, reg, slice_s)
        ev["novel_seen"] += n_novel
        wins = []
        for prog in progs:
            ev["constructed_tried"] += 1
            att2 = rerun(train_pairs, config, deadline, meta, ps, ea, (reg.get(prog),) + tuple(order0))
            if att2.programs:
                wins.append((prog, att2))
                if not ambiguity:
                    break
        if not progs:
            return None, "CANDIDATE_NOT_GENERATED"
        if not wins:
            return None, "UNKNOWN"
        if ambiguity and len(wins) >= 2 and len({renders(a) for _, a in wins}) > 1:
            return None, "HYPOTHESIS_AMBIGUOUS"
        ev["wins"].append({"pairs": len(train_pairs), "program": G.name(wins[0][0])})
        return wins[0][1], "REPRESENTATION_LANGUAGE_INSUFFICIENT"

    def controller(train_pairs, config, deadline, meta, ps, ea, own, dec):
        """Arm F (dec = own) or E (dec = shuffled). Probes act on T."""
        if dec["deadline_hit"] and dec["fit_objects"] >= SEARCH_FIT:
            a = rerun(train_pairs, config, deadline, meta, ps, ea, order0)
            if a.programs:
                return a, "SEARCH_BUDGET_EXHAUSTED"
        if dec["cut"]:
            cut = [v for v in order0 if v.value in own["cut"]]
            if cut:
                a = rerun(train_pairs, config, deadline, meta, ps, ea, cut + [v for v in order0 if v not in cut])
                if a.programs:
                    return a, "EXISTING_REPRESENTATION_EXCLUDED"
        if dec["stage"] in LANG_STAGES:
            return construct_and_run(train_pairs, config, deadline, meta, ps, ea, dec["stage"], True, True)
        if dec["stage"] == "parameter":
            return None, "EXECUTABLE_LANGUAGE_INSUFFICIENT"
        return None, "UNKNOWN"

    def wrapper(train_pairs, config, deadline, meta, partial_sink=None, explore_all=False):
        ev["calls"] += 1
        t0 = time.monotonic()
        att = orig(train_pairs, config, deadline, meta, partial_sink, explore_all)
        if att.programs:
            ev["calls_log"].append({"pairs": len(train_pairs), "ok": True, "s": round(time.monotonic() - t0, 2)})
            if n_top is not None and len(train_pairs) == n_top and ev["top_candidate"] is None:
                ev["top_candidate"] = att.programs[0]
            return att
        ev["failed_calls"] += 1
        own = observe(att, train_pairs, deadline)
        out, decision = None, "NONE"
        if arm == "C" and own["cut"]:
            cut = [v for v in order0 if v.value in own["cut"]]
            a = rerun(train_pairs, config, deadline, meta, partial_sink, explore_all, cut + [v for v in order0 if v not in cut])
            out, decision = (a, "EXISTING_REPRESENTATION_EXCLUDED") if a.programs else (None, "VIEW_CORRECTION_FAILED")
        elif arm == "D":
            out, decision = construct_and_run(train_pairs, config, deadline, meta, partial_sink, explore_all, own["stage"], False, False)
        elif arm in ("E", "F"):
            dec = dict(shuffle) if (arm == "E" and shuffle) else own
            out, decision = controller(train_pairs, config, deadline, meta, partial_sink, explore_all, own, dec)
        ev["decisions"][decision] += 1
        ev["calls_log"].append({"pairs": len(train_pairs), "ok": False, "s": round(time.monotonic() - t0, 2), **own,
                                "decision": decision, "adapted": out is not None})
        if out is not None and n_top is not None and len(train_pairs) == n_top and ev["top_candidate"] is None and out.programs:
            ev["top_candidate"] = out.programs[0]
        return out if out is not None else att

    I._induce_candidate = wrapper
    try:
        yield ev
    finally:
        I._induce_candidate, I.SEGMENTATION_TRIAL_ORDER = orig, order0
        reg.clear()
