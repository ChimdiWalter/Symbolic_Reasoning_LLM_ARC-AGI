"""Freeze the object arms' source-half costs into a packaged record (amendment 3), so that a kernel can compute the
matched static allowances of arms 4b and 4c without study A's controller records.

    python -I run.py object_costs OUT_JSON

Per benchmark: study A's controller CPU summed over every source task (the holes the object step uses come from it;
read from study A's `feasibility/controller_source_shard{0,1}.jsonl`, whose digests are recorded), and the builder's
recorded construction, gate and combined-check CPU for the frozen registry (read from the pinned
`runs/v2/<benchmark>/registry.json`, whose digest is checked against the freeze slot); the total is the arms' source
cost in Athe CPU-seconds. `ngb/object_arm.py` reads this record (in Athe and in a package alike).
"""
import json
import os
import sys

from ngb import env as E, object_arm as OA
from ngrow import data as DT


def main(out_path):
    shards = [os.path.join(E.STUDY_A, "feasibility", f"controller_source_shard{i}.jsonl") for i in (0, 1)]
    ctrl, seen = {}, {}
    for p in shards:
        with open(p, encoding="utf-8") as f:
            for x in f:
                if x.strip():
                    r = json.loads(x)
                    if r["task"] in seen:
                        raise SystemExit(f"duplicate controller row for {r['task']}")
                    seen[r["task"]] = r["bench"]
                    ctrl[r["bench"]] = ctrl.get(r["bench"], 0.0) + r["cpu_s"]
    out = {"unit": "Athe CPU-seconds", "controller_records_sha256": {os.path.relpath(p, E.REPO): E.sha_file(p)
                                                                     for p in shards},
           "benchmarks": {}}
    for b in DT.BENCHMARKS:
        src = {t for _, _, t in DT.half("source", (b,))}
        if {t for t, bb in seen.items() if bb == b} != src:
            raise SystemExit(f"{b}: controller records do not cover exactly the source half")
        d = OA.registry_doc(b)
        parts = {"controller_cpu_s": round(ctrl[b], 3), "construction_cpu_s": d["construction_cpu_s"],
                 "gate_cpu_s_distinct": d["gate_cpu_s_distinct"],
                 "combined_regression_cpu_s": d["combined_regression_cpu_s"]}
        out["benchmarks"][b] = dict(parts, source_cost_cpu_s=round(sum(parts.values()), 3),
                                    source_tasks=len(src), registry_sha256=E.sha_file(OA.registry_path(b)))
    E.dump(os.path.abspath(out_path), out)
    print(json.dumps({b: v["source_cost_cpu_s"] for b, v in out["benchmarks"].items()}))


if __name__ == "__main__":
    main(*sys.argv[1:])
