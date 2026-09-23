"""Object layer — per-task wrapper around the Stage-1 ObjectReasoningEngine.

Mounted as the THIRD harness layer (pipeline -> geocat -> object).  Like the
GeoCat layer it runs on EVERY task so overlap with the other layers is
measurable.  A fresh ``ObjectReasoningEngine`` is built per task: ``solve()``
reads no accumulated cross-task state in this configuration (the fragment
library starts empty and ``promote_and_validate()`` is never called inside
the harness), so per-task engines are behaviorally identical to one
sequential engine — matching the semantics of the standalone dev runner
``scripts/run_object_dev_eval.py``.

"solved" means exactly what the engine's acceptance gate means: the induced
ObjectProgram is train-perfect AND LOO-by-reinduction-perfect
(``result.solution.is_exact``).  When ground truth is provided we
ADDITIONALLY score the solution on the test pairs offline (``test_correct``)
AFTER solve has returned — test outputs never reach the engine (hard
constraint 6.3).

Artifacts: the engine persists programs/<task_id>.json and
certificates/<task_id>.json under ``out_dir`` (shared across workers; the
per-task filenames make concurrent writes safe).  Engine-native
NearSolveRecords go to per-task files under near_solve_parts/ so 20 spawned
workers never interleave a shared JSONL.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import numpy as np

#: Cooperative induction budget (s).  Kept below the harness hard cap (105 s,
#: run_harness.OBJECT_HARD_CAP_S) so the engine can return best-so-far
#: gracefully; the SIGALRM cap only guards non-cooperative hangs.
#: Raised 50 -> 90 after round 3: the wider tier search solves relational
#: tasks (e.g. 8ee62060) at ~63 s, past the old budget.
DEFAULT_OBJECT_BUDGET_S = 90.0


def _to_grid(g: Any) -> np.ndarray:
    return np.array(g, dtype=np.int32)


def run_object_task(
    task_id: str,
    task: Dict[str, Any],
    solution: Optional[List[Any]] = None,
    out_dir: Optional[str] = None,
    budget_s: Optional[float] = None,
) -> Dict[str, Any]:
    """Run the object engine on one raw challenges-JSON task entry.

    Returns a dict:
        solved          : bool — accepted program (train-exact + LOO-exact)
        strategy        : "object_program" when solved
        train_accuracy, loo_score, loo_folds : from the accepted solution
        test_correct    : bool | None — offline test score (None if unsolved
                          or no ground truth given)
        certificate     : full ProgramCertificate dict (None when the solve
                          carries no certificate, e.g. single-train-pair)
        parameter_class : certificate parameter_class shortcut (or None)
        seg_variant     : segmentation variant used/last explored
        failure_stage   : inducer failure stage when unsolved
        best_accuracy   : train_fit_pixels of the best attempt (1.0 if solved)
        near_solve      : object-level partial for unsolved tasks:
                          {program_partial: dict|None, train_fit_pixels,
                           train_fit_objects, failure_stage} or None
        elapsed_s, error
    """
    import harness  # noqa: F401  (sys.path bootstrap)
    from geocat_arc.object_reasoning.engine import ObjectReasoningEngine
    from geocat_arc.object_reasoning.inducer import InductionConfig
    from geocat_arc.object_reasoning.memory import NearSolveStore

    out: Dict[str, Any] = {
        "solved": False,
        "strategy": None,
        "train_accuracy": None,
        "loo_score": None,
        "loo_folds": None,
        "test_correct": None,
        "certificate": None,
        "parameter_class": None,
        "seg_variant": None,
        "failure_stage": None,
        "best_accuracy": 0.0,
        "near_solve": None,
        "elapsed_s": None,
        "error": None,
    }
    t0 = time.time()
    try:
        train_pairs = [
            (_to_grid(p["input"]), _to_grid(p["output"])) for p in task["train"]
        ]
        engine_dir = out_dir or "outputs/object_reasoning_dev/harness_layer"
        cfg = InductionConfig(budget_s=float(budget_s or DEFAULT_OBJECT_BUDGET_S))
        # PAPER E2 gate-off ablation ONLY (env-gated so no real config can
        # set it silently); results from such runs are quarantined by the
        # OBJECT_GATE_OFF stamp in the run config.
        import os as _os
        if _os.environ.get("OBJECT_GATE_OFF") == "1":
            cfg.accept_train_perfect = True
        engine = ObjectReasoningEngine(engine_dir, use_library=True, config=cfg)
        # Per-task near-solve part file: safe under concurrent workers.
        engine.near_solve_store = NearSolveStore(
            engine.output_dir / "near_solve_parts" / f"{task_id}.jsonl")

        result = engine.solve(task_id, train_pairs)

        ind = result.induction
        if ind is not None:
            out["best_accuracy"] = float(ind.train_fit_pixels)
            out["failure_stage"] = (ind.failure_stage.value
                                    if ind.failure_stage else None)
            if ind.program is not None:
                # reduction programs (round 10) don't segment -> "none"
                sv = ind.program.segmentation_variant
                out["seg_variant"] = sv.value if sv is not None else "none"
            elif ind.segmentation is not None:
                out["seg_variant"] = ind.segmentation.variant.value

        if result.solution and result.solution.is_exact:
            sol = result.solution
            out["solved"] = True
            out["strategy"] = sol.strategy
            out["train_accuracy"] = float(sol.train_accuracy)
            out["loo_score"] = float(sol.loo_score)
            out["loo_folds"] = (ind.loo.folds if (ind and ind.loo) else None)
            out["best_accuracy"] = 1.0
            out["failure_stage"] = None
            if result.certificate is not None:
                out["certificate"] = result.certificate.to_dict()
                out["parameter_class"] = result.certificate.parameter_class
            # predictions rendered from the train-only solution
            preds = []
            for pair in task["test"]:
                try:
                    preds.append(np.array(sol.apply_fn(_to_grid(pair["input"])),
                                          dtype=np.int32).tolist())
                except Exception:  # noqa: BLE001
                    preds.append(None)
            out["predictions"] = preds
            # Offline test scoring — first (and only) place test data appears.
            if solution is not None:
                ok = True
                for pred_l, gt in zip(preds, solution):
                    gt_arr = _to_grid(gt)
                    if pred_l is None:
                        ok = False
                        break
                    pred = np.array(pred_l, dtype=np.int32)
                    if pred.shape != gt_arr.shape or not np.array_equal(pred, gt_arr):
                        ok = False
                        break
                out["test_correct"] = ok
        elif result.near_solves:
            rec = result.near_solves[0]
            out["near_solve"] = {
                "program_partial": rec.program_partial,
                "train_fit_pixels": float(rec.train_fit_pixels),
                "train_fit_objects": float(rec.train_fit_objects),
                "failure_stage": rec.failure_stage,
            }
            # attempt_2 material: render the best UNCERTIFIED partial on the
            # test inputs (measured 0.91 precision for feature/relational
            # classes at loo stage; E2/RUN_HISTORY 2026-07-11)
            try:
                from geocat_arc.object_reasoning.types import ObjectProgram
                from geocat_arc.object_reasoning.actions import program_apply_fn
                pp = rec.program_partial
                if isinstance(pp, dict) and pp.get("rules"):
                    prog = ObjectProgram.from_dict(pp)
                    fn = program_apply_fn(prog)
                    p2 = []
                    for pair in task["test"]:
                        try:
                            p2.append(np.array(fn(_to_grid(pair["input"])),
                                               dtype=np.int32).tolist())
                        except Exception:  # noqa: BLE001
                            p2.append(None)
                    out["partial_predictions"] = p2
                    out["partial_parameter_class"] = \
                        prog.worst_parameter_class.value
                    out["partial_failure_stage"] = rec.failure_stage
            except Exception:  # noqa: BLE001
                pass
    except Exception as exc:  # noqa: BLE001
        out["error"] = repr(exc)
    out["elapsed_s"] = round(time.time() - t0, 3)
    return out


def object_near_solve_row(
    task_id: str,
    object_out: Dict[str, Any],
    run_timestamp: str,
    pipeline_error: Optional[str] = None,
    geocat_error: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Build a unified-harness near-solve row from the object layer's partial.

    Used by run_harness when the object layer holds a REAL partial program
    and the geocat-based fallback chain bottomed out at identity — a typed
    partial ObjectProgram is strictly more informative training data than an
    identity-accuracy floor.  Schema matches near_solve_store rows, plus
    object_* extras carrying the inspectable partial program.
    """
    ns = object_out.get("near_solve")
    if not ns or not ns.get("program_partial"):
        return None
    return {
        "task_id": task_id,
        "best_layer": "object",
        "best_family_or_strategy": f"object_partial:{ns.get('failure_stage')}",
        "best_train_pixel_acc": round(float(ns.get("train_fit_pixels") or 0.0), 6),
        "per_pair_acc": None,
        "timestamp_from_run_config": run_timestamp,
        "source": "object_near_solve",
        "pipeline_error": pipeline_error,
        "geocat_error": geocat_error,
        "object_failure_stage": ns.get("failure_stage"),
        "object_train_fit_objects": round(float(ns.get("train_fit_objects") or 0.0), 6),
        "object_program_partial": ns.get("program_partial"),
    }
