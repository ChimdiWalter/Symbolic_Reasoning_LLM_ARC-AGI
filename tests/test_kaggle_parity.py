"""Baseline delivery parity: the native deployment environment and the K*
research environment stay separate, and the packaged assets are the sealed ones."""
import hashlib
import importlib.util
import os
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "scripts"))


def notebook():
    spec = importlib.util.spec_from_file_location("kaggle_notebook", os.path.join(HERE, "kaggle", "kaggle_notebook.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)                     # main() is not run on import
    return mod


def test_native_env_has_exactly_the_sealed_flags():
    nb = notebook()
    env = nb.native_env("/x", base={"ARC_OVERLAY": "1", "HOME": "/h"})
    assert {k: v for k, v in env.items() if k.startswith("ARC_")} == nb.CHAIN_FLAGS
    assert env["PYTHONPATH"] == "/x:/x/src" and env["HOME"] == "/h"


def test_notebook_flags_and_assets_match_the_pilot_native_baseline():
    from cora_pilot import native as N
    nb = notebook()
    assert nb.CHAIN_FLAGS == N.CHAIN_FLAGS
    assert nb.ASSETS == {"library.json": N.LIBRARY_SHA256, "learned_verbs.json": N.LEARNED_VERBS_SHA256}


def test_install_assets_copies_and_refuses_altered_files(tmp_path):
    nb = notebook()
    code, out = tmp_path / "code", tmp_path / "run"
    code.mkdir()
    for name in nb.ASSETS:
        (code / name).write_bytes(open(os.path.join(HERE, name), "rb").read())
    obj = nb.install_assets(str(code), str(out))
    for name, digest in nb.ASSETS.items():
        assert hashlib.sha256(open(os.path.join(obj, name), "rb").read()).hexdigest() == digest
    (code / "learned_verbs.json").write_text("[]")
    with pytest.raises(SystemExit):
        nb.install_assets(str(code), str(out))


def test_kstar_refuses_the_native_flags(monkeypatch):
    from cora_arc2026 import v17_compiler as X
    monkeypatch.setenv("PYTHONHASHSEED", "0")
    nb = notebook()
    for k, v in nb.CHAIN_FLAGS.items():
        monkeypatch.setenv(k, v)
    problems = X.kstar_environment_problems()
    assert all(any(k in p for p in problems) for k in nb.CHAIN_FLAGS)


def test_research_workers_strip_native_flags(monkeypatch):
    import pilot_v1_run as RUN
    for k, v in notebook().CHAIN_FLAGS.items():
        monkeypatch.setenv(k, v)
    assert not any(k.startswith("ARC_") for k in RUN.worker_env("cora"))
    assert all(RUN.worker_env("native")[k] == v for k, v in notebook().CHAIN_FLAGS.items())
