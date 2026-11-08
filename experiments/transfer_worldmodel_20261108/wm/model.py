"""The rule language for world models: a model maps (grid, action) to the predicted next grid.

The STATIC language (the base, L0) has three rules:
  * Move: on a directional action, every cell of the actor's colour(s) shifts by the action's displacement when every
    target cell is inside the grid and its colour is passable (or is part of the actor); the cells left behind become
    background. Parameters: actor colours, a displacement per action, the passable colours.
  * ClickMap: on a click, the clicked cell's colour u becomes clickmap[u] (unlisted colours stay).
  * Everything else stays as it was.

GROWN pieces are compositions of one selector, one effect and one trigger (see SKELETONS in induce.py), plus two
representation switches on Move (slide: repeat the step until blocked; wrap: the grid is a torus).
"""
from collections import namedtuple

import numpy as np

from wm.envs import DIRS, parse_click

Piece = namedtuple("Piece", "sel theta eff psi trig when")
N4 = ((-1, 0), (1, 0), (0, -1), (0, 1))
N8 = N4 + ((-1, -1), (-1, 1), (1, -1), (1, 1))
UNIT = ((-1, 0), (1, 0), (0, -1), (0, 1))


class Model:
    __slots__ = ("bg", "actor", "delta", "passable", "slide", "wrap", "clickmap", "pre", "post")

    def __init__(self, bg, actor=()):
        self.bg, self.actor = int(bg), tuple(actor)
        self.delta, self.passable, self.clickmap = {}, frozenset([int(bg)]), {}
        self.slide = self.wrap = False
        self.pre, self.post = (), ()

    def copy(self):
        m = Model(self.bg, self.actor)
        m.delta, m.passable, m.clickmap = dict(self.delta), self.passable, dict(self.clickmap)
        m.slide, m.wrap, m.pre, m.post = self.slide, self.wrap, self.pre, self.post
        return m

    def with_piece(self, p):
        m = self.copy()
        if p.sel == "slide":
            m.slide = True
        elif p.sel == "wrap":
            m.wrap = True
        elif p.when == "pre":
            m.pre = self.pre + (p,)
        else:
            m.post = self.post + (p,)
        return m

    def size(self):
        return len(self.pre) + len(self.post) + int(self.slide) + int(self.wrap)

    def describe(self):
        return {"bg": self.bg, "actor": list(self.actor),
                "delta": {a: list(v) for a, v in sorted(self.delta.items())},
                "passable": sorted(self.passable), "slide": self.slide, "wrap": self.wrap,
                "clickmap": {str(k): v for k, v in sorted(self.clickmap.items())},
                "pieces": [describe_piece(p) for p in self.pre + self.post]}


def describe_piece(p):
    psi = p.psi if not isinstance(p.psi, tuple) or not p.psi or not isinstance(p.psi[0], tuple) else \
        [list(x) for x in p.psi]
    return {"sel": p.sel, "theta": p.theta, "eff": p.eff, "psi": psi, "trig": p.trig, "when": p.when}


def _component(g, y, x):
    c, H, W = g[y, x], g.shape[0], g.shape[1]
    seen, stack = {(y, x)}, [(y, x)]
    while stack:
        cy, cx = stack.pop()
        for dy, dx in N4:
            ny, nx = cy + dy, cx + dx
            if 0 <= ny < H and 0 <= nx < W and (ny, nx) not in seen and g[ny, nx] == c:
                seen.add((ny, nx))
                stack.append((ny, nx))
    return seen


def body_of(m, g):
    """The actor's cells as two index arrays (rows, columns)."""
    if not m.actor:
        return np.empty(0, np.int64), np.empty(0, np.int64)
    return np.nonzero(g == m.actor[0]) if len(m.actor) == 1 else np.nonzero(np.isin(g, m.actor))


def _target(m, y, x, d, H, W):
    ny, nx = y + d[0], x + d[1]
    if m.wrap:
        return ny % H, nx % W
    return (ny, nx) if 0 <= ny < H and 0 <= nx < W else None


def trig_ok(trig, a):
    return trig == "any" or (trig == "dir" and a[0] != "C") or (trig == "click" and a[0] == "C")


def select(p, m, g0, g1, a, ctx):
    """Cells chosen by piece p's selector. Pre pieces read the grid before the step; post pieces read the current
    grid for colour-based selectors and the grid before the step for region selectors."""
    s, H, W = p.sel, g0.shape[0], g0.shape[1]
    if s == "ahead":
        d = m.delta.get(a)
        if not d or d == (0, 0):
            return set()
        body = ctx.get("body")
        if body is None:
            body = ctx["body"] = body_of(m, g0)
        ys, xs = body
        if not len(ys):
            return set()
        ty, tx = ys + d[0], xs + d[1]
        if m.wrap:
            ty, tx = ty % H, tx % W
        else:
            k = (ty >= 0) & (ty < H) & (tx >= 0) & (tx < W)
            ty, tx = ty[k], tx[k]
        bm = np.zeros((H, W), bool)
        bm[ys, xs] = True
        k = (~bm[ty, tx]) & (g0[ty, tx] == p.theta[0])
        out = set()
        for y, x in zip(ty[k].tolist(), tx[k].tolist()):
            if (y, x) not in out:
                out |= _component(g0, y, x) if p.theta[1] else {(y, x)}
        return out
    if s == "vacated":
        return ctx.get("vacated", set())
    if s in ("click_n4", "click_n8", "click_region"):
        y, x = parse_click(a)
        if s == "click_region":
            return _component(g0, y, x)
        return {(y + dy, x + dx) for dy, dx in (N4 if s == "click_n4" else N8)
                if 0 <= y + dy < H and 0 <= x + dx < W}
    if s == "corner_region":
        cy, cx = ((0, 0), (0, W - 1), (H - 1, 0), (H - 1, W - 1))[p.theta]
        return _component(g0, cy, cx)
    if s == "first":
        c, order = p.theta
        src = g1 if p.when == "post" else g0
        idx = np.flatnonzero((src if order < 2 else src.T) == c)
        if not len(idx):
            return set()
        k = int(idx[0] if order % 2 == 0 else idx[-1])
        if order < 2:
            return {(k // W, k % W)}
        return {(k % H, k // H)}
    if s == "all":
        c = p.theta[0] if isinstance(p.theta, tuple) else p.theta
        src = g1 if p.when == "post" else g0
        return {tuple(q) for q in np.argwhere(src == c)}
    raise ValueError(s)


def apply_piece(p, m, g0, g1, a, ctx):
    if not trig_ok(p.trig, a):
        return
    cells = select(p, m, g0, g1, a, ctx)
    if not cells:
        return
    e, H, W = p.eff, g0.shape[0], g0.shape[1]
    if e == "recolour_to":
        for q in cells:
            g1[q] = p.psi
    elif e == "recolour_map":
        mp = dict(p.psi)
        for q in cells:
            v = mp.get(int(g1[q]))
            if v is not None:
                g1[q] = v
    elif e == "recolour_to_clicked":
        y, x = parse_click(a)
        c = g0[y, x]
        for q in cells:
            g1[q] = c
    elif e == "shift_action":
        d = m.delta.get(a)
        if not d or d == (0, 0):
            return
        dest = []
        for y, x in cells:
            t = _target(m, y, x, d, H, W)
            if t is None:
                return
            dest.append(t)
        if all(g1[t] == m.bg or t in cells for t in dest):
            vals = [g1[q] for q in cells]
            for q in cells:
                g1[q] = m.bg
            for t, v in zip(dest, vals):
                g1[t] = v
    elif e == "shift_fixed":
        dy, dx = p.theta[1]
        for y, x in sorted(cells, key=lambda q: -(q[0] * dy + q[1] * dx)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < H and 0 <= nx < W and g1[ny, nx] == m.bg and g1[y, x] != m.bg:
                g1[ny, nx], g1[y, x] = g1[y, x], m.bg
    else:
        raise ValueError(e)


def move(m, g0, g1, a, ctx):
    d = m.delta.get(a)
    if not d or d == (0, 0):
        return
    H, W = g0.shape
    body = ctx.get("body")
    if body is None:
        body = ctx["body"] = body_of(m, g0)
    ys, xs = body
    if not len(ys):
        return
    pas = np.fromiter(m.passable, dtype=g1.dtype, count=len(m.passable))
    cy, cx, moved = ys, xs, False
    for _ in range(max(H, W) if m.slide else 1):
        ty, tx = cy + d[0], cx + d[1]
        if m.wrap:
            ty, tx = ty % H, tx % W
        elif ((ty < 0) | (ty >= H) | (tx < 0) | (tx >= W)).any():
            break
        inb = np.zeros((H, W), bool)
        inb[cy, cx] = True
        if not (np.isin(g1[ty, tx], pas) | inb[ty, tx]).all():
            break
        vals = g1[cy, cx].copy()
        g1[cy, cx] = m.bg
        g1[ty, tx] = vals
        cy, cx, moved = ty, tx, True
    ctx["vacated"] = (set(zip(ys.tolist(), xs.tolist())) - set(zip(cy.tolist(), cx.tolist()))) if moved else set()
    ctx["moved"] = moved


def predict(m, g, a):
    g1 = g.copy()
    ctx = {}
    for p in m.pre:
        apply_piece(p, m, g, g1, a, ctx)
    if a[0] != "C" and m.actor:
        move(m, g, g1, a, ctx)
    elif a[0] == "C" and m.clickmap:
        y, x = parse_click(a)
        v = m.clickmap.get(int(g[y, x]))
        if v is not None:
            g1[y, x] = v
    for p in m.post:
        apply_piece(p, m, g, g1, a, ctx)
    return g1


def predict_pre(m, g, a):
    """The grid after the pre pieces only (used to refit the passable colours)."""
    g1 = g.copy()
    ctx = {}
    for p in m.pre:
        apply_piece(p, m, g, g1, a, ctx)
    return g1
