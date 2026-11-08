"""Neutral identifiers (safeguard 1): every G0 primitive is shown to the proposer under a code (Q001, Q002, ...)
renamed by a seeded permutation per run seed and used consistently within that seed in every arm. arc-dsl names,
docstrings and comments never reach a prompt: operations are described only by their argument kinds and by one
executed example on a fixed small grid. Constants are shown as their values.
"""
import random

from cgrow import paths as P, lang0 as L0

P.ensure_import_paths()
from a2 import arcdsl as D            # noqa: E402

EXAMPLE = ((1, 2, 3), (4, 5, 6))
EXAMPLE_B = ((7, 8, 9), (1, 1, 2))
NEW = "NEW"


class Names:
    def __init__(self, g, seed):
        names = sorted({p.name for p in g.prods if p.head.startswith("f:")} |
                       {h[3:] for h in g.fn_leaves if h.startswith("fn:")})
        codes = [f"Q{i:03d}" for i in range(1, len(names) + 1)]
        random.Random(f"cgrow-names-{seed}").shuffle(codes)
        self.code = dict(zip(names, codes))
        self.seed = seed
        _, self.consts, _, _ = D.load()

    def const(self, name):
        v = self.consts[name]
        if isinstance(v, bool):
            return "True" if v else "False"
        return repr(v)

    def show(self, t):
        h = t[0]
        if h == "I":
            return "I"
        if h.startswith("c:"):
            return self.const(h[2:])
        if h.startswith("fn:"):
            return self.code.get(h[3:], "Q???")
        if h.startswith("f:inv_") or h.startswith("f:new"):
            name = NEW
        elif h.startswith("f:"):
            name = self.code.get(h[2:], "Q???")
        elif h == "@":
            return f"{self.show(t[1])}({', '.join(self.show(c) for c in t[2:])})"
        else:
            name = h
        return f"{name}({', '.join(self.show(c) for c in t[1:])})"

    def card(self, g):
        """Lines for the G0 operations whose inputs are grids and small integers and whose result is a grid."""
        fns = D.guarded(D.load()[0])
        lines = []
        for name, kinds in L0.grid_signature_prims(g):
            args, shown = [], []
            gi = 0
            for k in kinds:
                if k == "grid":
                    args.append(EXAMPLE if gi == 0 else EXAMPLE_B)
                    shown.append("grid")
                    gi += 1
                else:
                    args.append(2)
                    shown.append("int")
            try:
                out = fns[name](*args)
            except Exception:                                    # noqa: BLE001
                continue
            if D.tag(out) != "G" or not D.valid(out):
                continue
            ex_in = ", ".join(grid_inline(a) if isinstance(a, tuple) else str(a) for a in args)
            lines.append((self.code[name], f"{self.code[name]}({', '.join(shown)}) -> grid; example: "
                                           f"{ex_in} -> {grid_inline(out)}"))
        lines.sort()
        return [x for _, x in lines]

    def n_other(self, g):
        return len([p for p in g.prods if p.head.startswith("f:")]) - len(self.card(g))


def grid_inline(g):
    return "[" + ", ".join("[" + ",".join(str(v) for v in r) + "]" for r in g) + "]"


def grid_block(g, indent="  "):
    """One row per line, digits without separators (about one token per cell)."""
    return "\n".join(indent + "".join(str(v) for v in r) for r in g)
