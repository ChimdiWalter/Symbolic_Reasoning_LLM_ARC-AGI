"""Unit tests: segmentation variants S1-S6, coherence-based per-task choice,
and the feature/relation registry (segmentation + features team ownership).

Real-task coverage (STAGE1_REQUIREMENTS.md Section 7.1/7.2 dev set):
  motion/copy: 05f2a901, dc433765, 1caeab9d (+ 88a10436 as the S3 probe)
  shrink:      4852f2fa, 358ba94e

No task-ID branches anywhere: task IDs appear only as data-loading keys.
"""
from __future__ import annotations

import json

import numpy as np
import pytest

from geocat_arc.data.arc_loader import load_tasks
from geocat_arc.perception.grid import Grid
from geocat_arc.perception.objects import ARCObject

from geocat_arc.object_reasoning.types import (
    FeatureKind,
    GridContext,
    MultiColorObject,
    SegmentationVariant,
    SEGMENTATION_TRIAL_ORDER,
    to_grid_pairs,
)
from geocat_arc.object_reasoning import segmentation as seg
from geocat_arc.object_reasoning import features as feat


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MOTION_TASKS = ["05f2a901", "dc433765", "1caeab9d"]
SHRINK_TASKS = ["4852f2fa", "358ba94e"]
S3_PROBE_TASK = "88a10436"
ALL_TASKS = MOTION_TASKS + SHRINK_TASKS + [S3_PROBE_TASK]


@pytest.fixture(scope="module", autouse=True)
def registry():
    feat.register_builtin_features()
    return feat.FEATURE_REGISTRY


@pytest.fixture(scope="module")
def dev_tasks():
    try:
        tasks = load_tasks(split="training", task_ids=ALL_TASKS)
    except FileNotFoundError:
        pytest.skip("ARC training data not available")
    by_id = {t.task_id: t for t in tasks}
    missing = [tid for tid in ALL_TASKS if tid not in by_id]
    if missing:
        pytest.skip(f"dev tasks missing from training split: {missing}")
    return by_id


def _pairs(task):
    return to_grid_pairs([(np.array(p.input), np.array(p.output))
                          for p in task.train])


# Synthetic grid A (5x5): distinguishes S1/S2/S3/S4/S6.
#   colors: 1 = L-tromino, 2 = L-tromino, 3 = three scattered singletons
#   (3,1) is 4-adjacent to the color-1 component (S3 merge) and
#   8-adjacent to (4,0) and (4,2) (S2/S4 merges).
GRID_A = Grid(np.array([
    [0, 0, 0, 0, 0],
    [1, 0, 0, 2, 2],
    [1, 1, 0, 2, 0],
    [0, 3, 0, 0, 0],
    [3, 0, 3, 0, 0],
]))

# Grid B (3x4-ish): majority color 7 => S5 adapts background to 7.
GRID_B = Grid(np.array([
    [7, 7, 7, 7],
    [7, 0, 0, 7],
    [7, 7, 7, 7],
]))

# Grid C: ring of 4 containing a 6 (containment features / relations).
GRID_C = Grid(np.array([
    [4, 4, 4, 4, 4],
    [4, 0, 6, 0, 4],
    [4, 4, 4, 4, 4],
]))

# Grid D: pure ring => exactly one hole.
GRID_D = Grid(np.array([
    [4, 4, 4],
    [4, 0, 4],
    [4, 4, 4],
]))


def _ctx(grid, objects, background=0):
    return GridContext(grid=grid, objects=objects, background=background)


def _by_first_cell(objects):
    return sorted(objects, key=lambda o: min(o.cells))


# ---------------------------------------------------------------------------
# Registry vocabulary (Requirement 2.2.1)
# ---------------------------------------------------------------------------

class TestRegistry:
    def test_exact_feature_vocabulary(self):
        planned = {name for name, _, _, _ in feat.PLANNED_FEATURES}
        assert set(feat.FEATURE_REGISTRY) == planned
        for name, kind, relational, _ in feat.PLANNED_FEATURES:
            spec = feat.get_feature(name)
            assert spec.kind is kind, name
            assert spec.relational == relational, name
            assert callable(spec.fn), name

    def test_exact_relation_vocabulary(self):
        planned = {name for name, _ in feat.PLANNED_RELATIONS}
        assert set(feat.RELATION_REGISTRY) == planned
        for name in planned:
            assert callable(feat.get_relation(name).fn)

    def test_idempotent_second_call(self):
        n_f, n_r = len(feat.FEATURE_REGISTRY), len(feat.RELATION_REGISTRY)
        feat.register_builtin_features()  # must not raise / duplicate
        assert len(feat.FEATURE_REGISTRY) == n_f
        assert len(feat.RELATION_REGISTRY) == n_r

    def test_duplicate_registration_rejected(self):
        with pytest.raises(ValueError):
            feat.register_feature("color", FeatureKind.COLOR,
                                  lambda o, c: 0)

    def test_features_of_kind_partition(self):
        total = sum(len(feat.features_of_kind(k)) for k in FeatureKind)
        assert total == len(feat.FEATURE_REGISTRY)


# ---------------------------------------------------------------------------
# Segmentation variants on synthetic grids
# ---------------------------------------------------------------------------

class TestVariantsSynthetic:
    def test_s1_same_color_4(self):
        objs = seg.segment_s1(GRID_A)
        assert len(objs) == 5
        by_color = {}
        for o in objs:
            by_color.setdefault(o.color, []).append(o)
        assert sorted(by_color) == [1, 2, 3]
        assert len(by_color[3]) == 3          # scattered singletons stay apart
        assert {o.size for o in by_color[3]} == {1}
        assert by_color[1][0].cells == frozenset({(1, 0), (2, 0), (2, 1)})

    def test_s2_same_color_8(self):
        objs = seg.segment_s2(GRID_A)
        assert len(objs) == 3                 # color-3 cells merge diagonally
        three = [o for o in objs if o.color == 3]
        assert len(three) == 1 and three[0].size == 3

    def test_s3_multicolor_4(self):
        objs = seg.segment_s3(GRID_A)
        assert len(objs) == 4
        merged = [o for o in objs if isinstance(o, MultiColorObject)
                  and len(o.color_multiset) > 1]
        assert len(merged) == 1
        m = merged[0]
        assert m.cells == frozenset({(1, 0), (2, 0), (2, 1), (3, 1)})
        assert m.color == 1                   # majority color
        assert m.color_multiset == (1, 3)
        assert m.cell_colors[(3, 1)] == 3
        assert m.cell_colors[(1, 0)] == 1

    def test_s4_multicolor_8(self):
        objs = seg.segment_s4(GRID_A)
        assert len(objs) == 2                 # left group + color-2 group
        sizes = sorted(o.size for o in objs)
        assert sizes == [3, 6]
        assert all(isinstance(o, MultiColorObject) for o in objs)

    def test_s5_background_adaptive(self):
        assert seg.background_for(GRID_B, SegmentationVariant.S5_BG_ADAPTIVE) == 7
        objs = seg.segment_s5(GRID_B)
        assert len(objs) == 1
        assert objs[0].color == 0             # the two 0-cells become the object
        assert objs[0].size == 2
        # S1 on the same grid treats 0 as background -> the 7-ring object
        s1 = seg.segment_s1(GRID_B)
        assert len(s1) == 1 and s1[0].color == 7

    def test_s6_color_layers(self):
        objs = seg.segment_s6(GRID_A)
        assert len(objs) == 3                 # one object per color
        by_color = {o.color: o for o in objs}
        assert set(by_color) == {1, 2, 3}
        assert by_color[3].cells == frozenset({(3, 1), (4, 0), (4, 2)})

    @pytest.mark.parametrize("variant", list(SegmentationVariant))
    def test_partition_and_dense_ids(self, variant):
        bg = seg.background_for(GRID_A, variant)
        objs = seg.segment(GRID_A, variant, bg)
        data = GRID_A.to_numpy()
        nonbg = {(r, c) for r in range(5) for c in range(5)
                 if data[r, c] != bg}
        union = set()
        for o in objs:
            assert o.cells, "empty object"
            assert not (union & set(o.cells)), "overlapping objects"
            union |= set(o.cells)
        assert union == nonbg                 # objects cover all non-bg cells
        assert [o.id for o in objs] == list(range(len(objs)))  # dense ids

    def test_dispatch_table_complete(self):
        assert set(seg.SEGMENTERS) == set(SegmentationVariant)


# ---------------------------------------------------------------------------
# Coherence-based per-task choice on REAL dev tasks (Requirement 2.1.1)
# ---------------------------------------------------------------------------

class TestChoiceOnDevTasks:
    @pytest.mark.parametrize("tid", MOTION_TASKS + SHRINK_TASKS)
    def test_choice_is_coherent_and_sane(self, dev_tasks, tid):
        pairs = _pairs(dev_tasks[tid])
        result = seg.choose_segmentation(pairs)
        assert result.coherent, f"{tid}: no coherent variant found"
        assert result.pixel_coverage >= seg.COHERENCE_PIXEL_THRESHOLD
        assert len(result.input_objects) == len(pairs)
        assert len(result.output_objects) == len(pairs)
        assert len(result.backgrounds) == len(pairs)
        assert result.object_counts == [
            (len(i), len(o))
            for i, o in zip(result.input_objects, result.output_objects)]
        for (grid_in, grid_out), in_objs, out_objs, bg in zip(
                pairs, result.input_objects, result.output_objects,
                result.backgrounds):
            assert in_objs, f"{tid}: pair with zero input objects"
            for grid, objs in ((grid_in, in_objs), (grid_out, out_objs)):
                assert [o.id for o in objs] == list(range(len(objs)))
                for o in objs:
                    assert o.cells
                    for r, c in o.cells:
                        assert 0 <= r < grid.height and 0 <= c < grid.width
                    if not isinstance(o, MultiColorObject):
                        assert o.color != bg

    @pytest.mark.parametrize("tid", MOTION_TASKS)
    def test_motion_tasks_object_preserving_counts(self, dev_tasks, tid):
        result = seg.choose_segmentation(_pairs(dev_tasks[tid]))
        # motion/copy dev tasks keep a constant in/out count difference
        diffs = {n_out - n_in for n_in, n_out in result.object_counts}
        assert len(diffs) == 1

    @pytest.mark.parametrize("tid", SHRINK_TASKS)
    def test_shrink_tasks_single_output_object(self, dev_tasks, tid):
        result = seg.choose_segmentation(_pairs(dev_tasks[tid]))
        # shrink dev tasks: output is one selected object's crop
        assert {n_out for _, n_out in result.object_counts} == {1}

    def test_s3_probe_multicolor_objects(self, dev_tasks):
        """88a10436 (designated S3 probe): S3 is coherent and yields genuine
        multicolor objects with per-cell color maps."""
        pairs = _pairs(dev_tasks[S3_PROBE_TASK])
        result = seg.evaluate_variant(
            SegmentationVariant.S3_MULTICOLOR_4, pairs)
        assert result.coherent
        multi = [o for objs in result.input_objects for o in objs
                 if isinstance(o, MultiColorObject)
                 and len(o.color_multiset) > 1]
        assert multi, "no multicolor object found under S3"
        m = multi[0]
        assert set(m.cell_colors) == set(m.cells)
        assert all(col in m.color_multiset for col in m.cell_colors.values())

    def test_choice_deterministic(self, dev_tasks):
        pairs = _pairs(dev_tasks[MOTION_TASKS[0]])
        r1 = seg.choose_segmentation(pairs)
        r2 = seg.choose_segmentation(pairs)
        assert r1.variant is r2.variant
        assert r1.object_counts == r2.object_counts
        assert r1.pixel_coverage == r2.pixel_coverage

    def test_evaluate_variant_never_raises_on_degenerate(self):
        empty = Grid(np.zeros((3, 3), dtype=np.int32))
        result = seg.evaluate_variant(
            SegmentationVariant.S1_SAME_COLOR_4, [(empty, empty)])
        assert result.coherent is False


# ---------------------------------------------------------------------------
# Feature tables on REAL dev tasks: complete and typed
# ---------------------------------------------------------------------------

def _assert_kind_type(name, kind, value):
    if kind is FeatureKind.BOOL:
        assert isinstance(value, bool), (name, value)
    elif kind is FeatureKind.SCALAR:
        assert isinstance(value, (int, float)) and \
            not isinstance(value, bool), (name, value)
    elif kind is FeatureKind.COLOR:
        assert isinstance(value, int) and not isinstance(value, bool), \
            (name, value)
        assert -1 <= value <= 9, (name, value)
    elif kind is FeatureKind.VECTOR:
        assert isinstance(value, tuple) and len(value) == 2 and \
            all(isinstance(v, int) for v in value), (name, value)
    elif kind is FeatureKind.CATEGORICAL:
        assert isinstance(value, (str, tuple)), (name, value)


class TestFeatureTablesOnDevTasks:
    @pytest.mark.parametrize("tid", ALL_TASKS)
    def test_table_complete_and_typed(self, dev_tasks, tid):
        pairs = _pairs(dev_tasks[tid])
        result = seg.choose_segmentation(pairs)
        kinds = {name: feat.get_feature(name).kind
                 for name in feat.FEATURE_REGISTRY}
        for pair_index, (grid_in, _) in enumerate(pairs):
            objs = result.input_objects[pair_index]
            table = feat.compute_feature_table(
                objs, grid_in, result.backgrounds[pair_index],
                pair_index=pair_index, role="input")
            assert len(table.rows) == len(objs)
            assert table.feature_names == sorted(feat.FEATURE_REGISTRY)
            for row in table.rows:
                assert row.pair_index == pair_index
                assert row.role == "input"
                present = set(row.intrinsic) | set(row.relational)
                assert present == set(feat.FEATURE_REGISTRY), \
                    f"{tid}: incomplete row"
                for name in feat.FEATURE_REGISTRY:
                    _assert_kind_type(name, kinds[name], row.value(name))

    def test_rows_json_serializable(self, dev_tasks):
        pairs = _pairs(dev_tasks[MOTION_TASKS[0]])
        result = seg.choose_segmentation(pairs)
        table = feat.compute_feature_table(
            result.input_objects[0], pairs[0][0], result.backgrounds[0])
        for row in table.rows:
            json.dumps(row.to_dict())  # must not raise

    def test_relations_boolean_on_real_objects(self, dev_tasks):
        pairs = _pairs(dev_tasks[MOTION_TASKS[0]])
        result = seg.choose_segmentation(pairs)
        objs = result.input_objects[0]
        ctx = _ctx(pairs[0][0], objs, result.backgrounds[0])
        for name, spec in feat.RELATION_REGISTRY.items():
            for a in objs:
                for b in objs:
                    if a.id == b.id:
                        continue
                    v = spec.fn(a, b, ctx)
                    assert isinstance(v, bool), name


# ---------------------------------------------------------------------------
# Feature semantics on hand-built grids (known ground truth)
# ---------------------------------------------------------------------------

class TestFeatureSemantics:
    @pytest.fixture(scope="class")
    def grid_a(self):
        objs = _by_first_cell(seg.segment_s1(GRID_A))
        # obj0: color1 L (3 cells); obj1: color2 L (3 cells);
        # obj2: 3@(3,1); obj3: 3@(4,0); obj4: 3@(4,2)
        ctx = _ctx(GRID_A, objs)
        return objs, ctx

    def _v(self, name, obj, ctx):
        return feat.get_feature(name).fn(obj, ctx)

    def test_intrinsic(self, grid_a):
        objs, ctx = grid_a
        o0 = objs[0]
        assert self._v("color", o0, ctx) == 1
        assert self._v("size", o0, ctx) == 3
        assert self._v("bbox", o0, ctx) == (1, 0, 3, 2)
        assert self._v("bbox_height", o0, ctx) == 2
        assert self._v("bbox_width", o0, ctx) == 2
        assert self._v("centroid", o0, ctx) == (2, 0)
        assert self._v("density", o0, ctx) == 0.75
        assert self._v("aspect_ratio", o0, ctx) == 1.0
        assert self._v("is_rectangle", o0, ctx) is False
        assert self._v("is_line", o0, ctx) is False
        assert self._v("is_line", objs[2], ctx) is True   # 1x1 singleton
        assert self._v("is_rectangle", objs[2], ctx) is True

    def test_touches_border(self, grid_a):
        objs, ctx = grid_a
        assert self._v("touches_border", objs[0], ctx) is True   # col 0
        assert self._v("touches_border", objs[2], ctx) is False  # interior
        assert self._v("touches_border", objs[3], ctx) is True   # bottom row

    def test_shape_signatures(self, grid_a):
        objs, ctx = grid_a
        # the two L-trominoes are congruent under rotation, not identical
        assert self._v("shape_sig", objs[0], ctx) != \
            self._v("shape_sig", objs[1], ctx)
        assert self._v("shape_sig_normalized", objs[0], ctx) == \
            self._v("shape_sig_normalized", objs[1], ctx)
        # all singletons share both signatures
        assert self._v("shape_sig", objs[2], ctx) == \
            self._v("shape_sig", objs[3], ctx)

    def test_rank_features(self, grid_a):
        objs, ctx = grid_a
        assert self._v("size_rank", objs[0], ctx) == 0        # size 3 largest
        assert self._v("size_rank", objs[2], ctx) == 1
        assert self._v("size_rank_reversed", objs[0], ctx) == 1
        assert self._v("size_rank_reversed", objs[2], ctx) == 0
        assert self._v("is_unique_size", objs[0], ctx) is False  # 2 of size 3
        assert self._v("is_unique_color", objs[0], ctx) is True
        assert self._v("is_unique_color", objs[2], ctx) is False
        assert self._v("is_unique_shape", objs[0], ctx) is False  # obj1 congruent
        assert self._v("is_majority_shape", objs[2], ctx) is True
        assert self._v("is_majority_shape", objs[0], ctx) is False
        assert self._v("count_of_same_shape", objs[0], ctx) == 2
        assert self._v("count_of_same_shape", objs[2], ctx) == 3
        assert self._v("count_of_same_color", objs[2], ctx) == 3
        assert self._v("count_of_same_color", objs[0], ctx) == 1
        assert self._v("color_frequency_rank", objs[2], ctx) == 0
        assert self._v("color_frequency_rank", objs[0], ctx) == 1

    def test_derived_relational(self, grid_a):
        objs, ctx = grid_a
        # nearest to (3,1): tie between (4,0)/(4,2) -> smaller id -> (4,0)
        assert self._v("vector_to_nearest", objs[2], ctx) == (1, -1)
        assert self._v("nearest_object_color", objs[2], ctx) == 3
        # (4,0) shares column band only with obj0 (cols 0-1): 1 empty row
        assert self._v("gap_to_nearest_row", objs[3], ctx) == 1
        # (4,0) shares row band with (4,2): 1 empty column between
        assert self._v("gap_to_nearest_col", objs[3], ctx) == 1
        # (3,1) shares no row band -> sentinel
        assert self._v("gap_to_nearest_col", objs[2], ctx) == \
            feat.UNDEFINED_SCALAR
        assert self._v("aligned_row_count", objs[3], ctx) == 1  # (4,2)
        assert self._v("aligned_col_count", objs[3], ctx) == 1  # obj0

    def test_totality_single_object(self):
        objs = seg.segment_s1(GRID_D)         # one ring object, alone
        ctx = _ctx(GRID_D, objs)
        o = objs[0]
        assert self._v("vector_to_nearest", o, ctx) == feat.UNDEFINED_VECTOR
        assert self._v("nearest_object_color", o, ctx) == feat.UNDEFINED_COLOR
        assert self._v("gap_to_nearest_row", o, ctx) == feat.UNDEFINED_SCALAR
        assert self._v("gap_to_nearest_col", o, ctx) == feat.UNDEFINED_SCALAR
        assert self._v("hole_count", o, ctx) == 1
        assert self._v("has_hole", o, ctx) is True

    def test_containment(self):
        objs = _by_first_cell(seg.segment_s1(GRID_C))
        ring, six = objs[0], objs[1]
        assert ring.color == 4 and six.color == 6
        ctx = _ctx(GRID_C, objs)
        assert self._v("is_container", ring, ctx) is True
        assert self._v("is_contained", ring, ctx) is False
        assert self._v("is_container", six, ctx) is False
        assert self._v("is_contained", six, ctx) is True
        assert self._v("containment_depth", six, ctx) == 1
        assert self._v("containment_depth", ring, ctx) == 0

    def test_relations_inside_is_inverse_of_contains(self):
        objs = _by_first_cell(seg.segment_s1(GRID_C))
        ctx = _ctx(GRID_C, objs)
        contains = feat.get_relation("contains").fn
        inside = feat.get_relation("inside").fn
        for a in objs:
            for b in objs:
                if a.id == b.id:
                    continue
                assert inside(a, b, ctx) == contains(b, a, ctx)
        ring, six = objs[0], objs[1]
        assert contains(ring, six, ctx) is True
        assert inside(six, ring, ctx) is True
        assert feat.get_relation("adjacent").fn(ring, six, ctx) is True

    def test_multicolor_object_features_total(self):
        """S3 objects (MultiColorObject) go through every feature without
        raising; color = majority color."""
        objs = seg.segment_s3(GRID_A)
        ctx = _ctx(GRID_A, objs)
        merged = next(o for o in objs if isinstance(o, MultiColorObject)
                      and len(o.color_multiset) > 1)
        row = feat.compute_features(merged, ctx)
        assert row.value("color") == 1
        assert row.value("size") == 4
        present = set(row.intrinsic) | set(row.relational)
        assert present == set(feat.FEATURE_REGISTRY)
