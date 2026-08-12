"""Train neural abstraction components on near-solved failure states."""
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
    _classify_kept_removed,
)
from reasoning_project.adaptive_loop import AdaptiveReasoningLoop
from reasoning_project.manifold_memory import MemoryManifold
from reasoning_project.near_solved_memory import NearSolvedMemory
from reasoning_project.events import ReasoningEventLog


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
    parser.add_argument("--output-dir", default="outputs/neural_abstraction")
    parser.add_argument("--max-tasks", type=int, default=0)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()

    out = args.output_dir
    os.makedirs(out, exist_ok=True)

    tasks = load_arc_tasks(args.arc_root)
    if args.max_tasks > 0:
        tasks = tasks[:args.max_tasks]
    print(f"Loaded {len(tasks)} ARC tasks", flush=True)

    # Phase 1: Build near-solved states
    print("\n=== Phase 1: Build near-solved states ===", flush=True)
    memory = ReasoningMemory()
    manifold = MemoryManifold()
    ns_mem = NearSolvedMemory(manifold)
    event_log = ReasoningEventLog()

    loop = AdaptiveReasoningLoop(
        max_iterations=4,
        timeout_seconds=15.0,
        memory=memory,
        manifold=manifold,
        near_solved_memory=ns_mem,
        event_log=event_log,
    )

    solved_ids = []
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
                solved_ids.append(task["task_id"])
        if (i + 1) % 100 == 0:
            print(f"  {i+1}/{len(tasks)} solved={len(solved_ids)}", flush=True)

    print(f"Phase 1: {len(solved_ids)} solved, "
          f"{len(ns_mem.states)} near-solved", flush=True)

    # Phase 2: Build training data for neural components
    print("\n=== Phase 2: Preparing training data ===", flush=True)
    adapter = GridDomainAdapter()
    training_examples = []

    for tid, state in ns_mem.states.items():
        if state.status == "solved":
            continue
        task = next((t for t in tasks if t["task_id"] == tid), None)
        if task is None:
            continue
        for inp, out_grid in task["train_pairs"]:
            objects = adapter.extract_objects(inp)
            cls = _classify_kept_removed(objects, inp, out_grid)
            if cls is None:
                continue
            kept, removed = cls
            if not kept or not removed:
                continue
            training_examples.append({
                "task_id": tid,
                "objects": objects,
                "kept": kept,
                "removed": removed,
                "failure_type": state.failure_type,
                "grid_shape": inp.shape,
            })

    print(f"  {len(training_examples)} training examples from "
          f"{len(ns_mem.states)} near-solved states", flush=True)

    # Phase 3: Run neural abstraction pipeline
    print("\n=== Phase 3: Neural abstraction pipeline ===", flush=True)
    try:
        from reasoning_project.neural_abstraction import NeuralAbstractionPipeline
        pipeline = NeuralAbstractionPipeline(device=args.device)
        result = pipeline.run_abstraction_pipeline(
            ns_mem, tasks, event_log=event_log,
        )
        with open(os.path.join(out, "abstraction_result.json"), "w") as f:
            json.dump(result, f, indent=2, default=str)
        print(f"  Proposed: {result.get('n_proposed', 0)}", flush=True)
        print(f"  Validated: {result.get('n_validated', 0)}", flush=True)
        print(f"  Registered: {result.get('n_registered', 0)}", flush=True)
    except ImportError:
        print("  neural_abstraction module not yet available", flush=True)
    except Exception as e:
        print(f"  Neural abstraction failed: {e}", flush=True)

    # Phase 4: Resume near-solved tasks
    print("\n=== Phase 4: Resume near-solved tasks ===", flush=True)
    promoted = []
    false_positives = []
    t0 = time.perf_counter()

    resume_tasks = [
        t for t in tasks
        if t["task_id"] in ns_mem.states
        and ns_mem.states[t["task_id"]].status != "solved"
    ]

    for i, task in enumerate(resume_tasks):
        tid = task["task_id"]
        rs = ns_mem.resume_from_state(tid)
        if rs is None:
            continue
        result = loop.solve(
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

    print(f"Phase 4: {len(promoted)} promoted, "
          f"{len(false_positives)} FP", flush=True)

    # Write final report
    summary = {
        "solved_before": len(solved_ids),
        "near_solved": len(ns_mem.states),
        "training_examples": len(training_examples),
        "promoted": promoted,
        "n_promoted": len(promoted),
        "false_positives": false_positives,
        "n_false_positives": len(false_positives),
    }
    with open(os.path.join(out, "neural_abstraction_summary.json"), "w") as f:
        json.dump(summary, f, indent=2, default=str)

    # Export event log
    event_log.export_jsonl(os.path.join(out, "events.jsonl"))

    print(f"\nWrote results to {out}/", flush=True)


if __name__ == "__main__":
    main()
