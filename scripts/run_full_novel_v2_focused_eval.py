"""Focused evaluation of the Full Novel Reasoning Pipeline v2.

Evaluates the orchestrator on targeted task subsets to validate integration
before committing to a full 1000-task run.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from reasoning_project.adaptive_orchestrator import (
    GatedAdaptiveReasoningOrchestrator,
    OrchestratorConfig,
    OrchestratorTrace,
)
from reasoning_project.arc_adapter import load_arc_tasks, load_conceptarc_tasks, ARCTask

ARC_ROOT = Path(__file__).parent.parent / "data" / "arc"
CONCEPTARC_ROOT = Path(__file__).parent.parent / "data" / "conceptarc"


OUTPUT_DIR = "outputs/full_novel_reasoning_pipeline_v2/focused_eval"


def load_v1_results(path: str = "outputs/full_arc1000_novel_pipeline/progress.jsonl") -> Dict[str, Dict]:
    results = {}
    if not os.path.exists(path):
        return results
    with open(path) as f:
        for line in f:
            if line.strip():
                row = json.loads(line)
                # v1 uses final_config_that_solved or operator_promoted as solve indicator
                row["solved"] = (
                    row.get("final_config_that_solved") is not None or
                    row.get("operator_promoted", False) or
                    row.get("solved_by_static", False)
                )
                row["certificate"] = row.get("certificate_emitted", False)
                row["runtime"] = row.get("runtime_seconds", 0)
                results[row.get("task_id", "")] = row
    return results


def get_task_subsets(v1_results: Dict[str, Dict], all_tasks: Dict[str, Any]) -> Dict[str, List[str]]:
    v1_solved = [tid for tid, r in v1_results.items() if r.get("solved")]
    v1_unsolved = [tid for tid, r in v1_results.items() if not r.get("solved")]
    v1_certified = [tid for tid, r in v1_results.items() if r.get("certificate")]

    # Known frontier operator tasks (expanded with verified-solvable tasks)
    shape_completion_tasks = ["d89b689b", "e9ac8c9e", "1d0a4b61", "8eb1be9a", "92e50de0", "a5313dff"]
    position_recolor_tasks = ["a48eeaf7", "4347f46a", "50cb2852", "bb43febb"]
    many_to_few_tasks = ["56ff96f3"]
    color_transfer_tasks = ["2a5f8217"]

    # Sort unsolved by runtime (timeout-heavy first)
    timeout_heavy = sorted(
        [(tid, r.get("runtime", 0)) for tid, r in v1_results.items() if not r.get("solved")],
        key=lambda x: -x[1]
    )[:50]

    import random
    rng = random.Random(42)
    random_unsolved = rng.sample(v1_unsolved, min(100, len(v1_unsolved)))

    # Top 100 failures (first 100 unsolved in sorted order)
    top_failures = v1_unsolved[:100]

    return {
        "v1_solved": v1_solved,
        "v1_certified": v1_certified,
        "shape_completion": shape_completion_tasks,
        "position_recolor": position_recolor_tasks,
        "many_to_few": many_to_few_tasks,
        "color_transfer": color_transfer_tasks,
        "top_100_failures": top_failures,
        "random_100_unsolved": random_unsolved,
        "timeout_heavy_50": [tid for tid, _ in timeout_heavy],
    }


CONFIGS = {
    "v2_full_gated_orchestrator": OrchestratorConfig(),
    "v2_core_only": OrchestratorConfig(
        enable_adapter_genesis=False,
        enable_manifold_memory=False,
        enable_neural_advisory=False,
        enable_domain_morphism=False,
    ),
    "v2_with_property_expansion": OrchestratorConfig(
        enable_adapter_genesis=False,
        enable_manifold_memory=False,
        enable_neural_advisory=False,
        enable_domain_morphism=False,
        enable_frontier_operators=False,
    ),
    "v2_with_frontier_operators": OrchestratorConfig(
        enable_adapter_genesis=False,
        enable_manifold_memory=False,
        enable_neural_advisory=False,
        enable_domain_morphism=False,
        enable_property_expansion=False,
    ),
    "v2_with_manifold_memory": OrchestratorConfig(
        enable_adapter_genesis=False,
        enable_neural_advisory=False,
        enable_domain_morphism=False,
        enable_frontier_operators=False,
        enable_property_expansion=False,
    ),
}


def _load_checkpoint(checkpoint_path: str) -> List[Dict[str, Any]]:
    """Load previously completed results from checkpoint JSONL."""
    results = []
    if os.path.exists(checkpoint_path):
        with open(checkpoint_path) as f:
            for line in f:
                if line.strip():
                    results.append(json.loads(line))
    return results


def _append_checkpoint(checkpoint_path: str, row: Dict[str, Any]) -> None:
    """Append a single result row to checkpoint file."""
    with open(checkpoint_path, "a") as f:
        f.write(json.dumps(row) + "\n")


def run_evaluation(
    config_name: str,
    config: OrchestratorConfig,
    tasks: Dict[str, ARCTask],
    task_ids: List[str],
    v1_results: Dict[str, Dict],
    output_dir: str,
) -> List[Dict[str, Any]]:
    config.output_dir = output_dir
    orch = GatedAdaptiveReasoningOrchestrator(config)

    checkpoint_path = os.path.join(output_dir, f"checkpoint_{config_name}.jsonl")
    existing = _load_checkpoint(checkpoint_path)
    done_keys = {(r["task_id"], r["config"]) for r in existing}
    if existing:
        print(f"  Resuming {config_name}: {len(existing)} tasks already done, skipping them")

    results = list(existing)

    for i, task_id in enumerate(task_ids):
        if task_id not in tasks:
            continue
        if (task_id, config_name) in done_keys:
            continue

        task = tasks[task_id]
        train_pairs = [(ex.input_grid, ex.output_grid) for ex in task.train if ex.output_grid is not None]
        test_inputs = [ex.input_grid for ex in task.test]
        test_outputs = [ex.output_grid for ex in task.test if ex.output_grid is not None] or None

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
            "modules_triggered": ",".join(trace.triggered_modules),
            "n_proposals": len(trace.proposals),
            "selected_module": trace.selected_proposal.module_name if trace.selected_proposal else None,
            "operator_family": trace.selected_proposal.operator_family if trace.selected_proposal else None,
            "certificate": trace.verification.certificate_path if trace.verification else None,
            "runtime_seconds": trace.runtime_seconds,
            "final_status": trace.final_status,
        }
        results.append(row)
        _append_checkpoint(checkpoint_path, row)

        if (i + 1) % 10 == 0 or trace.final_status == "solved":
            n_done = sum(1 for r in results if r["config"] == config_name)
            print(f"  [{n_done}/{len(task_ids)}] {config_name}: "
                  f"{sum(1 for r in results if r['v2_solved'])} solved, "
                  f"{sum(1 for r in results if r['new_solve'])} new",
                  flush=True)

    return results


def write_summary(all_results: List[Dict[str, Any]], output_dir: str) -> None:
    os.makedirs(output_dir, exist_ok=True)

    # Write full results CSV
    csv_path = os.path.join(output_dir, "results.csv")
    if all_results:
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=all_results[0].keys())
            writer.writeheader()
            writer.writerows(all_results)

    # Compute summary per config
    from collections import defaultdict
    by_config = defaultdict(list)
    for r in all_results:
        by_config[r["config"]].append(r)

    summary_lines = [
        "# Focused Evaluation Summary: Full Novel Pipeline v2\n",
        f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n",
        f"Total evaluations: {len(all_results)}\n\n",
        "## Per-Configuration Results\n\n",
        "| Config | Evaluated | Solved | New | Regressions | FP | Mean Runtime |\n",
        "|--------|-----------|--------|-----|-------------|----|--------------|\n",
    ]

    for config_name, rows in sorted(by_config.items()):
        n = len(rows)
        solved = sum(1 for r in rows if r["v2_solved"])
        new = sum(1 for r in rows if r["new_solve"])
        reg = sum(1 for r in rows if r["regression"])
        fp = sum(1 for r in rows if r["false_positive"])
        mean_rt = sum(r["runtime_seconds"] for r in rows) / max(n, 1)
        summary_lines.append(
            f"| {config_name} | {n} | {solved} | {new} | {reg} | {fp} | {mean_rt:.1f}s |\n"
        )

    # Module contribution table
    summary_lines.append("\n## Module Contributions (full orchestrator)\n\n")
    full_orch = by_config.get("v2_full_gated_orchestrator", [])
    module_counts: Dict[str, int] = defaultdict(int)
    for r in full_orch:
        if r["v2_solved"] and r["selected_module"]:
            module_counts[r["selected_module"]] += 1

    if module_counts:
        summary_lines.append("| Module | Solves |\n|--------|--------|\n")
        for mod, count in sorted(module_counts.items(), key=lambda x: -x[1]):
            summary_lines.append(f"| {mod} | {count} |\n")

    # Success criteria check
    summary_lines.append("\n## Success Criteria\n\n")
    full_results = by_config.get("v2_full_gated_orchestrator", [])
    v1_reproduced = all(
        r["v2_solved"] for r in full_results if r.get("v1_solved")
    ) if full_results else False
    total_fp = sum(1 for r in full_results if r["false_positive"])
    total_new = sum(1 for r in full_results if r["new_solve"])
    total_reg = sum(1 for r in full_results if r["regression"])

    summary_lines.append(f"- v1 certified reproduced: {'YES' if v1_reproduced else 'NO'}\n")
    summary_lines.append(f"- New solves over v1: {total_new}\n")
    summary_lines.append(f"- Regressions: {total_reg}\n")
    summary_lines.append(f"- False positives: {total_fp}\n")
    summary_lines.append(f"- Zero FP maintained: {'YES' if total_fp == 0 else 'NO'}\n")

    with open(os.path.join(output_dir, "summary.md"), "w") as f:
        f.writelines(summary_lines)

    # Module contributions CSV
    if module_counts:
        with open(os.path.join(output_dir, "module_contributions.csv"), "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["module", "solves"])
            for mod, count in sorted(module_counts.items(), key=lambda x: -x[1]):
                writer.writerows([[mod, count]])

    print(f"\n{'='*60}")
    print(f"  FOCUSED EVALUATION COMPLETE")
    print(f"{'='*60}")
    print(f"  Total evaluations: {len(all_results)}")
    for config_name, rows in sorted(by_config.items()):
        solved = sum(1 for r in rows if r["v2_solved"])
        new = sum(1 for r in rows if r["new_solve"])
        print(f"  {config_name}: {solved}/{len(rows)} solved, {new} new")
    print(f"  Regressions: {total_reg}")
    print(f"  False positives: {total_fp}")
    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=OUTPUT_DIR)
    parser.add_argument("--configs", default=None,
                        help="Comma-separated config names to run (default: all)")
    args = parser.parse_args()
    output_dir = args.output_dir

    print("=" * 60)
    print("  Full Novel Reasoning Pipeline v2: Focused Evaluation")
    print("=" * 60)

    os.makedirs(output_dir, exist_ok=True)

    print("\nLoading ARC tasks...")
    arc_task_list = load_arc_tasks(ARC_ROOT)
    tasks = {t.task_id: t for t in arc_task_list}
    print(f"  Loaded {len(tasks)} tasks")

    print("\nLoading v1 results...")
    v1_results = load_v1_results()
    print(f"  Loaded {len(v1_results)} v1 results")

    subsets = get_task_subsets(v1_results, tasks)
    print(f"\n  Task subsets:")
    for name, ids in subsets.items():
        print(f"    {name}: {len(ids)} tasks")

    # Focused subset: v1 solved + certified + frontier + sample of unsolved
    focused_ids = list(set(
        subsets["v1_solved"] +
        subsets["v1_certified"] +
        subsets["shape_completion"] +
        subsets["position_recolor"] +
        subsets.get("many_to_few", []) +
        subsets["color_transfer"] +
        subsets["top_100_failures"][:50]
    ))
    print(f"\n  Combined focused subset: {len(focused_ids)} tasks")

    selected_configs = CONFIGS
    if args.configs:
        requested = [c.strip() for c in args.configs.split(",")]
        selected_configs = {k: v for k, v in CONFIGS.items() if k in requested}
        missing = [c for c in requested if c not in CONFIGS]
        if missing:
            print(f"  WARNING: unknown configs ignored: {missing}")
            print(f"  Available: {list(CONFIGS.keys())}")

    all_results = []
    for config_name, config in selected_configs.items():
        print(f"\n--- Running config: {config_name} ---")
        results = run_evaluation(
            config_name, config, tasks, focused_ids, v1_results, output_dir
        )
        all_results.extend(results)

    write_summary(all_results, output_dir)


if __name__ == "__main__":
    main()
