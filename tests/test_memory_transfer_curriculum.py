"""Tests for curriculum task generation and memory transfer logic."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import pytest
from scipy import ndimage

# Ensure project is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from reasoning_project.view_adapters import (
    FrameInteriorAdapter,
    ColorLayerAdapter,
    ObjectInObjectAdapter,
)
from reasoning_project.adaptive_memory import AdaptiveMemory, _compute_task_signature
from reasoning_project.reasoning_engine import _extract_objects_with_properties


class TestCurriculumTaskValidity:
    """Test that generated curriculum tasks are valid."""

    @pytest.fixture
    def curriculum_tasks(self):
        # Import the builder
        from build_adaptive_memory_curriculum import build_curriculum
        return build_curriculum()

    def test_all_tasks_have_required_keys(self, curriculum_tasks):
        required = ["task_id", "group", "subgroup", "role", "train", "test"]
        for task in curriculum_tasks:
            for key in required:
                assert key in task, f"Task {task.get('task_id', '?')} missing key {key}"

    def test_all_grids_valid(self, curriculum_tasks):
        for task in curriculum_tasks:
            tid = task["task_id"]
            for i, pair in enumerate(task["train"]):
                inp = np.array(pair["input"])
                out = np.array(pair["output"])
                assert inp.min() >= 0 and inp.max() <= 9, \
                    f"{tid} train[{i}] input values out of range"
                assert out.min() >= 0 and out.max() <= 9, \
                    f"{tid} train[{i}] output values out of range"
                assert inp.ndim == 2, f"{tid} train[{i}] input not 2D"
                assert out.ndim == 2, f"{tid} train[{i}] output not 2D"

            for i, pair in enumerate(task["test"]):
                inp = np.array(pair["input"])
                out = np.array(pair["output"])
                assert inp.min() >= 0 and inp.max() <= 9
                assert out.min() >= 0 and out.max() <= 9

    def test_train_pairs_minimum(self, curriculum_tasks):
        for task in curriculum_tasks:
            assert len(task["train"]) >= 2, \
                f"{task['task_id']} has fewer than 2 train pairs"

    def test_test_pairs_exist(self, curriculum_tasks):
        for task in curriculum_tasks:
            assert len(task["test"]) >= 1, \
                f"{task['task_id']} has no test pairs"

    def test_grid_sizes_reasonable(self, curriculum_tasks):
        for task in curriculum_tasks:
            for pair in task["train"] + task["test"]:
                inp = np.array(pair["input"])
                h, w = inp.shape
                assert 3 <= h <= 12, f"{task['task_id']} grid height {h} out of range"
                assert 3 <= w <= 12, f"{task['task_id']} grid width {w} out of range"


class TestFrameInteriorTasksDefaultParserFails:
    """Verify that the default parser genuinely fails on frame-interior tasks."""

    @pytest.fixture
    def frame_tasks(self):
        from build_adaptive_memory_curriculum import build_curriculum
        tasks = build_curriculum()
        return [t for t in tasks if t.get("subgroup") == "frame_interior"]

    def test_frame_is_largest_component(self, frame_tasks):
        """The default parser should see the frame as the largest object."""
        for task in frame_tasks:
            inp = np.array(task["train"][0]["input"])
            objects = _extract_objects_with_properties(inp)
            if not objects:
                continue
            # Find the largest object
            largest = max(objects, key=lambda o: o["area"])
            # It should touch the border (it's the frame)
            assert largest.get("touches_boundary", False), \
                f"{task['task_id']}: largest object doesn't touch boundary"


class TestColorLayerTasks:
    """Verify color layer task consistency."""

    @pytest.fixture
    def color_tasks(self):
        from build_adaptive_memory_curriculum import build_curriculum
        tasks = build_curriculum()
        return [t for t in tasks if t.get("subgroup") == "color_layer"]

    def test_output_removes_one_color(self, color_tasks):
        for task in color_tasks:
            inp = np.array(task["train"][0]["input"])
            out = np.array(task["train"][0]["output"])
            inp_colors = set(inp.flatten().tolist()) - {0}
            out_colors = set(out.flatten().tolist()) - {0}
            removed = inp_colors - out_colors
            assert len(removed) >= 1, \
                f"{task['task_id']}: no color removed"


class TestContainmentTasks:
    """Verify containment task structure."""

    @pytest.fixture
    def containment_tasks(self):
        from build_adaptive_memory_curriculum import build_curriculum
        tasks = build_curriculum()
        return [t for t in tasks if t.get("subgroup") == "object_in_object"]

    def test_containment_detectable(self, containment_tasks):
        adapter = ObjectInObjectAdapter()
        for task in containment_tasks:
            inp = np.array(task["train"][0]["input"])
            assert adapter.can_apply(inp), \
                f"{task['task_id']}: containment not detected"


class TestMemoryTransferLogic:
    """Test the memory store-and-retrieve logic."""

    def test_store_from_seed_retrieve_for_heldout(self):
        memory = AdaptiveMemory()
        adapter = FrameInteriorAdapter()

        # Store from a seed-like task
        seed_inp = np.full((7, 7), 3, dtype=int)
        seed_inp[1:6, 1:6] = 0
        seed_inp[2:4, 2:4] = 1
        seed_out = seed_inp.copy()

        memory.store_verified_package(
            "seed_task",
            adapter,
            "discriminative_filter",
            "is_largest",
            "",
            [(seed_inp, seed_out)],
        )

        # Retrieve for a structurally similar held-out task
        heldout_inp = np.full((8, 8), 5, dtype=int)
        heldout_inp[1:7, 1:7] = 0
        heldout_inp[2:5, 2:5] = 2
        heldout_out = heldout_inp.copy()

        sig = _compute_task_signature([(heldout_inp, heldout_out)])
        results = memory.retrieve_by_signature(sig, top_k=1)
        assert len(results) == 1
        assert results[0].adapter_type == "frame_interior"

    def test_frozen_memory_retrieves_but_cannot_store(self):
        memory = AdaptiveMemory()
        adapter = FrameInteriorAdapter()
        inp = np.zeros((5, 5), dtype=int)
        out = inp.copy()

        memory.store_verified_package("t1", adapter, "f", "s", "", [(inp, out)])
        memory.freeze()

        # Can still retrieve
        sig = _compute_task_signature([(inp, out)])
        results = memory.retrieve_by_signature(sig)
        assert len(results) == 1

        # Cannot store
        with pytest.raises(RuntimeError):
            memory.store_verified_package("t2", adapter, "f", "s", "", [(inp, out)])
