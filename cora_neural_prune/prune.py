"""Failure-derived pruning: a failed candidate rules out other candidates without executing them.

This adapts the central idea of Popper (Cropper and Morel, "Learning programs by learning from failures", 2021) to
CORA's typed object programs. Popper turns a hypothesis that is too general into a constraint against its
generalizations, and one that is too specific into a constraint against its specializations. Here the evidence is
the cell masks of an executed candidate (cora_neural_v2g3.delta): cells it got wrong on a demonstration.
Level: L1/L2 candidate with PRIOR_ART_OVERLAP (Popper); a measured gain is not established by this module.

**The family it prunes.** Single-rule object programs

    (program VIEW (list (rule SEL ACT)) keep (same_as_input))

with a LOCAL action ACT in {(delete), (recolor (color c))}. Every other candidate passes through untouched.

**Locality (the property everything rests on).** Let O_i be the objects of VIEW on demonstration input A_i (their
cell sets must be pairwise disjoint; a view where they are not is ineligible). Let M_i(SEL) be the set of objects
SEL picks on A_i. It is computed by native execution of SEL alone (scene.selections), so it does not depend on ACT.
Under native semantics (one rule, first match, unmatched objects kept; geocat_arc.object_reasoning.actions.render
paints every output object over a frame of the view's background colour bg_i, the colour the view segments with),
and since every segmenter puts each non-background cell in an object and no background cell in any, the output is:
for x in cells(o) with o in M_i(SEL), a value fixed by ACT and A_i alone (bg_i for delete, c for recolor); for every
other cell, A_i[x]. So the output on cells(o) depends only on (ACT, whether o is picked, A_i).

**Constraints learned from a failed candidate (VIEW, SEL, ACT) on demonstration i with wrong-cell mask W:**
- forbid (too general): o picked and W hits cells(o). By locality, every candidate (VIEW, SEL', ACT) that picks o
  writes the same wrong values there, so it cannot fit.
- require (too specific): o not picked and W hits cells(o). Unpicked cells keep A_i, so B_i != A_i on cells(o), and
  every candidate of the family (any local ACT') that does not pick o is wrong there, so it cannot fit.
- unchanged: o picked, W hits cells(o), and B_i == A_i on cells(o). Every candidate whose action changes o (delete
  always, since no cell of o has colour bg_i; recolor c when some cell of o is not c) and picks o is wrong there, so
  it cannot fit.
- dead view: W hits a cell outside every object. No local action writes such a cell, so every candidate of the
  family in VIEW outputs A_i there and is wrong; none can fit.

**Theorem.** A candidate that `check` prunes does not fit every demonstration. Proof: each pruning reason is one of
the four cases above, each of which exhibits a demonstration cell that the candidate gets wrong. The argument needs
(i) exact pick sets (native, cached per (VIEW, SEL)); (ii) disjoint objects (checked); (iii) single rule, `keep`,
`same_as_input`, and a local action (checked by `family_key`). The tests execute every pruned candidate and check
that none fits.

**Cost.** Pruning a candidate skips its execution, but computing a pick set costs one native run per demonstration,
once per (VIEW, SEL). These runs are counted in `native_runs` and reported separately from candidate evaluations.
"""
from collections import Counter, defaultdict

import numpy as np

from cora_neural_v2.rast import N
from cora_neural_v2g3 import scene as SC


def family_key(prog):
    """(view, selector, action key) for a candidate of the pruned family, else None."""
    if not (isinstance(prog, N) and prog.op == "program") or len(prog.args) != 4:
        return None
    view, rules, default, render = prog.args
    if len(rules) != 1 or default != "keep" or not (isinstance(render, N) and render.op == "same_as_input"):
        return None
    rule = rules[0]
    if not (isinstance(rule, N) and rule.op == "rule" and len(rule.args) == 2):
        return None
    sel, act = rule.args
    if not isinstance(act, N):
        return None
    if act.op == "delete" and not act.args:
        return view, sel, ("delete",)
    if act.op == "recolor" and len(act.args) == 1 and isinstance(act.args[0], N) and act.args[0].op == "color":
        return view, sel, ("recolor", int(act.args[0].args[0]))
    return None


class Constraints:
    """Constraints learned from failed candidates of one task (demonstrations only)."""

    def __init__(self, train):
        self.train = train
        self.A = [np.asarray(a) for a, _ in train]
        self.B = [np.asarray(b) for _, b in train]
        self._objs, self._picks = {}, {}
        self.forbid = defaultdict(set)      # (view, act) -> {(demo, object)}
        self.require = defaultdict(set)     # view -> {(demo, object)}
        self.unchanged = defaultdict(set)   # view -> {(demo, object)}
        self.dead = set()                   # views
        self.native_runs = 0
        self.learned = Counter()

    def objects(self, view):
        """Per demonstration: [(row index array, column index array)] per object, or None if the view is ineligible."""
        if view not in self._objs:
            out = []
            for A, B, (a, _) in zip(self.A, self.B, self.train):
                if A.shape != B.shape:
                    out = None
                    break
                objs, _ = SC.native_objects(a, view)
                seen = np.zeros(A.shape, dtype=int)
                cells = []
                for o in objs:
                    rc = np.array(sorted(o.cells), dtype=int).reshape(-1, 2)
                    idx = (rc[:, 0], rc[:, 1])
                    seen[idx] += 1
                    cells.append(idx)
                if (seen > 1).any():                                       # overlapping objects: not local
                    out = None
                    break
                out.append(cells)
            self._objs[view] = out
        return self._objs[view]

    def picks(self, view, sel):
        k = (view, sel)
        if k not in self._picks:
            self.native_runs += len(self.train)
            self._picks[k] = SC.selections(view, [sel], self.train)[sel]
        return self._picks[k]

    def _changes(self, i, idx, act):
        return True if act[0] == "delete" else bool((self.A[i][idx] != act[1]).any())

    def check(self, key):
        """A pruning reason for this candidate, or None to execute it."""
        view, sel, act = key
        objs = self.objects(view)
        if objs is None:
            return None
        if view in self.dead:
            return "dead_view"
        if not (self.require[view] or self.forbid[(view, act)] or self.unchanged[view]):
            return None
        S = self.picks(view, sel)
        if any(s is None for s in S):
            return None
        picked = {(i, j) for i, s in enumerate(S) for j in s}
        if not self.require[view] <= picked:
            return "too_specific"
        if picked & self.forbid[(view, act)]:
            return "too_general"
        for i, j in picked & self.unchanged[view]:
            if self._changes(i, objs[i][j], act):
                return "changes_an_unchanged_object"
        return None

    def learn(self, key, deltas):
        """Record what a failed candidate of the family shows (its per-demonstration wrong masks)."""
        view, sel, act = key
        objs = self.objects(view)
        if objs is None:
            return
        S = self.picks(view, sel)
        for i, d in enumerate(deltas):
            if not d.shape_ok or d.wrong is None or not d.wrong.any() or S[i] is None:
                continue
            W = d.wrong
            covered = np.zeros(W.shape, dtype=bool)
            for j, idx in enumerate(objs[i]):
                covered[idx] = True
                if not W[idx].any():
                    continue
                if j in S[i]:
                    self.forbid[(view, act)].add((i, j))
                    self.learned["forbid"] += 1
                    if (self.A[i][idx] == self.B[i][idx]).all():
                        self.unchanged[view].add((i, j))
                        self.learned["unchanged"] += 1
                else:
                    self.require[view].add((i, j))
                    self.learned["require"] += 1
            if (W & ~covered).any():
                self.dead.add(view)
                self.learned["dead_view"] += 1
