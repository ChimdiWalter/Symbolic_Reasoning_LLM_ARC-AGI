"""Finite logic engine for evaluating propositions over object sets."""
from __future__ import annotations
from .proposition import Proposition


def evaluate_proposition(prop: Proposition, *objects) -> bool:
    return prop.evaluate(*objects)


def satisfying_objects(prop: Proposition, objects: list) -> list:
    return [obj for obj in objects if prop.evaluate(obj)]


def satisfying_pairs(prop: Proposition, objects: list) -> list[tuple]:
    results = []
    for i, a in enumerate(objects):
        for j, b in enumerate(objects):
            if i != j and prop.evaluate(a, b):
                results.append((a, b))
    return results
