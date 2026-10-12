"""Real-task adaptive LOO stability v1: the development recheck coordinator
(docs/CORA_REAL_TASK_LOO_STABILITY_v1_AMENDMENT_1.md), derived from the
diagnosis coordinator scripts/loo_v1_run.py.

  python scripts/loo_v1_recheck_run.py recheck            run ONCE (refuses unless the
                                                          freeze manifest matches)
  python scripts/loo_v1_recheck_run.py recheck --resume   only after a genuine interruption
                                                          (start record, no marker, no live
                                                          recorded worker; at most 2)
  python scripts/loo_v1_recheck_run.py --worker PHASE WID (spawned by the coordinator)

One coordinator (single-writer lock), 4 workers, single-threaded numerical
libraries, atomic rows, a start record with pid, start ticks, process group
and boot id. Workers run under the pilot isolation hook with the
development bundle as their only task input.
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
OUT = os.path.join(HERE, "outputs", "loo_v1")
LOG = os.path.join(HERE, "logs", "loo_v1")
MANIFEST = os.path.join(OUT, "recheck_manifest.json")
WORKERS = 4
PHASE_WALL_CAP_S = 8 * 3600
MAX_RESUMES = 2
PHASES = ("recheck",)


def rows_path(phase):
    return os.path.join(OUT, f"{phase}_rows.jsonl")


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
    return ticks is not None and start_ticks(pid) == ticks


# ------------------------------------------------------------------ worker

def worker(phase, wid):
    sys.path.insert(0, HERE)
    from cora_pilot import isolation as ISO
    ISO.install(BUNDLE)
    sys.path.insert(0, os.path.join(HERE, "src"))
    from cora_pilot import native as N
    problems = N.environment_problems()
    if problems:
        raise SystemExit(f"native environment: {problems}")
    from harness.run_harness import _set_worker_env
    _set_worker_env()
    from cora_loo import recheck as RC
    problems = RC.freeze_problems(HERE, MANIFEST, role="worker")
    if problems:
        raise SystemExit(f"recheck: freeze check failed: {problems}")
    tasks = json.load(open(BUNDLE))["tasks"]
    keys = RC.units(sorted(tasks), RC.fc_keys(HERE))
    dirs = RC.engine_dirs(os.path.join(OUT, "recheck_engine"))
    seconds = {}
    for line in open(os.path.join(HERE, "outputs", "reach_v1", "instances2_rows.jsonl")):
        if line.strip():
            r = json.loads(line)
            seconds[r["key"]] = r.get("seconds")
    rows = rows_path(phase)
    claims = os.path.join(LOG, f"{phase}_claims.json")
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
                row = RC.run_unit(key, tasks, dirs, HERE, seconds)
            except Exception as exc:                            # noqa: BLE001
                row = {"key": key, "error": f"{type(exc).__name__}: {exc}"[:500],
                       "traceback": traceback.format_exc()[-3000:], "class": "RUN_ERROR"}
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
        ISO.dump(os.path.join(LOG, f"isolation_{phase}_{wid}.json"))


# ------------------------------------------------------------------ coordinator

def worker_env():
    sys.path.insert(0, HERE)
    from cora_pilot.native import CHAIN_FLAGS
    env = {k: v for k, v in os.environ.items() if not k.startswith("ARC_")}
    env.update(PYTHONHASHSEED="0", OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1",
               PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=os.pathsep.join([HERE, os.path.join(HERE, "src"), TTI]))
    env.update(CHAIN_FLAGS)
    return env


def coordinator(phase, resume):
    sys.path.insert(0, HERE)
    from cora_loo import recheck as RC
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(LOG, exist_ok=True)
    lockf = open(os.path.join(LOG, f"coordinator_{phase}.lock"), "a+")
    try:
        fcntl.flock(lockf, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        raise SystemExit("another coordinator holds the lock")
    start = os.path.join(LOG, f"{phase}_0_start.json")
    workers_file = os.path.join(LOG, f"{phase}_0_workers.json")
    marker = os.path.join(LOG, f"{phase.upper()}_0_DONE")
    if os.path.exists(marker):
        raise SystemExit("this phase already finished")
    problems = RC.freeze_problems(HERE, MANIFEST)       # before any start record is written
    if problems:
        raise SystemExit(f"recheck: freeze check failed: {problems}")
    if os.path.exists(start) and not resume:
        raise SystemExit("start record exists: --resume only after a genuine interruption")
    if resume:
        if not os.path.exists(start):
            raise SystemExit("no start record: nothing to resume")
        if os.path.exists(workers_file):
            for w in json.load(open(workers_file))["workers"]:
                if alive(w["pid"], w["ticks"]):
                    raise SystemExit(f"recorded worker {w['pid']} is alive; not starting another writer")
        resumes = os.path.join(LOG, f"{phase}_0_resumes.jsonl")
        n = sum(1 for _ in open(resumes)) if os.path.exists(resumes) else 0
        if n >= MAX_RESUMES:
            raise SystemExit("resume limit reached")
        with open(resumes, "a") as handle:
            handle.write(json.dumps({"t": time.time(), "pid": os.getpid()}) + "\n")
    else:
        write_atomic(start, {"phase": phase, "first_start_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                             "pid": os.getpid(), "ticks": start_ticks(os.getpid()), "pgid": os.getpgid(0),
                             "boot_id": open("/proc/sys/kernel/random/boot_id").read().strip(),
                             "head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE, capture_output=True,
                                                    text=True).stdout.strip(),
                             "load": [round(x, 2) for x in os.getloadavg()],
                             "config": {"workers": WORKERS, "bundle": os.path.relpath(BUNDLE, HERE)}})
    keys = RC.units(sorted(json.load(open(BUNDLE))["tasks"]), RC.fc_keys(HERE))
    RC.engine_dirs(os.path.join(OUT, "recheck_engine"))
    write_atomic(os.path.join(LOG, f"{phase}_claims.json"), {"claimed": sorted(read_rows(rows_path(phase)))})
    procs = []
    for w in range(WORKERS):
        log = open(os.path.join(LOG, f"worker_{phase}_{w}.log"), "ab")
        procs.append(subprocess.Popen([PYTHON, os.path.abspath(__file__), "--worker", phase, str(w)],
                                      cwd=HERE, env=worker_env(), stdout=log, stderr=subprocess.STDOUT))
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
    rows = read_rows(rows_path(phase))
    missing = [k for k in keys if k not in rows]
    write_atomic(os.path.join(LOG, f"{phase}_0_record.json"),
                 {"exit_codes": codes, "rows": len(rows), "missing": missing, "units": keys, "t": time.time()})
    if not missing and all(c == 0 for c in codes):
        with open(marker, "w") as handle:
            handle.write(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()) + "\n")
        print(f"{phase}: {len(rows)} rows, done")
    else:
        print(f"{phase}: {len(rows)} rows, missing {len(missing)}, exit codes {codes}: resumable")


def main(argv):
    if argv[:1] == ["--worker"]:
        worker(argv[1], int(argv[2]))
    elif argv[:1] and argv[0] in PHASES:
        coordinator(argv[0], "--resume" in argv)
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
