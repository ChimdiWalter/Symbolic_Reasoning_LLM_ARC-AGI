"""Hebbian association memory for predicate/operator coactivation."""
from __future__ import annotations
from collections import defaultdict


class HebbianMemory:
    def __init__(self, learning_rate: float = 0.1, decay_rate: float = 0.01):
        self._associations: dict[tuple[str, str], float] = defaultdict(float)
        self.learning_rate = learning_rate
        self.decay_rate = decay_rate

    def update(self, predicate: str, operator: str, success: bool) -> None:
        key = (predicate, operator)
        if success:
            self._associations[key] += self.learning_rate
        else:
            self._associations[key] -= self.learning_rate * 0.3
            self._associations[key] = max(0.0, self._associations[key])

    def get_strength(self, predicate: str, operator: str) -> float:
        return self._associations.get((predicate, operator), 0.0)

    def top_associations(self, predicate: str, k: int = 5) -> list[tuple[str, float]]:
        results = []
        for (p, op), strength in self._associations.items():
            if p == predicate:
                results.append((op, strength))
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:k]

    def decay(self, rate: float | None = None) -> None:
        r = rate if rate is not None else self.decay_rate
        for key in list(self._associations.keys()):
            self._associations[key] *= (1.0 - r)
            if self._associations[key] < 1e-10:
                del self._associations[key]

    def to_dict(self) -> dict:
        return {f"{p}|{op}": v for (p, op), v in self._associations.items()}

    @classmethod
    def from_dict(cls, d: dict) -> HebbianMemory:
        mem = cls()
        for key, v in d.items():
            p, op = key.split("|", 1)
            mem._associations[(p, op)] = v
        return mem
