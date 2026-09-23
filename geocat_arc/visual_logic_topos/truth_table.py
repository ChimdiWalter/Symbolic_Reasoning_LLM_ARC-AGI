"""Truth table generation for propositions over finite domains."""
from __future__ import annotations
from .proposition import Proposition


def build_truth_table(proposition: Proposition, objects: list) -> dict:
    table = {}
    for obj in objects:
        key = getattr(obj, 'id', id(obj))
        table[key] = proposition.evaluate(obj)
    return table


def build_pair_truth_table(proposition: Proposition, objects: list) -> dict:
    table = {}
    for a in objects:
        for b in objects:
            if a is not b:
                ka = getattr(a, 'id', id(a))
                kb = getattr(b, 'id', id(b))
                table[(ka, kb)] = proposition.evaluate(a, b)
    return table
