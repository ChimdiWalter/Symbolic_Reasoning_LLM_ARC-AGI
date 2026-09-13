"""Tests for the Capability-Growth Gate's access guard.

They check the two properties the gate depends on. The read order is enforced
by code rather than by whoever runs it, and every stage after pinning is looking
at exactly the pinned bytes. Most tests assert that something is impossible.
All run on synthetic fixture trees; none touches the live experiment.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from cora_tti import freeze_pin as FP
from cora_tti.gate_guard import (GateGuard, PinProvenanceError, SealedAccessError,
                                 SealedClass, Stage, classify)


@pytest.fixture
def tree(tmp_path, monkeypatch):
    main, tti, proc = tmp_path / "main", tmp_path / "tti", tmp_path / "proc"
    b = main / "outputs" / "cora_breakthrough"
    p = {
        "journal": b / "level4_stepB_journal.jsonl",
        "witnesses": b / "level4_stepB_witnesses.json",
        "inventory": b / "level4_stepB_inventory.json",
        "lane": b / "level4_stepB_gate_outputs" / "deta_selection.json",
        "corpus": b / "level4_mechanism_inputs" / "invention_corpus.jsonl",
        "manifest": b / "level4_stepB_run_manifest.json",
        "out_hash": b / "level4_stepB_output_hash.txt",
        "firewall": b / "level4_provenance_firewall.json",
        "unknown": b / "level4_stepB_some_new_artifact.json",
        "transfer": b / "transfer_witnesses.jsonl",
        "lockbox": main / "outputs" / "lockbox" / "manifest.json",
        "evalsplit": main / "outputs" / "eval_split_v1.json",
        "runner": main / "scripts" / "cora_level4_stepB_run.py",
        "candidates": main / "level4_stepB" / "candidates.py",
        "train": main / "data" / "arc" / "arc-agi_training_challenges.json",
        "evaluation": main / "data" / "arc" / "arc-agi_evaluation_challenges.json",
        "log": main / "logs" / "level4_stepB_run.log",
        "tti_inventory_copy": tti / "outputs" / "cora_breakthrough" / "level4_stepB_inventory.json",
        "tti_eval_split": tti / "outputs" / "tti" / "eval_split_v1.json",
        "tti_other_output": tti / "outputs" / "tti" / "las_r1" / "rows.jsonl",
    }
    for path in p.values():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"k": 1}\n')
    p["log"].write_text("start\nSTEP B FROZEN\n")
    proc.mkdir()
    monkeypatch.setattr(FP, "MAIN", main)
    monkeypatch.setattr(FP, "TTI", tti)
    monkeypatch.setattr(FP, "PROC", proc)
    return SimpleNamespace(main=main, tti=tti, b=b, p=p)


def pin(tree):
    result = FP.create_pin()
    assert result["outcome"] == FP.PIN_CREATED, result


#  ------------------------------------------------------------- classify

def test_step_b_semantics_are_sealed(tree):
    for key in ("journal", "witnesses", "inventory", "lane", "corpus", "runner", "candidates"):
        assert classify(tree.p[key]) is SealedClass.STEP_B_SEMANTICS, key


def test_sealed_copies_inside_the_dev_worktree_are_sealed_too(tree):
    assert classify(tree.p["tti_inventory_copy"]) is SealedClass.STEP_B_SEMANTICS
    assert classify(tree.p["tti_eval_split"]) is SealedClass.LOCKBOX


def test_quantitative_protocol_artifacts_are_open(tree):
    for key in ("manifest", "out_hash", "log"):
        assert classify(tree.p[key]) is None, key


def test_the_firewall_unlocks_with_e_transfer_not_with_inspection(tree):
    assert classify(tree.p["firewall"]) is SealedClass.E_TRANSFER


def test_raw_arc_data_is_sealed_by_what_it_could_reveal(tree):
    assert classify(tree.p["train"]) is SealedClass.E_TRANSFER
    assert classify(tree.p["evaluation"]) is SealedClass.LOCKBOX


def test_transfer_and_lockbox_have_their_own_classes(tree):
    assert classify(tree.p["transfer"]) is SealedClass.E_TRANSFER
    assert classify(tree.p["lockbox"]) is SealedClass.LOCKBOX
    assert classify(tree.p["evalsplit"]) is SealedClass.LOCKBOX


def test_unknown_artifacts_under_a_watched_root_fail_closed(tree):
    assert classify(tree.p["unknown"]) is SealedClass.STEP_B_SEMANTICS
    assert classify(tree.p["tti_other_output"]) is SealedClass.STEP_B_SEMANTICS


def test_paths_outside_watched_roots_are_not_governed(tree):
    assert classify(tree.main / "docs" / "notes.md") is None
    assert classify(tree.tti / "cora_tti" / "module.py") is None


def test_an_ancestor_directory_name_cannot_decide_the_class(tmp_path, monkeypatch):
    root = tmp_path / "lockbox_scratch" / "e_transfer_notes" / "main"
    (root / "logs").mkdir(parents=True)
    log = root / "logs" / "level4_stepB_run.log"
    log.write_text("")
    monkeypatch.setattr(FP, "MAIN", root)
    monkeypatch.setattr(FP, "TTI", tmp_path / "tti")
    assert classify(log) is None


#  ------------------------------------------------------------ stage order

def test_pinning_stages_cannot_read_step_b_semantics(tree):
    for stage in (Stage.PIN_OUTPUT_HASH, Stage.PIN_PROTOCOL_HASHES):
        with pytest.raises(SealedAccessError):
            GateGuard(stage).check(tree.p["journal"])


def test_pinning_stages_run_without_a_pin(tree):
    GateGuard(Stage.PIN_OUTPUT_HASH)
    GateGuard(Stage.PIN_PROTOCOL_HASHES)


def test_inspection_unlocks_step_b_but_not_transfer_firewall_or_lockbox(tree):
    pin(tree)
    guard = GateGuard(Stage.INSPECT_RETAINED_PRODUCTIONS)
    guard.check(tree.p["journal"])
    guard.check(tree.p["runner"])
    for key in ("firewall", "transfer", "train", "lockbox", "evaluation"):
        with pytest.raises(SealedAccessError):
            guard.check(tree.p[key])


def test_worktree_copies_are_never_read_even_once_their_class_unlocks(tree):
    pin(tree)
    for stage in (Stage.INSPECT_RETAINED_PRODUCTIONS, Stage.GATE_COMPLETE):
        with pytest.raises(SealedAccessError):
            GateGuard(stage).check(tree.p["tti_inventory_copy"])


def test_e_transfer_unlocks_only_at_stage_seven(tree):
    pin(tree)
    with pytest.raises(SealedAccessError):
        GateGuard(Stage.CAPABILITY_GROWTH_WITNESS).check(tree.p["firewall"])
    guard = GateGuard(Stage.E_TRANSFER_EVALUATION)
    guard.check(tree.p["firewall"])
    with pytest.raises(SealedAccessError):
        guard.check(tree.p["lockbox"])


def test_lockbox_stays_closed_through_every_stage_inside_the_gate(tree):
    pin(tree)
    for stage in Stage:
        if stage is Stage.GATE_COMPLETE:
            continue
        with pytest.raises(SealedAccessError):
            GateGuard(stage).check(tree.p["lockbox"])


def test_lockbox_opens_only_once_the_gate_is_complete(tree):
    pin(tree)
    GateGuard(Stage.GATE_COMPLETE).check(tree.p["lockbox"])


#  ------------------------------------------- provenance after the pin

def test_stage_three_without_a_pin_refuses(tree):
    with pytest.raises(PinProvenanceError) as err:
        GateGuard(Stage.INSPECT_RETAINED_PRODUCTIONS)
    assert err.value.status == FP.PIN_MISSING


def test_the_pin_requirement_cannot_be_switched_off_after_stage_two(tree):
    pin(tree)
    with pytest.raises(ValueError):
        GateGuard(Stage.INSPECT_RETAINED_PRODUCTIONS, require_pin=False)


def test_untouched_pinned_set_permits_stage_three(tree):
    pin(tree)
    guard = GateGuard(Stage.INSPECT_RETAINED_PRODUCTIONS)
    assert guard.verification.status == FP.PIN_VERIFIED
    with guard.open(tree.p["journal"]) as handle:
        assert handle.read() == '{"k": 1}\n'


def test_pinned_artifact_modified_after_pin_refuses_stage_three(tree):
    pin(tree)
    tree.p["lane"].write_text("changed")
    with pytest.raises(PinProvenanceError) as err:
        GateGuard(Stage.INSPECT_RETAINED_PRODUCTIONS)
    assert err.value.status == FP.PIN_ARTIFACT_DRIFT


def test_pinned_artifact_deleted_after_pin_refuses_stage_three(tree):
    pin(tree)
    tree.p["corpus"].unlink()
    with pytest.raises(PinProvenanceError) as err:
        GateGuard(Stage.INSPECT_RETAINED_PRODUCTIONS)
    assert err.value.status == FP.PIN_ARTIFACT_MISSING


def test_pin_json_modified_refuses_stage_three(tree):
    pin(tree)
    data = json.loads(FP.pin_path().read_bytes())
    data["artifacts"].pop()
    FP.pin_path().write_text(json.dumps(data, indent=1, sort_keys=True))
    with pytest.raises(PinProvenanceError) as err:
        GateGuard(Stage.INSPECT_RETAINED_PRODUCTIONS)
    assert err.value.status == FP.PIN_JSON_ALTERED


def test_a_new_file_in_a_pinned_scope_refuses_stage_three(tree):
    pin(tree)
    (tree.b / "level4_stepB_gate_outputs" / "late.json").write_text("{}")
    with pytest.raises(PinProvenanceError) as err:
        GateGuard(Stage.INSPECT_RETAINED_PRODUCTIONS)
    assert err.value.status == FP.PIN_SCOPE_GREW_AFTER_FREEZE


def test_drift_after_construction_is_caught_on_the_next_read(tree):
    pin(tree)
    guard = GateGuard(Stage.INSPECT_RETAINED_PRODUCTIONS)
    tree.p["journal"].write_text("tampered\n")
    with pytest.raises(PinProvenanceError) as err:
        with guard.open(tree.p["journal"]):
            pass
    assert err.value.status == FP.PIN_ARTIFACT_DRIFT
    assert guard.ledger[-1].permitted is False
    assert guard.ledger[-1].reason == FP.PIN_ARTIFACT_DRIFT


def test_a_file_appearing_after_construction_is_caught_on_read(tree):
    pin(tree)
    guard = GateGuard(Stage.INSPECT_RETAINED_PRODUCTIONS)
    late = tree.b / "level4_mechanism_inputs" / "late.jsonl"
    late.write_text("{}")
    with pytest.raises(PinProvenanceError) as err:
        guard.check(late)
    assert err.value.status == FP.PIN_SCOPE_GREW_AFTER_FREEZE


def test_a_provenance_failure_is_never_swallowed_as_an_access_refusal(tree):
    assert not issubclass(PinProvenanceError, SealedAccessError)
    pin(tree)
    guard = GateGuard(Stage.INSPECT_RETAINED_PRODUCTIONS)
    tree.p["witnesses"].write_text("changed")
    with pytest.raises(PinProvenanceError):
        guard.permits(tree.p["witnesses"])


#  -------------------------------------------------------- writes and ledger

def test_the_gate_never_writes_into_the_experiment_tree(tree):
    pin(tree)
    guard = GateGuard(Stage.INSPECT_RETAINED_PRODUCTIONS)
    for mode in ("w", "a", "x", "r+"):
        with pytest.raises(SealedAccessError):
            with guard.open(tree.p["journal"], mode):
                pass
    assert FP.verify_pin().status == FP.PIN_VERIFIED


def test_every_decision_is_recorded_including_refusals(tree):
    pin(tree)
    guard = GateGuard(Stage.INSPECT_RETAINED_PRODUCTIONS)
    assert guard.permits(tree.p["journal"]) is True
    assert guard.permits(tree.p["lockbox"]) is False
    path = guard.write_ledger()
    records = [json.loads(line) for line in path.read_text().splitlines()]
    assert [r["permitted"] for r in records] == [True, False]
    assert records[1]["sealed_class"] == "LOCKBOX"
    assert path.parent == FP.gate_dir()
    assert guard.ledger == []


def test_the_ledger_is_append_only(tree):
    pin(tree)
    guard = GateGuard(Stage.INSPECT_RETAINED_PRODUCTIONS)
    guard.permits(tree.p["journal"])
    path = guard.write_ledger()
    guard.permits(tree.p["witnesses"])
    guard.write_ledger()
    assert len(path.read_text().splitlines()) == 2
