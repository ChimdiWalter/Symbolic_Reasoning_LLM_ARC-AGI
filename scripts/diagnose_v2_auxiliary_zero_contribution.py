#!/usr/bin/env python3
"""Diagnose why v2 auxiliary modules contribute 0 new solves.

For each auxiliary config, analyze:
- modules triggered?
- proposals generated?
- proposals executable?
- verifier called?
- rejection reason?

Classifies failures into categories.
"""
import csv
import json
import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reasoning_project.adaptive_orchestrator import (
    GatedAdaptiveReasoningOrchestrator,
    OrchestratorConfig,
    TaskAnalysis,
)

OUTPUT_DIR = "outputs/full_novel_reasoning_pipeline_v2/executable_proposal_repair"

KNOWN_FRONTIER_TASKS = {
    "shape_completion": ["1d0a4b61", "8eb1be9a", "92e50de0", "a5313dff"],
    "position_recolor": ["4347f46a", "50cb2852", "bb43febb"],
    "many_to_few": ["56ff96f3"],
}

CONFIGS = {
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
    "v2_full_gated_orchestrator": OrchestratorConfig(),
}

FAILURE_CATEGORIES = [
    "module_not_triggered",
    "proposal_metadata_only",
    "missing_execute_function",
    "missing_parameters",
    "hypothesis_not_serializable",
    "verifier_field_mismatch",
    "train_consistency_failed",
    "LOO_failed",
    "proof_obligation_failed",
    "falsification_failed",
    "certificate_failure",
    "task_not_in_operator_family",
    "import_error_silent",
    "trigger_deadlock",
]


def load_arc_tasks():
    """Load ARC tasks."""
    task_dir = Path("data/arc/training")
    if not task_dir.exists():
        for candidate in [
            Path("data/training"),
            Path("/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project/data/arc/training"),
            Path("/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project/data/training"),
        ]:
            if candidate.exists():
                task_dir = candidate
                break

    tasks = {}
    if not task_dir.exists():
        print(f"WARNING: task dir {task_dir} not found")
        return tasks

    for f in sorted(task_dir.glob("*.json")):
        tid = f.stem
        with open(f) as fh:
            tasks[tid] = json.load(fh)
    return tasks


def diagnose_task(task_id, task, config_name, config):
    """Run a single task through the orchestrator and diagnose proposal failures."""
    train_pairs = [
        (np.array(ex["input"]), np.array(ex["output"]))
        for ex in task["train"]
    ]
    test_inputs = [np.array(ex["input"]) for ex in task["test"]]
    test_outputs = [np.array(ex["output"]) for ex in task["test"]]

    orch = GatedAdaptiveReasoningOrchestrator(config)

    analysis = orch.analyze_task(task_id, train_pairs)
    routes = orch._route_with_reasons(analysis)

    triggered = [m for m, (t, _) in routes.items() if t]
    skipped = {m: r for m, (t, r) in routes.items() if not t}

    deadline = time.time() + 300.0
    proposals = orch.collect_proposals(analysis, triggered, train_pairs, test_inputs, deadline=deadline)

    diagnosis_rows = []

    auxiliary_modules = [
        "frontier_operators", "property_expansion", "operator_memory",
        "manifold_memory", "near_solved_memory", "neural_advisory",
        "domain_morphism", "adapter_genesis",
    ]

    for module in auxiliary_modules:
        row = {
            "task_id": task_id,
            "config": config_name,
            "module": module,
            "triggered": module in triggered,
            "skip_reason": skipped.get(module, ""),
            "n_proposals": 0,
            "n_executable": 0,
            "failure_category": "module_not_triggered" if module not in triggered else "",
        }

        module_proposals = [p for p in proposals if p.module_name == module]
        row["n_proposals"] = len(module_proposals)

        for p in module_proposals:
            hyp = p.hypothesis
            has_execute = False
            if callable(hyp):
                has_execute = True
            elif isinstance(hyp, dict):
                if callable(hyp.get("execute")):
                    has_execute = True
                elif callable(hyp.get("operator")):
                    has_execute = True
                elif callable(hyp.get("prediction_fn")):
                    has_execute = True

            if has_execute:
                row["n_executable"] += 1

        if row["triggered"] and row["n_proposals"] == 0:
            if module == "frontier_operators":
                row["failure_category"] = "import_error_silent"
            elif module == "property_expansion":
                row["failure_category"] = "proposal_metadata_only"
            else:
                row["failure_category"] = "task_not_in_operator_family"
        elif row["triggered"] and row["n_proposals"] > 0 and row["n_executable"] == 0:
            row["failure_category"] = "missing_execute_function"
        elif row["triggered"] and row["n_executable"] > 0:
            # Had executable proposals — check if verifier rejected
            for p in module_proposals:
                outcome = orch.verifier.verify(p, train_pairs, test_inputs, test_outputs)
                if outcome.accepted:
                    row["failure_category"] = "accepted"
                    break
                elif outcome.rejection_reason:
                    row["failure_category"] = outcome.rejection_reason
                    break

        diagnosis_rows.append(row)

    return diagnosis_rows


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("Loading ARC tasks...")
    tasks = load_arc_tasks()
    if not tasks:
        print("ERROR: No tasks loaded")
        return

    all_frontier_ids = set()
    for family_tasks in KNOWN_FRONTIER_TASKS.values():
        for tid in family_tasks:
            if tid in tasks:
                all_frontier_ids.add(tid)

    if not all_frontier_ids:
        print("No known frontier tasks found in data, using first 10 tasks")
        all_frontier_ids = set(list(tasks.keys())[:10])

    print(f"Diagnosing {len(all_frontier_ids)} tasks × {len(CONFIGS)} configs")

    all_rows = []
    category_counts = Counter()

    for config_name, config in CONFIGS.items():
        print(f"\n--- Config: {config_name} ---")
        for tid in sorted(all_frontier_ids):
            task = tasks[tid]
            rows = diagnose_task(tid, task, config_name, config)
            all_rows.extend(rows)
            for r in rows:
                if r["failure_category"]:
                    category_counts[r["failure_category"]] += 1
            print(f"  {tid}: {sum(1 for r in rows if r['n_proposals'] > 0)} modules proposed, "
                  f"{sum(1 for r in rows if r['n_executable'] > 0)} executable")

    # Write CSV
    csv_path = os.path.join(OUTPUT_DIR, "diagnosis.csv")
    fieldnames = [
        "task_id", "config", "module", "triggered", "skip_reason",
        "n_proposals", "n_executable", "failure_category",
    ]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    # Write markdown summary
    md_path = os.path.join(OUTPUT_DIR, "diagnosis.md")
    with open(md_path, "w") as f:
        f.write("# Diagnosis: Why Auxiliary Modules Add 0 Solves\n\n")
        f.write(f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Tasks diagnosed: {len(all_frontier_ids)}\n")
        f.write(f"Configs: {len(CONFIGS)}\n\n")

        f.write("## Failure Category Summary\n\n")
        f.write("| Category | Count |\n")
        f.write("|----------|-------|\n")
        for cat, count in category_counts.most_common():
            f.write(f"| {cat} | {count} |\n")

        f.write("\n## Per-Module Summary\n\n")
        module_stats = defaultdict(lambda: {"triggered": 0, "proposed": 0, "executable": 0})
        for r in all_rows:
            m = r["module"]
            if r["triggered"]:
                module_stats[m]["triggered"] += 1
            if r["n_proposals"] > 0:
                module_stats[m]["proposed"] += 1
            if r["n_executable"] > 0:
                module_stats[m]["executable"] += 1

        f.write("| Module | Triggered | Proposed | Executable |\n")
        f.write("|--------|-----------|----------|------------|\n")
        for m in sorted(module_stats.keys()):
            s = module_stats[m]
            f.write(f"| {m} | {s['triggered']} | {s['proposed']} | {s['executable']} |\n")

        f.write("\n## Root Causes\n\n")
        f.write("1. **ShapeCompletionOperator**: Imports `detect_shape_completion_pattern` and "
                "`build_shape_completion_hypothesis` which DO NOT EXIST. "
                "Silent ImportError → empty proposals.\n")
        f.write("2. **PositionRecolorOperator**: Same — imports non-existent "
                "`detect_position_recolor_pattern` and `build_position_recolor_hypothesis`.\n")
        f.write("3. **ManyToFewGroupingOperator**: Returns metadata-only dict with NO `execute` key.\n")
        f.write("4. **PropertyExpansion**: Returns `{name, family, score}` — no execute function.\n")
        f.write("5. **OperatorMemory**: In-memory only, empty on fresh run.\n")
        f.write("6. **NeuralAdvisory**: Returns family rankings only, no execute.\n")
        f.write("7. **DomainMorphism**: Never triggers for ARC domain.\n")
        f.write("8. **ShapeCompletion trigger deadlock**: Only triggers when no size_change, "
                "but shape_completion only added to candidate_families when there IS size_change.\n")

    print(f"\nDiagnosis written to {csv_path} and {md_path}")
    print(f"\nTop failure categories:")
    for cat, count in category_counts.most_common(5):
        print(f"  {cat}: {count}")


if __name__ == "__main__":
    main()
