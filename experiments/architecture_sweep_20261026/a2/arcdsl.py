"""arc-dsl as a typed program language for A2 and A3: loader, tree IR, faithful translation of verified solvers.

arc-dsl (michaelhodel/arc-dsl, commit 635de49, MIT License, Copyright (c) 2023 Michael Hodel) is executed from the
read-only download in outputs/search_components/resources_20261026/github/arc-dsl. Its files are exec'd by path into
private namespaces (no sys.path entry, nothing imported by name from that folder). Licence notice: see LICENSE there.

Tree IR (nested tuples, hashable): (head, *children)
    ('I',)            the input grid             ('c:NAME',)  an arc-dsl constant (T, F, ZERO, DOWN, ...)
    ('fn:NAME',)      a primitive used as a value ('f:NAME', a, b, ...)  primitive application
    ('L:NAME', a, ..) library production        ('@', fexpr, a, ...)    call of a computed function
    ('#k',)           parameter k of a library body;   ('R:NAME',) a representation leaf (A3: OBJS, BG)
Solver translation inlines each variable at its uses (straight-line code -> expression tree). Only solvers of
S_train and S_select tasks are ever translated; S_confirm and excluded tasks are never touched.
"""
import ast
import os

DSL_DIR = ("/path/to/repository/outputs/search_components/"
           "resources_20261026/github/arc-dsl")
FILES = ("arc_types.py", "dsl.py", "constants.py", "solvers.py", "LICENSE")

_NS = {}


def _exec_file(name, ns):
    path = os.path.join(DSL_DIR, name)
    with open(path, encoding="utf-8") as f:
        src = f.read()
    mod = ast.parse(src)                                      # the internal star-imports are replaced by the
    mod.body = [s for s in mod.body if not (isinstance(s, ast.ImportFrom)   # pre-populated namespace
                                            and s.module in ("arc_types", "dsl", "constants"))]
    exec(compile(mod, path, "exec"), ns)                      # noqa: S102 (pure-function MIT modules, audited)
    return src


def load():
    """(dsl namespace, constants dict, dsl source, solvers source). Cached."""
    if _NS:
        return _NS["dsl"], _NS["consts"], _NS["dsl_src"], _NS["solvers_src"]
    types_ns = {}
    _exec_file("arc_types.py", types_ns)
    dsl_ns = dict(types_ns)
    dsl_src = _exec_file("dsl.py", dsl_ns)
    const_ns = {}
    _exec_file("constants.py", const_ns)
    consts = {k: v for k, v in const_ns.items() if k.isupper() or k in ("T", "F")}
    with open(os.path.join(DSL_DIR, "solvers.py"), encoding="utf-8") as f:
        solvers_src = f.read()
    _NS.update(dsl=dsl_ns, consts=consts, dsl_src=dsl_src, solvers_src=solvers_src)
    return dsl_ns, consts, dsl_src, solvers_src


def file_hashes():
    import hashlib
    out = {}
    for n in FILES:
        with open(os.path.join(DSL_DIR, n), "rb") as f:
            out[n] = hashlib.sha256(f.read()).hexdigest()
    return out


def prim_signatures():
    """name -> list of parameter annotation names (from dsl.py source)."""
    _, _, src, _ = load()
    sigs = {}
    for f in ast.parse(src).body:
        if isinstance(f, ast.FunctionDef):
            sigs[f.name] = [ast.unparse(a.annotation) if a.annotation is not None else "Any" for a in f.args.args]
    return sigs


def prim_returns():
    """name -> return annotation name ('Callable' marks closure constructors)."""
    _, _, src, _ = load()
    return {f.name: (ast.unparse(f.returns) if f.returns is not None else "Any")
            for f in ast.parse(src).body if isinstance(f, ast.FunctionDef)}


# ------------------------------------------------------------------ runtime type tags
def tag(v):
    t = type(v)
    if t is bool:
        return "B"
    if t is int:
        return "I"
    if t is tuple:
        if not v:
            return "E"
        v0 = v[0]
        t0 = type(v0)
        if t0 is tuple:
            if v0 and type(v0[0]) is int:
                return "G"
            return "GT" if v0 and type(v0[0]) is tuple else "TT"
        if t0 is int and len(v) == 2:
            return "T"
        return "TU"
    if t is frozenset:
        if not v:
            return "E"
        x = next(iter(v))
        tx = type(x)
        if tx is tuple and len(x) == 2:
            if type(x[1]) is tuple:
                return "O" if type(x[0]) is int else "FU"
            return "X" if type(x[0]) is int and type(x[1]) is int else "FU"
        if tx is frozenset:
            if not x:
                return "XS"
            y = next(iter(x))
            if type(y) is tuple and len(y) == 2:
                return "S" if type(y[1]) is tuple else "XS"
            return "FU"
        if tx is int:
            return "Z"
        return "FU"
    if callable(v):
        return "F"
    return "U"


CONT = frozenset({"S", "O", "X", "Z", "XS", "G", "GT", "T", "TT", "TU", "FU", "E"})
ALL = CONT | {"I", "B"}                  # 'Any' takes values, not functions (Callable parameters take "F")
ANN = {"Grid": {"G"}, "Object": {"O"}, "Objects": {"S"}, "Indices": {"X"}, "Patch": {"O", "X"},
       "Piece": {"G", "O", "X"}, "Element": {"O", "G"}, "Integer": {"I"}, "Boolean": {"B"}, "IntegerTuple": {"T"},
       "Numerical": {"I", "T"}, "IntegerSet": {"Z"}, "Callable": {"F"}, "Any": ALL, "Container": CONT,
       "ContainerContainer": {"S", "XS", "GT", "TT"}, "FrozenSet": {"S", "O", "X", "Z", "XS", "FU", "E"},
       "Tuple": {"G", "GT", "T", "TT", "TU", "E"}, "TupleTuple": {"G", "GT", "TT"}, "IndicesSet": {"XS"},
       "Iterable": CONT, "Cell": {"TU"}}


def arg_tags(ann):
    return frozenset(ANN.get(ann, ALL))


# ------------------------------------------------------------------ guards (search only; translation runs raw)
MAXG = 30
MAXC = 2000
MAXI = 1000


class Bad(Exception):
    pass


def valid(v):
    """Reject values the search must not keep: grids over 30 x 30 or with non-colour cells, huge containers/ints."""
    t = type(v)
    if t is int:
        return -MAXI <= v <= MAXI
    if t is tuple:
        if v and type(v[0]) is tuple and v[0] and type(v[0][0]) is int:        # grid
            if len(v) > MAXG or len(v[0]) > MAXG:
                return False
            w = len(v[0])
            for r in v:
                if type(r) is not tuple or len(r) != w:
                    return False
            return True
        return len(v) <= MAXC
    if t is frozenset:
        return len(v) <= MAXC
    return True


def guarded(dsl):
    """Copies of size-creating primitives that refuse arguments producing oversized values before computing them."""
    g = dict(dsl)

    def _dims(x):
        return x if isinstance(x, tuple) and len(x) == 2 and all(type(a) is int for a in x) else None

    def canvas(value, dimensions):
        d = _dims(dimensions)
        if d is None or not (0 < d[0] <= MAXG and 0 < d[1] <= MAXG):
            raise Bad("canvas")
        return dsl["canvas"](value, dimensions)

    def upscale(element, factor):
        if type(factor) is not int or not 0 < factor <= MAXG:
            raise Bad("upscale")
        if isinstance(element, tuple) and element and (len(element) * factor > MAXG or len(element[0]) * factor > MAXG):
            raise Bad("upscale")
        return dsl["upscale"](element, factor)

    def hupscale(grid, factor):
        if type(factor) is not int or not 0 < factor or not grid or len(grid[0]) * factor > MAXG:
            raise Bad("hupscale")
        return dsl["hupscale"](grid, factor)

    def vupscale(grid, factor):
        if type(factor) is not int or not 0 < factor or len(grid) * factor > MAXG:
            raise Bad("vupscale")
        return dsl["vupscale"](grid, factor)

    def power(function, n):
        if type(n) is not int or not 0 < n <= 10:
            raise Bad("power")
        return dsl["power"](function, n)

    def repeat(item, num):
        if type(num) is not int or not 0 <= num <= MAXG:
            raise Bad("repeat")
        return dsl["repeat"](item, num)

    def interval(start, stop, step):
        if not all(type(x) is int for x in (start, stop, step)) or step == 0 or abs(stop - start) > 64 * abs(step):
            raise Bad("interval")
        return dsl["interval"](start, stop, step)

    def product(a, b):
        if len(a) * len(b) > MAXC:
            raise Bad("product")
        return dsl["product"](a, b)

    def prapply(function, a, b):
        if len(a) * len(b) > MAXC:
            raise Bad("prapply")
        return dsl["prapply"](function, a, b)

    for f in (canvas, upscale, hupscale, vupscale, power, repeat, interval, product, prapply):
        g[f.__name__] = f
    return g


# ------------------------------------------------------------------ tree IR
def size(t):
    return 1 + sum(size(c) for c in t[1:])


def prim_count(t):
    """Primitive applications in a tree (library calls are counted by the caller with their body counts)."""
    return (1 if t[0][:2] in ("f:", "@") or t[0] == "@" else 0) + sum(prim_count(c) for c in t[1:])


def show(t):
    h = t[0]
    if len(t) == 1:
        return h.split(":", 1)[-1] if ":" in h else h
    name = h.split(":", 1)[-1] if ":" in h else h
    return f"{name}({', '.join(show(c) for c in t[1:])})"


class Evaluator:
    """Evaluate a tree on one input with a memo; `lib` maps library names to (arity, body)."""

    def __init__(self, fns, consts, lib=None, reps=None):
        self.fns, self.consts, self.lib, self.reps = fns, consts, lib or {}, reps or {}

    def run(self, t, I, rep=None):
        memo = {}
        return self._ev(t, I, (), memo, rep)

    def _ev(self, t, I, params, memo, rep):
        key = (t, params) if params else t
        if key in memo:
            return memo[key]
        h = t[0]
        if h == "I":
            v = I
        elif h.startswith("c:"):
            v = self.consts[h[2:]]
        elif h.startswith("fn:"):
            v = self.fns[h[3:]]
        elif h.startswith("#"):
            v = params[int(h[1:])]
        elif h.startswith("R:"):
            v = rep[h[2:]]
        elif h.startswith("f:"):
            v = self.fns[h[2:]](*[self._ev(c, I, params, memo, rep) for c in t[1:]])
        elif h == "@":
            f = self._ev(t[1], I, params, memo, rep)
            v = f(*[self._ev(c, I, params, memo, rep) for c in t[2:]])
        elif h.startswith("L:"):
            ar, body = self.lib[h[2:]]
            args = tuple(self._ev(c, I, params, memo, rep) for c in t[1:])
            v = self._ev(body, I, args, {}, rep)
        else:
            raise ValueError(h)
        memo[key] = v
        return v


# ------------------------------------------------------------------ solver translation
def translate(fdef, dsl_names, consts):
    """One `def solve_<id>(I)` -> tree; raises ValueError on a construct outside straight-line calls."""
    env = {"I": ("I",)}
    out = None

    def arg(a):
        if isinstance(a, ast.Name):
            if a.id in env:
                return env[a.id]
            if a.id in consts:
                return ("c:" + a.id,)
            if a.id in dsl_names:
                return ("fn:" + a.id,)
        raise ValueError(f"argument {ast.unparse(a)}")

    for st in fdef.body:
        if isinstance(st, ast.Assign) and len(st.targets) == 1 and isinstance(st.targets[0], ast.Name) \
                and isinstance(st.value, ast.Call) and not st.value.keywords:
            fn = st.value.func
            args = tuple(arg(a) for a in st.value.args)
            if isinstance(fn, ast.Name) and fn.id in env:
                node = ("@", env[fn.id]) + args
            elif isinstance(fn, ast.Name) and fn.id in dsl_names:
                node = ("f:" + fn.id,) + args
            else:
                raise ValueError(f"call {ast.unparse(fn)}")
            env[st.targets[0].id] = node
        elif isinstance(st, ast.Return) and isinstance(st.value, ast.Name):
            out = env[st.value.id]
        else:
            raise ValueError(f"statement {ast.unparse(st)[:60]}")
    if out is None:
        raise ValueError("no return")
    return out


def translate_solvers(task_ids):
    """{task_id: tree} for the solvers of `task_ids` only (others are never parsed into programs)."""
    dsl, consts, _, src = load()
    names = {k for k, v in dsl.items() if callable(v) and not k.startswith("_") and k[0].islower()}
    want = set(task_ids)
    out, errors = {}, {}
    for f in ast.parse(src).body:
        if isinstance(f, ast.FunctionDef) and f.name.startswith("solve_") and f.name[6:] in want:
            try:
                out[f.name[6:]] = translate(f, names, consts)
            except ValueError as e:
                errors[f.name[6:]] = str(e)
    return out, errors


def solver_function(task_id):
    """The original solvers.py function (for the faithfulness test); executed in a private namespace."""
    dsl, consts, _, src = load()
    want = "solve_" + task_id
    for f in ast.parse(src).body:
        if isinstance(f, ast.FunctionDef) and f.name == want:
            ns = dict(dsl)
            ns.update(consts)
            exec(compile(ast.Module(body=[f], type_ignores=[]), "solvers.py", "exec"), ns)   # noqa: S102
            return ns[want]
    raise KeyError(task_id)


def to_grid(g):
    return tuple(tuple(r) for r in g)
