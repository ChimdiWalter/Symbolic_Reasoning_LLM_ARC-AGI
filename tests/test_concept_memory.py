"""Tests for concept graph memory."""
from __future__ import annotations

import json
import os
import tempfile
from typing import Any, Dict, List

import numpy as np
import pytest

from reasoning_project.concept_memory import (
    ConceptGraph,
    ConceptMemory,
    LearnedConcept,
)


# ── Fixtures ────────────────────────────────────────────────────────────


def _make_concept(
    name: str = "test_concept",
    expression: str = "test(x)",
    complexity: int = 1,
    source_cluster: str = "primitive",
    source_tasks: List[str] | None = None,
    dependencies: List[str] | None = None,
    status: str = "proposed",
    promoted_tasks: List[str] | None = None,
    solved_tasks: List[str] | None = None,
    false_positives: int = 0,
    loo_passed: bool = False,
    discrimination_score: float = 0.0,
) -> LearnedConcept:
    return LearnedConcept(
        name=name,
        expression_str=expression,
        complexity=complexity,
        source_failure_cluster=source_cluster,
        source_tasks=source_tasks or [],
        dependencies=dependencies or [],
        status=status,
        promoted_tasks=promoted_tasks or [],
        solved_tasks=solved_tasks or [],
        false_positives=false_positives,
        loo_passed=loo_passed,
        discrimination_score=discrimination_score,
    )


def _build_graph_with_hierarchy() -> ConceptGraph:
    """Build a graph: A, B are primitives; C depends on A and B; D depends on C."""
    g = ConceptGraph()
    g.add_concept(_make_concept("A", "A(x)", 1, status="registered"))
    g.add_concept(_make_concept("B", "B(x)", 1, status="registered"))
    g.add_concept(
        _make_concept("C", "A(x) AND B(x)", 2, dependencies=["A", "B"], status="validated")
    )
    g.add_concept(
        _make_concept("D", "C(x) AND large(x)", 3, dependencies=["C"], status="proposed")
    )
    return g


# ── LearnedConcept tests ───────────────────────────────────────────────


class TestLearnedConcept:
    def test_creation_defaults(self):
        c = _make_concept()
        assert c.name == "test_concept"
        assert c.expression_str == "test(x)"
        assert c.complexity == 1
        assert c.status == "proposed"
        assert c.promoted_tasks == []
        assert c.solved_tasks == []
        assert c.false_positives == 0
        assert c.loo_passed is False
        assert c.dependencies == []

    def test_to_dict(self):
        c = _make_concept(
            name="has_holes",
            expression="has_holes(x)",
            complexity=1,
            source_cluster="primitive",
            source_tasks=["task_001"],
            promoted_tasks=["task_002"],
            solved_tasks=["task_003"],
            false_positives=2,
            loo_passed=True,
            discrimination_score=0.85,
        )
        d = c.to_dict()
        assert d["name"] == "has_holes"
        assert d["expression"] == "has_holes(x)"
        assert d["complexity"] == 1
        assert d["source_cluster"] == "primitive"
        assert d["source_tasks"] == ["task_001"]
        assert d["promoted_tasks"] == ["task_002"]
        assert d["solved_tasks"] == ["task_003"]
        assert d["false_positives"] == 2
        assert d["loo_passed"] is True
        assert d["discrimination_score"] == 0.85
        assert d["status"] == "proposed"
        assert d["dependencies"] == []

    def test_to_dict_keys(self):
        c = _make_concept()
        d = c.to_dict()
        expected_keys = {
            "name", "expression", "complexity", "source_cluster",
            "source_tasks", "promoted_tasks", "solved_tasks", "domains_used",
            "false_positives", "counterexamples_survived", "counterexamples_total",
            "loo_passed", "discrimination_score", "dependencies", "status",
        }
        assert set(d.keys()) == expected_keys


# ── ConceptGraph tests ─────────────────────────────────────────────────


class TestConceptGraphAddRemoveGet:
    def test_add_and_get(self):
        g = ConceptGraph()
        c = _make_concept("p1", "p1(x)")
        g.add_concept(c)
        assert g.get_concept("p1") is c

    def test_get_missing_returns_none(self):
        g = ConceptGraph()
        assert g.get_concept("nonexistent") is None

    def test_remove_leaf(self):
        g = ConceptGraph()
        g.add_concept(_make_concept("p1", "p1(x)"))
        assert g.remove_concept("p1") is True
        assert g.get_concept("p1") is None

    def test_remove_nonexistent(self):
        g = ConceptGraph()
        assert g.remove_concept("ghost") is False

    def test_remove_fails_if_dependents_exist(self):
        g = _build_graph_with_hierarchy()
        # A has dependent C, so removal should fail
        assert g.remove_concept("A") is False
        assert g.get_concept("A") is not None

    def test_remove_updates_reverse_edges(self):
        g = ConceptGraph()
        g.add_concept(_make_concept("A", "A(x)", 1))
        g.add_concept(_make_concept("B", "B(x)", 2, dependencies=["A"]))
        # Remove B (leaf) should succeed and clean up reverse edges
        assert g.remove_concept("B") is True
        assert g.dependents("A") == set()


class TestConceptGraphDependencies:
    def test_dependencies_of_primitive(self):
        g = _build_graph_with_hierarchy()
        assert g.dependencies("A") == set()

    def test_dependencies_of_composed(self):
        g = _build_graph_with_hierarchy()
        assert g.dependencies("C") == {"A", "B"}

    def test_dependents_of_primitive(self):
        g = _build_graph_with_hierarchy()
        assert g.dependents("A") == {"C"}

    def test_dependents_of_composed(self):
        g = _build_graph_with_hierarchy()
        assert g.dependents("C") == {"D"}

    def test_dependents_of_leaf(self):
        g = _build_graph_with_hierarchy()
        assert g.dependents("D") == set()


class TestConceptGraphRootsLeaves:
    def test_roots(self):
        g = _build_graph_with_hierarchy()
        roots = set(g.roots())
        assert roots == {"A", "B"}

    def test_leaves(self):
        g = _build_graph_with_hierarchy()
        leaves = set(g.leaves())
        assert leaves == {"D"}

    def test_single_node_is_both_root_and_leaf(self):
        g = ConceptGraph()
        g.add_concept(_make_concept("solo", "solo(x)"))
        assert g.roots() == ["solo"]
        assert g.leaves() == ["solo"]


class TestConceptGraphTopologicalOrder:
    def test_basic_order(self):
        g = _build_graph_with_hierarchy()
        order = g.topological_order()
        # Dependencies must come before dependents
        pos = {name: i for i, name in enumerate(order)}
        assert pos["A"] < pos["C"]
        assert pos["B"] < pos["C"]
        assert pos["C"] < pos["D"]

    def test_all_present(self):
        g = _build_graph_with_hierarchy()
        order = g.topological_order()
        assert set(order) == {"A", "B", "C", "D"}


class TestConceptGraphDepth:
    def test_primitive_depth(self):
        g = _build_graph_with_hierarchy()
        assert g.depth("A") == 0
        assert g.depth("B") == 0

    def test_depth_1(self):
        g = _build_graph_with_hierarchy()
        assert g.depth("C") == 1

    def test_depth_2(self):
        g = _build_graph_with_hierarchy()
        assert g.depth("D") == 2


class TestConceptGraphByStatusComplexity:
    def test_by_status(self):
        g = _build_graph_with_hierarchy()
        registered = g.by_status("registered")
        assert {c.name for c in registered} == {"A", "B"}
        validated = g.by_status("validated")
        assert {c.name for c in validated} == {"C"}
        proposed = g.by_status("proposed")
        assert {c.name for c in proposed} == {"D"}

    def test_by_complexity(self):
        g = _build_graph_with_hierarchy()
        simple = g.by_complexity(1)
        assert {c.name for c in simple} == {"A", "B"}
        medium = g.by_complexity(2)
        assert {c.name for c in medium} == {"A", "B", "C"}
        all_concepts = g.by_complexity(10)
        assert len(all_concepts) == 4


class TestConceptGraphMark:
    def test_mark_promoted(self):
        g = ConceptGraph()
        g.add_concept(_make_concept("p1", "p1(x)"))
        g.mark_promoted("p1", "task_001")
        g.mark_promoted("p1", "task_002")
        # Duplicate should not be added
        g.mark_promoted("p1", "task_001")
        c = g.get_concept("p1")
        assert c is not None
        assert c.promoted_tasks == ["task_001", "task_002"]

    def test_mark_solved(self):
        g = ConceptGraph()
        g.add_concept(_make_concept("p1", "p1(x)"))
        g.mark_solved("p1", "task_003")
        g.mark_solved("p1", "task_003")  # duplicate
        c = g.get_concept("p1")
        assert c is not None
        assert c.solved_tasks == ["task_003"]

    def test_mark_false_positive(self):
        g = ConceptGraph()
        g.add_concept(_make_concept("p1", "p1(x)"))
        g.mark_false_positive("p1")
        g.mark_false_positive("p1")
        c = g.get_concept("p1")
        assert c is not None
        assert c.false_positives == 2

    def test_mark_nonexistent_no_error(self):
        g = ConceptGraph()
        # Should not raise
        g.mark_promoted("ghost", "task_x")
        g.mark_solved("ghost", "task_x")
        g.mark_false_positive("ghost")


class TestConceptGraphSummary:
    def test_summary_structure(self):
        g = _build_graph_with_hierarchy()
        g.mark_promoted("A", "task_1")
        g.mark_solved("B", "task_2")
        g.mark_false_positive("C")

        s = g.summary()
        assert s["total_concepts"] == 4
        assert s["status_counts"]["registered"] == 2
        assert s["status_counts"]["validated"] == 1
        assert s["status_counts"]["proposed"] == 1
        assert s["total_promoted"] == 1
        assert s["total_solved"] == 1
        assert s["total_false_positives"] == 1
        assert s["max_depth"] == 2
        assert s["n_primitives"] == 2
        assert s["n_composed"] == 2

    def test_empty_summary(self):
        g = ConceptGraph()
        s = g.summary()
        assert s["total_concepts"] == 0
        assert s["max_depth"] == 0
        assert s["n_primitives"] == 0


class TestConceptGraphExport:
    def test_export_json(self):
        g = _build_graph_with_hierarchy()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            path = f.name
        try:
            g.export_json(path)
            with open(path) as f:
                data = json.load(f)
            assert "concepts" in data
            assert "edges" in data
            assert "summary" in data
            assert "A" in data["concepts"]
            assert data["concepts"]["A"]["complexity"] == 1
            assert sorted(data["edges"]["C"]) == ["A", "B"]
        finally:
            os.unlink(path)

    def test_export_markdown(self):
        g = _build_graph_with_hierarchy()
        g.mark_promoted("A", "task_1")
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False, mode="w") as f:
            path = f.name
        try:
            g.export_markdown(path)
            with open(path) as f:
                content = f.read()
            assert "# Concept Graph" in content
            assert "Total concepts: 4" in content
            assert "Registered" in content
            assert "A(x)" in content
        finally:
            os.unlink(path)


# ── ConceptMemory tests ────────────────────────────────────────────────


class TestConceptMemorySeedPrimitives:
    def test_seed_with_explicit_names(self):
        mem = ConceptMemory()
        mem.seed_primitives(property_names=["is_largest", "is_smallest", "has_holes"])
        assert mem.graph.get_concept("is_largest") is not None
        assert mem.graph.get_concept("is_smallest") is not None
        assert mem.graph.get_concept("has_holes") is not None
        assert len(mem.graph.concepts) == 3
        # All should be registered primitives
        for c in mem.graph.concepts.values():
            assert c.status == "registered"
            assert c.complexity == 1
            assert c.dependencies == []

    def test_seed_from_engine(self):
        mem = ConceptMemory()
        mem.seed_primitives()
        # Should have at least the 24 BOOLEAN_PROPERTIES plus derived
        assert len(mem.graph.concepts) >= 24
        assert all(c.status == "registered" for c in mem.graph.concepts.values())


class TestConceptMemoryRegister:
    def test_register_new_concept(self):
        mem = ConceptMemory()
        c = _make_concept("new_pred", "new_pred(x)", 2, status="validated")
        fn = lambda obj: obj.get("area", 0) > 5
        result = mem.register_concept(c, compute_fn=fn)
        assert result is True
        assert c.status == "registered"
        assert mem.graph.get_concept("new_pred") is not None
        assert mem.get_compute_fn("new_pred") is fn

    def test_register_duplicate_fails(self):
        mem = ConceptMemory()
        c1 = _make_concept("dup", "dup(x)")
        c2 = _make_concept("dup", "dup(x)")
        assert mem.register_concept(c1) is True
        assert mem.register_concept(c2) is False

    def test_register_without_compute_fn(self):
        mem = ConceptMemory()
        c = _make_concept("no_fn", "no_fn(x)")
        mem.register_concept(c)
        assert mem.get_compute_fn("no_fn") is None


class TestConceptMemoryRetrieve:
    def test_retrieve_for_task_sorted_by_score(self):
        mem = ConceptMemory()
        # Add concepts with varying promoted_tasks / complexity / fp
        c1 = _make_concept("high_score", "high(x)", 1, promoted_tasks=["t1", "t2", "t3"])
        c2 = _make_concept("low_score", "low(x)", 5, false_positives=3)
        c3 = _make_concept("mid_score", "mid(x)", 2, promoted_tasks=["t1"])
        for c in [c1, c2, c3]:
            mem.register_concept(c)

        retrieved = mem.retrieve_for_task({}, max_concepts=2)
        assert len(retrieved) == 2
        # high_score should come first (30 - 1 - 0 = 29)
        assert retrieved[0].name == "high_score"

    def test_retrieve_max_concepts(self):
        mem = ConceptMemory()
        for i in range(10):
            mem.register_concept(_make_concept(f"c_{i}", f"c_{i}(x)"))
        retrieved = mem.retrieve_for_task({}, max_concepts=5)
        assert len(retrieved) == 5

    def test_retrieve_empty(self):
        mem = ConceptMemory()
        assert mem.retrieve_for_task({}) == []

    def test_retrieve_only_registered(self):
        mem = ConceptMemory()
        c_reg = _make_concept("registered_one", "reg(x)", status="proposed")
        mem.register_concept(c_reg)  # register_concept sets status to "registered"
        c_proposed = _make_concept("proposed_one", "prop(x)", status="proposed")
        mem.graph.add_concept(c_proposed)  # add directly without registering

        retrieved = mem.retrieve_for_task({}, max_concepts=10)
        names = [c.name for c in retrieved]
        assert "registered_one" in names
        assert "proposed_one" not in names


class TestConceptMemorySummary:
    def test_summary_delegates_to_graph(self):
        mem = ConceptMemory()
        mem.seed_primitives(property_names=["p1", "p2", "p3"])
        s = mem.summary
        assert s["total_concepts"] == 3
        assert s["n_primitives"] == 3
        assert s["n_composed"] == 0
