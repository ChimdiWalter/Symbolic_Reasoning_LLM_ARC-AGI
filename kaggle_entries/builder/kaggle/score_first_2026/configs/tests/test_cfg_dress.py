"""Dress rehearsals of the built A, B and AB notebooks on CPU. All cells run as one script against a fake Kaggle
root with a tiny RANDOM Qwen3 model (not the checkpoint), the real peft wheel, the real CAST package, two real public
evaluation tasks under new ids and three random tasks. Every run sits behind a socket guard that blocks and logs any
IPv4/IPv6 connection or name lookup from every Python process (offline check).

Checked:
- B hidden-like: schema; submission_A.json kept; B equals an independent recomputation of the Tier 0 merge;
  attempt 1 unchanged; the CAST process finished and is gone.
- B with the neural workers forced to fail: A is all fallbacks, and Tier 0 fills attempt 2 with CAST's answers.
- B with a broken CAST package, and B with a tampered embedded file: submission.json equals A's.
- AB rehearsal: both files written from one neural pass.
- A on the same input twice: byte-identical, and equal to B's submission_A.json (same neural path).
- B on the public placeholder: CAST runs only on the commit subset.

Run: CUDA_VISIBLE_DEVICES= PYTHONPATH=outputs/score_first/pylib:outputs/score_first/pylib_test \
     python3 -m pytest -q -p no:cacheprovider kaggle/score_first_2026/configs/tests/test_cfg_dress.py
"""
import json
import os
import random
import shutil
import subprocess
import sys
import textwrap
import time

import pytest

CONFIGS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SF_HOME = os.path.dirname(CONFIGS)
REPO = os.path.dirname(os.path.dirname(SF_HOME))
sys.path.insert(0, CONFIGS)
import build_configs as BC  # noqa: E402
from sfb import merge as M  # noqa: E402

DATA = os.path.join(REPO, "outputs", "score_first", "data")
WHEEL = os.path.join(REPO, "outputs", "score_first", "wheels", "peft-0.21.2-py3-none-any.whl")
OVERRIDES = {"neural_env": {"SF_TTT_STEPS": "2", "SF_TTT_RANK": "4", "SF_TTT_ALPHA": "8", "SF_COMMIT_TASKS": "3",
                            "SF_N_GEN": "2", "SF_N_SCORE": "2", "SF_DEADLINE_S": "900"},
             "b_env": {"SF_CAST_TOTAL_S": "600", "SF_CAST_END_RESERVE_S": "60"}}
GUARD = r'''
import os, socket
if os.environ.get("SF_TEST_NO_GPU") == "1":      # CPU-only tests: no process may see a GPU, whatever the runner sets
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
_LOG = os.environ.get("SF_NET_GUARD_LOG")
_LOCAL = {None, "localhost", "127.0.0.1", "::1", ""}
def _blocked(what, addr):
    if _LOG:
        with open(_LOG, "a") as f:
            f.write(f"{os.getpid()} {what} {addr!r}\n")
    raise OSError("network blocked by the offline test guard")
_connect, _connect_ex, _sendto = socket.socket.connect, socket.socket.connect_ex, socket.socket.sendto
def connect(self, addr):
    if self.family in (socket.AF_INET, socket.AF_INET6):
        _blocked("connect", addr)
    return _connect(self, addr)
def connect_ex(self, addr):
    if self.family in (socket.AF_INET, socket.AF_INET6):
        _blocked("connect_ex", addr)
    return _connect_ex(self, addr)
def sendto(self, *a):
    if self.family in (socket.AF_INET, socket.AF_INET6):
        _blocked("sendto", a[-1])
    return _sendto(self, *a)
_gai = socket.getaddrinfo
def getaddrinfo(host, *a, **k):
    if host not in _LOCAL:
        _blocked("getaddrinfo", host)
    return _gai(host, *a, **k)
socket.socket.connect, socket.socket.connect_ex, socket.socket.sendto = connect, connect_ex, sendto
socket.getaddrinfo = getaddrinfo
'''


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
    w = tmp_path_factory.mktemp("dress")
    torch.manual_seed(0)
    cfg = Qwen3Config(vocab_size=16, hidden_size=64, intermediate_size=128, num_hidden_layers=2,
                      num_attention_heads=4, num_key_value_heads=2, head_dim=16, max_position_embeddings=16384,
                      tie_word_embeddings=False, bos_token_id=13, eos_token_id=15, pad_token_id=13)
    Qwen3ForCausalLM(cfg).save_pretrained(str(w / "tiny"))
    (w / "guard").mkdir()
    (w / "guard" / "sitecustomize.py").write_text(GUARD)
    for name in ("A", "B", "AB"):
        BC.build(name, BC.DEFAULT_CAST_MANIFEST, str(w / "kernels"), OVERRIDES)
    pkg = w / "brokenpkg"                                   # a CAST package that fails at import
    (pkg / "cast_broken").mkdir(parents=True)
    text = "raise ImportError('simulated missing dependency')\n"
    (pkg / "cast_broken" / "__init__.py").write_text(text)
    import hashlib
    (pkg / "MANIFEST.json").write_text(json.dumps({
        "package": "cast_broken", "version": "broken-1", "entry_point": "cast_broken.cast_candidates(task)",
        "files": {"cast_broken/__init__.py": hashlib.sha256(text.encode()).hexdigest()}}))
    BC.BUILDS["Bbroken"] = dict(BC.BUILDS["B"], slug="sf-test-cfgB-broken")
    BC.build("Bbroken", str(pkg / "MANIFEST.json"), str(w / "kernels"), OVERRIDES)
    return w


def kdir(w, name):
    return w / "kernels" / BC.BUILDS[name]["slug"]


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


def run_nb(w, name, root, extra_env=None, notebook=None):
    nb = json.load(open(notebook or (kdir(w, name) / "notebook.ipynb")))
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
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    assert out["net"] == "", "network attempt under the offline guard: " + out["net"][:500]
    return out


def jl(p):
    with open(p) as f:
        return json.load(f)


def cast_results(root):
    d = root / "working" / "run" / "cast"
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


def test_guard_blocks_network(work):
    log = work / "guard_selftest.log"
    env = dict(os.environ, SF_NET_GUARD_LOG=str(log), SF_TEST_NO_GPU="1", PYTHONPATH=str(work / "guard"))
    code = "import socket\ntry:\n    socket.create_connection(('192.0.2.1', 443), timeout=1)\nexcept OSError as e:\n    print('blocked', e)\n"
    r = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=60)
    assert "blocked" in r.stdout and log.read_text().strip()


@pytest.fixture(scope="module")
def b_hidden(work):
    root = fake_root(work, "b_hidden")
    return root, run_nb(work, "B", root)


def test_b_hidden_like(b_hidden):
    root, out = b_hidden
    test = jl(root / "input" / "competitions" / "arc-prize-2026-arc-agi-2" / "arc-agi_test_challenges.json")
    wk = root / "working"
    sub_b, sub_a = jl(wk / "submission.json"), jl(wk / "submission_A.json")
    assert M.schema_problems(sub_b, test) == [] and M.schema_problems(sub_a, test) == []
    rep = jl(wk / "cast_merge_report.json")
    assert rep["ok"] and rep["tier"] == 0
    st = jl(wk / "run" / "cast" / "status.json")
    assert st["stopped"] == "finished" and st["done"] == len(test) and pid_gone(st["pid"])
    expect, _ = M.merge(sub_a, test, cast_results(root), tier=0)
    assert sub_b == expect
    for tid in test:
        assert [x["attempt_1"] for x in sub_a[tid]] == [x["attempt_1"] for x in sub_b[tid]]
    assert len(os.listdir(wk / "run" / "pools")) == len(test)


def test_b_neural_failure_tier0_fills_attempt_2(work):
    root = fake_root(work, "b_fail")
    run_nb(work, "B", root, extra_env={"SF_DEVICE": "cuda:0"})          # no GPU here: every worker fails
    test = jl(root / "input" / "competitions" / "arc-prize-2026-arc-agi-2" / "arc-agi_test_challenges.json")
    wk = root / "working"
    sub_a, sub_b, rep = jl(wk / "submission_A.json"), jl(wk / "submission.json"), jl(wk / "cast_merge_report.json")
    cast = cast_results(root)
    n_expected = 0
    for tid, t in test.items():
        for j, x in enumerate(t["test"]):
            assert sub_a[tid][j] == {"attempt_1": x["input"], "attempt_2": x["input"]}      # A's fallback
            assert sub_b[tid][j]["attempt_1"] == x["input"]
            gj = cast[tid]["grids"][j]
            if gj is not None and gj != x["input"]:
                n_expected += 1
                assert sub_b[tid][j]["attempt_2"] == gj
            else:
                assert sub_b[tid][j]["attempt_2"] == x["input"]
    assert rep["ok"] and rep["replaced_tier0"] == n_expected and n_expected >= 1


def test_b_broken_cast_keeps_a(work):
    root = fake_root(work, "b_broken")
    run_nb(work, "Bbroken", root)
    wk = root / "working"
    assert jl(wk / "submission.json") == jl(wk / "submission_A.json")
    st = jl(wk / "run" / "cast" / "status.json")
    assert st["stopped"] == "error" and "ImportError" in st["error"]
    rep = jl(wk / "cast_merge_report.json")
    assert rep["ok"] and rep["replaced_tier0"] == 0 and rep["replaced_tier1"] == 0


def test_b_tampered_embedded_file_keeps_a(work):
    nb = jl(kdir(work, "B") / "notebook.ipynb")
    src = nb["cells"][1]["source"]
    i = src.index("_sha = ") + len("_sha = {'")
    j = src.index("'", src.index(": '", i) + 3)
    nb["cells"][1]["source"] = src[:j - 64] + "0" * 64 + src[j:]                        # one wrong hash
    p = work / "tampered.ipynb"
    p.write_text(json.dumps(nb))
    root = fake_root(work, "b_tampered")
    out = run_nb(work, "B", root, notebook=str(p))
    assert "CAST not started" in out["stdout"] and "hash mismatch" in out["stdout"]
    wk = root / "working"
    assert jl(wk / "submission.json") == jl(wk / "submission_A.json")


def test_ab_rehearsal_writes_both(work):
    root = fake_root(work, "ab")
    run_nb(work, "AB", root)
    ev = jl(root / "input" / "competitions" / "arc-prize-2026-arc-agi-2" / "arc-agi_evaluation_challenges.json")
    wk = root / "working"
    sub_a, sub_b = jl(wk / "submission_A.json"), jl(wk / "submission_B.json")
    assert M.schema_problems(sub_a, ev) == [] and M.schema_problems(sub_b, ev) == []
    assert jl(wk / "submission.json") == sub_b
    assert jl(wk / "run_info.json")["challenges"].endswith("arc-agi_evaluation_challenges.json")
    st = jl(wk / "run" / "cast" / "status.json")
    assert st["done"] == len(ev) and st["stopped"] == "finished"
    assert M.merge(sub_a, ev, cast_results(root), tier=0)[0] == sub_b


def test_a_deterministic_and_equal_to_b_neural_path(work, b_hidden):
    outs = []
    for k in range(2):
        root = fake_root(work, f"a_{k}")
        run_nb(work, "A", root)
        outs.append((root / "working" / "submission.json").read_bytes())
        assert not (root / "working" / "submission_A.json").exists()           # A has no CAST cells
    assert outs[0] == outs[1]
    b_root, _ = b_hidden
    assert json.loads(outs[0]) == jl(b_root / "working" / "submission_A.json")


def test_b_placeholder_commit_subset(work):
    root = fake_root(work, "b_placeholder", placeholder=True)
    run_nb(work, "B", root)
    wk = root / "working"
    test = jl(root / "input" / "competitions" / "arc-prize-2026-arc-agi-2" / "arc-agi_test_challenges.json")
    assert jl(wk / "run_info.json")["placeholder_test_file"] is True
    st = jl(wk / "run" / "cast" / "status.json")
    assert st["n_tasks"] == 3 and st["done"] == 3
    assert len(os.listdir(wk / "run" / "pools")) == 3
    assert M.schema_problems(jl(wk / "submission.json"), test) == []
