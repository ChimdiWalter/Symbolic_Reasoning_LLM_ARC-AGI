"""The five arms: G0 alone, and G0 plus each library (PROTOCOL.md section 3).

Every library entry is added to a copy of G0 (study A's G0: A2's full arc-dsl grammar) as one production
(Grid) -> Grid of cost 3 and charge 1 (cgrow.lang0.add_production), exactly as the object-level builder adds its
operations (objgrow.gates.ObjPlugin.g0). The search is A2's bottom-up enumeration (cgrow.search.run) with the same
counted-operation budget for every arm: 150,000 primitive executions, two attempts, and a CPU-time safety cap
(config) that is reported when it stops a search.
"""
import json

from lr import env as E, libraries as LB
from cgrow import lang0 as L0, search as S, schema as SG
from ngrow import plugin as PL
from a2 import arcdsl as D, bus as B

ARMS = ("G0", "failure_kept", "compression", "random_1", "random_2")
_SH = {}


class SortedTags(frozenset):
    """Study B's fix (ngb/ops.py, frozen in its version 4 candidate): a frozenset of type tags whose iteration order is
    sorted, so that A2's enumeration order, and hence which programs a budget-stopped search reaches, does not depend
    on the interpreter's hash seed. Membership, equality and hashing are unchanged."""
    __slots__ = ()

    def __iter__(self):
        return iter(sorted(frozenset.__iter__(self)))


def shared():
    if "g0b" not in _SH:
        _SH["g0b"] = PL.G0Builder()
        for p in _SH["g0b"].g.prods:                       # seed-independent order (study B's G0Builder)
            p.argtags = tuple(SortedTags(t) for t in p.argtags)
        dsl, consts, _, _ = D.load()
        _SH["fns"] = D.guarded(dsl)
        _SH["consts"] = consts
        _SH["libs"] = E.load(LB.OUT)
        if _SH["libs"]["g0_sha256"] != _SH["g0b"].sha:
            raise RuntimeError("G0 differs from the one the libraries were built for")
    return _SH


def _param_tree(t):
    if t == ("I",):
        return ("#0",)
    if len(t) == 1:
        return t
    return (t[0],) + tuple(_param_tree(c) for c in t[1:])


def fragment_fn(tree):
    sh = shared()
    comp = B.compile_tree(_param_tree(LB.tup(tree)), sh["fns"], sh["consts"], {})

    def f(grid):
        if D.tag(grid) != "G":
            raise D.Bad("type")
        try:
            out = comp((grid,))
        except D.Bad:
            raise
        except Exception:                                           # noqa: BLE001
            raise D.Bad("undefined")
        if out is None or not D.valid(out) or D.tag(out) != "G":
            raise D.Bad("undefined")
        return out
    return f


def structure_fn_bound(sid, k):
    st = SG.by_sid()[sid]
    base = PL.structure_fn(st)
    if k is None:
        return base
    return lambda grid: base(grid, k)


def library_ops(arm, bench):
    """[(head, production function)] of one arm's library for one benchmark, in library order."""
    sh = shared()
    lib = sh["libs"]["benchmarks"][bench]
    if arm == "G0":
        return []
    if arm == "failure_kept":
        from objgrow import arm as OA, edits as ED
        doc = E.load(LB.REGISTRY[bench])
        return [(op.head, ED.production_fn(op)) for op in OA.ops_from_registry(doc)]
    if arm == "compression":
        return [("f:cmp_" + bench + "_" + str(i), fragment_fn(e["tree"])) for i, e in enumerate(lib["compression"])]
    if arm.startswith("random_"):
        return [(f"f:rnd_{sid.replace(':', '_')}_{k}", structure_fn_bound(sid, k)) for sid, k in lib[arm]]
    raise ValueError(arm)


def grammar(arm, bench):
    g = shared()["g0b"]()
    for head, fn in library_ops(arm, bench):
        prod = L0.add_production(g, head, fn, 0, cost=LB.ADDED_COST)
        prod.argtags = tuple(SortedTags(t) for t in prod.argtags)
    return g


def library_digest(arm, bench):
    lib = shared()["libs"]["benchmarks"][bench]
    spec = {"G0": [], "failure_kept": lib["failure_kept"], "compression": [e["program"] for e in lib["compression"]],
            "random_1": lib["random_1"], "random_2": lib["random_2"]}[arm]
    return E.sha_bytes(json.dumps(spec, sort_keys=True).encode())


def run_task(g, task, budget, cpu_cap):
    r = S.run(g, task["train"], task["test_inputs"], budget=budget, cpu_cap=cpu_cap, want=2)
    return {k: r[k] for k in ("fit", "program", "level_complete", "stop", "calls", "cpu_s", "closure_capped")} | \
        {"preds": r["preds"] if r["fit"] else None}
