#!/usr/bin/env python3
"""Round 10: framing census of the eval tasks the engine never engages.

84/120 eval tasks produce NO near-solve record (best object fit < 0.5) —
the bottleneck is not a missing verb inside a working analysis, it is that
the object-engine framing (segment -> correspond -> rules on preserved
objects) never gets traction.  This census asks WHAT those tasks look like
structurally, using only their train pairs (no solutions):

  shape regime      same_shape | shrink | grow | mixed; integer scale
                    factors; constant-output-size detection
  edit density      fraction of cells changed (same-shape tasks):
                    sparse edit vs dense rewrite
  palette relation  colors introduced by outputs (generative coloring)
  segmentation      best variant's object-count coherence in/out —
                    does ANY variant see matchable object populations?
  size class        grid areas (tiny logic grids vs large scenes)

Output: outputs/eval_framing_census.json — per-task profile + regime
histogram over exactly the uncovered set, vs the engaged set for contrast.
The regimes rank the round-10 framing work by task count.

Usage: eval_framing_census.py [run=outputs/unified_harness_eval_v13]
"""
import glob
import json
import os
import sys
from collections import Counter

sys.path.insert(0, ".")
from geocat_arc.perception.grid import Grid
from geocat_arc.object_reasoning.segmentation import evaluate_variant
from geocat_arc.object_reasoning.types import (SEGMENTATION_TRIAL_ORDER,
                                               SegmentationVariant)

RUN = sys.argv[1] if len(sys.argv) > 1 else "outputs/unified_harness_eval_v13"
OUT = "outputs/eval_framing_census.json"


def shape_regime(pairs):
    rels = set()
    scales = set()
    out_sizes = set()
    for gi, go in pairs:
        hi, wi, ho, wo = gi["h"], gi["w"], go["h"], go["w"]
        out_sizes.add((ho, wo))
        if (ho, wo) == (hi, wi):
            rels.add("same")
        elif ho <= hi and wo <= wi:
            rels.add("shrink")
        elif ho >= hi and wo >= wi:
            rels.add("grow")
        else:
            rels.add("mixed")
        if hi and wi and ho % hi == 0 and wo % wi == 0 \
                and (ho // hi, wo // wi) != (1, 1):
            scales.add((ho // hi, wo // wi))
    regime = rels.pop() if len(rels) == 1 else "varies"
    return regime, (len(scales) == 1 and len(rels) == 1), \
        len(out_sizes) == 1


def profile(task):
    pairs = []
    for p in task["train"]:
        gi, go = p["input"], p["output"]
        pairs.append(({"h": len(gi), "w": len(gi[0]), "cells": gi},
                      {"h": len(go), "w": len(go[0]), "cells": go}))
    regime, integer_scale, const_out = shape_regime(pairs)
    prof = {"shape_regime": regime, "integer_scale": integer_scale,
            "constant_output_size": const_out}
    # edit density + palette (same-shape only for density)
    dens = []
    new_colors = False
    for gi, go in pairs:
        ci = {c for row in gi["cells"] for c in row}
        co = {c for row in go["cells"] for c in row}
        if not co <= ci:
            new_colors = True
        if (gi["h"], gi["w"]) == (go["h"], go["w"]):
            total = gi["h"] * gi["w"]
            diff = sum(1 for r in range(gi["h"]) for c in range(gi["w"])
                       if gi["cells"][r][c] != go["cells"][r][c])
            dens.append(diff / total)
    prof["edit_density"] = round(sum(dens) / len(dens), 3) if dens else None
    prof["outputs_introduce_colors"] = new_colors
    prof["mean_input_area"] = round(sum(g["h"] * g["w"]
                                        for g, _ in pairs) / len(pairs))
    # segmentation coherence: best variant by matched in/out object counts
    grid_pairs = [(Grid.from_list(g["cells"]), Grid.from_list(o["cells"]))
                  for g, o in pairs]
    best = None
    for var in SEGMENTATION_TRIAL_ORDER:
        try:
            seg = evaluate_variant(SegmentationVariant(var.value)
                                   if not isinstance(var, SegmentationVariant)
                                   else var, grid_pairs)
            counts = [(len(i), len(o)) for i, o in
                      zip(seg.input_objects, seg.output_objects)]
            if any(ni == 0 or ni > 40 for ni, _ in counts):
                continue
            coherent = sum(1 for ni, no in counts
                           if no and 0.5 <= ni / no <= 2.0)
            score = coherent / len(counts)
            if best is None or score > best[1]:
                best = (str(getattr(var, "value", var)), score)
        except Exception:
            continue
    prof["best_variant_coherence"] = (best[0], round(best[1], 2)) \
        if best else None
    return prof


def regime_key(p):
    bits = [p["shape_regime"]]
    if p["shape_regime"] == "same":
        d = p["edit_density"]
        bits.append("dense" if (d or 0) > 0.35 else "sparse")
    if p["integer_scale"]:
        bits.append("int_scale")
    if p["constant_output_size"]:
        bits.append("const_out")
    if p["outputs_introduce_colors"]:
        bits.append("new_colors")
    coh = p["best_variant_coherence"]
    bits.append("seg_ok" if coh and coh[1] >= 0.99 else "seg_poor")
    return "|".join(bits)


def main():
    chal = json.load(open("data/arc/arc-agi_evaluation_challenges.json"))
    engaged = {os.path.basename(f)[:-6] for f in
               glob.glob(f"{RUN}/object/near_solve_parts/*.jsonl")}
    per_task = {}
    hist = {"uncovered": Counter(), "engaged": Counter()}
    for tid, task in sorted(chal.items()):
        try:
            p = profile(task)
        except Exception as exc:
            p = {"error": type(exc).__name__}
        group = "engaged" if tid in engaged else "uncovered"
        p["group"] = group
        per_task[tid] = p
        if "error" not in p:
            hist[group][regime_key(p)] += 1
    report = {
        "run": RUN,
        "uncovered_tasks": sum(hist["uncovered"].values()),
        "engaged_tasks": sum(hist["engaged"].values()),
        "uncovered_regimes": dict(hist["uncovered"].most_common()),
        "engaged_regimes": dict(hist["engaged"].most_common()),
        "per_task": per_task,
    }
    json.dump(report, open(OUT, "w"), indent=1)
    print(f"uncovered {report['uncovered_tasks']} / engaged "
          f"{report['engaged_tasks']}")
    print("TOP UNCOVERED REGIMES:")
    for k, n in list(hist["uncovered"].most_common(12)):
        print(f"  {n:3d}  {k}")
    print("(engaged, for contrast):")
    for k, n in list(hist["engaged"].most_common(5)):
        print(f"  {n:3d}  {k}")
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
