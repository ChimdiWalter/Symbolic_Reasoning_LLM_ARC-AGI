"""Bounded enumerative search over operator sequences with sound contract pruning (M3).

A program is a sequence of operator instances (op, theta) applied left to right to the input grid. A partial program
(prefix) is executed concretely on every demonstration input; its remaining completions are the sequences of at
most r further instances from the same grammar instance (stopping early is allowed).

Modes (the directive's mandatory controls; identical enumeration order and grammar):
    exact     no pruning: execute everything (exact execution only)
    typed     prune with the dimension domain only (ordinary typed constraints)
    fwd       sound forward analysis: hole(alpha(z), r) must contain the demonstrated output
    fwdbwd    fwd plus a backward predecessor check: meet(hole(alpha(z), r - 1), pre(y)) must be non-empty, where
              pre(y) is the join over the grammar of every operator's predecessor relation (and y itself)
A prune is recorded with its scope (prefix, remaining depth, grammar hash, demonstration index, domain, evidence
class). A prune is never generalized beyond that scope. Search outcome statuses are kept distinct:
    FIT                      at least one program reproduces every demonstration
    NO_FIT_EXHAUSTED         every program of the bounded grammar was decided (executed or soundly pruned) and none
                             fits: "bounded-unrealizable in this grammar instance", NOT a proof that the task is
                             unexpressible
    BUDGET_EXHAUSTED         the execution or CPU budget ran out first (unknown)
Observational equivalence (optional): prefixes whose outputs on every demonstration AND query input equal an earlier
prefix's (at the same or larger remaining depth) are skipped; two programs that fit but disagree on a query are never
merged.
"""
import hashlib
import time

import numpy as np

from . import absdom as D
from .ops import Identity

MODES = ("exact", "typed", "fwd", "fwdbwd")


def shapes_only(a):
    if a.bottom:
        return a
    return D.Abs(a.shapes, a.shape_lo, None, D.ALL)


class Budget:
    def __init__(self, max_exec=None, max_cpu_s=None):
        self.max_exec, self.max_cpu_s = max_exec, max_cpu_s
        self.t0 = time.process_time()
        self.execs = 0
        self.transfers = 0

    def out(self):
        if self.max_exec is not None and self.execs >= self.max_exec:
            return True
        if self.max_cpu_s is not None and time.process_time() - self.t0 >= self.max_cpu_s:
            return True
        return False

    @property
    def cpu_s(self):
        return time.process_time() - self.t0


def grammar_hash(instances):
    h = hashlib.sha256()
    for op, th in instances:
        h.update(f"{op.name}{th};".encode())
    return h.hexdigest()[:12]


class Searcher:
    def __init__(self, ctx, lib, depth=2, mode="fwdbwd", max_exec=None, max_cpu_s=None, oe=True,
                 keep_prunes=200, max_fits=64):
        assert mode in MODES
        self.ctx, self.lib, self.depth, self.mode, self.oe = ctx, lib, depth, mode, oe
        self.instances = [(op, th) for op in lib for th in op.domain(ctx)]
        self.ghash = grammar_hash(self.instances)
        self.budget = Budget(max_exec, max_cpu_s)
        self.fits, self.prunes, self.keep_prunes, self.max_fits = [], [], keep_prunes, max_fits
        self.n_pruned = {"subtree": 0, "subtree_bwd": 0, "leaf": 0}
        self.seen = {}
        self.ys = [y for _, y in ctx.train]
        self.queries = list(ctx.test_inputs)
        self._pre = None
        self._hcache = {}
        self.complete = True

    # ---------------------------------------------------------------- abstract helpers
    def _proj(self, a):
        return shapes_only(a) if self.mode == "typed" else a

    def hole(self, a, r):
        """Over-approximation of every completion of length <= r from abstract a (stop included)."""
        cur = self._proj(a)
        for _ in range(r):
            nxt = cur
            for op, th in self.instances:
                self.budget.transfers += 1
                nxt = D.join(nxt, self._proj(op.fwd(cur, th)))
            if _same(nxt, cur):
                break
            cur = nxt
        return cur

    def hole_summary(self, z, r):
        """Sound, cached over-approximation for subtree checks: the hole transfer started from the shape-and-palette
        abstraction of z (gamma contains alpha(z), so every completion's output is covered). Cached per
        (shape, palette, r); per-cell precision is kept for the leaf (instance) checks."""
        pal = int(D.BITW[np.bincount(z.ravel(), minlength=10)[:10] > 0].sum())
        key = (z.shape, pal, r, self.mode)
        hit = self._hcache.get(key)
        if hit is None:
            hit = self.hole(D.Abs({z.shape}, (1, 1), None, pal), r)
            self._hcache[key] = hit
        return hit

    def pre(self, i):
        """Join of the predecessor relations of every grammar instance for demonstration output i, plus y_i."""
        if self._pre is None:
            self._pre = []
            for y in self.ys:
                acc = D.alpha(y)
                for op, th in self.instances:
                    self.budget.transfers += 1
                    acc = D.join(acc, op.bwd(y, th))
                self._pre.append(acc)
        return self._pre[i]

    def _record(self, kind, prefix, r, i, why):
        self.n_pruned[kind] += 1
        if len(self.prunes) < self.keep_prunes:
            self.prunes.append({"kind": kind, "prefix": [f"{op.name}{th}" for op, th in prefix], "remaining": r,
                                "demo": i, "grammar": self.ghash, "domain": why,
                                "evidence": "PROVED_OPERATOR_CONTRACT"})

    def subtree_dead(self, prefix, zs, r):
        if self.mode == "exact" or r == 0:
            return False
        for i, (z, y) in enumerate(zip(zs, self.ys)):
            if not D.contains(self.hole_summary(z, r), y):
                self._record("subtree", prefix, r, i, "typed:dims" if self.mode == "typed" else "fwd")
                return True
        if self.mode == "fwdbwd":
            for i, (z, y) in enumerate(zip(zs, self.ys)):
                if np.array_equal(z, y) if z.shape == y.shape else False:
                    continue
                if D.meet(self.hole_summary(z, r - 1), self.pre(i)).bottom:
                    self._record("subtree_bwd", prefix, r, i, "fwd-meet-bwd")
                    return True
        return False

    def leaf_dead(self, prefix, zs, op, th):
        """Instance-level check before executing the last operator of a program (remaining depth 1)."""
        if self.mode == "exact":
            return False
        for i, (z, y) in enumerate(zip(zs, self.ys)):
            self.budget.transfers += 1
            if not D.contains(self._proj(op.fwd(D.alpha(z), th)), y):
                self._record("leaf", prefix + [(op, th)], 0, i, "instance contract")
                return True
        return False

    # ---------------------------------------------------------------- search
    def run(self):
        zs = [x for x, _ in self.ctx.train]
        self._visit([], zs, list(self.queries), self.depth)
        status = "FIT" if self.fits else ("NO_FIT_EXHAUSTED" if self.complete else "BUDGET_EXHAUSTED")
        return {"status": status, "fits": self.fits, "execs": self.budget.execs, "transfers": self.budget.transfers,
                "cpu_s": round(self.budget.cpu_s, 4), "pruned": dict(self.n_pruned), "mode": self.mode,
                "depth": self.depth, "grammar": self.ghash, "n_instances": len(self.instances)}

    def _visit(self, prefix, zs, qs, r):
        if self.budget.out():
            self.complete = False
            return
        if prefix and all(z.shape == y.shape and np.array_equal(z, y) for z, y in zip(zs, self.ys)):
            if len(self.fits) < self.max_fits:
                self.fits.append({"program": [(op.name, th) for op, th in prefix],
                                  "preds": [None if q is None else q.tolist() for q in qs]})
        if r == 0:
            return
        if prefix and self.subtree_dead(prefix, zs, r):
            return
        for op, th in self.instances:
            if self.budget.out():
                self.complete = False
                return
            if r == 1 and self.leaf_dead(prefix, zs, op, th):
                continue
            nz = []
            ok = True
            for z in zs:
                self.budget.execs += 1
                o = op.apply(z, th)
                if o is None:
                    ok = False
                    break
                nz.append(np.asarray(o, dtype=np.int64))
            if not ok:
                continue
            nq = []
            for q in qs:
                if q is None:
                    nq.append(None)
                    continue
                self.budget.execs += 1
                o = op.apply(q, th)
                nq.append(None if o is None else np.asarray(o, dtype=np.int64))
            if self.oe:
                key = tuple(z.shape + (z.tobytes(),) for z in nz) + tuple(
                    (None if q is None else q.shape + (q.tobytes(),)) for q in nq)
                if self.seen.get(key, -1) >= r - 1:
                    continue
                self.seen[key] = r - 1
            self._visit(prefix + [(op, th)], nz, nq, r - 1)


def _same(a, b):
    if a.bottom != b.bottom:
        return False
    if a.bottom:
        return True
    if a.shapes != b.shapes or a.shape_lo != b.shape_lo or a.pal != b.pal or a.need != b.need:
        return False
    if (a.cells is None) != (b.cells is None):
        return False
    if a.cells is not None and not np.array_equal(a.cells, b.cells):
        return False
    return bool(np.array_equal(a.lo, b.lo) and np.array_equal(a.hi, b.hi))


def stop_instance():
    return Identity(), ()
