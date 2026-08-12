"""Tests for crop_extract module."""
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reasoning_project.crop_extract import solve_task_crop_extract


def test_nonzero_bbox():
    inp = np.array([[0, 0, 0, 0], [0, 1, 2, 0], [0, 3, 4, 0], [0, 0, 0, 0]])
    out = np.array([[1, 2], [3, 4]])
    result = solve_task_crop_extract([(inp, out)], [inp])
    assert result is not None
    preds, meta = result
    np.testing.assert_array_equal(preds[0], out)


def test_largest_cc():
    inp = np.array([
        [1, 1, 0, 0, 0],
        [1, 1, 0, 0, 0],
        [0, 0, 0, 2, 0],
        [0, 0, 0, 0, 0],
    ])
    out = np.array([[1, 1], [1, 1]])
    result = solve_task_crop_extract([(inp, out)], [inp])
    assert result is not None
    preds, meta = result
    np.testing.assert_array_equal(preds[0], out)


def test_same_size_returns_none():
    inp = np.array([[1, 2], [3, 4]])
    out = np.array([[4, 3], [2, 1]])
    result = solve_task_crop_extract([(inp, out)], [inp])
    assert result is None


def test_halves():
    inp = np.array([[1, 2, 3, 4], [5, 6, 7, 8]])
    out = np.array([[1, 2], [5, 6]])
    result = solve_task_crop_extract([(inp, out)], [inp])
    assert result is not None
    preds, meta = result
    np.testing.assert_array_equal(preds[0], out)


def test_color_bbox():
    inp = np.array([
        [0, 0, 0, 0],
        [0, 3, 3, 0],
        [0, 3, 3, 0],
        [1, 1, 1, 1],
    ])
    out = np.array([[3, 3], [3, 3]])
    result = solve_task_crop_extract([(inp, out)], [inp])
    assert result is not None


def test_separator_split_row():
    """Split grid at a full-row separator and extract one side."""
    inp = np.array([
        [1, 2, 3],
        [4, 5, 6],
        [7, 7, 7],
        [8, 9, 1],
    ])
    # Output is above the row of 7s
    out = np.array([
        [1, 2, 3],
        [4, 5, 6],
    ])
    result = solve_task_crop_extract([(inp, out)], [inp])
    assert result is not None
    preds, meta = result
    np.testing.assert_array_equal(preds[0], out)


def test_separator_split_col():
    """Split grid at a full-column separator and extract one side."""
    inp = np.array([
        [1, 2, 5, 3, 4],
        [6, 7, 5, 8, 9],
    ])
    # Output is to the right of the column of 5s
    out = np.array([
        [3, 4],
        [8, 9],
    ])
    result = solve_task_crop_extract([(inp, out)], [inp])
    assert result is not None
    preds, meta = result
    np.testing.assert_array_equal(preds[0], out)


def test_mask_extract_horizontal():
    """Top half is a mask, bottom half is content."""
    inp = np.array([
        [1, 0, 1],
        [0, 1, 0],
        [5, 6, 7],
        [8, 9, 2],
    ])
    # Mask color 1 selects from bottom half
    out = np.array([
        [5, 0, 7],
        [0, 9, 0],
    ])
    result = solve_task_crop_extract([(inp, out)], [inp])
    assert result is not None
    preds, meta = result
    np.testing.assert_array_equal(preds[0], out)


def test_repeated_tile_extract():
    """Grid is a 2x2 repetition of a small tile."""
    tile = np.array([
        [1, 2],
        [3, 4],
    ])
    inp = np.tile(tile, (2, 2))  # 4x4 grid
    out = tile.copy()
    result = solve_task_crop_extract([(inp, out)], [inp])
    assert result is not None
    preds, meta = result
    np.testing.assert_array_equal(preds[0], out)


def test_repeated_tile_extract_3x3():
    """Grid is a 3x3 repetition of a tile."""
    tile = np.array([
        [5, 6],
        [7, 8],
    ])
    inp = np.tile(tile, (3, 3))  # 6x6 grid
    out = tile.copy()
    result = solve_task_crop_extract([(inp, out)], [inp])
    assert result is not None
    preds, meta = result
    np.testing.assert_array_equal(preds[0], out)
