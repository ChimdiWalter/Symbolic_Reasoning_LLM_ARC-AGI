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
           "loo_new": {"passed": ln, "folds": [{"class": "SUCCESS" if ln else "LOO_FAILURE",
                                                "accepted": ln, "heldout_exact": ln}] * 7},
           "loo_old": {"passed": lo, "folds": [{"class": "SUCCESS" if lo else "LOO_FAILURE",
                                                "accepted": lo, "heldout_exact": lo}] * 7},
           "restored": safe.get("restored", True), "wrong_trials": safe.get("wrong_trials", []),
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
    rows = [_row(i, lo=True) for i in range(30)]
    for i in range(14):                                          # 14 wrong certified folds: precision collapses
        rows[i]["loo_new"]["folds"] = [{"class": "LOO_FAILURE", "accepted": True, "heldout_exact": False}] + \
            [{"class": "SUCCESS", "accepted": True, "heldout_exact": True}] * 6
    out, gates = PR.outcome(rows, [], 30, 0)
    assert out == "REPAIR_UNSAFE" and not gates["G4_safety"]["checks"]["precision_floor"]
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


def test_one_extra_wrong_fold_is_reported_but_does_not_gate(thresholds):
    rows = [_row(i) for i in range(30)]
    rows[7]["loo_new"]["folds"] = [{"class": "LOO_FAILURE", "accepted": True, "heldout_exact": False}] + \
        [{"class": "SUCCESS", "accepted": True, "heldout_exact": True}] * 6
    rows[7]["loo_new"]["passed"] = False
    out, gates = PR.outcome(rows, [], 30, 0)
    p = gates["G4_safety"]["precision"]
    assert p["new"]["wrong_folds"] == 1 and p["new"]["certified"] == 30 + 210
    assert gates["G4_safety"]["pass"] and out == "ENGINE_STABILITY_REPAIR_ACCEPTED"


def test_precision_noninferiority_margin(thresholds):
    rows = [_row(i, lo=True) for i in range(30)]               # old: 240 certified, all correct
    for i in range(6):                                          # new: 6 wrong of 240 -> 0.975 < 1.0 - 0.02
        rows[i]["loo_new"]["folds"] = [{"class": "LOO_FAILURE", "accepted": True, "heldout_exact": False}] + \
            [{"class": "SUCCESS", "accepted": True, "heldout_exact": True}] * 6
    g = PR.outcome(rows, [], 30, 0)[1]["G4_safety"]
    assert not g["checks"]["precision_noninferior"] and g["checks"]["precision_floor"] is False or \
        not g["checks"]["precision_noninferior"]


def test_wilson_lower_bound():
    assert PR.wilson_lower(0, 0) == 0.0
    assert 0.96 < PR.wilson_lower(236, 238) < 0.99
    assert PR.wilson_lower(100, 100) > 0.96


def test_reduced_control_is_reported_not_gated(thresholds):
    rows = [_row(i) for i in range(30)]
    for r in rows:
        r["reduced"] = {"trials": [{"kind": "WRONG", "old": {"accepted": False, "right_on_E": None},
                                    "new": {"accepted": True, "right_on_E": False}}]}
    out, _ = PR.outcome(rows, [], 30, 0)
    assert out == "ENGINE_STABILITY_REPAIR_ACCEPTED"
    s = PR.reduced_summary(rows)
    assert s["new"]["false_accept"] == 30 and s["old"]["false_accept"] == 0


def test_low_volume_perfect_precision_is_not_unsafe(thresholds):
    rows = [_row(i, ln=i < 5, lo=False) for i in range(30)]     # 65 certified, all correct
    out, g = PR.outcome(rows, [], 30, 0)
    assert g["G4_safety"]["checks"]["precision_floor"] and out == "REPAIR_NOT_MATERIAL"



# erratum 01
def test_marginal_precision_gate(thresholds):
    rows = [_row(i, lo=True) for i in range(30)]               # old: everything certified and correct
    for r in rows:
        r["loo_old"]["folds"] = [{"class": "LOO_FAILURE", "accepted": False, "heldout_exact": False}] * 7
        r["loo_old"]["passed"] = False
    for i in range(4):                                          # 4 added wrong vs 210 added correct - 4
        rows[i]["loo_new"]["folds"] = [{"class": "LOO_FAILURE", "accepted": True, "heldout_exact": False}] + \
            [{"class": "SUCCESS", "accepted": True, "heldout_exact": True}] * 6
    g = PR.outcome(rows, [], 30, 0)[1]["G4_safety"]
    assert g["precision"]["added_wrong"] == 4 and g["checks"]["marginal_precision"]   # 4 <= 0.05 x 206
    for i in range(4, 12):                                      # 12 added wrong vs 198 added correct
        rows[i]["loo_new"]["folds"] = [{"class": "LOO_FAILURE", "accepted": True, "heldout_exact": False}] + \
            [{"class": "SUCCESS", "accepted": True, "heldout_exact": True}] * 6
    g = PR.outcome(rows, [], 30, 0)[1]["G4_safety"]
    assert not g["checks"]["marginal_precision"]                # 12 > 0.05 x 198


def test_correct_switch_from_a_native_winner_is_not_a_regression(thresholds):
    rows = [_row(i) for i in range(30)]
    rows[0]["old"]["uses"] = False                              # K*'s winner was native
    rows[0]["new_with"]["program_sha"] = "different"            # K*' picks e, still exact
    g = PR.outcome(rows, [], 30, 0)[1]["G4_safety"]
    assert g["checks"]["no_regression_full"]
    rows[0]["old"]["uses"] = True                               # same switch when K* used e: a regression
    assert not PR.outcome(rows, [], 30, 0)[1]["G4_safety"]["checks"]["no_regression_full"]


def test_pairing_mismatches_counted(thresholds):
    rows = [_row(i) for i in range(30)]
    rows[2]["loo_new"]["folds"] = [dict(f, selected="other") for f in rows[2]["loo_new"]["folds"]]
    assert PR.outcome(rows, [], 30, 0)[1]["G3_loo_stability"]["pairing_mismatches"] == 7


def test_read_rows_tolerates_a_truncated_line(tmp_path, monkeypatch):
    monkeypatch.setattr(PR, "ROWS", str(tmp_path / "rows.jsonl"))
    with open(PR.ROWS, "w") as fh:
        fh.write('{"i": 0}\n{"i": 1}\n{"i": 2, "arms": {"FAILU')
    rows, bad = PR.read_rows(report_unparsable=True)
    assert [r["i"] for r in rows] == [0, 1] and bad == 1


def test_claims_written_atomically(tmp_path, monkeypatch):
    monkeypatch.setattr(PR, "CLAIMS", str(tmp_path / "claims.json"))
    monkeypatch.setattr(PR, "LOCK", str(tmp_path / "lock"))
    assert [PR.claim(3) for _ in range(4)] == [0, 1, 2, None]
    assert not os.path.exists(PR.CLAIMS + ".tmp")


def test_wrong_extension_failure_is_recorded_not_raised(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("proposer limit")
    monkeypatch.setattr(PR.P, "Semantics", boom)
    out, failure = PR.wrong_extensions([], None, "cx", {})
    assert out == [] and failure == "RuntimeError"


def test_pid_alive():
    assert PR.pid_alive(os.getpid()) and not PR.pid_alive(None)
