"""Concept graph memory — stores primitive, composed, and learned concepts
as a dependency graph with validation history."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import json
import numpy as np


@dataclass
class LearnedConcept:
    """A concept that has been validated and stored in memory."""
    name: str
    expression_str: str  # human-readable, e.g. "exists y: is_marker(y) AND same_row(x,y)"
    complexity: int
    source_failure_cluster: str  # e.g. "no_discrimination:richer_property_language"
    source_tasks: List[str]  # task_ids from which this was mined
    promoted_tasks: List[str] = field(default_factory=list)
    solved_tasks: List[str] = field(default_factory=list)
    domains_used: List[str] = field(default_factory=list)  # e.g. ["grid", "graph"]
    false_positives: int = 0
    counterexamples_survived: int = 0
    counterexamples_total: int = 0
    loo_passed: bool = False
    discrimination_score: float = 0.0
    dependencies: List[str] = field(default_factory=list)  # names of sub-concepts
    status: str = "proposed"  # proposed, validated, registered, rejected, deprecated
    created_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "expression": self.expression_str,
            "complexity": self.complexity,
            "source_cluster": self.source_failure_cluster,
            "source_tasks": self.source_tasks,
            "promoted_tasks": self.promoted_tasks,
            "solved_tasks": self.solved_tasks,
            "domains_used": self.domains_used,
            "false_positives": self.false_positives,
            "counterexamples_survived": self.counterexamples_survived,
            "counterexamples_total": self.counterexamples_total,
            "loo_passed": self.loo_passed,
            "discrimination_score": self.discrimination_score,
            "dependencies": self.dependencies,
            "status": self.status,
        }


class ConceptGraph:
    """Directed acyclic graph of concepts — primitives -> composed -> schemas.

    Nodes are concept names. Edges represent "A depends on B" (A uses B as sub-concept).
    """

    def __init__(self):
        self.concepts: Dict[str, LearnedConcept] = {}
        self.edges: Dict[str, Set[str]] = {}  # name -> set of dependency names
        self.reverse_edges: Dict[str, Set[str]] = {}  # name -> set of dependents

    def add_concept(self, concept: LearnedConcept) -> None:
        """Add a concept to the graph."""
        self.concepts[concept.name] = concept
        self.edges[concept.name] = set(concept.dependencies)
        for dep in concept.dependencies:
            self.reverse_edges.setdefault(dep, set()).add(concept.name)

    def get_concept(self, name: str) -> Optional[LearnedConcept]:
        return self.concepts.get(name)

    def remove_concept(self, name: str) -> bool:
        """Remove a concept. Fails if other concepts depend on it."""
        if name in self.reverse_edges and self.reverse_edges[name]:
            return False
        if name in self.concepts:
            del self.concepts[name]
            deps = self.edges.pop(name, set())
            for dep in deps:
                if dep in self.reverse_edges:
                    self.reverse_edges[dep].discard(name)
            return True
        return False

    def dependents(self, name: str) -> Set[str]:
        """What concepts depend on this one?"""
        return self.reverse_edges.get(name, set())

    def dependencies(self, name: str) -> Set[str]:
        """What does this concept depend on?"""
        return self.edges.get(name, set())

    def roots(self) -> List[str]:
        """Concepts with no dependencies (primitives)."""
        return [n for n, deps in self.edges.items() if not deps]

    def leaves(self) -> List[str]:
        """Concepts that nothing depends on."""
        return [n for n in self.concepts if n not in self.reverse_edges or not self.reverse_edges[n]]

    def topological_order(self) -> List[str]:
        """Return concept names in dependency order (dependencies first)."""
        visited: Set[str] = set()
        order: List[str] = []

        def visit(n: str) -> None:
            if n in visited:
                return
            visited.add(n)
            for dep in self.edges.get(n, set()):
                if dep in self.concepts:
                    visit(dep)
            order.append(n)

        for n in self.concepts:
            visit(n)
        return order

    def depth(self, name: str) -> int:
        """Depth of a concept in the graph (primitives = 0)."""
        deps = self.edges.get(name, set())
        if not deps:
            return 0
        return 1 + max(self.depth(d) for d in deps if d in self.concepts)

    def by_status(self, status: str) -> List[LearnedConcept]:
        return [c for c in self.concepts.values() if c.status == status]

    def by_complexity(self, max_complexity: int) -> List[LearnedConcept]:
        return [c for c in self.concepts.values() if c.complexity <= max_complexity]

    def mark_promoted(self, concept_name: str, task_id: str) -> None:
        c = self.concepts.get(concept_name)
        if c is not None:
            if task_id not in c.promoted_tasks:
                c.promoted_tasks.append(task_id)

    def mark_solved(self, concept_name: str, task_id: str) -> None:
        c = self.concepts.get(concept_name)
        if c is not None:
            if task_id not in c.solved_tasks:
                c.solved_tasks.append(task_id)

    def mark_false_positive(self, concept_name: str) -> None:
        c = self.concepts.get(concept_name)
        if c is not None:
            c.false_positives += 1

    def summary(self) -> Dict[str, Any]:
        status_counts: Dict[str, int] = {}
        for c in self.concepts.values():
            status_counts[c.status] = status_counts.get(c.status, 0) + 1
        return {
            "total_concepts": len(self.concepts),
            "status_counts": status_counts,
            "total_promoted": sum(len(c.promoted_tasks) for c in self.concepts.values()),
            "total_solved": sum(len(c.solved_tasks) for c in self.concepts.values()),
            "total_false_positives": sum(c.false_positives for c in self.concepts.values()),
            "max_depth": max((self.depth(n) for n in self.concepts), default=0),
            "n_primitives": len(self.roots()),
            "n_composed": len(self.concepts) - len(self.roots()),
        }

    def export_json(self, path: str) -> None:
        data = {
            "concepts": {n: c.to_dict() for n, c in self.concepts.items()},
            "edges": {n: sorted(deps) for n, deps in self.edges.items()},
            "summary": self.summary(),
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)

    def export_markdown(self, path: str) -> None:
        lines = ["# Concept Graph\n"]
        s = self.summary()
        lines.append(f"Total concepts: {s['total_concepts']}")
        lines.append(f"Primitives: {s['n_primitives']}")
        lines.append(f"Composed: {s['n_composed']}")
        lines.append(f"Max depth: {s['max_depth']}")
        lines.append(f"Tasks promoted: {s['total_promoted']}")
        lines.append(f"Tasks solved: {s['total_solved']}")
        lines.append(f"False positives: {s['total_false_positives']}")
        lines.append("")

        for status in ["registered", "validated", "proposed", "rejected"]:
            concepts = self.by_status(status)
            if concepts:
                lines.append(f"\n## {status.title()} ({len(concepts)})\n")
                for c in sorted(concepts, key=lambda x: x.complexity):
                    lines.append(f"- `{c.expression_str}` (complexity={c.complexity}, "
                                 f"promoted={len(c.promoted_tasks)}, "
                                 f"fp={c.false_positives})")

        with open(path, "w") as f:
            f.write("\n".join(lines))


class ConceptMemory:
    """Persistent memory that bridges the concept graph with the reasoning engine.

    Responsibilities:
    1. Maintain the concept graph
    2. Seed it with primitive concepts from the current property language
    3. Register validated concepts into the reasoning engine
    4. Track which concepts solved which tasks
    5. Provide retrieval for the adaptive loop
    """

    def __init__(self):
        self.graph = ConceptGraph()
        self._registered_compute_fns: Dict[str, Any] = {}

    def seed_primitives(self, property_names: Optional[List[str]] = None) -> None:
        """Seed the graph with primitive concepts from the property language."""
        from reasoning_project.reasoning_engine import _all_property_names
        names = property_names or _all_property_names()
        for name in names:
            concept = LearnedConcept(
                name=name,
                expression_str=f"{name}(x)",
                complexity=1,
                source_failure_cluster="primitive",
                source_tasks=[],
                dependencies=[],
                status="registered",
            )
            self.graph.add_concept(concept)

    def register_concept(
        self, concept: LearnedConcept, compute_fn: Any = None,
    ) -> bool:
        """Register a validated concept into the graph and optionally the reasoning engine."""
        if concept.name in self.graph.concepts:
            return False
        concept.status = "registered"
        self.graph.add_concept(concept)
        if compute_fn is not None:
            self._registered_compute_fns[concept.name] = compute_fn
        return True

    def retrieve_for_task(
        self, task_signature: Dict[str, Any], max_concepts: int = 20,
    ) -> List[LearnedConcept]:
        """Retrieve relevant registered concepts for a task."""
        registered = self.graph.by_status("registered")
        # Sort by: promoted count (desc), complexity (asc), false_positives (asc)
        scored = []
        for c in registered:
            score = len(c.promoted_tasks) * 10 - c.complexity - c.false_positives * 5
            scored.append((score, c))
        scored.sort(key=lambda x: -x[0])
        return [c for _, c in scored[:max_concepts]]

    def get_compute_fn(self, name: str) -> Optional[Any]:
        return self._registered_compute_fns.get(name)

    @property
    def summary(self) -> Dict[str, Any]:
        return self.graph.summary()
