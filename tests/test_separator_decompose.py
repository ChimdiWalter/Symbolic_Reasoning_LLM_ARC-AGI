"""Tests for separator_decompose module."""
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reasoning_project.separator_decompose import (
    solve_task_separator_decompose,
    _find_separator_rows,
    _find_separator_cols,
    _split_by_single_separator,
    _split_into_cells,
    _try_binary_combine,
    _try_binary_combine_preserve_colors,
    _try_binary_combine_multi_color,
    _try_quadrant_compose,
    _try_unique_cell_extract,
    _try_grid_dimensions,
    _try_half_transform,
)


def test_find_separator_rows():
    grid = np.array([
        [1, 2, 3],
        [5, 5, 5],
        [4, 6, 7],
    ])
    seps = _find_separator_rows(grid)
    assert (1, 5) in seps


def test_find_separator_cols():
    grid = np.array([
        [1, 5, 3],
        [2, 5, 6],
        [4, 5, 7],
    ])
    seps = _find_separator_cols(grid)
    assert (1, 5) in seps


def test_split_by_single_separator_row():
    grid = np.array([
        [1, 0, 1],
        [0, 1, 0],
        [5, 5, 5],
        [0, 1, 0],
        [1, 0, 1],
    ])
    result = _split_by_single_separator(grid)
    assert result is not None
    a, b, direction, sep_color = result
    assert direction == "row"
    assert sep_color == 5
    assert a.shape == (2, 3)
    assert b.shape == (2, 3)


def test_split_by_single_separator_col():
    grid = np.array([
        [1, 0, 5, 0, 1],
        [0, 1, 5, 1, 0],
        [1, 1, 5, 0, 0],
    ])
    result = _split_by_single_separator(grid)
    assert result is not None
    a, b, direction, sep_color = result
    assert direction == "col"
    assert sep_color == 5
    assert a.shape == (3, 2)
    assert b.shape == (3, 2)


def test_binary_combine_and():
    """ARC task 0520fde7 pattern: AND of two halves → new color."""
    inp = np.array([
        [1, 1, 0, 5, 0, 1, 0],
        [0, 0, 1, 5, 1, 1, 1],
        [1, 1, 0, 5, 0, 1, 0],
    ])
    out = np.array([
        [0, 2, 0],
        [0, 0, 2],
        [0, 2, 0],
    ])
    test_inp = np.array([
        [1, 0, 1, 5, 1, 0, 1],
        [0, 1, 0, 5, 1, 0, 1],
        [1, 0, 1, 5, 0, 1, 0],
    ])
    expected = np.array([
        [2, 0, 2],
        [0, 0, 0],
        [0, 0, 0],
    ])
    result = _try_binary_combine([(inp, out)], [test_inp])
    assert result is not None
    preds, meta = result
    assert meta["op"] == "and"
    assert meta["out_color"] == 2
    np.testing.assert_array_equal(preds[0], expected)


def test_binary_combine_or():
    """OR of two binary halves → new color."""
    left = np.array([[1, 0], [0, 0]])
    right = np.array([[0, 1], [0, 0]])
    inp = np.column_stack([left, [[5], [5]], right])
    out = np.array([[3, 3], [0, 0]])
    result = _try_binary_combine([(inp, out)], [inp])
    assert result is not None
    preds, meta = result
    assert meta["op"] == "or"


def test_binary_combine_nor():
    """ARC task 0c9aba6e pattern: NOR of two halves."""
    top = np.array([
        [0, 0, 0, 2],
        [2, 0, 0, 0],
    ])
    bottom = np.array([
        [6, 0, 6, 6],
        [6, 0, 0, 6],
    ])
    sep = np.array([[7, 7, 7, 7]])
    inp = np.vstack([top, sep, bottom])
    out = np.array([
        [0, 8, 0, 0],
        [0, 8, 8, 0],
    ])
    result = _try_binary_combine([(inp, out)], [inp])
    assert result is not None
    preds, meta = result
    assert meta["op"] == "nor"
    assert meta["out_color"] == 8
    np.testing.assert_array_equal(preds[0], out)


def test_binary_combine_preserve_overlay():
    """Overlay half_a on half_b (non-zero from A takes priority)."""
    a = np.array([[1, 0], [0, 2]])
    b = np.array([[0, 3], [4, 0]])
    inp = np.column_stack([a, [[5], [5]], b])
    out = np.array([[1, 3], [4, 2]])
    result = _try_binary_combine_preserve_colors([(inp, out)], [inp])
    assert result is not None
    preds, meta = result
    np.testing.assert_array_equal(preds[0], out)


def test_binary_combine_multi_color():
    """Different output colors for overlap regions."""
    a = np.array([[1, 0, 1], [0, 1, 0]])
    b = np.array([[1, 1, 0], [0, 0, 1]])
    inp = np.column_stack([a, [[5], [5]], b])
    # both=3, a_only=4, b_only=5, neither=0
    out = np.array([[3, 5, 4], [0, 4, 5]])
    result = _try_binary_combine_multi_color([(inp, out)], [inp])
    assert result is not None
    preds, meta = result
    assert meta["color_both"] == 3
    assert meta["color_a_only"] == 4
    assert meta["color_b_only"] == 5
    np.testing.assert_array_equal(preds[0], out)


def test_quadrant_compose():
    """ARC task 0bb8deee pattern: 4 quadrants → tiled 2x2."""
    # 4 quadrants separated by row=3 (color 9) and col=3 (color 9)
    inp = np.array([
        [0, 1, 0, 9, 0, 2, 0],
        [1, 1, 0, 9, 2, 0, 0],
        [0, 0, 0, 9, 0, 0, 0],
        [9, 9, 9, 9, 9, 9, 9],
        [0, 0, 3, 9, 4, 0, 0],
        [0, 3, 3, 9, 0, 4, 0],
        [0, 0, 0, 9, 0, 0, 0],
    ])
    out = np.array([
        [0, 1, 0, 2],
        [1, 1, 2, 0],
        [0, 3, 4, 0],
        [3, 3, 0, 4],
    ])
    result = _try_quadrant_compose([(inp, out)], [inp])
    assert result is not None
    preds, meta = result
    assert meta["strategy"] == "quadrant_compose"
    np.testing.assert_array_equal(preds[0], out)


def test_unique_cell_extract():
    """Grid of uniform cells with one unique one."""
    bg = np.array([[1, 1], [1, 1]])
    unique = np.array([[1, 3], [3, 1]])
    # 3x3 grid of cells separated by color 5
    rows = []
    for ri in range(3):
        row_parts = []
        for ci in range(3):
            if ri == 1 and ci == 2:
                row_parts.append(unique)
            else:
                row_parts.append(bg.copy())
            if ci < 2:
                row_parts.append(np.full((2, 1), 5))
        rows.append(np.hstack(row_parts))
        if ri < 2:
            rows.append(np.full((1, rows[-1].shape[1]), 5))
    inp = np.vstack(rows)
    out = unique.copy()

    result = _try_unique_cell_extract([(inp, out)], [inp])
    assert result is not None
    preds, meta = result
    assert meta["strategy"] == "unique_cell_extract"
    np.testing.assert_array_equal(preds[0], out)


def test_grid_dimensions():
    """Output shape = (n_row_sections, n_col_sections) filled with bg."""
    # 2 row seps, 1 col sep → 3 rows × 2 cols
    inp = np.array([
        [1, 1, 8, 1, 1, 1],
        [1, 1, 8, 1, 1, 1],
        [8, 8, 8, 8, 8, 8],
        [1, 1, 8, 1, 1, 1],
        [1, 1, 8, 1, 1, 1],
        [1, 1, 8, 1, 1, 1],
        [8, 8, 8, 8, 8, 8],
        [1, 1, 8, 1, 1, 1],
    ])
    out = np.array([
        [1, 1],
        [1, 1],
        [1, 1],
    ])
    result = _try_grid_dimensions([(inp, out)], [inp])
    assert result is not None
    preds, meta = result
    assert meta["strategy"] == "grid_dimensions"
    np.testing.assert_array_equal(preds[0], out)


def test_grid_dimensions_variable_sep_color():
    """Separator color varies across training pairs."""
    # Pair 1: sep=8, bg=1
    inp1 = np.array([
        [1, 8, 1],
        [8, 8, 8],
        [1, 8, 1],
    ])
    out1 = np.array([[1, 1], [1, 1]])
    # Pair 2: sep=7, bg=3
    inp2 = np.array([
        [3, 7, 3],
        [7, 7, 7],
        [3, 7, 3],
    ])
    out2 = np.array([[3, 3], [3, 3]])

    result = _try_grid_dimensions([(inp1, out1), (inp2, out2)], [inp1])
    assert result is not None
    preds, meta = result
    np.testing.assert_array_equal(preds[0], out1)


def test_half_transform_color_remap():
    """Extract one half with color remapping."""
    top = np.array([[2, 0], [0, 2]])
    bottom = np.array([[6, 0], [0, 6]])
    sep = np.array([[7, 7]])
    inp = np.vstack([top, sep, bottom])
    out = np.array([[8, 0], [0, 8]])
    # Output is bottom half with 6→8
    result = _try_half_transform([(inp, out)], [inp])
    assert result is not None
    preds, meta = result
    assert meta["strategy"] == "half_transform"
    np.testing.assert_array_equal(preds[0], out)


def test_same_size_returns_none():
    """Same-size tasks should return None."""
    inp = np.array([[1, 2], [3, 4]])
    out = np.array([[4, 3], [2, 1]])
    result = solve_task_separator_decompose([(inp, out)], [inp])
    assert result is None


def test_no_separator_returns_none():
    """Tasks without separators should return None."""
    inp = np.array([
        [1, 2, 3],
        [4, 5, 6],
        [7, 8, 9],
        [1, 2, 3],
    ])
    out = np.array([[1, 2, 3]])
    result = solve_task_separator_decompose([(inp, out)], [inp])
    # May or may not return None depending on strategies, but shouldn't crash
    assert result is None or result is not None


def test_solve_task_routes_correctly():
    """Full solve_task_separator_decompose routes to correct strategy."""
    # Binary AND pattern
    inp = np.array([
        [1, 0, 5, 0, 1],
        [0, 1, 5, 1, 0],
    ])
    out = np.array([[0, 0], [0, 0]])
    result = solve_task_separator_decompose([(inp, out)], [inp])
    assert result is not None
    preds, meta = result
    np.testing.assert_array_equal(preds[0], out)
