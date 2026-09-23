"""Property invention from failure-cluster analysis.

When the reasoning engine fails to discriminate kept from removed objects,
it may be because the property language lacks a predicate that captures the
relevant distinction.  This module mines clusters of near-solved failures,
proposes new predicates across several *property families*, validates them
with staged leave-one-out checks, and registers survivors into the
reasoner's property language.

Property families
-----------------
- **object_identity** — shape/size comparisons to a reference object
- **spatial_relation** — positional relationships (aligned, between, nearest)
- **topology**        — holes, endpoints, junctions, rotational uniqueness
- **pattern_membership** — repeating/breaking patterns, minority groups
- **container**       — frame enclosure / containment predicates
- **color_stat**      — color-frequency statistics relative to scene
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
from scipy import ndimage

from reasoning_project.near_solved_memory import NearSolvedMemory, NearSolvedTaskState
from reasoning_project.reasoning_engine import (
    BOOLEAN_PROPERTIES,
    DERIVED_PREDICATES,
    GridDomainAdapter,
    _all_property_names,
    _classify_kept_removed,
    _classify_two_groups,
    _extract_objects_with_properties,
    _get_property_value,
)


# ═══════════════════════════════════════════════════════════════════════════
# VALIDATION LEVELS
# ═══════════════════════════════════════════════════════════════════════════

class ValidationLevel:
    """Staged validation levels for invented properties.

    Level 1 (candidate_validated): discriminates target/distractor in one task
    Level 2 (loo_validated): passes LOO cross-validation on one task
    Level 3 (cluster_validated): works across multiple tasks in failure cluster
    Level 4 (promotion_validated): actually promotes a near-solved task to solved
    Level 5 (transfer_validated): transfers to held-out tasks outside the cluster
    """
    PROPOSED = "proposed"
    CANDIDATE_VALIDATED = "candidate_validated"  # Level 1
    LOO_VALIDATED = "loo_validated"              # Level 2
    CLUSTER_VALIDATED = "cluster_validated"      # Level 3
    PROMOTION_VALIDATED = "promotion_validated"  # Level 4
    TRANSFER_VALIDATED = "transfer_validated"    # Level 5
    REGISTERED = "registered"
    REJECTED = "rejected"

    ORDERED = [
        PROPOSED,
        CANDIDATE_VALIDATED,
        LOO_VALIDATED,
        CLUSTER_VALIDATED,
        PROMOTION_VALIDATED,
        TRANSFER_VALIDATED,
        REGISTERED,
    ]

    @staticmethod
    def level_number(status: str) -> int:
        """Return numeric level (0=proposed, 1=candidate, ..., 5=transfer, 6=registered)."""
        try:
            return ValidationLevel.ORDERED.index(status)
        except ValueError:
            return -1

    @staticmethod
    def at_least(status: str, min_level: str) -> bool:
        """True if status is at or above min_level."""
        return ValidationLevel.level_number(status) >= ValidationLevel.level_number(min_level)


# ═══════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class InventedProperty:
    """A dynamically invented boolean predicate."""

    name: str
    expression: str  # human-readable description
    property_family: str  # object_identity, spatial_relation, topology,
    #                       pattern_membership, container, color_stat
    source_failure_cluster: str
    source_tasks: List[str]
    validation_tasks: List[str]
    compute_fn: Optional[Callable]  # (obj: Dict) -> bool
    train_discrimination_score: float  # fraction of training pairs where it discriminates
    loo_passed: bool
    false_positive_rate: float
    promoted_tasks: List[str]
    status: str  # ValidationLevel constant
    cluster_discrimination_score: float = 0.0  # avg score across cluster tasks
    n_cluster_tasks_passed: int = 0
    transfer_tasks_passed: List[str] = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.transfer_tasks_passed is None:
            self.transfer_tasks_passed = []

    @property
    def validation_level(self) -> int:
        return ValidationLevel.level_number(self.status)


# ═══════════════════════════════════════════════════════════════════════════
# HELPER UTILITIES
# ═══════════════════════════════════════════════════════════════════════════

def _objects_from_task(task: Dict[str, Any]) -> List[List[Dict[str, Any]]]:
    """Extract objects from every training-pair input in *task*."""
    pairs = task.get("train", [])
    result: List[List[Dict]] = []
    for pair in pairs:
        inp = pair.get("input")
        if inp is None:
            continue
        grid = np.array(inp, dtype=int) if not isinstance(inp, np.ndarray) else inp
        result.append(_extract_objects_with_properties(grid))
    return result


def _kept_removed_from_task(
    task: Dict[str, Any],
) -> List[Optional[Tuple[List[int], List[int]]]]:
    """For each training pair return (kept, removed) indices or None."""
    pairs = task.get("train", [])
    results: List[Optional[Tuple[List[int], List[int]]]] = []
    for pair in pairs:
        inp = np.array(pair["input"], dtype=int) if not isinstance(pair["input"], np.ndarray) else pair["input"]
        out = np.array(pair["output"], dtype=int) if not isinstance(pair["output"], np.ndarray) else pair["output"]
        objs = _extract_objects_with_properties(inp)
        results.append(_classify_two_groups(objs, inp, out))
    return results


def _discrimination_score(
    compute_fn: Callable,
    task: Dict[str, Any],
) -> float:
    """Fraction of training pairs where *compute_fn* perfectly separates
    kept from removed objects (all kept True, all removed False, or vice versa)."""
    pairs = task.get("train", [])
    if not pairs:
        return 0.0
    n_good = 0
    for pair in pairs:
        inp = np.array(pair["input"], dtype=int) if not isinstance(pair["input"], np.ndarray) else pair["input"]
        out = np.array(pair["output"], dtype=int) if not isinstance(pair["output"], np.ndarray) else pair["output"]
        objs = _extract_objects_with_properties(inp)
        kr = _classify_two_groups(objs, inp, out)
        if kr is None:
            continue
        kept_idx, removed_idx = kr
        kept_vals = [bool(compute_fn(objs[i])) for i in kept_idx]
        removed_vals = [bool(compute_fn(objs[i])) for i in removed_idx]
        # keep-when-True or keep-when-False
        if (all(kept_vals) and not any(removed_vals)) or \
           (not any(kept_vals) and all(removed_vals)):
            n_good += 1
    return n_good / len(pairs)


def _loo_validate(
    compute_fn: Callable,
    tasks: List[Dict[str, Any]],
) -> bool:
    """Leave-one-out: for each task with >=2 training pairs, hold out one pair,
    learn the polarity from the rest, and check the held-out pair."""
    for task in tasks:
        pairs = task.get("train", [])
        if len(pairs) < 2:
            continue
        for hold_idx in range(len(pairs)):
            # Learn polarity from remaining pairs
            polarity_votes: Dict[str, int] = {"true_keeps": 0, "false_keeps": 0}
            for i, pair in enumerate(pairs):
                if i == hold_idx:
                    continue
                inp = np.array(pair["input"], dtype=int) if not isinstance(pair["input"], np.ndarray) else pair["input"]
                out = np.array(pair["output"], dtype=int) if not isinstance(pair["output"], np.ndarray) else pair["output"]
                objs = _extract_objects_with_properties(inp)
                kr = _classify_two_groups(objs, inp, out)
                if kr is None:
                    continue
                kept_idx_list, removed_idx_list = kr
                kv = [bool(compute_fn(objs[k])) for k in kept_idx_list]
                rv = [bool(compute_fn(objs[k])) for k in removed_idx_list]
                if all(kv) and not any(rv):
                    polarity_votes["true_keeps"] += 1
                elif not any(kv) and all(rv):
                    polarity_votes["false_keeps"] += 1
            # Determine polarity
            if polarity_votes["true_keeps"] == 0 and polarity_votes["false_keeps"] == 0:
                continue  # no signal — skip
            keep_when_true = polarity_votes["true_keeps"] >= polarity_votes["false_keeps"]

            # Test on held-out pair
            hp = pairs[hold_idx]
            inp_h = np.array(hp["input"], dtype=int) if not isinstance(hp["input"], np.ndarray) else hp["input"]
            out_h = np.array(hp["output"], dtype=int) if not isinstance(hp["output"], np.ndarray) else hp["output"]
            objs_h = _extract_objects_with_properties(inp_h)
            kr_h = _classify_two_groups(objs_h, inp_h, out_h)
            if kr_h is None:
                continue
            kept_h, removed_h = kr_h
            kv_h = [bool(compute_fn(objs_h[k])) for k in kept_h]
            rv_h = [bool(compute_fn(objs_h[k])) for k in removed_h]
            if keep_when_true:
                if not (all(kv_h) and not any(rv_h)):
                    return False
            else:
                if not (not any(kv_h) and all(rv_h)):
                    return False
    return True


def _false_positive_rate(
    compute_fn: Callable,
    holdout_tasks: List[Dict[str, Any]],
) -> float:
    """Fraction of holdout training pairs where the property mislabels."""
    total = 0
    fp = 0
    for task in holdout_tasks:
        pairs = task.get("train", [])
        for pair in pairs:
            inp = np.array(pair["input"], dtype=int) if not isinstance(pair["input"], np.ndarray) else pair["input"]
            out = np.array(pair["output"], dtype=int) if not isinstance(pair["output"], np.ndarray) else pair["output"]
            objs = _extract_objects_with_properties(inp)
            kr = _classify_two_groups(objs, inp, out)
            if kr is None:
                continue
            total += 1
            kept_idx, removed_idx = kr
            kv = [bool(compute_fn(objs[k])) for k in kept_idx]
            rv = [bool(compute_fn(objs[k])) for k in removed_idx]
            perfect = (all(kv) and not any(rv)) or (not any(kv) and all(rv))
            if not perfect:
                fp += 1
    return fp / max(total, 1)


# ═══════════════════════════════════════════════════════════════════════════
# COMPUTE-FUNCTION BUILDERS (one per candidate predicate)
# ═══════════════════════════════════════════════════════════════════════════

def _make_same_shape_as_reference(ref_selector: str) -> Callable:
    """Return compute_fn: True if obj shares local_mask with the ref object.

    *ref_selector* is stored in a closure but the actual reference is
    determined at runtime from the object's ``_scene_objects`` list
    (injected during validation).
    """
    def compute(obj: Dict) -> bool:
        scene_objs = obj.get("_scene_objects", [])
        if not scene_objs:
            return False
        if ref_selector == "largest":
            ref = max(scene_objs, key=lambda o: o["area"])
        elif ref_selector == "smallest":
            ref = min(scene_objs, key=lambda o: o["area"])
        elif ref_selector == "unique":
            # The object whose shape appears exactly once
            from collections import Counter
            shape_keys = []
            for o in scene_objs:
                shape_keys.append(o["local_mask"].tobytes())
            counts = Counter(shape_keys)
            unique_key = [k for k, v in counts.items() if v == 1]
            if not unique_key:
                return False
            ref_idx = shape_keys.index(unique_key[0])
            ref = scene_objs[ref_idx]
        else:
            return False
        if ref is obj:
            return False
        return (obj["local_mask"].shape == ref["local_mask"].shape and
                bool(np.array_equal(obj["local_mask"], ref["local_mask"])))
    return compute


def _make_same_color_as_marker() -> Callable:
    """True if obj's primary_color matches a single-cell marker in the scene."""
    def compute(obj: Dict) -> bool:
        scene_objs = obj.get("_scene_objects", [])
        markers = [o for o in scene_objs if o["area"] == 1]
        if not markers:
            return False
        marker_colors = {m["primary_color"] for m in markers}
        return obj["primary_color"] in marker_colors
    return compute


def _make_inside_largest_frame() -> Callable:
    """True if obj bbox is inside the bbox of the largest frame-like object."""
    def compute(obj: Dict) -> bool:
        scene_objs = obj.get("_scene_objects", [])
        frames = [o for o in scene_objs if o["n_holes"] > 0 and o["convexity"] < 0.7]
        if not frames:
            return False
        largest_frame = max(frames, key=lambda o: o["area"])
        if largest_frame is obj:
            return False
        fr1, fc1, fr2, fc2 = largest_frame["bbox"]
        or1, oc1, or2, oc2 = obj["bbox"]
        return fr1 <= or1 and fc1 <= oc1 and fr2 >= or2 and fc2 >= oc2
    return compute


def _make_nearest_to_unique_color() -> Callable:
    """True if obj is the nearest object to the unique-colored one."""
    def compute(obj: Dict) -> bool:
        scene_objs = obj.get("_scene_objects", [])
        if len(scene_objs) < 2:
            return False
        from collections import Counter
        color_counts = Counter(o["primary_color"] for o in scene_objs)
        unique_colors = [c for c, cnt in color_counts.items() if cnt == 1]
        if not unique_colors:
            return False
        unique_objs = [o for o in scene_objs if o["primary_color"] in unique_colors]
        if obj in unique_objs:
            return False
        # Distance to closest unique-color object
        min_dist = float("inf")
        for uo in unique_objs:
            d = abs(obj["center_r"] - uo["center_r"]) + abs(obj["center_c"] - uo["center_c"])
            min_dist = min(min_dist, d)
        # Am I the closest non-unique to any unique object?
        for uo in unique_objs:
            best_d = float("inf")
            best_obj = None
            for o in scene_objs:
                if o is uo or o["primary_color"] in unique_colors:
                    continue
                d = abs(o["center_r"] - uo["center_r"]) + abs(o["center_c"] - uo["center_c"])
                if d < best_d:
                    best_d = d
                    best_obj = o
            if best_obj is obj:
                return True
        return False
    return compute


def _make_touches_marker_object() -> Callable:
    """True if obj is adjacent (4-connected dilation) to a single-cell marker."""
    def compute(obj: Dict) -> bool:
        scene_objs = obj.get("_scene_objects", [])
        markers = [o for o in scene_objs if o["area"] == 1 and o is not obj]
        if not markers:
            return False
        dilated = ndimage.binary_dilation(obj["mask"])
        for m in markers:
            if np.any(dilated & m["mask"]):
                return True
        return False
    return compute


def _make_between_two_objects() -> Callable:
    """True if obj center_r or center_c is between two reference objects."""
    def compute(obj: Dict) -> bool:
        scene_objs = obj.get("_scene_objects", [])
        if len(scene_objs) < 3:
            return False
        others = [o for o in scene_objs if o is not obj]
        # Check if center_r is between any two others
        for i in range(len(others)):
            for j in range(i + 1, len(others)):
                r_lo = min(others[i]["center_r"], others[j]["center_r"])
                r_hi = max(others[i]["center_r"], others[j]["center_r"])
                c_lo = min(others[i]["center_c"], others[j]["center_c"])
                c_hi = max(others[i]["center_c"], others[j]["center_c"])
                if r_lo < obj["center_r"] < r_hi and c_lo < obj["center_c"] < c_hi:
                    return True
        return False
    return compute


def _make_aligned_with_marker() -> Callable:
    """True if obj shares the same row or column (within 1.0) as a marker."""
    def compute(obj: Dict) -> bool:
        scene_objs = obj.get("_scene_objects", [])
        markers = [o for o in scene_objs if o["area"] == 1 and o is not obj]
        for m in markers:
            if abs(obj["center_r"] - m["center_r"]) < 1.0:
                return True
            if abs(obj["center_c"] - m["center_c"]) < 1.0:
                return True
        return False
    return compute


# --- Topology builders ---

def _make_has_exactly_n_holes(n: int) -> Callable:
    def compute(obj: Dict) -> bool:
        return obj.get("n_holes", 0) == n
    return compute


def _make_is_endpoint() -> Callable:
    """True if the object touches at most one other object."""
    def compute(obj: Dict) -> bool:
        return obj.get("n_touching", 0) <= 1
    return compute


def _make_is_junction() -> Callable:
    """True if the object touches three or more other objects."""
    def compute(obj: Dict) -> bool:
        return obj.get("n_touching", 0) >= 3
    return compute


def _make_unique_under_rotation() -> Callable:
    """True if no other object in the scene has the same shape under any
    90-degree rotation."""
    def compute(obj: Dict) -> bool:
        scene_objs = obj.get("_scene_objects", [])
        lm = obj["local_mask"]
        rotations = [lm, np.rot90(lm, 1), np.rot90(lm, 2), np.rot90(lm, 3)]
        for other in scene_objs:
            if other is obj:
                continue
            olm = other["local_mask"]
            for rot in rotations:
                if rot.shape == olm.shape and np.array_equal(rot, olm):
                    return False
        return True
    return compute


# --- Container builders ---

def _make_inside_colored_frame() -> Callable:
    """True if obj is inside the bbox of any frame-like object."""
    def compute(obj: Dict) -> bool:
        scene_objs = obj.get("_scene_objects", [])
        frames = [o for o in scene_objs
                  if o["n_holes"] > 0 and o["convexity"] < 0.7 and o is not obj]
        for frame in frames:
            fr1, fc1, fr2, fc2 = frame["bbox"]
            or1, oc1, or2, oc2 = obj["bbox"]
            if fr1 <= or1 and fc1 <= oc1 and fr2 >= or2 and fc2 >= oc2:
                return True
        return False
    return compute


def _make_outside_colored_frame() -> Callable:
    """True if obj is NOT inside any frame-like object."""
    inside_fn = _make_inside_colored_frame()
    def compute(obj: Dict) -> bool:
        return not inside_fn(obj)
    return compute


def _make_contains_color(target_color: int) -> Callable:
    """True if obj is a frame that encloses objects of *target_color*."""
    def compute(obj: Dict) -> bool:
        if obj["n_holes"] == 0 or obj["convexity"] >= 0.7:
            return False
        scene_objs = obj.get("_scene_objects", [])
        fr1, fc1, fr2, fc2 = obj["bbox"]
        for other in scene_objs:
            if other is obj:
                continue
            if other["primary_color"] != target_color:
                continue
            or1, oc1, or2, oc2 = other["bbox"]
            if fr1 <= or1 and fc1 <= oc1 and fr2 >= or2 and fc2 >= oc2:
                return True
        return False
    return compute


def _make_frame_contains_target() -> Callable:
    """True if obj is a frame that contains at least one other object."""
    def compute(obj: Dict) -> bool:
        if obj["n_holes"] == 0 or obj["convexity"] >= 0.7:
            return False
        scene_objs = obj.get("_scene_objects", [])
        fr1, fc1, fr2, fc2 = obj["bbox"]
        for other in scene_objs:
            if other is obj:
                continue
            or1, oc1, or2, oc2 = other["bbox"]
            if fr1 <= or1 and fc1 <= oc1 and fr2 >= or2 and fc2 >= oc2:
                return True
        return False
    return compute


# --- Pattern membership builders ---

def _make_part_of_repeating_pattern() -> Callable:
    """True if obj's shape appears 2+ times in the scene."""
    def compute(obj: Dict) -> bool:
        return obj.get("shape_group_size", 1) > 1
    return compute


def _make_breaks_repeating_pattern() -> Callable:
    """True if obj's shape appears exactly once (odd one out)."""
    def compute(obj: Dict) -> bool:
        return obj.get("shape_group_size", 1) == 1
    return compute


def _make_belongs_to_minority_shape_group() -> Callable:
    """True if obj belongs to the smallest shape group in the scene."""
    def compute(obj: Dict) -> bool:
        scene_objs = obj.get("_scene_objects", [])
        if not scene_objs:
            return False
        group_sizes = [o.get("shape_group_size", 1) for o in scene_objs]
        if not group_sizes:
            return False
        min_size = min(group_sizes)
        return obj.get("shape_group_size", 1) == min_size
    return compute


# ═══════════════════════════════════════════════════════════════════════════
# SCENE-INJECTION HELPER
# ═══════════════════════════════════════════════════════════════════════════

def _inject_scene_context(objects: List[Dict]) -> None:
    """Inject ``_scene_objects`` back-pointer into every object dict so that
    relational compute_fn's can access peer objects."""
    for obj in objects:
        obj["_scene_objects"] = objects


def _strip_scene_context(objects: List[Dict]) -> None:
    """Remove ``_scene_objects`` to avoid circular references."""
    for obj in objects:
        obj.pop("_scene_objects", None)


# ═══════════════════════════════════════════════════════════════════════════
# PROPERTY INVENTOR
# ═══════════════════════════════════════════════════════════════════════════

class PropertyInventor:
    """Mine, propose, validate, and register new boolean predicates."""

    def __init__(self) -> None:
        self.invented: List[InventedProperty] = []
        self.registered: List[InventedProperty] = []

    # ------------------------------------------------------------------
    # 1. MINING — cluster failures and identify property gaps
    # ------------------------------------------------------------------

    def mine_from_failures(
        self,
        near_solved_states: Dict[str, NearSolvedTaskState],
        tasks: List[Dict],
    ) -> List[Dict]:
        """Cluster failure states and identify what properties are missing.

        Groups by ``failure_type + missing_capability_guess`` and for each
        cluster collects the task data so proposal methods can analyse the
        actual grids.

        Returns a list of cluster dicts:
            {cluster_key, failure_type, missing_capability,
             task_ids, tasks, states}
        """
        clusters: Dict[str, List[NearSolvedTaskState]] = {}
        for state in near_solved_states.values():
            if state.status == "solved":
                continue
            key = f"{state.failure_type}:{state.missing_capability_guess}"
            clusters.setdefault(key, []).append(state)

        # Build task lookup
        task_map: Dict[str, Dict] = {}
        for t in tasks:
            tid = t.get("task_id", "")
            if tid:
                task_map[tid] = t

        result: List[Dict] = []
        for key, states in clusters.items():
            parts = key.split(":", 1)
            failure_type = parts[0]
            missing_cap = parts[1] if len(parts) > 1 else ""
            task_ids = [s.task_id for s in states]
            cluster_tasks = [task_map[tid] for tid in task_ids if tid in task_map]
            if not cluster_tasks:
                continue
            result.append({
                "cluster_key": key,
                "failure_type": failure_type,
                "missing_capability": missing_cap,
                "task_ids": task_ids,
                "tasks": cluster_tasks,
                "states": states,
            })

        return result

    # ------------------------------------------------------------------
    # 2. PROPOSAL — generate candidate predicates
    # ------------------------------------------------------------------

    def propose_relational_properties(
        self,
        cluster_tasks: List[Dict],
    ) -> List[InventedProperty]:
        """Propose new relational predicates based on object structure analysis."""
        candidates: List[Tuple[str, str, str, Callable]] = [
            ("same_shape_as_largest",
             "Shape matches the largest object in the scene",
             "object_identity",
             _make_same_shape_as_reference("largest")),
            ("same_shape_as_smallest",
             "Shape matches the smallest object in the scene",
             "object_identity",
             _make_same_shape_as_reference("smallest")),
            ("same_shape_as_unique",
             "Shape matches the unique-shaped object in the scene",
             "object_identity",
             _make_same_shape_as_reference("unique")),
            ("same_color_as_marker",
             "Color matches a single-cell marker object",
             "spatial_relation",
             _make_same_color_as_marker()),
            ("inside_largest_frame",
             "Contained within the largest hollow (frame) object",
             "spatial_relation",
             _make_inside_largest_frame()),
            ("nearest_to_unique_color",
             "Closest to the unique-colored object",
             "spatial_relation",
             _make_nearest_to_unique_color()),
            ("touches_marker_object",
             "Adjacent to a single-cell marker",
             "spatial_relation",
             _make_touches_marker_object()),
            ("between_two_objects",
             "Center row/col between two reference objects",
             "spatial_relation",
             _make_between_two_objects()),
            ("aligned_with_marker",
             "Same row or column as a single-cell marker",
             "spatial_relation",
             _make_aligned_with_marker()),
        ]

        task_ids = [t.get("task_id", f"task_{i}") for i, t in enumerate(cluster_tasks)]
        proposed: List[InventedProperty] = []

        for name, expression, family, compute_fn in candidates:
            score = self._score_candidate(compute_fn, cluster_tasks)
            if score > 0.0:
                prop = InventedProperty(
                    name=name,
                    expression=expression,
                    property_family=family,
                    source_failure_cluster="relational",
                    source_tasks=list(task_ids),
                    validation_tasks=[],
                    compute_fn=compute_fn,
                    train_discrimination_score=score,
                    loo_passed=False,
                    false_positive_rate=1.0,
                    promoted_tasks=[],
                    status="proposed",
                )
                proposed.append(prop)
                self.invented.append(prop)

        return proposed

    def propose_topological_properties(
        self,
        cluster_tasks: List[Dict],
    ) -> List[InventedProperty]:
        """Propose topology predicates from failure patterns."""
        candidates: List[Tuple[str, str, str, Callable]] = [
            ("has_exactly_1_hole",
             "Object has exactly 1 hole",
             "topology",
             _make_has_exactly_n_holes(1)),
            ("has_exactly_2_holes",
             "Object has exactly 2 holes",
             "topology",
             _make_has_exactly_n_holes(2)),
            ("is_endpoint",
             "Touches at most one other object (endpoint)",
             "topology",
             _make_is_endpoint()),
            ("is_junction",
             "Touches three or more other objects (junction)",
             "topology",
             _make_is_junction()),
            ("unique_under_rotation",
             "No rotational duplicate among scene objects",
             "topology",
             _make_unique_under_rotation()),
        ]

        task_ids = [t.get("task_id", f"task_{i}") for i, t in enumerate(cluster_tasks)]
        proposed: List[InventedProperty] = []

        for name, expression, family, compute_fn in candidates:
            score = self._score_candidate(compute_fn, cluster_tasks)
            if score > 0.0:
                prop = InventedProperty(
                    name=name,
                    expression=expression,
                    property_family=family,
                    source_failure_cluster="topology",
                    source_tasks=list(task_ids),
                    validation_tasks=[],
                    compute_fn=compute_fn,
                    train_discrimination_score=score,
                    loo_passed=False,
                    false_positive_rate=1.0,
                    promoted_tasks=[],
                    status="proposed",
                )
                proposed.append(prop)
                self.invented.append(prop)

        return proposed

    def propose_container_properties(
        self,
        cluster_tasks: List[Dict],
    ) -> List[InventedProperty]:
        """Propose container/containment predicates."""
        candidates: List[Tuple[str, str, str, Callable]] = [
            ("inside_colored_frame",
             "Object is inside the bbox of a frame-like object",
             "container",
             _make_inside_colored_frame()),
            ("outside_colored_frame",
             "Object is NOT inside any frame-like object",
             "container",
             _make_outside_colored_frame()),
            ("frame_contains_target",
             "Frame object encloses at least one other object",
             "container",
             _make_frame_contains_target()),
        ]

        # Add contains_color for colours 1..9
        for c in range(1, 10):
            candidates.append((
                f"contains_color_{c}",
                f"Frame encloses objects of color {c}",
                "container",
                _make_contains_color(c),
            ))

        task_ids = [t.get("task_id", f"task_{i}") for i, t in enumerate(cluster_tasks)]
        proposed: List[InventedProperty] = []

        for name, expression, family, compute_fn in candidates:
            score = self._score_candidate(compute_fn, cluster_tasks)
            if score > 0.0:
                prop = InventedProperty(
                    name=name,
                    expression=expression,
                    property_family=family,
                    source_failure_cluster="container",
                    source_tasks=list(task_ids),
                    validation_tasks=[],
                    compute_fn=compute_fn,
                    train_discrimination_score=score,
                    loo_passed=False,
                    false_positive_rate=1.0,
                    promoted_tasks=[],
                    status="proposed",
                )
                proposed.append(prop)
                self.invented.append(prop)

        return proposed

    def propose_pattern_membership_properties(
        self,
        cluster_tasks: List[Dict],
    ) -> List[InventedProperty]:
        """Propose pattern-based predicates."""
        candidates: List[Tuple[str, str, str, Callable]] = [
            ("part_of_repeating_pattern",
             "Shape appears 2+ times in the scene",
             "pattern_membership",
             _make_part_of_repeating_pattern()),
            ("breaks_repeating_pattern",
             "Shape appears exactly once (odd one out)",
             "pattern_membership",
             _make_breaks_repeating_pattern()),
            ("belongs_to_minority_shape_group",
             "Belongs to the smallest shape group in the scene",
             "pattern_membership",
             _make_belongs_to_minority_shape_group()),
        ]

        task_ids = [t.get("task_id", f"task_{i}") for i, t in enumerate(cluster_tasks)]
        proposed: List[InventedProperty] = []

        for name, expression, family, compute_fn in candidates:
            score = self._score_candidate(compute_fn, cluster_tasks)
            if score > 0.0:
                prop = InventedProperty(
                    name=name,
                    expression=expression,
                    property_family=family,
                    source_failure_cluster="pattern",
                    source_tasks=list(task_ids),
                    validation_tasks=[],
                    compute_fn=compute_fn,
                    train_discrimination_score=score,
                    loo_passed=False,
                    false_positive_rate=1.0,
                    promoted_tasks=[],
                    status="proposed",
                )
                proposed.append(prop)
                self.invented.append(prop)

        return proposed

    # ------------------------------------------------------------------
    # 3. VALIDATION — staged checks (incremental)
    # ------------------------------------------------------------------

    def validate_to_level(
        self,
        prop: InventedProperty,
        target_level: str,
        tasks: List[Dict],
        cluster_tasks: Optional[List[Dict]] = None,
        holdout_tasks: Optional[List[Dict]] = None,
    ) -> InventedProperty:
        """Advance a property through validation levels up to *target_level*.

        Each level is checked sequentially. If a level fails, the property
        stays at its current level (not rejected unless level 1 fails).
        This makes invention staged, not all-or-nothing.

        Levels:
          1 (candidate_validated): discriminates in at least one source task
          2 (loo_validated): passes LOO on source tasks
          3 (cluster_validated): discriminates across failure cluster tasks
          4 (promotion_validated): set externally when it promotes a task
          5 (transfer_validated): works on held-out tasks outside cluster
        """
        if prop.compute_fn is None:
            prop.status = ValidationLevel.REJECTED
            return prop

        target_num = ValidationLevel.level_number(target_level)

        # --- Level 1: candidate_validated ---
        if not ValidationLevel.at_least(prop.status, ValidationLevel.CANDIDATE_VALIDATED):
            source_tasks = [t for t in tasks if t.get("task_id") in prop.source_tasks]
            if not source_tasks:
                source_tasks = tasks[:5]

            best_score = 0.0
            for task in source_tasks:
                s = self._score_candidate_single(prop.compute_fn, task)
                best_score = max(best_score, s)
            prop.train_discrimination_score = best_score

            if best_score == 0.0:
                prop.status = ValidationLevel.REJECTED
                return prop

            prop.validation_tasks = [t.get("task_id", "") for t in source_tasks
                                     if t.get("task_id")]
            prop.status = ValidationLevel.CANDIDATE_VALIDATED

        if target_num <= 1:
            return prop

        # --- Level 2: loo_validated ---
        if not ValidationLevel.at_least(prop.status, ValidationLevel.LOO_VALIDATED):
            source_tasks = [t for t in tasks if t.get("task_id") in prop.source_tasks]
            if not source_tasks:
                source_tasks = tasks[:5]

            prop.loo_passed = _loo_validate(prop.compute_fn, source_tasks)
            if not prop.loo_passed:
                return prop  # stays at candidate_validated, not rejected

            prop.status = ValidationLevel.LOO_VALIDATED

        if target_num <= 2:
            return prop

        # --- Level 3: cluster_validated ---
        if not ValidationLevel.at_least(prop.status, ValidationLevel.CLUSTER_VALIDATED):
            eval_tasks = cluster_tasks if cluster_tasks else tasks
            total_score = 0.0
            n_passed = 0
            for task in eval_tasks:
                s = self._score_candidate_single(prop.compute_fn, task)
                total_score += s
                if s >= 1.0:
                    n_passed += 1
            prop.cluster_discrimination_score = total_score / max(len(eval_tasks), 1)
            prop.n_cluster_tasks_passed = n_passed

            if n_passed < 2 and len(eval_tasks) >= 2:
                return prop  # stays at loo_validated

            prop.status = ValidationLevel.CLUSTER_VALIDATED

        if target_num <= 3:
            return prop

        # --- Level 4: promotion_validated ---
        # Set externally via mark_promotion_validated() when it promotes a task
        if target_num <= 4:
            return prop

        # --- Level 5: transfer_validated ---
        if not ValidationLevel.at_least(prop.status, ValidationLevel.TRANSFER_VALIDATED):
            eval_holdout = holdout_tasks if holdout_tasks else [
                t for t in tasks if t.get("task_id") not in prop.source_tasks
            ]
            if not eval_holdout:
                return prop  # can't test transfer without holdout

            prop.false_positive_rate = _false_positive_rate(prop.compute_fn, eval_holdout)
            transfer_passed = []
            for task in eval_holdout:
                s = self._score_candidate_single(prop.compute_fn, task)
                if s >= 1.0:
                    tid = task.get("task_id", "")
                    if tid:
                        transfer_passed.append(tid)
            prop.transfer_tasks_passed = transfer_passed

            if prop.false_positive_rate > 0.5 or not transfer_passed:
                return prop  # stays at current level

            prop.status = ValidationLevel.TRANSFER_VALIDATED

        return prop

    def mark_promotion_validated(self, prop: InventedProperty, task_id: str) -> None:
        """Mark a property as promotion-validated when it promotes a near-solved task."""
        if ValidationLevel.at_least(prop.status, ValidationLevel.CLUSTER_VALIDATED):
            prop.status = ValidationLevel.PROMOTION_VALIDATED
            if task_id not in prop.promoted_tasks:
                prop.promoted_tasks.append(task_id)

    def validate_property(
        self,
        prop: InventedProperty,
        tasks: List[Dict],
    ) -> InventedProperty:
        """Legacy entry point — validates to cluster level (Level 3).

        For finer control, use validate_to_level() directly.
        """
        return self.validate_to_level(
            prop, ValidationLevel.CLUSTER_VALIDATED, tasks,
        )

    # ------------------------------------------------------------------
    # 4. REGISTRATION
    # ------------------------------------------------------------------

    def register_property(
        self,
        prop: InventedProperty,
        min_level: str = ValidationLevel.CLUSTER_VALIDATED,
    ) -> bool:
        """Register a validated property into the reasoning engine's property language.

        Appends to DERIVED_PREDICATES so that all downstream code
        (_get_property_value, _all_property_names, etc.) can see it.

        Properties must be at least *min_level* to register (default: cluster_validated).
        Returns True if registered, False if rejected or already present.
        """
        if not ValidationLevel.at_least(prop.status, min_level):
            return False

        existing_names = {n for n, _ in DERIVED_PREDICATES}
        existing_names.update(BOOLEAN_PROPERTIES)
        if prop.name in existing_names:
            return False

        if prop.compute_fn is None:
            return False

        DERIVED_PREDICATES.append((prop.name, prop.compute_fn))
        prop.status = ValidationLevel.REGISTERED
        self.registered.append(prop)
        return True

    # ------------------------------------------------------------------
    # 5. FULL PIPELINE
    # ------------------------------------------------------------------

    def run_full_pipeline(
        self,
        near_solved_mem: NearSolvedMemory,
        tasks: List[Dict],
        target_level: str = ValidationLevel.CLUSTER_VALIDATED,
        min_register_level: str = ValidationLevel.CLUSTER_VALIDATED,
    ) -> Dict:
        """Full pipeline: mine -> propose -> validate staged -> register.

        Returns summary dict with counts, level distribution, and lists of
        registered property names.
        """
        clusters = self.mine_from_failures(near_solved_mem.states, tasks)

        all_proposed: List[InventedProperty] = []
        for cluster in clusters:
            cluster_tasks = cluster["tasks"]
            all_proposed.extend(self.propose_relational_properties(cluster_tasks))
            all_proposed.extend(self.propose_topological_properties(cluster_tasks))
            all_proposed.extend(self.propose_container_properties(cluster_tasks))
            all_proposed.extend(self.propose_pattern_membership_properties(cluster_tasks))

        level_counts: Dict[str, int] = {}
        for prop in all_proposed:
            cluster_tasks = None
            for cluster in clusters:
                if any(tid in prop.source_tasks for tid in cluster["task_ids"]):
                    cluster_tasks = cluster["tasks"]
                    break
            holdout = [t for t in tasks if t.get("task_id") not in prop.source_tasks]
            self.validate_to_level(
                prop, target_level, tasks,
                cluster_tasks=cluster_tasks,
                holdout_tasks=holdout if holdout else None,
            )
            level_counts[prop.status] = level_counts.get(prop.status, 0) + 1

        registered_names: List[str] = []
        for prop in all_proposed:
            if ValidationLevel.at_least(prop.status, min_register_level):
                if self.register_property(prop, min_level=min_register_level):
                    registered_names.append(prop.name)

        return {
            "n_clusters": len(clusters),
            "n_proposed": len(all_proposed),
            "level_distribution": level_counts,
            "n_registered": len(registered_names),
            "registered_names": registered_names,
            "invented": [p.name for p in self.invented],
            "registered": [p.name for p in self.registered],
        }

    # ------------------------------------------------------------------
    # INTERNAL SCORING HELPERS
    # ------------------------------------------------------------------

    def _score_candidate(
        self,
        compute_fn: Callable,
        cluster_tasks: List[Dict],
    ) -> float:
        """Average discrimination score across tasks, with scene-context injection."""
        if not cluster_tasks:
            return 0.0
        total = 0.0
        n = 0
        for task in cluster_tasks:
            s = self._score_candidate_single(compute_fn, task)
            total += s
            n += 1
        return total / max(n, 1)

    def _score_candidate_single(
        self,
        compute_fn: Callable,
        task: Dict,
    ) -> float:
        """Discrimination score on a single task (fraction of pairs where
        the property perfectly separates kept from removed)."""
        pairs = task.get("train", [])
        if not pairs:
            return 0.0
        n_good = 0
        for pair in pairs:
            inp = np.array(pair["input"], dtype=int) if not isinstance(pair["input"], np.ndarray) else pair["input"]
            out = np.array(pair["output"], dtype=int) if not isinstance(pair["output"], np.ndarray) else pair["output"]
            objs = _extract_objects_with_properties(inp)
            _inject_scene_context(objs)
            kr = _classify_two_groups(objs, inp, out)
            if kr is None:
                _strip_scene_context(objs)
                continue
            kept_idx, removed_idx = kr
            kept_vals = [bool(compute_fn(objs[i])) for i in kept_idx]
            removed_vals = [bool(compute_fn(objs[i])) for i in removed_idx]
            _strip_scene_context(objs)
            if (all(kept_vals) and not any(removed_vals)) or \
               (not any(kept_vals) and all(removed_vals)):
                n_good += 1
        return n_good / len(pairs)
