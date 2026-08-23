"""The frozen synthetic semantic-witness set.

Deterministic (one seed, one PRNG, no wall clock), TYPE-DIRECTED (values
are generated from a type's structural capabilities and frozen bounds), and
INDEPENDENT of any candidate and of every Step-A artifact: this module
reads no file and takes the list of types to cover as its only input.

Purpose (design, "Semantic separation certificate" and "Deduplication"):
a candidate e : A -> B is later fingerprinted as the tuple of its outputs
over this fixed set, so that (1) independently proposed extensions can be
deduplicated semantically, (2) two supposedly equivalent proposals can be
told apart by a concrete witness, and (3) separation from the baseline
grammar F(K_L4*) is established on a bounded domain. A proposal cannot
choose the probes on which it is evaluated, because they exist first.

Expr-typed witnesses are built generically: every production of the frozen
registry whose result is that Expr type is applied to witness values of its
argument types. No production is named here.
"""
from __future__ import annotations

import hashlib
import json
import random

import numpy as np

from level4_blind_runtime import runtime as V

from . import kinds as K
from . import k2_slots as S

SEED = 424242
BOUNDS = {
    "contexts": 6,
    "side": (2, 6),                 # grid height and width, inclusive
    "colours_per_context": 4,       # distinct colours per context at most
    "alphabet": 10,                 # colour values 0..9 (the grid format)
    "cellsets_per_context": 4,
    "cellset_size": (1, 6),
    "collection_size": (1, 3),
    "values_per_type": 4,           # witness values per type per context
    "expr_depth": 2,
}


def _grid(rng, h, w, sample):
    bg = sample[0]
    out = np.full((h, w), bg, dtype=int)
    for r in range(h):
        for c in range(w):
            if rng.random() > 0.6:
                out[r, c] = rng.choice(sample)
    return out


def _connected(rng, h, w, size):
    r, c = rng.randrange(h), rng.randrange(w)
    cells = {(r, c)}
    while len(cells) < size:
        r, c = rng.choice(sorted(cells))
        dr, dc = rng.choice(((-1, 0), (1, 0), (0, -1), (0, 1)))
        nr, nc = r + dr, c + dc
        if 0 <= nr < h and 0 <= nc < w:
            cells.add((nr, nc))
        if len(cells) >= h * w:
            break
    return frozenset(cells)


class Context:
    def __init__(self, index, grid, cellsets, rng_state):
        self.index = index
        self.grid = grid
        self.cellsets = cellsets
        self.rng = random.Random(rng_state)


def contexts():
    rng = random.Random(SEED)
    lo, hi = BOUNDS["side"]
    out = []
    for index in range(BOUNDS["contexts"]):
        h, w = rng.randint(lo, hi), rng.randint(lo, hi)
        sample = rng.sample(range(BOUNDS["alphabet"]), BOUNDS["colours_per_context"])
        grid = _grid(rng, h, w, sample)
        a, b = BOUNDS["cellset_size"]
        cellsets = tuple(_connected(rng, h, w, rng.randint(a, min(b, h * w)))
                         for _ in range(BOUNDS["cellsets_per_context"]))
        out.append(Context(index, grid, cellsets, rng.random()))
    return out


# --------------------------------------------------------------------------
# type-directed value generation
# --------------------------------------------------------------------------

def _feature_values(ctx):
    values, seen = [], set()
    for cells in ctx.cellsets:
        table = V.descriptors(cells, ctx.grid)
        for v in table.values():
            key = repr(v)
            if v is not None and key not in seen:
                seen.add(key)
                values.append(v)
    return values


def _colours(ctx):
    return [ctx.rng.randrange(BOUNDS["alphabet"])
            for _ in range(BOUNDS["values_per_type"])]


def _induced_value(name, ctx, resolve, types):
    rng = ctx.rng
    if name == "Map":
        keys = _feature_values(ctx)
        if not keys:
            return None
        chosen = rng.sample(keys, min(len(keys), 3))
        return tuple(sorted(((k, rng.randrange(BOUNDS["alphabet"]))
                             for k in chosen), key=lambda kv: repr(kv[0])))
    if name == "IndexMap":
        matrix, k, origin = rng.choice(list(S.index_map_family()))
        return (matrix, k, origin, (rng.randint(-2, 2), rng.randint(-2, 2)))
    if name == "Frame":
        shape_rule, origin_rule, fill_rule = rng.choice(list(S.frame_family()))
        lo, hi = BOUNDS["side"]
        return (shape_rule, (rng.randint(lo, hi), rng.randint(lo, hi)),
                origin_rule, (rng.randint(0, 1), rng.randint(0, 1)),
                fill_rule, rng.randrange(BOUNDS["alphabet"]))
    if name == "Colour":
        return rng.randrange(BOUNDS["alphabet"])
    return None


def values_for(t: V.Type, ctx: Context, resolve, types, depth=None) -> list:
    """Witness values of type ``t`` relative to a context, by capability."""
    depth = BOUNDS["expr_depth"] if depth is None else depth
    kind = resolve(t)
    if kind is None:
        return []
    n = BOUNDS["values_per_type"]
    rng = ctx.rng
    if kind.has("vocab"):
        merged = {**S.TERMINALS, **V.TERMINAL_VALUES}
        return list(merged.get(str(t), ()))
    if kind.has("induced"):
        out = [_induced_value(str(t), ctx, resolve, types) for _ in range(n)]
        return [v for v in out if v is not None]
    if kind.has("expr"):
        if depth <= 0:
            return []
        out = []
        for name in sorted(V.REGISTRY):
            production = V.REGISTRY[name]
            if not V.type_equal(production.result_type, t):
                continue
            options = [values_for(a, ctx, resolve, types, depth - 1)
                       for a in production.arg_types]
            if any(not o for o in options):
                continue
            for _ in range(n):
                out.append((name, tuple(rng.choice(o) for o in options)))
        return out
    if kind.has("collection"):
        element_values = values_for(kind.element, ctx, resolve, types, depth)
        if not element_values:
            return []
        a, b = BOUNDS["collection_size"]
        out = []
        for _ in range(n):
            size = rng.randint(a, min(b, len(element_values)))
            out.append(tuple(rng.sample(element_values, size)))
        return out
    if kind.has("carrier"):
        lo, hi = BOUNDS["side"]
        sample = rng.sample(range(BOUNDS["alphabet"]), BOUNDS["colours_per_context"])
        return [ctx.grid.copy(),
                _grid(rng, rng.randint(lo, hi), rng.randint(lo, hi), sample)]
    if kind.has("cells") and kind.has("colour"):
        return [(cells, rng.randrange(BOUNDS["alphabet"])) for cells in ctx.cellsets]
    if kind.has("cells"):
        return list(ctx.cellsets)
    if kind.has("scalar") and kind.has("colour"):
        return _colours(ctx)
    if kind.has("scalar"):
        return _feature_values(ctx)
    return []


def witness_set(types: list, resolve) -> dict:
    """Every type covered on every context; canonical, JSON-able."""
    record = {"seed": SEED, "bounds": BOUNDS, "contexts": []}
    for ctx in contexts():
        entry = {"index": ctx.index, "grid": K.as_canonical(ctx.grid),
                 "values": {}}
        for t in sorted(types, key=str):
            ctx.rng = random.Random(f"{SEED}:{ctx.index}:{t}")
            entry["values"][str(t)] = [K.as_canonical(v)
                                       for v in values_for(t, ctx, resolve, types)]
        record["contexts"].append(entry)
    return record


def witness_values(types: list, resolve) -> list:
    """The same set as live values: [(Context, {type_str: [values]})]."""
    out = []
    for ctx in contexts():
        values = {}
        for t in sorted(types, key=str):
            ctx.rng = random.Random(f"{SEED}:{ctx.index}:{t}")
            values[str(t)] = values_for(t, ctx, resolve, types)
        out.append((ctx, values))
    return out


def sha256_of(record: dict) -> str:
    return hashlib.sha256(
        json.dumps(record, sort_keys=True, default=str).encode()).hexdigest()


# --------------------------------------------------------------------------
# behavioural fingerprint of a production over the witness set
# --------------------------------------------------------------------------

def behaviour(production, arg_types, arg_modes, witnesses, max_combos=24):
    """(context index, canonical args, canonical output) over the witness
    set; argument combinations are taken in canonical order, bounded."""
    rows = []
    for ctx, values in witnesses:
        options = [values.get(str(t), []) for t in arg_types]
        if any(not o for o in options):
            continue
        combos = [()]
        for o in options:
            combos = [c + (v,) for c in combos for v in o]
        if len(combos) > max_combos:
            step = -(-len(combos) // max_combos)      # even subsample, whole space
            combos = combos[::step][:max_combos]
        for combo in combos:
            try:
                out = production.evaluate(V.Ctx(ctx.grid), *combo)
            except Exception:
                out = None
            rows.append({"context": ctx.index,
                         "args": [K.as_canonical(v) for v in combo],
                         "out": K.as_canonical(out)})
    return rows


def fingerprint(rows) -> str:
    return hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()
