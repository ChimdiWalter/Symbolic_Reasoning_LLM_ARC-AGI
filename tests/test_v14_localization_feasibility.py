"""Static feasibility of protocol v1.4, mechanistic frontier localization.

No test reads a v1.4 experiment episode or computes any stage statistic on
real data. Synthetic groups are used to show the instrument can localize a
planted effect and does not report one where there is none.
"""
from __future__ import annotations

import glob
import hashlib
import json
import math
import os
import random
import re
import sys
import tempfile
from collections import Counter
from fractions import Fraction
from itertools import product

import numpy as np
import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tests"))

from cora_arc2026 import v14_loc as L                             # noqa: E402

G = L.G
PROTOCOL = os.path.join(HERE, "docs",
                        "CORA_TTI_MECHANISTIC_FRONTIER_LOCALIZATION_v1.4.md")
MANIFEST = os.path.join(HERE, "outputs", "tti",
                        "mechanistic_frontier_v14_manifest.json")
CAL_FILE = os.path.join(HERE, "outputs", "tti", "v13_calibration",
                        "calibration.json")


def _sha(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def _cal():
    with open(CAL_FILE) as handle:
        return json.load(handle)


# -- freeze ------------------------------------------------------------------

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
    assert set(man["external_file_sha256"]) == set(L.EXTERNAL_FILES)
    assert man["runtime_versions"] == L.runtime_versions()
    assert man["environment"]["required_snapshot"] == L.REQUIRED_ENV
    caps = man["caps"]
    assert caps["target_groups"] == L.TARGET_GROUPS == 42
    assert caps["floor_groups"] == L.FLOOR_GROUPS == 14
    assert caps["slot_cap"] * L.SLOT_STRIDE + L.SEED_BASE < L.SMOKE_BASE


def test_the_v13_calibration_is_the_committed_one():
    assert _sha(CAL_FILE) == \
        "ba82865e52cd9e025442ea73ee7ad83ee894b5ad8610a7753ce37a44051c7c02"
    cal = _cal()
    assert tuple(cal["demo_features"]) == tuple(G.DEMO_FEATURES)
    assert tuple(cal["descriptor_order"]) == tuple(G.DESCRIPTOR_ORDER)
    assert all(s > 0 for s in cal["descriptor_std"] + cal["demo_std"])


# -- descriptors -------------------------------------------------------------

def test_skeleton_abstracts_literals_and_keeps_structure():
    a = ["group:recolor", [{"n_members": 5, "selector": {"feature": "area",
                                                         "value": 3}}]]
    b = ["group:recolor", [{"n_members": 9, "selector": {"feature": "area",
                                                         "value": 7}}]]
    c = ["group:recolor", [{"n_members": 5, "selector": {"feature": "shape",
                                                         "value": 3}}]]
    assert L.key(a) == L.key(b)
    assert L.key(a) != L.key(c)
    assert L.skeleton(True) is True and L.skeleton(None) is None


def test_ruzicka_distance_properties():
    a, b = Counter({"x": 2, "y": 1}), Counter({"x": 1, "z": 4})
    assert L.ruzicka(a, a) == 0.0
    assert L.ruzicka(Counter(), Counter()) == 0.0
    assert L.ruzicka(Counter({"x": 1}), Counter({"y": 1})) == 1.0
    assert L.ruzicka(a, b) == L.ruzicka(b, a)
    assert L.ruzicka(a, b) == pytest.approx(1 - 1 / 7)


def _view(typed=(), fits=(), programs=(), mismatch=(), nodes=(), edges=(),
          demo=None, descriptor=None):
    traj = [[json.dumps(t), "typed"] for t in typed]
    traj += [[json.dumps(f), o] for f, o in fits]
    traj += [[json.dumps(p), o] for p, o in programs]
    return {"trajectory": traj, "mismatch": list(mismatch),
            "full_engine_tfg": {"nodes": list(nodes), "edges": list(edges)},
            "demo_features": demo or {k: 0 for k in G.DEMO_FEATURES},
            "descriptor": descriptor or {k: 0 for k in G.DESCRIPTOR_ORDER}}


def test_selector_stage_is_derived_from_event_order():
    g1 = ["group:recolor", [{"n_members": 2, "selector": None}]]
    g2 = ["group:delete", [{"n_members": 1, "selector": None}]]
    failed = ["group:recolor", [{"n_members": 2, "selector": {"f": "area"}}]]
    ok = ["rule:delete", [{"selector": {"f": "shape"}, "action": {"d": "x"}}]]
    view = {"trajectory": [[json.dumps(g1), "typed"],
                           [json.dumps(failed), "slot_fit_failed"],
                           [json.dumps(g2), "typed"],
                           [json.dumps(g1), "typed"],
                           [json.dumps(ok), "slot_fit_ok"]]}
    s3 = L.stage_multiset(view, "S3")
    assert sum(s3.values()) == 3
    kinds = Counter(json.loads(k)[0] for k in s3)
    assert kinds == Counter({"selector_induced": 2, "no_selector": 1})
    s4 = L.stage_multiset(view, "S4")
    assert Counter(json.loads(k)[0] for k in s4) == \
        Counter({"slot_fit_failed": 1, "slot_fit_ok": 1})


def test_descriptors_read_only_the_allowlisted_view():
    class Guarded(dict):
        def __getitem__(self, k):
            if k not in L.VIEW_KEYS:
                raise AssertionError(f"descriptor read {k}")
            return dict.__getitem__(self, k)

    base = _view(typed=[["group:recolor", [{"n_members": 2}]]])
    ep = Guarded(base, target_digest="aa" * 32, target_tokens=[["Key", "area"]],
                 seed=123456789, structural_family=[0, 0])
    view = L.model_view(ep)
    other = dict(base, target_digest="bb" * 32, seed=987654321)
    for stage in ("S2", "S3", "S4", "S5", "S6", "S7a"):
        assert L.stage_multiset(view, stage) == \
            L.stage_multiset(L.model_view(other), stage)
    assert set(view) == set(L.VIEW_KEYS)


def test_mismatch_classes():
    t = np.array([[1, 2], [3, 4]])
    assert L.mismatch_class(None, t) == "undefined"
    assert L.mismatch_class(np.zeros((3, 3)), t) == "shape_mismatch"
    assert L.mismatch_class(np.array([[1, 2], [3, 9]]), t) == "palette_extra"
    assert L.mismatch_class(np.array([[1, 2], [4, 3]]), t) == "cells_wrong"
    assert L.mismatch_class(t.copy(), t) == "exact_on_demo"


# -- the within-group null ---------------------------------------------------

IDX = [(t, r) for r in range(4) for t in (0, 1)]


def _random_dist(rng, ties):
    n = len(IDX)
    d = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            v = rng.choice([0.0, 0.5, 1.0]) if ties else rng.random()
            d[i][j] = d[j][i] = v
    return d


def test_the_twin_is_never_a_companion():
    d = [[1.0] * 8 for _ in range(8)]
    for i, (t, r) in enumerate(IDX):
        for j, (t2, r2) in enumerate(IDX):
            if r == r2 and i != j:
                d[i][j] = 0.0          # the twin is closest of all
    credits, hits, strict, tied = L.nn_credits(d, IDX, [t for t, _ in IDX])
    assert all(c == Fraction(1, 2) for c in credits)
    assert all(t == 1 for t in tied) and sum(strict) == 0


def test_ties_share_credit_and_a_strict_hit_needs_every_tie_to_agree():
    d = [[1.0] * 8 for _ in range(8)]
    q = IDX.index((0, 0))
    d[q][IDX.index((0, 1))] = d[q][IDX.index((1, 2))] = 0.1
    credits, hits, strict, _ = L.nn_credits(d, IDX, [t for t, _ in IDX])
    assert credits[q] == Fraction(1, 2) and strict[q] == 0
    d[q][IDX.index((1, 2))] = 0.2
    credits, hits, strict, _ = L.nn_credits(d, IDX, [t for t, _ in IDX])
    assert credits[q] == 1 and strict[q] == 1 and hits[q] == 1


@pytest.mark.parametrize("ties", [False, True])
def test_the_null_expectation_is_exactly_one_half_for_any_distances(ties):
    rng = random.Random(7 + ties)
    for _ in range(25):
        d = _random_dist(rng, ties)
        totals, hit_totals = [], []
        for sigma in product((0, 1), repeat=4):
            labels = [t ^ sigma[r] for t, r in IDX]
            c, hits, strict, _ = L.nn_credits(d, IDX, labels, salt="x")
            totals.append(sum(c))
            hit_totals.append(sum(hits))
            assert all(s <= h for s, h in zip(strict, hits))
        assert sum(totals) / len(totals) == 4      # 8 queries x 1/2
        assert Fraction(sum(hit_totals), len(hit_totals)) == 4


def test_randomization_p_matches_brute_force():
    rng = random.Random(11)
    nulls, observed = [], Fraction(0)
    for _ in range(3):
        d = _random_dist(rng, True)
        vals = [sum(L.nn_credits(d, IDX, [t ^ s[r] for t, r in IDX])[0])
                for s in product((0, 1), repeat=4)]
        nulls.append(vals)
        observed += vals[0]
    brute = sum(1 for combo in product(*nulls) if sum(combo) >= observed)
    assert L.randomization_p(observed, nulls) == Fraction(brute, 16 ** 3)


def test_one_group_can_never_qualify():
    # a pattern and its complement give the same total, so p >= 2/16
    d = [[1.0] * 8 for _ in range(8)]
    for i, (t, r) in enumerate(IDX):
        for j, (t2, r2) in enumerate(IDX):
            if t == t2 and r != r2:
                d[i][j] = 0.0
    vals = [sum(L.nn_credits(d, IDX, [t ^ s[r] for t, r in IDX])[0])
            for s in product((0, 1), repeat=4)]
    assert L.randomization_p(vals[0], [vals]) >= Fraction(1, 8)


def test_exact_sample_size_for_p1_060_against_one_half():
    def pmf(n, p):
        p = Fraction(p)
        return [math.comb(n, i) * p ** i * (1 - p) ** (n - i)
                for i in range(n + 1)]

    def design(n):
        f0, f1 = pmf(n, Fraction(1, 2)), pmf(n, Fraction(3, 5))
        tail0, c = Fraction(0), n + 1
        while c > 0 and tail0 + f0[c - 1] <= Fraction(1, 100):
            tail0 += f0[c - 1]
            c -= 1
        return c, tail0, sum(f1[c:], Fraction(0))

    first = next(n for n in range(8, 800, 8)
                 if design(n)[2] >= Fraction(9, 10))
    c, size, power = design(first)
    assert first == 336 == 8 * L.TARGET_GROUPS
    assert c == 190
    assert 0.0094 < float(size) < 0.0095 and 0.910 < float(power) < 0.911


# -- the classification ladder -----------------------------------------------

def _results(identifying=(), rand_only=()):
    out = {}
    for s in L.ALL_STAGES:
        out[s] = {"target_identifying": s in identifying,
                  "p_randomization": 0.001 if s in identifying or s in rand_only
                  else 0.5}
    return out


@pytest.mark.parametrize("identifying,rand_only,groups,expected", [
    (("S2",), (), 42, "RAW_TRAJECTORY_SIGNAL_TFG_LOSS"),
    (("S4", "S6"), (), 20, "RAW_TRAJECTORY_SIGNAL_TFG_LOSS"),
    (("S5",), (), 42, "LATE_EXECUTION_SIGNAL_ONLY"),
    (("S6", "S7a"), (), 42, "LATE_EXECUTION_SIGNAL_ONLY"),
    (("S7a",), (), 42, "TFG_AGGREGATION_LOSS"),
    (("S2", "S7"), (), 42, "CURRENT_TFG_IDENTIFYING_UNDER_TWINS"),
    ((), (), 42, "REASONER_TRAJECTORY_INSENSITIVE"),
    ((), ("S3",), 42, "MIXED_OR_INCONCLUSIVE"),
    ((), (), 41, "MIXED_OR_INCONCLUSIVE"),
    (("S2",), (), 13, "MIXED_OR_INCONCLUSIVE"),
    (("S5",), ("S2",), 42, "MIXED_OR_INCONCLUSIVE"),
    (("S7a",), ("S3",), 42, "MIXED_OR_INCONCLUSIVE"),
    (("S2",), ("S5",), 42, "RAW_TRAJECTORY_SIGNAL_TFG_LOSS"),
    (("S7",), ("S2",), 42, "CURRENT_TFG_IDENTIFYING_UNDER_TWINS"),
])
def test_classification_ladder(identifying, rand_only, groups, expected):
    c = L.classify(_results(identifying, rand_only), groups)
    assert c["classification"] == expected


def test_loss_point_distinguishes_graph_from_aggregation():
    assert L.classify(_results(("S3",)), 42)["loss_point"] == "TFG construction"
    assert L.classify(_results(("S3", "S7a")), 42)["loss_point"] == \
        "42-field aggregation"
    assert L.classify(_results(("S7a",)), 42)["loss_point"] == \
        "42-field aggregation"


def test_s0_never_enters_the_classification():
    assert L.classify(_results(("S0",)), 42)["classification"] == \
        "REASONER_TRAJECTORY_INSENSITIVE"


# -- planted effects on synthetic groups -------------------------------------

def _synthetic_groups(plant, n_groups=42, seed=3):
    """Every descriptor depends on the replicate (the shared input) only,
    except the planted stage, which also depends on the target."""
    rng = random.Random(seed)
    groups = []
    for g in range(n_groups):
        eps = []
        base = {r: [["group:op%d" % rng.randrange(12), [{"n_members": 1}]]
                    for _ in range(rng.randrange(2, 6))] for r in range(4)}
        demo = {r: {k: rng.random() for k in G.DEMO_FEATURES} for r in range(4)}
        desc = {r: {k: rng.random() * 5 for k in G.DESCRIPTOR_ORDER}
                for r in range(4)}
        for r in range(4):
            for t in (0, 1):
                typed = list(base[r])
                mismatch = []
                d = dict(desc[r])
                if plant == "S2":
                    typed.append(["group:planted%d" % t, [{"n_members": 1}]])
                if plant == "S6":
                    mismatch = [{"ast": json.dumps(["prog:x", [{}]]),
                                 "per_demo": ["cells_wrong" if t else
                                              "palette_extra"] * 3}]
                if plant == "S7":
                    d["op_bucket_0"] = d["op_bucket_0"] + 40 * t
                if plant == "reacts":
                    typed.append(["group:u%d_%d_%d" % (g, r, t),
                                  [{"n_members": 1}]])
                ep = _view(typed=typed, mismatch=mismatch, demo=demo[r],
                           descriptor=d)
                ep.update(target_index=t, replicate_index=r)
                if t == 0:
                    ep["self_rerun"] = dict(
                        json.loads(json.dumps(ep)),
                        order=["A" if w == 0 else "B" if w == 1 else "rerun"
                               for w in L.RUN_ORDERS[(g + r) % 6]])
                eps.append(ep)
        groups.append({"episodes": eps})
    return groups


@pytest.mark.parametrize("plant,expected,determining,reason", [
    ("S2", "RAW_TRAJECTORY_SIGNAL_TFG_LOSS", "S2", None),
    ("S6", "LATE_EXECUTION_SIGNAL_ONLY", "S6", None),
    ("S7", "CURRENT_TFG_IDENTIFYING_UNDER_TWINS", "S7", None),
    ("reacts", "REASONER_TRAJECTORY_INSENSITIVE", None,
     "REACTS_BUT_NOT_CONSISTENTLY"),
    (None, "REASONER_TRAJECTORY_INSENSITIVE", None,
     "NO_REACTION_BEYOND_TIMING_NOISE"),
])
def test_the_instrument_localizes_a_planted_effect(plant, expected,
                                                   determining, reason):
    out = L.audit_groups(_synthetic_groups(plant), _cal())
    c = out["classification"]
    assert c["classification"] == expected
    assert c["determining_stage"] == determining
    if determining:
        assert out["stages"][plant]["hit_rate"] == 1.0
        assert c["determining_stage_survives_holm"]
        assert out["sensitivity"][plant]["twin_farther"] == 168
        assert (plant in c["reacting_stages"]) == (plant in L.REACTION_STAGES)
    else:
        assert c["reason"] == reason
    if plant == "reacts":
        assert c["reacting_stages"] == ["S2", "S3"]
        assert out["sensitivity"]["S2"]["twin_farther"] == 168
    assert not out["stages"]["S0"]["target_identifying"]


def test_a_tie_heavy_coarse_signal_can_still_qualify():
    """The reviewer's case: coarse tokens tie across labels. Strict hits
    stay below 1/2 at any sample size; hash-broken hits do not."""
    rng = random.Random(5)
    groups = []
    for g in range(42):
        eps = []
        for r in range(4):
            for t in (0, 1):
                agree = rng.random() < 0.8
                tok = "group:recolor" if (t == 0) == agree else "group:delete"
                ep = _view(typed=[[tok, [{}]]])
                ep.update(target_index=t, replicate_index=r)
                if t == 0:
                    ep["self_rerun"] = dict(json.loads(json.dumps(ep)),
                                            order=["A", "B", "rerun"])
                eps.append(ep)
        groups.append({"episodes": eps})
    res = L.stage_result(groups, "S2", _cal())
    assert res["tie_fraction"] > 0.9
    assert res["strict_rate"] < res["hit_rate"]
    assert res["target_identifying"]


def test_rescoring_alone_never_counts_as_a_reaction():
    """Identical trajectories, mismatch classes differing only because each
    target's outputs differ: S6 differs, but no reaction is recorded."""
    groups = []
    for g in range(42):
        eps = []
        for r in range(4):
            typed = [["group:op%d" % ((g + r) % 5), [{}]]]
            for t in (0, 1):
                mm = [{"ast": json.dumps(["prog:x", [{}]]),
                       "per_demo": ["cells_wrong", "palette_extra" if t else
                                    "cells_wrong"]}]
                ep = _view(typed=typed, mismatch=mm)
                ep.update(target_index=t, replicate_index=r)
                if t == 0:
                    ep["self_rerun"] = dict(json.loads(json.dumps(ep)),
                                            order=["A", "B", "rerun"])
                eps.append(ep)
        groups.append({"episodes": eps})
    out = L.audit_groups(groups, _cal())
    assert out["sensitivity"]["S6"]["twin_farther"] == 168
    assert out["classification"]["reacting_stages"] == []


def test_sign_test_counts_and_order_strata():
    groups = _synthetic_groups("reacts", n_groups=3)
    r = L.sensitivity(groups, "S2", _cal())
    assert (r["twin_farther"], r["rerun_farther"], r["ties"]) == (12, 0, 0)
    strata = r["strata_twin_farther_rerun_farther"]
    assert sum(v[0] for v in strata.values()) == 12
    assert all(v[0] > 0 for v in strata.values())
    assert r["p_sign"] == pytest.approx(0.5 ** 12)


def test_run_orders_are_balanced():
    assert len(set(L.RUN_ORDERS)) == 6
    first = Counter(o.index(0) < o.index(1) for o in L.RUN_ORDERS)
    assert first[True] == first[False] == 3
    gaps = Counter((abs(o.index(1) - o.index(0)) > abs(o.index("rerun") - o.index(0)))
                   - (abs(o.index(1) - o.index(0)) < abs(o.index("rerun") - o.index(0)))
                   for o in L.RUN_ORDERS)
    assert gaps[1] == gaps[-1] == gaps[0] == 2
    used = Counter(L.run_order(L.SEED_BASE + 10000 * s + 100 * a + k)
                   for s in range(40) for a in range(5) for k in range(8))
    assert len(used) == 6 and min(used.values()) > 200


# -- the twin law, seeds and the engine boundary -----------------------------

def test_twin_law_accepts_feature_contrasts_and_rejects_the_others():
    for fam_text in ["(0,0)", "(1,0)", "(0,1)", "(1,1)", "(0,0,0)"]:
        fam = G.parse_family(fam_text)
        for a in range(20):
            anchor = L.CD.sample_target(400_000_000 + a * 100, fam)
            assert L.twin_law(anchor, G.contrast_target(anchor, "FEATURE",
                                                        rotation=a))[0]
            for other in ("PARTITION", "SELECT"):
                c = G.contrast_target(anchor, other, rotation=a)
                if c is not None:
                    assert not L.twin_law(anchor, c)[0], other


def test_seed_ranges_are_disjoint_from_every_stored_corpus():
    with open(MANIFEST) as handle:
        cap = json.load(handle)["caps"]["slot_cap"]
    top = L.SEED_BASE + cap * L.SLOT_STRIDE
    assert top < L.SMOKE_BASE
    stored = 0
    for path in glob.glob(os.path.join(HERE, "outputs", "tti", "v1[23]_*",
                                       "*.json")):
        with open(path) as handle:
            text = handle.read()
        for m in re.finditer(r'"(?:seed|generation_seed)": (\d+)', text):
            stored = max(stored, int(m.group(1)))
    assert stored > 0
    assert stored * 97 + 13 < L.SEED_BASE * 97


def test_the_engine_sees_only_demonstrations_under_an_opaque_label(monkeypatch):
    inputs = [np.array([[1, 0], [0, 1]]), np.array([[2, 2], [0, 0]]),
              np.array([[3, 0], [3, 0]])]
    outs = {0: [x + 1 for x in inputs], 1: [x * 2 for x in inputs]}
    calls = []

    def fake_demos(schema, seed):
        return list(zip(inputs, outs[schema]))

    def fake_eval(schema, **kw):
        return "ADMITTED", {
            "demonstrations": [{"input": a.tolist(), "output": b.tolist()}
                               for a, b in zip(inputs, outs[schema])],
            "target_digest": "%064x" % (schema + 1),
            "target_tokens": [["Key", "area"]], "structural_family": [0, 0],
            "schema_mdl": 11}, {}

    class Obs:
        candidates = []

    class Tfg:
        def to_json(self):
            return {"nodes": [], "edges": []}

    def fake_extract(*args, **kwargs):
        calls.append((args, kwargs))
        return {"solved": False, "tfg": Tfg(), "census": {}, "seconds": 0.1,
                "observer": Obs()}

    monkeypatch.setattr(L, "demonstrations_for", fake_demos)
    monkeypatch.setattr(L.CV, "family", lambda schema: (0, 0))
    monkeypatch.setattr(L.V2, "evaluate_target_v2", fake_eval)
    monkeypatch.setattr(L.ET, "extract", fake_extract)
    monkeypatch.setattr(L.G, "features_v12",
                        lambda tfg: {k: 0 for k in G.DEMO_FEATURES})
    monkeypatch.setattr(L.G, "informative", lambda f, g: True)
    monkeypatch.setattr(L.G, "raw_descriptor", lambda tfg: {})
    code, twin = L.make_twin_replicate(0, 1, 123456789, {
        "full_engine_observation_s": 8.0}, {}, ("full", 3, 4, 5), "/tmp/x")
    assert code == L.ADMITTED
    labels = [a[0] for a, _ in calls]
    assert len(labels) == 3 and len(set(labels)) == 3
    expected = ["A" if w == 0 else "B" if w == 1 else "rerun"
                for w in L.run_order(123456789)]
    assert twin[0]["self_rerun"]["order"] == expected
    assert labels == [L.opaque_label("full", 3, 4, 5, w)
                      for w in L.run_order(123456789)]
    assert "self_rerun" not in twin[1]
    for (label, pairs), kwargs in calls:
        assert re.fullmatch(r"v14-[0-9a-f]{16}", label)
        assert set(kwargs) == {"budget_s", "out_dir"}
        assert [p[0] for p in pairs] == [x.tolist() for x in inputs]
    assert twin[0]["seed"] == twin[1]["seed"] == 123456789


def test_twin_integrity_rejections(monkeypatch):
    inputs = [np.array([[1, 0], [0, 1]])] * 3
    monkeypatch.setattr(L, "demonstrations_for",
                        lambda s, seed: list(zip(inputs, inputs)))
    assert L.make_twin_replicate(0, 1, 5, {}, {}, (), "")[0] == L.R_TWIN_SAME
    monkeypatch.setattr(L, "demonstrations_for",
                        lambda s, seed: None if s else list(zip(inputs, inputs)))
    assert L.make_twin_replicate(0, 1, 5, {}, {}, (), "")[0] == L.R_TWIN_EXEC
    monkeypatch.setattr(L, "demonstrations_for",
                        lambda s, seed: list(zip([x + s for x in inputs], inputs)))
    assert L.make_twin_replicate(0, 1, 5, {}, {}, (), "")[0] == L.R_TWIN_INPUTS


def test_engine_state_guard(monkeypatch):
    for k in [k for k in os.environ if k.startswith("ARC_")]:
        monkeypatch.delenv(k)
    monkeypatch.setenv("ARC_META_BUDGET_S", "8")
    monkeypatch.setenv("PYTHONHASHSEED", "0")
    with tempfile.TemporaryDirectory() as d:
        assert L.engine_state_problems(d) == []
        monkeypatch.setenv("ARC_ANALOGY", "1")
        monkeypatch.setenv("ARC_OVERLAY", "0")
        open(os.path.join(d, "library.json"), "w").close()
        assert L.engine_state_problems(d) == [
            "env:ARC_ANALOGY", "env:ARC_OVERLAY", "file:library.json"]
        monkeypatch.delenv("ARC_ANALOGY")
        monkeypatch.delenv("ARC_OVERLAY")
        monkeypatch.setenv("ARC_META_BUDGET_S", "4")
        assert "env:ARC_META_BUDGET_S" in L.engine_state_problems(d)


def test_corpus_problems_catch_gaps_duplicates_and_environment():
    env, ver = dict(L.REQUIRED_ENV), {"python": "x"}
    def rec(slot, digest=None):
        return {"slot": slot, "admitted": digest is not None,
                "group": {"group_digest": digest} if digest else None,
                "environment": env, "runtime_versions": ver,
                "engine_state_problems": [], "freeze_ok": True}
    good = [rec(0, "a"), rec(1), rec(2, "b")]
    assert L.corpus_problems(good, 42, env, ver) == []
    assert "slots_not_contiguous" in L.corpus_problems(
        [rec(0), rec(2)], 42, env, ver)
    assert "duplicate_group_digest" in L.corpus_problems(
        [rec(0, "a"), rec(1, "a")], 42, env, ver)
    bad = rec(1)
    bad["environment"] = dict(env, ARC_GUIDE="1")
    bad["freeze_ok"] = False
    found = L.corpus_problems([rec(0), bad], 42, env, ver)
    assert "slot1:environment" in found and "slot1:freeze_not_reverified" in found


def test_integrity_and_leak_checks_catch_broken_groups():
    demo = [{"input": [[1]], "output": [[2]]}]
    other = [{"input": [[1]], "output": [[3]]}]
    eps = []
    for r in range(4):
        for t in (0, 1):
            ep = _view()
            ep.update(target_index=t, replicate_index=r, seed=100000000 + r,
                      target_digest=("a" if t == 0 else "b") * 64,
                      structural_family=[0, 0], schema_mdl=11,
                      demonstrations=demo if t == 0 else other)
            if t == 0:
                ep["self_rerun"] = dict(_view(), order=["A", "B", "rerun"])
            eps.append(ep)
    group = {"contrast_type": "FEATURE", "target_digests": ["a" * 64, "b" * 64],
             "group_digest": "c" * 64, "pair_seed": 100000000, "episodes": eps}
    assert L.integrity_problems(group) == []
    assert all(L.view_leaks(e, group) == [] for e in eps)
    eps[1]["demonstrations"] = demo
    assert "twin_outputs_identical_r0" in L.integrity_problems(group)
    eps[1]["demonstrations"] = [{"input": [[9]], "output": [[3]]}]
    assert "twin_inputs_r0" in L.integrity_problems(group)
    eps[1]["demonstrations"] = other
    eps[2]["trajectory"] = [[json.dumps(["x", ["a" * 12]]), "typed"]]
    assert L.view_leaks(eps[2], group) == ["digest"]
    eps[2]["trajectory"] = [[json.dumps(["x", [100000001]]), "typed"]]
    assert L.view_leaks(eps[2], group) == ["seed"]
    eps[2]["trajectory"] = []
    eps[0]["self_rerun"]["trajectory"] = [[json.dumps(["x", ["b" * 16]]), "typed"]]
    assert L.view_leaks(eps[0], group) == ["digest"]
    del eps[0]["self_rerun"]
    assert "self_rerun" in L.integrity_problems(group)


# -- noninterference on the real engine --------------------------------------

def test_engine_caches_are_cleared_before_each_run():
    import test_engine_trace_repair as TR
    from geocat_arc.object_reasoning import features as F
    cached = [v for v in vars(F).values() if hasattr(v, "cache_info")]
    assert len(cached) >= 2
    with tempfile.TemporaryDirectory() as engine_dir:
        L.ET.extract("fixture_recolour", TR.RECOLOUR, budget_s=8.0,
                     out_dir=engine_dir)
    assert sum(f.cache_info().currsize for f in cached) > 0
    assert L.clear_engine_caches() >= 2
    assert sum(f.cache_info().currsize for f in cached) == 0


def test_capture_is_the_observers_own_list_and_leaves_the_result_unchanged():
    import test_engine_trace_repair as TR
    with tempfile.TemporaryDirectory() as engine_dir:
        got = L.ET.extract("fixture_recolour", TR.RECOLOUR, budget_s=8.0,
                           out_dir=engine_dir)
    before = list(got["observer"].candidates)
    traj = L.serialize_trajectory(got["observer"])
    assert traj == [[L.ET.X._canonical_ast(a), o] for a, o in before]
    pairs = [(np.asarray(a), np.asarray(b)) for a, b in TR.RECOLOUR]
    first = L.evaluate_near_misses(got["observer"], pairs)
    assert L.evaluate_near_misses(got["observer"], pairs) == first
    assert list(got["observer"].candidates) == before
    plain = TR._solve_plain("fixture_recolour", TR.RECOLOUR)
    assert TR._result_fingerprint(plain) == \
        TR._result_fingerprint(got["result"])
