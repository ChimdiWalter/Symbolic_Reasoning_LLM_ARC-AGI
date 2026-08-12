"""ARC Reasoning V2: advanced pure reasoning strategies.

Strategies:
  1. Pattern extrapolation (row/col/tile periodicity)
  2. Per-object transform discovery (move, recolor, delete, grow)
  3. Grid-within-grid reasoning (subgrid decomposition)
  4. Template stamping (detect template + placement rule)
  5. Counting-based reasoning (output encodes counts)
  6. Symmetry completion (complete partial symmetry)
  7. Border/frame operations
  8. Majority/minority object filtering
  9. Pixel rule mining (multi-feature context → color)
 10. Relative position reasoning (distance/direction features)
"""
from __future__ import annotations

import time
import uuid
from collections import Counter, defaultdict
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import numpy as np
from scipy.ndimage import label as ndlabel

from reasoning_project.operator_genesis import SynthesizedOperator


def _check(fn, train_pairs):
    for inp, out in train_pairs:
        try:
            pred = fn(inp)
            if pred is None or not isinstance(pred, np.ndarray):
                return False
            if pred.shape != out.shape or not np.array_equal(pred, out):
                return False
        except Exception:
            return False
    return True


def _mk(family, fn, explanation):
    return SynthesizedOperator(
        operator_id=f"v2_{family}_{uuid.uuid4().hex[:8]}",
        operator_family=family,
        parameters={},
        preconditions=[],
        execute=fn,
        explanation=explanation,
        source_failure_signature={},
    )


def _extract_objects(grid, bg=0):
    mask = grid != bg
    labeled, n = ndlabel(mask)
    objs = []
    for i in range(1, n + 1):
        m = labeled == i
        rows, cols = np.where(m)
        r0, c0 = int(rows.min()), int(cols.min())
        r1, c1 = int(rows.max()), int(cols.max())
        patch = grid[r0:r1+1, c0:c1+1].copy()
        local_mask = m[r0:r1+1, c0:c1+1]
        colors = set(grid[m].tolist()) - {bg}
        objs.append({
            "mask": m, "rows": rows, "cols": cols,
            "r0": r0, "c0": c0, "r1": r1, "c1": c1,
            "patch": patch, "local_mask": local_mask,
            "area": int(m.sum()), "color": int(Counter(grid[m].tolist()).most_common(1)[0][0]),
            "colors": colors, "h": r1 - r0 + 1, "w": c1 - c0 + 1,
            "center_r": float(rows.mean()), "center_c": float(cols.mean()),
        })
    return objs


# ===================================================================
# Strategy 1: Pattern Extrapolation
# ===================================================================

def _try_pattern_extrapolation(train_pairs, deadline):
    results = []
    if not all(i.shape == o.shape for i, o in train_pairs):
        return results
    inp0, out0 = train_pairs[0]
    H, W = inp0.shape

    # Row periodicity: check if output rows follow a periodic pattern derived from input
    for period in range(1, min(H // 2 + 1, 8)):
        if time.time() > deadline:
            break
        for fill_rule in ["tile_rows", "mirror_rows"]:
            def make_fn(p, rule):
                def fn(grid, _p=p, _r=rule):
                    h, w = grid.shape
                    out = grid.copy()
                    if _r == "tile_rows":
                        for r in range(h):
                            out[r] = grid[r % _p]
                    elif _r == "mirror_rows":
                        for r in range(h):
                            cycle = r // _p
                            pos = r % _p
                            if cycle % 2 == 1:
                                pos = _p - 1 - pos
                            out[r] = grid[min(pos, h - 1)]
                    return out
                return fn
            fn = make_fn(period, fill_rule)
            if _check(fn, train_pairs):
                results.append(_mk(f"pattern_{fill_rule}_p{period}", fn,
                                   f"Pattern: {fill_rule} period={period}"))
                return results

    # Column periodicity
    for period in range(1, min(W // 2 + 1, 8)):
        if time.time() > deadline:
            break
        def make_fn(p):
            def fn(grid, _p=p):
                h, w = grid.shape
                out = grid.copy()
                for c in range(w):
                    out[:, c] = grid[:, c % _p]
                return out
            return fn
        fn = make_fn(period)
        if _check(fn, train_pairs):
            results.append(_mk(f"pattern_tile_cols_p{period}", fn,
                               f"Pattern: tile columns period={period}"))
            return results

    return results


# ===================================================================
# Strategy 2: Per-Object Transform Discovery
# ===================================================================

def _try_per_object_transforms(train_pairs, deadline):
    results = []
    if not all(i.shape == o.shape for i, o in train_pairs):
        return results

    # Detect background color
    all_colors = Counter()
    for inp, _ in train_pairs:
        for v in inp.flat:
            all_colors[int(v)] += 1
    bg = all_colors.most_common(1)[0][0]

    # Strategy: per-color recolor based on object properties
    for pair_idx, (inp, out) in enumerate(train_pairs):
        if time.time() > deadline:
            return results
        in_objs = _extract_objects(inp, bg)
        out_objs = _extract_objects(out, bg)
        if not in_objs:
            return results

    # Try: recolor objects by a property (size rank, position, has holes, etc.)
    property_fns = [
        ("area", lambda o: o["area"]),
        ("height", lambda o: o["h"]),
        ("width", lambda o: o["w"]),
        ("top", lambda o: o["r0"]),
        ("left", lambda o: o["c0"]),
        ("center_r", lambda o: int(o["center_r"])),
        ("center_c", lambda o: int(o["center_c"])),
    ]

    for prop_name, prop_fn in property_fns:
        if time.time() > deadline:
            return results

        # Learn: property_value → output_color mapping
        prop_color_map = {}
        consistent = True
        for inp, out in train_pairs:
            in_objs = _extract_objects(inp, bg)
            for obj in in_objs:
                pval = prop_fn(obj)
                mask = obj["mask"]
                out_colors = set(out[mask].tolist()) - {bg}
                if len(out_colors) == 1:
                    oc = out_colors.pop()
                    if pval in prop_color_map:
                        if prop_color_map[pval] != oc:
                            consistent = False
                            break
                    else:
                        prop_color_map[pval] = oc
                elif len(out_colors) == 0:
                    if pval in prop_color_map:
                        if prop_color_map[pval] != bg:
                            consistent = False
                            break
                    else:
                        prop_color_map[pval] = bg
            if not consistent:
                break

        if consistent and prop_color_map:
            frozen_map = dict(prop_color_map)
            _bg = bg
            def make_fn(pm, b, pfn):
                def fn(grid, _pm=pm, _b=b, _pfn=pfn):
                    out = grid.copy()
                    objs = _extract_objects(grid, _b)
                    for obj in objs:
                        pv = _pfn(obj)
                        if pv in _pm:
                            out[obj["mask"]] = _pm[pv]
                    return out
                return fn
            fn = make_fn(frozen_map, bg, prop_fn)
            if _check(fn, train_pairs):
                results.append(_mk(f"obj_recolor_by_{prop_name}", fn,
                                   f"Recolor objects by {prop_name}: {frozen_map}"))
                return results

    # Try: keep only objects matching a color/property, delete others
    for inp, out in train_pairs[:1]:
        in_objs = _extract_objects(inp, bg)
        # Which objects survived in output?
        survived_colors = set()
        deleted_colors = set()
        for obj in in_objs:
            mask = obj["mask"]
            if np.all(out[mask] == bg):
                deleted_colors.add(obj["color"])
            else:
                survived_colors.add(obj["color"])

        if survived_colors and deleted_colors and not (survived_colors & deleted_colors):
            frozen_keep = frozenset(survived_colors)
            _bg2 = bg
            def make_fn(keep_colors, b):
                def fn(grid, _kc=keep_colors, _b=b):
                    out = np.full_like(grid, _b)
                    objs = _extract_objects(grid, _b)
                    for obj in objs:
                        if obj["color"] in _kc:
                            out[obj["mask"]] = grid[obj["mask"]]
                    return out
                return fn
            fn = make_fn(frozen_keep, bg)
            if _check(fn, train_pairs):
                results.append(_mk("obj_keep_by_color", fn,
                                   f"Keep objects with colors {frozen_keep}"))
                return results

    # Try: keep largest / smallest object
    for keep_rule in ["largest", "smallest"]:
        if time.time() > deadline:
            return results
        _bg3 = bg
        def make_fn(rule, b):
            def fn(grid, _rule=rule, _b=b):
                out = np.full_like(grid, _b)
                objs = _extract_objects(grid, _b)
                if not objs:
                    return grid.copy()
                if _rule == "largest":
                    best = max(objs, key=lambda o: o["area"])
                else:
                    best = min(objs, key=lambda o: o["area"])
                out[best["mask"]] = grid[best["mask"]]
                return out
            return fn
        fn = make_fn(keep_rule, bg)
        if _check(fn, train_pairs):
            results.append(_mk(f"obj_keep_{keep_rule}", fn,
                               f"Keep {keep_rule} object"))
            return results

    # Try: sort objects by size and recolor by rank
    rank_color_map = {}
    rank_consistent = True
    for inp, out in train_pairs:
        in_objs = sorted(_extract_objects(inp, bg), key=lambda o: (o["area"], o["r0"], o["c0"]))
        for rank, obj in enumerate(in_objs):
            mask = obj["mask"]
            out_colors = set(out[mask].tolist()) - {bg}
            if len(out_colors) == 1:
                oc = out_colors.pop()
                if rank in rank_color_map:
                    if rank_color_map[rank] != oc:
                        rank_consistent = False
                        break
                else:
                    rank_color_map[rank] = oc
        if not rank_consistent:
            break

    if rank_consistent and rank_color_map:
        frozen_rank = dict(rank_color_map)
        _bg4 = bg
        def make_fn(rm, b):
            def fn(grid, _rm=rm, _b=b):
                out = grid.copy()
                objs = sorted(_extract_objects(grid, _b), key=lambda o: (o["area"], o["r0"], o["c0"]))
                for rank, obj in enumerate(objs):
                    if rank in _rm:
                        out[obj["mask"]] = _rm[rank]
                return out
            return fn
        fn = make_fn(frozen_rank, bg)
        if _check(fn, train_pairs):
            results.append(_mk("obj_recolor_by_rank", fn,
                               f"Recolor objects by size rank: {frozen_rank}"))
            return results

    return results


# ===================================================================
# Strategy 3: Grid-Within-Grid
# ===================================================================

def _try_grid_within_grid(train_pairs, deadline):
    results = []

    for inp0, out0 in train_pairs[:1]:
        H, W = inp0.shape
        # Look for separator rows/cols (uniform color rows)
        for sep_c in range(10):
            sep_rows = [r for r in range(H) if np.all(inp0[r, :] == sep_c)]
            sep_cols = [c for c in range(W) if np.all(inp0[:, c] == sep_c)]

            if len(sep_rows) >= 1 and len(sep_cols) >= 1:
                # Extract sub-cells between separators
                row_bounds = [-1] + sep_rows + [H]
                col_bounds = [-1] + sep_cols + [W]

                cells_r = [(row_bounds[i]+1, row_bounds[i+1]) for i in range(len(row_bounds)-1)
                           if row_bounds[i]+1 < row_bounds[i+1]]
                cells_c = [(col_bounds[i]+1, col_bounds[i+1]) for i in range(len(col_bounds)-1)
                           if col_bounds[i]+1 < col_bounds[i+1]]

                if len(cells_r) >= 2 and len(cells_c) >= 2:
                    cell_h = cells_r[0][1] - cells_r[0][0]
                    cell_w = cells_c[0][1] - cells_c[0][0]

                    if all(r1 - r0 == cell_h for r0, r1 in cells_r) and \
                       all(c1 - c0 == cell_w for c0, c1 in cells_c):
                        # Uniform sub-cells — try meta-level operations
                        nr, nc = len(cells_r), len(cells_c)

                        # Try: meta-level color = majority color in sub-cell
                        # Then apply a per-meta-cell rule
                        def _get_meta_grid(grid, cr, cc, sc):
                            h, w = grid.shape
                            s_rows = [r for r in range(h) if np.all(grid[r, :] == sc)]
                            s_cols = [c for c in range(w) if np.all(grid[:, c] == sc)]
                            rb = [-1] + s_rows + [h]
                            cb = [-1] + s_cols + [w]
                            crs = [(rb[i]+1, rb[i+1]) for i in range(len(rb)-1) if rb[i]+1 < rb[i+1]]
                            ccs = [(cb[i]+1, cb[i+1]) for i in range(len(cb)-1) if cb[i]+1 < cb[i+1]]
                            meta = np.zeros((len(crs), len(ccs)), dtype=int)
                            for ri, (r0, r1) in enumerate(crs):
                                for ci, (c0, c1) in enumerate(ccs):
                                    cell = grid[r0:r1, c0:c1]
                                    counts = Counter(cell.flat)
                                    if sc in counts:
                                        del counts[sc]
                                    if 0 in counts:
                                        del counts[0]
                                    meta[ri, ci] = counts.most_common(1)[0][0] if counts else 0
                            return meta, crs, ccs

                        # Check if output is also grid-structured with same separators
                        if out0.shape == inp0.shape:
                            break  # same shape — meta reasoning can work but complex

    return results


# ===================================================================
# Strategy 4: Template Stamping
# ===================================================================

def _try_template_stamping(train_pairs, deadline):
    results = []
    if not all(i.shape == o.shape for i, o in train_pairs):
        return results

    inp0, out0 = train_pairs[0]
    bg = 0

    # Find what was added (pixels that changed from bg to non-bg)
    added_mask = (inp0 == bg) & (out0 != bg)
    if not added_mask.any():
        return results

    # Find "seed" positions in input (non-bg pixels)
    seed_positions = list(zip(*np.where(inp0 != bg)))
    if not seed_positions or len(seed_positions) > 50:
        return results

    # For each seed, check if there's a consistent stamp pattern relative to it
    added_positions = list(zip(*np.where(added_mask)))
    if not added_positions:
        return results

    # Try: stamp a fixed template at each seed position
    for template_size in range(1, 6):
        if time.time() > deadline:
            break
        for seed_r, seed_c in seed_positions[:10]:
            seed_color = int(inp0[seed_r, seed_c])
            # Collect relative offsets and colors of added pixels near this seed
            nearby = []
            for ar, ac in added_positions:
                dr, dc = ar - seed_r, ac - seed_c
                if abs(dr) <= template_size and abs(dc) <= template_size:
                    nearby.append((dr, dc, int(out0[ar, ac])))

            if not nearby:
                continue

            # Check if same relative pattern exists at ALL seeds with same color
            same_color_seeds = [(r, c) for r, c in seed_positions if int(inp0[r, c]) == seed_color]
            if len(same_color_seeds) < 2:
                continue

            stamp_consistent = True
            for sr, sc in same_color_seeds:
                for dr, dc, expected_c in nearby:
                    tr, tc = sr + dr, sc + dc
                    H, W = out0.shape
                    if 0 <= tr < H and 0 <= tc < W:
                        if int(out0[tr, tc]) != expected_c and (tr, tc) not in seed_positions:
                            stamp_consistent = False
                            break
                if not stamp_consistent:
                    break

            if stamp_consistent and nearby:
                frozen_stamp = list(nearby)
                _sc = seed_color
                _bg = bg
                def make_fn(stamp, sc, b):
                    def fn(grid, _stamp=stamp, _sc=sc, _b=b):
                        out = grid.copy()
                        h, w = grid.shape
                        seeds = list(zip(*np.where(grid == _sc)))
                        for sr, scc in seeds:
                            for dr, dc, tc in _stamp:
                                tr, tcc = sr + dr, scc + dc
                                if 0 <= tr < h and 0 <= tcc < w and grid[tr, tcc] == _b:
                                    out[tr, tcc] = tc
                        return out
                    return fn
                fn = make_fn(frozen_stamp, seed_color, bg)
                if _check(fn, train_pairs):
                    results.append(_mk("template_stamp", fn,
                                       f"Stamp template ({len(frozen_stamp)} pixels) at color-{seed_color} seeds"))
                    return results

    return results


# ===================================================================
# Strategy 5: Counting-Based Reasoning
# ===================================================================

def _try_counting(train_pairs, deadline):
    results = []
    # Check if output is 1x1 or very small — could be a count
    out_shapes = [out.shape for _, out in train_pairs]
    if not all(s == out_shapes[0] for s in out_shapes):
        return results

    oh, ow = out_shapes[0]
    if oh * ow > 10:
        return results

    bg = 0

    # Count objects in input → match to output value
    for count_what in ["objects", "colors", "non_bg_pixels"]:
        count_map = {}
        consistent = True
        for inp, out in train_pairs:
            if count_what == "objects":
                objs = _extract_objects(inp, bg)
                count_val = len(objs)
            elif count_what == "colors":
                count_val = len(set(inp.flat) - {bg})
            else:
                count_val = int(np.sum(inp != bg))

            # Check if output is simply the count
            if oh == 1 and ow == 1:
                expected = int(out[0, 0])
                if count_val != expected:
                    consistent = False
                    break
        if consistent:
            _cw = count_what
            _oh, _ow = oh, ow
            def make_fn(what, bg_c, out_h, out_w):
                def fn(grid, _w=what, _b=bg_c, _oh=out_h, _ow=out_w):
                    if _w == "objects":
                        val = len(_extract_objects(grid, _b))
                    elif _w == "colors":
                        val = len(set(grid.flat) - {_b})
                    else:
                        val = int(np.sum(grid != _b))
                    out = np.zeros((_oh, _ow), dtype=int)
                    out[0, 0] = val
                    return out
                return fn
            fn = make_fn(count_what, bg, oh, ow)
            if _check(fn, train_pairs):
                results.append(_mk(f"count_{count_what}", fn,
                                   f"Count {count_what} → output"))
                return results

    return results


# ===================================================================
# Strategy 6: Symmetry Completion
# ===================================================================

def _try_symmetry_completion(train_pairs, deadline):
    results = []
    if not all(i.shape == o.shape for i, o in train_pairs):
        return results

    # Check: is output = input with horizontal/vertical symmetry imposed?
    for axis_name, axis_fn in [
        ("horizontal", lambda g: g[:, ::-1]),
        ("vertical", lambda g: g[::-1, :]),
        ("diagonal", lambda g: g.T if g.shape[0] == g.shape[1] else None),
        ("anti_diagonal", lambda g: g[::-1, ::-1].T if g.shape[0] == g.shape[1] else None),
    ]:
        # Try: output = overlay(input, flipped_input) keeping non-bg
        bg = 0
        def make_fn(afn, b):
            def fn(grid, _afn=afn, _b=b):
                flipped = _afn(grid)
                if flipped is None:
                    return grid.copy()
                out = grid.copy()
                fill_mask = (grid == _b) & (flipped != _b)
                out[fill_mask] = flipped[fill_mask]
                return out
            return fn
        fn = make_fn(axis_fn, bg)
        if _check(fn, train_pairs):
            results.append(_mk(f"symmetry_{axis_name}", fn,
                               f"Complete {axis_name} symmetry"))
            return results

    # Try: output = flipped input (replace, not overlay)
    for axis_name, axis_fn in [
        ("h_flip", lambda g: g[:, ::-1].copy()),
        ("v_flip", lambda g: g[::-1, :].copy()),
        ("rot90", lambda g: np.rot90(g, 1).copy()),
        ("rot180", lambda g: np.rot90(g, 2).copy()),
        ("rot270", lambda g: np.rot90(g, 3).copy()),
    ]:
        fn = axis_fn
        if _check(fn, train_pairs):
            results.append(_mk(f"transform_{axis_name}", fn,
                               f"Transform: {axis_name}"))
            return results

    return results


# ===================================================================
# Strategy 7: Border/Frame Operations
# ===================================================================

def _try_border_ops(train_pairs, deadline):
    results = []

    inp0, out0 = train_pairs[0]
    iH, iW = inp0.shape
    oH, oW = out0.shape

    # Add 1-pixel border
    if oH == iH + 2 and oW == iW + 2:
        for border_c in range(10):
            def make_fn(bc):
                def fn(grid, _bc=bc):
                    h, w = grid.shape
                    out = np.full((h + 2, w + 2), _bc, dtype=int)
                    out[1:-1, 1:-1] = grid
                    return out
                return fn
            fn = make_fn(border_c)
            if _check(fn, train_pairs):
                results.append(_mk("add_border", fn,
                                   f"Add border color={border_c}"))
                return results

    # Remove 1-pixel border
    if oH == iH - 2 and oW == iW - 2 and iH >= 3 and iW >= 3:
        def fn(grid):
            return grid[1:-1, 1:-1].copy()
        if _check(fn, train_pairs):
            results.append(_mk("remove_border", fn, "Remove 1-pixel border"))
            return results

    # Fill border with a color (same shape)
    if iH == oH and iW == oW:
        for border_c in range(10):
            def make_fn(bc):
                def fn(grid, _bc=bc):
                    out = grid.copy()
                    out[0, :] = _bc
                    out[-1, :] = _bc
                    out[:, 0] = _bc
                    out[:, -1] = _bc
                    return out
                return fn
            fn = make_fn(border_c)
            if _check(fn, train_pairs):
                results.append(_mk("fill_border", fn,
                                   f"Fill border with color {border_c}"))
                return results

    return results


# ===================================================================
# Strategy 8: Majority/Minority Filtering
# ===================================================================

def _try_majority_minority(train_pairs, deadline):
    results = []
    if not all(i.shape == o.shape for i, o in train_pairs):
        return results

    bg = 0

    # Keep only the most/least frequent color objects
    for rule in ["most_frequent", "least_frequent"]:
        def make_fn(r, b):
            def fn(grid, _r=r, _b=b):
                objs = _extract_objects(grid, _b)
                if not objs:
                    return grid.copy()
                color_counts = Counter(o["color"] for o in objs)
                if _r == "most_frequent":
                    keep_color = color_counts.most_common(1)[0][0]
                else:
                    keep_color = color_counts.most_common()[-1][0]
                out = np.full_like(grid, _b)
                for obj in objs:
                    if obj["color"] == keep_color:
                        out[obj["mask"]] = grid[obj["mask"]]
                return out
            return fn
        fn = make_fn(rule, bg)
        if _check(fn, train_pairs):
            results.append(_mk(f"filter_{rule}_color", fn,
                               f"Keep {rule} color objects"))
            return results

    return results


# ===================================================================
# Strategy 9: Pixel Rule Mining
# ===================================================================

def _try_pixel_rule_mining(train_pairs, deadline):
    results = []
    if not all(i.shape == o.shape for i, o in train_pairs):
        return results

    # Strategy: for each cell, compute (input_color, row_nonbg_count, col_nonbg_count) → output_color
    feature_sets = [
        ("ic_rnbc_cnbc", lambda g, r, c: (
            int(g[r, c]),
            int(np.sum(g[r, :] != 0)),
            int(np.sum(g[:, c] != 0)),
        )),
        ("ic_rdom_cdom", lambda g, r, c: (
            int(g[r, c]),
            int(np.argmax(np.bincount(g[r, :].astype(int), minlength=10))),
            int(np.argmax(np.bincount(g[:, c].astype(int), minlength=10))),
        )),
        ("ic_rnuniq_cnuniq", lambda g, r, c: (
            int(g[r, c]),
            len(set(g[r, :].tolist())),
            len(set(g[:, c].tolist())),
        )),
        ("ic_rdist_cdist", lambda g, r, c: (
            int(g[r, c]),
            min(r, g.shape[0] - 1 - r),
            min(c, g.shape[1] - 1 - c),
        )),
    ]

    for feat_name, feat_fn in feature_sets:
        if time.time() > deadline:
            break

        rule_map = {}
        consistent = True
        for inp, out in train_pairs:
            H, W = inp.shape
            for r in range(H):
                for c in range(W):
                    key = feat_fn(inp, r, c)
                    val = int(out[r, c])
                    if key in rule_map:
                        if rule_map[key] != val:
                            consistent = False
                            break
                    else:
                        rule_map[key] = val
                if not consistent:
                    break
            if not consistent:
                break

        if consistent and rule_map and len(rule_map) < 500:
            frozen_rules = dict(rule_map)
            def make_fn(rules, ffn):
                def fn(grid, _rules=rules, _ffn=ffn):
                    H, W = grid.shape
                    out = grid.copy()
                    for r in range(H):
                        for c in range(W):
                            key = _ffn(grid, r, c)
                            if key in _rules:
                                out[r, c] = _rules[key]
                    return out
                return fn
            fn = make_fn(frozen_rules, feat_fn)
            if _check(fn, train_pairs):
                results.append(_mk(f"pixel_rule_{feat_name}", fn,
                                   f"Pixel rule ({feat_name}): {len(frozen_rules)} entries"))
                return results

    return results


# ===================================================================
# Strategy 10: Relative Position / Distance Reasoning
# ===================================================================

def _try_relative_position(train_pairs, deadline):
    results = []
    if not all(i.shape == o.shape for i, o in train_pairs):
        return results

    bg = 0

    # For each cell: distance to nearest non-bg pixel → output color
    dist_rules = {}
    dist_ok = True
    for inp, out in train_pairs:
        if time.time() > deadline:
            return results
        nonbg_mask = inp != bg
        if not nonbg_mask.any():
            dist_ok = False
            break
        from scipy.ndimage import distance_transform_edt
        dist = distance_transform_edt(~nonbg_mask)
        H, W = inp.shape
        for r in range(H):
            for c in range(W):
                key = (int(inp[r, c]), int(dist[r, c]))
                val = int(out[r, c])
                if key in dist_rules:
                    if dist_rules[key] != val:
                        dist_ok = False
                        break
                else:
                    dist_rules[key] = val
            if not dist_ok:
                break
        if not dist_ok:
            break

    if dist_ok and dist_rules and len(dist_rules) < 200:
        frozen_dist = dict(dist_rules)
        def make_fn(rules, b):
            def fn(grid, _rules=rules, _b=b):
                from scipy.ndimage import distance_transform_edt
                nonbg = grid != _b
                if not nonbg.any():
                    return grid.copy()
                dist = distance_transform_edt(~nonbg)
                H, W = grid.shape
                out = grid.copy()
                for r in range(H):
                    for c in range(W):
                        key = (int(grid[r, c]), int(dist[r, c]))
                        if key in _rules:
                            out[r, c] = _rules[key]
                return out
            return fn
        fn = make_fn(frozen_dist, bg)
        if _check(fn, train_pairs):
            results.append(_mk("distance_rule", fn,
                               f"Distance-based rule: {len(frozen_dist)} entries"))
            return results

    return results


# ===================================================================
# Strategy 11: Connected Component Properties → Color
# ===================================================================

def _try_component_property_coloring(train_pairs, deadline):
    results = []
    if not all(i.shape == o.shape for i, o in train_pairs):
        return results
    bg = 0

    # Learn: (object_has_holes, object_is_symmetric) → new_color for each pixel
    prop_fns = [
        ("has_holes", lambda obj: 1 if _obj_has_holes(obj) else 0),
        ("is_h_sym", lambda obj: 1 if np.array_equal(obj["local_mask"], obj["local_mask"][::-1, :]) else 0),
        ("is_v_sym", lambda obj: 1 if np.array_equal(obj["local_mask"], obj["local_mask"][:, ::-1]) else 0),
        ("is_square", lambda obj: 1 if obj["h"] == obj["w"] else 0),
    ]

    for pname, pfn in prop_fns:
        if time.time() > deadline:
            return results
        color_map = {}
        ok = True
        for inp, out in train_pairs:
            objs = _extract_objects(inp, bg)
            for obj in objs:
                pval = pfn(obj)
                mask = obj["mask"]
                out_vals = set(out[mask].tolist())
                if len(out_vals) == 1:
                    oc = out_vals.pop()
                    key = (obj["color"], pval)
                    if key in color_map:
                        if color_map[key] != oc:
                            ok = False
                            break
                    else:
                        color_map[key] = oc
            if not ok:
                break

        if ok and color_map:
            frozen = dict(color_map)
            def make_fn(cm, b, pf):
                def fn(grid, _cm=cm, _b=b, _pf=pf):
                    out = grid.copy()
                    objs = _extract_objects(grid, _b)
                    for obj in objs:
                        pv = _pf(obj)
                        key = (obj["color"], pv)
                        if key in _cm:
                            out[obj["mask"]] = _cm[key]
                    return out
                return fn
            fn = make_fn(frozen, bg, pfn)
            if _check(fn, train_pairs):
                results.append(_mk(f"obj_color_by_{pname}", fn,
                                   f"Recolor objects by (color, {pname})"))
                return results

    return results


def _obj_has_holes(obj):
    local = obj["local_mask"]
    bg_labeled, n = ndlabel(~local)
    border_labels = set()
    h, w = local.shape
    border_labels.update(bg_labeled[0, :].tolist())
    border_labels.update(bg_labeled[-1, :].tolist())
    border_labels.update(bg_labeled[:, 0].tolist())
    border_labels.update(bg_labeled[:, -1].tolist())
    border_labels.discard(0)
    return n - len(border_labels) > 0


# ===================================================================
# Strategy 12: Flood Fill Enclosed Regions
# ===================================================================

def _try_flood_fill_enclosed(train_pairs, deadline):
    results = []
    if not all(i.shape == o.shape for i, o in train_pairs):
        return results

    for bg in [0]:
        # Fill enclosed regions with border color
        def make_fn(b):
            def fn(grid, _b=b):
                from scipy.ndimage import label as lbl, binary_dilation
                bg_mask = grid == _b
                labeled, n = lbl(bg_mask)
                h, w = grid.shape
                edge_labels = set()
                edge_labels.update(labeled[0, :].tolist())
                edge_labels.update(labeled[-1, :].tolist())
                edge_labels.update(labeled[:, 0].tolist())
                edge_labels.update(labeled[:, -1].tolist())
                edge_labels.discard(0)
                out = grid.copy()
                for lab in range(1, n + 1):
                    if lab not in edge_labels:
                        region = labeled == lab
                        border = binary_dilation(region) & ~region
                        border_colors = set(grid[border].tolist()) - {_b}
                        if len(border_colors) == 1:
                            out[region] = border_colors.pop()
                return out
            return fn
        fn = make_fn(bg)
        if _check(fn, train_pairs):
            results.append(_mk("flood_fill_enclosed", fn,
                               "Fill enclosed regions with border color"))
            return results

    return results


# ===================================================================
# Strategy 13: Row/Col Uniform Operations
# ===================================================================

def _try_row_col_ops(train_pairs, deadline):
    results = []
    if not all(i.shape == o.shape for i, o in train_pairs):
        return results

    inp0, out0 = train_pairs[0]
    H, W = inp0.shape

    # Sort rows by some property
    for sort_key_name, sort_key_fn in [
        ("nonzero_count", lambda row: -int(np.sum(row != 0))),
        ("sum", lambda row: -int(np.sum(row))),
        ("unique_count", lambda row: -len(set(row.tolist()))),
    ]:
        def make_fn(skf):
            def fn(grid, _skf=skf):
                rows = [grid[r, :].copy() for r in range(grid.shape[0])]
                rows.sort(key=_skf)
                return np.array(rows)
            return fn
        fn = make_fn(sort_key_fn)
        if _check(fn, train_pairs):
            results.append(_mk(f"sort_rows_{sort_key_name}", fn,
                               f"Sort rows by {sort_key_name}"))
            return results

    # Sort columns
    for sort_key_name, sort_key_fn in [
        ("nonzero_count", lambda col: -int(np.sum(col != 0))),
    ]:
        def make_fn(skf):
            def fn(grid, _skf=skf):
                cols = [grid[:, c].copy() for c in range(grid.shape[1])]
                cols.sort(key=_skf)
                return np.column_stack(cols)
            return fn
        fn = make_fn(sort_key_fn)
        if _check(fn, train_pairs):
            results.append(_mk(f"sort_cols_{sort_key_name}", fn,
                               f"Sort columns by {sort_key_name}"))
            return results

    return results


# ===================================================================
# Strategy 14: Tiling / Upscaling
# ===================================================================

def _try_tiling(train_pairs, deadline):
    results = []
    inp0, out0 = train_pairs[0]
    iH, iW = inp0.shape
    oH, oW = out0.shape

    if oH == 0 or oW == 0 or iH == 0 or iW == 0:
        return results

    # Check if output is a tiled version of input
    if oH % iH == 0 and oW % iW == 0:
        reps_r, reps_c = oH // iH, oW // iW
        if reps_r >= 2 or reps_c >= 2:
            def make_fn(rr, rc):
                def fn(grid, _rr=rr, _rc=rc):
                    return np.tile(grid, (_rr, _rc))
                return fn
            fn = make_fn(reps_r, reps_c)
            if _check(fn, train_pairs):
                results.append(_mk(f"tile_{reps_r}x{reps_c}", fn,
                                   f"Tile {reps_r}x{reps_c}"))
                return results

    # Check if output is upscaled input
    if oH % iH == 0 and oW % iW == 0:
        scale_r, scale_c = oH // iH, oW // iW
        if scale_r == scale_c and scale_r >= 2:
            def make_fn(s):
                def fn(grid, _s=s):
                    return np.repeat(np.repeat(grid, _s, axis=0), _s, axis=1)
                return fn
            fn = make_fn(scale_r)
            if _check(fn, train_pairs):
                results.append(_mk(f"upscale_{scale_r}x", fn,
                                   f"Upscale {scale_r}x"))
                return results

    # Check if output is downscaled input
    if iH % oH == 0 and iW % oW == 0:
        scale_r, scale_c = iH // oH, iW // oW
        if scale_r == scale_c and scale_r >= 2:
            for rule in ["top_left", "majority"]:
                def make_fn(s, r):
                    def fn(grid, _s=s, _r=r):
                        h, w = grid.shape
                        oh, ow = h // _s, w // _s
                        out = np.zeros((oh, ow), dtype=int)
                        for r in range(oh):
                            for c in range(ow):
                                block = grid[r*_s:(r+1)*_s, c*_s:(c+1)*_s]
                                if _r == "top_left":
                                    out[r, c] = int(block[0, 0])
                                else:
                                    out[r, c] = int(Counter(block.flat).most_common(1)[0][0])
                        return out
                    return fn
                fn = make_fn(scale_r, rule)
                if _check(fn, train_pairs):
                    results.append(_mk(f"downscale_{scale_r}x_{rule}", fn,
                                       f"Downscale {scale_r}x ({rule})"))
                    return results

    return results


# ===================================================================
# Strategy 15: Mask/Boolean Operations on Input
# ===================================================================

def _try_mask_ops(train_pairs, deadline):
    results = []
    if not all(i.shape == o.shape for i, o in train_pairs):
        return results

    # AND/OR/XOR of two color layers
    inp0, out0 = train_pairs[0]
    colors = sorted(set(inp0.flat) - {0})
    if len(colors) < 2:
        return results

    for c1 in colors:
        for c2 in colors:
            if c1 >= c2:
                continue
            if time.time() > deadline:
                return results
            # Intersection: pixels that are c1 AND have c2 neighbor → output color
            for op_name, op_fn in [
                ("and", lambda m1, m2: m1 & m2),
                ("or", lambda m1, m2: m1 | m2),
                ("xor", lambda m1, m2: m1 ^ m2),
            ]:
                for out_c in range(1, 10):
                    def make_fn(cc1, cc2, ofn, oc):
                        def fn(grid, _c1=cc1, _c2=cc2, _ofn=ofn, _oc=oc):
                            m1 = grid == _c1
                            m2 = grid == _c2
                            result = _ofn(m1, m2)
                            out = np.zeros_like(grid)
                            out[result] = _oc
                            return out
                        return fn
                    fn = make_fn(c1, c2, op_fn, out_c)
                    if _check(fn, train_pairs):
                        results.append(_mk(f"mask_{op_name}_{c1}_{c2}", fn,
                                           f"Mask {op_name}(color {c1}, color {c2}) → {out_c}"))
                        return results

    return results


# ===================================================================
# Main entry point
# ===================================================================

def reason_v2(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    timeout_seconds: float = 10.0,
) -> List[SynthesizedOperator]:
    start = time.time()
    deadline = start + timeout_seconds
    results = []

    strategies = [
        _try_symmetry_completion,
        _try_tiling,
        _try_border_ops,
        _try_flood_fill_enclosed,
        _try_counting,
        _try_template_stamping,
        _try_per_object_transforms,
        _try_majority_minority,
        _try_pixel_rule_mining,
        _try_pattern_extrapolation,
        _try_relative_position,
        _try_component_property_coloring,
        _try_row_col_ops,
        _try_mask_ops,
        _try_grid_within_grid,
    ]

    for strategy in strategies:
        if time.time() > deadline:
            break
        try:
            ops = strategy(train_pairs, deadline)
            results.extend(ops)
            if results:
                break
        except Exception:
            continue

    return results
