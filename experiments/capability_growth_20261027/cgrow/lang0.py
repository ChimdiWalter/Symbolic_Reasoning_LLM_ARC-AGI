"""The initial language G0 and its extensions, on A2's arc-dsl tree IR and bottom-up search (imported read-only).

G0 = A2's base grammar (productions, function leaves and constants used by the 194 verified S_train solvers, with
A2's integer prior costs re-estimated from that corpus) MINUS a removed set R of primitives. R is known only to the
evaluator (evaluator_only/REMOVED.json); the system side receives a built grammar, never R. Removal drops the
productions and their function-value leaves.

Every added production (the evaluator's reference in G_ref, or an invented operator in G1) gets the same cost
NEW_COST, the same charge (1 primitive execution per input) and a Grid-only signature (Grid[, Integer]) -> Grid,
so the reference and the inventions compete on equal terms.
"""
import json
import os

from cgrow import paths as P

P.ensure_import_paths()
from a2 import arcdsl as D            # noqa: E402
from a2 import bus as B               # noqa: E402
from a2 import grammars as GR         # noqa: E402
from a2.corpus import tree_from_json  # noqa: E402

NEW_COST = 3
CORPUS = os.path.join(P.SWEEP, "a2", "out", "corpus.json")
_CACHE = {}


def corpus(split=None):
    if "doc" not in _CACHE:
        with open(CORPUS, encoding="utf-8") as f:
            _CACHE["doc"] = json.load(f)
    doc = _CACHE["doc"]
    return {t: tree_from_json(v["tree"]) for t, v in doc["tasks"].items()
            if v["verified"] and (split is None or v["split"] == split)}


def build_g0(removed):
    """A2's base grammar estimated on the S_train verified corpus, minus `removed` (productions and fn leaves)."""
    removed = set(removed)
    g = GR.build(list(corpus("S_train").values()), drop_prims=tuple(sorted(removed)))
    g.fn_leaves = [h for h in g.fn_leaves if not (h.startswith("fn:") and h[3:] in removed)]
    for h in list(g.costs):
        if (h.startswith("f:") or h.startswith("fn:")) and h.split(":", 1)[1] in removed:
            del g.costs[h]
    assert not any(p.name in removed for p in g.prods)
    return g


def add_production(g, head, fn, n_int_params, cost=NEW_COST):
    """Append a production `head` with signature (Grid[, Integer]) -> Grid; returns the Prod."""
    tags = [frozenset({"G"})] + [frozenset({"I"})] * n_int_params
    prod = B.Prod(head, fn, tags, charge=1)
    g.prods.append(prod)
    g.costs[head] = cost
    return prod


def remove_production(g, head):
    g.prods = [p for p in g.prods if p.head != head]
    g.costs.pop(head, None)


def reference_fn(name):
    """The evaluator's reference implementation of a removed primitive (guarded arc-dsl), Grid-only."""
    dsl, _, _, _ = D.load()
    f = D.guarded(dsl)[name]

    def ref(grid, *ints):
        if not (isinstance(grid, tuple) and grid and isinstance(grid[0], tuple)):
            raise D.Bad("grid only")
        out = f(grid, *ints)
        if not D.valid(out) or D.tag(out) != "G":
            raise D.Bad("not a grid")
        return out
    return ref


def grid_signature_prims(g):
    """G0 productions whose arguments are grids and small integers and whose result can be a grid (for the card)."""
    sigs, rets = D.prim_signatures(), D.prim_returns()
    out = []
    for p in g.prods:
        if not p.head.startswith("f:"):
            continue
        anns = sigs.get(p.name, [])
        ret = rets.get(p.name, "")
        if ret not in ("Grid", "Piece", "Element", "Any") or not anns:
            continue
        kinds = []
        for a in anns:
            t = D.arg_tags(a)
            if "G" in t and t <= {"G", "O", "X"}:
                kinds.append("grid")
            elif t in (frozenset({"I"}), frozenset({"I", "T"})):
                kinds.append("int")
            else:
                kinds.append(None)
        if None in kinds or kinds[0] != "grid" or kinds.count("grid") > 2 or len(kinds) > 3:
            continue
        out.append((p.name, kinds))
    return out
