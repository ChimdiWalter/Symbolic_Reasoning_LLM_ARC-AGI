"""Full ARC-1000 evaluation with the v2 Gated Adaptive Reasoning Orchestrator.

Outputs every row with full module attribution for paper-ready analysis.
"""
from __future__ import annotations

import csv
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from reasoning_project.adaptive_orchestrator import (
    GatedAdaptiveReasoningOrchestrator,
    OrchestratorConfig,
)
from reasoning_project.arc_adapter import load_arc_tasks, ARCTask

ARC_ROOT = Path(__file__).parent.parent / "data" / "arc"


OUTPUT_DIR = "outputs/full_novel_reasoning_pipeline_v2/arc1000_after_stable_baseline_2026_06_16"
CHECKPOINT_PATH = os.path.join(OUTPUT_DIR, "progress.jsonl")


def load_v1_results(path: str = "outputs/full_arc1000_novel_pipeline/progress.jsonl") -> Dict[str, Dict]:
    results = {}
    if not os.path.exists(path):
        return results
    with open(path) as f:
        for line in f:
            if line.strip():
                row = json.loads(line)
                row["solved"] = (
                    row.get("final_config_that_solved") is not None or
                    row.get("operator_promoted", False) or
                    row.get("solved_by_static", False)
                )
                results[row.get("task_id", "")] = row
    return results


def load_checkpoint() -> set:
    completed = set()
    if os.path.exists(CHECKPOINT_PATH):
        with open(CHECKPOINT_PATH) as f:
            for line in f:
                if line.strip():
                    row = json.loads(line)
                    completed.add(row.get("task_id", ""))
    return completed


def main():
    print("=" * 70)
    print("  Full Novel Reasoning Pipeline v2: ARC-1000 Evaluation")
    print("=" * 70)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(os.path.join(OUTPUT_DIR, "certificates"), exist_ok=True)

    print("\nLoading ARC tasks...")
    arc_task_list = load_arc_tasks(ARC_ROOT)
    tasks = {t.task_id: t for t in arc_task_list}
    task_ids = sorted(tasks.keys())
    print(f"  Loaded {len(task_ids)} tasks")

    print("\nLoading v1 results...")
    v1_results = load_v1_results()
    print(f"  Loaded {len(v1_results)} v1 results")

    completed = load_checkpoint()
    print(f"  Resuming: {len(completed)} tasks already completed")

    remaining = [tid for tid in task_ids if tid not in completed]
    print(f"  Remaining: {len(remaining)} tasks")

    config = OrchestratorConfig(
        timeout_per_task=420.0,
        output_dir=OUTPUT_DIR,
    )
    orch = GatedAdaptiveReasoningOrchestrator(config)

    solved_count = 0
    fp_count = 0
    new_solve_count = 0
    cert_count = 0
    t_start = time.time()

    with open(CHECKPOINT_PATH, "a") as progress_f:
        for i, task_id in enumerate(remaining):
            task = tasks[task_id]
            train_pairs = [(ex.input_grid, ex.output_grid) for ex in task.train if ex.output_grid is not None]
            test_inputs = [ex.input_grid for ex in task.test]
            test_outputs = [ex.output_grid for ex in task.test if ex.output_grid is not None] or None

            trace = orch.solve_task(task_id, train_pairs, test_inputs, test_outputs)

            v1_solved = v1_results.get(task_id, {}).get("solved", False)
            v2_solved = trace.final_status == "solved"
            is_fp = trace.verification.false_positive if trace.verification else False
            has_cert = trace.verification.certificate_path is not None if trace.verification else False

            if v2_solved:
                solved_count += 1
            if is_fp:
                fp_count += 1
            if v2_solved and not v1_solved:
                new_solve_count += 1
            if has_cert:
                cert_count += 1

            row = {
                "task_id": task_id,
                "v1_solved": v1_solved,
                "v2_solved": v2_solved,
                "new_solve": v2_solved and not v1_solved,
                "domain": trace.domain,
                "modules_triggered": ",".join(trace.triggered_modules),
                "modules_skipped": json.dumps(trace.skipped_modules),
                "adapter_genesis_used": "adapter_genesis" in trace.triggered_modules,
                "manifold_memory_used": "manifold_memory" in trace.triggered_modules,
                "near_solved_memory_used": "near_solved_memory" in trace.triggered_modules,
                "operator_memory_used": "operator_memory" in trace.triggered_modules,
                "neural_advisory_used": "neural_advisory" in trace.triggered_modules,
                "domain_morphism_used": "domain_morphism" in trace.triggered_modules,
                "frontier_operator_used": "frontier_operators" in trace.triggered_modules,
                "property_expansion_used": "property_expansion" in trace.triggered_modules,
                "operator_family": trace.selected_proposal.operator_family if trace.selected_proposal else None,
                "property_family": trace.selected_proposal.selector if trace.selected_proposal else None,
                "LOO_passed": trace.verification.loo_passed if trace.verification else False,
                "proof_obligations_passed": trace.verification.proof_obligations_passed if trace.verification else False,
                "falsification_passed": trace.verification.falsification_passed if trace.verification else False,
                "certificate_emitted": has_cert,
                "false_positive": is_fp,
                "runtime_seconds": trace.runtime_seconds,
                "failure_reason": trace.verification.rejection_reason if trace.verification and not trace.verification.accepted else trace.final_status,
            }

            progress_f.write(json.dumps(row) + "\n")
            progress_f.flush()

            total_done = len(completed) + i + 1
            if (i + 1) % 10 == 0:
                elapsed = time.time() - t_start
                print(f"[{total_done}/1000 {total_done*100//1000}%] "
                      f"{task_id} ... {trace.selected_proposal.module_name if trace.selected_proposal else 'None'} "
                      f"({trace.runtime_seconds:.1f}s)")

            if (i + 1) % 100 == 0:
                elapsed = time.time() - t_start
                print(f"    -- checkpoint: {solved_count}/{total_done} solved, "
                      f"{new_solve_count} new, {fp_count} FP, {elapsed:.0f}s elapsed --")

    # Final summary
    elapsed_total = time.time() - t_start
    print(f"\n{'='*70}")
    print(f"  FULL ARC-1000 NOVEL PIPELINE v2 COMPLETE")
    print(f"{'='*70}")
    print(f"  Tasks:       {len(task_ids)}")
    print(f"  Solved:      {solved_count} ({solved_count*100/len(task_ids):.1f}%)")
    print(f"  New (v1→v2): {new_solve_count}")
    print(f"  FP:          {fp_count}")
    print(f"  Certs:       {cert_count}")
    print(f"  Wall time:   {elapsed_total:.0f}s ({elapsed_total/3600:.1f}h)")
    print(f"  Output:      {OUTPUT_DIR}/")
    print(f"{'='*70}")

    # Write final summary JSON
    summary = {
        "total_tasks": len(task_ids),
        "solved": solved_count,
        "solve_rate": solved_count / len(task_ids),
        "new_solves_over_v1": new_solve_count,
        "false_positives": fp_count,
        "certificates": cert_count,
        "wall_time_seconds": elapsed_total,
        "v1_baseline_solved": sum(1 for r in v1_results.values() if r.get("solved")),
    }
    with open(os.path.join(OUTPUT_DIR, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2)


if __name__ == "__main__":
    main()
