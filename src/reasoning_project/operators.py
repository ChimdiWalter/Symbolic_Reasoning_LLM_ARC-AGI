"""Transformation library and finite candidate program generation."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Callable, Dict, Iterable, List, Mapping, Sequence, Tuple

import numpy as np

from .parsing import ObjectComponent, adjacency_edges, containment_edges, parse_objects
from .schemas import Program, ProgramStep, program_signature


OperatorFn = Callable[[np.ndarray, Mapping[str, int | str]], np.ndarray]

CORE_DSL_PROFILE = "core"
ARC_EXPANDED_DSL_PROFILE = "arc_expanded"
DSL_PROFILES = {CORE_DSL_PROFILE, ARC_EXPANDED_DSL_PROFILE}


@dataclass(frozen=True)
class OperatorSpec:
    name: str
    fn: OperatorFn
    base_cost: float
    implemented_claim: str


def _copy(grid: np.ndarray) -> np.ndarray:
    return np.asarray(grid, dtype=int).copy()


def _validate_profile(profile: str) -> str:
    profile = str(profile)
    if profile not in DSL_PROFILES:
        raise ValueError(f"Unknown DSL profile: {profile}")
    return profile


def _nonzero_bbox(grid: np.ndarray) -> Tuple[int, int, int, int] | None:
    coords = np.argwhere(np.asarray(grid, dtype=int) != 0)
    if coords.size == 0:
        return None
    min_r = int(coords[:, 0].min())
    min_c = int(coords[:, 1].min())
    max_r = int(coords[:, 0].max())
    max_c = int(coords[:, 1].max())
    return min_r, min_c, max_r, max_c


def _crop_bbox(grid: np.ndarray, bbox: Tuple[int, int, int, int] | None) -> np.ndarray:
    arr = np.asarray(grid, dtype=int)
    if bbox is None:
        return arr.copy()
    min_r, min_c, max_r, max_c = bbox
    return arr[min_r : max_r + 1, min_c : max_c + 1].copy()


def _anchor_start(canvas_shape: Tuple[int, int], patch_shape: Tuple[int, int], anchor: str) -> Tuple[int, int]:
    ch, cw = int(canvas_shape[0]), int(canvas_shape[1])
    ph, pw = int(patch_shape[0]), int(patch_shape[1])
    if anchor == "top_right":
        return 0, max(0, cw - pw)
    if anchor == "bottom_left":
        return max(0, ch - ph), 0
    if anchor == "bottom_right":
        return max(0, ch - ph), max(0, cw - pw)
    if anchor == "center":
        return max(0, (ch - ph) // 2), max(0, (cw - pw) // 2)
    return 0, 0


def op_identity(grid: np.ndarray, params: Mapping[str, int | str]) -> np.ndarray:
    return _copy(grid)


def op_reflect_horizontal(grid: np.ndarray, params: Mapping[str, int | str]) -> np.ndarray:
    return np.flipud(np.asarray(grid, dtype=int)).copy()


def op_reflect_vertical(grid: np.ndarray, params: Mapping[str, int | str]) -> np.ndarray:
    return np.fliplr(np.asarray(grid, dtype=int)).copy()


def op_rotate_90(grid: np.ndarray, params: Mapping[str, int | str]) -> np.ndarray:
    return np.rot90(np.asarray(grid, dtype=int), k=-1).copy()


def op_rotate_180(grid: np.ndarray, params: Mapping[str, int | str]) -> np.ndarray:
    return np.rot90(np.asarray(grid, dtype=int), k=2).copy()


def op_rotate_270(grid: np.ndarray, params: Mapping[str, int | str]) -> np.ndarray:
    return np.rot90(np.asarray(grid, dtype=int), k=1).copy()


def op_translate(grid: np.ndarray, params: Mapping[str, int | str]) -> np.ndarray:
    arr = np.asarray(grid, dtype=int)
    dr = int(params.get("dr", 0))
    dc = int(params.get("dc", 0))
    out = np.zeros_like(arr)
    h, w = arr.shape
    for r in range(h):
        for c in range(w):
            value = int(arr[r, c])
            if value == 0:
                continue
            nr = r + dr
            nc = c + dc
            if 0 <= nr < h and 0 <= nc < w:
                out[nr, nc] = value
    return out


def op_crop_nonzero_bbox(grid: np.ndarray, params: Mapping[str, int | str]) -> np.ndarray:
    return _crop_bbox(np.asarray(grid, dtype=int), _nonzero_bbox(np.asarray(grid, dtype=int)))


def op_crop_largest_component_bbox(grid: np.ndarray, params: Mapping[str, int | str]) -> np.ndarray:
    arr = np.asarray(grid, dtype=int)
    largest = _largest_object(parse_objects(arr))
    if largest is None:
        return arr.copy()
    return _crop_bbox(arr, largest.bbox)


def op_translate_largest_component(grid: np.ndarray, params: Mapping[str, int | str]) -> np.ndarray:
    arr = np.asarray(grid, dtype=int)
    largest = _largest_object(parse_objects(arr))
    if largest is None:
        return arr.copy()
    dr = int(params.get("dr", 0))
    dc = int(params.get("dc", 0))
    out = arr.copy()
    for r, c in largest.pixels:
        out[r, c] = 0
    h, w = arr.shape
    for r, c in largest.pixels:
        nr = r + dr
        nc = c + dc
        if 0 <= nr < h and 0 <= nc < w:
            out[nr, nc] = largest.color
    return out


def op_snap_largest_component(grid: np.ndarray, params: Mapping[str, int | str]) -> np.ndarray:
    arr = np.asarray(grid, dtype=int)
    largest = _largest_object(parse_objects(arr))
    if largest is None:
        return arr.copy()
    min_r, min_c, max_r, max_c = largest.bbox
    anchor = str(params.get("anchor", "top_left"))
    start_r, start_c = _anchor_start(arr.shape, (max_r - min_r + 1, max_c - min_c + 1), anchor)
    return op_translate_largest_component(
        arr,
        {"dr": int(start_r - min_r), "dc": int(start_c - min_c)},
    )


def op_expand_canvas(grid: np.ndarray, params: Mapping[str, int | str]) -> np.ndarray:
    arr = np.asarray(grid, dtype=int)
    pad = max(0, int(params.get("pad", 1)))
    anchor = str(params.get("anchor", "center"))
    out = np.zeros((arr.shape[0] + 2 * pad, arr.shape[1] + 2 * pad), dtype=int)
    start_r, start_c = _anchor_start(out.shape, arr.shape, anchor)
    out[start_r : start_r + arr.shape[0], start_c : start_c + arr.shape[1]] = arr
    return out


def _largest_object(objects: Sequence[ObjectComponent]) -> ObjectComponent | None:
    if not objects:
        return None
    return sorted(objects, key=lambda obj: (-obj.size, obj.object_id))[0]


def op_recolor_largest_component(grid: np.ndarray, params: Mapping[str, int | str]) -> np.ndarray:
    out = _copy(grid)
    objects = parse_objects(out)
    largest = _largest_object(objects)
    if largest is None:
        return out
    new_color = int(params.get("new_color", 1))
    for r, c in largest.pixels:
        out[r, c] = new_color
    return out


def op_preserve_topology_change_color(grid: np.ndarray, params: Mapping[str, int | str]) -> np.ndarray:
    out = _copy(grid)
    new_color = int(params.get("new_color", 1))
    out[out != 0] = new_color
    return out


def op_count_objects_emit_bar(grid: np.ndarray, params: Mapping[str, int | str]) -> np.ndarray:
    arr = np.asarray(grid, dtype=int)
    out = np.zeros_like(arr)
    color = int(params.get("color", 1))
    count = min(len(parse_objects(arr)), arr.shape[1])
    if count > 0:
        out[0, :count] = color
    return out


def op_select_by_relational_predicate(grid: np.ndarray, params: Mapping[str, int | str]) -> np.ndarray:
    arr = np.asarray(grid, dtype=int)
    predicate = str(params.get("predicate", "touching_border"))
    objects = parse_objects(arr)
    keep_ids: set[int] = set()
    if predicate == "touching_border":
        keep_ids = {obj.object_id for obj in objects if obj.touches_border}
    elif predicate == "largest":
        largest = _largest_object(objects)
        keep_ids = set() if largest is None else {largest.object_id}
    elif predicate == "contained":
        keep_ids = {inner for _outer, inner in containment_edges(objects)}
    elif predicate == "adjacent":
        keep_ids = {idx for edge in adjacency_edges(objects) for idx in edge}
    elif predicate == "has_hole":
        keep_ids = {obj.object_id for obj in objects if obj.holes > 0}
    else:
        keep_ids = {obj.object_id for obj in objects}
    out = np.zeros_like(arr)
    for obj in objects:
        if obj.object_id not in keep_ids:
            continue
        for r, c in obj.pixels:
            out[r, c] = obj.color
    return out


def op_copy_to_corner(grid: np.ndarray, params: Mapping[str, int | str]) -> np.ndarray:
    arr = np.asarray(grid, dtype=int)
    objects = parse_objects(arr)
    largest = _largest_object(objects)
    out = np.zeros_like(arr)
    if largest is None:
        return out
    min_r, min_c, max_r, max_c = largest.bbox
    patch = arr[min_r : max_r + 1, min_c : max_c + 1]
    mask = patch != 0
    corner = str(params.get("corner", "top_left"))
    ph, pw = patch.shape
    if corner == "top_right":
        start_r, start_c = 0, arr.shape[1] - pw
    elif corner == "bottom_left":
        start_r, start_c = arr.shape[0] - ph, 0
    elif corner == "bottom_right":
        start_r, start_c = arr.shape[0] - ph, arr.shape[1] - pw
    else:
        start_r, start_c = 0, 0
    out[start_r : start_r + ph, start_c : start_c + pw][mask] = patch[mask]
    return out


def _reflected_bbox(obj: ObjectComponent, width: int) -> Tuple[int, int, int, int]:
    min_r, min_c, max_r, max_c = obj.bbox
    return min_r, width - 1 - max_c, max_r, width - 1 - min_c


def op_transpose(grid: np.ndarray, params: Mapping[str, int | str]) -> np.ndarray:
    return np.asarray(grid, dtype=int).T.copy()


def op_color_remap(grid: np.ndarray, params: Mapping[str, int | str]) -> np.ndarray:
    arr = np.asarray(grid, dtype=int)
    src = int(params.get("src", 0))
    dst = int(params.get("dst", 0))
    out = arr.copy()
    out[arr == src] = dst
    return out


def op_color_swap(grid: np.ndarray, params: Mapping[str, int | str]) -> np.ndarray:
    arr = np.asarray(grid, dtype=int)
    a = int(params.get("a", 0))
    b = int(params.get("b", 0))
    out = arr.copy()
    out[arr == a] = b
    out[arr == b] = a
    return out


def op_upscale(grid: np.ndarray, params: Mapping[str, int | str]) -> np.ndarray:
    arr = np.asarray(grid, dtype=int)
    factor = int(params.get("factor", 2))
    return np.repeat(np.repeat(arr, factor, axis=0), factor, axis=1).copy()


def op_gravity_down(grid: np.ndarray, params: Mapping[str, int | str]) -> np.ndarray:
    arr = np.asarray(grid, dtype=int)
    out = np.zeros_like(arr)
    for c in range(arr.shape[1]):
        col = arr[:, c]
        nonzero = col[col != 0]
        if len(nonzero) > 0:
            out[arr.shape[0] - len(nonzero):, c] = nonzero
    return out


def op_gravity_up(grid: np.ndarray, params: Mapping[str, int | str]) -> np.ndarray:
    arr = np.asarray(grid, dtype=int)
    out = np.zeros_like(arr)
    for c in range(arr.shape[1]):
        col = arr[:, c]
        nonzero = col[col != 0]
        if len(nonzero) > 0:
            out[:len(nonzero), c] = nonzero
    return out


def op_gravity_left(grid: np.ndarray, params: Mapping[str, int | str]) -> np.ndarray:
    arr = np.asarray(grid, dtype=int)
    out = np.zeros_like(arr)
    for r in range(arr.shape[0]):
        row = arr[r, :]
        nonzero = row[row != 0]
        if len(nonzero) > 0:
            out[r, :len(nonzero)] = nonzero
    return out


def op_gravity_right(grid: np.ndarray, params: Mapping[str, int | str]) -> np.ndarray:
    arr = np.asarray(grid, dtype=int)
    out = np.zeros_like(arr)
    for r in range(arr.shape[0]):
        row = arr[r, :]
        nonzero = row[row != 0]
        if len(nonzero) > 0:
            out[r, arr.shape[1] - len(nonzero):] = nonzero
    return out


def op_fill_background(grid: np.ndarray, params: Mapping[str, int | str]) -> np.ndarray:
    arr = np.asarray(grid, dtype=int)
    color = int(params.get("color", 1))
    out = arr.copy()
    out[arr == 0] = color
    return out


def op_hollow_objects(grid: np.ndarray, params: Mapping[str, int | str]) -> np.ndarray:
    arr = np.asarray(grid, dtype=int)
    out = arr.copy()
    h, w = arr.shape
    for r in range(1, h - 1):
        for c in range(1, w - 1):
            if arr[r, c] != 0:
                neighbors = [arr[r-1, c], arr[r+1, c], arr[r, c-1], arr[r, c+1]]
                if all(n != 0 for n in neighbors):
                    out[r, c] = 0
    return out


def op_outline_objects(grid: np.ndarray, params: Mapping[str, int | str]) -> np.ndarray:
    arr = np.asarray(grid, dtype=int)
    color = int(params.get("color", 0))
    out = arr.copy() if color == 0 else np.full_like(arr, color)
    h, w = arr.shape
    for r in range(h):
        for c in range(w):
            if arr[r, c] != 0:
                is_border = False
                for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nr, nc = r + dr, c + dc
                    if nr < 0 or nr >= h or nc < 0 or nc >= w or arr[nr, nc] == 0:
                        is_border = True
                        break
                if is_border:
                    out[r, c] = arr[r, c]
                elif color == 0:
                    out[r, c] = 0
    return out


def op_keep_color(grid: np.ndarray, params: Mapping[str, int | str]) -> np.ndarray:
    arr = np.asarray(grid, dtype=int)
    color = int(params.get("color", 1))
    out = np.zeros_like(arr)
    out[arr == color] = color
    return out


def op_remove_color(grid: np.ndarray, params: Mapping[str, int | str]) -> np.ndarray:
    arr = np.asarray(grid, dtype=int)
    color = int(params.get("color", 1))
    out = arr.copy()
    out[arr == color] = 0
    return out


def op_most_frequent_color_fill(grid: np.ndarray, params: Mapping[str, int | str]) -> np.ndarray:
    arr = np.asarray(grid, dtype=int)
    flat = arr[arr != 0]
    if flat.size == 0:
        return arr.copy()
    values, counts = np.unique(flat, return_counts=True)
    dominant = int(values[np.argmax(counts)])
    out = arr.copy()
    out[arr != 0] = dominant
    return out


def op_least_frequent_color_remove(grid: np.ndarray, params: Mapping[str, int | str]) -> np.ndarray:
    arr = np.asarray(grid, dtype=int)
    flat = arr[arr != 0]
    if flat.size == 0:
        return arr.copy()
    values, counts = np.unique(flat, return_counts=True)
    rarest = int(values[np.argmin(counts)])
    out = arr.copy()
    out[arr == rarest] = 0
    return out


def op_denoise(grid: np.ndarray, params: Mapping[str, int | str]) -> np.ndarray:
    arr = np.asarray(grid, dtype=int)
    out = arr.copy()
    h, w = arr.shape
    for r in range(h):
        for c in range(w):
            if arr[r, c] != 0:
                neighbors = 0
                for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < h and 0 <= nc < w and arr[nr, nc] != 0:
                        neighbors += 1
                if neighbors == 0:
                    out[r, c] = 0
    return out


def op_flood_fill_enclosed(grid: np.ndarray, params: Mapping[str, int | str]) -> np.ndarray:
    arr = np.asarray(grid, dtype=int)
    fill_color = int(params.get("color", 1))
    h, w = arr.shape
    visited = np.zeros((h, w), dtype=bool)
    border_connected = np.zeros((h, w), dtype=bool)
    stack: list = []
    for r in range(h):
        for c in [0, w - 1]:
            if arr[r, c] == 0 and not visited[r, c]:
                stack.append((r, c))
    for c in range(w):
        for r in [0, h - 1]:
            if arr[r, c] == 0 and not visited[r, c]:
                stack.append((r, c))
    while stack:
        r, c = stack.pop()
        if visited[r, c]:
            continue
        visited[r, c] = True
        border_connected[r, c] = True
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = r + dr, c + dc
            if 0 <= nr < h and 0 <= nc < w and not visited[nr, nc] and arr[nr, nc] == 0:
                stack.append((nr, nc))
    out = arr.copy()
    for r in range(h):
        for c in range(w):
            if arr[r, c] == 0 and not border_connected[r, c]:
                out[r, c] = fill_color
    return out


def op_tile_horizontal(grid: np.ndarray, params: Mapping[str, int | str]) -> np.ndarray:
    arr = np.asarray(grid, dtype=int)
    n = int(params.get("n", 2))
    return np.tile(arr, (1, n)).copy()


def op_tile_vertical(grid: np.ndarray, params: Mapping[str, int | str]) -> np.ndarray:
    arr = np.asarray(grid, dtype=int)
    n = int(params.get("n", 2))
    return np.tile(arr, (n, 1)).copy()


def op_tile_both(grid: np.ndarray, params: Mapping[str, int | str]) -> np.ndarray:
    arr = np.asarray(grid, dtype=int)
    n = int(params.get("n", 2))
    return np.tile(arr, (n, n)).copy()


def op_downscale(grid: np.ndarray, params: Mapping[str, int | str]) -> np.ndarray:
    arr = np.asarray(grid, dtype=int)
    factor = int(params.get("factor", 2))
    h, w = arr.shape
    if h % factor != 0 or w % factor != 0:
        return arr.copy()
    return arr[::factor, ::factor].copy()


def op_mirror_horizontal_concat(grid: np.ndarray, params: Mapping[str, int | str]) -> np.ndarray:
    arr = np.asarray(grid, dtype=int)
    return np.concatenate([arr, np.fliplr(arr)], axis=1).copy()


def op_mirror_vertical_concat(grid: np.ndarray, params: Mapping[str, int | str]) -> np.ndarray:
    arr = np.asarray(grid, dtype=int)
    return np.concatenate([arr, np.flipud(arr)], axis=0).copy()


def op_extract_unique_subgrid(grid: np.ndarray, params: Mapping[str, int | str]) -> np.ndarray:
    arr = np.asarray(grid, dtype=int)
    objects = parse_objects(arr)
    if not objects:
        return arr.copy()
    best = None
    best_colors = 0
    for obj in objects:
        min_r, min_c, max_r, max_c = obj.bbox
        sub = arr[min_r:max_r + 1, min_c:max_c + 1]
        n_colors = len(set(np.unique(sub)) - {0})
        if n_colors > best_colors:
            best_colors = n_colors
            best = sub
    return best.copy() if best is not None else arr.copy()


def op_sort_rows_by_color_count(grid: np.ndarray, params: Mapping[str, int | str]) -> np.ndarray:
    arr = np.asarray(grid, dtype=int)
    counts = [np.count_nonzero(arr[r, :]) for r in range(arr.shape[0])]
    order = sorted(range(arr.shape[0]), key=lambda r: counts[r])
    return arr[order, :].copy()


def op_sort_cols_by_color_count(grid: np.ndarray, params: Mapping[str, int | str]) -> np.ndarray:
    arr = np.asarray(grid, dtype=int)
    counts = [np.count_nonzero(arr[:, c]) for c in range(arr.shape[1])]
    order = sorted(range(arr.shape[1]), key=lambda c: counts[c])
    return arr[:, order].copy()


def op_remove_distractors_keep_symmetric_pair(grid: np.ndarray, params: Mapping[str, int | str]) -> np.ndarray:
    arr = np.asarray(grid, dtype=int)
    objects = parse_objects(arr)
    out = np.zeros_like(arr)
    keep_ids: set[int] = set()
    for obj in objects:
        target_bbox = _reflected_bbox(obj, arr.shape[1])
        for other in objects:
            if obj.object_id == other.object_id:
                continue
            if obj.color == other.color and other.bbox == target_bbox:
                keep_ids.add(obj.object_id)
                keep_ids.add(other.object_id)
    for obj in objects:
        if obj.object_id in keep_ids:
            for r, c in obj.pixels:
                out[r, c] = obj.color
    return out


def op_keep_adjacent_to_color(grid: np.ndarray, params: Mapping[str, int | str]) -> np.ndarray:
    arr = np.asarray(grid, dtype=int)
    target_color = int(params.get("target_color", 1))
    objects = parse_objects(arr)
    edges = adjacency_edges(objects)
    id_to_obj = {obj.object_id: obj for obj in objects}
    target_ids = {obj.object_id for obj in objects if obj.color == target_color}
    keep_ids = set(target_ids)
    for a, b in edges:
        if a in target_ids:
            keep_ids.add(b)
        if b in target_ids:
            keep_ids.add(a)
    out = np.zeros_like(arr)
    for object_id in keep_ids:
        obj = id_to_obj[object_id]
        for r, c in obj.pixels:
            out[r, c] = obj.color
    return out


def op_mark_contained_objects(grid: np.ndarray, params: Mapping[str, int | str]) -> np.ndarray:
    out = _copy(grid)
    objects = parse_objects(out)
    mark_color = int(params.get("mark_color", 8))
    contained_ids = {inner for _outer, inner in containment_edges(objects)}
    for obj in objects:
        if obj.object_id in contained_ids:
            for r, c in obj.pixels:
                out[r, c] = mark_color
    return out


REGISTRY: Dict[str, OperatorSpec] = {
    "identity": OperatorSpec("identity", op_identity, 0.2, "No-op control transformation."),
    "reflect_horizontal": OperatorSpec("reflect_horizontal", op_reflect_horizontal, 1.0, "Exact horizontal grid reflection."),
    "reflect_vertical": OperatorSpec("reflect_vertical", op_reflect_vertical, 1.0, "Exact vertical grid reflection."),
    "rotate_90": OperatorSpec("rotate_90", op_rotate_90, 1.2, "Exact clockwise 90-degree rotation."),
    "rotate_180": OperatorSpec("rotate_180", op_rotate_180, 1.1, "Exact 180-degree rotation."),
    "rotate_270": OperatorSpec("rotate_270", op_rotate_270, 1.2, "Exact counter-clockwise 90-degree rotation."),
    "translate": OperatorSpec("translate", op_translate, 1.5, "Non-background pixel translation with clipping."),
    "crop_nonzero_bbox": OperatorSpec("crop_nonzero_bbox", op_crop_nonzero_bbox, 1.6, "Crop to the bounding box of all non-background pixels."),
    "crop_largest_component_bbox": OperatorSpec("crop_largest_component_bbox", op_crop_largest_component_bbox, 1.8, "Crop to the bounding box of the largest connected component."),
    "translate_largest_component": OperatorSpec("translate_largest_component", op_translate_largest_component, 1.9, "Translate only the largest connected component with clipping."),
    "snap_largest_component": OperatorSpec("snap_largest_component", op_snap_largest_component, 2.0, "Move the largest connected component to a named anchor."),
    "expand_canvas": OperatorSpec("expand_canvas", op_expand_canvas, 1.9, "Pad the canvas with background and place the original grid at a named anchor."),
    "recolor_largest_component": OperatorSpec("recolor_largest_component", op_recolor_largest_component, 1.7, "Largest connected component recoloring."),
    "preserve_topology_change_color": OperatorSpec("preserve_topology_change_color", op_preserve_topology_change_color, 1.5, "Preserve support topology while changing non-background color."),
    "count_objects_emit_bar": OperatorSpec("count_objects_emit_bar", op_count_objects_emit_bar, 1.8, "Connected-component count encoded as a top-row bar."),
    "select_by_relational_predicate": OperatorSpec("select_by_relational_predicate", op_select_by_relational_predicate, 2.0, "Approximate relation-based component selection."),
    "copy_to_corner": OperatorSpec("copy_to_corner", op_copy_to_corner, 1.8, "Copy largest object to a named corner."),
    "remove_distractors_keep_symmetric_pair": OperatorSpec("remove_distractors_keep_symmetric_pair", op_remove_distractors_keep_symmetric_pair, 2.2, "Keep vertically mirrored same-color component pairs."),
    "keep_adjacent_to_color": OperatorSpec("keep_adjacent_to_color", op_keep_adjacent_to_color, 2.0, "Keep target-color components and adjacent components."),
    "mark_contained_objects": OperatorSpec("mark_contained_objects", op_mark_contained_objects, 2.0, "Mark components whose bounding box is contained by another."),
    "transpose": OperatorSpec("transpose", op_transpose, 1.0, "Matrix transpose of the grid."),
    "color_remap": OperatorSpec("color_remap", op_color_remap, 1.2, "Replace all pixels of one color with another."),
    "color_swap": OperatorSpec("color_swap", op_color_swap, 1.3, "Swap two colors bidirectionally."),
    "upscale": OperatorSpec("upscale", op_upscale, 1.4, "Block-repeat upscale by integer factor."),
    "gravity_down": OperatorSpec("gravity_down", op_gravity_down, 1.5, "Drop non-background pixels to the bottom of each column."),
    "gravity_up": OperatorSpec("gravity_up", op_gravity_up, 1.5, "Push non-background pixels to the top of each column."),
    "gravity_left": OperatorSpec("gravity_left", op_gravity_left, 1.5, "Push non-background pixels to the left of each row."),
    "gravity_right": OperatorSpec("gravity_right", op_gravity_right, 1.5, "Push non-background pixels to the right of each row."),
    "fill_background": OperatorSpec("fill_background", op_fill_background, 1.3, "Replace background (0) with a specified color."),
    "hollow_objects": OperatorSpec("hollow_objects", op_hollow_objects, 1.7, "Remove interior pixels of solid objects."),
    "outline_objects": OperatorSpec("outline_objects", op_outline_objects, 1.7, "Keep only border pixels of non-background regions."),
    "keep_color": OperatorSpec("keep_color", op_keep_color, 1.1, "Zero out everything except the specified color."),
    "remove_color": OperatorSpec("remove_color", op_remove_color, 1.1, "Zero out all pixels of the specified color."),
    "most_frequent_color_fill": OperatorSpec("most_frequent_color_fill", op_most_frequent_color_fill, 1.6, "Recolor all non-background pixels to the most frequent non-background color."),
    "least_frequent_color_remove": OperatorSpec("least_frequent_color_remove", op_least_frequent_color_remove, 1.6, "Remove the least frequent non-background color."),
    "denoise": OperatorSpec("denoise", op_denoise, 1.4, "Remove isolated non-background pixels with no 4-connected neighbors."),
    "flood_fill_enclosed": OperatorSpec("flood_fill_enclosed", op_flood_fill_enclosed, 1.8, "Fill enclosed background regions with a specified color."),
    "tile_horizontal": OperatorSpec("tile_horizontal", op_tile_horizontal, 1.4, "Repeat grid horizontally n times."),
    "tile_vertical": OperatorSpec("tile_vertical", op_tile_vertical, 1.4, "Repeat grid vertically n times."),
    "tile_both": OperatorSpec("tile_both", op_tile_both, 1.4, "Repeat grid in both dimensions n times."),
    "downscale": OperatorSpec("downscale", op_downscale, 1.4, "Subsample grid by integer factor."),
    "mirror_horizontal_concat": OperatorSpec("mirror_horizontal_concat", op_mirror_horizontal_concat, 1.5, "Concatenate grid with its horizontal mirror."),
    "mirror_vertical_concat": OperatorSpec("mirror_vertical_concat", op_mirror_vertical_concat, 1.5, "Concatenate grid with its vertical mirror."),
    "extract_unique_subgrid": OperatorSpec("extract_unique_subgrid", op_extract_unique_subgrid, 2.0, "Extract the bounding box of the object with the most distinct colors."),
    "sort_rows_by_color_count": OperatorSpec("sort_rows_by_color_count", op_sort_rows_by_color_count, 1.8, "Sort rows by number of non-background pixels."),
    "sort_cols_by_color_count": OperatorSpec("sort_cols_by_color_count", op_sort_cols_by_color_count, 1.8, "Sort columns by number of non-background pixels."),
}


def apply_step(grid: np.ndarray, step: ProgramStep) -> np.ndarray:
    if step.name not in REGISTRY:
        raise KeyError(f"Unknown operator: {step.name}")
    return REGISTRY[step.name].fn(grid, step.params)


def apply_program(grid: np.ndarray, program: Iterable[ProgramStep]) -> np.ndarray:
    out = np.asarray(grid, dtype=int).copy()
    for step in program:
        out = apply_step(out, step)
    return out


def program_description_length(program: Iterable[ProgramStep]) -> float:
    total = 0.0
    for step in program:
        spec = REGISTRY[step.name]
        param_cost = 0.15 * len(step.params)
        value_cost = 0.05 * sum(len(str(value)) for value in step.params.values())
        total += spec.base_cost + param_cost + value_cost
    return total


def base_candidate_steps(
    colors: Sequence[int] = (1, 2, 3, 4, 5, 6, 7, 8),
    profile: str = CORE_DSL_PROFILE,
) -> List[ProgramStep]:
    profile = _validate_profile(profile)
    colors = tuple(int(c) for c in colors)
    steps: List[ProgramStep] = [
        ProgramStep("identity"),
        ProgramStep("reflect_horizontal"),
        ProgramStep("reflect_vertical"),
        ProgramStep("rotate_90"),
        ProgramStep("rotate_180"),
        ProgramStep("rotate_270"),
    ]
    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1), (1, 1), (-1, -1)]:
        steps.append(ProgramStep("translate", {"dr": dr, "dc": dc}))
    for color in colors:
        steps.append(ProgramStep("recolor_largest_component", {"new_color": color}))
        steps.append(ProgramStep("preserve_topology_change_color", {"new_color": color}))
        steps.append(ProgramStep("count_objects_emit_bar", {"color": color}))
        steps.append(ProgramStep("keep_adjacent_to_color", {"target_color": color}))
    predicates = ["touching_border", "largest", "contained", "adjacent"]
    if profile == ARC_EXPANDED_DSL_PROFILE:
        predicates.append("has_hole")
    for predicate in predicates:
        steps.append(ProgramStep("select_by_relational_predicate", {"predicate": predicate}))
    for corner in ["top_left", "top_right", "bottom_left", "bottom_right"]:
        steps.append(ProgramStep("copy_to_corner", {"corner": corner}))
    for color in colors[-3:]:
        steps.append(ProgramStep("mark_contained_objects", {"mark_color": color}))
    steps.append(ProgramStep("remove_distractors_keep_symmetric_pair"))
    if profile == ARC_EXPANDED_DSL_PROFILE:
        steps.extend(
            [
                ProgramStep("crop_nonzero_bbox"),
                ProgramStep("crop_largest_component_bbox"),
            ]
        )
        for dr, dc in [
            (-2, 0),
            (-1, 0),
            (1, 0),
            (2, 0),
            (0, -2),
            (0, -1),
            (0, 1),
            (0, 2),
            (-1, -1),
            (-1, 1),
            (1, -1),
            (1, 1),
        ]:
            steps.append(ProgramStep("translate_largest_component", {"dr": dr, "dc": dc}))
        for anchor in ["top_left", "top_right", "bottom_left", "bottom_right", "center"]:
            steps.append(ProgramStep("snap_largest_component", {"anchor": anchor}))
        for pad in [1, 2]:
            for anchor in ["center", "top_left", "top_right", "bottom_left", "bottom_right"]:
                steps.append(ProgramStep("expand_canvas", {"pad": pad, "anchor": anchor}))
        steps.append(ProgramStep("transpose"))
        for src in colors:
            for dst in colors:
                if src != dst:
                    steps.append(ProgramStep("color_remap", {"src": src, "dst": dst}))
            for dst in [0]:
                steps.append(ProgramStep("color_remap", {"src": src, "dst": dst}))
            steps.append(ProgramStep("color_remap", {"src": 0, "dst": src}))
        for i, a in enumerate(colors):
            for b in colors[i + 1:]:
                steps.append(ProgramStep("color_swap", {"a": a, "b": b}))
        for factor in [2, 3]:
            steps.append(ProgramStep("upscale", {"factor": factor}))
            steps.append(ProgramStep("downscale", {"factor": factor}))
        steps.extend([
            ProgramStep("gravity_down"),
            ProgramStep("gravity_up"),
            ProgramStep("gravity_left"),
            ProgramStep("gravity_right"),
        ])
        for color in colors:
            steps.append(ProgramStep("fill_background", {"color": color}))
            steps.append(ProgramStep("keep_color", {"color": color}))
            steps.append(ProgramStep("remove_color", {"color": color}))
            steps.append(ProgramStep("flood_fill_enclosed", {"color": color}))
        steps.extend([
            ProgramStep("hollow_objects"),
            ProgramStep("outline_objects"),
            ProgramStep("most_frequent_color_fill"),
            ProgramStep("least_frequent_color_remove"),
            ProgramStep("denoise"),
        ])
        for n in [2, 3]:
            steps.append(ProgramStep("tile_horizontal", {"n": n}))
            steps.append(ProgramStep("tile_vertical", {"n": n}))
            steps.append(ProgramStep("tile_both", {"n": n}))
        steps.extend([
            ProgramStep("mirror_horizontal_concat"),
            ProgramStep("mirror_vertical_concat"),
            ProgramStep("extract_unique_subgrid"),
            ProgramStep("sort_rows_by_color_count"),
            ProgramStep("sort_cols_by_color_count"),
        ])
    return steps


def candidate_programs(
    max_depth: int = 1,
    colors: Sequence[int] = (1, 2, 3, 4, 5, 6, 7, 8),
    profile: str = CORE_DSL_PROFILE,
) -> List[Program]:
    """Generate a compact finite hypothesis class.

    Depth 2 includes geometric/color and selection/color compositions but avoids
    a full Cartesian explosion.
    """

    if max_depth < 1:
        return [[ProgramStep("identity")]]
    profile = _validate_profile(profile)
    steps = base_candidate_steps(colors, profile=profile)
    programs: List[Program] = [[step] for step in steps]
    if max_depth >= 2:
        geometry = [
            s
            for s in steps
            if s.name
            in {
                "reflect_horizontal",
                "reflect_vertical",
                "rotate_90",
                "rotate_180",
                "rotate_270",
                "translate",
                "translate_largest_component",
                "snap_largest_component",
            }
        ]
        semantic = [
            s
            for s in steps
            if s.name
            in {
                "recolor_largest_component",
                "preserve_topology_change_color",
                "count_objects_emit_bar",
                "select_by_relational_predicate",
                "copy_to_corner",
                "remove_distractors_keep_symmetric_pair",
                "keep_adjacent_to_color",
                "mark_contained_objects",
            }
        ]
        canvas_ops = [s for s in steps if s.name in {"crop_nonzero_bbox", "crop_largest_component_bbox", "expand_canvas"}]
        color_ops = [
            s for s in steps
            if s.name in {
                "color_remap", "color_swap", "fill_background",
                "keep_color", "remove_color", "most_frequent_color_fill",
                "least_frequent_color_remove",
            }
        ]
        structural_ops = [
            s for s in steps
            if s.name in {
                "gravity_down", "gravity_up", "gravity_left", "gravity_right",
                "hollow_objects", "outline_objects", "denoise",
                "flood_fill_enclosed", "transpose",
            }
        ]
        for first, second in product(geometry, semantic):
            programs.append([first, second])
        for first, second in product(semantic, geometry[:4]):
            programs.append([first, second])
        if profile == ARC_EXPANDED_DSL_PROFILE:
            for first, second in product(geometry, canvas_ops):
                programs.append([first, second])
            for first, second in product(canvas_ops, semantic):
                programs.append([first, second])
            for first, second in product(canvas_ops, geometry[:8]):
                programs.append([first, second])
            for first, second in product(geometry[:6], color_ops):
                programs.append([first, second])
            for first, second in product(color_ops[:18], geometry[:6]):
                programs.append([first, second])
            for first, second in product(structural_ops, geometry[:6]):
                programs.append([first, second])
            for first, second in product(geometry[:6], structural_ops):
                programs.append([first, second])
            for first, second in product(structural_ops, canvas_ops):
                programs.append([first, second])
            for first, second in product(canvas_ops, structural_ops):
                programs.append([first, second])
            for first, second in product(color_ops[:18], canvas_ops):
                programs.append([first, second])
            for first, second in product(canvas_ops, color_ops[:18]):
                programs.append([first, second])
    seen: set[str] = set()
    unique: List[Program] = []
    for program in programs:
        sig = program_signature(program)
        if sig in seen:
            continue
        seen.add(sig)
        unique.append(program)
    return unique
