"""T4 world-model probe, collection kernel (private Kaggle CPU kernel; development games only).

The kernel:
1. builds an isolated Python 3.12 environment in /tmp;
2. installs the MIT toolkit and engine (arc-agi 0.9.9, arcengine 0.9.3);
3. lists the public ARC-AGI-3 games through the toolkit's anonymous route, with logging silenced so that no key is
   ever printed;
4. splits the games by the hash rule fixed in DESIGN_NOTE.md (the salt is the design-note commit);
5. records random-action transitions for the DEVELOPMENT games only.

Version 2 adds the analysis stage: the study's own code (wm/*.py, embedded below by kernel/build.py) runs the five
arms on the development items inside the kernel, so every number is tied to this kernel's slug and version.
It writes only data (npz arrays and JSON summaries) to /kaggle/working/t4_out. Game code stays in /tmp. Before
exiting, every output file is checked for the key string. No competition data source is attached, no rules are
accepted and nothing is submitted.
"""
import os
import re
import subprocess
import sys
import textwrap

SALT = "989cb0ca9c21811144356d83955cae5ca76ec6c6"
MODE = "held"          # "dev": collect and analyse development games; "held": held games (only after the GO)
OUT = "/kaggle/working/t4_out"
VENV = "/tmp/t4venv"

WM_SOURCES = {"__init__.py": "", "envs.py": "\"\"\"Eleven public rule sets as deterministic grid simulators, written here from the published rules (not the original\ncode; running downloaded game code was not permitted in this study). Every simulator is a pure function of the visible\ngrid and the action, so the next frame is fully determined by what the learner sees.\n\nEach instance draws its own layout and its own colour for every role, so a learner cannot rely on fixed colours.\nActions follow the ARC-AGI-3 convention: four directional actions (ACTION1..4, written U, D, L, R) or a click on a\ncell (ACTION6 with coordinates, written \"C:y:x\").\n\n| family  | public rule set it follows                                    | rule in one line                                  |\n|---------|----------------------------------------------------------------|---------------------------------------------------|\n| maze    | ARCEngine example `simple_maze` (MIT)                          | the actor steps into background; anything blocks  |\n| toggle  | click-to-toggle cell puzzles                                   | a click swaps colour a and b on the clicked cell  |\n| push    | Sokoban movement and pushing (goal squares omitted)            | a box ahead moves on if the cell beyond is free   |\n| energy  | ARCEngine example `complex_maze`, its energy bar (MIT)          | maze moves; every action switches off one bar cell |\n| ice     | ice-sliding puzzles                                            | the actor slides until the next cell is not free  |\n| lights  | Lights Out                                                     | a click toggles the cell and its 4 neighbours     |\n| flood   | Flood-It (colour picked by clicking a cell)                    | the top-left region takes the clicked cell colour |\n| gravity | falling rocks as in Boulder Dash                               | after the move, each unsupported rock falls 1     |\n| trail   | trail-painting puzzles                                         | the cell the actor leaves becomes paint           |\n| merge   | ARCEngine example `merge` (MIT), adapted (see below)           | a piece the actor bumps into joins the actor      |\n| wrap    | wrap-around edges as in Pac-Man tunnels                        | moves off one edge re-enter at the opposite edge  |\n\nAdaptations, stated plainly: `maze` exits block instead of ending the level; `energy` keeps playing when the bar is\nempty (no game over); `merge` shows a joined piece in the actor's colour and the joining step does not move (in the\noriginal the joined body moves at once and keeps the piece's colour, which a frame does not show).\n\"\"\"\nimport numpy as np\n\nDIRS = {\"U\": (-1, 0), \"D\": (1, 0), \"L\": (0, -1), \"R\": (0, 1)}\nDIR_ACTIONS = [\"U\", \"D\", \"L\", \"R\"]\nFAMILIES = [\"maze\", \"toggle\", \"push\", \"energy\", \"ice\", \"lights\", \"flood\", \"gravity\", \"trail\", \"merge\", \"wrap\"]\n\n\ndef click_actions(H, W):\n    return [f\"C:{y}:{x}\" for y in range(H) for x in range(W)]\n\n\ndef parse_click(a):\n    _, y, x = a.split(\":\")\n    return int(y), int(x)\n\n\ndef _roles(rng, n):\n    return [int(c) for c in rng.choice(np.arange(1, 10), size=n, replace=False)]\n\n\ndef _room(rng, H, W, wall, density, border=True):\n    g = np.zeros((H, W), np.int8)\n    m = rng.random((H, W)) < density\n    if border:\n        m[0, :] = m[-1, :] = m[:, 0] = m[:, -1] = True\n    g[m] = wall\n    return g\n\n\ndef _place(rng, g, colour, n):\n    free = np.argwhere(g == 0)\n    idx = rng.choice(len(free), size=n, replace=False)\n    for y, x in free[idx]:\n        g[y, x] = colour\n\n\ndef _actor(g, a):\n    p = np.argwhere(g == a)\n    return (int(p[0][0]), int(p[0][1])) if len(p) else None\n\n\n# ---------------------------------------------------------------- generators: rng -> (grid, params, actions)\ndef gen_maze(rng):\n    H, W = int(rng.integers(8, 12)), int(rng.integers(8, 12))\n    w, a, x = _roles(rng, 3)\n    g = _room(rng, H, W, w, 0.18)\n    _place(rng, g, a, 1)\n    _place(rng, g, x, 1)\n    return g, {\"wall\": w, \"actor\": a, \"exit\": x}, DIR_ACTIONS\n\n\ndef gen_toggle(rng):\n    n = int(rng.integers(5, 8))\n    a, b, c = _roles(rng, 3)\n    g = rng.choice(np.array([a, b, c], np.int8), size=(n, n), p=[0.4, 0.4, 0.2]).astype(np.int8)\n    return g, {\"a\": a, \"b\": b}, click_actions(n, n)\n\n\ndef gen_push(rng):\n    H, W = int(rng.integers(8, 12)), int(rng.integers(8, 12))\n    w, a, b = _roles(rng, 3)\n    g = _room(rng, H, W, w, 0.08)\n    _place(rng, g, a, 1)\n    _place(rng, g, b, int(rng.integers(4, 8)))\n    return g, {\"actor\": a, \"box\": b}, DIR_ACTIONS\n\n\ndef gen_energy(rng):\n    H, W = int(rng.integers(8, 11)), int(rng.integers(9, 13))\n    w, a, e, o = _roles(rng, 4)\n    g = np.zeros((H + 1, W), np.int8)\n    g[1:] = _room(rng, H, W, w, 0.15)\n    g[0, :] = o\n    g[0, 1:W - 1] = e\n    _place(rng, g, a, 1)\n    return g, {\"actor\": a, \"lit\": e, \"off\": o}, DIR_ACTIONS\n\n\ndef gen_ice(rng):\n    H, W = int(rng.integers(8, 12)), int(rng.integers(8, 12))\n    w, a, r = _roles(rng, 3)\n    g = _room(rng, H, W, w, 0.06)\n    _place(rng, g, r, int(rng.integers(4, 9)))\n    _place(rng, g, a, 1)\n    return g, {\"actor\": a}, DIR_ACTIONS\n\n\ndef gen_lights(rng):\n    n = int(rng.integers(5, 8))\n    a, b = _roles(rng, 2)\n    g = np.where(rng.random((n, n)) < 0.5, a, b).astype(np.int8)\n    return g, {\"a\": a, \"b\": b}, click_actions(n, n)\n\n\ndef gen_flood(rng):\n    n = int(rng.integers(6, 9))\n    k = int(rng.integers(3, 6))\n    cols = np.array(_roles(rng, k), np.int8)\n    g = rng.choice(cols, size=(n, n)).astype(np.int8)\n    return g, {}, click_actions(n, n)\n\n\ndef gen_gravity(rng):\n    H, W = int(rng.integers(8, 12)), int(rng.integers(8, 12))\n    w, a, r = _roles(rng, 3)\n    g = _room(rng, H, W, w, 0.07)\n    _place(rng, g, a, 1)\n    _place(rng, g, r, int(rng.integers(5, 10)))\n    return g, {\"actor\": a, \"rock\": r}, DIR_ACTIONS\n\n\ndef gen_trail(rng):\n    H, W = int(rng.integers(8, 12)), int(rng.integers(8, 12))\n    w, a, p = _roles(rng, 3)\n    g = _room(rng, H, W, w, 0.12)\n    _place(rng, g, a, 1)\n    return g, {\"actor\": a, \"paint\": p}, DIR_ACTIONS\n\n\ndef gen_merge(rng):\n    H, W = int(rng.integers(8, 12)), int(rng.integers(8, 12))\n    w, a, m = _roles(rng, 3)\n    g = _room(rng, H, W, w, 0.08)\n    _place(rng, g, a, 1)\n    _place(rng, g, m, int(rng.integers(5, 9)))\n    return g, {\"wall\": w, \"actor\": a, \"piece\": m}, DIR_ACTIONS\n\n\ndef gen_wrap(rng):\n    H, W = int(rng.integers(6, 9)), int(rng.integers(6, 9))\n    w, a = _roles(rng, 2)\n    g = _room(rng, H, W, w, 0.15, border=False)\n    _place(rng, g, a, 1)\n    return g, {\"actor\": a}, DIR_ACTIONS\n\n\n# ---------------------------------------------------------------- dynamics: (grid, action, params) -> next grid\ndef _step_into(g, a, actor, free):\n    \"\"\"Single-cell actor steps by DIRS[a] if the target is inside the grid and its colour is in `free`.\"\"\"\n    p = _actor(g, actor)\n    dy, dx = DIRS[a]\n    y, x = p[0] + dy, p[1] + dx\n    if 0 <= y < g.shape[0] and 0 <= x < g.shape[1] and int(g[y, x]) in free:\n        g[p] = 0\n        g[y, x] = actor\n        return True\n    return False\n\n\ndef step_maze(g, a, p):\n    g = g.copy()\n    _step_into(g, a, p[\"actor\"], (0,))\n    return g\n\n\ndef step_toggle(g, a, p):\n    g = g.copy()\n    y, x = parse_click(a)\n    if g[y, x] == p[\"a\"]:\n        g[y, x] = p[\"b\"]\n    elif g[y, x] == p[\"b\"]:\n        g[y, x] = p[\"a\"]\n    return g\n\n\ndef step_push(g, a, p):\n    g = g.copy()\n    ay, ax = _actor(g, p[\"actor\"])\n    dy, dx = DIRS[a]\n    ty, tx = ay + dy, ax + dx\n    if g[ty, tx] == 0:\n        g[ay, ax], g[ty, tx] = 0, p[\"actor\"]\n    elif g[ty, tx] == p[\"box\"] and g[ty + dy, tx + dx] == 0:\n        g[ty + dy, tx + dx] = p[\"box\"]\n        g[ay, ax], g[ty, tx] = 0, p[\"actor\"]\n    return g\n\n\ndef step_energy(g, a, p):\n    g = g.copy()\n    _step_into(g, a, p[\"actor\"], (0,))\n    lit = np.flatnonzero(g[0] == p[\"lit\"])\n    if len(lit):\n        g[0, lit[-1]] = p[\"off\"]\n    return g\n\n\ndef step_ice(g, a, p):\n    g = g.copy()\n    while _step_into(g, a, p[\"actor\"], (0,)):\n        pass\n    return g\n\n\ndef step_lights(g, a, p):\n    g = g.copy()\n    y, x = parse_click(a)\n    for yy, xx in ((y, x), (y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):\n        if 0 <= yy < g.shape[0] and 0 <= xx < g.shape[1]:\n            g[yy, xx] = p[\"b\"] if g[yy, xx] == p[\"a\"] else p[\"a\"]\n    return g\n\n\ndef _component(g, y, x):\n    c, H, W = g[y, x], g.shape[0], g.shape[1]\n    seen, stack = {(y, x)}, [(y, x)]\n    while stack:\n        cy, cx = stack.pop()\n        for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):\n            if 0 <= ny < H and 0 <= nx < W and (ny, nx) not in seen and g[ny, nx] == c:\n                seen.add((ny, nx))\n                stack.append((ny, nx))\n    return seen\n\n\ndef step_flood(g, a, p):\n    g = g.copy()\n    y, x = parse_click(a)\n    c = g[y, x]\n    if c != g[0, 0]:\n        for cy, cx in _component(g, 0, 0):\n            g[cy, cx] = c\n    return g\n\n\ndef step_gravity(g, a, p):\n    g = g.copy()\n    _step_into(g, a, p[\"actor\"], (0,))\n    r = p[\"rock\"]\n    for y in range(g.shape[0] - 2, -1, -1):\n        for x in range(g.shape[1]):\n            if g[y, x] == r and g[y + 1, x] == 0:\n                g[y + 1, x], g[y, x] = r, 0\n    return g\n\n\ndef step_trail(g, a, p):\n    g = g.copy()\n    ay, ax = _actor(g, p[\"actor\"])\n    if _step_into(g, a, p[\"actor\"], (0, p[\"paint\"])):\n        g[ay, ax] = p[\"paint\"]\n    return g\n\n\ndef step_merge(g, a, p):\n    g = g.copy()\n    act, H, W = p[\"actor\"], g.shape[0], g.shape[1]\n    dy, dx = DIRS[a]\n    body = [tuple(q) for q in np.argwhere(g == act)]\n    bs = set(body)\n    tg = [(y + dy, x + dx) for y, x in body]\n    if any(not (0 <= y < H and 0 <= x < W) or g[y, x] == p[\"wall\"] for y, x in tg):\n        return g\n    hit = [(y, x) for y, x in tg if (y, x) not in bs and g[y, x] == p[\"piece\"]]\n    if hit:\n        for y, x in hit:\n            for cy, cx in _component(g, y, x):\n                g[cy, cx] = act\n        return g\n    if all(g[y, x] == 0 or (y, x) in bs for y, x in tg):\n        for y, x in body:\n            g[y, x] = 0\n        for y, x in tg:\n            g[y, x] = act\n    return g\n\n\ndef step_wrap(g, a, p):\n    g = g.copy()\n    ay, ax = _actor(g, p[\"actor\"])\n    dy, dx = DIRS[a]\n    ty, tx = (ay + dy) % g.shape[0], (ax + dx) % g.shape[1]\n    if g[ty, tx] == 0:\n        g[ay, ax], g[ty, tx] = 0, p[\"actor\"]\n    return g\n\n\nGEN = {f: globals()[\"gen_\" + f] for f in FAMILIES}\nSTEP = {f: globals()[\"step_\" + f] for f in FAMILIES}\n\n\nclass Env:\n    \"\"\"One instance: a family and an integer seed define the layout, the role colours and the action set.\"\"\"\n\n    def __init__(self, family, seed):\n        self.family, self.seed = family, int(seed)\n        rng = np.random.default_rng([abs(hash_name(family)), self.seed])\n        self.g0, self.params, self.actions = GEN[family](rng)\n\n    def step(self, g, a):\n        return STEP[self.family](g, a, self.params)\n\n\ndef hash_name(s):\n    \"\"\"A stable integer from a name (Python's hash() is salted per process, so it is not used).\"\"\"\n    v = 0\n    for ch in s.encode():\n        v = (v * 131 + ch) % 2147483647\n    return v\n\n\ndef rollout(env, g, n, rng):\n    \"\"\"n transitions under uniformly random actions from grid g: [(g_before, action, g_after)].\"\"\"\n    out = []\n    for _ in range(n):\n        a = env.actions[int(rng.integers(len(env.actions)))]\n        g2 = env.step(g, a)\n        out.append((g, a, g2))\n        g = g2\n    return out\n", "model.py": "\"\"\"The rule language for world models: a model maps (grid, action) to the predicted next grid.\n\nThe STATIC language (the base, L0) has three rules:\n  * Move: on a directional action, every cell of the actor's colour(s) shifts by the action's displacement when every\n    target cell is inside the grid and its colour is passable (or is part of the actor); the cells left behind become\n    background. Parameters: actor colours, a displacement per action, the passable colours.\n  * ClickMap: on a click, the clicked cell's colour u becomes clickmap[u] (unlisted colours stay).\n  * Everything else stays as it was.\n\nGROWN pieces are compositions of one selector, one effect and one trigger (see SKELETONS in induce.py), plus two\nrepresentation switches on Move (slide: repeat the step until blocked; wrap: the grid is a torus).\n\"\"\"\nfrom collections import namedtuple\n\nimport numpy as np\n\nfrom wm.envs import DIRS, parse_click\n\nPiece = namedtuple(\"Piece\", \"sel theta eff psi trig when\")\nN4 = ((-1, 0), (1, 0), (0, -1), (0, 1))\nN8 = N4 + ((-1, -1), (-1, 1), (1, -1), (1, 1))\nUNIT = ((-1, 0), (1, 0), (0, -1), (0, 1))\n\n\nclass Model:\n    __slots__ = (\"bg\", \"actor\", \"delta\", \"passable\", \"slide\", \"wrap\", \"clickmap\", \"pre\", \"post\")\n\n    def __init__(self, bg, actor=()):\n        self.bg, self.actor = int(bg), tuple(actor)\n        self.delta, self.passable, self.clickmap = {}, frozenset([int(bg)]), {}\n        self.slide = self.wrap = False\n        self.pre, self.post = (), ()\n\n    def copy(self):\n        m = Model(self.bg, self.actor)\n        m.delta, m.passable, m.clickmap = dict(self.delta), self.passable, dict(self.clickmap)\n        m.slide, m.wrap, m.pre, m.post = self.slide, self.wrap, self.pre, self.post\n        return m\n\n    def with_piece(self, p):\n        m = self.copy()\n        if p.sel == \"slide\":\n            m.slide = True\n        elif p.sel == \"wrap\":\n            m.wrap = True\n        elif p.when == \"pre\":\n            m.pre = self.pre + (p,)\n        else:\n            m.post = self.post + (p,)\n        return m\n\n    def size(self):\n        return len(self.pre) + len(self.post) + int(self.slide) + int(self.wrap)\n\n    def describe(self):\n        return {\"bg\": self.bg, \"actor\": list(self.actor),\n                \"delta\": {a: list(v) for a, v in sorted(self.delta.items())},\n                \"passable\": sorted(self.passable), \"slide\": self.slide, \"wrap\": self.wrap,\n                \"clickmap\": {str(k): v for k, v in sorted(self.clickmap.items())},\n                \"pieces\": [describe_piece(p) for p in self.pre + self.post]}\n\n\ndef describe_piece(p):\n    psi = p.psi if not isinstance(p.psi, tuple) or not p.psi or not isinstance(p.psi[0], tuple) else \\\n        [list(x) for x in p.psi]\n    return {\"sel\": p.sel, \"theta\": p.theta, \"eff\": p.eff, \"psi\": psi, \"trig\": p.trig, \"when\": p.when}\n\n\ndef _component(g, y, x):\n    c, H, W = g[y, x], g.shape[0], g.shape[1]\n    seen, stack = {(y, x)}, [(y, x)]\n    while stack:\n        cy, cx = stack.pop()\n        for dy, dx in N4:\n            ny, nx = cy + dy, cx + dx\n            if 0 <= ny < H and 0 <= nx < W and (ny, nx) not in seen and g[ny, nx] == c:\n                seen.add((ny, nx))\n                stack.append((ny, nx))\n    return seen\n\n\ndef body_of(m, g):\n    \"\"\"The actor's cells as two index arrays (rows, columns).\"\"\"\n    if not m.actor:\n        return np.empty(0, np.int64), np.empty(0, np.int64)\n    return np.nonzero(g == m.actor[0]) if len(m.actor) == 1 else np.nonzero(np.isin(g, m.actor))\n\n\ndef _target(m, y, x, d, H, W):\n    ny, nx = y + d[0], x + d[1]\n    if m.wrap:\n        return ny % H, nx % W\n    return (ny, nx) if 0 <= ny < H and 0 <= nx < W else None\n\n\ndef trig_ok(trig, a):\n    return trig == \"any\" or (trig == \"dir\" and a[0] != \"C\") or (trig == \"click\" and a[0] == \"C\")\n\n\ndef select(p, m, g0, g1, a, ctx):\n    \"\"\"Cells chosen by piece p's selector. Pre pieces read the grid before the step; post pieces read the current\n    grid for colour-based selectors and the grid before the step for region selectors.\"\"\"\n    s, H, W = p.sel, g0.shape[0], g0.shape[1]\n    if s == \"ahead\":\n        d = m.delta.get(a)\n        if not d or d == (0, 0):\n            return set()\n        body = ctx.get(\"body\")\n        if body is None:\n            body = ctx[\"body\"] = body_of(m, g0)\n        ys, xs = body\n        if not len(ys):\n            return set()\n        ty, tx = ys + d[0], xs + d[1]\n        if m.wrap:\n            ty, tx = ty % H, tx % W\n        else:\n            k = (ty >= 0) & (ty < H) & (tx >= 0) & (tx < W)\n            ty, tx = ty[k], tx[k]\n        bm = np.zeros((H, W), bool)\n        bm[ys, xs] = True\n        k = (~bm[ty, tx]) & (g0[ty, tx] == p.theta[0])\n        out = set()\n        for y, x in zip(ty[k].tolist(), tx[k].tolist()):\n            if (y, x) not in out:\n                out |= _component(g0, y, x) if p.theta[1] else {(y, x)}\n        return out\n    if s == \"vacated\":\n        return ctx.get(\"vacated\", set())\n    if s in (\"click_n4\", \"click_n8\", \"click_region\"):\n        y, x = parse_click(a)\n        if s == \"click_region\":\n            return _component(g0, y, x)\n        return {(y + dy, x + dx) for dy, dx in (N4 if s == \"click_n4\" else N8)\n                if 0 <= y + dy < H and 0 <= x + dx < W}\n    if s == \"corner_region\":\n        cy, cx = ((0, 0), (0, W - 1), (H - 1, 0), (H - 1, W - 1))[p.theta]\n        return _component(g0, cy, cx)\n    if s == \"first\":\n        c, order = p.theta\n        src = g1 if p.when == \"post\" else g0\n        idx = np.flatnonzero((src if order < 2 else src.T) == c)\n        if not len(idx):\n            return set()\n        k = int(idx[0] if order % 2 == 0 else idx[-1])\n        if order < 2:\n            return {(k // W, k % W)}\n        return {(k % H, k // H)}\n    if s == \"all\":\n        c = p.theta[0] if isinstance(p.theta, tuple) else p.theta\n        src = g1 if p.when == \"post\" else g0\n        return {tuple(q) for q in np.argwhere(src == c)}\n    raise ValueError(s)\n\n\ndef apply_piece(p, m, g0, g1, a, ctx):\n    if not trig_ok(p.trig, a):\n        return\n    cells = select(p, m, g0, g1, a, ctx)\n    if not cells:\n        return\n    e, H, W = p.eff, g0.shape[0], g0.shape[1]\n    if e == \"recolour_to\":\n        for q in cells:\n            g1[q] = p.psi\n    elif e == \"recolour_map\":\n        mp = dict(p.psi)\n        for q in cells:\n            v = mp.get(int(g1[q]))\n            if v is not None:\n                g1[q] = v\n    elif e == \"recolour_to_clicked\":\n        y, x = parse_click(a)\n        c = g0[y, x]\n        for q in cells:\n            g1[q] = c\n    elif e == \"shift_action\":\n        d = m.delta.get(a)\n        if not d or d == (0, 0):\n            return\n        dest = []\n        for y, x in cells:\n            t = _target(m, y, x, d, H, W)\n            if t is None:\n                return\n            dest.append(t)\n        if all(g1[t] == m.bg or t in cells for t in dest):\n            vals = [g1[q] for q in cells]\n            for q in cells:\n                g1[q] = m.bg\n            for t, v in zip(dest, vals):\n                g1[t] = v\n    elif e == \"shift_fixed\":\n        dy, dx = p.theta[1]\n        for y, x in sorted(cells, key=lambda q: -(q[0] * dy + q[1] * dx)):\n            ny, nx = y + dy, x + dx\n            if 0 <= ny < H and 0 <= nx < W and g1[ny, nx] == m.bg and g1[y, x] != m.bg:\n                g1[ny, nx], g1[y, x] = g1[y, x], m.bg\n    else:\n        raise ValueError(e)\n\n\ndef move(m, g0, g1, a, ctx):\n    d = m.delta.get(a)\n    if not d or d == (0, 0):\n        return\n    H, W = g0.shape\n    body = ctx.get(\"body\")\n    if body is None:\n        body = ctx[\"body\"] = body_of(m, g0)\n    ys, xs = body\n    if not len(ys):\n        return\n    pas = np.fromiter(m.passable, dtype=g1.dtype, count=len(m.passable))\n    cy, cx, moved = ys, xs, False\n    for _ in range(max(H, W) if m.slide else 1):\n        ty, tx = cy + d[0], cx + d[1]\n        if m.wrap:\n            ty, tx = ty % H, tx % W\n        elif ((ty < 0) | (ty >= H) | (tx < 0) | (tx >= W)).any():\n            break\n        inb = np.zeros((H, W), bool)\n        inb[cy, cx] = True\n        if not (np.isin(g1[ty, tx], pas) | inb[ty, tx]).all():\n            break\n        vals = g1[cy, cx].copy()\n        g1[cy, cx] = m.bg\n        g1[ty, tx] = vals\n        cy, cx, moved = ty, tx, True\n    ctx[\"vacated\"] = (set(zip(ys.tolist(), xs.tolist())) - set(zip(cy.tolist(), cx.tolist()))) if moved else set()\n    ctx[\"moved\"] = moved\n\n\ndef predict(m, g, a):\n    g1 = g.copy()\n    ctx = {}\n    for p in m.pre:\n        apply_piece(p, m, g, g1, a, ctx)\n    if a[0] != \"C\" and m.actor:\n        move(m, g, g1, a, ctx)\n    elif a[0] == \"C\" and m.clickmap:\n        y, x = parse_click(a)\n        v = m.clickmap.get(int(g[y, x]))\n        if v is not None:\n            g1[y, x] = v\n    for p in m.post:\n        apply_piece(p, m, g, g1, a, ctx)\n    return g1\n\n\ndef predict_pre(m, g, a):\n    \"\"\"The grid after the pre pieces only (used to refit the passable colours).\"\"\"\n    g1 = g.copy()\n    ctx = {}\n    for p in m.pre:\n        apply_piece(p, m, g, g1, a, ctx)\n    return g1\n", "induce.py": "\"\"\"Induction of a world model from observed transitions T = [(grid_before, action, grid_after)].\n\nstatic : fit the base language (Move + ClickMap) and stop.\ngrown  : the CORA loop. Fit the base language; check it on T; on failure describe what is missing (which kinds of\n         piece would cover the wrong cells, ranked by how well each piece's footprint matches them); build the\n         top-ranked pieces (fit their parameters on T); check again; keep a piece only if it lowers the wrong cells,\n         breaks no transition that was right, and helps on a held check (leave one transition out, refit the piece\n         without it, and it must predict that transition exactly). B pieces per round, at most R rounds.\nshuffled: the same loop, but the ranking of pieces comes from ANOTHER item's failure description (a different\n         family), so construction is not guided by this item's own failure. Checks use this item's data.\n\"\"\"\nfrom collections import Counter\n\nimport numpy as np\n\nfrom wm.envs import DIRS, parse_click\nfrom wm.model import Model, Piece, UNIT, body_of, predict, predict_pre, select, trig_ok, _target\n\nSKELETONS = [\n    (\"ahead_shift\", \"ahead\", \"shift_action\", \"dir\", \"pre\"),\n    (\"ahead_recolour_to\", \"ahead\", \"recolour_to\", \"dir\", \"pre\"),\n    (\"ahead_recolour_map\", \"ahead\", \"recolour_map\", \"dir\", \"pre\"),\n    (\"vacated_recolour_to\", \"vacated\", \"recolour_to\", \"dir\", \"post\"),\n    (\"vacated_recolour_map\", \"vacated\", \"recolour_map\", \"dir\", \"post\"),\n    (\"click_n4_recolour_map\", \"click_n4\", \"recolour_map\", \"click\", \"post\"),\n    (\"click_n4_recolour_to\", \"click_n4\", \"recolour_to\", \"click\", \"post\"),\n    (\"click_n4_recolour_to_clicked\", \"click_n4\", \"recolour_to_clicked\", \"click\", \"post\"),\n    (\"click_n8_recolour_map\", \"click_n8\", \"recolour_map\", \"click\", \"post\"),\n    (\"click_n8_recolour_to\", \"click_n8\", \"recolour_to\", \"click\", \"post\"),\n    (\"click_n8_recolour_to_clicked\", \"click_n8\", \"recolour_to_clicked\", \"click\", \"post\"),\n    (\"click_region_recolour_map\", \"click_region\", \"recolour_map\", \"click\", \"post\"),\n    (\"click_region_recolour_to\", \"click_region\", \"recolour_to\", \"click\", \"post\"),\n    (\"corner_region_recolour_map\", \"corner_region\", \"recolour_map\", \"any\", \"post\"),\n    (\"corner_region_recolour_to\", \"corner_region\", \"recolour_to\", \"any\", \"post\"),\n    (\"corner_region_recolour_to_clicked\", \"corner_region\", \"recolour_to_clicked\", \"click\", \"post\"),\n    (\"first_recolour_to\", \"first\", \"recolour_to\", \"any\", \"post\"),\n    (\"first_recolour_map\", \"first\", \"recolour_map\", \"any\", \"post\"),\n    (\"all_shift_fixed\", \"all\", \"shift_fixed\", \"any\", \"post\"),\n    (\"all_recolour_map\", \"all\", \"recolour_map\", \"any\", \"post\"),\n    (\"all_recolour_to\", \"all\", \"recolour_to\", \"any\", \"post\"),\n    (\"slide\", \"slide\", None, \"dir\", None),\n    (\"wrap\", \"wrap\", None, \"dir\", None),\n]\nSK = {s[0]: s for s in SKELETONS}\nMISSING = object()\nLOO_MAX = 5          # held checks tried per candidate piece (the first five transitions it fixes)\n\n\ndef colours_of(T):\n    \"\"\"Colours that take part in some observed change (before or after colour of a changed cell). Piece parameters\n    range over these only: a property of the observed data, the same for every arm.\"\"\"\n    s = set()\n    for g0, _, g1 in T:\n        ch = g0 != g1\n        if ch.any():\n            s.update(np.unique(g0[ch]).tolist())\n            s.update(np.unique(g1[ch]).tolist())\n    return sorted(int(c) for c in s)\n\n\ndef wrong_vec(m, T):\n    return np.array([int(np.count_nonzero(predict(m, g0, a) != g1)) for g0, a, g1 in T], dtype=np.int64)\n\n\ndef translation(A0, A1, shape):\n    if len(A0) == 0 or len(A0) != len(A1):\n        return None\n    s1 = set(map(tuple, A1.tolist()))\n    y0, x0 = int(A0[0][0]), int(A0[0][1])\n    for c in A1.tolist():\n        v = (c[0] - y0, c[1] - x0)\n        if {(int(y) + v[0], int(x) + v[1]) for y, x in A0} == s1:\n            return v\n        if {((int(y) + v[0]) % shape[0], (int(x) + v[1]) % shape[1]) for y, x in A0} == s1:\n            return v\n    return None\n\n\ndef refit_move(m, T):\n    \"\"\"Displacement per action = the most common translation of the actor; passable colours = background plus the\n    colours of cells the actor stepped into (read after the pre pieces).\"\"\"\n    if not m.actor:\n        m.delta = {}\n        return\n    cnt, moves = {}, []\n    for g0, a, g1 in T:\n        if a[0] == \"C\":\n            continue\n        A0 = np.argwhere(np.isin(g0, m.actor))\n        if len(A0) > ACTOR_MAX:\n            continue\n        v = translation(A0, np.argwhere(np.isin(g1, m.actor)), g0.shape)\n        if v is None or v == (0, 0):\n            continue\n        H, W = g0.shape\n        if m.wrap:\n            v = ((v[0] + H // 2) % H - H // 2, (v[1] + W // 2) % W - W // 2)\n        if m.slide and (v[0] == 0) != (v[1] == 0):\n            v = (int(np.sign(v[0])), int(np.sign(v[1])))\n        cnt.setdefault(a, Counter())[v] += 1\n        moves.append((g0, a, A0))\n    m.delta = {a: c.most_common(1)[0][0] for a, c in cnt.items()}\n    P = {m.bg}\n    for g0, a, A0 in moves:\n        d = m.delta[a]\n        gi = predict_pre(m, g0, a) if m.pre else g0\n        bs = set(map(tuple, A0.tolist()))\n        for y, x in bs:\n            t = _target(m, y, x, d, *g0.shape)\n            if t is not None and t not in bs:\n                P.add(int(gi[t]))\n    m.passable = frozenset(P)\n\n\ndef fit_clickmap(m, T):\n    cnt = {}\n    for g0, a, g1 in T:\n        if a[0] == \"C\":\n            y, x = parse_click(a)\n            cnt.setdefault(int(g0[y, x]), Counter())[int(g1[y, x])] += 1\n    m.clickmap = {u: c.most_common(1)[0][0] for u, c in cnt.items() if c.most_common(1)[0][0] != u}\n\n\ndef fit_static(T):\n    \"\"\"Search the base language: background among the three most frequent colours of the first grid (walls can\n    outnumber floor in small rooms), actor among the colours whose cells are seen to translate under a non-click\n    action at least once, covering at most ACTOR_MAX cells (or no actor); displacements, passable colours and the\n    click map are then fitted. Fewest wrong cells wins.\"\"\"\n    best = None\n    movers = []\n    for c in colours_of(T):\n        for g0, a, g1 in T:\n            if a[0] == \"C\" or not ((g0 == c) != (g1 == c)).any():\n                continue\n            A0 = np.argwhere(g0 == c)\n            if 0 < len(A0) <= ACTOR_MAX and translation(A0, np.argwhere(g1 == c), g0.shape) not in (None, (0, 0)):\n                movers.append(c)\n                break\n    for bg, _ in Counter(T[0][0].ravel().tolist()).most_common(3):\n        cands = [()] + [(c,) for c in movers if c != bg]\n        for act in cands:\n            m = Model(int(bg), act)\n            refit_move(m, T)\n            fit_clickmap(m, T)\n            w = int(wrong_vec(m, T).sum())\n            if best is None or w < best[0]:\n                best = (w, m)\n    return best[1]\n\n\nBIG = 1024           # colours covering more cells than this in the first observed grid are not used as objects\nACTOR_MAX = 600      # an actor candidate covers at most this many cells\n\n\ndef sizes_of(T):\n    v, c = np.unique(T[0][0], return_counts=True)\n    return {int(a): int(b) for a, b in zip(v, c)}\n\n\ndef thetas(sk, m, cols, sizes=None):\n    sel, eff = sk[1], sk[2]\n    nonbg = [c for c in cols if c != m.bg]\n    if sizes is not None and sel in (\"ahead\", \"all\"):\n        nonbg = [c for c in nonbg if sizes.get(c, 0) <= BIG]\n    if sel == \"ahead\":\n        return [(c, k) for c in nonbg if c not in m.actor for k in (0, 1)]   # k=1: the whole touched object\n    if sel == \"corner_region\":\n        return [0, 1, 2, 3]\n    if sel == \"first\":\n        return [(c, o) for c in nonbg for o in range(4)]\n    if sel == \"all\":\n        if eff == \"shift_fixed\":\n            return [(c, v) for c in nonbg if c not in m.actor for v in UNIT]\n        return nonbg\n    return [None]\n\n\ndef _post_ctx(m, g0, a):\n    \"\"\"The current model's prediction and its context (cells vacated by the move).\"\"\"\n    from wm.model import apply_piece, move\n    g1 = g0.copy()\n    ctx = {}\n    for p in m.pre:\n        apply_piece(p, m, g0, g1, a, ctx)\n    if a[0] != \"C\" and m.actor:\n        move(m, g0, g1, a, ctx)\n    elif a[0] == \"C\" and m.clickmap:\n        y, x = parse_click(a)\n        v = m.clickmap.get(int(g0[y, x]))\n        if v is not None:\n            g1[y, x] = v\n    for p in m.post:\n        apply_piece(p, m, g0, g1, a, ctx)\n    return g1, ctx\n\n\ndef footprint(sk, th, m, g0, a, gp, ctx):\n    name, sel, eff, trig, when = sk\n    if not trig_ok(trig, a):\n        return set()\n    H, W = g0.shape\n    if sel in (\"slide\", \"wrap\"):\n        d = m.delta.get(a)\n        if not d or not m.actor:\n            return set()\n        body = list(zip(*(v.tolist() for v in body_of(m, g0))))\n        out = set(body)\n        if sel == \"wrap\":\n            out |= {((y + d[0]) % H, (x + d[1]) % W) for y, x in body}\n        else:\n            u = (int(np.sign(d[0])), int(np.sign(d[1])))\n            for y, x in body:\n                ny, nx = y + u[0], x + u[1]\n                while 0 <= ny < H and 0 <= nx < W:\n                    out.add((ny, nx))\n                    ny, nx = ny + u[0], nx + u[1]\n        return out\n    if sel == \"vacated\":\n        return set(zip(*(v.tolist() for v in body_of(m, g0))))\n    cells = set(select(Piece(sel, th, eff, None, trig, when), m, g0, gp, a, dict(ctx)))\n    if eff == \"shift_action\":\n        d = m.delta.get(a)\n        if d:\n            cells |= {t for t in (_target(m, y, x, d, H, W) for y, x in cells) if t is not None}\n    elif eff == \"shift_fixed\":\n        dy, dx = th[1]\n        cells |= {(y + dy, x + dx) for y, x in cells if 0 <= y + dy < H and 0 <= x + dx < W}\n    return cells\n\n\ndef describe(m, T, cols):\n    \"\"\"The failure description: the wrong cells of the current model on T, and, for every kind of piece, how well its\n    footprint matches them (F1 of coverage and precision at its best parameter). Returns the ranked piece names.\"\"\"\n    res = []\n    for i, (g0, a, g1) in enumerate(T):\n        gp, ctx = _post_ctx(m, g0, a)\n        R = np.argwhere(gp != g1)\n        if len(R):\n            res.append((i, set(map(tuple, R.tolist())), gp, ctx))\n    total = sum(len(R) for _, R, _, _ in res)\n    if not total:\n        return [], {}\n    scores, sizes = [], sizes_of(T)\n    for k, sk in enumerate(SKELETONS):\n        best = 0.0\n        for th in thetas(sk, m, cols, sizes):\n            hit = fp = 0\n            for i, R, gp, ctx in res:\n                g0, a, _ = T[i]\n                F = footprint(sk, th, m, g0, a, gp, ctx)\n                hit += len(F & R)\n                fp += len(F)\n            if hit:\n                cov, prec = hit / total, hit / fp\n                best = max(best, 2 * cov * prec / (cov + prec))\n        if best > 0:\n            scores.append((-best, k, sk[0]))\n    scores.sort()\n    return [n for _, _, n in scores], {n: round(-s, 4) for s, _, n in scores}\n\n\ndef estimate_psi(sk, th, m, T, cache):\n    name, sel, eff, trig, when = sk\n    if eff in (\"shift_action\", \"shift_fixed\", \"recolour_to_clicked\"):\n        return None\n    pairs = []\n    for i, (g0, a, g1) in enumerate(T):\n        if not trig_ok(trig, a):\n            continue\n        gp, ctx = cache[i]\n        src = gp if when == \"post\" else g0\n        for q in select(Piece(sel, th, eff, None, trig, when), m, g0, gp, a, dict(ctx)):\n            pairs.append((int(src[q]), int(g1[q])))\n    if eff == \"recolour_to\":\n        ch = Counter(w for u, w in pairs if w != u)\n        return ch.most_common(1)[0][0] if ch else MISSING\n    per = {}\n    for u, w in pairs:\n        per.setdefault(u, Counter())[w] += 1\n    mp = tuple(sorted((u, c.most_common(1)[0][0]) for u, c in per.items() if c.most_common(1)[0][0] != u))\n    return mp if mp else MISSING\n\n\ndef fit_skeleton(sk, m, T, cols):\n    \"\"\"Best parameters of one kind of piece on T: (model with the piece, wrong cells per transition, piece).\"\"\"\n    name, sel, eff, trig, when = sk\n    if sel in (\"slide\", \"wrap\"):\n        if getattr(m, sel):\n            return None\n        m2 = m.copy()\n        setattr(m2, sel, True)\n        refit_move(m2, T)\n        return m2, wrong_vec(m2, T), Piece(sel, None, None, None, trig, None)\n    cache = [_post_ctx(m, g0, a) for g0, a, _ in T]\n    best, sizes = None, sizes_of(T)\n    for th in thetas(sk, m, cols, sizes):\n        psi = estimate_psi(sk, th, m, T, cache)\n        if psi is MISSING:\n            continue\n        p = Piece(sel, th, eff, psi, trig, when)\n        m2 = m.with_piece(p)\n        if when == \"pre\":\n            refit_move(m2, T)\n        w = wrong_vec(m2, T)\n        if best is None or w.sum() < best[1].sum():\n            best = (m2, w, p)\n    return best\n\n\ndef refit_all(m, T):\n    m = m.copy()\n    refit_move(m, T)\n    fit_clickmap(m, T)\n    return m\n\n\ndef accept(sk, m, T, cols, w_cur, fit):\n    m2, w2, p = fit\n    if w2.sum() >= w_cur.sum() or ((w_cur == 0) & (w2 > 0)).any():\n        return False\n    for t in np.flatnonzero((w_cur > 0) & (w2 == 0))[:LOO_MAX]:\n        Tm = T[:t] + T[t + 1:]\n        f = fit_skeleton(sk, refit_all(m, Tm), Tm, cols)\n        if f is not None and np.array_equal(predict(f[0], T[t][0], T[t][1]), T[t][2]):\n            return True\n    return False\n\n\ndef grow(T, fixed_ranking=None, B=3, R=4):\n    \"\"\"The loop. fixed_ranking=None uses this item's own failure description (grown); a list uses a given ranking\n    (shuffled control). Returns (model, log).\"\"\"\n    m = fit_static(T)\n    cols = colours_of(T)\n    w = wrong_vec(m, T)\n    tried, log = set(), []\n    for r in range(R):\n        if w.sum() == 0:\n            break\n        if fixed_ranking is None:\n            ranking, scores = describe(m, T, cols)\n        else:\n            ranking, scores = fixed_ranking, {}\n        cands = [n for n in ranking if n not in tried][:B]\n        if not cands:\n            break\n        best = None\n        for n in cands:\n            tried.add(n)\n            f = fit_skeleton(SK[n], m, T, cols)\n            if f is not None and accept(SK[n], m, T, cols, w, f) and (best is None or f[1].sum() < best[1].sum()):\n                best = f\n        log.append({\"round\": r, \"wrong_before\": int(w.sum()), \"ranking\": ranking[:6],\n                    \"scores\": {n: scores.get(n) for n in ranking[:6]}, \"tried\": cands,\n                    \"accepted\": None if best is None else best[2].sel + (\"\" if best[2].eff is None\n                                                                          else \"_\" + best[2].eff)})\n        if best is not None:\n            m = refit_all(best[0], T)\n            w = wrong_vec(m, T)\n    return m, log\n", "arc3.py": "\"\"\"ARC-AGI-3 frames as world-model items (development probe on public games; not a score).\n\nThe input is data only: npz episodes written by the collection kernel (frames, actions, states, levels). No game\ncode is read or run here.\n\nItem = (game, episode). The first K transitions are observed and fitted; the following transitions (at most MAXTEST)\nare test transitions and are never used for fitting. The rule language runs on the frame reduced by the largest\nblock size s in {8, 4, 2, 1} at which every observed frame is constant on s-by-s blocks (chosen from observed frames\nonly); predictions are scored at full 64 x 64 resolution.\n\"\"\"\nimport glob\nimport os\nimport time\n\nimport numpy as np\n\nfrom wm.induce import colours_of, describe, fit_static, grow\nfrom wm.model import predict\n\nK, MAXTEST = 30, 50\nARMS = (\"copy_previous\", \"tabular\", \"static\", \"grown\", \"shuffled\")\n\n\ndef block_scale(frames):\n    for s in (8, 4, 2):\n        if all((f.reshape(64 // s, s, 64 // s, s) == f.reshape(64 // s, s, 64 // s, s)[:, :1, :, :1]).all()\n               for f in frames):\n            return s\n    return 1\n\n\ndef act_str(a, x, y, s):\n    return f\"C:{int(y) // s}:{int(x) // s}\" if int(a) == 6 else f\"A{int(a)}\"\n\n\ndef load_items(out_dir):\n    items = []\n    for p in sorted(glob.glob(os.path.join(out_dir, \"*_e*.npz\"))):\n        name = os.path.basename(p)[:-4]\n        game, ep = name.rsplit(\"_e\", 1)\n        z = np.load(p, allow_pickle=False)\n        F, A = z[\"frames\"].astype(np.int8), z[\"actions\"]\n        n = len(A)\n        if n < K + 1:\n            items.append({\"game\": game, \"episode\": int(ep), \"excluded\": f\"only {n} transitions\"})\n            continue\n        s = block_scale(F[:K + 1])\n        G = [f[::s, ::s].copy() for f in F]\n        acts = [act_str(a, x, y, s) for a, x, y in A]\n        items.append({\"game\": game, \"episode\": int(ep), \"s\": s, \"F\": F, \"G\": G, \"acts\": acts, \"A\": A,\n                      \"states\": z[\"states\"].tolist(), \"levels\": z[\"levels\"].tolist(),\n                      \"T\": [(G[t], acts[t], G[t + 1]) for t in range(K)],\n                      \"test\": list(range(K, min(n, K + MAXTEST)))})\n    return items\n\n\ndef up(g, s):\n    return np.repeat(np.repeat(g, s, 0), s, 1) if s > 1 else g\n\n\ndef score(item, fn):\n    \"\"\"fn(t) -> predicted full-resolution next frame for test transition t.\"\"\"\n    F, st, lv = item[\"F\"], item[\"states\"], item[\"levels\"]\n    r = {\"n\": 0, \"exact\": 0, \"changed\": 0, \"changed_ok\": 0, \"n_within\": 0, \"exact_within\": 0,\n         \"changed_within\": 0, \"changed_ok_within\": 0, \"flags\": []}\n    for t in item[\"test\"]:\n        pred, true, cur = fn(t), F[t + 1], F[t]\n        ch = true != cur\n        ok = bool(np.array_equal(pred, true))\n        nch, nok = int(ch.sum()), int((pred[ch] == true[ch]).sum())\n        r[\"n\"] += 1\n        r[\"exact\"] += ok\n        r[\"flags\"].append(int(ok))\n        r[\"changed\"] += nch\n        r[\"changed_ok\"] += nok\n        if st[t] == st[t + 1] == \"NOT_FINISHED\" and lv[t] == lv[t + 1]:\n            r[\"n_within\"] += 1\n            r[\"exact_within\"] += ok\n            r[\"changed_within\"] += nch\n            r[\"changed_ok_within\"] += nok\n    return r\n\n\ndef rank0_of(it):\n    return describe(fit_static(it[\"T\"]), it[\"T\"], colours_of(it[\"T\"]))[0]\n\n\ndef partner_ranking(it, games, rank0):\n    gi = games.index(it[\"game\"])\n    for j in range(1, len(games)):\n        r = rank0.get((games[(gi + j) % len(games)], it[\"episode\"]))\n        if r:\n            return r\n    return []\n\n\ndef item_row(it, partner, B=3, R=4):\n    F, G, s, A, acts = it[\"F\"], it[\"G\"], it[\"s\"], it[\"A\"], it[\"acts\"]\n    row = {\"game\": it[\"game\"], \"episode\": it[\"episode\"], \"scale\": s, \"n_test\": len(it[\"test\"]),\n           \"observed_changes\": sum(int((g0 != g1).any()) for g0, _, g1 in it[\"T\"])}\n    row[\"copy_previous\"] = score(it, lambda t: F[t])\n    table = {}\n    for t in range(K):\n        table[(F[t].tobytes(), tuple(int(v) for v in A[t]))] = F[t + 1]\n    row[\"tabular\"] = score(it, lambda t: table.get((F[t].tobytes(), tuple(int(v) for v in A[t])), F[t]))\n    c0 = time.process_time()\n    ms = fit_static(it[\"T\"])\n    row[\"static\"] = score(it, lambda t: up(predict(ms, G[t], acts[t]), s))\n    c1 = time.process_time()\n    mg, lg = grow(it[\"T\"], None, B, R)\n    row[\"grown\"] = score(it, lambda t: up(predict(mg, G[t], acts[t]), s))\n    c2 = time.process_time()\n    msh, lsh = grow(it[\"T\"], partner, B, R)\n    row[\"shuffled\"] = score(it, lambda t: up(predict(msh, G[t], acts[t]), s))\n    c3 = time.process_time()\n    row[\"cpu\"] = {\"static\": round(c1 - c0, 2), \"grown\": round(c2 - c1, 2), \"shuffled\": round(c3 - c2, 2)}\n    row[\"grown_log\"], row[\"shuffled_log\"] = lg, lsh\n    row[\"grown_model\"], row[\"static_model\"] = mg.describe(), ms.describe()\n    return row\n\n\ndef run_items(items, B=3, R=4):\n    live = [it for it in items if \"excluded\" not in it]\n    rank0 = {(it[\"game\"], it[\"episode\"]): rank0_of(it) for it in live}\n    games = sorted({it[\"game\"] for it in live})\n    rows = []\n    for it in live:\n        row = item_row(it, partner_ranking(it, games, rank0), B, R)\n        rows.append(row)\n        print(it[\"game\"], it[\"episode\"], \"s\", row[\"scale\"], \"test\", row[\"n_test\"],\n              {a: f'{row[a][\"exact\"]}/{row[a][\"n\"]}' for a in ARMS}, [x[\"accepted\"] for x in row[\"grown_log\"]],\n              row[\"cpu\"], flush=True)\n    return rows\n"}

ANALYSIS = textwrap.dedent(r'''
import json, os, sys, time
sys.path.insert(0, "/tmp/t4work")
from multiprocessing import Pool
from math import comb
from wm import arc3


def r0(it):
    return (it["game"], it["episode"]), arc3.rank0_of(it)


ITEM_LIMIT = 300      # wall seconds per item; an item over the limit is dropped from every arm (reported)


class Slow(Exception):
    pass


def _alarm(*_):
    raise Slow()


def one(args):
    import signal
    it, partner = args
    t = time.process_time()
    signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(ITEM_LIMIT)
    try:
        r = arc3.item_row(it, partner)
    except Slow:
        r = {"game": it["game"], "episode": it["episode"], "timeout": True}
    finally:
        signal.alarm(0)
    r["cpu_item"] = round(time.process_time() - t, 2)
    return r


def sign_p(b, c):
    n = b + c
    return 1.0 if n == 0 else min(1.0, 2 * sum(comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n)


if __name__ == "__main__":
    OUT = sys.argv[1]
    t0 = time.time()
    items = arc3.load_items(OUT)
    live = [it for it in items if "excluded" not in it]
    with Pool(4) as p:
        rank0 = dict(p.map(r0, live))
    games = sorted({it["game"] for it in live})
    with Pool(4) as p:
        allrows = p.map(one, [(it, arc3.partner_ranking(it, games, rank0)) for it in live])
    rows = [r for r in allrows if not r.get("timeout")]
    keys = [k for k in rows[0]["grown"] if k != "flags"] if rows else []
    summ = {"label": ("development probe" if sys.argv[2] == "dev" else "held run") + " on public ARC-AGI-3 games; not a score",
            "mode": sys.argv[2], "items": len(rows),
            "excluded": [(it["game"], it["episode"], it["excluded"]) for it in items if "excluded" in it],
            "arms": {a: {k: sum(r[a][k] for r in rows) for k in keys} for a in arc3.ARMS},
            "per_game": {g: {a: {k: sum(r[a][k] for r in rows if r["game"] == g) for k in ("n", "exact", "changed", "changed_ok")}
                             for a in arc3.ARMS} for g in games},
            "timeouts": [(r["game"], r["episode"]) for r in allrows if r.get("timeout")],
            "cpu_seconds_items": round(sum(r["cpu_item"] for r in allrows), 1), "wall_seconds": round(time.time() - t0, 1)}
    import numpy as np
    rng = np.random.default_rng(0)
    gl = sorted({r["game"] for r in rows})
    for x, y in (("grown", "static"), ("grown", "shuffled"), ("grown", "tabular"), ("grown", "copy_previous")):
        fx = [f for r in rows for f in r[x]["flags"]]
        fy = [f for r in rows for f in r[y]["flags"]]
        b = sum(1 for u, v in zip(fx, fy) if u and not v)
        c = sum(1 for u, v in zip(fx, fy) if v and not u)
        per = {g: (sum(sum(r[x]["flags"]) for r in rows if r["game"] == g), sum(sum(r[y]["flags"]) for r in rows if r["game"] == g),
                   sum(r[x]["n"] for r in rows if r["game"] == g)) for g in gl}
        boots = []
        for _ in range(10000):
            pick = rng.integers(len(gl), size=len(gl))
            ex = sum(per[gl[i]][0] for i in pick); ey = sum(per[gl[i]][1] for i in pick); nn = sum(per[gl[i]][2] for i in pick)
            boots.append((ex - ey) / nn if nn else 0.0)
        n_all = len(fx)
        summ[f"transitions_{x}_vs_{y}"] = {"rate_" + x: round(sum(fx) / n_all, 4), "rate_" + y: round(sum(fy) / n_all, 4),
                                           "difference": round((sum(fx) - sum(fy)) / n_all, 4),
                                           "ci95_game_bootstrap": [round(float(np.percentile(boots, 2.5)), 4),
                                                                   round(float(np.percentile(boots, 97.5)), 4)],
                                           "only_" + x: b, "only_" + y: c, "exact_mcnemar_p": sign_p(b, c),
                                           "transitions": n_all, "games": len(gl)}
    for x, y in (("grown", "static"), ("grown", "shuffled"), ("grown", "tabular"), ("grown", "copy_previous"),
                 ("static", "copy_previous")):
        for k in ("exact", "changed_ok"):
            b = sum(r[x][k] > r[y][k] for r in rows)
            c = sum(r[y][k] > r[x][k] for r in rows)
            summ[f"{x}_vs_{y}_{k}"] = {"items_" + x + "_higher": b, "items_" + y + "_higher": c, "sign_test_p": sign_p(b, c)}
    with open(os.path.join(OUT, "analysis.json"), "w") as fh:
        json.dump({"summary": summ, "rows": rows}, fh, indent=1, default=str)
    print(json.dumps({"items": summ["items"], "timeouts": summ["timeouts"], "excluded": summ["excluded"],
                      "arms": summ["arms"], "cpu_seconds_items": summ["cpu_seconds_items"],
                      "wall_seconds": summ["wall_seconds"]}))
    for k, v in summ.items():
        if "_vs_" in k:
            print(k, v)
    for g, v in summ["per_game"].items():
        print(g, {a: (v[a]["exact"], v[a]["n"], v[a]["changed_ok"], v[a]["changed"]) for a in arc3.ARMS})
''')

COLLECT = textwrap.dedent(r'''
import hashlib, json, logging, os, sys, time, platform
logging.disable(logging.CRITICAL)
import numpy as np
SALT, OUT = sys.argv[1], sys.argv[2]
E, L = 6, 80
os.makedirs(OUT, exist_ok=True)
t0 = time.process_time()
silent = logging.getLogger("t4_silent")
silent.handlers.clear()
silent.addHandler(logging.NullHandler())
silent.setLevel(logging.CRITICAL + 10)
silent.propagate = False
import arc_agi
from arc_agi import OperationMode
from arcengine import GameAction
from importlib.metadata import version as pkgver
arc = arc_agi.Arcade(operation_mode=OperationMode.NORMAL, environments_dir="/tmp/t4_envs",
                     recordings_dir="/tmp/t4_rec", logger=silent)
KEY = str(getattr(arc, "arc_api_key", "") or "")
full = {}
for e in arc.available_environments:
    full.setdefault(e.game_id.split("-")[0], e.game_id)
order = sorted(full, key=lambda g: hashlib.sha256((SALT + "|" + g).encode()).hexdigest())
n = len(order)
held, dev = order[: n // 2], order[n // 2:]
summary = {"label": "probe on public ARC-AGI-3 games; not a score", "salt": SALT,
           "python": platform.python_version(), "arc_agi": pkgver("arc-agi"), "arcengine": pkgver("arcengine"),
           "n_games": n, "order_by_hash": order, "held_games": held, "dev_games": dev,
           "dev_full_ids": {g: full[g] for g in dev}, "episodes": {}, "errors": []}
MODE = sys.argv[3]
summary["mode"] = MODE
for g in (dev if MODE == "dev" else held):
    gseed = int(hashlib.sha256(g.encode()).hexdigest()[:8], 16)
    for ep in range(E):
        rec = {"length": 0, "end": None}
        try:
            try:
                env = arc.make(full[g], seed=ep)
            except TypeError:
                env = arc.make(full[g])
            fd = env.reset() if env is not None else None
            if fd is None or not len(fd.frame):
                rec["end"] = "no_reset_frame"
                summary["episodes"][f"{g}_e{ep}"] = rec
                continue
            rng = np.random.default_rng([ep, gseed])
            frames = [np.asarray(fd.frame[-1], dtype=np.uint8)]
            states, levels, acts, nfr, avails = [str(fd.state.value)], [int(fd.levels_completed)], [], [], []
            for t in range(L):
                avail = sorted(int(a) for a in fd.available_actions if int(a) != 0)
                avails.append(avail)
                if not avail:
                    rec["end"] = "no_actions"
                    break
                a = avail[int(rng.integers(len(avail)))]
                x = y = -1
                data = {}
                if a == 6:
                    cur = frames[-1]
                    if rng.random() < 0.5:
                        y, x = (int(v) for v in rng.integers(64, size=2))
                    else:
                        vals, cnt = np.unique(cur, return_counts=True)
                        ys, xs = np.nonzero(cur != vals[np.argmax(cnt)])
                        if len(ys):
                            i = int(rng.integers(len(ys)))
                            y, x = int(ys[i]), int(xs[i])
                        else:
                            y, x = (int(v) for v in rng.integers(64, size=2))
                    data = {"x": x, "y": y}
                fd2 = env.step(GameAction.from_id(a), data=data)
                if fd2 is None or not len(fd2.frame):
                    rec["end"] = "step_failed"
                    break
                frames.append(np.asarray(fd2.frame[-1], dtype=np.uint8))
                acts.append((a, x, y))
                nfr.append(len(fd2.frame))
                states.append(str(fd2.state.value))
                levels.append(int(fd2.levels_completed))
                fd = fd2
                if states[-1] in ("GAME_OVER", "WIN"):
                    rec["end"] = states[-1]
                    break
            rec["length"] = len(acts)
            rec["end"] = rec["end"] or "max_steps"
            rec["actions_available_union"] = sorted({a for s in avails for a in s})
            np.savez_compressed(os.path.join(OUT, f"{g}_e{ep}.npz"), frames=np.stack(frames),
                                actions=np.array(acts, dtype=np.int16).reshape(-1, 3),
                                nframes=np.array(nfr, dtype=np.int16), states=np.array(states),
                                levels=np.array(levels, dtype=np.int16))
        except Exception as ex:
            rec["end"] = "error"
            summary["errors"].append(f"{g}_e{ep}: {type(ex).__name__}: {str(ex)[:200]}")
        summary["episodes"][f"{g}_e{ep}"] = rec
summary["cpu_seconds_collect"] = round(time.process_time() - t0, 1)
with open(os.path.join(OUT, "summary.json"), "w") as fh:
    json.dump(summary, fh, indent=1)
redacted = 0
if KEY:
    for root, _, files in os.walk(os.path.dirname(OUT)):
        for f in files:
            p = os.path.join(root, f)
            b = open(p, "rb").read()
            if KEY.encode() in b:
                open(p, "wb").write(b.replace(KEY.encode(), b"REDACTED"))
                redacted += 1
print("key-scan:", "clean" if redacted == 0 else f"redacted {redacted} files")
print("games:", n, "held:", held, "dev:", dev)
print("episodes:", {k: (v["length"], v["end"]) for k, v in summary["episodes"].items()})
print("errors:", len(summary["errors"]), "cpu_s:", summary["cpu_seconds_collect"])
''')


def scrub(text):
    """Belt and braces: hide any long key-like token before anything from a child process is printed."""
    return re.sub(r"[A-Za-z0-9_-]{24,}", "[token hidden]", text)


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        print("FAILED:", " ".join(cmd[:5]), scrub(r.stderr[-800:]))
        sys.exit(1)
    return r


run([sys.executable, "-m", "pip", "install", "-q", "uv"])
run([sys.executable, "-m", "uv", "venv", VENV, "--python", "3.12"])
run([sys.executable, "-m", "uv", "pip", "install", "--python", f"{VENV}/bin/python", "-q", "arc-agi==0.9.9",
     "arcengine==0.9.3", "numpy"])
os.makedirs("/tmp/t4work", exist_ok=True)
with open("/tmp/t4work/collect.py", "w") as fh:
    fh.write(COLLECT)
r = subprocess.run([f"{VENV}/bin/python", "-I", "/tmp/t4work/collect.py", SALT, OUT, MODE], cwd="/tmp/t4work",
                   capture_output=True, text=True)
print(scrub(r.stdout[-6000:]))
print("collector exit code:", r.returncode)
if r.returncode != 0:
    print("collector stderr tail, scrubbed:", scrub(r.stderr[-1500:]))
if r.returncode == 0 and WM_SOURCES:
    os.makedirs("/tmp/t4work/wm", exist_ok=True)
    for name, src in WM_SOURCES.items():
        with open(f"/tmp/t4work/wm/{name}", "w") as fh:
            fh.write(src)
    with open("/tmp/t4work/analysis.py", "w") as fh:
        fh.write(ANALYSIS)
    a = subprocess.run([f"{VENV}/bin/python", "-I", "/tmp/t4work/analysis.py", OUT, MODE], cwd="/tmp/t4work",
                       capture_output=True, text=True)
    print(scrub(a.stdout[-8000:]))
    print("analysis exit code:", a.returncode)
    if a.returncode != 0:
        print("analysis stderr tail:", scrub(a.stderr[-2500:]))
print("working dir contents:", sorted(os.listdir("/kaggle/working")))
