"""Tests for scripts/gate_capture_run_env.py, against a fake /proc only.

The security property matters most: a value that is not on the allowlist must
never reach the record or the printed output.
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from cora_tti import freeze_pin as FP

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location("gate_capture_run_env",
                                               ROOT / "scripts" / "gate_capture_run_env.py")
CAP = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(CAP)

SECRET = "supersecretvalue-must-not-leak"
ENVIRON = b"\x00".join([b"PYTHONHASHSEED=0", b"OMP_NUM_THREADS=1",
                        b"SECRET_API_TOKEN=" + SECRET.encode(), b"ARC_META_BUDGET_S=8.0",
                        b"HOME=/home/someone"]) + b"\x00"


@pytest.fixture
def world(tmp_path, monkeypatch):
    main, tti, proc = tmp_path / "main", tmp_path / "tti", tmp_path / "proc"
    for directory in (main, tti, proc):
        directory.mkdir()
    monkeypatch.setattr(FP, "MAIN", main)
    monkeypatch.setattr(FP, "TTI", tti)
    monkeypatch.setattr(FP, "PROC", proc)
    return SimpleNamespace(main=main, tti=tti, proc=proc)


def fake_runner(world, pid, environ=ENVIRON, readable=True):
    entry = world.proc / str(pid)
    entry.mkdir()
    argv = [b"python3", b"scripts/cora_level4_stepB_run.py", b"--workers", b"20"]
    (entry / "cmdline").write_bytes(b"\x00".join(argv) + b"\x00")
    os.symlink(world.main, entry / "cwd")
    (entry / "stat").write_text(
        f"{pid} (python3) S 1 1 1 0 -1 4194560 0 0 0 0 0 0 0 0 20 0 21 0 123456 0 0")
    if readable:
        (entry / "environ").write_bytes(environ)


def test_values_only_for_the_allowlist_and_names_for_everything_else(world):
    fake_runner(world, 501)
    assert CAP.capture()["outcome"] == CAP.ENV_CAPTURED
    text = CAP.record_path().read_text()
    assert SECRET not in text
    record = json.loads(text)
    (environment,) = record["environments"].values()
    assert environment["values"] == {"ARC_META_BUDGET_S": "8.0", "OMP_NUM_THREADS": "1",
                                     "PYTHONHASHSEED": "0"}
    assert environment["other_variable_count"] == 2
    assert "SECRET_API_TOKEN" not in text and "HOME" not in text
    assert record["processes"][0]["start_ticks"] == 123456
    assert record["runner_pids"] == [501]


def test_identical_worker_environments_are_stored_once(world):
    fake_runner(world, 501)
    fake_runner(world, 502)
    assert CAP.capture()["distinct_environments"] == 1
    assert len(json.loads(CAP.record_path().read_text())["processes"]) == 2


def test_no_runner_is_recorded_as_unknown(world):
    assert CAP.capture()["outcome"] == CAP.ENV_RUN_UNKNOWN
    assert json.loads(CAP.record_path().read_text())["outcome"] == CAP.ENV_RUN_UNKNOWN


def test_an_unreadable_environment_is_partial(world):
    fake_runner(world, 503, readable=False)
    assert CAP.capture()["outcome"] == CAP.ENV_CAPTURE_PARTIAL


def test_the_record_is_never_overwritten(world):
    fake_runner(world, 501)
    CAP.capture()
    before = CAP.record_path().read_bytes()
    assert CAP.capture()["outcome"] == CAP.ENV_CAPTURE_EXISTS
    assert CAP.record_path().read_bytes() == before


def test_the_printed_summary_carries_no_values(world, capsys):
    fake_runner(world, 501)
    assert CAP.main() == 0
    out = capsys.readouterr().out
    assert out.splitlines()[0] == f"OUTCOME {CAP.ENV_CAPTURED}"
    assert SECRET not in out and "PYTHONHASHSEED" not in out


def test_caveats_are_derived_from_a_record_only():
    seeded_values = {"PYTHONHASHSEED": "0", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
                     "OPENBLAS_NUM_THREADS": "1"}
    unset = {"outcome": CAP.ENV_CAPTURED, "environments": {"h": {"values": {"LANG": "C"}}}}
    assert CAP.run_env_caveats(unset) == [CAP.ENV_HASHSEED_UNSET_AT_RUN, CAP.ENV_THREADS_UNSET_AT_RUN]
    seeded = {"outcome": CAP.ENV_CAPTURED, "environments": {"h": {"values": seeded_values}}}
    assert CAP.run_env_caveats(seeded) == []
    randomized = {"outcome": CAP.ENV_CAPTURED,
                  "environments": {"h": {"values": dict(seeded_values, PYTHONHASHSEED="random")}}}
    assert CAP.run_env_caveats(randomized) == [CAP.ENV_HASHSEED_UNSET_AT_RUN]
    assert CAP.run_env_caveats(dict(seeded, outcome=CAP.ENV_CAPTURE_PARTIAL)) == [CAP.ENV_CAPTURE_PARTIAL]
    assert CAP.run_env_caveats({"outcome": CAP.ENV_RUN_UNKNOWN, "environments": {}}) == [CAP.ENV_RUN_UNKNOWN]


def test_the_committed_capture_yields_the_recorded_caveats():
    record_file = Path(__file__).resolve().parents[1] / "outputs" / "tti" / "stepB_gate" / "stepB_run_env.json"
    if not record_file.is_file():
        pytest.skip("no committed capture in this checkout")
    caveats = CAP.run_env_caveats(json.loads(record_file.read_text()))
    assert caveats == [CAP.ENV_HASHSEED_UNSET_AT_RUN, CAP.ENV_THREADS_UNSET_AT_RUN]
