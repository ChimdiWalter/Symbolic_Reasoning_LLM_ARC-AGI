"""Item-2 v1.9 prospective engine-stability test: tests of the frozen script
(outcome ladder, safety gate, refusals) on synthetic rows. No engine run."""
from __future__ import annotations

import os
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "scripts"))

import v19_prospective as PR                                      # noqa: E402


def _row(i, fc=True, sf=False, bl=False, wn=True, wo=False, ln=True, lo=False, **safe):
    run = {"accepted": True, "heldout_exact": True, "program_sha": f"p{i}", "events": ["x"],
           "uses": True, "replays_training": True, "direct_equals_engine": True}
    run.update({k: v for k, v in safe.items() if k in run})
    row = {"i": i, "seed": 880_000_000 + 100 * i, "family": "(1,1)", "digest": f"d{i}",
           "arms": {"FAILURE_CONDITIONED": {"class": "SELECTED", "useful": fc, "selection": {"level": "MDL"}},
                    "SHUFFLED_FRONTIER": {"class": "SELECTED", "useful": sf, "selection": None},
                    "BLIND": {"class": "SELECTED", "useful": bl, "selection": None}},
           "old": {"uses": True, "verdict": "x",
                   "with": {"accepted": safe.get("old_accepted", True), "heldout_exact": True,
                            "events": [], "seconds": 1, "program_sha": f"p{i}"},
                   "without": {"accepted": False, "heldout_exact": False, "events": ["b"], "seconds": 1,
                               "program_sha": None}},
           "new_with": run, "new_alone": {"accepted": False, "events": ["b"], "program_sha": None},
           "baseline_3x": {"accepted": False, "heldout_exact": False},
           "loo_new": {"passed": ln, "folds": [{"class": "SUCCESS" if ln else "LOO_FAILURE"}] * 7},
           "loo_old": {"passed": lo, "folds": [{"class": "SUCCESS" if lo else "LOO_FAILURE"}] * 7},
           "restored": safe.get("restored", True), "wrong": safe.get("wrong"),
           "witness_new": {"complete": wn}, "witness_old": {"complete": wo}}
    return row


@pytest.fixture
def thresholds(monkeypatch):
    monkeypatch.setattr(PR, "N_TASKS", 30)
    monkeypatch.setattr(PR, "W_MIN", 18)
    monkeypatch.setattr(PR, "DELTA_MIN", 6)


def test_accepted_when_every_gate_passes(thresholds):
    rows = [_row(i) for i in range(30)]
    out, gates = PR.outcome(rows, [], 30, 0)
    assert out == "ENGINE_STABILITY_REPAIR_ACCEPTED"
    assert gates["G3_loo_stability"]["new_only"] == 30 and gates["G4_safety"]["pass"]


def test_leakage_overrides_and_run_error_and_shortfall(thresholds):
    rows = [_row(i) for i in range(30)]
    assert PR.outcome(rows, [], 30, 1)[0] == "PROPOSER_LEAKAGE"
    assert PR.outcome(rows, [{"stage": "x"}], 30, 0)[0] == "NO_VERDICT_RUN_ERROR"
    assert PR.outcome(rows, [], 29, 0)[0] == "NO_VERDICT_FIXTURE_SHORTFALL"


def test_unsafe_overrides_acceptance(thresholds):
    rows = [_row(i) for i in range(30)]
    rows[3]["new_with"]["replays_training"] = False
    assert PR.outcome(rows, [], 30, 0)[0] == "REPAIR_UNSAFE"
    rows = [_row(i) for i in range(30)]
    rows[4]["new_alone"]["accepted"] = True                     # not inert
    assert PR.outcome(rows, [], 30, 0)[0] == "REPAIR_UNSAFE"
    rows = [_row(i) for i in range(30)]
    rows[5]["wrong"] = {"old": {"accepted": False, "heldout_exact": False},
                        "new": {"accepted": True, "heldout_exact": False}}
    assert PR.outcome(rows, [], 30, 0)[0] == "REPAIR_UNSAFE"     # a false acceptance the old logic avoided
    rows = [_row(i, lo=True) for i in range(30)]
    rows[6]["loo_new"] = {"passed": False, "folds": [{"class": "LOO_FAILURE"}] + [{"class": "SUCCESS"}] * 6}
    assert PR.outcome(rows, [], 30, 0)[0] == "REPAIR_UNSAFE"     # an old SUCCESS fold regressed


def test_ladder_without_g1_g2_or_g3(thresholds):
    rows = [_row(i, sf=True, bl=True) for i in range(30)]          # no failure specificity
    assert PR.outcome(rows, [], 30, 0)[0] == "FAILURE_SPECIFICITY_LOST"
    rows = [_row(i, wn=i < 10) for i in range(30)]                 # 10 < 18 witnesses
    assert PR.outcome(rows, [], 30, 0)[0] == "REPAIR_STABILIZES_BELOW_WITNESS_THRESHOLD"
    rows = [_row(i, ln=i < 5, lo=False) for i in range(30)]        # only 5 new-only passes < 6
    assert PR.outcome(rows, [], 30, 0)[0] == "REPAIR_NOT_MATERIAL"


def test_g3_needs_both_delta_and_significance(thresholds):
    rows = [_row(i, ln=True, lo=i < 22) for i in range(30)]        # 8 new-only, 0 old-only
    g = PR.outcome(rows, [], 30, 0)[1]["G3_loo_stability"]
    assert g["new_only"] == 8 and g["old_only"] == 0 and g["pass"]
    rows = [_row(i, ln=i >= 2, lo=i < 25 and i >= 2 or i < 2) for i in range(30)]
    g = PR.outcome(rows, [], 30, 0)[1]["G3_loo_stability"]
    assert g["new_only"] - g["old_only"] < 6 and not g["pass"]


def test_sign_test_values():
    assert PR.binom_upper_p(0, 0) == 1.0
    assert PR.binom_upper_p(13, 0) == 2 ** -13
    assert abs(PR.binom_upper_p(7, 1) - 9 / 256) < 1e-15


def test_refuses_while_thresholds_unset_or_unfrozen():
    if PR.N_TASKS is None:
        problems, _ = PR.freeze_problems()
        assert problems
