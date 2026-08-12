"""Regression test: v2 orchestrator must reproduce v1's certified solves.

These tasks were verified in v1 with certificates. V2 must solve them
through its proposal-verify pipeline without relaxing verification.
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

V1_CERTIFIED_TASKS = ["2a5f8217", "d89b689b", "e9ac8c9e", "a48eeaf7"]
V1_STATIC_SOLVED = ["a5313dff", "f5aa3634"]


@pytest.fixture(scope="module")
def arc_tasks():
    return {t.task_id: t for t in load_arc_tasks(ARC_ROOT)}


@pytest.fixture(scope="module")
def orchestrator():
    config = OrchestratorConfig(timeout_per_task=300.0)
    return GatedAdaptiveReasoningOrchestrator(config)


@pytest.mark.parametrize("task_id", V1_CERTIFIED_TASKS)
def test_v2_reproduces_v1_certified(task_id, arc_tasks, orchestrator):
    task = arc_tasks[task_id]
    train_pairs = [(ex.input_grid, ex.output_grid) for ex in task.train if ex.output_grid is not None]
    test_inputs = [ex.input_grid for ex in task.test]
    test_outputs = [ex.output_grid for ex in task.test if ex.output_grid is not None] or None

    trace = orchestrator.solve_task(task_id, train_pairs, test_inputs, test_outputs)

    assert trace.final_status == "solved", (
        f"v2 failed to reproduce v1 certified task {task_id}: "
        f"status={trace.final_status}, proposals={len(trace.proposals)}"
    )
    assert trace.verification is not None
    assert trace.verification.accepted
    assert trace.verification.train_consistent
    assert trace.verification.loo_passed
    assert not trace.verification.false_positive


@pytest.mark.parametrize("task_id", V1_STATIC_SOLVED)
def test_v2_reproduces_v1_static(task_id, arc_tasks, orchestrator):
    task = arc_tasks[task_id]
    train_pairs = [(ex.input_grid, ex.output_grid) for ex in task.train if ex.output_grid is not None]
    test_inputs = [ex.input_grid for ex in task.test]
    test_outputs = [ex.output_grid for ex in task.test if ex.output_grid is not None] or None

    trace = orchestrator.solve_task(task_id, train_pairs, test_inputs, test_outputs)

    assert trace.final_status == "solved", (
        f"v2 failed to reproduce v1 static-solved task {task_id}: "
        f"status={trace.final_status}, proposals={len(trace.proposals)}"
    )
    assert trace.verification is not None
    assert trace.verification.accepted


def test_v2_produces_executable_proposals(arc_tasks, orchestrator):
    """At least one proposal per solved task must be executable."""
    task = arc_tasks["2a5f8217"]
    train_pairs = [(ex.input_grid, ex.output_grid) for ex in task.train if ex.output_grid is not None]
    test_inputs = [ex.input_grid for ex in task.test]

    config = OrchestratorConfig(timeout_per_task=300.0)
    orch = GatedAdaptiveReasoningOrchestrator(config)
    analysis = orch.analyze_task("2a5f8217", train_pairs)
    routes = orch._route_with_reasons(analysis)
    triggered = [m for m, (t, _) in routes.items() if t]
    proposals = orch.collect_proposals(analysis, triggered, train_pairs, test_inputs)

    executable_count = sum(
        1 for p in proposals
        if (isinstance(p.hypothesis, dict) and callable(p.hypothesis.get("execute")))
        or callable(p.hypothesis)
    )
    assert executable_count > 0, (
        f"No executable proposals generated for known-solvable task. "
        f"Total proposals: {len(proposals)}"
    )


def test_v2_zero_false_positives(arc_tasks, orchestrator):
    """V2 must not produce false positives on unsolvable tasks."""
    unsolvable_ids = ["1d0a4b61", "8eb1be9a"]
    for task_id in unsolvable_ids:
        if task_id not in arc_tasks:
            continue
        task = arc_tasks[task_id]
        train_pairs = [(ex.input_grid, ex.output_grid) for ex in task.train if ex.output_grid is not None]
        test_inputs = [ex.input_grid for ex in task.test]
        test_outputs = [ex.output_grid for ex in task.test if ex.output_grid is not None] or None

        trace = orchestrator.solve_task(task_id, train_pairs, test_inputs, test_outputs)

        assert trace.final_status != "false_positive_rejected", (
            f"v2 produced false positive on task {task_id}"
        )
