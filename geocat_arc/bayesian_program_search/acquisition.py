"""Acquisition functions for Bayesian program search."""
from __future__ import annotations
import numpy as np
from scipy.stats import norm


def ucb(mean: float, variance: float, kappa: float = 2.0) -> float:
    return mean + kappa * np.sqrt(max(variance, 0.0))


def expected_improvement(mean: float, variance: float, best_so_far: float) -> float:
    std = np.sqrt(max(variance, 1e-12))
    z = (mean - best_so_far) / std
    return std * (z * norm.cdf(z) + norm.pdf(z))


def thompson_sample(mean: float, variance: float, rng: np.random.Generator = None) -> float:
    if rng is None:
        rng = np.random.default_rng()
    std = np.sqrt(max(variance, 1e-12))
    return float(rng.normal(mean, std))
