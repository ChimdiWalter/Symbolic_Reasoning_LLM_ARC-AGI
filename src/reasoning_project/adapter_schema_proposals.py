"""AdapterGenesis schema proposals for alternative object extraction.

When the default connected-component extraction fails to provide objects
that can be discriminated by any property, this module proposes alternative
object schemas and re-runs selector invention on them.

Integration:
  - Called by adaptive_orchestrator._propose_adapter_genesis()
  - Feeds into SelectorInventor.propose_selectors()
  - Returns executable proposals ready for ProposalVerifier
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
from scipy import ndimage as ndi

from reasoning_project.reasoning_engine import (
    _extract_objects_with_properties,
    _add_relational_properties as _add_rel_props_raw,
    _get_property_value,
    _all_property_names,
)


def _safe_add_relational(objects, grid):
    """Wrapper that passes grid dimensions."""
    if grid is not None:
        h, w = grid.shape[:2]
        _add_rel_props_raw(objects, grid, h, w)
    return objects
from reasoning_project.selector_invention import SelectorInventor


@dataclass
class ObjectSchemaProposal:
    schema_name: str
    object_extractor_name: str
    objects: list
    relations: list
    properties: list
    evidence: dict = field(default_factory=dict)


# --- Alternative object extractors ---

def extract_per_color_components(grid: np.ndarray) -> List[Dict]:
    """Each same-color connected component is a separate object."""
    objects = []
    for c in sorted(set(grid.flatten().tolist())):
        if c == 0:
            continue
        labeled, n = ndi.label(grid == c)
        for i in range(1, n + 1):
            mask = labeled == i
            ys, xs = np.where(mask)
            r_min, c_min = int(ys.min()), int(xs.min())
            r_max, c_max = int(ys.max()), int(xs.max())
            bbox_h = r_max - r_min + 1
            bbox_w = c_max - c_min + 1
            local_mask = mask[r_min:r_max+1, c_min:c_max+1]
            objects.append({
                "mask": mask, "primary_color": c,
                "area": int(mask.sum()),
                "bbox": (r_min, c_min, r_max, c_max),
                "bbox_h": bbox_h, "bbox_w": bbox_w,
                "bbox_ratio": bbox_h / max(bbox_w, 1),
                "center_r": float(ys.mean()),
                "center_c": float(xs.mean()),
                "local_mask": local_mask,
                "n_holes": 0,
                "n_colors": 1,
                "convexity": float(mask.sum()) / max(bbox_h * bbox_w, 1),
                "is_filled_rect": bool(mask.sum() == bbox_h * bbox_w),
                "is_square": bbox_h == bbox_w,
            })
    return objects


def extract_monochrome_components(grid: np.ndarray) -> List[Dict]:
    """Ignore colors, treat all non-background as one foreground."""
    binary = (grid != 0).astype(int)
    labeled, n = ndi.label(binary)
    objects = []
    for i in range(1, n + 1):
        mask = labeled == i
        ys, xs = np.where(mask)
        r_min, c_min = int(ys.min()), int(xs.min())
        r_max, c_max = int(ys.max()), int(xs.max())
        bbox_h = r_max - r_min + 1
        bbox_w = c_max - c_min + 1
        local_mask = mask[r_min:r_max+1, c_min:c_max+1]
        colors = set(grid[mask].tolist()) - {0}
        objects.append({
            "mask": mask, "primary_color": int(grid[ys[0], xs[0]]),
            "area": int(mask.sum()),
            "bbox": (r_min, c_min, r_max, c_max),
            "bbox_h": bbox_h, "bbox_w": bbox_w,
            "bbox_ratio": bbox_h / max(bbox_w, 1),
            "center_r": float(ys.mean()),
            "center_c": float(xs.mean()),
            "local_mask": local_mask,
            "n_holes": 0,
            "n_colors": len(colors),
            "convexity": float(mask.sum()) / max(bbox_h * bbox_w, 1),
            "is_filled_rect": bool(mask.sum() == bbox_h * bbox_w),
            "is_square": bbox_h == bbox_w,
            "multi_colored": len(colors) > 1,
        })
    return objects


def extract_majority_bg_components(grid: np.ndarray) -> List[Dict]:
    """Auto-detect background as most frequent color."""
    flat = grid.flatten()
    bg = int(np.bincount(flat).argmax())
    labeled, n = ndi.label(grid != bg)
    objects = []
    for i in range(1, n + 1):
        mask = labeled == i
        ys, xs = np.where(mask)
        r_min, c_min = int(ys.min()), int(xs.min())
        r_max, c_max = int(ys.max()), int(xs.max())
        bbox_h = r_max - r_min + 1
        bbox_w = c_max - c_min + 1
        local_mask = mask[r_min:r_max+1, c_min:c_max+1]
        objects.append({
            "mask": mask, "primary_color": int(grid[ys[0], xs[0]]),
            "area": int(mask.sum()),
            "bbox": (r_min, c_min, r_max, c_max),
            "bbox_h": bbox_h, "bbox_w": bbox_w,
            "bbox_ratio": bbox_h / max(bbox_w, 1),
            "center_r": float(ys.mean()),
            "center_c": float(xs.mean()),
            "local_mask": local_mask,
            "n_holes": 0,
            "n_colors": 1,
            "convexity": float(mask.sum()) / max(bbox_h * bbox_w, 1),
            "is_filled_rect": bool(mask.sum() == bbox_h * bbox_w),
            "is_square": bbox_h == bbox_w,
        })
    return objects


SCHEMA_EXTRACTORS = {
    "connected_components": _extract_objects_with_properties,
    "per_color_components": extract_per_color_components,
    "monochrome_components": extract_monochrome_components,
    "majority_bg_components": extract_majority_bg_components,
}


def enrich_objects(objects: List[Dict], grid: np.ndarray) -> List[Dict]:
    """Add relational and derived properties to raw extracted objects."""
    for i, obj in enumerate(objects):
        obj.setdefault("n_holes", 0)
        obj.setdefault("n_colors", 1)
        obj.setdefault("convexity", 1.0)
        obj.setdefault("is_filled_rect", False)
        obj.setdefault("is_square", False)
        obj.setdefault("h_sym", False)
        obj.setdefault("v_sym", False)
        obj.setdefault("d_sym", False)
        obj.setdefault("any_sym", False)
        obj.setdefault("bbox_h", 1)
        obj.setdefault("bbox_w", 1)
        obj.setdefault("bbox_ratio", 1.0)

        h, w = grid.shape[:2]
        obj.setdefault("touches_boundary",
                        obj.get("bbox", (0,0,0,0))[0] == 0 or
                        obj.get("bbox", (0,0,h-1,w-1))[2] >= h - 1 or
                        obj.get("bbox", (0,0,0,0))[1] == 0 or
                        obj.get("bbox", (0,0,0,w-1))[3] >= w - 1)
        obj.setdefault("touches_top", obj.get("bbox", (1,0,0,0))[0] == 0)
        obj.setdefault("touches_bottom", obj.get("bbox", (0,0,0,0))[2] >= h - 1)
        obj.setdefault("touches_left", obj.get("bbox", (0,1,0,0))[1] == 0)
        obj.setdefault("touches_right", obj.get("bbox", (0,0,0,0))[3] >= w - 1)
        obj.setdefault("in_top_half", obj.get("center_r", 0) < h / 2)
        obj.setdefault("in_left_half", obj.get("center_c", 0) < w / 2)

    if len(objects) > 1:
        areas = [o["area"] for o in objects]
        max_area = max(areas)
        min_area = min(areas)
        for i, obj in enumerate(objects):
            obj["is_largest"] = obj["area"] == max_area
            obj["is_smallest"] = obj["area"] == min_area
            obj["size_rank"] = sorted(areas, reverse=True).index(obj["area"])
    else:
        for obj in objects:
            obj["is_largest"] = True
            obj["is_smallest"] = True
            obj["size_rank"] = 0

    try:
        objects = _safe_add_relational(objects, grid)
    except Exception:
        pass

    return objects


class AdapterSchemaProposer:
    """Propose alternative object schemas and try selectors on each."""

    def __init__(self):
        self.selector_inventor = SelectorInventor()

    def should_activate(
        self,
        property_trace: Dict,
        failure_trace: Dict,
        object_trace: Dict,
        all_proposals_failed: bool = False,
    ) -> bool:
        if not property_trace.get("has_discriminative_property"):
            return True
        if failure_trace.get("failure_type") in ("perception_failure", "no_discriminative_property"):
            return True
        if all_proposals_failed:
            return True
        if object_trace.get("pairs"):
            if any(p.get("n_input_objects", 0) < 2 for p in object_trace["pairs"]):
                return True
        return False

    def propose_schemas(
        self,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    ) -> List[ObjectSchemaProposal]:
        proposals = []
        for schema_name, extractor in SCHEMA_EXTRACTORS.items():
            if schema_name == "connected_components":
                continue  # skip default, already tried
            try:
                all_objects = []
                for inp, out in train_pairs:
                    if extractor == _extract_objects_with_properties:
                        objs = extractor(inp)
                    else:
                        objs = extractor(inp)
                    objs = enrich_objects(objs, inp)
                    all_objects.append(objs)

                if not all_objects or not all(len(o) >= 2 for o in all_objects):
                    continue

                all_props = [p for obj_list in all_objects for obj in obj_list for p in obj.keys()]
                unique_props = list(set(all_props))

                proposals.append(ObjectSchemaProposal(
                    schema_name=schema_name,
                    object_extractor_name=schema_name,
                    objects=all_objects,
                    relations=[],
                    properties=unique_props[:20],
                    evidence={"n_objects_per_pair": [len(o) for o in all_objects]},
                ))
            except Exception:
                continue
        return proposals

    def propose_executable_selectors(
        self,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    ) -> List[Dict[str, Any]]:
        """Try each schema, run selector invention, return executable results."""
        results = []
        schemas = self.propose_schemas(train_pairs)

        for schema in schemas:
            extractor = SCHEMA_EXTRACTORS.get(schema.object_extractor_name)
            if extractor is None:
                continue

            # Build per-pair targets using this schema's objects
            per_pair = []
            for (inp, out), objs in zip(train_pairs, schema.objects):
                if inp.shape != out.shape:
                    continue
                if len(objs) < 2:
                    continue

                diff = inp != out
                changed = [i for i, obj in enumerate(objs) if diff[obj["mask"]].any()]
                unchanged = [i for i in range(len(objs)) if i not in changed]

                if not changed or not unchanged:
                    # Try kept/removed classification
                    kr = None
                    try:
                        kr_result = _extract_objects_with_properties(inp)
                        from reasoning_project.reasoning_engine import _classify_kept_removed as _ckr
                        kr = _ckr(objs, inp, out)
                    except Exception:
                        pass
                    if kr is not None:
                        kept, removed = kr
                        per_pair.append({
                            "objects": objs,
                            "target_indices": removed,
                            "non_target_indices": kept,
                            "change_type": "kept_removed",
                        })
                    continue

                per_pair.append({
                    "objects": objs,
                    "target_indices": changed,
                    "non_target_indices": unchanged,
                    "change_type": "pixel_diff",
                })

            if not per_pair:
                continue

            # Search selectors on this schema's objects
            candidates = self.selector_inventor.search_single_properties(per_pair)
            if not candidates:
                candidates = self.selector_inventor.search_conjunctions(per_pair)
            if not candidates:
                candidates = self.selector_inventor.search_negations(per_pair)

            for cand in candidates[:3]:
                results.append({
                    "schema_name": schema.schema_name,
                    "selector_expression": cand.selector_expression,
                    "selector_type": cand.selector_type,
                    "extractor_name": schema.object_extractor_name,
                    "complexity": cand.complexity,
                    "train_fit_score": cand.train_fit_score,
                    "evidence": {
                        "schema": schema.schema_name,
                        **cand.evidence,
                    },
                })

        return results
