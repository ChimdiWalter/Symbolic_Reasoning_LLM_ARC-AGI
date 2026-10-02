"""Tests of the v1.6 candidate-failure-response module on synthetic fixtures
and on one re-derived v1.5 development episode. They never read a v1.6
prospective record and never fit anything on real labels except the
fit-equivalence check, which reproduces v1.5's own training fit."""
from __future__ import annotations

import hashlib
import json
import os
import random
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tests"))

from cora_arc2026 import v16_cfr as C                             # noqa: E402
import test_v15_selection_feasibility as T                        # noqa: E402

S = C.S


def _synthetic_queries(n_groups, seed=5, amb_share=0.6):
    """v1.5 synthetic queries plus random responses and pair keys."""
    rng = random.Random(seed)
    q = T.synthetic_queries(n_groups, 3)
    toks = S.feature_tokens()
    for x in q:
        x["family"] = str(x.get("family", "(0,0)"))
        g = x["group"]
        rng2 = random.Random(1000 + g)
        pair = sorted(rng2.sample(toks, 2))
        x["pair_key"] = json.dumps([list(t) for t in pair])
        x["group_digest"] = hashlib.sha256(str(g).encode()).hexdigest()
        rf = [rng.random() for _ in C.RESPONSE_FIELDS]
        rs = [rng.random() for _ in C.RESPONSE_FIELDS]
        x["resp"] = {"first": rf, "second": rs}
        x["delta"] = [round(a - b, C.ROUND) for a, b in zip(rf, rs)]
        x["ambiguous"] = rng.random() < amb_share
        x["transition"] = "K_NO_CONSISTENT|LOO_ALL|LOO_NONE"
    return q


def test_p0_rule_is_antisymmetric_and_ordered():
    assert C.p0_choice([0.2, 0, 0, 0]) == 1
    assert C.p0_choice([0, 0.1, 0, 0]) == -1          # smaller error wins
    assert C.p0_choice([0, 0, 0, -3]) == 1            # fewer entries wins
    assert C.p0_choice([0.1, 9, 9, 9]) == 1           # first key decides
    assert C.p0_choice([0, 0, 0, 0]) == 0
    rng = random.Random(1)
    for _ in range(200):
        d = [rng.choice([-1, 0, 1]) * rng.random() for _ in range(4)]
        assert C.p0_choice([-v for v in d]) == -C.p0_choice(d)


def test_p0_units_and_fallback():
    q = {"cands": ("a", "b"), "truth": "a"}
    assert C.p0_units(q, [1, 0, 0, 0]) == 2
    assert C.p0_units(q, [-1, 0, 0, 0]) == 0
    assert C.p0_units(q, [0, 0, 0, 0]) == 1
    assert C.p0_units(q, [0, 0, 0, 0], fallback_units=2) == 2


def test_swapped_response_inverts_every_p0_decision():
    q = _synthetic_queries(20)
    for x in q:
        a = C.p0_units(x, x["delta"])
        b = C.p0_units(x, [-v for v in x["delta"]])
        assert a + b == 2


def test_response_shuffle_is_a_valid_matched_permutation():
    q = _synthetic_queries(30)
    pi = C.response_shuffle(q)
    assert sorted(pi) == list(range(len(q)))
    for i, j in enumerate(pi):
        assert q[j]["group"] != q[i]["group"]
        assert q[j]["ambiguous"] == q[i]["ambiguous"]
    fid = C.shuffle_fidelity(q, pi)
    assert fid["same_status_share"] == 1.0 and fid["same_group_count"] == 0


def test_donor_delta_is_reoriented_for_same_pair_donors():
    q = _synthetic_queries(30)
    pi = C.response_shuffle(q)
    d = [x["delta"] for x in q]
    dd = C.donor_deltas(q, pi, d)
    for i, j in enumerate(pi):
        if q[j]["pair_key"] == q[i]["pair_key"] and q[j]["cands"][0] != q[i]["cands"][0]:
            assert dd[i] == [-v for v in d[j]]
        else:
            assert dd[i] == d[j]


def test_cv_a_folds_keep_token_pairs_together():
    q = _synthetic_queries(40)
    groups = [{"group_digest": hashlib.sha256(str(g).encode()).hexdigest(), "target_digests": []}
              for g in range(40)]
    folds = C.cv_a_folds(groups, q)
    assert set(folds) <= set(range(C.CV_FOLDS))
    by_pair = {}
    for x in q:
        by_pair.setdefault(x["pair_key"], set()).add(folds[x["group"]])
    assert all(len(v) == 1 for v in by_pair.values())


def test_rms_scale_keeps_antisymmetry_and_drops_constant_fields():
    d = [[1.0, 0.0, 2.0, 0.0], [-1.0, 0.0, -2.0, 0.0]]
    sc = C.rms_scale(d)
    assert sc[1] == 0.0 and sc[3] == 0.0 and C.active_fields(sc) == 2
    s = C.apply_scale(d, sc)
    assert s[0] == [-v for v in s[1]]


def test_fit_with_no_response_is_v15_fit_and_response_weights_are_shared():
    import numpy as np
    q = _synthetic_queries(24)
    std = S.standardizer_for(q, None)
    rows = C.d_rows(q, std)
    m15, _ = S.fit_pairs(rows, q)
    m16, info = C.fit(q, rows=rows)
    SFIT = S._scorer()
    W15 = np.array([m15.weights[SFIT.TERMINAL_INDEX[t]] for t in S.feature_tokens()])
    assert info["converged"] and float(np.max(np.abs(W15 - m16["W"]))) < 1e-9
    m, info = C.fit(q, rows=rows, deltas=[x["delta"] for x in q])
    assert info["converged"] and m["v"].shape == (4,)


def test_score_is_order_invariant_and_swap_negates_margin():
    q = _synthetic_queries(24)
    std = S.standardizer_for(q, None)
    rows = C.d_rows(q, std)
    d = [x["delta"] for x in q]
    m, _ = C.fit(q, rows=rows, deltas=d)
    sc = C.score(m, q, rows, d)
    assert all(s["order_invariant"] for s in sc)
    m_r, _ = C.fit(q, deltas=d)
    a = C.score(m_r, q, None, d)
    b = C.score(m_r, q, None, [[-v for v in x] for x in d])
    assert all(abs(x["margin"] + y["margin"]) < 1e-9 for x, y in zip(a, b))


def test_residualizer_never_fits_on_the_evaluation_pool():
    q = _synthetic_queries(40)
    std = S.standardizer_for(q, None)
    tr, ev = q[:60], q[60:]
    dtr, dev = C.residualized(tr, ev, None, std)
    ev2 = [dict(x, resp={"first": [9.0] * 4, "second": [9.0] * 4}) for x in ev]
    dtr2, _ = C.residualized(tr, ev2, None, std)
    assert dtr == dtr2                       # evaluation responses never touch the training fit
    assert len(dev) == len(ev) and len(dtr) == len(tr)


def test_increment_summary_counts_only_ambiguous_queries():
    q = _synthetic_queries(12, amb_share=0.5)
    ua = [2] * len(q)
    ub = [0] * len(q)
    s = C.increment_summary(q, ua, ub)
    assert s["queries"] == sum(1 for x in q if x["ambiguous"])
    assert s["mean_increment"] == 1.0


def test_heldout_pair_rule_is_a_fixed_hash():
    assert C.heldout_pair("x") == (hashlib.sha256(b"v16-heldout|x").hexdigest()[0] in "01234")


@pytest.mark.skipif(not os.path.exists(os.path.join(HERE, "outputs", "tti", "v15_test_corpus", "full00000.json")),
                    reason="needs the v1.5 development corpus")
def test_probe_restores_state_and_is_order_independent_on_a_real_episode():
    import re
    cdir = os.path.join(HERE, "outputs", "tti", "v15_test_corpus")
    rec = None
    for n in sorted(os.listdir(cdir)):
        if re.match(r"^full\d{5}\.json$", n):
            with open(os.path.join(cdir, n)) as handle:
                r = json.load(handle)
            if r["admitted"]:
                rec = r
                break
    a, b = C.group_candidates(rec, S.TEST_BASE)
    pairs = C.episode_pairs(rec["group"]["episodes"][0])
    s0 = C.state_snapshot()
    pa, pb = C.probe(a, pairs), C.probe(b, pairs)
    s1 = C.state_snapshot()
    pb2, pa2 = C.probe(b, pairs), C.probe(a, pairs)
    assert s0 == s1 == C.state_snapshot()
    assert json.dumps(pa, sort_keys=True) == json.dumps(pa2, sort_keys=True)
    assert json.dumps(pb, sort_keys=True) == json.dumps(pb2, sort_keys=True)
    assert set(pa["response"]) == set(C.RESPONSE_FIELDS)
    with pytest.raises(ValueError):
        bad = json.loads(json.dumps(rec))
        bad["group"]["target_digests"][1] = "0" * 64
        C.group_candidates(bad, S.TEST_BASE)
