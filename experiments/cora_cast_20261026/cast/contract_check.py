"""Contract checker API (M3): verify an operator's declared contract by exhaustive tiny-grid and randomized tests.

Usable for any operator object with the CAST interface (`domain(ctx)`, `apply(g, th)`, `fwd(a, th)`,
`bwd(y, th)`), hand-written or invented:

    from cast import contract_check as CC
    rep = CC.check_operator(op, level="full")        # dict; rep["verdict"] in {"PASS", "FAIL"}
    CC.check_operator(op, level="quick")             # h, w <= 2 x 3 exhaustive + 100 random cases

Checks (each counts cases and keeps the first violations):
  fwd_concrete   exhaustive: apply(x, th) in gamma(fwd(alpha(x), th)) for every grid x in the finite scope
  bwd            exhaustive: every x with apply(x, th) == y lies in gamma(bwd(y, th))
  fwd_abstract   random abstract inputs A with enumerable gamma(A): apply(z, th) in gamma(fwd(A, th)) for z in gamma(A)
  random_*       structured random grids up to 20 x 20 on random backgrounds: fwd on concrete inputs, bwd on the
                 actual preimage, fwd on sampled members of widened abstract inputs
Scope statement: PASS supports the contract on the declared finite scope plus the random cases; it is not a proof
for arbitrary grids. Operators get a CPU limit per case (`case_cpu_s`); a case that exceeds it is counted as
`timeouts`, never as a pass.
"""
import collections
import hashlib
import inspect
import itertools
import time

import numpy as np

from cast import absdom as D

LEVELS = {
    "quick": {"palette": (0, 1, 2), "shapes": [(1, 1), (1, 2), (2, 1), (2, 2), (1, 3), (3, 1), (2, 3), (3, 2)],
              "binary4": False, "n_abstract": 20, "n_random": 100},
    "full": {"palette": (0, 1, 2), "shapes": [(1, 1), (1, 2), (2, 1), (2, 2), (1, 3), (3, 1), (2, 3), (3, 2),
                                              (3, 3)],
             "binary4": True, "n_abstract": 60, "n_random": 300},
}


class _Ctx:
    def __init__(self, colours):
        self.in_pal = self.out_pal = self.all_pal = list(colours)
        self.same_shape = True
        self.train, self.test_inputs = [], []


def impl_hash(op):
    try:
        src = inspect.getsource(type(op))
    except (OSError, TypeError):
        src = repr(type(op))
    return hashlib.sha256(src.encode()).hexdigest()


def _grids(shapes, colours):
    for h, w in shapes:
        for vals in itertools.product(colours, repeat=h * w):
            yield np.array(vals, dtype=np.int64).reshape(h, w)


def _rand_structured(rng, h, w):
    bg = int(rng.integers(0, 10))
    g = np.full((h, w), bg, dtype=np.int64)
    for _ in range(int(rng.integers(1, 6))):
        c = int(rng.integers(0, 10))
        r0, c0 = int(rng.integers(0, h)), int(rng.integers(0, w))
        r1, c1 = min(h, r0 + int(rng.integers(1, 6))), min(w, c0 + int(rng.integers(1, 6)))
        g[r0:r1, c0:c1] = c
        if rng.random() < 0.3 and r1 - r0 > 2 and c1 - c0 > 2:
            g[r0 + 1:r1 - 1, c0 + 1:c1 - 1] = bg
    if rng.random() < 0.3:
        g = np.where(rng.random((h, w)) < 0.5, g, g[:, ::-1])
    return g


def _sample_small(rng):
    return _rand_structured(rng, int(rng.integers(2, 8)), int(rng.integers(2, 8)))


def _sample_blocky(rng):
    k = int(rng.integers(2, 4))
    small = _rand_structured(rng, int(rng.integers(2, 7)), int(rng.integers(2, 7)))
    return np.kron(small, np.ones((k, k), dtype=np.int64))


def _sample_rings(rng):
    bg = int(rng.integers(0, 10))
    h, w = int(rng.integers(6, 16)), int(rng.integers(6, 16))
    g = np.full((h, w), bg, dtype=np.int64)
    for _ in range(int(rng.integers(1, 4))):
        c = int(rng.choice([k for k in range(10) if k != bg]))
        r0, c0 = int(rng.integers(0, h - 3)), int(rng.integers(0, w - 3))
        r1, c1 = min(h, r0 + int(rng.integers(3, 6))), min(w, c0 + int(rng.integers(3, 6)))
        g[r0:r1, c0:c1] = c
        g[r0 + 1:r1 - 1, c0 + 1:c1 - 1] = bg
    return g


def _sample_symmetric(rng):
    h, w = int(rng.integers(4, 15)), int(rng.integers(4, 15))
    base = rng.integers(0, 7, size=(h, w))
    kind = int(rng.integers(0, 3))
    if kind == 0:
        g = np.concatenate([base[:, : (w + 1) // 2], base[:, : w // 2][:, ::-1]], 1)
    elif kind == 1:
        g = np.where(np.arange(h * w).reshape(h, w) < (h * w) / 2, base, np.rot90(base, 2))
    else:
        g = np.concatenate([base[: (h + 1) // 2], base[: h // 2][::-1]], 0)
    g = g.astype(np.int64)
    r0, c0 = int(rng.integers(0, g.shape[0] - 1)), int(rng.integers(0, g.shape[1] - 1))
    g[r0:r0 + 2, c0:c0 + 2] = int(rng.integers(7, 10))
    return g


#: operator-specific input samplers for the random part (operators that are rarely defined on random grids)
SAMPLERS = {"scale": _sample_small, "down": _sample_blocky, "fill_enclosed": _sample_rings,
            "symcomplete": _sample_symmetric, "tile": _sample_small, "concat": _sample_small}


def _widen(rng, x, p=0.15):
    cells = D.BITS[x].astype(np.uint16)
    for idx in zip(*np.nonzero(rng.random(x.shape) < p)):
        cells[idx] |= np.uint16(1 << int(rng.integers(0, 10)))
    return D.Abs({x.shape}, (1, 1), cells, D.ALL)


def _members(a, limit, rng):
    opts = [[k for k in range(10) if m >> k & 1] for m in a.cells.ravel()]
    total = 1
    for o in opts:
        total *= len(o)
    if total <= limit:
        for vals in itertools.product(*opts):
            g = np.array(vals, dtype=np.int64).reshape(a.cells.shape)
            if D.contains(a, g):
                yield g
    else:
        for _ in range(limit):
            g = np.array([rng.choice(o) for o in opts], dtype=np.int64).reshape(a.cells.shape)
            if D.contains(a, g):
                yield g


class _Tally:
    def __init__(self):
        self.cases, self.violations, self.timeouts = 0, [], 0

    def bad(self, item):
        if len(self.violations) < 5:
            self.violations.append(item)

    def as_dict(self):
        return {"cases": self.cases, "violations": len(self.violations), "first_violations": self.violations,
                "timeouts": self.timeouts}


def _timed(fn, limit):
    t = time.process_time()
    out = fn()
    return out, (time.process_time() - t) > limit


def check_operator(op, level="full", seed=0, case_cpu_s=2.0, domain_ctx=None, max_theta=None):
    """max_theta: check a seeded random subset of at most this many parameters (declared in the report)."""
    cfg = LEVELS[level]
    rng = np.random.default_rng(seed)
    ctx = domain_ctx or _Ctx(cfg["palette"])
    thetas = list(op.domain(ctx))
    n_domain = len(thetas)
    if max_theta is not None and len(thetas) > max_theta:
        thetas = [thetas[i] for i in sorted(rng.choice(len(thetas), max_theta, replace=False))]
    t0 = time.process_time()
    tal = {k: _Tally() for k in ("fwd_concrete", "bwd", "fwd_abstract", "random_fwd", "random_bwd",
                                 "random_fwd_abstract")}
    grids = list(_grids(cfg["shapes"], cfg["palette"]))
    if cfg["binary4"]:
        grids += list(_grids([(4, 4)], (0, 1)))
    for th in thetas:
        pre = collections.defaultdict(list)
        for x in grids:
            y, slow = _timed(lambda: op.apply(x, th), case_cpu_s)
            if slow:
                tal["fwd_concrete"].timeouts += 1
            if y is None:
                continue
            y = np.asarray(y, dtype=np.int64)
            tal["fwd_concrete"].cases += 1
            if not D.contains(op.fwd(D.alpha(x), th), y):
                tal["fwd_concrete"].bad({"theta": repr(th), "x": x.tolist(), "y": y.tolist()})
            pre[(y.shape, y.tobytes())].append(x)
        for key, xs in pre.items():
            y = np.frombuffer(key[1], dtype=np.int64).reshape(key[0])
            b = op.bwd(y, th)
            for x in xs:
                tal["bwd"].cases += 1
                if not D.contains(b, x):
                    tal["bwd"].bad({"theta": repr(th), "y": y.tolist(), "x": x.tolist()})
    small = [s for s in cfg["shapes"] if s[0] * s[1] >= 4] + ([(4, 4)] if cfg["binary4"] else [])
    for t in range(cfg["n_abstract"]):
        s = small[t % len(small)]
        cells = np.zeros(s, dtype=np.uint16)
        for idx in np.ndindex(s):
            for c in rng.choice(cfg["palette"], size=2 if rng.random() < 0.35 else 1, replace=False):
                cells[idx] |= np.uint16(1 << int(c))
        a = D.Abs({s}, (1, 1), cells, D.ALL)
        mem = list(_members(a, 300, rng))
        for th in thetas:
            f = op.fwd(a, th)
            for z in mem:
                y = op.apply(z, th)
                if y is None:
                    continue
                tal["fwd_abstract"].cases += 1
                if not D.contains(f, y):
                    tal["fwd_abstract"].bad({"theta": repr(th), "z": z.tolist()})
    rctx = _Ctx(tuple(range(10)))
    rthetas = list(op.domain(domain_ctx or rctx))
    if max_theta is not None and len(rthetas) > 4 * max_theta:
        rthetas = [rthetas[i] for i in sorted(rng.choice(len(rthetas), 4 * max_theta, replace=False))]
    sampler = SAMPLERS.get(getattr(op, "name", ""))
    for t in range(cfg["n_random"]):
        h, w = int(rng.integers(3, 21)), int(rng.integers(3, 21))
        x = sampler(rng) if (sampler is not None and t % 2 == 0) else _rand_structured(rng, h, w)
        th = rthetas[int(rng.integers(0, len(rthetas)))]
        y, slow = _timed(lambda: op.apply(x, th), case_cpu_s)
        if slow:
            tal["random_fwd"].timeouts += 1
        if y is None:
            continue
        y = np.asarray(y, dtype=np.int64)
        tal["random_fwd"].cases += 1
        if not D.contains(op.fwd(D.alpha(x), th), y):
            tal["random_fwd"].bad({"theta": repr(th), "shape": list(x.shape)})
        tal["random_bwd"].cases += 1
        if not D.contains(op.bwd(y, th), x):
            tal["random_bwd"].bad({"theta": repr(th), "shape": list(x.shape)})
        a = _widen(rng, x)
        f = op.fwd(a, th)
        for z in _members(a, 8, rng):
            yz = op.apply(z, th)
            if yz is None:
                continue
            tal["random_fwd_abstract"].cases += 1
            if not D.contains(f, np.asarray(yz, dtype=np.int64)):
                tal["random_fwd_abstract"].bad({"theta": repr(th), "shape": list(x.shape)})
    checks = {k: v.as_dict() for k, v in tal.items()}
    nviol = sum(v["violations"] for v in checks.values())
    nto = sum(v["timeouts"] for v in checks.values())
    return {"operator": getattr(op, "name", type(op).__name__), "class": type(op).__name__,
            "impl_sha256": impl_hash(op), "level": level, "seed": seed, "n_theta": len(thetas),
            "n_theta_domain": n_domain, "theta_subsampled": len(thetas) < n_domain,
            "scope": {"palette": list(cfg["palette"]), "shapes": [list(s) for s in cfg["shapes"]],
                      "binary_4x4": cfg["binary4"], "random_cases": cfg["n_random"], "random_max_shape": [20, 20]},
            "checks": checks, "cpu_s": round(time.process_time() - t0, 2),
            "verdict": "PASS" if nviol == 0 and nto == 0 else ("FAIL" if nviol else "INCOMPLETE_TIMEOUTS"),
            "evidence": "EXHAUSTIVE_FINITE_SCOPE_PLUS_RANDOMIZED (not a general proof)"}
