"""Tests for composed frontier operators (select_then_recolor, select_then_crop_extract)."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reasoning_project.composed_frontier_operators import (
    SelectThenRecolorOperator,
    SelectThenCropExtractOperator,
    _infer_recolor_map,
    _execute_select_recolor,
    _execute_select_crop,
)
from reasoning_project.frontier_operator_registry import FrontierOperatorRegistry
from reasoning_project.adaptive_orchestrator import ModuleProposal
from reasoning_project.proposal_verifier import ProposalVerifier


def _make_recolor_pairs():
    """Two objects: largest gets recolored from 1->3, smallest removed."""
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


def _make_crop_pairs():
    """Two objects: largest is kept and cropped to bounding box."""
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


class TestSelectThenRecolorOperator:

    def test_trigger_with_discriminative_property(self):
        op = SelectThenRecolorOperator()
        analysis = type("A", (), {
            "property_trace": {"has_discriminative_property": True},
            "object_trace": {"pairs": []},
            "candidate_operator_families": [],
        })()
        assert op.trigger(analysis)

    def test_trigger_same_size_no_property(self):
        op = SelectThenRecolorOperator()
        analysis = type("A", (), {
            "property_trace": {"has_discriminative_property": False},
            "object_trace": {"pairs": [{"size_change": False}]},
            "candidate_operator_families": [],
        })()
        assert op.trigger(analysis)

    def test_propose_produces_executable(self):
        op = SelectThenRecolorOperator()
        pairs = _make_recolor_pairs()
        analysis = type("A", (), {
            "property_trace": {"has_discriminative_property": True},
            "object_trace": {"pairs": [{"size_change": False}]},
            "candidate_operator_families": [],
            "task_id": "test_recolor",
        })()
        proposals = op.propose(analysis, pairs, [pairs[0][0]])
        assert len(proposals) > 0
        hp = proposals[0]
        assert callable(hp["execute"])
        assert hp["operator_family"] == "select_then_recolor"

    def test_execute_train_consistent(self):
        op = SelectThenRecolorOperator()
        pairs = _make_recolor_pairs()
        analysis = type("A", (), {
            "property_trace": {"has_discriminative_property": True},
            "object_trace": {"pairs": [{"size_change": False}]},
            "candidate_operator_families": [],
            "task_id": "test_recolor",
        })()
        proposals = op.propose(analysis, pairs, [pairs[0][0]])
        assert len(proposals) > 0
        execute_fn = proposals[0]["execute"]
        for inp, out in pairs:
            pred = execute_fn(inp)
            assert pred is not None
            assert np.array_equal(pred, out), f"Mismatch: {pred} vs {out}"

    def test_verifier_accepts_correct_proposal(self):
        op = SelectThenRecolorOperator()
        pairs = _make_recolor_pairs()
        analysis = type("A", (), {
            "property_trace": {"has_discriminative_property": True},
            "object_trace": {"pairs": [{"size_change": False}]},
            "candidate_operator_families": [],
            "task_id": "test_recolor",
        })()
        proposals = op.propose(analysis, pairs, [pairs[0][0]])
        assert len(proposals) > 0

        verifier = ProposalVerifier()
        mp = ModuleProposal(
            module_name="frontier_operators",
            proposal_type="frontier_select_then_recolor",
            operator_family="select_then_recolor",
            selector=proposals[0].get("selector"),
            hypothesis=proposals[0],
            confidence=0.65,
            evidence={},
        )
        outcome = verifier.verify(mp, pairs, [pairs[0][0]])
        assert outcome.accepted
        assert outcome.train_consistent
        assert outcome.loo_passed

    def test_verifier_rejects_wrong_recolor(self):
        verifier = ProposalVerifier()
        pairs = _make_recolor_pairs()
        mp = ModuleProposal(
            module_name="frontier_operators",
            proposal_type="frontier_select_then_recolor",
            operator_family="select_then_recolor",
            selector=None,
            hypothesis={"execute": lambda grid: grid},
            confidence=0.5,
            evidence={},
        )
        outcome = verifier.verify(mp, pairs, [pairs[0][0]])
        assert not outcome.accepted


class TestSelectThenCropExtractOperator:

    def test_trigger_with_size_change(self):
        op = SelectThenCropExtractOperator()
        analysis = type("A", (), {
            "property_trace": {},
            "object_trace": {"pairs": [{"size_change": True}]},
            "candidate_operator_families": [],
        })()
        assert op.trigger(analysis)

    def test_no_trigger_without_size_change(self):
        op = SelectThenCropExtractOperator()
        analysis = type("A", (), {
            "property_trace": {},
            "object_trace": {"pairs": [{"size_change": False}]},
            "candidate_operator_families": [],
        })()
        assert not op.trigger(analysis)

    def test_propose_produces_executable(self):
        op = SelectThenCropExtractOperator()
        pairs = _make_crop_pairs()
        analysis = type("A", (), {
            "property_trace": {},
            "object_trace": {"pairs": [{"size_change": True}]},
            "candidate_operator_families": [],
            "task_id": "test_crop",
        })()
        proposals = op.propose(analysis, pairs, [pairs[0][0]])
        assert len(proposals) > 0
        hp = proposals[0]
        assert callable(hp["execute"])
        assert hp["operator_family"] == "select_then_crop_extract"

    def test_execute_train_consistent(self):
        op = SelectThenCropExtractOperator()
        pairs = _make_crop_pairs()
        analysis = type("A", (), {
            "property_trace": {},
            "object_trace": {"pairs": [{"size_change": True}]},
            "candidate_operator_families": [],
            "task_id": "test_crop",
        })()
        proposals = op.propose(analysis, pairs, [pairs[0][0]])
        assert len(proposals) > 0
        execute_fn = proposals[0]["execute"]
        for inp, out in pairs:
            pred = execute_fn(inp)
            assert pred is not None
            assert np.array_equal(pred, out), f"Shape: {pred.shape} vs {out.shape}"

    def test_verifier_accepts_correct_crop(self):
        op = SelectThenCropExtractOperator()
        pairs = _make_crop_pairs()
        analysis = type("A", (), {
            "property_trace": {},
            "object_trace": {"pairs": [{"size_change": True}]},
            "candidate_operator_families": [],
            "task_id": "test_crop",
        })()
        proposals = op.propose(analysis, pairs, [pairs[0][0]])
        assert len(proposals) > 0

        verifier = ProposalVerifier()
        mp = ModuleProposal(
            module_name="frontier_operators",
            proposal_type="frontier_select_then_crop",
            operator_family="select_then_crop_extract",
            selector=proposals[0].get("selector"),
            hypothesis=proposals[0],
            confidence=0.65,
            evidence={},
        )
        outcome = verifier.verify(mp, pairs, [pairs[0][0]])
        assert outcome.accepted
        assert outcome.train_consistent
        assert outcome.loo_passed


class TestRegistryIntegration:

    def test_new_operators_registered(self):
        registry = FrontierOperatorRegistry()
        names = registry.get_all()
        assert "select_then_recolor" in names
        assert "select_then_crop_extract" in names

    def test_recolor_triggered(self):
        registry = FrontierOperatorRegistry()
        analysis = type("A", (), {
            "property_trace": {"has_discriminative_property": True},
            "object_trace": {"pairs": [{"size_change": False}]},
            "candidate_operator_families": ["recolor"],
        })()
        triggered_names = [name for name, _ in registry.get_triggered(analysis)]
        assert "select_then_recolor" in triggered_names

    def test_crop_triggered(self):
        registry = FrontierOperatorRegistry()
        analysis = type("A", (), {
            "property_trace": {},
            "object_trace": {"pairs": [{"size_change": True, "n_input_objects": 3, "n_output_objects": 1}]},
            "candidate_operator_families": ["shape_completion"],
        })()
        triggered_names = [name for name, _ in registry.get_triggered(analysis)]
        assert "select_then_crop_extract" in triggered_names
