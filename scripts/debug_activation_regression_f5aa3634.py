"""Debug the f5aa3634 regression introduced by activation repair.

Runs f5aa3634 through multiple pipeline configurations and logs detailed
diagnostics for each: modules triggered, proposals generated, verification
outcomes, and why the final status became false_positive_rejected.
"""
from __future__ import annotations

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
from reasoning_project.proposal_verifier import ProposalVerifier
from reasoning_project.arc_adapter import load_arc_tasks

ARC_ROOT = Path(__file__).parent.parent / "data" / "arc"
OUTPUT_DIR = "outputs/full_novel_reasoning_pipeline_v2/activation_regression_repair"
TASK_ID = "f5aa3634"


def run_config(name: str, config: OrchestratorConfig, task, output_dir: str) -> Dict[str, Any]:
    train_pairs = [(ex.input_grid, ex.output_grid) for ex in task.train if ex.output_grid is not None]
    test_inputs = [ex.input_grid for ex in task.test]
    test_outputs = [ex.output_grid for ex in task.test if ex.output_grid is not None] or None

    orch = GatedAdaptiveReasoningOrchestrator(config)
    trace = orch.solve_task(TASK_ID, train_pairs, test_inputs, test_outputs)

    proposal_details = []
    verifier = ProposalVerifier()
    for i, proposal in enumerate(trace.proposals):
        outcome = verifier.verify(proposal, train_pairs, test_inputs, test_outputs)
        executable = None
        if isinstance(proposal.hypothesis, dict) and callable(proposal.hypothesis.get("execute")):
            executable = proposal.hypothesis["execute"]
        elif callable(proposal.hypothesis):
            executable = proposal.hypothesis

        predictions = []
        if executable:
            for ti in test_inputs:
                try:
                    pred = executable(ti)
                    predictions.append(pred.tolist() if pred is not None else None)
                except Exception as e:
                    predictions.append(f"ERROR: {e}")

        proposal_details.append({
            "index": i,
            "module": proposal.module_name,
            "type": proposal.proposal_type,
            "family": proposal.operator_family,
            "selector": str(proposal.selector),
            "confidence": proposal.confidence,
            "has_executable": executable is not None,
            "verification": {
                "accepted": outcome.accepted,
                "train_consistent": outcome.train_consistent,
                "loo_passed": outcome.loo_passed,
                "proof_obligations_passed": outcome.proof_obligations_passed,
                "falsification_passed": outcome.falsification_passed,
                "false_positive": outcome.false_positive,
                "rejection_reason": outcome.rejection_reason,
                "evidence": outcome.evidence,
            },
            "predictions_match_test": (
                all(
                    isinstance(p, list) and np.array_equal(np.array(p), to)
                    for p, to in zip(predictions, [ex.output_grid for ex in task.test if ex.output_grid is not None])
                )
                if predictions and test_outputs else None
            ),
        })

    result = {
        "config_name": name,
        "final_status": trace.final_status,
        "modules_triggered": trace.triggered_modules,
        "n_proposals": len(trace.proposals),
        "selected_module": trace.selected_proposal.module_name if trace.selected_proposal else None,
        "operator_family": trace.selected_proposal.operator_family if trace.selected_proposal else None,
        "runtime_seconds": trace.runtime_seconds,
        "proposals": proposal_details,
    }

    return result


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    tasks = {t.task_id: t for t in load_arc_tasks(ARC_ROOT)}
    if TASK_ID not in tasks:
        print(f"ERROR: Task {TASK_ID} not found in ARC data")
        return

    task = tasks[TASK_ID]
    print(f"Debugging task {TASK_ID}")
    print(f"  Train pairs: {len(task.train)}")
    print(f"  Test pairs: {len(task.test)}")

    configs = {
        "full_orchestrator": OrchestratorConfig(),
        "static_portfolio_only": OrchestratorConfig(
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
        "trace_invention_only": OrchestratorConfig(
            enable_adapter_genesis=False,
            enable_manifold_memory=False,
            enable_near_solved_memory=False,
            enable_operator_memory=False,
            enable_neural_advisory=False,
            enable_domain_morphism=False,
            enable_property_expansion=False,
            enable_frontier_operators=False,
            enable_static_portfolio=False,
        ),
        "frontier_only": OrchestratorConfig(
            enable_adapter_genesis=False,
            enable_manifold_memory=False,
            enable_near_solved_memory=False,
            enable_operator_memory=False,
            enable_neural_advisory=False,
            enable_domain_morphism=False,
            enable_property_expansion=False,
            enable_trace_invention=False,
            enable_static_portfolio=False,
        ),
        "property_expansion_only": OrchestratorConfig(
            enable_adapter_genesis=False,
            enable_manifold_memory=False,
            enable_near_solved_memory=False,
            enable_operator_memory=False,
            enable_neural_advisory=False,
            enable_domain_morphism=False,
            enable_frontier_operators=False,
            enable_trace_invention=False,
            enable_static_portfolio=False,
        ),
        "no_auxiliary_modules": OrchestratorConfig(
            enable_adapter_genesis=False,
            enable_manifold_memory=False,
            enable_neural_advisory=False,
            enable_domain_morphism=False,
            enable_frontier_operators=False,
            enable_property_expansion=False,
        ),
    }

    all_results = []
    proposals_jsonl = []

    for name, config in configs.items():
        print(f"\n--- Config: {name} ---")
        result = run_config(name, config, task, OUTPUT_DIR)
        all_results.append(result)
        print(f"  Status: {result['final_status']}")
        print(f"  Proposals: {result['n_proposals']}")
        print(f"  Selected: {result['selected_module']} ({result['operator_family']})")
        print(f"  Runtime: {result['runtime_seconds']:.2f}s")

        for p in result["proposals"]:
            print(f"    [{p['index']}] {p['module']}/{p['family']} "
                  f"conf={p['confidence']:.2f} "
                  f"train={p['verification']['train_consistent']} "
                  f"loo={p['verification']['loo_passed']} "
                  f"proof={p['verification']['proof_obligations_passed']} "
                  f"fals={p['verification']['falsification_passed']} "
                  f"fp={p['verification']['false_positive']} "
                  f"reject={p['verification']['rejection_reason']}")
            proposals_jsonl.append({
                "config": name,
                "task_id": TASK_ID,
                **{k: v for k, v in p.items() if k != "predictions_match_test"},
            })

    # Write outputs
    trace_path = os.path.join(OUTPUT_DIR, "f5aa3634_trace.json")
    with open(trace_path, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\nTrace written to {trace_path}")

    proposals_path = os.path.join(OUTPUT_DIR, "f5aa3634_proposals.jsonl")
    with open(proposals_path, "w") as f:
        for row in proposals_jsonl:
            f.write(json.dumps(row, default=str) + "\n")
    print(f"Proposals written to {proposals_path}")

    # Write summary
    summary_lines = [
        f"# f5aa3634 Regression Debug\n\n",
        f"**Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n",
        f"## Results by Config\n\n",
        f"| Config | Status | Proposals | Selected | Family | Runtime |\n",
        f"|--------|--------|-----------|----------|--------|--------|\n",
    ]
    for r in all_results:
        summary_lines.append(
            f"| {r['config_name']} | {r['final_status']} | {r['n_proposals']} | "
            f"{r['selected_module'] or '-'} | {r['operator_family'] or '-'} | "
            f"{r['runtime_seconds']:.2f}s |\n"
        )

    summary_lines.append("\n## Proposal Details (full_orchestrator)\n\n")
    full_result = next((r for r in all_results if r["config_name"] == "full_orchestrator"), None)
    if full_result:
        for p in full_result["proposals"]:
            v = p["verification"]
            summary_lines.append(
                f"- **[{p['index']}] {p['module']}/{p['family']}** "
                f"(conf={p['confidence']:.2f}): "
                f"train={v['train_consistent']}, loo={v['loo_passed']}, "
                f"proof={v['proof_obligations_passed']}, fals={v['falsification_passed']}, "
                f"fp={v['false_positive']}"
            )
            if v['rejection_reason']:
                summary_lines.append(f"  → rejected: {v['rejection_reason']}")
            summary_lines.append("\n")

    summary_lines.append("\n## Diagnosis\n\n")
    static_only = next((r for r in all_results if r["config_name"] == "static_portfolio_only"), None)
    if static_only and static_only["final_status"] == "solved":
        summary_lines.append(
            "Static portfolio ALONE solves f5aa3634. The regression is caused by "
            "interaction between modules in the full orchestrator, not by the static "
            "portfolio itself.\n"
        )
    elif static_only:
        summary_lines.append(
            f"Static portfolio alone: {static_only['final_status']}. "
            f"This suggests the static portfolio code itself may have been affected.\n"
        )

    debug_path = os.path.join(OUTPUT_DIR, "f5aa3634_debug.md")
    with open(debug_path, "w") as f:
        f.writelines(summary_lines)
    print(f"Debug summary written to {debug_path}")


if __name__ == "__main__":
    main()
