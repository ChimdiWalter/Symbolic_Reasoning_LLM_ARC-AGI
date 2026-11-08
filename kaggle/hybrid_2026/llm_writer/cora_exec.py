"""CORA's execution of one program on a task, with a time guard: `cora_neural_hybrid.execute` semantics (INVALID,
ERROR, FITS, INCOMPLETE; fixed, broken and still-wrong cell counts and masks; test predictions for fits), extended
to demonstrations whose output shape differs from the input (there only wrong cells are defined), plus
changed-cell precision and recall. Demonstrations and test inputs only: expected test outputs never enter here.

Every program is CORA data (a rast AST or a version 4 G4Program) executed by CORA's own interpreters: a native
program is compiled once by `cora_neural_v2g2.grammar.compile_program` and run by native `render_program`
(`grammar.run`), exactly the path of `cora_neural_v2g3.delta`; a G4Program runs through
`cora_neural_v2g4.program.execute`. The masks are those of `cora_neural_v2g3.delta.DemoDelta`.
"""
import signal
import threading
import time
from contextlib import contextmanager

import numpy as np

from cora_neural_v2.rast import ASTError
from cora_neural_v2g2 import grammar as G
from cora_neural_v2g3 import delta as D
from cora_neural_v2g4 import program as PG
from cora_neural_hybrid import execute as EX

STATS = {"programs": 0, "grid_runs": 0, "timeouts": 0, "exec_s": 0.0}


class ExecTimeout(Exception):
    pass


@contextmanager
def time_guard(seconds):
    """Raise ExecTimeout after `seconds` of wall time (main thread only; elsewhere no guard)."""
    if seconds is None or threading.current_thread() is not threading.main_thread():
        yield
        return

    def _raise(signum, frame):                      # noqa: ARG001
        raise ExecTimeout()
    old = signal.signal(signal.SIGALRM, _raise)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


def foreign(program):
    """A program of another bounded language (the gridfn adapter contract: it carries its own `run`)."""
    from cora_neural_v2.rast import N
    return not isinstance(program, (N, PG.G4Program)) and callable(getattr(program, "run", None))


LAST_ERROR = {"message": None}


def _native_runner(d):
    """Exactly native's execution path (`cora_neural_v2.bridge.run_native_dict`: program_from_dict, then
    render_program on a Grid), built once, keeping native's error message (for example "color_map has no entry for
    color 4") instead of discarding it, so the diagnosis can name the cause."""
    from geocat_arc.object_reasoning.actions import render_program
    from geocat_arc.object_reasoning.expressions import EvalError
    from geocat_arc.object_reasoning.types import program_from_dict
    from geocat_arc.perception.grid import Grid
    prog = program_from_dict(d)

    def run(grid):
        LAST_ERROR["message"] = None
        try:
            out = render_program(prog, Grid(np.asarray(grid, dtype=np.int32)))
        except EvalError as e:
            LAST_ERROR["message"] = str(e)[:200]
            return None
        except ExecTimeout:
            raise
        except Exception as e:                         # noqa: BLE001 (native runtime failure: no output)
            LAST_ERROR["message"] = f"{type(e).__name__}: {str(e)[:160]}"
            return None
        return np.asarray(out.to_numpy(), dtype=np.int64)
    return run


def runner(program):
    """A function grid -> output grid (numpy) or None, compiled once."""
    if foreign(program):
        def run(grid):
            LAST_ERROR["message"] = None
            out = program.run(grid)
            if out is None:
                LAST_ERROR["message"] = getattr(program, "last_error", None)
            return None if out is None else np.asarray(out)
        return run
    if isinstance(program, PG.G4Program):
        def run(grid):
            LAST_ERROR["message"] = None
            return PG.execute(program, grid)
        return run
    d = G.compile_program(program)
    try:
        return _native_runner(d)
    except Exception:                                  # noqa: BLE001 (fall back to the bridge's own path)
        def run(grid):
            LAST_ERROR["message"] = None
            return G.run(d, grid)
        return run


def _safe(run, grid, errors=None):
    STATS["grid_runs"] += 1
    try:
        out = run(grid)
    except ExecTimeout:
        raise
    except Exception as e:                             # noqa: BLE001 (a native runtime failure: no output)
        LAST_ERROR["message"] = f"{type(e).__name__}: {str(e)[:160]}"
        out = None
    if errors is not None:
        errors.append(LAST_ERROR["message"] if out is None else None)
    return None if out is None else np.asarray(out)


def _valid_shape(p):
    return p is not None and p.ndim == 2 and 1 <= p.shape[0] <= 30 and 1 <= p.shape[1] <= 30


def run(program, task, guard_s=5.0):
    """EX.Execution for `program` on task {"train": [(in, out)], "test_inputs": [grid]}. Adds `outs` (one output
    grid per demonstration, or None) and per-demonstration `changed`, `precision` and `recall`."""
    ok, why = (True, "ok") if foreign(program) else EX.check(program)
    if not ok:
        return EX.Execution("INVALID", why)
    train = task["train"]
    t0 = time.time()
    STATS["programs"] += 1
    preds = None
    try:
        with time_guard(guard_s):
            fn = runner(program)
            demo_err, test_err = [], []
            outs = []
            for a, _ in train:
                outs.append(_safe(fn, a, demo_err))
                if outs[-1] is None and foreign(program) and str(demo_err[-1] or "").startswith(("StepLimit",
                                                                                                "Timeout")):
                    # a resource limit on one grid: the remaining grids are not run (same verdict, less time)
                    for _ in train[len(outs):]:
                        outs.append(None)
                        demo_err.append("not run after a resource limit")
                    break
            if all(o is not None and o.shape == np.asarray(b).shape and np.array_equal(o, np.asarray(b))
                   for o, (_, b) in zip(outs, train)):
                preds = [_safe(fn, t, test_err) for t in task["test_inputs"]]
    except ExecTimeout:
        STATS["timeouts"] += 1
        return EX.Execution("ERROR", f"execution exceeded {guard_s} s")
    except (ASTError, AttributeError, TypeError, ValueError, KeyError, IndexError) as e:
        return EX.Execution("INVALID", f"compile: {str(e)[:200]}")
    finally:
        STATS["exec_s"] += time.time() - t0
    ds, per = [], []
    for (a, b), o, err in zip(train, outs, demo_err):
        A, B = np.asarray(a), np.asarray(b)
        if o is None or o.shape != B.shape:
            ds.append(D.DemoDelta(False, B.shape, None if o is None else o.shape))
            per.append({"shape_ok": False, "expected_shape": list(B.shape),
                        "got_shape": None if o is None else list(o.shape), "wrong": None, "fixed": None,
                        "broken": None, "remaining": None, "changed": None, "precision": None, "recall": None,
                        "error": err})
            continue
        wrong = o != B
        row = {"shape_ok": True, "wrong": int(wrong.sum()), "cells": int(wrong.size)}
        if A.shape == B.shape:
            diff = A != B
            fixed, broken, remaining = diff & ~wrong, ~diff & wrong, diff & wrong
            ds.append(D.DemoDelta(True, B.shape, o.shape, wrong, fixed, broken, remaining))
            changed = int((o != A).sum())
            row.update(fixed=int(fixed.sum()), broken=int(broken.sum()), remaining=int(remaining.sum()),
                       changed=changed, precision=(int(fixed.sum()) / changed) if changed else None,
                       recall=(int(fixed.sum()) / int(diff.sum())) if int(diff.sum()) else None)
        else:
            ds.append(D.DemoDelta(True, B.shape, o.shape, wrong))
            row.update(fixed=None, broken=None, remaining=None, changed=None, precision=None, recall=None)
        per.append(row)
    if not all(d.shape_ok for d in ds):
        ex = EX.Execution("ERROR", "no output or wrong output shape", per_demo=per, deltas=ds)
        ex.outs = outs
        return ex
    tot = {k: sum((p[k] or 0) for p in per) for k in ("wrong", "fixed", "broken", "remaining")}
    if tot["wrong"]:
        ex = EX.Execution("INCOMPLETE", "", per_demo=per, deltas=ds, **tot)
        ex.outs = outs
        return ex
    if preds is None or any(p is None for p in preds):
        bad = [(i, e) for i, e in enumerate(test_err) if e is not None or preds[i] is None]
        why = "; ".join(f"test input {i + 1}: {e or 'no output'}" for i, e in bad[:2])
        ex = EX.Execution("ERROR", f"no output on a test input ({why})", per_demo=per, deltas=ds, **tot)
        ex.outs = outs
        return ex
    if not all(_valid_shape(p) for p in preds):
        ex = EX.Execution("ERROR", "test output outside 1..30 cells per side", per_demo=per, deltas=ds, **tot)
        ex.outs = outs
        return ex
    ex = EX.Execution("FITS", "", per_demo=per, deltas=ds, preds=[np.asarray(p) for p in preds], **tot)
    ex.outs = outs
    return ex


def predict(program, grid, guard_s=5.0):
    """CORA's output for one grid (None if it fails or is not a valid 1..30 grid), for the near-miss tier."""
    try:
        with time_guard(guard_s):
            p = _safe(runner(program), grid)
    except Exception:                                  # noqa: BLE001
        return None
    return p if _valid_shape(p) else None
