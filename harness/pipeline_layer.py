"""Pipeline layer — single-task wrapper around ``evaluate_arc_unified``.

SAFETY AUDIT (src/reasoning_project/unified_reasoning_system.py, function
``evaluate_arc_unified`` at line 1587, inspected 2026-07-02):

  * With ``submission_mode=True`` the solver call is
        reason_unified(train_pairs, test_inputs=test_inputs,
                       test_outputs=None, ...)
    i.e. test OUTPUTS never reach any solver code path.  Inside
    ``reason_unified`` every use of test outputs is gated on
    ``test_inputs and test_outputs`` which is False, and the cortical
    fallback block is explicitly gated on ``not (test_inputs and
    test_outputs)``.
  * The ``solutions`` argument is read only in the "Score AFTER" block:
    the already-synthesized program is applied to the test inputs and the
    prediction is compared offline against the ground truth.  The
    LOO-replace block that can rewrite ``ops`` uses train pairs only.

Conclusion: ``evaluate_arc_unified`` uses solutions ONLY for final scoring
in submission mode, so we call it directly with a one-task challenges /
solutions dict.  This reproduces the exact cortical-v6b submission code
path (including LOO-replace and cortical fallbacks) instead of
re-implementing it around ``reason_unified``.

WHAT THE PIPELINE EXPOSES ON FAILURE: nothing usable.  The return value of
``evaluate_arc_unified`` contains only aggregate counters and the solved
list; the internal ``UnifiedTrace`` and the partial-candidate pool are not
returned.  Near-solve information for unsolved tasks is therefore taken
from the GeoCat layer (see ``near_solve_store.py`` for the exact fallback
chain and record schema).
"""
from __future__ import annotations

import time
from typing import Any, Dict, List


def run_pipeline_task(
    task_id: str,
    task: Dict[str, Any],
    solution: List[Any],
    timeout_per_task: float = 60.0,
    per_layer_timeout: float = 8.0,
) -> Dict[str, Any]:
    """Run the unified cortical pipeline on a single ARC task.

    ``task`` is the raw challenges-JSON entry ({"train": [...], "test":
    [...]}), ``solution`` the raw solutions-JSON entry (list of test output
    grids).  The solution is passed through to ``evaluate_arc_unified``
    which uses it only for offline scoring (see module docstring).

    Returns a dict:
        solved  : bool  — submission-valid solve (train-synthesized program
                  reproduced ALL test outputs, scored offline)
        layer   : solving layer name or None
        family  : operator family or None
        iteration : solve iteration or None
        explanation, delta_type : provenance strings when solved
        elapsed_s : wall time
        error   : repr of an exception if the pipeline call raised
        partial : always None — the pipeline exposes no partial-candidate
                  info on failure (documented above)
    """
    import harness  # noqa: F401  (sys.path bootstrap)
    from reasoning_project.unified_reasoning_system import evaluate_arc_unified

    out: Dict[str, Any] = {
        "solved": False,
        "layer": None,
        "family": None,
        "iteration": None,
        "explanation": None,
        "delta_type": None,
        "elapsed_s": None,
        "error": None,
        "partial": None,
    }
    t0 = time.time()
    try:
        res = evaluate_arc_unified(
            {task_id: task},
            {task_id: solution},
            timeout_per_task=timeout_per_task,
            per_layer_timeout=per_layer_timeout,
            submission_mode=True,
        )
        if res.get("total_solved", 0) >= 1 and res.get("solved"):
            rec = res["solved"][0]
            out["solved"] = True
            out["layer"] = rec.get("layer")
            out["family"] = rec.get("family")
            out["iteration"] = rec.get("iteration")
            out["explanation"] = rec.get("explanation")
            out["delta_type"] = rec.get("delta_type")
            out["predictions"] = rec.get("predictions")
    except Exception as exc:  # noqa: BLE001 — harness must never crash on one task
        out["error"] = repr(exc)
    out["elapsed_s"] = round(time.time() - t0, 3)
    return out
