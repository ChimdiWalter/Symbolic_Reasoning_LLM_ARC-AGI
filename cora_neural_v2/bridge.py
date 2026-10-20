"""The ncv2-g1 compiler bridge: typed AST -> native CORA program dict -> the UNCHANGED native interpreter.

`compile_program(ast)` emits exactly the dict native `program_from_dict` reads (ObjectProgram, or ComposedProgram
for `seq`). Every AST op maps to one existing native construct; nothing is rendered by any other code path.

- Bound variables (`rule_with`) are substituted by their REF expressions. Native RefExprs are evaluated relative to
  the object being transformed, so substitution preserves meaning exactly.
- Holes refuse to compile.
- `execute(ast, grid)` runs the compiled program with native `render_program`. A native EvalError (an expression
  undefined on this input) returns None, exactly as the native search treats it.
"""
import numpy as np

from cora_neural_v2.rast import ASTError, N, typecheck

STATS = {"executions": 0, "eval_errors": 0, "other_errors": 0}


def _e(cls, op, *args):
    return {"expr_class": cls, "op": op, "args": list(args)}


def _tup(xs):
    return {"__tuple__": [(_tup(x) if isinstance(x, tuple) else x) for x in xs]}


def _expr(n, env):
    """A value node -> a native Expr dict."""
    o, a = n.op, n.args
    if o == "hole":
        raise ASTError(f"cannot compile a hole of type {a[0]}")
    if o == "var":
        return _expr(env[a[0]], env)
    table = {
        "true": lambda: _e("PredExpr", "true"),
        "test": lambda: _e("PredExpr", "test", a[0], a[1], a[2]),
        "and": lambda: _e("PredExpr", "and2", _expr(a[0], env), _expr(a[1], env)),
        "in_set": lambda: _e("PredExpr", "in_set", a[0], _tup(a[1])),
        "exists": lambda: _e("PredExpr", "relation_exists", a[0], _expr(a[1], env)),
        "self": lambda: _e("RefExpr", "self"),
        "nearest": lambda: _e("RefExpr", "nearest_object", _expr(a[0], env)),
        "nearest_of_color": lambda: _e("RefExpr", "nearest_object_of_color", a[0]),
        "container": lambda: _e("RefExpr", "container"),
        "contained": lambda: _e("RefExpr", "contained"),
        "largest": lambda: _e("RefExpr", "largest", _expr(a[0], env)),
        "unique": lambda: _e("RefExpr", "unique", _expr(a[0], env)),
        "shape_twin": lambda: _e("RefExpr", "nearest_shape_twin"),
        "color": lambda: _e("ColorExpr", "const", a[0]),
        "color_of": lambda: _e("ColorExpr", "color_of", _expr(a[0], env)),
        "most_common_color": lambda: _e("ColorExpr", "most_common_color"),
        "least_common_color": lambda: _e("ColorExpr", "least_common_color"),
        "color_map": lambda: _e("ColorExpr", "color_map", _tup(tuple(sorted(a[0])))),
        "feature_map": lambda: _e("ColorExpr", "feature_map", a[0], _tup(tuple(sorted(a[1])))),
        "feature_affine": lambda: _e("ColorExpr", "feature_affine", a[0], a[1]),
        "vec": lambda: _e("VecExpr", "const", a[0], a[1]),
        "vector_to": lambda: _e("VecExpr", "vector_to", _expr(a[0], env)),
        "to_border": lambda: _e("VecExpr", "vector_to_border", a[0]),
        "gap_closing": lambda: _e("VecExpr", "gap_closing_vector", _expr(a[0], env), a[1]),
        "scaled": lambda: _e("VecExpr", "scaled_unit", a[0], _expr(a[1], env)),
        "step_toward": lambda: _e("VecExpr", "step_toward", _expr(a[0], env)),
        "slide": lambda: _e("VecExpr", "slide_vector", a[0]),
        "align_to": lambda: _e("VecExpr", "align_vector", _expr(a[0], env), a[1]),
        "mirror": lambda: _e("VecExpr", "mirror_vector", a[0]),
        "reflect_across": lambda: _e("VecExpr", "reflect_across", _expr(a[0], env), a[1]),
        "int": lambda: _e("ScalarExpr", "const", a[0]),
        "size": lambda: _e("ScalarExpr", "size"),
        "feature": lambda: _e("ScalarExpr", "feature", a[0]),
        "count": lambda: _e("ScalarExpr", "count", _expr(a[0], env)),
        "hole_count": lambda: _e("ScalarExpr", "hole_count"),
        "bbox_self": lambda: _e("RegionExpr", "bbox_self"),
        "bbox": lambda: _e("RegionExpr", "bbox", _expr(a[0], env)),
        "quadrant": lambda: _e("RegionExpr", "grid_quadrant", a[0]),
        "separator_cell": lambda: _e("RegionExpr", "separator_cell", a[0], a[1]),
        "separator_block_self": lambda: _e("RegionExpr", "separator_block_self"),
        "axis": lambda: _e("AxisExpr", "const", a[0]),
        "angle": lambda: _e("AngleExpr", "const", a[0]),
        "dir": lambda: _e("DirectionExpr", "const", a[0]),
        "align_mode": lambda: _e("AlignExpr", "const", a[0]),
    }
    if o not in table:
        raise ASTError(f"{o} is not a value node")
    return table[o]()


def _numbered(prefix, vecs, env):
    if len(vecs) > 99:
        raise ASTError("at most 99 numbered copy slots")
    return {f"{prefix}{i:02d}": _expr(v, env) for i, v in enumerate(vecs)}   # zero-padded: lexical = numeric order


def _params(n, env):
    """An ACTION node -> (native delta_type, {param name: Expr dict})."""
    o, a = n.op, n.args
    X = lambda x: _expr(x, env)                                     # noqa: E731
    if o in ("keep", "delete"):
        return o, {}
    simple = {"translate": ("translate", "vector"), "recolor": ("recolor", "color"), "move_to": ("move_to", "position"),
              "scale": ("scale", "factor"), "paint": ("paint", "source"), "crop_to": ("crop_to", "region")}
    if o in simple:
        d, p = simple[o]
        return d, {p: X(a[0])}
    if o == "copy_targets":
        return "copy", {"targets": X(a[0]), "align": X(a[1])}
    if o == "copy_offsets":
        return "copy", _numbered("offset", a[0], env)
    if o == "copy_period":
        return "copy", {"period": X(a[0]), **_numbered("offset", a[1], env)}
    if o == "copy_rays":
        return "copy", _numbered("ray", a[0], env)
    if o == "move_until_adjacent":
        return "move_until_adjacent", {"direction": X(a[0])}
    if o == "move_until_adjacent_to":
        return "move_until_adjacent", {"direction": X(a[0]), "target": X(a[1])}
    if o == "reflect":
        return "reflect", {"axis": X(a[0])}
    if o == "reflect_shift":
        return "reflect", {"axis": X(a[0]), "vector": X(a[1])}
    if o == "rotate":
        return "rotate", {"angle": X(a[0])}
    if o == "rotate_shift":
        return "rotate", {"angle": X(a[0]), "vector": X(a[1])}
    if o == "connect":
        return "connect", {"target": X(a[0]), "color": X(a[1])}
    if o == "fill_line":                                            # native reads axis/extent as args[0] of an Expr
        return "fill_line", {"axis": _e("AxisExpr", "const", a[0]), "color": X(a[1]),
                             "extent": _e("AxisExpr", "const", a[2])}
    if o == "copy_part":
        return "copy_part", {"window": X(a[0]), "placement": X(a[1])}
    if o == "extract_part":
        return "extract_part", {"source": X(a[0]), "transform_k": _e("ScalarExpr", "const", a[1]),
                                "transform_flip": _e("ScalarExpr", "const", a[2]), "placement": X(a[3])}
    if o == "composite":
        params = {}
        for i, part in enumerate(a[0]):
            if part.op == "composite":
                raise ASTError("nested composite is not allowed")
            d, ps = _params(part, env)
            if not ps:
                raise ASTError(f"composite part {part.op} has no parameters; native composite cannot carry it")
            params.update({f"{i}:{d}:{k}": v for k, v in ps.items()})
        return "composite", params
    if o == "hole":
        raise ASTError("cannot compile a hole of type ACTION")
    raise ASTError(f"{o} is not an action")


def _parameter_class(params):
    from geocat_arc.object_reasoning.expressions import parameter_class_of
    from geocat_arc.object_reasoning.types import Expr, ParameterClass
    if not params:
        return "constant"
    return ParameterClass.worst([parameter_class_of(Expr.from_dict(v)) for v in params.values()]).value


def _action(n, env):
    d, ps = _params(n, env)
    return {"delta_type": d, "params": ps, "parameter_class": _parameter_class(ps)}


def _literals(p):
    o = p.op
    if o == "true":
        return 0
    if o in ("test", "exists"):
        return 1
    if o == "in_set":
        return len(p.args[1])
    if o == "and":
        return _literals(p.args[0]) + _literals(p.args[1])
    return 0


def _rule(r, env):
    if r.op == "hole":
        raise ASTError("cannot compile a hole of type RULE")
    if r.op == "rule_with":
        local = dict(env)
        for name, ref in r.args[0]:
            local[name] = ref
        pred, act = r.args[1], r.args[2]
    else:
        local, (pred, act) = env, r.args
    return {"selector": {"predicate": _expr(pred, local), "literals": _literals(pred)}, "action": _action(act, local)}


def _render(n, env):
    spec = {"mode": "same_as_input", "region": None, "height": None, "width": None, "background": None, "fill": None}
    if n.op == "crop":
        spec.update(mode="crop", region=_expr(n.args[0], env))
    elif n.op == "crop_by_action":
        spec.update(mode="crop")
    elif n.op == "constant_shape":
        spec.update(mode="constant_shape", height=n.args[0], width=n.args[1], background=_expr(n.args[2], env))
    elif n.op != "same_as_input":
        raise ASTError(f"{n.op} is not a render mode")
    return spec


def _object_program(p):
    view, rules, default, render = p.args
    return {"segmentation_variant": view, "rules": [_rule(r, {}) for r in rules],
            "default_action": {"delta_type": default, "params": {}, "parameter_class": "constant"},
            "output_spec": _render(render, {}), "library_operators_used": []}


def compile_program(p):
    """A PROGRAM node -> the native program dict. Typechecks first; refuses holes."""
    if typecheck(p) != "PROGRAM":
        raise ASTError("not a PROGRAM")
    if p.op == "program":
        return _object_program(p)
    stages = []

    def flat(q):
        if q.op == "seq":
            for s in q.args[0]:
                flat(s)
        else:
            stages.append(_object_program(q))
    flat(p)
    if len(stages) == 1:
        return stages[0]
    return {"program_class": "composed", "stages": stages, "stage_provenance": []}


def native_program(p):
    from geocat_arc.object_reasoning.types import program_from_dict
    import geocat_arc.object_reasoning.expressions  # noqa: F401  (registers the Expr classes)
    return program_from_dict(compile_program(p))


def run_native_dict(d, grid):
    """Execute a native program dict with the unchanged native interpreter (None on a native EvalError)."""
    from geocat_arc.object_reasoning.actions import render_program
    from geocat_arc.object_reasoning.expressions import EvalError
    from geocat_arc.object_reasoning.types import program_from_dict
    from geocat_arc.perception.grid import Grid
    STATS["executions"] += 1
    try:
        out = render_program(program_from_dict(d), Grid(np.asarray(grid, dtype=np.int32)))
    except EvalError:
        STATS["eval_errors"] += 1
        return None
    except Exception:                                               # noqa: BLE001  (counted, as in cora_neural_v1)
        STATS["other_errors"] += 1
        return None
    return np.asarray(out.to_numpy(), dtype=np.int64)


def execute(p, grid):
    return run_native_dict(compile_program(p), grid)


def fit(p, pairs):
    """(fits every demonstration, per-pair wrong-cell counts; None = no output or a shape mismatch)."""
    d = compile_program(p)
    wrong = []
    for a, b in pairs:
        out = run_native_dict(d, a)
        B = np.asarray(b)
        wrong.append(None if out is None or out.shape != B.shape else int((out != B).sum()))
        if wrong[-1] != 0:
            break
    return len(wrong) == len(pairs) and all(w == 0 for w in wrong), wrong
