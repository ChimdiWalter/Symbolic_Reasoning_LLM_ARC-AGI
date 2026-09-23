"""Synthetic hidden-rule benchmark generation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

import numpy as np

from .operators import apply_program
from .schemas import Program, ProgramStep, ReasoningTask, TaskExample, TaskSuite
from .utils import read_json, stable_hash, write_json


DEFAULT_FAMILIES = [
    "reflection",
    "rotation",
    "translation",
    "recolor_predicate",
    "component_count",
    "containment",
    "adjacency",
    "symmetry",
    "topology",
    "spurious",
    "compositional",
]

H2_NONCOMMUTING_FAMILY = "h2_noncommuting_composition_probe"
H2_REFLECT_RECOLOR_FAMILY = "h2_symmetric_reflect_recolor_probe"
H2_ROTATE_RECOLOR_FAMILY = "h2_symmetric_rotate_recolor_probe"
H2_REFLECT_SELECT_BORDER_FAMILY = "h2_reflect_select_border_probe"
H2_REFLECT_MARK_CONTAINED_FAMILY = "h2_reflect_mark_contained_probe"
H2_COPY_CORNER_FAMILY = "h2_copy_corner_probe"
H2_LARGEST_VS_BORDER_FAMILY = "h2_largest_vs_border_probe"
H2_AMBIGUOUS_FAMILIES = {
    H2_NONCOMMUTING_FAMILY,
    H2_REFLECT_RECOLOR_FAMILY,
    H2_ROTATE_RECOLOR_FAMILY,
    H2_REFLECT_SELECT_BORDER_FAMILY,
    H2_REFLECT_MARK_CONTAINED_FAMILY,
    H2_COPY_CORNER_FAMILY,
    H2_LARGEST_VS_BORDER_FAMILY,
}

PAPER_COMPOSITION_REFLECT_COUNT_FAMILY = "paper_composition_reflect_count"
PAPER_COMPOSITION_ADJACENT_REFLECT_FAMILY = "paper_composition_adjacent_reflect"
PAPER_COPY_CORNER_DISTRACTOR_FAMILY = "paper_copy_corner_distractor"
PAPER_TOPOLOGY_DISTRACTOR_FAMILY = "paper_topology_distractor"
PAPER_NUISANCE_MARKER_RECOLOR_FAMILY = "paper_nuisance_marker_recolor"
PAPER_CAUSAL_SPURIOUS_LARGEST_FAMILY = "paper_causal_spurious_largest"
PAPER_CONTAINMENT_REFLECT_MARK_FAMILY = "paper_containment_reflect_mark"
PAPER_SYMMETRY_REPAIR_CHALLENGE_FAMILY = "paper_symmetry_repair_challenge"
ARC_CROP_NONZERO_FAMILY = "arc_crop_nonzero_bbox"
ARC_CROP_LARGEST_FAMILY = "arc_crop_largest_component_bbox"
ARC_TRANSLATE_LARGEST_FAMILY = "arc_translate_largest_component"
ARC_SNAP_LARGEST_FAMILY = "arc_snap_largest_component"
ARC_EXPAND_CANVAS_FAMILY = "arc_expand_canvas"
ARC_EXPANDED_TRAINING_FAMILIES = {
    ARC_CROP_NONZERO_FAMILY,
    ARC_CROP_LARGEST_FAMILY,
    ARC_TRANSLATE_LARGEST_FAMILY,
    ARC_SNAP_LARGEST_FAMILY,
    ARC_EXPAND_CANVAS_FAMILY,
}
PAPER_BREADTH_FAMILIES = {
    PAPER_COMPOSITION_REFLECT_COUNT_FAMILY,
    PAPER_COMPOSITION_ADJACENT_REFLECT_FAMILY,
    PAPER_COPY_CORNER_DISTRACTOR_FAMILY,
    PAPER_TOPOLOGY_DISTRACTOR_FAMILY,
    PAPER_NUISANCE_MARKER_RECOLOR_FAMILY,
    PAPER_CAUSAL_SPURIOUS_LARGEST_FAMILY,
    PAPER_CONTAINMENT_REFLECT_MARK_FAMILY,
    PAPER_SYMMETRY_REPAIR_CHALLENGE_FAMILY,
}


def designed_ambiguity_level(family: str) -> str:
    if family in H2_AMBIGUOUS_FAMILIES or family == "spurious":
        return "high"
    if family in {
        PAPER_NUISANCE_MARKER_RECOLOR_FAMILY,
        PAPER_CAUSAL_SPURIOUS_LARGEST_FAMILY,
    }:
        return "high"
    if family in ARC_EXPANDED_TRAINING_FAMILIES:
        return "medium"
    if family in {"compositional", "symmetry", "topology"} or family in PAPER_BREADTH_FAMILIES:
        return "medium"
    return "low"


def _shape(grid_size: int | Sequence[int]) -> Tuple[int, int]:
    if isinstance(grid_size, int):
        return grid_size, grid_size
    return int(grid_size[0]), int(grid_size[1])


def _rng(seed: int) -> np.random.Generator:
    return np.random.default_rng(int(seed))


def _can_place(grid: np.ndarray, r: int, c: int, h: int, w: int, pad: int = 1) -> bool:
    rr0 = max(0, r - pad)
    cc0 = max(0, c - pad)
    rr1 = min(grid.shape[0], r + h + pad)
    cc1 = min(grid.shape[1], c + w + pad)
    return bool(np.all(grid[rr0:rr1, cc0:cc1] == 0))


def _place_rect(grid: np.ndarray, r: int, c: int, h: int, w: int, color: int) -> None:
    grid[r : r + h, c : c + w] = int(color)


def _add_random_distractors(
    grid: np.ndarray,
    rng: np.random.Generator,
    count: int,
    colors: Sequence[int],
    max_size: int = 2,
) -> None:
    h, w = grid.shape
    attempts = 0
    placed = 0
    while placed < count and attempts < count * 50 + 50:
        attempts += 1
        rh = int(rng.integers(1, max_size + 1))
        rw = int(rng.integers(1, max_size + 1))
        if rh >= h - 1 or rw >= w - 1:
            continue
        r = int(rng.integers(0, h - rh + 1))
        c = int(rng.integers(0, w - rw + 1))
        if not _can_place(grid, r, c, rh, rw, pad=0):
            continue
        _place_rect(grid, r, c, rh, rw, int(rng.choice(colors)))
        placed += 1


def random_scene(
    rng: np.random.Generator,
    grid_size: int | Sequence[int],
    object_count: int,
    colors: Sequence[int],
    margin: int = 0,
    distractors: int = 0,
) -> np.ndarray:
    h, w = _shape(grid_size)
    grid = np.zeros((h, w), dtype=int)
    attempts = 0
    placed = 0
    while placed < object_count and attempts < object_count * 80 + 80:
        attempts += 1
        max_h = max(1, min(3, h - 2 * margin))
        max_w = max(1, min(3, w - 2 * margin))
        rh = int(rng.integers(1, max_h + 1))
        rw = int(rng.integers(1, max_w + 1))
        r_low = margin
        c_low = margin
        r_high = h - rh - margin + 1
        c_high = w - rw - margin + 1
        if r_high <= r_low or c_high <= c_low:
            continue
        r = int(rng.integers(r_low, r_high))
        c = int(rng.integers(c_low, c_high))
        if not _can_place(grid, r, c, rh, rw, pad=1):
            continue
        _place_rect(grid, r, c, rh, rw, int(rng.choice(colors)))
        placed += 1
    _add_random_distractors(grid, rng, distractors, colors)
    return grid


def containment_scene(
    rng: np.random.Generator,
    grid_size: int | Sequence[int],
    colors: Sequence[int],
    distractors: int = 0,
) -> np.ndarray:
    h, w = _shape(grid_size)
    grid = np.zeros((h, w), dtype=int)
    top = max(1, h // 4)
    left = max(1, w // 4)
    bottom = min(h - 2, top + max(4, h // 2))
    right = min(w - 2, left + max(4, w // 2))
    frame_color = int(colors[1 % len(colors)])
    inner_color = int(colors[2 % len(colors)])
    grid[top, left : right + 1] = frame_color
    grid[bottom, left : right + 1] = frame_color
    grid[top : bottom + 1, left] = frame_color
    grid[top : bottom + 1, right] = frame_color
    _place_rect(grid, top + 2, left + 2, 1, 1, inner_color)
    _add_random_distractors(grid, rng, distractors, colors)
    return grid


def adjacency_scene(
    rng: np.random.Generator,
    grid_size: int | Sequence[int],
    colors: Sequence[int],
    distractors: int = 0,
) -> np.ndarray:
    h, w = _shape(grid_size)
    grid = np.zeros((h, w), dtype=int)
    r = max(1, h // 2 - 1)
    c = max(1, w // 2 - 2)
    _place_rect(grid, r, c, 2, 2, 1)
    _place_rect(grid, r, c + 2, 2, 2, int(colors[1 % len(colors)]))
    _add_random_distractors(grid, rng, distractors, colors)
    return grid


def symmetric_pair_scene(
    rng: np.random.Generator,
    grid_size: int | Sequence[int],
    colors: Sequence[int],
    distractors: int = 1,
) -> np.ndarray:
    h, w = _shape(grid_size)
    grid = np.zeros((h, w), dtype=int)
    rh = 2
    rw = 2
    r = int(rng.integers(1, max(2, h - rh)))
    c = int(rng.integers(1, max(2, w // 2 - rw)))
    mirror_c = w - c - rw
    color = int(colors[0])
    _place_rect(grid, r, c, rh, rw, color)
    _place_rect(grid, r, mirror_c, rh, rw, color)
    _add_random_distractors(grid, rng, distractors, colors[1:] or colors)
    return grid


def topology_scene(
    rng: np.random.Generator,
    grid_size: int | Sequence[int],
    colors: Sequence[int],
    distractors: int = 0,
) -> np.ndarray:
    h, w = _shape(grid_size)
    grid = np.zeros((h, w), dtype=int)
    top = max(1, h // 3)
    left = max(1, w // 3)
    bottom = min(h - 2, top + 3)
    right = min(w - 2, left + 3)
    color = int(colors[0])
    grid[top : bottom + 1, left : right + 1] = color
    if bottom - top >= 2 and right - left >= 2:
        grid[top + 1 : bottom, left + 1 : right] = 0
    _add_random_distractors(grid, rng, distractors, colors[1:] or colors)
    return grid


def largest_component_scene(
    rng: np.random.Generator,
    grid_size: int | Sequence[int],
    colors: Sequence[int],
    margin: int = 2,
    distractors: int = 1,
) -> np.ndarray:
    h, w = _shape(grid_size)
    grid = np.zeros((h, w), dtype=int)
    rh = min(3, max(2, h - 2 * margin))
    rw = min(3, max(2, w - 2 * margin))
    r_low = min(margin, max(0, h - rh))
    c_low = min(margin, max(0, w - rw))
    r_high = max(r_low + 1, h - rh - margin + 1)
    c_high = max(c_low + 1, w - rw - margin + 1)
    r = int(rng.integers(r_low, r_high))
    c = int(rng.integers(c_low, c_high))
    _place_rect(grid, r, c, rh, rw, int(colors[0]))
    _add_random_distractors(grid, rng, max(1, distractors), colors[1:] or colors, max_size=2)
    return grid


def noncommuting_composition_scene(
    rng: np.random.Generator,
    grid_size: int | Sequence[int],
    object_count: int,
    colors: Sequence[int],
    split: str,
    distractors: int = 0,
) -> np.ndarray:
    """Scene for an H2 probe where count and translate commute only on train.

    The latent rule is translate-down then count-components. Training scenes
    keep all components away from the lower boundary, making a plain count rule
    observationally equivalent. Held-out and oracle-probe scenes include one
    single-cell component on the lower edge, so translate-down clips it before
    counting.
    """

    h, w = _shape(grid_size)
    grid = np.zeros((h, w), dtype=int)
    total_components = max(2, min(w - 1, int(object_count) + max(0, int(distractors))))
    edge_sensitive = split in {"val", "test", "ood"}

    if edge_sensitive:
        edge_col = max(1, min(w - 2, w // 2))
        grid[h - 1, edge_col] = int(colors[0])
        placed = 1
    else:
        placed = 0

    attempts = 0
    while placed < total_components and attempts < total_components * 80 + 80:
        attempts += 1
        if h <= 4 or w <= 4:
            r = int(rng.integers(0, h))
            c = int(rng.integers(0, w))
        else:
            r = int(rng.integers(1, h - 2))
            c = int(rng.integers(1, w - 1))
        if grid[r, c] != 0 or not _can_place(grid, r, c, 1, 1, pad=1):
            continue
        grid[r, c] = int(colors[placed % len(colors)])
        placed += 1
    return grid


def h2_reflect_recolor_scene(
    rng: np.random.Generator,
    grid_size: int | Sequence[int],
    colors: Sequence[int],
    split: str,
    distractors: int = 0,
) -> np.ndarray:
    """Train scenes make reflection invisible; held-out scenes expose it."""

    h, w = _shape(grid_size)
    grid = np.zeros((h, w), dtype=int)
    color = int(colors[0])
    edge_sensitive = split in {"val", "test", "ood"}
    if edge_sensitive:
        r = max(1, h // 3)
        c = 1
    else:
        r = max(1, h // 3)
        c = max(1, w // 2 - 1)
    _place_rect(grid, r, c, min(2, h - r), min(2, w - c), color)
    if distractors > 0:
        dcolor = int(colors[1 % len(colors)])
        if edge_sensitive:
            _place_rect(grid, max(0, h - 2), min(w - 2, 2), 1, 1, dcolor)
        else:
            rr = max(0, h - 2)
            grid[rr, 1] = dcolor
            grid[rr, w - 2] = dcolor
    return grid


def h2_rotate_recolor_scene(
    rng: np.random.Generator,
    grid_size: int | Sequence[int],
    colors: Sequence[int],
    split: str,
    distractors: int = 0,
) -> np.ndarray:
    """Train scenes make 180 rotation invisible; held-out scenes expose it."""

    h, w = _shape(grid_size)
    grid = np.zeros((h, w), dtype=int)
    color = int(colors[0])
    edge_sensitive = split in {"val", "test", "ood"}
    if edge_sensitive:
        r, c = 1, 1
    else:
        r = max(1, h // 2 - 1)
        c = max(1, w // 2 - 1)
    _place_rect(grid, r, c, min(2, h - r), min(2, w - c), color)
    if distractors > 0:
        dcolor = int(colors[1 % len(colors)])
        if edge_sensitive:
            grid[max(1, h - 3), 2] = dcolor
        else:
            grid[1, 1] = dcolor
            grid[h - 2, w - 2] = dcolor
    return grid


def h2_reflect_select_border_scene(
    rng: np.random.Generator,
    grid_size: int | Sequence[int],
    colors: Sequence[int],
    split: str,
    distractors: int = 0,
) -> np.ndarray:
    """A simple border selector fits train, but reflection matters off train."""

    h, w = _shape(grid_size)
    grid = np.zeros((h, w), dtype=int)
    color = int(colors[0])
    edge_sensitive = split in {"val", "test", "ood"}
    if edge_sensitive:
        grid[1 : min(h - 1, 4), 0] = color
    else:
        grid[0, 1 : max(2, w - 1)] = color
    if distractors > 0 and h > 4 and w > 4:
        grid[h // 2, w // 2] = int(colors[1 % len(colors)])
    return grid


def h2_reflect_mark_contained_scene(
    rng: np.random.Generator,
    grid_size: int | Sequence[int],
    colors: Sequence[int],
    split: str,
    distractors: int = 0,
) -> np.ndarray:
    """A contained-object marker fits symmetric train scenes only."""

    h, w = _shape(grid_size)
    grid = np.zeros((h, w), dtype=int)
    frame_color = int(colors[1 % len(colors)])
    inner_color = int(colors[2 % len(colors)])
    edge_sensitive = split in {"val", "test", "ood"}
    top = max(1, h // 3)
    if edge_sensitive:
        left = 1
        right = min(w - 2, left + 3)
    else:
        left = max(1, w // 2 - 2)
        right = min(w - 2, left + 3)
    bottom = min(h - 2, top + 4)
    if right - left < 3:
        left = max(1, w - 6)
        right = min(w - 2, left + 3)
    grid[top, left : right + 1] = frame_color
    grid[bottom, left : right + 1] = frame_color
    grid[top : bottom + 1, left] = frame_color
    grid[top : bottom + 1, right] = frame_color
    inner_r = min(bottom - 1, top + 2)
    if edge_sensitive:
        inner_c = min(right - 1, left + 1)
        grid[inner_r, inner_c] = inner_color
    else:
        grid[inner_r, left + 1 : right] = inner_color
    if distractors > 0 and h > 4 and w > 4:
        dcolor = int(colors[3 % len(colors)])
        if edge_sensitive:
            grid[h - 2, min(w - 2, left + 1)] = dcolor
        else:
            grid[h - 2, 1] = dcolor
            grid[h - 2, w - 2] = dcolor
    return grid


def h2_copy_corner_scene(
    rng: np.random.Generator,
    grid_size: int | Sequence[int],
    colors: Sequence[int],
    split: str,
    distractors: int = 0,
) -> np.ndarray:
    """A largest-selector fits train; copy-to-corner matters off train."""

    h, w = _shape(grid_size)
    grid = np.zeros((h, w), dtype=int)
    color = int(colors[0])
    edge_sensitive = split in {"val", "test", "ood"}
    if edge_sensitive:
        r = max(2, h // 2)
        c = max(2, w // 2)
    else:
        r, c = 0, 0
    _place_rect(grid, r, c, min(2, h - r), min(2, w - c), color)
    if distractors > 0 and h > 4 and w > 4:
        grid[h - 1, w - 1] = int(colors[1 % len(colors)])
    return grid


def h2_largest_vs_border_scene(
    rng: np.random.Generator,
    grid_size: int | Sequence[int],
    colors: Sequence[int],
    split: str,
    distractors: int = 0,
) -> np.ndarray:
    """A border selector fits train; largest-object selection matters off train."""

    h, w = _shape(grid_size)
    grid = np.zeros((h, w), dtype=int)
    color = int(colors[0])
    edge_sensitive = split in {"val", "test", "ood"}
    if edge_sensitive:
        r = max(2, h // 2)
        c = max(2, w // 2)
        _place_rect(grid, r, c, min(3, h - r), min(3, w - c), color)
        grid[0, min(w - 2, 1)] = int(colors[1 % len(colors)])
    else:
        _place_rect(grid, 0, 1, min(2, h), min(3, w - 1), color)
        if distractors > 0 and h > 4 and w > 4:
            grid[h - 2, w - 2] = int(colors[1 % len(colors)])
    return grid


def copy_corner_distractor_scene(
    rng: np.random.Generator,
    grid_size: int | Sequence[int],
    colors: Sequence[int],
    distractors: int = 0,
) -> np.ndarray:
    h, w = _shape(grid_size)
    grid = np.zeros((h, w), dtype=int)
    r = max(1, h // 2)
    c = max(1, w // 2)
    _place_rect(grid, r, c, min(2, h - r), min(2, w - c), int(colors[0]))
    _add_random_distractors(grid, rng, max(2, distractors + 1), colors[1:] or colors, max_size=1)
    return grid


def nuisance_marker_scene(
    rng: np.random.Generator,
    grid_size: int | Sequence[int],
    object_count: int,
    colors: Sequence[int],
    split: str,
    distractors: int = 0,
) -> np.ndarray:
    grid = random_scene(rng, grid_size, object_count, colors, margin=1, distractors=distractors)
    marker = 9
    if split in {"train", "val"}:
        grid[0, 0] = marker
    else:
        grid[-1, -1] = marker
    return grid


def family_program(family: str, variant: int, colors: Sequence[int]) -> Program:
    colors = tuple(int(c) for c in colors)
    if family == "reflection":
        return [ProgramStep("reflect_vertical" if variant % 2 else "reflect_horizontal")]
    if family == "rotation":
        return [ProgramStep(["rotate_90", "rotate_180", "rotate_270"][variant % 3])]
    if family == "translation":
        options = [(-1, 0), (1, 0), (0, -1), (0, 1), (1, 1), (-1, -1)]
        dr, dc = options[variant % len(options)]
        return [ProgramStep("translate", {"dr": dr, "dc": dc})]
    if family == "recolor_predicate":
        return [ProgramStep("recolor_largest_component", {"new_color": colors[-1]})]
    if family == "component_count":
        return [ProgramStep("count_objects_emit_bar", {"color": colors[0]})]
    if family == "containment":
        return [ProgramStep("mark_contained_objects", {"mark_color": colors[-1]})]
    if family == "adjacency":
        return [ProgramStep("keep_adjacent_to_color", {"target_color": colors[0]})]
    if family == "symmetry":
        return [ProgramStep("remove_distractors_keep_symmetric_pair")]
    if family == "topology":
        return [ProgramStep("preserve_topology_change_color", {"new_color": colors[-2]})]
    if family == "spurious":
        return [ProgramStep("recolor_largest_component", {"new_color": colors[-1]})]
    if family == "compositional":
        return [
            ProgramStep("reflect_vertical"),
            ProgramStep("recolor_largest_component", {"new_color": colors[-2]}),
        ]
    if family == H2_NONCOMMUTING_FAMILY:
        return [
            ProgramStep("translate", {"dr": 1, "dc": 0}),
            ProgramStep("count_objects_emit_bar", {"color": colors[0]}),
        ]
    if family == H2_REFLECT_RECOLOR_FAMILY:
        return [
            ProgramStep("reflect_vertical"),
            ProgramStep("recolor_largest_component", {"new_color": colors[-2]}),
        ]
    if family == H2_ROTATE_RECOLOR_FAMILY:
        return [
            ProgramStep("rotate_180"),
            ProgramStep("recolor_largest_component", {"new_color": colors[-2]}),
        ]
    if family == H2_REFLECT_SELECT_BORDER_FAMILY:
        return [
            ProgramStep("reflect_vertical"),
            ProgramStep("select_by_relational_predicate", {"predicate": "touching_border"}),
        ]
    if family == H2_REFLECT_MARK_CONTAINED_FAMILY:
        return [
            ProgramStep("reflect_vertical"),
            ProgramStep("mark_contained_objects", {"mark_color": colors[-1]}),
        ]
    if family == H2_COPY_CORNER_FAMILY:
        return [ProgramStep("copy_to_corner", {"corner": "top_left"})]
    if family == H2_LARGEST_VS_BORDER_FAMILY:
        return [ProgramStep("select_by_relational_predicate", {"predicate": "largest"})]
    if family == PAPER_COMPOSITION_REFLECT_COUNT_FAMILY:
        return [
            ProgramStep("reflect_vertical"),
            ProgramStep("count_objects_emit_bar", {"color": colors[0]}),
        ]
    if family == PAPER_COMPOSITION_ADJACENT_REFLECT_FAMILY:
        return [
            ProgramStep("keep_adjacent_to_color", {"target_color": colors[0]}),
            ProgramStep("reflect_vertical"),
        ]
    if family == PAPER_COPY_CORNER_DISTRACTOR_FAMILY:
        return [ProgramStep("copy_to_corner", {"corner": "top_left"})]
    if family == PAPER_TOPOLOGY_DISTRACTOR_FAMILY:
        return [ProgramStep("preserve_topology_change_color", {"new_color": colors[-2]})]
    if family == PAPER_NUISANCE_MARKER_RECOLOR_FAMILY:
        return [ProgramStep("recolor_largest_component", {"new_color": colors[-1]})]
    if family == PAPER_CAUSAL_SPURIOUS_LARGEST_FAMILY:
        return [ProgramStep("select_by_relational_predicate", {"predicate": "largest"})]
    if family == PAPER_CONTAINMENT_REFLECT_MARK_FAMILY:
        return [
            ProgramStep("mark_contained_objects", {"mark_color": colors[-1]}),
            ProgramStep("reflect_horizontal"),
        ]
    if family == PAPER_SYMMETRY_REPAIR_CHALLENGE_FAMILY:
        return [ProgramStep("remove_distractors_keep_symmetric_pair")]
    if family == ARC_CROP_NONZERO_FAMILY:
        return [ProgramStep("crop_nonzero_bbox")]
    if family == ARC_CROP_LARGEST_FAMILY:
        return [ProgramStep("crop_largest_component_bbox")]
    if family == ARC_TRANSLATE_LARGEST_FAMILY:
        options = [(-2, 0), (-1, 0), (1, 0), (2, 0), (0, -1), (0, 1), (1, 1), (-1, -1)]
        dr, dc = options[variant % len(options)]
        return [ProgramStep("translate_largest_component", {"dr": dr, "dc": dc})]
    if family == ARC_SNAP_LARGEST_FAMILY:
        anchors = ["top_left", "top_right", "bottom_left", "bottom_right", "center"]
        return [ProgramStep("snap_largest_component", {"anchor": anchors[variant % len(anchors)]})]
    if family == ARC_EXPAND_CANVAS_FAMILY:
        anchors = ["center", "top_left", "top_right", "bottom_left", "bottom_right"]
        pad = 1 if variant % 2 == 0 else 2
        return [ProgramStep("expand_canvas", {"pad": pad, "anchor": anchors[variant % len(anchors)]})]
    raise ValueError(f"Unknown family: {family}")


def _input_for_family(
    family: str,
    rng: np.random.Generator,
    grid_size: int | Sequence[int],
    object_count: int,
    colors: Sequence[int],
    split: str,
    distractors: int,
) -> np.ndarray:
    if family == "containment":
        return containment_scene(rng, grid_size, colors, distractors=distractors)
    if family == "adjacency":
        return adjacency_scene(rng, grid_size, colors, distractors=distractors)
    if family == "symmetry":
        return symmetric_pair_scene(rng, grid_size, colors, distractors=max(1, distractors))
    if family == "topology":
        return topology_scene(rng, grid_size, colors, distractors=distractors)
    if family == H2_NONCOMMUTING_FAMILY:
        return noncommuting_composition_scene(
            rng,
            grid_size,
            object_count,
            colors,
            split=split,
            distractors=distractors,
        )
    if family == H2_REFLECT_RECOLOR_FAMILY:
        return h2_reflect_recolor_scene(rng, grid_size, colors, split=split, distractors=distractors)
    if family == H2_ROTATE_RECOLOR_FAMILY:
        return h2_rotate_recolor_scene(rng, grid_size, colors, split=split, distractors=distractors)
    if family == H2_REFLECT_SELECT_BORDER_FAMILY:
        return h2_reflect_select_border_scene(rng, grid_size, colors, split=split, distractors=distractors)
    if family == H2_REFLECT_MARK_CONTAINED_FAMILY:
        return h2_reflect_mark_contained_scene(rng, grid_size, colors, split=split, distractors=distractors)
    if family == H2_COPY_CORNER_FAMILY:
        return h2_copy_corner_scene(rng, grid_size, colors, split=split, distractors=distractors)
    if family == H2_LARGEST_VS_BORDER_FAMILY:
        return h2_largest_vs_border_scene(rng, grid_size, colors, split=split, distractors=distractors)
    if family == PAPER_COMPOSITION_REFLECT_COUNT_FAMILY:
        return random_scene(rng, grid_size, object_count, colors, margin=1, distractors=distractors)
    if family == PAPER_COMPOSITION_ADJACENT_REFLECT_FAMILY:
        return adjacency_scene(rng, grid_size, colors, distractors=max(1, distractors))
    if family == PAPER_COPY_CORNER_DISTRACTOR_FAMILY:
        return copy_corner_distractor_scene(rng, grid_size, colors, distractors=distractors)
    if family == PAPER_TOPOLOGY_DISTRACTOR_FAMILY:
        return topology_scene(rng, grid_size, colors, distractors=max(2, distractors))
    if family == PAPER_NUISANCE_MARKER_RECOLOR_FAMILY:
        return nuisance_marker_scene(rng, grid_size, object_count, colors, split=split, distractors=distractors)
    if family == PAPER_CAUSAL_SPURIOUS_LARGEST_FAMILY:
        return h2_largest_vs_border_scene(rng, grid_size, colors, split=split, distractors=max(1, distractors))
    if family == PAPER_CONTAINMENT_REFLECT_MARK_FAMILY:
        return containment_scene(rng, grid_size, colors, distractors=max(1, distractors))
    if family == PAPER_SYMMETRY_REPAIR_CHALLENGE_FAMILY:
        return symmetric_pair_scene(rng, grid_size, colors, distractors=max(3, distractors + 2))
    if family == ARC_CROP_NONZERO_FAMILY:
        return random_scene(rng, grid_size, object_count, colors, margin=2, distractors=max(1, distractors))
    if family in {ARC_CROP_LARGEST_FAMILY, ARC_TRANSLATE_LARGEST_FAMILY, ARC_SNAP_LARGEST_FAMILY}:
        return largest_component_scene(rng, grid_size, colors, margin=2, distractors=max(1, distractors))
    if family == ARC_EXPAND_CANVAS_FAMILY:
        return random_scene(rng, grid_size, object_count, colors, margin=1, distractors=max(1, distractors))
    margin = 1 if family == "translation" else 0
    grid = random_scene(rng, grid_size, object_count, colors, margin=margin, distractors=distractors)
    if family == "spurious":
        marker = 9
        if split in {"train", "val"}:
            grid[0, 0] = marker
        else:
            grid[-1, -1] = marker
    return grid


def make_example(
    family: str,
    program: Program,
    rng: np.random.Generator,
    grid_size: int | Sequence[int],
    object_count: int,
    colors: Sequence[int],
    split: str,
    distractors: int,
) -> TaskExample:
    input_grid = _input_for_family(
        family=family,
        rng=rng,
        grid_size=grid_size,
        object_count=object_count,
        colors=colors,
        split=split,
        distractors=distractors,
    )
    output_grid = apply_program(input_grid, program)
    return TaskExample(
        input_grid=input_grid,
        output_grid=output_grid,
        metadata={
            "split": split,
            "family": family,
            "grid_shape": list(input_grid.shape),
            "object_count_requested": int(object_count),
            "distractors_requested": int(distractors),
        },
    )


def generate_task(
    family: str,
    task_index: int,
    config: Mapping[str, Any],
    rng: np.random.Generator,
) -> ReasoningTask:
    colors = tuple(int(c) for c in config.get("colors", [1, 2, 3, 4, 5, 6, 7, 8]))
    program = family_program(family, task_index, colors)
    split_counts = dict(config.get("examples_per_split", {"train": 3, "val": 1, "test": 2, "ood": 2}))
    grid_size = config.get("grid_size", 8)
    ood_grid_size = config.get("ood_grid_size", 10)
    object_count = int(config.get("object_count", 3))
    ood_object_count = int(config.get("ood_object_count", object_count + 1))
    distractors = int(config.get("distractors", 0))
    ood_distractors = int(config.get("ood_distractors", distractors + 1))
    is_compositional = family == "compositional" or family in H2_AMBIGUOUS_FAMILIES or len(program) > 1
    distractor_condition = "distractor_heavy" if max(distractors, ood_distractors) > 0 else "simple"
    examples: Dict[str, List[TaskExample]] = {}
    for split, count in split_counts.items():
        examples[split] = []
        for _ in range(int(count)):
            is_ood = split == "ood"
            examples[split].append(
                make_example(
                    family=family,
                    program=program,
                    rng=rng,
                    grid_size=ood_grid_size if is_ood else grid_size,
                    object_count=ood_object_count if is_ood else object_count,
                    colors=colors,
                    split=split,
                    distractors=ood_distractors if is_ood else distractors,
                )
            )
    task_id = f"{family}_{task_index:03d}_{stable_hash({'family': family, 'idx': task_index, 'program': [s.to_dict() for s in program]}, 6)}"
    return ReasoningTask(
        task_id=task_id,
        family=family,
        program=program,
        examples=examples,
        metadata={
            "true_latent_rule": [step.to_dict() for step in program],
            "true_rule_family": family,
            "causal_variables": [step.name for step in program],
            "nuisance_variables": ["grid_size", "object_count", "distractors", "spurious_marker"],
            "designed_ambiguity_level": designed_ambiguity_level(family),
            "distractor_condition": distractor_condition,
            "distractor_count_train": distractors,
            "distractor_count_ood": ood_distractors,
            "compositional_condition": "compositional" if is_compositional else "non_compositional",
            "split_tags": {
                "ood": "held-out grid size/object/distractor regime",
                "leave_one_rule_family_out": family,
                "compositional": is_compositional,
            },
            "world_config": dict(config),
        },
    )


def generate_suite(config: Mapping[str, Any]) -> TaskSuite:
    seed = int(config.get("seed", 0))
    rng = _rng(seed)
    families = list(config.get("families", DEFAULT_FAMILIES))
    tasks_per_family = int(config.get("tasks_per_family", 1))
    tasks: List[ReasoningTask] = []
    for family in families:
        for task_index in range(tasks_per_family):
            tasks.append(generate_task(family, task_index, config, rng))
    return TaskSuite(
        name=str(config.get("name", "reasoning_suite")),
        tasks=tasks,
        config=dict(config),
        metadata={
            "seed": seed,
            "families": families,
            "implemented_splits": ["train", "val", "test", "ood"],
            "leave_one_rule_family_out": families,
            "compositional_families": [task.family for task in tasks if task.metadata["split_tags"]["compositional"]],
        },
    )


def save_suite(suite: TaskSuite, path: str | Path) -> None:
    write_json(path, suite.to_dict())


def load_suite(path: str | Path) -> TaskSuite:
    return TaskSuite.from_dict(read_json(path))


@dataclass
class HiddenRuleWorld:
    """Interactive synthetic world with a known secret program.

    This is intentionally an oracle only for synthetic diagnostics. Passive
    models do not get access to it unless an experiment config enables
    interactive falsification.
    """

    task: ReasoningTask
    seed: int = 0

    def __post_init__(self) -> None:
        self.rng = _rng(self.seed)

    def probe(self, input_grid: np.ndarray) -> np.ndarray:
        return apply_program(input_grid, self.task.program)

    def sample_probe(self, split: str = "ood") -> TaskExample:
        config = self.task.metadata.get("world_config", {})
        colors = tuple(int(c) for c in config.get("colors", [1, 2, 3, 4, 5, 6, 7, 8]))
        grid_size = int(config.get("probe_grid_size", 9 if split == "ood" else 8))
        object_count = int(config.get("probe_object_count", 4 if split == "ood" else 3))
        distractors = int(config.get("probe_distractors", 1 if split == "ood" else 0))
        return make_example(
            family=self.task.family,
            program=self.task.program,
            rng=self.rng,
            grid_size=grid_size,
            object_count=object_count,
            colors=colors,
            split=split,
            distractors=distractors,
        )
