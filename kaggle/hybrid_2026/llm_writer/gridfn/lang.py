"""The grid-function language, version gridfn-1: parsing and the explicit allowlist check.

A program is text in a strict subset of Python that defines `def transform(grid): ...` and, optionally, helper
functions and top-level constants. `check(src)` parses it with Python's `ast` module (the text is never compiled
or executed), then:
1. checks every node against ALLOWED (anything else is a DisallowedNode error, with a hint for the usual cases:
   imports, lambda, classes, try, with, global, attribute access, f-strings, *args, dunder names);
2. allows attribute syntax only as a call of a whitelisted container method (`row.append(x)`, `d.get(k)`, ...);
3. resolves every name lexically (parameters, assignments and loop targets of each function, comprehension
   targets, top-level functions and constants, then SAFE BUILTINS, the PRIMITIVES and the direction CONSTANTS);
   an unknown name is an UnknownName error with the closest known name as a hint;
4. checks the structure: `transform` defined at the top level with one grid parameter, top level holding only
   `def` and constant assignments, `return` only inside functions, `break`/`continue` only inside loops, bounded
   source length, node count, nesting depth, string and integer literal sizes;
5. normalizes the tree (docstrings, bare constant statements and type annotations removed; annotations are checked
   for syntax only and never evaluated) and prints its canonical text with `ast.unparse`.

The result (`Checked`) carries the normalized tree, the canonical text, the node count, the names used and the
sha256 of the source and of the canonical text (provenance).
"""
import ast
import difflib
import hashlib

from . import npx as NPX
from . import prims as P

VERSION = "gridfn-1"
MAX_SRC_CHARS = 8000
MAX_NODES = 3000
MAX_DEPTH = 50
MAX_STR = 64
MAX_INT_LITERAL = 10 ** 12

PARSE_KINDS = ("SyntaxError", "DisallowedNode", "UnknownName")
RUN_KINDS = ("Timeout", "StepLimit", "RuntimeFault", "ShapeError", "ValueError")
KINDS = PARSE_KINDS + RUN_KINDS

#: safe builtins (implemented by interp.BUILTINS; `print` is accepted and ignored)
BUILTIN_NAMES = ("abs", "all", "any", "bool", "deepcopy", "dict", "divmod", "enumerate", "filter", "int", "len",
                 "list", "map", "max", "min", "print", "range", "reversed", "round", "set", "sorted", "sum", "tuple",
                 "zip")
#: container methods callable with attribute syntax, per receiver type (implemented by interp.METHODS)
METHODS = {
    "list": ("append", "extend", "insert", "pop", "remove", "index", "count", "copy", "reverse", "sort", "clear"),
    "dict": ("get", "keys", "values", "items", "setdefault", "update", "copy", "pop"),
    "set": ("add", "discard", "remove", "union", "intersection", "difference", "issubset", "issuperset", "update",
            "copy"),
    "tuple": ("index", "count"),
}
METHOD_NAMES = frozenset(m for ms in METHODS.values() for m in ms)
PRIMITIVE_NAMES = tuple(P.REGISTRY)
CONSTANT_NAMES = tuple(P.CONSTANTS)

ALLOWED = frozenset((
    "Module", "FunctionDef", "arguments", "arg", "Return", "Assign", "AugAssign", "AnnAssign", "For", "While", "If",
    "Expr", "Pass", "Break", "Continue",
    "BoolOp", "BinOp", "UnaryOp", "IfExp", "Compare", "Call", "keyword", "Name", "Constant", "List", "Tuple", "Dict",
    "Set", "Subscript", "Slice", "ListComp", "SetComp", "DictComp", "GeneratorExp", "comprehension", "Attribute",
    "Load", "Store",
    "And", "Or", "Add", "Sub", "Mult", "Div", "FloorDiv", "Mod", "Pow", "LShift", "RShift", "BitOr", "BitXor",
    "BitAnd", "UAdd", "USub", "Not", "Invert", "Eq", "NotEq", "Lt", "LtE", "Gt", "GtE", "Is", "IsNot", "In", "NotIn",
))
_IMPORT_HINT = "imports are not allowed (there is no numpy): grids are lists of lists; use the card's functions"
HINTS = {
    "Import": _IMPORT_HINT, "ImportFrom": _IMPORT_HINT,
    "Lambda": "lambda is not allowed: define a helper function with def and pass its name",
    "ClassDef": "classes are not allowed",
    "With": "with is not allowed", "AsyncWith": "with is not allowed",
    "Try": "try/except is not allowed: check the condition with if instead", "TryStar": "try is not allowed",
    "Raise": "raise is not allowed", "Assert": "assert is not allowed: use if",
    "Global": "global is not allowed: pass values as arguments", "Nonlocal": "nonlocal is not allowed",
    "Delete": "del is not allowed", "Del": "del is not allowed",
    "AsyncFunctionDef": "async functions are not allowed", "Await": "await is not allowed",
    "Yield": "yield is not allowed: build and return a list", "YieldFrom": "yield is not allowed",
    "NamedExpr": "the := operator is not allowed",
    "JoinedStr": "f-strings are not allowed", "FormattedValue": "f-strings are not allowed",
    "Starred": "* unpacking is not allowed: pass the arguments one by one (for zip(*grid) use "
               "transpose(grid))",
    "Match": "match is not allowed: use if/elif", "MatMult": "the @ operator is not allowed",
    "TypeAlias": "type aliases are not allowed",
}
_ATTR_HINTS = {"shape": "use shape(g)", "deepcopy": "use copy(g)", "copy": "use copy(g)", "T": "use transpose(g)",
               "tolist": "grids are already lists", "flatten": "use [v for row in g for v in row]"}


#: the dialect of the current check: "gridfn-1" (no imports, no attributes) or "gridfn-2" (adds the audited numpy
#: subset of npx.py: `import numpy as np` lowered to a binding, np.<function>, array attributes and methods)
_DIALECT = ["gridfn-1"]
NP_NAMES = ("np", "numpy")
COLLECTION_NAMES = ("Counter", "defaultdict", "deque", "float")
EXTRA_METHODS = ("popleft", "appendleft", "most_common", "pop")


def _np_ok():
    return _DIALECT[0] == "gridfn-2"


class GridFnError(ValueError):
    """A typed error of the grid-function language; str() is the message returned to the program's author."""

    def __init__(self, kind, message, line=None):
        self.kind, self.message, self.line = kind, message, line
        super().__init__(self.text())

    def text(self):
        return f"{self.kind}: {self.message}" + (f" (line {self.line})" if self.line else "")


def _err(kind, message, node=None):
    return GridFnError(kind, message, getattr(node, "lineno", None))


class Checked:
    """A program that passed the check: normalized tree, canonical text and provenance."""
    __slots__ = ("tree", "canonical", "nodes", "functions", "primitives", "builtins", "methods", "src_sha256",
                 "canonical_sha256")

    def __init__(self, tree, canonical, nodes, functions, primitives, builtins, methods, src_sha256):
        self.tree, self.canonical, self.nodes = tree, canonical, nodes
        self.functions, self.primitives, self.builtins, self.methods = functions, primitives, builtins, methods
        self.src_sha256 = src_sha256
        self.canonical_sha256 = sha256(canonical)

    def info(self):
        return {"ok": True, "language": VERSION, "nodes": self.nodes, "functions": list(self.functions),
                "primitives": list(self.primitives), "builtins": list(self.builtins), "methods": list(self.methods),
                "src_sha256": self.src_sha256, "canonical_sha256": self.canonical_sha256}


def sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ------------------------------------------------------------------ size limits (iterative: safe on deep trees)
def _size_and_depth(tree):
    n, deepest = 0, 0
    stack = [(tree, 1)]
    while stack:
        node, d = stack.pop()
        n += 1
        deepest = max(deepest, d)
        if n > MAX_NODES * 4 or deepest > MAX_DEPTH * 4:
            break
        for child in ast.iter_child_nodes(node):
            stack.append((child, d + 1))
    return n, deepest


_UNCOUNTED = (ast.expr_context, ast.operator, ast.boolop, ast.unaryop, ast.cmpop)


def count_nodes(tree):
    """Program size: syntax nodes other than contexts and operators."""
    return sum(1 for n in ast.walk(tree) if not isinstance(n, _UNCOUNTED))


# ------------------------------------------------------------------ the allowlist check
def _check_annotation(node):
    """Annotations are never evaluated (they are removed); only plain type syntax is accepted."""
    if node is None:
        return
    for n in ast.walk(node):
        name = type(n).__name__
        if name not in ("Name", "Subscript", "Tuple", "List", "Constant", "Attribute", "BinOp", "BitOr", "Load",
                        "Index"):
            raise _err("DisallowedNode", "a type annotation may only name types, e.g. grid: list", node)
        if isinstance(n, ast.Name) and n.id.startswith("__") or isinstance(n, ast.Attribute) and \
                n.attr.startswith("__"):
            raise _err("DisallowedNode", "names with double underscores are not allowed", node)


def _name_ok(name, node):
    if name.startswith("__"):
        raise _err("DisallowedNode", f"names with double underscores ({name}) are not allowed", node)


class _Checker:
    def __init__(self):
        self.functions, self.prims, self.builtins, self.methods = set(), set(), set(), set()

    def node(self, node, loop=False, func=False):
        name = type(node).__name__
        if name == "Lambda" and _np_ok():                  # gridfn-2: lambda (plain parameters, one expression)
            a = node.args
            if a.vararg or a.kwarg or a.kwonlyargs or getattr(a, "posonlyargs", None):
                raise _err("DisallowedNode", "only plain lambda parameters are allowed", node)
            for p in a.args:
                _name_ok(p.arg, node)
            for d in a.defaults:
                self.node(d, loop, func)
            return self.node(node.body, False, True)
        if name not in ALLOWED:
            raise _err("DisallowedNode", HINTS.get(name, f"{name} is not part of the language"), node)
        m = getattr(self, "n_" + name, None)
        if m is not None:
            return m(node, loop, func)
        for child in ast.iter_child_nodes(node):
            self.node(child, loop, func)

    def body(self, stmts, loop, func):
        for s in stmts:
            self.node(s, loop, func)

    def n_FunctionDef(self, node, loop, func):
        _name_ok(node.name, node)
        if node.decorator_list:
            raise _err("DisallowedNode", "decorators are not allowed", node)
        if getattr(node, "type_params", None):
            raise _err("DisallowedNode", "type parameters are not allowed", node)
        a = node.args
        if a.vararg or a.kwarg or a.kwonlyargs or getattr(a, "posonlyargs", None):
            raise _err("DisallowedNode", "only plain parameters (with optional defaults) are allowed: no *args, "
                       "**kwargs or keyword-only parameters", node)
        for p in a.args:
            _name_ok(p.arg, node)
            _check_annotation(p.annotation)
        _check_annotation(node.returns)
        for d in a.defaults:
            self.node(d, loop, func)
        self.body(node.body, False, True)

    def n_Return(self, node, loop, func):
        if not func:
            raise _err("SyntaxError", "'return' outside a function", node)
        if node.value is not None:
            self.node(node.value, loop, func)

    def n_Break(self, node, loop, func):
        if not loop:
            raise _err("SyntaxError", "'break' outside a loop", node)

    n_Continue = n_Break

    def n_For(self, node, loop, func):
        self._target(node.target)
        self.node(node.iter, loop, func)
        self.body(node.body, True, func)
        self.body(node.orelse, loop, func)

    def n_While(self, node, loop, func):
        self.node(node.test, loop, func)
        self.body(node.body, True, func)
        self.body(node.orelse, loop, func)

    def n_AnnAssign(self, node, loop, func):
        _check_annotation(node.annotation)
        self._target(node.target)
        if node.value is not None:
            self.node(node.value, loop, func)

    def n_Assign(self, node, loop, func):
        for t in node.targets:
            self._target(t)
        self.node(node.value, loop, func)

    def n_AugAssign(self, node, loop, func):
        if type(node.op).__name__ not in ALLOWED:
            raise _err("DisallowedNode", HINTS.get(type(node.op).__name__, "operator not allowed"), node)
        self._target(node.target)
        self.node(node.value, loop, func)

    def _target(self, t):
        name = type(t).__name__
        if name == "Name":
            _name_ok(t.id, t)
        elif name in ("Tuple", "List"):
            for e in t.elts:
                self._target(e)
        elif name == "Subscript":
            self.node(t.value)
            self.node(t.slice)
        elif name == "Starred":
            raise _err("DisallowedNode", HINTS["Starred"], t)
        elif name == "Attribute":
            raise _err("DisallowedNode", f"assigning to an attribute (.{t.attr}) is not allowed", t)
        else:
            raise _err("DisallowedNode", f"cannot assign to {name}", t)

    def n_Expr(self, node, loop, func):
        self.node(node.value, loop, func)

    def n_Call(self, node, loop, func):
        f = node.func
        if _np_ok() and any(type(a).__name__ == "Starred" for a in node.args):
            if isinstance(f, ast.Attribute):
                raise _err("CompatibilityGap", "f(*args) on a method is outside the supported subset", node)
            node = ast.Call(f, [a.value if type(a).__name__ == "Starred" else a for a in node.args], node.keywords)
        if isinstance(f, ast.Attribute):
            if _np_ok() and (_np_attr(f) or f.attr in NPX.METHODS or f.attr in EXTRA_METHODS):
                self.node(f.value, loop, func)
                for a in node.args:
                    self.node(a, loop, func)
                for k in node.keywords:
                    if k.arg is None:
                        raise _err("DisallowedNode", "** unpacking is not allowed", node)
                    self.node(k.value, loop, func)
                return
            if f.attr not in METHOD_NAMES:
                if _np_ok():
                    raise _err("CompatibilityGap", f"method or function .{f.attr}() is outside the supported subset",
                               f)
                raise _err("DisallowedNode", _attr_msg(f), f)
            self.methods.add(f.attr)
            self.node(f.value, loop, func)
        else:
            self.node(f, loop, func)
        for a in node.args:
            self.node(a, loop, func)
        for k in node.keywords:
            if k.arg is None:
                raise _err("DisallowedNode", "** unpacking is not allowed", node)
            _name_ok(k.arg, node)
            self.node(k.value, loop, func)

    def n_Dict(self, node, loop, func):
        if any(k is None for k in node.keys):
            raise _err("DisallowedNode", "** unpacking is not allowed", node)
        for child in ast.iter_child_nodes(node):
            self.node(child, loop, func)

    def n_Attribute(self, node, loop, func):
        if _np_ok():
            if _np_attr(node) or node.attr in NPX.ATTRS or node.attr in METHOD_NAMES or node.attr in EXTRA_METHODS:
                self.node(node.value, loop, func)
                return
            raise _err("CompatibilityGap", f"attribute .{node.attr} is outside the supported numpy subset", node)
        raise _err("DisallowedNode", _attr_msg(node), node)

    def n_Name(self, node, loop, func):
        _name_ok(node.id, node)

    def n_Constant(self, node, loop, func):
        v = node.value
        t = type(v)
        if t is str:
            if len(v) > MAX_STR:
                raise _err("DisallowedNode", f"string literal longer than {MAX_STR} characters", node)
        elif t is int:
            if abs(v) > MAX_INT_LITERAL:
                raise _err("DisallowedNode", f"integer literal larger than {MAX_INT_LITERAL}", node)
        elif t not in (bool, float, type(None)):
            raise _err("DisallowedNode", f"{t.__name__} literals are not allowed", node)

    def n_comprehension(self, node, loop, func):
        if node.is_async:
            raise _err("DisallowedNode", "async comprehensions are not allowed", node)
        self._target(node.target)
        self.node(node.iter, loop, func)
        for c in node.ifs:
            self.node(c, loop, func)

    def n_BinOp(self, node, loop, func):
        if type(node.op).__name__ not in ALLOWED:
            raise _err("DisallowedNode", HINTS.get(type(node.op).__name__, "operator not allowed"), node)
        self.node(node.left, loop, func)
        self.node(node.right, loop, func)


def _np_attr(node):
    """np.<name> or numpy.<name> with <name> in the audited subset (gridfn-2)."""
    return isinstance(node.value, ast.Name) and node.value.id in NP_NAMES and node.attr in NPX.NAMES


def _lower_imports(tree):
    """gridfn-2 lowering: `import numpy [as X]` and `from numpy import a [as b]` become bindings of X to np and of
    b to np.a; typing and __future__ imports are dropped; any other import is a COMPATIBILITY_GAP."""
    def lower(stmts):
        out = []
        for s in stmts:
            if isinstance(s, ast.Import):
                for a in s.names:
                    top = a.name.split(".")[0]
                    if a.name == "numpy":
                        if a.asname and a.asname not in NP_NAMES:
                            out.append(ast.copy_location(ast.Assign([ast.Name(a.asname, ast.Store())],
                                                                    ast.Name("np", ast.Load())), s))
                    elif top in ("typing", "__future__", "collections"):
                        continue
                    else:
                        raise _err("CompatibilityGap", f"import of {a.name} is not supported", s)
                continue
            if isinstance(s, ast.ImportFrom):
                mod = s.module or ""
                if mod in ("typing", "__future__"):
                    continue
                if mod == "collections":
                    for a in s.names:
                        if a.name not in COLLECTION_NAMES:
                            raise _err("CompatibilityGap", f"collections.{a.name} is not supported", s)
                        if a.asname and a.asname != a.name:
                            out.append(ast.copy_location(ast.Assign([ast.Name(a.asname, ast.Store())],
                                                                    ast.Name(a.name, ast.Load())), s))
                    continue
                if mod != "numpy":
                    raise _err("CompatibilityGap", f"import from {mod or '.'} is not supported", s)
                for a in s.names:
                    if a.name == "*" or a.name not in NPX.NAMES:
                        raise _err("CompatibilityGap", f"numpy.{a.name} is outside the supported subset", s)
                    out.append(ast.copy_location(ast.Assign([ast.Name(a.asname or a.name, ast.Store())],
                                                            ast.Attribute(ast.Name("np", ast.Load()), a.name,
                                                                          ast.Load())), s))
                continue
            for field in ("body", "orelse"):
                v = getattr(s, field, None)
                if isinstance(v, list) and v and isinstance(v[0], ast.stmt):
                    setattr(s, field, lower(v) or [ast.Pass()])
            out.append(s)
        return out
    tree.body = lower(tree.body)

    class _Coll(ast.NodeTransformer):                      # collections.Counter(...) -> Counter(...)
        def visit_Attribute(self, node):
            self.generic_visit(node)
            if isinstance(node.value, ast.Name) and node.value.id == "collections" and node.attr in COLLECTION_NAMES:
                return ast.copy_location(ast.Name(node.attr, node.ctx), node)
            return node
    tree = _Coll().visit(tree)
    return ast.fix_missing_locations(tree)


def _attr_msg(node):
    hint = _ATTR_HINTS.get(node.attr)
    base = isinstance(node.value, ast.Name) and node.value.id in ("np", "numpy")
    if base:
        return "numpy is not available: grids are lists of lists; use the card's functions"
    if node.attr.startswith("__"):
        return "names with double underscores are not allowed"
    msg = f"attribute access (.{node.attr}) is not allowed; only these methods: " + ", ".join(sorted(METHOD_NAMES))
    return msg + (f"; {hint}" if hint else "")


# ------------------------------------------------------------------ names
def _bound_names(stmts):
    """Names bound in a function body (assignment, loop and def targets), not entering nested defs or
    comprehensions."""
    out = set()

    def targets(t):
        if isinstance(t, ast.Name):
            out.add(t.id)
        elif isinstance(t, (ast.Tuple, ast.List)):
            for e in t.elts:
                targets(e)

    def walk(s):
        if isinstance(s, ast.FunctionDef):
            out.add(s.name)
            return
        if isinstance(s, ast.Assign):
            for t in s.targets:
                targets(t)
        elif isinstance(s, (ast.AugAssign, ast.AnnAssign)):
            targets(s.target)
        elif isinstance(s, ast.For):
            targets(s.target)
        for field in ("body", "orelse"):
            for c in getattr(s, field, ()) or ():
                walk(c)
    for s in stmts:
        walk(s)
    return out


def _names_only(t):
    if isinstance(t, ast.Name):
        return True
    return isinstance(t, (ast.Tuple, ast.List)) and all(_names_only(e) for e in t.elts)


def _target_names(t):
    out = set()
    for n in ast.walk(t):
        if isinstance(n, ast.Name):
            out.add(n.id)
    return out


class _Names:
    """Lexical name resolution; records the primitives and builtins a program uses."""

    def __init__(self, module_names):
        self.module = module_names
        self.prims, self.builtins = set(), set()

    def visible(self, scopes):
        names = set(self.module) | set(BUILTIN_NAMES) | set(PRIMITIVE_NAMES) | set(CONSTANT_NAMES)
        for s in scopes:
            names |= s
        return names

    def load(self, name, node, scopes):
        for s in reversed(scopes):
            if name in s:
                return
        if (name in NP_NAMES or name in COLLECTION_NAMES) and _np_ok():
            return
        if name in self.module:
            return
        if name in BUILTIN_NAMES:
            self.builtins.add(name)
            return
        if name in P.REGISTRY:
            self.prims.add(name)
            return
        if name in P.CONSTANTS:
            return
        close = difflib.get_close_matches(name, sorted(self.visible(scopes)), n=1, cutoff=0.6)
        hint = f" (did you mean {close[0]}?)" if close else ""
        if name in ("open", "exec", "eval", "compile", "getattr", "setattr", "globals", "locals", "vars", "dir",
                    "type", "object", "input", "breakpoint", "help", "id", "hash", "memoryview", "iter", "next"):
            hint = " (not available in this language)"
        raise _err("UnknownName", f"name '{name}' is not defined{hint}", node)

    def expr(self, node, scopes):
        if node is None:
            return
        if isinstance(node, ast.Name):
            if isinstance(node.ctx, ast.Load):
                self.load(node.id, node, scopes)
            return
        if isinstance(node, ast.Lambda):
            for d in node.args.defaults:
                self.expr(d, scopes)
            self.expr(node.body, list(scopes) + [{a.arg for a in node.args.args}])
            return
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
            inner = list(scopes)
            for i, g in enumerate(node.generators):
                self.expr(g.iter, inner if i else scopes)
                inner = inner + [_target_names(g.target)]
                for c in g.ifs:
                    self.expr(c, inner)
            if isinstance(node, ast.DictComp):
                self.expr(node.key, inner)
                self.expr(node.value, inner)
            else:
                self.expr(node.elt, inner)
            return
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.expr):
                self.expr(child, scopes)
            elif isinstance(child, ast.keyword):
                self.expr(child.value, scopes)
            elif isinstance(child, (ast.comprehension,)):
                pass

    def stmts(self, stmts, scopes):
        for s in stmts:
            self.stmt(s, scopes)

    def stmt(self, s, scopes):
        if isinstance(s, ast.FunctionDef):
            for d in s.args.defaults:
                self.expr(d, scopes)
            local = {a.arg for a in s.args.args} | _bound_names(s.body)
            self.stmts(s.body, scopes + [local])
            return
        for field, value in ast.iter_fields(s):
            if field in ("body", "orelse"):
                self.stmts(value, scopes)
            elif field in ("annotation", "returns", "type_comment"):
                continue
            elif isinstance(value, ast.expr):
                self.expr(value, scopes)
            elif isinstance(value, list):
                for v in value:
                    if isinstance(v, ast.expr):
                        self.expr(v, scopes)


# ------------------------------------------------------------------ normalization
def _drop_prints(tree):
    """`print(...)` statements do nothing here, so they are removed before the check (their arguments, for example
    f-strings, are never evaluated), unless the program binds the name print itself."""
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and (n.name == "print" or any(a.arg == "print" for a in n.args.args)) or \
                isinstance(n, ast.Name) and n.id == "print" and not isinstance(n.ctx, ast.Load):
            return

    def is_print(s):
        return isinstance(s, ast.Expr) and isinstance(s.value, ast.Call) and isinstance(s.value.func, ast.Name) and \
            s.value.func.id == "print"
    for n in ast.walk(tree):
        for field in ("body", "orelse"):
            v = getattr(n, field, None)
            if isinstance(v, list) and any(is_print(s) for s in v):
                kept = [s for s in v if not is_print(s)]
                setattr(n, field, kept or ([ast.Pass()] if field == "body" or v else []))


def _normalize(stmts):
    """Docstrings and bare constant statements removed, annotations dropped (AnnAssign becomes Assign; a bare
    annotation disappears); an emptied body becomes `pass`. Changes the statements in place."""
    out = []
    for s in stmts:
        if isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant):
            continue
        if isinstance(s, ast.AnnAssign):
            if s.value is None:
                continue
            s = ast.copy_location(ast.Assign(targets=[s.target], value=s.value), s)
        if isinstance(s, ast.FunctionDef):
            s.returns = None
            s.type_comment = None
            for a in s.args.args:
                a.annotation = None
                a.type_comment = None
        if hasattr(s, "type_comment"):
            s.type_comment = None
        for field in ("body", "orelse"):
            v = getattr(s, field, None)
            if isinstance(v, list) and (v or field == "body"):
                setattr(s, field, _normalize(v))
        out.append(s)
    return out or [ast.Pass()]


# ------------------------------------------------------------------ entry point
def check(src, dialect="gridfn-1"):
    """Checked program, or GridFnError (kind SyntaxError, DisallowedNode, UnknownName or, in gridfn-2,
    CompatibilityGap)."""
    _DIALECT[0] = dialect
    try:
        return _check(src, dialect)
    finally:
        _DIALECT[0] = "gridfn-1"


def _check(src, dialect):
    if not isinstance(src, str) or not src.strip():
        raise GridFnError("SyntaxError", "no program: write def transform(grid): ... inside ```python ... ```")
    if len(src) > MAX_SRC_CHARS:
        raise GridFnError("SyntaxError", f"program longer than {MAX_SRC_CHARS} characters")
    if "\x00" in src:
        raise GridFnError("SyntaxError", "the program contains a null character")
    try:
        tree = ast.parse(src, mode="exec")
    except SyntaxError as e:
        raise GridFnError("SyntaxError", (e.msg or "invalid syntax")[:200], e.lineno) from None
    except (ValueError, RecursionError, MemoryError, OverflowError) as e:
        raise GridFnError("SyntaxError", f"cannot parse: {type(e).__name__}") from None
    n, depth = _size_and_depth(tree)
    if dialect == "gridfn-2" and n <= MAX_NODES and depth <= MAX_DEPTH:
        tree = _lower_imports(tree)
    if n <= MAX_NODES and depth <= MAX_DEPTH:
        _drop_prints(tree)
    if n > MAX_NODES:
        raise GridFnError("DisallowedNode", f"program too large ({n} syntax nodes; at most {MAX_NODES})")
    if depth > MAX_DEPTH:
        raise GridFnError("DisallowedNode", f"program nested too deeply (depth {depth}; at most {MAX_DEPTH})")
    ck = _Checker()
    for s in tree.body:
        if isinstance(s, ast.FunctionDef):
            ck.node(s)
        elif isinstance(s, (ast.Assign, ast.AnnAssign)):
            for t in (s.targets if isinstance(s, ast.Assign) else [s.target]):
                if not _names_only(t):
                    raise _err("DisallowedNode", "the top level may only assign names (constants)", s)
            ck.node(s)
        elif isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant) and isinstance(s.value.value, str):
            continue
        else:
            name = type(s).__name__
            if name not in ALLOWED:
                raise _err("DisallowedNode", HINTS.get(name, f"{name} is not part of the language"), s)
            raise _err("DisallowedNode", "the top level may only hold def statements and NAME = value constants; "
                       "put the code inside def transform(grid):", s)
    defs = [s for s in tree.body if isinstance(s, ast.FunctionDef)]
    tf = [s for s in defs if s.name == "transform"]
    if not tf:
        raise GridFnError("SyntaxError", "the program must define a top-level function transform(grid)")
    a = tf[-1].args
    if not a.args or len(a.args) - len(a.defaults) > 1:
        raise _err("SyntaxError", "transform must take exactly one argument, the input grid: def transform(grid):",
                   tf[-1])
    module_names = {s.name for s in defs}
    for s in tree.body:
        if isinstance(s, ast.Assign):
            for t in s.targets:
                module_names |= _target_names(t)
        elif isinstance(s, ast.AnnAssign):
            module_names |= _target_names(s.target)
    names = _Names(module_names)
    names.stmts(tree.body, [])
    tree.body = _normalize(tree.body)
    norm = ast.fix_missing_locations(tree)
    try:
        canonical = ast.unparse(norm)
    except (RecursionError, ValueError) as e:            # pragma: no cover (bounded depth)
        raise GridFnError("SyntaxError", f"cannot print the program: {type(e).__name__}") from None
    return Checked(norm, canonical, count_nodes(norm), tuple(s.name for s in defs), tuple(sorted(names.prims)),
                   tuple(sorted(names.builtins)), tuple(sorted(ck.methods)), sha256(src))


def closest(name, pool):
    m = difflib.get_close_matches(name, sorted(pool), n=1, cutoff=0.6)
    return m[0] if m else None
