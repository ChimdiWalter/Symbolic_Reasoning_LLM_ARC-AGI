"""Forensic probe: the exact segmentation-eligibility predicates (observation
only; development tasks; no induction). Summit addendum section B.

  python scripts/loo_v1_probe_eligibility.py   -> outputs/loo_v1/probe_eligibility.json

For each failure-conditioned task of reach v1 and each demonstration subset
(full data, every n-1, every n-2), and for every variant in the engine's
trial order: the per-pair object counts, the engine's own count-relation
test (segmentation._count_relation_consistent), whether a copy/grow
relaxation was needed (the engine's coherence equals its pixel coverage
exactly when its overall consistency holds), the pixel coverage against
COHERENCE_PIXEL_THRESHOLD, the first rejection site, the granularity
mismatch, and the variant's position against inducer.MAX_SEG_VARIANTS_TRIED.
Every value is read from the engine's own functions; nothing is re-implemented.
The demonstration subsets examined on kf892487f1049 were chosen AFTER the
development failure was seen: this is causal debugging, not test evidence.
"""
import itertools
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
BUNDLE = os.path.join(HERE, "records", "pilot_v1", "dev_bundle.json")


def main():
    from cora_pilot import isolation as ISO
    ISO.install(BUNDLE)
    sys.path.insert(0, os.path.join(HERE, "src"))
    from cora_pilot import native as N
    if N.environment_problems():
        raise SystemExit(f"native environment: {N.environment_problems()}")
    import geocat_arc.object_reasoning.inducer as I
    import geocat_arc.object_reasoning.segmentation as S
    from geocat_arc.object_reasoning.types import to_grid_pairs
    from cora_loo import diagnose as DG
    from cora_reach import measure as M
    tasks = json.load(open(BUNDLE))["tasks"]
    ctx = DG.load_context(HERE)
    out = {"threshold": S.COHERENCE_PIXEL_THRESHOLD, "cap": I.MAX_SEG_VARIANTS_TRIED,
           "trial_order": [v.value for v in I.SEGMENTATION_TRIAL_ORDER], "tasks": {}}
    for key, c in sorted(ctx.items()):
        train, _ = M.arrays(tasks[key])
        n = len(train)
        subsets = [tuple(range(n))] + [s for r in (n - 1, n - 2) if r >= 1
                                        for s in itertools.combinations(range(n), r)]
        rec = {"extension": c["ext"]["family"], "variant": c["variant"], "subsets": {}}
        for sub in subsets:
            pairs = to_grid_pairs([train[j] for j in sub])
            rows, coherent_order = [], []
            for v in I.SEGMENTATION_TRIAL_ORDER:
                r = S.evaluate_variant(v, pairs)
                count_ok = S._count_relation_consistent(r.object_counts)
                overall_ok = r.pixel_coverage > 0 and abs(r.coherence - r.pixel_coverage) < 1e-12
                cov_ok = r.pixel_coverage >= S.COHERENCE_PIXEL_THRESHOLD
                if r.coherent:
                    first = None
                    coherent_order.append(v.value)
                elif not overall_ok:
                    first = "count_relation_inconsistent_and_no_copy_or_grow_relaxation"
                elif not cov_ok:
                    first = "pixel_coverage_below_threshold"
                else:
                    first = "other"
                rows.append({"variant": v.value, "object_counts": [list(x) for x in r.object_counts],
                             "count_relation_consistent": count_ok, "overall_consistent": overall_ok,
                             "relaxation_used": bool(overall_ok and not count_ok),
                             "pixel_coverage": round(r.pixel_coverage, 4), "coverage_ok": cov_ok,
                             "granularity_mismatch": r.granularity_mismatch, "coherent": r.coherent,
                             "first_rejection": first})
            searched = coherent_order[:I.MAX_SEG_VARIANTS_TRIED]
            if not coherent_order:
                inc = [x for x in rows]
                fb = max(inc, key=lambda x: (0.0, x["pixel_coverage"]))["variant"]
                searched = [fb]
            for x in rows:
                x["coherent_rank"] = coherent_order.index(x["variant"]) + 1 if x["variant"] in coherent_order else None
                x["searched"] = x["variant"] in searched
            rec["subsets"]["".join(map(str, sub))] = {"demos": list(sub), "searched": searched,
                                                      "coherent": coherent_order, "variants": rows}
        out["tasks"][key] = rec
    with open(os.path.join(HERE, "outputs", "loo_v1", "probe_eligibility.json"), "w") as handle:
        json.dump(out, handle, indent=1, sort_keys=True)
    ISO.dump(os.path.join(HERE, "logs", "loo_v1", "isolation_probe_eligibility.json"))
    k = "kf892487f1049"
    for name, s in out["tasks"][k]["subsets"].items():
        print(k, name.ljust(4), "searched", s["searched"])
        for x in s["variants"]:
            print("     ", x["variant"], "counts", x["object_counts"], "count_ok", x["count_relation_consistent"],
                  "relax", x["relaxation_used"], "cov %.3f" % x["pixel_coverage"], "mismatch", x["granularity_mismatch"],
                  "coherent", x["coherent"], "rank", x["coherent_rank"], "first_rejection", x["first_rejection"])


if __name__ == "__main__":
    main()
