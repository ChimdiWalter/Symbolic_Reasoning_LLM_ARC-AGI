"""Module ablation on the 40 ARC-1000 v2 solved tasks.

Runs each solved task under 12 controlled configs to determine which modules
are necessary for each solve. Does NOT modify solver or verifier logic.
"""
from __future__ import annotations

import csv
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from reasoning_project.adaptive_orchestrator import (
    GatedAdaptiveReasoningOrchestrator,
    OrchestratorConfig,
)
from reasoning_project.arc_adapter import load_arc_tasks

ARC_ROOT = Path(__file__).parent.parent / "data" / "arc"
AUDIT_ROOT = Path(__file__).parent.parent / "outputs" / "full_novel_reasoning_pipeline_v2"
OUTPUT_DIR = str(AUDIT_ROOT / "arc1000_module_causality_audit_2026_06_19")
CHECKPOINT_PATH = os.path.join(OUTPUT_DIR, "ablation_progress.jsonl")

CONFIGS = {
    "full_v2": OrchestratorConfig(),
    "no_frontier_operators": OrchestratorConfig(enable_frontier_operators=False),
    "no_trace_invention": OrchestratorConfig(enable_trace_invention=False),
    "no_static_portfolio": OrchestratorConfig(enable_static_portfolio=False),
    "no_property_expansion": OrchestratorConfig(enable_property_expansion=False),
    "no_adapter_genesis": OrchestratorConfig(enable_adapter_genesis=False),
    "no_manifold_memory": OrchestratorConfig(enable_manifold_memory=False),
    "no_operator_memory": OrchestratorConfig(enable_operator_memory=False),
    "no_neural_advisory": OrchestratorConfig(enable_neural_advisory=False),
    "frontier_only": OrchestratorConfig(
        enable_static_portfolio=False,
        enable_trace_invention=False,
        enable_adapter_genesis=False,
        enable_manifold_memory=False,
        enable_near_solved_memory=False,
        enable_operator_memory=False,
        enable_neural_advisory=False,
        enable_domain_morphism=False,
        enable_property_expansion=False,
    ),
    "trace_only": OrchestratorConfig(
        enable_static_portfolio=False,
        enable_frontier_operators=False,
        enable_adapter_genesis=False,
        enable_manifold_memory=False,
        enable_near_solved_memory=False,
        enable_operator_memory=False,
        enable_neural_advisory=False,
        enable_domain_morphism=False,
        enable_property_expansion=False,
    ),
    "static_only": OrchestratorConfig(
        enable_frontier_operators=False,
        enable_trace_invention=False,
        enable_adapter_genesis=False,
        enable_manifold_memory=False,
        enable_near_solved_memory=False,
        enable_operator_memory=False,
        enable_neural_advisory=False,
        enable_domain_morphism=False,
        enable_property_expansion=False,
    ),
}


def load_solved_task_ids(path: str) -> List[str]:
    with open(path) as f:
        return [line.strip() for line in f if line.strip()]


def load_checkpoint() -> set:
    done = set()
    if os.path.exists(CHECKPOINT_PATH):
        with open(CHECKPOINT_PATH) as f:
            for line in f:
                if line.strip():
                    row = json.loads(line)
                    done.add((row["task_id"], row["config"]))
    return done


def main():
    print("=" * 70)
    print("  ARC-1000 Solved Task Module Ablation")
    print("=" * 70)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    solved_ids_path = os.path.join(OUTPUT_DIR, "solved_40_ids.txt")
    task_ids = load_solved_task_ids(solved_ids_path)
    print(f"  Loaded {len(task_ids)} solved task IDs")

    print("\nLoading ARC tasks...")
    arc_task_list = load_arc_tasks(ARC_ROOT)
    tasks = {t.task_id: t for t in arc_task_list}
    print(f"  Loaded {len(tasks)} total ARC tasks")

    completed = load_checkpoint()
    total_runs = len(CONFIGS) * len(task_ids)
    print(f"  Resuming: {len(completed)} task/config pairs already done")
    print(f"  Total runs: {total_runs}, remaining: {total_runs - len(completed)}")

    config_names = list(CONFIGS.keys())
    t_start = time.time()
    run_count = 0
    fp_count = 0

    with open(CHECKPOINT_PATH, "a") as progress_f:
        for config_name in config_names:
            config = CONFIGS[config_name]
            config.output_dir = OUTPUT_DIR
            config.timeout_per_task = 420.0

            orch = GatedAdaptiveReasoningOrchestrator(config)

            config_solved = 0
            config_total = 0

            for task_id in task_ids:
                if (task_id, config_name) in completed:
                    continue
                if task_id not in tasks:
                    print(f"  WARNING: task {task_id} not found in ARC data")
                    continue

                task = tasks[task_id]
                train_pairs = [
                    (ex.input_grid, ex.output_grid)
                    for ex in task.train
                    if ex.output_grid is not None
                ]
                test_inputs = [ex.input_grid for ex in task.test]
                test_outputs = (
                    [ex.output_grid for ex in task.test if ex.output_grid is not None]
                    or None
                )

                trace = orch.solve_task(task_id, train_pairs, test_inputs, test_outputs)

                v2_solved = trace.final_status == "solved"
                is_fp = (
                    trace.verification.false_positive if trace.verification else False
                )
                has_cert = (
                    trace.verification.certificate_path is not None
                    if trace.verification
                    else False
                )

                row = {
                    "task_id": task_id,
                    "config": config_name,
                    "v2_solved": v2_solved,
                    "selected_module": (
                        trace.selected_proposal.module_name
                        if trace.selected_proposal
                        else None
                    ),
                    "operator_family": (
                        trace.selected_proposal.operator_family
                        if trace.selected_proposal
                        else None
                    ),
                    "certificate_emitted": has_cert,
                    "false_positive": is_fp,
                    "final_status": trace.final_status,
                    "runtime_seconds": round(trace.runtime_seconds, 2),
                }

                progress_f.write(json.dumps(row) + "\n")
                progress_f.flush()

                if v2_solved:
                    config_solved += 1
                if is_fp:
                    fp_count += 1
                config_total += 1
                run_count += 1

                if run_count % 10 == 0:
                    elapsed = time.time() - t_start
                    done_total = len(completed) + run_count
                    print(
                        f"  [{done_total}/{total_runs}] "
                        f"config={config_name} task={task_id} "
                        f"solved={v2_solved} fp={is_fp} "
                        f"({trace.runtime_seconds:.1f}s) "
                        f"[{elapsed:.0f}s elapsed]",
                        flush=True,
                    )

            print(
                f"  Config {config_name}: {config_solved}/{config_total + sum(1 for tid in task_ids if (tid, config_name) in completed)} solved",
                flush=True,
            )

    elapsed_total = time.time() - t_start

    print(f"\nGenerating summary files...")
    _generate_summary(OUTPUT_DIR)

    print(f"\n{'=' * 70}")
    print(f"  MODULE ABLATION COMPLETE")
    print(f"{'=' * 70}")
    print(f"  Tasks:       {len(task_ids)}")
    print(f"  Configs:     {len(CONFIGS)}")
    print(f"  Total runs:  {total_runs}")
    print(f"  FP:          {fp_count}")
    print(f"  Wall time:   {elapsed_total:.0f}s ({elapsed_total / 3600:.1f}h)")
    print(f"  Output:      {OUTPUT_DIR}/")
    print(f"{'=' * 70}")


def _generate_summary(output_dir: str):
    rows = []
    with open(os.path.join(output_dir, "ablation_progress.jsonl")) as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))

    task_ids_path = os.path.join(output_dir, "solved_40_ids.txt")
    with open(task_ids_path) as f:
        all_task_ids = [l.strip() for l in f if l.strip()]

    new_v2_path = os.path.join(output_dir, "new_v2_only_11_ids.txt")
    with open(new_v2_path) as f:
        new_v2_ids = set(l.strip() for l in f if l.strip())

    config_names = sorted(set(r["config"] for r in rows))

    with open(os.path.join(output_dir, "module_ablation_40_tasks.csv"), "w", newline="") as csvf:
        writer = csv.writer(csvf)
        header = ["task_id", "is_new_v2"] + config_names
        writer.writerow(header)
        for tid in all_task_ids:
            is_new = tid in new_v2_ids
            solved_by = {}
            for r in rows:
                if r["task_id"] == tid:
                    solved_by[r["config"]] = r["v2_solved"]
            row_out = [tid, is_new] + [solved_by.get(c, "") for c in config_names]
            writer.writerow(row_out)

    fp_any = any(r.get("false_positive", False) for r in rows)

    lines = [
        "# Module Ablation Results — 40 Solved Tasks",
        "",
        f"**Date:** 2026-06-19",
        f"**Tasks:** {len(all_task_ids)} (11 new v2-only, 29 v1-preserved)",
        f"**Configs:** {len(config_names)}",
        f"**False positives across all runs:** {'YES — INVESTIGATE' if fp_any else '0'}",
        "",
        "## Config Solve Counts",
        "",
        "| Config | Solved / 40 | New v2-only Solved / 11 |",
        "|--------|-------------|------------------------|",
    ]
    for cn in config_names:
        cn_rows = [r for r in rows if r["config"] == cn]
        total_s = sum(1 for r in cn_rows if r["v2_solved"])
        new_s = sum(1 for r in cn_rows if r["v2_solved"] and r["task_id"] in new_v2_ids)
        lines.append(f"| {cn} | {total_s} | {new_s} |")

    lines += [
        "",
        "## Per-Task Solve Matrix",
        "",
        "| Task ID | New? | " + " | ".join(config_names) + " |",
        "|---------|------|" + "|".join(["---"] * len(config_names)) + "|",
    ]
    for tid in all_task_ids:
        is_new = "**YES**" if tid in new_v2_ids else ""
        cells = []
        for cn in config_names:
            match = [r for r in rows if r["task_id"] == tid and r["config"] == cn]
            if match and match[0]["v2_solved"]:
                cells.append("SOLVED")
            elif match:
                cells.append("-")
            else:
                cells.append("?")
        lines.append(f"| {tid} | {is_new} | " + " | ".join(cells) + " |")

    with open(os.path.join(output_dir, "module_ablation_40_tasks.md"), "w") as f:
        f.write("\n".join(lines) + "\n")

    print(f"  Written: module_ablation_40_tasks.csv, module_ablation_40_tasks.md")


if __name__ == "__main__":
    main()
