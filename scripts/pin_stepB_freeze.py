"""Step-B capability-growth gate, stage 1 and 2: PIN BEFORE INSPECTION.

This script exists so that the first action after `STEP B FROZEN` cannot be
improvised. It records and pins the final Step-B output hash together with the
runner, manifest, candidate-inventory and environment hashes, and it does so
WITHOUT reading the scientific content of any of them.

Design constraints, all deliberate:

  * It reads the live experiment's directory but writes NOTHING there. Every
    artifact it produces lands in the cora-tti-dev worktree. The main checkout
    is never modified, and nothing is merged.
  * It never prints, returns or stores file CONTENTS. Only sha256 digests,
    byte sizes, modification times and line counts. A line count is a count.
  * It refuses to run before the freeze marker is present, so a pin can never
    describe a partial run.
  * It refuses to overwrite an existing pin. The pin is immutable. A second
    pin attempt is an error, not a silent regeneration.
  * `--verify` re-walks the pinned set and fails loudly on any drift, so every
    later gate stage can prove it is looking at the same artifacts.

Usage:
    python3 scripts/pin_stepB_freeze.py          # create the pin (once)
    python3 scripts/pin_stepB_freeze.py --verify # check the pin still holds
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

TTI = Path(__file__).resolve().parents[1]
MAIN = Path("/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project")
OUTDIR = TTI / "outputs" / "tti" / "stepB_gate"
PIN = OUTDIR / "stepB_freeze_pin.json"
PIN_HASH = OUTDIR / "stepB_freeze_pin_hash.txt"

RUN_LOG = MAIN / "logs" / "level4_stepB_run.log"
BREAKTHROUGH = MAIN / "outputs" / "cora_breakthrough"
FREEZE_MARKER = "STEP B FROZEN"

#  Files pinned by explicit path. Globs are expanded too, so an output the
#  runner creates at freeze time is captured even though it does not exist yet.
PINNED_PATHS = [
    MAIN / "scripts" / "cora_level4_stepB_run.py",
    MAIN / "scripts" / "restart_stepB_after_reboot.sh",
    MAIN / "level4_stepB" / "candidates.py",
    RUN_LOG,
]
PINNED_GLOBS = [
    (BREAKTHROUGH, "level4_stepB*"),
    (BREAKTHROUGH, "level4_blind_runtime_manifest.json"),
    (BREAKTHROUGH, "level4_provenance_firewall.json"),
    (BREAKTHROUGH, "level4_withheld_expectation_seal.json"),
    (BREAKTHROUGH, "concept_registry.json"),
]

#  Whole subtrees pinned recursively. The gate-output tree carries the three
#  determinism lanes (ckpt, deta, detb), each with its own output hash, so the
#  pin must cover every file in it rather than the directory name alone. The
#  mechanism-input tree is pinned because a claim about what Step B produced is
#  only meaningful alongside a record of what it was given.
PINNED_TREES = [
    BREAKTHROUGH / "level4_stepB_gate_outputs",
    BREAKTHROUGH / "level4_mechanism_inputs",
]


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    """Digest a file without holding or exposing its content."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(chunk)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def line_count(path: Path, chunk: int = 1 << 20) -> int:
    total = 0
    with path.open("rb") as handle:
        while True:
            block = handle.read(chunk)
            if not block:
                break
            total += block.count(b"\n")
    return total


def describe(path: Path) -> dict:
    """Quantitative description only. No content leaves this function."""
    stat = path.stat()
    record = {
        "path": str(path),
        "relative_to_main": os.path.relpath(path, MAIN),
        "sha256": sha256_file(path),
        "bytes": stat.st_size,
        "mtime_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(stat.st_mtime)),
    }
    if path.suffix in (".jsonl", ".log", ".txt"):
        record["lines"] = line_count(path)
    return record


def collect() -> list:
    seen, records = set(), []
    for path in PINNED_PATHS:
        if path.is_file() and path not in seen:
            seen.add(path)
            records.append(describe(path))
    for directory, pattern in PINNED_GLOBS:
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob(pattern)):
            if path.is_file() and path not in seen:
                seen.add(path)
                records.append(describe(path))
    for tree in PINNED_TREES:
        if not tree.is_dir():
            continue
        for path in sorted(tree.rglob("*")):
            if path.is_file() and path not in seen and "__pycache__" not in path.parts:
                seen.add(path)
                records.append(describe(path))
    return sorted(records, key=lambda r: r["path"])


def freeze_marker_present() -> tuple:
    """Count freeze markers by streaming. The log's prose is never retained."""
    if not RUN_LOG.is_file():
        return False, 0
    count = 0
    with RUN_LOG.open("r", errors="replace") as handle:
        for line in handle:
            count += line.count(FREEZE_MARKER)
    return count > 0, count


def git_state(repo: Path) -> dict:
    def run(*args):
        try:
            return subprocess.run(["git", "-C", str(repo), *args], check=True,
                                  capture_output=True, text=True).stdout.strip()
        except Exception:
            return None
    return {"repo": str(repo), "head": run("rev-parse", "HEAD"),
            "branch": run("rev-parse", "--abbrev-ref", "HEAD"),
            "dirty_file_count": len([l for l in (run("status", "--porcelain") or "").splitlines() if l.strip()])}


def environment() -> dict:
    versions = {}
    for module in ("numpy", "scipy"):
        try:
            versions[module] = __import__(module).__version__
        except Exception:
            versions[module] = None
    return {
        "python": sys.version.split()[0],
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "hostname": platform.node(),
        "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
        "omp_num_threads": os.environ.get("OMP_NUM_THREADS"),
        "mkl_num_threads": os.environ.get("MKL_NUM_THREADS"),
        "openblas_num_threads": os.environ.get("OPENBLAS_NUM_THREADS"),
        "module_versions": versions,
    }


def build_pin() -> dict:
    present, count = freeze_marker_present()
    records = collect()
    manifest_line = "\n".join(f"{r['sha256']}  {r['relative_to_main']}" for r in records)
    return {
        "pin_version": "stepB_capability_gate_pin:v1",
        "purpose": "record and pin the final Step-B output hash and all protocol "
                   "hashes BEFORE any semantic inspection of the retained productions",
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "freeze_marker": {"text": FREEZE_MARKER, "present": present, "occurrences": count},
        "artifacts": records,
        "artifact_count": len(records),
        "aggregate_sha256": hashlib.sha256(manifest_line.encode()).hexdigest(),
        "git": {"main": git_state(MAIN), "tti": git_state(TTI)},
        "environment": environment(),
        "content_inspected": False,
        "note": "Digests, sizes, mtimes and line counts only. No artifact content "
                "was read into memory, printed or stored by this script.",
    }


def write_pin(pin: dict) -> None:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    text = json.dumps(pin, indent=1, sort_keys=True)
    PIN.write_text(text)
    PIN_HASH.write_text(hashlib.sha256(text.encode()).hexdigest() + "\n")


def verify() -> int:
    if not PIN.is_file():
        print("NO PIN: run without --verify first, after the freeze marker appears")
        return 2
    text = PIN.read_text()
    stored = PIN_HASH.read_text().split()[0] if PIN_HASH.is_file() else None
    actual = hashlib.sha256(text.encode()).hexdigest()
    if stored != actual:
        print(f"PIN FILE ALTERED: recorded {stored} but file hashes {actual}")
        return 3
    pin = json.loads(text)
    expected = {r["path"]: r["sha256"] for r in pin["artifacts"]}
    drift, missing = [], []
    for path, digest in expected.items():
        candidate = Path(path)
        if not candidate.is_file():
            missing.append(path)
        elif sha256_file(candidate) != digest:
            drift.append(path)
    new = [r["path"] for r in collect() if r["path"] not in expected]
    print(f"pin {actual[:16]}... covers {len(expected)} artifacts")
    print(f"  drifted: {len(drift)}  missing: {len(missing)}  appeared since pin: {len(new)}")
    for path in drift + missing:
        print(f"    ! {os.path.relpath(path, MAIN)}")
    for path in new:
        print(f"    + {os.path.relpath(path, MAIN)} (not covered by the pin)")
    if drift or missing:
        print("PIN VERIFICATION FAILED")
        return 4
    print("PIN VERIFIED")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true", help="check an existing pin")
    parser.add_argument("--allow-unfrozen", action="store_true",
                        help="DRY RUN ONLY: build a pin preview before the freeze "
                             "marker exists. Writes nothing.")
    args = parser.parse_args()

    if args.verify:
        return verify()

    present, count = freeze_marker_present()
    if not present and not args.allow_unfrozen:
        print(f"REFUSING TO PIN: '{FREEZE_MARKER}' is not present in {RUN_LOG}.")
        print("A pin must describe a completed run, never a partial one.")
        print("Use --allow-unfrozen for a dry-run preview that writes nothing.")
        return 1

    pin = build_pin()
    if not present:
        print("DRY RUN, freeze marker absent, nothing written.")
        print(f"  would pin {pin['artifact_count']} artifacts")
        print(f"  aggregate {pin['aggregate_sha256']}")
        for record in pin["artifacts"]:
            extra = f" lines={record['lines']}" if "lines" in record else ""
            print(f"    {record['sha256'][:16]}  {record['bytes']:>12}{extra}  "
                  f"{record['relative_to_main']}")
        return 0

    if PIN.is_file():
        print(f"REFUSING TO OVERWRITE: {PIN} already exists.")
        print("The pin is immutable. Use --verify to check it.")
        return 5

    write_pin(pin)
    print(f"PINNED {pin['artifact_count']} artifacts "
          f"({count} freeze marker occurrence(s))")
    print(f"  aggregate sha256 {pin['aggregate_sha256']}")
    print(f"  pin sha256       {PIN_HASH.read_text().split()[0]}")
    print(f"  written to       {PIN}")
    print("\nSTAGE 1 AND 2 COMPLETE. Semantic inspection is now permitted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
