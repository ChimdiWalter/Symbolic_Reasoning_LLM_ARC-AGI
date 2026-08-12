#!/usr/bin/env python3
"""Lever 4b: cross-corpus blocker census + dependency report.

Reads a harness run's object near-solve parts and reports, per task, the
FULL blocker set the record carries (not just the first failure stage):
  - failure_stage (selector | parameter | matching | loo | segmentation)
  - unexplained delta types (matching residuals / vocabulary gaps)
  - selector/parameter conflict counts
  - LOO fold-divergence classification (new in round 9): diff the full-data
    program against each reinduced fold program —
      param_value_diff   same structure, same expr kind, different args
                         (the constant-that-won't-re-derive signature;
                          lever-1 mining fuel)
      param_kind_diff    same structure, different expression kind per fold
      selector_diff      same actions, different selector
      structure_diff     different rule count / delta types
      no_fold_program    reinduction returned nothing
      eval_error         fold program crashed on the held-out pair

Single- vs multi-blocker classification drives lever ordering: a task is
"single-blocker" when exactly one category blocks it — those are the tasks
each new capability can flip outright.

Usage: blocker_census.py [run_dir=outputs/unified_harness_v12] [out_json]
"""
import glob
import json
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, ".")
from geocat_arc.object_reasoning.trace_mining import classify_divergence

RUN = sys.argv[1] if len(sys.argv) > 1 else "outputs/unified_harness_v12"
OUT = sys.argv[2] if len(sys.argv) > 2 else "outputs/blocker_census.json"


def main():
    per_task = {}
    stage_counts = Counter()
    unexplained_types = Counter()
    divergence_kinds = Counter()
    traced = 0
    for f in sorted(glob.glob(f"{RUN}/object/near_solve_parts/*.jsonl")):
        tid = os.path.basename(f)[:-6]
        try:
            rec = json.loads(open(f).readline())
        except Exception:
            continue
        stage = rec.get("failure_stage", "?")
        stage_counts[stage] += 1
        res = rec.get("residual") or {}
        blockers = set()
        for d in res.get("unexplained_deltas") or []:
            dt = d.get("delta_type", "?")
            unexplained_types[dt] += 1
            blockers.add(f"vocab:{dt}")
        conf = res.get("conflict_report") or {}
        if conf.get("selector_conflicts"):
            blockers.add("selector_conflicts")
        if conf.get("parameter_conflicts"):
            blockers.add("parameter_conflicts")
        if res.get("loo_failures"):
            blockers.add("loo")
        kinds = []
        div = res.get("loo_divergence") or []
        if div:
            traced += 1
            full_prog = rec.get("program_partial")
            for t in div:
                for k in classify_divergence(full_prog, t):
                    kinds.append(k)
                    divergence_kinds[k] += 1
        per_task[tid] = {
            "failure_stage": stage,
            "blockers": sorted(blockers),
            "n_blockers": len(blockers),
            "divergence_kinds": sorted(set(kinds)),
        }
    single = [t for t, v in per_task.items() if v["n_blockers"] == 1]
    multi = [t for t, v in per_task.items() if v["n_blockers"] > 1]
    single_by = Counter(per_task[t]["blockers"][0] for t in single)
    report = {
        "run": RUN,
        "tasks": len(per_task),
        "failure_stages": dict(stage_counts.most_common()),
        "unexplained_delta_types": dict(unexplained_types.most_common()),
        "single_blocker_tasks": len(single),
        "single_blocker_by_category": dict(single_by.most_common()),
        "multi_blocker_tasks": len(multi),
        "records_with_loo_divergence_trace": traced,
        "divergence_kinds": dict(divergence_kinds.most_common(25)),
        "per_task": per_task,
    }
    os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
    json.dump(report, open(OUT, "w"), indent=1)
    for k in ("failure_stages", "unexplained_delta_types",
              "single_blocker_by_category", "divergence_kinds"):
        print(f"{k}: {report[k]}")
    print(f"single-blocker {len(single)} / multi-blocker {len(multi)} "
          f"/ traced {traced} -> {OUT}")


if __name__ == "__main__":
    main()
