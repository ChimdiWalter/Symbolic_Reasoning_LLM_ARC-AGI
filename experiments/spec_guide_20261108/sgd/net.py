"""The specification-reading guide: a small transformer encoder over the cells of a hole's input-target pairs.

Tokens (per pair, at most MAXPAIRS pairs):
  a header token: the input and target sizes and whether they are the same;
  cell tokens: in a same-shape pair every changed cell first, then every other cell that is not background in the
  input or the target (at most MAXCELLS); in a pair whose shapes differ, the input's non-background cells and the
  target's cells (at most MAXCELLS / 2 each). A cell token carries the input colour, the target colour (10 for
  none), its row and column, whether it changed, whether the input and the target cell are background, its kind
  (aligned, input only, target only) and its pair's index.
Plus one summary token. The encoder's summary output feeds the heads:
  edit: the operation's edit type (the 19 edits of the frozen language and crop), multi-label;
  view: the view, multi-label;
  key: success of each (kind, view, edit type) block key, multi-label (trained on traced data only).
Augmentation that keeps the labels: a permutation of colours 1 to 9 (0 stays) applied to every grid of the
specification, and the eight symmetries of the square applied to every grid (the edit type and the view do not
change under them; the key head is trained without symmetries, since parameters such as directions would).
"""
import math
import random

import numpy as np
import torch
import torch.nn as nn

from gcon import engine as EN
from objgrow import scene as SC

MAXPAIRS = 4
MAXCELLS = 120
EDITS = tuple(EN.EDIT_TYPES[:-1]) + ("crop",)            # the 19 frozen edits and crop (recolor_table is not generated)
VIEWS = SC.VIEWS
KEYS = [("S", v, e) for v in VIEWS for e in EN.EDIT_TYPES] + [("T", v) for v in VIEWS] + [("W", v) for v in VIEWS]
KEY_INDEX = {k: i for i, k in enumerate(KEYS)}
NONE = 10
NFEAT = 60          # gcon.features: the block feature vector's length (len(features.NAMES))


def bg_of(g):
    cnt = {}
    for r in g:
        for v in r:
            cnt[v] = cnt.get(v, 0) + 1
    return max(sorted(cnt), key=lambda c: cnt[c])


def d4(g, k):
    """The k-th symmetry of the square (0 identity; 1-3 rotations; 4-7 reflections)."""
    a = [list(r) for r in g]
    if k >= 4:
        a = [list(r) for r in zip(*a)]
    for _ in range(k % 4):
        a = [list(r) for r in zip(*a[::-1])]
    return tuple(tuple(r) for r in a)


def tokens(pairs, rng=None, sym=0, perm=None):
    """[(fields...)] integer token rows for one specification: (type, in, out, row, col, changed, inbg, outbg,
    kind, pair, a, b, c, d)."""
    rows = [(0, NONE, NONE, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)]                       # the summary token
    for pi, (x, y) in enumerate(pairs[:MAXPAIRS]):
        if sym:
            x, y = d4(x, sym), d4(y, sym)
        if perm is not None:
            x = tuple(tuple(perm[v] for v in r) for r in x)
            y = tuple(tuple(perm[v] for v in r) for r in y)
        H, W, H2, W2 = len(x), len(x[0]), len(y), len(y[0])
        same = (H, W) == (H2, W2)
        rows.append((1, NONE, NONE, 0, 0, int(same), 0, 0, 0, pi, min(H, 30), min(W, 30), min(H2, 30), min(W2, 30)))
        bx, by = bg_of(x), bg_of(y)
        cells = []
        if same:
            ch, ctx = [], []
            for i in range(H):
                for j in range(W):
                    a, b = x[i][j], y[i][j]
                    t = (2, a, b, i, j, int(a != b), int(a == bx), int(b == by), 0, pi, 0, 0, 0, 0)
                    if a != b:
                        ch.append(t)
                    elif a != bx or b != by:
                        ctx.append(t)
            cells = (ch + ctx)[:MAXCELLS]
        else:
            ins = [(2, x[i][j], NONE, i, j, 0, 0, 0, 1, pi, 0, 0, 0, 0) for i in range(H) for j in range(W)
                   if x[i][j] != bx]
            outs = [(2, NONE, y[i][j], i, j, 0, 0, int(y[i][j] == by), 2, pi, 0, 0, 0, 0) for i in range(H2)
                    for j in range(W2)]
            cells = ins[:MAXCELLS // 2] + outs[:MAXCELLS // 2]
        rows += [tuple(min(v, 29) if k in (3, 4) else v for k, v in enumerate(t)) for t in cells]
    return rows


def batch(token_lists, device):
    n = max(len(t) for t in token_lists)
    arr = np.zeros((len(token_lists), n, 14), dtype=np.int64)
    mask = np.ones((len(token_lists), n), dtype=bool)
    for i, t in enumerate(token_lists):
        arr[i, :len(t)] = np.array(t, dtype=np.int64)
        mask[i, :len(t)] = False
    return torch.from_numpy(arr).to(device), torch.from_numpy(mask).to(device)


class SpecNet(nn.Module):
    def __init__(self, d=128, layers=4, heads=4, ff=256, dropout=0.1):
        super().__init__()
        self.d = d
        self.e_type = nn.Embedding(3, d)
        self.e_in = nn.Embedding(11, d)
        self.e_out = nn.Embedding(11, d)
        self.e_row = nn.Embedding(30, d)
        self.e_col = nn.Embedding(30, d)
        self.e_ch = nn.Embedding(2, d)
        self.e_inbg = nn.Embedding(2, d)
        self.e_outbg = nn.Embedding(2, d)
        self.e_kind = nn.Embedding(3, d)
        self.e_pair = nn.Embedding(MAXPAIRS, d)
        self.e_size = nn.ModuleList([nn.Embedding(31, d) for _ in range(4)])
        enc = nn.TransformerEncoderLayer(d, heads, ff, dropout, batch_first=True, norm_first=True)
        self.enc = nn.TransformerEncoder(enc, layers)
        self.norm = nn.LayerNorm(d)
        self.h_edit = nn.Linear(d, len(EDITS))
        self.h_view = nn.Linear(d, len(VIEWS))
        self.h_key = nn.Sequential(nn.Linear(d, d), nn.GELU(), nn.Linear(d, len(KEYS)))
        # the block head: one block's success (logit) and log(1 + operations) (standardised), from the
        # specification's summary, the block's features (the step's own pair analysis, standardised) and its key
        self.k_emb = nn.Embedding(len(KEYS), 32)
        self.h_block = nn.Sequential(nn.Linear(d + NFEAT + 32, 128), nn.GELU(), nn.Linear(128, 64), nn.GELU(),
                                     nn.Linear(64, 2))

    def embed(self, t, mask):
        x = (self.e_type(t[..., 0]) + self.e_in(t[..., 1]) + self.e_out(t[..., 2]) + self.e_row(t[..., 3]) +
             self.e_col(t[..., 4]) + self.e_ch(t[..., 5]) + self.e_inbg(t[..., 6]) + self.e_outbg(t[..., 7]) +
             self.e_kind(t[..., 8]) + self.e_pair(t[..., 9]))
        x = x + sum(self.e_size[k](t[..., 10 + k]) for k in range(4))
        h = self.enc(x, src_key_padding_mask=mask)
        return self.norm(h[:, 0])

    def forward(self, t, mask):
        z = self.embed(t, mask)
        return {"edit": self.h_edit(z), "view": self.h_view(z), "key": self.h_key(z), "z": z}

    def blocks(self, z, owner, feats, keys):
        """Per block (owner: the index of its specification in the batch): (success logit, standardised cost)."""
        h = torch.cat([z[owner], feats, self.k_emb(keys)], dim=-1)
        o = self.h_block(h)
        return o[:, 0], o[:, 1]


def n_params(m):
    return sum(p.numel() for p in m.parameters())
