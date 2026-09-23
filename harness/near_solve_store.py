"""Near-solve store — JSONL-backed record of best partial progress on every
UNSOLVED task.  This is the seed of the cumulative-learning memory:
failures are training data.

File: ``outputs/unified_harness_v1/near_solves.jsonl`` (one JSON object per
line, append-only; written by the single orchestrator process so no locking
is needed).

EXACTLY WHAT IS RECORDED per unsolved task
------------------------------------------
    {
      "task_id":                  ARC task id,
      "best_layer":               provenance layer of the best partial
                                  candidate ("geocat" | "identity"),
      "best_family_or_strategy":  strategy name of that candidate
                                  (e.g. "grid:gravity", "geocat_best_accuracy_unattributed",
                                  "identity"),
      "best_train_pixel_acc":     mean pixel accuracy across all train pairs
                                  (0.0 for shape-mismatched predictions),
      "per_pair_acc":             list of per-train-pair pixel accuracies,
                                  or null when no callable candidate exists
                                  (see fallback chain, case 2),
      "timestamp_from_run_config": the run_id / ISO timestamp of the harness
                                  run configuration that produced the row,
      "source":                   which fallback-chain case fired (below),
      "pipeline_error", "geocat_error": exception reprs if a layer crashed
                                  (null otherwise).
    }

PROVENANCE / FALLBACK CHAIN (why GeoCat, not the pipeline)
----------------------------------------------------------
The cortical pipeline (``evaluate_arc_unified``) exposes NO partial-
candidate information on failure — it returns only aggregate counters and
the solved list; its internal UnifiedTrace and candidate pool are not
returned (audited in pipeline_layer.py).  GeoCat runs on every task anyway
(~0.1 s) and its ReasoningResult DOES expose partials, so the chain is:

  1. source="geocat_near_solve": GeoCat returned near_solves (partial
     grid-solver candidates with a stored apply_fn).  We take the one with
     the highest train accuracy and recompute per-pair pixel accuracy.
  2. source="geocat_best_accuracy_unattributed": no stored candidate fn,
     but the engine's best_accuracy (best train pixel accuracy over
     everything it tried, e.g. a partial structural-inference fit whose fn
     is not retained) beats identity.  per_pair_acc is null because no
     callable survives to recompute it.
  3. source="identity_fallback": otherwise record the identity transform's
     accuracy (0.0 per pair whenever output shape != input shape).  This is
     the honest floor: "no system got anywhere on this task."
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Set

import numpy as np


def identity_per_pair_accuracy(task: Dict[str, Any]) -> List[float]:
    """Pixel accuracy of the identity transform on each train pair."""
    accs: List[float] = []
    for p in task["train"]:
        inp = np.array(p["input"], dtype=np.int32)
        out = np.array(p["output"], dtype=np.int32)
        if inp.shape != out.shape:
            accs.append(0.0)
        else:
            accs.append(float((inp == out).mean()))
    return accs


def build_near_solve_record(
    task_id: str,
    task: Dict[str, Any],
    geocat_out: Dict[str, Any],
    run_timestamp: str,
    pipeline_error: Optional[str] = None,
) -> Dict[str, Any]:
    """Build the near-solve row for an unsolved task (fallback chain above)."""
    identity_acc = identity_per_pair_accuracy(task)
    identity_mean = float(np.mean(identity_acc)) if identity_acc else 0.0

    ns = geocat_out.get("near_solve")
    best_acc = float(geocat_out.get("best_accuracy") or 0.0)

    if ns is not None and ns["train_pixel_acc"] >= max(best_acc, identity_mean):
        source = "geocat_near_solve"
        best_layer = "geocat"
        best_family = ns["strategy"]
        best_train_acc = ns["train_pixel_acc"]
        per_pair = ns["per_pair_acc"]
    elif best_acc > identity_mean:
        source = "geocat_best_accuracy_unattributed"
        best_layer = "geocat"
        best_family = "geocat_best_accuracy_unattributed"
        best_train_acc = best_acc
        per_pair = None  # engine keeps no callable for this partial
    else:
        source = "identity_fallback"
        best_layer = "identity"
        best_family = "identity"
        best_train_acc = identity_mean
        per_pair = identity_acc

    return {
        "task_id": task_id,
        "best_layer": best_layer,
        "best_family_or_strategy": best_family,
        "best_train_pixel_acc": round(float(best_train_acc), 6),
        "per_pair_acc": ([round(float(a), 6) for a in per_pair]
                         if per_pair is not None else None),
        "timestamp_from_run_config": run_timestamp,
        "source": source,
        "pipeline_error": pipeline_error,
        "geocat_error": geocat_out.get("error"),
    }


class NearSolveStore:
    """Append-only JSONL store; single-writer (the orchestrator process)."""

    def __init__(self, path: str):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)

    def existing_task_ids(self) -> Set[str]:
        ids: Set[str] = set()
        if os.path.exists(self.path):
            with open(self.path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        ids.add(json.loads(line)["task_id"])
                    except Exception:  # noqa: BLE001 — tolerate a torn last line
                        continue
        return ids

    def append(self, record: Dict[str, Any]) -> None:
        with open(self.path, "a") as f:
            f.write(json.dumps(record) + "\n")
            f.flush()
