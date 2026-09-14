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

BOUND TO A COMMIT. A digest stored beside the pin cannot detect a pin that was
deleted and recreated. So after the pin directory is committed, `bind_pin`
writes a tracked binding record naming the pin's sha256 and its commit. Every
stage after stage 2 verifies with `require_binding=True`: the binding is
committed exactly once, its pin commit is an ancestor of HEAD, and the on-disk
pin and digest are byte-identical to the blobs in that commit. A recreated pin
has different bytes and fails as PIN_COMMIT_MISMATCH.
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
FREEZE_MARKER = "STEP B FROZEN"
RUNNER_SCRIPT = "cora_level4_stepB_run.py"
RUNNER_MODULE = "cora_level4_stepB_run"
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

READINESS_OUTCOMES = (READY, FREEZE_MARKER_ABSENT, FREEZE_OUTPUT_NOT_READY,
                      FREEZE_RUNNER_STILL_ACTIVE)
PROVENANCE_FAILURES = (PIN_MISSING, PIN_HASH_RECORD_MISSING, PIN_JSON_ALTERED,
                       PIN_ARTIFACT_MISSING, PIN_ARTIFACT_DRIFT,
                       PIN_SCOPE_GREW_AFTER_FREEZE, PIN_BINDING_MISSING,
                       PIN_BINDING_REWRITTEN, PIN_COMMIT_MISMATCH, MODULE_PIN_MISSING,
                       MODULE_PIN_ALTERED, MODULE_ARTIFACT_MISSING, MODULE_ARTIFACT_DRIFT)

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
        done = subprocess.run(["git", "-C", str(TTI), *args], capture_output=True, check=False)
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


def bind_pin() -> dict:
    """Record, in a tracked file, which commit holds the pin. Run once, after committing the pin."""
    check = verify_pin(require_binding=False)
    if not check.ok():
        return {"outcome": check.status, "verification": check.to_json()}
    if binding_path().exists():
        return {"outcome": PIN_BINDING_EXISTS_REFUSING_OVERWRITE, "binding": str(binding_path())}
    rel_pin, rel_hash = _relative_to_tti(pin_path()), _relative_to_tti(pin_hash_path())
    for relative, path in ((rel_pin, pin_path()), (rel_hash, pin_hash_path())):
        committed = _git("cat-file", "blob", f"HEAD:{relative}", binary=True)
        if committed is None or committed != path.read_bytes():
            return {"outcome": PIN_NOT_COMMITTED, "path": relative,
                    "note": "commit the pin directory with git add -f before binding"}
        if _history_count(relative) != 1:
            return {"outcome": PIN_COMMIT_MISMATCH, "path": relative,
                    "note": "the pin has more than one commit in history"}
    pin_commit = _git("log", "-n", "1", "--format=%H", "--", rel_pin)
    record = {"binding_version": BINDING_VERSION, "pin_relpath": rel_pin, "hash_relpath": rel_hash,
              "pin_sha256": check.pin_sha256, "pin_commit": pin_commit,
              "bound_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    binding_path().parent.mkdir(parents=True, exist_ok=True)
    with open(binding_path(), "x") as handle:
        handle.write(json.dumps(record, indent=1, sort_keys=True) + "\n")
    return {"outcome": PIN_BOUND, "binding": str(binding_path()), "pin_commit": pin_commit,
            "pin_sha256": check.pin_sha256,
            "next": "commit the binding file; no stage after stage 2 runs until it is committed"}


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


@dataclass(frozen=True)
class ModuleVerification:
    status: str
    missing: tuple
    drifted: tuple

    def ok(self) -> bool:
        return self.status == MODULE_PIN_VERIFIED

    def to_json(self) -> dict:
        return {"outcome": self.status, "missing": list(self.missing), "drifted": list(self.drifted)}


def verify_module_pin() -> ModuleVerification:
    """Verify the second pinned set, fail closed.

    The G2 module pin covers what the first pin cannot: engine and runtime
    modules in the dev worktree, the admissibility artifact that defines
    K_L4*, the split and Lockbox manifests, every gate script, and any
    behaviour-preservation record. Format: {"artifacts": [{"path", "sha256"}]}
    with a sibling digest file. Both files must be committed exactly once and
    be byte-identical to HEAD, and every listed artifact must still hash to its
    recorded value. The dev worktree is active, so without this a change to K
    applied equally to both conditions would pass every digest comparison.
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
        if blob is None or blob != path.read_bytes() or _history_count(relative) != 1:
            return ModuleVerification(MODULE_PIN_ALTERED, (), ())
    try:
        expected = {r["path"]: r["sha256"] for r in json.loads(raw)["artifacts"]}
    except (ValueError, KeyError, TypeError):
        return ModuleVerification(MODULE_PIN_ALTERED, (), ())
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
    try:
        pin_digest = write_pin(pin)
    except OSError as error:
        return {"outcome": PIN_EXISTS_REFUSING_OVERWRITE if pin_dir().exists() else PIN_WRITE_FAILED,
                "error": str(error)}
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
