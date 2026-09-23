"""A tiny meta-language of generic combinators, and programs built from it.

Nothing here names an ARC transformation.  There is no "fill the regions"
node: there is a way to carve a grid into cell sets, a way to keep some of
them, a way to compute a key, a way to look a value up, and a way to paint.
Whatever ARC-shaped abstraction the system ends up using has to be a
COMPOSITION of these, discovered by search and named by the anti-unifier --
which is the only way "the machine invented the concept" can mean anything.

An AST is a plain nested tuple ``(op, args)`` so it is hashable, comparable
and JSON-round-trippable without machinery.  Every program is a pure
function of (AST, input grid).

MDL counts AST nodes and induced-table entries.  It never counts painted
cells: a spelling that stores its output must not be able to look cheap.
"""
from __future__ import annotations

import json
from typing import Any, Optional

import numpy as np

# --------------------------------------------------------------------------
# primitive vocabulary
# --------------------------------------------------------------------------

#: Ways to carve a grid into cell sets.  Each is a pure function of the grid.
PARTITIONS: dict = {}

#: Predicates over a cell set's descriptors.
PREDICATES: dict = {}

#: Named descriptors a Key node may read.
KEY_FEATURES: tuple = ()


def register_vocabulary(partitions: dict, predicates: dict,
                        key_features: tuple) -> None:
    """Install the primitive vocabulary (called by meta_induction)."""
    global PARTITIONS, PREDICATES, KEY_FEATURES
    PARTITIONS = dict(partitions)
    PREDICATES = dict(predicates)
    KEY_FEATURES = tuple(key_features)


# --------------------------------------------------------------------------
# AST constructors -- (op, args); args are literals or child ASTs
# --------------------------------------------------------------------------

def Partition(name: str):
    return ("Partition", (name,))


def Select(predicate: str):
    return ("Select", (predicate,))


def Key(feature: str):
    return ("Key", (feature,))


def Lookup(table: tuple):
    return ("Lookup", (table,))


def Map(key_node, lookup_node):
    return ("Map", (key_node, lookup_node))


def Paint():
    return ("Paint", ())


def Compose(*stages):
    return ("Compose", tuple(stages))


# --------------------------------------------------------------------------
# structural accounting
# --------------------------------------------------------------------------

def ast_nodes(ast) -> int:
    """Node count, with an induced table costing one per entry."""
    op, args = ast
    if op == "Lookup":
        return 1 + len(args[0])
    total = 1
    for arg in args:
        if isinstance(arg, tuple) and len(arg) == 2 and isinstance(arg[0], str) \
                and arg[0] in _OPS:
            total += ast_nodes(arg)
    return total


_OPS = {"Partition", "Select", "Key", "Lookup", "Map", "Paint", "Compose"}


def value_bound_count(ast) -> int:
    """Literals bound to observed training values (i.e. table entries)."""
    op, args = ast
    if op == "Lookup":
        return len(args[0])
    total = 0
    for arg in args:
        if isinstance(arg, tuple) and len(arg) == 2 and isinstance(arg[0], str) \
                and arg[0] in _OPS:
            total += value_bound_count(arg)
    return total


def concepts_used(ast) -> list:
    """Grammar concepts this AST exercises, for provenance and attribution."""
    out: list = []

    def walk(node):
        op, args = node
        if op == "Partition":
            out.append(f"Partition:{args[0]}")
        elif op == "Select":
            out.append(f"Select:{args[0]}")
        elif op == "Key":
            out.append(f"Key:{args[0]}")
        elif op == "Lookup":
            out.append("Lookup")
        else:
            out.append(op)
        for arg in args:
            if isinstance(arg, tuple) and len(arg) == 2 \
                    and isinstance(arg[0], str) and arg[0] in _OPS:
                walk(arg)

    walk(ast)
    return out


# --------------------------------------------------------------------------
# execution
# --------------------------------------------------------------------------

def evaluate(ast, grid: np.ndarray, descriptors_fn) -> Optional[np.ndarray]:
    """Run a Compose pipeline over ``grid``; None when it paints nothing.

    Pipeline state is (cell sets, colour per set).  Stages narrow the sets,
    assign colours, then paint.  Any stage that cannot apply aborts the
    program rather than guessing -- an unseen key contributes no cells.
    """
    op, args = ast
    if op != "Compose":
        raise ValueError("a program must be a Compose pipeline")
    sets: list = []
    colours: dict = {}
    out = grid.copy()
    painted = False
    for stage in args:
        sop, sargs = stage
        if sop == "Partition":
            build = PARTITIONS.get(sargs[0])
            if build is None:
                return None
            sets = build(grid)
            if not sets:
                return None
        elif sop == "Select":
            predicate = PREDICATES.get(sargs[0])
            if predicate is None:
                return None
            sets = [s for s in sets if predicate(descriptors_fn(s, grid))]
            if not sets:
                return None
        elif sop == "Map":
            key_node, lookup_node = sargs
            feature = key_node[1][0]
            table = dict(lookup_node[1][0])
            colours = {}
            for cells in sets:
                key = descriptors_fn(cells, grid).get(feature)
                if key in table:
                    colours[cells] = int(table[key])
        elif sop == "Paint":
            for cells, colour in colours.items():
                for r, c in cells:
                    out[r, c] = colour
                painted = True
        else:
            return None
    return out if painted else None


# --------------------------------------------------------------------------
# serialization
# --------------------------------------------------------------------------

def ast_to_json(ast):
    op, args = ast
    return {"op": op, "args": [_arg_to_json(a) for a in args]}


def _arg_to_json(arg):
    if isinstance(arg, tuple) and len(arg) == 2 and isinstance(arg[0], str) \
            and arg[0] in _OPS:
        return ast_to_json(arg)
    return {"lit": json.dumps(arg, default=list)}


def ast_from_json(d):
    return (d["op"], tuple(_arg_from_json(a) for a in d["args"]))


def _arg_from_json(a):
    if "lit" in a:
        return _tuplify(json.loads(a["lit"]))
    return ast_from_json(a)


def _tuplify(value):
    if isinstance(value, list):
        return tuple(_tuplify(v) for v in value)
    return value


# --------------------------------------------------------------------------
# anti-unification -- where a reusable concept actually comes from
# --------------------------------------------------------------------------

def anti_unify(asts: list) -> Optional[tuple]:
    """Least general generalization of several ASTs.

    Positions where every AST agrees stay concrete; positions that differ
    become typed slots.  The result is a SCHEMA: the shared machinery the
    individual discoveries are instances of.  Returns None when the ASTs
    share no structure, or when they are identical (nothing was abstracted).
    """
    if len(asts) < 2:
        return None
    slots: list = []
    schema = _au(asts, slots)
    if schema is None or not slots:
        return None
    return schema, tuple(slots)


def _au(nodes: list, slots: list):
    first = nodes[0]
    if not all(isinstance(n, tuple) and len(n) == 2 for n in nodes):
        return _slot(nodes, slots)
    ops = {n[0] for n in nodes}
    if len(ops) != 1:
        return _slot(nodes, slots)
    op = first[0]
    arities = {len(n[1]) for n in nodes}
    if len(arities) != 1:
        return _slot(nodes, slots)
    args = []
    for i in range(len(first[1])):
        children = [n[1][i] for n in nodes]
        if all(isinstance(c, tuple) and len(c) == 2 and isinstance(c[0], str)
               and c[0] in _OPS for c in children):
            args.append(_au(children, slots))
        elif len({repr(c) for c in children}) == 1:
            args.append(children[0])
        else:
            args.append(_slot(children, slots))
    return (op, tuple(args))


def _slot(children, slots):
    name = f"?{len(slots)}"
    slots.append({"slot": name,
                  "observed": sorted({repr(c) for c in children})})
    return name


def instantiate(schema, bindings: dict):
    """Fill a schema's slots, producing a concrete AST."""
    if isinstance(schema, str) and schema.startswith("?"):
        # an unbound slot stays a slot: partial instantiation is normal
        # (enumerable slots are bound first, induced ones fitted after)
        return bindings.get(schema, schema)
    if isinstance(schema, tuple) and len(schema) == 2 \
            and isinstance(schema[0], str) and schema[0] in _OPS:
        return (schema[0], tuple(instantiate(a, bindings) for a in schema[1]))
    return schema


# --------------------------------------------------------------------------
# slot typing -- read off the grammar, not off any particular concept
# --------------------------------------------------------------------------

#: Typed signatures: op -> (argument types, result type).  A slot's type
#: comes from its ARGUMENT POSITION in the production that contains it, not
#: from the name of its parent node -- so an operator with several typed
#: arguments (a transform and an anchor, say) types each of them correctly.
#: ``None`` as the argument tuple marks a variadic pipeline node.
OP_SIGNATURES: dict = {
    "Compose":   (None, "Grid"),
    "Partition": (("PartitionExpr",), "Set[Region]"),
    "Select":    (("Predicate",), "Set[Region]"),
    "Key":       (("FeatureExpr",), "FeatureValue"),
    "Lookup":    (("Map[FeatureValue,Colour]",), "Colour"),
    "Map":       (("Function", "Function"), "Set[Coloured]"),
    "Paint":     ((), "Grid"),
}

#: Slot types whose value is enumerated from a vocabulary.
ENUMERABLE_TYPES: dict = {
    "PartitionExpr": lambda: tuple(sorted(PARTITIONS)),
    "Predicate": lambda: tuple(sorted(PREDICATES)),
    "FeatureExpr": lambda: tuple(KEY_FEATURES),
}

#: Slot types whose value must be INDUCED from the demonstrations.  The
#: fitting procedure for each lives in a registry keyed by this type, so a
#: schema carrying a colour bijection, a lattice or an anchor is fitted by
#: the same dispatch that fits a feature map.
INDUCED_TYPES: frozenset = frozenset({
    "Map[FeatureValue,Colour]",
    "ColourBijection",
    "Lattice",
    "Anchor",
    "Transform",
})

# retained for compatibility with the earlier position-name mapping
ENUMERABLE_KINDS = frozenset(ENUMERABLE_TYPES)
INDUCED_KINDS = INDUCED_TYPES


def free_slot_types(schema) -> dict:
    """Map every free slot to its TYPE, taken from the typed signature of
    the production it sits in (by argument position)."""
    types: dict = {}

    def walk(node):
        if not (isinstance(node, tuple) and len(node) == 2):
            return
        op, args = node
        signature = OP_SIGNATURES.get(op)
        arg_types = signature[0] if signature else None
        for index, arg in enumerate(args):
            if isinstance(arg, str) and arg.startswith("?"):
                if arg_types and index < len(arg_types):
                    types[arg] = arg_types[index]
            else:
                walk(arg)

    walk(schema)
    return types


def slot_domain(slot_type: str) -> tuple:
    """The values an enumerable slot of this type may take."""
    domain = ENUMERABLE_TYPES.get(slot_type)
    return domain() if domain else ()


def type_signature(schema) -> str:
    """Human-readable typing, persisted with the concept."""
    types = free_slot_types(schema)
    args = ", ".join(f"{slot} : {slot_type}"
                     for slot, slot_type in sorted(types.items()))
    result = OP_SIGNATURES.get(schema[0], (None, "Grid"))[1]
    return f"({args}) -> {result}"


def bound_values(ast) -> dict:
    """The concrete values a fully instantiated AST binds, by kind."""
    out: dict = {}

    def walk(node):
        if not (isinstance(node, tuple) and len(node) == 2):
            return
        op, args = node
        signature = OP_SIGNATURES.get(op)
        arg_types = signature[0] if signature else None
        for index, arg in enumerate(args):
            if isinstance(arg, tuple) and len(arg) == 2 \
                    and isinstance(arg[0], str) and arg[0] in _OPS:
                walk(arg)
            elif arg_types and index < len(arg_types):
                out[arg_types[index]] = arg

    walk(ast)
    return out
