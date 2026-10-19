"""Neural-CORA v1: typed IR semantics through the native interpreter, purity, enumeration and generator checks."""
import copy
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cora_neural_v1 import generator as G                              # noqa: E402
from cora_neural_v1 import interp as I                                 # noqa: E402
from cora_neural_v1 import space as SP                                 # noqa: E402
from cora_neural_v1.ir import ACTIONS, SELECTORS, Hypothesis, Rule     # noqa: E402


def _grid():
    g = np.zeros((7, 7), int)
    g[1, 1] = g[1, 2] = 3          # a 2-cell colour-3 bar
    g[4, 4] = 5                    # a single colour-5 cell
    g[5, 1] = 3                    # a single colour-3 cell
    return g


def test_non_additive_operators_full_grid():
    g = _grid()
    rec = I.run(Hypothesis("S1", (Rule(("color", 3), ("recolor", 6)),)), g)
    exp = g.copy()
    exp[exp == 3] = 6
    assert np.array_equal(rec, exp)
    dele = I.run(Hypothesis("S1", (Rule(("size", 1), ("delete",)),)), g)
    exp = g.copy()
    exp[4, 4] = exp[5, 1] = 0
    assert np.array_equal(dele, exp)
    mv = I.run(Hypothesis("S1", (Rule(("color", 5), ("translate", -1, 1)),)), g)
    exp = g.copy()
    exp[4, 4] = 0
    exp[3, 5] = 5
    assert np.array_equal(mv, exp)


def test_additive_operator_full_grid():
    g = _grid()
    out = I.run(Hypothesis("S1", (Rule(("color", 5), ("fill_line", "horizontal", 2)),)), g)
    exp = g.copy()
    exp[4, :] = 2
    exp[4, 4] = 5                  # the object itself is kept; the line is drawn behind it
    assert np.array_equal(out, exp)


def test_first_match_two_rules_and_default_delete():
    g = _grid()
    out = I.run(Hypothesis("S1", (Rule(("size", 1), ("delete",)), Rule(("true", None), ("recolor", 9)))), g)
    exp = np.zeros_like(g)
    exp[1, 1] = exp[1, 2] = 9
    assert np.array_equal(out, exp)
    keep = I.run(Hypothesis("S1", (Rule(("color", 5), ("keep",)),), "delete"), g)
    exp = np.zeros_like(g)
    exp[4, 4] = 5
    assert np.array_equal(keep, exp)


def test_serialization_and_determinism():
    h = Hypothesis("S2", (Rule(("color", 4), ("fill_line", "both", 7)), Rule(("size_rank", 0), ("delete",))), "keep")
    back = Hypothesis.from_dict(h.to_dict())
    assert back.key() == h.key() and back.program_sha() == h.program_sha()
    g = _grid()
    assert np.array_equal(I.run(h, g), I.run(back, g))


def test_purity_and_restoration():
    g = _grid()
    g0 = g.copy()
    before = (len(I._PROGRAMS), dict(I.STATS))
    for a in ACTIONS[:20]:
        I.run(Hypothesis("S1", (Rule(("true", None), a),)), g)       # many rejected candidates
    assert np.array_equal(g, g0)                                     # input untouched
    h = Hypothesis("S1", (Rule(("color", 3), ("recolor", 6)),))
    first = I.run(h, g)
    for _ in range(3):
        assert np.array_equal(I.run(h, g), first)                     # no hidden state changes the result
    assert len(I._PROGRAMS) >= before[0]


def test_negative_mutants_rejected_and_generator_program_fits():
    t = G.make_task("T_recolor_then_delete", 7)
    h = Hypothesis.from_dict(t["program"])
    assert I.fit(h, t["train"])[0]
    r0 = h.rules[0]
    wrong_colour = [a for a in ACTIONS if a[0] == "recolor" and a != r0.action][0]
    mut = Hypothesis(h.variant, (Rule(r0.selector, wrong_colour),) + h.rules[1:], h.default)
    assert not I.fit(mut, t["train"])[0]
    drop = Hypothesis(h.variant, h.rules[:1], h.default)
    assert not I.fit(drop, t["train"])[0]


def test_generator_deterministic_and_validated():
    for fam in G.TRAIN_FAMILIES + G.HELDOUT_FAMILIES:
        a, b = G.make_task(fam, 3), G.make_task(fam, 3)
        assert a == b and a is not None
        h = Hypothesis.from_dict(a["program"])
        assert I.fit(h, a["train"] + a["test"])[0]                  # every output is the program's execution
        assert all(not np.array_equal(np.asarray(x), np.asarray(y)) for x, y in a["train"] + a["test"])


def test_enumeration_is_best_first_unique_and_valid():
    t = G.make_task("T_line_then_recolor", 2)
    doms = SP.domains(t["train"])
    sc = SP.heuristic_scores(doms, t["train"])
    seen, last = set(), float("inf")
    for h, s in SP.enumerate_programs(doms, sc, 400):
        assert s <= last + 1e-9
        last = s
        assert h.key() not in seen
        seen.add(h.key())
        if len(h.rules) == 2:
            assert h.rules[0].selector != h.rules[1].selector
    assert len(seen) == 400


def test_public_task_has_no_answer_or_program():
    t = G.make_task("H_line_by_size", 4)
    pub = {"task_id": "x", "train": t["train"], "test_inputs": [t["test"][0][0]]}
    assert set(pub) == {"task_id", "train", "test_inputs"}
    from cora_neural_v1 import search as S
    r = S.search_typed(pub, SP.simplicity_scores(SP.domains(pub["train"])), 50)
    assert "test_output" not in r and r["n_candidates"] == 50


def test_extensional_targets_include_generator_components():
    from cora_neural_v1.prior import targets
    from cora_neural_v1.ir import SEL_INDEX, ACT_INDEX
    t = G.make_task("T_delete_by_size", 5)
    y = targets(t)
    h = Hypothesis.from_dict(t["program"])
    assert y["sel"][SEL_INDEX[h.rules[0].selector]] == 1 and y["act"][ACT_INDEX[h.rules[0].action]] == 1
    assert y["var"].sum() >= 1 and len(y["sel"]) == len(SELECTORS) and len(y["act"]) == len(ACTIONS)
