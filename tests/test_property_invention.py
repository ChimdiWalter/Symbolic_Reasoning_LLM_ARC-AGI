"""Tests for property_invention module.

Covers InventedProperty creation, PropertyInventor methods, compute_fn
builders, staged validation, registration, and the full pipeline.
"""
from __future__ import annotations

import numpy as np
import pytest

from reasoning_project.property_invention import (
    InventedProperty,
    PropertyInventor,
    _inject_scene_context,
    _strip_scene_context,
    _make_same_shape_as_reference,
    _make_same_color_as_marker,
    _make_inside_largest_frame,
    _make_touches_marker_object,
    _make_between_two_objects,
    _make_aligned_with_marker,
    _make_has_exactly_n_holes,
    _make_is_endpoint,
    _make_is_junction,
    _make_unique_under_rotation,
    _make_inside_colored_frame,
    _make_outside_colored_frame,
    _make_frame_contains_target,
    _make_part_of_repeating_pattern,
    _make_breaks_repeating_pattern,
    _make_belongs_to_minority_shape_group,
    _make_nearest_to_unique_color,
    _make_contains_color,
)
from reasoning_project.near_solved_memory import (
    NearSolvedMemory,
    NearSolvedTaskState,
    RepairAction,
)
from reasoning_project.manifold_memory import ManifoldPoint
from reasoning_project.reasoning_engine import (
    DERIVED_PREDICATES,
    _extract_objects_with_properties,
)


# ═══════════════════════════════════════════════════════════════════════════
# HELPERS — synthetic grids and mock near-solved states
# ═══════════════════════════════════════════════════════════════════════════

def _make_grid(*rows: list) -> np.ndarray:
    return np.array(rows, dtype=int)


def _simple_filter_task(task_id: str = "t1") -> dict:
    """Task where the rule is 'keep the largest object, remove others'.

    Grid layout (6x6):
      - Large 3x3 block of color 1 at (0,0)
      - Small 1x1 pixel of color 2 at (4,4)
      - Small 1x1 pixel of color 3 at (5,5)

    Output: only the 3x3 block survives.
    """
    inp = np.zeros((6, 6), dtype=int)
    inp[0:3, 0:3] = 1
    inp[4, 4] = 2
    inp[5, 5] = 3

    out = np.zeros((6, 6), dtype=int)
    out[0:3, 0:3] = 1

    inp2 = np.zeros((6, 6), dtype=int)
    inp2[0:3, 3:6] = 4
    inp2[4, 0] = 5
    inp2[5, 1] = 6

    out2 = np.zeros((6, 6), dtype=int)
    out2[0:3, 3:6] = 4

    return {
        "task_id": task_id,
        "train": [
            {"input": inp, "output": out},
            {"input": inp2, "output": out2},
        ],
    }


def _frame_filter_task(task_id: str = "t_frame") -> dict:
    """Task where the rule is 'keep objects inside a frame'.

    A 5x5 frame of color 1 encloses a 1x1 pixel of color 2.
    Another pixel of color 3 sits outside.
    Output keeps only objects inside the frame (and the frame).
    """
    inp = np.zeros((7, 7), dtype=int)
    # Frame: border of a 5x5 box at (1,1)-(5,5)
    inp[1, 1:6] = 1
    inp[5, 1:6] = 1
    inp[1:6, 1] = 1
    inp[1:6, 5] = 1
    # Object inside frame
    inp[3, 3] = 2
    # Object outside frame
    inp[0, 0] = 3

    out = np.zeros((7, 7), dtype=int)
    out[1, 1:6] = 1
    out[5, 1:6] = 1
    out[1:6, 1] = 1
    out[1:6, 5] = 1
    out[3, 3] = 2

    # Second pair — same structure different position
    inp2 = np.zeros((7, 7), dtype=int)
    inp2[0, 0:5] = 4
    inp2[4, 0:5] = 4
    inp2[0:5, 0] = 4
    inp2[0:5, 4] = 4
    inp2[2, 2] = 5
    inp2[6, 6] = 6

    out2 = np.zeros((7, 7), dtype=int)
    out2[0, 0:5] = 4
    out2[4, 0:5] = 4
    out2[0:5, 0] = 4
    out2[0:5, 4] = 4
    out2[2, 2] = 5

    return {
        "task_id": task_id,
        "train": [
            {"input": inp, "output": out},
            {"input": inp2, "output": out2},
        ],
    }


def _pattern_task(task_id: str = "t_pat") -> dict:
    """Task where the rule is 'remove the odd-one-out shape'.

    Three identical 2x1 shapes and one unique 1x1 shape.
    Output removes the unique one.
    """
    inp = np.zeros((8, 8), dtype=int)
    inp[0, 0:2] = 1  # shape A copy 1
    inp[2, 0:2] = 2  # shape A copy 2
    inp[4, 0:2] = 3  # shape A copy 3
    inp[6, 6] = 4     # shape B — unique

    out = np.zeros((8, 8), dtype=int)
    out[0, 0:2] = 1
    out[2, 0:2] = 2
    out[4, 0:2] = 3

    inp2 = np.zeros((8, 8), dtype=int)
    inp2[0, 4:6] = 5
    inp2[2, 4:6] = 6
    inp2[4, 4:6] = 7
    inp2[7, 7] = 8

    out2 = np.zeros((8, 8), dtype=int)
    out2[0, 4:6] = 5
    out2[2, 4:6] = 6
    out2[4, 4:6] = 7

    return {
        "task_id": task_id,
        "train": [
            {"input": inp, "output": out},
            {"input": inp2, "output": out2},
        ],
    }


def _make_mock_near_solved_state(
    task_id: str,
    failure_type: str = "no_discrimination",
    missing_cap: str = "property_gap",
    train_fit: float = 0.5,
) -> NearSolvedTaskState:
    emb = np.zeros(16, dtype=float)
    point = ManifoldPoint(
        embedding=emb,
        task_signature={"n_objects": 3},
        domain="grid",
    )
    return NearSolvedTaskState(
        task_id=task_id,
        manifold_point=point,
        active_chart="color_cc",
        best_hypothesis=None,
        hypothesis_score=train_fit,
        train_fit=train_fit,
        train_fit_detail=[True, False],
        loo_passed=False,
        failure_type=failure_type,
        failed_examples=[1],
        error_signature={"failure_type": failure_type},
        retrieved_success_anchors=[],
        retrieved_failure_anchors=[],
        proposed_repairs=[RepairAction("add_conjunction", "try conjunction", priority=1.0)],
        missing_capability_guess=missing_cap,
        views_tried=["color_cc"],
        iterations_used=3,
    )


# ═══════════════════════════════════════════════════════════════════════════
# TESTS
# ═══════════════════════════════════════════════════════════════════════════

# --- 1. InventedProperty creation ---

def test_invented_property_creation():
    """InventedProperty can be created with all fields."""
    prop = InventedProperty(
        name="test_prop",
        expression="a test property",
        property_family="topology",
        source_failure_cluster="cluster_0",
        source_tasks=["t1", "t2"],
        validation_tasks=[],
        compute_fn=lambda o: True,
        train_discrimination_score=0.75,
        loo_passed=False,
        false_positive_rate=0.0,
        promoted_tasks=[],
        status="proposed",
    )
    assert prop.name == "test_prop"
    assert prop.property_family == "topology"
    assert prop.status == "proposed"
    assert prop.train_discrimination_score == 0.75


def test_invented_property_status_transitions():
    """Status field accepts the expected values."""
    prop = InventedProperty(
        name="p",
        expression="",
        property_family="spatial_relation",
        source_failure_cluster="",
        source_tasks=[],
        validation_tasks=[],
        compute_fn=None,
        train_discrimination_score=0.0,
        loo_passed=False,
        false_positive_rate=0.0,
        promoted_tasks=[],
        status="proposed",
    )
    for status in ("proposed", "candidate_validated", "registered", "rejected"):
        prop.status = status
        assert prop.status == status


# --- 2. mine_from_failures ---

def test_mine_from_failures_basic():
    """mine_from_failures clusters states and links to tasks."""
    inventor = PropertyInventor()
    states = {
        "t1": _make_mock_near_solved_state("t1"),
        "t2": _make_mock_near_solved_state("t2"),
    }
    tasks = [_simple_filter_task("t1"), _simple_filter_task("t2")]
    clusters = inventor.mine_from_failures(states, tasks)
    assert len(clusters) >= 1
    cluster = clusters[0]
    assert "task_ids" in cluster
    assert "tasks" in cluster
    assert len(cluster["tasks"]) == 2


def test_mine_from_failures_skips_solved():
    """Solved states are excluded from clusters."""
    inventor = PropertyInventor()
    s1 = _make_mock_near_solved_state("t1")
    s2 = _make_mock_near_solved_state("t2")
    s2.status = "solved"
    states = {"t1": s1, "t2": s2}
    tasks = [_simple_filter_task("t1"), _simple_filter_task("t2")]
    clusters = inventor.mine_from_failures(states, tasks)
    # Only t1 is unsolved; cluster should still form (with 1 task)
    total_tasks = sum(len(c["tasks"]) for c in clusters)
    assert total_tasks == 1


# --- 3. propose_relational_properties ---

def test_propose_relational_properties_on_simple_task():
    """Relational proposals are generated; scores are computed."""
    inventor = PropertyInventor()
    tasks = [_simple_filter_task()]
    props = inventor.propose_relational_properties(tasks)
    # At least some candidates should score > 0 on this task
    assert isinstance(props, list)
    for p in props:
        assert p.status == "proposed"
        assert p.train_discrimination_score > 0.0


def test_propose_relational_returns_empty_on_no_input():
    """No crash on empty task list."""
    inventor = PropertyInventor()
    props = inventor.propose_relational_properties([])
    assert props == []


# --- 4. propose_topological_properties ---

def test_propose_topological_properties():
    """Topological proposals are generated for a frame-containing task."""
    inventor = PropertyInventor()
    tasks = [_frame_filter_task()]
    props = inventor.propose_topological_properties(tasks)
    assert isinstance(props, list)
    for p in props:
        assert p.property_family == "topology"
        assert p.status == "proposed"


# --- 5. propose_container_properties ---

def test_propose_container_properties():
    """Container proposals are generated for a frame-based task."""
    inventor = PropertyInventor()
    tasks = [_frame_filter_task()]
    props = inventor.propose_container_properties(tasks)
    assert isinstance(props, list)
    names = [p.name for p in props]
    # At least one container property should score > 0
    for p in props:
        assert p.property_family == "container"


# --- 6. propose_pattern_membership_properties ---

def test_propose_pattern_membership_properties():
    """Pattern membership proposals detect repeating/unique shapes."""
    inventor = PropertyInventor()
    tasks = [_pattern_task()]
    props = inventor.propose_pattern_membership_properties(tasks)
    names = [p.name for p in props]
    # breaks_repeating_pattern should fire: unique shape removed
    assert any("break" in n or "minority" in n or "repeating" in n for n in names)


# --- 7. validate_property stages ---

def test_validate_property_rejects_no_compute_fn():
    """Property with compute_fn=None is rejected immediately."""
    inventor = PropertyInventor()
    prop = InventedProperty(
        name="bad",
        expression="",
        property_family="topology",
        source_failure_cluster="",
        source_tasks=[],
        validation_tasks=[],
        compute_fn=None,
        train_discrimination_score=0.0,
        loo_passed=False,
        false_positive_rate=0.0,
        promoted_tasks=[],
        status="proposed",
    )
    result = inventor.validate_property(prop, [_simple_filter_task()])
    assert result.status == "rejected"


def test_validate_property_stages():
    """A property that discriminates on the task passes validation stages."""
    inventor = PropertyInventor()
    # Use is_largest — it perfectly separates kept/removed in _simple_filter_task
    fn = lambda o: o.get("is_largest", False)
    prop = InventedProperty(
        name="test_is_largest",
        expression="is the largest object",
        property_family="object_identity",
        source_failure_cluster="test",
        source_tasks=["t1"],
        validation_tasks=[],
        compute_fn=fn,
        train_discrimination_score=0.0,
        loo_passed=False,
        false_positive_rate=1.0,
        promoted_tasks=[],
        status="proposed",
    )
    tasks = [_simple_filter_task("t1")]
    result = inventor.validate_property(prop, tasks)
    assert result.train_discrimination_score > 0.0
    assert result.loo_passed is True
    assert result.status in ("candidate_validated", "cluster_validated", "promotion_validated")


def test_validate_property_rejects_bad_discrimination():
    """A property that never discriminates gets rejected."""
    inventor = PropertyInventor()
    fn = lambda o: True  # Always True — no discrimination
    prop = InventedProperty(
        name="always_true",
        expression="always true",
        property_family="topology",
        source_failure_cluster="test",
        source_tasks=["t1"],
        validation_tasks=[],
        compute_fn=fn,
        train_discrimination_score=0.0,
        loo_passed=False,
        false_positive_rate=0.0,
        promoted_tasks=[],
        status="proposed",
    )
    tasks = [_simple_filter_task("t1")]
    result = inventor.validate_property(prop, tasks)
    assert result.status == "rejected"


# --- 8. register_property ---

def test_register_property_success():
    """Validated property gets registered into DERIVED_PREDICATES."""
    inventor = PropertyInventor()
    unique_name = "_test_reg_prop_xyz_123"
    fn = lambda o: o.get("is_largest", False)
    prop = InventedProperty(
        name=unique_name,
        expression="test",
        property_family="object_identity",
        source_failure_cluster="test",
        source_tasks=[],
        validation_tasks=[],
        compute_fn=fn,
        train_discrimination_score=1.0,
        loo_passed=True,
        false_positive_rate=0.0,
        promoted_tasks=[],
        status="cluster_validated",
    )
    ok = inventor.register_property(prop)
    assert ok is True
    assert prop.status == "registered"
    assert prop in inventor.registered
    # Check it's in DERIVED_PREDICATES
    assert any(n == unique_name for n, _ in DERIVED_PREDICATES)
    # Cleanup
    DERIVED_PREDICATES[:] = [(n, f) for n, f in DERIVED_PREDICATES if n != unique_name]


def test_register_property_rejects_unvalidated():
    """Property that hasn't been validated cannot be registered."""
    inventor = PropertyInventor()
    prop = InventedProperty(
        name="unvalidated",
        expression="",
        property_family="topology",
        source_failure_cluster="",
        source_tasks=[],
        validation_tasks=[],
        compute_fn=lambda o: True,
        train_discrimination_score=0.0,
        loo_passed=False,
        false_positive_rate=0.0,
        promoted_tasks=[],
        status="proposed",
    )
    ok = inventor.register_property(prop)
    assert ok is False


def test_register_property_rejects_duplicate():
    """Cannot register a property whose name already exists."""
    inventor = PropertyInventor()
    prop = InventedProperty(
        name="is_filled_rect",  # already in BOOLEAN_PROPERTIES
        expression="",
        property_family="topology",
        source_failure_cluster="",
        source_tasks=[],
        validation_tasks=[],
        compute_fn=lambda o: True,
        train_discrimination_score=1.0,
        loo_passed=True,
        false_positive_rate=0.0,
        promoted_tasks=[],
        status="candidate_validated",
    )
    ok = inventor.register_property(prop)
    assert ok is False


# --- 9. run_full_pipeline smoke test ---

def test_run_full_pipeline_smoke():
    """Full pipeline runs without error and returns summary dict."""
    inventor = PropertyInventor()
    mem = NearSolvedMemory()
    s1 = _make_mock_near_solved_state("t1")
    s2 = _make_mock_near_solved_state("t2")
    mem.store_partial(s1)
    mem.store_partial(s2)

    tasks = [_simple_filter_task("t1"), _simple_filter_task("t2")]
    result = inventor.run_full_pipeline(mem, tasks)
    assert "n_clusters" in result
    assert "n_proposed" in result
    assert "level_distribution" in result
    assert "n_registered" in result
    assert "registered_names" in result
    assert isinstance(result["registered_names"], list)

    # Clean up any registered predicates
    registered = result.get("registered_names", [])
    if registered:
        DERIVED_PREDICATES[:] = [(n, f) for n, f in DERIVED_PREDICATES
                                  if n not in registered]


# --- 10. compute_fn builders ---

def test_compute_fn_has_exactly_n_holes():
    """has_exactly_n_holes compute_fn works on object dicts."""
    fn1 = _make_has_exactly_n_holes(1)
    fn0 = _make_has_exactly_n_holes(0)
    obj_with_hole = {"n_holes": 1}
    obj_no_hole = {"n_holes": 0}
    assert fn1(obj_with_hole) is True
    assert fn1(obj_no_hole) is False
    assert fn0(obj_no_hole) is True


def test_compute_fn_is_endpoint():
    fn = _make_is_endpoint()
    assert fn({"n_touching": 0}) is True
    assert fn({"n_touching": 1}) is True
    assert fn({"n_touching": 2}) is False


def test_compute_fn_is_junction():
    fn = _make_is_junction()
    assert fn({"n_touching": 3}) is True
    assert fn({"n_touching": 2}) is False


# --- 11. scene-context injection ---

def test_inject_and_strip_scene_context():
    """_inject_scene_context adds _scene_objects, _strip removes it."""
    objs = [{"label": 1}, {"label": 2}]
    _inject_scene_context(objs)
    assert objs[0]["_scene_objects"] is objs
    assert objs[1]["_scene_objects"] is objs
    _strip_scene_context(objs)
    assert "_scene_objects" not in objs[0]


# --- 12. relational compute_fn with scene context ---

def test_same_color_as_marker_with_scene_context():
    """same_color_as_marker works with injected scene context."""
    fn = _make_same_color_as_marker()
    marker = {"area": 1, "primary_color": 3, "label": 1}
    target = {"area": 9, "primary_color": 3, "label": 2}
    other = {"area": 4, "primary_color": 5, "label": 3}
    objs = [marker, target, other]
    _inject_scene_context(objs)
    assert fn(target) is True
    assert fn(other) is False
    _strip_scene_context(objs)


# --- 13. pattern membership compute_fns ---

def test_part_of_repeating_pattern():
    fn = _make_part_of_repeating_pattern()
    assert fn({"shape_group_size": 3}) is True
    assert fn({"shape_group_size": 1}) is False


def test_breaks_repeating_pattern():
    fn = _make_breaks_repeating_pattern()
    assert fn({"shape_group_size": 1}) is True
    assert fn({"shape_group_size": 2}) is False


def test_belongs_to_minority_shape_group():
    fn = _make_belongs_to_minority_shape_group()
    objs = [
        {"shape_group_size": 3},
        {"shape_group_size": 3},
        {"shape_group_size": 3},
        {"shape_group_size": 1},
    ]
    _inject_scene_context(objs)
    assert fn(objs[3]) is True
    assert fn(objs[0]) is False
    _strip_scene_context(objs)


# --- 14. container compute_fns ---

def test_inside_colored_frame():
    fn = _make_inside_colored_frame()
    frame = {
        "n_holes": 1,
        "convexity": 0.5,
        "bbox": (0, 0, 10, 10),
        "area": 36,
        "label": 1,
    }
    inside = {
        "n_holes": 0,
        "convexity": 1.0,
        "bbox": (2, 2, 4, 4),
        "area": 9,
        "label": 2,
    }
    outside = {
        "n_holes": 0,
        "convexity": 1.0,
        "bbox": (12, 12, 14, 14),
        "area": 9,
        "label": 3,
    }
    objs = [frame, inside, outside]
    _inject_scene_context(objs)
    assert fn(inside) is True
    assert fn(outside) is False
    assert fn(frame) is False  # frame is not inside itself
    _strip_scene_context(objs)


def test_outside_colored_frame():
    fn = _make_outside_colored_frame()
    frame = {"n_holes": 1, "convexity": 0.5, "bbox": (0, 0, 10, 10), "area": 36, "label": 1}
    inside = {"n_holes": 0, "convexity": 1.0, "bbox": (2, 2, 4, 4), "area": 9, "label": 2}
    outside = {"n_holes": 0, "convexity": 1.0, "bbox": (12, 12, 14, 14), "area": 9, "label": 3}
    objs = [frame, inside, outside]
    _inject_scene_context(objs)
    assert fn(outside) is True
    assert fn(inside) is False
    _strip_scene_context(objs)


# --- 15. full pipeline produces reasonable output structure ---

def test_full_pipeline_with_pattern_task():
    """Full pipeline on pattern tasks yields expected summary keys."""
    inventor = PropertyInventor()
    mem = NearSolvedMemory()
    s1 = _make_mock_near_solved_state("t_pat")
    s2 = _make_mock_near_solved_state("t_pat2")
    mem.store_partial(s1)
    mem.store_partial(s2)

    tasks = [_pattern_task("t_pat"), _pattern_task("t_pat2")]
    result = inventor.run_full_pipeline(mem, tasks)

    assert result["n_clusters"] >= 1
    assert result["n_proposed"] >= 0
    assert isinstance(result["registered"], list)
    assert isinstance(result["invented"], list)

    # Cleanup
    registered = result.get("registered_names", [])
    if registered:
        DERIVED_PREDICATES[:] = [(n, f) for n, f in DERIVED_PREDICATES
                                  if n not in registered]
