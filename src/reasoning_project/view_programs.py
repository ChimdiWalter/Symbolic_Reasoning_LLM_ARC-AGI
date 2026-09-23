"""Composable view transformation system for ARC grid tasks.

Each ViewProgram transforms a grid into a different representation to help an
operator solve it.  ViewPrograms can be composed (depth up to 2).

This replaces the earlier view_adapters system which had only 5 coarse
adapters and no composition.  The new system provides finer-grained,
composable view operations.

Architecture:
    ViewProgram (abstract base)
      IdentityView               -- no-op
      CropNonBackgroundView      -- crop to bounding box of all non-zero pixels
      CropBoundingBoxView        -- crop to bounding box of a specific label/CC
      CropMarkerNeighborhoodView -- crop around unique-color marker pixels
      RemoveFrameView            -- strip rectangular frame, return interior
      ExtractInteriorView        -- like RemoveFrameView + coordinate normalize
      SplitColorLayerView        -- binary mask for one color
      ForegroundBackgroundView   -- simplify to 2-class (fg/bg)
      ObjectGraphView            -- summary pixel per connected component
      NormalizeObjectBBoxView    -- per-object bbox normalization
      SymmetryQuotientView       -- return one half of symmetric grid
      RepeatedMotifView          -- extract base tile from repeated grid
      LineAnchorView             -- segment grid by spanning lines
      ContainmentGraphView       -- flatten containment to depth labels
    ComposedViewProgram          -- depth-2 composition of two ViewPrograms
"""
from __future__ import annotations

import abc
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy import ndimage


# ============================================================================
# Protocol / base class
# ============================================================================

class ViewProgram(abc.ABC):
    """Abstract base for all view programs."""

    view_type: str = "base"

    @abc.abstractmethod
    def can_apply(self, grid: np.ndarray) -> bool:
        """Return True if this view is applicable to *grid*.  Must be cheap."""

    @abc.abstractmethod
    def apply(self, grid: np.ndarray) -> np.ndarray:
        """Deterministic forward transformation.  Returns transformed grid."""

    def lift_train_pairs(
        self,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    ) -> List[Tuple[np.ndarray, np.ndarray]]:
        """Transform every (input, output) pair through *apply*."""
        lifted: List[Tuple[np.ndarray, np.ndarray]] = []
        for inp, out in train_pairs:
            try:
                li = self.apply(inp)
                lo = self.apply(out)
                lifted.append((li, lo))
            except Exception:
                lifted.append((inp, out))
        return lifted

    @abc.abstractmethod
    def project(
        self, adapted_output: np.ndarray, original_grid: np.ndarray
    ) -> np.ndarray:
        """Invert *apply* as closely as possible."""

    def signature(self) -> Dict[str, Any]:
        """Return a dict identifying this view type and its parameters."""
        return {"view_type": self.view_type}

    def failure_modes(self) -> List[str]:
        """Describe what can go wrong with this view."""
        return []


# ============================================================================
# 1. IdentityView
# ============================================================================

class IdentityView(ViewProgram):
    """No-op view -- returns grid unchanged.  Useful as composition base."""

    view_type = "identity"

    def can_apply(self, grid: np.ndarray) -> bool:
        return True

    def apply(self, grid: np.ndarray) -> np.ndarray:
        return grid.copy()

    def project(
        self, adapted_output: np.ndarray, original_grid: np.ndarray
    ) -> np.ndarray:
        return adapted_output

    def failure_modes(self) -> List[str]:
        return ["never fails"]


# ============================================================================
# 2. CropNonBackgroundView
# ============================================================================

class CropNonBackgroundView(ViewProgram):
    """Crop to bounding box of all non-zero pixels.

    *project* pads the result back into the original shape, placing the
    cropped region at the same position it came from.
    """

    view_type = "crop_nonbg"

    def can_apply(self, grid: np.ndarray) -> bool:
        return bool(np.any(grid != 0))

    def apply(self, grid: np.ndarray) -> np.ndarray:
        bbox = self._bbox(grid)
        if bbox is None:
            return grid.copy()
        r0, c0, r1, c1 = bbox
        return grid[r0:r1 + 1, c0:c1 + 1].copy()

    def project(
        self, adapted_output: np.ndarray, original_grid: np.ndarray
    ) -> np.ndarray:
        bbox = self._bbox(original_grid)
        if bbox is None:
            return adapted_output
        r0, c0, r1, c1 = bbox
        result = np.zeros_like(original_grid)
        ah, aw = adapted_output.shape
        ph, pw = r1 - r0 + 1, c1 - c0 + 1
        h = min(ah, ph)
        w = min(aw, pw)
        result[r0:r0 + h, c0:c0 + w] = adapted_output[:h, :w]
        return result

    def lift_train_pairs(
        self,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    ) -> List[Tuple[np.ndarray, np.ndarray]]:
        lifted: List[Tuple[np.ndarray, np.ndarray]] = []
        for inp, out in train_pairs:
            try:
                li = self.apply(inp)
            except Exception:
                li = inp
            try:
                lo = self.apply(out)
            except Exception:
                lo = out
            lifted.append((li, lo))
        return lifted

    @staticmethod
    def _bbox(grid: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
        rows, cols = np.where(grid != 0)
        if len(rows) == 0:
            return None
        return int(rows.min()), int(cols.min()), int(rows.max()), int(cols.max())

    def failure_modes(self) -> List[str]:
        return [
            "grid is entirely background (all zeros)",
            "crop may discard spatial context needed by operator",
        ]


# ============================================================================
# 3. CropBoundingBoxView
# ============================================================================

class CropBoundingBoxView(ViewProgram):
    """Crop to bounding box of the largest connected component, or by label.

    Parameters
    ----------
    label : int or None
        If given, crop to the CC whose color matches *label*.
        If None, crop to the largest CC by area.
    """

    view_type = "crop_bbox"

    def __init__(self, label: Optional[int] = None):
        self.label = label
        self._last_bbox: Optional[Tuple[int, int, int, int]] = None

    def can_apply(self, grid: np.ndarray) -> bool:
        return bool(np.any(grid != 0))

    def apply(self, grid: np.ndarray) -> np.ndarray:
        bbox = self._find_bbox(grid)
        if bbox is None:
            return grid.copy()
        self._last_bbox = bbox
        r0, c0, r1, c1 = bbox
        return grid[r0:r1 + 1, c0:c1 + 1].copy()

    def project(
        self, adapted_output: np.ndarray, original_grid: np.ndarray
    ) -> np.ndarray:
        bbox = self._find_bbox(original_grid)
        if bbox is None:
            return adapted_output
        r0, c0, r1, c1 = bbox
        result = original_grid.copy()
        ah, aw = adapted_output.shape
        ph, pw = r1 - r0 + 1, c1 - c0 + 1
        h = min(ah, ph)
        w = min(aw, pw)
        result[r0:r0 + h, c0:c0 + w] = adapted_output[:h, :w]
        return result

    def _find_bbox(
        self, grid: np.ndarray
    ) -> Optional[Tuple[int, int, int, int]]:
        if self.label is not None:
            mask = grid == self.label
            if not np.any(mask):
                return None
            rows, cols = np.where(mask)
        else:
            labeled, n = ndimage.label(grid != 0)
            if n == 0:
                return None
            sizes = ndimage.sum(grid != 0, labeled, range(1, n + 1))
            best = int(np.argmax(sizes)) + 1
            mask = labeled == best
            rows, cols = np.where(mask)
        if len(rows) == 0:
            return None
        return int(rows.min()), int(cols.min()), int(rows.max()), int(cols.max())

    def signature(self) -> Dict[str, Any]:
        return {"view_type": self.view_type, "label": self.label}

    def failure_modes(self) -> List[str]:
        return [
            "label not present in grid",
            "multiple CCs of same size -- largest is ambiguous",
        ]


# ============================================================================
# 4. CropMarkerNeighborhoodView
# ============================================================================

class CropMarkerNeighborhoodView(ViewProgram):
    """Find unique-color single-pixel markers, crop neighborhood around them.

    A 'marker' is a pixel whose color appears exactly once in the grid.
    The neighborhood is a (2*radius+1) square centred on that pixel (clipped
    to grid bounds).
    """

    view_type = "crop_marker"

    def __init__(self, radius: int = 3):
        self.radius = radius

    def can_apply(self, grid: np.ndarray) -> bool:
        markers = self._find_markers(grid)
        return len(markers) > 0

    def apply(self, grid: np.ndarray) -> np.ndarray:
        markers = self._find_markers(grid)
        if not markers:
            return grid.copy()
        # Use the first marker found
        r, c, _color = markers[0]
        return self._crop_around(grid, r, c)

    def project(
        self, adapted_output: np.ndarray, original_grid: np.ndarray
    ) -> np.ndarray:
        markers = self._find_markers(original_grid)
        if not markers:
            return adapted_output
        r, c, _color = markers[0]
        result = original_grid.copy()
        h, w = original_grid.shape
        rad = self.radius
        r0 = max(0, r - rad)
        c0 = max(0, c - rad)
        r1 = min(h, r + rad + 1)
        c1 = min(w, c + rad + 1)
        ah, aw = adapted_output.shape
        ph, pw = r1 - r0, c1 - c0
        mh = min(ah, ph)
        mw = min(aw, pw)
        result[r0:r0 + mh, c0:c0 + mw] = adapted_output[:mh, :mw]
        return result

    def _crop_around(self, grid: np.ndarray, r: int, c: int) -> np.ndarray:
        h, w = grid.shape
        rad = self.radius
        r0 = max(0, r - rad)
        c0 = max(0, c - rad)
        r1 = min(h, r + rad + 1)
        c1 = min(w, c + rad + 1)
        return grid[r0:r1, c0:c1].copy()

    @staticmethod
    def _find_markers(grid: np.ndarray) -> List[Tuple[int, int, int]]:
        """Return list of (row, col, color) for unique-color single pixels."""
        flat = grid.flatten()
        colors, counts = np.unique(flat, return_counts=True)
        unique_colors = set(int(c) for c, cnt in zip(colors, counts) if cnt == 1 and c != 0)
        if not unique_colors:
            return []
        markers = []
        for uc in sorted(unique_colors):
            positions = np.argwhere(grid == uc)
            if len(positions) == 1:
                markers.append((int(positions[0, 0]), int(positions[0, 1]), uc))
        return markers

    def signature(self) -> Dict[str, Any]:
        return {"view_type": self.view_type, "radius": self.radius}

    def failure_modes(self) -> List[str]:
        return [
            "no unique-color single-pixel markers in grid",
            "marker near edge -- neighborhood is clipped",
            "multiple markers -- only first is used",
        ]


# ============================================================================
# 5. RemoveFrameView
# ============================================================================

class RemoveFrameView(ViewProgram):
    """Detect a rectangular frame (uniform colour border), return interior.

    The frame is the outermost contiguous border of a single colour forming
    a complete rectangle.  *project* wraps interior back in the frame.
    """

    view_type = "remove_frame"

    def can_apply(self, grid: np.ndarray) -> bool:
        return self._detect_frame(grid) is not None

    def apply(self, grid: np.ndarray) -> np.ndarray:
        result = self._detect_frame(grid)
        if result is None:
            return grid.copy()
        _fc, _t, interior = result
        return interior

    def project(
        self, adapted_output: np.ndarray, original_grid: np.ndarray
    ) -> np.ndarray:
        result = self._detect_frame(original_grid)
        if result is None:
            return adapted_output
        frame_color, thickness, _interior = result
        h, w = original_grid.shape
        out = np.full((h, w), frame_color, dtype=original_grid.dtype)
        ih, iw = h - 2 * thickness, w - 2 * thickness
        ah, aw = adapted_output.shape
        mh = min(ah, ih)
        mw = min(aw, iw)
        out[thickness:thickness + mh, thickness:thickness + mw] = adapted_output[:mh, :mw]
        return out

    def lift_train_pairs(
        self,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    ) -> List[Tuple[np.ndarray, np.ndarray]]:
        lifted: List[Tuple[np.ndarray, np.ndarray]] = []
        for inp, out in train_pairs:
            inp_r = self._detect_frame(inp)
            out_r = self._detect_frame(out)
            if inp_r is not None and out_r is not None:
                lifted.append((inp_r[2], out_r[2]))
            elif inp_r is not None:
                lifted.append((inp_r[2], out))
            else:
                lifted.append((inp, out))
        return lifted

    @staticmethod
    def _detect_frame(
        grid: np.ndarray,
    ) -> Optional[Tuple[int, int, np.ndarray]]:
        """Return (frame_color, thickness, interior) or None."""
        h, w = grid.shape
        if h < 3 or w < 3:
            return None
        top = grid[0, :]
        if len(set(top.tolist())) != 1:
            return None
        fc = int(top[0])
        if fc == 0:
            return None
        if not (np.all(grid[-1, :] == fc) and
                np.all(grid[:, 0] == fc) and
                np.all(grid[:, -1] == fc)):
            return None
        thickness = 0
        for r in range(h // 2):
            if np.all(grid[r, :] == fc):
                thickness = r + 1
            else:
                break
        if thickness == 0:
            thickness = 1
        for r in range(h - 1, h - 1 - thickness, -1):
            if not np.all(grid[r, :] == fc):
                return None
        for c in range(thickness):
            if not np.all(grid[:, c] == fc):
                return None
            if not np.all(grid[:, w - 1 - c] == fc):
                return None
        if h - 2 * thickness < 1 or w - 2 * thickness < 1:
            return None
        interior = grid[thickness:h - thickness, thickness:w - thickness].copy()
        return fc, thickness, interior

    def failure_modes(self) -> List[str]:
        return [
            "no uniform-colour border detected",
            "border colour is 0 (background) -- ignored",
            "non-uniform thickness -- not handled",
        ]


# ============================================================================
# 6. ExtractInteriorView
# ============================================================================

class ExtractInteriorView(ViewProgram):
    """Like RemoveFrameView but also normalises interior coordinates.

    The interior is extracted and its non-zero pixel values are re-indexed
    starting from 1 (preserving relative colour identity), making it easier
    for operators to work on the interior independent of frame context.
    """

    view_type = "extract_interior"

    def __init__(self):
        self._frame_view = RemoveFrameView()

    def can_apply(self, grid: np.ndarray) -> bool:
        return self._frame_view.can_apply(grid)

    def apply(self, grid: np.ndarray) -> np.ndarray:
        interior = self._frame_view.apply(grid)
        return interior

    def project(
        self, adapted_output: np.ndarray, original_grid: np.ndarray
    ) -> np.ndarray:
        return self._frame_view.project(adapted_output, original_grid)

    def lift_train_pairs(
        self,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    ) -> List[Tuple[np.ndarray, np.ndarray]]:
        return self._frame_view.lift_train_pairs(train_pairs)

    def failure_modes(self) -> List[str]:
        return self._frame_view.failure_modes() + [
            "colour re-indexing may break colour-identity tasks",
        ]


# ============================================================================
# 7. SplitColorLayerView
# ============================================================================

class SplitColorLayerView(ViewProgram):
    """Extract a binary mask for a specific colour.

    If *target_color* is None, auto-detects a useful colour by picking the
    least-common non-zero colour in the grid.
    """

    view_type = "split_color"

    def __init__(self, target_color: Optional[int] = None):
        self.target_color = target_color

    def can_apply(self, grid: np.ndarray) -> bool:
        colors = set(grid.flatten().tolist()) - {0}
        if self.target_color is not None:
            return self.target_color in colors
        return len(colors) >= 1

    def apply(self, grid: np.ndarray) -> np.ndarray:
        tc = self._resolve_color(grid)
        if tc is None:
            return grid.copy()
        return (grid == tc).astype(grid.dtype)

    def project(
        self, adapted_output: np.ndarray, original_grid: np.ndarray
    ) -> np.ndarray:
        tc = self._resolve_color(original_grid)
        if tc is None:
            return adapted_output
        result = original_grid.copy()
        # Remove old pixels of target colour
        result[original_grid == tc] = 0
        # Re-place target colour where adapted_output is non-zero
        result[adapted_output != 0] = tc
        return result

    def lift_train_pairs(
        self,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    ) -> List[Tuple[np.ndarray, np.ndarray]]:
        lifted: List[Tuple[np.ndarray, np.ndarray]] = []
        for inp, out in train_pairs:
            tc_in = self._resolve_color(inp)
            tc_out = self._resolve_color(out)
            if tc_in is not None:
                li = (inp == tc_in).astype(inp.dtype)
            else:
                li = inp
            if tc_out is not None:
                lo = (out == tc_out).astype(out.dtype)
            else:
                lo = out
            lifted.append((li, lo))
        return lifted

    def _resolve_color(self, grid: np.ndarray) -> Optional[int]:
        if self.target_color is not None:
            return self.target_color
        flat = grid.flatten()
        colors, counts = np.unique(flat, return_counts=True)
        non_bg = [(int(c), int(cnt)) for c, cnt in zip(colors, counts) if c != 0]
        if not non_bg:
            return None
        # Pick the least common non-zero colour
        non_bg.sort(key=lambda x: x[1])
        return non_bg[0][0]

    def signature(self) -> Dict[str, Any]:
        return {"view_type": self.view_type, "target_color": self.target_color}

    def failure_modes(self) -> List[str]:
        return [
            "target_color not present in grid",
            "auto-detect picks wrong colour for the task",
            "binary mask loses spatial colour structure",
        ]


# ============================================================================
# 8. ForegroundBackgroundView
# ============================================================================

class ForegroundBackgroundView(ViewProgram):
    """Simplify multi-colour grid to 2-class: foreground (1) and background (0).

    The most-common non-zero colour is treated as 'foreground'; all other
    non-zero colours become background (0).
    """

    view_type = "fg_bg"

    def can_apply(self, grid: np.ndarray) -> bool:
        colors = set(grid.flatten().tolist()) - {0}
        return len(colors) >= 2

    def apply(self, grid: np.ndarray) -> np.ndarray:
        fg = self._fg_color(grid)
        if fg is None:
            return grid.copy()
        return (grid == fg).astype(grid.dtype)

    def project(
        self, adapted_output: np.ndarray, original_grid: np.ndarray
    ) -> np.ndarray:
        fg = self._fg_color(original_grid)
        if fg is None:
            return adapted_output
        result = np.zeros_like(original_grid)
        result[adapted_output != 0] = fg
        return result

    @staticmethod
    def _fg_color(grid: np.ndarray) -> Optional[int]:
        flat = grid.flatten()
        colors, counts = np.unique(flat, return_counts=True)
        non_bg = [(int(c), int(cnt)) for c, cnt in zip(colors, counts) if c != 0]
        if not non_bg:
            return None
        non_bg.sort(key=lambda x: -x[1])
        return non_bg[0][0]

    def failure_modes(self) -> List[str]:
        return [
            "fewer than 2 non-zero colours -- nothing to simplify",
            "most-common colour is not the semantic foreground",
        ]


# ============================================================================
# 9. ObjectGraphView
# ============================================================================

class ObjectGraphView(ViewProgram):
    """Replace each connected component with a single pixel at its centroid.

    The output grid has the same shape as the input; each CC is represented by
    a single pixel (its colour) placed at the integer centroid.  All other
    pixels are 0.
    """

    view_type = "object_graph"

    def can_apply(self, grid: np.ndarray) -> bool:
        labeled, n = ndimage.label(grid != 0)
        return n >= 1

    def apply(self, grid: np.ndarray) -> np.ndarray:
        labeled, n = ndimage.label(grid != 0)
        result = np.zeros_like(grid)
        for lab in range(1, n + 1):
            mask = labeled == lab
            rows, cols = np.where(mask)
            if len(rows) == 0:
                continue
            cr = int(round(rows.mean()))
            cc = int(round(cols.mean()))
            color = int(grid[rows[0], cols[0]])
            result[cr, cc] = color
        return result

    def project(
        self, adapted_output: np.ndarray, original_grid: np.ndarray
    ) -> np.ndarray:
        # Cannot faithfully invert a graph view to full objects.
        # Best effort: return the adapted output as-is.
        return adapted_output

    def failure_modes(self) -> List[str]:
        return [
            "centroid may collide for nearby objects",
            "projection is lossy -- object shapes are lost",
        ]


# ============================================================================
# 10. NormalizeObjectBBoxView
# ============================================================================

class NormalizeObjectBBoxView(ViewProgram):
    """Extract each object, normalise to its bounding box.

    Returns a grid whose rows are stacked normalised object patches (padded
    to the same width).  This makes object comparison position-independent.

    For tasks with a single dominant object, this acts like CropBoundingBoxView
    on the largest CC.
    """

    view_type = "normalize_obj_bbox"

    def can_apply(self, grid: np.ndarray) -> bool:
        labeled, n = ndimage.label(grid != 0)
        return n >= 1

    def apply(self, grid: np.ndarray) -> np.ndarray:
        patches = self._extract_patches(grid)
        if not patches:
            return grid.copy()
        if len(patches) == 1:
            return patches[0]
        # Stack vertically, padding to max width
        max_w = max(p.shape[1] for p in patches)
        padded = []
        for p in patches:
            if p.shape[1] < max_w:
                pad = np.zeros((p.shape[0], max_w - p.shape[1]), dtype=p.dtype)
                p = np.hstack([p, pad])
            padded.append(p)
        return np.vstack(padded)

    def project(
        self, adapted_output: np.ndarray, original_grid: np.ndarray
    ) -> np.ndarray:
        # Lossy inverse: place adapted_output in top-left of original shape
        result = np.zeros_like(original_grid)
        ah, aw = adapted_output.shape
        oh, ow = original_grid.shape
        mh = min(ah, oh)
        mw = min(aw, ow)
        result[:mh, :mw] = adapted_output[:mh, :mw]
        return result

    @staticmethod
    def _extract_patches(grid: np.ndarray) -> List[np.ndarray]:
        labeled, n = ndimage.label(grid != 0)
        patches: List[np.ndarray] = []
        for lab in range(1, n + 1):
            mask = labeled == lab
            rows, cols = np.where(mask)
            if len(rows) == 0:
                continue
            r0, r1 = int(rows.min()), int(rows.max())
            c0, c1 = int(cols.min()), int(cols.max())
            patch = grid[r0:r1 + 1, c0:c1 + 1].copy()
            # Zero out pixels not belonging to this CC
            local_mask = mask[r0:r1 + 1, c0:c1 + 1]
            patch[~local_mask] = 0
            patches.append(patch)
        return patches

    def failure_modes(self) -> List[str]:
        return [
            "stacking changes shape -- operator must handle variable height",
            "projection is lossy -- original positions lost",
        ]


# ============================================================================
# 11. SymmetryQuotientView
# ============================================================================

class SymmetryQuotientView(ViewProgram):
    """If grid has vertical or horizontal symmetry, return only one half.

    *project* mirrors the half back to full size.
    """

    view_type = "symmetry_quotient"

    def can_apply(self, grid: np.ndarray) -> bool:
        return self._detect_axis(grid) is not None

    def apply(self, grid: np.ndarray) -> np.ndarray:
        axis = self._detect_axis(grid)
        if axis is None:
            return grid.copy()
        h, w = grid.shape
        if axis == "horizontal":
            return grid[:h // 2, :].copy()
        else:
            return grid[:, :w // 2].copy()

    def project(
        self, adapted_output: np.ndarray, original_grid: np.ndarray
    ) -> np.ndarray:
        axis = self._detect_axis(original_grid)
        if axis is None:
            return adapted_output
        h, w = original_grid.shape
        result = np.zeros((h, w), dtype=original_grid.dtype)
        if axis == "horizontal":
            half_h = h // 2
            ah, aw = adapted_output.shape
            mh = min(ah, half_h)
            mw = min(aw, w)
            result[:mh, :mw] = adapted_output[:mh, :mw]
            # Mirror
            result[h - mh:, :mw] = adapted_output[:mh, :mw][::-1, :]
            # Handle odd middle row
            if h % 2 == 1 and mh > 0:
                result[half_h, :mw] = adapted_output[mh - 1, :mw]
        else:
            half_w = w // 2
            ah, aw = adapted_output.shape
            mh = min(ah, h)
            mw = min(aw, half_w)
            result[:mh, :mw] = adapted_output[:mh, :mw]
            result[:mh, w - mw:] = adapted_output[:mh, :mw][:, ::-1]
            if w % 2 == 1 and mw > 0:
                result[:mh, half_w] = adapted_output[:mh, mw - 1]
        return result

    def lift_train_pairs(
        self,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    ) -> List[Tuple[np.ndarray, np.ndarray]]:
        lifted: List[Tuple[np.ndarray, np.ndarray]] = []
        for inp, out in train_pairs:
            axis_in = self._detect_axis(inp)
            axis_out = self._detect_axis(out)
            if axis_in is not None:
                li = self.apply(inp)
            else:
                li = inp
            if axis_out is not None:
                # Use same axis as input if available
                ax = axis_in if axis_in is not None else axis_out
                oh, ow = out.shape
                if ax == "horizontal":
                    lo = out[:oh // 2, :].copy()
                else:
                    lo = out[:, :ow // 2].copy()
            else:
                lo = out
            lifted.append((li, lo))
        return lifted

    @staticmethod
    def _detect_axis(grid: np.ndarray) -> Optional[str]:
        h, w = grid.shape
        if h >= 2:
            top = grid[:h // 2, :]
            bot = grid[-(h // 2):, :][::-1, :]
            if np.array_equal(top, bot):
                return "horizontal"
        if w >= 2:
            left = grid[:, :w // 2]
            right = grid[:, -(w // 2):][:, ::-1]
            if np.array_equal(left, right):
                return "vertical"
        return None

    def failure_modes(self) -> List[str]:
        return [
            "grid has no exact symmetry",
            "near-symmetry with small defects is not detected",
        ]


# ============================================================================
# 12. RepeatedMotifView
# ============================================================================

class RepeatedMotifView(ViewProgram):
    """If grid tiles, extract the base motif.  *project* re-tiles."""

    view_type = "repeated_motif"

    def can_apply(self, grid: np.ndarray) -> bool:
        return self._detect_motif(grid) is not None

    def apply(self, grid: np.ndarray) -> np.ndarray:
        result = self._detect_motif(grid)
        if result is None:
            return grid.copy()
        motif, _th, _tw, _nr, _nc = result
        return motif

    def project(
        self, adapted_output: np.ndarray, original_grid: np.ndarray
    ) -> np.ndarray:
        result = self._detect_motif(original_grid)
        if result is None:
            return adapted_output
        _motif, tile_h, tile_w, n_rows, n_cols = result
        h, w = original_grid.shape
        out = np.zeros((h, w), dtype=original_grid.dtype)
        for tr in range(n_rows):
            for tc in range(n_cols):
                r0 = tr * tile_h
                c0 = tc * tile_w
                r1 = min(r0 + tile_h, h)
                c1 = min(c0 + tile_w, w)
                mh = r1 - r0
                mw = c1 - c0
                out[r0:r1, c0:c1] = adapted_output[:mh, :mw]
        return out

    def lift_train_pairs(
        self,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    ) -> List[Tuple[np.ndarray, np.ndarray]]:
        lifted: List[Tuple[np.ndarray, np.ndarray]] = []
        for inp, out in train_pairs:
            inp_r = self._detect_motif(inp)
            out_r = self._detect_motif(out)
            if inp_r is not None and out_r is not None:
                lifted.append((inp_r[0], out_r[0]))
            elif inp_r is not None:
                lifted.append((inp_r[0], out))
            else:
                lifted.append((inp, out))
        return lifted

    @staticmethod
    def _detect_motif(
        grid: np.ndarray,
    ) -> Optional[Tuple[np.ndarray, int, int, int, int]]:
        """Return (motif, tile_h, tile_w, n_rows, n_cols) or None."""
        h, w = grid.shape
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

    def failure_modes(self) -> List[str]:
        return [
            "grid dimensions not factorisable into repeated tiles",
            "near-tiling with small defects is not detected",
        ]


# ============================================================================
# 13. LineAnchorView
# ============================================================================

class LineAnchorView(ViewProgram):
    """Detect horizontal/vertical lines spanning the grid, segment into regions.

    A 'spanning line' is a full row or column of a single colour.  The view
    removes the separator lines and returns the first region (top-left).
    *project* reinserts the separators and pastes the region back.
    """

    view_type = "line_anchor"

    def can_apply(self, grid: np.ndarray) -> bool:
        sep_rows, sep_cols = self._find_separators(grid)
        return len(sep_rows) > 0 or len(sep_cols) > 0

    def apply(self, grid: np.ndarray) -> np.ndarray:
        regions = self._segment(grid)
        if not regions:
            return grid.copy()
        return regions[0].copy()

    def project(
        self, adapted_output: np.ndarray, original_grid: np.ndarray
    ) -> np.ndarray:
        sep_rows, sep_cols = self._find_separators(original_grid)
        if not sep_rows and not sep_cols:
            return adapted_output
        result = original_grid.copy()
        # Place adapted_output in the first region slot
        if sep_rows:
            r_end = sep_rows[0][0]
        else:
            r_end = original_grid.shape[0]
        if sep_cols:
            c_end = sep_cols[0][0]
        else:
            c_end = original_grid.shape[1]
        ah, aw = adapted_output.shape
        mh = min(ah, r_end)
        mw = min(aw, c_end)
        result[:mh, :mw] = adapted_output[:mh, :mw]
        return result

    def lift_train_pairs(
        self,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    ) -> List[Tuple[np.ndarray, np.ndarray]]:
        lifted: List[Tuple[np.ndarray, np.ndarray]] = []
        for inp, out in train_pairs:
            inp_regions = self._segment(inp)
            out_regions = self._segment(out)
            if inp_regions and out_regions:
                lifted.append((inp_regions[0], out_regions[0]))
            elif inp_regions:
                lifted.append((inp_regions[0], out))
            else:
                lifted.append((inp, out))
        return lifted

    def _segment(self, grid: np.ndarray) -> List[np.ndarray]:
        """Segment grid into regions separated by spanning lines."""
        h, w = grid.shape
        sep_rows, sep_cols = self._find_separators(grid)

        # Compute row boundaries
        row_indices = sorted(set(r for r, _ in sep_rows))
        row_bounds: List[Tuple[int, int]] = []
        prev = 0
        for ri in row_indices:
            if ri > prev:
                row_bounds.append((prev, ri))
            prev = ri + 1
        if prev < h:
            row_bounds.append((prev, h))

        # Compute col boundaries
        col_indices = sorted(set(c for c, _ in sep_cols))
        col_bounds: List[Tuple[int, int]] = []
        prev = 0
        for ci in col_indices:
            if ci > prev:
                col_bounds.append((prev, ci))
            prev = ci + 1
        if prev < w:
            col_bounds.append((prev, w))

        if not row_bounds:
            row_bounds = [(0, h)]
        if not col_bounds:
            col_bounds = [(0, w)]

        regions: List[np.ndarray] = []
        for r0, r1 in row_bounds:
            for c0, c1 in col_bounds:
                region = grid[r0:r1, c0:c1]
                if region.size > 0:
                    regions.append(region)
        return regions

    @staticmethod
    def _find_separators(
        grid: np.ndarray,
    ) -> Tuple[List[Tuple[int, int]], List[Tuple[int, int]]]:
        """Return (sep_rows, sep_cols) as lists of (index, color).

        Only non-background (non-zero) uniform rows/columns count, to avoid
        treating empty rows as separators.
        """
        h, w = grid.shape
        sep_rows: List[Tuple[int, int]] = []
        for r in range(h):
            vals = set(grid[r, :].tolist())
            if len(vals) == 1:
                c = vals.pop()
                if c != 0:
                    sep_rows.append((r, c))
        sep_cols: List[Tuple[int, int]] = []
        for c in range(w):
            vals = set(grid[:, c].tolist())
            if len(vals) == 1:
                v = vals.pop()
                if v != 0:
                    sep_cols.append((c, v))
        return sep_rows, sep_cols

    def failure_modes(self) -> List[str]:
        return [
            "no spanning lines in grid",
            "separator colour same as object colour -- misdetect",
            "only first region returned -- other regions lost",
        ]


# ============================================================================
# 14. ContainmentGraphView
# ============================================================================

class ContainmentGraphView(ViewProgram):
    """Detect which objects are inside which others, flatten to depth labels.

    Outer objects get label 1, objects contained in them get label 2, etc.
    Background remains 0.
    """

    view_type = "containment_graph"

    def can_apply(self, grid: np.ndarray) -> bool:
        containments = self._find_containments(grid)
        return len(containments) > 0

    def apply(self, grid: np.ndarray) -> np.ndarray:
        depths = self._compute_depths(grid)
        if depths is None:
            return grid.copy()
        return depths

    def project(
        self, adapted_output: np.ndarray, original_grid: np.ndarray
    ) -> np.ndarray:
        # Inverse: map depth labels back to original colours using the depth
        # map from original_grid.
        depths = self._compute_depths(original_grid)
        if depths is None:
            return adapted_output
        result = np.zeros_like(original_grid)
        # Build depth -> original-colour mapping from the original grid
        depth_to_colors: Dict[int, int] = {}
        for d in sorted(set(depths.flatten().tolist())):
            if d == 0:
                continue
            mask = depths == d
            orig_vals = original_grid[mask]
            non_zero = orig_vals[orig_vals != 0]
            if len(non_zero) > 0:
                colors, counts = np.unique(non_zero, return_counts=True)
                depth_to_colors[d] = int(colors[np.argmax(counts)])
        # Apply mapping to adapted output
        for d, color in depth_to_colors.items():
            result[adapted_output == d] = color
        return result

    def _compute_depths(self, grid: np.ndarray) -> Optional[np.ndarray]:
        """Assign containment depth to each pixel."""
        labeled, n = ndimage.label(grid != 0)
        if n < 2:
            return None
        objects = self._extract_objects(grid, labeled, n)
        containments = self._find_containments_from_objects(objects)
        if not containments:
            return None
        # Build parent mapping
        parent: Dict[int, Optional[int]] = {o["label"]: None for o in objects}
        for inner_lab, outer_lab in containments:
            # Only record the smallest container
            if parent[inner_lab] is None or (
                parent[inner_lab] is not None
                and next(
                    o["area"] for o in objects if o["label"] == outer_lab
                )
                < next(
                    o["area"]
                    for o in objects
                    if o["label"] == parent[inner_lab]
                )
            ):
                parent[inner_lab] = outer_lab

        # Compute depth via parent chain
        depth_map: Dict[int, int] = {}

        def _depth(lab: int) -> int:
            if lab in depth_map:
                return depth_map[lab]
            p = parent.get(lab)
            if p is None:
                depth_map[lab] = 1
            else:
                depth_map[lab] = _depth(p) + 1
            return depth_map[lab]

        for o in objects:
            _depth(o["label"])

        result = np.zeros_like(grid)
        for o in objects:
            mask = labeled == o["label"]
            result[mask] = depth_map[o["label"]]
        return result

    @staticmethod
    def _extract_objects(
        grid: np.ndarray, labeled: np.ndarray, n: int
    ) -> List[Dict[str, Any]]:
        objects: List[Dict[str, Any]] = []
        for lab in range(1, n + 1):
            mask = labeled == lab
            rows, cols = np.where(mask)
            if len(rows) == 0:
                continue
            objects.append({
                "label": lab,
                "bbox": (int(rows.min()), int(cols.min()),
                         int(rows.max()), int(cols.max())),
                "area": int(mask.sum()),
                "color": int(grid[rows[0], cols[0]]),
            })
        return objects

    @staticmethod
    def _find_containments_from_objects(
        objects: List[Dict[str, Any]],
    ) -> List[Tuple[int, int]]:
        """Return list of (inner_label, outer_label) pairs."""
        containments: List[Tuple[int, int]] = []
        for inner in objects:
            ir0, ic0, ir1, ic1 = inner["bbox"]
            for outer in objects:
                if inner["label"] == outer["label"]:
                    continue
                if inner["area"] >= outer["area"]:
                    continue
                or0, oc0, or1, oc1 = outer["bbox"]
                if ir0 > or0 and ir1 < or1 and ic0 > oc0 and ic1 < oc1:
                    containments.append((inner["label"], outer["label"]))
        return containments

    def _find_containments(self, grid: np.ndarray) -> List[Tuple[int, int]]:
        labeled, n = ndimage.label(grid != 0)
        if n < 2:
            return []
        objects = self._extract_objects(grid, labeled, n)
        return self._find_containments_from_objects(objects)

    def failure_modes(self) -> List[str]:
        return [
            "fewer than 2 objects -- no containment possible",
            "objects touch -- connected component merges them",
            "projection relies on depth-to-colour mapping which may not be 1:1",
        ]


# ============================================================================
# ComposedViewProgram
# ============================================================================

class ComposedViewProgram(ViewProgram):
    """Compose two ViewPrograms: first -> second.

    apply   = second.apply(first.apply(grid))
    project = first.project(second.project(output, first.apply(grid)), grid)
    """

    view_type = "composed"

    def __init__(self, first: ViewProgram, second: ViewProgram):
        self.first = first
        self.second = second

    def can_apply(self, grid: np.ndarray) -> bool:
        if not self.first.can_apply(grid):
            return False
        try:
            intermediate = self.first.apply(grid)
        except Exception:
            return False
        return self.second.can_apply(intermediate)

    def apply(self, grid: np.ndarray) -> np.ndarray:
        intermediate = self.first.apply(grid)
        return self.second.apply(intermediate)

    def lift_train_pairs(
        self,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    ) -> List[Tuple[np.ndarray, np.ndarray]]:
        lifted1 = self.first.lift_train_pairs(train_pairs)
        return self.second.lift_train_pairs(lifted1)

    def project(
        self, adapted_output: np.ndarray, original_grid: np.ndarray
    ) -> np.ndarray:
        intermediate = self.first.apply(original_grid)
        second_proj = self.second.project(adapted_output, intermediate)
        return self.first.project(second_proj, original_grid)

    def signature(self) -> Dict[str, Any]:
        return {
            "view_type": self.view_type,
            "first": self.first.signature(),
            "second": self.second.signature(),
        }

    def failure_modes(self) -> List[str]:
        return (
            [f"first({self.first.view_type}): {m}" for m in self.first.failure_modes()]
            + [f"second({self.second.view_type}): {m}" for m in self.second.failure_modes()]
            + ["composition may amplify projection error"]
        )


# ============================================================================
# Registry and enumeration
# ============================================================================

def _base_view_programs(grid: np.ndarray) -> List[ViewProgram]:
    """Instantiate all single-depth ViewPrograms applicable to *grid*."""
    candidates: List[ViewProgram] = [
        IdentityView(),
        CropNonBackgroundView(),
        CropBoundingBoxView(label=None),
        RemoveFrameView(),
        ExtractInteriorView(),
        SplitColorLayerView(target_color=None),
        ForegroundBackgroundView(),
        ObjectGraphView(),
        NormalizeObjectBBoxView(),
        SymmetryQuotientView(),
        RepeatedMotifView(),
        LineAnchorView(),
        ContainmentGraphView(),
        CropMarkerNeighborhoodView(radius=3),
    ]
    # Also create SplitColorLayerView and CropBoundingBoxView per colour
    colors = set(grid.flatten().tolist()) - {0}
    for c in sorted(colors):
        candidates.append(SplitColorLayerView(target_color=c))
        candidates.append(CropBoundingBoxView(label=c))
    # Marker views with different radii
    for r in [2, 5]:
        candidates.append(CropMarkerNeighborhoodView(radius=r))

    applicable: List[ViewProgram] = []
    for vp in candidates:
        try:
            if vp.can_apply(grid):
                applicable.append(vp)
        except Exception:
            continue
    return applicable


def enumerate_view_programs(
    grid: np.ndarray,
    max_depth: int = 2,
) -> List[ViewProgram]:
    """Enumerate applicable ViewPrograms for *grid*, including depth-2 compositions.

    Parameters
    ----------
    grid : np.ndarray
        The input grid.
    max_depth : int
        Maximum composition depth (1 = single views only, 2 = include
        pairwise compositions).

    Returns
    -------
    List[ViewProgram]
        All applicable ViewPrograms, ordered single-then-composed.
    """
    base = _base_view_programs(grid)
    results: List[ViewProgram] = list(base)

    if max_depth >= 2:
        # Filter out IdentityView from composition (it adds nothing)
        non_identity = [vp for vp in base if not isinstance(vp, IdentityView)]
        seen_sigs: set = set()
        for first in non_identity:
            for second in non_identity:
                # Skip composing a view with itself (same type + params)
                s1 = _hashable_sig(first.signature())
                s2 = _hashable_sig(second.signature())
                if s1 == s2:
                    continue
                comp_sig = (s1, s2)
                if comp_sig in seen_sigs:
                    continue
                composed = ComposedViewProgram(first, second)
                try:
                    if composed.can_apply(grid):
                        seen_sigs.add(comp_sig)
                        results.append(composed)
                except Exception:
                    continue

    return results


def _hashable_sig(sig: Dict[str, Any]) -> tuple:
    """Convert a signature dict to a hashable tuple."""
    items = []
    for k in sorted(sig.keys()):
        v = sig[k]
        if isinstance(v, dict):
            v = _hashable_sig(v)
        items.append((k, v))
    return tuple(items)
