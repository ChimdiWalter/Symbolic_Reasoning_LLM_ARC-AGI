"""Candidate operations from a solution program (a tree over A2's arc-dsl grammar) and the operation objects.

A solution found on a source task is a tree such as ("f:paint", ("I",), ("f:vmirror", ("f:merge", ("f:fgpartition",
("I",))))). Candidates, in this order:
  whole   the tree itself, as the unary operation grid -> tree[I := grid];
  sub     every proper subtree that contains the input leaf I, has at least one primitive application, and is
          grid-valued on the source task's inputs (and on the demonstrations' outputs' shapes nothing is assumed);
  abs     for the whole tree and each such subtree, every variant with ONE integer-constant leaf replaced by an
          integer parameter (the production then takes an Integer argument: cost 3 plus the argument's cost).
Candidates are identified by their tree; a candidate seen on an earlier source task is not repeated, but every source
task that produced it is recorded.

An operation object quacks like a schema structure of the construction test (sid, param, thetas(), __call__(grid,
*theta) -> grid or None), so the growth study's gates (novelty, retry, regression) run on it unchanged.
"""
from ngrow import plugin as PL                                                 # noqa: F401  (import paths)
from cgrow import lang0 as L0                                                  # noqa: E402
from a2 import arcdsl as D                                                     # noqa: E402

INT_VALUES = (-2, -1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10)                      # G0's integer constants
PARAM = ("#0",)


def contains_I(t):
    return t[0] == "I" or any(contains_I(c) for c in t[1:])


def n_apps(t):
    return (1 if t[0].startswith("f:") or t[0] == "@" else 0) + sum(n_apps(c) for c in t[1:])


def subtrees(t):
    out = [t]
    for c in t[1:]:
        out.extend(subtrees(c))
    return out


def int_const_positions(t, consts, path=()):
    """Paths of leaves c:NAME whose constant is a plain integer."""
    h = t[0]
    if len(t) == 1:
        if h.startswith("c:") and type(consts[h[2:]]) is int:
            return [path]
        return []
    out = []
    for i, c in enumerate(t[1:], 1):
        out.extend(int_const_positions(c, consts, path + (i,)))
    return out


def replace_at(t, path, leaf):
    if not path:
        return leaf
    i = path[0]
    return t[:i] + (replace_at(t[i], path[1:], leaf),) + t[i + 1:]


class LibOp:
    """One library operation: a tree with the input leaf I and at most one parameter leaf #0."""
    __slots__ = ("sid", "tree", "param", "kind", "sources", "family", "ev", "text")

    def __init__(self, sid, tree, kind, source, family, ev):
        self.sid, self.tree, self.kind, self.ev = sid, tree, kind, ev
        self.param = any(s[0] == "#0" for s in subtrees(tree))
        self.sources, self.family = [source], family
        self.text = D.show(tree)

    def thetas(self):
        return [(v,) for v in INT_VALUES] if self.param else [()]

    def __call__(self, g, *th):
        try:
            v = self.ev._ev(self.tree, g, tuple(th), {}, None)
        except Exception:                                                  # noqa: BLE001
            return None
        if not D.valid(v) or D.tag(v) != "G":
            return None
        return v

    def describe(self):
        return {"sid": self.sid, "program": self.text, "param": self.param, "kind": self.kind,
                "sources": list(self.sources), "family": self.family, "tree": self.tree}


def grid_valued(tree, inputs, ev):
    for x in inputs:
        try:
            v = ev._ev(tree, x, (), {}, None)
        except Exception:                                                  # noqa: BLE001
            return False
        if not D.valid(v) or D.tag(v) != "G":
            return False
    return True


def candidates_of(tree, inputs, consts, ev):
    """[(kind, tree)] in the fixed order: whole, subs, then one-constant abstractions of each."""
    base = [("whole", tree)]
    for s in subtrees(tree)[1:]:
        if contains_I(s) and n_apps(s) >= 1 and grid_valued(s, inputs, ev) and s not in [b for _, b in base]:
            base.append(("sub", s))
    out = list(base)
    for kind, t in base:
        for path in int_const_positions(t, consts):
            a = replace_at(t, path, PARAM)
            if a not in [b for _, b in out]:
                out.append(("abs", a))
    return out


def production_fn(op):
    """The production function (identical in form to the construction test's)."""
    def f(grid, *ints):
        if D.tag(grid) != "G":
            raise D.Bad("type")
        if op.param and (len(ints) != 1 or type(ints[0]) is not int or ints[0] not in INT_VALUES):
            raise D.Bad("param")
        out = op(grid, *ints)
        if out is None:
            raise D.Bad("undefined")
        return out
    return f


def head_of(sid):
    return "f:" + "".join(c if c.isalnum() else "_" for c in sid)


class LibraryPlugin(PL.NaturalPlugin):
    """The study A plug-in with the candidate operations in place of the schema structures. The grammar builder
    must be this module's G0Builder (seed-independent enumeration order)."""

    def __init__(self, g0b, ops, base=()):
        super().__init__(g0b)
        assert isinstance(g0b, G0Builder), "use ngb.ops.G0Builder"
        self.ops = list(ops)
        self.base_ops = list(base)
        self.st = {o.sid: o for o in self.ops}

    def structures(self):
        return list(self.ops)

    def g0(self):
        g = self.b()
        for o in self.base_ops:
            L0.add_production(g, head_of(o.sid), production_fn(o), 1 if o.param else 0)
        return g

    def with_structure(self, op):
        g = self.g0()
        L0.add_production(g, head_of(op.sid), production_fn(op), 1 if op.param else 0)
        return g


def grammar_with(g0b, ops):
    return LibraryPlugin(g0b, [], ops).g0()


# ------------------------------------------------------------------ deterministic enumeration order
class SortedTags(frozenset):
    """A frozenset of type tags whose iteration order is sorted. A2's enumerator iterates a production's argument
    tags (`for tg in tags` in a2/bus.py) when it assembles the candidate pools, and a plain frozenset's iteration
    order depends on the interpreter's hash seed; with a budget-stopped search the enumeration order decides which
    programs are reached before the budget ends. Sorting the tags makes the order independent of the seed. The set's
    membership, equality and hashing are unchanged."""
    __slots__ = ()

    def __iter__(self):
        return iter(sorted(frozenset.__iter__(self)))


def deterministic(g):
    """Replace every production's argument tags of grammar g by SortedTags (in place; returns g)."""
    for p in g.prods:
        p.argtags = tuple(SortedTags(t) for t in p.argtags)
    return g


class G0Builder(PL.G0Builder):
    """Study A's G0 builder with a seed-independent enumeration order (SortedTags on every production)."""

    def __init__(self):
        super().__init__()
        deterministic(self.g)


def ops_from_json(doc, ev):
    """Library operations from their frozen description (library.json or shuffled.json entries)."""
    from a2.corpus import tree_from_json
    out = []
    for d in doc:
        o = LibOp(d["sid"], tree_from_json(d["tree"]), d["kind"], d["sources"][0], d["family"], ev)
        o.sources = list(d["sources"])
        out.append(o)
    return out
