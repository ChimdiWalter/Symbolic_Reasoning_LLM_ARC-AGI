"""Integration tests for select-then-transform operators with the full orchestrator."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reasoning_project.adaptive_orchestrator import (
    GatedAdaptiveReasoningOrchestrator,
    OrchestratorConfig,
)
from reasoning_project.proposal_verifier import ProposalVerifier


def _make_recolor_task():
    """Task: keep largest object, recolor from 1->3, remove small objects."""
    inp1 = np.array([
        [1, 1, 0, 2],
        [1, 1, 0, 2],
        [0, 0, 0, 0],
    ])
    out1 = np.array([
        [3, 3, 0, 0],
        [3, 3, 0, 0],
        [0, 0, 0, 0],
    ])
    inp2 = np.array([
        [1, 1, 1, 0, 4],
        [1, 1, 1, 0, 0],
        [0, 0, 0, 0, 0],
    ])
    out2 = np.array([
        [3, 3, 3, 0, 0],
        [3, 3, 3, 0, 0],
        [0, 0, 0, 0, 0],
    ])
    return [(inp1, out1), (inp2, out2)]


def _make_crop_task():
    """Task: keep largest object, crop to bounding box."""
    inp1 = np.array([
        [0, 0, 0, 0, 0],
        [0, 5, 5, 0, 0],
        [0, 5, 5, 0, 2],
        [0, 0, 0, 0, 0],
    ])
    out1 = np.array([
        [5, 5],
        [5, 5],
    ])
    inp2 = np.array([
        [0, 0, 0, 0, 0],
        [0, 0, 5, 5, 5],
        [0, 0, 5, 5, 5],
        [3, 0, 5, 5, 5],
        [0, 0, 0, 0, 0],
    ])
    out2 = np.array([
        [5, 5, 5],
        [5, 5, 5],
        [5, 5, 5],
    ])
    return [(inp1, out1), (inp2, out2)]


class TestSelectThenRecolorIntegration:

    def test_orchestrator_solves_recolor_task(self):
        config = OrchestratorConfig(
            timeout_per_task=120.0,
            enable_trace_invention=False,
            enable_static_portfolio=False,
            enable_adapter_genesis=False,
        )
        orch = GatedAdaptiveReasoningOrchestrator(config=config)
        pairs = _make_recolor_task()
        test_inputs = [pairs[0][0]]
        test_outputs = [pairs[0][1]]

        trace = orch.solve_task("synth_recolor", pairs, test_inputs, test_outputs)
        assert trace.final_status == "solved", (
            f"Expected solved, got {trace.final_status}. "
            f"Proposals: {[(p.module_name, p.operator_family) for p in trace.proposals]}"
        )

    def test_recolor_no_false_positive(self):
        config = OrchestratorConfig(
            timeout_per_task=120.0,
            enable_trace_invention=False,
            enable_static_portfolio=False,
            enable_adapter_genesis=False,
        )
        orch = GatedAdaptiveReasoningOrchestrator(config=config)
        pairs = _make_recolor_task()
        test_inputs = [pairs[0][0]]
        wrong_output = [np.zeros_like(pairs[0][1])]

        trace = orch.solve_task("synth_recolor_fp", pairs, test_inputs, wrong_output)
        if trace.verification:
            assert not trace.verification.false_positive or trace.final_status != "solved"


class TestSelectThenCropIntegration:

    def test_orchestrator_solves_crop_task(self):
        config = OrchestratorConfig(
            timeout_per_task=120.0,
            enable_trace_invention=False,
            enable_static_portfolio=False,
            enable_adapter_genesis=False,
        )
        orch = GatedAdaptiveReasoningOrchestrator(config=config)
        pairs = _make_crop_task()
        test_inputs = [pairs[0][0]]
        test_outputs = [pairs[0][1]]

        trace = orch.solve_task("synth_crop", pairs, test_inputs, test_outputs)
        assert trace.final_status == "solved", (
            f"Expected solved, got {trace.final_status}. "
            f"Proposals: {[(p.module_name, p.operator_family) for p in trace.proposals]}"
        )


class TestNoV1Regression:

    def test_flipud_still_works(self):
        """Ensure a simple flipud task still solves (v1 regression guard)."""
        verifier = ProposalVerifier()
        inp1 = np.array([[1, 2], [3, 4]])
        out1 = np.array([[3, 4], [1, 2]])
        inp2 = np.array([[5, 6], [7, 8]])
        out2 = np.array([[7, 8], [5, 6]])
        pairs = [(inp1, out1), (inp2, out2)]

        from reasoning_project.adaptive_orchestrator import ModuleProposal
        mp = ModuleProposal(
            module_name="test",
            proposal_type="test",
            operator_family="flip",
            selector=None,
            hypothesis={"execute": lambda grid: np.flipud(grid)},
            confidence=0.8,
            evidence={},
        )
        outcome = verifier.verify(mp, pairs, [pairs[0][0]])
        assert outcome.accepted
