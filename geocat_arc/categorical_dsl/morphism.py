"""Morphism base class for typed ARC operators."""
from __future__ import annotations
from .types import ArcType


class Morphism:
    name: str = "unnamed"
    input_types: tuple[ArcType, ...] = ()
    output_type: ArcType = ArcType.GRID
    cost: float = 1.0

    def apply(self, *args):
        raise NotImplementedError(f"{self.name}.apply() not implemented")

    def applicable(self, *args) -> bool:
        return True

    def __repr__(self) -> str:
        in_str = " x ".join(t.name for t in self.input_types)
        return f"{self.name}: {in_str} -> {self.output_type.name}"
