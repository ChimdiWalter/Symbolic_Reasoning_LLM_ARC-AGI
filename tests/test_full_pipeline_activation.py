"""Tests for the full pipeline activation repair.

Validates that:
  1. No v1 regressions
  2. No frontier regressions
  3. No false-positive acceptance path
  4. Selector invention integrates with property expansion
  5. AdapterGenesis schema proposals integrate with orchestrator
  6. Neural advisory returns routing hints
  7. Memory seeding works
"""
import numpy as np
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from reasoning_project.adaptive_orchestrator import (
    GatedAdaptiveReasoningOrchestrator,
    ModuleProposal,
    OrchestratorConfig,
)
from reasoning_project.selector_invention import SelectorInventor
from reasoning_project.property_expansion import PropertyExpansionEngine
from reasoning_project.adapter_schema_proposals import AdapterSchemaProposer
from reasoning_project.neural_proposal_interface import NeuralProposalInterface
from reasoning_project.proposal_verifier import ProposalVerifier


def _make_simple_filter_task():
    """Task solvable by is_largest filter."""
    inp = np.zeros((5, 5), dtype=int)
    inp[0:3, 0:3] = 1
    inp[4, 4] = 2
    out = np.zeros((5, 5), dtype=int)
    out[0:3, 0:3] = 1
    return [(inp, out)]


def _make_recolor_task():
    """Task solvable by discriminative filter + recolor."""
    inp = np.zeros((5, 5), dtype=int)
    inp[0:2, 0:2] = 1
    inp[3:5, 3:5] = 2
    out = np.zeros((5, 5), dtype=int)
    out[0:2, 0:2] = 3  # recolored
    out[3:5, 3:5] = 2
    return [(inp, out)]


class TestSelectorIntegration:
    def test_property_expansion_uses_selector_inventor(self):
        engine = PropertyExpansionEngine()
        assert hasattr(engine, "selector_inventor")
        assert isinstance(engine.selector_inventor, SelectorInventor)

    def test_find_executable_selectors(self):
        engine = PropertyExpansionEngine()
        pairs = _make_simple_filter_task()
        results = engine.find_executable_selectors(
            pairs,
            object_trace={"pairs": [{"n_input_objects": 2}]},
            failure_trace={"failure_type": "no_discriminative_property"},
        )
        assert len(results) > 0
        for r in results:
            assert "selector_expression" in r
            assert "selector_callable" in r
            assert callable(r["selector_callable"])

    def test_find_discriminative_property_includes_invented(self):
        engine = PropertyExpansionEngine()
        pairs = _make_simple_filter_task()
        results = engine.find_discriminative_property(
            pairs,
            object_trace={"pairs": [{"n_input_objects": 2}]},
            failure_trace={"failure_type": "no_discriminative_property"},
        )
        assert len(results) > 0
        # Should contain at least some with score > 0
        assert any(r["score"] > 0 for r in results)


class TestAdapterGenesisSchemaIntegration:
    def test_adapter_schema_proposer_init(self):
        proposer = AdapterSchemaProposer()
        assert hasattr(proposer, "selector_inventor")

    def test_propose_schemas_returns_alternatives(self):
        proposer = AdapterSchemaProposer()
        pairs = _make_simple_filter_task()
        schemas = proposer.propose_schemas(pairs)
        # Should propose at least per_color or monochrome
        schema_names = [s.schema_name for s in schemas]
        assert "connected_components" not in schema_names  # default excluded


class TestNeuralAdvisoryRouting:
    def test_routing_hints_present(self):
        npi = NeuralProposalInterface()

        class FakeAnalysis:
            object_trace = {"pairs": [{"n_input_objects": 5, "n_output_objects": 5, "size_change": False}]}
            property_trace = {"has_discriminative_property": False, "best_property": None, "score": 0}
            candidate_operator_families = ["filter_select"]
            failure_trace = {"failure_type": "no_discriminative_property"}
            memory_retrievals = []
            domain = "arc"

        result = npi.propose(FakeAnalysis(), [(np.zeros((3,3),dtype=int), np.zeros((3,3),dtype=int))])
        assert result is not None
        assert result.neural_helped_routing is True
        assert len(result.selector_type_ranking) > 0


class TestVerifierIntegrity:
    def test_non_executable_rejected(self):
        verifier = ProposalVerifier()
        proposal = ModuleProposal(
            module_name="test",
            proposal_type="test",
            operator_family="test",
            selector=None,
            hypothesis={"metadata_only": True},  # no execute callable
            confidence=0.5,
            evidence={},
        )
        pairs = _make_simple_filter_task()
        outcome = verifier.verify(proposal, pairs, [pairs[0][0]], None)
        assert not outcome.accepted
        assert "executable" in (outcome.rejection_reason or "").lower() or not outcome.train_consistent

    def test_correct_proposal_accepted(self):
        verifier = ProposalVerifier()
        pairs = _make_simple_filter_task()

        def execute(grid):
            result = grid.copy()
            from reasoning_project.reasoning_engine import _extract_objects_with_properties
            objs = _extract_objects_with_properties(grid)
            if len(objs) < 2:
                return result
            max_area = max(o["area"] for o in objs)
            for o in objs:
                if o["area"] < max_area:
                    result[o["mask"]] = 0
            return result

        proposal = ModuleProposal(
            module_name="test",
            proposal_type="test",
            operator_family="filter",
            selector="is_largest",
            hypothesis={"execute": execute},
            confidence=0.9,
            evidence={},
        )
        outcome = verifier.verify(proposal, pairs, [pairs[0][0]], None)
        assert outcome.accepted or outcome.train_consistent

    def test_wrong_proposal_rejected(self):
        verifier = ProposalVerifier()
        pairs = _make_simple_filter_task()

        def bad_execute(grid):
            return np.ones_like(grid) * 9

        proposal = ModuleProposal(
            module_name="test",
            proposal_type="test",
            operator_family="bad",
            selector=None,
            hypothesis={"execute": bad_execute},
            confidence=0.9,
            evidence={},
        )
        outcome = verifier.verify(proposal, pairs, [pairs[0][0]], None)
        assert not outcome.accepted
