"""The budgeted CORA search (Neural-CORA v1). Reads demonstrations and test inputs only.

`search_typed` is shared by C+, C+H, L0 and L1:
- enumerate hypotheses best-first under the arm's component scores;
- execute each on every demonstration with the fixed native interpreter, stopping at the first demonstration that
  disagrees;
- keep every demonstration-consistent hypothesis;
- record its test prediction.

**Two-attempt selection, the same fixed rule for every arm:** attempt 1 is the prediction of the first consistent
hypothesis in the arm's order. Attempt 2 is the next distinct prediction.

The whole budget is always spent, so "candidate coverage" (distinct consistent predictions within budget) is
measured too. A demonstration-consistent program is a candidate, not a verified answer. Correctness is decided later
by the separate evaluator.

`search_native` is C0: native CORA's own inducer (`induce_program`) under a CPU-time budget (the `cora_funnel` CPU
clock). Its single attempt is the accepted program's render.
"""
import time

import numpy as np

from cora_neural_v1 import interp as I
from cora_neural_v1 import space as SP

MAX_KEPT = 50                     # distinct consistent predictions kept per task (coverage is counted up to here)


def search_typed(task, scores, budget):
    train = task["train"]
    test_in = task["test_inputs"][0]
    doms = SP.domains(train)
    c0, e0 = time.process_time(), I.STATS["executions"]
    preds, first_at, n_consistent, kept = [], {}, 0, []
    n = 0
    for h, s in SP.enumerate_programs(doms, scores, budget):
        n += 1
        ok, _ = I.fit(h, train)
        if not ok:
            continue
        n_consistent += 1
        p = I.run(h, test_in)
        if p is None:
            continue
        key = p.tobytes() + bytes(p.shape)
        if key not in first_at:
            first_at[key] = n
            if len(preds) < MAX_KEPT:
                preds.append(p.tolist())
                kept.append({"at": n, "program": h.to_dict(), "score": round(float(s), 4)})
    return {"attempts": preds[:2], "predictions": preds, "first_consistent_at": kept[0]["at"] if kept else None,
            "second_distinct_at": kept[1]["at"] if len(kept) > 1 else None, "n_candidates": n,
            "n_consistent": n_consistent, "n_distinct_predictions": len(first_at), "kept": kept[:5],
            "executions": I.STATS["executions"] - e0, "cpu_s": round(time.process_time() - c0, 3),
            "domain_size": {"selectors": len(doms["selectors"]), "actions": len(doms["actions"])}}


def search_native(task, budget_s):
    """C0: native induce_program on the demonstrations, with native's deadlines on process CPU time."""
    from cora_funnel import run as FR                               # noqa: F401 (sealed native flags)
    patched = FR.cpu_clock()
    from geocat_arc.object_reasoning.actions import render_program
    from geocat_arc.object_reasoning.inducer import InductionConfig, induce_program
    from geocat_arc.object_reasoning.types import to_grid_pairs
    from geocat_arc.perception.grid import Grid
    c0 = time.process_time()
    res = induce_program(to_grid_pairs(task["train"]), InductionConfig(budget_s=float(budget_s)))
    att = []
    if res.accepted and res.program is not None:
        try:
            out = render_program(res.program, Grid(np.asarray(task["test_inputs"][0], dtype=np.int32))).to_numpy()
            att = [np.asarray(out, dtype=np.int64).tolist()]
        except Exception:                                           # noqa: BLE001
            att = []
    return {"attempts": att, "accepted": bool(res.accepted), "cpu_s": round(time.process_time() - c0, 3),
            "failure_stage": getattr(getattr(res, "failure_stage", None), "value", None), "clock_patched": len(patched)}
