"""Tests for new operators — pattern, frame, object_logic, set-level ops."""
import numpy as np
import pytest
from geocat_arc.perception.grid import Grid
from geocat_arc.perception.objects import ARCObject, extract_objects
from geocat_arc.categorical_dsl.operators_basic import (
    RecolorAll, TranslateAll, ReflectAll, RotateAll, Render,
)
from geocat_arc.categorical_dsl.operators_pattern import (
    RepeatTilePattern, ExtendLineOrPattern,
)
from geocat_arc.categorical_dsl.operators_frame import (
    CropToObject, CropToFrame, ExtractInnerFrame, FillEnclosedRegion,
)
from geocat_arc.categorical_dsl.operators_object_logic import (
    CopyToPosition, CopyRelativeToAnchor, ConditionalRecolor,
    ReplaceObjectByShapeMatch, ObjectUnion, ObjectIntersection,
    ObjectDifference, CountBasedSelect,
)
from geocat_arc.visual_logic_topos.predicates import HasColor


def _make_obj(id, cells, color):
    rows = [r for r, c in cells]
    cols = [c for r, c in cells]
    bbox = (min(rows), min(cols), max(rows) + 1, max(cols) + 1)
    return ARCObject(id=id, cells=frozenset(cells), color=color, bounding_box=bbox)


GRID_5x5 = [
    [0, 0, 0, 0, 0],
    [0, 1, 1, 0, 0],
    [0, 1, 1, 0, 0],
    [0, 0, 0, 2, 2],
    [0, 0, 0, 2, 2],
]


class TestSetLevelOperators:
    def test_recolor_all(self):
        g = Grid.from_list(GRID_5x5)
        objs = extract_objects(g)
        result = RecolorAll().apply(objs, 5)
        assert all(o.color == 5 for o in result)

    def test_translate_all(self):
        g = Grid.from_list(GRID_5x5)
        objs = extract_objects(g)
        result = TranslateAll().apply(objs, (1, 0))
        for orig, moved in zip(objs, result):
            orig_c = orig.centroid
            moved_c = moved.centroid
            assert abs(moved_c[0] - orig_c[0] - 1.0) < 0.01

    def test_reflect_all(self):
        g = Grid.from_list(GRID_5x5)
        objs = extract_objects(g)
        result = ReflectAll().apply(objs, "horizontal")
        assert len(result) == len(objs)

    def test_rotate_all(self):
        g = Grid.from_list(GRID_5x5)
        objs = extract_objects(g)
        result = RotateAll().apply(objs, 90)
        assert len(result) == len(objs)

    def test_render_dynamic_size(self):
        objs = [_make_obj(0, {(0, 0), (0, 1), (1, 0), (1, 1)}, 1)]
        r = Render()
        result = r.apply(objs, _ctx={"height": 5, "width": 5, "background": 0})
        assert result.height == 5
        assert result.width == 5

    def test_render_infers_size(self):
        objs = [_make_obj(0, {(3, 4)}, 1)]
        r = Render()
        result = r.apply(objs)
        assert result.height >= 4
        assert result.width >= 5


class TestPatternOperators:
    def test_repeat_tile_horizontal(self):
        g = Grid.from_list([[1, 2], [3, 4]])
        op = RepeatTilePattern(direction="horizontal", repeats=3)
        result = op.apply(g)
        assert result.width == 6
        assert result.height == 2

    def test_repeat_tile_vertical(self):
        g = Grid.from_list([[1, 2], [3, 4]])
        op = RepeatTilePattern(direction="vertical", repeats=2)
        result = op.apply(g)
        assert result.height == 4
        assert result.width == 2

    def test_repeat_tile_both(self):
        g = Grid.from_list([[1]])
        op = RepeatTilePattern(direction="both", repeats=3)
        result = op.apply(g)
        assert result.height == 3
        assert result.width == 3

    def test_repeat_tile_bad_direction(self):
        g = Grid.from_list([[1]])
        op = RepeatTilePattern(direction="diagonal", repeats=2)
        with pytest.raises(ValueError):
            op.apply(g)

    def test_extend_line_horizontal(self):
        line_obj = _make_obj(0, {(2, 1), (2, 2), (2, 3)}, 1)
        op = ExtendLineOrPattern(grid_h=5, grid_w=5)
        result = op.apply([line_obj])
        assert len(result) == 1
        assert result[0].size == 5

    def test_extend_line_vertical(self):
        line_obj = _make_obj(0, {(0, 3), (1, 3), (2, 3)}, 1)
        op = ExtendLineOrPattern(grid_h=5, grid_w=5)
        result = op.apply([line_obj])
        assert result[0].size == 5

    def test_extend_non_line_unchanged(self):
        square = _make_obj(0, {(0, 0), (0, 1), (1, 0), (1, 1)}, 1)
        op = ExtendLineOrPattern(grid_h=5, grid_w=5)
        result = op.apply([square])
        assert result[0].size == square.size


class TestFrameOperators:
    def test_crop_to_object(self):
        g = Grid.from_list(GRID_5x5)
        objs = extract_objects(g)
        obj1 = [o for o in objs if o.color == 1][0]
        result = CropToObject().apply(g, obj1)
        assert result.height == 2
        assert result.width == 2

    def test_extract_inner_frame(self):
        grid = [
            [1, 1, 1, 1, 1],
            [1, 0, 0, 0, 1],
            [1, 0, 2, 0, 1],
            [1, 0, 0, 0, 1],
            [1, 1, 1, 1, 1],
        ]
        g = Grid.from_list(grid)
        frame_obj = _make_obj(0, {
            (0, 0), (0, 1), (0, 2), (0, 3), (0, 4),
            (1, 0), (1, 4),
            (2, 0), (2, 4),
            (3, 0), (3, 4),
            (4, 0), (4, 1), (4, 2), (4, 3), (4, 4),
        }, 1)
        result = ExtractInnerFrame().apply(g, frame_obj)
        assert result.height == 3
        assert result.width == 3
        assert result.cell(1, 1) == 2

    def test_extract_inner_frame_too_small(self):
        tiny = _make_obj(0, {(0, 0), (0, 1), (1, 0), (1, 1)}, 1)
        g = Grid.from_list([[1, 1], [1, 1]])
        with pytest.raises(ValueError):
            ExtractInnerFrame().apply(g, tiny)

    def test_extract_inner_frame_applicable(self):
        tiny = _make_obj(0, {(0, 0), (0, 1), (1, 0), (1, 1)}, 1)
        assert not ExtractInnerFrame().applicable(Grid.from_list([[0]]), tiny)

    def test_fill_enclosed_region(self):
        grid = [
            [0, 0, 0, 0, 0],
            [0, 1, 1, 1, 0],
            [0, 1, 0, 1, 0],
            [0, 1, 1, 1, 0],
            [0, 0, 0, 0, 0],
        ]
        g = Grid.from_list(grid)
        result = FillEnclosedRegion().apply(g, 3)
        assert result.cell(2, 2) == 3
        assert result.cell(0, 0) == 0

    def test_fill_enclosed_no_enclosed(self):
        grid = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]
        g = Grid.from_list(grid)
        result = FillEnclosedRegion().apply(g, 5)
        assert result == g


class TestObjectLogicOperators:
    def test_copy_to_position(self):
        obj = _make_obj(0, {(0, 0), (0, 1), (1, 0), (1, 1)}, 1)
        result = CopyToPosition().apply(obj, (3, 3, 5, 5))
        assert (3, 3) in result.cells
        assert (0, 0) not in result.cells

    def test_copy_relative_to_anchor(self):
        obj = _make_obj(0, {(0, 0)}, 1)
        anchor = _make_obj(1, {(5, 5)}, 2)
        result = CopyRelativeToAnchor().apply(obj, anchor, (1, 1))
        assert (6, 6) in result.cells

    def test_conditional_recolor(self):
        objs = [
            _make_obj(0, {(0, 0)}, 1),
            _make_obj(1, {(1, 1)}, 2),
            _make_obj(2, {(2, 2)}, 1),
        ]
        result = ConditionalRecolor().apply(objs, HasColor(1), 5)
        assert result[0].color == 5
        assert result[1].color == 2
        assert result[2].color == 5

    def test_replace_by_shape(self):
        square1 = _make_obj(0, {(0, 0), (0, 1), (1, 0), (1, 1)}, 1)
        square2 = _make_obj(1, {(3, 3), (3, 4), (4, 3), (4, 4)}, 2)
        replacement = _make_obj(2, {(0, 0), (0, 1), (1, 0), (1, 1)}, 5)
        result = ReplaceObjectByShapeMatch().apply([square1, square2], replacement)
        assert result[0].color == 5
        assert result[1].color == 5

    def test_object_union(self):
        a = _make_obj(0, {(0, 0), (0, 1)}, 1)
        b = _make_obj(1, {(1, 0), (1, 1)}, 1)
        result = ObjectUnion().apply(a, b)
        assert result.size == 4
        assert (0, 0) in result.cells
        assert (1, 1) in result.cells

    def test_object_intersection(self):
        a = _make_obj(0, {(0, 0), (0, 1), (1, 0)}, 1)
        b = _make_obj(1, {(0, 0), (0, 1), (1, 1)}, 2)
        result = ObjectIntersection().apply(a, b)
        assert result.size == 2
        assert (0, 0) in result.cells

    def test_object_intersection_empty_raises(self):
        a = _make_obj(0, {(0, 0)}, 1)
        b = _make_obj(1, {(5, 5)}, 2)
        with pytest.raises(ValueError):
            ObjectIntersection().apply(a, b)

    def test_object_difference(self):
        a = _make_obj(0, {(0, 0), (0, 1), (1, 0)}, 1)
        b = _make_obj(1, {(0, 0)}, 2)
        result = ObjectDifference().apply(a, b)
        assert result.size == 2
        assert (0, 0) not in result.cells

    def test_object_difference_empty_raises(self):
        a = _make_obj(0, {(0, 0)}, 1)
        b = _make_obj(1, {(0, 0)}, 2)
        with pytest.raises(ValueError):
            ObjectDifference().apply(a, b)

    def test_count_select_largest(self):
        small = _make_obj(0, {(0, 0)}, 1)
        big = _make_obj(1, {(1, 0), (1, 1), (2, 0), (2, 1)}, 2)
        result = CountBasedSelect(mode="largest").apply([small, big])
        assert result.id == big.id

    def test_count_select_smallest(self):
        small = _make_obj(0, {(0, 0)}, 1)
        big = _make_obj(1, {(1, 0), (1, 1), (2, 0), (2, 1)}, 2)
        result = CountBasedSelect(mode="smallest").apply([small, big])
        assert result.id == small.id

    def test_count_select_empty_raises(self):
        with pytest.raises(ValueError):
            CountBasedSelect(mode="largest").apply([])

    def test_count_select_applicable(self):
        assert not CountBasedSelect().applicable([])
        assert CountBasedSelect().applicable([_make_obj(0, {(0, 0)}, 1)])
