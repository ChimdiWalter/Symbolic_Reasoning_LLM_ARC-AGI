#!/usr/bin/env python3
"""Round-4 probe: are merge-dominant matching deaths a SEGMENTATION-CHOICE
problem?  For each merge-dominant task, count merge instances under EVERY
segmentation variant; report the min-merge variant vs the recorded one.
If min-merge is often 0 at some other variant, the fix is coherence scoring
(consistent granularity), not a new MERGE delta."""
import json
import sys
from collections import Counter

sys.path.insert(0, ".")
from geocat_arc.perception.grid import Grid
from geocat_arc.object_reasoning.segmentation import (evaluate_variant,
                                                      SEGMENTATION_TRIAL_ORDER)
from geocat_arc.object_reasoning.correspondence import match_pair
from geocat_arc.object_reasoning.types import SegmentationVariant

chal = json.load(open("data/arc/arc-agi_training_challenges.json"))
rep = json.load(open("outputs/matching_deaths_v6.json"))
targets = [t for t, d in rep["per_task"].items()
           if (d.get("kinds") or {}).get("merge")
           and max((d["kinds"]).items(), key=lambda kv: kv[1])[0] == "merge"]
print(f"merge-dominant tasks: {len(targets)}", flush=True)

summary = Counter()
rows = {}
for i, tid in enumerate(sorted(targets)):
    pairs = [(Grid.from_list(p["input"]), Grid.from_list(p["output"]))
             for p in chal[tid]["train"]]
    best = None
    per_variant = {}
    for var in SEGMENTATION_TRIAL_ORDER:
        try:
            seg = evaluate_variant(var, pairs)
            merges = 0
            for pi, (gi, go) in enumerate(pairs):
                ins, outs = seg.input_objects[pi], seg.output_objects[pi]
                for o in outs:
                    if len({a.id for a in ins if a.cells & o.cells}) > 1:
                        merges += 1
            per_variant[str(var.value if hasattr(var, "value") else var)] = \
                {"merges": merges, "coherent": bool(seg.coherent)}
            if best is None or merges < best[1]:
                best = (str(var.value if hasattr(var, "value") else var),
                        merges)
        except Exception:
            pass
    rows[tid] = {"recorded": rep["per_task"][tid]["variant"],
                 "best_variant": best[0] if best else None,
                 "best_merges": best[1] if best else None,
                 "per_variant": per_variant}
    if best:
        summary["zero_merge_variant_exists" if best[1] == 0
                else "all_variants_merge"] += 1
    if (i + 1) % 10 == 0:
        print(f"  {i+1}/{len(targets)}", flush=True)

json.dump({"summary": dict(summary), "tasks": rows},
          open("outputs/probe_merge_variants.json", "w"), indent=1)
print("SUMMARY:", dict(summary))
print("report -> outputs/probe_merge_variants.json")
