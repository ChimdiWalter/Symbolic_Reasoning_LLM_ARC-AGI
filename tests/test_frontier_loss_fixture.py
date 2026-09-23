"""Smallest fixture reproducing the failure-frontier information loss.

Synthetic tasks only. No ARC data, no scoring, no hidden outputs. The
fixture pins the measured defect so a repair has a falsifiable target:

    the instrumented search judges thousands of candidates, every one of
    them fails slot fitting, so no near miss is ever created; the frontier
    that reaches the Typed Failure Graph is therefore a constant of the
    language rather than evidence about the task.
"""
import sys
import time

sys.path.insert(0, "/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_tti")

import numpy as np                                               # noqa: E402
from level4_blind_runtime import env as E                        # noqa: E402
from level4_blind_runtime import stepA_trace_search as TS        # noqa: E402
from cora_tti import tfg_extractor as X                          # noqa: E402

#  two ordinary, structurally unrelated transformations that the
#  11-primitive blind runtime cannot express
TILE = [(np.array([[1, 0], [0, 2]]), np.tile(np.array([[1, 0], [0, 2]]), (2, 2))),
        (np.array([[3, 3], [0, 1]]), np.tile(np.array([[3, 3], [0, 1]]), (2, 2)))]
TRANSPOSE = [(np.array([[1, 2], [3, 4]]), np.array([[1, 3], [2, 4]])),
             (np.array([[5, 6], [7, 8]]), np.array([[5, 7], [6, 8]]))]


def _trace(pairs, budget_s=4.0):
    observer = TS.TraceObserver()
    TS.set_observer(observer)
    try:
        results, stats = TS.search(pairs, deadline=time.monotonic() + budget_s,
                                   env=E.BASE_ENV)
    finally:
        TS.set_observer(None)
    census = {}
    for _, outcome in observer.candidates:
        census[outcome] = census.get(outcome, 0) + 1
    return results, stats, observer, census


def test_search_judges_many_candidates_but_fits_none():
    results, _, _, census = _trace(TILE)
    assert not results, "fixture must be a failure case"
    assert census.get("typed", 0) > 100, census
    assert census.get("slot_fit_ok", 0) == 0, census
    assert census.get("executed_not_exact", 0) == 0, census
    assert census.get("slot_fit_failed", 0) == census["typed"], census


def test_candidate_trace_is_identical_for_unrelated_tasks():
    """The information loss, stated as an equality.

    Two tasks that differ in shape behaviour, palette and structure produce
    the same candidate census and the same frontier ASTs, so the candidate
    channel carries nothing that identifies the task.
    """
    _, _, obs_a, census_a = _trace(TILE)
    _, _, obs_b, census_b = _trace(TRANSPOSE)
    assert census_a == census_b, (census_a, census_b)
    asts_a = [X._canonical_ast(a) for a, o in obs_a.candidates
              if o in X.FRONTIER_OUTCOMES]
    asts_b = [X._canonical_ast(a) for a, o in obs_b.candidates
              if o in X.FRONTIER_OUTCOMES]
    assert asts_a == asts_b


def test_frontier_exists_but_carries_no_value_evidence():
    _, stats, observer, _ = _trace(TILE)
    tfg = X.build_tfg(TILE, stats, observer, E.BASE_ENV, "Grid",
                      X.MAX_FRONTIER_TERMS)
    frontier = [n for n in tfg.nodes() if n.kind == "frontier_term"]
    assert frontier, "frontier nodes are emitted"
    assert {n.attrs["outcome"] for n in frontier} == {"slot_fit_failed"}
    assert [n for n in tfg.nodes() if n.kind == "value_signature"] == []


def test_every_frontier_term_shares_one_operator():
    _, stats, observer, _ = _trace(TILE)
    tfg = X.build_tfg(TILE, stats, observer, E.BASE_ENV, "Grid",
                      X.MAX_FRONTIER_TERMS)
    ops = {n.attrs["op"] for n in tfg.nodes() if n.kind == "frontier_term"}
    assert len(ops) == 1, ops


def test_only_one_primitive_can_return_the_goal_type():
    env = E.BASE_ENV
    grid_returning = [n for n in sorted(env.names)
                      if str(env.result_type(n)) == "Grid"]
    assert len(grid_returning) == 1, grid_returning
