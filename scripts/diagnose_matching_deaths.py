#!/usr/bin/env python3
"""Round-2 lever-1 scoping: WHY does each probe task die at stage=matching?

Mirrors _induce_candidate's flow on the seg variant the probe chose:
enumerate_labeled_tables -> _induce_on_table, then reports per alternative:
lossy? orphans? failed groups (stage + delta type + count)? render failure?
Aggregates the failure reasons across tasks so lever 1 targets the real gap.
"""
import json
import sys
import time
from collections import Counter

sys.path.insert(0, ".")
from geocat_arc.perception.grid import Grid
from geocat_arc.object_reasoning.segmentation import evaluate_variant
from geocat_arc.object_reasoning.types import SegmentationVariant
from geocat_arc.object_reasoning import inducer as I
from geocat_arc.object_reasoning.inducer import InductionConfig

TASKS = {
    "103eff5b": "S3", "2b01abd0": "S2", "2de01db2": "S6", "3906de3d": "S3",
    "56dc2b01": "S3", "760b3cac": "S5", "87ab05b8": "S5", "9565186b": "S6",
    "98c475bf": "S6", "df8cc377": "S4", "e40b9e2f": "S2", "f25ffba3": "S1",
    "97239e3d": "S6", "99306f82": "S6", "e69241bd": "S2", "b782dc8a": "S6",
}

chal = json.load(open("data/arc/arc-agi_training_challenges.json"))
config = InductionConfig()
agg = Counter()

for tid, var in TASKS.items():
    pairs = [(Grid.from_list(p["input"]), Grid.from_list(p["output"]))
             for p in chal[tid]["train"]]
    seg = evaluate_variant(SegmentationVariant(var), pairs)
    I.register_builtin_features()
    deadline = time.monotonic() + 60
    print(f"\n=== {tid} ({var}) ===")
    n_alt = 0
    for table, report in I.enumerate_labeled_tables(seg, pairs,
                                                    max_alternatives=4):
        n_alt += 1
        octx = I._octx(table)
        try:
            att = I._induce_on_table(seg, table, report, pairs, config,
                                     deadline, I._Meta())
        except Exception as e:
            print(f"  alt{n_alt}: INDUCE CRASH {type(e).__name__}: {str(e)[:100]}")
            agg["induce_crash"] += 1
            continue
        reasons = []
        if att.programs:
            reasons.append("TRAIN_PERFECT")
            agg["train_perfect_alt"] += 1
        if octx.lossy:
            px = sum(c.unreconciled_pixels for c in octx.corrs.values())
            reasons.append(f"lossy({px}px)")
            agg["lossy"] += 1
        if octx.orphans:
            reasons.append(f"orphans({len(octx.orphans)})")
            agg["orphans"] += 1
        failed = [u for u in att.unexplained if u.get("example_features")]
        for u in failed:
            agg[f"group_fail_{u['delta_type']}"] += 1
        if not att.programs and not octx.lossy and not octx.orphans and not failed:
            reasons.append("RENDER_FAILED_OR_RULECAP")
            agg["render_failed_or_rulecap"] += 1
        print(f"  alt{n_alt}: stage={att.stage} fit_obj={att.fit_objects:.2f} "
              f"fit_px={att.fit_pixels:.2f} reasons={reasons} "
              f"failed_groups={[(u['delta_type'], u['count']) for u in failed]}")
    if n_alt == 0:
        print("  NO ALTERNATIVES")
        agg["no_alternatives"] += 1

print("\nAGGREGATE:", dict(agg.most_common()))
