#!/usr/bin/env python3
"""Lever 1 prep: generate fold-divergence traces for the LOO-blocked corpus.

Re-runs induce_program (now instrumented, round 9) on every task whose
near-solve record says failure_stage == loo, and stores the near-solve
record WITH residual["loo_divergence"] to outputs/loo_traces/<tid>.json.
Resumable: tasks with an existing output file are skipped.

Usage: generate_loo_traces.py [census=outputs/blocker_census_v12.json]
                              [workers=6] [budget_s=60]
"""
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed

sys.path.insert(0, ".")

CENSUS = sys.argv[1] if len(sys.argv) > 1 else "outputs/blocker_census_v12.json"
WORKERS = int(sys.argv[2]) if len(sys.argv) > 2 else 6
BUDGET = float(sys.argv[3]) if len(sys.argv) > 3 else 60.0
OUT_DIR = "outputs/loo_traces"


def run_one(tid, budget_s):
    from geocat_arc.perception.grid import Grid
    from geocat_arc.object_reasoning.inducer import (induce_program,
                                                     InductionConfig)
    chal = json.load(open("data/arc/arc-agi_training_challenges.json"))
    pairs = [(Grid.from_list(p["input"]), Grid.from_list(p["output"]))
             for p in chal[tid]["train"]]
    res = induce_program(pairs, InductionConfig(budget_s=budget_s))
    rec = None
    if res.near_solve is not None:
        rec = res.near_solve.to_dict()
        rec["task_id"] = tid
    return tid, res.accepted, (res.failure_stage.value
                               if res.failure_stage else None), rec


def main():
    census = json.load(open(CENSUS))
    tids = sorted(t for t, v in census["per_task"].items()
                  if v["failure_stage"] == "loo")
    os.makedirs(OUT_DIR, exist_ok=True)
    todo = [t for t in tids if not os.path.exists(f"{OUT_DIR}/{t}.json")]
    print(f"{len(tids)} loo tasks, {len(todo)} to trace "
          f"(workers={WORKERS}, budget={BUDGET}s)", flush=True)
    done = 0
    with ProcessPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(run_one, t, BUDGET): t for t in todo}
        for fut in as_completed(futs):
            tid = futs[fut]
            done += 1
            try:
                tid, accepted, stage, rec = fut.result()
            except Exception as exc:
                print(f"[{done}/{len(todo)}] {tid} CRASH {exc}", flush=True)
                continue
            if rec is not None:
                json.dump(rec, open(f"{OUT_DIR}/{tid}.json", "w"))
            n_div = len((rec or {}).get("residual", {})
                        .get("loo_divergence", []))
            print(f"[{done}/{len(todo)}] {tid} accepted={accepted} "
                  f"stage={stage} divergence={n_div}", flush=True)
    print("TRACE GENERATION COMPLETE", flush=True)


if __name__ == "__main__":
    main()
