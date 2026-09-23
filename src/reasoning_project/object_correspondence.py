"""Deep Object Correspondence Engine.

Matches input objects to output objects, discovers per-object transformation
rules (recolor, move, filter, sort, stamp), and generalises across training
pairs.  Pure algorithmic reasoning — no ML.
"""
from __future__ import annotations

import time
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import numpy as np
from scipy.ndimage import label as ndlabel

from reasoning_project.operator_genesis import SynthesizedOperator


# ===================================================================
# 1.  Object Extraction
# ===================================================================

@dataclass
class RichObject:
    obj_id: int
    color: int
    mask: np.ndarray
    pixels: List[Tuple[int, int]]
    bbox: Tuple[int, int, int, int]  # r0, r1, c0, c1
    area: int
    centroid: Tuple[float, float]
    aspect_ratio: float
    perimeter: int
    is_convex: bool
    symmetry_h: bool
    symmetry_v: bool
    hole_count: int
    border_touching: bool
    grid_region: str  # "top","bottom","left","right","center","topleft", etc.
    rel_row: float  # centroid row / grid height
    rel_col: float  # centroid col / grid width
    shape_sig: Tuple  # normalised shape signature for comparison


def _perimeter(mask: np.ndarray) -> int:
    h, w = mask.shape
    p = 0
    for r, c in zip(*np.where(mask)):
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nr, nc = r + dr, c + dc
            if nr < 0 or nr >= h or nc < 0 or nc >= w or not mask[nr, nc]:
                p += 1
    return p


def _is_convex(mask: np.ndarray, bbox: Tuple[int, int, int, int]) -> bool:
    r0, r1, c0, c1 = bbox
    sub = mask[r0:r1 + 1, c0:c1 + 1]
    return int(sub.sum()) == (r1 - r0 + 1) * (c1 - c0 + 1)


def _symmetry(mask: np.ndarray, bbox: Tuple[int, int, int, int]):
    r0, r1, c0, c1 = bbox
    sub = mask[r0:r1 + 1, c0:c1 + 1]
    sym_h = np.array_equal(sub, sub[::-1, :])
    sym_v = np.array_equal(sub, sub[:, ::-1])
    return sym_h, sym_v


def _hole_count(mask: np.ndarray, bbox: Tuple[int, int, int, int]) -> int:
    r0, r1, c0, c1 = bbox
    sub = mask[r0:r1 + 1, c0:c1 + 1]
    inv = ~sub
    labeled, n = ndlabel(inv)
    border_labels: set = set()
    if inv.shape[0] > 0:
        border_labels |= set(labeled[0, :].tolist())
        border_labels |= set(labeled[-1, :].tolist())
    if inv.shape[1] > 0:
        border_labels |= set(labeled[:, 0].tolist())
        border_labels |= set(labeled[:, -1].tolist())
    border_labels.discard(0)
    return max(0, n - len(border_labels))


def _grid_region(cr: float, cc: float, h: int, w: int) -> str:
    vert = "top" if cr < h / 3 else ("bottom" if cr > 2 * h / 3 else "mid")
    horiz = "left" if cc < w / 3 else ("right" if cc > 2 * w / 3 else "mid")
    if vert == "mid" and horiz == "mid":
        return "center"
    if vert == "mid":
        return horiz
    if horiz == "mid":
        return vert
    return vert + horiz


def _shape_signature(mask: np.ndarray, bbox: Tuple[int, int, int, int]) -> Tuple:
    r0, r1, c0, c1 = bbox
    sub = mask[r0:r1 + 1, c0:c1 + 1].astype(np.uint8)
    return tuple(sub.flatten().tolist())


def extract_objects(grid: np.ndarray, bg: int = -1) -> List[RichObject]:
    """Extract per-color connected components with rich features."""
    h, w = grid.shape
    if bg == -1:
        counts = np.bincount(grid.flatten().astype(int), minlength=10)
        bg = int(np.argmax(counts))

    objects: List[RichObject] = []
    obj_id = 0

    for color in range(10):
        if color == bg:
            continue
        cmask = grid == color
        if not cmask.any():
            continue
        labeled, n = ndlabel(cmask)
        for i in range(1, n + 1):
            mask = labeled == i
            rows, cols = np.where(mask)
            if len(rows) == 0:
                continue
            r0, r1 = int(rows.min()), int(rows.max())
            c0, c1 = int(cols.min()), int(cols.max())
            area = int(mask.sum())
            cr = float(rows.mean())
            cc = float(cols.mean())
            bbox = (r0, r1, c0, c1)
            bh = r1 - r0 + 1
            bw = c1 - c0 + 1
            ar = bh / max(bw, 1)
            peri = _perimeter(mask)
            convex = _is_convex(mask, bbox)
            sh, sv = _symmetry(mask, bbox)
            holes = _hole_count(mask, bbox)
            bt = r0 == 0 or r1 == h - 1 or c0 == 0 or c1 == w - 1
            region = _grid_region(cr, cc, h, w)
            sig = _shape_signature(mask, bbox)
            pixels = list(zip(rows.tolist(), cols.tolist()))

            objects.append(RichObject(
                obj_id=obj_id, color=color, mask=mask, pixels=pixels,
                bbox=bbox, area=area, centroid=(cr, cc),
                aspect_ratio=ar, perimeter=peri, is_convex=convex,
                symmetry_h=sh, symmetry_v=sv, hole_count=holes,
                border_touching=bt, grid_region=region,
                rel_row=cr / max(h, 1), rel_col=cc / max(w, 1),
                shape_sig=sig,
            ))
            obj_id += 1

    return objects


def extract_multicolor_objects(grid: np.ndarray, bg: int = -1) -> List[RichObject]:
    """Extract multi-color connected components (any non-bg adjacent pixels)."""
    h, w = grid.shape
    if bg == -1:
        counts = np.bincount(grid.flatten().astype(int), minlength=10)
        bg = int(np.argmax(counts))

    nonbg = grid != bg
    if not nonbg.any():
        return []

    labeled, n = ndlabel(nonbg)
    objects: List[RichObject] = []
    for i in range(1, n + 1):
        mask = labeled == i
        rows, cols = np.where(mask)
        if len(rows) == 0:
            continue
        r0, r1 = int(rows.min()), int(rows.max())
        c0, c1 = int(cols.min()), int(cols.max())
        area = int(mask.sum())
        cr, cc = float(rows.mean()), float(cols.mean())
        bbox = (r0, r1, c0, c1)
        bh, bw = r1 - r0 + 1, c1 - c0 + 1
        colors = grid[mask]
        dominant = int(np.argmax(np.bincount(colors.astype(int), minlength=10)))
        peri = _perimeter(mask)
        convex = _is_convex(mask, bbox)
        sh, sv = _symmetry(mask, bbox)
        holes = _hole_count(mask, bbox)
        bt = r0 == 0 or r1 == h - 1 or c0 == 0 or c1 == w - 1
        region = _grid_region(cr, cc, h, w)
        sig = _shape_signature(mask, bbox)
        pixels = list(zip(rows.tolist(), cols.tolist()))

        objects.append(RichObject(
            obj_id=i - 1, color=dominant, mask=mask, pixels=pixels,
            bbox=bbox, area=area, centroid=(cr, cc),
            aspect_ratio=bh / max(bw, 1), perimeter=peri,
            is_convex=convex, symmetry_h=sh, symmetry_v=sv,
            hole_count=holes, border_touching=bt, grid_region=region,
            rel_row=cr / max(h, 1), rel_col=cc / max(w, 1),
            shape_sig=sig,
        ))
    return objects


# ===================================================================
# 2.  Object Correspondence
# ===================================================================

@dataclass
class ObjMatch:
    inp_obj: Optional[RichObject]
    out_obj: Optional[RichObject]
    score: float
    transform: str  # kept, moved, recolored, resized, deleted, created, deformed


def _iou(a: RichObject, b: RichObject) -> float:
    ar0, ar1, ac0, ac1 = a.bbox
    br0, br1, bc0, bc1 = b.bbox
    ir0 = max(ar0, br0)
    ir1 = min(ar1, br1)
    ic0 = max(ac0, bc0)
    ic1 = min(ac1, bc1)
    if ir0 > ir1 or ic0 > ic1:
        return 0.0
    inter = (ir1 - ir0 + 1) * (ic1 - ic0 + 1)
    union = a.area + b.area - inter
    return inter / max(union, 1)


def _shape_match(a: RichObject, b: RichObject) -> bool:
    ar0, ar1, ac0, ac1 = a.bbox
    br0, br1, bc0, bc1 = b.bbox
    ah, aw = ar1 - ar0 + 1, ac1 - ac0 + 1
    bh, bw = br1 - br0 + 1, bc1 - bc0 + 1
    if ah != bh or aw != bw:
        return False
    asub = a.mask[ar0:ar1 + 1, ac0:ac1 + 1]
    bsub = b.mask[br0:br1 + 1, bc0:bc1 + 1]
    return np.array_equal(asub, bsub)


def _centroid_dist(a: RichObject, b: RichObject) -> float:
    return ((a.centroid[0] - b.centroid[0]) ** 2 +
            (a.centroid[1] - b.centroid[1]) ** 2) ** 0.5


def _correspondence_score(inp_obj: RichObject, out_obj: RichObject) -> float:
    s = 0.0
    if inp_obj.color == out_obj.color:
        s += 3.0
    if _shape_match(inp_obj, out_obj):
        s += 5.0
    iou = _iou(inp_obj, out_obj)
    s += iou * 3.0
    dist = _centroid_dist(inp_obj, out_obj)
    s += max(0, 2.0 - dist * 0.1)
    ar_ratio = min(inp_obj.aspect_ratio, out_obj.aspect_ratio) / max(inp_obj.aspect_ratio, out_obj.aspect_ratio, 0.01)
    s += ar_ratio
    return s


def _classify_transform(inp_obj: RichObject, out_obj: RichObject) -> str:
    if np.array_equal(inp_obj.mask, out_obj.mask) and inp_obj.color == out_obj.color:
        return "kept"
    if _shape_match(inp_obj, out_obj):
        if inp_obj.color != out_obj.color:
            return "recolored"
        return "moved"
    if inp_obj.color == out_obj.color:
        iou = _iou(inp_obj, out_obj)
        if iou > 0.3:
            area_ratio = out_obj.area / max(inp_obj.area, 1)
            if 1.5 < area_ratio < 10 or 0.1 < area_ratio < 0.7:
                return "resized"
            return "deformed"
        return "moved"
    return "deformed"


def compute_correspondence(
    inp_objs: List[RichObject],
    out_objs: List[RichObject],
) -> List[ObjMatch]:
    """Greedy best-score matching between input and output objects."""
    if not inp_objs and not out_objs:
        return []

    matches: List[ObjMatch] = []
    used_inp: Set[int] = set()
    used_out: Set[int] = set()

    scores = []
    for i, io in enumerate(inp_objs):
        for j, oo in enumerate(out_objs):
            s = _correspondence_score(io, oo)
            scores.append((s, i, j))
    scores.sort(key=lambda x: -x[0])

    for s, i, j in scores:
        if i in used_inp or j in used_out:
            continue
        if s < 1.0:
            continue
        t = _classify_transform(inp_objs[i], out_objs[j])
        matches.append(ObjMatch(inp_objs[i], out_objs[j], s, t))
        used_inp.add(i)
        used_out.add(j)

    for i, io in enumerate(inp_objs):
        if i not in used_inp:
            matches.append(ObjMatch(io, None, 0.0, "deleted"))
    for j, oo in enumerate(out_objs):
        if j not in used_out:
            matches.append(ObjMatch(None, oo, 0.0, "created"))

    return matches


# ===================================================================
# 3.  Feature Extraction for Discrimination
# ===================================================================

def _bool_props(obj: RichObject, all_objs: List[RichObject]) -> Dict[str, bool]:
    areas = [o.area for o in all_objs] if all_objs else [obj.area]
    colors = [o.color for o in all_objs]
    color_counts = Counter(colors)
    return {
        "border_touching": obj.border_touching,
        "has_holes": obj.hole_count > 0,
        "is_symmetric_h": obj.symmetry_h,
        "is_symmetric_v": obj.symmetry_v,
        "is_convex": obj.is_convex,
        "is_largest": obj.area == max(areas),
        "is_smallest": obj.area == min(areas),
        "is_unique_color": color_counts.get(obj.color, 0) == 1,
        "is_most_common_color": obj.color == color_counts.most_common(1)[0][0] if color_counts else False,
        "area_gt_1": obj.area > 1,
        "is_square": (obj.bbox[1] - obj.bbox[0]) == (obj.bbox[3] - obj.bbox[2]),
        "is_tall": obj.aspect_ratio > 1.5,
        "is_wide": obj.aspect_ratio < 0.67,
        "is_single_pixel": obj.area == 1,
    }


def _numeric_props(obj: RichObject, all_objs: List[RichObject]) -> Dict[str, float]:
    areas = sorted(set(o.area for o in all_objs))
    area_rank = areas.index(obj.area) if obj.area in areas else 0
    colors = sorted(set(o.color for o in all_objs))
    color_rank = colors.index(obj.color) if obj.color in colors else 0
    return {
        "area": float(obj.area),
        "perimeter": float(obj.perimeter),
        "aspect_ratio": obj.aspect_ratio,
        "color": float(obj.color),
        "centroid_row": obj.centroid[0],
        "centroid_col": obj.centroid[1],
        "rel_row": obj.rel_row,
        "rel_col": obj.rel_col,
        "bbox_height": float(obj.bbox[1] - obj.bbox[0] + 1),
        "bbox_width": float(obj.bbox[3] - obj.bbox[2] + 1),
        "hole_count": float(obj.hole_count),
        "area_rank": float(area_rank),
        "color_rank": float(color_rank),
        "n_colors_nearby": 0.0,
    }


# ===================================================================
# 4.  Transformation Rule Discovery
# ===================================================================

def _find_bool_discriminator(
    kept_objs: List[RichObject],
    deleted_objs: List[RichObject],
    all_objs_per_pair: List[List[RichObject]],
    kept_per_pair: List[List[RichObject]],
    deleted_per_pair: List[List[RichObject]],
) -> Optional[Tuple[str, bool]]:
    """Find a boolean property that perfectly separates kept from deleted."""
    if not kept_objs or not deleted_objs:
        return None

    prop_names = list(_bool_props(kept_objs[0], kept_objs + deleted_objs).keys())

    for prop in prop_names:
        for keep_val in (True, False):
            consistent = True
            for all_o, k_o, d_o in zip(all_objs_per_pair, kept_per_pair, deleted_per_pair):
                for o in k_o:
                    bp = _bool_props(o, all_o)
                    if bp[prop] != keep_val:
                        consistent = False
                        break
                if not consistent:
                    break
                for o in d_o:
                    bp = _bool_props(o, all_o)
                    if bp[prop] == keep_val:
                        consistent = False
                        break
                if not consistent:
                    break
            if consistent:
                return (prop, keep_val)
    return None


def _find_numeric_discriminator(
    kept_objs: List[RichObject],
    deleted_objs: List[RichObject],
    all_objs_per_pair: List[List[RichObject]],
    kept_per_pair: List[List[RichObject]],
    deleted_per_pair: List[List[RichObject]],
) -> Optional[Tuple[str, str, float]]:
    """Find a numeric property + threshold that separates kept from deleted."""
    if not kept_objs or not deleted_objs:
        return None

    prop_names = list(_numeric_props(kept_objs[0], kept_objs + deleted_objs).keys())

    for prop in prop_names:
        all_vals = set()
        for o in kept_objs + deleted_objs:
            all_vals.add(_numeric_props(o, kept_objs + deleted_objs)[prop])

        for thresh in sorted(all_vals):
            for direction in ("gt", "lt", "eq"):
                consistent = True
                for all_o, k_o, d_o in zip(all_objs_per_pair, kept_per_pair, deleted_per_pair):
                    for o in k_o:
                        v = _numeric_props(o, all_o)[prop]
                        if direction == "gt" and not (v > thresh):
                            consistent = False
                        elif direction == "lt" and not (v < thresh):
                            consistent = False
                        elif direction == "eq" and not (v == thresh):
                            consistent = False
                        if not consistent:
                            break
                    if not consistent:
                        break
                    for o in d_o:
                        v = _numeric_props(o, all_o)[prop]
                        if direction == "gt" and (v > thresh):
                            consistent = False
                        elif direction == "lt" and (v < thresh):
                            consistent = False
                        elif direction == "eq" and (v == thresh):
                            consistent = False
                        if not consistent:
                            break
                    if not consistent:
                        break
                if consistent:
                    return (prop, direction, thresh)
    return None


def _find_color_recolor_rule(
    matches_per_pair: List[List[ObjMatch]],
) -> Optional[Dict[int, int]]:
    """Find a consistent color → color mapping across all pairs."""
    cmap: Dict[int, int] = {}
    for matches in matches_per_pair:
        for m in matches:
            if m.transform == "recolored" and m.inp_obj and m.out_obj:
                ic = m.inp_obj.color
                oc = m.out_obj.color
                if ic in cmap:
                    if cmap[ic] != oc:
                        return None
                else:
                    cmap[ic] = oc
    return cmap if cmap else None


def _find_property_recolor_rule(
    matches_per_pair: List[List[ObjMatch]],
    all_objs_per_pair: List[List[RichObject]],
) -> Optional[Tuple[str, Dict]]:
    """Find recolor rule based on object property (e.g., largest→red)."""
    prop_names = ["is_largest", "is_smallest", "border_touching", "has_holes",
                  "is_symmetric_h", "is_symmetric_v", "is_convex",
                  "is_unique_color", "is_most_common_color", "is_square"]

    for prop in prop_names:
        true_color: Optional[int] = None
        false_color: Optional[int] = None
        consistent = True
        for matches, all_o in zip(matches_per_pair, all_objs_per_pair):
            for m in matches:
                if m.inp_obj and m.out_obj and m.transform == "recolored":
                    bp = _bool_props(m.inp_obj, all_o)
                    oc = m.out_obj.color
                    if bp[prop]:
                        if true_color is None:
                            true_color = oc
                        elif true_color != oc:
                            consistent = False
                            break
                    else:
                        if false_color is None:
                            false_color = oc
                        elif false_color != oc:
                            consistent = False
                            break
            if not consistent:
                break
        if consistent and (true_color is not None or false_color is not None):
            rule = {}
            if true_color is not None:
                rule[True] = true_color
            if false_color is not None:
                rule[False] = false_color
            if len(rule) >= 1:
                return (prop, rule)
    return None


def _find_rank_recolor_rule(
    matches_per_pair: List[List[ObjMatch]],
    all_objs_per_pair: List[List[RichObject]],
) -> Optional[Tuple[str, Dict[int, int]]]:
    """Recolor based on rank of numeric property (e.g., rank by area → color)."""
    for rank_prop in ("area", "perimeter", "centroid_row", "centroid_col"):
        rank_to_color: Dict[int, int] = {}
        consistent = True
        for matches, all_o in zip(matches_per_pair, all_objs_per_pair):
            recolored = [(m.inp_obj, m.out_obj) for m in matches
                         if m.transform == "recolored" and m.inp_obj and m.out_obj]
            if not recolored:
                continue
            vals = sorted(set(_numeric_props(io, all_o)[rank_prop] for io, _ in recolored))
            for io, oo in recolored:
                v = _numeric_props(io, all_o)[rank_prop]
                rank = vals.index(v)
                if rank in rank_to_color:
                    if rank_to_color[rank] != oo.color:
                        consistent = False
                        break
                else:
                    rank_to_color[rank] = oo.color
            if not consistent:
                break
        if consistent and rank_to_color:
            return (rank_prop, rank_to_color)
    return None


def _find_movement_rule(
    matches_per_pair: List[List[ObjMatch]],
) -> Optional[Tuple[str, Any]]:
    """Find consistent movement pattern."""
    # Uniform displacement
    displacements = []
    for matches in matches_per_pair:
        for m in matches:
            if m.transform == "moved" and m.inp_obj and m.out_obj:
                dr = m.out_obj.centroid[0] - m.inp_obj.centroid[0]
                dc = m.out_obj.centroid[1] - m.inp_obj.centroid[1]
                displacements.append((round(dr), round(dc)))

    if displacements and len(set(displacements)) == 1:
        return ("uniform", displacements[0])

    # Gravity (all objects move to same edge)
    for direction in ("top", "bottom", "left", "right"):
        consistent = True
        for matches in matches_per_pair:
            for m in matches:
                if m.transform != "moved" or not m.inp_obj or not m.out_obj:
                    continue
                oo = m.out_obj
                if direction == "top" and oo.bbox[0] != 0:
                    consistent = False
                elif direction == "bottom":
                    pass  # need grid height, skip for now
                elif direction == "left" and oo.bbox[2] != 0:
                    consistent = False
                elif direction == "right":
                    pass
                if not consistent:
                    break
            if not consistent:
                break
        if consistent and displacements:
            return ("gravity", direction)

    return None


# ===================================================================
# 5.  Operator Builders
# ===================================================================

def _verify_on_train(fn: Callable, train_pairs) -> bool:
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


def _make_op(family: str, fn: Callable, explanation: str) -> SynthesizedOperator:
    return SynthesizedOperator(
        operator_id=f"{family}_{uuid.uuid4().hex[:8]}",
        operator_family=family,
        parameters={},
        preconditions=[],
        execute=fn,
        explanation=explanation,
        source_failure_signature={},
    )


def _build_filter_by_bool(
    train_pairs, all_objs_per_pair, matches_per_pair,
    kept_per_pair, deleted_per_pair, bg_per_pair,
) -> List[SynthesizedOperator]:
    ops = []
    kept_all = [o for kk in kept_per_pair for o in kk]
    deleted_all = [o for dd in deleted_per_pair for o in dd]
    disc = _find_bool_discriminator(kept_all, deleted_all,
                                     all_objs_per_pair, kept_per_pair, deleted_per_pair)
    if disc is None:
        return []
    prop, keep_val = disc

    def solve(grid, _prop=prop, _keep_val=keep_val):
        h, w = grid.shape
        counts = np.bincount(grid.flatten().astype(int), minlength=10)
        bg = int(np.argmax(counts))
        objs = extract_objects(grid, bg)
        out = np.full((h, w), bg, dtype=grid.dtype)
        for o in objs:
            bp = _bool_props(o, objs)
            if bp[_prop] == _keep_val:
                out[o.mask] = grid[o.mask]
        return out

    if _verify_on_train(solve, train_pairs):
        ops.append(_make_op("object_filter",
                            solve,
                            f"Keep objects where {prop}=={keep_val}"))
    return ops


def _build_filter_by_numeric(
    train_pairs, all_objs_per_pair, matches_per_pair,
    kept_per_pair, deleted_per_pair, bg_per_pair,
) -> List[SynthesizedOperator]:
    ops = []
    kept_all = [o for kk in kept_per_pair for o in kk]
    deleted_all = [o for dd in deleted_per_pair for o in dd]
    disc = _find_numeric_discriminator(kept_all, deleted_all,
                                        all_objs_per_pair, kept_per_pair, deleted_per_pair)
    if disc is None:
        return []
    prop, direction, thresh = disc

    def solve(grid, _p=prop, _d=direction, _t=thresh):
        h, w = grid.shape
        counts = np.bincount(grid.flatten().astype(int), minlength=10)
        bg = int(np.argmax(counts))
        objs = extract_objects(grid, bg)
        out = np.full((h, w), bg, dtype=grid.dtype)
        for o in objs:
            np_vals = _numeric_props(o, objs)
            v = np_vals[_p]
            keep = False
            if _d == "gt" and v > _t:
                keep = True
            elif _d == "lt" and v < _t:
                keep = True
            elif _d == "eq" and v == _t:
                keep = True
            if keep:
                out[o.mask] = grid[o.mask]
        return out

    if _verify_on_train(solve, train_pairs):
        ops.append(_make_op("object_filter",
                            solve,
                            f"Keep objects where {prop} {direction} {thresh}"))
    return ops


def _build_recolor_by_map(
    train_pairs, matches_per_pair,
) -> List[SynthesizedOperator]:
    ops = []
    cmap = _find_color_recolor_rule(matches_per_pair)
    if cmap is None:
        return []

    def solve(grid, _cmap=cmap):
        out = grid.copy()
        for src, tgt in _cmap.items():
            out[grid == src] = tgt
        return out

    if _verify_on_train(solve, train_pairs):
        ops.append(_make_op("object_recolor",
                            solve,
                            f"Recolor map: {cmap}"))
    return ops


def _build_recolor_by_property(
    train_pairs, matches_per_pair, all_objs_per_pair,
) -> List[SynthesizedOperator]:
    ops = []
    result = _find_property_recolor_rule(matches_per_pair, all_objs_per_pair)
    if result is None:
        return []
    prop, rule = result

    def solve(grid, _prop=prop, _rule=rule):
        h, w = grid.shape
        counts = np.bincount(grid.flatten().astype(int), minlength=10)
        bg = int(np.argmax(counts))
        objs = extract_objects(grid, bg)
        out = grid.copy()
        for o in objs:
            bp = _bool_props(o, objs)
            val = bp[_prop]
            if val in _rule:
                out[o.mask] = _rule[val]
        return out

    if _verify_on_train(solve, train_pairs):
        ops.append(_make_op("object_recolor",
                            solve,
                            f"Recolor by {prop}: {rule}"))
    return ops


def _build_recolor_by_rank(
    train_pairs, matches_per_pair, all_objs_per_pair,
) -> List[SynthesizedOperator]:
    ops = []
    result = _find_rank_recolor_rule(matches_per_pair, all_objs_per_pair)
    if result is None:
        return []
    rank_prop, rank_map = result

    def solve(grid, _rp=rank_prop, _rm=rank_map):
        h, w = grid.shape
        counts = np.bincount(grid.flatten().astype(int), minlength=10)
        bg = int(np.argmax(counts))
        objs = extract_objects(grid, bg)
        vals = sorted(set(_numeric_props(o, objs)[_rp] for o in objs))
        out = grid.copy()
        for o in objs:
            v = _numeric_props(o, objs)[_rp]
            rank = vals.index(v) if v in vals else -1
            if rank in _rm:
                out[o.mask] = _rm[rank]
        return out

    if _verify_on_train(solve, train_pairs):
        ops.append(_make_op("object_recolor",
                            solve,
                            f"Recolor by rank of {rank_prop}: {rank_map}"))
    return ops


def _build_move_uniform(
    train_pairs, matches_per_pair,
) -> List[SynthesizedOperator]:
    ops = []
    result = _find_movement_rule(matches_per_pair)
    if result is None:
        return []
    kind, params = result

    if kind == "uniform":
        dr, dc = params

        def solve(grid, _dr=dr, _dc=dc):
            h, w = grid.shape
            counts = np.bincount(grid.flatten().astype(int), minlength=10)
            bg = int(np.argmax(counts))
            objs = extract_objects(grid, bg)
            out = np.full((h, w), bg, dtype=grid.dtype)
            for o in objs:
                for r, c in o.pixels:
                    nr, nc = r + _dr, c + _dc
                    if 0 <= nr < h and 0 <= nc < w:
                        out[nr, nc] = grid[r, c]
            return out

        if _verify_on_train(solve, train_pairs):
            ops.append(_make_op("object_move",
                                solve,
                                f"Move all objects by ({dr},{dc})"))
    return ops


def _build_filter_keep_color(
    train_pairs, matches_per_pair, bg_per_pair,
) -> List[SynthesizedOperator]:
    """Keep only objects of a specific color."""
    ops = []
    keep_colors: Optional[Set[int]] = None
    for matches in matches_per_pair:
        pair_keep = set()
        for m in matches:
            if m.transform != "deleted" and m.inp_obj:
                pair_keep.add(m.inp_obj.color)
        if keep_colors is None:
            keep_colors = pair_keep
        else:
            keep_colors &= pair_keep
    if not keep_colors:
        return []

    for kc in keep_colors:
        def solve(grid, _kc=kc):
            h, w = grid.shape
            counts = np.bincount(grid.flatten().astype(int), minlength=10)
            bg = int(np.argmax(counts))
            out = np.full((h, w), bg, dtype=grid.dtype)
            out[grid == _kc] = _kc
            return out

        if _verify_on_train(solve, train_pairs):
            ops.append(_make_op("object_filter",
                                solve,
                                f"Keep only color {kc}"))
    return ops


def _build_nearest_neighbor_recolor(
    train_pairs, all_objs_per_pair, matches_per_pair,
) -> List[SynthesizedOperator]:
    """Recolor each object to the color of its nearest neighbor."""
    ops = []

    def solve(grid):
        h, w = grid.shape
        counts = np.bincount(grid.flatten().astype(int), minlength=10)
        bg = int(np.argmax(counts))
        objs = extract_objects(grid, bg)
        if len(objs) < 2:
            return grid.copy()
        out = grid.copy()
        for o in objs:
            best_dist = float('inf')
            best_color = o.color
            for other in objs:
                if other.obj_id == o.obj_id:
                    continue
                d = _centroid_dist(o, other)
                if d < best_dist:
                    best_dist = d
                    best_color = other.color
            out[o.mask] = best_color
        return out

    if _verify_on_train(solve, train_pairs):
        ops.append(_make_op("object_recolor",
                            solve,
                            "Recolor each object to nearest neighbor's color"))
    return ops


def _build_sort_objects(
    train_pairs, matches_per_pair, all_objs_per_pair,
) -> List[SynthesizedOperator]:
    """Sort objects by property and rearrange positions."""
    ops = []
    for sort_prop in ("area", "color", "centroid_row", "centroid_col"):
        # Check if output objects are sorted by this property
        consistent = True
        sort_dir = None
        for matches, all_o in zip(matches_per_pair, all_objs_per_pair):
            matched = [(m.inp_obj, m.out_obj) for m in matches
                       if m.inp_obj and m.out_obj]
            if len(matched) < 2:
                continue
            out_positions = [(m.out_obj.centroid[0], m.out_obj.centroid[1])
                             for m in matches if m.out_obj]
            inp_vals = [_numeric_props(io, all_o)[sort_prop] for io, _ in matched]
            asc = all(inp_vals[i] <= inp_vals[i + 1] for i in range(len(inp_vals) - 1))
            desc = all(inp_vals[i] >= inp_vals[i + 1] for i in range(len(inp_vals) - 1))
            if not asc and not desc:
                consistent = False
                break
            d = "asc" if asc else "desc"
            if sort_dir is None:
                sort_dir = d
            elif sort_dir != d:
                consistent = False
                break
        if not consistent or sort_dir is None:
            continue

        def solve(grid, _sp=sort_prop, _sd=sort_dir):
            h, w = grid.shape
            counts = np.bincount(grid.flatten().astype(int), minlength=10)
            bg = int(np.argmax(counts))
            objs = extract_objects(grid, bg)
            if len(objs) < 2:
                return grid.copy()
            original_positions = [(o.bbox[0], o.bbox[2]) for o in objs]
            vals = [_numeric_props(o, objs)[_sp] for o in objs]
            indices = sorted(range(len(objs)), key=lambda i: vals[i],
                             reverse=(_sd == "desc"))
            out = np.full((h, w), bg, dtype=grid.dtype)
            for new_idx, orig_idx in enumerate(indices):
                o = objs[orig_idx]
                if new_idx < len(original_positions):
                    tgt_r, tgt_c = original_positions[new_idx]
                    r0, _, c0, _ = o.bbox
                    dr = tgt_r - r0
                    dc = tgt_c - c0
                    for r, c in o.pixels:
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < h and 0 <= nc < w:
                            out[nr, nc] = grid[r, c]
            return out

        if _verify_on_train(solve, train_pairs):
            ops.append(_make_op("object_sort",
                                solve,
                                f"Sort objects by {sort_prop} ({sort_dir})"))
    return ops


def _build_stamp_pattern(
    train_pairs, matches_per_pair,
) -> List[SynthesizedOperator]:
    """Detect stamp/copy patterns: an object is copied to multiple locations."""
    ops = []
    for matches in matches_per_pair:
        created = [m for m in matches if m.transform == "created" and m.out_obj]
        if len(created) < 2:
            continue
        sigs = [m.out_obj.shape_sig for m in created]
        if len(set(sigs)) != 1:
            continue
        # All created objects have same shape — stamping pattern
        template_match = created[0]
        template_obj = template_match.out_obj

        def solve(grid, _tmpl=template_obj):
            h, w = grid.shape
            counts = np.bincount(grid.flatten().astype(int), minlength=10)
            bg = int(np.argmax(counts))
            objs = extract_objects(grid, bg)
            out = grid.copy()
            tr0, tr1, tc0, tc1 = _tmpl.bbox
            th, tw = tr1 - tr0 + 1, tc1 - tc0 + 1
            tmpl_sub = _tmpl.mask[tr0:tr1 + 1, tc0:tc1 + 1]
            for o in objs:
                cr, cc = int(round(o.centroid[0])), int(round(o.centroid[1]))
                sr = cr - th // 2
                sc = cc - tw // 2
                for r in range(th):
                    for c in range(tw):
                        if tmpl_sub[r, c]:
                            nr, nc = sr + r, sc + c
                            if 0 <= nr < h and 0 <= nc < w:
                                out[nr, nc] = _tmpl.color
            return out

        if _verify_on_train(solve, train_pairs):
            ops.append(_make_op("object_stamp",
                                solve,
                                "Stamp template at each object location"))
    return ops


def _build_bbox_crop(train_pairs) -> List[SynthesizedOperator]:
    """Output = bounding box of a specific color."""
    ops = []
    for color in range(10):
        def solve(grid, _c=color):
            mask = grid == _c
            if not mask.any():
                return grid.copy()
            rows, cols = np.where(mask)
            r0, r1 = rows.min(), rows.max()
            c0, c1 = cols.min(), cols.max()
            return grid[r0:r1 + 1, c0:c1 + 1].copy()

        if _verify_on_train(solve, train_pairs):
            ops.append(_make_op("object_filter",
                                solve,
                                f"Crop to bounding box of color {color}"))

    # Crop to largest object
    def solve_largest(grid):
        h, w = grid.shape
        counts = np.bincount(grid.flatten().astype(int), minlength=10)
        bg = int(np.argmax(counts))
        objs = extract_objects(grid, bg)
        if not objs:
            return grid.copy()
        largest = max(objs, key=lambda o: o.area)
        r0, r1, c0, c1 = largest.bbox
        return grid[r0:r1 + 1, c0:c1 + 1].copy()

    if _verify_on_train(solve_largest, train_pairs):
        ops.append(_make_op("object_filter",
                            solve_largest,
                            "Crop to largest object bbox"))
    return ops


def _build_delete_reconstruct(
    train_pairs, bg_per_pair,
) -> List[SynthesizedOperator]:
    """Delete specific objects and fill with background."""
    ops = []
    for color in range(10):
        def solve(grid, _c=color):
            counts = np.bincount(grid.flatten().astype(int), minlength=10)
            bg = int(np.argmax(counts))
            if _c == bg:
                return grid.copy()
            out = grid.copy()
            out[grid == _c] = bg
            return out

        if _verify_on_train(solve, train_pairs):
            ops.append(_make_op("object_filter",
                                solve,
                                f"Delete all color {color} pixels"))
    return ops


def _build_mirror_object(train_pairs) -> List[SynthesizedOperator]:
    """Mirror objects horizontally or vertically."""
    ops = []
    for axis in ("h", "v"):
        def solve(grid, _ax=axis):
            h, w = grid.shape
            counts = np.bincount(grid.flatten().astype(int), minlength=10)
            bg = int(np.argmax(counts))
            objs = extract_objects(grid, bg)
            out = grid.copy()
            for o in objs:
                r0, r1, c0, c1 = o.bbox
                for r, c in o.pixels:
                    if _ax == "h":
                        mr = r0 + (r1 - r)
                        mc = c
                    else:
                        mr = r
                        mc = c0 + (c1 - c)
                    if 0 <= mr < h and 0 <= mc < w:
                        out[mr, mc] = grid[r, c]
            return out

        if _verify_on_train(solve, train_pairs):
            ops.append(_make_op("object_correspondence",
                                solve,
                                f"Mirror each object {'horizontally' if axis == 'h' else 'vertically'}"))
    return ops


def _build_fill_object_bbox(train_pairs) -> List[SynthesizedOperator]:
    """Fill each object's bounding box with its color."""
    ops = []

    def solve(grid):
        h, w = grid.shape
        counts = np.bincount(grid.flatten().astype(int), minlength=10)
        bg = int(np.argmax(counts))
        objs = extract_objects(grid, bg)
        out = grid.copy()
        for o in objs:
            r0, r1, c0, c1 = o.bbox
            out[r0:r1 + 1, c0:c1 + 1] = o.color
        return out

    if _verify_on_train(solve, train_pairs):
        ops.append(_make_op("object_correspondence",
                            solve,
                            "Fill each object's bbox with its color"))
    return ops


def _build_outline_object(train_pairs) -> List[SynthesizedOperator]:
    """Draw outline around each object."""
    ops = []
    for outline_c in range(10):
        def solve(grid, _oc=outline_c):
            h, w = grid.shape
            counts = np.bincount(grid.flatten().astype(int), minlength=10)
            bg = int(np.argmax(counts))
            objs = extract_objects(grid, bg)
            out = grid.copy()
            for o in objs:
                for r, c in o.pixels:
                    for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < h and 0 <= nc < w and not o.mask[nr, nc]:
                            out[nr, nc] = _oc
            return out

        if _verify_on_train(solve, train_pairs):
            ops.append(_make_op("object_correspondence",
                                solve,
                                f"Outline objects with color {outline_c}"))
    return ops


def _build_gravity_drop(train_pairs) -> List[SynthesizedOperator]:
    """Drop all objects down (gravity)."""
    ops = []
    for direction in ("down", "up", "left", "right"):
        def solve(grid, _dir=direction):
            h, w = grid.shape
            counts = np.bincount(grid.flatten().astype(int), minlength=10)
            bg = int(np.argmax(counts))
            objs = extract_objects(grid, bg)
            out = np.full((h, w), bg, dtype=grid.dtype)

            if _dir in ("down", "up"):
                objs_sorted = sorted(objs,
                                     key=lambda o: -o.bbox[1] if _dir == "down" else o.bbox[0])
                for o in objs_sorted:
                    r0, r1, c0, c1 = o.bbox
                    oh = r1 - r0 + 1
                    sub = o.mask[r0:r1 + 1, c0:c1 + 1]
                    if _dir == "down":
                        # Find lowest free row for each column in object
                        for dc in range(c1 - c0 + 1):
                            col = c0 + dc
                            obj_rows = [dr for dr in range(oh) if sub[dr, dc]]
                            if not obj_rows:
                                continue
                            span = len(obj_rows)
                            # Find lowest position where all pixels fit
                            target_bottom = h - 1
                            while target_bottom >= 0 and out[target_bottom, col] != bg:
                                target_bottom -= 1
                            target_top = target_bottom - span + 1
                            for i, dr in enumerate(obj_rows):
                                nr = target_top + i
                                if 0 <= nr < h:
                                    out[nr, col] = grid[r0 + dr, col]
                    else:  # up
                        for dc in range(c1 - c0 + 1):
                            col = c0 + dc
                            obj_rows = [dr for dr in range(oh) if sub[dr, dc]]
                            if not obj_rows:
                                continue
                            span = len(obj_rows)
                            target_top = 0
                            while target_top < h and out[target_top, col] != bg:
                                target_top += 1
                            for i, dr in enumerate(obj_rows):
                                nr = target_top + i
                                if 0 <= nr < h:
                                    out[nr, col] = grid[r0 + dr, col]
            else:  # left/right
                objs_sorted = sorted(objs,
                                     key=lambda o: -o.bbox[3] if _dir == "right" else o.bbox[2])
                for o in objs_sorted:
                    r0, r1, c0, c1 = o.bbox
                    ow = c1 - c0 + 1
                    sub = o.mask[r0:r1 + 1, c0:c1 + 1]
                    if _dir == "right":
                        for dr in range(r1 - r0 + 1):
                            row = r0 + dr
                            obj_cols = [dc for dc in range(ow) if sub[dr, dc]]
                            if not obj_cols:
                                continue
                            span = len(obj_cols)
                            target_right = w - 1
                            while target_right >= 0 and out[row, target_right] != bg:
                                target_right -= 1
                            target_left = target_right - span + 1
                            for i, dc in enumerate(obj_cols):
                                nc = target_left + i
                                if 0 <= nc < w:
                                    out[row, nc] = grid[row, c0 + dc]
                    else:  # left
                        for dr in range(r1 - r0 + 1):
                            row = r0 + dr
                            obj_cols = [dc for dc in range(ow) if sub[dr, dc]]
                            if not obj_cols:
                                continue
                            span = len(obj_cols)
                            target_left = 0
                            while target_left < w and out[row, target_left] != bg:
                                target_left += 1
                            for i, dc in enumerate(obj_cols):
                                nc = target_left + i
                                if 0 <= nc < w:
                                    out[row, nc] = grid[row, c0 + dc]
            return out

        if _verify_on_train(solve, train_pairs):
            ops.append(_make_op("object_move",
                                solve,
                                f"Gravity: drop all objects {direction}"))
    return ops


def _build_color_count_recolor(train_pairs) -> List[SynthesizedOperator]:
    """Recolor each object based on number of pixels of that color in grid."""
    ops = []

    # Recolor by area (object pixel count)
    area_to_color: Dict[int, int] = {}
    consistent = True
    for inp, out in train_pairs:
        counts = np.bincount(inp.flatten().astype(int), minlength=10)
        bg = int(np.argmax(counts))
        inp_objs = extract_objects(inp, bg)
        out_objs = extract_objects(out, bg)
        matches = compute_correspondence(inp_objs, out_objs)
        for m in matches:
            if m.transform == "recolored" and m.inp_obj and m.out_obj:
                a = m.inp_obj.area
                c = m.out_obj.color
                if a in area_to_color:
                    if area_to_color[a] != c:
                        consistent = False
                        break
                else:
                    area_to_color[a] = c
        if not consistent:
            break

    if consistent and area_to_color:
        def solve(grid, _atc=area_to_color):
            counts = np.bincount(grid.flatten().astype(int), minlength=10)
            bg = int(np.argmax(counts))
            objs = extract_objects(grid, bg)
            out = grid.copy()
            for o in objs:
                if o.area in _atc:
                    out[o.mask] = _atc[o.area]
            return out

        if _verify_on_train(solve, train_pairs):
            ops.append(_make_op("object_recolor",
                                solve,
                                f"Recolor by area: {area_to_color}"))
    return ops


def _build_keep_unique_shape(train_pairs) -> List[SynthesizedOperator]:
    """Keep only objects with unique shapes (or most common shape)."""
    ops = []

    def solve_unique(grid):
        h, w = grid.shape
        counts = np.bincount(grid.flatten().astype(int), minlength=10)
        bg = int(np.argmax(counts))
        objs = extract_objects(grid, bg)
        sig_counts = Counter(o.shape_sig for o in objs)
        out = np.full((h, w), bg, dtype=grid.dtype)
        for o in objs:
            if sig_counts[o.shape_sig] == 1:
                out[o.mask] = grid[o.mask]
        return out

    if _verify_on_train(solve_unique, train_pairs):
        ops.append(_make_op("object_filter",
                            solve_unique,
                            "Keep only objects with unique shape"))

    def solve_common(grid):
        h, w = grid.shape
        counts = np.bincount(grid.flatten().astype(int), minlength=10)
        bg = int(np.argmax(counts))
        objs = extract_objects(grid, bg)
        sig_counts = Counter(o.shape_sig for o in objs)
        most_common_sig = sig_counts.most_common(1)[0][0] if sig_counts else None
        out = np.full((h, w), bg, dtype=grid.dtype)
        for o in objs:
            if o.shape_sig == most_common_sig:
                out[o.mask] = grid[o.mask]
        return out

    if _verify_on_train(solve_common, train_pairs):
        ops.append(_make_op("object_filter",
                            solve_common,
                            "Keep only objects with most common shape"))
    return ops


def _build_multicolor_filter(train_pairs) -> List[SynthesizedOperator]:
    """Filter using multi-color objects."""
    ops = []

    def solve_keep_largest_mc(grid):
        h, w = grid.shape
        counts = np.bincount(grid.flatten().astype(int), minlength=10)
        bg = int(np.argmax(counts))
        mc_objs = extract_multicolor_objects(grid, bg)
        if not mc_objs:
            return grid.copy()
        largest = max(mc_objs, key=lambda o: o.area)
        out = np.full((h, w), bg, dtype=grid.dtype)
        out[largest.mask] = grid[largest.mask]
        return out

    if _verify_on_train(solve_keep_largest_mc, train_pairs):
        ops.append(_make_op("object_filter",
                            solve_keep_largest_mc,
                            "Keep largest multi-color object"))

    def solve_keep_smallest_mc(grid):
        h, w = grid.shape
        counts = np.bincount(grid.flatten().astype(int), minlength=10)
        bg = int(np.argmax(counts))
        mc_objs = extract_multicolor_objects(grid, bg)
        if not mc_objs:
            return grid.copy()
        smallest = min(mc_objs, key=lambda o: o.area)
        out = np.full((h, w), bg, dtype=grid.dtype)
        out[smallest.mask] = grid[smallest.mask]
        return out

    if _verify_on_train(solve_keep_smallest_mc, train_pairs):
        ops.append(_make_op("object_filter",
                            solve_keep_smallest_mc,
                            "Keep smallest multi-color object"))
    return ops


# ===================================================================
# 6.  Main Entry Point
# ===================================================================

def reason_by_object_correspondence(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    timeout_seconds: float = 10.0,
    task_id: str = "",
) -> List[SynthesizedOperator]:
    """Discover object-level transformation rules from training pairs."""
    deadline = time.time() + timeout_seconds
    results: List[SynthesizedOperator] = []

    try:
        # ---- Extract objects from all pairs ----
        all_objs_per_pair: List[List[RichObject]] = []
        out_objs_per_pair: List[List[RichObject]] = []
        matches_per_pair: List[List[ObjMatch]] = []
        bg_per_pair: List[int] = []
        kept_per_pair: List[List[RichObject]] = []
        deleted_per_pair: List[List[RichObject]] = []

        for inp, out in train_pairs:
            if time.time() > deadline:
                return results
            counts = np.bincount(inp.flatten().astype(int), minlength=10)
            bg = int(np.argmax(counts))
            bg_per_pair.append(bg)

            inp_objs = extract_objects(inp, bg)
            o_objs = extract_objects(out, bg)
            all_objs_per_pair.append(inp_objs)
            out_objs_per_pair.append(o_objs)

            matches = compute_correspondence(inp_objs, o_objs)
            matches_per_pair.append(matches)

            kept = [m.inp_obj for m in matches
                    if m.transform in ("kept", "recolored", "moved", "resized") and m.inp_obj]
            deleted = [m.inp_obj for m in matches
                       if m.transform == "deleted" and m.inp_obj]
            kept_per_pair.append(kept)
            deleted_per_pair.append(deleted)

        # ---- Phase 1: Filter operators ----
        builders = [
            lambda: _build_filter_by_bool(train_pairs, all_objs_per_pair,
                                          matches_per_pair, kept_per_pair,
                                          deleted_per_pair, bg_per_pair),
            lambda: _build_filter_by_numeric(train_pairs, all_objs_per_pair,
                                             matches_per_pair, kept_per_pair,
                                             deleted_per_pair, bg_per_pair),
            lambda: _build_filter_keep_color(train_pairs, matches_per_pair, bg_per_pair),
            lambda: _build_keep_unique_shape(train_pairs),
            lambda: _build_multicolor_filter(train_pairs),
            lambda: _build_bbox_crop(train_pairs),
            lambda: _build_delete_reconstruct(train_pairs, bg_per_pair),
            # Phase 2: Recolor operators
            lambda: _build_recolor_by_map(train_pairs, matches_per_pair),
            lambda: _build_recolor_by_property(train_pairs, matches_per_pair, all_objs_per_pair),
            lambda: _build_recolor_by_rank(train_pairs, matches_per_pair, all_objs_per_pair),
            lambda: _build_nearest_neighbor_recolor(train_pairs, all_objs_per_pair, matches_per_pair),
            lambda: _build_color_count_recolor(train_pairs),
            # Phase 3: Movement operators
            lambda: _build_move_uniform(train_pairs, matches_per_pair),
            lambda: _build_gravity_drop(train_pairs),
            # Phase 4: Sort / stamp / structural
            lambda: _build_sort_objects(train_pairs, matches_per_pair, all_objs_per_pair),
            lambda: _build_stamp_pattern(train_pairs, matches_per_pair),
            lambda: _build_mirror_object(train_pairs),
            lambda: _build_fill_object_bbox(train_pairs),
            lambda: _build_outline_object(train_pairs),
        ]

        seen_families: Set[str] = set()
        for builder in builders:
            if time.time() > deadline:
                break
            try:
                ops = builder()
                for op in ops:
                    key = (op.operator_family, op.explanation)
                    if key not in seen_families:
                        seen_families.add(key)
                        results.append(op)
            except Exception:
                continue

    except Exception:
        pass

    return results
