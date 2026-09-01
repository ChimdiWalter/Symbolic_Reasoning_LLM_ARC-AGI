"""Tests for the anytime scheduler simulator and the two-attempt diversity policy."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cora_tti import anytime as AT                     # noqa: E402
from cora_tti.diversity import (Candidate, complementarity_report,   # noqa: E402
                                pick_attempts, pick_top2)


# --------------------------------------------------------------------------
# anytime scheduler
# --------------------------------------------------------------------------

def heterogeneous_tasks():
    """Many cheap tasks + a few expensive + unsolvable sinks: the regime where
    equal split wastes budget on sinks and starves the mid-cost tasks."""
    tasks = {}
    for i in range(8):
        tasks[f"easy{i}"] = AT.SyntheticTask(need_s=5.0)
    for i in range(4):
        tasks[f"mid{i}"] = AT.SyntheticTask(need_s=45.0)
    for i in range(4):
        tasks[f"sink{i}"] = AT.SyntheticTask(need_s=1e9, solvable=False)
    return tasks


def class_priors(tasks):
    """Difficulty-class priors as the plan permits (public/synthetic statistics
    only — never hidden-task identity; here the class is encoded in the
    synthetic id purely for test construction)."""
    priors = {}
    for tid in tasks:
        if tid.startswith("easy"):
            priors[tid] = (0.9, 5.0)
        elif tid.startswith("mid"):
            priors[tid] = (0.8, 30.0)
        else:
            priors[tid] = (0.05, 300.0)
    return priors


def test_greedy_with_priors_beats_equal_split():
    tasks = heterogeneous_tasks()
    budget = 16 * 20.0                      # equal split gives each task 20s
    equal = AT.simulate("equal", tasks, budget, quantum_s=10.0)
    greedy = AT.simulate("greedy", tasks, budget, quantum_s=10.0,
                         priors=class_priors(tasks))
    #  equal split solves only the easies (20s < 45s and sinks eat 80s)
    assert equal["n_solved"] == 8
    assert greedy["n_solved"] > equal["n_solved"], (equal, greedy)
    assert greedy["within_budget"] and equal["within_budget"]


def test_greedy_is_deterministic():
    tasks = heterogeneous_tasks()
    priors = class_priors(tasks)
    a = AT.simulate("greedy", tasks, 300.0, quantum_s=7.0, priors=priors)
    b = AT.simulate("greedy", tasks, 300.0, quantum_s=7.0, priors=priors)
    assert a == b


def test_priors_move_budget_away_from_sinks():
    tasks = heterogeneous_tasks()
    out = AT.simulate("greedy", tasks, 16 * 20.0, quantum_s=10.0,
                      priors=class_priors(tasks))
    sink_spend = sum(out["per_task_spent"][t] for t in tasks if t.startswith("sink"))
    mid_spend = sum(out["per_task_spent"][t] for t in tasks if t.startswith("mid"))
    assert mid_spend > sink_spend, out["per_task_spent"]


def test_without_priors_sinks_are_indistinguishable_from_hard_tasks():
    """Honest limitation, asserted so it stays visible: with uniform priors a
    quantum failure on a solvable-but-slow task looks exactly like one on an
    unsolvable sink, so the scheduler cannot separate them. The information
    must come from priors or richer failure observations (the TFG), not from
    the allocation mathematics."""
    tasks = heterogeneous_tasks()
    out = AT.simulate("greedy", tasks, 16 * 20.0, quantum_s=10.0)
    sink_spend = sum(out["per_task_spent"][t] for t in tasks if t.startswith("sink"))
    mid_spend = sum(out["per_task_spent"][t] for t in tasks if t.startswith("mid"))
    #  within one quantum of each other per task class member
    assert abs(sink_spend - mid_spend) <= 10.0 * 4 + 1e-9


def test_budget_is_never_exceeded():
    tasks = {f"t{i}": AT.SyntheticTask(need_s=30.0) for i in range(10)}
    out = AT.simulate("greedy", tasks, 47.0, quantum_s=9.0)
    assert out["used_s"] <= 47.0 + 1e-9


def test_scheduler_retires_solved_tasks():
    scheduler = AT.AnytimeScheduler(["a", "b"], total_budget_s=100, quantum_s=5)
    tid, budget = scheduler.next_grant()
    scheduler.report(tid, 5.0, solved=True)
    nxt = scheduler.next_grant()
    assert nxt is not None and nxt[0] != tid
    scheduler.report(nxt[0], 5.0, solved=True)
    assert scheduler.next_grant() is None
    assert scheduler.solved_ids() == ["a", "b"]


def test_emulator_adapter_caps_and_shrinks():
    adapter = AT.EmulatorAdapter(cap_fraction=3.0)
    assert adapter(1200.0, 120) == pytest.approx(30.0)      # 3x the equal 10s
    assert adapter(100.0, 1) == pytest.approx(100.0)        # last task gets rest
    assert adapter(10.0, 100) <= 10.0


# --------------------------------------------------------------------------
# two-attempt diversity
# --------------------------------------------------------------------------

RIGHT = [[1, 2], [3, 4]]
WRONG_A = [[9, 9], [9, 9]]
WRONG_B = [[8, 8], [8, 8]]


def test_diversity_rescues_correlated_top2():
    """Rank 1 and rank 2 are the same wrong grid from one explanation; a
    lower-confidence but DIFFERENT candidate is right: naive top-2 misses,
    the diversity policy scores."""
    pool = [Candidate(WRONG_A, 0.9, "certified"),
            Candidate(WRONG_A, 0.85, "certified"),
            Candidate(RIGHT, 0.4, "invented_production")]
    assert pick_top2(pool) == (WRONG_A, WRONG_A)
    a1, a2 = pick_attempts(pool)
    assert a1 == WRONG_A and a2 == RIGHT


def test_diversity_prefers_other_source_on_ties():
    pool = [Candidate(WRONG_A, 0.9, "certified"),
            Candidate(WRONG_B, 0.8, "certified"),
            Candidate(RIGHT, 0.8, "other_view")]
    a1, a2 = pick_attempts(pool)
    assert a1 == WRONG_A and a2 == RIGHT      # other_view outranks same-source


def test_diversity_falls_back_to_rank2_when_all_agree():
    pool = [Candidate(RIGHT, 0.9, "certified"),
            Candidate(RIGHT, 0.5, "uncertified")]
    a1, a2 = pick_attempts(pool)
    assert a1 == RIGHT and a2 == RIGHT


def test_empty_and_none_pools():
    assert pick_attempts([]) == (None, None)
    assert pick_attempts([Candidate(None, 0.9)]) == (None, None)


def test_complementarity_report_scores_policies():
    pools = {
        "o1": [Candidate(WRONG_A, 0.9, "certified"),
               Candidate(WRONG_A, 0.8, "certified"),
               Candidate(RIGHT, 0.3, "invented_production")],
        "o2": [Candidate(RIGHT, 0.95, "certified"),
               Candidate(WRONG_A, 0.4, "uncertified")],
        "o3": [Candidate(WRONG_B, 0.7, "certified")],
    }
    solutions = {"o1": RIGHT, "o2": RIGHT, "o3": RIGHT}
    report = complementarity_report(pools, solutions)
    assert report["n_outputs"] == 3
    assert report["attempt1_only"] == pytest.approx(1 / 3)
    assert report["naive_top2"] == pytest.approx(1 / 3)
    assert report["diversity_policy"] == pytest.approx(2 / 3)
    assert report["rescued_by_diversity"] == ["o1"]
    assert report["lost_by_diversity"] == []
    assert report["second_attempt_win_source_pairs"] == {
        "certified->invented_production": 1}
