"""Model search over a hyperedge space.

fit: the CORA arms' search. Objective (errors, size), compared lexicographically: errors = binarised training data
points the model gets wrong (an NA prediction is wrong); size = number of inputs over the active hyperedges.
Iterated local search: steepest single-flip descent from fixed starts (empty, full, extra starts) and seeded random
starts, then seeded perturbations (k random flips, re-descend, keep when not worse). Every local optimum is pooled; the
least-error set is every distinct pooled model with the minimum error (at most VOTE_CAP, smallest first).

vote: the least-error vote. Each least-error model predicts the held columns; a readout bit is the majority; a tie
takes the representative model's value (smallest size, then smallest bit string).

ga_cellnopt: the classical comparator. CellNOpt's objective (computeScoreT1 and getFit, re-implemented: squared
deviation over t1 and t0 data divided by 2, plus NAFac per NA prediction, plus nDataPts * sizeFac * nInputs / nInTot,
all divided by the number of measured t1 data points) under CellNOpt's binary genetic algorithm (gaBinaryT1 defaults:
popSize 50, pMutation 0.5, maxGens 500, stallGenMax 100, selPress 1.2, elitism 5; initial population all-ones plus
random strings; linear ranking with stochastic universal sampling; uniform crossover; per-bit mutation pMutation/bLength).
"""
import hashlib
import random

from .model import simulate

VOTE_CAP = 64


def rng_for(label):
    return random.Random(int.from_bytes(hashlib.sha256(label.encode()).digest()[:8], "big"))


class Fitter:
    def __init__(self, space, design, obs, colmask=-1):
        self.space, self.design, self.obs, self.colmask = space, design, obs, colmask
        self.cache = {}
        self.evals = 0

    def score(self, m):
        s = self.cache.get(m)
        if s is None:
            x, na = simulate(self.space, self.design, m)
            s = (self.obs.errors(x, na, self.colmask), self.space.size(m))
            self.cache[m] = s
            self.evals += 1
        return s

    def descend(self, m):
        cur = self.score(m)
        H = self.space.H
        while True:
            best, bsc = None, cur
            for h in range(H):
                m2 = m ^ (1 << h)
                sc = self.score(m2)
                if sc < bsc:
                    best, bsc = m2, sc
            if best is None:
                return m, cur
            m, cur = best, bsc


def fit(space, design, obs, label, restarts, perturb, kflip=3, extra_starts=(), colmask=-1):
    """Returns dict: err, least (list of (model, size) sorted), rep (representative model), evals."""
    F = Fitter(space, design, obs, colmask)
    rng = rng_for("fit|" + label)
    H = space.H
    full = (1 << H) - 1
    starts = [0, full] + list(extra_starts)
    for _ in range(restarts):
        starts.append(rng.getrandbits(H) if H else 0)
    pool = {}
    for s0 in starts:
        m, sc = F.descend(s0)
        pool[m] = sc
        for _ in range(perturb):
            m2 = m
            for _ in range(kflip):
                m2 ^= 1 << rng.randrange(H) if H else 0
            m2, sc2 = F.descend(m2)
            pool[m2] = sc2
            if sc2 <= sc:
                m, sc = m2, sc2
    emin = min(sc[0] for sc in pool.values())
    least = sorted(((m, sc[1]) for m, sc in pool.items() if sc[0] == emin), key=lambda t: (t[1], t[0]))[:VOTE_CAP]
    return {"err": emin, "least": least, "rep": least[0][0], "evals": F.evals}


def predict_model(space, design, model):
    x, na = simulate(space, design, model)
    return x, na


def vote(space, design, least):
    """Majority over the least-error models: per node bit columns (values, na) for the readouts' use."""
    full = design.full
    rep_x, rep_na = simulate(space, design, least[0][0])
    if len(least) == 1:
        return rep_x, rep_na
    ones = [[0] * design.K for _ in range(space.N)]
    zeros = [[0] * design.K for _ in range(space.N)]
    ro = sorted({space.ix[r] for r in space.readouts})
    for m, _ in least:
        x, na = simulate(space, design, m)
        for v in ro:
            for k in range(design.K):
                if na is not None and (na[v] >> k) & 1:
                    continue
                if (x[v] >> k) & 1:
                    ones[v][k] += 1
                else:
                    zeros[v][k] += 1
    out_x = list(rep_x)
    out_na = [0] * space.N if rep_na is None else list(rep_na)
    for v in ro:
        xv, nv = 0, 0
        for k in range(design.K):
            if ones[v][k] > zeros[v][k]:
                xv |= 1 << k
            elif ones[v][k] == zeros[v][k]:
                xv |= rep_x[v] & (1 << k)
                if rep_na is not None:
                    nv |= rep_na[v] & (1 << k)
        out_x[v] = xv & full
        out_na[v] = nv
    return out_x, (out_na if any(out_na) else None)


# ------------------------------------------------------------------------------------------- CellNOpt comparator
class CellNOptScore:
    """CellNOpt's objective for one training design: columns flagged t1 or t0."""

    def __init__(self, space, design, obs, is_t1, n_t1_conditions, size_fac=1e-4, na_fac=1.0):
        self.space, self.design, self.obs = space, design, obs
        self.size_fac, self.na_fac = size_fac, na_fac
        K = design.K
        self.base = 0.0
        self.tables = []
        for j in range(len(obs.ro)):
            c0, d = [0.0] * K, [0.0] * K
            for k in range(K):
                v = obs.vals[j][k]
                if v is None:
                    continue
                c0[k] = v * v
                d[k] = (1 - v) * (1 - v) - v * v
            self.base += sum(c0)
            tabs = []
            for q in range(0, K, 8):
                t = [0.0] * 256
                for b in range(256):
                    t[b] = sum(d[q + i] for i in range(8) if (b >> i) & 1 and q + i < K)
                tabs.append(t)
            self.tables.append(tabs)
        self.c0 = [[(obs.vals[j][k] or 0.0) ** 2 if obs.vals[j][k] is not None else 0.0 for k in range(K)]
                   for j in range(len(obs.ro))]
        self.d = [[((1 - obs.vals[j][k]) ** 2 - obs.vals[j][k] ** 2) if obs.vals[j][k] is not None else 0.0
                   for k in range(K)] for j in range(len(obs.ro))]
        t1mask = 0
        for k, f in enumerate(is_t1):
            if f:
                t1mask |= 1 << k
        self.n_data_pts = n_t1_conditions * len(obs.ro)
        self.n_data_p = sum((obs.meas[j] & t1mask).bit_count() for j in range(len(obs.ro)))
        self.n_in_tot = sum(space.nin)
        self.cache = {}
        self.evals = 0

    def __call__(self, m):
        s = self.cache.get(m)
        if s is not None:
            return s
        self.evals += 1
        x, na = simulate(self.space, self.design, m)
        dev = self.base
        nas = 0
        for j, v in enumerate(self.obs.ro):
            bits = x[v]
            if na is not None and na[v]:
                bits &= ~na[v]
                nb = na[v]
                nas += nb.bit_count()
                k = 0
                while nb:
                    if nb & 1 and self.obs.vals[j][k] is not None:
                        dev -= self.c0[j][k]
                    nb >>= 1
                    k += 1
            tabs = self.tables[j]
            q = 0
            while bits:
                dev += tabs[q][bits & 255]
                bits >>= 8
                q += 1
        n_inputs = self.space.size(m)
        size_pen = self.n_data_pts * self.size_fac * n_inputs / self.n_in_tot if self.n_in_tot else 0.0
        s = (dev / 2.0 + self.na_fac * nas + size_pen) / self.n_data_p
        self.cache[m] = s
        return s


def ga_cellnopt(score, H, label, pop_size=50, p_mut=0.5, max_gens=500, stall_max=100, sel_press=1.2, elitism=5):
    rng = rng_for("ga|" + label)
    full = (1 << H) - 1
    pop = [full] + [rng.getrandbits(H) for _ in range(pop_size - 1)]
    best, best_s, stall = None, float("inf"), 0
    fitness = [2 - sel_press + 2 * (sel_press - 1) * i / (pop_size - 1) for i in range(pop_size)]
    tot = sum(fitness)
    wheel, acc = [], 0.0
    for f in fitness:
        acc += f / tot
        wheel.append(acc)
    gens = 0
    for gens in range(1, max_gens + 1):
        sc = [score(m) for m in pop]
        order = sorted(range(pop_size), key=lambda i: -sc[i])          # worst first, best last (CellNOpt's ranking)
        pop = [pop[i] for i in order]
        sc = [sc[i] for i in order]
        if sc[-1] < best_s - 1e-12:
            best, best_s, stall = pop[-1], sc[-1], 0
        else:
            stall += 1
        if stall >= stall_max:
            break
        start = rng.random() / pop_size
        sel = []
        for i in range(pop_size):
            b = start + i / pop_size
            j = next((t for t, w in enumerate(wheel) if w > b), pop_size - 1)
            sel.append(pop[j])
        n_child = pop_size - elitism
        children = []
        for _ in range(n_child):
            a = sel[rng.randrange(pop_size)]
            b = sel[rng.randrange(pop_size)]
            cross = rng.getrandbits(H) if H else 0
            child = (a & ~cross) | (b & cross)
            mut = 0
            for h in range(H):
                if rng.random() < p_mut / H:
                    mut |= 1 << h
            children.append((child ^ mut) & full)
        pop = children + pop[pop_size - elitism:]
    return {"model": best, "score": best_s, "gens": gens, "evals": score.evals}
