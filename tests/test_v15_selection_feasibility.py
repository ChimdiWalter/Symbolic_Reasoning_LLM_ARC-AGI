"""Static feasibility of protocol v1.5, conditional failure-conditioned
selection.

No test fits or scores a selector on real v1.4 or v1.5 data. Real records are
read only to check that views, queries, the leak boundary and the shuffle can
be built. Every behavioural test uses synthetic queries with planted or
absent signal.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import math
import os
import random
import re
import sys
import tempfile
from fractions import Fraction
from itertools import product

import numpy as np
import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from cora_arc2026 import v14_loc as L                             # noqa: E402
from cora_arc2026 import v15_sel as S                             # noqa: E402
from cora_arc2026 import scorer_fit as SFIT                       # noqa: E402

G = S.G
PROTOCOL = os.path.join(HERE, "docs", "CORA_TTI_FAILURE_CONDITIONED_SELECTION_v1.5.md")
MANIFEST = os.path.join(HERE, "outputs", "tti", "failure_conditioned_selection_v15_manifest.json")
TOKENS = S.feature_tokens()


def _sha(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def _module(name, rel):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, rel))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# -- synthetic queries ---------------------------------------------------------

def _views(rng, d_signal=None, f_signal=None, truth_index=0):
    v = {b: {k: rng.gauss(0, 1) for k in fields} for b, fields in S.VIEW_BLOCKS.items()}
    if d_signal is not None:
        v["D_RICH"][S.D_RICH_FIELDS[truth_index % len(S.D_RICH_FIELDS)]] += d_signal
    if f_signal is not None:
        field = S.F_S7_FIELDS[truth_index % len(S.F_S7_FIELDS)]
        v["F_S7"][field] += f_signal
    return v


def synthetic_queries(n_groups, seed, d_signal=None, f_signal=None, f_redundant=False):
    """Groups of 8 queries over one token pair, 4 with each side true. A
    planted signal raises one field tied to the TRUE token's index."""
    rng = random.Random(seed)
    qs = []
    for g in range(n_groups):
        a, b = rng.sample(range(len(TOKENS)), 2)
        state = [0.0, 0.0, 1.0, 0.0, 0.1]
        for t, r in product((0, 1), range(4)):
            ti = a if t == 0 else b
            v = _views(rng, d_signal, f_signal, ti)
            if f_redundant:
                v["F_S7"] = {k: v["D_RICH"][S.D_RICH_FIELDS[i % len(S.D_RICH_FIELDS)]]
                             for i, k in enumerate(S.F_S7_FIELDS)}
            key = hashlib.sha256(f"{seed}|{g}|{t}|{r}".encode()).hexdigest()
            qs.append({"group": g, "group_digest": f"{g:064x}", "t": t, "r": r,
                       "state": state, "truth": TOKENS[ti],
                       "cands": S.presentation(key, (TOKENS[a], TOKENS[b])),
                       "views": v, "key": key, "other_fits": None})
    return qs


def run(cond, q_fit, q_eval, fblock="F_S7"):
    std = S.standardizer_for(q_fit, fblock)
    pf, pe = S.matched_shuffle(q_fit), S.matched_shuffle(q_eval)
    model, info = S.fit_pairs(S.design(q_fit, cond, std, pf), q_fit)
    scored = S.score_queries(model, S.design(q_eval, cond, std, pe), q_eval)
    return model, scored


def units(cond, q_fit, q_eval):
    return S.group_units(run(cond, q_fit, q_eval)[1], q_eval)[0]


# -- freeze --------------------------------------------------------------------

def test_protocol_manifest_and_implementation_are_the_frozen_ones():
    with open(MANIFEST) as handle:
        man = json.load(handle)
    assert _sha(PROTOCOL) == man["protocol_doc_sha256"]
    with open(MANIFEST + ".sha256") as handle:
        assert handle.read().split()[0] == _sha(MANIFEST)
    for rel, digest in man["implementation_sha256"].items():
        assert _sha(os.path.join(HERE, rel)) == digest, rel
    for name, root in L.dependency_roots(HERE).items():
        assert L.tree_digest(root) == man["dependency_tree_sha256"][name], name
    for path, digest in man["external_file_sha256"].items():
        assert _sha(path) == digest, path
    assert man["runtime_versions"] == L.runtime_versions()
    assert man["caps"]["test_groups"] == S.TEST_GROUPS == 288
    assert man["statistics"]["delta_min"] == "1/20" and S.DELTA_MIN == Fraction(1, 20)
    assert man["parent"]["result_commit"] == "134e36c"
    assert _sha(S.EXCLUSION_FILE) == man["exclusion"]["sha256"]


# -- data laws -----------------------------------------------------------------

def test_exclusion_set_is_rebuilt_exactly_from_the_earlier_corpora():
    with open(S.EXCLUSION_FILE) as handle:
        frozen = json.load(handle)
    rebuilt = S.build_exclusion()
    assert rebuilt == frozen
    assert len(frozen["target_digests"]) == 471 and len(frozen["group_digests"]) == 69


def test_seed_ranges_are_disjoint_from_every_earlier_range():
    with open(MANIFEST) as handle:
        cap = json.load(handle)["caps"]["slot_cap"]
    top = S.TEST_BASE + cap * S.SLOT_STRIDE
    assert S.TEST_BASE > 2.1e8 and top <= S.PILOT_BASE
    assert S.TARGET_SEED_STRIDE * 2 <= S.ATTEMPT_STRIDE
    assert S.SEEDS_PER_TARGET <= S.TARGET_SEED_STRIDE
    #  grid seeds are seed * 97 + i: v1.4 test and smoke stay below 2.1e8 * 97
    assert S.TEST_BASE * 97 > 2.1e8 * 97 + 14


def test_attempt_order_is_balanced_between_targets():
    firsts = [S.attempt_order(S.TEST_BASE + 100 * a, k)[0]
              for a in range(200) for k in range(8)]
    assert 0.45 < sum(firsts) / len(firsts) < 0.55


def test_the_generator_skips_excluded_and_used_pairs_before_any_engine_run(monkeypatch):
    calls = []
    monkeypatch.setattr(S, "make_independent_episode",
                        lambda *a, **k: calls.append(a[2]) or ("TARGET_NOT_FITTABLE", None))
    fam = G.parse_family("(0,0)")
    pair_seed = S.TEST_BASE + 5 * S.SLOT_STRIDE
    anchor = S.CD.sample_target(pair_seed, fam)
    contrast = G.contrast_target(anchor, "FEATURE", rotation=0)
    da, db = S.CV.digest(anchor), S.CV.digest(contrast)
    cfg = {"base": S.TEST_BASE, "budgets": {}, "gate": {}, "prefix": "t",
           "engine": "/nonexistent", "exclusion": (frozenset({da}), frozenset())}
    record = S.run_slot(5, fam, cfg)
    skip = next(x for x in record["skips"] if x["attempt"] == 0)
    assert skip["code"] == S.R_EXCLUDED_TARGET and skip["target_digests"] == [da, db]
    assert not any(pair_seed <= s < pair_seed + S.ATTEMPT_STRIDE for s in calls)
    cfg["exclusion"] = (frozenset(), frozenset())
    calls.clear()
    record = S.run_slot(5, fam, cfg, seen_targets=frozenset({db}))
    assert next(x for x in record["skips"] if x["attempt"] == 0)["code"] == S.R_USED_TARGET
    calls.clear()
    S.run_slot(5, fam, cfg)
    assert any(pair_seed <= s < pair_seed + S.ATTEMPT_STRIDE for s in calls)


def test_a_pair_admits_only_with_four_episodes_per_target_on_its_own_seeds(monkeypatch):
    tried = []

    def fake(schema, other, seed, *rest):
        tried.append(seed)
        return ("ADMITTED", {"seed": seed}) if (seed % 10) % 2 == 0 else ("X", None)

    monkeypatch.setattr(S, "make_independent_episode", fake)
    cfg = {"budgets": {}, "gate": {}, "engine": "", "counter": {"replicate_attempts": 0}}
    eps = S.run_pair("A", "B", 1000, cfg, ("p",), lambda code: None)
    assert eps is not None and len(eps) == 8
    assert sorted(e["target_index"] for e in eps) == [0] * 4 + [1] * 4
    for t in (0, 1):
        seeds = [e["seed"] for e in eps if e["target_index"] == t]
        assert set(seeds) <= set(S.episode_seeds(1000, t))
    assert not set(S.episode_seeds(1000, 0)) & set(S.episode_seeds(1000, 1))
    monkeypatch.setattr(S, "make_independent_episode", lambda *a, **k: ("X", None))
    cfg["counter"]["replicate_attempts"] = 0
    assert S.run_pair("A", "B", 1000, cfg, ("p",), lambda code: None) is None
    assert cfg["counter"]["replicate_attempts"] <= 2 * 5


def _gen():
    return _module("gen15", "scripts/generate_v15_pairs.py")


def _rec(slot, digest=None, targets=()):
    return {"slot": slot, "admitted": digest is not None,
            "group": {"group_digest": digest, "target_digests": list(targets)} if digest else None}


class _Stub:
    def __init__(self, groups):
        self.groups, self.calls = list(groups), []

    def __call__(self, slot, fam, cfg, seen_groups, seen_targets):
        self.calls.append((slot, set(seen_groups), set(seen_targets)))
        g = self.groups.pop(0) if self.groups else None
        return {"slot": slot, "anchor_family": "(0,0)", "admitted": g is not None,
                "group": {"group_digest": g[0], "target_digests": list(g[1])} if g else None,
                "pair_attempts": 1, "replicate_attempts": 0, "skips": [], "rejections": {}}


def test_resume_counts_unique_groups_never_rewrites_and_keeps_the_clock():
    GEN = _gen()
    with tempfile.TemporaryDirectory() as out:
        for slot, g in ((0, ("A", ("a1", "a2"))), (1, None), (2, ("B", ("b1", "b2")))):
            with open(os.path.join(out, f"full{slot:05d}.json"), "w") as handle:
                json.dump(_rec(slot, *(g or (None,))), handle)
        before = {n: _sha(os.path.join(out, n)) for n in os.listdir(out)}
        cfg = {"out": out, "prefix": "full", "target": 3, "slots": 10, "wall": 1e9,
               "engine": out, "manifest": None}
        stub = _Stub([("C", ("c1", "c2"))])
        end = GEN.continue_run(cfg, [None] * 5, first=0.0, run_slot_fn=stub, clock=lambda: 5.0)
        assert stub.calls[0] == (3, {"A", "B"}, {"a1", "a2", "b1", "b2"})
        assert end["stop_reason"] == "target_groups" and end["admitted_groups"] == 3
        assert {n: _sha(os.path.join(out, n)) for n in before} == before
        stub = _Stub([("D", ("d1", "d2"))])
        cfg["target"] = 5
        end = GEN.continue_run(cfg, [None] * 5, first=0.0, run_slot_fn=stub,
                               clock=lambda: 1e9 + 1)
        assert stub.calls == [] and end["stop_reason"] == "wall_clock"


# -- views, queries and the leak boundary ---------------------------------------

def test_views_read_only_the_evidence_keys():
    allowed = {"demo_features", "full_engine_tfg", "descriptor", "trajectory"}

    class Guarded(dict):
        def __getitem__(self, k):
            if k not in allowed:
                raise AssertionError(f"view read {k}")
            return dict.__getitem__(self, k)

        def get(self, k, default=None):
            if k not in allowed:
                raise AssertionError(f"view read {k}")
            return dict.get(self, k, default)

    ep = Guarded(demo_features={k: 1 for k in S.D_AGG_FIELDS},
                 full_engine_tfg={"nodes": [], "edges": []},
                 descriptor={k: 0 for k in S.F_S7_FIELDS}, trajectory=[],
                 target_digest="aa" * 32, seed=123456789, target_tokens=[["M", "area"]])
    v = S.views(ep)
    assert {b: tuple(x) for b, x in v.items()} == S.VIEW_BLOCKS
    assert S.scan_view(v, {"digests": ["aa" * 32], "seeds": [123456789]}) == []


def test_the_leak_scanner_catches_injected_leaks():
    rng = random.Random(3)
    v = _views(rng)
    meta = {"digests": ["ab" * 32], "seeds": [300012345]}
    assert S.scan_view(v, meta) == []
    bad = copy.deepcopy(v)
    bad["F_S7"][S.F_S7_FIELDS[0]] = float(int(("ab" * 32)[:8], 16))
    assert "leaked_identity_number" in S.scan_view(bad, meta)
    bad = copy.deepcopy(v)
    bad["D_RICH"][S.D_RICH_FIELDS[0]] = 300012345
    assert "leaked_identity_number" in S.scan_view(bad, meta)
    bad = copy.deepcopy(v)
    bad["F_SEARCH"]["selector_bucket_0"] = "area"
    assert any(f.startswith("non_numeric") for f in S.scan_view(bad, meta))
    bad = copy.deepcopy(v)
    bad["target"] = {"x": 1.0}
    assert any(f.startswith("blocks") for f in S.scan_view(bad, meta))
    bad = copy.deepcopy(v)
    del bad["F_S7"][S.F_S7_FIELDS[3]]
    assert "fields:F_S7" in S.scan_view(bad, meta)


def test_the_differing_step_is_a_legal_key_feature_and_rejects_other_pairs():
    fam = G.parse_family("(1,0)")
    anchor = S.CD.sample_target(S.TEST_BASE + 7, fam)
    contrast = G.contrast_target(anchor, "FEATURE", rotation=2)
    ta = [list(t) for t in S.CV.tokens_from_ast(anchor)]
    tb = [list(t) for t in S.CV.tokens_from_ast(contrast)]
    state, ca, cb = S.differing_step(ta, tb)
    assert ca[0] == cb[0] == "M" and ca != cb
    assert ca in state.legal_tokens() and cb in state.legal_tokens()
    with pytest.raises(ValueError):
        S.differing_step(ta, ta)
    other = G.contrast_target(anchor, "PARTITION", rotation=0)
    if other is not None:
        with pytest.raises(ValueError):
            S.differing_step(ta, [list(t) for t in S.CV.tokens_from_ast(other)])


def test_the_real_training_resource_builds_without_fitting():
    recs = [json.load(open(os.path.join(HERE, "outputs", "tti", "v14_twin_corpus", n)))
            for n in sorted(os.listdir(os.path.join(HERE, "outputs", "tti", "v14_twin_corpus")))
            if re.fullmatch(r"full\d{5}\.json", n)]
    inc, _ = L.first_admissions(recs)
    groups = sorted((r["group"] for r in inc), key=lambda g: g["group_digest"])
    qs = S.build_queries(groups)
    assert len(groups) == 42 and len(qs) == 336
    assert all(q["truth"] in q["cands"] and all(c[0] == "M" for c in q["cands"]) for q in qs)
    for q in qs:
        g = groups[q["group"]]
        assert S.scan_view(q["views"], {"digests": list(g["target_digests"]) + [g["group_digest"]],
                                        "seeds": [g["pair_seed"]]}) == []


# -- candidate order -------------------------------------------------------------

def test_presentation_order_ignores_which_candidate_is_true():
    for i in range(200):
        key = hashlib.sha256(str(i).encode()).hexdigest()
        a, b = TOKENS[i % 10], TOKENS[(i + 3) % 10]
        assert S.presentation(key, (a, b)) == S.presentation(key, (b, a))
    firsts = sum(1 for i in range(400)
                 if S.presentation(hashlib.sha256(str(i).encode()).hexdigest(),
                                   (TOKENS[0], TOKENS[1]))[0] == TOKENS[0])
    assert 150 < firsts < 250


def test_the_choice_is_invariant_to_presentation_order():
    q = synthetic_queries(30, 5, f_signal=2.0)
    model, scored = run("D+F_ASSOC", q[:160], q[160:])
    assert all(s["order_invariant"] for s in scored)
    x = [1.0] * model.dim
    a, b = TOKENS[0], TOKENS[1]
    assert S.choose(model, x, a, b) == S.choose(model, x, b, a)


def test_a_duplicated_candidate_is_a_tie_with_half_credit():
    q = synthetic_queries(12, 6, f_signal=2.0)
    model, _ = run("D+F_ASSOC", q, q)
    x = [0.5] * model.dim
    assert S.choose(model, x, TOKENS[2], TOKENS[2]) is None
    dup = dict(q[0], cands=(q[0]["truth"], q[0]["truth"]))
    std = S.standardizer_for(q, "F_S7")
    scored = S.score_queries(model, S.design([dup], "D+F_ASSOC", std, [0]), [dup])
    assert scored[0]["tie"] and scored[0]["units"] == 1
    assert abs(scored[0]["nll"] - math.log(2)) < 1e-12


# -- the shuffle -----------------------------------------------------------------

def test_the_matched_shuffle_is_a_cross_group_derangement_that_keeps_D():
    q = synthetic_queries(25, 7)
    pi = S.matched_shuffle(q)
    assert sorted(pi) == list(range(len(q)))
    assert all(pi[i] != i and q[pi[i]]["group"] != q[i]["group"] for i in range(len(q)))
    std = S.standardizer_for(q, "F_S7")
    rows_a = S.design(q, "D+F_ASSOC", std, pi)
    rows_s = S.design(q, "D+F_SHUFFLED", std, pi)
    nd = 1 + sum(1 for f in std.order if ":" not in f)
    assert all(ra[:nd] == rs[:nd] for ra, rs in zip(rows_a, rows_s))
    assert sorted(map(tuple, (r[nd:-5] for r in rows_a))) == \
        sorted(map(tuple, (r[nd:-5] for r in rows_s)))


def test_a_leftover_query_joins_a_three_cycle():
    q = synthetic_queries(3, 8)
    q = [x for x in q if not (x["group"] == 0 and x["r"] >= 2)] + \
        [x for x in q if x["group"] == 0 and x["r"] >= 2][:1]
    pi = S.matched_shuffle(q)
    assert sorted(pi) == list(range(len(q)))
    assert all(pi[i] != i and q[pi[i]]["group"] != q[i]["group"] for i in range(len(q)))


def test_the_shuffle_uses_no_label():
    q = synthetic_queries(20, 9, f_signal=3.0)
    flipped = [dict(x, truth=[c for c in x["cands"] if c != x["truth"]][0]) for x in q]
    assert S.matched_shuffle(q) == S.matched_shuffle(flipped)


# -- the fit ---------------------------------------------------------------------

def test_newton_reaches_the_gradient_ascent_fixed_point_of_the_v12_rule():
    q = synthetic_queries(15, 10, f_signal=1.5, d_signal=1.0)
    std = S.standardizer_for(q, "F_S7")
    rows = S.design(q, "D+F_ASSOC", std)
    model, info = S.fit_pairs(rows, q)
    assert info["final_step"] < 1e-10
    tix = {t: i for i, t in enumerate(TOKENS)}
    W = np.zeros((len(TOKENS), len(rows[0])))
    X = np.array(rows)
    A = np.array([tix[qq["truth"]] for qq in q])
    B = np.array([tix[[c for c in qq["cands"] if c != qq["truth"]][0]] for qq in q])
    for _ in range(20000):
        p = 1 / (1 + np.exp(-((W[A] - W[B]) * X).sum(axis=1)))
        coef = (1 - p)[:, None] * X
        grad = np.zeros_like(W)
        np.add.at(grad, A, coef)
        np.add.at(grad, B, -coef)
        W += 0.5 * (grad / len(q) - 2 * S.LAMBDA * W)
    newton = np.array([model.weights[SFIT.TERMINAL_INDEX[t]] for t in TOKENS])
    assert float(np.max(np.abs(newton - W))) < 1e-5


def test_the_fitted_model_is_the_v12_log_linear_scorer():
    q = synthetic_queries(10, 11, f_signal=2.0)
    std = S.standardizer_for(q, "F_S7")
    rows = S.design(q, "D+F_ASSOC", std)
    model, _ = S.fit_pairs(rows, q)
    assert isinstance(model, SFIT.LogLinearScorer)
    x = rows[0]
    w = model.weights[SFIT.TERMINAL_INDEX[TOKENS[0]]]
    assert model.logits([TOKENS[0]], x)[0] == sum(a * b for a, b in zip(w, x))


def test_neutral_blocks_are_inert():
    q = synthetic_queries(20, 12, f_signal=3.0)
    std = S.standardizer_for(q, "F_S7")
    model, _ = S.fit_pairs(S.design(q, "D", std), q)
    nd = 1 + sum(1 for f in std.order if ":" not in f)
    for t in TOKENS:
        assert all(v == 0.0 for v in model.weights[SFIT.TERMINAL_INDEX[t]][nd:-5])
    q2 = [dict(x, views=dict(x["views"], F_S7={k: 99.0 for k in S.F_S7_FIELDS})) for x in q]
    s1 = S.score_queries(model, S.design(q, "D", std), q)
    s2 = S.score_queries(model, S.design(q2, "D", std), q2)
    assert [a["margin"] for a in s1] == [b["margin"] for b in s2]


# -- controls on planted fixtures ------------------------------------------------

def test_planted_failure_signal_beyond_demonstrations_passes_every_gate():
    fit, ev = synthetic_queries(60, 13, f_signal=2.5), synthetic_queries(120, 14, f_signal=2.5)
    ud, ua, us = (units(c, fit, ev) for c in S.PRIMARY)
    out = S.gates({"acc": ua, "d_demo": [a - b for a, b in zip(ua, ud)],
                   "d_shuffle": [a - b for a, b in zip(ua, us)]})
    assert all(out["test"][k] for k in ("A_above_chance", "B_beats_demo",
                                          "C_beats_shuffle", "D_min_effect"))


def test_pure_noise_failure_evidence_fails_the_shuffle_gate():
    fit, ev = synthetic_queries(60, 15, d_signal=2.0), synthetic_queries(120, 16, d_signal=2.0)
    ud, ua, us = (units(c, fit, ev) for c in S.PRIMARY)
    out = S.gates({"acc": ua, "d_demo": [a - b for a, b in zip(ua, ud)],
                   "d_shuffle": [a - b for a, b in zip(ua, us)]})
    assert out["test"]["A_above_chance"]
    assert not out["test"]["B_beats_demo"] and not out["test"]["C_beats_shuffle"]


def test_failure_evidence_redundant_with_demonstrations_gives_no_increment():
    fit = synthetic_queries(60, 17, d_signal=2.0, f_redundant=True)
    ev = synthetic_queries(120, 18, d_signal=2.0, f_redundant=True)
    ua, ud = units("D+F_ASSOC", fit, ev), units("D", fit, ev)
    out = S.gates({"acc": ua, "d_demo": [a - b for a, b in zip(ua, ud)],
                   "d_shuffle": [0] * len(ua)})
    assert not (out["test"]["B_beats_demo"] and out["test"]["D_min_effect"])


def test_permuted_training_labels_learn_nothing():
    fit = synthetic_queries(60, 19, f_signal=2.5)
    rng = random.Random(0)
    perm = [dict(x, truth=rng.choice(x["cands"])) for x in fit]
    ev = synthetic_queries(120, 20, f_signal=2.5)
    ua = units("D+F_ASSOC", perm, ev)
    out = S.gates({"acc": ua, "d_demo": [0] * len(ua), "d_shuffle": [0] * len(ua)})
    assert not out["test"]["A_above_chance"]


def test_with_no_evidence_every_balanced_group_scores_exactly_one_half():
    fit, ev = synthetic_queries(30, 21), synthetic_queries(30, 22)
    blank = lambda qs: [dict(x, views={b: {k: 0.0 for k in f} for b, f in S.VIEW_BLOCKS.items()})
                        for x in qs]
    fit, ev = blank(fit), blank(ev)
    for x in fit:
        x["views"]["D_RICH"][S.D_RICH_FIELDS[0]] = 1.0 if x["r"] % 2 else 0.0
    ua = units("D", fit, ev)
    assert all(u == S.UNITS_PER_GROUP // 2 for u in ua)


# -- exact inference, power and the ladder --------------------------------------

def test_the_signflip_test_matches_brute_force():
    rng = random.Random(23)
    for _ in range(20):
        vals = [rng.randint(-6, 6) for _ in range(rng.randint(1, 9))]
        a = [abs(v) for v in vals]
        brute = sum(1 for e in product((1, -1), repeat=len(a))
                    if sum(x * y for x, y in zip(e, a)) >= sum(vals))
        assert S.signflip_p(vals) == Fraction(brute, 2 ** len(a))


def test_the_sign_test_is_the_exact_binomial_tail():
    vals = [1, 2, -1, 0, 3, 1, -2, 4]
    pos, m = 5, 7
    expect = sum(Fraction(math.comb(m, i), 2 ** m) for i in range(pos, m + 1))
    assert S.sign_test_p(vals) == expect


def test_the_frozen_power_calculation_reproduces():
    POW = _module("pow15", "scripts/v15_power.py")
    with open(MANIFEST) as handle:
        rec = json.load(handle)["sample_size"]
    assert POW.power(288, 0.05) == rec["simulated_power_at_288"]
    assert rec["simulated_power_at_288"] >= 0.90
    assert POW.power(272, 0.05) < 0.90


def _gate_dict(A=True, B=True, C=True, D=True):
    return {"A_above_chance": A, "B_beats_demo": B, "C_beats_shuffle": C, "D_min_effect": D}


@pytest.mark.parametrize("test,twin,n,ok,expected", [
    (_gate_dict(), None, 288, True, "FAILURE_CONDITIONED_SELECTION_GENERALIZES"),
    (_gate_dict(), None, 100, True, "FAILURE_CONDITIONED_SELECTION_GENERALIZES"),
    (_gate_dict(), None, 71, True, "MIXED_OR_INCONCLUSIVE"),
    (_gate_dict(), None, 288, False, "MIXED_OR_INCONCLUSIVE"),
    (_gate_dict(B=False), _gate_dict(), 288, True, "TWIN_ONLY_SELECTION_SIGNAL"),
    (_gate_dict(B=False), _gate_dict(C=False), 288, True, "DEMONSTRATIONS_SUFFICIENT_FOR_SELECTION"),
    (_gate_dict(D=False), None, 288, True, "DEMONSTRATIONS_SUFFICIENT_FOR_SELECTION"),
    (_gate_dict(C=False), None, 288, True, "FAILURE_ASSOCIATION_NOT_CAUSAL_FOR_SELECTION"),
    (_gate_dict(B=False, C=False), None, 288, True, "FAILURE_ASSOCIATION_NOT_CAUSAL_FOR_SELECTION"),
    (_gate_dict(B=False), None, 200, True, "MIXED_OR_INCONCLUSIVE"),
    (_gate_dict(A=False), None, 288, True, "MIXED_OR_INCONCLUSIVE"),
])
def test_the_classification_ladder(test, twin, n, ok, expected):
    gate_out = {"test": test}
    if twin is not None:
        gate_out["twin"] = twin
    out = S.classify(gate_out, n, ok, True, True, True)
    assert out["classification"] == expected


def test_pass_is_impossible_without_beating_the_demonstration_baseline():
    for A, C, D in product((True, False), repeat=3):
        out = S.classify({"test": _gate_dict(A=A, B=False, C=C, D=D)}, 288, True, True, True, True)
        assert out["classification"] != "FAILURE_CONDITIONED_SELECTION_GENERALIZES"


def test_twin_folds_keep_shared_targets_together_and_are_deterministic():
    groups = [{"group_digest": f"{i:064x}", "target_digests": [f"t{i}", f"t{i + 100}"]}
              for i in range(42)]
    groups[5]["target_digests"][1] = "t0"
    folds = S.twin_folds(groups)
    assert folds == S.twin_folds(groups)
    assert folds[0] == folds[5] and set(folds) == set(range(S.TWIN_FOLDS))


# -- the evaluator's integrity checks on synthetic test records ------------------

def test_the_evaluator_blocks_on_shared_inputs_seed_law_and_excluded_digests(monkeypatch):
    EV = _module("ev15", "scripts/evaluate_v15_selection.py")
    fam = S.FAMILIES[3 % 5]
    pair_seed = S.TEST_BASE + 3 * S.SLOT_STRIDE + 2 * S.ATTEMPT_STRIDE
    anchor = S.CD.sample_target(pair_seed, G.parse_family(fam))
    contrast = G.contrast_target(anchor, "FEATURE", rotation=2)
    if not L.twin_law(anchor, contrast)[0]:
        pytest.skip("pair at this seed fails the twin law")
    da, db = S.CV.digest(anchor), S.CV.digest(contrast)
    toks = {0: [list(t) for t in S.CV.tokens_from_ast(anchor)],
            1: [list(t) for t in S.CV.tokens_from_ast(contrast)]}
    eps = []
    for t in (0, 1):
        for k in range(4):
            eps.append({"target_index": t, "replicate_index": k, "target_digest": [da, db][t],
                        "seed": S.episode_seeds(pair_seed, t)[k], "target_tokens": toks[t],
                        "structural_family": [1, 1], "schema_mdl": 13,
                        "demonstrations": [{"input": [[t, k]], "output": [[1]]}]})
    man = {"environment": {"required_snapshot": dict(L.REQUIRED_ENV)},
           "runtime_versions": {"python": "x"}, "caps": {"wall_clock_s": 100.0}}
    monkeypatch.setattr(EV, "sha256", lambda path: "m")
    monkeypatch.setattr(EV, "TEST_DIR", tempfile.mkdtemp())
    rec = lambda slot, g: {"slot": slot, "admitted": g is not None, "group": g,
                           "environment": dict(L.REQUIRED_ENV), "runtime_versions": {"python": "x"},
                           "freeze_ok": True, "engine_state_problems": [], "manifest_sha256": "m",
                           "started_since_first_start_s": 1.0}
    group = {"group_digest": G.group_digest(da, db), "contrast_type": "FEATURE",
             "anchor_family": fam, "target_digests": [da, db], "pair_seed": pair_seed,
             "episodes": eps}
    records = [rec(0, None), rec(1, None), rec(2, None), rec(3, group)]
    clean = EV.test_integrity(records, man, (frozenset(), frozenset()))
    assert clean == []
    assert "slot3:excluded_digest" in EV.test_integrity(records, man, (frozenset({da}), frozenset()))
    bad = copy.deepcopy(group)
    bad["episodes"][1]["demonstrations"] = bad["episodes"][0]["demonstrations"]
    assert "slot3:inputs_shared" in EV.test_integrity(records[:3] + [rec(3, bad)], man,
                                                        (frozenset(), frozenset()))
    bad = copy.deepcopy(group)
    bad["episodes"][2]["seed"] = pair_seed + 55
    assert "slot3:seed_law" in EV.test_integrity(records[:3] + [rec(3, bad)], man,
                                                   (frozenset(), frozenset()))


# -- end to end on a synthetic corpus ----------------------------------------------

def _synthetic_episode(t, r, tokens, digest, seed, feature_index, rng, plant):
    demos = 3
    nodes = []
    for i in range(demos):
        nodes += [{"id": f"delta{i}", "kind": "delta_signature", "type": "",
                   "attrs": {"same_shape": True, "shrinks": False, "grows": False}},
                  {"id": f"palette{i}", "kind": "palette_change", "type": "",
                   "attrs": {"introduced": rng.randint(0, 3), "removed": rng.randint(0, 3),
                             "n_in": rng.randint(2, 6), "n_out": rng.randint(2, 6)}},
                  {"id": f"shape{i}", "kind": "shape_change", "type": "",
                   "attrs": {"cells_changed": rng.randint(1, 50),
                             "fraction_changed": round(rng.random(), 4)}}]
    desc = {k: rng.gauss(0, 1) for k in S.F_S7_FIELDS}
    desc[S.F_S7_FIELDS[feature_index % len(S.F_S7_FIELDS)]] += plant
    return {"target_index": t, "replicate_index": r, "target_digest": digest,
            "seed": seed, "target_tokens": tokens, "structural_family": [0, 0],
            "schema_mdl": 11, "other_candidate_fits": rng.random() < 0.5,
            "demonstrations": [{"input": [[seed % 9, r, t]], "output": [[1]]}],
            "demo_features": {"n_demonstrations": demos, "mean_cells_changed": rng.random(),
                              "mean_fraction_changed": rng.random(), "same_shape_all": True,
                              "palette_introduced_mean": rng.random(),
                              "palette_removed_mean": rng.random()},
            "full_engine_tfg": {"nodes": nodes, "edges": []},
            "descriptor": desc, "trajectory": []}


def _synthetic_pairs(n, exclusion, used, base, stride_slot):
    """Genuine grammar pairs at genuine seeds, avoiding excluded digests."""
    out = []
    slot = 0
    while len(out) < n:
        fam = S.FAMILIES[slot % 5]
        for attempt in range(S.ATTEMPTS_PER_SLOT):
            ps = base + slot * stride_slot + attempt * S.ATTEMPT_STRIDE
            anchor = S.CD.sample_target(ps, G.parse_family(fam))
            contrast = G.contrast_target(anchor, "FEATURE", rotation=attempt)
            if not L.twin_law(anchor, contrast)[0]:
                continue
            da, db = S.CV.digest(anchor), S.CV.digest(contrast)
            if {da, db} & (exclusion | used):
                continue
            used |= {da, db}
            out.append((slot, attempt, fam, ps, anchor, contrast, da, db))
            break
        else:
            out.append((slot, None, fam, None, None, None, None, None))
        slot += 1
    return out


def test_the_evaluator_runs_end_to_end_on_a_synthetic_corpus(monkeypatch):
    EV = _module("ev15e2e", "scripts/evaluate_v15_selection.py")
    rng = random.Random(31)
    ex_t, _ = S.load_exclusion()
    used = set()
    tmp = tempfile.mkdtemp()
    train_dir, test_dir = os.path.join(tmp, "train"), os.path.join(tmp, "test")
    os.makedirs(train_dir)
    os.makedirs(test_dir)
    man = {"protocol_doc_sha256": "p", "caps": {"wall_clock_s": 1e9, "test_groups": 288},
           "environment": {"required_snapshot": dict(L.REQUIRED_ENV)},
           "runtime_versions": L.runtime_versions(),
           "training_resource": {"groups": 42}}
    man_path = os.path.join(tmp, "manifest.json")
    json.dump(man, open(man_path, "w"))
    tix = {t: i for i, t in enumerate(TOKENS)}

    def build_group(pair, plant, test_seeds):
        slot, attempt, fam, ps, anchor, contrast, da, db = pair
        toks = {0: [list(t) for t in S.CV.tokens_from_ast(anchor)],
                1: [list(t) for t in S.CV.tokens_from_ast(contrast)]}
        _, ca, cb = S.differing_step(toks[0], toks[1])
        eps = []
        for t in (0, 1):
            for r in range(4):
                seed = S.episode_seeds(ps, t)[r] if test_seeds else ps + 10 * t + r
                eps.append(_synthetic_episode(t, r, toks[t], [da, db][t], seed,
                                              tix[[ca, cb][t]], rng, plant))
        return {"group_digest": G.group_digest(da, db), "contrast_type": "FEATURE",
                "anchor_family": fam, "target_digests": [da, db], "pair_seed": ps,
                "episodes": eps}

    for i, pair in enumerate(_synthetic_pairs(42, ex_t, used, 900_000_000, 10_000)):
        g = build_group(pair, 3.0, False) if pair[1] is not None else None
        json.dump({"slot": i, "admitted": g is not None, "group": g},
                  open(os.path.join(train_dir, f"full{i:05d}.json"), "w"))
    for pair in _synthetic_pairs(80, ex_t, used, S.TEST_BASE, S.SLOT_STRIDE):
        slot = pair[0]
        g = build_group(pair, 3.0, True) if pair[1] is not None else None
        rec = {"slot": slot, "admitted": g is not None, "group": g,
               "environment": dict(L.REQUIRED_ENV), "runtime_versions": L.runtime_versions(),
               "freeze_ok": True, "engine_state_problems": [], "manifest_sha256": "m",
               "started_since_first_start_s": 1.0}
        json.dump(rec, open(os.path.join(test_dir, f"full{slot:05d}.json"), "w"))
    monkeypatch.setattr(EV, "TRAIN_DIR", train_dir)
    monkeypatch.setattr(EV, "TEST_DIR", test_dir)
    monkeypatch.setattr(EV, "MANIFEST", man_path)
    monkeypatch.setattr(EV, "verify_freeze", lambda m: [])
    real_sha = EV.sha256
    monkeypatch.setattr(EV, "sha256", lambda p: "m" if p == man_path else real_sha(p))
    out = os.path.join(tmp, "report.json")
    monkeypatch.setattr(sys, "argv", ["evaluate", out])
    EV.main()
    rep = json.load(open(out))
    assert rep["integrity_problems"] == [] and rep["leaks"] == []
    assert rep["train_groups"] == 42 and rep["test_groups"] == 80
    assert rep["order_invariant"] is True
    assert rep["classification"]["classification"] == "FAILURE_CONDITIONED_SELECTION_GENERALIZES"
    assert rep["conditions"]["D+F_ASSOC"]["accuracy"] > rep["conditions"]["D"]["accuracy"]
    assert rep["twin_control"]["accuracy"]["D+F_TWINSWAP"] < \
        rep["twin_control"]["accuracy"]["D+F_ASSOC"]
    assert rep["verification_diagnostic"]["queries"] == 640
    #  the same corpus evaluated twice gives the same bytes
    out2 = os.path.join(tmp, "report2.json")
    monkeypatch.setattr(sys, "argv", ["evaluate", out2])
    EV.main()
    assert open(out).read() == open(out2).read()
