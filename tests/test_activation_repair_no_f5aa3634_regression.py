"""Regression guard: f5aa3634 must remain solved after activation repair.

This task regressed from solved to false_positive_rejected when the
activation repair introduced memory cross-contamination via shared
ReasoningMemory in AdaptiveReasoningLoop instances. The fix isolates
memory per proposal source.
"""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from reasoning_project.adaptive_orchestrator import (
    GatedAdaptiveReasoningOrchestrator,
    OrchestratorConfig,
)
from reasoning_project.arc_adapter import load_arc_tasks

ARC_ROOT = Path(__file__).parent.parent / "data" / "arc"
TASK_ID = "f5aa3634"


@pytest.fixture(scope="module")
def arc_tasks():
    return {t.task_id: t for t in load_arc_tasks(ARC_ROOT)}


def _get_task_data(arc_tasks):
    task = arc_tasks[TASK_ID]
    train_pairs = [(ex.input_grid, ex.output_grid) for ex in task.train if ex.output_grid is not None]
    test_inputs = [ex.input_grid for ex in task.test]
    test_outputs = [ex.output_grid for ex in task.test if ex.output_grid is not None] or None
    return train_pairs, test_inputs, test_outputs


def test_full_orchestrator_solves_f5aa3634(arc_tasks):
    """Full orchestrator with all modules must solve f5aa3634."""
    config = OrchestratorConfig(timeout_per_task=300.0)
    orch = GatedAdaptiveReasoningOrchestrator(config)
    train_pairs, test_inputs, test_outputs = _get_task_data(arc_tasks)

    trace = orch.solve_task(TASK_ID, train_pairs, test_inputs, test_outputs)

    assert trace.final_status == "solved", (
        f"f5aa3634 regression: status={trace.final_status}, "
        f"proposals={len(trace.proposals)}, "
        f"triggered={trace.triggered_modules}"
    )
    assert trace.verification is not None
    assert trace.verification.accepted
    assert not trace.verification.false_positive


def test_static_portfolio_solves_f5aa3634(arc_tasks):
    """Static portfolio alone must solve f5aa3634."""
    config = OrchestratorConfig(
        timeout_per_task=300.0,
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
    orch = GatedAdaptiveReasoningOrchestrator(config)
    train_pairs, test_inputs, test_outputs = _get_task_data(arc_tasks)

    trace = orch.solve_task(TASK_ID, train_pairs, test_inputs, test_outputs)

    assert trace.final_status == "solved", (
        f"f5aa3634 static portfolio regression: status={trace.final_status}"
    )
    assert trace.selected_proposal is not None
    assert trace.selected_proposal.module_name == "static_portfolio"


def test_no_false_positive_on_f5aa3634(arc_tasks):
    """f5aa3634 must not be flagged as false_positive_rejected."""
    config = OrchestratorConfig(timeout_per_task=300.0)
    orch = GatedAdaptiveReasoningOrchestrator(config)
    train_pairs, test_inputs, test_outputs = _get_task_data(arc_tasks)

    trace = orch.solve_task(TASK_ID, train_pairs, test_inputs, test_outputs)

    assert trace.final_status != "false_positive_rejected", (
        f"f5aa3634 false positive regression: proposals={len(trace.proposals)}"
    )


def test_disabling_auxiliary_does_not_block_f5aa3634(arc_tasks):
    """Disabling auxiliary modules must not block f5aa3634."""
    config = OrchestratorConfig(
        timeout_per_task=300.0,
        enable_adapter_genesis=False,
        enable_manifold_memory=False,
        enable_neural_advisory=False,
        enable_domain_morphism=False,
        enable_frontier_operators=False,
        enable_property_expansion=False,
    )
    orch = GatedAdaptiveReasoningOrchestrator(config)
    train_pairs, test_inputs, test_outputs = _get_task_data(arc_tasks)

    trace = orch.solve_task(TASK_ID, train_pairs, test_inputs, test_outputs)

    assert trace.final_status == "solved", (
        f"f5aa3634 core-only regression: status={trace.final_status}"
    )
