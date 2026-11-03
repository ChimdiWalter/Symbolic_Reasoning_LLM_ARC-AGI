"""O+ v2: the side process enforces CAST v1's NEW deployment caps (45 CPU-s, 90 wall-s, grace 10 s) at process
level, even when a package disables its own timers:
- a package that sleeps forever with SIGALRM/SIGVTALRM/SIGTERM ignored is SIGKILLed by the parent at 90 + 10 s and
  reaped;
- a package that burns CPU with its timers ignored is killed by the child's RLIMIT_CPU at int(45 + 10) + 1 = 56 CPU-s;
- the next puzzle then runs normally, and no killed process survives.

Run: CUDA_VISIBLE_DEVICES= python3 -m pytest -q -p no:cacheprovider configs/tests/test_op2_caps.py
"""
import json
import os
import subprocess
import sys
import textwrap
import time

CONFIGS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

STUB = """
import os, signal, time
VERSION = 'stub'
def cast_candidates(task, cpu_s=15, wall_s=30, details=False):
    mode = task['train'][0]['input'][0][0]
    if mode == 9:                                   # an ordinary quick answer
        return {'grids': [[[1]] for _ in task['test']], 'status': 'OK'}
    open(PIDDIR + '/pid_' + str(os.getpid()), 'w').close()
    for s in (signal.SIGALRM, signal.SIGVTALRM, signal.SIGTERM):
        signal.signal(s, signal.SIG_IGN)
    if mode == 1:                                   # hang without using CPU: only the parent's wall kill stops it
        while True:
            time.sleep(1)
    x = 0                                           # burn CPU: the child's RLIMIT_CPU stops it
    while True:
        x += 1
"""


def run(tmp, modes):
    pkg = tmp / "stub_caps"
    pkg.mkdir()
    (pkg / "__init__.py").write_text(f"PIDDIR = {str(tmp)!r}\n" + textwrap.dedent(STUB))
    ch = {f"t{k}": {"train": [{"input": [[m]], "output": [[m]]}, {"input": [[m]], "output": [[m]]}],
                    "test": [{"input": [[0]]}]} for k, m in enumerate(modes)}
    (tmp / "ch.json").write_text(json.dumps(ch))
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([CONFIGS, str(tmp)]), CUDA_VISIBLE_DEVICES="")
    t0 = time.time()
    r = subprocess.run([sys.executable, "-m", "sfb.cast_side", "--challenges", str(tmp / "ch.json"), "--out",
                        str(tmp / "out"), "--package", "stub_caps", "--entry", "cast_candidates",
                        "--deadline", str(time.time() + 900), "--cpu-s", "45", "--wall-s", "90", "--grace-s", "10"],
                       cwd=str(tmp), env=env, capture_output=True, text=True, timeout=900)
    assert r.returncode == 0, r.stderr[-1500:]
    res = {k: json.loads((tmp / "out" / f"{k}.json").read_text()) for k in ch}
    return res, time.time() - t0


def gone(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    try:
        return open(f"/proc/{pid}/stat").read().split(")")[1].split()[0] == "Z"
    except OSError:
        return True


def test_wall_kill_at_100_s_then_next_puzzle_runs(tmp_path):
    res, wall = run(tmp_path, [1, 9])
    r = res["t0"]
    assert r["status"] == "KILLED_WALL" and r["child"]["killed_by_parent"] and r["child"]["signal"] == 9
    assert 99.0 <= r["child"]["wall_s"] <= 106.0, r["child"]
    assert res["t1"]["status"] == "OK" and res["t1"]["grids"] == [[[1]]]
    pids = [int(f[4:]) for f in os.listdir(tmp_path) if f.startswith("pid_")]
    assert pids and all(gone(p) for p in pids)


def test_cpu_rlimit_kill_at_56_cpu_s(tmp_path):
    res, wall = run(tmp_path, [2])
    r = res["t0"]
    assert r["status"] == "KILLED_CPU" and not r["child"]["killed_by_parent"] and r["child"]["signal"] in (24, 9)
    assert 54.0 <= r["child"]["cpu_s"] <= 63.0, r["child"]
    pids = [int(f[4:]) for f in os.listdir(tmp_path) if f.startswith("pid_")]
    assert pids and all(gone(p) for p in pids)
