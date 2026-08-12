#!/usr/bin/env python3
"""Round-4 lever-3 scoping: what ARE the adjacent orphans?

Over the orphan_adj-dominant matching-death tasks (v6 census), classify
every orphan output object that touches a matched object:

  connector    — a line/rect of uniform color whose endpoints touch TWO
                 different matched objects (bridge-drawing family)
  appendage    — touches exactly ONE matched object (mark/flag/extension
                 that segmentation carved separately; near-GROW family)
  twin_shape   — same canonical shape as its touched neighbour (satellite
                 copy adjacency)
  other

Also record per orphan: size, uniform color?, line?, touched-object count.
Aggregate decides the generic fix (e.g. an ATTACH delta: orphan attributed
to its touched object as a satellite with relative placement).
"""
import json
import sys
from collections import Counter

sys.path.insert(0, ".")
from geocat_arc.perception.grid import Grid
from geocat_arc.object_reasoning.segmentation import evaluate_variant
from geocat_arc.object_reasoning.correspondence import match_pair, extract_deltas
from geocat_arc.object_reasoning.types import SegmentationVariant

chal = json.load(open("data/arc/arc-agi_training_challenges.json"))
rep = json.load(open("outputs/matching_deaths_v6.json"))
targets = {}
for t, d in rep["per_task"].items():
    k = d.get("kinds") or {}
    if k and max(k.items(), key=lambda kv: kv[1])[0] == "orphan_adj":
        targets[t] = d["variant"]
print(f"orphan_adj-dominant tasks: {len(targets)}", flush=True)


def _touches(a_cells, b_cells):
    return any((r + dr, c + dc) in b_cells
               for (r, c) in a_cells
               for dr in (-1, 0, 1) for dc in (-1, 0, 1))


def _canon(o):
    import numpy as np
    m = np.array(o.shape_signature, dtype=int)
    forms = [m, np.rot90(m, 1), np.rot90(m, 2), np.rot90(m, 3)]
    forms += [np.fliplr(f) for f in forms]
    return min(tuple(map(tuple, f.tolist())) for f in forms)


agg = Counter()
per_task = {}
for i, (tid, var) in enumerate(sorted(targets.items())):
    try:
        pairs = [(Grid.from_list(p["input"]), Grid.from_list(p["output"]))
                 for p in chal[tid]["train"]]
        seg = evaluate_variant(SegmentationVariant(var), pairs)
        kinds = Counter()
        for pi, (gi, go) in enumerate(pairs):
            ins, outs = seg.input_objects[pi], seg.output_objects[pi]
            corr = match_pair(ins, outs, gi, go, pair_index=pi)[0]
            out_by = {o.id: o for o in corr.output_objects}
            matched_out = {oid for _, oid, _ in corr.matches} | \
                          {oid for v in corr.copies.values() for oid in v}
            matched_objs = [out_by[oid] for oid in matched_out
                            if oid in out_by]
            for d in extract_deltas(corr):
                if d.input_object_id is not None or not d.output_object_ids:
                    continue
                o = out_by[d.output_object_ids[0]]
                touched = [m for m in matched_objs
                           if _touches(o.cells, m.cells)]
                if not touched:
                    kinds["free"] += 1
                    continue
                uniform = True  # single-color objects in most variants
                is_line = (o.bbox_height == 1 or o.bbox_width == 1)
                if len(touched) >= 2 and is_line:
                    kinds["connector"] += 1
                elif any(_canon(o) == _canon(m) for m in touched):
                    kinds["twin_shape"] += 1
                elif len(touched) == 1:
                    kinds[f"appendage{'_line' if is_line else ''}"] += 1
                else:
                    kinds["other_multi_touch"] += 1
        per_task[tid] = dict(kinds)
        agg.update(kinds)
    except Exception as e:
        per_task[tid] = {"error": f"{type(e).__name__}: {e}"}
        agg["diag_error"] += 1
    if (i + 1) % 10 == 0:
        print(f"  {i+1}/{len(targets)}", flush=True)

json.dump({"aggregate": dict(agg.most_common()), "per_task": per_task},
          open("outputs/orphan_adj_diagnosis.json", "w"), indent=1)
print("\nAGGREGATE:", dict(agg.most_common()))
print("report -> outputs/orphan_adj_diagnosis.json")
