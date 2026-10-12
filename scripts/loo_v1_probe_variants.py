"""Forensic probe of segmentation-variant admission (observation only;
development tasks; no induction is run).

  python scripts/loo_v1_probe_variants.py   -> outputs/loo_v1/probe_variants.json

For each failure-conditioned task of reach v1 and every demonstration subset
its adaptive leave-one-out uses (full data, each outer fold's n-1, each inner
fold's n-2): which segmentation variants are coherent (the engine's own
segmentation.evaluate_variant), which the engine would search (the coherent
variants in SEGMENTATION_TRIAL_ORDER cut at MAX_SEG_VARIANTS_TRIED, as
inducer._induce_candidate does without the create-coherence flag), and
whether the extension's construction variant is coherent and searched.
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
    from geocat_arc.object_reasoning.segmentation import evaluate_variant
    from geocat_arc.object_reasoning.types import to_grid_pairs
    from cora_loo import diagnose as DG
    from cora_reach import measure as M
    if os.environ.get("ARC_CREATE_COHERENCE", "") not in ("", "0"):
        raise SystemExit("this probe models the cap without the create-coherence flag")
    tasks = json.load(open(BUNDLE))["tasks"]
    ctx = DG.load_context(HERE)
    out = {"trial_order": [v.value for v in I.SEGMENTATION_TRIAL_ORDER], "cap": I.MAX_SEG_VARIANTS_TRIED,
           "tasks": {}}
    for key, c in sorted(ctx.items()):
        train, _ = M.arrays(tasks[key])
        n = len(train)
        ev = c["variant"]
        subsets = {"full": tuple(range(n))}
        for i in range(n):
            rest = tuple(j for j in range(n) if j != i)
            subsets[f"outer{i}"] = rest
            for h in rest:
                subsets[f"outer{i}_inner{h}"] = tuple(j for j in rest if j != h)
        rec = {"extension": c["ext"]["family"], "variant": ev, "subsets": {}}
        cache = {}
        for name, sub in subsets.items():
            if sub not in cache:
                pairs = to_grid_pairs([train[j] for j in sub])
                coherent = [v.value for v in I.SEGMENTATION_TRIAL_ORDER if evaluate_variant(v, pairs).coherent]
                tried = coherent[:I.MAX_SEG_VARIANTS_TRIED]
                cache[sub] = {"demos": list(sub), "coherent": coherent, "searched": tried,
                              "ext_variant_coherent": ev in coherent, "ext_variant_searched": ev in tried,
                              "ext_variant_cut_by_cap": ev in coherent and ev not in tried}
            rec["subsets"][name] = cache[sub]
        rec["summary"] = {kind: {"subsets": len(v), "ext_searched": sum(1 for s in v if s["ext_variant_searched"]),
                                 "ext_cut_by_cap": sum(1 for s in v if s["ext_variant_cut_by_cap"]),
                                 "ext_incoherent": sum(1 for s in v if not s["ext_variant_coherent"])}
                          for kind, v in (("full", [rec["subsets"]["full"]]),
                                          ("outer", [s for k, s in rec["subsets"].items()
                                                     if k.startswith("outer") and "_inner" not in k]),
                                          ("inner", [s for k, s in rec["subsets"].items() if "_inner" in k]))}
        out["tasks"][key] = rec
    with open(os.path.join(HERE, "outputs", "loo_v1", "probe_variants.json"), "w") as handle:
        json.dump(out, handle, indent=1, sort_keys=True)
    ISO.dump(os.path.join(HERE, "logs", "loo_v1", "isolation_probe_variants.json"))
    for key, rec in out["tasks"].items():
        print(key, rec["extension"], rec["variant"], json.dumps(rec["summary"]))
        print("   full:", rec["subsets"]["full"]["coherent"], "searched", rec["subsets"]["full"]["searched"])
        cut = sorted({tuple(s["demos"]) for s in rec["subsets"].values() if s["ext_variant_cut_by_cap"]})
        print("   subsets where the cap cuts the extension's variant:", cut)


if __name__ == "__main__":
    main()
