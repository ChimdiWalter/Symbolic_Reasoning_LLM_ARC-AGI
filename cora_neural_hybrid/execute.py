"""Compile and execute a hypothesis with CORA's own machinery, and classify the outcome. Demonstrations and test
inputs only; expected test outputs never enter this module.

Status: INVALID (does not typecheck or compile), ERROR (no output or a shape mismatch on some demonstration), FITS
(every demonstration reproduced exactly), INCOMPLETE (runs everywhere, some cells wrong). FITS means
demonstration-consistent, not correct on the hidden test output.
"""
from dataclasses import dataclass, field

import numpy as np

from cora_neural_v2.rast import ASTError, N, holes
from cora_neural_v2g2 import grammar as G
from cora_neural_v2g3 import delta as D
from cora_neural_v2g4 import program as PG
from cora_neural_v2g4 import search as S4


@dataclass
class Execution:
    status: str
    reason: str = ""
    wrong: int = 0                   # wrong output cells, summed over demonstrations
    fixed: int = 0                   # cells that had to change and now are right
    broken: int = 0                  # cells that had to stay and now are wrong
    remaining: int = 0               # cells that had to change and are still wrong
    per_demo: list = field(default_factory=list)
    deltas: list = None              # delta.DemoDelta per demonstration (masks), for feedback
    preds: list = None               # one predicted grid per test input, in order (FITS only)


def check(program):
    """(True, "ok") if the program is well typed and complete; else (False, reason)."""
    try:
        if isinstance(program, PG.G4Program):
            if program.base is not None:
                G.typecheck(program.base)
            for r in program.rules:
                probe = N("program", (program.view, (N("rule", (r.sel, N("delete", ()))),), "keep",
                                       N("same_as_input", ())))
                G.typecheck(probe)
            return True, "ok"
        if not isinstance(program, N):
            return False, "not a program"
        if holes(program):
            return False, "has holes (a sketch)"
        G.typecheck(program)
        return True, "ok"
    except (ASTError, AttributeError, TypeError, ValueError) as e:
        return False, f"ill_typed: {e}"


def run(program, task):
    ok, why = check(program)
    if not ok:
        return Execution("INVALID", why)
    train = task["train"]
    try:
        ds = PG.deltas(program, train) if isinstance(program, PG.G4Program) else D.deltas(program, train)
    except (ASTError, AttributeError, TypeError, ValueError) as e:
        return Execution("INVALID", f"compile: {e}")
    if len(ds) < len(train) or not all(d.shape_ok for d in ds):
        return Execution("ERROR", "no output or wrong shape", deltas=ds)
    per = [{"wrong": int(d.wrong.sum()), "fixed": int(d.fixed.sum()), "broken": int(d.broken.sum()),
            "remaining": int(d.remaining.sum())} for d in ds]
    tot = {k: sum(p[k] for p in per) for k in per[0]}
    if tot["wrong"]:
        return Execution("INCOMPLETE", "", per_demo=per, deltas=ds, **tot)
    preds = [S4._execute(program, t) for t in task["test_inputs"]]
    if any(p is None for p in preds):
        return Execution("ERROR", "no output on a test input", per_demo=per, deltas=ds, **tot)
    return Execution("FITS", "", per_demo=per, deltas=ds, preds=[np.asarray(p) for p in preds], **tot)
