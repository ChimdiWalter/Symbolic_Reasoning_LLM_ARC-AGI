#!/usr/bin/env python3
"""Selector-death census (round-5 lever scoping; eval + training).

For each selector-stage death, rebuild the labeled table and, for every
FAILED delta group, test whether ANY single registered feature separates
the group's members from non-members (zero-conflict):

  separable_missed — an existing feature separates -> SEARCH DEFECT
                     (selector induction should have found it)
  needs_conjunction— separable only by 2-feature conjunction -> depth gap
  vocabulary_gap   — NO feature (or pair) separates -> the selector-feature
                     vocabulary cannot name the concept (meta-induction fuel)

Usage: diagnose_selector_deaths.py RUN_DIR SPLIT OUT_JSON
"""
import itertools
import json
import sys
import time
from collections import Counter

sys.path.insert(0, ".")
from geocat_arc.perception.grid import Grid
from geocat_arc.object_reasoning.segmentation import evaluate_variant
from geocat_arc.object_reasoning.types import SegmentationVariant
from geocat_arc.object_reasoning import inducer as I
from geocat_arc.object_reasoning.features import FEATURE_REGISTRY

run_dir, split, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
chal = json.load(open(f"data/arc/arc-agi_{split}_challenges.json"))

targets = {}
for line in open(f"{run_dir}/progress.jsonl"):
    d = json.loads(line)
    o = d.get("object") or {}
    if o.get("failure_stage") == "selector":
        targets[d["task_id"]] = o.get("seg_variant") or "S1"
print(f"selector-death tasks: {len(targets)}", flush=True)

I.register_builtin_features()
agg = Counter()
per_task = {}
for n, (tid, var) in enumerate(sorted(targets.items())):
    try:
        pairs = [(Grid.from_list(p["input"]), Grid.from_list(p["output"]))
                 for p in chal[tid]["train"]]
        seg = evaluate_variant(SegmentationVariant(var), pairs)
        table, report = next(I.enumerate_labeled_tables(seg, pairs,
                                                        max_alternatives=1))
        groups = I._tier_groups(table, split=False)
        rows = {(r.pair_index, r.object_id): r for r in table.rows}
        kinds = Counter()
        for gkey, g in groups.items():
            members = set(g["members"])
            others = set(rows) - members
            if not others:
                continue
            sep = None
            feat_vals = {}
            for name in sorted(FEATURE_REGISTRY):
                try:
                    mv = {rows[k].value(name) for k in members}
                    ov = {rows[k].value(name) for k in others}
                except Exception:
                    continue
                feat_vals[name] = (mv, ov)
                if not (mv & ov):
                    sep = name
                    break
            if sep:
                kinds[f"separable[{g['delta_type'].value}]"] += 1
                continue
            pair_sep = None
            names = sorted(feat_vals)
            for a, b in itertools.combinations(names, 2):
                mv = {(rows[k].value(a), rows[k].value(b)) for k in members}
                ov = {(rows[k].value(a), rows[k].value(b)) for k in others}
                if not (mv & ov):
                    pair_sep = (a, b)
                    break
            if pair_sep:
                kinds[f"conjunction[{g['delta_type'].value}]"] += 1
            else:
                kinds[f"VOCAB_GAP[{g['delta_type'].value}]"] += 1
        per_task[tid] = dict(kinds)
        for k, v in kinds.items():
            agg[k.split("[")[0]] += v
    except Exception as e:
        per_task[tid] = {"error": f"{type(e).__name__}: {e}"}
        agg["diag_error"] += 1
    if (n + 1) % 10 == 0:
        print(f"  {n+1}/{len(targets)}", flush=True)

json.dump({"aggregate": dict(agg.most_common()), "per_task": per_task},
          open(out_path, "w"), indent=1)
print("AGGREGATE:", dict(agg.most_common()))
print(f"report -> {out_path}")
