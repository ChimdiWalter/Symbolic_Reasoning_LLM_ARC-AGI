#!/usr/bin/env python3
"""Diagnose orphan COPY deltas (round-2 lever 1 scoping).

For every matching-stage death in the 1000-scale probe set, re-run
segmentation + correspondence and classify each orphan output object by the
cheapest generic explanation that reproduces its mask/pattern from some
input object: rot90/180/270, flipH/V, transpose, scale up/down (integer),
recolored exact shape, union-of-inputs, subshape-of-input, or NONE
(genuinely drawn).  Prints a per-task and aggregate histogram — this decides
which generic attribution passes are worth implementing.
"""
import json
import sys
from collections import Counter

import numpy as np

sys.path.insert(0, ".")
from geocat_arc.perception.grid import Grid
from geocat_arc.object_reasoning.segmentation import evaluate_variant
from geocat_arc.object_reasoning.correspondence import match_pair, extract_deltas
from geocat_arc.object_reasoning.types import DeltaType, SegmentationVariant

TASKS = {  # task -> seg variant chosen in the probe run
    "103eff5b": "S3", "2b01abd0": "S2", "2de01db2": "S6", "3906de3d": "S3",
    "56dc2b01": "S3", "760b3cac": "S5", "87ab05b8": "S5", "9565186b": "S6",
    "98c475bf": "S6", "df8cc377": "S4", "e40b9e2f": "S2", "f25ffba3": "S1",
    "97239e3d": "S6", "99306f82": "S6", "e69241bd": "S2", "b782dc8a": "S6",
}

chal = json.load(open("data/arc/arc-agi_training_challenges.json"))


def mask_of(obj):
    return np.array(obj.shape_signature, dtype=int)


def pattern_of(obj):
    r0, c0, _, _ = obj.bounding_box
    return {(r - r0, c - c0): obj.cell_colors[(r, c)] for (r, c) in obj.cells}


def classify(out_obj, in_objs):
    """Cheapest generic explanation of out_obj from any input object."""
    om = mask_of(out_obj)
    ocolors = {out_obj.color}
    xforms = [
        ("rot90", lambda m: np.rot90(m, 1)), ("rot180", lambda m: np.rot90(m, 2)),
        ("rot270", lambda m: np.rot90(m, 3)), ("flipH", np.fliplr),
        ("flipV", np.flipud), ("transpose", lambda m: m.T),
        ("anti_transpose", lambda m: np.rot90(m, 2).T),
    ]
    for a in in_objs:
        am = mask_of(a)
        # recolored exact shape (mask equal, colors differ)
        if am.shape == om.shape and np.array_equal(am, om):
            return "recolor_same_shape"
    for name, f in xforms:
        for a in in_objs:
            if np.array_equal(f(mask_of(a)), om):
                return f"xform_{name}"
    # integer scale
    for a in in_objs:
        am = mask_of(a)
        for k in (2, 3, 4):
            if am.shape[0] * k == om.shape[0] and am.shape[1] * k == om.shape[1]:
                if np.array_equal(np.kron(am, np.ones((k, k), dtype=int)), om):
                    return f"scale_up_{k}"
            if om.shape[0] * k == am.shape[0] and om.shape[1] * k == am.shape[1]:
                if np.array_equal(np.kron(om, np.ones((k, k), dtype=int)), am):
                    return f"scale_down_{k}"
    # subshape: out mask is a sub-window of some input mask (part of object)
    for a in in_objs:
        am = mask_of(a)
        if am.shape[0] >= om.shape[0] and am.shape[1] >= om.shape[1]:
            for r in range(am.shape[0] - om.shape[0] + 1):
                for c in range(am.shape[1] - om.shape[1] + 1):
                    if np.array_equal(am[r:r + om.shape[0], c:c + om.shape[1]], om):
                        return "subshape_of_input"
    # single-color rectangle / line (drawable primitives)
    if len(ocolors) == 1:
        if om.all():
            return "solid_rect"
        if om.shape[0] == 1 or om.shape[1] == 1:
            return "line"
    return "NONE"


agg = Counter()
for tid, var in TASKS.items():
    t = chal[tid]
    pairs = [(Grid.from_list(p["input"]), Grid.from_list(p["output"]))
             for p in t["train"]]
    seg = evaluate_variant(SegmentationVariant(var), pairs)
    per = Counter()
    for i, (gi, go) in enumerate(pairs):
        ins, outs = seg.input_objects[i], seg.output_objects[i]
        corrs = match_pair(ins, outs, gi, go, pair_index=i)
        corr = corrs[0]
        for d in extract_deltas(corr):
            if d.delta_type is DeltaType.COPY and d.input_object_id is None:
                out_obj = {o.id: o for o in corr.output_objects}[d.output_object_ids[0]]
                per[classify(out_obj, ins)] += 1
    agg.update(per)
    print(f"{tid} ({var}): {dict(per)}")
print("\nAGGREGATE over orphan copies:", dict(agg.most_common()))
