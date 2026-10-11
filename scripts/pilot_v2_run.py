"""Real ARC growth-repair pilot v2: the reasoner side (protocol sections 6
to 9 and 14).

  python scripts/pilot_v2_run.py pilot             coordinator, run ONCE: freeze check, start
                                                   record, native, instances and cora phases,
                                                   isolation audit, composed predictions, git
                                                   commit, marker
  python scripts/pilot_v2_run.py pilot --resume    the same after a genuine interruption only
                                                   (start record, no marker, no live recorded
                                                   worker; at most 2)
  python scripts/pilot_v2_run.py --worker PHASE WID   (spawned by the coordinator)

Worker processes install the isolation audit hook before importing any
project code; their only task input is the bundle. The coordinator checks
the freeze (the workers cannot: the manifest pins files the hook forbids
them), and never opens a solutions file or the evaluator's key map.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import subprocess
import sys
import time
import traceback

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TTI = "/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_tti"
PYTHON = os.path.join(HERE, ".venv_arc2026", "bin", "python")
WORKERS = 4
PHASE_WALL_CAP_S = 8 * 3600      # per phase; past it the workers are stopped by exact pid
MAX_RESUMES = 2
BUNDLE = os.path.join(HERE, "records", "pilot_v2", "pilot_bundle.json")
OUT = os.path.join(HERE, "outputs", "pilot_v2")
LOG = os.path.join(HERE, "logs", "pilot_v2")
MARKER = os.path.join(HERE, "logs", "PILOT_V2_REASONER_DONE")
PHASES = ("native", "instances", "cora")


def paths() -> dict:
    return {"rows": {ph: os.path.join(OUT, f"{ph}_rows.jsonl") for ph in PHASES},
            "claims": {ph: os.path.join(LOG, f"{ph}_claims.json") for ph in PHASES},
            "workers": {ph: os.path.join(LOG, f"workers_{ph}.json") for ph in PHASES},
            "lock": os.path.join(LOG, "rows.lock"),
            "isolation": lambda ph, w: os.path.join(LOG, f"isolation_{ph}_{w}.json"),
            "native_dir": os.path.join(OUT, "native_engine"),
            "instances_engine": os.path.join(OUT, "instances_engine"),
            "instances_dir": os.path.join(OUT, "instances"),
            "measure_engine": os.path.join(OUT, "measure_engine"),
            "start": os.path.join(LOG, "start.json"),
            "resumes": os.path.join(LOG, "resumes.jsonl"),
            "predictions": os.path.join(OUT, "committed_predictions.json"),
            "record": os.path.join(OUT, "reasoner_record.json"),
            "commit": os.path.join(LOG, "predictions_commit.json")}


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_atomic(path, obj) -> None:
    tmp = f"{path}.tmp.{os.getpid()}"
    with open(tmp, "w") as handle:
        json.dump(obj, handle, sort_keys=True)
    os.replace(tmp, path)


def read_rows(path) -> dict:
    out = {}
    if os.path.exists(path):
        with open(path) as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
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


# --------------------------------------------------------------------------
# worker
# --------------------------------------------------------------------------

def _claim(p, phase, keys):
    with open(p["lock"], "a+") as lockf:
        fcntl.flock(lockf, fcntl.LOCK_EX)
        try:
            state = json.load(open(p["claims"][phase])) if os.path.exists(p["claims"][phase]) else {}
            done = set(read_rows(p["rows"][phase]))
            claimed = set(state.get("claimed", []))
            for k in keys:
                if k not in done and k not in claimed:
                    state.setdefault("claimed", []).append(k)
                    write_atomic(p["claims"][phase], state)
                    return k
            return None
        finally:
            fcntl.flock(lockf, fcntl.LOCK_UN)


def _append(p, phase, row):
    data = (json.dumps(row, sort_keys=True, default=str) + "\n").encode()
    with open(p["lock"], "a+") as lockf:
        fcntl.flock(lockf, fcntl.LOCK_EX)
        try:
            with open(p["rows"][phase], "ab") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
        finally:
            fcntl.flock(lockf, fcntl.LOCK_UN)


def worker(phase, wid) -> None:
    p = paths()
    sys.path.insert(0, HERE)
    from cora_pilot import isolation as ISO
    ISO.install(BUNDLE)                            # before any project import
    sys.path.insert(0, os.path.join(HERE, "src"))
    from cora_pilot import native as N
    problems = N.environment_problems()
    if problems:
        raise SystemExit(f"native environment: {problems}")
    from harness.run_harness import _set_worker_env
    _set_worker_env()
    from cora_pilot2 import reasoner as RS
    from cora_reach import measure as M
    with open(BUNDLE) as handle:
        tasks = json.load(handle)["tasks"]
    keys = sorted(tasks)
    ctx = None
    if phase == "cora":
        seconds = {k: r.get("seconds") for k, r in read_rows(p["rows"]["instances"]).items()}
        ctx = {"dirs": M.engine_dirs(p["measure_engine"]), "instances_dir": p["instances_dir"]}
    try:
        while True:
            key = _claim(p, phase, keys)
            if key is None:
                break
            t0 = time.time()
            try:
                if phase == "native":
                    row = N.run_native(key, tasks[key], p["native_dir"])
                elif phase == "instances":
                    row = RS.run_instances(key, tasks[key], os.path.join(p["instances_engine"], "object"),
                                           p["instances_dir"])
                else:
                    row = RS.run_cora(key, tasks[key], dict(ctx, donor=RS.donor(keys, key),
                                                            extract_seconds=seconds.get(key)))
            except Exception as exc:                            # noqa: BLE001
                row = {"key": key, "path_class": "RUN_ERROR", "activated": False,
                       "error": f"{type(exc).__name__}: {exc}"[:500],
                       "traceback": traceback.format_exc()[-4000:]}
            row["phase"], row["worker"], row["wall_s"] = phase, wid, round(time.time() - t0, 3)
            row["load"] = [round(x, 2) for x in os.getloadavg()]
            _append(p, phase, row)
    finally:
        ISO.dump(p["isolation"](phase, wid))


# --------------------------------------------------------------------------
# coordinator
# --------------------------------------------------------------------------

def worker_env() -> dict:
    sys.path.insert(0, HERE)
    from cora_pilot.native import CHAIN_FLAGS
    env = {k: v for k, v in os.environ.items() if not k.startswith("ARC_")}
    env.update(PYTHONHASHSEED="0", OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1",
               PYTHONDONTWRITEBYTECODE="1")
    env["PYTHONPATH"] = os.pathsep.join([HERE, os.path.join(HERE, "src"), TTI])
    env.update(CHAIN_FLAGS)                        # every phase runs the native engine
    return env


def run_phase(phase) -> dict:
    p = paths()
    #  claims restart from the finished rows (a task claimed by a worker that
    #  died before writing its row is claimed again)
    write_atomic(p["claims"][phase], {"claimed": sorted(read_rows(p["rows"][phase]))})
    procs = []
    for w in range(WORKERS):
        log = open(os.path.join(LOG, f"worker_{phase}_{w}.log"), "ab")
        procs.append(subprocess.Popen([PYTHON, os.path.abspath(__file__), "--worker", phase, str(w)],
                                      cwd=HERE, env=worker_env(), stdout=log, stderr=subprocess.STDOUT))
    write_atomic(p["workers"][phase], {"workers": [{"pid": pr.pid, "ticks": start_ticks(pr.pid)} for pr in procs],
                                       "started": time.time()})
    deadline = time.time() + PHASE_WALL_CAP_S
    codes, capped = [], False
    for pr in procs:
        try:
            codes.append(pr.wait(timeout=max(1.0, deadline - time.time())))
        except subprocess.TimeoutExpired:
            capped = True
            pr.kill()                                  # this worker's exact pid only
            codes.append(pr.wait())
    return {"pids": [pr.pid for pr in procs], "exit_codes": codes, "wall_capped": capped}


def isolation_audit() -> dict:
    sys.path.insert(0, HERE)
    from cora_pilot import isolation as ISO
    p = paths()
    out = {}
    for ph in PHASES:
        for w in range(WORKERS):
            path = p["isolation"](ph, w)
            if not os.path.exists(path):
                out[f"{ph}_{w}"] = ["isolation log missing"]
                continue
            out[f"{ph}_{w}"] = ISO.audit_log(json.load(open(path)))
    return {"problems": {k: v for k, v in out.items() if v}, "logs": sorted(out)}


def git(*args) -> str:
    return subprocess.run(["git", *args], cwd=HERE, check=True, capture_output=True, text=True).stdout.strip()


def coordinator(resume=False) -> None:
    sys.path.insert(0, HERE)
    sys.path.insert(0, os.path.join(HERE, "scripts"))
    import freeze_pilot_v2 as FZ
    p = paths()
    problems = FZ.freeze_problems("reasoner")
    if problems:
        raise SystemExit(f"FREEZE PROBLEMS: {problems}")
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(LOG, exist_ok=True)
    lockf = open(os.path.join(LOG, "coordinator.lock"), "a+")
    try:
        fcntl.flock(lockf, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        raise SystemExit("another coordinator holds the lock")
    if os.path.exists(MARKER):
        raise SystemExit("the pilot reasoner already finished; it runs once")
    if os.path.exists(p["start"]) and not resume:
        raise SystemExit("start record exists: use --resume only after a genuine interruption")
    if resume:
        if not os.path.exists(p["start"]):
            raise SystemExit("no start record: nothing to resume")
        for ph in PHASES:
            if os.path.exists(p["workers"][ph]):
                for w in json.load(open(p["workers"][ph]))["workers"]:
                    if w["ticks"] is not None and start_ticks(w["pid"]) == w["ticks"]:
                        raise SystemExit(f"recorded worker {w['pid']} is alive; not starting another writer")
        n = sum(1 for _ in open(p["resumes"])) if os.path.exists(p["resumes"]) else 0
        if n >= MAX_RESUMES:
            raise SystemExit("resume limit reached")
        with open(p["resumes"], "a") as handle:
            handle.write(json.dumps({"t": time.time(), "pid": os.getpid()}) + "\n")
    else:
        write_atomic(p["start"], {"utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "t": time.time(),
                                  "pid": os.getpid(), "ticks": start_ticks(os.getpid()), "pgid": os.getpgid(0),
                                  "head": git("rev-parse", "HEAD"), "bundle_sha256": sha256_file(BUNDLE),
                                  "boot_id": open("/proc/sys/kernel/random/boot_id").read().strip(),
                                  "load": [round(x, 2) for x in os.getloadavg()], "workers": WORKERS})
    from cora_pilot import native as N
    from cora_reach import measure as M
    N.prepare_object_dir(p["native_dir"])          # once, before the workers start
    N.prepare_object_dir(p["instances_engine"])
    M.engine_dirs(p["measure_engine"])
    t0 = time.time()
    results = {}
    for ph in PHASES:
        results[ph] = run_phase(ph)
        results[ph]["seconds"] = round(time.time() - t0, 1)
    iso = isolation_audit()
    keys = sorted(json.load(open(BUNDLE))["tasks"])
    rows = {ph: read_rows(p["rows"][ph]) for ph in PHASES}
    record = {"phases": results, "isolation": iso, "seconds": round(time.time() - t0, 1),
              "rows": {ph: len(rows[ph]) for ph in PHASES},
              "missing": {ph: [k for k in keys if k not in rows[ph]] for ph in PHASES}}
    if any(record["missing"][ph] for ph in PHASES) or any(
            c != 0 for r in results.values() for c in r["exit_codes"]):
        write_atomic(os.path.join(LOG, "interrupted.json"), record)
        raise SystemExit("rows missing or a worker failed: resumable, no commit")
    from cora_pilot2 import reasoner as RS
    tasks = json.load(open(BUNDLE))["tasks"]
    preds = RS.compose(tasks, rows["native"], rows["cora"])
    with open(p["predictions"], "w") as handle:
        json.dump(preds, handle, sort_keys=True)
    record["predictions_sha256"] = sha256_file(p["predictions"])
    record["rows_sha256"] = {ph: sha256_file(p["rows"][ph]) for ph in PHASES}
    record["bundle_sha256"] = sha256_file(BUNDLE)
    write_atomic(p["record"], record)
    files = [p["predictions"], p["record"], p["start"]] + [p["rows"][ph] for ph in PHASES] + \
        [p["isolation"](ph, w) for ph in PHASES for w in range(WORKERS)] + \
        sorted(os.path.join(p["instances_dir"], f) for f in os.listdir(p["instances_dir"]))
    files = [f for f in files if os.path.exists(f)]
    git("add", "-f", *files)
    git("commit", "-q", "-m", "Adding the real ARC growth-repair pilot v2 reasoner predictions, rows, failure "
                              "evidence and isolation logs, committed before any target is read", "--", *files)
    commit = git("rev-parse", "HEAD")
    write_atomic(p["commit"], {"commit": commit, "predictions_sha256": record["predictions_sha256"],
                               "t": time.time()})
    with open(MARKER, "w") as handle:
        handle.write(commit + "\n")
    print(f"reasoner done; predictions committed at {commit}")


def main(argv) -> None:
    if argv[:1] == ["--worker"]:
        worker(argv[1], int(argv[2]))
    elif argv[:1] == ["pilot"]:
        coordinator(resume="--resume" in argv)
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
