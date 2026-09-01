"""Tests for the hash-chained ablation ledger and the §XII conjunction."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cora_tti.ablation_ledger import (AblationLedger, CONJUNCTION,   # noqa: E402
                                      causal_decomposition, tti_dependent)


def full_evidence(**overrides):
    row = {k: True for k in CONJUNCTION}
    row.update(overrides)
    return row


def test_conjunction_requires_every_leg():
    assert tti_dependent(full_evidence())
    for leg in CONJUNCTION:
        assert not tti_dependent(full_evidence(**{leg: False})), leg
    assert not tti_dependent({})                      # missing keys are False


def test_ablation_survivor_gets_no_credit():
    """A solve that persists after removing the production is search's, not
    invention's — the single most important negative rule of §XII."""
    assert not tti_dependent(full_evidence(ablation_fails=False))


def test_ledger_appends_and_verifies(tmp_path):
    ledger = AblationLedger(tmp_path / "ledger.jsonl")
    ledger.record_note("run started")
    ledger.record_evaluation("cfg-abc", "dev",
                             {"base": 0.05, "tti": 0.09, "final": 0.11})
    ledger.record_tti_ablation("o-17", "Set[Region]->Grid#e42", full_evidence())
    report = ledger.verify()
    assert report["ok"] and report["entries"] == 3
    rows = ledger.entries("tti_ablation")
    assert rows[0]["payload"]["tti_dependent"] is True


def test_tampering_is_detected(tmp_path):
    path = tmp_path / "ledger.jsonl"
    ledger = AblationLedger(path)
    ledger.record_note("a")
    ledger.record_evaluation("cfg", "dev", {"base": 0.1, "final": 0.2})
    ledger.record_note("b")
    lines = path.read_text().splitlines()
    #  edit a middle entry in place (inflate the final score)
    doctored = json.loads(lines[1])
    doctored["payload"]["scores"]["final"] = 0.9
    lines[1] = json.dumps(doctored, sort_keys=True)
    path.write_text("\n".join(lines) + "\n")
    report = ledger.verify()
    assert not report["ok"] and report["break_at"] == 1
    assert report["reason"] == "content"


def test_reordering_and_deletion_break_the_chain(tmp_path):
    path = tmp_path / "ledger.jsonl"
    ledger = AblationLedger(path)
    for i in range(3):
        ledger.record_note(f"n{i}")
    lines = path.read_text().splitlines()
    path.write_text("\n".join([lines[0], lines[2]]) + "\n")   # delete middle
    assert not ledger.verify()["ok"]
    path.write_text("\n".join([lines[1], lines[0], lines[2]]) + "\n")
    assert not ledger.verify()["ok"]


def test_holdout_gate_validation(tmp_path):
    ledger = AblationLedger(tmp_path / "ledger.jsonl")
    with pytest.raises(ValueError):
        ledger.record_holdout_gate("dev-peek", 0.5, "x" * 64)
    ledger.record_holdout_gate("C3", 0.12, "x" * 64)
    assert ledger.verify()["ok"]


def test_evaluation_rejects_unknown_stages(tmp_path):
    ledger = AblationLedger(tmp_path / "ledger.jsonl")
    with pytest.raises(ValueError):
        ledger.record_evaluation("cfg", "dev", {"vibes": 0.9})


def test_causal_decomposition_reports_deltas_without_fabrication(tmp_path):
    ledger = AblationLedger(tmp_path / "ledger.jsonl")
    ledger.record_evaluation("cfg-1", "dev", {"base": 0.05, "gpn": 0.08,
                                              "final": 0.12})
    ledger.record_evaluation("cfg-2", "dev", {"base": 0.06, "gpn": 0.09,
                                              "tti": 0.13, "final": 0.14})
    out = causal_decomposition(ledger.entries())
    dev = out["dev"]
    assert dev["config_fingerprint"] == "cfg-2"        # latest wins
    assert "global" not in dev["scores"]               # missing stays missing
    assert dev["deltas"] == {"base->gpn": 0.03, "gpn->tti": 0.04,
                             "tti->final": 0.01}
