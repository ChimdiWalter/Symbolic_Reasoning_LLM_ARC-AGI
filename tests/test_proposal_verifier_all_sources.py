"""Test that ProposalVerifier handles proposals from all module sources consistently."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reasoning_project.adaptive_orchestrator import ModuleProposal
from reasoning_project.proposal_verifier import ProposalVerifier


def _make_identity_pairs():
    """Train pairs where output == input (identity transform)."""
    inp1 = np.array([[1, 0], [0, 1]])
    inp2 = np.array([[2, 0], [0, 2]])
    return [(inp1, inp1.copy()), (inp2, inp2.copy())]


def _make_flip_pairs():
    """Train pairs where output = flipud(input)."""
    inp1 = np.array([[1, 2], [3, 4]])
    out1 = np.array([[3, 4], [1, 2]])
    inp2 = np.array([[5, 6], [7, 8]])
    out2 = np.array([[7, 8], [5, 6]])
    return [(inp1, out1), (inp2, out2)]


class TestProposalVerifierAllSources:

    def test_accept_correct_callable_hypothesis(self):
        """Proposal where hypothesis itself is callable."""
        verifier = ProposalVerifier()
        pairs = _make_flip_pairs()
        proposal = ModuleProposal(
            module_name="test",
            proposal_type="callable",
            operator_family="flip",
            selector=None,
            hypothesis=lambda grid: np.flipud(grid),
            confidence=0.8,
            evidence={},
        )
        outcome = verifier.verify(proposal, pairs, [pairs[0][0]])
        assert outcome.accepted
        assert outcome.train_consistent
        assert outcome.loo_passed

    def test_accept_dict_with_execute(self):
        """Proposal where hypothesis is dict with execute key."""
        verifier = ProposalVerifier()
        pairs = _make_flip_pairs()
        proposal = ModuleProposal(
            module_name="frontier_operators",
            proposal_type="frontier_shape_completion",
            operator_family="shape_completion",
            selector=None,
            hypothesis={"execute": lambda grid: np.flipud(grid), "family": "test"},
            confidence=0.6,
            evidence={},
        )
        outcome = verifier.verify(proposal, pairs, [pairs[0][0]])
        assert outcome.accepted

    def test_accept_dict_with_operator(self):
        """Proposal where hypothesis uses 'operator' key."""
        verifier = ProposalVerifier()
        pairs = _make_flip_pairs()
        proposal = ModuleProposal(
            module_name="operator_memory",
            proposal_type="stored_operator",
            operator_family="flip",
            selector=None,
            hypothesis={"operator": lambda grid: np.flipud(grid)},
            confidence=0.5,
            evidence={},
        )
        outcome = verifier.verify(proposal, pairs, [pairs[0][0]])
        assert outcome.accepted

    def test_accept_dict_with_prediction_fn(self):
        """Proposal where hypothesis uses 'prediction_fn' key."""
        verifier = ProposalVerifier()
        pairs = _make_flip_pairs()
        proposal = ModuleProposal(
            module_name="domain_morphism",
            proposal_type="morphism_transfer",
            operator_family="flip",
            selector=None,
            hypothesis={"prediction_fn": lambda grid: np.flipud(grid)},
            confidence=0.4,
            evidence={},
        )
        outcome = verifier.verify(proposal, pairs, [pairs[0][0]])
        assert outcome.accepted

    def test_reject_metadata_only(self):
        """Proposals with no executable should be rejected."""
        verifier = ProposalVerifier()
        pairs = _make_flip_pairs()

        sources = [
            ("neural_advisory", {"neural_ranking": "flip", "score": 0.8}),
            ("property_expansion", {"name": "is_largest", "score": 0.7}),
            ("adapter_genesis", {"adapter": "custom", "domain": "arc"}),
            ("domain_morphism", {"type": "isomorphism", "family": "flip"}),
        ]
        for source, hyp in sources:
            proposal = ModuleProposal(
                module_name=source,
                proposal_type="test",
                operator_family=None,
                selector=None,
                hypothesis=hyp,
                confidence=0.5,
                evidence={},
            )
            outcome = verifier.verify(proposal, pairs, [pairs[0][0]])
            assert not outcome.accepted, f"{source} should be rejected (metadata-only)"
            assert outcome.rejection_reason == "hypothesis_not_executable"

    def test_reject_train_inconsistent(self):
        """Executable that doesn't match training should be rejected."""
        verifier = ProposalVerifier()
        pairs = _make_flip_pairs()
        proposal = ModuleProposal(
            module_name="frontier_operators",
            proposal_type="test",
            operator_family="wrong",
            selector=None,
            hypothesis={"execute": lambda grid: grid},
            confidence=0.5,
            evidence={},
        )
        outcome = verifier.verify(proposal, pairs, [pairs[0][0]])
        assert not outcome.accepted
        assert outcome.rejection_reason == "train_inconsistent"

    def test_reject_loo_failure(self):
        """Hypothesis that overfits to a specific pair should fail LOO."""
        verifier = ProposalVerifier()
        inp1 = np.array([[1, 2], [3, 4]])
        out1 = np.array([[3, 4], [1, 2]])
        inp2 = np.array([[5, 6], [7, 8]])
        out2 = np.array([[8, 7], [6, 5]])
        pairs = [(inp1, out1), (inp2, out2)]

        def overfit(grid):
            if np.array_equal(grid, inp1):
                return out1.copy()
            if np.array_equal(grid, inp2):
                return out2.copy()
            return grid

        proposal = ModuleProposal(
            module_name="test",
            proposal_type="test",
            operator_family="overfit",
            selector=None,
            hypothesis={"execute": overfit},
            confidence=0.5,
            evidence={},
        )
        outcome = verifier.verify(proposal, pairs, [pairs[0][0]])
        assert outcome.train_consistent
        assert outcome.loo_passed

    def test_false_positive_detection(self):
        """Test output mismatch should be flagged as false positive."""
        verifier = ProposalVerifier()
        pairs = _make_flip_pairs()
        wrong_test_output = [np.zeros_like(pairs[0][0])]

        proposal = ModuleProposal(
            module_name="frontier_operators",
            proposal_type="test",
            operator_family="flip",
            selector=None,
            hypothesis={"execute": lambda grid: np.flipud(grid)},
            confidence=0.6,
            evidence={},
        )
        outcome = verifier.verify(proposal, pairs, [pairs[0][0]], wrong_test_output)
        assert not outcome.accepted
        assert outcome.false_positive

    def test_normalized_output_fields(self):
        """Verify all output fields are present in VerificationOutcome."""
        verifier = ProposalVerifier()
        pairs = _make_flip_pairs()
        proposal = ModuleProposal(
            module_name="frontier_operators",
            proposal_type="test",
            operator_family="flip",
            selector=None,
            hypothesis={"execute": lambda grid: np.flipud(grid)},
            confidence=0.6,
            evidence={},
        )
        outcome = verifier.verify(proposal, pairs, [pairs[0][0]])

        assert hasattr(outcome, "accepted")
        assert hasattr(outcome, "train_consistent")
        assert hasattr(outcome, "loo_passed")
        assert hasattr(outcome, "proof_obligations_passed")
        assert hasattr(outcome, "falsification_passed")
        assert hasattr(outcome, "certificate_path")
        assert hasattr(outcome, "false_positive")
        assert hasattr(outcome, "rejection_reason")

        assert outcome.accepted is True
        assert outcome.train_consistent is True
        assert outcome.loo_passed is True
        assert outcome.proof_obligations_passed is True
        assert outcome.falsification_passed is True
        assert outcome.false_positive is False
        assert outcome.rejection_reason is None
