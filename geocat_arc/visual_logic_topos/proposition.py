"""Propositions over ARC objects — finite logic."""
from __future__ import annotations
from .predicates import Predicate


class Proposition:
    def evaluate(self, *args) -> bool:
        raise NotImplementedError

    def __and__(self, other: Proposition) -> And:
        return And(self, other)

    def __or__(self, other: Proposition) -> Or:
        return Or(self, other)

    def __invert__(self) -> Not:
        return Not(self)


class AtomicProp(Proposition):
    def __init__(self, predicate: Predicate, *bound_args):
        self.predicate = predicate
        self.bound_args = bound_args

    def evaluate(self, *args) -> bool:
        all_args = self.bound_args + args
        return self.predicate(*all_args)

    def __repr__(self):
        return f"Atom({self.predicate}, {self.bound_args})"


class And(Proposition):
    def __init__(self, left: Proposition, right: Proposition):
        self.left = left
        self.right = right

    def evaluate(self, *args) -> bool:
        return self.left.evaluate(*args) and self.right.evaluate(*args)

    def __repr__(self):
        return f"({self.left} AND {self.right})"


class Or(Proposition):
    def __init__(self, left: Proposition, right: Proposition):
        self.left = left
        self.right = right

    def evaluate(self, *args) -> bool:
        return self.left.evaluate(*args) or self.right.evaluate(*args)

    def __repr__(self):
        return f"({self.left} OR {self.right})"


class Not(Proposition):
    def __init__(self, prop: Proposition):
        self.prop = prop

    def evaluate(self, *args) -> bool:
        return not self.prop.evaluate(*args)

    def __repr__(self):
        return f"NOT({self.prop})"


class Implies(Proposition):
    def __init__(self, antecedent: Proposition, consequent: Proposition):
        self.antecedent = antecedent
        self.consequent = consequent

    def evaluate(self, *args) -> bool:
        return (not self.antecedent.evaluate(*args)) or self.consequent.evaluate(*args)

    def __repr__(self):
        return f"({self.antecedent} => {self.consequent})"
