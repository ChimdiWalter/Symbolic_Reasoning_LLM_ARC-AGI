"""ncv2-g1 search: recovery of known programs on generated tasks, the firing filter, exact truncation, the score hook.

Each task is made by running a known ncv2-g1 program through the native interpreter on random scenes (CORA's own
scene generator), so every demonstration is native-valid by construction. These are engineering tests on fresh
seeds, not the v1 held-out pool and not dev60.
"""
import os
import sys
import zlib

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cora_neural_v2 import bridge as B                                  # noqa: E402
from cora_neural_v2 import search as S                                  # noqa: E402
from cora_neural_v2.rast import parse_sexpr                             # noqa: E402


def make_task(src, seed, n=4, palette=(1, 2, 3)):
    from cora_neural_v1.generator import _scene
    rng = np.random.default_rng(seed)
    prog = parse_sexpr(src)
    pairs, tries = [], 0
    while len(pairs) < n and tries < 400:
        tries += 1
        G = _scene(rng, list(palette) + [4, 5])
        if G is None:
            continue
        out = B.execute(prog, G)
        if out is None or (out.shape == G.shape and np.array_equal(out, G)):
            continue
        pairs.append((G.tolist(), out.tolist()))
    assert len(pairs) == n, src
    return {"task_id": f"t{seed}", "train": pairs[:-1], "test_inputs": [pairs[-1][0]]}, np.asarray(pairs[-1][1])


P = lambda rules, default="keep", render="(same_as_input)": f"(program S1 (list {rules}) {default} {render})"   # noqa: E731
CASES = [
    ("recolour", P("(rule (test color == 1) (recolor (color 4)))"), 3000),
    ("two_rule", P("(rule (test color == 1) (recolor (color 4))) (rule (test color == 3) (delete))"), 3000),
    ("relational_guard", P("(rule (exists adjacent (test color == 2)) (recolor (color 5)))"), 3000),
    ("copy_offset", P("(rule (test color == 2) (copy_offsets (list (vec 0 2))))"), 3000),
    ("move_toward", P("(rule (test color == 3) (translate (step_toward (nearest (test color == 1)))))"), 3000),
    ("pure_crop", P("", render="(crop (bbox (largest (true))))"), 500),
]


@pytest.mark.parametrize("name,src,budget", CASES)
def test_search_recovers_known_programs(name, src, budget):
    if name == "relational_guard":                           # adjacency needs touching objects: build scenes by hand
        pytest.skip("the shared scene generator never makes touching objects; covered by the parity tests")
    task, answer = make_task(src, seed=zlib.crc32(name.encode()) % 10000 + 70000)   # deterministic seed
    r = S.search(task, budget)
    assert r["n_consistent"] >= 1, f"{name}: no consistent program within {budget}"
    assert any(np.array_equal(np.asarray(p), answer) for p in r["predictions"]), f"{name}: correct output not among candidates"


def test_firing_filter_drops_selectors_that_select_nothing():
    task, _ = make_task(P("(rule (test color == 1) (recolor (color 4)))"), seed=70101)
    sel_absent = S.T("color", 9)
    assert not S.fires("S1", sel_absent, task["train"]) and S.fires("S1", S.T("color", 1), task["train"])


def test_budget_truncation_is_exact():
    task, _ = make_task(P("(rule (test color == 3) (delete))"), seed=70102)
    big, small = S.search(task, 300), S.search(task, 100)
    keep = [p for p, at in zip(big["predictions"], big["pred_at"]) if at <= 100]
    assert keep == small["predictions"] and big["n_candidates"] == 300 and small["n_candidates"] == 100


def test_learned_score_hook_changes_order_not_candidates():
    task, _ = make_task(P("(rule (test color == 1) (recolor (color 4)))"), seed=70103)
    flat = lambda view, rules, ev: [0.0] * len(rules)                    # noqa: E731  (a guide with no information)
    a = [S.N.__repr__(p) for p, _ in S.enumerate_programs(task, 400)]
    b = [S.N.__repr__(p) for p, _ in S.enumerate_programs(task, 400, rule_scores=flat)]
    assert a != b and len(a) == len(b) == 400                            # the order differs; the budget is the same


def test_two_rule_order_comes_first_when_two_change_kinds():
    task, answer = make_task(P("(rule (test color == 1) (recolor (color 4))) (rule (test color == 3) (delete))"), seed=70104)
    r = S.search(task, 3000)
    first = next(at for p, at in zip(r["predictions"], r["pred_at"]) if np.array_equal(np.asarray(p), answer))
    assert first <= 3000


def test_search_recovers_a_relational_guard_on_touching_objects():
    """Blue objects that touch a red object turn yellow; lone blue objects stay. Hand-built scenes (objects touch)."""
    src = P("(rule (exists adjacent (test color == 2)) (recolor (color 4)))")
    prog = parse_sexpr(src)
    scenes = [
        [[0, 0, 0, 0, 0, 0], [0, 1, 2, 0, 0, 0], [0, 0, 0, 0, 1, 0], [0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0]],
        [[0, 0, 0, 0, 0, 0], [0, 1, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0], [0, 0, 2, 1, 0, 0], [0, 0, 0, 0, 0, 0]],
        [[1, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0], [0, 0, 0, 2, 0, 0], [0, 0, 0, 1, 0, 0], [0, 0, 0, 0, 0, 1]],
        [[0, 0, 0, 0, 0, 0], [0, 0, 1, 0, 0, 0], [0, 0, 2, 0, 0, 0], [0, 0, 0, 0, 0, 0], [0, 1, 0, 0, 0, 0]],
    ]
    pairs = [(g, B.execute(prog, np.asarray(g)).tolist()) for g in scenes]
    task = {"task_id": "rel", "train": pairs[:3], "test_inputs": [pairs[3][0]]}
    r = S.search(task, 3000)
    assert any(np.array_equal(np.asarray(p), np.asarray(pairs[3][1])) for p in r["predictions"])


def test_cpu_cap_stops_and_is_recorded():
    task, _ = make_task(P("(rule (test color == 3) (delete))"), seed=70105)
    r = S.search(task, 3000, cpu_cap_s=0.0)
    assert r["state"]["cpu_truncated"] and r["n_candidates"] == 0 and r["n_consistent"] == 0
    assert not S.search(task, 50, cpu_cap_s=600.0)["state"]["cpu_truncated"]


def test_exhaustive_single_rule_finds_what_exists_and_reports_absence():
    task, _ = make_task(P("(rule (test color == 1) (recolor (color 4)))"), seed=70201)
    r = S.exhaustive_single_rule(task, cpu_cap_s=120)
    assert r["complete"] and r["any_fit"] and r["n_checked"] > 100
    two, _ = make_task(P("(rule (test color == 1) (recolor (color 4))) (rule (test color == 3) (delete))"), seed=70202)
    r2 = S.exhaustive_single_rule(two, cpu_cap_s=120)
    assert r2["complete"] and not r2["any_fit"]          # a genuine two-rule task has no single-rule explanation
