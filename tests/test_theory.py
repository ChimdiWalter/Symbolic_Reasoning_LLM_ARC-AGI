"""Tests for the four portfolio-architecture theorems in theory.py.

Uses simple synthetic solvers and small grids to verify the Monotone Diversity
Theorem, Consensus Correctness Bound, First-Hit Dominance, and Inductive
Soundness of the structural property language.
"""
from __future__ import annotations

import numpy as np
import pytest

from reasoning_project.theory import (
    Portfolio,
    Solver,
    SolveResult,
    Task,
    compute_consensus_bound,
    verify_first_hit_dominance,
    verify_inductive_soundness,
    verify_monotone_diversity,
)


# ---------------------------------------------------------------------------
# Synthetic solver factories
# ---------------------------------------------------------------------------

def _make_identity_solver(name: str = "identity"):
    """Solver that returns the input unchanged (correct for identity tasks)."""

    def fn(train_pairs, test_inputs):
        return [inp.copy() for inp in test_inputs], {"program": ["identity"]}

    return Solver(name=name, solve_fn=fn)


def _make_constant_solver(name: str, value: int = 0):
    """Solver that fills the output with a constant value."""

    def fn(train_pairs, test_inputs):
        preds = [np.full_like(inp, value) for inp in test_inputs]
        return preds, {"program": [f"fill_{value}"]}

    return Solver(name=name, solve_fn=fn)


def _make_none_solver(name: str = "noop"):
    """Solver that never produces output."""

    def fn(train_pairs, test_inputs):
        return None

    return Solver(name=name, solve_fn=fn)


def _make_flip_solver(name: str = "flip"):
    """Solver that flips the grid vertically."""

    def fn(train_pairs, test_inputs):
        return [np.flipud(inp) for inp in test_inputs], {"program": ["flipud"]}

    return Solver(name=name, solve_fn=fn)


def _make_correct_solver(name: str = "oracle"):
    """Solver that memorises ground-truth outputs from training pairs and
    returns the first training output for every test input (hack for
    testing -- only correct when train_output == test_output)."""

    def fn(train_pairs, test_inputs):
        if not train_pairs:
            return None
        # Return the first training output for every test input -- the tests
        # below craft tasks where this is correct.
        preds = [train_pairs[0][1].copy() for _ in test_inputs]
        return preds, {"program": ["oracle_lookup"]}

    return Solver(name=name, solve_fn=fn)


# ---------------------------------------------------------------------------
# Task fixtures
# ---------------------------------------------------------------------------

def _identity_task(task_id: str = "identity_0", size: int = 3, seed: int = 0):
    """Task where the output == input."""
    rng = np.random.RandomState(seed)
    grid = rng.randint(0, 10, (size, size))
    return Task(
        task_id=task_id,
        train_pairs=[(grid.copy(), grid.copy())],
        test_inputs=[grid.copy()],
        test_outputs=[grid.copy()],
    )


def _fill_task(task_id: str = "fill_0", size: int = 3, value: int = 7):
    """Task where the correct output is a grid filled with *value*."""
    inp = np.zeros((size, size), dtype=int)
    out = np.full((size, size), value, dtype=int)
    return Task(
        task_id=task_id,
        train_pairs=[(inp.copy(), out.copy())],
        test_inputs=[inp.copy()],
        test_outputs=[out.copy()],
    )


def _flip_task(task_id: str = "flip_0", size: int = 3, seed: int = 42):
    """Task where the output is the vertically-flipped input."""
    rng = np.random.RandomState(seed)
    inp = rng.randint(0, 10, (size, size))
    out = np.flipud(inp)
    return Task(
        task_id=task_id,
        train_pairs=[(inp.copy(), out.copy())],
        test_inputs=[inp.copy()],
        test_outputs=[out.copy()],
    )


# ---------------------------------------------------------------------------
# Theorem 1 -- Monotone Diversity
# ---------------------------------------------------------------------------

class TestMonotoneDiversity:
    """Empirical verification of the Monotone Diversity Theorem."""

    def test_adding_irrelevant_solver_preserves_solve_set(self):
        """A solver that never produces output cannot hurt."""
        base = Portfolio(solvers=[_make_identity_solver()], mode="collect_all")
        noop = _make_none_solver("noop")
        tasks = [_identity_task(f"id_{i}", seed=i) for i in range(5)]

        result = verify_monotone_diversity(base, noop, tasks)
        assert result["passed"]
        assert result["base_solved"] == result["augmented_solved"]

    def test_adding_correct_solver_expands_solve_set(self):
        """A solver that solves new tasks must enlarge the solve set."""
        # Base: noop solver (produces nothing). Cannot solve any task.
        base = Portfolio(solvers=[_make_none_solver("noop")], mode="collect_all")
        fill7 = _make_constant_solver("fill7", value=7)
        tasks = [
            _fill_task("fill_0", value=7),
            _fill_task("fill_1", value=7),
        ]

        result = verify_monotone_diversity(base, fill7, tasks)
        assert result["passed"]
        assert "fill_0" in result["new_solves"]
        assert "fill_1" in result["new_solves"]
        assert len(result["base_solved"]) == 0

    def test_adding_wrong_solver_does_not_remove_solves(self):
        """A solver that always gives wrong answers must not hurt."""
        base = Portfolio(solvers=[_make_identity_solver()], mode="collect_all")
        wrong = _make_constant_solver("wrong", value=99)
        tasks = [_identity_task(f"id_{i}", seed=i) for i in range(4)]

        result = verify_monotone_diversity(base, wrong, tasks)
        assert result["passed"]
        assert result["base_solved"] == result["augmented_solved"]

    def test_rejects_first_hit_mode(self):
        """Monotone diversity requires collect_all mode."""
        base = Portfolio(solvers=[], mode="first_hit")
        with pytest.raises(ValueError, match="collect_all"):
            verify_monotone_diversity(base, _make_none_solver(), [])

    def test_multiple_additions_are_monotone(self):
        """Adding solvers one-by-one should yield a non-decreasing solve set."""
        tasks = [
            _identity_task("id_0"),
            _flip_task("flip_0"),
            _fill_task("fill_0", value=7),
        ]
        p0 = Portfolio(solvers=[], mode="collect_all")
        solvers_to_add = [
            _make_identity_solver(),
            _make_flip_solver(),
            _make_constant_solver("fill7", value=7),
        ]
        prev_solved: set = set()
        for s in solvers_to_add:
            result = verify_monotone_diversity(p0, s, tasks)
            assert result["passed"]
            assert result["augmented_solved"] >= prev_solved
            prev_solved = result["augmented_solved"]
            p0 = p0.add(s)


# ---------------------------------------------------------------------------
# Theorem 2 -- Consensus Correctness Bound
# ---------------------------------------------------------------------------

class TestConsensusCorrectnessBound:
    """Tests for the consensus false-agreement probability bound."""

    def test_single_solver(self):
        """k=1: bound equals the raw false-positive rate."""
        result = compute_consensus_bound(1, [0.1])
        assert abs(result["product_bound"] - 0.1) < 1e-12

    def test_uniform_two_solvers(self):
        """k=2, uniform eps=0.1: bound = 0.01."""
        result = compute_consensus_bound(2, [0.1])
        assert abs(result["product_bound"] - 0.01) < 1e-12

    def test_uniform_three_solvers(self):
        """k=3, uniform eps=0.1: bound = 0.001."""
        result = compute_consensus_bound(3, [0.1])
        assert abs(result["product_bound"] - 0.001) < 1e-12

    def test_heterogeneous_rates(self):
        """Different fp rates are multiplied together."""
        result = compute_consensus_bound(3, [0.1, 0.2, 0.5])
        expected = 0.1 * 0.2 * 0.5
        assert abs(result["product_bound"] - expected) < 1e-12

    def test_exponential_decay(self):
        """Bound decreases exponentially as k grows (uniform eps)."""
        eps = 0.1
        bounds = []
        for k in range(1, 8):
            result = compute_consensus_bound(k, [eps])
            bounds.append(result["product_bound"])
        for i in range(1, len(bounds)):
            assert bounds[i] < bounds[i - 1]
            ratio = bounds[i] / bounds[i - 1]
            assert abs(ratio - eps) < 1e-12

    def test_rate_extension(self):
        """When fp_rates is shorter than k, last rate is repeated."""
        result = compute_consensus_bound(4, [0.1, 0.2])
        # rates become [0.1, 0.2, 0.2, 0.2]
        expected = 0.1 * 0.2 * 0.2 * 0.2
        assert abs(result["product_bound"] - expected) < 1e-12

    def test_invalid_agreement_count(self):
        with pytest.raises(ValueError):
            compute_consensus_bound(0, [0.1])

    def test_empty_fp_rates(self):
        with pytest.raises(ValueError):
            compute_consensus_bound(2, [])

    def test_perfect_solvers(self):
        """fp_rate = 0 -> bound = 0 for k >= 1."""
        result = compute_consensus_bound(5, [0.0])
        assert result["product_bound"] == 0.0

    def test_uniform_bound_matches_product_for_uniform_rates(self):
        """When all rates are equal, uniform_bound == product_bound."""
        result = compute_consensus_bound(4, [0.15, 0.15, 0.15, 0.15])
        assert abs(result["uniform_bound"] - result["product_bound"]) < 1e-12


# ---------------------------------------------------------------------------
# Theorem 3 -- First-Hit Dominance
# ---------------------------------------------------------------------------

class TestFirstHitDominance:
    """Verify that collect-all always solves a superset of first-hit."""

    def test_single_correct_solver(self):
        """With one solver, both modes solve the same tasks."""
        solvers = [_make_identity_solver()]
        tasks = [_identity_task(f"id_{i}", seed=i) for i in range(3)]
        result = verify_first_hit_dominance(solvers, tasks)
        assert result["passed"]
        assert result["first_hit_solved"] == result["collect_all_solved"]

    def test_first_hit_picks_wrong_solver_first(self):
        """First-hit may fail when the first solver is wrong, but
        collect-all can still succeed when multiple correct solvers
        outvote the wrong one via consensus."""
        # Order: wrong solver first, then two correct solvers that agree.
        # In first-hit mode, `wrong` produces non-None output and is
        # accepted immediately (incorrectly).
        # In collect-all mode, `identity_a` and `identity_b` both produce
        # the correct output -- 2 agreeing solvers beat `wrong` (1 agreeing).
        wrong = _make_constant_solver("wrong", value=99)
        correct_a = _make_identity_solver("identity_a")
        correct_b = _make_identity_solver("identity_b")
        solvers = [wrong, correct_a, correct_b]
        tasks = [_identity_task("id_0")]

        result = verify_first_hit_dominance(solvers, tasks)
        assert result["passed"]
        # First-hit takes `wrong`'s output (non-None but incorrect).
        assert "id_0" not in result["first_hit_solved"]
        # Collect-all sees 2 votes for the correct answer vs 1 for wrong.
        assert "id_0" in result["collect_all_solved"]
        assert "id_0" in result["advantage"]

    def test_collect_all_superset_multi_task(self):
        """On a mixed task suite, collect_all >= first_hit."""
        # Two identity solvers to outvote `wrong` via consensus on
        # identity tasks; two flip solvers for flip tasks.
        wrong = _make_constant_solver("wrong", value=99)
        identity_a = _make_identity_solver("identity_a")
        identity_b = _make_identity_solver("identity_b")
        flip_a = _make_flip_solver("flip_a")
        flip_b = _make_flip_solver("flip_b")

        solvers = [wrong, identity_a, identity_b, flip_a, flip_b]
        tasks = [
            _identity_task("id_0"),
            _identity_task("id_1", seed=1),
            _flip_task("flip_0"),
        ]

        result = verify_first_hit_dominance(solvers, tasks)
        assert result["passed"]
        assert result["first_hit_solved"].issubset(result["collect_all_solved"])

    def test_all_noop_solvers(self):
        """When no solver produces output, both modes solve nothing."""
        solvers = [_make_none_solver("noop1"), _make_none_solver("noop2")]
        tasks = [_identity_task("id_0")]
        result = verify_first_hit_dominance(solvers, tasks)
        assert result["passed"]
        assert len(result["first_hit_solved"]) == 0
        assert len(result["collect_all_solved"]) == 0

    def test_empty_task_list(self):
        """Vacuously true on an empty task list."""
        solvers = [_make_identity_solver()]
        result = verify_first_hit_dominance(solvers, [])
        assert result["passed"]
        assert result["advantage"] == set()


# ---------------------------------------------------------------------------
# Integration: all three theorems on the same task suite
# ---------------------------------------------------------------------------

class TestIntegrated:
    """Run all three theorems on a shared task suite."""

    @pytest.fixture
    def suite(self):
        return [
            _identity_task("id_0", seed=0),
            _identity_task("id_1", seed=1),
            _flip_task("flip_0", seed=10),
            _flip_task("flip_1", seed=11),
            _fill_task("fill_0", value=5),
        ]

    def test_all_theorems_hold(self, suite):
        identity = _make_identity_solver()
        flip = _make_flip_solver()
        fill5 = _make_constant_solver("fill5", value=5)
        noop = _make_none_solver()

        base = Portfolio(solvers=[identity, flip], mode="collect_all")

        # Theorem 1: add fill5
        r1 = verify_monotone_diversity(base, fill5, suite)
        assert r1["passed"], f"Monotone diversity failed: {r1}"

        # Theorem 1: add noop
        r1b = verify_monotone_diversity(base, noop, suite)
        assert r1b["passed"], f"Monotone diversity failed for noop: {r1b}"

        # Theorem 2: bounds shrink with more agreement
        bounds = []
        for k in range(1, 6):
            r2 = compute_consensus_bound(k, [0.05])
            bounds.append(r2["product_bound"])
        for i in range(1, len(bounds)):
            assert bounds[i] < bounds[i - 1]

        # Theorem 3: collect_all >= first_hit
        all_solvers = [identity, flip, fill5, noop]
        r3 = verify_first_hit_dominance(all_solvers, suite)
        assert r3["passed"], f"First-hit dominance failed: {r3}"


# ---------------------------------------------------------------------------
# Theorem 4 -- Inductive Soundness
# ---------------------------------------------------------------------------

def _make_filter_task(task_id: str) -> Task:
    """Create a task where the rule is 'keep largest object, remove others'.

    Input: 3+ objects of different sizes on a grid. Output: only the largest remains.
    Requires 3 training pairs for the reasoning engine.
    """
    pairs = []
    for seed in range(3):
        rng = np.random.RandomState(seed + 100)
        grid = np.zeros((10, 10), dtype=int)
        sizes = [6, 3, 2]
        positions = [(0, 0), (0, 7), (7, 0)]
        for i, (sz, (r, c)) in enumerate(zip(sizes, positions)):
            color = rng.randint(1, 6)
            for dr in range(sz):
                for dc in range(1):
                    if r + dr < 10 and c + dc < 10:
                        grid[r + dr, c + dc] = color
        out = np.zeros_like(grid)
        mask = grid != 0
        from scipy import ndimage
        labeled, n = ndimage.label(mask)
        best_lab = 0
        best_size = 0
        for lab in range(1, n + 1):
            s = int(np.sum(labeled == lab))
            if s > best_size:
                best_size = s
                best_lab = lab
        if best_lab > 0:
            out[labeled == best_lab] = grid[labeled == best_lab]
        pairs.append((grid, out))

    return Task(
        task_id=task_id,
        train_pairs=pairs,
        test_inputs=[pairs[0][0].copy()],
        test_outputs=[pairs[0][1].copy()],
    )


def _make_recolor_task(task_id: str) -> Task:
    """Create a task where hole-bearing objects get color 3, solid ones get color 1."""
    pairs = []
    for seed in range(3):
        grid = np.zeros((8, 12), dtype=int)
        grid[0:3, 0:3] = 5
        grid[1, 1] = 0
        grid[0:2, 5:7] = 5
        out = grid.copy()
        from scipy import ndimage
        mask = grid != 0
        labeled, n = ndimage.label(mask)
        for lab in range(1, n + 1):
            obj_mask = labeled == lab
            local = obj_mask[np.ix_(np.any(obj_mask, axis=1), np.any(obj_mask, axis=0))]
            _, n_holes = ndimage.label(~local)
            interior_holes = n_holes - 1
            if interior_holes > 0:
                out[obj_mask] = 3
            else:
                out[obj_mask] = 1
        pairs.append((grid, out))

    return Task(
        task_id=task_id,
        train_pairs=pairs,
        test_inputs=[pairs[0][0].copy()],
        test_outputs=[pairs[0][1].copy()],
    )


class TestInductiveSoundness:

    def test_soundness_on_synthetic_filter(self):
        task = _make_filter_task("synth_filter")
        result = verify_inductive_soundness([task])
        assert result["passed"], f"Soundness failed: {result}"
        assert result["training_violations"] == 0
        assert result["loo_violations"] == 0

    def test_soundness_on_synthetic_recolor(self):
        task = _make_recolor_task("synth_recolor")
        result = verify_inductive_soundness([task])
        assert result["passed"], f"Soundness failed: {result}"
        assert result["training_violations"] == 0
        assert result["loo_violations"] == 0

    def test_soundness_on_empty_tasks(self):
        result = verify_inductive_soundness([])
        assert result["passed"]
        assert result["tasks_tested"] == 0
        assert result["hypotheses_emitted"] == 0

    def test_soundness_on_unsolvable_task(self):
        rng = np.random.RandomState(42)
        pairs = [(rng.randint(0, 5, (5, 5)), rng.randint(0, 5, (5, 5)))
                 for _ in range(3)]
        task = Task(
            task_id="random",
            train_pairs=pairs,
            test_inputs=[pairs[0][0].copy()],
            test_outputs=[pairs[0][1].copy()],
        )
        result = verify_inductive_soundness([task])
        assert result["passed"]
        assert result["hypotheses_emitted"] == 0
