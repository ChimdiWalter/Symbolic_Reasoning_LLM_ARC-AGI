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

ATOMIC. The pin and its digest are written into a private staging directory,
flushed, and renamed into place in one step, so a crash cannot leave a pin
without its digest.

BOUND TO A COMMIT AND ANCHORED OUTSIDE THE REPOSITORY. A digest stored beside
the pin cannot detect a pin that was deleted and recreated, and the history of
one branch cannot detect a pin recreated on another. So after the pin directory
is committed, `bind_pin` writes a tracked binding record naming the pin's sha256
and its commit, and, with exclusive create, an anchor record outside both
checkouts. Every stage after stage 2 verifies with `require_binding=True`: the
binding is committed exactly once; the pin and the binding each have exactly
one distinct blob across all refs and the reflog; the pin commit is an ancestor
of HEAD; the on-disk pin and digest equal the blobs in that commit; and the
anchor names the same sha256 and commit. The anchor is a second copy, not a
tamper-proof store, so the protocol also copies it into the review record.

OUTPUT SIZES. Byte sizes and line counts are recorded only for the run log.
For every other artifact the pin records path, sha256 and mtime, so reading the
pin cannot hint at the size of any result.
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

PIN_VERSION = "stepB_capability_gate_pin:v3"
BINDING_VERSION = "stepB_capability_gate_pin_binding:v1"
ANCHOR_VERSION = "stepB_capability_gate_pin_anchor:v1"
FREEZE_MARKER = "STEP B FROZEN"
RUNNER_SCRIPT = "cora_level4_stepB_run.py"
RUNNER_MODULE = "cora_level4_stepB_run"
FINAL_OUTPUT_HASH_NAME = "level4_stepB_output_hash.txt"
CHUNK = 1 << 20

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
PIN_WRITE_FAILED = "PIN_WRITE_FAILED"
PIN_BOUND = "PIN_BOUND"
PIN_NOT_COMMITTED = "PIN_NOT_COMMITTED"
PIN_BINDING_EXISTS_REFUSING_OVERWRITE = "PIN_BINDING_EXISTS_REFUSING_OVERWRITE"
PIN_BINDING_MISSING = "PIN_BINDING_MISSING"
PIN_BINDING_REWRITTEN = "PIN_BINDING_REWRITTEN"
PIN_COMMIT_MISMATCH = "PIN_COMMIT_MISMATCH"
MODULE_PIN_VERIFIED = "MODULE_PIN_VERIFIED"
MODULE_PIN_MISSING = "MODULE_PIN_MISSING"
MODULE_PIN_ALTERED = "MODULE_PIN_ALTERED"
MODULE_ARTIFACT_MISSING = "MODULE_ARTIFACT_MISSING"
MODULE_ARTIFACT_DRIFT = "MODULE_ARTIFACT_DRIFT"
PIN_WRITTEN_BUT_UNVERIFIED = "PIN_WRITTEN_BUT_UNVERIFIED"
PIN_RECREATED_IN_HISTORY = "PIN_RECREATED_IN_HISTORY"
PIN_ANCHOR_MISSING = "PIN_ANCHOR_MISSING"
PIN_ANCHOR_MISMATCH = "PIN_ANCHOR_MISMATCH"
PIN_ANCHOR_EXISTS_REFUSING_OVERWRITE = "PIN_ANCHOR_EXISTS_REFUSING_OVERWRITE"
MODULE_PIN_WRITTEN = "MODULE_PIN_WRITTEN"
MODULE_PIN_EXISTS_REFUSING_OVERWRITE = "MODULE_PIN_EXISTS_REFUSING_OVERWRITE"
MODULE_PIN_EMPTY = "MODULE_PIN_EMPTY"
MODULE_SCOPE_CHANGED = "MODULE_SCOPE_CHANGED"
MODULE_TREE_MISMATCH = "MODULE_TREE_MISMATCH"
CLI_USAGE_ERROR = "CLI_USAGE_ERROR"

READINESS_OUTCOMES = (READY, FREEZE_MARKER_ABSENT, FREEZE_OUTPUT_NOT_READY,
                      FREEZE_RUNNER_STILL_ACTIVE)
PROVENANCE_FAILURES = (PIN_MISSING, PIN_HASH_RECORD_MISSING, PIN_JSON_ALTERED,
                       PIN_ARTIFACT_MISSING, PIN_ARTIFACT_DRIFT,
                       PIN_SCOPE_GREW_AFTER_FREEZE, PIN_BINDING_MISSING,
                       PIN_BINDING_REWRITTEN, PIN_COMMIT_MISMATCH, MODULE_PIN_MISSING,
                       MODULE_PIN_ALTERED, MODULE_ARTIFACT_MISSING, MODULE_ARTIFACT_DRIFT,
                       PIN_WRITTEN_BUT_UNVERIFIED, PIN_RECREATED_IN_HISTORY, PIN_ANCHOR_MISSING,
                       PIN_ANCHOR_MISMATCH, MODULE_PIN_EMPTY, MODULE_SCOPE_CHANGED,
                       MODULE_TREE_MISMATCH)

EXIT_CODES = {
    PIN_CREATED: 0, PIN_VERIFIED: 0, DRY_RUN_OK: 0,
    FREEZE_MARKER_ABSENT: 1, PIN_MISSING: 2, PIN_HASH_RECORD_MISSING: 3,
    PIN_JSON_ALTERED: 3, PIN_ARTIFACT_MISSING: 4, PIN_ARTIFACT_DRIFT: 4,
    PIN_EXISTS_REFUSING_OVERWRITE: 5, PIN_SCOPE_GREW_AFTER_FREEZE: 6,
    FREEZE_OUTPUT_NOT_READY: 7, FREEZE_RUNNER_STILL_ACTIVE: 8,
    DRY_RUN_REFUSED_ON_LIVE_TREE: 9, PIN_SOURCE_UNSTABLE: 10,
    PIN_BOUND: 0, PIN_NOT_COMMITTED: 11, PIN_BINDING_MISSING: 12,
    PIN_BINDING_REWRITTEN: 13, PIN_COMMIT_MISMATCH: 14,
    PIN_BINDING_EXISTS_REFUSING_OVERWRITE: 15, PIN_WRITE_FAILED: 16,
    MODULE_PIN_VERIFIED: 0, MODULE_PIN_MISSING: 17, MODULE_PIN_ALTERED: 18,
    MODULE_ARTIFACT_MISSING: 19, MODULE_ARTIFACT_DRIFT: 20,
    PIN_WRITTEN_BUT_UNVERIFIED: 40, PIN_RECREATED_IN_HISTORY: 41, PIN_ANCHOR_MISSING: 42,
    PIN_ANCHOR_MISMATCH: 43, PIN_ANCHOR_EXISTS_REFUSING_OVERWRITE: 44, MODULE_PIN_WRITTEN: 0,
    MODULE_PIN_EXISTS_REFUSING_OVERWRITE: 45, MODULE_PIN_EMPTY: 46, MODULE_SCOPE_CHANGED: 47,
    MODULE_TREE_MISMATCH: 48, CLI_USAGE_ERROR: 64,
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


def pin_dir() -> Path:
    return gate_dir() / "pin"


def pin_path() -> Path:
    return pin_dir() / "stepB_freeze_pin.json"


def pin_hash_path() -> Path:
    return pin_dir() / "stepB_freeze_pin_hash.txt"


def binding_path() -> Path:
    """Tracked, not ignored: the binding must live in git history."""
    return TTI / "docs" / "stepB_gate" / "pin_binding.json"


def anchor_path() -> Path:
    """Outside both checkouts. Written once by bind_pin, never overwritten."""
    return TTI.resolve().parent / "CORA_reports" / "gate_anchor" / "stepB_freeze_pin_anchor.json"


def module_pin_path() -> Path:
    """The second pinned set, written at G2 by gate_module_pin.py."""
    return gate_dir() / "stepB_gate_module_pin.json"


def module_pin_hash_path() -> Path:
    return gate_dir() / "stepB_gate_module_pin_hash.txt"

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
              "sha256": digest,
              "mtime_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(stat.st_mtime))}
    if path.resolve() == run_log().resolve():
        record["bytes"] = stat.st_size
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


def _within(path: Path, root: Path) -> bool:
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
        return True
    except ValueError:
        return False


def _runner_invocation(argv: list):
    """('script', path) or ('module', name) when argv runs the Step-B runner."""
    for index, arg in enumerate(argv):
        if arg.endswith(RUNNER_SCRIPT):
            return "script", arg
        if arg == "-m" and index + 1 < len(argv):
            if argv[index + 1].split(".")[-1] == RUNNER_MODULE:
                return "module", argv[index + 1]
    return None


def _is_python(entry: Path, argv: list) -> bool:
    if argv and "python" in os.path.basename(argv[0]).lower():
        return True
    try:
        return "python" in os.path.basename(os.readlink(entry / "exe")).lower()
    except OSError:
        return False


def runner_processes() -> list:
    """Live Python processes running the Step-B runner from THIS checkout.

    A process matches when a Python interpreter, identified by argv[0] or by
    the executable link, runs the runner either as a script path or as a module
    via -m. A relative script path is resolved against the process working
    directory and must land inside MAIN; a module launch must have its working
    directory inside MAIN; an absolute script path must lie inside MAIN. A
    matching process whose working directory cannot be read is counted as
    live, so this check fails closed.
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
        invocation = _runner_invocation(argv)
        if invocation is None or not _is_python(entry, argv):
            continue
        kind, target = invocation
        if kind == "script" and os.path.isabs(target):
            if _within(Path(target), MAIN):
                found.append(int(entry.name))
            continue
        try:
            cwd = Path(os.readlink(entry / "cwd"))
        except OSError:
            found.append(int(entry.name))
            continue
        inside = _within(cwd / target, MAIN) if kind == "script" else _within(cwd, MAIN)
        if inside:
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
            return subprocess.run(["git", "--no-optional-locks", "-C", str(repo), *args], check=True,
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
    return [(r["path"], r["sha256"]) for r in records]


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


def _fsync_dir(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_pin(pin: dict) -> str:
    """Write the pin and its digest as one atomic directory rename.

    Both files go into a private staging directory, are flushed to disk, and
    the directory is renamed into place. Either both files exist or neither
    does. The rename fails if a pin directory with content already exists, so
    a pin is never overwritten.
    """
    gate_dir().mkdir(parents=True, exist_ok=True)
    data = json.dumps(pin, indent=1, sort_keys=True).encode()
    digest = hashlib.sha256(data).hexdigest()
    staging = gate_dir() / f".pin_staging_{os.getpid()}_{time.time_ns()}"
    staging.mkdir()
    try:
        for name, payload in ((pin_path().name, data), (pin_hash_path().name, (digest + "\n").encode())):
            with open(staging / name, "xb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
        _fsync_dir(staging)
        os.rename(staging, pin_dir())
        _fsync_dir(gate_dir())
    except OSError:
        for leftover in staging.glob("*"):
            leftover.unlink()
        if staging.exists():
            staging.rmdir()
        raise
    return digest


#  ---------------------------------------------------------------- binding

def _git(*args, binary: bool = False):
    try:
        done = subprocess.run(["git", "--no-optional-locks", "-C", str(TTI), *args],
                              capture_output=True, check=False)
    except OSError:
        return None
    if done.returncode != 0:
        return None
    return done.stdout if binary else done.stdout.decode(errors="replace").strip()


def _relative_to_tti(path: Path) -> str:
    return Path(path).resolve().relative_to(TTI.resolve()).as_posix()


def _history_count(relative: str) -> int:
    out = _git("log", "--format=%H", "--", relative)
    return len(out.splitlines()) if out else 0


def distinct_blobs(relative: str) -> set:
    """Blob ids a path has had in any commit reachable from any ref or reflog entry."""
    out = _git("log", "--all", "--reflog", "--format=%H", "--", relative)
    blobs = set()
    for commit in (out.splitlines() if out else []):
        blob = _git("rev-parse", "--verify", "-q", f"{commit}:{relative}")
        if blob:
            blobs.add(blob)
    return blobs


def bind_pin() -> dict:
    """Record, in a tracked file, which commit holds the pin. Run once, after committing the pin."""
    check = verify_pin(require_binding=False)
    if not check.ok():
        return {"outcome": check.status, "verification": check.to_json()}
    if binding_path().exists():
        return {"outcome": PIN_BINDING_EXISTS_REFUSING_OVERWRITE, "binding": str(binding_path())}
    if anchor_path().exists():
        return {"outcome": PIN_ANCHOR_EXISTS_REFUSING_OVERWRITE, "anchor": str(anchor_path())}
    rel_pin, rel_hash = _relative_to_tti(pin_path()), _relative_to_tti(pin_hash_path())
    for relative, path in ((rel_pin, pin_path()), (rel_hash, pin_hash_path())):
        committed = _git("cat-file", "blob", f"HEAD:{relative}", binary=True)
        if committed is None or committed != path.read_bytes():
            return {"outcome": PIN_NOT_COMMITTED, "path": relative,
                    "note": "commit the pin directory with git add -f before binding"}
        if _history_count(relative) != 1:
            return {"outcome": PIN_COMMIT_MISMATCH, "path": relative,
                    "note": "the pin has more than one commit in history"}
        if len(distinct_blobs(relative)) != 1:
            return {"outcome": PIN_RECREATED_IN_HISTORY, "path": relative,
                    "note": "another ref or reflog entry holds different pin bytes"}
    pin_commit = _git("log", "-n", "1", "--format=%H", "--", rel_pin)
    record = {"binding_version": BINDING_VERSION, "pin_relpath": rel_pin, "hash_relpath": rel_hash,
              "pin_sha256": check.pin_sha256, "pin_commit": pin_commit,
              "bound_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    binding_path().parent.mkdir(parents=True, exist_ok=True)
    with open(binding_path(), "x") as handle:
        handle.write(json.dumps(record, indent=1, sort_keys=True) + "\n")
    anchor = {"anchor_version": ANCHOR_VERSION, "pin_sha256": check.pin_sha256,
              "pin_commit": pin_commit, "bound_utc": record["bound_utc"]}
    try:
        anchor_path().parent.mkdir(parents=True, exist_ok=True)
        with open(anchor_path(), "x") as handle:
            handle.write(json.dumps(anchor, indent=1, sort_keys=True) + "\n")
    except OSError as error:
        binding_path().unlink()
        return {"outcome": PIN_WRITE_FAILED, "error": str(error),
                "note": "the anchor could not be written; the uncommitted binding was removed"}
    return {"outcome": PIN_BOUND, "binding": str(binding_path()), "pin_commit": pin_commit,
            "pin_sha256": check.pin_sha256, "anchor": str(anchor_path()),
            "next": "commit the binding file and copy the anchor record into the review record; "
                    "no stage after stage 2 runs until both are done"}


def verify_binding() -> str | None:
    """None when the committed binding holds; otherwise the provenance outcome."""
    path = binding_path()
    if not path.is_file():
        return PIN_BINDING_MISSING
    relative = _relative_to_tti(path)
    committed = _git("cat-file", "blob", f"HEAD:{relative}", binary=True)
    if committed is None:
        return PIN_BINDING_MISSING
    if committed != path.read_bytes() or _history_count(relative) != 1:
        return PIN_BINDING_REWRITTEN
    try:
        record = json.loads(committed)
        pin_commit, rel_pin = record["pin_commit"], record["pin_relpath"]
        rel_hash, pin_sha = record["hash_relpath"], record["pin_sha256"]
    except (ValueError, KeyError, TypeError):
        return PIN_BINDING_REWRITTEN
    if rel_pin != _relative_to_tti(pin_path()) or rel_hash != _relative_to_tti(pin_hash_path()):
        return PIN_COMMIT_MISMATCH
    if not pin_commit or _git("merge-base", "--is-ancestor", pin_commit, "HEAD") is None:
        return PIN_COMMIT_MISMATCH
    for rel, disk in ((rel_pin, pin_path()), (rel_hash, pin_hash_path())):
        blob = _git("cat-file", "blob", f"{pin_commit}:{rel}", binary=True)
        if blob is None or not disk.is_file() or blob != disk.read_bytes():
            return PIN_COMMIT_MISMATCH
    if hashlib.sha256(pin_path().read_bytes()).hexdigest() != pin_sha or _history_count(rel_pin) != 1:
        return PIN_COMMIT_MISMATCH
    if any(len(distinct_blobs(rel)) != 1 for rel in (rel_pin, rel_hash, relative)):
        return PIN_RECREATED_IN_HISTORY
    if not anchor_path().is_file():
        return PIN_ANCHOR_MISSING
    try:
        anchor = json.loads(anchor_path().read_bytes())
    except ValueError:
        return PIN_ANCHOR_MISMATCH
    if anchor.get("pin_sha256") != pin_sha or anchor.get("pin_commit") != pin_commit:
        return PIN_ANCHOR_MISMATCH
    return None


#  ------------------------------------------------------------ verification

@dataclass(frozen=True)
class Verification:
    status: str
    pin_sha256: str | None
    artifact_count: int
    missing: tuple
    drifted: tuple
    appeared: tuple
    binding_checked: bool = False

    def ok(self) -> bool:
        return self.status == PIN_VERIFIED

    def to_json(self) -> dict:
        return {"outcome": self.status, "pin_sha256": self.pin_sha256,
                "artifact_count": self.artifact_count, "missing": list(self.missing),
                "drifted": list(self.drifted), "appeared_after_pin": list(self.appeared),
                "binding_checked": self.binding_checked}


def verify_pin(require_binding: bool = False) -> Verification:
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
    if require_binding:
        failure = verify_binding()
        if failure:
            return Verification(failure, actual, len(expected), (), (), (), True)
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
                        tuple(drifted), tuple(appeared), require_binding)


def load_pinned_digests() -> dict:
    """Path to sha256 for every pinned artifact. Call only after verify_pin passes."""
    return {r["path"]: r["sha256"] for r in json.loads(pin_path().read_bytes())["artifacts"]}


MODULE_PIN_VERSION = "stepB_gate_module_pin:v2"


@dataclass(frozen=True)
class ModuleVerification:
    status: str
    missing: tuple
    drifted: tuple
    changed: tuple = ()

    def ok(self) -> bool:
        return self.status == MODULE_PIN_VERIFIED

    def to_json(self) -> dict:
        return {"outcome": self.status, "missing": list(self.missing),
                "drifted": list(self.drifted), "changed": list(self.changed)}


def tree_files(root) -> list:
    """Relative paths of every file under root, bytecode caches excluded."""
    root = Path(root).resolve()
    if not root.is_dir():
        return []
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*")
                  if p.is_file() and not _ignored(p.relative_to(root)))


def _cross_tree_mismatches(pairs) -> list:
    found = []
    for pair in pairs:
        a, b, exempt = Path(pair["a"]), Path(pair["b"]), set(pair.get("exempt") or ())
        files_a, files_b = set(tree_files(a)) - exempt, set(tree_files(b)) - exempt
        found.extend(f"only in {a}: {rel}" for rel in sorted(files_a - files_b))
        found.extend(f"only in {b}: {rel}" for rel in sorted(files_b - files_a))
        found.extend(f"differs: {rel}" for rel in sorted(files_a & files_b)
                     if file_digest(a / rel) != file_digest(b / rel))
    return found


def build_module_pin(roots=(), files=(), cross_tree=()) -> dict:
    """The G2 module pin: whole roots with full file lists, extra files, cross-tree pairs.

    Only what affects K belongs here: engine and runtime package roots in both
    checkouts, the admissibility artifact that defines K_L4*, the split and
    Lockbox manifests, and behaviour-preservation records. Gate scripts are
    governed by the tool manifest at G3b, not by this pin, so a committed fix to
    a gate script before G3b does not stop the gate.
    """
    artifacts, root_records, pairs = {}, [], []
    for root in roots:
        resolved = Path(root).resolve()
        listing = tree_files(resolved)
        root_records.append({"root": str(resolved), "files": listing})
        for relative in listing:
            artifacts[str(resolved / relative)] = file_digest(resolved / relative)
    for path in files:
        resolved = Path(path).resolve()
        artifacts[str(resolved)] = file_digest(resolved)
    for a, b, exempt in cross_tree:
        pairs.append({"a": str(Path(a).resolve()), "b": str(Path(b).resolve()),
                      "exempt": sorted(exempt)})
    return {"module_pin_version": MODULE_PIN_VERSION, "roots": root_records, "cross_tree": pairs,
            "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "artifacts": [{"path": k, "sha256": v} for k, v in sorted(artifacts.items())]}


def write_module_pin(roots=(), files=(), cross_tree=()) -> dict:
    """Write the module pin once, at G2. The caller commits both files. Never overwrites."""
    if module_pin_path().exists() or module_pin_hash_path().exists():
        return {"outcome": MODULE_PIN_EXISTS_REFUSING_OVERWRITE, "module_pin": str(module_pin_path())}
    pin = build_module_pin(roots, files, cross_tree)
    if not pin["artifacts"]:
        return {"outcome": MODULE_PIN_EMPTY}
    mismatch = _cross_tree_mismatches(pin["cross_tree"])
    if mismatch:
        return {"outcome": MODULE_TREE_MISMATCH, "changed": mismatch}
    data = json.dumps(pin, indent=1, sort_keys=True).encode()
    gate_dir().mkdir(parents=True, exist_ok=True)
    with open(module_pin_path(), "xb") as handle:
        handle.write(data)
    with open(module_pin_hash_path(), "x") as handle:
        handle.write(hashlib.sha256(data).hexdigest() + "\n")
    return {"outcome": MODULE_PIN_WRITTEN, "artifact_count": len(pin["artifacts"]),
            "module_pin": str(module_pin_path()),
            "next": "commit both module pin files; no stage after G2 runs until they are committed"}


def verify_module_pin() -> ModuleVerification:
    """Verify the second pinned set, fail closed.

    Both files must be committed exactly once, have one distinct blob across all
    refs and the reflog, and be byte-identical to HEAD. The pin must list at
    least one artifact. Every listed artifact must still hash to its recorded
    value. Every pinned root must hold exactly the recorded file list, so a new
    or removed module is caught. Every cross-tree pair must hold the same files
    with the same digests, apart from its declared exemptions.
    """
    pin_file, hash_file = module_pin_path(), module_pin_hash_path()
    if not pin_file.is_file() or not hash_file.is_file():
        return ModuleVerification(MODULE_PIN_MISSING, (), ())
    raw = pin_file.read_bytes()
    if (hash_file.read_text().split() or [""])[0] != hashlib.sha256(raw).hexdigest():
        return ModuleVerification(MODULE_PIN_ALTERED, (), ())
    for path in (pin_file, hash_file):
        relative = _relative_to_tti(path)
        blob = _git("cat-file", "blob", f"HEAD:{relative}", binary=True)
        if (blob is None or blob != path.read_bytes() or _history_count(relative) != 1
                or len(distinct_blobs(relative)) != 1):
            return ModuleVerification(MODULE_PIN_ALTERED, (), ())
    try:
        pin = json.loads(raw)
        expected = {r["path"]: r["sha256"] for r in pin["artifacts"]}
        roots = [(r["root"], list(r["files"])) for r in pin.get("roots") or ()]
        pairs = list(pin.get("cross_tree") or ())
    except (ValueError, KeyError, TypeError):
        return ModuleVerification(MODULE_PIN_ALTERED, (), ())
    if not expected:
        return ModuleVerification(MODULE_PIN_EMPTY, (), ())
    missing, drifted = [], []
    for path, digest in sorted(expected.items()):
        candidate = Path(path)
        if not candidate.is_file():
            missing.append(path)
        elif file_digest(candidate) != digest:
            drifted.append(path)
    if missing:
        return ModuleVerification(MODULE_ARTIFACT_MISSING, tuple(missing), tuple(drifted))
    if drifted:
        return ModuleVerification(MODULE_ARTIFACT_DRIFT, (), tuple(drifted))
    changed = [root for root, listing in roots if tree_files(root) != listing]
    if changed:
        return ModuleVerification(MODULE_SCOPE_CHANGED, (), (), tuple(changed))
    mismatch = _cross_tree_mismatches(pairs)
    if mismatch:
        return ModuleVerification(MODULE_TREE_MISMATCH, (), (), tuple(mismatch))
    return ModuleVerification(MODULE_PIN_VERIFIED, (), ())


def load_module_pinned_digests() -> dict:
    return {r["path"]: r["sha256"] for r in json.loads(module_pin_path().read_bytes())["artifacts"]}

#  ---------------------------------------------------------------- actions

def is_live_tree() -> bool:
    return (os.path.abspath(MAIN) == os.path.abspath(LIVE_MAIN)
            or os.path.realpath(MAIN) == os.path.realpath(LIVE_MAIN))


def create_pin() -> dict:
    if pin_dir().exists():
        return {"outcome": PIN_EXISTS_REFUSING_OVERWRITE, "pin": str(pin_dir())}
    ready = readiness()
    if ready.status != READY:
        return {"outcome": ready.status, "readiness": ready.to_json()}
    pin, stable = build_pin(ready)
    if not stable:
        return {"outcome": PIN_SOURCE_UNSTABLE, "readiness": ready.to_json(),
                "note": "the artifact set changed between two consecutive collections; nothing written"}
    again = readiness()
    if again.status != READY:
        return {"outcome": again.status, "readiness": again.to_json(),
                "note": "readiness changed during collection; nothing written"}
    if _identity([describe(p) for p in scope_files()]) != _identity(pin["artifacts"]):
        return {"outcome": PIN_SOURCE_UNSTABLE, "readiness": again.to_json(),
                "note": "the artifact set changed just before the write; nothing written"}
    try:
        pin_digest = write_pin(pin)
    except OSError as error:
        return {"outcome": PIN_EXISTS_REFUSING_OVERWRITE if pin_dir().exists() else PIN_WRITE_FAILED,
                "error": str(error)}
    check = verify_pin()
    if not check.ok():
        return {"outcome": PIN_WRITTEN_BUT_UNVERIFIED, "terminal": True, "pin_sha256": pin_digest,
                "verification": check.to_json(),
                "note": "the pin exists but failed its immediate verification; the gate stops "
                        "as a provenance failure; never repin"}
    return {"outcome": PIN_CREATED,
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
