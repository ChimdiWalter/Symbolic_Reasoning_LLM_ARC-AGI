"""Build and cache Phase 1 near-solved states so downstream scripts skip rebuilding.

Usage:
    python3.11 scripts/build_near_solved_cache.py --build-cache --max-tasks 200
    python3.11 scripts/build_near_solved_cache.py --build-cache --start-index 0 --end-index 500

Outputs:
    outputs/cache/near_solved_states.jsonl   — one JSON line per NearSolvedTaskState
    outputs/cache/solved_tasks.json          — task_ids solved by static solver or loop
    outputs/cache/phase1_status.json         — summary: counts, timing, task ranges
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reasoning_project.reasoning_engine import (
    GridDomainAdapter,
    ReasoningMemory,
    StructuralReasoner,
)
from reasoning_project.adaptive_loop import AdaptiveReasoningLoop
from reasoning_project.manifold_memory import ManifoldPoint, MemoryManifold
from reasoning_project.near_solved_memory import (
    NearSolvedMemory,
    NearSolvedTaskState,
    RepairAction,
    save_near_solved_cache,
    load_near_solved_cache,
)


# ═══════════════════════════════════════════════════════════════════════════
# TASK LOADING
# ═══════════════════════════════════════════════════════════════════════════

def load_arc_tasks(arc_root: str) -> List[Dict]:
    tasks = []
    challenges_path = Path(arc_root) / "arc-agi_training_challenges.json"
    solutions_path = Path(arc_root) / "arc-agi_training_solutions.json"
    if not challenges_path.exists():
        print(f"[ERROR] No challenges at {challenges_path}")
        return tasks
    with open(challenges_path) as f:
        challenges = json.load(f)
    solutions = {}
    if solutions_path.exists():
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
        tasks.append({
            "task_id": task_id,
            "train_pairs": train_pairs,
            "test_inputs": test_inputs,
            "test_outputs": test_outputs,
        })
    return tasks


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Build Phase 1 near-solved state cache")
    parser.add_argument("--arc-root", default="data/arc")
    parser.add_argument("--cache-dir", default="outputs/cache")
    parser.add_argument("--max-tasks", type=int, default=0,
                        help="Max tasks (0 = all)")
    parser.add_argument("--start-index", type=int, default=0)
    parser.add_argument("--end-index", type=int, default=0,
                        help="End index (0 = max-tasks or all)")
    parser.add_argument("--loop-iters", type=int, default=4,
                        help="Max adaptive loop iterations")
    parser.add_argument("--timeout", type=float, default=30.0,
                        help="Per-task timeout for adaptive loop")
    parser.add_argument("--build-cache", action="store_true",
                        help="Build and save cache")
    parser.add_argument("--verify", action="store_true",
                        help="Load and verify existing cache")
    args = parser.parse_args()

    if args.verify:
        cache_dir = Path(args.cache_dir)
        ns_mem, solved_ids, status = load_near_solved_cache(str(cache_dir))
        print(f"Cache at {cache_dir}:")
        print(f"  Near-solved states: {len(ns_mem.states)}")
        print(f"  Solved tasks: {len(solved_ids)}")
        print(f"  Status: {json.dumps(status, indent=2)}")
        summary = ns_mem.summary
        for k, v in summary.items():
            print(f"  {k}: {v}")
        return

    if not args.build_cache:
        parser.error("Specify --build-cache to build, or --verify to check existing")

    print("Loading ARC tasks...", flush=True)
    all_tasks = load_arc_tasks(args.arc_root)
    if not all_tasks:
        print("[ERROR] No tasks loaded")
        return

    start = args.start_index
    end = args.end_index if args.end_index > 0 else (
        args.max_tasks if args.max_tasks > 0 else len(all_tasks))
    end = min(end, len(all_tasks))
    tasks = all_tasks[start:end]
    print(f"Processing tasks [{start}:{end}] = {len(tasks)} tasks", flush=True)

    memory = ReasoningMemory()
    manifold = MemoryManifold()
    ns_mem = NearSolvedMemory(manifold)
    solved_ids: List[str] = []

    loop = AdaptiveReasoningLoop(
        max_iterations=args.loop_iters,
        timeout_seconds=args.timeout,
        memory=memory,
        manifold=manifold,
        near_solved_memory=ns_mem,
    )

    t0 = time.perf_counter()
    for i, task in enumerate(tasks):
        tid = task["task_id"]
        train_pairs = task["train_pairs"]
        test_inputs = task["test_inputs"]
        test_outputs = task.get("test_outputs", [])

        if len(train_pairs) < 2:
            continue

        adapter = GridDomainAdapter()
        reasoner = StructuralReasoner(adapter, memory=memory, min_train=2)
        result = reasoner.solve(train_pairs, test_inputs)

        if result is not None:
            preds, hyp = result
            correct = (
                test_outputs and
                len(preds) == len(test_outputs) and
                all(np.array_equal(p, e) for p, e in zip(preds, test_outputs))
            )
            if correct:
                solved_ids.append(tid)
        else:
            loop_result = loop.solve(train_pairs, test_inputs, task_id=tid)
            if loop_result.solved and loop_result.predictions and test_outputs:
                correct = all(
                    np.array_equal(p, e)
                    for p, e in zip(loop_result.predictions, test_outputs)
                )
                if correct:
                    solved_ids.append(tid)

        if (i + 1) % 50 == 0:
            elapsed = time.perf_counter() - t0
            rate = elapsed / (i + 1)
            eta = rate * (len(tasks) - i - 1)
            print(f"  {i+1}/{len(tasks)}  solved={len(solved_ids)}  "
                  f"near_solved={len(ns_mem.states)}  "
                  f"elapsed={elapsed:.0f}s  eta={eta:.0f}s", flush=True)

    elapsed = time.perf_counter() - t0
    status = {
        "start_index": start,
        "end_index": end,
        "n_tasks": len(tasks),
        "n_solved": len(solved_ids),
        "n_near_solved": len(ns_mem.states),
        "elapsed_seconds": round(elapsed, 1),
        "loop_iters": args.loop_iters,
        "timeout": args.timeout,
        "summary": ns_mem.summary,
    }

    print(f"\nDone in {elapsed:.1f}s")
    print(f"  Solved: {len(solved_ids)}/{len(tasks)}")
    print(f"  Near-solved: {len(ns_mem.states)}")

    save_near_solved_cache(args.cache_dir, ns_mem, solved_ids, status)
    print(f"\nCache saved to {args.cache_dir}/")
    print(f"  near_solved_states.jsonl: {len(ns_mem.states)} states")
    print(f"  solved_tasks.json: {len(solved_ids)} solved")


if __name__ == "__main__":
    main()
