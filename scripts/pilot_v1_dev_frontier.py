"""Real ARC pilot v1 feasibility: why the proposer stops on real tasks.

  python scripts/pilot_v1_dev_frontier.py   -> outputs/pilot_v1_dev/frontier_census.json

For each DEVELOPMENT task (records/pilot_v1/dev_bundle.json; demonstrations
only, no target exists or is read), the frozen reasoner's typed failure
frontier over its 200 single-block programs (v1.8 build_input): status per
block, the fitter code of every conflicting block, and how much of the
change the best consistent block covers. Aggregated by mechanism, never by
task identity.
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)


def main() -> None:
    from cora_pilot import reasoner as RS
    from cora_arc2026 import v18_proposer as P
    bundle = json.load(open(os.path.join(HERE, "records", "pilot_v1", "dev_bundle.json")))
    codes, per_task = {}, []
    for key, task in sorted(bundle["tasks"].items()):
        train, _tests = RS.arrays(task)
        sem = P.Semantics(train)
        rows = P.frontier(sem)
        st = {"FULL": 0, "PARTIAL": 0, "CONFLICT": 0}
        tc = {}
        best = 0.0
        total = sum(len(c) for c in sem.changed) or 1
        for r in rows:
            st[r["status"]] += 1
            if r["status"] == "CONFLICT":
                tc[r["code"]] = tc.get(r["code"], 0) + 1
            else:
                best = max(best, sum(r["covered"]) / total)
        for c, n in tc.items():
            codes[c] = codes.get(c, 0) + n
        dominant = max(tc, key=tc.get) if tc else None
        changed_share = sum(len(c) for c in sem.changed) / sum(a.size for a, _b in sem.demos)
        per_task.append({"status": st, "dominant_conflict": dominant, "best_consistent_coverage": round(best, 3),
                         "changed_share": round(changed_share, 3), "n_train": len(train)})
    n = len(per_task)
    agg = {"tasks": n, "conflict_codes_over_all_blocks": dict(sorted(codes.items(), key=lambda kv: -kv[1])),
           "tasks_by_dominant_conflict": {}, "tasks_with_any_consistent_block": sum(
               1 for t in per_task if t["status"]["PARTIAL"] + t["status"]["FULL"] > 0),
           "best_consistent_coverage_quartiles": None, "changed_share_quartiles": None}
    for t in per_task:
        agg["tasks_by_dominant_conflict"][str(t["dominant_conflict"])] = \
            agg["tasks_by_dominant_conflict"].get(str(t["dominant_conflict"]), 0) + 1

    def quart(xs):
        xs = sorted(xs)
        return [xs[int(q * (len(xs) - 1))] for q in (0.0, 0.25, 0.5, 0.75, 1.0)]
    agg["best_consistent_coverage_quartiles"] = quart([t["best_consistent_coverage"] for t in per_task])
    agg["changed_share_quartiles"] = quart([t["changed_share"] for t in per_task])
    out = {"aggregate": agg, "per_task_anonymous": sorted(per_task, key=lambda t: json.dumps(t, sort_keys=True))}
    with open(os.path.join(HERE, "outputs", "pilot_v1_dev", "frontier_census.json"), "w") as handle:
        json.dump(out, handle, indent=1, sort_keys=True)
    print(json.dumps(agg, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
