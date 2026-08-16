#!/usr/bin/env python3
"""R19 TRACE stage 2: falsify candidate DERIVED modes against ground truth.

Candidate modes (each named by a stage-1 trace, none speculative):
  periodic_continue  — d8c310e9, 9b30e358: added = the object repeated along
                       one axis at a period DERIVED from the object itself
                       (its own internal period, else its bbox extent),
                       continued until the grid border.
  rect_frame         — 52fd389e: added = a solid rectangular ring around the
                       object's bbox whose THICKNESS is derived by counting
                       the object's minority-color cells, painted in the
                       minority color.

For each exemplar task: recompute the correspondence, take every GROW delta
whose detected mode is `pattern`, and check whether a candidate reproduces
the added set EXACTLY.  Anything not reproduced exactly is a REJECT.
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

EXEMPLARS = ["95755ff2", "5c0a986e", "575b1a71", "31adaf00", "9b30e358",
             "fcc82909", "ecdecbb3", "aa300dc3", "55059096", "c62e2108",
             "52fd389e", "9772c176", "c4d1a9ae", "d8c310e9", "e5062a87"]

NEAR_SOLVE = Path(PROJECT_ROOT) / "outputs/unified_harness_v20/object/near_solve_parts"
_UNIT = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}


# --------------------------------------------------------------------------
# Candidate 1: periodic_continue
# --------------------------------------------------------------------------

def self_period(cell_colors, axis):
    """Smallest p>=1 such that translating the object by p along `axis`
    agrees with itself EXACTLY on the overlap of the two bboxes -- occupancy
    AND color (a cell present in one and absent in the other is a mismatch).
    None when no period shorter than the object's own extent exists."""
    i = 0 if axis == "v" else 1
    rs = [c[0] for c in cell_colors]; cs = [c[1] for c in cell_colors]
    r0, r1, c0, c1 = min(rs), max(rs), min(cs), max(cs)
    extent = (r1 - r0 + 1) if i == 0 else (c1 - c0 + 1)
    for p in range(1, extent):
        shifted = {}
        for (r, c), col in cell_colors.items():
            shifted[(r + p, c) if i == 0 else (r, c + p)] = col
        # overlap region = intersection of the two bboxes
        if i == 0:
            lo, hi = max(r0, r0 + p), min(r1, r1 + p)
            region = [(r, c) for r in range(lo, hi + 1)
                      for c in range(c0, c1 + 1)]
        else:
            lo, hi = max(c0, c0 + p), min(c1, c1 + p)
            region = [(r, c) for r in range(r0, r1 + 1)
                      for c in range(lo, hi + 1)]
        if not region:
            continue
        if all(cell_colors.get(k) == shifted.get(k) for k in region) and \
                any(k in cell_colors for k in region):
            return p
    return None


def bbox_extent(cell_colors, axis):
    i = 0 if axis == "v" else 1
    vals = [c[i] for c in cell_colors]
    return max(vals) - min(vals) + 1


def periodic_continue(cell_colors, direction, bounds, period_src="auto"):
    """Added cells: the object repeated in `direction` at a derived period,
    continued until wholly out of bounds.  Fully relational."""
    if direction not in _UNIT:
        return None
    dr, dc = _UNIT[direction]
    axis = "v" if dr else "h"
    p = None
    if period_src in ("auto", "self"):
        p = self_period(cell_colors, axis)
    if p is None and period_src in ("auto", "bbox"):
        p = bbox_extent(cell_colors, axis)
    if not p:
        return None
    h, w = bounds
    added = {}
    for k in range(1, max(h, w) // p + 2):
        any_in = False
        for (r, c), col in cell_colors.items():
            nr, nc = r + dr * k * p, c + dc * k * p
            if 0 <= nr < h and 0 <= nc < w:
                any_in = True
                if (nr, nc) not in cell_colors:
                    added[(nr, nc)] = int(col)
        if not any_in:
            break
    return added or None


# --------------------------------------------------------------------------
# Candidate 2: rect_frame
# --------------------------------------------------------------------------

def rect_frame(cell_colors, bounds, thickness_src="minority_count"):
    """Added cells: a solid rectangular ring around the object's bbox.
    thickness = the number of minority-color cells in the object; the ring
    color = that minority color.  Both DERIVED, no literals."""
    if not cell_colors:
        return None
    counts = collections.Counter(cell_colors.values())
    if len(counts) != 2:
        return None
    (maj, _), (minor, n_minor) = counts.most_common()
    if thickness_src != "minority_count":
        return None
    t = int(n_minor)
    if t < 1:
        return None
    rs = [r for r, _ in cell_colors]; cs = [c for _, c in cell_colors]
    r0, r1, c0, c1 = min(rs), max(rs), min(cs), max(cs)
    h, w = bounds
    added = {}
    for r in range(r0 - t, r1 + t + 1):
        for c in range(c0 - t, c1 + t + 1):
            if r0 <= r <= r1 and c0 <= c <= c1:
                continue
            if not (0 <= r < h and 0 <= c < w):
                return None      # ring would fall off the grid: undefined
            added[(r, c)] = int(minor)
    return added or None


# --------------------------------------------------------------------------

def run():
    from geocat_arc.perception.grid import Grid
    from geocat_arc.object_reasoning.segmentation import evaluate_variant
    from geocat_arc.object_reasoning.correspondence import (
        match_pair, extract_deltas)
    from geocat_arc.object_reasoning.types import (
        DeltaType, SegmentationVariant, cell_colors_of)

    chal = json.load(open(Path(PROJECT_ROOT) /
                          "data/arc/arc-agi_training_challenges.json"))
    report = []
    for tid in EXEMPLARS:
        pairs = [(Grid.from_list(q["input"]), Grid.from_list(q["output"]))
                 for q in chal[tid]["train"]]
        best = None
        for variant in [v.value for v in SegmentationVariant]:
            try:
                seg = evaluate_variant(SegmentationVariant(variant), pairs)
            except Exception:
                continue
            hits = collections.Counter()
            total = 0
            for pi, (gi, go) in enumerate(pairs):
                try:
                    corr = match_pair(seg.input_objects[pi],
                                      seg.output_objects[pi], gi, go,
                                      pair_index=pi)[0]
                except Exception:
                    continue
                in_by = {o.id: o for o in corr.input_objects}
                out_by = {o.id: o for o in corr.output_objects}
                bounds = (gi.height, gi.width)
                for d in extract_deltas(corr):
                    if d.delta_type is not DeltaType.GROW:
                        continue
                    if d.params.get("mode") != "pattern":
                        continue
                    src_cc = cell_colors_of(in_by[d.input_object_id])
                    dst_cc = cell_colors_of(out_by[d.output_object_ids[0]])
                    added = {c: v for c, v in dst_cc.items()
                             if c not in src_cc}
                    if not added:
                        continue
                    total += 1
                    named = None
                    for direction in ("up", "down", "left", "right"):
                        for psrc in ("self", "bbox"):
                            if periodic_continue(src_cc, direction, bounds,
                                                 psrc) == added:
                                named = f"periodic:{direction}:{psrc}"
                                break
                        if named:
                            break
                    if named is None and rect_frame(src_cc, bounds) == added:
                        named = "rect_frame:minority_count"
                    hits[named or "UNEXPLAINED"] += 1
            if total == 0:
                continue
            score = total - hits["UNEXPLAINED"]
            if best is None or (score, -hits["UNEXPLAINED"]) > best[0]:
                best = ((score, -hits["UNEXPLAINED"]), variant, total,
                        dict(hits))
        if best is None:
            print(f"{tid}: no pattern deltas under any variant")
            report.append({"task_id": tid, "best": None})
            continue
        _, variant, total, hits = best
        flag = "  <== FULLY EXPLAINED" if hits.get("UNEXPLAINED", 0) == 0 \
            else ""
        print(f"{tid} best={variant} pattern_deltas={total} {hits}{flag}")
        report.append({"task_id": tid, "best_variant": variant,
                       "n_pattern_deltas": total, "hits": hits})
    outp = Path(PROJECT_ROOT) / "outputs/r19_trace/mode_falsification.json"
    outp.parent.mkdir(parents=True, exist_ok=True)
    json.dump(report, open(outp, "w"), indent=1)
    print(f"\nwrote {outp}")


if __name__ == "__main__":
    run()
