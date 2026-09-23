"""Thin full-engine extraction entry point for the delivery sprint.

Installs the existing TraceObserver on the real ARC reasoning engine, runs
the ordinary reasoning path, uninstalls the observer in a finally block and
calls the existing ``tfg_extractor.build_tfg``. Nothing is proposed,
constructed, installed, extended or scored here.

Only demonstration pairs are used. Test inputs, test outputs and solutions
are never passed in, so no hidden answer can enter the trace.
"""
from __future__ import annotations

import os
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TTI = "/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_tti"
#  the sprint's own engine copy must win over the research tree, which is on
#  the path only for the shared TFG code
for _p in (TTI, HERE):
    if _p in sys.path:
        sys.path.remove(_p)
    sys.path.insert(0, _p)

from level4_blind_runtime import env as E                        # noqa: E402
from level4_blind_runtime import stepA_trace_search as TS        # noqa: E402
from cora_tti import tfg_extractor as X                          # noqa: E402

from geocat_arc.object_reasoning import _trace_hook as HOOK      # noqa: E402

import geocat_arc as _geocat                                     # noqa: E402
if not os.path.abspath(_geocat.__file__).startswith(HERE + os.sep):
    raise ImportError(
        "the sprint must use its own allowlisted engine copy, not "
        + os.path.abspath(_geocat.__file__))

#: real-engine transitions each existing outcome name is emitted at.
#: Documented in records/ENGINE_EVENT_MAPPING.md. No name is redefined.
EVENT_MAPPING = {
    "typed": "a delta group is formed and enters rule induction",
    "slot_fit_failed": "_induce_action_for_group returned None "
                       "(FailureStage.PARAMETER)",
    "slot_fit_ok": "selector and action both induced; ObjectRule complete",
    "executed_not_exact": "assembled program rendered on every train pair "
                          "and is not train-perfect",
    "exact": "assembled program rendered on every train pair and is "
             "train-perfect",
}
#: real-engine transitions with NO truthful counterpart in the existing
#: vocabulary. Deliberately not emitted rather than silently relabelled.
UNMAPPED = {
    "typecheck_failed": "the object grammar constructs only well-typed "
                        "rules, so no program-level typecheck rejection "
                        "exists to observe",
    "selector_failed": "_induce_selector_for returned None; a real engine "
                       "state that no existing outcome name describes",
}


def _stats_from(census, seconds):
    stats = TS.SearchStats()
    stats.typed = census.get("typed", 0)
    stats.generated = sum(census.values())
    stats.rejected = (census.get("slot_fit_failed", 0)
                      + census.get("executed_not_exact", 0))
    stats.max_depth = 0
    stats.semantic_classes = census.get("exact", 0)
    stats.seconds = seconds
    return stats


def trace_full_engine(task_id, train_pairs, budget_s=8.0, out_dir=None):
    """Run the real engine once with the observer installed.

    ``train_pairs`` is a list of (input, output) demonstration grids. Returns
    the observer, the engine result and the elapsed seconds. The sink is
    always uninstalled, whatever happens.
    """
    import numpy as np
    from geocat_arc.object_reasoning.engine import ObjectReasoningEngine
    from geocat_arc.object_reasoning.inducer import InductionConfig

    #  solve() takes ARRAY pairs and converts internally
    pairs = [(np.asarray(a), np.asarray(b)) for a, b in train_pairs]
    engine_dir = out_dir or os.path.join(HERE, "outputs", "engine_trace")
    config = InductionConfig(budget_s=float(budget_s))
    engine = ObjectReasoningEngine(engine_dir, use_library=True,
                                   config=config)
    observer = TS.TraceObserver()
    HOOK.set_sink(observer.candidate)
    started = time.monotonic()
    try:
        result = engine.solve(task_id, pairs)
    finally:
        HOOK.set_sink(None)
    return observer, result, time.monotonic() - started


def extract(task_id, train_pairs, budget_s=8.0, goal_type="Grid",
            max_frontier_terms=None, out_dir=None):
    """Full-engine analogue of tfg_extractor.extract.

    Returns {"solved", "tfg", "census", "seconds", "observer", "result"}.
    build_tfg is called unchanged.
    """
    import numpy as np

    observer, result, seconds = trace_full_engine(
        task_id, train_pairs, budget_s=budget_s, out_dir=out_dir)
    census = {}
    for _, outcome in observer.candidates:
        census[outcome] = census.get(outcome, 0) + 1

    solved = bool(getattr(getattr(result, "solution", None), "is_exact",
                          False))
    pairs = [(np.asarray(a), np.asarray(b)) for a, b in train_pairs]
    cap = (X.MAX_FRONTIER_TERMS if max_frontier_terms is None
           else max_frontier_terms)
    tfg = X.build_tfg(pairs, _stats_from(census, seconds), observer,
                      E.BASE_ENV, goal_type, cap)
    return {"solved": solved, "tfg": tfg, "census": census,
            "seconds": seconds, "observer": observer, "result": result}


def engine_value_evidence(observer, train_pairs, limit=12):
    """Mismatch evidence for executed-not-exact candidates, rendered by the
    engine's own executor.

    ``build_tfg`` cannot compute this: its ``_mismatch_signature`` evaluates
    through the blind-runtime evaluator, which does not execute object
    programs. Measured here so the audit can report whether the evidence
    exists at the producer, without altering the consumer.
    """
    import numpy as np
    from geocat_arc.object_reasoning.actions import render_program
    from geocat_arc.object_reasoning.types import ObjectProgram
    from geocat_arc.perception.grid import Grid

    pairs = [(Grid.from_list(a) if not hasattr(a, "height") else a,
              Grid.from_list(b) if not hasattr(b, "height") else b)
             for a, b in train_pairs]
    out = []
    seen = set()
    for ast, outcome in observer.candidates:
        if outcome != "executed_not_exact" or len(out) >= limit:
            continue
        key = X._canonical_ast(ast)
        if key in seen:
            continue
        seen.add(key)
        try:
            program = ObjectProgram.from_dict(ast[1][0])
        except Exception as exc:  # noqa: BLE001
            out.append({"defined": False, "reason": f"from_dict: {exc!r}"})
            continue
        row = {"defined": False}
        for grid_in, grid_out in pairs:
            try:
                rendered = render_program(program, grid_in).to_numpy()
            except Exception as exc:  # noqa: BLE001
                row = {"defined": False, "reason": repr(exc)}
                break
            target = grid_out.to_numpy()
            if rendered.shape != target.shape:
                row = {"defined": True, "shape_matches": False,
                       "rendered_cells": int(rendered.size),
                       "target_cells": int(target.size)}
                break
            wrong = int(np.count_nonzero(rendered != target))
            row = {"defined": True, "shape_matches": True,
                   "cells_wrong": wrong,
                   "fraction_wrong": round(wrong / target.size, 4),
                   "palette_extra": len(set(np.unique(rendered).tolist())
                                        - set(np.unique(target).tolist()))}
            break
        out.append(row)
    return out
