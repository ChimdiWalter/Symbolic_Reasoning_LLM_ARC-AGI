"""Monitor drift in operator distributions over time."""
from __future__ import annotations
from .belief_distribution import BeliefDistribution
from .distance_metrics import js_divergence


class DriftMonitor:
    def __init__(self, window_size: int = 10):
        self.window_size = window_size
        self._history: list[BeliefDistribution] = []

    def record(self, distribution: BeliefDistribution) -> None:
        self._history.append(distribution)

    def detect_drift(self, threshold: float = 0.1) -> bool:
        if len(self._history) < 2:
            return False
        recent = self._history[-1].probs
        if len(self._history) >= self.window_size:
            old_probs = {}
            old_dists = self._history[-self.window_size:-1]
            for d in old_dists:
                for k, v in d.probs.items():
                    old_probs[k] = old_probs.get(k, 0.0) + v
            total = sum(old_probs.values())
            if total > 0:
                old_probs = {k: v / total for k, v in old_probs.items()}
        else:
            old_probs = self._history[-2].probs

        return js_divergence(recent, old_probs) > threshold

    @property
    def num_records(self) -> int:
        return len(self._history)
