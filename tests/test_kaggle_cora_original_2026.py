"""CORA-ONLY-G3 Kaggle entry (kaggle/cora_original_2026): software verification only, no scored evaluation.

Covers the attempt policy and its source labels, schema validation, multiple test inputs, the fallback, the package
build and its provenance audit, the notebook and kernel settings (private, internet off, no accelerator), the forbidden
module audit, and the isolated search children (results, wall-clock kill). Fixtures are hand-made grids.
"""
import importlib.util
import json
import os
import sys
import tarfile
import tempfile

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
PKG = os.path.join(HERE, "kaggle", "cora_original_2026")


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(PKG, f"{name}.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CO = _load("cora_only")
G1, G2, G3, G4 = [[1]], [[2]], [[3]], [[4]]
TASK = {"train": [{"input": [[0]], "output": [[0]]}], "test": [{"input": [[9]]}, {"input": [[8]]}]}


def native_row(source, solved_object=False, folds=0, a1=None, a2=None):
    return {"predictions": {"attempt_1": a1, "attempt_1_source": source, "attempt_2": a2},
            "object": {"solved": solved_object, "loo_folds": folds, "loo_score": 1.0 if solved_object else None}}


def g3_row(*attempts_per_test):
    return {"status": "ok", "attempts_by_test": [list(a) for a in attempts_per_test], "n_consistent": 1}


# ------------------------------------------------------------------ labels and policy
def test_object_render_is_certified_only_with_two_or_more_folds():
    assert CO.native_label(native_row("object", True, 2)) == "NATIVE_CERTIFIED"
    assert CO.native_label(native_row("object", True, 0)) == "NATIVE_CLAIMED"         # a single demonstration
    assert CO.native_label(native_row("pipeline", True, 3)) == "NATIVE_CLAIMED_ON_CERTIFIED_TASK"
    assert CO.native_label(native_row("geocat", False, 0)) == "NATIVE_CLAIMED"
    assert CO.native_label({}) is None


def test_precision_policy_order_and_distinct_attempts():
    challenges = {"t": TASK}
    nat = {"t": native_row("pipeline", False, 0, a1=[G1, G1], a2=[G4, G4])}
    srch = {"t": g3_row([G2, G3], [G2, G1])}
    sub, prov = CO.merge(challenges, nat, srch, "precision")
    # test 0: G3_FIT_1 (g3) then NATIVE_CLAIMED; test 1: g3's second attempt equals native's, so it is not repeated
    assert sub["t"][0] == {"attempt_1": G2, "attempt_2": G1}
    assert [a["source"] for a in prov["t"][0]] == ["G3_FIT_1", "NATIVE_CLAIMED"]
    assert sub["t"][1] == {"attempt_1": G2, "attempt_2": G1}
    assert not any(a["certified"] for pair in prov["t"] for a in pair)


def test_certified_native_render_comes_first_and_is_marked():
    challenges = {"t": TASK}
    nat = {"t": native_row("object", True, 2, a1=[G1, G4])}
    sub, prov = CO.merge(challenges, nat, {"t": g3_row([G2], [G3])}, "precision")
    assert sub["t"][0]["attempt_1"] == G1 and prov["t"][0][0] == {"source": "NATIVE_CERTIFIED", "certified": True}
    assert sub["t"][1] == {"attempt_1": G4, "attempt_2": G3}


def test_search_first_policy_puts_both_search_attempts_before_native_claims():
    challenges = {"t": {"train": TASK["train"], "test": [{"input": [[9]]}]}}
    nat = {"t": native_row("pipeline", False, 0, a1=[G1])}
    sub, _ = CO.merge(challenges, nat, {"t": g3_row([G2, G3])}, "search_first")
    assert sub["t"][0] == {"attempt_1": G2, "attempt_2": G3}


def test_fallback_is_the_test_input_and_both_attempts_always_exist():
    sub, prov = CO.merge({"t": TASK}, {}, {}, "precision")
    assert sub["t"] == [{"attempt_1": [[9]], "attempt_2": [[9]]}, {"attempt_1": [[8]], "attempt_2": [[8]]}]
    assert prov["t"][0][0]["source"] == "FALLBACK" and CO.validate(sub, {"t": TASK}) == []


def test_invalid_candidates_are_skipped():
    bad = [[1, 2], [3]]                                                  # ragged
    nat = {"t": native_row("pipeline", False, 0, a1=[bad, [[10]]])}     # and an illegal colour
    sub, prov = CO.merge({"t": TASK}, nat, {}, "precision")
    assert sub["t"][0]["attempt_1"] == [[9]] and sub["t"][1]["attempt_1"] == [[8]]


def test_validate_reports_missing_and_misordered_entries():
    ch = {"a": TASK, "b": TASK}
    good, _ = CO.merge(ch, {}, {}, "precision")
    assert CO.validate(good, ch) == []
    assert CO.validate({"b": good["b"], "a": good["a"]}, ch)            # order differs
    assert CO.validate({"a": good["a"][:1], "b": good["b"]}, ch)        # a missing test position


# ------------------------------------------------------------------ provenance
def test_forbidden_module_audit_flags_a_model_runtime():
    sys.modules["torch_fake_for_test"] = sys
    try:
        assert "torch_fake_for_test" in CO.audit_modules()
    finally:
        del sys.modules["torch_fake_for_test"]
    assert CO.audit_modules() == []


def test_package_build_passes_its_audit_and_stages_private_offline_kernels(tmp_path):
    bp = _load("build_package")
    out = tmp_path / "deploy"
    sys.argv = ["build_package.py", "--out", str(out)]
    bp.main()
    rec = json.load(open(out / "BUILD_RECORD.json"))
    with tarfile.open(rec["tarball"]) as t:
        names = t.getnames()
    assert any(n.endswith("cora_neural_v2g3/search.py") for n in names)
    assert not any(n.endswith("cora_neural_v2g3/neural.py") for n in names)
    assert not any("prior.py" in n or "pilot.py" in n for n in names)
    for k in ("submit", "dev_a", "dev_b"):
        meta = json.load(open(out / f"kernel_{k}" / "kernel-metadata.json"))
        assert meta["is_private"] and not meta["enable_internet"] and not meta["enable_gpu"] and not meta["enable_tpu"]
        nb = json.load(open(out / f"kernel_{k}" / "notebook.ipynb"))
        assert ("score_dev()" in "".join(nb["cells"][-1]["source"])) == k.startswith("dev")
    assert json.load(open(out / "dataset" / "dataset-metadata.json"))["licenses"] == [{"name": "other"}]


# ------------------------------------------------------------------ isolated search children
def test_search_child_returns_attempts_for_every_test_input(tmp_path):
    recolour = lambda g: [[5 if v == 1 else v for v in r] for r in g]   # noqa: E731
    a, b = [[0, 1], [1, 1]], [[1, 0, 1]]
    t = {"train": [{"input": a, "output": recolour(a)}, {"input": b, "output": recolour(b)}],
         "test": [{"input": [[1, 1, 0]]}, {"input": [[0], [1]]}]}
    CO.VARIANTS["T_SMALL"] = {"search": "g3", "budget": 300, "soft_cpu": 20, "hard_cpu": 60, "wall": 120}
    try:
        res = CO.run_search(HERE, {"t": t}, {}, "T_SMALL", __import__("time").time() + 200, 1, str(tmp_path))
    finally:
        del CO.VARIANTS["T_SMALL"]
    r = res["t"]
    assert r["status"] == "ok" and len(r["attempts_by_test"]) == 2
    assert r["attempts_by_test"][0][0] == recolour([[1, 1, 0]]) and r["attempts_by_test"][1][0] == recolour([[0], [1]])


def test_search_child_is_killed_at_its_wall_limit(tmp_path):
    big = [[(i * j) % 7 for j in range(25)] for i in range(25)]
    t = {"train": [{"input": big, "output": [r[::-1] for r in big]}], "test": [{"input": big}]}
    CO.VARIANTS["T_KILL"] = {"search": "g3", "budget": 100000, "soft_cpu": 600, "hard_cpu": 600, "wall": 0.5}
    try:
        res = CO.run_search(HERE, {"t": t}, {}, "T_KILL", __import__("time").time() + 30, 1, str(tmp_path))
    finally:
        del CO.VARIANTS["T_KILL"]
    assert res["t"]["status"] in ("timeout", "ok")                     # killed, unless it finished in 0.5 s


# ------------------------------------------------------------------ answer separation, dev scoring, determinism, arm E
def _comp(tmp_path, with_solutions=True):
    comp = tmp_path / "comp"
    comp.mkdir()
    ch = {"t1": {"train": [{"input": [[1]], "output": [[2]]}], "test": [{"input": [[1]]}, {"input": [[3]]}]},
          "t2": {"train": [{"input": [[5]], "output": [[5]]}], "test": [{"input": [[7]]}]}}
    json.dump(ch, open(comp / "arc-agi_evaluation_challenges.json", "w"))
    json.dump(ch, open(comp / "arc-agi_test_challenges.json", "w"))
    if with_solutions:
        json.dump({"t1": [[[2]], [[4]]], "t2": [[[7]]]}, open(comp / "arc-agi_evaluation_solutions.json", "w"))
    return comp, ch


def test_dev_staging_never_copies_the_evaluation_solutions(tmp_path):
    comp, ch = _comp(tmp_path)
    code = tmp_path / "solver"
    got, name, _ = CO.stage_inputs(str(code), str(comp), "dev")
    data = code / "data" / "arc"
    assert name == "arc-agi_evaluation_challenges.json" and list(got) == list(ch)
    assert json.load(open(data / "arc-agi_evaluation_solutions.json")) == {}
    assert sorted(os.listdir(data)) == ["arc-agi_evaluation_challenges.json", "arc-agi_evaluation_solutions.json"]


def test_score_dev_scores_each_variant_and_policy_by_test_output(tmp_path, monkeypatch):
    comp, ch = _comp(tmp_path)
    work = tmp_path / "work"
    (work / "solver" / "data" / "arc").mkdir(parents=True)
    json.dump(ch, open(work / "solver" / "data" / "arc" / "arc-agi_evaluation_challenges.json", "w"))
    rows = {"native": {}, "search": {"G3": {"t1": g3_row([[[2]]], [[[9]]]), "t2": g3_row([[[7]]])}}}
    json.dump(rows, open(work / "cora_rows.json", "w"))
    monkeypatch.setattr(CO, "WORK", str(work))
    monkeypatch.setenv("K_COMP", str(comp))
    rep = CO.score_dev()
    # t1: first output right, second wrong -> 0.5; t2 right -> 1.0; mean 75%
    assert rep["G3/precision"]["score_pct"] == 75.0 and rep["G3/precision"]["tasks_with_a_correct_output"] == 2
    assert rep["label"].startswith("exposed public evaluation")
    # native alone has nothing but the fallback: t2's fallback (the input [[7]]) happens to be right
    assert rep["NATIVE_ONLY"]["score_pct"] == 50.0


def test_merge_is_deterministic_and_keeps_test_order():
    ch = {"b": TASK, "a": TASK}
    nat = {"a": native_row("pipeline", a1=[G1, G2])}
    srch = {"b": g3_row([G3, G4], [G4]), "a": g3_row([G3], [G4])}
    s1, p1 = CO.merge(ch, nat, srch)
    s2, p2 = CO.merge(ch, nat, srch)
    assert s1 == s2 and p1 == p2 and list(s1) == ["b", "a"]
    assert s1["b"][0]["attempt_1"] == G3 and s1["b"][1]["attempt_1"] == G4      # per test input, in order
    assert [a["source"] for a in p1["a"][0]] == ["G3_FIT_1", "NATIVE_CLAIMED"]


def test_arm_e_returns_the_runner_contract_on_every_test_input(monkeypatch):
    """Native forced to fail (emulation switch) keeps this fast; the search runs for real on a tiny recolour task."""
    monkeypatch.setenv("K_FORCE_NATIVE_FAIL", "1")
    arm_e = _load("arm_e")
    task = {"task_id": "fx_arm_e", "train": [[[[1, 0], [0, 1]], [[5, 0], [0, 5]]], [[[0, 1], [1, 1]], [[0, 5], [5, 5]]]],
            "test_inputs": [[[1, 1], [0, 0]], [[0, 0], [1, 0]]]}
    r = arm_e.cora_only_g3(task, 3000, 120)
    for k in ("attempts_by_test", "predictions", "n_consistent", "n_candidates", "cpu_s", "provenance"):
        assert k in r
    assert len(r["attempts_by_test"]) == 2 and all(len(p) == 2 for p in r["attempts_by_test"])
    assert r["native_status"] == "failed" and not r["native_object_certified"]
    assert r["attempts_by_test"][0][0] == [[5, 5], [0, 0]] and r["attempts_by_test"][1][0] == [[0, 0], [5, 0]]
    assert not any(a["certified"] for pair in r["provenance"] for a in pair)
