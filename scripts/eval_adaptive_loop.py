#!/usr/bin/env python3
"""Evaluate AdaptiveReasoningLoop vs static PortfolioSolver on ARC + ConceptARC.

Compares:
1. Static PortfolioSolver (single view, no iteration)
2. AdaptiveReasoningLoop (multi-view, iterative, invariant-guided, memory-backed)

Reports: solve rate, unique solves, view usage, iteration distribution, timing.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import numpy as np
from reasoning_project.arc_adapter import load_arc_tasks, load_conceptarc_tasks
from reasoning_project.reasoning_engine import (
    GridDomainAdapter,
    ReasoningMemory,
    StructuralReasoner,
)
from reasoning_project.adaptive_loop import (
    AdaptiveReasoningLoop,
    LoopResult,
)
from reasoning_project.manifold_memory import MemoryManifold

ARC_ROOT = Path(__file__).resolve().parent.parent / "data" / "arc"
CONCEPTARC_ROOT = Path(__file__).resolve().parent.parent / "data" / "conceptarc"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "outputs" / "adaptive_eval"


def eval_static(tasks, label="ARC"):
    """Run static StructuralReasoner (single GridDomainAdapter view)."""
    adapter = GridDomainAdapter()
    memory = ReasoningMemory()
    reasoner = StructuralReasoner(adapter, memory=memory)
    solved_ids = []
    fp_ids = []
    t0 = time.perf_counter()

    for i, task in enumerate(tasks):
        train_pairs = [(ex.input_grid, ex.output_grid) for ex in task.train]
        test_inputs = [ex.input_grid for ex in task.test]
        test_outputs = [ex.output_grid for ex in task.test if ex.output_grid is not None]

        result = reasoner.solve(train_pairs, test_inputs)
        if result is not None:
            predictions, meta = result
            if test_outputs:
                if all(np.array_equal(p, e) for p, e in zip(predictions, test_outputs)):
                    solved_ids.append(task.task_id)
                else:
                    fp_ids.append(task.task_id)
            else:
                solved_ids.append(task.task_id)

        if (i + 1) % 100 == 0:
            elapsed = time.perf_counter() - t0
            print(f"  [{label}/static] {i+1}/{len(tasks)} ({elapsed:.0f}s, solved={len(solved_ids)})")

    elapsed = time.perf_counter() - t0
    return {
        "solved": len(solved_ids),
        "solved_ids": solved_ids,
        "fp": len(fp_ids),
        "fp_ids": fp_ids,
        "total": len(tasks),
        "elapsed": elapsed,
    }


def eval_adaptive(tasks, label="ARC", max_iterations=8, timeout=30.0):
    """Run AdaptiveReasoningLoop (multi-view, iterative, memory-backed)."""
    memory = ReasoningMemory()
    manifold = MemoryManifold()
    loop = AdaptiveReasoningLoop(
        max_iterations=max_iterations,
        timeout_seconds=timeout,
        memory=memory,
        manifold=manifold,
    )
    solved_ids = []
    fp_ids = []
    view_usage = {}
    iteration_counts = []
    diagnosis_types = {}
    t0 = time.perf_counter()

    for i, task in enumerate(tasks):
        train_pairs = [(ex.input_grid, ex.output_grid) for ex in task.train]
        test_inputs = [ex.input_grid for ex in task.test]
        test_outputs = [ex.output_grid for ex in task.test if ex.output_grid is not None]

        result = loop.solve(train_pairs, test_inputs, task_id=task.task_id)
        iteration_counts.append(result.iterations_used)

        for v in result.views_tried:
            view_usage[v] = view_usage.get(v, 0) + 1
        for d in result.diagnosis_trace:
            diagnosis_types[d.failure_type] = diagnosis_types.get(d.failure_type, 0) + 1

        if result.solved and result.predictions is not None:
            if test_outputs:
                if all(np.array_equal(p, e) for p, e in zip(result.predictions, test_outputs)):
                    solved_ids.append(task.task_id)
                else:
                    fp_ids.append(task.task_id)
            else:
                solved_ids.append(task.task_id)

        if (i + 1) % 100 == 0:
            elapsed = time.perf_counter() - t0
            print(f"  [{label}/adaptive] {i+1}/{len(tasks)} ({elapsed:.0f}s, solved={len(solved_ids)})")

    elapsed = time.perf_counter() - t0
    return {
        "solved": len(solved_ids),
        "solved_ids": solved_ids,
        "fp": len(fp_ids),
        "fp_ids": fp_ids,
        "total": len(tasks),
        "elapsed": elapsed,
        "view_usage": view_usage,
        "mean_iterations": float(np.mean(iteration_counts)),
        "iteration_histogram": {
            str(k): int(v) for k, v in
            zip(*np.unique(iteration_counts, return_counts=True))
        },
        "diagnosis_types": diagnosis_types,
        "memory_episodes": len(memory.episodes),
        "learned_predicates": len(memory.learned_predicates),
        "manifold_charts": len(manifold.charts),
    }


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading ARC training tasks...")
    arc_tasks = load_arc_tasks(ARC_ROOT, split="training", max_tasks=400)
    print(f"Loaded {len(arc_tasks)} ARC tasks")

    conceptarc_tasks = []
    if CONCEPTARC_ROOT.exists():
        print("Loading ConceptARC tasks...")
        conceptarc_tasks = load_conceptarc_tasks(CONCEPTARC_ROOT)
        print(f"Loaded {len(conceptarc_tasks)} ConceptARC tasks")

    print("\n=== Static StructuralReasoner (ARC) ===")
    static_arc = eval_static(arc_tasks, label="ARC")
    print(f"  Static: {static_arc['solved']}/{static_arc['total']} "
          f"({100*static_arc['solved']/max(static_arc['total'],1):.1f}%), "
          f"{static_arc['fp']} FP, {static_arc['elapsed']:.0f}s")

    print("\n=== Adaptive Loop (ARC) ===")
    adaptive_arc = eval_adaptive(arc_tasks, label="ARC", max_iterations=8, timeout=30.0)
    print(f"  Adaptive: {adaptive_arc['solved']}/{adaptive_arc['total']} "
          f"({100*adaptive_arc['solved']/max(adaptive_arc['total'],1):.1f}%), "
          f"{adaptive_arc['fp']} FP, {adaptive_arc['elapsed']:.0f}s")

    # Unique solves
    static_set = set(static_arc["solved_ids"])
    adaptive_set = set(adaptive_arc["solved_ids"])
    adaptive_unique = adaptive_set - static_set
    static_unique = static_set - adaptive_set

    print(f"\n  Adaptive unique solves: {len(adaptive_unique)}")
    if adaptive_unique:
        for tid in sorted(adaptive_unique)[:20]:
            print(f"    {tid}")
    print(f"  Static unique solves: {len(static_unique)}")
    if static_unique:
        for tid in sorted(static_unique)[:20]:
            print(f"    {tid}")

    print(f"\n  View usage: {adaptive_arc['view_usage']}")
    print(f"  Mean iterations: {adaptive_arc['mean_iterations']:.2f}")
    print(f"  Iteration histogram: {adaptive_arc['iteration_histogram']}")
    print(f"  Diagnosis types: {adaptive_arc['diagnosis_types']}")
    print(f"  Memory: {adaptive_arc['memory_episodes']} episodes, "
          f"{adaptive_arc['learned_predicates']} predicates, "
          f"{adaptive_arc['manifold_charts']} charts")

    if conceptarc_tasks:
        print("\n=== Static StructuralReasoner (ConceptARC) ===")
        static_ca = eval_static(conceptarc_tasks, label="ConceptARC")
        print(f"  Static: {static_ca['solved']}/{static_ca['total']} "
              f"({100*static_ca['solved']/max(static_ca['total'],1):.1f}%), "
              f"{static_ca['fp']} FP, {static_ca['elapsed']:.0f}s")

        print("\n=== Adaptive Loop (ConceptARC) ===")
        adaptive_ca = eval_adaptive(
            conceptarc_tasks, label="ConceptARC", max_iterations=8, timeout=30.0,
        )
        print(f"  Adaptive: {adaptive_ca['solved']}/{adaptive_ca['total']} "
              f"({100*adaptive_ca['solved']/max(adaptive_ca['total'],1):.1f}%), "
              f"{adaptive_ca['fp']} FP, {adaptive_ca['elapsed']:.0f}s")
    else:
        static_ca = None
        adaptive_ca = None

    summary = {
        "arc": {
            "static": {k: v for k, v in static_arc.items() if k != "solved_ids" and k != "fp_ids"},
            "adaptive": {k: v for k, v in adaptive_arc.items() if k != "solved_ids" and k != "fp_ids"},
            "adaptive_unique": sorted(adaptive_unique),
            "static_unique": sorted(static_unique),
        },
    }
    if static_ca and adaptive_ca:
        ca_adaptive_set = set(adaptive_ca["solved_ids"])
        ca_static_set = set(static_ca["solved_ids"])
        summary["conceptarc"] = {
            "static": {k: v for k, v in static_ca.items() if k != "solved_ids" and k != "fp_ids"},
            "adaptive": {k: v for k, v in adaptive_ca.items() if k != "solved_ids" and k != "fp_ids"},
            "adaptive_unique": sorted(ca_adaptive_set - ca_static_set),
            "static_unique": sorted(ca_static_set - ca_adaptive_set),
        }

    out_file = OUTPUT_DIR / "adaptive_vs_static.json"
    with open(out_file, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"\nWrote {out_file}")


if __name__ == "__main__":
    main()
