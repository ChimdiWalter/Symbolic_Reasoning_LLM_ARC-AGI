"""Unit tests for the expressions/actions team deliverables.

Covers (task contract):
- expression evaluation on synthetic object scenes (every node class),
- parameter-class classification (Requirement 2.4.1),
- full JSON serialization round-trips (expressions and whole programs),
- enumerate_expressions determinism / dedup / preference ordering / depth,
- substitute_free_slots (library-fragment instantiation),
- every action primitive on synthetic grids + render_program end-to-end.

The tests self-register the minimal canonical feature/relation names they
need ONLY if the features team's register_builtin_features() is not yet
implemented (names + semantics match the frozen PLANNED_FEATURES list, so
the tests are valid before and after that lands).
"""
from __future__ import annotations

import json

import numpy as np
import pytest

from geocat_arc.perception.grid import Grid
from geocat_arc.perception.objects import ARCObject
from geocat_arc.perception import relations as perception_relations

from geocat_arc.object_reasoning import features as F
from geocat_arc.object_reasoning import expressions as X
from geocat_arc.object_reasoning import actions as A
from geocat_arc.object_reasoning.expressions import (
    AngleExpr,
    AxisExpr,
    ColorExpr,
    DirectionExpr,
    EnumerationContext,
    EvalContext,
    EvalError,
    FreeSlotExpr,
    PredExpr,
    RefExpr,
    RegionExpr,
    ScalarExpr,
    VecExpr,
    enumerate_expressions,
    evaluate,
    make_color_map,
    parameter_class_of,
    production_depth,
    substitute_free_slots,
)
from geocat_arc.object_reasoning.segmentation import segment_s1, segment_s3
from geocat_arc.object_reasoning.types import (
    ActionRule,
    DeltaType,
    Expr,
    ExprType,
    FeatureKind,
    GridContext,
    MultiColorObject,
    ObjectProgram,
    ObjectRule,
    OutputSpec,
    ParameterClass,
    SegmentationVariant,
    SelectorRule,
)


# ---------------------------------------------------------------------------
# Registry bootstrap (canonical names, register-if-absent)
# ---------------------------------------------------------------------------

def _ensure_registry() -> None:
    try:
        F.register_builtin_features()
    except NotImplementedError:
        pass
    if "color" not in F.FEATURE_REGISTRY:
        F.register_feature("color", FeatureKind.COLOR,
                           lambda o, ctx: int(o.color))
    if "size" not in F.FEATURE_REGISTRY:
        F.register_feature("size", FeatureKind.SCALAR,
                           lambda o, ctx: int(o.size))
    if "has_hole" not in F.FEATURE_REGISTRY:
        F.register_feature("has_hole", FeatureKind.BOOL,
                           lambda o, ctx: bool(o.has_hole))
    if "adjacent" not in F.RELATION_REGISTRY:
        F.register_relation("adjacent",
                            lambda a, b, ctx: perception_relations.adjacent(a, b))


_ensure_registry()


# ---------------------------------------------------------------------------
# Synthetic scenes
# ---------------------------------------------------------------------------

def _grid(rows: list[list[int]]) -> Grid:
    return Grid(np.array(rows, dtype=np.int32))


def _scene(grid: Grid):
    """Segment with S1 and return (objects, GridContext)."""
    objects = segment_s1(grid, background=0)
    ctx = GridContext(grid=grid, objects=objects, background=0)
    return objects, ctx


def _by_color(objects: list[ARCObject], color: int) -> ARCObject:
    matches = [o for o in objects if o.color == color]
    assert len(matches) == 1, f"expected one object of color {color}"
    return matches[0]


def _ectx(obj: ARCObject, ctx: GridContext, template=None) -> EvalContext:
    return EvalContext(obj=obj, grid_ctx=ctx, matched_template=template)


def playground():
    """10x10 scene:
    A: 3x3 square color 3 at (1,1)-(3,3)   size 9, centroid (2,2)
    B: 1 cell   color 2 at (1,5)           size 1
    C: 3x3 ring color 4 at (5,5)-(7,7)     size 8, hole at (6,6)
    D: 1 cell   color 6 at (6,6)           inside C
    E: 1 cell   color 3 at (8,1)           second color-3 object
    """
    g = np.zeros((10, 10), dtype=np.int32)
    g[1:4, 1:4] = 3                       # A
    g[1, 5] = 2                           # B
    g[5:8, 5:8] = 4                       # C (ring)
    g[6, 6] = 6                           # D (also punches C's hole)
    g[8, 1] = 3                           # E
    grid = Grid(g)
    objects, ctx = _scene(grid)
    named = {name: _by_color(objects, c)
             for name, c in (("B", 2), ("C", 4), ("D", 6))}
    color3 = sorted([o for o in objects if o.color == 3], key=lambda o: o.size,
                    reverse=True)
    named["A"], named["E"] = color3[0], color3[1]
    return grid, objects, ctx, named


# ---------------------------------------------------------------------------
# Expression evaluation — RefExpr
# ---------------------------------------------------------------------------

class TestRefExpr:
    def setup_method(self):
        self.grid, self.objects, self.ctx, self.o = playground()

    def test_self(self):
        a = self.o["A"]
        assert evaluate(RefExpr(op="self"), a, _ectx(a, self.ctx)) is a

    def test_nearest_object(self):
        a = self.o["A"]
        got = evaluate(RefExpr(op="nearest_object", args=(PredExpr(op="true"),)),
                       a, _ectx(a, self.ctx))
        assert got is self.o["B"]

    def test_nearest_object_of_color(self):
        a = self.o["A"]
        got = evaluate(RefExpr(op="nearest_object_of_color", args=(2,)),
                       a, _ectx(a, self.ctx))
        assert got is self.o["B"]
        with pytest.raises(EvalError):
            evaluate(RefExpr(op="nearest_object_of_color", args=(9,)),
                     a, _ectx(a, self.ctx))

    def test_container_and_contained(self):
        d, c = self.o["D"], self.o["C"]
        assert evaluate(RefExpr(op="container"), d, _ectx(d, self.ctx)) is c
        assert evaluate(RefExpr(op="contained"), c, _ectx(c, self.ctx)) is d
        a = self.o["A"]
        with pytest.raises(EvalError):
            evaluate(RefExpr(op="container"), a, _ectx(a, self.ctx))
        with pytest.raises(EvalError):
            evaluate(RefExpr(op="contained"), a, _ectx(a, self.ctx))

    def test_largest(self):
        b = self.o["B"]
        got = evaluate(RefExpr(op="largest", args=(PredExpr(op="true"),)),
                       b, _ectx(b, self.ctx))
        assert got is self.o["A"]

    def test_unique(self):
        a = self.o["A"]
        pred = PredExpr(op="test", args=("color", "==", 6))
        got = evaluate(RefExpr(op="unique", args=(pred,)), a, _ectx(a, self.ctx))
        assert got is self.o["D"]
        # two color-3 objects -> not unique
        with pytest.raises(EvalError):
            evaluate(RefExpr(op="unique",
                             args=(PredExpr(op="test", args=("color", "==", 3)),)),
                     a, _ectx(a, self.ctx))

    def test_matched_template(self):
        a, b = self.o["A"], self.o["B"]
        assert evaluate(RefExpr(op="matched_template"), a,
                        _ectx(a, self.ctx, template=b)) is b
        with pytest.raises(EvalError):
            evaluate(RefExpr(op="matched_template"), a, _ectx(a, self.ctx))


# ---------------------------------------------------------------------------
# Expression evaluation — ColorExpr / VecExpr / ScalarExpr / RegionExpr / Pred
# ---------------------------------------------------------------------------

class TestColorExpr:
    def setup_method(self):
        self.grid, self.objects, self.ctx, self.o = playground()

    def test_const(self):
        a = self.o["A"]
        assert evaluate(ColorExpr(op="const", args=(7,)), a, _ectx(a, self.ctx)) == 7

    def test_color_of_container(self):
        d = self.o["D"]
        expr = ColorExpr(op="color_of", args=(RefExpr(op="container"),))
        assert evaluate(expr, d, _ectx(d, self.ctx)) == 4

    def test_most_and_least_common(self):
        a = self.o["A"]
        # color counts: {3: 2, 2: 1, 4: 1, 6: 1}
        assert evaluate(ColorExpr(op="most_common_color"), a,
                        _ectx(a, self.ctx)) == 3
        # least: tie among 2/4/6 -> smallest color
        assert evaluate(ColorExpr(op="least_common_color"), a,
                        _ectx(a, self.ctx)) == 2

    def test_color_map(self):
        a, b = self.o["A"], self.o["B"]
        expr = make_color_map({3: 8})
        assert evaluate(expr, a, _ectx(a, self.ctx)) == 8
        with pytest.raises(EvalError):
            evaluate(expr, b, _ectx(b, self.ctx))  # no entry for color 2


class TestVecExpr:
    def setup_method(self):
        self.grid, self.objects, self.ctx, self.o = playground()

    def test_const(self):
        a = self.o["A"]
        assert evaluate(VecExpr(op="const", args=(2, -1)), a,
                        _ectx(a, self.ctx)) == (2, -1)

    def test_vector_to_nearest_of_color(self):
        a = self.o["A"]
        expr = VecExpr(op="vector_to",
                       args=(RefExpr(op="nearest_object_of_color", args=(2,)),))
        # B centroid (1,5) - A centroid (2,2)
        assert evaluate(expr, a, _ectx(a, self.ctx)) == (-1, 3)

    def test_vector_to_border(self):
        a = self.o["A"]  # bbox (1,1,4,4) on 10x10
        e = _ectx(a, self.ctx)
        assert evaluate(VecExpr(op="vector_to_border", args=("up",)), a, e) == (-1, 0)
        assert evaluate(VecExpr(op="vector_to_border", args=("down",)), a, e) == (6, 0)
        assert evaluate(VecExpr(op="vector_to_border", args=("left",)), a, e) == (0, -1)
        assert evaluate(VecExpr(op="vector_to_border", args=("right",)), a, e) == (0, 6)

    def test_gap_closing_vector(self):
        a = self.o["A"]
        e = _ectx(a, self.ctx)
        to_c = RefExpr(op="nearest_object_of_color", args=(4,))
        assert evaluate(VecExpr(op="gap_closing_vector", args=(to_c, "vertical")),
                        a, e) == (1, 0)     # A bottom row 3, C top row 5
        to_b = RefExpr(op="nearest_object_of_color", args=(2,))
        assert evaluate(VecExpr(op="gap_closing_vector", args=(to_b, "horizontal")),
                        a, e) == (0, 1)     # A right col 3, B col 5
        with pytest.raises(EvalError):  # overlap with itself along the axis
            evaluate(VecExpr(op="gap_closing_vector",
                             args=(RefExpr(op="self"), "vertical")), a, e)

    def test_scaled_unit(self):
        a = self.o["A"]  # size 9
        e = _ectx(a, self.ctx)
        expr = VecExpr(op="scaled_unit", args=("down", ScalarExpr(op="size")))
        assert evaluate(expr, a, e) == (9, 0)
        expr = VecExpr(op="scaled_unit", args=("right", ScalarExpr(op="const", args=(2,))))
        assert evaluate(expr, a, e) == (0, 2)


class TestScalarExpr:
    def setup_method(self):
        self.grid, self.objects, self.ctx, self.o = playground()

    def test_all_ops(self):
        a, c = self.o["A"], self.o["C"]
        e = _ectx(a, self.ctx)
        assert evaluate(ScalarExpr(op="const", args=(5,)), a, e) == 5
        assert evaluate(ScalarExpr(op="size"), a, e) == 9
        assert evaluate(ScalarExpr(op="hole_count"), c, _ectx(c, self.ctx)) == 1
        assert evaluate(ScalarExpr(op="feature", args=("size",)), a, e) == 9
        count = ScalarExpr(op="count",
                           args=(PredExpr(op="test", args=("color", "==", 3)),))
        assert evaluate(count, a, e) == 2   # A and E

    def test_feature_kind_mismatch(self):
        a = self.o["A"]
        with pytest.raises(EvalError):
            evaluate(ScalarExpr(op="feature", args=("color",)), a,
                     _ectx(a, self.ctx))
        with pytest.raises(EvalError):
            evaluate(ScalarExpr(op="feature", args=("not_a_feature",)), a,
                     _ectx(a, self.ctx))


class TestRegionExpr:
    def setup_method(self):
        self.grid, self.objects, self.ctx, self.o = playground()

    def test_bboxes(self):
        a, d = self.o["A"], self.o["D"]
        assert evaluate(RegionExpr(op="bbox_self"), a,
                        _ectx(a, self.ctx)) == (1, 1, 4, 4)
        expr = RegionExpr(op="bbox", args=(RefExpr(op="container"),))
        assert evaluate(expr, d, _ectx(d, self.ctx)) == (5, 5, 8, 8)

    def test_grid_quadrant(self):
        a = self.o["A"]
        e = _ectx(a, self.ctx)
        assert evaluate(RegionExpr(op="grid_quadrant", args=(0,)), a, e) == (0, 0, 5, 5)
        assert evaluate(RegionExpr(op="grid_quadrant", args=(3,)), a, e) == (5, 5, 10, 10)
        with pytest.raises(EvalError):
            evaluate(RegionExpr(op="grid_quadrant", args=(4,)), a, e)

    def test_separator_cell(self):
        grid = _grid([
            [1, 0, 2, 0, 3],
            [0, 1, 0, 0, 0],
            [5, 5, 5, 5, 5],
            [0, 0, 4, 0, 0],
            [6, 0, 0, 0, 7],
        ])
        objects, ctx = _scene(grid)
        obj = objects[0]
        e = _ectx(obj, ctx)
        assert evaluate(RegionExpr(op="separator_cell", args=(0, 0)), obj, e) \
            == (0, 0, 2, 5)
        assert evaluate(RegionExpr(op="separator_cell", args=(1, 0)), obj, e) \
            == (3, 0, 5, 5)
        with pytest.raises(EvalError):
            evaluate(RegionExpr(op="separator_cell", args=(0, 1)), obj, e)


class TestPredExpr:
    def setup_method(self):
        self.grid, self.objects, self.ctx, self.o = playground()

    def test_true_and_test(self):
        a, b = self.o["A"], self.o["B"]
        assert evaluate(PredExpr(op="true"), a, _ectx(a, self.ctx)) is True
        t = PredExpr(op="test", args=("color", "==", 3))
        assert evaluate(t, a, _ectx(a, self.ctx)) is True
        assert evaluate(t, b, _ectx(b, self.ctx)) is False
        lt = PredExpr(op="test", args=("size", "<", 5))
        assert evaluate(lt, b, _ectx(b, self.ctx)) is True
        assert evaluate(lt, a, _ectx(a, self.ctx)) is False

    def test_rank_markers(self):
        a, b = self.o["A"], self.o["B"]
        biggest = PredExpr(op="test", args=("size", "==", "@rank_max"))
        assert evaluate(biggest, a, _ectx(a, self.ctx)) is True
        assert evaluate(biggest, b, _ectx(b, self.ctx)) is False
        smallest = PredExpr(op="test", args=("size", "==", "@rank_min"))
        assert evaluate(smallest, b, _ectx(b, self.ctx)) is True

    def test_and2_and_literals(self):
        a = self.o["A"]
        t1 = PredExpr(op="test", args=("color", "==", 3))
        t2 = PredExpr(op="test", args=("size", "==", "@rank_max"))
        conj = PredExpr(op="and2", args=(t1, t2))
        assert evaluate(conj, a, _ectx(a, self.ctx)) is True
        e = self.o["E"]  # color 3 but not largest
        assert evaluate(conj, e, _ectx(e, self.ctx)) is False
        assert PredExpr(op="true").literals == 0
        assert t1.literals == 1
        assert conj.literals == 2

    def test_relation_exists(self):
        d, b = self.o["D"], self.o["B"]
        rex = PredExpr(op="relation_exists", args=("adjacent", PredExpr(op="true")))
        assert evaluate(rex, d, _ectx(d, self.ctx)) is True   # D touches ring C
        assert evaluate(rex, b, _ectx(b, self.ctx)) is False  # B is isolated
        assert rex.literals == 1
        with pytest.raises(EvalError):
            evaluate(PredExpr(op="relation_exists",
                              args=("no_such_relation", PredExpr(op="true"))),
                     d, _ectx(d, self.ctx))

    def test_free_slot_raises(self):
        a = self.o["A"]
        with pytest.raises(EvalError):
            evaluate(FreeSlotExpr(op="free_slot", args=("c", "color")), a,
                     _ectx(a, self.ctx))


class TestSymbolLeaves:
    def test_axis_angle_direction(self):
        grid, objects, ctx, o = playground()
        a = o["A"]
        e = _ectx(a, ctx)
        assert evaluate(AxisExpr(op="const", args=("horizontal",)), a, e) == "horizontal"
        assert evaluate(AngleExpr(op="const", args=(180,)), a, e) == 180
        assert evaluate(DirectionExpr(op="const", args=("down",)), a, e) == "down"
        with pytest.raises(EvalError):
            evaluate(AxisExpr(op="const", args=("sideways",)), a, e)
        with pytest.raises(EvalError):
            evaluate(AngleExpr(op="const", args=(45,)), a, e)


# ---------------------------------------------------------------------------
# Parameter-class classification (Requirement 2.4.1)
# ---------------------------------------------------------------------------

class TestParameterClass:
    def test_relational(self):
        assert parameter_class_of(
            VecExpr(op="vector_to",
                    args=(RefExpr(op="nearest_object", args=(PredExpr(op="true"),)),))
        ) is ParameterClass.RELATIONAL
        assert parameter_class_of(
            ColorExpr(op="color_of", args=(RefExpr(op="container"),))
        ) is ParameterClass.RELATIONAL
        assert parameter_class_of(
            VecExpr(op="gap_closing_vector",
                    args=(RefExpr(op="nearest_object_of_color", args=(2,)), "vertical"))
        ) is ParameterClass.RELATIONAL
        assert parameter_class_of(
            VecExpr(op="vector_to_border", args=("down",))
        ) is ParameterClass.RELATIONAL

    def test_feature(self):
        assert parameter_class_of(
            VecExpr(op="scaled_unit", args=("down", ScalarExpr(op="size")))
        ) is ParameterClass.FEATURE
        assert parameter_class_of(
            ColorExpr(op="color_of", args=(RefExpr(op="self"),))
        ) is ParameterClass.FEATURE
        assert parameter_class_of(ScalarExpr(op="hole_count")) is ParameterClass.FEATURE

    def test_induced_map(self):
        assert parameter_class_of(make_color_map({1: 2})) is ParameterClass.INDUCED_MAP

    def test_constant(self):
        assert parameter_class_of(VecExpr(op="const", args=(2, 0))) \
            is ParameterClass.CONSTANT
        assert parameter_class_of(ColorExpr(op="const", args=(3,))) \
            is ParameterClass.CONSTANT
        assert parameter_class_of(
            VecExpr(op="scaled_unit", args=("down", ScalarExpr(op="const", args=(3,))))
        ) is ParameterClass.CONSTANT

    def test_worst_wins_on_mixed(self):
        # relational + induced map -> the worse (induced_map) wins
        mixed = PredExpr(op="and2", args=(
            PredExpr(op="relation_exists", args=("adjacent", PredExpr(op="true"))),
            PredExpr(op="test", args=("color", "==", 3))))
        assert parameter_class_of(mixed) is ParameterClass.RELATIONAL


# ---------------------------------------------------------------------------
# Serialization round-trips
# ---------------------------------------------------------------------------

ROUND_TRIP_EXPRS = [
    ColorExpr(op="const", args=(7,)),
    ColorExpr(op="color_of", args=(RefExpr(op="container"),)),
    make_color_map({3: 8, 2: 1}),
    RefExpr(op="nearest_object", args=(PredExpr(op="test", args=("color", "==", 2)),)),
    VecExpr(op="vector_to", args=(RefExpr(op="nearest_object_of_color", args=(2,)),)),
    VecExpr(op="gap_closing_vector", args=(RefExpr(op="largest",
            args=(PredExpr(op="true"),)), "vertical")),
    VecExpr(op="scaled_unit", args=("down", ScalarExpr(op="feature", args=("size",)))),
    ScalarExpr(op="count", args=(PredExpr(op="and2", args=(
        PredExpr(op="test", args=("color", "==", 3)),
        PredExpr(op="test", args=("size", "==", "@rank_max")))),)),
    RegionExpr(op="bbox", args=(RefExpr(op="unique",
               args=(PredExpr(op="test", args=("has_hole", "==", True)),)),)),
    RegionExpr(op="separator_cell", args=(1, 0)),
    PredExpr(op="relation_exists", args=("adjacent",
             PredExpr(op="test", args=("color", "==", 4)))),
    FreeSlotExpr(op="free_slot", args=("target_color", "color")),
    AxisExpr(op="const", args=("diag_main",)),
    AngleExpr(op="const", args=(270,)),
    DirectionExpr(op="const", args=("left",)),
]


class TestSerialization:
    @pytest.mark.parametrize("expr", ROUND_TRIP_EXPRS,
                             ids=lambda e: f"{type(e).__name__}:{e.op}")
    def test_expr_json_round_trip(self, expr):
        wire = json.dumps(expr.to_dict())          # through REAL json
        back = Expr.from_dict(json.loads(wire))
        assert back == expr
        assert type(back) is type(expr)
        assert back.rtype is expr.rtype

    def test_serialize_aliases(self):
        expr = ROUND_TRIP_EXPRS[4]
        assert X.deserialize_expr(X.serialize_expr(expr)) == expr

    def test_program_json_round_trip(self):
        program = _gravity_program()
        wire = program.to_json()
        back = ObjectProgram.from_json(wire)
        assert back.to_dict() == program.to_dict()
        assert back.segmentation_variant is program.segmentation_variant
        assert back.rules[0].action.params["vector"] == \
            program.rules[0].action.params["vector"]


# ---------------------------------------------------------------------------
# Enumeration
# ---------------------------------------------------------------------------

def _enum_ctx() -> EnumerationContext:
    return EnumerationContext(
        observed_colors=[3, 2],
        observed_constants=[1, 2, (2, 0), {3: 8}],
        scalar_features=["size"],
        bool_features=["has_hole"],
        color_features=["color"],
        categorical_features=[],
        relation_names=["adjacent"],
    )


ENUM_TYPES = [ExprType.COLOR, ExprType.VECTOR, ExprType.SCALAR,
              ExprType.REGION, ExprType.PREDICATE, ExprType.REF,
              ExprType.AXIS, ExprType.ANGLE, ExprType.DIRECTION]


class TestEnumeration:
    @pytest.mark.parametrize("rtype", ENUM_TYPES, ids=lambda t: t.value)
    def test_deterministic_and_deduped(self, rtype):
        first = list(enumerate_expressions(rtype, _enum_ctx()))
        second = list(enumerate_expressions(rtype, _enum_ctx()))
        assert first == second
        assert len(first) == len(set(first))
        assert first, f"enumeration for {rtype} is empty"

    @pytest.mark.parametrize("rtype", ENUM_TYPES, ids=lambda t: t.value)
    def test_production_depth_capped(self, rtype):
        for e in enumerate_expressions(rtype, _enum_ctx()):
            assert production_depth(e) <= X.MAX_DEPTH
            if isinstance(e, PredExpr):
                assert e.depth <= X.MAX_DEPTH  # PRED cap is structural

    @pytest.mark.parametrize("rtype", [ExprType.COLOR, ExprType.VECTOR,
                                       ExprType.SCALAR, ExprType.REGION],
                             ids=lambda t: t.value)
    def test_preference_order(self, rtype):
        ranks = [parameter_class_of(e).rank
                 for e in enumerate_expressions(rtype, _enum_ctx())]
        assert ranks == sorted(ranks), \
            "relational > feature > induced_map > constant ordering violated"

    def test_pred_stream_shape(self):
        preds = list(enumerate_expressions(ExprType.PREDICATE, _enum_ctx()))
        assert preds[0] == PredExpr(op="true")
        assert PredExpr(op="test", args=("color", "==", 3)) in preds
        assert PredExpr(op="test", args=("size", "==", "@rank_max")) in preds
        assert any(p.op == "relation_exists" for p in preds)
        assert any(p.op == "and2" for p in preds)
        ops = [p.op for p in preds]
        assert ops.index("test") < ops.index("and2"), "tests must precede and2"

    def test_required_expressivity_present(self):
        vectors = list(enumerate_expressions(ExprType.VECTOR, _enum_ctx()))
        assert VecExpr(op="vector_to",
                       args=(RefExpr(op="nearest_object_of_color", args=(2,)),)) \
            in vectors, "vector_to_nearest(color=X) missing"
        assert any(v.op == "gap_closing_vector" for v in vectors)
        assert VecExpr(op="vector_to_border", args=("down",)) in vectors
        colors = list(enumerate_expressions(ExprType.COLOR, _enum_ctx()))
        assert ColorExpr(op="color_of", args=(RefExpr(op="container"),)) in colors
        assert make_color_map({3: 8}) in colors
        assert ColorExpr(op="const", args=(2,)) in colors
        # constants after the relational block (last-resort rule)
        c_idx = colors.index(ColorExpr(op="const", args=(2,)))
        r_idx = colors.index(ColorExpr(op="color_of", args=(RefExpr(op="container"),)))
        assert r_idx < c_idx

    def test_symbol_enumerations(self):
        assert [e.args[0] for e in
                enumerate_expressions(ExprType.AXIS, _enum_ctx())] == \
            ["horizontal", "vertical", "diag_main", "diag_anti"]
        assert len(list(enumerate_expressions(ExprType.ANGLE, _enum_ctx()))) == 3
        assert len(list(enumerate_expressions(ExprType.DIRECTION, _enum_ctx()))) == 4

    def test_depth_one_is_leaves_only(self):
        for rtype in (ExprType.COLOR, ExprType.VECTOR, ExprType.SCALAR,
                      ExprType.REGION):
            for e in enumerate_expressions(rtype, _enum_ctx(), max_depth=1):
                assert e.depth == 1, f"non-leaf {e} at max_depth=1"

    @pytest.mark.parametrize("rtype", [ExprType.COLOR, ExprType.VECTOR,
                                       ExprType.SCALAR, ExprType.REGION,
                                       ExprType.PREDICATE],
                             ids=lambda t: t.value)
    def test_all_candidates_evaluate_or_evalerror(self, rtype):
        """Total-safety property: every enumerated hypothesis either evaluates
        or raises EvalError — never any other exception (Req: undefined case
        = conflict, never a crash)."""
        grid, objects, ctx, o = playground()
        a = o["A"]
        for expr in enumerate_expressions(rtype, _enum_ctx()):
            try:
                evaluate(expr, a, _ectx(a, ctx))
            except EvalError:
                pass


class TestFreeSlots:
    def test_substitute(self):
        frag = VecExpr(op="vector_to",
                       args=(FreeSlotExpr(op="free_slot", args=("target", "ref")),))
        bound = substitute_free_slots(
            frag, {"target": RefExpr(op="nearest_object_of_color", args=(2,))})
        assert bound == VecExpr(
            op="vector_to",
            args=(RefExpr(op="nearest_object_of_color", args=(2,)),))
        # untouched expressions come back identical
        plain = ColorExpr(op="const", args=(3,))
        assert substitute_free_slots(plain, {}) is plain

    def test_missing_binding_raises(self):
        frag = FreeSlotExpr(op="free_slot", args=("c", "color"))
        with pytest.raises(KeyError):
            substitute_free_slots(frag, {})


# ---------------------------------------------------------------------------
# Action primitives (direct unit calls)
# ---------------------------------------------------------------------------

def _canvas_for(grid: Grid, background: int = 0) -> A.ObjectCanvas:
    return A.ObjectCanvas(objects=[], height=grid.height, width=grid.width,
                          background=background, source_grid=grid)


def _rule(delta: DeltaType, **params) -> ActionRule:
    return ActionRule(delta_type=delta, params=params)


class TestActionPrimitives:
    def setup_method(self):
        self.grid, self.objects, self.ctx, self.o = playground()
        self.canvas = _canvas_for(self.grid)

    def test_keep_delete(self):
        a = self.o["A"]
        e = _ectx(a, self.ctx)
        assert A.apply_keep(self.canvas, a, _rule(DeltaType.KEEP), e) == [a]
        assert A.apply_delete(self.canvas, a, _rule(DeltaType.DELETE), e) == []

    def test_translate(self):
        b = self.o["B"]
        out = A.apply_translate(
            self.canvas, b,
            _rule(DeltaType.TRANSLATE, vector=VecExpr(op="const", args=(2, -1))),
            _ectx(b, self.ctx))
        assert len(out) == 1 and out[0].cells == frozenset({(3, 4)})

    def test_recolor_relational(self):
        c = self.o["C"]
        out = A.apply_recolor(
            self.canvas, c,
            _rule(DeltaType.RECOLOR,
                  color=ColorExpr(op="color_of", args=(RefExpr(op="contained"),))),
            _ectx(c, self.ctx))
        assert out[0].color == 6 and out[0].cells == c.cells

    def test_copy(self):
        b = self.o["B"]
        out = A.apply_copy(
            self.canvas, b,
            _rule(DeltaType.COPY,
                  k=ScalarExpr(op="const", args=(2,)),
                  placement=VecExpr(op="const", args=(0, 2))),
            _ectx(b, self.ctx))
        assert len(out) == 3                      # original + 2 copies
        assert out[0] is b
        assert all(o.cells == frozenset({(1, 7)}) for o in out[1:])
        assert len({o.id for o in out}) == 3      # fresh ids

    def test_copy_without_original(self):
        b = self.o["B"]
        out = A.apply_copy(
            self.canvas, b,
            _rule(DeltaType.COPY,
                  k=ScalarExpr(op="const", args=(1,)),
                  placement=VecExpr(op="const", args=(1, 0)),
                  keep_original=ScalarExpr(op="const", args=(0,))),
            _ectx(b, self.ctx))
        assert len(out) == 1 and out[0].cells == frozenset({(2, 5)})

    def test_move_to(self):
        a = self.o["A"]
        out = A.apply_move_to(
            self.canvas, a,
            _rule(DeltaType.MOVE_TO, position=VecExpr(op="const", args=(5, 5))),
            _ectx(a, self.ctx))
        assert out[0].bounding_box == (5, 5, 8, 8)

    def test_scale_up_down(self):
        grid = _grid([[0] * 6 for _ in range(6)])
        sq = ARCObject(id=0, cells=frozenset({(1, 1), (1, 2), (2, 1), (2, 2)}),
                       color=5, bounding_box=(1, 1, 3, 3))
        ctx = GridContext(grid=grid, objects=[sq], background=0)
        canvas = _canvas_for(grid)
        up = A.apply_scale(canvas, sq,
                           _rule(DeltaType.SCALE,
                                 factor=ScalarExpr(op="const", args=(2,))),
                           _ectx(sq, ctx))[0]
        assert up.bounding_box == (1, 1, 5, 5) and up.size == 16
        down = A.apply_scale(canvas, up,
                             _rule(DeltaType.SCALE,
                                   factor=ScalarExpr(op="const", args=(-2,))),
                             _ectx(up, ctx))[0]
        assert down.cells == sq.cells
        with pytest.raises(EvalError):
            A.apply_scale(canvas, sq,
                          _rule(DeltaType.SCALE,
                                factor=ScalarExpr(op="const", args=(0,))),
                          _ectx(sq, ctx))

    def test_reflect(self):
        grid = _grid([[0] * 4 for _ in range(4)])
        ell = ARCObject(id=0, cells=frozenset({(0, 0), (1, 0), (1, 1)}),
                        color=7, bounding_box=(0, 0, 2, 2))
        ctx = GridContext(grid=grid, objects=[ell], background=0)
        canvas = _canvas_for(grid)

        def reflect(axis):
            return A.apply_reflect(
                canvas, ell,
                _rule(DeltaType.REFLECT, axis=AxisExpr(op="const", args=(axis,))),
                _ectx(ell, ctx))[0]

        assert reflect("vertical").cells == frozenset({(0, 1), (1, 0), (1, 1)})
        assert reflect("horizontal").cells == frozenset({(0, 0), (0, 1), (1, 0)})
        assert reflect("diag_main").cells == frozenset({(0, 0), (0, 1), (1, 1)})

    def test_rotate(self):
        grid = _grid([[0] * 4 for _ in range(4)])
        line = ARCObject(id=0, cells=frozenset({(0, 0), (1, 0), (2, 0)}),
                         color=7, bounding_box=(0, 0, 3, 1))
        ctx = GridContext(grid=grid, objects=[line], background=0)
        canvas = _canvas_for(grid)
        out = A.apply_rotate(
            canvas, line,
            _rule(DeltaType.ROTATE, angle=AngleExpr(op="const", args=(90,))),
            _ectx(line, ctx))[0]
        assert out.cells == frozenset({(0, 0), (0, 1), (0, 2)})
        # 90 twice == 180
        twice = A.apply_rotate(
            canvas, out,
            _rule(DeltaType.ROTATE, angle=AngleExpr(op="const", args=(90,))),
            _ectx(out, ctx))[0]
        once180 = A.apply_rotate(
            canvas, line,
            _rule(DeltaType.ROTATE, angle=AngleExpr(op="const", args=(180,))),
            _ectx(line, ctx))[0]
        assert twice.cells == once180.cells

    def test_crop_to_sets_region(self):
        a = self.o["A"]
        out = A.apply_crop_to(
            self.canvas, a,
            _rule(DeltaType.CROP_TO, region=RegionExpr(op="bbox_self")),
            _ectx(a, self.ctx))
        assert out == [a]
        assert self.canvas.crop_region == (1, 1, 4, 4)

    def test_missing_param_is_evalerror(self):
        a = self.o["A"]
        with pytest.raises(EvalError):
            A.apply_translate(self.canvas, a, _rule(DeltaType.TRANSLATE),
                              _ectx(a, self.ctx))


class TestMoveUntilAdjacent:
    def _gravity_scene(self):
        g = np.zeros((8, 8), dtype=np.int32)
        g[0:2, 4:6] = 3          # movable P
        g[6:8, 3:7] = 8          # wall T
        grid = Grid(g)
        objects, ctx = _scene(grid)
        return grid, ctx, _by_color(objects, 3)

    def test_with_direction_and_target(self):
        grid, ctx, p = self._gravity_scene()
        canvas = _canvas_for(grid)
        out = A.apply_move_until_adjacent(
            canvas, p,
            _rule(DeltaType.MOVE_UNTIL_ADJACENT,
                  target=RefExpr(op="nearest_object_of_color", args=(8,)),
                  direction=DirectionExpr(op="const", args=("down",))),
            _ectx(p, ctx))[0]
        assert out.bounding_box == (4, 4, 6, 6)   # rows 4-5, adjacent to row 6

    def test_direction_inferred(self):
        grid, ctx, p = self._gravity_scene()
        out = A.apply_move_until_adjacent(
            _canvas_for(grid), p,
            _rule(DeltaType.MOVE_UNTIL_ADJACENT,
                  target=RefExpr(op="nearest_object_of_color", args=(8,))),
            _ectx(p, ctx))[0]
        assert out.bounding_box == (4, 4, 6, 6)

    def test_border_mode(self):
        g = np.zeros((8, 8), dtype=np.int32)
        g[0:2, 4:6] = 3
        grid = Grid(g)
        objects, ctx = _scene(grid)
        p = objects[0]
        out = A.apply_move_until_adjacent(
            _canvas_for(grid), p,
            _rule(DeltaType.MOVE_UNTIL_ADJACENT,
                  direction=DirectionExpr(op="const", args=("down",))),
            _ectx(p, ctx))[0]
        assert out.bounding_box == (6, 4, 8, 6)   # flush with bottom border

    def test_unreachable_is_evalerror(self):
        grid, ctx, p = self._gravity_scene()
        with pytest.raises(EvalError):
            A.apply_move_until_adjacent(
                _canvas_for(grid), p,
                _rule(DeltaType.MOVE_UNTIL_ADJACENT,
                      target=RefExpr(op="nearest_object_of_color", args=(8,)),
                      direction=DirectionExpr(op="const", args=("up",))),
                _ectx(p, ctx))


class TestCompositeAndRender:
    def test_composite_translate_then_recolor(self):
        g = np.zeros((3, 4), dtype=np.int32)
        g[0, 0] = 5
        grid = Grid(g)
        objects, ctx = _scene(grid)
        obj = objects[0]
        action = ActionRule(delta_type=DeltaType.COMPOSITE, params={
            "0:translate:vector": VecExpr(op="const", args=(0, 1)),
            "1:recolor:color": ColorExpr(op="const", args=(9,)),
        })
        out = A.apply_action(_canvas_for(grid), obj, action, _ectx(obj, ctx))
        assert len(out) == 1
        assert out[0].cells == frozenset({(0, 1)}) and out[0].color == 9

    def test_composite_bad_key_is_evalerror(self):
        g = np.zeros((2, 2), dtype=np.int32)
        g[0, 0] = 5
        grid = Grid(g)
        objects, ctx = _scene(grid)
        action = ActionRule(delta_type=DeltaType.COMPOSITE,
                            params={"vector": VecExpr(op="const", args=(0, 1))})
        with pytest.raises(EvalError):
            A.apply_action(_canvas_for(grid), objects[0], action,
                           _ectx(objects[0], ctx))

    def test_render_later_object_wins(self):
        grid = _grid([[0, 0], [0, 0]])
        first = ARCObject(id=0, cells=frozenset({(0, 0)}), color=1,
                          bounding_box=(0, 0, 1, 1))
        second = ARCObject(id=1, cells=frozenset({(0, 0)}), color=2,
                           bounding_box=(0, 0, 1, 1))
        canvas = A.ObjectCanvas(objects=[first, second], height=2, width=2,
                                background=0, source_grid=grid)
        assert A.render(canvas).to_numpy()[0, 0] == 2

    def test_render_multicolor_cells(self):
        grid = _grid([[0, 0, 0], [0, 0, 0]])
        blob = MultiColorObject(id=0, cells=frozenset({(0, 0), (0, 1)}),
                                color=1, bounding_box=(0, 0, 1, 2),
                                cell_colors={(0, 0): 1, (0, 1): 2})
        canvas = A.ObjectCanvas(objects=[blob], height=2, width=3,
                                background=0, source_grid=grid)
        out = A.render(canvas).to_numpy()
        assert out[0, 0] == 1 and out[0, 1] == 2

    def test_render_clips_out_of_frame(self):
        grid = _grid([[0, 0], [0, 0]])
        stray = ARCObject(id=0, cells=frozenset({(5, 5), (0, 1)}), color=3,
                          bounding_box=(0, 1, 6, 6))
        canvas = A.ObjectCanvas(objects=[stray], height=2, width=2,
                                background=0, source_grid=grid)
        out = A.render(canvas).to_numpy()
        assert out[0, 1] == 3 and out.sum() == 3  # only in-frame cell painted


# ---------------------------------------------------------------------------
# render_program end-to-end (THE executor, Requirement 4.4)
# ---------------------------------------------------------------------------

def _selector(pred: PredExpr) -> SelectorRule:
    return SelectorRule(predicate=pred, literals=pred.literals)


def _gravity_program() -> ObjectProgram:
    """Canonical Section 2.4 example: move color-3 objects until adjacent to
    the color-8 wall (translate by gap_closing_vector, relational params)."""
    vec = VecExpr(op="gap_closing_vector",
                  args=(RefExpr(op="nearest_object_of_color", args=(8,)),
                        "vertical"))
    rule = ObjectRule(
        selector=_selector(PredExpr(op="test", args=("color", "==", 3))),
        action=ActionRule(delta_type=DeltaType.TRANSLATE,
                          params={"vector": vec},
                          parameter_class=parameter_class_of(vec)))
    return ObjectProgram(segmentation_variant=SegmentationVariant.S1_SAME_COLOR_4,
                         rules=[rule])


class TestRenderProgram:
    def test_delete_by_selector_first_match_wins(self):
        g = np.zeros((4, 4), dtype=np.int32)
        g[0, 0:2] = 2
        g[2, 2] = 3
        grid = Grid(g)
        program = ObjectProgram(
            segmentation_variant=SegmentationVariant.S1_SAME_COLOR_4,
            rules=[ObjectRule(selector=_selector(
                       PredExpr(op="test", args=("color", "==", 2))),
                   action=ActionRule(delta_type=DeltaType.DELETE))])
        out = A.render_program(program, grid).to_numpy()
        expected = g.copy()
        expected[0, 0:2] = 0
        assert np.array_equal(out, expected)

        # first-matching-rule-wins: a KEEP rule ahead of DELETE shadows it
        program2 = ObjectProgram(
            segmentation_variant=SegmentationVariant.S1_SAME_COLOR_4,
            rules=[ObjectRule(selector=_selector(PredExpr(op="true")),
                              action=ActionRule(delta_type=DeltaType.KEEP)),
                   ObjectRule(selector=_selector(
                       PredExpr(op="test", args=("color", "==", 2))),
                       action=ActionRule(delta_type=DeltaType.DELETE))])
        assert np.array_equal(A.render_program(program2, grid).to_numpy(), g)

    def test_gravity_program(self):
        g = np.zeros((8, 8), dtype=np.int32)
        g[0:2, 4:6] = 3
        g[6:8, 3:7] = 8
        expected = np.zeros((8, 8), dtype=np.int32)
        expected[4:6, 4:6] = 3
        expected[6:8, 3:7] = 8
        out = A.render_program(_gravity_program(), Grid(g)).to_numpy()
        assert np.array_equal(out, expected)

    def test_gravity_as_move_until_adjacent(self):
        g = np.zeros((8, 8), dtype=np.int32)
        g[0:2, 4:6] = 3
        g[6:8, 3:7] = 8
        program = ObjectProgram(
            segmentation_variant=SegmentationVariant.S1_SAME_COLOR_4,
            rules=[ObjectRule(
                selector=_selector(PredExpr(op="test", args=("color", "==", 3))),
                action=ActionRule(
                    delta_type=DeltaType.MOVE_UNTIL_ADJACENT,
                    params={"target": RefExpr(op="nearest_object_of_color",
                                              args=(8,))}))])
        assert np.array_equal(A.render_program(program, Grid(g)).to_numpy(),
                              A.render_program(_gravity_program(), Grid(g)).to_numpy())

    def test_recolor_largest_by_contained(self):
        """Second canonical Section 2.4 example: recolor the largest object
        with the color of the object it contains."""
        g = np.zeros((8, 8), dtype=np.int32)
        g[2:5, 2:5] = 4        # ring...
        g[3, 3] = 6            # ...around inner cell
        g[6, 6] = 2            # bystander
        grid = Grid(g)
        color = ColorExpr(op="color_of", args=(RefExpr(op="contained"),))
        program = ObjectProgram(
            segmentation_variant=SegmentationVariant.S1_SAME_COLOR_4,
            rules=[ObjectRule(
                selector=_selector(PredExpr(op="test",
                                            args=("size", "==", "@rank_max"))),
                action=ActionRule(delta_type=DeltaType.RECOLOR,
                                  params={"color": color},
                                  parameter_class=parameter_class_of(color)))])
        out = A.render_program(program, grid).to_numpy()
        expected = g.copy()
        expected[2:5, 2:5] = 6
        expected[3, 3] = 6
        assert np.array_equal(out, expected)

    def test_crop_program_via_action(self):
        g = np.zeros((5, 6), dtype=np.int32)
        g[1:3, 1:4] = 4
        g[4, 5] = 7
        grid = Grid(g)
        program = ObjectProgram(
            segmentation_variant=SegmentationVariant.S1_SAME_COLOR_4,
            rules=[ObjectRule(
                selector=_selector(PredExpr(op="test",
                                            args=("size", "==", "@rank_max"))),
                action=ActionRule(delta_type=DeltaType.CROP_TO,
                                  params={"region": RegionExpr(op="bbox_self")}))],
            output_spec=OutputSpec(mode="crop"))
        out = A.render_program(program, grid).to_numpy()
        assert np.array_equal(out, np.full((2, 3), 4, dtype=np.int32))

    def test_crop_program_via_output_spec_region(self):
        g = np.zeros((5, 6), dtype=np.int32)
        g[1:3, 1:4] = 4
        g[4, 5] = 7
        grid = Grid(g)
        region = RegionExpr(op="bbox",
                            args=(RefExpr(op="largest", args=(PredExpr(op="true"),)),))
        program = ObjectProgram(
            segmentation_variant=SegmentationVariant.S1_SAME_COLOR_4,
            output_spec=OutputSpec(mode="crop", region=region))
        out = A.render_program(program, grid).to_numpy()
        assert np.array_equal(out, np.full((2, 3), 4, dtype=np.int32))

    def test_constant_shape_fill(self):
        g = np.zeros((6, 6), dtype=np.int32)
        g[1:3, 1:3] = 4        # largest
        g[5, 5] = 7
        grid = Grid(g)
        fill = ColorExpr(op="color_of",
                         args=(RefExpr(op="largest", args=(PredExpr(op="true"),)),))
        program = ObjectProgram(
            segmentation_variant=SegmentationVariant.S1_SAME_COLOR_4,
            default_action=ActionRule(delta_type=DeltaType.DELETE),
            output_spec=OutputSpec(mode="constant_shape", height=2, width=2,
                                   fill=fill))
        out = A.render_program(program, grid).to_numpy()
        assert np.array_equal(out, np.full((2, 2), 4, dtype=np.int32))

    def test_multicolor_s3_translate(self):
        g = np.zeros((4, 6), dtype=np.int32)
        g[1, 1] = 1
        g[1, 2] = 2
        grid = Grid(g)
        assert isinstance(segment_s3(grid, 0)[0], MultiColorObject)
        program = ObjectProgram(
            segmentation_variant=SegmentationVariant.S3_MULTICOLOR_4,
            rules=[ObjectRule(
                selector=_selector(PredExpr(op="true")),
                action=ActionRule(delta_type=DeltaType.TRANSLATE,
                                  params={"vector": VecExpr(op="const",
                                                            args=(0, 2))}))])
        out = A.render_program(program, grid).to_numpy()
        expected = np.zeros((4, 6), dtype=np.int32)
        expected[1, 3] = 1
        expected[1, 4] = 2
        assert np.array_equal(out, expected)

    def test_round_trip_program_same_prediction(self):
        g = np.zeros((8, 8), dtype=np.int32)
        g[0:2, 4:6] = 3
        g[6:8, 3:7] = 8
        program = _gravity_program()
        back = ObjectProgram.from_json(program.to_json())
        assert np.array_equal(A.render_program(program, Grid(g)).to_numpy(),
                              A.render_program(back, Grid(g)).to_numpy())

    def test_program_apply_fn_contract(self):
        g = np.zeros((8, 8), dtype=np.int32)
        g[0:2, 4:6] = 3
        g[6:8, 3:7] = 8
        fn = A.program_apply_fn(_gravity_program())
        out = fn(g)
        assert isinstance(out, np.ndarray)
        assert np.array_equal(out, A.render_program(_gravity_program(),
                                                    Grid(g)).to_numpy())

    def test_undefined_expression_raises_evalerror_only(self):
        g = np.zeros((4, 4), dtype=np.int32)
        g[1, 1] = 3            # no container anywhere
        grid = Grid(g)
        color = ColorExpr(op="color_of", args=(RefExpr(op="container"),))
        program = ObjectProgram(
            segmentation_variant=SegmentationVariant.S1_SAME_COLOR_4,
            rules=[ObjectRule(selector=_selector(PredExpr(op="true")),
                              action=ActionRule(delta_type=DeltaType.RECOLOR,
                                                params={"color": color}))])
        with pytest.raises(EvalError):
            A.render_program(program, grid)

    def test_program_metrics(self):
        program = _gravity_program()
        assert program.worst_parameter_class is ParameterClass.RELATIONAL
        assert program.rules[0].selector.literals == 1
        assert program.expression_size >= 3
