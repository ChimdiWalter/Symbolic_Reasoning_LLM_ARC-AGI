"""Tests for visual logic predicates and propositions."""
import pytest
from geocat_arc.perception.objects import ARCObject
from geocat_arc.visual_logic_topos.predicates import (
    HasColor, SameColor, IsRectangle, IsLine, HasHole, SameShape,
    IsLargest, IsSmallest, TouchesBorder, Inside, LeftOf, Above,
)
from geocat_arc.visual_logic_topos.proposition import AtomicProp, And, Or, Not, Implies
from geocat_arc.visual_logic_topos.quantifiers import ForAll, Exists
from geocat_arc.visual_logic_topos.truth_table import build_truth_table


def _make_obj(id, cells, color, bbox):
    return ARCObject(id=id, cells=frozenset(cells), color=color, bounding_box=bbox)


OBJ_RED = _make_obj(0, [(1, 1), (1, 2), (2, 1), (2, 2)], color=2, bbox=(1, 1, 3, 3))
OBJ_BLUE = _make_obj(1, [(4, 4), (4, 5)], color=1, bbox=(4, 4, 5, 6))
OBJ_RED2 = _make_obj(2, [(6, 1), (6, 2), (7, 1), (7, 2)], color=2, bbox=(6, 1, 8, 3))
OBJECTS = [OBJ_RED, OBJ_BLUE, OBJ_RED2]


class TestPredicates:
    def test_has_color(self):
        assert HasColor(2)(OBJ_RED)
        assert not HasColor(2)(OBJ_BLUE)

    def test_same_color(self):
        assert SameColor()(OBJ_RED, OBJ_RED2)
        assert not SameColor()(OBJ_RED, OBJ_BLUE)

    def test_is_rectangle(self):
        assert IsRectangle()(OBJ_RED)

    def test_is_line(self):
        assert IsLine()(OBJ_BLUE)
        assert not IsLine()(OBJ_RED)

    def test_same_shape(self):
        assert SameShape()(OBJ_RED, OBJ_RED2)

    def test_is_largest(self):
        pred = IsLargest(OBJECTS)
        assert pred(OBJ_RED)
        assert not pred(OBJ_BLUE)

    def test_touches_border(self):
        pred = TouchesBorder(10, 10)
        assert not pred(OBJ_RED)
        border_obj = _make_obj(3, [(0, 0)], color=1, bbox=(0, 0, 1, 1))
        assert pred(border_obj)


class TestPropositions:
    def test_atomic(self):
        p = AtomicProp(HasColor(2))
        assert p.evaluate(OBJ_RED)
        assert not p.evaluate(OBJ_BLUE)

    def test_and(self):
        p = And(AtomicProp(HasColor(2)), AtomicProp(IsRectangle()))
        assert p.evaluate(OBJ_RED)

    def test_or(self):
        p = Or(AtomicProp(HasColor(2)), AtomicProp(HasColor(1)))
        assert p.evaluate(OBJ_RED)
        assert p.evaluate(OBJ_BLUE)

    def test_not(self):
        p = Not(AtomicProp(HasColor(2)))
        assert p.evaluate(OBJ_BLUE)
        assert not p.evaluate(OBJ_RED)

    def test_implies(self):
        p = Implies(AtomicProp(HasColor(2)), AtomicProp(IsRectangle()))
        assert p.evaluate(OBJ_RED)
        assert p.evaluate(OBJ_BLUE)

    def test_operator_overloads(self):
        p = AtomicProp(HasColor(2)) & AtomicProp(IsRectangle())
        assert p.evaluate(OBJ_RED)


class TestQuantifiers:
    def test_forall_true(self):
        prop = AtomicProp(IsRectangle())
        q = ForAll(prop, [OBJ_RED, OBJ_RED2])
        assert q.evaluate()

    def test_forall_false(self):
        prop = AtomicProp(HasColor(2))
        q = ForAll(prop, OBJECTS)
        assert not q.evaluate()

    def test_exists_true(self):
        prop = AtomicProp(HasColor(1))
        q = Exists(prop, OBJECTS)
        assert q.evaluate()


class TestTruthTable:
    def test_truth_table(self):
        prop = AtomicProp(HasColor(2))
        table = build_truth_table(prop, OBJECTS)
        assert table[0] is True
        assert table[1] is False
        assert table[2] is True
