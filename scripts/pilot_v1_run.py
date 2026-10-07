"""Real ARC pilot v1: the reasoner side (protocol sections 6 to 9).

  python scripts/pilot_v1_run.py pilot             coordinator, run once: freeze check,
                                                   start record, native phase, CORA
                                                   phase, isolation audit, composed
                                                   predictions, git commit, marker
  python scripts/pilot_v1_run.py pilot --resume    the same after a genuine interruption
  python scripts/pilot_v1_run.py dev [cora|native] [LIMIT]
                                                   development dry run on the frozen
                                                   development bundle: reasoner only,
                                                   never committed, never scored
  python scripts/pilot_v1_run.py --worker MODE PHASE WID   (spawned by the coordinator)

Worker processes install the isolation audit hook before importing any
project code; their only task input is the bundle. The coordinator never
opens a solutions file or the evaluator's key map.
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
DEV_NATIVE_DEFAULT = 6
PHASE_WALL_CAP_S = 8 * 3600      # per phase; past it the workers are stopped by exact pid

MODES = {
    "pilot": {"bundle": os.path.join(HERE, "records", "pilot_v1", "pilot_bundle.json"),
              "out": os.path.join(HERE, "outputs", "pilot_v1"),
              "log": os.path.join(HERE, "logs", "pilot_v1")},
    "dev": {"bundle": os.path.join(HERE, "records", "pilot_v1", "dev_bundle.json"),
            "out": os.path.join(HERE, "outputs", "pilot_v1_dev"),
            "log": os.path.join(HERE, "logs", "pilot_v1_dev")},
}
MARKER = os.path.join(HERE, "logs", "PILOT_V1_REASONER_DONE")
PHASES = ("native", "cora")


def paths(mode):
    m = MODES[mode]
    return {"bundle": m["bundle"], "out": m["out"], "log": m["log"],
            "rows": {ph: os.path.join(m["out"], f"{ph}_rows.jsonl") for ph in PHASES},
            "claims": {ph: os.path.join(m["log"], f"{ph}_claims.json") for ph in PHASES},
            "lock": os.path.join(m["log"], "rows.lock"),
            "isolation": lambda ph, w: os.path.join(m["log"], f"isolation_{ph}_{w}.json"),
            "native_dir": os.path.join(m["out"], "native_engine"),
            "start": os.path.join(m["log"], "start.json"),
            "resumes": os.path.join(m["log"], "resumes.jsonl"),
            "predictions": os.path.join(m["out"], "committed_predictions.json"),
            "record": os.path.join(m["out"], "reasoner_record.json"),
            "commit": os.path.join(m["log"], "predictions_commit.json")}


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_atomic(path, obj) -> None:
    tmp = path + ".tmp"
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
    data = (json.dumps(row, sort_keys=True) + "\n").encode()
    with open(p["lock"], "a+") as lockf:
        fcntl.flock(lockf, fcntl.LOCK_EX)
        try:
            with open(p["rows"][phase], "ab") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
        finally:
            fcntl.flock(lockf, fcntl.LOCK_UN)


def worker(mode, phase, wid) -> None:
    p = paths(mode)
    sys.path.insert(0, HERE)
    from cora_pilot import isolation as ISO
    ISO.install(p["bundle"])                       # before any project import
    if phase == "native":
        sys.path.insert(0, os.path.join(HERE, "src"))
        from cora_pilot import native as N
        problems = N.environment_problems()
        if problems:
            raise SystemExit(f"native environment: {problems}")
        from harness.run_harness import _set_worker_env
        _set_worker_env()
    else:
        from cora_pilot import reasoner as RS
    with open(p["bundle"]) as handle:
        bundle = json.load(handle)
    tasks = bundle["tasks"]
    keys = sorted(tasks)
    limit = int(os.environ.get("PILOT_DEV_LIMIT", "0") or 0)
    if limit:
        keys = keys[:limit]
    try:
        while True:
            key = _claim(p, phase, keys)
            if key is None:
                break
            t0 = time.time()
            try:
                if phase == "native":
                    row = N.run_native(key, tasks[key], p["native_dir"])
                else:
                    donor = RS.donor_failure(tasks, key)
                    row = RS.run_cora(key, tasks[key], donor["failure"])
                    row["donor"] = donor["donor"]
                    row["donor_error"] = donor.get("error")
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

def worker_env(phase) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("ARC_")}
    env.update(PYTHONHASHSEED="0", OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1",
               PYTHONDONTWRITEBYTECODE="1")
    env["PYTHONPATH"] = os.pathsep.join([HERE, os.path.join(HERE, "src"), TTI])
    if phase == "native":
        from cora_pilot.native import CHAIN_FLAGS
        env.update(CHAIN_FLAGS)
    return env


def run_phase(mode, phase, n_workers, extra_env=None) -> dict:
    p = paths(mode)
    #  claims restart from the finished rows (a task claimed by a worker that
    #  died before writing its row is claimed again)
    write_atomic(p["claims"][phase], {"claimed": sorted(read_rows(p["rows"][phase]))})
    procs = []
    for w in range(n_workers):
        env = worker_env(phase)
        env.update(extra_env or {})
        log = open(os.path.join(p["log"], f"worker_{phase}_{w}.log"), "ab")
        procs.append(subprocess.Popen([PYTHON, os.path.abspath(__file__), "--worker", mode, phase, str(w)],
                                      cwd=HERE, env=env, stdout=log, stderr=subprocess.STDOUT))
    pids = [pr.pid for pr in procs]
    write_atomic(os.path.join(p["log"], f"workers_{phase}.json"), {"pids": pids, "started": time.time()})
    deadline = time.time() + PHASE_WALL_CAP_S
    codes, capped = [], False
    for pr in procs:
        try:
            codes.append(pr.wait(timeout=max(1.0, deadline - time.time())))
        except subprocess.TimeoutExpired:
            capped = True
            pr.kill()                                  # this worker's exact pid only
            codes.append(pr.wait())
    return {"pids": pids, "exit_codes": codes, "wall_capped": capped}


def isolation_audit(mode, n_workers, phases=PHASES) -> dict:
    sys.path.insert(0, HERE)
    from cora_pilot import isolation as ISO
    p = paths(mode)
    out = {}
    for ph in phases:
        for w in range(n_workers):
            path = p["isolation"](ph, w)
            if not os.path.exists(path):
                out[f"{ph}_{w}"] = ["isolation log missing"]
                continue
            out[f"{ph}_{w}"] = ISO.audit_log(json.load(open(path)))
    return {"problems": {k: v for k, v in out.items() if v}, "logs": sorted(out)}


def system_attempts(native_row, cora_row, n_test) -> list:
    """The deployable output (protocol section 7): native attempts, with an
    activated CORA prediction taking attempt 2 when native has an attempt 1
    for that test input, and attempt 1 otherwise (native attempt 2 kept)."""
    a1 = (native_row or {}).get("attempt_1") or [None] * n_test
    a2 = (native_row or {}).get("attempt_2") or [None] * n_test
    cp = (cora_row or {}).get("cora_prediction") if (cora_row or {}).get("activated") else None
    out = []
    for i in range(n_test):
        if cp is not None and cp[i] is not None:
            out.append([a1[i], cp[i]] if a1[i] is not None else [cp[i], a2[i]])
        else:
            out.append([a1[i], a2[i]])
    return out


def compose(mode) -> dict:
    p = paths(mode)
    bundle = json.load(open(p["bundle"]))
    nat, cor = read_rows(p["rows"]["native"]), read_rows(p["rows"]["cora"])
    preds = {}
    for k, t in sorted(bundle["tasks"].items()):
        n = len(t["test"])
        c = cor.get(k) or {}
        preds[k] = {
            "native": {"attempt_1": (nat.get(k) or {}).get("attempt_1"),
                       "attempt_2": (nat.get(k) or {}).get("attempt_2")},
            "kstar_prime_alone": (c.get("kstar_prime_alone") or {}).get("predictions"),
            "cora_with_e": (c.get("with_e") or {}).get("predictions"),
            "activated": bool(c.get("activated")),
            "cora_prediction": c.get("cora_prediction"),
            "removed": (c.get("removed") or {}).get("predictions"),
            "matched": (c.get("matched") or {}).get("predictions"),
            "controls": {arm: ((c.get("controls") or {}).get(arm) or {}).get("with_e", {}).get("predictions")
                         for arm in ("DEMO_ONLY", "SHUFFLED_FRONTIER")},
            "system": system_attempts(nat.get(k), c, n)}
    return preds


def git(*args) -> str:
    return subprocess.run(["git", *args], cwd=HERE, check=True, capture_output=True, text=True).stdout.strip()


def coordinator(mode, resume=False, dev_args=()) -> None:
    sys.path.insert(0, HERE)
    p = paths(mode)
    os.makedirs(p["out"], exist_ok=True)
    os.makedirs(p["log"], exist_ok=True)
    if mode == "pilot":
        sys.path.insert(0, os.path.join(HERE, "scripts"))
        import freeze_pilot_v1 as FZ
        problems = FZ.freeze_problems()
        if problems:
            raise SystemExit(f"FREEZE PROBLEMS: {problems}")
        if os.path.exists(MARKER):
            raise SystemExit("the pilot reasoner already finished; it runs once")
        if os.path.exists(p["start"]) and not resume:
            raise SystemExit("start record exists: use --resume only after a genuine interruption")
        if resume:
            with open(p["resumes"], "a") as handle:
                handle.write(json.dumps({"t": time.time(), "pid": os.getpid()}) + "\n")
        else:
            write_atomic(p["start"], {"t": time.time(), "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                      "pid": os.getpid(), "head": git("rev-parse", "HEAD"),
                                      "bundle_sha256": sha256_file(p["bundle"]),
                                      "boot_id": open("/proc/sys/kernel/random/boot_id").read().strip()})
        phases = list(PHASES)
        extra = {}
    else:
        phases = [dev_args[0]] if dev_args and dev_args[0] in PHASES else list(PHASES)
        limit = dev_args[1] if len(dev_args) > 1 else None
        extra = {"PILOT_DEV_LIMIT": str(limit)} if limit else {}
    t0 = time.time()
    results = {}
    if "native" in phases:
        from cora_pilot import native as N
        N.prepare_object_dir(p["native_dir"])          # once, before the workers start
    for ph in phases:
        env = dict(extra)
        if mode == "dev" and ph == "native" and "PILOT_DEV_LIMIT" not in env:
            env["PILOT_DEV_LIMIT"] = str(DEV_NATIVE_DEFAULT)
        results[ph] = run_phase(mode, ph, WORKERS, env)
        results[ph]["seconds"] = round(time.time() - t0, 1)
    iso = isolation_audit(mode, WORKERS, phases)
    bundle = json.load(open(p["bundle"]))
    keys = sorted(bundle["tasks"])
    rows = {ph: read_rows(p["rows"][ph]) for ph in PHASES}
    record = {"mode": mode, "phases": results, "isolation": iso, "seconds": round(time.time() - t0, 1),
              "rows": {ph: len(rows[ph]) for ph in PHASES},
              "missing": {ph: [k for k in keys if k not in rows[ph]] for ph in phases}}
    if mode == "dev":
        write_atomic(os.path.join(p["out"], "dev_record.json"), record)
        print(json.dumps({k: record[k] for k in ("rows", "seconds")}, sort_keys=True))
        return
    if any(record["missing"][ph] for ph in phases) or any(
            c != 0 for r in results.values() for c in r["exit_codes"]):
        write_atomic(os.path.join(p["log"], "interrupted.json"), record)
        raise SystemExit("rows missing or a worker failed: resumable, no commit")
    preds = compose(mode)
    with open(p["predictions"], "w") as handle:
        json.dump(preds, handle, sort_keys=True)
    record["predictions_sha256"] = sha256_file(p["predictions"])
    record["rows_sha256"] = {ph: sha256_file(p["rows"][ph]) for ph in PHASES}
    record["bundle_sha256"] = sha256_file(p["bundle"])
    write_atomic(p["record"], record)
    files = [p["predictions"], p["record"], p["rows"]["native"], p["rows"]["cora"],
             p["start"]] + [p["isolation"](ph, w) for ph in PHASES for w in range(WORKERS)]
    files = [f for f in files if os.path.exists(f)]
    git("add", "-f", *files)
    git("commit", "-q", "-m", "Adding the real ARC pilot v1 reasoner predictions, rows and isolation logs, "
                              "committed before any target is read", "--", *files)
    commit = git("rev-parse", "HEAD")
    write_atomic(p["commit"], {"commit": commit, "predictions_sha256": record["predictions_sha256"],
                               "t": time.time()})
    with open(MARKER, "w") as handle:
        handle.write(commit + "\n")
    print(f"reasoner done; predictions committed at {commit}")


def main(argv) -> None:
    if argv[:1] == ["--worker"]:
        worker(argv[1], argv[2], int(argv[3]))
    elif argv[:1] == ["pilot"]:
        coordinator("pilot", resume="--resume" in argv)
    elif argv[:1] == ["dev"]:
        coordinator("dev", dev_args=argv[1:])
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
