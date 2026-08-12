"""Tests for color_solver module."""
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reasoning_project.color_solver import solve_task_color


def test_fill_enclosed():
    inp = np.array([
        [0, 0, 0, 0, 0],
        [0, 1, 1, 1, 0],
        [0, 1, 0, 1, 0],
        [0, 1, 1, 1, 0],
        [0, 0, 0, 0, 0],
    ])
    out = np.array([
        [0, 0, 0, 0, 0],
        [0, 1, 1, 1, 0],
        [0, 1, 2, 1, 0],
        [0, 1, 1, 1, 0],
        [0, 0, 0, 0, 0],
    ])
    result = solve_task_color([(inp, out)], [inp])
    assert result is not None
    preds, meta = result
    np.testing.assert_array_equal(preds[0], out)
    assert meta["strategy"] == "fill_enclosed"


def test_recolor_cc_by_color():
    inp = np.array([
        [1, 1, 0, 2, 2],
        [1, 1, 0, 2, 2],
        [0, 0, 0, 0, 0],
        [3, 3, 0, 0, 0],
    ])
    out = np.array([
        [4, 4, 0, 5, 5],
        [4, 4, 0, 5, 5],
        [0, 0, 0, 0, 0],
        [6, 6, 0, 0, 0],
    ])
    result = solve_task_color([(inp, out)], [inp])
    assert result is not None


def test_same_size_only():
    inp = np.array([[1, 2], [3, 4]])
    out = np.array([[1]])
    result = solve_task_color([(inp, out)], [inp])
    assert result is None


def test_majority_fill():
    inp = np.array([
        [1, 1, 2],
        [1, 1, 1],
        [0, 0, 0],
    ])
    out = np.array([
        [1, 1, 1],
        [1, 1, 1],
        [0, 0, 0],
    ])
    result = solve_task_color([(inp, out)], [inp])
    assert result is not None


def test_global_color_permutation():
    """Test simple global color remapping: 1->3, 2->4, 0->0."""
    inp = np.array([
        [1, 2, 0],
        [2, 1, 0],
        [0, 0, 1],
    ])
    out = np.array([
        [3, 4, 0],
        [4, 3, 0],
        [0, 0, 3],
    ])
    result = solve_task_color([(inp, out)], [inp])
    assert result is not None
    preds, meta = result
    np.testing.assert_array_equal(preds[0], out)
    assert meta["strategy"] == "global_color_permutation"


def test_global_color_permutation_identity_rejected():
    """Identity mapping should be rejected."""
    inp = np.array([[1, 2], [3, 0]])
    result = solve_task_color([(inp, inp)], [inp])
    # Identity is rejected by global_color_permutation but may match other strategies
    # Just ensure no crash
    if result is not None:
        preds, meta = result
        assert meta["strategy"] != "global_color_permutation"


def test_conditional_color_by_neighbor_count():
    """Pixels with different neighbor counts get different colors."""
    inp = np.array([
        [0, 0, 0, 0, 0],
        [0, 1, 1, 1, 0],
        [0, 1, 1, 1, 0],
        [0, 1, 1, 1, 0],
        [0, 0, 0, 0, 0],
    ])
    # Corners (2 neighbors)->5, edges (3 neighbors)->6, center (4 neighbors)->7
    out = np.array([
        [0, 0, 0, 0, 0],
        [0, 5, 6, 5, 0],
        [0, 6, 7, 6, 0],
        [0, 5, 6, 5, 0],
        [0, 0, 0, 0, 0],
    ])
    result = solve_task_color([(inp, out)], [inp])
    assert result is not None
    preds, meta = result
    np.testing.assert_array_equal(preds[0], out)
    assert meta["strategy"] == "conditional_color_by_neighbor_count"


def test_color_by_component_position():
    """Components recolored based on their spatial position."""
    inp = np.array([
        [1, 1, 0, 2, 2],
        [1, 1, 0, 2, 2],
        [0, 0, 0, 0, 0],
        [0, 0, 3, 3, 0],
    ])
    # top-left comp -> 5, top-right comp -> 6, bottom-middle comp -> 7
    out = np.array([
        [5, 5, 0, 6, 6],
        [5, 5, 0, 6, 6],
        [0, 0, 0, 0, 0],
        [0, 0, 7, 7, 0],
    ])
    result = solve_task_color([(inp, out)], [inp])
    assert result is not None
    preds, meta = result
    np.testing.assert_array_equal(preds[0], out)
    assert meta["strategy"] in ("color_by_component_position", "recolor_cc_by_color", "recolor_cc_by_size")


def test_swap_colors():
    """Pairwise color swap: 1<->2, everything else unchanged."""
    inp = np.array([
        [1, 2, 0],
        [2, 1, 3],
        [0, 3, 1],
    ])
    out = np.array([
        [2, 1, 0],
        [1, 2, 3],
        [0, 3, 2],
    ])
    result = solve_task_color([(inp, out)], [inp])
    assert result is not None
    preds, meta = result
    np.testing.assert_array_equal(preds[0], out)
    assert meta["strategy"] in ("swap_colors", "global_color_permutation")


def test_remove_color():
    """Remove all pixels of color 2, replace with background."""
    inp = np.array([
        [1, 2, 3],
        [2, 1, 2],
        [3, 2, 1],
    ])
    out = np.array([
        [1, 0, 3],
        [0, 1, 0],
        [3, 0, 1],
    ])
    result = solve_task_color([(inp, out)], [inp])
    assert result is not None
    preds, meta = result
    np.testing.assert_array_equal(preds[0], out)
    assert meta["strategy"] in ("remove_color", "global_color_permutation")


def test_keep_only_color():
    """Keep only pixels of color 1, set everything else to background."""
    inp = np.array([
        [1, 2, 3],
        [2, 1, 2],
        [3, 2, 1],
    ])
    out = np.array([
        [1, 0, 0],
        [0, 1, 0],
        [0, 0, 1],
    ])
    result = solve_task_color([(inp, out)], [inp])
    assert result is not None
    preds, meta = result
    np.testing.assert_array_equal(preds[0], out)
    assert meta["strategy"] in ("keep_only_color", "global_color_permutation")
