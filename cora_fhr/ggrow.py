"""G-grow v1: the declared, bounded grammar of growth operators
(docs/CORA_FHR_GGROW_v1.md).

An operator maps one object O (cell -> colour) of a scene G (2-D int array)
to the cells it adds:
    op(O, G) = result & {in-grid background cells of G} - cells(O)
Every quantity derives from O and G. No parameter is a cell literal.

The grammar has:
- 10 sources;
- 50 unary transforms;
- depth-1 terms U(S);
- depth-2 terms U2(U1(S));
- same-source unions union(Ua(S), Ub(S)) with a < b.

That is 37,750 expressions, enumerated in canonical order (class, source,
transforms).
"""
import hashlib
import itertools
import json

import numpy as np

DIRS8 = (("N", (-1, 0)), ("S", (1, 0)), ("E", (0, 1)), ("W", (0, -1)),
         ("NE", (-1, 1)), ("NW", (-1, -1)), ("SE", (1, 1)), ("SW", (1, -1)))
AXIS4 = ("N", "S", "E", "W")
SOURCES = ("self", "part_minority", "part_majority", "edge:N", "edge:S", "edge:E", "edge:W", "corners",
           "centre", "bbox")
TRANSFORMS = tuple(
    [("shift", "unit", d) for d, _ in DIRS8]
    + [("shift", "size", d) for d in AXIS4]
    + [("shift", "size_gap", d) for d in AXIS4]
    + [("ray", d, stop) for d, _ in DIRS8 for stop in ("border", "obstacle")]
    + [("reflect", a) for a in ("N", "S", "E", "W", "H", "V")]
    + [("ring", 4), ("ring", 8), ("hull",), ("interior",)]
    + [("repeat", kind, d) for kind in ("size", "size_gap") for d in AXIS4])
assert len(SOURCES) == 10 and len(TRANSFORMS) == 50
_DIR = dict(DIRS8)
FORMAT, VERSION = "cora_fhr_ggrow", 1
REPEAT_CAP = 30


class Ctx:
    """Everything an expression may read about one object in one scene, all derived."""

    def __init__(self, O, G):
        self.O = {(int(r), int(c)): int(v) for (r, c), v in O.items()}
        self.G = np.asarray(G, dtype=int)
        self.H, self.W = self.G.shape
        vals, counts = np.unique(self.G, return_counts=True)
        self.bg = int(min(zip(vals, counts), key=lambda vc: (-vc[1], vc[0]))[0])   # native growth.grid_background
        cells = list(self.O)
        rs, cs = [r for r, _ in cells], [c for _, c in cells]
        self.r0, self.r1, self.c0, self.c1 = min(rs), max(rs), min(cs), max(cs)
        self.h, self.w = self.r1 - self.r0 + 1, self.c1 - self.c0 + 1
        cnt = {}
        for v in self.O.values():
            cnt[v] = cnt.get(v, 0) + 1
        self.n_colours = len(cnt)
        self.minority = min(cnt.items(), key=lambda kv: (kv[1], kv[0]))[0]
        self.majority = min(cnt.items(), key=lambda kv: (-kv[1], kv[0]))[0]
        self.free = {(r, c) for r in range(self.H) for c in range(self.W)
                     if self.G[r, c] == self.bg and (r, c) not in self.O}

    def inside(self, r, c):
        return 0 <= r < self.H and 0 <= c < self.W


def source(name, x):
    O = x.O
    if name == "self":
        return set(O)
    if name == "part_minority":
        return {p for p, v in O.items() if v == x.minority} if x.n_colours >= 2 else set()
    if name == "part_majority":
        return {p for p, v in O.items() if v == x.majority}
    if name.startswith("edge:"):
        d = name[5:]
        if d == "N":
            return {p for p in O if p[0] == x.r0}
        if d == "S":
            return {p for p in O if p[0] == x.r1}
        if d == "E":
            return {p for p in O if p[1] == x.c1}
        return {p for p in O if p[1] == x.c0}
    if name == "corners":
        return {(x.r0, x.c0), (x.r0, x.c1), (x.r1, x.c0), (x.r1, x.c1)}
    if name == "centre":
        return {((x.r0 + x.r1) // 2, (x.c0 + x.c1) // 2)}
    if name == "bbox":
        return {(r, c) for r in range(x.r0, x.r1 + 1) for c in range(x.c0, x.c1 + 1)}
    raise ValueError(name)


def _vec(kind, d, x):
    if kind == "unit":
        return _DIR[d]
    gap = 1 if kind == "size_gap" else 0
    return {"N": (-(x.h + gap), 0), "S": (x.h + gap, 0), "E": (0, x.w + gap), "W": (0, -(x.w + gap))}[d]


def transform(t, X, x):
    op = t[0]
    if op == "shift":
        dr, dc = _vec(t[1], t[2], x)
        return {(r + dr, c + dc) for r, c in X}
    if op == "ray":
        dr, dc = _DIR[t[1]]
        out = set()
        for r, c in X:
            r, c = r + dr, c + dc
            while x.inside(r, c):
                if t[2] == "obstacle" and x.G[r, c] != x.bg and (r, c) not in x.O:
                    break
                out.add((r, c))
                r, c = r + dr, c + dc
        return out
    if op == "reflect":
        a = t[1]
        f = {"N": lambda r, c: (2 * x.r0 - 1 - r, c), "S": lambda r, c: (2 * x.r1 + 1 - r, c),
             "W": lambda r, c: (r, 2 * x.c0 - 1 - c), "E": lambda r, c: (r, 2 * x.c1 + 1 - c),
             "H": lambda r, c: (x.r0 + x.r1 - r, c), "V": lambda r, c: (r, x.c0 + x.c1 - c)}[a]
        return {f(r, c) for r, c in X}
    if op == "ring":
        nb = ((-1, 0), (1, 0), (0, -1), (0, 1)) if t[1] == 4 else \
             tuple((i, j) for i in (-1, 0, 1) for j in (-1, 0, 1) if (i, j) != (0, 0))
        return {(r + i, c + j) for r, c in X for i, j in nb} - X
    if op == "hull":
        if not X:
            return set()
        rs, cs = [r for r, _ in X], [c for _, c in X]
        return {(r, c) for r in range(min(rs), max(rs) + 1) for c in range(min(cs), max(cs) + 1)}
    if op == "interior":
        if not X:
            return set()
        rs, cs = [r for r, _ in X], [c for _, c in X]
        r0, r1, c0, c1 = min(rs), max(rs), min(cs), max(cs)
        box = {(r, c) for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)}
        open_ = {p for p in box if p not in X and (p[0] in (r0, r1) or p[1] in (c0, c1))}
        stack = list(open_)
        while stack:
            r, c = stack.pop()
            for i, j in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                q = (r + i, c + j)
                if q in box and q not in X and q not in open_:
                    open_.add(q)
                    stack.append(q)
        return box - X - open_
    if op == "repeat":
        dr, dc = _vec(t[1], t[2], x)
        out = set()
        for k in range(1, REPEAT_CAP + 1):
            moved = {(r + k * dr, c + k * dc) for r, c in X}
            if not any(x.inside(r, c) for r, c in moved):
                break
            out |= moved
        return out
    raise ValueError(t)


def finalize(cells, x):
    return cells & x.free


# ---------------------------------------------------------------- expressions
def expressions():
    """All 37,750 expressions, in canonical order, as tuples:
    ("d1", s, t), ("d2", s, t1, t2) meaning t2(t1(s)), or ("u", s, ta, tb) with ta < tb."""
    n = len(TRANSFORMS)
    for s in range(len(SOURCES)):
        for t in range(n):
            yield ("d1", s, t)
    for s in range(len(SOURCES)):
        for t1 in range(n):
            for t2 in range(n):
                yield ("d2", s, t1, t2)
    for s in range(len(SOURCES)):
        for ta, tb in itertools.combinations(range(n), 2):
            yield ("u", s, ta, tb)


def evaluate(expr, x):
    """The added cells of `expr` for object context x."""
    cls, s = expr[0], expr[1]
    S = source(SOURCES[s], x)
    if cls == "d1":
        return finalize(transform(TRANSFORMS[expr[2]], S, x), x)
    if cls == "d2":
        return finalize(transform(TRANSFORMS[expr[3]], transform(TRANSFORMS[expr[2]], S, x), x), x)
    if cls == "u":
        return finalize(transform(TRANSFORMS[expr[2]], S, x) | transform(TRANSFORMS[expr[3]], S, x), x)
    raise ValueError(expr)


def to_str(expr):
    return "|".join(str(v) for v in expr)


def from_str(s):
    parts = s.split("|")
    cls = parts[0]
    if cls not in ("d1", "d2", "u") or len(parts) != {"d1": 3, "d2": 4, "u": 4}[cls]:
        raise ValueError(f"not a G-grow expression: {s!r}")
    e = (cls,) + tuple(int(p) for p in parts[1:])
    if not 0 <= e[1] < len(SOURCES) or any(not 0 <= t < len(TRANSFORMS) for t in e[2:]) or (cls == "u" and e[2] >= e[3]):
        raise ValueError(f"outside the grammar: {s!r}")
    return e


def pretty(expr):
    t = lambda i: TRANSFORMS[i][0] + (f"({','.join(str(v) for v in TRANSFORMS[i][1:])})" if len(TRANSFORMS[i]) > 1 else "")
    s = SOURCES[expr[1]]
    if expr[0] == "d1":
        return f"{t(expr[2])}[{s}]"
    if expr[0] == "d2":
        return f"{t(expr[3])}[{t(expr[2])}[{s}]]"
    return f"union({t(expr[2])}[{s}], {t(expr[3])}[{s}])"


def search(instances, first_only=True, count_cap=2000):
    """Canonical-first expression whose added cells equal every instance's added cells.

    instances: list of (O dict, A set, G). Returns (expr or None, n_fitting counted up to count_cap,
    expressions evaluated). Bottom-up: the depth-1 transforms of every source are cached per instance, and an
    expression is rejected at the first instance it misses."""
    ctx = [Ctx(O, G) for O, _A, G in instances]
    targets = [set(A) for _O, A, _G in instances]
    raw1 = [{} for _ in ctx]                           # (s, t) -> unfinalized set, per instance

    def r1(i, s, t):
        k = (s, t)
        if k not in raw1[i]:
            raw1[i][k] = transform(TRANSFORMS[t], source(SOURCES[s], ctx[i]), ctx[i])
        return raw1[i][k]

    def fits(expr):
        for i, x in enumerate(ctx):
            cls, s = expr[0], expr[1]
            if cls == "d1":
                got = finalize(r1(i, s, expr[2]), x)
            elif cls == "d2":
                got = finalize(transform(TRANSFORMS[expr[3]], r1(i, s, expr[2]), x), x)
            else:
                got = finalize(r1(i, s, expr[2]) | r1(i, s, expr[3]), x)
            if got != targets[i]:
                return False
        return True
    first, n, tried = None, 0, 0
    for expr in expressions():
        tried += 1
        if fits(expr):
            n += 1
            if first is None:
                first = expr
                if first_only:
                    break
            if n >= count_cap:
                break
    return first, n, tried


# ---------------------------------------------------------------- extensions
def canonical_json(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def make(expr) -> dict:
    s = to_str(expr)
    from_str(s)                                         # validates
    body = {"format": FORMAT, "version": VERSION, "expr": s}
    body["name"] = "fx_" + hashlib.sha256(canonical_json(body)).hexdigest()[:16]
    return body


def serialize(ext) -> bytes:
    return canonical_json(ext)


def load(data: bytes) -> dict:
    d = json.loads(data)
    if isinstance(d, dict) and d.get("format") == "cora_fhr_ggrow_guard":   # separate guarded format (ggrow_guard.py)
        from cora_fhr import ggrow_guard as GU
        return GU.load(data)
    if not isinstance(d, dict) or set(d) != {"format", "version", "expr", "name"} or d["format"] != FORMAT \
            or d["version"] != VERSION:
        raise ValueError("not a CORA-FHR G-grow extension")
    rebuilt = make(from_str(d["expr"]))
    if serialize(rebuilt) != data:
        raise ValueError("bytes differ from the canonical form")
    return rebuilt


def render(ext, cc, G) -> set:
    """The added cells of the extension for an object (cell -> colour dict) in a scene."""
    if ext.get("format") == "cora_fhr_ggrow_guard":
        from cora_fhr import ggrow_guard as GU
        return GU.render(ext, cc, G)
    return evaluate(from_str(ext["expr"]), Ctx(cc, G))


def grammar_identity() -> str:
    h = hashlib.sha256()
    h.update(canonical_json({"sources": SOURCES, "transforms": [list(t) for t in TRANSFORMS], "format": FORMAT,
                             "version": VERSION, "repeat_cap": REPEAT_CAP}))
    return h.hexdigest()
