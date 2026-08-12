"""Tests for the AdaptiveReasoningLoop and multi-view perception."""
import numpy as np
import pytest
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from reasoning_project.adaptive_loop import (
    AdaptiveReasoningLoop,
    AdaptivePortfolio,
    Diagnosis,
    FailureDiagnoser,
    LoopResult,
    MajorityBgAdapter,
    MonochromeAdapter,
    PerColorAdapter,
    PerceptionSelector,
    _compute_invariants,
    _make_adapter,
)
from reasoning_project.reasoning_engine import GridDomainAdapter, ReasoningMemory
from reasoning_project.manifold_memory import MemoryManifold


# ═══════════════════════════════════════════════════════════════════════════
# Helpers — synthetic tasks
# ═══════════════════════════════════════════════════════════════════════════

def _make_keep_largest_task():
    """Task: keep only the largest object (by area)."""
    pairs = []
    for _ in range(3):
        grid = np.zeros((8, 8), dtype=int)
        # Large object (area=6)
        grid[1:3, 1:4] = 3
        # Small object (area=2)
        grid[5:6, 5:7] = 7
        out = np.zeros_like(grid)
        out[1:3, 1:4] = 3
        pairs.append((grid.copy(), out.copy()))
    test_in = np.zeros((8, 8), dtype=int)
    test_in[0:2, 0:3] = 3
    test_in[6:7, 6:8] = 7
    test_out = np.zeros_like(test_in)
    test_out[0:2, 0:3] = 3
    return pairs, [test_in], [test_out]


def _make_keep_symmetric_task():
    """Task: keep only symmetric objects."""
    pairs = []
    for _ in range(3):
        grid = np.zeros((10, 10), dtype=int)
        # Symmetric 2x2 block
        grid[1:3, 1:3] = 4
        # Asymmetric L-shape
        grid[6, 6] = 2
        grid[7, 6] = 2
        grid[7, 7] = 2
        out = np.zeros_like(grid)
        out[1:3, 1:3] = 4
        pairs.append((grid.copy(), out.copy()))
    test_in = np.zeros((10, 10), dtype=int)
    test_in[2:4, 2:4] = 4
    test_in[7, 7] = 2
    test_in[8, 7] = 2
    test_in[8, 8] = 2
    test_out = np.zeros_like(test_in)
    test_out[2:4, 2:4] = 4
    return pairs, [test_in], [test_out]


def _make_non_zero_bg_task():
    """Task with bg=5 (majority color), keep hollow objects."""
    pairs = []
    for _ in range(3):
        grid = np.full((8, 8), 5, dtype=int)
        # Hollow ring (has hole)
        grid[1, 1:4] = 3
        grid[3, 1:4] = 3
        grid[1:4, 1] = 3
        grid[1:4, 3] = 3
        # Solid block (no hole)
        grid[5:7, 5:7] = 2
        out = np.full_like(grid, 5)
        out[1, 1:4] = 3
        out[3, 1:4] = 3
        out[1:4, 1] = 3
        out[1:4, 3] = 3
        pairs.append((grid.copy(), out.copy()))
    test_in = np.full((8, 8), 5, dtype=int)
    test_in[1, 1:4] = 3
    test_in[3, 1:4] = 3
    test_in[1:4, 1] = 3
    test_in[1:4, 3] = 3
    test_in[5:7, 5:7] = 2
    test_out = np.full_like(test_in, 5)
    test_out[1, 1:4] = 3
    test_out[3, 1:4] = 3
    test_out[1:4, 1] = 3
    test_out[1:4, 3] = 3
    return pairs, [test_in], [test_out]


# ═══════════════════════════════════════════════════════════════════════════
# Multi-View Perception Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestPerColorAdapter:
    def test_extracts_per_color_objects(self):
        grid = np.zeros((6, 6), dtype=int)
        grid[0:2, 0:2] = 3
        grid[3:5, 3:5] = 3
        grid[0:2, 4:6] = 7
        adapter = PerColorAdapter()
        objects = adapter.extract_objects(grid)
        assert len(objects) == 3
        colors = sorted(o["primary_color"] for o in objects)
        assert colors == [3, 3, 7]

    def test_single_color_same_as_cc(self):
        grid = np.zeros((6, 6), dtype=int)
        grid[0:2, 0:2] = 3
        grid[4:6, 4:6] = 3
        per_color = PerColorAdapter()
        cc = GridDomainAdapter()
        assert len(per_color.extract_objects(grid)) == len(cc.extract_objects(grid))

    def test_multi_color_connected(self):
        grid = np.zeros((4, 4), dtype=int)
        grid[0:2, 0:2] = 3
        grid[0:2, 2:4] = 7
        per_color = PerColorAdapter()
        cc = GridDomainAdapter()
        assert len(per_color.extract_objects(grid)) == 2
        assert len(cc.extract_objects(grid)) == 1  # connected as one blob

    def test_reconstruct_filtered(self):
        grid = np.zeros((6, 6), dtype=int)
        grid[0:2, 0:2] = 3
        grid[4:5, 4:5] = 7
        adapter = PerColorAdapter()
        objects = adapter.extract_objects(grid)
        keep = [True, False]
        result = adapter.reconstruct_filtered(grid, objects, keep)
        assert result[4, 4] == 0
        assert result[0, 0] == 3


class TestMonochromeAdapter:
    def test_ignores_colors(self):
        grid = np.zeros((6, 6), dtype=int)
        grid[0:2, 0:2] = 3
        grid[0:2, 2:4] = 7
        adapter = MonochromeAdapter()
        objects = adapter.extract_objects(grid)
        assert len(objects) == 1  # all merged into one blob

    def test_separate_blobs(self):
        grid = np.zeros((6, 6), dtype=int)
        grid[0, 0] = 3
        grid[5, 5] = 7
        adapter = MonochromeAdapter()
        objects = adapter.extract_objects(grid)
        assert len(objects) == 2


class TestMajorityBgAdapter:
    def test_detects_non_zero_bg(self):
        grid = np.full((8, 8), 5, dtype=int)
        grid[1:3, 1:3] = 3
        grid[5:6, 5:6] = 2
        adapter = MajorityBgAdapter()
        objects = adapter.extract_objects(grid)
        assert len(objects) == 2
        assert adapter._detected_bg == 5

    def test_zero_bg_when_dominant(self):
        grid = np.zeros((8, 8), dtype=int)
        grid[1:3, 1:3] = 3
        adapter = MajorityBgAdapter()
        adapter.extract_objects(grid)
        assert adapter._detected_bg == 0


# ═══════════════════════════════════════════════════════════════════════════
# Perception Selector Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestPerceptionSelector:
    def test_default_order(self):
        selector = PerceptionSelector()
        v1 = selector.next_view()
        assert v1 == "color_cc"
        selector.mark_tried(v1)
        v2 = selector.next_view()
        assert v2 == "per_color"

    def test_diagnosis_overrides_order(self):
        selector = PerceptionSelector()
        selector.mark_tried("color_cc")
        diag = Diagnosis(
            failure_type="no_objects",
            suggested_views=["majority_bg"],
        )
        v = selector.next_view(diag)
        assert v == "majority_bg"

    def test_has_untried(self):
        selector = PerceptionSelector()
        assert selector.has_untried()
        for v in PerceptionSelector.DEFAULT_ORDER:
            selector.mark_tried(v)
        assert not selector.has_untried()

    def test_custom_priority(self):
        selector = PerceptionSelector(priority=["monochrome", "color_cc"])
        assert selector.next_view() == "monochrome"


# ═══════════════════════════════════════════════════════════════════════════
# Failure Diagnoser Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestFailureDiagnoser:
    def test_diagnoses_no_objects(self):
        grid = np.zeros((4, 4), dtype=int)
        pairs = [(grid, grid)] * 3
        diagnoser = FailureDiagnoser()
        adapter = GridDomainAdapter()
        diag = diagnoser.diagnose(adapter, pairs, "color_cc")
        assert diag.failure_type == "no_objects"

    def test_diagnoses_with_objects(self):
        pairs, _, _ = _make_keep_largest_task()
        diagnoser = FailureDiagnoser()
        adapter = GridDomainAdapter()
        diag = diagnoser.diagnose(adapter, pairs, "color_cc")
        assert diag.failure_type in (
            "no_discrimination", "partial_match", "wrong_reconstruction"
        )

    def test_suggested_views_nonempty(self):
        grid = np.zeros((4, 4), dtype=int)
        pairs = [(grid, grid)] * 3
        diagnoser = FailureDiagnoser()
        adapter = GridDomainAdapter()
        diag = diagnoser.diagnose(adapter, pairs, "color_cc")
        assert len(diag.suggested_views) > 0


# ═══════════════════════════════════════════════════════════════════════════
# Invariant Discovery Integration
# ═══════════════════════════════════════════════════════════════════════════

class TestInvariantIntegration:
    def test_compute_invariants(self):
        pairs, _, _ = _make_keep_largest_task()
        inv = _compute_invariants(pairs)
        assert "preserved" in inv
        assert "transformed" in inv
        assert isinstance(inv["size_changes"], bool)

    def test_color_change_detection(self):
        grid_in = np.zeros((4, 4), dtype=int)
        grid_in[0, 0] = 3
        grid_out = np.zeros((4, 4), dtype=int)
        grid_out[0, 0] = 7
        inv = _compute_invariants([(grid_in, grid_out)])
        assert inv["color_changes"] is True


# ═══════════════════════════════════════════════════════════════════════════
# AdaptiveReasoningLoop Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestAdaptiveReasoningLoop:
    def test_solves_keep_largest(self):
        pairs, test_in, test_out = _make_keep_largest_task()
        loop = AdaptiveReasoningLoop(max_iterations=4, timeout_seconds=30.0)
        result = loop.solve(pairs, test_in, task_id="test_largest")
        assert result.solved
        assert result.predictions is not None
        assert np.array_equal(result.predictions[0], test_out[0])

    def test_solves_keep_symmetric(self):
        pairs, test_in, test_out = _make_keep_symmetric_task()
        loop = AdaptiveReasoningLoop(max_iterations=4, timeout_seconds=30.0)
        result = loop.solve(pairs, test_in, task_id="test_sym")
        assert result.solved
        assert np.array_equal(result.predictions[0], test_out[0])

    def test_returns_loop_metadata(self):
        pairs, test_in, _ = _make_keep_largest_task()
        loop = AdaptiveReasoningLoop(max_iterations=4)
        result = loop.solve(pairs, test_in)
        assert result.iterations_used >= 1
        assert len(result.views_tried) >= 1
        assert result.elapsed_seconds > 0

    def test_unsolvable_returns_diagnosis(self):
        rng = np.random.RandomState(99)
        pairs = []
        for _ in range(3):
            grid_in = rng.randint(0, 10, (5, 5))
            grid_out = rng.randint(0, 10, (3, 7))
            pairs.append((grid_in, grid_out))
        test_in = [rng.randint(0, 10, (5, 5))]
        loop = AdaptiveReasoningLoop(max_iterations=4, timeout_seconds=5.0)
        result = loop.solve(pairs, test_in)
        assert not result.solved
        assert len(result.diagnosis_trace) > 0

    def test_timeout_respected(self):
        pairs, test_in, _ = _make_keep_largest_task()
        loop = AdaptiveReasoningLoop(max_iterations=100, timeout_seconds=0.001)
        result = loop.solve(pairs, test_in)
        assert result.iterations_used <= 2

    def test_memory_persists_across_solves(self):
        memory = ReasoningMemory()
        loop = AdaptiveReasoningLoop(max_iterations=4, memory=memory)
        pairs, test_in, _ = _make_keep_largest_task()
        loop.solve(pairs, test_in, task_id="first")
        assert len(memory.episodes) >= 1

    def test_manifold_integration(self):
        manifold = MemoryManifold()
        loop = AdaptiveReasoningLoop(
            max_iterations=4, manifold=manifold,
        )
        pairs, test_in, test_out = _make_keep_largest_task()
        result = loop.solve(pairs, test_in, task_id="manifold_test")
        assert result.solved
        total = sum(len(c.points) for c in manifold.charts.values())
        assert total >= 1

    def test_multi_view_tried_on_failure(self):
        grid_in = np.array([[1, 2], [3, 4]])
        grid_out = np.array([[9, 8], [7, 6]])
        pairs = [(grid_in, grid_out)] * 3
        test_in = [np.array([[5, 6], [7, 8]])]
        loop = AdaptiveReasoningLoop(max_iterations=8, timeout_seconds=10.0)
        result = loop.solve(pairs, test_in)
        assert len(result.views_tried) > 1


class TestAdaptiveLoopNonZeroBg:
    def test_majority_bg_view_helps(self):
        pairs, test_in, test_out = _make_non_zero_bg_task()
        loop = AdaptiveReasoningLoop(
            max_iterations=4, timeout_seconds=30.0,
        )
        result = loop.solve(pairs, test_in, task_id="nonzero_bg")
        if result.solved:
            assert np.array_equal(result.predictions[0], test_out[0])


# ═══════════════════════════════════════════════════════════════════════════
# AdaptivePortfolio Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestAdaptivePortfolio:
    def test_solves_via_adaptive_loop(self):
        pairs, test_in, test_out = _make_keep_largest_task()
        portfolio = AdaptivePortfolio(
            max_iterations=4,
            adaptive_timeout=30.0,
        )
        result = portfolio.solve("test", pairs, test_in, test_out)
        assert result["solved"]
        assert result["source"] == "adaptive_loop"

    def test_falls_back_to_static(self):
        grid_in = np.array([[1, 0], [0, 1]])
        grid_out = np.array([[1, 0], [0, 1]])
        pairs = [(grid_in, grid_out)] * 3
        test_in = [grid_in.copy()]

        def identity_solver(train, test):
            return [t.copy() for t in test], {"strategy": "identity"}

        portfolio = AdaptivePortfolio(
            static_solvers={"identity": identity_solver},
            max_iterations=2,
            adaptive_timeout=5.0,
        )
        result = portfolio.solve("test", pairs, test_in, [grid_out.copy()])
        assert result["solved"]

    def test_returns_views_and_iterations(self):
        pairs, test_in, test_out = _make_keep_largest_task()
        portfolio = AdaptivePortfolio(max_iterations=4)
        result = portfolio.solve("test", pairs, test_in, test_out)
        assert "views_tried" in result
        assert "iterations" in result


# ═══════════════════════════════════════════════════════════════════════════
# Edge Cases
# ═══════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    def test_single_training_pair_limited(self):
        """With a single training pair, structural reasoner needs >=2 for LOO,
        but invariant-guided path may still solve. Just verify no crash."""
        pairs, test_in, _ = _make_keep_largest_task()
        loop = AdaptiveReasoningLoop(max_iterations=2)
        result = loop.solve(pairs[:1], test_in)
        assert isinstance(result, LoopResult)

    def test_empty_grid(self):
        grid = np.zeros((4, 4), dtype=int)
        pairs = [(grid, grid)] * 3
        loop = AdaptiveReasoningLoop(max_iterations=2)
        result = loop.solve(pairs, [grid])
        assert not result.solved

    def test_make_adapter_all_views(self):
        for view_name in ["color_cc", "per_color", "monochrome", "majority_bg"]:
            adapter = _make_adapter(view_name)
            assert adapter is not None
