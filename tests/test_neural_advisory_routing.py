"""Tests for neural advisory routing improvements."""
import numpy as np
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from reasoning_project.neural_proposal_interface import (
    NeuralProposal,
    NeuralProposalInterface,
)


def _make_analysis(n_objects=5, size_change=False, has_property=False, n_families=2):
    class FakeAnalysis:
        pass
    a = FakeAnalysis()
    a.object_trace = {"pairs": [
        {"n_input_objects": n_objects, "n_output_objects": n_objects if not size_change else 1,
         "size_change": size_change}
    ]}
    a.property_trace = {
        "has_discriminative_property": has_property,
        "best_property": "is_largest" if has_property else None,
        "score": 1.0 if has_property else 0.0,
    }
    a.candidate_operator_families = ["filter_select", "recolor"][:n_families]
    a.failure_trace = {"failure_type": "no_discriminative_property"}
    a.memory_retrievals = []
    a.domain = "arc"
    a.domain_signature = None
    a.morphism_candidates = []
    return a


class TestNeuralProposalInterface:
    def test_returns_proposal(self):
        npi = NeuralProposalInterface()
        analysis = _make_analysis()
        pairs = [(np.zeros((3, 3), dtype=int), np.zeros((3, 3), dtype=int))]
        result = npi.propose(analysis, pairs)
        assert result is not None
        assert isinstance(result, NeuralProposal)

    def test_family_ranking_has_entries(self):
        npi = NeuralProposalInterface()
        analysis = _make_analysis(n_objects=8)
        pairs = [(np.zeros((3, 3), dtype=int), np.zeros((3, 3), dtype=int))]
        result = npi.propose(analysis, pairs)
        assert len(result.operator_family_ranking) > 0

    def test_selector_type_ranking_populated(self):
        npi = NeuralProposalInterface()
        analysis = _make_analysis()
        pairs = [(np.zeros((3, 3), dtype=int), np.zeros((3, 3), dtype=int))]
        result = npi.propose(analysis, pairs)
        assert len(result.selector_type_ranking) > 0

    def test_size_change_suggests_crop(self):
        npi = NeuralProposalInterface()
        analysis = _make_analysis(size_change=True)
        pairs = [(np.zeros((3, 3), dtype=int), np.zeros((3, 3), dtype=int))]
        result = npi.propose(analysis, pairs)
        families = [f for f, s in result.operator_family_ranking]
        assert "crop_extract" in families or "separator_decompose" in families

    def test_neural_helped_routing_flag(self):
        npi = NeuralProposalInterface()
        analysis = _make_analysis()
        pairs = [(np.zeros((3, 3), dtype=int), np.zeros((3, 3), dtype=int))]
        result = npi.propose(analysis, pairs)
        assert result.neural_helped_routing is True

    def test_object_schema_hint_few_objects(self):
        npi = NeuralProposalInterface()
        analysis = _make_analysis(n_objects=1)
        pairs = [(np.zeros((3, 3), dtype=int), np.zeros((3, 3), dtype=int))]
        result = npi.propose(analysis, pairs)
        assert result.object_schema_hint == "per_color_components"

    def test_object_schema_hint_many_objects(self):
        npi = NeuralProposalInterface()
        analysis = _make_analysis(n_objects=15)
        pairs = [(np.zeros((3, 3), dtype=int), np.zeros((3, 3), dtype=int))]
        result = npi.propose(analysis, pairs)
        assert result.object_schema_hint == "monochrome_components"

    def test_selector_candidates_populated(self):
        npi = NeuralProposalInterface()
        analysis = _make_analysis(has_property=True)
        pairs = [(np.zeros((3, 3), dtype=int), np.zeros((3, 3), dtype=int))]
        result = npi.propose(analysis, pairs)
        assert len(result.selector_candidates) > 0
        assert result.selector_candidates[0][0] == "is_largest"
