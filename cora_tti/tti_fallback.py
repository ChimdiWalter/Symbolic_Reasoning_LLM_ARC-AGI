"""TTI fallback for the REAL engine (directive item 1, base+TTI arm).

On a task the full certified engine fails, install EPHEMERAL task-local
concepts through the engine's own certified injection path and re-enter the
full learner:

    run_one_task under K_global  -> failed
    -> write a task-local concept file
    -> re-run run_one_task with ARC_META_INDUCTION=1 + ARC_TTI_CONCEPTS=<file>
       (the hook sits inside _induce_composed, so every leave-one-out fold
        re-derives any concept-guided candidate; ranking and acceptance are
        the engine's own, unchanged)
    -> record evidence; the concept file is deleted and the env restored in a
       finally block, so nothing persists to the next task (reset rule).

V1 PROPOSAL FAMILY -- honesty box: the ephemeral concepts below are GENERIC
constructor compositions over the engine's frozen meta-vocabulary
(Partition / Select / Map(Key, Lookup) / Paint with typed slots), including
composition shapes the engine's fixed meta-search never enumerates (the
double-Select refinement). They are not learned from the failure, and they
are not semantic inventions: this arm exists to make the S_base+TTI
measurement REAL end to end. The Stage-B constructive proposer replaces
`v1_schema_family()` with failure-conditioned construction; nothing else in
this file changes when it does.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "src")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from cora_tti.full_engine_solver import (CHAIN_FLAGS, FullEngineSolver,   # noqa: E402
                                         _ensure_flags, _normalize)


# --------------------------------------------------------------------------
# v1 ephemeral schema family (generic constructor compositions, typed slots)
# --------------------------------------------------------------------------

def v1_schema_family() -> list:
    """ConceptRecord dicts for the ephemeral file. Slots: ?0 PartitionExpr,
    ?1/?3 Predicate, ?2 FeatureExpr (enumerable); ?4 the induced table."""
    from geocat_arc.object_reasoning import meta_ast as M
    from geocat_arc.object_reasoning.concept_registry import ConceptRecord

    def compose(*stages):
        return M.Compose(*stages)

    full = compose(M.Partition("?0"), M.Select("?1"),
                   M.Map(M.Key("?2"), ("Lookup", ("?4",))), M.Paint())
    refined = compose(M.Partition("?0"), M.Select("?1"), M.Select("?3"),
                      M.Map(M.Key("?2"), ("Lookup", ("?4",))), M.Paint())
    records = []
    for name, schema in (("tti_generic_full", full),
                         ("tti_generic_refined", refined)):
        records.append(ConceptRecord(
            name=name, schema=schema,
            concept_class="tti_v1_generic_constructor_composition",
            status="provisional",
            provenance=("tti-ephemeral",)).to_dict())
    return records


# --------------------------------------------------------------------------
# the fallback
# --------------------------------------------------------------------------

class _ephemeral_concepts:
    """Write the concept file + set env for ONE task; always restored."""

    def __init__(self, records: Sequence[Mapping[str, Any]],
                 meta_budget_s: float):
        self.records = list(records)
        self.meta_budget_s = meta_budget_s

    def __enter__(self):
        handle = tempfile.NamedTemporaryFile(
            "w", suffix=".tti_concepts.json", delete=False)
        json.dump(self.records, handle)
        handle.close()
        self.path = handle.name
        self.saved = {k: os.environ.get(k) for k in
                      ("ARC_META_INDUCTION", "ARC_TTI_CONCEPTS",
                       "ARC_META_BUDGET_S")}
        os.environ["ARC_META_INDUCTION"] = "1"
        os.environ["ARC_TTI_CONCEPTS"] = self.path
        os.environ["ARC_META_BUDGET_S"] = str(self.meta_budget_s)
        return self

    def __exit__(self, *exc):
        for key, value in self.saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        try:
            os.unlink(self.path)
        except OSError:
            pass
        return False


class TTIEngineSolver(FullEngineSolver):
    """FullEngineSolver + ephemeral-concept fallback on failure.

    Evidence per activation: base failed (that IS the ablation leg for the
    ephemeral concept: without it the identical engine found nothing),
    whether the TTI pass gate-accepted, and whether its winning strategy is
    the meta layer's (computed_pattern), i.e. the concepts were in the
    winning path rather than incidental.
    """

    def __init__(self, per_layer_timeout: float = 8.0,
                 meta_budget_s: float = 8.0,
                 schema_family=None):
        super().__init__(per_layer_timeout)
        self.meta_budget_s = meta_budget_s
        self.schema_family = schema_family or v1_schema_family
        self.tti_records: list = []

    def __call__(self, train, test_inputs, budget_s: float) -> list:
        t0 = time.time()
        base_attempts = super().__call__(train, test_inputs, budget_s * 0.55)
        base_record = self.records[-1]
        if base_record["solved"]:
            self.tti_records.append({"route": "ordinary",
                                     "activated": False})
            return base_attempts
        #  invention route: ephemeral concepts through the engine's own path
        remaining = max(20.0, budget_s - (time.time() - t0))
        with _ephemeral_concepts(self.schema_family(), self.meta_budget_s):
            tti_attempts = super().__call__(train, test_inputs, remaining)
        tti_record = self.records[-1]
        strategy = None
        used_meta = False
        if tti_record["solved"]:
            #  layer detail: the object layer's strategy names computed_pattern
            #  when the meta path produced the winner
            strategy = tti_record.get("layer")
        row = {"route": "invention", "activated": True,
               "tti_gate_accepted": bool(tti_record["solved"]),
               "base_gate_accepted": False,
               "solving_layer": strategy,
               "wall_s": round(time.time() - t0, 3)}
        self.tti_records.append(row)
        if tti_record["solved"]:
            return tti_attempts
        #  neither arm solved: keep base attempt-2 material if TTI produced none
        merged = []
        for base_row, tti_row in zip(base_attempts, tti_attempts):
            first = tti_row[0] if tti_row[0] is not None else base_row[0]
            second = tti_row[1] if tti_row[1] is not None else base_row[1]
            if first is not None and second == first:
                second = base_row[1]
            merged.append([first, second])
        return merged

    def tti_summary(self) -> dict:
        n = len(self.tti_records)
        activations = [r for r in self.tti_records if r.get("activated")]
        return {
            "tasks": n,
            "invention_activations": len(activations),
            "tti_gate_accepted": sum(bool(r.get("tti_gate_accepted"))
                                     for r in activations),
        }
