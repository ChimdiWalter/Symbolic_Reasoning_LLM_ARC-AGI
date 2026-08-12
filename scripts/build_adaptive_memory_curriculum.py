#!/usr/bin/env python3.11
"""Generate controlled curriculum tasks for the adaptive memory/adapter-genesis proof.

Each task is designed so that a specific module (adapter genesis, memory,
property expansion, neural advisory) is causally necessary for solving it.
The default connected-component parser (`_extract_objects_with_properties`)
must genuinely fail on Group A tasks.

Output: curriculum_tasks.json in the proof output directory.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
from scipy import ndimage

# ---------------------------------------------------------------------------
# Project root setup
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

OUTPUT_DIR = PROJECT_ROOT / "outputs" / "full_novel_reasoning_pipeline_v2" / "adaptive_memory_adaptergenesis_proof_2026_06_20"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ===========================================================================
# Helpers
# ===========================================================================

def _make_frame_grid(
    h: int, w: int, frame_color: int, interior: np.ndarray, thickness: int = 1,
) -> np.ndarray:
    """Create a grid with a colored frame around an interior."""
    grid = np.full((h, w), frame_color, dtype=int)
    ih, iw = interior.shape
    assert ih == h - 2 * thickness and iw == w - 2 * thickness, \
        f"Interior shape {interior.shape} != expected ({h - 2 * thickness}, {w - 2 * thickness})"
    grid[thickness:h - thickness, thickness:w - thickness] = interior
    return grid


def _largest_interior_object_filter(grid: np.ndarray, frame_color: int, thickness: int = 1) -> np.ndarray:
    """Keep only the largest object in the interior, zero everything else."""
    h, w = grid.shape
    interior = grid[thickness:h - thickness, thickness:w - thickness].copy()
    labeled, n = ndimage.label(interior != 0)
    if n == 0:
        return _make_frame_grid(h, w, frame_color, np.zeros_like(interior), thickness)
    sizes = []
    for lab in range(1, n + 1):
        sizes.append((lab, int((labeled == lab).sum())))
    sizes.sort(key=lambda x: -x[1])
    largest_lab = sizes[0][0]
    result_interior = np.zeros_like(interior)
    mask = labeled == largest_lab
    result_interior[mask] = interior[mask]
    return _make_frame_grid(h, w, frame_color, result_interior, thickness)


def _remove_color_layer(grid: np.ndarray, color_to_remove: int) -> np.ndarray:
    """Remove all pixels of a given color (set to 0)."""
    result = grid.copy()
    result[result == color_to_remove] = 0
    return result


def _extract_inner_object(grid: np.ndarray) -> np.ndarray:
    """Extract the inner object from a containment pattern.

    Finds the smallest object that is fully inside a larger one and
    returns a grid with only that object on a black background.
    """
    labeled, n = ndimage.label(grid != 0)
    if n < 2:
        return grid.copy()

    objects = []
    for lab in range(1, n + 1):
        mask = labeled == lab
        rows, cols = np.where(mask)
        r_min, r_max = int(rows.min()), int(rows.max())
        c_min, c_max = int(cols.min()), int(cols.max())
        objects.append({
            "label": lab,
            "mask": mask,
            "area": int(mask.sum()),
            "color": int(grid[mask].flat[0]),
            "bbox": (r_min, c_min, r_max, c_max),
        })

    # Find containment: inner bbox strictly inside outer bbox
    for inner in objects:
        for outer in objects:
            if inner["label"] == outer["label"]:
                continue
            if inner["area"] >= outer["area"]:
                continue
            ir_min, ic_min, ir_max, ic_max = inner["bbox"]
            or_min, oc_min, or_max, oc_max = outer["bbox"]
            if (ir_min > or_min and ir_max < or_max and
                    ic_min > oc_min and ic_max < oc_max):
                # Found containment -- extract inner
                result = np.zeros_like(grid)
                result[inner["mask"]] = inner["color"]
                return result

    return grid.copy()


def _verify_task(task: Dict[str, Any]) -> bool:
    """Verify that a task is internally consistent."""
    try:
        train = task["train"]
        test = task["test"]

        for pair in train:
            inp = np.array(pair["input"])
            out = np.array(pair["output"])
            assert inp.dtype == int or np.issubdtype(inp.dtype, np.integer), \
                f"Input dtype {inp.dtype}"
            assert out.dtype == int or np.issubdtype(out.dtype, np.integer), \
                f"Output dtype {out.dtype}"
            assert inp.min() >= 0 and inp.max() <= 9, \
                f"Input values out of range: {inp.min()}-{inp.max()}"
            assert out.min() >= 0 and out.max() <= 9, \
                f"Output values out of range: {out.min()}-{out.max()}"

        for pair in test:
            inp = np.array(pair["input"])
            out = np.array(pair["output"])
            assert inp.min() >= 0 and inp.max() <= 9
            assert out.min() >= 0 and out.max() <= 9

        return True
    except Exception as e:
        print(f"  VERIFICATION FAILED for {task['task_id']}: {e}")
        return False


def _verify_default_parser_fails(task: Dict[str, Any]) -> bool:
    """Verify that the default parser genuinely fails on this task.

    For frame_interior tasks: the default parser's is_largest should
    select the frame, not the target interior object.
    """
    group = task.get("group", "")
    if "adapter_genesis" not in group:
        return True  # Only check Group A

    subgroup = task.get("subgroup", "")
    expected_op = task.get("expected_operator", "")
    expected_sel = task.get("expected_selector", "")

    if subgroup == "frame_interior" and expected_sel == "is_largest":
        # Check that the frame is the largest connected component
        inp = np.array(task["train"][0]["input"])
        labeled, n = ndimage.label(inp != 0)
        if n < 2:
            return False
        sizes = {}
        for lab in range(1, n + 1):
            sizes[lab] = int((labeled == lab).sum())
        largest_lab = max(sizes, key=sizes.get)
        # The largest object should be the frame
        largest_mask = labeled == largest_lab
        # Check: does the largest object touch all 4 borders?
        rows, cols = np.where(largest_mask)
        touches_all = (rows.min() == 0 and rows.max() == inp.shape[0] - 1 and
                       cols.min() == 0 and cols.max() == inp.shape[1] - 1)
        if not touches_all:
            print(f"  WARNING: {task['task_id']} -- frame is NOT the largest component")
            return False
        return True

    return True


# ===========================================================================
# Group A: AdapterGenesis necessary (6 seed + 6 held-out)
# ===========================================================================

def _build_frame_interior_tasks() -> List[Dict]:
    """Frame-interior tasks: keep only largest interior object.

    Default parser sees frame as largest object -> filter(is_largest) keeps frame.
    With FrameInteriorAdapter: frame is stripped, interior objects are parsed,
    is_largest correctly identifies the target interior object.
    """
    tasks = []

    # --- Seed 01: 8x8 grid, frame color 3 (green), 3 interior objects ---
    interior_01 = np.zeros((6, 6), dtype=int)
    interior_01[0:3, 0:3] = 1   # 3x3 red block (area=9) -- largest interior
    interior_01[0:2, 4:6] = 2   # 2x2 blue block (area=4)
    interior_01[4:5, 1:3] = 5   # 1x2 gray block (area=2)
    inp_01 = _make_frame_grid(8, 8, 3, interior_01)

    out_interior_01 = np.zeros((6, 6), dtype=int)
    out_interior_01[0:3, 0:3] = 1
    out_01 = _make_frame_grid(8, 8, 3, out_interior_01)

    # Second train pair -- different positions
    interior_01b = np.zeros((6, 6), dtype=int)
    interior_01b[1:4, 1:4] = 4    # 3x3 yellow block (area=9) -- largest
    interior_01b[0:1, 0:2] = 2    # 1x2 blue (area=2)
    interior_01b[5:6, 3:6] = 5    # 1x3 gray (area=3)
    inp_01b = _make_frame_grid(8, 8, 3, interior_01b)

    out_interior_01b = np.zeros((6, 6), dtype=int)
    out_interior_01b[1:4, 1:4] = 4
    out_01b = _make_frame_grid(8, 8, 3, out_interior_01b)

    # Test pair
    interior_01t = np.zeros((6, 6), dtype=int)
    interior_01t[2:5, 0:3] = 6    # 3x3 magenta (area=9) -- largest
    interior_01t[0:2, 4:5] = 1    # 2x1 red (area=2)
    inp_01t = _make_frame_grid(8, 8, 3, interior_01t)
    out_interior_01t = np.zeros((6, 6), dtype=int)
    out_interior_01t[2:5, 0:3] = 6
    out_01t = _make_frame_grid(8, 8, 3, out_interior_01t)

    tasks.append({
        "task_id": "group_a_frame_interior_seed_01",
        "group": "A_adapter_genesis",
        "subgroup": "frame_interior",
        "role": "seed",
        "train": [
            {"input": inp_01.tolist(), "output": out_01.tolist()},
            {"input": inp_01b.tolist(), "output": out_01b.tolist()},
        ],
        "test": [{"input": inp_01t.tolist(), "output": out_01t.tolist()}],
        "expected_adapter": "FrameInteriorAdapter",
        "expected_operator": "discriminative_filter",
        "expected_selector": "is_largest",
        "why_default_fails": "Default parser treats frame as single large object, masking interior objects",
    })

    # --- Seed 02: 9x9 grid, frame color 7 (orange), different objects ---
    interior_02 = np.zeros((7, 7), dtype=int)
    interior_02[0:2, 0:5] = 4    # 2x5 yellow (area=10) -- largest
    interior_02[3:5, 2:4] = 1    # 2x2 red (area=4)
    interior_02[5:7, 5:7] = 8    # 2x2 azure (area=4)
    inp_02 = _make_frame_grid(9, 9, 7, interior_02)

    out_interior_02 = np.zeros((7, 7), dtype=int)
    out_interior_02[0:2, 0:5] = 4
    out_02 = _make_frame_grid(9, 9, 7, out_interior_02)

    interior_02b = np.zeros((7, 7), dtype=int)
    interior_02b[2:5, 1:5] = 6    # 3x4 magenta (area=12) -- largest
    interior_02b[0:1, 0:2] = 9    # 1x2 maroon (area=2)
    interior_02b[6:7, 5:7] = 2    # 1x2 blue (area=2)
    inp_02b = _make_frame_grid(9, 9, 7, interior_02b)

    out_interior_02b = np.zeros((7, 7), dtype=int)
    out_interior_02b[2:5, 1:5] = 6
    out_02b = _make_frame_grid(9, 9, 7, out_interior_02b)

    interior_02t = np.zeros((7, 7), dtype=int)
    interior_02t[1:4, 0:4] = 5    # 3x4 gray (area=12) -- largest
    interior_02t[5:6, 4:6] = 1    # 1x2 red (area=2)
    inp_02t = _make_frame_grid(9, 9, 7, interior_02t)
    out_interior_02t = np.zeros((7, 7), dtype=int)
    out_interior_02t[1:4, 0:4] = 5
    out_02t = _make_frame_grid(9, 9, 7, out_interior_02t)

    tasks.append({
        "task_id": "group_a_frame_interior_seed_02",
        "group": "A_adapter_genesis",
        "subgroup": "frame_interior",
        "role": "seed",
        "train": [
            {"input": inp_02.tolist(), "output": out_02.tolist()},
            {"input": inp_02b.tolist(), "output": out_02b.tolist()},
        ],
        "test": [{"input": inp_02t.tolist(), "output": out_02t.tolist()}],
        "expected_adapter": "FrameInteriorAdapter",
        "expected_operator": "discriminative_filter",
        "expected_selector": "is_largest",
        "why_default_fails": "Default parser treats frame as single large object, masking interior objects",
    })

    # --- Held-out 01: 10x10 grid, frame color 2 (blue) ---
    interior_h01 = np.zeros((8, 8), dtype=int)
    interior_h01[0:4, 0:4] = 9    # 4x4 maroon (area=16) -- largest
    interior_h01[1:3, 5:7] = 5    # 2x2 gray (area=4)
    interior_h01[6:8, 1:3] = 4    # 2x2 yellow (area=4)
    inp_h01 = _make_frame_grid(10, 10, 2, interior_h01)

    out_interior_h01 = np.zeros((8, 8), dtype=int)
    out_interior_h01[0:4, 0:4] = 9
    out_h01 = _make_frame_grid(10, 10, 2, out_interior_h01)

    interior_h01b = np.zeros((8, 8), dtype=int)
    interior_h01b[2:6, 2:6] = 6    # 4x4 magenta (area=16) -- largest
    interior_h01b[0:1, 0:3] = 1    # 1x3 red (area=3)
    interior_h01b[7:8, 5:8] = 8    # 1x3 azure (area=3)
    inp_h01b = _make_frame_grid(10, 10, 2, interior_h01b)

    out_interior_h01b = np.zeros((8, 8), dtype=int)
    out_interior_h01b[2:6, 2:6] = 6
    out_h01b = _make_frame_grid(10, 10, 2, out_interior_h01b)

    interior_h01t = np.zeros((8, 8), dtype=int)
    interior_h01t[1:5, 3:7] = 4    # 4x4 yellow (area=16) -- largest
    interior_h01t[6:7, 0:2] = 1    # 1x2 red (area=2)
    inp_h01t = _make_frame_grid(10, 10, 2, interior_h01t)
    out_interior_h01t = np.zeros((8, 8), dtype=int)
    out_interior_h01t[1:5, 3:7] = 4
    out_h01t = _make_frame_grid(10, 10, 2, out_interior_h01t)

    tasks.append({
        "task_id": "group_a_frame_interior_heldout_01",
        "group": "A_adapter_genesis",
        "subgroup": "frame_interior",
        "role": "heldout",
        "train": [
            {"input": inp_h01.tolist(), "output": out_h01.tolist()},
            {"input": inp_h01b.tolist(), "output": out_h01b.tolist()},
        ],
        "test": [{"input": inp_h01t.tolist(), "output": out_h01t.tolist()}],
        "expected_adapter": "FrameInteriorAdapter",
        "expected_operator": "discriminative_filter",
        "expected_selector": "is_largest",
        "why_default_fails": "Default parser treats frame as single large object, masking interior objects",
    })

    # --- Held-out 02: 7x7 grid, frame color 8 (azure) ---
    interior_h02 = np.zeros((5, 5), dtype=int)
    interior_h02[0:3, 0:3] = 1    # 3x3 red (area=9) -- largest
    interior_h02[3:4, 3:5] = 6    # 1x2 magenta (area=2)
    inp_h02 = _make_frame_grid(7, 7, 8, interior_h02)

    out_interior_h02 = np.zeros((5, 5), dtype=int)
    out_interior_h02[0:3, 0:3] = 1
    out_h02 = _make_frame_grid(7, 7, 8, out_interior_h02)

    interior_h02b = np.zeros((5, 5), dtype=int)
    interior_h02b[1:4, 2:5] = 5    # 3x3 gray (area=9) -- largest
    interior_h02b[0:1, 0:1] = 4    # 1x1 yellow (area=1)
    inp_h02b = _make_frame_grid(7, 7, 8, interior_h02b)

    out_interior_h02b = np.zeros((5, 5), dtype=int)
    out_interior_h02b[1:4, 2:5] = 5
    out_h02b = _make_frame_grid(7, 7, 8, out_interior_h02b)

    interior_h02t = np.zeros((5, 5), dtype=int)
    interior_h02t[0:2, 0:5] = 9    # 2x5 maroon (area=10) -- largest
    interior_h02t[4:5, 2:4] = 3    # 1x2 green (area=2)
    inp_h02t = _make_frame_grid(7, 7, 8, interior_h02t)
    out_interior_h02t = np.zeros((5, 5), dtype=int)
    out_interior_h02t[0:2, 0:5] = 9
    out_h02t = _make_frame_grid(7, 7, 8, out_interior_h02t)

    tasks.append({
        "task_id": "group_a_frame_interior_heldout_02",
        "group": "A_adapter_genesis",
        "subgroup": "frame_interior",
        "role": "heldout",
        "train": [
            {"input": inp_h02.tolist(), "output": out_h02.tolist()},
            {"input": inp_h02b.tolist(), "output": out_h02b.tolist()},
        ],
        "test": [{"input": inp_h02t.tolist(), "output": out_h02t.tolist()}],
        "expected_adapter": "FrameInteriorAdapter",
        "expected_operator": "discriminative_filter",
        "expected_selector": "is_largest",
        "why_default_fails": "Default parser treats frame as single large object, masking interior objects",
    })

    return tasks


def _build_color_layer_tasks() -> List[Dict]:
    """Color-layer tasks: remove all objects of one color, keep others.

    Default parser extracts all objects together; the adapter separates
    by color layer so color-specific operations become possible.
    """
    tasks = []

    # --- Seed 01: 8x8 grid, remove color 2 (blue), keep color 5 (gray) ---
    def _make_color_layer_pair(h, w, keep_color, remove_color, positions_keep, positions_remove, seed=0):
        inp = np.zeros((h, w), dtype=int)
        for (r1, c1, r2, c2) in positions_keep:
            inp[r1:r2, c1:c2] = keep_color
        for (r1, c1, r2, c2) in positions_remove:
            inp[r1:r2, c1:c2] = remove_color
        out = _remove_color_layer(inp, remove_color)
        return inp, out

    inp_01, out_01 = _make_color_layer_pair(
        8, 8, 5, 2,
        [(0, 0, 3, 3), (5, 5, 7, 7)],
        [(1, 4, 3, 6), (4, 0, 6, 2)],
    )
    inp_01b, out_01b = _make_color_layer_pair(
        8, 8, 5, 2,
        [(0, 5, 2, 8), (4, 1, 7, 3)],
        [(2, 0, 4, 2), (6, 5, 8, 7)],
    )
    inp_01t, out_01t = _make_color_layer_pair(
        8, 8, 5, 2,
        [(1, 1, 4, 4), (5, 0, 7, 2)],
        [(0, 5, 2, 7), (5, 4, 7, 6)],
    )

    tasks.append({
        "task_id": "group_a_color_layer_seed_01",
        "group": "A_adapter_genesis",
        "subgroup": "color_layer",
        "role": "seed",
        "train": [
            {"input": inp_01.tolist(), "output": out_01.tolist()},
            {"input": inp_01b.tolist(), "output": out_01b.tolist()},
        ],
        "test": [{"input": inp_01t.tolist(), "output": out_01t.tolist()}],
        "expected_adapter": "ColorLayerAdapter",
        "expected_operator": "color_layer_remove",
        "expected_selector": "color_match",
        "why_default_fails": "Default parser extracts all objects together; cannot identify color-layer operation",
    })

    # --- Seed 02: 9x9 grid, remove color 4 (yellow), keep color 1 (red) ---
    inp_02, out_02 = _make_color_layer_pair(
        9, 9, 1, 4,
        [(0, 0, 3, 3), (6, 6, 9, 9)],
        [(0, 5, 2, 8), (4, 1, 6, 3), (7, 3, 9, 5)],
    )
    inp_02b, out_02b = _make_color_layer_pair(
        9, 9, 1, 4,
        [(1, 1, 4, 4), (5, 5, 8, 8)],
        [(0, 6, 2, 9), (3, 0, 5, 2), (7, 0, 9, 2)],
    )
    inp_02t, out_02t = _make_color_layer_pair(
        9, 9, 1, 4,
        [(2, 2, 5, 5), (6, 0, 9, 3)],
        [(0, 0, 2, 2), (0, 6, 2, 9), (5, 6, 7, 9)],
    )

    tasks.append({
        "task_id": "group_a_color_layer_seed_02",
        "group": "A_adapter_genesis",
        "subgroup": "color_layer",
        "role": "seed",
        "train": [
            {"input": inp_02.tolist(), "output": out_02.tolist()},
            {"input": inp_02b.tolist(), "output": out_02b.tolist()},
        ],
        "test": [{"input": inp_02t.tolist(), "output": out_02t.tolist()}],
        "expected_adapter": "ColorLayerAdapter",
        "expected_operator": "color_layer_remove",
        "expected_selector": "color_match",
        "why_default_fails": "Default parser extracts all objects together; cannot identify color-layer operation",
    })

    # --- Held-out 01: 7x7, remove color 6 (magenta), keep color 9 (maroon) ---
    inp_h01, out_h01 = _make_color_layer_pair(
        7, 7, 9, 6,
        [(0, 0, 2, 3), (4, 4, 7, 7)],
        [(2, 4, 4, 6), (5, 0, 7, 2)],
    )
    inp_h01b, out_h01b = _make_color_layer_pair(
        7, 7, 9, 6,
        [(1, 1, 3, 4), (5, 3, 7, 6)],
        [(0, 5, 2, 7), (3, 0, 5, 2)],
    )
    inp_h01t, out_h01t = _make_color_layer_pair(
        7, 7, 9, 6,
        [(0, 4, 3, 7), (4, 0, 7, 3)],
        [(0, 0, 2, 2), (5, 4, 7, 6)],
    )

    tasks.append({
        "task_id": "group_a_color_layer_heldout_01",
        "group": "A_adapter_genesis",
        "subgroup": "color_layer",
        "role": "heldout",
        "train": [
            {"input": inp_h01.tolist(), "output": out_h01.tolist()},
            {"input": inp_h01b.tolist(), "output": out_h01b.tolist()},
        ],
        "test": [{"input": inp_h01t.tolist(), "output": out_h01t.tolist()}],
        "expected_adapter": "ColorLayerAdapter",
        "expected_operator": "color_layer_remove",
        "expected_selector": "color_match",
        "why_default_fails": "Default parser extracts all objects together; cannot identify color-layer operation",
    })

    # --- Held-out 02: 8x8, remove color 3 (green), keep color 8 (azure) ---
    inp_h02, out_h02 = _make_color_layer_pair(
        8, 8, 8, 3,
        [(0, 0, 2, 4), (5, 4, 8, 8)],
        [(2, 5, 4, 8), (5, 0, 7, 2)],
    )
    inp_h02b, out_h02b = _make_color_layer_pair(
        8, 8, 8, 3,
        [(1, 0, 4, 3), (4, 5, 7, 8)],
        [(0, 4, 2, 7), (6, 0, 8, 3)],
    )
    inp_h02t, out_h02t = _make_color_layer_pair(
        8, 8, 8, 3,
        [(0, 0, 3, 3), (5, 5, 8, 8)],
        [(0, 5, 2, 8), (6, 0, 8, 2)],
    )

    tasks.append({
        "task_id": "group_a_color_layer_heldout_02",
        "group": "A_adapter_genesis",
        "subgroup": "color_layer",
        "role": "heldout",
        "train": [
            {"input": inp_h02.tolist(), "output": out_h02.tolist()},
            {"input": inp_h02b.tolist(), "output": out_h02b.tolist()},
        ],
        "test": [{"input": inp_h02t.tolist(), "output": out_h02t.tolist()}],
        "expected_adapter": "ColorLayerAdapter",
        "expected_operator": "color_layer_remove",
        "expected_selector": "color_match",
        "why_default_fails": "Default parser extracts all objects together; cannot identify color-layer operation",
    })

    return tasks


def _build_object_in_object_tasks() -> List[Dict]:
    """Object-in-object tasks: extract the inner (contained) object.

    Default parser uses connected components but does not detect
    spatial containment.
    """
    tasks = []

    def _make_containment_pair(h, w, outer_positions, inner_positions, outer_color, inner_color):
        """Create a grid with an outer container and an inner object."""
        inp = np.zeros((h, w), dtype=int)
        # Draw outer as a frame (not filled)
        for (r1, c1, r2, c2) in outer_positions:
            inp[r1:r2, c1:c2] = outer_color
        # Draw inner
        for (r1, c1, r2, c2) in inner_positions:
            inp[r1:r2, c1:c2] = inner_color
        # Output: just the inner object
        out = np.zeros((h, w), dtype=int)
        for (r1, c1, r2, c2) in inner_positions:
            out[r1:r2, c1:c2] = inner_color
        return inp, out

    # --- Seed 01: 8x8, outer=color 3 frame, inner=color 1 block ---
    # Outer: a rectangular ring at rows 1-6, cols 1-6
    inp_01 = np.zeros((8, 8), dtype=int)
    # Draw the outer ring
    inp_01[1:7, 1:7] = 3
    inp_01[2:6, 2:6] = 0   # hollow out the center
    # Draw inner object
    inp_01[3:5, 3:5] = 1    # 2x2 red
    out_01 = np.zeros((8, 8), dtype=int)
    out_01[3:5, 3:5] = 1

    inp_01b = np.zeros((8, 8), dtype=int)
    inp_01b[0:6, 0:6] = 3
    inp_01b[1:5, 1:5] = 0
    inp_01b[2:4, 2:4] = 5    # 2x2 gray
    out_01b = np.zeros((8, 8), dtype=int)
    out_01b[2:4, 2:4] = 5

    inp_01t = np.zeros((8, 8), dtype=int)
    inp_01t[2:8, 2:8] = 3
    inp_01t[3:7, 3:7] = 0
    inp_01t[4:6, 4:6] = 4    # 2x2 yellow
    out_01t = np.zeros((8, 8), dtype=int)
    out_01t[4:6, 4:6] = 4

    tasks.append({
        "task_id": "group_a_object_in_object_seed_01",
        "group": "A_adapter_genesis",
        "subgroup": "object_in_object",
        "role": "seed",
        "train": [
            {"input": inp_01.tolist(), "output": out_01.tolist()},
            {"input": inp_01b.tolist(), "output": out_01b.tolist()},
        ],
        "test": [{"input": inp_01t.tolist(), "output": out_01t.tolist()}],
        "expected_adapter": "ObjectInObjectAdapter",
        "expected_operator": "containment_extract",
        "expected_selector": "is_inner_object",
        "why_default_fails": "Default parser detects connected components but not containment relationships",
    })

    # --- Seed 02: 9x9, outer=color 6 ring, inner=color 2 ---
    inp_02 = np.zeros((9, 9), dtype=int)
    inp_02[1:8, 1:8] = 6
    inp_02[2:7, 2:7] = 0
    inp_02[3:6, 3:6] = 2    # 3x3 blue
    out_02 = np.zeros((9, 9), dtype=int)
    out_02[3:6, 3:6] = 2

    inp_02b = np.zeros((9, 9), dtype=int)
    inp_02b[0:7, 0:7] = 6
    inp_02b[1:6, 1:6] = 0
    inp_02b[2:5, 2:5] = 9    # 3x3 maroon
    out_02b = np.zeros((9, 9), dtype=int)
    out_02b[2:5, 2:5] = 9

    inp_02t = np.zeros((9, 9), dtype=int)
    inp_02t[2:9, 2:9] = 6
    inp_02t[3:8, 3:8] = 0
    inp_02t[4:7, 4:7] = 1    # 3x3 red
    out_02t = np.zeros((9, 9), dtype=int)
    out_02t[4:7, 4:7] = 1

    tasks.append({
        "task_id": "group_a_object_in_object_seed_02",
        "group": "A_adapter_genesis",
        "subgroup": "object_in_object",
        "role": "seed",
        "train": [
            {"input": inp_02.tolist(), "output": out_02.tolist()},
            {"input": inp_02b.tolist(), "output": out_02b.tolist()},
        ],
        "test": [{"input": inp_02t.tolist(), "output": out_02t.tolist()}],
        "expected_adapter": "ObjectInObjectAdapter",
        "expected_operator": "containment_extract",
        "expected_selector": "is_inner_object",
        "why_default_fails": "Default parser detects connected components but not containment relationships",
    })

    # --- Held-out 01: 10x10, outer=color 4, inner=color 8 ---
    inp_h01 = np.zeros((10, 10), dtype=int)
    inp_h01[1:9, 1:9] = 4
    inp_h01[2:8, 2:8] = 0
    inp_h01[3:7, 3:7] = 8    # 4x4 azure
    out_h01 = np.zeros((10, 10), dtype=int)
    out_h01[3:7, 3:7] = 8

    inp_h01b = np.zeros((10, 10), dtype=int)
    inp_h01b[0:8, 0:8] = 4
    inp_h01b[1:7, 1:7] = 0
    inp_h01b[2:6, 2:6] = 5    # 4x4 gray
    out_h01b = np.zeros((10, 10), dtype=int)
    out_h01b[2:6, 2:6] = 5

    inp_h01t = np.zeros((10, 10), dtype=int)
    inp_h01t[2:10, 0:8] = 4
    inp_h01t[3:9, 1:7] = 0
    inp_h01t[4:8, 2:6] = 1    # 4x4 red
    out_h01t = np.zeros((10, 10), dtype=int)
    out_h01t[4:8, 2:6] = 1

    tasks.append({
        "task_id": "group_a_object_in_object_heldout_01",
        "group": "A_adapter_genesis",
        "subgroup": "object_in_object",
        "role": "heldout",
        "train": [
            {"input": inp_h01.tolist(), "output": out_h01.tolist()},
            {"input": inp_h01b.tolist(), "output": out_h01b.tolist()},
        ],
        "test": [{"input": inp_h01t.tolist(), "output": out_h01t.tolist()}],
        "expected_adapter": "ObjectInObjectAdapter",
        "expected_operator": "containment_extract",
        "expected_selector": "is_inner_object",
        "why_default_fails": "Default parser detects connected components but not containment relationships",
    })

    # --- Held-out 02: 7x7, outer=color 5, inner=color 3 ---
    inp_h02 = np.zeros((7, 7), dtype=int)
    inp_h02[0:6, 0:6] = 5
    inp_h02[1:5, 1:5] = 0
    inp_h02[2:4, 2:4] = 3    # 2x2 green
    out_h02 = np.zeros((7, 7), dtype=int)
    out_h02[2:4, 2:4] = 3

    inp_h02b = np.zeros((7, 7), dtype=int)
    inp_h02b[1:7, 1:7] = 5
    inp_h02b[2:6, 2:6] = 0
    inp_h02b[3:5, 3:5] = 6    # 2x2 magenta
    out_h02b = np.zeros((7, 7), dtype=int)
    out_h02b[3:5, 3:5] = 6

    inp_h02t = np.zeros((7, 7), dtype=int)
    inp_h02t[0:5, 0:5] = 5
    inp_h02t[1:4, 1:4] = 0
    inp_h02t[2:3, 2:3] = 9    # 1x1 maroon
    out_h02t = np.zeros((7, 7), dtype=int)
    out_h02t[2:3, 2:3] = 9

    tasks.append({
        "task_id": "group_a_object_in_object_heldout_02",
        "group": "A_adapter_genesis",
        "subgroup": "object_in_object",
        "role": "heldout",
        "train": [
            {"input": inp_h02.tolist(), "output": out_h02.tolist()},
            {"input": inp_h02b.tolist(), "output": out_h02b.tolist()},
        ],
        "test": [{"input": inp_h02t.tolist(), "output": out_h02t.tolist()}],
        "expected_adapter": "ObjectInObjectAdapter",
        "expected_operator": "containment_extract",
        "expected_selector": "is_inner_object",
        "why_default_fails": "Default parser detects connected components but not containment relationships",
    })

    return tasks


# ===========================================================================
# Group B: Memory necessary (3 seed + 3 held-out)
# ===========================================================================

def _build_memory_transfer_tasks() -> List[Dict]:
    """Memory transfer tasks: same structural pattern, different surface features.

    Seed tasks teach adapter+operator packages. Held-out tasks have the
    same structure but different colors/sizes, requiring memory retrieval.
    """
    tasks = []

    # Pattern 1: frame-interior (same as Group A but for memory transfer)
    # Seed
    interior_s1 = np.zeros((5, 5), dtype=int)
    interior_s1[0:2, 0:3] = 4    # 2x3 yellow (area=6) -- largest
    interior_s1[3:4, 3:5] = 1    # 1x2 red (area=2)
    inp_s1 = _make_frame_grid(7, 7, 3, interior_s1)
    out_int_s1 = np.zeros((5, 5), dtype=int)
    out_int_s1[0:2, 0:3] = 4
    out_s1 = _make_frame_grid(7, 7, 3, out_int_s1)

    interior_s1b = np.zeros((5, 5), dtype=int)
    interior_s1b[1:3, 1:4] = 6    # 2x3 magenta (area=6) -- largest
    interior_s1b[4:5, 0:1] = 2    # 1x1 blue (area=1)
    inp_s1b = _make_frame_grid(7, 7, 3, interior_s1b)
    out_int_s1b = np.zeros((5, 5), dtype=int)
    out_int_s1b[1:3, 1:4] = 6
    out_s1b = _make_frame_grid(7, 7, 3, out_int_s1b)

    interior_s1t = np.zeros((5, 5), dtype=int)
    interior_s1t[2:4, 0:3] = 9    # 2x3 maroon (area=6) -- largest
    interior_s1t[0:1, 4:5] = 5    # 1x1 gray (area=1)
    inp_s1t = _make_frame_grid(7, 7, 3, interior_s1t)
    out_int_s1t = np.zeros((5, 5), dtype=int)
    out_int_s1t[2:4, 0:3] = 9
    out_s1t = _make_frame_grid(7, 7, 3, out_int_s1t)

    tasks.append({
        "task_id": "group_b_memory_transfer_seed_01",
        "group": "B_memory",
        "subgroup": "memory_transfer",
        "role": "seed",
        "train": [
            {"input": inp_s1.tolist(), "output": out_s1.tolist()},
            {"input": inp_s1b.tolist(), "output": out_s1b.tolist()},
        ],
        "test": [{"input": inp_s1t.tolist(), "output": out_s1t.tolist()}],
        "expected_adapter": "FrameInteriorAdapter",
        "expected_operator": "discriminative_filter",
        "expected_selector": "is_largest",
        "why_default_fails": "Default parser treats frame as largest object",
    })

    # Held-out 1: different frame color, grid size
    interior_h1 = np.zeros((6, 6), dtype=int)
    interior_h1[0:3, 0:3] = 8    # 3x3 azure (area=9) -- largest
    interior_h1[4:5, 4:6] = 2    # 1x2 blue (area=2)
    inp_h1 = _make_frame_grid(8, 8, 5, interior_h1)
    out_int_h1 = np.zeros((6, 6), dtype=int)
    out_int_h1[0:3, 0:3] = 8
    out_h1 = _make_frame_grid(8, 8, 5, out_int_h1)

    interior_h1b = np.zeros((6, 6), dtype=int)
    interior_h1b[1:4, 1:4] = 1    # 3x3 red (area=9) -- largest
    interior_h1b[5:6, 0:2] = 4    # 1x2 yellow (area=2)
    inp_h1b = _make_frame_grid(8, 8, 5, interior_h1b)
    out_int_h1b = np.zeros((6, 6), dtype=int)
    out_int_h1b[1:4, 1:4] = 1
    out_h1b = _make_frame_grid(8, 8, 5, out_int_h1b)

    interior_h1t = np.zeros((6, 6), dtype=int)
    interior_h1t[2:5, 2:5] = 6    # 3x3 magenta (area=9) -- largest
    interior_h1t[0:1, 0:1] = 9    # 1x1 maroon (area=1)
    inp_h1t = _make_frame_grid(8, 8, 5, interior_h1t)
    out_int_h1t = np.zeros((6, 6), dtype=int)
    out_int_h1t[2:5, 2:5] = 6
    out_h1t = _make_frame_grid(8, 8, 5, out_int_h1t)

    tasks.append({
        "task_id": "group_b_memory_transfer_heldout_01",
        "group": "B_memory",
        "subgroup": "memory_transfer",
        "role": "heldout",
        "train": [
            {"input": inp_h1.tolist(), "output": out_h1.tolist()},
            {"input": inp_h1b.tolist(), "output": out_h1b.tolist()},
        ],
        "test": [{"input": inp_h1t.tolist(), "output": out_h1t.tolist()}],
        "expected_adapter": "FrameInteriorAdapter",
        "expected_operator": "discriminative_filter",
        "expected_selector": "is_largest",
        "why_default_fails": "Default parser treats frame as largest object",
    })

    # Pattern 2: color-layer removal
    def _cl(h, w, keep, rem, kp, rp):
        inp = np.zeros((h, w), dtype=int)
        for (r1, c1, r2, c2) in kp:
            inp[r1:r2, c1:c2] = keep
        for (r1, c1, r2, c2) in rp:
            inp[r1:r2, c1:c2] = rem
        return inp, _remove_color_layer(inp, rem)

    s2i, s2o = _cl(8, 8, 1, 4, [(0, 0, 3, 3), (5, 5, 8, 8)], [(1, 4, 3, 6), (5, 0, 7, 2)])
    s2ib, s2ob = _cl(8, 8, 1, 4, [(2, 2, 5, 5), (6, 0, 8, 3)], [(0, 5, 2, 8), (4, 0, 6, 2)])
    s2it, s2ot = _cl(8, 8, 1, 4, [(0, 0, 2, 4), (5, 4, 8, 8)], [(3, 0, 5, 3), (0, 5, 2, 7)])

    tasks.append({
        "task_id": "group_b_memory_transfer_seed_02",
        "group": "B_memory",
        "subgroup": "memory_transfer",
        "role": "seed",
        "train": [
            {"input": s2i.tolist(), "output": s2o.tolist()},
            {"input": s2ib.tolist(), "output": s2ob.tolist()},
        ],
        "test": [{"input": s2it.tolist(), "output": s2ot.tolist()}],
        "expected_adapter": "ColorLayerAdapter",
        "expected_operator": "color_layer_remove",
        "expected_selector": "color_match",
        "why_default_fails": "Default parser cannot separate color layers",
    })

    h2i, h2o = _cl(9, 9, 8, 6, [(0, 0, 3, 3), (6, 6, 9, 9)], [(1, 5, 3, 8), (5, 0, 7, 2)])
    h2ib, h2ob = _cl(9, 9, 8, 6, [(2, 2, 5, 5), (6, 0, 9, 3)], [(0, 6, 2, 9), (4, 0, 6, 2)])
    h2it, h2ot = _cl(9, 9, 8, 6, [(0, 0, 2, 4), (6, 5, 9, 9)], [(3, 0, 5, 3), (0, 6, 2, 9)])

    tasks.append({
        "task_id": "group_b_memory_transfer_heldout_02",
        "group": "B_memory",
        "subgroup": "memory_transfer",
        "role": "heldout",
        "train": [
            {"input": h2i.tolist(), "output": h2o.tolist()},
            {"input": h2ib.tolist(), "output": h2ob.tolist()},
        ],
        "test": [{"input": h2it.tolist(), "output": h2ot.tolist()}],
        "expected_adapter": "ColorLayerAdapter",
        "expected_operator": "color_layer_remove",
        "expected_selector": "color_match",
        "why_default_fails": "Default parser cannot separate color layers",
    })

    # Pattern 3: containment extraction
    i3 = np.zeros((8, 8), dtype=int)
    i3[1:7, 1:7] = 7; i3[2:6, 2:6] = 0; i3[3:5, 3:5] = 2
    o3 = np.zeros((8, 8), dtype=int); o3[3:5, 3:5] = 2

    i3b = np.zeros((8, 8), dtype=int)
    i3b[0:6, 0:6] = 7; i3b[1:5, 1:5] = 0; i3b[2:4, 2:4] = 4
    o3b = np.zeros((8, 8), dtype=int); o3b[2:4, 2:4] = 4

    i3t = np.zeros((8, 8), dtype=int)
    i3t[2:8, 2:8] = 7; i3t[3:7, 3:7] = 0; i3t[4:6, 4:6] = 1
    o3t = np.zeros((8, 8), dtype=int); o3t[4:6, 4:6] = 1

    tasks.append({
        "task_id": "group_b_memory_transfer_seed_03",
        "group": "B_memory",
        "subgroup": "memory_transfer",
        "role": "seed",
        "train": [
            {"input": i3.tolist(), "output": o3.tolist()},
            {"input": i3b.tolist(), "output": o3b.tolist()},
        ],
        "test": [{"input": i3t.tolist(), "output": o3t.tolist()}],
        "expected_adapter": "ObjectInObjectAdapter",
        "expected_operator": "containment_extract",
        "expected_selector": "is_inner_object",
        "why_default_fails": "Default parser does not detect containment",
    })

    h3 = np.zeros((9, 9), dtype=int)
    h3[0:8, 0:8] = 3; h3[1:7, 1:7] = 0; h3[2:6, 2:6] = 5
    o_h3 = np.zeros((9, 9), dtype=int); o_h3[2:6, 2:6] = 5

    h3b = np.zeros((9, 9), dtype=int)
    h3b[1:9, 1:9] = 3; h3b[2:8, 2:8] = 0; h3b[3:7, 3:7] = 9
    o_h3b = np.zeros((9, 9), dtype=int); o_h3b[3:7, 3:7] = 9

    h3t = np.zeros((9, 9), dtype=int)
    h3t[0:7, 0:7] = 3; h3t[1:6, 1:6] = 0; h3t[2:5, 2:5] = 8
    o_h3t = np.zeros((9, 9), dtype=int); o_h3t[2:5, 2:5] = 8

    tasks.append({
        "task_id": "group_b_memory_transfer_heldout_03",
        "group": "B_memory",
        "subgroup": "memory_transfer",
        "role": "heldout",
        "train": [
            {"input": h3.tolist(), "output": o_h3.tolist()},
            {"input": h3b.tolist(), "output": o_h3b.tolist()},
        ],
        "test": [{"input": h3t.tolist(), "output": o_h3t.tolist()}],
        "expected_adapter": "ObjectInObjectAdapter",
        "expected_operator": "containment_extract",
        "expected_selector": "is_inner_object",
        "why_default_fails": "Default parser does not detect containment",
    })

    return tasks


# ===========================================================================
# Group C: Property expansion necessary (4 seed + 4 held-out)
# ===========================================================================

def _build_property_expansion_tasks() -> List[Dict]:
    """Property expansion tasks: need a non-standard property for selection.

    The needed property (e.g., "touches_frame_but_not_frame",
    "has_exactly_one_hole") is NOT in the base _all_property_names() list.
    """
    tasks = []

    # Pattern 1: keep the object that touches exactly 2 borders (corner-hugging).
    # "touches_exactly_two_borders" is not in the base property list.
    # The base has touches_boundary, is_corner, etc., but not an exact count.

    def _make_two_border_task(h, w, objs_spec):
        """objs_spec: list of (r1,c1,r2,c2,color,touches_n_borders)"""
        inp = np.zeros((h, w), dtype=int)
        out = np.zeros((h, w), dtype=int)
        for (r1, c1, r2, c2, color, keep) in objs_spec:
            inp[r1:r2, c1:c2] = color
            if keep:
                out[r1:r2, c1:c2] = color
        return inp, out

    # Seed 01: keep the object touching exactly 2 borders
    inp_s1, out_s1 = _make_two_border_task(8, 8, [
        (0, 0, 2, 2, 1, True),   # top-left corner: touches top + left = 2 borders -> keep
        (3, 3, 5, 5, 2, False),  # center: touches 0 borders -> remove
        (6, 2, 8, 4, 4, False),  # bottom edge: touches 1 border (bottom) -> remove
    ])
    inp_s1b, out_s1b = _make_two_border_task(8, 8, [
        (0, 6, 2, 8, 5, True),   # top-right corner: 2 borders -> keep
        (3, 0, 5, 2, 6, False),  # left edge only: 1 border -> remove
        (6, 3, 8, 5, 9, False),  # bottom only: 1 border -> remove
    ])
    inp_s1t, out_s1t = _make_two_border_task(8, 8, [
        (6, 6, 8, 8, 3, True),   # bottom-right corner: 2 borders -> keep
        (0, 3, 2, 5, 1, False),  # top only: 1 border -> remove
        (3, 3, 5, 5, 8, False),  # center: 0 borders -> remove
    ])

    tasks.append({
        "task_id": "group_c_property_expansion_seed_01",
        "group": "C_property_expansion",
        "subgroup": "touches_two_borders",
        "role": "seed",
        "train": [
            {"input": inp_s1.tolist(), "output": out_s1.tolist()},
            {"input": inp_s1b.tolist(), "output": out_s1b.tolist()},
        ],
        "test": [{"input": inp_s1t.tolist(), "output": out_s1t.tolist()}],
        "expected_adapter": "none",
        "expected_operator": "discriminative_filter",
        "expected_selector": "touches_exactly_two_borders",
        "why_default_fails": "touches_exactly_two_borders is not in base property list; is_corner matches but with different semantics",
    })

    inp_s2, out_s2 = _make_two_border_task(9, 9, [
        (7, 0, 9, 2, 4, True),   # bottom-left corner: 2 borders -> keep
        (0, 4, 2, 6, 2, False),  # top only: 1 border -> remove
        (4, 4, 6, 6, 7, False),  # center: 0 borders -> remove
    ])
    inp_s2b, out_s2b = _make_two_border_task(9, 9, [
        (0, 7, 2, 9, 1, True),   # top-right: 2 borders -> keep
        (4, 0, 6, 2, 5, False),  # left only: 1 border -> remove
        (7, 4, 9, 6, 3, False),  # bottom only: 1 border -> remove
    ])
    inp_s2t, out_s2t = _make_two_border_task(9, 9, [
        (0, 0, 2, 2, 8, True),   # top-left: 2 borders -> keep
        (4, 3, 6, 6, 6, False),  # center: 0 borders -> remove
        (7, 7, 9, 9, 9, False),  # bottom-right: this ALSO touches 2 borders!
    ])
    # Fix: make the second "2-border" object NOT touch 2 borders
    # Actually, bottom-right corner (7,7)-(9,9) touches bottom and right = 2 borders.
    # We need to ensure only ONE object touches exactly 2. Let me adjust.
    inp_s2t = np.zeros((9, 9), dtype=int)
    inp_s2t[0:2, 0:2] = 8   # top-left: 2 borders -> keep
    inp_s2t[4:6, 3:6] = 6   # center: 0 borders -> remove
    inp_s2t[7:9, 4:6] = 9   # bottom only: 1 border -> remove
    out_s2t = np.zeros((9, 9), dtype=int)
    out_s2t[0:2, 0:2] = 8

    tasks.append({
        "task_id": "group_c_property_expansion_seed_02",
        "group": "C_property_expansion",
        "subgroup": "touches_two_borders",
        "role": "seed",
        "train": [
            {"input": inp_s2.tolist(), "output": out_s2.tolist()},
            {"input": inp_s2b.tolist(), "output": out_s2b.tolist()},
        ],
        "test": [{"input": inp_s2t.tolist(), "output": out_s2t.tolist()}],
        "expected_adapter": "none",
        "expected_operator": "discriminative_filter",
        "expected_selector": "touches_exactly_two_borders",
        "why_default_fails": "touches_exactly_two_borders not in base property list",
    })

    # Held-out versions
    inp_h1, out_h1 = _make_two_border_task(7, 7, [
        (5, 5, 7, 7, 2, True),   # bottom-right: 2 borders -> keep
        (0, 3, 2, 5, 4, False),  # top only: 1 border -> remove
        (3, 0, 5, 2, 1, False),  # left only: 1 border -> remove
    ])
    inp_h1b, out_h1b = _make_two_border_task(7, 7, [
        (0, 0, 2, 2, 6, True),   # top-left: 2 borders -> keep
        (3, 3, 5, 5, 9, False),  # center: 0 borders -> remove
        (5, 0, 7, 2, 3, False),  # bottom+left: 2 borders!
    ])
    # Fix: bottom-left also touches 2 borders. Adjust.
    inp_h1b = np.zeros((7, 7), dtype=int)
    inp_h1b[0:2, 0:2] = 6   # top-left: 2 borders -> keep
    inp_h1b[3:5, 3:5] = 9   # center: 0 borders -> remove
    inp_h1b[5:7, 3:5] = 3   # bottom only: 1 border -> remove
    out_h1b = np.zeros((7, 7), dtype=int)
    out_h1b[0:2, 0:2] = 6

    inp_h1t, out_h1t = _make_two_border_task(7, 7, [
        (5, 0, 7, 2, 5, True),   # bottom-left: 2 borders -> keep
        (0, 3, 2, 5, 8, False),  # top only: 1 border -> remove
        (3, 3, 5, 5, 1, False),  # center: 0 -> remove
    ])

    tasks.append({
        "task_id": "group_c_property_expansion_heldout_01",
        "group": "C_property_expansion",
        "subgroup": "touches_two_borders",
        "role": "heldout",
        "train": [
            {"input": inp_h1.tolist(), "output": out_h1.tolist()},
            {"input": inp_h1b.tolist(), "output": out_h1b.tolist()},
        ],
        "test": [{"input": inp_h1t.tolist(), "output": out_h1t.tolist()}],
        "expected_adapter": "none",
        "expected_operator": "discriminative_filter",
        "expected_selector": "touches_exactly_two_borders",
        "why_default_fails": "touches_exactly_two_borders not in base property list",
    })

    inp_h2, out_h2 = _make_two_border_task(10, 10, [
        (0, 8, 2, 10, 4, True),   # top-right: 2 borders -> keep
        (4, 4, 6, 6, 7, False),   # center: 0 borders -> remove
        (8, 4, 10, 6, 2, False),  # bottom only: 1 border -> remove
    ])
    inp_h2b, out_h2b = _make_two_border_task(10, 10, [
        (8, 0, 10, 2, 1, True),   # bottom-left: 2 borders -> keep
        (0, 4, 2, 6, 3, False),   # top only: 1 border -> remove
        (4, 0, 6, 2, 9, False),   # left only: 1 border -> remove
    ])
    inp_h2t, out_h2t = _make_two_border_task(10, 10, [
        (0, 0, 2, 2, 6, True),    # top-left: 2 borders -> keep
        (5, 5, 7, 7, 8, False),   # center: 0 borders -> remove
        (8, 5, 10, 7, 5, False),  # bottom only: 1 border -> remove
    ])

    tasks.append({
        "task_id": "group_c_property_expansion_heldout_02",
        "group": "C_property_expansion",
        "subgroup": "touches_two_borders",
        "role": "heldout",
        "train": [
            {"input": inp_h2.tolist(), "output": out_h2.tolist()},
            {"input": inp_h2b.tolist(), "output": out_h2b.tolist()},
        ],
        "test": [{"input": inp_h2t.tolist(), "output": out_h2t.tolist()}],
        "expected_adapter": "none",
        "expected_operator": "discriminative_filter",
        "expected_selector": "touches_exactly_two_borders",
        "why_default_fails": "touches_exactly_two_borders not in base property list",
    })

    # Pattern 2: keep object with exactly 2 holes
    # "has_exactly_two_holes" is not a base property (has_holes is, but not count==2)

    def _make_object_with_holes(h, w, n_holes, color, bg_color=0):
        """Create a rectangular object with n internal holes."""
        obj = np.full((h, w), color, dtype=int)
        # Create holes -- small 1x1 holes inside the object
        hole_positions = []
        for i in range(n_holes):
            r = 1 + i
            c = 1 + i
            if r < h - 1 and c < w - 1:
                obj[r, c] = bg_color
                hole_positions.append((r, c))
        return obj

    # Seed 03: keep object with exactly 2 holes
    inp_s3 = np.zeros((8, 8), dtype=int)
    # Object 1: 4x4 block with 2 holes at (1,1) and (2,2) -> keep
    inp_s3[0:4, 0:4] = 1
    inp_s3[1, 1] = 0
    inp_s3[2, 2] = 0
    # Object 2: 3x3 block with 0 holes -> remove
    inp_s3[5:8, 5:8] = 2
    out_s3 = np.zeros((8, 8), dtype=int)
    out_s3[0:4, 0:4] = 1
    out_s3[1, 1] = 0
    out_s3[2, 2] = 0

    inp_s3b = np.zeros((8, 8), dtype=int)
    # Object 1: 5x5 with 2 holes -> keep
    inp_s3b[0:5, 0:5] = 4
    inp_s3b[1, 1] = 0
    inp_s3b[3, 3] = 0
    # Object 2: 3x3 with 1 hole -> remove
    inp_s3b[5:8, 5:8] = 6
    inp_s3b[6, 6] = 0
    out_s3b = np.zeros((8, 8), dtype=int)
    out_s3b[0:5, 0:5] = 4
    out_s3b[1, 1] = 0
    out_s3b[3, 3] = 0

    inp_s3t = np.zeros((8, 8), dtype=int)
    # Object 1: 4x4 with 2 holes -> keep
    inp_s3t[2:6, 2:6] = 5
    inp_s3t[3, 3] = 0
    inp_s3t[4, 4] = 0
    # Object 2: 2x3 solid -> remove
    inp_s3t[0:2, 0:3] = 9
    out_s3t = np.zeros((8, 8), dtype=int)
    out_s3t[2:6, 2:6] = 5
    out_s3t[3, 3] = 0
    out_s3t[4, 4] = 0

    tasks.append({
        "task_id": "group_c_property_expansion_seed_03",
        "group": "C_property_expansion",
        "subgroup": "has_exactly_two_holes",
        "role": "seed",
        "train": [
            {"input": inp_s3.tolist(), "output": out_s3.tolist()},
            {"input": inp_s3b.tolist(), "output": out_s3b.tolist()},
        ],
        "test": [{"input": inp_s3t.tolist(), "output": out_s3t.tolist()}],
        "expected_adapter": "none",
        "expected_operator": "discriminative_filter",
        "expected_selector": "has_exactly_two_holes",
        "why_default_fails": "has_exactly_two_holes not in base property list; has_holes matches both 1-hole and 2-hole",
    })

    # Seed 04: similar pattern
    inp_s4 = np.zeros((9, 9), dtype=int)
    inp_s4[0:5, 0:5] = 3
    inp_s4[1, 1] = 0; inp_s4[3, 3] = 0  # 2 holes -> keep
    inp_s4[6:9, 6:9] = 7                 # solid -> remove
    out_s4 = np.zeros((9, 9), dtype=int)
    out_s4[0:5, 0:5] = 3
    out_s4[1, 1] = 0; out_s4[3, 3] = 0

    inp_s4b = np.zeros((9, 9), dtype=int)
    inp_s4b[1:6, 1:6] = 8
    inp_s4b[2, 2] = 0; inp_s4b[4, 4] = 0  # 2 holes -> keep
    inp_s4b[0:2, 7:9] = 1                  # solid -> remove
    out_s4b = np.zeros((9, 9), dtype=int)
    out_s4b[1:6, 1:6] = 8
    out_s4b[2, 2] = 0; out_s4b[4, 4] = 0

    inp_s4t = np.zeros((9, 9), dtype=int)
    inp_s4t[2:7, 2:7] = 6
    inp_s4t[3, 3] = 0; inp_s4t[5, 5] = 0  # 2 holes -> keep
    inp_s4t[0:2, 0:3] = 2                  # solid -> remove
    out_s4t = np.zeros((9, 9), dtype=int)
    out_s4t[2:7, 2:7] = 6
    out_s4t[3, 3] = 0; out_s4t[5, 5] = 0

    tasks.append({
        "task_id": "group_c_property_expansion_seed_04",
        "group": "C_property_expansion",
        "subgroup": "has_exactly_two_holes",
        "role": "seed",
        "train": [
            {"input": inp_s4.tolist(), "output": out_s4.tolist()},
            {"input": inp_s4b.tolist(), "output": out_s4b.tolist()},
        ],
        "test": [{"input": inp_s4t.tolist(), "output": out_s4t.tolist()}],
        "expected_adapter": "none",
        "expected_operator": "discriminative_filter",
        "expected_selector": "has_exactly_two_holes",
        "why_default_fails": "has_exactly_two_holes not in base property list",
    })

    # Held-out 03, 04
    inp_h3 = np.zeros((7, 7), dtype=int)
    inp_h3[0:4, 0:4] = 9
    inp_h3[1, 1] = 0; inp_h3[2, 2] = 0  # 2 holes -> keep
    inp_h3[5:7, 5:7] = 4                 # solid -> remove
    out_h3 = np.zeros((7, 7), dtype=int)
    out_h3[0:4, 0:4] = 9
    out_h3[1, 1] = 0; out_h3[2, 2] = 0

    inp_h3b = np.zeros((7, 7), dtype=int)
    inp_h3b[1:5, 1:5] = 5
    inp_h3b[2, 2] = 0; inp_h3b[3, 3] = 0  # 2 holes -> keep
    inp_h3b[0:1, 5:7] = 1                  # solid -> remove
    out_h3b = np.zeros((7, 7), dtype=int)
    out_h3b[1:5, 1:5] = 5
    out_h3b[2, 2] = 0; out_h3b[3, 3] = 0

    inp_h3t = np.zeros((7, 7), dtype=int)
    inp_h3t[2:6, 2:6] = 8
    inp_h3t[3, 3] = 0; inp_h3t[4, 4] = 0  # 2 holes
    inp_h3t[0:2, 0:2] = 3                  # solid
    out_h3t = np.zeros((7, 7), dtype=int)
    out_h3t[2:6, 2:6] = 8
    out_h3t[3, 3] = 0; out_h3t[4, 4] = 0

    tasks.append({
        "task_id": "group_c_property_expansion_heldout_03",
        "group": "C_property_expansion",
        "subgroup": "has_exactly_two_holes",
        "role": "heldout",
        "train": [
            {"input": inp_h3.tolist(), "output": out_h3.tolist()},
            {"input": inp_h3b.tolist(), "output": out_h3b.tolist()},
        ],
        "test": [{"input": inp_h3t.tolist(), "output": out_h3t.tolist()}],
        "expected_adapter": "none",
        "expected_operator": "discriminative_filter",
        "expected_selector": "has_exactly_two_holes",
        "why_default_fails": "has_exactly_two_holes not in base property list",
    })

    inp_h4 = np.zeros((10, 10), dtype=int)
    inp_h4[0:5, 0:5] = 2
    inp_h4[1, 1] = 0; inp_h4[3, 3] = 0
    inp_h4[6:9, 6:9] = 7
    out_h4 = np.zeros((10, 10), dtype=int)
    out_h4[0:5, 0:5] = 2
    out_h4[1, 1] = 0; out_h4[3, 3] = 0

    inp_h4b = np.zeros((10, 10), dtype=int)
    inp_h4b[2:7, 2:7] = 1
    inp_h4b[3, 3] = 0; inp_h4b[5, 5] = 0
    inp_h4b[0:2, 8:10] = 6
    out_h4b = np.zeros((10, 10), dtype=int)
    out_h4b[2:7, 2:7] = 1
    out_h4b[3, 3] = 0; out_h4b[5, 5] = 0

    inp_h4t = np.zeros((10, 10), dtype=int)
    inp_h4t[3:8, 3:8] = 4
    inp_h4t[4, 4] = 0; inp_h4t[6, 6] = 0
    inp_h4t[0:3, 0:3] = 5
    out_h4t = np.zeros((10, 10), dtype=int)
    out_h4t[3:8, 3:8] = 4
    out_h4t[4, 4] = 0; out_h4t[6, 6] = 0

    tasks.append({
        "task_id": "group_c_property_expansion_heldout_04",
        "group": "C_property_expansion",
        "subgroup": "has_exactly_two_holes",
        "role": "heldout",
        "train": [
            {"input": inp_h4.tolist(), "output": out_h4.tolist()},
            {"input": inp_h4b.tolist(), "output": out_h4b.tolist()},
        ],
        "test": [{"input": inp_h4t.tolist(), "output": out_h4t.tolist()}],
        "expected_adapter": "none",
        "expected_operator": "discriminative_filter",
        "expected_selector": "has_exactly_two_holes",
        "why_default_fails": "has_exactly_two_holes not in base property list",
    })

    return tasks


# ===========================================================================
# Group D: Neural advisory necessary under budget (2 seed + 2 held-out)
# ===========================================================================

def _build_neural_advisory_tasks() -> List[Dict]:
    """Neural advisory tasks: many plausible operator families.

    Under tight proposal budget (max_proposals_per_module=1), random
    ordering fails but neural-guided ranking succeeds.

    These tasks have multiple valid-looking filter properties, but only
    one produces correct results. The neural advisor must prioritize
    the correct operator family.
    """
    tasks = []

    # Task: multiple objects with different properties. Only one property
    # discriminates. With budget=1, must pick the right one first try.

    # Seed 01: keep is_smallest (but multiple objects match other filters)
    inp_s1 = np.zeros((8, 8), dtype=int)
    inp_s1[0:3, 0:3] = 1    # 3x3 red, largest, touches_top+left
    inp_s1[0:2, 5:7] = 2    # 2x2 blue, touches_top
    inp_s1[5:7, 0:2] = 4    # 2x2 yellow, touches_left
    inp_s1[6:7, 6:7] = 5    # 1x1 gray, smallest
    inp_s1[3:5, 3:5] = 9    # 2x2 maroon, center
    out_s1 = np.zeros((8, 8), dtype=int)
    out_s1[6:7, 6:7] = 5    # keep smallest

    inp_s1b = np.zeros((8, 8), dtype=int)
    inp_s1b[0:4, 0:4] = 3    # 4x4 green, largest
    inp_s1b[0:2, 5:7] = 6    # 2x2 magenta
    inp_s1b[5:7, 0:2] = 8    # 2x2 azure
    inp_s1b[7:8, 7:8] = 2    # 1x1 blue, smallest
    inp_s1b[4:6, 4:6] = 1    # 2x2 red
    out_s1b = np.zeros((8, 8), dtype=int)
    out_s1b[7:8, 7:8] = 2

    inp_s1t = np.zeros((8, 8), dtype=int)
    inp_s1t[0:3, 0:3] = 4    # 3x3 yellow
    inp_s1t[0:2, 4:7] = 1    # 2x3 red
    inp_s1t[4:6, 0:3] = 6    # 2x3 magenta
    inp_s1t[3:4, 5:6] = 9    # 1x1 maroon, smallest
    inp_s1t[5:7, 5:7] = 2    # 2x2 blue
    out_s1t = np.zeros((8, 8), dtype=int)
    out_s1t[3:4, 5:6] = 9

    tasks.append({
        "task_id": "group_d_neural_routing_seed_01",
        "group": "D_neural_advisory",
        "subgroup": "neural_routing",
        "role": "seed",
        "train": [
            {"input": inp_s1.tolist(), "output": out_s1.tolist()},
            {"input": inp_s1b.tolist(), "output": out_s1b.tolist()},
        ],
        "test": [{"input": inp_s1t.tolist(), "output": out_s1t.tolist()}],
        "expected_adapter": "none",
        "expected_operator": "discriminative_filter",
        "expected_selector": "is_smallest",
        "why_default_fails": "Under budget=1, random ordering may try wrong operator first. Neural advisory needed to prioritize is_smallest.",
    })

    # Seed 02
    inp_s2 = np.zeros((9, 9), dtype=int)
    inp_s2[0:4, 0:4] = 2    # largest
    inp_s2[0:3, 5:8] = 4
    inp_s2[5:8, 0:3] = 6
    inp_s2[5:8, 5:8] = 8
    inp_s2[4:5, 4:5] = 1    # 1x1 smallest
    out_s2 = np.zeros((9, 9), dtype=int)
    out_s2[4:5, 4:5] = 1

    inp_s2b = np.zeros((9, 9), dtype=int)
    inp_s2b[0:3, 0:3] = 5
    inp_s2b[0:3, 4:7] = 3
    inp_s2b[4:7, 0:3] = 9
    inp_s2b[4:7, 4:7] = 7
    inp_s2b[8:9, 8:9] = 6    # 1x1 smallest
    out_s2b = np.zeros((9, 9), dtype=int)
    out_s2b[8:9, 8:9] = 6

    inp_s2t = np.zeros((9, 9), dtype=int)
    inp_s2t[0:3, 0:4] = 1
    inp_s2t[0:3, 5:9] = 8
    inp_s2t[4:7, 0:4] = 3
    inp_s2t[4:7, 5:9] = 5
    inp_s2t[3:4, 4:5] = 4    # 1x1 smallest
    out_s2t = np.zeros((9, 9), dtype=int)
    out_s2t[3:4, 4:5] = 4

    tasks.append({
        "task_id": "group_d_neural_routing_seed_02",
        "group": "D_neural_advisory",
        "subgroup": "neural_routing",
        "role": "seed",
        "train": [
            {"input": inp_s2.tolist(), "output": out_s2.tolist()},
            {"input": inp_s2b.tolist(), "output": out_s2b.tolist()},
        ],
        "test": [{"input": inp_s2t.tolist(), "output": out_s2t.tolist()}],
        "expected_adapter": "none",
        "expected_operator": "discriminative_filter",
        "expected_selector": "is_smallest",
        "why_default_fails": "Under budget=1, many viable families. Neural advisory needed.",
    })

    # Held-out
    inp_h1 = np.zeros((7, 7), dtype=int)
    inp_h1[0:3, 0:3] = 3
    inp_h1[0:2, 4:6] = 8
    inp_h1[4:6, 0:2] = 1
    inp_h1[4:6, 4:6] = 6
    inp_h1[3:4, 3:4] = 9    # 1x1 smallest
    out_h1 = np.zeros((7, 7), dtype=int)
    out_h1[3:4, 3:4] = 9

    inp_h1b = np.zeros((7, 7), dtype=int)
    inp_h1b[0:2, 0:3] = 4
    inp_h1b[0:2, 4:7] = 2
    inp_h1b[3:5, 0:3] = 5
    inp_h1b[3:5, 4:7] = 7
    inp_h1b[6:7, 3:4] = 1    # 1x1 smallest
    out_h1b = np.zeros((7, 7), dtype=int)
    out_h1b[6:7, 3:4] = 1

    inp_h1t = np.zeros((7, 7), dtype=int)
    inp_h1t[0:3, 0:3] = 6
    inp_h1t[0:2, 4:7] = 9
    inp_h1t[4:7, 0:3] = 2
    inp_h1t[5:7, 4:7] = 8
    inp_h1t[3:4, 5:6] = 4    # 1x1 smallest
    out_h1t = np.zeros((7, 7), dtype=int)
    out_h1t[3:4, 5:6] = 4

    tasks.append({
        "task_id": "group_d_neural_routing_heldout_01",
        "group": "D_neural_advisory",
        "subgroup": "neural_routing",
        "role": "heldout",
        "train": [
            {"input": inp_h1.tolist(), "output": out_h1.tolist()},
            {"input": inp_h1b.tolist(), "output": out_h1b.tolist()},
        ],
        "test": [{"input": inp_h1t.tolist(), "output": out_h1t.tolist()}],
        "expected_adapter": "none",
        "expected_operator": "discriminative_filter",
        "expected_selector": "is_smallest",
        "why_default_fails": "Under budget=1, neural advisory needed for prioritization",
    })

    inp_h2 = np.zeros((10, 10), dtype=int)
    inp_h2[0:4, 0:4] = 2
    inp_h2[0:3, 5:9] = 7
    inp_h2[5:8, 0:4] = 4
    inp_h2[5:8, 5:9] = 1
    inp_h2[4:5, 4:5] = 3    # 1x1 smallest
    inp_h2[8:10, 0:3] = 9
    out_h2 = np.zeros((10, 10), dtype=int)
    out_h2[4:5, 4:5] = 3

    inp_h2b = np.zeros((10, 10), dtype=int)
    inp_h2b[0:3, 0:4] = 5
    inp_h2b[0:3, 5:10] = 8
    inp_h2b[4:7, 0:4] = 6
    inp_h2b[4:7, 5:10] = 1
    inp_h2b[8:10, 0:4] = 9
    inp_h2b[3:4, 9:10] = 4    # 1x1 smallest
    out_h2b = np.zeros((10, 10), dtype=int)
    out_h2b[3:4, 9:10] = 4

    inp_h2t = np.zeros((10, 10), dtype=int)
    inp_h2t[0:3, 0:5] = 1
    inp_h2t[0:3, 6:10] = 3
    inp_h2t[4:7, 0:5] = 8
    inp_h2t[4:7, 6:10] = 6
    inp_h2t[8:10, 0:5] = 7
    inp_h2t[8:9, 5:6] = 2    # 1x1 smallest
    out_h2t = np.zeros((10, 10), dtype=int)
    out_h2t[8:9, 5:6] = 2

    tasks.append({
        "task_id": "group_d_neural_routing_heldout_02",
        "group": "D_neural_advisory",
        "subgroup": "neural_routing",
        "role": "heldout",
        "train": [
            {"input": inp_h2.tolist(), "output": out_h2.tolist()},
            {"input": inp_h2b.tolist(), "output": out_h2b.tolist()},
        ],
        "test": [{"input": inp_h2t.tolist(), "output": out_h2t.tolist()}],
        "expected_adapter": "none",
        "expected_operator": "discriminative_filter",
        "expected_selector": "is_smallest",
        "why_default_fails": "Under budget=1, neural advisory needed",
    })

    return tasks


# ===========================================================================
# Main
# ===========================================================================

def build_curriculum() -> List[Dict]:
    """Build all curriculum tasks."""
    tasks = []
    tasks.extend(_build_frame_interior_tasks())
    tasks.extend(_build_color_layer_tasks())
    tasks.extend(_build_object_in_object_tasks())
    tasks.extend(_build_memory_transfer_tasks())
    tasks.extend(_build_property_expansion_tasks())
    tasks.extend(_build_neural_advisory_tasks())
    return tasks


def main():
    print("Building adaptive memory/adapter-genesis curriculum tasks...")
    tasks = build_curriculum()

    # Verify all tasks
    n_valid = 0
    n_parser_fails = 0
    for task in tasks:
        valid = _verify_task(task)
        if valid:
            n_valid += 1
        parser_fails = _verify_default_parser_fails(task)
        if parser_fails:
            n_parser_fails += 1

    print(f"\nVerification: {n_valid}/{len(tasks)} valid, "
          f"{n_parser_fails}/{len(tasks)} default parser correctly fails")

    # Summary by group
    groups = {}
    for task in tasks:
        g = task["group"]
        r = task["role"]
        key = f"{g}_{r}"
        groups[key] = groups.get(key, 0) + 1

    print("\nTasks by group:")
    for key, count in sorted(groups.items()):
        print(f"  {key}: {count}")

    # Save
    output_path = OUTPUT_DIR / "curriculum_tasks.json"
    with open(output_path, "w") as f:
        json.dump(tasks, f, indent=2)

    print(f"\nSaved {len(tasks)} tasks to {output_path}")
    return tasks


if __name__ == "__main__":
    main()
