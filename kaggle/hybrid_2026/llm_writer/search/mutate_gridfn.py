"""Typed mutations of grid-function programs. A program is the allowlist-checked syntax tree of
`llm_writer.gridfn.lang`; a mutation edits a COPY of that tree, prints it with `ast.unparse` and re-checks the text
with `llm_writer.gridfn.adapter.parse` (the full allowlist and name check). Nothing is compiled or executed as
Python: mutants run only in the grid-function interpreter's isolated worker.

Positions get a light type from their syntax and from the primitive registry (an int literal, a colour literal
0-9, a comparison, a call of a registered primitive with its signature, a keyword of a perception primitive, a
statement, the returned value), and a position is only replaced by a value of the same type. Families mirror
`mutate_cora.FAMILIES`:
- PARAMETER: int and bool literals (colours to the puzzle's colours), +/- swaps;
- SELECTOR: comparison operators, `and`/`or`, dropping a `not`;
- TRANSFORM: a primitive call replaced by another registered primitive of the same section, grid-op status and
  arity (for example flip_lr -> flip_ud, most_common_color -> least_common_color);
- OUTPUT: the returned grid wrapped in a grid-to-grid primitive (flip, rotate, transpose, trim);
- REPRESENTATION: perception keywords (`diag`, `multicolor`) flipped, `bg` changed;
- COMPOSE: drop one statement, or recolour the returned grid with `replace(..., a, b)`;
- SUBTREE: a primitive call replaced by a same-primitive-class call taken from another recorded program of the
  puzzle whose free names exist in the recipient (crossover).
"""
import ast
import copy
import re

FAMILIES = ("PARAMETER", "SELECTOR", "TRANSFORM", "OUTPUT", "REPRESENTATION", "COMPOSE", "SUBTREE")
CMP_OPS = (ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE)
WRAPS = ("flip_lr", "flip_ud", "rot_cw", "rot_ccw", "rot180", "transpose", "trim")
REPR_KW = ("diag", "multicolor")


def _prims():
    from llm_writer.gridfn import prims as P
    return P.REGISTRY


def _arity(sig):
    m = re.match(r"\w+\((.*)\)", sig)
    if not m or not m.group(1).strip():
        return 0
    return sum(1 for a in m.group(1).split(",") if "=" not in a and a.strip() and not a.strip().startswith("*"))


def _groups():
    reg = _prims()
    g = {}
    for name, p in reg.items():
        g.setdefault((p.section, bool(p.grid_op), _arity(p.sig)), []).append(name)
    return {n: [m for m in g[(p.section, bool(p.grid_op), _arity(p.sig))] if m != n] for n, p in reg.items()}


_GROUPS = None


def substitutes(name):
    global _GROUPS
    if _GROUPS is None:
        _GROUPS = _groups()
    return _GROUPS.get(name, [])


class Library:
    """Donors for one puzzle: its colours and the primitive calls of the recorded programs."""

    def __init__(self, task, progs=()):
        from llm_writer.search.common import colours
        self.colours = colours(task)
        self.calls = []
        seen = set()
        reg = _prims()
        for p in progs:
            for n in ast.walk(p.checked.tree):
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in reg:
                    t = ast.unparse(n)
                    if t not in seen and len(t) < 160:
                        seen.add(t)
                        self.calls.append(n)


def _transform(tree):
    defs = [s for s in tree.body if isinstance(s, ast.FunctionDef) and s.name == "transform"]
    return defs[-1] if defs else None


def _names(tree):
    return {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | \
        {a.arg for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) for a in n.args.args}


def _sites(tree):
    """[(family, node, parent_list_or_None, index)] mutation sites of a checked tree."""
    reg = _prims()
    out = []
    for parent in ast.walk(tree):
        for field, value in ast.iter_fields(parent):
            items = value if isinstance(value, list) else [value]
            for i, n in enumerate(items):
                if not isinstance(n, ast.AST):
                    continue
                if isinstance(n, ast.Constant) and isinstance(n.value, (int, bool)):
                    out.append(("PARAMETER", n, None, None))
                elif isinstance(n, ast.Compare):
                    out.append(("SELECTOR", n, None, None))
                elif isinstance(n, ast.BoolOp):
                    out.append(("SELECTOR", n, None, None))
                elif isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.Not):
                    out.append(("SELECTOR", n, (parent, field), i if isinstance(value, list) else None))
                elif isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Add, ast.Sub)):
                    out.append(("PARAMETER", n, None, None))
                elif isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in reg:
                    out.append(("TRANSFORM", n, None, None))
                    out.append(("SUBTREE", n, (parent, field), i if isinstance(value, list) else None))
                    for kw in n.keywords:
                        if kw.arg in REPR_KW or kw.arg == "bg":
                            out.append(("REPRESENTATION", kw, None, None))
                elif isinstance(n, ast.Return) and n.value is not None:
                    out.append(("OUTPUT", n, None, None))
                if isinstance(value, list) and isinstance(n, ast.stmt) and not isinstance(n, (ast.Return,
                                                                                            ast.FunctionDef)):
                    out.append(("COMPOSE", n, (parent, field), i))
    return out


def _alt_int(rng, lib, v):
    if 0 <= v <= 9 and rng.random() < 0.7:
        opts = [c for c in lib.colours if c != v]
    else:
        opts = [x for x in (v - 2, v - 1, v + 1, v + 2) if x != v and -30 <= x <= 30]
    return rng.choice(opts) if opts else None


def _edit(tree, site, rng, lib):
    fam, n, where, idx = site
    reg = _prims()
    if fam == "PARAMETER":
        if isinstance(n, ast.Constant):
            if isinstance(n.value, bool):
                n.value = not n.value
                return "flip bool"
            new = _alt_int(rng, lib, n.value)
            if new is None:
                return None
            old, n.value = n.value, new
            return f"int {old}->{new}"
        n.op = ast.Sub() if isinstance(n.op, ast.Add) else ast.Add()
        return "+/- swap"
    if fam == "SELECTOR":
        if isinstance(n, ast.Compare):
            j = rng.randrange(len(n.ops))
            opts = [o for o in CMP_OPS if not isinstance(n.ops[j], o)]
            n.ops[j] = rng.choice(opts)()
            return f"compare op {j}"
        if isinstance(n, ast.BoolOp):
            n.op = ast.Or() if isinstance(n.op, ast.And) else ast.And()
            return "and/or swap"
        parent, field = where
        if idx is None:
            setattr(parent, field, n.operand)
        else:
            getattr(parent, field)[idx] = n.operand
        return "drop not"
    if fam == "TRANSFORM":
        subs = substitutes(n.func.id)
        if not subs:
            return None
        old = n.func.id
        n.func.id = rng.choice(subs)
        return f"{old}->{n.func.id}"
    if fam == "REPRESENTATION":
        if isinstance(n.value, ast.Constant) and isinstance(n.value.value, bool):
            n.value.value = not n.value.value
            return f"{n.arg} flipped"
        if n.arg == "bg":
            n.value = ast.Constant(rng.choice(lib.colours))
            return "bg changed"
        return None
    if fam == "OUTPUT":
        w = rng.choice(WRAPS)
        n.value = ast.Call(func=ast.Name(id=w, ctx=ast.Load()), args=[n.value], keywords=[])
        return f"wrap return in {w}"
    if fam == "COMPOSE":
        parent, field = where
        body = getattr(parent, field)
        if rng.random() < 0.6 and len(body) > 1:
            del body[idx]
            return f"drop statement {idx}"
        ret = [s for s in ast.walk(tree) if isinstance(s, ast.Return) and s.value is not None]
        if not ret or len(lib.colours) < 2:
            return None
        a, b = rng.sample(lib.colours, 2)
        r = rng.choice(ret)
        r.value = ast.Call(func=ast.Name(id="replace", ctx=ast.Load()),
                           args=[r.value, ast.Constant(a), ast.Constant(b)], keywords=[])
        return f"replace({a}->{b}) on return"
    if fam == "SUBTREE":
        if not lib.calls or where is None:
            return None
        names = _names(tree)
        p = reg[n.func.id]
        cands = [c for c in lib.calls if reg[c.func.id].grid_op == p.grid_op and ast.unparse(c) != ast.unparse(n)
                 and {x.id for x in ast.walk(c) if isinstance(x, ast.Name)} <= names | set(reg)]
        if not cands:
            return None
        donor = copy.deepcopy(rng.choice(cands))
        parent, field = where
        if idx is None:
            setattr(parent, field, donor)
        else:
            getattr(parent, field)[idx] = donor
        return f"call {n.func.id} <- {donor.func.id}"
    return None


def propose(prog, family, rng, lib, focus=None, tries=12):     # noqa: ARG001 (no rule index in this language)
    """One mutant (Program, label) of family `family`, re-checked by the allowlist parser, or (None, None)."""
    from llm_writer.gridfn import adapter as GA
    base = prog.checked.tree
    for _ in range(tries):
        tree = copy.deepcopy(base)
        sites = [s for s in _sites(tree) if s[0] == family]
        if not sites:
            return None, None
        site = rng.choice(sites)
        try:
            label = _edit(tree, site, rng, lib)
        except (IndexError, ValueError, TypeError, AttributeError):
            label = None
        if label is None:
            continue
        try:
            src = ast.unparse(ast.fix_missing_locations(tree))
            child = GA.parse(src, getattr(prog, "dialect", "gridfn-1"))   # a gridfn-2 parent keeps its dialect
        except (ValueError, RecursionError, SyntaxError):
            continue
        if child.key() != prog.key():
            return child, f"{family}:{label}"
    return None, None


def mutable(prog):
    return getattr(prog, "checked", None) is not None and _transform(prog.checked.tree) is not None
