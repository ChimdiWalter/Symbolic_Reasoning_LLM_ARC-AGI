"""Vicarious reward — update operator priors from successful examples."""
from __future__ import annotations
from collections import defaultdict


class VicariousReward:
    def __init__(self):
        self._priors: dict[str, float] = defaultdict(lambda: 1.0)

    def reward(self, operator: str, success_score: float) -> None:
        self._priors[operator] += success_score

    def penalize(self, operator: str, failure_score: float) -> None:
        self._priors[operator] = max(0.01, self._priors[operator] - failure_score * 0.3)

    def get_prior(self, operator: str) -> float:
        return self._priors[operator]

    def normalize(self) -> None:
        total = sum(self._priors.values())
        if total > 0:
            for k in self._priors:
                self._priors[k] /= total

    def top_operators(self, k: int = 5) -> list[tuple[str, float]]:
        sorted_ops = sorted(self._priors.items(), key=lambda x: x[1], reverse=True)
        return sorted_ops[:k]

    def all_priors(self) -> dict[str, float]:
        return dict(self._priors)
