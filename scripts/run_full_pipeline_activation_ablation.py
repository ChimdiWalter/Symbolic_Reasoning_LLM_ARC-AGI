"""Phase 9: Contribution-aware ablation study for the full pipeline.

Runs focused eval with multiple module-disable configurations to measure
the contribution of each new module to solve count.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from reasoning_project.adaptive_orchestrator import (
    GatedAdaptiveReasoningOrchestrator,
    OrchestratorConfig,
)
from reasoning_project.arc_adapter import load_arc_tasks, ARCTask

ARC_ROOT = Path(__file__).parent.parent / "data" / "arc"
OUTPUT_DIR = "outputs/full_novel_reasoning_pipeline_v2/full_pipeline_activation_repair"


def load_v1_results(path: str = "outputs/full_arc1000_novel_pipeline/progress.jsonl") -> Dict[str, Dict]:
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


def get_focused_task_ids(v1_results: Dict[str, Dict]) -> List[str]:
    v1_solved = [tid for tid, r in v1_results.items() if r.get("solved")]
    v1_certified = [tid for tid, r in v1_results.items() if r.get("certificate_emitted")]
    shape_completion_tasks = ["d89b689b", "e9ac8c9e", "1d0a4b61", "8eb1be9a", "92e50de0", "a5313dff"]
    position_recolor_tasks = ["a48eeaf7", "4347f46a", "50cb2852", "bb43febb"]
    many_to_few_tasks = ["56ff96f3"]
    color_transfer_tasks = ["2a5f8217"]
    v1_unsolved = [tid for tid, r in v1_results.items() if not r.get("solved")]
    top_failures = v1_unsolved[:50]
    return list(set(
        v1_solved + v1_certified + shape_completion_tasks +
        position_recolor_tasks + many_to_few_tasks + color_transfer_tasks +
        top_failures
    ))


ABLATION_CONFIGS = {
    "baseline_v2_full": OrchestratorConfig(),
    "no_selector_invention": OrchestratorConfig(
        enable_property_expansion=False,
    ),
    "no_adapter_genesis_schema": OrchestratorConfig(
        enable_adapter_genesis=False,
    ),
    "no_memory": OrchestratorConfig(
        enable_manifold_memory=False,
        enable_operator_memory=False,
        enable_near_solved_memory=False,
    ),
    "no_neural": OrchestratorConfig(
        enable_neural_advisory=False,
    ),
    "no_property_expansion": OrchestratorConfig(
        enable_property_expansion=False,
    ),
    "no_frontier": OrchestratorConfig(
        enable_frontier_operators=False,
    ),
    "no_trace_invention": OrchestratorConfig(
        enable_trace_invention=False,
    ),
    "only_static": OrchestratorConfig(
        enable_adapter_genesis=False,
        enable_manifold_memory=False,
        enable_near_solved_memory=False,
        enable_operator_memory=False,
        enable_neural_advisory=False,
        enable_domain_morphism=False,
        enable_property_expansion=False,
        enable_frontier_operators=False,
        enable_trace_invention=False,
    ),
    "only_frontier": OrchestratorConfig(
        enable_adapter_genesis=False,
        enable_manifold_memory=False,
        enable_near_solved_memory=False,
        enable_operator_memory=False,
        enable_neural_advisory=False,
        enable_domain_morphism=False,
        enable_property_expansion=False,
        enable_trace_invention=False,
    ),
    "only_trace": OrchestratorConfig(
        enable_adapter_genesis=False,
        enable_manifold_memory=False,
        enable_near_solved_memory=False,
        enable_operator_memory=False,
        enable_neural_advisory=False,
        enable_domain_morphism=False,
        enable_property_expansion=False,
        enable_frontier_operators=False,
    ),
}


def run_ablation(
    config_name: str,
    config: OrchestratorConfig,
    tasks: Dict[str, ARCTask],
    task_ids: List[str],
    v1_results: Dict[str, Dict],
    output_dir: str,
) -> List[Dict[str, Any]]:
    config.output_dir = output_dir
    orch = GatedAdaptiveReasoningOrchestrator(config)
    results = []

    for i, task_id in enumerate(task_ids):
        if task_id not in tasks:
            continue
        task = tasks[task_id]
        train_pairs = [
            (ex.input_grid, ex.output_grid) for ex in task.train
            if ex.output_grid is not None
        ]
        test_inputs = [ex.input_grid for ex in task.test]
        test_outputs = [
            ex.output_grid for ex in task.test if ex.output_grid is not None
        ] or None

        trace = orch.solve_task(task_id, train_pairs, test_inputs, test_outputs)

        v1_solved = v1_results.get(task_id, {}).get("solved", False)
        row = {
            "task_id": task_id,
            "config": config_name,
            "v1_solved": v1_solved,
            "v2_solved": trace.final_status == "solved",
            "new_solve": (trace.final_status == "solved") and not v1_solved,
            "regression": v1_solved and (trace.final_status != "solved"),
            "false_positive": trace.verification.false_positive if trace.verification else False,
            "selected_module": trace.selected_proposal.module_name if trace.selected_proposal else None,
            "operator_family": trace.selected_proposal.operator_family if trace.selected_proposal else None,
            "n_proposals": len(trace.proposals),
            "runtime_seconds": trace.runtime_seconds,
            "final_status": trace.final_status,
        }
        results.append(row)

        if (i + 1) % 10 == 0:
            solved = sum(1 for r in results if r["v2_solved"])
            print(f"  [{i+1}/{len(task_ids)}] {config_name}: {solved} solved")

    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=OUTPUT_DIR)
    parser.add_argument("--configs", nargs="*", default=None)
    args = parser.parse_args()
    output_dir = args.output_dir

    print("=" * 60)
    print("  Full Pipeline Activation Ablation")
    print("=" * 60)

    os.makedirs(output_dir, exist_ok=True)

    print("\nLoading ARC tasks...")
    arc_tasks = load_arc_tasks(ARC_ROOT)
    tasks = {t.task_id: t for t in arc_tasks}
    print(f"  Loaded {len(tasks)} tasks")

    print("\nLoading v1 results...")
    v1_results = load_v1_results()
    print(f"  Loaded {len(v1_results)} v1 results")

    focused_ids = get_focused_task_ids(v1_results)
    print(f"  Focused subset: {len(focused_ids)} tasks")

    configs = ABLATION_CONFIGS
    if args.configs:
        configs = {k: v for k, v in configs.items() if k in args.configs}

    all_results = []
    for config_name, config in configs.items():
        print(f"\n--- Running ablation: {config_name} ---")
        results = run_ablation(config_name, config, tasks, focused_ids, v1_results, output_dir)
        all_results.extend(results)

    # Write CSV
    csv_path = os.path.join(output_dir, "ablation_results.csv")
    if all_results:
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=all_results[0].keys())
            writer.writeheader()
            writer.writerows(all_results)

    # Write summary
    by_config = defaultdict(list)
    for r in all_results:
        by_config[r["config"]].append(r)

    md_lines = [
        "# Full Pipeline Activation Ablation\n\n",
        f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n",
        "| Config | Evaluated | Solved | New | Regressions | FP | Mean Runtime |\n",
        "|--------|-----------|--------|-----|-------------|----|--------------|\n",
    ]
    for cn, rows in sorted(by_config.items()):
        n = len(rows)
        solved = sum(1 for r in rows if r["v2_solved"])
        new = sum(1 for r in rows if r["new_solve"])
        reg = sum(1 for r in rows if r["regression"])
        fp = sum(1 for r in rows if r["false_positive"])
        mean_rt = sum(r["runtime_seconds"] for r in rows) / max(n, 1)
        md_lines.append(
            f"| {cn} | {n} | {solved} | {new} | {reg} | {fp} | {mean_rt:.1f}s |\n"
        )

    # Module contributions per config
    md_lines.append("\n## Module Contributions per Config\n\n")
    for cn, rows in sorted(by_config.items()):
        mod_counts = defaultdict(int)
        for r in rows:
            if r["v2_solved"] and r["selected_module"]:
                mod_counts[r["selected_module"]] += 1
        if mod_counts:
            md_lines.append(f"### {cn}\n\n")
            for mod, count in sorted(mod_counts.items(), key=lambda x: -x[1]):
                md_lines.append(f"- {mod}: {count}\n")
            md_lines.append("\n")

    with open(os.path.join(output_dir, "ablation_summary.md"), "w") as f:
        f.writelines(md_lines)

    print(f"\n{'='*60}")
    print(f"  ABLATION COMPLETE")
    print(f"{'='*60}")
    for cn, rows in sorted(by_config.items()):
        solved = sum(1 for r in rows if r["v2_solved"])
        new = sum(1 for r in rows if r["new_solve"])
        fp = sum(1 for r in rows if r["false_positive"])
        print(f"  {cn}: {solved}/{len(rows)} solved, {new} new, {fp} FP")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
