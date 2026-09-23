"""The SAME prospective audit, run against the repaired full-engine channel.

Same 12 dev tasks, same 8 s budget, same goal type, same frontier cap, same
preregistered thresholds, same reported fields as
scripts/audit_failure_frontier.py. Measurement only: nothing is proposed,
constructed, installed, trained, ablated or scored, and no test output is
read.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from cora_arc2026 import engine_trace as ET                      # noqa: E402
from cora_arc2026.vendor import tfg_extractor as X               # noqa: E402

TASKS = os.path.join(HERE, "data", "arc", "dev60_challenges.json")
OUT = os.path.join(HERE, "outputs", "frontier_audit")
N_TASKS = 12
BUDGET_S = float(os.environ.get("ARC_META_BUDGET_S", "8"))


def audit_one(task_id, pairs):
    got = ET.extract(task_id, pairs, budget_s=BUDGET_S)
    observer, tfg, census = got["observer"], got["tfg"], got["census"]
    eligible = [(a, o) for a, o in observer.candidates
                if o in X.FRONTIER_OUTCOMES]
    record = {
        "task_id": task_id,
        "n_demonstrations": len(pairs),
        "baseline_failure": not got["solved"],
        "solved_by_full_engine": got["solved"],
        "extraction_seconds": round(got["seconds"], 3),
        "observer_candidate_events": len(observer.candidates),
        "observer_census": census,
        "frontier_eligible_events": len(eligible),
        "frontier_eligible_distinct_asts":
            len({X._canonical_ast(a) for a, _ in eligible}),
        "truncations": sorted(observer.truncations),
    }
    kinds = {}
    for node in tfg.nodes():
        kinds[node.kind] = kinds.get(node.kind, 0) + 1
    frontier = [n for n in tfg.nodes() if n.kind == "frontier_term"]
    vsigs = [n for n in tfg.nodes() if n.kind == "value_signature"]
    evidence = ET.engine_value_evidence(observer, pairs)
    record.update({
        "total_tfg_nodes": len(tfg.nodes()),
        "node_kinds": kinds,
        "goal_type": tfg.interface()[1],
        "frontier_term_count": len(frontier),
        "frontier_result_types": sorted({(n.type_str or "<none>")
                                         for n in frontier}),
        "frontier_outcomes": sorted({n.attrs.get("outcome")
                                     for n in frontier}),
        "frontier_ops": sorted({n.attrs.get("op") for n in frontier}),
        "frontier_distinct_asts": len({n.attrs.get("ast") for n in frontier}),
        "executed_nonexact_in_frontier":
            sum(1 for n in frontier
                if n.attrs.get("outcome") == "executed_not_exact"),
        "slot_failed_in_frontier":
            sum(1 for n in frontier
                if n.attrs.get("outcome") == "slot_fit_failed"),
        "typed_events": census.get("typed", 0),
        "slot_fit_ok_events": census.get("slot_fit_ok", 0),
        "executed_not_exact_events": census.get("executed_not_exact", 0),
        "exact_events": census.get("exact", 0),
        "value_signature_nodes": len(vsigs),
        "value_signatures_defined":
            len([n for n in vsigs if n.attrs.get("defined")]),
        "engine_value_evidence_rows": len(evidence),
        "engine_value_evidence_defined":
            len([r for r in evidence if r.get("defined")]),
        "engine_value_evidence_sample": evidence[:3],
        "palette_change_nodes": kinds.get("palette_change", 0),
        "shape_change_nodes": kinds.get("shape_change", 0),
        "delta_signature_nodes": kinds.get("delta_signature", 0),
        "slot_aggregate_nodes": kinds.get("slot", 0),
        "cause_nodes": kinds.get("cause", 0),
    })
    return record


def main():
    with open(TASKS) as handle:
        tasks = json.load(handle)
    chosen = sorted(tasks)[:N_TASKS]
    os.makedirs(OUT, exist_ok=True)
    records = []
    for index, task_id in enumerate(chosen, 1):
        pairs = [(p["input"], p["output"]) for p in tasks[task_id]["train"]]
        record = audit_one(task_id, pairs)
        records.append(record)
        print(f"[{index:2d}/{len(chosen)}] {task_id} "
              f"events={record['observer_candidate_events']} "
              f"frontier={record['frontier_term_count']} "
              f"exec_nonexact={record['executed_not_exact_events']} "
              f"eng_defined={record['engine_value_evidence_defined']} "
              f"{record['extraction_seconds']}s", flush=True)
    path = os.path.join(OUT, "frontier_audit_v2_records.json")
    with open(path, "w") as handle:
        json.dump({"selection": "first 12 dev60 ids, ascending",
                   "channel": "repaired full-engine trace",
                   "budget_s": BUDGET_S,
                   "event_mapping": ET.EVENT_MAPPING,
                   "unmapped": ET.UNMAPPED,
                   "records": records}, handle, indent=1, default=str)
    print("wrote", path)


if __name__ == "__main__":
    main()
