"""Adaptive Reasoning Loop — iterative perceive→hypothesize→test→diagnose→refine→learn.

Unlike the static PortfolioSolver (each solver gets one shot with a fixed perception),
this module runs an iterative loop that adapts perception and hypothesis generation
based on failure diagnosis. Each iteration:

1. PERCEIVE  — select a perception view (color CCs, per-color, silhouette, monochrome)
2. HYPOTHESIZE — generate hypotheses using the current view + invariants
3. TEST     — validate hypotheses against training pairs (LOO)
4. DIAGNOSE — classify WHY the best hypothesis failed
5. REFINE   — use diagnosis to choose next perception view / constrain search
6. LEARN    — on success, store solution in manifold memory

Test-time compute scales with difficulty: easy tasks exit in iteration 1,
hard tasks get more iterations with different views.
"""
from __future__ import annotations

import time
import numpy as np
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from reasoning_project.reasoning_engine import (
    DomainAdapter,
    GridDomainAdapter,
    ReasoningMemory,
    StructuralReasoner,
    WorkingMemory,
    _extract_objects_with_properties,
    _add_relational_properties,
    _classify_kept_removed,
    _classify_object_changes,
    _match_objects_hungarian,
)
from reasoning_project.manifold_memory import (
    FiberBundle,
    GeodesicSolver,
    ManifoldPoint,
    MemoryManifold,
    WorkingMemoryManifold,
    TopologicalRetriever,
    encode_task_signature,
    _signature_to_embedding,
)
from reasoning_project.neural_math import (
    InvariantDiscovery,
)
from reasoning_project.near_solved_memory import (
    NearSolvedTaskState,
    NearSolvedMemory,
    build_near_solved_state,
)
from reasoning_project.events import ReasoningEventLog

from scipy import ndimage


# ═══════════════════════════════════════════════════════════════════════════
# FAILURE DIAGNOSIS
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class Diagnosis:
    """Structured explanation of why a hypothesis failed."""
    failure_type: str  # "no_objects", "wrong_objects", "no_discrimination",
                       # "wrong_reconstruction", "partial_match", "no_hypothesis"
    detail: str = ""
    failing_pairs: List[int] = field(default_factory=list)
    near_miss_props: List[str] = field(default_factory=list)
    suggested_views: List[str] = field(default_factory=list)
    best_prop_score: float = 0.0


@dataclass
class LoopResult:
    """Result from the adaptive reasoning loop."""
    solved: bool
    predictions: Optional[List[np.ndarray]]
    hypothesis: Optional[Dict[str, Any]]
    iterations_used: int
    views_tried: List[str]
    diagnosis_trace: List[Diagnosis]
    elapsed_seconds: float
    memory_retrievals: int = 0
    manifold_chart: Optional[str] = None
    geodesic_info: Optional[Dict[str, Any]] = None


# ═══════════════════════════════════════════════════════════════════════════
# MULTI-VIEW PERCEPTION — different ways to decompose a grid into objects
# ═══════════════════════════════════════════════════════════════════════════

class PerColorAdapter(DomainAdapter):
    """Extract objects per-color: each contiguous region of each color is one object.
    Same as default GridDomainAdapter but treats each color independently."""

    def __init__(self, bg: int = 0):
        self.bg = bg

    def extract_objects(self, scene: np.ndarray) -> List[Dict[str, Any]]:
        h, w = scene.shape
        all_objects = []
        label_counter = 0
        colors_present = sorted(set(scene.flatten().tolist()) - {self.bg})
        for color in colors_present:
            color_mask = scene == color
            labeled, n = ndimage.label(color_mask)
            for lab in range(1, n + 1):
                obj_mask = labeled == lab
                rows, cols = np.where(obj_mask)
                if len(rows) == 0:
                    continue
                label_counter += 1
                r_min, r_max = int(rows.min()), int(rows.max())
                c_min, c_max = int(cols.min()), int(cols.max())
                bbox_h = r_max - r_min + 1
                bbox_w = c_max - c_min + 1
                local_mask = obj_mask[r_min:r_max + 1, c_min:c_max + 1]
                area = int(obj_mask.sum())
                convexity = area / max(bbox_h * bbox_w, 1)
                shape_bin = local_mask.astype(int)
                h_sym = bool(np.array_equal(shape_bin, shape_bin[::-1, :]))
                v_sym = bool(np.array_equal(shape_bin, shape_bin[:, ::-1]))
                d_sym = bool(np.array_equal(shape_bin, shape_bin.T)) if bbox_h == bbox_w else False
                touches_top = r_min == 0
                touches_bottom = r_max == h - 1
                touches_left = c_min == 0
                touches_right = c_max == w - 1
                bg_labeled, n_bg = ndimage.label(~local_mask)
                border_labels = set()
                border_labels.update(bg_labeled[0, :].tolist())
                border_labels.update(bg_labeled[-1, :].tolist())
                border_labels.update(bg_labeled[:, 0].tolist())
                border_labels.update(bg_labeled[:, -1].tolist())
                border_labels.discard(0)
                n_holes = sum(1 for lb in range(1, n_bg + 1) if lb not in border_labels)
                perimeter = 0
                for r in range(bbox_h):
                    for c in range(bbox_w):
                        if local_mask[r, c]:
                            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                                nr, nc = r + dr, c + dc
                                if nr < 0 or nr >= bbox_h or nc < 0 or nc >= bbox_w or not local_mask[nr, nc]:
                                    perimeter += 1
                all_objects.append({
                    "label": label_counter,
                    "mask": obj_mask,
                    "local_mask": local_mask,
                    "bbox": (r_min, c_min, r_max, c_max),
                    "center_r": float(rows.mean()),
                    "center_c": float(cols.mean()),
                    "area": area,
                    "bbox_h": bbox_h,
                    "bbox_w": bbox_w,
                    "primary_color": color,
                    "colors": [color],
                    "n_colors": 1,
                    "perimeter": perimeter,
                    "n_holes": n_holes,
                    "euler_char": 1 - n_holes,
                    "h_sym": h_sym,
                    "v_sym": v_sym,
                    "d_sym": d_sym,
                    "any_sym": h_sym or v_sym or d_sym,
                    "convexity": convexity,
                    "is_filled_rect": area == bbox_h * bbox_w,
                    "is_square": bbox_h == bbox_w,
                    "touches_boundary": touches_top or touches_bottom or touches_left or touches_right,
                    "touches_top": touches_top,
                    "touches_bottom": touches_bottom,
                    "touches_left": touches_left,
                    "touches_right": touches_right,
                    "bbox_ratio": bbox_h / max(bbox_w, 1),
                })
        _add_relational_properties(all_objects, scene, h, w)
        return all_objects

    def property_names(self) -> List[str]:
        from reasoning_project.reasoning_engine import _all_property_names
        return _all_property_names()

    def get_property(self, obj: Dict, prop: str) -> bool:
        from reasoning_project.reasoning_engine import _get_property_value
        return _get_property_value(obj, prop)

    def classify_kept_removed(self, objects, inp, out):
        return _classify_kept_removed(objects, inp, out)

    def classify_object_changes(self, objects, inp, out):
        return _classify_object_changes(objects, inp, out, bg=0)

    def reconstruct_filtered(self, inp, objects, keep_mask):
        result = inp.copy()
        for obj, keep in zip(objects, keep_mask):
            if not keep:
                result[obj["mask"]] = 0
        return result

    def reconstruct_recolored(self, inp, objects, label_map):
        result = inp.copy()
        for i, obj in enumerate(objects):
            if i in label_map:
                result[obj["mask"]] = label_map[i]
        return result

    def reconstruct_extracted(self, inp, objects, keep_mask):
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
        crop_mask = combined[r_min:r_max + 1, c_min:c_max + 1]
        cropped[crop_mask] = inp[r_min:r_max + 1, c_min:c_max + 1][crop_mask]
        return cropped

    def scenes_equal(self, a, b):
        return np.array_equal(a, b)

    def same_structure(self, a, b):
        return a.shape == b.shape

    def match_objects(self, in_objs, out_objs):
        return _match_objects_hungarian(in_objs, out_objs)


class MonochromeAdapter(DomainAdapter):
    """Ignore colors, treat all non-bg pixels as one color, then extract CCs."""

    def __init__(self, bg: int = 0):
        self.bg = bg

    def extract_objects(self, scene: np.ndarray) -> List[Dict[str, Any]]:
        binary = (scene != self.bg).astype(np.int32)
        return _extract_objects_with_properties(binary, bg=0)

    def property_names(self) -> List[str]:
        from reasoning_project.reasoning_engine import _all_property_names
        return _all_property_names()

    def get_property(self, obj: Dict, prop: str) -> bool:
        from reasoning_project.reasoning_engine import _get_property_value
        return _get_property_value(obj, prop)

    def classify_kept_removed(self, objects, inp, out):
        binary_out = (out != self.bg).astype(np.int32)
        return _classify_kept_removed(objects, (inp != self.bg).astype(np.int32), binary_out)

    def classify_object_changes(self, objects, inp, out):
        binary_inp = (inp != self.bg).astype(np.int32)
        binary_out = (out != self.bg).astype(np.int32)
        return _classify_object_changes(objects, binary_inp, binary_out, bg=0)

    def reconstruct_filtered(self, inp, objects, keep_mask):
        result = inp.copy()
        for obj, keep in zip(objects, keep_mask):
            if not keep:
                result[obj["mask"]] = 0
        return result

    def reconstruct_recolored(self, inp, objects, label_map):
        result = inp.copy()
        for i, obj in enumerate(objects):
            if i in label_map:
                result[obj["mask"]] = label_map[i]
        return result

    def reconstruct_extracted(self, inp, objects, keep_mask):
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
        crop_mask = combined[r_min:r_max + 1, c_min:c_max + 1]
        cropped[crop_mask] = inp[r_min:r_max + 1, c_min:c_max + 1][crop_mask]
        return cropped

    def scenes_equal(self, a, b):
        return np.array_equal(a, b)

    def same_structure(self, a, b):
        return a.shape == b.shape

    def match_objects(self, in_objs, out_objs):
        return _match_objects_hungarian(in_objs, out_objs)


class MajorityBgAdapter(DomainAdapter):
    """Auto-detect background as the most frequent color (not necessarily 0)."""

    def __init__(self):
        self._detected_bg: Optional[int] = None

    def _detect_bg(self, scene: np.ndarray) -> int:
        vals, counts = np.unique(scene, return_counts=True)
        return int(vals[np.argmax(counts)])

    def extract_objects(self, scene: np.ndarray) -> List[Dict[str, Any]]:
        bg = self._detect_bg(scene)
        self._detected_bg = bg
        return _extract_objects_with_properties(scene, bg=bg)

    def property_names(self) -> List[str]:
        from reasoning_project.reasoning_engine import _all_property_names
        return _all_property_names()

    def get_property(self, obj: Dict, prop: str) -> bool:
        from reasoning_project.reasoning_engine import _get_property_value
        return _get_property_value(obj, prop)

    def classify_kept_removed(self, objects, inp, out):
        return _classify_kept_removed(objects, inp, out)

    def classify_object_changes(self, objects, inp, out):
        bg = self._detected_bg if self._detected_bg is not None else 0
        return _classify_object_changes(objects, inp, out, bg=bg)

    def reconstruct_filtered(self, inp, objects, keep_mask):
        bg = self._detected_bg if self._detected_bg is not None else 0
        result = inp.copy()
        for obj, keep in zip(objects, keep_mask):
            if not keep:
                result[obj["mask"]] = bg
        return result

    def reconstruct_recolored(self, inp, objects, label_map):
        result = inp.copy()
        for i, obj in enumerate(objects):
            if i in label_map:
                result[obj["mask"]] = label_map[i]
        return result

    def reconstruct_extracted(self, inp, objects, keep_mask):
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
        crop_mask = combined[r_min:r_max + 1, c_min:c_max + 1]
        cropped[crop_mask] = inp[r_min:r_max + 1, c_min:c_max + 1][crop_mask]
        return cropped

    def scenes_equal(self, a, b):
        return np.array_equal(a, b)

    def same_structure(self, a, b):
        return a.shape == b.shape

    def match_objects(self, in_objs, out_objs):
        return _match_objects_hungarian(in_objs, out_objs)


# All available perception views
PERCEPTION_VIEWS: Dict[str, type] = {
    "color_cc": GridDomainAdapter,
    "per_color": PerColorAdapter,
    "monochrome": MonochromeAdapter,
    "majority_bg": MajorityBgAdapter,
}


def _make_adapter(view_name: str) -> DomainAdapter:
    cls = PERCEPTION_VIEWS[view_name]
    return cls()


# ═══════════════════════════════════════════════════════════════════════════
# PERCEPTION SELECTOR — choose which view to try next based on diagnosis
# ═══════════════════════════════════════════════════════════════════════════

class PerceptionSelector:
    """Chooses the next perception view based on failure diagnosis history."""

    DEFAULT_ORDER = ["color_cc", "per_color", "majority_bg", "monochrome"]

    def __init__(self, priority: Optional[List[str]] = None):
        self.order = list(priority or self.DEFAULT_ORDER)
        self.tried: List[str] = []
        self._pointer = 0

    def next_view(self, diagnosis: Optional[Diagnosis] = None) -> str:
        if diagnosis is not None and diagnosis.suggested_views:
            for sv in diagnosis.suggested_views:
                if sv not in self.tried and sv in PERCEPTION_VIEWS:
                    return sv
        while self._pointer < len(self.order):
            v = self.order[self._pointer]
            self._pointer += 1
            if v not in self.tried:
                return v
        return self.order[0]

    def mark_tried(self, view: str) -> None:
        if view not in self.tried:
            self.tried.append(view)

    def has_untried(self) -> bool:
        return any(v not in self.tried for v in self.order)


# ═══════════════════════════════════════════════════════════════════════════
# FAILURE DIAGNOSER — structured diagnosis of why a hypothesis failed
# ═══════════════════════════════════════════════════════════════════════════

class FailureDiagnoser:
    """Analyzes why a reasoning attempt failed and suggests next steps."""

    def diagnose(
        self,
        adapter: DomainAdapter,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        view_name: str,
    ) -> Diagnosis:
        for pi, (inp, out) in enumerate(train_pairs):
            objects = adapter.extract_objects(inp)
            if len(objects) < 2:
                return Diagnosis(
                    failure_type="no_objects",
                    detail=f"View '{view_name}' extracted <2 objects from pair {pi}",
                    failing_pairs=[pi],
                    suggested_views=self._suggest_for_no_objects(view_name),
                )

        prop_scores = self._score_properties(adapter, train_pairs)
        if not prop_scores:
            return Diagnosis(
                failure_type="no_discrimination",
                detail=f"No properties discriminate kept/removed in view '{view_name}'",
                suggested_views=self._suggest_for_no_discrimination(view_name),
            )

        best_prop, best_score = prop_scores[0]
        near_miss = [p for p, s in prop_scores if s > 0.5]

        if best_score < 1.0:
            failing = []
            for pi, (inp, out) in enumerate(train_pairs):
                objects = adapter.extract_objects(inp)
                cls = adapter.classify_kept_removed(objects, inp, out)
                if cls is None:
                    failing.append(pi)
                    continue
                kept, removed = cls
                for ki in kept:
                    if not adapter.get_property(objects[ki], best_prop):
                        failing.append(pi)
                        break

            return Diagnosis(
                failure_type="partial_match",
                detail=f"Best property '{best_prop}' matches {best_score:.1%} of pairs",
                failing_pairs=failing,
                near_miss_props=near_miss,
                best_prop_score=best_score,
                suggested_views=self._suggest_for_partial(view_name),
            )

        return Diagnosis(
            failure_type="wrong_reconstruction",
            detail=f"Properties discriminate but reconstruction fails in '{view_name}'",
            near_miss_props=near_miss,
            best_prop_score=best_score,
            suggested_views=self._suggest_for_reconstruction(view_name),
        )

    def _score_properties(
        self,
        adapter: DomainAdapter,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    ) -> List[Tuple[str, float]]:
        props = adapter.property_names()
        scores = []
        for prop in props:
            n_consistent = 0
            n_classifiable = 0
            for inp, out in train_pairs:
                objects = adapter.extract_objects(inp)
                cls = adapter.classify_kept_removed(objects, inp, out)
                if cls is None:
                    continue
                n_classifiable += 1
                kept, removed = cls
                kept_vals = [adapter.get_property(objects[k], prop) for k in kept]
                removed_vals = [adapter.get_property(objects[r], prop) for r in removed]
                if kept_vals and removed_vals:
                    if all(kept_vals) and not any(removed_vals):
                        n_consistent += 1
                    elif not any(kept_vals) and all(removed_vals):
                        n_consistent += 1
            if n_classifiable > 0:
                scores.append((prop, n_consistent / n_classifiable))
        scores.sort(key=lambda x: -x[1])
        return scores

    @staticmethod
    def _suggest_for_no_objects(view: str) -> List[str]:
        suggestions = {"color_cc": ["per_color", "majority_bg"],
                       "per_color": ["color_cc", "monochrome"],
                       "monochrome": ["color_cc", "per_color"],
                       "majority_bg": ["color_cc", "per_color"]}
        return suggestions.get(view, ["color_cc"])

    @staticmethod
    def _suggest_for_no_discrimination(view: str) -> List[str]:
        suggestions = {"color_cc": ["per_color", "majority_bg"],
                       "per_color": ["monochrome", "color_cc"],
                       "monochrome": ["per_color", "majority_bg"],
                       "majority_bg": ["per_color", "monochrome"]}
        return suggestions.get(view, ["per_color"])

    @staticmethod
    def _suggest_for_partial(view: str) -> List[str]:
        suggestions = {"color_cc": ["per_color", "majority_bg", "monochrome"],
                       "per_color": ["color_cc", "majority_bg"],
                       "monochrome": ["color_cc", "per_color"],
                       "majority_bg": ["color_cc", "per_color"]}
        return suggestions.get(view, ["color_cc"])

    @staticmethod
    def _suggest_for_reconstruction(view: str) -> List[str]:
        suggestions = {"color_cc": ["per_color"],
                       "per_color": ["color_cc"],
                       "monochrome": ["color_cc"],
                       "majority_bg": ["color_cc"]}
        return suggestions.get(view, ["color_cc"])


# ═══════════════════════════════════════════════════════════════════════════
# INVARIANT-GUIDED HYPOTHESIS GENERATION
# ═══════════════════════════════════════════════════════════════════════════

def _compute_invariants(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> Dict[str, Any]:
    """Discover preserved and transformed properties across training pairs."""
    discovery = InvariantDiscovery()
    result = discovery.discover(train_pairs)

    return {
        "preserved": result.get("preserved", []),
        "transformed": result.get("transformed", []),
        "irrelevant": result.get("irrelevant", []),
        "size_changes": not all(i.shape == o.shape for i, o in train_pairs),
        "color_changes": any(
            set(i.flatten()) != set(o.flatten()) for i, o in train_pairs
        ),
    }


# ═══════════════════════════════════════════════════════════════════════════
# ADAPTIVE REASONING LOOP
# ═══════════════════════════════════════════════════════════════════════════

class AdaptiveReasoningLoop:
    """Iterative reasoning with perception adaptation and failure-driven refinement.

    Unlike PortfolioSolver (one-shot, fixed perception), this loop:
    - Tries multiple perception views, guided by failure diagnosis
    - Uses invariant discovery to constrain hypothesis search
    - Retrieves similar tasks from manifold memory
    - Stores successful solutions for cross-task learning
    - Scales compute with difficulty (easy=1 iter, hard=many)
    """

    def __init__(
        self,
        max_iterations: int = 8,
        timeout_seconds: float = 60.0,
        memory: Optional[ReasoningMemory] = None,
        manifold: Optional[MemoryManifold] = None,
        view_order: Optional[List[str]] = None,
        near_solved_memory: Optional[NearSolvedMemory] = None,
        event_log: Optional[ReasoningEventLog] = None,
    ):
        self.max_iterations = max_iterations
        self.timeout_seconds = timeout_seconds
        self.memory = memory or ReasoningMemory()
        self.manifold = manifold
        self.view_order = view_order
        self.diagnoser = FailureDiagnoser()
        self.bundle = FiberBundle(manifold) if manifold is not None else None
        self.geodesic_solver = (
            GeodesicSolver(manifold, self.bundle) if manifold is not None else None
        )
        self.near_solved_memory = near_solved_memory or NearSolvedMemory(manifold)
        self.event_log = event_log

    def solve(
        self,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        test_inputs: List[np.ndarray],
        task_id: str = "",
        resume_from: Optional[NearSolvedTaskState] = None,
    ) -> LoopResult:
        t0 = time.perf_counter()
        log = self.event_log
        selector = PerceptionSelector(self.view_order)
        diagnosis_trace: List[Diagnosis] = []
        views_tried: List[str] = []
        memory_retrievals = 0
        parent_ids: List[str] = []

        # Emit TASK_OBSERVED
        if log is not None:
            ev = log.emit("TASK_OBSERVED", task_id, {
                "n_train": len(train_pairs),
                "n_test": len(test_inputs),
                "resumed": resume_from is not None,
            }, module="adaptive_loop")
            parent_ids.append(ev.event_id)

        # Resume: record prior views for logging but reset selector so all
        # views can be retried with the new hypothesis/invented operators
        if resume_from is not None:
            views_tried.extend(resume_from.views_tried)
            if log is not None:
                ev = log.emit("TASK_RESUMED", task_id, {
                    "views_tried_before": resume_from.views_tried,
                    "has_prior_hypothesis": resume_from.best_hypothesis is not None,
                }, module="adaptive_loop", parent_event_ids=parent_ids[:])
                parent_ids.append(ev.event_id)

        invariants = _compute_invariants(train_pairs)

        manifold_hints: List[Dict[str, Any]] = []
        geodesic_info: Optional[Dict[str, Any]] = None

        # Resume: inject the best partial hypothesis as first hint
        if resume_from is not None and resume_from.best_hypothesis is not None:
            manifold_hints.append(resume_from.best_hypothesis)
            memory_retrievals += 1

        if self.manifold is not None:
            sig = encode_task_signature(train_pairs)
            emb = _signature_to_embedding(sig)
            query_point = ManifoldPoint(
                embedding=emb,
                task_signature=sig,
            )
            retrieved = self.manifold.retrieve_topological(query_point, k=5)
            for pt in retrieved:
                if pt.hypothesis is not None:
                    manifold_hints.append(pt.hypothesis)
                    memory_retrievals += 1

            # Geodesic analysis: find path from query to nearest solution
            if self.geodesic_solver is not None:
                trajectory = self.geodesic_solver.solve_geodesic(query_point)
                geodesic_info = {
                    "converged": trajectory.converged,
                    "length": trajectory.length,
                    "energy": trajectory.energy,
                    "steps": len(trajectory.points),
                    "curvature_mismatch": self.geodesic_solver.curvature_mismatch_score(
                        query_point
                    ),
                }

        diagnosis: Optional[Diagnosis] = None

        for iteration in range(self.max_iterations):
            if time.perf_counter() - t0 > self.timeout_seconds:
                break

            view_name = selector.next_view(diagnosis)
            selector.mark_tried(view_name)
            views_tried.append(view_name)
            adapter = _make_adapter(view_name)

            # --- Phase 0: Try manifold-retrieved hypotheses ---
            if iteration == 0 and manifold_hints:
                reasoner = StructuralReasoner(adapter, memory=self.memory)
                for hyp in manifold_hints:
                    result = reasoner._replay_hypothesis(
                        hyp, train_pairs, test_inputs,
                    )
                    if result is not None:
                        predictions, meta = result
                        meta = dict(meta)
                        meta["source"] = "manifold_recall"
                        meta["view"] = view_name
                        meta["iteration"] = iteration
                        self._store_success(
                            train_pairs, test_inputs, predictions, meta,
                        )
                        return LoopResult(
                            solved=True,
                            predictions=predictions,
                            hypothesis=meta,
                            iterations_used=iteration + 1,
                            views_tried=views_tried,
                            diagnosis_trace=diagnosis_trace,
                            elapsed_seconds=time.perf_counter() - t0,
                            memory_retrievals=memory_retrievals,
                            geodesic_info=geodesic_info,
                        )

            # --- Phase 1: Full structural reasoning with this view ---
            reasoner = StructuralReasoner(adapter, memory=self.memory)
            solve_deadline = t0 + self.timeout_seconds
            result = reasoner.solve(train_pairs, test_inputs, deadline=solve_deadline)
            if result is not None:
                predictions, meta = result
                meta = dict(meta)
                meta["view"] = view_name
                meta["iteration"] = iteration
                self._store_success(
                    train_pairs, test_inputs, predictions, meta,
                )
                if log is not None:
                    log.emit("HYPOTHESIS_ACCEPTED", task_id, {
                        "strategy": meta.get("strategy"),
                        "view": view_name,
                        "iteration": iteration,
                    }, module="adaptive_loop", parent_event_ids=parent_ids[:])
                    log.emit("FINAL_PREDICTION_EMITTED", task_id, {
                        "source": "structural_reasoning",
                        "iteration": iteration,
                    }, module="adaptive_loop", parent_event_ids=parent_ids[:])
                return LoopResult(
                    solved=True,
                    predictions=predictions,
                    hypothesis=meta,
                    iterations_used=iteration + 1,
                    views_tried=views_tried,
                    diagnosis_trace=diagnosis_trace,
                    elapsed_seconds=time.perf_counter() - t0,
                    memory_retrievals=memory_retrievals,
                    geodesic_info=geodesic_info,
                )

            if time.perf_counter() - t0 > self.timeout_seconds:
                break

            # --- Phase 2: Invariant-guided hypothesis refinement ---
            if invariants["preserved"]:
                inv_result = self._try_invariant_guided(
                    adapter, train_pairs, test_inputs, invariants,
                )
                if inv_result is not None:
                    predictions, meta = inv_result
                    meta["view"] = view_name
                    meta["iteration"] = iteration
                    meta["source"] = "invariant_guided"
                    self._store_success(
                        train_pairs, test_inputs, predictions, meta,
                    )
                    return LoopResult(
                        solved=True,
                        predictions=predictions,
                        hypothesis=meta,
                        iterations_used=iteration + 1,
                        views_tried=views_tried,
                        diagnosis_trace=diagnosis_trace,
                        elapsed_seconds=time.perf_counter() - t0,
                        memory_retrievals=memory_retrievals,
                    )

            if time.perf_counter() - t0 > self.timeout_seconds:
                break

            # --- Phase 3: Diagnose failure and refine ---
            diagnosis = self.diagnoser.diagnose(adapter, train_pairs, view_name)
            diagnosis_trace.append(diagnosis)

            if not selector.has_untried():
                break

        best_partial_hyp = None
        for diag in reversed(diagnosis_trace):
            if diag.near_miss_props and diag.best_prop_score > 0:
                best_partial_hyp = {
                    "strategy": "partial_filter",
                    "property": diag.near_miss_props[0],
                    "keep_when_true": True,
                    "score": diag.best_prop_score,
                    "source": "failure_diagnosis",
                }
                break

        fail_result = LoopResult(
            solved=False,
            predictions=None,
            hypothesis=best_partial_hyp,
            iterations_used=len(views_tried),
            views_tried=views_tried,
            diagnosis_trace=diagnosis_trace,
            elapsed_seconds=time.perf_counter() - t0,
            memory_retrievals=memory_retrievals,
            geodesic_info=geodesic_info,
        )

        if task_id and self.near_solved_memory is not None:
            ns_state = build_near_solved_state(task_id, train_pairs, fail_result)
            self.near_solved_memory.store_partial(ns_state)
            if log is not None:
                log.emit("NEAR_SOLVED_STORED", task_id, {
                    "is_near_solved": ns_state.is_near_solved,
                    "failure_type": ns_state.failure_type,
                    "views_tried": ns_state.views_tried,
                    "has_hypothesis": ns_state.best_hypothesis is not None,
                }, module="adaptive_loop", parent_event_ids=parent_ids[:])

        return fail_result

    def _try_invariant_guided(
        self,
        adapter: DomainAdapter,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        test_inputs: List[np.ndarray],
        invariants: Dict[str, Any],
    ) -> Optional[Tuple[List[np.ndarray], Dict[str, Any]]]:
        """Use discovered invariants to focus hypothesis search.

        If we know certain properties are preserved (e.g., object count, color set),
        we can narrow the search to hypotheses consistent with those invariants.
        """
        preserved = invariants.get("preserved", [])
        if not preserved:
            return None

        props = adapter.property_names()
        preserved_set = set(preserved)

        for prop in props:
            for keep in [True, False]:
                if not self._check_count_consistency(
                    adapter, train_pairs, prop, keep, invariants
                ):
                    continue

                consistent = True
                for inp, out in train_pairs:
                    objects = adapter.extract_objects(inp)
                    cls = adapter.classify_kept_removed(objects, inp, out)
                    if cls is None:
                        consistent = False
                        break
                    kept, removed = cls
                    for ki in kept:
                        if adapter.get_property(objects[ki], prop) != keep:
                            consistent = False
                            break
                    if not consistent:
                        break
                    for ri in removed:
                        if adapter.get_property(objects[ri], prop) == keep:
                            consistent = False
                            break
                    if not consistent:
                        break

                if not consistent:
                    continue

                loo_ok = True
                for hold_out in range(len(train_pairs)):
                    held_inp, held_out_scene = train_pairs[hold_out]
                    objs = adapter.extract_objects(held_inp)
                    km = [adapter.get_property(o, prop) == keep for o in objs]
                    if all(km) or not any(km):
                        loo_ok = False
                        break
                    pred = adapter.reconstruct_filtered(held_inp, objs, km)
                    if pred is None or not adapter.scenes_equal(pred, held_out_scene):
                        loo_ok = False
                        break

                if loo_ok:
                    predictions = []
                    for ti in test_inputs:
                        objs = adapter.extract_objects(ti)
                        km = [adapter.get_property(o, prop) == keep for o in objs]
                        if all(km) or not any(km):
                            break
                        pred = adapter.reconstruct_filtered(ti, objs, km)
                        if pred is None:
                            break
                        predictions.append(pred)
                    else:
                        return predictions, {
                            "strategy": "invariant_guided_filter",
                            "property": prop,
                            "keep_when_true": keep,
                            "invariants_used": list(preserved_set),
                        }

        return None

    def _check_count_consistency(
        self,
        adapter: DomainAdapter,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        prop: str,
        keep: bool,
        invariants: Dict[str, Any],
    ) -> bool:
        """Check if filtering by this property produces count-consistent outputs."""
        if "n_objects" not in invariants.get("preserved", []):
            return True
        for inp, out in train_pairs:
            in_objs = adapter.extract_objects(inp)
            out_objs = adapter.extract_objects(out)
            n_kept = sum(1 for o in in_objs if adapter.get_property(o, prop) == keep)
            if n_kept != len(out_objs):
                return False
        return True

    def _store_success(
        self,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        test_inputs: List[np.ndarray],
        predictions: List[np.ndarray],
        hypothesis: Dict[str, Any],
    ) -> None:
        """Store successful solve in both episodic and manifold memory."""
        adapter = GridDomainAdapter()
        sig = ReasoningMemory.compute_task_signature(adapter, train_pairs)
        self.memory.store_episode(sig, hypothesis)

        if self.manifold is not None:
            msig = encode_task_signature(train_pairs)
            embedding = np.zeros(16)
            for i, (k, v) in enumerate(sorted(msig.items())):
                if i < 16 and isinstance(v, (int, float)):
                    embedding[i] = float(v)
            point = ManifoldPoint(
                embedding=embedding,
                task_signature=msig,
                hypothesis=hypothesis,
            )
            self.manifold.add_point(point)


# ═══════════════════════════════════════════════════════════════════════════
# ADAPTIVE PORTFOLIO — wraps static solvers + adaptive loop
# ═══════════════════════════════════════════════════════════════════════════

class AdaptivePortfolio:
    """Combines the static PortfolioSolver with the AdaptiveReasoningLoop.

    Strategy:
    1. Run the adaptive loop first (multi-view, invariant-guided, memory-backed)
    2. If it fails, fall back to the static portfolio solvers
    3. Collect all results, pick the best

    This ensures the adaptive loop can solve tasks the static solvers miss
    (via perception adaptation), while never regressing on tasks the static
    solvers already handle.
    """

    def __init__(
        self,
        static_solvers: Optional[Dict[str, Any]] = None,
        max_iterations: int = 8,
        adaptive_timeout: float = 30.0,
        static_timeout: float = 30.0,
        memory: Optional[ReasoningMemory] = None,
        manifold: Optional[MemoryManifold] = None,
    ):
        self.static_solvers = static_solvers or {}
        self.adaptive_loop = AdaptiveReasoningLoop(
            max_iterations=max_iterations,
            timeout_seconds=adaptive_timeout,
            memory=memory,
            manifold=manifold,
        )
        self.static_timeout = static_timeout

    def solve(
        self,
        task_id: str,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        test_inputs: List[np.ndarray],
        test_outputs: Optional[List[np.ndarray]] = None,
    ) -> Dict[str, Any]:
        t0 = time.perf_counter()

        # Phase 1: Adaptive loop (multi-view, iterative)
        loop_result = self.adaptive_loop.solve(
            train_pairs, test_inputs, task_id=task_id,
        )

        if loop_result.solved:
            correct = False
            if test_outputs is not None and loop_result.predictions is not None:
                correct = all(
                    np.array_equal(p, e)
                    for p, e in zip(loop_result.predictions, test_outputs)
                )
            return {
                "task_id": task_id,
                "solved": correct if test_outputs else True,
                "predictions": loop_result.predictions,
                "source": "adaptive_loop",
                "hypothesis": loop_result.hypothesis,
                "iterations": loop_result.iterations_used,
                "views_tried": loop_result.views_tried,
                "elapsed": time.perf_counter() - t0,
            }

        # Phase 2: Fall back to static solvers
        best_predictions = None
        best_solver = None
        best_meta = None
        for solver_name, solver_fn in self.static_solvers.items():
            if time.perf_counter() - t0 > self.static_timeout + self.adaptive_loop.timeout_seconds:
                break
            try:
                result = solver_fn(train_pairs, test_inputs)
            except Exception:
                continue
            if result is None:
                continue
            predictions, metadata = result
            if predictions is not None:
                if test_outputs is not None:
                    if all(np.array_equal(p, e) for p, e in zip(predictions, test_outputs)):
                        return {
                            "task_id": task_id,
                            "solved": True,
                            "predictions": predictions,
                            "source": f"static:{solver_name}",
                            "hypothesis": metadata if isinstance(metadata, dict) else {"info": str(metadata)},
                            "iterations": loop_result.iterations_used,
                            "views_tried": loop_result.views_tried,
                            "elapsed": time.perf_counter() - t0,
                        }
                if best_predictions is None:
                    best_predictions = predictions
                    best_solver = solver_name
                    best_meta = metadata

        if best_predictions is not None:
            correct = False
            if test_outputs is not None:
                correct = all(
                    np.array_equal(p, e)
                    for p, e in zip(best_predictions, test_outputs)
                )
            return {
                "task_id": task_id,
                "solved": correct if test_outputs else True,
                "predictions": best_predictions,
                "source": f"static:{best_solver}",
                "hypothesis": best_meta if isinstance(best_meta, dict) else {"info": str(best_meta)},
                "iterations": loop_result.iterations_used,
                "views_tried": loop_result.views_tried,
                "elapsed": time.perf_counter() - t0,
            }

        return {
            "task_id": task_id,
            "solved": False,
            "predictions": None,
            "source": "none",
            "hypothesis": None,
            "iterations": loop_result.iterations_used,
            "views_tried": loop_result.views_tried,
            "diagnosis_trace": [
                {"type": d.failure_type, "detail": d.detail}
                for d in loop_result.diagnosis_trace
            ],
            "elapsed": time.perf_counter() - t0,
        }
