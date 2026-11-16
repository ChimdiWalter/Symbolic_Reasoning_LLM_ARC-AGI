"""arc-dsl loader (dsl.py, arc_types.py, constants.py only), signatures and runtime type tags.
Author: Chimdi Walter Ndubuisi

arc-dsl: michaelhodel/arc-dsl, commit 635de49, MIT License, Copyright (c) 2023 Michael Hodel. Its three files are
executed by path into private namespaces; nothing else in that download is read.
"""
import ast
import json
import os

ROOT = "/path/to/repository"
DSL_DIR = ROOT + "/outputs/search_components/resources_20261026/github/arc-dsl"
SELF = ROOT + "/experiments/proposer_20261109/selflesion"

_C = {}


def _exec(name, ns):
    path = os.path.join(DSL_DIR, name)
    src = open(path, encoding="utf-8").read()
    mod = ast.parse(src)
    mod.body = [s for s in mod.body
                if not (isinstance(s, ast.ImportFrom) and s.module in ("arc_types", "dsl", "constants"))]
    exec(compile(mod, path, "exec"), ns)        # noqa: S102 (pure-function MIT module)
    return src


def load():
    """dict: ns (function namespace), consts, sigs {name: [(param, annotation)]}, rets, lib_order, lib_deps, fam."""
    if _C:
        return _C
    tns = {}
    _exec("arc_types.py", tns)
    ns = dict(tns)
    src = _exec("dsl.py", ns)
    cns = {}
    _exec("constants.py", cns)
    sigs, rets = {}, {}
    for f in ast.parse(src).body:
        if isinstance(f, ast.FunctionDef):
            sigs[f.name] = [(a.arg, ast.unparse(a.annotation) if a.annotation is not None else "?")
                            for a in f.args.args]
            rets[f.name] = ast.unparse(f.returns) if f.returns is not None else "?"
    lib = json.load(open(SELF + "/library/LIBRARY.json"))
    gram = json.load(open(SELF + "/grammar/SYSTEM_GRAMMAR.json"))
    fams = json.load(open(SELF + "/families/FAMILIES.json"))["families"]
    order = list(lib["order"])
    sources = {k: lib["entries"][k]["source"] for k in order}
    const_names = list(gram["const_names"])
    _C.update(ns=ns, sources=sources, consts={k: cns[k] for k in const_names}, const_names=const_names, sigs=sigs, rets=rets,
              lib_order=order, lib_deps={k: list(lib["entries"][k]["deps"]) for k in order},
              fn_leaf_names=[x[3:] for x in gram["fn_leaves"]],
              fam_of={m: f["members"] for f in fams for m in f["members"]},
              fam_label={m: f["label"] for f in fams for m in f["members"]})
    assert set(_C["fam_of"]) == set(order) and set(order) <= set(sigs)
    return _C


def reverse_closure(names):
    """`names` plus every library operation that depends on one of them, transitively, by the "deps" of the library
    text (the source this study executes)."""
    L = load()
    out = set(names)
    changed = True
    while changed:
        changed = False
        for o in L["lib_order"]:
            if o not in out and out & set(L["lib_deps"][o]):
                out.add(o)
                changed = True
    return out


_FULL = {}


def full_ns():
    """The library text with nothing hidden (cached). Everything that is executed comes from library text."""
    if "ns" not in _FULL:
        _FULL["ns"] = library_namespace(())
    return _FULL["ns"]


def canon(v):
    """Canonical typed text of a value: bool distinct from int, tuple from frozenset, sets in sorted order,
    functions by name. Never contains a memory address."""
    t = type(v)
    if t is bool:
        return "b%d" % v
    if t is int:
        return "i%d" % v
    if t is tuple:
        return "t(" + ",".join(canon(x) for x in v) + ")"
    if t is frozenset:
        return "s{" + ",".join(sorted(canon(x) for x in v)) + "}"
    if callable(v):
        return "f:" + getattr(v, "__name__", "?")
    return "?" + t.__name__


SPLIT_SEED = "self-lesion-20261110"
HOLD_OUT_PERCENT = 20


def held_out_names():
    """Names in families that the earlier study's rule (FAMILY_RULE.md section 4) holds out."""
    import hashlib
    out = {}
    for members in {tuple(sorted(m)) for m in load()["fam_of"].values()}:
        fid = "fam-" + hashlib.sha256("+".join(members).encode()).hexdigest()[:12]
        if int(hashlib.sha256(f"{SPLIT_SEED}:{fid}".encode()).hexdigest()[:8], 16) % 100 < HOLD_OUT_PERCENT:
            for m in members:
                out[m] = fid
    return out


def library_namespace(hidden=()):
    """Executable namespace for one hiding condition, built from the library's own source text (LIBRARY.json,
    entries[name]["source"], in the library's dependency order), leaving out every hidden name. A name that is
    left out does not exist: any remaining operation whose body reaches it raises NameError when it runs.
    (lbind and rbind use the library's own hand-written equivalents.)"""
    L = load()
    hidden = set(hidden)
    ns = {"__builtins__": __builtins__}
    for name in L["lib_order"]:
        if name not in hidden:
            exec(compile(L["sources"][name], "<library:%s>" % name, "exec"), ns)    # noqa: S102 (trusted library)
    return ns


# ---------------------------------------------------------------- runtime type tags
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
        if t0 is int and len(v) == 2 and type(v[1]) is int:
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
                return "OS" if type(y[1]) is tuple else "XS"
            return "FU"
        if tx is int:
            return "Z"
        return "FU"
    if callable(v):
        return "F"
    return "U"


def tagset(vals):
    """frozenset of runtime tags over a value vector (E dropped when another tag is present); None if unusable."""
    return norm({tag(v) for v in vals})


def norm(ts):
    if "U" in ts:
        return None
    if len(ts) > 1:
        ts.discard("E")
        if "F" in ts:
            return None
    return frozenset(ts)


ALL = frozenset("B I T G TU TT GT O X OS XS Z FU E".split())
CONT = frozenset("G T TU TT GT O X OS XS Z FU E".split())
ACC = {
    "Any": ALL, "?": frozenset("F"), "Callable": frozenset("F"), "Integer": frozenset("I"),
    "Boolean": frozenset("B"), "IntegerTuple": frozenset("T"), "Numerical": frozenset("IT"),
    "IntegerSet": frozenset(["Z", "E"]), "Grid": frozenset("G"), "Object": frozenset(["O", "E"]),
    "Objects": frozenset(["OS", "E"]), "Indices": frozenset(["X", "E"]), "Patch": frozenset(["O", "X", "E"]),
    "Element": frozenset(["O", "G"]), "Piece": frozenset(["G", "O", "X", "E"]),
    "FrozenSet": frozenset("O X OS XS Z FU E".split()), "Tuple": frozenset("G T TU TT GT E".split()),
    "Container": CONT,
    # a parameter annotated ContainerContainer accepts every container tag whose elements can themselves be
    # containers (grids, sets of cells, objects and sets of such); integers-only tags (T, Z) stay out
    "ContainerContainer": frozenset("G TT GT O X OS XS TU FU E".split()),
}


def vsize(v):
    """Top-level length of a container value (1 otherwise); used to bound intermediate values."""
    return len(v) if isinstance(v, (tuple, frozenset)) else 1


def valid_value(v, cap=3000):
    return tag(v) != "U" and vsize(v) <= cap
