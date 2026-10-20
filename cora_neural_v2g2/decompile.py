"""Native ObjectProgram / ComposedProgram dict -> the ncv2-g1 typed AST: the inverse of `cora_neural_v2.bridge`.

It lets a native program, such as one of native's own certificates, be read as a typed hypothesis. It also enforces
the exposure boundary: anything ncv2-g1 does not expose raises ASTError rather than being approximated. That covers
grow, synth_copy, matched_template, copy k / placement / keep_original, connect turn, crop_to tiling, the spec fill,
library operators and non-keep/delete defaults.

The tests check compile(decompile(d)) == d, ignoring the parameter_class metadata.
"""
from cora_neural_v2.rast import ASTError, N


def _args(e):
    a = e.get("args", [])
    return [_un(x) for x in a]


def _un(x):
    if isinstance(x, dict) and "__tuple__" in x:
        return tuple(_un(y) for y in x["__tuple__"])
    if isinstance(x, list):
        return tuple(_un(y) for y in x)
    return x


def expr(e):
    if not isinstance(e, dict) or "expr_class" not in e:
        raise ASTError(f"not a native expression: {e!r}")
    cls, op, raw = e["expr_class"], e["op"], e.get("args", [])
    a = [_un(x) for x in raw]
    sub = lambda i: expr(raw[i])                                           # noqa: E731
    table = {
        ("PredExpr", "true"): lambda: N("true", ()),
        ("PredExpr", "test"): lambda: N("test", (a[0], a[1], a[2])),
        ("PredExpr", "and2"): lambda: N("and", (sub(0), sub(1))),
        ("PredExpr", "in_set"): lambda: N("in_set", (a[0], tuple(a[1]))),
        ("PredExpr", "relation_exists"): lambda: N("exists", (a[0], sub(1))),
        ("RefExpr", "self"): lambda: N("self", ()),
        ("RefExpr", "nearest_object"): lambda: N("nearest", (sub(0),)),
        ("RefExpr", "nearest_object_of_color"): lambda: N("nearest_of_color", (a[0],)),
        ("RefExpr", "container"): lambda: N("container", ()),
        ("RefExpr", "contained"): lambda: N("contained", ()),
        ("RefExpr", "largest"): lambda: N("largest", (sub(0),)),
        ("RefExpr", "unique"): lambda: N("unique", (sub(0),)),
        ("RefExpr", "nearest_shape_twin"): lambda: N("shape_twin", ()),
        ("ColorExpr", "const"): lambda: N("color", (a[0],)),
        ("ColorExpr", "color_of"): lambda: N("color_of", (sub(0),)),
        ("ColorExpr", "most_common_color"): lambda: N("most_common_color", ()),
        ("ColorExpr", "least_common_color"): lambda: N("least_common_color", ()),
        ("ColorExpr", "color_map"): lambda: N("color_map", (tuple(tuple(p) for p in a[0]),)),
        ("ColorExpr", "feature_map"): lambda: N("feature_map", (a[0], tuple(tuple(p) for p in a[1]))),
        ("ColorExpr", "feature_affine"): lambda: N("feature_affine", (a[0], a[1])),
        ("VecExpr", "const"): lambda: N("vec", (a[0], a[1])),
        ("VecExpr", "vector_to"): lambda: N("vector_to", (sub(0),)),
        ("VecExpr", "vector_to_border"): lambda: N("to_border", (a[0],)),
        ("VecExpr", "gap_closing_vector"): lambda: N("gap_closing", (sub(0), a[1])),
        ("VecExpr", "scaled_unit"): lambda: N("scaled", (a[0], sub(1))),
        ("VecExpr", "step_toward"): lambda: N("step_toward", (sub(0),)),
        ("VecExpr", "slide_vector"): lambda: N("slide", (a[0],)),
        ("VecExpr", "align_vector"): lambda: N("align_to", (sub(0), a[1])),
        ("VecExpr", "mirror_vector"): lambda: N("mirror", (a[0],)),
        ("VecExpr", "reflect_across"): lambda: N("reflect_across", (sub(0), a[1])),
        ("ScalarExpr", "const"): lambda: N("int", (a[0],)),
        ("ScalarExpr", "size"): lambda: N("size", ()),
        ("ScalarExpr", "feature"): lambda: N("feature", (a[0],)),
        ("ScalarExpr", "count"): lambda: N("count", (sub(0),)),
        ("ScalarExpr", "hole_count"): lambda: N("hole_count", ()),
        ("RegionExpr", "bbox_self"): lambda: N("bbox_self", ()),
        ("RegionExpr", "bbox"): lambda: N("bbox", (sub(0),)),
        ("RegionExpr", "grid_quadrant"): lambda: N("quadrant", (a[0],)),
        ("RegionExpr", "separator_cell"): lambda: N("separator_cell", (a[0], a[1])),
        ("RegionExpr", "separator_block_self"): lambda: N("separator_block_self", ()),
        ("AxisExpr", "const"): lambda: N("axis", (a[0],)),
        ("AngleExpr", "const"): lambda: N("angle", (a[0],)),
        ("DirectionExpr", "const"): lambda: N("dir", (a[0],)),
        ("AlignExpr", "const"): lambda: N("align_mode", (a[0],)),
    }
    if (cls, op) not in table:
        raise ASTError(f"{cls}.{op} is not exposed in ncv2-g1")
    return table[(cls, op)]()


def _const_arg(e, cls):
    if not (isinstance(e, dict) and e.get("expr_class") == cls and e.get("op") == "const"):
        raise ASTError(f"expected a constant {cls}, got {e!r}")
    return _un(e["args"][0])


def _numbered(params, prefix):
    keys = sorted(k for k in params if k.startswith(prefix))
    if [k for k in keys] != [f"{prefix}{i:02d}" for i in range(len(keys))]:
        raise ASTError(f"non-contiguous {prefix} slots: {keys}")
    return tuple(expr(params[k]) for k in keys)


def action(delta, params):
    p = dict(params)
    simple = {"translate": ("vector",), "recolor": ("color",), "move_to": ("position",), "scale": ("factor",),
              "paint": ("source",), "crop_to": ("region",)}
    if delta in ("keep", "delete"):
        if p:
            raise ASTError(f"{delta} with parameters")
        return N(delta, ())
    if delta in simple:
        if set(p) != set(simple[delta]):
            raise ASTError(f"{delta} parameters {sorted(p)} are not exposed")
        return N(delta, (expr(p[simple[delta][0]]),))
    if delta == "copy":
        if {"k", "placement", "keep_original"} & set(p):
            raise ASTError("copy k / placement / keep_original are not exposed")
        if "targets" in p:
            if set(p) != {"targets", "align"}:
                raise ASTError(f"copy targets with {sorted(p)}")
            return N("copy_targets", (expr(p["targets"]), expr(p["align"])))
        if "period" in p:
            return N("copy_period", (expr(p.pop("period")), _numbered(p, "offset")))
        if any(k.startswith("ray") for k in p):
            return N("copy_rays", (_numbered(p, "ray"),))
        return N("copy_offsets", (_numbered(p, "offset"),))
    if delta == "move_until_adjacent":
        if "target" in p:
            return N("move_until_adjacent_to", (expr(p["direction"]), expr(p["target"])))
        return N("move_until_adjacent", (expr(p["direction"]),))
    if delta in ("reflect", "rotate"):
        key = "axis" if delta == "reflect" else "angle"
        if "vector" in p:
            return N(f"{delta}_shift", (expr(p[key]), expr(p["vector"])))
        return N(delta, (expr(p[key]),))
    if delta == "connect":
        if "turn" in p:
            raise ASTError("connect turn is not exposed")
        return N("connect", (expr(p["target"]), expr(p["color"])))
    if delta == "fill_line":
        return N("fill_line", (_const_arg(p["axis"], "AxisExpr"), expr(p["color"]), _const_arg(p["extent"], "AxisExpr")))
    if delta == "copy_part":
        return N("copy_part", (expr(p["window"]), expr(p["placement"])))
    if delta == "extract_part":
        return N("extract_part", (expr(p["source"]), _const_arg(p["transform_k"], "ScalarExpr"),
                                  _const_arg(p["transform_flip"], "ScalarExpr"), expr(p["placement"])))
    if delta == "composite":
        parts = {}
        for k, v in p.items():
            i, d, name = k.split(":", 2)
            parts.setdefault(int(i), (d, {}))[1][name] = v
        return N("composite", (tuple(action(d, ps) for _, (d, ps) in sorted(parts.items())),))
    raise ASTError(f"delta {delta} is not exposed in ncv2-g1")


def _render(spec):
    if spec.get("fill") is not None:
        raise ASTError("output_spec fill is not exposed")
    m = spec["mode"]
    if m == "same_as_input":
        return N("same_as_input", ())
    if m == "crop":
        return N("crop_by_action", ()) if spec.get("region") is None else N("crop", (expr(spec["region"]),))
    if m == "constant_shape":
        return N("constant_shape", (int(spec["height"]), int(spec["width"]), expr(spec["background"])))
    raise ASTError(f"output mode {m} is not exposed")


def object_program(d):
    if d.get("library_operators_used"):
        raise ASTError("library operators are not exposed")
    default = d["default_action"]["delta_type"]
    if default not in ("keep", "delete") or d["default_action"].get("params"):
        raise ASTError(f"default action {default} is not exposed")
    rules = tuple(N("rule", (expr(r["selector"]["predicate"]), action(r["action"]["delta_type"], r["action"]["params"])))
                  for r in d["rules"])
    return N("program", (d["segmentation_variant"], rules, default, _render(d["output_spec"])))


def program(d):
    """A native ObjectProgram or ComposedProgram dict -> the ncv2-g1 AST."""
    if d.get("program_class") == "composed":
        return N("seq", (tuple(object_program(s) for s in d["stages"]),))
    if d.get("program_class") not in (None, "object"):
        raise ASTError(f"program class {d.get('program_class')} is not an object program")
    return object_program(d)
