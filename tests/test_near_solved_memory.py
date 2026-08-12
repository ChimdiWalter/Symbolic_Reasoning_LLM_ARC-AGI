"""Tests for near-solution boundary memory."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
import pytest

from reasoning_project.near_solved_memory import (
    NearSolvedMemory,
    NearSolvedStatus,
    NearSolvedTaskState,
    RepairAction,
    build_near_solved_state,
)
from reasoning_project.manifold_memory import ManifoldPoint, MemoryManifold


def _make_point(emb=None, sig=None):
    if emb is None:
        emb = np.random.default_rng(42).random(16)
    if sig is None:
        sig = {"n_objects": 3, "has_separators": False}
    return ManifoldPoint(embedding=emb, task_signature=sig, domain="grid")


def _make_state(
    task_id="test_task",
    train_fit=0.75,
    failure_type="no_discrimination",
    n_repairs=2,
) -> NearSolvedTaskState:
    repairs = [
        RepairAction("add_conjunction", "try compound predicate", priority=0.9)
        for _ in range(n_repairs)
    ]
    return NearSolvedTaskState(
        task_id=task_id,
        manifold_point=_make_point(),
        active_chart="filter_chart",
        best_hypothesis={"strategy": "discriminative_filter", "property": "is_largest"},
        hypothesis_score=train_fit,
        train_fit=train_fit,
        train_fit_detail=[True, True, True, False],
        loo_passed=False,
        failure_type=failure_type,
        failed_examples=[3],
        error_signature={"failure_type": failure_type},
        retrieved_success_anchors=[],
        retrieved_failure_anchors=[],
        proposed_repairs=repairs,
        missing_capability_guess="richer_property_language",
        views_tried=["color_cc", "per_color"],
        iterations_used=2,
    )


class TestNearSolvedTaskState:
    def test_is_near_solved_true(self):
        state = _make_state(train_fit=0.75, n_repairs=2)
        assert state.is_near_solved is True

    def test_is_near_solved_false_low_fit(self):
        state = _make_state(train_fit=0.2, n_repairs=2)
        assert state.is_near_solved is False

    def test_is_near_solved_false_no_repairs(self):
        state = _make_state(train_fit=0.75, n_repairs=0)
        assert state.is_near_solved is False

    def test_repair_distance(self):
        state = _make_state(n_repairs=3)
        assert state.repair_distance == 3
        state.proposed_repairs[0].tried = True
        assert state.repair_distance == 2

    def test_best_untried_repair(self):
        state = _make_state(n_repairs=2)
        r = state.best_untried_repair()
        assert r is not None
        assert r.action_type == "add_conjunction"

    def test_best_untried_repair_all_tried(self):
        state = _make_state(n_repairs=1)
        state.proposed_repairs[0].tried = True
        assert state.best_untried_repair() is None

    def test_to_dict(self):
        state = _make_state()
        d = state.to_dict()
        assert d["task_id"] == "test_task"
        assert d["train_fit"] == 0.75
        assert d["failure_type"] == "no_discrimination"
        assert isinstance(d["repair_distance"], int)


class TestNearSolvedMemory:
    def test_store_and_retrieve(self):
        mem = NearSolvedMemory()
        state = _make_state(task_id="task_1")
        mem.store_partial(state)
        assert "task_1" in mem.states

    def test_store_sets_near_solved_status(self):
        mem = NearSolvedMemory()
        state = _make_state(train_fit=0.75, n_repairs=2)
        mem.store_partial(state)
        assert state.status == NearSolvedStatus.NEAR_SOLVED

    def test_resume_from_state(self):
        mem = NearSolvedMemory()
        state = _make_state(task_id="task_1")
        mem.store_partial(state)
        resumed = mem.resume_from_state("task_1")
        assert resumed is not None
        assert resumed.task_id == "task_1"

    def test_resume_nonexistent(self):
        mem = NearSolvedMemory()
        assert mem.resume_from_state("nonexistent") is None

    def test_promote_to_solved(self):
        mem = NearSolvedMemory()
        state = _make_state(task_id="task_1")
        mem.store_partial(state)
        result = mem.promote_to_solved("task_1", {"strategy": "solved_strategy"})
        assert result is True
        assert mem.states["task_1"].status == NearSolvedStatus.SOLVED
        assert mem.states["task_1"].train_fit == 1.0

    def test_promote_nonexistent(self):
        mem = NearSolvedMemory()
        assert mem.promote_to_solved("nonexistent", {}) is False

    def test_retrieve_similar_partial(self):
        mem = NearSolvedMemory()
        for i in range(5):
            rng = np.random.default_rng(i)
            state = _make_state(task_id=f"task_{i}")
            state.manifold_point = _make_point(emb=rng.random(16))
            mem.store_partial(state)

        sig = {"n_objects": 3, "has_separators": False}
        similar = mem.retrieve_similar_partial(sig, k=3)
        assert len(similar) == 3

    def test_detect_missing_charts(self):
        mem = NearSolvedMemory()
        for i in range(5):
            state = _make_state(task_id=f"task_{i}")
            state.failure_type = "no_discrimination"
            state.missing_capability_guess = "richer_property_language"
            mem.store_partial(state)

        missing = mem.detect_missing_charts(min_cluster_size=3)
        assert len(missing) >= 1
        assert missing[0]["n_tasks"] == 5
        assert missing[0]["missing_capability"] == "richer_property_language"

    def test_detect_no_missing_charts_small_cluster(self):
        mem = NearSolvedMemory()
        state = _make_state(task_id="task_1")
        mem.store_partial(state)
        missing = mem.detect_missing_charts(min_cluster_size=3)
        assert len(missing) == 0

    def test_summary(self):
        mem = NearSolvedMemory()
        mem.store_partial(_make_state(task_id="t1", train_fit=0.8, n_repairs=2))
        mem.store_partial(_make_state(task_id="t2", train_fit=0.2, n_repairs=1))
        mem.promote_to_solved("t1", {"strategy": "solved"})
        s = mem.summary
        assert s[NearSolvedStatus.SOLVED] == 1
        assert s[NearSolvedStatus.PARTIAL] == 1

    def test_store_with_manifold(self):
        manifold = MemoryManifold()
        mem = NearSolvedMemory(manifold=manifold)
        state = _make_state(task_id="task_1")
        mem.store_partial(state)
        assert len(manifold.all_points) == 1

    def test_promote_with_manifold(self):
        manifold = MemoryManifold()
        mem = NearSolvedMemory(manifold=manifold)
        state = _make_state(task_id="task_1")
        mem.store_partial(state)
        mem.promote_to_solved("task_1", {"strategy": "solved"})
        assert len(manifold.all_points) == 2
        solved_pts = [p for p in manifold.all_points if p.metadata.get("solved")]
        assert len(solved_pts) == 1


class TestBuildNearSolvedState:
    def test_build_from_mock_loop_result(self):
        @dataclass
        class MockDiag:
            failure_type: str = "no_discrimination"
            detail: str = ""
            failing_pairs: List[int] = field(default_factory=list)

        @dataclass
        class MockResult:
            solved: bool = False
            predictions: Optional[list] = None
            hypothesis: Optional[Dict[str, Any]] = None
            iterations_used: int = 4
            views_tried: List[str] = field(default_factory=lambda: ["color_cc", "per_color"])
            diagnosis_trace: List[Any] = field(default_factory=lambda: [MockDiag()])
            manifold_chart: Optional[str] = "filter_chart"

        inp = np.zeros((5, 5), dtype=int)
        inp[1:3, 1:3] = 1
        out = np.zeros((5, 5), dtype=int)
        out[1:3, 1:3] = 2
        train_pairs = [(inp, out)]

        result = MockResult()
        state = build_near_solved_state("test_task", train_pairs, result)

        assert state.task_id == "test_task"
        assert state.failure_type == "no_discrimination"
        assert state.iterations_used == 4
        assert state.active_chart == "filter_chart"
        assert len(state.proposed_repairs) > 0
        assert state.missing_capability_guess != ""
        assert state.topology_signature is not None

    def test_build_with_no_diagnosis(self):
        @dataclass
        class MockResult:
            solved: bool = False
            predictions: Optional[list] = None
            hypothesis: Optional[Dict[str, Any]] = None
            iterations_used: int = 1
            views_tried: List[str] = field(default_factory=list)
            diagnosis_trace: List[Any] = field(default_factory=list)
            manifold_chart: Optional[str] = None

        train_pairs = [(np.zeros((3, 3), dtype=int), np.ones((3, 3), dtype=int))]
        state = build_near_solved_state("task_x", train_pairs, MockResult())
        assert state.failure_type == "unknown"
