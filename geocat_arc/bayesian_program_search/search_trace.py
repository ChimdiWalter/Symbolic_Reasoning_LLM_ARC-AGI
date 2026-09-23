"""Search trace storage."""
from __future__ import annotations
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class SearchRecord:
    task_id: str
    iteration: int
    candidate_program: str
    posterior_mean: float
    posterior_uncertainty: float
    acquisition_score: float
    real_score: float
    exact_match: bool


class SearchTrace:
    def __init__(self):
        self.records: list[SearchRecord] = []

    def add(self, record: SearchRecord) -> None:
        self.records.append(record)

    @property
    def best_score(self) -> float:
        if not self.records:
            return 0.0
        return max(r.real_score for r in self.records)

    @property
    def best_record(self) -> SearchRecord | None:
        if not self.records:
            return None
        return max(self.records, key=lambda r: r.real_score)

    def to_jsonl(self, path: str | Path) -> None:
        with open(path, "w") as f:
            for rec in self.records:
                f.write(json.dumps(asdict(rec)) + "\n")

    @classmethod
    def from_jsonl(cls, path: str | Path) -> SearchTrace:
        trace = cls()
        with open(path) as f:
            for line in f:
                d = json.loads(line)
                trace.add(SearchRecord(**d))
        return trace
