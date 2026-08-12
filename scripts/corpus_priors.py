#!/usr/bin/env python3
"""Lever 5: corpus-learned search priors from the certified corpus.

Statistics over every certificate of a sealed run — what the system's own
certified history says about where solutions live:
  - segmentation-variant win histogram (drives SEGMENTATION_TRIAL_ORDER,
    a constant refreshed between runs — fold-invariant by construction)
  - delta-type usage across certified rules
  - selector predicate op usage (how often in_set vs grammar predicates win)
  - parameter-class distribution of certified programs

LEGALITY: priors are learned from the system's own past certified runs and
applied as CONSTANTS between runs (same regime as the operator library and
learned verbs).  Nothing is conditioned per-task, so LOO folds see
identical search order.  The task-level gate remains the only acceptance
path.

Usage: corpus_priors.py [run=outputs/unified_harness_v12]
Writes outputs/corpus_priors.json.
"""
import glob
import json
import sys
from collections import Counter

RUN = sys.argv[1] if len(sys.argv) > 1 else "outputs/unified_harness_v12"
OUT = "outputs/corpus_priors.json"


def main():
    variants = Counter()
    delta_types = Counter()
    selector_ops = Counter()
    param_classes = Counter()
    n = 0
    for f in sorted(glob.glob(f"{RUN}/object/certificates/*.json")):
        try:
            cert = json.load(open(f))
        except Exception:
            continue
        prog = cert.get("program") or {}
        n += 1
        variants[prog.get("segmentation_variant", "?")] += 1
        for rule in prog.get("rules") or []:
            delta_types[(rule.get("action") or {}).get("delta_type", "?")] += 1
            pred = (rule.get("selector") or {}).get("predicate") or {}
            selector_ops[pred.get("op", "?")] += 1
        if "worst_parameter_class" in cert:
            param_classes[cert["worst_parameter_class"]] += 1
    report = {
        "run": RUN,
        "certificates": n,
        "segmentation_variant_wins": dict(variants.most_common()),
        "delta_type_usage": dict(delta_types.most_common()),
        "selector_op_usage": dict(selector_ops.most_common()),
        "worst_parameter_class": dict(param_classes.most_common()),
    }
    json.dump(report, open(OUT, "w"), indent=1)
    for k, v in report.items():
        if k not in ("run",):
            print(f"{k}: {v}")
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
