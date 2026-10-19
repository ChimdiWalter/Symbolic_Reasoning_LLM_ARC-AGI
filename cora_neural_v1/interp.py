"""The fixed interpreter and the demonstration evidence (Neural-CORA v1).

Execution goes through native CORA's `render_program`, unchanged: the program dict from `ir.compile_native` is
deserialized with native `program_from_dict`, the native path for a program read from JSON. Nothing here is learned or
tuned, and nothing reads a test output.

Purity: `run` copies its input and keeps no state except a cache of deserialized programs keyed by the hypothesis's
semantic key. So a rejected candidate leaves no trace: exact restoration is trivial and tested.
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from geocat_arc.object_reasoning.actions import render_program          # noqa: E402
from geocat_arc.object_reasoning.types import program_from_dict          # noqa: E402
from geocat_arc.perception.grid import Grid                              # noqa: E402

from cora_neural_v1.ir import compile_native                             # noqa: E402

_PROGRAMS = {}
STATS = {"executions": 0, "eval_errors": 0, "other_errors": 0}


def native_program(h):
    k = h.key()
    p = _PROGRAMS.get(k)
    if p is None:
        p = program_from_dict(compile_native(h))
        _PROGRAMS[k] = p
    return p


def run(h, grid):
    """The output grid (np.ndarray) of hypothesis `h` on `grid`, or None if native rejects or fails."""
    STATS["executions"] += 1
    try:
        out = render_program(native_program(h), Grid(np.array(grid, dtype=np.int32)))
    except Exception as e:                              # native EvalError and anything else count as no output
        STATS["eval_errors" if type(e).__name__ == "EvalError" else "other_errors"] += 1
        return None
    return np.asarray(out.to_numpy(), dtype=np.int64)


def fit(h, pairs, stop_at_first_miss=True):
    """Demonstration evidence: (fits_all, per-demo wrong-cell counts; None = no output or a size change)."""
    wrong = []
    for a, b in pairs:
        out = run(h, a)
        B = np.asarray(b)
        if out is None or out.shape != B.shape:
            wrong.append(None)
        else:
            wrong.append(int((out != B).sum()))
        if stop_at_first_miss and wrong[-1] != 0:
            break
    return (len(wrong) == len(pairs) and all(w == 0 for w in wrong)), wrong
