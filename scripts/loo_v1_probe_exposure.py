"""Static exposure of a proposed cap correction (summit addendum, sections
B and E; observation only; segmentation-level, no induction is run).

  python scripts/loo_v1_probe_exposure.py   -> outputs/loo_v1/probe_exposure.json

The engine keeps the coherent segmentation variants in its fixed trial order
and searches the first MAX_SEG_VARIANTS_TRIED of them (kept set K, cut set R).
After a variant yields a train-perfect program it still tries the remaining
strictly coarser variants (fewer total objects over the pairs), and that rule
is what is meant to make an n-1 fold converge on the variant the full set
picks. The proposal (P1, not authorized, not run) would let that coarser
completion reach the cut set R as well. P1 can change a search only if some
r in R has fewer total objects than a kept variant; this script counts where
that necessary condition holds, for every demonstration subset that an
induction or its own leave-one-out sees:

  - the 24 seeded synthetic tasks of scripts/loo_v1_probe_negative.py (same
    generator and seeds; training demonstrations only): the full 3-pair set
    and its three 2-pair leave-one-out folds;
  - the four development tasks already recorded in
    outputs/loo_v1/probe_eligibility.json (read from that file; no ARC grid
    is opened here).

STRICT: some r in R is strictly coarser than every kept variant (if any kept
variant yields a train-perfect program, P1 searches r). WEAK: some r in R is
strictly coarser than at least one kept variant (P1 searches r only if the
winner is one of those).
"""
import itertools
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "scripts"))


def exposure(order, coherent, counts, cap):
    kept = [v for v in order if v in coherent][:cap]
    cut = [v for v in order if v in coherent][cap:]
    if not kept:
        return {"kept": [], "cut": cut, "strict": [], "weak": [], "counts": counts}
    lo, hi = min(counts[v] for v in kept), max(counts[v] for v in kept)
    return {"kept": kept, "cut": cut, "counts": {v: counts[v] for v in kept + cut},
            "strict": [v for v in cut if counts[v] < lo],
            "weak": [v for v in cut if counts[v] < hi]}


def synthetic(cap):
    import geocat_arc.object_reasoning.inducer as I
    from geocat_arc.object_reasoning.segmentation import evaluate_variant
    from geocat_arc.object_reasoning.types import to_grid_pairs
    from loo_v1_probe_negative import tasks
    order = [v.value for v in I.SEGMENTATION_TRIAL_ORDER]
    out = {}
    for t in tasks():
        rows = {}
        n = len(t["train"])
        for k in (n, n - 1):
            for sub in itertools.combinations(range(n), k):
                gp = to_grid_pairs([t["train"][i] for i in sub])
                coherent, counts = set(), {}
                for v in I.SEGMENTATION_TRIAL_ORDER:
                    r = evaluate_variant(v, gp)
                    counts[v.value] = sum(len(o) for o in r.input_objects) + sum(len(o) for o in r.output_objects)
                    if r.coherent:
                        coherent.add(v.value)
                rows["".join(map(str, sub))] = exposure(order, coherent, counts, cap)
        out[t["id"]] = rows
    return out


def development(cap):
    with open(os.path.join(HERE, "outputs", "loo_v1", "probe_eligibility.json")) as handle:
        d = json.load(handle)
    order = d["trial_order"]
    out = {}
    for task, x in d["tasks"].items():
        rows = {}
        for key, s in x["subsets"].items():
            counts = {v["variant"]: sum(a + b for a, b in v["object_counts"]) for v in s["variants"]}
            rows[key] = exposure(order, set(s["coherent"]), counts, cap)
        out[task] = rows
    return out


def main():
    import geocat_arc.object_reasoning.inducer as I
    cap = I.MAX_SEG_VARIANTS_TRIED
    syn, dev = synthetic(cap), development(cap)

    def tally(block):
        subsets = [(t, k, r) for t, rows in block.items() for k, r in rows.items()]
        return {"subsets": len(subsets),
                "cap_binds": sum(1 for _, _, r in subsets if r["cut"]),
                "strict": sorted(f"{t}:{k}" for t, k, r in subsets if r["strict"]),
                "weak": sorted(f"{t}:{k}" for t, k, r in subsets if r["weak"])}
    out = {"cap": cap, "trial_order": [v.value for v in I.SEGMENTATION_TRIAL_ORDER],
           "synthetic": syn, "development": dev,
           "summary": {"synthetic": tally(syn), "development": tally(dev)}}
    with open(os.path.join(HERE, "outputs", "loo_v1", "probe_exposure.json"), "w") as handle:
        json.dump(out, handle, indent=1, sort_keys=True)
    print(json.dumps(out["summary"], indent=1))


if __name__ == "__main__":
    main()
