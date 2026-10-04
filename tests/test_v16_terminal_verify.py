"""The v1.6 terminal verifier on a synthetic corpus: it must agree with the
sealed evaluator on every recomputed value, and catch a tampered report.
Synthetic data only; nothing here touches a real v1.6 record."""
from __future__ import annotations

import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tests"))

import test_v15_selection_feasibility as T                        # noqa: E402
import test_v16_prospective as P                                  # noqa: E402

V = T._module("v16term", "scripts/v16_terminal_verify.py")


def _setup(monkeypatch, tmp_name, p_truth, p_false):
    EV, tmp = P._corpus(monkeypatch, 60, 110, tmp_name, p_truth=p_truth, p_false=p_false)
    rep, path = P._run(EV, tmp, monkeypatch, "rep.json")
    reports = [os.path.join(tmp, f"r{i}.json") for i in range(3)]
    for r in reports:
        shutil.copy(path, r)
    cfg = dict(V.default_cfg(), manifest=EV.MANIFEST, dev_dir=EV.TRAIN_DIR, test_dir=EV.TEST_DIR,
               dev_resp=EV.TRAIN_RESP, test_resp=EV.TEST_RESP, reports=reports,
               out=os.path.join(tmp, "ver.json"), csv=os.path.join(tmp, "t.csv"),
               figure=os.path.join(tmp, "f.json"), marker_dir=tmp, skip_freeze=True)
    return cfg, tmp, rep


def test_verifier_agrees_with_the_evaluator_on_a_planted_signal(monkeypatch):
    cfg, tmp, rep = _setup(monkeypatch, "ev16term1", 0.95, 0.15)
    assert V.main(cfg) == 0
    out = json.load(open(cfg["out"]))
    assert out["all_checks_pass"], [c for c in out["checks"] if not c["ok"]]
    assert out["classification_recomputed"] == rep["classification"]["classification"]
    assert os.path.exists(os.path.join(tmp, "V16_TERMINAL_VERIFIED"))
    assert os.path.exists(cfg["csv"]) and os.path.exists(cfg["figure"])


def test_verifier_agrees_on_a_null(monkeypatch):
    cfg, tmp, rep = _setup(monkeypatch, "ev16term2", 0.5, 0.5)
    assert V.main(cfg) == 0
    out = json.load(open(cfg["out"]))
    assert out["classification_recomputed"] == rep["classification"]["classification"]


def test_verifier_catches_a_tampered_report(monkeypatch):
    cfg, tmp, rep = _setup(monkeypatch, "ev16term3", 0.95, 0.15)
    bad = json.load(open(cfg["reports"][0]))
    bad["gates"]["P0"]["D_min_effect"] = not bad["gates"]["P0"]["D_min_effect"]
    for r in cfg["reports"]:
        json.dump(bad, open(r, "w"))
    assert V.main(cfg) == 1
    assert os.path.exists(os.path.join(tmp, "V16_TERMINAL_DISCREPANCY"))


def test_verifier_catches_differing_passes(monkeypatch):
    cfg, tmp, rep = _setup(monkeypatch, "ev16term4", 0.95, 0.15)
    with open(cfg["reports"][2], "a") as handle:
        handle.write(" ")
    assert V.main(cfg) == 1
    out = json.load(open(cfg["out"]))
    assert not [c for c in out["checks"] if c["check"] == "reports_byte_identical"][0]["ok"]
