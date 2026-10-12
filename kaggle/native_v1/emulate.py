"""Offline Kaggle emulation for NATIVE_BASELINE native_v1. Never uploads anything.

  python kaggle/native_v1/emulate.py fixtures   synthetic integration fixtures (multi-output, 1x1, 30x30)
  python kaggle/native_v1/emulate.py failure    forced harness failure: the fallback path
  python kaggle/native_v1/emulate.py dev60      the 60 authorized training-development tasks (inputs only)

Each mode builds a fresh Kaggle-style tree under the scratch dir given by
K_EMU_ROOT:
- input/arc-prize-2026-arc-agi-2/ holds arc-agi_test_challenges.json and
  sample_submission.json, with NO solutions of any kind;
- input/arc-native-baseline/ holds the built tarball;
- working/ is the output directory.

A socket guard (sitecustomize.py, harness subprocess only, emulation only)
makes every network attempt fail and logs it. The notebook runs exactly as
on Kaggle (K_INPUT and K_WORK point into the tree). submission.json is then
validated independently, and runtime, peak memory of the process tree and
the guard log are recorded in emu_report_<mode>.json.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
TARBALL = os.path.join(HERE, "arc_native_baseline_v1.tar.gz")
GUARD = '''import socket, os, traceback
_log = os.environ.get("K_GUARD_LOG")
def _deny(*a, **k):
    if _log:
        open(_log, "a").write("network attempt blocked: " + repr(a[:2]) + "\\n")
    raise OSError("network disabled (Kaggle emulation)")
socket.socket.connect = _deny
socket.socket.connect_ex = _deny
socket.create_connection = _deny
socket.getaddrinfo = _deny
'''


def fixtures():
    """Synthetic integration fixtures with known rules: one task with two test
    outputs (order matters), a 1x1 task, a 30x30 task, a non-square task."""
    def recolour(g, a, b):
        return [[b if v == a else v for v in row] for row in g]
    t = {}
    g1 = [[0, 1, 0], [1, 1, 0], [0, 0, 2]]
    g2 = [[1, 0], [0, 1]]
    t["fx_two_outputs"] = {"train": [{"input": g1, "output": recolour(g1, 1, 3)}, {"input": g2, "output": recolour(g2, 1, 3)}],
                           "test": [{"input": [[1, 1, 0], [0, 0, 1]]}, {"input": [[0, 1], [1, 0], [1, 1]]}]}
    t["fx_one_by_one"] = {"train": [{"input": [[4]], "output": [[4]]}, {"input": [[6]], "output": [[6]]}],
                          "test": [{"input": [[7]]}]}
    big = [[(r * 3 + c) % 2 for c in range(30)] for r in range(30)]
    t["fx_thirty"] = {"train": [{"input": big, "output": recolour(big, 1, 5)},
                                {"input": [row[::-1] for row in big], "output": recolour([row[::-1] for row in big], 1, 5)}],
                      "test": [{"input": [row[1:] + row[:1] for row in big]}]}
    ns = [[0, 2, 2, 0, 0], [0, 0, 2, 0, 0]]
    t["fx_non_square"] = {"train": [{"input": ns, "output": recolour(ns, 2, 8)}, {"input": [r[::-1] for r in ns], "output": recolour([r[::-1] for r in ns], 2, 8)}],
                          "test": [{"input": [[2, 0, 0, 2, 2], [0, 0, 0, 0, 2]]}]}
    return t


def dev60():
    bundle = json.load(open(os.path.join(ROOT, "records", "pilot_v1", "dev_bundle.json")))["tasks"]
    out = {}
    for k, task in bundle.items():
        assert all(set(c) == {"input"} for c in task["test"]), "a test output is present: refusing"
        out[k] = {"train": [{"input": p["input"], "output": p["output"]} for p in task["train"]],
                  "test": [{"input": c["input"]} for c in task["test"]]}
    return out


def validate(sub, challenges):
    problems = []
    if set(sub) != set(challenges):
        problems.append(f"task ids differ: missing {sorted(set(challenges) - set(sub))[:5]}, extra {sorted(set(sub) - set(challenges))[:5]}")
    for tid, task in challenges.items():
        entries = sub.get(tid, [])
        if not isinstance(entries, list) or len(entries) != len(task["test"]):
            problems.append(f"{tid}: {len(entries) if isinstance(entries, list) else 'non-list'} entries for {len(task['test'])} outputs")
            continue
        for i, e in enumerate(entries):
            if not isinstance(e, dict) or set(e) != {"attempt_1", "attempt_2"}:
                problems.append(f"{tid}[{i}]: keys {sorted(e) if isinstance(e, dict) else type(e).__name__}")
                continue
            for k, g in e.items():
                ok = (isinstance(g, list) and 1 <= len(g) <= 30 and all(isinstance(r, list) and len(r) == len(g[0]) for r in g)
                      and 1 <= len(g[0]) <= 30 and all(type(v) is int and 0 <= v <= 9 for r in g for v in r))
                if not ok:
                    problems.append(f"{tid}[{i}].{k}: invalid grid")
    return problems


def _tree_rss(pid):
    total = 0
    try:
        kids = subprocess.run(["ps", "-o", "pid=,rss=", "--ppid", str(pid)], capture_output=True, text=True).stdout
        total += int(open(f"/proc/{pid}/statm").read().split()[1]) * os.sysconf("SC_PAGE_SIZE") // 1024
        for line in kids.split("\n"):
            if line.strip():
                cpid, _rss = line.split()
                total += _tree_rss(int(cpid))
    except (OSError, ValueError):
        pass
    return total


def main(mode):
    emu = os.environ.get("K_EMU_ROOT") or sys.exit("set K_EMU_ROOT to a scratch directory")
    base = os.path.join(emu, mode)
    shutil.rmtree(base, ignore_errors=True)
    comp = os.path.join(base, "input", "arc-prize-2026-arc-agi-2")
    data = os.path.join(base, "input", "arc-native-baseline")
    work = os.path.join(base, "working")
    guard = os.path.join(base, "guard")
    for d in (comp, data, work, guard):
        os.makedirs(d)
    challenges = fixtures() if mode in ("fixtures", "failure") else dev60()
    json.dump(challenges, open(os.path.join(comp, "arc-agi_test_challenges.json"), "w"))
    json.dump({k: [{"attempt_1": [[0]], "attempt_2": [[0]]} for _ in v["test"]] for k, v in challenges.items()},
              open(os.path.join(comp, "sample_submission.json"), "w"))
    shutil.copy(TARBALL, data)
    open(os.path.join(guard, "sitecustomize.py"), "w").write(GUARD)
    env = {k: v for k, v in os.environ.items() if not k.startswith(("ARC_", "K_"))}
    env.update(K_INPUT=os.path.join(base, "input"), K_WORK=work, K_GUARD_DIR=guard,
               K_GUARD_LOG=os.path.join(base, "guard.log"), K_WORKERS="0" if mode == "failure" else "4")
    if os.environ.get("K_BUDGET_S"):
        env["K_BUDGET_S"] = os.environ["K_BUDGET_S"]
    t0 = time.time()
    proc = subprocess.Popen([sys.executable, os.path.join(HERE, "notebook.py")], env=env, cwd=work,
                            stdout=open(os.path.join(base, "notebook.log"), "w"), stderr=subprocess.STDOUT)
    peak = [0]

    def sample():
        while proc.poll() is None:
            peak[0] = max(peak[0], _tree_rss(proc.pid))
            time.sleep(5)
    threading.Thread(target=sample, daemon=True).start()
    proc.wait()
    wall = time.time() - t0
    sub_path = os.path.join(work, "submission.json")
    sub = json.load(open(sub_path)) if os.path.exists(sub_path) else {}
    man = json.load(open(os.path.join(work, "execution_manifest.json"))) if os.path.exists(os.path.join(work, "execution_manifest.json")) else {}
    rows = os.path.join(work, "run", "progress.jsonl")
    per_task = [json.loads(x) for x in open(rows)] if os.path.exists(rows) else []
    times = sorted(r.get("wall_s") or r.get("seconds") or r.get("elapsed_s") or 0 for r in per_task)
    report = {"mode": mode, "notebook_returncode": proc.returncode, "wall_s": round(wall, 1),
              "peak_rss_mb": round(peak[0] / 1024, 1), "tasks": len(challenges),
              "test_outputs": sum(len(t["test"]) for t in challenges.values()),
              "schema_problems": validate(sub, challenges), "manifest": man,
              "network_attempts": open(env["K_GUARD_LOG"]).read().count("\n") if os.path.exists(env["K_GUARD_LOG"]) else 0,
              "per_task_s": {"n": len(times), "median": times[len(times) // 2] if times else None,
                             "max": times[-1] if times else None},
              "solutions_in_input": [f for f in os.listdir(comp) if "solution" in f],
              "tarball_sha256": hashlib.sha256(open(TARBALL, "rb").read()).hexdigest(),
              "notebook_sha256": hashlib.sha256(open(os.path.join(HERE, "notebook.py"), "rb").read()).hexdigest()}
    if mode == "fixtures":
        report["fixture_predictions"] = sub
    json.dump(report, open(os.path.join(emu, f"emu_report_{mode}.json"), "w"), indent=1, default=str)
    print(json.dumps({k: report[k] for k in ("mode", "notebook_returncode", "wall_s", "peak_rss_mb", "tasks", "test_outputs",
                                              "schema_problems", "network_attempts", "per_task_s", "solutions_in_input")}, default=str))
    print("harness:", man.get("harness_status"), "| writer:", man.get("writer"), "| validation:", man.get("validation"))


if __name__ == "__main__":
    main(sys.argv[1])
