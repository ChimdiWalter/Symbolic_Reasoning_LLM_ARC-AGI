"""Categorical belief distributions over ARC operators/predicates/relations."""
from __future__ import annotations
import math
from collections import Counter


class BeliefDistribution:
    def __init__(self, probs: dict[str, float] | None = None):
        self._probs: dict[str, float] = dict(probs) if probs else {}
        if self._probs:
            self.normalize()

    @classmethod
    def from_counts(cls, counts: dict[str, int]) -> BeliefDistribution:
        total = sum(counts.values())
        if total == 0:
            return cls({k: 1.0 / len(counts) for k in counts} if counts else {})
        return cls({k: v / total for k, v in counts.items()})

    @classmethod
    def uniform(cls, keys: list[str]) -> BeliefDistribution:
        n = len(keys)
        return cls({k: 1.0 / n for k in keys}) if n > 0 else cls()

    def normalize(self) -> None:
        total = sum(self._probs.values())
        if total > 0:
            self._probs = {k: v / total for k, v in self._probs.items()}

    @property
    def probs(self) -> dict[str, float]:
        return dict(self._probs)

    @property
    def keys(self) -> list[str]:
        return list(self._probs.keys())

    def __getitem__(self, key: str) -> float:
        return self._probs.get(key, 0.0)

    def __setitem__(self, key: str, value: float) -> None:
        self._probs[key] = value

    def entropy(self) -> float:
        h = 0.0
        for p in self._probs.values():
            if p > 0:
                h -= p * math.log(p)
        return h

    def to_dict(self) -> dict:
        return {"probs": dict(self._probs)}

    @classmethod
    def from_dict(cls, d: dict) -> BeliefDistribution:
        return cls(d.get("probs", {}))

    def __repr__(self) -> str:
        return f"BeliefDistribution({len(self._probs)} keys, H={self.entropy():.3f})"
