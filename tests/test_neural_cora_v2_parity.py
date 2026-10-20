"""ncv2-g1 native parity, part 2: every remaining exposed construct, the execution semantics the v2 addendum names,
and parity on real (already exposed) ARC grids.

Part 1 (`tests/test_neural_cora_v2_ast.py`, frozen with the G2 protocol) covers 32 programs. This file adds:
1. **PARITY** for every other exposed op. Each has a hand-written native dict, identical native outputs, and a real
   change. Covered: constant translate, move_to, move_until_adjacent, reflect/rotate variants, paint (including a
   multicolour result), copy_part, extract_part, constant_shape, vector_to, gap_closing, reflect_across,
   unique/largest/contained/shape-twin references, most/least common colour, the scalars, separator regions, every
   relation and the boolean features.
2. **SEMANTICS**, with expected grids written by hand from native's source (`render_program`,
   geocat_arc/object_reasoning/actions.py):
   - first-match precedence;
   - guards (WHERE) vs actions (WHAT);
   - default actions;
   - occlusion order;
   - ordered composite parts;
   - stage re-segmentation;
   - output dimensions;
   - constructs that are deliberately NOT exposed (grow, synthesized copies, matched templates, loops), which must
     be rejected.
3. **REAL GRIDS:** every program from parts 1 and 2 on the demonstration inputs of 6 exposed dev60 tasks
   (solver-visible; no answers are read), with AST-compiled and hand-written native giving identical results. The
   full 60-task version is `scripts/neural_cora_v2_parity_bench.py`.
"""
import importlib.util
import os
import sys

import numpy as np
import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from cora_neural_v2 import bridge as B                                  # noqa: E402
from cora_neural_v2 import inventory as INV                             # noqa: E402
from cora_neural_v2.rast import ASTError, parse_sexpr, typecheck        # noqa: E402

_spec = importlib.util.spec_from_file_location("ast_cases", os.path.join(HERE, "tests", "test_neural_cora_v2_ast.py"))
AC = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(AC)
E, T, A, P, R, TEQ, C, V, SAME, prog, _canon = AC.E, AC.T, AC.A, AC.P, AC.R, AC.TEQ, AC.C, AC.V, AC.SAME, AC.prog, AC._canon
GA, GL, GD = AC.GA, AC.GL, AC.GD

GT = np.array([[0, 0, 0, 0, 0, 0, 0, 0],   # two L shapes of different colours (shape twins), and a dot
               [0, 1, 0, 0, 0, 0, 2, 0],
               [0, 1, 1, 0, 0, 0, 2, 2],
               [0, 0, 0, 0, 0, 0, 0, 0],
               [0, 0, 0, 3, 0, 0, 0, 0],
               [0, 0, 0, 0, 0, 0, 0, 0]])
GS = np.array([[1, 0, 0, 5, 0, 0, 0],      # a grey cross splits the grid into four 3x3 cells
               [0, 0, 0, 5, 0, 2, 0],
               [0, 0, 0, 5, 0, 0, 0],
               [5, 5, 5, 5, 5, 5, 5],
               [0, 0, 0, 5, 0, 0, 0],
               [0, 3, 0, 5, 0, 0, 4],
               [0, 0, 0, 5, 0, 0, 0]])
GP = np.array([[0, 0, 0, 0, 0],            # a two-colour domino (one object in S3) and a green domino
               [0, 1, 2, 0, 0],
               [0, 0, 0, 0, 0],
               [0, 3, 3, 0, 0],
               [0, 0, 0, 0, 0]])
GR = np.array([[0, 0, 0, 0, 0, 0, 0, 0],   # an L and a ROTATED copy of it: same shape only after normalization
               [0, 1, 0, 0, 0, 2, 2, 0],
               [0, 1, 1, 0, 0, 0, 2, 0],
               [0, 0, 0, 0, 0, 0, 0, 0],
               [0, 0, 0, 3, 0, 0, 0, 0],
               [0, 0, 0, 0, 0, 0, 0, 0]])
GB = AC.GB
GC = np.array([[0, 0, 0, 0, 0, 0],         # one object per colour: colour frequency ties break to the smaller colour
               [0, 1, 1, 1, 0, 0],
               [0, 0, 0, 0, 0, 0],
               [0, 2, 2, 0, 3, 0],
               [0, 0, 0, 0, 0, 0]])
GO = np.array([[0, 0, 0, 0, 0, 0],         # blue (first in native's object order), red (second)
               [0, 1, 0, 2, 0, 0],
               [0, 0, 0, 0, 0, 0],
               [0, 0, 0, 0, 0, 0]])
GO2 = np.array([[0, 0, 0, 0, 0, 0],        # the same positions, colours swapped
                [0, 2, 0, 1, 0, 0],
                [0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0]])

REF = lambda op, *a: E("RefExpr", op, *a)                                         # noqa: E731
NEAR = lambda pred: REF("nearest_object", pred)                                   # noqa: E731
REL = lambda rel, pred: E("PredExpr", "relation_exists", rel, pred)               # noqa: E731
RECOL9 = A("recolor", {"color": C(9)})

# (name, AST S-expression, expected native dict, grid)
NEW_CASES = [
    ("translate_const", prog("(rule (test color == 3) (translate (vec -1 2)))"),
     P([R(TEQ("color", 3), 1, A("translate", {"vector": V(-1, 2)}))]), GA),
    ("move_to", prog("(rule (test color == 3) (move_to (vec 0 0)))"),
     P([R(TEQ("color", 3), 1, A("move_to", {"position": V(0, 0)}))]), GA),
    ("move_until_adjacent", prog("(rule (test color == 1) (move_until_adjacent (dir right)))"),
     P([R(TEQ("color", 1), 1, A("move_until_adjacent", {"direction": E("DirectionExpr", "const", "right")}))]), GA),
    ("reflect_shift", prog("(rule (test color == 1) (reflect_shift (axis vertical) (vec 0 2)))"),
     P([R(TEQ("color", 1), 1, A("reflect", {"axis": E("AxisExpr", "const", "vertical"), "vector": V(0, 2)}))]), GL),
    ("rotate", prog("(rule (test color == 1) (rotate (angle 180)))"),
     P([R(TEQ("color", 1), 1, A("rotate", {"angle": E("AngleExpr", "const", 180)}))]), GL),
    ("paint_ref", prog("(rule (test color == 3) (paint (nearest (test color == 1))))"),
     P([R(TEQ("color", 3), 1, A("paint", {"source": NEAR(TEQ("color", 1))}))]), AC.GM),
    ("paint_multicolour", prog("(rule (test color == 3) (paint (nearest (test is_multicolor == #t))))", view="S3"),
     P([R(TEQ("color", 3), 1, A("paint", {"source": NEAR(TEQ("is_multicolor", True))}))], view="S3"), GP),
    ("copy_part", prog("(rule (test color == 4) (copy_part (bbox_self) (vec 0 3)))"),
     P([R(TEQ("color", 4), 1, A("copy_part", {"window": E("RegionExpr", "bbox_self"), "placement": V(0, 3)}))]), GD),
    ("extract_part", prog("(rule (test color == 4) (extract_part (bbox_self) 1 0 (vec 0 3)))"),
     P([R(TEQ("color", 4), 1, A("extract_part", {"source": E("RegionExpr", "bbox_self"),
                                                    "transform_k": E("ScalarExpr", "const", 1),
                                                    "transform_flip": E("ScalarExpr", "const", 0), "placement": V(0, 3)}))]),
     GD),
    ("constant_shape", prog("(rule (true) (keep))", render="(constant_shape 4 5 (color 8))"),
     P([R(E("PredExpr", "true"), 0, A("keep"))], spec={**SAME, "mode": "constant_shape", "height": 4, "width": 5,
                                                        "background": C(8)}), GA),
    ("vector_to", prog("(rule (test color == 3) (translate (vector_to (nearest (test color == 2)))))"),
     P([R(TEQ("color", 3), 1, A("translate", {"vector": E("VecExpr", "vector_to", NEAR(TEQ("color", 2)))}))]), GA),
    ("gap_closing", prog("(rule (test color == 1) (translate (gap_closing (nearest (test color == 2)) horizontal)))"),
     P([R(TEQ("color", 1), 1, A("translate", {"vector": E("VecExpr", "gap_closing_vector", NEAR(TEQ("color", 2)),
                                                            "horizontal")}))]), GA),
    ("reflect_across", prog("(rule (test color == 3) (translate (reflect_across (nearest (test color == 1)) vertical)))"),
     P([R(TEQ("color", 3), 1, A("translate", {"vector": E("VecExpr", "reflect_across", NEAR(TEQ("color", 1)),
                                                            "vertical")}))]), GA),
    ("unique_ref", prog("(rule (test color == 3) (recolor (color_of (unique (test size == 2)))))"),
     P([R(TEQ("color", 3), 1, A("recolor", {"color": E("ColorExpr", "color_of", REF("unique", TEQ("size", 2)))}))]), GA),
    ("largest_ref", prog("(rule (test color == 3) (translate (step_toward (largest (true)))))"),
     P([R(TEQ("color", 3), 1, A("translate", {"vector": E("VecExpr", "step_toward",
                                                            REF("largest", E("PredExpr", "true")))}))]), GA),
    ("contained_ref", prog("(rule (test color == 4) (recolor (color_of (contained))))"),
     P([R(TEQ("color", 4), 1, A("recolor", {"color": E("ColorExpr", "color_of", REF("contained"))}))]), GD),
    ("shape_twin", prog("(rule (test color == 1) (recolor (color_of (shape_twin))))"),
     P([R(TEQ("color", 1), 1, A("recolor", {"color": E("ColorExpr", "color_of", REF("nearest_shape_twin"))}))]), GT),
    ("most_common", prog("(rule (test color == 3) (recolor (most_common_color)))"),
     P([R(TEQ("color", 3), 1, A("recolor", {"color": E("ColorExpr", "most_common_color")}))]), GA),
    ("least_common", prog("(rule (test color == 2) (recolor (least_common_color)))"),
     P([R(TEQ("color", 2), 1, A("recolor", {"color": E("ColorExpr", "least_common_color")}))]), GC),
    ("scalar_size", prog("(rule (test color == 1) (translate (scaled down (size))))"),
     P([R(TEQ("color", 1), 1, A("translate", {"vector": E("VecExpr", "scaled_unit", "down", E("ScalarExpr", "size"))}))]),
     GA),
    ("scalar_feature", prog("(rule (test color == 1) (translate (scaled down (feature size))))"),
     P([R(TEQ("color", 1), 1, A("translate", {"vector": E("VecExpr", "scaled_unit", "down",
                                                            E("ScalarExpr", "feature", "size"))}))]), GA),
    ("scalar_hole_count", prog("(rule (test color == 4) (translate (scaled right (hole_count))))"),
     P([R(TEQ("color", 4), 1, A("translate", {"vector": E("VecExpr", "scaled_unit", "right",
                                                            E("ScalarExpr", "hole_count"))}))]), GD),
    ("separator_cell", prog("", render="(crop (separator_cell 0 1))"),
     P([], spec={**SAME, "mode": "crop", "region": E("RegionExpr", "separator_cell", 0, 1)}), GS),
    ("separator_block_self", prog("(rule (test color == 2) (crop_to (separator_block_self)))", render="(crop_by_action)"),
     P([R(TEQ("color", 2), 1, A("crop_to", {"region": E("RegionExpr", "separator_block_self")}))],
       spec={**SAME, "mode": "crop"}), GS),
    ("rel_inside", prog("(rule (exists inside (test color == 4)) (recolor (color 9)))"),
     P([R(REL("inside", TEQ("color", 4)), 1, RECOL9)]), GD),
    ("rel_contains", prog("(rule (exists contains (test color == 5)) (recolor (color 9)))"),
     P([R(REL("contains", TEQ("color", 5)), 1, RECOL9)]), GD),
    ("rel_left_of", prog("(rule (exists left_of (test color == 2)) (recolor (color 9)))"),
     P([R(REL("left_of", TEQ("color", 2)), 1, RECOL9)]), GA),
    ("rel_right_of", prog("(rule (exists right_of (test color == 1)) (recolor (color 9)))"),
     P([R(REL("right_of", TEQ("color", 1)), 1, RECOL9)]), GA),
    ("rel_above", prog("(rule (exists above (test color == 3)) (recolor (color 9)))"),
     P([R(REL("above", TEQ("color", 3)), 1, RECOL9)]), GA),
    ("rel_below", prog("(rule (exists below (test color == 1)) (recolor (color 9)))"),
     P([R(REL("below", TEQ("color", 1)), 1, RECOL9)]), GA),
    ("rel_same_shape", prog("(rule (exists same_shape (test color == 2)) (recolor (color 9)))"),
     P([R(REL("same_shape", TEQ("color", 2)), 1, RECOL9)]), GT),
    ("rel_same_shape_normalized", prog("(rule (exists same_shape_normalized (test color == 2)) (recolor (color 9)))"),
     P([R(REL("same_shape_normalized", TEQ("color", 2)), 1, RECOL9)]), GR),
    ("crop_bbox_self_ref", prog("", render="(crop (bbox (self)))"),
     P([], spec={**SAME, "mode": "crop", "region": E("RegionExpr", "bbox", REF("self"))}), GD),
    ("rel_same_size", prog("(rule (exists same_size (test color == 3)) (recolor (color 9)))"),
     P([R(REL("same_size", TEQ("color", 3)), 1, RECOL9)]), GA),
    ("rel_same_color", prog("(rule (exists same_color (test size == 1)) (recolor (color 9)))"),
     P([R(REL("same_color", TEQ("size", 1)), 1, RECOL9)]), GB),
    ("feat_size_rank", prog("(rule (test size_rank == 0) (recolor (color 9)))"),
     P([R(TEQ("size_rank", 0), 1, RECOL9)]), GA),
    ("feat_touches_border", prog("(rule (test touches_border == #t) (delete))"),
     P([R(TEQ("touches_border", True), 1, A("delete"))]), GS),
    ("feat_has_hole", prog("(rule (test has_hole == #t) (recolor (color 9)))"),
     P([R(TEQ("has_hole", True), 1, RECOL9)]), GD),
    ("feat_is_line", prog("(rule (test is_line == #t) (recolor (color 9)))"),
     P([R(TEQ("is_line", True), 1, RECOL9)]), GA),
]


def _parity(src, expected, grid):
    ast = parse_sexpr(src)
    assert typecheck(ast) == "PROGRAM"
    got = B.compile_program(ast)
    assert _canon(got) == _canon(expected)
    INV.check_bridge_dict(got)
    out_ast, out_native = B.execute(ast, grid), B.run_native_dict(expected, grid)
    assert (out_ast is None) == (out_native is None)
    if out_native is not None:
        assert out_ast.shape == out_native.shape and np.array_equal(out_ast, out_native)
    return out_native


@pytest.mark.parametrize("name,src,expected,grid", NEW_CASES)
def test_remaining_ops_native_parity(name, src, expected, grid):
    out = _parity(src, expected, grid)
    assert out is not None, f"{name}: native raised"
    assert out.shape != grid.shape or not np.array_equal(out, grid), f"{name}: no change"


def test_every_exposed_action_and_expression_op_has_a_parity_case():
    """Coverage of the inventory: every native delta type and expression op that g1 exposes appears in some parity
    case of part 1 or part 2."""
    import json
    blob = json.dumps([c[2] for c in AC.CASES] + [AC.SEQ_EXPECTED] + [c[2] for c in NEW_CASES])
    inv = INV.native_inventory()
    exposed_deltas = set(inv["delta_types"]) - {"grow", "synth_copy"}
    missing = [d for d in exposed_deltas if f'"delta_type": "{d}"' not in blob]
    exposed_ops = {(g, op) for g, ops in inv["expression_grammars"].items() for op in ops
                   if g not in ("FreeSlotExpr", "GrowModeExpr", "PatternExpr") and op != "matched_template"}
    missing += [f"{g}.{op}" for g, op in exposed_ops if f'"expr_class": "{g}", "op": "{op}"' not in blob]
    assert not missing, missing


# ------------------------------------------------------------------ semantics, with hand-written expected grids
def _run(src, grid):
    return B.execute(parse_sexpr(src), grid)


def test_first_match_precedence():
    """An object that matches both rules gets the FIRST rule's action (render_program breaks at the first match)."""
    ab = _run(prog("(rule (test size == 1) (recolor (color 7))) (rule (test color == 2) (delete))"), GA)
    ba = _run(prog("(rule (test color == 2) (delete)) (rule (test size == 1) (recolor (color 7)))"), GA)
    assert ab[1, 5] == 7 and ba[1, 5] == 0                    # the red dot matches both rules
    assert ab[4, 1] == 7 and ba[4, 1] == 7                    # the green dot matches only "size 1"
    assert np.array_equal(ab[1, 1:3], [1, 1]) and np.array_equal(ba[1, 1:3], [1, 1])   # the blue bar matches neither


def test_guard_is_where_and_action_is_what():
    """The guard compiles into the selector only; the same action under different guards acts on different objects."""
    act = "(recolor (color 6))"
    d1 = B.compile_program(parse_sexpr(prog(f"(rule (test color == 1) {act})")))
    d3 = B.compile_program(parse_sexpr(prog(f"(rule (test color == 3) {act})")))
    assert d1["rules"][0]["action"] == d3["rules"][0]["action"]
    assert d1["rules"][0]["selector"] != d3["rules"][0]["selector"]
    o1, o3 = _run(prog(f"(rule (test color == 1) {act})"), GA), _run(prog(f"(rule (test color == 3) {act})"), GA)
    assert set(zip(*np.nonzero(o1 != GA))) == {(1, 1), (1, 2)} and set(zip(*np.nonzero(o3 != GA))) == {(4, 1)}


def test_default_action_applies_to_unmatched_objects():
    out = _run(prog("(rule (test color == 2) (keep))", default="delete"), GA)
    exp = np.zeros_like(GA)
    exp[1, 5] = 2
    assert np.array_equal(out, exp)


@pytest.mark.parametrize("src,grid,expected_row1", [
    (prog("(rule (test color == 1) (translate (vec 0 2)))"), GO, [0, 0, 0, 2, 0, 0]),      # the moved one is hidden
    (prog("(rule (test color == 2) (translate (vec 0 -2)))"), GO, [0, 2, 0, 0, 0, 0]),     # the moved one shows
    (prog("(rule (test color == 2) (translate (vec 0 2)))"), GO2, [0, 0, 0, 1, 0, 0]),     # colour does not matter
    (prog("(rule (test color == 1) (translate (vec 0 -2)))"), GO2, [0, 1, 0, 0, 0, 0]),
    (prog("(rule (test color == 1) (copy_offsets (list (vec 0 2))))"), GO, [0, 1, 0, 2, 0, 0]),   # a copy draws with
    (prog("(rule (test color == 2) (copy_offsets (list (vec 0 -2))))"), GO, [0, 2, 0, 2, 0, 0]),  # its source object
    (prog("(rule (test color == 1) (translate (vec 0 1))) (rule (test color == 2) (translate (vec 0 -1)))"), GO,
     [0, 0, 2, 0, 0, 0]),
])
def test_occlusion_follows_native_object_order(src, grid, expected_row1):
    """Characterization of native semantics: objects are drawn in segmentation order, and a later object (here the one
    starting at column 3) occludes an earlier one, whichever of them moved."""
    out = _run(src, grid)
    assert out[1].tolist() == expected_row1 and not out[[0, 2, 3]].any()


def test_composite_parts_apply_in_order_on_the_transformed_object():
    first = "(composite (list (translate (to_border right)) (translate (vec 0 -1))))"
    second = "(composite (list (translate (vec 0 -1)) (translate (to_border right))))"
    exp1 = P([R(TEQ("color", 3), 1, A("composite", {"0:translate:vector": E("VecExpr", "vector_to_border", "right"),
                                                     "1:translate:vector": V(0, -1)}))])
    exp2 = P([R(TEQ("color", 3), 1, A("composite", {"0:translate:vector": V(0, -1),
                                                     "1:translate:vector": E("VecExpr", "vector_to_border", "right")}))])
    o1 = _parity(prog(f"(rule (test color == 3) {first})"), exp1, GA)
    o2 = _parity(prog(f"(rule (test color == 3) {second})"), exp2, GA)
    assert o1[4, 5] == 3 and o2[4, 6] == 3                     # order matters
    # a later part's expressions see the earlier part's result: move next to red, then adopt the nearest colour
    a = _run(prog("(rule (test color == 3) (composite (list (translate (vec 0 4)) (recolor (color_of (nearest (true)))))))"), GA)
    b = _run(prog("(rule (test color == 3) (composite (list (recolor (color_of (nearest (true)))) (translate (vec 0 4)))))"), GA)
    assert a[4, 5] == 2 and b[4, 5] == 1


def test_multicolour_output_via_paint():
    out = _run(prog("(rule (test color == 3) (paint (nearest (test is_multicolor == #t))))", view="S3"), GP)
    assert out[3, 1:3].tolist() == [1, 2]                      # one object now carries two colours


def test_stages_resegment_the_previous_output():
    """`seq` stage 2 re-segments stage 1's output; the same two rules in one stage behave differently."""
    staged = _run("(seq (list " + prog("(rule (test color == 1) (recolor (color 2)))") + " "
                  + prog("(rule (test color == 2) (delete))") + "))", GA)
    flat = _run(prog("(rule (test color == 1) (recolor (color 2))) (rule (test color == 2) (delete))"), GA)
    assert not staged[1].any() and flat[1, 1:3].tolist() == [2, 2] and flat[1, 5] == 0


def test_output_dimensions():
    assert _run(prog("", render="(crop (bbox (largest (true))))"), GD).shape == (3, 3)
    out = _run(prog("(rule (true) (keep))", render="(constant_shape 4 5 (color 8))"), GA)
    assert out.shape == (4, 5) and (out == 8).sum() == 18      # background 8; the blue bar is painted at its place
    assert _run(prog("", render="(crop (separator_cell 0 1))"), GS).shape == (3, 3)


def test_colour_frequency_counts_objects_and_ties_break_to_the_smaller_colour():
    """most/least_common_color count OBJECTS per colour (expressions.py), not cells: in GC each colour has one object,
    so both return colour 1 although colour 3 has the fewest cells."""
    assert _run(prog("(rule (test color == 2) (recolor (least_common_color)))"), GC)[3, 1] == 1
    assert _run(prog("(rule (test color == 3) (recolor (most_common_color)))"), GC)[3, 4] == 1


@pytest.mark.parametrize("bad", [
    prog("(rule (true) (grow (dir right)))"),                                          # native GROW: not exposed
    prog("(rule (true) (synth_copy (color 1)))"),                                      # learned-verb asset: not exposed
    prog("(rule (true) (recolor (color_of (matched_template))))"),                     # correspondence-bound: not exposed
    prog("(rule (true) (repeat 3 (translate (vec 0 1))))"),                            # no loops in g1
    prog("(rule (true) (copy_k 2 (vec 0 1)))"),                                        # copy k-mode: not exposed
])
def test_not_exposed_constructs_are_rejected(bad):
    with pytest.raises(ASTError):
        typecheck(parse_sexpr(bad))


# ------------------------------------------------------------------ real exposed grids (no answers read)
def dev60_demo_inputs(n_tasks):
    from cora_funnel.run import load
    return [(k, np.asarray(p["input"])) for k, t in load("dev60")[:n_tasks] for p in t["train"]]


def all_parity_programs():
    return [(c[0], c[1], c[2]) for c in AC.CASES] + [("seq_two_stages", AC.SEQ_SRC, AC.SEQ_EXPECTED)] + \
           [(c[0], c[1], c[2]) for c in NEW_CASES]


def real_grid_parity(n_tasks):
    rows = {"executions": 0, "mismatches": [], "both_eval_error": 0, "changed": 0}
    grids = dev60_demo_inputs(n_tasks)
    for name, src, expected in all_parity_programs():
        ast = parse_sexpr(src)
        for key, g in grids:
            a, b = B.execute(ast, g), B.run_native_dict(expected, g)
            rows["executions"] += 1
            if (a is None) != (b is None) or (a is not None and (a.shape != b.shape or not np.array_equal(a, b))):
                rows["mismatches"].append((name, key))
            elif a is None:
                rows["both_eval_error"] += 1
            elif a.shape != g.shape or not np.array_equal(a, g):
                rows["changed"] += 1
    return rows


def test_parity_on_real_exposed_grids():
    r = real_grid_parity(6)
    assert not r["mismatches"], r["mismatches"][:5]
    assert r["changed"] > 0 and r["executions"] > 500
