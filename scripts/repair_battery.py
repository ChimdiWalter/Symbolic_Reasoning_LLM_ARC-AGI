#!/usr/bin/env python3
"""Lever 3: repair search over the near-solve corpus — propose cheap,
verify expensive.

Propose: select failed tasks whose recorded blocker set matches a newly
shipped capability (no search spent on tasks the levers can't address):
  - vocab:copy blockers        -> registered learned verbs (SYNTH_COPY)
  - param_value_diff targets   -> feature_affine relational spelling
Verify: re-run FULL induction (LOO-by-reinduction gate intact, learned
verbs registered) on each selected task.  Newly certified tasks are
attributable flips; everything else stays honestly failed.

Usage: repair_battery.py [census=outputs/blocker_census_v12.json]
                         [mining=outputs/param_expr_mining.json]
                         [workers=6] [budget_s=120]
Writes outputs/repair_battery.json.
"""
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed

sys.path.insert(0, ".")

CENSUS = sys.argv[1] if len(sys.argv) > 1 else "outputs/blocker_census_v12.json"
MINING = sys.argv[2] if len(sys.argv) > 2 else "outputs/param_expr_mining.json"
WORKERS = int(sys.argv[3]) if len(sys.argv) > 3 else 6
BUDGET = float(sys.argv[4]) if len(sys.argv) > 4 else 120.0
OUT = "outputs/repair_battery.json"
REGISTRY = "outputs/learned_verbs/learned_verbs.json"


def run_one(tid, budget_s):
    from geocat_arc.perception.grid import Grid
    from geocat_arc.object_reasoning import correspondence as C
    from geocat_arc.object_reasoning.synth_verbs import LearnedVerbRegistry
    from geocat_arc.object_reasoning.inducer import (induce_program,
                                                     InductionConfig)
    try:
        verbs = json.load(open(REGISTRY))
    except Exception:
        verbs = []
    C.set_learned_verbs(LearnedVerbRegistry(verbs))
    chal = json.load(open("data/arc/arc-agi_training_challenges.json"))
    sols = json.load(open("data/arc/arc-agi_training_solutions.json"))
    pairs = [(Grid.from_list(p["input"]), Grid.from_list(p["output"]))
             for p in chal[tid]["train"]]
    res = induce_program(pairs, InductionConfig(budget_s=budget_s))
    test_ok = None
    if res.accepted:
        from geocat_arc.object_reasoning.actions import render_program
        try:
            oks = []
            for ti, tcase in enumerate(chal[tid]["test"]):
                pred = render_program(res.program,
                                      Grid.from_list(tcase["input"]))
                oks.append(pred.to_list() == sols[tid][ti])
            test_ok = all(oks)
        except Exception:
            test_ok = False
    return tid, res.accepted, test_ok, (res.failure_stage.value
                                        if res.failure_stage else None)


def main():
    census = json.load(open(CENSUS))
    mining = json.load(open(MINING))
    verb_targets = sorted(
        t for t, v in census["per_task"].items()
        if any(b.startswith("vocab:copy") for b in v["blockers"]))
    param_targets = sorted({t for e in mining["param_targets_ranked"]
                            for t in e["tasks"]})
    targets = {t: "verbs" for t in verb_targets}
    for t in param_targets:
        targets[t] = "affine" if t not in targets else "both"
    print(f"repair battery: {len(targets)} tasks "
          f"(verbs {len(verb_targets)}, affine {len(param_targets)}), "
          f"budget {BUDGET}s, workers {WORKERS}", flush=True)
    results = {}
    done = 0
    with ProcessPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(run_one, t, BUDGET): t for t in targets}
        for fut in as_completed(futs):
            tid = futs[fut]
            done += 1
            try:
                tid, accepted, test_ok, stage = fut.result()
            except Exception as exc:
                print(f"[{done}/{len(targets)}] {tid} CRASH {exc}",
                      flush=True)
                results[tid] = {"lever": targets[tid], "error": str(exc)}
                continue
            results[tid] = {"lever": targets[tid], "accepted": accepted,
                            "test_correct": test_ok, "stage": stage}
            mark = " *** NEWLY CERTIFIED ***" if accepted else ""
            print(f"[{done}/{len(targets)}] {tid} lever={targets[tid]} "
                  f"accepted={accepted} test={test_ok}{mark}", flush=True)
    flips = sorted(t for t, r in results.items() if r.get("accepted"))
    correct = sorted(t for t in flips if results[t].get("test_correct"))
    report = {"budget_s": BUDGET, "targets": len(targets),
              "newly_certified": flips, "test_correct": correct,
              "results": results}
    json.dump(report, open(OUT, "w"), indent=1)
    print(f"REPAIR BATTERY COMPLETE: {len(flips)} newly certified "
          f"({len(correct)} test-correct) -> {OUT}", flush=True)


if __name__ == "__main__":
    main()
