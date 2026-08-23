"""Value kinds: what a runtime value STRUCTURALLY carries, by type.

The constructor inventory never asks "is this type Set[Region]?". It asks
"does this type carry cells?", "is it a collection?", "does it carry a
colour?". Those capabilities are declared here once, per atomic type of the
admitted universe, and verified against the frozen runtime by the unit tests
(a declared representation that the runtime does not actually produce fails
the test). Composite types get their capabilities structurally: Set[X] is a
collection of X, Expr[A,B] is a contextual expression.

Capabilities
    cells         the value is, or carries, a finite set of (row, col) cells
    colour        the value carries one colour of its own
    colour_field  the value assigns a colour to every cell it carries
    carrier       the value is a rectangular colour field with a shape
    scalar        the value is a plain comparable scalar
    collection    the value is a finite sequence of element values
    expr          a contextual expression, evaluated under an element/value
    vocab         a terminal drawn from a frozen finite vocabulary
    induced       a value supplied by a slot learner from demonstrations
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from level4_blind_runtime import runtime as V

#: Representation of each ATOMIC value type of the admitted universe. This is
#: the only table in the package that names a type, and it names every atomic
#: value type uniformly; nothing downstream consults it by name, only by the
#: capability sets it yields. Verified against the runtime in the tests.
ATOMIC_REPRESENTATION = {
    "Grid": frozenset({"carrier", "cells", "colour_field"}),
    "Region": frozenset({"cells"}),
    "Entity": frozenset({"cells"}),
    "Coloured": frozenset({"cells", "colour"}),
    "Colour": frozenset({"scalar", "colour"}),      # a colour carries itself
    "FeatureValue": frozenset({"scalar"}),
}

#: Frozen structural bound: collections nest at most one level, and only over
#: atomic value types. Keeps the instantiation closure finite and uniform.
MAX_SET_NESTING = 1


@dataclass(frozen=True)
class Kind:
    type: V.Type
    caps: frozenset
    element: Optional[V.Type] = None     # for collections

    def has(self, *caps) -> bool:
        return all(c in self.caps for c in caps)


def kind_of(t: V.Type, induced_types=(), vocab_types=()) -> Optional[Kind]:
    """Structural capabilities of a type, or None if it is not a value type
    the inventory can reason about (unknown atomic types are refused, not
    guessed)."""
    if t.name == "Set" and len(t.args) == 1:
        inner = t.args[0]
        if inner.name == "Set":
            return None                       # nesting bound
        ek = kind_of(inner, induced_types, vocab_types)
        if ek is None or not ek.caps or ek.has("collection"):
            return None
        if ek.has("expr") or ek.has("vocab") or ek.has("induced"):
            return None
        return Kind(t, frozenset({"collection"}), inner)
    if t.name == "Expr" and len(t.args) == 2:
        return Kind(t, frozenset({"expr"}))
    name = str(t)
    if name in ATOMIC_REPRESENTATION:
        return Kind(t, ATOMIC_REPRESENTATION[name])
    if name in vocab_types:
        return Kind(t, frozenset({"vocab"}))
    if name in induced_types:
        return Kind(t, frozenset({"induced"}))
    return None


# --------------------------------------------------------------------------
# uniform accessors: every constructor touches values ONLY through these
# --------------------------------------------------------------------------

def cells_of(value, kind: Kind):
    """The cell set a value carries (None if undefined)."""
    if kind.has("carrier"):
        h, w = value.shape
        return frozenset((r, c) for r in range(h) for c in range(w))
    if kind.has("colour"):
        return frozenset(value[0])
    if kind.has("cells"):
        return frozenset(value)
    return None


def coloured_cells(value, kind: Kind, context: np.ndarray):
    """Sorted (cell, colour) pairs: the colours a value assigns its cells.

    A value without a colour of its own is coloured by the context grid at
    its cells (the design's "the colours the input assigns those cells").
    """
    if kind.has("carrier"):
        h, w = value.shape
        return tuple(((r, c), int(value[r, c]))
                     for r in range(h) for c in range(w))
    if kind.has("colour"):
        cells, colour = value
        return tuple((cell, int(colour)) for cell in sorted(cells))
    if kind.has("cells"):
        h, w = context.shape
        out = []
        for r, c in sorted(value):
            if 0 <= r < h and 0 <= c < w:
                out.append(((r, c), int(context[r, c])))
        return tuple(out)
    return None


def derived_caps(kind: Kind, element_kind: Optional[Kind]) -> frozenset:
    """Capabilities including ``elem:<cap>`` for a collection's elements."""
    caps = set(kind.caps)
    if element_kind is not None:
        caps |= {f"elem:{c}" for c in element_kind.caps}
    return frozenset(caps)


def satisfies(caps: frozenset, requirement) -> bool:
    """``requirement`` is a tuple of alternatives; each alternative is a set
    of tokens: a plain capability that must be present, or ``only:a,b`` which
    demands the capability set be EXACTLY {a, b}."""
    for alternative in requirement:
        ok = True
        for token in alternative:
            if token.startswith("only:"):
                exact = frozenset(token[5:].split(","))
                if frozenset(c for c in caps if not c.startswith("elem:")) != exact:
                    ok = False
            elif token not in caps:
                ok = False
        if ok:
            return True
    return False


def own_colour(value, kind: Kind, context: np.ndarray):
    """The single colour a value carries; None if it has none or several."""
    if kind.has("scalar") and kind.has("colour"):
        return int(value)
    if kind.has("colour"):
        return int(value[1])
    pairs = coloured_cells(value, kind, context)
    if not pairs:
        return None
    colours = {colour for _, colour in pairs}
    return colours.pop() if len(colours) == 1 else None


def rebuild(kind: Kind, pairs, fill=None):
    """A value of ``kind`` from (cell, colour) pairs.

    carrier      the tight extent of the cells, origin-normalised, filled
                 with ``fill`` where no pair lands (fill None -> undefined)
    colour       cells plus their one shared colour (several -> undefined)
    cells        the cell set
    """
    if not pairs:
        return None
    cells = [cell for cell, _ in pairs]
    if kind.has("carrier"):
        if fill is None:
            return None
        r0 = min(r for r, _ in cells)
        c0 = min(c for _, c in cells)
        h = max(r for r, _ in cells) - r0 + 1
        w = max(c for _, c in cells) - c0 + 1
        out = np.full((h, w), int(fill), dtype=int)
        for (r, c), colour in pairs:
            out[r - r0, c - c0] = int(colour)
        return out
    if kind.has("colour"):
        colours = {colour for _, colour in pairs}
        if len(colours) != 1:
            return None
        return (frozenset(cells), colours.pop())
    if kind.has("cells"):
        return frozenset(cells)
    return None


def descriptors_of(value, kind: Kind, context: np.ndarray):
    """The frozen descriptor table of a cell-bearing value (None if empty)."""
    cells = cells_of(value, kind)
    if not cells:
        return None
    h, w = context.shape
    inside = {(r, c) for r, c in cells if 0 <= r < h and 0 <= c < w}
    if not inside:
        return None
    return V.descriptors(inside, context)


def descriptor_of(value, kind: Kind, context: np.ndarray, feature: str):
    """A feature of a cell-bearing value under the frozen descriptor table."""
    table = descriptors_of(value, kind, context)
    return None if table is None else table.get(feature)


def extent_cells(value, kind: Kind):
    """The bounding-box cell set of a cell-bearing value."""
    cells = cells_of(value, kind)
    if not cells:
        return None
    r0 = min(r for r, _ in cells)
    c0 = min(c for _, c in cells)
    r1 = max(r for r, _ in cells)
    c1 = max(c for _, c in cells)
    return frozenset((r, c) for r in range(r0, r1 + 1) for c in range(c0, c1 + 1))


def elements(value, kind: Kind):
    """The element sequence of a collection value."""
    if not kind.has("collection"):
        return None
    return tuple(value)


def collection(kind: Kind, items):
    """A collection value of ``kind`` (empty -> undefined, as in the runtime)."""
    items = tuple(x for x in items if x is not None)
    return items or None


def as_canonical(value):
    """Deterministic, hashable, JSON-able image of any runtime value."""
    if value is None:
        return None
    if isinstance(value, np.ndarray):
        return {"grid": [[int(x) for x in row] for row in value.tolist()]}
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, float):
        return float(value)
    if isinstance(value, str):
        return value
    if isinstance(value, frozenset):
        return {"cells": sorted([int(r), int(c)] for r, c in value)}
    if isinstance(value, (tuple, list)):
        return [as_canonical(v) for v in value]
    if isinstance(value, dict):
        return {str(k): as_canonical(v) for k, v in sorted(value.items())}
    return repr(value)
