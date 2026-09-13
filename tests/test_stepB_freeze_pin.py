"""Tests for the Step-B freeze pin: cora_tti/freeze_pin.py and its command line.

The pin runs once, on a live experiment's outputs, at the one moment when an
error is unrecoverable, so its guarantees are tested on synthetic fixture trees
rather than trusted. No test here touches the live experiment tree.

What the content tests establish, and what they do not. The sentinel tests show
that no artifact content LEAKS into the pin, the printed output, or the returned
result. They do not show that bytes never entered a temporary hash buffer:
hashing reads bytes, which is the documented and permitted exception. The
open-mode test shows that artifacts are opened only in binary mode and that no
JSON decoder runs while the pin is built.
"""
from __future__ import annotations

import builtins
import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from cora_tti import freeze_pin as FP

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location("pin_stepB_freeze_cli",
                                               ROOT / "scripts" / "pin_stepB_freeze.py")
CLI = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(CLI)

SENTINELS = {
    "journal": "SENTINEL_JOURNAL_MUST_NOT_LEAK",
    "log": "SENTINEL_LOG_MUST_NOT_LEAK",
    "lane": "SENTINEL_LANE_MUST_NOT_LEAK",
    "corpus": "SENTINEL_CORPUS_MUST_NOT_LEAK",
    "firewall": "SENTINEL_FIREWALL_MUST_NOT_LEAK",
}


def make_tree(tmp_path, monkeypatch, *, frozen=True, output_hash=True):
    main, tti, proc = tmp_path / "main", tmp_path / "tti", tmp_path / "proc"
    b = main / "outputs" / "cora_breakthrough"
    for directory in (b / "level4_stepB_gate_outputs", b / "level4_mechanism_inputs",
                      main / "logs", main / "scripts", main / "level4_stepB" / "__pycache__",
                      main / "level4_blind_runtime", tti / "outputs" / "tti", proc):
        directory.mkdir(parents=True, exist_ok=True)
    files = {
        "journal": b / "level4_stepB_journal.jsonl",
        "manifest": b / "level4_stepB_run_manifest.json",
        "lane": b / "level4_stepB_gate_outputs" / "deta_output_hash.txt",
        "corpus": b / "level4_mechanism_inputs" / "invention_corpus.jsonl",
        "firewall": b / "level4_provenance_firewall.json",
        "runner": main / "scripts" / "cora_level4_stepB_run.py",
        "candidates": main / "level4_stepB" / "candidates.py",
        "pyc": main / "level4_stepB" / "__pycache__" / "candidates.cpython-312.pyc",
        "runtime": main / "level4_blind_runtime" / "search.py",
        "unrelated": b / "notes_unrelated.json",
    }
    files["journal"].write_text(json.dumps({"secret": SENTINELS["journal"]}) + "\n")
    files["manifest"].write_text('{"manifest": 1}')
    files["lane"].write_text(SENTINELS["lane"] + "\n")
    files["corpus"].write_text(json.dumps({"source_token": SENTINELS["corpus"]}) + "\n")
    files["firewall"].write_text(json.dumps({"ids": [SENTINELS["firewall"]]}))
    files["runner"].write_text("# runner\n")
    files["candidates"].write_text("# candidates\n")
    files["pyc"].write_bytes(b"\x00compiled")
    files["runtime"].write_text("MAX_DEPTH = 5\n")
    files["unrelated"].write_text("{}")
    log = main / "logs" / "level4_stepB_run.log"
    log.write_text(f"start\n{SENTINELS['log']}\n" + ("STEP B FROZEN\n" if frozen else ""))
    out_hash = b / "level4_stepB_output_hash.txt"
    if output_hash:
        out_hash.write_text("f" * 64 + "\n")
    monkeypatch.setattr(FP, "MAIN", main)
    monkeypatch.setattr(FP, "TTI", tti)
    monkeypatch.setattr(FP, "PROC", proc)
    return SimpleNamespace(root=tmp_path, main=main, tti=tti, proc=proc, b=b, log=log,
                           out_hash=out_hash, files=files)


@pytest.fixture
def tree(tmp_path, monkeypatch):
    return make_tree(tmp_path, monkeypatch)


@pytest.fixture
def pinned(tree):
    assert FP.create_pin()["outcome"] == FP.PIN_CREATED
    return tree


def fake_process(tree, pid, argv, cwd=None):
    entry = tree.proc / str(pid)
    entry.mkdir()
    (entry / "cmdline").write_bytes(b"\0".join(a.encode() for a in argv) + b"\0")
    if cwd is not None:
        os.symlink(cwd, entry / "cwd")


#  ------------------------------------------------------------- readiness

def test_refuses_without_the_freeze_marker(tmp_path, monkeypatch):
    make_tree(tmp_path, monkeypatch, frozen=False)
    assert FP.create_pin()["outcome"] == FP.FREEZE_MARKER_ABSENT
    assert not FP.pin_path().exists()


def test_marker_without_the_final_output_hash_is_not_ready(tmp_path, monkeypatch):
    make_tree(tmp_path, monkeypatch, output_hash=False)

    def forbidden(*args, **kwargs):
        raise AssertionError("nothing may be hashed before readiness holds")
    monkeypatch.setattr(FP, "digest_and_lines", forbidden)
    result = FP.create_pin()
    assert result["outcome"] == FP.FREEZE_OUTPUT_NOT_READY
    assert result["readiness"]["marker_occurrences"] == 1
    assert result["readiness"]["final_output_hash_present"] is False
    assert not FP.pin_path().exists()


def test_output_hash_without_the_marker_is_still_not_frozen(tmp_path, monkeypatch):
    make_tree(tmp_path, monkeypatch, frozen=False, output_hash=True)
    assert FP.create_pin()["outcome"] == FP.FREEZE_MARKER_ABSENT


def test_a_live_runner_in_this_checkout_blocks_the_pin(tree):
    fake_process(tree, 4242, ["python3", "scripts/cora_level4_stepB_run.py", "--workers", "20"],
                 cwd=tree.main)
    result = FP.create_pin()
    assert result["outcome"] == FP.FREEZE_RUNNER_STILL_ACTIVE
    assert result["readiness"]["runner_pids"] == [4242]
    assert not FP.pin_path().exists()


def test_an_absolute_runner_path_inside_this_checkout_blocks(tree):
    fake_process(tree, 77, ["/usr/bin/python3.12",
                            str(tree.main / "scripts" / "cora_level4_stepB_run.py")], cwd=tree.tti)
    assert FP.readiness().status == FP.FREEZE_RUNNER_STILL_ACTIVE


def test_a_runner_from_another_checkout_does_not_block(tree):
    elsewhere = tree.root / "another_checkout"
    elsewhere.mkdir()
    fake_process(tree, 4243, ["python3", "scripts/cora_level4_stepB_run.py"], cwd=elsewhere)
    assert FP.create_pin()["outcome"] == FP.PIN_CREATED


def test_a_non_python_process_naming_the_runner_does_not_block(tree):
    fake_process(tree, 4244, ["pgrep", "-cf", "cora_level4_stepB_run.py"], cwd=tree.main)
    assert FP.readiness().status == FP.READY


def test_a_runner_whose_cwd_cannot_be_read_counts_as_live(tree):
    fake_process(tree, 4245, ["python3", "scripts/cora_level4_stepB_run.py"], cwd=None)
    assert FP.readiness().status == FP.FREEZE_RUNNER_STILL_ACTIVE


#  ---------------------------------------------------------------- creation

def test_pins_when_ready_and_verifies_immediately(tree):
    result = FP.create_pin()
    assert result["outcome"] == FP.PIN_CREATED
    assert result["verification"]["outcome"] == FP.PIN_VERIFIED
    pin = json.loads(FP.pin_path().read_bytes())
    relative = {r["relative_to_main"] for r in pin["artifacts"]}
    for expected in ("outputs/cora_breakthrough/level4_stepB_output_hash.txt",
                     "outputs/cora_breakthrough/level4_stepB_gate_outputs/deta_output_hash.txt",
                     "outputs/cora_breakthrough/level4_mechanism_inputs/invention_corpus.jsonl",
                     "outputs/cora_breakthrough/level4_provenance_firewall.json",
                     "scripts/cora_level4_stepB_run.py", "level4_stepB/candidates.py",
                     "level4_blind_runtime/search.py", "logs/level4_stepB_run.log"):
        assert expected in relative, expected
    assert not any("__pycache__" in r for r in relative)
    assert "outputs/cora_breakthrough/notes_unrelated.json" not in relative
    assert pin["readiness"]["status"] == FP.READY
    assert pin["pin_version"] == FP.PIN_VERSION
    assert "never parsed" in pin["content_policy"]


def test_refuses_to_overwrite_an_existing_pin(pinned):
    before = FP.pin_path().read_bytes()
    assert FP.create_pin()["outcome"] == FP.PIN_EXISTS_REFUSING_OVERWRITE
    assert FP.pin_path().read_bytes() == before


def test_an_artifact_set_that_changes_during_pinning_writes_nothing(tree, monkeypatch):
    real, count, calls = FP.describe, len(FP.scope_files()), {"n": 0}

    def flaky(path):
        calls["n"] += 1
        record = real(path)
        return dict(record, sha256="0" * 64) if calls["n"] > count else record
    monkeypatch.setattr(FP, "describe", flaky)
    assert FP.create_pin()["outcome"] == FP.PIN_SOURCE_UNSTABLE
    assert not FP.pin_path().exists()


#  ---------------------------------------------------------- content policy

def test_no_content_leaks_into_the_pin_or_the_printed_output(tree, capsys):
    assert CLI.main([]) == 0
    out = capsys.readouterr().out
    assert out.splitlines()[0] == f"OUTCOME {FP.PIN_CREATED}"
    pin_text = FP.pin_path().read_text()
    for sentinel in SENTINELS.values():
        assert sentinel not in pin_text
        assert sentinel not in out


def test_no_content_leaks_into_the_returned_result(tree):
    blob = json.dumps(FP.create_pin(), default=str)
    for sentinel in SENTINELS.values():
        assert sentinel not in blob


def test_artifacts_are_opened_only_in_binary_mode_and_never_decoded(tree, monkeypatch):
    opened, real_open = [], builtins.open

    def recording_open(file, mode="r", *args, **kwargs):
        opened.append((str(file), mode))
        return real_open(file, mode, *args, **kwargs)

    def no_decode(*args, **kwargs):
        raise AssertionError("no JSON decoding may happen while the pin is built")
    monkeypatch.setattr(FP, "open", recording_open, raising=False)
    monkeypatch.setattr(FP.json, "loads", no_decode)
    monkeypatch.setattr(FP.json, "load", no_decode)
    FP.build_pin(FP.readiness())
    main = str(tree.main.resolve())
    artifact_opens = [(f, m) for f, m in opened if f.startswith(main)]
    assert artifact_opens, "the build must have read the artifacts to hash them"
    assert {m for _, m in artifact_opens} == {"rb"}


#  ----------------------------------------------------------------- dry run

def test_dry_run_is_refused_on_the_live_tree_before_anything_is_read(monkeypatch, capsys):
    monkeypatch.setattr(FP, "MAIN", FP.LIVE_MAIN)

    def forbidden(*args, **kwargs):
        raise AssertionError("the live tree must not be read")
    for name in ("digest_and_lines", "readiness", "scope_files", "build_pin"):
        monkeypatch.setattr(FP, name, forbidden)
    for flag in ("--dry-run", "--allow-unfrozen"):
        assert CLI.main([flag]) == FP.EXIT_CODES[FP.DRY_RUN_REFUSED_ON_LIVE_TREE]
        assert capsys.readouterr().out.splitlines()[0] == f"OUTCOME {FP.DRY_RUN_REFUSED_ON_LIVE_TREE}"


def test_dry_run_on_a_fixture_writes_nothing(tree):
    result = FP.dry_run()
    assert result["outcome"] == FP.DRY_RUN_OK and result["stable"] is True
    assert not FP.pin_path().exists()


#  ------------------------------------------------------------ verification

def test_verify_passes_on_an_untouched_set(pinned):
    assert FP.verify_pin().status == FP.PIN_VERIFIED


def test_verify_without_a_pin(tree):
    assert FP.verify_pin().status == FP.PIN_MISSING


def test_verify_detects_content_drift(pinned):
    pinned.files["manifest"].write_text('{"manifest": 2}')
    result = FP.verify_pin()
    assert result.status == FP.PIN_ARTIFACT_DRIFT
    assert any(p.endswith("level4_stepB_run_manifest.json") for p in result.drifted)


def test_verify_detects_deletion(pinned):
    pinned.files["lane"].unlink()
    assert FP.verify_pin().status == FP.PIN_ARTIFACT_MISSING


def test_verify_detects_an_altered_pin(pinned):
    pin = json.loads(FP.pin_path().read_bytes())
    pin["artifacts"] = pin["artifacts"][1:]
    FP.pin_path().write_text(json.dumps(pin, indent=1, sort_keys=True))
    assert FP.verify_pin().status == FP.PIN_JSON_ALTERED


def test_verify_detects_a_missing_hash_record(pinned):
    FP.pin_hash_path().unlink()
    assert FP.verify_pin().status == FP.PIN_HASH_RECORD_MISSING


def test_run_log_growth_after_the_pin_is_drift(pinned):
    with pinned.log.open("a") as handle:
        handle.write("a late line\n")
    assert FP.verify_pin().status == FP.PIN_ARTIFACT_DRIFT


@pytest.mark.parametrize("where", ["gate_outputs", "top_level", "mechanism_inputs",
                                   "blind_runtime", "stepB_source"])
def test_a_file_appearing_in_a_pinned_scope_fails_closed(pinned, where):
    target = {
        "gate_outputs": pinned.b / "level4_stepB_gate_outputs" / "late_result.json",
        "top_level": pinned.b / "level4_stepB_late_artifact.json",
        "mechanism_inputs": pinned.b / "level4_mechanism_inputs" / "extra.jsonl",
        "blind_runtime": pinned.main / "level4_blind_runtime" / "late.py",
        "stepB_source": pinned.main / "level4_stepB" / "late.py",
    }[where]
    target.write_text("{}")
    result = FP.verify_pin()
    assert result.status == FP.PIN_SCOPE_GREW_AFTER_FREEZE
    assert str(target.resolve()) in result.appeared


def test_bytecode_caches_and_unrelated_files_are_not_growth(pinned):
    (pinned.main / "level4_stepB" / "__pycache__" / "late.cpython-312.pyc").write_bytes(b"x")
    (pinned.b / "another_unrelated.json").write_text("{}")
    assert FP.verify_pin().status == FP.PIN_VERIFIED


def test_cli_verify_reports_outcome_and_fixed_exit_code(pinned, capsys):
    pinned.files["runner"].write_text("# edited\n")
    assert CLI.main(["--verify"]) == FP.EXIT_CODES[FP.PIN_ARTIFACT_DRIFT]
    assert capsys.readouterr().out.splitlines()[0] == f"OUTCOME {FP.PIN_ARTIFACT_DRIFT}"


def test_every_outcome_has_a_fixed_exit_code():
    outcomes = [v for k, v in vars(FP).items()
                if isinstance(v, str) and k == v and k.isupper() and k != FP.READY]
    assert len(outcomes) >= 15
    for name in outcomes:
        assert name in FP.EXIT_CODES, name


def test_freeze_marker_counting(tree):
    assert FP.freeze_marker_occurrences() == 1
    with tree.log.open("a") as handle:
        handle.write("STEP B FROZEN again\n")
    assert FP.freeze_marker_occurrences() == 2
