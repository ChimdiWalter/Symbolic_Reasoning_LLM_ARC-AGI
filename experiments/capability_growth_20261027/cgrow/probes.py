"""Generic probe grids for behaviour checks (system side: rename / short-composition / kind checks; evaluator side:
agreement with a removed reference). Seeded and deterministic. The generator mixes standard ARC-like structures
(uniform noise, sparse objects on a background, framed grids, grids with uniform lines, periodic tilings,
block-magnified grids) and is the same for every arm; it is never shown to the proposer.
"""
import random


def _noise(r, h, w, k):
    cols = r.sample(range(10), k)
    return [[r.choice(cols) for _ in range(w)] for _ in range(h)]


def _sparse(r, h, w):
    bg = r.randrange(10)
    g = [[bg] * w for _ in range(h)]
    for _ in range(r.randint(1, 4)):
        c = r.choice([x for x in range(10) if x != bg])
        hh, ww = r.randint(1, max(1, h // 2)), r.randint(1, max(1, w // 2))
        i0, j0 = r.randrange(h - hh + 1), r.randrange(w - ww + 1)
        for i in range(i0, i0 + hh):
            for j in range(j0, j0 + ww):
                if r.random() < 0.85:
                    g[i][j] = c
    return g


def _framed(r, h, w):
    g = _noise(r, h, w, r.randint(2, 4))
    c = r.randrange(10)
    for i in range(h):
        for j in range(w):
            if i in (0, h - 1) or j in (0, w - 1):
                g[i][j] = c
    return g


def _lined(r, h, w):
    g = _noise(r, h, w, r.randint(2, 4))
    for _ in range(r.randint(1, 3)):
        c = r.randrange(10)
        if r.random() < 0.5:
            i = r.randrange(h)
            g[i] = [c] * w
        else:
            j = r.randrange(w)
            for i in range(h):
                g[i][j] = c
    return g


def _tiled(r, h, w):
    th, tw = r.randint(1, 3), r.randint(1, 3)
    t = _noise(r, th, tw, r.randint(2, 3))
    return [[t[i % th][j % tw] for j in range(w)] for i in range(h)]


def _blocks(r, h, w):
    k = r.choice([2, 3])
    sh, sw = max(1, h // k), max(1, w // k)
    s = _noise(r, sh, sw, r.randint(2, 4))
    return [[s[i // k][j // k] for j in range(sw * k)] for i in range(sh * k)]


KINDS = (_noise, _sparse, _framed, _lined, _tiled, _blocks)


def probe_grids(n=12, seed=20261027, min_side=2, max_side=10):
    r = random.Random(seed)
    out = []
    for i in range(n):
        kind = KINDS[i % len(KINDS)]
        h, w = r.randint(max(min_side, 3), max_side), r.randint(max(min_side, 3), max_side)
        g = kind(r, h, w) if kind is not _noise else _noise(r, h, w, r.randint(2, 4))
        out.append(tuple(tuple(row) for row in g))
    return out
