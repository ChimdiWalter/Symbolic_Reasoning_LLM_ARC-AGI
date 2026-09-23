"""Tests for the round-1 generic-fix primitives (failure-analysis driven).

Covers:
- VecExpr step_toward / slide_vector (relational motion vectors),
- ColorExpr feature_map (induced ordinal recolor maps),
- AlignExpr symbol leaf + COPY 'targets' (copy-at-markers) and 'period'
  (periodic repetition until border) placement modes,
- same_shape_normalized relation,
- fold-deterministic selector ranking (@rank tests beat literal thresholds),
- end-to-end induction of a recolor-by-size-rank task (feature_map path).

Every primitive is generic (no task constants at definition time) and
justified by >= 2 dev/sample tasks in the 2026-07-02 failure analysis.
"""
from __future__ import annotations

import numpy as np

from geocat_arc.perception.grid import Grid

from geocat_arc.object_reasoning import features as F
from geocat_arc.object_reasoning.actions import ObjectCanvas, apply_action, render
from geocat_arc.object_reasoning.expressions import (
    AlignExpr,
    ColorExpr,
    EvalContext,
    EvalError,
    PredExpr,
    RefExpr,
    ScalarExpr,
    VecExpr,
    evaluate,
    make_feature_map,
    parameter_class_of,
)
from geocat_arc.object_reasoning.inducer import (
    InductionConfig,
    _copy_period_candidates,
    induce_program,
)
from geocat_arc.object_reasoning.segmentation import segment_s1
from geocat_arc.object_reasoning.types import (
    ActionRule,
    DeltaType,
    Expr,
    GridContext,
    ObjectDelta,
    ParameterClass,
    to_grid_pairs,
)

F.register_builtin_features()


def _ctx(grid_data, background=0):
    grid = Grid(np.array(grid_data))
    objs = segment_s1(grid, background)
    gctx = GridContext(grid=grid, objects=objs, background=background)
    return grid, objs, gctx


def _ectx(obj, gctx):
    return EvalContext(obj=obj, grid_ctx=gctx)


class TestStepToward:
    def test_diagonal_sign_step(self):
        # object of 3s at top-left, target 4 at bottom-right
        data = [[3, 0, 0, 0],
                [0, 0, 0, 0],
                [0, 0, 0, 0],
                [0, 0, 0, 4]]
        _, objs, gctx = _ctx(data)
        mover = next(o for o in objs if o.color == 3)
        expr = VecExpr(op="step_toward",
                       args=(RefExpr(op="nearest_object_of_color", args=(4,)),))
        assert evaluate(expr, mover, _ectx(mover, gctx)) == (1, 1)
        assert parameter_class_of(expr) is ParameterClass.RELATIONAL

    def test_axis_aligned_and_zero(self):
        data = [[3, 0, 0, 4]]
        _, objs, gctx = _ctx(data)
        mover = next(o for o in objs if o.color == 3)
        expr = VecExpr(op="step_toward",
                       args=(RefExpr(op="nearest_object_of_color", args=(4,)),))
        assert evaluate(expr, mover, _ectx(mover, gctx)) == (0, 1)


class TestSlideVector:
    def test_blocked_by_object(self):
        # 3 falls down, blocked by the 5-bar two rows below
        data = [[3, 0],
                [0, 0],
                [0, 0],
                [5, 5]]
        _, objs, gctx = _ctx(data)
        mover = next(o for o in objs if o.color == 3)
        expr = VecExpr(op="slide_vector", args=("down",))
        assert evaluate(expr, mover, _ectx(mover, gctx)) == (2, 0)
        assert parameter_class_of(expr) is ParameterClass.RELATIONAL

    def test_blocked_by_border(self):
        data = [[0, 0, 3, 0, 0]]
        _, objs, gctx = _ctx(data)
        mover = objs[0]
        expr = VecExpr(op="slide_vector", args=("right",))
        assert evaluate(expr, mover, _ectx(mover, gctx)) == (0, 2)
        expr = VecExpr(op="slide_vector", args=("left",))
        assert evaluate(expr, mover, _ectx(mover, gctx)) == (0, -2)

    def test_already_blocked_is_zero(self):
        data = [[3, 5]]
        _, objs, gctx = _ctx(data)
        mover = next(o for o in objs if o.color == 3)
        expr = VecExpr(op="slide_vector", args=("right",))
        assert evaluate(expr, mover, _ectx(mover, gctx)) == (0, 0)


class TestFeatureMap:
    def test_evaluate_and_class(self):
        # sizes 1 and 3 -> size_rank 1 and 0
        data = [[3, 0, 0, 0, 0],
                [0, 0, 5, 5, 5]]
        _, objs, gctx = _ctx(data)
        small = next(o for o in objs if o.size == 1)
        large = next(o for o in objs if o.size == 3)
        expr = make_feature_map("size_rank", {0: 1, 1: 2})
        assert evaluate(expr, large, _ectx(large, gctx)) == 1
        assert evaluate(expr, small, _ectx(small, gctx)) == 2
        assert parameter_class_of(expr) is ParameterClass.INDUCED_MAP

    def test_missing_value_is_evalerror(self):
        data = [[3]]
        _, objs, gctx = _ctx(data)
        expr = make_feature_map("size_rank", {7: 1})
        try:
            evaluate(expr, objs[0], _ectx(objs[0], gctx))
            assert False, "expected EvalError"
        except EvalError:
            pass

    def test_json_round_trip(self):
        expr = make_feature_map("size_rank", {0: 1, 1: 2})
        assert Expr.from_dict(expr.to_dict()) == expr


class TestAlignExpr:
    def test_round_trip_and_evaluate(self):
        data = [[3]]
        _, objs, gctx = _ctx(data)
        for align in ("bbox_center", "bbox_origin"):
            expr = AlignExpr(op="const", args=(align,))
            assert evaluate(expr, objs[0], _ectx(objs[0], gctx)) == align
            assert Expr.from_dict(expr.to_dict()) == expr


class TestCopyModes:
    def test_copy_at_markers_center(self):
        # source 2x2 of 3s; markers: two 5-dots; copies centered on markers
        data = [[3, 3, 0, 0, 0, 0],
                [3, 3, 0, 0, 0, 0],
                [0, 0, 0, 5, 0, 0],
                [0, 0, 0, 0, 0, 5]]
        grid, objs, gctx = _ctx(data)
        src = next(o for o in objs if o.color == 3)
        action = ActionRule(
            delta_type=DeltaType.COPY,
            params={"targets": PredExpr(op="test", args=("color", "==", 5)),
                    "align": AlignExpr(op="const", args=("bbox_origin",))})
        canvas = ObjectCanvas(objects=[], height=4, width=6, background=0,
                              source_grid=grid)
        produced = apply_action(canvas, src, action, _ectx(src, gctx))
        # original + one copy per marker
        assert len(produced) == 3
        cells = set().union(*(o.cells for o in produced))
        assert (2, 3) in cells and (3, 4) in cells  # copy at first marker
        assert (3, 5) in cells                       # copy at second marker

    def test_copy_at_markers_no_match_is_evalerror(self):
        data = [[3, 0]]
        grid, objs, gctx = _ctx(data)
        action = ActionRule(
            delta_type=DeltaType.COPY,
            params={"targets": PredExpr(op="test", args=("color", "==", 5))})
        canvas = ObjectCanvas(objects=[], height=1, width=2, background=0,
                              source_grid=grid)
        try:
            apply_action(canvas, objs[0], action, _ectx(objs[0], gctx))
            assert False, "expected EvalError"
        except EvalError:
            pass

    def test_copy_periodic_until_border(self):
        data = [[3, 0, 0, 0, 0, 0, 0]]
        grid, objs, gctx = _ctx(data)
        action = ActionRule(
            delta_type=DeltaType.COPY,
            params={"period": VecExpr(op="const", args=(0, 2))})
        canvas = ObjectCanvas(objects=[], height=1, width=7, background=0,
                              source_grid=grid)
        produced = apply_action(canvas, objs[0], action, _ectx(objs[0], gctx))
        canvas.objects.extend(produced)
        out = render(canvas).to_numpy()
        assert out.tolist() == [[3, 0, 3, 0, 3, 0, 3]]

    def test_copy_periodic_keep_original_false(self):
        data = [[3, 0, 0, 0]]
        grid, objs, gctx = _ctx(data)
        action = ActionRule(
            delta_type=DeltaType.COPY,
            params={"period": VecExpr(op="const", args=(0, 2)),
                    "keep_original": ScalarExpr(op="const", args=(0,))})
        canvas = ObjectCanvas(objects=[], height=1, width=4, background=0,
                              source_grid=grid)
        produced = apply_action(canvas, objs[0], action, _ectx(objs[0], gctx))
        canvas.objects.extend(produced)
        out = render(canvas).to_numpy()
        assert out.tolist() == [[0, 0, 3, 0]]


class TestAlignVector:
    def test_vertical_and_horizontal(self):
        data = [[0, 0, 0, 0, 1],
                [3, 3, 0, 0, 1],
                [3, 3, 0, 0, 0]]
        _, objs, gctx = _ctx(data)
        mover = next(o for o in objs if o.color == 3)
        ref = RefExpr(op="nearest_object_of_color", args=(1,))
        v = VecExpr(op="align_vector", args=(ref, "vertical"))
        assert evaluate(v, mover, _ectx(mover, gctx)) == (-1, 0)
        h = VecExpr(op="align_vector", args=(ref, "horizontal"))
        assert evaluate(h, mover, _ectx(mover, gctx)) == (0, 4)
        assert parameter_class_of(v) is ParameterClass.RELATIONAL

    def test_json_round_trip(self):
        ref = RefExpr(op="nearest_object_of_color", args=(1,))
        v = VecExpr(op="align_vector", args=(ref, "vertical"))
        assert Expr.from_dict(v.to_dict()) == v


class TestEnclosedRegions:
    def test_multi_cell_hole_counted(self):
        # 3x5 rectangle with a 1x3 interior hole: perception obj.holes
        # misses it; enclosed_region_count must see exactly 1 region.
        data = [[3, 3, 3, 3, 3],
                [3, 0, 0, 0, 3],
                [3, 3, 3, 3, 3]]
        _, objs, gctx = _ctx(data)
        fn = F.FEATURE_REGISTRY["enclosed_region_count"].fn
        assert fn(objs[0], gctx) == 1
        assert F.FEATURE_REGISTRY["has_enclosed_region"].fn(objs[0], gctx)

    def test_background_agnostic(self):
        # ring of 1s on background 9: interior cells are 9, not 0 — the
        # enclosed region must still be detected (mask topology only).
        data = [[9, 9, 9, 9, 9],
                [9, 1, 1, 1, 9],
                [9, 1, 9, 1, 9],
                [9, 1, 1, 1, 9]]
        grid = Grid(np.array(data))
        objs = segment_s1(grid, 9)
        gctx = GridContext(grid=grid, objects=objs, background=9)
        ring = next(o for o in objs if o.color == 1)
        assert F.FEATURE_REGISTRY["enclosed_region_count"].fn(ring, gctx) == 1

    def test_open_shape_is_zero(self):
        data = [[3, 3, 3],
                [3, 0, 0],
                [3, 3, 3]]
        _, objs, gctx = _ctx(data)
        assert F.FEATURE_REGISTRY["enclosed_region_count"].fn(objs[0], gctx) == 0


class TestSameShapeNormalized:
    def test_registered_and_rotation_invariant(self):
        assert "same_shape_normalized" in F.RELATION_REGISTRY
        # L-tromino and its 90-degree rotation
        data = [[3, 0, 0, 0, 4, 4],
                [3, 3, 0, 0, 4, 0]]
        _, objs, gctx = _ctx(data)
        a = next(o for o in objs if o.color == 3)
        b = next(o for o in objs if o.color == 4)
        spec = F.RELATION_REGISTRY["same_shape_normalized"]
        assert spec.fn(a, b, gctx) is True


class TestSelectorRankPreference:
    def test_rank_test_beats_literal_threshold(self):
        """@rank tests score a small constant (parameter-free), literal
        thresholds keep feature cardinality — the fold-determinism fix."""
        from geocat_arc.object_reasoning.inducer import (
            _pred_generalization_score, build_labeled_table)
        from geocat_arc.object_reasoning.segmentation import evaluate_variant
        from geocat_arc.object_reasoning.types import SegmentationVariant
        pairs = to_grid_pairs([
            (np.array([[3, 0, 0], [0, 0, 0], [5, 5, 5]]),
             np.array([[3, 0, 0], [0, 0, 0], [5, 5, 5]])),
            (np.array([[0, 3, 0], [5, 5, 0], [5, 5, 0]]),
             np.array([[0, 3, 0], [5, 5, 0], [5, 5, 0]])),
        ])
        seg = evaluate_variant(SegmentationVariant.S1_SAME_COLOR_4, pairs)
        table, _ = build_labeled_table(seg, pairs)
        rank_pred = PredExpr(op="test", args=("size", "==", "@rank_max"))
        lit_pred = PredExpr(op="test", args=("size", ">", 2))
        assert _pred_generalization_score(rank_pred, table) \
            < _pred_generalization_score(lit_pred, table)


class TestPeriodMining:
    def test_consecutive_diffs_and_min_placement(self):
        members = {
            (0, 0): ObjectDelta(0, DeltaType.COPY, 0, [1, 2, 3],
                                {"k": 3, "placements": [[2, 0], [4, 0], [6, 0]]}),
            (1, 0): ObjectDelta(1, DeltaType.COPY, 0, [1],
                                {"k": 1, "placements": [[-3, 0]]}),
        }
        periods = _copy_period_candidates(members)
        assert (2, 0) in periods       # consecutive diff
        assert (-3, 0) in periods      # min-L1 placement (negative direction)


class TestEndToEndInduction:
    def test_recolor_by_size_rank(self):
        """Ordinal recolor: largest -> 1, middle -> 2, smallest -> 3 (colors
        differ per object count, only rank explains it) — feature_map path.
        Three pairs so the LOO gate is exercised for real."""
        def make_pair(positions):
            # positions: list of (row, col, length) horizontal bars of color 5
            g = np.zeros((7, 9), dtype=int)
            o = np.zeros((7, 9), dtype=int)
            ranks = sorted(range(len(positions)),
                           key=lambda i: -positions[i][2])
            colors = {}
            for rank, i in enumerate(ranks):
                colors[i] = rank + 1
            for i, (r, c, ln) in enumerate(positions):
                g[r, c:c + ln] = 5
                o[r, c:c + ln] = colors[i]
            return g, o

        pairs = [
            make_pair([(0, 0, 5), (2, 1, 3), (4, 2, 1)]),
            make_pair([(1, 3, 4), (3, 0, 2), (5, 5, 1)]),
            make_pair([(0, 2, 6), (2, 0, 3), (6, 1, 2)]),
        ]
        result = induce_program(to_grid_pairs(pairs),
                                InductionConfig(budget_s=30.0))
        assert result.accepted, (result.failure_stage, result.loo)
        assert result.loo is not None and result.loo.all_passed

    def test_gravity_with_obstacle(self):
        """Objects slide down until blocked by a floor bar (slide_vector):
        the fall distance differs per pair, so no constant vector fits."""
        def make_pair(col, start_row, floor_row):
            g = np.zeros((8, 5), dtype=int)
            o = np.zeros((8, 5), dtype=int)
            g[start_row, col] = 3
            o[floor_row - 1, col] = 3
            g[floor_row, :] = 5
            o[floor_row, :] = 5
            return g, o

        # dot never touches a border in the input (so no border feature can
        # coincidentally separate the pairs); fall distances differ.
        pairs = [make_pair(1, 1, 6), make_pair(3, 2, 7), make_pair(2, 1, 5)]
        result = induce_program(to_grid_pairs(pairs),
                                InductionConfig(budget_s=30.0))
        assert result.accepted, (result.failure_stage, result.loo)
