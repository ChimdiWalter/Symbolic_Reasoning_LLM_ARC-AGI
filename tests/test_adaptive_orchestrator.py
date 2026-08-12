"""Tests for the Gated Adaptive Reasoning Orchestrator (v2 pipeline)."""
from __future__ import annotations

import numpy as np
import pytest

from reasoning_project.adaptive_orchestrator import (
    GatedAdaptiveReasoningOrchestrator,
    OrchestratorConfig,
    TaskAnalysis,
    ModuleProposal,
    OrchestratorTrace,
)
from reasoning_project.module_triggers import (
    should_call_adapter_genesis,
    should_call_manifold_memory,
    should_call_near_solved_memory,
    should_call_operator_memory,
    should_call_neural_advisory,
    should_call_domain_morphism,
    should_call_property_expansion,
    should_call_frontier_operators,
)
from reasoning_project.proposal_verifier import ProposalVerifier, VerificationOutcome
from reasoning_project.adapter_signature_interface import (
    AdapterSignature,
    adapter_to_signature,
    validate_signature,
)
from reasoning_project.operator_memory import OperatorMemory
from reasoning_project.property_expansion import PropertyExpansionEngine
from reasoning_project.frontier_operator_registry import FrontierOperatorRegistry
from reasoning_project.neural_proposal_interface import NeuralProposalInterface


def _make_analysis(
    task_id="test_task",
    domain="arc",
    adapter_ok=True,
    has_property=True,
    n_objects=5,
    size_change=False,
    failure_type="unknown",
) -> TaskAnalysis:
    return TaskAnalysis(
        task_id=task_id,
        domain=domain,
        adapter_status={"adapter_ok": adapter_ok, "confidence": 1.0 if adapter_ok else 0.3},
        object_trace={"pairs": [{"n_input_objects": n_objects, "n_output_objects": n_objects, "size_change": size_change}]},
        property_trace={"has_discriminative_property": has_property, "best_property": "is_largest" if has_property else None, "score": 0.9 if has_property else 0.0},
        relation_trace={"relations_extracted": True},
        failure_trace={"task_id": task_id, "failure_type": failure_type},
        candidate_operator_families=["filter_select", "recolor"],
        memory_retrievals=[],
        neural_advisory=None,
        domain_signature=None,
        morphism_candidates=[],
        evidence={},
    )


class TestModuleTriggers:
    def test_adapter_genesis_not_triggered_for_arc(self):
        analysis = _make_analysis(domain="arc", adapter_ok=True)
        triggered, reason = should_call_adapter_genesis(analysis)
        assert not triggered

    def test_adapter_genesis_triggered_for_non_arc(self):
        analysis = _make_analysis(domain="chess")
        triggered, reason = should_call_adapter_genesis(analysis)
        assert triggered
        assert "non_arc" in reason

    def test_adapter_genesis_triggered_on_failure(self):
        analysis = _make_analysis(adapter_ok=False)
        triggered, reason = should_call_adapter_genesis(analysis)
        assert triggered

    def test_manifold_memory_triggered_on_no_property(self):
        analysis = _make_analysis(has_property=False)
        triggered, reason = should_call_manifold_memory(analysis)
        assert triggered

    def test_manifold_memory_not_triggered_with_property(self):
        analysis = _make_analysis(has_property=True)
        analysis.memory_retrievals = []
        triggered, reason = should_call_manifold_memory(analysis)
        assert not triggered

    def test_near_solved_memory_triggered_on_property_failure(self):
        analysis = _make_analysis(failure_type="no_discriminative_property")
        triggered, reason = should_call_near_solved_memory(analysis)
        assert triggered

    def test_property_expansion_triggered_on_no_property(self):
        analysis = _make_analysis(has_property=False)
        triggered, reason = should_call_property_expansion(analysis)
        assert triggered

    def test_property_expansion_not_triggered_with_strong_property(self):
        analysis = _make_analysis(has_property=True)
        triggered, reason = should_call_property_expansion(analysis)
        assert not triggered

    def test_frontier_operators_triggered_on_candidate_family(self):
        analysis = _make_analysis()
        analysis.candidate_operator_families = ["shape_completion"]
        triggered, reason = should_call_frontier_operators(analysis)
        assert triggered

    def test_domain_morphism_not_triggered_for_arc(self):
        analysis = _make_analysis(domain="arc")
        triggered, reason = should_call_domain_morphism(analysis)
        assert not triggered

    def test_domain_morphism_triggered_for_non_arc(self):
        analysis = _make_analysis(domain="graph")
        triggered, reason = should_call_domain_morphism(analysis)
        assert triggered


class TestAdapterSignature:
    def test_grid_adapter_signature(self):
        from reasoning_project.reasoning_engine import GridDomainAdapter
        adapter = GridDomainAdapter()
        sig = adapter_to_signature(adapter, "arc")
        assert sig.domain_name == "arc"
        assert sig.adapter_name == "GridDomainAdapter"
        assert len(sig.property_library) > 10
        assert sig.confidence == 1.0

    def test_validate_valid_signature(self):
        sig = AdapterSignature(
            domain_name="arc",
            adapter_name="test",
            object_schema={"type": "grid"},
            property_library=["is_largest"],
            relation_algebra=["above"],
            operator_hooks=["filter"],
            confidence=0.9,
        )
        result = validate_signature(sig)
        assert result["valid"]

    def test_validate_empty_signature(self):
        sig = AdapterSignature(
            domain_name="",
            adapter_name="test",
            object_schema={},
            property_library=[],
            relation_algebra=[],
            operator_hooks=[],
            confidence=0.5,
        )
        result = validate_signature(sig)
        assert not result["valid"]


class TestOperatorMemory:
    def test_store_and_retrieve_by_task(self):
        mem = OperatorMemory()
        mem.store(task_id="t1", family="recolor", selector="is_largest")
        results = mem.get_by_task("t1")
        assert len(results) == 1
        assert results[0]["family"] == "recolor"

    def test_store_and_retrieve_by_family(self):
        mem = OperatorMemory()
        mem.store(task_id="t1", family="recolor")
        mem.store(task_id="t2", family="recolor")
        mem.store(task_id="t3", family="filter")
        results = mem.get_by_family("recolor")
        assert len(results) == 2

    def test_empty_retrieval(self):
        mem = OperatorMemory()
        assert mem.get_by_task("nonexistent") == []
        assert mem.get_by_family("nonexistent") == []


class TestPropertyExpansion:
    def test_engine_init(self):
        engine = PropertyExpansionEngine()
        catalog = engine.get_property_catalog()
        assert len(catalog) > 30

    def test_find_properties_on_simple_grid(self):
        engine = PropertyExpansionEngine()
        grid_in = np.zeros((5, 5), dtype=int)
        grid_in[0:2, 0:2] = 1
        grid_in[3:5, 3:5] = 2
        grid_out = np.zeros((5, 5), dtype=int)
        grid_out[0:2, 0:2] = 1
        train_pairs = [(grid_in, grid_out)]
        object_trace = {"pairs": [{"n_input_objects": 2, "n_output_objects": 1, "size_change": False}]}
        failure_trace = {"failure_type": "no_discriminative_property"}
        results = engine.find_discriminative_property(train_pairs, object_trace, failure_trace)
        assert isinstance(results, list)


class TestFrontierRegistry:
    def test_registry_init(self):
        reg = FrontierOperatorRegistry()
        assert len(reg.get_all()) >= 7

    def test_many_to_few_trigger(self):
        reg = FrontierOperatorRegistry()
        analysis = _make_analysis()
        analysis.object_trace = {"pairs": [{"n_input_objects": 5, "n_output_objects": 1, "size_change": False}]}
        triggered = reg.get_triggered(analysis)
        names = [name for name, _ in triggered]
        assert "many_to_few_grouping" in names


class TestNeuralInterface:
    def test_rule_based_fallback(self):
        interface = NeuralProposalInterface()
        analysis = _make_analysis()
        train_pairs = [(np.zeros((5, 5), dtype=int), np.zeros((5, 5), dtype=int))]
        proposal = interface.propose(analysis, train_pairs)
        assert proposal is not None
        assert len(proposal.operator_family_ranking) > 0


class TestProposalVerifier:
    def test_reject_no_hypothesis(self):
        verifier = ProposalVerifier(certificate_dir="/tmp/test_certs_v2")
        proposal = ModuleProposal(
            module_name="test", proposal_type="test",
            operator_family=None, selector=None,
            hypothesis=None, confidence=0.5, evidence={},
        )
        outcome = verifier.verify(proposal, [], [])
        assert not outcome.accepted
        assert outcome.rejection_reason == "no_executable_hypothesis"

    def test_reject_non_executable(self):
        verifier = ProposalVerifier(certificate_dir="/tmp/test_certs_v2")
        proposal = ModuleProposal(
            module_name="test", proposal_type="test",
            operator_family=None, selector=None,
            hypothesis={"data": "not_callable"}, confidence=0.5, evidence={},
        )
        outcome = verifier.verify(proposal, [], [])
        assert not outcome.accepted

    def test_accept_correct_hypothesis(self):
        verifier = ProposalVerifier(certificate_dir="/tmp/test_certs_v2")
        grid_in = np.array([[1, 0], [0, 1]])
        grid_out = np.array([[0, 1], [1, 0]])
        train_pairs = [(grid_in, grid_out)]
        test_inputs = [grid_in]

        def flip_fn(g):
            return 1 - g

        proposal = ModuleProposal(
            module_name="test", proposal_type="test",
            operator_family="flip", selector=None,
            hypothesis={"execute": flip_fn}, confidence=0.9, evidence={},
        )
        outcome = verifier.verify(proposal, train_pairs, test_inputs)
        assert outcome.accepted
        assert outcome.loo_passed
        assert outcome.certificate_path is not None

    def test_reject_train_inconsistent(self):
        verifier = ProposalVerifier(certificate_dir="/tmp/test_certs_v2")
        grid_in = np.array([[1, 0], [0, 1]])
        grid_out = np.array([[0, 1], [1, 0]])
        train_pairs = [(grid_in, grid_out)]

        def wrong_fn(g):
            return g

        proposal = ModuleProposal(
            module_name="test", proposal_type="test",
            operator_family=None, selector=None,
            hypothesis={"execute": wrong_fn}, confidence=0.9, evidence={},
        )
        outcome = verifier.verify(proposal, train_pairs, [grid_in])
        assert not outcome.accepted
        assert outcome.rejection_reason == "train_inconsistent"

    def test_detect_false_positive(self):
        verifier = ProposalVerifier(certificate_dir="/tmp/test_certs_v2")
        grid_in = np.array([[1, 0], [0, 1]])
        grid_out = np.array([[0, 1], [1, 0]])
        test_expected = np.array([[1, 1], [1, 1]])
        train_pairs = [(grid_in, grid_out)]

        def flip_fn(g):
            return 1 - g

        proposal = ModuleProposal(
            module_name="test", proposal_type="test",
            operator_family=None, selector=None,
            hypothesis={"execute": flip_fn}, confidence=0.9, evidence={},
        )
        outcome = verifier.verify(proposal, train_pairs, [grid_in], [test_expected])
        assert not outcome.accepted
        assert outcome.false_positive


class TestNoModuleBypassesVerifier:
    def test_orchestrator_always_verifies(self):
        config = OrchestratorConfig(timeout_per_task=10.0)
        orch = GatedAdaptiveReasoningOrchestrator(config)
        grid_in = np.array([[1, 2], [3, 4]])
        grid_out = np.array([[4, 3], [2, 1]])
        train_pairs = [(grid_in, grid_out)]
        test_inputs = [grid_in]
        trace = orch.solve_task("test_no_bypass", train_pairs, test_inputs)
        assert trace.final_status in ("unsolved", "all_proposals_rejected", "timeout")


class TestOrchestratorIntegration:
    def test_orchestrator_instantiates(self):
        orch = GatedAdaptiveReasoningOrchestrator()
        assert orch.config is not None

    def test_analyze_task(self):
        orch = GatedAdaptiveReasoningOrchestrator()
        grid_in = np.zeros((5, 5), dtype=int)
        grid_in[1:3, 1:3] = 1
        grid_in[3:5, 3:5] = 2
        grid_out = np.zeros((5, 5), dtype=int)
        grid_out[1:3, 1:3] = 1
        train_pairs = [(grid_in, grid_out)]
        analysis = orch.analyze_task("t1", train_pairs)
        assert analysis.task_id == "t1"
        assert analysis.domain == "arc"

    def test_route_modules(self):
        orch = GatedAdaptiveReasoningOrchestrator()
        analysis = _make_analysis(has_property=False)
        routes = orch.route_modules(analysis)
        assert routes.get("property_expansion") is True

    def test_solve_returns_trace(self):
        config = OrchestratorConfig(timeout_per_task=5.0)
        orch = GatedAdaptiveReasoningOrchestrator(config)
        grid_in = np.array([[1, 0], [0, 1]])
        grid_out = np.array([[0, 1], [1, 0]])
        train_pairs = [(grid_in, grid_out)]
        test_inputs = [grid_in]
        trace = orch.solve_task("t_smoke", train_pairs, test_inputs)
        assert isinstance(trace, OrchestratorTrace)
        assert trace.task_id == "t_smoke"
        assert trace.final_status in ("solved", "unsolved", "all_proposals_rejected", "timeout")
