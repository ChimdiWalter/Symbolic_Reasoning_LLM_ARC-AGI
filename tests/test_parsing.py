import numpy as np

from reasoning_project.parsing import adjacency_edges, parse_objects, scene_graph


def test_parse_objects_and_relations():
    grid = np.zeros((6, 6), dtype=int)
    grid[1:3, 1:3] = 1
    grid[1:3, 3:5] = 2
    objects = parse_objects(grid)
    assert len(objects) == 2
    assert sorted(obj.size for obj in objects) == [4, 4]
    assert adjacency_edges(objects) == [(0, 1)]
    graph = scene_graph(grid)
    assert graph["summary"]["object_count"] == 2
    assert graph["relations"]["adjacency"] == [[0, 1]]


def test_hole_count_for_ring_component():
    grid = np.zeros((6, 6), dtype=int)
    grid[1:5, 1:5] = 3
    grid[2:4, 2:4] = 0
    objects = parse_objects(grid)
    assert len(objects) == 1
    assert objects[0].holes == 1

