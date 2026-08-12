"""ARC task data structures."""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class GridPair:
    input: list[list[int]]
    output: list[list[int]]


@dataclass
class ARCTask:
    task_id: str
    train: list[GridPair]
    test: list[GridPair] = field(default_factory=list)

    @property
    def num_train(self) -> int:
        return len(self.train)

    @property
    def num_test(self) -> int:
        return len(self.test)
