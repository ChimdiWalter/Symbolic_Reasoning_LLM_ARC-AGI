"""Real-task reach v1 coordinator (docs/CORA_REAL_TASK_REACH_DEV_v1.md).

  python scripts/reach_v1_run.py census            native failure census, all 60 dev tasks
  python scripts/reach_v1_run.py census --resume   only after a genuine interruption
  python scripts/reach_v1_run.py census --limit K  engineering smoke on the first K keys
  python scripts/reach_v1_run.py --worker PHASE WID LIMIT   (spawned by the coordinator)

One coordinator (single-writer lock), at most four workers, single-threaded
numerical libraries, atomic per-task rows, a start record with pid, start
ticks, process group and boot id, finite resume rule. Workers run under the
pilot isolation hook with the development bundle as their only task input.
"""
from __future__ import annotations

import fcntl
import json
import os
import subprocess
import sys
import time
import traceback

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TTI = "/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_tti"
PYTHON = os.path.join(HERE, ".venv_arc2026", "bin", "python")
BUNDLE = os.path.join(HERE, "records", "pilot_v1", "dev_bundle.json")
OUT = os.path.join(HERE, "outputs", "reach_v1")
LOG = os.path.join(HERE, "logs", "reach_v1")
WORKERS = 4
PHASE_WALL_CAP_S = 6 * 3600
MAX_RESUMES = 2
PHASES = {"census": {"native_env": True}}


def rows_path(phase, limit):
    return os.path.join(OUT, f"{phase}_rows.jsonl" if not limit else f"{phase}_smoke{limit}_rows.jsonl")


def write_atomic(path, obj):
    tmp = f"{path}.tmp.{os.getpid()}"
    with open(tmp, "w") as handle:
        json.dump(obj, handle, sort_keys=True)
    os.replace(tmp, path)


def read_rows(path):
    out = {}
    if os.path.exists(path):
        for line in open(path):
            line = line.strip()
            if line:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                out[r["key"]] = r
    return out


def start_ticks(pid):
    try:
        return int(open(f"/proc/{pid}/stat").read().rsplit(")", 1)[1].split()[19])
    except (OSError, IndexError, ValueError):
        return None


def alive(pid, ticks):
    return start_ticks(pid) is not None and start_ticks(pid) == ticks


# ------------------------------------------------------------------ worker

def worker(phase, wid, limit):
    sys.path.insert(0, HERE)
    from cora_pilot import isolation as ISO
    ISO.install(BUNDLE)
    if PHASES[phase]["native_env"]:
        sys.path.insert(0, os.path.join(HERE, "src"))
        from cora_pilot import native as N
        problems = N.environment_problems()
        if problems:
            raise SystemExit(f"native environment: {problems}")
        from harness.run_harness import _set_worker_env
        _set_worker_env()
    from cora_reach import census as C
    tasks = json.load(open(BUNDLE))["tasks"]
    keys = sorted(tasks)[:limit] if limit else sorted(tasks)
    rows = rows_path(phase, limit)
    claims = os.path.join(LOG, f"{phase}_claims_{limit}.json")
    lock = os.path.join(LOG, "rows.lock")
    try:
        while True:
            with open(lock, "a+") as lk:
                fcntl.flock(lk, fcntl.LOCK_EX)
                state = json.load(open(claims)) if os.path.exists(claims) else {"claimed": []}
                key = next((k for k in keys if k not in state["claimed"]), None)
                if key is not None:
                    state["claimed"].append(key)
                    write_atomic(claims, state)
                fcntl.flock(lk, fcntl.LOCK_UN)
            if key is None:
                break
            t0 = time.time()
            try:
                row = C.run_census(key, tasks[key], os.path.join(OUT, "native_engine"),
                                   os.path.join(OUT, "census_programs"))
            except Exception as exc:                            # noqa: BLE001
                row = {"key": key, "error": f"{type(exc).__name__}: {exc}"[:500],
                       "traceback": traceback.format_exc()[-3000:], "diagnosis": {"class": "RUN_ERROR"}}
            row.update(worker=wid, wall_s=round(time.time() - t0, 2),
                       load=[round(x, 2) for x in os.getloadavg()])
            data = (json.dumps(row, sort_keys=True, default=str) + "\n").encode()
            with open(lock, "a+") as lk:
                fcntl.flock(lk, fcntl.LOCK_EX)
                with open(rows, "ab") as handle:
                    handle.write(data)
                    handle.flush()
                    os.fsync(handle.fileno())
                fcntl.flock(lk, fcntl.LOCK_UN)
    finally:
        ISO.dump(os.path.join(LOG, f"isolation_{phase}_{limit}_{wid}.json"))


# ------------------------------------------------------------------ coordinator

def worker_env(phase):
    env = {k: v for k, v in os.environ.items() if not k.startswith("ARC_")}
    env.update(PYTHONHASHSEED="0", OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1",
               PYTHONDONTWRITEBYTECODE="1",
               PYTHONPATH=os.pathsep.join([HERE, os.path.join(HERE, "src"), TTI]))
    if PHASES[phase]["native_env"]:
        sys.path.insert(0, HERE)
        from cora_pilot.native import CHAIN_FLAGS
        env.update(CHAIN_FLAGS)
    return env


def coordinator(phase, resume, limit):
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(LOG, exist_ok=True)
    lockf = open(os.path.join(LOG, f"coordinator_{phase}.lock"), "a+")
    try:
        fcntl.flock(lockf, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        raise SystemExit("another coordinator holds the lock")
    start = os.path.join(LOG, f"{phase}_{limit}_start.json")
    workers_file = os.path.join(LOG, f"{phase}_{limit}_workers.json")
    marker = os.path.join(LOG, f"{phase.upper()}_{limit}_DONE")
    if os.path.exists(marker):
        raise SystemExit("this phase already finished")
    if os.path.exists(start) and not resume:
        raise SystemExit("start record exists: --resume only after a genuine interruption")
    if resume:
        if os.path.exists(workers_file):
            for w in json.load(open(workers_file))["workers"]:
                if alive(w["pid"], w["ticks"]):
                    raise SystemExit(f"recorded worker {w['pid']} is alive; not starting another writer")
        resumes = os.path.join(LOG, f"{phase}_{limit}_resumes.jsonl")
        n = sum(1 for _ in open(resumes)) if os.path.exists(resumes) else 0
        if n >= MAX_RESUMES:
            raise SystemExit("resume limit reached")
        with open(resumes, "a") as handle:
            handle.write(json.dumps({"t": time.time(), "pid": os.getpid()}) + "\n")
    else:
        write_atomic(start, {"phase": phase, "limit": limit, "first_start_utc": time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "pid": os.getpid(), "ticks": start_ticks(os.getpid()),
            "pgid": os.getpgid(0), "boot_id": open("/proc/sys/kernel/random/boot_id").read().strip(),
            "head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE, capture_output=True,
                                   text=True).stdout.strip(),
            "config": {"workers": WORKERS, "bundle": os.path.relpath(BUNDLE, HERE),
                       "native_env": PHASES[phase]["native_env"]}})
    #  claims restart from the finished rows
    write_atomic(os.path.join(LOG, f"{phase}_claims_{limit}.json"),
                 {"claimed": sorted(read_rows(rows_path(phase, limit)))})
    if PHASES[phase]["native_env"]:
        sys.path.insert(0, HERE)
        from cora_pilot import native as N
        N.prepare_object_dir(os.path.join(OUT, "native_engine"))
    procs = []
    for w in range(WORKERS):
        log = open(os.path.join(LOG, f"worker_{phase}_{limit}_{w}.log"), "ab")
        procs.append(subprocess.Popen([PYTHON, os.path.abspath(__file__), "--worker", phase, str(w), str(limit)],
                                      cwd=HERE, env=worker_env(phase), stdout=log, stderr=subprocess.STDOUT))
    write_atomic(workers_file, {"workers": [{"pid": p.pid, "ticks": start_ticks(p.pid)} for p in procs],
                                "coordinator": os.getpid()})
    deadline = time.time() + PHASE_WALL_CAP_S
    codes = []
    for p in procs:
        try:
            codes.append(p.wait(timeout=max(1.0, deadline - time.time())))
        except subprocess.TimeoutExpired:
            p.kill()                                    # this worker's exact pid only
            codes.append(p.wait())
    rows = read_rows(rows_path(phase, limit))
    tasks = json.load(open(BUNDLE))["tasks"]
    keys = sorted(tasks)[:limit] if limit else sorted(tasks)
    missing = [k for k in keys if k not in rows]
    write_atomic(os.path.join(LOG, f"{phase}_{limit}_record.json"),
                 {"exit_codes": codes, "rows": len(rows), "missing": missing, "t": time.time()})
    if not missing and all(c == 0 for c in codes):
        with open(marker, "w") as handle:
            handle.write(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()) + "\n")
        print(f"{phase}: {len(rows)} rows, done")
    else:
        print(f"{phase}: {len(rows)} rows, missing {len(missing)}, exit codes {codes}: resumable")


def main(argv):
    if argv[:1] == ["--worker"]:
        worker(argv[1], int(argv[2]), int(argv[3]))
    elif argv[:1] and argv[0] in PHASES:
        limit = int(argv[argv.index("--limit") + 1]) if "--limit" in argv else 0
        coordinator(argv[0], "--resume" in argv, limit)
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
