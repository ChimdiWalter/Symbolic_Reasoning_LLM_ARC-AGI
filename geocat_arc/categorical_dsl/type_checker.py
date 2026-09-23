"""Type checker for morphism compositions."""
from __future__ import annotations
from .morphism import Morphism
from .types import ArcType


class TypeCheckError(Exception):
    pass


def check_composition(morphisms: list[Morphism]) -> bool:
    if len(morphisms) < 2:
        return True
    for i in range(len(morphisms) - 1):
        out_type = morphisms[i].output_type
        next_in = morphisms[i + 1].input_types
        if not next_in:
            continue
        if out_type != next_in[0]:
            raise TypeCheckError(
                f"Type mismatch: {morphisms[i].name} outputs {out_type.name} "
                f"but {morphisms[i+1].name} expects {next_in[0].name}"
            )
    return True


def validate_input(morphism: Morphism, args: tuple, arg_types: tuple[ArcType, ...]) -> bool:
    if len(arg_types) != len(morphism.input_types):
        raise TypeCheckError(
            f"{morphism.name} expects {len(morphism.input_types)} args, got {len(arg_types)}"
        )
    for i, (expected, actual) in enumerate(zip(morphism.input_types, arg_types)):
        if expected != actual:
            raise TypeCheckError(
                f"{morphism.name} arg {i}: expected {expected.name}, got {actual.name}"
            )
    return True
