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

ANCHORED (the narrower proposal P2, not authorized, not run: inside the
engine's own leave-one-out folds only, the variant of the program being
validated is appended when the fold finds it coherent but the cap cuts it):
for every parent subset P and each fold F = P minus one demonstration, the
kept variants of P that F finds coherent and cuts. This is an upper bound on
P2's exposure (P2 appends only the winner's variant, not every kept one).
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


def anchored(rows):
    out = {}
    for parent, p in rows.items():
        if len(parent) < 2:
            continue
        folds = ["".join(c) for c in itertools.combinations(parent, len(parent) - 1)]
        if not all(f in rows for f in folds):
            continue
        out[parent] = {f: [v for v in p["kept"] if v in rows[f]["cut"]] for f in folds}
    return out


def monotone(rows):
    """Example-count dependence: coherent variants a fold adds or loses
    relative to its parent (the consistency clauses quantify over pairs, so
    only the pooled coverage ratio can make a fold lose one)."""
    out = {}
    for parent, p in rows.items():
        if len(parent) < 2:
            continue
        cp = set(p["kept"]) | set(p["cut"])
        for f in ("".join(c) for c in itertools.combinations(parent, len(parent) - 1)):
            if f in rows:
                cf = set(rows[f]["kept"]) | set(rows[f]["cut"])
                out[f"{parent}>{f}"] = {"added": sorted(cf - cp), "lost": sorted(cp - cf)}
    return out


def main():
    import geocat_arc.object_reasoning.inducer as I
    cap = I.MAX_SEG_VARIANTS_TRIED
    syn, dev = synthetic(cap), development(cap)
    anc = {"synthetic": {t: anchored(rows) for t, rows in syn.items()},
           "development": {t: anchored(rows) for t, rows in dev.items()}}
    mon = {"synthetic": {t: monotone(rows) for t, rows in syn.items()},
           "development": {t: monotone(rows) for t, rows in dev.items()}}

    def tally(block, name):
        subsets = [(t, k, r) for t, rows in block.items() for k, r in rows.items()]
        folds = [(t, p, f, vs) for t, ps in anc[name].items() for p, fs in ps.items() for f, vs in fs.items()]
        pairs = [(t, k, x) for t, ms in mon[name].items() for k, x in ms.items()]
        return {"subsets": len(subsets),
                "cap_binds": sum(1 for _, _, r in subsets if r["cut"]),
                "strict": sorted(f"{t}:{k}" for t, k, r in subsets if r["strict"]),
                "weak": sorted(f"{t}:{k}" for t, k, r in subsets if r["weak"]),
                "anchored_folds": len(folds),
                "anchored_exposed": sorted(f"{t}:{p}>{f}:{'+'.join(vs)}" for t, p, f, vs in folds if vs),
                "parent_fold_pairs": len(pairs),
                "fold_adds_coherent": sum(1 for _, _, x in pairs if x["added"]),
                "fold_loses_coherent": sorted(f"{t}:{k}:{'+'.join(x['lost'])}" for t, k, x in pairs if x["lost"])}
    out = {"cap": cap, "trial_order": [v.value for v in I.SEGMENTATION_TRIAL_ORDER],
           "synthetic": syn, "development": dev, "anchored": anc, "monotone": mon,
           "summary": {"synthetic": tally(syn, "synthetic"), "development": tally(dev, "development")}}
    with open(os.path.join(HERE, "outputs", "loo_v1", "probe_exposure.json"), "w") as handle:
        json.dump(out, handle, indent=1, sort_keys=True)
    print(json.dumps(out["summary"], indent=1))


if __name__ == "__main__":
    main()
