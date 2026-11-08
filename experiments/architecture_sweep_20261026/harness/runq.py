"""Restartable, detached run queue. A run is skipped ONLY when a completed artifact (EXIT_OK) exists whose config,
data and code hashes all match; anything else (no record, failure, changed hash) runs again.

Launch (returns at once; the run survives the session):
    python -m harness.runq launch --name a1_train_v1 --family A1 --kind train [--gpu] \
        --config a1/cfg_v1.json --data runs/episodes_v1 --code a1 -- <python> a1/train.py --cfg a1/cfg_v1.json
It writes runs/<name>/{cmd.json, hashes.json, START, launcher.pid}, then starts
    setsid nohup sh scripts/with_cpu_slot.sh [flock gpu0.lock] <python> -m harness.runq exec <name> > runs/<name>/log
`exec` (inside both locks) waits for enough free host memory, runs the command as a child, forwards SIGTERM/SIGINT
(the child saves its checkpoint), and writes runs/<name>/EXIT (status, rc, cpu_h, wall_h) plus a ledger record.
Restart = run the same launch command again (the child resumes from its own checkpoint).
    python -m harness.runq status            # every run folder: START / EXIT / alive pid
"""
import argparse
import hashlib
import json
import os
import resource
import signal
import subprocess
import sys
import time

from harness import ledger as LG
from harness import paths as P

MEM_GB = {"gpu": 3.0, "cpu": 1.2}


def sha_paths(paths, exts=None):
    h = hashlib.sha256()
    for p in sorted(paths):
        ap = p if os.path.isabs(p) else os.path.join(P.EXP, p)
        files = []
        if os.path.isdir(ap):
            for root, dirs, fs in os.walk(ap):            # inside the campaign folder only (callers pass its paths)
                dirs[:] = sorted(d for d in dirs if d != "__pycache__")
                files += [os.path.join(root, f) for f in sorted(fs) if exts is None or f.endswith(exts)]
        elif os.path.exists(ap):
            files = [ap]
        for f in files:
            h.update(os.path.relpath(f, P.EXP).encode())
            with open(f, "rb") as fh:
                h.update(hashlib.sha256(fh.read()).digest())
    return h.hexdigest()[:20]


def run_dir(name):
    return os.path.join(P.RUNS, name)


def mem_available_gb():
    with open("/proc/meminfo") as f:
        for line in f:
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) / 1e6
    return 0.0


def should_skip(exit_path, hashes):
    """True only for a completed (EXIT_OK) artifact whose config, data and code hashes ALL match."""
    if not os.path.exists(exit_path):
        return False
    e = json.load(open(exit_path))
    return e.get("status") == "EXIT_OK" and all(e.get(k) == v for k, v in hashes.items())


def launch(a):
    d = run_dir(a.name)
    os.makedirs(d, exist_ok=True)
    hashes = {"config_sha": sha_paths(a.config or []), "data_sha": sha_paths(a.data or []),
              "code_sha": sha_paths(["harness"] + (a.code or []), exts=(".py",))}
    ex = os.path.join(d, "EXIT")
    if os.path.exists(ex):
        if should_skip(ex, hashes):
            LG.append({"run_id": a.name, "family": a.family, "kind": a.kind, "status": "SKIPPED", **hashes,
                       "note": "completed artifact with matching config/data/code hashes"})
            print("SKIPPED (hashes match a completed run)", a.name)
            return
        os.rename(ex, ex + f".prev{int(time.time())}")
    json.dump({"cmd": a.cmd, "family": a.family, "kind": a.kind, "gpu": a.gpu, **hashes},
              open(os.path.join(d, "cmd.json"), "w"), indent=1)
    inner = [P.PYTHON, "-m", "harness.runq", "exec", a.name]
    if a.gpu:
        inner = ["flock", P.GPU0_LOCK] + inner
    log = os.path.join(d, "log")
    with open(log, "ab") as lf:
        p = subprocess.Popen(["setsid", "nohup", "sh", os.path.join(P.REPO, "scripts", "with_cpu_slot.sh")] + inner,
                             cwd=P.EXP, stdout=lf, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                             start_new_session=True, env=dict(os.environ, PYTHONPATH=P.EXP))
    open(os.path.join(d, "launcher.pid"), "w").write(str(p.pid))
    open(os.path.join(d, "START"), "w").write(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()) + "\n")
    LG.append({"run_id": a.name, "family": a.family, "kind": a.kind, "status": "START", **hashes, "pid": p.pid,
               "log": os.path.relpath(log, P.EXP), "cmd": " ".join(a.cmd), "gpu": a.gpu})
    print("launched", a.name, "pid", p.pid, "log", log)


def execute(name):
    d = run_dir(name)
    c = json.load(open(os.path.join(d, "cmd.json")))
    need = MEM_GB["gpu" if c["gpu"] else "cpu"]
    waited = 0
    while mem_available_gb() < need:
        if waited == 0:
            LG.append({"run_id": name, "family": c["family"], "kind": c["kind"], "status": "WAITING",
                       "note": f"host MemAvailable {mem_available_gb():.2f} GB < {need} GB"})
        time.sleep(60)
        waited += 60
    t0 = time.time()
    open(os.path.join(d, "exec.pid"), "w").write(str(os.getpid()))
    env = dict(os.environ, PYTHONPATH=P.EXP, RUNQ_DIR=d, OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1",
               CUDA_VISIBLE_DEVICES="0" if c["gpu"] else "")
    child = subprocess.Popen(c["cmd"], cwd=P.EXP, env=env)
    open(os.path.join(d, "child.pid"), "w").write(str(child.pid))
    got = {}

    def fwd(signum, frame):                               # noqa: ARG001
        got["sig"] = signum
        child.send_signal(signal.SIGTERM)
    signal.signal(signal.SIGTERM, fwd)
    signal.signal(signal.SIGINT, fwd)
    rc = child.wait()
    ru = resource.getrusage(resource.RUSAGE_CHILDREN)
    wall = (time.time() - t0) / 3600.0
    status = "TERMINATED" if got else ("EXIT_OK" if rc == 0 else "EXIT_FAIL")
    rec = {"run_id": name, "family": c["family"], "kind": c["kind"], "status": status, "rc": rc,
           "config_sha": c["config_sha"], "data_sha": c["data_sha"], "code_sha": c["code_sha"],
           "wall_h": round(wall, 5), "cpu_h": round((ru.ru_utime + ru.ru_stime) / 3600.0, 5),
           "gpu_wall_h": round(wall, 5) if c["gpu"] else 0.0, "max_rss_mb": round(ru.ru_maxrss / 1024.0, 1),
           "pid": child.pid, "log": os.path.relpath(os.path.join(d, "log"), P.EXP), "cmd": " ".join(c["cmd"])}
    act = os.path.join(d, "gpu_active_h.txt")
    if os.path.exists(act):
        rec["gpu_active_h"] = float(open(act).read().strip() or 0)
    json.dump(rec, open(os.path.join(d, "EXIT"), "w"), indent=1)
    LG.append(rec)
    return rc


def alive(pid):
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, ValueError):
        return False


def status():
    if not os.path.isdir(P.RUNS):
        return
    for n in sorted(os.listdir(P.RUNS)):
        d = run_dir(n)
        ex = os.path.join(d, "EXIT")
        st = json.load(open(ex))["status"] if os.path.exists(ex) else "RUNNING_OR_QUEUED"
        pid = open(os.path.join(d, "child.pid")).read().strip() if os.path.exists(os.path.join(d, "child.pid")) else ""
        print(f"{n:32s} {st:18s} child_pid={pid} alive={alive(pid) if pid else None}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="op", required=True)
    la = sub.add_parser("launch")
    la.add_argument("--name", required=True)
    la.add_argument("--family", required=True)
    la.add_argument("--kind", required=True)
    la.add_argument("--gpu", action="store_true")
    la.add_argument("--config", nargs="*")
    la.add_argument("--data", nargs="*")
    la.add_argument("--code", nargs="*")
    la.add_argument("cmd", nargs=argparse.REMAINDER)
    ex = sub.add_parser("exec")
    ex.add_argument("name")
    sub.add_parser("status")
    a = ap.parse_args()
    if a.op == "launch":
        a.cmd = [x for x in a.cmd if x != "--"] if a.cmd[:1] == ["--"] else a.cmd
        launch(a)
    elif a.op == "exec":
        sys.exit(execute(a.name))
    else:
        status()


if __name__ == "__main__":
    main()
