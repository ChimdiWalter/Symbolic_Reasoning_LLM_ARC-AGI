"""Multi-color object decomposition for ARC grids.

Provides three complementary object views:
  1. Color components  -- per-color connected components
  2. Silhouette components -- color-agnostic (any non-bg touching = one object)
  3. Part-whole decomposition -- silhouettes with per-color sub-parts

Plus higher-level detectors:
  - Containment
  - Same-Different shape grouping (with rotation/reflection invariance)
  - Ordering (spatial, size, frequency)

And a MultiColorGridAdapter that plugs into StructuralReasoner.
"""
from __future__ import annotations

import abc
import numpy as np
from scipy import ndimage
from scipy.optimize import linear_sum_assignment
from typing import Optional, List, Tuple, Dict, Any, Set, NamedTuple
from dataclasses import dataclass, field


# ═══════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class CompositeObject:
    """A silhouette-level object with its per-color sub-parts."""
    silhouette_mask: np.ndarray        # full-grid boolean mask
    parts: List[Dict[str, Any]]        # per-color sub-masks within this silhouette
    colors: Set[int]                   # set of non-bg colors present
    n_parts: int = 0
    is_multicolor: bool = False
    primary_color: int = 0             # most frequent color
    area: int = 0
    bbox: Tuple[int, int, int, int] = (0, 0, 0, 0)  # (r_min, c_min, r_max, c_max)
    center_r: float = 0.0
    center_c: float = 0.0
    local_mask: np.ndarray = field(default_factory=lambda: np.zeros((1, 1), dtype=bool))

    def __post_init__(self):
        rows, cols = np.where(self.silhouette_mask)
        if len(rows) > 0:
            r_min, r_max = int(rows.min()), int(rows.max())
            c_min, c_max = int(cols.min()), int(cols.max())
            self.bbox = (r_min, c_min, r_max, c_max)
            self.center_r = float(rows.mean())
            self.center_c = float(cols.mean())
            self.area = int(self.silhouette_mask.sum())
            self.local_mask = self.silhouette_mask[r_min:r_max+1, c_min:c_max+1]
        self.n_parts = len(self.parts)
        self.is_multicolor = len(self.colors) > 1
        if self.parts:
            best = max(self.parts, key=lambda p: p["area"])
            self.primary_color = best["color"]


@dataclass
class ShapeGroup:
    """A group of objects with equivalent shape (up to rotation/reflection)."""
    members: List[int]          # indices into the object list
    equivalence_type: str       # 'exact', 'rotation', 'reflection', or 'rotation+reflection'


# ═══════════════════════════════════════════════════════════════════════════
# 1. COLOR COMPONENT EXTRACTION (per-color CCs)
# ═══════════════════════════════════════════════════════════════════════════

def extract_color_components(
    grid: np.ndarray, bg: int = 0
) -> List[Dict[str, Any]]:
    """Extract per-color connected components.

    For each non-background color, finds connected components of that color.
    Returns a list of object dicts, each with:
        mask, local_mask, color, area, bbox, center_r, center_c
    """
    h, w = grid.shape
    objects: List[Dict[str, Any]] = []
    colors_present = set(grid.flat) - {bg}

    for color in sorted(colors_present):
        color_mask = grid == color
        labeled, n = ndimage.label(color_mask)
        for lab in range(1, n + 1):
            obj_mask = labeled == lab
            rows, cols = np.where(obj_mask)
            if len(rows) == 0:
                continue
            r_min, r_max = int(rows.min()), int(rows.max())
            c_min, c_max = int(cols.min()), int(cols.max())
            area = int(obj_mask.sum())
            local_mask = obj_mask[r_min:r_max+1, c_min:c_max+1]
            objects.append({
                "mask": obj_mask,
                "local_mask": local_mask,
                "color": int(color),
                "primary_color": int(color),
                "area": area,
                "bbox": (r_min, c_min, r_max, c_max),
                "bbox_h": r_max - r_min + 1,
                "bbox_w": c_max - c_min + 1,
                "center_r": float(rows.mean()),
                "center_c": float(cols.mean()),
                "n_colors": 1,
                "colors": [int(color)],
                "is_multicolor": False,
            })

    return objects


# ═══════════════════════════════════════════════════════════════════════════
# 2. SILHOUETTE COMPONENT EXTRACTION (color-agnostic CCs)
# ═══════════════════════════════════════════════════════════════════════════

def extract_silhouette_components(
    grid: np.ndarray, bg: int = 0
) -> List[Dict[str, Any]]:
    """Extract color-agnostic connected components.

    Any non-background cells touching (4-connectivity) form one object,
    regardless of color. Each returned object may contain multiple colors.
    """
    h, w = grid.shape
    mask = grid != bg
    labeled, n = ndimage.label(mask)
    objects: List[Dict[str, Any]] = []

    for lab in range(1, n + 1):
        obj_mask = labeled == lab
        rows, cols = np.where(obj_mask)
        if len(rows) == 0:
            continue
        r_min, r_max = int(rows.min()), int(rows.max())
        c_min, c_max = int(cols.min()), int(cols.max())
        area = int(obj_mask.sum())
        local_mask = obj_mask[r_min:r_max+1, c_min:c_max+1]

        # Determine colors within this silhouette
        vals = grid[obj_mask]
        colors_in_obj = sorted(set(vals.tolist()) - {bg})
        # Primary color = most frequent non-bg color
        if len(colors_in_obj) > 0:
            color_counts = {c: int(np.sum(vals == c)) for c in colors_in_obj}
            primary_color = max(color_counts, key=color_counts.get)
        else:
            primary_color = 0

        objects.append({
            "mask": obj_mask,
            "local_mask": local_mask,
            "color": primary_color,
            "primary_color": primary_color,
            "area": area,
            "bbox": (r_min, c_min, r_max, c_max),
            "bbox_h": r_max - r_min + 1,
            "bbox_w": c_max - c_min + 1,
            "center_r": float(rows.mean()),
            "center_c": float(cols.mean()),
            "n_colors": len(colors_in_obj),
            "colors": colors_in_obj,
            "is_multicolor": len(colors_in_obj) > 1,
        })

    return objects


# ═══════════════════════════════════════════════════════════════════════════
# 3. PART-WHOLE DECOMPOSITION
# ═══════════════════════════════════════════════════════════════════════════

def extract_part_whole(
    grid: np.ndarray, bg: int = 0
) -> List[CompositeObject]:
    """Build a part-whole graph: silhouettes with per-color sub-parts.

    For each silhouette component, extract per-color connected components
    within it to find sub-parts.
    """
    h, w = grid.shape
    silhouettes = extract_silhouette_components(grid, bg=bg)
    composites: List[CompositeObject] = []

    for sil in silhouettes:
        sil_mask = sil["mask"]
        colors_in_sil = set(sil["colors"])
        parts: List[Dict[str, Any]] = []

        for color in sorted(colors_in_sil):
            # Mask of this color within this silhouette
            color_within = sil_mask & (grid == color)
            labeled, n = ndimage.label(color_within)
            for lab in range(1, n + 1):
                part_mask = labeled == lab
                area = int(part_mask.sum())
                rows, cols = np.where(part_mask)
                if len(rows) == 0:
                    continue
                r_min, r_max = int(rows.min()), int(rows.max())
                c_min, c_max = int(cols.min()), int(cols.max())
                parts.append({
                    "mask": part_mask,
                    "local_mask": part_mask[r_min:r_max+1, c_min:c_max+1],
                    "color": int(color),
                    "area": area,
                    "bbox": (r_min, c_min, r_max, c_max),
                    "center_r": float(rows.mean()),
                    "center_c": float(cols.mean()),
                })

        comp = CompositeObject(
            silhouette_mask=sil_mask,
            parts=parts,
            colors=colors_in_sil,
        )
        composites.append(comp)

    return composites


# ═══════════════════════════════════════════════════════════════════════════
# 4. CONTAINMENT DETECTION
# ═══════════════════════════════════════════════════════════════════════════

def detect_containment(
    objects: List[Dict[str, Any]],
) -> List[Tuple[int, int]]:
    """Detect containment relationships between objects.

    Object A contains B if B's bounding box is strictly inside A's bounding box
    AND all of B's mask pixels fall within A's bounding box (with 0-margin).

    Args:
        objects: list of dicts each having 'mask' and 'bbox' keys.
            For CompositeObject, pass their dict representations.

    Returns:
        List of (container_idx, contained_idx) pairs.
    """
    n = len(objects)
    containment: List[Tuple[int, int]] = []

    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            # Get bboxes
            bbox_i = _get_bbox(objects[i])
            bbox_j = _get_bbox(objects[j])
            ir1, ic1, ir2, ic2 = bbox_i
            jr1, jc1, jr2, jc2 = bbox_j

            # j is strictly inside i's bbox
            if ir1 < jr1 and ic1 < jc1 and ir2 > jr2 and ic2 > jc2:
                # Verify all of j's mask pixels are within i's bbox
                mask_j = _get_mask(objects[j])
                rows, cols = np.where(mask_j)
                if len(rows) > 0:
                    if (rows.min() > ir1 and rows.max() < ir2 and
                            cols.min() > ic1 and cols.max() < ic2):
                        containment.append((i, j))

    return containment


def _get_bbox(obj) -> Tuple[int, int, int, int]:
    """Extract bbox from either a dict or a CompositeObject."""
    if isinstance(obj, CompositeObject):
        return obj.bbox
    return obj.get("bbox", (0, 0, 0, 0))


def _get_mask(obj) -> np.ndarray:
    """Extract mask from either a dict or a CompositeObject."""
    if isinstance(obj, CompositeObject):
        return obj.silhouette_mask
    return obj.get("mask", np.zeros((1, 1), dtype=bool))


# ═══════════════════════════════════════════════════════════════════════════
# 5. SAME-DIFFERENT DETECTION
# ═══════════════════════════════════════════════════════════════════════════

def _canonical_rotations_reflections(mask: np.ndarray) -> List[np.ndarray]:
    """Generate all 8 rotation/reflection variants of a binary mask."""
    variants = []
    m = mask
    for _ in range(4):
        variants.append(m)
        variants.append(np.fliplr(m))
        m = np.rot90(m)
    return variants


def _shapes_equivalent(
    mask_a: np.ndarray, mask_b: np.ndarray
) -> Optional[str]:
    """Check if two local binary masks are equivalent under rotation/reflection.

    Returns equivalence type string or None if not equivalent.
    """
    a = mask_a.astype(bool)
    b = mask_b.astype(bool)

    # Exact match
    if a.shape == b.shape and np.array_equal(a, b):
        return "exact"

    # Try 4 rotations
    m = a
    for rot in range(1, 4):
        m = np.rot90(m)
        if m.shape == b.shape and np.array_equal(m, b):
            return "rotation"

    # Try reflections
    for flip_fn in [np.fliplr, np.flipud]:
        fa = flip_fn(a)
        if fa.shape == b.shape and np.array_equal(fa, b):
            return "reflection"
        m = fa
        for rot in range(1, 4):
            m = np.rot90(m)
            if m.shape == b.shape and np.array_equal(m, b):
                return "rotation+reflection"

    return None


def detect_same_different(
    objects: List[Dict[str, Any]],
) -> List[ShapeGroup]:
    """Group objects by structural equivalence.

    Checks shape equivalence (exact, rotation, reflection), color, and size.
    Returns list of ShapeGroup with members and equivalence type.
    """
    n = len(objects)
    if n == 0:
        return []

    # Extract local masks
    local_masks = []
    for obj in objects:
        if isinstance(obj, CompositeObject):
            local_masks.append(obj.local_mask.astype(bool))
        else:
            local_masks.append(obj.get("local_mask", np.zeros((1, 1), dtype=bool)).astype(bool))

    # Build shape groups
    assigned = [False] * n
    groups: List[ShapeGroup] = []

    for i in range(n):
        if assigned[i]:
            continue
        members = [i]
        eq_type = "exact"
        assigned[i] = True

        for j in range(i + 1, n):
            if assigned[j]:
                continue
            result = _shapes_equivalent(local_masks[i], local_masks[j])
            if result is not None:
                members.append(j)
                assigned[j] = True
                # Track the weakest equivalence type in the group
                if result != "exact":
                    eq_type = result

        groups.append(ShapeGroup(members=members, equivalence_type=eq_type))

    return groups


# ═══════════════════════════════════════════════════════════════════════════
# 6. ORDERING DETECTION
# ═══════════════════════════════════════════════════════════════════════════

def detect_ordering(
    objects: List[Dict[str, Any]],
) -> Optional[List[Dict[str, Any]]]:
    """Detect if objects form a clear spatial or size ordering.

    Checks:
        - Left-to-right (by center_c)
        - Top-to-bottom (by center_r)
        - By size (area, ascending)
        - By color frequency

    Returns a list of dicts with ordering info, or None if < 2 objects.
    """
    n = len(objects)
    if n < 2:
        return None

    def _get_center_c(obj):
        if isinstance(obj, CompositeObject):
            return obj.center_c
        return obj.get("center_c", 0.0)

    def _get_center_r(obj):
        if isinstance(obj, CompositeObject):
            return obj.center_r
        return obj.get("center_r", 0.0)

    def _get_area(obj):
        if isinstance(obj, CompositeObject):
            return obj.area
        return obj.get("area", 0)

    def _get_color(obj):
        if isinstance(obj, CompositeObject):
            return obj.primary_color
        return obj.get("primary_color", 0)

    orderings: List[Dict[str, Any]] = []

    # Left-to-right
    lr_order = sorted(range(n), key=lambda i: _get_center_c(objects[i]))
    orderings.append({
        "type": "left_to_right",
        "order": lr_order,
        "key": "center_c",
    })

    # Top-to-bottom
    tb_order = sorted(range(n), key=lambda i: _get_center_r(objects[i]))
    orderings.append({
        "type": "top_to_bottom",
        "order": tb_order,
        "key": "center_r",
    })

    # By size (ascending)
    size_order = sorted(range(n), key=lambda i: _get_area(objects[i]))
    orderings.append({
        "type": "by_size_asc",
        "order": size_order,
        "key": "area",
    })

    # By color frequency (ascending)
    color_freq: Dict[int, int] = {}
    for obj in objects:
        c = _get_color(obj)
        color_freq[c] = color_freq.get(c, 0) + 1
    freq_order = sorted(range(n), key=lambda i: color_freq.get(_get_color(objects[i]), 0))
    orderings.append({
        "type": "by_color_frequency",
        "order": freq_order,
        "key": "color_frequency",
    })

    return orderings


# ═══════════════════════════════════════════════════════════════════════════
# 7. OBJECT COUNTING
# ═══════════════════════════════════════════════════════════════════════════

def count_objects(
    grid: np.ndarray, mode: str = "color", bg: int = 0
) -> int:
    """Count objects using specified decomposition mode.

    Args:
        grid: 2D integer array
        mode: 'color' (per-color CCs), 'silhouette' (color-agnostic),
              or 'part_whole' (composite objects)
        bg: background value

    Returns:
        Number of objects found.
    """
    if grid.size == 0:
        return 0

    if mode == "color":
        return len(extract_color_components(grid, bg=bg))
    elif mode == "silhouette":
        return len(extract_silhouette_components(grid, bg=bg))
    elif mode == "part_whole":
        return len(extract_part_whole(grid, bg=bg))
    else:
        raise ValueError(f"Unknown mode: {mode!r}. Use 'color', 'silhouette', or 'part_whole'.")


# ═══════════════════════════════════════════════════════════════════════════
# 8. MULTI-COLOR GRID ADAPTER
# ═══════════════════════════════════════════════════════════════════════════

# Import DomainAdapter base class
from reasoning_project.reasoning_engine import DomainAdapter, _match_objects_hungarian_generic


# --- Extended property computation ---

def _compute_holes(local_mask: np.ndarray) -> int:
    """Count holes in a binary mask (background regions fully enclosed)."""
    bg_labeled, n_bg = ndimage.label(~local_mask)
    border_labels = set()
    border_labels.update(bg_labeled[0, :].tolist())
    border_labels.update(bg_labeled[-1, :].tolist())
    border_labels.update(bg_labeled[:, 0].tolist())
    border_labels.update(bg_labeled[:, -1].tolist())
    border_labels.discard(0)
    return sum(1 for lb in range(1, n_bg + 1) if lb not in border_labels)


def _compute_symmetry(local_mask: np.ndarray) -> Dict[str, bool]:
    """Compute symmetry properties of a binary mask."""
    shape_bin = local_mask.astype(int)
    h_sym = bool(np.array_equal(shape_bin, shape_bin[::-1, :]))
    v_sym = bool(np.array_equal(shape_bin, shape_bin[:, ::-1]))
    d_sym = False
    bh, bw = local_mask.shape
    if bh == bw:
        d_sym = bool(np.array_equal(shape_bin, shape_bin.T))
    return {"h_sym": h_sym, "v_sym": v_sym, "d_sym": d_sym}


def _detect_frame(composite: CompositeObject, grid: np.ndarray) -> bool:
    """Detect if a composite object has a frame structure.

    A frame = outer ring of one color, inner region of another color.
    """
    if not composite.is_multicolor or composite.n_parts < 2:
        return False

    r1, c1, r2, c2 = composite.bbox
    local_grid = grid[r1:r2+1, c1:c2+1]
    local_sil = composite.local_mask

    bh, bw = local_sil.shape
    if bh < 3 or bw < 3:
        return False

    # Build border mask (cells on the edge of the local_mask)
    border_mask = np.zeros_like(local_sil)
    for r in range(bh):
        for c in range(bw):
            if not local_sil[r, c]:
                continue
            is_border = False
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nr, nc = r + dr, c + dc
                if nr < 0 or nr >= bh or nc < 0 or nc >= bw or not local_sil[nr, nc]:
                    is_border = True
                    break
            if is_border:
                border_mask[r, c] = True

    interior_mask = local_sil & ~border_mask
    if not np.any(interior_mask):
        return False

    border_colors = set(local_grid[border_mask].tolist()) - {0}
    interior_colors = set(local_grid[interior_mask].tolist()) - {0}

    # Frame: border is one color, interior is different color(s)
    return len(border_colors) == 1 and len(interior_colors) >= 1 and border_colors != interior_colors


def _composite_to_dict(
    composite: CompositeObject,
    idx: int,
    grid: np.ndarray,
    grid_h: int,
    grid_w: int,
) -> Dict[str, Any]:
    """Convert a CompositeObject to a property dict for the adapter."""
    r_min, c_min, r_max, c_max = composite.bbox
    bbox_h = r_max - r_min + 1
    bbox_w = c_max - c_min + 1

    n_holes = _compute_holes(composite.local_mask)
    sym = _compute_symmetry(composite.local_mask)
    convexity = composite.area / max(bbox_h * bbox_w, 1)
    has_frame = _detect_frame(composite, grid)

    # Boundary touching
    touches_top = r_min == 0
    touches_bottom = r_max == grid_h - 1
    touches_left = c_min == 0
    touches_right = c_max == grid_w - 1
    touches_boundary = touches_top or touches_bottom or touches_left or touches_right

    # Perimeter
    perimeter = 0
    lm = composite.local_mask
    lh, lw = lm.shape
    for r in range(lh):
        for c in range(lw):
            if lm[r, c]:
                for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nr, nc = r + dr, c + dc
                    if nr < 0 or nr >= lh or nc < 0 or nc >= lw or not lm[nr, nc]:
                        perimeter += 1

    return {
        "label": idx,
        "mask": composite.silhouette_mask,
        "local_mask": composite.local_mask,
        "bbox": composite.bbox,
        "center_r": composite.center_r,
        "center_c": composite.center_c,
        "area": composite.area,
        "bbox_h": bbox_h,
        "bbox_w": bbox_w,
        "primary_color": composite.primary_color,
        "colors": sorted(composite.colors),
        "n_colors": len(composite.colors),
        "perimeter": perimeter,
        "n_holes": n_holes,
        "euler_char": 1 - n_holes,
        "h_sym": sym["h_sym"],
        "v_sym": sym["v_sym"],
        "d_sym": sym["d_sym"],
        "any_sym": sym["h_sym"] or sym["v_sym"] or sym["d_sym"],
        "convexity": convexity,
        "is_filled_rect": composite.area == bbox_h * bbox_w,
        "is_square": bbox_h == bbox_w,
        "touches_boundary": touches_boundary,
        "touches_top": touches_top,
        "touches_bottom": touches_bottom,
        "touches_left": touches_left,
        "touches_right": touches_right,
        "bbox_ratio": bbox_h / max(bbox_w, 1),
        # Multi-color properties
        "is_multicolor": composite.is_multicolor,
        "n_parts": composite.n_parts,
        "has_frame": has_frame,
        # Composite reference
        "_composite": composite,
    }


_MC_BOOLEAN_PROPERTIES = [
    "is_filled_rect",
    "is_square",
    "any_sym",
    "h_sym",
    "v_sym",
    "d_sym",
    "touches_boundary",
    "touches_top",
    "touches_bottom",
    "touches_left",
    "touches_right",
    "is_largest",
    "is_smallest",
    "is_unique_shape",
    "is_majority_shape",
    "is_contained",
    "is_container",
    "touches_largest",
    "is_largest_in_color_group",
    "is_unique_color",
    "in_top_half",
    "in_left_half",
    # Multi-color specific
    "is_multicolor",
    "has_frame",
    "has_holes",
    "is_symmetric",
    "is_unique_shape_rot",
    "has_matching_shape",
]

_MC_DERIVED_PREDICATES = [
    ("has_holes", lambda o: o.get("n_holes", 0) > 0),
    ("is_convex", lambda o: o.get("convexity", 0) > 0.95),
    ("is_elongated_h", lambda o: o.get("bbox_ratio", 1) > 2.0),
    ("is_elongated_v", lambda o: o.get("bbox_ratio", 1) < 0.5),
    ("multi_colored", lambda o: o.get("n_colors", 1) > 1),
    ("single_cell", lambda o: o.get("area", 0) == 1),
    ("large_object", lambda o: o.get("area", 0) > 9),
    ("is_symmetric", lambda o: o.get("any_sym", False)),
]


def _add_multicolor_relational_properties(
    objects: List[Dict[str, Any]], grid: np.ndarray, grid_h: int, grid_w: int
):
    """Add relational properties that depend on all objects collectively."""
    n = len(objects)
    if n == 0:
        return

    sizes = [o["area"] for o in objects]
    max_size = max(sizes)
    min_size = min(sizes)
    size_sorted = sorted(range(n), key=lambda i: sizes[i], reverse=True)
    largest_idx = size_sorted[0]

    # Shape groups (with rotation/reflection invariance)
    local_masks = [o["local_mask"].astype(bool) for o in objects]
    shape_groups: Dict[int, List[int]] = {}
    shape_id_map: Dict[int, int] = {}
    next_shape_id = 0

    for i in range(n):
        found = False
        for sid, members in shape_groups.items():
            ref_mask = local_masks[members[0]]
            eq = _shapes_equivalent(local_masks[i], ref_mask)
            if eq is not None:
                shape_groups[sid].append(i)
                shape_id_map[i] = sid
                found = True
                break
        if not found:
            shape_groups[next_shape_id] = [i]
            shape_id_map[i] = next_shape_id
            next_shape_id += 1

    # Containment via bounding box
    contained_by: Dict[int, int] = {}
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            ir1, ic1, ir2, ic2 = objects[i]["bbox"]
            jr1, jc1, jr2, jc2 = objects[j]["bbox"]
            if jr1 <= ir1 and jc1 <= ic1 and jr2 >= ir2 and jc2 >= ic2:
                contained_by[i] = j

    # Containment depth
    def _containment_depth(idx: int, visited: Optional[Set[int]] = None) -> int:
        if visited is None:
            visited = set()
        if idx in visited or idx not in contained_by:
            return 0
        visited.add(idx)
        return 1 + _containment_depth(contained_by[idx], visited)

    # Touching largest
    touching_largest = set()
    if n > 1:
        largest_dilated = ndimage.binary_dilation(objects[largest_idx]["mask"])
        for i in range(n):
            if i == largest_idx:
                continue
            if np.any(largest_dilated & objects[i]["mask"]):
                touching_largest.add(i)

    # Color groups
    color_groups: Dict[int, List[int]] = {}
    for i, o in enumerate(objects):
        c = o["primary_color"]
        color_groups.setdefault(c, []).append(i)

    # Assign all properties
    for i, o in enumerate(objects):
        o["is_largest"] = (i == largest_idx)
        o["is_smallest"] = (sizes[i] == min_size)
        o["size_rank"] = size_sorted.index(i)
        o["shape_group_id"] = shape_id_map[i]
        o["shape_group_size"] = len(shape_groups[shape_id_map[i]])
        o["is_unique_shape"] = o["shape_group_size"] == 1
        o["is_unique_shape_rot"] = o["shape_group_size"] == 1
        o["is_majority_shape"] = o["shape_group_size"] == max(
            len(g) for g in shape_groups.values()
        )
        o["has_matching_shape"] = o["shape_group_size"] > 1
        o["n_shape_matches"] = o["shape_group_size"] - 1
        o["is_contained"] = i in contained_by
        o["is_container"] = any(v == i for v in contained_by.values())
        o["containment_depth"] = _containment_depth(i)
        o["touches_largest"] = i in touching_largest
        o["is_largest_in_color_group"] = (
            sizes[i] == max(sizes[j] for j in color_groups[o["primary_color"]])
        )
        o["color_group_size"] = len(color_groups[o["primary_color"]])
        o["is_unique_color"] = o["color_group_size"] == 1

        # Positional
        o["in_top_half"] = o["center_r"] < grid_h / 2
        o["in_left_half"] = o["center_c"] < grid_w / 2

        # Position ranks
        o["position_rank_lr"] = sorted(
            range(n), key=lambda k: objects[k]["center_c"]
        ).index(i)
        o["position_rank_tb"] = sorted(
            range(n), key=lambda k: objects[k]["center_r"]
        ).index(i)


class MultiColorGridAdapter(DomainAdapter):
    """ARC adapter using multi-color part-whole decomposition.

    Objects are extracted as silhouette-level composites, preserving
    multi-color structure. Properties include containment, shape
    grouping with rotation invariance, and frame detection.
    """

    def __init__(self, bg: int = 0):
        self.bg = bg

    def extract_objects(self, scene: np.ndarray) -> List[Dict[str, Any]]:
        """Extract objects using part-whole decomposition."""
        h, w = scene.shape
        composites = extract_part_whole(scene, bg=self.bg)
        objects = [
            _composite_to_dict(comp, i, scene, h, w)
            for i, comp in enumerate(composites)
        ]
        _add_multicolor_relational_properties(objects, scene, h, w)
        return objects

    def property_names(self) -> List[str]:
        return _MC_BOOLEAN_PROPERTIES + [name for name, _ in _MC_DERIVED_PREDICATES]

    def get_property(self, obj: Dict, prop: str) -> bool:
        if prop in obj:
            return bool(obj[prop])
        for name, fn in _MC_DERIVED_PREDICATES:
            if name == prop:
                return fn(obj)
        return False

    def classify_kept_removed(
        self, objects: List[Dict], inp: np.ndarray, out: np.ndarray,
    ) -> Optional[Tuple[List[int], List[int]]]:
        if inp.shape != out.shape:
            return None
        kept, removed = [], []
        for i, obj in enumerate(objects):
            out_vals = out[obj["mask"]]
            if np.any(out_vals != 0):
                kept.append(i)
            else:
                removed.append(i)
        if not kept or not removed:
            return None
        return kept, removed

    def reconstruct_filtered(
        self, inp: np.ndarray, objects: List[Dict], keep_mask: List[bool],
    ) -> Optional[np.ndarray]:
        result = inp.copy()
        for obj, keep in zip(objects, keep_mask):
            if not keep:
                result[obj["mask"]] = 0
        return result

    def reconstruct_recolored(
        self, inp: np.ndarray, objects: List[Dict], label_map: Dict[int, int],
    ) -> Optional[np.ndarray]:
        result = inp.copy()
        for i, obj in enumerate(objects):
            if i in label_map:
                result[obj["mask"]] = label_map[i]
        return result

    def reconstruct_extracted(
        self, inp: np.ndarray, objects: List[Dict], keep_mask: List[bool],
    ) -> Optional[np.ndarray]:
        combined = np.zeros_like(inp, dtype=bool)
        for obj, keep in zip(objects, keep_mask):
            if keep:
                combined |= obj["mask"]
        rows, cols = np.where(combined)
        if len(rows) == 0:
            return None
        r_min, r_max = int(rows.min()), int(rows.max())
        c_min, c_max = int(cols.min()), int(cols.max())
        cropped = np.zeros((r_max - r_min + 1, c_max - c_min + 1), dtype=inp.dtype)
        crop_mask = combined[r_min:r_max+1, c_min:c_max+1]
        cropped[crop_mask] = inp[r_min:r_max+1, c_min:c_max+1][crop_mask]
        return cropped

    def scenes_equal(self, a: np.ndarray, b: np.ndarray) -> bool:
        return np.array_equal(a, b)

    def same_structure(self, a: np.ndarray, b: np.ndarray) -> bool:
        return a.shape == b.shape

    def match_objects(
        self, in_objs: List[Dict], out_objs: List[Dict],
    ) -> List[Tuple[int, int, float]]:
        return _match_objects_hungarian_generic(in_objs, out_objs)


# ═══════════════════════════════════════════════════════════════════════════
# 9. TASK SOLVER
# ═══════════════════════════════════════════════════════════════════════════

def solve_task_multicolor(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
    bg: int = 0,
) -> Optional[Tuple[List[np.ndarray], Dict[str, Any]]]:
    """Solve an ARC task using multi-color object decomposition.

    Tries multiple object views (color CCs, silhouettes, part-whole)
    and for each view tries discriminative filtering with LOO cross-validation.

    Args:
        train_pairs: list of (input_grid, output_grid)
        test_inputs: list of test input grids
        bg: background color

    Returns:
        (test_outputs, info_dict) or None if no consistent solution found.
    """
    if not train_pairs or not test_inputs:
        return None

    views = [
        ("part_whole", _extract_pw_objects),
        ("silhouette", _extract_sil_objects),
        ("color", _extract_color_objects),
    ]

    for view_name, extract_fn in views:
        result = _try_discriminative_view(
            train_pairs, test_inputs, extract_fn, view_name, bg
        )
        if result is not None:
            return result

    return None


def _extract_pw_objects(grid: np.ndarray, bg: int = 0) -> List[Dict[str, Any]]:
    """Extract part-whole objects as dicts for the solver."""
    h, w = grid.shape
    composites = extract_part_whole(grid, bg=bg)
    objects = [
        _composite_to_dict(comp, i, grid, h, w)
        for i, comp in enumerate(composites)
    ]
    _add_multicolor_relational_properties(objects, grid, h, w)
    return objects


def _extract_sil_objects(grid: np.ndarray, bg: int = 0) -> List[Dict[str, Any]]:
    """Extract silhouette objects as enriched dicts."""
    sil_objs = extract_silhouette_components(grid, bg=bg)
    h, w = grid.shape
    for i, o in enumerate(sil_objs):
        o["label"] = i
        o["is_multicolor"] = o.get("n_colors", 1) > 1
        o["n_parts"] = 1
        o["has_frame"] = False
        # Compute missing fields
        r1, c1, r2, c2 = o["bbox"]
        o["n_holes"] = _compute_holes(o["local_mask"])
        sym = _compute_symmetry(o["local_mask"])
        o.update(sym)
        o["any_sym"] = sym["h_sym"] or sym["v_sym"] or sym["d_sym"]
        o["convexity"] = o["area"] / max(o["bbox_h"] * o["bbox_w"], 1)
        o["is_filled_rect"] = o["area"] == o["bbox_h"] * o["bbox_w"]
        o["is_square"] = o["bbox_h"] == o["bbox_w"]
        o["touches_top"] = r1 == 0
        o["touches_bottom"] = r2 == h - 1
        o["touches_left"] = c1 == 0
        o["touches_right"] = c2 == w - 1
        o["touches_boundary"] = o["touches_top"] or o["touches_bottom"] or o["touches_left"] or o["touches_right"]
        o["euler_char"] = 1 - o["n_holes"]
        o["bbox_ratio"] = o["bbox_h"] / max(o["bbox_w"], 1)
        o["perimeter"] = 0  # skip expensive computation for solver speed
    _add_multicolor_relational_properties(sil_objs, grid, h, w)
    return sil_objs


def _extract_color_objects(grid: np.ndarray, bg: int = 0) -> List[Dict[str, Any]]:
    """Extract per-color objects as enriched dicts."""
    color_objs = extract_color_components(grid, bg=bg)
    h, w = grid.shape
    for i, o in enumerate(color_objs):
        o["label"] = i
        o["n_parts"] = 1
        o["has_frame"] = False
        r1, c1, r2, c2 = o["bbox"]
        o["n_holes"] = _compute_holes(o["local_mask"])
        sym = _compute_symmetry(o["local_mask"])
        o.update(sym)
        o["any_sym"] = sym["h_sym"] or sym["v_sym"] or sym["d_sym"]
        o["convexity"] = o["area"] / max(o["bbox_h"] * o["bbox_w"], 1)
        o["is_filled_rect"] = o["area"] == o["bbox_h"] * o["bbox_w"]
        o["is_square"] = o["bbox_h"] == o["bbox_w"]
        o["touches_top"] = r1 == 0
        o["touches_bottom"] = r2 == h - 1
        o["touches_left"] = c1 == 0
        o["touches_right"] = c2 == w - 1
        o["touches_boundary"] = o["touches_top"] or o["touches_bottom"] or o["touches_left"] or o["touches_right"]
        o["euler_char"] = 1 - o["n_holes"]
        o["bbox_ratio"] = o["bbox_h"] / max(o["bbox_w"], 1)
        o["perimeter"] = 0
    _add_multicolor_relational_properties(color_objs, grid, h, w)
    return color_objs


def _get_all_mc_property_names() -> List[str]:
    return _MC_BOOLEAN_PROPERTIES + [name for name, _ in _MC_DERIVED_PREDICATES]


def _get_mc_property_value(obj: Dict, prop_name: str) -> bool:
    if prop_name in obj:
        return bool(obj[prop_name])
    for name, fn in _MC_DERIVED_PREDICATES:
        if name == prop_name:
            return fn(obj)
    return False


def _try_discriminative_view(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
    extract_fn,
    view_name: str,
    bg: int = 0,
) -> Optional[Tuple[List[np.ndarray], Dict[str, Any]]]:
    """Try discriminative filtering with a specific object extraction view."""
    all_props = _get_all_mc_property_names()

    # For each property, track consistency across training pairs
    candidates = {p: {"true_keeps": True, "false_keeps": True} for p in all_props}

    for inp, out in train_pairs:
        if inp.shape != out.shape:
            return None

        objects = extract_fn(inp, bg=bg)
        if len(objects) < 2:
            return None

        # Classify kept/removed
        kept, removed = [], []
        for i, obj in enumerate(objects):
            out_vals = out[obj["mask"]]
            if np.any(out_vals != 0):
                kept.append(i)
            else:
                removed.append(i)

        if not kept or not removed:
            return None

        for prop in list(candidates.keys()):
            kept_vals = [_get_mc_property_value(objects[i], prop) for i in kept]
            removed_vals = [_get_mc_property_value(objects[i], prop) for i in removed]

            if not (all(kept_vals) and not any(removed_vals)):
                candidates[prop]["true_keeps"] = False

            if not (all(not v for v in kept_vals) and all(removed_vals)):
                candidates[prop]["false_keeps"] = False

            if not candidates[prop]["true_keeps"] and not candidates[prop]["false_keeps"]:
                del candidates[prop]

    if not candidates:
        return None

    # LOO cross-validation
    best_prop = None
    best_direction = None

    for prop, dirs in candidates.items():
        for direction in ["true_keeps", "false_keeps"]:
            if not dirs[direction]:
                continue
            # LOO: hold out each training pair, check if property still works
            loo_ok = True
            for hold_out in range(len(train_pairs)):
                other_pairs = [p for k, p in enumerate(train_pairs) if k != hold_out]
                if not other_pairs:
                    continue
                # Re-check consistency on the non-held-out pairs
                still_ok = True
                for inp, out in other_pairs:
                    objects = extract_fn(inp, bg=bg)
                    if len(objects) < 2:
                        still_ok = False
                        break
                    kept, removed = [], []
                    for i, obj in enumerate(objects):
                        out_vals = out[obj["mask"]]
                        if np.any(out_vals != 0):
                            kept.append(i)
                        else:
                            removed.append(i)
                    if not kept or not removed:
                        still_ok = False
                        break
                    if direction == "true_keeps":
                        kv = [_get_mc_property_value(objects[i], prop) for i in kept]
                        rv = [_get_mc_property_value(objects[i], prop) for i in removed]
                        if not (all(kv) and not any(rv)):
                            still_ok = False
                            break
                    else:
                        kv = [_get_mc_property_value(objects[i], prop) for i in kept]
                        rv = [_get_mc_property_value(objects[i], prop) for i in removed]
                        if not (all(not v for v in kv) and all(rv)):
                            still_ok = False
                            break
                if not still_ok:
                    loo_ok = False
                    break
            if loo_ok:
                best_prop = prop
                best_direction = direction
                break
        if best_prop is not None:
            break

    if best_prop is None:
        return None

    # Apply to test inputs
    keep_when_true = (best_direction == "true_keeps")
    test_outputs = []
    for test_inp in test_inputs:
        objects = extract_fn(test_inp, bg=bg)
        result = test_inp.copy()
        for obj in objects:
            val = _get_mc_property_value(obj, best_prop)
            should_keep = val if keep_when_true else not val
            if not should_keep:
                result[obj["mask"]] = 0
        test_outputs.append(result)

    return test_outputs, {
        "view": view_name,
        "property": best_prop,
        "keep_when_true": keep_when_true,
    }
