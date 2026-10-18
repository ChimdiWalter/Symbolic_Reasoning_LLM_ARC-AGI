"""Guarded G-grow extensions (DEVELOPMENT; protocol records/CORA_FHR_GUARD_PROBE_PROTOCOL_20261018.md).

A guarded operator has a typed applicability condition. One object feature selects which of two G-grow v1
expressions acts on the object:

    if <feature> <op> <value>: <then expression>  else: <else expression>

- features: size, n_colours, colours (the sorted colour set), h, w (the bbox);
- op: eq for every feature; le for size, h and w.

It encodes both **where** an operation applies and **what** it does. The branch expressions are ordinary
G-grow v1 expressions; the v1 grammar, its 37,750 expressions and its identity are unchanged. The format
is separate ("cora_fhr_ggrow_guard"), and `ggrow.load` and `ggrow.render` dispatch to this module only
for it.

The guard reads the object and scene only: no answers and no labels.
"""
import hashlib
import json

from cora_fhr import ggrow as GG

FORMAT, VERSION = "cora_fhr_ggrow_guard", 1
FEATURES = ("size", "n_colours", "colours", "h", "w")
ORDERED = ("size", "h", "w")


def feature(x, f):
    if f == "size":
        return len(x.O)
    if f == "n_colours":
        return x.n_colours
    if f == "colours":
        return tuple(sorted(set(x.O.values())))
    if f == "h":
        return x.h
    if f == "w":
        return x.w
    raise ValueError(f)


def holds(guard, x):
    f, op, v = guard
    val = feature(x, f)
    return val == v if op == "eq" else val <= v


def evaluate(g, x):
    return GG.evaluate(g["then"] if holds(g["guard"], x) else g["else"], x)


def to_str(g):
    f, op, v = g["guard"]
    return json.dumps({"guard": [f, op, list(v) if isinstance(v, tuple) else v],
                       "then": GG.to_str(g["then"]), "else": GG.to_str(g["else"])}, sort_keys=True)


def from_str(s):
    d = json.loads(s)
    f, op, v = d["guard"]
    if f not in FEATURES or op not in ("eq", "le") or (op == "le" and f not in ORDERED):
        raise ValueError("invalid guard")
    return {"guard": (f, op, tuple(v) if isinstance(v, list) else v), "then": GG.from_str(d["then"]),
            "else": GG.from_str(d["else"])}


def pretty(g):
    f, op, v = g["guard"]
    return f"if {f} {'==' if op == 'eq' else '<='} {v}: {GG.pretty(g['then'])} else {GG.pretty(g['else'])}"


def make(g):
    s = to_str(g)
    from_str(s)
    body = {"format": FORMAT, "version": VERSION, "expr": s}
    body["name"] = "fg_" + hashlib.sha256(GG.canonical_json(body)).hexdigest()[:16]
    return body


def load(data):
    d = json.loads(data)
    if not isinstance(d, dict) or set(d) != {"format", "version", "expr", "name"} or d["format"] != FORMAT \
            or d["version"] != VERSION:
        raise ValueError("not a CORA-FHR guarded extension")
    rebuilt = make(from_str(d["expr"]))
    if GG.serialize(rebuilt) != data:
        raise ValueError("bytes differ from the canonical form")
    return rebuilt


def render(ext, cc, G):
    return evaluate(from_str(ext["expr"]), GG.Ctx(cc, G))


def guards(ctx):
    """Candidate guards, in canonical order (feature order, then values sorted by str); both sides non-empty."""
    out = []
    for f in FEATURES:
        vals = sorted({feature(x, f) for x in ctx}, key=str)
        for v in vals:
            for op in (("eq", "le") if f in ORDERED else ("eq",)):
                g = (f, op, v)
                side = [holds(g, x) for x in ctx]
                if any(side) and not all(side) and g not in out:
                    out.append(g)
    return out


def _fitting(trip, cap):
    ctx = [GG.Ctx(O, G) for O, _A, G in trip]
    tgt = [set(A) for _O, A, _G in trip]
    first = GG.search(trip)[0]
    if first is None:
        return []
    fits = []
    for e in GG.expressions():
        if e[0] == first[0] and all(GG.evaluate(e, x) == t for x, t in zip(ctx, tgt)):
            fits.append(e)
            if len(fits) >= cap:
                break
    return fits


def search(trip, cap=8):
    """All fitting guarded operators (each guard with both sides jointly expressible), canonical first.
    trip: [(O, A, G)]. Each side's alternatives are the same-class fitting expressions, capped. Returns a list of
    {"guard", "then", "else", "alt_then", "alt_else"}."""
    ctx = [GG.Ctx(O, G) for O, _A, G in trip]
    found = []
    for g in guards(ctx):
        a = [t for t, x in zip(trip, ctx) if holds(g, x)]
        b = [t for t, x in zip(trip, ctx) if not holds(g, x)]
        fa = _fitting(a, cap)
        if not fa:
            continue
        fb = _fitting(b, cap)
        if fb:
            found.append({"guard": g, "then": fa[0], "else": fb[0], "alt_then": fa, "alt_else": fb})
    return found
