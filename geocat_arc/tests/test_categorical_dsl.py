"""Tests for the typed categorical DSL."""
import pytest
from geocat_arc.perception.grid import Grid
from geocat_arc.perception.objects import ARCObject, extract_objects
from geocat_arc.categorical_dsl.types import ArcType
from geocat_arc.categorical_dsl.morphism import Morphism
from geocat_arc.categorical_dsl.type_checker import check_composition, TypeCheckError
from geocat_arc.categorical_dsl.operators_basic import Segment, Filter, Render, Copy
from geocat_arc.categorical_dsl.operators_color import Recolor
from geocat_arc.categorical_dsl.operators_spatial import Translate, Rotate90, Reflect
from geocat_arc.categorical_dsl.composition import compose
from geocat_arc.categorical_dsl.program import Program
from geocat_arc.visual_logic_topos.predicates import HasColor


SAMPLE_GRID = [
    [0, 0, 0, 0, 0],
    [0, 1, 1, 0, 0],
    [0, 1, 1, 0, 0],
    [0, 0, 0, 2, 2],
    [0, 0, 0, 2, 2],
]


class TestTypeChecker:
    def test_valid_composition(self):
        seg = Segment()
        render = Render(5, 5)
        assert check_composition([seg, render])

    def test_invalid_composition(self):
        recolor = Recolor()
        seg = Segment()
        with pytest.raises(TypeCheckError):
            check_composition([recolor, seg])

    def test_single_morphism(self):
        assert check_composition([Segment()])


class TestOperators:
    def test_segment(self):
        g = Grid.from_list(SAMPLE_GRID)
        seg = Segment()
        objs = seg.apply(g)
        assert len(objs) == 2

    def test_filter(self):
        g = Grid.from_list(SAMPLE_GRID)
        objs = Segment().apply(g)
        filtered = Filter().apply(objs, HasColor(1))
        assert len(filtered) == 1
        assert filtered[0].color == 1

    def test_recolor(self):
        g = Grid.from_list(SAMPLE_GRID)
        objs = Segment().apply(g)
        obj = objs[0]
        recolored = Recolor().apply(obj, 5)
        assert recolored.color == 5
        assert recolored.cells == obj.cells

    def test_copy(self):
        g = Grid.from_list(SAMPLE_GRID)
        objs = Segment().apply(g)
        copied = Copy().apply(objs[0])
        assert copied.cells == objs[0].cells
        assert copied.color == objs[0].color

    def test_translate(self):
        g = Grid.from_list(SAMPLE_GRID)
        objs = Segment().apply(g)
        translated = Translate().apply(objs[0], (1, 1))
        orig_centroid = objs[0].centroid
        new_centroid = translated.centroid
        assert abs(new_centroid[0] - orig_centroid[0] - 1) < 0.01
        assert abs(new_centroid[1] - orig_centroid[1] - 1) < 0.01

    def test_render(self):
        g = Grid.from_list(SAMPLE_GRID)
        objs = Segment().apply(g)
        rendered = Render(5, 5).apply(objs)
        assert rendered == g

    def test_reflect(self):
        g = Grid.from_list(SAMPLE_GRID)
        objs = Segment().apply(g)
        reflected = Reflect().apply(objs[0], "horizontal")
        assert reflected.size == objs[0].size

    def test_rotate(self):
        g = Grid.from_list(SAMPLE_GRID)
        objs = Segment().apply(g)
        rotated = Rotate90().apply(objs[0], 90)
        assert rotated.size == objs[0].size


class TestComposition:
    def test_compose_valid(self):
        seg = Segment()
        render = Render(5, 5)
        composed = compose(seg, render)
        g = Grid.from_list(SAMPLE_GRID)
        result = composed.apply(g)
        assert result == g

    def test_compose_invalid(self):
        with pytest.raises(TypeCheckError):
            compose(Recolor(), Segment())


class TestProgram:
    def test_program_execution(self):
        g = Grid.from_list(SAMPLE_GRID)
        prog = Program()
        prog.add_step(Segment())
        prog.add_step(Render(5, 5))
        result = prog.apply(g)
        assert result == g

    def test_program_type_check(self):
        prog = Program()
        prog.add_step(Segment())
        prog.add_step(Render(5, 5))
        assert prog.type_check()

    def test_program_depth(self):
        prog = Program()
        prog.add_step(Segment())
        prog.add_step(Render(5, 5))
        assert prog.depth == 2

    def test_program_serialization(self):
        prog = Program()
        prog.add_step(Segment())
        d = prog.to_dict()
        assert "steps" in d
        assert d["depth"] == 1
