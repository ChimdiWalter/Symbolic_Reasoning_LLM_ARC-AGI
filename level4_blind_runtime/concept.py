"""Concepts for V2.1: typed least-general anti-unification, and macros.

The anti-unifier knows two rules and nothing else:

    AU(x, x) = x
    AU(x : t, y : t) = a fresh variable of type t

Crucially the type of an introduced variable comes from the PARENT
PRODUCTION'S DECLARED ARGUMENT TYPE, not from the Python type of the
literal sitting there. A learned colour table is a tuple at runtime, but in
an argument position declared ``Map`` the variable is typed ``Map``.

Nothing here mentions a task, a family, or a concept name, and nothing
steers the result toward any expected shape: if two discovered programs
happen to agree on a literal, that literal is retained.

A learned concept is a MACRO. It carries a surface form used for search
depth, cost and attribution, and it elaborates into a core AST of ordinary
productions. Type checking, slot learning, execution and leave-one-out all
operate on the elaboration, so no concept-specific evaluator or learner
exists anywhere.

PROJECTED from meta_v21_concept.py for the Level-4 blind environment by
scripts/cora_level4_build_blind_runtime.py. The body is unchanged except
for its imports, which are rewired to the blind runtime, so search policy,
slot learners, costs and budgets are identical to the frozen runtime.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from . import runtime as V


# --------------------------------------------------------------------------
# typed least-general anti-unification
# --------------------------------------------------------------------------

@dataclass
class AntiUnification:
    schema: object                      # AST with "?v0", "?v1", ... slots
    slot_types: dict = field(default_factory=dict)
    bindings: tuple = ()                # one binding dict per input program

    def as_dict(self) -> dict:
        return {"schema": V.to_json(self.schema),
                "slot_types": {k: str(v) for k, v in self.slot_types.items()},
                "bindings": [{k: _jsonable(v) for k, v in b.items()}
                             for b in self.bindings]}


def _jsonable(value):
    try:
        json.dumps(value)
        return value
    except TypeError:
        return json.dumps(value, default=list)


def anti_unify(first, second) -> Optional[AntiUnification]:
    """Least general generalization of two typed ASTs."""
    state = {"count": 0, "types": {}, "left": {}, "right": {}}
    schema = _au(first, second, None, state)
    if schema is None:
        return None
    return AntiUnification(schema=schema, slot_types=state["types"],
                           bindings=(state["left"], state["right"]))


def _fresh(state, declared_type, left, right):
    name = f"?v{state['count']}"
    state["count"] += 1
    state["types"][name] = declared_type
    state["left"][name] = left
    state["right"][name] = right
    return name


def _au(left, right, declared_type, state):
    """Generalize two terms sitting in a position of ``declared_type``."""
    if V.is_ast(left) and V.is_ast(right):
        if left[0] != right[0] or len(left[1]) != len(right[1]):
            if declared_type is None:
                return None            # roots disagree: nothing to generalize
            return _fresh(state, declared_type, left, right)
        production = V.REGISTRY[left[0]]
        args = []
        for index, (a, b) in enumerate(zip(left[1], right[1])):
            child_type = (production.arg_types[index]
                          if index < len(production.arg_types) else None)
            generalized = _au(a, b, child_type, state)
            if generalized is None:
                return None
            args.append(generalized)
        return (left[0], tuple(args))
    if repr(left) == repr(right):
        return left                    # identical literal: retained
    if declared_type is None:
        return None
    return _fresh(state, declared_type, left, right)


def rename_slots(schema) -> object:
    """Canonical slot names in first-encounter order, for comparison."""
    mapping: dict = {}

    def walk(node):
        if isinstance(node, str) and node.startswith("?v"):
            if node not in mapping:
                mapping[node] = f"?v{len(mapping)}"
            return mapping[node]
        if V.is_ast(node):
            return (node[0], tuple(walk(a) for a in node[1]))
        return node

    return walk(schema)


def instantiate(schema, bindings: dict):
    if isinstance(schema, str) and schema.startswith("?v"):
        return bindings.get(schema, schema)
    if V.is_ast(schema):
        return (schema[0], tuple(instantiate(a, bindings) for a in schema[1]))
    return schema


def introduced_slots(schema) -> list:
    found: list = []

    def walk(node):
        if isinstance(node, str) and node.startswith("?v"):
            if node not in found:
                found.append(node)
            return
        if V.is_ast(node):
            for arg in node[1]:
                walk(arg)

    walk(schema)
    return found


# --------------------------------------------------------------------------
# a learned concept as a macro
# --------------------------------------------------------------------------

@dataclass
class Concept:
    """A learned macro: surface name plus its elaboration.

    ``cost`` is frozen when the concept is created, BEFORE any transfer task
    is examined. A macro that expands into a depth-4 core but counts as
    depth 1 is exactly how a learned abstraction can make a previously
    unreachable program reachable under bounded search, so its accounting
    must not be tuned after seeing results.
    """
    name: str
    schema: object
    slot_types: dict
    provenance: tuple
    source_hashes: tuple
    result_type: V.Type
    cost: int = 1
    status: str = "provisional"

    def elaborate(self, args) -> object:
        """Surface application to core AST, by ordinary substitution."""
        slots = introduced_slots(self.schema)
        if len(args) != len(slots):
            return None
        return instantiate(self.schema, dict(zip(slots, args)))

    def arg_types(self) -> tuple:
        return tuple(self.slot_types[s] for s in introduced_slots(self.schema))

    def to_dict(self) -> dict:
        return {"name": self.name, "schema": V.to_json(self.schema),
                "slot_types": {k: str(v) for k, v in self.slot_types.items()},
                "arg_types": [str(t) for t in self.arg_types()],
                "result_type": str(self.result_type),
                "provenance": list(self.provenance),
                "source_program_sha256": list(self.source_hashes),
                "cost": self.cost, "status": self.status}


def program_hash(ast) -> str:
    return hashlib.sha256(
        json.dumps(V.to_json(ast), sort_keys=True).encode()).hexdigest()[:16]


def learn_concept(programs_by_task: dict, name: str) -> Optional[Concept]:
    """Anti-unify two discovered programs into a macro.

    Nothing about the expected shape is supplied: the schema is whatever the
    least-general generalization returns.
    """
    if len(programs_by_task) != 2:
        return None
    (task_a, first), (task_b, second) = sorted(programs_by_task.items())
    result = anti_unify(first, second)
    if result is None or not introduced_slots(result.schema):
        return None                    # identical programs generalize nothing
    return Concept(name=name, schema=result.schema,
                   slot_types=result.slot_types,
                   provenance=(task_a, task_b),
                   source_hashes=(program_hash(first), program_hash(second)),
                   result_type=V.REGISTRY[result.schema[0]].result_type,
                   cost=1)


class ConceptRegistry:
    """Fresh per experiment; never seeded from an earlier registry."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.concepts: dict = {}

    def next_name(self) -> str:
        return f"concept_{len(self.concepts) + 1:04d}"

    def register(self, concept: Concept) -> None:
        self.concepts[concept.name] = concept
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(
            {n: c.to_dict() for n, c in sorted(self.concepts.items())},
            indent=1))
