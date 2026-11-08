"""Exhaustive finite-model validation of every L0 operator contract (directive section 8 and 16).

Declared scope of this test: every grid with h, w <= 3 over colours {0, 1, 2} (21,861 grids; 3 x 3 included), every
4 x 4 grid over {0, 1} (65,536) for the operators whose behaviour needs an interior (fill, outline, gravity), and
every parameter in the operator's domain over that palette. Checks:
  (a) forward on concrete inputs:  apply(x, th) in gamma(fwd(alpha(x), th))
  (b) backward:                    every x with apply(x, th) == y is in gamma(bwd(y, th))
  (c) forward on abstract inputs:  for random abstract values A with enumerable gamma(A), every apply(z, th) for z in
                                   gamma(A) is in gamma(fwd(A, th))
These support the finite scope only; they are not a proof for arbitrary grids (the property tests add larger grids).
"""
import collections
import itertools

import numpy as np
import pytest
from conftest import FakeCtx, all_grids, tiny_space

from cast import absdom as D
from cast import ops as O

CTX = FakeCtx((0, 1, 2))
TINY = list(tiny_space(max_cells=9, colours=(0, 1, 2), extra=()))
BIN4 = list(all_grids(4, 4, (0, 1)))
NEEDS_INTERIOR = ("fill_enclosed", "outline", "gravity")


def space_for(op):
    return TINY + (BIN4 if op.name in NEEDS_INTERIOR else [])


@pytest.mark.parametrize("op", O.L0, ids=lambda o: o.name)
def test_forward_and_backward_exhaustive(op):
    grids = space_for(op)
    for th in op.domain(CTX):
        pre = collections.defaultdict(list)
        for x in grids:
            y = op.apply(x, th)
            if y is None:
                continue
            assert D.contains(op.fwd(D.alpha(x), th), y), (op.name, th, x.tolist(), y.tolist())
            pre[(y.shape, y.tobytes())].append(x)
        for key, xs in pre.items():
            y = np.frombuffer(key[1], dtype=np.int64).reshape(key[0])
            b = op.bwd(y, th)
            for x in xs:
                assert D.contains(b, x), ("bwd", op.name, th, y.tolist(), x.tolist())


def random_abstract(rng, shape, colours=(0, 1, 2), p_multi=0.35):
    cells = np.zeros(shape, dtype=np.uint16)
    for idx in np.ndindex(shape):
        k = 2 if rng.random() < p_multi else 1
        cs = rng.choice(colours, size=k, replace=False)
        for c in cs:
            cells[idx] |= np.uint16(1 << int(c))
    return D.Abs({shape}, (1, 1), cells, D.ALL)


def members(a):
    opts = [[k for k in range(10) if m >> k & 1] for m in a.cells.ravel()]
    for vals in itertools.product(*opts):
        g = np.array(vals, dtype=np.int64).reshape(a.cells.shape)
        if D.contains(a, g):
            yield g


@pytest.mark.parametrize("op", O.L0, ids=lambda o: o.name)
def test_forward_on_abstract_inputs(op):
    rng = np.random.default_rng(7)
    shapes = [(2, 2), (2, 3), (3, 3), (3, 2)] + ([(4, 4)] if op.name in NEEDS_INTERIOR else [])
    for trial in range(60):
        s = shapes[trial % len(shapes)]
        a = random_abstract(rng, s)
        mem = list(members(a))
        if len(mem) > 600:
            mem = [mem[i] for i in rng.choice(len(mem), 600, replace=False)]
        for th in op.domain(CTX):
            f = op.fwd(a, th)
            for z in mem:
                y = op.apply(z, th)
                if y is not None:
                    assert D.contains(f, y), (op.name, th, z.tolist(), y.tolist())


def test_alpha_is_exact_and_join_meet_laws():
    rng = np.random.default_rng(3)
    for _ in range(200):
        x = rng.integers(0, 3, size=(rng.integers(1, 4), rng.integers(1, 4)))
        y = rng.integers(0, 3, size=x.shape)
        ax, ay = D.alpha(x), D.alpha(y)
        assert D.contains(ax, x)
        assert D.contains(ax, y) == np.array_equal(x, y)
        j = D.join(ax, ay)
        assert D.contains(j, x) and D.contains(j, y)
        m = D.meet(ax, ay)
        assert m.bottom == (not np.array_equal(x, y))
        assert not D.contains(D.BOTTOM(), x)
