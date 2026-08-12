"""Marker-projection operator family: removed objects project information
onto kept objects or background instead of physically relocating.

Projection types:
    - color_stamp: removed marker's color appears at a cell determined by
      spatial relationship to nearest kept object
    - line_projection: removed marker projects a line of its color in a
      cardinal/diagonal direction until hitting an obstacle
    - directional_ray: like line_projection but fills all cells along the ray
    - region_fill: removed marker's color fills an enclosed region
    - color_transfer: removed marker recolors the nearest/matched kept object
    - position_signal: removed marker's position determines where a modification
      happens to a kept object (e.g., which row/column to fill)

Each type supports: parameter inference, cross-training validation, LOO
validation, and execution on test inputs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy import ndimage

from reasoning_project.reasoning_engine import (
    _extract_objects_with_properties,
    _classify_kept_removed,
    _get_property_value,
)


# ═══════════════════════════════════════════════════════════════════════════
# PARAMETER DATACLASS
# ═══════════════════════════════════════════════════════════════════════════

PROJECTION_TYPES = [
    "color_stamp",
    "line_projection",
    "directional_ray",
    "region_fill",
    "color_transfer",
    "position_signal",
]

DIRECTIONS = {
    "up": (-1, 0),
    "down": (1, 0),
    "left": (0, -1),
    "right": (0, 1),
    "up_left": (-1, -1),
    "up_right": (-1, 1),
    "down_left": (1, -1),
    "down_right": (1, 1),
}


@dataclass
class MarkerProjectionParams:
    source_selector: str          # property selecting "marker" objects
    target_selector: str          # "kept" objects or "background"
    projection_type: str          # one of PROJECTION_TYPES
    projection_direction: str     # "cardinal", "diagonal", "nearest", "all", or specific direction name
    color_rule: str               # "source_color", "target_color", "learned_map"
    fill_mode: str                # "cell", "line", "region", "stamp"
    color_map: Optional[Dict[int, int]] = None  # learned color mapping
    keep_when_true: bool = True   # which group the selector selects
    background: int = 0
    direction_vector: Optional[Tuple[int, int]] = None  # explicit (dr, dc) for line/ray
    stamp_offset: Optional[Tuple[int, int]] = None  # offset for color_stamp
    signal_axis: Optional[str] = None  # "row", "col", or "both" for position_signal
    signal_fill_color_rule: Optional[str] = None  # how to determine fill color for position_signal

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_selector": self.source_selector,
            "target_selector": self.target_selector,
            "projection_type": self.projection_type,
            "projection_direction": self.projection_direction,
            "color_rule": self.color_rule,
            "fill_mode": self.fill_mode,
            "color_map": self.color_map,
            "keep_when_true": self.keep_when_true,
            "background": self.background,
            "direction_vector": list(self.direction_vector) if self.direction_vector else None,
            "stamp_offset": list(self.stamp_offset) if self.stamp_offset else None,
            "signal_axis": self.signal_axis,
            "signal_fill_color_rule": self.signal_fill_color_rule,
        }


# ═══════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def _split_kept_removed(grid, selector, keep_when_true):
    """Split objects into kept and removed groups using a selector property."""
    objects = _extract_objects_with_properties(grid)
    if len(objects) < 2:
        return None, None, None
    kept = []
    removed = []
    for obj in objects:
        val = _get_property_value(obj, selector)
        if val == keep_when_true:
            kept.append(obj)
        else:
            removed.append(obj)
    if not kept or not removed:
        return None, None, None
    return objects, kept, removed


def _build_kept_mask(grid_shape, kept):
    """Build a boolean mask of all kept-object pixels."""
    mask = np.zeros(grid_shape, dtype=bool)
    for obj in kept:
        mask |= obj["mask"]
    return mask


def _build_base_grid(grid, kept, background=0):
    """Build a grid with only kept objects (removed objects erased)."""
    base = np.full(grid.shape, background, dtype=grid.dtype)
    for obj in kept:
        base[obj["mask"]] = grid[obj["mask"]]
    # Also preserve background pixels that are not part of any object
    all_obj_mask = np.zeros(grid.shape, dtype=bool)
    objects = _extract_objects_with_properties(grid, bg=background)
    for obj in objects:
        all_obj_mask |= obj["mask"]
    # Background cells: not part of any object
    bg_mask = ~all_obj_mask
    base[bg_mask] = grid[bg_mask]
    return base


def _nearest_kept_object(obj, kept):
    """Find the nearest kept object to a removed object by centroid distance."""
    if not kept:
        return None
    cr = obj.get("center_r", (obj["bbox"][0] + obj["bbox"][2]) / 2.0)
    cc = obj.get("center_c", (obj["bbox"][1] + obj["bbox"][3]) / 2.0)
    best_dist = float("inf")
    best_obj = None
    for k in kept:
        kr = k.get("center_r", (k["bbox"][0] + k["bbox"][2]) / 2.0)
        kc = k.get("center_c", (k["bbox"][1] + k["bbox"][3]) / 2.0)
        dist = abs(cr - kr) + abs(cc - kc)
        if dist < best_dist:
            best_dist = dist
            best_obj = k
    return best_obj


def _object_centroid(obj):
    """Return (row, col) centroid of an object."""
    return (
        obj.get("center_r", (obj["bbox"][0] + obj["bbox"][2]) / 2.0),
        obj.get("center_c", (obj["bbox"][1] + obj["bbox"][3]) / 2.0),
    )


# ═══════════════════════════════════════════════════════════════════════════
# INDUCER
# ═══════════════════════════════════════════════════════════════════════════

class MarkerProjectionInducer:
    """Infer marker-projection rules from training examples."""

    def propose_projections(
        self,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        selector: str,
        keep_when_true: bool = True,
    ) -> List[MarkerProjectionParams]:
        """Try all projection types, return those that fit all training pairs."""
        candidates = []
        for try_fn in [
            self._try_line_projection,
            self._try_directional_ray,
            self._try_color_stamp,
            self._try_region_fill,
            self._try_color_transfer,
            self._try_position_signal,
        ]:
            try:
                result = try_fn(train_pairs, selector, keep_when_true)
                if result is not None:
                    candidates.append(result)
            except Exception:
                pass
        return candidates

    # ------------------------------------------------------------------
    # line_projection
    # ------------------------------------------------------------------

    def _try_line_projection(
        self,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        selector: str,
        keep_when_true: bool,
    ) -> Optional[MarkerProjectionParams]:
        """Removed markers project a line of their color in a specific cardinal
        direction until hitting a kept object or grid boundary.
        The marker itself is removed (erased to background)."""
        for dir_name, (dr, dc) in DIRECTIONS.items():
            if self._check_line_projection_fits(train_pairs, selector, keep_when_true, dr, dc):
                return MarkerProjectionParams(
                    source_selector=selector,
                    target_selector="background",
                    projection_type="line_projection",
                    projection_direction=dir_name,
                    color_rule="source_color",
                    fill_mode="line",
                    keep_when_true=keep_when_true,
                    background=0,
                    direction_vector=(dr, dc),
                )
        return None

    def _check_line_projection_fits(self, train_pairs, selector, keep_when_true, dr, dc):
        for inp, out in train_pairs:
            pred = _execute_line_projection(inp, selector, keep_when_true, dr, dc)
            if pred is None or not np.array_equal(pred, out):
                return False
        return True

    # ------------------------------------------------------------------
    # directional_ray
    # ------------------------------------------------------------------

    def _try_directional_ray(
        self,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        selector: str,
        keep_when_true: bool,
    ) -> Optional[MarkerProjectionParams]:
        """Like line_projection but the marker cell itself is kept and the ray
        extends from it (marker color preserved at original position)."""
        for dir_name, (dr, dc) in DIRECTIONS.items():
            if self._check_directional_ray_fits(train_pairs, selector, keep_when_true, dr, dc):
                return MarkerProjectionParams(
                    source_selector=selector,
                    target_selector="background",
                    projection_type="directional_ray",
                    projection_direction=dir_name,
                    color_rule="source_color",
                    fill_mode="line",
                    keep_when_true=keep_when_true,
                    background=0,
                    direction_vector=(dr, dc),
                )
        return None

    def _check_directional_ray_fits(self, train_pairs, selector, keep_when_true, dr, dc):
        for inp, out in train_pairs:
            pred = _execute_directional_ray(inp, selector, keep_when_true, dr, dc)
            if pred is None or not np.array_equal(pred, out):
                return False
        return True

    # ------------------------------------------------------------------
    # color_stamp
    # ------------------------------------------------------------------

    def _try_color_stamp(
        self,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        selector: str,
        keep_when_true: bool,
    ) -> Optional[MarkerProjectionParams]:
        """Removed markers stamp their color at specific cells relative to
        the nearest kept object. Infer a consistent offset from training."""
        all_offsets = []
        for inp, out in train_pairs:
            objects, kept, removed = _split_kept_removed(inp, selector, keep_when_true)
            if objects is None:
                return None

            pair_offsets = []
            for rm_obj in removed:
                nearest = _nearest_kept_object(rm_obj, kept)
                if nearest is None:
                    return None

                rm_r, rm_c = _object_centroid(rm_obj)
                k_r, k_c = _object_centroid(nearest)

                # Find cells in output that differ from base grid and match marker color
                base = _build_base_grid(inp, kept)
                diff_mask = (out != base) & (out == rm_obj["primary_color"])
                diff_rows, diff_cols = np.where(diff_mask)
                if len(diff_rows) == 0:
                    return None

                # Compute offset of new colored cells relative to nearest kept centroid
                for r, c in zip(diff_rows.tolist(), diff_cols.tolist()):
                    offset = (r - int(round(k_r)), c - int(round(k_c)))
                    pair_offsets.append(offset)

            all_offsets.append(set(map(tuple, pair_offsets)) if pair_offsets else set())

        if not all_offsets:
            return None

        # Check if there is at least one consistent offset pattern
        # For simplicity, check if relative offset from marker to nearest kept
        # is consistent across examples
        offsets_per_pair = []
        for inp, out in train_pairs:
            objects, kept, removed = _split_kept_removed(inp, selector, keep_when_true)
            if objects is None:
                return None
            pair_offs = []
            for rm_obj in removed:
                nearest = _nearest_kept_object(rm_obj, kept)
                if nearest is None:
                    return None
                rm_r, rm_c = _object_centroid(rm_obj)
                k_r, k_c = _object_centroid(nearest)
                # The offset from the marker to its effect in the output
                base = _build_base_grid(inp, kept)
                diff_mask = (out != base) & (out == rm_obj["primary_color"])
                diff_rows, diff_cols = np.where(diff_mask)
                if len(diff_rows) == 0:
                    return None
                # Offset from marker position to stamped position
                for r, c in zip(diff_rows.tolist(), diff_cols.tolist()):
                    pair_offs.append((r - int(round(rm_r)), c - int(round(rm_c))))
            offsets_per_pair.append(pair_offs)

        if not offsets_per_pair or not offsets_per_pair[0]:
            return None

        # Check for a consistent single offset across all examples
        # Use the first example's offsets as reference
        ref_offsets = set(offsets_per_pair[0])
        for pair_offs in offsets_per_pair[1:]:
            if set(pair_offs) != ref_offsets:
                return None

        # Use the most common offset
        from collections import Counter
        all_flat = [o for po in offsets_per_pair for o in po]
        if not all_flat:
            return None
        most_common = Counter(all_flat).most_common(1)[0][0]

        # Validate: does applying this stamp offset reproduce all outputs?
        params = MarkerProjectionParams(
            source_selector=selector,
            target_selector="nearest_kept",
            projection_type="color_stamp",
            projection_direction="nearest",
            color_rule="source_color",
            fill_mode="cell",
            keep_when_true=keep_when_true,
            background=0,
            stamp_offset=most_common,
        )
        for inp, out in train_pairs:
            pred = execute_marker_projection(inp, params, train_pairs)
            if pred is None or not np.array_equal(pred, out):
                return None

        return params

    # ------------------------------------------------------------------
    # region_fill
    # ------------------------------------------------------------------

    def _try_region_fill(
        self,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        selector: str,
        keep_when_true: bool,
    ) -> Optional[MarkerProjectionParams]:
        """Removed markers' color fills an enclosed region defined by kept objects.
        Check if the removed object's color flood-fills into the background-connected
        region containing it that is bounded by kept objects."""
        # First check: do the outputs have flood-filled regions of removed-object colors?
        for inp, out in train_pairs:
            objects, kept, removed = _split_kept_removed(inp, selector, keep_when_true)
            if objects is None:
                return None

            base = _build_base_grid(inp, kept)
            diff = (out != base)
            if not np.any(diff):
                return None

            # Each removed object should correspond to a filled region
            for rm_obj in removed:
                color = rm_obj["primary_color"]
                rm_r = int(round(rm_obj.get("center_r", (rm_obj["bbox"][0] + rm_obj["bbox"][2]) / 2.0)))
                rm_c = int(round(rm_obj.get("center_c", (rm_obj["bbox"][1] + rm_obj["bbox"][3]) / 2.0)))

                # Check: at marker position, the output should have marker's color
                if rm_r < 0 or rm_r >= out.shape[0] or rm_c < 0 or rm_c >= out.shape[1]:
                    return None
                if out[rm_r, rm_c] != color:
                    return None

        # Build and validate the region fill
        params = MarkerProjectionParams(
            source_selector=selector,
            target_selector="background",
            projection_type="region_fill",
            projection_direction="all",
            color_rule="source_color",
            fill_mode="region",
            keep_when_true=keep_when_true,
            background=0,
        )
        for inp, out in train_pairs:
            pred = execute_marker_projection(inp, params, train_pairs)
            if pred is None or not np.array_equal(pred, out):
                return None

        return params

    # ------------------------------------------------------------------
    # color_transfer
    # ------------------------------------------------------------------

    def _try_color_transfer(
        self,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        selector: str,
        keep_when_true: bool,
    ) -> Optional[MarkerProjectionParams]:
        """Removed markers transfer their color to the nearest kept object.
        E.g., a small colored dot recolors the nearest large object."""
        # Check: for each training pair, each removed object's color appears
        # on the nearest kept object in the output
        color_maps = []
        for inp, out in train_pairs:
            objects, kept, removed = _split_kept_removed(inp, selector, keep_when_true)
            if objects is None:
                return None

            pair_map = {}
            for rm_obj in removed:
                nearest = _nearest_kept_object(rm_obj, kept)
                if nearest is None:
                    return None

                rm_color = rm_obj["primary_color"]
                # In the output, the nearest kept object should have the removed marker's color
                out_colors_at_kept = set(out[nearest["mask"]].tolist())
                out_colors_at_kept.discard(0)

                if rm_color not in out_colors_at_kept:
                    return None

                # The kept object's original color maps to the marker's color
                kept_color = nearest["primary_color"]
                pair_map[kept_color] = rm_color

            color_maps.append(pair_map)

        # Verify consistency across pairs
        if not color_maps:
            return None

        # Check: is it a direct "recolor kept with removed's color"?
        params = MarkerProjectionParams(
            source_selector=selector,
            target_selector="nearest_kept",
            projection_type="color_transfer",
            projection_direction="nearest",
            color_rule="source_color",
            fill_mode="cell",
            keep_when_true=keep_when_true,
            background=0,
        )
        for inp, out in train_pairs:
            pred = execute_marker_projection(inp, params, train_pairs)
            if pred is None or not np.array_equal(pred, out):
                return None

        return params

    # ------------------------------------------------------------------
    # position_signal
    # ------------------------------------------------------------------

    def _try_position_signal(
        self,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        selector: str,
        keep_when_true: bool,
    ) -> Optional[MarkerProjectionParams]:
        """Removed markers' position determines where a modification happens
        to a kept object (e.g., fill the row or column of the marker)."""
        for axis in ["row", "col"]:
            for color_rule in ["source_color", "target_color"]:
                params = MarkerProjectionParams(
                    source_selector=selector,
                    target_selector="background",
                    projection_type="position_signal",
                    projection_direction="all",
                    color_rule=color_rule,
                    fill_mode="line",
                    keep_when_true=keep_when_true,
                    background=0,
                    signal_axis=axis,
                    signal_fill_color_rule=color_rule,
                )
                fits = True
                for inp, out in train_pairs:
                    pred = execute_marker_projection(inp, params, train_pairs)
                    if pred is None or not np.array_equal(pred, out):
                        fits = False
                        break
                if fits:
                    return params

        return None

    # ------------------------------------------------------------------
    # LOO validation
    # ------------------------------------------------------------------

    def loo_validate(
        self,
        params: MarkerProjectionParams,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    ) -> Tuple[bool, List[Dict[str, Any]]]:
        """Leave-one-out validation: for each pair, re-infer params from
        the remaining pairs and check prediction on the held-out pair."""
        if len(train_pairs) < 2:
            return True, []

        failures = []
        for i in range(len(train_pairs)):
            held_inp, held_out = train_pairs[i]
            train_subset = [p for j, p in enumerate(train_pairs) if j != i]

            # Re-infer parameters from subset
            sub_params = infer_marker_projection_params(
                train_subset,
                params.source_selector,
                keep_when_true=params.keep_when_true,
            )
            if sub_params is None:
                failures.append({
                    "fold": i,
                    "reason": "param_inference_failed_on_subset",
                })
                return False, failures

            pred = execute_marker_projection(held_inp, sub_params, train_subset)
            if pred is None or not np.array_equal(pred, held_out):
                failures.append({
                    "fold": i,
                    "reason": "prediction_mismatch",
                })
                return False, failures

        return True, []


# ═══════════════════════════════════════════════════════════════════════════
# EXECUTION FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def _execute_line_projection(
    grid: np.ndarray,
    selector: str,
    keep_when_true: bool,
    dr: int,
    dc: int,
    background: int = 0,
) -> Optional[np.ndarray]:
    """Project lines from removed markers in direction (dr, dc) until hitting
    a kept object or grid boundary. Marker itself is erased."""
    objects, kept, removed = _split_kept_removed(grid, selector, keep_when_true)
    if objects is None:
        return None

    result = _build_base_grid(grid, kept, background)
    h, w = grid.shape
    kept_mask = _build_kept_mask(grid.shape, kept)

    for rm_obj in removed:
        color = rm_obj["primary_color"]
        rows, cols = np.where(rm_obj["mask"])
        for r, c in zip(rows.tolist(), cols.tolist()):
            cr, cc = r + dr, c + dc
            while 0 <= cr < h and 0 <= cc < w:
                if kept_mask[cr, cc]:
                    break
                result[cr, cc] = color
                cr += dr
                cc += dc

    return result


def _execute_directional_ray(
    grid: np.ndarray,
    selector: str,
    keep_when_true: bool,
    dr: int,
    dc: int,
    background: int = 0,
) -> Optional[np.ndarray]:
    """Like line_projection but the marker's original cells are preserved."""
    objects, kept, removed = _split_kept_removed(grid, selector, keep_when_true)
    if objects is None:
        return None

    result = grid.copy()  # Keep everything including markers
    h, w = grid.shape
    kept_mask = _build_kept_mask(grid.shape, kept)

    for rm_obj in removed:
        color = rm_obj["primary_color"]
        rows, cols = np.where(rm_obj["mask"])
        for r, c in zip(rows.tolist(), cols.tolist()):
            cr, cc = r + dr, c + dc
            while 0 <= cr < h and 0 <= cc < w:
                if kept_mask[cr, cc]:
                    break
                result[cr, cc] = color
                cr += dr
                cc += dc

    return result


def _execute_color_stamp(
    grid: np.ndarray,
    selector: str,
    keep_when_true: bool,
    stamp_offset: Tuple[int, int],
    background: int = 0,
) -> Optional[np.ndarray]:
    """Stamp removed marker's color at offset position relative to marker centroid."""
    objects, kept, removed = _split_kept_removed(grid, selector, keep_when_true)
    if objects is None:
        return None

    result = _build_base_grid(grid, kept, background)
    h, w = grid.shape

    for rm_obj in removed:
        color = rm_obj["primary_color"]
        rm_r, rm_c = _object_centroid(rm_obj)
        target_r = int(round(rm_r)) + stamp_offset[0]
        target_c = int(round(rm_c)) + stamp_offset[1]
        if 0 <= target_r < h and 0 <= target_c < w:
            result[target_r, target_c] = color

    return result


def _execute_region_fill(
    grid: np.ndarray,
    selector: str,
    keep_when_true: bool,
    background: int = 0,
) -> Optional[np.ndarray]:
    """Fill the background-connected region containing each removed marker
    with that marker's color. The region is bounded by kept objects and
    grid edges."""
    objects, kept, removed = _split_kept_removed(grid, selector, keep_when_true)
    if objects is None:
        return None

    result = _build_base_grid(grid, kept, background)
    h, w = grid.shape
    kept_mask = _build_kept_mask(grid.shape, kept)

    # Build a barrier mask: kept objects are barriers
    barrier = kept_mask.copy()

    for rm_obj in removed:
        color = rm_obj["primary_color"]
        rm_r = int(round(rm_obj.get("center_r", (rm_obj["bbox"][0] + rm_obj["bbox"][2]) / 2.0)))
        rm_c = int(round(rm_obj.get("center_c", (rm_obj["bbox"][1] + rm_obj["bbox"][3]) / 2.0)))

        if rm_r < 0 or rm_r >= h or rm_c < 0 or rm_c >= w:
            continue

        # Flood fill from the marker position, stopping at barriers
        filled = np.zeros((h, w), dtype=bool)
        stack = [(rm_r, rm_c)]
        while stack:
            r, c = stack.pop()
            if r < 0 or r >= h or c < 0 or c >= w:
                continue
            if filled[r, c] or barrier[r, c]:
                continue
            filled[r, c] = True
            stack.extend([(r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)])

        result[filled] = color

    return result


def _execute_color_transfer(
    grid: np.ndarray,
    selector: str,
    keep_when_true: bool,
    background: int = 0,
) -> Optional[np.ndarray]:
    """Recolor each nearest kept object with the removed marker's color."""
    objects, kept, removed = _split_kept_removed(grid, selector, keep_when_true)
    if objects is None:
        return None

    result = _build_base_grid(grid, kept, background)

    for rm_obj in removed:
        nearest = _nearest_kept_object(rm_obj, kept)
        if nearest is None:
            continue
        result[nearest["mask"]] = rm_obj["primary_color"]

    return result


def _execute_position_signal(
    grid: np.ndarray,
    selector: str,
    keep_when_true: bool,
    signal_axis: str,
    color_rule: str,
    background: int = 0,
) -> Optional[np.ndarray]:
    """Fill the row or column of each removed marker with its color (or the
    nearest kept object's color), stopping at kept objects."""
    objects, kept, removed = _split_kept_removed(grid, selector, keep_when_true)
    if objects is None:
        return None

    result = _build_base_grid(grid, kept, background)
    h, w = grid.shape
    kept_mask = _build_kept_mask(grid.shape, kept)

    for rm_obj in removed:
        if color_rule == "source_color":
            color = rm_obj["primary_color"]
        elif color_rule == "target_color":
            nearest = _nearest_kept_object(rm_obj, kept)
            color = nearest["primary_color"] if nearest else rm_obj["primary_color"]
        else:
            color = rm_obj["primary_color"]

        rm_r = int(round(rm_obj.get("center_r", (rm_obj["bbox"][0] + rm_obj["bbox"][2]) / 2.0)))
        rm_c = int(round(rm_obj.get("center_c", (rm_obj["bbox"][1] + rm_obj["bbox"][3]) / 2.0)))

        if signal_axis == "row":
            for c in range(w):
                if not kept_mask[rm_r, c] and result[rm_r, c] == background:
                    result[rm_r, c] = color
        elif signal_axis == "col":
            for r in range(h):
                if not kept_mask[r, rm_c] and result[r, rm_c] == background:
                    result[r, rm_c] = color

    return result


# ═══════════════════════════════════════════════════════════════════════════
# TOP-LEVEL API
# ═══════════════════════════════════════════════════════════════════════════

def infer_marker_projection_params(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    selector: str,
    keep_when_true: bool = True,
) -> Optional[MarkerProjectionParams]:
    """Top-level: try all projection types, validate across training,
    return the first that fits all training pairs."""
    if not train_pairs:
        return None

    # Quick sanity: all pairs must have same-shape input/output
    for inp, out in train_pairs:
        if inp.shape != out.shape:
            return None

    inducer = MarkerProjectionInducer()
    candidates = inducer.propose_projections(train_pairs, selector, keep_when_true)
    if not candidates:
        return None

    # Return the first candidate (they are already validated against all training)
    return candidates[0]


def execute_marker_projection(
    grid: np.ndarray,
    params: MarkerProjectionParams,
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> Optional[np.ndarray]:
    """Execute a marker projection on an input grid using inferred parameters."""
    try:
        ptype = params.projection_type
        bg = params.background

        if ptype == "line_projection":
            if params.direction_vector is None:
                return None
            dr, dc = params.direction_vector
            return _execute_line_projection(
                grid, params.source_selector, params.keep_when_true, dr, dc, bg,
            )

        if ptype == "directional_ray":
            if params.direction_vector is None:
                return None
            dr, dc = params.direction_vector
            return _execute_directional_ray(
                grid, params.source_selector, params.keep_when_true, dr, dc, bg,
            )

        if ptype == "color_stamp":
            if params.stamp_offset is None:
                return None
            return _execute_color_stamp(
                grid, params.source_selector, params.keep_when_true,
                params.stamp_offset, bg,
            )

        if ptype == "region_fill":
            return _execute_region_fill(
                grid, params.source_selector, params.keep_when_true, bg,
            )

        if ptype == "color_transfer":
            return _execute_color_transfer(
                grid, params.source_selector, params.keep_when_true, bg,
            )

        if ptype == "position_signal":
            if params.signal_axis is None:
                return None
            color_rule = params.signal_fill_color_rule or params.color_rule
            return _execute_position_signal(
                grid, params.source_selector, params.keep_when_true,
                params.signal_axis, color_rule, bg,
            )

        return None
    except Exception:
        return None
