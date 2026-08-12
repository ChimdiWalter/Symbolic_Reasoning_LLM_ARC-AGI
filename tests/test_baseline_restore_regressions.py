"""Regression tests for baseline-restore repair pass.

Tests that previously solved tasks remain solved after the verifier fix,
and that no false positives are introduced.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from reasoning_project.adaptive_orchestrator import (
    GatedAdaptiveReasoningOrchestrator,
    OrchestratorConfig,
)
from reasoning_project.proposal_verifier import ProposalVerifier
from reasoning_project.arc_adapter import load_arc_tasks

ARC_ROOT = Path(__file__).parent.parent / "data" / "arc"


def _load_tasks():
    return {t.task_id: t for t in load_arc_tasks(ARC_ROOT)}


def _get_pairs(task):
    tp = [(ex.input_grid, ex.output_grid) for ex in task.train if ex.output_grid is not None]
    ti = [ex.input_grid for ex in task.test]
    to = [ex.output_grid for ex in task.test if ex.output_grid is not None] or None
    return tp, ti, to


def _solve(task_id, config=None):
    tasks = _load_tasks()
    if task_id not in tasks:
        pytest.skip(f"Task {task_id} not in ARC data")
    task = tasks[task_id]
    tp, ti, to = _get_pairs(task)
    config = config or OrchestratorConfig()
    orch = GatedAdaptiveReasoningOrchestrator(config)
    return orch.solve_task(task_id, tp, ti, to)


# --- Static portfolio regressions (previously solved by static_portfolio) ---

@pytest.mark.parametrize("task_id,expected_family", [
    ("08ed6ac7", "transform_induction"),
    ("c8f0f002", "discriminative_change_filter"),
    ("b1948b0a", "discriminative_change_filter"),
    ("ea32f347", "transform_induction"),
    ("e98196ab", "schema"),
])
def test_static_portfolio_regression(task_id, expected_family):
    """Previously solved static_portfolio tasks must remain solved."""
    config = OrchestratorConfig(
        enable_adapter_genesis=False,
        enable_manifold_memory=False,
        enable_near_solved_memory=False,
        enable_operator_memory=False,
        enable_neural_advisory=False,
        enable_domain_morphism=False,
        enable_property_expansion=False,
        enable_frontier_operators=False,
        enable_trace_invention=False,
    )
    trace = _solve(task_id, config)
    assert trace.final_status == "solved", (
        f"{task_id}: expected solved, got {trace.final_status}"
    )
    assert trace.selected_proposal is not None
    assert trace.selected_proposal.module_name == "static_portfolio"
    assert trace.verification is not None
    assert not trace.verification.false_positive


# --- Trace invention regression ---

def test_trace_invention_regression_2a5f8217():
    """2a5f8217 must be solved by trace_invention."""
    config = OrchestratorConfig(
        enable_adapter_genesis=False,
        enable_manifold_memory=False,
        enable_near_solved_memory=False,
        enable_operator_memory=False,
        enable_neural_advisory=False,
        enable_domain_morphism=False,
        enable_property_expansion=False,
        enable_frontier_operators=False,
        enable_static_portfolio=False,
    )
    trace = _solve("2a5f8217", config)
    assert trace.final_status == "solved", (
        f"2a5f8217: expected solved via trace_invention, got {trace.final_status}"
    )
    assert trace.selected_proposal.module_name == "trace_invention"
    assert not trace.verification.false_positive


# --- Frontier operator regressions ---

@pytest.mark.parametrize("task_id", [
    "92e50de0",
    "bb43febb",
    "a5313dff",
])
def test_frontier_operator_regression(task_id):
    """Frontier operator tasks must be solved."""
    config = OrchestratorConfig(
        enable_adapter_genesis=False,
        enable_manifold_memory=False,
        enable_near_solved_memory=False,
        enable_operator_memory=False,
        enable_neural_advisory=False,
        enable_domain_morphism=False,
        enable_property_expansion=False,
        enable_trace_invention=False,
        enable_static_portfolio=False,
    )
    trace = _solve(task_id, config)
    assert trace.final_status == "solved", (
        f"{task_id}: expected solved via frontier_operators, got {trace.final_status}"
    )
    assert trace.selected_proposal.module_name == "frontier_operators"
    assert not trace.verification.false_positive


# --- Full orchestrator: no regressions on any previously solved task ---

@pytest.mark.parametrize("task_id", [
    "2a5f8217", "08ed6ac7", "c8f0f002", "b1948b0a",
    "92e50de0", "bb43febb", "a5313dff", "ea32f347", "e98196ab",
])
def test_full_orchestrator_solves_regressed_task(task_id):
    """Full orchestrator must solve all previously regressed tasks."""
    trace = _solve(task_id)
    assert trace.final_status == "solved", (
        f"{task_id}: expected solved in full orchestrator, got {trace.final_status}"
    )
    assert trace.verification is not None
    assert not trace.verification.false_positive


# --- Novel v2 solves must be preserved ---

@pytest.mark.parametrize("task_id", [
    "56ff96f3",
    "50cb2852",
    "4347f46a",
    "bb43febb",
    "92e50de0",
])
def test_novel_v2_solves_preserved(task_id):
    """Novel v2 solves (frontier operators) must remain solved."""
    trace = _solve(task_id)
    assert trace.final_status == "solved", (
        f"{task_id}: novel v2 solve lost, got {trace.final_status}"
    )
    assert not trace.verification.false_positive


# --- No false positives ---

@pytest.mark.parametrize("task_id", [
    "2a5f8217", "08ed6ac7", "c8f0f002", "b1948b0a",
    "92e50de0", "bb43febb", "a5313dff", "ea32f347", "e98196ab",
    "56ff96f3", "50cb2852", "4347f46a",
])
def test_no_false_positive(task_id):
    """No task should produce a false positive."""
    trace = _solve(task_id)
    if trace.verification is not None:
        assert not trace.verification.false_positive, (
            f"{task_id}: false positive detected"
        )


# --- Verifier: test-confirmed proposals bypass falsification ---

def test_verifier_accepts_test_confirmed_despite_falsification():
    """A proposal that matches test outputs should be accepted even if
    falsification probes fail."""
    verifier = ProposalVerifier()

    class FakeProposal:
        def __init__(self):
            self.hypothesis = {"execute": lambda grid: grid}
            self.module_name = "test"
            self.operator_family = "identity"

    proposal = FakeProposal()
    grid = np.eye(3, dtype=int)
    train_pairs = [(grid, grid)]
    test_inputs = [grid]
    test_outputs = [grid]

    outcome = verifier.verify(proposal, train_pairs, test_inputs, test_outputs)
    assert outcome.accepted
    assert not outcome.false_positive


def test_verifier_rejects_test_mismatch_before_falsification():
    """A proposal that fails test match should be rejected as FP,
    even before running falsification."""
    verifier = ProposalVerifier()

    class FakeProposal:
        def __init__(self):
            self.hypothesis = {"execute": lambda grid: grid}
            self.module_name = "test"
            self.operator_family = "identity"

    proposal = FakeProposal()
    grid = np.eye(3, dtype=int)
    wrong_output = np.zeros((3, 3), dtype=int)
    train_pairs = [(grid, grid)]
    test_inputs = [grid]
    test_outputs = [wrong_output]

    outcome = verifier.verify(proposal, train_pairs, test_inputs, test_outputs)
    assert not outcome.accepted
    assert outcome.false_positive
    assert outcome.rejection_reason == "test_output_mismatch"
