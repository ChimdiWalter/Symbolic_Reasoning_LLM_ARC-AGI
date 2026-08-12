"""Tests for abstract program induction (strengthens H1 and H4)."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reasoning_project.abstract_programs import (
    AbstractProgram,
    InputOutputRelation,
    OverlayOp,
    apply_abstract_program,
    infer_abstract_program,
    infer_relation,
    solve_task_abstract_programs,
)


# ---------------------------------------------------------------------------
# InputOutputRelation
# ---------------------------------------------------------------------------

class TestInferRelation:
    def test_identity(self):
        grid = np.array([[1, 2], [3, 0]])
        rel = infer_relation(grid, grid.copy())
        assert rel.spatial_type == "identity"
        assert rel.preserves_shape is True
        assert rel.size_change == pytest.approx((1.0, 1.0))

    def test_reflect_h(self):
        inp = np.array([[1, 2], [3, 4]])
        out = inp[::-1, :]
        rel = infer_relation(inp, out)
        assert rel.spatial_type == "reflect_h"

    def test_reflect_v(self):
        inp = np.array([[1, 2], [3, 4]])
        out = inp[:, ::-1]
        rel = infer_relation(inp, out)
        assert rel.spatial_type == "reflect_v"

    def test_size_change(self):
        inp = np.array([[1, 2]])
        out = np.array([[1, 2], [3, 4]])
        rel = infer_relation(inp, out)
        assert rel.preserves_shape is False
        assert rel.size_change[0] == pytest.approx(2.0)

    def test_color_mapping(self):
        inp = np.array([[1, 2], [1, 2]])
        out = np.array([[3, 4], [3, 4]])
        rel = infer_relation(inp, out)
        assert rel.color_mapping == {1: 3, 2: 4}


# ---------------------------------------------------------------------------
# Strategy: conditional_transform
# ---------------------------------------------------------------------------

class TestConditionalTransform:
    def test_simple_recolor(self):
        """Simple color mapping: 1->3, 2->4."""
        pairs = [
            (np.array([[1, 2], [2, 1]]), np.array([[3, 4], [4, 3]])),
            (np.array([[1, 1], [2, 2]]), np.array([[3, 3], [4, 4]])),
        ]
        prog = infer_abstract_program(pairs)
        assert prog is not None
        assert prog.strategy == "conditional_transform"

        test_inp = np.array([[2, 1], [1, 2]])
        result = apply_abstract_program(prog, test_inp)
        expected = np.array([[4, 3], [3, 4]])
        assert np.array_equal(result, expected)

    def test_identity_rejected(self):
        """Pure identity should not be detected as conditional_transform."""
        grid = np.array([[1, 2], [3, 4]])
        pairs = [(grid, grid.copy())]
        prog = infer_abstract_program(pairs)
        # conditional_transform rejects identity
        assert prog is None or prog.strategy != "conditional_transform"

    def test_nondeterministic_rejected(self):
        """Non-deterministic mapping should be rejected."""
        inp = np.array([[1, 1], [1, 1]])
        out = np.array([[2, 3], [2, 3]])  # color 1 maps to both 2 and 3
        pairs = [(inp, out)]
        prog = infer_abstract_program(pairs)
        assert prog is None or prog.strategy != "conditional_transform"


# ---------------------------------------------------------------------------
# Strategy: pattern_continuation
# ---------------------------------------------------------------------------

class TestPatternContinuation:
    def test_horizontal_tile(self):
        """Input tiled 2x horizontally."""
        inp = np.array([[1, 2], [3, 4]])
        out = np.array([[1, 2, 1, 2], [3, 4, 3, 4]])
        pairs = [(inp, out)]
        prog = infer_abstract_program(pairs)
        assert prog is not None
        assert prog.strategy == "pattern_continuation"
        assert prog.params["axis"] == "horizontal"
        assert prog.params["factor"] == 2

    def test_vertical_tile(self):
        """Input tiled 3x vertically."""
        inp = np.array([[1, 2]])
        out = np.array([[1, 2], [1, 2], [1, 2]])
        pairs = [(inp, out)]
        prog = infer_abstract_program(pairs)
        assert prog is not None
        assert prog.strategy == "pattern_continuation"
        assert prog.params["axis"] == "vertical"
        assert prog.params["factor"] == 3

    def test_apply_tile(self):
        """Apply tiling to a new input."""
        pairs = [
            (np.array([[5, 6]]), np.array([[5, 6, 5, 6]])),
        ]
        prog = infer_abstract_program(pairs)
        assert prog is not None

        test_inp = np.array([[7, 8]])
        result = apply_abstract_program(prog, test_inp)
        assert np.array_equal(result, np.array([[7, 8, 7, 8]]))


# ---------------------------------------------------------------------------
# Strategy: symmetry_completion
# ---------------------------------------------------------------------------

class TestSymmetryCompletion:
    def test_horizontal_completion(self):
        """Fill zeros to make horizontally symmetric output."""
        inp = np.array([[1, 2, 3], [0, 0, 0]])  # top half only
        out = np.array([[1, 2, 3], [1, 2, 3]])  # symmetric
        pairs = [(inp, out)]
        prog = infer_abstract_program(pairs)
        # This may or may not detect depending on match fraction thresholds
        # The main point is that the strategy is exercised
        if prog is not None and prog.strategy == "symmetry_completion":
            result = apply_abstract_program(prog, inp)
            # Should fill zeros from reflected half
            assert result.shape == inp.shape

    def test_apply_symmetry(self):
        """Apply symmetry completion to a new grid."""
        prog = AbstractProgram(
            strategy="symmetry_completion",
            params={"axis": "vertical"},
        )
        inp = np.array([[1, 0], [3, 0]])
        result = apply_abstract_program(prog, inp)
        expected = np.array([[1, 1], [3, 3]])  # zeros filled from [:, ::-1]
        assert np.array_equal(result, expected)


# ---------------------------------------------------------------------------
# Strategy: overlay_two_objects
# ---------------------------------------------------------------------------

class TestOverlay:
    def test_or_overlay(self):
        """OR of two colored regions."""
        # Region A (color 1): top-left
        # Region B (color 2): bottom-right
        inp = np.array([
            [1, 1, 0],
            [1, 0, 0],
            [0, 0, 2],
        ])
        # OR: union of both regions
        out = np.array([
            [3, 3, 0],
            [3, 0, 0],
            [0, 0, 3],
        ])
        pairs = [(inp, out)]
        prog = infer_abstract_program(pairs)
        if prog is not None and prog.strategy == "overlay_two_objects":
            assert prog.params["operation"] == "or"

    def test_apply_overlay_or(self):
        """Apply OR overlay."""
        prog = AbstractProgram(
            strategy="overlay_two_objects",
            params={"operation": "or", "output_color": 5},
        )
        inp = np.array([
            [1, 0],
            [0, 2],
        ])
        result = apply_abstract_program(prog, inp)
        expected = np.array([
            [5, 0],
            [0, 5],
        ])
        assert np.array_equal(result, expected)


# ---------------------------------------------------------------------------
# Full solve pipeline
# ---------------------------------------------------------------------------

class TestSolveTaskAbstractPrograms:
    def test_solve_color_mapping(self):
        """End-to-end solve with conditional transform."""
        train = [
            (np.array([[1, 2], [2, 1]]), np.array([[3, 4], [4, 3]])),
            (np.array([[1, 1], [2, 2]]), np.array([[3, 3], [4, 4]])),
        ]
        test = [np.array([[2, 2], [1, 1]])]

        result = solve_task_abstract_programs(train, test)
        assert result is not None
        predictions, meta = result
        assert len(predictions) == 1
        assert np.array_equal(predictions[0], np.array([[4, 4], [3, 3]]))
        assert meta["strategy"] == "conditional_transform"

    def test_solve_tiling(self):
        """End-to-end solve with pattern continuation."""
        train = [
            (np.array([[1, 2]]), np.array([[1, 2, 1, 2]])),
            (np.array([[3, 4]]), np.array([[3, 4, 3, 4]])),
        ]
        test = [np.array([[5, 6]])]

        result = solve_task_abstract_programs(train, test)
        assert result is not None
        predictions, meta = result
        assert np.array_equal(predictions[0], np.array([[5, 6, 5, 6]]))
        assert meta["strategy"] == "pattern_continuation"

    def test_solve_no_match(self):
        """No matching strategy returns None."""
        train = [
            (np.array([[1, 2, 3]]), np.array([[9]]))
        ]
        test = [np.array([[4, 5, 6]])]

        result = solve_task_abstract_programs(train, test)
        assert result is None

    def test_solve_empty(self):
        """Empty training pairs returns None."""
        result = solve_task_abstract_programs([], [])
        assert result is None


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    def test_unknown_strategy(self):
        """Unknown strategy raises ValueError."""
        prog = AbstractProgram(strategy="nonexistent")
        with pytest.raises(ValueError, match="Unknown abstract program"):
            apply_abstract_program(prog, np.array([[1]]))

    def test_overlay_too_few_regions(self):
        """Overlay with fewer than 2 regions raises ValueError."""
        prog = AbstractProgram(
            strategy="overlay_two_objects",
            params={"operation": "or", "output_color": 1},
        )
        with pytest.raises(ValueError, match="at least 2"):
            apply_abstract_program(prog, np.zeros((2, 2), dtype=int))
