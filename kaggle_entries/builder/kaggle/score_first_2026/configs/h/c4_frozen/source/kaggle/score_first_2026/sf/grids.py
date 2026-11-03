"""Grid utilities: validation, the eight symmetries of the square (D8), colour permutations, and task augmentation
with exact inverses. Written for this project from first principles."""
import random

import numpy as np

N_COLOURS = 10
MAX_SIDE = 30


def as_array(grid):
    a = np.asarray(grid, dtype=np.int64)
    if a.ndim != 2:
        raise ValueError("grid must be 2-D")
    return a


def is_valid_grid(grid):
    """A valid ARC grid: a non-empty rectangular list of rows of ints in 0..9, at most 30 x 30."""
    if not isinstance(grid, (list, tuple)) or not grid:
        return False
    w = None
    for row in grid:
        if not isinstance(row, (list, tuple)) or not row:
            return False
        if w is None:
            w = len(row)
        elif len(row) != w:
            return False
        for v in row:
            if isinstance(v, bool) or not isinstance(v, (int, np.integer)) or not 0 <= int(v) < N_COLOURS:
                return False
    return len(grid) <= MAX_SIDE and w <= MAX_SIDE


def to_list(a):
    return [[int(v) for v in row] for row in np.asarray(a)]


def key(grid):
    """Hashable canonical key of a grid."""
    a = np.asarray(grid)
    return (a.shape[0], a.shape[1], a.astype(np.int8).tobytes())


# D8: t in 0..7; k = t % 4 quarter turns counter-clockwise, then a left-right flip when t >= 4.
def d8(a, t):
    a = np.rot90(np.asarray(a), t % 4)
    if t >= 4:
        a = np.fliplr(a)
    return np.ascontiguousarray(a)


def d8_inv(a, t):
    a = np.asarray(a)
    if t >= 4:
        a = np.fliplr(a)
    return np.ascontiguousarray(np.rot90(a, -(t % 4)))


def identity_perm():
    return np.arange(N_COLOURS)


def random_perm(rng, keep_zero=True):
    p = np.arange(N_COLOURS)
    if keep_zero:
        rest = list(range(1, N_COLOURS))
        rng.shuffle(rest)
        p[1:] = rest
    else:
        rest = list(range(N_COLOURS))
        rng.shuffle(rest)
        p[:] = rest
    return p


class Aug:
    """One augmentation: a D8 element, a colour permutation (applied after the symmetry) and a demonstration order."""

    def __init__(self, t=0, perm=None, order=None):
        self.t = int(t)
        self.perm = identity_perm() if perm is None else np.asarray(perm, dtype=np.int64)
        self.inv_perm = np.argsort(self.perm)
        self.order = None if order is None else list(order)

    def fwd(self, g):
        return self.perm[d8(as_array(g), self.t)]

    def inv(self, g):
        return d8_inv(self.inv_perm[as_array(g)], self.t)

    def apply_task(self, train_pairs, test_inputs):
        pairs = [(self.fwd(i), self.fwd(o)) for i, o in train_pairs]
        if self.order is not None:
            pairs = [pairs[j] for j in self.order]
        return pairs, [self.fwd(g) for g in test_inputs]

    def describe(self):
        return {"t": self.t, "perm": [int(v) for v in self.perm], "order": self.order}

    @staticmethod
    def from_desc(d):
        return Aug(d["t"], d["perm"], d.get("order"))


def make_augs(n, n_train, seed, keep_zero=True, shuffle_order=True):
    """n augmentations: the identity first, then the other seven symmetries with identity colours, then random
    (symmetry, colour permutation, order) triples. Deterministic in seed."""
    rng = random.Random(seed)
    augs = [Aug(0)]
    for t in range(1, 8):
        if len(augs) >= n:
            break
        augs.append(Aug(t))
    while len(augs) < n:
        t = rng.randrange(8)
        perm = random_perm(rng, keep_zero)
        order = list(range(n_train))
        if shuffle_order:
            rng.shuffle(order)
        augs.append(Aug(t, perm, order))
    return augs[:n]


def palette(g):
    return set(int(v) for v in np.unique(as_array(g)))
