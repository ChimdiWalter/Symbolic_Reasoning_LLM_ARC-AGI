"""GeoCat layer — per-task wrapper around ``geocat_arc``'s ReasoningEngine.

A fresh ``ReasoningEngine`` is built per task: ``solve()`` never reads the
engine's accumulated state (``solved_insights`` / ``near_solve_memory`` are
write-only inside ``solve``), so per-task engines are behaviorally identical
to the single sequential engine used to produce
``outputs/failure_landscape_2026_07_02.json``.

"solved" here means what it meant in the failure landscape: the engine
returned a Solution with ``is_exact=True`` (train-exact + LOO-validated,
induced from train pairs only).  When test data is provided we ADDITIONALLY
score the solution on the test pairs offline (``test_correct``) — the test
outputs never reach the engine, which only ever sees train pairs.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import numpy as np


def _to_grid(g: Any) -> np.ndarray:
    return np.array(g, dtype=np.int32)


def fn_per_pair_accuracy(fn, train_pairs) -> List[float]:
    """Pixel accuracy of ``fn`` on each train pair (0.0 on shape mismatch/error)."""
    accs: List[float] = []
    for inp, out in train_pairs:
        try:
            pred = np.array(fn(inp), dtype=np.int32)
            if pred.shape != out.shape:
                accs.append(0.0)
            else:
                accs.append(float((pred == out).mean()))
        except Exception:  # noqa: BLE001
            accs.append(0.0)
    return accs


def run_geocat_task(
    task_id: str,
    task: Dict[str, Any],
    solution: Optional[List[Any]] = None,
) -> Dict[str, Any]:
    """Run GeoCat on one raw challenges-JSON task entry.

    Returns a dict:
        solved         : bool — exact train-verified solution (is_exact)
        strategy       : result.solution.strategy when exact
        train_accuracy, loo_score : floats from the Solution when exact
        test_correct   : bool | None — offline test score (None if no
                         solution or no ground truth given)
        best_accuracy  : engine's best train pixel accuracy over everything
                         it tried (0.0..1.0)
        near_solve     : best partial candidate for unsolved tasks:
                         {strategy, train_pixel_acc, per_pair_acc} or None.
                         Taken from result.near_solves (grid-solver partials
                         with stored apply_fn); per-pair accuracy recomputed
                         on the train pairs.
        strategies_tried_n, elapsed_s, error
    """
    import harness  # noqa: F401  (sys.path bootstrap)
    from geocat_arc.reasoning.reasoning_engine import ReasoningEngine

    out: Dict[str, Any] = {
        "solved": False,
        "strategy": None,
        "train_accuracy": None,
        "loo_score": None,
        "apply_fn_qualname": None,
        "test_correct": None,
        "best_accuracy": 0.0,
        "near_solve": None,
        "strategies_tried_n": 0,
        "elapsed_s": None,
        "error": None,
    }
    t0 = time.time()
    try:
        train_pairs = [
            (_to_grid(p["input"]), _to_grid(p["output"])) for p in task["train"]
        ]
        result = ReasoningEngine().solve(task_id, train_pairs)
        out["strategies_tried_n"] = len(result.strategies_tried)
        out["best_accuracy"] = float(result.best_accuracy)

        if result.solution and result.solution.is_exact:
            sol = result.solution
            out["solved"] = True
            out["strategy"] = sol.strategy
            out["train_accuracy"] = float(sol.train_accuracy)
            out["loo_score"] = float(sol.loo_score)
            # Provenance for origin_classes: "inferred_structural" is a mixed
            # strategy; the defining function in the qualname tells whether the
            # transform was induced (color mapping learned from train) or a
            # hardcoded primitive (flip/rot/tile/crop/...).
            out["apply_fn_qualname"] = getattr(sol.apply_fn, "__qualname__", None)
            # predictions rendered from train-only solution (emit-predictions)
            preds = []
            for pair in task["test"]:
                try:
                    preds.append(np.array(sol.apply_fn(_to_grid(pair["input"])),
                                          dtype=np.int32).tolist())
                except Exception:  # noqa: BLE001
                    preds.append(None)
            out["predictions"] = preds
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
        else:
            # Best partial candidate with a stored apply_fn (grid-solver partials)
            if result.near_solves:
                best = max(result.near_solves, key=lambda n: n.train_accuracy)
                out["near_solve"] = {
                    "strategy": best.strategy,
                    "train_pixel_acc": float(best.train_accuracy),
                    "per_pair_acc": fn_per_pair_accuracy(best.apply_fn, train_pairs),
                }
    except Exception as exc:  # noqa: BLE001
        out["error"] = repr(exc)
    out["elapsed_s"] = round(time.time() - t0, 3)
    return out
