"""Parameter-expression grammar (Section 2.4) — the heart of program CREATION.

Action parameters are expressions over registered features and relations,
not bare numbers.  Grammar (depth <= 2 in Stage 1):

    ColorExpr  := const(c) | color_of(REF) | most_common_color
                | least_common_color | color_map[color_of(self)]
    REF        := self | nearest_object(PRED) | nearest_object_of_color(c)
                | container(self) | contained(self) | largest(PRED)
                | unique(PRED) | matched_template
    VecExpr    := const(dr,dc) | vector_to(REF) | vector_to_border(direction)
                | gap_closing_vector(REF, axis) | scaled_unit(direction, ScalarExpr)
    RegionExpr := bbox(REF) | bbox(self) | grid_quadrant(q) | separator_cell(i,j)
    ScalarExpr := const(k) | size(self) | count(PRED) | hole_count(self)
    PredExpr   := true | test(feature, op, value) | and2(test, test)
                  (feature-predicate conjunctions of depth <= 2, Section 2.2 names)

Symbol leaves (AxisExpr / AngleExpr / DirectionExpr) carry the fixed
axis/angle/direction vocabularies of types.py so actions like reflect(axis)
keep their parameters as serializable Exprs (ExprType.AXIS/ANGLE/DIRECTION).

Every node is a frozen dataclass (types.Expr subclass) whose ``op`` comes
from the per-class GRAMMAR table and whose Expr children respect the
CHILD_TYPES signature.  Serialization is inherited from types.Expr
(registry-tagged dicts) — programs stay closure-free JSON.

Depth accounting: ``Expr.depth`` is structural (MDL); enumeration bounds
candidates by *production depth* (``production_depth``), which treats the
PRED argument of a REF/count production as atomic — the Section 2.4 grammar
gives PRED its own depth-2 budget as a separate bounded sub-language, so
``vector_to(nearest_object(PRED))`` is a legal depth-2 parameter expression.

enumerate_expressions() IS the hypothesis generator: it proposes every
well-typed expression up to depth 2 from the grammar plus the registered
feature vocabulary.  The inducer filters by zero-conflict fit + LOO.

color_map canonical encoding: args = (pairs,) where pairs is a sorted tuple
of (src_color, dst_color) int pairs (hashable + JSON-round-trippable via the
__tuple__ tag; a raw dict would stringify its keys under json).  Build with
``make_color_map({3: 8, ...})``; ``evaluate`` also tolerates a dict arg.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Iterator, Optional

from geocat_arc.perception.grid import Grid  # noqa: F401 (typing/doc)
from geocat_arc.perception.objects import ARCObject

from .features import (
    FeatureKind,
    get_feature,
    get_relation,
)
from .types import (
    ALIGNMENTS,
    ANGLES,
    AXES,
    DIRECTIONS,
    Expr,
    ExprType,
    GridContext,
    ParameterClass,
    register_expr_class,
)

MAX_DEPTH: int = 2  # Stage-1 hard cap (Section 2.4)

#: Unit displacement per direction symbol (shared with actions.py).
DIRECTION_UNITS: dict[str, tuple[int, int]] = {
    "up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1),
}


# ---------------------------------------------------------------------------
# Node classes.  Per class: GRAMMAR maps op -> tuple of child types, where a
# child type is an ExprType (an Expr subtree) or a python type (a literal).
# ---------------------------------------------------------------------------

@register_expr_class
@dataclass(frozen=True)
class RefExpr(Expr):
    """Object reference: resolves to an ARCObject (or EvalError, never None)."""
    rtype: ExprType = ExprType.REF

    GRAMMAR = {
        "self": (),
        "nearest_object": (ExprType.PREDICATE,),
        "nearest_object_of_color": (int,),
        "container": (),           # innermost object containing self
        "contained": (),           # unique object inside self
        "largest": (ExprType.PREDICATE,),
        "unique": (ExprType.PREDICATE,),   # the single object satisfying PRED
        "matched_template": (),    # the template object bound by correspondence
        "nearest_shape_twin": (),  # nearest OTHER object with the identical
                                   # bbox-relative cell mask (translation-
                                   # invariant, colors ignored) — template/
                                   # placeholder pairing
    }


@register_expr_class
@dataclass(frozen=True)
class ColorExpr(Expr):
    """Evaluates to a color int 0..9."""
    rtype: ExprType = ExprType.COLOR

    GRAMMAR = {
        "const": (int,),
        "color_of": (ExprType.REF,),
        "most_common_color": (),        # over ctx objects (excl. background)
        "least_common_color": (),
        "color_map": (tuple,),          # induced global map as sorted tuple of
                                        # (src, dst) pairs, applied to
                                        # color_of(self); GeoCat color-rule style
        "feature_map": (str, tuple),    # induced map from a registered SCALAR
                                        # feature's value to a color: args =
                                        # (feature_name, sorted ((val, color),..))
                                        # — ordinal recolors (e.g. size_rank ->
                                        # color) as a generic induced map
        "feature_affine": (str, int),   # color = feature value + offset
                                        # (round-9 lever 1, mined from LOO
                                        # fold-divergence: rank->sequential-
                                        # color tasks memorized as maps).
                                        # ONE bound literal vs one per map
                                        # entry — re-derives on any subset.
    }


@register_expr_class
@dataclass(frozen=True)
class VecExpr(Expr):
    """Evaluates to an integer (dr, dc) displacement."""
    rtype: ExprType = ExprType.VECTOR

    GRAMMAR = {
        "const": (int, int),
        "vector_to": (ExprType.REF,),           # o_ref.centroid - self.centroid, rounded
        "vector_to_border": (str,),             # direction in types.DIRECTIONS
        "gap_closing_vector": (ExprType.REF, str),  # move until adjacent; axis in AXES
        "scaled_unit": (str, ExprType.SCALAR),  # k * unit(direction)
        "step_toward": (ExprType.REF,),         # one unit step (sign of centroid
                                                # gap per axis) toward REF
        "slide_vector": (str,),                 # max motion along direction until
                                                # blocked by another object or the
                                                # border (obstacle-aware gravity)
        "align_vector": (ExprType.REF, str),    # translate along ONE axis so the
                                                # bbox origin aligns with REF's:
                                                # axis "vertical" -> (R0-r0, 0),
                                                # "horizontal" -> (0, C0-c0)
        "mirror_vector": (str,),                # translate to the position
                                                # mirrored about the grid center
                                                # along one axis (pattern kept):
                                                # "horizontal" -> (H-r1-r0, 0),
                                                # "vertical" -> (0, W-c1-c0)
        "reflect_across": (ExprType.REF, str),  # translate to the position
                                                # mirrored about REF's bbox
                                                # center line along one axis:
                                                # "horizontal" -> (R0+R1-r0-r1, 0)
                                                # "vertical" -> (0, C0+C1-c0-c1)
                                                # (pairs with REFLECT's vector
                                                # slot for true reflections
                                                # across a reference line)
    }


@register_expr_class
@dataclass(frozen=True)
class ScalarExpr(Expr):
    """Evaluates to a number (int; float for ratio-valued features)."""
    rtype: ExprType = ExprType.SCALAR

    GRAMMAR = {
        "const": (int,),
        "size": (),                 # size(self)
        "feature": (str,),          # any registered SCALAR feature of self, by name
        "count": (ExprType.PREDICATE,),  # objects in grid satisfying PRED
        "hole_count": (),           # hole_count(self)
    }


@register_expr_class
@dataclass(frozen=True)
class RegionExpr(Expr):
    """Evaluates to a bbox (r0, c0, r1, c1) in grid coordinates."""
    rtype: ExprType = ExprType.REGION

    GRAMMAR = {
        "bbox_self": (),
        "bbox": (ExprType.REF,),
        "grid_quadrant": (int,),        # q in 0..3 (TL, TR, BL, BR)
        "separator_cell": (int, int),   # block (i, j) of the separator partition
        "separator_block_self": (),     # the separator-partition block that
                                        # contains self's bbox (index-free)
    }


@register_expr_class
@dataclass(frozen=True)
class PredExpr(Expr):
    """Boolean predicate over one object's registered features (selectors and
    REF arguments).  ``test`` literals: (feature_name, cmp, value) where cmp
    is one of {"==", "!=", "<", ">", "<=", ">="}; value is a JSON-native
    constant OR the string "@rank_min"/"@rank_max" for argmin/argmax tests.
    """
    rtype: ExprType = ExprType.PREDICATE

    GRAMMAR = {
        "true": (),                                  # selects all (0 literals)
        "test": (str, str, object),                  # (feature, cmp, value)
        "and2": (ExprType.PREDICATE, ExprType.PREDICATE),  # conjunction, depth 2
        "relation_exists": (str, ExprType.PREDICATE),
        # ^ exists other object b: RELATION_REGISTRY[name](self, b) and PRED(b)
        # in_set (round 5): feature value-set membership — the DISJUNCTIVE
        # spelling the census showed was missing (~90% of failed selector
        # groups are value-set separable).  Values are induced from the
        # group's members like color_map keys; every element is a bound
        # literal (MDL) so single tests always outrank it when they exist.
        "in_set": (str, tuple),                      # (feature, values)
    }

    @property
    def literals(self) -> int:
        """Number of atomic tests (SelectorRule.literals; 'true' -> 0)."""
        if self.op == "true":
            return 0
        if self.op in ("test", "relation_exists"):
            return 1
        if self.op == "in_set":
            return len(self.args[1])
        return sum(a.literals for a in self.args if isinstance(a, PredExpr))


@register_expr_class
@dataclass(frozen=True)
class FreeSlotExpr(Expr):
    """A hole in a library-operator fragment (Section 5.3): args =
    (slot_name: str, expr_type_value: str).  Never evaluable — must be
    substituted by per-task induction before execution."""
    rtype: ExprType = ExprType.REF  # placeholder; actual type in args[1]

    GRAMMAR = {"free_slot": (str, str)}


@register_expr_class
@dataclass(frozen=True)
class AxisExpr(Expr):
    """Symbol leaf: an axis constant from types.AXES (reflect / gap axes)."""
    rtype: ExprType = ExprType.AXIS

    GRAMMAR = {"const": (str,)}


@register_expr_class
@dataclass(frozen=True)
class AngleExpr(Expr):
    """Symbol leaf: an angle constant from types.ANGLES (rotate)."""
    rtype: ExprType = ExprType.ANGLE

    GRAMMAR = {"const": (int,)}


@register_expr_class
@dataclass(frozen=True)
class DirectionExpr(Expr):
    """Symbol leaf: a direction constant from types.DIRECTIONS (motion)."""
    rtype: ExprType = ExprType.DIRECTION

    GRAMMAR = {"const": (str,)}


@register_expr_class
@dataclass(frozen=True)
class AlignExpr(Expr):
    """Symbol leaf: a copy-placement alignment constant from types.ALIGNMENTS
    (COPY 'targets' mode: place each copy bbox-center- or bbox-origin-aligned
    with its target object)."""
    rtype: ExprType = ExprType.ALIGN

    GRAMMAR = {"const": (str,)}


@register_expr_class
@dataclass(frozen=True)
class GrowModeExpr(Expr):
    """Symbol leaf: a growth-mode constant from growth.GROW_MODES
    (DeltaType.GROW, round 2)."""
    rtype: ExprType = ExprType.GROW_MODE

    GRAMMAR = {"const": (str,)}


@register_expr_class
@dataclass(frozen=True)
class PatternExpr(Expr):
    """Constant leaf: a bbox-origin-relative added-cell pattern — a sorted
    tuple of ((dr, dc), color) pairs (the GROW ``pattern`` fallback mode;
    ParameterClass CONSTANT by construction).

    MDL: every cell is a train-bound literal, so ``size`` counts them —
    a memorized 20-cell pattern must NOT outrank a 3-node generative
    spelling (COPY period, ray-to-border, ...) in canonical ranking."""
    rtype: ExprType = ExprType.PATTERN

    GRAMMAR = {"const": (tuple,)}

    @property
    def size(self) -> int:
        pat = self.args[0] if self.args else ()
        return 1 + len(pat)


def make_color_map(mapping: dict[int, int]) -> ColorExpr:
    """Canonical color_map constructor: dict -> sorted tuple of (src, dst)
    pairs (hashable, JSON-round-trippable)."""
    pairs = tuple(sorted((int(k), int(v)) for k, v in mapping.items()))
    return ColorExpr(op="color_map", args=(pairs,))


def make_feature_map(feature_name: str, mapping: dict) -> ColorExpr:
    """Canonical feature_map constructor: dict {feature_value: color} ->
    sorted tuple of (value, color) pairs (hashable, JSON-round-trippable).
    Values must be JSON-native scalars (int feature values in practice)."""
    pairs = tuple(sorted((int(k), int(v)) for k, v in mapping.items()))
    return ColorExpr(op="feature_map", args=(str(feature_name), pairs))


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

@dataclass
class EvalContext:
    """Runtime environment for expression evaluation.

    ``obj`` is the object bound to ``self``; ``grid_ctx`` supplies the grid
    and full object set; ``matched_template`` is the correspondence-bound
    template object (or None); ``bindings`` holds induced global values such
    as color maps keyed by expression identity, if the implementation caches.
    """
    obj: ARCObject
    grid_ctx: GridContext
    matched_template: Optional[ARCObject] = None
    bindings: dict[str, Any] = field(default_factory=dict)


class EvalError(Exception):
    """Raised when an expression is undefined for this object/context (e.g.
    container(self) with no container).  The inducer treats EvalError as a
    conflict for that candidate — never a crash."""


def _centroid_dist2(a: ARCObject, b: ARCObject) -> float:
    (ar, ac), (br, bc) = a.centroid, b.centroid
    return (ar - br) ** 2 + (ac - bc) ** 2


def _nearest(obj: ARCObject, candidates: list[ARCObject]) -> ARCObject:
    """Nearest candidate by centroid distance; deterministic tie-break by
    (distance, bbox r0, bbox c0, id).  EvalError if empty."""
    if not candidates:
        raise EvalError("no candidate object for nearest_* reference")
    return min(candidates, key=lambda b: (_centroid_dist2(obj, b),
                                          b.bounding_box[0], b.bounding_box[1],
                                          b.id))


def _rel_mask(obj: ARCObject) -> frozenset:
    """Bbox-relative cell mask (translation-invariant, colors ignored)."""
    r0, c0 = obj.bounding_box[:2]
    return frozenset((r - r0, c - c0) for r, c in obj.cells)


def _bbox_contains(outer: ARCObject, inner: ARCObject) -> bool:
    """perception.relations.contains semantics (bbox enclosure, id-guarded)."""
    from geocat_arc.perception.relations import contains
    return contains(outer, inner)


def _feature_value(name: str, obj: ARCObject, gctx: GridContext) -> Any:
    """Registered feature value of ``obj`` (KeyError -> EvalError)."""
    try:
        spec = get_feature(name)
    except KeyError as exc:
        raise EvalError(str(exc)) from None
    return spec.fn(obj, gctx)


def _resolve_ref(expr: RefExpr, obj: ARCObject, context: EvalContext) -> ARCObject:
    gctx = context.grid_ctx
    objs = gctx.objects
    op = expr.op
    if op == "self":
        return obj
    if op == "matched_template":
        if context.matched_template is None:
            raise EvalError("matched_template unbound in this context")
        return context.matched_template
    if op == "nearest_object":
        pred = expr.args[0]
        cands = [b for b in objs if b.id != obj.id
                 and evaluate(pred, b, context)]
        return _nearest(obj, cands)
    if op == "nearest_object_of_color":
        color = int(expr.args[0])
        cands = [b for b in objs if b.id != obj.id and b.color == color]
        return _nearest(obj, cands)
    if op == "nearest_shape_twin":
        mask = _rel_mask(obj)
        cands = [b for b in objs if b.id != obj.id and _rel_mask(b) == mask]
        return _nearest(obj, cands)
    if op == "container":
        cands = [b for b in objs if b.id != obj.id and _bbox_contains(b, obj)]
        if not cands:
            raise EvalError("object has no container")
        # innermost = smallest bbox area; deterministic tie-break
        def area(b: ARCObject) -> int:
            r0, c0, r1, c1 = b.bounding_box
            return (r1 - r0) * (c1 - c0)
        return min(cands, key=lambda b: (area(b), b.bounding_box[0],
                                         b.bounding_box[1], b.id))
    if op == "contained":
        cands = [b for b in objs if b.id != obj.id and _bbox_contains(obj, b)]
        # direct children only (not transitively nested inside another child)
        direct = [b for b in cands
                  if not any(c.id != b.id and _bbox_contains(c, b) for c in cands)]
        if len(direct) != 1:
            raise EvalError(f"contained(self) requires exactly one direct "
                            f"child, found {len(direct)}")
        return direct[0]
    if op == "largest":
        pred = expr.args[0]
        cands = [b for b in objs if evaluate(pred, b, context)]
        if not cands:
            raise EvalError("largest(PRED): no object satisfies PRED")
        return max(cands, key=lambda b: (b.size, -b.bounding_box[0],
                                         -b.bounding_box[1], -b.id))
    if op == "unique":
        pred = expr.args[0]
        cands = [b for b in objs if evaluate(pred, b, context)]
        if len(cands) != 1:
            raise EvalError(f"unique(PRED): {len(cands)} objects satisfy PRED")
        return cands[0]
    raise EvalError(f"unknown RefExpr op: {op}")


def _compare(cmp: str, a: Any, b: Any) -> bool:
    if isinstance(a, list):
        a = tuple(a)
    if isinstance(b, list):
        b = tuple(b)
    if cmp == "==":
        return a == b
    if cmp == "!=":
        return a != b
    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        raise EvalError(f"ordering comparison {cmp!r} on non-numeric values "
                        f"({a!r}, {b!r})")
    if cmp == "<":
        return a < b
    if cmp == ">":
        return a > b
    if cmp == "<=":
        return a <= b
    if cmp == ">=":
        return a >= b
    raise EvalError(f"unknown comparator: {cmp!r}")


def _eval_test(feature: str, cmp: str, value: Any, obj: ARCObject,
               context: EvalContext) -> bool:
    fval = _feature_value(feature, obj, context.grid_ctx)
    if value in ("@rank_min", "@rank_max"):
        objs = context.grid_ctx.objects
        if not objs:
            raise EvalError("@rank test with no objects in context")
        values = [_feature_value(feature, b, context.grid_ctx) for b in objs]
        try:
            extreme = min(values) if value == "@rank_min" else max(values)
        except TypeError:
            raise EvalError(f"@rank test on non-orderable feature {feature!r}") from None
        is_extreme = fval == extreme
        if cmp == "==":
            return is_extreme
        if cmp == "!=":
            return not is_extreme
        raise EvalError(f"@rank tests support ==/!= only, got {cmp!r}")
    return _compare(cmp, fval, value)


def _separator_blocks(grid: Grid) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
    """Row-ranges x col-ranges of the separator partition: a separator is any
    fully-uniform row/column; blocks are the maximal non-separator runs."""
    data = grid.to_numpy()
    h, w = data.shape
    sep_rows = [r for r in range(h) if len(set(data[r, :].tolist())) == 1]
    sep_cols = [c for c in range(w) if len(set(data[:, c].tolist())) == 1]

    def runs(n: int, seps: list[int]) -> list[tuple[int, int]]:
        sset = set(seps)
        out, start = [], None
        for i in range(n):
            if i in sset:
                if start is not None:
                    out.append((start, i))
                    start = None
            elif start is None:
                start = i
        if start is not None:
            out.append((start, n))
        return out

    return runs(h, sep_rows), runs(w, sep_cols)


def evaluate(expr: Expr, obj: ARCObject, context: EvalContext) -> Any:
    """Evaluate ``expr`` with ``self`` bound to ``obj``.

    Return type by node class: ColorExpr -> int, VecExpr -> (int, int),
    ScalarExpr -> int/float, RegionExpr -> (r0, c0, r1, c1), PredExpr -> bool,
    RefExpr -> ARCObject, AxisExpr/DirectionExpr -> str, AngleExpr -> int.
    Pure; consults only feature/relation registries + context.  Raises
    EvalError on every undefined case; FreeSlotExpr always raises EvalError
    (unbound hole).
    """
    gctx = context.grid_ctx

    if isinstance(expr, FreeSlotExpr):
        raise EvalError(f"unbound free slot {expr.args[0]!r} "
                        f"(library fragment not instantiated)")

    if isinstance(expr, RefExpr):
        return _resolve_ref(expr, obj, context)

    if isinstance(expr, ColorExpr):
        op = expr.op
        if op == "const":
            return int(expr.args[0])
        if op == "color_of":
            ref = evaluate(expr.args[0], obj, context)
            return int(ref.color)
        if op in ("most_common_color", "least_common_color"):
            if not gctx.objects:
                raise EvalError(f"{op} with no objects in context")
            counts: dict[int, int] = {}
            for b in gctx.objects:
                counts[int(b.color)] = counts.get(int(b.color), 0) + 1
            reverse = op == "most_common_color"
            # ties -> smaller color, deterministic
            ordered = sorted(counts.items(),
                             key=lambda kv: (-kv[1] if reverse else kv[1], kv[0]))
            return ordered[0][0]
        if op == "color_map":
            raw = expr.args[0]
            mapping = dict(raw) if not isinstance(raw, dict) else dict(raw)
            key = int(obj.color)
            if key not in mapping:
                raise EvalError(f"color_map has no entry for color {key}")
            return int(mapping[key])
        if op == "feature_map":
            name, raw = expr.args
            mapping = dict(raw) if not isinstance(raw, dict) else dict(raw)
            fval = _feature_value(name, obj, gctx)
            if isinstance(fval, bool) or not isinstance(
                    fval, (int, float)) or int(fval) != fval:
                raise EvalError(f"feature_map({name!r}) requires an integer "
                                f"feature value, got {fval!r}")
            key = int(fval)
            if key not in mapping:
                raise EvalError(f"feature_map({name!r}) has no entry for "
                                f"value {key}")
            return int(mapping[key])
        if op == "feature_affine":
            name, offset = expr.args
            fval = _feature_value(name, obj, gctx)
            if isinstance(fval, bool) or not isinstance(
                    fval, (int, float)) or int(fval) != fval:
                raise EvalError(f"feature_affine({name!r}) requires an "
                                f"integer feature value, got {fval!r}")
            color = int(fval) + int(offset)
            if not 0 <= color <= 9:
                raise EvalError(f"feature_affine({name!r}) out of color "
                                f"range: {color}")
            return color
        raise EvalError(f"unknown ColorExpr op: {op}")

    if isinstance(expr, VecExpr):
        op = expr.op
        if op == "const":
            return (int(expr.args[0]), int(expr.args[1]))
        if op == "vector_to":
            ref = evaluate(expr.args[0], obj, context)
            (sr, sc), (tr, tc) = obj.centroid, ref.centroid
            return (int(round(tr - sr)), int(round(tc - sc)))
        if op == "vector_to_border":
            direction = expr.args[0]
            r0, c0, r1, c1 = obj.bounding_box
            h, w = gctx.grid.height, gctx.grid.width
            if direction == "up":
                return (-r0, 0)
            if direction == "down":
                return (h - r1, 0)
            if direction == "left":
                return (0, -c0)
            if direction == "right":
                return (0, w - c1)
            raise EvalError(f"unknown direction: {direction!r}")
        if op == "gap_closing_vector":
            ref = evaluate(expr.args[0], obj, context)
            axis = expr.args[1]
            r0, c0, r1, c1 = obj.bounding_box
            R0, C0, R1, C1 = ref.bounding_box
            if axis == "vertical":       # motion along rows
                if R0 >= r1:             # target below
                    return (R0 - r1, 0)
                if R1 <= r0:             # target above
                    return (R1 - r0, 0)
                raise EvalError("gap_closing_vector: objects already overlap "
                                "along the vertical axis")
            if axis == "horizontal":     # motion along columns
                if C0 >= c1:             # target to the right
                    return (0, C0 - c1)
                if C1 <= c0:             # target to the left
                    return (0, C1 - c0)
                raise EvalError("gap_closing_vector: objects already overlap "
                                "along the horizontal axis")
            raise EvalError(f"gap_closing_vector: unsupported axis {axis!r}")
        if op == "scaled_unit":
            direction = expr.args[0]
            if direction not in DIRECTION_UNITS:
                raise EvalError(f"unknown direction: {direction!r}")
            k = evaluate(expr.args[1], obj, context)
            ur, uc = DIRECTION_UNITS[direction]
            return (int(round(k * ur)), int(round(k * uc)))
        if op == "step_toward":
            ref = evaluate(expr.args[0], obj, context)
            (sr, sc), (tr, tc) = obj.centroid, ref.centroid
            dr, dc = tr - sr, tc - sc
            return ((dr > 0) - (dr < 0), (dc > 0) - (dc < 0))
        if op == "align_vector":
            ref = evaluate(expr.args[0], obj, context)
            axis = expr.args[1]
            r0, c0 = obj.bounding_box[:2]
            R0, C0 = ref.bounding_box[:2]
            if axis == "vertical":       # motion along rows
                return (R0 - r0, 0)
            if axis == "horizontal":     # motion along columns
                return (0, C0 - c0)
            raise EvalError(f"align_vector: unsupported axis {axis!r}")
        if op == "mirror_vector":
            axis = expr.args[0]
            r0, c0, r1, c1 = obj.bounding_box
            h, w = gctx.grid.height, gctx.grid.width
            if axis == "horizontal":     # mirror row position (up/down)
                return (h - r1 - r0, 0)
            if axis == "vertical":       # mirror column position (left/right)
                return (0, w - c1 - c0)
            raise EvalError(f"mirror_vector: unsupported axis {axis!r}")
        if op == "reflect_across":
            ref = evaluate(expr.args[0], obj, context)
            axis = expr.args[1]
            r0, c0, r1, c1 = obj.bounding_box
            R0, C0, R1, C1 = ref.bounding_box
            if axis == "horizontal":   # mirror row position about ref's rows
                return ((R0 + R1) - (r0 + r1), 0)
            if axis == "vertical":     # mirror column position about ref's cols
                return (0, (C0 + C1) - (c0 + c1))
            raise EvalError(f"reflect_across: unsupported axis {axis!r}")
        if op == "slide_vector":
            direction = expr.args[0]
            if direction not in DIRECTION_UNITS:
                raise EvalError(f"unknown direction: {direction!r}")
            ur, uc = DIRECTION_UNITS[direction]
            h, w = gctx.grid.height, gctx.grid.width
            obstacles: set = set()
            for b in gctx.objects:
                if b.id != obj.id:
                    obstacles.update(b.cells)
            cells = set(obj.cells)
            k = 0
            while k <= h + w:
                nxt = {(r + ur, c + uc) for r, c in cells}
                if any(not (0 <= r < h and 0 <= c < w) for r, c in nxt) \
                        or (nxt & obstacles):
                    break
                cells = nxt
                k += 1
            return (k * ur, k * uc)
        raise EvalError(f"unknown VecExpr op: {op}")

    if isinstance(expr, ScalarExpr):
        op = expr.op
        if op == "const":
            return int(expr.args[0])
        if op == "size":
            return obj.size
        if op == "hole_count":
            return len(obj.holes)
        if op == "feature":
            name = expr.args[0]
            try:
                spec = get_feature(name)
            except KeyError as exc:
                raise EvalError(str(exc)) from None
            if spec.kind is not FeatureKind.SCALAR:
                raise EvalError(f"feature({name!r}) is {spec.kind.value}, "
                                f"not scalar")
            return spec.fn(obj, gctx)
        if op == "count":
            pred = expr.args[0]
            return sum(1 for b in gctx.objects if evaluate(pred, b, context))
        raise EvalError(f"unknown ScalarExpr op: {op}")

    if isinstance(expr, RegionExpr):
        op = expr.op
        if op == "bbox_self":
            return tuple(obj.bounding_box)
        if op == "bbox":
            ref = evaluate(expr.args[0], obj, context)
            return tuple(ref.bounding_box)
        if op == "grid_quadrant":
            q = int(expr.args[0])
            h, w = gctx.grid.height, gctx.grid.width
            mr, mc = h // 2, w // 2
            quads = {0: (0, 0, mr, mc), 1: (0, mc, mr, w),
                     2: (mr, 0, h, mc), 3: (mr, mc, h, w)}
            if q not in quads:
                raise EvalError(f"grid_quadrant index out of range: {q}")
            r0, c0, r1, c1 = quads[q]
            if r0 >= r1 or c0 >= c1:
                raise EvalError(f"grid_quadrant({q}) is empty on this grid")
            return (r0, c0, r1, c1)
        if op == "separator_cell":
            i, j = int(expr.args[0]), int(expr.args[1])
            row_runs, col_runs = _separator_blocks(gctx.grid)
            if not (0 <= i < len(row_runs)) or not (0 <= j < len(col_runs)):
                raise EvalError(f"separator_cell({i},{j}) out of range "
                                f"({len(row_runs)}x{len(col_runs)} blocks)")
            (r0, r1), (c0, c1) = row_runs[i], col_runs[j]
            return (r0, c0, r1, c1)
        if op == "separator_block_self":
            row_runs, col_runs = _separator_blocks(gctx.grid)
            r0, c0, r1, c1 = obj.bounding_box
            row = next(((a, b) for a, b in row_runs if a <= r0 and r1 <= b),
                       None)
            col = next(((a, b) for a, b in col_runs if a <= c0 and c1 <= b),
                       None)
            if row is None or col is None:
                raise EvalError("separator_block_self: object spans "
                                "separator lines (no single enclosing block)")
            return (row[0], col[0], row[1], col[1])
        raise EvalError(f"unknown RegionExpr op: {op}")

    if isinstance(expr, PredExpr):
        op = expr.op
        if op == "true":
            return True
        if op == "test":
            feature, cmp, value = expr.args
            return bool(_eval_test(feature, cmp, value, obj, context))
        if op == "in_set":
            feature, values = expr.args
            try:
                spec = get_feature(feature)
            except KeyError as exc:
                raise EvalError(str(exc)) from None
            v = spec.fn(obj, gctx)
            return v in set(values)
        if op == "and2":
            return bool(evaluate(expr.args[0], obj, context)
                        and evaluate(expr.args[1], obj, context))
        if op == "relation_exists":
            rel_name, pred = expr.args
            try:
                spec = get_relation(rel_name)
            except KeyError as exc:
                raise EvalError(str(exc)) from None
            for b in gctx.objects:
                if b.id == obj.id:
                    continue
                if spec.fn(obj, b, gctx) and evaluate(pred, b, context):
                    return True
            return False
        raise EvalError(f"unknown PredExpr op: {op}")

    if isinstance(expr, AxisExpr):
        axis = expr.args[0]
        if axis not in AXES:
            raise EvalError(f"unknown axis: {axis!r}")
        return axis

    if isinstance(expr, AngleExpr):
        angle = int(expr.args[0])
        if angle not in ANGLES:
            raise EvalError(f"unknown angle: {angle}")
        return angle

    if isinstance(expr, DirectionExpr):
        direction = expr.args[0]
        if direction not in DIRECTIONS:
            raise EvalError(f"unknown direction: {direction!r}")
        return direction

    if isinstance(expr, AlignExpr):
        align = expr.args[0]
        if align not in ALIGNMENTS:
            raise EvalError(f"unknown alignment: {align!r}")
        return align

    if isinstance(expr, GrowModeExpr):
        from .growth import GROW_MODES
        mode = expr.args[0]
        if mode not in GROW_MODES:
            raise EvalError(f"unknown grow mode: {mode!r}")
        return mode

    if isinstance(expr, PatternExpr):
        return tuple(expr.args[0])

    raise EvalError(f"unknown expression class: {type(expr).__name__}")


# ---------------------------------------------------------------------------
# Parameter-class classification (Requirement 2.4.1)
# ---------------------------------------------------------------------------

#: Ops that dereference another object (contract: RefExpr other than 'self',
#: relation_exists, vector_to*, gap_closing_vector).
_RELATIONAL_OPS = frozenset({
    "nearest_object", "nearest_object_of_color", "container", "contained",
    "largest", "unique", "matched_template", "nearest_shape_twin",
    "relation_exists", "vector_to", "vector_to_border", "gap_closing_vector",
    "step_toward", "slide_vector", "align_vector", "mirror_vector",
    "reflect_across",
})
#: Ops that read (only) features of the bound object / grid context.
_FEATURE_OPS = frozenset({
    "self", "size", "hole_count", "feature", "count", "test", "color_of",
    "bbox_self", "bbox", "most_common_color", "least_common_color",
    "separator_block_self", "feature_affine",
})
_MAP_OPS = frozenset({"color_map", "feature_map"})
# everything else ("const", "true", "and2", "scaled_unit", "grid_quadrant",
# "separator_cell", "free_slot", symbol consts) is neutral / constant.


def _walk(expr: Expr) -> Iterator[Expr]:
    yield expr
    for a in expr.args:
        if isinstance(a, Expr):
            yield from _walk(a)


def parameter_class_of(expr: Expr) -> ParameterClass:
    """Classify an expression per Requirement 2.4.1:
    RELATIONAL if it dereferences another object (RefExpr other than 'self',
    relation_exists, vector_to*, gap_closing_vector); FEATURE if it reads
    only self's features; INDUCED_MAP if it contains a color_map node;
    CONSTANT if every leaf is const.  Worst wins on mixed trees."""
    has_relational = has_feature = has_map = False
    for node in _walk(expr):
        if node.op in _RELATIONAL_OPS:
            has_relational = True
        elif node.op in _MAP_OPS:
            has_map = True
        elif node.op in _FEATURE_OPS:
            has_feature = True
    met: list[ParameterClass] = []
    if has_relational:
        met.append(ParameterClass.RELATIONAL)
    if has_feature and not has_relational:
        met.append(ParameterClass.FEATURE)
    if has_map:
        met.append(ParameterClass.INDUCED_MAP)
    if not met:
        met.append(ParameterClass.CONSTANT)
    return ParameterClass.worst(met)


# ---------------------------------------------------------------------------
# Serialization (thin aliases over types.Expr — implemented)
# ---------------------------------------------------------------------------

def serialize_expr(expr: Expr) -> dict:
    """Expr -> JSON-able dict (registry-tagged)."""
    return expr.to_dict()


def deserialize_expr(d: dict) -> Expr:
    """Inverse of serialize_expr."""
    return Expr.from_dict(d)


# ---------------------------------------------------------------------------
# Enumeration — the candidate generator (program creation)
# ---------------------------------------------------------------------------

@dataclass
class EnumerationContext:
    """Bounds the enumeration to values actually present in the train data
    (colors seen, directions, scalar feature names, observed constants) so
    the candidate stream is finite and cheapest-first.

    ``observed_colors``: colors present across train grids (for const/
    nearest_object_of_color).  ``observed_constants``: raw delta parameter
    values seen (const proposals are drawn ONLY from these — constants are
    the last resort, Requirement 2.4.1); int entries feed scalar consts and
    scalar tests, (dr, dc) tuples feed vector consts, str entries feed
    categorical tests, and dict / tuple-of-pairs entries are interpreted as
    induced color maps (the inducer fits the map, enumeration replays it).
    ``scalar_features`` / ``bool_features`` etc.: registered feature names by
    kind, from features.features_of_kind.
    """
    observed_colors: list[int] = field(default_factory=list)
    observed_constants: list[Any] = field(default_factory=list)
    scalar_features: list[str] = field(default_factory=list)
    bool_features: list[str] = field(default_factory=list)
    color_features: list[str] = field(default_factory=list)
    categorical_features: list[str] = field(default_factory=list)
    relation_names: list[str] = field(default_factory=list)


def production_depth(expr: Expr) -> int:
    """Grammar-production depth: the PRED argument of a non-PRED production
    (REF's nearest_object/largest/unique, ScalarExpr count) counts as atomic
    because the Section 2.4 grammar gives PRED its own depth-2 budget.
    Inside the PRED sub-language (and2, relation_exists) depth is structural.
    """
    kids = []
    for a in expr.args:
        if isinstance(a, Expr):
            if isinstance(a, PredExpr) and not isinstance(expr, PredExpr):
                continue
            kids.append(production_depth(a))
    return 1 + (max(kids) if kids else 0)


def _stable_key(expr: Expr) -> str:
    """Deterministic total order tiebreaker."""
    return json.dumps(expr.to_dict(), sort_keys=True, default=str)


def _dedup(exprs: list[Expr]) -> list[Expr]:
    seen: set[Expr] = set()
    out: list[Expr] = []
    for e in exprs:
        if e not in seen:
            seen.add(e)
            out.append(e)
    return out


def _value_boundness(expr: Expr) -> int:
    """1 when the expression binds a train-observed VALUE literal (a raw
    color argument or a non-bool, non-@rank test value), else 0.  Closed
    vocabularies (bool test values, @rank sentinels, axis/direction symbols)
    are unbound."""
    if isinstance(expr, RefExpr) and expr.op == "nearest_object_of_color":
        return 1
    if isinstance(expr, PredExpr) and expr.op == "test":
        v = expr.args[2]
        if not isinstance(v, bool) and isinstance(v, (int, str)) \
                and v not in ("@rank_min", "@rank_max"):
            return 1
    for a in expr.args:
        if isinstance(a, Expr) and _value_boundness(a):
            return 1
    return 0


def _pref_sorted(exprs: list[Expr]) -> list[Expr]:
    """Preference order 2.4.1: relational > feature > induced_map > constant,
    then smaller size, then stable serialization key."""
    return sorted(_dedup(exprs),
                  key=lambda e: (parameter_class_of(e).rank, e.size,
                                 _stable_key(e)))


def _int_constants(context: EnumerationContext) -> list[int]:
    return sorted({int(v) for v in context.observed_constants
                   if isinstance(v, int) and not isinstance(v, bool)})


def _vector_constants(context: EnumerationContext) -> list[tuple[int, int]]:
    vecs = set()
    for v in context.observed_constants:
        if isinstance(v, (tuple, list)) and len(v) == 2 \
                and all(isinstance(x, int) and not isinstance(x, bool) for x in v):
            vecs.add((int(v[0]), int(v[1])))
    return sorted(vecs)


def _color_map_constants(context: EnumerationContext) -> list[tuple]:
    """Induced color maps supplied by the inducer via observed_constants."""
    maps = set()
    for v in context.observed_constants:
        if isinstance(v, dict) and v \
                and all(isinstance(k, int) and isinstance(x, int)
                        for k, x in v.items()):
            maps.add(tuple(sorted((int(k), int(x)) for k, x in v.items())))
        elif isinstance(v, (tuple, list)) and v \
                and all(isinstance(p, (tuple, list)) and len(p) == 2
                        and all(isinstance(x, int) for x in p) for p in v):
            maps.add(tuple(sorted((int(p[0]), int(p[1])) for p in v)))
    return sorted(maps)


def _single_tests(context: EnumerationContext) -> list[PredExpr]:
    """All single feature tests over registered names with values from the
    train-observed context (deterministic construction order)."""
    tests: list[PredExpr] = []
    for name in sorted(set(context.bool_features)):
        tests.append(PredExpr(op="test", args=(name, "==", True)))
        tests.append(PredExpr(op="test", args=(name, "==", False)))
    ints = _int_constants(context)
    for name in sorted(set(context.scalar_features)):
        tests.append(PredExpr(op="test", args=(name, "==", "@rank_max")))
        tests.append(PredExpr(op="test", args=(name, "==", "@rank_min")))
        for k in ints:
            tests.append(PredExpr(op="test", args=(name, "==", k)))
            tests.append(PredExpr(op="test", args=(name, ">", k)))
            tests.append(PredExpr(op="test", args=(name, "<", k)))
    colors = sorted({int(c) for c in context.observed_colors})
    for name in sorted(set(context.color_features)):
        for c in colors:
            tests.append(PredExpr(op="test", args=(name, "==", c)))
            tests.append(PredExpr(op="test", args=(name, "!=", c)))
    strs = sorted({v for v in context.observed_constants if isinstance(v, str)})
    for name in sorted(set(context.categorical_features)):
        for s in strs:
            tests.append(PredExpr(op="test", args=(name, "==", s)))
    return _dedup(tests)


def _small_preds(context: EnumerationContext) -> list[PredExpr]:
    """Bounded predicate set used INSIDE REF productions (keeps the ref
    cross-product finite): true + bool tests + color-equality tests."""
    preds: list[PredExpr] = [PredExpr(op="true")]
    for name in sorted(set(context.bool_features)):
        preds.append(PredExpr(op="test", args=(name, "==", True)))
        preds.append(PredExpr(op="test", args=(name, "==", False)))
    colors = sorted({int(c) for c in context.observed_colors})
    for name in sorted(set(context.color_features)):
        for c in colors:
            preds.append(PredExpr(op="test", args=(name, "==", c)))
    return _dedup(preds)


def _enumerate_refs(context: EnumerationContext,
                    include_self: bool = False) -> list[RefExpr]:
    refs: list[RefExpr] = []
    if include_self:
        refs.append(RefExpr(op="self"))
    refs.append(RefExpr(op="container"))
    refs.append(RefExpr(op="contained"))
    refs.append(RefExpr(op="matched_template"))
    refs.append(RefExpr(op="nearest_shape_twin"))
    for c in sorted({int(c) for c in context.observed_colors}):
        refs.append(RefExpr(op="nearest_object_of_color", args=(c,)))
    for pred in _small_preds(context):
        refs.append(RefExpr(op="nearest_object", args=(pred,)))
        refs.append(RefExpr(op="largest", args=(pred,)))
        refs.append(RefExpr(op="unique", args=(pred,)))
    return _dedup(refs)


def _enumerate_scalars(context: EnumerationContext,
                       max_depth: int) -> list[ScalarExpr]:
    out: list[ScalarExpr] = [ScalarExpr(op="size"), ScalarExpr(op="hole_count")]
    for name in sorted(set(context.scalar_features)):
        out.append(ScalarExpr(op="feature", args=(name,)))
    if max_depth >= 2:
        for pred in _small_preds(context):
            out.append(ScalarExpr(op="count", args=(pred,)))
    for k in _int_constants(context):
        out.append(ScalarExpr(op="const", args=(k,)))
    return _dedup(out)


def enumerate_expressions(rtype: ExprType, context: EnumerationContext,
                          max_depth: int = MAX_DEPTH) -> Iterator[Expr]:
    """Yield every well-typed expression of type ``rtype`` up to
    ``max_depth`` (production depth), cheapest-first within type:

      order = relational ops > feature ops > induced maps > constants
      (preference lattice 2.4.1), and within a class smaller ``size`` first.

    Deterministic (fixed grammar-table order + sorted context lists); no
    duplicates (nodes are hashable).  PRED enumeration yields 'true', then
    all single tests over registered features with values from context, then
    relation_exists forms, then and2 conjunctions of two distinct tests
    (depth 2 cap).
    """
    nested = max_depth >= 2

    if rtype is ExprType.PREDICATE:
        # Contract-fixed staged order (not class-sorted): 'true' first.
        yield PredExpr(op="true")
        tests = _single_tests(context)
        yield from tests
        if nested:
            # Inner vocabulary = _small_preds (true + bool tests + color
            # tests): closed/low-cardinality tests only, so shape-match-to-
            # reference-group selectors (e.g. exists b: same_shape_normalized
            # and b.is_contained) are spellable while the cross product stays
            # bounded and fold-deterministic.
            for rel in sorted(set(context.relation_names)):
                for p in _small_preds(context):
                    yield PredExpr(op="relation_exists", args=(rel, p))
            for i, t1 in enumerate(tests):
                for t2 in tests[i + 1:]:
                    yield PredExpr(op="and2", args=(t1, t2))
        return

    if rtype is ExprType.REF:
        # Fold-determinism: train-value-free references (container, twin,
        # nearest_object over bool tests, ...) strictly before references
        # bound to observed literals (nearest_object_of_color(c), color-
        # literal predicates) — an N-1-pair reinduction fold must converge
        # on the same spelling the full train set picks (cf. the round-1
        # selector-tier fix).
        refs = list(_enumerate_refs(context, include_self=True))
        yield from sorted(refs,
                          key=lambda e: (parameter_class_of(e).rank,
                                         _value_boundness(e), e.size,
                                         _stable_key(e)))
        return

    if rtype is ExprType.COLOR:
        out: list[Expr] = []
        if nested:
            for ref in _enumerate_refs(context, include_self=True):
                out.append(ColorExpr(op="color_of", args=(ref,)))
        out.append(ColorExpr(op="most_common_color"))
        out.append(ColorExpr(op="least_common_color"))
        for pairs in _color_map_constants(context):
            out.append(ColorExpr(op="color_map", args=(pairs,)))
        for c in sorted({int(c) for c in context.observed_colors}):
            out.append(ColorExpr(op="const", args=(c,)))
        yield from _pref_sorted(out)
        return

    if rtype is ExprType.VECTOR:
        out = []
        if nested:
            refs = _enumerate_refs(context, include_self=False)
            for ref in refs:
                out.append(VecExpr(op="vector_to", args=(ref,)))
            for ref in refs:
                for axis in ("horizontal", "vertical"):
                    out.append(VecExpr(op="gap_closing_vector", args=(ref, axis)))
            for ref in refs:
                out.append(VecExpr(op="step_toward", args=(ref,)))
            for ref in refs:
                for axis in ("horizontal", "vertical"):
                    out.append(VecExpr(op="align_vector", args=(ref, axis)))
            for ref in refs:
                for axis in ("horizontal", "vertical"):
                    out.append(VecExpr(op="reflect_across", args=(ref, axis)))
            for direction in DIRECTIONS:
                for s in _enumerate_scalars(context, max_depth=1):
                    out.append(VecExpr(op="scaled_unit", args=(direction, s)))
        for direction in DIRECTIONS:
            out.append(VecExpr(op="vector_to_border", args=(direction,)))
            out.append(VecExpr(op="slide_vector", args=(direction,)))
        for axis in ("horizontal", "vertical"):
            out.append(VecExpr(op="mirror_vector", args=(axis,)))
        for dr, dc in _vector_constants(context):
            out.append(VecExpr(op="const", args=(dr, dc)))
        yield from _pref_sorted(out)
        return

    if rtype is ExprType.SCALAR:
        yield from _pref_sorted(list(_enumerate_scalars(context, max_depth)))
        return

    if rtype is ExprType.REGION:
        out = [RegionExpr(op="bbox_self"),
               RegionExpr(op="separator_block_self")]
        if nested:
            for ref in _enumerate_refs(context, include_self=False):
                out.append(RegionExpr(op="bbox", args=(ref,)))
        for q in range(4):
            out.append(RegionExpr(op="grid_quadrant", args=(q,)))
        for i in range(3):
            for j in range(3):
                out.append(RegionExpr(op="separator_cell", args=(i, j)))
        yield from _pref_sorted(out)
        return

    if rtype is ExprType.AXIS:
        for axis in AXES:
            yield AxisExpr(op="const", args=(axis,))
        return

    if rtype is ExprType.ANGLE:
        for angle in ANGLES:
            yield AngleExpr(op="const", args=(angle,))
        return

    if rtype is ExprType.DIRECTION:
        for direction in DIRECTIONS:
            yield DirectionExpr(op="const", args=(direction,))
        return

    if rtype is ExprType.ALIGN:
        for align in ALIGNMENTS:
            yield AlignExpr(op="const", args=(align,))
        return

    raise ValueError(f"enumerate_expressions: unsupported rtype {rtype!r}")


def substitute_free_slots(expr: Expr, bindings: dict[str, Expr]) -> Expr:
    """Replace every FreeSlotExpr(slot_name, _) in ``expr`` with
    bindings[slot_name]; raises KeyError on missing slot.  Used when a
    library-operator fragment is instantiated per task (Section 5.3)."""
    if isinstance(expr, FreeSlotExpr):
        slot_name = expr.args[0]
        if slot_name not in bindings:
            raise KeyError(f"no binding for free slot {slot_name!r}")
        return bindings[slot_name]

    def sub(a: Any) -> Any:
        if isinstance(a, Expr):
            return substitute_free_slots(a, bindings)
        if isinstance(a, tuple):
            return tuple(sub(x) for x in a)
        return a

    new_args = tuple(sub(a) for a in expr.args)
    if new_args == expr.args:
        return expr
    return type(expr)(op=expr.op, args=new_args)
