"""Tests for perception layer — segmentation, objects, relations, matching."""
import numpy as np
import pytest
from geocat_arc.perception.grid import Grid
from geocat_arc.perception.segmentation import extract_connected_components
from geocat_arc.perception.objects import ARCObject, extract_objects, render_objects
from geocat_arc.perception.relations import build_relation_graph, left_of, above, same_color
from geocat_arc.perception.matching import match_objects, overall_similarity
from geocat_arc.perception.change_detection import detect_changes


SAMPLE_GRID = [
    [0, 0, 0, 0, 0],
    [0, 1, 1, 0, 0],
    [0, 1, 1, 0, 0],
    [0, 0, 0, 2, 2],
    [0, 0, 0, 2, 2],
]


class TestGrid:
    def test_from_list(self):
        g = Grid.from_list(SAMPLE_GRID)
        assert g.height == 5
        assert g.width == 5
        assert g.shape == (5, 5)

    def test_background_color(self):
        g = Grid.from_list(SAMPLE_GRID)
        assert g.background_color == 0

    def test_colors_used(self):
        g = Grid.from_list(SAMPLE_GRID)
        assert g.colors_used == {0, 1, 2}

    def test_cell(self):
        g = Grid.from_list(SAMPLE_GRID)
        assert g.cell(1, 1) == 1
        assert g.cell(3, 3) == 2
        assert g.cell(0, 0) == 0

    def test_subgrid(self):
        g = Grid.from_list(SAMPLE_GRID)
        sub = g.subgrid((1, 1, 3, 3))
        assert sub.height == 2
        assert sub.width == 2

    def test_equality(self):
        g1 = Grid.from_list(SAMPLE_GRID)
        g2 = Grid.from_list(SAMPLE_GRID)
        assert g1 == g2

    def test_roundtrip(self):
        g = Grid.from_list(SAMPLE_GRID)
        assert g.to_list() == SAMPLE_GRID


class TestSegmentation:
    def test_extract_components(self):
        g = Grid.from_list(SAMPLE_GRID)
        comps = extract_connected_components(g, connectivity=4)
        assert len(comps) == 2
        colors = {c.color for c in comps}
        assert colors == {1, 2}

    def test_component_sizes(self):
        g = Grid.from_list(SAMPLE_GRID)
        comps = extract_connected_components(g, connectivity=4)
        sizes = sorted(c.size for c in comps)
        assert sizes == [4, 4]

    def test_8connectivity(self):
        grid = [
            [0, 0, 0],
            [0, 1, 0],
            [0, 0, 1],
        ]
        g = Grid.from_list(grid)
        comps4 = extract_connected_components(g, connectivity=4)
        comps8 = extract_connected_components(g, connectivity=8)
        assert len(comps4) == 2
        assert len(comps8) == 1


class TestObjects:
    def test_extract_objects(self):
        g = Grid.from_list(SAMPLE_GRID)
        objs = extract_objects(g)
        assert len(objs) == 2

    def test_object_properties(self):
        g = Grid.from_list(SAMPLE_GRID)
        objs = extract_objects(g)
        for obj in objs:
            assert obj.size == 4
            assert obj.is_rectangle
            assert not obj.is_line

    def test_render_objects(self):
        g = Grid.from_list(SAMPLE_GRID)
        objs = extract_objects(g)
        rendered = render_objects(objs, 5, 5, background=0)
        assert rendered == g

    def test_object_with_hole(self):
        grid = [
            [0, 0, 0, 0, 0],
            [0, 1, 1, 1, 0],
            [0, 1, 0, 1, 0],
            [0, 1, 1, 1, 0],
            [0, 0, 0, 0, 0],
        ]
        g = Grid.from_list(grid)
        objs = extract_objects(g)
        ring = [o for o in objs if o.color == 1]
        assert len(ring) == 1
        assert ring[0].has_hole


class TestRelations:
    def test_build_relations(self):
        g = Grid.from_list(SAMPLE_GRID)
        objs = extract_objects(g)
        rels = build_relation_graph(objs)
        rel_types = {r.relation_type for r in rels}
        assert "same_size" in rel_types

    def test_left_of(self):
        g = Grid.from_list(SAMPLE_GRID)
        objs = extract_objects(g)
        obj_by_color = {o.color: o for o in objs}
        assert left_of(obj_by_color[1], obj_by_color[2])

    def test_above(self):
        g = Grid.from_list(SAMPLE_GRID)
        objs = extract_objects(g)
        obj_by_color = {o.color: o for o in objs}
        assert above(obj_by_color[1], obj_by_color[2])


class TestMatching:
    def test_identical_objects_match(self):
        g = Grid.from_list(SAMPLE_GRID)
        objs = extract_objects(g)
        matches = match_objects(objs, objs)
        assert len(matches) == 2
        for inp, out, sim in matches:
            assert sim > 0.9

    def test_different_grids(self):
        g1 = Grid.from_list(SAMPLE_GRID)
        g2 = Grid.from_list([
            [0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0],
            [0, 0, 3, 3, 0],
            [0, 0, 3, 3, 0],
            [0, 0, 0, 0, 0],
        ])
        objs1 = extract_objects(g1)
        objs2 = extract_objects(g2)
        matches = match_objects(objs1, objs2)
        assert len(matches) >= 1


class TestChangeDetection:
    def test_no_change(self):
        g = Grid.from_list(SAMPLE_GRID)
        report = detect_changes(g, g)
        assert report.num_cells_changed == 0
        assert report.cell_accuracy == 1.0

    def test_detect_recolor(self):
        g1 = Grid.from_list(SAMPLE_GRID)
        modified = [row[:] for row in SAMPLE_GRID]
        modified[1][1] = 3
        modified[1][2] = 3
        modified[2][1] = 3
        modified[2][2] = 3
        g2 = Grid.from_list(modified)
        report = detect_changes(g1, g2)
        assert report.num_cells_changed == 4
        assert len(report.objects_recolored) >= 1
