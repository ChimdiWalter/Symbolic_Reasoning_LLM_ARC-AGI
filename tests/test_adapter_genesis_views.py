"""Tests for view adapter parse/lift/project round-trip."""
from __future__ import annotations

import numpy as np
import pytest

from reasoning_project.view_adapters import (
    FrameInteriorAdapter,
    ColorLayerAdapter,
    ObjectInObjectAdapter,
    SymmetryAxisAdapter,
    RepeatedMotifAdapter,
    get_applicable_adapters,
)


# ---------------------------------------------------------------------------
# FrameInteriorAdapter
# ---------------------------------------------------------------------------

class TestFrameInteriorAdapter:
    def _make_frame_grid(self, h, w, frame_color, interior):
        grid = np.full((h, w), frame_color, dtype=int)
        grid[1:h-1, 1:w-1] = interior
        return grid

    def test_can_apply_with_frame(self):
        interior = np.zeros((5, 5), dtype=int)
        interior[1:3, 1:3] = 1
        grid = self._make_frame_grid(7, 7, 3, interior)
        adapter = FrameInteriorAdapter()
        assert adapter.can_apply(grid)

    def test_can_apply_without_frame(self):
        grid = np.zeros((5, 5), dtype=int)
        grid[1:3, 1:3] = 1
        adapter = FrameInteriorAdapter()
        assert not adapter.can_apply(grid)

    def test_parse_extracts_interior(self):
        interior = np.zeros((5, 5), dtype=int)
        interior[1:3, 1:3] = 2
        grid = self._make_frame_grid(7, 7, 3, interior)
        adapter = FrameInteriorAdapter()
        parsed = adapter.parse(grid)
        assert parsed["has_frame"]
        assert parsed["frame_color"] == 3
        assert np.array_equal(parsed["interior"], interior)

    def test_extract_interior_objects(self):
        interior = np.zeros((5, 5), dtype=int)
        interior[0:2, 0:2] = 1
        interior[3:5, 3:5] = 2
        grid = self._make_frame_grid(7, 7, 4, interior)
        adapter = FrameInteriorAdapter()
        objects = adapter.extract_interior_objects(grid)
        assert len(objects) == 2
        areas = sorted([o["area"] for o in objects])
        assert areas == [4, 4]

    def test_lift_and_project_round_trip(self):
        interior_in = np.zeros((5, 5), dtype=int)
        interior_in[0:3, 0:3] = 1  # largest
        interior_in[3:4, 3:5] = 2  # small
        grid_in = self._make_frame_grid(7, 7, 3, interior_in)

        interior_out = np.zeros((5, 5), dtype=int)
        interior_out[0:3, 0:3] = 1
        grid_out = self._make_frame_grid(7, 7, 3, interior_out)

        adapter = FrameInteriorAdapter()
        lifted = adapter.lift_train_pairs([(grid_in, grid_out)])
        assert len(lifted) == 1
        lifted_in, lifted_out = lifted[0]
        assert np.array_equal(lifted_in, interior_in)
        assert np.array_equal(lifted_out, interior_out)

        # Project adapted output back
        projected = adapter.project(interior_out, grid_in)
        assert np.array_equal(projected, grid_out)

    def test_signature(self):
        adapter = FrameInteriorAdapter()
        sig = adapter.signature()
        assert sig["adapter_type"] == "frame_interior"


# ---------------------------------------------------------------------------
# ColorLayerAdapter
# ---------------------------------------------------------------------------

class TestColorLayerAdapter:
    def test_can_apply(self):
        grid = np.zeros((5, 5), dtype=int)
        grid[0:2, 0:2] = 1
        grid[3:5, 3:5] = 2
        adapter = ColorLayerAdapter()
        assert adapter.can_apply(grid)

    def test_can_apply_single_color(self):
        grid = np.zeros((5, 5), dtype=int)
        grid[0:2, 0:2] = 1
        adapter = ColorLayerAdapter()
        assert not adapter.can_apply(grid)

    def test_parse_creates_layers(self):
        grid = np.zeros((5, 5), dtype=int)
        grid[0:2, 0:2] = 1
        grid[3:5, 3:5] = 2
        adapter = ColorLayerAdapter()
        parsed = adapter.parse(grid)
        assert 1 in parsed["colors"]
        assert 2 in parsed["colors"]
        assert np.array_equal(parsed["layers"][1], (grid == 1).astype(int))

    def test_lift_train_pairs_removes_color(self):
        grid_in = np.zeros((5, 5), dtype=int)
        grid_in[0:2, 0:2] = 1
        grid_in[3:5, 3:5] = 2
        grid_out = grid_in.copy()
        grid_out[grid_out == 2] = 0

        adapter = ColorLayerAdapter(target_color=2)
        lifted = adapter.lift_train_pairs([(grid_in, grid_out)])
        lifted_in, lifted_out = lifted[0]
        # Lifted input has only color 2
        assert np.all((lifted_in == 0) | (lifted_in == 2))
        # Lifted output has no color 2
        assert np.all(lifted_out == 0)

    def test_project_merges_layer(self):
        grid_orig = np.zeros((5, 5), dtype=int)
        grid_orig[0:2, 0:2] = 1
        grid_orig[3:5, 3:5] = 2

        # Adapted output: removed color 2
        adapted = np.zeros((5, 5), dtype=int)

        adapter = ColorLayerAdapter(target_color=2)
        projected = adapter.project(adapted, grid_orig)
        # Color 2 should be removed
        assert not np.any(projected == 2)
        # Color 1 should remain
        assert np.any(projected == 1)


# ---------------------------------------------------------------------------
# ObjectInObjectAdapter
# ---------------------------------------------------------------------------

class TestObjectInObjectAdapter:
    def test_can_apply_with_containment(self):
        grid = np.zeros((8, 8), dtype=int)
        grid[1:7, 1:7] = 3
        grid[2:6, 2:6] = 0
        grid[3:5, 3:5] = 1
        adapter = ObjectInObjectAdapter()
        assert adapter.can_apply(grid)

    def test_can_apply_without_containment(self):
        grid = np.zeros((5, 5), dtype=int)
        grid[0:2, 0:2] = 1
        grid[3:5, 3:5] = 2
        adapter = ObjectInObjectAdapter()
        assert not adapter.can_apply(grid)

    def test_extract_inner_objects(self):
        grid = np.zeros((8, 8), dtype=int)
        grid[1:7, 1:7] = 3
        grid[2:6, 2:6] = 0
        grid[3:5, 3:5] = 1
        adapter = ObjectInObjectAdapter()
        inner = adapter.extract_interior_objects(grid)
        assert len(inner) >= 1
        inner_colors = {o["primary_color"] for o in inner}
        assert 1 in inner_colors

    def test_lift_train_pairs(self):
        grid_in = np.zeros((8, 8), dtype=int)
        grid_in[1:7, 1:7] = 3
        grid_in[2:6, 2:6] = 0
        grid_in[3:5, 3:5] = 1
        grid_out = np.zeros((8, 8), dtype=int)
        grid_out[3:5, 3:5] = 1

        adapter = ObjectInObjectAdapter()
        lifted = adapter.lift_train_pairs([(grid_in, grid_out)])
        lifted_in, lifted_out = lifted[0]
        # Lifted input should show only inner objects
        assert np.any(lifted_in == 1)
        assert not np.any(lifted_in == 3)


# ---------------------------------------------------------------------------
# SymmetryAxisAdapter
# ---------------------------------------------------------------------------

class TestSymmetryAxisAdapter:
    def test_can_apply_horizontal_symmetry(self):
        grid = np.zeros((6, 4), dtype=int)
        grid[0:3, :] = np.array([[1, 2, 0, 0],
                                  [0, 3, 3, 0],
                                  [0, 0, 4, 0]])
        grid[3:6, :] = grid[0:3, :][::-1, :]
        adapter = SymmetryAxisAdapter()
        assert adapter.can_apply(grid)

    def test_can_apply_no_symmetry(self):
        grid = np.array([[1, 2, 3], [4, 5, 6], [7, 8, 9]])
        adapter = SymmetryAxisAdapter()
        assert not adapter.can_apply(grid)

    def test_parse_detects_axis(self):
        grid = np.zeros((6, 4), dtype=int)
        top = np.array([[1, 2, 0, 0],
                        [0, 3, 3, 0],
                        [0, 0, 4, 0]])
        grid[:3, :] = top
        grid[3:, :] = top[::-1, :]
        adapter = SymmetryAxisAdapter()
        parsed = adapter.parse(grid)
        assert parsed["has_symmetry"]
        assert parsed["axis"] == "horizontal"

    def test_project_mirrors(self):
        grid = np.zeros((6, 4), dtype=int)
        top = np.array([[1, 0, 0, 0],
                        [0, 2, 0, 0],
                        [0, 0, 3, 0]])
        grid[:3, :] = top
        grid[3:, :] = top[::-1, :]
        adapter = SymmetryAxisAdapter()

        # Modified half
        new_half = np.array([[5, 0, 0, 0],
                             [0, 6, 0, 0],
                             [0, 0, 7, 0]])
        projected = adapter.project(new_half, grid)
        assert projected.shape == (6, 4)
        assert np.array_equal(projected[:3, :], new_half)
        assert np.array_equal(projected[3:, :], new_half[::-1, :])


# ---------------------------------------------------------------------------
# RepeatedMotifAdapter
# ---------------------------------------------------------------------------

class TestRepeatedMotifAdapter:
    def test_can_apply_with_tiling(self):
        motif = np.array([[1, 2], [3, 0]])
        grid = np.tile(motif, (3, 3))
        adapter = RepeatedMotifAdapter()
        assert adapter.can_apply(grid)

    def test_can_apply_no_tiling(self):
        grid = np.array([[1, 2, 3], [4, 5, 6], [7, 8, 9]])
        adapter = RepeatedMotifAdapter()
        assert not adapter.can_apply(grid)

    def test_parse_finds_motif(self):
        motif = np.array([[1, 2], [3, 0]])
        grid = np.tile(motif, (2, 2))
        adapter = RepeatedMotifAdapter()
        parsed = adapter.parse(grid)
        assert parsed["has_motif"]
        assert np.array_equal(parsed["motif"], motif)
        assert parsed["n_rows"] == 2
        assert parsed["n_cols"] == 2

    def test_project_tiles_back(self):
        motif = np.array([[1, 2], [3, 0]])
        grid = np.tile(motif, (2, 2))
        adapter = RepeatedMotifAdapter()

        new_motif = np.array([[5, 6], [7, 0]])
        projected = adapter.project(new_motif, grid)
        expected = np.tile(new_motif, (2, 2))
        assert np.array_equal(projected, expected)


# ---------------------------------------------------------------------------
# get_applicable_adapters
# ---------------------------------------------------------------------------

class TestGetApplicableAdapters:
    def test_returns_applicable(self):
        # Grid with a frame
        grid = np.full((7, 7), 3, dtype=int)
        interior = np.zeros((5, 5), dtype=int)
        interior[1:3, 1:3] = 1
        interior[3:5, 3:5] = 2
        grid[1:6, 1:6] = interior
        adapters = get_applicable_adapters(grid)
        types = {a.adapter_type for a in adapters}
        assert "frame_interior" in types

    def test_empty_grid(self):
        grid = np.zeros((5, 5), dtype=int)
        adapters = get_applicable_adapters(grid)
        # No adapters should apply to an all-zero grid
        for a in adapters:
            assert a.adapter_type != "frame_interior"
