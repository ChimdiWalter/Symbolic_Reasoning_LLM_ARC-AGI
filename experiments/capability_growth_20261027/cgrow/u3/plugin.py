"""List-domain plug-in for cgrow/selfext_core.py (U3)."""
import random

from cgrow.u3 import listdsl as LD, lschema as LS


def probe_lists(n=12, seed=20261102):
    """Generic seeded probe lists: lengths 0-9, values from 0-9 or 0-99, some with repeats."""
    r = random.Random(seed)
    out = []
    for i in range(n):
        ln = r.randint(0, 9) if i else 0
        hi = 9 if i % 2 else 99
        xs = [r.randint(0, hi) for _ in range(ln)]
        if i % 3 == 0 and xs:
            xs.append(xs[0])
        out.append(tuple(xs))
    return out


class ListPlugin:
    BASE_BUDGET, BASE_CPU = 150_000, 20.0
    NOVELTY_BUDGET, NOVELTY_CPU = 200_000, 10.0
    PROBE_FACTOR = 4
    invert_tests = [(1, 2, 3), (3, 1, 2, 2), (5, 0, 7, 1, 4), (9,)]

    def __init__(self, removed):
        self.removed = tuple(removed)
        self._g0 = LD.Grammar(self.removed)
        self.probes = probe_lists()

    def g0(self):
        return self._g0.copy()

    def with_structure(self, st):
        def fn(xs, *ints):
            if st.param and (len(ints) != 1 or ints[0] not in LS.KS):
                raise LD.Undefined()
            out = st(xs, *ints)
            if out is None:
                raise LD.Undefined()
            return out
        return self.g0().add("sig_" + st.sid.replace(":", "_"), fn, 1 if st.param else 0)

    def with_reference(self, name):
        g = self.g0()
        a, r, f = LD.OPS[name]
        g.prods.append(LD.Prod(name, a, r, f))
        return g

    def search(self, g, train, qs, budget, cpu_cap, want):
        return LD.search(g, train, qs, budget=budget, cpu_cap=cpu_cap, want=want)

    @staticmethod
    def defined(v):
        return v is not None

    @staticmethod
    def same(a, b):
        return tuple(a) == tuple(b)

    structures = staticmethod(LS.structures)
    seeded_order = staticmethod(LS.seeded_order)

    @staticmethod
    def consistent(st, pairs):
        return LS.consistent(st, [(tuple(a), tuple(b)) for a, b in pairs])

    @staticmethod
    def unary_ops(g):
        out = {}
        for p in g.prods:
            if p.argtypes == ("L",) and p.rettype == "L" and not p.name.startswith("sig_"):
                out[p.name] = (lambda xs, p=p: LD.apply_op(p.fn, "L", [tuple(xs)]))
        return out

    @staticmethod
    def unary_ops_with_constants(g):
        out = {}
        for p in g.prods:
            if p.argtypes == ("L", "I") and p.rettype == "L" and not p.name.startswith("sig_"):
                for c in range(10):
                    out[f"{p.name}_{c}"] = (lambda xs, p=p, c=c: LD.apply_op(p.fn, "L", [tuple(xs), c]))
        return out

    @staticmethod
    def similarity(x, y):
        x, y = tuple(x), tuple(y)
        if not y:
            return 1.0 if not x else 0.0
        if not x:
            return 0.0
        return sum(y[i] == x[min(len(x) - 1, i * len(x) // len(y))] for i in range(len(y))) / len(y)
