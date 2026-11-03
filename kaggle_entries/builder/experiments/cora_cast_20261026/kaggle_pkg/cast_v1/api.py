"""CAST v1 core for the Kaggle entry (configuration B): one call, hard caps, deterministic, fail-safe.

    from cast_v1 import cast_candidates
    grids = cast_candidates(task)              # list over test inputs: a grid (list of lists) or None
    info = cast_candidates(task, details=True) # {"grids": [...], "module": [...], "program": [...], "status": ...}

`task` is a Kaggle/ARC task dict ({"train": [{"input", "output"}, ...], "test": [{"input"}, ...]}). Test outputs are
never read. Modules, in this fixed order (the frozen CAST v1 core): M4 general symmetry completion (complete
predictions only), M2 typed guarded rewriting and guarded frames, L0 contract-guided search (depth 2, 1,000 executions).
General acceptance rule (task-independent; no task ids, no special cases). A module's first attempt for a query is
returned only if
  1. its program reproduces EVERY demonstration exactly (by construction of every module);
  2. the answer is complete: a valid grid (1..30 x 1..30, colours 0..9), not the unchanged query input, and for M4 no
     undetermined cell;
  3. leave-one-demonstration-out passes: with each demonstration held out in turn, the same module rebuilt from the
     remaining demonstrations ranks that demonstration's output among its top two attempts (tasks with fewer than two
     demonstrations are never accepted).
Queries take the first accepting module in the order above; others get None. Hard caps per call: `cpu_s` of process
CPU (ITIMER_VIRTUAL) and `wall_s` of wall time (ITIMER_REAL), both from the main thread; any error, timeout or invalid
input returns None for every query. The caller's signal handlers and timers are restored afterwards.
"""
import signal
import threading
import time

import numpy as np

from . import absdom as D
from . import candidates as CA
from . import grids as G
from . import ops as O
from . import rewrite as RW
from . import search as SR
from . import symmetry as S

VERSION = "cast-v1-core-1"
ORDER = ("m4", "m2", "l0")


class _Timeout(BaseException):
    pass


# ------------------------------------------------------------------ the three frozen modules
def _m4_decide(op, thetas, demos):
    fits = []
    for th in thetas:
        if any(not D.contains(op.fwd(D.alpha(x), th), y) for x, y in demos):
            continue
        ok = True
        for x, y in demos:
            out = op.apply(x, th)
            if out is None or out.shape != y.shape or not np.array_equal(out, y):
                ok = False
                break
        if ok:
            fits.append(th)
    return fits


def _m4(task):
    op = S.SymComplete(0.5, 0.5)
    demos = [(np.asarray(x), np.asarray(y)) for x, y in task["train"]]
    qs = [np.asarray(q) for q in task["test_inputs"]]
    ctx = O.TaskCtx(task["train"], task["test_inputs"])
    fits = []
    for k, th in enumerate(_m4_decide(op, op.domain(ctx), demos)):
        preds, complete = [], []
        for q in qs:
            out = op.apply(q, th)
            preds.append(out)
            complete.append(out is not None and (op.last_trace or {}).get("status") == "COMPLETE")
        fits.append({"program": f"(symcomplete mask={th[0]} crop={th[1]})", "preds": preds, "complete": complete,
                     "cost": 1.0, "order": k, "loo": 0.0})
    return fits


def _m2(task):
    return RW.search(task)


def _l0(task):
    ctx = O.TaskCtx(task["train"], task["test_inputs"])
    r = SR.Searcher(ctx, O.L0, depth=2, mode="fwdbwd", max_exec=1000, oe=True, max_fits=32).run()
    return [{"program": " ; ".join(f"{n}{th!r}" for n, th in f["program"]),
             "preds": [None if p is None else np.asarray(p) for p in f["preds"]],
             "complete": [p is not None for p in f["preds"]], "cost": float(len(f["program"])), "order": i}
            for i, f in enumerate(r["fits"])]


MODULES = {"m4": _m4, "m2": _m2, "l0": _l0}


def _ranked(module, task):
    fits = MODULES[module](task)
    if module == "m4":
        fits = [f for f in fits if all(f["complete"])] or [f for f in fits if any(f["complete"])]
    demos = [(np.asarray(x), np.asarray(y)) for x, y in task["train"]]
    qs = [np.asarray(q) for q in task["test_inputs"]]
    groups = CA.rank(fits, {"train": demos, "test_inputs": qs})
    return groups, CA.attempts(groups, len(qs))


def _loo_pass(module, task):
    if len(task["train"]) < 2:
        return False
    for i in range(len(task["train"])):
        rest = [d for j, d in enumerate(task["train"]) if j != i]
        sub = {"train": rest, "test_inputs": [task["train"][i][0]]}
        _, atts = _ranked(module, sub)
        y = np.asarray(task["train"][i][1])
        if not any(np.asarray(a).shape == y.shape and np.array_equal(np.asarray(a), y) for a in atts[0]):
            return False
    return True


# ------------------------------------------------------------------ input, caps, entry point
def _norm(task):
    train = [(p["input"], p["output"]) if isinstance(p, dict) else (p[0], p[1]) for p in task["train"]]
    tests = task.get("test_inputs")
    if tests is None:
        tests = [t["input"] if isinstance(t, dict) else t for t in task["test"]]
    for g in [a for a, _ in train] + [b for _, b in train] + list(tests):
        if not G.valid_grid(np.asarray(g)):
            raise ValueError("invalid grid")
    return {"task_id": "task", "train": train, "test_inputs": list(tests)}


class _Caps:
    def __init__(self, cpu_s, wall_s):
        self.cpu_s, self.wall_s, self.on = cpu_s, wall_s, threading.current_thread() is threading.main_thread()

    def __enter__(self):
        if self.on:
            def boom(signum, frame):                          # noqa: ARG001
                raise _Timeout()
            self.old = (signal.signal(signal.SIGVTALRM, boom), signal.signal(signal.SIGALRM, boom))
            self.old_t = (signal.setitimer(signal.ITIMER_VIRTUAL, self.cpu_s),
                          signal.setitimer(signal.ITIMER_REAL, self.wall_s))
        return self

    def __exit__(self, *exc):
        if self.on:
            signal.setitimer(signal.ITIMER_VIRTUAL, 0)
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGVTALRM, self.old[0])
            signal.signal(signal.SIGALRM, self.old[1])
            for which, (val, interval) in ((signal.ITIMER_VIRTUAL, self.old_t[0]), (signal.ITIMER_REAL, self.old_t[1])):
                if val > 0:
                    signal.setitimer(which, val, interval)
        return False


def cast_candidates(task, cpu_s=15.0, wall_s=30.0, details=False):
    n_test = len(task.get("test", task.get("test_inputs", [])) or [])
    info = {"grids": [None] * n_test, "module": [None] * n_test, "program": [None] * n_test, "status": "NONE",
            "version": VERSION, "cpu_s": 0.0}
    t0 = time.process_time()
    try:
        with _Caps(cpu_s, wall_s):
            t = _norm(task)
            changes = all(np.asarray(x).shape != np.asarray(y).shape or not np.array_equal(x, y) for x, y in t["train"])
            for module in ORDER:
                if all(g is not None for g in info["grids"]):
                    break
                groups, atts = _ranked(module, t)
                if not any(atts) or not _loo_pass(module, t):
                    continue
                for j, q in enumerate(t["test_inputs"]):
                    if info["grids"][j] is not None or not atts[j]:
                        continue
                    g = np.asarray(atts[j][0])
                    if not G.valid_grid(g) or (changes and g.shape == np.asarray(q).shape and np.array_equal(g, q)):
                        continue
                    info["grids"][j] = g.astype(int).tolist()
                    info["module"][j] = module
                    info["program"][j] = groups[0]["members"][0]["program"] if groups else None
            info["status"] = "OK"
    except _Timeout:
        info.update(grids=[None] * n_test, module=[None] * n_test, program=[None] * n_test, status="TIMEOUT")
    except Exception as e:                                    # noqa: BLE001  fail-safe by contract
        info.update(grids=[None] * n_test, module=[None] * n_test, program=[None] * n_test,
                    status=f"ERROR:{type(e).__name__}")
    info["cpu_s"] = round(time.process_time() - t0, 3)
    return info if details else info["grids"]
