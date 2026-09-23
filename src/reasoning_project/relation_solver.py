"""Relational reasoning solver for ARC tasks.

Object-structural reasoning: instead of pixel-level pattern matching,
infer transformations over objects, relations, and structural invariants.

Core paradigms:
1. Persistent object identity — match input/output objects by structural signature
2. Spatial relationship algebra — above/below/left/right relative to separators
3. Structural signatures — area, perimeter, Euler characteristic, holes, symmetry
4. Object identity comparison — keep/remove objects based on shape equivalence
5. Structural property filtering — filled/hollow, symmetric/asymmetric, boundary/interior
6. Invariant-guided search — find what's preserved, then search transformations
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage
from scipy.optimize import linear_sum_assignment
from typing import Optional, List, Tuple, Dict, Any


def _compute_structural_signature(local_mask: np.ndarray) -> Dict[str, Any]:
    """Compute topology-aware structural fingerprint for an object.

    Captures: area, perimeter, Euler characteristic, holes, symmetry axes,
    convexity, bounding box ratio, skeleton properties.
    """
    area = int(local_mask.sum())
    h, w = local_mask.shape

    perimeter = 0
    for r in range(h):
        for c in range(w):
            if local_mask[r, c]:
                for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nr, nc = r + dr, c + dc
                    if nr < 0 or nr >= h or nc < 0 or nc >= w or not local_mask[nr, nc]:
                        perimeter += 1

    interior_bg = np.zeros_like(local_mask)
    bg_labeled, n_bg = ndimage.label(~local_mask)
    border_labels = set()
    border_labels.update(bg_labeled[0, :].tolist())
    border_labels.update(bg_labeled[-1, :].tolist())
    border_labels.update(bg_labeled[:, 0].tolist())
    border_labels.update(bg_labeled[:, -1].tolist())
    border_labels.discard(0)
    n_holes = 0
    for lab in range(1, n_bg + 1):
        if lab not in border_labels:
            n_holes += 1

    euler_char = 1 - n_holes

    h_sym = bool(np.array_equal(local_mask, local_mask[::-1, :]))
    v_sym = bool(np.array_equal(local_mask, local_mask[:, ::-1]))
    d_sym = False
    if h == w:
        d_sym = bool(np.array_equal(local_mask, local_mask.T))

    convexity = area / max(h * w, 1)

    return {
        "area": area,
        "perimeter": perimeter,
        "n_holes": n_holes,
        "euler_char": euler_char,
        "h_sym": h_sym,
        "v_sym": v_sym,
        "d_sym": d_sym,
        "convexity": convexity,
        "bbox_ratio": h / max(w, 1),
        "bbox_h": h,
        "bbox_w": w,
    }


def _extract_objects(grid: np.ndarray, bg: int = 0) -> List[Dict[str, Any]]:
    """Extract connected components as objects with structural signatures."""
    mask = grid != bg
    labeled, n = ndimage.label(mask)
    objects = []
    for lab in range(1, n + 1):
        obj_mask = labeled == lab
        rows, cols = np.where(obj_mask)
        if len(rows) == 0:
            continue
        r_min, r_max = rows.min(), rows.max()
        c_min, c_max = cols.min(), cols.max()
        bbox_h = r_max - r_min + 1
        bbox_w = c_max - c_min + 1
        patch = grid[r_min:r_max+1, c_min:c_max+1].copy()
        local_mask = obj_mask[r_min:r_max+1, c_min:c_max+1]
        colors = set(grid[obj_mask].tolist()) - {bg}
        sig = _compute_structural_signature(local_mask)
        objects.append({
            "label": lab,
            "mask": obj_mask,
            "rows": rows,
            "cols": cols,
            "bbox": (r_min, c_min, r_max, c_max),
            "center": (rows.mean(), cols.mean()),
            "size": int(obj_mask.sum()),
            "bbox_h": bbox_h,
            "bbox_w": bbox_w,
            "patch": patch,
            "local_mask": local_mask,
            "colors": colors,
            "primary_color": int(grid[obj_mask].flat[0]),
            "signature": sig,
        })
    return objects


def _extract_objects_by_color(grid: np.ndarray, bg: int = 0) -> List[Dict[str, Any]]:
    """Extract connected components per color (color-aware segmentation)."""
    objects = []
    for color in sorted(set(grid.flat) - {bg}):
        color_mask = grid == color
        labeled, n = ndimage.label(color_mask)
        for lab in range(1, n + 1):
            obj_mask = labeled == lab
            rows, cols = np.where(obj_mask)
            if len(rows) == 0:
                continue
            r_min, r_max = rows.min(), rows.max()
            c_min, c_max = cols.min(), cols.max()
            bbox_h = r_max - r_min + 1
            bbox_w = c_max - c_min + 1
            patch = grid[r_min:r_max+1, c_min:c_max+1].copy()
            local_mask = obj_mask[r_min:r_max+1, c_min:c_max+1]
            sig = _compute_structural_signature(local_mask)
            objects.append({
                "label": len(objects) + 1,
                "mask": obj_mask,
                "rows": rows,
                "cols": cols,
                "bbox": (r_min, c_min, r_max, c_max),
                "center": (rows.mean(), cols.mean()),
                "size": int(obj_mask.sum()),
                "bbox_h": bbox_h,
                "bbox_w": bbox_w,
                "patch": patch,
                "local_mask": local_mask,
                "colors": {color},
                "primary_color": color,
                "signature": sig,
            })
    return objects


def _find_separator_lines(grid: np.ndarray) -> List[Dict[str, Any]]:
    """Find horizontal or vertical separator lines spanning the full grid."""
    h, w = grid.shape
    separators = []
    for r in range(h):
        vals = set(grid[r, :].tolist())
        if len(vals) == 1 and 0 not in vals:
            separators.append({"type": "horizontal", "pos": r, "color": vals.pop()})
    for c in range(w):
        vals = set(grid[:, c].tolist())
        if len(vals) == 1 and 0 not in vals:
            separators.append({"type": "vertical", "pos": c, "color": vals.pop()})
    return separators


def _normalize_shape(patch: np.ndarray, local_mask: np.ndarray) -> np.ndarray:
    """Normalize an object to a binary shape (1 where object, 0 where bg)."""
    return local_mask.astype(int)


def _shapes_equal(obj1: Dict, obj2: Dict) -> bool:
    """Check if two objects have the same shape (ignoring color and position)."""
    s1 = _normalize_shape(obj1["patch"], obj1["local_mask"])
    s2 = _normalize_shape(obj2["patch"], obj2["local_mask"])
    if s1.shape != s2.shape:
        return False
    return np.array_equal(s1, s2)


def _is_filled_rectangle(obj: Dict) -> bool:
    """Check if an object is a solid filled rectangle."""
    return obj["size"] == obj["bbox_h"] * obj["bbox_w"]


def _is_symmetric(obj: Dict) -> bool:
    """Check if an object has any symmetry (horizontal or vertical)."""
    shape = _normalize_shape(obj["patch"], obj["local_mask"])
    h_sym = np.array_equal(shape, shape[::-1, :])
    v_sym = np.array_equal(shape, shape[:, ::-1])
    return h_sym or v_sym


# --------------------------------------------------------------------------
# Strategy 1: Keep/remove objects relative to separator
# --------------------------------------------------------------------------

def _try_keep_objects_relative_to_separator(train_pairs, test_inputs):
    """Keep objects on one side of a separator line, remove the rest."""
    if len(train_pairs) < 2:
        return None

    learned_rule = None

    for inp, out in train_pairs:
        seps = _find_separator_lines(inp)
        if not seps:
            return None

        objects = _extract_objects(inp)
        if len(objects) < 2:
            return None

        for sep in seps:
            if sep["type"] == "horizontal":
                above = [o for o in objects if o["center"][0] < sep["pos"]
                         and o["primary_color"] != sep["color"]]
                below = [o for o in objects if o["center"][0] > sep["pos"]
                         and o["primary_color"] != sep["color"]]
            else:
                above = [o for o in objects if o["center"][1] < sep["pos"]
                         and o["primary_color"] != sep["color"]]
                below = [o for o in objects if o["center"][1] > sep["pos"]
                         and o["primary_color"] != sep["color"]]

            if not above and not below:
                continue

            expected = inp.copy()
            for side_label, side_objects in [("above", above), ("below", below)]:
                test_grid = inp.copy()
                for o in (below if side_label == "above" else above):
                    test_grid[o["mask"]] = 0
                if np.array_equal(test_grid, out):
                    rule = {
                        "sep_type": sep["type"],
                        "sep_color": sep["color"],
                        "keep": side_label,
                    }
                    if learned_rule is None:
                        learned_rule = rule
                    elif learned_rule != rule:
                        return None
                    break
            else:
                continue
            break
        else:
            return None

    if learned_rule is None:
        return None

    predictions = []
    for test_inp in test_inputs:
        seps = _find_separator_lines(test_inp)
        matching_seps = [s for s in seps
                         if s["type"] == learned_rule["sep_type"]
                         and s["color"] == learned_rule["sep_color"]]
        if not matching_seps:
            return None

        sep = matching_seps[0]
        objects = _extract_objects(test_inp)
        result = test_inp.copy()

        for obj in objects:
            if obj["primary_color"] == sep["color"]:
                continue
            if sep["type"] == "horizontal":
                obj_side = "above" if obj["center"][0] < sep["pos"] else "below"
            else:
                obj_side = "above" if obj["center"][1] < sep["pos"] else "below"

            if obj_side != learned_rule["keep"]:
                result[obj["mask"]] = 0

        predictions.append(result)

    return predictions, {"strategy": "keep_relative_to_separator"}


# --------------------------------------------------------------------------
# Strategy 2: Keep same-shape objects, remove different
# --------------------------------------------------------------------------

def _try_keep_same_remove_different(train_pairs, test_inputs):
    """Keep objects with the most common shape, remove outlier shapes."""
    if len(train_pairs) < 2:
        return None

    keep_rule = None

    for inp, out in train_pairs:
        objects = _extract_objects(inp)
        if len(objects) < 3:
            return None

        shapes = []
        for i, obj in enumerate(objects):
            shapes.append(_normalize_shape(obj["patch"], obj["local_mask"]))

        shape_groups = []
        assigned = [False] * len(objects)
        for i in range(len(objects)):
            if assigned[i]:
                continue
            group = [i]
            assigned[i] = True
            for j in range(i + 1, len(objects)):
                if assigned[j]:
                    continue
                if _shapes_equal(objects[i], objects[j]):
                    group.append(j)
                    assigned[j] = True
            shape_groups.append(group)

        if len(shape_groups) < 2:
            return None

        kept_in_output = set()
        removed_from_output = set()
        for i, obj in enumerate(objects):
            obj_present = np.any(out[obj["mask"]] != 0)
            if obj_present:
                kept_in_output.add(i)
            else:
                removed_from_output.add(i)

        if not kept_in_output or not removed_from_output:
            return None

        kept_groups = [g for g in shape_groups if all(i in kept_in_output for i in g)]
        removed_groups = [g for g in shape_groups if all(i in removed_from_output for i in g)]

        if not kept_groups or not removed_groups:
            return None

        rule = "keep_largest_group"
        largest = max(shape_groups, key=len)
        if all(i in kept_in_output for i in largest):
            if keep_rule is None:
                keep_rule = rule
            elif keep_rule != rule:
                return None
        else:
            return None

    if keep_rule is None:
        return None

    predictions = []
    for test_inp in test_inputs:
        objects = _extract_objects(test_inp)
        if len(objects) < 3:
            return None

        shape_groups = []
        assigned = [False] * len(objects)
        for i in range(len(objects)):
            if assigned[i]:
                continue
            group = [i]
            assigned[i] = True
            for j in range(i + 1, len(objects)):
                if assigned[j]:
                    continue
                if _shapes_equal(objects[i], objects[j]):
                    group.append(j)
                    assigned[j] = True
            shape_groups.append(group)

        largest = max(shape_groups, key=len)
        keep_indices = set(largest)

        result = test_inp.copy()
        for i, obj in enumerate(objects):
            if i not in keep_indices:
                result[obj["mask"]] = 0
        predictions.append(result)

    return predictions, {"strategy": "keep_same_remove_different"}


# --------------------------------------------------------------------------
# Strategy 3: Keep filled objects, remove hollow
# --------------------------------------------------------------------------

def _try_keep_filled_remove_hollow(train_pairs, test_inputs):
    """Keep filled (solid) objects, remove hollow ones (or vice versa)."""
    if len(train_pairs) < 3:
        return None

    keep_filled = None

    for inp, out in train_pairs:
        objects = _extract_objects(inp)
        if len(objects) < 2:
            return None

        filled_objs = []
        hollow_objs = []
        for obj in objects:
            if _is_filled_rectangle(obj):
                filled_objs.append(obj)
            else:
                hollow_objs.append(obj)

        if not filled_objs or not hollow_objs:
            return None

        filled_kept = all(np.any(out[o["mask"]] != 0) for o in filled_objs)
        hollow_kept = all(np.any(out[o["mask"]] != 0) for o in hollow_objs)
        filled_removed = all(not np.any(out[o["mask"]] != 0) for o in filled_objs)
        hollow_removed = all(not np.any(out[o["mask"]] != 0) for o in hollow_objs)

        if filled_kept and hollow_removed:
            rule = True
        elif hollow_kept and filled_removed:
            rule = False
        else:
            return None

        if keep_filled is None:
            keep_filled = rule
        elif keep_filled != rule:
            return None

    if keep_filled is None:
        return None

    predictions = []
    for test_inp in test_inputs:
        objects = _extract_objects(test_inp)
        result = test_inp.copy()
        for obj in objects:
            is_filled = _is_filled_rectangle(obj)
            if (keep_filled and not is_filled) or (not keep_filled and is_filled):
                result[obj["mask"]] = 0
        predictions.append(result)

    return predictions, {"strategy": "keep_filled_remove_hollow"}


# --------------------------------------------------------------------------
# Strategy 4: Keep symmetric objects, remove asymmetric
# --------------------------------------------------------------------------

def _try_keep_symmetric_remove_asymmetric(train_pairs, test_inputs):
    """Keep symmetric objects, remove asymmetric (or vice versa)."""
    if len(train_pairs) < 3:
        return None

    keep_sym = None

    for inp, out in train_pairs:
        objects = _extract_objects(inp)
        if len(objects) < 2:
            return None

        sym_objs = [o for o in objects if _is_symmetric(o)]
        asym_objs = [o for o in objects if not _is_symmetric(o)]

        if not sym_objs or not asym_objs:
            return None

        sym_kept = all(np.any(out[o["mask"]] != 0) for o in sym_objs)
        asym_removed = all(not np.any(out[o["mask"]] != 0) for o in asym_objs)

        if sym_kept and asym_removed:
            rule = True
        elif all(np.any(out[o["mask"]] != 0) for o in asym_objs) and \
             all(not np.any(out[o["mask"]] != 0) for o in sym_objs):
            rule = False
        else:
            return None

        if keep_sym is None:
            keep_sym = rule
        elif keep_sym != rule:
            return None

    if keep_sym is None:
        return None

    predictions = []
    for test_inp in test_inputs:
        objects = _extract_objects(test_inp)
        result = test_inp.copy()
        for obj in objects:
            is_sym = _is_symmetric(obj)
            if (keep_sym and not is_sym) or (not keep_sym and is_sym):
                result[obj["mask"]] = 0
        predictions.append(result)

    return predictions, {"strategy": "keep_symmetric_remove_asymmetric"}


# --------------------------------------------------------------------------
# Strategy 5: Remove objects touching boundary
# --------------------------------------------------------------------------

def _try_remove_boundary_objects(train_pairs, test_inputs):
    """Remove objects touching the grid boundary, keep interior ones."""
    if len(train_pairs) < 3:
        return None

    keep_interior = None

    for inp, out in train_pairs:
        h, w = inp.shape
        objects = _extract_objects(inp)
        if len(objects) < 2:
            return None

        interior = []
        boundary = []
        for obj in objects:
            r_min, c_min, r_max, c_max = obj["bbox"]
            touches = r_min == 0 or c_min == 0 or r_max == h - 1 or c_max == w - 1
            if touches:
                boundary.append(obj)
            else:
                interior.append(obj)

        if not interior or not boundary:
            return None

        int_kept = all(np.any(out[o["mask"]] != 0) for o in interior)
        bnd_removed = all(not np.any(out[o["mask"]] != 0) for o in boundary)

        if int_kept and bnd_removed:
            rule = True
        elif all(np.any(out[o["mask"]] != 0) for o in boundary) and \
             all(not np.any(out[o["mask"]] != 0) for o in interior):
            rule = False
        else:
            return None

        if keep_interior is None:
            keep_interior = rule
        elif keep_interior != rule:
            return None

    if keep_interior is None:
        return None

    predictions = []
    for test_inp in test_inputs:
        h, w = test_inp.shape
        objects = _extract_objects(test_inp)
        result = test_inp.copy()
        for obj in objects:
            r_min, c_min, r_max, c_max = obj["bbox"]
            touches = r_min == 0 or c_min == 0 or r_max == h - 1 or c_max == w - 1
            if (keep_interior and touches) or (not keep_interior and not touches):
                result[obj["mask"]] = 0
        predictions.append(result)

    return predictions, {"strategy": "remove_boundary_objects"}


# --------------------------------------------------------------------------
# Strategy 6: Keep largest object per color group
# --------------------------------------------------------------------------

def _try_keep_largest_per_color(train_pairs, test_inputs):
    """For each color, keep only the largest object."""
    if len(train_pairs) < 2:
        return None

    for inp, out in train_pairs:
        objects = _extract_objects(inp)
        if len(objects) < 2:
            return None

        color_groups = {}
        for obj in objects:
            c = obj["primary_color"]
            if c not in color_groups:
                color_groups[c] = []
            color_groups[c].append(obj)

        has_multi_color = any(len(g) > 1 for g in color_groups.values())
        if not has_multi_color:
            return None

        expected = np.zeros_like(inp)
        for color, group in color_groups.items():
            largest = max(group, key=lambda o: o["size"])
            expected[largest["mask"]] = inp[largest["mask"]]

        if not np.array_equal(expected, out):
            return None

    predictions = []
    for test_inp in test_inputs:
        objects = _extract_objects(test_inp)
        color_groups = {}
        for obj in objects:
            c = obj["primary_color"]
            if c not in color_groups:
                color_groups[c] = []
            color_groups[c].append(obj)

        result = np.zeros_like(test_inp)
        for color, group in color_groups.items():
            largest = max(group, key=lambda o: o["size"])
            result[largest["mask"]] = test_inp[largest["mask"]]
        predictions.append(result)

    return predictions, {"strategy": "keep_largest_per_color"}


# --------------------------------------------------------------------------
# Strategy 7: Recolor objects by relative position
# --------------------------------------------------------------------------

def _try_recolor_by_vertical_position(train_pairs, test_inputs):
    """Recolor objects based on their vertical position (top=color_a, bottom=color_b)."""
    if len(train_pairs) < 2:
        return None

    color_map_rule = None

    for inp, out in train_pairs:
        objects_in = _extract_objects(inp)
        objects_out = _extract_objects(out)
        if len(objects_in) < 2 or len(objects_in) != len(objects_out):
            return None

        sorted_by_y = sorted(objects_in, key=lambda o: o["center"][0])

        mapping = {}
        for obj_in, obj_sorted in zip(sorted_by_y, sorted(objects_out, key=lambda o: o["center"][0])):
            if obj_in["size"] != obj_sorted["size"]:
                return None
            in_color = obj_in["primary_color"]
            out_color = obj_sorted["primary_color"]
            rank = sorted_by_y.index(obj_in)
            mapping[rank] = (in_color, out_color)

        if color_map_rule is None:
            color_map_rule = mapping
        elif color_map_rule != mapping:
            return None

    if color_map_rule is None or not any(v[0] != v[1] for v in color_map_rule.values()):
        return None

    predictions = []
    for test_inp in test_inputs:
        objects = _extract_objects(test_inp)
        if len(objects) != len(color_map_rule):
            return None
        sorted_objs = sorted(objects, key=lambda o: o["center"][0])
        result = test_inp.copy()
        for rank, obj in enumerate(sorted_objs):
            if rank in color_map_rule:
                _, new_color = color_map_rule[rank]
                result[obj["mask"]] = new_color
        predictions.append(result)

    return predictions, {"strategy": "recolor_by_vertical_position"}


# --------------------------------------------------------------------------
# Strategy 8: Keep objects with holes, remove solid (or vice versa)
# --------------------------------------------------------------------------

def _try_keep_holey_remove_solid(train_pairs, test_inputs):
    """Keep objects with holes (Euler char < 1), remove solid ones."""
    if len(train_pairs) < 3:
        return None

    keep_holey = None

    for inp, out in train_pairs:
        objects = _extract_objects(inp)
        if len(objects) < 2:
            return None

        holey = [o for o in objects if o["signature"]["n_holes"] > 0]
        solid = [o for o in objects if o["signature"]["n_holes"] == 0]

        if not holey or not solid:
            return None

        holey_kept = all(np.any(out[o["mask"]] != 0) for o in holey)
        solid_removed = all(not np.any(out[o["mask"]] != 0) for o in solid)

        if holey_kept and solid_removed:
            rule = True
        elif all(np.any(out[o["mask"]] != 0) for o in solid) and \
             all(not np.any(out[o["mask"]] != 0) for o in holey):
            rule = False
        else:
            return None

        if keep_holey is None:
            keep_holey = rule
        elif keep_holey != rule:
            return None

    if keep_holey is None:
        return None

    predictions = []
    for test_inp in test_inputs:
        objects = _extract_objects(test_inp)
        result = test_inp.copy()
        for obj in objects:
            has_holes = obj["signature"]["n_holes"] > 0
            if (keep_holey and not has_holes) or (not keep_holey and has_holes):
                result[obj["mask"]] = 0
        predictions.append(result)

    return predictions, {"strategy": "keep_holey_remove_solid"}


# --------------------------------------------------------------------------
# Strategy 9: Match objects by structural signature and apply color transform
# --------------------------------------------------------------------------

def _try_match_and_recolor_by_structure(train_pairs, test_inputs):
    """Match input→output objects by shape, learn per-signature color transform."""
    if len(train_pairs) < 3:
        return None

    color_transforms = {}

    for inp, out in train_pairs:
        in_objs = _extract_objects(inp)
        out_objs = _extract_objects(out)
        if len(in_objs) != len(out_objs) or len(in_objs) < 2:
            return None

        matched = set()
        for i_obj in in_objs:
            best_j = None
            best_overlap = 0
            for j, o_obj in enumerate(out_objs):
                if j in matched:
                    continue
                overlap = np.sum(i_obj["mask"] & o_obj["mask"])
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_j = j
            if best_j is None:
                return None
            matched.add(best_j)
            o_obj = out_objs[best_j]

            if not np.array_equal(i_obj["local_mask"], o_obj["local_mask"]):
                return None

            sig_key = (i_obj["signature"]["area"],
                       i_obj["signature"]["n_holes"],
                       i_obj["signature"]["bbox_h"],
                       i_obj["signature"]["bbox_w"])
            transform = (i_obj["primary_color"], o_obj["primary_color"])

            if sig_key in color_transforms:
                if color_transforms[sig_key] != transform:
                    return None
            else:
                color_transforms[sig_key] = transform

    if not color_transforms or all(t[0] == t[1] for t in color_transforms.values()):
        return None

    predictions = []
    for test_inp in test_inputs:
        objects = _extract_objects(test_inp)
        result = test_inp.copy()
        for obj in objects:
            sig_key = (obj["signature"]["area"],
                       obj["signature"]["n_holes"],
                       obj["signature"]["bbox_h"],
                       obj["signature"]["bbox_w"])
            if sig_key in color_transforms:
                old_c, new_c = color_transforms[sig_key]
                if obj["primary_color"] == old_c:
                    result[obj["mask"]] = new_c
        predictions.append(result)

    return predictions, {"strategy": "match_and_recolor_by_structure"}


# --------------------------------------------------------------------------
# Strategy 10: Keep/remove by containment (InsideOutside)
# --------------------------------------------------------------------------

def _try_keep_by_containment(train_pairs, test_inputs):
    """Keep contained objects (inside) or containers (outside), remove the rest."""
    if len(train_pairs) < 2:
        return None

    keep_rule = None

    for inp, out in train_pairs:
        objects = _extract_objects(inp)
        if len(objects) < 2:
            return None

        contained = set()
        containers = set()
        for i, obj_a in enumerate(objects):
            for j, obj_b in enumerate(objects):
                if i == j:
                    continue
                a_r1, a_c1, a_r2, a_c2 = obj_a["bbox"]
                b_r1, b_c1, b_r2, b_c2 = obj_b["bbox"]
                if a_r1 <= b_r1 and a_c1 <= b_c1 and a_r2 >= b_r2 and a_c2 >= b_c2:
                    containers.add(i)
                    contained.add(j)

        pure_inside = contained - containers
        pure_outside = containers - contained
        if not pure_inside or not pure_outside:
            return None

        inside_kept = all(np.any(out[objects[i]["mask"]] != 0) for i in pure_inside)
        outside_removed = all(not np.any(out[objects[i]["mask"]] != 0) for i in pure_outside)

        if inside_kept and outside_removed:
            rule = "inside"
        elif all(np.any(out[objects[i]["mask"]] != 0) for i in pure_outside) and \
             all(not np.any(out[objects[i]["mask"]] != 0) for i in pure_inside):
            rule = "outside"
        else:
            return None

        if keep_rule is None:
            keep_rule = rule
        elif keep_rule != rule:
            return None

    if keep_rule is None:
        return None

    predictions = []
    for test_inp in test_inputs:
        objects = _extract_objects(test_inp)
        contained = set()
        containers = set()
        for i, obj_a in enumerate(objects):
            for j, obj_b in enumerate(objects):
                if i == j:
                    continue
                a_r1, a_c1, a_r2, a_c2 = obj_a["bbox"]
                b_r1, b_c1, b_r2, b_c2 = obj_b["bbox"]
                if a_r1 <= b_r1 and a_c1 <= b_c1 and a_r2 >= b_r2 and a_c2 >= b_c2:
                    containers.add(i)
                    contained.add(j)

        pure_inside = contained - containers
        pure_outside = containers - contained

        result = test_inp.copy()
        if keep_rule == "inside":
            for i, obj in enumerate(objects):
                if i not in pure_inside:
                    result[obj["mask"]] = 0
        else:
            for i, obj in enumerate(objects):
                if i not in pure_outside:
                    result[obj["mask"]] = 0
        predictions.append(result)

    return predictions, {"strategy": "keep_by_containment"}


# --------------------------------------------------------------------------
# Strategy 11: Extract unique (different) object (SameDifferent)
# --------------------------------------------------------------------------

def _try_extract_unique_object(train_pairs, test_inputs):
    """Extract the 'odd one out' — the object with a unique shape."""
    if len(train_pairs) < 2:
        return None

    extract_mode = None

    for inp, out in train_pairs:
        objects = _extract_objects(inp)
        if len(objects) < 3:
            return None

        shape_groups = []
        assigned = [False] * len(objects)
        for i in range(len(objects)):
            if assigned[i]:
                continue
            group = [i]
            assigned[i] = True
            for j in range(i + 1, len(objects)):
                if assigned[j]:
                    continue
                if _shapes_equal(objects[i], objects[j]):
                    group.append(j)
                    assigned[j] = True
            shape_groups.append(group)

        if len(shape_groups) < 2:
            return None

        unique_groups = [g for g in shape_groups if len(g) == 1]
        majority_groups = [g for g in shape_groups if len(g) > 1]
        if len(unique_groups) != 1 or not majority_groups:
            return None

        unique_idx = unique_groups[0][0]
        unique_obj = objects[unique_idx]

        out_objs = _extract_objects(out)
        if len(out_objs) == 1:
            out_obj = out_objs[0]
            if _shapes_equal(unique_obj, out_obj):
                mode = "extract_unique"
            else:
                return None
        else:
            return None

        if extract_mode is None:
            extract_mode = mode
        elif extract_mode != mode:
            return None

    if extract_mode is None:
        return None

    predictions = []
    for test_inp in test_inputs:
        objects = _extract_objects(test_inp)
        if len(objects) < 3:
            return None

        shape_groups = []
        assigned = [False] * len(objects)
        for i in range(len(objects)):
            if assigned[i]:
                continue
            group = [i]
            assigned[i] = True
            for j in range(i + 1, len(objects)):
                if assigned[j]:
                    continue
                if _shapes_equal(objects[i], objects[j]):
                    group.append(j)
                    assigned[j] = True
            shape_groups.append(group)

        unique_groups = [g for g in shape_groups if len(g) == 1]
        if len(unique_groups) != 1:
            return None

        unique_idx = unique_groups[0][0]
        unique_obj = objects[unique_idx]
        r_min, c_min, r_max, c_max = unique_obj["bbox"]
        result = np.zeros_like(test_inp)
        patch = test_inp[r_min:r_max+1, c_min:c_max+1].copy()
        result[:patch.shape[0], :patch.shape[1]] = patch
        predictions.append(result)

    return predictions, {"strategy": "extract_unique_object"}


# --------------------------------------------------------------------------
# Strategy 12: Hungarian-matched recoloring
# --------------------------------------------------------------------------

def _signature_distance(sig1, sig2):
    """Weighted distance between structural signatures."""
    weights = {
        "area": 0.3, "perimeter": 0.1, "n_holes": 0.2,
        "h_sym": 0.05, "v_sym": 0.05, "convexity": 0.1,
        "bbox_ratio": 0.1, "bbox_h": 0.05, "bbox_w": 0.05,
    }
    dist = 0.0
    for key, w in weights.items():
        v1 = sig1.get(key, 0.0)
        v2 = sig2.get(key, 0.0)
        if isinstance(v1, bool):
            v1 = float(v1)
        if isinstance(v2, bool):
            v2 = float(v2)
        denom = max(abs(v1), abs(v2), 1.0)
        dist += w * abs(v1 - v2) / denom
    return dist


def _match_objects_hungarian(in_objects, out_objects):
    """Match input→output objects via Hungarian algorithm on structural+positional distance."""
    n_in = len(in_objects)
    n_out = len(out_objects)
    if n_in == 0 or n_out == 0:
        return []

    n = max(n_in, n_out)
    cost = np.full((n, n), 1e6)

    for i in range(n_in):
        for j in range(n_out):
            shape_dist = _signature_distance(
                in_objects[i]["signature"], out_objects[j]["signature"]
            )
            shape_bonus = 0.0
            lm1 = in_objects[i]["local_mask"]
            lm2 = out_objects[j]["local_mask"]
            if lm1.shape == lm2.shape and np.array_equal(lm1, lm2):
                shape_bonus = -2.0

            pos_dist = abs(in_objects[i]["center"][0] - out_objects[j]["center"][0]) + \
                       abs(in_objects[i]["center"][1] - out_objects[j]["center"][1])
            grid_h = in_objects[i]["mask"].shape[0]
            pos_norm = pos_dist / max(grid_h, 1)

            cost[i, j] = shape_dist + shape_bonus + 0.1 * pos_norm

    row_ind, col_ind = linear_sum_assignment(cost)

    matches = []
    for i, j in zip(row_ind, col_ind):
        if i < n_in and j < n_out and cost[i, j] < 10.0:
            matches.append((i, j, float(cost[i, j])))
    return matches


def _try_hungarian_recolor(train_pairs, test_inputs):
    """Match objects via Hungarian algorithm and learn structural-property-based recoloring."""
    if len(train_pairs) < 2:
        return None

    recolor_rules = []

    for inp, out in train_pairs:
        in_objs = _extract_objects(inp)
        out_objs = _extract_objects(out)
        if len(in_objs) != len(out_objs) or len(in_objs) < 2:
            return None

        matches = _match_objects_hungarian(in_objs, out_objs)
        if len(matches) != len(in_objs):
            return None

        pair_rules = []
        all_same_shape = True
        any_recolored = False
        for i_idx, j_idx, _ in matches:
            i_obj = in_objs[i_idx]
            o_obj = out_objs[j_idx]
            if not np.array_equal(i_obj["local_mask"], o_obj["local_mask"]):
                all_same_shape = False
                break
            if i_obj["primary_color"] != o_obj["primary_color"]:
                any_recolored = True
            pair_rules.append((i_obj["primary_color"], o_obj["primary_color"],
                              i_obj["size"], i_obj["signature"]["n_holes"]))

        if not all_same_shape or not any_recolored:
            return None
        recolor_rules.append(pair_rules)

    if not recolor_rules:
        return None

    size_sorted_first = sorted(recolor_rules[0], key=lambda x: x[2])
    color_by_size_rank = {}
    for rank, (_, new_c, _, _) in enumerate(size_sorted_first):
        color_by_size_rank[rank] = new_c

    consistent = True
    for rules in recolor_rules[1:]:
        sorted_rules = sorted(rules, key=lambda x: x[2])
        for rank, (_, new_c, _, _) in enumerate(sorted_rules):
            if rank in color_by_size_rank and color_by_size_rank[rank] != new_c:
                consistent = False
                break
        if not consistent:
            break

    if not consistent:
        return None

    predictions = []
    for test_inp in test_inputs:
        objects = _extract_objects(test_inp)
        if len(objects) != len(color_by_size_rank):
            return None

        sorted_objs = sorted(range(len(objects)), key=lambda i: objects[i]["size"])
        result = test_inp.copy()
        for rank, obj_idx in enumerate(sorted_objs):
            if rank in color_by_size_rank:
                result[objects[obj_idx]["mask"]] = color_by_size_rank[rank]
        predictions.append(result)

    return predictions, {"strategy": "hungarian_recolor"}


# --------------------------------------------------------------------------
# Strategy 13: Recolor by above/below position relative to reference
# --------------------------------------------------------------------------

def _try_recolor_by_spatial_relation(train_pairs, test_inputs):
    """Recolor objects based on above/below/left/right position relative to largest object."""
    if len(train_pairs) < 2:
        return None

    relation_rule = None

    for inp, out in train_pairs:
        in_objs = _extract_objects(inp)
        out_objs = _extract_objects(out)
        if len(in_objs) < 3 or len(in_objs) != len(out_objs):
            return None

        ref_idx = max(range(len(in_objs)), key=lambda i: in_objs[i]["size"])
        ref_obj = in_objs[ref_idx]

        matches = _match_objects_hungarian(in_objs, out_objs)
        if len(matches) != len(in_objs):
            return None

        above_colors = []
        below_colors = []
        for i_idx, j_idx, _ in matches:
            i_obj = in_objs[i_idx]
            o_obj = out_objs[j_idx]
            if i_idx == ref_idx:
                continue
            if not np.array_equal(i_obj["local_mask"], o_obj["local_mask"]):
                return None
            rel_pos = "above" if i_obj["center"][0] < ref_obj["center"][0] else "below"
            if rel_pos == "above":
                above_colors.append(o_obj["primary_color"])
            else:
                below_colors.append(o_obj["primary_color"])

        if not above_colors or not below_colors:
            return None
        if len(set(above_colors)) != 1 or len(set(below_colors)) != 1:
            return None
        if above_colors[0] == below_colors[0]:
            return None

        rule = {"above_color": above_colors[0], "below_color": below_colors[0]}
        if relation_rule is None:
            relation_rule = rule
        elif relation_rule != rule:
            return None

    if relation_rule is None:
        return None

    predictions = []
    for test_inp in test_inputs:
        objects = _extract_objects(test_inp)
        if len(objects) < 3:
            return None
        ref_idx = max(range(len(objects)), key=lambda i: objects[i]["size"])
        ref_obj = objects[ref_idx]

        result = test_inp.copy()
        for i, obj in enumerate(objects):
            if i == ref_idx:
                continue
            if obj["center"][0] < ref_obj["center"][0]:
                result[obj["mask"]] = relation_rule["above_color"]
            else:
                result[obj["mask"]] = relation_rule["below_color"]
        predictions.append(result)

    return predictions, {"strategy": "recolor_by_spatial_relation"}


# --------------------------------------------------------------------------
# Strategy 14: Keep touching objects (spatial adjacency filter)
# --------------------------------------------------------------------------

def _try_keep_touching_reference(train_pairs, test_inputs):
    """Keep objects touching a reference object, remove those not touching."""
    if len(train_pairs) < 2:
        return None

    ref_rule = None

    for inp, out in train_pairs:
        objects = _extract_objects(inp)
        if len(objects) < 3:
            return None

        largest_idx = max(range(len(objects)), key=lambda i: objects[i]["size"])
        ref_obj = objects[largest_idx]

        touching = set()
        not_touching = set()
        for i, obj in enumerate(objects):
            if i == largest_idx:
                continue
            dilated = ndimage.binary_dilation(ref_obj["mask"])
            if np.any(dilated & obj["mask"]):
                touching.add(i)
            else:
                not_touching.add(i)

        if not touching or not not_touching:
            return None

        touch_kept = all(np.any(out[objects[i]["mask"]] != 0) for i in touching)
        nontouch_removed = all(not np.any(out[objects[i]["mask"]] != 0) for i in not_touching)

        if touch_kept and nontouch_removed:
            rule = "keep_touching"
        elif all(np.any(out[objects[i]["mask"]] != 0) for i in not_touching) and \
             all(not np.any(out[objects[i]["mask"]] != 0) for i in touching):
            rule = "keep_not_touching"
        else:
            return None

        if ref_rule is None:
            ref_rule = rule
        elif ref_rule != rule:
            return None

    if ref_rule is None:
        return None

    predictions = []
    for test_inp in test_inputs:
        objects = _extract_objects(test_inp)
        if len(objects) < 3:
            return None
        largest_idx = max(range(len(objects)), key=lambda i: objects[i]["size"])
        ref_obj = objects[largest_idx]

        result = test_inp.copy()
        for i, obj in enumerate(objects):
            if i == largest_idx:
                continue
            dilated = ndimage.binary_dilation(ref_obj["mask"])
            is_touching = bool(np.any(dilated & obj["mask"]))
            if (ref_rule == "keep_touching" and not is_touching) or \
               (ref_rule == "keep_not_touching" and is_touching):
                result[obj["mask"]] = 0
        predictions.append(result)

    return predictions, {"strategy": "keep_touching_reference"}


# --------------------------------------------------------------------------
# Strategy 15: Keep objects on one side of separator (color-aware)
# --------------------------------------------------------------------------

def _try_keep_side_of_separator_color_aware(train_pairs, test_inputs):
    """Keep color-objects on one side of a separator, remove the other side."""
    if len(train_pairs) < 2:
        return None

    learned_rule = None

    for inp, out in train_pairs:
        seps = _find_separator_lines(inp)
        if not seps:
            return None

        objects = _extract_objects_by_color(inp)
        non_sep_objects = [o for o in objects
                          if o["primary_color"] not in {s["color"] for s in seps}]
        if len(non_sep_objects) < 2:
            return None

        for sep in seps:
            if sep["type"] == "horizontal":
                above = [o for o in non_sep_objects if o["center"][0] < sep["pos"]]
                below = [o for o in non_sep_objects if o["center"][0] > sep["pos"]]
            else:
                above = [o for o in non_sep_objects if o["center"][1] < sep["pos"]]
                below = [o for o in non_sep_objects if o["center"][1] > sep["pos"]]

            if not above or not below:
                continue

            for keep_side, keep_objs, remove_objs in [("above", above, below), ("below", below, above)]:
                test_grid = inp.copy()
                for o in remove_objs:
                    test_grid[o["mask"]] = 0
                if np.array_equal(test_grid, out):
                    rule = {"sep_type": sep["type"], "sep_color": sep["color"], "keep": keep_side}
                    if learned_rule is None:
                        learned_rule = rule
                    elif learned_rule != rule:
                        return None
                    break
            else:
                continue
            break
        else:
            return None

    if learned_rule is None:
        return None

    predictions = []
    for test_inp in test_inputs:
        seps = _find_separator_lines(test_inp)
        matching = [s for s in seps
                    if s["type"] == learned_rule["sep_type"]
                    and s["color"] == learned_rule["sep_color"]]
        if not matching:
            return None

        sep = matching[0]
        objects = _extract_objects_by_color(test_inp)
        non_sep = [o for o in objects if o["primary_color"] != sep["color"]]

        result = test_inp.copy()
        for obj in non_sep:
            if sep["type"] == "horizontal":
                side = "above" if obj["center"][0] < sep["pos"] else "below"
            else:
                side = "above" if obj["center"][1] < sep["pos"] else "below"
            if side != learned_rule["keep"]:
                result[obj["mask"]] = 0
        predictions.append(result)

    return predictions, {"strategy": "keep_side_of_separator_color_aware"}


# --------------------------------------------------------------------------
# Strategy 16: Extract inner content of containing object
# --------------------------------------------------------------------------

def _try_extract_inner_content(train_pairs, test_inputs):
    """Extract the content inside a containing frame/border object."""
    if len(train_pairs) < 2:
        return None

    for inp, out in train_pairs:
        objects = _extract_objects_by_color(inp)
        if len(objects) < 2:
            return None

        frame_candidates = [o for o in objects if o["signature"]["n_holes"] > 0]
        if not frame_candidates:
            return None

        frame = max(frame_candidates, key=lambda o: o["size"])
        fr1, fc1, fr2, fc2 = frame["bbox"]

        inner_region = inp[fr1:fr2+1, fc1:fc2+1].copy()
        frame_color = frame["primary_color"]
        for r in range(inner_region.shape[0]):
            for c in range(inner_region.shape[1]):
                if inner_region[r, c] == frame_color:
                    inner_region[r, c] = 0

        if inner_region.shape == out.shape and np.array_equal(inner_region, out):
            continue
        else:
            return None

    predictions = []
    for test_inp in test_inputs:
        objects = _extract_objects_by_color(test_inp)
        frame_candidates = [o for o in objects if o["signature"]["n_holes"] > 0]
        if not frame_candidates:
            return None

        frame = max(frame_candidates, key=lambda o: o["size"])
        fr1, fc1, fr2, fc2 = frame["bbox"]
        frame_color = frame["primary_color"]

        inner_region = test_inp[fr1:fr2+1, fc1:fc2+1].copy()
        for r in range(inner_region.shape[0]):
            for c in range(inner_region.shape[1]):
                if inner_region[r, c] == frame_color:
                    inner_region[r, c] = 0

        predictions.append(inner_region)

    return predictions, {"strategy": "extract_inner_content"}


# --------------------------------------------------------------------------
# Strategy 17: Count objects with a property (output is count grid)
# --------------------------------------------------------------------------

def _try_count_objects_inside(train_pairs, test_inputs):
    """Count objects inside a container and output a count-sized column."""
    if len(train_pairs) < 2:
        return None

    for inp, out in train_pairs:
        objects = _extract_objects_by_color(inp)
        if len(objects) < 2:
            return None

        frame_candidates = [o for o in objects if o["signature"]["n_holes"] > 0]
        if not frame_candidates:
            return None

        frame = max(frame_candidates, key=lambda o: o["size"])
        fr1, fc1, fr2, fc2 = frame["bbox"]

        inside_count = 0
        inside_color = None
        for obj in objects:
            if obj is frame or obj["primary_color"] == frame["primary_color"]:
                continue
            or1, oc1, or2, oc2 = obj["bbox"]
            if fr1 <= or1 and fc1 <= oc1 and fr2 >= or2 and fc2 >= oc2:
                inside_count += 1
                inside_color = obj["primary_color"]

        if inside_count == 0:
            return None

        expected = np.zeros((inside_count, 1), dtype=out.dtype)
        if out.shape != expected.shape:
            return None

    predictions = []
    for test_inp in test_inputs:
        objects = _extract_objects_by_color(test_inp)
        frame_candidates = [o for o in objects if o["signature"]["n_holes"] > 0]
        if not frame_candidates:
            return None

        frame = max(frame_candidates, key=lambda o: o["size"])
        fr1, fc1, fr2, fc2 = frame["bbox"]

        inside_count = 0
        for obj in objects:
            if obj is frame or obj["primary_color"] == frame["primary_color"]:
                continue
            or1, oc1, or2, oc2 = obj["bbox"]
            if fr1 <= or1 and fc1 <= oc1 and fr2 >= or2 and fc2 >= oc2:
                inside_count += 1

        predictions.append(np.zeros((max(inside_count, 1), 1), dtype=test_inp.dtype))

    return predictions, {"strategy": "count_objects_inside"}


RELATION_STRATEGIES = [
    _try_keep_objects_relative_to_separator,
    _try_keep_same_remove_different,
    _try_keep_filled_remove_hollow,
    _try_keep_symmetric_remove_asymmetric,
    _try_remove_boundary_objects,
    _try_keep_largest_per_color,
    _try_recolor_by_vertical_position,
    _try_keep_holey_remove_solid,
    _try_match_and_recolor_by_structure,
    _try_keep_by_containment,
    _try_extract_unique_object,
    _try_hungarian_recolor,
    _try_recolor_by_spatial_relation,
    _try_keep_touching_reference,
    _try_keep_side_of_separator_color_aware,
    _try_extract_inner_content,
    _try_count_objects_inside,
]


def solve_task_relation(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
) -> Optional[Tuple[List[np.ndarray], Dict[str, Any]]]:
    """Try all relation strategies with leave-one-out cross-validation guard."""
    if len(train_pairs) < 2:
        return None

    for strategy_fn in RELATION_STRATEGIES:
        try:
            if len(train_pairs) >= 3:
                all_valid = True
                for hold_out_idx in range(len(train_pairs)):
                    held_train = [p for i, p in enumerate(train_pairs) if i != hold_out_idx]
                    held_test_inp = [train_pairs[hold_out_idx][0]]
                    held_test_out = [train_pairs[hold_out_idx][1]]
                    result = strategy_fn(held_train, held_test_inp)
                    if result is None:
                        all_valid = False
                        break
                    preds, _ = result
                    if not np.array_equal(preds[0], held_test_out[0]):
                        all_valid = False
                        break
                if not all_valid:
                    continue
            else:
                result_check = strategy_fn(train_pairs, [train_pairs[0][0], train_pairs[1][0]])
                if result_check is None:
                    continue
                preds_check, _ = result_check
                if not np.array_equal(preds_check[0], train_pairs[0][1]):
                    continue
                if not np.array_equal(preds_check[1], train_pairs[1][1]):
                    continue

            result = strategy_fn(train_pairs, test_inputs)
            if result is not None:
                return result
        except Exception:
            continue

    return None
