"""Append-only RUN_LEDGER.jsonl (one JSON object per line; never rewritten) and per-family budget accounting.

Record fields: ts, run_id, family (SHARED, A1..A5), kind (prep, canary, train, screen, test, audit), status (START,
EXIT_OK, EXIT_FAIL, TERMINATED, SKIPPED, WAITING), config_sha, data_sha, code_sha, wall_h, cpu_h (process plus
reaped children), gpu_wall_h (wall time while holding gpu0.lock; 0 for CPU jobs), gpu_active_h (when the job
measures it, else null), max_rss_mb, pid, log, cmd, artifact, note. Failed runs stay in the ledger.

    python -m harness.ledger summary          # per-family totals against the campaign ceilings
"""
import fcntl
import json
import os
import sys
import time

from harness import paths as P

CEILINGS = {"gpu_h": {"SHARED": 2.0, "A1": 2.0, "A2": 2.0, "A3": 2.0, "A4": 2.0, "A5": 2.0, "RESERVE": 8.0},
            "cpu_h_portfolio": 12.0}


def append(rec, path=None):
    path = path or P.LEDGER
    rec = dict(rec)
    rec.setdefault("ts", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    line = json.dumps(rec, sort_keys=True) + "\n"
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o664)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        os.write(fd, line.encode())
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
    return rec


def read(path=None):
    path = path or P.LEDGER
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


def summary(path=None):
    tot = {}
    for r in read(path):
        if r.get("status") in ("START", "WAITING", "SKIPPED", "STAGE"):
            continue
        f = tot.setdefault(r.get("family", "?"), {"cpu_h": 0.0, "gpu_wall_h": 0.0, "gpu_active_h": 0.0, "runs": 0,
                                                  "failed": 0})
        f["cpu_h"] += r.get("cpu_h") or 0.0
        f["gpu_wall_h"] += r.get("gpu_wall_h") or 0.0
        f["gpu_active_h"] += r.get("gpu_active_h") or 0.0
        f["runs"] += 1
        f["failed"] += r.get("status") != "EXIT_OK"
    cpu = sum(v["cpu_h"] for v in tot.values())
    return {"families": tot, "cpu_h_total": round(cpu, 4), "cpu_h_ceiling": CEILINGS["cpu_h_portfolio"],
            "gpu_ceilings_h": CEILINGS["gpu_h"]}


def check_budget(family, gpu_h_needed=0.0, cpu_h_needed=0.0):
    """Raise if starting a run would exceed the family's GPU ceiling or the portfolio CPU ceiling."""
    s = summary()
    used_gpu = s["families"].get(family, {}).get("gpu_wall_h", 0.0)
    if gpu_h_needed and used_gpu + gpu_h_needed > CEILINGS["gpu_h"].get(family, 0.0):
        raise RuntimeError(f"{family} GPU ceiling: used {used_gpu:.3f} h + {gpu_h_needed} h > "
                           f"{CEILINGS['gpu_h'].get(family)} h")
    if s["cpu_h_total"] + cpu_h_needed > CEILINGS["cpu_h_portfolio"]:
        raise RuntimeError(f"portfolio CPU ceiling: {s['cpu_h_total']:.3f} + {cpu_h_needed} > 12 h")
    return s


if __name__ == "__main__":
    if sys.argv[1:] == ["summary"]:
        print(json.dumps(summary(), indent=1))
