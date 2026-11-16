"""Fast tests on invented data. Author: Chimdi Walter Ndubuisi"""
import json
import os
import re

import core
import dslx
import gen
import presets as P
import search as S

L = dslx.load()


def test_generator_is_deterministic_and_typed():
    a, b = gen.gen_examples("hmirror"), gen.gen_examples("hmirror")
    assert a["status"] == "ok" and len(a["examples"]) == P.N_FIT + P.N_VAL
    assert repr(a["examples"]) == repr(b["examples"])
    assert repr(gen.gen_examples("vmirror")["examples"]) != repr(a["examples"])
    assert gen.seed_for("hmirror") != gen.seed_for("vmirror")
    for args, out in a["examples"]:                      # a Piece: grid, object or indices
        assert dslx.tag(args[0]) in dslx.ACC["Piece"]
        assert out == L["ns"]["hmirror"](*args)


def test_exclusions_are_recorded_not_dropped():
    g = gen.gen_examples("compose")
    assert g["status"] == "excluded" and "function" in g["reason"]
    rec = core.run_condition("compose", "a", g)
    assert rec["status"] == "excluded" and rec["reason"]


def test_known_regeneration_with_family_available():
    g = gen.gen_examples("rot180")
    rec = core.run_condition("rot180", "a", g, budgets=_B(20), max_size=3)
    assert rec["regenerated"] and rec["size"] == 3
    assert "rot180" not in rec["expr"]
    assert rec["readings"]["6"] == "right"


def _B(x):
    return {k: x for k in ("1", "2", "3", "6", "oracle")}


def test_family_hiding_follows_the_protocol():
    g = gen.gen_examples("rot180")
    fam = set(L["fam_of"]["rot180"])
    assert len(fam) > 1 and "rot90" in fam
    rb = core.run_condition("rot180", "b", g, budgets=_B(3), max_size=3)
    assert set(rb["hidden"]) == fam
    ns = dslx.library_namespace(fam)
    assert not (set(ns) & fam)
    ops, leaves, _ = core.build("rot180", fam, g["examples"], ns)
    assert not ({o[0] for o in ops} & fam) and not ({t[1] for t, _ in leaves if t[0] == "FN"} & fam)
    assert not rb["regenerated"]                          # the two-turn rebuild needs a hidden member
    ra = core.run_condition("rot180", "a", g, budgets=_B(3), max_size=3)
    assert ra["hidden"] == ["rot180"]


def test_hidden_operation_is_really_absent():
    grid = ((1, 2, 3, 4), (5, 6, 7, 8))
    full = dslx.library_namespace(())
    assert full["lefthalf"](grid) == L["ns"]["lefthalf"](grid)
    ns = dslx.library_namespace({"rot90"})
    assert "rot90" not in ns
    try:
        ns["lefthalf"](grid)                       # lefthalf calls rot90 inside its own text
        raise AssertionError("lefthalf ran although rot90 is hidden")
    except NameError:
        pass
    ns2 = dslx.library_namespace({"hmirror"})      # an unrelated name
    assert ns2["lefthalf"](grid) == L["ns"]["lefthalf"](grid)


def test_library_text_agrees_with_original_on_invented_inputs():
    ns = dslx.library_namespace(())
    for op in ("hmirror", "objects", "lefthalf", "center", "frontiers", "add", "mapply"):
        for args, out in gen.gen_examples(op)["examples"][:10]:
            assert ns[op](*args) == out


def test_validation_is_not_used_by_the_search():
    """A K arm sees only the first K examples: changing the later examples cannot change its choice."""
    g = gen.gen_examples("width")
    ex = list(g["examples"])
    ns = dslx.library_namespace({"width"})
    ops, leaves, Y = core.build("width", {"width"}, ex, ns)
    r1 = core._arm(ops, leaves, Y, 2, 10, 3)
    ex2 = ex[:2] + [(a, 0) for a, _ in ex[2:]]
    ops2, leaves2, Y2 = core.build("width", {"width"}, ex2, ns)
    r2 = core._arm(ops2, leaves2, Y2, 2, 10, 3)
    assert r1["found"][0] == r2["found"][0] and r1["bank"] == r2["bank"]


def test_fits_but_wrong_is_detected():
    ns = L["ns"]
    ops = [("add", ns["add"], tuple(dslx.ACC[a] for _, a in L["sigs"]["add"]), False)]
    x = (0, 0, 0, 1, 2, 3)
    leaves = [(("P", "x"), x), (("C", "ONE"), (1,) * 6), (("C", "ZERO"), (0,) * 6)]
    Y = tuple(v + 1 for v in x)
    short = S.search(ops, [(t, v[:3]) for t, v in leaves], Y[:3], 10, 3)
    assert short["found"][0] == "ONE"                     # fits the first three, wrong overall
    full = S.search(ops, leaves, Y, 10, 3)
    assert full["found"][:2] == ("add(x, ONE)", 3) and full["stop"] == "found"
    tree = short["found"][2]
    ev = [S.eval_tree(tree, ns, {"ONE": 1, "ZERO": 0}, {"x": v}) == y for v, y in zip(x[3:], Y[3:])]
    assert not all(ev)


def test_fits_but_wrong_arm_in_a_condition():
    """Constructed examples: the first example's output is constant 1, so the first fit at K=1 is wrong."""
    g = dict(status="ok", draws=0, raised=0, reason=None,
             examples=[((v,), v + 1) for v in (0, 0, 0, 0, 0, 0)] + [((v,), v + 1) for v in range(1, 31)])
    rec = core.run_condition("increment", "a", g, budgets=_B(10), max_size=3)
    assert rec["readings"]["1"] == "wrong" and rec["arms"]["1"]["validation_equal"] < 30
    assert rec["readings"]["6"] == "wrong"                # six identical examples do not tell the rule apart


def test_resumable(tmp_path):
    out = str(tmp_path)
    cpu1 = core.run_op(out, "rot180", budgets=_B(1), max_size=2)
    pa = core.path(out, "rot180", "a")
    m = os.path.getmtime(pa)
    assert core.run_op(out, "rot180", budgets=_B(1), max_size=2) == 0.0 and os.path.getmtime(pa) == m
    os.remove(core.path(out, "rot180", "b"))
    core.run_op(out, "rot180", budgets=_B(1), max_size=2)
    assert os.path.exists(core.path(out, "rot180", "b")) and cpu1 >= 0


def test_summary_counts_add_up(tmp_path):
    out = str(tmp_path)
    ops = ["rot180", "width", "compose", "identity"]
    for o in ops:
        core.run_op(out, o, budgets=_B(2), max_size=3)
    s = core.summarize(out, set(ops))
    for c in "ab":
        cd = s["conditions"][c]
        oc = cd["oracle_assisted_coverage"]
        assert oc["expressible_within_limit_and_budget"] + oc["not_found_within_limit_and_budget"] \
            + oc["excluded"] == len(ops)
        assert sum(oc["by_size"].values()) == oc["expressible_within_limit_and_budget"]
        for k, cnt in cd["rule_choice_by_n_fit_examples"].items():
            assert sum(cnt.values()) == len(ops) - oc["excluded"]
    assert s["conditions"]["a"]["oracle_assisted_coverage"]["excluded"] == 1
    assert "identity" in s["conditions"]["a"]["oracle_assisted_coverage"]["ops"]          # a parameter itself
    core_set = s["core_estimate_condition_a"]["members"]
    assert "compose" in core_set and s["core_estimate_condition_a"]["size"] <= len(ops)
    assert s["pilot_ops_in_this_summary"] == sorted(o for o in ops if o in P.PILOT_OPS)


def test_greedy_core_breaks_cycles():
    reg = {"a": {"b"}, "b": {"a"}, "c": {"a", "z"}}
    c = core.greedy_core(reg, ["a", "b", "c", "z"])
    assert "z" in c and ("a" in c) != ("b" in c) and "c" not in c
    assert core.check_core(c, reg, ["a", "b", "c", "z"])


def test_greedy_core_external_names_terminate():
    """A witness whose expression uses a name outside the scope (a -> z, scope only a) must not loop."""
    c = core.greedy_core({"a": {"z"}}, ["a"])
    assert c == []                                        # z is an external basis node, so a is derivable
    c2 = core.greedy_core({"a": {"a2"}, "a2": {"a"}}, ["a", "a2"])
    assert len(c2) == 1
    assert core.greedy_core({"a": {"a"}}, ["a"]) == []


def test_protocol_names_every_function_in_the_fixed_sets():
    p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "PROTOCOL.md")
    if not os.path.exists(p):
        return
    txt = open(p).read()
    for nme in gen.UNARY + gen.BINARY + list(P.PILOT_OPS):
        assert nme in txt, nme


def test_k1_candidate_that_raises_only_on_a_later_example_stays_eligible():
    """first(x) fits example 1 (x is a pair) and raises on example 2 (x is an int). The K=1 search must choose it
    (nothing beyond its one example may prune it); the K=2 search sees the error and cannot."""
    ns = dslx.full_ns()
    ops = [("first", ns["first"], tuple(dslx.ACC[a] for _, a in L["sigs"]["first"]), False)]
    leaves = [(("P", "x"), ((7, 8), 5))]
    Y = (7, 5)
    k1 = S.search(ops, [(t, v[:1]) for t, v in leaves], Y[:1], 5, 3)
    assert k1["found"][0] == "first(x)"
    k2 = S.search(ops, leaves, Y, 5, 3)
    assert k2["found"] is None
    try:
        S.eval_tree(k1["found"][2], ns, {}, {"x": 5})       # on a later example the chosen expression raises
        raise AssertionError("expected an error")
    except TypeError:
        pass                                                # counted as a validation failure by core._validate


def test_validation_error_counts_as_failure_and_never_changes_the_choice():
    ns = dslx.full_ns()
    tree = ("L", "first", ("P", "container"))
    eq, err = core._validate(tree, "first", ns, [(((1, 2),), 1), ((5,), 5)])
    assert (eq, err) == (1, 1)


def test_rejected_draws_and_function_pools():
    g = gen.gen_examples("sfilter")
    assert g["status"] == "ok" and set(g["rejected"]) >= {"target_raised", "duplicate"}
    gone = set(g["function_pool_excluded"])
    assert "sfilter" in gone and "mfilter" in gone                      # mfilter calls sfilter
    for args, _ in g["examples"]:
        for a in args:
            if callable(a):
                assert a.__name__ not in gone
    h = gen.gen_examples("hmirror")
    assert {"hmirror", "vmirror", "dmirror", "cmirror"} <= set(h["function_pool_excluded"])


def test_canonical_encoding_is_typed_and_address_free():
    assert dslx.canon(True) != dslx.canon(1) and dslx.canon((1, 2)) != dslx.canon(frozenset({1, 2}))
    assert dslx.canon(frozenset({3, 1, 2})) == dslx.canon(frozenset({2, 3, 1}))
    assert dslx.canon(()) != dslx.canon(frozenset())
    assert "0x" not in dslx.canon(dslx.full_ns()["size"]) and dslx.canon(dslx.full_ns()["size"]) == "f:size"


def test_held_out_roster_is_forty_names_in_twelve_families():
    h = dslx.held_out_names()
    assert len(h) == 40 and len(set(h.values())) == 12


def test_reduced_subset_expression_may_use_names_outside_the_subset(tmp_path):
    """lefthalf is rebuilt as apply(tophalf, grid): names outside the one-operation subset."""
    out = str(tmp_path)
    core.run_op(out, "lefthalf", budgets=_B(5), max_size=3)
    s = core.summarize(out, {"lefthalf"})
    ca = s["core_estimate_condition_a"]
    assert ca["external_basis_names"] and ca["graph_check_passed"] and ca["size"] == 0
    assert s["conditions"]["a"]["oracle_assisted_coverage"]["expressible_within_limit_and_budget"] == 1


def test_greedy_core_order_and_progress():
    reg = {"a": {"b"}, "b": {"c"}, "c": set()}
    order = core.check_core(core.greedy_core(reg, ["a", "b", "c"]), reg, ["a", "b", "c"], {"a": "A", "b": "B", "c": "C"})
    assert [o for o, _ in order] == ["a", "b", "c"] or {o for o, _ in order} == {"a", "b", "c"}


def test_known_short_definitions_listed_and_found():
    k = core.known_definitions()
    assert set(k) == {"mfilter", "other", "mapply", "lefthalf", "righthalf"}
    g = gen.gen_examples("mapply")
    rec = core.run_condition("mapply", "a", g, budgets=_B(30), max_size=4)
    kd = rec["known_definition"]
    assert kd["equals_all_36"] and kd["found"] and kd["miss_reason"] is None     # merge(apply(function, container))
    assert rec["regenerated"] and rec["arms"]["6"]["equal_all_36"] in (True, False)
    for k_ in "1236":
        if rec["arms"][k_].get("expr"):
            a = rec["arms"][k_]
            assert a["later_fit_n"] == 6 - int(k_) and "later_fit_errors" in a and "equal_all_36" in a


def test_container_container_rule_accepts_cells_and_objects():
    cc = dslx.ACC["ContainerContainer"]
    assert {"O", "X"} <= cc and not ({"T", "Z"} & cc)


def test_function_cap_is_reported():
    ns = dslx.full_ns()
    comp = ("compose", ns["compose"], tuple(dslx.ACC[a] for _, a in L["sigs"]["compose"]), True)
    leaves = [(("P", "x"), (3, 4)), (("FN", "size"), (ns["size"],) * 2), (("FN", "first"), (ns["first"],) * 2)]
    r = S.search([comp], leaves, (9, 9), 5, 5, max_fn=0)
    assert r["found"] is None and r["function_cap_reached"] and r["stop"] == "size_exhausted_function_cap"
    r2 = S.search([comp], leaves, (9, 9), 5, 5)
    assert r2["stop"] == "size_exhausted" and not r2["function_cap_reached"]


def test_acceptance_needs_exact_typed_equality():
    leaves = [(("P", "x"), (((True, False),),))]
    r = S.search([], leaves, (((1, 0),),), 5, 2)
    assert r["found"] is None                                # True == 1 in Python, but not accepted
    r = S.search([], leaves, (((True, False),),), 5, 2)
    assert r["found"][0] == "x"
    assert core._validate(("P", "container"), "first", {}, [((((True, False),),), ((1, 0),))]) == (0, 0)
