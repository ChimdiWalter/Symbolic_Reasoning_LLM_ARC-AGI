"""Unit checks for the T1 adapter (brute force on small cases). Run: python3 -I tests/test_tlogic.py"""
import os
import random
import sys
from itertools import combinations

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tlogic import classical, core, pla, policy  # noqa: E402


def bit(x, i):
    return (x >> i) & 1


def brute_conflicts(n, O, Z, avail, d):
    out = {}
    pts1 = [i for i in range(1 << n) if bit(O, i)]
    pts0 = [i for i in range(1 << n) if bit(Z, i)]
    for a in pts1:
        for b in pts0:
            diff = [v for v in range(n) if bit(a ^ b, v)]
            if len(diff) == d and all(v in avail for v in diff):
                for v in diff:
                    out[v] = out.get(v, 0) + 1
    return out


def test_counts():
    rng = random.Random(1)
    for n in (4, 5, 6):
        for _ in range(30):
            T = rng.getrandbits(1 << n)
            P = rng.getrandbits(1 << n)
            O, Z = T & P, P & ~T
            avail = tuple(range(n))
            assert core.witness_counts(n, O, Z, avail) == brute_conflicts(n, O, Z, avail, 1)
            for d in (2, 3):
                assert core.conflict_counts(n, O, Z, avail, d) == brute_conflicts(n, O, Z, avail, d)


def test_fits_and_static_superset():
    rng = random.Random(2)
    for n in (5, 6, 7):
        for _ in range(40):
            T = rng.getrandbits(1 << n)
            P = rng.getrandbits(1 << n) | 1
            O, Z = T & P, P & ~T
            for mode in ("grown", "shuffled"):
                prog, st = core.learn(n, O, Z, mode, "k")
                assert st == "FIT" and not (core.vec(prog, n) ^ T) & P
            sp, st = core.learn(n, O, Z, "static", "k")
            gp, _ = core.learn(n, O, Z, "grown", "k")
            if sp is not None:
                assert sp == gp          # grown returns the static block whenever the base language fits
            E = classical.espresso_like(n, O, Z)
            assert not (E ^ T) & P
            C = classical.cart(n, O, Z)
            assert not (C ^ T) & P


def test_two_input_exact():
    n = 6
    full, V, NV, cells = core.masks(n)
    for a, b in combinations(range(n), 2):
        T = V[a] ^ V[b]
        prog, st = core.learn(n, T, full ^ T, "static", "k")
        assert core.vec(prog, n) == T
    e = core.essential(V[1] & V[4], n)
    assert e == [1, 4]


def test_pla_parse():
    n, m, cubes, _ = pla.parse(".i 3\n.o 2\n1-0 10\n01-|01\n.e\n")
    on, dc = pla.tables(n, m, cubes)
    full, V, NV, _ = core.masks(3)
    assert on[0] == V[0] & NV[2] and on[1] == NV[0] & V[1] and dc == [0, 0]


def test_policy():
    rng = random.Random(3)
    T = policy.tests()
    for _ in range(20):
        rules = []
        for _ in range(rng.randint(1, 6)):
            r = tuple(rng.choice([None] + [t for t, _ in T[f]]) for f in range(5))
            rules.append((r, rng.randint(0, 1)))
        vecv = policy.evaluate(rules)
        for i in rng.sample(range(4096), 50):        # brute-force first match at sampled headers
            want = 0
            for r, act in rules:
                if bit(policy.rule_mask(r), i):
                    want = act
                    break
            assert bit(vecv, i) == want
        P = rng.getrandbits(4096)
        O, Z = vecv & P, P & ~vecv
        for mode in ("grown", "shuffled", "grown_arity", "full"):
            rs, d, st, _ = policy.learn(O, Z, mode, "k")
            assert st == "FIT" and not (policy.evaluate(rs, d) ^ vecv) & P


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
