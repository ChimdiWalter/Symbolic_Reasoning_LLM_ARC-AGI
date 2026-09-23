"""Symmetry completion: detect partial symmetry, fill missing cells.

From the deep analysis (11852cab): a pattern has N-fold symmetry with
some cells missing; the output fills those cells with the color dictated
by the symmetric counterpart.  Generic, fold-invariant, LOO-certifiable.

Symmetry types detected (in order of simplicity):
  - horizontal reflection (across vertical center axis)
  - vertical reflection (across horizontal center axis)
  - 4-fold (both reflections simultaneously)
  - 180-degree rotation (point symmetry around center)

For each symmetry type, the detector:
  1. Finds the non-background cells in the input
  2. Computes the symmetry center (centroid of all non-bg cells)
  3. For each non-bg cell, checks if its symmetric counterpart is also
     non-bg; if not, the counterpart is a "missing" cell
  4. The program fills every missing cell with the color of its symmetric
     source — zero-conflict if the color is consistent across all pairs

Packaged as a ReductionProgram (split={"kind":"symmetry"}) for the
ranking/rendering/certification surface.
"""
from __future__ import annotations
from typing import Optional
from geocat_arc.perception.grid import Grid

BG = 0


def _nonbg_cells(grid_list):
    return {(r, c): grid_list[r][c]
            for r in range(len(grid_list))
            for c in range(len(grid_list[0]))
            if grid_list[r][c] != BG}


def _center(cells):
    if not cells:
        return (0, 0)
    rs = [r for r, _ in cells]
    cs = [c for _, c in cells]
    return ((min(rs) + max(rs)) / 2, (min(cs) + max(cs)) / 2)


def _best_center(cells, sym_fn, multi):
    """The symmetry center that maximizes color-consistent symmetric
    pairs with ZERO conflicts (a counterpart present with a different
    color kills the candidate).  Searched over half-integer centers within
    the bbox; deterministic tiebreak (score desc, then center asc).  Falls
    back to the bbox center when nothing scores."""
    if not cells or len(cells) > 60:
        # cost guard (round-12 budget-wall lesson): symmetry-completion
        # patterns are small; big scenes must not pay the center search
        return _center(cells) if cells else (0, 0)
    rs = sorted({r for r, _ in cells})
    cs = sorted({c for _, c in cells})
    bcr, bcc = _center(cells)
    # centers lie near the bbox center for real patterns: +-2 cells
    cand_rs = sorted({x / 2 for x in range(int(2 * (bcr - 2)),
                                           int(2 * (bcr + 2)) + 1)})
    cand_cs = sorted({x / 2 for x in range(int(2 * (bcc - 2)),
                                           int(2 * (bcc + 2)) + 1)})
    best = None
    for cr in cand_rs:
        for cc in cand_cs:
            score = 0
            ok = True
            for (r, c), color in cells.items():
                targets = sym_fn(r, c, cr, cc) if multi \
                    else [sym_fn(r, c, cr, cc)]
                for (sr, sc) in targets:
                    if (sr, sc) == (r, c):
                        continue            # self-maps carry no evidence
                    got = cells.get((sr, sc))
                    if got == color:
                        score += 1
                    elif got is not None:
                        ok = False
                        break
                if not ok:
                    break
            if ok and score > 0:
                key = (-score, cr, cc)
                if best is None or key < best[0]:
                    best = (key, (cr, cc))
    return best[1] if best is not None else _center(cells)


def _sym_h(r, c, cr, cc):
    return (r, int(2 * cc - c))


def _sym_v(r, c, cr, cc):
    return (int(2 * cr - r), c)


def _sym_4(r, c, cr, cc):
    return [(r, int(2 * cc - c)),
            (int(2 * cr - r), c),
            (int(2 * cr - r), int(2 * cc - c))]


def _sym_rot180(r, c, cr, cc):
    return (int(2 * cr - r), int(2 * cc - c))


def _sym_rot90(r, c, cr, cc):
    """C4: images under 90/180/270-degree rotation about the center."""
    dr, dc = r - cr, c - cc
    return [(int(cr + dc), int(cc - dr)),      # 90
            (int(cr - dr), int(cc - dc)),      # 180
            (int(cr - dc), int(cc + dr))]      # 270


def _sym_d4(r, c, cr, cc):
    """Full dihedral group: reflections + rotations (7 images)."""
    out = set(_sym_4(r, c, cr, cc)) | set(_sym_rot90(r, c, cr, cc))
    out.discard((r, c))
    return sorted(out)


def _try_symmetry(pairs, sym_fn, multi=False):
    """Try one symmetry type across all train pairs.
    Returns the filled cells per pair if consistent, else None."""
    all_fills = []
    for gi, go in pairs:
        h, w = len(gi), len(gi[0])
        in_cells = _nonbg_cells(gi)
        out_cells = _nonbg_cells(go)
        cr, cc = _best_center(in_cells, sym_fn, multi)

        fills = {}
        for (r, c), color in in_cells.items():
            targets = sym_fn(r, c, cr, cc) if multi else [sym_fn(r, c, cr, cc)]
            for (sr, sc) in targets:
                if 0 <= sr < h and 0 <= sc < w and (sr, sc) not in in_cells:
                    if (sr, sc) in fills and fills[(sr, sc)] != color:
                        return None  # conflict
                    fills[(sr, sc)] = color

        # verify: input + fills == output (for non-bg cells)
        expected = dict(in_cells)
        expected.update(fills)
        if expected != out_cells:
            return None
        all_fills.append(fills)
    return all_fills


def induce_symmetry_completion(train_pairs) -> Optional[dict]:
    """Try symmetry completion across all train pairs.
    Returns program dict or None."""
    pairs = [(gi.to_list(), go.to_list()) for gi, go in train_pairs]
    if not all(len(gi) == len(go) and len(gi[0]) == len(go[0])
               for gi, go in pairs):
        return None
    # cost guard: this family is for small patterns; skip large scenes
    if any(len(_nonbg_cells(gi)) > 60 for gi, _ in pairs):
        return None

    for name, fn, multi in [
        ("d4", _sym_d4, True),
        ("4fold", _sym_4, True),
        ("rot90", _sym_rot90, True),
        ("horizontal", _sym_h, False),
        ("vertical", _sym_v, False),
        ("rot180", _sym_rot180, False),
    ]:
        result = _try_symmetry(pairs, fn, multi)
        if result is not None:
            return {"mode": "symmetry_completion", "symmetry": name}
    return None


def render_symmetry_completion(program: dict, input_grid: Grid) -> Grid:
    """Apply symmetry completion to one grid."""
    gi = input_grid.to_list()
    h, w = len(gi), len(gi[0])
    go = [row[:] for row in gi]
    in_cells = _nonbg_cells(gi)
    sym = program["symmetry"]

    fn_map = {
        "horizontal": (_sym_h, False),
        "vertical": (_sym_v, False),
        "rot180": (_sym_rot180, False),
        "4fold": (_sym_4, True),
        "rot90": (_sym_rot90, True),
        "d4": (_sym_d4, True),
    }
    fn, multi = fn_map[sym]
    cr, cc = _best_center(in_cells, fn, multi)

    for (r, c), color in in_cells.items():
        targets = fn(r, c, cr, cc) if multi else [fn(r, c, cr, cc)]
        for (sr, sc) in targets:
            if 0 <= sr < h and 0 <= sc < w and go[sr][sc] == BG:
                go[sr][sc] = color

    return Grid.from_list(go)
