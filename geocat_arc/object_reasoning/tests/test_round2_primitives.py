"""Tests for the round-2 generic-fix primitives (failure-analysis driven).

Covers:
- VecExpr mirror_vector (grid-frame position mirror; e21a174a, 8ee62060),
- mirror_rows/mirror_cols correspondence profiles (reference-frame matching),
- RefExpr nearest_shape_twin + PAINT delta/action (template stamping;
  e76a88a6, e734a0e8) and the is_multicolor feature,
- COPY placement lattices: multi-ray ("ray<i>"; 623ea044) and base offsets
  + period ("offset<i>" + "period"; 3ac3eb23) with MDL-ordered mining,
- RegionExpr separator_block_self + block-crop shrink form (2dc579da,
  c444b776 partition family),
- CROP_TO tiling (tile_h/tile_w; 28bf18c6, 8597cfd7),
- tier 1b KEEP-absorption (identity member of a parameterized group;
  8ee62060 center object),
- end-to-end induction incl. LOO for a mirror-reversal task and a
  tiled-crop shrink task.

Every primitive is generic (no task constants at definition time) and
justified by >= 2 dev/sample tasks in the failure analysis.
"""
from __future__ import annotations

import numpy as np

from geocat_arc.perception.grid import Grid

from geocat_arc.object_reasoning import features as F
from geocat_arc.object_reasoning.actions import (
    ObjectCanvas,
    apply_action,
    render_program,
)
from geocat_arc.object_reasoning.correspondence import (
    extract_deltas,
    match_pair,
    _minimal_delta,
)
from geocat_arc.object_reasoning.expressions import (
    EvalContext,
    EvalError,
    PredExpr,
    RefExpr,
    RegionExpr,
    ScalarExpr,
    VecExpr,
    evaluate,
    parameter_class_of,
)
from geocat_arc.object_reasoning.inducer import (
    InductionConfig,
    _copy_lattice_candidates,
    induce_program,
)
from geocat_arc.object_reasoning.segmentation import segment_s1, segment_s3
from geocat_arc.object_reasoning.types import (
    ActionRule,
    DeltaType,
    GridContext,
    ObjectDelta,
    ParameterClass,
    to_grid_pairs,
)

F.register_builtin_features()


def _ctx(grid_data, background=0, segmenter=segment_s1):
    grid = Grid(np.array(grid_data))
    objs = segmenter(grid, background)
    gctx = GridContext(grid=grid, objects=objs, background=background)
    return grid, objs, gctx


def _obj_at(objs, r, c):
    return next(o for o in objs if (r, c) in o.cells)


# ---------------------------------------------------------------------------
# mirror_vector
# ---------------------------------------------------------------------------

class TestMirrorVector:
    def test_horizontal_mirrors_row_position(self):
        _, objs, gctx = _ctx([[0, 0, 0],
                              [5, 0, 0],
                              [0, 0, 0],
                              [0, 0, 0]])
        obj = objs[0]  # bbox rows [1,2)
        ectx = EvalContext(obj=obj, grid_ctx=gctx)
        v = evaluate(VecExpr(op="mirror_vector", args=("horizontal",)),
                     obj, ectx)
        assert v == (4 - 2 - 1, 0) == (1, 0)   # new r0 = H - r1 = 2

    def test_vertical_mirrors_col_position(self):
        _, objs, gctx = _ctx([[0, 5, 5, 0, 0]])
        obj = objs[0]  # cols [1,3)
        ectx = EvalContext(obj=obj, grid_ctx=gctx)
        v = evaluate(VecExpr(op="mirror_vector", args=("vertical",)),
                     obj, ectx)
        assert v == (0, 5 - 3 - 1) == (0, 1)   # new c0 = W - c1 = 2

    def test_center_object_gets_zero_vector(self):
        _, objs, gctx = _ctx([[0], [5], [0]])
        obj = objs[0]
        ectx = EvalContext(obj=obj, grid_ctx=gctx)
        assert evaluate(VecExpr(op="mirror_vector", args=("horizontal",)),
                        obj, ectx) == (0, 0)

    def test_relational_class(self):
        assert parameter_class_of(
            VecExpr(op="mirror_vector", args=("horizontal",))) \
            is ParameterClass.RELATIONAL


# ---------------------------------------------------------------------------
# mirror correspondence profiles
# ---------------------------------------------------------------------------

class TestMirrorProfiles:
    def test_mirror_rows_alternative_reverses_pairing(self):
        # three identical shapes; output = vertical order reversal
        gin = Grid(np.array([[1, 1, 0, 0],
                             [0, 0, 0, 0],
                             [1, 1, 0, 0],
                             [0, 0, 0, 0],
                             [0, 0, 1, 1]]))
        gout = Grid(np.array([[0, 0, 1, 1],
                              [0, 0, 0, 0],
                              [1, 1, 0, 0],
                              [0, 0, 0, 0],
                              [1, 1, 0, 0]]))
        in_objs = segment_s1(gin, 0)
        out_objs = segment_s1(gout, 0)
        alts = match_pair(in_objs, out_objs, gin, gout, 0)
        by_profile = {a.weights_profile: a for a in alts}
        assert "mirror_rows" in by_profile
        mirror = by_profile["mirror_rows"]
        # top-left input object must match the bottom output object
        top_in = _obj_at(in_objs, 0, 0)
        bottom_out = _obj_at(out_objs, 4, 0)
        assert (top_in.id, bottom_out.id) in \
            {(i, o) for i, o, _ in mirror.matches}


# ---------------------------------------------------------------------------
# PAINT (template stamping) + nearest_shape_twin + is_multicolor
# ---------------------------------------------------------------------------

class TestPaint:
    def test_minimal_delta_same_cells_nonuniform_is_paint(self):
        gin, in_objs, _ = _ctx([[5, 5, 5]])
        gout, out_objs, _ = _ctx([[2, 4, 2]], segmenter=segment_s3)
        dtype, params, residual = _minimal_delta(in_objs[0], out_objs[0], 0)
        assert dtype is DeltaType.PAINT
        assert residual == 0
        assert params["pattern"] == [[[0, 0], 2], [[0, 1], 4], [[0, 2], 2]]

    def test_apply_paint_copies_source_pattern(self):
        grid, objs, gctx = _ctx([[2, 4, 2, 0, 5, 5, 5]],
                                segmenter=segment_s3)
        template = _obj_at(objs, 0, 0)
        gray = _obj_at(objs, 0, 4)
        ectx = EvalContext(obj=gray, grid_ctx=gctx)
        action = ActionRule(
            delta_type=DeltaType.PAINT,
            params={"source": RefExpr(op="nearest_shape_twin")})
        canvas = ObjectCanvas(objects=[], height=1, width=7, background=0,
                              source_grid=grid)
        produced = apply_action(canvas, gray, action, ectx)
        assert len(produced) == 1
        from geocat_arc.object_reasoning.types import cell_colors_of
        assert cell_colors_of(produced[0]) == {(0, 4): 2, (0, 5): 4, (0, 6): 2}
        del template

    def test_apply_paint_mask_mismatch_is_eval_error(self):
        grid, objs, gctx = _ctx([[2, 2, 0, 0, 5]], segmenter=segment_s1)
        gray = _obj_at(objs, 0, 4)
        ectx = EvalContext(obj=gray, grid_ctx=gctx)
        action = ActionRule(
            delta_type=DeltaType.PAINT,
            params={"source": RefExpr(op="nearest_object",
                                      args=(PredExpr(op="true"),))})
        canvas = ObjectCanvas(objects=[], height=1, width=5, background=0,
                              source_grid=grid)
        try:
            apply_action(canvas, gray, action, ectx)
            assert False, "expected EvalError"
        except EvalError:
            pass

    def test_nearest_shape_twin_requires_candidate(self):
        _, objs, gctx = _ctx([[5, 0, 0], [0, 0, 2], [0, 0, 2]])
        single = _obj_at(objs, 0, 0)
        ectx = EvalContext(obj=single, grid_ctx=gctx)
        try:
            evaluate(RefExpr(op="nearest_shape_twin"), single, ectx)
            assert False, "expected EvalError"
        except EvalError:
            pass

    def test_is_multicolor_feature(self):
        _, objs, gctx = _ctx([[2, 4, 0, 5, 5]], segmenter=segment_s3)
        multi = _obj_at(objs, 0, 0)
        mono = _obj_at(objs, 0, 3)
        assert F.get_feature("is_multicolor").fn(multi, gctx) is True
        assert F.get_feature("is_multicolor").fn(mono, gctx) is False


# ---------------------------------------------------------------------------
# COPY placement lattices
# ---------------------------------------------------------------------------

def _copy_cells(grid_data, action, seed_rc):
    grid, objs, gctx = _ctx(grid_data)
    obj = _obj_at(objs, *seed_rc)
    ectx = EvalContext(obj=obj, grid_ctx=gctx)
    canvas = ObjectCanvas(objects=[], height=grid.height, width=grid.width,
                          background=0, source_grid=grid)
    produced = apply_action(canvas, obj, action, ectx)
    cells = set()
    for o in produced:
        cells |= set(o.cells)
    return cells


class TestCopyLattices:
    def test_rays_emit_diagonal_star(self):
        action = ActionRule(
            delta_type=DeltaType.COPY,
            params={f"ray{i}": VecExpr(op="const", args=v)
                    for i, v in enumerate([(-1, -1), (-1, 1), (1, -1), (1, 1)])})
        cells = _copy_cells([[0] * 5 for _ in range(5)]
                            [:2] + [[0, 0, 4, 0, 0]] + [[0] * 5, [0] * 5],
                            action, (2, 2))
        assert cells == {(2, 2), (1, 1), (0, 0), (1, 3), (0, 4),
                         (3, 1), (4, 0), (3, 3), (4, 4)}

    def test_offsets_plus_period_zigzag(self):
        action = ActionRule(
            delta_type=DeltaType.COPY,
            params={"offset0": VecExpr(op="const", args=(1, -1)),
                    "offset1": VecExpr(op="const", args=(1, 1)),
                    "period": VecExpr(op="const", args=(2, 0))})
        grid_data = [[0, 4, 0]] + [[0, 0, 0]] * 5
        cells = _copy_cells(grid_data, action, (0, 1))
        assert cells == {(0, 1), (2, 1), (4, 1),
                         (1, 0), (3, 0), (5, 0),
                         (1, 2), (3, 2), (5, 2)}

    def test_offsets_only(self):
        action = ActionRule(
            delta_type=DeltaType.COPY,
            params={"offset0": VecExpr(op="const", args=(0, 2))})
        cells = _copy_cells([[4, 0, 0]], action, (0, 0))
        assert cells == {(0, 0), (0, 2)}

    def test_lattice_mining_rays_and_mdl_order(self):
        # star placements -> a rays proposal exists
        placements = [[-1, -1], [-2, -2], [-1, 1], [1, -1], [1, 1], [2, 2]]
        members = {(0, 0): ObjectDelta(0, DeltaType.COPY, 0, [1],
                                       {"k": len(placements),
                                        "placements": placements})}
        props = _copy_lattice_candidates(members)
        ray_props = [p for p in props if any(k.startswith("ray") for k in p)]
        assert ray_props
        assert sorted(ray_props[0].values()) == \
            [(-1, -1), (-1, 1), (1, -1), (1, 1)]
        # MDL: proposals are ordered by number of lattice vectors
        sizes = [len(p) for p in props]
        assert sizes == sorted(sizes)

    def test_lattice_mining_offsets_period(self):
        placements = [[1, -1], [1, 1], [2, 0], [3, -1], [3, 1], [4, 0],
                      [5, -1], [5, 1]]
        members = {(0, 0): ObjectDelta(0, DeltaType.COPY, 0, [1],
                                       {"k": len(placements),
                                        "placements": placements})}
        props = _copy_lattice_candidates(members)
        assert any(p.get("period") == (2, 0)
                   and sorted(v for k, v in p.items() if k.startswith("offset"))
                   == [(1, -1), (1, 1)]
                   for p in props)


# ---------------------------------------------------------------------------
# separator_block_self + CROP_TO tiling
# ---------------------------------------------------------------------------

class TestRegionsAndTiling:
    def test_separator_block_self(self):
        # column 2 is a uniform separator; object in the right block
        _, objs, gctx = _ctx([[4, 4, 1, 5, 0],
                              [4, 4, 1, 0, 0],
                              [0, 0, 1, 0, 5]])
        obj = _obj_at(objs, 0, 3)
        ectx = EvalContext(obj=obj, grid_ctx=gctx)
        region = evaluate(RegionExpr(op="separator_block_self"), obj, ectx)
        assert region == (0, 3, 3, 5)

    def test_separator_block_self_spanning_is_error(self):
        _, objs, gctx = _ctx([[4, 4, 1, 5, 0],
                              [4, 4, 1, 0, 0],
                              [0, 0, 1, 0, 5]])
        sep = _obj_at(objs, 0, 2)   # the separator line spans blocks
        ectx = EvalContext(obj=sep, grid_ctx=gctx)
        try:
            evaluate(RegionExpr(op="separator_block_self"), sep, ectx)
            assert False, "expected EvalError"
        except EvalError:
            pass

    def test_crop_to_tiling_renders_repeated_crop(self):
        from geocat_arc.object_reasoning.types import (
            ObjectProgram, ObjectRule, OutputSpec, SelectorRule,
            SegmentationVariant)
        program = ObjectProgram(
            segmentation_variant=SegmentationVariant.S1_SAME_COLOR_4,
            rules=[ObjectRule(
                selector=SelectorRule(
                    predicate=PredExpr(op="test", args=("color", "==", 8)),
                    literals=1),
                action=ActionRule(
                    delta_type=DeltaType.CROP_TO,
                    params={"region": RegionExpr(op="bbox_self"),
                            "tile_w": ScalarExpr(
                                op="count",
                                args=(PredExpr(op="test",
                                               args=("color", "==", 4)),))}))],
            output_spec=OutputSpec(mode="crop"))
        grid = Grid(np.array([[8, 8, 0, 0, 0],
                              [0, 8, 0, 4, 0],
                              [0, 0, 0, 0, 4]]))
        out = render_program(program, grid).to_numpy()
        unit = np.array([[8, 8], [0, 8]])
        assert np.array_equal(out, np.tile(unit, (1, 2)))


# ---------------------------------------------------------------------------
# End-to-end induction (incl. the blocking LOO gate)
# ---------------------------------------------------------------------------

def _mirror_reversal_task():
    """Distinct shapes reverse their vertical order; the middle pair has a
    center object that maps to itself (KEEP absorbed into TRANSLATE via
    tier 1b)."""
    def flip(g):
        return np.flipud(np.array(g)).tolist()

    g1 = [[0, 1, 1, 5],
          [0, 0, 0, 0],
          [2, 0, 0, 0],   # center row: maps to itself
          [0, 0, 0, 0],
          [3, 3, 3, 0]]
    g2 = [[4, 4, 0, 9],
          [0, 0, 0, 0],
          [0, 0, 6, 0],   # center row: maps to itself
          [0, 0, 0, 0],
          [0, 7, 7, 7]]
    g3 = [[0, 0, 2, 2],
          [0, 0, 0, 0],
          [0, 0, 0, 0],
          [0, 0, 0, 0],
          [8, 0, 0, 0]]
    pairs = []
    for g in (g1, g2, g3):
        arr = np.array(g)
        pairs.append((arr, np.flipud(arr)))
    return pairs


class TestEndToEnd:
    def test_mirror_reversal_accepted_with_loo(self):
        pairs = to_grid_pairs(_mirror_reversal_task())
        result = induce_program(pairs, InductionConfig(budget_s=30.0))
        assert result.accepted, (result.failure_stage, result.loo)
        assert result.loo is not None and result.loo.all_passed
        prog_json = result.program.to_json()
        assert "mirror_vector" in prog_json

    def test_tiled_crop_shrink_accepted_with_loo(self):
        # output = crop of the 8-object, tiled horizontally count(color==4)x
        def make(pos4, unit):
            g = np.zeros((6, 6), dtype=int)
            u = np.array(unit)
            g[0:u.shape[0], 0:u.shape[1]] = u
            for r, c in pos4:
                g[r, c] = 4
            out = np.tile(u, (1, max(1, len(pos4))))
            return g, out

        unit = [[8, 0], [8, 8]]
        pairs = to_grid_pairs([
            make([(4, 4)], unit),
            make([(3, 3), (5, 1)], unit),
            make([(2, 4), (4, 2), (5, 5)], unit),
        ])
        result = induce_program(pairs, InductionConfig(budget_s=30.0))
        assert result.accepted, (result.failure_stage, result.loo)
        prog_json = result.program.to_json()
        assert "tile_w" in prog_json and "crop_to" in prog_json
