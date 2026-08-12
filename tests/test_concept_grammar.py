"""Tests for reasoning_project.concept_grammar."""
from __future__ import annotations

import numpy as np
import pytest

from reasoning_project.concept_grammar import (
    RELATION_REGISTRY,
    SCORE_FIELDS,
    VALID_COMPOSITIONS,
    AndConcept,
    ArgMaxConcept,
    ArgMinConcept,
    BoundRelationConcept,
    ConceptExpression,
    ConceptGenerator,
    ConceptValidator,
    CountConcept,
    ExistsConcept,
    ForAllConcept,
    NotConcept,
    OrConcept,
    PrimitiveConcept,
    ReferenceConcept,
    RelationConcept,
    SchemaConcept,
    _check_composition,
    _scene_from_grid,
    _scene_from_objects,
)
from reasoning_project.reasoning_engine import (
    _all_property_names,
    _extract_objects_with_properties,
)


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════

def _make_grid_2obj():
    """A 6x6 grid with two objects:
    - obj A: 2x2 block of color 1 at top-left
    - obj B: 1x1 dot of color 2 at bottom-right
    """
    g = np.zeros((6, 6), dtype=int)
    g[0:2, 0:2] = 1  # A: area=4
    g[5, 5] = 2       # B: area=1
    return g


def _make_grid_frame():
    """A 7x7 grid with a frame (color 3) enclosing a small block (color 1)."""
    g = np.zeros((7, 7), dtype=int)
    # Frame: outer ring
    g[1, 1:6] = 3
    g[5, 1:6] = 3
    g[1:6, 1] = 3
    g[1:6, 5] = 3
    # Content: small block inside
    g[3, 3] = 1
    return g


def _make_grid_row():
    """Three single-cell objects in the same row, different colours."""
    g = np.zeros((5, 10), dtype=int)
    g[2, 1] = 1
    g[2, 4] = 2
    g[2, 7] = 3
    return g


def _make_grid_symmetric():
    """Two symmetric objects across the vertical centre line."""
    g = np.zeros((5, 9), dtype=int)
    g[2, 1] = 4
    g[2, 7] = 5
    return g


def _scene(grid: np.ndarray) -> dict:
    return _scene_from_grid(grid)


def _make_task_keep_largest():
    """Synthetic task: keep only the largest object."""
    pairs = []
    for _ in range(3):
        g = np.zeros((6, 6), dtype=int)
        g[0:3, 0:3] = 1   # large: area 9
        g[5, 5] = 2        # small: area 1
        out = g.copy()
        out[5, 5] = 0      # remove small
        pairs.append({"input": g, "output": out})
    return {"task_id": "keep_largest", "train": pairs}


# ═══════════════════════════════════════════════════════════════════════════
# 1. PrimitiveConcept
# ═══════════════════════════════════════════════════════════════════════════

def test_primitive_concept_evaluate():
    grid = _make_grid_2obj()
    scene = _scene(grid)
    objs = scene["objects"]
    pc = PrimitiveConcept("is_largest")
    assert pc.evaluate(objs[0], scene) is True   # obj A is larger
    assert pc.evaluate(objs[1], scene) is False

    pc2 = PrimitiveConcept("single_cell")
    assert pc2.evaluate(objs[0], scene) is False
    assert pc2.evaluate(objs[1], scene) is True


def test_primitive_concept_metadata():
    pc = PrimitiveConcept("has_holes")
    assert pc.complexity == 1
    assert pc.type_signature == "Object->Bool"
    assert pc.to_string() == "has_holes(x)"


# ═══════════════════════════════════════════════════════════════════════════
# 2. RelationConcept — inside, touches, same_shape, same_color, same_row,
#    same_col, left_of, above
# ═══════════════════════════════════════════════════════════════════════════

def test_relation_inside():
    grid = _make_grid_frame()
    scene = _scene(grid)
    objs = scene["objects"]
    # Expect two objects: the frame and the inner block
    frame_obj = max(objs, key=lambda o: o["area"])
    inner_obj = min(objs, key=lambda o: o["area"])
    rel = RelationConcept("inside")
    assert rel.evaluate_pair(inner_obj, frame_obj) is True
    assert rel.evaluate_pair(frame_obj, inner_obj) is False


def test_relation_touches():
    g = np.zeros((5, 5), dtype=int)
    g[0:2, 0:2] = 1  # 2x2 block
    g[0:2, 3:5] = 2  # 2x2 block nearby but not adjacent
    g[0, 2] = 1       # bridge pixel connecting them
    scene = _scene(g)
    objs = scene["objects"]
    if len(objs) < 2:
        # objects merged; use per-color extraction
        from reasoning_project.adaptive_loop import PerColorAdapter
        adapter = PerColorAdapter()
        objs = adapter.extract_objects(g)
        scene = {"objects": objs, "grid": g, "grid_h": g.shape[0], "grid_w": g.shape[1]}
    assert len(objs) >= 2
    rel = RelationConcept("touches")
    assert rel.evaluate_pair(objs[0], objs[1]) is True


def test_relation_same_shape():
    g = np.zeros((5, 10), dtype=int)
    g[0:2, 0:2] = 1  # 2x2 block
    g[0:2, 5:7] = 2  # identical 2x2 block, different colour
    scene = _scene(g)
    objs = scene["objects"]
    rel = RelationConcept("same_shape")
    assert rel.evaluate_pair(objs[0], objs[1]) is True


def test_relation_same_color():
    g = np.zeros((5, 10), dtype=int)
    g[0, 0] = 3
    g[0, 5] = 3
    scene = _scene(g)
    objs = scene["objects"]
    rel = RelationConcept("same_color")
    assert rel.evaluate_pair(objs[0], objs[1]) is True


def test_relation_same_row():
    grid = _make_grid_row()
    scene = _scene(grid)
    objs = scene["objects"]
    rel = RelationConcept("same_row")
    assert rel.evaluate_pair(objs[0], objs[1]) is True


def test_relation_same_col():
    g = np.zeros((5, 5), dtype=int)
    g[0, 2] = 1
    g[3, 2] = 2
    scene = _scene(g)
    objs = scene["objects"]
    rel = RelationConcept("same_col")
    assert rel.evaluate_pair(objs[0], objs[1]) is True


def test_relation_left_of():
    grid = _make_grid_row()
    scene = _scene(grid)
    objs = sorted(scene["objects"], key=lambda o: o["center_c"])
    rel = RelationConcept("left_of")
    assert rel.evaluate_pair(objs[0], objs[1]) is True
    assert rel.evaluate_pair(objs[1], objs[0]) is False


def test_relation_above():
    g = np.zeros((5, 5), dtype=int)
    g[0, 2] = 1
    g[4, 2] = 2
    scene = _scene(g)
    objs = sorted(scene["objects"], key=lambda o: o["center_r"])
    rel = RelationConcept("above")
    assert rel.evaluate_pair(objs[0], objs[1]) is True
    assert rel.evaluate_pair(objs[1], objs[0]) is False


# ═══════════════════════════════════════════════════════════════════════════
# 3. NotConcept
# ═══════════════════════════════════════════════════════════════════════════

def test_not_concept():
    grid = _make_grid_2obj()
    scene = _scene(grid)
    objs = scene["objects"]
    pc = PrimitiveConcept("is_largest")
    nc = NotConcept(pc)
    assert nc.evaluate(objs[0], scene) is False
    assert nc.evaluate(objs[1], scene) is True
    assert nc.complexity == 2
    assert "NOT" in nc.to_string()


# ═══════════════════════════════════════════════════════════════════════════
# 4. AndConcept
# ═══════════════════════════════════════════════════════════════════════════

def test_and_concept():
    grid = _make_grid_2obj()
    scene = _scene(grid)
    objs = scene["objects"]
    p1 = PrimitiveConcept("is_largest")
    p2 = PrimitiveConcept("is_filled_rect")
    ac = AndConcept(p1, p2)
    # obj A: largest and filled rect -> True
    assert ac.evaluate(objs[0], scene) is True
    # obj B: not largest -> False
    assert ac.evaluate(objs[1], scene) is False
    assert ac.complexity == 3
    assert "AND" in ac.to_string()


# ═══════════════════════════════════════════════════════════════════════════
# 5. OrConcept
# ═══════════════════════════════════════════════════════════════════════════

def test_or_concept():
    grid = _make_grid_2obj()
    scene = _scene(grid)
    objs = scene["objects"]
    p1 = PrimitiveConcept("is_largest")
    p2 = PrimitiveConcept("single_cell")
    oc = OrConcept(p1, p2)
    assert oc.evaluate(objs[0], scene) is True   # largest
    assert oc.evaluate(objs[1], scene) is True   # single cell
    assert oc.complexity == 3
    assert "OR" in oc.to_string()


# ═══════════════════════════════════════════════════════════════════════════
# 6. ExistsConcept
# ═══════════════════════════════════════════════════════════════════════════

def test_exists_concept():
    grid = _make_grid_row()
    scene = _scene(grid)
    objs = scene["objects"]
    # "exists y: single_cell(y) AND same_row(x, y)"
    filt = PrimitiveConcept("single_cell")
    rel = RelationConcept("same_row")
    ex = ExistsConcept(filt, rel)
    # All three objects are single cells in the same row, so each sees others
    for o in objs:
        assert ex.evaluate(o, scene) is True
    assert "exists y" in ex.to_string()


# ═══════════════════════════════════════════════════════════════════════════
# 7. ForAllConcept
# ═══════════════════════════════════════════════════════════════════════════

def test_forall_concept():
    grid = _make_grid_row()
    scene = _scene(grid)
    objs = scene["objects"]
    # "forall y: single_cell(y) => same_row(x, y)"
    filt = PrimitiveConcept("single_cell")
    rel = RelationConcept("same_row")
    fa = ForAllConcept(filt, rel)
    # All are single cells in the same row => True for everyone
    for o in objs:
        assert fa.evaluate(o, scene) is True
    assert "forall y" in fa.to_string()


# ═══════════════════════════════════════════════════════════════════════════
# 8. CountConcept
# ═══════════════════════════════════════════════════════════════════════════

def test_count_concept_eq():
    grid = _make_grid_row()
    scene = _scene(grid)
    objs = scene["objects"]
    filt = PrimitiveConcept("single_cell")
    cc = CountConcept(filt, 3, "==")
    # Scene-level: all objects get the same answer
    assert cc.evaluate(objs[0], scene) is True


def test_count_concept_ge():
    grid = _make_grid_row()
    scene = _scene(grid)
    objs = scene["objects"]
    filt = PrimitiveConcept("single_cell")
    cc = CountConcept(filt, 5, ">=")
    assert cc.evaluate(objs[0], scene) is False


# ═══════════════════════════════════════════════════════════════════════════
# 9. ArgMaxConcept
# ═══════════════════════════════════════════════════════════════════════════

def test_argmax_concept():
    grid = _make_grid_2obj()
    scene = _scene(grid)
    objs = scene["objects"]
    am = ArgMaxConcept("area")
    assert am.evaluate(objs[0], scene) is True   # larger
    assert am.evaluate(objs[1], scene) is False


# ═══════════════════════════════════════════════════════════════════════════
# 10. ArgMinConcept
# ═══════════════════════════════════════════════════════════════════════════

def test_argmin_concept():
    grid = _make_grid_2obj()
    scene = _scene(grid)
    objs = scene["objects"]
    am = ArgMinConcept("area")
    assert am.evaluate(objs[0], scene) is False
    assert am.evaluate(objs[1], scene) is True   # smaller
    assert am.complexity == 2


# ═══════════════════════════════════════════════════════════════════════════
# 11. ReferenceConcept
# ═══════════════════════════════════════════════════════════════════════════

def test_reference_largest():
    grid = _make_grid_2obj()
    scene = _scene(grid)
    ref = ReferenceConcept("largest")
    resolved = ref.resolve(scene)
    assert resolved is not None
    assert resolved["area"] == 4


def test_reference_smallest():
    grid = _make_grid_2obj()
    scene = _scene(grid)
    ref = ReferenceConcept("smallest")
    resolved = ref.resolve(scene)
    assert resolved is not None
    assert resolved["area"] == 1


def test_reference_unique_color():
    g = np.zeros((5, 10), dtype=int)
    g[0, 0] = 1
    g[0, 3] = 1  # two obj of color 1 (two connected components? No — separate)
    g[0, 7] = 2  # unique color
    scene = _scene(g)
    ref = ReferenceConcept("unique_color")
    resolved = ref.resolve(scene)
    assert resolved is not None
    assert resolved["primary_color"] == 2


def test_reference_marker():
    grid = _make_grid_2obj()
    scene = _scene(grid)
    ref = ReferenceConcept("marker")
    resolved = ref.resolve(scene)
    assert resolved is not None
    assert resolved["area"] == 1


def test_reference_frame():
    grid = _make_grid_frame()
    scene = _scene(grid)
    ref = ReferenceConcept("frame")
    resolved = ref.resolve(scene)
    assert resolved is not None
    assert resolved["n_holes"] > 0


def test_reference_none_when_missing():
    g = np.zeros((5, 5), dtype=int)
    g[0:2, 0:2] = 1
    g[3:5, 3:5] = 2
    scene = _scene(g)
    ref = ReferenceConcept("marker")
    # No single-cell marker
    assert ref.resolve(scene) is None


# ═══════════════════════════════════════════════════════════════════════════
# 12. BoundRelationConcept
# ═══════════════════════════════════════════════════════════════════════════

def test_bound_relation():
    grid = _make_grid_2obj()
    scene = _scene(grid)
    objs = scene["objects"]
    rel = RelationConcept("same_color")
    ref = ReferenceConcept("marker")
    br = BoundRelationConcept(rel, ref)
    # marker is color 2 (the single-cell obj)
    # obj A (color 1) should be False
    assert br.evaluate(objs[0], scene) is False
    # Marker itself: br returns False when ref is the same object
    marker_obj = ref.resolve(scene)
    assert br.evaluate(marker_obj, scene) is False
    assert br.to_string() == "same_color(x, marker)"


def test_bound_relation_returns_false_when_no_reference():
    g = np.zeros((5, 5), dtype=int)
    g[0:2, 0:2] = 1
    scene = _scene(g)
    rel = RelationConcept("same_color")
    ref = ReferenceConcept("marker")  # no single-cell marker
    br = BoundRelationConcept(rel, ref)
    assert br.evaluate(scene["objects"][0], scene) is False


# ═══════════════════════════════════════════════════════════════════════════
# 13. SchemaConcept
# ═══════════════════════════════════════════════════════════════════════════

def test_schema_container_content():
    grid = _make_grid_frame()
    scene = _scene(grid)
    objs = scene["objects"]
    inner = min(objs, key=lambda o: o["area"])
    frame = max(objs, key=lambda o: o["area"])
    sc = SchemaConcept("ContainerContent")
    assert sc.evaluate(inner, scene) is True
    assert sc.evaluate(frame, scene) is False


def test_schema_marker_target():
    grid = _make_grid_2obj()
    scene = _scene(grid)
    objs = scene["objects"]
    sc = SchemaConcept("MarkerTarget")
    # obj B is the marker (area=1), obj A is NOT marker-color
    # since they have different colours, A is not a target
    assert sc.evaluate(objs[0], scene) is False


def test_schema_symmetry_completion():
    grid = _make_grid_symmetric()
    scene = _scene(grid)
    objs = scene["objects"]
    sc = SchemaConcept("SymmetryCompletion")
    # The two objects are symmetric across the vertical centre
    assert sc.evaluate(objs[0], scene) is True
    assert sc.evaluate(objs[1], scene) is True
    assert sc.complexity == 4


# ═══════════════════════════════════════════════════════════════════════════
# 14. ConceptGenerator depth 1
# ═══════════════════════════════════════════════════════════════════════════

def test_generator_depth_1():
    gen = ConceptGenerator()
    d1 = gen.generate_depth_1()
    n_props = len(_all_property_names())
    n_argmax_min = 2 * len(gen._DEPTH1_SCORE_FIELDS)
    assert len(d1) == n_props + n_argmax_min
    # All should be complexity 1 or 2
    assert all(c.complexity <= 2 for c in d1)


# ═══════════════════════════════════════════════════════════════════════════
# 15. ConceptGenerator depth 2
# ═══════════════════════════════════════════════════════════════════════════

def test_generator_depth_2():
    gen = ConceptGenerator(primitives=["is_largest", "single_cell", "has_holes"])
    d2 = gen.generate_depth_2(beam_size=500)
    names = [c.name for c in d2]
    # Should contain NOT, AND, BoundRelation, Exists
    assert any("not_" in n for n in names)
    assert any("AND" in n for n in names)
    assert any("_wrt_" in n for n in names)
    assert any("exists_" in n for n in names)


# ═══════════════════════════════════════════════════════════════════════════
# 16. ConceptGenerator depth k
# ═══════════════════════════════════════════════════════════════════════════

def test_generator_depth_k():
    gen = ConceptGenerator(primitives=["is_largest", "single_cell"])
    dk = gen.generate_depth_k(3, beam_size=50)
    assert len(dk) > 0
    assert len(dk) <= 50
    # Should be sorted by complexity
    complexities = [c.complexity for c in dk]
    assert complexities == sorted(complexities)


# ═══════════════════════════════════════════════════════════════════════════
# 17. ConceptGenerator from failure cluster
# ═══════════════════════════════════════════════════════════════════════════

def test_generator_from_failure_cluster():
    task = _make_task_keep_largest()
    gen = ConceptGenerator()
    concepts = gen.generate_from_failure_cluster([task], max_concepts=20)
    # Should find at least one concept that discriminates
    assert len(concepts) > 0
    # Check that at least one has "is_largest" or "argmax_area" in its name
    names = [c.name for c in concepts]
    assert any("largest" in n or "area" in n or "single_cell" in n for n in names)


# ═══════════════════════════════════════════════════════════════════════════
# 18. ConceptValidator discrimination
# ═══════════════════════════════════════════════════════════════════════════

def test_validator_discrimination():
    task = _make_task_keep_largest()
    val = ConceptValidator()
    pc = PrimitiveConcept("is_largest")
    score = val.training_discrimination_score(pc, task)
    assert score == 1.0


def test_validator_discrimination_zero():
    task = _make_task_keep_largest()
    val = ConceptValidator()
    # "in_top_half" does not separate kept/removed in this task
    pc = PrimitiveConcept("in_top_half")
    score = val.training_discrimination_score(pc, task)
    # Both the large block and the small one differ in top_half but
    # we need to check actual value — large is in top, small is not.
    # Actually, the large block (rows 0-2) is in top half and the small
    # (row 5) is in bottom, AND kept=large, removed=small, so this
    # actually discriminates. Let's pick something that definitely doesn't.
    pc2 = PrimitiveConcept("is_filled_rect")
    score2 = val.training_discrimination_score(pc2, task)
    # Both objects are filled rects, so this cannot discriminate
    assert score2 == 0.0


# ═══════════════════════════════════════════════════════════════════════════
# 19. ConceptValidator LOO
# ═══════════════════════════════════════════════════════════════════════════

def test_validator_loo():
    task = _make_task_keep_largest()
    val = ConceptValidator()
    pc = PrimitiveConcept("is_largest")
    assert val.loo_validate(pc, task) is True


# ═══════════════════════════════════════════════════════════════════════════
# 20. ConceptValidator batch_evaluate
# ═══════════════════════════════════════════════════════════════════════════

def test_validator_batch():
    task = _make_task_keep_largest()
    val = ConceptValidator()
    concepts = [PrimitiveConcept("is_largest"), PrimitiveConcept("is_filled_rect")]
    results = val.batch_evaluate(concepts, [task], min_discrimination=1.0)
    # Only is_largest should pass
    assert len(results) >= 1
    assert results[0][0].name == "is_largest"


# ═══════════════════════════════════════════════════════════════════════════
# 21. Type checking
# ═══════════════════════════════════════════════════════════════════════════

def test_type_check_valid():
    assert _check_composition("Not", "Object->Bool") is True
    assert _check_composition("And", "Object->Bool", "Object->Bool") is True
    assert _check_composition("Exists", "Object->Bool", "Object,Object->Bool") is True
    assert _check_composition("BoundRelation", "Object,Object->Bool", "Scene->Object") is True


def test_type_check_invalid():
    assert _check_composition("Not", "Scene->Object") is False
    assert _check_composition("And", "Object->Bool", "Scene->Object") is False


def test_type_error_raised():
    rel = RelationConcept("inside")
    with pytest.raises(TypeError):
        NotConcept(rel)  # rel is Object,Object->Bool, not Object->Bool


# ═══════════════════════════════════════════════════════════════════════════
# 22. to_string for complex expressions
# ═══════════════════════════════════════════════════════════════════════════

def test_to_string_complex():
    p1 = PrimitiveConcept("is_largest")
    p2 = PrimitiveConcept("has_holes")
    not_p2 = NotConcept(p2)
    and_expr = AndConcept(p1, not_p2)
    s = and_expr.to_string()
    assert "AND" in s
    assert "NOT" in s
    assert "is_largest" in s
    assert "has_holes" in s


# ═══════════════════════════════════════════════════════════════════════════
# 23. scene helpers
# ═══════════════════════════════════════════════════════════════════════════

def test_scene_from_grid():
    grid = _make_grid_2obj()
    scene = _scene_from_grid(grid)
    assert "objects" in scene
    assert "grid" in scene
    assert scene["grid_h"] == 6
    assert scene["grid_w"] == 6
    assert len(scene["objects"]) == 2


# ═══════════════════════════════════════════════════════════════════════════
# 24. RelationConcept error for unknown relation
# ═══════════════════════════════════════════════════════════════════════════

def test_relation_unknown_raises():
    with pytest.raises(ValueError):
        RelationConcept("nonexistent_relation")


# ═══════════════════════════════════════════════════════════════════════════
# 25. ArgMax/ArgMin error for unknown field
# ═══════════════════════════════════════════════════════════════════════════

def test_argmax_unknown_field_raises():
    with pytest.raises(ValueError):
        ArgMaxConcept("unknown_field")


def test_argmin_unknown_field_raises():
    with pytest.raises(ValueError):
        ArgMinConcept("unknown_field")


# ═══════════════════════════════════════════════════════════════════════════
# 26. CountConcept comparators
# ═══════════════════════════════════════════════════════════════════════════

def test_count_concept_comparators():
    grid = _make_grid_row()
    scene = _scene(grid)
    objs = scene["objects"]
    filt = PrimitiveConcept("single_cell")
    # There are 3 single-cell objects
    assert CountConcept(filt, 3, "==").evaluate(objs[0], scene) is True
    assert CountConcept(filt, 2, ">").evaluate(objs[0], scene) is True
    assert CountConcept(filt, 4, "<").evaluate(objs[0], scene) is True
    assert CountConcept(filt, 4, "<=").evaluate(objs[0], scene) is True
    assert CountConcept(filt, 3, "<=").evaluate(objs[0], scene) is True
    assert CountConcept(filt, 2, "<=").evaluate(objs[0], scene) is False


# ═══════════════════════════════════════════════════════════════════════════
# 27. ReferenceConcept unique_shape
# ═══════════════════════════════════════════════════════════════════════════

def test_reference_unique_shape():
    g = np.zeros((6, 10), dtype=int)
    g[0:2, 0:2] = 1   # 2x2 block A
    g[0:2, 4:6] = 2   # 2x2 block B (same shape)
    g[0, 8] = 3        # 1x1 dot (unique shape)
    scene = _scene(g)
    ref = ReferenceConcept("unique_shape")
    resolved = ref.resolve(scene)
    assert resolved is not None
    assert resolved["area"] == 1


# ═══════════════════════════════════════════════════════════════════════════
# 28. SchemaConcept marker target positive case
# ═══════════════════════════════════════════════════════════════════════════

def test_schema_marker_target_positive():
    g = np.zeros((6, 6), dtype=int)
    g[0, 0] = 5         # marker (area=1, color 5)
    g[2:4, 2:4] = 5     # larger obj same colour as marker
    scene = _scene(g)
    objs = scene["objects"]
    big = max(objs, key=lambda o: o["area"])
    sc = SchemaConcept("MarkerTarget")
    assert sc.evaluate(big, scene) is True
