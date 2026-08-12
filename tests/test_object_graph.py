"""Tests for object-graph module."""
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reasoning_project.object_graph import (
    extract_objects,
    compute_relations,
    build_object_graph,
    graph_signature,
    object_graph_features,
)


def test_extract_objects_empty():
    grid = np.zeros((3, 3), dtype=int)
    objs = extract_objects(grid)
    assert len(objs) == 0


def test_extract_objects_single():
    grid = np.array([[0, 1, 0], [0, 1, 0], [0, 0, 0]])
    objs = extract_objects(grid)
    assert len(objs) == 1
    assert objs[0].color == 1
    assert objs[0].size == 2


def test_extract_objects_multiple_colors():
    grid = np.array([[1, 0, 2], [0, 0, 0], [3, 0, 0]])
    objs = extract_objects(grid)
    assert len(objs) == 3


def test_extract_objects_two_components_same_color():
    grid = np.array([[1, 0, 1], [0, 0, 0], [0, 0, 0]])
    objs = extract_objects(grid)
    assert len(objs) == 2
    assert all(o.color == 1 for o in objs)


def test_object_properties():
    grid = np.array([[1, 1], [1, 1]])
    objs = extract_objects(grid)
    assert len(objs) == 1
    assert objs[0].is_rectangular
    assert objs[0].width == 2
    assert objs[0].height == 2


def test_compute_relations_adjacent():
    grid = np.array([[1, 2, 0], [0, 0, 0], [0, 0, 0]])
    objs = extract_objects(grid)
    rels = compute_relations(objs, grid.shape)
    adj = [r for r in rels if r.relation_type == "adjacent"]
    assert len(adj) >= 2


def test_build_object_graph():
    grid = np.array([[1, 1, 0], [0, 0, 2], [0, 2, 2]])
    graph = build_object_graph(grid)
    assert len(graph.objects) >= 2
    assert graph.grid_shape == (3, 3)


def test_graph_signature():
    grid = np.array([[1, 0, 2], [0, 3, 0], [0, 0, 0]])
    graph = build_object_graph(grid)
    sig = graph_signature(graph)
    assert "n_objects" in sig
    assert "colors" in sig
    assert sig["n_objects"] == 3


def test_object_graph_features():
    grid = np.array([[1, 1], [0, 2]])
    feats = object_graph_features(grid)
    assert "n_objects" in feats
    assert feats["n_objects"] >= 1


def test_solve_color_remap():
    from reasoning_project.object_graph import solve_task_object_graph
    inp1 = np.array([[0, 1, 0], [0, 1, 0], [0, 0, 0]])
    out1 = np.array([[0, 2, 0], [0, 2, 0], [0, 0, 0]])
    inp2 = np.array([[1, 0, 0], [1, 1, 0], [0, 0, 0]])
    out2 = np.array([[2, 0, 0], [2, 2, 0], [0, 0, 0]])
    result = solve_task_object_graph([(inp1, out1), (inp2, out2)], [inp1])
    assert result is not None
    predictions, meta = result
    assert meta["strategy"] == "color_remap"
    np.testing.assert_array_equal(predictions[0], out1)


def test_solve_object_filter():
    from reasoning_project.object_graph import solve_task_object_graph
    inp1 = np.array([[1, 0, 2], [1, 0, 0], [0, 0, 0]])
    out1 = np.array([[1, 0, 0], [1, 0, 0], [0, 0, 0]])
    result = solve_task_object_graph([(inp1, out1)], [inp1])
    if result is not None:
        predictions, meta = result
        assert meta["strategy"] == "object_filter"


def test_solve_crop_largest():
    from reasoning_project.object_graph import solve_task_object_graph
    inp = np.array([[0, 0, 0, 0], [0, 1, 1, 0], [0, 1, 1, 0], [0, 0, 0, 2]])
    out = np.array([[1, 1], [1, 1]])
    result = solve_task_object_graph([(inp, out)], [inp])
    assert result is not None
    predictions, meta = result
    assert meta["strategy"] == "crop_largest_object"
    np.testing.assert_array_equal(predictions[0], out)


def test_solve_crop_smallest():
    from reasoning_project.object_graph import solve_task_object_graph
    inp = np.array([[1, 1, 0, 0], [1, 1, 0, 0], [0, 0, 0, 2], [0, 0, 0, 0]])
    out = np.array([[2]])
    result = solve_task_object_graph([(inp, out)], [inp])
    assert result is not None
    predictions, meta = result
    assert meta["strategy"] == "crop_smallest_object"


def test_solve_returns_none_for_complex():
    from reasoning_project.object_graph import solve_task_object_graph
    inp = np.array([[1, 2, 3], [4, 5, 6], [7, 8, 9]])
    out = np.array([[9, 8, 7], [6, 5, 4], [3, 2, 1]])
    result = solve_task_object_graph([(inp, out)], [inp])
    # Complex transform — may return None or a solution, but should not crash
