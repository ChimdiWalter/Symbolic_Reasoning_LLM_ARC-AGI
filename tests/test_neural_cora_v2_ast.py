"""ncv2-g1 parity tests: typed AST -> bridge -> the UNCHANGED native interpreter.

For every case the expected native program dict is written here by hand from the native grammar. The tests assert:
1. the bridge emits exactly that dict (ignoring `parameter_class`, certificate metadata that never affects execution);
2. the native interpreter gives identical outputs (shape and every cell) for both;
3. the S-expression and JSON forms round-trip exactly;
4. the compiled dict uses only ops and parameters native defines and reads (`inventory.check_bridge_dict`).

Positive cases must change the grid, so the parity is not vacuous. Negative cases must fail the same way in both.
"""
import json
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cora_neural_v2 import bridge as B                                  # noqa: E402
from cora_neural_v2 import inventory as INV                             # noqa: E402
from cora_neural_v2 import macros as M                                  # noqa: E402
from cora_neural_v2.rast import ASTError, N, from_json, holes, parse_sexpr, to_json, to_sexpr, typecheck  # noqa: E402


# ------------------------------------------------------------------ hand-written native dicts
def E(cls, op, *a):
    return {"expr_class": cls, "op": op, "args": list(a)}


def T(*xs):
    return {"__tuple__": list(xs)}


def A(delta, params=None):
    return {"delta_type": delta, "params": params or {}, "parameter_class": "constant"}


SAME = {"mode": "same_as_input", "region": None, "height": None, "width": None, "background": None, "fill": None}


def P(rules, view="S1", default="keep", spec=None):
    return {"segmentation_variant": view, "rules": rules, "default_action": A(default), "output_spec": spec or SAME,
            "library_operators_used": []}


def R(pred, lit, action):
    return {"selector": {"predicate": pred, "literals": lit}, "action": action}


def TEQ(f, v):
    return E("PredExpr", "test", f, "==", v)


def C(c):
    return E("ColorExpr", "const", c)


def V(dr, dc):
    return E("VecExpr", "const", dr, dc)


# ------------------------------------------------------------------ grids
GA = np.array([[0, 0, 0, 0, 0, 0, 0],      # blue bar (1,1)-(1,2), red dot (1,5), green dot (4,1)
               [0, 1, 1, 0, 0, 2, 0],
               [0, 0, 0, 0, 0, 0, 0],
               [0, 0, 0, 0, 0, 0, 0],
               [0, 3, 0, 0, 0, 0, 0],
               [0, 0, 0, 0, 0, 0, 0],
               [0, 0, 0, 0, 0, 0, 0]])
GB = np.array([[0, 0, 0, 0, 0, 0],         # blue next to red; a lone blue
               [0, 1, 2, 0, 0, 0],
               [0, 0, 0, 0, 0, 0],
               [0, 0, 0, 1, 0, 0],
               [0, 0, 0, 0, 0, 0]])
GL = np.array([[0, 0, 0, 0, 0, 0],         # an L shape, and a dot
               [0, 1, 0, 0, 0, 0],
               [0, 1, 1, 0, 0, 0],
               [0, 0, 0, 0, 0, 0],
               [0, 0, 0, 0, 3, 0],
               [0, 0, 0, 0, 0, 0]])
GD = np.array([[0, 0, 0, 0, 0, 0, 0],      # a yellow frame around a grey dot, and a magenta dot
               [0, 4, 4, 4, 0, 0, 0],
               [0, 4, 5, 4, 0, 0, 0],
               [0, 4, 4, 4, 0, 0, 0],
               [0, 0, 0, 0, 0, 6, 0],
               [0, 0, 0, 0, 0, 0, 0]])
GM = np.array([[0, 0, 0, 0, 0],            # one two-colour object (S3 groups it), and a dot
               [0, 1, 2, 0, 0],
               [0, 0, 0, 0, 0],
               [0, 0, 0, 3, 0],
               [0, 0, 0, 0, 0]])

prog = lambda rules, view="S1", default="keep", render="(same_as_input)": (   # noqa: E731
    f"(program {view} (list {rules}) {default} {render})")

# (name, AST S-expression, expected native dict, grid, must the grid change?)
CASES = [
    ("recolor_const", prog("(rule (test color == 1) (recolor (color 4)))"),
     P([R(TEQ("color", 1), 1, A("recolor", {"color": C(4)}))]), GA, True),
    ("default_delete", prog("(rule (test color == 3) (keep))", default="delete"),
     P([R(TEQ("color", 3), 1, A("keep"))], default="delete"), GA, True),
    ("relation_exists", prog("(rule (exists adjacent (test color == 2)) (recolor (color 7)))"),
     P([R(E("PredExpr", "relation_exists", "adjacent", TEQ("color", 2)), 1, A("recolor", {"color": C(7)}))]), GB, True),
    ("and_in_set", prog("(rule (and (test size == 1) (in_set color (list 2 3))) (delete))"),
     P([R(E("PredExpr", "and2", TEQ("size", 1), E("PredExpr", "in_set", "color", T(2, 3))), 3, A("delete"))]), GA, True),
    ("step_toward_ref", prog("(rule (test color == 3) (translate (step_toward (nearest (test color == 2)))))"),
     P([R(TEQ("color", 3), 1, A("translate", {"vector": E("VecExpr", "step_toward",
                                                            E("RefExpr", "nearest_object", TEQ("color", 2)))}))]), GA, True),
    ("move_until_adjacent_to", prog("(rule (test color == 1) (move_until_adjacent_to (dir right) (nearest_of_color 2)))"),
     P([R(TEQ("color", 1), 1, A("move_until_adjacent", {"direction": E("DirectionExpr", "const", "right"),
                                                           "target": E("RefExpr", "nearest_object_of_color", 2)}))]), GA, True),
    ("copy_offsets", prog("(rule (test color == 2) (copy_offsets (list (vec 2 0) (vec 0 -2))))"),
     P([R(TEQ("color", 2), 1, A("copy", {"offset00": V(2, 0), "offset01": V(0, -2)}))]), GA, True),
    ("copy_rays", prog("(rule (test color == 3) (copy_rays (list (vec 0 2))))"),
     P([R(TEQ("color", 3), 1, A("copy", {"ray00": V(0, 2)}))]), GA, True),
    ("copy_period", prog("(rule (test color == 2) (copy_period (vec 2 0) (list)))"),
     P([R(TEQ("color", 2), 1, A("copy", {"period": V(2, 0)}))]), GA, True),
    ("copy_targets", prog("(rule (test color == 3) (copy_targets (test color == 2) (align_mode bbox_center)))"),
     P([R(TEQ("color", 3), 1, A("copy", {"targets": TEQ("color", 2), "align": E("AlignExpr", "const", "bbox_center")}))]),
     GA, True),
    ("reflect", prog("(rule (test color == 1) (reflect (axis horizontal)))"),
     P([R(TEQ("color", 1), 1, A("reflect", {"axis": E("AxisExpr", "const", "horizontal")}))]), GL, True),
    ("rotate_shift", prog("(rule (test color == 1) (rotate_shift (angle 90) (vec 0 1)))"),
     P([R(TEQ("color", 1), 1, A("rotate", {"angle": E("AngleExpr", "const", 90), "vector": V(0, 1)}))]), GL, True),
    ("scale", prog("(rule (test color == 1) (scale (int 2)))"),
     P([R(TEQ("color", 1), 1, A("scale", {"factor": E("ScalarExpr", "const", 2)}))]), GL, True),
    ("connect", prog("(rule (test color == 1) (connect (nearest (test color == 2)) (color 5)))"),
     P([R(TEQ("color", 1), 1, A("connect", {"target": E("RefExpr", "nearest_object", TEQ("color", 2)), "color": C(5)}))]),
     GA, True),
    ("fill_line", prog("(rule (test color == 3) (fill_line horizontal (color 6) to_border))"),
     P([R(TEQ("color", 3), 1, A("fill_line", {"axis": E("AxisExpr", "const", "horizontal"), "color": C(6),
                                                 "extent": E("AxisExpr", "const", "to_border")}))]), GA, True),
    ("composite", prog("(rule (test color == 3) (composite (list (translate (vec -1 0)) (recolor (color 8)))))"),
     P([R(TEQ("color", 3), 1, A("composite", {"0:translate:vector": V(-1, 0), "1:recolor:color": C(8)}))]), GA, True),
    ("crop_region", prog("", render="(crop (bbox (largest (true))))"),
     P([], spec={**SAME, "mode": "crop", "region": E("RegionExpr", "bbox", E("RefExpr", "largest", E("PredExpr", "true")))}),
     GD, True),
    ("crop_by_action", prog("(rule (test color == 4) (crop_to (bbox_self)))", render="(crop_by_action)"),
     P([R(TEQ("color", 4), 1, A("crop_to", {"region": E("RegionExpr", "bbox_self")}))], spec={**SAME, "mode": "crop"}),
     GD, True),
    ("crop_quadrant", prog("", render="(crop (quadrant 0))"),
     P([], spec={**SAME, "mode": "crop", "region": E("RegionExpr", "grid_quadrant", 0)}), GD, True),
    ("color_map", prog("(rule (true) (recolor (color_map (list (1 4) (2 5) (3 6)))))"),
     P([R(E("PredExpr", "true"), 0, A("recolor", {"color": E("ColorExpr", "color_map", T(T(1, 4), T(2, 5), T(3, 6)))}))]),
     GA, True),
    ("feature_map", prog("(rule (true) (recolor (feature_map size (list (1 7) (2 8)))))"),
     P([R(E("PredExpr", "true"), 0, A("recolor", {"color": E("ColorExpr", "feature_map", "size", T(T(1, 7), T(2, 8)))}))]),
     GA, True),
    ("feature_affine", prog("(rule (true) (recolor (feature_affine size 3)))"),
     P([R(E("PredExpr", "true"), 0, A("recolor", {"color": E("ColorExpr", "feature_affine", "size", 3)}))]), GA, True),
    ("color_of_ref", prog("(rule (test color == 3) (recolor (color_of (nearest (test color == 2)))))"),
     P([R(TEQ("color", 3), 1, A("recolor", {"color": E("ColorExpr", "color_of",
                                                         E("RefExpr", "nearest_object", TEQ("color", 2)))}))]), GA, True),
    ("multicolour_view_S3", prog("(rule (test is_multicolor == #t) (recolor (color 9)))", view="S3"),
     P([R(TEQ("is_multicolor", True), 1, A("recolor", {"color": C(9)}))], view="S3"), GM, True),
    ("to_border", prog("(rule (test color == 3) (translate (to_border down)))"),
     P([R(TEQ("color", 3), 1, A("translate", {"vector": E("VecExpr", "vector_to_border", "down")}))]), GA, True),
    ("slide", prog("(rule (test color == 1) (translate (slide right)))"),
     P([R(TEQ("color", 1), 1, A("translate", {"vector": E("VecExpr", "slide_vector", "right")}))]), GA, True),
    ("align_to", prog("(rule (test color == 3) (translate (align_to (nearest (test color == 1)) vertical)))"),
     P([R(TEQ("color", 3), 1, A("translate", {"vector": E("VecExpr", "align_vector",
                                                            E("RefExpr", "nearest_object", TEQ("color", 1)), "vertical")}))]),
     GA, True),
    ("mirror", prog("(rule (test color == 3) (translate (mirror horizontal)))"),
     P([R(TEQ("color", 3), 1, A("translate", {"vector": E("VecExpr", "mirror_vector", "horizontal")}))]), GA, True),
    ("scaled_count", prog("(rule (test color == 1) (translate (scaled down (count (true)))))"),
     P([R(TEQ("color", 1), 1, A("translate", {"vector": E("VecExpr", "scaled_unit", "down",
                                                            E("ScalarExpr", "count", E("PredExpr", "true")))}))]), GA, True),
    ("container_ref", prog("(rule (test color == 5) (recolor (color_of (container))))"),
     P([R(TEQ("color", 5), 1, A("recolor", {"color": E("ColorExpr", "color_of", E("RefExpr", "container"))}))]), GD, True),
    ("binding_inlined",
     prog("(rule_with (list (?t (nearest (test color == 2)))) (test color == 3) "
          "(composite (list (translate (step_toward (var ?t))) (recolor (color_of (var ?t))))))"),
     P([R(TEQ("color", 3), 1, A("composite", {
         "0:translate:vector": E("VecExpr", "step_toward", E("RefExpr", "nearest_object", TEQ("color", 2))),
         "1:recolor:color": E("ColorExpr", "color_of", E("RefExpr", "nearest_object", TEQ("color", 2)))}))]), GA, True),
]
SEQ_SRC = ("(seq (list " + prog("(rule (test color == 1) (recolor (color 2)))") + " "
           + prog("(rule (test color == 2) (delete))") + "))")
SEQ_EXPECTED = {"program_class": "composed", "stage_provenance": [], "stages": [
    P([R(TEQ("color", 1), 1, A("recolor", {"color": C(2)}))]), P([R(TEQ("color", 2), 1, A("delete"))])]}


def _strip(d):
    """Drop parameter_class (metadata only) everywhere, for dict comparison."""
    if isinstance(d, dict):
        return {k: _strip(v) for k, v in d.items() if k != "parameter_class"}
    if isinstance(d, list):
        return [_strip(x) for x in d]
    return d


def _canon(d):
    """Round-trip a native dict through the native parser, so both sides are compared in native's own form."""
    from geocat_arc.object_reasoning.types import program_from_dict
    import geocat_arc.object_reasoning.expressions  # noqa: F401
    return _strip(program_from_dict(d).to_dict())


@pytest.mark.parametrize("name,src,expected,grid,changes", CASES + [("seq_two_stages", SEQ_SRC, SEQ_EXPECTED, GA, True)])
def test_native_parity(name, src, expected, grid, changes):
    ast = parse_sexpr(src)
    assert typecheck(ast) == "PROGRAM"
    got = B.compile_program(ast)
    assert _canon(got) == _canon(expected), name
    INV.check_bridge_dict(got)
    out_ast, out_native = B.execute(ast, grid), B.run_native_dict(expected, grid)
    assert (out_ast is None) == (out_native is None), name
    if out_native is not None:
        assert out_ast.shape == out_native.shape and np.array_equal(out_ast, out_native), name
    if changes:
        assert out_native is not None, f"{name}: native raised on a positive case"
        assert out_native.shape != grid.shape or not np.array_equal(out_native, grid), f"{name}: no change"
    # round trips: S-expression and JSON
    assert parse_sexpr(to_sexpr(ast)) == ast
    assert from_json(json.loads(json.dumps(to_json(ast)))) == ast


def test_shape_changing_renders_change_shape():
    for name in ("crop_region", "crop_by_action", "crop_quadrant"):
        src, grid = next((c[1], c[3]) for c in CASES if c[0] == name)
        assert B.execute(parse_sexpr(src), grid).shape != grid.shape, name


def test_native_eval_error_is_the_same_failure():
    # copy onto targets that do not exist: native raises EvalError -> both sides return None
    src = prog("(rule (test color == 3) (copy_targets (test color == 9) (align_mode bbox_center)))")
    exp = P([R(TEQ("color", 3), 1, A("copy", {"targets": TEQ("color", 9), "align": E("AlignExpr", "const", "bbox_center")}))])
    assert B.execute(parse_sexpr(src), GA) is None and B.run_native_dict(exp, GA) is None


@pytest.mark.parametrize("bad", [
    prog("(rule (test color == 1) (recolor (vec 1 2)))"),                 # wrong type
    prog("(rule (test colour == 1) (delete))"),                            # not a native feature
    prog("(rule (exists touching (true)) (delete))"),                      # not a native relation
    prog("(rule (test color =~ 1) (delete))"),                             # bad comparison
    prog("(rule (true) (translate (vector_to (var ?u))))"),                # unbound variable
    prog("(rule (true) (recolor (color 1) (color 2)))"),                   # arity
    "(program S9 (list) keep (same_as_input))",                            # not a view
])
def test_typecheck_rejects(bad):
    with pytest.raises(ASTError):
        typecheck(parse_sexpr(bad))


def test_holes_typecheck_but_never_compile():
    sketch = parse_sexpr(prog("(rule (hole PRED) (recolor (hole COLOR)))"))
    assert typecheck(sketch) == "PROGRAM" and holes(sketch) == ["PRED", "COLOR"]
    with pytest.raises(ASTError):
        B.compile_program(sketch)


def test_composite_rejects_parameterless_parts():
    with pytest.raises(ASTError):
        B.compile_program(parse_sexpr(prog("(rule (true) (composite (list (delete) (recolor (color 1)))))")))


def test_macro_expansion_is_typed_hygienic_and_compiles_to_native():
    # "move toward the nearest object of a colour and take its colour", a reusable researcher macro
    body = parse_sexpr("(rule_with (list (?t (nearest (param target)))) (param sel) "
                       "(composite (list (translate (step_toward (var ?t))) (recolor (color_of (var ?t))))))")
    mac = M.Macro("approach_and_adopt", (("sel", "PRED"), ("target", "PRED")), "RULE", body, provenance="researcher")
    call = parse_sexpr("(program S1 (list (call approach_and_adopt (list (test color == 3) (test color == 2)))) keep "
                       "(same_as_input))")
    two = N("program", ("S1", (call.args[1][0], call.args[1][0]), "keep", N("same_as_input", ())))
    expanded = M.expand(two, {"approach_and_adopt": mac})
    names = [r.args[0][0][0] for r in expanded.args[1]]
    assert len(set(names)) == 2 and all(n.startswith("?t__approach_and_adopt") for n in names)   # hygienic renaming
    assert typecheck(expanded) == "PROGRAM"
    one = M.expand(call, {"approach_and_adopt": mac})
    expected = next(c[2] for c in CASES if c[0] == "binding_inlined")
    assert _canon(B.compile_program(one)) == _canon(expected)            # a macro is sugar over existing native ops
    with pytest.raises(ASTError):
        M.Macro("bad", (("x", "COLOR"),), "ACTION", parse_sexpr("(translate (param x))"))   # ill-typed body
    with pytest.raises(ASTError):
        M.expand(parse_sexpr("(call approach_and_adopt (list (color 1) (true)))"), {"approach_and_adopt": mac})


def test_native_code_is_unchanged_since_the_v1_freeze():
    """G2a: the bridge must not have modified native CORA (aggregate sha over geocat_arc/**/*.py)."""
    import glob
    import hashlib
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    man = json.load(open(os.path.join(here, "records", "NEURAL_CORA_V1_FREEZE_MANIFEST.json")))["groups"]["native_cora_v23_geocat_arc"]
    files = sorted(f for f in glob.glob(os.path.join(here, "geocat_arc/**/*.py"), recursive=True) if "__pycache__" not in f)
    per = {os.path.relpath(f, here): hashlib.sha256(open(f, "rb").read()).hexdigest() for f in files}
    agg = hashlib.sha256("".join(f"{k}:{v}\n" for k, v in per.items()).encode()).hexdigest()
    assert agg == man["aggregate_sha256"]


def test_inventory_reads_native_registries():
    inv = INV.native_inventory()
    assert "copy" in inv["delta_types"] and "relation_exists" in inv["expression_grammars"]["PredExpr"]
    assert {"adjacent", "inside", "contains"} <= set(inv["relations"]) and "size_rank" in inv["features"]
    with pytest.raises(ValueError):
        INV.check_bridge_dict(P([R(TEQ("color", 1), 1, A("recolor", {"colour": C(2)}))]))    # a misspelt parameter
    with pytest.raises(ValueError):
        INV.check_bridge_dict(P([R(E("PredExpr", "or2", TEQ("color", 1), TEQ("color", 2)), 2, A("delete"))]))
