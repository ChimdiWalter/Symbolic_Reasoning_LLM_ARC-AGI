"""Operator ablation for tasks recovered by OperatorGenesis.

For each recovered task, runs configs with specific modules removed
to classify causal dependencies.

Usage:
    source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate
    PYTHONPATH=src python3.11 scripts/run_operator_genesis_ablation.py [--slurm]
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from reasoning_project.failure_driven_operator_genesis import (
    run_failure_driven_operator_genesis,
    submit_proposals_to_verifier,
)
from reasoning_project.operator_genesis import (
    synthesize_operators_from_train,
    _check_train_consistency,
)
from reasoning_project.proposal_verifier import ProposalVerifier
from reasoning_project.adaptive_orchestrator import ModuleProposal

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs" / "full_novel_reasoning_pipeline_v2" / "operator_genesis_v1_2026_06_21"
ARC_CHALLENGES = ROOT / "data" / "arc" / "arc-agi_training_challenges.json"
ARC_SOLUTIONS = ROOT / "data" / "arc" / "arc-agi_training_solutions.json"
RECOVERIES_CSV = OUT / "operator_genesis_new_recoveries.csv"

TASK_TIMEOUT = 180


def load_arc_data():
    with open(ARC_CHALLENGES) as f:
        challenges = json.load(f)
    with open(ARC_SOLUTIONS) as f:
        solutions = json.load(f)
    return challenges, solutions


def load_task(task_id, challenges, solutions):
    task = challenges[task_id]
    sol = solutions.get(task_id, [])
    train_pairs = [(np.array(p["input"], dtype=int), np.array(p["output"], dtype=int))
                   for p in task["train"]]
    test_inputs = [np.array(t["input"], dtype=int) for t in task["test"]]
    test_outputs = [np.array(sol[i], dtype=int) for i in range(len(sol))] if sol else None
    return train_pairs, test_inputs, test_outputs


def load_recoveries() -> List[Dict[str, str]]:
    if not RECOVERIES_CSV.exists():
        return []
    rows = []
    with open(RECOVERIES_CSV) as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


ABLATION_CONFIGS = [
    "full_view_plus_og",
    "no_view_program",
    "no_operator_genesis",
    "no_memory",
    "no_property_expansion",
    "no_neural_advisory",
]


def run_ablation_config(
    config: str,
    task_id: str,
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
    test_outputs: Optional[List[np.ndarray]],
    verifier: ProposalVerifier,
    proposals_log: str,
) -> Dict[str, Any]:
    """Run a single ablation config."""
    if config == "full_view_plus_og":
        proposals = run_failure_driven_operator_genesis(
            task_id, train_pairs, test_inputs, test_outputs,
            timeout=TASK_TIMEOUT, proposals_log_path=proposals_log,
        )
        results = submit_proposals_to_verifier(
            proposals, train_pairs, test_inputs, test_outputs, verifier,
        )
        for r in results:
            if r.get("accepted"):
                return {"solved": True, "operator_family": r.get("operator_family"),
                        "view_program": r.get("view_program")}
        return {"solved": False}

    elif config == "no_view_program":
        ops = synthesize_operators_from_train(train_pairs, max_candidates=100)
        tc = [op for op in ops if _check_train_consistency(op.execute, train_pairs)[0]]
        for op in tc:
            mod_prop = ModuleProposal(
                module_name="og_no_view",
                proposal_type="og_direct",
                operator_family=op.operator_family,
                selector=op.explanation,
                hypothesis={"execute": op.execute},
                confidence=0.5,
                evidence={},
            )
            outcome = verifier.verify(mod_prop, train_pairs, test_inputs, test_outputs)
            if outcome.accepted:
                return {"solved": True, "operator_family": op.operator_family}
        return {"solved": False}

    elif config == "no_operator_genesis":
        from reasoning_project.failure_driven_adaptergenesis import run_failure_driven_adaptergenesis
        proposals = run_failure_driven_adaptergenesis(
            task_id, train_pairs, test_inputs, test_outputs, timeout=TASK_TIMEOUT,
        )
        tc = [p for p in proposals if p.get("train_consistent") and p.get("execute")]
        for p in tc:
            mod_prop = ModuleProposal(
                module_name="no_og",
                proposal_type=f"view_{p.get('view_program', 'unknown')}",
                operator_family=p.get("operator_family", "unknown"),
                selector=p.get("selector_property"),
                hypothesis={"execute": p["execute"]},
                confidence=0.5,
                evidence={},
            )
            outcome = verifier.verify(mod_prop, train_pairs, test_inputs, test_outputs)
            if outcome.accepted:
                return {"solved": True, "operator_family": p.get("operator_family")}
        return {"solved": False}

    else:
        # no_memory, no_property_expansion, no_neural_advisory
        # Same as full for now (these aren't wired into OG yet)
        proposals = run_failure_driven_operator_genesis(
            task_id, train_pairs, test_inputs, test_outputs,
            timeout=TASK_TIMEOUT, proposals_log_path=proposals_log,
        )
        results = submit_proposals_to_verifier(
            proposals, train_pairs, test_inputs, test_outputs, verifier,
        )
        for r in results:
            if r.get("accepted"):
                return {"solved": True, "operator_family": r.get("operator_family"),
                        "view_program": r.get("view_program")}
        return {"solved": False}


def main():
    parser = argparse.ArgumentParser(description="OperatorGenesis ablation")
    parser.add_argument("--slurm", action="store_true")
    args = parser.parse_args()

    os.makedirs(OUT, exist_ok=True)

    recoveries = load_recoveries()
    if not recoveries:
        print("No recovered tasks to ablate.")
        return

    task_ids = list({r["task_id"] for r in recoveries})
    print(f"OperatorGenesis ablation: {len(task_ids)} recovered tasks")

    challenges, solutions = load_arc_data()
    verifier = ProposalVerifier(certificate_dir=str(OUT / "certificates"))
    proposals_log = str(OUT / "ablation_proposals.jsonl")

    all_results = []
    all_necessity = []

    for i, task_id in enumerate(task_ids):
        train_pairs, test_inputs, test_outputs = load_task(task_id, challenges, solutions)
        print(f"[{i+1}/{len(task_ids)}] {task_id}...", flush=True)

        task_results = {}
        for cfg in ABLATION_CONFIGS:
            t0 = time.time()
            try:
                res = run_ablation_config(
                    cfg, task_id, train_pairs, test_inputs, test_outputs,
                    verifier, proposals_log,
                )
            except Exception:
                if not args.slurm:
                    traceback.print_exc()
                res = {"solved": False}

            elapsed = time.time() - t0
            row = {"task_id": task_id, "config": cfg, "solved": res.get("solved", False),
                   "operator_family": res.get("operator_family"),
                   "view_program": res.get("view_program"),
                   "runtime_seconds": round(elapsed, 2)}
            all_results.append(row)
            task_results[cfg] = res.get("solved", False)
            status = "SOLVED" if row["solved"] else "failed"
            print(f"  {cfg}: {status} ({elapsed:.1f}s)", flush=True)

        # Classify necessity
        full_solved = task_results.get("full_view_plus_og", False)
        necessary = []
        if full_solved:
            if not task_results.get("no_view_program", False):
                necessary.append("view_program")
            if not task_results.get("no_operator_genesis", False):
                necessary.append("operator_genesis")
            if all(task_results.get(c, False) for c in ABLATION_CONFIGS if c != "full_view_plus_og"):
                necessary.append("redundant")
        all_necessity.append({
            "task_id": task_id,
            "necessary_module": ",".join(necessary) if necessary else "none",
        })

    # Write outputs
    csv_path = OUT / "operator_genesis_ablation.csv"
    keys = ["task_id", "config", "solved", "operator_family", "view_program", "runtime_seconds"]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_results)
    print(f"Saved {csv_path}", flush=True)

    md_path = OUT / "operator_genesis_ablation_summary.md"
    necessity_counts: Dict[str, int] = {}
    for row in all_necessity:
        for mod in row["necessary_module"].split(","):
            if mod and mod != "none":
                necessity_counts[mod] = necessity_counts.get(mod, 0) + 1

    with open(md_path, "w") as f:
        f.write("# OperatorGenesis Ablation Summary\n\n")
        f.write(f"**Date:** 2026-06-21\n")
        f.write(f"**Tasks ablated:** {len(task_ids)}\n\n")
        f.write("## Module Necessity\n\n")
        f.write("| Module | Tasks Where Necessary |\n")
        f.write("|--------|-----------------------|\n")
        for mod, cnt in sorted(necessity_counts.items()):
            f.write(f"| {mod} | {cnt} |\n")
        n_redundant = sum(1 for r in all_necessity if "redundant" in r["necessary_module"])
        f.write(f"\n**Total recovered:** {len(task_ids)}\n")
        f.write(f"**Redundant:** {n_redundant}\n")

    print(f"Saved {md_path}", flush=True)


if __name__ == "__main__":
    main()
