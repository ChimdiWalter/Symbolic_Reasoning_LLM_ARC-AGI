"""ncv2-g3 execution deltas: run a hypothesis on every demonstration and measure what it fixed and broke.

Relative to the identity baseline (output = input), each demonstration's cells split into those that must change
(`diff`) and those that must not. A hypothesis executed on the demonstration input then has:
- fixed:     cells that had to change and now match the output;
- broken:    cells that had to stay and now differ;
- remaining: cells that had to change and still differ.
A demonstration whose output shape differs from the program's (or from the input, for the baseline) has no delta
(`shape_ok` False); such a hypothesis cannot fit.

`mismatch` turns the wrong cells into a diagnosis that the joint search (ordering) and the revision controller read:
missing / extra / wrong-colour cells, expected and produced colours, the input objects the errors touch, the bounding
box of the errors, and any shape mismatch. Everything here reads demonstrations only.
"""
from dataclasses import dataclass

import numpy as np

from cora_neural_v2.rast import ASTError
from cora_neural_v2g2 import grammar as G


@dataclass
class DemoDelta:
    shape_ok: bool
    expected_shape: tuple
    got_shape: tuple = None
    wrong: np.ndarray = None          # bool mask over the output (shape_ok only)
    fixed: np.ndarray = None
    broken: np.ndarray = None
    remaining: np.ndarray = None

    @property
    def n_wrong(self):
        return None if not self.shape_ok else int(self.wrong.sum())


def execute(prog, grid):
    try:
        return G.execute(prog, grid)
    except ASTError:
        raise
    except Exception:                                   # noqa: BLE001 (a native runtime failure: no output)
        return None


def deltas(prog, train, stop_early=False):
    """[DemoDelta] over every demonstration, or up to the first failed one with `stop_early` (the cheap fit check).
    Raises ASTError for an ill-typed program."""
    d = G.compile_program(prog)
    out = []
    for a, b in train:
        A, B = np.asarray(a), np.asarray(b)
        try:
            res = G.run(d, a)
        except Exception:                               # noqa: BLE001
            res = None
        if res is None or res.shape != B.shape:
            out.append(DemoDelta(False, B.shape, None if res is None else res.shape))
        else:
            wrong = res != B
            if A.shape == B.shape:
                diff = A != B
                out.append(DemoDelta(True, B.shape, res.shape, wrong, diff & ~wrong, ~diff & wrong, diff & wrong))
            else:
                out.append(DemoDelta(True, B.shape, res.shape, wrong))
        if stop_early and out[-1].n_wrong != 0:
            break
    return out


def fits(ds, n_demos=None):
    return (n_demos is None or len(ds) == n_demos) and all(d.shape_ok and d.n_wrong == 0 for d in ds)


def totals(ds):
    """(fixed, broken, remaining) cell counts pooled over demonstrations; None if any delta is undefined."""
    if not all(d.shape_ok and d.fixed is not None for d in ds):
        return None
    return (sum(int(d.fixed.sum()) for d in ds), sum(int(d.broken.sum()) for d in ds),
            sum(int(d.remaining.sum()) for d in ds))


def mismatch(prog, train, scene=None):
    """A per-demonstration diagnosis of where and how `prog` fails the demonstrations."""
    report = []
    for i, ((a, b), d) in enumerate(zip(train, deltas(prog, train))):
        A, B = np.asarray(a), np.asarray(b)
        if not d.shape_ok:
            report.append({"demo": i, "shape_ok": False, "expected_shape": tuple(d.expected_shape),
                           "got_shape": None if d.got_shape is None else tuple(d.got_shape)})
            continue
        res = execute(prog, a)
        bg = scene.background[i] if scene is not None else 0
        w = d.wrong
        rows, cols = np.nonzero(w)
        entry = {"demo": i, "shape_ok": True, "n_wrong": int(w.sum()),
                 "missing": int((w & (B != bg) & (res == bg)).sum()),
                 "extra": int((w & (B == bg) & (res != bg)).sum()),
                 "wrong_colour": int((w & (B != bg) & (res != bg)).sum()),
                 "expected_colours": {int(c): int(n) for c, n in zip(*np.unique(B[w], return_counts=True))},
                 "got_colours": {int(c): int(n) for c, n in zip(*np.unique(res[w], return_counts=True))},
                 "bbox": None if not len(rows) else (int(rows.min()), int(cols.min()), int(rows.max()), int(cols.max()))}
        if d.fixed is not None:
            entry.update(fixed=int(d.fixed.sum()), broken=int(d.broken.sum()), remaining=int(d.remaining.sum()))
        if scene is not None and A.shape == B.shape:
            entry["objects"] = [{"index": o.index, "fate": o.fate, "wrong_cells": sum(bool(w[x]) for x in o.cells)}
                                for o in scene.objects[i] if any(w[x] for x in o.cells)]
        report.append(entry)
    return report
