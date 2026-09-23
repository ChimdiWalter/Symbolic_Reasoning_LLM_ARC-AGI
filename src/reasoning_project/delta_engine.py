"""Delta Engine: rich structural differencing between input/output grid pairs.

Computes what changed, how it changed, and whether changes are consistent
across training pairs. This is the perceptual foundation for adaptive
program synthesis — the system's "eyes."

The delta representation drives hypothesis generation: instead of enumerating
all possible programs, the synthesizer uses the delta to constrain which
primitives to try.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
from scipy.optimize import linear_sum_assignment


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ObjectCorrespondence:
    """Mapping between one input object and one output object."""
    input_idx: int
    output_idx: int
    transform_type: str  # identical, moved, recolored, moved_recolored, resized, appeared, disappeared
    translation: Optional[Tuple[int, int]] = None
    color_map: Optional[Dict[int, int]] = None
    scale_factor: Optional[Tuple[float, float]] = None
    shape_preserved: bool = True
    confidence: float = 1.0


@dataclass
class PairDelta:
    """Structural delta for a single input→output pair."""
    # Pixel level
    pixels_changed: int = 0
    pixels_total: int = 0
    change_rate: float = 0.0
    changed_mask: Optional[np.ndarray] = None

    # Size level
    same_size: bool = True
    input_shape: Tuple[int, int] = (0, 0)
    output_shape: Tuple[int, int] = (0, 0)
    size_ratio: Tuple[float, float] = (1.0, 1.0)

    # Color level
    input_colors: Set[int] = field(default_factory=set)
    output_colors: Set[int] = field(default_factory=set)
    colors_added: Set[int] = field(default_factory=set)
    colors_removed: Set[int] = field(default_factory=set)
    color_map: Optional[Dict[int, int]] = None
    bg_color: int = 0

    # Object level
    input_object_count: int = 0
    output_object_count: int = 0
    correspondences: List[ObjectCorrespondence] = field(default_factory=list)
    objects_appeared: int = 0
    objects_disappeared: int = 0

    # Spatial transforms
    has_consistent_translation: bool = False
    consistent_translation: Optional[Tuple[int, int]] = None
    has_reflection: bool = False
    reflection_axis: Optional[str] = None
    has_rotation: bool = False
    rotation_angle: Optional[int] = None

    # Structural patterns
    is_crop: bool = False
    crop_rule: Optional[str] = None
    is_tile: bool = False
    tile_factor: Optional[Tuple[int, int]] = None
    is_fill: bool = False
    is_filter: bool = False
    is_recolor: bool = False
    is_global_transform: bool = False

    # Evidence
    evidence: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskDelta:
    """Cross-pair consistent delta representation for a full task."""
    pair_deltas: List[PairDelta] = field(default_factory=list)
    n_pairs: int = 0

    # Consensus properties (consistent across all pairs)
    consistent_same_size: Optional[bool] = None
    consistent_change_type: Optional[str] = None
    consistent_color_map: Optional[Dict[int, int]] = None
    consistent_translation: Optional[Tuple[int, int]] = None
    consistent_reflection: Optional[str] = None
    consistent_rotation: Optional[int] = None

    # High-level classification
    delta_type: str = "unknown"
    delta_subtypes: List[str] = field(default_factory=list)
    consistency_score: float = 0.0

    # Synthesis hints (ordered by priority)
    synthesis_hints: List[Dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Object extraction (lightweight, standalone)
# ---------------------------------------------------------------------------

def _extract_objects(grid: np.ndarray, bg: int = 0) -> List[Dict]:
    """Extract connected components as objects with basic properties."""
    from scipy.ndimage import label as ndlabel
    objects = []
    H, W = grid.shape
    for color in range(10):
        if color == bg:
            continue
        mask = grid == color
        if not mask.any():
            continue
        labeled, n = ndlabel(mask)
        for comp_id in range(1, n + 1):
            comp_mask = labeled == comp_id
            rows, cols = np.where(comp_mask)
            if len(rows) == 0:
                continue
            r0, c0 = int(rows.min()), int(cols.min())
            r1, c1 = int(rows.max()), int(cols.max())
            area = int(comp_mask.sum())
            objects.append({
                "mask": comp_mask,
                "bbox": (r0, c0, r1, c1),
                "area": area,
                "color": color,
                "center": (float(rows.mean()), float(cols.mean())),
                "local_mask": comp_mask[r0:r1+1, c0:c1+1],
                "h": r1 - r0 + 1,
                "w": c1 - c0 + 1,
            })
    objects.sort(key=lambda o: -o["area"])
    return objects


def _match_objects(in_objs: List[Dict], out_objs: List[Dict],
                   in_grid: np.ndarray, out_grid: np.ndarray,
                   bg: int = 0) -> List[ObjectCorrespondence]:
    """Match input objects to output objects using Hungarian algorithm + heuristics."""
    if not in_objs or not out_objs:
        correspondences = []
        for i in range(len(in_objs)):
            correspondences.append(ObjectCorrespondence(
                input_idx=i, output_idx=-1,
                transform_type="disappeared", confidence=1.0,
            ))
        for j in range(len(out_objs)):
            correspondences.append(ObjectCorrespondence(
                input_idx=-1, output_idx=j,
                transform_type="appeared", confidence=1.0,
            ))
        return correspondences

    n_in, n_out = len(in_objs), len(out_objs)
    cost = np.full((n_in, n_out), 1e6)

    for i, io in enumerate(in_objs):
        for j, oo in enumerate(out_objs):
            c = _object_match_cost(io, oo, in_grid, out_grid, bg)
            cost[i, j] = c

    row_ind, col_ind = linear_sum_assignment(cost)

    matched_in = set()
    matched_out = set()
    correspondences = []

    for i, j in zip(row_ind, col_ind):
        if cost[i, j] > 50.0:
            continue
        matched_in.add(i)
        matched_out.add(j)
        io, oo = in_objs[i], out_objs[j]
        corr = _classify_correspondence(i, j, io, oo, in_grid, out_grid, bg)
        correspondences.append(corr)

    for i in range(n_in):
        if i not in matched_in:
            correspondences.append(ObjectCorrespondence(
                input_idx=i, output_idx=-1,
                transform_type="disappeared", confidence=1.0,
            ))
    for j in range(n_out):
        if j not in matched_out:
            correspondences.append(ObjectCorrespondence(
                input_idx=-1, output_idx=j,
                transform_type="appeared", confidence=1.0,
            ))

    return correspondences


def _object_match_cost(io: Dict, oo: Dict, in_grid, out_grid, bg) -> float:
    """Cost of matching input object io to output object oo."""
    area_diff = abs(io["area"] - oo["area"]) / max(io["area"], oo["area"], 1)
    ci, co = io["center"], oo["center"]
    H = max(in_grid.shape[0], out_grid.shape[0])
    W = max(in_grid.shape[1], out_grid.shape[1])
    diag = max((H**2 + W**2)**0.5, 1.0)
    pos_dist = ((ci[0] - co[0])**2 + (ci[1] - co[1])**2)**0.5 / diag

    shape_sim = 0.0
    lm_i, lm_o = io["local_mask"], oo["local_mask"]
    if lm_i.shape == lm_o.shape:
        shape_sim = 1.0 - float(np.sum(lm_i != lm_o)) / max(lm_i.size, 1)
    elif io["h"] == oo["h"] and io["w"] == oo["w"]:
        shape_sim = 0.5

    color_match = 1.0 if io["color"] == oo["color"] else 0.0

    cost = (0.3 * area_diff + 0.2 * pos_dist +
            0.3 * (1.0 - shape_sim) + 0.2 * (1.0 - color_match))
    return cost * 100.0


def _classify_correspondence(i, j, io, oo, in_grid, out_grid, bg) -> ObjectCorrespondence:
    """Classify the transformation between matched objects."""
    same_pos = (io["bbox"][:2] == oo["bbox"][:2])
    same_shape = (io["local_mask"].shape == oo["local_mask"].shape and
                  np.array_equal(io["local_mask"], oo["local_mask"]))
    same_color = io["color"] == oo["color"]

    dr = oo["bbox"][0] - io["bbox"][0]
    dc = oo["bbox"][1] - io["bbox"][1]
    translation = (dr, dc) if (dr != 0 or dc != 0) else None

    color_map = None
    if not same_color:
        color_map = {io["color"]: oo["color"]}

    if same_pos and same_shape and same_color:
        ir0, ic0, ir1, ic1 = io["bbox"]
        or0, oc0, or1, oc1 = oo["bbox"]
        in_patch = in_grid[ir0:ir1+1, ic0:ic1+1]
        out_patch = out_grid[or0:or1+1, oc0:oc1+1]
        if in_patch.shape == out_patch.shape and np.array_equal(in_patch, out_patch):
            ttype = "identical"
        else:
            ttype = "recolored"
    elif same_shape and same_color and translation:
        ttype = "moved"
    elif same_shape and not same_color and translation:
        ttype = "moved_recolored"
    elif same_shape and not same_color:
        ttype = "recolored"
    elif not same_shape:
        ttype = "resized"
    else:
        ttype = "moved"

    return ObjectCorrespondence(
        input_idx=i, output_idx=j,
        transform_type=ttype,
        translation=translation,
        color_map=color_map,
        shape_preserved=same_shape,
        confidence=0.9,
    )


# ---------------------------------------------------------------------------
# Pixel-level analysis
# ---------------------------------------------------------------------------

def _detect_global_color_map(inp: np.ndarray, out: np.ndarray) -> Optional[Dict[int, int]]:
    """Check if output is a consistent color permutation of input."""
    if inp.shape != out.shape:
        return None
    cmap: Dict[int, int] = {}
    for iv, ov in zip(inp.flat, out.flat):
        iv, ov = int(iv), int(ov)
        if iv in cmap:
            if cmap[iv] != ov:
                return None
        else:
            cmap[iv] = ov
    if all(k == v for k, v in cmap.items()):
        return None
    return cmap


def _check_crop(inp: np.ndarray, out: np.ndarray, bg: int = 0) -> Optional[str]:
    """Check if output is a subregion of input."""
    ih, iw = inp.shape
    oh, ow = out.shape
    if oh > ih or ow > iw:
        return None
    for r in range(ih - oh + 1):
        for c in range(iw - ow + 1):
            if np.array_equal(inp[r:r+oh, c:c+ow], out):
                return f"crop_at_{r}_{c}"
    nonbg = np.argwhere(inp != bg)
    if len(nonbg) > 0:
        r0, c0 = nonbg.min(axis=0)
        r1, c1 = nonbg.max(axis=0)
        cropped = inp[r0:r1+1, c0:c1+1]
        if cropped.shape == out.shape and np.array_equal(cropped, out):
            return "crop_to_content"
    return None


def _check_tile(inp: np.ndarray, out: np.ndarray) -> Optional[Tuple[int, int]]:
    """Check if output is a tiling of input."""
    ih, iw = inp.shape
    oh, ow = out.shape
    if oh < ih or ow < iw:
        return None
    if oh % ih != 0 or ow % iw != 0:
        return None
    th, tw = oh // ih, ow // iw
    if th == 1 and tw == 1:
        return None
    for r in range(th):
        for c in range(tw):
            patch = out[r*ih:(r+1)*ih, c*iw:(c+1)*iw]
            if not np.array_equal(patch, inp):
                return None
    return (th, tw)


def _check_reflection(inp: np.ndarray, out: np.ndarray) -> Optional[str]:
    """Check if output is a reflection of input."""
    if inp.shape != out.shape:
        return None
    if np.array_equal(inp[::-1, :], out):
        return "vertical"
    if np.array_equal(inp[:, ::-1], out):
        return "horizontal"
    if np.array_equal(inp[::-1, ::-1], out):
        return "both"
    return None


def _check_rotation(inp: np.ndarray, out: np.ndarray) -> Optional[int]:
    """Check if output is a rotation of input."""
    for angle in [90, 180, 270]:
        rotated = np.rot90(inp, k=angle // 90)
        if rotated.shape == out.shape and np.array_equal(rotated, out):
            return angle
    return None


def _check_transpose(inp: np.ndarray, out: np.ndarray) -> bool:
    """Check if output is the transpose of input."""
    return inp.T.shape == out.shape and np.array_equal(inp.T, out)


# ---------------------------------------------------------------------------
# Single-pair delta computation
# ---------------------------------------------------------------------------

def compute_pair_delta(inp: np.ndarray, out: np.ndarray, bg: int = 0) -> PairDelta:
    """Compute rich structural delta for one input→output pair."""
    delta = PairDelta()
    delta.input_shape = inp.shape
    delta.output_shape = out.shape
    delta.same_size = (inp.shape == out.shape)
    delta.bg_color = bg

    if delta.same_size:
        delta.size_ratio = (1.0, 1.0)
    else:
        delta.size_ratio = (
            out.shape[0] / max(inp.shape[0], 1),
            out.shape[1] / max(inp.shape[1], 1),
        )

    # Colors
    in_colors = set(int(v) for v in np.unique(inp))
    out_colors = set(int(v) for v in np.unique(out))
    delta.input_colors = in_colors
    delta.output_colors = out_colors
    delta.colors_added = out_colors - in_colors
    delta.colors_removed = in_colors - out_colors

    # Pixel-level changes
    if delta.same_size:
        changed = inp != out
        delta.pixels_changed = int(changed.sum())
        delta.pixels_total = int(inp.size)
        delta.change_rate = delta.pixels_changed / max(delta.pixels_total, 1)
        delta.changed_mask = changed
    else:
        delta.pixels_total = int(inp.size)
        delta.pixels_changed = delta.pixels_total
        delta.change_rate = 1.0

    # Global color map
    if delta.same_size:
        delta.color_map = _detect_global_color_map(inp, out)

    # Global transforms
    if delta.same_size and delta.pixels_changed == 0:
        delta.is_global_transform = False
    elif delta.same_size:
        ref = _check_reflection(inp, out)
        if ref:
            delta.has_reflection = True
            delta.reflection_axis = ref
            delta.is_global_transform = True

    rot = _check_rotation(inp, out)
    if rot:
        delta.has_rotation = True
        delta.rotation_angle = rot
        delta.is_global_transform = True

    if _check_transpose(inp, out):
        delta.is_global_transform = True
        delta.evidence["is_transpose"] = True

    # Crop
    if not delta.same_size and out.shape[0] <= inp.shape[0] and out.shape[1] <= inp.shape[1]:
        crop_rule = _check_crop(inp, out, bg)
        if crop_rule:
            delta.is_crop = True
            delta.crop_rule = crop_rule

    # Tile
    if not delta.same_size and out.shape[0] >= inp.shape[0] and out.shape[1] >= inp.shape[1]:
        tile = _check_tile(inp, out)
        if tile:
            delta.is_tile = True
            delta.tile_factor = tile

    # Object-level analysis
    in_objs = _extract_objects(inp, bg)
    out_objs = _extract_objects(out, bg)
    delta.input_object_count = len(in_objs)
    delta.output_object_count = len(out_objs)

    if in_objs or out_objs:
        delta.correspondences = _match_objects(in_objs, out_objs, inp, out, bg)
        delta.objects_appeared = sum(1 for c in delta.correspondences if c.transform_type == "appeared")
        delta.objects_disappeared = sum(1 for c in delta.correspondences if c.transform_type == "disappeared")

        # Check for consistent translation
        translations = [c.translation for c in delta.correspondences
                        if c.translation is not None and c.transform_type in ("moved", "moved_recolored")]
        if translations and len(set(translations)) == 1:
            delta.has_consistent_translation = True
            delta.consistent_translation = translations[0]

    # Classify recolor vs fill vs filter
    if delta.same_size and delta.color_map:
        delta.is_recolor = True

    if delta.same_size and delta.objects_disappeared > 0 and delta.objects_appeared == 0:
        delta.is_filter = True

    if delta.same_size and delta.change_rate > 0:
        changed_vals = out[delta.changed_mask] if delta.changed_mask is not None else np.array([])
        if len(changed_vals) > 0:
            unique_new = set(int(v) for v in np.unique(changed_vals))
            if len(unique_new) <= 2:
                delta.is_fill = True

    return delta


# ---------------------------------------------------------------------------
# Cross-pair consistency (TaskDelta)
# ---------------------------------------------------------------------------

def compute_task_delta(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    bg: int = 0,
) -> TaskDelta:
    """Compute cross-pair consistent delta for a full task."""
    td = TaskDelta()
    td.n_pairs = len(train_pairs)

    for inp, out in train_pairs:
        pd = compute_pair_delta(inp, out, bg)
        td.pair_deltas.append(pd)

    if not td.pair_deltas:
        return td

    # Check cross-pair consistency
    _check_size_consistency(td)
    _check_color_map_consistency(td)
    _check_translation_consistency(td)
    _check_reflection_consistency(td)
    _check_rotation_consistency(td)
    _classify_delta_type(td)
    _generate_synthesis_hints(td)

    return td


def _check_size_consistency(td: TaskDelta):
    sizes = [pd.same_size for pd in td.pair_deltas]
    if all(sizes):
        td.consistent_same_size = True
    elif not any(sizes):
        td.consistent_same_size = False
    else:
        td.consistent_same_size = None


def _check_color_map_consistency(td: TaskDelta):
    maps = [pd.color_map for pd in td.pair_deltas if pd.color_map is not None]
    if not maps:
        td.consistent_color_map = None
        return
    ref = maps[0]
    if all(m == ref for m in maps):
        td.consistent_color_map = ref
    else:
        td.consistent_color_map = None


def _check_translation_consistency(td: TaskDelta):
    trans = [pd.consistent_translation for pd in td.pair_deltas
             if pd.has_consistent_translation and pd.consistent_translation]
    if trans and len(set(trans)) == 1:
        td.consistent_translation = trans[0]


def _check_reflection_consistency(td: TaskDelta):
    axes = [pd.reflection_axis for pd in td.pair_deltas if pd.has_reflection]
    if axes and len(set(axes)) == 1 and len(axes) == td.n_pairs:
        td.consistent_reflection = axes[0]


def _check_rotation_consistency(td: TaskDelta):
    angles = [pd.rotation_angle for pd in td.pair_deltas if pd.has_rotation]
    if angles and len(set(angles)) == 1 and len(angles) == td.n_pairs:
        td.consistent_rotation = angles[0]


def _classify_delta_type(td: TaskDelta):
    """Classify the overall delta into a high-level type."""
    subtypes = []
    scores = {}

    # Global transform checks
    if td.consistent_reflection:
        subtypes.append("reflection")
        scores["reflection"] = 1.0
    if td.consistent_rotation:
        subtypes.append("rotation")
        scores["rotation"] = 1.0
    if all(pd.evidence.get("is_transpose") for pd in td.pair_deltas):
        subtypes.append("transpose")
        scores["transpose"] = 1.0
    if td.consistent_color_map:
        subtypes.append("color_permutation")
        scores["color_permutation"] = 1.0

    # Structural checks
    if all(pd.is_crop for pd in td.pair_deltas):
        subtypes.append("crop")
        scores["crop"] = 1.0
    if all(pd.is_tile for pd in td.pair_deltas):
        subtypes.append("tile")
        scores["tile"] = 1.0
    if all(pd.is_filter for pd in td.pair_deltas):
        subtypes.append("filter")
        scores["filter"] = 0.9
    if all(pd.is_recolor for pd in td.pair_deltas):
        subtypes.append("recolor")
        scores["recolor"] = 0.9
    if all(pd.is_fill for pd in td.pair_deltas):
        subtypes.append("fill")
        scores["fill"] = 0.8

    # Object-level patterns
    change_types = set()
    for pd in td.pair_deltas:
        for c in pd.correspondences:
            if c.transform_type not in ("identical", "appeared", "disappeared"):
                change_types.add(c.transform_type)
    if change_types == {"moved"}:
        subtypes.append("object_movement")
        scores["object_movement"] = 0.85
    elif change_types == {"recolored"}:
        subtypes.append("object_recolor")
        scores["object_recolor"] = 0.85

    # Size change patterns
    if td.consistent_same_size is False:
        ratios = [pd.size_ratio for pd in td.pair_deltas]
        h_ratios = set(r[0] for r in ratios)
        w_ratios = set(r[1] for r in ratios)
        if len(h_ratios) == 1 and len(w_ratios) == 1:
            subtypes.append("consistent_resize")
            scores["consistent_resize"] = 0.9

    # Change rate analysis
    change_rates = [pd.change_rate for pd in td.pair_deltas if pd.same_size]
    if change_rates:
        avg_rate = sum(change_rates) / len(change_rates)
        if avg_rate < 0.1:
            subtypes.append("minimal_change")
        elif avg_rate > 0.8:
            subtypes.append("major_change")

    td.delta_subtypes = subtypes

    if scores:
        td.delta_type = max(scores, key=scores.get)
        td.consistency_score = max(scores.values())
    elif subtypes:
        td.delta_type = subtypes[0]
        td.consistency_score = 0.5
    else:
        td.delta_type = "complex"
        td.consistency_score = 0.0


def _generate_synthesis_hints(td: TaskDelta):
    """Generate prioritized synthesis hints from the delta analysis."""
    hints = []

    # Direct global transforms
    if td.consistent_reflection:
        hints.append({
            "strategy": "reflection",
            "axis": td.consistent_reflection,
            "priority": 1.0,
            "depth": 1,
        })
    if td.consistent_rotation:
        hints.append({
            "strategy": "rotation",
            "angle": td.consistent_rotation,
            "priority": 1.0,
            "depth": 1,
        })
    if all(pd.evidence.get("is_transpose") for pd in td.pair_deltas):
        hints.append({
            "strategy": "transpose",
            "priority": 1.0,
            "depth": 1,
        })
    if td.consistent_color_map:
        hints.append({
            "strategy": "color_map",
            "mapping": td.consistent_color_map,
            "priority": 0.95,
            "depth": 1,
        })

    # Structural transforms
    if "crop" in td.delta_subtypes:
        crop_rules = [pd.crop_rule for pd in td.pair_deltas if pd.crop_rule]
        hints.append({
            "strategy": "crop",
            "rules": crop_rules,
            "priority": 0.9,
            "depth": 1,
        })
    if "tile" in td.delta_subtypes:
        factors = [pd.tile_factor for pd in td.pair_deltas if pd.tile_factor]
        hints.append({
            "strategy": "tile",
            "factors": factors,
            "priority": 0.9,
            "depth": 1,
        })

    # Object-level transforms
    if "filter" in td.delta_subtypes:
        hints.append({
            "strategy": "filter_objects",
            "priority": 0.85,
            "depth": 1,
        })
    if "object_movement" in td.delta_subtypes:
        hints.append({
            "strategy": "move_objects",
            "translation": td.consistent_translation,
            "priority": 0.85,
            "depth": 1,
        })
    if "object_recolor" in td.delta_subtypes or "recolor" in td.delta_subtypes:
        hints.append({
            "strategy": "recolor",
            "priority": 0.8,
            "depth": 1,
        })
    if "fill" in td.delta_subtypes:
        hints.append({
            "strategy": "fill_regions",
            "priority": 0.75,
            "depth": 1,
        })

    # Compositional hints (when single operation doesn't explain everything)
    if not hints or td.consistency_score < 0.5:
        hints.append({
            "strategy": "compositional_search",
            "priority": 0.5,
            "depth": 3,
        })

    # Always include generic synthesis as fallback
    hints.append({
        "strategy": "operator_genesis",
        "priority": 0.4,
        "depth": 1,
    })

    hints.sort(key=lambda h: -h["priority"])
    td.synthesis_hints = hints


# ---------------------------------------------------------------------------
# Delta embedding (for memory storage/retrieval)
# ---------------------------------------------------------------------------

def delta_to_embedding(td: TaskDelta) -> np.ndarray:
    """Convert TaskDelta to a fixed-size embedding vector for manifold storage."""
    features = []

    # Size features (4)
    features.append(1.0 if td.consistent_same_size else 0.0)
    if td.pair_deltas:
        pd0 = td.pair_deltas[0]
        features.extend([pd0.size_ratio[0], pd0.size_ratio[1]])
        features.append(pd0.change_rate)
    else:
        features.extend([1.0, 1.0, 0.0])

    # Color features (4)
    if td.pair_deltas:
        pd0 = td.pair_deltas[0]
        features.append(len(pd0.input_colors) / 10.0)
        features.append(len(pd0.output_colors) / 10.0)
        features.append(len(pd0.colors_added) / 10.0)
        features.append(len(pd0.colors_removed) / 10.0)
    else:
        features.extend([0.0, 0.0, 0.0, 0.0])

    # Object features (4)
    if td.pair_deltas:
        pd0 = td.pair_deltas[0]
        features.append(min(pd0.input_object_count / 20.0, 1.0))
        features.append(min(pd0.output_object_count / 20.0, 1.0))
        features.append(min(pd0.objects_appeared / 10.0, 1.0))
        features.append(min(pd0.objects_disappeared / 10.0, 1.0))
    else:
        features.extend([0.0, 0.0, 0.0, 0.0])

    # Type flags (12)
    type_flags = [
        "reflection", "rotation", "transpose", "color_permutation",
        "crop", "tile", "filter", "recolor", "fill",
        "object_movement", "object_recolor", "consistent_resize",
    ]
    for tf in type_flags:
        features.append(1.0 if tf in td.delta_subtypes else 0.0)

    # Consistency score (1)
    features.append(td.consistency_score)

    return np.array(features, dtype=np.float32)


# ---------------------------------------------------------------------------
# Partial correctness scoring
# ---------------------------------------------------------------------------

def score_partial_correctness(
    predicted: np.ndarray,
    expected: np.ndarray,
) -> Dict[str, float]:
    """Score how close a prediction is to the expected output."""
    if predicted is None:
        return {"pixel_accuracy": 0.0, "shape_match": False, "score": 0.0}

    shape_match = predicted.shape == expected.shape
    if not shape_match:
        return {"pixel_accuracy": 0.0, "shape_match": False, "score": 0.0}

    total = expected.size
    correct = int(np.sum(predicted == expected))
    pixel_acc = correct / max(total, 1)

    return {
        "pixel_accuracy": pixel_acc,
        "shape_match": True,
        "score": pixel_acc,
        "pixels_correct": correct,
        "pixels_total": total,
        "pixels_wrong": total - correct,
    }


def compute_residual(
    predicted: np.ndarray,
    expected: np.ndarray,
) -> Optional[PairDelta]:
    """Compute the delta between a prediction and the expected output.

    This represents "what still needs to be fixed" — the residual problem.
    """
    if predicted is None or predicted.shape != expected.shape:
        return None
    return compute_pair_delta(predicted, expected, bg=-1)
