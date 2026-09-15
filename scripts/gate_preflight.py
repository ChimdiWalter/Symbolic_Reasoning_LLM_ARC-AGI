"""Gate preflight. Enforces the environment every gate process runs in, and writes nothing.

Run before the pin and before every gate stage:

    PYTHONHASHSEED=0 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
        python3 scripts/gate_preflight.py

Required, in this order:
  1. PYTHONHASHSEED is "0".
  2. OMP_NUM_THREADS, MKL_NUM_THREADS and OPENBLAS_NUM_THREADS are each "1".
  3. Every gate tooling file is committed at HEAD, and its on-disk bytes equal
     the committed blob. Tooling is every file matching TOOLING_GLOBS, on disk
     or tracked, plus REQUIRED_TOOLING, so a new or deleted gate script is caught.
  4. The dev worktree is porcelain clean.

Recorded, not required: the main checkout's dirty file count. The gate never
writes into the main checkout, so it cannot make that checkout clean, and
requiring it would leave no lawful way forward at the freeze marker. The pin
records the same count. Git is run with --no-optional-locks, so reading status
does not rewrite either checkout's index.

The first output line is `OUTCOME <name>`, and each outcome has a fixed exit code.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cora_tti import freeze_pin as FP   # noqa: E402

PREFLIGHT_OK = "PREFLIGHT_OK"
PREFLIGHT_HASHSEED = "PREFLIGHT_HASHSEED"
PREFLIGHT_THREADS = "PREFLIGHT_THREADS"
PREFLIGHT_UNCOMMITTED_TOOLING = "PREFLIGHT_UNCOMMITTED_TOOLING"
PREFLIGHT_DIRTY_WORKTREE = "PREFLIGHT_DIRTY_WORKTREE"
EXIT_CODES = {PREFLIGHT_OK: 0, PREFLIGHT_HASHSEED: 21, PREFLIGHT_THREADS: 22,
              PREFLIGHT_UNCOMMITTED_TOOLING: 24, PREFLIGHT_DIRTY_WORKTREE: 23}

THREAD_VARIABLES = ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS")
REQUIRED_TOOLING = ("cora_tti/freeze_pin.py", "cora_tti/gate_guard.py", "cora_tti/split_extract.py",
                    "scripts/pin_stepB_freeze.py", "scripts/gate_preflight.py",
                    "scripts/gate_capture_run_env.py")
TOOLING = REQUIRED_TOOLING
TOOLING_GLOBS = ("cora_tti/*.py", "scripts/gate_*.py", "scripts/pin_stepB_freeze.py",
                 "scripts/check_gate_protocol_*.py")


def tooling_files() -> list:
    """Required tooling, plus every file matching the globs on disk or at HEAD."""
    found = set(REQUIRED_TOOLING)
    for pattern in TOOLING_GLOBS:
        found.update(p.relative_to(FP.TTI).as_posix() for p in FP.TTI.glob(pattern) if p.is_file())
    tracked = FP._git("ls-files", "--", *TOOLING_GLOBS)
    if tracked:
        found.update(line for line in tracked.splitlines() if line)
    return sorted(found)


def run(env=None) -> dict:
    env = os.environ if env is None else env
    record = {"pythonhashseed": env.get("PYTHONHASHSEED"),
              "threads": {name: env.get(name) for name in THREAD_VARIABLES},
              "tti": FP.git_state(FP.TTI), "main": FP.git_state(FP.MAIN)}
    if env.get("PYTHONHASHSEED") != "0":
        return {"outcome": PREFLIGHT_HASHSEED, **record}
    if any(env.get(name) != "1" for name in THREAD_VARIABLES):
        return {"outcome": PREFLIGHT_THREADS, **record}
    uncommitted = []
    for relative in tooling_files():
        path = FP.TTI / relative
        blob = FP._git("cat-file", "blob", f"HEAD:{relative}", binary=True)
        if not path.is_file() or blob is None or blob != path.read_bytes():
            uncommitted.append(relative)
    if uncommitted:
        return {"outcome": PREFLIGHT_UNCOMMITTED_TOOLING, "uncommitted": uncommitted, **record}
    dirty = (record["tti"] or {}).get("dirty_file_count")
    if dirty != 0:
        return {"outcome": PREFLIGHT_DIRTY_WORKTREE, **record}
    return {"outcome": PREFLIGHT_OK, **record}


def main(argv=None) -> int:
    result = run()
    print(f"OUTCOME {result['outcome']}")
    print(json.dumps(result, indent=1, sort_keys=True, default=str))
    return EXIT_CODES[result["outcome"]]


if __name__ == "__main__":
    raise SystemExit(main())
