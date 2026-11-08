"""Induction of a world model from observed transitions T = [(grid_before, action, grid_after)].

static : fit the base language (Move + ClickMap) and stop.
grown  : the CORA loop. Fit the base language; check it on T; on failure describe what is missing (which kinds of
         piece would cover the wrong cells, ranked by how well each piece's footprint matches them); build the
         top-ranked pieces (fit their parameters on T); check again; keep a piece only if it lowers the wrong cells,
         breaks no transition that was right, and helps on a held check (leave one transition out, refit the piece
         without it, and it must predict that transition exactly). B pieces per round, at most R rounds.
shuffled: the same loop, but the ranking of pieces comes from ANOTHER item's failure description (a different
         family), so construction is not guided by this item's own failure. Checks use this item's data.
"""
from collections import Counter

import numpy as np

from wm.envs import DIRS, parse_click
from wm.model import Model, Piece, UNIT, body_of, predict, predict_pre, select, trig_ok, _target

SKELETONS = [
    ("ahead_shift", "ahead", "shift_action", "dir", "pre"),
    ("ahead_recolour_to", "ahead", "recolour_to", "dir", "pre"),
    ("ahead_recolour_map", "ahead", "recolour_map", "dir", "pre"),
    ("vacated_recolour_to", "vacated", "recolour_to", "dir", "post"),
    ("vacated_recolour_map", "vacated", "recolour_map", "dir", "post"),
    ("click_n4_recolour_map", "click_n4", "recolour_map", "click", "post"),
    ("click_n4_recolour_to", "click_n4", "recolour_to", "click", "post"),
    ("click_n4_recolour_to_clicked", "click_n4", "recolour_to_clicked", "click", "post"),
    ("click_n8_recolour_map", "click_n8", "recolour_map", "click", "post"),
    ("click_n8_recolour_to", "click_n8", "recolour_to", "click", "post"),
    ("click_n8_recolour_to_clicked", "click_n8", "recolour_to_clicked", "click", "post"),
    ("click_region_recolour_map", "click_region", "recolour_map", "click", "post"),
    ("click_region_recolour_to", "click_region", "recolour_to", "click", "post"),
    ("corner_region_recolour_map", "corner_region", "recolour_map", "any", "post"),
    ("corner_region_recolour_to", "corner_region", "recolour_to", "any", "post"),
    ("corner_region_recolour_to_clicked", "corner_region", "recolour_to_clicked", "click", "post"),
    ("first_recolour_to", "first", "recolour_to", "any", "post"),
    ("first_recolour_map", "first", "recolour_map", "any", "post"),
    ("all_shift_fixed", "all", "shift_fixed", "any", "post"),
    ("all_recolour_map", "all", "recolour_map", "any", "post"),
    ("all_recolour_to", "all", "recolour_to", "any", "post"),
    ("slide", "slide", None, "dir", None),
    ("wrap", "wrap", None, "dir", None),
]
SK = {s[0]: s for s in SKELETONS}
MISSING = object()
LOO_MAX = 5          # held checks tried per candidate piece (the first five transitions it fixes)


def colours_of(T):
    """Colours that take part in some observed change (before or after colour of a changed cell). Piece parameters
    range over these only: a property of the observed data, the same for every arm."""
    s = set()
    for g0, _, g1 in T:
        ch = g0 != g1
        if ch.any():
            s.update(np.unique(g0[ch]).tolist())
            s.update(np.unique(g1[ch]).tolist())
    return sorted(int(c) for c in s)


def wrong_vec(m, T):
    return np.array([int(np.count_nonzero(predict(m, g0, a) != g1)) for g0, a, g1 in T], dtype=np.int64)


def translation(A0, A1, shape):
    if len(A0) == 0 or len(A0) != len(A1):
        return None
    s1 = set(map(tuple, A1.tolist()))
    y0, x0 = int(A0[0][0]), int(A0[0][1])
    for c in A1.tolist():
        v = (c[0] - y0, c[1] - x0)
        if {(int(y) + v[0], int(x) + v[1]) for y, x in A0} == s1:
            return v
        if {((int(y) + v[0]) % shape[0], (int(x) + v[1]) % shape[1]) for y, x in A0} == s1:
            return v
    return None


def refit_move(m, T):
    """Displacement per action = the most common translation of the actor; passable colours = background plus the
    colours of cells the actor stepped into (read after the pre pieces)."""
    if not m.actor:
        m.delta = {}
        return
    cnt, moves = {}, []
    for g0, a, g1 in T:
        if a[0] == "C":
            continue
        A0 = np.argwhere(np.isin(g0, m.actor))
        if len(A0) > ACTOR_MAX:
            continue
        v = translation(A0, np.argwhere(np.isin(g1, m.actor)), g0.shape)
        if v is None or v == (0, 0):
            continue
        H, W = g0.shape
        if m.wrap:
            v = ((v[0] + H // 2) % H - H // 2, (v[1] + W // 2) % W - W // 2)
        if m.slide and (v[0] == 0) != (v[1] == 0):
            v = (int(np.sign(v[0])), int(np.sign(v[1])))
        cnt.setdefault(a, Counter())[v] += 1
        moves.append((g0, a, A0))
    m.delta = {a: c.most_common(1)[0][0] for a, c in cnt.items()}
    P = {m.bg}
    for g0, a, A0 in moves:
        d = m.delta[a]
        gi = predict_pre(m, g0, a) if m.pre else g0
        bs = set(map(tuple, A0.tolist()))
        for y, x in bs:
            t = _target(m, y, x, d, *g0.shape)
            if t is not None and t not in bs:
                P.add(int(gi[t]))
    m.passable = frozenset(P)


def fit_clickmap(m, T):
    cnt = {}
    for g0, a, g1 in T:
        if a[0] == "C":
            y, x = parse_click(a)
            cnt.setdefault(int(g0[y, x]), Counter())[int(g1[y, x])] += 1
    m.clickmap = {u: c.most_common(1)[0][0] for u, c in cnt.items() if c.most_common(1)[0][0] != u}


def fit_static(T):
    """Search the base language: background among the three most frequent colours of the first grid (walls can
    outnumber floor in small rooms), actor among the colours whose cells are seen to translate under a non-click
    action at least once, covering at most ACTOR_MAX cells (or no actor); displacements, passable colours and the
    click map are then fitted. Fewest wrong cells wins."""
    best = None
    movers = []
    for c in colours_of(T):
        for g0, a, g1 in T:
            if a[0] == "C" or not ((g0 == c) != (g1 == c)).any():
                continue
            A0 = np.argwhere(g0 == c)
            if 0 < len(A0) <= ACTOR_MAX and translation(A0, np.argwhere(g1 == c), g0.shape) not in (None, (0, 0)):
                movers.append(c)
                break
    for bg, _ in Counter(T[0][0].ravel().tolist()).most_common(3):
        cands = [()] + [(c,) for c in movers if c != bg]
        for act in cands:
            m = Model(int(bg), act)
            refit_move(m, T)
            fit_clickmap(m, T)
            w = int(wrong_vec(m, T).sum())
            if best is None or w < best[0]:
                best = (w, m)
    return best[1]


BIG = 1024           # colours covering more cells than this in the first observed grid are not used as objects
ACTOR_MAX = 600      # an actor candidate covers at most this many cells


def sizes_of(T):
    v, c = np.unique(T[0][0], return_counts=True)
    return {int(a): int(b) for a, b in zip(v, c)}


def thetas(sk, m, cols, sizes=None):
    sel, eff = sk[1], sk[2]
    nonbg = [c for c in cols if c != m.bg]
    if sizes is not None and sel in ("ahead", "all"):
        nonbg = [c for c in nonbg if sizes.get(c, 0) <= BIG]
    if sel == "ahead":
        return [(c, k) for c in nonbg if c not in m.actor for k in (0, 1)]   # k=1: the whole touched object
    if sel == "corner_region":
        return [0, 1, 2, 3]
    if sel == "first":
        return [(c, o) for c in nonbg for o in range(4)]
    if sel == "all":
        if eff == "shift_fixed":
            return [(c, v) for c in nonbg if c not in m.actor for v in UNIT]
        return nonbg
    return [None]


def _post_ctx(m, g0, a):
    """The current model's prediction and its context (cells vacated by the move)."""
    from wm.model import apply_piece, move
    g1 = g0.copy()
    ctx = {}
    for p in m.pre:
        apply_piece(p, m, g0, g1, a, ctx)
    if a[0] != "C" and m.actor:
        move(m, g0, g1, a, ctx)
    elif a[0] == "C" and m.clickmap:
        y, x = parse_click(a)
        v = m.clickmap.get(int(g0[y, x]))
        if v is not None:
            g1[y, x] = v
    for p in m.post:
        apply_piece(p, m, g0, g1, a, ctx)
    return g1, ctx


def footprint(sk, th, m, g0, a, gp, ctx):
    name, sel, eff, trig, when = sk
    if not trig_ok(trig, a):
        return set()
    H, W = g0.shape
    if sel in ("slide", "wrap"):
        d = m.delta.get(a)
        if not d or not m.actor:
            return set()
        body = list(zip(*(v.tolist() for v in body_of(m, g0))))
        out = set(body)
        if sel == "wrap":
            out |= {((y + d[0]) % H, (x + d[1]) % W) for y, x in body}
        else:
            u = (int(np.sign(d[0])), int(np.sign(d[1])))
            for y, x in body:
                ny, nx = y + u[0], x + u[1]
                while 0 <= ny < H and 0 <= nx < W:
                    out.add((ny, nx))
                    ny, nx = ny + u[0], nx + u[1]
        return out
    if sel == "vacated":
        return set(zip(*(v.tolist() for v in body_of(m, g0))))
    cells = set(select(Piece(sel, th, eff, None, trig, when), m, g0, gp, a, dict(ctx)))
    if eff == "shift_action":
        d = m.delta.get(a)
        if d:
            cells |= {t for t in (_target(m, y, x, d, H, W) for y, x in cells) if t is not None}
    elif eff == "shift_fixed":
        dy, dx = th[1]
        cells |= {(y + dy, x + dx) for y, x in cells if 0 <= y + dy < H and 0 <= x + dx < W}
    return cells


def describe(m, T, cols):
    """The failure description: the wrong cells of the current model on T, and, for every kind of piece, how well its
    footprint matches them (F1 of coverage and precision at its best parameter). Returns the ranked piece names."""
    res = []
    for i, (g0, a, g1) in enumerate(T):
        gp, ctx = _post_ctx(m, g0, a)
        R = np.argwhere(gp != g1)
        if len(R):
            res.append((i, set(map(tuple, R.tolist())), gp, ctx))
    total = sum(len(R) for _, R, _, _ in res)
    if not total:
        return [], {}
    scores, sizes = [], sizes_of(T)
    for k, sk in enumerate(SKELETONS):
        best = 0.0
        for th in thetas(sk, m, cols, sizes):
            hit = fp = 0
            for i, R, gp, ctx in res:
                g0, a, _ = T[i]
                F = footprint(sk, th, m, g0, a, gp, ctx)
                hit += len(F & R)
                fp += len(F)
            if hit:
                cov, prec = hit / total, hit / fp
                best = max(best, 2 * cov * prec / (cov + prec))
        if best > 0:
            scores.append((-best, k, sk[0]))
    scores.sort()
    return [n for _, _, n in scores], {n: round(-s, 4) for s, _, n in scores}


def estimate_psi(sk, th, m, T, cache):
    name, sel, eff, trig, when = sk
    if eff in ("shift_action", "shift_fixed", "recolour_to_clicked"):
        return None
    pairs = []
    for i, (g0, a, g1) in enumerate(T):
        if not trig_ok(trig, a):
            continue
        gp, ctx = cache[i]
        src = gp if when == "post" else g0
        for q in select(Piece(sel, th, eff, None, trig, when), m, g0, gp, a, dict(ctx)):
            pairs.append((int(src[q]), int(g1[q])))
    if eff == "recolour_to":
        ch = Counter(w for u, w in pairs if w != u)
        return ch.most_common(1)[0][0] if ch else MISSING
    per = {}
    for u, w in pairs:
        per.setdefault(u, Counter())[w] += 1
    mp = tuple(sorted((u, c.most_common(1)[0][0]) for u, c in per.items() if c.most_common(1)[0][0] != u))
    return mp if mp else MISSING


def fit_skeleton(sk, m, T, cols):
    """Best parameters of one kind of piece on T: (model with the piece, wrong cells per transition, piece)."""
    name, sel, eff, trig, when = sk
    if sel in ("slide", "wrap"):
        if getattr(m, sel):
            return None
        m2 = m.copy()
        setattr(m2, sel, True)
        refit_move(m2, T)
        return m2, wrong_vec(m2, T), Piece(sel, None, None, None, trig, None)
    cache = [_post_ctx(m, g0, a) for g0, a, _ in T]
    best, sizes = None, sizes_of(T)
    for th in thetas(sk, m, cols, sizes):
        psi = estimate_psi(sk, th, m, T, cache)
        if psi is MISSING:
            continue
        p = Piece(sel, th, eff, psi, trig, when)
        m2 = m.with_piece(p)
        if when == "pre":
            refit_move(m2, T)
        w = wrong_vec(m2, T)
        if best is None or w.sum() < best[1].sum():
            best = (m2, w, p)
    return best


def refit_all(m, T):
    m = m.copy()
    refit_move(m, T)
    fit_clickmap(m, T)
    return m


def accept(sk, m, T, cols, w_cur, fit):
    m2, w2, p = fit
    if w2.sum() >= w_cur.sum() or ((w_cur == 0) & (w2 > 0)).any():
        return False
    for t in np.flatnonzero((w_cur > 0) & (w2 == 0))[:LOO_MAX]:
        Tm = T[:t] + T[t + 1:]
        f = fit_skeleton(sk, refit_all(m, Tm), Tm, cols)
        if f is not None and np.array_equal(predict(f[0], T[t][0], T[t][1]), T[t][2]):
            return True
    return False


def grow(T, fixed_ranking=None, B=3, R=4):
    """The loop. fixed_ranking=None uses this item's own failure description (grown); a list uses a given ranking
    (shuffled control). Returns (model, log)."""
    m = fit_static(T)
    cols = colours_of(T)
    w = wrong_vec(m, T)
    tried, log = set(), []
    for r in range(R):
        if w.sum() == 0:
            break
        if fixed_ranking is None:
            ranking, scores = describe(m, T, cols)
        else:
            ranking, scores = fixed_ranking, {}
        cands = [n for n in ranking if n not in tried][:B]
        if not cands:
            break
        best = None
        for n in cands:
            tried.add(n)
            f = fit_skeleton(SK[n], m, T, cols)
            if f is not None and accept(SK[n], m, T, cols, w, f) and (best is None or f[1].sum() < best[1].sum()):
                best = f
        log.append({"round": r, "wrong_before": int(w.sum()), "ranking": ranking[:6],
                    "scores": {n: scores.get(n) for n in ranking[:6]}, "tried": cands,
                    "accepted": None if best is None else best[2].sel + ("" if best[2].eff is None
                                                                          else "_" + best[2].eff)})
        if best is not None:
            m = refit_all(best[0], T)
            w = wrong_vec(m, T)
    return m, log
