"""Measure what the EXISTING failure path puts into a Typed Failure Graph.

Measurement only. Nothing is proposed, installed, trained or scored. The
components are imported unmodified; this script only counts what passes
between them, at four points:

    1. TraceObserver.candidate events, by outcome
    2. of those, the outcomes the extractor treats as frontier-eligible
    3. what frontier_candidates() actually yields after dedup and the cap
    4. frontier_term nodes present in the finished ConcreteTFG

Test outputs are never read: the challenge file contains none.
"""
import json
import os
import sys
import time

TTI = "/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_tti"
sys.path.insert(0, TTI)

import numpy as np                                               # noqa: E402
from level4_blind_runtime import env as E                        # noqa: E402
from level4_blind_runtime import runtime as V                    # noqa: E402
from level4_blind_runtime import stepA_trace_search as TS        # noqa: E402
from cora_tti import tfg_extractor as X                          # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TASKS = os.path.join(HERE, "data", "arc", "dev60_challenges.json")
OUT = os.path.join(HERE, "outputs", "frontier_audit")
N_TASKS = 12


def audit_one(task_id, pairs):
    env = E.BASE_ENV
    pairs = [(np.asarray(a), np.asarray(b)) for a, b in pairs]
    observer = TS.TraceObserver()
    TS.set_observer(observer)
    started = time.monotonic()
    try:
        deadline = time.monotonic() + float(os.environ.get("ARC_META_BUDGET_S", "8"))
        results, stats = TS.search(pairs, deadline=deadline, env=env)
    finally:
        TS.set_observer(None)
    elapsed = time.monotonic() - started

    # stage 1: every candidate event the observer recorded
    census = {}
    for _, outcome in observer.candidates:
        census[outcome] = census.get(outcome, 0) + 1

    # stage 2: the subset the extractor's frontier definition admits
    eligible = [(a, o) for a, o in observer.candidates
                if o in X.FRONTIER_OUTCOMES]
    eligible_distinct = len({X._canonical_ast(a) for a, _ in eligible})

    record = {
        "task_id": task_id,
        "n_demonstrations": len(pairs),
        "baseline_failure": not bool(results),
        "solved_by_blind_runtime": bool(results),
        "extraction_seconds": round(elapsed, 3),
        "observer_candidate_events": len(observer.candidates),
        "observer_census": census,
        "frontier_eligible_events": len(eligible),
        "frontier_eligible_distinct_asts": eligible_distinct,
        "truncations": sorted(observer.truncations),
        "search_stats": {"typed": int(stats.typed),
                         "generated": int(stats.generated),
                         "rejected": int(stats.rejected),
                         "max_depth": int(stats.max_depth),
                         "semantic_classes": int(stats.semantic_classes)},
    }
    if results:
        record["tfg"] = None
        return record

    # stage 3 + 4: the finished graph
    tfg = X.build_tfg(pairs, stats, observer, env, "Grid", X.MAX_FRONTIER_TERMS)
    kinds = {}
    for node in tfg.nodes():
        kinds[node.kind] = kinds.get(node.kind, 0) + 1
    frontier = [n for n in tfg.nodes() if n.kind == "frontier_term"]
    vsigs = [n for n in tfg.nodes() if n.kind == "value_signature"]
    defined = [n for n in vsigs if n.attrs.get("defined")]
    record.update({
        "total_tfg_nodes": len(tfg.nodes()),
        "node_kinds": kinds,
        "goal_type": tfg.interface()[1],
        "frontier_term_count": len(frontier),
        "frontier_result_types": sorted({(n.type_str or "<none>")
                                         for n in frontier}),
        "frontier_outcomes": sorted({n.attrs.get("outcome") for n in frontier}),
        "frontier_ops": sorted({n.attrs.get("op") for n in frontier}),
        "frontier_distinct_asts": len({n.attrs.get("ast") for n in frontier}),
        "frontier_max_surface_nodes": max([n.attrs.get("surface_nodes", 0)
                                           for n in frontier], default=0),
        "executed_nonexact_in_frontier":
            sum(1 for n in frontier if n.attrs.get("outcome") == "executed_not_exact"),
        "slot_failed_in_frontier":
            sum(1 for n in frontier if n.attrs.get("outcome") == "slot_fit_failed"),
        "value_signature_nodes": len(vsigs),
        "value_signatures_defined": len(defined),
        "slot_aggregate_nodes": kinds.get("slot", 0),
        "palette_change_nodes": kinds.get("palette_change", 0),
        "shape_change_nodes": kinds.get("shape_change", 0),
        "delta_signature_nodes": kinds.get("delta_signature", 0),
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
              f"eligible={record['frontier_eligible_events']} "
              f"frontier={record.get('frontier_term_count')} "
              f"vsig_defined={record.get('value_signatures_defined')} "
              f"{record['extraction_seconds']}s", flush=True)
    path = os.path.join(OUT, "frontier_audit_records.json")
    with open(path, "w") as handle:
        json.dump({"selection": "first 12 dev60 ids, ascending",
                   "budget_s": float(os.environ.get("ARC_META_BUDGET_S", "8")),
                   "records": records}, handle, indent=1, default=str)
    print("wrote", path)


if __name__ == "__main__":
    main()
