import itertools
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(HERE))          # a PYTHONPATH code snapshot, when set, takes precedence
os.environ.setdefault("OMP_NUM_THREADS", "1")


class FakeCtx:
    """A grammar instance with a fixed palette (tests only)."""

    def __init__(self, colours=(0, 1, 2)):
        self.in_pal = list(colours)
        self.out_pal = list(colours)
        self.all_pal = list(colours)
        self.same_shape = True
        self.train = []
        self.test_inputs = []


def all_grids(h, w, colours):
    for vals in itertools.product(colours, repeat=h * w):
        yield np.array(vals, dtype=np.int64).reshape(h, w)


def tiny_space(max_cells=6, colours=(0, 1, 2), extra=((3, 3),)):
    """Every grid with h, w <= 3 and h * w <= max_cells over `colours`, plus the shapes in `extra`."""
    shapes = [(h, w) for h in (1, 2, 3) for w in (1, 2, 3) if h * w <= max_cells] + list(extra)
    seen = set()
    for s in shapes:
        if s in seen:
            continue
        seen.add(s)
        yield from all_grids(s[0], s[1], colours)
