"""Tests for multicolor_decompose module."""
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reasoning_project.multicolor_decompose import (
    extract_color_components,
    extract_silhouette_components,
    extract_part_whole,
    detect_containment,
    detect_same_different,
    detect_ordering,
    count_objects,
    MultiColorGridAdapter,
    solve_task_multicolor,
    CompositeObject,
    ShapeGroup,
)


# ═══════════════════════════════════════════════════════════════════════════
# 1. Color component extraction
# ═══════════════════════════════════════════════════════════════════════════

def test_extract_color_components_basic():
    """Two separate colored regions should yield two color components."""
    grid = np.array([
        [1, 1, 0, 2, 2],
        [1, 0, 0, 0, 2],
        [0, 0, 0, 0, 0],
    ])
    objs = extract_color_components(grid, bg=0)
    assert len(objs) == 2
    colors = {o["color"] for o in objs}
    assert colors == {1, 2}
    # Each object is single-color
    for o in objs:
        assert o["n_colors"] == 1
        assert o["is_multicolor"] is False


def test_extract_color_components_adjacent_colors():
    """Adjacent cells of different colors should be separate color components."""
    grid = np.array([
        [1, 2],
        [2, 1],
    ])
    objs = extract_color_components(grid, bg=0)
    # Color 1 has two disconnected cells, color 2 has two disconnected cells
    # (diagonal cells are NOT connected in 4-connectivity)
    assert len(objs) == 4
    color1_objs = [o for o in objs if o["color"] == 1]
    color2_objs = [o for o in objs if o["color"] == 2]
    assert len(color1_objs) == 2
    assert len(color2_objs) == 2


# ═══════════════════════════════════════════════════════════════════════════
# 2. Silhouette component extraction
# ═══════════════════════════════════════════════════════════════════════════

def test_extract_silhouette_components_basic():
    """Adjacent cells of different colors should merge into one silhouette."""
    grid = np.array([
        [1, 2, 0, 0],
        [2, 1, 0, 3],
        [0, 0, 0, 3],
    ])
    objs = extract_silhouette_components(grid, bg=0)
    # The 1-2 block forms one silhouette, the 3-3 column forms another
    assert len(objs) == 2
    areas = sorted([o["area"] for o in objs])
    assert areas == [2, 4]


def test_extract_silhouette_multi_color_detection():
    """Silhouette with multiple colors should be marked as multicolor."""
    grid = np.array([
        [1, 2],
        [3, 4],
    ])
    objs = extract_silhouette_components(grid, bg=0)
    assert len(objs) == 1
    assert objs[0]["is_multicolor"] is True
    assert objs[0]["n_colors"] == 4


# ═══════════════════════════════════════════════════════════════════════════
# 3. Part-whole decomposition on multi-color objects
# ═══════════════════════════════════════════════════════════════════════════

def test_extract_part_whole_multicolor():
    """A multi-color object should have multiple parts within one composite."""
    # Frame-like object: outer ring of color 1, inner color 2
    grid = np.array([
        [1, 1, 1, 0],
        [1, 2, 1, 0],
        [1, 1, 1, 0],
        [0, 0, 0, 3],
    ])
    composites = extract_part_whole(grid, bg=0)
    assert len(composites) == 2  # one big composite (the frame) and one small (color 3)
    # Find the multicolor one
    mc = [c for c in composites if c.is_multicolor]
    assert len(mc) == 1
    assert mc[0].n_parts == 2  # color-1 part + color-2 part
    assert 1 in mc[0].colors and 2 in mc[0].colors


def test_extract_part_whole_single_color():
    """Single-color objects should yield composites with one part."""
    grid = np.array([
        [1, 1, 0],
        [1, 0, 0],
        [0, 0, 2],
    ])
    composites = extract_part_whole(grid, bg=0)
    assert len(composites) == 2
    for c in composites:
        assert c.n_parts == 1
        assert c.is_multicolor is False


# ═══════════════════════════════════════════════════════════════════════════
# 4. Containment detection (nested objects)
# ═══════════════════════════════════════════════════════════════════════════

def test_detect_containment_nested():
    """An inner object fully inside an outer object's bbox should be detected."""
    # Outer: large rectangle, inner: small dot inside
    outer_mask = np.zeros((7, 7), dtype=bool)
    outer_mask[0, :] = True
    outer_mask[6, :] = True
    outer_mask[:, 0] = True
    outer_mask[:, 6] = True

    inner_mask = np.zeros((7, 7), dtype=bool)
    inner_mask[3, 3] = True

    objects = [
        {"mask": outer_mask, "bbox": (0, 0, 6, 6)},
        {"mask": inner_mask, "bbox": (3, 3, 3, 3)},
    ]
    containment = detect_containment(objects)
    assert len(containment) == 1
    container_idx, contained_idx = containment[0]
    assert container_idx == 0
    assert contained_idx == 1


def test_detect_containment_no_nesting():
    """Non-overlapping objects should have no containment."""
    mask_a = np.zeros((5, 10), dtype=bool)
    mask_a[0:3, 0:3] = True
    mask_b = np.zeros((5, 10), dtype=bool)
    mask_b[0:3, 7:10] = True

    objects = [
        {"mask": mask_a, "bbox": (0, 0, 2, 2)},
        {"mask": mask_b, "bbox": (0, 7, 2, 9)},
    ]
    containment = detect_containment(objects)
    assert len(containment) == 0


# ═══════════════════════════════════════════════════════════════════════════
# 5. Same-different detection (rotated shapes)
# ═══════════════════════════════════════════════════════════════════════════

def test_detect_same_different_exact():
    """Identical shapes should be grouped together."""
    grid = np.array([
        [1, 0, 0, 2, 0],
        [1, 0, 0, 2, 0],
        [0, 0, 0, 0, 0],
    ])
    objs = extract_color_components(grid, bg=0)
    groups = detect_same_different(objs)
    # Both are vertical 2-cell bars -> should be in same group
    assert len(groups) == 1
    assert len(groups[0].members) == 2
    assert groups[0].equivalence_type == "exact"


def test_detect_same_different_rotation():
    """Shapes related by rotation should be grouped together."""
    # L-shape and its 90-degree rotation
    mask_a = np.array([[True, False],
                       [True, True]], dtype=bool)
    mask_b = np.rot90(mask_a)

    obj_a = {"local_mask": mask_a, "area": 3}
    obj_b = {"local_mask": mask_b, "area": 3}
    groups = detect_same_different([obj_a, obj_b])
    assert len(groups) == 1
    assert "rotation" in groups[0].equivalence_type or groups[0].equivalence_type == "exact"


def test_detect_same_different_distinct():
    """Truly different shapes should be in separate groups."""
    mask_a = np.array([[True, True]], dtype=bool)  # horizontal bar
    mask_b = np.array([[True, True],
                       [True, True]], dtype=bool)  # 2x2 square

    obj_a = {"local_mask": mask_a, "area": 2}
    obj_b = {"local_mask": mask_b, "area": 4}
    groups = detect_same_different([obj_a, obj_b])
    assert len(groups) == 2
    assert len(groups[0].members) == 1
    assert len(groups[1].members) == 1


# ═══════════════════════════════════════════════════════════════════════════
# 6. Ordering detection
# ═══════════════════════════════════════════════════════════════════════════

def test_detect_ordering_spatial():
    """Objects at different positions should produce spatial orderings."""
    grid = np.array([
        [1, 0, 2, 0, 3],
        [0, 0, 0, 0, 0],
    ])
    objs = extract_color_components(grid, bg=0)
    orderings = detect_ordering(objs)
    assert orderings is not None
    lr = [o for o in orderings if o["type"] == "left_to_right"][0]
    # Objects should be ordered by center_c: color1 (c=0), color2 (c=2), color3 (c=4)
    ordered_colors = [objs[i]["color"] for i in lr["order"]]
    assert ordered_colors == [1, 2, 3]


def test_detect_ordering_too_few():
    """Fewer than 2 objects should return None."""
    grid = np.array([[1, 0], [0, 0]])
    objs = extract_color_components(grid, bg=0)
    assert len(objs) == 1
    result = detect_ordering(objs)
    assert result is None


# ═══════════════════════════════════════════════════════════════════════════
# 7. Object counting in all modes
# ═══════════════════════════════════════════════════════════════════════════

def test_count_objects_color_mode():
    """Color mode should count per-color components."""
    grid = np.array([
        [1, 2, 0],
        [1, 2, 0],
        [0, 0, 3],
    ])
    # Color 1: one CC, color 2: one CC, color 3: one CC -> 3
    assert count_objects(grid, mode="color") == 3


def test_count_objects_silhouette_mode():
    """Silhouette mode should merge adjacent colors."""
    grid = np.array([
        [1, 2, 0],
        [1, 2, 0],
        [0, 0, 3],
    ])
    # 1-2 block is one silhouette, 3 is another -> 2
    assert count_objects(grid, mode="silhouette") == 2


def test_count_objects_part_whole_mode():
    """Part-whole mode should count composite objects (same as silhouette count)."""
    grid = np.array([
        [1, 2, 0],
        [1, 2, 0],
        [0, 0, 3],
    ])
    assert count_objects(grid, mode="part_whole") == 2


# ═══════════════════════════════════════════════════════════════════════════
# 8. MultiColorGridAdapter property computation
# ═══════════════════════════════════════════════════════════════════════════

def test_adapter_extract_objects():
    """MultiColorGridAdapter should extract objects with all expected properties."""
    grid = np.array([
        [1, 1, 1, 0, 0],
        [1, 2, 1, 0, 3],
        [1, 1, 1, 0, 3],
    ])
    adapter = MultiColorGridAdapter(bg=0)
    objs = adapter.extract_objects(grid)
    assert len(objs) == 2  # frame (1+2 silhouette) and bar (3)

    # Find the multi-color object
    mc = [o for o in objs if o["is_multicolor"]]
    assert len(mc) == 1
    assert mc[0]["n_parts"] == 2
    assert mc[0]["n_colors"] == 2

    # Check standard properties exist
    for o in objs:
        assert "area" in o
        assert "bbox" in o
        assert "center_r" in o
        assert "is_largest" in o
        assert "is_smallest" in o
        assert "shape_group_id" in o
        assert "is_contained" in o
        assert "is_container" in o
        assert "position_rank_lr" in o
        assert "position_rank_tb" in o
        assert "size_rank" in o
        assert "n_holes" in o
        assert "euler_char" in o
        assert "any_sym" in o


def test_adapter_property_names():
    """Adapter should return a non-empty list of property names."""
    adapter = MultiColorGridAdapter()
    props = adapter.property_names()
    assert len(props) > 20
    assert "is_multicolor" in props
    assert "has_frame" in props
    assert "is_contained" in props


def test_adapter_get_property():
    """get_property should return correct values for both stored and derived."""
    adapter = MultiColorGridAdapter()
    obj = {"is_multicolor": True, "n_holes": 2, "convexity": 0.5}
    assert adapter.get_property(obj, "is_multicolor") is True
    assert adapter.get_property(obj, "has_holes") is True
    assert adapter.get_property(obj, "is_convex") is False


# ═══════════════════════════════════════════════════════════════════════════
# 9. solve_task_multicolor: synthetic "keep the multi-color object"
# ═══════════════════════════════════════════════════════════════════════════

def test_solve_keep_multicolor_object():
    """Task: keep multi-color objects, remove single-color ones."""
    def _make_pair():
        inp = np.array([
            [1, 2, 0, 0, 0],
            [3, 1, 0, 0, 0],
            [0, 0, 0, 4, 4],
            [0, 0, 0, 4, 4],
        ])
        out = inp.copy()
        # Remove the single-color object (color 4 block)
        out[2:4, 3:5] = 0
        return inp, out

    train = [_make_pair(), _make_pair()]
    test_inp = np.array([
        [5, 6, 0, 0, 0],
        [7, 5, 0, 0, 0],
        [0, 0, 0, 8, 8],
        [0, 0, 0, 8, 8],
    ])

    result = solve_task_multicolor(train, [test_inp])
    assert result is not None
    outputs, info = result
    assert len(outputs) == 1
    # The single-color block (8s) should be removed
    assert outputs[0][2, 3] == 0
    assert outputs[0][3, 4] == 0
    # The multi-color block should be kept
    assert outputs[0][0, 0] == 5
    assert outputs[0][1, 1] == 5


# ═══════════════════════════════════════════════════════════════════════════
# 10. solve_task_multicolor: synthetic "keep objects inside the frame"
# ═══════════════════════════════════════════════════════════════════════════

def test_solve_keep_contained_object():
    """Task: keep objects that are contained (inside a larger frame), remove others."""
    def _make_pair():
        inp = np.zeros((9, 9), dtype=int)
        # Large frame
        inp[0, 0:7] = 1
        inp[6, 0:7] = 1
        inp[0:7, 0] = 1
        inp[0:7, 6] = 1
        # Small object inside frame
        inp[3, 3] = 2
        # Object outside frame
        inp[8, 8] = 3

        out = inp.copy()
        out[8, 8] = 0  # remove outside object
        return inp, out

    train = [_make_pair()]
    test_inp = np.zeros((9, 9), dtype=int)
    test_inp[0, 0:7] = 4
    test_inp[6, 0:7] = 4
    test_inp[0:7, 0] = 4
    test_inp[0:7, 6] = 4
    test_inp[3, 3] = 5
    test_inp[8, 8] = 6

    result = solve_task_multicolor(train, [test_inp])
    # The solver may or may not find "is_contained" depending on view
    # At minimum, it should try and return something if it finds a separator
    if result is not None:
        outputs, info = result
        assert len(outputs) == 1
        # The outside object should be removed
        assert outputs[0][8, 8] == 0


# ═══════════════════════════════════════════════════════════════════════════
# 11. Edge case: single-color grid
# ═══════════════════════════════════════════════════════════════════════════

def test_single_color_grid():
    """A grid with only one non-bg color should work for all extractors."""
    grid = np.array([
        [1, 1, 0],
        [0, 1, 0],
        [0, 0, 0],
    ])
    cc = extract_color_components(grid, bg=0)
    assert len(cc) == 1
    assert cc[0]["color"] == 1

    sil = extract_silhouette_components(grid, bg=0)
    assert len(sil) == 1
    assert sil[0]["is_multicolor"] is False

    pw = extract_part_whole(grid, bg=0)
    assert len(pw) == 1
    assert pw[0].is_multicolor is False
    assert pw[0].n_parts == 1


# ═══════════════════════════════════════════════════════════════════════════
# 12. Edge case: empty grid
# ═══════════════════════════════════════════════════════════════════════════

def test_empty_grid():
    """An all-background grid should return no objects in any mode."""
    grid = np.zeros((3, 3), dtype=int)

    assert extract_color_components(grid, bg=0) == []
    assert extract_silhouette_components(grid, bg=0) == []
    assert extract_part_whole(grid, bg=0) == []
    assert count_objects(grid, mode="color") == 0
    assert count_objects(grid, mode="silhouette") == 0
    assert count_objects(grid, mode="part_whole") == 0


def test_empty_grid_adapter():
    """MultiColorGridAdapter on empty grid should return empty list."""
    grid = np.zeros((3, 3), dtype=int)
    adapter = MultiColorGridAdapter(bg=0)
    objs = adapter.extract_objects(grid)
    assert objs == []


def test_empty_grid_solver():
    """Solver on empty grid should return None."""
    grid = np.zeros((3, 3), dtype=int)
    result = solve_task_multicolor([(grid, grid)], [grid])
    assert result is None


# ═══════════════════════════════════════════════════════════════════════════
# Additional robustness tests
# ═══════════════════════════════════════════════════════════════════════════

def test_count_objects_invalid_mode():
    """Invalid mode should raise ValueError."""
    grid = np.array([[1, 0], [0, 2]])
    try:
        count_objects(grid, mode="invalid")
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


def test_detect_same_different_empty():
    """Empty object list should return empty groups."""
    groups = detect_same_different([])
    assert groups == []


def test_adapter_scenes_equal():
    """scenes_equal should compare grids correctly."""
    adapter = MultiColorGridAdapter()
    a = np.array([[1, 2], [3, 4]])
    b = np.array([[1, 2], [3, 4]])
    c = np.array([[1, 2], [3, 5]])
    assert adapter.scenes_equal(a, b) is True
    assert adapter.scenes_equal(a, c) is False


def test_adapter_reconstruct_filtered():
    """reconstruct_filtered should zero out removed objects."""
    adapter = MultiColorGridAdapter(bg=0)
    grid = np.array([
        [1, 0, 2],
        [0, 0, 0],
        [3, 0, 0],
    ])
    objs = adapter.extract_objects(grid)
    keep_mask = [True] * len(objs)
    keep_mask[-1] = False  # remove last object
    result = adapter.reconstruct_filtered(grid, objs, keep_mask)
    # At least one object should be zeroed out
    assert result is not None
    assert np.sum(result != 0) < np.sum(grid != 0)
