"""Single-task v2 debug runner with verbose output.

Usage:
    python scripts/debug_full_novel_v2_known_task.py 2a5f8217
    python scripts/debug_full_novel_v2_known_task.py --all-known
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from reasoning_project.adaptive_orchestrator import (
    GatedAdaptiveReasoningOrchestrator,
    OrchestratorConfig,
)
from reasoning_project.arc_adapter import load_arc_tasks

ARC_ROOT = Path(__file__).parent.parent / "data" / "arc"
OUTPUT_DIR = "outputs/full_novel_reasoning_pipeline_v2/debug"

KNOWN_TASKS = [
    "2a5f8217", "d89b689b", "e9ac8c9e", "a48eeaf7",
    "1d0a4b61", "8eb1be9a", "92e50de0", "a5313dff",
    "4347f46a", "50cb2852", "bb43febb",
]


def debug_task(task_id: str, tasks: dict, v1_results: dict) -> dict:
    print(f"\n{'='*60}")
    print(f"  DEBUG: {task_id}")
    print(f"{'='*60}")

    if task_id not in tasks:
        print(f"  ERROR: task {task_id} not found in ARC data")
        return {"task_id": task_id, "error": "not_found"}

    task = tasks[task_id]
    train_pairs = [(ex.input_grid, ex.output_grid) for ex in task.train if ex.output_grid is not None]
    test_inputs = [ex.input_grid for ex in task.test]
    test_outputs = [ex.output_grid for ex in task.test if ex.output_grid is not None] or None

    print(f"  Train pairs: {len(train_pairs)}")
    print(f"  Test inputs: {len(test_inputs)}")
    for i, (inp, out) in enumerate(train_pairs):
        print(f"    Pair {i}: {inp.shape} -> {out.shape}")

    config = OrchestratorConfig(
        timeout_per_task=420.0,
        output_dir=OUTPUT_DIR,
    )
    orch = GatedAdaptiveReasoningOrchestrator(config)

    print("\n  --- Task Analysis ---")
    analysis = orch.analyze_task(task_id, train_pairs)
    print(f"  Domain: {analysis.domain}")
    print(f"  Property trace: discriminative={analysis.property_trace.get('has_discriminative_property')}")
    if analysis.property_trace.get("best_property"):
        print(f"    Best property: {analysis.property_trace['best_property']} (score={analysis.property_trace.get('score', 0):.2f})")
    print(f"  Failure trace: {analysis.failure_trace.get('failure_type')}")
    print(f"  Candidate families: {analysis.candidate_operator_families}")

    print("\n  --- Module Routing ---")
    routes = orch._route_with_reasons(analysis)
    for module, (triggered, reason) in sorted(routes.items()):
        status = "TRIGGERED" if triggered else "SKIPPED"
        print(f"    {module}: {status} ({reason})")

    triggered_modules = [m for m, (t, _) in routes.items() if t]

    print(f"\n  --- Collecting Proposals (triggered: {len(triggered_modules)} modules) ---")
    t0 = time.time()
    proposals = orch.collect_proposals(analysis, triggered_modules, train_pairs, test_inputs)
    elapsed = time.time() - t0
    print(f"  Generated {len(proposals)} proposals in {elapsed:.1f}s")

    for i, p in enumerate(proposals):
        has_exec = False
        if isinstance(p.hypothesis, dict) and callable(p.hypothesis.get("execute")):
            has_exec = True
        elif callable(p.hypothesis):
            has_exec = True
        print(f"    [{i}] {p.module_name}/{p.proposal_type} "
              f"family={p.operator_family} conf={p.confidence:.2f} "
              f"executable={'YES' if has_exec else 'NO'}")

    print(f"\n  --- Ranking & Verification ---")
    ranked = orch.rank_proposals(proposals)

    verification = None
    selected = None
    final_status = "unsolved"

    for j, proposal in enumerate(ranked):
        outcome = orch.verifier.verify(proposal, train_pairs, test_inputs, test_outputs)
        status = "ACCEPTED" if outcome.accepted else f"REJECTED({outcome.rejection_reason})"
        print(f"    [{j}] {proposal.module_name}: {status}")
        if outcome.accepted:
            selected = proposal
            verification = outcome
            final_status = "solved"
            break

    if final_status != "solved" and proposals:
        final_status = "all_proposals_rejected"

    v1_solved = v1_results.get(task_id, {}).get("solved", False)

    print(f"\n  --- Result ---")
    print(f"  v1 solved: {v1_solved}")
    print(f"  v2 solved: {final_status == 'solved'}")
    if selected:
        print(f"  Selected: {selected.module_name}/{selected.operator_family}")
    if verification and verification.certificate_path:
        print(f"  Certificate: {verification.certificate_path}")
    if final_status != "solved":
        print(f"  Status: {final_status}")

    return {
        "task_id": task_id,
        "v1_solved": v1_solved,
        "v2_solved": final_status == "solved",
        "n_proposals": len(proposals),
        "n_executable": sum(
            1 for p in proposals
            if (isinstance(p.hypothesis, dict) and callable(p.hypothesis.get("execute")))
               or callable(p.hypothesis)
        ),
        "selected_module": selected.module_name if selected else None,
        "final_status": final_status,
    }


def load_v1_results(path="outputs/full_arc1000_novel_pipeline/progress.jsonl"):
    results = {}
    if not os.path.exists(path):
        return results
    with open(path) as f:
        for line in f:
            if line.strip():
                row = json.loads(line)
                row["solved"] = (
                    row.get("final_config_that_solved") is not None
                    or row.get("operator_promoted", False)
                    or row.get("solved_by_static", False)
                )
                results[row.get("task_id", "")] = row
    return results


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("task_ids", nargs="*", default=[])
    parser.add_argument("--all-known", action="store_true")
    args = parser.parse_args()

    task_ids = args.task_ids
    if args.all_known or not task_ids:
        task_ids = KNOWN_TASKS

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("Loading ARC tasks...")
    arc_tasks = load_arc_tasks(ARC_ROOT)
    tasks = {t.task_id: t for t in arc_tasks}
    print(f"  Loaded {len(tasks)} tasks")

    print("Loading v1 results...")
    v1_results = load_v1_results()
    print(f"  Loaded {len(v1_results)} v1 results")

    results = []
    for tid in task_ids:
        r = debug_task(tid, tasks, v1_results)
        results.append(r)

    print(f"\n{'='*60}")
    print(f"  SUMMARY")
    print(f"{'='*60}")
    solved = sum(1 for r in results if r.get("v2_solved"))
    v1_solved = sum(1 for r in results if r.get("v1_solved"))
    print(f"  Tasks: {len(results)}")
    print(f"  v1 solved: {v1_solved}")
    print(f"  v2 solved: {solved}")
    print(f"  v2 with executable proposals: {sum(1 for r in results if r.get('n_executable', 0) > 0)}")

    for r in results:
        marker = "OK" if r.get("v2_solved") else ("REGRESSION" if r.get("v1_solved") else "MISS")
        print(f"    {r['task_id']}: {marker} (proposals={r.get('n_proposals',0)}, "
              f"executable={r.get('n_executable',0)}, v1={r.get('v1_solved')}, "
              f"module={r.get('selected_module', 'none')})")

    with open(os.path.join(OUTPUT_DIR, "debug_results.json"), "w") as f:
        json.dump(results, f, indent=2)


if __name__ == "__main__":
    main()
