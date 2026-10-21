"""ncv2-g3 joint rule construction. It reads the demonstrations only.

**Joint rule priors.** A rule is a whole (selector, action) pair from the ncv2-g2 candidate sets (`cora_neural_v2g2.search`,
unchanged and imported) and keeps its C+H score. A coupling bonus is added when the SELECTOR picks exactly (or mostly)
the objects of an observed change group (scene.py, read through native execution) AND the ACTION is of a kind that
explains that group's fate. So the selector and the action are scored together, through the objects they share,
not as independent components.

**Execution-guided composition.** Rules are probed lazily, best-first: each probe runs the one-rule program on every
demonstration and records its delta (delta.py). A probe that fixes cells and breaks none is a PARTIAL explanation.
Partials are combined only when their fixed cells complement each other: a combination is ranked by its predicted
remaining error (the demonstration cells that neither part fixes) and predicted breakage, then executed, because
first-match interactions decide the real outcome. An executed combination that is still partial can take one more
rule, up to `max_rules`. This replaces the score-sum order over independently ranked rules, which needed more than
40,000 candidates on two-rule synthetic tasks (records/NEURAL_CORA_V2G2_SYNTHETIC_REPORT_20261020.md, section 4).

Nothing here prunes. Priors, groups and predicted residuals ORDER candidates; every candidate is still compiled and
executed by the unchanged native interpreter, and only a program that fits every demonstration counts.
"""
import heapq
from dataclasses import dataclass

import numpy as np

from cora_neural_v2.rast import ASTError, N
from cora_neural_v2g2 import search as S2
from cora_neural_v2g3 import scene as SC


@dataclass
class JointConfig:
    max_rules: int = 3
    max_broken: int = 0                 # a partial may break at most this many cells
    max_partials: int = 64              # per view
    combo_base: float = 40.0            # orders combinations among themselves
    combo_share: float = 0.5            # at most this share of joint evaluations goes to inexact combinations
    sel_exact: float = 3.0
    sel_partial: float = 1.5
    fate_agree: float = 1.0
    rescore: object = None              # (view, pool) -> priors; neural.residual_rescore plugs in here


def _family(kind):
    return kind[0] if isinstance(kind, tuple) else kind


def rule_pool(view, train, ev, scene, cfg):
    """[(rule node, prior, (sel key, kind))] for one view, best first. Dead selectors (no pick in any
    demonstration) are dropped, as ncv2-g1/g2 drop them."""
    S, A = S2.selectors(ev), S2.actions(ev, train)
    picks = SC.selections(view, [s for s, _, _ in S], train)
    live = [(s, c, k) for s, c, k in S if any(p for p in picks[s] if p)]
    seps = {}
    for s, _, _ in live:
        best = []
        for key, members in scene.groups.items():
            exact, f1 = SC.separation(picks[s], members)
            if f1 >= 0.5:
                best.append((key[0], cfg.sel_exact if exact else cfg.sel_partial * f1))
        seps[s] = best
    pool = []
    for s, sc, sk in live:
        for a, ac, kind in A:
            prior = -(sc + ac) + S2.bonus(sk, kind, ev)
            coupling = 0.0
            for fate, b in seps[s]:
                agree = _family(kind) in SC.FATE_ACTIONS.get(fate, ())
                coupling = max(coupling, b + cfg.fate_agree if agree else 0.25 * b)
            pool.append((S2.rule_node(s, a), prior + coupling, (sk, kind)))
    if cfg.rescore is not None:
        pool = [(r, float(p), k) for (r, _, k), p in zip(pool, cfg.rescore(view, pool))]
    order = sorted(range(len(pool)), key=lambda i: -pool[i][1])
    return [pool[i] for i in order]


def build_pools(task, ev, views, cfg=None):
    """{view: rule pool} for every view with a scene (same-shape tasks only)."""
    cfg = cfg or JointConfig()
    train = task["train"]
    out = {}
    for v in views:
        scene = SC.analyse(train, v)
        if scene is not None:
            out[v] = rule_pool(v, train, ev, scene, cfg)
    return out


@dataclass
class Partial:
    rules: tuple                         # indices into the view's pool
    fixed: list                          # per-demonstration bool masks
    broken: list
    n_fixed: int
    n_remaining: int


def _program(view, pool, idx):
    return N("program", (view, tuple(pool[i][0] for i in idx), "keep", N("same_as_input", ())))


def construct(task, ev, views, evaluate, cfg=None, pools=None):
    """A generator of evaluations: it yields after each candidate it evaluates, and stops when `evaluate` returns
    None (the shared budget is spent) or when the agenda is empty. `evaluate(prog, origin)` returns an object with
    `.deltas` (delta.DemoDelta list, or None if ill-typed); the caller records fits. `pools` may be prebuilt
    (build_pools) and shared with sketch completion."""
    cfg = cfg or JointConfig()
    train = task["train"]
    if not all(np.asarray(a).shape == np.asarray(b).shape for a, b in train):
        return
    diffs = [np.asarray(a) != np.asarray(b) for a, b in train]
    pools = build_pools(task, ev, views, cfg) if pools is None else pools
    singles, multis = {v: [] for v in pools}, {v: [] for v in pools}
    sv = {v: -0.5 * i for i, v in enumerate(S2.VIEWS)}
    probes, exact, inexact, seq, seen = [], [], [], 0, set()
    n_eval = n_inexact = 0

    def push(heap, pri, item):
        nonlocal seq
        heapq.heappush(heap, (-pri, seq, item))
        seq += 1

    for v in views:
        if pools.get(v):
            push(probes, pools[v][0][1] + sv[v], ("probe", v, 0))

    def combine(v, p, q):
        """Queue p + q, in both orders, if the union of their fixes is predicted to beat each part alone."""
        if set(p.rules) & set(q.rules) or len(p.rules) + len(q.rules) > cfg.max_rules:
            return
        fx = [f | g for f, g in zip(p.fixed, q.fixed)]
        br = sum(int((b | c).sum()) for b, c in zip(p.broken, q.broken))
        res = sum(int((d & ~f).sum()) for d, f in zip(diffs, fx))
        if res >= min(p.n_remaining, q.n_remaining):
            return
        pri = cfg.combo_base - res - 2 * br + 0.05 * sum(pools[v][i][1] for i in p.rules + q.rules)
        for idx in (p.rules + q.rules, q.rules + p.rules):
            if idx not in seen:
                seen.add(idx)
                push(exact if res == 0 and br == 0 else inexact, pri, ("combo", v, idx))

    def register(v, idx, ds):
        if ds is None or not all(d.shape_ok and d.fixed is not None for d in ds):
            return
        nf = sum(int(d.fixed.sum()) for d in ds)
        nb = sum(int(d.broken.sum()) for d in ds)
        nr = sum(int(d.remaining.sum()) for d in ds)
        if nf == 0 or nb > cfg.max_broken or nr == 0:
            return
        part = Partial(idx, [d.fixed for d in ds], [d.broken for d in ds], nf, nr)
        if len(idx) == 1:
            if len(singles[v]) >= cfg.max_partials:
                return
            for q in singles[v] + multis[v]:
                combine(v, part, q)
            singles[v].append(part)
        elif len(idx) < cfg.max_rules:
            for q in singles[v]:
                combine(v, part, q)
            multis[v].append(part)

    while probes or exact or inexact:
        # predicted-exact combinations first; otherwise probe, unless inexact combinations are below their share
        if exact:
            heap = exact
        elif inexact and (not probes or n_inexact < cfg.combo_share * n_eval):
            heap = inexact
        else:
            heap = probes
        _, _, item = heapq.heappop(heap)
        kind, v = item[0], item[1]
        if kind == "probe":
            i = item[2]
            if i + 1 < len(pools[v]):
                push(probes, pools[v][i + 1][1] + sv[v], ("probe", v, i + 1))
            idx = (i,)
            if idx in seen:
                continue
            seen.add(idx)
        else:
            idx = item[2]
        n_eval += 1
        n_inexact += heap is inexact
        try:
            e = evaluate(_program(v, pools[v], idx), "joint" if len(idx) > 1 else "joint_probe")
        except ASTError:
            continue
        if e is None:
            return
        register(v, idx, e.deltas)
        yield e
