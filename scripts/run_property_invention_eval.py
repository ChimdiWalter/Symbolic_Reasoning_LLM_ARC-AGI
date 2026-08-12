"""Property invention evaluation: mine failures, propose properties, validate, measure promotions."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reasoning_project.reasoning_engine import (
    GridDomainAdapter,
    ReasoningMemory,
    StructuralReasoner,
)
from reasoning_project.adaptive_loop import AdaptiveReasoningLoop
from reasoning_project.manifold_memory import MemoryManifold
from reasoning_project.near_solved_memory import NearSolvedMemory
from reasoning_project.events import ReasoningEventLog
from reasoning_project.property_invention import PropertyInventor


def load_arc_tasks(root: str):
    tasks = []
    challenges_path = os.path.join(root, "arc-agi_training_challenges.json")
    solutions_path = os.path.join(root, "arc-agi_training_solutions.json")
    if not os.path.isfile(challenges_path):
        return tasks
    with open(challenges_path) as f:
        challenges = json.load(f)
    solutions = {}
    if os.path.isfile(solutions_path):
        with open(solutions_path) as f:
            solutions = json.load(f)
    for task_id in sorted(challenges.keys()):
        data = challenges[task_id]
        train_pairs = [
            (np.array(ex["input"]), np.array(ex["output"]))
            for ex in data["train"]
        ]
        test_inputs = [np.array(ex["input"]) for ex in data["test"]]
        test_outputs = []
        if task_id in solutions:
            test_outputs = [np.array(o) for o in solutions[task_id]]
        elif data["test"] and "output" in data["test"][0]:
            test_outputs = [np.array(ex["output"]) for ex in data["test"]]
        if test_outputs:
            tasks.append({
                "task_id": task_id,
                "train_pairs": train_pairs,
                "test_inputs": test_inputs,
                "test_outputs": test_outputs,
            })
    return tasks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--arc-root", default="data/arc")
    parser.add_argument("--output-dir", default="outputs/property_invention")
    parser.add_argument("--max-tasks", type=int, default=0)
    parser.add_argument("--use-cache", default="",
                        help="Load Phase 1 near-solved cache from this dir")
    args = parser.parse_args()

    out = args.output_dir
    os.makedirs(out, exist_ok=True)

    event_log = ReasoningEventLog()

    tasks = load_arc_tasks(args.arc_root)
    if args.max_tasks > 0:
        tasks = tasks[:args.max_tasks]
    print(f"Loaded {len(tasks)} ARC tasks", flush=True)

    # Phase 1: Build near-solved states (or load from cache)
    print("\n=== Phase 1: Build near-solved states ===", flush=True)
    memory = ReasoningMemory()
    manifold = MemoryManifold()

    if args.use_cache:
        from reasoning_project.near_solved_memory import load_near_solved_cache
        ns_mem, solved_before, _ = load_near_solved_cache(args.use_cache)
        print(f"  Loaded cache: {len(ns_mem.states)} near-solved, "
              f"{len(solved_before)} solved", flush=True)
        phase1_time = 0.0
    else:
        ns_mem = NearSolvedMemory(manifold)
        loop = AdaptiveReasoningLoop(
            max_iterations=4,
            timeout_seconds=15.0,
            memory=memory,
            manifold=manifold,
            near_solved_memory=ns_mem,
            event_log=event_log,
        )

        solved_before = []
        t0 = time.perf_counter()
        for i, task in enumerate(tasks):
            result = loop.solve(
                task["train_pairs"], task["test_inputs"],
                task_id=task["task_id"],
            )
            if result.solved and result.predictions is not None:
                correct = all(
                    np.array_equal(p, e)
                    for p, e in zip(result.predictions, task["test_outputs"])
                )
                if correct:
                    solved_before.append(task["task_id"])
            if (i + 1) % 100 == 0:
                print(f"  {i+1}/{len(tasks)} ({time.perf_counter()-t0:.0f}s, "
                      f"solved={len(solved_before)}, "
                      f"near-solved={len(ns_mem.states)})", flush=True)

        phase1_time = time.perf_counter() - t0

    print(f"Phase 1: {len(solved_before)} solved, "
          f"{len(ns_mem.states)} near-solved, {phase1_time:.0f}s", flush=True)

    # Phase 2: Property invention
    print("\n=== Phase 2: Property invention ===", flush=True)
    inventor = PropertyInventor()
    t0 = time.perf_counter()
    invention_result = inventor.run_full_pipeline(ns_mem, tasks)
    phase2_time = time.perf_counter() - t0

    n_proposed = invention_result.get("n_proposed", 0)
    n_validated = invention_result.get("n_validated", 0)
    n_registered = invention_result.get("n_registered", 0)
    print(f"Phase 2: {n_proposed} proposed, {n_validated} validated, "
          f"{n_registered} registered, {phase2_time:.0f}s", flush=True)

    # Phase 3: Resume with invented properties
    print("\n=== Phase 3: Resume near-solved tasks ===", flush=True)
    promoted = []
    false_positives = []
    t0 = time.perf_counter()

    resume_tasks = [
        t for t in tasks
        if t["task_id"] in ns_mem.states
        and ns_mem.states[t["task_id"]].status != "solved"
    ]
    print(f"  Resuming {len(resume_tasks)} tasks", flush=True)

    resume_loop = AdaptiveReasoningLoop(
        max_iterations=4,
        timeout_seconds=15.0,
        memory=memory,
        manifold=manifold,
        near_solved_memory=ns_mem,
        event_log=event_log,
    )

    for i, task in enumerate(resume_tasks):
        tid = task["task_id"]
        rs = ns_mem.resume_from_state(tid)
        if rs is None:
            continue
        result = resume_loop.solve(
            task["train_pairs"], task["test_inputs"],
            task_id=tid, resume_from=rs,
        )
        if result.solved and result.predictions is not None:
            correct = all(
                np.array_equal(p, e)
                for p, e in zip(result.predictions, task["test_outputs"])
            )
            if correct:
                promoted.append(tid)
                ns_mem.promote_to_solved(tid, result.hypothesis or {})
            else:
                false_positives.append(tid)
        if (i + 1) % 100 == 0:
            print(f"  {i+1}/{len(resume_tasks)} "
                  f"(promoted={len(promoted)}, fp={len(false_positives)})",
                  flush=True)

    phase3_time = time.perf_counter() - t0
    print(f"Phase 3: {len(promoted)} promoted, "
          f"{len(false_positives)} FP, {phase3_time:.0f}s", flush=True)

    # Write report
    report = {
        "property_language_failures_analyzed": len(ns_mem.states),
        "solved_before_invention": len(solved_before),
        "n_near_solved": len(ns_mem.states),
        "n_proposed": n_proposed,
        "n_validated": n_validated,
        "n_registered": n_registered,
        "n_promoted": len(promoted),
        "promoted_tasks": promoted,
        "n_false_positives": len(false_positives),
        "false_positive_tasks": false_positives,
        "invented_properties": invention_result.get("properties", []),
        "phase1_time": phase1_time,
        "phase2_time": phase2_time,
        "phase3_time": phase3_time,
    }
    with open(os.path.join(out, "property_invention_summary.json"), "w") as f:
        json.dump(report, f, indent=2, default=str)

    # Markdown report
    lines = [
        "# Property Invention Report\n",
        f"**Property-language failures analyzed**: {len(ns_mem.states)}",
        f"**Solved before invention**: {len(solved_before)}",
        "",
        "## Invention Results\n",
        f"- Properties proposed: {n_proposed}",
        f"- Properties validated (LOO): {n_validated}",
        f"- Properties registered: {n_registered}",
        "",
        "## Promotion Results\n",
        f"- Tasks resumed: {len(resume_tasks)}",
        f"- **Tasks promoted**: {len(promoted)}",
        f"- False positives: {len(false_positives)}",
        "",
    ]
    if promoted:
        lines.append("### Promoted Tasks\n")
        for tid in promoted:
            lines.append(f"- `{tid}`")
    else:
        lines.append("No tasks were promoted from near-solved to solved.")
        lines.append("The cumulative reasoning infrastructure is implemented, "
                      "but empirical promotion remains blocked by property-language "
                      "expressiveness.")

    with open(os.path.join(out, "property_invention_report.md"), "w") as f:
        f.write("\n".join(lines))

    print(f"\nWrote results to {out}/", flush=True)


if __name__ == "__main__":
    main()
