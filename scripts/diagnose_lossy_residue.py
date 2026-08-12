#!/usr/bin/env python3
"""Round-2 lever-1 scoping part 2: WHAT is the lossy residue?

For each probe task's best correspondence alternative: for every matched
(in,out) pair with residual pixels, classify the relationship:
  grow   — out cells ⊇ in cells (translated): object gained pixels
  shrink — out cells ⊆ in cells: object lost pixels
  reshape— overlap but neither containment
  disjoint — no overlap under best translation
For orphan outputs: size + color + adjacency to a matched object.
Aggregates across tasks: tells us which generic delta subtype pays.
"""
import json
import sys
from collections import Counter

sys.path.insert(0, ".")
from geocat_arc.perception.grid import Grid
from geocat_arc.object_reasoning.segmentation import evaluate_variant
from geocat_arc.object_reasoning.correspondence import match_pair, extract_deltas
from geocat_arc.object_reasoning.types import SegmentationVariant, DeltaType

TASKS = {
    "103eff5b": "S3", "2b01abd0": "S2", "2de01db2": "S6", "3906de3d": "S3",
    "56dc2b01": "S3", "760b3cac": "S5", "87ab05b8": "S5", "9565186b": "S6",
    "98c475bf": "S6", "df8cc377": "S4", "e40b9e2f": "S2", "f25ffba3": "S1",
    "97239e3d": "S6", "99306f82": "S6", "e69241bd": "S2", "b782dc8a": "S6",
}
chal = json.load(open("data/arc/arc-agi_training_challenges.json"))
agg = Counter()

for tid, var in TASKS.items():
    pairs = [(Grid.from_list(p["input"]), Grid.from_list(p["output"]))
             for p in chal[tid]["train"]]
    seg = evaluate_variant(SegmentationVariant(var), pairs)
    per = Counter()
    for i, (gi, go) in enumerate(pairs):
        ins, outs = seg.input_objects[i], seg.output_objects[i]
        corr = match_pair(ins, outs, gi, go, pair_index=i)[0]
        in_by = {o.id: o for o in corr.input_objects}
        out_by = {o.id: o for o in corr.output_objects}
        matched_cells = set()
        for d in extract_deltas(corr):
            if d.input_object_id is not None and d.output_object_ids:
                for oid in d.output_object_ids:
                    matched_cells |= out_by[oid].cells
            if d.residual_pixels <= 0:
                continue
            if d.input_object_id is None:
                o = out_by[d.output_object_ids[0]]
                near = any(o.cells & {(r + dr, c + dc)
                                      for (r, c) in m.cells
                                      for dr in (-1, 0, 1) for dc in (-1, 0, 1)}
                           for m in ins)
                per[f"orphan_{'adj' if near else 'free'}"] += 1
                continue
            a = in_by[d.input_object_id]
            o = out_by[d.output_object_ids[0]]
            # best alignment: bbox-origin shift
            dr = o.bounding_box[0] - a.bounding_box[0]
            dc = o.bounding_box[1] - a.bounding_box[1]
            ash = {(r + dr, c + dc) for (r, c) in a.cells}
            inter = ash & o.cells
            if not inter:
                per[f"{d.delta_type.value}_disjoint"] += 1
            elif ash <= o.cells:
                per[f"{d.delta_type.value}_grow(+{len(o.cells) - len(ash)})"] += 1
                agg["GROW"] += 1
            elif o.cells <= ash:
                per[f"{d.delta_type.value}_shrink(-{len(ash) - len(o.cells)})"] += 1
                agg["SHRINK"] += 1
            else:
                per[f"{d.delta_type.value}_reshape"] += 1
                agg["RESHAPE"] += 1
    for k, v in per.items():
        if k.startswith("orphan"):
            agg[k.upper()] += v
    print(f"{tid} ({var}): {dict(per)}")
print("\nAGGREGATE:", dict(agg.most_common()))
