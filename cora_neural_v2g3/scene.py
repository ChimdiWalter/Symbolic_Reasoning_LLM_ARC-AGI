"""ncv2-g3 scene analysis: which input objects change in each demonstration, and how. Demonstrations only.

For every demonstration whose grid shape is unchanged, each native object of a view gets one FATE, by comparing its
cells with the output grid:
- unchanged: the output repeats the object's cells and colours;
- recoloured: every cell takes one new non-background colour;
- moved: the same colour pattern appears at a displacement (the nearest one, if several) on cells that changed;
- deleted: every cell becomes background and no displaced copy exists;
- other.

Objects with the same fate across demonstrations form a CHANGE GROUP, at two grains: by fate alone, and by fate plus
target colour (recolouring only). Groups only ORDER the search (joint.py). They never remove a candidate.

`selections` asks native CORA which objects each selector picks, by running `(rule SEL (delete))` and reading which
objects disappear. Selector semantics are therefore never re-implemented here.
"""
from dataclasses import dataclass, field

import numpy as np

from cora_neural_v2.rast import N
from cora_neural_v2g2 import grammar as G

MAX_MOVE_CELLS = 64
FATE_ACTIONS = {                                  # action kinds (cora_neural_v2 / v2g2 `kind` keys) that explain a fate
    "deleted": {"delete"},
    "recoloured": {"recolour", "recolour_ref", "recolour_map", "recolour_rel", "recolour_freq", "recolour_featmap", "paint"},
    "moved": {"move_vec", "move_rel", "move_rel2", "move_to", "geometry_shift", "bind"},
}


@dataclass(frozen=True)
class Obj:
    demo: int
    index: int
    cells: frozenset
    fate: str
    to_colour: int = None
    vector: tuple = None


@dataclass
class Scene:
    view: str
    objects: list                                  # per demonstration: [Obj]
    background: list                               # per demonstration
    groups: dict = field(default_factory=dict)     # group key -> per-demonstration frozenset of object indices


def native_objects(grid, view):
    from geocat_arc.object_reasoning.segmentation import background_for, segment
    from geocat_arc.object_reasoning.types import SegmentationVariant as SV
    from geocat_arc.perception.grid import Grid
    g = Grid(np.asarray(grid, dtype=np.int32))
    bg = background_for(g, SV(view))
    return segment(g, SV(view), bg), int(bg)


def _displacement(cells, A, B):
    """The nearest non-zero displacement at which B repeats the object's colour pattern on cells that changed."""
    if len(cells) > MAX_MOVE_CELLS:
        return None
    h, w = B.shape
    (r0, c0), k = cells[0], int(A[cells[0]])
    best = None
    for r, c in zip(*np.nonzero(B == k)):
        d = (int(r - r0), int(c - c0))
        if d == (0, 0) or (best is not None and abs(d[0]) + abs(d[1]) >= abs(best[0]) + abs(best[1])):
            continue
        dest = [(rr + d[0], cc + d[1]) for rr, cc in cells]
        if all(0 <= rr < h and 0 <= cc < w for rr, cc in dest) and \
                all(B[x] == A[y] for x, y in zip(dest, cells)) and any(A[x] != B[x] for x in dest):
            best = d
    return best


def fate(o_cells, A, B, bg):
    cells = sorted(o_cells)
    src = [int(A[x]) for x in cells]
    out = [int(B[x]) for x in cells]
    if out == src:
        return "unchanged", None, None
    vals = set(out)
    if len(vals) == 1 and vals != {bg}:
        return "recoloured", next(iter(vals)), None
    d = _displacement(cells, A, B)
    if d is not None:
        return "moved", None, d
    if vals == {bg}:
        return "deleted", None, None
    return "other", None, None


def analyse(train, view="S1"):
    """The Scene of a view, or None when a demonstration changes the grid shape."""
    objs, bgs = [], []
    for i, (a, b) in enumerate(train):
        A, B = np.asarray(a), np.asarray(b)
        if A.shape != B.shape:
            return None
        native, bg = native_objects(A, view)
        objs.append([Obj(i, j, frozenset(o.cells), *fate(o.cells, A, B, bg)) for j, o in enumerate(native)])
        bgs.append(bg)
    sc = Scene(view, objs, bgs)
    for demo in objs:
        for o in demo:
            if o.fate == "unchanged":
                continue
            for key in ((o.fate,), (o.fate, o.to_colour)) if o.fate == "recoloured" else ((o.fate,),):
                sc.groups.setdefault(key, [set() for _ in objs])[o.demo].add(o.index)
    sc.groups = {k: [frozenset(s) for s in v] for k, v in sc.groups.items()}
    return sc


def selections(view, sels, train):
    """{selector: per-demonstration frozenset of the object indices it picks} (None for a demonstration it cannot run)."""
    out = {}
    natives = [native_objects(a, view) for a, _ in train]
    for s in sels:
        d = G.compile_program(N("program", (view, (N("rule", (s, N("delete", ()))),), "keep", N("same_as_input", ()))))
        picks = []
        for (a, _), (objs, bg) in zip(train, natives):
            res = G.run(d, a)
            if res is None:
                picks.append(None)
                continue
            A = np.asarray(a)
            picks.append(frozenset(j for j, o in enumerate(objs) if all(res[x] == bg != A[x] for x in o.cells)))
        out[s] = picks
    return out


def separation(picks, members):
    """(exact, f1) of a selector's picks against a group's members, pooled over demonstrations."""
    if any(p is None for p in picks):
        return False, 0.0
    tp = sum(len(p & m) for p, m in zip(picks, members))
    fp = sum(len(p - m) for p, m in zip(picks, members))
    fn = sum(len(m - p) for p, m in zip(picks, members))
    if tp == 0:
        return False, 0.0
    return fp == 0 and fn == 0, 2 * tp / (2 * tp + fp + fn)
