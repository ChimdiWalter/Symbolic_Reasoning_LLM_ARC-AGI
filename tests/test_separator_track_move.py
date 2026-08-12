"""Unit tests for separator_track_move operator family."""
import sys
import os
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from reasoning_project.operator_genesis import (
    _detect_box_and_track,
    _apply_track_move,
    _synthesize_separator_track_move,
    _check_train_consistency,
    _check_loo,
    _infer_background,
    synthesize_operators_from_train,
)


def _make_track_grid(H, W, box_r, box_c, border_color, track_color, bg,
                     axis, track_positions):
    grid = np.full((H, W), bg, dtype=int)
    for dr in range(3):
        for dc in range(3):
            grid[box_r + dr, box_c + dc] = border_color
    grid[box_r + 1, box_c + 1] = track_color
    center = (box_r + 1) if axis == "v" else (box_c + 1)
    for pos in track_positions:
        if pos == center:
            continue
        if axis == "v":
            grid[pos, box_c + 1] = track_color
        else:
            grid[box_r + 1, pos] = track_color
    return grid


class TestDetectBoxAndTrack:
    def test_vertical_track(self):
        grid = _make_track_grid(13, 7, 3, 3, 2, 3, 0,
                                "v", [0, 2, 4, 6, 8, 10, 12])
        det = _detect_box_and_track(grid, 0)
        assert det is not None
        assert det["box_r"] == 3
        assert det["box_c"] == 3
        assert det["border_color"] == 2
        assert det["track_color"] == 3
        assert det["axis"] == "v"
        assert det["track_positions"] == [0, 2, 4, 6, 8, 10, 12]
        assert det["spacing"] == 2

    def test_horizontal_track(self):
        grid = _make_track_grid(7, 13, 2, 0, 2, 3, 0,
                                "h", [1, 3, 5, 7, 9, 11])
        det = _detect_box_and_track(grid, 0)
        assert det is not None
        assert det["axis"] == "h"
        assert det["track_positions"] == [1, 3, 5, 7, 9, 11]

    def test_no_box(self):
        grid = np.zeros((7, 7), dtype=int)
        grid[3, :] = 3
        det = _detect_box_and_track(grid, 0)
        assert det is None

    def test_no_track(self):
        grid = np.zeros((7, 7), dtype=int)
        for dr in range(3):
            for dc in range(3):
                grid[2 + dr, 2 + dc] = 2
        grid[3, 3] = 3
        det = _detect_box_and_track(grid, 0)
        assert det is None

    def test_insufficient_dots(self):
        grid = np.zeros((7, 7), dtype=int)
        for dr in range(3):
            for dc in range(3):
                grid[2 + dr, 2 + dc] = 2
        grid[3, 3] = 3
        grid[0, 3] = 3
        det = _detect_box_and_track(grid, 0)
        assert det is None


class TestApplyTrackMove:
    def test_move_down(self):
        inp = _make_track_grid(13, 7, 3, 3, 2, 3, 0,
                               "v", [0, 2, 4, 6, 8, 10, 12])
        expected = _make_track_grid(13, 7, 5, 3, 2, 3, 0,
                                    "v", [0, 2, 4, 6, 8, 10, 12])
        result = _apply_track_move(inp, 0, 2, 3)
        np.testing.assert_array_equal(result, expected)

    def test_move_right(self):
        inp = _make_track_grid(7, 13, 2, 0, 2, 3, 0,
                               "h", [1, 3, 5, 7, 9, 11])
        expected = _make_track_grid(7, 13, 2, 2, 2, 3, 0,
                                    "h", [1, 3, 5, 7, 9, 11])
        result = _apply_track_move(inp, 0, 2, 3)
        np.testing.assert_array_equal(result, expected)

    def test_centered_moves_positive(self):
        inp = _make_track_grid(7, 9, 2, 3, 2, 3, 0,
                               "h", [0, 2, 4, 6, 8])
        expected = _make_track_grid(7, 9, 2, 5, 2, 3, 0,
                                    "h", [0, 2, 4, 6, 8])
        result = _apply_track_move(inp, 0, 2, 3)
        np.testing.assert_array_equal(result, expected)

    def test_move_up(self):
        inp = _make_track_grid(9, 5, 5, 1, 2, 3, 0,
                               "v", [0, 2, 4, 6, 8])
        expected = _make_track_grid(9, 5, 3, 1, 2, 3, 0,
                                    "v", [0, 2, 4, 6, 8])
        result = _apply_track_move(inp, 0, 2, 3)
        np.testing.assert_array_equal(result, expected)

    def test_no_detection_returns_copy(self):
        grid = np.zeros((5, 5), dtype=int)
        result = _apply_track_move(grid, 0, 2, 3)
        np.testing.assert_array_equal(result, grid)


class TestSynthesizeSTM:
    def test_synthesis_on_arc_like_pairs(self):
        inp0 = _make_track_grid(13, 7, 3, 3, 2, 3, 0,
                                "v", [0, 2, 4, 6, 8, 10, 12])
        out0 = _make_track_grid(13, 7, 5, 3, 2, 3, 0,
                                "v", [0, 2, 4, 6, 8, 10, 12])
        inp1 = _make_track_grid(7, 13, 2, 0, 2, 3, 0,
                                "h", [1, 3, 5, 7, 9, 11])
        out1 = _make_track_grid(7, 13, 2, 2, 2, 3, 0,
                                "h", [1, 3, 5, 7, 9, 11])
        ops = _synthesize_separator_track_move([(inp0, out0), (inp1, out1)])
        assert len(ops) == 1
        assert ops[0].operator_family == "separator_track_move"

    def test_synthesis_rejects_non_track_task(self):
        grid = np.zeros((5, 5), dtype=int)
        grid[2, :] = 3
        ops = _synthesize_separator_track_move([(grid, grid)])
        assert ops == []

    def test_synthesis_rejects_shape_mismatch(self):
        inp = np.zeros((5, 5), dtype=int)
        out = np.zeros((5, 3), dtype=int)
        ops = _synthesize_separator_track_move([(inp, out)])
        assert ops == []

    def test_loo_passes(self):
        inp0 = _make_track_grid(13, 7, 3, 3, 2, 3, 0,
                                "v", [0, 2, 4, 6, 8, 10, 12])
        out0 = _make_track_grid(13, 7, 5, 3, 2, 3, 0,
                                "v", [0, 2, 4, 6, 8, 10, 12])
        inp1 = _make_track_grid(7, 7, 1, 1, 2, 3, 0,
                                "v", [0, 2, 4, 6])
        out1 = _make_track_grid(7, 7, 3, 1, 2, 3, 0,
                                "v", [0, 2, 4, 6])
        pairs = [(inp0, out0), (inp1, out1)]
        loo_ok = _check_loo(_synthesize_separator_track_move, pairs)
        assert loo_ok

    def test_included_in_full_synthesis(self):
        inp = _make_track_grid(13, 7, 3, 3, 2, 3, 0,
                               "v", [0, 2, 4, 6, 8, 10, 12])
        out = _make_track_grid(13, 7, 5, 3, 2, 3, 0,
                               "v", [0, 2, 4, 6, 8, 10, 12])
        ops = synthesize_operators_from_train([(inp, out)])
        stm_ops = [o for o in ops if o.operator_family == "separator_track_move"]
        assert len(stm_ops) >= 1
