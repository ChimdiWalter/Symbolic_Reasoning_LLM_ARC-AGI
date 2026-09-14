"""P0.2: capture the live Step-B runner's environment while it still exists.

The gate needs to know whether the run itself had PYTHONHASHSEED and thread
limits set, and that can only be read from the running processes. Once the
runner exits the information is gone for good, and the record can only say
ENV-RUN-UNKNOWN.

For every process matched by freeze_pin.runner_processes(), it reads argv, the
executable link, the working directory, the start time and the environment
block, all from /proc. It reads nothing from the experiment's files.

SECURITY. Environment values are recorded ONLY for an allowlist of
reproducibility variables. Every other variable is COUNTED, not named, because
the record is committed and pushed and even the name of a credential variable
should not leave the machine. Each block is identified by sha256. Identical
worker environments are stored once.

It writes outputs/tti/stepB_gate/stepB_run_env.json once, with exclusive
create, and never overwrites it. The printed summary carries counts only.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cora_tti import freeze_pin as FP   # noqa: E402

RECORD_VERSION = "stepB_run_env:v1"
ALLOWED_VALUES = ("PYTHONHASHSEED", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                  "NUMEXPR_NUM_THREADS", "CUDA_VISIBLE_DEVICES", "PYTHONPATH",
                  "PYTHONDONTWRITEBYTECODE", "PYTHONOPTIMIZE", "PYTHONUNBUFFERED",
                  "VIRTUAL_ENV", "CONDA_DEFAULT_ENV", "LANG", "LC_ALL", "TZ")
ALLOWED_PREFIXES = ("ARC_", "CORA_")

ENV_CAPTURED = "ENV_CAPTURED"
ENV_RUN_UNKNOWN = "ENV-RUN-UNKNOWN"
ENV_CAPTURE_PARTIAL = "ENV_CAPTURE_PARTIAL"
ENV_CAPTURE_EXISTS = "ENV_CAPTURE_EXISTS"
EXIT_CODES = {ENV_CAPTURED: 0, ENV_RUN_UNKNOWN: 30, ENV_CAPTURE_PARTIAL: 31, ENV_CAPTURE_EXISTS: 32}


def record_path() -> Path:
    return FP.gate_dir() / "stepB_run_env.json"


def _allowed(name: str) -> bool:
    return name in ALLOWED_VALUES or name.startswith(ALLOWED_PREFIXES)


def read_process(pid: int) -> tuple:
    """(process facts, environment facts or None). Values only for allowlisted names."""
    entry = FP.PROC / str(pid)
    facts = {"pid": pid}
    try:
        facts["argv"] = [a.decode(errors="replace")
                         for a in (entry / "cmdline").read_bytes().split(b"\x00") if a]
    except OSError:
        facts["argv"] = None
    for link in ("exe", "cwd"):
        try:
            facts[link] = os.readlink(entry / link)
        except OSError:
            facts[link] = None
    try:
        fields = (entry / "stat").read_text().rsplit(")", 1)[1].split()
        facts["start_ticks"] = int(fields[19])
    except (OSError, ValueError, IndexError):
        facts["start_ticks"] = None
    try:
        raw = (entry / "environ").read_bytes()
    except OSError:
        facts["environ_readable"] = False
        return facts, None
    pairs = []
    for item in raw.split(b"\x00"):
        if item and b"=" in item:
            key, value = item.split(b"=", 1)
            pairs.append((key.decode(errors="replace"), value))
    digest = hashlib.sha256(raw).hexdigest()
    environment = {
        "environ_sha256": digest,
        "values": {k: v.decode(errors="replace") for k, v in sorted(pairs) if _allowed(k)},
        "other_variable_count": sum(1 for k, _ in pairs if not _allowed(k)),
    }
    facts["environ_readable"] = True
    facts["environ_sha256"] = digest
    return facts, environment


def capture() -> dict:
    if record_path().exists():
        return {"outcome": ENV_CAPTURE_EXISTS, "record": str(record_path())}
    pids = FP.runner_processes()
    processes, environments = [], {}
    for pid in pids:
        facts, environment = read_process(pid)
        processes.append(facts)
        if environment is not None:
            environments.setdefault(environment["environ_sha256"], environment)
    if not pids:
        outcome = ENV_RUN_UNKNOWN
    elif all(p["environ_readable"] for p in processes):
        outcome = ENV_CAPTURED
    else:
        outcome = ENV_CAPTURE_PARTIAL
    record = {
        "record_version": RECORD_VERSION,
        "outcome": outcome,
        "captured_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "main": str(FP.MAIN),
        "runner_pids": pids,
        "processes": processes,
        "environments": environments,
        "script_sha256": FP.file_digest(Path(__file__)),
        "policy": ("environment values are recorded only for allowlisted reproducibility "
                   "variables; every other variable is counted, not named; each block is "
                   "identified by sha256"),
    }
    FP.gate_dir().mkdir(parents=True, exist_ok=True)
    with open(record_path(), "x") as handle:
        handle.write(json.dumps(record, indent=1, sort_keys=True) + "\n")
    return {"outcome": outcome, "record": str(record_path()), "runner_processes": len(pids),
            "distinct_environments": len(environments)}


def main(argv=None) -> int:
    result = capture()
    print(f"OUTCOME {result['outcome']}")
    print(json.dumps(result, indent=1, sort_keys=True))
    return EXIT_CODES[result["outcome"]]


if __name__ == "__main__":
    raise SystemExit(main())
