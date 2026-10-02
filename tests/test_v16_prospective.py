"""End-to-end tests of the v1.6 sealed evaluator on a synthetic development
resource and a synthetic prospective corpus built from genuine grammar pairs
at genuine v1.6 seeds, with synthetic candidate responses. Byte-identical
reproduction, the floor rule, a planted signal that P0 must detect, and a
null that it must not. Nothing here touches a real v1.6 record."""
from __future__ import annotations

import json
import os
import random
import sys
import tempfile

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tests"))

from cora_arc2026 import v14_loc as L                             # noqa: E402
from cora_arc2026 import v15_sel as S                             # noqa: E402
from cora_arc2026 import v16_cfr as C                             # noqa: E402
import test_v15_selection_feasibility as T                        # noqa: E402

G = S.G
TEST_BASE_V16 = 500_000_000


def _response(fits, exact, rng):
    err = round(1.0 - exact + (0.0 if exact == 1.0 else rng.random() * 0.1), 12)
    return {"fits_all": fits, "full_fit_failure": None if fits else "scoped_fit_failed",
            "response": {"loo_exact": exact if fits else 0.0,
                         "loo_fit_fail": 0.0 if fits else 1.0,
                         "loo_cell_error": min(1.0, err) if fits else 1.0,
                         "table_entries": rng.choice([0.4, 0.6, 0.8]) if fits else 0.0},
            "loo_class": "LOO_ALL" if exact == 1.0 else ("LOO_NONE" if exact == 0.0 else "LOO_PARTIAL"),
            "fold_codes": []}


def _corpus(monkeypatch, n_dev, n_test, name, p_truth, p_false, amb_share=0.6):
    """Returns the evaluator module and a report path. p_truth / p_false are
    the probabilities that the true / false candidate re-derives every
    held-out demonstration on ambiguous queries (the planted signal)."""
    EV = T._module(name, "scripts/evaluate_v16_cfr.py")
    rng = random.Random(7)
    ex_t, _ = S.load_exclusion(os.path.join(HERE, "outputs", "tti", "v16_exclusion_digests.json"))
    used = set()
    tmp = tempfile.mkdtemp()
    dev_dir, test_dir = os.path.join(tmp, "dev"), os.path.join(tmp, "test")
    os.makedirs(dev_dir)
    os.makedirs(test_dir)
    tix = {t: i for i, t in enumerate(T.TOKENS)}

    def build(pair, test_seeds):
        slot, attempt, fam, ps, anchor, contrast, da, db = pair
        toks = {0: [list(t) for t in S.CV.tokens_from_ast(anchor)],
                1: [list(t) for t in S.CV.tokens_from_ast(contrast)]}
        _, ca, cb = S.differing_step(toks[0], toks[1])
        eps, rows = [], []
        gd = G.group_digest(da, db)
        for t in (0, 1):
            for r in range(4):
                seed = S.episode_seeds(ps, t)[r] if test_seeds else ps + 10 * t + r
                amb = rng.random() < amb_share
                ep = T._synthetic_episode(t, r, toks[t], [da, db][t], seed, tix[[ca, cb][t]], rng, 0.0)
                ep["other_candidate_fits"] = amb
                eps.append(ep)
                truth = "anchor" if t == 0 else "contrast"
                other = "contrast" if t == 0 else "anchor"
                resp = {"s0": {"exact": 0, "fitted": 0, "fold_exact": [0], "class": "K_NO_CONSISTENT"},
                        truth: _response(True, 1.0 if rng.random() < p_truth else 0.0, rng),
                        other: _response(amb, (1.0 if rng.random() < p_false else 0.0) if amb else 0.0, rng)}
                rows.append({"group_digest": gd, "t": t, "r": r, "responses": resp})
        return ({"group_digest": gd, "contrast_type": "FEATURE", "anchor_family": fam,
                 "target_digests": [da, db], "pair_seed": ps, "episodes": eps}, rows)

    dev_rows, test_rows, dev_groups = [], [], []
    for i, pair in enumerate(T._synthetic_pairs(n_dev, ex_t, used, S.TEST_BASE, S.SLOT_STRIDE)):
        g = None
        if pair[1] is not None:
            g, rows = build(pair, True)
            dev_rows += rows
            dev_groups.append(g)
        json.dump({"slot": i, "admitted": g is not None, "group": g},
                  open(os.path.join(dev_dir, f"full{i:05d}.json"), "w"))
    for pair in T._synthetic_pairs(n_test, ex_t, used, TEST_BASE_V16, S.SLOT_STRIDE):
        slot = pair[0]
        g = None
        if pair[1] is not None:
            g, rows = build(pair, True)
            test_rows += rows
        rec = {"slot": slot, "admitted": g is not None, "group": g,
               "environment": dict(L.REQUIRED_ENV), "runtime_versions": L.runtime_versions(),
               "freeze_ok": True, "engine_state_problems": [], "manifest_sha256": "m",
               "started_since_first_start_s": 1.0}
        json.dump(rec, open(os.path.join(test_dir, f"full{slot:05d}.json"), "w"))
    fitter = "f" * 64
    for path, rows in ((os.path.join(tmp, "dev_resp.json"), dev_rows),
                       (os.path.join(tmp, "test_resp.json"), test_rows)):
        json.dump({"probe_identity": C.probe_identity(), "fitter_identity": fitter,
                   "state_restored_every_group": True, "rows": rows}, open(path, "w"))
    qdev = C.build_queries(sorted(dev_groups, key=lambda g: g["group_digest"]),
                           {(r["group_digest"], r["t"], r["r"]): r["responses"] for r in dev_rows})
    pk = {}
    for q in qdev:
        pk.setdefault(q["group"], q["pair_key"])
    training = sum(1 for i in pk if not C.heldout_pair(pk[i]))
    man = {"protocol_doc_sha256": "p",
           "caps": {"wall_clock_s": 1e9, "test_groups": n_test, "target_ambiguous_groups": 40,
                    "floor_ambiguous_groups": 12},
           "environment": {"required_snapshot": dict(L.REQUIRED_ENV)},
           "runtime_versions": L.runtime_versions(),
           "development_resource": {"groups": len(dev_groups)},
           "training_resource": {"groups": training, "hash_list": "x", "hash_list_sha256": "x",
                                 "responses_sha256": "x"},
           "probe_identity": C.probe_identity(), "fitter_identity": fitter,
           "P1_representation": "R0", "P0_keys": list(C.P0_KEYS),
           "statistics": {"alpha": 0.01, "delta_min": 0.05},
           "transfer_gate": {"min_unseen_groups": 3, "alpha_above_chance": 0.05}}
    man_path = os.path.join(tmp, "manifest.json")
    json.dump(man, open(man_path, "w"))
    monkeypatch.setattr(EV, "TRAIN_DIR", dev_dir)
    monkeypatch.setattr(EV, "TEST_DIR", test_dir)
    monkeypatch.setattr(EV, "MANIFEST", man_path)
    monkeypatch.setattr(EV, "TRAIN_RESP", os.path.join(tmp, "dev_resp.json"))
    monkeypatch.setattr(EV, "TEST_RESP", os.path.join(tmp, "test_resp.json"))
    monkeypatch.setattr(EV, "verify_freeze", lambda m: [])
    real_sha = EV.sha256
    monkeypatch.setattr(EV, "sha256", lambda p: "m" if p == man_path else real_sha(p))
    return EV, tmp


def _run(EV, tmp, monkeypatch, name):
    out = os.path.join(tmp, name)
    monkeypatch.setattr(sys, "argv", ["evaluate", out])
    EV.main()
    return json.load(open(out)), out


def test_planted_signal_is_detected_and_reproduced_byte_for_byte(monkeypatch):
    EV, tmp = _corpus(monkeypatch, 60, 110, "ev16sig", p_truth=0.95, p_false=0.15)
    r1, p1 = _run(EV, tmp, monkeypatch, "r1.json")
    r2, p2 = _run(EV, tmp, monkeypatch, "r2.json")
    assert open(p1, "rb").read() == open(p2, "rb").read()
    assert r1["freeze_problems"] == [] and r1["integrity_problems"] == [] and r1["leaks"] == []
    assert r1["fits_converged"] and r1["order_invariant"]
    g = r1["gates"]["P0"]
    assert g["A_above_chance"] and g["B_beats_demo"] and g["C_beats_shuffle"] and g["D_min_effect"]
    assert r1["verdict"] in ("PURE_CFR_SELECTION_GENERALIZES", "PURE_CFR_FAMILIAR_PAIRS_ONLY")
    #  identity destroyed inverts P0 exactly
    a, b = r1["arms"]["P0"]["accuracy_ambiguous"], r1["arms"]["P0_SWAPPED"]["accuracy_ambiguous"]
    assert abs((a + b) - 1.0) < 1e-9


def test_null_signal_does_not_pass(monkeypatch):
    EV, tmp = _corpus(monkeypatch, 60, 110, "ev16null", p_truth=0.5, p_false=0.5)
    r, _ = _run(EV, tmp, monkeypatch, "r.json")
    assert not r["gates"]["P0"]["primary_pass"]
    assert r["verdict"] not in ("PURE_CFR_SELECTION_GENERALIZES", "HYBRID_CFR_SELECTION_GENERALIZES")


def test_floor_rule_computes_no_statistic(monkeypatch):
    EV, tmp = _corpus(monkeypatch, 60, 8, "ev16floor", p_truth=0.95, p_false=0.15)
    r, _ = _run(EV, tmp, monkeypatch, "r.json")
    assert r["verdict"] == "MIXED_OR_INCONCLUSIVE" and "gates" not in r


def test_missing_test_responses_block_the_audit(monkeypatch):
    EV, tmp = _corpus(monkeypatch, 60, 40, "ev16miss", p_truth=0.9, p_false=0.2)
    os.remove(os.path.join(tmp, "test_resp.json"))
    r, _ = _run(EV, tmp, monkeypatch, "r.json")
    assert r["verdict"] == "AUDIT_BLOCKED" and "test_responses_missing" in r["integrity_problems"]


def test_integrity_only_exits_nonzero_on_a_tampered_record(monkeypatch):
    EV, tmp = _corpus(monkeypatch, 60, 40, "ev16tamper", p_truth=0.9, p_false=0.2)
    path = os.path.join(EV.TEST_DIR, "full00000.json")
    rec = json.load(open(path))
    rec["freeze_ok"] = False
    json.dump(rec, open(path, "w"))
    monkeypatch.setattr(EV, "INTEGRITY_ONLY", True)
    monkeypatch.setattr(sys, "argv", ["evaluate", "--integrity-only"])
    with pytest.raises(SystemExit) as exc:
        EV.main()
    assert exc.value.code == 1


def _gate(full=False, primary=False, abc=False, bdec=False, cdec=False, d=False):
    return {"full_pass": full, "primary_pass": primary, "A_above_chance": abc, "B_beats_demo": abc,
            "C_beats_shuffle": abc, "D_min_effect": d, "B_fails_decisively": bdec,
            "C_fails_decisively": cdec}


def test_classification_ladder_order_and_names():
    EV = T._module("ev16ladder", "scripts/evaluate_v16_cfr.py")
    man = {"caps": {"floor_ambiguous_groups": 10, "target_ambiguous_groups": 100}}
    none = {a: _gate() for a in EV.GATED_ARMS}
    assert EV.classify(none, 200, man, True, True)[0] == "MIXED_OR_INCONCLUSIVE"
    assert EV.classify(none, 5, man, False, True)[0] == "MIXED_OR_INCONCLUSIVE"
    g = dict(none, P0_then_D=_gate(full=True, primary=True, abc=True, d=True))
    assert EV.classify(g, 200, man, False, True)[0] == "PURE_RULE_WITH_DEMONSTRATION_FALLBACK_GENERALIZES"
    g = dict(none, P0=_gate(full=True, primary=True, abc=True, d=True),
             P1=_gate(full=True, primary=True, abc=True, d=True))
    assert EV.classify(g, 200, man, False, True)[0] == "PURE_CFR_SELECTION_GENERALIZES"
    g = dict(none, P1=_gate(primary=True, abc=True, d=True))
    assert EV.classify(g, 200, man, False, True)[0] == "HYBRID_CFR_FAMILIAR_PAIRS_ONLY"
    g = dict(none, P0_then_D=_gate(abc=True))
    assert EV.classify(g, 200, man, False, True)[0] == "CFR_INCREMENT_SIGNIFICANT_BELOW_FLOOR"
    assert EV.classify(none, 50, man, False, True)[0] == "MIXED_OR_INCONCLUSIVE"
    g = {a: _gate(cdec=True) for a in EV.GATED_ARMS}
    assert EV.classify(g, 200, man, False, True)[0] == "CANDIDATE_RESPONSE_NOT_EPISODE_SPECIFIC"
    g = {a: _gate(bdec=True) for a in EV.GATED_ARMS}
    assert EV.classify(g, 200, man, False, True)[0] == "CANDIDATE_INTERVENTION_NO_INCREMENT_OVER_DEMONSTRATIONS"
    g = dict(none, P0=_gate(bdec=True))
    assert EV.classify(g, 200, man, False, True)[0] == "MIXED_OR_INCONCLUSIVE"
