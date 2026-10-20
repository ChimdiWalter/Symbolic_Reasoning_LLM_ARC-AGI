"""ncv2-g2: ncv2-g1 (unchanged and imported) plus native CORA's reduction and generative program classes.

One entry point for every program form:
- `parse`: an S-expression into a typed AST;
- `typecheck`;
- `compile_program`: to exactly the native dict;
- `execute` and `fit`: through the unchanged native `render_program` only;
- `decompile`: a native dict back into the typed AST.

ncv2-g1 forms are delegated to `cora_neural_v2` unchanged. The program-class forms live in `classes.py`.
"""
import numpy as np

from cora_neural_v2 import bridge as G1B
from cora_neural_v2 import rast as G1
from cora_neural_v2.rast import ASTError, N, to_sexpr                    # noqa: F401  (re-exported)
from cora_neural_v2g2 import classes as C
from cora_neural_v2g2 import decompile as D

GRAMMAR_VERSION = "ncv2-g2"


def is_class(node):
    return isinstance(node, N) and node.op in C.CLASS_PROGRAM_OPS


def parse(s):
    """S-expression -> AST. Heads that are ncv2-g1 ops, meta ops or ncv2-g2 class ops become nodes."""
    toks = G1._tokens(s)
    pos = 0
    heads = set(G1.SIGNATURES) | set(G1.META_OPS) | set(C.CLASS_OPS)

    def read():
        nonlocal pos
        t = toks[pos]
        pos += 1
        if t != "(":
            if t == ")":
                raise ASTError("unexpected ')'")
            return G1._atom(t)
        items = []
        while toks[pos] != ")":
            items.append(read())
        pos += 1
        if not items:
            raise ASTError("empty list")
        head = items[0]
        if head == "list":
            return tuple(items[1:])
        if isinstance(head, str) and head in heads:
            return N(head, tuple(items[1:]))
        return tuple(items)
    x = read()
    if pos != len(toks):
        raise ASTError("trailing tokens after the expression")
    return x


def typecheck(node):
    return C.typecheck(node) if is_class(node) else G1.typecheck(node)


def compile_program(node):
    return C.compile_class(node) if is_class(node) else G1B.compile_program(node)


def decompile(d):
    if d.get("program_class") in ("reduction", "generative"):
        return C.decompile_class(d)
    return D.program(d)


def run(d, grid):
    return G1B.run_native_dict(d, grid)


def execute(node, grid):
    return run(compile_program(node), grid)


def fit(node, pairs):
    """(fits every demonstration, per-pair wrong-cell counts; None = no output or a shape mismatch)."""
    d = compile_program(node)
    wrong = []
    for a, b in pairs:
        out = run(d, a)
        B = np.asarray(b)
        wrong.append(None if out is None or out.shape != B.shape else int((out != B).sum()))
        if wrong[-1] != 0:
            break
    return len(wrong) == len(pairs) and all(w == 0 for w in wrong), wrong
