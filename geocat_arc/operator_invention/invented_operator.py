"""Invented operator from failure cluster analysis."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Any


@dataclass
class InventedOperator:
    name: str
    input_types: list[str]
    output_type: str
    preconditions: list[str]
    postconditions: list[str]
    source_cluster_ids: list[str]
    apply_fn: Callable[..., Any] | None = None
    verified: bool = False
    certificate_path: str | None = None

    def apply(self, *args):
        if self.apply_fn is None:
            raise RuntimeError(f"Operator {self.name} has no apply function")
        return self.apply_fn(*args)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "input_types": self.input_types,
            "output_type": self.output_type,
            "preconditions": self.preconditions,
            "postconditions": self.postconditions,
            "source_cluster_ids": self.source_cluster_ids,
            "verified": self.verified,
            "certificate_path": self.certificate_path,
        }
