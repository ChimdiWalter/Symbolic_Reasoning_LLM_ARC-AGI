"""Test that operator memory stores and retrieves executable operator schemas."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


class TestMemoryRetrievesExecutableOperator:
    def test_store_and_retrieve_executable(self):
        from reasoning_project.operator_memory import OperatorMemory

        mem = OperatorMemory()

        execute_fn = lambda grid: grid * 2

        mem.store_with_schema(
            task_id="test_task_1",
            family="discriminative_filter",
            selector="is_largest",
            hypothesis={"execute": execute_fn, "strategy": "filter"},
            certificate_path="/tmp/cert_test.json",
            execute_fn_name="discriminative_filter",
            operator_schema={"module": "static_portfolio"},
            proof_obligations_met=["train_consistent", "loo_passed"],
        )

        stored = mem.get_by_family("discriminative_filter")
        assert len(stored) == 1
        op = stored[0]
        assert op["family"] == "discriminative_filter"
        assert op["selector"] == "is_largest"
        assert op["certificate_path"] is not None
        assert "proof_obligations_met" in op
        assert "train_consistent" in op["proof_obligations_met"]

        hyp = op["hypothesis"]
        assert isinstance(hyp, dict)
        assert callable(hyp.get("execute"))

        template = op["parameter_template"]
        assert template.get("execute_fn_name") == "discriminative_filter"
        assert "operator_schema" in template

    def test_retrieve_by_task(self):
        from reasoning_project.operator_memory import OperatorMemory

        mem = OperatorMemory()
        mem.store_with_schema(
            task_id="abc123",
            family="shape_completion",
            hypothesis={"execute": lambda g: g},
            execute_fn_name="frontier_operators",
        )

        stored = mem.get_by_task("abc123")
        assert len(stored) == 1
        assert stored[0]["family"] == "shape_completion"

    def test_verifier_accepts_retrieved_executable(self):
        from reasoning_project.operator_memory import OperatorMemory
        from reasoning_project.proposal_verifier import ProposalVerifier

        mem = OperatorMemory()

        flip_fn = lambda grid: np.flipud(grid)

        inp1 = np.array([[1, 2], [3, 4]])
        out1 = np.array([[3, 4], [1, 2]])
        inp2 = np.array([[5, 6], [7, 8]])
        out2 = np.array([[7, 8], [5, 6]])
        train_pairs = [(inp1, out1), (inp2, out2)]

        mem.store_with_schema(
            task_id="flip_task",
            family="transform_induction",
            hypothesis={"execute": flip_fn, "strategy": "flipud"},
            execute_fn_name="static_portfolio",
            proof_obligations_met=["train_consistent", "loo_passed"],
        )

        stored = mem.get_by_family("transform_induction")
        assert len(stored) == 1
        hyp = stored[0]["hypothesis"]
        assert callable(hyp["execute"])

        from reasoning_project.adaptive_orchestrator import ModuleProposal
        proposal = ModuleProposal(
            module_name="operator_memory",
            proposal_type="stored_operator_schema",
            operator_family="transform_induction",
            selector=None,
            hypothesis=hyp,
            confidence=0.55,
            evidence={},
        )

        verifier = ProposalVerifier()
        outcome = verifier.verify(proposal, train_pairs, [inp1])
        assert outcome.accepted
        assert outcome.train_consistent
        assert outcome.loo_passed
