"""Lightweight e-graph/equality-saturation layer for DSL program equivalence.

Represents groups of equivalent programs compactly and finds the
lowest-cost equivalent program using rewrite rules.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
import numpy as np


@dataclass(frozen=True)
class ProgramNode:
    """An operator application in the program tree."""
    op: str
    args: Tuple = ()

    def __repr__(self):
        if self.args:
            return f"{self.op}({', '.join(repr(a) for a in self.args)})"
        return self.op

    def cost(self) -> int:
        base = 20
        arg_cost = sum(3 + len(str(a)) for a in self.args)
        return base + arg_cost


@dataclass
class EClass:
    """Equivalence class: a set of equivalent program nodes."""
    id: int
    nodes: Set[ProgramNode] = field(default_factory=set)

    def best_node(self) -> ProgramNode:
        return min(self.nodes, key=lambda n: n.cost())


class EGraph:
    """Simple e-graph for program equivalence and simplification."""

    def __init__(self):
        self._classes: Dict[int, EClass] = {}
        self._node_to_class: Dict[ProgramNode, int] = {}
        self._next_id = 0

    def add(self, node: ProgramNode) -> int:
        if node in self._node_to_class:
            return self._node_to_class[node]
        cid = self._next_id
        self._next_id += 1
        ec = EClass(id=cid, nodes={node})
        self._classes[cid] = ec
        self._node_to_class[node] = cid
        return cid

    def merge(self, id1: int, id2: int) -> int:
        if id1 == id2:
            return id1
        ec1 = self._classes[id1]
        ec2 = self._classes[id2]
        for n in ec2.nodes:
            ec1.nodes.add(n)
            self._node_to_class[n] = id1
        del self._classes[id2]
        return id1

    def find(self, node: ProgramNode) -> Optional[int]:
        return self._node_to_class.get(node)

    def equivalent(self, n1: ProgramNode, n2: ProgramNode) -> bool:
        c1 = self.find(n1)
        c2 = self.find(n2)
        if c1 is None or c2 is None:
            return False
        return c1 == c2

    def best(self, class_id: int) -> ProgramNode:
        return self._classes[class_id].best_node()

    def class_size(self, class_id: int) -> int:
        return len(self._classes[class_id].nodes)

    @property
    def n_classes(self) -> int:
        return len(self._classes)

    @property
    def n_nodes(self) -> int:
        return sum(len(ec.nodes) for ec in self._classes.values())


# Rewrite rules for DSL simplification
REWRITE_RULES: List[Tuple[ProgramNode, ProgramNode]] = [
    # Identity simplifications
    (ProgramNode("rotate_90", ()), ProgramNode("rotate_90")),

    # Double reflection = identity
    # reflect_horizontal ∘ reflect_horizontal = identity
    # These are represented as composition rules below

    # Rotation simplifications
    # rotate_90 ∘ rotate_90 ∘ rotate_90 ∘ rotate_90 = identity
    # rotate_180 ∘ rotate_180 = identity
]


def build_composition_equivalences() -> List[Tuple[Tuple[str, ...], Tuple[str, ...]]]:
    """Build equivalence rules for operator compositions."""
    rules = []

    # reflect ∘ reflect = identity
    rules.append((("reflect_horizontal", "reflect_horizontal"), ("identity",)))
    rules.append((("reflect_vertical", "reflect_vertical"), ("identity",)))

    # rotate compositions
    rules.append((("rotate_180", "rotate_180"), ("identity",)))
    rules.append((("rotate_90", "rotate_90"), ("rotate_180",)))
    rules.append((("rotate_90", "rotate_180"), ("rotate_270",)))
    rules.append((("rotate_180", "rotate_90"), ("rotate_270",)))
    rules.append((("rotate_90", "rotate_270"), ("identity",)))
    rules.append((("rotate_270", "rotate_90"), ("identity",)))

    # reflect + rotate equivalences
    rules.append((("reflect_horizontal", "rotate_180"), ("reflect_vertical",)))
    rules.append((("reflect_vertical", "rotate_180"), ("reflect_horizontal",)))

    # transpose equivalences
    rules.append((("transpose", "transpose"), ("identity",)))
    rules.append((("transpose", "reflect_horizontal"), ("rotate_270",)))
    rules.append((("reflect_horizontal", "transpose"), ("rotate_90",)))

    return rules


COMPOSITION_RULES = build_composition_equivalences()


def simplify_program(steps: List[str]) -> List[str]:
    """Simplify a program by applying composition equivalence rules."""
    changed = True
    result = list(steps)

    while changed:
        changed = False
        for lhs, rhs in COMPOSITION_RULES:
            ll = len(lhs)
            for i in range(len(result) - ll + 1):
                if tuple(result[i:i + ll]) == lhs:
                    result = result[:i] + list(rhs) + result[i + ll:]
                    changed = True
                    break
            if changed:
                break

    # Remove identity steps
    result = [s for s in result if s != "identity"]
    return result if result else ["identity"]


def extensional_equality(
    fn1, fn2, test_grids: List[np.ndarray]
) -> bool:
    """Check extensional equality of two functions on test grids."""
    for grid in test_grids:
        try:
            r1 = fn1(grid)
            r2 = fn2(grid)
        except Exception:
            return False
        if r1 is None or r2 is None:
            if r1 is not r2:
                return False
            continue
        if not np.array_equal(np.asarray(r1), np.asarray(r2)):
            return False
    return True


def collapse_equivalent_candidates(
    candidates: List[Tuple[List[str], float]],
    test_grids: Optional[List[np.ndarray]] = None,
) -> List[Tuple[List[str], float]]:
    """Collapse candidates that are equivalent after simplification.

    Returns deduplicated candidates sorted by cost.
    """
    seen = {}
    results = []

    for steps, score in candidates:
        simplified = simplify_program(steps)
        key = tuple(simplified)
        if key not in seen:
            seen[key] = (simplified, score)
            results.append((simplified, score))

    results.sort(key=lambda x: sum(ProgramNode(s).cost() for s in x[0]))
    return results


def build_egraph_from_candidates(
    candidates: List[List[str]],
) -> Tuple[EGraph, Dict[int, List[str]]]:
    """Build an e-graph from a list of candidate programs."""
    eg = EGraph()
    class_to_program: Dict[int, List[str]] = {}

    # Map each program to a simplified form and group
    simplified_to_classes: Dict[tuple, int] = {}

    for steps in candidates:
        simplified = simplify_program(steps)
        key = tuple(simplified)
        node = ProgramNode("compose", tuple(steps))
        cid = eg.add(node)

        if key in simplified_to_classes:
            eg.merge(simplified_to_classes[key], cid)
        else:
            simplified_to_classes[key] = cid

        class_to_program[cid] = steps

    return eg, class_to_program
