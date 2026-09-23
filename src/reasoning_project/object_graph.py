"""Object-graph representation and rewrite rule induction for ARC tasks.

Represents grids as object graphs with properties (color, size, position,
shape, adjacency, containment) and infers graph rewrite rules from examples.
"""
from __future__ import annotations

import numpy as np
from typing import Optional, List, Tuple, Dict, Set, Any
from dataclasses import dataclass, field
from scipy import ndimage


@dataclass
class GridObject:
    """A connected component in a grid."""
    obj_id: int
    color: int
    pixels: List[Tuple[int, int]]
    bbox: Tuple[int, int, int, int]  # min_r, min_c, max_r, max_c
    centroid: Tuple[float, float]
    size: int

    @property
    def width(self) -> int:
        return self.bbox[3] - self.bbox[1] + 1

    @property
    def height(self) -> int:
        return self.bbox[2] - self.bbox[0] + 1

    @property
    def is_rectangular(self) -> bool:
        return self.size == self.width * self.height

    @property
    def aspect_ratio(self) -> float:
        return self.width / max(self.height, 1)


@dataclass
class ObjectRelation:
    """A relation between two objects."""
    source_id: int
    target_id: int
    relation_type: str
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ObjectGraph:
    """Graph of objects with their relations."""
    objects: List[GridObject]
    relations: List[ObjectRelation]
    background_color: int = 0
    grid_shape: Tuple[int, int] = (0, 0)


def extract_objects(grid: np.ndarray, background: int = 0) -> List[GridObject]:
    """Extract connected components as objects."""
    arr = np.asarray(grid, dtype=int)
    objects = []
    obj_id = 0

    for color in sorted(set(arr.flatten().tolist())):
        if color == background:
            continue
        mask = arr == color
        labeled, n = ndimage.label(mask)
        for comp_id in range(1, n + 1):
            pixels = list(zip(*np.where(labeled == comp_id)))
            if not pixels:
                continue
            rows = [p[0] for p in pixels]
            cols = [p[1] for p in pixels]
            bbox = (min(rows), min(cols), max(rows), max(cols))
            centroid = (float(np.mean(rows)), float(np.mean(cols)))
            objects.append(GridObject(
                obj_id=obj_id,
                color=color,
                pixels=pixels,
                bbox=bbox,
                centroid=centroid,
                size=len(pixels),
            ))
            obj_id += 1

    return objects


def compute_relations(objects: List[GridObject], grid_shape: Tuple[int, int]) -> List[ObjectRelation]:
    """Compute spatial relations between objects."""
    relations = []

    for i, obj_a in enumerate(objects):
        for j, obj_b in enumerate(objects):
            if i == j:
                continue

            # Adjacency: objects whose bboxes are within 1 pixel
            a_r0, a_c0, a_r1, a_c1 = obj_a.bbox
            b_r0, b_c0, b_r1, b_c1 = obj_b.bbox

            h_gap = max(b_c0 - a_c1, a_c0 - b_c1, 0)
            v_gap = max(b_r0 - a_r1, a_r0 - b_r1, 0)

            if h_gap <= 1 and v_gap <= 1:
                relations.append(ObjectRelation(
                    source_id=obj_a.obj_id,
                    target_id=obj_b.obj_id,
                    relation_type="adjacent",
                ))

            # Containment: a contains b if all b pixels are within a's bbox
            if (b_r0 >= a_r0 and b_r1 <= a_r1 and
                b_c0 >= a_c0 and b_c1 <= a_c1 and
                obj_a.size > obj_b.size):
                relations.append(ObjectRelation(
                    source_id=obj_a.obj_id,
                    target_id=obj_b.obj_id,
                    relation_type="contains",
                ))

            # Alignment
            if abs(obj_a.centroid[0] - obj_b.centroid[0]) < 0.5:
                relations.append(ObjectRelation(
                    source_id=obj_a.obj_id,
                    target_id=obj_b.obj_id,
                    relation_type="horizontally_aligned",
                ))
            if abs(obj_a.centroid[1] - obj_b.centroid[1]) < 0.5:
                relations.append(ObjectRelation(
                    source_id=obj_a.obj_id,
                    target_id=obj_b.obj_id,
                    relation_type="vertically_aligned",
                ))

            # Same color
            if obj_a.color == obj_b.color:
                relations.append(ObjectRelation(
                    source_id=obj_a.obj_id,
                    target_id=obj_b.obj_id,
                    relation_type="same_color",
                ))

            # Same size
            if obj_a.size == obj_b.size:
                relations.append(ObjectRelation(
                    source_id=obj_a.obj_id,
                    target_id=obj_b.obj_id,
                    relation_type="same_size",
                ))

            # Same shape
            if (obj_a.height == obj_b.height and obj_a.width == obj_b.width and
                obj_a.is_rectangular == obj_b.is_rectangular):
                relations.append(ObjectRelation(
                    source_id=obj_a.obj_id,
                    target_id=obj_b.obj_id,
                    relation_type="same_shape",
                ))

    return relations


def build_object_graph(grid: np.ndarray, background: int = 0) -> ObjectGraph:
    """Build complete object graph from grid."""
    objects = extract_objects(grid, background)
    relations = compute_relations(objects, grid.shape)
    return ObjectGraph(
        objects=objects,
        relations=relations,
        background_color=background,
        grid_shape=grid.shape,
    )


def graph_signature(graph: ObjectGraph) -> Dict[str, Any]:
    """Compute a structural signature for matching."""
    return {
        "n_objects": len(graph.objects),
        "n_relations": len(graph.relations),
        "colors": sorted(set(o.color for o in graph.objects)),
        "sizes": sorted(o.size for o in graph.objects),
        "relation_types": sorted(set(r.relation_type for r in graph.relations)),
        "has_containment": any(r.relation_type == "contains" for r in graph.relations),
        "has_alignment": any("aligned" in r.relation_type for r in graph.relations),
    }


@dataclass
class RewriteRule:
    """A graph rewrite rule: condition -> action."""
    name: str
    condition: Dict[str, Any]
    action: str
    parameters: Dict[str, Any] = field(default_factory=dict)


def infer_rewrite_rules(
    input_graphs: List[ObjectGraph],
    output_graphs: List[ObjectGraph],
) -> List[RewriteRule]:
    """Infer graph rewrite rules from input-output graph pairs."""
    rules = []

    for in_g, out_g in zip(input_graphs, output_graphs):
        in_sig = graph_signature(in_g)
        out_sig = graph_signature(out_g)

        if out_sig["n_objects"] < in_sig["n_objects"]:
            rules.append(RewriteRule(
                name="remove_objects",
                condition={"n_objects_decrease": in_sig["n_objects"] - out_sig["n_objects"]},
                action="remove",
                parameters={"removed_count": in_sig["n_objects"] - out_sig["n_objects"]},
            ))

        if out_sig["n_objects"] > in_sig["n_objects"]:
            rules.append(RewriteRule(
                name="add_objects",
                condition={"n_objects_increase": out_sig["n_objects"] - in_sig["n_objects"]},
                action="add",
                parameters={"added_count": out_sig["n_objects"] - in_sig["n_objects"]},
            ))

        if set(out_sig["colors"]) != set(in_sig["colors"]):
            rules.append(RewriteRule(
                name="recolor",
                condition={"input_colors": in_sig["colors"]},
                action="recolor",
                parameters={
                    "new_colors": sorted(set(out_sig["colors"]) - set(in_sig["colors"])),
                    "removed_colors": sorted(set(in_sig["colors"]) - set(out_sig["colors"])),
                },
            ))

    return rules


def object_graph_features(grid: np.ndarray) -> Dict[str, float]:
    """Compute object-graph features for routing decisions."""
    graph = build_object_graph(grid)
    sig = graph_signature(graph)
    return {
        "n_objects": float(sig["n_objects"]),
        "n_colors": float(len(sig["colors"])),
        "n_relations": float(sig["n_relations"]),
        "has_containment": float(sig["has_containment"]),
        "has_alignment": float(sig["has_alignment"]),
        "max_size": float(max(sig["sizes"])) if sig["sizes"] else 0.0,
        "min_size": float(min(sig["sizes"])) if sig["sizes"] else 0.0,
    }


def _match_objects_by_position(in_objs: List[GridObject], out_objs: List[GridObject]) -> List[Tuple[GridObject, GridObject]]:
    """Match input to output objects by centroid proximity."""
    matched = []
    used = set()
    for in_obj in in_objs:
        best_dist = float("inf")
        best_j = -1
        for j, out_obj in enumerate(out_objs):
            if j in used:
                continue
            dist = ((in_obj.centroid[0] - out_obj.centroid[0]) ** 2 +
                    (in_obj.centroid[1] - out_obj.centroid[1]) ** 2)
            if dist < best_dist:
                best_dist = dist
                best_j = j
        if best_j >= 0:
            matched.append((in_obj, out_objs[best_j]))
            used.add(best_j)
    return matched


def _infer_color_map(pairs: List[Tuple[GridObject, GridObject]]) -> Optional[Dict[int, int]]:
    """Infer a consistent color remapping from matched object pairs."""
    cmap: Dict[int, int] = {}
    for in_obj, out_obj in pairs:
        if in_obj.color in cmap:
            if cmap[in_obj.color] != out_obj.color:
                return None
        cmap[in_obj.color] = out_obj.color
    return cmap


def _infer_object_filter(
    in_objs: List[GridObject],
    out_objs: List[GridObject],
) -> Optional[Dict[str, Any]]:
    """Infer which objects are kept/removed based on a simple property predicate."""
    out_pixels = set()
    for obj in out_objs:
        out_pixels.update(obj.pixels)

    kept = []
    removed = []
    for obj in in_objs:
        if any(p in out_pixels for p in obj.pixels):
            kept.append(obj)
        else:
            removed.append(obj)

    if not removed:
        return None

    for attr in ["color", "size"]:
        kept_vals = set(getattr(o, attr) for o in kept)
        removed_vals = set(getattr(o, attr) for o in removed)
        if not kept_vals.intersection(removed_vals):
            return {"filter_attr": attr, "keep_values": sorted(kept_vals), "remove_values": sorted(removed_vals)}

    if kept and removed:
        kept_sizes = [o.size for o in kept]
        removed_sizes = [o.size for o in removed]
        if min(kept_sizes) > max(removed_sizes):
            return {"filter_attr": "size_threshold", "min_size": min(kept_sizes)}
        if max(kept_sizes) < min(removed_sizes):
            return {"filter_attr": "size_threshold_max", "max_size": max(kept_sizes)}

    return None


def solve_task_object_graph(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
    background: int = 0,
) -> Optional[Tuple[List[np.ndarray], Dict[str, Any]]]:
    """Attempt to solve a task using object-graph rewrite rules."""
    if not train_pairs:
        return None

    in_graphs = [build_object_graph(inp, background) for inp, _ in train_pairs]
    out_graphs = [build_object_graph(out, background) for _, out in train_pairs]

    # Strategy 1: consistent color remapping across all examples
    all_cmaps = []
    for in_g, out_g in zip(in_graphs, out_graphs):
        if len(in_g.objects) != len(out_g.objects):
            break
        matched = _match_objects_by_position(in_g.objects, out_g.objects)
        cmap = _infer_color_map(matched)
        if cmap is None:
            break
        all_cmaps.append(cmap)
    else:
        if all_cmaps and len(all_cmaps) == len(train_pairs):
            merged = all_cmaps[0]
            consistent = True
            for cm in all_cmaps[1:]:
                for k, v in cm.items():
                    if k in merged and merged[k] != v:
                        consistent = False
                        break
                    merged[k] = v
                if not consistent:
                    break
            if consistent and merged:
                ok = True
                for inp, out in train_pairs:
                    pred = inp.copy()
                    for old_c, new_c in merged.items():
                        pred[inp == old_c] = new_c
                    if not np.array_equal(pred, out):
                        ok = False
                        break
                if ok:
                    predictions = []
                    for test_inp in test_inputs:
                        pred = test_inp.copy()
                        for old_c, new_c in merged.items():
                            pred[test_inp == old_c] = new_c
                        predictions.append(pred)
                    return predictions, {"strategy": "color_remap", "color_map": {str(k): v for k, v in merged.items()}}

    # Strategy 2: object filtering (keep/remove by property)
    same_size = all(inp.shape == out.shape for inp, out in train_pairs)
    if same_size:
        filters = []
        for in_g, out_g in zip(in_graphs, out_graphs):
            filt = _infer_object_filter(in_g.objects, out_g.objects)
            if filt is None:
                break
            filters.append(filt)
        else:
            if filters and all(f["filter_attr"] == filters[0]["filter_attr"] for f in filters):
                filt = filters[0]
                ok = True
                for inp, out in train_pairs:
                    pred = np.full_like(inp, background)
                    objs = extract_objects(inp, background)
                    for obj in objs:
                        keep = False
                        if filt["filter_attr"] == "color":
                            keep = obj.color in filt["keep_values"]
                        elif filt["filter_attr"] == "size":
                            keep = obj.size in filt["keep_values"]
                        elif filt["filter_attr"] == "size_threshold":
                            keep = obj.size >= filt["min_size"]
                        elif filt["filter_attr"] == "size_threshold_max":
                            keep = obj.size <= filt["max_size"]
                        if keep:
                            for r, c in obj.pixels:
                                pred[r, c] = obj.color
                    if not np.array_equal(pred, out):
                        ok = False
                        break
                if ok:
                    predictions = []
                    for test_inp in test_inputs:
                        pred = np.full_like(test_inp, background)
                        objs = extract_objects(test_inp, background)
                        for obj in objs:
                            keep = False
                            if filt["filter_attr"] == "color":
                                keep = obj.color in filt["keep_values"]
                            elif filt["filter_attr"] == "size":
                                keep = obj.size in filt["keep_values"]
                            elif filt["filter_attr"] == "size_threshold":
                                keep = obj.size >= filt["min_size"]
                            elif filt["filter_attr"] == "size_threshold_max":
                                keep = obj.size <= filt["max_size"]
                            if keep:
                                for r, c in obj.pixels:
                                    pred[r, c] = obj.color
                        predictions.append(pred)
                    return predictions, {"strategy": "object_filter", "filter": filt}

    # Strategy 3: crop to largest object bounding box
    all_same_crop = True
    crop_strategy = None
    for inp, out in train_pairs:
        objs = extract_objects(inp, background)
        if not objs:
            all_same_crop = False
            break
        largest = max(objs, key=lambda o: o.size)
        r0, c0, r1, c1 = largest.bbox
        cropped = inp[r0:r1+1, c0:c1+1]
        if np.array_equal(cropped, out):
            crop_strategy = "crop_largest"
        else:
            all_same_crop = False
            break
    if all_same_crop and crop_strategy:
        predictions = []
        for test_inp in test_inputs:
            objs = extract_objects(test_inp, background)
            if objs:
                largest = max(objs, key=lambda o: o.size)
                r0, c0, r1, c1 = largest.bbox
                predictions.append(test_inp[r0:r1+1, c0:c1+1].copy())
            else:
                predictions.append(test_inp.copy())
        return predictions, {"strategy": "crop_largest_object"}

    # Strategy 4: crop to smallest object bounding box
    all_same_crop = True
    for inp, out in train_pairs:
        objs = extract_objects(inp, background)
        if not objs:
            all_same_crop = False
            break
        smallest = min(objs, key=lambda o: o.size)
        r0, c0, r1, c1 = smallest.bbox
        cropped = inp[r0:r1+1, c0:c1+1]
        if not np.array_equal(cropped, out):
            all_same_crop = False
            break
    if all_same_crop:
        predictions = []
        for test_inp in test_inputs:
            objs = extract_objects(test_inp, background)
            if objs:
                smallest = min(objs, key=lambda o: o.size)
                r0, c0, r1, c1 = smallest.bbox
                predictions.append(test_inp[r0:r1+1, c0:c1+1].copy())
            else:
                predictions.append(test_inp.copy())
        return predictions, {"strategy": "crop_smallest_object"}

    # Strategy 5: crop to unique-color object (the one object whose color appears only once)
    for inp, out in train_pairs:
        objs = extract_objects(inp, background)
        color_counts: Dict[int, int] = {}
        for obj in objs:
            color_counts[obj.color] = color_counts.get(obj.color, 0) + 1
        unique_objs = [obj for obj in objs if color_counts.get(obj.color, 0) == 1]
        if len(unique_objs) != 1:
            break
        r0, c0, r1, c1 = unique_objs[0].bbox
        cropped = inp[r0:r1+1, c0:c1+1]
        if not np.array_equal(cropped, out):
            break
    else:
        if train_pairs:
            predictions = []
            for test_inp in test_inputs:
                objs = extract_objects(test_inp, background)
                color_counts_t: Dict[int, int] = {}
                for obj in objs:
                    color_counts_t[obj.color] = color_counts_t.get(obj.color, 0) + 1
                unique_objs_t = [obj for obj in objs if color_counts_t.get(obj.color, 0) == 1]
                if unique_objs_t:
                    target = unique_objs_t[0]
                    r0, c0, r1, c1 = target.bbox
                    predictions.append(test_inp[r0:r1+1, c0:c1+1].copy())
                else:
                    predictions.append(test_inp.copy())
            return predictions, {"strategy": "crop_unique_color_object"}

    # Strategy 6: recolor objects by size rank
    if same_size:
        size_recolor_ok = True
        recolor_map: Optional[Dict[int, int]] = None
        for inp, out in train_pairs:
            in_objs = extract_objects(inp, background)
            out_objs = extract_objects(out, background)
            if len(in_objs) != len(out_objs):
                size_recolor_ok = False
                break
            in_sorted = sorted(in_objs, key=lambda o: (o.size, o.centroid))
            out_sorted = sorted(out_objs, key=lambda o: (o.size, o.centroid))
            cur_map: Dict[int, int] = {}
            for in_o, out_o in zip(in_sorted, out_sorted):
                rank = in_sorted.index(in_o)
                if rank in cur_map and cur_map[rank] != out_o.color:
                    size_recolor_ok = False
                    break
                cur_map[rank] = out_o.color
            if not size_recolor_ok:
                break
            if recolor_map is None:
                recolor_map = cur_map
            elif recolor_map != cur_map:
                size_recolor_ok = False
                break
        if size_recolor_ok and recolor_map:
            ok = True
            for inp, out in train_pairs:
                pred = np.full_like(inp, background)
                objs = extract_objects(inp, background)
                obj_sorted = sorted(objs, key=lambda o: (o.size, o.centroid))
                for rank, obj in enumerate(obj_sorted):
                    new_color = recolor_map.get(rank, obj.color)
                    for r, c in obj.pixels:
                        pred[r, c] = new_color
                if not np.array_equal(pred, out):
                    ok = False
                    break
            if ok:
                predictions = []
                for test_inp in test_inputs:
                    pred = np.full_like(test_inp, background)
                    objs = extract_objects(test_inp, background)
                    obj_sorted = sorted(objs, key=lambda o: (o.size, o.centroid))
                    for rank, obj in enumerate(obj_sorted):
                        new_color = recolor_map.get(rank, obj.color)
                        for r, c in obj.pixels:
                            pred[r, c] = new_color
                    predictions.append(pred)
                return predictions, {"strategy": "recolor_by_size_rank", "rank_map": {str(k): v for k, v in recolor_map.items()}}

    return None
