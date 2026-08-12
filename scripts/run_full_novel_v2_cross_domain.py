"""Cross-domain v2 evaluation with the Gated Adaptive Reasoning Orchestrator.

Tests the orchestrator on grid, graph, chess, molecule, ConceptARC,
and domain-morphism transfer cases.
"""
from __future__ import annotations

import csv
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from reasoning_project.adaptive_orchestrator import (
    GatedAdaptiveReasoningOrchestrator,
    OrchestratorConfig,
)
from reasoning_project.arc_adapter import load_arc_tasks, load_conceptarc_tasks, ARCTask

ARC_ROOT = Path(__file__).parent.parent / "data" / "arc"
CONCEPTARC_ROOT = Path(__file__).parent.parent / "data" / "conceptarc"


OUTPUT_DIR = "outputs/full_novel_reasoning_pipeline_v2/cross_domain"


CROSS_DOMAIN_CONFIGS = {
    "hand_coded_adapter_only": OrchestratorConfig(
        enable_adapter_genesis=False,
        enable_domain_morphism=False,
        enable_manifold_memory=False,
        enable_neural_advisory=False,
    ),
    "adapter_genesis_signature": OrchestratorConfig(
        enable_adapter_genesis=True,
        enable_domain_morphism=False,
        enable_manifold_memory=False,
        enable_neural_advisory=False,
    ),
    "domain_morphism": OrchestratorConfig(
        enable_adapter_genesis=True,
        enable_domain_morphism=True,
        enable_manifold_memory=False,
        enable_neural_advisory=False,
    ),
    "full_gated_orchestrator": OrchestratorConfig(
        enable_adapter_genesis=True,
        enable_domain_morphism=True,
        enable_manifold_memory=True,
        enable_neural_advisory=True,
    ),
}


def load_cross_domain_tasks() -> Dict[str, List[Dict[str, Any]]]:
    domains = {}

    # ConceptARC
    try:
        concept_task_list = load_conceptarc_tasks(CONCEPTARC_ROOT, max_tasks=50)
        concept_list = []
        for task in concept_task_list:
            concept_list.append({
                "task_id": task.task_id,
                "domain": "conceptarc",
                "train": [{"input": ex.input_grid, "output": ex.output_grid} for ex in task.train],
                "test": [{"input": ex.input_grid, "output": ex.output_grid} for ex in task.test],
            })
        domains["conceptarc"] = concept_list
    except Exception:
        domains["conceptarc"] = []

    # Cross-domain benchmark (grid, graph, chess, molecule)
    try:
        from reasoning_project.benchmark_generator import generate_cross_domain_benchmark
        benchmark = generate_cross_domain_benchmark()
        for domain_name, tasks in benchmark.items():
            domain_list = []
            for task in tasks:
                domain_list.append({
                    "task_id": task.get("id", f"{domain_name}_{len(domain_list)}"),
                    "domain": domain_name,
                    "train": task.get("train", []),
                    "test": task.get("test", []),
                })
            domains[domain_name] = domain_list
    except Exception:
        pass

    return domains


def run_cross_domain_eval(
    config_name: str,
    config: OrchestratorConfig,
    domain_tasks: Dict[str, List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    results = []

    for domain_name, tasks in domain_tasks.items():
        config.output_dir = OUTPUT_DIR
        orch = GatedAdaptiveReasoningOrchestrator(config)

        for task in tasks:
            task_id = task["task_id"]
            domain = task["domain"]

            try:
                train_pairs = [(np.array(p["input"]), np.array(p["output"])) for p in task["train"]]
                test_inputs = [np.array(p["input"]) for p in task["test"]]
                test_outputs = [np.array(p["output"]) for p in task["test"]] if task["test"] else None
            except Exception:
                continue

            trace = orch.solve_task(task_id, train_pairs, test_inputs, test_outputs, domain=domain)

            row = {
                "task_id": task_id,
                "domain": domain,
                "config": config_name,
                "solved": trace.final_status == "solved",
                "false_positive": trace.verification.false_positive if trace.verification else False,
                "modules_triggered": ",".join(trace.triggered_modules),
                "selected_module": trace.selected_proposal.module_name if trace.selected_proposal else None,
                "adapter_genesis_used": "adapter_genesis" in trace.triggered_modules,
                "domain_morphism_used": "domain_morphism" in trace.triggered_modules,
                "certificate": trace.verification.certificate_path if trace.verification else None,
                "runtime_seconds": trace.runtime_seconds,
                "final_status": trace.final_status,
            }
            results.append(row)

    return results


def write_cross_domain_summary(all_results: List[Dict[str, Any]], output_dir: str) -> None:
    os.makedirs(output_dir, exist_ok=True)

    # Write CSV
    if all_results:
        csv_path = os.path.join(output_dir, "results.csv")
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=all_results[0].keys())
            writer.writeheader()
            writer.writerows(all_results)

    # Summary by domain x config
    from collections import defaultdict
    summary = defaultdict(lambda: defaultdict(list))
    for r in all_results:
        summary[r["domain"]][r["config"]].append(r)

    lines = [
        "# Cross-Domain v2 Evaluation Summary\n\n",
        f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n",
        "## Results by Domain x Config\n\n",
        "| Domain | Config | Evaluated | Solved | FP |\n",
        "|--------|--------|-----------|--------|----|\n",
    ]

    for domain in sorted(summary.keys()):
        for config in sorted(summary[domain].keys()):
            rows = summary[domain][config]
            n = len(rows)
            solved = sum(1 for r in rows if r["solved"])
            fp = sum(1 for r in rows if r["false_positive"])
            lines.append(f"| {domain} | {config} | {n} | {solved} | {fp} |\n")

    with open(os.path.join(output_dir, "summary.md"), "w") as f:
        f.writelines(lines)

    total_solved = sum(1 for r in all_results if r["solved"])
    total_fp = sum(1 for r in all_results if r["false_positive"])
    print(f"\n{'='*60}")
    print(f"  CROSS-DOMAIN v2 EVALUATION COMPLETE")
    print(f"{'='*60}")
    print(f"  Total: {len(all_results)} evaluations")
    print(f"  Solved: {total_solved}")
    print(f"  FP: {total_fp}")
    print(f"{'='*60}")


def main():
    print("=" * 60)
    print("  Full Novel Pipeline v2: Cross-Domain Evaluation")
    print("=" * 60)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("\nLoading cross-domain tasks...")
    domain_tasks = load_cross_domain_tasks()
    for domain, tasks in domain_tasks.items():
        print(f"  {domain}: {len(tasks)} tasks")

    all_results = []
    for config_name, config in CROSS_DOMAIN_CONFIGS.items():
        print(f"\n--- Config: {config_name} ---")
        results = run_cross_domain_eval(config_name, config, domain_tasks)
        all_results.extend(results)

    write_cross_domain_summary(all_results, OUTPUT_DIR)


if __name__ == "__main__":
    main()
