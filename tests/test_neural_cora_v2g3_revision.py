"""ncv2-g3 Phase 5: the rule-based revision controller on deterministic near-miss programs (DEV-style tasks only).

Each test starts from a program that is wrong in a known way and checks that the controller repairs it by an
executed AST edit. These are mechanics tests: they show that revisions are executable and measured, and they claim
no advantage for the authentic policy over its controls.
"""
import os
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from cora_neural_v2g2 import families as F                               # noqa: E402
from cora_neural_v2g2 import grammar as G                                # noqa: E402
from cora_neural_v2g3 import revision as RV                              # noqa: E402
from test_neural_cora_v2g3 import TWO_RULE, make                         # noqa: E402

DOTS = lambda r: F.scene_dots(r, (2, 3))                                 # noqa: E731


def repaired(task, start, policy=None, budget=400):
    rv = RV.Reviser(task, budget)
    out = rv.run(G.parse(start), policy)
    kept = [e for e in out["log"] if e["kept"]]
    assert [e["wrong_after"] for e in kept] == sorted({e["wrong_after"] for e in kept}, reverse=True)
    assert out["used"] <= budget
    return out, kept


def test_wrong_colour_parameter_is_changed():
    task, _ = make(F.P("(rule (test color == 2) (recolor (color 4)))"), DOTS, 0)
    out, kept = repaired(task, F.P("(rule (test color == 2) (recolor (color 7)))"))
    assert out["fits"] and kept and kept[0]["action"] in ("change_parameter", "change_reference")


def test_wrong_selector_is_changed():
    task, _ = F.make_task("negated_selector_delete", 0)
    out, kept = repaired(task, F.P("(rule (test is_rectangle == #t) (delete))"))
    assert out["fits"] and {e["action"] for e in kept} <= {"change_selector", "add_guard", "remove_rule", "add_rule"}


def test_missing_rule_is_added():
    task, _ = make(TWO_RULE, F.scene_mixed, 0)
    out, kept = repaired(task, F.P("(rule (test has_hole == #t) (delete))"))
    assert out["fits"] and any(e["action"] == "add_rule" for e in kept)


def test_rule_order_is_repaired():
    task, _ = make(F.P("(rule (test color == 2) (delete)) (rule (true) (recolor (color 5)))"), DOTS, 1)
    out, kept = repaired(task, F.P("(rule (true) (recolor (color 5))) (rule (test color == 2) (delete))"))
    assert out["fits"] and out["revisions"] >= 1


def test_rejected_edits_roll_back():
    task, _ = make(F.P("(rule (test color == 2) (recolor (color 4)))"), DOTS, 2)
    out, _ = repaired(task, F.P("(rule (test color == 2) (recolor (color 7)))"))
    assert any(not e["kept"] for e in out["log"]) or out["revisions"] == 1
    assert out["revisions"] == sum(e["kept"] for e in out["log"])


@pytest.mark.parametrize("policy", [RV.FixedOrderPolicy(), RV.TryAllPolicy(),
                                    RV.ShuffledTracePolicy([{"shape_ok": True, "n_wrong": 3, "broken": 3}])])
def test_controls_use_the_same_machinery(policy):
    task, _ = make(F.P("(rule (test color == 2) (recolor (color 4)))"), DOTS, 3)
    a, _ = repaired(task, F.P("(rule (test color == 2) (recolor (color 7)))"), policy, budget=150)
    b, _ = repaired(task, F.P("(rule (test color == 2) (recolor (color 7)))"), policy, budget=150)
    assert a["program"] == b["program"] and a["used"] == b["used"]


def test_budget_is_respected():
    task, _ = make(TWO_RULE, F.scene_mixed, 1)
    out, _ = repaired(task, F.P("(rule (test color == 9) (delete))"), budget=5)
    assert out["used"] <= 5
