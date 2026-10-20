"""ncv2-g2: native parity of the program-class forms, type safety, determinism, the object decompiler, and the Phase C
family checks on DEV families. Each family gets four checks:
1. the grammar admits the program;
2. the generator constructs it, or an execution-equivalent program;
3. search reaches the correct answer within the declared budget;
4. the interpreter executes it correctly.

HELDOUT families (cora_neural_v2g2.families) are never used here. Native certificates from dev60 are used ONLY as
parity fixtures (EXPOSED ENGINEERING). They are read from outputs/ and skipped when absent; no answer is read.
"""
import glob
import importlib.util
import json
import os
import sys

import numpy as np
import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from cora_neural_v2 import bridge as G1B                                 # noqa: E402
from cora_neural_v2 import search as G1S                                 # noqa: E402
from cora_neural_v2.constraints import evidence                          # noqa: E402
from cora_neural_v2.rast import ASTError, N, to_sexpr                    # noqa: E402
from cora_neural_v2g2 import families as F                               # noqa: E402
from cora_neural_v2g2 import grammar as G                                # noqa: E402
from cora_neural_v2g2 import search as S2                                # noqa: E402

BUDGET = 3000


def canon(d):
    from geocat_arc.object_reasoning.types import program_from_dict
    import geocat_arc.object_reasoning.expressions  # noqa: F401

    def strip(x):
        if isinstance(x, dict):
            return {k: strip(v) for k, v in x.items() if k != "parameter_class"}
        if isinstance(x, list):
            return [strip(v) for v in x]
        return x
    return strip(program_from_dict(d).to_dict())


def same_out(a, b):
    return (a is None and b is None) or (a is not None and b is not None and a.shape == b.shape and np.array_equal(a, b))


# ------------------------------------------------------------------ 1. parity of the class forms (hand-written native dicts)
GRID = np.array([[0, 0, 0, 0, 0, 0, 0],
                 [0, 1, 0, 0, 0, 0, 0],
                 [0, 1, 1, 0, 0, 2, 0],
                 [0, 0, 0, 0, 0, 0, 0],
                 [0, 0, 0, 3, 0, 0, 0],
                 [0, 0, 0, 0, 0, 0, 0]])
PANELS = np.array([[1, 0, 0, 5, 0, 2, 0],
                   [0, 1, 0, 5, 2, 0, 0],
                   [0, 0, 1, 5, 0, 0, 2]])
RED = lambda split, mode, params: {"program_class": "reduction", "split": split, "mode": mode, "params": params}   # noqa: E731
CLASS_CASES = [
    ("symmetry_lr", "(symmetry_completion horizontal)", RED({"kind": "symmetry"}, "horizontal", {"mode": "symmetry_completion", "symmetry": "horizontal"}), GRID),
    ("counting_majority", "(counting majority_color)", RED({"kind": "counting"}, "majority_color", {"mode": "majority_color"}), GRID),
    ("counting_row", "(counting color_count_row)", RED({"kind": "counting"}, "color_count_row", {"mode": "color_count_row"}), GRID),
    ("pixel_swap", "(pixel_rule color_swap (list (entry (key_color 1) 4) (entry (key_color 0) 9)))",
     RED({"kind": "pixel_rule"}, "color_swap", {"mode": "color_swap", "table": {"1": 4, "0": 9}}), GRID),
    ("pixel_count", "(pixel_rule neighbor_count (list (entry (key_count 0 1) 8) (entry (key_count 1 2) 6)))",
     RED({"kind": "pixel_rule"}, "neighbor_count", {"mode": "neighbor_count", "table": {"(0, 1)": 8, "(1, 2)": 6}}), GRID),
    ("pixel_pattern", "(pixel_rule neighbor_pattern (list (entry (key_pattern 0 (list 1 0 0 0)) 7)))",
     RED({"kind": "pixel_rule"}, "neighbor_pattern", {"mode": "neighbor_pattern", "table": {"(0, (1, 0, 0, 0))": 7}}), GRID),
    ("panel_overlay", "(panel_reduction (split_separator 5) (overlay overlay_first))", RED({"kind": "separator", "color": 5}, "overlay_first", {}), PANELS),
    ("panel_select", "(panel_reduction (split_separator 5) (select_panel most_nonbg))", RED({"kind": "separator", "color": 5}, "select_panel", {"criterion": "most_nonbg"}), PANELS),
    ("panel_cellwise", "(panel_reduction (split_separator 5) (cellwise (list (cell_row (flags #t #f) 3) (cell_row (flags #f #t) (panel 1)) (cell_row (flags #f #f) 0) (cell_row (flags #t #t) 4))))",
     RED({"kind": "separator", "color": 5}, "cellwise", {"table": {"(True, False)": 3, "(False, True)": "@panel1", "(False, False)": 0, "(True, True)": 4}}), PANELS),
    ("panel_cellwise_color", "(panel_reduction (split_separator 5) (cellwise_color (list (cell_row (colors 1 0) 7) (cell_row (colors 0 2) 8) (cell_row (colors 0 0) 0))))",
     RED({"kind": "separator", "color": 5}, "cellwise_color", {"table": {"(1, 0)": 7, "(0, 2)": 8, "(0, 0)": 0}}), PANELS),
    ("gen_ray", "(generative S1 (list (gen (gsel (list (sel_color 3))) (grule ray (list (gp direction up) (gp color 6))))) over_input 0 #f none)",
     {"program_class": "generative", "seg_variant": "S1", "generators": [{"selector": {"color": 3}, "rule": {"kind": "ray", "direction": "up", "color": 6}}],
      "canvas_policy": "over_input", "background": 0}, GRID),
    ("gen_lines_blank", "(generative S1 (list (gen (gsel (list)) (grule row_line (list))) (gen (gsel (list (sel_min_size 2))) (grule col_line (list (gp color 9))))) blank 0 #t 4)",
     {"program_class": "generative", "seg_variant": "S1", "generators": [{"selector": {}, "rule": {"kind": "row_line"}},
                                                                          {"selector": {"min_size": 2}, "rule": {"kind": "col_line", "color": 9}}],
      "canvas_policy": "blank", "background": 0, "delete_source": True, "intersection_color": 4}, GRID),
    ("gen_halo_none_length", "(generative S1 (list (gen (gsel (list (sel_not_background))) (grule ray (list (gp direction left) (gp length none))))) over_input 0 #f none)",
     {"program_class": "generative", "seg_variant": "S1", "generators": [{"selector": {"not_background": True}, "rule": {"kind": "ray", "direction": "left", "length": None}}],
      "canvas_policy": "over_input", "background": 0}, GRID),
]


@pytest.mark.parametrize("name,src,expected,grid", CLASS_CASES)
def test_class_forms_native_parity(name, src, expected, grid):
    ast = G.parse(src)
    assert G.typecheck(ast) == "PROGRAM"
    got = G.compile_program(ast)
    assert canon(got) == canon(expected), name
    a, b = G.execute(ast, grid), G.run(expected, grid)
    assert same_out(a, b), name
    assert G.decompile(got) == ast and G.parse(to_sexpr(ast)) == ast                 # round trips
    assert G.compile_program(ast) == got and same_out(G.execute(ast, grid), a)       # deterministic


def test_some_class_forms_change_the_grid():
    changed = [n for n, s, _, g in CLASS_CASES if not same_out(G.execute(G.parse(s), g), g)]
    assert {"pixel_swap", "pixel_count", "panel_overlay", "gen_ray", "gen_lines_blank", "counting_majority"} <= set(changed)


@pytest.mark.parametrize("bad", [
    "(symmetry_completion diagonal)",                                                  # not a native symmetry
    "(counting median_color)",
    "(pixel_rule neighbor_count (list (entry (key_color 1) 2)))",                     # wrong key type for the mode
    "(pixel_rule color_swap (list (entry (key_color 12) 2)))",                        # colour out of range
    "(pixel_rule color_swap (list))",                                                  # empty table
    "(panel_reduction (split_separator 5) (overlay overlay_mean))",
    "(generative S1 (list (gen (gsel (list)) (grule grow_wild (list)))) over_input 0 #f none)",
    "(generative S1 (list (gen (gsel (list)) (grule ray_relational (list)))) over_input 0 #f none)",   # refused kind
    "(generative S1 (list (gen (gsel (list)) (grule learned_generator (list)))) over_input 0 #f none)",
    "(generative S1 (list (gen (gsel (list)) (grule ray (list (gp color 2))))) over_input 0 #f none)",  # missing direction
    "(generative S1 (list (gen (gsel (list)) (grule halo (list (gp direction up))))) over_input 0 #f none)",  # not a halo param
    "(generative S9 (list (gen (gsel (list)) (grule row_line (list)))) over_input 0 #f none)",
    "(generative S1 (list) over_input 0 #f none)",
])
def test_class_forms_typecheck_rejects(bad):
    with pytest.raises(ASTError):
        G.typecheck(G.parse(bad))


@pytest.mark.parametrize("d", [
    RED({"kind": "separator", "color": 5, "extra": 1}, "overlay_first", {}),
    RED({"kind": "spiral"}, "x", {}),
    {"program_class": "framed", "frame": [1, False], "inner": {}},
    {"program_class": "generative", "seg_variant": "S1", "generators": [{"selector": {"shape": 1}, "rule": {"kind": "ray", "direction": "up"}}],
     "canvas_policy": "over_input", "background": 0},
])
def test_decompile_refuses_what_is_not_exposed(d):
    with pytest.raises(ASTError):
        G.decompile(d)


# ------------------------------------------------------------------ 2. the object decompiler inverts ncv2-g1's compiler
def _g1_cases():
    spec = importlib.util.spec_from_file_location("ast_cases", os.path.join(HERE, "tests", "test_neural_cora_v2_ast.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return [(c[0], c[1]) for c in m.CASES] + [("seq", m.SEQ_SRC)]


@pytest.mark.parametrize("name,src", _g1_cases())
def test_object_decompile_round_trip(name, src):
    d = G1B.compile_program(G.parse(src))
    back = G.decompile(d)
    assert G1B.compile_program(back) == d, name


def test_object_decompile_refuses_unexposed_native_constructs():
    base = {"segmentation_variant": "S1", "default_action": {"delta_type": "keep", "params": {}}, "library_operators_used": [],
            "output_spec": {"mode": "same_as_input", "region": None, "height": None, "width": None, "background": None, "fill": None}}
    sel = {"predicate": {"expr_class": "PredExpr", "op": "true", "args": []}, "literals": 0}
    for act in ({"delta_type": "grow", "params": {}}, {"delta_type": "copy", "params": {"k": {}}},
                {"delta_type": "recolor", "params": {"color": {"expr_class": "ColorExpr", "op": "color_of",
                                                               "args": [{"expr_class": "RefExpr", "op": "matched_template", "args": []}]}}}):
        with pytest.raises(ASTError):
            G.decompile({**base, "rules": [{"selector": sel, "action": act}]})


# ------------------------------------------------------------------ 3. native certificates as parity fixtures (EXPOSED ENGINEERING)
CERTS = sorted(glob.glob(os.path.join(HERE, "outputs", "funnel_v0", "engine_dev60_native", "certificates", "*.json")))


@pytest.mark.skipif(not CERTS, reason="native certificate fixtures are local-only (outputs/ is not in the repository)")
def test_native_certificates_round_trip_with_identical_execution():
    """EXPOSED ENGINEERING fixture: every saved native certificate decompiles into ncv2-g2, compiles back to native's
    own dict, and executes identically on its task's demonstration inputs. No answer is read."""
    from cora_funnel.run import load
    tasks = dict(load("dev60"))
    for f in CERTS:
        d = json.load(open(f))["program"]
        ast = G.parse(to_sexpr(G.decompile(d)))
        G.typecheck(ast)
        d2 = G.compile_program(ast)
        assert canon(d2) == canon(d), f
        key = os.path.basename(f)[:-5]
        for p in tasks[key]["train"]:
            g = np.asarray(p["input"])
            assert same_out(G.run(d, g), G.run(d2, g)), f


# ------------------------------------------------------------------ 4. Phase C: the four checks per DEV family
def rule_candidates(task):
    ev = S2.evidence2(task["train"])
    return {repr(S2.rule_node(s, a)) for s, _, _ in S2.selectors(ev) for a, _, _ in S2.actions(ev, task["train"])}


def g1_rule_candidates(task):
    ev = evidence(task["train"])
    return {repr(N("rule", (s, a))) for s, _, _ in G1S.selectors(ev) for a, _, _ in G1S.actions(ev)}


@pytest.mark.parametrize("name", F.names("dev"))
def test_family_four_checks(name):
    made = F.make_task(name, 1)
    assert made is not None, f"{name}: the family generator produced no task"
    task, answer = made
    src = F.FAMILIES[name][1]
    prog = G.parse(src)
    # 1. the grammar admits it
    assert G.typecheck(prog) == "PROGRAM"
    # 4a. the interpreter executes it correctly (it reproduces every demonstration and the test output)
    assert G.fit(prog, task["train"])[0] and same_out(G.execute(prog, task["test_inputs"][0]), answer)
    # 2. the generator constructs it, or an execution-equivalent program
    if G.is_class(prog):
        cands, _ = S2.class_candidates(task)
        assert any(G.fit(c, task["train"])[0] and same_out(G.execute(c, task["test_inputs"][0]), answer) for c in cands), name
    else:
        rules = rule_candidates(task)
        assert all(repr(r) in rules for r in prog.args[1]), name
    # 3. search reaches the correct answer within the declared budget, and it is one of the two attempts
    r = S2.search(task, BUDGET)
    assert r["first_fit_at"] is not None and r["first_fit_at"] <= BUDGET
    assert any(same_out(np.asarray(p), answer) for p in r["attempts"]), name
    # 4b. the recorded program behind the correct attempt re-executes to the same output
    k = next(i for i, p in enumerate(r["predictions"]) if same_out(np.asarray(p), answer))
    assert same_out(G.execute(G.parse(r["programs"][k]), task["test_inputs"][0]), answer)


@pytest.mark.parametrize("name", ["relational_feature_recolour", "most_common_recolour", "feature_map_recolour", "bind_approach_adopt"])
def test_representable_but_absent_from_the_g1_generator(name):
    """The program is expressible in ncv2-g1 (it compiles with ncv2-g1's own bridge) but ncv2-g1's candidate set does
    not contain it. ncv2-g2's does."""
    task, _ = F.make_task(name, 1)
    prog = G.parse(F.FAMILIES[name][1])
    G1B.compile_program(prog)                                                        # ncv2-g1 can express it
    g1 = g1_rule_candidates(task)
    rule = prog.args[1][0]
    assert repr(rule) not in g1 and repr(rule) in rule_candidates(task), name


def test_class_families_are_absent_from_g1_entirely():
    for name in ("symmetry_completion", "pixel_neighbor_count", "counting_majority", "generative_ray", "panel_overlay"):
        with pytest.raises(ASTError):
            G1B.compile_program(G.parse(F.FAMILIES[name][1]))


def test_no_regression_on_g1_search_cases():
    spec = importlib.util.spec_from_file_location("g1s", os.path.join(HERE, "tests", "test_neural_cora_v2_search.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    import zlib
    for name, src, budget in m.CASES:
        if name == "relational_guard":
            continue
        task, answer = m.make_task(src, seed=zlib.crc32(name.encode()) % 10000 + 70000)
        r = S2.search(task, budget + 300)                    # the same budget plus the class candidates' share
        assert any(same_out(np.asarray(p), answer) for p in r["predictions"]), name


def test_budget_truncation_is_exact_and_records_programs():
    task, _ = F.make_task("negated_selector_delete", 1)
    big, small = S2.search(task, 400), S2.search(task, 150)
    keep = [p for p, at in zip(big["predictions"], big["pred_at"]) if at <= 150]
    assert keep == small["predictions"] and big["n_candidates"] == 400 and small["n_candidates"] == 150
    assert len(big["programs"]) == len(big["predictions"])
