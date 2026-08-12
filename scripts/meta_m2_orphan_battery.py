#!/usr/bin/env python3
"""META-INDUCTION M2 pre-synthesis: construction battery for the
orphan-copy family (124 tasks, the top M1 pattern).

For every orphan output object (created, no canonical-shape twin among
inputs) in the family's tasks, test a battery of GENERIC constructions
that could produce it from the input scene:

  scaled_input      — integer up/down-scale of some input object's mask
  pair_union        — union of TWO input objects' cells (translated)
  input_subshape    — a connected sub-window of an input object
  bbox_fill         — the filled bbox of some input object (translated)
  bbox_outline      — the bbox ring of some input object (translated)
  line_between      — a straight segment whose endpoints touch two input
                      objects' bboxes
  grid_motif        — equals a color-connected component of the INPUT GRID
                      under a DIFFERENT segmentation (S3 multicolor scene)
                      -> segmentation-choice residue, not a new verb
  none              — unexplained (true synthesis targets)

The histogram decides which verb(s) M2 synthesizes first.
Output: outputs/meta_m2_orphan_battery.json
"""
import json
import sys
from collections import Counter

import numpy as np

sys.path.insert(0, ".")
from geocat_arc.perception.grid import Grid
from geocat_arc.object_reasoning.segmentation import evaluate_variant
from geocat_arc.object_reasoning.correspondence import match_pair, extract_deltas
from geocat_arc.object_reasoning.types import SegmentationVariant

chal = json.load(open("data/arc/arc-agi_training_challenges.json"))
try:
    chal.update(json.load(open("data/arc/arc-agi_evaluation_challenges.json")))
except Exception:
    pass

m1 = json.load(open("outputs/meta_m1_residual_patterns.json"))
# recover the family tasks: rows whose near-solve carries unexplained copy@matching
import glob
import os
family = {}
for run in ("outputs/unified_harness_v8", "outputs/unified_harness_emit_training",
            "outputs/unified_harness_emit_evaluation"):
    for f in glob.glob(f"{run}/object/near_solve_parts/*.jsonl"):
        tid = os.path.basename(f)[:-6]
        if tid in family:
            continue
        try:
            r = json.loads(open(f).readline())
        except Exception:
            continue
        if r.get("failure_stage") != "matching":
            continue
        if any(u.get("delta_type") == "copy"
               for u in (r.get("residual") or {}).get("unexplained_deltas") or []):
            family[tid] = r.get("segmentation_variant") or "S1"
print(f"orphan-copy family tasks: {len(family)}", flush=True)


def canon_masks(m):
    a = np.array(m, dtype=int)
    forms = [a, np.rot90(a, 1), np.rot90(a, 2), np.rot90(a, 3)]
    forms += [np.fliplr(x) for x in forms]
    return {tuple(map(tuple, x.tolist())) for x in forms}


def mask_of(o):
    return np.array(o.shape_signature, dtype=int)


def classify(orph, ins, gi):
    om = mask_of(orph)
    ocan = canon_masks(om)
    # scaled input
    for a in ins:
        am = mask_of(a)
        for k in (2, 3, 4):
            up = np.kron(am, np.ones((k, k), dtype=int))
            if tuple(map(tuple, up.tolist())) in ocan:
                return "scaled_input"
            if am.shape[0] % k == 0 and am.shape[1] % k == 0:
                dn = am[::k, ::k]
                if tuple(map(tuple, dn.tolist())) in ocan:
                    return "scaled_input"
    # bbox fill / outline
    for a in ins:
        h, w = a.bbox_height, a.bbox_width
        if (h, w) == om.shape and om.all():
            return "bbox_fill"
        ring = np.zeros((h, w), dtype=int)
        if h >= 2 and w >= 2:
            ring[0, :] = ring[-1, :] = 1
            ring[:, 0] = ring[:, -1] = 1
            if ring.shape == om.shape and np.array_equal(ring, om):
                return "bbox_outline"
    # line between two inputs
    if om.shape[0] == 1 or om.shape[1] == 1:
        cells = orph.cells
        ends = [min(cells), max(cells)]
        near = 0
        for a in ins:
            r0, c0, r1, c1 = a.bounding_box
            for (r, c) in ends:
                if r0 - 1 <= r <= r1 and c0 - 1 <= c <= c1:
                    near += 1
                    break
        if near >= 2:
            return "line_between"
    # pair union (translated): try all input pairs, align by orphan bbox
    oc = {(r - orph.bounding_box[0], c - orph.bounding_box[1])
          for (r, c) in orph.cells}
    per_obj = []
    for a in ins:
        per_obj.append({(r - a.bounding_box[0], c - a.bounding_box[1])
                        for (r, c) in a.cells})
    for i in range(len(per_obj)):
        for j in range(i + 1, len(per_obj)):
            A, B = per_obj[i], per_obj[j]
            if len(A) + len(B) < len(oc):
                continue
            # search small relative offsets of B against A
            for dr in range(-6, 7):
                for dc in range(-6, 7):
                    u = A | {(r + dr, c + dc) for (r, c) in B}
                    rs = min(r for r, _ in u)
                    cs = min(c for _, c in u)
                    if {(r - rs, c - cs) for (r, c) in u} == oc:
                        return "pair_union"
    # grid motif under multicolor segmentation
    try:
        from geocat_arc.object_reasoning.segmentation import segment, background_for
        bg = background_for(gi, SegmentationVariant("S3"))
        for o3 in segment(gi, SegmentationVariant("S3"), bg):
            if canon_masks(mask_of(o3)) & ocan:
                return "grid_motif"
    except Exception:
        pass
    # input subshape
    for a in ins:
        am = mask_of(a)
        oh, ow = om.shape
        if am.shape[0] >= oh and am.shape[1] >= ow:
            for r in range(am.shape[0] - oh + 1):
                for c in range(am.shape[1] - ow + 1):
                    if np.array_equal(am[r:r + oh, c:c + ow], om):
                        return "input_subshape"
    return "none"


agg = Counter()
per_task = {}
for n, (tid, var) in enumerate(sorted(family.items())):
    try:
        pairs = [(Grid.from_list(p["input"]), Grid.from_list(p["output"]))
                 for p in chal[tid]["train"]]
        seg = evaluate_variant(SegmentationVariant(var), pairs)
        kinds = Counter()
        for pi, (gi, go) in enumerate(pairs):
            ins, outs = seg.input_objects[pi], seg.output_objects[pi]
            corr = match_pair(ins, outs, gi, go, pair_index=pi)[0]
            out_by = {o.id: o for o in corr.output_objects}
            for d in extract_deltas(corr):
                if d.input_object_id is None and d.output_object_ids:
                    o = out_by[d.output_object_ids[0]]
                    kinds[classify(o, ins, gi)] += 1
        per_task[tid] = dict(kinds)
        agg.update(kinds)
    except Exception as e:
        per_task[tid] = {"error": f"{type(e).__name__}: {e}"}
        agg["diag_error"] += 1
    if (n + 1) % 20 == 0:
        print(f"  {n+1}/{len(family)}", flush=True)

json.dump({"aggregate": dict(agg.most_common()), "per_task": per_task},
          open("outputs/meta_m2_orphan_battery.json", "w"), indent=1)
print("AGGREGATE:", dict(agg.most_common()))
print("report -> outputs/meta_m2_orphan_battery.json")
