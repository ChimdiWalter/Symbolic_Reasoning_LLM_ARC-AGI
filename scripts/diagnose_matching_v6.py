#!/usr/bin/env python3
"""Round-4 lever-1 scoping: classify ALL v6 matching-stage deaths.

For every near-solve row with failure_stage == 'matching' in the v6 run,
re-run segmentation (the recorded variant) + best correspondence and
classify each unexplained element:

  matched-with-residual ->  grow / shrink / reshape / disjoint
                            (grow should be rare now — GROW handles it;
                             what remains is the round-4 target)
  orphan outputs        ->  orphan_adj / orphan_free (near a matched object?)
  merges                ->  one output object covering >1 input objects'
                            cells (segmentation-relation failure)
  splits                ->  one input object's cells split over >1 outputs
  lossy-only            ->  correspondence lossy with none of the above

Writes outputs/matching_deaths_v6.json (per-task + aggregate) and prints
the aggregate histogram — the round-4 implementation decision input.
"""
import json
import glob
import os
import sys
from collections import Counter

import numpy as np

sys.path.insert(0, ".")
from geocat_arc.perception.grid import Grid
from geocat_arc.object_reasoning.segmentation import evaluate_variant
from geocat_arc.object_reasoning.correspondence import match_pair, extract_deltas
from geocat_arc.object_reasoning.types import SegmentationVariant

chal = json.load(open("data/arc/arc-agi_training_challenges.json"))

tasks = {}
for f in glob.glob("outputs/unified_harness_v6/object/near_solve_parts/*.jsonl"):
    r = json.loads(open(f).readline())
    if r.get("failure_stage") == "matching":
        tasks[r["task_id"]] = r.get("segmentation_variant") or "S1"
print(f"matching-death tasks: {len(tasks)}", flush=True)

per_task = {}
agg = Counter()
for i, (tid, var) in enumerate(sorted(tasks.items())):
    try:
        pairs = [(Grid.from_list(p["input"]), Grid.from_list(p["output"]))
                 for p in chal[tid]["train"]]
        seg = evaluate_variant(SegmentationVariant(var), pairs)
        kinds = Counter()
        for pi, (gi, go) in enumerate(pairs):
            ins, outs = seg.input_objects[pi], seg.output_objects[pi]
            corr = match_pair(ins, outs, gi, go, pair_index=pi)[0]
            in_by = {o.id: o for o in corr.input_objects}
            out_by = {o.id: o for o in corr.output_objects}
            # merges / splits by cell coverage
            for o in outs:
                srcs = {a.id for a in ins if a.cells & o.cells}
                if len(srcs) > 1:
                    kinds["merge"] += 1
            for a in ins:
                dsts = {o.id for o in outs if o.cells & a.cells}
                if len(dsts) > 1:
                    kinds["split"] += 1
            for d in extract_deltas(corr):
                if d.residual_pixels <= 0:
                    continue
                if d.input_object_id is None:
                    o = out_by[d.output_object_ids[0]]
                    near = any(o.cells & {(r + dr, c + dc)
                                          for (r, c) in m.cells
                                          for dr in (-1, 0, 1)
                                          for dc in (-1, 0, 1)}
                               for m in ins)
                    kinds["orphan_adj" if near else "orphan_free"] += 1
                    continue
                a = in_by[d.input_object_id]
                o = out_by[d.output_object_ids[0]]
                dr = o.bounding_box[0] - a.bounding_box[0]
                dc = o.bounding_box[1] - a.bounding_box[1]
                ash = {(r + dr, c + dc) for (r, c) in a.cells}
                inter = ash & o.cells
                if not inter:
                    kinds["disjoint"] += 1
                elif ash <= o.cells:
                    kinds["grow_residual"] += 1     # slipped past GROW: why?
                elif o.cells <= ash:
                    kinds["shrink"] += 1
                else:
                    kinds["reshape"] += 1
        per_task[tid] = {"variant": var, "kinds": dict(kinds)}
        agg.update(kinds)
    except Exception as e:
        per_task[tid] = {"variant": var, "error": f"{type(e).__name__}: {e}"}
        agg["diag_error"] += 1
    if (i + 1) % 25 == 0:
        print(f"  {i+1}/{len(tasks)} done", flush=True)

os.makedirs("outputs", exist_ok=True)
json.dump({"aggregate": dict(agg.most_common()), "per_task": per_task},
          open("outputs/matching_deaths_v6.json", "w"), indent=1)
print("\nAGGREGATE:", dict(agg.most_common()))
print("report -> outputs/matching_deaths_v6.json")
