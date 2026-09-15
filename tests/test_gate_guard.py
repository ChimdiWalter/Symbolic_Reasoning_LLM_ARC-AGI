"""Tests for the Capability-Growth Gate's access guard.

They check the properties the gate depends on. The read order, inside a stage
and across stages, is enforced by code through committed, one-shot, chained
events rather than by whoever runs it. Sealed names keep their class wherever a
copy lives. Raw ARC data yields licensed members only. Every stage after pinning
sees exactly the pinned bytes, with both pins bound to commits and the freeze pin
anchored outside the repository. Most tests assert that something is impossible.
All run on synthetic fixture trees; none touches the live experiment.
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
SENTINEL = "LOCKBOX_SENTINEL_MUST_NEVER_BE_DECODED"


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
    p["lockbox"].write_text(json.dumps({"splits": {"lockbox": ["cccc3333", SENTINEL],
                                                   "promotion": ["aaaa1111"]}}) + "\n")
    p["train_flat"].write_text(json.dumps({
        "aaaa1111": {"train": [], "test": [{"input": [[1]]}]},
        "bbbb2222": {"train": [], "test": [{"input": [[2]]}]},
        "cccc3333": {"note": SENTINEL}}) + "\n")
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
    result = FP.write_module_pin(roots=[tree.p["engine"].parent],
                                 files=[tree.p["lockbox"], tree.p["admissibility"]])
    assert result["outcome"] == FP.MODULE_PIN_WRITTEN, result
    run_git(tree.tti, "add", "-f", "outputs/tti/stepB_gate/stepB_gate_module_pin.json",
            "outputs/tti/stepB_gate/stepB_gate_module_pin_hash.txt")
    run_git(tree.tti, "commit", "-q", "-m", "module pin")


def commit_files(tree, *paths, message="records"):
    run_git(tree.tti, "add", "-f", *[str(Path(x).relative_to(tree.tti)) for x in paths])
    run_git(tree.tti, "commit", "-q", "-m", message)


def gate_file(name, payload=None):
    path = FP.gate_dir() / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"record": name} if payload is None else payload) + "\n")
    return path


PAYLOADS = {"etransfer_admitted_set.json": {"admitted": ["aaaa1111", "bbbb2222"]},
            "etransfer_withdrawals.json": {"withdrawn": ["bbbb2222"]},
            "lockbox_closure.json": {"outcome": "LOCKBOX-ELIGIBLE"}}
FULL_CHAIN = ("g3b_open", "g7b_open", "g8_open", "g8_closed", "g11_complete")


def open_event(tree, event):
    """Commit what the event requires and attests, then write and commit the event."""
    spec = G.EVENTS[event]
    needed = [gate_file(n, PAYLOADS.get(n)) for n in spec.requires if not (FP.gate_dir() / n).exists()]
    if spec.attests and not (FP.gate_dir() / spec.attests).exists():
        needed.append(gate_file(spec.attests, PAYLOADS.get(spec.attests)))
    if needed:
        commit_files(tree, *needed, message=f"{event} inputs")
    result = G.write_event(event)
    assert result["outcome"] == G.EVENT_WRITTEN, result
    commit_files(tree, FP.gate_dir() / spec.file, message=event)


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


def test_protocol_artifacts_and_the_gate_directory_are_not_sealed(tree):
    for key in ("manifest", "out_hash", "log"):
        assert classify(tree.p[key]) is None, key
    assert classify(tree.tti / "outputs" / "tti" / "stepB_gate" / "notes.json") is None


def test_the_firewall_is_provenance_class(tree):
    assert classify(tree.p["firewall"]) is SealedClass.E_TRANSFER_PROVENANCE


def test_every_raw_arc_data_file_is_lockbox_wherever_it_lives(tree, tmp_path):
    for key in ("train_flat", "train_nested", "eval_nested", "data_other", "tti_train_copy"):
        assert classify(tree.p[key]) is SealedClass.LOCKBOX, key
    assert classify(tmp_path / "scratch" / "arc-agi_training_copy.json") is SealedClass.LOCKBOX


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


def test_an_ancestor_directory_name_inside_a_checkout_cannot_decide_the_class(tmp_path, monkeypatch):
    root = tmp_path / "lockbox_scratch" / "e_transfer_notes" / "main"
    (root / "logs").mkdir(parents=True)
    log = root / "logs" / "level4_stepB_run.log"
    log.write_text("")
    monkeypatch.setattr(FP, "MAIN", root)
    monkeypatch.setattr(FP, "TTI", tmp_path / "tti")
    assert classify(log) is None


def test_sealed_names_keep_their_class_when_copied_anywhere(tree, tmp_path):
    backup = tree.main / "outputs" / "backup"
    assert classify(backup / "level4_provenance_firewall.json") is SealedClass.E_TRANSFER_PROVENANCE
    assert classify(backup / "level4_stepB_journal_copy.jsonl") is SealedClass.NEVER
    elsewhere = tmp_path / "elsewhere"
    assert classify(elsewhere / "level4_withheld_expectation_seal.json") is SealedClass.NEVER
    assert classify(elsewhere / "level4_stepB_inventory.json") is SealedClass.STEP_B_OUTPUTS
    assert classify(elsewhere / "etransfer_tasks.json") is SealedClass.E_TRANSFER


def test_the_strictest_matching_class_wins(tree, tmp_path):
    assert classify(tmp_path / "lockbox" / "level4_stepB_journal.jsonl") is SealedClass.NEVER
    assert classify(tree.main / "outputs" / "e_transfer" / "promotion_tasks.json") is SealedClass.E_TRANSFER


#  ---------------------------------------------------- stage order and events

def test_pinning_stages_read_nothing_sealed(tree):
    for stage in (Stage.PIN_OUTPUT_HASH, Stage.PIN_PROTOCOL_HASHES):
        guard = GateGuard(stage)
        for key in ("runner", "runtime", "admissibility", "inventory", "journal"):
            with pytest.raises(SealedAccessError):
                guard.check(tree.p[key])


def test_protocol_artifact_content_opens_only_at_stage_three(tree):
    for stage in (Stage.PIN_OUTPUT_HASH, Stage.PIN_PROTOCOL_HASHES):
        with pytest.raises(SealedAccessError, match="stage 3"):
            GateGuard(stage).check(tree.p["log"])
    digest = GateGuard(Stage.PIN_PROTOCOL_HASHES).hash_only(tree.p["log"])["sha256"]
    assert digest == hashlib.sha256(tree.p["log"].read_bytes()).hexdigest()
    ready(tree)
    GateGuard(Stage.INSPECT_RETAINED_PRODUCTIONS).check(tree.p["log"])


def test_stage_three_reads_source_and_pre_run_records_before_the_event(tree):
    ready(tree)
    guard = GateGuard(Stage.INSPECT_RETAINED_PRODUCTIONS)
    for key in ("runner", "runtime", "admissibility"):
        guard.check(tree.p[key])
    with pytest.raises(SealedAccessError, match="g3b_open"):
        guard.check(tree.p["inventory"])


def test_an_early_committed_tool_manifest_opens_nothing(tree):
    commit_files(tree, gate_file("gate_tool_manifest.json"), message="draft manifest at G1")
    ready(tree)
    with pytest.raises(SealedAccessError, match="g3b_open"):
        GateGuard(Stage.INSPECT_RETAINED_PRODUCTIONS).check(tree.p["inventory"])


def test_run_outputs_open_only_after_the_event_is_committed(tree):
    ready(tree)
    commit_files(tree, gate_file("gate_tool_manifest.json"), gate_file("g3a_record.json"))
    assert G.write_event("g3b_open")["outcome"] == G.EVENT_WRITTEN
    with pytest.raises(SealedAccessError):
        GateGuard(Stage.INSPECT_RETAINED_PRODUCTIONS).check(tree.p["inventory"])
    commit_files(tree, FP.gate_dir() / "event_g3b_open.json")
    GateGuard(Stage.INSPECT_RETAINED_PRODUCTIONS).check(tree.p["inventory"])


def test_an_event_needs_its_stage_record_and_its_committed_artifact(tree):
    ready(tree)
    commit_files(tree, gate_file("gate_tool_manifest.json"))
    assert G.write_event("g3b_open")["outcome"] == G.EVENT_REQUIREMENT_NOT_COMMITTED
    commit_files(tree, gate_file("g3a_record.json"))
    (FP.gate_dir() / "gate_tool_manifest.json").write_text('{"edited": true}\n')
    assert G.write_event("g3b_open")["outcome"] == G.EVENT_ARTIFACT_NOT_COMMITTED


def test_an_event_is_written_once(tree):
    ready(tree)
    open_event(tree, "g3b_open")
    assert G.write_event("g3b_open")["outcome"] == G.EVENT_EXISTS_REFUSING_OVERWRITE


def test_an_event_needs_a_valid_predecessor(tree):
    ready(tree)
    commit_files(tree, gate_file("g6_record.json"), gate_file("g7a_record.json"),
                 gate_file("etransfer_admitted_set.json", PAYLOADS["etransfer_admitted_set.json"]))
    assert G.write_event("g7b_open")["outcome"] == G.EVENT_PREDECESSOR_NOT_VALID


def test_an_empty_admitted_set_opens_nothing(tree):
    ready(tree)
    open_event(tree, "g3b_open")
    commit_files(tree, gate_file("g6_record.json"), gate_file("g7a_record.json"),
                 gate_file("etransfer_admitted_set.json", {"admitted": []}))
    assert G.write_event("g7b_open")["outcome"] == G.EVENT_ADMITTED_SET_EMPTY


def test_withdrawing_every_admitted_task_opens_nothing(tree):
    ready(tree)
    open_event(tree, "g3b_open")
    open_event(tree, "g7b_open")
    commit_files(tree, gate_file("g7b_record.json"),
                 gate_file("etransfer_withdrawals.json", {"withdrawn": ["aaaa1111", "bbbb2222"]}))
    assert G.write_event("g8_open")["outcome"] == G.EVENT_ADMITTED_SET_EMPTY


def test_the_firewall_needs_stage_seven_and_the_g7b_event(tree):
    ready(tree)
    open_event(tree, "g3b_open")
    with pytest.raises(SealedAccessError):
        GateGuard(Stage.CAPABILITY_GROWTH_WITNESS).check(tree.p["firewall"])
    with pytest.raises(SealedAccessError, match="g7b_open"):
        GateGuard(Stage.E_TRANSFER_EVALUATION).check(tree.p["firewall"])
    open_event(tree, "g7b_open")
    GateGuard(Stage.E_TRANSFER_EVALUATION).check(tree.p["firewall"])
    GateGuard(Stage.E_TRANSFER_EVALUATION).check(tree.p["extract_promotion"])


def test_e_transfer_needs_stage_eight_and_the_g8_event(tree):
    ready(tree)
    open_event(tree, "g3b_open")
    open_event(tree, "g7b_open")
    with pytest.raises(SealedAccessError):
        GateGuard(Stage.E_TRANSFER_EVALUATION).check(tree.p["extract_etransfer"])
    with pytest.raises(SealedAccessError, match="g8_open"):
        GateGuard(Stage.E_TRANSFER_MEASUREMENT).check(tree.p["extract_etransfer"])
    open_event(tree, "g8_open")
    GateGuard(Stage.E_TRANSFER_MEASUREMENT).check(tree.p["extract_etransfer"])


def test_e_transfer_closes_after_its_single_pass(tree):
    ready(tree)
    for event in ("g3b_open", "g7b_open", "g8_open", "g8_closed"):
        open_event(tree, event)
    with pytest.raises(SealedAccessError, match="closed"):
        GateGuard(Stage.E_TRANSFER_MEASUREMENT).check(tree.p["extract_etransfer"])


def test_an_admitted_set_rewritten_after_its_event_stops_the_gate(tree):
    ready(tree)
    open_event(tree, "g3b_open")
    open_event(tree, "g7b_open")
    commit_files(tree, gate_file("etransfer_admitted_set.json", {"admitted": ["aaaa1111", "zzzz9999"]}),
                 message="rewrite admitted set")
    with pytest.raises(PinProvenanceError) as err:
        GateGuard(Stage.E_TRANSFER_EVALUATION).check(tree.p["firewall"])
    assert err.value.status == G.EVENT_ARTIFACT_DRIFT


def test_a_rewritten_event_stops_the_gate(tree):
    ready(tree)
    open_event(tree, "g3b_open")
    event = FP.gate_dir() / "event_g3b_open.json"
    record = json.loads(event.read_text())
    record["created_utc"] = "1970-01-01T00:00:00Z"
    event.write_text(json.dumps(record) + "\n")
    commit_files(tree, event, message="rewrite event")
    with pytest.raises(PinProvenanceError) as err:
        GateGuard(Stage.INSPECT_RETAINED_PRODUCTIONS).check(tree.p["inventory"])
    assert err.value.status == G.EVENT_REWRITTEN


def test_raw_training_data_is_never_readable_for_content(tree):
    ready(tree)
    for event in ("g3b_open", "g7b_open", "g8_open"):
        open_event(tree, event)
    for stage in Stage:
        if stage is Stage.GATE_COMPLETE:
            continue
        with pytest.raises(SealedAccessError):
            GateGuard(stage, require_pin=stage > Stage.PIN_PROTOCOL_HASHES).check(tree.p["train_flat"])


def test_lockbox_needs_the_committed_completion_event(tree):
    ready(tree)
    with pytest.raises(SealedAccessError):
        GateGuard(Stage.POST_PROMOTION_ANALYSIS).check(tree.p["lockbox"])
    with pytest.raises(SealedAccessError, match="g11_complete"):
        GateGuard(Stage.GATE_COMPLETE).check(tree.p["lockbox"])
    for event in FULL_CHAIN:
        open_event(tree, event)
    GateGuard(Stage.GATE_COMPLETE).check(tree.p["lockbox"])


def test_the_journal_and_the_seal_are_refused_even_after_completion(tree):
    ready(tree)
    for event in FULL_CHAIN:
        open_event(tree, event)
    guard = GateGuard(Stage.GATE_COMPLETE)
    for key in ("journal", "seal"):
        with pytest.raises(SealedAccessError, match="NEVER"):
            guard.check(tree.p[key])


def test_worktree_copies_are_refused_at_every_stage(tree):
    ready(tree)
    open_event(tree, "g3b_open")
    for stage in (Stage.INSPECT_RETAINED_PRODUCTIONS, Stage.GATE_COMPLETE):
        with pytest.raises(SealedAccessError):
            GateGuard(stage).check(tree.p["tti_inventory_copy"])


#  ------------------------------------------------------ filtered extraction

def test_promotion_extraction_returns_licensed_tasks_only(tree):
    ready(tree)
    open_event(tree, "g3b_open")
    open_event(tree, "g7b_open")
    guard = GateGuard(Stage.E_TRANSFER_EVALUATION)
    result = guard.extract(tree.p["train_flat"], "promotion", keys=["aaaa1111"])
    assert list(result["members"]) == ["aaaa1111"] and result["skipped"] == 2
    assert SENTINEL not in json.dumps(result)
    assert guard.ledger[-1].access_mode == "FILTERED_EXTRACT" and guard.ledger[-1].permitted


def test_the_lockbox_manifest_yields_only_the_declared_path(tree):
    ready(tree)
    open_event(tree, "g3b_open")
    open_event(tree, "g7b_open")
    result = GateGuard(Stage.E_TRANSFER_EVALUATION).extract(
        tree.p["lockbox"], "promotion", key_path=["splits", "promotion"])
    assert result == {"value": ["aaaa1111"], "skipped": 1}


def test_extraction_is_refused_before_its_event_and_at_the_wrong_stage(tree):
    ready(tree)
    open_event(tree, "g3b_open")
    with pytest.raises(SealedAccessError, match="g7b_open"):
        GateGuard(Stage.E_TRANSFER_EVALUATION).extract(tree.p["train_flat"], "promotion", keys=["aaaa1111"])
    with pytest.raises(SealedAccessError, match="stage 7"):
        GateGuard(Stage.E_TRANSFER_MEASUREMENT).extract(tree.p["train_flat"], "promotion", keys=["aaaa1111"])


def test_extraction_applies_only_to_raw_data_and_the_lockbox_manifest(tree):
    ready(tree)
    open_event(tree, "g3b_open")
    open_event(tree, "g7b_open")
    with pytest.raises(SealedAccessError, match="raw ARC data"):
        GateGuard(Stage.E_TRANSFER_EVALUATION).extract(tree.p["inventory"], "promotion", keys=["x"])


def test_e_transfer_extraction_closes_with_the_pass(tree):
    ready(tree)
    for event in ("g3b_open", "g7b_open", "g8_open"):
        open_event(tree, event)
    guard = GateGuard(Stage.E_TRANSFER_MEASUREMENT)
    assert list(guard.extract(tree.p["train_flat"], "etransfer", keys=["aaaa1111"])["members"]) == ["aaaa1111"]
    open_event(tree, "g8_closed")
    with pytest.raises(SealedAccessError, match="closed"):
        guard.extract(tree.p["train_flat"], "etransfer", keys=["aaaa1111"])


#  ------------------------------------------------------------ hash-only

def test_hash_only_is_licensed_at_stage_two_and_ledgered(tree):
    guard = GateGuard(Stage.PIN_PROTOCOL_HASHES)
    result = guard.hash_only(tree.p["lockbox"])
    assert result["sha256"] == hashlib.sha256(tree.p["lockbox"].read_bytes()).hexdigest()
    assert guard.ledger[-1].access_mode == "HASH_ONLY" and guard.ledger[-1].permitted


def test_hash_only_is_refused_outside_stages_two_and_eleven(tree):
    ready(tree)
    with pytest.raises(SealedAccessError):
        GateGuard(Stage.CLASSIFY_CLAIM_LEVEL).hash_only(tree.p["lockbox"])


def test_hash_only_never_touches_the_never_class_or_worktree_copies(tree):
    for key in ("journal", "tti_inventory_copy"):
        with pytest.raises(SealedAccessError):
            GateGuard(Stage.PIN_PROTOCOL_HASHES).hash_only(tree.p[key])


#  ------------------------------------------- provenance after the pin

def expect_provenance(status, stage=Stage.INSPECT_RETAINED_PRODUCTIONS):
    with pytest.raises(PinProvenanceError) as err:
        GateGuard(stage)
    assert err.value.status == status


def test_stage_three_without_a_pin_refuses(tree):
    expect_provenance(FP.PIN_MISSING)


def test_stage_three_without_a_committed_binding_refuses(tree):
    assert FP.create_pin()["outcome"] == FP.PIN_CREATED
    expect_provenance(FP.PIN_BINDING_MISSING)


def test_stage_three_without_the_module_pin_refuses(tree):
    ready(tree)
    FP.module_pin_path().unlink()
    expect_provenance(FP.MODULE_PIN_MISSING)


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
    expect_provenance(FP.PIN_ARTIFACT_DRIFT)


def test_a_pinned_artifact_deleted_after_the_pin_refuses_stage_three(tree):
    ready(tree)
    tree.p["corpus"].unlink()
    expect_provenance(FP.PIN_ARTIFACT_MISSING)


def test_a_modified_pin_json_refuses_stage_three(tree):
    ready(tree)
    data = json.loads(FP.pin_path().read_bytes())
    data["artifacts"].pop()
    FP.pin_path().write_text(json.dumps(data, indent=1, sort_keys=True))
    expect_provenance(FP.PIN_JSON_ALTERED)


def test_a_new_file_in_a_pinned_scope_refuses_stage_three(tree):
    ready(tree)
    (tree.b / "level4_stepB_gate_outputs" / "late.json").write_text("{}")
    expect_provenance(FP.PIN_SCOPE_GREW_AFTER_FREEZE)


def test_deleting_and_recreating_the_pin_refuses_stage_three(tree):
    ready(tree)
    shutil.rmtree(FP.pin_dir())
    assert FP.create_pin()["outcome"] == FP.PIN_CREATED
    expect_provenance(FP.PIN_COMMIT_MISMATCH)


def test_a_missing_anchor_refuses_stage_three(tree):
    ready(tree)
    FP.anchor_path().unlink()
    expect_provenance(FP.PIN_ANCHOR_MISSING)


def test_an_engine_change_after_g2_refuses_stage_three(tree):
    ready(tree)
    tree.p["engine"].write_text("# K changed in the dev worktree\n")
    expect_provenance(FP.MODULE_ARTIFACT_DRIFT)


def test_a_new_module_under_a_pinned_root_refuses_stage_three(tree):
    ready(tree)
    (tree.p["engine"].parent / "late_module.py").write_text("# added after G2\n")
    expect_provenance(FP.MODULE_SCOPE_CHANGED)


def test_drift_after_construction_is_caught_on_the_next_read(tree):
    ready(tree)
    guard = GateGuard(Stage.INSPECT_RETAINED_PRODUCTIONS)
    tree.p["runner"].write_text("# tampered\n")
    with pytest.raises(PinProvenanceError) as err:
        with guard.open(tree.p["runner"]):
            pass
    assert err.value.status == FP.PIN_ARTIFACT_DRIFT
    assert guard.ledger[-1].permitted is False and guard.ledger[-1].reason == FP.PIN_ARTIFACT_DRIFT


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
    assert path.parent == FP.gate_dir() and guard.ledger == []


def test_the_ledger_is_append_only(tree):
    ready(tree)
    guard = GateGuard(Stage.INSPECT_RETAINED_PRODUCTIONS)
    guard.permits(tree.p["runner"])
    path = guard.write_ledger()
    guard.permits(tree.p["runtime"])
    guard.write_ledger()
    assert len(path.read_text().splitlines()) == 2


#  ------------------------------------------------------ completion and extracts

def test_completion_cannot_be_declared_before_the_transfer_pass_closes(tree):
    ready(tree)
    commit_files(tree, gate_file("gate_completion_record.json"),
                 gate_file("lockbox_closure.json", PAYLOADS["lockbox_closure.json"]))
    assert G.write_event("g11_complete")["outcome"] == G.EVENT_PREDECESSOR_NOT_VALID
    with pytest.raises(SealedAccessError):
        GateGuard(Stage.GATE_COMPLETE).check(tree.p["lockbox"])


def test_completion_never_opens_lockbox_unless_eligible(tree):
    ready(tree)
    for event in FULL_CHAIN[:-1]:
        open_event(tree, event)
    commit_files(tree, gate_file("gate_completion_record.json"),
                 gate_file("lockbox_closure.json", {"outcome": "LOCKBOX-CLOSED"}))
    assert G.write_event("g11_complete")["outcome"] == G.EVENT_LOCKBOX_NOT_ELIGIBLE
    with pytest.raises(SealedAccessError):
        GateGuard(Stage.GATE_COMPLETE).check(tree.p["lockbox"])


def test_an_unrecognized_file_among_the_extracts_fails_closed(tree):
    extracts = tree.tti / "outputs" / "tti" / "stepB_gate" / "extracts"
    assert classify(extracts / "notes.json") is SealedClass.E_TRANSFER
    assert classify(tree.p["extract_promotion"]) is SealedClass.PROMOTION_DATA
    assert classify(tree.tti / "outputs" / "tti" / "stepB_gate" / "etransfer_results.jsonl") is None
