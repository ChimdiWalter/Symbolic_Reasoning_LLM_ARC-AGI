#!/usr/bin/env python3
"""Debug known frontier tasks through the v2 orchestrator after executable proposal repair.

For each known frontier task:
- expected operator family
- module triggered?
- proposal executable?
- verifier accepted?
- prediction correct?
- certificate emitted?
- failure reason
"""
import csv
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reasoning_project.adaptive_orchestrator import (
    GatedAdaptiveReasoningOrchestrator,
    OrchestratorConfig,
)

OUTPUT_DIR = "outputs/full_novel_reasoning_pipeline_v2/executable_proposal_repair"

KNOWN_TASKS = {
    # shape completion
    "1d0a4b61": "shape_completion",
    "8eb1be9a": "shape_completion",
    "92e50de0": "shape_completion",
    "a5313dff": "shape_completion",
    # position recolor
    "4347f46a": "position_within_object_recolor",
    "50cb2852": "position_within_object_recolor",
    "bb43febb": "position_within_object_recolor",
    # many-to-few
    "56ff96f3": "many_to_few_grouping",
}


def load_arc_tasks():
    # Try combined JSON format first (arc-agi_training_challenges.json + solutions)
    base = Path(__file__).resolve().parent.parent
    for arc_dir in [base / "data" / "arc", base / "data"]:
        challenges = arc_dir / "arc-agi_training_challenges.json"
        solutions = arc_dir / "arc-agi_training_solutions.json"
        if challenges.exists():
            with open(challenges) as f:
                chal = json.load(f)
            sol = {}
            if solutions.exists():
                with open(solutions) as f:
                    sol = json.load(f)
            tasks = {}
            for tid, tdata in chal.items():
                task = {"train": tdata["train"], "test": []}
                test_entries = tdata.get("test", [])
                sol_entries = sol.get(tid, [])
                for i, te in enumerate(test_entries):
                    entry = {"input": te["input"]}
                    if i < len(sol_entries):
                        entry["output"] = sol_entries[i]
                    elif "output" in te:
                        entry["output"] = te["output"]
                    task["test"].append(entry)
                tasks[tid] = task
            print(f"Loaded {len(tasks)} tasks from {challenges}")
            return tasks

    # Fallback: per-task JSON files
    for candidate in [base / "data" / "arc" / "training", base / "data" / "training"]:
        if candidate.exists():
            tasks = {}
            for f in sorted(candidate.glob("*.json")):
                tasks[f.stem] = json.load(open(f))
            return tasks

    print("ERROR: Cannot find ARC task directory")
    return {}


def debug_task(task_id, task, expected_family):
    """Debug a single task through the full v2 orchestrator."""
    train_pairs = [
        (np.array(ex["input"]), np.array(ex["output"]))
        for ex in task["train"]
    ]
    test_inputs = [np.array(ex["input"]) for ex in task["test"]]
    test_outputs = [np.array(ex["output"]) for ex in task["test"]]

    config = OrchestratorConfig(timeout_per_task=300.0)
    orch = GatedAdaptiveReasoningOrchestrator(config)

    print(f"\n{'='*60}")
    print(f"Task: {task_id}  Expected family: {expected_family}")
    print(f"{'='*60}")

    # Analysis
    analysis = orch.analyze_task(task_id, train_pairs)
    print(f"  Candidate families: {analysis.candidate_operator_families}")
    print(f"  Has discriminative property: {analysis.property_trace.get('has_discriminative_property')}")
    print(f"  Best property: {analysis.property_trace.get('best_property')}")
    print(f"  Failure type: {analysis.failure_trace.get('failure_type')}")

    # Routing
    routes = orch._route_with_reasons(analysis)
    triggered = [m for m, (t, _) in routes.items() if t]
    print(f"  Triggered modules: {triggered}")
    frontier_triggered = "frontier_operators" in triggered
    print(f"  Frontier operators triggered: {frontier_triggered}")

    # Proposals
    t0 = time.time()
    deadline = t0 + 300.0
    proposals = orch.collect_proposals(analysis, triggered, train_pairs, test_inputs, deadline=deadline)
    t_proposals = time.time() - t0
    print(f"  Total proposals: {len(proposals)} ({t_proposals:.1f}s)")

    frontier_proposals = [p for p in proposals if p.module_name == "frontier_operators"]
    print(f"  Frontier proposals: {len(frontier_proposals)}")

    for p in proposals:
        has_exec = False
        if callable(p.hypothesis):
            has_exec = True
        elif isinstance(p.hypothesis, dict) and callable(p.hypothesis.get("execute")):
            has_exec = True
        family = p.operator_family or "?"
        print(f"    [{p.module_name}] family={family} conf={p.confidence:.2f} exec={has_exec}")

    # Verification
    ranked = orch.rank_proposals(proposals)
    accepted = None
    verification = None
    all_rejections = []

    for p in ranked:
        outcome = orch.verifier.verify(p, train_pairs, test_inputs, test_outputs)
        if outcome.accepted:
            accepted = p
            verification = outcome
            print(f"  ACCEPTED: [{p.module_name}] family={p.operator_family}")
            print(f"    train_consistent={outcome.train_consistent}")
            print(f"    loo_passed={outcome.loo_passed}")
            print(f"    falsification_passed={outcome.falsification_passed}")
            print(f"    certificate={outcome.certificate_path}")
            print(f"    false_positive={outcome.false_positive}")
            break
        else:
            all_rejections.append({
                "module": p.module_name,
                "family": p.operator_family,
                "reason": outcome.rejection_reason,
                "fp": outcome.false_positive,
            })

    if not accepted:
        print(f"  NOT SOLVED. Rejections:")
        for rej in all_rejections[:5]:
            print(f"    [{rej['module']}] family={rej['family']} reason={rej['reason']} fp={rej['fp']}")

    result = {
        "task_id": task_id,
        "expected_family": expected_family,
        "candidate_families": analysis.candidate_operator_families,
        "frontier_triggered": frontier_triggered,
        "n_proposals": len(proposals),
        "n_frontier_proposals": len(frontier_proposals),
        "n_executable": sum(
            1 for p in proposals
            if (callable(p.hypothesis) or
                (isinstance(p.hypothesis, dict) and callable(p.hypothesis.get("execute"))))
        ),
        "solved": accepted is not None,
        "solved_by": accepted.module_name if accepted else None,
        "solved_family": accepted.operator_family if accepted else None,
        "false_positive": verification.false_positive if verification else False,
        "certificate": verification.certificate_path if verification else None,
        "failure_reason": all_rejections[0]["reason"] if all_rejections and not accepted else None,
        "runtime_s": time.time() - t0,
    }
    return result


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("Loading ARC tasks...")
    tasks = load_arc_tasks()
    if not tasks:
        return

    results = []
    for tid, expected_family in KNOWN_TASKS.items():
        if tid not in tasks:
            print(f"\nWARNING: {tid} not found in dataset, skipping")
            results.append({
                "task_id": tid, "expected_family": expected_family,
                "solved": False, "failure_reason": "task_not_found",
            })
            continue
        result = debug_task(tid, tasks[tid], expected_family)
        results.append(result)

    # Write CSV
    csv_path = os.path.join(OUTPUT_DIR, "frontier_known_task_debug.csv")
    fieldnames = [
        "task_id", "expected_family", "frontier_triggered", "n_proposals",
        "n_frontier_proposals", "n_executable", "solved", "solved_by",
        "solved_family", "false_positive", "certificate", "failure_reason", "runtime_s",
    ]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)

    # Write markdown
    md_path = os.path.join(OUTPUT_DIR, "frontier_known_task_debug.md")
    with open(md_path, "w") as f:
        f.write("# Frontier Known Task Debug Report\n\n")
        f.write(f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        solved = [r for r in results if r.get("solved")]
        unsolved = [r for r in results if not r.get("solved")]
        fp = [r for r in results if r.get("false_positive")]

        f.write(f"## Summary\n\n")
        f.write(f"- Tasks tested: {len(results)}\n")
        f.write(f"- Solved: {len(solved)}\n")
        f.write(f"- Unsolved: {len(unsolved)}\n")
        f.write(f"- False positives: {len(fp)}\n\n")

        f.write("## Per-Task Results\n\n")
        f.write("| Task | Expected | Frontier? | Props | Exec | Solved | By | FP | Reason |\n")
        f.write("|------|----------|-----------|-------|------|--------|----|----|--------|\n")
        for r in results:
            f.write(f"| {r['task_id']} "
                    f"| {r.get('expected_family', '?')} "
                    f"| {r.get('frontier_triggered', '?')} "
                    f"| {r.get('n_proposals', 0)} "
                    f"| {r.get('n_executable', 0)} "
                    f"| {r.get('solved', False)} "
                    f"| {r.get('solved_by', '-')} "
                    f"| {r.get('false_positive', False)} "
                    f"| {r.get('failure_reason', '-')} |\n")

        if solved:
            f.write("\n## Solved Tasks\n\n")
            for r in solved:
                f.write(f"- **{r['task_id']}**: solved by {r['solved_by']} "
                        f"(family={r.get('solved_family')}, "
                        f"cert={r.get('certificate', 'none')})\n")

        if unsolved:
            f.write("\n## Unsolved Tasks\n\n")
            for r in unsolved:
                f.write(f"- **{r['task_id']}**: {r.get('failure_reason', 'unknown')}\n")
                f.write(f"  - Expected: {r.get('expected_family')}\n")
                f.write(f"  - Frontier triggered: {r.get('frontier_triggered')}\n")
                f.write(f"  - Proposals: {r.get('n_proposals', 0)} total, "
                        f"{r.get('n_executable', 0)} executable\n")

    print(f"\n{'='*60}")
    print(f"Results: {len(solved)}/{len(results)} solved, {len(fp)} FP")
    print(f"Written to {csv_path} and {md_path}")


if __name__ == "__main__":
    main()
