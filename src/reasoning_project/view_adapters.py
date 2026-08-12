"""View adapters for grid representation transformation.

Each adapter transforms a grid into a structured view that exposes aspects
invisible to the default connected-component parser. Adapters do NOT solve
tasks -- they change the representation so that existing operators can solve
tasks that are otherwise out of reach.

Architecture:
    ViewAdapter (protocol)
      FrameInteriorAdapter     -- extract interior of a rectangular frame
      ColorLayerAdapter        -- decompose into per-color binary layers
      ObjectInObjectAdapter    -- detect containment, extract inner objects
      SymmetryAxisAdapter      -- detect reflection axes, work in half-grid
      RepeatedMotifAdapter     -- detect tiling, work on the base motif
"""
from __future__ import annotations

import abc
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy import ndimage


# ============================================================================
# Protocol
# ============================================================================

class ViewAdapter(abc.ABC):
    """Base class for view adapters."""

    adapter_type: str = "base"

    @abc.abstractmethod
    def can_apply(self, grid: np.ndarray) -> bool:
        """Check if this adapter is applicable to the given grid."""

    @abc.abstractmethod
    def parse(self, grid: np.ndarray) -> Dict[str, Any]:
        """Parse grid into structured view."""

    @abc.abstractmethod
    def extract_interior_objects(self, grid: np.ndarray) -> List[Dict]:
        """Extract objects from the adapted view."""

    @abc.abstractmethod
    def lift_train_pairs(
        self, train_pairs: List[Tuple[np.ndarray, np.ndarray]]
    ) -> List[Tuple[np.ndarray, np.ndarray]]:
        """Transform train pairs into adapted view."""

    @abc.abstractmethod
    def project(
        self, adapted_output: np.ndarray, original_grid: np.ndarray
    ) -> np.ndarray:
        """Project adapted output back to full grid."""

    def signature(self) -> Dict[str, Any]:
        """Return a hashable signature for memory retrieval."""
        return {"adapter_type": self.adapter_type}


# ============================================================================
# FrameInteriorAdapter
# ============================================================================

class FrameInteriorAdapter(ViewAdapter):
    """Detects a rectangular frame and extracts interior objects only.

    The frame is the outermost contiguous border of a single color that
    forms a complete rectangle around the grid edges. Interior is everything
    inside, with frame pixels replaced by background (0).

    Why this matters: the default connected-component parser treats the
    frame as the single largest object. When the task requires operating
    on interior objects (e.g., filter by is_largest among interior objects),
    the default parser selects the frame instead.
    """

    adapter_type = "frame_interior"

    def can_apply(self, grid: np.ndarray) -> bool:
        """Check if grid has a rectangular frame."""
        parsed = self._detect_frame(grid)
        return parsed is not None

    def parse(self, grid: np.ndarray) -> Dict[str, Any]:
        """Parse grid, extracting frame and interior."""
        result = self._detect_frame(grid)
        if result is None:
            return {"has_frame": False}
        frame_color, thickness, interior = result
        return {
            "has_frame": True,
            "frame_color": frame_color,
            "frame_thickness": thickness,
            "interior": interior,
            "original_shape": grid.shape,
        }

    def extract_interior_objects(self, grid: np.ndarray) -> List[Dict]:
        """Extract objects from the interior only (frame removed)."""
        parsed = self.parse(grid)
        if not parsed.get("has_frame"):
            return []
        interior = parsed["interior"]
        # Use connected component extraction on the interior
        labeled, n = ndimage.label(interior != 0)
        objects = []
        for lab in range(1, n + 1):
            mask = labeled == lab
            rows, cols = np.where(mask)
            if len(rows) == 0:
                continue
            area = int(mask.sum())
            primary_color = int(interior[mask].flat[0])
            objects.append({
                "label": lab,
                "mask": mask,
                "area": area,
                "primary_color": primary_color,
                "center_r": float(rows.mean()),
                "center_c": float(cols.mean()),
                "bbox": (int(rows.min()), int(cols.min()),
                         int(rows.max()), int(cols.max())),
            })
        return objects

    def lift_train_pairs(
        self, train_pairs: List[Tuple[np.ndarray, np.ndarray]]
    ) -> List[Tuple[np.ndarray, np.ndarray]]:
        """Lift train pairs: extract interior from both input and output."""
        lifted = []
        for inp, out in train_pairs:
            inp_parsed = self.parse(inp)
            out_parsed = self.parse(out)
            if inp_parsed.get("has_frame") and out_parsed.get("has_frame"):
                lifted.append((inp_parsed["interior"], out_parsed["interior"]))
            elif inp_parsed.get("has_frame"):
                # Output might not have frame (e.g., extraction task)
                lifted.append((inp_parsed["interior"], out))
            else:
                lifted.append((inp, out))
        return lifted

    def project(
        self, adapted_output: np.ndarray, original_grid: np.ndarray
    ) -> np.ndarray:
        """Put adapted output back inside the frame."""
        parsed = self.parse(original_grid)
        if not parsed.get("has_frame"):
            return adapted_output
        result = original_grid.copy()
        t = parsed["frame_thickness"]
        h, w = original_grid.shape
        interior_h = h - 2 * t
        interior_w = w - 2 * t
        if adapted_output.shape == (interior_h, interior_w):
            result[t:h - t, t:w - t] = adapted_output
        elif adapted_output.shape == original_grid.shape:
            result[t:h - t, t:w - t] = adapted_output[t:h - t, t:w - t]
        else:
            # Output is a different size -- return as-is (extraction mode)
            return adapted_output
        return result

    def _detect_frame(
        self, grid: np.ndarray
    ) -> Optional[Tuple[int, int, np.ndarray]]:
        """Detect a rectangular frame.

        Returns (frame_color, thickness, interior_grid) or None.
        """
        h, w = grid.shape
        if h < 3 or w < 3:
            return None

        # Check top row for a uniform non-background color
        top_row = grid[0, :]
        if len(set(top_row.tolist())) != 1:
            return None
        frame_color = int(top_row[0])
        if frame_color == 0:
            return None

        # Check all border pixels match frame_color
        bottom_row = grid[-1, :]
        left_col = grid[:, 0]
        right_col = grid[:, -1]
        if not (np.all(bottom_row == frame_color) and
                np.all(left_col == frame_color) and
                np.all(right_col == frame_color)):
            return None

        # Determine frame thickness -- check how many rows from top are all frame_color
        thickness = 0
        for r in range(h // 2):
            if np.all(grid[r, :] == frame_color):
                thickness = r + 1
            else:
                break

        if thickness == 0:
            thickness = 1

        # Verify bottom thickness matches
        for r in range(h - 1, h - 1 - thickness, -1):
            if not np.all(grid[r, :] == frame_color):
                return None

        # Verify left/right thickness matches
        for c in range(thickness):
            if not np.all(grid[:, c] == frame_color):
                return None
            if not np.all(grid[:, w - 1 - c] == frame_color):
                return None

        # Extract interior
        if h - 2 * thickness < 1 or w - 2 * thickness < 1:
            return None

        interior = grid[thickness:h - thickness, thickness:w - thickness].copy()
        return frame_color, thickness, interior

    def signature(self) -> Dict[str, Any]:
        return {"adapter_type": self.adapter_type}


# ============================================================================
# ColorLayerAdapter
# ============================================================================

class ColorLayerAdapter(ViewAdapter):
    """Decomposes grid into per-color binary masks.

    The transformation can operate on one color layer independently (e.g.,
    remove all objects of color X while keeping color Y objects).

    Why this matters: the default parser extracts all objects together.
    When the task requires operating on a specific color layer (e.g., remove
    all objects of one color), the default parser cannot distinguish the
    layers.
    """

    adapter_type = "color_layer"

    def __init__(self, target_color: Optional[int] = None):
        self.target_color = target_color

    def can_apply(self, grid: np.ndarray) -> bool:
        """Check if grid has at least 2 non-background colors."""
        colors = set(grid.flatten().tolist()) - {0}
        return len(colors) >= 2

    def parse(self, grid: np.ndarray) -> Dict[str, Any]:
        """Parse grid into per-color layers."""
        colors = sorted(set(grid.flatten().tolist()) - {0})
        layers = {}
        for c in colors:
            layers[c] = (grid == c).astype(int)
        return {
            "colors": colors,
            "layers": layers,
            "original_shape": grid.shape,
        }

    def extract_interior_objects(self, grid: np.ndarray) -> List[Dict]:
        """Extract objects per color layer."""
        parsed = self.parse(grid)
        objects = []
        lab_counter = 1
        for color in parsed["colors"]:
            layer = parsed["layers"][color]
            labeled, n = ndimage.label(layer)
            for lab in range(1, n + 1):
                mask = labeled == lab
                rows, cols = np.where(mask)
                if len(rows) == 0:
                    continue
                objects.append({
                    "label": lab_counter,
                    "mask": mask,
                    "area": int(mask.sum()),
                    "primary_color": color,
                    "color_layer": color,
                    "center_r": float(rows.mean()),
                    "center_c": float(cols.mean()),
                    "bbox": (int(rows.min()), int(cols.min()),
                             int(rows.max()), int(cols.max())),
                })
                lab_counter += 1
        return objects

    def lift_train_pairs(
        self, train_pairs: List[Tuple[np.ndarray, np.ndarray]]
    ) -> List[Tuple[np.ndarray, np.ndarray]]:
        """Lift train pairs by extracting the target color layer.

        If target_color is set, extract that layer. Otherwise, auto-detect
        which color layer changes between input and output.
        """
        target = self.target_color
        if target is None:
            target = self._detect_changing_color(train_pairs)
        if target is None:
            return train_pairs

        lifted = []
        for inp, out in train_pairs:
            # Create a version of input with only the target color visible
            inp_layer = np.where(inp == target, target, 0).astype(inp.dtype)
            out_layer = np.where(out == target, target, 0).astype(out.dtype)
            lifted.append((inp_layer, out_layer))
        return lifted

    def project(
        self, adapted_output: np.ndarray, original_grid: np.ndarray
    ) -> np.ndarray:
        """Merge adapted layer back into original grid."""
        target = self.target_color
        if target is None:
            return adapted_output
        result = original_grid.copy()
        # Remove original target color pixels
        result[original_grid == target] = 0
        # Add back adapted output's target color pixels
        result[adapted_output == target] = target
        return result

    def _detect_changing_color(
        self, train_pairs: List[Tuple[np.ndarray, np.ndarray]]
    ) -> Optional[int]:
        """Detect which color changes between input and output."""
        changed_colors = set()
        for inp, out in train_pairs:
            if inp.shape != out.shape:
                continue
            diff = inp != out
            if not np.any(diff):
                continue
            inp_at_diff = set(inp[diff].tolist())
            out_at_diff = set(out[diff].tolist())
            # Colors that were present in input but removed in output
            removed = inp_at_diff - out_at_diff - {0}
            if removed:
                changed_colors.update(removed)
        if len(changed_colors) == 1:
            return changed_colors.pop()
        return None

    def signature(self) -> Dict[str, Any]:
        return {
            "adapter_type": self.adapter_type,
            "target_color": self.target_color,
        }


# ============================================================================
# ObjectInObjectAdapter
# ============================================================================

class ObjectInObjectAdapter(ViewAdapter):
    """Detects containment relationships (object A fully inside object B).

    Extracts inner objects with containment parent metadata.

    Why this matters: the default parser extracts connected components
    but does not detect spatial containment. When the task requires
    extracting the inner object from a container, the default parser
    has no containment predicate.
    """

    adapter_type = "object_in_object"

    def can_apply(self, grid: np.ndarray) -> bool:
        """Check if grid has containment relationships."""
        containments = self._find_containments(grid)
        return len(containments) > 0

    def parse(self, grid: np.ndarray) -> Dict[str, Any]:
        """Parse grid, detecting containment relationships."""
        containments = self._find_containments(grid)
        return {
            "containments": containments,
            "original_shape": grid.shape,
        }

    def extract_interior_objects(self, grid: np.ndarray) -> List[Dict]:
        """Extract inner objects with parent metadata."""
        containments = self._find_containments(grid)
        inner_objects = []
        for c in containments:
            inner_objects.append({
                "label": c["inner_label"],
                "mask": c["inner_mask"],
                "area": c["inner_area"],
                "primary_color": c["inner_color"],
                "parent_label": c["outer_label"],
                "parent_color": c["outer_color"],
                "center_r": c["inner_center_r"],
                "center_c": c["inner_center_c"],
                "bbox": c["inner_bbox"],
            })
        return inner_objects

    def lift_train_pairs(
        self, train_pairs: List[Tuple[np.ndarray, np.ndarray]]
    ) -> List[Tuple[np.ndarray, np.ndarray]]:
        """Lift train pairs by extracting inner objects."""
        lifted = []
        for inp, out in train_pairs:
            containments = self._find_containments(inp)
            if containments:
                # Extract a grid with only inner objects
                inner_grid = np.zeros_like(inp)
                for c in containments:
                    inner_grid[c["inner_mask"]] = c["inner_color"]
                lifted.append((inner_grid, out))
            else:
                lifted.append((inp, out))
        return lifted

    def project(
        self, adapted_output: np.ndarray, original_grid: np.ndarray
    ) -> np.ndarray:
        """Project inner object output back to full grid."""
        # If adapted output is already the right shape, return it
        if adapted_output.shape == original_grid.shape:
            return adapted_output
        # Otherwise treat as extraction -- return as-is
        return adapted_output

    def _find_containments(self, grid: np.ndarray) -> List[Dict]:
        """Find all containment relationships in the grid."""
        h, w = grid.shape
        labeled, n = ndimage.label(grid != 0)
        if n < 2:
            return []

        objects = []
        for lab in range(1, n + 1):
            mask = labeled == lab
            rows, cols = np.where(mask)
            if len(rows) == 0:
                continue
            r_min, r_max = int(rows.min()), int(rows.max())
            c_min, c_max = int(cols.min()), int(cols.max())
            objects.append({
                "label": lab,
                "mask": mask,
                "bbox": (r_min, c_min, r_max, c_max),
                "area": int(mask.sum()),
                "primary_color": int(grid[mask].flat[0]),
                "center_r": float(rows.mean()),
                "center_c": float(cols.mean()),
            })

        containments = []
        for i, inner in enumerate(objects):
            for j, outer in enumerate(objects):
                if i == j:
                    continue
                if inner["area"] >= outer["area"]:
                    continue
                # Check if inner's bbox is strictly inside outer's bbox
                ir_min, ic_min, ir_max, ic_max = inner["bbox"]
                or_min, oc_min, or_max, oc_max = outer["bbox"]
                if (ir_min > or_min and ir_max < or_max and
                        ic_min > oc_min and ic_max < oc_max):
                    # Check that inner color differs from outer color
                    if inner["primary_color"] != outer["primary_color"]:
                        containments.append({
                            "inner_label": inner["label"],
                            "inner_mask": inner["mask"],
                            "inner_area": inner["area"],
                            "inner_color": inner["primary_color"],
                            "inner_center_r": inner["center_r"],
                            "inner_center_c": inner["center_c"],
                            "inner_bbox": inner["bbox"],
                            "outer_label": outer["label"],
                            "outer_area": outer["area"],
                            "outer_color": outer["primary_color"],
                        })
        return containments

    def signature(self) -> Dict[str, Any]:
        return {"adapter_type": self.adapter_type}


# ============================================================================
# SymmetryAxisAdapter
# ============================================================================

class SymmetryAxisAdapter(ViewAdapter):
    """Detects reflection symmetry axes and works in half-grid coordinates.

    Why this matters: when a grid has reflection symmetry along an axis,
    operating on just half the grid (and mirroring the result) reduces the
    search space and makes patterns visible that are obscured in the full grid.
    """

    adapter_type = "symmetry_axis"

    def can_apply(self, grid: np.ndarray) -> bool:
        """Check if grid has a reflection symmetry axis."""
        return self._detect_axis(grid) is not None

    def parse(self, grid: np.ndarray) -> Dict[str, Any]:
        """Parse grid, detecting symmetry axis and extracting half."""
        axis = self._detect_axis(grid)
        if axis is None:
            return {"has_symmetry": False}
        h, w = grid.shape
        if axis == "horizontal":
            half = grid[:h // 2, :].copy()
        else:
            half = grid[:, :w // 2].copy()
        return {
            "has_symmetry": True,
            "axis": axis,
            "half_grid": half,
            "original_shape": grid.shape,
        }

    def extract_interior_objects(self, grid: np.ndarray) -> List[Dict]:
        """Extract objects from the half-grid."""
        parsed = self.parse(grid)
        if not parsed.get("has_symmetry"):
            return []
        half = parsed["half_grid"]
        labeled, n = ndimage.label(half != 0)
        objects = []
        for lab in range(1, n + 1):
            mask = labeled == lab
            rows, cols = np.where(mask)
            if len(rows) == 0:
                continue
            objects.append({
                "label": lab,
                "mask": mask,
                "area": int(mask.sum()),
                "primary_color": int(half[mask].flat[0]),
                "center_r": float(rows.mean()),
                "center_c": float(cols.mean()),
                "bbox": (int(rows.min()), int(cols.min()),
                         int(rows.max()), int(cols.max())),
            })
        return objects

    def lift_train_pairs(
        self, train_pairs: List[Tuple[np.ndarray, np.ndarray]]
    ) -> List[Tuple[np.ndarray, np.ndarray]]:
        """Lift train pairs by extracting the canonical half."""
        lifted = []
        for inp, out in train_pairs:
            axis = self._detect_axis(inp)
            if axis is None:
                lifted.append((inp, out))
                continue
            h, w = inp.shape
            oh, ow = out.shape
            if axis == "horizontal":
                half_in = inp[:h // 2, :].copy()
                half_out = out[:oh // 2, :].copy()
            else:
                half_in = inp[:, :w // 2].copy()
                half_out = out[:, :ow // 2].copy()
            lifted.append((half_in, half_out))
        return lifted

    def project(
        self, adapted_output: np.ndarray, original_grid: np.ndarray
    ) -> np.ndarray:
        """Mirror the half-grid back to full size."""
        parsed = self.parse(original_grid)
        if not parsed.get("has_symmetry"):
            return adapted_output
        axis = parsed["axis"]
        h, w = original_grid.shape
        result = np.zeros((h, w), dtype=original_grid.dtype)
        if axis == "horizontal":
            half_h = h // 2
            if adapted_output.shape[0] <= half_h:
                result[:half_h, :adapted_output.shape[1]] = adapted_output
                result[h - half_h:, :adapted_output.shape[1]] = adapted_output[::-1, :]
            else:
                return adapted_output
        else:
            half_w = w // 2
            if adapted_output.shape[1] <= half_w:
                result[:adapted_output.shape[0], :half_w] = adapted_output
                result[:adapted_output.shape[0], w - half_w:] = adapted_output[:, ::-1]
            else:
                return adapted_output
        return result

    def _detect_axis(self, grid: np.ndarray) -> Optional[str]:
        """Detect horizontal or vertical reflection symmetry."""
        h, w = grid.shape
        # Check horizontal symmetry (top-bottom mirror)
        if h >= 2 and np.array_equal(grid[:h // 2, :], grid[-(h // 2):, :][::-1, :]):
            return "horizontal"
        # Check vertical symmetry (left-right mirror)
        if w >= 2 and np.array_equal(grid[:, :w // 2], grid[:, -(w // 2):][:, ::-1]):
            return "vertical"
        return None

    def signature(self) -> Dict[str, Any]:
        return {"adapter_type": self.adapter_type}


# ============================================================================
# RepeatedMotifAdapter
# ============================================================================

class RepeatedMotifAdapter(ViewAdapter):
    """Detects repeated patterns/tiles and works on the base motif.

    Why this matters: when a grid is composed of repeated tiles, the
    default parser extracts each tile's objects separately. Operating on
    the base motif and tiling the result is more efficient and can reveal
    the transformation rule.
    """

    adapter_type = "repeated_motif"

    def can_apply(self, grid: np.ndarray) -> bool:
        """Check if grid has a repeated motif."""
        return self._detect_motif(grid) is not None

    def parse(self, grid: np.ndarray) -> Dict[str, Any]:
        """Parse grid, detecting repeated motif."""
        result = self._detect_motif(grid)
        if result is None:
            return {"has_motif": False}
        motif, tile_h, tile_w, n_rows, n_cols = result
        return {
            "has_motif": True,
            "motif": motif,
            "tile_h": tile_h,
            "tile_w": tile_w,
            "n_rows": n_rows,
            "n_cols": n_cols,
            "original_shape": grid.shape,
        }

    def extract_interior_objects(self, grid: np.ndarray) -> List[Dict]:
        """Extract objects from the base motif."""
        parsed = self.parse(grid)
        if not parsed.get("has_motif"):
            return []
        motif = parsed["motif"]
        labeled, n = ndimage.label(motif != 0)
        objects = []
        for lab in range(1, n + 1):
            mask = labeled == lab
            rows, cols = np.where(mask)
            if len(rows) == 0:
                continue
            objects.append({
                "label": lab,
                "mask": mask,
                "area": int(mask.sum()),
                "primary_color": int(motif[mask].flat[0]),
                "center_r": float(rows.mean()),
                "center_c": float(cols.mean()),
                "bbox": (int(rows.min()), int(cols.min()),
                         int(rows.max()), int(cols.max())),
            })
        return objects

    def lift_train_pairs(
        self, train_pairs: List[Tuple[np.ndarray, np.ndarray]]
    ) -> List[Tuple[np.ndarray, np.ndarray]]:
        """Lift train pairs by extracting the base motif."""
        lifted = []
        for inp, out in train_pairs:
            inp_result = self._detect_motif(inp)
            out_result = self._detect_motif(out)
            if inp_result is not None and out_result is not None:
                lifted.append((inp_result[0], out_result[0]))
            elif inp_result is not None:
                lifted.append((inp_result[0], out))
            else:
                lifted.append((inp, out))
        return lifted

    def project(
        self, adapted_output: np.ndarray, original_grid: np.ndarray
    ) -> np.ndarray:
        """Tile the motif back to full grid size."""
        parsed = self.parse(original_grid)
        if not parsed.get("has_motif"):
            return adapted_output
        tile_h = parsed["tile_h"]
        tile_w = parsed["tile_w"]
        n_rows = parsed["n_rows"]
        n_cols = parsed["n_cols"]
        h, w = original_grid.shape
        result = np.zeros((h, w), dtype=original_grid.dtype)
        for tr in range(n_rows):
            for tc in range(n_cols):
                r_start = tr * tile_h
                c_start = tc * tile_w
                r_end = min(r_start + tile_h, h)
                c_end = min(c_start + tile_w, w)
                mh = r_end - r_start
                mw = c_end - c_start
                result[r_start:r_end, c_start:c_end] = adapted_output[:mh, :mw]
        return result

    def _detect_motif(
        self, grid: np.ndarray
    ) -> Optional[Tuple[np.ndarray, int, int, int, int]]:
        """Detect a repeated motif (tiling) in the grid.

        Returns (motif, tile_h, tile_w, n_rows, n_cols) or None.
        """
        h, w = grid.shape
        # Try divisors of h and w
        for th in range(1, h // 2 + 1):
            if h % th != 0:
                continue
            for tw in range(1, w // 2 + 1):
                if w % tw != 0:
                    continue
                n_rows = h // th
                n_cols = w // tw
                if n_rows * n_cols < 2:
                    continue
                motif = grid[:th, :tw]
                is_tiled = True
                for tr in range(n_rows):
                    for tc in range(n_cols):
                        tile = grid[tr * th:(tr + 1) * th,
                                    tc * tw:(tc + 1) * tw]
                        if not np.array_equal(tile, motif):
                            is_tiled = False
                            break
                    if not is_tiled:
                        break
                if is_tiled:
                    return motif, th, tw, n_rows, n_cols
        return None

    def signature(self) -> Dict[str, Any]:
        return {"adapter_type": self.adapter_type}


# ============================================================================
# Registry
# ============================================================================

ALL_VIEW_ADAPTERS = [
    FrameInteriorAdapter,
    ColorLayerAdapter,
    ObjectInObjectAdapter,
    SymmetryAxisAdapter,
    RepeatedMotifAdapter,
]


def get_applicable_adapters(grid: np.ndarray) -> List[ViewAdapter]:
    """Return all adapters that can apply to the given grid."""
    applicable = []
    for adapter_cls in ALL_VIEW_ADAPTERS:
        try:
            adapter = adapter_cls()
            if adapter.can_apply(grid):
                applicable.append(adapter)
        except Exception:
            continue
    return applicable
