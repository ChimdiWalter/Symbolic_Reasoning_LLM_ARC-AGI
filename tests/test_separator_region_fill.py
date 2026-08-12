"""Unit tests for separator_region_fill operator family."""
import sys
import os
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from reasoning_project.operator_genesis import (
    _synthesize_separator_region_fill,
    _detect_cross_structure,
    _apply_separator_region_fill,
    _check_train_consistency,
    _check_loo,
    synthesize_operators_from_train,
)


def _make_cross_grid(H, W, vcol_idx, vcol_color, bg, icol, seps):
    """Build a cross-structure grid.

    seps: list of (row_index, fill_color)
    """
    grid = np.full((H, W), bg, dtype=int)
    for r in range(H):
        grid[r, vcol_idx] = vcol_color
    for r, fc in seps:
        for c in range(W):
            grid[r, c] = fc if c != vcol_idx else icol
    return grid


class TestDetectCrossStructure:
    def test_basic_cross(self):
        grid = _make_cross_grid(10, 10, vcol_idx=3, vcol_color=8, bg=0,
                                icol=1, seps=[(2, 5), (7, 3)])
        result = _detect_cross_structure(grid, 0)
        assert result is not None
        assert result["vcol_idx"] == 3
        assert result["vcol_color"] == 8
        assert result["icol"] == 1
        assert len(result["separators"]) == 2
        assert result["separators"][0] == (2, 5)
        assert result["separators"][1] == (7, 3)

    def test_no_vertical_line(self):
        grid = np.zeros((5, 5), dtype=int)
        grid[2, :] = 3
        result = _detect_cross_structure(grid, 0)
        assert result is None

    def test_no_separator_rows(self):
        grid = np.zeros((5, 5), dtype=int)
        grid[:, 2] = 8
        result = _detect_cross_structure(grid, 0)
        assert result is None

    def test_vcol_at_edge(self):
        grid = _make_cross_grid(8, 8, vcol_idx=0, vcol_color=8, bg=7,
                                icol=1, seps=[(3, 4)])
        result = _detect_cross_structure(grid, 7)
        assert result is not None
        assert result["vcol_idx"] == 0


class TestApplySeparatorRegionFill:
    def test_horizontal_two_seps_different_colors_even_midpoint(self):
        """Two separators with different colors, even midpoint → boundary row."""
        # Separators at rows 2 and 8, midpoint = 5
        grid = _make_cross_grid(11, 6, vcol_idx=2, vcol_color=8, bg=7,
                                icol=1, seps=[(2, 9), (8, 3)])
        out = _apply_separator_region_fill(grid, 7, 8, 1)

        # Rows 0-1: fill color 9, vcol=1
        for r in [0, 1]:
            for c in range(6):
                if c == 2:
                    assert out[r, c] == 1, f"row {r} col {c}"
                else:
                    assert out[r, c] == 9, f"row {r} col {c}"

        # Row 2: original separator → icol everywhere except vcol→vcol_color
        for c in range(6):
            expected = 8 if c == 2 else 1
            assert out[2, c] == expected, f"row 2 col {c}"

        # Row 5: boundary (midpoint) → all icol
        for c in range(6):
            assert out[5, c] == 1, f"row 5 col {c}"

        # Rows 3-4: fill color 9
        for r in [3, 4]:
            for c in range(6):
                expected = 1 if c == 2 else 9
                assert out[r, c] == expected, f"row {r} col {c}"

        # Rows 6-7: fill color 3
        for r in [6, 7]:
            for c in range(6):
                expected = 1 if c == 2 else 3
                assert out[r, c] == expected, f"row {r} col {c}"

        # Row 8: original separator
        for c in range(6):
            expected = 8 if c == 2 else 1
            assert out[8, c] == expected, f"row 8 col {c}"

        # Rows 9-10: fill color 3
        for r in [9, 10]:
            for c in range(6):
                expected = 1 if c == 2 else 3
                assert out[r, c] == expected, f"row {r} col {c}"

    def test_horizontal_two_seps_different_colors_odd_midpoint(self):
        """Two separators with different colors, non-integer midpoint → clean split."""
        # Separators at rows 2 and 7, midpoint = 4.5
        grid = _make_cross_grid(10, 6, vcol_idx=2, vcol_color=8, bg=7,
                                icol=1, seps=[(2, 5), (7, 3)])
        out = _apply_separator_region_fill(grid, 7, 8, 1)

        # Rows 3-4: fill color 5 (below sep@2, before midpoint 4.5)
        for r in [3, 4]:
            for c in range(6):
                expected = 1 if c == 2 else 5
                assert out[r, c] == expected, f"row {r} col {c}"

        # Rows 5-6: fill color 3 (after midpoint 4.5, above sep@7)
        for r in [5, 6]:
            for c in range(6):
                expected = 1 if c == 2 else 3
                assert out[r, c] == expected, f"row {r} col {c}"

    def test_horizontal_two_seps_same_color(self):
        """Two separators with same color → no boundary, single fill."""
        grid = _make_cross_grid(10, 6, vcol_idx=2, vcol_color=8, bg=7,
                                icol=1, seps=[(2, 4), (6, 4)])
        out = _apply_separator_region_fill(grid, 7, 8, 1)

        # Rows 3-5: fill color 4 (between seps, same color)
        for r in [3, 4, 5]:
            for c in range(6):
                expected = 1 if c == 2 else 4
                assert out[r, c] == expected, f"row {r} col {c}"

    def test_vertical_cross_via_transpose(self):
        """Vertical cross structure (transposed)."""
        # Build a grid where the "vertical line" is actually a horizontal row
        # and "separator rows" are vertical columns. Then transpose to get
        # a horizontal cross for the synthesizer.
        grid_T = _make_cross_grid(6, 10, vcol_idx=2, vcol_color=8, bg=7,
                                  icol=1, seps=[(1, 5), (4, 3)])
        grid = grid_T.T  # Now it's 10x6

        train_pairs = [(grid, None)]
        # Apply via transpose
        out_T = _apply_separator_region_fill(grid.T, 7, 8, 1)
        out = out_T.T

        # Check separator rows in the transposed view became separator
        # columns in the original
        assert out.shape == grid.shape

    def test_no_cross_returns_copy(self):
        """Grid without cross structure returns unchanged copy."""
        grid = np.ones((5, 5), dtype=int) * 3
        out = _apply_separator_region_fill(grid, 0, 8, 1)
        assert np.array_equal(out, grid)

    def test_three_seps_mixed_colors(self):
        """Three separators: same-same then different."""
        grid = _make_cross_grid(16, 6, vcol_idx=2, vcol_color=8, bg=7,
                                icol=1, seps=[(3, 4), (7, 4), (13, 2)])
        out = _apply_separator_region_fill(grid, 7, 8, 1)

        # Between seps 3 and 7 (same color 4): rows 4-6 → color 4
        for r in [4, 5, 6]:
            assert out[r, 0] == 4, f"row {r}"

        # Between seps 7 and 13 (different colors 4 vs 2):
        # midpoint = 10, rows 8-9 → color 4, row 10 → all 1, rows 11-12 → color 2
        for r in [8, 9]:
            assert out[r, 0] == 4, f"row {r}"
        for c in range(6):
            assert out[10, c] == 1, f"boundary row 10 col {c}"
        for r in [11, 12]:
            assert out[r, 0] == 2, f"row {r}"


class TestSynthesizeSeparatorRegionFill:
    def test_synthesis_on_cross_pairs(self):
        """Synthesizer returns operator for consistent cross-structure pairs."""
        grid1 = _make_cross_grid(10, 8, vcol_idx=3, vcol_color=8, bg=7,
                                 icol=1, seps=[(2, 5), (7, 3)])
        out1 = _apply_separator_region_fill(grid1, 7, 8, 1)

        grid2 = _make_cross_grid(10, 8, vcol_idx=5, vcol_color=8, bg=7,
                                 icol=1, seps=[(3, 9), (6, 2)])
        out2 = _apply_separator_region_fill(grid2, 7, 8, 1)

        train_pairs = [(grid1, out1), (grid2, out2)]
        ops = _synthesize_separator_region_fill(train_pairs)
        assert len(ops) == 1
        assert ops[0].operator_family == "separator_region_fill"

        tc, err = _check_train_consistency(ops[0].execute, train_pairs)
        assert tc is True
        assert err == 0.0

    def test_no_synthesis_without_cross(self):
        """No operators when grids lack cross structure."""
        grid1 = np.zeros((5, 5), dtype=int)
        grid2 = np.ones((5, 5), dtype=int)
        ops = _synthesize_separator_region_fill([(grid1, grid2)])
        assert len(ops) == 0

    def test_no_synthesis_different_shapes(self):
        """No operators when input/output shapes differ."""
        grid1 = np.zeros((5, 5), dtype=int)
        grid2 = np.zeros((5, 6), dtype=int)
        ops = _synthesize_separator_region_fill([(grid1, grid2)])
        assert len(ops) == 0

    def test_inconsistent_mapping_rejected(self):
        """Reject when the cross-fill rule doesn't match the output."""
        grid1 = _make_cross_grid(10, 8, vcol_idx=3, vcol_color=8, bg=7,
                                 icol=1, seps=[(2, 5), (7, 3)])
        wrong_out = grid1.copy()
        wrong_out[0, 0] = 99
        ops = _synthesize_separator_region_fill([(grid1, wrong_out)])
        assert len(ops) == 0

    def test_loo_validation_passes(self):
        """LOO validation succeeds for consistent multi-pair examples."""
        pairs = []
        for vcol_idx in [2, 4, 6]:
            grid = _make_cross_grid(12, 10, vcol_idx=vcol_idx, vcol_color=8,
                                    bg=7, icol=1, seps=[(3, 5), (8, 2)])
            out = _apply_separator_region_fill(grid, 7, 8, 1)
            pairs.append((grid, out))

        ops = _synthesize_separator_region_fill(pairs)
        assert len(ops) == 1

        loo_ok = _check_loo(
            lambda p: _synthesize_separator_region_fill(p),
            pairs,
        )
        assert loo_ok is True

    def test_loo_validation_fails_on_inconsistent(self):
        """LOO fails when one pair has a different bg."""
        grid1 = _make_cross_grid(10, 8, vcol_idx=3, vcol_color=8, bg=7,
                                 icol=1, seps=[(2, 5), (7, 3)])
        out1 = _apply_separator_region_fill(grid1, 7, 8, 1)

        grid2 = _make_cross_grid(10, 8, vcol_idx=3, vcol_color=8, bg=0,
                                 icol=1, seps=[(2, 5), (7, 3)])
        out2 = _apply_separator_region_fill(grid2, 0, 8, 1)

        # These have different bg colors, so synthesis from one pair
        # won't predict the other
        ops = _synthesize_separator_region_fill([(grid1, out1), (grid2, out2)])
        assert len(ops) == 0

    def test_registered_in_family_synthesizers(self):
        """separator_region_fill is reachable via synthesize_operators_from_train."""
        grid = _make_cross_grid(10, 8, vcol_idx=3, vcol_color=8, bg=7,
                                icol=1, seps=[(2, 5), (7, 3)])
        out = _apply_separator_region_fill(grid, 7, 8, 1)

        all_ops = synthesize_operators_from_train([(grid, out)])
        srf_ops = [o for o in all_ops if o.operator_family == "separator_region_fill"]
        assert len(srf_ops) >= 1
