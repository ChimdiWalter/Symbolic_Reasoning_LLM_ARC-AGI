#!/usr/bin/env python3
"""R19 TRACE: what is the memorized GROW pattern a FUNCTION OF?

For each extensional_pattern exemplar: load the near-solve program's
segmentation variant, recompute per-pair object correspondence, isolate the
GROW deltas whose detected mode is `pattern` (the memorizers), and test
structural hypotheses against the ADDED cell set:

  H_self      added mask == the source object's own mask, stamped at some offset
  H_reflect   added == a reflection/rotation of the source object
  H_scene     added mask == some OTHER input object's mask (stamped)
  H_period    added == periodic continuation of the source at its own bbox period
  H_bbox      added fills the source's bbox / a container's interior
  H_grid      added is a sub-region of the input grid (copy of scene content)

Usage:
    python3 scripts/trace_r19_pattern.py [--tasks a,b,c] [--show]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = os.environ.get(
    "ARC_PROJECT_ROOT",
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

import numpy as np  # noqa: E402

EXEMPLARS = ["95755ff2", "5c0a986e", "575b1a71", "31adaf00", "9b30e358",
             "fcc82909", "ecdecbb3", "aa300dc3", "55059096", "c62e2108",
             "52fd389e", "9772c176", "c4d1a9ae", "d8c310e9", "e5062a87"]

NEAR_SOLVE = Path(PROJECT_ROOT) / "outputs/unified_harness_v20/object/near_solve_parts"


def load_challenges():
    p = Path(PROJECT_ROOT) / "data/arc/arc-agi_training_challenges.json"
    with open(p) as f:
        return json.load(f)


def best_near_solve(tid):
    p = NEAR_SOLVE / f"{tid}.jsonl"
    if not p.exists():
        return None
    best = None
    for line in open(p):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if best is None or r.get("train_fit_pixels", 0) > best.get("train_fit_pixels", 0):
            best = r
    return best


def show(g, label=""):
    a = np.asarray(g)
    print(f"  {label} {a.shape}")
    for row in a:
        print("   " + "".join(str(int(v)) if v else "." for v in row))


def mask_of(cells):
    rs = [r for r, _ in cells]
    cs = [c for _, c in cells]
    r0, c0 = min(rs), min(cs)
    return frozenset((r - r0, c - c0) for r, c in cells), (r0, c0)


def dihedral_masks(mask):
    """All 8 dihedral images of a normalized mask, normalized."""
    out = {}
    cur = set(mask)
    for flip in (False, True):
        m = {(r, -c) for r, c in mask} if flip else set(mask)
        for k in range(4):
            # rot90 CCW: (r,c) -> (-c, r)
            m2 = set(m)
            for _ in range(k):
                m2 = {(-c, r) for r, c in m2}
            nm, _ = mask_of(m2)
            out.setdefault(nm, (k, flip))
    return out


def analyze_task(tid, chal, verbose=False):
    from geocat_arc.perception.grid import Grid
    from geocat_arc.object_reasoning.segmentation import evaluate_variant
    from geocat_arc.object_reasoning.correspondence import (
        match_pair, extract_deltas)
    from geocat_arc.object_reasoning.types import (
        DeltaType, SegmentationVariant, cell_colors_of)

    rec = best_near_solve(tid)
    variant = (rec or {}).get("segmentation_variant", "S1")
    task = chal[tid]
    pairs = [(Grid.from_list(p["input"]), Grid.from_list(p["output"]))
             for p in task["train"]]
    seg = evaluate_variant(SegmentationVariant(variant), pairs)

    findings = {"task_id": tid, "variant": variant, "n_pairs": len(pairs),
                "pattern_deltas": [], "hyp_counts": {}}

    for pi, (gi, go) in enumerate(pairs):
        ins, outs = seg.input_objects[pi], seg.output_objects[pi]
        corr = match_pair(ins, outs, gi, go, pair_index=pi)[0]
        in_by = {o.id: o for o in corr.input_objects}
        out_by = {o.id: o for o in corr.output_objects}
        for d in extract_deltas(corr):
            if d.delta_type is not DeltaType.GROW:
                continue
            if d.params.get("mode") != "pattern":
                continue
            src = in_by[d.input_object_id]
            dst = out_by[d.output_object_ids[0]]
            src_cc = cell_colors_of(src)
            dst_cc = cell_colors_of(dst)
            added = {c: v for c, v in dst_cc.items() if c not in src_cc}
            if not added:
                continue
            entry = analyze_added(tid, pi, gi, src_cc, added, ins, in_by)
            findings["pattern_deltas"].append(entry)
            for h in entry["hyps"]:
                findings["hyp_counts"][h] = findings["hyp_counts"].get(h, 0) + 1
            if verbose:
                print(f"  pair {pi} obj {src.id}: |src|={len(src_cc)} "
                      f"|added|={len(added)} hyps={entry['hyps']}")
    return findings


def analyze_added(tid, pi, gi, src_cc, added, all_in_objs, in_by):
    """Test structural hypotheses about what `added` is a function of."""
    hyps = []
    detail = {}
    src_cells = set(src_cc)
    src_mask, src_org = mask_of(src_cells)
    add_mask, add_org = mask_of(set(added))

    # H_self: added mask == source mask (a stamped copy of the object itself)
    if add_mask == src_mask:
        hyps.append("self_stamp")
        detail["self_offset"] = (add_org[0] - src_org[0], add_org[1] - src_org[1])
        # colors carried?
        same = all(added[(add_org[0] + r, add_org[1] + c)] ==
                   src_cc[(src_org[0] + r, src_org[1] + c)]
                   for r, c in src_mask)
        detail["self_colors_carried"] = bool(same)

    # H_reflect: added mask is a dihedral image of the source mask
    dih = dihedral_masks(src_mask)
    if add_mask in dih and add_mask != src_mask:
        hyps.append("self_dihedral")
        detail["dihedral"] = dih[add_mask]

    # H_scene: added mask == another input object's mask
    for o in all_in_objs:
        if o.cells == src_cells or not o.cells:
            continue
        om, oorg = mask_of(o.cells)
        if om == add_mask:
            hyps.append("other_object_stamp")
            detail.setdefault("other_ids", []).append(int(o.id))
        elif add_mask in dihedral_masks(om):
            hyps.append("other_object_dihedral")
            detail.setdefault("other_dih_ids", []).append(int(o.id))

    # H_bbox_fill: added == the complement of source within its own bbox
    rs = [r for r, _ in src_cells]; cs = [c for _, c in src_cells]
    r0, r1, c0, c1 = min(rs), max(rs), min(cs), max(cs)
    bbox_rest = {(r, c) for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)
                 if (r, c) not in src_cells}
    if bbox_rest and set(added) == bbox_rest:
        hyps.append("bbox_fill")

    # H_grid: added's colored patch matches a sub-region of the INPUT grid
    #         elsewhere (scene content copied)
    ah, aw = (max(r for r, _ in added) - min(r for r, _ in added) + 1,
              max(c for _, c in added) - min(c for _, c in added) + 1)
    arr = gi.to_numpy()
    gh, gw = arr.shape
    patch = {}
    for (r, c), v in added.items():
        patch[(r - add_org[0], c - add_org[1])] = v
    hits = []
    if ah <= gh and aw <= gw:
        for rr in range(gh - ah + 1):
            for cc in range(gw - aw + 1):
                if (rr, cc) == add_org:
                    continue
                if all(int(arr[rr + dr, cc + dc]) == v
                       for (dr, dc), v in patch.items()):
                    hits.append((rr, cc))
    if hits:
        hyps.append("grid_subregion_copy")
        detail["grid_hits"] = hits[:6]

    # H_period: added cells are the source translated by k*(bbox size)
    bh, bw = r1 - r0 + 1, c1 - c0 + 1
    per_hit = []
    for k in range(-4, 5):
        for axis, vec in (("v", (k * bh, 0)), ("h", (0, k * bw))):
            if k == 0:
                continue
            moved = {(r + vec[0], c + vec[1]) for r, c in src_cells}
            if moved and moved <= set(added):
                per_hit.append((axis, k))
    if per_hit:
        hyps.append("periodic_tile")
        detail["periods"] = per_hit

    # Structural summary of the added set even when no hypothesis fires
    detail["n_added"] = len(added)
    detail["n_src"] = len(src_cc)
    detail["added_colors"] = sorted(set(added.values()))
    detail["src_colors"] = sorted(set(src_cc.values()))
    detail["added_bbox_hw"] = [ah, aw]
    detail["src_bbox_hw"] = [bh, bw]
    detail["added_touches_border"] = bool(
        any(r in (0, gh - 1) or c in (0, gw - 1) for r, c in added))
    # is the added set contiguous with the source?
    detail["added_adjacent_to_src"] = bool(any(
        (r + dr, c + dc) in src_cells
        for r, c in added for dr in (-1, 0, 1) for dc in (-1, 0, 1)))
    if not hyps:
        hyps.append("UNNAMED")
    return {"pair": pi, "hyps": hyps, "detail": detail}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", default=",".join(EXEMPLARS))
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--out", default="outputs/r19_trace/trace.json")
    args = ap.parse_args()

    chal = load_challenges()
    tids = [t for t in args.tasks.split(",") if t]
    results = []
    for tid in tids:
        print(f"\n=== {tid} ===")
        if args.show:
            for i, p in enumerate(chal[tid]["train"]):
                show(p["input"], f"pair{i} IN")
                show(p["output"], f"pair{i} OUT")
        try:
            f = analyze_task(tid, chal, verbose=True)
        except Exception as e:
            print(f"  ERROR {type(e).__name__}: {e}")
            results.append({"task_id": tid, "error": f"{type(e).__name__}: {e}"})
            continue
        print(f"  variant={f['variant']} pattern_deltas={len(f['pattern_deltas'])} "
              f"hyps={f['hyp_counts']}")
        for e in f["pattern_deltas"]:
            print(f"    pair{e['pair']} {e['hyps']} {json.dumps(e['detail'])}")
        results.append(f)

    outp = Path(PROJECT_ROOT) / args.out
    outp.parent.mkdir(parents=True, exist_ok=True)
    with open(outp, "w") as fh:
        json.dump(results, fh, indent=1)
    print(f"\nwrote {outp}")


if __name__ == "__main__":
    main()
