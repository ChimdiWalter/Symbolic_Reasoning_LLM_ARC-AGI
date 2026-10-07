"""CORA-TTI Item-2 v1.9: decision tracing for K* (+ {e}), observation only.

The v1.9 engine acceptance stability audit asks why the same compiled
extension is accepted with seven demonstrations and rejected with six.
This module records the engine's decision chain for one run of the frozen
runner (`v17_compiler.run_reasoner`) without changing a decision:

- every patch wraps one engine function, calls it with the same arguments,
  returns its value unchanged and appends what it saw to the trace;
- every patch is removed on exit, before and after the K* state snapshot
  (patches are applied outside `kstar()`, so its snapshot sees one
  consistent set of functions);
- nothing in geocat_arc, the scoped fitter, the v1.7 compiler or the v1.8
  proposer is edited.

Patched (module attributes, restored on exit):
  engine.induce_program            the induction result of the run
  inducer.loo_validate             the engine's own leave-one-out, per fold
  inducer._induce_composed         the ranked candidate pool per context
  meta_induction.trigger_fires     routing into the expression phase
  meta_induction.search_with_concepts   the installed-concept search
  scoped_slot_fitting.fit_induced_occurrences   the concept's fit, with
                                   the fitter's own failure evidence

Clock conditions (`clock=`): WALL (no patch: the host's wall clock),
CPU1 (the engine reads process CPU time instead of the wall clock, so host
contention cannot move a deadline: the controlled low-contention condition)
and CPU10 (process CPU time at one tenth rate: ten times the CPU budget).
Only `time` inside geocat_arc modules and the fitter is replaced; the
runner's own wall-clock seconds are unaffected.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import sys
import time
import types

from cora_arc2026 import v17_compiler as X

VERSION = "1.9.0-audit"
CLOCKS = ("WALL", "CPU1", "CPU10")
_SCALE = {"CPU1": 1.0, "CPU10": 0.1}

_T = None   # the active trace


def _mods():
    from geocat_arc.object_reasoning import engine as E
    from geocat_arc.object_reasoning import inducer as I
    from geocat_arc.object_reasoning import meta_induction as MI
    return E, I, MI, X._sf()


def _now():
    """The engine's clock as the engine sees it (shimmed or not)."""
    _, I, _, _ = _mods()
    return I.time.monotonic()


def _time_shim(scale: float):
    shim = types.ModuleType("time")          # a module, so K*'s snapshot skips it
    for k in dir(time):
        if not k.startswith("__"):
            setattr(shim, k, getattr(time, k))
    shim.monotonic = lambda: time.process_time() * scale
    shim.perf_counter = shim.monotonic
    return shim


@contextlib.contextmanager
def _clock(mode: str):
    if mode not in CLOCKS:
        raise ValueError(mode)
    if mode == "WALL":
        yield []
        return
    shim = _time_shim(_SCALE[mode])
    patched = []
    _, _, _, SF = _mods()
    for name, mod in list(sys.modules.items()):
        if mod is None:
            continue
        if not (name.startswith("geocat_arc.") or mod is SF):
            continue
        if getattr(mod, "time", None) is time:
            patched.append((mod, "time"))
            mod.time = shim
    try:
        yield [m.__name__ for m, _ in patched]
    finally:
        for mod, attr in patched:
            setattr(mod, attr, time)


def _ctx():
    return _T["stack"][-1]


def _w_induce_program(orig):
    def induce_program(*args, **kwargs):
        rec = {"n": len(args[0]), "t0": _now()}
        res = orig(*args, **kwargs)
        rec.update(result=res, t1=_now())
        _T["induce_program"].append(rec)
        return res
    return induce_program


def _w_loo(orig):
    def loo_validate(fn, train_pairs):
        k = len(_T["loo"])
        rec = {"k": k, "phase": getattr(fn, "__name__", "?"), "n": len(train_pairs),
               "ctx": _ctx(), "folds": [], "t0": _now()}
        _T["loo"].append(rec)
        ids = [id(p) for p in train_pairs]

        def fold_fn(subset):
            sub = {id(p) for p in subset}
            hold = [i for i, x in enumerate(ids) if x not in sub]
            frec = {"hold": hold[0] if len(hold) == 1 else hold, "n_sub": len(subset),
                    "t0": _now()}
            rec["folds"].append(frec)
            _T["stack"].append(("LOO", k, rec["phase"], frec["hold"]))
            try:
                r = fn(subset)
                frec["result"] = r
                return r
            except BaseException as exc:                     # noqa: BLE001
                frec["exception"] = type(exc).__name__
                raise
            finally:
                frec["t1"] = _now()
                _T["stack"].pop()
        report = orig(fold_fn, train_pairs)
        rec.update(report=report, t1=_now())
        return report
    return loo_validate


def _w_composed(orig):
    def _induce_composed(*args, **kwargs):
        depth = _T["composed_depth"]
        _T["composed_depth"] = depth + 1
        t0 = _now()
        try:
            att = orig(*args, **kwargs)
        finally:
            _T["composed_depth"] = depth
        if depth == 0:
            cfg = args[1] if len(args) > 1 else kwargs.get("config")
            _T["composed"].append({
                "ctx": _ctx(), "n": len(args[0]), "t0": t0, "t1": _now(),
                "deadline": args[2] if len(args) > 2 else kwargs.get("deadline"),
                "force_compose": bool(kwargs.get("force_compose", False)),
                "force_relational": bool(getattr(cfg, "force_relational", False)),
                "programs": list(att.programs), "stage": getattr(att.stage, "value", None)})
        return att
    return _induce_composed


def _w_trigger(orig):
    def trigger_fires(train_pairs):
        fired = orig(train_pairs)
        _T["trigger"].append({"ctx": _ctx(), "n": len(train_pairs), "fired": bool(fired)})
        return fired
    return trigger_fires


def _w_search(orig, MI):
    def search_with_concepts(pairs, concepts, deadline=None):
        total = 0
        for concept in concepts:
            types_ = MI.meta_ast.free_slot_types(concept.schema)
            n = 1
            for slot, kind in types_.items():
                if kind in MI.meta_ast.ENUMERABLE_TYPES:
                    n *= len(MI.meta_ast.slot_domain(kind))
            total += n
        rec = {"ctx": _ctx(), "n": len(pairs), "concepts": [c.name for c in concepts],
               "bindings_total": total, "deadline": deadline, "t0": _now(), "fits": []}
        _T["search"].append(rec)
        prev = _T["in_search"]
        _T["in_search"] = rec
        try:
            found, stats = orig(pairs, concepts, deadline=deadline)
        finally:
            _T["in_search"] = prev
        rec.update(hits=[(getattr(c, "name", None), ast) for c, ast in found],
                   stats=stats.as_dict(), t1=_now(),
                   past_deadline=bool(deadline is not None and _now() > deadline))
        return found, stats
    return search_with_concepts


def _w_fit(orig):
    def fit_induced_occurrences(schema, pairs, require_exact_replay=True):
        fitted, ev = orig(schema, pairs, require_exact_replay=require_exact_replay)
        rec = _T["in_search"] if _T is not None else None
        if rec is not None:
            rec["fits"].append({"n": len(pairs), "ok": fitted is not None,
                                "failure": ev.get("failure"), "detail": ev.get("detail"),
                                "fitted": fitted})
        return fitted, ev
    return fit_induced_occurrences


@contextlib.contextmanager
def traced(clock: str = "WALL"):
    """Trace one or more frozen-runner calls. Yields the trace dict."""
    global _T
    if _T is not None:
        raise RuntimeError("a trace is already active")
    E, I, MI, SF = _mods()
    _T = {"stack": [("TOP",)], "composed_depth": 0, "induce_program": [], "loo": [],
          "composed": [], "trigger": [], "search": [], "in_search": None, "clock": clock}
    saved = [(E, "induce_program", E.induce_program), (I, "loo_validate", I.loo_validate),
             (I, "_induce_composed", I._induce_composed), (MI, "trigger_fires", MI.trigger_fires),
             (MI, "search_with_concepts", MI.search_with_concepts),
             (SF, "fit_induced_occurrences", SF.fit_induced_occurrences)]
    E.induce_program = _w_induce_program(E.induce_program)
    I.loo_validate = _w_loo(I.loo_validate)
    I._induce_composed = _w_composed(I._induce_composed)
    MI.trigger_fires = _w_trigger(MI.trigger_fires)
    MI.search_with_concepts = _w_search(MI.search_with_concepts, MI)
    SF.fit_induced_occurrences = _w_fit(SF.fit_induced_occurrences)
    try:
        with _clock(clock) as patched:
            _T["clock_patched"] = patched
            yield _T
    finally:
        for mod, attr, fn in saved:
            setattr(mod, attr, fn)
        _T = None


def untraced_identity():
    """True when no tracing patch is left on any engine attribute."""
    E, I, MI, SF = _mods()
    return all(getattr(f, "__name__", "") and getattr(f, "__module__", "") != __name__
               for f in (E.induce_program, I.loo_validate, I._induce_composed,
                         MI.trigger_fires, MI.search_with_concepts, SF.fit_induced_occurrences))


def program_sha(p) -> str:
    return hashlib.sha256(json.dumps(p.to_dict(), sort_keys=True, default=str).encode()).hexdigest()[:16]
