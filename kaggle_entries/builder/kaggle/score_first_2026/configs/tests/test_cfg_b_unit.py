"""Configuration B, unit and process-level checks (CPU only, no model):
- the merge rule (Tier 0 default, Tier 1 off) and its self-check;
- Tier 0 dominance under the official metric (a random property test);
- malformed or missing CAST output keeps A;
- the side process, run for real against stub packages:
  - the caps stop the work at process level: the parent's wall kill and the child's RLIMIT_CPU;
  - the stopped child is reaped and gone;
  - state resets between puzzles (module globals, caches, timers, signal handlers);
  - the total budget is honoured;
  - an import failure is fail-safe;
- the real CAST package through the side process: identical answers in either task order and when each task runs
  alone, and equal to the frozen research output where it answers.

Run: CUDA_VISIBLE_DEVICES= python3 -m pytest -q -p no:cacheprovider configs/tests/test_cfg_b_unit.py
"""
import copy
import json
import os
import random
import subprocess
import sys
import textwrap
import time

import pytest

CONFIGS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SF_HOME = os.path.dirname(CONFIGS)
REPO = os.path.dirname(os.path.dirname(SF_HOME))
sys.path.insert(0, CONFIGS)
from sfb import merge as M  # noqa: E402

DATA = os.path.join(REPO, "outputs", "score_first", "data")
CAST_PKG = os.path.join(REPO, "experiments", "cora_cast_20261026", "kaggle_pkg")
FROZEN_CANDS = os.path.join(REPO, "experiments", "cora_cast_20261026", "results", "candidates_for_score_first",
                            "ARC_eval_dev.json")


def g(v, h=2, w=2):
    return [[v] * w for _ in range(h)]


# ----- merge rule ------------------------------------------------------------------------------------------------
def test_merge_rules_and_self_check():
    ch = {"t1": {"train": [], "test": [{"input": g(0)}, {"input": g(0)}, {"input": g(0)}]},
          "t2": {"train": [], "test": [{"input": g(0)}]},
          "t3": {"train": [], "test": [{"input": g(0)}]},
          "t4": {"train": [], "test": [{"input": g(0)}]}}
    a = {"t1": [{"attempt_1": g(1), "attempt_2": g(1)},          # identical pair
                {"attempt_1": g(1), "attempt_2": g(2)},          # distinct pair
                {"attempt_1": g(3), "attempt_2": g(3)}],         # identical pair, CAST equals it
         "t2": [{"attempt_1": g(1), "attempt_2": g(2)}],         # distinct pair, CAST equals attempt 2
         "t3": [{"attempt_1": g(1), "attempt_2": g(1)}],         # CAST timed out
         "t4": [{"attempt_1": g(1), "attempt_2": g(1)}]}         # CAST malformed
    cast = {"t1": {"status": "OK", "grids": [g(5), g(6), g(3)]},
            "t2": {"status": "OK", "grids": [g(2)]},
            "t3": {"status": "TIMEOUT", "grids": [g(7)]},
            "t4": {"status": "OK", "grids": [[[1, 2], [3]]]}}
    b0, r0 = M.merge(a, ch, cast, tier=0)
    assert b0["t1"][0] == {"attempt_1": g(1), "attempt_2": g(5)}
    assert b0["t1"][1] == a["t1"][1] and b0["t1"][2] == a["t1"][2]
    assert b0["t2"] == a["t2"] and b0["t3"] == a["t3"] and b0["t4"] == a["t4"]
    assert (r0["replaced_tier0"], r0["replaced_tier1"], r0["tier1_candidates"]) == (1, 0, 1)
    assert (r0["same_as_attempt_1"], r0["same_as_attempt_2"], r0["skipped_malformed"]) == (1, 1, 1)
    assert r0["identical_attempt_outputs"] == 4
    assert M.self_check(a, b0, ch, 0) == []
    b1, r1 = M.merge(a, ch, cast, tier=1)
    assert b1["t1"][1] == {"attempt_1": g(1), "attempt_2": g(6)} and r1["replaced_tier1"] == 1
    assert M.self_check(a, b1, ch, 1) == []
    assert M.self_check(a, b1, ch, 0), "tier 0 must reject a change to a distinct pair"
    for tier, b in ((0, b0), (1, b1)):                    # attempt 1 is never changed
        for tid in a:
            for x, y in zip(a[tid], b[tid]):
                assert x["attempt_1"] == y["attempt_1"]
    bad = copy.deepcopy(b0)
    bad["t2"][0]["attempt_1"] = g(9)
    assert any("attempt_1 changed" in p for p in M.self_check(a, bad, ch, 0))
    bad = copy.deepcopy(b0)
    bad["t1"][0]["attempt_2"] = [[1, 2], [3]]
    assert any("invalid grid" in p for p in M.self_check(a, bad, ch, 0))
    with pytest.raises(ValueError):
        M.merge(a, ch, cast, tier=2)


@pytest.mark.parametrize("bad", [None, "x", [], [[]], [[1, 2], [3]], [[10]], [[True]], [[1.0]], [["1"]],
                                 [[0] * 31], [[0]] * 31, [[[0]]], {"a": 1}])
def test_malformed_cast_grid_keeps_a(bad):
    ch = {"t": {"train": [], "test": [{"input": g(0)}]}}
    a = {"t": [{"attempt_1": g(1), "attempt_2": g(1)}]}
    b, rep = M.merge(a, ch, {"t": {"status": "OK", "grids": [bad]}}, tier=0)
    assert b == a and rep["replaced_tier0"] == 0


@pytest.mark.parametrize("grids", [None, "x", [], [g(5), g(5)], {"0": g(5)}])
def test_wrong_grids_field_keeps_a(grids):
    ch = {"t": {"train": [], "test": [{"input": g(0)}]}}
    a = {"t": [{"attempt_1": g(1), "attempt_2": g(1)}]}
    b, rep = M.merge(a, ch, {"t": {"status": "OK", "grids": grids}}, tier=0)
    assert b == a and rep["replaced_tier0"] == 0


def test_tier0_dominance_random():
    """Under the official metric (a query scores if either attempt equals its truth), Tier 0 never lowers any
    query's score, and never changes attempt 1."""
    rng = random.Random(7)
    for _ in range(3000):
        n = rng.randint(1, 3)
        ch = {"t": {"train": [], "test": [{"input": g(0)} for _ in range(n)]}}
        vals = list(range(4))
        a, truth, grids = [], [], []
        for _j in range(n):
            a1 = rng.choice(vals)
            a2 = a1 if rng.random() < 0.5 else rng.choice(vals)
            a.append({"attempt_1": g(a1), "attempt_2": g(a2)})
            truth.append(g(rng.choice(vals)))
            grids.append(None if rng.random() < 0.3 else g(rng.choice(vals)))
        sub_a = {"t": a}
        sub_b, _ = M.merge(sub_a, ch, {"t": {"status": "OK", "grids": grids}}, tier=0)
        for j in range(n):
            sa = truth[j] in (sub_a["t"][j]["attempt_1"], sub_a["t"][j]["attempt_2"])
            sb = truth[j] in (sub_b["t"][j]["attempt_1"], sub_b["t"][j]["attempt_2"])
            assert sb >= sa
            assert sub_b["t"][j]["attempt_1"] == sub_a["t"][j]["attempt_1"]


def test_merge_files_corrupt_cast_file_and_atomic_write(tmp_path):
    ch = {"t": {"train": [], "test": [{"input": g(0)}]}, "u": {"train": [], "test": [{"input": g(0)}]}}
    a = {"t": [{"attempt_1": g(1), "attempt_2": g(1)}], "u": [{"attempt_1": g(1), "attempt_2": g(1)}]}
    (tmp_path / "a.json").write_text(json.dumps(a))
    (tmp_path / "ch.json").write_text(json.dumps(ch))
    cd = tmp_path / "cast"
    cd.mkdir()
    (cd / "t.json").write_text('{"status": "OK", "grids": [[[5, 5]')           # truncated
    (cd / "u.json").write_text(json.dumps({"status": "OK", "grids": [g(4)]}))
    rep = M.merge_files(str(tmp_path / "a.json"), str(tmp_path / "ch.json"), str(cd), 0, str(tmp_path / "b.json"),
                        str(tmp_path / "rep.json"))
    b = json.loads((tmp_path / "b.json").read_text())
    assert rep["ok"] and b["t"] == a["t"] and b["u"][0]["attempt_2"] == g(4)
    assert not [f for f in os.listdir(tmp_path) if ".tmp" in f]


# ----- the side process against stub packages ----------------------------------------------------------------------
def make_pkg(root, name, body):
    d = root / name
    d.mkdir(parents=True)
    (d / "__init__.py").write_text("VERSION = 'stub'\n" + textwrap.dedent(body))
    return name


def tasks(n, n_test=1):
    return {f"s{k:03d}": {"train": [{"input": g(1), "output": g(2)}, {"input": g(3), "output": g(4)}],
                          "test": [{"input": g(5)} for _ in range(n_test)]} for k in range(n)}


def run_side(tmp, pkg, ch, deadline_s=120.0, cpu_s=15.0, wall_s=30.0, grace_s=10.0, extra=(), tag=""):
    chp = tmp / f"ch_{pkg}{tag}.json"
    chp.write_text(json.dumps(ch))
    out = tmp / f"out_{pkg}{tag}"
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([CONFIGS, str(tmp)]), CUDA_VISIBLE_DEVICES="")
    t0 = time.time()
    r = subprocess.run([sys.executable, "-m", "sfb.cast_side", "--challenges", str(chp), "--out", str(out),
                        "--package", pkg, "--entry", "cast_candidates", "--deadline", str(time.time() + deadline_s),
                        "--cpu-s", str(cpu_s), "--wall-s", str(wall_s), "--grace-s", str(grace_s), *extra],
                       cwd=str(tmp), env=env, capture_output=True, text=True, timeout=600)
    wall = time.time() - t0
    assert r.returncode == 0, r.stderr[-2000:]
    st = json.loads((out / "status.json").read_text())
    res = {f[:-5]: json.loads((out / f).read_text()) for f in os.listdir(out) if f.endswith(".json") and
           f != "status.json"}
    return st, res, wall


def gone(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    try:                                                   # a zombie still answers kill(0); check its state
        return open(f"/proc/{pid}/stat").read().split(")")[1].split()[0] == "Z"
    except OSError:
        return True


def test_side_wall_kill_when_package_caps_fail(tmp_path):
    """The package's own timers are disabled (signals ignored, pure-Python loop): the parent's SIGKILL at
    wall_s + grace_s must stop it, reap it and move on."""
    pkg = make_pkg(tmp_path, "stub_hang", f"""
        import os, signal
        def cast_candidates(task, cpu_s=15, wall_s=30, details=False):
            open({str(tmp_path)!r} + '/pid_' + str(os.getpid()), 'w').close()
            for s in (signal.SIGALRM, signal.SIGVTALRM, signal.SIGTERM):
                signal.signal(s, signal.SIG_IGN)
            while True:
                pass
        """)
    st, res, wall = run_side(tmp_path, pkg, tasks(2), cpu_s=60, wall_s=1.5, grace_s=1.0)
    assert st["done"] == 2 and st["stopped"] == "finished"
    for r in res.values():
        assert r["status"] == "KILLED_WALL" and r["grids"] == [None]
        assert 2.4 <= r["child"]["wall_s"] <= 6.0, r["child"]
        assert r["child"]["killed_by_parent"] and r["child"]["signal"] == 9
    pids = [int(f[4:]) for f in os.listdir(tmp_path) if f.startswith("pid_")]
    assert len(pids) == 2 and all(gone(p) for p in pids)
    assert wall < 30


@pytest.mark.parametrize("ignore_xcpu", [False, True])
def test_side_cpu_rlimit_kill(tmp_path, ignore_xcpu):
    """CPU burn with the package's timers disabled and a long wall cap: the child's RLIMIT_CPU must kill it (SIGXCPU
    at the soft limit, SIGKILL at the hard limit when SIGXCPU is ignored)."""
    pkg = make_pkg(tmp_path, f"stub_burn{int(ignore_xcpu)}", f"""
        import signal
        def cast_candidates(task, cpu_s=15, wall_s=30, details=False):
            for s in (signal.SIGALRM, signal.SIGVTALRM):
                signal.signal(s, signal.SIG_IGN)
            if {ignore_xcpu!r}:
                signal.signal(signal.SIGXCPU, signal.SIG_IGN)
            x = 0
            while True:
                x += 1
        """)
    st, res, wall = run_side(tmp_path, pkg, tasks(1), deadline_s=300.0, cpu_s=1.0, wall_s=120.0, grace_s=1.0)
    r = res["s000"]
    assert r["status"] == "KILLED_CPU" and r["grids"] == [None], r
    assert r["child"]["signal"] in (24, 9) and not r["child"]["killed_by_parent"]
    assert r["child"]["cpu_s"] <= (3.5 if not ignore_xcpu else 9.0), r["child"]
    assert wall < 60


def test_side_state_resets_between_puzzles(tmp_path):
    """Globals, caches, an armed timer and a replaced signal handler left behind by one call must not reach the
    next puzzle: every puzzle sees a fresh module."""
    pkg = make_pkg(tmp_path, "stub_state", """
        import signal
        CALLS = []
        CACHE = {}
        def cast_candidates(task, cpu_s=15, wall_s=30, details=False):
            CALLS.append(1)
            CACHE[len(CACHE)] = task["test"][0]["input"]
            fresh = len(CALLS) == 1 and len(CACHE) == 1 and signal.getsignal(signal.SIGALRM) is signal.SIG_DFL
            signal.signal(signal.SIGALRM, lambda *a: None)
            signal.setitimer(signal.ITIMER_REAL, 1000)
            v = 1 if fresh else 9
            return {"grids": [[[v, len(CALLS)]] for _ in task["test"]], "status": "OK", "version": "stub"}
        """)
    ch = tasks(5, n_test=2)
    st, res, _ = run_side(tmp_path, pkg, ch)
    assert st["done"] == 5 and st["answered_outputs"] == 10
    assert all(r["grids"] == [[[1, 1]], [[1, 1]]] for r in res.values())
    rev = dict(reversed(list(ch.items())))
    _, res2, _ = run_side(tmp_path, pkg, rev, tag="_reversed")
    assert {k: v["grids"] for k, v in res2.items()} == {k: v["grids"] for k, v in res.items()}


@pytest.mark.parametrize("body,status", [
    ("return {'grids': [[[1]]], 'status': 'OK'}", "MALFORMED_SHAPE"),                    # wrong count (2 tests)
    ("return {'grids': [[[1, 2], [3]], [[10]]], 'status': 'OK'}", "OK"),                 # both malformed
    ("return {'grids': [[[True]], 'x'], 'status': 'OK'}", "OK"),
    ("return {'grids': [[[0] * 31], [[1]] * 31], 'status': 'OK'}", "OK"),
    ("return {'grids': [[[1]], [[2]]], 'status': 'OK', 'pad': 'x' * (5 << 20)}", "KILLED_TOO_BIG"),
    ("raise RuntimeError('boom')", "ERROR_CHILD"),
    ("import os; os._exit(7)", "ERROR_NO_REPLY"),
    ("import sys; sys.exit(0)", "ERROR_CHILD"),
])
def test_side_malformed_and_errors_give_no_answer(tmp_path, body, status):
    pkg = make_pkg(tmp_path, "stub_bad", f"""
        def cast_candidates(task, cpu_s=15, wall_s=30, details=False):
            {body}
        """)
    st, res, _ = run_side(tmp_path, pkg, tasks(1, n_test=2))
    r = res["s000"]
    assert r["status"] == status and r["grids"] == [None, None], r
    assert st["answered_outputs"] == 0
    sub_a = {"s000": [{"attempt_1": g(1), "attempt_2": g(1)}] * 2}
    b, _ = M.merge(sub_a, tasks(1, n_test=2), res, tier=0)
    assert b == sub_a


def test_side_total_budget(tmp_path):
    pkg = make_pkg(tmp_path, "stub_slow", """
        import time
        def cast_candidates(task, cpu_s=15, wall_s=30, details=False):
            time.sleep(1.5)
            return {'grids': [[[1]]], 'status': 'OK'}
        """)
    st, res, wall = run_side(tmp_path, pkg, tasks(6), deadline_s=5.0, wall_s=2.0, grace_s=1.0)
    assert st["stopped"] == "budget" and 1 <= st["done"] < 6 and len(res) == st["done"]
    assert wall < 8.0


def test_side_import_failure_is_failsafe(tmp_path):
    pkg = make_pkg(tmp_path, "stub_import", "raise ImportError('missing dependency')\n")
    st, res, _ = run_side(tmp_path, pkg, tasks(2))
    assert st["stopped"] == "error" and "ImportError" in st["error"] and res == {}


# ----- the real package through the side process ------------------------------------------------------------------
REAL = ["62593bfd", "981571dc", "0934a4d8", "2c181942", "16de56c4"]


def real_run(tmp, ids, pkg_dir, name, deadline_s=1200.0):
    ev = json.load(open(os.path.join(DATA, "arc-agi_evaluation_challenges.json")))
    ch = {k: ev[k] for k in ids if k in ev}
    chp = tmp / f"{name}.json"
    chp.write_text(json.dumps(ch))
    out = tmp / name
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([CONFIGS, pkg_dir]), CUDA_VISIBLE_DEVICES="",
               PYTHONHASHSEED=str(len(name)))
    r = subprocess.run([sys.executable, "-m", "sfb.cast_side", "--challenges", str(chp), "--out", str(out),
                        "--package", "cast_v1", "--entry", "cast_candidates", "--deadline",
                        str(time.time() + deadline_s)], cwd=str(tmp), env=env, capture_output=True, text=True,
                       timeout=1800)
    assert r.returncode == 0, r.stderr[-2000:]
    return {f[:-5]: json.loads((out / f).read_text()) for f in os.listdir(out) if f.endswith(".json") and
            f != "status.json"}


def test_real_package_order_independent_and_matches_frozen(tmp_path):
    fwd = real_run(tmp_path, REAL, CAST_PKG, "fwd")
    rev = real_run(tmp_path, list(reversed(REAL)), CAST_PKG, "reverse")
    assert {k: v["grids"] for k, v in fwd.items()} == {k: v["grids"] for k, v in rev.items()}
    alone = {}
    for k in REAL[:3]:
        alone.update(real_run(tmp_path, [k], CAST_PKG, f"alone_{k}"))
    assert {k: alone[k]["grids"] for k in alone} == {k: fwd[k]["grids"] for k in alone}
    frozen = json.load(open(FROZEN_CANDS))
    n_checked = 0
    for k, r in fwd.items():
        for j, grid in enumerate(r["grids"]):
            if grid is not None and k in frozen:
                assert grid == frozen[k]["per_test"][j][0]["grid"]
                n_checked += 1
    print(json.dumps({k: [r["status"], [x is not None for x in r["grids"]], r["child"]["cpu_s"]]
                      for k, r in fwd.items()}))
    assert n_checked >= 1
