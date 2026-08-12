"""Morphism composition with type checking."""
from __future__ import annotations
from .morphism import Morphism
from .types import ArcType
from .type_checker import check_composition, TypeCheckError


class ComposedMorphism(Morphism):
    def __init__(self, first: Morphism, second: Morphism):
        check_composition([first, second])
        self.first = first
        self.second = second
        self.name = f"{second.name} . {first.name}"
        self.input_types = first.input_types
        self.output_type = second.output_type
        self.cost = first.cost + second.cost

    def apply(self, *args):
        intermediate = self.first.apply(*args)
        return self.second.apply(intermediate)

    def applicable(self, *args) -> bool:
        return self.first.applicable(*args)


def compose(f: Morphism, g: Morphism) -> ComposedMorphism:
    return ComposedMorphism(f, g)
