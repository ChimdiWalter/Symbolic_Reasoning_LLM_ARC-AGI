"""P3 semantic audit (P3 safety directive 2026-10-12, sections 3 and 4;
read-only: segmentation only, no induction, no repair installed).

  python scripts/p3_audit_equivalence.py   -> outputs/p3/audit_equivalence.json

1. Census reproduction. Recompute the frozen segmentation-equivalence census
   (scripts/loo_v1_probe_equivalence.py, output 7d11993) in memory, compare
   every subset record with the committed output, and re-derive its headline
   counts. The committed census file is only read.
2. Training equivalence against unseen execution. Two views that give the
   reasoner identical input on a training subset can still segment an input
   outside that subset differently, and a program re-segments every input it
   is rendered on (actions.py:945). For every training subset an induction
   or its own leave-one-out receives, and every INDUCTION-equivalence class
   with two or more coherent views, each member segments every input NOT in
   the subset (development: the other training demonstrations only;
   synthetic: the other training demonstrations and both held-out inputs).
   A member diverges when its typed segmentation (objects, cells, colours,
   class, background) differs from the class's earliest view.
"""
import itertools
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "scripts"))
BUNDLE = os.path.join(HERE, "records", "pilot_v1", "dev_bundle.json")
CENSUS = os.path.join(HERE, "outputs", "loo_v1", "probe_equivalence.json")


def typed_grid(grid, v, S, cell_colors_of):
    bg = S.background_for(grid, v)
    return json.dumps([bg, [(o.id, type(o).__name__, int(o.color), sorted((list(k), int(c)) for k, c in
                                                                           cell_colors_of(o).items()))
                            for o in S.segment(grid, v, bg)]])


def unseen(task_id, train, heldout, rows, order):
    import geocat_arc.object_reasoning.segmentation as S
    from geocat_arc.object_reasoning.types import cell_colors_of, to_grid_pairs
    grids = [p[0] for p in to_grid_pairs(train)] + [p[0] for p in to_grid_pairs(heldout)] if heldout else \
        [p[0] for p in to_grid_pairs(train)]
    cache = {}
    out = []
    for key, r in rows.items():
        inside = {int(c) for c in key}
        others = [i for i in range(len(grids)) if i not in inside]
        if not others:
            continue
        for cls in r["classes"]["INDUCTION"]:
            if len(cls) < 2:
                continue
            rep = cls[0]
            for m in cls[1:]:
                div = []
                for i in others:
                    for v in (rep, m):
                        if (v, i) not in cache:
                            V = next(x for x in S.SEGMENTATION_TRIAL_ORDER if x.value == v)
                            cache[(v, i)] = typed_grid(grids[i], V, S, cell_colors_of)
                    if cache[(rep, i)] != cache[(m, i)]:
                        div.append(i if i < len(train) else f"heldout{i - len(train)}")
                out.append({"task": task_id, "subset": key, "earliest": rep, "member": m,
                            "kept_natively": [x for x in (rep, m) if x in r["kept"]], "diverges_on": div})
    return out


def main():
    from cora_pilot import isolation as ISO
    ISO.install(BUNDLE)
    sys.path.insert(0, os.path.join(HERE, "src"))
    from cora_pilot import native as N
    if N.environment_problems():
        raise SystemExit(f"native environment: {N.environment_problems()}")
    import geocat_arc.object_reasoning.inducer as I
    from cora_reach import measure as M
    import loo_v1_probe_equivalence as EQ
    from loo_v1_probe_negative import tasks as synthetic_tasks
    frozen = json.load(open(CENSUS))
    order = [v.value for v in I.SEGMENTATION_TRIAL_ORDER]
    bundle = json.load(open(BUNDLE))["tasks"]
    mismatch, audit_dev, audit_syn = [], [], []
    for key in sorted(bundle):
        train, _tests = M.arrays(bundle[key])          # training demonstrations only; test inputs unused
        n = len(train)
        subsets = [tuple(range(n))] + [s for r in (n - 1, n - 2) if r >= 1 for s in itertools.combinations(range(n), r)]
        _, rec = EQ.task_record((key, train, subsets, key == "kf892487f1049"))
        rec = json.loads(json.dumps(rec))
        if rec != frozen["development"][key]:
            mismatch.append(key)
        audit_dev += unseen(key, train, None, rec["subsets"], order)
    for t in synthetic_tasks():
        n = len(t["train"])
        subsets = [tuple(range(n))] + list(itertools.combinations(range(n), n - 1))
        _, rec = EQ.task_record((f"SYN:{t['id']}", t["train"], subsets, False))
        rec = json.loads(json.dumps(rec))
        if rec != frozen["synthetic"][t["id"]]:
            mismatch.append("SYN:" + t["id"])
        audit_syn += unseen(t["id"], t["train"], t["heldout"], rec["subsets"], order)
    s = frozen["summary"]["development"]
    f = json.load(open(os.path.join(HERE, "outputs", "reach_v1", "measure_funnel.json")))["per_task"]
    natives = sorted(k for k, v in f.items() if not v["A_native_baseline_failure"])
    natives_changed = [k for k in natives
                       if frozen["development"][k]["subsets"]["".join(map(str, range(frozen["development"][k]["n_train"])))]["dedup_admits"]]
    kf = frozen["development"]["kf892487f1049"]["subsets"]

    def summarize(rows):
        return {"train_equivalent_pairs": len(rows),
                "pairs_diverging_on_an_unseen_input": sum(1 for r in rows if r["diverges_on"]),
                "both_kept_natively_and_diverging": sum(1 for r in rows if r["diverges_on"] and len(r["kept_natively"]) == 2),
                "by_views": {f"{a}~{b}": sum(1 for r in rows if (r["earliest"], r["member"]) == (a, b) and r["diverges_on"])
                             for a, b in sorted({(r["earliest"], r["member"]) for r in rows})}}
    out = {"census_reproduced": not mismatch, "census_mismatches": mismatch,
           "census_counts": {"wasted_slots_induction": [s["wasted_slots"]["INDUCTION"], s["kept_slots"]],
                             "subsets_changed_by_dedup": [len(s["dedup_changes_search"]), s["subsets"]],
                             "native_successes_full_data_changed": [len(natives_changed), len(natives), natives_changed],
                             "kf89_02_admits": kf["02"]["dedup_admits"], "kf89_13_admits": kf["13"]["dedup_admits"]},
           "unseen": {"development": summarize(audit_dev), "synthetic": summarize(audit_syn)},
           "kf89_rows": [r for r in audit_dev if r["task"] == "kf892487f1049" and r["subset"] in ("02", "13")],
           "examples": {"development": [r for r in audit_dev if r["diverges_on"]][:12],
                        "synthetic": [r for r in audit_syn if r["diverges_on"]][:12]}}
    os.makedirs(os.path.join(HERE, "outputs", "p3"), exist_ok=True)
    with open(os.path.join(HERE, "outputs", "p3", "audit_equivalence.json"), "w") as handle:
        json.dump(out, handle, indent=1, sort_keys=True)
    print(json.dumps({k: out[k] for k in ("census_reproduced", "census_counts", "unseen", "kf89_rows")}, indent=1))


if __name__ == "__main__":
    main()
