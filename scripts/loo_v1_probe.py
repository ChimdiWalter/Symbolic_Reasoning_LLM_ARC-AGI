"""Forensic probe of the adaptive LOO diagnosis (observation only; one
development task; docs/CORA_REAL_TASK_LOO_STABILITY_v1.md sections 2 and 6).

  python scripts/loo_v1_probe.py [KEY]   -> outputs/loo_v1/probe_<KEY>.json

The frozen diagnosis showed, on kf892487f1049, that every outer fold finds
the full-data program G (one rule, selector true, grow by the installed
relation, colour of self) and that the engine's own leave-one-out rejects
it because one 2-demonstration re-induction returns a different program.
This probe asks, for every pair of demonstrations, with the reach v1
extension installed and the engine's deadlines on process CPU time:
- what the engine's own search (inducer._induce_composed, as an inner fold
  calls it) returns, and on which segmentation variant;
- which variants the cross-variant search tried and which it skipped;
- whether G is in the returned pool and whether G is train-exact on the pair;
- what the same candidate search returns with every variant explored
  (inducer._induce_candidate(explore_all=True), the engine's own phase-B
  switch), and whether each winner reproduces the other two demonstrations.
No engine function is edited; the spies return their wrapped results. No
target is read: only demonstrations.
"""
import itertools
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
BUNDLE = os.path.join(HERE, "records", "pilot_v1", "dev_bundle.json")


def main(argv):
    key = argv[0] if argv else "kf892487f1049"
    from cora_pilot import isolation as ISO
    ISO.install(BUNDLE)
    sys.path.insert(0, os.path.join(HERE, "src"))
    from cora_pilot import native as N
    problems = N.environment_problems()
    if problems:
        raise SystemExit(f"native environment: {problems}")
    from harness.run_harness import _set_worker_env
    _set_worker_env()
    import numpy as np
    import geocat_arc.object_reasoning.inducer as I
    from geocat_arc.object_reasoning.engine import ObjectReasoningEngine
    from geocat_arc.object_reasoning.types import program_from_dict, to_grid_pairs
    import geocat_arc.object_reasoning.actions as AC
    from cora_v19 import v19_trace as TR
    from cora_reach import bridge as BR, census as CS, measure as M
    from cora_loo import instrument as IN
    tasks = json.load(open(BUNDLE))["tasks"]
    row = next(json.loads(l) for l in open(os.path.join(HERE, "outputs", "reach_v1", "measure_rows.jsonl"))
               if l.strip() and json.loads(l)["key"] == key)
    e = row["extension"]
    train, _tests = M.arrays(tasks[key])
    obj = N.prepare_object_dir(os.path.join(HERE, "outputs", "loo_v1", "probe_engine"))
    out = {"key": key, "extension": e, "n_train": len(train), "pairs": {}}
    #  G: the full-data program, as the frozen run found it
    full, G = IN.engine_run(f"{key}_probe_full", train, [], obj, ext=e, clock="CPU1")
    out["full"] = {"accepted": full["accepted"], "uses": full.get("uses"), "program_sha": full["program_sha"],
                   "program": G}
    if G is None:
        raise SystemExit("the full-data run did not accept a program: nothing to probe")
    g_sha = M.psha(G)
    seen = []
    orig_table = I._induce_on_table

    def _induce_on_table(seg, table, report, pairs, config, deadline, meta):
        att = orig_table(seg, table, report, pairs, config, deadline, meta)
        if seen is not None:
            seen.append({"variant": getattr(seg.variant, "value", None),
                         "seg_count": sum(len(o) for o in seg.input_objects) + sum(len(o) for o in seg.output_objects),
                         "programs": len(att.programs),
                         "top": CS.prog_summary(att.programs[0]) if att.programs else None,
                         "has_G": any(M.psha(p.to_dict()) == g_sha for p in att.programs)})
        return att

    def winner_record(att, pairs_idx, others):
        if not att.programs:
            return {"programs": 0, "stage": getattr(att.stage, "value", None)}
        p = att.programs[0]
        d = p.to_dict()
        fn = AC.program_apply_fn(program_from_dict(json.loads(json.dumps(d))))
        exact = {}
        for j in others:
            try:
                exact[j] = M._grid(fn(train[j][0])) == M._grid(train[j][1])
            except Exception:                                   # noqa: BLE001
                exact[j] = False
        return {"programs": len(att.programs), "variant": getattr(att.seg.variant, "value", None) if att.seg else None,
                "top": CS.prog_summary(d), "top_is_G": M.psha(d) == g_sha, "uses_e": BR.uses(d, e),
                "G_in_pool": any(M.psha(q.to_dict()) == g_sha for q in att.programs),
                "reproduces_other_demos": exact}
    cfg0 = ObjectReasoningEngine(obj, use_library=True, config=I.InductionConfig(budget_s=M.BUDGET_S))
    cfg = cfg0._config_with_library()
    I._induce_on_table = _induce_on_table
    try:
        for pair in itertools.combinations(range(len(train)), 2):
            others = [j for j in range(len(train)) if j not in pair]
            sub = to_grid_pairs([train[j] for j in pair])
            rec = {}
            with BR.installed(e), TR._clock("CPU1"):
                fn = AC.program_apply_fn(program_from_dict(json.loads(json.dumps(G))))
                rec["G_train_exact_on_pair"] = all(M._grid(fn(train[j][0])) == M._grid(train[j][1]) for j in pair)
                for mode in ("engine", "explore_all"):
                    seen.clear()
                    M.clear_engine_caches()
                    t0 = time.process_time()
                    deadline = I.time.monotonic() + M.BUDGET_S
                    if mode == "engine":
                        att = I._induce_composed(sub, cfg, deadline, I._Meta(), max(1, int(cfg.max_composition_depth)))
                    else:
                        att = I._induce_candidate(sub, cfg, deadline, I._Meta(), explore_all=True)
                    rec[mode] = winner_record(att, pair, others)
                    rec[mode]["cpu_s"] = round(time.process_time() - t0, 3)
                    rec[mode]["variants_tried"] = list(seen)
            out["pairs"]["".join(map(str, pair))] = rec
    finally:
        I._induce_on_table = orig_table
    out["restored"] = BR.restored() and I._induce_on_table is orig_table
    path = os.path.join(HERE, "outputs", "loo_v1", f"probe_{key}.json")
    with open(path, "w") as handle:
        json.dump(out, handle, indent=1, sort_keys=True, default=str)
    ISO.dump(os.path.join(HERE, "logs", "loo_v1", f"isolation_probe_{key}.json"))
    for k, r in out["pairs"].items():
        en, ex = r["engine"], r["explore_all"]
        print(k, "G exact on pair", r["G_train_exact_on_pair"],
              "| engine:", en.get("variant"), "top_is_G", en.get("top_is_G"), "G_in_pool", en.get("G_in_pool"),
              "others", en.get("reproduces_other_demos"), "tried", [(v["variant"], v["seg_count"], v["programs"], v["has_G"]) for v in en["variants_tried"]],
              "| explore_all:", ex.get("variant"), "top_is_G", ex.get("top_is_G"), "others", ex.get("reproduces_other_demos"),
              "tried", [(v["variant"], v["seg_count"], v["programs"], v["has_G"]) for v in ex["variants_tried"]])


if __name__ == "__main__":
    main(sys.argv[1:])
