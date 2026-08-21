#!/usr/bin/env python3
"""R22 TRACE: stage 1 + stage 2 for v22 census ray/line extension exemplars.

Stage 1: What are the missing cells? Raw ground-truth changed-cell components,
  their geometry, which input objects they touch, whether they reach the border.
Stage 2: Falsify each candidate mode by EXACT reproduction of the added-cell
  set, colour included, on EVERY train pair, swept over segmentation views.

Template: scripts/trace_r20_modes.py.

Census exemplars (extension_beyond_objects):
  0a938d79, 0e671a1a, 0f63c0b9, 32e9702f, 692cd3b6 (already R20-rejected),
  992798f6, a2fd1cf0, d22278a0, d4a91cb9, e45ef808, e7639916.
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

# All v22 census ray-class exemplars (excluding 692cd3b6, already R20-rejected)
RAY_EXEMPLARS = [
    "0a938d79", "0e671a1a", "0f63c0b9", "32e9702f",
    "992798f6", "a2fd1cf0", "d22278a0", "d4a91cb9",
    "e45ef808", "e7639916",
]

_UNIT = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}
VIEWS = ("S1", "S2", "S3", "S5", "S6", "S7")


# ---------------------------------------------------------------- helpers

def comps(cells, conn=4):
    """Connected components of a cell set."""
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
                objs.append((frozenset(comp), col))
    elif view in ("S3", "S5"):
        conn = 4 if view == "S3" else 8
        for comp in comps(nonbg, conn):
            cols = {grid[r][c] for r, c in comp}
            objs.append((frozenset(comp), next(iter(cols)) if len(cols) == 1 else None))
    elif view in ("S6", "S7"):
        conn = 4 if view == "S6" else 8
        for comp in comps(nonbg, conn):
            cols = {grid[r][c] for r, c in comp}
            objs.append((frozenset(comp), next(iter(cols)) if len(cols) == 1 else None))
    return objs


def bbox(cells):
    rs = [r for r, _ in cells]
    cs = [c for _, c in cells]
    return min(rs), max(rs), min(cs), max(cs)


def grid_bg(grid):
    """Most common colour, ties -> lowest."""
    h, w = len(grid), len(grid[0])
    cnt = collections.Counter()
    for r in range(h):
        for c in range(w):
            cnt[grid[r][c]] += 1
    most = max(cnt.values())
    return min(c for c, n in cnt.items() if n == most)


def diff_grids(in_grid, out_grid):
    """Return dicts of added, removed, recoloured cells."""
    h, w = len(in_grid), len(in_grid[0])
    oh, ow = len(out_grid), len(out_grid[0])
    added, removed, recoloured = {}, {}, {}
    for r in range(max(h, oh)):
        for c in range(max(w, ow)):
            iv = in_grid[r][c] if r < h and c < w else 0
            ov = out_grid[r][c] if r < oh and c < ow else 0
            if iv == ov:
                continue
            bg_in = grid_bg(in_grid)
            if iv == bg_in and ov != bg_in:
                added[(r, c)] = ov
            elif iv != bg_in and ov == bg_in:
                removed[(r, c)] = iv
            else:
                recoloured[(r, c)] = (iv, ov)
    return added, removed, recoloured


# --------------------------------------------------------- RAY candidate modes

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


def ray_to_border(cells, direction, colour, bounds):
    """Plain ray from each edge cell of the object to the border."""
    dr, dc = _UNIT[direction]
    h, w = bounds
    out = {}
    for r, c in cells:
        nr, nc = r + dr, c + dc
        while 0 <= nr < h and 0 <= nc < w:
            if (nr, nc) not in cells:
                out[(nr, nc)] = colour
            nr, nc = nr + dr, nc + dc
    return out


def cross_center(cells, grid, bg, colour):
    """Full grid row/col through bbox centre, painting bg only."""
    r0, r1, c0, c1 = bbox(cells)
    h, w = len(grid), len(grid[0])
    if (r1 - r0) % 2 == 1 or (c1 - c0) % 2 == 1:
        return None  # even extent
    cr = (r0 + r1) // 2
    cc = (c0 + c1) // 2
    out = {}
    for c in range(w):
        if grid[cr][c] == bg and (cr, c) not in cells:
            out[(cr, c)] = colour
    for r in range(h):
        if grid[r][cc] == bg and (r, cc) not in cells:
            out[(r, cc)] = colour
    return out


def cavity_leak(cells, grid, bg, colour):
    """Fill interior + leak through gaps to border."""
    r0, r1, c0, c1 = bbox(cells)
    h, w = len(grid), len(grid[0])
    interior = set()
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            if (r, c) not in cells and grid[r][c] == bg:
                interior.add((r, c))
    # find gaps on the bbox boundary
    out = {}
    for r, c in interior:
        out[(r, c)] = colour
    # check each bbox edge for gaps and extrude rays
    for side in ["top", "bottom", "left", "right"]:
        if side == "top":
            for c in range(c0, c1 + 1):
                if (r0, c) not in cells:
                    rr = r0 - 1
                    while rr >= 0 and grid[rr][c] == bg:
                        out[(rr, c)] = colour
                        rr -= 1
        elif side == "bottom":
            for c in range(c0, c1 + 1):
                if (r1, c) not in cells:
                    rr = r1 + 1
                    while rr < h and grid[rr][c] == bg:
                        out[(rr, c)] = colour
                        rr += 1
        elif side == "left":
            for r in range(r0, r1 + 1):
                if (r, c0) not in cells:
                    cc = c0 - 1
                    while cc >= 0 and grid[r][cc] == bg:
                        out[(r, cc)] = colour
                        cc -= 1
        elif side == "right":
            for r in range(r0, r1 + 1):
                if (r, c1) not in cells:
                    cc = c1 + 1
                    while cc < w and grid[r][cc] == bg:
                        out[(r, cc)] = colour
                        cc += 1
    return out


def ray_deflect(cells, direction, grid, bg, colour):
    """Extrude in direction, deflecting around obstacles to nearer side.
    Tie -> positive lateral."""
    dr, dc = _UNIT[direction]
    if dr and dc:
        return None
    h, w = len(grid), len(grid[0])
    obstacles = {(r, c) for r in range(h) for c in range(w)
                 if grid[r][c] != bg and (r, c) not in cells}
    obs_comps = comps(obstacles, 4)
    out = {}
    lane_key = 1 if dr else 0
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
        oc = next((o for o in obs_comps if pos in o), None)
        if oc is None:
            continue
        rr0, rr1, cc0, cc1 = bbox(oc)
        lo, hi = (cc0, cc1) if dr else (rr0, rr1)
        left_exit, right_exit = lo - 1, hi + 1
        dl, dr_ = k - left_exit, right_exit - k
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
            if 0 <= p[0] < h and 0 <= p[1] < w:
                if grid[p[0]][p[1]] == bg and p not in cells:
                    out[p] = colour
            else:
                ok = False
                break
        if ok:
            frontier.append((exit_k, v))
    return out


def ray_until_same_color(cells, direction, grid, bg, obj_colour):
    """Extrude until hitting a cell of the SAME colour as the object."""
    if obj_colour is None:
        return None
    dr, dc = _UNIT[direction]
    h, w = len(grid), len(grid[0])
    out = {}
    for r, c in cells:
        nr, nc = r + dr, c + dc
        while 0 <= nr < h and 0 <= nc < w:
            if grid[nr][nc] == obj_colour and (nr, nc) not in cells:
                break
            if (nr, nc) not in cells and grid[nr][nc] == bg:
                out[(nr, nc)] = obj_colour
            nr, nc = nr + dr, nc + dc
    return out


def ray_between_objects(obj_a, obj_b, grid, bg, colour):
    """Ray from object A toward object B, stopping at B's edge."""
    # determine relative direction
    ar0, ar1, ac0, ac1 = bbox(obj_a)
    br0, br1, bc0, bc1 = bbox(obj_b)
    h, w = len(grid), len(grid[0])
    # Check projections
    out = {}
    # Try connecting via overlapping projection
    row_overlap = max(0, min(ar1, br1) - max(ar0, br0) + 1)
    col_overlap = max(0, min(ac1, bc1) - max(ac0, bc0) + 1)
    if col_overlap > 0:
        # vertical connection
        if br0 > ar1:  # B is below A
            for c in range(max(ac0, bc0), min(ac1, bc1) + 1):
                for r in range(ar1 + 1, br0):
                    if grid[r][c] == bg:
                        out[(r, c)] = colour
        elif ar0 > br1:  # A is below B
            for c in range(max(ac0, bc0), min(ac1, bc1) + 1):
                for r in range(br1 + 1, ar0):
                    if grid[r][c] == bg:
                        out[(r, c)] = colour
    if row_overlap > 0:
        # horizontal connection
        if bc0 > ac1:  # B is right of A
            for r in range(max(ar0, br0), min(ar1, br1) + 1):
                for c in range(ac1 + 1, bc0):
                    if grid[r][c] == bg:
                        out[(r, c)] = colour
        elif ac0 > bc1:  # A is right of B
            for r in range(max(ar0, br0), min(ar1, br1) + 1):
                for c in range(bc1 + 1, ac0):
                    if grid[r][c] == bg:
                        out[(r, c)] = colour
    return out


# --------------------------------------------------------- Stage 1: Structure

def stage1_pair(in_grid, out_grid, pair_idx, task_id):
    """Characterize the ground-truth changed cells."""
    bg = grid_bg(in_grid)
    added, removed, recoloured = diff_grids(in_grid, out_grid)
    h, w = len(in_grid), len(in_grid[0])

    info = {
        "pair": pair_idx,
        "grid_size": f"{h}x{w}",
        "bg": bg,
        "n_added": len(added),
        "n_removed": len(removed),
        "n_recoloured": len(recoloured),
    }

    if added:
        add_cells = set(added.keys())
        add_colours = set(added.values())
        info["added_colours"] = sorted(add_colours)
        # connected components of added cells
        add_comps = comps(add_cells, 4)
        info["added_components"] = len(add_comps)
        info["added_comp_sizes"] = sorted([len(c) for c in add_comps], reverse=True)

        # Geometry: do they form lines? rays from objects?
        # Check if added cells reach grid borders
        reaches_border = any(
            r == 0 or r == h - 1 or c == 0 or c == w - 1
            for r, c in add_cells
        )
        info["reaches_border"] = reaches_border

        # Check row/column spans
        rows_touched = {r for r, c in add_cells}
        cols_touched = {c for r, c in add_cells}
        info["rows_touched"] = len(rows_touched)
        info["cols_touched"] = len(cols_touched)

        # Check if any added component is linear (single row or column)
        linear_comps = []
        for comp in add_comps:
            rows_c = {r for r, c in comp}
            cols_c = {c for r, c in comp}
            if len(rows_c) == 1:
                linear_comps.append(("row", next(iter(rows_c)), len(comp)))
            elif len(cols_c) == 1:
                linear_comps.append(("col", next(iter(cols_c)), len(comp)))
        if linear_comps:
            info["linear_components"] = linear_comps

        # Which input objects do they touch/extend from?
        for view in ("S1", "S2", "S6"):
            objs = segment(in_grid, bg, view)
            touching = []
            for oi, (oc, ocol) in enumerate(objs):
                # Does any added cell touch this object?
                adj = set()
                for r, c in oc:
                    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        adj.add((r + dr, c + dc))
                overlap = adj & add_cells
                if overlap:
                    touching.append({
                        "obj_idx": oi,
                        "obj_size": len(oc),
                        "obj_colour": ocol,
                        "obj_bbox": bbox(oc),
                        "touching_count": len(overlap),
                    })
            if touching:
                info[f"touching_objects_{view}"] = touching

    if removed:
        info["removed_colours"] = sorted(set(removed.values()))
    if recoloured:
        info["recolour_pairs"] = sorted(set(recoloured.values()))

    return info


# --------------------------------------------------------- Stage 2: Falsify

def stage2_pair(in_grid, out_grid, pair_idx, all_pairs_data):
    """Try all candidate modes on this pair and report match quality."""
    bg = grid_bg(in_grid)
    added, removed, recoloured = diff_grids(in_grid, out_grid)
    h, w = len(in_grid), len(in_grid[0])
    bounds = (h, w)
    results = {}

    if not added:
        return {"pair": pair_idx, "n_added": 0, "note": "no added cells"}

    added_set = set(added.keys())
    added_with_color = added  # {(r,c): color}

    for view in VIEWS:
        objs = segment(in_grid, bg, view)
        if not objs:
            continue

        for oi, (ocells, ocol) in enumerate(objs):
            obj_key = f"{view}_obj{oi}_{len(ocells)}cells"

            # Try each mode
            for direction in ["up", "down", "left", "right"]:
                for colour_rule in ["const", "self"]:
                    for c_val in sorted(set(added.values())):
                        use_colour = c_val if colour_rule == "const" else (ocol if ocol is not None else c_val)

                        # ray_until_obstacle
                        try:
                            pred = ray_until_obstacle(ocells, direction, in_grid, bg, use_colour)
                            if pred:
                                hit = len(set(pred.keys()) & added_set)
                                miss = len(added_set - set(pred.keys()))
                                extra = len(set(pred.keys()) - added_set)
                                color_match = sum(1 for k in pred if k in added and pred[k] == added[k])
                                if hit > 0:
                                    k = f"ray_until_obstacle:{direction}:{colour_rule}:{c_val}:{obj_key}"
                                    results[k] = {"hit": hit, "miss": miss, "extra": extra,
                                                  "color_match": color_match, "total_added": len(added),
                                                  "exact": hit == len(added) and miss == 0 and extra == 0 and color_match == hit}
                        except Exception:
                            pass

                        # ray_paint_bg
                        try:
                            pred = ray_paint_bg(ocells, direction, in_grid, bg, use_colour)
                            if pred:
                                hit = len(set(pred.keys()) & added_set)
                                miss = len(added_set - set(pred.keys()))
                                extra = len(set(pred.keys()) - added_set)
                                color_match = sum(1 for k in pred if k in added and pred[k] == added[k])
                                if hit > 0:
                                    k = f"ray_paint_bg:{direction}:{colour_rule}:{c_val}:{obj_key}"
                                    results[k] = {"hit": hit, "miss": miss, "extra": extra,
                                                  "color_match": color_match, "total_added": len(added),
                                                  "exact": hit == len(added) and miss == 0 and extra == 0 and color_match == hit}
                        except Exception:
                            pass

                        # ray_to_border
                        try:
                            pred = ray_to_border(ocells, direction, use_colour, bounds)
                            if pred:
                                hit = len(set(pred.keys()) & added_set)
                                miss = len(added_set - set(pred.keys()))
                                extra = len(set(pred.keys()) - added_set)
                                color_match = sum(1 for k in pred if k in added and pred[k] == added[k])
                                if hit > 0:
                                    k = f"ray_to_border:{direction}:{colour_rule}:{c_val}:{obj_key}"
                                    results[k] = {"hit": hit, "miss": miss, "extra": extra,
                                                  "color_match": color_match, "total_added": len(added),
                                                  "exact": hit == len(added) and miss == 0 and extra == 0 and color_match == hit}
                        except Exception:
                            pass

                        # ray_deflect
                        try:
                            pred = ray_deflect(ocells, direction, in_grid, bg, use_colour)
                            if pred:
                                hit = len(set(pred.keys()) & added_set)
                                miss = len(added_set - set(pred.keys()))
                                extra = len(set(pred.keys()) - added_set)
                                color_match = sum(1 for k in pred if k in added and pred[k] == added[k])
                                if hit > 0:
                                    k = f"ray_deflect:{direction}:{colour_rule}:{c_val}:{obj_key}"
                                    results[k] = {"hit": hit, "miss": miss, "extra": extra,
                                                  "color_match": color_match, "total_added": len(added),
                                                  "exact": hit == len(added) and miss == 0 and extra == 0 and color_match == hit}
                        except Exception:
                            pass

                        # ray_until_same_color
                        try:
                            pred = ray_until_same_color(ocells, direction, in_grid, bg, ocol)
                            if pred:
                                hit = len(set(pred.keys()) & added_set)
                                miss = len(added_set - set(pred.keys()))
                                extra = len(set(pred.keys()) - added_set)
                                color_match = sum(1 for k in pred if k in added and pred[k] == added[k])
                                if hit > 0:
                                    k = f"ray_until_same:{direction}:{colour_rule}:{c_val}:{obj_key}"
                                    results[k] = {"hit": hit, "miss": miss, "extra": extra,
                                                  "color_match": color_match, "total_added": len(added),
                                                  "exact": hit == len(added) and miss == 0 and extra == 0 and color_match == hit}
                        except Exception:
                            pass

            # cross_center
            for c_val in sorted(set(added.values())):
                try:
                    pred = cross_center(ocells, in_grid, bg, c_val)
                    if pred:
                        hit = len(set(pred.keys()) & added_set)
                        miss = len(added_set - set(pred.keys()))
                        extra = len(set(pred.keys()) - added_set)
                        color_match = sum(1 for k in pred if k in added and pred[k] == added[k])
                        if hit > 0:
                            k = f"cross_center:{c_val}:{obj_key}"
                            results[k] = {"hit": hit, "miss": miss, "extra": extra,
                                          "color_match": color_match, "total_added": len(added),
                                          "exact": hit == len(added) and miss == 0 and extra == 0 and color_match == hit}
                except Exception:
                    pass

            # cavity_leak
            for c_val in sorted(set(added.values())):
                try:
                    pred = cavity_leak(ocells, in_grid, bg, c_val)
                    if pred:
                        hit = len(set(pred.keys()) & added_set)
                        miss = len(added_set - set(pred.keys()))
                        extra = len(set(pred.keys()) - added_set)
                        color_match = sum(1 for k in pred if k in added and pred[k] == added[k])
                        if hit > 0:
                            k = f"cavity_leak:{c_val}:{obj_key}"
                            results[k] = {"hit": hit, "miss": miss, "extra": extra,
                                          "color_match": color_match, "total_added": len(added),
                                          "exact": hit == len(added) and miss == 0 and extra == 0 and color_match == hit}
                except Exception:
                    pass

        # Inter-object: ray_between_objects (all pairs)
        for oi, (oa, oca) in enumerate(objs):
            for oj, (ob, ocb) in enumerate(objs):
                if oi >= oj:
                    continue
                for c_val in sorted(set(added.values())):
                    try:
                        pred = ray_between_objects(oa, ob, in_grid, bg, c_val)
                        if pred:
                            hit = len(set(pred.keys()) & added_set)
                            miss = len(added_set - set(pred.keys()))
                            extra = len(set(pred.keys()) - added_set)
                            color_match = sum(1 for k in pred if k in added and pred[k] == added[k])
                            if hit > 0:
                                k = f"connect:{c_val}:{view}_o{oi}+o{oj}"
                                results[k] = {"hit": hit, "miss": miss, "extra": extra,
                                              "color_match": color_match, "total_added": len(added),
                                              "exact": hit == len(added) and miss == 0 and extra == 0 and color_match == hit}
                    except Exception:
                        pass

    return {"pair": pair_idx, "n_added": len(added), "n_removed": len(removed),
            "n_recoloured": len(recoloured), "results": results}


# ----------------------------------------------------------------- main

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", nargs="*", default=RAY_EXEMPLARS)
    parser.add_argument("--out-dir", default=os.path.join(PROJECT_ROOT, "outputs", "r22_trace"))
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    # Load ARC data
    data_dir = os.path.join(PROJECT_ROOT, "data")
    with open(os.path.join(data_dir, "arc-agi_training_challenges.json")) as f:
        train_challenges = json.load(f)
    with open(os.path.join(data_dir, "arc-agi_evaluation_challenges.json")) as f:
        eval_challenges = json.load(f)

    all_results = {}

    for task_id in args.tasks:
        if task_id in train_challenges:
            task = train_challenges[task_id]
        elif task_id in eval_challenges:
            task = eval_challenges[task_id]
        else:
            print(f"  {task_id}: NOT FOUND")
            continue

        pairs = task["train"]
        print(f"\n{'='*60}")
        print(f"TASK {task_id} ({len(pairs)} train pairs)")
        print(f"{'='*60}")

        task_result = {"task_id": task_id, "n_pairs": len(pairs),
                       "stage1": [], "stage2": []}

        for pi, pair in enumerate(pairs):
            in_grid = pair["input"]
            out_grid = pair["output"]

            # Stage 1
            s1 = stage1_pair(in_grid, out_grid, pi, task_id)
            task_result["stage1"].append(s1)
            print(f"\n  Pair {pi}: {s1['grid_size']}, "
                  f"added={s1['n_added']}, removed={s1['n_removed']}, "
                  f"recoloured={s1['n_recoloured']}")
            if s1.get("added_colours"):
                print(f"    added colours: {s1['added_colours']}")
            if s1.get("reaches_border"):
                print(f"    reaches border: True")
            if s1.get("linear_components"):
                print(f"    linear components: {s1['linear_components']}")
            if s1.get("added_components"):
                print(f"    {s1['added_components']} components, sizes {s1['added_comp_sizes']}")

            # Stage 2
            s2 = stage2_pair(in_grid, out_grid, pi, pairs)
            task_result["stage2"].append(s2)
            if isinstance(s2.get("results"), dict):
                # Show best matches
                exact = {k: v for k, v in s2["results"].items() if v.get("exact")}
                if exact:
                    print(f"    EXACT MATCHES ({len(exact)}):")
                    for k, v in sorted(exact.items()):
                        print(f"      {k}: hit={v['hit']}/{v['total_added']}")
                else:
                    # Show top-3 by hit/total ratio
                    ranked = sorted(s2["results"].items(),
                                    key=lambda x: (x[1]["hit"] / max(1, x[1]["total_added"]),
                                                   -x[1]["extra"]),
                                    reverse=True)[:5]
                    if ranked:
                        print(f"    BEST PARTIAL (no exact):")
                        for k, v in ranked:
                            print(f"      {k}: {v['hit']}/{v['total_added']} hit, "
                                  f"{v['miss']} miss, {v['extra']} extra")

        # Cross-pair exact-match summary
        all_pair_exact = set()
        for pi in range(len(pairs)):
            s2 = task_result["stage2"][pi]
            if isinstance(s2.get("results"), dict):
                pair_exact = {k for k, v in s2["results"].items() if v.get("exact")}
                if pi == 0:
                    all_pair_exact = pair_exact
                else:
                    all_pair_exact &= pair_exact

        if all_pair_exact:
            print(f"\n  ALL-PAIR EXACT MATCHES:")
            for k in sorted(all_pair_exact):
                print(f"    {k}")
            task_result["verdict"] = "VERIFIED"
            task_result["verified_modes"] = sorted(all_pair_exact)
        else:
            # Check if any mode was exact on at least one pair
            any_exact = set()
            for pi in range(len(pairs)):
                s2 = task_result["stage2"][pi]
                if isinstance(s2.get("results"), dict):
                    any_exact |= {k for k, v in s2["results"].items() if v.get("exact")}
            if any_exact:
                print(f"\n  PARTIAL (exact on some pairs only): 1-PAIR COINCIDENCES")
                for k in sorted(any_exact)[:5]:
                    pairs_with = []
                    for pi in range(len(pairs)):
                        s2 = task_result["stage2"][pi]
                        if isinstance(s2.get("results"), dict) and k in s2["results"] and s2["results"][k].get("exact"):
                            pairs_with.append(pi)
                    print(f"    {k} (exact on pairs {pairs_with})")
                task_result["verdict"] = "PARTIAL_COINCIDENCE"
            else:
                print(f"\n  NO EXACT MATCH ON ANY PAIR")
                task_result["verdict"] = "REJECTED"

        all_results[task_id] = task_result

    # Summary
    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    verified = [tid for tid, r in all_results.items() if r.get("verdict") == "VERIFIED"]
    rejected = [tid for tid, r in all_results.items() if r.get("verdict") == "REJECTED"]
    partial = [tid for tid, r in all_results.items() if r.get("verdict") == "PARTIAL_COINCIDENCE"]
    print(f"  VERIFIED: {len(verified)} - {verified}")
    print(f"  PARTIAL_COINCIDENCE: {len(partial)} - {partial}")
    print(f"  REJECTED: {len(rejected)} - {rejected}")

    # Save
    with open(os.path.join(args.out_dir, "r22_trace_results.json"), "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\nSaved to {args.out_dir}/r22_trace_results.json")


if __name__ == "__main__":
    main()
