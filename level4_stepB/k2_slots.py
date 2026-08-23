"""Parameter meta-families of the K2 constructors, and their generic learners.

Design rule (K2.2): "parameters a constructor needs (an ordering, an
arrangement, a value rule) are not chosen by the schema: they become induced
slots fitted per task by the ordinary slot-learner machinery". So every
parameter here is either

    a TERMINAL from a finite frozen vocabulary, enumerated by search
    (SetOp, Extremum), or

    an INDUCED type with a finite frozen meta-family and ONE generic learner
    that fits it by consistency with the demonstrations (IndexMap, Frame,
    Colour).

Every learner locates its source value inside the AST BY CAPABILITY (the
outermost slot-free sub-term whose result carries cells), exactly as the
frozen feature-colour learner locates its source by type; no learner reads a
demonstration statistic to choose a meta-family member, it tries the members
in frozen order and keeps the first that is consistent with every pair.

Meta-families are GENERATED, not listed: the orthogonal 2x2 integer
matrices are enumerated from the orthogonality equations, so no matrix is
hand-picked.
"""
from __future__ import annotations

import itertools
from typing import Optional

import numpy as np

from level4_blind_runtime import runtime as V
from level4_blind_runtime.search import LearnedValue

from . import kinds as K

# --------------------------------------------------------------------------
# terminal vocabularies (finite, frozen, enumerated by search)
# --------------------------------------------------------------------------

TERMINALS = {
    "SetOp": ("union", "intersection"),        # associative set folds
    "Extremum": ("max", "min"),                # comparison folds
}


# --------------------------------------------------------------------------
# IndexMap: structure-preserving maps of the cell lattice
#   m(x) = k * A (x - o) + b      A orthogonal integer 2x2, k >= 1 dilation
#   o = (0,0) or the source's minimal cell, b a constant offset
# --------------------------------------------------------------------------

def orthogonal_matrices():
    """All 2x2 integer matrices with entries in {-1,0,1} whose rows are unit
    and orthogonal: the automorphism group of the square lattice. Generated
    from the equations, identity first."""
    found = []
    for a, b, c, d in itertools.product((-1, 0, 1), repeat=4):
        if a * a + b * b == 1 and c * c + d * d == 1 and a * c + b * d == 0:
            found.append((a, b, c, d))
    found.sort(key=lambda m: (m != (1, 0, 0, 1), m))
    return tuple(found)


MATRICES = orthogonal_matrices()
DILATIONS = (1, 2, 3)
ORIGIN_RULES = ("zero", "value_min")


def _origin(rule, pairs):
    if rule == "zero" or not pairs:
        return (0, 0)
    return (min(r for (r, _), _ in pairs), min(c for (_, c), _ in pairs))


def apply_index_map(index_map, pairs):
    """Image of (cell, colour) pairs; a dilation k sends a cell to a k x k
    block. Later pairs overwrite earlier ones on collision (deterministic:
    pairs are processed in the order given)."""
    (a, b, c, d), k, origin_rule, (br, bc) = index_map
    o_r, o_c = _origin(origin_rule, pairs)
    out = {}
    for (r, cc), colour in pairs:
        x, y = r - o_r, cc - o_c
        base_r = k * (a * x + b * y) + br
        base_c = k * (c * x + d * y) + bc
        for i in range(k):
            for j in range(k):
                out[(base_r + i, base_c + j)] = colour
    return tuple(sorted(out.items()))


def index_map_family():
    """The frozen meta-family without the offset (offset is fitted)."""
    for matrix in MATRICES:
        for k in DILATIONS:
            for origin in ORIGIN_RULES:
                yield matrix, k, origin


# --------------------------------------------------------------------------
# Frame: how a value is placed into a fresh carrier
#   carrier shape by SHAPE_RULE, cell x -> x - o + t, uncovered cells by FILL
# --------------------------------------------------------------------------

SHAPE_RULES = ("value_extent", "context_extent", "constant")
FILL_RULES = ("context_content", "context_background", "constant")


def _extent(pairs):
    rows = [r for (r, _), _ in pairs]
    cols = [c for (_, c), _ in pairs]
    return (max(rows) - min(rows) + 1, max(cols) - min(cols) + 1)


def apply_frame(frame, pairs, context):
    """Embed (cell, colour) pairs into a carrier described by ``frame``."""
    shape_rule, shape_param, origin_rule, (tr, tc), fill_rule, fill_param = frame
    if not pairs:
        return None
    if shape_rule == "value_extent":
        shape = _extent(pairs)
    elif shape_rule == "context_extent":
        shape = tuple(int(x) for x in context.shape)
    else:
        shape = tuple(shape_param)
    if fill_rule == "context_content":
        if shape != tuple(int(x) for x in context.shape):
            return None
        out = context.copy()
    elif fill_rule == "context_background":
        out = np.full(shape, V.background(context), dtype=int)
    else:
        out = np.full(shape, int(fill_param), dtype=int)
    o_r, o_c = _origin(origin_rule, pairs)
    h, w = shape
    for (r, c), colour in pairs:
        rr, cc = r - o_r + tr, c - o_c + tc
        if not (0 <= rr < h and 0 <= cc < w):
            return None
        out[rr, cc] = int(colour)
    return out


def frame_family():
    for shape_rule in SHAPE_RULES:
        for origin_rule in ORIGIN_RULES:
            for fill_rule in FILL_RULES:
                yield shape_rule, origin_rule, fill_rule


# --------------------------------------------------------------------------
# locating the source value of a slot, by capability
# --------------------------------------------------------------------------

def runtime_kind(t: V.Type) -> Optional[K.Kind]:
    return K.kind_of(t, tuple(V.INDUCED_TYPES), tuple(V.TERMINAL_VALUES))


def _carries_cells(kind: Optional[K.Kind]) -> bool:
    if kind is None:
        return False
    if kind.has("collection"):
        return _carries_cells(runtime_kind(kind.element))
    return kind.has("cells")


def cell_source(ast):
    """Outermost slot-free sub-AST whose result carries cells, plus its kind."""
    found = []

    def walk(node):
        if not V.is_ast(node) or found:
            return
        kind = runtime_kind(V.REGISTRY[node[0]].result_type)
        if _carries_cells(kind) and not V.free_slots(node):
            found.append((node, kind))
            return
        for arg in node[1]:
            walk(arg)

    walk(ast)
    return found[0] if found else (None, None)


def value_pairs(value, kind: K.Kind, context):
    """(cell, colour) pairs of a value or of every element of a collection."""
    if kind.has("collection"):
        ekind = runtime_kind(kind.element)
        merged = {}
        for element in K.elements(value, kind):
            pairs = K.coloured_cells(element, ekind, context)
            if pairs is None:
                return None
            merged.update(dict(pairs))
        return tuple(sorted(merged.items())) or None
    return K.coloured_cells(value, kind, context) or None


def _source_pairs_per_pair(ast, pairs):
    source, kind = cell_source(ast)
    if source is None:
        return None
    out = []
    for grid_in, grid_out in pairs:
        value = V._eval(source, V.Ctx(grid_in))
        if value is None:
            return None
        cell_pairs = value_pairs(value, kind, grid_in)
        if not cell_pairs:
            return None
        out.append((grid_in, grid_out, cell_pairs))
    return out


def _inside(grid, cell):
    r, c = cell
    return 0 <= r < grid.shape[0] and 0 <= c < grid.shape[1]


# --------------------------------------------------------------------------
# the three generic learners
# --------------------------------------------------------------------------

def learn_colour(ast, pairs, slot) -> Optional[LearnedValue]:
    """The one colour the demonstrations assign to the source's cells."""
    rows = _source_pairs_per_pair(ast, pairs)
    if rows is None:
        return None
    colours, observations = set(), 0
    for _, grid_out, cell_pairs in rows:
        for cell, _ in cell_pairs:
            if not _inside(grid_out, cell):
                return None
            colours.add(int(grid_out[cell]))
            observations += 1
    if len(colours) != 1:
        return None
    return LearnedValue(value=colours.pop(), support=len(rows),
                        observations=observations, fold_coverable=True, cost=1)


def _offset_candidates(first_pairs, grid_out, image_of):
    """Offsets that send the first source cell onto some output cell of its
    colour; ``image_of`` maps a source pair to its un-offset image pairs."""
    (cell, colour) = first_pairs[0]
    images = image_of(((cell, colour),))
    candidates = set()
    h, w = grid_out.shape
    for (ir, ic), _ in images:
        for r in range(h):
            for c in range(w):
                if int(grid_out[r, c]) == colour:
                    candidates.add((r - ir, c - ic))
    return sorted(candidates)


def _consistent_images(rows, mapper):
    """Every mapped cell lands inside its output and has its colour."""
    observations = 0
    for _, grid_out, cell_pairs in rows:
        images = mapper(cell_pairs)
        if not images:
            return None
        for cell, colour in images:
            if not _inside(grid_out, cell) or int(grid_out[cell]) != colour:
                return None
            observations += 1
    return observations


def learn_index_map(ast, pairs, slot) -> Optional[LearnedValue]:
    rows = _source_pairs_per_pair(ast, pairs)
    if rows is None:
        return None
    first_pairs, first_out = rows[0][2], rows[0][1]
    for matrix, k, origin in index_map_family():
        zero = (matrix, k, origin, (0, 0))
        # offsets are relative to the un-offset image of the first cell, so
        # the origin rule is applied to the WHOLE source, as at apply time
        o_r, o_c = _origin(origin, first_pairs)
        shifted = tuple((((r - o_r), (c - o_c)), col) for (r, c), col in first_pairs)
        for offset in _offset_candidates(
                shifted, first_out,
                lambda p, z=zero: apply_index_map((z[0], z[1], "zero", (0, 0)), p)):
            candidate = (matrix, k, origin, offset)
            observations = _consistent_images(
                rows, lambda p, m=candidate: apply_index_map(m, p))
            if observations is not None:
                return LearnedValue(value=candidate, support=len(rows),
                                    observations=observations,
                                    fold_coverable=True, cost=1)
    return None


def learn_frame(ast, pairs, slot) -> Optional[LearnedValue]:
    rows = _source_pairs_per_pair(ast, pairs)
    if rows is None:
        return None
    first_in, first_out, first_pairs = rows[0]
    out_shapes = {tuple(int(x) for x in grid_out.shape) for _, grid_out, _ in rows}
    for shape_rule, origin_rule, fill_rule in frame_family():
        shape_param = tuple(out_shapes)[0] if len(out_shapes) == 1 else None
        if shape_rule == "constant" and shape_param is None:
            continue
        o_r, o_c = _origin(origin_rule, first_pairs)
        shifted = tuple((((r - o_r), (c - o_c)), col) for (r, c), col in first_pairs)
        for offset in _offset_candidates(shifted, first_out, lambda p: p):
            fill_param = None
            if fill_rule == "constant":
                fill_param = _uncovered_colour(
                    rows, shape_rule, shape_param, origin_rule, offset)
                if fill_param is None:
                    continue
            frame = (shape_rule, shape_param, origin_rule, offset,
                     fill_rule, fill_param)
            observations, ok = 0, True
            for grid_in, grid_out, cell_pairs in rows:
                embedded = apply_frame(frame, cell_pairs, grid_in)
                if embedded is None or embedded.shape != grid_out.shape:
                    ok = False
                    break
                for (r, c), colour in cell_pairs:
                    rr, cc = r - _origin(origin_rule, cell_pairs)[0] + offset[0], \
                        c - _origin(origin_rule, cell_pairs)[1] + offset[1]
                    if int(grid_out[rr, cc]) != colour:
                        ok = False
                        break
                    observations += 1
                if not ok:
                    break
            if ok:
                return LearnedValue(value=frame, support=len(rows),
                                    observations=observations,
                                    fold_coverable=True, cost=1)
    return None


def _uncovered_colour(rows, shape_rule, shape_param, origin_rule, offset):
    """The single colour every demonstration gives the carrier cells the
    source does not cover; None if there are none or several."""
    colours = set()
    for grid_in, grid_out, cell_pairs in rows:
        if shape_rule == "value_extent":
            shape = _extent(cell_pairs)
        elif shape_rule == "context_extent":
            shape = tuple(int(x) for x in grid_in.shape)
        else:
            shape = shape_param
        if shape != tuple(int(x) for x in grid_out.shape):
            return None
        o_r, o_c = _origin(origin_rule, cell_pairs)
        covered = {(r - o_r + offset[0], c - o_c + offset[1])
                   for (r, c), _ in cell_pairs}
        for r in range(shape[0]):
            for c in range(shape[1]):
                if (r, c) not in covered:
                    colours.add(int(grid_out[r, c]))
    return colours.pop() if len(colours) == 1 else None


INDUCED = {
    "Colour": learn_colour,
    "IndexMap": learn_index_map,
    "Frame": learn_frame,
}
