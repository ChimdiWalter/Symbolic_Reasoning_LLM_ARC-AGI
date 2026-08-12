"""Failure-driven AdapterGenesis replay on rejected/unsolved ARC-1000 tasks.

Runs a targeted evaluation of the failure-driven AdapterGenesis system,
stratified by failure signature categories, with 5 configurations per task.
Strict success criteria require passing every gate in the verification chain.

Usage:
    source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate
    PYTHONPATH=src python3.11 scripts/run_failure_driven_adaptergenesis_replay.py [--slurm]
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import signal
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reasoning_project.failure_driven_adaptergenesis import (
    classify_failure_signature,
    run_failure_driven_adaptergenesis,
)
from reasoning_project.proposal_verifier import ProposalVerifier
from reasoning_project.adaptive_orchestrator import (
    GatedAdaptiveReasoningOrchestrator,
    OrchestratorConfig,
    ModuleProposal,
)
from reasoning_project.adaptive_memory import AdaptiveMemory

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
ARC_CHALLENGES = ROOT / "data" / "arc" / "arc-agi_training_challenges.json"
ARC_SOLUTIONS = ROOT / "data" / "arc" / "arc-agi_training_solutions.json"
PROGRESS_FILE = (
    ROOT
    / "outputs"
    / "full_novel_reasoning_pipeline_v2"
    / "arc1000_after_stable_baseline_2026_06_16"
    / "progress.jsonl"
)
OUTPUT_DIR = (
    ROOT
    / "outputs"
    / "full_novel_reasoning_pipeline_v2"
    / "failure_driven_adaptergenesis_v2_2026_06_21"
)

TASK_TIMEOUT = 180  # seconds per task per config

# ---------------------------------------------------------------------------
# Graceful interrupt
# ---------------------------------------------------------------------------
_interrupted = False


def _sigint_handler(signum, frame):
    global _interrupted
    _interrupted = True
    print("\n[INTERRUPT] Caught signal, finishing current task then exiting...", flush=True)


signal.signal(signal.SIGINT, _sigint_handler)
signal.signal(signal.SIGTERM, _sigint_handler)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_arc_data() -> Tuple[dict, dict]:
    with open(ARC_CHALLENGES) as f:
        challenges = json.load(f)
    with open(ARC_SOLUTIONS) as f:
        solutions = json.load(f)
    return challenges, solutions


def load_task(
    task_id: str, challenges: dict, solutions: dict
) -> Tuple[List[Tuple[np.ndarray, np.ndarray]], List[np.ndarray], Optional[List[np.ndarray]]]:
    task = challenges[task_id]
    sol = solutions.get(task_id, [])

    train_pairs: List[Tuple[np.ndarray, np.ndarray]] = []
    for pair in task["train"]:
        inp = np.array(pair["input"], dtype=int)
        out = np.array(pair["output"], dtype=int)
        train_pairs.append((inp, out))

    test_inputs: List[np.ndarray] = []
    test_outputs: List[np.ndarray] = []
    for i, t in enumerate(task["test"]):
        test_inputs.append(np.array(t["input"], dtype=int))
        if i < len(sol):
            test_outputs.append(np.array(sol[i], dtype=int))
        elif "output" in t:
            test_outputs.append(np.array(t["output"], dtype=int))

    return train_pairs, test_inputs, test_outputs if test_outputs else None


def load_failed_task_ids() -> List[dict]:
    """Load tasks with failure_reason in {all_proposals_rejected, unsolved}."""
    rows = []
    with open(PROGRESS_FILE) as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            status = row.get("failure_reason", row.get("status", ""))
            if status in ("all_proposals_rejected", "unsolved"):
                rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# Stratified task selection
# ---------------------------------------------------------------------------
CATEGORY_QUOTAS = [
    ("frame_border", 25),
    ("color_layer", 25),
    ("crop_subregion", 20),
    ("symmetry_motif", 15),
    ("object_relation", 15),
]


def categorize_task(
    sig: Dict[str, Any],
) -> Optional[str]:
    """Assign a task to one failure-signature category (first match wins)."""
    if sig.get("has_frame") or sig.get("largest_object_touches_all_borders"):
        return "frame_border"
    if sig.get("multi_color_with_layer_structure"):
        return "color_layer"
    if sig.get("output_is_crop") or sig.get("output_is_subregion"):
        return "crop_subregion"
    if (
        sig.get("objects_repeat_in_tile")
        or sig.get("train_residual_is_mirrored")
    ):
        return "symmetry_motif"
    if (
        sig.get("object_role_depends_on_containment")
        or sig.get("has_line_separators")
        or sig.get("has_markers")
    ):
        return "object_relation"
    return None


def select_stratified_tasks(
    failed_rows: List[dict],
    challenges: dict,
    n_total: int = 100,
) -> List[Tuple[str, str, str]]:
    """Select up to n_total tasks stratified by failure signature.

    Returns list of (task_id, category, dominant_failure).
    """
    # Classify every failed task
    categorized: Dict[str, List[Tuple[str, str]]] = {
        cat: [] for cat, _ in CATEGORY_QUOTAS
    }
    uncategorized: List[Tuple[str, str]] = []

    for row in failed_rows:
        tid = row["task_id"]
        if tid not in challenges:
            continue
        task = challenges[tid]
        train_pairs = []
        for pair in task["train"]:
            inp = np.array(pair["input"], dtype=int)
            out = np.array(pair["output"], dtype=int)
            train_pairs.append((inp, out))

        sig = classify_failure_signature(train_pairs)
        cat = categorize_task(sig)
        dominant = sig.get("dominant_failure", "unknown")

        if cat is not None:
            categorized[cat].append((tid, dominant))
        else:
            uncategorized.append((tid, dominant))

    selected: List[Tuple[str, str, str]] = []
    shortfall = 0

    for cat, quota in CATEGORY_QUOTAS:
        pool = categorized[cat]
        np.random.shuffle(pool)
        take = min(quota, len(pool))
        for tid, dom in pool[:take]:
            selected.append((tid, cat, dom))
        shortfall += quota - take

    # Fill shortfall from the largest remaining pool
    if shortfall > 0:
        # Merge all unused tasks
        used_ids = {tid for tid, _, _ in selected}
        remaining: List[Tuple[str, str, str]] = []
        for cat, _ in CATEGORY_QUOTAS:
            for tid, dom in categorized[cat]:
                if tid not in used_ids:
                    remaining.append((tid, cat, dom))
        for tid, dom in uncategorized:
            if tid not in used_ids:
                remaining.append((tid, "uncategorized", dom))
        np.random.shuffle(remaining)
        for item in remaining[:shortfall]:
            selected.append(item)

    return selected[:n_total]


# ---------------------------------------------------------------------------
# Configuration runners
# ---------------------------------------------------------------------------
def run_static_only(
    task_id: str,
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
    test_outputs: Optional[List[np.ndarray]],
) -> Dict[str, Any]:
    """Config 1: static portfolio only."""
    config = OrchestratorConfig(
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
        timeout_per_task=TASK_TIMEOUT,
    )
    orch = GatedAdaptiveReasoningOrchestrator(config)
    trace = orch.solve_task(task_id, train_pairs, test_inputs, test_outputs)
    return {
        "solved": trace.final_status == "solved",
        "operator_family": getattr(trace.selected_proposal, "operator_family", None)
        if trace.selected_proposal
        else None,
        "view_program": None,
        "false_positive": trace.final_status == "false_positive_rejected",
    }


def run_full_v2_original(
    task_id: str,
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
    test_outputs: Optional[List[np.ndarray]],
) -> Dict[str, Any]:
    """Config 2: full v2 orchestrator (all modules)."""
    config = OrchestratorConfig(
        timeout_per_task=TASK_TIMEOUT,
    )
    orch = GatedAdaptiveReasoningOrchestrator(config)
    trace = orch.solve_task(task_id, train_pairs, test_inputs, test_outputs)
    return {
        "solved": trace.final_status == "solved",
        "operator_family": getattr(trace.selected_proposal, "operator_family", None)
        if trace.selected_proposal
        else None,
        "view_program": None,
        "false_positive": trace.final_status == "false_positive_rejected",
    }


def _run_fdag_proposals(
    task_id: str,
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
    test_outputs: Optional[List[np.ndarray]],
    verifier: ProposalVerifier,
    use_memory: bool = False,
    memory_store: Optional[AdaptiveMemory] = None,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Run failure-driven AdapterGenesis and submit proposals through verifier.

    Returns (result_summary, list_of_proposal_records).
    """
    proposals = run_failure_driven_adaptergenesis(
        task_id=task_id,
        train_pairs=train_pairs,
        test_inputs=test_inputs,
        test_outputs=test_outputs,
        timeout=TASK_TIMEOUT - 10,  # leave margin for verification
    )

    result = {
        "solved": False,
        "operator_family": None,
        "view_program": None,
        "false_positive": False,
    }
    proposal_records: List[Dict[str, Any]] = []

    gate_counts = {
        "total": len(proposals),
        "train_consistent": 0,
        "has_execute": 0,
        "submitted_to_verifier": 0,
        "loo_passed": 0,
        "proof_obligations_passed": 0,
        "falsification_passed": 0,
        "accepted": 0,
    }

    for pidx, prop in enumerate(proposals):
        record: Dict[str, Any] = {
            "task_id": task_id,
            "proposal_idx": pidx,
            "view_program": prop.get("view_program"),
            "view_signature": str(prop.get("view_signature", "")),
            "operator_family": prop.get("operator_family"),
            "selector_property": prop.get("selector_property"),
            "strategy": prop.get("strategy"),
            "train_consistent": prop.get("train_consistent", False),
            "train_pixel_error": prop.get("train_pixel_error", -1),
        }

        if not prop.get("train_consistent", False):
            record.update({
                "submitted": False,
                "accepted": False,
                "loo_passed": False,
                "proof_obligations_passed": False,
                "falsification_passed": False,
                "false_positive": False,
                "rejection_reason": "train_inconsistent_preflight",
                "certificate_path": None,
            })
            proposal_records.append(record)
            continue

        gate_counts["train_consistent"] += 1

        exe = prop.get("execute")
        if exe is None or not callable(exe):
            record.update({
                "submitted": False,
                "accepted": False,
                "loo_passed": False,
                "proof_obligations_passed": False,
                "falsification_passed": False,
                "false_positive": False,
                "rejection_reason": "no_executable",
                "certificate_path": None,
            })
            proposal_records.append(record)
            continue

        gate_counts["has_execute"] += 1

        # Wrap into a ModuleProposal for the verifier
        hypothesis = {
            "execute": exe,
            "source": "failure_driven_adaptergenesis",
            "view_program": prop.get("view_program"),
            "operator_family": prop.get("operator_family"),
        }
        if use_memory and memory_store is not None:
            hypothesis["memory_source"] = "adaptive_memory"

        mp = ModuleProposal(
            module_name="failure_driven_adaptergenesis",
            proposal_type=prop.get("strategy", "fd_adaptergenesis"),
            operator_family=prop.get("operator_family"),
            selector=prop.get("selector_property"),
            hypothesis=hypothesis,
            confidence=0.65,
            evidence={
                "view_program": prop.get("view_program"),
                "failure_signature": prop.get("failure_signature"),
            },
        )

        gate_counts["submitted_to_verifier"] += 1
        outcome = verifier.verify(mp, train_pairs, test_inputs, test_outputs)

        record.update({
            "submitted": True,
            "accepted": outcome.accepted,
            "loo_passed": outcome.loo_passed,
            "proof_obligations_passed": outcome.proof_obligations_passed,
            "falsification_passed": outcome.falsification_passed,
            "false_positive": outcome.false_positive,
            "rejection_reason": outcome.rejection_reason or "",
            "certificate_path": outcome.certificate_path or "",
            "test_confirmed": outcome.evidence.get("test_confirmed", False),
        })

        if outcome.loo_passed:
            gate_counts["loo_passed"] += 1
        if outcome.proof_obligations_passed:
            gate_counts["proof_obligations_passed"] += 1
        if outcome.falsification_passed:
            gate_counts["falsification_passed"] += 1
        if outcome.accepted:
            gate_counts["accepted"] += 1

        proposal_records.append(record)

        if outcome.accepted:
            result["solved"] = True
            result["operator_family"] = prop.get("operator_family")
            result["view_program"] = prop.get("view_program")
            result["false_positive"] = False
            break
        elif outcome.false_positive:
            result["false_positive"] = True

    result["gate_counts"] = gate_counts
    return result, proposal_records


def run_fdag(
    task_id: str,
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
    test_outputs: Optional[List[np.ndarray]],
    verifier: ProposalVerifier,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Config 3: failure-driven AdapterGenesis (standard)."""
    return _run_fdag_proposals(
        task_id, train_pairs, test_inputs, test_outputs, verifier,
        use_memory=False, memory_store=None,
    )


def run_fdag_no_memory(
    task_id: str,
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
    test_outputs: Optional[List[np.ndarray]],
    verifier: ProposalVerifier,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Config 4: failure-driven AdapterGenesis without memory retrieval."""
    return _run_fdag_proposals(
        task_id, train_pairs, test_inputs, test_outputs, verifier,
        use_memory=False, memory_store=None,
    )


def run_fdag_with_memory(
    task_id: str,
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
    test_outputs: Optional[List[np.ndarray]],
    verifier: ProposalVerifier,
    memory_store: AdaptiveMemory,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Config 5: failure-driven AdapterGenesis with memory seeded from earlier successes."""
    return _run_fdag_proposals(
        task_id, train_pairs, test_inputs, test_outputs, verifier,
        use_memory=True, memory_store=memory_store,
    )


# ---------------------------------------------------------------------------
# Strict success criteria
# ---------------------------------------------------------------------------
def is_new_recovery(
    static_result: Dict[str, Any],
    full_v2_result: Dict[str, Any],
    fdag_result: Dict[str, Any],
    fdag_proposals: List[Dict[str, Any]],
) -> bool:
    """Check if a task meets the strict new-recovery criteria."""
    # static_only must fail
    if static_result.get("solved"):
        return False
    # full_v2_original must fail or match original failure
    if full_v2_result.get("solved"):
        return False
    # fdag must have accepted a proposal
    if not fdag_result.get("solved"):
        return False
    if fdag_result.get("false_positive"):
        return False

    # Check the accepted proposal passed all gates
    for p in fdag_proposals:
        if p.get("accepted"):
            if not p.get("loo_passed"):
                return False
            if not p.get("proof_obligations_passed"):
                return False
            if not (p.get("falsification_passed") or p.get("test_confirmed")):
                return False
            if p.get("false_positive"):
                return False
            if not p.get("certificate_path"):
                return False
            return True

    return False


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------
def write_selected_tasks_csv(
    tasks: List[Tuple[str, str, str]], out_dir: Path
) -> None:
    path = out_dir / "selected_replay_tasks.csv"
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["task_id", "category", "failure_signature_dominant"])
        for tid, cat, dom in tasks:
            writer.writerow([tid, cat, dom])
    print(f"  Saved selected tasks to {path}", flush=True)


def write_results_csv(
    results: List[Dict[str, Any]], out_dir: Path
) -> None:
    path = out_dir / "failure_driven_replay_results.csv"
    fieldnames = [
        "task_id", "config", "solved", "operator_family", "view_program",
        "false_positive", "runtime_seconds",
    ]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)
    print(f"  Saved results to {path}", flush=True)


def write_proposals_jsonl(
    proposals: List[Dict[str, Any]], out_dir: Path
) -> None:
    path = out_dir / "proposals.jsonl"
    with open(path, "w") as f:
        for p in proposals:
            # Ensure JSON serializable
            record = {}
            for k, v in p.items():
                if callable(v):
                    record[k] = "<callable>"
                elif isinstance(v, np.ndarray):
                    record[k] = v.tolist()
                else:
                    try:
                        json.dumps(v)
                        record[k] = v
                    except (TypeError, ValueError):
                        record[k] = str(v)
            f.write(json.dumps(record) + "\n")
    print(f"  Saved {len(proposals)} proposal records to {path}", flush=True)


def write_new_recoveries_csv(
    recoveries: List[Dict[str, Any]], out_dir: Path
) -> None:
    path = out_dir / "new_arc_recoveries.csv"
    fieldnames = [
        "task_id", "category", "operator_family", "view_program",
        "certificate_path", "config",
    ]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(recoveries)
    print(f"  Saved {len(recoveries)} new recoveries to {path}", flush=True)


def write_proposal_rejection_breakdown(
    breakdown: List[Dict[str, Any]], out_dir: Path
) -> None:
    path = out_dir / "proposal_rejection_breakdown.csv"
    fieldnames = [
        "task_id", "config", "total", "train_consistent", "has_execute",
        "submitted_to_verifier", "loo_passed", "proof_obligations_passed",
        "falsification_passed", "accepted",
    ]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(breakdown)
    print(f"  Saved rejection breakdown to {path}", flush=True)


def write_summary_md(
    results: List[Dict[str, Any]],
    recoveries: List[Dict[str, Any]],
    selected_tasks: List[Tuple[str, str, str]],
    out_dir: Path,
    elapsed_total: float,
) -> None:
    path = out_dir / "failure_driven_replay_summary.md"

    configs = ["static_only", "full_v2_original", "failure_driven_adaptergenesis",
               "failure_driven_adaptergenesis_no_memory",
               "failure_driven_adaptergenesis_with_memory"]

    # Category counts
    cat_counts: Dict[str, int] = {}
    for _, cat, _ in selected_tasks:
        cat_counts[cat] = cat_counts.get(cat, 0) + 1

    lines = [
        "# Failure-Driven AdapterGenesis Replay Summary",
        "",
        f"**Date**: 2026-06-21",
        f"**Total tasks evaluated**: {len(selected_tasks)}",
        f"**Total runtime**: {elapsed_total:.1f}s ({elapsed_total/3600:.1f}h)",
        "",
        "## Task Selection by Category",
        "",
        "| Category | Count |",
        "| --- | --- |",
    ]
    for cat, count in sorted(cat_counts.items()):
        lines.append(f"| {cat} | {count} |")

    lines.extend(["", "## Pass Rates by Configuration", "",
                   "| Config | Solved | Pass Rate |",
                   "| --- | --- | --- |"])
    for cfg in configs:
        cfg_results = [r for r in results if r.get("config") == cfg]
        solved = sum(1 for r in cfg_results if r.get("solved"))
        total = len(cfg_results)
        rate = f"{100*solved/total:.1f}%" if total > 0 else "N/A"
        lines.append(f"| {cfg} | {solved}/{total} | {rate} |")

    lines.extend(["", f"## New Recoveries: {len(recoveries)}", ""])
    if recoveries:
        lines.extend([
            "| Task ID | Category | Operator Family | View Program | Config |",
            "| --- | --- | --- | --- | --- |",
        ])
        for rec in recoveries:
            lines.append(
                f"| {rec['task_id']} | {rec.get('category', '')} "
                f"| {rec.get('operator_family', '')} "
                f"| {rec.get('view_program', '')} "
                f"| {rec.get('config', '')} |"
            )
    else:
        lines.append("No new recoveries met the strict criteria.")

    lines.append("")

    with open(path, "w") as f:
        f.write("\n".join(lines))
    print(f"  Saved summary to {path}", flush=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Failure-driven AdapterGenesis replay evaluation"
    )
    parser.add_argument(
        "--slurm", action="store_true",
        help="Running under SLURM (enables extra flushing)",
    )
    parser.add_argument(
        "--n-tasks", type=int, default=100,
        help="Number of tasks to evaluate (default: 100)",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed for task selection",
    )
    args = parser.parse_args()

    np.random.seed(args.seed)

    print("=" * 70, flush=True)
    print("  Failure-Driven AdapterGenesis Replay Evaluation", flush=True)
    print("=" * 70, flush=True)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    cert_dir = OUTPUT_DIR / "certificates"
    os.makedirs(cert_dir, exist_ok=True)

    # Load data
    print("\nLoading ARC data...", flush=True)
    challenges, solutions = load_arc_data()
    print(f"  {len(challenges)} challenges loaded", flush=True)

    # Load failed tasks
    print("Loading failed task IDs from progress file...", flush=True)
    failed_rows = load_failed_task_ids()
    print(f"  {len(failed_rows)} failed tasks found", flush=True)

    # Select stratified tasks
    print(f"Selecting {args.n_tasks} stratified tasks...", flush=True)
    selected_tasks = select_stratified_tasks(
        failed_rows, challenges, n_total=args.n_tasks
    )
    print(f"  Selected {len(selected_tasks)} tasks", flush=True)
    write_selected_tasks_csv(selected_tasks, OUTPUT_DIR)

    # Print category breakdown
    cat_counts: Dict[str, int] = {}
    for _, cat, _ in selected_tasks:
        cat_counts[cat] = cat_counts.get(cat, 0) + 1
    for cat, cnt in sorted(cat_counts.items()):
        print(f"    {cat}: {cnt}", flush=True)

    # Set up verifier and memory
    verifier = ProposalVerifier(
        certificate_dir=str(cert_dir),
    )
    memory_store = AdaptiveMemory()

    # Results accumulators
    all_results: List[Dict[str, Any]] = []
    all_proposals: List[Dict[str, Any]] = []
    all_recoveries: List[Dict[str, Any]] = []
    all_breakdowns: List[Dict[str, Any]] = []

    t_total_start = time.time()
    configs = [
        "static_only",
        "full_v2_original",
        "failure_driven_adaptergenesis",
        "failure_driven_adaptergenesis_no_memory",
        "failure_driven_adaptergenesis_with_memory",
    ]

    print(f"\n{'='*70}", flush=True)
    print(f"  Running {len(selected_tasks)} tasks x {len(configs)} configs", flush=True)
    print(f"  Timeout per task-config: {TASK_TIMEOUT}s", flush=True)
    print(f"{'='*70}\n", flush=True)

    for task_idx, (task_id, category, dominant_failure) in enumerate(selected_tasks):
        if _interrupted:
            print("[INTERRUPT] Stopping task loop.", flush=True)
            break

        train_pairs, test_inputs, test_outputs = load_task(
            task_id, challenges, solutions
        )

        task_results: Dict[str, Dict[str, Any]] = {}
        task_fdag_proposals: List[Dict[str, Any]] = []
        task_breakdowns: List[Dict[str, Any]] = []

        for cfg in configs:
            if _interrupted:
                break

            t0 = time.time()
            result_row: Dict[str, Any] = {
                "task_id": task_id,
                "config": cfg,
                "solved": False,
                "operator_family": None,
                "view_program": None,
                "false_positive": False,
                "runtime_seconds": 0.0,
            }

            try:
                if cfg == "static_only":
                    res = run_static_only(
                        task_id, train_pairs, test_inputs, test_outputs
                    )
                    result_row.update(res)

                elif cfg == "full_v2_original":
                    res = run_full_v2_original(
                        task_id, train_pairs, test_inputs, test_outputs
                    )
                    result_row.update(res)

                elif cfg == "failure_driven_adaptergenesis":
                    res, proposals = run_fdag(
                        task_id, train_pairs, test_inputs, test_outputs, verifier
                    )
                    result_row.update(res)
                    for p in proposals:
                        p["config"] = cfg
                    task_fdag_proposals.extend(proposals)
                    gate_counts = res.get("gate_counts", {})
                    task_breakdowns.append({"task_id": task_id, "config": cfg, **gate_counts})

                elif cfg == "failure_driven_adaptergenesis_no_memory":
                    res, proposals = run_fdag_no_memory(
                        task_id, train_pairs, test_inputs, test_outputs, verifier
                    )
                    result_row.update(res)
                    for p in proposals:
                        p["config"] = cfg
                    task_fdag_proposals.extend(proposals)
                    gate_counts = res.get("gate_counts", {})
                    task_breakdowns.append({"task_id": task_id, "config": cfg, **gate_counts})

                elif cfg == "failure_driven_adaptergenesis_with_memory":
                    res, proposals = run_fdag_with_memory(
                        task_id, train_pairs, test_inputs, test_outputs,
                        verifier, memory_store,
                    )
                    result_row.update(res)
                    for p in proposals:
                        p["config"] = cfg
                    task_fdag_proposals.extend(proposals)
                    gate_counts = res.get("gate_counts", {})
                    task_breakdowns.append({"task_id": task_id, "config": cfg, **gate_counts})

            except Exception as exc:
                result_row["solved"] = False
                result_row["operator_family"] = None
                result_row["view_program"] = None
                result_row["false_positive"] = False
                if not args.slurm:
                    traceback.print_exc()

            elapsed = time.time() - t0
            result_row["runtime_seconds"] = round(elapsed, 2)
            # Remove non-serializable gate_counts from the CSV row
            result_row.pop("gate_counts", None)
            task_results[cfg] = result_row
            all_results.append(result_row)

            status = "SOLVED" if result_row["solved"] else "failed"
            print(
                f"[{task_idx+1}/{len(selected_tasks)}] {task_id}: "
                f"{cfg} {status} ({elapsed:.1f}s)",
                flush=True,
            )

        # Check new recovery for each fdag config
        static_res = task_results.get("static_only", {"solved": False})
        full_v2_res = task_results.get("full_v2_original", {"solved": False})

        for fdag_cfg in [
            "failure_driven_adaptergenesis",
            "failure_driven_adaptergenesis_no_memory",
            "failure_driven_adaptergenesis_with_memory",
        ]:
            fdag_res = task_results.get(fdag_cfg, {"solved": False})
            fdag_props = [p for p in task_fdag_proposals if p.get("config") == fdag_cfg]
            if is_new_recovery(static_res, full_v2_res, fdag_res, fdag_props):
                cert = ""
                for p in fdag_props:
                    if p.get("accepted") and p.get("certificate_path"):
                        cert = p["certificate_path"]
                        break
                all_recoveries.append({
                    "task_id": task_id,
                    "category": category,
                    "operator_family": fdag_res.get("operator_family"),
                    "view_program": fdag_res.get("view_program"),
                    "certificate_path": cert,
                    "config": fdag_cfg,
                })
                # Seed memory from this recovery for subsequent tasks
                # (affects failure_driven_adaptergenesis_with_memory)
                try:
                    memory_store.store_verified_package(
                        task_id=task_id,
                        adapter=type("Adapter", (), {
                            "adapter_type": str(fdag_res.get("view_program", "unknown")),
                            "signature": lambda self: {"type": self.adapter_type},
                        })(),
                        operator_family=str(fdag_res.get("operator_family", "unknown")),
                        selector=str(fdag_res.get("view_program", "")),
                        certificate_path=cert,
                        train_pairs=train_pairs,
                    )
                except Exception:
                    pass

        all_proposals.extend(task_fdag_proposals)
        all_breakdowns.extend(task_breakdowns)

    elapsed_total = time.time() - t_total_start

    # Write outputs
    print(f"\n{'='*70}", flush=True)
    print("  Writing output files...", flush=True)
    print(f"{'='*70}", flush=True)

    write_results_csv(all_results, OUTPUT_DIR)
    write_proposals_jsonl(all_proposals, OUTPUT_DIR)
    write_new_recoveries_csv(all_recoveries, OUTPUT_DIR)
    write_proposal_rejection_breakdown(all_breakdowns, OUTPUT_DIR)
    write_summary_md(all_results, all_recoveries, selected_tasks, OUTPUT_DIR, elapsed_total)

    # Print summary
    print(f"\n{'='*70}", flush=True)
    print("  SUMMARY", flush=True)
    print(f"{'='*70}", flush=True)
    print(f"  Tasks evaluated: {len(selected_tasks)}", flush=True)
    print(f"  Total runtime: {elapsed_total:.1f}s ({elapsed_total/3600:.1f}h)", flush=True)
    print(f"  New recoveries (strict): {len(all_recoveries)}", flush=True)
    for cfg in configs:
        cfg_res = [r for r in all_results if r.get("config") == cfg]
        solved = sum(1 for r in cfg_res if r.get("solved"))
        total = len(cfg_res)
        print(f"    {cfg}: {solved}/{total} solved", flush=True)
    print(f"\n  Output directory: {OUTPUT_DIR}", flush=True)
    print("", flush=True)


if __name__ == "__main__":
    main()
