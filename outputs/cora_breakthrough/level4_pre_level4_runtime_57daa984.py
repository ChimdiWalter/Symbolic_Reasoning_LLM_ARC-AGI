"""CORA V2.1: the minimal typed language the evidence actually supports.

Two properties distinguish this module from the V2 prototype.

First, it has no signature list of its own. The registry is built by reading
``outputs/cora_breakthrough/v2_1_semantic_contract_v2.json`` at import time,
and refuses to start if that file's hash has moved. A hardcoded table here
is exactly the transcription drift that let V2 diverge from its own frozen
specification.

Second, it obeys the contract's polymorphism policy. Where a rule's
polymorphism grade is COMPATIBLE, the reconstructed generality is NOT
implemented: only the instantiation that was actually observed. So
``Map_V1`` maps regions to colours and nothing else, and ``Compose_V1``
threads the observed pipeline rather than providing a composition calculus.
Widening either requires a dated design resolution, not an implementation
decision.

Rules the contract marks inactive have no implementation at all. They are
absent from the registry, so the enumerator cannot reach them by accident:
Function, MapOver, Compose-as-combinator, Fold, Repeat, Propagate_with_Seed,
Sequence_consumer and Collection_to_Grid.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = (ROOT / "outputs" / "cora_breakthrough"
                 / "v2_1_semantic_contract_v2.json")
FROZEN_HASH_PATH = (ROOT / "outputs" / "cora_breakthrough"
                    / "v2_1_contract_frozen_hash.txt")


class ContractDrift(RuntimeError):
    """The contract this module was built against has changed."""


def load_contract(verify: bool = True) -> dict:
    text = CONTRACT_PATH.read_bytes()
    if verify and FROZEN_HASH_PATH.exists():
        expected = FROZEN_HASH_PATH.read_text().strip()
        actual = hashlib.sha256(text).hexdigest()
        if expected and actual != expected:
            raise ContractDrift(
                f"contract hash {actual[:16]} does not match the frozen "
                f"{expected[:16]}; re-run the contract audits and re-freeze "
                f"before using this module")
    return json.loads(text)


CONTRACT = load_contract()


# --------------------------------------------------------------------------
# types: full parameterised terms, never head-type approximations
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Type:
    name: str
    args: tuple = ()

    def __str__(self):
        if not self.args:
            return self.name
        return f"{self.name}[{','.join(str(a) for a in self.args)}]"


def T(name, *args):
    return Type(name, tuple(args))


GRID = T("Grid")
REGION = T("Region")
ENTITY = T("Entity")
COLOUR = T("Colour")
PLACEMENT = T("Placement")
FEATURE_VALUE = T("FeatureValue")
SET_REGION = T("Set", REGION)
SET_ENTITY = T("Set", ENTITY)
SET_COLOURED = T("Set", T("Coloured"))
EXPR_REGION_COLOUR = T("Expr", REGION, COLOUR)
EXPR_REGION_FEATURE = T("Expr", REGION, FEATURE_VALUE)
EXPR_FEATURE_COLOUR = T("Expr", FEATURE_VALUE, COLOUR)

# terminal (vocabulary) types
PARTITION_EXPR = T("PartitionExpr")
SEGMENTATION_EXPR = T("SegmentationExpr")
PREDICATE = T("Predicate")
FEATURE_EXPR = T("FeatureExpr")
RELATION = T("Relation")
COLOUR_MAP = T("Map")
COLOUR_BIJECTION = T("ColourBijection")
TRANSFORM = T("Transform")
ANCHOR = T("Anchor")


def type_equal(a: Type, b: Type) -> bool:
    """Structural equality over FULL parameterised types.

    Deliberately not a head-type comparison: Set[Region] and Set[Placement]
    are different types, and the coarse contract checker's approximation
    must not leak into the runtime.
    """
    return a.name == b.name and len(a.args) == len(b.args) and \
        all(type_equal(x, y) for x, y in zip(a.args, b.args))


# --------------------------------------------------------------------------
# vocabulary
# --------------------------------------------------------------------------

def _components(mask, connectivity=4):
    steps = ((-1, 0), (1, 0), (0, -1), (0, 1))
    if connectivity == 8:
        steps = steps + ((-1, -1), (-1, 1), (1, -1), (1, 1))
    seen, out = set(), []
    for cell in sorted(mask):
        if cell in seen:
            continue
        comp, stack = {cell}, [cell]
        seen.add(cell)
        while stack:
            r, c = stack.pop()
            for dr, dc in steps:
                nb = (r + dr, c + dc)
                if nb in mask and nb not in seen:
                    seen.add(nb)
                    comp.add(nb)
                    stack.append(nb)
        out.append(frozenset(comp))
    return out


def background(grid):
    values, counts = np.unique(grid, return_counts=True)
    return int(values[int(np.argmax(counts))])


def _bg_components(grid):
    bg = background(grid)
    h, w = grid.shape
    return _components({(r, c) for r in range(h) for c in range(w)
                        if int(grid[r, c]) == bg})


def _enclosed(grid):
    h, w = grid.shape
    return [comp for comp in _bg_components(grid)
            if not any(r in (0, h - 1) or c in (0, w - 1) for r, c in comp)]


def _colour_components(grid, connectivity=4):
    bg = background(grid)
    h, w = grid.shape
    out = []
    for colour in sorted({int(v) for v in np.unique(grid)} - {bg}):
        out.extend(_components({(r, c) for r in range(h) for c in range(w)
                                if int(grid[r, c]) == colour}, connectivity))
    return out


def _panels(grid):
    h, w = grid.shape
    sep_rows = {r for r in range(h) if len({int(x) for x in grid[r, :]}) == 1}
    sep_cols = {c for c in range(w) if len({int(x) for x in grid[:, c]}) == 1}
    if not sep_rows and not sep_cols:
        return []

    def bands(n, seps):
        out, cur = [], []
        for i in range(n):
            if i in seps:
                if cur:
                    out.append(cur)
                cur = []
            else:
                cur.append(i)
        if cur:
            out.append(cur)
        return out

    rows = bands(h, sep_rows) or [list(range(h))]
    cols = bands(w, sep_cols) or [list(range(w))]
    return [frozenset((r, c) for r in a for c in b) for a in rows for b in cols]


PARTITION_VOCAB = {"enclosed_regions": _enclosed,
                   "background_components": _bg_components,
                   "colour_components": _colour_components,
                   "separator_panels": _panels}

SEGMENTATION_VOCAB = {"same_colour_4": lambda g: _colour_components(g, 4),
                      "same_colour_8": lambda g: _colour_components(g, 8)}


def descriptors(cells, grid) -> dict:
    rows = [r for r, _ in cells]
    cols = [c for _, c in cells]
    r0, c0, r1, c1 = min(rows), min(cols), max(rows), max(cols)
    h, w = grid.shape
    bh, bw = r1 - r0 + 1, c1 - c0 + 1
    ring = set()
    for r, c in cells:
        for nb in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
            if nb not in cells and 0 <= nb[0] < h and 0 <= nb[1] < w:
                ring.add(int(grid[nb]))
    colours = {int(grid[r, c]) for r, c in cells}
    return {"area": len(cells), "hw": (bh, bw),
            "shape": tuple(sorted((r - r0, c - c0) for r, c in cells)),
            "is_rect": len(cells) == bh * bw, "is_square": bh == bw,
            "touches_border": r0 == 0 or c0 == 0 or r1 == h - 1 or c1 == w - 1,
            "colour": (sorted(colours)[0] if len(colours) == 1 else None),
            "n_colours": len(colours),
            "neighbour_colours": tuple(sorted(ring)),
            "sole_neighbour_colour": (sorted(ring)[0] if len(ring) == 1 else None),
            "row_band": r0, "col_band": c0, "origin": (r0, c0)}


PREDICATE_VOCAB = {"all": lambda d: True,
                   "touching_border": lambda d: d["touches_border"],
                   "not_touching_border": lambda d: not d["touches_border"],
                   "rectangular": lambda d: d["is_rect"],
                   "not_rectangular": lambda d: not d["is_rect"],
                   "square": lambda d: d["is_square"],
                   "single_colour": lambda d: d["n_colours"] == 1}

FEATURE_VOCAB = ("sole_neighbour_colour", "touches_border", "is_rect",
                 "is_square", "area", "hw", "colour", "n_colours",
                 "neighbour_colours", "shape", "row_band", "col_band")

TERMINAL_VALUES = {
    str(PARTITION_EXPR): tuple(sorted(PARTITION_VOCAB)),
    str(SEGMENTATION_EXPR): tuple(sorted(SEGMENTATION_VOCAB)),
    str(PREDICATE): tuple(sorted(PREDICATE_VOCAB)),
    str(FEATURE_EXPR): FEATURE_VOCAB,
}

#: Slot types fitted from the demonstrations rather than enumerated.
INDUCED_TYPES = {str(COLOUR_MAP), str(COLOUR_BIJECTION), str(TRANSFORM),
                 str(ANCHOR)}


# --------------------------------------------------------------------------
# productions
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Production:
    name: str
    arg_types: tuple
    result_type: Type
    evaluate: Callable
    contract_grades: dict = field(default_factory=dict)
    cost: int = 1


@dataclass
class Ctx:
    grid: np.ndarray
    element: Any = None
    value: Any = None


# -- evaluators ------------------------------------------------------------

def _partition(ctx, name):
    build = PARTITION_VOCAB.get(name)
    if build is None:
        return None
    sets = build(ctx.grid)
    return tuple(sets) or None


def _entities(ctx, name):
    build = SEGMENTATION_VOCAB.get(name)
    if build is None:
        return None
    sets = build(ctx.grid)
    return tuple(sets) or None


def _select(ctx, sets, predicate):
    test = PREDICATE_VOCAB.get(predicate)
    if test is None or not sets:
        return None
    kept = tuple(s for s in sets if test(descriptors(s, ctx.grid)))
    return kept or None


def _key(ctx, feature):
    """Contextual expression: evaluated under the current element."""
    if ctx.element is None:
        return None
    return descriptors(ctx.element, ctx.grid).get(feature)


def _lookup(ctx, table):
    """Contextual expression: evaluated under the current value."""
    if ctx.value is None:
        return None
    mapping = dict(table)
    return int(mapping[ctx.value]) if ctx.value in mapping else None


def _map_v1(ctx, sets, expr_ast):
    """Observed instantiation only: regions to colours.

    The contract's Set[A] x Expr[A=>B] -> Set[B] is COMPATIBLE, not
    demonstrated, so the generality is deliberately not implemented.
    """
    if not sets or expr_ast is None:
        return None
    out = []
    for cells in sets:
        value = _eval(expr_ast, Ctx(ctx.grid, element=cells))
        if value is None:
            continue
        out.append((cells, int(value)))
    return tuple(out) or None


def _compose_v1(ctx, first_ast, second_ast):
    """Thread a value through two contextual expressions.

    Registered at the OBSERVED instantiation only:
    Expr[Region,FeatureValue] x Expr[FeatureValue,Colour] -> Expr[Region,Colour].
    That is what the pre-freeze pipeline did (Key then Lookup inside Map).
    The contract's general (A=>B) x (B=>C) form is COMPATIBLE, not
    demonstrated, so no composition calculus is provided.
    """
    value = _eval(first_ast, ctx)
    if value is None:
        return None
    return _eval(second_ast, Ctx(ctx.grid, ctx.element, value))


def _paint_each(ctx, coloured):
    """DR-02: the observed behaviour was per-region computed colours."""
    if not coloured:
        return None
    out = ctx.grid.copy()
    for cells, colour in coloured:
        for r, c in cells:
            out[r, c] = int(colour)
    return out


def _paint(ctx, sets, colour):
    if not sets or colour is None:
        return None
    out = ctx.grid.copy()
    for cells in sets:
        for r, c in cells:
            out[r, c] = int(colour)
    return out


def _unique(ctx, sets):
    return sets[0] if sets and len(sets) == 1 else None


def _argmax(ctx, sets, feature):
    return _extremum(ctx, sets, feature, max)


def _argmin(ctx, sets, feature):
    return _extremum(ctx, sets, feature, min)


def _extremum(ctx, sets, feature, pick):
    if not sets:
        return None
    values = [(descriptors(s, ctx.grid).get(feature), s) for s in sets]
    values = [(v, s) for v, s in values if isinstance(v, (int, float))]
    if not values:
        return None
    best = pick(values, key=lambda vs: vs[0])[0]
    winners = [s for v, s in values if v == best]
    return winners[0] if len(winners) == 1 else None


def _overlay(ctx, base, top):
    if base is None or top is None or base.shape != top.shape:
        return None
    bg = background(base)
    out = base.copy()
    mask = top != bg
    out[mask] = top[mask]
    return out


# --------------------------------------------------------------------------
# the registry is COMPILED FROM THE CONTRACT
#
# Python supplies execution semantics and nothing else.  Every argument type
# and result type below comes from the contract, either from a rule's own
# ``form`` or, for the policy-constrained rules, from that policy's
# ``implemented_signature``.  A signature written here in Python would be a
# second hand-maintained table, which is the exact drift this design exists
# to prevent.
# --------------------------------------------------------------------------

#: Behaviour only.  No signatures.
EVALUATORS = {
    "Partition": _partition,
    "Entities": _entities,
    "Select": _select,
    "Key": _key,
    "Lookup": _lookup,
    "Compose_V1": _compose_v1,
    "Map_V1": _map_v1,
    "PaintEach": _paint_each,
    "Paint": _paint,
    "Unique": _unique,
    "ArgMax": _argmax,
    "ArgMin": _argmin,
    "Overlay": _overlay,
}


def parse_type(text: str) -> Type:
    """Parse a contract type string into a Type term.

    ``Expr[A=>B]`` and ``Expr[A,B]`` are the same term: the contract writes
    the arrow form for readability.
    """
    text = text.strip().replace("=>", ",")
    if "[" not in text:
        return T(text)
    head, rest = text.split("[", 1)
    assert rest.endswith("]"), text
    parts, depth, current = [], 0, ""
    for ch in rest[:-1]:
        if ch == "," and depth == 0:
            parts.append(current)
            current = ""
            continue
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
        current += ch
    if current:
        parts.append(current)
    return T(head.strip(), *[parse_type(x) for x in parts])


def parse_signature(form: str):
    """(argument types, result type) from a contract 'A x B -> C' string."""
    left, right = form.rsplit("->", 1)
    args = [a.strip() for a in left.split(" x ") if a.strip()]
    # a leading Grid argument is supplied by the interpreter context
    # (recorded as CONTEXT_IMPLICIT by the exact-signature audit)
    if args and args[0].strip() == "Grid":
        args = args[1:]
    return tuple(parse_type(a) for a in args), parse_type(right)


def _contract_rules(contract) -> dict:
    out = {}
    for rule in contract["layer_A_evidence_minimal"]["judgements"]:
        out[rule["rule"]] = rule
    for rule in contract["layer_B_frozen_design"]["rules"]:
        out.setdefault(rule["rule"], rule)
    for rule in contract["active_productions"]:
        out.setdefault(rule["rule"], rule)
    return out


def compile_registry(contract) -> dict:
    """Build the runtime registry from the contract and its policy.

    Only the kernel the contract derives from the certified source programs
    is compiled, so the executable language is the smallest one able to
    reproduce those two concepts.
    """
    rules = _contract_rules(contract)
    policy = contract.get("polymorphism_policy", {}).get("instantiations", {})
    kernel = contract.get("v21_kernel", {}).get("rules") or sorted(EVALUATORS)
    inactive = set()
    for rule in contract["layer_B_frozen_design"]["rules"]:
        if not rule.get("active", False):
            inactive.add(rule["rule"])
    for rule in contract["inactive_unresolved"]:
        inactive.add(rule["rule"])

    registry = {}
    for name in kernel:
        if name in inactive:
            raise RuntimeError(f"kernel names a contract-inactive rule: {name}")
        evaluator = EVALUATORS.get(name)
        if evaluator is None:
            raise RuntimeError(f"no evaluator implemented for kernel rule {name}")
        constrained = policy.get(name, {}).get("implemented_signature")
        source = "polymorphism_policy" if constrained else "contract form"
        form = constrained or rules[name]["form"]
        arg_types, result_type = parse_signature(form)
        grades = {k: v for k, v in rules.get(name, {}).items()
                  if k.endswith("_grade")}
        registry[name] = Production(name, arg_types, result_type, evaluator,
                                    {**grades, "signature_source": source,
                                     "signature_text": form})
    return registry


REGISTRY = compile_registry(CONTRACT)


def contract_inactive() -> set:
    names = set()
    for rule in CONTRACT["layer_B_frozen_design"]["rules"]:
        if not rule.get("active", False):
            names.add(rule["rule"])
    for rule in CONTRACT["inactive_unresolved"]:
        names.add(rule["rule"])
    return names


INACTIVE = contract_inactive()
assert not (set(REGISTRY) & INACTIVE), \
    f"registry implements contract-inactive rules: {set(REGISTRY) & INACTIVE}"


# --------------------------------------------------------------------------
# interpreter
# --------------------------------------------------------------------------

def is_ast(value) -> bool:
    return isinstance(value, tuple) and len(value) == 2 \
        and isinstance(value[0], str) and value[0] in REGISTRY


def _eval(node, ctx):
    if not is_ast(node):
        return None
    op, args = node
    production = REGISTRY[op]
    if op == "Map_V1":
        sets = _eval(args[0], ctx) if is_ast(args[0]) else args[0]
        return production.evaluate(ctx, sets, args[1])
    if op in ("Key", "Lookup"):
        return production.evaluate(ctx, args[0])
    if op == "Compose_V1":
        return production.evaluate(ctx, args[0], args[1])
    values = []
    for arg in args:
        if is_ast(arg):
            child = _eval(arg, ctx)
            if child is None:
                return None
            values.append(child)
        elif isinstance(arg, str) and arg.startswith("?"):
            return None
        else:
            values.append(arg)
    try:
        return production.evaluate(ctx, *values)
    except Exception:
        return None


def evaluate(ast, grid) -> Optional[np.ndarray]:
    """Execute a well-typed AST; None when undefined on this input.

    ``Compose_V1`` is not a separate node: the observed pipeline is the AST's
    own nesting, which is the stage threading the evidence shows and nothing
    more general.
    """
    value = _eval(ast, Ctx(np.asarray(grid)))
    return value if isinstance(value, np.ndarray) else None


# --------------------------------------------------------------------------
# type checking over full parameterised types
# --------------------------------------------------------------------------

def type_of(ast) -> Optional[Type]:
    """The result type of a well-typed AST, or None if it does not typecheck."""
    if not is_ast(ast):
        return None
    op, args = ast
    production = REGISTRY[op]
    if len(args) != len(production.arg_types):
        return None
    for arg, expected in zip(args, production.arg_types):
        if is_ast(arg):
            got = type_of(arg)
            if got is None or not type_equal(got, expected):
                return None
        elif isinstance(arg, str) and arg.startswith("?"):
            if str(expected) not in INDUCED_TYPES:
                return None
        elif str(expected) in TERMINAL_VALUES:
            if arg not in TERMINAL_VALUES[str(expected)]:
                return None
        elif str(expected) in INDUCED_TYPES:
            continue                      # a fitted table or induced value
        else:
            return None
    return production.result_type


def free_slots(ast) -> dict:
    """Unfilled induced slots, mapped to their declared type."""
    out: dict = {}

    def walk(node):
        if not is_ast(node):
            return
        production = REGISTRY[node[0]]
        for arg, expected in zip(node[1], production.arg_types):
            if isinstance(arg, str) and arg.startswith("?"):
                out[arg] = expected
            elif is_ast(arg):
                walk(arg)

    walk(ast)
    return out


def instantiate(ast, bindings: dict):
    if isinstance(ast, str) and ast.startswith("?"):
        return bindings.get(ast, ast)
    if is_ast(ast):
        return (ast[0], tuple(instantiate(a, bindings) for a in ast[1]))
    return ast


def ast_nodes(ast) -> int:
    if not is_ast(ast):
        return 0
    total = REGISTRY[ast[0]].cost
    for arg in ast[1]:
        if is_ast(arg):
            total += ast_nodes(arg)
        elif isinstance(arg, tuple):
            total += len(arg)
    return total


def value_bound_count(ast) -> int:
    if not is_ast(ast):
        return 0
    total = 0
    for arg in ast[1]:
        if is_ast(arg):
            total += value_bound_count(arg)
        elif isinstance(arg, tuple):
            total += len(arg)
    return total


def ast_depth(ast) -> int:
    if not is_ast(ast):
        return 0
    depths = [ast_depth(a) for a in ast[1] if is_ast(a)]
    return 1 + (max(depths) if depths else 0)


def to_json(ast):
    if is_ast(ast):
        return {"op": ast[0], "args": [to_json(a) for a in ast[1]]}
    return {"lit": json.dumps(ast, default=list)}


def from_json(d):
    if "lit" in d:
        return _tuplify(json.loads(d["lit"]))
    return (d["op"], tuple(from_json(a) for a in d["args"]))


def _tuplify(value):
    if isinstance(value, list):
        return tuple(_tuplify(v) for v in value)
    return value


def concepts_used(ast) -> list:
    out = []
    if not is_ast(ast):
        return out
    op, args = ast
    out.append(op)
    for arg in args:
        if is_ast(arg):
            out.extend(concepts_used(arg))
        elif isinstance(arg, str):
            out.append(f"{op}:{arg}")
    return out
