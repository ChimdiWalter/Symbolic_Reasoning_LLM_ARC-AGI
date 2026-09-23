"""Object-Spatial Reasoning Engine with Gestalt Perception.

A reasoning system that perceives grid patterns as meaningful shapes,
computes spatial relationships between objects, and generates hypotheses
about WHY specific cells change — based on their spatial relationship
to perceived objects.

This is NOT template matching. The system:
  1. PERCEIVES: extracts objects, recognizes gestalt shapes (arrows,
     crosses, figures, lines), computes spatial relationships
  2. REASONS: generates hypotheses about fill/recolor rules based on
     spatial relationships (containment, adjacency, direction, alignment)
  3. VERIFIES: tests each hypothesis against ALL training pairs
  4. REMEMBERS: stores successful (spatial_pattern → strategy) pairs
     for transfer to structurally similar tasks

Gestalt perception is novel for ARC: recognizing that a cluster of cells
forms an "arrow pointing right" and using that to infer fill direction.
"""
from __future__ import annotations

import uuid
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import numpy as np
from scipy.ndimage import label as ndlabel

from reasoning_project.operator_genesis import SynthesizedOperator


# ===================================================================
# LAYER 1: Object Extraction
# ===================================================================

@dataclass
class GridObject:
    """A perceived object in the grid."""
    obj_id: int
    color: int
    mask: np.ndarray
    pixels: List[Tuple[int, int]]
    bbox: Tuple[int, int, int, int]  # r_min, r_max, c_min, c_max
    area: int
    centroid: Tuple[float, float]
    # Gestalt properties (computed lazily)
    gestalt: Optional[Dict[str, Any]] = None
    spatial_rels: Optional[Dict[str, Any]] = None


def _extract_objects(grid: np.ndarray, bg: int = 0) -> List[GridObject]:
    """Extract connected components as objects."""
    objects = []
    obj_id = 0
    for color in sorted(set(grid.flat)):
        if color == bg:
            continue
        color_mask = grid == color
        labeled, n = ndlabel(color_mask)
        for comp_id in range(1, n + 1):
            mask = labeled == comp_id
            pixels = list(zip(*np.where(mask)))
            if not pixels:
                continue
            rows, cols = zip(*pixels)
            r_min, r_max = min(rows), max(rows)
            c_min, c_max = min(cols), max(cols)
            centroid = (np.mean(rows), np.mean(cols))
            objects.append(GridObject(
                obj_id=obj_id,
                color=int(color),
                mask=mask,
                pixels=pixels,
                bbox=(r_min, r_max, c_min, c_max),
                area=len(pixels),
                centroid=centroid,
            ))
            obj_id += 1
    return objects


def _extract_bg_regions(grid: np.ndarray, bg: int = 0) -> List[GridObject]:
    """Extract connected background regions."""
    bg_mask = grid == bg
    labeled, n = ndlabel(bg_mask)
    regions = []
    for comp_id in range(1, n + 1):
        mask = labeled == comp_id
        pixels = list(zip(*np.where(mask)))
        if not pixels:
            continue
        rows, cols = zip(*pixels)
        r_min, r_max = min(rows), max(rows)
        c_min, c_max = min(cols), max(cols)
        centroid = (np.mean(rows), np.mean(cols))
        regions.append(GridObject(
            obj_id=comp_id + 1000,
            color=bg,
            mask=mask,
            pixels=pixels,
            bbox=(r_min, r_max, c_min, c_max),
            area=len(pixels),
            centroid=centroid,
        ))
    return regions


# ===================================================================
# LAYER 2: Gestalt Perception
# Recognize shapes as meaningful: arrow, cross, line, L, T, figure
# ===================================================================

def _compute_gestalt(obj: GridObject, grid: np.ndarray) -> Dict[str, Any]:
    """Perceive the gestalt (shape meaning) of an object."""
    g: Dict[str, Any] = {}
    r_min, r_max, c_min, c_max = obj.bbox
    h = r_max - r_min + 1
    w = c_max - c_min + 1

    # Basic shape properties
    g["height"] = h
    g["width"] = w
    g["aspect_ratio"] = h / max(w, 1)
    g["fill_ratio"] = obj.area / max(h * w, 1)
    g["is_single_pixel"] = obj.area == 1
    g["is_line_h"] = h == 1 and w > 1
    g["is_line_v"] = w == 1 and h > 1
    g["is_line"] = g["is_line_h"] or g["is_line_v"]
    g["is_square"] = h == w and h > 1
    g["is_rectangle"] = h != w and h > 1 and w > 1
    g["is_filled_rect"] = g["fill_ratio"] > 0.95

    # Extract local bitmask for shape analysis
    bitmask = obj.mask[r_min:r_max + 1, c_min:c_max + 1].astype(int)

    # Symmetry detection
    g["symmetric_h"] = np.array_equal(bitmask, bitmask[:, ::-1])
    g["symmetric_v"] = np.array_equal(bitmask, bitmask[::-1, :])
    g["symmetric_both"] = g["symmetric_h"] and g["symmetric_v"]

    # Arrow detection: does this shape point in a direction?
    g["arrow_direction"] = _detect_arrow(bitmask)

    # Cross/plus detection
    g["is_cross"] = _detect_cross(bitmask)

    # L-shape detection
    g["is_L"] = _detect_L(bitmask)

    # T-shape detection
    g["is_T"] = _detect_T(bitmask)

    # Figure detection: does this look like it has distinct parts
    # (head, body, limbs) — a figurative/anthropomorphic shape?
    g["is_figure"] = _detect_figure(bitmask)
    g["figure_orientation"] = _detect_figure_orientation(bitmask)

    # Convexity: is the shape convex (no holes, no concavities)?
    g["is_convex"] = g["fill_ratio"] > 0.9

    # Holes: does the object have internal holes?
    g["has_holes"] = _detect_holes(bitmask)

    # Border touching
    H, W = grid.shape
    g["touches_top"] = r_min == 0
    g["touches_bottom"] = r_max == H - 1
    g["touches_left"] = c_min == 0
    g["touches_right"] = c_max == W - 1
    g["touches_border"] = any([
        g["touches_top"], g["touches_bottom"],
        g["touches_left"], g["touches_right"]
    ])

    obj.gestalt = g
    return g


def _detect_arrow(bitmask: np.ndarray) -> Optional[str]:
    """Detect if shape is an arrow and return direction it points."""
    h, w = bitmask.shape
    if h < 2 or w < 2:
        return None

    # Count filled cells per row and column
    row_counts = bitmask.sum(axis=1)
    col_counts = bitmask.sum(axis=0)

    # Arrow pointing RIGHT: rows taper from wide to narrow left-to-right
    # Equivalently: leftmost column has fewer cells, rightmost has more
    # OR: triangular shape widest on left, narrowing right
    if h >= 3 and w >= 3:
        # Check if row widths form a diamond/triangle pointing in a direction
        # Right arrow: widest in middle rows, narrows toward top and bottom,
        # AND mass center is shifted right
        mass_col = np.mean([c for r, c in zip(*np.where(bitmask))])
        mass_row = np.mean([r for r, c in zip(*np.where(bitmask))])

        # Triangular check: each row's filled span
        spans = []
        for r in range(h):
            cols_in_row = np.where(bitmask[r])[0]
            if len(cols_in_row) > 0:
                spans.append((cols_in_row[0], cols_in_row[-1], len(cols_in_row)))

        if len(spans) >= 3:
            widths = [s[2] for s in spans]
            # Right-pointing: widths increase then decrease, right edge constant
            right_edges = [s[1] for s in spans]
            left_edges = [s[0] for s in spans]

            if (max(right_edges) - min(right_edges) <= 1 and
                    max(widths) > min(widths) * 1.5):
                mid = h // 2
                if widths[mid] >= max(widths) * 0.8:
                    return "right"

            if (max(left_edges) - min(left_edges) <= 1 and
                    max(widths) > min(widths) * 1.5):
                mid = h // 2
                if widths[mid] >= max(widths) * 0.8:
                    return "left"

            # Down-pointing: widths decrease from top to bottom
            top_edges = [s[0] for s in zip(*[(r, bitmask[r].sum())
                                              for r in range(h) if bitmask[r].sum() > 0])]

        # Simple heuristic: center of mass offset indicates pointing direction
        center_r, center_c = (h - 1) / 2, (w - 1) / 2
        if mass_col - center_c > w * 0.15:
            return "right"
        elif center_c - mass_col > w * 0.15:
            return "left"
        elif mass_row - center_r > h * 0.15:
            return "down"
        elif center_r - mass_row > h * 0.15:
            return "up"

    return None


def _detect_cross(bitmask: np.ndarray) -> bool:
    """Detect if shape is a cross/plus."""
    h, w = bitmask.shape
    if h < 3 or w < 3:
        return False
    # A cross has a center row and center column both fully filled
    # and the corners are empty
    cr, cc = h // 2, w // 2
    # Check center row and center column
    if not all(bitmask[cr, c] for c in range(w)):
        return False
    if not all(bitmask[r, cc] for r in range(h)):
        return False
    # Check at least one corner is empty
    corners = [(0, 0), (0, w - 1), (h - 1, 0), (h - 1, w - 1)]
    empty_corners = sum(1 for r, c in corners if bitmask[r, c] == 0)
    return empty_corners >= 2


def _detect_L(bitmask: np.ndarray) -> bool:
    """Detect L-shaped objects."""
    h, w = bitmask.shape
    if h < 2 or w < 2:
        return False
    total = bitmask.sum()
    if total < 3:
        return False
    # L-shape: occupies two edges of the bounding box
    # Check: bottom row + left column, or other combinations
    for rot in range(4):
        b = np.rot90(bitmask, rot)
        rh, rw = b.shape
        if rh < 2 or rw < 2:
            continue
        # Check if bottom row is full and left column is full
        bottom_full = all(b[rh - 1, c] for c in range(rw))
        left_full = all(b[r, 0] for r in range(rh))
        if bottom_full and left_full:
            # And the interior is mostly empty
            interior = b[:rh - 1, 1:]
            if interior.sum() < interior.size * 0.3:
                return True
    return False


def _detect_T(bitmask: np.ndarray) -> bool:
    """Detect T-shaped objects."""
    h, w = bitmask.shape
    if h < 2 or w < 2:
        return False
    for rot in range(4):
        b = np.rot90(bitmask, rot)
        rh, rw = b.shape
        if rh < 2 or rw < 2:
            continue
        # Top row full, center column full below
        top_full = all(b[0, c] for c in range(rw))
        if not top_full:
            continue
        cc = rw // 2
        col_below = all(b[r, cc] for r in range(1, rh))
        if col_below:
            # Check that non-center cells in rows below top are empty
            non_center_below = sum(
                b[r, c] for r in range(1, rh) for c in range(rw) if c != cc
            )
            if non_center_below < (rh - 1) * (rw - 1) * 0.3:
                return True
    return False


def _detect_figure(bitmask: np.ndarray) -> bool:
    """Detect figurative/anthropomorphic shapes.

    A figure has distinct regions that could be interpreted as
    head (narrow top), body (wider middle), limbs (extensions).
    """
    h, w = bitmask.shape
    if h < 4 or w < 3:
        return False

    row_widths = [bitmask[r].sum() for r in range(h)]
    if max(row_widths) < 2:
        return False

    # Figure pattern: narrow-wide-narrow from top to bottom
    # (head-body-legs pattern)
    thirds = [
        sum(row_widths[:h // 3]) / max(h // 3, 1),
        sum(row_widths[h // 3:2 * h // 3]) / max(h // 3, 1),
        sum(row_widths[2 * h // 3:]) / max(h - 2 * (h // 3), 1),
    ]

    # Head narrow, body wide, legs narrow/split
    if thirds[0] < thirds[1] and thirds[2] <= thirds[1]:
        # Additionally check for bilateral symmetry (figures are usually symmetric)
        if np.array_equal(bitmask, bitmask[:, ::-1]):
            return True

    return False


def _detect_figure_orientation(bitmask: np.ndarray) -> Optional[str]:
    """If the shape is figurative, which way does it face?"""
    h, w = bitmask.shape
    if h < 3 or w < 3:
        return None

    # Mass distribution: which side has more cells?
    left_mass = bitmask[:, :w // 2].sum()
    right_mass = bitmask[:, w // 2:].sum()
    top_mass = bitmask[:h // 2, :].sum()
    bottom_mass = bitmask[h // 2:, :].sum()

    total = bitmask.sum()
    if total < 3:
        return None

    # A figure "faces" the direction where it has asymmetric extension
    if not np.array_equal(bitmask, bitmask[:, ::-1]):
        if right_mass > left_mass * 1.3:
            return "right"
        elif left_mass > right_mass * 1.3:
            return "left"

    # Vertical: upright vs inverted
    if top_mass < bottom_mass * 0.7:
        return "upright"
    elif bottom_mass < top_mass * 0.7:
        return "inverted"

    return "upright"


def _detect_holes(bitmask: np.ndarray) -> bool:
    """Check if the shape has internal holes."""
    if bitmask.sum() < 4:
        return False
    # Invert and check for enclosed bg regions
    inverted = 1 - bitmask
    labeled, n = ndlabel(inverted)
    h, w = bitmask.shape
    for comp_id in range(1, n + 1):
        comp = labeled == comp_id
        rows, cols = np.where(comp)
        # A hole doesn't touch any border
        if (min(rows) > 0 and max(rows) < h - 1
                and min(cols) > 0 and max(cols) < w - 1):
            return True
    return False


# ===================================================================
# LAYER 3: Spatial Relationship Computation
# ===================================================================

@dataclass
class SpatialRelation:
    """A spatial relationship between two objects or between object and region."""
    source_id: int
    target_id: int
    relation: str  # containment, adjacent, above, below, left, right, aligned_h, aligned_v
    distance: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)


def _compute_containment(
    objects: List[GridObject],
    bg_regions: List[GridObject],
    grid: np.ndarray,
) -> List[SpatialRelation]:
    """Which bg regions are enclosed by which objects?"""
    H, W = grid.shape
    relations = []
    for region in bg_regions:
        r_min, r_max, c_min, c_max = region.bbox
        # A region is enclosed if it doesn't touch any grid border
        touches_border = (r_min == 0 or r_max == H - 1 or
                          c_min == 0 or c_max == W - 1)
        if touches_border:
            continue

        # Find which objects surround this region
        # Expand the region mask by 1 pixel and see what colors we hit
        dilated = np.zeros_like(grid, dtype=bool)
        for r, c in region.pixels:
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nr, nc = r + dr, c + dc
                if 0 <= nr < H and 0 <= nc < W:
                    dilated[nr, nc] = True
        # Remove the region itself
        border_mask = dilated & ~region.mask
        border_colors = set(int(grid[r, c]) for r, c in zip(*np.where(border_mask)))
        border_colors.discard(0)

        for obj in objects:
            if obj.color in border_colors:
                # Check if this object actually borders the region
                overlap = border_mask & obj.mask
                if overlap.any():
                    relations.append(SpatialRelation(
                        source_id=region.obj_id,
                        target_id=obj.obj_id,
                        relation="enclosed_by",
                        details={"enclosing_color": obj.color},
                    ))

    return relations


def _compute_adjacency(
    objects: List[GridObject],
    grid: np.ndarray,
) -> List[SpatialRelation]:
    """Which objects are adjacent to each other?"""
    H, W = grid.shape
    relations = []

    for i, obj_a in enumerate(objects):
        for j, obj_b in enumerate(objects):
            if i >= j:
                continue

            # Check if objects are adjacent (within 1 cell)
            min_dist = float("inf")
            for ra, ca in obj_a.pixels[:50]:  # sample for speed
                for rb, cb in obj_b.pixels[:50]:
                    d = abs(ra - rb) + abs(ca - cb)
                    min_dist = min(min_dist, d)
                    if d <= 2:
                        break
                if min_dist <= 2:
                    break

            if min_dist <= 2:
                # Determine relative direction
                dr = obj_b.centroid[0] - obj_a.centroid[0]
                dc = obj_b.centroid[1] - obj_a.centroid[1]
                if abs(dr) > abs(dc):
                    direction = "below" if dr > 0 else "above"
                else:
                    direction = "right" if dc > 0 else "left"

                relations.append(SpatialRelation(
                    source_id=obj_a.obj_id,
                    target_id=obj_b.obj_id,
                    relation=f"adjacent_{direction}",
                    distance=min_dist,
                ))

    return relations


def _compute_alignment(
    objects: List[GridObject],
) -> List[SpatialRelation]:
    """Which objects are aligned horizontally or vertically?"""
    relations = []
    for i, a in enumerate(objects):
        for j, b in enumerate(objects):
            if i >= j:
                continue
            # Horizontal alignment: centroids share similar row
            if abs(a.centroid[0] - b.centroid[0]) <= 1.0:
                relations.append(SpatialRelation(
                    source_id=a.obj_id,
                    target_id=b.obj_id,
                    relation="aligned_h",
                ))
            # Vertical alignment: centroids share similar column
            if abs(a.centroid[1] - b.centroid[1]) <= 1.0:
                relations.append(SpatialRelation(
                    source_id=a.obj_id,
                    target_id=b.obj_id,
                    relation="aligned_v",
                ))
    return relations


def _nearest_object_per_cell(
    grid: np.ndarray,
    objects: List[GridObject],
    bg: int = 0,
) -> np.ndarray:
    """For each bg cell, find the nearest object (by obj_id). Returns grid of obj_ids."""
    H, W = grid.shape
    nearest = np.full((H, W), -1, dtype=int)
    dist = np.full((H, W), float("inf"))

    for obj in objects:
        for r, c in obj.pixels:
            # BFS-like: mark this cell and propagate
            nearest[r, c] = obj.obj_id
            dist[r, c] = 0

    # Simple distance propagation (Manhattan)
    changed = True
    for iteration in range(max(H, W)):
        if not changed:
            break
        changed = False
        for r in range(H):
            for c in range(W):
                if grid[r, c] != bg:
                    continue
                for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < H and 0 <= nc < W and dist[nr, nc] + 1 < dist[r, c]:
                        dist[r, c] = dist[nr, nc] + 1
                        nearest[r, c] = nearest[nr, nc]
                        changed = True

    return nearest


def _object_above_below_left_right(
    cell_r: int, cell_c: int,
    grid: np.ndarray,
    objects: List[GridObject],
) -> Dict[str, Optional[GridObject]]:
    """For a given cell, find the nearest object in each cardinal direction."""
    H, W = grid.shape
    result: Dict[str, Optional[GridObject]] = {
        "above": None, "below": None, "left": None, "right": None
    }

    for obj in objects:
        for r, c in obj.pixels:
            if c == cell_c and r < cell_r:
                if result["above"] is None or r > result["above"].bbox[1]:
                    result["above"] = obj
            if c == cell_c and r > cell_r:
                if result["below"] is None or r < result["below"].bbox[0]:
                    result["below"] = obj
            if r == cell_r and c < cell_c:
                if result["left"] is None or c > result["left"].bbox[3]:
                    result["left"] = obj
            if r == cell_r and c > cell_c:
                if result["right"] is None or c < result["right"].bbox[2]:
                    result["right"] = obj

    return result


# ===================================================================
# LAYER 4: Spatial Reasoning Memory
# ===================================================================

@dataclass
class SpatialStrategy:
    """A remembered spatial reasoning strategy."""
    strategy_name: str
    spatial_pattern: str  # e.g., "enclosed_regions_exist"
    delta_signature: str  # e.g., "fill_bg_with_enclosing_color"
    success_count: int = 0
    task_ids: List[str] = field(default_factory=list)


class SpatialMemory:
    """Stores and retrieves spatial reasoning strategies."""

    def __init__(self):
        self.strategies: List[SpatialStrategy] = []

    def store(self, name: str, pattern: str, sig: str, task_id: str):
        for s in self.strategies:
            if s.strategy_name == name:
                s.success_count += 1
                s.task_ids.append(task_id)
                return
        self.strategies.append(SpatialStrategy(
            strategy_name=name,
            spatial_pattern=pattern,
            delta_signature=sig,
            success_count=1,
            task_ids=[task_id],
        ))

    def suggest_order(self, spatial_features: Dict) -> List[str]:
        """Given spatial features of a new task, suggest strategy order."""
        scores = []
        for s in self.strategies:
            score = s.success_count
            if s.spatial_pattern in str(spatial_features):
                score *= 2
            scores.append((s.strategy_name, score))
        scores.sort(key=lambda x: -x[1])
        return [name for name, _ in scores]


# Global memory instance (persists across calls within a session)
_spatial_memory = SpatialMemory()


# ===================================================================
# LAYER 5: Hypothesis Generation — Fill Tasks
# ===================================================================

def _hypothesize_containment_fill(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    timeout: float,
) -> List[SynthesizedOperator]:
    """Hypothesis: enclosed bg regions get filled with the color of their
    enclosing object."""
    results = []
    start = time.time()

    # Check first pair to see if this pattern exists
    inp0, out0 = train_pairs[0]
    if inp0.shape != out0.shape:
        return results

    objects = _extract_objects(inp0)
    bg_regions = _extract_bg_regions(inp0)
    containment = _compute_containment(objects, bg_regions, inp0)

    if not containment:
        return results

    # Hypothesis A: fill enclosed region with enclosing object's color
    def make_fill_enclosed_color():
        def fn(grid):
            objs = _extract_objects(grid)
            bg_regs = _extract_bg_regions(grid)
            rels = _compute_containment(objs, bg_regs, grid)
            obj_map = {o.obj_id: o for o in objs}
            out = grid.copy()
            for rel in rels:
                if rel.relation == "enclosed_by":
                    region = None
                    for br in bg_regs:
                        if br.obj_id == rel.source_id:
                            region = br
                            break
                    enc_obj = obj_map.get(rel.target_id)
                    if region is not None and enc_obj is not None:
                        out[region.mask] = enc_obj.color
            return out
        return fn

    fn = make_fill_enclosed_color()
    if _verify(fn, train_pairs):
        results.append(SynthesizedOperator(
            operator_id=f"spatial_containment_fill_{uuid.uuid4().hex[:8]}",
            operator_family="spatial_containment_fill",
            parameters={},
            preconditions=[],
            execute=fn,
            explanation="[Spatial] Fill enclosed bg regions with enclosing object's color",
            source_failure_signature={},
        ))
        return results

    # Hypothesis B: fill enclosed regions with a FIXED color (not enclosing)
    if time.time() - start > timeout:
        return results

    # Determine what color enclosed regions become in the output
    for region in bg_regions:
        out_colors = set(int(out0[r, c]) for r, c in region.pixels)
        out_colors.discard(0)
        if len(out_colors) == 1:
            fill_color = out_colors.pop()

            def make_fill_enclosed_fixed(fc):
                def fn(grid, _fc=fc):
                    objs = _extract_objects(grid)
                    bg_regs = _extract_bg_regions(grid)
                    rels = _compute_containment(objs, bg_regs, grid)
                    out = grid.copy()
                    enclosed_ids = set(rel.source_id for rel in rels
                                       if rel.relation == "enclosed_by")
                    for br in bg_regs:
                        if br.obj_id in enclosed_ids:
                            out[br.mask] = _fc
                    return out
                return fn

            fn = make_fill_enclosed_fixed(fill_color)
            if _verify(fn, train_pairs):
                results.append(SynthesizedOperator(
                    operator_id=f"spatial_containment_fill_fixed_{uuid.uuid4().hex[:8]}",
                    operator_family="spatial_containment_fill_fixed",
                    parameters={"fill_color": fill_color},
                    preconditions=[],
                    execute=fn,
                    explanation=f"[Spatial] Fill enclosed bg regions with color {fill_color}",
                    source_failure_signature={},
                ))
                return results

    return results


def _hypothesize_stamp_pattern(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    timeout: float,
) -> List[SynthesizedOperator]:
    """Hypothesis: each object 'stamps' a pattern around itself.

    Like a cross/diamond emanating from each colored cell into bg.
    """
    results = []
    start = time.time()

    inp0, out0 = train_pairs[0]
    if inp0.shape != out0.shape:
        return results

    diff = inp0 != out0
    if not diff.any():
        return results

    # Only bg cells changed
    changed_were_bg = all(inp0[r, c] == 0 for r, c in zip(*np.where(diff)))
    if not changed_were_bg:
        return results

    objects = _extract_objects(inp0)
    if not objects:
        return results

    # For each changed bg cell, find the nearest object and the offset
    changed_cells = list(zip(*np.where(diff)))

    # Group by which object they're nearest to (by color)
    for obj in objects:
        if time.time() - start > timeout:
            break

        # Find changed cells near this object
        obj_changed = []
        for r, c in changed_cells:
            # Check if this cell's output color matches something related to this object
            for pr, pc in obj.pixels:
                dr, dc = r - pr, c - pc
                obj_changed.append((dr, dc, int(out0[r, c])))
                break  # just use first pixel for offset reference

    # Try: each non-bg cell radiates a cross pattern
    for pattern_name, offsets_fn in [
        ("cross", lambda: [(-1, 0), (1, 0), (0, -1), (0, 1),
                           (-2, 0), (2, 0), (0, -2), (0, 2)]),
        ("diamond", lambda: [(-1, 0), (1, 0), (0, -1), (0, 1),
                             (-1, -1), (-1, 1), (1, -1), (1, 1)]),
        ("line_h", lambda: [(0, d) for d in range(-5, 6) if d != 0]),
        ("line_v", lambda: [(d, 0) for d in range(-5, 6) if d != 0]),
    ]:
        if time.time() - start > timeout:
            break

        offsets = offsets_fn()

        def make_stamp_fn(offs):
            def fn(grid, _offs=offs):
                H, W = grid.shape
                out = grid.copy()
                for r in range(H):
                    for c in range(W):
                        if grid[r, c] == 0:
                            continue
                        color = int(grid[r, c])
                        for dr, dc in _offs:
                            nr, nc = r + dr, c + dc
                            if 0 <= nr < H and 0 <= nc < W and out[nr, nc] == 0:
                                out[nr, nc] = color
                return out
            return fn

        fn = make_stamp_fn(offsets)
        if _verify(fn, train_pairs):
            results.append(SynthesizedOperator(
                operator_id=f"spatial_stamp_{pattern_name}_{uuid.uuid4().hex[:8]}",
                operator_family=f"spatial_stamp_{pattern_name}",
                parameters={"pattern": pattern_name},
                preconditions=[],
                execute=fn,
                explanation=f"[Spatial] Each colored cell stamps a {pattern_name} pattern",
                source_failure_signature={},
            ))
            return results

    # Try: each colored cell radiates lines until hitting another colored cell
    for direction_set_name, dirs in [
        ("cross_extend", [(-1, 0), (1, 0), (0, -1), (0, 1)]),
        ("diagonal_extend", [(-1, -1), (-1, 1), (1, -1), (1, 1)]),
        ("all_extend", [(-1, 0), (1, 0), (0, -1), (0, 1),
                        (-1, -1), (-1, 1), (1, -1), (1, 1)]),
    ]:
        if time.time() - start > timeout:
            break

        def make_extend_fn(ds):
            def fn(grid, _ds=ds):
                H, W = grid.shape
                out = grid.copy()
                for r in range(H):
                    for c in range(W):
                        if grid[r, c] == 0:
                            continue
                        color = int(grid[r, c])
                        for dr, dc in _ds:
                            nr, nc = r + dr, c + dc
                            while 0 <= nr < H and 0 <= nc < W:
                                if grid[nr, nc] != 0:
                                    break
                                out[nr, nc] = color
                                nr += dr
                                nc += dc
                return out
            return fn

        fn = make_extend_fn(dirs)
        if _verify(fn, train_pairs):
            results.append(SynthesizedOperator(
                operator_id=f"spatial_extend_{direction_set_name}_{uuid.uuid4().hex[:8]}",
                operator_family=f"spatial_extend_{direction_set_name}",
                parameters={"directions": direction_set_name},
                preconditions=[],
                execute=fn,
                explanation=f"[Spatial] Extend colored cells in {direction_set_name} until hitting boundary",
                source_failure_signature={},
            ))
            return results

    return results


def _hypothesize_arrow_directed_fill(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    timeout: float,
) -> List[SynthesizedOperator]:
    """Hypothesis: arrow-shaped objects indicate fill direction.

    The system perceives arrow shapes and uses their direction
    to determine how to fill or transform nearby regions.
    """
    results = []
    start = time.time()

    inp0, out0 = train_pairs[0]
    if inp0.shape != out0.shape:
        return results

    objects = _extract_objects(inp0)
    for obj in objects:
        _compute_gestalt(obj, inp0)

    arrows = [o for o in objects if o.gestalt and o.gestalt.get("arrow_direction")]
    if not arrows:
        return results

    # Hypothesis: arrow objects "push" or "fill" in their pointing direction
    for arrow in arrows:
        if time.time() - start > timeout:
            break
        direction = arrow.gestalt["arrow_direction"]
        arrow_color = arrow.color

        dr, dc = {"up": (-1, 0), "down": (1, 0),
                  "left": (0, -1), "right": (0, 1)}.get(direction, (0, 0))

        def make_arrow_fill(a_mask, a_color, ddr, ddc):
            def fn(grid, _mask=a_mask, _color=a_color, _dr=ddr, _dc=ddc):
                H, W = grid.shape
                out = grid.copy()
                # Find arrow tip (furthest point in direction)
                arrow_pixels = list(zip(*np.where(_mask)))
                if not arrow_pixels:
                    return out
                if _dr != 0:
                    tip = max(arrow_pixels, key=lambda p: p[0] * _dr)
                else:
                    tip = max(arrow_pixels, key=lambda p: p[1] * _dc)
                # Fill from tip in direction
                r, c = tip
                r += _dr
                c += _dc
                while 0 <= r < H and 0 <= c < W:
                    if grid[r, c] == 0:
                        out[r, c] = _color
                    r += _dr
                    c += _dc
                return out
            return fn

        fn = make_arrow_fill(arrow.mask, arrow_color, dr, dc)
        if _verify(fn, train_pairs):
            results.append(SynthesizedOperator(
                operator_id=f"spatial_arrow_fill_{uuid.uuid4().hex[:8]}",
                operator_family="spatial_arrow_directed_fill",
                parameters={"direction": direction, "color": arrow_color},
                preconditions=[],
                execute=fn,
                explanation=f"[Gestalt] Arrow ({arrow_color}) points {direction}, fill in that direction",
                source_failure_signature={},
            ))
            return results

    return results


def _hypothesize_line_extension(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    timeout: float,
) -> List[SynthesizedOperator]:
    """Hypothesis: colored pixels extend lines to grid boundaries or
    to other colored pixels."""
    results = []
    start = time.time()

    inp0, out0 = train_pairs[0]
    if inp0.shape != out0.shape:
        return results

    # Try: each colored pixel extends horizontal/vertical lines
    for mode in ["h_only", "v_only", "cross", "to_border"]:
        if time.time() - start > timeout:
            break

        def make_line_extend(m):
            def fn(grid, _m=m):
                H, W = grid.shape
                out = grid.copy()
                for r in range(H):
                    for c in range(W):
                        if grid[r, c] == 0:
                            continue
                        color = int(grid[r, c])
                        if _m in ("h_only", "cross", "to_border"):
                            # Extend left
                            for cc in range(c - 1, -1, -1):
                                if grid[r, cc] != 0:
                                    break
                                out[r, cc] = color
                            # Extend right
                            for cc in range(c + 1, W):
                                if grid[r, cc] != 0:
                                    break
                                out[r, cc] = color
                        if _m in ("v_only", "cross", "to_border"):
                            # Extend up
                            for rr in range(r - 1, -1, -1):
                                if grid[rr, c] != 0:
                                    break
                                out[rr, c] = color
                            # Extend down
                            for rr in range(r + 1, H):
                                if grid[rr, c] != 0:
                                    break
                                out[rr, c] = color
                return out
            return fn

        fn = make_line_extend(mode)
        if _verify(fn, train_pairs):
            results.append(SynthesizedOperator(
                operator_id=f"spatial_line_extend_{mode}_{uuid.uuid4().hex[:8]}",
                operator_family=f"spatial_line_extend_{mode}",
                parameters={"mode": mode},
                preconditions=[],
                execute=fn,
                explanation=f"[Spatial] Extend colored cells as lines ({mode})",
                source_failure_signature={},
            ))
            return results

    return results


def _hypothesize_nearest_object_fill(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    timeout: float,
) -> List[SynthesizedOperator]:
    """Hypothesis: each bg cell gets the color of the nearest object."""
    results = []
    start = time.time()

    inp0, out0 = train_pairs[0]
    if inp0.shape != out0.shape:
        return results

    def make_nearest_fill():
        def fn(grid):
            H, W = grid.shape
            objs = _extract_objects(grid)
            if not objs:
                return grid.copy()
            nearest = _nearest_object_per_cell(grid, objs)
            obj_map = {o.obj_id: o for o in objs}
            out = grid.copy()
            for r in range(H):
                for c in range(W):
                    if grid[r, c] == 0 and nearest[r, c] >= 0:
                        obj = obj_map.get(nearest[r, c])
                        if obj:
                            out[r, c] = obj.color
            return out
        return fn

    fn = make_nearest_fill()
    if _verify(fn, train_pairs):
        results.append(SynthesizedOperator(
            operator_id=f"spatial_nearest_fill_{uuid.uuid4().hex[:8]}",
            operator_family="spatial_nearest_object_fill",
            parameters={},
            preconditions=[],
            execute=fn,
            explanation="[Spatial] Fill each bg cell with the color of the nearest object",
            source_failure_signature={},
        ))

    return results


def _hypothesize_row_col_object_intersection(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    timeout: float,
) -> List[SynthesizedOperator]:
    """Hypothesis: bg cell's output color is determined by the intersection
    of its row-object and column-object.

    E.g., a cell at (r,c) gets the color of the object in the same row
    if there's also an object in the same column.
    """
    results = []
    start = time.time()

    inp0, out0 = train_pairs[0]
    if inp0.shape != out0.shape:
        return results

    # Strategy 1: color = row's unique non-bg color
    def make_row_unique():
        def fn(grid):
            H, W = grid.shape
            out = grid.copy()
            for r in range(H):
                colors = set(int(grid[r, c]) for c in range(W)) - {0}
                if len(colors) == 1:
                    fill = colors.pop()
                    for c in range(W):
                        if grid[r, c] == 0:
                            out[r, c] = fill
            return out
        return fn

    fn = make_row_unique()
    if _verify(fn, train_pairs):
        results.append(SynthesizedOperator(
            operator_id=f"spatial_row_unique_{uuid.uuid4().hex[:8]}",
            operator_family="spatial_row_unique_fill",
            parameters={},
            preconditions=[],
            execute=fn,
            explanation="[Spatial] Fill bg in rows with a single unique color",
            source_failure_signature={},
        ))
        return results

    # Strategy 2: color = col's unique non-bg color
    def make_col_unique():
        def fn(grid):
            H, W = grid.shape
            out = grid.copy()
            for c in range(W):
                colors = set(int(grid[r, c]) for r in range(H)) - {0}
                if len(colors) == 1:
                    fill = colors.pop()
                    for r in range(H):
                        if grid[r, c] == 0:
                            out[r, c] = fill
            return out
        return fn

    fn = make_col_unique()
    if _verify(fn, train_pairs):
        results.append(SynthesizedOperator(
            operator_id=f"spatial_col_unique_{uuid.uuid4().hex[:8]}",
            operator_family="spatial_col_unique_fill",
            parameters={},
            preconditions=[],
            execute=fn,
            explanation="[Spatial] Fill bg in cols with a single unique color",
            source_failure_signature={},
        ))
        return results

    # Strategy 3: intersection of row color and col color
    if time.time() - start > timeout:
        return results

    def make_intersection_fill():
        def fn(grid):
            H, W = grid.shape
            out = grid.copy()
            row_colors = {}
            col_colors = {}
            for r in range(H):
                cs = set(int(grid[r, c]) for c in range(W)) - {0}
                if len(cs) == 1:
                    row_colors[r] = cs.pop()
            for c in range(W):
                cs = set(int(grid[r, c]) for r in range(H)) - {0}
                if len(cs) == 1:
                    col_colors[c] = cs.pop()
            for r in range(H):
                for c in range(W):
                    if grid[r, c] == 0 and r in row_colors and c in col_colors:
                        out[r, c] = row_colors[r]
            return out
        return fn

    fn = make_intersection_fill()
    if _verify(fn, train_pairs):
        results.append(SynthesizedOperator(
            operator_id=f"spatial_intersection_{uuid.uuid4().hex[:8]}",
            operator_family="spatial_intersection_fill",
            parameters={},
            preconditions=[],
            execute=fn,
            explanation="[Spatial] Fill bg at row-col intersection of colored lines",
            source_failure_signature={},
        ))

    return results


# ===================================================================
# LAYER 6: Hypothesis Generation — Object Recolor
# ===================================================================

def _hypothesize_component_coloring(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    timeout: float,
) -> List[SynthesizedOperator]:
    """Hypothesis: different connected components of the same color
    get recolored differently based on properties (size, position)."""
    results = []
    start = time.time()

    inp0, out0 = train_pairs[0]
    if inp0.shape != out0.shape:
        return results

    objects = _extract_objects(inp0)
    if len(objects) < 2:
        return results

    # Group objects by input color
    by_color = defaultdict(list)
    for obj in objects:
        by_color[obj.color].append(obj)

    # Find colors where all objects got recolored to DIFFERENT output colors
    for color, objs in by_color.items():
        if len(objs) < 2:
            continue
        if time.time() - start > timeout:
            break

        out_colors = []
        for obj in objs:
            oc = Counter(int(out0[r, c]) for r, c in obj.pixels)
            dominant = oc.most_common(1)[0][0]
            out_colors.append(dominant)

        if len(set(out_colors)) <= 1:
            continue

        # Hypothesis: recolor by SIZE ordering
        size_sorted = sorted(range(len(objs)), key=lambda i: objs[i].area)
        color_order = [out_colors[i] for i in size_sorted]

        def make_size_recolor(in_color, c_order):
            def fn(grid, _ic=in_color, _co=c_order):
                cur_objs = _extract_objects(grid)
                same = [o for o in cur_objs if o.color == _ic]
                same.sort(key=lambda o: o.area)
                out = grid.copy()
                for i, obj in enumerate(same):
                    if i < len(_co):
                        out[obj.mask] = _co[i]
                return out
            return fn

        fn = make_size_recolor(color, color_order)
        if _verify(fn, train_pairs):
            results.append(SynthesizedOperator(
                operator_id=f"spatial_comp_size_{uuid.uuid4().hex[:8]}",
                operator_family="spatial_component_size_recolor",
                parameters={"input_color": color},
                preconditions=[],
                execute=fn,
                explanation=f"[Spatial] Recolor components of color {color} by size order",
                source_failure_signature={},
            ))
            return results

        # Hypothesis: recolor by POSITION (top-to-bottom, left-to-right)
        pos_sorted = sorted(range(len(objs)), key=lambda i: (
            objs[i].centroid[0], objs[i].centroid[1]))
        color_order_pos = [out_colors[i] for i in pos_sorted]

        def make_pos_recolor(in_color, c_order):
            def fn(grid, _ic=in_color, _co=c_order):
                cur_objs = _extract_objects(grid)
                same = [o for o in cur_objs if o.color == _ic]
                same.sort(key=lambda o: (o.centroid[0], o.centroid[1]))
                out = grid.copy()
                for i, obj in enumerate(same):
                    if i < len(_co):
                        out[obj.mask] = _co[i]
                return out
            return fn

        fn = make_pos_recolor(color, color_order_pos)
        if _verify(fn, train_pairs):
            results.append(SynthesizedOperator(
                operator_id=f"spatial_comp_pos_{uuid.uuid4().hex[:8]}",
                operator_family="spatial_component_position_recolor",
                parameters={"input_color": color},
                preconditions=[],
                execute=fn,
                explanation=f"[Spatial] Recolor components of color {color} by position order",
                source_failure_signature={},
            ))
            return results

    return results


def _hypothesize_gestalt_property_recolor(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    timeout: float,
) -> List[SynthesizedOperator]:
    """Hypothesis: objects get recolored based on their gestalt properties.

    E.g., 'objects with holes get color X', 'arrows get color Y',
    'the cross-shaped object gets color Z'.
    """
    results = []
    start = time.time()

    inp0, out0 = train_pairs[0]
    if inp0.shape != out0.shape:
        return results

    objects = _extract_objects(inp0)
    if len(objects) < 2:
        return results

    for obj in objects:
        _compute_gestalt(obj, inp0)

    # Determine each object's fate
    fates = []
    for obj in objects:
        out_colors = Counter(int(out0[r, c]) for r, c in obj.pixels)
        dominant = out_colors.most_common(1)[0][0]
        changed = dominant != obj.color
        fates.append({"obj": obj, "out_color": dominant, "changed": changed})

    if not any(f["changed"] for f in fates):
        return results

    # Try each gestalt property as discriminator
    gestalt_props = [
        "is_cross", "is_L", "is_T", "is_figure", "has_holes",
        "is_square", "is_rectangle", "is_filled_rect", "is_line",
        "symmetric_both", "symmetric_h", "symmetric_v",
        "touches_border", "is_convex", "is_single_pixel",
    ]

    for prop in gestalt_props:
        if time.time() - start > timeout:
            break

        # Check if this property discriminates fates across ALL training pairs
        consistent = True
        prop_to_color = {}

        for inp, out in train_pairs:
            pair_objs = _extract_objects(inp)
            for o in pair_objs:
                _compute_gestalt(o, inp)

            for o in pair_objs:
                g = o.gestalt or {}
                pval = g.get(prop, False)
                out_c = Counter(int(out[r, c]) for r, c in o.pixels).most_common(1)[0][0]

                key = (pval, o.color)
                if key in prop_to_color:
                    if prop_to_color[key] != out_c:
                        consistent = False
                        break
                else:
                    prop_to_color[key] = out_c

            if not consistent:
                break

        if not consistent or not prop_to_color:
            continue

        # Check it's not trivial (all same mapping regardless of property)
        mappings_true = {v for (p, _), v in prop_to_color.items() if p}
        mappings_false = {v for (p, _), v in prop_to_color.items() if not p}
        if mappings_true == mappings_false and len(mappings_true) == 1:
            continue

        def make_gestalt_recolor(pr, p2c):
            def fn(grid, _pr=pr, _p2c=p2c):
                objs = _extract_objects(grid)
                out = grid.copy()
                for o in objs:
                    _compute_gestalt(o, grid)
                    g = o.gestalt or {}
                    pval = g.get(_pr, False)
                    key = (pval, o.color)
                    if key in _p2c:
                        out[o.mask] = _p2c[key]
                return out
            return fn

        fn = make_gestalt_recolor(prop, dict(prop_to_color))
        if _verify(fn, train_pairs):
            results.append(SynthesizedOperator(
                operator_id=f"spatial_gestalt_{prop}_{uuid.uuid4().hex[:8]}",
                operator_family=f"spatial_gestalt_recolor_{prop}",
                parameters={"property": prop},
                preconditions=[],
                execute=fn,
                explanation=f"[Gestalt] Recolor objects by gestalt property: {prop}",
                source_failure_signature={},
            ))
            return results

    # Try arrow direction as discriminator
    if time.time() - start < timeout:
        consistent = True
        dir_to_color = {}
        for inp, out in train_pairs:
            pair_objs = _extract_objects(inp)
            for o in pair_objs:
                _compute_gestalt(o, inp)
                ad = (o.gestalt or {}).get("arrow_direction", "none")
                out_c = Counter(int(out[r, c]) for r, c in o.pixels).most_common(1)[0][0]
                key = (ad, o.color)
                if key in dir_to_color:
                    if dir_to_color[key] != out_c:
                        consistent = False
                        break
                else:
                    dir_to_color[key] = out_c
            if not consistent:
                break

        if consistent and dir_to_color:
            def make_arrow_recolor(d2c):
                def fn(grid, _d2c=d2c):
                    objs = _extract_objects(grid)
                    out = grid.copy()
                    for o in objs:
                        _compute_gestalt(o, grid)
                        ad = (o.gestalt or {}).get("arrow_direction", "none")
                        key = (ad, o.color)
                        if key in _d2c:
                            out[o.mask] = _d2c[key]
                    return out
                return fn

            fn = make_arrow_recolor(dict(dir_to_color))
            if _verify(fn, train_pairs):
                results.append(SynthesizedOperator(
                    operator_id=f"spatial_gestalt_arrow_dir_{uuid.uuid4().hex[:8]}",
                    operator_family="spatial_gestalt_arrow_direction_recolor",
                    parameters={},
                    preconditions=[],
                    execute=fn,
                    explanation="[Gestalt] Recolor objects by arrow direction",
                    source_failure_signature={},
                ))

    return results


def _hypothesize_template_transfer(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    timeout: float,
) -> List[SynthesizedOperator]:
    """Hypothesis: one object acts as a template/pattern that gets
    stamped/copied into regions defined by other objects.

    Common ARC pattern: a small pattern object and larger 'target' regions.
    """
    results = []
    start = time.time()

    inp0, out0 = train_pairs[0]
    if inp0.shape != out0.shape:
        return results

    objects = _extract_objects(inp0)
    if len(objects) < 2:
        return results

    # Find the smallest object (likely the template)
    objects_sorted = sorted(objects, key=lambda o: o.area)

    for template_obj in objects_sorted[:3]:
        if time.time() - start > timeout:
            break
        if template_obj.area > 25:
            continue

        r_min, r_max, c_min, c_max = template_obj.bbox
        template = inp0[r_min:r_max + 1, c_min:c_max + 1].copy()
        th, tw = template.shape

        # Try stamping this template at positions of other objects
        for target_obj in objects:
            if target_obj.obj_id == template_obj.obj_id:
                continue
            if time.time() - start > timeout:
                break

            # Check if the template fits in/near the target
            tr, tc = target_obj.bbox[0], target_obj.bbox[2]

            def make_template_stamp(tmpl, templ_obj_id, tmpl_color):
                def fn(grid, _t=tmpl, _tid=templ_obj_id, _tc=tmpl_color):
                    objs = _extract_objects(grid)
                    out = grid.copy()
                    H, W = grid.shape
                    tmpl_h, tmpl_w = _t.shape
                    # Find the template object (smallest with matching color)
                    template_candidates = sorted(
                        [o for o in objs if o.color == _tc],
                        key=lambda o: o.area
                    )
                    if not template_candidates:
                        return out
                    tmpl_obj = template_candidates[0]
                    # Stamp at each other object's position
                    for o in objs:
                        if o.obj_id == tmpl_obj.obj_id:
                            continue
                        sr, sc = o.bbox[0], o.bbox[2]
                        for dr in range(tmpl_h):
                            for dc in range(tmpl_w):
                                nr, nc = sr + dr, sc + dc
                                if (0 <= nr < H and 0 <= nc < W
                                        and _t[dr, dc] != 0):
                                    out[nr, nc] = int(_t[dr, dc])
                    return out
                return fn

            fn = make_template_stamp(template, template_obj.obj_id, template_obj.color)
            if _verify(fn, train_pairs):
                results.append(SynthesizedOperator(
                    operator_id=f"spatial_template_{uuid.uuid4().hex[:8]}",
                    operator_family="spatial_template_transfer",
                    parameters={},
                    preconditions=[],
                    execute=fn,
                    explanation=f"[Gestalt] Stamp template (color {template_obj.color}) at other object positions",
                    source_failure_signature={},
                ))
                return results

    return results


def _hypothesize_flood_fill_from_objects(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    timeout: float,
) -> List[SynthesizedOperator]:
    """Hypothesis: bg cells get flood-filled from adjacent colored cells,
    spreading color through connected bg regions."""
    results = []
    start = time.time()

    inp0, out0 = train_pairs[0]
    if inp0.shape != out0.shape:
        return results

    # Try flood fill where each bg region takes the color of its
    # most common adjacent non-bg neighbor
    def make_adjacent_flood():
        def fn(grid):
            H, W = grid.shape
            out = grid.copy()
            bg_mask = grid == 0
            labeled, n = ndlabel(bg_mask)
            for comp_id in range(1, n + 1):
                comp = labeled == comp_id
                # Find adjacent non-bg colors
                adj_colors = Counter()
                for r, c in zip(*np.where(comp)):
                    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < H and 0 <= nc < W and grid[nr, nc] != 0:
                            adj_colors[int(grid[nr, nc])] += 1
                if adj_colors:
                    fill_color = adj_colors.most_common(1)[0][0]
                    out[comp] = fill_color
            return out
        return fn

    fn = make_adjacent_flood()
    if _verify(fn, train_pairs):
        results.append(SynthesizedOperator(
            operator_id=f"spatial_flood_adj_{uuid.uuid4().hex[:8]}",
            operator_family="spatial_flood_fill_adjacent",
            parameters={},
            preconditions=[],
            execute=fn,
            explanation="[Spatial] Flood fill bg regions with most common adjacent color",
            source_failure_signature={},
        ))

    return results


# ===================================================================
# LAYER 7: Compositional Spatial Reasoning
# ===================================================================

def _hypothesize_gestalt_then_fill(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    timeout: float,
) -> List[SynthesizedOperator]:
    """Two-step reasoning: first perceive gestalt, then fill based on it.

    E.g., 'the cross-shaped object defines axes; fill the quadrants
    between the axes with specific colors.'
    """
    results = []
    start = time.time()

    inp0, out0 = train_pairs[0]
    if inp0.shape != out0.shape:
        return results

    objects = _extract_objects(inp0)
    for obj in objects:
        _compute_gestalt(obj, inp0)

    # Find cross-shaped objects
    crosses = [o for o in objects if o.gestalt and o.gestalt.get("is_cross")]
    if crosses:
        cross = crosses[0]
        cr_min, cr_max, cc_min, cc_max = cross.bbox
        cr_center = (cr_min + cr_max) // 2
        cc_center = (cc_min + cc_max) // 2

        # The cross divides the grid into quadrants
        # Check if each quadrant has a distinct fill color in output
        H, W = inp0.shape
        quadrants = {
            "TL": (0, cr_center, 0, cc_center),
            "TR": (0, cr_center, cc_center + 1, W),
            "BL": (cr_center + 1, H, 0, cc_center),
            "BR": (cr_center + 1, H, cc_center + 1, W),
        }

        quad_colors = {}
        for qname, (r0, r1, c0, c1) in quadrants.items():
            colors = Counter()
            for r in range(r0, r1):
                for c in range(c0, c1):
                    if inp0[r, c] == 0 and out0[r, c] != 0:
                        colors[int(out0[r, c])] += 1
            if colors:
                quad_colors[qname] = colors.most_common(1)[0][0]

        if len(quad_colors) >= 2:
            def make_cross_quadrant_fill(cross_color, qc):
                def fn(grid, _cc=cross_color, _qc=qc):
                    objs = _extract_objects(grid)
                    for o in objs:
                        _compute_gestalt(o, grid)
                    cx = [o for o in objs if o.gestalt and o.gestalt.get("is_cross")]
                    if not cx:
                        return grid.copy()
                    c = cx[0]
                    cr = (c.bbox[0] + c.bbox[1]) // 2
                    cc = (c.bbox[2] + c.bbox[3]) // 2
                    H, W = grid.shape
                    out = grid.copy()
                    quads = {
                        "TL": (0, cr, 0, cc),
                        "TR": (0, cr, cc + 1, W),
                        "BL": (cr + 1, H, 0, cc),
                        "BR": (cr + 1, H, cc + 1, W),
                    }
                    for qn, (r0, r1, c0, c1) in quads.items():
                        if qn in _qc:
                            for r in range(r0, r1):
                                for ci in range(c0, c1):
                                    if grid[r, ci] == 0:
                                        out[r, ci] = _qc[qn]
                    return out
                return fn

            fn = make_cross_quadrant_fill(cross.color, quad_colors)
            if _verify(fn, train_pairs):
                results.append(SynthesizedOperator(
                    operator_id=f"spatial_cross_quad_{uuid.uuid4().hex[:8]}",
                    operator_family="spatial_cross_quadrant_fill",
                    parameters={"quadrant_colors": quad_colors},
                    preconditions=[],
                    execute=fn,
                    explanation=f"[Gestalt] Cross divides grid into quadrants, fill each with {quad_colors}",
                    source_failure_signature={},
                ))
                return results

    return results


# ===================================================================
# VERIFICATION
# ===================================================================

def _verify(fn, train_pairs):
    for inp, out in train_pairs:
        try:
            pred = fn(inp)
            if pred is None or not isinstance(pred, np.ndarray):
                return False
            if pred.shape != out.shape or not np.array_equal(pred, out):
                return False
        except Exception:
            return False
    return True


# ===================================================================
# OBJECT TRANSFORMATION REASONING
# ===================================================================

def _match_objects(
    in_objs: List[GridObject], out_objs: List[GridObject],
    in_grid: np.ndarray, out_grid: np.ndarray,
) -> List[Tuple[Optional[GridObject], Optional[GridObject]]]:
    """Find correspondences between input and output objects.

    Returns list of (in_obj, out_obj) pairs. None means unmatched
    (deleted input object or new output object).
    """
    pairs = []
    used_out = set()

    for io in in_objs:
        best_match = None
        best_score = 0.0
        for j, oo in enumerate(out_objs):
            if j in used_out:
                continue
            score = 0.0
            # Color match
            if io.color == oo.color:
                score += 2.0
            # Shape match (normalized pixel set)
            io_rel = frozenset((r - io.bbox[0], c - io.bbox[2]) for r, c in io.pixels)
            oo_rel = frozenset((r - oo.bbox[0], c - oo.bbox[2]) for r, c in oo.pixels)
            if io_rel == oo_rel:
                score += 3.0
            elif io.area == oo.area:
                score += 1.0
            # Position overlap
            overlap = np.sum(io.mask & oo.mask)
            if overlap > 0:
                score += 2.0 * overlap / max(io.area, oo.area)
            # Proximity
            dist = ((io.centroid[0] - oo.centroid[0])**2 +
                    (io.centroid[1] - oo.centroid[1])**2) ** 0.5
            score += max(0, 1.0 - dist / 20.0)
            if score > best_score:
                best_score = score
                best_match = j
        if best_match is not None and best_score >= 2.0:
            pairs.append((io, out_objs[best_match]))
            used_out.add(best_match)
        else:
            pairs.append((io, None))

    for j, oo in enumerate(out_objs):
        if j not in used_out:
            pairs.append((None, oo))

    return pairs


def _hypothesize_object_movement(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    timeout: float,
) -> List[SynthesizedOperator]:
    """Discover object movement rules: objects move to new positions."""
    start = time.time()
    results = []

    movements_per_pair = []
    for inp, out in train_pairs:
        if inp.shape != out.shape:
            return []
        in_objs = _extract_objects(inp, bg=0)
        out_objs = _extract_objects(out, bg=0)
        if not in_objs or not out_objs:
            return []

        pairs = _match_objects(in_objs, out_objs, inp, out)
        movements = []
        for io, oo in pairs:
            if io is None or oo is None:
                continue
            dr = oo.centroid[0] - io.centroid[0]
            dc = oo.centroid[1] - io.centroid[1]
            movements.append({
                "in_obj": io, "out_obj": oo,
                "dr": dr, "dc": dc,
                "color": io.color, "area": io.area,
            })
        movements_per_pair.append(movements)

    if not movements_per_pair or not movements_per_pair[0]:
        return []

    # Strategy 1: All objects move by the same (dr, dc) — uniform shift
    uniform_ok = True
    for pair_moves in movements_per_pair:
        if len(pair_moves) < 2:
            uniform_ok = False
            break
        drs = [m["dr"] for m in pair_moves]
        dcs = [m["dc"] for m in pair_moves]
        if len(set(round(d, 1) for d in drs)) > 1 or len(set(round(d, 1) for d in dcs)) > 1:
            uniform_ok = False
            break

    if uniform_ok and movements_per_pair[0]:
        dr0 = round(movements_per_pair[0][0]["dr"])
        dc0 = round(movements_per_pair[0][0]["dc"])
        consistent = all(
            all(round(m["dr"]) == dr0 and round(m["dc"]) == dc0 for m in pm)
            for pm in movements_per_pair
        )
        if consistent and (dr0 != 0 or dc0 != 0):
            def make_shift(dr, dc):
                def fn(grid, _dr=dr, _dc=dc):
                    h, w = grid.shape
                    out = np.zeros_like(grid)
                    objs = _extract_objects(grid, bg=0)
                    for obj in objs:
                        for r, c in obj.pixels:
                            nr, nc = r + _dr, c + _dc
                            if 0 <= nr < h and 0 <= nc < w:
                                out[nr, nc] = obj.color
                    return out
                return fn
            op = SynthesizedOperator(
                operator_id=f"obj_shift_{uuid.uuid4().hex[:8]}",
                operator_family="object_uniform_shift",
                parameters={"dr": dr0, "dc": dc0},
                preconditions=[],
                execute=make_shift(dr0, dc0),
                explanation=f"Shift all objects by ({dr0},{dc0})",
                source_failure_signature={},
            )
            if _check_train(op, train_pairs):
                results.append(op)
                return results

    if time.time() - start > timeout:
        return results

    # Strategy 2: Per-object movement depends on object property (color, size, position)
    # Check if movement is a function of object properties
    for prop_name, prop_fn in [
        ("area", lambda m: m["area"]),
        ("color", lambda m: m["color"]),
    ]:
        # For each pair, build property → (dr, dc) mapping
        prop_maps = []
        prop_consistent = True
        for pair_moves in movements_per_pair:
            pmap = {}
            for m in pair_moves:
                key = prop_fn(m)
                val = (round(m["dr"]), round(m["dc"]))
                if key in pmap and pmap[key] != val:
                    prop_consistent = False
                    break
                pmap[key] = val
            if not prop_consistent:
                break
            prop_maps.append(pmap)

        if not prop_consistent:
            continue

        # Check consistency across training pairs
        if len(prop_maps) >= 2:
            ref = prop_maps[0]
            for pm in prop_maps[1:]:
                for k, v in pm.items():
                    if k in ref and ref[k] != v:
                        prop_consistent = False
                        break
                if not prop_consistent:
                    break
                ref.update(pm)

        if not prop_consistent:
            continue

        merged_map = {}
        for pm in prop_maps:
            merged_map.update(pm)

        if not merged_map or all(v == (0, 0) for v in merged_map.values()):
            continue

        frozen_map = dict(merged_map)
        def make_prop_shift(pmap, prop):
            def fn(grid, _pmap=pmap, _prop=prop):
                h, w = grid.shape
                out = np.zeros_like(grid)
                objs = _extract_objects(grid, bg=0)
                for obj in objs:
                    key = obj.area if _prop == "area" else obj.color
                    dr, dc = _pmap.get(key, (0, 0))
                    for r, c in obj.pixels:
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < h and 0 <= nc < w:
                            out[nr, nc] = obj.color
                return out
            return fn
        op = SynthesizedOperator(
            operator_id=f"obj_propshift_{uuid.uuid4().hex[:8]}",
            operator_family=f"object_shift_by_{prop_name}",
            parameters={"map": {str(k): list(v) for k, v in frozen_map.items()}},
            preconditions=[],
            execute=make_prop_shift(frozen_map, prop_name),
            explanation=f"Move each object by ({prop_name}→displacement)",
            source_failure_signature={},
        )
        if _check_train(op, train_pairs):
            results.append(op)
            return results

    return results


def _hypothesize_object_filtering(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    timeout: float,
) -> List[SynthesizedOperator]:
    """Discover object filtering rules: keep/remove objects by property."""
    start = time.time()
    results = []

    for inp, out in train_pairs:
        if inp.shape != out.shape:
            return []

    # For each training pair, which input objects survive in output?
    survival_per_pair = []
    for inp, out in train_pairs:
        in_objs = _extract_objects(inp, bg=0)
        out_objs = _extract_objects(out, bg=0)
        pairs = _match_objects(in_objs, out_objs, inp, out)
        survived = []
        removed = []
        for io, oo in pairs:
            if io is None:
                continue
            if oo is not None:
                io_rel = frozenset((r - io.bbox[0], c - io.bbox[2]) for r, c in io.pixels)
                oo_rel = frozenset((r - oo.bbox[0], c - oo.bbox[2]) for r, c in oo.pixels)
                if io_rel == oo_rel and io.color == oo.color:
                    survived.append(io)
                else:
                    removed.append(io)
            else:
                removed.append(io)
        survival_per_pair.append((survived, removed))

    if not survival_per_pair:
        return []

    # Try filtering by each property
    for prop_name, prop_fn in [
        ("color", lambda o: o.color),
        ("area", lambda o: o.area),
        ("is_largest", lambda o: "__largest__"),
        ("is_smallest", lambda o: "__smallest__"),
    ]:
        # Determine which property values survive vs get removed
        if prop_name in ("is_largest", "is_smallest"):
            consistent = True
            keep_extreme = prop_name
            for survived, removed in survival_per_pair:
                all_objs = survived + removed
                if not all_objs:
                    consistent = False
                    break
                if keep_extreme == "is_largest":
                    max_area = max(o.area for o in all_objs)
                    expected_survived = [o for o in all_objs if o.area == max_area]
                    expected_removed = [o for o in all_objs if o.area != max_area]
                else:
                    min_area = min(o.area for o in all_objs)
                    expected_survived = [o for o in all_objs if o.area == min_area]
                    expected_removed = [o for o in all_objs if o.area != min_area]
                if set(o.obj_id for o in survived) != set(o.obj_id for o in expected_survived):
                    consistent = False
                    break
            if consistent:
                def make_filter_extreme(keep):
                    def fn(grid, _keep=keep):
                        objs = _extract_objects(grid, bg=0)
                        if not objs:
                            return grid.copy()
                        if _keep == "is_largest":
                            target_area = max(o.area for o in objs)
                        else:
                            target_area = min(o.area for o in objs)
                        out = np.zeros_like(grid)
                        for obj in objs:
                            if obj.area == target_area:
                                out[obj.mask] = obj.color
                        return out
                    return fn
                op = SynthesizedOperator(
                    operator_id=f"obj_filter_{uuid.uuid4().hex[:8]}",
                    operator_family=f"object_keep_{keep_extreme}",
                    parameters={},
                    preconditions=[],
                    execute=make_filter_extreme(keep_extreme),
                    explanation=f"Keep only {keep_extreme.replace('is_', '')} object(s)",
                    source_failure_signature={},
                )
                if _check_train(op, train_pairs):
                    results.append(op)
                    return results
        else:
            # Determine kept property values
            kept_vals = None
            consistent = True
            for survived, removed in survival_per_pair:
                s_vals = set(prop_fn(o) for o in survived)
                r_vals = set(prop_fn(o) for o in removed)
                if s_vals & r_vals:
                    consistent = False
                    break
                if kept_vals is None:
                    kept_vals = s_vals
                elif kept_vals != s_vals:
                    consistent = False
                    break
            if consistent and kept_vals:
                frozen_vals = frozenset(kept_vals)
                def make_filter(vals, prop):
                    def fn(grid, _vals=vals, _prop=prop):
                        objs = _extract_objects(grid, bg=0)
                        out = np.zeros_like(grid)
                        for obj in objs:
                            val = obj.color if _prop == "color" else obj.area
                            if val in _vals:
                                out[obj.mask] = obj.color
                        return out
                    return fn
                op = SynthesizedOperator(
                    operator_id=f"obj_filter_{uuid.uuid4().hex[:8]}",
                    operator_family=f"object_filter_by_{prop_name}",
                    parameters={"keep": sorted(kept_vals)},
                    preconditions=[],
                    execute=make_filter(frozen_vals, prop_name),
                    explanation=f"Keep objects where {prop_name} in {sorted(kept_vals)}",
                    source_failure_signature={},
                )
                if _check_train(op, train_pairs):
                    results.append(op)
                    return results

    if time.time() - start > timeout:
        return results

    # Try: output = input with specific objects removed (by color)
    removed_colors_per_pair = []
    for inp, out in train_pairs:
        if not np.array_equal(inp.shape, out.shape):
            return []
        diff = inp != out
        changed_to_bg = diff & (out == 0)
        changed_from_bg = diff & (inp == 0)
        if changed_from_bg.any():
            continue
        removed_colors = set(np.unique(inp[changed_to_bg]).tolist())
        removed_colors_per_pair.append(removed_colors)

    if len(removed_colors_per_pair) == len(train_pairs) and removed_colors_per_pair:
        common_removed = removed_colors_per_pair[0]
        for rc in removed_colors_per_pair[1:]:
            common_removed &= rc
        if common_removed:
            frozen_rm = frozenset(common_removed)
            def make_remove_colors(cols):
                def fn(grid, _cols=cols):
                    out = grid.copy()
                    for c in _cols:
                        out[out == c] = 0
                    return out
                return fn
            op = SynthesizedOperator(
                operator_id=f"obj_rmcolor_{uuid.uuid4().hex[:8]}",
                operator_family="object_remove_colors",
                parameters={"colors": sorted(common_removed)},
                preconditions=[],
                execute=make_remove_colors(frozen_rm),
                explanation=f"Remove all pixels of colors {sorted(common_removed)}",
                source_failure_signature={},
            )
            if _check_train(op, train_pairs):
                results.append(op)
                return results

    return results


def _hypothesize_object_recolor(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    timeout: float,
) -> List[SynthesizedOperator]:
    """Discover object recoloring rules: objects change color based on a property."""
    results = []

    for inp, out in train_pairs:
        if inp.shape != out.shape:
            return []

    # For each pair, find object color changes
    recolor_maps = []
    for inp, out in train_pairs:
        in_objs = _extract_objects(inp, bg=0)
        out_objs = _extract_objects(out, bg=0)
        pairs = _match_objects(in_objs, out_objs, inp, out)
        rmap = {}
        for io, oo in pairs:
            if io is None or oo is None:
                continue
            io_rel = frozenset((r - io.bbox[0], c - io.bbox[2]) for r, c in io.pixels)
            oo_rel = frozenset((r - oo.bbox[0], c - oo.bbox[2]) for r, c in oo.pixels)
            if io_rel == oo_rel and io.color != oo.color:
                if io.color in rmap and rmap[io.color] != oo.color:
                    rmap = None
                    break
                rmap[io.color] = oo.color
        if rmap is None:
            return []
        recolor_maps.append(rmap)

    if not recolor_maps:
        return []

    # Check consistency across pairs
    merged = {}
    for rm in recolor_maps:
        for k, v in rm.items():
            if k in merged and merged[k] != v:
                return []
            merged[k] = v

    if not merged:
        return []

    frozen_map = dict(merged)
    def make_recolor(cmap):
        def fn(grid, _cmap=cmap):
            out = grid.copy()
            for src, tgt in _cmap.items():
                out[grid == src] = tgt
            return out
        return fn
    op = SynthesizedOperator(
        operator_id=f"obj_recolor_{uuid.uuid4().hex[:8]}",
        operator_family="object_recolor",
        parameters={"map": frozen_map},
        preconditions=[],
        execute=make_recolor(frozen_map),
        explanation=f"Recolor objects: {frozen_map}",
        source_failure_signature={},
    )
    if _check_train(op, train_pairs):
        results.append(op)

    return results


def _hypothesize_object_stamp(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    timeout: float,
) -> List[SynthesizedOperator]:
    """Discover stamp/copy rules: a template object is placed at marker positions."""
    start = time.time()
    results = []

    for inp, out in train_pairs:
        if inp.shape != out.shape:
            return []

    # Find objects in input — look for a "template" and "markers"
    for inp, out in train_pairs[:1]:
        in_objs = _extract_objects(inp, bg=0)
        if len(in_objs) < 2:
            return []

        # Group by shape
        shape_groups: Dict[frozenset, List[GridObject]] = defaultdict(list)
        for obj in in_objs:
            rel = frozenset((r - obj.bbox[0], c - obj.bbox[2]) for r, c in obj.pixels)
            shape_groups[rel].append(obj)

        # Try each object as template, single-pixel objects as markers
        single_pixel_objs = [o for o in in_objs if o.area == 1]
        multi_pixel_objs = [o for o in in_objs if o.area > 1]

        if not single_pixel_objs or not multi_pixel_objs:
            return []

        # Group markers by color
        marker_colors = defaultdict(list)
        for sp in single_pixel_objs:
            marker_colors[sp.color].append(sp)

        for template in multi_pixel_objs:
            if time.time() - start > timeout:
                return results

            # Template relative shape
            t_rel = [(r - template.bbox[0], c - template.bbox[2])
                     for r, c in template.pixels]

            for marker_color, markers in marker_colors.items():
                if marker_color == template.color:
                    continue

                # Check: in output, does the template shape appear at each marker position?
                all_pairs_ok = True
                stamp_color = None

                for inp_p, out_p in train_pairs:
                    p_in_objs = _extract_objects(inp_p, bg=0)
                    p_markers = [o for o in p_in_objs
                                 if o.area == 1 and o.color == marker_color]
                    p_templates = [o for o in p_in_objs if o.area > 1]

                    # Find which template matches
                    t_match = None
                    for t in p_templates:
                        t_r = frozenset((r - t.bbox[0], c - t.bbox[2])
                                        for r, c in t.pixels)
                        orig_r = frozenset(t_rel)
                        if t_r == orig_r and t.color == template.color:
                            t_match = t
                            break
                    if t_match is None:
                        all_pairs_ok = False
                        break

                    # Check each marker: does template shape appear centered at marker?
                    for mk in p_markers:
                        mr, mc = mk.pixels[0]
                        for dr, dc in t_rel:
                            nr, nc = mr + dr, mc + dc
                            if 0 <= nr < out_p.shape[0] and 0 <= nc < out_p.shape[1]:
                                oc = out_p[nr, nc]
                                if stamp_color is None:
                                    stamp_color = oc
                                elif oc != stamp_color and oc != 0:
                                    pass  # might be marker's own color
                            else:
                                all_pairs_ok = False
                                break

                if not all_pairs_ok:
                    continue

                # Build the stamp operator
                frozen_rel = list(t_rel)
                def make_stamp(rel, t_color, m_color, s_color):
                    def fn(grid, _rel=rel, _tc=t_color, _mc=m_color, _sc=s_color):
                        out = grid.copy()
                        objs = _extract_objects(grid, bg=0)
                        markers = [o for o in objs if o.area == 1 and o.color == _mc]
                        for mk in markers:
                            mr, mc_pos = mk.pixels[0]
                            for dr, dc in _rel:
                                nr, nc = mr + dr, mc_pos + dc
                                if 0 <= nr < out.shape[0] and 0 <= nc < out.shape[1]:
                                    if out[nr, nc] == 0 or out[nr, nc] == _mc:
                                        out[nr, nc] = _sc if _sc else _mc
                        return out
                    return fn
                op = SynthesizedOperator(
                    operator_id=f"obj_stamp_{uuid.uuid4().hex[:8]}",
                    operator_family="object_stamp_at_markers",
                    parameters={"template_color": template.color,
                                "marker_color": marker_color},
                    preconditions=[],
                    execute=make_stamp(frozen_rel, template.color,
                                       marker_color, stamp_color),
                    explanation=f"Stamp template (color {template.color}) at marker positions (color {marker_color})",
                    source_failure_signature={},
                )
                if _check_train(op, train_pairs):
                    results.append(op)
                    return results

    return results


def _hypothesize_object_sort(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    timeout: float,
) -> List[SynthesizedOperator]:
    """Discover object sorting/ordering rules."""
    results = []

    for inp, out in train_pairs:
        if inp.shape != out.shape:
            return []

    # Check if objects in output are sorted by some property
    for inp, out in train_pairs[:1]:
        in_objs = _extract_objects(inp, bg=0)
        out_objs = _extract_objects(out, bg=0)
        if len(in_objs) != len(out_objs) or len(in_objs) < 2:
            return []

    # Try sorting by area, color
    for sort_key, key_fn, axis in [
        ("area_row", lambda o: o.area, "row"),
        ("area_col", lambda o: o.area, "col"),
        ("color_row", lambda o: o.color, "row"),
        ("color_col", lambda o: o.color, "col"),
    ]:
        consistent = True
        ascending = None
        for inp, out in train_pairs:
            in_objs = _extract_objects(inp, bg=0)
            out_objs = _extract_objects(out, bg=0)
            if len(in_objs) != len(out_objs):
                consistent = False
                break

            # Sort input objects by position
            if axis == "row":
                in_sorted = sorted(in_objs, key=lambda o: o.centroid[0])
                out_sorted = sorted(out_objs, key=lambda o: o.centroid[0])
            else:
                in_sorted = sorted(in_objs, key=lambda o: o.centroid[1])
                out_sorted = sorted(out_objs, key=lambda o: o.centroid[1])

            out_keys = [key_fn(o) for o in out_sorted]
            if ascending is None:
                ascending = out_keys == sorted(out_keys)
                if not ascending and out_keys != sorted(out_keys, reverse=True):
                    consistent = False
                    break
            else:
                if ascending and out_keys != sorted(out_keys):
                    consistent = False
                    break
                if not ascending and out_keys != sorted(out_keys, reverse=True):
                    consistent = False
                    break

        if not consistent:
            continue

        prop = sort_key.split("_")[0]
        frozen_axis = axis
        frozen_asc = ascending
        def make_sort(prop_name, ax, asc):
            def fn(grid, _prop=prop_name, _ax=ax, _asc=asc):
                objs = _extract_objects(grid, bg=0)
                if len(objs) < 2:
                    return grid.copy()
                if _ax == "row":
                    positions = sorted(set(round(o.centroid[0]) for o in objs))
                else:
                    positions = sorted(set(round(o.centroid[1]) for o in objs))
                kf = (lambda o: o.area) if _prop == "area" else (lambda o: o.color)
                sorted_objs = sorted(objs, key=kf, reverse=not _asc)
                out = np.zeros_like(grid)
                for obj, pos in zip(sorted_objs, positions):
                    rel = [(r - round(obj.centroid[0 if _ax == "row" else 1]),
                            c - round(obj.centroid[1 if _ax == "row" else 0]))
                           for r, c in obj.pixels]
                    for dr, dc in rel:
                        if _ax == "row":
                            nr, nc = pos + dr, round(obj.centroid[1]) + dc
                        else:
                            nr, nc = round(obj.centroid[0]) + dr, pos + dc
                        if 0 <= nr < grid.shape[0] and 0 <= nc < grid.shape[1]:
                            out[nr, nc] = obj.color
                return out
            return fn
        op = SynthesizedOperator(
            operator_id=f"obj_sort_{uuid.uuid4().hex[:8]}",
            operator_family=f"object_sort_{sort_key}",
            parameters={"ascending": frozen_asc},
            preconditions=[],
            execute=make_sort(prop, frozen_axis, frozen_asc),
            explanation=f"Sort objects by {prop} along {frozen_axis} ({'asc' if frozen_asc else 'desc'})",
            source_failure_signature={},
        )
        if _check_train(op, train_pairs):
            results.append(op)
            return results

    return results


def _hypothesize_object_crop(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    timeout: float,
) -> List[SynthesizedOperator]:
    """Discover crop-to-object rules: output is a cropped region around an object."""
    results = []

    # Check if output is smaller than input (cropping)
    for inp, out in train_pairs:
        if out.shape[0] >= inp.shape[0] and out.shape[1] >= inp.shape[1]:
            return []

    # Try: output = bounding box of largest/smallest/specific-color object
    for criterion, desc in [
        ("largest", "largest"),
        ("smallest", "smallest"),
    ]:
        consistent = True
        for inp, out in train_pairs:
            in_objs = _extract_objects(inp, bg=0)
            if not in_objs:
                consistent = False
                break
            if criterion == "largest":
                target = max(in_objs, key=lambda o: o.area)
            else:
                target = min(in_objs, key=lambda o: o.area)
            r0, r1, c0, c1 = target.bbox
            cropped = inp[r0:r1+1, c0:c1+1]
            if not np.array_equal(cropped, out):
                consistent = False
                break

        if consistent:
            def make_crop(crit):
                def fn(grid, _crit=crit):
                    objs = _extract_objects(grid, bg=0)
                    if not objs:
                        return grid.copy()
                    if _crit == "largest":
                        target = max(objs, key=lambda o: o.area)
                    else:
                        target = min(objs, key=lambda o: o.area)
                    r0, r1, c0, c1 = target.bbox
                    return grid[r0:r1+1, c0:c1+1].copy()
                return fn
            op = SynthesizedOperator(
                operator_id=f"obj_crop_{uuid.uuid4().hex[:8]}",
                operator_family=f"object_crop_{desc}",
                parameters={},
                preconditions=[],
                execute=make_crop(criterion),
                explanation=f"Crop to {desc} object bounding box",
                source_failure_signature={},
            )
            if _check_train(op, train_pairs):
                results.append(op)
                return results

    # Try: output = bounding box of specific color
    for color in range(1, 10):
        consistent = True
        for inp, out in train_pairs:
            in_objs = [o for o in _extract_objects(inp, bg=0) if o.color == color]
            if not in_objs:
                consistent = False
                break
            # Combined bounding box of all objects with this color
            r0 = min(o.bbox[0] for o in in_objs)
            r1 = max(o.bbox[1] for o in in_objs)
            c0 = min(o.bbox[2] for o in in_objs)
            c1 = max(o.bbox[3] for o in in_objs)
            cropped = inp[r0:r1+1, c0:c1+1]
            if not np.array_equal(cropped, out):
                consistent = False
                break
        if consistent:
            def make_crop_color(c):
                def fn(grid, _c=c):
                    objs = [o for o in _extract_objects(grid, bg=0) if o.color == _c]
                    if not objs:
                        return grid.copy()
                    r0 = min(o.bbox[0] for o in objs)
                    r1 = max(o.bbox[1] for o in objs)
                    c0 = min(o.bbox[2] for o in objs)
                    c1 = max(o.bbox[3] for o in objs)
                    return grid[r0:r1+1, c0:c1+1].copy()
                return fn
            op = SynthesizedOperator(
                operator_id=f"obj_crop_{uuid.uuid4().hex[:8]}",
                operator_family=f"object_crop_color_{color}",
                parameters={"color": color},
                preconditions=[],
                execute=make_crop_color(color),
                explanation=f"Crop to bounding box of color {color}",
                source_failure_signature={},
            )
            if _check_train(op, train_pairs):
                results.append(op)
                return results

    return results


def _check_train(op: SynthesizedOperator,
                 train_pairs: List[Tuple[np.ndarray, np.ndarray]]) -> bool:
    """Verify operator on all training pairs."""
    for inp, out in train_pairs:
        try:
            pred = op.execute(inp)
            if pred is None or not isinstance(pred, np.ndarray):
                return False
            if pred.shape != out.shape or not np.array_equal(pred, out):
                return False
        except Exception:
            return False
    return True


# ===================================================================
# MAIN ENTRY POINT
# ===================================================================

def reason_spatially(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    timeout_seconds: float = 30.0,
    task_id: str = "",
) -> List[SynthesizedOperator]:
    """Main entry: run all spatial reasoning hypotheses.

    The system reasons through hypotheses in order of likelihood,
    informed by spatial memory from previously solved tasks.
    """
    start = time.time()
    verified = []

    # Check memory for suggested strategy order
    spatial_features = {}
    inp0, out0 = train_pairs[0]
    if inp0.shape == out0.shape:
        spatial_features["same_size"] = True
        diff = inp0 != out0
        spatial_features["change_count"] = int(diff.sum())
        spatial_features["only_bg_changed"] = all(
            inp0[r, c] == 0 for r, c in zip(*np.where(diff))
        ) if diff.any() else False

    suggested = _spatial_memory.suggest_order(spatial_features)

    # Build hypothesis list
    hypothesis_fns = [
        ("object_movement", _hypothesize_object_movement),
        ("object_filtering", _hypothesize_object_filtering),
        ("object_recolor", _hypothesize_object_recolor),
        ("object_stamp", _hypothesize_object_stamp),
        ("object_sort", _hypothesize_object_sort),
        ("object_crop", _hypothesize_object_crop),
        ("containment_fill", _hypothesize_containment_fill),
        ("stamp_pattern", _hypothesize_stamp_pattern),
        ("line_extension", _hypothesize_line_extension),
        ("arrow_directed_fill", _hypothesize_arrow_directed_fill),
        ("nearest_object_fill", _hypothesize_nearest_object_fill),
        ("row_col_intersection", _hypothesize_row_col_object_intersection),
        ("flood_fill_adjacent", _hypothesize_flood_fill_from_objects),
        ("component_coloring", _hypothesize_component_coloring),
        ("gestalt_recolor", _hypothesize_gestalt_property_recolor),
        ("template_transfer", _hypothesize_template_transfer),
        ("gestalt_then_fill", _hypothesize_gestalt_then_fill),
    ]

    # Reorder based on memory suggestions
    if suggested:
        def priority(name):
            try:
                return suggested.index(name)
            except ValueError:
                return len(suggested)
        hypothesis_fns.sort(key=lambda x: priority(x[0]))

    for hyp_name, hyp_fn in hypothesis_fns:
        if time.time() - start > timeout_seconds:
            break
        remaining = timeout_seconds - (time.time() - start)
        try:
            ops = hyp_fn(train_pairs, min(remaining, 5.0))
            for op in ops:
                verified.append(op)
                # Store in spatial memory
                _spatial_memory.store(
                    hyp_name,
                    str(spatial_features),
                    op.operator_family,
                    task_id,
                )
        except Exception:
            continue

    return verified
