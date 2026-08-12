"""Phase 1: Full module-contribution audit for the v2 pipeline.

For every module, reports:
  - how often triggered
  - proposals generated (total, executable, metadata-only)
  - proposals reaching verifier
  - failure breakdown (train_inconsistent, loo_failed, proof_failed, falsification_failed)
  - certificates emitted
  - solves / new solves

Reads the existing focused-eval results.csv for solve counts, then re-runs
the full orchestrator on 86 tasks with detailed trace capture.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from reasoning_project.adaptive_orchestrator import (
    GatedAdaptiveReasoningOrchestrator,
    ModuleProposal,
    OrchestratorConfig,
    OrchestratorTrace,
)
from reasoning_project.arc_adapter import load_arc_tasks, ARCTask
from reasoning_project.proposal_verifier import ProposalVerifier, VerificationOutcome

ARC_ROOT = Path(__file__).parent.parent / "data" / "arc"
OUTPUT_DIR = "outputs/full_novel_reasoning_pipeline_v2/full_pipeline_activation_repair"

ALL_MODULES = [
    "static_portfolio",
    "trace_invention",
    "frontier_operators",
    "property_expansion",
    "manifold_memory",
    "operator_memory",
    "near_solved_memory",
    "neural_advisory",
    "adapter_genesis",
    "domain_morphism",
]


@dataclass
class ModuleStats:
    module: str
    triggered: int = 0
    not_triggered: int = 0
    proposals_total: int = 0
    proposals_executable: int = 0
    proposals_metadata_only: int = 0
    proposals_reached_verifier: int = 0
    failed_train_consistency: int = 0
    failed_loo: int = 0
    failed_proof_obligations: int = 0
    failed_falsification: int = 0
    certificates_emitted: int = 0
    solved: int = 0
    new_solves: int = 0


def is_executable(proposal: ModuleProposal) -> bool:
    hyp = proposal.hypothesis
    if callable(hyp):
        return True
    if isinstance(hyp, dict) and callable(hyp.get("execute")):
        return True
    return False


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

    focused = list(set(
        v1_solved + v1_certified + shape_completion_tasks +
        position_recolor_tasks + many_to_few_tasks + color_transfer_tasks +
        top_failures
    ))
    return focused


def run_audit(
    tasks: Dict[str, ARCTask],
    task_ids: List[str],
    v1_results: Dict[str, Dict],
    output_dir: str,
) -> Tuple[Dict[str, ModuleStats], List[Dict[str, Any]]]:
    config = OrchestratorConfig()
    config.output_dir = output_dir
    orch = GatedAdaptiveReasoningOrchestrator(config)

    stats = {m: ModuleStats(module=m) for m in ALL_MODULES}
    failure_rows = []

    n_tasks = len(task_ids)
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
        v2_solved = trace.final_status == "solved"
        is_new = v2_solved and not v1_solved

        triggered_set = set(trace.triggered_modules)
        skipped_set = set(trace.skipped_modules.keys())

        for m in ALL_MODULES:
            if m in triggered_set:
                stats[m].triggered += 1
            else:
                stats[m].not_triggered += 1

        proposals_by_module: Dict[str, List[ModuleProposal]] = defaultdict(list)
        for p in trace.proposals:
            proposals_by_module[p.module_name].append(p)

        for m in ALL_MODULES:
            module_proposals = proposals_by_module.get(m, [])
            stats[m].proposals_total += len(module_proposals)
            for p in module_proposals:
                if is_executable(p):
                    stats[m].proposals_executable += 1
                else:
                    stats[m].proposals_metadata_only += 1

        # Verify each proposal individually to get per-module failure reasons
        verifier = orch.verifier
        for m in ALL_MODULES:
            module_proposals = proposals_by_module.get(m, [])
            for p in module_proposals:
                if not is_executable(p):
                    failure_rows.append({
                        "task_id": task_id,
                        "module": m,
                        "proposal_type": p.proposal_type,
                        "failure_stage": "not_executable",
                        "detail": "metadata_only_proposal",
                    })
                    continue

                stats[m].proposals_reached_verifier += 1
                outcome = verifier.verify(p, train_pairs, test_inputs, test_outputs)

                if not outcome.train_consistent:
                    stats[m].failed_train_consistency += 1
                    failure_rows.append({
                        "task_id": task_id,
                        "module": m,
                        "proposal_type": p.proposal_type,
                        "failure_stage": "train_inconsistent",
                        "detail": outcome.rejection_reason or "",
                    })
                elif not outcome.loo_passed:
                    stats[m].failed_loo += 1
                    failure_rows.append({
                        "task_id": task_id,
                        "module": m,
                        "proposal_type": p.proposal_type,
                        "failure_stage": "loo_failed",
                        "detail": outcome.rejection_reason or "",
                    })
                elif not outcome.proof_obligations_passed:
                    stats[m].failed_proof_obligations += 1
                    failure_rows.append({
                        "task_id": task_id,
                        "module": m,
                        "proposal_type": p.proposal_type,
                        "failure_stage": "proof_obligations_failed",
                        "detail": outcome.rejection_reason or "",
                    })
                elif not outcome.falsification_passed:
                    stats[m].failed_falsification += 1
                    failure_rows.append({
                        "task_id": task_id,
                        "module": m,
                        "proposal_type": p.proposal_type,
                        "failure_stage": "falsification_failed",
                        "detail": outcome.rejection_reason or "",
                    })
                elif outcome.accepted:
                    stats[m].certificates_emitted += 1

        if v2_solved and trace.selected_proposal:
            winning_module = trace.selected_proposal.module_name
            if winning_module in stats:
                stats[winning_module].solved += 1
                if is_new:
                    stats[winning_module].new_solves += 1

        if (i + 1) % 10 == 0:
            solved_so_far = sum(s.solved for s in stats.values())
            print(f"  [{i+1}/{n_tasks}] {solved_so_far} solved")

    return stats, failure_rows


def write_outputs(
    stats: Dict[str, ModuleStats],
    failure_rows: List[Dict[str, Any]],
    output_dir: str,
) -> None:
    os.makedirs(output_dir, exist_ok=True)

    # CSV
    csv_path = os.path.join(output_dir, "module_contribution_audit.csv")
    fieldnames = [
        "module", "triggered", "not_triggered",
        "proposals_total", "proposals_executable", "proposals_metadata_only",
        "proposals_reached_verifier",
        "failed_train_consistency", "failed_loo",
        "failed_proof_obligations", "failed_falsification",
        "certificates_emitted", "solved", "new_solves",
    ]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for m in ALL_MODULES:
            s = stats[m]
            writer.writerow({
                "module": s.module,
                "triggered": s.triggered,
                "not_triggered": s.not_triggered,
                "proposals_total": s.proposals_total,
                "proposals_executable": s.proposals_executable,
                "proposals_metadata_only": s.proposals_metadata_only,
                "proposals_reached_verifier": s.proposals_reached_verifier,
                "failed_train_consistency": s.failed_train_consistency,
                "failed_loo": s.failed_loo,
                "failed_proof_obligations": s.failed_proof_obligations,
                "failed_falsification": s.failed_falsification,
                "certificates_emitted": s.certificates_emitted,
                "solved": s.solved,
                "new_solves": s.new_solves,
            })

    # Failure reasons CSV
    fail_path = os.path.join(output_dir, "module_failure_reasons.csv")
    if failure_rows:
        with open(fail_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=failure_rows[0].keys())
            writer.writeheader()
            writer.writerows(failure_rows)

    # Markdown summary
    md_path = os.path.join(output_dir, "module_contribution_audit.md")
    lines = [
        "# Full V2 Module Contribution Audit\n\n",
        f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n",
        "## Per-Module Summary\n\n",
        "| Module | Triggered | Proposals | Executable | Verifier | Train-Fail | LOO-Fail | Proof-Fail | Falsif-Fail | Certs | Solved | New |\n",
        "|--------|-----------|-----------|------------|----------|------------|----------|------------|-------------|-------|--------|-----|\n",
    ]
    for m in ALL_MODULES:
        s = stats[m]
        lines.append(
            f"| {s.module} | {s.triggered} | {s.proposals_total} | "
            f"{s.proposals_executable} | {s.proposals_reached_verifier} | "
            f"{s.failed_train_consistency} | {s.failed_loo} | "
            f"{s.failed_proof_obligations} | {s.failed_falsification} | "
            f"{s.certificates_emitted} | {s.solved} | {s.new_solves} |\n"
        )

    lines.append("\n## Module Disposition Categories\n\n")
    for m in ALL_MODULES:
        s = stats[m]
        lines.append(f"### {s.module}\n\n")
        if s.not_triggered == s.triggered + s.not_triggered and s.triggered == 0:
            lines.append("- **Status**: NEVER TRIGGERED\n")
        elif s.proposals_total == 0:
            lines.append(f"- **Status**: TRIGGERED ({s.triggered}x) but produced NO proposals\n")
        elif s.proposals_executable == 0:
            lines.append(f"- **Status**: TRIGGERED ({s.triggered}x), produced {s.proposals_total} proposals, ALL metadata-only (no executable)\n")
        elif s.solved == 0:
            lines.append(f"- **Status**: TRIGGERED ({s.triggered}x), produced {s.proposals_executable} executable proposals, NONE accepted\n")
            if s.failed_train_consistency > 0:
                lines.append(f"  - {s.failed_train_consistency} failed train consistency\n")
            if s.failed_loo > 0:
                lines.append(f"  - {s.failed_loo} failed LOO\n")
            if s.failed_proof_obligations > 0:
                lines.append(f"  - {s.failed_proof_obligations} failed proof obligations\n")
            if s.failed_falsification > 0:
                lines.append(f"  - {s.failed_falsification} failed falsification\n")
        else:
            lines.append(f"- **Status**: CONTRIBUTING ({s.solved} solves, {s.new_solves} new)\n")
        lines.append("\n")

    # Failure breakdown by stage
    lines.append("## Failure Breakdown by Stage\n\n")
    stage_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in failure_rows:
        stage_counts[row["module"]][row["failure_stage"]] += 1

    for m in ALL_MODULES:
        if m in stage_counts:
            lines.append(f"### {m}\n\n")
            for stage, count in sorted(stage_counts[m].items(), key=lambda x: -x[1]):
                lines.append(f"- {stage}: {count}\n")
            lines.append("\n")

    with open(md_path, "w") as f:
        f.writelines(lines)

    print(f"\nOutputs written to {output_dir}/")
    print(f"  module_contribution_audit.csv")
    print(f"  module_contribution_audit.md")
    print(f"  module_failure_reasons.csv")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=OUTPUT_DIR)
    args = parser.parse_args()
    output_dir = args.output_dir

    print("=" * 60)
    print("  Full V2 Module Contribution Audit")
    print("=" * 60)

    os.makedirs(output_dir, exist_ok=True)

    print("\nLoading ARC tasks...")
    arc_task_list = load_arc_tasks(ARC_ROOT)
    tasks = {t.task_id: t for t in arc_task_list}
    print(f"  Loaded {len(tasks)} tasks")

    print("\nLoading v1 results...")
    v1_results = load_v1_results()
    print(f"  Loaded {len(v1_results)} v1 results")

    focused_ids = get_focused_task_ids(v1_results)
    print(f"\n  Focused subset: {len(focused_ids)} tasks")

    print("\nRunning audit...")
    stats, failure_rows = run_audit(tasks, focused_ids, v1_results, output_dir)

    write_outputs(stats, failure_rows, output_dir)

    print("\n" + "=" * 60)
    print("  AUDIT COMPLETE")
    print("=" * 60)
    for m in ALL_MODULES:
        s = stats[m]
        print(f"  {m}: triggered={s.triggered} proposals={s.proposals_total} "
              f"executable={s.proposals_executable} solved={s.solved} new={s.new_solves}")
    print("=" * 60)


if __name__ == "__main__":
    main()
