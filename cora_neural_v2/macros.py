"""Lisp-style typed macros over ncv2-g1 ASTs: the hook for later library learning (DreamCoder/LILO-style).

A macro is a named, typed template. `(call NAME (list ARG ...))` expands to the macro body with each
`(param P)` replaced by the matching argument. Expansion is purely syntactic and happens before typechecking, so
the expanded tree is checked and compiled like any hand-written program, and it compiles to existing native ops.

- Typed: each parameter declares a type. Each argument is checked against it at expansion time. At definition time
  the body, with every parameter replaced by a typed hole, must typecheck to the declared result type.
- Hygienic: variables bound inside a macro body (`rule_with`) are renamed at each expansion, so they cannot
  capture or clash with the caller's variables.
- Provenance: every macro is tagged "researcher" (hand-written syntax) or "learned" (mined and compressed from
  programs). A learned macro is a reusable abstraction over existing operations, never a new primitive.
"""
import itertools
from dataclasses import dataclass

from cora_neural_v2.rast import ASTError, N, typecheck

_GENSYM = itertools.count()


@dataclass(frozen=True)
class Macro:
    name: str
    params: tuple            # ((name, TYPE), ...)
    result: str              # TYPE of the expansion
    body: object             # an AST using (param NAME) placeholders
    provenance: str = "researcher"

    def __post_init__(self):
        if self.provenance not in ("researcher", "learned"):
            raise ASTError("provenance is 'researcher' or 'learned'")
        holed = _subst(self.body, {p: N("hole", (t,)) for p, t in self.params})
        if typecheck(holed) != self.result:
            raise ASTError(f"macro {self.name}: body does not typecheck to {self.result}")


def _subst(x, mapping, rename=None):
    rename = rename or {}
    if isinstance(x, N):
        if x.op == "param":
            if x.args[0] not in mapping:
                raise ASTError(f"unknown macro parameter {x.args[0]!r}")
            return mapping[x.args[0]]
        if x.op == "var" and x.args[0] in rename:
            return N("var", (rename[x.args[0]],))
        return N(x.op, tuple(_subst(a, mapping, rename) for a in x.args))
    if isinstance(x, tuple):
        return tuple(_subst(a, mapping, rename) for a in x)
    if isinstance(x, str) and x in rename:
        return rename[x]
    return x


def _bound_vars(x, out):
    if isinstance(x, N):
        if x.op == "rule_with":
            for name, _ in x.args[0]:
                out.add(name)
        for a in x.args:
            _bound_vars(a, out)
    elif isinstance(x, tuple):
        for a in x:
            _bound_vars(a, out)
    return out


def expand(x, registry, depth=0):
    """Expand every (call NAME (list ARGS)) using `registry` {name: Macro}; recursive, at most 8 levels deep."""
    if depth > 8:
        raise ASTError("macro expansion deeper than 8 levels")
    if isinstance(x, N):
        if x.op == "call":
            name, args = x.args
            if name not in registry:
                raise ASTError(f"unknown macro {name!r}")
            m = registry[name]
            if len(args) != len(m.params):
                raise ASTError(f"macro {name} takes {len(m.params)} arguments")
            args = tuple(expand(a, registry, depth + 1) for a in args)
            for (pname, ptype), a in zip(m.params, args):
                if isinstance(a, N) and typecheck(a, {v: "REF" for v in _free_vars(a)}) != ptype:
                    raise ASTError(f"macro {name}: argument {pname} must be {ptype}")
            rename = {v: f"{v}__{name}{next(_GENSYM)}" for v in _bound_vars(m.body, set())}   # hygiene
            return expand(_subst(m.body, dict(zip((p for p, _ in m.params), args)), rename), registry, depth + 1)
        return N(x.op, tuple(expand(a, registry, depth) for a in x.args))
    if isinstance(x, tuple):
        return tuple(expand(a, registry, depth) for a in x)
    return x


def _free_vars(x, out=None):
    out = set() if out is None else out
    if isinstance(x, N):
        if x.op == "var":
            out.add(x.args[0])
        for a in x.args:
            _free_vars(a, out)
    elif isinstance(x, tuple):
        for a in x:
            _free_vars(a, out)
    return out
