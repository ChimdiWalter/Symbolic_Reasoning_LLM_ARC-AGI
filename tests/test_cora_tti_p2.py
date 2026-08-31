"""Tests for phase-P2 scaffolding: the Kaggle runtime emulator (gate C0) and the
concrete Typed Failure Graph. Everything here is synthetic — no ARC data file is read.
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cora_parent.tfg import (ConcreteTFG, IdentityLeak, TFGEdge, TFGNode)   # noqa: E402
from cora_tti import kaggle_emulator as KE                                  # noqa: E402


# --------------------------------------------------------------------------
# fixtures: a tiny synthetic "identity" task family the dummy solvers know
# --------------------------------------------------------------------------

def make_tasks(n=4):
    tasks, solutions = {}, {}
    for i in range(n):
        grid = [[i, 0], [0, i + 1]]
        tasks[f"t{i:02d}"] = {"train": [{"input": grid, "output": grid}],
                              "test": [{"input": grid}]}
        solutions[f"t{i:02d}"] = [grid]
    return tasks, solutions


def perfect_solver(train, test_inputs, budget_s):
    return [[g, None] for g in test_inputs]


def second_attempt_solver(train, test_inputs, budget_s):
    return [[[[9]], g] for g in test_inputs]        # attempt 1 wrong, attempt 2 right


def failing_solver(train, test_inputs, budget_s):
    return [[None, None] for _ in test_inputs]


def crashing_solver(train, test_inputs, budget_s):
    raise RuntimeError("boom")


# --------------------------------------------------------------------------
# emulator
# --------------------------------------------------------------------------

def test_scoring_pass_at_2_counts_either_attempt():
    tasks, sols = make_tasks()
    cfg = KE.EmulatorConfig(budget_s=60, forbid_network=False)
    a = KE.run(tasks, perfect_solver, cfg, sols)
    b = KE.run(tasks, second_attempt_solver, cfg, sols)
    c = KE.run(tasks, failing_solver, cfg, sols)
    assert a["score"]["pass_at_2"] == 1.0
    assert b["score"]["pass_at_2"] == 1.0            # attempt 2 counts
    assert c["score"]["pass_at_2"] == 0.0
    assert a["score"]["tasks_fully_correct"] == len(tasks)


def test_exactly_two_attempts_are_kept():
    tasks, sols = make_tasks(1)

    def greedy(train, test_inputs, budget_s):
        return [[g, g, g, g] for g in test_inputs]   # tries to submit 4 attempts

    cfg = KE.EmulatorConfig(budget_s=30, forbid_network=False)
    report = KE.run(tasks, greedy, cfg, sols)
    # normalization truncates to 2; score still computed
    assert report["score"]["pass_at_2"] == 1.0
    assert report["contract"]["attempts"] == 2


def test_solver_crash_forfeits_only_that_task():
    tasks, sols = make_tasks(3)
    calls = {"n": 0}

    def flaky(train, test_inputs, budget_s):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("boom")
        return [[g, None] for g in test_inputs]

    cfg = KE.EmulatorConfig(budget_s=60, forbid_network=False)
    report = KE.run(tasks, flaky, cfg, sols)
    assert report["score"]["tasks_fully_correct"] == 2
    assert any("error" in row for row in report["per_task"])


def test_budget_exhaustion_skips_remaining_tasks():
    tasks, sols = make_tasks(3)

    def slow(train, test_inputs, budget_s):
        import time
        time.sleep(0.3)
        return [[g, None] for g in test_inputs]

    cfg = KE.EmulatorConfig(budget_s=0.35, min_task_budget_s=0.01,
                            forbid_network=False)
    report = KE.run(tasks, slow, cfg, sols)
    skipped = [r for r in report["per_task"] if r.get("skipped_no_budget")]
    assert skipped, "later tasks must be skipped when the global budget is gone"
    assert report["score"]["pass_at_2"] < 1.0


def test_network_guard_blocks_sockets():
    tasks, sols = make_tasks(1)

    def phone_home(train, test_inputs, budget_s):
        urllib.request.urlopen("http://example.com", timeout=1)
        return [[g, None] for g in test_inputs]

    cfg = KE.EmulatorConfig(budget_s=30, forbid_network=True)
    with pytest.raises(KE.NetworkForbidden):
        KE.run(tasks, phone_home, cfg, sols)
    # and the guard is removed afterwards (socket usable again at import level)
    import socket
    socket.socket().close()


def test_predictions_hash_ignores_timing():
    tasks, sols = make_tasks(2)
    cfg = KE.EmulatorConfig(budget_s=30, forbid_network=False)
    r1 = KE.run(tasks, perfect_solver, cfg, sols)
    r2 = KE.run(tasks, perfect_solver, cfg, sols)
    assert r1["predictions_sha256"] == r2["predictions_sha256"]


def test_holdout_requires_gate_and_ledgers(tmp_path):
    tasks, sols = make_tasks(2)
    ledger = tmp_path / "ledger.jsonl"
    with pytest.raises(PermissionError):
        KE.run(tasks, perfect_solver,
               KE.EmulatorConfig(budget_s=30, role="holdout",
                                 forbid_network=False, ledger_file=ledger), sols)
    report = KE.run(tasks, perfect_solver,
                    KE.EmulatorConfig(budget_s=30, role="holdout", gate="C3",
                                      forbid_network=False, ledger_file=ledger), sols)
    lines = [json.loads(l) for l in ledger.read_text().splitlines()]
    assert lines and lines[0]["gate"] == "C3"
    assert report["ledgered"]["pass_at_2"] == 1.0


def test_frozen_split_loads_and_partitions():
    dev = KE.load_split("dev")
    holdout = KE.load_split("holdout")
    assert len(dev) == 60 and len(holdout) == 60
    assert not set(dev) & set(holdout)
    with pytest.raises(ValueError):
        KE.load_split("all")


def test_scheduler_hook_receives_remaining_state():
    tasks, sols = make_tasks(3)
    seen = []

    def schedule(remaining_s, remaining_tasks):
        seen.append((round(remaining_s, 1), remaining_tasks))
        return remaining_s / remaining_tasks

    cfg = KE.EmulatorConfig(budget_s=30, schedule=schedule, forbid_network=False)
    KE.run(tasks, perfect_solver, cfg, sols)
    assert [n for _, n in seen] == [3, 2, 1]


# --------------------------------------------------------------------------
# typed failure graph
# --------------------------------------------------------------------------

def _tiny_tfg():
    nodes = [TFGNode("f1", "frontier_term", "Set[Region]", {"arity": 1}),
             TFGNode("g", "goal", "Grid"),
             TFGNode("d", "delta_signature", "", {"class": "shape_shrink"}),
             TFGNode("s1", "slot", "Colour", {"fit": False})]
    edges = [TFGEdge("f1", "has_type", "g"),
             TFGEdge("f1", "blocks", "d"),
             TFGEdge("s1", "fails", "f1")]
    return ConcreteTFG("Set[Region]", "Grid", nodes, edges)


def test_tfg_roundtrip_and_stable_digest():
    t = _tiny_tfg()
    again = ConcreteTFG.from_json(json.loads(json.dumps(t.to_json())))
    assert again.canonical() == t.canonical()
    assert again.digest() == t.digest()
    assert t.interface() == ("Set[Region]", "Grid")


def test_tfg_canonical_is_order_invariant():
    nodes = [TFGNode("b", "goal", "Grid"), TFGNode("a", "frontier_term", "Grid")]
    edges = [TFGEdge("a", "produces", "b")]
    t1 = ConcreteTFG("Grid", "Grid", nodes, edges)
    t2 = ConcreteTFG("Grid", "Grid", list(reversed(nodes)), edges)
    assert t1.digest() == t2.digest()


def test_tfg_rejects_identity_attrs_and_bad_vocab():
    with pytest.raises(IdentityLeak):
        TFGNode("x", "goal", "Grid", {"task_id": "abc"})
    with pytest.raises(IdentityLeak):
        TFGNode("x", "goal", "Grid", {"Source_Token": "abc"})
    with pytest.raises(ValueError):
        TFGNode("x", "prose_description", "Grid")
    with pytest.raises(ValueError):
        TFGEdge("a", "vibes", "b")
    with pytest.raises(ValueError):
        ConcreteTFG("Grid", "Grid", [TFGNode("a", "goal")],
                    [TFGEdge("a", "produces", "missing")])


def test_tfg_queries():
    t = _tiny_tfg()
    assert [n.node_id for n in t.nodes_of_kind("slot")] == ["s1"]
    assert ("fails", "s1") in t.neighbors("f1")
