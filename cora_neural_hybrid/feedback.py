"""Structured execution feedback: what an inadequate hypothesis got wrong, in domain-free terms, from the
demonstrations only. This is the input a revision policy (rule-based now, learned later) reads.

Every cell that had to change and is still wrong (a REMAINING cell) is classified against the input's objects (one
view): ADDED (the cell was background: something must be drawn), PART (the cell is in an object whose cells did not
all change: part of an object changes), WHOLE (the cell is in an object whose cells all changed). Shares of these
three, plus broken cells, rival fits and the budget left, form the feature vector `vector(fb)`.
"""
from dataclasses import dataclass

import numpy as np

from cora_neural_v2g3 import scene as SC

FEATURES = ("fits", "demos_failing", "wrong", "fixed", "broken", "remaining", "share_added", "share_part",
            "share_whole", "n_fits", "n_behaviours", "budget_left")


@dataclass
class Feedback:
    status: str
    demos_failing: int = 0
    wrong: int = 0
    fixed: int = 0
    broken: int = 0
    remaining: int = 0
    share_added: float = 0.0
    share_part: float = 0.0
    share_whole: float = 0.0
    n_fits: int = 0
    n_behaviours: int = 0
    budget_left: int = 0


def locality(ex, task, view="S1"):
    """(added, part, whole) counts of the remaining cells over every demonstration."""
    added = part = whole = 0
    for d, (a, _) in zip(ex.deltas or [], task["train"]):
        if not d.shape_ok or d.remaining is None:
            continue
        A = np.asarray(a)
        objs, bg = SC.native_objects(a, view)
        owner = {}
        for j, o in enumerate(objs):
            for x in o.cells:
                owner[tuple(x)] = j
        changed = d.fixed | d.remaining                       # cells that had to change
        all_changed = {j: all(changed[tuple(x)] for x in o.cells) for j, o in enumerate(objs)}
        for x in zip(*np.nonzero(d.remaining)):
            x = (int(x[0]), int(x[1]))
            if A[x] == bg or x not in owner:
                added += 1
            elif all_changed[owner[x]]:
                whole += 1
            else:
                part += 1
    return added, part, whole


def from_execution(ex, task, vs=None, budget_left=0, view="S1"):
    fb = Feedback(ex.status, sum(1 for p in ex.per_demo if p["wrong"]), ex.wrong, ex.fixed, ex.broken, ex.remaining,
                  budget_left=budget_left)
    if ex.status == "INCOMPLETE":
        a, p, w = locality(ex, task, view)
        n = max(1, a + p + w)
        fb.share_added, fb.share_part, fb.share_whole = a / n, p / n, w / n
    if vs is not None:
        fb.n_fits, fb.n_behaviours = len(vs.members), len(vs.groups())
    return fb


def vector(fb):
    return np.array([1.0 if fb.status == "FITS" else 0.0] + [float(getattr(fb, k)) for k in FEATURES[1:]])
