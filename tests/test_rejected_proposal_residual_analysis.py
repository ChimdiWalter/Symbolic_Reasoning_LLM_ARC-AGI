"""Tests for the rejected proposal residual analyzer."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from analyze_rejected_executable_proposals import compute_residual, classify_residual


class TestComputeResidual:

    def test_identical_grids(self):
        grid = np.array([[1, 2], [3, 4]])
        result = compute_residual(grid, grid)
        assert result["type"] == "cell_diff"
        assert result["diff_cells"] == 0
        assert result["diff_fraction"] == 0.0

    def test_shape_mismatch(self):
        pred = np.array([[1, 2], [3, 4]])
        gold = np.array([[1, 2, 3]])
        result = compute_residual(pred, gold)
        assert result["type"] == "shape_mismatch"

    def test_cell_diff(self):
        pred = np.array([[1, 2], [3, 4]])
        gold = np.array([[1, 5], [3, 4]])
        result = compute_residual(pred, gold)
        assert result["type"] == "cell_diff"
        assert result["diff_cells"] == 1
        assert result["diff_fraction"] == 0.25

    def test_none_prediction(self):
        gold = np.array([[1, 2]])
        result = compute_residual(None, gold)
        assert result["type"] == "no_prediction"


class TestClassifyResidual:

    def test_correct(self):
        grid = np.array([[1, 0], [0, 1]])
        residual = {"type": "cell_diff", "diff_cells": 0, "diff_fraction": 0.0}
        cls = classify_residual(grid, grid, grid, residual, {})
        assert cls == "correct"

    def test_needs_recolor_small_diff(self):
        inp = np.array([[1, 0], [0, 1]])
        pred = np.array([[1, 0], [0, 2]])
        gold = np.array([[1, 0], [0, 3]])
        residual = compute_residual(pred, gold)
        cls = classify_residual(inp, pred, gold, residual, {})
        assert "recolor" in cls or "spatial" in cls or "unknown" not in cls

    def test_shape_mismatch_smaller_gold(self):
        inp = np.array([[1, 0, 0], [0, 1, 0], [0, 0, 0]])
        pred = None
        gold = np.array([[1]])
        residual = {"type": "shape_mismatch", "predicted_shape": [3, 3], "gold_shape": [1, 1]}
        cls = classify_residual(inp, pred, gold, residual, {})
        assert "crop" in cls or "extract" in cls or "resize" in cls

    def test_no_prediction(self):
        inp = np.array([[1]])
        gold = np.array([[2]])
        residual = {"type": "no_prediction", "diff_cells": -1, "diff_fraction": 1.0}
        cls = classify_residual(inp, None, gold, residual, {})
        assert cls == "unknown"
