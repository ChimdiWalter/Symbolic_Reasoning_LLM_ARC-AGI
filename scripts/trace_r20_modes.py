#!/usr/bin/env python3
"""R20 TRACE stage 2: FALSIFY candidate modes against ground truth.

Every candidate below was NAMED by a stage-1 trace (scripts/
trace_r20_structures.py + eyeballing the raw pairs) -- none is speculative.
Each is checked by EXACT reproduction of the pair's ground-truth
added-cell set (colour included), swept over four segmentation views.
Anything not reproduced exactly on EVERY train pair is a REJECT.

RAY family (candidate A, extension beyond objects)
  ray_until_obstacle  extrude the object's silhouette in a unit direction,
                      each lane stopping BEFORE the first non-background
                      cell (border otherwise).
  ray_paint_bg        extrude to the border but paint only background
                      cells (the ray passes UNDER other objects).
  ray_deflect         extrude in a unit direction; when a lane is blocked
                      by an obstacle, step sideways to the nearer free
                      side of that obstacle and continue.
  cross_center        4 rays from the object's bbox CENTRE row/column out
                      to the grid borders, painting background only.
  cavity_leak         fill the object's bbox cavity, then extrude a ray
                      out of each gap in the object's outline to the
                      border (width = the gap width).

CONNECT family (candidate B, inter-object connector)
  connect_full_overlap  the FULL rectangle spanning the projection overlap
                        between two facing objects (not the 1-wide centre
                        line growth.connect_segment already emits).
  connect_L             an L-shaped Manhattan path between two objects
                        whose projections do NOT overlap.
Both are swept over pair-selection rules: all facing pairs, nearest-only.
"""
from __future__ import annotations

import collections
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = os.environ.get(
    "ARC_PROJECT_ROOT",
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

RAY_EXEMPLARS = ["692cd3b6", "d56f2372", "41e4d17e", "9bebae7a",
                 "03560426", "3490cc26"]
CONNECT_EXEMPLARS = ["292dd178", "465b7d93", "321b1fc6", "896d5239",
                     "e74e1818", "2601afb7", "c87289bb", "6c434453",
                     "18419cfa"]
_UNIT = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}


# ---------------------------------------------------------------- helpers

def comps(cells, conn=4):
    offs = ((-1, 0), (1, 0), (0, -1), (0, 1)) if conn == 4 else tuple(
        (dr, dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1)
        if (dr, dc) != (0, 0))
    seen, out = set(), []
    for s in sorted(cells):
        if s in seen:
            continue
        st, comp = [s], set()
        seen.add(s)
        while st:
            p = st.pop()
            comp.add(p)
            for dr, dc in offs:
                q = (p[0] + dr, p[1] + dc)
                if q in cells and q not in seen:
                    seen.add(q)
                    st.append(q)
        out.append(comp)
    return out


def segment(grid, bg, view):
    """Return [(cells, colour_or_None)] under a segmentation view."""
    h, w = len(grid), len(grid[0])
    nonbg = {(r, c) for r in range(h) for c in range(w) if grid[r][c] != bg}
    objs = []
    if view in ("S1", "S2"):
        conn = 4 if view == "S1" else 8
        bycol = collections.defaultdict(set)
        for r, c in nonbg:
            bycol[grid[r][c]].add((r, c))
        for col, cc in bycol.items():
            for comp in comps(cc, conn):
                objs.append((comp, col))
    else:
        conn = 4 if view == "S3" else 8
        for comp in comps(nonbg, conn):
            cols = {grid[r][c] for r, c in comp}
            objs.append((comp, next(iter(cols)) if len(cols) == 1 else None))
    return objs


def bbox(cells):
    rs = [r for r, _ in cells]
    cs = [c for _, c in cells]
    return min(rs), max(rs), min(cs), max(cs)


# ------------------------------------------------------------ RAY family

def ray_until_obstacle(cells, direction, grid, bg, colour):
    """Silhouette extrusion stopping before the first non-bg cell."""
    dr, dc = _UNIT[direction]
    h, w = len(grid), len(grid[0])
    out = {}
    for r, c in cells:
        nr, nc = r + dr, c + dc
        while 0 <= nr < h and 0 <= nc < w:
            if (nr, nc) in cells or grid[nr][nc] != bg:
                break
            out[(nr, nc)] = colour
            nr, nc = nr + dr, nc + dc
    return out


def ray_paint_bg(cells, direction, grid, bg, colour):
    """Extrusion to the border painting ONLY background cells."""
    dr, dc = _UNIT[direction]
    h, w = len(grid), len(grid[0])
    out = {}
    for r, c in cells:
        nr, nc = r + dr, c + dc
        while 0 <= nr < h and 0 <= nc < w:
            if (nr, nc) not in cells and grid[nr][nc] == bg:
                out[(nr, nc)] = colour
            nr, nc = nr + dr, nc + dc
    return out


def ray_deflect(cells, direction, grid, bg, colour):
    """Extrude in `direction`; a lane blocked by an obstacle steps sideways
    along the obstacle's near face to the nearer free side and continues.
    Only defined for the axis directions; obstacles are non-bg components
    other than the source object."""
    dr, dc = _UNIT[direction]
    if dr and dc:
        return None
    h, w = len(grid), len(grid[0])
    obstacles = {(r, c) for r in range(h) for c in range(w)
                 if grid[r][c] != bg and (r, c) not in cells}
    obs_comps = comps(obstacles, 4)
    out = {}
    # leading edge of the object in `direction`
    lane_key = 1 if dr else 0          # lanes indexed by the OTHER axis
    lanes = {}
    for r, c in cells:
        k = (r, c)[lane_key]
        v = (r, c)[1 - lane_key]
        best = lanes.get(k)
        if best is None or (dr + dc) * v > (dr + dc) * best:
            lanes[k] = v
    frontier = []
    for k, v in lanes.items():
        frontier.append((k, v))
    guard = 0
    while frontier and guard < 4 * h * w:
        guard += 1
        k, v = frontier.pop()
        # step forward
        nv = v + (dr + dc)
        pos = (nv, k) if dr else (k, nv)
        if not (0 <= pos[0] < h and 0 <= pos[1] < w):
            continue
        if pos in cells:
            continue
        if grid[pos[0]][pos[1]] == bg:
            if pos not in out:
                out[pos] = colour
                frontier.append((k, nv))
            continue
        # blocked: find the obstacle component and its two side exits
        oc = next((o for o in obs_comps if pos in o), None)
        if oc is None:
            continue
        r0, r1, c0, c1 = bbox(oc)
        lo, hi = (c0, c1) if dr else (r0, r1)
        left_exit, right_exit = lo - 1, hi + 1
        dl, dr_ = k - left_exit, right_exit - k
        # strictly-nearer side wins; a TIE resolves to the POSITIVE lateral
        # direction (falsified on c87289bb pairs 2 and 3, both ties).
        order = ([left_exit, right_exit] if dl < dr_
                 else [right_exit, left_exit])
        exit_k = order[0]
        if not (0 <= exit_k < (w if dr else h)):
            exit_k = order[1]
            if not (0 <= exit_k < (w if dr else h)):
                continue
        step = 1 if exit_k > k else -1
        kk = k
        ok = True
        while kk != exit_k:
            kk += step
            p = (v, kk) if dr else (kk, v)
            if not (0 <= p[0] < h and 0 <= p[1] < w) or grid[p[0]][p[1]] != bg:
                ok = False
                break
            if p not in cells:
                out.setdefault(p, colour)
        if ok:
            frontier.append((exit_k, v))
    return out


def cross_center(cells, grid, bg, colour):
    """Full row+column through the object's bbox centre, painting bg only."""
    h, w = len(grid), len(grid[0])
    r0, r1, c0, c1 = bbox(cells)
    if (r1 - r0) % 2 or (c1 - c0) % 2:
        return None                       # centre not a single cell
    cr, cc = (r0 + r1) // 2, (c0 + c1) // 2
    out = {}
    for c in range(w):
        if (cr, c) not in cells and grid[cr][c] == bg:
            out[(cr, c)] = colour
    for r in range(h):
        if (r, cc) not in cells and grid[r][cc] == bg:
            out[(r, cc)] = colour
    return out


def cavity_leak(cells, grid, bg, colour):
    """Fill the object's bbox cavity, then extrude a ray out of every gap in
    the object's bbox outline until the grid border."""
    h, w = len(grid), len(grid[0])
    r0, r1, c0, c1 = bbox(cells)
    inner = {(r, c) for r in range(r0 + 1, r1) for c in range(c0 + 1, c1)
             if (r, c) not in cells}
    if not inner:
        return None
    out = {p: colour for p in inner}
    # gaps: outline positions of the bbox border not occupied by the object
    for c in range(c0, c1 + 1):
        if (r0, c) not in cells:
            for r in range(r0, -1, -1):
                if (r, c) in cells:
                    break
                out[(r, c)] = colour
        if (r1, c) not in cells:
            for r in range(r1, h):
                if (r, c) in cells:
                    break
                out[(r, c)] = colour
    for r in range(r0, r1 + 1):
        if (r, c0) not in cells:
            for c in range(c0, -1, -1):
                if (r, c) in cells:
                    break
                out[(r, c)] = colour
        if (r, c1) not in cells:
            for c in range(c1, w):
                if (r, c) in cells:
                    break
                out[(r, c)] = colour
    return out


# -------------------------------------------------------- CONNECT family

def facing(a, b):
    """(axis, lo, hi, olo, ohi) for two objects that face each other with a
    strict gap, else None.  axis 'h' = horizontal gap (columns between)."""
    ar0, ar1, ac0, ac1 = bbox(a)
    br0, br1, bc0, bc1 = bbox(b)
    ro0, ro1 = max(ar0, br0), min(ar1, br1)
    if ro0 <= ro1:
        if ac1 < bc0 - 1:
            return ("h", ac1 + 1, bc0 - 1, ro0, ro1)
        if bc1 < ac0 - 1:
            return ("h", bc1 + 1, ac0 - 1, ro0, ro1)
    co0, co1 = max(ac0, bc0), min(ac1, bc1)
    if co0 <= co1:
        if ar1 < br0 - 1:
            return ("v", ar1 + 1, br0 - 1, co0, co1)
        if br1 < ar0 - 1:
            return ("v", br1 + 1, ar0 - 1, co0, co1)
    return None


def connect_full_overlap(a, b, colour):
    """The FULL rectangle spanning the projection overlap of two facing
    objects (growth.connect_segment emits only its centre line)."""
    f = facing(a, b)
    if f is None:
        return None
    axis, lo, hi, olo, ohi = f
    if axis == "h":
        return {(r, c): colour for r in range(olo, ohi + 1)
                for c in range(lo, hi + 1)}
    return {(r, c): colour for c in range(olo, ohi + 1)
            for r in range(lo, hi + 1)}


def connect_L(a, b, colour, corner="row_first"):
    """L-shaped Manhattan path between the two objects' nearest cells."""
    if facing(a, b) is not None:
        return None
    pa, pb = min(
        ((p, q) for p in a for q in b),
        key=lambda t: (abs(t[0][0] - t[1][0]) + abs(t[0][1] - t[1][1]),
                       t[0], t[1]))
    out = {}
    if corner == "row_first":
        path = [(pa[0], c) for c in range(min(pa[1], pb[1]),
                                          max(pa[1], pb[1]) + 1)] + \
               [(r, pb[1]) for r in range(min(pa[0], pb[0]),
                                          max(pa[0], pb[0]) + 1)]
    else:
        path = [(r, pa[1]) for r in range(min(pa[0], pb[0]),
                                          max(pa[0], pb[0]) + 1)] + \
               [(pb[0], c) for c in range(min(pa[1], pb[1]),
                                          max(pa[1], pb[1]) + 1)]
    for p in path:
        if p not in a and p not in b:
            out[p] = colour
    return out or None


# ---------------------------------------------------------------- driver

def candidates_for_pair(grid, bg, added, view):
    """Yield (mode_name, reproduced_dict) for every candidate spelling."""
    objs = segment(grid, bg, view)
    if not objs:
        return
    colours = sorted({v for v in added.values()})
    colour = colours[0] if len(colours) == 1 else None
    obj_colours = sorted({c for _, c in objs if c is not None})
    # colour rules: the single observed colour (constant), or the source
    # object's own colour (relational).
    colour_rules = []
    if colour is not None:
        colour_rules.append(("const", lambda o, col=colour: col))
    colour_rules.append(("self", lambda o: o[1]))

    # ---- per-object ray modes, over object-subset selectors
    selectors = [("all", None)] + [(f"col{c}", c) for c in obj_colours]
    for cname, crule in colour_rules:
        for sname, sel in selectors:
            sub = [o for o in objs if sel is None or o[1] == sel]
            if not sub:
                continue
            for direction in ("up", "down", "left", "right"):
                for fn, mname in ((ray_until_obstacle, "ray_until_obstacle"),
                                  (ray_paint_bg, "ray_paint_bg"),
                                  (ray_deflect, "ray_deflect")):
                    acc = {}
                    ok = True
                    for o in sub:
                        col = crule(o)
                        if col is None:
                            ok = False
                            break
                        r = fn(o[0], direction, grid, bg, col)
                        if r is None:
                            ok = False
                            break
                        acc.update(r)
                    if ok and acc:
                        yield (f"{mname}:{direction}:{cname}:{sname}", acc)
            for fn, mname in ((cross_center, "cross_center"),
                              (cavity_leak, "cavity_leak")):
                acc = {}
                ok = True
                for o in sub:
                    col = crule(o)
                    if col is None:
                        ok = False
                        break
                    r = fn(o[0], grid, bg, col)
                    if r is None:
                        ok = False
                        break
                    acc.update(r)
                if ok and acc:
                    yield (f"{mname}:{cname}:{sname}", acc)

    # ---- pairwise connector modes
    if colour is None:
        return
    for sname, sel in selectors:
        sub = [o for o in objs if sel is None or o[1] == sel]
        if len(sub) < 2:
            continue
        n = len(sub)
        pairs = [(i, j) for i in range(n) for j in range(i + 1, n)]
        for pair_rule in ("all", "nearest"):
            if pair_rule == "nearest":
                chosen = []
                for i in range(n):
                    cand = [(min(abs(p[0] - q[0]) + abs(p[1] - q[1])
                                 for p in sub[i][0] for q in sub[j][0]), j)
                            for j in range(n) if j != i]
                    if cand:
                        chosen.append(tuple(sorted((i, min(cand)[1]))))
                use = sorted(set(chosen))
            else:
                use = pairs
            for mname, fn in (("connect_full_overlap", connect_full_overlap),
                              ("connect_L_rowfirst",
                               lambda a, b, c: connect_L(a, b, c,
                                                         "row_first")),
                              ("connect_L_colfirst",
                               lambda a, b, c: connect_L(a, b, c,
                                                         "col_first"))):
                acc = {}
                for i, j in use:
                    r = fn(sub[i][0], sub[j][0], colour)
                    if r:
                        acc.update(r)
                if acc:
                    yield (f"{mname}:{pair_rule}:{sname}", acc)


def run(which="all"):
    chal = json.load(open(Path(PROJECT_ROOT) /
                          "data/arc/arc-agi_training_challenges.json"))
    ids = []
    if which in ("all", "ray"):
        ids += RAY_EXEMPLARS
    if which in ("all", "connect"):
        ids += CONNECT_EXEMPLARS
    report = []
    for tid in ids:
        pairs = chal[tid]["train"]
        best = {}
        for view in ("S1", "S2", "S3", "S4"):
            # a mode QUALIFIES only if it reproduces the added set exactly
            # on EVERY pair of the task (fold-safety by construction).
            per_pair = []
            skip = False
            for q in pairs:
                gi, go = q["input"], q["output"]
                if len(gi) != len(go) or len(gi[0]) != len(go[0]):
                    skip = True
                    break
                flat = [v for row in gi for v in row]
                bg = collections.Counter(flat).most_common(1)[0][0]
                added = {(r, c): go[r][c]
                         for r in range(len(gi)) for c in range(len(gi[0]))
                         if gi[r][c] != go[r][c] and gi[r][c] == bg}
                if not added:
                    per_pair.append(set())
                    continue
                hits = set()
                for name, repro in candidates_for_pair(gi, bg, added, view):
                    if repro == added:
                        hits.add(name)
                per_pair.append(hits)
            if skip:
                best[view] = "SHAPE_CHANGE"
                continue
            common = set.intersection(*per_pair) if per_pair and all(
                per_pair) else set()
            best[view] = sorted(common)
        allhits = sorted({m for v in best.values()
                          if isinstance(v, list) for m in v})
        status = "EXPLAINED" if allhits else "reject"
        print(f"{tid:>10} {status:<10} {allhits if allhits else ''}")
        if not allhits:
            for v, r in best.items():
                if r == "SHAPE_CHANGE":
                    print(f"           {v}: SHAPE CHANGE (crop task)")
                    break
        report.append({"task_id": tid, "per_view": best,
                       "explained_by": allhits})
    outp = Path(PROJECT_ROOT) / "outputs/r20_trace/mode_falsification.json"
    outp.parent.mkdir(parents=True, exist_ok=True)
    json.dump(report, open(outp, "w"), indent=1)
    print(f"\nwrote {outp}")


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "all")
