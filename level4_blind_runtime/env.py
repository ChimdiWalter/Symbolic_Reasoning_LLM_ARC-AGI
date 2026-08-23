"""Language environments: the frozen kernel, plus learned concepts as macros.

The kernel K is never mutated. An experiment arm is a ``LanguageEnv``
holding the frozen base registry and an overlay of learned concepts, so the
treatment is ``K + C`` and the ablation is literally the same object with the
overlay emptied.

A learned concept is a SURFACE production. Search depth, cost, candidate
ordering and attribution all read the surface AST, where a concept counts as
one node. Type checking, slot fitting, execution and leave-one-out all read
the ELABORATION into ordinary kernel productions. There is therefore no
concept-specific evaluator, no concept-specific slot learner, and no branch
anywhere on a concept's name: a macro is expanded by generic substitution
and everything downstream sees only kernel productions.

That separation is the whole mechanism. Under unlimited search a macro adds
nothing, because it expands into the kernel; under a fixed budget it can
make a program reachable that was not. What Phase 5 can therefore establish
is a change in what is reachable at a fixed budget, not a change in what the
language can denote.

PROJECTED from meta_v21_env.py for the Level-4 blind environment by
scripts/cora_level4_build_blind_runtime.py. The body is unchanged except
for its imports, which are rewired to the blind runtime, so search policy,
slot learners, costs and budgets are identical to the frozen runtime.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional

from . import runtime as V
from . import concept as C


@dataclass
class LanguageEnv:
    """A frozen base registry plus a concept overlay."""
    base: dict = field(default_factory=lambda: dict(V.REGISTRY))
    concepts: dict = field(default_factory=dict)
    label: str = "K"

    # -- membership -------------------------------------------------------
    @property
    def names(self) -> set:
        return set(self.base) | set(self.concepts)

    def is_concept(self, name: str) -> bool:
        return name in self.concepts

    def is_ast(self, value) -> bool:
        return isinstance(value, tuple) and len(value) == 2 \
            and isinstance(value[0], str) and value[0] in self.names

    def with_concept(self, concept: C.Concept, label=None) -> "LanguageEnv":
        """A NEW environment; the base registry is untouched."""
        return LanguageEnv(base=self.base,
                           concepts={**self.concepts, concept.name: concept},
                           label=label or f"{self.label}+{concept.name}")

    def without_concepts(self, label=None) -> "LanguageEnv":
        """The ablation: the same base, no overlay."""
        return LanguageEnv(base=self.base, concepts={},
                           label=label or f"{self.label}-concepts")

    # -- typed interface of any production, kernel or concept -------------
    def arg_types(self, name: str) -> tuple:
        if name in self.concepts:
            return self.concepts[name].arg_types()
        return self.base[name].arg_types

    def result_type(self, name: str):
        if name in self.concepts:
            return self.concepts[name].result_type
        return self.base[name].result_type

    def cost(self, name: str) -> int:
        """Surface cost. A concept counts as ONE node by frozen policy."""
        if name in self.concepts:
            return self.concepts[name].cost
        return self.base[name].cost


def expand(ast, env: LanguageEnv):
    """Surface AST to core AST by generic substitution.

    Applies recursively, so a concept whose schema itself contained another
    concept would expand too. Returns None if a concept application has the
    wrong arity.
    """
    if not env.is_ast(ast):
        return ast
    op, args = ast
    expanded_args = tuple(expand(a, env) for a in args)
    if any(a is None for a in expanded_args):
        return None
    if env.is_concept(op):
        core = env.concepts[op].elaborate(list(expanded_args))
        return core
    return (op, expanded_args)


def uses_concept(ast, env: LanguageEnv, name: str) -> bool:
    """Does the SURFACE program actually apply this concept?"""
    if not env.is_ast(ast):
        return False
    if ast[0] == name:
        return True
    return any(uses_concept(a, env, name) for a in ast[1])


# --------------------------------------------------------------------------
# surface accounting, kept separate from the core
# --------------------------------------------------------------------------

def surface_nodes(ast, env: LanguageEnv) -> int:
    if not env.is_ast(ast):
        return 0
    total = env.cost(ast[0])
    for arg in ast[1]:
        if env.is_ast(arg):
            total += surface_nodes(arg, env)
        elif isinstance(arg, tuple):
            total += len(arg)
    return total


def surface_depth(ast, env: LanguageEnv) -> int:
    if not env.is_ast(ast):
        return 0
    depths = [surface_depth(a, env) for a in ast[1] if env.is_ast(a)]
    return 1 + (max(depths) if depths else 0)


def surface_value_bound(ast, env: LanguageEnv) -> int:
    if not env.is_ast(ast):
        return 0
    total = 0
    for arg in ast[1]:
        if env.is_ast(arg):
            total += surface_value_bound(arg, env)
        elif isinstance(arg, tuple):
            total += len(arg)
    return total


def accounting(ast, env: LanguageEnv) -> dict:
    """Both views, always reported together."""
    core = expand(ast, env)
    return {"surface_cost": surface_nodes(ast, env),
            "surface_depth": surface_depth(ast, env),
            "core_cost": V.ast_nodes(core) if core is not None else None,
            "core_depth": V.ast_depth(core) if core is not None else None,
            "compression": (round(V.ast_nodes(core) / surface_nodes(ast, env), 3)
                            if core is not None and surface_nodes(ast, env)
                            else None)}


# --------------------------------------------------------------------------
# type checking and execution: always on the elaboration
# --------------------------------------------------------------------------

def type_of(ast, env: LanguageEnv):
    core = expand(ast, env)
    return V.type_of(core) if core is not None else None


def evaluate(ast, grid, env: LanguageEnv):
    core = expand(ast, env)
    return V.evaluate(core, grid) if core is not None else None


def free_slots(ast, env: LanguageEnv) -> dict:
    core = expand(ast, env)
    return V.free_slots(core) if core is not None else {}


def instantiate(ast, bindings: dict, env: LanguageEnv):
    """Substitute into the SURFACE program, keeping it a surface program."""
    if isinstance(ast, str) and ast.startswith("?"):
        return bindings.get(ast, ast)
    if env.is_ast(ast):
        return (ast[0], tuple(instantiate(a, bindings, env) for a in ast[1]))
    return ast


def to_json(ast, env: LanguageEnv):
    if env.is_ast(ast):
        return {"op": ast[0], "args": [to_json(a, env) for a in ast[1]]}
    return {"lit": json.dumps(ast, default=list)}


def concepts_used(ast, env: LanguageEnv) -> list:
    out = []
    if not env.is_ast(ast):
        return out
    out.append(ast[0])
    for arg in ast[1]:
        if env.is_ast(arg):
            out.extend(concepts_used(arg, env))
        elif isinstance(arg, str):
            out.append(f"{ast[0]}:{arg}")
    return out


BASE_ENV = LanguageEnv(label="K")
