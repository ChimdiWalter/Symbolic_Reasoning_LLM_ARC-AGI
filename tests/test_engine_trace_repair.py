"""Acceptance fixtures for the full-engine observation repair.

A. noninterference: the search result is identical with and without the
   observer installed.
B. task conditioning: unrelated tasks no longer produce identical traces.
C. real near misses: candidates reach beyond typing.
D. executable value evidence: an executed-not-exact candidate renders and
   yields a defined mismatch signature.
E. reset: observer state from one task cannot enter the next.

Measurement only. No proposal, no construction, no install, no scoring, and
no test outputs are read.
"""
import json
import os
import sys

import numpy as np
import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from cora_arc2026 import engine_trace as ET                      # noqa: E402
from geocat_arc.object_reasoning import _trace_hook as HOOK      # noqa: E402

TILE = [([[1, 0], [0, 2]], [[1, 0, 1, 0], [0, 2, 0, 2],
                            [1, 0, 1, 0], [0, 2, 0, 2]]),
        ([[3, 3], [0, 1]], [[3, 3, 3, 3], [0, 1, 0, 1],
                            [3, 3, 3, 3], [0, 1, 0, 1]])]
RECOLOUR = [([[0, 1, 0], [1, 0, 1], [0, 1, 0]],
             [[0, 3, 0], [3, 0, 3], [0, 3, 0]]),
            ([[2, 0, 0], [0, 2, 0], [0, 0, 2]],
             [[3, 0, 0], [0, 3, 0], [0, 0, 3]])]

#  authorized DEV-60 tasks, used only as trace fixtures. The file holds
#  challenges alone, so no answer can be read from it.
DEV = os.path.join(HERE, "data", "arc", "dev60_challenges.json")


def _dev_pairs(task_id):
    with open(DEV) as handle:
        tasks = json.load(handle)
    return [(p["input"], p["output"]) for p in tasks[task_id]["train"]]


def _result_fingerprint(result):
    solution = getattr(result, "solution", None)
    induction = getattr(result, "induction", None)
    program = getattr(solution, "program", None) if solution else None
    return {
        "is_exact": bool(getattr(solution, "is_exact", False)) if solution
                    else False,
        "strategy": getattr(solution, "strategy", None) if solution else None,
        "train_accuracy": (round(float(getattr(solution, "train_accuracy", 0)), 6)
                           if solution else None),
        "loo_score": (round(float(getattr(solution, "loo_score", 0)), 6)
                      if solution else None),
        "best_accuracy": round(float(getattr(result, "best_accuracy", 0)), 6),
        "failure_stage": str(getattr(induction, "failure_stage", None)),
        "train_fit_pixels": (round(float(getattr(induction, "train_fit_pixels", 0)), 6)
                             if induction else None),
        "program": (json.dumps(program.to_dict(), sort_keys=True)
                    if program is not None else None),
        "program_partial": (json.dumps(getattr(induction, "program_partial", None),
                                       sort_keys=True, default=str)
                            if induction else None),
    }


def _solve_plain(task_id, pairs, budget_s=8.0):
    """The ordinary reasoning path with NO observer installed."""
    from geocat_arc.object_reasoning.engine import ObjectReasoningEngine
    from geocat_arc.object_reasoning.inducer import InductionConfig
    assert HOOK.get_sink() is None
    engine = ObjectReasoningEngine(
        os.path.join(HERE, "outputs", "engine_trace"), use_library=True,
        config=InductionConfig(budget_s=float(budget_s)))
    return engine.solve(task_id, [(np.asarray(a), np.asarray(b))
                                  for a, b in pairs])


# -- A. noninterference ----------------------------------------------------

@pytest.mark.parametrize("task_id,pairs", [("fixture_tile", TILE),
                                           ("fixture_recolour", RECOLOUR)])
def test_observation_does_not_change_the_search_result(task_id, pairs):
    plain = _result_fingerprint(_solve_plain(task_id, pairs))
    observed = ET.extract(task_id, pairs, budget_s=8.0)
    assert HOOK.get_sink() is None, "sink must be uninstalled in finally"
    assert _result_fingerprint(observed["result"]) == plain


# -- B. task conditioning --------------------------------------------------

def test_unrelated_tasks_no_longer_produce_identical_traces():
    a = ET.extract("fixture_tile", TILE, budget_s=8.0)
    b = ET.extract("fixture_recolour", RECOLOUR, budget_s=8.0)
    assert a["census"] or b["census"], "at least one task must emit events"
    assert a["census"] != b["census"] or _asts(a) != _asts(b)


def _asts(got):
    from cora_tti import tfg_extractor as X
    return [X._canonical_ast(ast) for ast, _ in got["observer"].candidates]


def test_trace_difference_is_structural_not_incidental():
    """The traces differ in the operators reached, not only in counts."""
    a = ET.extract("dev_a", _dev_pairs("16b78196"), budget_s=8.0)
    b = ET.extract("dev_b", _dev_pairs("221dfab4"), budget_s=8.0)
    ops_a = {n.attrs["op"] for n in a["tfg"].nodes()
             if n.kind == "frontier_term"}
    ops_b = {n.attrs["op"] for n in b["tfg"].nodes()
             if n.kind == "frontier_term"}
    assert ops_a and ops_b
    assert ops_a != ops_b


# -- C. real near misses ---------------------------------------------------

def test_candidates_reach_beyond_typing():
    got = ET.extract("dev_a", _dev_pairs("16b78196"), budget_s=8.0)
    census = got["census"]
    assert census.get("typed", 0) > 0
    beyond = census.get("slot_fit_ok", 0) + census.get("executed_not_exact", 0)
    assert beyond > 0, census


def test_a_near_miss_is_not_accepted():
    got = ET.extract("dev_a", _dev_pairs("16b78196"), budget_s=8.0)
    assert not got["solved"]
    assert got["census"].get("executed_not_exact", 0) > 0, got["census"]


# -- D. executable value evidence ------------------------------------------

def test_executed_not_exact_candidate_yields_a_defined_signature():
    pairs = _dev_pairs("16b78196")
    got = ET.extract("dev_a", pairs, budget_s=8.0)
    evidence = ET.engine_value_evidence(got["observer"], pairs)
    defined = [row for row in evidence if row.get("defined")]
    assert defined, evidence[:3]
    assert any("cells_wrong" in row or "shape_matches" in row
               for row in defined)


# -- E. reset --------------------------------------------------------------

def test_observer_state_cannot_leak_between_tasks():
    first = ET.extract("dev_a", _dev_pairs("16b78196"), budget_s=8.0)
    second = ET.extract("fixture_tile", TILE, budget_s=8.0)
    assert first["observer"] is not second["observer"]
    assert HOOK.get_sink() is None
    ids_first = {id(o) for o in first["observer"].candidates}
    ids_second = {id(o) for o in second["observer"].candidates}
    assert not (ids_first & ids_second)
    assert len(second["observer"].candidates) < len(first["observer"].candidates)


def test_sink_is_uninstalled_even_when_the_engine_raises():
    HOOK.set_sink(None)
    try:
        ET.extract("fixture_bad", [([[0]], [[0, 0]])], budget_s=1.0)
    except Exception:
        pass
    assert HOOK.get_sink() is None
