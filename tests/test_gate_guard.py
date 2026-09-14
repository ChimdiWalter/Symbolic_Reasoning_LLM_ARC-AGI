"""Tests for the Capability-Growth Gate's access guard.

They check the two properties the gate depends on. The read order, including
the order inside a stage, is enforced by code rather than by whoever runs it.
And every stage after pinning is looking at exactly the pinned bytes, with both
pins bound to commits. Most tests assert that something is impossible. All run
on synthetic fixture trees; none touches the live experiment.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from cora_tti import freeze_pin as FP
from cora_tti import gate_guard as G
from cora_tti.gate_guard import (GateGuard, PinProvenanceError, SealedAccessError,
                                 SealedClass, Stage, classify)

GIT = ["git", "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid",
       "-c", "commit.gpgsign=false", "-c", "init.defaultBranch=main"]


def run_git(repo, *args):
    return subprocess.run([*GIT, "-C", str(repo), *args], check=True,
                          capture_output=True, text=True).stdout


@pytest.fixture
def tree(tmp_path, monkeypatch):
    main, tti, proc = tmp_path / "main", tmp_path / "tti", tmp_path / "proc"
    b = main / "outputs" / "cora_breakthrough"
    p = {
        "journal": b / "level4_stepB_journal.jsonl",
        "seal": b / "level4_withheld_expectation_seal.json",
        "witnesses": b / "level4_stepB_witnesses.json",
        "inventory": b / "level4_stepB_inventory.json",
        "lane": b / "level4_stepB_gate_outputs" / "deta_selection.json",
        "corpus": b / "level4_mechanism_inputs" / "invention_corpus.jsonl",
        "manifest": b / "level4_stepB_run_manifest.json",
        "out_hash": b / "level4_stepB_output_hash.txt",
        "firewall": b / "level4_provenance_firewall.json",
        "unknown_stepb": b / "level4_stepB_some_new_artifact.json",
        "admissibility": b / "level4_baseline_admissibility_v2.json",
        "stepa": b / "level4_stepA_clusters.json",
        "v21": b / "v21_promotion_manifest.json",
        "registry": b / "concept_registry.json",
        "transfer": b / "transfer_witnesses.jsonl",
        "lockbox": main / "outputs" / "lockbox" / "manifest.json",
        "evalsplit": main / "outputs" / "eval_split_v1.json",
        "other_output": main / "outputs" / "some_other_study" / "rows.jsonl",
        "runner": main / "scripts" / "cora_level4_stepB_run.py",
        "candidates": main / "level4_stepB" / "candidates.py",
        "runtime": main / "level4_blind_runtime" / "search.py",
        "train_flat": main / "data" / "arc-agi_training_challenges.json",
        "train_nested": main / "data" / "arc" / "arc-agi_training_solutions.json",
        "eval_nested": main / "data" / "arc" / "arc-agi_evaluation_challenges.json",
        "data_other": main / "data" / "derived_copy.json",
        "log": main / "logs" / "level4_stepB_run.log",
        "tti_inventory_copy": tti / "outputs" / "cora_breakthrough" / "level4_stepB_inventory.json",
        "tti_eval_split": tti / "outputs" / "tti" / "eval_split_v1.json",
        "tti_other_output": tti / "outputs" / "tti" / "las_r1" / "rows.jsonl",
        "tti_train_copy": tti / "data" / "arc-agi_training_challenges.json",
        "extract_promotion": tti / "outputs" / "tti" / "stepB_gate" / "extracts" / "promotion_tasks.json",
        "extract_etransfer": tti / "outputs" / "tti" / "stepB_gate" / "extracts" / "etransfer_tasks.json",
        "engine": tti / "geocat_arc" / "object_reasoning" / "meta_v21.py",
    }
    for path in p.values():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"k": 1}\n')
    p["log"].write_text("start\nSTEP B FROZEN\n")
    proc.mkdir()
    (tti / ".gitignore").write_text("outputs/\n")
    run_git(tti, "init", "-q")
    run_git(tti, "add", ".gitignore")
    run_git(tti, "commit", "-q", "-m", "init")
    monkeypatch.setattr(FP, "MAIN", main)
    monkeypatch.setattr(FP, "TTI", tti)
    monkeypatch.setattr(FP, "PROC", proc)
    return SimpleNamespace(main=main, tti=tti, b=b, p=p)


def ready(tree):
    """Pin, commit, bind, commit, then write and commit the G2 module pin."""
    assert FP.create_pin()["outcome"] == FP.PIN_CREATED
    run_git(tree.tti, "add", "-f", "outputs/tti/stepB_gate/pin")
    run_git(tree.tti, "commit", "-q", "-m", "pin")
    assert FP.bind_pin()["outcome"] == FP.PIN_BOUND
    run_git(tree.tti, "add", "docs/stepB_gate/pin_binding.json")
    run_git(tree.tti, "commit", "-q", "-m", "bind")
    records = [{"path": str(Path(x).resolve()), "sha256": FP.file_digest(x)}
               for x in (tree.p["engine"], tree.p["lockbox"], tree.p["admissibility"])]
    data = json.dumps({"artifacts": records}, indent=1, sort_keys=True).encode()
    FP.module_pin_path().write_bytes(data)
    FP.module_pin_hash_path().write_text(hashlib.sha256(data).hexdigest() + "\n")
    run_git(tree.tti, "add", "-f", "outputs/tti/stepB_gate/stepB_gate_module_pin.json",
            "outputs/tti/stepB_gate/stepB_gate_module_pin_hash.txt")
    run_git(tree.tti, "commit", "-q", "-m", "module pin")


def commit_event(tree, event, commit=True):
    path = FP.gate_dir() / G.EVENT_FILES[event]
    path.write_text(json.dumps({"event": event}) + "\n")
    if commit:
        run_git(tree.tti, "add", "-f", str(path.relative_to(tree.tti)))
        run_git(tree.tti, "commit", "-q", "-m", event)


#  ------------------------------------------------------------- classify

def test_frozen_design_source_is_its_own_class(tree):
    for key in ("runner", "candidates", "runtime"):
        assert classify(tree.p[key]) is SealedClass.STEP_B_SOURCE, key


def test_run_outputs_are_their_own_class(tree):
    for key in ("witnesses", "inventory", "lane", "corpus", "unknown_stepb"):
        assert classify(tree.p[key]) is SealedClass.STEP_B_OUTPUTS, key


def test_the_journal_and_the_expectation_seal_are_never_readable(tree):
    assert classify(tree.p["journal"]) is SealedClass.NEVER
    assert classify(tree.p["seal"]) is SealedClass.NEVER


def test_pre_run_records_are_separate_from_run_outputs(tree):
    for key in ("admissibility", "stepa", "v21", "registry"):
        assert classify(tree.p[key]) is SealedClass.PRE_RUN_RECORDS, key


def test_quantitative_protocol_artifacts_are_open(tree):
    for key in ("manifest", "out_hash", "log"):
        assert classify(tree.p[key]) is None, key
    assert classify(tree.tti / "outputs" / "tti" / "stepB_gate" / "notes.json") is None


def test_the_firewall_is_provenance_class(tree):
    assert classify(tree.p["firewall"]) is SealedClass.E_TRANSFER_PROVENANCE


def test_every_raw_arc_data_file_is_lockbox_wherever_it_lives(tree, tmp_path):
    for key in ("train_flat", "train_nested", "eval_nested", "data_other", "tti_train_copy"):
        assert classify(tree.p[key]) is SealedClass.LOCKBOX, key
    stray = tmp_path / "scratch" / "arc-agi_training_copy.json"
    assert classify(stray) is SealedClass.LOCKBOX


def test_per_split_extracts_have_their_own_classes(tree):
    assert classify(tree.p["extract_promotion"]) is SealedClass.PROMOTION_DATA
    assert classify(tree.p["extract_etransfer"]) is SealedClass.E_TRANSFER


def test_transfer_and_lockbox_names(tree):
    assert classify(tree.p["transfer"]) is SealedClass.E_TRANSFER
    assert classify(tree.p["lockbox"]) is SealedClass.LOCKBOX
    assert classify(tree.p["evalsplit"]) is SealedClass.LOCKBOX
    assert classify(tree.p["tti_eval_split"]) is SealedClass.LOCKBOX


def test_unrecognized_outputs_fail_closed(tree):
    assert classify(tree.p["other_output"]) is SealedClass.STEP_B_OUTPUTS
    assert classify(tree.p["tti_other_output"]) is SealedClass.STEP_B_OUTPUTS


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


#  ---------------------------------------------------- stage order and events

def test_pinning_stages_read_nothing_sealed(tree):
    for stage in (Stage.PIN_OUTPUT_HASH, Stage.PIN_PROTOCOL_HASHES):
        guard = GateGuard(stage)
        for key in ("runner", "runtime", "admissibility", "inventory", "journal"):
            with pytest.raises(SealedAccessError):
                guard.check(tree.p[key])


def test_stage_three_reads_source_and_pre_run_records_before_the_tool_manifest(tree):
    ready(tree)
    guard = GateGuard(Stage.INSPECT_RETAINED_PRODUCTIONS)
    guard.check(tree.p["runner"])
    guard.check(tree.p["runtime"])
    guard.check(tree.p["admissibility"])
    with pytest.raises(SealedAccessError, match="tool_manifest"):
        guard.check(tree.p["inventory"])


def test_run_outputs_open_only_once_the_tool_manifest_is_committed(tree):
    ready(tree)
    commit_event(tree, "tool_manifest", commit=False)
    with pytest.raises(SealedAccessError):
        GateGuard(Stage.INSPECT_RETAINED_PRODUCTIONS).check(tree.p["inventory"])
    run_git(tree.tti, "add", "-f", "outputs/tti/stepB_gate/gate_tool_manifest.json")
    run_git(tree.tti, "commit", "-q", "-m", "tool manifest")
    GateGuard(Stage.INSPECT_RETAINED_PRODUCTIONS).check(tree.p["inventory"])


def test_the_firewall_needs_stage_seven_and_the_committed_admitted_set(tree):
    ready(tree)
    commit_event(tree, "tool_manifest")
    with pytest.raises(SealedAccessError):
        GateGuard(Stage.CAPABILITY_GROWTH_WITNESS).check(tree.p["firewall"])
    with pytest.raises(SealedAccessError, match="admitted_set"):
        GateGuard(Stage.E_TRANSFER_EVALUATION).check(tree.p["firewall"])
    commit_event(tree, "admitted_set")
    GateGuard(Stage.E_TRANSFER_EVALUATION).check(tree.p["firewall"])
    GateGuard(Stage.E_TRANSFER_EVALUATION).check(tree.p["extract_promotion"])


def test_e_transfer_needs_stage_eight_and_the_committed_withdrawals(tree):
    ready(tree)
    commit_event(tree, "admitted_set")
    with pytest.raises(SealedAccessError):
        GateGuard(Stage.E_TRANSFER_EVALUATION).check(tree.p["extract_etransfer"])
    with pytest.raises(SealedAccessError, match="withdrawals"):
        GateGuard(Stage.E_TRANSFER_MEASUREMENT).check(tree.p["extract_etransfer"])
    commit_event(tree, "withdrawals")
    GateGuard(Stage.E_TRANSFER_MEASUREMENT).check(tree.p["extract_etransfer"])


def test_raw_training_data_is_never_readable_inside_the_gate(tree):
    ready(tree)
    for event in ("tool_manifest", "admitted_set", "withdrawals"):
        commit_event(tree, event)
    for stage in Stage:
        if stage is Stage.GATE_COMPLETE:
            continue
        with pytest.raises(SealedAccessError):
            GateGuard(stage, require_pin=stage > Stage.PIN_PROTOCOL_HASHES).check(tree.p["train_flat"])


def test_the_journal_and_the_seal_are_refused_even_at_gate_complete(tree):
    ready(tree)
    guard = GateGuard(Stage.GATE_COMPLETE)
    for key in ("journal", "seal"):
        with pytest.raises(SealedAccessError, match="NEVER"):
            guard.check(tree.p[key])


def test_worktree_copies_are_refused_at_every_stage(tree):
    ready(tree)
    commit_event(tree, "tool_manifest")
    for stage in (Stage.INSPECT_RETAINED_PRODUCTIONS, Stage.GATE_COMPLETE):
        with pytest.raises(SealedAccessError):
            GateGuard(stage).check(tree.p["tti_inventory_copy"])


def test_lockbox_opens_in_code_only_at_gate_complete(tree):
    ready(tree)
    with pytest.raises(SealedAccessError):
        GateGuard(Stage.POST_PROMOTION_ANALYSIS).check(tree.p["lockbox"])
    GateGuard(Stage.GATE_COMPLETE).check(tree.p["lockbox"])


#  ------------------------------------------------------------ hash-only

def test_hash_only_is_licensed_at_stage_two_and_ledgered(tree):
    guard = GateGuard(Stage.PIN_PROTOCOL_HASHES)
    result = guard.hash_only(tree.p["lockbox"])
    assert result["sha256"] == hashlib.sha256(b'{"k": 1}\n').hexdigest()
    assert guard.ledger[-1].access_mode == "HASH_ONLY" and guard.ledger[-1].permitted


def test_hash_only_is_refused_outside_stages_two_and_eleven(tree):
    ready(tree)
    with pytest.raises(SealedAccessError):
        GateGuard(Stage.CLASSIFY_CLAIM_LEVEL).hash_only(tree.p["lockbox"])


def test_hash_only_never_touches_the_never_class(tree):
    with pytest.raises(SealedAccessError):
        GateGuard(Stage.PIN_PROTOCOL_HASHES).hash_only(tree.p["journal"])


#  ------------------------------------------- provenance after the pin

def test_stage_three_without_a_pin_refuses(tree):
    with pytest.raises(PinProvenanceError) as err:
        GateGuard(Stage.INSPECT_RETAINED_PRODUCTIONS)
    assert err.value.status == FP.PIN_MISSING


def test_stage_three_without_a_committed_binding_refuses(tree):
    assert FP.create_pin()["outcome"] == FP.PIN_CREATED
    with pytest.raises(PinProvenanceError) as err:
        GateGuard(Stage.INSPECT_RETAINED_PRODUCTIONS)
    assert err.value.status == FP.PIN_BINDING_MISSING


def test_stage_three_without_the_module_pin_refuses(tree):
    ready(tree)
    FP.module_pin_path().unlink()
    with pytest.raises(PinProvenanceError) as err:
        GateGuard(Stage.INSPECT_RETAINED_PRODUCTIONS)
    assert err.value.status == FP.MODULE_PIN_MISSING


def test_the_pin_requirement_cannot_be_switched_off_after_stage_two(tree):
    ready(tree)
    with pytest.raises(ValueError):
        GateGuard(Stage.INSPECT_RETAINED_PRODUCTIONS, require_pin=False)


def test_an_untouched_bound_set_permits_stage_three(tree):
    ready(tree)
    guard = GateGuard(Stage.INSPECT_RETAINED_PRODUCTIONS)
    assert guard.verification.status == FP.PIN_VERIFIED
    assert guard.module_verification.status == FP.MODULE_PIN_VERIFIED
    with guard.open(tree.p["runner"]) as handle:
        assert handle.read() == '{"k": 1}\n'


def test_a_pinned_artifact_modified_after_the_pin_refuses_stage_three(tree):
    ready(tree)
    tree.p["lane"].write_text("changed")
    with pytest.raises(PinProvenanceError) as err:
        GateGuard(Stage.INSPECT_RETAINED_PRODUCTIONS)
    assert err.value.status == FP.PIN_ARTIFACT_DRIFT


def test_a_pinned_artifact_deleted_after_the_pin_refuses_stage_three(tree):
    ready(tree)
    tree.p["corpus"].unlink()
    with pytest.raises(PinProvenanceError) as err:
        GateGuard(Stage.INSPECT_RETAINED_PRODUCTIONS)
    assert err.value.status == FP.PIN_ARTIFACT_MISSING


def test_a_modified_pin_json_refuses_stage_three(tree):
    ready(tree)
    data = json.loads(FP.pin_path().read_bytes())
    data["artifacts"].pop()
    FP.pin_path().write_text(json.dumps(data, indent=1, sort_keys=True))
    with pytest.raises(PinProvenanceError) as err:
        GateGuard(Stage.INSPECT_RETAINED_PRODUCTIONS)
    assert err.value.status == FP.PIN_JSON_ALTERED


def test_a_new_file_in_a_pinned_scope_refuses_stage_three(tree):
    ready(tree)
    (tree.b / "level4_stepB_gate_outputs" / "late.json").write_text("{}")
    with pytest.raises(PinProvenanceError) as err:
        GateGuard(Stage.INSPECT_RETAINED_PRODUCTIONS)
    assert err.value.status == FP.PIN_SCOPE_GREW_AFTER_FREEZE


def test_deleting_and_recreating_the_pin_refuses_stage_three(tree):
    ready(tree)
    shutil.rmtree(FP.pin_dir())
    assert FP.create_pin()["outcome"] == FP.PIN_CREATED
    with pytest.raises(PinProvenanceError) as err:
        GateGuard(Stage.INSPECT_RETAINED_PRODUCTIONS)
    assert err.value.status == FP.PIN_COMMIT_MISMATCH


def test_an_engine_change_after_g2_refuses_stage_three(tree):
    ready(tree)
    tree.p["engine"].write_text("# K changed in the dev worktree\n")
    with pytest.raises(PinProvenanceError) as err:
        GateGuard(Stage.INSPECT_RETAINED_PRODUCTIONS)
    assert err.value.status == FP.MODULE_ARTIFACT_DRIFT


def test_drift_after_construction_is_caught_on_the_next_read(tree):
    ready(tree)
    guard = GateGuard(Stage.INSPECT_RETAINED_PRODUCTIONS)
    tree.p["runner"].write_text("# tampered\n")
    with pytest.raises(PinProvenanceError) as err:
        with guard.open(tree.p["runner"]):
            pass
    assert err.value.status == FP.PIN_ARTIFACT_DRIFT
    assert guard.ledger[-1].permitted is False
    assert guard.ledger[-1].reason == FP.PIN_ARTIFACT_DRIFT


def test_module_drift_after_construction_is_caught_on_read(tree):
    ready(tree)
    guard = GateGuard(Stage.INSPECT_RETAINED_PRODUCTIONS)
    tree.p["admissibility"].write_text("changed")
    with pytest.raises(PinProvenanceError) as err:
        guard.check(tree.p["admissibility"])
    assert err.value.status == FP.MODULE_ARTIFACT_DRIFT


def test_a_file_appearing_after_construction_is_caught_on_read(tree):
    ready(tree)
    guard = GateGuard(Stage.INSPECT_RETAINED_PRODUCTIONS)
    late = tree.main / "level4_blind_runtime" / "late.py"
    late.write_text("# late\n")
    with pytest.raises(PinProvenanceError) as err:
        guard.check(late)
    assert err.value.status == FP.PIN_SCOPE_GREW_AFTER_FREEZE


def test_a_provenance_failure_is_never_swallowed_as_an_access_refusal(tree):
    assert not issubclass(PinProvenanceError, SealedAccessError)
    ready(tree)
    guard = GateGuard(Stage.INSPECT_RETAINED_PRODUCTIONS)
    tree.p["runner"].write_text("changed")
    with pytest.raises(PinProvenanceError):
        guard.permits(tree.p["runner"])


#  -------------------------------------------------------- writes and ledger

def test_the_gate_never_writes_into_the_experiment_tree(tree):
    ready(tree)
    guard = GateGuard(Stage.INSPECT_RETAINED_PRODUCTIONS)
    for mode in ("w", "a", "x", "r+"):
        with pytest.raises(SealedAccessError):
            with guard.open(tree.p["runner"], mode):
                pass
    assert FP.verify_pin(require_binding=True).status == FP.PIN_VERIFIED


def test_every_decision_is_recorded_including_refusals(tree):
    ready(tree)
    guard = GateGuard(Stage.INSPECT_RETAINED_PRODUCTIONS)
    assert guard.permits(tree.p["runner"]) is True
    assert guard.permits(tree.p["lockbox"]) is False
    path = guard.write_ledger()
    records = [json.loads(line) for line in path.read_text().splitlines()]
    assert [r["permitted"] for r in records] == [True, False]
    assert records[1]["sealed_class"] == "LOCKBOX"
    assert path.parent == FP.gate_dir()
    assert guard.ledger == []


def test_the_ledger_is_append_only(tree):
    ready(tree)
    guard = GateGuard(Stage.INSPECT_RETAINED_PRODUCTIONS)
    guard.permits(tree.p["runner"])
    path = guard.write_ledger()
    guard.permits(tree.p["runtime"])
    guard.write_ledger()
    assert len(path.read_text().splitlines()) == 2
