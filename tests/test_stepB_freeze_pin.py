"""Tests for the Step-B freeze pin.

The pin runs once, on a live experiment's outputs, at the single moment when
getting it wrong is unrecoverable. So its guarantees are tested here rather than
trusted:

  * it refuses to pin an unfrozen run
  * it refuses to overwrite an existing pin
  * `--verify` detects content drift, deletion, and tampering with the pin itself
  * and, the invariant that matters most, IT NEVER CAPTURES FILE CONTENT

The content test uses sentinel strings. If any byte of an artifact's content
reached the pin, the sentinel would appear in the pin JSON. This is the
mechanical check that reading the Step-B outputs to hash them cannot leak their
semantics into an artifact that gets read later.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "pin_stepB_freeze", ROOT / "scripts" / "pin_stepB_freeze.py")
PIN_MOD = importlib.util.module_from_spec(SPEC)
sys.modules["pin_stepB_freeze"] = PIN_MOD
SPEC.loader.exec_module(PIN_MOD)

SENTINEL_JOURNAL = "SENTINEL_JOURNAL_SEMANTIC_CONTENT_MUST_NOT_LEAK"
SENTINEL_LOG = "SENTINEL_LOG_LINE_MUST_NOT_LEAK"
SENTINEL_TREE = "SENTINEL_TREE_FILE_MUST_NOT_LEAK"


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """A fake experiment tree with the same shape as the real one."""
    main = tmp_path / "main"
    breakthrough = main / "outputs" / "cora_breakthrough"
    tree = breakthrough / "level4_stepB_gate_outputs"
    logs = main / "logs"
    for directory in (breakthrough, tree, logs):
        directory.mkdir(parents=True, exist_ok=True)

    run_log = logs / "level4_stepB_run.log"
    run_log.write_text(f"starting\n{SENTINEL_LOG}\nphase propose K2 1/2\n")
    (breakthrough / "level4_stepB_journal.jsonl").write_text(
        json.dumps({"secret": SENTINEL_JOURNAL}) + "\n")
    (breakthrough / "level4_stepB_run_manifest.json").write_text('{"manifest": 1}')
    (tree / "deta_output_hash.txt").write_text(SENTINEL_TREE + "\n")

    outdir = tmp_path / "gate"
    monkeypatch.setattr(PIN_MOD, "MAIN", main)
    monkeypatch.setattr(PIN_MOD, "BREAKTHROUGH", breakthrough)
    monkeypatch.setattr(PIN_MOD, "RUN_LOG", run_log)
    monkeypatch.setattr(PIN_MOD, "PINNED_PATHS", [run_log])
    monkeypatch.setattr(PIN_MOD, "PINNED_GLOBS", [(breakthrough, "level4_stepB*")])
    monkeypatch.setattr(PIN_MOD, "PINNED_TREES", [tree])
    monkeypatch.setattr(PIN_MOD, "OUTDIR", outdir)
    monkeypatch.setattr(PIN_MOD, "PIN", outdir / "stepB_freeze_pin.json")
    monkeypatch.setattr(PIN_MOD, "PIN_HASH", outdir / "stepB_freeze_pin_hash.txt")
    return {"main": main, "breakthrough": breakthrough, "tree": tree,
            "run_log": run_log, "outdir": outdir}


def freeze(sandbox):
    with sandbox["run_log"].open("a") as handle:
        handle.write("STEP B FROZEN\n")


#  ---------------------------------------------------------------- refusals

def test_refuses_to_pin_an_unfrozen_run(sandbox, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["pin"])
    assert PIN_MOD.main() == 1
    assert not PIN_MOD.PIN.exists(), "an unfrozen run must leave no pin behind"


def test_dry_run_writes_nothing(sandbox, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["pin", "--allow-unfrozen"])
    assert PIN_MOD.main() == 0
    assert not PIN_MOD.PIN.exists()


def test_verify_without_a_pin_is_an_error(sandbox, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["pin", "--verify"])
    assert PIN_MOD.main() == 2


def test_refuses_to_overwrite_an_existing_pin(sandbox, monkeypatch):
    freeze(sandbox)
    monkeypatch.setattr(sys, "argv", ["pin"])
    assert PIN_MOD.main() == 0
    first = PIN_MOD.PIN.read_text()
    assert PIN_MOD.main() == 5, "the pin is immutable"
    assert PIN_MOD.PIN.read_text() == first


#  ------------------------------------------------------ the content invariant

def test_pin_never_captures_file_content(sandbox, monkeypatch):
    freeze(sandbox)
    monkeypatch.setattr(sys, "argv", ["pin"])
    assert PIN_MOD.main() == 0
    text = PIN_MOD.PIN.read_text()
    for sentinel in (SENTINEL_JOURNAL, SENTINEL_LOG, SENTINEL_TREE):
        assert sentinel not in text, f"{sentinel} leaked into the pin"


def test_pin_records_quantities_not_semantics(sandbox, monkeypatch):
    freeze(sandbox)
    monkeypatch.setattr(sys, "argv", ["pin"])
    PIN_MOD.main()
    pin = json.loads(PIN_MOD.PIN.read_text())
    assert pin["content_inspected"] is False
    allowed = {"path", "relative_to_main", "sha256", "bytes", "mtime_utc", "lines"}
    for record in pin["artifacts"]:
        assert set(record) <= allowed, f"unexpected field in {record['path']}"
    journal = next(r for r in pin["artifacts"] if r["path"].endswith("journal.jsonl"))
    assert journal["lines"] == 1


def test_tree_is_walked_recursively(sandbox, monkeypatch):
    freeze(sandbox)
    monkeypatch.setattr(sys, "argv", ["pin"])
    PIN_MOD.main()
    pin = json.loads(PIN_MOD.PIN.read_text())
    paths = {r["relative_to_main"] for r in pin["artifacts"]}
    assert any("deta_output_hash.txt" in p for p in paths), \
        "the determinism lanes live in a subdirectory and must be pinned"


#  ------------------------------------------------------------------- verify

def test_verify_passes_on_an_untouched_tree(sandbox, monkeypatch):
    freeze(sandbox)
    monkeypatch.setattr(sys, "argv", ["pin"])
    PIN_MOD.main()
    monkeypatch.setattr(sys, "argv", ["pin", "--verify"])
    assert PIN_MOD.main() == 0


def test_verify_detects_content_drift(sandbox, monkeypatch):
    freeze(sandbox)
    monkeypatch.setattr(sys, "argv", ["pin"])
    PIN_MOD.main()
    (sandbox["breakthrough"] / "level4_stepB_run_manifest.json").write_text('{"manifest": 2}')
    monkeypatch.setattr(sys, "argv", ["pin", "--verify"])
    assert PIN_MOD.main() == 4


def test_verify_detects_deletion(sandbox, monkeypatch):
    freeze(sandbox)
    monkeypatch.setattr(sys, "argv", ["pin"])
    PIN_MOD.main()
    (sandbox["tree"] / "deta_output_hash.txt").unlink()
    monkeypatch.setattr(sys, "argv", ["pin", "--verify"])
    assert PIN_MOD.main() == 4


def test_verify_detects_tampering_with_the_pin_itself(sandbox, monkeypatch):
    freeze(sandbox)
    monkeypatch.setattr(sys, "argv", ["pin"])
    PIN_MOD.main()
    pin = json.loads(PIN_MOD.PIN.read_text())
    pin["artifacts"] = pin["artifacts"][:1]
    PIN_MOD.PIN.write_text(json.dumps(pin, indent=1, sort_keys=True))
    monkeypatch.setattr(sys, "argv", ["pin", "--verify"])
    assert PIN_MOD.main() == 3


def test_verify_reports_but_does_not_fail_on_new_files(sandbox, monkeypatch, capsys):
    """A file appearing after the pin is reported, not silently absorbed."""
    freeze(sandbox)
    monkeypatch.setattr(sys, "argv", ["pin"])
    PIN_MOD.main()
    (sandbox["breakthrough"] / "level4_stepB_late_artifact.json").write_text("{}")
    monkeypatch.setattr(sys, "argv", ["pin", "--verify"])
    assert PIN_MOD.main() == 0
    assert "not covered by the pin" in capsys.readouterr().out


#  ------------------------------------------------------------- freeze marker

def test_freeze_marker_detection(sandbox):
    present, count = PIN_MOD.freeze_marker_present()
    assert present is False and count == 0
    freeze(sandbox)
    present, count = PIN_MOD.freeze_marker_present()
    assert present is True and count == 1
