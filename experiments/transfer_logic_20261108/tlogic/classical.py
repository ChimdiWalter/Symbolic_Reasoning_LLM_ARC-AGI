"""Classical references (not gates).

espresso_like: two-level minimisation with every unprobed input as a don't-care, in the style of Espresso's EXPAND and
IRREDUNDANT steps (re-implemented here; the Espresso program itself is not built or run). Each uncovered on-set probe,
in index order, is expanded into a cube by repeatedly dropping the literal whose removal keeps the cube free of
off-set probes and covers the most on-set probes (ties: lowest input); a greedy cover then keeps the cubes that cover
the most still-uncovered on-set probes (ties: earliest cube).
cart: scikit-learn's DecisionTreeClassifier with default settings and random_state 0 on the input bits.
"""
import numpy as np

from .core import masks


def espresso_like(n, O, Z):
    if not O:
        return 0
    if not Z:
        return masks(n)[0]
    cubes, covered = [], 0
    x = O
    while x:
        low = x & -x
        p = low.bit_length() - 1
        x ^= low
        if (covered >> p) & 1:
            continue
        lits = {v: (p >> v) & 1 for v in range(n)}
        cube = 1 << p
        while True:
            best = None
            for v in sorted(lits):
                s = 1 << v
                m = cube | (cube >> s) if lits[v] else cube | (cube << s)
                if m & Z:
                    continue
                gain = (m & O).bit_count()
                if best is None or gain > best[0]:
                    best = (gain, v, m)
            if best is None:
                break
            del lits[best[1]]
            cube = best[2]
        cubes.append(cube)
        covered |= cube
    out, rem = 0, O
    while rem:
        i = max(range(len(cubes)), key=lambda j: ((cubes[j] & rem).bit_count(), -j))
        out |= cubes[i]
        rem &= ~cubes[i]
    return out


def bits_matrix(n):
    N = 1 << n
    idx = np.arange(N)
    return ((idx[:, None] >> np.arange(n)[None, :]) & 1).astype(np.int8)


def to_array(x, n):
    N = 1 << n
    return np.unpackbits(np.frombuffer(x.to_bytes(N // 8 if N >= 8 else 1, "little"), dtype=np.uint8),
                         bitorder="little")[:N]


def from_array(a):
    a = np.asarray(a, dtype=np.uint8)
    pad = (-len(a)) % 8
    if pad:
        a = np.concatenate([a, np.zeros(pad, dtype=np.uint8)])
    return int.from_bytes(np.packbits(a, bitorder="little").tobytes(), "little")


def cart(n, O, Z):
    from sklearn.tree import DecisionTreeClassifier
    X = bits_matrix(n)
    on, off = to_array(O, n).astype(bool), to_array(Z, n).astype(bool)
    rows = on | off
    y = on[rows].astype(int)
    if y.min() == y.max():
        return masks(n)[0] if y[0] else 0
    clf = DecisionTreeClassifier(random_state=0).fit(X[rows], y)
    return from_array(clf.predict(X))
