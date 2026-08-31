"""Exact Kaggle-runtime emulator for ARC-AGI-2 submissions (Gate C0).

Emulates the 2026 competition contract for a pluggable solver:

- a task set in the public ARC JSON format ({task_id: {"train": [...], "test": [...]}});
- EXACTLY two attempts per test input;
- one global wall-clock budget (default 12 h, scalable for development);
- per-task and total CPU/wall/memory accounting;
- offline execution (a socket guard makes any network call raise, as on Kaggle);
- pass@2 scoring against a solutions file when one is provided
  (per test output: correct iff attempt 1 OR attempt 2 matches exactly;
  task score = mean over its test outputs; total = mean over tasks —
  the strict all-outputs-correct count is also reported).

Split discipline (docs/CORA_DATA_ACCESS_DAG.md): runs restricted to the frozen
eval-split roles. role="dev" is free; role="holdout" REQUIRES a gate label in
{"C3","C4","C5"} and appends an entry to outputs/tti/holdout_ledger.jsonl — scoring
the holdout outside a gate is a protocol breach and raises. Task identities are data
plumbing only: nothing here branches on a task id.

The solver contract is a single callable:

    solve(train_pairs, test_inputs, budget_s) -> [[attempt1, attempt2], ...]

one [attempt1, attempt2] per test input, each attempt a grid (list of lists) or None.
The emulator never inspects HOW the solver works; the anytime scheduler (later phase)
will replace the default equal-split per-task budgeting via the `schedule` hook.
"""
from __future__ import annotations

import hashlib
import json
import resource
import socket
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SPLIT_FILE = ROOT / "outputs" / "tti" / "eval_split_v1.json"
LEDGER_FILE = ROOT / "outputs" / "tti" / "holdout_ledger.jsonl"

KAGGLE_BUDGET_S = 12 * 3600.0
ATTEMPTS = 2

Solver = Callable[[Sequence[Mapping[str, Any]], Sequence[Any], float],
                  Sequence[Sequence[Any]]]


class NetworkForbidden(RuntimeError):
    """Raised by the socket guard: the Kaggle notebook is offline."""


class _SocketGuard:
    """While active, any attempt to create a socket raises NetworkForbidden."""

    def __enter__(self):
        self._saved = socket.socket.__init__

        def refuse(*args, **kwargs):
            raise NetworkForbidden("network access is forbidden under the Kaggle "
                                   "emulator (offline notebook)")

        socket.socket.__init__ = refuse
        return self

    def __exit__(self, *exc):
        socket.socket.__init__ = self._saved
        return False


def _cpu_seconds() -> float:
    self_ru = resource.getrusage(resource.RUSAGE_SELF)
    child_ru = resource.getrusage(resource.RUSAGE_CHILDREN)
    return (self_ru.ru_utime + self_ru.ru_stime
            + child_ru.ru_utime + child_ru.ru_stime)


def _peak_rss_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def load_split(role: str, split_file: Path = SPLIT_FILE) -> list[str]:
    split = json.loads(split_file.read_text())
    if role not in ("dev", "holdout"):
        raise ValueError(f"unknown split role {role!r} (dev|holdout)")
    return list(split[role])


@dataclass
class EmulatorConfig:
    budget_s: float = KAGGLE_BUDGET_S
    #: development convenience: scale the whole budget (1.0 = full Kaggle contract)
    budget_scale: float = 1.0
    #: offline guard active (Kaggle contract); disable only for local debugging
    forbid_network: bool = True
    #: minimum per-task budget floor, seconds
    min_task_budget_s: float = 1.0
    #: optional replacement for equal-split budgeting:
    #: schedule(remaining_s, remaining_task_count) -> budget for the next task
    schedule: Callable[[float, int], float] | None = None
    #: role of the task set: "train-like" (free), "dev", or "holdout"
    role: str = "train-like"
    #: REQUIRED when role == "holdout": the gate being scored ("C3"|"C4"|"C5")
    gate: str | None = None
    ledger_file: Path = LEDGER_FILE


def _grids_equal(a, b) -> bool:
    return a is not None and b is not None and a == b


def run(tasks: Mapping[str, Mapping[str, Any]], solver: Solver,
        config: EmulatorConfig,
        solutions: Mapping[str, Sequence[Any]] | None = None) -> dict:
    """Run `solver` over `tasks` under the emulated Kaggle contract; return report."""
    if config.role == "holdout":
        if config.gate not in ("C3", "C4", "C5"):
            raise PermissionError(
                "holdout may only be scored at gates C3/C4/C5; pass "
                "EmulatorConfig(gate=...) and accept the ledger entry")
    total_budget = config.budget_s * config.budget_scale
    order = sorted(tasks)                       # deterministic, id-blind order
    started_wall = time.monotonic()
    started_cpu = _cpu_seconds()
    per_task, predictions = [], {}
    guard = _SocketGuard() if config.forbid_network else None
    if guard:
        guard.__enter__()
    try:
        for index, task_id in enumerate(order):
            remaining = total_budget - (time.monotonic() - started_wall)
            remaining_tasks = len(order) - index
            if remaining <= 0:
                per_task.append({"task": task_id, "skipped_no_budget": True})
                predictions[task_id] = [[None, None]
                                        for _ in tasks[task_id]["test"]]
                continue
            if config.schedule is not None:
                budget = config.schedule(remaining, remaining_tasks)
            else:
                budget = remaining / remaining_tasks
            budget = max(config.min_task_budget_s, min(budget, remaining))
            t0_wall, t0_cpu = time.monotonic(), _cpu_seconds()
            train = tasks[task_id]["train"]
            test_inputs = [t["input"] for t in tasks[task_id]["test"]]
            try:
                attempts = solver(train, test_inputs, budget)
            except NetworkForbidden:
                raise
            except Exception as error:          # a solver crash forfeits the task only
                attempts = [[None, None] for _ in test_inputs]
                per_task.append({"task": task_id, "error": repr(error)[:200]})
            wall = time.monotonic() - t0_wall
            cpu = _cpu_seconds() - t0_cpu
            #  normalize: exactly ATTEMPTS entries per test input
            normal = []
            for i in range(len(test_inputs)):
                row = list(attempts[i]) if i < len(attempts) else []
                row = (row + [None] * ATTEMPTS)[:ATTEMPTS]
                normal.append(row)
            predictions[task_id] = normal
            per_task.append({"task": task_id, "wall_s": round(wall, 3),
                             "cpu_s": round(cpu, 3),
                             "budget_s": round(budget, 3),
                             "over_budget": wall > budget * 1.05,
                             "test_inputs": len(test_inputs)})
    finally:
        if guard:
            guard.__exit__(None, None, None)

    report: dict = {
        "contract": {"budget_s": total_budget, "attempts": ATTEMPTS,
                     "offline": config.forbid_network, "role": config.role,
                     "tasks": len(order)},
        "resources": {"wall_s": round(time.monotonic() - started_wall, 3),
                      "cpu_s": round(_cpu_seconds() - started_cpu, 3),
                      "peak_rss_mb": round(_peak_rss_mb(), 1)},
        "per_task": per_task,
        "within_budget": (time.monotonic() - started_wall) <= total_budget,
    }
    #  hash over predictions only: timing never enters the result identity
    canonical = json.dumps(predictions, sort_keys=True)
    report["predictions_sha256"] = hashlib.sha256(canonical.encode()).hexdigest()

    if solutions is not None:
        task_scores, strict = {}, 0
        for task_id in order:
            outputs = solutions[task_id]
            rows = predictions[task_id]
            correct = [any(_grids_equal(a, outputs[i]) for a in rows[i])
                       for i in range(len(outputs))]
            task_scores[task_id] = sum(correct) / max(1, len(correct))
            strict += all(correct)
        report["score"] = {
            "pass_at_2": round(sum(task_scores.values()) / max(1, len(task_scores)), 6),
            "tasks_fully_correct": strict,
            "tasks_partially_correct": sum(0 < s < 1 for s in task_scores.values()),
            "per_task": {k: round(v, 4) for k, v in sorted(task_scores.items())},
        }
    if config.role == "holdout":
        config.ledger_file.parent.mkdir(parents=True, exist_ok=True)
        entry = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "gate": config.gate,
                 "tasks": len(order),
                 "pass_at_2": report.get("score", {}).get("pass_at_2"),
                 "predictions_sha256": report["predictions_sha256"]}
        with config.ledger_file.open("a") as handle:
            handle.write(json.dumps(entry, sort_keys=True) + "\n")
        report["ledgered"] = entry
    return report


def run_files(challenges: Path, solver: Solver, config: EmulatorConfig,
              solutions: Path | None = None,
              restrict_to: Sequence[str] | None = None) -> dict:
    """Convenience wrapper over ARC-format files, with optional id restriction
    (e.g. the frozen dev split)."""
    tasks = json.loads(Path(challenges).read_text())
    if restrict_to is not None:
        tasks = {k: tasks[k] for k in restrict_to}
    sols = None
    if solutions is not None:
        sols = json.loads(Path(solutions).read_text())
        sols = {k: sols[k] for k in tasks}
    return run(tasks, solver, config, sols)
