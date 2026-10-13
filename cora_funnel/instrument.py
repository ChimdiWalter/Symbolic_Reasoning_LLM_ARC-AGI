"""Read-only funnel probe around the frozen native object layer.

`probe(n_top, test_inputs)` wraps five native names for the duration of one
task and restores them on exit:
- `engine.induce_program`, to count the frames: call 0 is the identity
  frame, calls 1-7 are the dihedral reframings in engine.py's order;
- `inducer._induce_composed`: each outermost call on all n_top pairs is a
  candidate-producing search (initial, phase B forced, phase C). Calls on
  n_top - 1 pairs are leave-one-out folds;
- `inducer.loo_validate`: every certification decision;
- `inducer.rank_by_score`: the order native would commit in;
- `generative.induce_generative_candidates`: the top-level generative
  fallback.

Train-exact candidates are kept by reference and rendered on the test inputs
only after the task finishes (`finalize`), so the probe spends none of the
native deadline. Rendering uses inputs only, never answers; framed
candidates go through the native FramedProgram. The probe changes no return
value: native behaviour is unchanged.
"""
import contextlib
import time

import numpy as np

# identity, then the engine's reframing order (engine.py, round-13 fallback)
FRAMES = ((0, False), (1, False), (2, False), (3, False), (0, True), (1, True), (2, True), (3, True))
K_RENDER = 24


def render(prog, frame, test_inputs):
    from geocat_arc.object_reasoning.actions import program_apply_fn
    from geocat_arc.object_reasoning.types import FramedProgram
    p = prog if frame in (None, (0, False)) else FramedProgram(frame=frame, inner=prog)
    try:
        fn = program_apply_fn(p)
    except Exception:                                                   # noqa: BLE001
        return None
    out = []
    for x in test_inputs:
        try:
            out.append(np.asarray(fn(np.asarray(x)), dtype=int).tolist())
        except Exception:                                               # noqa: BLE001
            out.append(None)
    return out


def perception(train_pairs):
    """Observation only: which native views pass the inducer's own coherence
    rule on the demonstrations, and which 4 the variant cap keeps."""
    import geocat_arc.object_reasoning.inducer as I
    import geocat_arc.object_reasoning.segmentation as S
    order = list(I.SEGMENTATION_TRIAL_ORDER)
    coh = []
    for v in order:
        try:
            if S.evaluate_variant(v, train_pairs).coherent:
                coh.append(v.value)
        except Exception:                                               # noqa: BLE001
            pass
    return {"coherent": coh, "n_coherent": len(coh), "kept_by_cap": coh[:I.MAX_SEG_VARIANTS_TRIED]}


@contextlib.contextmanager
def probe(n_top, test_inputs):
    import geocat_arc.object_reasoning.engine as E
    import geocat_arc.object_reasoning.generative as GEN
    import geocat_arc.object_reasoning.inducer as I
    rec = {"events": [], "frames": [], "_pending": []}
    st = {"frame": -1, "depth": 0, "lists": {}}
    orig = (E.induce_program, I._induce_composed, I.loo_validate, I.rank_by_score, GEN.induce_generative_candidates)
    o_ip, o_ic, o_loo, o_rank, o_gen = orig

    def frame():
        return FRAMES[st["frame"]] if 0 <= st["frame"] < len(FRAMES) else None

    def ip(pairs, *a, **k):
        st["frame"] += 1
        t0 = time.monotonic()
        res = o_ip(pairs, *a, **k)
        rec["frames"].append({"frame": st["frame"], "accepted": bool(res.accepted), "s": round(time.monotonic() - t0, 2),
                              "hypotheses": int(getattr(res, "hypotheses_enumerated", 0) or 0),
                              "failure_stage": getattr(res.failure_stage, "value", None)})
        return res

    def ic(train_pairs, config, deadline, *a, **k):
        outer = st["depth"] == 0
        st["depth"] += 1
        t0 = time.monotonic()
        try:
            att = o_ic(train_pairs, config, deadline, *a, **k)
        finally:
            st["depth"] -= 1
        if not outer:
            return att
        hit = bool(deadline is not None and time.monotonic() >= deadline - 0.25)
        progs = list(att.programs or [])
        if len(train_pairs) == n_top:
            ev = {"type": "search", "frame": st["frame"], "force_compose": bool(k.get("force_compose", a[2] if len(a) > 2 else False)),
                  "n_programs": len(progs), "stage": getattr(att.stage, "value", None),
                  "fit_objects": round(float(att.fit_objects), 3), "fit_pixels": round(float(att.fit_pixels), 3),
                  "seg": att.seg.variant.value if att.seg is not None else None, "deadline_hit": hit,
                  "s": round(time.monotonic() - t0, 2), "kinds": [type(p).__name__ for p in progs[:K_RENDER]],
                  "outputs": None, "rank": None}
            rec["events"].append(ev)
            rec["_pending"].append((ev, progs[:K_RENDER], frame()))
            st["lists"][id(att.programs)] = (att.programs, ev)
        elif len(train_pairs) == n_top - 1:
            rec["events"].append({"type": "fold", "frame": st["frame"], "n_programs": len(progs), "deadline_hit": hit,
                                  "s": round(time.monotonic() - t0, 2), "stage": getattr(att.stage, "value", None)})
        return att

    def loo(fn, train_pairs):
        r = o_loo(fn, train_pairs)
        if len(train_pairs) == n_top:
            rec["events"].append({"type": "loo", "frame": st["frame"], "folds": int(r.folds), "passed": int(r.passed),
                                  "all_passed": bool(r.all_passed), "failed": [int(i) for i in (r.failed_pair_indices or [])]})
        return r

    def rank(programs, loo_reports, cfg):
        r = o_rank(programs, loo_reports, cfg)
        hit = st["lists"].get(id(programs))
        if hit is not None and hit[0] is programs:
            hit[1]["rank"] = [next(i for i, q in enumerate(programs) if q is p) for p in r]
        return r

    def gen(pairs, *a, **k):
        r = o_gen(pairs, *a, **k)
        if st["depth"] == 0 and len(pairs) == n_top:
            ev = {"type": "generative", "frame": st["frame"], "n_programs": len(r or []), "outputs": None}
            rec["events"].append(ev)
            rec["_pending"].append((ev, list(r or [])[:K_RENDER], frame()))
        return r

    E.induce_program, I._induce_composed, I.loo_validate, I.rank_by_score, GEN.induce_generative_candidates = ip, ic, loo, rank, gen
    try:
        yield rec
    finally:
        E.induce_program, I._induce_composed, I.loo_validate, I.rank_by_score, GEN.induce_generative_candidates = orig
        st["lists"].clear()


def finalize(rec, test_inputs):
    """After the task: render the kept candidates on the test inputs."""
    for ev, progs, fr in rec.pop("_pending", []):
        ev["outputs"] = [render(p, fr, test_inputs) for p in progs]
    return rec
