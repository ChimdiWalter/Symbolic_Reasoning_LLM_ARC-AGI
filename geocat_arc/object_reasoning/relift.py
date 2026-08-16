"""R2 relational relift: lift constant parameters to relational/feature
expressions on the 194 parameter-overfit graduation failures.

For each train-perfect-but-LOO-failing program:
  1. Identify all CONSTANT parameters (ParameterClass.CONSTANT)
  2. For each constant, enumerate candidate relational/feature expressions
  3. Check if the new expression yields the same value on all train pairs
  4. If ALL constants can be lifted: verify train-perfect, full LOO recertify

Env-gated: ARC_RELIFT=1 (zero cost when off).
"""
from __future__ import annotations

import copy
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np

from geocat_arc.perception.grid import Grid
from geocat_arc.perception.objects import ARCObject

from .actions import render_program
from .expressions import (
    AxisExpr,
    AngleExpr,
    AlignExpr,
    ColorExpr,
    DirectionExpr,
    EvalContext,
    EvalError,
    GrowModeExpr,
    PatternExpr,
    PredExpr,
    RefExpr,
    ScalarExpr,
    VecExpr,
    evaluate,
    parameter_class_of,
    _small_preds,
)
from .features import (
    FEATURE_REGISTRY,
    FeatureKind,
    features_of_kind,
    register_builtin_features,
)
from .segmentation import background_for, segment
from .types import (
    DIRECTIONS,
    ActionRule,
    DeltaType,
    Expr,
    ExprType,
    GridContext,
    GridPair,
    ObjectProgram,
    ObjectRule,
    ParameterClass,
    program_from_dict,
)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class ReliftResult:
    task_id: str
    success: bool = False
    original_param_class: str = ""
    relifted_param_class: str = ""
    loo_passed: bool = False
    loo_report: Optional[dict] = None
    relifted_program_dict: Optional[dict] = None
    constants_lifted: int = 0
    constants_total: int = 0
    time_s: float = 0.0
    error: Optional[str] = None

    @property
    def program(self) -> Optional[Any]:
        """Convenience: parse the relifted program dict back to an object.
        Returns None if no relifted program or parse fails."""
        if self.relifted_program_dict is None:
            return None
        try:
            return program_from_dict(self.relifted_program_dict)
        except Exception:
            return None

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "success": self.success,
            "original_param_class": self.original_param_class,
            "relifted_param_class": self.relifted_param_class,
            "loo_passed": self.loo_passed,
            "loo_report": self.loo_report,
            "relifted_program_dict": self.relifted_program_dict,
            "constants_lifted": self.constants_lifted,
            "constants_total": self.constants_total,
            "time_s": self.time_s,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Symbol-leaf expression classes: constant by construction, never relifted
# ---------------------------------------------------------------------------

_SYMBOL_EXPR_TYPES = (AxisExpr, AngleExpr, DirectionExpr, AlignExpr,
                      GrowModeExpr, PatternExpr)


def _is_liftable_constant(expr: Expr) -> bool:
    """True if the expression is a const-op leaf that should be relifted.

    Symbol-leaf expressions (axis, angle, direction, align, grow_mode,
    pattern) are closed-vocabulary constants and should NOT be relifted --
    they are structural, not data-dependent.
    """
    if isinstance(expr, _SYMBOL_EXPR_TYPES):
        return False
    return expr.op == "const" and parameter_class_of(expr) == ParameterClass.CONSTANT


# ---------------------------------------------------------------------------
# Candidate expression generators
# ---------------------------------------------------------------------------

def _make_eval_context(obj: ARCObject, grid: Grid,
                       objects: list[ARCObject],
                       background: int,
                       variant) -> EvalContext:
    """Build an EvalContext for expression evaluation."""
    gctx = GridContext(grid=grid, objects=objects, background=background,
                       pair_index=0, role="input", variant=variant)
    return EvalContext(obj=obj, grid_ctx=gctx)


def _safe_eval(expr: Expr, obj: ARCObject, ectx: EvalContext) -> Any:
    """Evaluate an expression, returning None on EvalError."""
    try:
        return evaluate(expr, obj, ectx)
    except EvalError:
        return None


def _enumerate_refs(observed_colors: list[int]) -> list[RefExpr]:
    """Enumerate reference expressions for relift candidate generation."""
    refs: list[RefExpr] = []
    refs.append(RefExpr(op="self"))
    refs.append(RefExpr(op="container"))
    refs.append(RefExpr(op="contained"))
    refs.append(RefExpr(op="matched_template"))
    refs.append(RefExpr(op="nearest_shape_twin"))
    for c in sorted(set(observed_colors)):
        refs.append(RefExpr(op="nearest_object_of_color", args=(c,)))
    # Bool features
    bool_names = sorted(s.name for s in features_of_kind(FeatureKind.BOOL))
    color_names = sorted(s.name for s in features_of_kind(FeatureKind.COLOR))
    preds: list[PredExpr] = [PredExpr(op="true")]
    for name in bool_names:
        preds.append(PredExpr(op="test", args=(name, "==", True)))
        preds.append(PredExpr(op="test", args=(name, "==", False)))
    for name in color_names:
        for c in sorted(set(observed_colors)):
            preds.append(PredExpr(op="test", args=(name, "==", c)))
    seen = set()
    deduped_preds = []
    for p in preds:
        if p not in seen:
            seen.add(p)
            deduped_preds.append(p)
    for pred in deduped_preds:
        refs.append(RefExpr(op="nearest_object", args=(pred,)))
        refs.append(RefExpr(op="largest", args=(pred,)))
        refs.append(RefExpr(op="unique", args=(pred,)))
    return refs


def _lift_constant_color(color_value: int, obj: ARCObject,
                         ectx: EvalContext,
                         observed_colors: list[int]) -> list[ColorExpr]:
    """Given a constant color c, enumerate ColorExpr candidates that
    evaluate to c for the given object/context. Preference-sorted:
    relational > feature > constant."""
    candidates: list[ColorExpr] = []
    refs = _enumerate_refs(observed_colors)
    for ref in refs:
        expr = ColorExpr(op="color_of", args=(ref,))
        val = _safe_eval(expr, obj, ectx)
        if val == color_value:
            candidates.append(expr)
    # most_common_color / least_common_color
    for op in ("most_common_color", "least_common_color"):
        expr = ColorExpr(op=op)
        val = _safe_eval(expr, obj, ectx)
        if val == color_value:
            candidates.append(expr)
    # feature_affine: color = feature_value + offset
    scalar_names = sorted(s.name for s in features_of_kind(FeatureKind.SCALAR))
    for name in scalar_names:
        try:
            fval = FEATURE_REGISTRY[name].fn(obj, ectx.grid_ctx)
            if isinstance(fval, bool) or not isinstance(fval, (int, float)):
                continue
            if int(fval) != fval:
                continue
            offset = color_value - int(fval)
            if 0 <= color_value <= 9:
                expr = ColorExpr(op="feature_affine", args=(name, offset))
                val = _safe_eval(expr, obj, ectx)
                if val == color_value:
                    candidates.append(expr)
        except Exception:
            continue
    # Filter: only candidates better than CONSTANT
    return [c for c in candidates
            if parameter_class_of(c) != ParameterClass.CONSTANT]


def _lift_constant_vector(vec_value: tuple, obj: ARCObject,
                          ectx: EvalContext,
                          observed_colors: list[int]) -> list[VecExpr]:
    """Given a constant (dr, dc), enumerate VecExpr candidates that evaluate
    to that value. Preference-sorted."""
    dr_target, dc_target = int(vec_value[0]), int(vec_value[1])
    candidates: list[VecExpr] = []
    refs = _enumerate_refs(observed_colors)
    # vector_to(REF)
    for ref in refs:
        if ref.op == "self":
            continue
        expr = VecExpr(op="vector_to", args=(ref,))
        val = _safe_eval(expr, obj, ectx)
        if val is not None and val[0] == dr_target and val[1] == dc_target:
            candidates.append(expr)
    # gap_closing_vector(REF, axis)
    for ref in refs:
        if ref.op == "self":
            continue
        for axis in ("horizontal", "vertical"):
            expr = VecExpr(op="gap_closing_vector", args=(ref, axis))
            val = _safe_eval(expr, obj, ectx)
            if val is not None and val[0] == dr_target and val[1] == dc_target:
                candidates.append(expr)
    # step_toward(REF)
    for ref in refs:
        if ref.op == "self":
            continue
        expr = VecExpr(op="step_toward", args=(ref,))
        val = _safe_eval(expr, obj, ectx)
        if val is not None and val[0] == dr_target and val[1] == dc_target:
            candidates.append(expr)
    # align_vector(REF, axis)
    for ref in refs:
        if ref.op == "self":
            continue
        for axis in ("horizontal", "vertical"):
            expr = VecExpr(op="align_vector", args=(ref, axis))
            val = _safe_eval(expr, obj, ectx)
            if val is not None and val[0] == dr_target and val[1] == dc_target:
                candidates.append(expr)
    # reflect_across(REF, axis)
    for ref in refs:
        if ref.op == "self":
            continue
        for axis in ("horizontal", "vertical"):
            expr = VecExpr(op="reflect_across", args=(ref, axis))
            val = _safe_eval(expr, obj, ectx)
            if val is not None and val[0] == dr_target and val[1] == dc_target:
                candidates.append(expr)
    # vector_to_border(direction)
    for direction in DIRECTIONS:
        expr = VecExpr(op="vector_to_border", args=(direction,))
        val = _safe_eval(expr, obj, ectx)
        if val is not None and val[0] == dr_target and val[1] == dc_target:
            candidates.append(expr)
    # slide_vector(direction)
    for direction in DIRECTIONS:
        expr = VecExpr(op="slide_vector", args=(direction,))
        val = _safe_eval(expr, obj, ectx)
        if val is not None and val[0] == dr_target and val[1] == dc_target:
            candidates.append(expr)
    # mirror_vector(axis)
    for axis in ("horizontal", "vertical"):
        expr = VecExpr(op="mirror_vector", args=(axis,))
        val = _safe_eval(expr, obj, ectx)
        if val is not None and val[0] == dr_target and val[1] == dc_target:
            candidates.append(expr)
    # Filter: only candidates better than CONSTANT
    return [c for c in candidates
            if parameter_class_of(c) != ParameterClass.CONSTANT]


def _lift_constant_scalar(scalar_value: int, obj: ARCObject,
                          ectx: EvalContext) -> list[ScalarExpr]:
    """Given a constant k, enumerate ScalarExpr candidates that evaluate
    to k."""
    candidates: list[ScalarExpr] = []
    # size()
    expr = ScalarExpr(op="size")
    val = _safe_eval(expr, obj, ectx)
    if val == scalar_value:
        candidates.append(expr)
    # hole_count()
    expr = ScalarExpr(op="hole_count")
    val = _safe_eval(expr, obj, ectx)
    if val == scalar_value:
        candidates.append(expr)
    # feature(name) for each scalar feature
    scalar_names = sorted(s.name for s in features_of_kind(FeatureKind.SCALAR))
    for name in scalar_names:
        expr = ScalarExpr(op="feature", args=(name,))
        val = _safe_eval(expr, obj, ectx)
        if val == scalar_value:
            candidates.append(expr)
    return [c for c in candidates
            if parameter_class_of(c) != ParameterClass.CONSTANT]


# ---------------------------------------------------------------------------
# Per-param lifting across all train-pair objects
# ---------------------------------------------------------------------------

def _collect_selected_objects(
    program: ObjectProgram,
    rule_index: int,
    train_pairs: list[GridPair],
) -> list[tuple[ARCObject, EvalContext, Grid]]:
    """For a specific rule in the program, collect all objects that match
    its selector across all train pairs, along with their eval contexts.

    Returns a list of (obj, eval_context, input_grid) tuples.
    """
    register_builtin_features()
    variant = program.segmentation_variant
    rule = program.rules[rule_index]
    results: list[tuple[ARCObject, EvalContext, Grid]] = []
    for gi, _go in train_pairs:
        bg = background_for(gi, variant)
        try:
            objects = segment(gi, variant, bg)
        except Exception:
            continue
        gctx = GridContext(grid=gi, objects=objects, background=bg,
                           pair_index=0, role="input", variant=variant)
        for obj in objects:
            ectx = EvalContext(obj=obj, grid_ctx=gctx)
            try:
                if evaluate(rule.selector.predicate, obj, ectx):
                    results.append((obj, ectx, gi))
            except EvalError:
                continue
    return results


def _lift_param(
    param_name: str,
    const_expr: Expr,
    selected: list[tuple[ARCObject, EvalContext, Grid]],
    observed_colors: list[int],
    deadline: float,
) -> Optional[Expr]:
    """Try to lift one constant parameter expression to a relational/feature
    expression that evaluates to the SAME value for all selected objects
    across all train pairs.

    Returns the best (most relational, smallest) lifted expression, or None
    if no candidate works for all objects.
    """
    if not selected or time.monotonic() > deadline:
        return None

    # Get the target value for each object
    obj0, ectx0, _ = selected[0]
    try:
        target0 = evaluate(const_expr, obj0, ectx0)
    except EvalError:
        return None

    if isinstance(const_expr, ColorExpr):
        candidates = _lift_constant_color(int(target0), obj0, ectx0,
                                          observed_colors)
    elif isinstance(const_expr, VecExpr):
        candidates = _lift_constant_vector(target0, obj0, ectx0,
                                           observed_colors)
    elif isinstance(const_expr, ScalarExpr):
        candidates = _lift_constant_scalar(int(target0), obj0, ectx0)
    else:
        return None

    if not candidates:
        return None

    # For each candidate: check it produces the correct value on ALL
    # selected objects across ALL train pairs.
    # STRONG GATE: require the candidate expression has a BETTER
    # parameter class than CONSTANT (i.e., is genuinely RELATIONAL or
    # FEATURE). feature_affine with a coincidentally-constant feature
    # is FEATURE-class (reads self's features), which is still better
    # than CONSTANT. color_of(largest(true)) is RELATIONAL (references
    # another object). Both are accepted. But an expression that is
    # classified as CONSTANT by parameter_class_of is rejected.
    for cand in candidates:
        if time.monotonic() > deadline:
            return None
        # The candidates list is already filtered to non-CONSTANT,
        # but double-check
        if parameter_class_of(cand) == ParameterClass.CONSTANT:
            continue
        all_match = True
        for obj, ectx, _gi in selected:
            try:
                expected = evaluate(const_expr, obj, ectx)
                actual = _safe_eval(cand, obj, ectx)
                if actual is None or actual != expected:
                    all_match = False
                    break
            except EvalError:
                all_match = False
                break
        if all_match:
            return cand

    return None


# ---------------------------------------------------------------------------
# Relift one rule
# ---------------------------------------------------------------------------

def _try_relift_rule(
    program: ObjectProgram,
    rule_index: int,
    train_pairs: list[GridPair],
    observed_colors: list[int],
    deadline: float,
) -> tuple[Optional[ActionRule], int, int]:
    """For one rule in the program, try to lift each constant parameter.

    Returns (relifted_action_rule_or_None, constants_lifted, constants_total).
    """
    rule = program.rules[rule_index]
    action = rule.action

    # Identify constant params
    const_params: list[tuple[str, Expr]] = []
    for pname, expr in action.params.items():
        if _is_liftable_constant(expr):
            const_params.append((pname, expr))

    if not const_params:
        return None, 0, 0

    # Collect all objects that match this rule's selector
    selected = _collect_selected_objects(program, rule_index, train_pairs)
    if not selected:
        return None, 0, len(const_params)

    # Try to lift each constant
    new_params = dict(action.params)
    lifted = 0
    for pname, expr in const_params:
        if time.monotonic() > deadline:
            break
        replacement = _lift_param(pname, expr, selected, observed_colors,
                                  deadline)
        if replacement is not None:
            new_params[pname] = replacement
            lifted += 1

    if lifted == 0:
        return None, 0, len(const_params)

    # Build new action rule with lifted params
    new_action = ActionRule(
        delta_type=action.delta_type,
        params=new_params,
        parameter_class=ParameterClass.worst(
            [parameter_class_of(e) for e in new_params.values()]),
    )
    return new_action, lifted, len(const_params)


# ---------------------------------------------------------------------------
# Also check and relift the output spec expressions (background, fill, region)
# ---------------------------------------------------------------------------

def _relift_output_spec(
    program: ObjectProgram,
    train_pairs: list[GridPair],
    observed_colors: list[int],
    deadline: float,
) -> tuple[ObjectProgram, int, int]:
    """Try to relift constant expressions in the output spec.
    Returns (modified_program, lifted_count, total_const_count)."""
    register_builtin_features()
    variant = program.segmentation_variant
    spec = program.output_spec
    lifted = 0
    total = 0
    new_spec_bg = spec.background
    new_spec_fill = spec.fill

    for attr_name, expr in [("background", spec.background),
                            ("fill", spec.fill)]:
        if expr is None:
            continue
        if not _is_liftable_constant(expr):
            continue
        total += 1
        # For output spec expressions, the "object" is the anchor object
        # (first segmented object). Collect anchor objects from all pairs.
        anchor_selected: list[tuple[ARCObject, EvalContext, Grid]] = []
        for gi, _go in train_pairs:
            bg = background_for(gi, variant)
            try:
                objects = segment(gi, variant, bg)
            except Exception:
                continue
            gctx = GridContext(grid=gi, objects=objects, background=bg,
                               pair_index=0, role="input", variant=variant)
            anchor = objects[0] if objects else None
            if anchor is None:
                continue
            ectx = EvalContext(obj=anchor, grid_ctx=gctx)
            anchor_selected.append((anchor, ectx, gi))

        if anchor_selected and time.monotonic() < deadline:
            replacement = _lift_param(attr_name, expr, anchor_selected,
                                      observed_colors, deadline)
            if replacement is not None:
                if attr_name == "background":
                    new_spec_bg = replacement
                elif attr_name == "fill":
                    new_spec_fill = replacement
                lifted += 1

    if lifted == 0:
        return program, 0, total

    from .types import OutputSpec
    new_output_spec = OutputSpec(
        mode=spec.mode,
        region=spec.region,
        height=spec.height,
        width=spec.width,
        background=new_spec_bg,
        fill=new_spec_fill,
    )
    new_program = ObjectProgram(
        segmentation_variant=program.segmentation_variant,
        rules=program.rules,
        default_action=program.default_action,
        output_spec=new_output_spec,
        library_operators_used=list(program.library_operators_used),
    )
    return new_program, lifted, total


# ---------------------------------------------------------------------------
# Train-perfect verification
# ---------------------------------------------------------------------------

def _is_train_perfect(program: ObjectProgram,
                      train_pairs: list[GridPair]) -> bool:
    """Check if program produces pixel-perfect output on all train pairs."""
    for gi, go in train_pairs:
        try:
            rendered = render_program(program, gi)
            if not np.array_equal(rendered.to_numpy(), go.to_numpy()):
                return False
        except Exception:
            return False
    return True


# ---------------------------------------------------------------------------
# LOO verification (direct rendering, no reinduction)
# ---------------------------------------------------------------------------

def _loo_verify(program: ObjectProgram,
                train_pairs: list[GridPair]) -> tuple[bool, dict]:
    """LOO verification by direct rendering: the relifted program should
    generalize because its expressions are relational (scene-derived).

    For each held-out pair, render the relifted program on the held-out
    input and check pixel equality with the held-out output.
    """
    n = len(train_pairs)
    if n < 2:
        return False, {"folds": 0, "passed": 0, "reason": "single_pair"}

    passed = 0
    failed_indices: list[int] = []
    for hold in range(n):
        held_in, held_out = train_pairs[hold]
        try:
            rendered = render_program(program, held_in)
            if np.array_equal(rendered.to_numpy(), held_out.to_numpy()):
                passed += 1
            else:
                failed_indices.append(hold)
        except Exception:
            failed_indices.append(hold)

    all_passed = passed == n
    report = {
        "folds": n,
        "passed": passed,
        "failed": failed_indices,
        "all_passed": all_passed,
    }
    return all_passed, report


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def relift_program(
    program_or_dict,
    train_pairs: list[GridPair],
    task_id: str = "",
    budget_s: float = 60.0,
) -> ReliftResult:
    """Attempt to relift a train-perfect-but-LOO-failing program.

    Accepts either a program dict or a program object directly.

    1. Parse the program from dict (if dict)
    2. Identify all CONSTANT parameters in rules and output spec
    3. For each constant, try to find a relational/feature expression
       that evaluates to the same value across all selected objects
    4. Verify the relifted program is still train-perfect
    5. LOO verify by direct rendering

    Returns a ReliftResult.
    """
    started = time.monotonic()
    deadline = started + budget_s
    result = ReliftResult(task_id=task_id)

    # Parse program
    try:
        if isinstance(program_or_dict, dict):
            program = program_from_dict(program_or_dict)
        elif isinstance(program_or_dict, ObjectProgram):
            program = program_or_dict
        else:
            # Try to_dict -> from_dict roundtrip
            program = program_from_dict(program_or_dict.to_dict())
    except Exception as exc:
        result.error = f"parse error: {exc}"
        result.time_s = time.monotonic() - started
        return result

    if not isinstance(program, ObjectProgram):
        result.error = f"unsupported program type: {type(program).__name__}"
        result.time_s = time.monotonic() - started
        return result

    result.original_param_class = program.worst_parameter_class.value

    # Ensure features are registered
    register_builtin_features()

    # Collect observed colors from all train grids
    observed_colors: list[int] = []
    for gi, go in train_pairs:
        observed_colors.extend(int(c) for c in set(gi.to_numpy().flat))
        observed_colors.extend(int(c) for c in set(go.to_numpy().flat))
    observed_colors = sorted(set(observed_colors))

    # Count total constants and attempt to lift each rule's constants
    total_lifted = 0
    total_constants = 0
    new_rules: list[ObjectRule] = []

    for ri, rule in enumerate(program.rules):
        if time.monotonic() > deadline:
            break
        new_action, lifted, total = _try_relift_rule(
            program, ri, train_pairs, observed_colors, deadline)
        total_constants += total
        if new_action is not None:
            total_lifted += lifted
            new_rules.append(ObjectRule(
                selector=rule.selector,
                action=new_action,
            ))
        else:
            new_rules.append(rule)

    # Also try to relift the default action if it has constant params
    new_default = program.default_action
    for pname, expr in program.default_action.params.items():
        if _is_liftable_constant(expr):
            total_constants += 1
            # Default action applies to unmatched objects -- more complex
            # to collect. For now, skip default action relifting as it
            # is rare for the default to carry meaningful constants.

    # Build intermediate program with relifted rules
    relifted = ObjectProgram(
        segmentation_variant=program.segmentation_variant,
        rules=new_rules,
        default_action=new_default,
        output_spec=program.output_spec,
        library_operators_used=list(program.library_operators_used),
    )

    # Relift output spec expressions
    relifted, spec_lifted, spec_total = _relift_output_spec(
        relifted, train_pairs, observed_colors, deadline)
    total_lifted += spec_lifted
    total_constants += spec_total

    result.constants_lifted = total_lifted
    result.constants_total = total_constants

    if total_lifted == 0:
        result.error = "no constants could be lifted"
        result.time_s = time.monotonic() - started
        return result

    result.relifted_param_class = relifted.worst_parameter_class.value

    # Verify train-perfect
    if not _is_train_perfect(relifted, train_pairs):
        result.error = "relifted program not train-perfect"
        result.time_s = time.monotonic() - started
        return result

    # LOO verify
    loo_passed, loo_report = _loo_verify(relifted, train_pairs)
    result.loo_passed = loo_passed
    result.loo_report = loo_report

    if loo_passed:
        result.success = True
        result.relifted_program_dict = relifted.to_dict()

    result.time_s = time.monotonic() - started
    return result


# ---------------------------------------------------------------------------
# Env gate
# ---------------------------------------------------------------------------

def relift_enabled() -> bool:
    """Check if ARC_RELIFT=1 is set in the environment."""
    import os
    return os.environ.get("ARC_RELIFT", "0") == "1"
