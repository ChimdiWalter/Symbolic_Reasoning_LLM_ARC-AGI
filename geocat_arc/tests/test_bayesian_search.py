"""Tests for Bayesian program search."""
import numpy as np
import pytest
from geocat_arc.bayesian_program_search.bayes_ranker import BayesianLinearRanker
from geocat_arc.bayesian_program_search.acquisition import ucb, expected_improvement, thompson_sample
from geocat_arc.bayesian_program_search.real_objective import normalized_cell_accuracy, exact_match
from geocat_arc.bayesian_program_search.program_features import extract_features, feature_dim


class TestBayesianRanker:
    def test_initial_prediction(self):
        ranker = BayesianLinearRanker(feature_dim=5)
        feat = np.ones(5)
        mean, var = ranker.predict(feat)
        assert var > 0

    def test_update_changes_posterior(self):
        ranker = BayesianLinearRanker(feature_dim=5)
        feat = np.ones(5)
        m1, v1 = ranker.predict(feat)
        ranker.update(feat, 1.0)
        m2, v2 = ranker.predict(feat)
        assert v2 < v1

    def test_ranking_changes_after_observations(self):
        ranker = BayesianLinearRanker(feature_dim=3)
        feat_a = np.array([1.0, 0.0, 0.0])
        feat_b = np.array([0.0, 1.0, 0.0])

        ranker.update(feat_a, 2.0)
        ranker.update(feat_b, 0.1)

        ranking = ranker.rank_candidates([feat_a, feat_b], kappa=0.1)
        assert ranking[0] == 0

    def test_n_observations(self):
        ranker = BayesianLinearRanker(feature_dim=3)
        assert ranker.n_observations == 0
        ranker.update(np.ones(3), 1.0)
        assert ranker.n_observations == 1


class TestAcquisition:
    def test_ucb(self):
        assert ucb(1.0, 0.5, kappa=2.0) > 1.0

    def test_expected_improvement(self):
        ei = expected_improvement(1.5, 0.5, best_so_far=1.0)
        assert ei > 0

    def test_thompson_sample_differs(self):
        rng = np.random.default_rng(42)
        samples = [thompson_sample(0.0, 1.0, rng) for _ in range(10)]
        assert len(set(samples)) > 1


class TestRealObjective:
    def test_identical_grids(self):
        grid = [[1, 2], [3, 4]]
        assert normalized_cell_accuracy(grid, grid) == 1.0

    def test_completely_different(self):
        pred = [[0, 0], [0, 0]]
        target = [[1, 1], [1, 1]]
        assert normalized_cell_accuracy(pred, target) == 0.0

    def test_partial_match(self):
        pred = [[1, 0], [0, 0]]
        target = [[1, 1], [1, 1]]
        acc = normalized_cell_accuracy(pred, target)
        assert 0.0 < acc < 1.0

    def test_exact_match(self):
        grid = [[1, 2], [3, 4]]
        assert exact_match(grid, grid)
        assert not exact_match(grid, [[0, 0], [0, 0]])

    def test_different_shapes(self):
        pred = [[1, 2, 3]]
        target = [[1, 2]]
        acc = normalized_cell_accuracy(pred, target)
        assert 0.0 <= acc <= 1.0
