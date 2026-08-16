#!/usr/bin/env python3
"""R20 TRACE stage 1: what ARE the missing cells a function of?

Both R20 candidates (ray-extension, inter-object connector) are dominated
by tasks that fail at MATCHING or are VOCAB_BLOCKED, i.e. there is no
stored fold-program divergence to diff.  So stage 1 works from the raw
ground truth: the changed-cell set between train input and train output.

For every changed-cell connected component we record what it geometrically
IS (straight run / L-path / diagonal / rectangle / blob), where it starts
and stops (touching which input objects, the grid border, or a
non-background obstacle), and what colour it carries relative to the
objects it touches.  No mode is proposed here -- this stage only NAMES the
structure so stage 2 can falsify a candidate against it.
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
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

RAY_EXEMPLARS = ["692cd3b6", "d56f2372", "41e4d17e", "9bebae7a",
                 "03560426", "3490cc26"]
CONNECT_EXEMPLARS = ["292dd178", "465b7d93", "321b1fc6", "896d5239",
                     "e74e1818", "2601afb7", "c87289bb", "6c434453",
                     "18419cfa"]


def components(cells, conn=4):
    """4- or 8-connected components of a cell set."""
    if conn == 4:
        offs = ((-1, 0), (1, 0), (0, -1), (0, 1))
    else:
        offs = tuple((dr, dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1)
                     if (dr, dc) != (0, 0))
    seen = set()
    out = []
    for start in sorted(cells):
        if start in seen:
            continue
        stack = [start]
        seen.add(start)
        comp = set()
        while stack:
            p = stack.pop()
            comp.add(p)
            for dr, dc in offs:
                q = (p[0] + dr, p[1] + dc)
                if q in cells and q not in seen:
                    seen.add(q)
                    stack.append(q)
        out.append(comp)
    return out


def bbox(cells):
    rs = [r for r, _ in cells]
    cs = [c for _, c in cells]
    return min(rs), max(rs), min(cs), max(cs)


def shape_of(comp):
    """Name the component's geometry."""
    r0, r1, c0, c1 = bbox(comp)
    h, w = r1 - r0 + 1, c1 - c0 + 1
    n = len(comp)
    if h == 1 and w == 1:
        return "single"
    if h == 1 and n == w:
        return "hline"
    if w == 1 and n == h:
        return "vline"
    if n == h * w:
        return "rect"
    # L-path: 1-wide everywhere, exactly one turn.  Detect by counting
    # cells with degree 2 whose two neighbours are perpendicular.
    degs = {}
    corners = 0
    for p in comp:
        nb = [q for q in ((p[0] - 1, p[1]), (p[0] + 1, p[1]),
                          (p[0], p[1] - 1), (p[0], p[1] + 1)) if q in comp]
        degs[p] = len(nb)
        if len(nb) == 2:
            (a, b) = nb
            if a[0] != b[0] and a[1] != b[1]:
                corners += 1
    ends = sum(1 for d in degs.values() if d == 1)
    if max(degs.values()) <= 2 and ends == 2:
        if corners == 1:
            return "Lpath"
        if corners == 0:
            return "line"       # unreachable (covered above) but explicit
        return f"path_turns{corners}"
    # diagonal: every cell 8-connected chain, no 4-neighbours
    if all(d == 0 for d in degs.values()) and n > 1:
        return "diagonal"
    return "blob"


def analyse_task(tid, chal, verbose=True):
    from geocat_arc.perception.grid import Grid
    rec = {"task_id": tid, "pairs": []}
    for pi, q in enumerate(chal[tid]["train"]):
        gi = [list(r) for r in q["input"]]
        go = [list(r) for r in q["output"]]
        pinfo = {"pair": pi, "in_shape": [len(gi), len(gi[0])],
                 "out_shape": [len(go), len(go[0])]}
        if len(gi) != len(go) or len(gi[0]) != len(go[0]):
            pinfo["shape_change"] = True
            rec["pairs"].append(pinfo)
            continue
        h, w = len(gi), len(gi[0])
        flat = [v for row in gi for v in row]
        bg = collections.Counter(flat).most_common(1)[0][0]
        changed = {(r, c): (gi[r][c], go[r][c])
                   for r in range(h) for c in range(w)
                   if gi[r][c] != go[r][c]}
        added = {p: v[1] for p, v in changed.items() if v[0] == bg}
        removed = {p: v[0] for p, v in changed.items() if v[1] == bg}
        recol = {p: v for p, v in changed.items()
                 if v[0] != bg and v[1] != bg}
        pinfo.update(bg=bg, n_changed=len(changed), n_added=len(added),
                     n_removed=len(removed), n_recolour=len(recol))
        # input objects (same-colour 4-conn, non-bg)
        nonbg = {(r, c) for r in range(h) for c in range(w)
                 if gi[r][c] != bg}
        objs = []
        for comp in components(nonbg):
            cols = {gi[r][c] for r, c in comp}
            if len(cols) == 1:
                objs.append((comp, next(iter(cols))))
            else:
                # split by colour for the S1 view
                bycol = collections.defaultdict(set)
                for r, c in comp:
                    bycol[gi[r][c]].add((r, c))
                for col, cc in bycol.items():
                    for sub in components(cc):
                        objs.append((sub, col))
        pinfo["n_input_objects"] = len(objs)
        pinfo["input_object_colours"] = sorted(
            collections.Counter(col for _, col in objs).items())

        def touching(comp):
            hits = []
            for i, (ocells, col) in enumerate(objs):
                for p in comp:
                    if any((p[0] + dr, p[1] + dc) in ocells
                           for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1))):
                        hits.append((i, col))
                        break
            return hits

        comps = []
        for comp in components(set(added)):
            cols = sorted({added[p] for p in comp})
            t = touching(comp)
            r0, r1, c0, c1 = bbox(comp)
            at_border = (r0 == 0 or c0 == 0 or r1 == h - 1 or c1 == w - 1)
            comps.append({
                "size": len(comp), "shape": shape_of(comp),
                "colours": cols, "n_touch": len(t),
                "touch_colours": sorted({c for _, c in t}),
                "touches_border": at_border,
                "bbox": [r0, r1, c0, c1],
            })
        pinfo["added_components"] = comps
        pinfo["added_shape_hist"] = dict(collections.Counter(
            c["shape"] for c in comps))
        pinfo["added_touch_hist"] = dict(collections.Counter(
            c["n_touch"] for c in comps))
        rec["pairs"].append(pinfo)
    if verbose:
        print(f"\n=== {tid} ===")
        for p in rec["pairs"]:
            if p.get("shape_change"):
                print(f"  pair{p['pair']}: SHAPE CHANGE "
                      f"{p['in_shape']} -> {p['out_shape']}")
                continue
            print(f"  pair{p['pair']}: {p['in_shape']} bg={p['bg']} "
                  f"objs={p['n_input_objects']} "
                  f"added={p['n_added']} removed={p['n_removed']} "
                  f"recol={p['n_recolour']}")
            print(f"     shapes={p['added_shape_hist']} "
                  f"touch={p['added_touch_hist']}")
            for c in p["added_components"][:10]:
                print(f"       {c['shape']:>10} n={c['size']:<3} "
                      f"col={c['colours']} touch={c['n_touch']}"
                      f"{c['touch_colours']} border={c['touches_border']} "
                      f"bbox={c['bbox']}")
            if len(p["added_components"]) > 10:
                print(f"       ... {len(p['added_components']) - 10} more")
    return rec


def run(which="all"):
    chal = json.load(open(Path(PROJECT_ROOT) /
                          "data/arc/arc-agi_training_challenges.json"))
    ids = []
    if which in ("all", "ray"):
        ids += RAY_EXEMPLARS
    if which in ("all", "connect"):
        ids += CONNECT_EXEMPLARS
    out = [analyse_task(t, chal) for t in ids]
    outp = Path(PROJECT_ROOT) / "outputs/r20_trace/structures.json"
    outp.parent.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(outp, "w"), indent=1)
    print(f"\nwrote {outp}")


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "all")
