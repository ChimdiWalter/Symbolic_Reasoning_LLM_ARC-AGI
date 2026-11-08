"""Eleven public rule sets as deterministic grid simulators, written here from the published rules (not the original
code; running downloaded game code was not permitted in this study). Every simulator is a pure function of the visible
grid and the action, so the next frame is fully determined by what the learner sees.

Each instance draws its own layout and its own colour for every role, so a learner cannot rely on fixed colours.
Actions follow the ARC-AGI-3 convention: four directional actions (ACTION1..4, written U, D, L, R) or a click on a
cell (ACTION6 with coordinates, written "C:y:x").

| family  | public rule set it follows                                    | rule in one line                                  |
|---------|----------------------------------------------------------------|---------------------------------------------------|
| maze    | ARCEngine example `simple_maze` (MIT)                          | the actor steps into background; anything blocks  |
| toggle  | click-to-toggle cell puzzles                                   | a click swaps colour a and b on the clicked cell  |
| push    | Sokoban movement and pushing (goal squares omitted)            | a box ahead moves on if the cell beyond is free   |
| energy  | ARCEngine example `complex_maze`, its energy bar (MIT)          | maze moves; every action switches off one bar cell |
| ice     | ice-sliding puzzles                                            | the actor slides until the next cell is not free  |
| lights  | Lights Out                                                     | a click toggles the cell and its 4 neighbours     |
| flood   | Flood-It (colour picked by clicking a cell)                    | the top-left region takes the clicked cell colour |
| gravity | falling rocks as in Boulder Dash                               | after the move, each unsupported rock falls 1     |
| trail   | trail-painting puzzles                                         | the cell the actor leaves becomes paint           |
| merge   | ARCEngine example `merge` (MIT), adapted (see below)           | a piece the actor bumps into joins the actor      |
| wrap    | wrap-around edges as in Pac-Man tunnels                        | moves off one edge re-enter at the opposite edge  |

Adaptations, stated plainly: `maze` exits block instead of ending the level; `energy` keeps playing when the bar is
empty (no game over); `merge` shows a joined piece in the actor's colour and the joining step does not move (in the
original the joined body moves at once and keeps the piece's colour, which a frame does not show).
"""
import numpy as np

DIRS = {"U": (-1, 0), "D": (1, 0), "L": (0, -1), "R": (0, 1)}
DIR_ACTIONS = ["U", "D", "L", "R"]
FAMILIES = ["maze", "toggle", "push", "energy", "ice", "lights", "flood", "gravity", "trail", "merge", "wrap"]


def click_actions(H, W):
    return [f"C:{y}:{x}" for y in range(H) for x in range(W)]


def parse_click(a):
    _, y, x = a.split(":")
    return int(y), int(x)


def _roles(rng, n):
    return [int(c) for c in rng.choice(np.arange(1, 10), size=n, replace=False)]


def _room(rng, H, W, wall, density, border=True):
    g = np.zeros((H, W), np.int8)
    m = rng.random((H, W)) < density
    if border:
        m[0, :] = m[-1, :] = m[:, 0] = m[:, -1] = True
    g[m] = wall
    return g


def _place(rng, g, colour, n):
    free = np.argwhere(g == 0)
    idx = rng.choice(len(free), size=n, replace=False)
    for y, x in free[idx]:
        g[y, x] = colour


def _actor(g, a):
    p = np.argwhere(g == a)
    return (int(p[0][0]), int(p[0][1])) if len(p) else None


# ---------------------------------------------------------------- generators: rng -> (grid, params, actions)
def gen_maze(rng):
    H, W = int(rng.integers(8, 12)), int(rng.integers(8, 12))
    w, a, x = _roles(rng, 3)
    g = _room(rng, H, W, w, 0.18)
    _place(rng, g, a, 1)
    _place(rng, g, x, 1)
    return g, {"wall": w, "actor": a, "exit": x}, DIR_ACTIONS


def gen_toggle(rng):
    n = int(rng.integers(5, 8))
    a, b, c = _roles(rng, 3)
    g = rng.choice(np.array([a, b, c], np.int8), size=(n, n), p=[0.4, 0.4, 0.2]).astype(np.int8)
    return g, {"a": a, "b": b}, click_actions(n, n)


def gen_push(rng):
    H, W = int(rng.integers(8, 12)), int(rng.integers(8, 12))
    w, a, b = _roles(rng, 3)
    g = _room(rng, H, W, w, 0.08)
    _place(rng, g, a, 1)
    _place(rng, g, b, int(rng.integers(4, 8)))
    return g, {"actor": a, "box": b}, DIR_ACTIONS


def gen_energy(rng):
    H, W = int(rng.integers(8, 11)), int(rng.integers(9, 13))
    w, a, e, o = _roles(rng, 4)
    g = np.zeros((H + 1, W), np.int8)
    g[1:] = _room(rng, H, W, w, 0.15)
    g[0, :] = o
    g[0, 1:W - 1] = e
    _place(rng, g, a, 1)
    return g, {"actor": a, "lit": e, "off": o}, DIR_ACTIONS


def gen_ice(rng):
    H, W = int(rng.integers(8, 12)), int(rng.integers(8, 12))
    w, a, r = _roles(rng, 3)
    g = _room(rng, H, W, w, 0.06)
    _place(rng, g, r, int(rng.integers(4, 9)))
    _place(rng, g, a, 1)
    return g, {"actor": a}, DIR_ACTIONS


def gen_lights(rng):
    n = int(rng.integers(5, 8))
    a, b = _roles(rng, 2)
    g = np.where(rng.random((n, n)) < 0.5, a, b).astype(np.int8)
    return g, {"a": a, "b": b}, click_actions(n, n)


def gen_flood(rng):
    n = int(rng.integers(6, 9))
    k = int(rng.integers(3, 6))
    cols = np.array(_roles(rng, k), np.int8)
    g = rng.choice(cols, size=(n, n)).astype(np.int8)
    return g, {}, click_actions(n, n)


def gen_gravity(rng):
    H, W = int(rng.integers(8, 12)), int(rng.integers(8, 12))
    w, a, r = _roles(rng, 3)
    g = _room(rng, H, W, w, 0.07)
    _place(rng, g, a, 1)
    _place(rng, g, r, int(rng.integers(5, 10)))
    return g, {"actor": a, "rock": r}, DIR_ACTIONS


def gen_trail(rng):
    H, W = int(rng.integers(8, 12)), int(rng.integers(8, 12))
    w, a, p = _roles(rng, 3)
    g = _room(rng, H, W, w, 0.12)
    _place(rng, g, a, 1)
    return g, {"actor": a, "paint": p}, DIR_ACTIONS


def gen_merge(rng):
    H, W = int(rng.integers(8, 12)), int(rng.integers(8, 12))
    w, a, m = _roles(rng, 3)
    g = _room(rng, H, W, w, 0.08)
    _place(rng, g, a, 1)
    _place(rng, g, m, int(rng.integers(5, 9)))
    return g, {"wall": w, "actor": a, "piece": m}, DIR_ACTIONS


def gen_wrap(rng):
    H, W = int(rng.integers(6, 9)), int(rng.integers(6, 9))
    w, a = _roles(rng, 2)
    g = _room(rng, H, W, w, 0.15, border=False)
    _place(rng, g, a, 1)
    return g, {"actor": a}, DIR_ACTIONS


# ---------------------------------------------------------------- dynamics: (grid, action, params) -> next grid
def _step_into(g, a, actor, free):
    """Single-cell actor steps by DIRS[a] if the target is inside the grid and its colour is in `free`."""
    p = _actor(g, actor)
    dy, dx = DIRS[a]
    y, x = p[0] + dy, p[1] + dx
    if 0 <= y < g.shape[0] and 0 <= x < g.shape[1] and int(g[y, x]) in free:
        g[p] = 0
        g[y, x] = actor
        return True
    return False


def step_maze(g, a, p):
    g = g.copy()
    _step_into(g, a, p["actor"], (0,))
    return g


def step_toggle(g, a, p):
    g = g.copy()
    y, x = parse_click(a)
    if g[y, x] == p["a"]:
        g[y, x] = p["b"]
    elif g[y, x] == p["b"]:
        g[y, x] = p["a"]
    return g


def step_push(g, a, p):
    g = g.copy()
    ay, ax = _actor(g, p["actor"])
    dy, dx = DIRS[a]
    ty, tx = ay + dy, ax + dx
    if g[ty, tx] == 0:
        g[ay, ax], g[ty, tx] = 0, p["actor"]
    elif g[ty, tx] == p["box"] and g[ty + dy, tx + dx] == 0:
        g[ty + dy, tx + dx] = p["box"]
        g[ay, ax], g[ty, tx] = 0, p["actor"]
    return g


def step_energy(g, a, p):
    g = g.copy()
    _step_into(g, a, p["actor"], (0,))
    lit = np.flatnonzero(g[0] == p["lit"])
    if len(lit):
        g[0, lit[-1]] = p["off"]
    return g


def step_ice(g, a, p):
    g = g.copy()
    while _step_into(g, a, p["actor"], (0,)):
        pass
    return g


def step_lights(g, a, p):
    g = g.copy()
    y, x = parse_click(a)
    for yy, xx in ((y, x), (y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
        if 0 <= yy < g.shape[0] and 0 <= xx < g.shape[1]:
            g[yy, xx] = p["b"] if g[yy, xx] == p["a"] else p["a"]
    return g


def _component(g, y, x):
    c, H, W = g[y, x], g.shape[0], g.shape[1]
    seen, stack = {(y, x)}, [(y, x)]
    while stack:
        cy, cx = stack.pop()
        for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
            if 0 <= ny < H and 0 <= nx < W and (ny, nx) not in seen and g[ny, nx] == c:
                seen.add((ny, nx))
                stack.append((ny, nx))
    return seen


def step_flood(g, a, p):
    g = g.copy()
    y, x = parse_click(a)
    c = g[y, x]
    if c != g[0, 0]:
        for cy, cx in _component(g, 0, 0):
            g[cy, cx] = c
    return g


def step_gravity(g, a, p):
    g = g.copy()
    _step_into(g, a, p["actor"], (0,))
    r = p["rock"]
    for y in range(g.shape[0] - 2, -1, -1):
        for x in range(g.shape[1]):
            if g[y, x] == r and g[y + 1, x] == 0:
                g[y + 1, x], g[y, x] = r, 0
    return g


def step_trail(g, a, p):
    g = g.copy()
    ay, ax = _actor(g, p["actor"])
    if _step_into(g, a, p["actor"], (0, p["paint"])):
        g[ay, ax] = p["paint"]
    return g


def step_merge(g, a, p):
    g = g.copy()
    act, H, W = p["actor"], g.shape[0], g.shape[1]
    dy, dx = DIRS[a]
    body = [tuple(q) for q in np.argwhere(g == act)]
    bs = set(body)
    tg = [(y + dy, x + dx) for y, x in body]
    if any(not (0 <= y < H and 0 <= x < W) or g[y, x] == p["wall"] for y, x in tg):
        return g
    hit = [(y, x) for y, x in tg if (y, x) not in bs and g[y, x] == p["piece"]]
    if hit:
        for y, x in hit:
            for cy, cx in _component(g, y, x):
                g[cy, cx] = act
        return g
    if all(g[y, x] == 0 or (y, x) in bs for y, x in tg):
        for y, x in body:
            g[y, x] = 0
        for y, x in tg:
            g[y, x] = act
    return g


def step_wrap(g, a, p):
    g = g.copy()
    ay, ax = _actor(g, p["actor"])
    dy, dx = DIRS[a]
    ty, tx = (ay + dy) % g.shape[0], (ax + dx) % g.shape[1]
    if g[ty, tx] == 0:
        g[ay, ax], g[ty, tx] = 0, p["actor"]
    return g


GEN = {f: globals()["gen_" + f] for f in FAMILIES}
STEP = {f: globals()["step_" + f] for f in FAMILIES}


class Env:
    """One instance: a family and an integer seed define the layout, the role colours and the action set."""

    def __init__(self, family, seed):
        self.family, self.seed = family, int(seed)
        rng = np.random.default_rng([abs(hash_name(family)), self.seed])
        self.g0, self.params, self.actions = GEN[family](rng)

    def step(self, g, a):
        return STEP[self.family](g, a, self.params)


def hash_name(s):
    """A stable integer from a name (Python's hash() is salted per process, so it is not used)."""
    v = 0
    for ch in s.encode():
        v = (v * 131 + ch) % 2147483647
    return v


def rollout(env, g, n, rng):
    """n transitions under uniformly random actions from grid g: [(g_before, action, g_after)]."""
    out = []
    for _ in range(n):
        a = env.actions[int(rng.integers(len(env.actions)))]
        g2 = env.step(g, a)
        out.append((g, a, g2))
        g = g2
    return out
