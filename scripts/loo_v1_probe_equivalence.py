"""Segmentation-equivalence census (post-diagnosis addendum 2026-10-12,
sections 2 and 3; DIAGNOSIS ONLY: segmentation, correspondence and feature
tables are computed, no induction is run and no repair is installed).

  python scripts/loo_v1_probe_equivalence.py   -> outputs/loo_v1/probe_equivalence.json

Question: do several of the engine's segmentation variants give the
downstream reasoner the SAME input on a demonstration subset, so that they
occupy several of the MAX_SEG_VARIANTS_TRIED slots with one view? Equal
object counts are not enough. Five nested levels, each computed from the
subset's own training pairs only (never a held-out pair, never a program):

  COUNT      per-pair (input, output) object counts;
  PARTITION  per grid: background and the set of object cell sets;
  COLOURED   per grid: background and the set of objects as cell->colour maps;
  TYPED      per grid: background and the ordered object list with id,
             Python class (plain ARCObject or MultiColorObject: the engine's
             correspondence scores colour differently for the two,
             correspondence.py:156), colour, cell colours and bounding box;
  INDUCTION  TYPED plus the engine's own correspondence alternatives
             (correspondence.match_pair, first MAX_ALTS_PER_PAIR) and the
             input-object feature tables (features.compute_feature_table).

Inside the engine the variant's identity is otherwise used only to segment a
grid a program is rendered on (actions.py:945); features and correspondences
read objects, grids and backgrounds. So INDUCTION-equal variants yield the
same candidate programs on that subset, and the winner key (attempt key,
object count, trial order) then picks the earlier one.

Data: the 60 development tasks (training demonstrations only, through the
isolation hook; subsets: full, every n-1, every n-2) and the 24 synthetic
negative-control tasks of scripts/loo_v1_probe_negative.py (full and every
2-pair fold). Also (monotonicity clarification) every parent-fold pair:
coherent variants added or lost and the pooled coverage of each variant, and
one constructed two-pair example (TOY, labelled) in which removing a
demonstration makes a coherent variant incoherent through coverage alone.
"""
import itertools
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "scripts"))
BUNDLE = os.path.join(HERE, "records", "pilot_v1", "dev_bundle.json")
LEVELS = ("COUNT", "PARTITION", "COLOURED", "TYPED", "INDUCTION")


def _engine():
    import geocat_arc.object_reasoning.correspondence as C
    import geocat_arc.object_reasoning.features as F
    import geocat_arc.object_reasoning.inducer as I
    import geocat_arc.object_reasoning.segmentation as S
    from geocat_arc.object_reasoning.types import cell_colors_of, to_grid_pairs
    F.register_builtin_features()
    return C, F, I, S, cell_colors_of, to_grid_pairs


def _canon(x):
    return json.dumps(x, sort_keys=True, default=repr)


def per_demo(train):
    """Per demonstration and variant: the subset-independent pieces (the
    engine segments, matches and tabulates each pair on its own)."""
    C, F, I, S, cell_colors_of, to_grid_pairs = _engine()
    pairs = to_grid_pairs(train)
    out = {}
    for v in I.SEGMENTATION_TRIAL_ORDER:
        rows = []
        for i, (gi, go) in enumerate(pairs):
            bi, bo = S.background_for(gi, v), S.background_for(gi, v)   # one background per pair (the input's)
            oi, oo = S.segment(gi, v, bi), S.segment(go, v, bo)

            def typed(objs):
                return [(o.id, type(o).__name__, int(o.color), sorted((list(k), int(c)) for k, c in cell_colors_of(o).items()),
                         list(o.bounding_box)) for o in objs]
            ti, to = typed(oi), typed(oo)
            alts = C.match_pair(oi, oo, gi, go, pair_index=i)[:I.MAX_ALTS_PER_PAIR]
            corr = [(a.weights_profile, sorted((int(x), int(y), round(float(s), 9)) for x, y, s in a.matches),
                     sorted((int(k), sorted(int(z) for z in vs)) for k, vs in a.copies.items()),
                     sorted(int(z) for z in a.deleted_input_ids), sorted(int(z) for z in a.created_output_ids),
                     int(a.unreconciled_pixels), bool(a.is_object_preserving)) for a in alts]
            feats = [_canon(r) for r in F.compute_feature_table(oi, gi, bi, pair_index=i, role="input").rows]
            rows.append({
                "COUNT": (len(oi), len(oo)),
                "PARTITION": [(bi, sorted(sorted(map(tuple, (c for c, _ in t[3]))) for t in ti)),
                              (bo, sorted(sorted(map(tuple, (c for c, _ in t[3]))) for t in to))],
                "COLOURED": [(bi, sorted(_canon(t[3]) for t in ti)), (bo, sorted(_canon(t[3]) for t in to))],
                "TYPED": [(bi, ti), (bo, to)],
                "INDUCTION": [(bi, ti), (bo, to), corr, feats],
                "objects": {"input": ti, "output": to}})
        out[v.value] = rows
    return out


def subset_record(train, sub, demo, keep_objects=False):
    C, F, I, S, cell_colors_of, to_grid_pairs = _engine()
    pairs = to_grid_pairs([train[j] for j in sub])
    order = [v.value for v in I.SEGMENTATION_TRIAL_ORDER]
    res = {v.value: S.evaluate_variant(v, pairs) for v in I.SEGMENTATION_TRIAL_ORDER}
    for v, r in res.items():                      # the subset's segmentation is the per-demo one
        assert [len(o) for o in r.input_objects] == [demo[v][j]["COUNT"][0] for j in sub], (v, sub)
    coherent = [v for v in order if res[v].coherent]
    kept = coherent[:I.MAX_SEG_VARIANTS_TRIED]
    if not coherent:                               # the engine's fallback: max (coherence, coverage), trial order on ties
        kept = [max((res[v] for v in order), key=lambda r: (r.coherence, r.pixel_coverage)).variant.value]
    sig = {lvl: {v: _canon([demo[v][j][lvl] for j in sub]) for v in order} for lvl in LEVELS}
    classes = {}
    for lvl in LEVELS:
        groups = {}
        for v in coherent:
            groups.setdefault(sig[lvl][v], []).append(v)
        classes[lvl] = sorted(groups.values(), key=lambda g: order.index(g[0]))
    distinct = []
    for v in coherent:                              # canonical dedup at the INDUCTION level, trial order kept
        if all(sig["INDUCTION"][v] != sig["INDUCTION"][u] for u in distinct):
            distinct.append(v)
    dedup_kept = distinct[:I.MAX_SEG_VARIANTS_TRIED] if coherent else kept
    rec = {"coherent": coherent, "kept": kept,
           "wasted_slots": {lvl: len(kept) - len({sig[lvl][v] for v in kept}) for lvl in LEVELS} if coherent else
           {lvl: 0 for lvl in LEVELS},
           "classes": classes, "dedup_kept": dedup_kept,
           "dedup_admits": [v for v in dedup_kept if v not in kept],
           "dedup_drops": [v for v in kept if v not in dedup_kept],
           "coverage": {v: round(float(res[v].pixel_coverage), 6) for v in order},
           "consistent": {v: bool(res[v].pixel_coverage > 0 and abs(res[v].coherence - res[v].pixel_coverage) < 1e-12)
                          for v in order},
           "object_totals": {v: int(sum(len(o) for o in res[v].input_objects) + sum(len(o) for o in res[v].output_objects))
                             for v in order}}
    if keep_objects:
        rec["objects"] = {v: [demo[v][j]["objects"] for j in sub] for v in order}
    return rec


def task_record(args):
    key, train, subsets, keep = args
    demo = per_demo(train)
    return key, {"n_train": len(train),
                 "subsets": {"".join(map(str, s)): subset_record(train, s, demo, keep_objects=keep) for s in subsets}}


def monotone(rows):
    out = {}
    for parent, p in rows.items():
        if len(parent) < 2:
            continue
        for f in ("".join(c) for c in itertools.combinations(parent, len(parent) - 1)):
            if f not in rows:
                continue
            cp, cf = set(p["coherent"]), set(rows[f]["coherent"])
            drops = {v: round(p["coverage"][v] - rows[f]["coverage"][v], 6) for v in cp}
            out[f"{parent}>{f}"] = {"added": sorted(cf - cp), "lost": sorted(cp - cf),
                                   "max_coverage_drop": max(drops.values()) if drops else None,
                                   "min_fold_coverage_of_parent_coherent":
                                       min((rows[f]["coverage"][v] for v in cp), default=None)}
    return out


def counterexample():
    """TOY, constructed: pair A (a rectangle copied; coverage 1.0) and pair B
    (one cell kept, a new ring drawn; coverage 0.2); counts (1,2), (1,2)."""
    C, F, I, S, cell_colors_of, to_grid_pairs = _engine()
    a_in = np.zeros((10, 10), int)
    a_in[0:4, 0:5] = 3
    a_out = a_in.copy()
    a_out[5:9, 0:5] = 3
    b_in = np.zeros((10, 10), int)
    b_in[0, 0] = 1
    b_out = b_in.copy()
    b_out[4:7, 4:7] = 2
    b_out[5, 5] = 0
    v = I.SEGMENTATION_TRIAL_ORDER[0]
    rows = {}
    for name, pairs in (("AB", [(a_in, a_out), (b_in, b_out)]), ("A", [(a_in, a_out)]), ("B", [(b_in, b_out)])):
        r = S.evaluate_variant(v, to_grid_pairs(pairs))
        rows[name] = {"variant": v.value, "object_counts": [list(x) for x in r.object_counts],
                      "pixel_coverage": round(float(r.pixel_coverage), 6), "coherent": bool(r.coherent)}
    rows["loss_on_removing_A"] = rows["AB"]["coherent"] and not rows["B"]["coherent"]
    return rows


def main():
    from cora_pilot import isolation as ISO
    ISO.install(BUNDLE)
    sys.path.insert(0, os.path.join(HERE, "src"))
    from cora_pilot import native as N
    if N.environment_problems():
        raise SystemExit(f"native environment: {N.environment_problems()}")
    import geocat_arc.object_reasoning.inducer as I
    from cora_reach import measure as M
    from loo_v1_probe_negative import tasks as synthetic_tasks
    bundle = json.load(open(BUNDLE))["tasks"]
    jobs = []
    for key in sorted(bundle):
        train, _tests = M.arrays(bundle[key])         # training demonstrations only
        n = len(train)
        subsets = [tuple(range(n))] + [s for r in (n - 1, n - 2) if r >= 1 for s in itertools.combinations(range(n), r)]
        jobs.append((key, train, subsets, key == "kf892487f1049"))
    for t in synthetic_tasks():
        n = len(t["train"])
        jobs.append((f"SYN:{t['id']}", t["train"], [tuple(range(n))] + list(itertools.combinations(range(n), n - 1)), False))
    done = dict(task_record(j) for j in jobs)        # one process: the isolation hook refuses os.fork
    dev = {k: v for k, v in done.items() if not k.startswith("SYN:")}
    syn = {k[4:]: v for k, v in done.items() if k.startswith("SYN:")}

    def tally(block):
        subs = [(t, k, r) for t, x in block.items() for k, r in x["subsets"].items()]
        binds = [(t, k, r) for t, k, r in subs if len(r["coherent"]) > I.MAX_SEG_VARIANTS_TRIED]
        mon = {t: monotone(x["subsets"]) for t, x in block.items()}
        pairs = [(t, k, m) for t, ms in mon.items() for k, m in ms.items()]
        return {"tasks": len(block), "subsets": len(subs), "cap_binds": len(binds),
                "kept_slots": sum(len(r["kept"]) for _, _, r in subs if r["coherent"]),
                "wasted_slots": {lvl: sum(r["wasted_slots"][lvl] for _, _, r in subs) for lvl in LEVELS},
                "subsets_with_waste": {lvl: sum(1 for _, _, r in subs if r["wasted_slots"][lvl]) for lvl in LEVELS},
                "dedup_changes_search": sorted(f"{t}:{k}:+{'+'.join(r['dedup_admits'])}" for t, k, r in subs if r["dedup_admits"]),
                "parent_fold_pairs": len(pairs),
                "fold_adds_coherent": sum(1 for _, _, m in pairs if m["added"]),
                "fold_loses_coherent": sorted(f"{t}:{k}:{'+'.join(m['lost'])}" for t, k, m in pairs if m["lost"]),
                "max_coverage_drop": max((m["max_coverage_drop"] for _, _, m in pairs if m["max_coverage_drop"] is not None),
                                         default=None),
                "min_fold_coverage_of_parent_coherent": min((m["min_fold_coverage_of_parent_coherent"] for _, _, m in pairs
                                                             if m["min_fold_coverage_of_parent_coherent"] is not None),
                                                            default=None)}, mon
    sdev, mdev = tally(dev)
    ssyn, msyn = tally(syn)
    out = {"levels": LEVELS, "cap": I.MAX_SEG_VARIANTS_TRIED, "trial_order": [v.value for v in I.SEGMENTATION_TRIAL_ORDER],
           "development": dev, "synthetic": syn, "monotone": {"development": mdev, "synthetic": msyn},
           "counterexample_TOY": counterexample(), "summary": {"development": sdev, "synthetic": ssyn}}
    with open(os.path.join(HERE, "outputs", "loo_v1", "probe_equivalence.json"), "w") as handle:
        json.dump(out, handle, indent=1, sort_keys=True)
    print(json.dumps({"summary": out["summary"], "counterexample_TOY": out["counterexample_TOY"]}, indent=1))


if __name__ == "__main__":
    main()
