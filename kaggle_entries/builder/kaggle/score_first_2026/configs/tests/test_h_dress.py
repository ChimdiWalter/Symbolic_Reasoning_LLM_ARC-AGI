"""Dress rehearsals of entry H on CPU: every cell of the built H notebook runs as one script against a fake Kaggle root.
The setup:
- C4's verified cells run with the tiny RANDOM Qwen3 model as a stub neural pass;
- the real peft wheel and the real cast_selective_v2 package;
- two real public evaluation tasks under new ids, plus three random tasks;
- the offline socket guard on every Python process.
The test builds rewrite only C4's environment values (2 TTT steps, rank 4, 2 + 2 augmentations, 900 s deadline,
commit subset 3). The real builds keep C4's cells byte for byte.

Checked:
- H hidden-like: schema; submission_A.json (C4's file) kept; H equals an independent recomputation of the merge with
  the package's own insert_attempt2(tier1:B3); attempt 1 unchanged; the CORA process finished and is gone.
- H with every neural worker failing: C4 writes input copies, and H inserts exactly the B3-accepted grids.
- H with a broken CORA package: submission.json equals C4's file.
- The H rehearsal build on an evaluation file: both files written.
- H on the public placeholder: CORA runs only on the commit subset.

Run: CUDA_VISIBLE_DEVICES= PYTHONPATH=outputs/score_first/pylib:outputs/score_first/pylib_test \
     python3 -m pytest -q -p no:cacheprovider kaggle/score_first_2026/configs/tests/test_h_dress.py
"""
import hashlib
import json
import os
import random
import shutil
import subprocess
import sys
import time

import pytest

CONFIGS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SF_HOME = os.path.dirname(CONFIGS)
REPO = os.path.dirname(os.path.dirname(SF_HOME))
sys.path.insert(0, CONFIGS)
import build_configs as BC  # noqa: E402
from sfb import merge as M  # noqa: E402

V2_DIR = os.path.join(REPO, "experiments", "cora_cast_20261026", "kaggle_pkg", "cast_selective_v2")
sys.path.insert(0, V2_DIR)
import cast_selective_v2 as V2  # noqa: E402

DATA = os.path.join(REPO, "outputs", "score_first", "data")
WHEEL = os.path.join(REPO, "outputs", "score_first", "wheels", "peft-0.21.2-py3-none-any.whl")
OVERRIDES = {"neural_env": {"SF_TTT_STEPS": "2", "SF_TTT_RANK": "4", "SF_TTT_ALPHA": "8", "SF_COMMIT_TASKS": "3",
                            "SF_N_GEN": "2", "SF_N_SCORE": "2", "SF_DEADLINE_S": "900"},
             "b_env": {"SF_CAST_TOTAL_S": "600", "SF_CAST_END_RESERVE_S": "60"}}
PKG = "cast_selective_v2"
GUARD = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_cfg_dress.py")).read().split(
    "GUARD = r'''")[1].split("'''")[0]


def rand_grid(rng, h, w):
    return [[rng.randrange(10) for _ in range(w)] for _ in range(h)]


def rand_tasks(rng, prefix, n):
    return {f"{prefix}{k:03d}": {"train": [{"input": rand_grid(rng, 3, 3), "output": rand_grid(rng, 3, 3)}
                                           for _ in range(2)],
                                 "test": [{"input": rand_grid(rng, 3, 3)} for _ in range(1 + k % 2)]}
            for k in range(n)}


def hidden_like():
    ev = json.load(open(os.path.join(DATA, "arc-agi_evaluation_challenges.json")))
    t = {}
    for new, old in (("hx000", "62593bfd"), ("hx001", "981571dc")):
        t[new] = {"train": ev[old]["train"], "test": [{"input": x["input"]} for x in ev[old]["test"]]}
    t.update(rand_tasks(random.Random(3), "hr", 3))
    return t


@pytest.fixture(scope="module")
def work(tmp_path_factory):
    if not os.path.exists(WHEEL):
        pytest.skip("peft wheel not downloaded")
    import torch
    from transformers import Qwen3Config, Qwen3ForCausalLM
    w = tmp_path_factory.mktemp("hdress")
    torch.manual_seed(0)
    cfg = Qwen3Config(vocab_size=16, hidden_size=64, intermediate_size=128, num_hidden_layers=2,
                      num_attention_heads=4, num_key_value_heads=2, head_dim=16, max_position_embeddings=16384,
                      tie_word_embeddings=False, bos_token_id=13, eos_token_id=15, pad_token_id=13)
    Qwen3ForCausalLM(cfg).save_pretrained(str(w / "tiny"))
    (w / "guard").mkdir()
    (w / "guard" / "sitecustomize.py").write_text(GUARD)
    for name in ("H", "HRH"):
        BC.build_h(name, str(w / "kernels"), OVERRIDES)
    pkg = w / "brokenpkg"
    (pkg / "cast_broken").mkdir(parents=True)
    text = "raise ImportError('simulated missing dependency')\n"
    (pkg / "cast_broken" / "__init__.py").write_text(text)
    (pkg / "MANIFEST.json").write_text(json.dumps({
        "package": "cast_broken", "version": "broken-1", "entry_points": ["evaluate(task)"],
        "files": {"cast_broken/__init__.py": hashlib.sha256(text.encode()).hexdigest()}}))
    BC.H_BUILDS["Hbroken"] = dict(BC.H_BUILDS["H"], slug="sf-test-h-broken", packages=[
        {"manifest": str(pkg / "MANIFEST.json"), "entry": "evaluate", "mode": "evidence", "policy": "tier1:B3"}])
    BC.build_h("Hbroken", str(w / "kernels"), OVERRIDES)
    return w


def kdir(w, name):
    return w / "kernels" / BC.H_BUILDS[name]["slug"]


def fake_root(w, tag, test=None, evaluation=None, placeholder=False):
    root = w / f"root_{tag}" / "kaggle"
    comp = root / "input" / "competitions" / "arc-prize-2026-arc-agi-2"
    comp.mkdir(parents=True)
    train = rand_tasks(random.Random(11), "tr", 12)
    if placeholder:
        test = {k: {"train": train[k]["train"], "test": [{"input": x["input"]} for x in train[k]["test"]]}
                for k in list(train)[:10]}
    (comp / "arc-agi_training_challenges.json").write_text(json.dumps(train))
    (comp / "arc-agi_test_challenges.json").write_text(json.dumps(test if test is not None else hidden_like()))
    (comp / "arc-agi_evaluation_challenges.json").write_text(json.dumps(evaluation or hidden_like()))
    shutil.copytree(w / "tiny", root / "input" / "models" / "tiny" / "transformers" / "x" / "1")
    (root / "input" / "datasets" / "sf-peft-wheel-0212").mkdir(parents=True)
    shutil.copy(WHEEL, root / "input" / "datasets" / "sf-peft-wheel-0212")
    (root / "working").mkdir()
    return root


def run_nb(w, name, root, extra_env=None):
    nb = json.load(open(kdir(w, name) / "notebook.ipynb"))
    src = "\n".join(c["source"] for c in nb["cells"])
    log = root.parent / "net_guard.log"
    env = dict(os.environ, SF_KAGGLE_ROOT=str(root), SF_DEVICE="cpu", CUDA_VISIBLE_DEVICES="", SF_GPUS="1",
               SF_NET_GUARD_LOG=str(log), SF_TEST_NO_GPU="1",
               PYTHONPATH=os.pathsep.join([str(w / "guard"), os.environ.get("PYTHONPATH", "")]))
    env.update(extra_env or {})
    t0 = time.time()
    script = root.parent / "notebook_src.py"            # one argument may not exceed 128 KB, so run it as a file
    script.write_text(src)
    r = subprocess.run([sys.executable, str(script)], env=env, capture_output=True, text=True, timeout=2400,
                       cwd=str(root.parent))
    out = {"rc": r.returncode, "stdout": r.stdout, "stderr": r.stderr, "wall": time.time() - t0,
           "net": log.read_text() if log.exists() else ""}
    (root.parent / "notebook_stdout.txt").write_text(r.stdout[-20000:] + "\n---stderr---\n" + r.stderr[-20000:])
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    assert out["net"] == "", "network attempt under the offline guard: " + out["net"][:500]
    return out


def jl(p):
    with open(p) as f:
        return json.load(f)


def side_dir(root, i=0, pkg=PKG):
    return root / "working" / "cora_side" / f"{i}_{pkg}"


def side_results(root):
    d = side_dir(root)
    return {f[:-5]: jl(d / f) for f in os.listdir(d) if f.endswith(".json") and f != "status.json"}


def pid_gone(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    try:
        return open(f"/proc/{pid}/stat").read().split(")")[1].split()[0] == "Z"
    except OSError:
        return True


def recompute(root, ch):
    sub_a = jl(root / "working" / "submission_A.json")
    pk = [{"name": PKG, "mode": "evidence", "policy": "tier1:B3"}]
    return M.merge_packages(sub_a, ch, pk, {PKG: side_results(root)}, {PKG: V2.insert_attempt2})


@pytest.fixture(scope="module")
def h_hidden(work):
    root = fake_root(work, "h_hidden")
    return root, run_nb(work, "H", root)


def test_h_hidden_like(h_hidden):
    root, out = h_hidden
    test = jl(root / "input" / "competitions" / "arc-prize-2026-arc-agi-2" / "arc-agi_test_challenges.json")
    wk = root / "working"
    sub_h, sub_c4 = jl(wk / "submission.json"), jl(wk / "submission_A.json")
    assert M.schema_problems(sub_h, test) == [] and M.schema_problems(sub_c4, test) == []
    rep = jl(wk / "cast_merge_report.json")
    assert rep["ok"] and rep["tier"] == 1
    st = jl(side_dir(root) / "status.json")
    assert st["stopped"] == "finished" and st["done"] == len(test) and st["mode"] == "evidence" and pid_gone(st["pid"])
    assert recompute(root, test)[0] == sub_h == jl(wk / "submission_B.json")
    for tid in test:
        assert [x["attempt_1"] for x in sub_c4[tid]] == [x["attempt_1"] for x in sub_h[tid]]
    runs = [d for d in os.listdir(wk) if d.startswith("guarded_run_")]
    assert len(runs) == 1 and jl(wk / runs[0] / "guard_status.json")


def test_h_neural_failure_b3_inserts(work):
    root = fake_root(work, "h_fail")
    run_nb(work, "H", root, extra_env={"SF_DEVICE": "cuda:0"})          # no GPU here: every worker fails
    test = jl(root / "input" / "competitions" / "arc-prize-2026-arc-agi-2" / "arc-agi_test_challenges.json")
    wk = root / "working"
    sub_c4, sub_h = jl(wk / "submission_A.json"), jl(wk / "submission.json")
    res = side_results(root)
    n_expected = 0
    for tid, t in test.items():
        ev = res[tid].get("evidence")
        for j, x in enumerate(t["test"]):
            assert sub_c4[tid][j] == {"attempt_1": x["input"], "attempt_2": x["input"]}       # C4's fallback
            assert sub_h[tid][j]["attempt_1"] == x["input"]
            acc = ev["queries"][j]["accepted"].get("B3") if ev and ev.get("status") == "OK" else None
            if acc is not None and acc != x["input"]:
                n_expected += 1
                assert sub_h[tid][j]["attempt_2"] == acc
            else:
                assert sub_h[tid][j]["attempt_2"] == x["input"]
    rep = jl(wk / "cast_merge_report.json")
    assert rep["ok"] and rep["replaced_tier0"] + rep["replaced_tier1"] == n_expected
    (root.parent / "b3_insertions.txt").write_text(str(n_expected))


def test_h_broken_cora_keeps_c4(work):
    root = fake_root(work, "h_broken")
    run_nb(work, "Hbroken", root)
    wk = root / "working"
    assert jl(wk / "submission.json") == jl(wk / "submission_A.json")
    st = jl(side_dir(root, 0, "cast_broken") / "status.json")
    assert st["stopped"] == "error" and "ImportError" in st["error"]


def test_h_rehearsal_build_writes_both(work):
    root = fake_root(work, "h_rehearsal")
    run_nb(work, "HRH", root)
    ev = jl(root / "input" / "competitions" / "arc-prize-2026-arc-agi-2" / "arc-agi_evaluation_challenges.json")
    wk = root / "working"
    sub_a, sub_b = jl(wk / "submission_A.json"), jl(wk / "submission_B.json")
    assert M.schema_problems(sub_a, ev) == [] and M.schema_problems(sub_b, ev) == []
    assert jl(wk / "submission.json") == sub_b
    st = jl(side_dir(root) / "status.json")
    assert st["done"] == len(ev) and st["stopped"] == "finished"
    assert recompute(root, ev)[0] == sub_b


def test_h_placeholder_commit_subset(work):
    root = fake_root(work, "h_placeholder", placeholder=True)
    run_nb(work, "H", root)
    wk = root / "working"
    test = jl(root / "input" / "competitions" / "arc-prize-2026-arc-agi-2" / "arc-agi_test_challenges.json")
    st = jl(side_dir(root) / "status.json")
    assert st["n_tasks"] == 3 and st["done"] == 3
    assert M.schema_problems(jl(wk / "submission.json"), test) == []
