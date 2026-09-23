"""Quantifiers over finite object domains."""
from __future__ import annotations
from .proposition import Proposition


class ForAll(Proposition):
    def __init__(self, proposition: Proposition, domain: list):
        self.proposition = proposition
        self.domain = domain

    def evaluate(self, *args) -> bool:
        return all(self.proposition.evaluate(obj) for obj in self.domain)

    def __repr__(self):
        return f"ForAll({self.proposition}, |domain|={len(self.domain)})"


class Exists(Proposition):
    def __init__(self, proposition: Proposition, domain: list):
        self.proposition = proposition
        self.domain = domain

    def evaluate(self, *args) -> bool:
        return any(self.proposition.evaluate(obj) for obj in self.domain)

    def __repr__(self):
        return f"Exists({self.proposition}, |domain|={len(self.domain)})"
