#!/usr/bin/env python3
"""META-INDUCTION M1: cross-task residual-pattern mining (GO/NO-GO data).

Normalizes every near-solve residual across the given runs and reports
recurrence: does ANY normalized pattern recur across >= K distinct tasks?

Normalizations (the M1 knobs, docs/META_INDUCTION_DESIGN.md):
  - unexplained delta groups -> (delta_type, size_bucket, count_bucket)
  - orphan shapes -> canonical mask (rot/flip-invariant) hashed, size-bucketed
  - failed selector groups -> (delta_type, n_members_bucket)
  - lossy residue -> (grow/shrink/reshape/disjoint tag from stored residuals
    where present)

Output: outputs/meta_m1_residual_patterns.json + recurrence histogram.
"""
import glob
import json
import os
import sys
from collections import Counter, defaultdict

RUNS = sys.argv[1:] or ["outputs/unified_harness_v8",
                        "outputs/unified_harness_emit_training",
                        "outputs/unified_harness_emit_evaluation"]


def bucket(n):
    for b in (1, 2, 3, 5, 8, 13, 21):
        if n <= b:
            return b
    return 34


pattern_tasks = defaultdict(set)
seen_tasks = set()
for run in RUNS:
    for f in glob.glob(f"{run}/object/near_solve_parts/*.jsonl"):
        tid = os.path.basename(f)[:-6]
        if tid in seen_tasks:
            continue
        try:
            r = json.loads(open(f).readline())
        except Exception:
            continue
        seen_tasks.add(tid)
        stage = r.get("failure_stage")
        res = r.get("residual") or {}
        for u in res.get("unexplained_deltas") or []:
            key = ("unexplained", u.get("delta_type"),
                   bucket(u.get("count", 1)), stage)
            pattern_tasks[key].add(tid)
        hist = r.get("delta_histogram") or {}
        if hist:
            key = ("histogram-shape",
                   tuple(sorted((k, bucket(v)) for k, v in hist.items())),
                   stage)
            pattern_tasks[key].add(tid)

rec = Counter({k: len(v) for k, v in pattern_tasks.items()})
top = rec.most_common(25)
go = [(k, n) for k, n in rec.items() if n >= 5]
report = {
    "runs": RUNS, "tasks_covered": len(seen_tasks),
    "distinct_patterns": len(rec),
    "patterns_recurring_5plus": len(go),
    "top25": [{"pattern": [str(x) for x in k], "tasks": n} for k, n in top],
}
json.dump(report, open("outputs/meta_m1_residual_patterns.json", "w"),
          indent=1)
print(f"tasks {len(seen_tasks)} | patterns {len(rec)} | >=5-task recurrence: "
      f"{len(go)}")
for k, n in top[:12]:
    print(f"  {n:4d}  {k}")
print("report -> outputs/meta_m1_residual_patterns.json")
print("GO" if go else "NO-GO", "for M2 at K=5")
