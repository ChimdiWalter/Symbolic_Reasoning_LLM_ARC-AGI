"""ncv2-g1: CORA's typed relational program AST (Neural-CORA v2). Researcher-designed syntax over EXISTING native ops.

A program is a tree of nodes `N(op, args)`. Every op has a fixed signature (`SIGNATURES`) and compiles one-to-one
onto an existing native CORA construct (`compile.py`); nothing here executes a grid. There is no eval and no
generated code: a program is data, checked by `typecheck`, compiled, then run by the unchanged native interpreter.

Two equivalent concrete forms:
- S-expressions (Lisp-like, for reading, macros and sketches), e.g.
      (program S1 (list (rule (test color == 1) (recolor (color 2)))) keep (same_as_input))
  Literal lists are tagged `(list ...)`; booleans are #t / #f; other bare words are symbols.
- JSON: {"op": ..., "args": [...]}; lists are JSON arrays.

Slots (the directive's AST slots, each mapped to native):
- SCENE / VIEW: the `program` view symbol (S1..S7: connectivity, multicolour, colour layers, proximity).
- OBJECT / RELATION / GUARD: PRED nodes over the native feature registry, with `and`, `in_set` and
  `exists(relation, PRED)` (relations: adjacent, inside, contains, left_of, same_shape, ...).
- BINDING: `rule_with((list (?t REF) ...), PRED, ACTION)` binds reference variables (`?t`) usable as `(var ?t)`
  anywhere a REF is expected in that rule. The selected object is `(self)`. References resolve relative to the
  object being transformed, exactly as native RefExprs do, so binding compiles by substitution.
- GEOMETRY: translate, move_to, move_until_adjacent, reflect, rotate, scale, copy (targets, offsets, period, rays),
  copy_part, extract_part, connect, fill_line, crop_to; relational vectors (vector_to, gap_closing, align, slide,
  mirror, reflect_across, step_toward, to_border, scaled).
- COLOUR / VALUE: constant, colour of a referenced object, most/least common, induced colour maps, feature-to-colour
  maps and affine maps; paint copies per-cell colours (multicolour) from a referenced object.
- CONTROL / COMPOSITION: first-match rules + default (keep/delete), `composite` (several deltas on one object, in
  order), `seq` (stages that re-segment the previous output), and three render modes (same_as_input, crop,
  constant_shape) including size changes.
- HOLES: `(hole TYPE)` stands for an unknown subtree of TYPE in a sketch; it typechecks but never compiles.

Not exposed in g1 (reasons in inventory.py): native GROW modes, SYNTH_COPY (a learned-verb asset), library
operators, copy's per-index `k` mode, the generative / reduction / framed / overlay program classes.
"""
from dataclasses import dataclass

GRAMMAR_VERSION = "ncv2-g1"
TYPES = ("VIEW", "PRED", "REF", "COLOR", "VEC", "SCALAR", "REGION", "AXIS", "ANGLE", "DIR", "ALIGN", "ACTION",
         "RULE", "RENDER", "PROGRAM")
VIEWS = ("S1", "S2", "S3", "S4", "S5", "S6", "S7")
CMPS = ("==", "!=", "<", ">", "<=", ">=")
AXES = ("horizontal", "vertical", "diag_main", "diag_anti")
LINE_AXES = ("horizontal", "vertical", "both")
EXTENTS = ("to_border", "to_object")
DIRECTIONS = ("up", "down", "left", "right")
ALIGNMENTS = ("bbox_center", "bbox_origin")
ANGLES = (90, 180, 270)
DEFAULTS = ("keep", "delete")


@dataclass(frozen=True)
class N:
    op: str
    args: tuple = ()


# argument kinds: a TYPE name (a child node of that type), or a literal kind:
#   int, sym:<SET>, feature, relation, cmp, value, var, pairs, fpairs, values,
#   list:<TYPE> (a literal list of nodes of TYPE), list+:<TYPE> (non-empty), bindings
SIGNATURES = {
    # ---- predicates (selectors, guards)
    "true": ("PRED", ()),
    "test": ("PRED", ("feature", "cmp", "value")),
    "and": ("PRED", ("PRED", "PRED")),
    "in_set": ("PRED", ("feature", "values")),
    "exists": ("PRED", ("relation", "PRED")),
    # ---- object references (relative to the object being transformed)
    "self": ("REF", ()),
    "var": ("REF", ("var",)),
    "nearest": ("REF", ("PRED",)),
    "nearest_of_color": ("REF", ("int",)),
    "container": ("REF", ()),
    "contained": ("REF", ()),
    "largest": ("REF", ("PRED",)),
    "unique": ("REF", ("PRED",)),
    "shape_twin": ("REF", ()),
    # ---- colours
    "color": ("COLOR", ("int",)),
    "color_of": ("COLOR", ("REF",)),
    "most_common_color": ("COLOR", ()),
    "least_common_color": ("COLOR", ()),
    "color_map": ("COLOR", ("pairs",)),
    "feature_map": ("COLOR", ("feature", "fpairs")),
    "feature_affine": ("COLOR", ("feature", "int")),
    # ---- vectors
    "vec": ("VEC", ("int", "int")),
    "vector_to": ("VEC", ("REF",)),
    "to_border": ("VEC", ("sym:DIRECTIONS",)),
    "gap_closing": ("VEC", ("REF", "sym:AXES")),
    "scaled": ("VEC", ("sym:DIRECTIONS", "SCALAR")),
    "step_toward": ("VEC", ("REF",)),
    "slide": ("VEC", ("sym:DIRECTIONS",)),
    "align_to": ("VEC", ("REF", "sym:LINE2")),
    "mirror": ("VEC", ("sym:LINE2",)),
    "reflect_across": ("VEC", ("REF", "sym:LINE2")),
    # ---- scalars
    "int": ("SCALAR", ("int",)),
    "size": ("SCALAR", ()),
    "feature": ("SCALAR", ("feature",)),
    "count": ("SCALAR", ("PRED",)),
    "hole_count": ("SCALAR", ()),
    # ---- regions
    "bbox_self": ("REGION", ()),
    "bbox": ("REGION", ("REF",)),
    "quadrant": ("REGION", ("int",)),
    "separator_cell": ("REGION", ("int", "int")),
    "separator_block_self": ("REGION", ()),
    # ---- symbol leaves
    "axis": ("AXIS", ("sym:AXES",)),
    "angle": ("ANGLE", ("int",)),
    "dir": ("DIR", ("sym:DIRECTIONS",)),
    "align_mode": ("ALIGN", ("sym:ALIGNMENTS",)),
    # ---- actions (geometry, colour, copying)
    "keep": ("ACTION", ()),
    "delete": ("ACTION", ()),
    "translate": ("ACTION", ("VEC",)),
    "recolor": ("ACTION", ("COLOR",)),
    "copy_targets": ("ACTION", ("PRED", "ALIGN")),
    "copy_offsets": ("ACTION", ("list+:VEC",)),
    "copy_period": ("ACTION", ("VEC", "list:VEC")),
    "copy_rays": ("ACTION", ("list+:VEC",)),
    "move_to": ("ACTION", ("VEC",)),
    "move_until_adjacent": ("ACTION", ("DIR",)),
    "move_until_adjacent_to": ("ACTION", ("DIR", "REF")),
    "scale": ("ACTION", ("SCALAR",)),
    "reflect": ("ACTION", ("AXIS",)),
    "reflect_shift": ("ACTION", ("AXIS", "VEC")),
    "rotate": ("ACTION", ("ANGLE",)),
    "rotate_shift": ("ACTION", ("ANGLE", "VEC")),
    "paint": ("ACTION", ("REF",)),
    "connect": ("ACTION", ("REF", "COLOR")),
    "fill_line": ("ACTION", ("sym:LINE_AXES", "COLOR", "sym:EXTENTS")),
    "crop_to": ("ACTION", ("REGION",)),
    "copy_part": ("ACTION", ("REGION", "VEC")),
    "extract_part": ("ACTION", ("REGION", "int", "int", "VEC")),
    "composite": ("ACTION", ("list+:ACTION",)),
    # ---- rules, rendering, programs
    "rule": ("RULE", ("PRED", "ACTION")),
    "rule_with": ("RULE", ("bindings", "PRED", "ACTION")),
    "same_as_input": ("RENDER", ()),
    "crop": ("RENDER", ("REGION",)),
    "crop_by_action": ("RENDER", ()),                          # crop mode; the region is set by a crop_to action
    "constant_shape": ("RENDER", ("int", "int", "COLOR")),
    "program": ("PROGRAM", ("sym:VIEWS", "list:RULE", "sym:DEFAULTS", "RENDER")),
    "seq": ("PROGRAM", ("list+:PROGRAM",)),
    # ---- a typed hole (sketches only; never compiles)
    "hole": (None, ("sym:TYPES",)),
}
#: purely syntactic forms, removed by macros.expand before typechecking (typecheck rejects them)
META_OPS = ("call", "param")
SYMBOL_SETS = {"DIRECTIONS": DIRECTIONS, "AXES": AXES, "LINE2": ("horizontal", "vertical"), "LINE_AXES": LINE_AXES,
               "EXTENTS": EXTENTS, "ALIGNMENTS": ALIGNMENTS, "VIEWS": VIEWS, "DEFAULTS": DEFAULTS, "TYPES": TYPES}


class ASTError(TypeError):
    pass


import functools


@functools.lru_cache(maxsize=1)
def _native_names():
    """Registered native feature and relation names (the only legal ones); read once."""
    from geocat_arc.object_reasoning import features as F
    if not F.FEATURE_REGISTRY:
        F.register_builtin_features()
    if not F.RELATION_REGISTRY:
        F.register_builtin_features()
    return set(F.FEATURE_REGISTRY), set(F.RELATION_REGISTRY)


def typecheck(node, env=None, path="root"):
    """Return the node's type; raise ASTError on any violation. `env` maps bound variable names to 'REF'."""
    env = env or {}
    if not isinstance(node, N):
        raise ASTError(f"{path}: expected a node, got {node!r}")
    if node.op not in SIGNATURES:
        raise ASTError(f"{path}: unknown op {node.op!r} (not in {GRAMMAR_VERSION})")
    rtype, kinds = SIGNATURES[node.op]
    if len(node.args) != len(kinds):
        raise ASTError(f"{path}: {node.op} takes {len(kinds)} arguments, got {len(node.args)}")
    feats, rels = _native_names()
    local = dict(env)
    for i, (kind, a) in enumerate(zip(kinds, node.args)):
        p = f"{path}.{node.op}[{i}]"
        if kind == "bindings":
            if not isinstance(a, tuple) or not a:
                raise ASTError(f"{p}: bindings must be a non-empty list of (?name REF)")
            for b in a:
                if not (isinstance(b, tuple) and len(b) == 2 and isinstance(b[0], str) and b[0].startswith("?")):
                    raise ASTError(f"{p}: a binding is (?name REF), got {b!r}")
                if b[0] in local:
                    raise ASTError(f"{p}: variable {b[0]} bound twice")
                if typecheck(b[1], local, p) != "REF":
                    raise ASTError(f"{p}: binding {b[0]} must be a REF")
                local[b[0]] = "REF"
            continue
        if kind in TYPES:
            t = typecheck(a, local, p)
            if t != kind:
                raise ASTError(f"{p}: expected {kind}, got {t}")
        elif kind.startswith("list"):
            want = kind.split(":", 1)[1]
            if not isinstance(a, tuple) or (kind.startswith("list+") and not a):
                raise ASTError(f"{p}: expected a {'non-empty ' if kind.startswith('list+') else ''}list of {want}")
            for j, x in enumerate(a):
                if typecheck(x, local, f"{p}[{j}]") != want:
                    raise ASTError(f"{p}[{j}]: expected {want}")
        elif kind == "int":
            if not isinstance(a, int) or isinstance(a, bool):
                raise ASTError(f"{p}: expected an int")
        elif kind.startswith("sym:"):
            if a not in SYMBOL_SETS[kind[4:]]:
                raise ASTError(f"{p}: {a!r} not in {SYMBOL_SETS[kind[4:]]}")
        elif kind == "feature":
            if a not in feats:
                raise ASTError(f"{p}: {a!r} is not a registered native feature")
        elif kind == "relation":
            if a not in rels:
                raise ASTError(f"{p}: {a!r} is not a registered native relation")
        elif kind == "cmp":
            if a not in CMPS:
                raise ASTError(f"{p}: comparison {a!r} not in {CMPS}")
        elif kind == "value":
            if not isinstance(a, (int, str, bool)):
                raise ASTError(f"{p}: a test value is an int, symbol or boolean")
        elif kind == "var":
            if a not in local:
                raise ASTError(f"{p}: unbound variable {a!r}")
        elif kind in ("pairs", "fpairs"):
            if not isinstance(a, tuple) or not all(isinstance(x, tuple) and len(x) == 2 for x in a):
                raise ASTError(f"{p}: expected a list of pairs")
        elif kind == "values":
            if not isinstance(a, tuple) or not a:
                raise ASTError(f"{p}: expected a non-empty list of values")
        else:
            raise ASTError(f"{p}: unknown argument kind {kind}")
    if node.op == "hole":
        return node.args[0]
    return rtype


def holes(node):
    """Every typed hole in a tree (a sketch is complete when this is empty)."""
    out = []

    def walk(x):
        if isinstance(x, N):
            if x.op == "hole":
                out.append(x.args[0])
            for a in x.args:
                walk(a)
        elif isinstance(x, tuple):
            for a in x:
                walk(a)
    walk(node)
    return out


# ------------------------------------------------------------------ S-expressions
def to_sexpr(x):
    if isinstance(x, N):
        return "(" + " ".join([x.op] + [to_sexpr(a) for a in x.args]) + ")"
    if isinstance(x, tuple):
        return "(list" + "".join(" " + to_sexpr(a) for a in x) + ")"
    if isinstance(x, bool):
        return "#t" if x else "#f"
    return str(x)


def _tokens(s):
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c.isspace():
            i += 1
        elif c in "()":
            out.append(c)
            i += 1
        else:
            j = i
            while j < len(s) and not s[j].isspace() and s[j] not in "()":
                j += 1
            out.append(s[i:j])
            i = j
    return out


def _atom(t):
    if t == "#t":
        return True
    if t == "#f":
        return False
    try:
        return int(t)
    except ValueError:
        return t


def parse_sexpr(s):
    toks = _tokens(s)
    pos = 0

    def read():
        nonlocal pos
        t = toks[pos]
        pos += 1
        if t != "(":
            if t == ")":
                raise ASTError("unexpected ')'")
            return _atom(t)
        items = []
        while toks[pos] != ")":
            items.append(read())
        pos += 1
        if not items:
            raise ASTError("empty list")
        head = items[0]
        if head == "list":
            return tuple(items[1:])
        if isinstance(head, str) and (head in SIGNATURES or head in META_OPS):
            return N(head, tuple(items[1:]))
        return tuple(items)                                         # an untagged pair such as (1 2) or (?t REF)
    x = read()
    if pos != len(toks):
        raise ASTError("trailing tokens after the expression")
    return x


# ------------------------------------------------------------------ JSON
def to_json(x):
    if isinstance(x, N):
        return {"op": x.op, "args": [to_json(a) for a in x.args]}
    if isinstance(x, tuple):
        return [to_json(a) for a in x]
    return x


def from_json(d):
    if isinstance(d, dict):
        return N(d["op"], tuple(from_json(a) for a in d["args"]))
    if isinstance(d, list):
        return tuple(from_json(a) for a in d)
    return d
