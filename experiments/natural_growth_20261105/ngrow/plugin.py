"""The natural-task plug-in: G0 (A2's full arc-dsl grammar), the search, and the schema language of the construction
test, for the shared construction core (cgrow/selfext_core.py) and the growth controller (cgrow/controller.py).

G0 = A2's base grammar (productions, function leaves and constants of the 194 verified S_train solvers with A2's
integer costs), with NOTHING removed: on natural tasks there is no deliberately missing capability, so the system
is the grammar as it stands. Added productions are the construction test's: one schema structure per production,
cost 3, charge 1, signature (Grid[, Integer]) -> Grid, every parameter value of the structure through the integer
argument (k in {2, 3, 4}).

Search: A2's bottom-up enumeration (cgrow/search.py), base budget 150,000 primitive executions with a CPU-time cap of
20 CPU-s, two attempts (the first two fitting programs with distinct test predictions). CPU caps are process CPU time
(time.process_time) at their frozen values; the searches stop on their execution budgets (phase 1: always). The
machine's speed factor CPU_SCALE (bench.py) scales only blind enumeration's 60 CPU-s per unit (grow.py), the one
CPU-defined stop that binds.
"""
import copy
import os

from ngrow import env as E                                                     # noqa: F401  (import paths)
from cgrow import lang0 as L0, search as S, schema as SG, probes as PR          # noqa: E402
from a2 import arcdsl as D                                                      # noqa: E402

CPU_SCALE = float(os.environ.get("NG_CPU_SCALE", "1.0"))
NEW_COST = L0.NEW_COST
#: the construction test's probe grids (cgrow.episode.SIG_PROBES, recomputed here without importing the module
#: that loads the model-code sandbox; equality is checked in checks.py)
SIG_PROBES = PR.probe_grids(30, seed=7071, min_side=1, max_side=9)


class G0Builder:
    """Builds G0 once and hands out independent copies (the system side adds productions to copies only)."""

    def __init__(self):
        self.g = L0.build_g0(())
        self.sha = E.sha_text(repr(sorted(p.head for p in self.g.prods)) + repr(sorted(self.g.fn_leaves)) +
                              repr(sorted(self.g.costs.items())))

    def __call__(self):
        g = copy.copy(self.g)
        g.prods, g.costs = list(self.g.prods), dict(self.g.costs)
        return g


def structure_fn(st):
    """The construction test's production function for a schema structure (identical to cgrow.s1.Gates.fn)."""
    def f(grid, *ints):
        if D.tag(grid) != "G":
            raise D.Bad("type")
        if st.param and (len(ints) != 1 or type(ints[0]) is not int or ints[0] not in SG.KS):
            raise D.Bad("param")
        out = st(grid, *ints)
        if out is None or not D.valid(out) or D.tag(out) != "G":
            raise D.Bad("undefined")
        return out
    return f


def head_of(sid):
    return "f:sig_" + sid.replace(":", "_")


class NaturalPlugin:
    """Plug-in interface of cgrow/selfext_core.py (see its docstring), on natural tasks with the full G0."""
    BASE_BUDGET, BASE_CPU = S.BASE_BUDGET, S.BASE_CPU
    NOVELTY_BUDGET, NOVELTY_CPU = 200_000, 10.0          # S1's novelty gate (cgrow.episode.DUP_BUDGET, 10 s cap)
    PROBE_FACTOR = 4

    def __init__(self, g0b=None, base=()):
        """base: sids of structures already in the grammar (a grown grammar G_t); default G0."""
        self.b = g0b or G0Builder()
        self.base = tuple(base)
        self.probes = SIG_PROBES[:12]
        self.st = SG.by_sid()

    def g0(self):
        g = self.b()
        for sid in self.base:
            st = self.st[sid]
            L0.add_production(g, head_of(sid), structure_fn(st), 1 if st.param else 0)
        return g

    def with_structure(self, st):
        g = self.g0()
        L0.add_production(g, head_of(st.sid), structure_fn(st), 1 if st.param else 0)
        return g

    def search(self, g, train, qs, budget, cpu_cap, want):
        return S.run(g, train, qs, budget=budget, cpu_cap=cpu_cap, want=want)

    @staticmethod
    def defined(v):
        return v is not None and D.valid(v)

    @staticmethod
    def same(a, b):
        return a == b

    structures = staticmethod(SG.structures)
    seeded_order = staticmethod(SG.seeded_order)

    @staticmethod
    def consistent(st, pairs):
        return SG.consistent(st, [(tuple(tuple(r) for r in a), tuple(tuple(r) for r in b)) for a, b in pairs])


def grammar_with(g0b, sids):
    """G0 plus the given structures, in order (a grown grammar)."""
    return NaturalPlugin(g0b, sids).g0()
