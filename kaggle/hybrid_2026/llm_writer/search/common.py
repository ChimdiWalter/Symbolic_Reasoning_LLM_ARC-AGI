"""Shared pieces of the search components: paths, the CPU budget, tasks and execution through the existing executor.

Budgets are CPU seconds, never wall-clock seconds (the development machine is shared and often oversubscribed, so a
wall-clock budget would measure its load). The clock counts this process, every reaped child (each SWI-Prolog run)
and the live grid-function worker process (read from /proc), so the cost of failed candidates and of the Prolog
backend is charged like everything else. Expected test outputs never enter this package: a task here is
{"train": [(input, output)], "test_inputs": [grid]}.
"""
import os
import resource
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
WRITER = os.path.dirname(HERE)
HYBRID = os.path.dirname(WRITER)
REPO = os.path.dirname(os.path.dirname(HYBRID))
_TICK = os.sysconf("SC_CLK_TCK") if hasattr(os, "sysconf") else 100


def ensure_paths():
    """Make `cora_neural_*`, `geocat_arc` and `llm_writer` importable (scripts and tests)."""
    for p in (HYBRID, REPO):
        if p not in sys.path:
            sys.path.insert(0, p)


def _worker_cpu():
    """CPU seconds of the live grid-function worker (0 if none). A worker that was recycled has been reaped and is
    then counted by RUSAGE_CHILDREN instead."""
    sb = sys.modules.get("llm_writer.gridfn.sandbox")
    inst = getattr(sb, "_DEFAULT", None) if sb else None
    proc = getattr(inst, "proc", None)
    if proc is None or proc.poll() is not None:
        return 0.0
    try:
        with open(f"/proc/{proc.pid}/stat") as f:
            fields = f.read().rsplit(")", 1)[1].split()
        return (int(fields[11]) + int(fields[12])) / _TICK
    except (OSError, IndexError, ValueError):
        return 0.0


def cpu_now():
    """Process CPU + reaped children's CPU + the live grid-function worker's CPU, in seconds."""
    ru = resource.getrusage(resource.RUSAGE_CHILDREN)
    return time.process_time() + ru.ru_utime + ru.ru_stime + _worker_cpu()


class CPUBudget:
    """A CPU-second allowance. `charge(s)` adds a cost paid elsewhere (for example a cached seed evaluation that an
    earlier arm paid for), so arms sharing a cache are still charged the same."""

    def __init__(self, seconds):
        self.limit = float(seconds)
        self.t0 = cpu_now()
        self.extra = 0.0

    def used(self):
        return cpu_now() - self.t0 + self.extra

    def left(self):
        return self.limit - self.used()

    def exhausted(self):
        return self.used() >= self.limit

    def charge(self, seconds):
        self.extra += float(seconds)


def task_of(task_json):
    """The solver-side task of a challenge record: demonstrations and test inputs only."""
    return {"train": [(p["input"], p["output"]) for p in task_json["train"]],
            "test_inputs": [c["input"] for c in task_json["test"]]}


def colours(task):
    """Colours present in any demonstration grid or test input (visible data only)."""
    out = set()
    for a, b in task["train"]:
        out |= set(np.unique(np.asarray(a)).tolist()) | set(np.unique(np.asarray(b)).tolist())
    for t in task["test_inputs"]:
        out |= set(np.unique(np.asarray(t)).tolist())
    return sorted(int(c) for c in out)


def behaviour_key(preds):
    """One key per distinct test behaviour (two fitting programs with equal predictions on every test input)."""
    return "|".join(";".join(",".join(str(int(v)) for v in row) for row in np.asarray(p).tolist()) for p in preds)


class Result:
    """One executed candidate: the program, the existing executor's Execution record, the objective, its cost."""
    __slots__ = ("key", "prog", "ex", "obj", "cpu", "origin", "parent", "op")

    def __init__(self, key, prog, ex, obj, cpu, origin=None, parent=None, op=None):
        self.key, self.prog, self.ex, self.obj, self.cpu = key, prog, ex, obj, cpu
        self.origin, self.parent, self.op = origin, parent, op

    @property
    def status(self):
        return self.ex.status

    @property
    def fits(self):
        return self.ex.status == "FITS"

    def preds(self):
        return [np.asarray(p).tolist() for p in (self.ex.preds or [])]


class Runner:
    """Executes candidates with the existing executor (`llm_writer.cora_exec.run`; a grid-function program through
    `llm_writer.gridfn.adapter.execute`, the same record, with a tighter step limit for search), caches by
    canonical key and charges the CPU of every execution, including failed ones, to the budget's clock."""

    def __init__(self, task, language, guard_s=5.0, gridfn_steps=2_000_000):
        from llm_writer.search import lang as LG
        from llm_writer.search import objective as OB
        self.task, self.L, self.guard_s = task, LG.get(language), guard_s
        self.OB = OB
        self.cache = {}
        self.n_exec = 0
        self.cpu = 0.0
        self.gridfn_steps = gridfn_steps

    def run(self, prog, origin=None, parent=None, op=None):
        key = self.L.key(prog)
        hit = self.cache.get(key)
        if hit is not None:
            return hit, False
        t0 = cpu_now()
        ex = self.L.execute(prog, self.task, self.guard_s, self.gridfn_steps)
        obj = self.OB.score(self.task, ex)
        dt = cpu_now() - t0
        self.n_exec += 1
        self.cpu += dt
        res = Result(key, prog, ex, obj, dt, origin, parent, op)
        self.cache[key] = res
        return res, True
