"""Tests for CEGIS solver."""
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reasoning_project.cegis import (
    CEGISSolver,
    _find_failed_pixels,
    _extract_counterexample,
)


def test_find_failed_pixels_all_match():
    a = np.array([[1, 2], [3, 4]])
    assert _find_failed_pixels(a, a) == []


def test_find_failed_pixels_some_mismatch():
    a = np.array([[1, 2], [3, 4]])
    b = np.array([[1, 9], [3, 4]])
    failed = _find_failed_pixels(a, b)
    assert (0, 1) in failed
    assert len(failed) == 1


def test_find_failed_pixels_shape_mismatch():
    a = np.array([[1, 2]])
    b = np.array([[1, 2], [3, 4]])
    failed = _find_failed_pixels(a, b)
    assert len(failed) == 4


def test_extract_counterexample():
    inp = np.array([[1]])
    out = np.array([[2]])
    pred = np.array([[3]])
    cx = _extract_counterexample(inp, out, pred, 0)
    assert cx.example_index == 0
    assert cx.failure_fraction == 1.0
    assert len(cx.failed_pixels) == 1


def test_cegis_solver_with_identity():
    inp1 = np.array([[1, 2], [3, 4]])
    out1 = inp1.copy()
    candidates = [lambda g: g.copy()]
    solver = CEGISSolver(dsl_candidates=candidates, max_refinement_steps=10)
    result = solver.solve([(inp1, out1)], [inp1])
    assert result.solved
    assert result.predictions is not None
    np.testing.assert_array_equal(result.predictions[0], inp1)


def test_cegis_solver_no_dsl_falls_back_to_local():
    inp1 = np.array([[1, 2], [3, 4]])
    out1 = np.array([[4, 3], [2, 1]])
    solver = CEGISSolver(dsl_candidates=[], max_refinement_steps=10)
    result = solver.solve([(inp1, out1)], [inp1])
    assert result.solved
    assert result.best_candidate.hypothesis_type == "local_rule"


def test_cegis_solver_no_candidates_different_size_fails():
    inp1 = np.array([[1, 2], [3, 4]])
    out1 = np.array([[1]])
    solver = CEGISSolver(dsl_candidates=[], max_refinement_steps=10)
    result = solver.solve([(inp1, out1)], [inp1])
    assert not result.solved


def test_cegis_solver_counterexample_count():
    inp1 = np.array([[1, 2], [3, 4]])
    out1 = np.array([[4, 3], [2, 1]])
    wrong1 = lambda g: g.copy()
    wrong2 = lambda g: np.zeros_like(g)
    solver = CEGISSolver(dsl_candidates=[wrong1, wrong2], max_refinement_steps=10)
    result = solver.solve([(inp1, out1)], [inp1])
    assert result.total_counterexamples > 0


def test_cegis_trace_recorded():
    inp1 = np.array([[1]])
    out1 = np.array([[2]])
    candidates = [lambda g: g.copy(), lambda g: g * 2]
    solver = CEGISSolver(dsl_candidates=candidates, max_refinement_steps=10)
    result = solver.solve([(inp1, out1)], [inp1])
    assert len(result.trace) > 0
