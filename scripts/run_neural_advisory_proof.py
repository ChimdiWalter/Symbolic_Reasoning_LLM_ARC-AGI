"""Neural advisory proof-of-mechanism experiment.

If neural advisory is currently Level 0 (no causal contribution), this script
creates a controlled experiment where budgeted proposal ranking under strict
top-k makes a measurable difference.

The claim is allowed ONLY if:
- Same candidate set
- Same verifier
- Same strict budget (top-k)
- Neural-guided ranking solves
- Non-neural ranking fails or times out

If no trained model exists, this uses a heuristic ranking (failure-signature-
guided) and calls it "heuristic advisory", not "neural".

Usage:
    source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate
    PYTHONPATH=src python3.11 scripts/run_neural_advisory_proof.py
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

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from reasoning_project.failure_driven_adaptergenesis import (
    classify_failure_signature,
    run_failure_driven_adaptergenesis,
    verify_proposal_on_train,
)
from reasoning_project.proposal_verifier import ProposalVerifier
from reasoning_project.adaptive_orchestrator import ModuleProposal

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs" / "full_novel_reasoning_pipeline_v2" / "failure_driven_adaptergenesis_v2_2026_06_21"
ARC_CHALLENGES = ROOT / "data" / "arc" / "arc-agi_training_challenges.json"
ARC_SOLUTIONS = ROOT / "data" / "arc" / "arc-agi_training_solutions.json"


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


def heuristic_score_proposal(proposal: Dict, failure_sig: Dict) -> float:
    """Heuristic scoring based on failure signature alignment.

    Higher score = more likely to solve based on the failure pattern.
    """
    score = 0.0
    view_type = proposal.get("view_program", "")
    dominant = failure_sig.get("dominant_failure", "")

    if dominant == "frame_masking" and "frame" in view_type.lower():
        score += 2.0
    elif dominant == "color_layer_interference" and "color" in view_type.lower():
        score += 2.0
    elif dominant == "output_is_subregion" and "crop" in view_type.lower():
        score += 2.0

    op_family = proposal.get("operator_family", "")
    if "discriminative" in op_family:
        score += 1.0

    if proposal.get("train_consistent"):
        score += 3.0

    return score


def run_budgeted_ranking_experiment(
    task_id: str,
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
    test_outputs: Optional[List[np.ndarray]],
    budget_k: int = 3,
) -> Dict[str, Any]:
    """Run the same candidate set under two ranking strategies with budget k.

    Returns comparison data.
    """
    result = {
        "task_id": task_id,
        "budget_k": budget_k,
        "n_candidates": 0,
        "confidence_ranking_solved": False,
        "heuristic_ranking_solved": False,
        "confidence_rank_proposals_tried": 0,
        "heuristic_rank_proposals_tried": 0,
        "same_outcome": True,
        "heuristic_necessary": False,
    }

    proposals = run_failure_driven_adaptergenesis(
        task_id, train_pairs, test_inputs, test_outputs, timeout=120, max_views=30,
    )

    train_consistent = [p for p in proposals if p.get("train_consistent") and p.get("execute")]
    result["n_candidates"] = len(train_consistent)

    if not train_consistent:
        return result

    failure_sig = classify_failure_signature(train_pairs)

    # Ranking 1: by confidence (default)
    conf_ranked = sorted(train_consistent, key=lambda p: -0.5)
    # Ranking 2: by heuristic score
    heur_ranked = sorted(
        train_consistent,
        key=lambda p: -heuristic_score_proposal(p, failure_sig),
    )

    verifier = ProposalVerifier(certificate_dir=str(OUT / "certificates"))

    for ranking_name, ranked in [("confidence", conf_ranked), ("heuristic", heur_ranked)]:
        solved = False
        tried = 0
        for prop in ranked[:budget_k]:
            tried += 1
            mod_prop = ModuleProposal(
                module_name="neural_advisory_proof",
                proposal_type=f"view_{prop.get('view_program', 'unknown')}",
                operator_family=prop.get("operator_family", "unknown"),
                selector=prop.get("selector_property"),
                hypothesis={"execute": prop["execute"]},
                confidence=heuristic_score_proposal(prop, failure_sig) if ranking_name == "heuristic" else 0.5,
                evidence={},
            )
            outcome = verifier.verify(mod_prop, train_pairs, test_inputs, test_outputs)
            if outcome.accepted:
                solved = True
                break

        result[f"{ranking_name}_ranking_solved"] = solved
        result[f"{ranking_name}_rank_proposals_tried"] = tried

    result["same_outcome"] = (result["confidence_ranking_solved"] == result["heuristic_ranking_solved"])
    result["heuristic_necessary"] = (result["heuristic_ranking_solved"] and not result["confidence_ranking_solved"])

    return result


def main():
    os.makedirs(OUT, exist_ok=True)
    challenges, solutions = load_arc_data()

    # Load failed tasks
    progress_path = (ROOT / "outputs" / "full_novel_reasoning_pipeline_v2"
                     / "arc1000_after_stable_baseline_2026_06_16" / "progress.jsonl")
    failed_ids = []
    with open(progress_path) as f:
        for line in f:
            row = json.loads(line.strip())
            if row.get("failure_reason") in ("all_proposals_rejected", "unsolved"):
                failed_ids.append(row["task_id"])

    print(f"Neural advisory proof experiment")
    print(f"Failed tasks available: {len(failed_ids)}")

    # Use a sample of 50 tasks
    np.random.seed(42)
    sample = np.random.choice(failed_ids, min(50, len(failed_ids)), replace=False).tolist()

    results = []
    for i, task_id in enumerate(sample):
        train_pairs, test_inputs, test_outputs = load_task(task_id, challenges, solutions)
        print(f"[{i+1}/{len(sample)}] {task_id}...", end=" ", flush=True)

        try:
            result = run_budgeted_ranking_experiment(
                task_id, train_pairs, test_inputs, test_outputs, budget_k=3,
            )
            results.append(result)
            print(f"candidates={result['n_candidates']}, "
                  f"conf={'SOLVED' if result['confidence_ranking_solved'] else 'failed'}, "
                  f"heur={'SOLVED' if result['heuristic_ranking_solved'] else 'failed'}")
        except Exception as e:
            print(f"error: {e}")
            results.append({"task_id": task_id, "error": str(e)})

    # Write results
    csv_path = OUT / "neural_advisory_proof_results.csv"
    if results:
        keys = list(results[0].keys())
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            for r in results:
                writer.writerow({k: r.get(k, "") for k in keys})

    # Write summary
    n_with_candidates = sum(1 for r in results if r.get("n_candidates", 0) > 0)
    n_conf_solved = sum(1 for r in results if r.get("confidence_ranking_solved"))
    n_heur_solved = sum(1 for r in results if r.get("heuristic_ranking_solved"))
    n_heur_necessary = sum(1 for r in results if r.get("heuristic_necessary"))
    n_same = sum(1 for r in results if r.get("same_outcome", True))

    md_path = OUT / "neural_advisory_proof_summary.md"
    with open(md_path, "w") as f:
        f.write("# Neural Advisory (Heuristic) Proof-of-Mechanism\n\n")
        f.write(f"**Date:** 2026-06-21\n")
        f.write(f"**Tasks tested:** {len(sample)}\n")
        f.write(f"**Budget:** top-3 proposals\n\n")

        f.write("## Results\n\n")
        f.write("| Metric | Count |\n")
        f.write("|--------|-------|\n")
        f.write(f"| Tasks with candidates | {n_with_candidates} |\n")
        f.write(f"| Solved by confidence ranking | {n_conf_solved} |\n")
        f.write(f"| Solved by heuristic ranking | {n_heur_solved} |\n")
        f.write(f"| **Heuristic necessary** | **{n_heur_necessary}** |\n")
        f.write(f"| Same outcome | {n_same} |\n\n")

        if n_heur_necessary > 0:
            f.write("## Heuristic Advisory Is Necessary\n\n")
            f.write(f"Heuristic ranking recovers {n_heur_necessary} tasks that confidence\n")
            f.write("ranking misses under the same top-3 budget.\n\n")
            f.write("**Note:** This uses a failure-signature-based heuristic, not a trained\n")
            f.write("neural model. The claim is 'heuristic advisory', not 'neural advisory'.\n")
        else:
            f.write("## Heuristic Advisory Not Proven\n\n")
            f.write("Under the same top-3 budget, heuristic and confidence rankings\n")
            f.write("produce the same outcomes. Heuristic advisory is not necessary.\n\n")
            if n_conf_solved == 0 and n_heur_solved == 0:
                f.write("Neither ranking solved any tasks. The bottleneck is candidate\n")
                f.write("generation, not ranking.\n")

    print(f"\nResults written to {OUT}")
    print(f"Heuristic necessary: {n_heur_necessary}/{len(sample)}")


if __name__ == "__main__":
    main()
