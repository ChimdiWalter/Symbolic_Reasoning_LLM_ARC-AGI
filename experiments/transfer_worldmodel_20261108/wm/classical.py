"""Classical comparator: a local-patch nearest-neighbour transition model (a learned cellular-automaton table).

Each cell's next colour is predicted from (the action, the cell's offset to the click if any, clipped to -3..3, and
its 5x5 neighbourhood before the step). A key seen in training gives its majority next colour; an unseen key takes
the majority next colour of the training keys with the same action part at the smallest Hamming distance over the
patch; with no such keys the cell keeps its colour. With fallback="keep", an unseen key keeps its colour (a plain
local table with no-change as the default).
"""
from collections import Counter

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from wm.envs import parse_click


def _keys(g, a):
    H, W = g.shape
    P = sliding_window_view(np.pad(g.astype(np.int16), 2, constant_values=-1), (5, 5)).reshape(H * W, 25)
    if a[0] == "C":
        cy, cx = parse_click(a)
        ys, xs = np.divmod(np.arange(H * W), W)
        oy, ox = np.clip(ys - cy, -3, 3), np.clip(xs - cx, -3, 3)
        heads = [("C", int(u), int(v)) for u, v in zip(oy, ox)]
    else:
        heads = [(a, 0, 0)] * (H * W)
    return heads, P


class LocalNN:
    def __init__(self, T, fallback="nn"):
        self.fallback, self.table, groups = fallback, {}, {}
        for g0, a, g1 in T:
            heads, P = _keys(g0, a)
            lab = g1.ravel()
            for h, row, y in zip(heads, P, lab):
                self.table.setdefault((h, row.tobytes()), Counter())[int(y)] += 1
                groups.setdefault(h, ([], []))
                groups[h][0].append(row)
                groups[h][1].append(int(y))
        self.groups = {h: (np.array(r), np.array(y)) for h, (r, y) in groups.items()}

    def predict(self, g, a):
        heads, P = _keys(g, a)
        out = g.ravel().copy()
        for i, (h, row) in enumerate(zip(heads, P)):
            c = self.table.get((h, row.tobytes()))
            if c is not None:
                out[i] = c.most_common(1)[0][0]
                continue
            grp = self.groups.get(h)
            if grp is None or self.fallback == "keep":
                continue
            d = (grp[0] != row).sum(1)
            near = grp[1][d == d.min()]
            out[i] = Counter(near.tolist()).most_common(1)[0][0]
        return out.reshape(g.shape)
