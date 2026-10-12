"""NATIVE_BASELINE native_v1 Kaggle package tests (kaggle/native_v1/)."""
import importlib.util
import json
import os
import tarfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NB = os.path.join(HERE, "kaggle", "native_v1", "notebook.py")


def _nb():
    spec = importlib.util.spec_from_file_location("nb_native_v1", NB)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


CH = {"a": {"train": [], "test": [{"input": [[1, 2]]}, {"input": [[3]]}]}, "b": {"train": [], "test": [{"input": [[0]]}]}}


def test_label_flags_assets_match_the_historical_notebook():
    m = _nb()
    spec = importlib.util.spec_from_file_location("nb_hist", os.path.join(HERE, "kaggle", "kaggle_notebook.py"))
    h = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(h)
    assert m.LABEL == "NATIVE_BASELINE" and m.CHAIN_FLAGS == h.CHAIN_FLAGS and m.ASSETS == h.ASSETS


def test_native_env_exact_flags_and_no_leak():
    m = _nb()
    base = {"PATH": "/bin", "ARC_SOMETHING_ELSE": "1", "ARC_GUIDE": "1"}
    env = m.native_env("/code", base)
    assert {k: v for k, v in env.items() if k.startswith("ARC_")} == m.CHAIN_FLAGS
    assert env["PYTHONPATH"] == "/code:/code/src" and "K_GUARD_DIR" not in env
    assert not any(k.startswith("ARC_") for k in os.environ if k in m.CHAIN_FLAGS and os.environ[k] != base.get(k, os.environ[k]))
    g = m.native_env("/code", dict(base, K_GUARD_DIR="/g"))
    assert g["PYTHONPATH"].startswith("/g:")


def test_validate_and_repair_follows_the_writer_fallback_order():
    m = _nb()
    sub = {"a": [{"attempt_1": [[1, 1]], "attempt_2": "bad"}, {"attempt_1": [[10]], "attempt_2": [[4]]}],
           "c": [{"attempt_1": [[0]], "attempt_2": [[0]]}]}
    out, repairs, extra = m.validate_and_repair(sub, CH)
    assert out["a"][0] == {"attempt_1": [[1, 1]], "attempt_2": [[1, 1]]}          # bad attempt_2 -> attempt_1
    assert out["a"][1] == {"attempt_1": [[4]], "attempt_2": [[4]]}                # bad attempt_1 -> attempt_2
    assert out["b"] == [{"attempt_1": [[0]], "attempt_2": [[0]]}]                 # missing task -> test input
    assert extra == ["c"] and len(repairs) == 4
    assert set(out) == set(CH) and [len(v) for v in out.values()] == [2, 1]


def test_grid_validity_rules():
    m = _nb()
    assert m._grid_ok([[0, 9]]) and not m._grid_ok([]) and not m._grid_ok([[1], [1, 2]])
    assert not m._grid_ok([[True]]) and not m._grid_ok([[1.0]]) and not m._grid_ok([[0] * 31])


def test_fallback_submission_without_progress(tmp_path):
    m = _nb()
    sub = m.fallback_submission(CH, str(tmp_path / "missing.jsonl"))
    assert sub == {"a": [{"attempt_1": [[1, 2]], "attempt_2": [[1, 2]]}, {"attempt_1": [[3]], "attempt_2": [[3]]}],
                   "b": [{"attempt_1": [[0]], "attempt_2": [[0]]}]}


def test_package_matches_the_historical_v23_code():
    new = os.path.join(HERE, "kaggle", "native_v1", "arc_native_baseline_v1.tar.gz")
    old = os.path.join(HERE, "kaggle", "arc_certified_solver_v23.tar.gz")
    if not (os.path.exists(new) and os.path.exists(old)):
        return
    def files(p):
        with tarfile.open(p) as t:
            return {os.path.normpath(i.name): t.extractfile(i).read() for i in t.getmembers() if i.isfile()}
    a, b = files(new), files(old)
    a.pop("MANIFEST.json", None)
    assert set(a) == set(b), (sorted(set(a) ^ set(b)))[:10]
    assert [k for k in a if a[k] != b[k]] == []
