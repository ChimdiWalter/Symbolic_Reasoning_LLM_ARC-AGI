"""ncv2-g4 programs: an ncv2 object program (or the identity), then part and ray rules over the INPUT grid's native
objects of one view.

- `PartRule(sel, kind, colour)` writes `colour` on part `kind` (parts.py) of every object the selector picks.
- `RayRule(sel, dirs, stop, colour)` draws a ray in each direction from every cell of a picked object that has no
  object cell next to it in that direction. `stop="obstacle"` ends the ray before the first non-background INPUT cell;
  `stop="through"` runs to the grid edge, writing background cells only.
- `colour` is an int, or "own" (the picked object's colour).

Which objects a selector picks is decided by native CORA (cora_neural_v2g3.scene.selections), so selector semantics
are never re-implemented. The part and ray layer is NOT native: it writes cells itself. Where it overlaps native
(a `whole`-part recolour vs native `recolor`), the tests require identical outputs. Rules apply in order; a later
rule overwrites an earlier one on shared cells.
"""
import functools
from typing import NamedTuple

import numpy as np

from cora_neural_v2.rast import ASTError, N
from cora_neural_v2g3 import delta as D
from cora_neural_v2g3 import scene as SC
from cora_neural_v2g4 import parts as P

DIRS8 = ((0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (1, -1), (-1, 1), (-1, -1))


class PartRule(NamedTuple):
    sel: object
    kind: str
    colour: object


class RayRule(NamedTuple):
    sel: object
    dirs: tuple
    stop: str
    colour: object


class G4Program(NamedTuple):
    op: str                   # always "g4program", so that ncv2-g3's selection can read the family
    view: str
    base: object              # an ncv2 program AST, or None for the identity
    rules: tuple


def make(view, base, rules):
    return G4Program("g4program", view, base, tuple(rules))


def _key(grid):
    return tuple(tuple(int(v) for v in row) for row in np.asarray(grid))


@functools.lru_cache(maxsize=4096)
def _picks(view, sel, gkey):
    p = SC.selections(view, [sel], [(list(map(list, gkey)), None)])[sel][0]
    return p


@functools.lru_cache(maxsize=512)
def _objects(view, gkey):
    objs, bg = SC.native_objects(list(map(list, gkey)), view)
    return tuple(frozenset(o.cells) for o in objs), tuple(int(o.color) for o in objs), bg


def ray_cells(cells, dirs, stop, A, bg):
    cells = frozenset(cells)
    out = set()
    h, w = A.shape
    for dr, dc in dirs:
        for r, c in cells:
            if (r + dr, c + dc) in cells:
                continue
            rr, cc = r + dr, c + dc
            while 0 <= rr < h and 0 <= cc < w:
                if A[rr, cc] != bg:
                    if stop == "obstacle":
                        break
                else:
                    out.add((rr, cc))
                rr, cc = rr + dr, cc + dc
    return frozenset(out)


def rule_cells(rule, cells, A, bg):
    if isinstance(rule, PartRule):
        return P.part(cells, rule.kind, A, bg)
    return ray_cells(cells, rule.dirs, rule.stop, A, bg)


def execute(prog, grid):
    """The output grid, or None (no output, a shape change, or a selector native cannot evaluate)."""
    A = np.asarray(grid)
    out = A.copy() if prog.base is None else D.execute(prog.base, grid)
    if out is None or np.asarray(out).shape != A.shape:
        return None
    out = np.array(out)
    if not prog.rules:
        return out
    gkey = _key(A)
    cells, colours, bg = _objects(prog.view, gkey)
    for rule in prog.rules:
        picked = _picks(prog.view, rule.sel, gkey)
        if picked is None:
            return None
        for j in sorted(picked):
            colour = colours[j] if rule.colour == "own" else int(rule.colour)
            for x in rule_cells(rule, cells[j], A, bg):
                out[x] = colour
    return out


def deltas(prog, train, stop_early=False):
    """delta.DemoDelta per demonstration, as ncv2-g3 computes them, through the g4 executor."""
    out = []
    for a, b in train:
        A, B = np.asarray(a), np.asarray(b)
        try:
            res = execute(prog, a)
        except ASTError:
            raise
        except Exception:                                  # noqa: BLE001
            res = None
        if res is None or res.shape != B.shape:
            out.append(D.DemoDelta(False, B.shape, None if res is None else res.shape))
        else:
            wrong = res != B
            diff = A != B
            out.append(D.DemoDelta(True, B.shape, res.shape, wrong, diff & ~wrong, ~diff & wrong, diff & wrong))
        if stop_early and out[-1].n_wrong != 0:
            break
    return out


def fits(prog, train):
    return D.fits(deltas(prog, train, stop_early=True), len(train))
