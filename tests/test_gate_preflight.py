"""Tests for scripts/gate_preflight.py, on synthetic repositories only."""
from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from cora_tti import freeze_pin as FP

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location("gate_preflight", ROOT / "scripts" / "gate_preflight.py")
PF = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(PF)

GIT = ["git", "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid",
       "-c", "commit.gpgsign=false", "-c", "init.defaultBranch=main"]
GOOD = {"PYTHONHASHSEED": "0", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1"}


def run_git(repo, *args):
    return subprocess.run([*GIT, "-C", str(repo), *args], check=True,
                          capture_output=True, text=True).stdout


@pytest.fixture
def repo(tmp_path, monkeypatch):
    main, tti = tmp_path / "main", tmp_path / "tti"
    main.mkdir()
    for relative in PF.TOOLING:
        path = tti / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# {relative}\n")
    run_git(tti, "init", "-q")
    run_git(tti, "add", "-A")
    run_git(tti, "commit", "-q", "-m", "tooling")
    monkeypatch.setattr(FP, "MAIN", main)
    monkeypatch.setattr(FP, "TTI", tti)
    return SimpleNamespace(main=main, tti=tti)


def test_a_clean_committed_seeded_environment_passes(repo):
    assert PF.run(env=dict(GOOD))["outcome"] == PF.PREFLIGHT_OK


@pytest.mark.parametrize("seed", [None, "1", "random"])
def test_the_hash_seed_must_be_zero(repo, seed):
    env = dict(GOOD)
    if seed is None:
        env.pop("PYTHONHASHSEED")
    else:
        env["PYTHONHASHSEED"] = seed
    assert PF.run(env=env)["outcome"] == PF.PREFLIGHT_HASHSEED


def test_thread_limits_are_required(repo):
    env = dict(GOOD)
    env.pop("MKL_NUM_THREADS")
    assert PF.run(env=env)["outcome"] == PF.PREFLIGHT_THREADS


def test_modified_tooling_is_refused_and_named(repo):
    (repo.tti / "cora_tti" / "freeze_pin.py").write_text("# edited after commit\n")
    result = PF.run(env=dict(GOOD))
    assert result["outcome"] == PF.PREFLIGHT_UNCOMMITTED_TOOLING
    assert result["uncommitted"] == ["cora_tti/freeze_pin.py"]


def test_an_untracked_file_makes_the_worktree_dirty(repo):
    (repo.tti / "notes.txt").write_text("scratch\n")
    assert PF.run(env=dict(GOOD))["outcome"] == PF.PREFLIGHT_DIRTY_WORKTREE


def test_the_main_checkout_is_recorded_but_not_required_clean(repo):
    run_git(repo.main, "init", "-q")
    (repo.main / "untracked.txt").write_text("x\n")
    result = PF.run(env=dict(GOOD))
    assert result["outcome"] == PF.PREFLIGHT_OK
    assert result["main"]["dirty_file_count"] == 1


def test_the_preflight_writes_nothing(repo):
    def snapshot():
        return sorted(str(p) for root in (repo.tti, repo.main) for p in root.rglob("*")
                      if ".git" not in p.parts)
    before = snapshot()
    PF.run(env=dict(GOOD))
    PF.run(env={})
    assert snapshot() == before


def test_the_first_output_line_names_the_outcome(repo, monkeypatch, capsys):
    for name, value in GOOD.items():
        monkeypatch.setenv(name, value)
    assert PF.main() == 0
    assert capsys.readouterr().out.splitlines()[0] == f"OUTCOME {PF.PREFLIGHT_OK}"
