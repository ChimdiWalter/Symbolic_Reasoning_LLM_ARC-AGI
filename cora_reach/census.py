"""Native failure census (development protocol v1, section 2).

One task through the sealed native entry (the five chain flags, the frozen
library, solution None) under the v1.9 observation-only tracer. Returns a
compact record, plus the native programs needed to design a mechanism. No
target exists here; nothing is scored.
"""
from __future__ import annotations

import hashlib
import json
import os
import time

OBJECT_BUDGET_S = 90.0          # harness/object_layer.DEFAULT_OBJECT_BUDGET_S
SEARCH_LIMIT_SHARE = 0.95


def _sha(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:12]


def skeleton(d):
    """The program with every numeric literal masked: two programs with the
    same skeleton differ only in fitted values."""
    def walk(v):
        if isinstance(v, bool) or v is None:
            return v
        if isinstance(v, int):
            return "#"
        if isinstance(v, float):
            return "#f"
        if isinstance(v, dict):
            return {k: walk(x) for k, x in sorted(v.items())}
        if isinstance(v, (list, tuple)):
            return [walk(x) for x in v]
        return v
    return walk(d)


def _as_dict(p):
    if p is None:
        return None
    if isinstance(p, dict):
        return p
    try:
        return p.to_dict()
    except Exception:                                           # noqa: BLE001
        return {"unserializable": type(p).__name__}


def _ops(v, out):
    if isinstance(v, dict):
        if isinstance(v.get("op"), str):
            out.add(v["op"])
        for x in v.values():
            _ops(x, out)
    elif isinstance(v, (list, tuple)):
        for x in v:
            _ops(x, out)
    return out


def prog_summary(p) -> dict | None:
    d = _as_dict(p)
    if d is None:
        return None
    rules = d.get("rules")
    obj = p
    if isinstance(p, dict):
        try:
            from geocat_arc.object_reasoning.types import program_from_dict
            obj = program_from_dict(json.loads(json.dumps(p)))
        except Exception:                                       # noqa: BLE001
            obj = None
    wpc = getattr(obj, "worst_parameter_class", None) if obj is not None else None
    if callable(wpc):
        try:
            wpc = wpc()
        except Exception:                                       # noqa: BLE001
            wpc = None
    actions_ops = sorted(_ops([r.get("action") for r in rules], set())) if isinstance(rules, list) else None
    selector_ops = sorted(_ops([r.get("selector") for r in rules], set())) if isinstance(rules, list) else None
    return {"class": d.get("program_class", "object"), "param_ops": actions_ops, "selector_ops": selector_ops,
            "rules": len(rules) if isinstance(rules, list) else None,
            "actions": [((r.get("action") or {}).get("delta_type")) for r in rules]
            if isinstance(rules, list) else None,
            "worst_class": getattr(wpc, "value", None),
            "skeleton": _sha(skeleton(d)), "sha": _sha(d)}


def _induction(ind) -> dict | None:
    if ind is None:
        return None
    loo = ind.loo
    return {"accepted": bool(ind.accepted),
            "failure_stage": getattr(ind.failure_stage, "value", None),
            "train_fit_objects": round(float(ind.train_fit_objects), 4),
            "train_fit_pixels": round(float(ind.train_fit_pixels), 4),
            "hypotheses": int(ind.hypotheses_enumerated), "time_s": round(float(ind.induction_time_s), 2),
            "program": prog_summary(ind.program),
            "loo": None if loo is None else {
                "folds": loo.folds, "passed": loo.passed, "failed": list(loo.failed_pair_indices),
                "divergence": [{"fold": dv.get("fold"), "fold_program": prog_summary(dv.get("fold_program")),
                                "cells_wrong": dv.get("cells_wrong"), "shape_mismatch": dv.get("shape_mismatch")}
                               for dv in loo.divergence]},
            "events": sorted(set(ind.events))[:40]}


def _near_solve(ns) -> dict | None:
    if ns is None:
        return None
    rules = ns.explained_rules or []
    res = ns.residual or {}
    return {"train_fit_pixels": round(float(ns.train_fit_pixels), 4),
            "train_fit_objects": round(float(ns.train_fit_objects), 4),
            "failure_stage": ns.failure_stage, "segmentation": ns.segmentation_variant,
            "explained_rules": len(rules),
            "explained_actions": [r.get("action") for r in rules],
            "objects_explained": [r.get("n_objects_explained") for r in rules],
            "unexplained": [{"delta_type": u.get("delta_type"), "count": u.get("count")}
                            for u in (res.get("unexplained_deltas") or [])],
            "conflicts": res.get("conflict_report"), "loo_failures": res.get("loo_failures"),
            "delta_histogram": ns.delta_histogram, "partial": prog_summary(ns.program_partial)}


def reference_program(ind):
    """The demonstration-exact program whose leave-one-out is reported: the
    accepted program when there is one; when leave-one-out failed the engine
    leaves it only in the near-solve partial."""
    if ind is None:
        return None
    if ind.program is not None:
        return _as_dict(ind.program)
    ns = ind.near_solve
    return ns.program_partial if ns is not None else None


def divergence_class(ind) -> str | None:
    """PARAM: every failed fold re-derives the full program's skeleton with
    other values. STRUCT: some failed fold derives another skeleton. NOFOLD:
    some failed fold derives nothing. None: no leave-one-out report. A
    rejected induction may keep no program; its demonstration-exact program
    is then the near-solve's partial."""
    loo = ind.loo if ind is not None else None
    if loo is None or not loo.divergence:
        return None
    full = reference_program(ind)
    if full is None and ind.near_solve is not None and float(ind.near_solve.train_fit_pixels) >= 1.0:
        full = ind.near_solve.program_partial
    sk = _sha(skeleton(full)) if full is not None else None
    out = "PARAM"
    for dv in loo.divergence:
        fp = dv.get("fold_program")
        if fp is None:
            return "NOFOLD"
        if sk is None or _sha(skeleton(_as_dict(fp))) != sk:
            out = "STRUCT"
    return out


def diagnose(obj_accepted, ind) -> dict:
    """Protocol section 3, first rule that applies."""
    if obj_accepted:
        return {"class": "NATIVE_CERTIFIED"}
    if ind is None:
        return {"class": "NO_INDUCTION"}
    fs = getattr(ind.failure_stage, "value", None)
    if fs in ("segmentation", "matching"):
        return {"class": "A_REPRESENTATION", "stage": fs}
    if fs == "loo":
        return {"class": "DE_LOO", "sub": divergence_class(ind) or "UNKNOWN"}
    if fs in ("selector", "parameter"):
        used = float(ind.induction_time_s) / OBJECT_BUDGET_S
        return {"class": "C_SEARCH" if used >= SEARCH_LIMIT_SHARE else "B_LANGUAGE", "stage": fs,
                "budget_used": round(used, 3)}
    return {"class": "UNCLASSIFIED", "stage": fs}


def _trace(T) -> dict:
    top_pools = [c for c in T["composed"] if c["ctx"] == ("TOP",)]
    pools = [len(c["programs"]) for c in top_pools]
    best = top_pools[0]["programs"][:3] if top_pools else []
    loo_top = [r for r in T["loo"] if r["ctx"] == ("TOP",)]
    return {"inductions": len(T["induce_program"]),
            "loo_calls": len(T["loo"]), "loo_top": len(loo_top),
            "composed_calls": len(T["composed"]), "top_pool_sizes": pools[:12],
            "top_candidates": [prog_summary(p) for p in best],
            "expression_trigger": [t["fired"] for t in T["trigger"]][:4]}


def run_census(key: str, task: dict, out_dir: str, programs_dir: str) -> dict:
    from harness.run_harness import run_one_task
    from cora_pilot import native as N
    from cora_v19 import v19_trace as TR
    import geocat_arc.object_reasoning.engine as E
    obj = N.prepare_object_dir(out_dir)
    config = {"run_id": "reach-v1-census", "timeout_per_task": 60.0, "per_layer_timeout": 8.0,
              "submission_mode": True, "emit_predictions": True, "object_out_dir": obj}
    seen = []
    orig = E.ObjectReasoningEngine.solve

    def solve(self, task_id, pairs):
        r = orig(self, task_id, pairs)
        seen.append(r)
        return r
    t0 = time.time()
    E.ObjectReasoningEngine.solve = solve
    try:
        with TR.traced("WALL") as T:
            rec = run_one_task((key, {"train": task["train"], "test": task["test"]}, None, config))
            trace = _trace(T)
            first = T["induce_program"][0]["result"] if T["induce_program"] else None
    finally:
        E.ObjectReasoningEngine.solve = orig
    res = seen[-1] if seen else None
    final = res.induction if res is not None else None
    accepted = bool(res is not None and res.solution is not None)
    identity = first if first is not None else final
    preds = rec.get("predictions") or {}
    row = {"key": key, "n_train": len(task["train"]), "n_test": len(task["test"]),
           "seconds": round(time.time() - t0, 2),
           "layers": {
               "pipeline": {k: (rec.get("pipeline") or {}).get(k) for k in ("solved", "layer", "family",
                                                                              "elapsed_s", "error")},
               "geocat": {k: (rec.get("geocat") or {}).get(k) for k in ("solved", "strategy", "best_accuracy",
                                                                          "elapsed_s", "error")},
               "object": {k: (rec.get("object") or {}).get(k) for k in ("solved", "failure_stage",
                                                                          "best_accuracy", "elapsed_s", "error")}},
           "claim": {"attempt_1_source": preds.get("attempt_1_source"),
                     "attempt_2": any(x is not None for x in (preds.get("attempt_2") or []))},
           "object_accepted": accepted,
           "identity_induction": _induction(identity),
           "final_induction": _induction(final) if final is not identity else "same",
           "near_solve": _near_solve(identity.near_solve if identity is not None else None),
           "trace": trace,
           "diagnosis": diagnose(accepted, identity)}
    ns = identity.near_solve if identity is not None else None
    row["usable_trace"] = bool((ns is not None and ns.explained_rules)
                               or (row["diagnosis"]["class"] == "DE_LOO" and reference_program(identity) is not None))
    row["exact_demo_fit"] = bool(identity is not None and float(identity.train_fit_pixels) >= 1.0)
    os.makedirs(programs_dir, exist_ok=True)
    with open(os.path.join(programs_dir, f"{key}.json"), "w") as handle:
        json.dump({"identity_program": _as_dict(identity.program) if identity is not None else None,
                   "near_solve_partial": ns.program_partial if ns is not None else None,
                   "near_solve_rules": ns.explained_rules if ns is not None else None,
                   "near_solve_residual": ns.residual if ns is not None else None,
                   "loo_divergence": [{"fold": dv.get("fold"), "fold_program": _as_dict(dv.get("fold_program")),
                                       "cells_wrong": dv.get("cells_wrong")}
                                      for dv in ((identity.loo.divergence if identity is not None and identity.loo
                                                  else []) or [])]},
                  handle, sort_keys=True, default=str)
    return row
