"""Freeze-pin library for the Step-B Capability-Growth Gate.

The first action after the Step-B run freezes is to record, once and
immutably, the digests of every artifact that defines or constitutes the run,
before anything is inspected. Every later stage must then prove mechanically
that it is looking at exactly those bytes. This module is that mechanism.
`scripts/pin_stepB_freeze.py` is its command line, and
`cora_tti/gate_guard.py` enforces `verify_pin` at every stage after pinning.

CONTENT POLICY. An earlier version claimed the pin tool never read artifact
content into memory. That was false: hashing reads bytes. The precise
invariant is:

    Artifact bytes are read transiently, in fixed-size binary blocks, only for
    cryptographic hashing and newline counting. They are never parsed,
    deserialized, decoded as text, semantically interpreted, retained after
    the block is digested, printed, returned, or serialized into the pin.

The run log is the one file searched for anything, and only for the freeze
marker, which is the reading the standing monitoring rule already permits.

READINESS. A pin describes a finished run or nothing. Creating it requires the
freeze marker in the run log AND the final output hash file the runner writes
at completion AND no live runner process for this checkout, so that the run
log cannot grow after its digest is taken. Each unmet condition has its own
outcome, and none is diagnosed by inspecting anything.

VERIFICATION FAILS CLOSED. Once the pin exists, a missing pinned artifact, a
changed pinned artifact, a pin file that no longer matches its recorded
digest, and any file that appears inside a pinned scope after the pin, are
each a provenance failure with its own outcome. None is a scientific result.
None is repaired by repinning. The pin is never overwritten.
"""
from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

LIVE_MAIN = Path("/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project")
MAIN = LIVE_MAIN
TTI = Path(__file__).resolve().parents[1]
PROC = Path("/proc")

PIN_VERSION = "stepB_capability_gate_pin:v2"
FREEZE_MARKER = "STEP B FROZEN"
RUNNER_SCRIPT = "cora_level4_stepB_run.py"
FINAL_OUTPUT_HASH_NAME = "level4_stepB_output_hash.txt"
CHUNK = 1 << 20
LINE_COUNTED_SUFFIXES = (".jsonl", ".log", ".txt")

CONTENT_POLICY = (
    "Artifact bytes were read transiently, in fixed-size binary blocks, only for "
    "sha256 hashing and newline counting. They were never parsed, deserialized, "
    "decoded as text, semantically interpreted, retained after digesting, printed, "
    "returned, or serialized into this pin. The run log was additionally streamed "
    "to count occurrences of the freeze marker.")

#  ------------------------------------------------------------ outcomes

READY = "READY"
PIN_CREATED = "PIN_CREATED"
DRY_RUN_OK = "DRY_RUN_OK"
FREEZE_MARKER_ABSENT = "FREEZE_MARKER_ABSENT"
FREEZE_OUTPUT_NOT_READY = "FREEZE_OUTPUT_NOT_READY"
FREEZE_RUNNER_STILL_ACTIVE = "FREEZE_RUNNER_STILL_ACTIVE"
PIN_SOURCE_UNSTABLE = "PIN_SOURCE_UNSTABLE"
PIN_EXISTS_REFUSING_OVERWRITE = "PIN_EXISTS_REFUSING_OVERWRITE"
DRY_RUN_REFUSED_ON_LIVE_TREE = "DRY_RUN_REFUSED_ON_LIVE_TREE"
PIN_VERIFIED = "PIN_VERIFIED"
PIN_MISSING = "PIN_MISSING"
PIN_HASH_RECORD_MISSING = "PIN_HASH_RECORD_MISSING"
PIN_JSON_ALTERED = "PIN_JSON_ALTERED"
PIN_ARTIFACT_MISSING = "PIN_ARTIFACT_MISSING"
PIN_ARTIFACT_DRIFT = "PIN_ARTIFACT_DRIFT"
PIN_SCOPE_GREW_AFTER_FREEZE = "PIN_SCOPE_GREW_AFTER_FREEZE"

READINESS_OUTCOMES = (READY, FREEZE_MARKER_ABSENT, FREEZE_OUTPUT_NOT_READY,
                      FREEZE_RUNNER_STILL_ACTIVE)
PROVENANCE_FAILURES = (PIN_MISSING, PIN_HASH_RECORD_MISSING, PIN_JSON_ALTERED,
                       PIN_ARTIFACT_MISSING, PIN_ARTIFACT_DRIFT,
                       PIN_SCOPE_GREW_AFTER_FREEZE)

EXIT_CODES = {
    PIN_CREATED: 0, PIN_VERIFIED: 0, DRY_RUN_OK: 0,
    FREEZE_MARKER_ABSENT: 1, PIN_MISSING: 2, PIN_HASH_RECORD_MISSING: 3,
    PIN_JSON_ALTERED: 3, PIN_ARTIFACT_MISSING: 4, PIN_ARTIFACT_DRIFT: 4,
    PIN_EXISTS_REFUSING_OVERWRITE: 5, PIN_SCOPE_GREW_AFTER_FREEZE: 6,
    FREEZE_OUTPUT_NOT_READY: 7, FREEZE_RUNNER_STILL_ACTIVE: 8,
    DRY_RUN_REFUSED_ON_LIVE_TREE: 9, PIN_SOURCE_UNSTABLE: 10,
}

#  ------------------------------------------------------------- locations
#  Functions rather than constants, so every path follows MAIN and TTI.

def breakthrough() -> Path:
    return MAIN / "outputs" / "cora_breakthrough"


def run_log() -> Path:
    return MAIN / "logs" / "level4_stepB_run.log"


def final_output_hash_file() -> Path:
    return breakthrough() / FINAL_OUTPUT_HASH_NAME


def gate_dir() -> Path:
    return TTI / "outputs" / "tti" / "stepB_gate"


def pin_path() -> Path:
    return gate_dir() / "stepB_freeze_pin.json"


def pin_hash_path() -> Path:
    return gate_dir() / "stepB_freeze_pin_hash.txt"

#  ---------------------------------------------------------------- scopes

def explicit_paths() -> list:
    return [MAIN / "scripts" / RUNNER_SCRIPT,
            MAIN / "scripts" / "restart_stepB_after_reboot.sh",
            run_log()]


def glob_scopes() -> list:
    b = breakthrough()
    return [(b, "level4_stepB*"),
            (b, "level4_blind_runtime_manifest.json"),
            (b, "level4_provenance_firewall.json"),
            (b, "level4_withheld_expectation_seal.json"),
            (b, "concept_registry.json")]


def tree_scopes() -> list:
    b = breakthrough()
    return [b / "level4_stepB_gate_outputs",
            b / "level4_mechanism_inputs",
            MAIN / "level4_stepB",
            MAIN / "level4_blind_runtime"]


def _ignored(relative: Path) -> bool:
    return "__pycache__" in relative.parts


def scope_files() -> list:
    """Every existing file inside a pinned scope, as resolved paths."""
    seen, found = set(), []

    def add(path: Path) -> None:
        resolved = path.resolve()
        if str(resolved) not in seen:
            seen.add(str(resolved))
            found.append(resolved)

    for path in explicit_paths():
        if path.is_file():
            add(path)
    for directory, pattern in glob_scopes():
        if directory.is_dir():
            for path in sorted(directory.glob(pattern)):
                if path.is_file():
                    add(path)
    for tree in tree_scopes():
        if tree.is_dir():
            for path in sorted(tree.rglob("*")):
                if path.is_file() and not _ignored(path.relative_to(tree)):
                    add(path)
    return sorted(found, key=str)


def in_pinned_scope(path) -> bool:
    """True if a file at this path would belong to the pinned artifact set."""
    candidate = Path(path).resolve()
    if any(candidate == p.resolve() for p in explicit_paths()):
        return True
    for directory, pattern in glob_scopes():
        if candidate.parent == directory.resolve() and fnmatch.fnmatchcase(candidate.name, pattern):
            return True
    for tree in tree_scopes():
        try:
            relative = candidate.relative_to(tree.resolve())
        except ValueError:
            continue
        return not _ignored(relative)
    return False

#  --------------------------------------------------------------- digests

def digest_and_lines(path) -> tuple:
    """sha256 and newline count, from transient binary blocks only."""
    digest, lines = hashlib.sha256(), 0
    with open(path, "rb") as handle:
        while True:
            block = handle.read(CHUNK)
            if not block:
                break
            digest.update(block)
            lines += block.count(b"\n")
    return digest.hexdigest(), lines


def file_digest(path) -> str:
    return digest_and_lines(path)[0]


def describe(path) -> dict:
    path = Path(path)
    stat = path.stat()
    digest, lines = digest_and_lines(path)
    record = {"path": str(path),
              "relative_to_main": os.path.relpath(path, MAIN.resolve()),
              "sha256": digest, "bytes": stat.st_size,
              "mtime_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(stat.st_mtime))}
    if path.suffix in LINE_COUNTED_SUFFIXES:
        record["lines"] = lines
    return record

#  -------------------------------------------------------------- readiness

def freeze_marker_occurrences() -> int:
    log = run_log()
    if not log.is_file():
        return 0
    marker, count = FREEZE_MARKER.encode(), 0
    with open(log, "rb") as handle:
        for raw in handle:
            count += raw.count(marker)
    return count


def runner_processes() -> list:
    """Live Python processes running the Step-B runner from THIS checkout.

    Identity is the runner script in argv, launched by a Python interpreter,
    with the process working directory (or an absolute script path) inside
    MAIN. A matching process whose working directory cannot be read is
    counted as live: this check fails closed.
    """
    found = []
    if not PROC.is_dir():
        return found
    for entry in PROC.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            argv = [a.decode(errors="replace")
                    for a in (entry / "cmdline").read_bytes().split(b"\0") if a]
        except OSError:
            continue
        positions = [i for i, a in enumerate(argv) if a.endswith(RUNNER_SCRIPT)]
        if not positions:
            continue
        if not any(os.path.basename(a).startswith("python") for a in argv[:positions[0]]):
            continue
        script = argv[positions[0]]
        if os.path.isabs(script):
            try:
                Path(script).resolve().relative_to(MAIN.resolve())
                found.append(int(entry.name))
            except ValueError:
                pass
            continue
        try:
            cwd = Path(os.readlink(entry / "cwd"))
        except OSError:
            found.append(int(entry.name))
            continue
        if cwd.resolve() == MAIN.resolve():
            found.append(int(entry.name))
    return sorted(found)


@dataclass(frozen=True)
class Readiness:
    status: str
    marker_occurrences: int
    final_output_hash_present: bool
    runner_pids: tuple

    def to_json(self) -> dict:
        return {"status": self.status, "marker_occurrences": self.marker_occurrences,
                "final_output_hash_present": self.final_output_hash_present,
                "runner_pids": list(self.runner_pids)}


def readiness() -> Readiness:
    occurrences = freeze_marker_occurrences()
    present = final_output_hash_file().is_file()
    pids = tuple(runner_processes())
    if occurrences == 0:
        status = FREEZE_MARKER_ABSENT
    elif not present:
        status = FREEZE_OUTPUT_NOT_READY
    elif pids:
        status = FREEZE_RUNNER_STILL_ACTIVE
    else:
        status = READY
    return Readiness(status, occurrences, present, pids)

#  ------------------------------------------------------------ pin record

def git_state(repo: Path) -> dict:
    def run(*args):
        try:
            return subprocess.run(["git", "-C", str(repo), *args], check=True,
                                  capture_output=True, text=True).stdout.strip()
        except Exception:
            return None
    porcelain = run("status", "--porcelain")
    return {"repo": str(repo), "head": run("rev-parse", "HEAD"),
            "branch": run("rev-parse", "--abbrev-ref", "HEAD"),
            "dirty_file_count": None if porcelain is None
            else len([l for l in porcelain.splitlines() if l.strip()])}


def environment() -> dict:
    return {"python": sys.version.split()[0],
            "implementation": platform.python_implementation(),
            "platform": platform.platform(), "hostname": platform.node(),
            "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
            "omp_num_threads": os.environ.get("OMP_NUM_THREADS"),
            "mkl_num_threads": os.environ.get("MKL_NUM_THREADS"),
            "openblas_num_threads": os.environ.get("OPENBLAS_NUM_THREADS")}


def _identity(records: list) -> list:
    return [(r["path"], r["sha256"], r["bytes"]) for r in records]


def build_pin(ready: Readiness) -> tuple:
    """Collect twice and require agreement, so a file changing mid-pin is caught."""
    first = [describe(p) for p in scope_files()]
    second = [describe(p) for p in scope_files()]
    stable = _identity(first) == _identity(second)
    manifest = "\n".join(f"{r['sha256']}  {r['relative_to_main']}" for r in second)
    pin = {
        "pin_version": PIN_VERSION,
        "purpose": "record and pin the final Step-B output hash and all protocol hashes "
                   "BEFORE any semantic inspection of the retained productions",
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "readiness": ready.to_json(),
        "content_policy": CONTENT_POLICY,
        "scopes": {
            "explicit": [os.path.relpath(p, MAIN) for p in explicit_paths()],
            "globs": [f"{os.path.relpath(d, MAIN)}/{g}" for d, g in glob_scopes()],
            "trees_excluding_pycache": [os.path.relpath(t, MAIN) for t in tree_scopes()]},
        "artifacts": second,
        "artifact_count": len(second),
        "aggregate_sha256": hashlib.sha256(manifest.encode()).hexdigest(),
        "git": {"main": git_state(MAIN), "tti": git_state(TTI)},
        "environment": environment(),
    }
    return pin, stable


def write_pin(pin: dict) -> str:
    gate_dir().mkdir(parents=True, exist_ok=True)
    data = json.dumps(pin, indent=1, sort_keys=True).encode()
    with open(pin_path(), "xb") as handle:       # exclusive: never overwrites
        handle.write(data)
    digest = hashlib.sha256(data).hexdigest()
    with open(pin_hash_path(), "x") as handle:
        handle.write(digest + "\n")
    return digest

#  ------------------------------------------------------------ verification

@dataclass(frozen=True)
class Verification:
    status: str
    pin_sha256: str | None
    artifact_count: int
    missing: tuple
    drifted: tuple
    appeared: tuple

    def ok(self) -> bool:
        return self.status == PIN_VERIFIED

    def to_json(self) -> dict:
        return {"outcome": self.status, "pin_sha256": self.pin_sha256,
                "artifact_count": self.artifact_count, "missing": list(self.missing),
                "drifted": list(self.drifted), "appeared_after_pin": list(self.appeared)}


def verify_pin() -> Verification:
    pin_file, hash_file = pin_path(), pin_hash_path()
    if not pin_file.is_file():
        return Verification(PIN_MISSING, None, 0, (), (), ())
    if not hash_file.is_file():
        return Verification(PIN_HASH_RECORD_MISSING, None, 0, (), (), ())
    raw = pin_file.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    recorded = (hash_file.read_text().split() or [""])[0]
    if recorded != actual:
        return Verification(PIN_JSON_ALTERED, actual, 0, (), (), ())
    try:
        pin = json.loads(raw)
        expected = {r["path"]: r["sha256"] for r in pin["artifacts"]}
    except (ValueError, KeyError, TypeError):
        return Verification(PIN_JSON_ALTERED, actual, 0, (), (), ())
    missing, drifted = [], []
    for path, digest in sorted(expected.items()):
        candidate = Path(path)
        if not candidate.is_file():
            missing.append(path)
        elif file_digest(candidate) != digest:
            drifted.append(path)
    appeared = [str(p) for p in scope_files() if str(p) not in expected]
    if missing:
        status = PIN_ARTIFACT_MISSING
    elif drifted:
        status = PIN_ARTIFACT_DRIFT
    elif appeared:
        status = PIN_SCOPE_GREW_AFTER_FREEZE
    else:
        status = PIN_VERIFIED
    return Verification(status, actual, len(expected), tuple(missing),
                        tuple(drifted), tuple(appeared))


def load_pinned_digests() -> dict:
    """Path to sha256 for every pinned artifact. Call only after verify_pin passes."""
    return {r["path"]: r["sha256"] for r in json.loads(pin_path().read_bytes())["artifacts"]}

#  ---------------------------------------------------------------- actions

def is_live_tree() -> bool:
    return (os.path.abspath(MAIN) == os.path.abspath(LIVE_MAIN)
            or os.path.realpath(MAIN) == os.path.realpath(LIVE_MAIN))


def create_pin() -> dict:
    if pin_path().exists():
        return {"outcome": PIN_EXISTS_REFUSING_OVERWRITE, "pin": str(pin_path())}
    ready = readiness()
    if ready.status != READY:
        return {"outcome": ready.status, "readiness": ready.to_json()}
    pin, stable = build_pin(ready)
    if not stable:
        return {"outcome": PIN_SOURCE_UNSTABLE, "readiness": ready.to_json(),
                "note": "the artifact set changed between two consecutive collections; nothing written"}
    pin_digest = write_pin(pin)
    check = verify_pin()
    return {"outcome": PIN_CREATED if check.ok() else check.status,
            "readiness": ready.to_json(), "artifact_count": pin["artifact_count"],
            "aggregate_sha256": pin["aggregate_sha256"], "pin_sha256": pin_digest,
            "pin": str(pin_path()), "verification": check.to_json()}


def dry_run() -> dict:
    """Fixture trees only. Refused on the live tree before anything is read."""
    if is_live_tree():
        return {"outcome": DRY_RUN_REFUSED_ON_LIVE_TREE,
                "note": "pre-freeze dry runs against the live experiment are retired; "
                        "use a synthetic fixture tree"}
    ready = readiness()
    pin, stable = build_pin(ready)
    return {"outcome": DRY_RUN_OK, "readiness": ready.to_json(),
            "artifact_count": pin["artifact_count"], "stable": stable}
