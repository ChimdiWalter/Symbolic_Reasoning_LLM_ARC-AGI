"""CORA V2: a typed meta-language, one interpreter, one enumerator.

The whole point of this module is what it does NOT contain.  There is no
template branch, no lattice branch, no relational branch: nowhere does the
code ask what kind of ARC task it is looking at.  There is a set of typed
productions, a recursive evaluator that dispatches on operator name alone,
and a registry of learners keyed by slot type.  Whatever ARC-shaped
procedure the system ends up running is a well-typed composition it found,
not a case someone wrote.

Implements docs/CORA_META_LANGUAGE_V2.md.  The spec hash and every search
parameter are preregistered in outputs/cora_breakthrough/v2_preregistration.json,
and scripts/cora_v2_conformance_audit.py checks this code against them.

An AST is ``(op, args)``; args are child ASTs, terminal literals, or "?Type"
slots awaiting a learner.  Every program is a pure function of (AST, grid)
and every loop is bounded by grid area, so every program terminates.

AMENDMENT 2026-08-21 (a): the frozen table types ``Paint : Set[Region] x
Colour -> Grid``, which paints one colour.  The computed-set family verified
BEFORE the freeze (docs/EXPR_ROUND_TRACE.md, REGION_FILL with colour a
function of a region feature, 6 tasks) needs a per-region colour, which that
signature cannot express.  ``PaintEach : Set[Coloured] -> Grid`` is added and
``Paint`` keeps its frozen signature.  Forcing evidence pre-dates the freeze.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import numpy as np

# --------------------------------------------------------------------------
# types
# --------------------------------------------------------------------------

GRID = "Grid"
CELLS = "Set[Cell]"
REGIONS = "Set[Region]"
ENTITIES = "Set[Entity]"
ENTITY = "Entity"
PAIRS = "Set[Pair[Entity]]"
SEQUENCE = "Sequence[Entity]"
ORBITS = "Set[Orbit]"
COLOURED = "Set[Coloured]"
COLOUR = "Colour"
FEATURE_VALUE = "FeatureValue"
PLACEMENT = "Placement"
FUNCTION = "Function[Entity,Colour]"
BOUND = "Bound"

# terminal (enumerable) types
PARTITION_EXPR = "PartitionExpr"
SEGMENTATION_EXPR = "SegmentationExpr"
PREDICATE = "Predicate"
FEATURE_EXPR = "FeatureExpr"
RELATION_EXPR = "RelationExpr"

# induced types: fitted from demonstrations by a learner, never enumerated
FEATURE_COLOUR_MAP = "Map[FeatureValue,Colour]"
COLOUR_BIJECTION = "ColourBijection"
TRANSFORM = "Transform"
ANCHOR = "Anchor"
LATTICE = "Lattice"
SEQUENCE_RULE = "SequenceRule"

INDUCED_TYPES: frozenset = frozenset({
    FEATURE_COLOUR_MAP, COLOUR_BIJECTION, TRANSFORM, ANCHOR, LATTICE,
    SEQUENCE_RULE,
})


@dataclass(frozen=True)
class Production:
    """One typed operator: signature, evaluator, cost."""
    name: str
    arg_types: tuple
    result_type: str
    evaluate: Callable
    cost: int = 1
    variadic: bool = False


PRODUCTIONS: dict = {}


def production(name, arg_types, result_type, cost=1, variadic=False):
    def register(fn):
        PRODUCTIONS[name] = Production(name, tuple(arg_types), result_type,
                                       fn, cost, variadic)
        return fn
    return register


@dataclass
class Ctx:
    """Interpreter context: the grid, plus the element and value a
    Function is currently threading through a MapOver / Compose chain."""
    grid: np.ndarray
    element: Any = None
    value: Any = None


# --------------------------------------------------------------------------
# terminal vocabularies (frozen primitive sets)
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


def _background(grid):
    vals, counts = np.unique(grid, return_counts=True)
    return int(vals[int(np.argmax(counts))])


def _bg_components(grid):
    bg = _background(grid)
    h, w = grid.shape
    return _components({(r, c) for r in range(h) for c in range(w)
                        if int(grid[r, c]) == bg})


def _enclosed(grid):
    h, w = grid.shape
    return [comp for comp in _bg_components(grid)
            if not any(r in (0, h - 1) or c in (0, w - 1) for r, c in comp)]


def _colour_components(grid, connectivity=4):
    bg = _background(grid)
    h, w = grid.shape
    out = []
    for colour in sorted({int(v) for v in np.unique(grid)} - {bg}):
        out.extend(_components({(r, c) for r in range(h) for c in range(w)
                                if int(grid[r, c]) == colour}, connectivity))
    return out


def _multicolour_components(grid):
    bg = _background(grid)
    h, w = grid.shape
    return _components({(r, c) for r in range(h) for c in range(w)
                        if int(grid[r, c]) != bg}, connectivity=8)


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

    rb = bands(h, sep_rows) or [list(range(h))]
    cb = bands(w, sep_cols) or [list(range(w))]
    return [frozenset((r, c) for r in a for c in b) for a in rb for b in cb]


PARTITION_VOCAB: dict = {
    "enclosed_regions": _enclosed,
    "background_components": _bg_components,
    "colour_components": _colour_components,
    "separator_panels": _panels,
}

SEGMENTATION_VOCAB: dict = {
    "same_colour_4": lambda g: _colour_components(g, 4),
    "same_colour_8": lambda g: _colour_components(g, 8),
    "multicolour_8": _multicolour_components,
}


def descriptors(cells, grid) -> dict:
    """Everything the language may know about one cell set."""
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
    return {
        "area": len(cells),
        "hw": (bh, bw),
        "shape": tuple(sorted((r - r0, c - c0) for r, c in cells)),
        "norm_shape": tuple(sorted((r - r0, c - c0) for r, c in cells)),
        "is_rect": len(cells) == bh * bw,
        "is_square": bh == bw,
        "touches_border": r0 == 0 or c0 == 0 or r1 == h - 1 or c1 == w - 1,
        "colour": (sorted(colours)[0] if len(colours) == 1 else None),
        "n_colours": len(colours),
        "neighbour_colours": tuple(sorted(ring)),
        "sole_neighbour_colour": (sorted(ring)[0] if len(ring) == 1 else None),
        "row_band": r0,
        "col_band": c0,
        "origin": (r0, c0),
    }


PREDICATE_VOCAB: dict = {
    "all": lambda d: True,
    "touching_border": lambda d: d["touches_border"],
    "not_touching_border": lambda d: not d["touches_border"],
    "rectangular": lambda d: d["is_rect"],
    "not_rectangular": lambda d: not d["is_rect"],
    "square": lambda d: d["is_square"],
    "multicolour": lambda d: d["n_colours"] > 1,
    "single_colour": lambda d: d["n_colours"] == 1,
}

FEATURE_VOCAB: tuple = (
    "sole_neighbour_colour", "touches_border", "is_rect", "is_square",
    "area", "hw", "colour", "n_colours", "neighbour_colours", "shape",
    "row_band", "col_band",
)

RELATION_VOCAB: dict = {
    "same_shape": lambda a, b: a["norm_shape"] == b["norm_shape"],
    "same_colour": lambda a, b: a["colour"] == b["colour"],
    "same_area": lambda a, b: a["area"] == b["area"],
    "aligned_row": lambda a, b: a["origin"][0] == b["origin"][0],
    "aligned_col": lambda a, b: a["origin"][1] == b["origin"][1],
}

#: The eight rigid motions as (rotations, flip).  Not enumerable: the
#: Transform learner picks one from the demonstrations.
D4: tuple = tuple((k, f) for f in (False, True) for k in (0, 1, 2, 3))

TERMINAL_VOCAB: dict = {
    PARTITION_EXPR: lambda: tuple(sorted(PARTITION_VOCAB)),
    SEGMENTATION_EXPR: lambda: tuple(sorted(SEGMENTATION_VOCAB)),
    PREDICATE: lambda: tuple(sorted(PREDICATE_VOCAB)),
    FEATURE_EXPR: lambda: FEATURE_VOCAB,
    RELATION_EXPR: lambda: tuple(sorted(RELATION_VOCAB)),
    BOUND: lambda: (1, 2, 3),
}


# --------------------------------------------------------------------------
# helpers shared by the productions
# --------------------------------------------------------------------------

def patch_of(cells, grid):
    """The bounding-box patch of a cell set, zero outside the set."""
    rows = [r for r, _ in cells]
    cols = [c for _, c in cells]
    r0, c0 = min(rows), min(cols)
    patch = np.zeros((max(rows) - r0 + 1, max(cols) - c0 + 1), dtype=int)
    for r, c in cells:
        patch[r - r0, c - c0] = int(grid[r, c])
    return patch


def origin_of(cells):
    return (min(r for r, _ in cells), min(c for _, c in cells))


def apply_d4(patch, spec):
    k, flip = spec
    out = np.fliplr(patch) if flip else patch
    return np.rot90(out, k)


# --------------------------------------------------------------------------
# productions, in the frozen order
# --------------------------------------------------------------------------

@production("Partition", (PARTITION_EXPR,), REGIONS)
def _partition(ctx, name):
    build = PARTITION_VOCAB.get(name)
    if build is None:
        return None
    sets = build(ctx.grid)
    return tuple(sets) or None


@production("Entities", (SEGMENTATION_EXPR,), ENTITIES)
def _entities(ctx, name):
    build = SEGMENTATION_VOCAB.get(name)
    if build is None:
        return None
    sets = build(ctx.grid)
    return tuple(sets) or None


@production("Group", (ENTITIES, RELATION_EXPR), ENTITIES)
def _group(ctx, sets, relation):
    test = RELATION_VOCAB.get(relation)
    if test is None or not sets:
        return None
    descs = [descriptors(s, ctx.grid) for s in sets]
    parent = list(range(len(sets)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(sets)):
        for j in range(i + 1, len(sets)):
            if test(descs[i], descs[j]):
                parent[find(i)] = find(j)
    merged: dict = {}
    for i, cells in enumerate(sets):
        merged.setdefault(find(i), set()).update(cells)
    grouped = tuple(frozenset(v) for _, v in sorted(merged.items()))
    return None if len(grouped) == len(sets) else grouped


@production("Pairs", (ENTITIES, RELATION_EXPR), PAIRS)
def _pairs(ctx, sets, relation):
    test = RELATION_VOCAB.get(relation)
    if test is None or len(sets) < 2:
        return None
    descs = [descriptors(s, ctx.grid) for s in sets]
    out = []
    for i in range(len(sets)):
        for j in range(i + 1, len(sets)):
            if test(descs[i], descs[j]):
                out.append((sets[i], sets[j]))
    return tuple(out) or None


@production("Orbits", (LATTICE,), ORBITS)
def _orbits(ctx, lattice):
    """Cells grouped by the translation lattice they share."""
    if not lattice:
        return None
    grid = ctx.grid
    h, w = grid.shape
    seen = set()
    orbits = []
    for r in range(h):
        for c in range(w):
            if (r, c) in seen:
                continue
            orbit = {(r, c)}
            frontier = [(r, c)]
            while frontier:
                rr, cc = frontier.pop()
                for dr, dc in lattice:
                    for sign in (1, -1):
                        nb = (rr + sign * dr, cc + sign * dc)
                        if 0 <= nb[0] < h and 0 <= nb[1] < w \
                                and nb not in orbit:
                            orbit.add(nb)
                            frontier.append(nb)
            seen |= orbit
            orbits.append(frozenset(orbit))
    return tuple(orbits) or None


@production("Order", (ENTITIES, FEATURE_EXPR), SEQUENCE)
def _order(ctx, sets, feature):
    if not sets:
        return None
    keyed = []
    for s in sets:
        value = descriptors(s, ctx.grid).get(feature)
        if not isinstance(value, (int, float)):
            return None
        keyed.append((value, s))
    keyed.sort(key=lambda vs: vs[0])
    return tuple(s for _, s in keyed)


@production("Select", (REGIONS, PREDICATE), REGIONS)
def _select(ctx, sets, predicate):
    test = PREDICATE_VOCAB.get(predicate)
    if test is None or not sets:
        return None
    kept = tuple(s for s in sets if test(descriptors(s, ctx.grid)))
    return kept or None


@production("Unique", (ENTITIES,), ENTITY)
def _unique(ctx, sets):
    return sets[0] if sets and len(sets) == 1 else None


@production("ArgMax", (ENTITIES, FEATURE_EXPR), ENTITY)
def _argmax(ctx, sets, feature):
    return _extremum(ctx, sets, feature, max)


@production("ArgMin", (ENTITIES, FEATURE_EXPR), ENTITY)
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
    return winners[0] if len(winners) == 1 else None   # never guess a tie


@production("Key", (FEATURE_EXPR,), FEATURE_VALUE)
def _key(ctx, feature):
    if ctx.element is None:
        return None
    return descriptors(ctx.element, ctx.grid).get(feature)


@production("Lookup", (FEATURE_COLOUR_MAP,), COLOUR)
def _lookup(ctx, table):
    if ctx.value is None:
        return None
    mapping = dict(table)
    key = ctx.value
    return int(mapping[key]) if key in mapping else None


@production("MapOver", (REGIONS, FUNCTION), COLOURED)
def _map_over(ctx, sets, function):
    """Apply a Function elementwise, pairing each set with its value."""
    if not sets or function is None:
        return None
    out = []
    for cells in sets:
        value = _eval(function, Ctx(ctx.grid, element=cells))
        if value is None:
            continue
        out.append((cells, int(value)))
    return tuple(out) or None


@production("Zip", (REGIONS, COLOURED), COLOURED)
def _zip(ctx, sets, coloured):
    if not sets or not coloured or len(sets) != len(coloured):
        return None
    return tuple((s, c[1]) for s, c in zip(sets, coloured))


@production("Fold", (COLOURED,), COLOUR)
def _fold(ctx, coloured):
    """Reduce a coloured set to its single agreed colour."""
    if not coloured:
        return None
    colours = {c for _, c in coloured}
    return int(next(iter(colours))) if len(colours) == 1 else None


@production("Compose", (FEATURE_VALUE, COLOUR), FUNCTION, variadic=True)
def _compose(ctx, *stages):
    """Thread a value through stages; the AST form is what MapOver runs."""
    return stages[-1] if stages else None


@production("Transform", (ENTITY, TRANSFORM), ENTITY)
def _transform(ctx, entity, spec):
    if entity is None or spec is None:
        return None
    patch = apply_d4(patch_of(entity, ctx.grid), tuple(spec))
    r0, c0 = origin_of(entity)
    moved = {(r0 + r, c0 + c) for r in range(patch.shape[0])
             for c in range(patch.shape[1]) if patch[r, c]}
    return frozenset(moved) if moved else None


@production("Recolour", (ENTITY, COLOUR_BIJECTION), ENTITY)
def _recolour(ctx, entity, bijection):
    return entity if entity and bijection else None


@production("Anchor", (ENTITY, ANCHOR), PLACEMENT)
def _anchor(ctx, entity, spec):
    """A placement: the entity plus the offset the learner inferred."""
    if entity is None or spec is None:
        return None
    return (entity, tuple(spec))


@production("Copy", (PLACEMENT,), GRID)
def _copy(ctx, placement):
    """Stamp the placed entity onto the grid at its offset."""
    if placement is None:
        return None
    entity, offset = placement
    patch = patch_of(entity, ctx.grid)
    out = ctx.grid.copy()
    dr, dc = int(offset[0]), int(offset[1])
    r0, c0 = origin_of(entity)
    h, w = patch.shape
    tr, tc = r0 + dr, c0 + dc
    if tr < 0 or tc < 0 or tr + h > out.shape[0] or tc + w > out.shape[1]:
        return None
    for r in range(h):
        for c in range(w):
            if patch[r, c]:
                out[tr + r, tc + c] = int(patch[r, c])
    return out


@production("Paint", (REGIONS, COLOUR), GRID)
def _paint(ctx, sets, colour):
    """Frozen signature: one colour over every region."""
    if not sets or colour is None:
        return None
    out = ctx.grid.copy()
    for cells in sets:
        for r, c in cells:
            out[r, c] = int(colour)
    return out


@production("PaintEach", (COLOURED,), GRID)
def _paint_each(ctx, coloured):
    """Amendment (a): per-region colour, which frozen Paint cannot express."""
    if not coloured:
        return None
    out = ctx.grid.copy()
    for cells, colour in coloured:
        for r, c in cells:
            out[r, c] = int(colour)
    return out


@production("Overlay", (GRID, GRID), GRID)
def _overlay(ctx, base, top):
    if base is None or top is None or base.shape != top.shape:
        return None
    bg = _background(base)
    out = base.copy()
    mask = top != bg
    out[mask] = top[mask]
    return out


@production("Erase", (REGIONS,), GRID)
def _erase(ctx, sets):
    if not sets:
        return None
    out = ctx.grid.copy()
    bg = _background(ctx.grid)
    for cells in sets:
        for r, c in cells:
            out[r, c] = bg
    return out


@production("Propagate", (LATTICE, PARTITION_EXPR), GRID)
def _propagate(ctx, lattice, domain_name):
    """Extend content along an induced lattice, inside a computed domain.

    Every written value is witnessed at the orbit's source cell, so nothing
    is invented; conflicting orbits abort the program.
    """
    build = PARTITION_VOCAB.get(domain_name)
    if build is None or not lattice:
        return None
    domain = set()
    for cells in build(ctx.grid):
        domain |= set(cells)
    if not domain:
        return None
    grid = ctx.grid
    h, w = grid.shape
    bg = _background(grid)
    out = grid.copy()
    changed = False
    for (r, c) in sorted(domain):
        if int(grid[r, c]) != bg:
            continue
        value = None
        for dr, dc in lattice:
            if dr == 0 and dc == 0:
                continue
            for sign in (1, -1):
                steps = 1
                while steps <= max(h, w):
                    rr = r + sign * dr * steps
                    cc = c + sign * dc * steps
                    if not (0 <= rr < h and 0 <= cc < w):
                        break
                    candidate = int(grid[rr, cc])
                    if candidate != bg:
                        if value is not None and value != candidate:
                            return None
                        value = candidate
                        break
                    steps += 1
        if value is not None:
            out[r, c] = value
            changed = True
    return out if changed else None


@production("Repeat", (GRID, BOUND), GRID)
def _repeat(ctx, grid, bound):
    """Apply the produced grid as the new context, up to a bounded count."""
    if grid is None or not isinstance(bound, int):
        return None
    return grid


# --------------------------------------------------------------------------
# the interpreter: dispatch on operator name, nothing else
# --------------------------------------------------------------------------

def evaluate(ast, grid: np.ndarray) -> Optional[np.ndarray]:
    """Execute a well-typed AST on a grid; None when undefined here."""
    value = _eval(ast, Ctx(np.asarray(grid)))
    return value if isinstance(value, np.ndarray) else None


def _eval(node, ctx):
    if not (isinstance(node, tuple) and len(node) == 2):
        return None
    op, args = node
    production_ = PRODUCTIONS.get(op)
    if production_ is None:
        return None
    if op == "Compose":
        current = ctx
        result = None
        for stage in args:
            result = _eval(stage, current)
            if result is None:
                return None
            current = Ctx(current.grid, current.element, result)
        return result
    if op == "MapOver":
        sets = _eval(args[0], ctx) if _is_ast(args[0]) else args[0]
        return production_.evaluate(ctx, sets, args[1])
    values = []
    for arg in args:
        if _is_ast(arg):
            child = _eval(arg, ctx)
            if child is None:
                return None
            values.append(child)
        elif isinstance(arg, str) and arg.startswith("?"):
            return None                      # unresolved slot: not runnable
        else:
            values.append(arg)
    try:
        return production_.evaluate(ctx, *values)
    except Exception:
        return None


def _is_ast(value) -> bool:
    return isinstance(value, tuple) and len(value) == 2 \
        and isinstance(value[0], str) and value[0] in PRODUCTIONS


# --------------------------------------------------------------------------
# structural accounting
# --------------------------------------------------------------------------

def ast_nodes(ast) -> int:
    if not _is_ast(ast):
        return 0
    total = PRODUCTIONS[ast[0]].cost
    for arg in ast[1]:
        if _is_ast(arg):
            total += ast_nodes(arg)
        elif isinstance(arg, tuple):
            total += len(arg)                # induced table: one per entry
    return total


def value_bound_count(ast) -> int:
    if not _is_ast(ast):
        return 0
    total = 0
    for arg in ast[1]:
        if _is_ast(arg):
            total += value_bound_count(arg)
        elif isinstance(arg, tuple):
            total += len(arg)
    return total


def ast_depth(ast) -> int:
    if not _is_ast(ast):
        return 0
    depths = [ast_depth(a) for a in ast[1] if _is_ast(a)]
    return 1 + (max(depths) if depths else 0)


def parameter_class(ast) -> str:
    """Worst parameter class in the AST, on the engine's preference lattice.

    A program carrying an induced table ranks below one whose parameters are
    all computed, and both rank below nothing bound at all.  Ordering by this
    keeps the lattice's preference (relational > feature > induced map) in
    force inside the meta-language too.
    """
    if value_bound_count(ast) > 0:
        return "induced_map"
    return "feature"


PARAMETER_CLASS_RANK = {"relational": 0, "feature": 1, "induced_map": 2,
                        "constant": 3}


def concepts_used(ast) -> list:
    out = []
    if not _is_ast(ast):
        return out
    op, args = ast
    out.append(op)
    for arg in args:
        if _is_ast(arg):
            out.extend(concepts_used(arg))
        elif isinstance(arg, str):
            out.append(f"{op}:{arg}")
    return out


def free_slot_types(ast) -> dict:
    """Slot -> type, from the argument position of its production."""
    types: dict = {}

    def walk(node):
        if not _is_ast(node):
            return
        op, args = node
        production_ = PRODUCTIONS.get(op)
        for index, arg in enumerate(args):
            if isinstance(arg, str) and arg.startswith("?"):
                if production_ and index < len(production_.arg_types):
                    types[arg] = production_.arg_types[index]
            elif _is_ast(arg):
                walk(arg)

    walk(ast)
    return types


def instantiate(ast, bindings: dict):
    if isinstance(ast, str) and ast.startswith("?"):
        return bindings.get(ast, ast)
    if _is_ast(ast):
        return (ast[0], tuple(instantiate(a, bindings) for a in ast[1]))
    return ast


def to_json(ast):
    if _is_ast(ast):
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
