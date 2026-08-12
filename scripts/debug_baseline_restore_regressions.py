"""Debug each regressed task to find why proposals are now rejected.

Runs each task through isolated module paths and logs detailed proposal/verification info.
"""
from __future__ import annotations

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
    ModuleProposal,
)
from reasoning_project.proposal_verifier import ProposalVerifier
from reasoning_project.arc_adapter import load_arc_tasks, ARCTask

ARC_ROOT = Path(__file__).parent.parent / "data" / "arc"
OUTPUT_DIR = "outputs/full_novel_reasoning_pipeline_v2/baseline_restore_regression_repair"

REGRESSED_TASKS = [
    "2a5f8217",
    "08ed6ac7",
    "c8f0f002",
    "b1948b0a",
    "92e50de0",
    "bb43febb",
    "a5313dff",
    "ea32f347",
    "e98196ab",
]

CONFIGS_TO_TEST = {
    "static_only": OrchestratorConfig(
        enable_adapter_genesis=False,
        enable_manifold_memory=False,
        enable_near_solved_memory=False,
        enable_operator_memory=False,
        enable_neural_advisory=False,
        enable_domain_morphism=False,
        enable_property_expansion=False,
        enable_frontier_operators=False,
        enable_trace_invention=False,
        enable_static_portfolio=True,
    ),
    "trace_only": OrchestratorConfig(
        enable_adapter_genesis=False,
        enable_manifold_memory=False,
        enable_near_solved_memory=False,
        enable_operator_memory=False,
        enable_neural_advisory=False,
        enable_domain_morphism=False,
        enable_property_expansion=False,
        enable_frontier_operators=False,
        enable_trace_invention=True,
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
        enable_frontier_operators=True,
        enable_trace_invention=False,
        enable_static_portfolio=False,
    ),
    "core_with_frontier": OrchestratorConfig(
        enable_adapter_genesis=False,
        enable_manifold_memory=False,
        enable_neural_advisory=False,
        enable_domain_morphism=False,
        enable_property_expansion=False,
    ),
    "full_orchestrator": OrchestratorConfig(),
}


def verify_proposal_detailed(
    proposal: ModuleProposal,
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
    test_outputs: Optional[List[np.ndarray]],
) -> Dict[str, Any]:
    """Run verification and return detailed diagnostics."""
    verifier = ProposalVerifier()

    hypothesis = getattr(proposal, "hypothesis", None)
    has_executable = False
    executable = None

    if hypothesis is not None:
        executable = verifier._extract_executable(hypothesis)
        has_executable = executable is not None

    result = {
        "module": proposal.module_name,
        "family": proposal.operator_family,
        "selector": proposal.selector,
        "confidence": proposal.confidence,
        "has_hypothesis": hypothesis is not None,
        "has_executable": has_executable,
    }

    if not has_executable:
        result["rejection_reason"] = "no_executable"
        result["train_consistent"] = False
        result["loo_passed"] = False
        result["proof_passed"] = False
        result["falsification_passed"] = False
        result["accepted"] = False
        return result

    # Check train consistency with details
    train_ok = True
    train_details = []
    for i, (inp, expected_out) in enumerate(train_pairs):
        try:
            predicted = executable(inp)
            if predicted is None:
                train_details.append({"pair": i, "status": "returned_none"})
                train_ok = False
            elif not isinstance(predicted, np.ndarray):
                predicted = np.array(predicted)
                if predicted.shape != expected_out.shape:
                    train_details.append({
                        "pair": i, "status": "shape_mismatch",
                        "predicted_shape": list(predicted.shape),
                        "expected_shape": list(expected_out.shape),
                    })
                    train_ok = False
                elif not np.array_equal(predicted, expected_out):
                    diff_count = int(np.sum(predicted != expected_out))
                    train_details.append({
                        "pair": i, "status": "value_mismatch",
                        "diff_cells": diff_count,
                        "total_cells": int(expected_out.size),
                    })
                    train_ok = False
                else:
                    train_details.append({"pair": i, "status": "ok"})
            else:
                if predicted.shape != expected_out.shape:
                    train_details.append({
                        "pair": i, "status": "shape_mismatch",
                        "predicted_shape": list(predicted.shape),
                        "expected_shape": list(expected_out.shape),
                    })
                    train_ok = False
                elif not np.array_equal(predicted, expected_out):
                    diff_count = int(np.sum(predicted != expected_out))
                    train_details.append({
                        "pair": i, "status": "value_mismatch",
                        "diff_cells": diff_count,
                        "total_cells": int(expected_out.size),
                    })
                    train_ok = False
                else:
                    train_details.append({"pair": i, "status": "ok"})
        except Exception as e:
            train_details.append({"pair": i, "status": "exception", "error": str(e)[:200]})
            train_ok = False

    result["train_consistent"] = train_ok
    result["train_details"] = train_details

    if not train_ok:
        result["rejection_reason"] = "train_inconsistent"
        result["loo_passed"] = False
        result["proof_passed"] = False
        result["falsification_passed"] = False
        result["accepted"] = False
        return result

    # Full verification
    outcome = verifier.verify(proposal, train_pairs, test_inputs, test_outputs)
    result["loo_passed"] = outcome.loo_passed
    result["proof_passed"] = outcome.proof_obligations_passed
    result["falsification_passed"] = outcome.falsification_passed
    result["accepted"] = outcome.accepted
    result["false_positive"] = outcome.false_positive
    result["rejection_reason"] = outcome.rejection_reason
    result["certificate"] = outcome.certificate_path

    return result


def debug_task(
    task_id: str,
    task: ARCTask,
    configs: Dict[str, OrchestratorConfig],
) -> List[Dict[str, Any]]:
    """Run a task through all configs and collect detailed debug info."""
    train_pairs = [(ex.input_grid, ex.output_grid) for ex in task.train if ex.output_grid is not None]
    test_inputs = [ex.input_grid for ex in task.test]
    test_outputs = [ex.output_grid for ex in task.test if ex.output_grid is not None] or None

    all_results = []

    for config_name, config in configs.items():
        config.output_dir = OUTPUT_DIR
        orch = GatedAdaptiveReasoningOrchestrator(config)

        t0 = time.time()
        trace = orch.solve_task(task_id, train_pairs, test_inputs, test_outputs)
        elapsed = time.time() - t0

        for pi, proposal in enumerate(trace.proposals):
            detail = verify_proposal_detailed(proposal, train_pairs, test_inputs, test_outputs)
            detail["task_id"] = task_id
            detail["config"] = config_name
            detail["proposal_index"] = pi
            detail["total_proposals"] = len(trace.proposals)
            detail["final_status"] = trace.final_status
            detail["selected"] = (trace.selected_proposal is proposal) if trace.selected_proposal else False
            detail["runtime"] = elapsed
            detail["modules_triggered"] = ",".join(trace.triggered_modules)
            all_results.append(detail)

        if not trace.proposals:
            all_results.append({
                "task_id": task_id,
                "config": config_name,
                "proposal_index": -1,
                "total_proposals": 0,
                "final_status": trace.final_status,
                "selected": False,
                "runtime": elapsed,
                "modules_triggered": ",".join(trace.triggered_modules),
                "module": None,
                "family": None,
                "selector": None,
                "confidence": None,
                "has_hypothesis": False,
                "has_executable": False,
                "train_consistent": False,
                "loo_passed": False,
                "proof_passed": False,
                "falsification_passed": False,
                "accepted": False,
                "rejection_reason": "no_proposals",
            })

    return all_results


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("Loading ARC tasks...")
    arc_tasks = load_arc_tasks(ARC_ROOT)
    tasks = {t.task_id: t for t in arc_tasks}

    all_debug = []
    proposals_jsonl = []

    for task_id in REGRESSED_TASKS:
        if task_id not in tasks:
            print(f"  SKIP {task_id}: not found in ARC data")
            continue

        print(f"\n{'='*70}")
        print(f"  Debugging: {task_id}")
        print(f"{'='*70}")

        results = debug_task(task_id, tasks[task_id], CONFIGS_TO_TEST)
        all_debug.extend(results)

        for r in results:
            print(f"  {r['config']:25s} | {str(r.get('module','')):20s} | "
                  f"exec={str(r.get('has_executable','?')):5s} | "
                  f"train={str(r.get('train_consistent','?')):5s} | "
                  f"loo={str(r.get('loo_passed','?')):5s} | "
                  f"accept={str(r.get('accepted','?')):5s} | "
                  f"reason={r.get('rejection_reason','')}")

            proposals_jsonl.append({
                k: v for k, v in r.items()
                if k != "train_details" or (isinstance(v, list) and any(
                    d.get("status") != "ok" for d in v
                ))
            })

    # Write regression_debug.csv
    csv_path = os.path.join(OUTPUT_DIR, "regression_debug.csv")
    csv_fields = [
        "task_id", "config", "proposal_index", "total_proposals",
        "module", "family", "selector", "confidence",
        "has_executable", "train_consistent", "loo_passed",
        "proof_passed", "falsification_passed", "accepted",
        "false_positive", "rejection_reason", "final_status",
        "selected", "runtime", "modules_triggered",
    ]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_debug)
    print(f"\nWrote {csv_path}")

    # Write regression_proposals.jsonl
    jsonl_path = os.path.join(OUTPUT_DIR, "regression_proposals.jsonl")
    with open(jsonl_path, "w") as f:
        for row in proposals_jsonl:
            serializable = {}
            for k, v in row.items():
                try:
                    json.dumps(v)
                    serializable[k] = v
                except (TypeError, ValueError):
                    serializable[k] = str(v)
            f.write(json.dumps(serializable) + "\n")
    print(f"Wrote {jsonl_path}")

    # Write regression_debug.md
    md_path = os.path.join(OUTPUT_DIR, "regression_debug.md")
    with open(md_path, "w") as f:
        f.write("# Regression Debug Report\n\n")
        f.write(f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        for task_id in REGRESSED_TASKS:
            task_rows = [r for r in all_debug if r["task_id"] == task_id]
            if not task_rows:
                continue

            f.write(f"## Task: `{task_id}`\n\n")
            f.write("| Config | Module | Family | Executable | Train | LOO | Accept | Reason |\n")
            f.write("|--------|--------|--------|-----------|-------|-----|--------|--------|\n")
            for r in task_rows:
                f.write(f"| {r.get('config','')} | {r.get('module','')} | "
                        f"{r.get('family','')} | {r.get('has_executable','')} | "
                        f"{r.get('train_consistent','')} | {r.get('loo_passed','')} | "
                        f"{r.get('accepted','')} | {r.get('rejection_reason','')} |\n")

            # Summarize train_details for failing proposals
            failing = [r for r in task_rows if r.get("train_details")]
            for r in failing:
                details = r.get("train_details", [])
                bad = [d for d in details if d.get("status") != "ok"]
                if bad:
                    f.write(f"\n**{r['config']}/{r.get('module','')}** train failures:\n")
                    for d in bad:
                        f.write(f"- Pair {d['pair']}: {d['status']}")
                        if "diff_cells" in d:
                            f.write(f" ({d['diff_cells']}/{d['total_cells']} cells differ)")
                        if "error" in d:
                            f.write(f" — {d['error']}")
                        f.write("\n")
            f.write("\n---\n\n")

        # Summary
        f.write("## Summary\n\n")
        for task_id in REGRESSED_TASKS:
            task_rows = [r for r in all_debug if r["task_id"] == task_id]
            any_solved = any(r.get("accepted") for r in task_rows)
            configs_solved = [r["config"] for r in task_rows if r.get("accepted")]
            configs_failed = [r["config"] for r in task_rows
                             if r.get("total_proposals", 0) > 0 and not r.get("accepted")]
            f.write(f"- `{task_id}`: {'SOLVABLE' if any_solved else 'BROKEN'}")
            if configs_solved:
                f.write(f" (solved by: {', '.join(configs_solved)})")
            if configs_failed:
                reasons = set(r.get("rejection_reason", "") for r in task_rows
                              if r["config"] in configs_failed and r.get("rejection_reason"))
                f.write(f" (failed in: {', '.join(configs_failed)}; reasons: {reasons})")
            f.write("\n")

    print(f"Wrote {md_path}")
    print("\nDone.")


if __name__ == "__main__":
    main()
