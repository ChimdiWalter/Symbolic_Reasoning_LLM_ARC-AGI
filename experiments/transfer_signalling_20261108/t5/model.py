"""Logic models over a hyperedge space, simulated bit-parallel over observation columns (one bit per condition).

A model is a Python int over the space's hyperedges (bit i set: hyperedge i active). A node's value is the OR of its
active hyperedges, each the AND of its signed inputs; stimuli are OR-ed with the applied stimulus and inhibited nodes
are forced to 0 (CellNOpt's steady-state semantics, simulatorT1). Acyclic spaces are evaluated in one topological pass;
cyclic spaces by synchronous iteration from the cue state for at most ceil(1.2 * nodes) steps, and bits still changing
are NA (CellNOpt's oscillation rule). Evaluation of node expressions reuses the bit-column evaluator of the Boolean
network core (experiments/universality_boolean_bbm_20261103/u6/bn.py: evaluate), which the checker also uses.
"""
import math
import os
import sys

_CORE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                     "universality_boolean_bbm_20261103")
if _CORE not in sys.path:
    sys.path.insert(0, _CORE)
from u6.bn import evaluate as core_evaluate  # noqa: E402


class Space:
    """Nodes, hyperedges and the observation design for one task. Hyperedges: list of (target, ((src, sign), ...))."""

    def __init__(self, nodes, hyper, stimuli, inhibitors, readouts):
        self.nodes = sorted(nodes)
        self.ix = {n: i for i, n in enumerate(self.nodes)}
        self.N = len(self.nodes)
        self.hyper = list(hyper)
        self.H = len(self.hyper)
        self.tgt = [self.ix[t] for t, _ in self.hyper]
        self.lits = [tuple((self.ix[u], s < 0) for u, s in lits) for _, lits in self.hyper]
        self.nin = [len(l) for l in self.lits]
        self.stimuli = [s for s in stimuli if s in self.ix]
        self.inhibitors = [s for s in inhibitors if s in self.ix]
        self.readouts = list(readouts)
        self.by_tgt = [[] for _ in range(self.N)]
        for h, t in enumerate(self.tgt):
            self.by_tgt[t].append(h)
        self.topo = self._topo()

    def _topo(self):
        succ = [set() for _ in range(self.N)]
        indeg = [0] * self.N
        for h in range(self.H):
            for u, _ in self.lits[h]:
                if self.tgt[h] not in succ[u]:
                    succ[u].add(self.tgt[h])
                    indeg[self.tgt[h]] += 1
        order = []
        ready = sorted(i for i in range(self.N) if indeg[i] == 0)
        while ready:
            u = ready.pop(0)
            order.append(u)
            for v in sorted(succ[u]):
                indeg[v] -= 1
                if indeg[v] == 0:
                    ready.append(v)
        return order if len(order) == self.N else None

    def descendants(self, node):
        """Nodes reachable from node over all hyperedges of the space (node included)."""
        succ = [set() for _ in range(self.N)]
        for h in range(self.H):
            for u, _ in self.lits[h]:
                succ[u].add(self.tgt[h])
        seen, stack = {node}, [node]
        while stack:
            u = stack.pop()
            for v in succ[u]:
                if v not in seen:
                    seen.add(v)
                    stack.append(v)
        return seen

    def size(self, model):
        s, h = 0, 0
        while model:
            if model & 1:
                s += self.nin[h]
            model >>= 1
            h += 1
        return s

    def active(self, model):
        return [h for h in range(self.H) if (model >> h) & 1]

    def describe(self, model):
        out = []
        for h in self.active(model):
            t, lits = self.hyper[h]
            out.append("+".join(("!" if s < 0 else "") + u for u, s in lits) + "=" + t)
        return sorted(out)


class Design:
    """Observation columns: each has a stimulus vector and an inhibitor vector (0/1 per cue)."""

    def __init__(self, space, cols_stim, cols_inh, stim_names, inh_names):
        self.K = len(cols_stim)
        self.full = (1 << self.K) - 1
        self.stim_mask = [0] * space.N
        self.inh_mask = [0] * space.N
        for k, (sv, iv) in enumerate(zip(cols_stim, cols_inh)):
            for n, v in zip(stim_names, sv):
                if v and n in space.ix:
                    self.stim_mask[space.ix[n]] |= 1 << k
            for n, v in zip(inh_names, iv):
                if v and n in space.ix:
                    self.inh_mask[space.ix[n]] |= 1 << k


def simulate(space, design, model):
    """Steady state: (values, na) as lists of bit columns per node."""
    full = design.full
    act = [[h for h in space.by_tgt[v] if (model >> h) & 1] for v in range(space.N)]
    if space.topo is not None:
        x = [0] * space.N
        for v in space.topo:
            acc = 0
            for h in act[v]:
                t = full
                for u, neg in space.lits[h]:
                    t &= (~x[u] & full) if neg else x[u]
                    if not t:
                        break
                acc |= t
            x[v] = (acc | design.stim_mask[v]) & ~design.inh_mask[v] & full
        return x, None
    x = [(design.stim_mask[v] & ~design.inh_mask[v]) & full for v in range(space.N)]
    cap = math.ceil(1.2 * space.N)
    for _ in range(cap):
        new = [0] * space.N
        for v in range(space.N):
            acc = 0
            for h in act[v]:
                t = full
                for u, neg in space.lits[h]:
                    t &= (~x[u] & full) if neg else x[u]
                acc |= t
            new[v] = (acc | design.stim_mask[v]) & ~design.inh_mask[v] & full
        if new == x:
            return x, None
        prev, x = x, new
    return x, [a ^ b for a, b in zip(x, prev)]


def simulate_core(space, design, model):
    """Checker: the same steady state computed with the core's expression evaluator on explicit ASTs, by synchronous
    iteration from the cue state for the same ceil(1.2 * nodes) steps and the same oscillation rule as simulate (bits
    still changing after the last step are NA), so a program that does not settle is scored as a mismatch rather than
    reported as a disagreement. Used to cross-check simulate on every final model."""
    full = design.full
    names = space.nodes
    asts = {}
    for v in range(space.N):
        terms = []
        for h in space.by_tgt[v]:
            if (model >> h) & 1:
                fs = [("not", ("var", names[u])) if neg else ("var", names[u]) for u, neg in space.lits[h]]
                terms.append(fs[0] if len(fs) == 1 else ("and", fs))
        asts[v] = None if not terms else (terms[0] if len(terms) == 1 else ("or", terms))
    x = [(design.stim_mask[v] & ~design.inh_mask[v]) & full for v in range(space.N)]
    for _ in range(math.ceil(1.2 * space.N)):
        env = {names[v]: x[v] for v in range(space.N)}
        new = []
        for v in range(space.N):
            acc = 0 if asts[v] is None else core_evaluate(asts[v], env, full)
            new.append((acc | design.stim_mask[v]) & ~design.inh_mask[v] & full)
        if new == x:
            return x, None
        prev, x = x, new
    return x, [a ^ b for a, b in zip(x, prev)]


class Obs:
    """Binarised observations of the readouts over the design's columns: one (meas, ones) pair of bit masks per readout
    (meas: measured, not NaN; ones: measured value >= threshold). vals keeps the raw values for the continuous score."""

    def __init__(self, space, design, rows, threshold=0.5):
        self.ro = [space.ix[r] for r in space.readouts]
        self.meas = [0] * len(self.ro)
        self.ones = [0] * len(self.ro)
        self.vals = [[None] * design.K for _ in self.ro]
        for k, row in enumerate(rows):
            for j, v in enumerate(row):
                if v is None:
                    continue
                self.meas[j] |= 1 << k
                self.vals[j][k] = v
                if v >= threshold:
                    self.ones[j] |= 1 << k
        self.n_meas = sum(m.bit_count() for m in self.meas)

    def errors(self, x, na, colmask=-1):
        e = 0
        for j, v in enumerate(self.ro):
            bad = (x[v] ^ self.ones[j])
            if na is not None:
                bad |= na[v]
            e += (bad & self.meas[j] & colmask).bit_count()
        return e

    def residual(self, x, na):
        """Per readout: (miss_on, miss_off, keep_on, keep_off) bit masks over measured columns."""
        out = []
        for j, v in enumerate(self.ro):
            p = x[v]
            n = na[v] if na is not None else 0
            m, o = self.meas[j], self.ones[j]
            out.append(((o & ~p | o & n) & m, (~o & p | ~o & n) & m, o & p & ~n & m, ~o & ~p & ~n & m))
        return out
