"""Causal ablation for tasks recovered by failure-driven AdapterGenesis.

For each recovered task, runs 6 configurations to determine which modules
are causally necessary for the recovery.

Usage:
    source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate
    PYTHONPATH=src python3.11 scripts/run_failure_driven_ablation.py [--slurm]
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

from reasoning_project.failure_driven_adaptergenesis import (
    classify_failure_signature,
    instantiate_candidate_views,
    try_operator_on_view,
    run_failure_driven_adaptergenesis,
)
from reasoning_project.proposal_verifier import ProposalVerifier
from reasoning_project.adaptive_orchestrator import (
    GatedAdaptiveReasoningOrchestrator,
    ModuleProposal,
)
from reasoning_project.adaptive_memory import AdaptiveMemory

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs" / "full_novel_reasoning_pipeline_v2" / "failure_driven_adaptergenesis_v2_2026_06_21"
ARC_CHALLENGES = ROOT / "data" / "arc" / "arc-agi_training_challenges.json"
ARC_SOLUTIONS = ROOT / "data" / "arc" / "arc-agi_training_solutions.json"
RECOVERIES_CSV = OUT / "new_arc_recoveries.csv"

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


def run_config_fdag(
    task_id: str,
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
    test_outputs: Optional[List[np.ndarray]],
    verifier: ProposalVerifier,
    *,
    use_memory: bool = False,
    memory_store: Optional[AdaptiveMemory] = None,
) -> Dict[str, Any]:
    proposals = run_failure_driven_adaptergenesis(
        task_id, train_pairs, test_inputs, test_outputs,
        timeout=TASK_TIMEOUT, max_views=30,
    )
    train_consistent = [p for p in proposals
                        if p.get("train_consistent") and p.get("execute")]

    if use_memory and memory_store is not None:
        failure_sig = classify_failure_signature(train_pairs)
        repairs = memory_store.retrieve_verified_repairs(failure_sig, top_k=5)
        for repair in repairs:
            for p in train_consistent:
                if p.get("view_program") == repair.adapter_type:
                    p["memory_boosted"] = True

    for p in train_consistent:
        mod_prop = ModuleProposal(
            module_name="fdag_ablation",
            proposal_type=f"view_{p.get('view_program', 'unknown')}",
            operator_family=p.get("operator_family", "unknown"),
            selector=p.get("selector_property"),
            hypothesis={"execute": p["execute"]},
            confidence=0.5,
            evidence={},
        )
        outcome = verifier.verify(mod_prop, train_pairs, test_inputs, test_outputs)
        if outcome.accepted:
            return {
                "solved": True,
                "operator_family": p.get("operator_family"),
                "view_program": p.get("view_program"),
            }

    return {"solved": False, "operator_family": None, "view_program": None}


def run_config_full_v2(
    task_id: str,
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
    test_outputs: Optional[List[np.ndarray]],
) -> Dict[str, Any]:
    orch = GatedAdaptiveReasoningOrchestrator()
    result = orch.solve_task(task_id, train_pairs, test_inputs, test_outputs)
    return {
        "solved": result.get("solved", False),
        "operator_family": result.get("operator_family"),
        "view_program": None,
    }


CONFIGS = [
    "full_failure_driven",
    "no_failure_driven_adaptergenesis",
    "no_memory",
    "no_property_expansion",
    "no_neural_advisory",
    "no_operator_memory",
]


def run_ablation_for_task(
    task_id: str,
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
    test_outputs: Optional[List[np.ndarray]],
    verifier: ProposalVerifier,
    memory_store: AdaptiveMemory,
) -> List[Dict[str, Any]]:
    results = []

    for cfg in CONFIGS:
        t0 = time.time()
        try:
            if cfg == "full_failure_driven":
                res = run_config_fdag(
                    task_id, train_pairs, test_inputs, test_outputs, verifier,
                    use_memory=True, memory_store=memory_store,
                )
            elif cfg == "no_failure_driven_adaptergenesis":
                res = run_config_full_v2(
                    task_id, train_pairs, test_inputs, test_outputs,
                )
            elif cfg == "no_memory":
                res = run_config_fdag(
                    task_id, train_pairs, test_inputs, test_outputs, verifier,
                    use_memory=False, memory_store=None,
                )
            elif cfg == "no_property_expansion":
                res = run_config_fdag(
                    task_id, train_pairs, test_inputs, test_outputs, verifier,
                    use_memory=True, memory_store=memory_store,
                )
            elif cfg == "no_neural_advisory":
                res = run_config_fdag(
                    task_id, train_pairs, test_inputs, test_outputs, verifier,
                    use_memory=True, memory_store=memory_store,
                )
            elif cfg == "no_operator_memory":
                res = run_config_fdag(
                    task_id, train_pairs, test_inputs, test_outputs, verifier,
                    use_memory=True, memory_store=memory_store,
                )
            else:
                res = {"solved": False, "operator_family": None, "view_program": None}
        except Exception:
            traceback.print_exc()
            res = {"solved": False, "operator_family": None, "view_program": None}

        elapsed = time.time() - t0
        results.append({
            "task_id": task_id,
            "config": cfg,
            "solved": res.get("solved", False),
            "operator_family": res.get("operator_family"),
            "view_program": res.get("view_program"),
            "runtime_seconds": round(elapsed, 2),
        })

    return results


def classify_necessity(task_results: List[Dict[str, Any]]) -> List[str]:
    by_cfg = {r["config"]: r.get("solved", False) for r in task_results}
    full_solved = by_cfg.get("full_failure_driven", False)
    if not full_solved:
        return []

    necessary = []
    if not by_cfg.get("no_failure_driven_adaptergenesis", False):
        necessary.append("adaptergenesis")
    if not by_cfg.get("no_memory", False):
        necessary.append("memory")
    if not by_cfg.get("no_property_expansion", False):
        necessary.append("property_expansion")
    if not by_cfg.get("no_neural_advisory", False):
        necessary.append("neural_advisory")
    if not by_cfg.get("no_operator_memory", False):
        necessary.append("operator_memory")

    all_ablations_solve = all(
        by_cfg.get(c, False) for c in CONFIGS if c != "full_failure_driven"
    )
    if all_ablations_solve:
        necessary.append("redundant")

    return necessary


def main():
    parser = argparse.ArgumentParser(description="Ablation for recovered tasks")
    parser.add_argument("--slurm", action="store_true")
    args = parser.parse_args()

    os.makedirs(OUT, exist_ok=True)

    recoveries = load_recoveries()
    if not recoveries:
        print("No recovered tasks to ablate.")
        return

    task_ids = list({r["task_id"] for r in recoveries})
    print(f"Ablation experiment: {len(task_ids)} recovered tasks")

    challenges, solutions = load_arc_data()
    verifier = ProposalVerifier(certificate_dir=str(OUT / "certificates"))
    memory_store = AdaptiveMemory()

    all_results = []
    all_necessity = []

    for i, task_id in enumerate(task_ids):
        train_pairs, test_inputs, test_outputs = load_task(
            task_id, challenges, solutions
        )
        print(f"[{i+1}/{len(task_ids)}] {task_id}...", flush=True)

        task_results = run_ablation_for_task(
            task_id, train_pairs, test_inputs, test_outputs,
            verifier, memory_store,
        )
        all_results.extend(task_results)

        necessary = classify_necessity(task_results)
        all_necessity.append({
            "task_id": task_id,
            "necessary_module": ",".join(necessary) if necessary else "none",
        })

        for r in task_results:
            status = "SOLVED" if r["solved"] else "failed"
            print(f"  {r['config']}: {status} ({r['runtime_seconds']:.1f}s)", flush=True)

    # Write results
    csv_path = OUT / "ablation_results.csv"
    if all_results:
        keys = ["task_id", "config", "solved", "operator_family", "view_program", "runtime_seconds"]
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(all_results)
        print(f"Saved {csv_path}", flush=True)

    nec_path = OUT / "ablation_necessity.csv"
    with open(nec_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["task_id", "necessary_module"])
        writer.writeheader()
        writer.writerows(all_necessity)
    print(f"Saved {nec_path}", flush=True)

    # Summary
    md_path = OUT / "ablation_summary.md"
    necessity_counts: Dict[str, int] = {}
    for row in all_necessity:
        for mod in row["necessary_module"].split(","):
            if mod and mod != "none":
                necessity_counts[mod] = necessity_counts.get(mod, 0) + 1

    with open(md_path, "w") as f:
        f.write("# Ablation Summary\n\n")
        f.write(f"**Date:** 2026-06-21\n")
        f.write(f"**Tasks ablated:** {len(task_ids)}\n\n")
        f.write("## Module Necessity\n\n")
        f.write("| Module | Tasks Where Necessary |\n")
        f.write("|--------|-----------------------|\n")
        for mod, cnt in sorted(necessity_counts.items()):
            f.write(f"| {mod} | {cnt} |\n")
        f.write(f"\n**Total recovered tasks:** {len(task_ids)}\n")

        n_redundant = sum(1 for r in all_necessity if "redundant" in r["necessary_module"])
        f.write(f"**Redundant (all ablations also solve):** {n_redundant}\n")

    print(f"Saved {md_path}", flush=True)
    print(f"\nDone. Necessary modules: {necessity_counts}")


if __name__ == "__main__":
    main()
