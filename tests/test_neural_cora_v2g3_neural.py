"""ncv2-g3 Phase 4 interfaces: exact cell-token alignment and pooling, joint rule features, scorers and controls, the
grammar automaton (every decoded sketch typechecks), residual ranking (zero residual = C+H), and untrusted proposals.

No model is loaded. A toy tokenizer with the audited property of the Qwen3-4B checkpoint (each digit is one token
whose id equals the colour; no other token has an id below 10) stands in for the real one.
"""
import os
import sys

import numpy as np
import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from cora_neural_v2.rast import ASTError, N                              # noqa: E402
from cora_neural_v2g2 import families as F                               # noqa: E402
from cora_neural_v2g2 import grammar as G                                # noqa: E402
from cora_neural_v2g2 import search as S2                                # noqa: E402
from cora_neural_v2 import search as G1S                                 # noqa: E402
from cora_neural_v2g3 import joint as J                                  # noqa: E402
from cora_neural_v2g3 import neural as NN                                # noqa: E402
from cora_neural_v2g3 import search as S3                                # noqa: E402

SPECIAL = {"<|im_start|>": 11, "<|im_end|>": 12, "user": 13, "assistant": 14, "\n": 10}


def toy_ids(text):
    ids, i = [], 0
    while i < len(text):
        for s, t in SPECIAL.items():
            if text.startswith(s, i):
                ids.append(t)
                i += len(s)
                break
        else:
            ids.append(int(text[i]))
            i += 1
    return ids


@pytest.fixture(scope="module")
def task():
    return F.make_task("negated_selector_delete", 7)[0]


# ------------------------------------------------------------------ A. alignment and pooling
def test_alignment_is_exact_and_checked(task):
    ids = toy_ids(NN.serialize(task))
    amap = NN.align(task, ids)
    for role, i, g in NN.grids(task):
        for r, row in enumerate(g):
            for c, v in enumerate(row):
                assert ids[amap[(role, i, r, c)]] == v
    bad = list(ids)
    bad[amap[("test_in", 0, 0, 0)]] = (bad[amap[("test_in", 0, 0, 0)]] + 1) % 10
    with pytest.raises(ValueError):
        NN.align(task, bad)


def test_reread_copies_come_after_the_test_input(task):
    ids = toy_ids(NN.serialize(task, reread=True))
    amap = NN.align(task, ids, reread=True)
    last_test = max(p for k, p in amap.items() if k[0] == "test_in")
    assert all(p > last_test for k, p in amap.items() if k[0] == "reread_in")


def test_object_slots_pool_their_cells(task):
    ids = toy_ids(NN.serialize(task))
    states = np.arange(len(ids) * 3, dtype=float).reshape(len(ids), 3)
    slots = NN.object_slots(task, states, ids)
    amap = NN.align(task, ids)
    from cora_neural_v2g3.scene import native_objects
    objs = native_objects(task["train"][0][0], "S1")[0]
    o = objs[0]
    want = states[[amap[("demo_in", 0, r, c)] for r, c in sorted(o.cells)]].mean(0)
    assert np.allclose(slots[(0, 0)], want)


# ------------------------------------------------------------------ B/D. features, scorers, residual ranking
def test_zero_residual_keeps_the_ch_order(task):
    ev, views = S2.evidence2(task["train"]), G1S.distinct_views(task)
    plain = J.build_pools(task, ev, views[:1])
    feats = lambda rule, prior, key: NN.rule_features(rule, prior, key)            # noqa: E731
    zero = J.build_pools(task, ev, views[:1], J.JointConfig(rescore=NN.residual_rescore(NN.ZeroScorer(), feats)))
    assert [p[0] for p in plain[views[0]]] == [p[0] for p in zero[views[0]]]


def test_features_have_a_fixed_length_and_include_selected_slots(task):
    ev, views = S2.evidence2(task["train"]), G1S.distinct_views(task)
    pool = J.build_pools(task, ev, views[:1])[views[0]]
    rule, prior, key = pool[0]
    picks = [frozenset({0})] + [frozenset()] * (len(task["train"]) - 1)
    slots = {(0, 0): np.array([1.0, 2.0])}
    v = NN.rule_features(rule, prior, key, picks, slots, (3, 0, 1), slot_dim=2)
    assert len(v) == len(NN.rule_features(rule, prior, key)) + 2 and list(v[-2:]) == [1.0, 2.0]


def test_untrained_scorer_is_deterministic_and_shuffled_slots_are_a_derangement():
    x = np.linspace(-1, 1, 25)
    assert NN.UntrainedScorer(25, seed=3)(x) == NN.UntrainedScorer(25, seed=3)(x)
    ids = [f"t{i}" for i in range(9)]
    sh = NN.ShuffledSlots(ids, seed=1)
    partners = [sh.partner(t) for t in ids]
    assert all(p != t for p, t in zip(partners, ids)) and sorted(partners) == sorted(ids)


# ------------------------------------------------------------------ C. the grammar automaton
def test_every_decoded_sketch_typechecks():
    sketches = NN.UntrainedSketchDecoder(seed=0).propose(None, 200)
    assert len(sketches) >= 150
    for s in sketches:
        assert G.typecheck(s) == "PROGRAM"


def test_automaton_rejects_illegal_tokens_and_round_trips():
    aut = NN.GrammarAutomaton()
    st = aut.start()
    with pytest.raises(ASTError):
        aut.step(st, ("op", "recolor"))                     # an ACTION where a PROGRAM is expected
    toks = [("op", "program"), ("lit", "S1"), ("len", 1), ("op", "rule"), ("hole", "PRED"), ("op", "delete"),
            ("lit", "keep"), ("op", "same_as_input")]
    for t in toks:
        st = aut.step(st, t)
    assert aut.done(st)
    assert aut.build(st[1]) == G.parse("(program S1 (list (rule (hole PRED) (delete))) keep (same_as_input))")


# ------------------------------------------------------------------ E. untrusted proposals
def test_proposals_are_admitted_completed_and_executed(task):
    bad = NN.Proposal(N("program", ("S1", (N("rule", (N("delete", ()), N("delete", ()))),), "keep", N("same_as_input", ()))), "toy")
    sketch = NN.Proposal(G.parse("(program S1 (list (rule (hole PRED) (delete))) keep (same_as_input))"), "toy", 1.0)
    r = S3.search(task, 300, use_joint=False, proposals=[bad, sketch], proposal_ratio=4)
    assert r["state"]["proposal_rejected"] == 1
    assert r["fit_origins"].get("proposal:toy", 0) >= 1
    assert r["first_fit_at"] is not None and r["first_fit_at"] <= 40
