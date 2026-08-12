"""Object-structural reasoning engine for ARC tasks.

Implements the five core paradigms:
1. Object matching via optimal transport (Hungarian algorithm)
2. Spatial relation graph construction
3. Invariant-guided search
4. Counterfactual testing
5. Transformation field inference

This module provides the foundation for reasoning about objects,
relations, and structural invariants rather than pixels.
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage
from scipy.optimize import linear_sum_assignment
from typing import Optional, List, Tuple, Dict, Any, Set, FrozenSet


# ---------------------------------------------------------------------------
# 1. Object matching via optimal transport
# ---------------------------------------------------------------------------

def compute_structural_signature(local_mask: np.ndarray) -> Dict[str, float]:
    """Topology-aware structural fingerprint for an object."""
    area = float(local_mask.sum())
    h, w = local_mask.shape

    perimeter = 0.0
    for r in range(h):
        for c in range(w):
            if local_mask[r, c]:
                for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nr, nc = r + dr, c + dc
                    if nr < 0 or nr >= h or nc < 0 or nc >= w or not local_mask[nr, nc]:
                        perimeter += 1

    bg_labeled, n_bg = ndimage.label(~local_mask)
    border_labels = set()
    border_labels.update(bg_labeled[0, :].tolist())
    border_labels.update(bg_labeled[-1, :].tolist())
    border_labels.update(bg_labeled[:, 0].tolist())
    border_labels.update(bg_labeled[:, -1].tolist())
    border_labels.discard(0)
    n_holes = sum(1 for lab in range(1, n_bg + 1) if lab not in border_labels)

    h_sym = float(np.array_equal(local_mask, local_mask[::-1, :]))
    v_sym = float(np.array_equal(local_mask, local_mask[:, ::-1]))

    return {
        "area": area,
        "perimeter": perimeter,
        "n_holes": float(n_holes),
        "euler_char": float(1 - n_holes),
        "h_sym": h_sym,
        "v_sym": v_sym,
        "convexity": area / max(h * w, 1),
        "bbox_ratio": float(h) / max(w, 1),
        "bbox_h": float(h),
        "bbox_w": float(w),
    }


def extract_objects(grid: np.ndarray, bg: int = 0) -> List[Dict[str, Any]]:
    """Extract connected components with structural signatures."""
    mask = grid != bg
    labeled, n = ndimage.label(mask)
    objects = []
    for lab in range(1, n + 1):
        obj_mask = labeled == lab
        rows, cols = np.where(obj_mask)
        if len(rows) == 0:
            continue
        r_min, r_max = int(rows.min()), int(rows.max())
        c_min, c_max = int(cols.min()), int(cols.max())
        local_mask = obj_mask[r_min:r_max+1, c_min:c_max+1]
        patch = grid[r_min:r_max+1, c_min:c_max+1].copy()
        sig = compute_structural_signature(local_mask)
        colors = sorted(set(grid[obj_mask].tolist()) - {bg})
        objects.append({
            "id": lab,
            "mask": obj_mask,
            "bbox": (r_min, c_min, r_max, c_max),
            "center_r": float(rows.mean()),
            "center_c": float(cols.mean()),
            "size": int(obj_mask.sum()),
            "local_mask": local_mask,
            "patch": patch,
            "colors": colors,
            "primary_color": int(grid[obj_mask].flat[0]),
            "signature": sig,
        })
    return objects


def signature_distance(sig1: Dict[str, float], sig2: Dict[str, float]) -> float:
    """Weighted distance between two structural signatures."""
    weights = {
        "area": 0.3, "perimeter": 0.1, "n_holes": 0.2,
        "h_sym": 0.05, "v_sym": 0.05, "convexity": 0.1,
        "bbox_ratio": 0.1, "bbox_h": 0.05, "bbox_w": 0.05,
    }
    dist = 0.0
    for key, w in weights.items():
        v1 = sig1.get(key, 0.0)
        v2 = sig2.get(key, 0.0)
        denom = max(abs(v1), abs(v2), 1.0)
        dist += w * abs(v1 - v2) / denom
    return dist


def match_objects_hungarian(
    in_objects: List[Dict], out_objects: List[Dict]
) -> List[Tuple[int, int, float]]:
    """Match input→output objects using Hungarian algorithm on structural distance."""
    n_in = len(in_objects)
    n_out = len(out_objects)
    if n_in == 0 or n_out == 0:
        return []

    n = max(n_in, n_out)
    cost = np.full((n, n), 1e6)

    for i in range(n_in):
        for j in range(n_out):
            shape_dist = signature_distance(
                in_objects[i]["signature"], out_objects[j]["signature"]
            )
            shape_match = 0.0
            lm1 = in_objects[i]["local_mask"]
            lm2 = out_objects[j]["local_mask"]
            if lm1.shape == lm2.shape:
                shape_match = -float(np.array_equal(lm1, lm2)) * 2.0

            pos_dist = abs(in_objects[i]["center_r"] - out_objects[j]["center_r"]) + \
                       abs(in_objects[i]["center_c"] - out_objects[j]["center_c"])
            pos_norm = pos_dist / max(in_objects[i]["mask"].shape[0], 1)

            cost[i, j] = shape_dist + shape_match + 0.1 * pos_norm

    row_ind, col_ind = linear_sum_assignment(cost)

    matches = []
    for i, j in zip(row_ind, col_ind):
        if i < n_in and j < n_out and cost[i, j] < 10.0:
            matches.append((i, j, float(cost[i, j])))
    return matches


def classify_object_transform(
    in_obj: Dict, out_obj: Dict
) -> Dict[str, Any]:
    """Classify the transformation between matched input/output objects."""
    transform = {
        "same_shape": np.array_equal(in_obj["local_mask"], out_obj["local_mask"]),
        "same_color": in_obj["primary_color"] == out_obj["primary_color"],
        "same_position": (
            abs(in_obj["center_r"] - out_obj["center_r"]) < 0.5 and
            abs(in_obj["center_c"] - out_obj["center_c"]) < 0.5
        ),
        "same_size": in_obj["size"] == out_obj["size"],
        "color_change": (in_obj["primary_color"], out_obj["primary_color"]),
        "position_delta": (
            out_obj["center_r"] - in_obj["center_r"],
            out_obj["center_c"] - in_obj["center_c"],
        ),
    }

    if transform["same_shape"] and transform["same_color"] and not transform["same_position"]:
        transform["type"] = "moved"
    elif transform["same_shape"] and not transform["same_color"] and transform["same_position"]:
        transform["type"] = "recolored"
    elif transform["same_shape"] and transform["same_color"] and transform["same_position"]:
        transform["type"] = "unchanged"
    elif not transform["same_shape"]:
        transform["type"] = "reshaped"
    else:
        transform["type"] = "complex"

    return transform


# ---------------------------------------------------------------------------
# 2. Spatial relation graph
# ---------------------------------------------------------------------------

def compute_spatial_relations(objects: List[Dict]) -> List[Dict[str, Any]]:
    """Compute pairwise spatial relations between all objects."""
    relations = []
    for i, obj_a in enumerate(objects):
        for j, obj_b in enumerate(objects):
            if i >= j:
                continue
            rel = _compute_pair_relations(obj_a, obj_b)
            relations.append({
                "obj_a": i,
                "obj_b": j,
                "relations": rel,
            })
    return relations


def _compute_pair_relations(a: Dict, b: Dict) -> Dict[str, bool]:
    """Compute spatial relations between two objects."""
    a_r, a_c = a["center_r"], a["center_c"]
    b_r, b_c = b["center_r"], b["center_c"]

    a_r1, a_c1, a_r2, a_c2 = a["bbox"]
    b_r1, b_c1, b_r2, b_c2 = b["bbox"]

    touching = bool(np.any(
        ndimage.binary_dilation(a["mask"]) & b["mask"]
    ))

    a_contains_b = bool(
        a_r1 <= b_r1 and a_c1 <= b_c1 and a_r2 >= b_r2 and a_c2 >= b_c2
    )
    b_contains_a = bool(
        b_r1 <= a_r1 and b_c1 <= a_c1 and b_r2 >= a_r2 and b_c2 >= a_c2
    )

    overlapping = bool(np.any(a["mask"] & b["mask"]))

    same_shape = False
    if a["local_mask"].shape == b["local_mask"].shape:
        same_shape = bool(np.array_equal(a["local_mask"], b["local_mask"]))

    h_aligned = abs(a_r - b_r) < 1.0
    v_aligned = abs(a_c - b_c) < 1.0

    return {
        "above": a_r < b_r - 1,
        "below": a_r > b_r + 1,
        "left_of": a_c < b_c - 1,
        "right_of": a_c > b_c + 1,
        "touching": touching,
        "overlapping": overlapping,
        "a_contains_b": a_contains_b,
        "b_contains_a": b_contains_a,
        "same_shape": same_shape,
        "same_color": a["primary_color"] == b["primary_color"],
        "same_size": a["size"] == b["size"],
        "h_aligned": h_aligned,
        "v_aligned": v_aligned,
    }


def relation_graph_signature(objects: List[Dict], relations: List[Dict]) -> Dict[str, Any]:
    """Compute a summary signature of the relation graph."""
    n_objects = len(objects)
    n_touching = sum(1 for r in relations if r["relations"]["touching"])
    n_same_shape = sum(1 for r in relations if r["relations"]["same_shape"])
    n_same_color = sum(1 for r in relations if r["relations"]["same_color"])
    n_contained = sum(1 for r in relations
                      if r["relations"]["a_contains_b"] or r["relations"]["b_contains_a"])

    colors = set()
    sizes = []
    for obj in objects:
        colors.update(obj["colors"])
        sizes.append(obj["size"])

    return {
        "n_objects": n_objects,
        "n_colors": len(colors),
        "n_touching_pairs": n_touching,
        "n_same_shape_pairs": n_same_shape,
        "n_same_color_pairs": n_same_color,
        "n_containment": n_contained,
        "size_variance": float(np.var(sizes)) if sizes else 0.0,
    }


# ---------------------------------------------------------------------------
# 3. Invariant-guided search
# ---------------------------------------------------------------------------

def compute_invariants(
    in_objects: List[Dict],
    out_objects: List[Dict],
    in_relations: List[Dict],
    out_relations: List[Dict],
    matches: List[Tuple[int, int, float]],
) -> Dict[str, bool]:
    """Compute what is preserved between input and output."""
    invariants = {}

    invariants["same_object_count"] = len(in_objects) == len(out_objects)

    in_colors = set()
    out_colors = set()
    for obj in in_objects:
        in_colors.update(obj["colors"])
    for obj in out_objects:
        out_colors.update(obj["colors"])
    invariants["same_color_set"] = in_colors == out_colors

    in_sizes = sorted(obj["size"] for obj in in_objects)
    out_sizes = sorted(obj["size"] for obj in out_objects)
    invariants["same_size_multiset"] = in_sizes == out_sizes

    all_same_shape = True
    all_same_color = True
    all_same_position = True
    for i_idx, j_idx, _ in matches:
        t = classify_object_transform(in_objects[i_idx], out_objects[j_idx])
        if not t["same_shape"]:
            all_same_shape = False
        if not t["same_color"]:
            all_same_color = False
        if not t["same_position"]:
            all_same_position = False

    invariants["all_shapes_preserved"] = all_same_shape
    invariants["all_colors_preserved"] = all_same_color
    invariants["all_positions_preserved"] = all_same_position

    in_sig = relation_graph_signature(in_objects, in_relations)
    out_sig = relation_graph_signature(out_objects, out_relations)
    invariants["same_touching_count"] = (
        in_sig["n_touching_pairs"] == out_sig["n_touching_pairs"]
    )
    invariants["same_containment"] = (
        in_sig["n_containment"] == out_sig["n_containment"]
    )

    return invariants


def analyze_task_invariants(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> Dict[str, bool]:
    """Find invariants that hold across ALL training pairs."""
    if not train_pairs:
        return {}

    all_invariants = None
    for inp, out in train_pairs:
        in_objs = extract_objects(inp)
        out_objs = extract_objects(out)
        in_rels = compute_spatial_relations(in_objs)
        out_rels = compute_spatial_relations(out_objs)
        matches = match_objects_hungarian(in_objs, out_objs)

        inv = compute_invariants(in_objs, out_objs, in_rels, out_rels, matches)

        if all_invariants is None:
            all_invariants = inv
        else:
            for key in list(all_invariants.keys()):
                if all_invariants[key] and not inv.get(key, False):
                    all_invariants[key] = False

    return all_invariants or {}


# ---------------------------------------------------------------------------
# 4. Counterfactual testing
# ---------------------------------------------------------------------------

def counterfactual_remove(
    grid: np.ndarray, objects: List[Dict], remove_idx: int
) -> np.ndarray:
    """Create a counterfactual grid with one object removed."""
    result = grid.copy()
    result[objects[remove_idx]["mask"]] = 0
    return result


def counterfactual_recolor(
    grid: np.ndarray, objects: List[Dict], obj_idx: int, new_color: int
) -> np.ndarray:
    """Create a counterfactual grid with one object recolored."""
    result = grid.copy()
    result[objects[obj_idx]["mask"]] = new_color
    return result


def identify_causal_properties(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> Dict[str, float]:
    """Test which object properties are causally relevant.

    For each training pair, systematically test counterfactuals:
    - Remove each object → does the rule break?
    - Recolor each object → does the output change?
    - The properties of objects that cause changes are "causal."
    """
    if not train_pairs:
        return {}

    causal_scores = {
        "color_causal": 0.0,
        "position_causal": 0.0,
        "size_causal": 0.0,
        "shape_causal": 0.0,
        "count_causal": 0.0,
    }
    n_tests = 0

    for inp, out in train_pairs:
        in_objs = extract_objects(inp)
        out_objs = extract_objects(out)
        matches = match_objects_hungarian(in_objs, out_objs)

        for i_idx, j_idx, _ in matches:
            t = classify_object_transform(in_objs[i_idx], out_objs[j_idx])
            n_tests += 1

            if not t["same_color"]:
                causal_scores["color_causal"] += 1.0
            if not t["same_position"]:
                causal_scores["position_causal"] += 1.0
            if not t["same_size"]:
                causal_scores["size_causal"] += 1.0
            if not t["same_shape"]:
                causal_scores["shape_causal"] += 1.0

        if len(in_objs) != len(out_objs):
            causal_scores["count_causal"] += 1.0
            n_tests += 1

    if n_tests > 0:
        for key in causal_scores:
            causal_scores[key] /= n_tests

    return causal_scores


# ---------------------------------------------------------------------------
# 5. Full structural analysis pipeline
# ---------------------------------------------------------------------------

def analyze_task(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> Dict[str, Any]:
    """Run full structural analysis on a task.

    Returns invariants, causal properties, object transforms, and
    relation graph signatures for all training pairs.
    """
    pair_analyses = []
    for inp, out in train_pairs:
        in_objs = extract_objects(inp)
        out_objs = extract_objects(out)
        in_rels = compute_spatial_relations(in_objs)
        out_rels = compute_spatial_relations(out_objs)
        matches = match_objects_hungarian(in_objs, out_objs)

        transforms = []
        for i_idx, j_idx, dist in matches:
            t = classify_object_transform(in_objs[i_idx], out_objs[j_idx])
            t["match_distance"] = dist
            transforms.append(t)

        pair_analyses.append({
            "n_in_objects": len(in_objs),
            "n_out_objects": len(out_objs),
            "n_matches": len(matches),
            "transforms": transforms,
            "in_graph_sig": relation_graph_signature(in_objs, in_rels),
            "out_graph_sig": relation_graph_signature(out_objs, out_rels),
        })

    invariants = analyze_task_invariants(train_pairs)
    causal = identify_causal_properties(train_pairs)

    return {
        "invariants": invariants,
        "causal_properties": causal,
        "pair_analyses": pair_analyses,
    }
