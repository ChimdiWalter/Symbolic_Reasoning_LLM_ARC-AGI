#!/usr/bin/env python
"""expr_trace_v1.py -- TRACE-FIRST analysis for the expression-grammar round,
family #1: pattern|outside_vocabulary|extensional-pattern (111 tasks).

ANALYSIS ONLY. No engine imports. No LLMs. Deterministic.

Lockbox discipline: loads outputs/lockbox/manifest.json and inspects ONLY
tasks whose split == "experience". Promotion/lockbox members of the family
are COUNTED (ids only), never opened.

For each experience-split family task this script:
  1. loads ground-truth train pairs (data/arc-agi_training_challenges.json),
  2. computes the changed-cell set per pair (output != input),
  3. extracts the stored near-solve program's literal grow masks from
     outputs/unified_harness_v22/object/near_solve_parts/<task>.jsonl,
  4. runs a battery of deterministic FUNCTIONAL-FORM CHECKERS that ask:
     can the ground-truth changed-cell set (cells AND colors) on ALL train
     pairs be produced by a pattern that is a FUNCTION of object features?

Checkers (each must reproduce the changed-cell set EXACTLY on ALL pairs):
  INTERIOR_FILL  pattern = enclosed-hole cells of an object; fill color a
                 function of an object feature (intensional positions).
  HALO           pattern = ring at Chebyshev/Manhattan distance 1 around the
                 object; color a function of an object feature.
  TEMPLATE_COPY  pattern = the cell-pattern of another object in the SAME
                 input grid, stamped (translated) at the changed region.
  PERIODIC_REPAIR output is periodic/symmetric and every changed cell's value
                 is recoverable from its clean orbit in the input.
  REL_STAMP      pattern = fixed relative (dr,dc)->color stamp anchored at
                 the object, keyed by an object feature (color / shape /
                 (color,shape)); same key => same stamp across ALL objects
                 of ALL pairs, every changed cell attributed.

REL_STAMP passes are additionally graded for evidence:
  keys with >=2 occurrences (non-vacuous) and fold-coverage (every key seen
  in a pair also appears in some OTHER pair => LOO-reinduction could recover
  it). A pass with no repeated key is COINCIDENCE-RISK by construction.

Outputs: outputs/expr_round_trace/trace_results.jsonl (one row per task),
         outputs/expr_round_trace/trace_summary.json
"""
import json
import os
import sys
from collections import Counter, defaultdict

ROOT = "/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project"
FAMILY = "pattern|outside_vocabulary|extensional-pattern"
OUT_DIR = os.path.join(ROOT, "outputs/expr_round_trace")


# ---------------------------------------------------------------- utilities
def load_working_set():
    manifest = json.load(open(os.path.join(ROOT, "outputs/lockbox/manifest.json")))
    split = {r["task_id"]: r["split"] for r in manifest["tasks"]}
    fam = []
    for line in open(os.path.join(ROOT, "outputs/nearsolve_compiler/ns_dataset.jsonl")):
        r = json.loads(line)
        if r["cluster_key"] == FAMILY:
            fam.append(r["task_id"])
    exp = sorted(t for t in fam if split.get(t) == "experience")
    counts = Counter(split.get(t, "MISSING") for t in fam)
    return fam, exp, counts


def background(grid):
    c = Counter(v for row in grid for v in row)
    return 0 if 0 in c else c.most_common(1)[0][0]


def changed_cells(inp, out):
    return {(r, c): out[r][c]
            for r in range(len(inp)) for c in range(len(inp[0]))
            if inp[r][c] != out[r][c]}


def segment(grid, bg, mode):
    """mode: 'color4' same-color 4-conn; 'multi8' any-nonbg 8-conn."""
    H, W = len(grid), len(grid[0])
    seen = [[False] * W for _ in range(H)]
    objs = []
    if mode == "color4":
        nbrs = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    else:
        nbrs = [(dr, dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1)
                if (dr, dc) != (0, 0)]
    for r in range(H):
        for c in range(W):
            if seen[r][c] or grid[r][c] == bg:
                continue
            stack, comp = [(r, c)], []
            seen[r][c] = True
            while stack:
                y, x = stack.pop()
                comp.append((y, x))
                for dr, dc in nbrs:
                    ny, nx = y + dr, x + dc
                    if 0 <= ny < H and 0 <= nx < W and not seen[ny][nx] \
                            and grid[ny][nx] != bg:
                        if mode == "color4" and grid[ny][nx] != grid[r][c]:
                            continue
                        seen[ny][nx] = True
                        stack.append((ny, nx))
            objs.append(comp)
    return objs


def obj_features(grid, comp):
    rs = [p[0] for p in comp]
    cs = [p[1] for p in comp]
    r0, c0 = min(rs), min(cs)
    cells = frozenset((r - r0, c - c0) for r, c in comp)
    colors = Counter(grid[r][c] for r, c in comp)
    pattern = frozenset((r - r0, c - c0, grid[r][c]) for r, c in comp)
    return {
        "anchor": (r0, c0),
        "bbox": (r0, c0, max(rs), max(cs)),
        "h": max(rs) - r0 + 1, "w": max(cs) - c0 + 1,
        "area": len(comp),
        "color": colors.most_common(1)[0][0],
        "ncolors": len(colors),
        "shape": cells,           # normalized cell set (shape signature)
        "pattern": pattern,       # normalized cell+color set
        "cells": set(comp),
    }


def holes(grid, comp, bg):
    """Enclosed cells inside comp's bbox not reachable from bbox border
    without crossing comp (4-conn flood over non-comp cells)."""
    rs = [p[0] for p in comp]
    cs = [p[1] for p in comp]
    r0, r1, c0, c1 = min(rs), max(rs), min(cs), max(cs)
    compset = set(comp)
    outside = set()
    stack = []
    for r in range(r0, r1 + 1):
        for c in (c0, c1):
            if (r, c) not in compset:
                stack.append((r, c))
    for c in range(c0, c1 + 1):
        for r in (r0, r1):
            if (r, c) not in compset:
                stack.append((r, c))
    while stack:
        y, x = stack.pop()
        if (y, x) in outside or (y, x) in compset:
            continue
        outside.add((y, x))
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            ny, nx = y + dr, x + dc
            if r0 <= ny <= r1 and c0 <= nx <= c1 and (ny, nx) not in outside \
                    and (ny, nx) not in compset:
                stack.append((ny, nx))
    return {(r, c) for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)
            if (r, c) not in compset and (r, c) not in outside
            and grid[r][c] == bg}


def key_of(feat, kind):
    if kind == "color":
        return feat["color"]
    if kind == "shape":
        return feat["shape"]
    if kind == "color+shape":
        return (feat["color"], feat["shape"])
    if kind == "area":
        return feat["area"]
    if kind == "hw":
        return (feat["h"], feat["w"])
    raise ValueError(kind)


KEY_KINDS = ["color", "shape", "color+shape", "area", "hw"]


def fold_coverable(occ_by_pair):
    """occ_by_pair: key -> set(pair_idx). Every key in a pair must appear in
    some other pair for LOO reinduction to recover it."""
    for key, pairs in occ_by_pair.items():
        if len(pairs) == 1 and len(occ_by_pair) > 0:
            # key appears in exactly one pair; if that pair holds the only
            # occurrence(s), a fold holding that pair out cannot induce it
            return False
    return True


# ---------------------------------------------------------------- checkers
def check_rel_stamp(pairs, seg_mode, key_kind, anchor_kind="tl"):
    """pattern = f(key) as a relative stamp anchored at object top-left.
    Every changed cell attributed to its nearest object (Chebyshev)."""
    stamp = {}          # key -> frozenset((dr,dc,color))
    occ = Counter()     # key -> occurrences
    occ_pairs = defaultdict(set)
    for pi, (inp, out) in enumerate(pairs):
        bg = background(inp)
        ch = changed_cells(inp, out)
        objs = segment(inp, bg, seg_mode)
        if not objs:
            return {"pass": False, "why": "no objects"}
        feats = [obj_features(inp, o) for o in objs]
        # attribute changed cells to nearest object
        assign = defaultdict(dict)
        for (r, c), col in ch.items():
            best, bestd = None, None
            for i, f in enumerate(feats):
                d = min(max(abs(r - y), abs(c - x)) for y, x in f["cells"])
                if bestd is None or d < bestd or (d == bestd and best is not None
                                                  and feats[i]["area"] < feats[best]["area"]):
                    best, bestd = i, d
            assign[best][(r, c)] = col
        for i, f in enumerate(feats):
            if anchor_kind == "tl":
                ar, ac = f["anchor"]
            else:
                ar = (f["bbox"][0] + f["bbox"][2]) // 2
                ac = (f["bbox"][1] + f["bbox"][3]) // 2
            rel = frozenset((r - ar, c - ac, col)
                            for (r, c), col in assign.get(i, {}).items())
            k = key_of(f, key_kind)
            if k in stamp:
                if stamp[k] != rel:
                    return {"pass": False,
                            "why": f"key {str(k)[:40]} inconsistent (pair {pi})"}
            else:
                stamp[k] = rel
            occ[k] += 1
            occ_pairs[k].add(pi)
    repeated = sum(1 for k, n in occ.items() if n >= 2)
    fold_break = [k for k, ps in occ_pairs.items() if len(ps) == 1]
    # a key confined to one pair breaks the LOO fold holding that pair out,
    # UNLESS its stamp is empty and "unknown key => no-op" is the default
    fold_break_nonempty = [k for k in fold_break if stamp[k]]
    return {"pass": True,
            "n_keys": len(stamp),
            "keys_repeated": repeated,
            "fold_coverable": fold_coverable(occ_pairs),
            "fold_break_keys": len(fold_break),
            "fold_break_nonempty": len(fold_break_nonempty),
            "fold_coverable_with_noop_default": len(fold_break_nonempty) == 0,
            "vacuous": repeated == 0,
            "nonempty_stamps": sum(1 for s in stamp.values() if s)}


def induce_color_fn(items, pairs_idx):
    """items: list of (feature_dict_for_keys, color). Try each key kind;
    return first kind giving a consistent, fold-coverable function."""
    results = {}
    for kind in KEY_KINDS + ["holeshape", "n_holes", "hole_area", "rank_area"]:
        table = {}
        occ_pairs = defaultdict(set)
        ok = True
        for (featkeys, col), pi in zip(items, pairs_idx):
            k = featkeys.get(kind)
            if k is None:
                ok = False
                break
            if k in table and table[k] != col:
                ok = False
                break
            table[k] = col
            occ_pairs[k].add(pi)
        if ok and len(table) >= 1:
            repeated = sum(1 for k in occ_pairs if len(occ_pairs[k]) >= 2
                           or sum(1 for (fk, _), p in zip(items, pairs_idx)
                                  if fk.get(kind) == k) >= 2)
            results[kind] = {"n_keys": len(table),
                            "fold_coverable": fold_coverable(occ_pairs),
                            "repeated_keys": repeated}
    return results


def check_interior_fill(pairs, seg_mode):
    """changed cells == union of enclosed holes of (some) objects, each hole
    region filled with a single color; color a function of object features."""
    items, items_pairs = [], []
    for pi, (inp, out) in enumerate(pairs):
        bg = background(inp)
        ch = changed_cells(inp, out)
        if not ch:
            return {"pass": False, "why": "pair with no change"}
        objs = segment(inp, bg, seg_mode)
        feats = [obj_features(inp, o) for o in objs]
        covered = set()
        for o, f in zip(objs, feats):
            hs = holes(inp, o, bg)
            if not hs:
                continue
            hcells = {p for p in hs if p in ch}
            if not hcells:
                # object with holes but no fill: fill color fn must map it
                # to "no fill"; record as color None
                if any(p in ch for p in hs):
                    pass
                filled_col = None
            else:
                if hcells != hs:
                    return {"pass": False, "why": f"partial hole fill pair {pi}"}
                cols = {ch[p] for p in hs}
                if len(cols) != 1:
                    return {"pass": False, "why": f"multicolor hole pair {pi}"}
                filled_col = cols.pop()
                covered |= hs
            fk = {"color": f["color"], "shape": f["shape"],
                  "color+shape": (f["color"], f["shape"]),
                  "area": f["area"], "hw": (f["h"], f["w"]),
                  "holeshape": frozenset((r - f["anchor"][0], c - f["anchor"][1])
                                         for r, c in hs),
                  "n_holes": None, "hole_area": len(hs),
                  "rank_area": None}
            items.append((fk, filled_col))
            items_pairs.append(pi)
        if covered != set(ch):
            return {"pass": False,
                    "why": f"changed != hole union pair {pi} "
                           f"(extra {len(set(ch)-covered)}, "
                           f"missed {len(covered-set(ch))})"}
    fns = induce_color_fn(items, items_pairs)
    if not fns:
        return {"pass": False, "why": "no consistent color function"}
    return {"pass": True, "color_fn": {k: v for k, v in fns.items()},
            "n_fill_events": len(items)}


def check_halo(pairs, seg_mode, dist_kind):
    """changed == union of distance-1 rings (chebyshev/manhattan/corners)
    around every object, on background cells; ring color = f(object key)."""
    items, items_pairs = [], []
    for pi, (inp, out) in enumerate(pairs):
        bg = background(inp)
        ch = changed_cells(inp, out)
        H, W = len(inp), len(inp[0])
        objs = segment(inp, bg, seg_mode)
        feats = [obj_features(inp, o) for o in objs]
        covered = set()
        for f in feats:
            ring = set()
            for (y, x) in f["cells"]:
                if dist_kind == "chebyshev":
                    nb = [(y + dr, x + dc) for dr in (-1, 0, 1)
                          for dc in (-1, 0, 1)]
                elif dist_kind == "manhattan":
                    nb = [(y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)]
                else:  # corners
                    nb = [(y - 1, x - 1), (y - 1, x + 1),
                          (y + 1, x - 1), (y + 1, x + 1)]
                for ny, nx in nb:
                    if 0 <= ny < H and 0 <= nx < W and (ny, nx) not in f["cells"] \
                            and inp[ny][nx] == bg:
                        ring.add((ny, nx))
            ring_ch = {p for p in ring if p in ch}
            if not ring_ch:
                col = None
            else:
                if ring_ch != ring:
                    return {"pass": False, "why": f"partial ring pair {pi}"}
                cols = {ch[p] for p in ring}
                if len(cols) != 1:
                    return {"pass": False, "why": f"multicolor ring pair {pi}"}
                col = cols.pop()
                covered |= ring
            fk = {"color": f["color"], "shape": f["shape"],
                  "color+shape": (f["color"], f["shape"]),
                  "area": f["area"], "hw": (f["h"], f["w"]),
                  "holeshape": None, "n_holes": None, "hole_area": None,
                  "rank_area": None}
            items.append((fk, col))
            items_pairs.append(pi)
        if covered != set(changed_cells(inp, out)):
            return {"pass": False, "why": f"changed != ring union pair {pi}"}
    fns = induce_color_fn(items, items_pairs)
    if not fns:
        return {"pass": False, "why": "no consistent color function"}
    return {"pass": True, "color_fn": {k: v for k, v in fns.items()},
            "dist": dist_kind}


def check_bbox_outline(pairs, seg_mode, offset):
    """changed == union of rectangular rings around object bboxes (dilated by
    `offset`), drawn on background cells only; ring color = f(object key).
    Intensional positions: works for unseen shapes/sizes."""
    items, items_pairs = [], []
    for pi, (inp, out) in enumerate(pairs):
        bg = background(inp)
        ch = changed_cells(inp, out)
        H, W = len(inp), len(inp[0])
        objs = segment(inp, bg, seg_mode)
        feats = [obj_features(inp, o) for o in objs]
        covered = set()
        for f in feats:
            r0, c0, r1, c1 = f["bbox"]
            r0, c0, r1, c1 = r0 - offset, c0 - offset, r1 + offset, c1 + offset
            ring = set()
            for r in range(r0, r1 + 1):
                for c in (c0, c1):
                    if 0 <= r < H and 0 <= c < W and inp[r][c] == bg:
                        ring.add((r, c))
            for c in range(c0, c1 + 1):
                for r in (r0, r1):
                    if 0 <= r < H and 0 <= c < W and inp[r][c] == bg:
                        ring.add((r, c))
            ring -= f["cells"]
            ring_ch = {p for p in ring if p in ch}
            if not ring_ch:
                col = None
            else:
                if ring_ch != ring:
                    return {"pass": False, "why": f"partial ring pair {pi}"}
                cols = {ch[p] for p in ring}
                if len(cols) != 1:
                    return {"pass": False, "why": f"multicolor ring pair {pi}"}
                col = cols.pop()
                covered |= ring
            fk = {"color": f["color"], "shape": f["shape"],
                  "color+shape": (f["color"], f["shape"]),
                  "area": f["area"], "hw": (f["h"], f["w"]),
                  "holeshape": None, "n_holes": None, "hole_area": None,
                  "rank_area": None}
            items.append((fk, col))
            items_pairs.append(pi)
        if covered != set(ch):
            return {"pass": False, "why": f"changed != ring union pair {pi}"}
    fns = induce_color_fn(items, items_pairs)
    if not fns:
        return {"pass": False, "why": "no consistent color function"}
    return {"pass": True, "color_fn": {k: v for k, v in fns.items()},
            "offset": offset}


def check_template_copy(pairs, seg_mode):
    """every connected changed region equals (translated) the cell/color
    pattern of some object present in the SAME input grid."""
    n_regions = 0
    shape_only_needed = False
    for pi, (inp, out) in enumerate(pairs):
        bg = background(inp)
        ch = changed_cells(inp, out)
        if not ch:
            return {"pass": False, "why": "pair with no change"}
        objs = segment(inp, bg, seg_mode)
        feats = [obj_features(inp, o) for o in objs]
        # connected components of changed cells (8-conn)
        cells = set(ch)
        seen = set()
        for start in sorted(cells):
            if start in seen:
                continue
            stack, comp = [start], []
            seen.add(start)
            while stack:
                y, x = stack.pop()
                comp.append((y, x))
                for dr in (-1, 0, 1):
                    for dc in (-1, 0, 1):
                        p = (y + dr, x + dc)
                        if p in cells and p not in seen:
                            seen.add(p)
                            stack.append(p)
            n_regions += 1
            r0 = min(p[0] for p in comp)
            c0 = min(p[1] for p in comp)
            patt = frozenset((r - r0, c - c0, ch[(r, c)]) for r, c in comp)
            shape = frozenset((r - r0, c - c0) for r, c in comp)
            if any(f["pattern"] == patt for f in feats):
                continue
            if any(f["shape"] == shape for f in feats):
                shape_only_needed = True
                continue
            return {"pass": False,
                    "why": f"changed region pair {pi} matches no input object"}
    return {"pass": True, "n_regions": n_regions,
            "shape_only": shape_only_needed}


def _periodic(out, pr, pc):
    H, W = len(out), len(out[0])
    for r in range(H):
        for c in range(W):
            if out[r][c] != out[r % pr][c % pc]:
                return False
    return True


def check_periodic_repair(pairs):
    """output is periodic (or mirror-symmetric) and every changed cell's
    value is determined by the clean members of its orbit in the INPUT."""
    kinds = []
    for pi, (inp, out) in enumerate(pairs):
        H, W = len(out), len(out[0])
        ch = changed_cells(inp, out)
        if not ch:
            return {"pass": False, "why": "pair with no change"}
        found = None
        # periodicity
        for pr in range(1, H + 1):
            if found:
                break
            if H % pr and pr != H:
                pass
            for pc in range(1, W + 1):
                if (pr, pc) == (H, W):
                    continue
                if _periodic(out, pr, pc):
                    # orbit check from input
                    ok = True
                    for (r, c) in ch:
                        orbit = [(rr, cc) for rr in range(r % pr, H, pr)
                                 for cc in range(c % pc, W, pc)]
                        clean = [inp[rr][cc] for rr, cc in orbit
                                 if inp[rr][cc] == out[rr][cc]]
                        if not clean or any(v != out[r][c] for v in clean):
                            ok = False
                            break
                    if ok:
                        found = ("periodic", pr, pc)
                        break
        if not found:
            # mirror symmetries
            def sym_ok(mapfn):
                for (r, c) in ch:
                    seenv = []
                    rr, cc = mapfn(r, c)
                    if out[rr][cc] != out[r][c]:
                        return False
                    if inp[rr][cc] == out[rr][cc]:
                        seenv.append(inp[rr][cc])
                    if not seenv or any(v != out[r][c] for v in seenv):
                        return False
                return True
            for name, fn, cond in [
                    ("mirror_h", lambda r, c: (r, W - 1 - c), True),
                    ("mirror_v", lambda r, c: (H - 1 - r, c), True),
                    ("rot180", lambda r, c: (H - 1 - r, W - 1 - c), True),
                    ("transpose", lambda r, c: (c, r), H == W)]:
                if cond and all(out[fn(r, c)[0]][fn(r, c)[1]] == out[r][c]
                                for r in range(H) for c in range(W)) \
                        and sym_ok(fn):
                    found = (name,)
                    break
        if not found:
            return {"pass": False, "why": f"no derivable structure pair {pi}"}
        kinds.append(found)
    return {"pass": True, "kinds": [list(map(str, k)) for k in kinds]}


def _panel_partition(grid, bg):
    """Partition by full separator rows/cols (rows/cols entirely one non-bg
    color, the same color for all separators). Returns list of regions
    (set of cells) with (row_band, col_band) index, or None."""
    H, W = len(grid), len(grid[0])
    sep_colors = set()
    sep_rows, sep_cols = [], []
    for r in range(H):
        vals = set(grid[r])
        if len(vals) == 1 and grid[r][0] != bg:
            sep_rows.append(r)
            sep_colors.add(grid[r][0])
    for c in range(W):
        vals = {grid[r][c] for r in range(H)}
        if len(vals) == 1 and grid[0][c] != bg:
            sep_cols.append(c)
            sep_colors.add(grid[0][c])
    if len(sep_colors) != 1 or (not sep_rows and not sep_cols):
        return None
    row_bands, cur = [], []
    for r in range(H):
        if r in sep_rows:
            if cur:
                row_bands.append(cur)
            cur = []
        else:
            cur.append(r)
    if cur:
        row_bands.append(cur)
    col_bands, cur = [], []
    for c in range(W):
        if c in sep_cols:
            if cur:
                col_bands.append(cur)
            cur = []
        else:
            cur.append(c)
    if cur:
        col_bands.append(cur)
    regions = []
    for i, rb in enumerate(row_bands):
        for j, cb in enumerate(col_bands):
            regions.append(((i, j), {(r, c) for r in rb for c in cb}))
    return regions


def check_region_fill(pairs):
    """grid partitions into panels via separator lines; changed cells lie in
    panels; each touched panel's bg cells are filled with ONE color; color a
    function of panel index / row / col / content-derived features."""
    items, items_pairs = [], []
    for pi, (inp, out) in enumerate(pairs):
        bg = background(inp)
        regions = _panel_partition(inp, bg)
        if regions is None:
            return {"pass": False, "why": f"no panel partition pair {pi}"}
        ch = changed_cells(inp, out)
        covered = set()
        nrows = max(i for (i, j), _ in regions) + 1
        ncols = max(j for (i, j), _ in regions) + 1
        for (i, j), cells in regions:
            bgcells = {p for p in cells if inp[p[0]][p[1]] == bg}
            chc = {p for p in bgcells if p in ch}
            content = frozenset(
                (r - min(x[0] for x in cells), c - min(x[1] for x in cells),
                 inp[r][c]) for r, c in cells if inp[r][c] != bg)
            if not chc:
                col = None
            else:
                if chc != bgcells:
                    return {"pass": False,
                            "why": f"partial panel fill pair {pi} panel {(i,j)}"}
                cols = {ch[p] for p in chc}
                if len(cols) != 1:
                    return {"pass": False,
                            "why": f"multicolor panel pair {pi} panel {(i,j)}"}
                col = cols.pop()
                covered |= chc
            pos_class = (min(i, 1) + (1 if i == nrows - 1 else 0) * 2,
                         min(j, 1) + (1 if j == ncols - 1 else 0) * 2)
            fk = {"panel_index": (i, j), "panel_row": i, "panel_col": j,
                  "panel_pos_class": pos_class,
                  "panel_content": content,
                  "panel_has_content": bool(content)}
            items.append((fk, col))
            items_pairs.append(pi)
        if covered != set(ch):
            return {"pass": False, "why": f"changed != panel union pair {pi}"}
    # induce color fn over panel feature kinds
    results = {}
    for kind in ("panel_index", "panel_row", "panel_col",
                 "panel_pos_class", "panel_content", "panel_has_content"):
        table, occp, ok = {}, defaultdict(set), True
        for (fk, col), pi in zip(items, items_pairs):
            k = fk[kind]
            if k in table and table[k] != col:
                ok = False
                break
            table[k] = col
            occp[k].add(pi)
        if ok:
            results[kind] = {"n_keys": len(table),
                             "fold_coverable": fold_coverable(occp)}
    if not results:
        return {"pass": False, "why": "no consistent panel color function"}
    return {"pass": True, "color_fn": results}


def check_region_fill_connected(pairs):
    """regions = 4-connected components of background cells (walls = non-bg);
    changed cells fill whole regions uniformly; color = f(region feature:
    touches_border / area / bbox / rectangularity)."""
    items, items_pairs = [], []
    for pi, (inp, out) in enumerate(pairs):
        bg = background(inp)
        H, W = len(inp), len(inp[0])
        seen = [[False] * W for _ in range(H)]
        ch = changed_cells(inp, out)
        covered = set()
        for r0 in range(H):
            for c0 in range(W):
                if seen[r0][c0] or inp[r0][c0] != bg:
                    continue
                stack, comp = [(r0, c0)], []
                seen[r0][c0] = True
                while stack:
                    y, x = stack.pop()
                    comp.append((y, x))
                    for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                        ny, nx = y + dr, x + dc
                        if 0 <= ny < H and 0 <= nx < W and not seen[ny][nx] \
                                and inp[ny][nx] == bg:
                            seen[ny][nx] = True
                            stack.append((ny, nx))
                compset = set(comp)
                chc = {p for p in compset if p in ch}
                if not chc:
                    col = None
                else:
                    if chc != compset:
                        return {"pass": False,
                                "why": f"partial region fill pair {pi}"}
                    cols = {ch[p] for p in chc}
                    if len(cols) != 1:
                        return {"pass": False,
                                "why": f"multicolor region pair {pi}"}
                    col = cols.pop()
                    covered |= chc
                rs = [p[0] for p in comp]
                cs = [p[1] for p in comp]
                h = max(rs) - min(rs) + 1
                w = max(cs) - min(cs) + 1
                fk = {"touches_border": any(r in (0, H - 1) or c in (0, W - 1)
                                            for r, c in comp),
                      "area": len(comp), "bbox_hw": (h, w),
                      "is_rect": len(comp) == h * w,
                      "rect_hw": (len(comp) == h * w, h, w)}
                items.append((fk, col))
                items_pairs.append(pi)
        if covered != set(ch):
            return {"pass": False, "why": f"changed != region union pair {pi}"}
    results = {}
    for kind in ("touches_border", "area", "bbox_hw", "is_rect", "rect_hw"):
        table, occp, ok = {}, defaultdict(set), True
        for (fk, col), pi in zip(items, items_pairs):
            k = fk[kind]
            if k in table and table[k] != col:
                ok = False
                break
            table[k] = col
            occp[k].add(pi)
        if ok:
            results[kind] = {"n_keys": len(table),
                             "fold_coverable": fold_coverable(occp)}
    if not results:
        return {"pass": False, "why": "no consistent region color function"}
    return {"pass": True, "color_fn": results}


_D4 = [
    ("id", lambda r, c, h, w: (r, c)),
    ("rot90", lambda r, c, h, w: (c, h - 1 - r)),
    ("rot180", lambda r, c, h, w: (h - 1 - r, w - 1 - c)),
    ("rot270", lambda r, c, h, w: (w - 1 - c, r)),
    ("flipH", lambda r, c, h, w: (r, w - 1 - c)),
    ("flipV", lambda r, c, h, w: (h - 1 - r, c)),
    ("flipD", lambda r, c, h, w: (c, r)),
    ("flipA", lambda r, c, h, w: (w - 1 - c, h - 1 - r)),
]


def _norm(patt):
    r0 = min(p[0] for p in patt)
    c0 = min(p[1] for p in patt)
    return frozenset((r - r0, c - c0, v) for r, c, v in patt)


def check_template_stamp_xform(pairs, seg_mode):
    """every changed region equals some input object's pattern under a D4
    transform and a color bijection (bijection may differ per region)."""
    used = Counter()
    for pi, (inp, out) in enumerate(pairs):
        bg = background(inp)
        ch = changed_cells(inp, out)
        if not ch:
            return {"pass": False, "why": "pair with no change"}
        objs = segment(inp, bg, seg_mode)
        feats = [obj_features(inp, o) for o in objs]
        cells = set(ch)
        seen = set()
        for start in sorted(cells):
            if start in seen:
                continue
            stack, comp = [start], []
            seen.add(start)
            while stack:
                y, x = stack.pop()
                comp.append((y, x))
                for dr in (-1, 0, 1):
                    for dc in (-1, 0, 1):
                        p = (y + dr, x + dc)
                        if p in cells and p not in seen:
                            seen.add(p)
                            stack.append(p)
            target = _norm([(r, c, ch[(r, c)]) for r, c in comp])
            matched = False
            for f in feats:
                h, w = f["h"], f["w"]
                src = [(r, c, v) for r, c, v in f["pattern"]]
                for tname, tf in _D4:
                    timg = _norm([(tf(r, c, h, w) + (v,)) for r, c, v in src])
                    tshape = frozenset((r, c) for r, c, v in timg)
                    if tshape != frozenset((r, c) for r, c, v in target):
                        continue
                    # color bijection?
                    m, minv, ok = {}, {}, True
                    tmap = {(r, c): v for r, c, v in timg}
                    gmap = {(r, c): v for r, c, v in target}
                    for p in tshape:
                        a, b = tmap[p], gmap[p]
                        if m.get(a, b) != b or minv.get(b, a) != a:
                            ok = False
                            break
                        m[a] = b
                        minv[b] = a
                    if ok:
                        used[tname + ("" if all(k == v for k, v in m.items())
                                      else "+recolor")] += 1
                        matched = True
                        break
                if matched:
                    break
            if not matched:
                return {"pass": False,
                        "why": f"changed region pair {pi} matches no object "
                               f"under D4+bijection"}
    return {"pass": True, "transforms_used": dict(used)}


_VECS = [(0, 1), (0, 2), (0, 3), (0, 4), (0, 5), (0, 6), (0, 7), (0, 8),
         (1, 0), (2, 0), (3, 0), (4, 0), (5, 0), (6, 0), (7, 0), (8, 0),
         (1, 1), (1, -1), (2, 2), (2, -2), (1, 2), (2, 1), (1, -2), (2, -1)]


def check_periodic_extend(pairs):
    """output invariant under 1-2 translation vectors; every cell's value
    derivable from a non-background input cell in its orbit."""
    per_pair = []
    for pi, (inp, out) in enumerate(pairs):
        H, W = len(out), len(out[0])
        ch = changed_cells(inp, out)
        if not ch:
            return {"pass": False, "why": "pair with no change"}
        bg = background(inp)

        def invariant(v):
            vr, vc = v
            for r in range(H):
                for c in range(W):
                    rr, cc = r + vr, c + vc
                    if 0 <= rr < H and 0 <= cc < W and out[r][c] != out[rr][cc]:
                        return False
            return True

        invs = [v for v in _VECS if invariant(v)]
        if not invs:
            return {"pass": False, "why": f"no invariant vector pair {pi}"}
        # orbit closure under all invariant vectors; every changed cell's
        # orbit must contain an input cell that already had the output value
        found = None
        combos = [[v] for v in invs] + \
                 [[invs[i], invs[j]] for i in range(len(invs))
                  for j in range(i + 1, len(invs))]
        for vecs in combos[:120]:
            ok = True
            for (r, c) in ch:
                orbit, stack = {(r, c)}, [(r, c)]
                while stack and len(orbit) < 4 * H * W:
                    y, x = stack.pop()
                    for vr, vc in vecs:
                        for s in (1, -1):
                            p = (y + s * vr, x + s * vc)
                            if 0 <= p[0] < H and 0 <= p[1] < W \
                                    and p not in orbit:
                                orbit.add(p)
                                stack.append(p)
                if not any(inp[y][x] == out[r][c] and inp[y][x] != bg
                           for y, x in orbit):
                    ok = False
                    break
            if ok:
                found = vecs
                break
        if not found:
            return {"pass": False,
                    "why": f"orbit not derivable from input pair {pi}"}
        per_pair.append(found)
    return {"pass": True, "vectors": per_pair}


# ------------------------------------------------------- stored-mask stats
def stored_mask_stats(task_id):
    path = os.path.join(ROOT, "outputs/unified_harness_v22/object/"
                              f"near_solve_parts/{task_id}.jsonl")
    if not os.path.exists(path):
        return None
    best = None
    for line in open(path):
        r = json.loads(line)
        fit = r.get("train_fit_pixels") or 0
        if best is None or fit > (best.get("train_fit_pixels") or 0):
            best = r
    rules = (best.get("program_partial") or {}).get("rules", [])
    n_pat, sizes, n_rules = 0, [], len(rules)
    for rule in rules:
        act = rule.get("action", {})
        params = act.get("params", {})
        pat = params.get("pattern")
        if pat and pat.get("op") == "const":
            n_pat += 1
            args = pat.get("args", [None])[0]
            try:
                sizes.append(len(args["__tuple__"]))
            except Exception:
                sizes.append(-1)
    sels = []
    for rule in rules:
        pred = (rule.get("selector") or {}).get("predicate") or {}
        a = pred.get("args") or []
        sels.append(a[0] if a else None)
    return {"seg_variant": best.get("segmentation_variant"),
            "train_fit_pixels": best.get("train_fit_pixels"),
            "failure_stage": best.get("failure_stage"),
            "n_rules": n_rules, "n_const_pattern_rules": n_pat,
            "pattern_sizes": sizes, "selector_features": sels}


# ------------------------------------------------------------------- main
def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    fam, exp, counts = load_working_set()
    ch_all = json.load(open(os.path.join(ROOT,
                        "data/arc-agi_training_challenges.json")))
    rows = []
    for t in exp:
        task = ch_all[t]
        pairs = [(p["input"], p["output"]) for p in task["train"]]
        H = max(len(p["input"]) for p in task["train"])
        W = max(len(p["input"][0]) for p in task["train"])
        bg = background(pairs[0][0])
        nobj = {m: [len(segment(i, background(i), m)) for i, _ in pairs]
                for m in ("color4", "multi8")}
        nch = [len(changed_cells(i, o)) for i, o in pairs]
        bg_frac = []
        for i, o in pairs:
            b = background(i)
            cc = changed_cells(i, o)
            bg_frac.append(sum(1 for p in cc if i[p[0]][p[1]] == b)
                           / max(1, len(cc)))
        row = {"task_id": t, "n_pairs": len(pairs), "grid_max": [H, W],
               "n_objects": {m: v for m, v in nobj.items()},
               "n_changed": nch,
               "changed_on_bg_frac": [round(f, 3) for f in bg_frac],
               "stored": stored_mask_stats(t),
               "checks": {}}
        # run checkers
        for m in ("color4", "multi8"):
            r = check_interior_fill(pairs, m)
            row["checks"][f"INTERIOR_FILL[{m}]"] = r
            for d in ("chebyshev", "manhattan", "corners"):
                row["checks"][f"HALO[{m},{d}]"] = check_halo(pairs, m, d)
            for off in (0, 1):
                row["checks"][f"BBOX_OUTLINE[{m},off{off}]"] = \
                    check_bbox_outline(pairs, m, off)
            row["checks"][f"TEMPLATE_COPY[{m}]"] = check_template_copy(pairs, m)
            row["checks"][f"TEMPLATE_STAMP_XFORM[{m}]"] = \
                check_template_stamp_xform(pairs, m)
            for kk in ("color", "shape", "color+shape"):
                row["checks"][f"REL_STAMP[{m},{kk}]"] = \
                    check_rel_stamp(pairs, m, kk)
        row["checks"]["PERIODIC_REPAIR"] = check_periodic_repair(pairs)
        row["checks"]["REGION_FILL_PANELS"] = check_region_fill(pairs)
        row["checks"]["REGION_FILL_CONNECTED"] = \
            check_region_fill_connected(pairs)
        row["checks"]["PERIODIC_EXTEND"] = check_periodic_extend(pairs)
        rows.append(row)
        passes = [k for k, v in row["checks"].items() if v.get("pass")]
        print(t, "PASS:", passes if passes else "NONE", flush=True)

    with open(os.path.join(OUT_DIR, "trace_results.jsonl"), "w") as f:
        for row in rows:
            f.write(json.dumps(row, default=str) + "\n")

    summary = {
        "family": FAMILY,
        "family_total": len(fam),
        "split_counts": dict(counts),
        "experience_ids": exp,
        "checker_pass_counts": Counter(
            k for row in rows for k, v in row["checks"].items()
            if v.get("pass")),
        "tasks_no_pass": [r["task_id"] for r in rows
                          if not any(v.get("pass")
                                     for v in r["checks"].values())],
    }
    summary["checker_pass_counts"] = dict(summary["checker_pass_counts"])
    with open(os.path.join(OUT_DIR, "trace_summary.json"), "w") as f:
        json.dump(summary, f, indent=1, default=str)
    print(json.dumps({k: v for k, v in summary.items()
                      if k != "experience_ids"}, indent=1, default=str))


if __name__ == "__main__":
    sys.setrecursionlimit(100000)
    main()
