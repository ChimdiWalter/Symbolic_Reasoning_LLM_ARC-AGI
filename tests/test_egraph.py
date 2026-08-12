"""Tests for e-graph/equality-saturation module."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reasoning_project.egraph import (
    ProgramNode,
    EGraph,
    simplify_program,
    collapse_equivalent_candidates,
    build_egraph_from_candidates,
)


def test_program_node_cost():
    n = ProgramNode("identity")
    assert n.cost() == 20
    n2 = ProgramNode("rotate_90", ("angle", "90"))
    assert n2.cost() > 20


def test_egraph_add_and_find():
    eg = EGraph()
    n1 = ProgramNode("identity")
    c1 = eg.add(n1)
    assert eg.find(n1) == c1
    assert eg.n_classes == 1


def test_egraph_merge():
    eg = EGraph()
    n1 = ProgramNode("rotate_180")
    n2 = ProgramNode("rotate_180_alt")
    c1 = eg.add(n1)
    c2 = eg.add(n2)
    assert eg.n_classes == 2
    eg.merge(c1, c2)
    assert eg.n_classes == 1
    assert eg.equivalent(n1, n2)


def test_simplify_double_reflect():
    result = simplify_program(["reflect_horizontal", "reflect_horizontal"])
    assert result == ["identity"]


def test_simplify_rotate_360():
    result = simplify_program(["rotate_90", "rotate_270"])
    assert result == ["identity"]


def test_simplify_rotate_compose():
    result = simplify_program(["rotate_90", "rotate_90"])
    assert result == ["rotate_180"]


def test_simplify_no_change():
    result = simplify_program(["rotate_90", "reflect_horizontal"])
    assert "rotate_90" in result
    assert "reflect_horizontal" in result


def test_collapse_equivalent():
    candidates = [
        (["reflect_horizontal", "reflect_horizontal"], 0.0),
        (["identity"], 0.0),
        (["rotate_90"], 0.5),
    ]
    collapsed = collapse_equivalent_candidates(candidates)
    assert len(collapsed) == 2


def test_build_egraph():
    programs = [
        ["identity"],
        ["reflect_horizontal", "reflect_horizontal"],
        ["rotate_90"],
    ]
    eg, mapping = build_egraph_from_candidates(programs)
    assert eg.n_classes <= 3
