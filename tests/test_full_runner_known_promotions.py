"""Regression test: the full ARC-1000 runner must reproduce all 4 known promotions.

These tasks were verified to promote via direct TraceDrivenOperatorInventor calls.
The full runner must reproduce the same result — if it doesn't, the ARC-1000 gating
experiment is invalid.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from reasoning_project.arc_adapter import load_arc_tasks
from reasoning_project.trace_operator_invention import TraceDrivenOperatorInventor
from reasoning_project.events import ReasoningEventLog
from reasoning_project.reasoning_engine import ReasoningMemory
from reasoning_project.manifold_memory import MemoryManifold
from reasoning_project.near_solved_memory import NearSolvedMemory
from reasoning_project.adapter_genesis import AdapterGenesis
from reasoning_project.active_falsifier import ActiveFalsifier
from reasoning_project.certificates import CertificateBuilder

from run_full_arc1000_novel_pipeline import (
    run_single_task_across_configs,
    CONFIGS,
    load_gap_traces,
    build_trace_for_task,
)

KNOWN_TASKS = {
    "2a5f8217": {
        "trace_family": "recolor_in_place",
        "trace_property": "is_color_1",
        "expected_op_family": "color_transfer_recolor",
    },
    "a48eeaf7": {
        "trace_family": "copy_to_position",
        "trace_property": "is_largest",
        "expected_op_family": "copy_to_position",
    },
    "d89b689b": {
        "trace_family": "copy_to_position",
        "trace_property": "is_largest",
        "expected_op_family": "copy_to_position",
    },
    "e9ac8c9e": {
        "trace_family": "copy_to_position",
        "trace_property": "is_largest",
        "expected_op_family": "copy_to_position",
    },
}


@pytest.fixture(scope="module")
def arc_tasks():
    return {t.task_id: t for t in load_arc_tasks("data/arc", split="training")}


@pytest.fixture(scope="module")
def gap_traces():
    traces = load_gap_traces(PROJECT_ROOT)
    if not traces:
        traces = load_gap_traces(Path("."))
    return traces


def _build_shared_state(gap_traces, tmpdir):
    event_log = ReasoningEventLog()
    memory = ReasoningMemory()
    manifold = MemoryManifold()
    ns_mem = NearSolvedMemory(manifold)
    cert_dir = Path(tmpdir) / "certs"
    cert_dir.mkdir(exist_ok=True)
    return {
        "memory": memory,
        "manifold": manifold,
        "ns_mem": ns_mem,
        "event_log": event_log,
        "adapter_genesis": AdapterGenesis(manifold=manifold),
        "trace_inventor": TraceDrivenOperatorInventor(event_log=event_log),
        "falsifier": ActiveFalsifier(),
        "cert_builder": CertificateBuilder(),
        "cert_dir": cert_dir,
        "gap_traces": gap_traces,
    }


class TestTraceLoading:
    def test_traces_loaded(self, gap_traces):
        for tid in KNOWN_TASKS:
            assert tid in gap_traces, f"Task {tid} not found in gap traces"

    @pytest.mark.parametrize("task_id", list(KNOWN_TASKS.keys()))
    def test_trace_fields(self, task_id, gap_traces):
        spec = KNOWN_TASKS[task_id]
        trace = build_trace_for_task(task_id, gap_traces, None)
        assert trace.get("best_property") == spec["trace_property"], (
            f"Expected trace_property={spec['trace_property']}, "
            f"got {trace.get('best_property')}"
        )
        assert trace.get("needed_operator_family") == spec["trace_family"], (
            f"Expected trace_family={spec['trace_family']}, "
            f"got {trace.get('needed_operator_family')}"
        )


class TestDirectPromotion:
    @pytest.mark.parametrize("task_id", list(KNOWN_TASKS.keys()))
    def test_direct_promotion(self, task_id, arc_tasks, gap_traces):
        task = arc_tasks[task_id]
        train_pairs = [(ex.input_grid, ex.output_grid) for ex in task.train]
        test_inputs = [ex.input_grid for ex in task.test]
        test_outputs = [
            ex.output_grid for ex in task.test if ex.output_grid is not None
        ]
        if len(test_outputs) != len(test_inputs):
            test_outputs = []
        trace = build_trace_for_task(task_id, gap_traces, None)

        inventor = TraceDrivenOperatorInventor(event_log=ReasoningEventLog())
        result = inventor.run_full_pipeline(
            task_id=task_id,
            train_pairs=train_pairs,
            test_inputs=test_inputs,
            trace=trace,
            test_outputs=test_outputs if test_outputs else None,
        )

        assert result["operator_proposed"], f"{task_id}: operator not proposed"
        assert result["loo_passed"], f"{task_id}: LOO failed"
        assert result["promoted"], f"{task_id}: not promoted"
        assert result.get("predictions") is not None, f"{task_id}: no predictions"
        if test_outputs:
            for p, e in zip(result["predictions"], test_outputs):
                assert np.array_equal(p, e), f"{task_id}: prediction mismatch"


class TestFullRunnerPromotion:
    @pytest.mark.parametrize("task_id", list(KNOWN_TASKS.keys()))
    def test_full_runner_promotion(self, task_id, arc_tasks, gap_traces, tmp_path):
        task = arc_tasks[task_id]
        shared_state = _build_shared_state(gap_traces, tmp_path)

        t0 = time.perf_counter()
        result = run_single_task_across_configs(
            task=task,
            configs=CONFIGS,
            timeout_per_config=60.0,
            shared_state=shared_state,
        )
        elapsed = time.perf_counter() - t0

        assert result["operator_proposed"], (
            f"{task_id}: operator not proposed in full runner "
            f"(elapsed={elapsed:.1f}s, error={result.get('error')})"
        )
        assert result["operator_promoted"], (
            f"{task_id}: not promoted in full runner "
            f"(family={result.get('operator_family')}, elapsed={elapsed:.1f}s)"
        )
        assert result["final_config_that_solved"] is not None, (
            f"{task_id}: no solving config"
        )

        spec = KNOWN_TASKS[task_id]
        if result.get("operator_family"):
            assert result["operator_family"] == spec["expected_op_family"], (
                f"{task_id}: expected family {spec['expected_op_family']}, "
                f"got {result['operator_family']}"
            )


class TestKnownTaskGuardWouldPass:
    @pytest.mark.parametrize("task_id", list(KNOWN_TASKS.keys()))
    def test_guard_pass(self, task_id, arc_tasks, gap_traces, tmp_path):
        """The known-task guard in the main loop would not stop the run."""
        task = arc_tasks[task_id]
        shared_state = _build_shared_state(gap_traces, tmp_path)

        result = run_single_task_across_configs(
            task=task,
            configs=CONFIGS,
            timeout_per_config=60.0,
            shared_state=shared_state,
        )

        assert result["operator_promoted"], (
            f"Guard would STOP: {task_id} not promoted"
        )
