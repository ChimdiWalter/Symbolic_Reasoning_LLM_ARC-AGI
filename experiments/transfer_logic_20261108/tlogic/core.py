"""Boolean core on exact truth tables stored as Python integers.

A function of n inputs is an integer of 2**n bits: bit i is the value at input i, and bit v of i is input x_v.

Building blocks (the base language, "two-input gates"): constants, literals and every two-input gate (all tables of
every pair of inputs). This is the companion cofactor engine's two-input leaf bank, re-implemented on bitsets so that it
runs at 12 inputs.
Selection among fitting blocks: smallest size first (constant 0, literal 1, gate 2), then the most witness evidence on
the block's inputs, then canonical order (lowest input indices, positive literal first).
Unobserved cells of a chosen gate, and empty cofactors, take the majority label of the nearest observed node (ties 0).
Failure description: when no block fits the probes of a node, the inputs implicated by the closest conflicting probe
pairs: witness edges (two probes one input apart with different labels, which certify that input as essential), else
conflicting pairs two inputs apart, else three.
Growth: a Shannon cofactor split on the most implicated input (ties: lowest index); both halves are solved by the
same loop. The shuffled control replaces the chosen input by a seeded random permutation of the free inputs.
"""
from functools import lru_cache
from itertools import combinations, product
import hashlib
import random


class Exhausted(RuntimeError):
    """The node allowance of one fit ran out; the arm then returns no program (fail closed)."""


@lru_cache(None)
def masks(n):
    """Return (full, V, NV, cells): V[v] = inputs with x_v = 1, NV[v] its complement, cells[(a, b)] four cell masks."""
    N = 1 << n
    full = (1 << N) - 1
    V = []
    for v in range(n):
        s = "".join("1" if (i >> v) & 1 else "0" for i in range(N - 1, -1, -1))
        V.append(int(s, 2))
    NV = [full ^ m for m in V]
    cells = {}
    for a, b in combinations(range(n), 2):
        cells[(a, b)] = tuple((V[a] if c & 1 else NV[a]) & (V[b] if c & 2 else NV[b]) for c in range(4))
    return full, tuple(V), tuple(NV), cells


def vec(prog, n):
    """Truth table of a program."""
    full, V, NV, cells = masks(n)
    op = prog[0]
    if op == "C":
        return full if prog[1] else 0
    if op == "L":
        return V[prog[1]] if prog[2] else NV[prog[1]]
    if op == "G":
        _, a, b, t = prog
        out = 0
        for c in range(4):
            if (t >> c) & 1:
                out |= cells[(a, b)][c]
        return out
    if op == "IF":
        _, v, t0, t1 = prog
        return (vec(t0, n) & NV[v]) | (vec(t1, n) & V[v])
    raise ValueError(op)


def size(prog):
    """Number of blocks and splits: constant 0, literal 1, gate 2, split 1 + both halves."""
    op = prog[0]
    if op == "IF":
        return 1 + size(prog[2]) + size(prog[3])
    return {"C": 0, "L": 1, "G": 2}[op]


def leaves(prog):
    return leaves(prog[2]) + leaves(prog[3]) if prog[0] == "IF" else 1


def depth(prog):
    return 1 + max(depth(prog[2]), depth(prog[3])) if prog[0] == "IF" else 0


def essential(T, n):
    """Inputs the function depends on."""
    full, V, NV, _ = masks(n)
    return [v for v in range(n) if ((T & NV[v]) << (1 << v)) ^ (T & V[v])]


def majority(O, Z, inherited):
    a, b = O.bit_count(), Z.bit_count()
    if a == b == 0:
        return inherited
    return 1 if a > b else 0


def witness_counts(n, O, Z, avail):
    """Witness edges per free input: probe pairs one input apart with different labels."""
    full, V, NV, _ = masks(n)
    out = {}
    for v in avail:
        s = 1 << v
        c = ((O & NV[v]) & (Z >> s)).bit_count() + ((Z & NV[v]) & (O >> s)).bit_count()
        if c:
            out[v] = c
    return out


def conflict_counts(n, O, Z, avail, d):
    """Conflicting probe pairs exactly d free inputs apart; each pair adds one to each input where they differ."""
    full, V, NV, _ = masks(n)
    out = {}
    for combo in combinations(sorted(avail), d):
        u, rest = combo[0], combo[1:]
        for signs in product((0, 1), repeat=d - 1):
            m, off = NV[u], 1 << u
            for w, sg in zip(rest, signs):
                if sg:
                    m &= V[w]
                    off -= 1 << w
                else:
                    m &= NV[w]
                    off += 1 << w
            Zs = Z >> off if off > 0 else Z << -off
            Os = O >> off if off > 0 else O << -off
            k = ((O & m) & Zs).bit_count() + ((Z & m) & Os).bit_count()
            if k:
                for w in combo:
                    out[w] = out.get(w, 0) + k
    return out


def describe_failure(n, O, Z, avail, wc):
    """What is missing: the inputs implicated by the closest conflicting probe pairs, and their distance."""
    if wc:
        return wc, 1
    for d in (2, 3):
        if len(avail) >= d:
            c = conflict_counts(n, O, Z, avail, d)
            if c:
                return c, d
    return {}, None


def fit_block(n, O, Z, avail, wc, inherited):
    """Smallest fitting base-language block on the probes O (label 1) and Z (label 0) of a node, or None."""
    full, V, NV, cells = masks(n)
    fill = majority(O, Z, inherited)
    if not Z:
        return ("C", 1) if O else ("C", fill)
    if not O:
        return ("C", 0)
    best = None
    for v in avail:
        for s in (1, 0):
            pos, neg = (V[v], NV[v]) if s else (NV[v], V[v])
            if not (O & neg) and not (Z & pos):
                key = (-wc.get(v, 0), v, -s)
                if best is None or key < best[0]:
                    best = (key, ("L", v, s))
    if best:
        return best[1]
    for a, b in combinations(sorted(avail), 2):
        t, ok = 0, True
        for c, m in enumerate(cells[(a, b)]):
            o, z = O & m, Z & m
            if o and z:
                ok = False
                break
            if o or (not z and fill):
                t |= 1 << c
        if ok:
            key = (-(wc.get(a, 0) + wc.get(b, 0)), a, b)
            if best is None or key < best[0]:
                best = (key, ("G", a, b, t))
    return best[1] if best else None


def _seed(*parts):
    return int.from_bytes(hashlib.sha256("|".join(map(str, parts)).encode()).digest()[:8], "big")


def grow(n, O, Z, avail, mode, key, path=(), allowance=None, inherited=0, trace=None):
    """The reasoning loop on one node: propose a block, check it, describe the failure, split, solve the halves.

    mode: "static" (no growth), "grown" (split on the described input) or "shuffled" (seeded permutation of it).
    """
    if allowance is not None:
        allowance[0] -= 1
        if allowance[0] < 0:
            raise Exhausted("node allowance")
    wc = witness_counts(n, O, Z, avail)
    block = fit_block(n, O, Z, avail, wc, inherited)
    if block is not None:
        return block
    if mode == "static":
        return None
    score, dist = describe_failure(n, O, Z, avail, wc)
    full, V, NV, _ = masks(n)
    if score:
        v = min(score, key=lambda u: (-score[u], u))
    else:
        both = [u for u in avail if ((O | Z) & V[u]) and ((O | Z) & NV[u])]
        v = both[0] if both else avail[0]
    if mode == "shuffled":
        perm = list(avail)
        random.Random(_seed("shuffled", key, path)).shuffle(perm)
        v = dict(zip(avail, perm))[v]
    elif mode != "grown":
        raise ValueError(mode)
    if trace is not None:
        trace.append({"path": path, "split": v, "distance": dist, "certified": sorted(wc)})
    rest = tuple(u for u in avail if u != v)
    here = majority(O, Z, inherited)
    t0 = grow(n, O & NV[v], Z & NV[v], rest, mode, key, path + ((v, 0),), allowance, here, trace)
    t1 = grow(n, O & V[v], Z & V[v], rest, mode, key, path + ((v, 1),), allowance, here, trace)
    return ("IF", v, t0, t1)


def learn(n, O, Z, mode, key, node_cap=4096, trace=None):
    """Fit a program to the probes. Returns (program or None, status)."""
    try:
        prog = grow(n, O, Z, tuple(range(n)), mode, key, (), [node_cap], majority(O, Z, 0), trace)
    except Exhausted:
        return None, "EXHAUSTED"
    if prog is None:
        return None, "NO_FIT_IN_LANGUAGE"
    T = vec(prog, n)
    if (T & Z) or (O & ~T):
        raise AssertionError("composed program violates a probe")
    return prog, "FIT"
