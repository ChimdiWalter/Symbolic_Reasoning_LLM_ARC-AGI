"""Observation-only instrument (docs/CORA_REAL_TASK_LOO_STABILITY_v1.md
sections 3 to 5).

An engine run here is reach v1's: the harness object layer
(`harness.object_layer.run_object_task`) with at most one extension
installed by `cora_reach.bridge`, under
- the v1.9 tracer (every induce_program, the engine's own leave-one-out per
  fold, the ranked candidate pool per context), with its clock condition
  WALL or CPU1 (the engine's deadlines read process CPU time);
- a deadline spy on `inducer._check_deadline` (every `_BudgetExhausted`,
  with the tracer's context);
- a substitution spy on the bridge's `detect_grow` (how often the installed
  relation replaced a `pattern` memorization).
Every spy returns its wrapped function's value unchanged and is removed on
exit; the bridge's restoration check still applies. Nothing here reads a
target: held-out exactness compares against a held-out DEMONSTRATION.
"""
from __future__ import annotations

import collections
import contextlib
import os
import time

from cora_reach import bridge as BR
from cora_reach import census as CS
from cora_reach import construct as CN
from cora_reach import growth_ext as GE
from cora_reach import instances as INST
from cora_reach import measure as M
from cora_reach import relations as REL

VERSION = "loo-diag-1"
CLOCKS = ("WALL", "CPU1")
CPU_WALL_CAP_S = 3600            # wall hard cap under CPU1 (diagnostic only; budgets unchanged)
TOP_PROGRAMS = 3


def _load():
    return [round(x, 2) for x in os.getloadavg()]


@contextlib.contextmanager
def deadline_spy():
    """Count every _BudgetExhausted raised by inducer._check_deadline, by
    the tracer's context (top-level search or an inner leave-one-out fold)."""
    import geocat_arc.object_reasoning.inducer as I
    from cora_v19 import v19_trace as TR
    orig = I._check_deadline
    hits = collections.Counter()

    def _check_deadline(deadline):
        try:
            return orig(deadline)
        except I._BudgetExhausted:
            hits[repr(TR._T["stack"][-1]) if TR._T is not None else "untraced"] += 1
            raise
    I._check_deadline = _check_deadline
    try:
        yield hits
    finally:
        I._check_deadline = orig


@contextlib.contextmanager
def substitution_spy(name):
    """Inside the bridge: the results of correspondence.detect_grow by mode
    (the installed relation, the constant pattern, or another native mode)."""
    import geocat_arc.object_reasoning.correspondence as CO
    inner = CO.detect_grow
    counts = collections.Counter()

    def detect_grow(in_cc, out_cc, bounds, grid=None):
        res = inner(in_cc, out_cc, bounds, grid)
        mode = (res or {}).get("mode")
        counts["installed" if mode == name else ("pattern" if mode == "pattern" else
                                                 ("none" if mode is None else "native"))] += 1
        return res
    CO.detect_grow = detect_grow
    try:
        yield counts
    finally:
        CO.detect_grow = inner


def _induction_summary(rec) -> dict:
    res = rec.get("result")
    out = {"n": rec.get("n"), "engine_s": round(rec["t1"] - rec["t0"], 3) if "t1" in rec else None}
    if res is not None:
        out.update(CS._induction(res) or {})
        out["near_solve"] = CS._near_solve(res.near_solve)
    return out


def _fold_result_summary(r) -> dict | None:
    if r is None:
        return None
    return {"accepted": bool(getattr(r, "accepted", False)),
            "failure_stage": getattr(getattr(r, "failure_stage", None), "value", None),
            "train_fit_pixels": round(float(getattr(r, "train_fit_pixels", 0.0) or 0.0), 4),
            "hypotheses": int(getattr(r, "hypotheses_enumerated", 0) or 0),
            "time_s": round(float(getattr(r, "induction_time_s", 0.0) or 0.0), 3),
            "program": CS.prog_summary(r.program) if getattr(r, "program", None) is not None else None}


def summarize_trace(T) -> dict:
    """The decision chain of one engine run, from the v1.9 trace."""
    inductions = [_induction_summary(r) for r in T["induce_program"]]
    loo = []
    for rec in T["loo"]:
        folds = []
        for f in rec["folds"]:
            folds.append({"hold": f.get("hold"), "n_sub": f.get("n_sub"),
                          "engine_s": round(f["t1"] - f["t0"], 3) if "t1" in f else None,
                          "exception": f.get("exception"), "result": _fold_result_summary(f.get("result"))})
        rep = rec.get("report")
        loo.append({"k": rec["k"], "phase": rec["phase"], "n": rec["n"], "ctx": repr(rec["ctx"]),
                    "engine_s": round(rec["t1"] - rec["t0"], 3) if "t1" in rec else None,
                    "report": None if rep is None else {"folds": rep.folds, "passed": rep.passed,
                                                        "failed": list(rep.failed_pair_indices)},
                    "folds": folds})
    pools = []
    for c in T["composed"]:
        if c["ctx"] == ("TOP",):
            pools.append({"n": c["n"], "stage": c["stage"], "size": len(c["programs"]),
                          "engine_s": round(c["t1"] - c["t0"], 3),
                          "top": [CS.prog_summary(p) for p in c["programs"][:TOP_PROGRAMS]]})
    return {"inductions": inductions, "inner_loo": loo, "top_pools": pools,
            "clock_patched_modules": len(T.get("clock_patched") or [])}


def engine_run(task_id, train, tests, engine_dir, ext=None, budget_s=None, clock="WALL"):
    """One traced object-layer run (budget: measure.BUDGET_S, read at call
    time). Returns (record, accepted program JSON or None)."""
    import geocat_arc.object_reasoning.engine as E
    from harness.object_layer import run_object_task
    from cora_v19 import v19_trace as TR
    if clock not in CLOCKS:
        raise ValueError(clock)
    budget_s = M.BUDGET_S if budget_s is None else budget_s
    HT = M._hard_timeout()
    cap = (budget_s + M.CAP_SLACK_S + M.FRAMES_ALLOWANCE_S) if clock == "WALL" else CPU_WALL_CAP_S
    out = {"version": VERSION, "installed": ext["name"] if ext is not None else None, "clock": clock,
           "budget_s": budget_s, "cap_s": cap, "accepted": False, "program_sha": None,
           "predictions": [None] * len(tests), "timeout": False, "error": None, "load_start": _load()}
    seen = []
    orig = E.ObjectReasoningEngine.solve

    def solve(self, tid, pairs):
        r = orig(self, tid, pairs)
        seen.append(r)
        return r
    program = None
    out["caches_cleared"] = M.clear_engine_caches()
    t0, c0 = time.time(), time.process_time()
    E.ObjectReasoningEngine.solve = solve
    try:
        with contextlib.ExitStack() as stack:
            subs = None
            if ext is not None:
                stack.enter_context(BR.installed(ext))
                subs = stack.enter_context(substitution_spy(ext["name"]))
            hits = stack.enter_context(deadline_spy())
            T = stack.enter_context(TR.traced(clock))
            try:
                with M.hard_cap(cap):
                    res = run_object_task(task_id, M.as_task(train, tests), None, out_dir=engine_dir,
                                          budget_s=budget_s)
            except HT:
                res = {"solved": False, "error": "hard_timeout"}
                out["timeout"] = True
            out["wall_s"] = round(time.time() - t0, 3)
            out["cpu_s"] = round(time.process_time() - c0, 3)
            sol = seen[-1].solution if seen else None
            accepted = bool(res.get("solved")) and sol is not None
            program = sol.program_json if accepted else None
            out.update(accepted=accepted, program_sha=M.psha(program), error=res.get("error"),
                       failure_stage=res.get("failure_stage"), best_accuracy=res.get("best_accuracy"),
                       program=CS.prog_summary(program) if program else None)
            if accepted:
                preds = res.get("predictions") or []
                out["predictions"] = [M._grid(preds[i]) if i < len(preds) else None for i in range(len(tests))]
            if ext is not None:
                out["uses"] = bool(accepted and BR.uses(program, ext))
            out["trace"] = summarize_trace(T)
            out["deadline_hits"] = dict(hits)
            out["substitutions"] = dict(subs) if subs is not None else None
    finally:
        E.ObjectReasoningEngine.solve = orig
    if ext is not None:
        out["restored"] = BR.restored()
    out["cpu_share"] = round(out["cpu_s"] / out["wall_s"], 3) if out.get("wall_s") else None
    out["frames_run"] = max(0, len((out.get("trace") or {}).get("inductions", [])) - 1)
    out["load_end"] = _load()
    return out, program


def extract_run(train, obj_dir, clock="WALL"):
    """The identity-frame extraction (cora_reach.instances.extract, budget
    90 s) under the clock condition. Returns (instances, record)."""
    from cora_v19 import v19_trace as TR
    HT = M._hard_timeout()
    cap = M.EXTRACT_CAP_S if clock == "WALL" else CPU_WALL_CAP_S
    rec = {"clock": clock, "cap_s": cap, "timeout": False, "load_start": _load()}
    inst = []
    M.clear_engine_caches()
    t0, c0 = time.time(), time.process_time()
    hits = collections.Counter()
    try:
        with deadline_spy() as hits, TR._clock(clock):
            with M.hard_cap(cap):
                ind, inst = INST.extract(train, obj_dir, budget_s=M.BUDGET_S)
        rec["induction"] = CS._induction(ind)
    except HT:
        rec["timeout"] = True
    rec["deadline_hits"] = dict(hits)
    rec.update(wall_s=round(time.time() - t0, 3), cpu_s=round(time.process_time() - c0, 3),
               instances=len(inst), with_grid=sum(1 for i in inst if i.get("grid") is not None),
               demos=sorted({i["demo"] for i in inst if i.get("demo") is not None}))
    return inst, rec


def variant_analysis(raw, full_ext=None, max_settings=8) -> dict:
    """Per segmentation variant: the usable instances (one-colour additions
    with a scene), their demonstrations, the settings reproducing all of
    them (the first max_settings in grammar order), and how many of them the
    full-data extension reproduces."""
    groups = CN._instances(raw)
    out = {}
    for v, insts in sorted(groups.items()):
        insts = insts[:CN.MAX_INSTANCES]
        demos = sorted({d for *_x, d in insts if d is not None})
        fits = []
        for fam, params in REL.settings(CN.GRAMMAR):
            if all(REL.apply(fam, params, O, G) == A for O, A, G, _d in insts):
                fits.append({"name": GE.make(fam, params)["name"], "family": fam, "params": params})
                if len(fits) >= max_settings:
                    break
        out[v] = {"instances": len(insts), "demos": demos, "support_ok": len(demos) >= CN.SUPPORT_DEMOS,
                  "settings_reproducing_all": fits,
                  "full_ext_reproduces": None if full_ext is None else
                  sum(1 for O, A, G, _d in insts if GE.render(full_ext, O, G) == A)}
    return {"raw": len(raw), "usable": sum(len(v) for v in groups.values()), "variants": out}


def heldout_check(full_raw, held, candidates) -> list:
    """For each candidate extension (with its variant): whether it reproduces
    the held-out demonstration's own memorized instances in that variant
    (reach v1's full-data instances; demonstrations only)."""
    groups = CN._instances([i for i in full_raw if i.get("demo") == held])
    out = []
    for c in candidates:
        insts = groups.get(str(c["variant"]), []) if c.get("variant") is not None else \
            [x for v in groups.values() for x in v]
        ok = sum(1 for O, A, G, _d in insts if GE.render(c["ext"], O, G) == A)
        out.append({"name": c["ext"]["name"], "family": c["ext"]["family"], "params": c["ext"]["params"],
                    "variant": c.get("variant"), "heldout_instances": len(insts), "reproduces": ok})
    return out
