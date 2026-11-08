"""Run one job with run.status, configuration, code hash and ledger rows (family CGROW, shared ledger schema).

    python -m cgrow.runjob RUN_ID KIND [--gpu] -- MODULE [ARGS...]

Writes runs/RUN_ID/run.status (start line with UTC time and pid; exit line with status, CPU-h, wall-h), and
runs/RUN_ID/config.json (argv, code sha256 over cgrow/*.py, partitions manifest sha256). Appends START and
EXIT_OK / EXIT_FAIL rows to experiments/architecture_sweep_20261026/RUN_LEDGER.jsonl. CPU = this process plus
reaped children (the sandbox worker). With --gpu the job is expected to run under outputs/locks/gpu0.lock (the
launcher takes the lock) and its wall time is recorded as gpu_wall_h.
"""
import glob
import hashlib
import json
import os
import resource
import runpy
import sys
import time
import traceback

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from cgrow import paths as P     # noqa: E402

P.ensure_import_paths()


def code_sha():
    hh = hashlib.sha256()
    for f in sorted(glob.glob(os.path.join(HERE, "cgrow", "*.py"))):
        with open(f, "rb") as fh:
            hh.update(os.path.basename(f).encode() + fh.read())
    return hh.hexdigest()


def file_sha(path):
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def cpu_now():
    a, b = resource.getrusage(resource.RUSAGE_SELF), resource.getrusage(resource.RUSAGE_CHILDREN)
    return a.ru_utime + a.ru_stime + b.ru_utime + b.ru_stime


def ledger(row):
    from harness import ledger as LG
    LG.append(row, path=P.LEDGER)


def main():
    argv = sys.argv[1:]
    run_id, kind = argv[0], argv[1]
    gpu = "--gpu" in argv[:argv.index("--")]
    mod, margs = argv[argv.index("--") + 1], argv[argv.index("--") + 2:]
    rdir = os.path.join(P.RUNS, run_id)
    os.makedirs(rdir, exist_ok=True)
    cfg = {"run_id": run_id, "kind": kind, "module": mod, "args": margs, "gpu": gpu, "code_sha256": code_sha(),
           "partitions_manifest_sha256": file_sha(os.path.join(P.PARTITIONS, "PARTITIONS_MANIFEST.json")),
           "pid": os.getpid(), "python": sys.executable}
    with P.open_write(os.path.join(rdir, "config.json")) as f:
        json.dump(cfg, f, indent=1)
    t0, c0 = time.time(), cpu_now()
    start = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with P.open_write(os.path.join(rdir, "run.status"), "a") as f:
        f.write(f"start {start} pid {os.getpid()} module {mod} args {' '.join(margs)}\n")
    base = {"run_id": run_id, "family": "CGROW", "kind": kind, "pid": os.getpid(), "log": f"runs/{run_id}/log",
            "cmd": f"python -m {mod} {' '.join(margs)}", "code_sha": cfg["code_sha256"][:20],
            "config_sha": hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()[:20],
            "data_sha": (cfg["partitions_manifest_sha256"] or "")[:20], "gpu": gpu,
            "artifact": f"experiments/capability_growth_20261027/runs/{run_id}"}
    ledger(base | {"status": "START"})
    status, note = "EXIT_OK", ""
    sys.argv = [mod] + margs
    try:
        runpy.run_module(mod, run_name="__main__", alter_sys=True)
    except SystemExit as e:
        if e.code not in (None, 0):
            status, note = "EXIT_FAIL", f"SystemExit {e.code}"
    except BaseException as e:                                  # noqa: BLE001
        status, note = "EXIT_FAIL", f"{type(e).__name__}: {e}"[:300]
        traceback.print_exc()
    try:
        from llm_writer.gridfn import sandbox as SB
        if SB._DEFAULT is not None:
            SB._DEFAULT.close()
    except Exception:                                           # noqa: BLE001
        pass
    wall_h, cpu_h = (time.time() - t0) / 3600, (cpu_now() - c0) / 3600
    end = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with P.open_write(os.path.join(rdir, "run.status"), "a") as f:
        f.write(f"exit {end} status {status} cpu_h {cpu_h:.4f} wall_h {wall_h:.4f} {note}\n")
    ledger(base | {"status": status, "wall_h": round(wall_h, 4), "cpu_h": round(cpu_h, 4),
                   "gpu_wall_h": round(wall_h, 4) if gpu else 0.0, "gpu_active_h": None,
                   "max_rss_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1), "note": note})
    sys.exit(0 if status == "EXIT_OK" else 1)


if __name__ == "__main__":
    main()
