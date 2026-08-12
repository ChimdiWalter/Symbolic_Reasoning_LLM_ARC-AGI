"""Tests for local_rules module."""
import numpy as np
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reasoning_project.local_rules import (
    induce_local_rule,
    apply_local_rule,
    apply_local_rule_with_fallback,
    synthesize_local_rules,
    solve_task_local_rules,
    multi_pass_local_rule,
    STRATEGY_REGISTRY,
)


def test_strategy_registry_not_empty():
    assert len(STRATEGY_REGISTRY) > 10


def test_induce_identity_rule():
    inp = np.array([[1, 2], [3, 4]])
    out = inp.copy()
    rule = induce_local_rule([(inp, out)], "cross")
    assert rule is not None
    pred = apply_local_rule(inp, rule)
    assert pred is not None
    np.testing.assert_array_equal(pred, out)


def test_induce_conflicting_returns_none():
    inp1 = np.array([[1, 1, 1], [1, 1, 1], [1, 1, 1]])
    out1 = np.array([[2, 2, 2], [2, 2, 2], [2, 2, 2]])
    inp2 = np.array([[1, 1, 1], [1, 1, 1], [1, 1, 1]])
    out2 = np.array([[3, 3, 3], [3, 3, 3], [3, 3, 3]])
    rule = induce_local_rule([(inp1, out1), (inp2, out2)], "cross")
    assert rule is None


def test_induce_color_count():
    inp = np.array([[0, 0, 0], [0, 1, 0], [0, 0, 0]])
    out = np.array([[0, 0, 0], [0, 2, 0], [0, 0, 0]])
    rule = induce_local_rule([(inp, out)], "color_count_r1")
    assert rule is not None


def test_synthesize_returns_sorted():
    inp = np.array([[1, 2, 3], [4, 5, 6], [7, 8, 9]])
    out = np.array([[9, 8, 7], [6, 5, 4], [3, 2, 1]])
    rules = synthesize_local_rules([(inp, out)])
    if rules:
        for i in range(len(rules) - 1):
            assert len(rules[i].mapping) <= len(rules[i + 1].mapping)


def test_solve_task_same_size():
    inp1 = np.array([[0, 1], [1, 0]])
    out1 = np.array([[1, 0], [0, 1]])
    inp2 = np.array([[0, 0], [1, 1]])
    out2 = np.array([[1, 1], [0, 0]])
    result = solve_task_local_rules([(inp1, out1), (inp2, out2)], [inp1])
    # May or may not solve depending on strategy
    # Just check it doesn't crash


def test_solve_task_different_size_returns_none():
    inp = np.array([[1, 2], [3, 4]])
    out = np.array([[1]])
    result = solve_task_local_rules([(inp, out)], [inp])
    assert result is None


def test_apply_with_fallback():
    inp = np.array([[1, 2], [3, 4]])
    out = inp.copy()
    rule = induce_local_rule([(inp, out)], "cross")
    if rule is not None:
        new_inp = np.array([[5, 6], [7, 8]])
        pred = apply_local_rule_with_fallback(new_inp, rule)
        assert pred.shape == new_inp.shape


def test_periodic_strategy():
    inp = np.zeros((4, 4), dtype=int)
    out = np.zeros((4, 4), dtype=int)
    for r in range(4):
        for c in range(4):
            out[r, c] = (r + c) % 2
    rule = induce_local_rule([(inp, out)], "periodic_2")
    assert rule is not None
    pred = apply_local_rule(inp, rule)
    assert pred is not None
    np.testing.assert_array_equal(pred, out)


def test_new_strategies_registered():
    for name in ["full_5x5_wrap", "cross_5", "row_projection", "col_projection",
                 "row_color_sig", "col_color_sig", "conditional_neighbor",
                 "color_position_boundary", "symmetry",
                 "simple_color_map", "absolute_position", "color_and_absolute",
                 "checkerboard", "row_index", "col_index", "binary_3x3",
                 "edge_detection", "global_color_rank", "neighbor_color_set",
                 "diagonal_position", "flood_region_size"]:
        assert name in STRATEGY_REGISTRY, f"Missing strategy: {name}"


def test_symmetry_strategy():
    inp = np.array([[1, 0, 1], [0, 2, 0], [1, 0, 1]])
    out = inp.copy()
    rule = induce_local_rule([(inp, out)], "symmetry")
    assert rule is not None


def test_conditional_neighbor_strategy():
    inp = np.array([[0, 1, 0], [1, 0, 1], [0, 1, 0]])
    out = np.array([[0, 1, 0], [1, 2, 1], [0, 1, 0]])
    rule = induce_local_rule([(inp, out)], "conditional_neighbor")
    if rule is not None:
        pred = apply_local_rule(inp, rule)
        assert pred is not None


def test_multi_pass_integration():
    result = solve_task_local_rules(
        [(np.array([[1, 2], [3, 4]]), np.array([[1, 2], [3, 4]]))],
        [np.array([[1, 2], [3, 4]])],
        try_multi_pass=True,
    )
    assert result is not None


def test_simple_color_map_strategy():
    inp = np.array([[1, 2, 3], [1, 2, 3], [1, 2, 3]])
    out = np.array([[4, 5, 6], [4, 5, 6], [4, 5, 6]])
    rule = induce_local_rule([(inp, out)], "simple_color_map")
    assert rule is not None
    pred = apply_local_rule(inp, rule)
    assert pred is not None
    np.testing.assert_array_equal(pred, out)


def test_checkerboard_strategy():
    inp = np.zeros((4, 4), dtype=int)
    out = np.array([[(r + c) % 2 for c in range(4)] for r in range(4)])
    rule = induce_local_rule([(inp, out)], "checkerboard")
    assert rule is not None
    pred = apply_local_rule(inp, rule)
    assert pred is not None
    np.testing.assert_array_equal(pred, out)


def test_edge_detection_strategy():
    inp = np.array([[1, 1, 1], [1, 1, 1], [1, 1, 1]])
    out = inp.copy()
    rule = induce_local_rule([(inp, out)], "edge_detection")
    assert rule is not None


def test_flood_region_size_strategy():
    inp = np.array([[1, 1, 0], [1, 1, 0], [0, 0, 2]])
    out = np.array([[3, 3, 0], [3, 3, 0], [0, 0, 4]])
    rule = induce_local_rule([(inp, out)], "flood_region_size")
    assert rule is not None


def test_binary_3x3_strategy():
    inp = np.array([[0, 1, 0], [1, 0, 1], [0, 1, 0]])
    out = np.array([[0, 1, 0], [1, 2, 1], [0, 1, 0]])
    rule = induce_local_rule([(inp, out)], "binary_3x3")
    assert rule is not None


def test_global_color_rank_strategy():
    inp = np.array([[0, 0, 0], [0, 1, 0], [0, 0, 0]])
    out = np.array([[2, 2, 2], [2, 3, 2], [2, 2, 2]])
    rule = induce_local_rule([(inp, out)], "global_color_rank")
    assert rule is not None


def test_absolute_position_strategy():
    inp = np.array([[0, 0], [0, 0]])
    out = np.array([[1, 2], [3, 4]])
    rule = induce_local_rule([(inp, out)], "absolute_position")
    assert rule is not None
    pred = apply_local_rule(inp, rule)
    np.testing.assert_array_equal(pred, out)


def test_total_strategy_count():
    assert len(STRATEGY_REGISTRY) == 36


def test_row_color_sig_strategy():
    inp = np.array([[1, 2, 1], [3, 3, 3], [1, 2, 1]])
    out = np.array([[5, 5, 5], [6, 6, 6], [5, 5, 5]])
    rule = induce_local_rule([(inp, out)], "row_color_sig")
    if rule is not None:
        pred = apply_local_rule(inp, rule)
        if pred is not None:
            np.testing.assert_array_equal(pred, out)
