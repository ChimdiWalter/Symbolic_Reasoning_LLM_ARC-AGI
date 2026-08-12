"""Promotion microcycle test: prove the feedback loop can mechanically
promote at least one task from near-solved to solved.

Design principle: tasks use 3 training pairs (satisfies min_train=3 in
StructuralReasoner), and the discriminating concept is an ExistsConcept
or BoundRelation that is NOT equivalent to any single base property or
conjunction of two base properties.

Full local loop per family:
    static solve → fail → store NearSolvedTaskState
    → cluster failure → ConceptGenerator proposes
    → ConceptValidator validates → register as learned property
    → StructuralReasoner resume with extended adapter → solve
    → emit certificate

Success criteria:
    near_solved_states > 0
    generated_concepts > 0
    validated_concepts > 0
    promotions > 0
    false_positives = 0
"""
from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reasoning_project.reasoning_engine import (
    DomainAdapter,
    GridDomainAdapter,
    ReasoningMemory,
    StructuralReasoner,
    _all_property_names,
    _extract_objects_with_properties,
    _classify_kept_removed,
    _get_property_value,
)
from reasoning_project.concept_grammar import (
    BoundRelationConcept,
    ConceptExpression,
    ConceptGenerator,
    ConceptValidator,
    ExistsConcept,
    PrimitiveConcept,
    ReferenceConcept,
    RelationConcept,
    _scene_from_objects,
)
from reasoning_project.concept_memory import ConceptMemory, LearnedConcept
from reasoning_project.near_solved_memory import (
    NearSolvedMemory,
    NearSolvedTaskState,
    build_near_solved_state,
)
from reasoning_project.adaptive_loop import AdaptiveReasoningLoop
from reasoning_project.manifold_memory import MemoryManifold
from reasoning_project.events import ReasoningEventLog


# ═══════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def _make_grid(h: int, w: int, bg: int = 0) -> np.ndarray:
    return np.full((h, w), bg, dtype=int)


def _place_rect(grid: np.ndarray, r: int, c: int, h: int, w: int, color: int) -> None:
    grid[r:r+h, c:c+w] = color


def _place_frame(grid: np.ndarray, r: int, c: int, h: int, w: int, color: int) -> None:
    grid[r:r+h, c:c+w] = color
    grid[r+1:r+h-1, c+1:c+w-1] = 0


# ═══════════════════════════════════════════════════════════════════════════
# TASK FAMILIES — each requires a concept NOT in base 81 properties
# ═══════════════════════════════════════════════════════════════════════════

def make_exists_marker_same_row_tasks() -> List[Dict]:
    """Family 1: Keep objects in the same row as a single-cell marker.

    Marker = unique color (1), area 1. Rule: keep x if same_row(x, marker).
    The marker itself is REMOVED from output (so it's not in the "kept" list).

    Design: objects have same size (2x2), colors shared between kept/removed.
    Only spatial row relation to the marker discriminates.

    Concept needed: same_row(x, ref_marker) — BoundRelation.
    """
    tasks = []
    configs = [
        {"marker_rc": (3, 0), "keep": [(3, 3, 2, 2, 4), (3, 7, 2, 2, 5)],
         "remove": [(7, 3, 2, 2, 4), (7, 7, 2, 2, 5), (0, 5, 2, 2, 6)]},
        {"marker_rc": (5, 0), "keep": [(5, 4, 2, 2, 3), (5, 8, 2, 2, 6)],
         "remove": [(0, 4, 2, 2, 3), (9, 4, 2, 2, 6), (0, 8, 2, 2, 7)]},
        {"marker_rc": (7, 0), "keep": [(7, 3, 2, 2, 4), (7, 7, 2, 2, 5)],
         "remove": [(1, 3, 2, 2, 4), (1, 7, 2, 2, 5), (4, 5, 2, 2, 6)]},
        {"marker_rc": (2, 0), "keep": [(2, 4, 2, 2, 3), (2, 8, 2, 2, 7)],
         "remove": [(6, 4, 2, 2, 3), (6, 8, 2, 2, 7), (9, 2, 2, 2, 4)]},
    ]
    for cfg in configs:
        inp = _make_grid(11, 11)
        mr, mc = cfg["marker_rc"]
        inp[mr, mc] = 1  # marker

        for r, c, h, w, col in cfg["keep"]:
            _place_rect(inp, r, c, h, w, col)
        for r, c, h, w, col in cfg["remove"]:
            _place_rect(inp, r, c, h, w, col)

        # Output: keep only same-row objects, remove marker too
        out = _make_grid(11, 11)
        for r, c, h, w, col in cfg["keep"]:
            _place_rect(out, r, c, h, w, col)

        tasks.append({"input": inp.tolist(), "output": out.tolist()})

    return [{"task_id": "exists_marker_same_row", "train": tasks[:3], "test": tasks[3:]}]


def make_exists_frame_inside_tasks() -> List[Dict]:
    """Family 2: Keep objects inside a frame (frame removed from output too).

    Frame (hollow rect, color 2) + single-cell objects inside and outside.
    Output: only inside objects survive (frame and outside objects zeroed).
    This avoids the frame being in "kept" which would break discrimination.

    Design: outside objects placed AWAY from grid boundary (not at corners)
    to prevent touches_boundary from discriminating.

    Concept needed: inside(x, ref_frame) — BoundRelation.
    """
    tasks = []
    configs = [
        {"frame": (2, 2, 7, 7),
         "inside": [(4, 4, 3), (5, 6, 4), (6, 3, 5)],
         "outside": [(1, 0, 3), (9, 5, 4), (0, 9, 5)]},
        {"frame": (1, 1, 8, 8),
         "inside": [(3, 3, 3), (5, 5, 4), (6, 2, 5)],
         "outside": [(0, 0, 3), (9, 5, 4), (5, 10, 5)]},
        {"frame": (2, 2, 6, 7),
         "inside": [(4, 4, 3), (5, 6, 4), (6, 3, 5)],
         "outside": [(0, 5, 3), (9, 5, 4), (1, 10, 5)]},
        {"frame": (2, 2, 7, 7),
         "inside": [(4, 5, 3), (6, 4, 4), (5, 3, 5)],
         "outside": [(0, 5, 3), (10, 5, 4), (5, 10, 5)]},
    ]
    for cfg in configs:
        inp = _make_grid(11, 11)
        fr, fc, fh, fw = cfg["frame"]
        _place_frame(inp, fr, fc, fh, fw, 2)
        for r, c, col in cfg["inside"]:
            inp[r, c] = col
        for r, c, col in cfg["outside"]:
            inp[r, c] = col

        # Output: only inside objects survive
        out = _make_grid(11, 11)
        for r, c, col in cfg["inside"]:
            out[r, c] = col

        tasks.append({"input": inp.tolist(), "output": out.tolist()})

    return [{"task_id": "exists_frame_inside", "train": tasks[:3], "test": tasks[3:]}]


def make_same_shape_unique_color_tasks() -> List[Dict]:
    """Family 3: Keep objects with same shape as the unique-color reference.

    Unique-color object (color 9) has a specific shape. Objects with same
    shape (any rotation) are kept. Objects with different shape are removed.
    Design: same-shaped objects have different colors to prevent color-based
    discrimination. Different-shaped objects also have varied colors.

    Concept needed: same_shape(x, ref_unique_color) — BoundRelation.
    """
    tasks = []
    # L-shape template
    L = np.array([[1, 0], [1, 0], [1, 1]], dtype=int)
    # T-shape template (distractor)
    T = np.array([[1, 1, 1], [0, 1, 0]], dtype=int)

    configs = [
        {"ref": (1, 1, 9), "same": [(1, 5, 3), (5, 1, 4), (5, 5, 6)],
         "diff": [(8, 0, 5), (8, 5, 7)]},
        {"ref": (2, 2, 9), "same": [(2, 6, 4), (6, 2, 5), (6, 6, 3)],
         "diff": [(0, 7, 6), (9, 0, 7)]},
        {"ref": (0, 0, 9), "same": [(0, 4, 3), (4, 0, 5), (4, 4, 7)],
         "diff": [(8, 1, 4), (8, 6, 6)]},
        {"ref": (1, 1, 9), "same": [(1, 6, 4), (6, 1, 5), (6, 6, 8)],
         "diff": [(0, 7, 3), (9, 0, 6)]},
    ]
    for cfg in configs:
        inp = _make_grid(11, 11)
        rr, rc, rcol = cfg["ref"]
        for r in range(3):
            for c in range(2):
                if L[r, c]:
                    inp[rr + r, rc + c] = rcol

        for sr, sc, col in cfg["same"]:
            for r in range(3):
                for c in range(2):
                    if L[r, c]:
                        inp[sr + r, sc + c] = col

        for dr, dc, col in cfg["diff"]:
            for r in range(2):
                for c in range(3):
                    if T[r, c]:
                        inp[dr + r, dc + c] = col

        out = inp.copy()
        for dr, dc, col in cfg["diff"]:
            for r in range(2):
                for c in range(3):
                    if T[r, c]:
                        out[dr + r, dc + c] = 0

        tasks.append({"input": inp.tolist(), "output": out.tolist()})

    return [{"task_id": "same_shape_unique_color", "train": tasks[:3], "test": tasks[3:]}]


def make_touches_largest_tasks() -> List[Dict]:
    """Family 4: Keep single-cell objects touching the largest object.

    Large block + single-cell objects. Some adjacent (4-connected), some far.
    Large block is REMOVED from output so only touching objects remain.
    Colors shared between touching and far to prevent color discrimination.

    Concept needed: touches(x, ref_largest) — BoundRelation.
    """
    tasks = []
    configs = [
        {"large": (3, 3, 4, 4, 2),
         "touching": [(3, 7, 3), (7, 4, 4), (2, 3, 5), (5, 2, 6)],
         "far": [(0, 0, 3), (0, 10, 4), (10, 0, 5), (10, 10, 6)]},
        {"large": (4, 4, 3, 3, 2),
         "touching": [(4, 7, 3), (7, 5, 4), (3, 4, 5), (5, 3, 6)],
         "far": [(0, 0, 3), (0, 10, 4), (10, 0, 5), (10, 10, 6)]},
        {"large": (2, 2, 4, 4, 2),
         "touching": [(2, 6, 3), (6, 3, 4), (1, 2, 5), (4, 1, 6)],
         "far": [(0, 9, 3), (9, 9, 4), (9, 0, 5), (0, 0, 6)]},
        {"large": (3, 3, 5, 5, 2),
         "touching": [(3, 8, 3), (8, 4, 4), (2, 3, 5), (5, 2, 6)],
         "far": [(0, 0, 3), (0, 10, 4), (10, 0, 5), (10, 10, 6)]},
    ]
    for cfg in configs:
        inp = _make_grid(11, 11)
        lr, lc, lh, lw, lcol = cfg["large"]
        _place_rect(inp, lr, lc, lh, lw, lcol)

        for r, c, col in cfg["touching"]:
            inp[r, c] = col
        for r, c, col in cfg["far"]:
            inp[r, c] = col

        # Output: only touching objects survive (large block removed)
        out = _make_grid(11, 11)
        for r, c, col in cfg["touching"]:
            out[r, c] = col

        tasks.append({"input": inp.tolist(), "output": out.tolist()})

    return [{"task_id": "touches_largest", "train": tasks[:3], "test": tasks[3:]}]


def make_same_col_as_marker_tasks() -> List[Dict]:
    """Family 5: Keep objects in the same column as a single-cell marker.

    Marker (area=1, color 1) is REMOVED from output.
    Objects in same column kept, others removed.

    Concept needed: same_col(x, ref_marker) — BoundRelation.
    """
    tasks = []
    configs = [
        {"marker_rc": (0, 5), "keep": [(3, 5, 2, 2, 3), (7, 5, 2, 2, 4)],
         "remove": [(3, 0, 2, 2, 3), (7, 0, 2, 2, 4), (3, 9, 2, 2, 5)]},
        {"marker_rc": (0, 3), "keep": [(4, 3, 2, 2, 6), (8, 3, 2, 2, 7)],
         "remove": [(4, 7, 2, 2, 6), (8, 7, 2, 2, 7), (1, 9, 2, 2, 8)]},
        {"marker_rc": (0, 7), "keep": [(3, 7, 2, 2, 3), (7, 7, 2, 2, 4)],
         "remove": [(3, 1, 2, 2, 3), (7, 1, 2, 2, 4), (5, 4, 2, 2, 5)]},
        {"marker_rc": (0, 4), "keep": [(4, 4, 2, 2, 6), (8, 4, 2, 2, 5)],
         "remove": [(4, 9, 2, 2, 6), (8, 9, 2, 2, 5), (1, 1, 2, 2, 7)]},
    ]
    for cfg in configs:
        inp = _make_grid(11, 11)
        mr, mc = cfg["marker_rc"]
        inp[mr, mc] = 1

        for r, c, h, w, col in cfg["keep"]:
            _place_rect(inp, r, c, h, w, col)
        for r, c, h, w, col in cfg["remove"]:
            _place_rect(inp, r, c, h, w, col)

        # Output: keep only same-column objects, remove marker too
        out = _make_grid(11, 11)
        for r, c, h, w, col in cfg["keep"]:
            _place_rect(out, r, c, h, w, col)

        tasks.append({"input": inp.tolist(), "output": out.tolist()})

    return [{"task_id": "same_col_as_marker", "train": tasks[:3], "test": tasks[3:]}]


ALL_FAMILIES = [
    ("exists_marker_same_row", make_exists_marker_same_row_tasks),
    ("exists_frame_inside", make_exists_frame_inside_tasks),
    ("same_shape_unique_color", make_same_shape_unique_color_tasks),
    ("touches_largest", make_touches_largest_tasks),
    ("same_col_as_marker", make_same_col_as_marker_tasks),
]


# ═══════════════════════════════════════════════════════════════════════════
# EXTENDED ADAPTER — adds learned concepts as properties
# ═══════════════════════════════════════════════════════════════════════════

class ExtendedGridAdapter(GridDomainAdapter):
    """GridDomainAdapter with learned ConceptExpressions as additional properties."""

    def __init__(self, learned_concepts: List[Tuple[str, ConceptExpression]] = None):
        super().__init__()
        self._learned = learned_concepts or []

    def property_names(self) -> List[str]:
        base = super().property_names()
        return base + [name for name, _ in self._learned]

    def get_property(self, obj: Dict, prop: str) -> bool:
        for name, expr in self._learned:
            if prop == name:
                scene = obj.get("_scene")
                if scene is None:
                    return False
                return expr.evaluate(obj, scene)
        return super().get_property(obj, prop)

    def extract_objects(self, scene: np.ndarray) -> List[Dict[str, Any]]:
        objects = super().extract_objects(scene)
        scene_dict = _scene_from_objects(objects, scene)
        for obj in objects:
            obj["_scene"] = scene_dict
        return objects


# ═══════════════════════════════════════════════════════════════════════════
# CONCEPT INVENTION
# ═══════════════════════════════════════════════════════════════════════════

def _is_non_primitive_concept(concept: ConceptExpression) -> bool:
    """Guard: a promotion only counts if the concept is relational/composed,
    not a base primitive predicate already in the 81-property language."""
    if isinstance(concept, PrimitiveConcept):
        return False
    base_props = set(_all_property_names())
    if concept.name in base_props:
        return False
    if concept.complexity <= 1:
        return False
    return True


def invent_concept_for_task(
    family_name: str, task: Dict
) -> Optional[Tuple[ConceptExpression, LearnedConcept]]:
    """Generate and validate a concept for a task.

    Guard: only returns concepts that are NOT already in the base
    primitive property language (must be relational or composed).
    """
    generator = ConceptGenerator()
    validator = ConceptValidator()

    # Strategy 1: failure-guided (checks BoundRelation and ExistsConcept)
    concepts = generator.generate_from_failure_cluster([task])
    for concept in concepts:
        if concept.type_signature != "Object->Bool":
            continue
        if not _is_non_primitive_concept(concept):
            continue
        disc = validator.training_discrimination_score(concept, task)
        if disc >= 1.0:
            loo = validator.loo_validate(concept, task)
            if loo:
                return _wrap(concept, family_name, task)

    # Strategy 2: depth-2 enumeration (skip primitives)
    d2 = generator.generate_depth_2(beam_size=300)
    for concept in d2:
        if concept.type_signature != "Object->Bool":
            continue
        if not _is_non_primitive_concept(concept):
            continue
        disc = validator.training_discrimination_score(concept, task)
        if disc >= 1.0:
            loo = validator.loo_validate(concept, task)
            if loo:
                return _wrap(concept, family_name, task)

    return None


def _wrap(concept: ConceptExpression, family_name: str, task: Dict
          ) -> Tuple[ConceptExpression, LearnedConcept]:
    return concept, LearnedConcept(
        name=concept.name,
        expression_str=concept.to_string(),
        complexity=concept.complexity,
        source_failure_cluster=f"microcycle:{family_name}",
        source_tasks=[task["task_id"]],
        loo_passed=True,
        discrimination_score=1.0,
        status="validated",
    )


# ═══════════════════════════════════════════════════════════════════════════
# MICROCYCLE
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class MicrocycleResult:
    family_name: str
    static_solved: bool = False
    near_solved_stored: bool = False
    concept_generated: bool = False
    concept_validated: bool = False
    concept_name: str = ""
    concept_expression: str = ""
    resume_solved: bool = False
    false_positive: bool = False
    elapsed_seconds: float = 0.0
    error: str = ""
    debug_info: str = ""


def run_microcycle(family_name: str, tasks_fn) -> MicrocycleResult:
    """Run the full promotion microcycle for one family."""
    t0 = time.perf_counter()
    result = MicrocycleResult(family_name=family_name)

    try:
        task_list = tasks_fn()
        task = task_list[0]
        train_pairs = [(np.array(p["input"]), np.array(p["output"]))
                       for p in task["train"]]
        test_inputs = [np.array(p["input"]) for p in task["test"]]
        test_outputs = [np.array(p["output"]) for p in task["test"]]

        # === Step 1: Static solve — should FAIL ===
        adapter = GridDomainAdapter()
        memory = ReasoningMemory()
        reasoner = StructuralReasoner(adapter, memory=memory, min_train=2)
        static_result = reasoner.solve(train_pairs, test_inputs)

        if static_result is not None:
            preds, meta = static_result
            correct = all(np.array_equal(p, t) for p, t in zip(preds, test_outputs))
            if correct:
                result.static_solved = True
                result.debug_info = f"Solved by: {meta.get('strategy', '?')}, prop={meta.get('property', '?')}"
                result.elapsed_seconds = time.perf_counter() - t0
                return result

        # === Step 2: Store near-solved state ===
        event_log = ReasoningEventLog()
        manifold = MemoryManifold()
        ns_memory = NearSolvedMemory(manifold)
        loop = AdaptiveReasoningLoop(
            max_iterations=4,
            timeout_seconds=30.0,
            memory=memory,
            manifold=manifold,
            near_solved_memory=ns_memory,
            event_log=event_log,
        )
        loop_result = loop.solve(train_pairs, test_inputs, task_id=task["task_id"])

        if loop_result.solved:
            preds = loop_result.predictions
            correct = all(np.array_equal(p, t) for p, t in zip(preds, test_outputs))
            if correct:
                result.static_solved = True
                result.debug_info = "Solved by adaptive loop"
                result.elapsed_seconds = time.perf_counter() - t0
                return result

        result.near_solved_stored = True

        # === Step 3: Concept invention ===
        invention = invent_concept_for_task(family_name, task)
        if invention is None:
            result.error = "concept_generation_failed"
            result.elapsed_seconds = time.perf_counter() - t0
            return result

        concept_expr, learned_concept = invention
        result.concept_generated = True
        result.concept_validated = learned_concept.loo_passed
        result.concept_name = learned_concept.name
        result.concept_expression = learned_concept.expression_str

        # === Step 4: Resume with extended adapter ===
        ext_adapter = ExtendedGridAdapter(
            learned_concepts=[(learned_concept.name, concept_expr)]
        )
        ext_memory = ReasoningMemory()
        ext_reasoner = StructuralReasoner(ext_adapter, memory=ext_memory, min_train=2)
        resume_result = ext_reasoner.solve(train_pairs, test_inputs)

        if resume_result is not None:
            preds, meta = resume_result
            correct = all(np.array_equal(p, t) for p, t in zip(preds, test_outputs))
            if correct:
                result.resume_solved = True
            else:
                result.false_positive = True
                result.debug_info = f"Wrong output via {meta.get('strategy')}"
        else:
            # Debug: check adapter discrimination
            debug_lines = []
            for i, (inp, out) in enumerate(train_pairs):
                objs = ext_adapter.extract_objects(inp)
                kr = ext_adapter.classify_kept_removed(objs, inp, out)
                if kr is None:
                    debug_lines.append(f"P{i}: classify=None")
                    continue
                kept, removed = kr
                k_vals = [ext_adapter.get_property(objs[k], learned_concept.name) for k in kept]
                r_vals = [ext_adapter.get_property(objs[r], learned_concept.name) for r in removed]
                disc_pos = all(k_vals) and not any(r_vals)
                disc_neg = not any(k_vals) and all(r_vals)
                debug_lines.append(
                    f"P{i}: kept={k_vals} rem={r_vals} disc={'POS' if disc_pos else 'NEG' if disc_neg else 'NO'}"
                )
            result.debug_info = "; ".join(debug_lines)
            result.error = "resume_solve_failed"

    except Exception as e:
        import traceback
        result.error = f"exception: {type(e).__name__}: {e}"
        result.debug_info = traceback.format_exc()[-500:]

    result.elapsed_seconds = time.perf_counter() - t0
    return result


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def main():
    output_dir = Path(__file__).resolve().parent.parent / "outputs" / "promotion_microcycle"
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("PROMOTION MICROCYCLE TEST")
    print("=" * 60)
    print()

    results: List[MicrocycleResult] = []
    promoted_tasks = []
    validated_concepts = []
    event_chains = []

    for family_name, tasks_fn in ALL_FAMILIES:
        print(f"[{family_name}] Running microcycle...")
        r = run_microcycle(family_name, tasks_fn)
        results.append(r)

        status = "PROMOTED" if r.resume_solved else (
            "STATIC_SOLVED" if r.static_solved else f"FAILED({r.error})")
        print(f"  static={r.static_solved} ns={r.near_solved_stored} "
              f"gen={r.concept_generated} val={r.concept_validated} "
              f"promoted={r.resume_solved} fp={r.false_positive} [{r.elapsed_seconds:.1f}s]")
        print(f"  → {status}")
        if r.concept_name:
            print(f"  concept: {r.concept_name} = {r.concept_expression}")
        if r.debug_info:
            print(f"  debug: {r.debug_info[:300]}")
        print()

        if r.resume_solved:
            promoted_tasks.append({"task_id": family_name, "concept_name": r.concept_name,
                                   "concept_expression": r.concept_expression})
        if r.concept_validated:
            validated_concepts.append({"name": r.concept_name, "expression": r.concept_expression,
                                       "family": family_name, "promoted": r.resume_solved})
        event_chains.append({"family": family_name, "static_fail": not r.static_solved,
                             "near_solved_stored": r.near_solved_stored,
                             "concept_generated": r.concept_generated,
                             "concept_validated": r.concept_validated,
                             "promotion": r.resume_solved, "false_positive": r.false_positive})

    # Summary
    n = len(results)
    n_static = sum(1 for r in results if r.static_solved)
    n_ns = sum(1 for r in results if r.near_solved_stored)
    n_gen = sum(1 for r in results if r.concept_generated)
    n_val = sum(1 for r in results if r.concept_validated)
    n_promo = sum(1 for r in results if r.resume_solved)
    n_fp = sum(1 for r in results if r.false_positive)

    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  families:           {n}")
    print(f"  static_solved:      {n_static}")
    print(f"  near_solved:        {n_ns}")
    print(f"  concepts_generated: {n_gen}")
    print(f"  concepts_validated: {n_val}")
    print(f"  promotions:         {n_promo}")
    print(f"  false_positives:    {n_fp}")

    criteria = {
        "near_solved_states > 0": n_ns > 0,
        "generated_concepts > 0": n_gen > 0,
        "validated_concepts > 0": n_val > 0,
        "promotions > 0": n_promo > 0,
        "false_positives = 0": n_fp == 0,
    }
    all_pass = all(criteria.values())
    print("\nSUCCESS CRITERIA:")
    for crit, passed in criteria.items():
        print(f"  [{'PASS' if passed else 'FAIL'}] {crit}")
    print(f"\nOVERALL: {'PASS' if all_pass else 'FAIL'}")

    # Write outputs
    with open(output_dir / "summary.md", "w") as f:
        f.write("# Promotion Microcycle Results\n\n")
        f.write(f"**Date**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("## Metrics\n\n| Metric | Value |\n|--------|-------|\n")
        f.write(f"| Families | {n} |\n| Static solved | {n_static} |\n")
        f.write(f"| Near-solved | {n_ns} |\n| Concepts generated | {n_gen} |\n")
        f.write(f"| Concepts validated | {n_val} |\n| **Promotions** | **{n_promo}** |\n")
        f.write(f"| False positives | {n_fp} |\n\n")
        f.write("## Criteria\n\n")
        for crit, passed in criteria.items():
            f.write(f"- [{'PASS' if passed else 'FAIL'}] `{crit}`\n")
        f.write(f"\n**Overall: {'PASS' if all_pass else 'FAIL'}**\n\n")
        f.write("## Per-Family\n\n| Family | Static | NS | Gen | Val | Promo | FP | Error |\n")
        f.write("|--------|--------|----|-----|-----|-------|----|-------|\n")
        for r in results:
            f.write(f"| {r.family_name} | {r.static_solved} | {r.near_solved_stored} | "
                    f"{r.concept_generated} | {r.concept_validated} | "
                    f"{r.resume_solved} | {r.false_positive} | {r.error} |\n")
        f.write("\n## Concepts\n\n")
        for vc in validated_concepts:
            f.write(f"- **{vc['name']}**: `{vc['expression']}` → promoted={vc['promoted']}\n")

    with open(output_dir / "promoted_tasks.jsonl", "w") as f:
        for pt in promoted_tasks:
            f.write(json.dumps(pt) + "\n")
    with open(output_dir / "event_chains.jsonl", "w") as f:
        for ec in event_chains:
            f.write(json.dumps(ec) + "\n")
    with open(output_dir / "validated_concepts.json", "w") as f:
        json.dump(validated_concepts, f, indent=2)

    print(f"\nOutputs: {output_dir}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
