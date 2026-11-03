"""Stdlib parent guard: fallback before model discovery, checkpoint salvage, wall reserve.

Only the newly spawned child session is supervised. No model, answer file,
signal-timer nesting, or neural selection code runs in this parent.
"""
from copy import deepcopy
from dataclasses import dataclass
import fcntl
import glob
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import time
import threading


_TERMINATION_SCOPE_ACTIVE = False


class TerminationRequest:
    """Scoped cooperative SIGTERM, not an asynchronous exception or exit replay.

    The previous handler is restored on exit but is not called for a signal
    received here. No masks/preexec hooks are inherited by the child. A request
    inside Popen waits until its return assigns the owned process before cleanup.
    SIGINT retains the caller's existing behavior. Main-thread, nonnested use.
    """
    def __init__(self):
        self.signum = None

    @property
    def requested(self):
        return self.signum is not None

    def _record(self, signum, frame):
        # No locks, I/O, raising, or previous-handler calls in the signal handler.
        if self.signum is None:
            self.signum = int(signum)

    def __enter__(self):
        global _TERMINATION_SCOPE_ACTIVE
        if threading.current_thread() is not threading.main_thread():
            raise RuntimeError("guardian SIGTERM scope requires the main thread")
        if _TERMINATION_SCOPE_ACTIVE:
            raise RuntimeError("nested guardian SIGTERM scopes are not supported")
        self.signum = None
        self.previous = signal.getsignal(signal.SIGTERM)
        signal.signal(signal.SIGTERM, self._record)
        _TERMINATION_SCOPE_ACTIVE = True
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        global _TERMINATION_SCOPE_ACTIVE
        try:
            signal.signal(signal.SIGTERM, self.previous)
        finally:
            _TERMINATION_SCOPE_ACTIVE = False
        return False


def valid_grid(g):
    return (type(g) is list and 1 <= len(g) <= 30 and type(g[0]) is list
            and 1 <= len(g[0]) <= 30 and all(type(r) is list and len(r) == len(g[0])
            and all(type(v) is int and 0 <= v <= 9 for v in r) for r in g))


def valid_pair(pair):
    return (type(pair) is dict and set(pair) == {"attempt_1", "attempt_2"}
            and all(valid_grid(v) for v in pair.values()))


def fallback(challenges):
    sub = {}
    for tid, task in challenges.items():
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", tid):
            raise ValueError("unsafe task identifier")
        if not isinstance(task.get("test"), list) or not task["test"]:
            raise ValueError("missing test inputs")
        sub[tid] = []
        for item in task["test"]:
            g = item.get("input")
            if not valid_grid(g):
                raise ValueError("invalid challenge input")
            sub[tid].append({"attempt_1": deepcopy(g), "attempt_2": deepcopy(g)})
    if not sub:
        raise ValueError("empty challenges")
    return sub


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + f".tmp.{os.getpid()}")
    try:
        with temp.open("w") as f:
            json.dump(value, f, allow_nan=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def read_json(path):
    try:
        path = Path(path)
        if path.stat().st_size > 64 * 1024 * 1024:
            return None
        return json.loads(path.read_text())
    except (OSError, ValueError, RecursionError):
        return None


def find_challenges(kaggle_root, rehearse=False):
    filename = "arc-agi_evaluation_challenges.json" if rehearse else "arc-agi_test_challenges.json"
    for directory in ("input/competitions/arc-prize-2026-arc-agi-2", "input/arc-prize-2026-arc-agi-2"):
        path = Path(kaggle_root) / directory / filename
        if path.is_file():
            return path
    hits = sorted(glob.glob(str(Path(kaggle_root) / "input" / "**" / filename), recursive=True))
    if not hits:
        raise FileNotFoundError("competition challenge file not found")
    return Path(hits[0])


def salvage(challenges, child_submission, run_dir):
    """Validate each query independently. Checkpoints contain already-ranked pairs.

    Precedence: completed task checkpoint, in-flight query checkpoint, child
    submission, fallback. A malformed query cannot erase valid other queries.
    """
    result = fallback(challenges)
    child = read_json(child_submission)
    if type(child) is dict:
        for tid, entries in result.items():
            incoming = child.get(tid)
            if type(incoming) is list:
                for j in range(min(len(entries), len(incoming))):
                    if valid_pair(incoming[j]):
                        entries[j] = incoming[j]
    recovered = 0
    for tid, entries in result.items():
        for folder in ("progress", "pools"):
            record = read_json(Path(run_dir) / folder / (tid + ".json"))
            if type(record) is not dict or record.get("task") != tid:
                continue
            selected = record.get("selected")
            if type(selected) is not list:
                continue
            for j in range(min(len(entries), len(selected))):
                if valid_pair(selected[j]):
                    entries[j] = selected[j]
        recovered += sum(result[tid][j] != fallback({tid: challenges[tid]})[tid][j]
                         for j in range(len(entries)))
    return result, recovered


@dataclass(frozen=True)
class Budget:
    start: float
    total_s: float
    serialization_s: float
    shutdown_s: float

    def __post_init__(self):
        if (any(not math.isfinite(x) or x < 0 for x in
                (self.start, self.total_s, self.serialization_s, self.shutdown_s))
                or self.total_s <= self.serialization_s + self.shutdown_s):
            raise ValueError("invalid parent runtime budget")

    def work_left(self, now=None):
        now = time.monotonic() if now is None else now
        return max(0.0, self.start + self.total_s - self.serialization_s - self.shutdown_s - now)

    def task_seconds(self, outstanding, workers, task_cap=900, now=None):
        # Planning helper; the outer process guard remains the global wall bound.
        left = self.work_left(now)
        return max(0.0, min(task_cap, left, left * workers / max(1, outstanding)))


def stop_owned_session(process, grace_s):
    """Terminate only the session created by this Popen(start_new_session=True).

    The session is exclusively owned for this run. No name matching or system
    process search is used. Process groups do not include the parent/notebook.
    """
    try:
        if process.poll() is None and os.getpgid(process.pid) != process.pid:
            raise RuntimeError("owned child lost its separate process group")
    except ProcessLookupError:
        # The leader can exit after poll(); its descendants still occupy our
        # separately created group and must reach the cleanup below.
        pass
    # A session remains ours while any of its workers survive the leader. Its
    # identifier cannot be allocated to a new process while those members live.
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        process.wait(timeout=max(1, grace_s))
        return
    until = time.monotonic() + grace_s
    while time.monotonic() < until:
        process.poll()  # reap a finished leader; workers can outlive it
        try:
            os.killpg(process.pid, 0)
        except ProcessLookupError:
            return
        time.sleep(min(.02, max(0, until - time.monotonic())))
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait(timeout=max(1, grace_s))


def supervise(challenges, submission, run_dir, command, *, budget, env=None,
              cwd=None, poll_s=1.0, terminate_grace_s=5.0):
    """Prewrite fallback, supervise a fresh session, preserve checkpoints at exit.

    This is a local tested safety layer, not an OS or Kaggle runtime certificate.
    If this parent is killed, its last atomically written submission still exists.
    """
    submission, run_dir = Path(submission), Path(run_dir)
    submission.parent.mkdir(parents=True, exist_ok=True)
    lease_path = submission.parent / ".submission_guard.lock"
    process = None
    start = time.monotonic()
    with TerminationRequest() as termination, lease_path.open("a+") as lease:
        fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if run_dir.exists():
            raise FileExistsError("fresh exclusively owned run directory required")
        run_dir.mkdir(parents=True)
        atomic_json(submission, fallback(challenges))  # before any model/PEFT imports
        report = {"status": "FALLBACK_WRITTEN", "child_pid": None,
                  "run_dir": str(run_dir), "recovered_queries": 0}
        child_env = dict(os.environ if env is None else env)
        child_env["SF_RUN_DIR"] = str(run_dir)
        child_env["SF_CHILD_SUBMISSION"] = str(run_dir / "child_submission.json")
        original = float(child_env.get("SF_DEADLINE_S", "41400"))
        child_env["SF_DEADLINE_S"] = str(min(original, budget.work_left()))
        child_env["PYTHONDONTWRITEBYTECODE"] = "1"
        try:
            if termination.requested:
                report["status"] = "PARENT_SIGTERM"
            elif budget.work_left() <= 0:
                report["status"] = "PREPARATION_EXHAUSTED_BUDGET"
            else:
                with (run_dir / "child.log").open("wb") as log:
                    process = subprocess.Popen(command, env=child_env, cwd=cwd,
                                               stdout=log, stderr=subprocess.STDOUT,
                                               start_new_session=True)
                    report.update(status="RUNNING", child_pid=process.pid)
                    while process.poll() is None and not termination.requested:
                        sub, recovered = salvage(challenges, submission, run_dir)
                        atomic_json(submission, sub)
                        report["recovered_queries"] = recovered
                        if termination.requested:
                            break
                        left = budget.work_left()
                        if left <= 0:
                            report["status"] = "PARENT_WALL_LIMIT"
                            break
                        time.sleep(min(poll_s, left))
                    if termination.requested:
                        report["status"] = "PARENT_SIGTERM"
                    elif report["status"] == "RUNNING":
                        report["status"] = "CHILD_EXIT"
        finally:
            if process is not None:
                try:
                    stop_owned_session(process, min(terminate_grace_s, max(.01, budget.shutdown_s)))
                except OSError as error:
                    report["shutdown_error"] = type(error).__name__
                report["child_returncode"] = process.poll()
            if termination.requested:
                report.update(status="PARENT_SIGTERM", termination_signal=termination.signum)
            sub, recovered = salvage(challenges, submission, run_dir)
            atomic_json(submission, sub)
            report.update(recovered_queries=recovered, wall_s=time.monotonic() - start,
                          remaining_serialization_s=budget.start + budget.total_s - time.monotonic(),
                          schema_valid=True)
            if termination.requested:
                report.update(status="PARENT_SIGTERM", termination_signal=termination.signum)
            atomic_json(run_dir / "guard_status.json", report)
        return report
