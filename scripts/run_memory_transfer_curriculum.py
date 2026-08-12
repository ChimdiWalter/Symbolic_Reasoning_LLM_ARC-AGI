#!/usr/bin/env python3.11
"""Sequential memory transfer experiment.

Stage 1: Run seed tasks with AdaptiveMemory write enabled -> store certified packages
Stage 2: Freeze memory (no new writes)
Stage 3: Run held-out tasks with memory retrieval enabled -> solve using packages
Stage 4: Run same held-out tasks with memory disabled -> should fail

Output:
  - memory_transfer_results.csv
  - memory_transfer_summary.md
  - memory_store_manifest.jsonl
"""
from __future__ import annotations

import csv
import json
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

OUTPUT_DIR = PROJECT_ROOT / "outputs" / "full_novel_reasoning_pipeline_v2" / "adaptive_memory_adaptergenesis_proof_2026_06_20"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

from reasoning_project.adaptive_orchestrator import OrchestratorConfig, ModuleProposal
from reasoning_project.proposal_verifier import ProposalVerifier
from reasoning_project.reasoning_engine import (
    GridDomainAdapter,
    StructuralReasoner,
    ReasoningMemory,
)
from reasoning_project.view_adapters import (
    FrameInteriorAdapter,
    ColorLayerAdapter,
    ObjectInObjectAdapter,
    get_applicable_adapters,
)
from reasoning_project.adaptive_memory import AdaptiveMemory, _compute_task_signature
from reasoning_project.proposal_logger import ProposalLogger


def _load_task_pairs(task: Dict) -> Tuple[
    List[Tuple[np.ndarray, np.ndarray]],
    List[np.ndarray],
    List[np.ndarray],
]:
    train_pairs = []
    for pair in task["train"]:
        inp = np.array(pair["input"], dtype=int)
        out = np.array(pair["output"], dtype=int)
        train_pairs.append((inp, out))
    test_inputs = [np.array(p["input"], dtype=int) for p in task["test"]]
    test_outputs = [np.array(p["output"], dtype=int) for p in task["test"]]
    return train_pairs, test_inputs, test_outputs


def _try_solve_with_adapters(
    train_pairs, test_inputs, test_outputs,
    adaptive_memory: Optional[AdaptiveMemory] = None,
    use_memory: bool = True,
    timeout: float = 10.0,
) -> Tuple[bool, str, Optional[str]]:
    """Try to solve using adapter genesis pipeline.

    Returns (solved, module_source, adapter_type).
    """
    deadline = time.perf_counter() + timeout

    # Step 1: Try standard reasoner first
    try:
        adapter = GridDomainAdapter()
        reasoner = StructuralReasoner(adapter, memory=ReasoningMemory())
        result = reasoner.solve(train_pairs, test_inputs, deadline=deadline)
        if result is not None:
            predictions, _ = result
            if predictions and len(predictions) == len(test_outputs):
                all_match = all(
                    np.array_equal(np.array(p), to)
                    for p, to in zip(predictions, test_outputs)
                )
                if all_match:
                    return True, "static_portfolio", None
    except Exception:
        pass

    # Step 2: Try memory retrieval (if enabled)
    if use_memory and adaptive_memory and len(adaptive_memory) > 0:
        task_sig = _compute_task_signature(train_pairs)
        packages = adaptive_memory.retrieve_by_signature(task_sig, top_k=5)

        for pkg in packages:
            try:
                if pkg.adapter_type == "frame_interior":
                    va = FrameInteriorAdapter()
                elif pkg.adapter_type == "color_layer":
                    va = ColorLayerAdapter()
                elif pkg.adapter_type == "object_in_object":
                    va = ObjectInObjectAdapter()
                else:
                    continue

                first_input = train_pairs[0][0]
                if not va.can_apply(first_input):
                    continue

                # Try the adapter
                solved, exec_fn = _try_adapter(va, train_pairs, test_inputs, test_outputs, deadline)
                if solved:
                    return True, "memory_retrieval", pkg.adapter_type
            except Exception:
                continue

    # Step 3: Try fresh adapter genesis
    first_input = train_pairs[0][0]
    applicable = get_applicable_adapters(first_input)
    for va in applicable:
        try:
            if time.perf_counter() > deadline:
                break
            solved, exec_fn = _try_adapter(va, train_pairs, test_inputs, test_outputs, deadline)
            if solved:
                return True, "adapter_genesis", va.adapter_type
        except Exception:
            continue

    return False, "none", None


def _try_adapter(va, train_pairs, test_inputs, test_outputs, deadline):
    """Try solving with a specific adapter. Returns (solved, executable)."""
    adapter_type = va.adapter_type

    if adapter_type == "color_layer":
        target_color = va._detect_changing_color(train_pairs)
        if target_color is not None:
            def execute(grid, tc=target_color):
                result = grid.copy()
                result[result == tc] = 0
                return result
            preds = [execute(ti) for ti in test_inputs]
            if all(np.array_equal(p, to) for p, to in zip(preds, test_outputs)):
                return True, execute

    elif adapter_type == "object_in_object":
        def execute(grid):
            containments = va._find_containments(grid)
            if not containments:
                return grid
            result = np.zeros_like(grid)
            for c in containments:
                result[c["inner_mask"]] = c["inner_color"]
            return result
        preds = [execute(ti) for ti in test_inputs]
        if all(np.array_equal(p, to) for p, to in zip(preds, test_outputs)):
            return True, execute

    elif adapter_type == "frame_interior":
        # Lift pairs and try reasoner on interior
        lifted = va.lift_train_pairs(train_pairs)
        lifted_test = []
        for ti in test_inputs:
            parsed = va.parse(ti)
            if parsed.get("has_frame"):
                lifted_test.append(parsed["interior"])
            else:
                lifted_test.append(ti)

        adapter = GridDomainAdapter()
        reasoner = StructuralReasoner(adapter, memory=ReasoningMemory())
        result = reasoner.solve(lifted, lifted_test, deadline=deadline)
        if result is not None:
            lifted_preds, metadata = result
            if lifted_preds and len(lifted_preds) == len(test_outputs):
                # Project back
                final_preds = []
                for lp, ti in zip(lifted_preds, test_inputs):
                    projected = va.project(np.array(lp), ti)
                    final_preds.append(projected)
                if all(np.array_equal(p, to)
                       for p, to in zip(final_preds, test_outputs)):
                    def make_exec(va_ref, meta):
                        hyp_exec = meta.get("execute")
                        def execute(grid):
                            parsed = va_ref.parse(grid)
                            if parsed.get("has_frame"):
                                interior = parsed["interior"]
                                if hyp_exec and callable(hyp_exec):
                                    result_interior = hyp_exec(interior)
                                else:
                                    return grid
                                return va_ref.project(result_interior, grid)
                            return grid
                        return execute
                    return True, make_exec(va, metadata)

    return False, None


def main():
    # Load curriculum
    curriculum_path = OUTPUT_DIR / "curriculum_tasks.json"
    if not curriculum_path.exists():
        print(f"Curriculum not found at {curriculum_path}")
        print("Run build_adaptive_memory_curriculum.py first.")
        sys.exit(1)

    with open(curriculum_path) as f:
        tasks = json.load(f)

    # Separate seed and held-out tasks
    seed_tasks = [t for t in tasks if t.get("role") == "seed"]
    heldout_tasks = [t for t in tasks if t.get("role") == "heldout"]

    print(f"Loaded {len(tasks)} tasks: {len(seed_tasks)} seed, {len(heldout_tasks)} held-out")

    proposal_logger = ProposalLogger(str(OUTPUT_DIR / "memory_transfer_proposal_log.jsonl"))
    results = []

    # ===== Stage 1: Run seeds with memory write enabled =====
    print("\n" + "=" * 60)
    print("Stage 1: Seed tasks (memory write enabled)")
    print("=" * 60)

    adaptive_memory = AdaptiveMemory()

    for task in seed_tasks:
        train_pairs, test_inputs, test_outputs = _load_task_pairs(task)
        t0 = time.perf_counter()

        solved, module_source, adapter_type = _try_solve_with_adapters(
            train_pairs, test_inputs, test_outputs,
            adaptive_memory=adaptive_memory,
            use_memory=False,  # No memory to retrieve from yet
        )

        runtime = time.perf_counter() - t0

        # Store in memory if solved
        if solved and adapter_type:
            if adapter_type == "frame_interior":
                va = FrameInteriorAdapter()
            elif adapter_type == "color_layer":
                va = ColorLayerAdapter()
            elif adapter_type == "object_in_object":
                va = ObjectInObjectAdapter()
            else:
                va = None

            if va:
                adaptive_memory.store_verified_package(
                    task_id=task["task_id"],
                    adapter=va,
                    operator_family=task.get("expected_operator", "unknown"),
                    selector=task.get("expected_selector", "unknown"),
                    certificate_path="",
                    train_pairs=train_pairs,
                )

        status = "SOLVED" if solved else "FAILED"
        print(f"  {task['task_id']}: {status} (module={module_source}, adapter={adapter_type})")

        results.append({
            "stage": "stage_1_seed",
            "task_id": task["task_id"],
            "group": task.get("group", ""),
            "role": "seed",
            "solved": solved,
            "module_source": module_source,
            "adapter_type": adapter_type or "",
            "memory_enabled": True,
            "memory_size": len(adaptive_memory),
            "runtime_seconds": runtime,
        })

    # ===== Stage 2: Freeze memory =====
    print(f"\nStage 2: Freezing memory ({len(adaptive_memory)} packages stored)")
    adaptive_memory.freeze()

    # Save manifest
    manifest_path = OUTPUT_DIR / "memory_store_manifest.jsonl"
    adaptive_memory.save_manifest(str(manifest_path))
    print(f"  Manifest saved to {manifest_path}")

    # ===== Stage 3: Held-out tasks WITH memory =====
    print("\n" + "=" * 60)
    print("Stage 3: Held-out tasks (memory retrieval enabled)")
    print("=" * 60)

    for task in heldout_tasks:
        train_pairs, test_inputs, test_outputs = _load_task_pairs(task)
        t0 = time.perf_counter()

        solved, module_source, adapter_type = _try_solve_with_adapters(
            train_pairs, test_inputs, test_outputs,
            adaptive_memory=adaptive_memory,
            use_memory=True,
        )

        runtime = time.perf_counter() - t0
        status = "SOLVED" if solved else "FAILED"
        print(f"  {task['task_id']}: {status} (module={module_source}, adapter={adapter_type})")

        results.append({
            "stage": "stage_3_heldout_with_memory",
            "task_id": task["task_id"],
            "group": task.get("group", ""),
            "role": "heldout",
            "solved": solved,
            "module_source": module_source,
            "adapter_type": adapter_type or "",
            "memory_enabled": True,
            "memory_size": len(adaptive_memory),
            "runtime_seconds": runtime,
        })

    # ===== Stage 4: Held-out tasks WITHOUT memory =====
    print("\n" + "=" * 60)
    print("Stage 4: Held-out tasks (memory disabled)")
    print("=" * 60)

    for task in heldout_tasks:
        train_pairs, test_inputs, test_outputs = _load_task_pairs(task)
        t0 = time.perf_counter()

        solved, module_source, adapter_type = _try_solve_with_adapters(
            train_pairs, test_inputs, test_outputs,
            adaptive_memory=None,
            use_memory=False,
        )

        runtime = time.perf_counter() - t0
        status = "SOLVED" if solved else "FAILED"
        print(f"  {task['task_id']}: {status} (module={module_source}, adapter={adapter_type})")

        results.append({
            "stage": "stage_4_heldout_no_memory",
            "task_id": task["task_id"],
            "group": task.get("group", ""),
            "role": "heldout",
            "solved": solved,
            "module_source": module_source,
            "adapter_type": adapter_type or "",
            "memory_enabled": False,
            "memory_size": 0,
            "runtime_seconds": runtime,
        })

    # ===== Write results =====
    csv_path = OUTPUT_DIR / "memory_transfer_results.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "stage", "task_id", "group", "role", "solved",
            "module_source", "adapter_type", "memory_enabled",
            "memory_size", "runtime_seconds",
        ])
        writer.writeheader()
        for r in results:
            writer.writerow(r)

    print(f"\nResults written to {csv_path}")

    # ===== Write summary =====
    md_path = OUTPUT_DIR / "memory_transfer_summary.md"
    with open(md_path, "w") as f:
        f.write("# Memory Transfer Experiment\n\n")
        f.write(f"Date: 2026-06-20\n\n")

        # Stage summaries
        for stage_name in ["stage_1_seed", "stage_3_heldout_with_memory",
                           "stage_4_heldout_no_memory"]:
            stage_results = [r for r in results if r["stage"] == stage_name]
            n_solved = sum(1 for r in stage_results if r["solved"])
            n_total = len(stage_results)
            f.write(f"## {stage_name}\n")
            f.write(f"- Solved: {n_solved}/{n_total}\n")
            for r in stage_results:
                status = "SOLVED" if r["solved"] else "FAILED"
                f.write(f"  - {r['task_id']}: {status} ({r['module_source']})\n")
            f.write("\n")

        # Memory transfer analysis
        f.write("## Memory Transfer Analysis\n\n")
        stage3 = {r["task_id"]: r["solved"]
                  for r in results if r["stage"] == "stage_3_heldout_with_memory"}
        stage4 = {r["task_id"]: r["solved"]
                  for r in results if r["stage"] == "stage_4_heldout_no_memory"}

        f.write("| Task | With Memory | Without Memory | Memory Necessary |\n")
        f.write("|------|------------|----------------|------------------|\n")
        for tid in sorted(stage3.keys()):
            with_mem = stage3.get(tid, False)
            without_mem = stage4.get(tid, False)
            necessary = with_mem and not without_mem
            f.write(f"| {tid} | {'yes' if with_mem else 'no'} | "
                    f"{'yes' if without_mem else 'no'} | "
                    f"{'YES' if necessary else 'no'} |\n")

        n_memory_necessary = sum(
            1 for tid in stage3
            if stage3[tid] and not stage4.get(tid, False)
        )
        f.write(f"\nMemory was causally necessary for {n_memory_necessary} "
                f"out of {len(stage3)} held-out tasks.\n")

        # Manifest
        f.write(f"\n## Memory Store\n")
        f.write(f"- Packages stored: {len(adaptive_memory)}\n")
        f.write(f"- Manifest: memory_store_manifest.jsonl\n")

    print(f"Summary written to {md_path}")

    # Print final stats
    print("\n" + "=" * 60)
    print("FINAL SUMMARY")
    print("=" * 60)
    for stage_name in ["stage_1_seed", "stage_3_heldout_with_memory",
                       "stage_4_heldout_no_memory"]:
        stage_results = [r for r in results if r["stage"] == stage_name]
        n_solved = sum(1 for r in stage_results if r["solved"])
        n_total = len(stage_results)
        print(f"  {stage_name}: {n_solved}/{n_total}")


if __name__ == "__main__":
    main()
