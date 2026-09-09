"""Tests for the Capability-Growth Gate's access guard.

These check the property the gate depends on: that the protocol's read order is
enforced by the code and not by whoever is running it. The interesting cases are
the refusals, so most of these assert that something is impossible.
"""
from __future__ import annotations

import hashlib
import json

import pytest

from cora_tti import gate_guard as G
from cora_tti.gate_guard import (GateGuard, MissingPinError, SealedAccessError,
                                 SealedClass, Stage, classify)


@pytest.fixture
def tree(tmp_path, monkeypatch):
    """A fake experiment tree plus a valid freeze pin."""
    breakthrough = tmp_path / "outputs" / "cora_breakthrough"
    lanes = breakthrough / "level4_stepB_gate_outputs"
    logs = tmp_path / "logs"
    for directory in (lanes, logs):
        directory.mkdir(parents=True, exist_ok=True)

    paths = {
        "journal": breakthrough / "level4_stepB_journal.jsonl",
        "witnesses": breakthrough / "level4_stepB_witnesses.json",
        "inventory": breakthrough / "level4_stepB_inventory.json",
        "lane": lanes / "deta_selection.json",
        "manifest": breakthrough / "level4_stepB_run_manifest.json",
        "log": logs / "level4_stepB_run.log",
        "unknown": breakthrough / "level4_stepB_some_new_artifact.json",
        "transfer": breakthrough / "transfer_witnesses.jsonl",
        "lockbox": tmp_path / "outputs" / "lockbox" / "manifest.json",
        "evalsplit": tmp_path / "outputs" / "eval_split_v1.json",
    }
    paths["lockbox"].parent.mkdir(parents=True, exist_ok=True)
    for path in paths.values():
        path.write_text("{}")

    gate = tmp_path / "gate"
    gate.mkdir()
    monkeypatch.setattr(G, "MAIN", tmp_path)
    monkeypatch.setattr(G, "GATE_DIR", gate)
    monkeypatch.setattr(G, "FREEZE_PIN", gate / "stepB_freeze_pin.json")
    return {"paths": paths, "gate": gate}


def write_pin(tree, valid: bool = True):
    text = json.dumps({"pin_version": "stepB_capability_gate_pin:v1"})
    G.FREEZE_PIN.write_text(text)
    digest = hashlib.sha256(text.encode()).hexdigest()
    (tree["gate"] / "stepB_freeze_pin_hash.txt").write_text(
        (digest if valid else "0" * 64) + "\n")


#  --------------------------------------------------------------- classify

def test_step_b_semantics_are_sealed(tree):
    for key in ("journal", "witnesses", "inventory", "lane"):
        assert classify(tree["paths"][key]) is SealedClass.STEP_B_SEMANTICS


def test_manifest_and_log_are_quantitative_and_open(tree):
    assert classify(tree["paths"]["manifest"]) is None
    assert classify(tree["paths"]["log"]) is None


def test_transfer_and_lockbox_have_their_own_classes(tree):
    assert classify(tree["paths"]["transfer"]) is SealedClass.E_TRANSFER
    assert classify(tree["paths"]["lockbox"]) is SealedClass.LOCKBOX
    assert classify(tree["paths"]["evalsplit"]) is SealedClass.LOCKBOX


def test_unknown_artifact_under_a_watched_root_fails_closed(tree):
    assert classify(tree["paths"]["unknown"]) is SealedClass.STEP_B_SEMANTICS


def test_paths_outside_watched_roots_are_not_governed(tmp_path, tree):
    assert classify(tmp_path / "docs" / "notes.md") is None
    assert classify(tmp_path / "scripts" / "run_thing.py") is None


def test_an_ancestor_directory_name_cannot_decide_the_class(tmp_path, tree,
                                                           monkeypatch):
    """A parent directory called "lockbox_scratch" must not seal a log file."""
    root = tmp_path / "lockbox_scratch" / "e_transfer_notes"
    monkeypatch.setattr(G, "MAIN", root)
    (root / "logs").mkdir(parents=True)
    log = root / "logs" / "level4_stepB_run.log"
    log.write_text("")
    assert classify(log) is None


#  ------------------------------------------------------------ stage order

def test_pinning_stages_cannot_read_step_b_semantics(tree):
    for stage in (Stage.PIN_OUTPUT_HASH, Stage.PIN_PROTOCOL_HASHES):
        guard = GateGuard(stage, require_pin=False)
        with pytest.raises(SealedAccessError):
            guard.check(tree["paths"]["journal"])


def test_inspection_stage_unlocks_step_b_but_nothing_else(tree):
    write_pin(tree)
    guard = GateGuard(Stage.INSPECT_RETAINED_PRODUCTIONS)
    guard.check(tree["paths"]["journal"])
    for key in ("transfer", "lockbox"):
        with pytest.raises(SealedAccessError):
            guard.check(tree["paths"][key])


def test_e_transfer_unlocks_only_at_stage_seven(tree):
    write_pin(tree)
    early = GateGuard(Stage.CAPABILITY_GROWTH_WITNESS)
    with pytest.raises(SealedAccessError):
        early.check(tree["paths"]["transfer"])
    guard = GateGuard(Stage.E_TRANSFER_EVALUATION)
    guard.check(tree["paths"]["transfer"])
    with pytest.raises(SealedAccessError):
        guard.check(tree["paths"]["lockbox"])


def test_lockbox_stays_closed_through_every_stage_inside_the_gate(tree):
    write_pin(tree)
    for stage in Stage:
        if stage is Stage.GATE_COMPLETE:
            continue
        guard = GateGuard(stage, require_pin=stage > Stage.PIN_PROTOCOL_HASHES)
        with pytest.raises(SealedAccessError):
            guard.check(tree["paths"]["lockbox"])


def test_lockbox_opens_only_once_the_gate_is_complete(tree):
    write_pin(tree)
    GateGuard(Stage.GATE_COMPLETE).check(tree["paths"]["lockbox"])


#  -------------------------------------------------------------- pin gating

def test_stages_past_two_require_a_pin(tree):
    with pytest.raises(MissingPinError):
        GateGuard(Stage.INSPECT_RETAINED_PRODUCTIONS)


def test_a_tampered_pin_blocks_every_later_stage(tree):
    write_pin(tree, valid=False)
    with pytest.raises(MissingPinError):
        GateGuard(Stage.INSPECT_RETAINED_PRODUCTIONS)


def test_pinning_stages_run_without_a_pin(tree):
    GateGuard(Stage.PIN_OUTPUT_HASH)
    GateGuard(Stage.PIN_PROTOCOL_HASHES)


#  ------------------------------------------------------------------ writes

def test_the_gate_never_writes_into_the_experiment_tree(tree):
    write_pin(tree)
    guard = GateGuard(Stage.INSPECT_RETAINED_PRODUCTIONS)
    for mode in ("w", "a", "x", "r+"):
        with pytest.raises(SealedAccessError):
            with guard.open(tree["paths"]["journal"], mode):
                pass


def test_permitted_reads_work_through_the_context_manager(tree):
    write_pin(tree)
    guard = GateGuard(Stage.INSPECT_RETAINED_PRODUCTIONS)
    with guard.open(tree["paths"]["journal"]) as handle:
        assert handle.read() == "{}"


#  ------------------------------------------------------------------ ledger

def test_every_decision_is_recorded_including_refusals(tree):
    write_pin(tree)
    guard = GateGuard(Stage.INSPECT_RETAINED_PRODUCTIONS)
    guard.permits(tree["paths"]["journal"])
    guard.permits(tree["paths"]["lockbox"])
    assert len(guard.ledger) == 2
    path = guard.write_ledger()
    records = [json.loads(line) for line in path.read_text().splitlines()]
    assert [r["permitted"] for r in records] == [True, False]
    assert records[1]["sealed_class"] == "LOCKBOX"
    assert guard.ledger == [], "the ledger flushes so records are never doubled"


def test_ledger_is_append_only(tree):
    write_pin(tree)
    guard = GateGuard(Stage.INSPECT_RETAINED_PRODUCTIONS)
    guard.permits(tree["paths"]["journal"])
    path = guard.write_ledger()
    guard.permits(tree["paths"]["witnesses"])
    guard.write_ledger()
    assert len(path.read_text().splitlines()) == 2


def test_the_runner_and_candidate_inventory_are_sealed_until_inspection(tree,
                                                                       monkeypatch,
                                                                       tmp_path):
    """The standing rule forbids reading the runner while the run is live."""
    write_pin(tree)
    (tmp_path / "scripts").mkdir(exist_ok=True)
    (tmp_path / "level4_stepB").mkdir(exist_ok=True)
    runner = tmp_path / "scripts" / "cora_level4_stepB_run.py"
    inventory = tmp_path / "level4_stepB" / "candidates.py"
    for path in (runner, inventory):
        path.write_text("")
        assert classify(path) is SealedClass.STEP_B_SEMANTICS
    with pytest.raises(SealedAccessError):
        GateGuard(Stage.PIN_OUTPUT_HASH, require_pin=False).check(runner)
    GateGuard(Stage.INSPECT_RETAINED_PRODUCTIONS).check(runner)
