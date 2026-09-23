"""Program representation — ordered sequence of morphism applications."""
from __future__ import annotations
from dataclasses import dataclass, field
from .morphism import Morphism
from .type_checker import check_composition, TypeCheckError
from geocat_arc.perception.grid import Grid


@dataclass
class ProgramStep:
    morphism: Morphism
    bound_args: tuple = ()

    def to_dict(self) -> dict:
        return {
            "morphism": self.morphism.name,
            "bound_args": [repr(a) for a in self.bound_args],
        }


class Program:
    def __init__(self, steps: list[ProgramStep] = None):
        self.steps: list[ProgramStep] = steps or []

    def add_step(self, morphism: Morphism, *bound_args):
        self.steps.append(ProgramStep(morphism=morphism, bound_args=bound_args))

    def type_check(self) -> bool:
        if len(self.steps) < 2:
            return True
        morphisms = [s.morphism for s in self.steps]
        try:
            return check_composition(morphisms)
        except TypeCheckError:
            return False

    def apply(self, input_grid: Grid):
        ctx = {
            "height": input_grid.height,
            "width": input_grid.width,
            "background": input_grid.background_color,
        }
        result = input_grid
        for step in self.steps:
            if step.morphism.name == "render":
                args = (result,)
                result = step.morphism.apply(*args, _ctx=ctx)
            else:
                args = (result,) + step.bound_args
                result = step.morphism.apply(*args)
        return result

    @property
    def depth(self) -> int:
        return len(self.steps)

    @property
    def total_cost(self) -> float:
        return sum(s.morphism.cost for s in self.steps)

    @property
    def operator_names(self) -> list[str]:
        return [s.morphism.name for s in self.steps]

    def to_dict(self) -> dict:
        return {
            "steps": [s.to_dict() for s in self.steps],
            "depth": self.depth,
            "total_cost": self.total_cost,
        }

    def __repr__(self) -> str:
        ops = " -> ".join(s.morphism.name for s in self.steps)
        return f"Program({ops})"
