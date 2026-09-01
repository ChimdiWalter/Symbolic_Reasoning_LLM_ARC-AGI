"""The REAL certified engine as an emulator solver (directive item 1, step 1).

Adapts ``harness.run_harness.run_one_task`` — the exact per-task entry that
produced the artifact-backed 185/1000 corpus (pipeline + geocat + object
layers, hard-capped, LOO-certified acceptance) — to the Kaggle emulator's
``solve(train, test_inputs, budget_s)`` contract. This gives the anchor
measurement S_base on the frozen DEV split; the TTI fallback then attaches
BEHIND this solver (failure -> TFG -> proposals -> re-entry), never replacing
it, and the certified learner remains the only acceptance authority.

Facts inherited from the engine, not chosen here:

  - with solutions=None the layers run in true submission mode (no offline
    scoring); record["solved"] means GATE-ACCEPTED (certified), not
    test-verified;
  - attempt 1 is the solving layer's render; attempt-2 material is the object
    layer's best uncertified partial (the measured +14 policy);
  - hard caps use SIGALRM, so this solver must run in the MAIN thread (the
    emulator does);
  - the v23 chain flags must be set or the engine runs below its sealed
    capability.

Nothing here persists between tasks: the engine's stacks are re-entered per
call and no registry is mutated.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "src")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

#: the sealed v23 capability flags (RUN_HISTORY: chain flags at the 185 seal)
CHAIN_FLAGS = {
    "ARC_DIHEDRAL_FRAMES": "45",
    "ARC_GENERATIVE": "1",
    "ARC_PATTERN_DERIVE": "1",
    "ARC_VARIANT_BUDGET": "1",
    "ARC_RAY_EXT": "1",
}


def _ensure_flags() -> None:
    for key, value in CHAIN_FLAGS.items():
        os.environ.setdefault(key, value)


def _normalize(preds, n_tests: int) -> list:
    """Layer predictions arrive as a list per test input (or None)."""
    out = [None] * n_tests
    if isinstance(preds, list):
        for i in range(min(n_tests, len(preds))):
            p = preds[i]
            out[i] = p if isinstance(p, list) else None
    return out


class FullEngineSolver:
    """Callable matching the emulator's Solver contract, plus per-task records
    kept in memory for the measurement report (never used for tuning)."""

    def __init__(self, per_layer_timeout: float = 8.0):
        self.per_layer_timeout = per_layer_timeout
        self.records: list = []
        _ensure_flags()
        from harness.run_harness import _set_worker_env
        _set_worker_env()               # BLAS pinning + SIGALRM handler (main thread)

    def __call__(self, train: Sequence[Mapping[str, Any]],
                 test_inputs: Sequence[Any], budget_s: float) -> list:
        from harness.run_harness import run_one_task
        task = {"train": list(train),
                "test": [{"input": g} for g in test_inputs]}
        #  scale the engine's cooperative + hard caps to the granted budget:
        #  the three layers run sequentially, so each gets a share; hard caps
        #  sit slightly above the cooperative budgets exactly as in the
        #  sealed harness (150/120/105 for a 60 s task)
        coop = max(10.0, min(60.0, budget_s * 0.45))
        config = {
            "run_id": "tti-dev-measurement",
            "timeout_per_task": coop,
            "per_layer_timeout": self.per_layer_timeout,
            "submission_mode": True,
            "emit_predictions": True,
            "pipeline_hard_cap_s": max(20, int(budget_s * 0.40)),
            "geocat_hard_cap_s": max(15, int(budget_s * 0.30)),
            "object_hard_cap_s": max(15, int(budget_s * 0.30)),
        }
        t0 = time.time()
        record = run_one_task((f"anon{len(self.records):03d}", task, None,
                               config))
        record["wall_s"] = round(time.time() - t0, 3)
        preds = record.get("predictions") or {}
        a1 = _normalize(preds.get("attempt_1"), len(test_inputs))
        a2 = _normalize(preds.get("attempt_2"), len(test_inputs))
        self.records.append({
            "solved": record.get("solved"), "origin": record.get("origin"),
            "layer": record.get("layer"), "wall_s": record["wall_s"],
            "errors": {name: (record.get(name) or {}).get("error")
                       for name in ("pipeline", "geocat", "object")},
            "has_a1": any(x is not None for x in a1),
            "has_a2": any(x is not None for x in a2),
        })
        return [[a1[i], a2[i]] for i in range(len(test_inputs))]

    # -- measurement summary (aggregate only; no per-task tuning) ------------
    def summary(self) -> dict:
        n = max(1, len(self.records))
        walls = sorted(r["wall_s"] for r in self.records)
        return {
            "tasks": len(self.records),
            "gate_accepted": sum(bool(r["solved"]) for r in self.records),
            "by_origin": _count(r["origin"] for r in self.records),
            "attempt1_present": sum(r["has_a1"] for r in self.records),
            "attempt2_present": sum(r["has_a2"] for r in self.records),
            "hard_timeouts": sum(
                1 for r in self.records
                if any(e and "timeout" in str(e) for e in r["errors"].values())),
            "mean_wall_s": round(sum(walls) / n, 2),
            "median_wall_s": round(walls[len(walls) // 2], 2) if walls else 0,
            "max_wall_s": walls[-1] if walls else 0,
        }


def _count(items) -> dict:
    out: dict = {}
    for item in items:
        key = str(item)
        out[key] = out.get(key, 0) + 1
    return out
