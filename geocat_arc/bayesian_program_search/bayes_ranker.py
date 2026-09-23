"""Bayesian linear regression ranker for candidate programs."""
from __future__ import annotations
import numpy as np
from .acquisition import ucb


class BayesianLinearRanker:
    def __init__(self, feature_dim: int, alpha: float = 1.0, beta: float = 1.0):
        self.feature_dim = feature_dim
        self.alpha = alpha
        self.beta = beta
        self.prior_precision = alpha * np.eye(feature_dim)
        self.posterior_precision = self.prior_precision.copy()
        self.posterior_mean_weighted = np.zeros(feature_dim)
        self._n_obs = 0

    @property
    def posterior_cov(self) -> np.ndarray:
        return np.linalg.inv(self.posterior_precision)

    @property
    def posterior_weights(self) -> np.ndarray:
        return self.posterior_cov @ self.posterior_mean_weighted

    def update(self, features: np.ndarray, score: float) -> None:
        x = features.reshape(-1)
        self.posterior_precision += self.beta * np.outer(x, x)
        self.posterior_mean_weighted += self.beta * score * x
        self._n_obs += 1

    def predict(self, features: np.ndarray) -> tuple[float, float]:
        x = features.reshape(-1)
        w = self.posterior_weights
        cov = self.posterior_cov
        mean = float(x @ w)
        variance = float(x @ cov @ x) + 1.0 / self.beta
        return mean, max(variance, 1e-12)

    def rank_candidates(
        self,
        candidate_features: list[np.ndarray],
        kappa: float = 2.0,
    ) -> list[int]:
        scores = []
        for feat in candidate_features:
            mean, var = self.predict(feat)
            acq = ucb(mean, var, kappa=kappa)
            scores.append(acq)
        return sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)

    @property
    def n_observations(self) -> int:
        return self._n_obs
