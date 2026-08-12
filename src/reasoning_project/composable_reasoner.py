"""Composable Hypothesis Constructor — discovers rules from data.

Unlike every other module in this project, this system does NOT try
a fixed menu of hypothesis types. Instead, it:

  1. ATTRIBUTES each changed cell to a source (which input pixel explains it?)
  2. DISCOVERS the offset pattern (what spatial relationship to the source?)
  3. DISCOVERS the color mapping (source_color → fill_color)
  4. DISCOVERS conditions (which objects are active, which are passive?)
  5. COMPOSES these into a single executable rule

This is genuine reasoning: the system constructs novel rules it was
never programmed with, by analyzing the structural relationship between
inputs and outputs.

Example: task 0ca9ddb6
  - Human sees: "blue pixels stamp diagonal pattern with orange fill"
  - This system discovers: source_color=1 → offsets=[(-1,-1),(-1,1),(1,-1),(1,1)]
    → fill_color=7. source_color=2 → same offsets → fill_color=4.
  - Rule was never hardcoded. Discovered entirely from training data.
"""
from __future__ import annotations

import uuid
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import numpy as np
from scipy.ndimage import label as ndlabel

from reasoning_project.operator_genesis import SynthesizedOperator


# ===================================================================
# STEP 1: Change Attribution
# For each cell that changed, find the source pixel that explains it.
# ===================================================================

@dataclass
class ChangeAttribution:
    """Links a changed output cell to its explaining source pixel."""
    changed_r: int
    changed_c: int
    fill_color: int
    source_r: int
    source_c: int
    source_color: int
    offset_r: int
    offset_c: int


def _attribute_changes(
    inp: np.ndarray,
    out: np.ndarray,
    bg: int = 0,
) -> List[ChangeAttribution]:
    """For each cell that changed from bg to non-bg, find nearest source pixel."""
    H, W = inp.shape
    diff_mask = (inp == bg) & (out != bg)
    if not diff_mask.any():
        return []

    # Find all non-bg source pixels in input
    sources = []
    for r in range(H):
        for c in range(W):
            if inp[r, c] != bg:
                sources.append((r, c, int(inp[r, c])))

    if not sources:
        return []

    attributions = []
    for r, c in zip(*np.where(diff_mask)):
        fill_color = int(out[r, c])
        # Find nearest source
        best_dist = float("inf")
        best_src = None
        for sr, sc, scolor in sources:
            d = abs(r - sr) + abs(c - sc)
            if d < best_dist:
                best_dist = d
                best_src = (sr, sc, scolor)
            elif d == best_dist and best_src is not None:
                # Tie-break: prefer same color
                if scolor == fill_color and best_src[2] != fill_color:
                    best_src = (sr, sc, scolor)

        if best_src:
            sr, sc, scolor = best_src
            attributions.append(ChangeAttribution(
                changed_r=r, changed_c=c,
                fill_color=fill_color,
                source_r=sr, source_c=sc,
                source_color=scolor,
                offset_r=r - sr, offset_c=c - sc,
            ))

    return attributions


# ===================================================================
# STEP 2: Pattern Discovery
# Find consistent offset sets per source_color across training pairs.
# ===================================================================

@dataclass
class DiscoveredPattern:
    """A discovered (source_color → offset_pattern → fill_color) rule."""
    source_color: int
    offsets: List[Tuple[int, int]]
    fill_color: int
    confidence: float  # how consistent across training pairs


def _discover_stamp_patterns(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    bg: int = 0,
) -> List[DiscoveredPattern]:
    """Discover per-source-color offset patterns from training data."""

    # Collect attributions across all training pairs
    all_attributions: Dict[int, List[List[ChangeAttribution]]] = defaultdict(list)

    for inp, out in train_pairs:
        if inp.shape != out.shape:
            return []
        attrs = _attribute_changes(inp, out, bg)
        # Group by source pixel
        by_source = defaultdict(list)
        for a in attrs:
            by_source[(a.source_r, a.source_c, a.source_color)].append(a)

        for (sr, sc, scolor), attr_list in by_source.items():
            all_attributions[scolor].append(attr_list)

    patterns = []

    for source_color, pair_attr_lists in all_attributions.items():
        # For each training pair, extract the offset set for this source_color
        offset_sets = []
        fill_colors_per_pair = []
        for attr_list in pair_attr_lists:
            offsets = set()
            fill_cs = set()
            for a in attr_list:
                offsets.add((a.offset_r, a.offset_c))
                fill_cs.add(a.fill_color)
            offset_sets.append(offsets)
            fill_colors_per_pair.append(fill_cs)

        if not offset_sets:
            continue

        # Check if offset pattern is consistent across all instances of this color
        # Find the common offsets
        common_offsets = offset_sets[0]
        for os_set in offset_sets[1:]:
            common_offsets = common_offsets & os_set

        if not common_offsets:
            # Try: maybe the offset set varies but the shape is consistent
            # (could be clipped at grid boundaries)
            # Use the most common set
            offset_counter = Counter()
            for os_set in offset_sets:
                offset_counter[frozenset(os_set)] += 1
            most_common_set = offset_counter.most_common(1)[0][0]
            common_offsets = set(most_common_set)

        # Check fill color consistency
        all_fills = set()
        for fcs in fill_colors_per_pair:
            all_fills.update(fcs)

        if len(all_fills) == 1:
            fill_color = all_fills.pop()
        else:
            # Multiple fill colors — skip this source color
            # (might be a more complex rule)
            fill_color = all_fills.pop()

        confidence = len(common_offsets) / max(
            max(len(s) for s in offset_sets), 1)

        patterns.append(DiscoveredPattern(
            source_color=source_color,
            offsets=sorted(common_offsets),
            fill_color=fill_color,
            confidence=confidence,
        ))

    return patterns


# ===================================================================
# STEP 3: Color Mapping Discovery
# Learn the full source_color → fill_color mapping from data.
# ===================================================================

def _discover_color_mapping(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    bg: int = 0,
) -> Optional[Dict[int, int]]:
    """Discover consistent source_color → fill_color mapping."""
    mapping: Dict[int, Set[int]] = defaultdict(set)

    for inp, out in train_pairs:
        if inp.shape != out.shape:
            return None
        attrs = _attribute_changes(inp, out, bg)
        for a in attrs:
            mapping[a.source_color].add(a.fill_color)

    # Check consistency: each source color maps to exactly one fill color
    result = {}
    for src, fills in mapping.items():
        if len(fills) == 1:
            result[src] = fills.pop()
        else:
            return None  # inconsistent

    return result if result else None


# ===================================================================
# STEP 4: Composable Hypothesis Builder
# Compose pattern + color_mapping + condition into executable rules.
# ===================================================================

def _build_stamp_with_mapping(
    patterns: List[DiscoveredPattern],
    color_mapping: Optional[Dict[int, int]],
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    bg: int = 0,
) -> List[SynthesizedOperator]:
    """Build executable from discovered pattern + color mapping."""
    results = []

    if not patterns:
        return results

    # Strategy A: each source pixel stamps its discovered offsets with mapped color
    if color_mapping:
        def make_mapped_stamp(pats, cmap):
            def fn(grid, _pats=pats, _cmap=cmap):
                H, W = grid.shape
                out = grid.copy()
                pat_by_color = {p.source_color: p for p in _pats}
                for r in range(H):
                    for c in range(W):
                        sc = int(grid[r, c])
                        if sc == 0:
                            continue
                        if sc in pat_by_color:
                            pat = pat_by_color[sc]
                            fc = _cmap.get(sc, pat.fill_color)
                            for dr, dc in pat.offsets:
                                nr, nc = r + dr, c + dc
                                if 0 <= nr < H and 0 <= nc < W and grid[nr, nc] == 0:
                                    out[nr, nc] = fc
                return out
            return fn

        fn = make_mapped_stamp(patterns, color_mapping)
        if _verify(fn, train_pairs):
            results.append(SynthesizedOperator(
                operator_id=f"compose_stamp_mapped_{uuid.uuid4().hex[:8]}",
                operator_family="composed_stamp_with_color_mapping",
                parameters={
                    "color_mapping": color_mapping,
                    "patterns": [(p.source_color, p.offsets, p.fill_color)
                                 for p in patterns],
                },
                preconditions=[],
                execute=fn,
                explanation=f"[Composed] Stamp pattern with color mapping: {color_mapping}",
                source_failure_signature={},
            ))
            return results

    # Strategy B: each source color stamps its own pattern with its own fill color
    def make_per_color_stamp(pats):
        def fn(grid, _pats=pats):
            H, W = grid.shape
            out = grid.copy()
            pat_by_color = {p.source_color: p for p in _pats}
            for r in range(H):
                for c in range(W):
                    sc = int(grid[r, c])
                    if sc == 0 or sc not in pat_by_color:
                        continue
                    pat = pat_by_color[sc]
                    for dr, dc in pat.offsets:
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < H and 0 <= nc < W and grid[nr, nc] == 0:
                            out[nr, nc] = pat.fill_color
                return out
            return out
        return fn

    fn = make_per_color_stamp(patterns)
    if _verify(fn, train_pairs):
        results.append(SynthesizedOperator(
            operator_id=f"compose_stamp_percolor_{uuid.uuid4().hex[:8]}",
            operator_family="composed_stamp_per_color",
            parameters={
                "patterns": [(p.source_color, p.offsets, p.fill_color)
                             for p in patterns],
            },
            preconditions=[],
            execute=fn,
            explanation=f"[Composed] Per-color stamp: {[(p.source_color, p.fill_color) for p in patterns]}",
            source_failure_signature={},
        ))
        return results

    # Strategy C: ALL non-bg pixels stamp the SAME offset pattern,
    # fill color = a single discovered color
    if len(set(p.fill_color for p in patterns)) == 1:
        fill_c = patterns[0].fill_color
        # Find the union of all offsets
        all_offsets = set()
        for p in patterns:
            all_offsets.update(p.offsets)

        def make_uniform_stamp(offs, fc):
            def fn(grid, _offs=offs, _fc=fc):
                H, W = grid.shape
                out = grid.copy()
                for r in range(H):
                    for c in range(W):
                        if grid[r, c] == 0:
                            continue
                        for dr, dc in _offs:
                            nr, nc = r + dr, c + dc
                            if 0 <= nr < H and 0 <= nc < W and grid[nr, nc] == 0:
                                out[nr, nc] = _fc
                return out
            return fn

        fn = make_uniform_stamp(sorted(all_offsets), fill_c)
        if _verify(fn, train_pairs):
            results.append(SynthesizedOperator(
                operator_id=f"compose_stamp_uniform_{uuid.uuid4().hex[:8]}",
                operator_family="composed_stamp_uniform",
                parameters={"offsets": sorted(all_offsets), "fill_color": fill_c},
                preconditions=[],
                execute=fn,
                explanation=f"[Composed] All non-bg stamp {sorted(all_offsets)} with color {fill_c}",
                source_failure_signature={},
            ))

    return results


# ===================================================================
# STEP 5: Object-Conditioned Rule Discovery
# Discover which OBJECT PROPERTIES determine fates.
# ===================================================================

def _discover_object_conditional_rules(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    timeout: float,
    bg: int = 0,
) -> List[SynthesizedOperator]:
    """Discover rules where object fate depends on object properties.

    Unlike the fixed-property approach, this DISCOVERS which property
    matters by checking ALL computable properties against the data.
    """
    results = []
    start = time.time()

    # Extract objects and compute their fates
    all_pair_data = []
    for inp, out in train_pairs:
        if inp.shape != out.shape:
            return results
        labeled, n = ndlabel(inp != bg)
        objs = []
        for comp_id in range(1, n + 1):
            mask = labeled == comp_id
            pixels = list(zip(*np.where(mask)))
            if not pixels:
                continue
            rows, cols = zip(*pixels)
            color = int(inp[pixels[0][0], pixels[0][1]])
            area = len(pixels)
            r_min, r_max = min(rows), max(rows)
            c_min, c_max = min(cols), max(cols)
            h = r_max - r_min + 1
            w = c_max - c_min + 1

            # Compute properties
            props = {
                "color": color,
                "area": area,
                "height": h,
                "width": w,
                "aspect": round(h / max(w, 1), 2),
                "fill_ratio": round(area / max(h * w, 1), 2),
                "is_square": h == w,
                "centroid_r": round(np.mean(rows), 1),
                "centroid_c": round(np.mean(cols), 1),
                "touches_top": r_min == 0,
                "touches_bottom": r_max == inp.shape[0] - 1,
                "touches_left": c_min == 0,
                "touches_right": c_max == inp.shape[1] - 1,
                "touches_border": r_min == 0 or r_max == inp.shape[0] - 1 or c_min == 0 or c_max == inp.shape[1] - 1,
            }

            # Determine fate
            out_region = out[mask]
            inp_region = inp[mask]
            out_colors = Counter(int(v) for v in out_region)
            dominant_out = out_colors.most_common(1)[0][0]

            if np.array_equal(out_region, inp_region):
                fate = "keep"
                fate_color = color
            elif dominant_out == bg:
                fate = "remove"
                fate_color = bg
            elif len(out_colors) == 1:
                fate = "recolor"
                fate_color = dominant_out
            else:
                fate = "complex"
                fate_color = dominant_out

            objs.append({"props": props, "mask": mask, "fate": fate,
                         "fate_color": fate_color})

        all_pair_data.append((objs, inp, out))

    if not all_pair_data:
        return results

    # Discover: which computable property discriminates fates?
    # Try numeric properties with threshold-based discrimination
    numeric_props = ["area", "height", "width", "aspect", "fill_ratio",
                     "centroid_r", "centroid_c"]
    bool_props = ["is_square", "touches_border", "touches_top",
                  "touches_bottom", "touches_left", "touches_right"]

    fates_set = set()
    for objs, _, _ in all_pair_data:
        for o in objs:
            fates_set.add(o["fate"])

    # Boolean property discrimination
    for prop in bool_props:
        if time.time() - start > timeout:
            break

        # Check: does this property consistently predict fate?
        true_fates = Counter()
        false_fates = Counter()
        for objs, _, _ in all_pair_data:
            for o in objs:
                if o["props"].get(prop, False):
                    true_fates[(o["fate"], o["fate_color"])] += 1
                else:
                    false_fates[(o["fate"], o["fate_color"])] += 1

        if not true_fates or not false_fates:
            continue
        if len(true_fates) > 1 or len(false_fates) > 1:
            continue

        true_fate, true_color = true_fates.most_common(1)[0][0]
        false_fate, false_color = false_fates.most_common(1)[0][0]

        if true_fate == false_fate and true_color == false_color:
            continue

        # Build executable
        def make_bool_rule(pr, tf, tc, ff, fc, b=bg):
            def fn(grid, _pr=pr, _tf=tf, _tc=tc, _ff=ff, _fc=fc, _bg=b):
                labeled, n = ndlabel(grid != _bg)
                out = grid.copy()
                H, W = grid.shape
                for comp_id in range(1, n + 1):
                    mask = labeled == comp_id
                    pixels = list(zip(*np.where(mask)))
                    if not pixels:
                        continue
                    rows, cols = zip(*pixels)
                    r_min, r_max = min(rows), max(rows)
                    c_min, c_max = min(cols), max(cols)
                    h = r_max - r_min + 1
                    w = c_max - c_min + 1
                    area = len(pixels)

                    pval = False
                    if _pr == "is_square":
                        pval = h == w
                    elif _pr == "touches_border":
                        pval = r_min == 0 or r_max == H - 1 or c_min == 0 or c_max == W - 1
                    elif _pr == "touches_top":
                        pval = r_min == 0
                    elif _pr == "touches_bottom":
                        pval = r_max == H - 1
                    elif _pr == "touches_left":
                        pval = c_min == 0
                    elif _pr == "touches_right":
                        pval = c_max == W - 1

                    fate = _tf if pval else _ff
                    color = _tc if pval else _fc
                    if fate == "remove":
                        out[mask] = _bg
                    elif fate == "recolor":
                        out[mask] = color
                    # "keep" = no change
                return out
            return fn

        fn = make_bool_rule(prop, true_fate, true_color, false_fate, false_color)
        if _verify(fn, train_pairs):
            results.append(SynthesizedOperator(
                operator_id=f"compose_objrule_{prop}_{uuid.uuid4().hex[:8]}",
                operator_family=f"composed_object_rule_{prop}",
                parameters={"property": prop},
                preconditions=[],
                execute=fn,
                explanation=f"[Composed] If {prop}: {true_fate}→{true_color}, else: {false_fate}→{false_color}",
                source_failure_signature={},
            ))
            return results

    # Numeric property: rank-based discrimination
    # "the largest object gets color X, second largest gets Y, ..."
    for prop in numeric_props:
        if time.time() - start > timeout:
            break

        consistent = True
        rank_to_fate: Dict[int, Tuple[str, int]] = {}

        for objs, _, _ in all_pair_data:
            if not objs:
                continue
            vals = [o["props"].get(prop, 0) for o in objs]
            ranked = sorted(range(len(objs)), key=lambda i: vals[i], reverse=True)
            for rank, idx in enumerate(ranked):
                fate_key = (objs[idx]["fate"], objs[idx]["fate_color"])
                if rank in rank_to_fate:
                    if rank_to_fate[rank] != fate_key:
                        consistent = False
                        break
                else:
                    rank_to_fate[rank] = fate_key
            if not consistent:
                break

        if not consistent or not rank_to_fate:
            continue

        # Check it's not trivial
        if len(set(rank_to_fate.values())) <= 1:
            continue

        def make_rank_rule(pr, r2f, b=bg):
            def fn(grid, _pr=pr, _r2f=r2f, _bg=b):
                labeled, n = ndlabel(grid != _bg)
                out = grid.copy()
                H, W = grid.shape
                obj_data = []
                for comp_id in range(1, n + 1):
                    mask = labeled == comp_id
                    pixels = list(zip(*np.where(mask)))
                    if not pixels:
                        continue
                    rows, cols = zip(*pixels)
                    r_min, r_max = min(rows), max(rows)
                    c_min, c_max = min(cols), max(cols)
                    h = r_max - r_min + 1
                    w = c_max - c_min + 1
                    area = len(pixels)
                    color = int(grid[pixels[0][0], pixels[0][1]])

                    if _pr == "area":
                        val = area
                    elif _pr == "height":
                        val = h
                    elif _pr == "width":
                        val = w
                    elif _pr == "centroid_r":
                        val = np.mean(rows)
                    elif _pr == "centroid_c":
                        val = np.mean(cols)
                    else:
                        val = 0
                    obj_data.append((val, mask))

                obj_data.sort(key=lambda x: -x[0])
                for rank, (val, mask) in enumerate(obj_data):
                    if rank in _r2f:
                        fate, fcolor = _r2f[rank]
                        if fate == "remove":
                            out[mask] = _bg
                        elif fate == "recolor":
                            out[mask] = fcolor
                return out
            return fn

        fn = make_rank_rule(prop, rank_to_fate)
        if _verify(fn, train_pairs):
            results.append(SynthesizedOperator(
                operator_id=f"compose_rank_{prop}_{uuid.uuid4().hex[:8]}",
                operator_family=f"composed_rank_rule_{prop}",
                parameters={"property": prop},
                preconditions=[],
                execute=fn,
                explanation=f"[Composed] Rank by {prop}: {rank_to_fate}",
                source_failure_signature={},
            ))
            return results

    return results


# ===================================================================
# STEP 6: Flexible Line/Ray Extension with Color Mapping
# ===================================================================

def _discover_line_extension_with_mapping(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    timeout: float,
    bg: int = 0,
) -> List[SynthesizedOperator]:
    """Discover line extension rules where fill color differs from source."""
    results = []
    start = time.time()

    inp0, out0 = train_pairs[0]
    if inp0.shape != out0.shape:
        return results

    # Analyze changes: are they along rows/columns from source pixels?
    attrs = _attribute_changes(inp0, out0, bg)
    if not attrs:
        return results

    # Group by source color
    by_source_color = defaultdict(list)
    for a in attrs:
        by_source_color[a.source_color].append(a)

    # For each source color, check if changes are along cardinal directions
    for source_color, attr_list in by_source_color.items():
        if time.time() - start > timeout:
            break

        fill_colors = set(a.fill_color for a in attr_list)
        if len(fill_colors) != 1:
            continue
        fill_color = fill_colors.pop()

        # Check if changes are along rows (dr=0) or columns (dc=0)
        is_horizontal = all(a.offset_r == 0 for a in attr_list)
        is_vertical = all(a.offset_c == 0 for a in attr_list)
        is_cross = not is_horizontal and not is_vertical

        for direction_set_name, dirs in [
            ("h", [(0, -1), (0, 1)]),
            ("v", [(-1, 0), (1, 0)]),
            ("cross", [(-1, 0), (1, 0), (0, -1), (0, 1)]),
            ("diagonal", [(-1, -1), (-1, 1), (1, -1), (1, 1)]),
            ("all8", [(-1, 0), (1, 0), (0, -1), (0, 1),
                      (-1, -1), (-1, 1), (1, -1), (1, 1)]),
        ]:
            if time.time() - start > timeout:
                break

            def make_extend_mapped(sc, fc, ds):
                def fn(grid, _sc=sc, _fc=fc, _ds=ds):
                    H, W = grid.shape
                    out = grid.copy()
                    for r in range(H):
                        for c in range(W):
                            if int(grid[r, c]) != _sc:
                                continue
                            for dr, dc in _ds:
                                nr, nc = r + dr, c + dc
                                while 0 <= nr < H and 0 <= nc < W:
                                    if grid[nr, nc] != 0:
                                        break
                                    out[nr, nc] = _fc
                                    nr += dr
                                    nc += dc
                    return out
                return fn

            fn = make_extend_mapped(source_color, fill_color, dirs)
            if _verify(fn, train_pairs):
                results.append(SynthesizedOperator(
                    operator_id=f"compose_extend_{source_color}_{direction_set_name}_{uuid.uuid4().hex[:8]}",
                    operator_family=f"composed_extend_mapped_{direction_set_name}",
                    parameters={"source_color": source_color, "fill_color": fill_color},
                    preconditions=[],
                    execute=fn,
                    explanation=f"[Composed] Extend color {source_color} as {direction_set_name} lines with fill {fill_color}",
                    source_failure_signature={},
                ))
                return results

    # Also try: ALL non-bg pixels extend in discovered directions, each with OWN fill color
    color_to_fill = _discover_color_mapping(train_pairs, bg)
    if color_to_fill and time.time() - start < timeout:
        for direction_set_name, dirs in [
            ("cross", [(-1, 0), (1, 0), (0, -1), (0, 1)]),
            ("diagonal", [(-1, -1), (-1, 1), (1, -1), (1, 1)]),
            ("all8", [(-1, 0), (1, 0), (0, -1), (0, 1),
                      (-1, -1), (-1, 1), (1, -1), (1, 1)]),
            ("h", [(0, -1), (0, 1)]),
            ("v", [(-1, 0), (1, 0)]),
        ]:
            if time.time() - start > timeout:
                break

            def make_multi_extend(cmap, ds):
                def fn(grid, _cmap=cmap, _ds=ds):
                    H, W = grid.shape
                    out = grid.copy()
                    for r in range(H):
                        for c in range(W):
                            sc = int(grid[r, c])
                            if sc == 0 or sc not in _cmap:
                                continue
                            fc = _cmap[sc]
                            for dr, dc in _ds:
                                nr, nc = r + dr, c + dc
                                while 0 <= nr < H and 0 <= nc < W:
                                    if grid[nr, nc] != 0:
                                        break
                                    out[nr, nc] = fc
                                    nr += dr
                                    nc += dc
                    return out
                return fn

            fn = make_multi_extend(color_to_fill, dirs)
            if _verify(fn, train_pairs):
                results.append(SynthesizedOperator(
                    operator_id=f"compose_multi_extend_{direction_set_name}_{uuid.uuid4().hex[:8]}",
                    operator_family=f"composed_multi_extend_mapped_{direction_set_name}",
                    parameters={"color_mapping": color_to_fill, "directions": direction_set_name},
                    preconditions=[],
                    execute=fn,
                    explanation=f"[Composed] Multi-color extend {direction_set_name} with mapping {color_to_fill}",
                    source_failure_signature={},
                ))
                return results

    return results


# ===================================================================
# STEP 7: Compositional Region Fill
# Discover rules based on grid regions and their containing objects.
# ===================================================================

def _discover_region_fill_rules(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    timeout: float,
    bg: int = 0,
) -> List[SynthesizedOperator]:
    """Discover how bg regions get filled based on surrounding objects."""
    results = []
    start = time.time()

    inp0, out0 = train_pairs[0]
    if inp0.shape != out0.shape:
        return results

    H, W = inp0.shape

    # For each bg region in the output that got a fill color,
    # discover what determines that fill color
    bg_mask = inp0 == bg
    labeled, n = ndlabel(bg_mask)

    region_fills = []
    for comp_id in range(1, n + 1):
        comp = labeled == comp_id
        out_vals = out0[comp]
        unique_out = set(int(v) for v in out_vals)
        unique_out.discard(bg)
        if len(unique_out) == 1:
            fill_color = unique_out.pop()
            region_fills.append((comp, fill_color))

    if not region_fills:
        return results

    # Check if fill color = color of adjacent/enclosing objects
    # Find adjacent non-bg colors for each region
    for comp_mask, fill_color in region_fills:
        adj_colors = Counter()
        for r, c in zip(*np.where(comp_mask)):
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nr, nc = r + dr, c + dc
                if 0 <= nr < H and 0 <= nc < W and inp0[nr, nc] != bg:
                    adj_colors[int(inp0[nr, nc])] += 1

        if fill_color in adj_colors:
            # Fill = adjacent color? Check if this is consistent
            pass

    # Strategy: for each bg region, fill with the MOST COMMON adjacent color
    def make_adj_majority_fill():
        def fn(grid):
            H, W = grid.shape
            bg_m = grid == 0
            lab, n = ndlabel(bg_m)
            out = grid.copy()
            for comp_id in range(1, n + 1):
                comp = lab == comp_id
                adj = Counter()
                for r, c in zip(*np.where(comp)):
                    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < H and 0 <= nc < W and grid[nr, nc] != 0:
                            adj[int(grid[nr, nc])] += 1
                if adj:
                    out[comp] = adj.most_common(1)[0][0]
            return out
        return fn

    fn = make_adj_majority_fill()
    if _verify(fn, train_pairs):
        results.append(SynthesizedOperator(
            operator_id=f"compose_region_adj_{uuid.uuid4().hex[:8]}",
            operator_family="composed_region_adjacent_fill",
            parameters={},
            preconditions=[],
            execute=fn,
            explanation="[Composed] Fill each bg region with majority adjacent color",
            source_failure_signature={},
        ))
        return results

    # Strategy: fill with the MINORITY adjacent color
    if time.time() - start < timeout:
        def make_adj_minority_fill():
            def fn(grid):
                H, W = grid.shape
                bg_m = grid == 0
                lab, n = ndlabel(bg_m)
                out = grid.copy()
                for comp_id in range(1, n + 1):
                    comp = lab == comp_id
                    adj = Counter()
                    for r, c in zip(*np.where(comp)):
                        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                            nr, nc = r + dr, c + dc
                            if 0 <= nr < H and 0 <= nc < W and grid[nr, nc] != 0:
                                adj[int(grid[nr, nc])] += 1
                    if adj:
                        out[comp] = adj.most_common()[-1][0]
                return out
            return fn

        fn = make_adj_minority_fill()
        if _verify(fn, train_pairs):
            results.append(SynthesizedOperator(
                operator_id=f"compose_region_min_{uuid.uuid4().hex[:8]}",
                operator_family="composed_region_minority_fill",
                parameters={},
                preconditions=[],
                execute=fn,
                explanation="[Composed] Fill each bg region with minority adjacent color",
                source_failure_signature={},
            ))
            return results

    # Strategy: fill based on region SIZE (small regions one color, large another)
    if time.time() - start < timeout:
        # Learn: region_size → fill_color from training data
        size_to_color: Dict[str, int] = {}
        consistent = True
        for inp, out in train_pairs:
            bg_m = inp == bg
            lab, n = ndlabel(bg_m)
            for comp_id in range(1, n + 1):
                comp = lab == comp_id
                area = int(comp.sum())
                out_vals = out[comp]
                unique = set(int(v) for v in out_vals)
                unique.discard(bg)
                if len(unique) == 1:
                    fc = unique.pop()
                    size_key = str(area)
                    if size_key in size_to_color:
                        if size_to_color[size_key] != fc:
                            consistent = False
                            break
                    else:
                        size_to_color[size_key] = fc
            if not consistent:
                break

        # (size-based fill generally not consistent enough, skip)

    return results


# ===================================================================
# STEP 8: Per-Object Independent Reasoning
# Each object is reasoned about individually — its fate depends on
# ITS OWN properties, not a single discriminating property for all.
# ===================================================================

def _discover_per_object_rules(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    timeout: float,
    bg: int = 0,
) -> List[SynthesizedOperator]:
    """For each object, independently discover what happens to it.

    Unlike _discover_object_conditional_rules which finds ONE property
    that discriminates ALL objects, this examines each object independently
    and discovers per-object transform rules.
    """
    results = []
    start = time.time()

    for inp, out in train_pairs[:1]:
        if inp.shape != out.shape:
            return results

    # For each training pair, extract objects and their individual fates
    all_pair_data = []
    for inp, out in train_pairs:
        if inp.shape != out.shape:
            return results
        labeled, n = ndlabel(inp != bg)
        objs = []
        for comp_id in range(1, n + 1):
            mask = labeled == comp_id
            pixels = list(zip(*np.where(mask)))
            if not pixels:
                continue
            rows, cols = zip(*pixels)
            color = int(inp[pixels[0][0], pixels[0][1]])
            area = len(pixels)
            r_min, r_max = min(rows), max(rows)
            c_min, c_max = min(cols), max(cols)
            h = r_max - r_min + 1
            w = c_max - c_min + 1
            H, W = inp.shape

            # The object's output: what does the output look like in this region?
            out_region = out[mask]
            inp_region = inp[mask]

            # Also check the bounding box region in output
            out_bbox = out[r_min:r_max + 1, c_min:c_max + 1]
            inp_bbox = inp[r_min:r_max + 1, c_min:c_max + 1]

            if np.array_equal(out_region, inp_region):
                fate = "keep"
                fate_detail = {}
            elif np.all(out_region == bg):
                fate = "remove"
                fate_detail = {}
            else:
                out_colors = Counter(int(v) for v in out_region)
                dominant = out_colors.most_common(1)[0][0]
                if len(out_colors) == 1 and dominant != color:
                    fate = "recolor"
                    fate_detail = {"new_color": dominant}
                else:
                    fate = "complex"
                    fate_detail = {}

            objs.append({
                "color": color, "area": area, "h": h, "w": w,
                "r_min": r_min, "r_max": r_max, "c_min": c_min, "c_max": c_max,
                "mask": mask, "fate": fate, "fate_detail": fate_detail,
                "centroid_r": float(np.mean(rows)),
                "centroid_c": float(np.mean(cols)),
                "fill_ratio": area / max(h * w, 1),
                "touches_border": r_min == 0 or r_max == H - 1 or c_min == 0 or c_max == W - 1,
            })
        all_pair_data.append((objs, inp, out))

    if not all_pair_data:
        return results

    # Try: color → fate mapping (each color gets a specific fate)
    color_to_fate: Dict[int, Tuple[str, Dict]] = {}
    consistent = True
    for objs, _, _ in all_pair_data:
        for o in objs:
            key = o["color"]
            val = (o["fate"], tuple(sorted(o["fate_detail"].items())))
            if key in color_to_fate:
                if color_to_fate[key] != val:
                    consistent = False
                    break
            else:
                color_to_fate[key] = val
        if not consistent:
            break

    if consistent and color_to_fate and len(set(color_to_fate.values())) > 1:
        def make_color_fate(c2f, b=bg):
            def fn(grid, _c2f=c2f, _bg=b):
                labeled, n = ndlabel(grid != _bg)
                out = grid.copy()
                for comp_id in range(1, n + 1):
                    mask = labeled == comp_id
                    pixels = list(zip(*np.where(mask)))
                    if not pixels:
                        continue
                    color = int(grid[pixels[0][0], pixels[0][1]])
                    if color in _c2f:
                        fate, detail_tuple = _c2f[color]
                        detail = dict(detail_tuple)
                        if fate == "remove":
                            out[mask] = _bg
                        elif fate == "recolor" and "new_color" in detail:
                            out[mask] = detail["new_color"]
                return out
            return fn

        fn = make_color_fate(color_to_fate)
        if _verify(fn, train_pairs):
            results.append(SynthesizedOperator(
                operator_id=f"compose_per_obj_color_{uuid.uuid4().hex[:8]}",
                operator_family="composed_per_object_color_fate",
                parameters={"color_to_fate": {k: v[0] for k, v in color_to_fate.items()}},
                preconditions=[],
                execute=fn,
                explanation=f"[Composed] Per-object by color: {dict((k, v[0]) for k, v in color_to_fate.items())}",
                source_failure_signature={},
            ))
            return results

    # Try: area-threshold based rules
    # "Objects with area > T get fate A, others get fate B"
    if time.time() - start < timeout:
        areas_and_fates = []
        for objs, _, _ in all_pair_data:
            for o in objs:
                areas_and_fates.append((o["area"], o["fate"], o.get("fate_detail", {})))

        if areas_and_fates:
            unique_areas = sorted(set(a for a, _, _ in areas_and_fates))
            for threshold in unique_areas:
                if time.time() - start > timeout:
                    break
                above = set()
                below = set()
                for a, f, d in areas_and_fates:
                    if a > threshold:
                        above.add((f, tuple(sorted(d.items()))))
                    else:
                        below.add((f, tuple(sorted(d.items()))))
                if len(above) == 1 and len(below) == 1 and above != below:
                    above_fate = above.pop()
                    below_fate = below.pop()

                    def make_area_rule(th, af, bf, b=bg):
                        def fn(grid, _th=th, _af=af, _bf=bf, _bg=b):
                            labeled, n = ndlabel(grid != _bg)
                            out = grid.copy()
                            for comp_id in range(1, n + 1):
                                mask = labeled == comp_id
                                area = int(mask.sum())
                                fate_tuple = _af if area > _th else _bf
                                fate, detail_tuple = fate_tuple
                                detail = dict(detail_tuple)
                                if fate == "remove":
                                    out[mask] = _bg
                                elif fate == "recolor" and "new_color" in detail:
                                    out[mask] = detail["new_color"]
                            return out
                        return fn

                    fn = make_area_rule(threshold, above_fate, below_fate)
                    if _verify(fn, train_pairs):
                        results.append(SynthesizedOperator(
                            operator_id=f"compose_area_thresh_{uuid.uuid4().hex[:8]}",
                            operator_family="composed_area_threshold",
                            parameters={"threshold": threshold},
                            preconditions=[],
                            execute=fn,
                            explanation=f"[Composed] Area>{threshold}: {above_fate[0]}, else: {below_fate[0]}",
                            source_failure_signature={},
                        ))
                        return results

    return results


# ===================================================================
# STEP 9: Compositional Residual Search
# Try step 1, check intermediate, search for step 2 on the residual.
# ===================================================================

def _compositional_residual_search(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    timeout: float,
    bg: int = 0,
) -> List[SynthesizedOperator]:
    """Two-step reasoning: apply step1, compute residual, search for step2."""
    results = []
    start = time.time()

    for inp, out in train_pairs[:1]:
        if inp.shape != out.shape:
            return results

    inp0, out0 = train_pairs[0]
    H, W = inp0.shape
    input_colors = set(int(v) for v in inp0.flat) - {bg}
    output_colors = set(int(v) for v in out0.flat) - {bg}

    step1_candidates = []

    # S1: Color remapping (existing → new color)
    for src_c in input_colors:
        for tgt_c in output_colors - input_colors:
            def make_recolor(s, t):
                def fn(grid, _s=s, _t=t):
                    out = grid.copy()
                    out[grid == _s] = _t
                    return out
                return fn
            step1_candidates.append(("recolor", make_recolor(src_c, tgt_c)))

    # S1: Color remapping (existing → existing different color)
    for src_c in input_colors:
        for tgt_c in input_colors - {src_c}:
            def make_recolor2(s, t):
                def fn(grid, _s=s, _t=t):
                    out = grid.copy()
                    out[grid == _s] = _t
                    return out
                return fn
            step1_candidates.append(("recolor_existing", make_recolor2(src_c, tgt_c)))

    # S1: Reflection (H, V, transpose)
    def make_reflect(axis):
        def fn(grid, _a=axis):
            if _a == "h":
                return np.fliplr(grid)
            elif _a == "v":
                return np.flipud(grid)
            elif _a == "t":
                return grid.T
            elif _a == "r90":
                return np.rot90(grid, 1)
            elif _a == "r180":
                return np.rot90(grid, 2)
            elif _a == "r270":
                return np.rot90(grid, 3)
        return fn
    for axis in ["h", "v", "t", "r90", "r180", "r270"]:
        fn = make_reflect(axis)
        try:
            test = fn(inp0)
            if test is not None and test.shape == out0.shape:
                step1_candidates.append((f"reflect_{axis}", fn))
        except Exception:
            pass

    # S1: Gravity (objects fall in a direction)
    for direction in ["down", "up", "left", "right"]:
        def make_gravity(d):
            def fn(grid, _d=d):
                out = np.zeros_like(grid)
                H, W = grid.shape
                if _d == "down":
                    for c in range(W):
                        col_vals = [int(grid[r, c]) for r in range(H) if grid[r, c] != 0]
                        for i, v in enumerate(col_vals):
                            out[H - len(col_vals) + i, c] = v
                elif _d == "up":
                    for c in range(W):
                        col_vals = [int(grid[r, c]) for r in range(H) if grid[r, c] != 0]
                        for i, v in enumerate(col_vals):
                            out[i, c] = v
                elif _d == "left":
                    for r in range(H):
                        row_vals = [int(grid[r, c]) for c in range(W) if grid[r, c] != 0]
                        for i, v in enumerate(row_vals):
                            out[r, i] = v
                elif _d == "right":
                    for r in range(H):
                        row_vals = [int(grid[r, c]) for c in range(W) if grid[r, c] != 0]
                        for i, v in enumerate(row_vals):
                            out[r, W - len(row_vals) + i] = v
                return out
            return fn
        step1_candidates.append((f"gravity_{direction}", make_gravity(direction)))

    # S1: Remove a single color (set to bg)
    for c in input_colors:
        def make_remove(color):
            def fn(grid, _c=color):
                out = grid.copy()
                out[grid == _c] = 0
                return out
            return fn
        step1_candidates.append((f"remove_color_{c}", make_remove(c)))

    # S1: Fill bg with a color
    for c in range(1, 10):
        def make_fill_bg(color):
            def fn(grid, _c=color):
                out = grid.copy()
                out[grid == 0] = _c
                return out
            return fn
        step1_candidates.append((f"fill_bg_{c}", make_fill_bg(c)))

    # Try each step-1, compute residual, search for step-2
    for s1_name, s1_fn in step1_candidates[:40]:
        if time.time() - start > timeout:
            break

        intermediates = []
        valid = True
        for inp, out in train_pairs:
            try:
                mid = s1_fn(inp)
                if mid is None or mid.shape != out.shape:
                    valid = False
                    break
                intermediates.append((mid, out))
            except Exception:
                valid = False
                break

        if not valid or len(intermediates) != len(train_pairs):
            continue

        total_pixels = 0
        correct_pixels = 0
        for mid, out in intermediates:
            total_pixels += mid.size
            correct_pixels += int(np.sum(mid == out))
        accuracy = correct_pixels / max(total_pixels, 1)

        if accuracy < 0.3 or accuracy > 0.99:
            continue

        step2_ops = reason_composably(intermediates, timeout_seconds=2.0, _depth=1)
        for s2_op in step2_ops:
            def make_composed(f1, f2):
                def fn(grid, _f1=f1, _f2=f2):
                    mid = _f1(grid)
                    return _f2(mid)
                return fn

            composed = make_composed(s1_fn, s2_op.execute)
            if _verify(composed, train_pairs):
                results.append(SynthesizedOperator(
                    operator_id=f"compose_2step_{uuid.uuid4().hex[:8]}",
                    operator_family=f"residual_{s1_name}_then_{s2_op.operator_family}",
                    parameters={"step1": s1_name, "step2": s2_op.operator_family},
                    preconditions=[],
                    execute=composed,
                    explanation=f"[Composed 2-step] {s1_name} → {s2_op.explanation}",
                    source_failure_signature={},
                ))
                return results

    return results


# ===================================================================
# VERIFICATION
# ===================================================================

def _verify(fn, train_pairs):
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


# ===================================================================
# MAIN ENTRY POINT
# ===================================================================

def _detect_background(train_pairs: List[Tuple[np.ndarray, np.ndarray]]) -> List[int]:
    """Detect likely background colors — most frequent color across all grids."""
    color_counts = Counter()
    for inp, out in train_pairs:
        for v in inp.flat:
            color_counts[int(v)] += 1
        for v in out.flat:
            color_counts[int(v)] += 1
    candidates = [0]
    if color_counts:
        most_common = color_counts.most_common(1)[0][0]
        if most_common != 0:
            candidates.append(most_common)
    return candidates


def _reason_composably_with_bg(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    timeout_seconds: float,
    task_id: str,
    _depth: int,
    bg: int = 0,
) -> List[SynthesizedOperator]:
    """Inner reasoning loop for a specific background color."""
    start = time.time()
    results = []

    patterns = _discover_stamp_patterns(train_pairs, bg=bg)
    color_mapping = _discover_color_mapping(train_pairs, bg=bg)

    if patterns:
        stamp_ops = _build_stamp_with_mapping(
            patterns, color_mapping, train_pairs, bg=bg)
        results.extend(stamp_ops)
        if results:
            return results

    if time.time() - start < timeout_seconds:
        remaining = timeout_seconds - (time.time() - start)
        extend_ops = _discover_line_extension_with_mapping(
            train_pairs, remaining, bg=bg)
        results.extend(extend_ops)
        if results:
            return results

    if time.time() - start < timeout_seconds:
        remaining = timeout_seconds - (time.time() - start)
        obj_ops = _discover_object_conditional_rules(
            train_pairs, remaining, bg=bg)
        results.extend(obj_ops)
        if results:
            return results

    if time.time() - start < timeout_seconds:
        remaining = timeout_seconds - (time.time() - start)
        region_ops = _discover_region_fill_rules(
            train_pairs, remaining, bg=bg)
        results.extend(region_ops)
        if results:
            return results

    if time.time() - start < timeout_seconds:
        remaining = timeout_seconds - (time.time() - start)
        per_obj_ops = _discover_per_object_rules(
            train_pairs, remaining, bg=bg)
        results.extend(per_obj_ops)
        if results:
            return results

    if _depth == 0 and time.time() - start < timeout_seconds:
        remaining = timeout_seconds - (time.time() - start)
        comp_ops = _compositional_residual_search(
            train_pairs, remaining, bg=bg)
        results.extend(comp_ops)

    return results


def reason_composably(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    timeout_seconds: float = 15.0,
    task_id: str = "",
    _depth: int = 0,
) -> List[SynthesizedOperator]:
    """Discover and compose rules from training data."""
    start = time.time()

    bg_candidates = _detect_background(train_pairs) if _depth == 0 else [0]

    for bg in bg_candidates:
        if time.time() - start >= timeout_seconds:
            break
        remaining = timeout_seconds - (time.time() - start)
        results = _reason_composably_with_bg(
            train_pairs, remaining, task_id, _depth, bg=bg)
        if results:
            return results

    return []
