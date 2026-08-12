"""Tests for formal verification infrastructure."""
from __future__ import annotations

import numpy as np
import pytest

from reasoning_project.formal_verification import (
    Always,
    And,
    Atomic,
    ConvergenceBound,
    DecisionProcedure,
    Eventually,
    Implies,
    LTLFormula,
    LTLModelChecker,
    Next,
    Not,
    Or,
    Postcondition,
    Precondition,
    ProofObject,
    ProofStatus,
    ProofStep,
    TerminationProof,
    Until,
    build_trace_from_loop_result,
    make_mismatch_decision_procedure,
    prove_inductive_soundness,
    prove_monotone_diversity,
    reasoning_loop_specifications,
)

# Try to import LoopResult-related imports but skip if not available
try:
    from reasoning_project.manifold_memory import (
        ManifoldPoint,
        MemoryManifold,
        FiberBundle,
    )
    HAS_MANIFOLD = True
except ImportError:
    HAS_MANIFOLD = False


# ---------------------------------------------------------------------------
# 1. PROOF OBJECTS
# ---------------------------------------------------------------------------

class TestProofObject:
    def test_valid_proof(self):
        proof = ProofObject(
            name="test",
            axioms=["A", "B"],
            steps=[
                ProofStep(rule="modus_ponens", premises=["A", "B"], conclusion="C"),
            ],
            conclusion="C",
        )
        assert proof.verify() == ProofStatus.VALID

    def test_invalid_proof_missing_premise(self):
        proof = ProofObject(
            name="test",
            axioms=["A"],
            steps=[
                ProofStep(rule="modus_ponens", premises=["A", "B"], conclusion="C"),
            ],
            conclusion="C",
        )
        assert proof.verify() == ProofStatus.INVALID

    def test_invalid_proof_wrong_conclusion(self):
        proof = ProofObject(
            name="test",
            axioms=["A"],
            steps=[
                ProofStep(rule="intro", premises=["A"], conclusion="B"),
            ],
            conclusion="C",
        )
        assert proof.verify() == ProofStatus.INVALID

    def test_multi_step_proof(self):
        proof = ProofObject(
            name="chain",
            axioms=["A"],
            steps=[
                ProofStep(rule="step1", premises=["A"], conclusion="B"),
                ProofStep(rule="step2", premises=["B"], conclusion="C"),
                ProofStep(rule="step3", premises=["A", "C"], conclusion="D"),
            ],
            conclusion="D",
        )
        assert proof.verify() == ProofStatus.VALID

    def test_inductive_soundness_proof(self):
        proof = prove_inductive_soundness()
        assert proof.verify() == ProofStatus.VALID
        assert proof.name == "Inductive Soundness (Theorem 4)"

    def test_monotone_diversity_proof(self):
        proof = prove_monotone_diversity()
        assert proof.verify() == ProofStatus.VALID
        assert proof.name == "Monotone Diversity (Theorem 1)"


# ---------------------------------------------------------------------------
# 2. TERMINATION PROOFS
# ---------------------------------------------------------------------------

class TestTerminationProof:
    def test_ranking_function(self):
        tp = TerminationProof(max_iterations=8, n_views=4, timeout_seconds=60.0)
        rank = tp.ranking_function(0, 4)
        assert rank == (8, 4)
        rank = tp.ranking_function(3, 2)
        assert rank == (5, 2)

    def test_verify_decrease(self):
        tp = TerminationProof(max_iterations=8, n_views=4, timeout_seconds=60.0)
        assert tp.verify_decrease((8, 4), (7, 4))
        assert tp.verify_decrease((8, 4), (8, 3))
        assert not tp.verify_decrease((7, 4), (8, 4))
        assert not tp.verify_decrease((7, 3), (7, 3))

    def test_well_founded(self):
        tp = TerminationProof(max_iterations=8, n_views=4, timeout_seconds=60.0)
        result = tp.verify_well_founded()
        assert result["well_founded"] is True
        assert result["bounded_below"] is True
        assert result["all_steps_decrease"] is True
        assert result["upper_bound_iterations"] == 8
        assert result["ranking_domain"] == "ℕ × ℕ (lexicographic)"

    def test_verify_on_trace(self):
        tp = TerminationProof(max_iterations=8, n_views=4, timeout_seconds=60.0)
        trace = [
            {"iteration": 0, "untried_views": 4},
            {"iteration": 1, "untried_views": 3},
            {"iteration": 2, "untried_views": 2},
            {"iteration": 3, "untried_views": 1},
        ]
        result = tp.verify_on_trace(trace)
        assert result["passed"] is True
        assert result["terminated"] is True

    def test_verify_on_bad_trace(self):
        tp = TerminationProof(max_iterations=8, n_views=4, timeout_seconds=60.0)
        trace = [
            {"iteration": 0, "untried_views": 4},
            {"iteration": 0, "untried_views": 4},
        ]
        result = tp.verify_on_trace(trace)
        assert result["passed"] is False
        assert len(result["violations"]) > 0


# ---------------------------------------------------------------------------
# 3. CONVERGENCE BOUNDS
# ---------------------------------------------------------------------------

class TestConvergenceBound:
    def test_max_step_size(self):
        cb = ConvergenceBound(lipschitz_L=10.0)
        assert cb.max_step_size() == pytest.approx(0.1)

    def test_sublinear_rate(self):
        cb = ConvergenceBound(lipschitz_L=10.0)
        assert cb.convergence_rate() == "sublinear O(1/T)"

    def test_linear_rate(self):
        cb = ConvergenceBound(lipschitz_L=10.0, strong_convexity_mu=1.0)
        assert cb.convergence_rate() == "linear (exponential)"

    def test_steps_to_epsilon_sublinear(self):
        cb = ConvergenceBound(lipschitz_L=10.0, step_size=0.1)
        T = cb.steps_to_epsilon(initial_distance=1.0, epsilon=0.01)
        assert T > 0
        assert isinstance(T, int)

    def test_steps_to_epsilon_linear(self):
        cb = ConvergenceBound(lipschitz_L=10.0, strong_convexity_mu=1.0, step_size=0.1)
        T = cb.steps_to_epsilon(initial_distance=1.0, epsilon=0.01)
        assert T > 0

    def test_certificate(self):
        cb = ConvergenceBound(lipschitz_L=10.0, step_size=0.1)
        cert = cb.certificate(T=100, initial_distance=5.0)
        assert cert["T"] == 100
        assert cert["initial_distance"] == 5.0
        assert cert["final_energy_bound"] > 0
        assert cert["convergence_rate"] == "sublinear O(1/T)"

    def test_verify_decreasing_energies(self):
        cb = ConvergenceBound(lipschitz_L=1.0, step_size=0.5)
        energies = [10.0, 5.0, 2.5, 1.25, 0.625]
        result = cb.verify_on_trajectory(energies, initial_distance=10.0)
        assert result["step_size_valid"] is True

    def test_linear_convergence_faster(self):
        cb_sub = ConvergenceBound(lipschitz_L=10.0, step_size=0.1)
        cb_lin = ConvergenceBound(lipschitz_L=10.0, strong_convexity_mu=1.0, step_size=0.1)
        T_sub = cb_sub.steps_to_epsilon(1.0, 0.001)
        T_lin = cb_lin.steps_to_epsilon(1.0, 0.001)
        assert T_lin < T_sub


# ---------------------------------------------------------------------------
# 4. DECISION PROCEDURES
# ---------------------------------------------------------------------------

class TestDecisionProcedure:
    def test_all_preconditions_met(self):
        dp = DecisionProcedure(
            name="test",
            preconditions=[
                Precondition("is_positive", lambda x: x > 0, "x must be positive"),
            ],
            postconditions=[
                Postcondition("result_is_dict", lambda r: isinstance(r, dict), "must return dict"),
            ],
            procedure=lambda x: {"value": x * 2},
        )
        result = dp.execute(5)
        assert result["executed"] is True
        assert result["contract_satisfied"] is True
        assert result["result"]["value"] == 10

    def test_precondition_violated(self):
        dp = DecisionProcedure(
            name="test",
            preconditions=[
                Precondition("is_positive", lambda x: x > 0, "x must be positive"),
            ],
            postconditions=[],
            procedure=lambda x: x * 2,
        )
        result = dp.execute(-1)
        assert result["executed"] is False
        assert result["reason"] == "precondition_violated"

    def test_postcondition_violated(self):
        dp = DecisionProcedure(
            name="test",
            preconditions=[
                Precondition("always_true", lambda x: True, ""),
            ],
            postconditions=[
                Postcondition("is_positive", lambda r: r > 0, "result must be positive"),
            ],
            procedure=lambda x: -1,
        )
        result = dp.execute(5)
        assert result["executed"] is True
        assert result["contract_satisfied"] is False

    @pytest.mark.skipif(not HAS_MANIFOLD, reason="manifold_memory not available")
    def test_mismatch_decision_procedure(self):
        dp = make_mismatch_decision_procedure()
        m = MemoryManifold()
        rng = np.random.default_rng(42)
        for i in range(5):
            m.add_point(ManifoldPoint(
                embedding=rng.random(8),
                task_signature={"n_objects": i},
            ))
        query = ManifoldPoint(
            embedding=rng.random(8),
            task_signature={"n_objects": 3},
        )
        result = dp.execute(query, m)
        assert result["executed"] is True
        assert "triggered" in result["result"]
        assert result["contract_satisfied"] is True

    @pytest.mark.skipif(not HAS_MANIFOLD, reason="manifold_memory not available")
    def test_mismatch_dp_precondition_fail(self):
        dp = make_mismatch_decision_procedure()
        m = MemoryManifold()
        query = ManifoldPoint(
            embedding=np.zeros(8),
            task_signature={},
        )
        result = dp.execute(query, m)
        assert result["executed"] is False


# ---------------------------------------------------------------------------
# 5. TEMPORAL LOGIC MODEL CHECKING
# ---------------------------------------------------------------------------

class TestLTLFormulas:
    def test_atomic(self):
        checker = LTLModelChecker()
        f = Atomic("x", lambda s: s.get("x", False))
        assert checker.check(f, [{"x": True}])
        assert not checker.check(f, [{"x": False}])

    def test_not(self):
        checker = LTLModelChecker()
        f = Not(Atomic("x", lambda s: s.get("x", False)))
        assert not checker.check(f, [{"x": True}])
        assert checker.check(f, [{"x": False}])

    def test_and(self):
        checker = LTLModelChecker()
        f = And(
            Atomic("x", lambda s: s["x"]),
            Atomic("y", lambda s: s["y"]),
        )
        assert checker.check(f, [{"x": True, "y": True}])
        assert not checker.check(f, [{"x": True, "y": False}])

    def test_or(self):
        checker = LTLModelChecker()
        f = Or(
            Atomic("x", lambda s: s["x"]),
            Atomic("y", lambda s: s["y"]),
        )
        assert checker.check(f, [{"x": False, "y": True}])
        assert not checker.check(f, [{"x": False, "y": False}])

    def test_implies(self):
        checker = LTLModelChecker()
        f = Implies(
            Atomic("x", lambda s: s["x"]),
            Atomic("y", lambda s: s["y"]),
        )
        assert checker.check(f, [{"x": True, "y": True}])
        assert checker.check(f, [{"x": False, "y": False}])
        assert not checker.check(f, [{"x": True, "y": False}])

    def test_always(self):
        checker = LTLModelChecker()
        f = Always(Atomic("safe", lambda s: s["safe"]))
        trace = [{"safe": True}, {"safe": True}, {"safe": True}]
        assert checker.check(f, trace)
        trace_bad = [{"safe": True}, {"safe": False}, {"safe": True}]
        assert not checker.check(f, trace_bad)

    def test_eventually(self):
        checker = LTLModelChecker()
        f = Eventually(Atomic("done", lambda s: s["done"]))
        trace = [{"done": False}, {"done": False}, {"done": True}]
        assert checker.check(f, trace)
        trace_never = [{"done": False}, {"done": False}]
        assert not checker.check(f, trace_never)

    def test_until(self):
        checker = LTLModelChecker()
        f = Until(
            Atomic("running", lambda s: s["running"]),
            Atomic("done", lambda s: s["done"]),
        )
        trace = [
            {"running": True, "done": False},
            {"running": True, "done": False},
            {"running": False, "done": True},
        ]
        assert checker.check(f, trace)

        trace_broken = [
            {"running": True, "done": False},
            {"running": False, "done": False},
        ]
        assert not checker.check(f, trace_broken)

    def test_next(self):
        checker = LTLModelChecker()
        f = Next(Atomic("x", lambda s: s["x"]))
        assert checker.check(f, [{"x": False}, {"x": True}])
        assert not checker.check(f, [{"x": True}])

    def test_empty_trace(self):
        checker = LTLModelChecker()
        f = Atomic("x", lambda s: True)
        assert not checker.check(f, [])


class TestReasoningLoopSpecs:
    def test_specifications_exist(self):
        specs = reasoning_loop_specifications()
        assert "always_sound" in specs
        assert "eventually_terminates" in specs
        assert "progress_until_solved" in specs
        assert "solution_stability" in specs
        assert "within_budget" in specs

    def test_sound_solving_trace(self):
        checker = LTLModelChecker()
        specs = reasoning_loop_specifications()
        trace = [
            {"solved": False, "terminated": False, "false_positive": False,
             "progress": True, "new_view_tried": True, "iteration": 0, "max_iterations": 8},
            {"solved": False, "terminated": False, "false_positive": False,
             "progress": True, "new_view_tried": True, "iteration": 1, "max_iterations": 8},
            {"solved": True, "terminated": True, "false_positive": False,
             "progress": True, "new_view_tried": True, "iteration": 2, "max_iterations": 8},
        ]
        results = checker.check_all(specs, trace)
        assert results["always_sound"] is True
        assert results["eventually_terminates"] is True
        assert results["within_budget"] is True

    def test_unsound_trace_detected(self):
        checker = LTLModelChecker()
        specs = reasoning_loop_specifications()
        trace = [
            {"solved": False, "terminated": False, "false_positive": True,
             "progress": True, "new_view_tried": True, "iteration": 0, "max_iterations": 8},
            {"solved": True, "terminated": True, "false_positive": False,
             "progress": True, "new_view_tried": True, "iteration": 1, "max_iterations": 8},
        ]
        results = checker.check_all(specs, trace)
        assert results["always_sound"] is False

    def test_check_all_returns_dict(self):
        checker = LTLModelChecker()
        specs = reasoning_loop_specifications()
        trace = [{"solved": False, "terminated": True, "false_positive": False,
                   "progress": False, "new_view_tried": False,
                   "iteration": 0, "max_iterations": 8}]
        results = checker.check_all(specs, trace)
        assert isinstance(results, dict)
        assert all(isinstance(v, bool) for v in results.values())


class TestBuildTrace:
    def test_from_mock_loop_result(self):
        class MockResult:
            solved = True
            views_tried = ["color_cc", "per_color", "monochrome"]
            diagnosis_trace = []
        result = MockResult()
        trace = build_trace_from_loop_result(result)
        assert len(trace) == 3
        assert trace[-1]["solved"] is True
        assert trace[-1]["terminated"] is True
        assert trace[0]["solved"] is False

    def test_empty_result(self):
        class MockResult:
            solved = False
            views_tried = []
            diagnosis_trace = []
        trace = build_trace_from_loop_result(MockResult())
        assert len(trace) == 1
        assert trace[0]["terminated"] is True
