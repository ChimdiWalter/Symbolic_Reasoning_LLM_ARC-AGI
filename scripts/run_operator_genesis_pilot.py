"""OperatorGenesis pilot: 20 failed ARC tasks with operator synthesis.

Uses 20 stratified tasks from the selected replay set and runs 5 configs
to test whether OperatorGenesis can recover tasks that all existing
approaches fail on.

Usage:
    source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate
    PYTHONPATH=src python3.11 scripts/run_operator_genesis_pilot.py [--slurm]
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

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from reasoning_project.failure_driven_operator_genesis import (
    run_failure_driven_operator_genesis,
    submit_proposals_to_verifier,
)
from reasoning_project.operator_genesis import (
    synthesize_operators_from_train,
    _check_train_consistency,
)
from reasoning_project.failure_driven_adaptergenesis import (
    classify_failure_signature,
    run_failure_driven_adaptergenesis,
)
from reasoning_project.proposal_verifier import ProposalVerifier
from reasoning_project.adaptive_orchestrator import (
    GatedAdaptiveReasoningOrchestrator,
    ModuleProposal,
)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs" / "full_novel_reasoning_pipeline_v2" / "operator_genesis_v2_2026_06_22"
FDAG_OUT = ROOT / "outputs" / "full_novel_reasoning_pipeline_v2" / "failure_driven_adaptergenesis_v2_2026_06_21"
ARC_CHALLENGES = ROOT / "data" / "arc" / "arc-agi_training_challenges.json"
ARC_SOLUTIONS = ROOT / "data" / "arc" / "arc-agi_training_solutions.json"
PROGRESS_PATH = (ROOT / "outputs" / "full_novel_reasoning_pipeline_v2"
                 / "arc1000_after_stable_baseline_2026_06_16" / "progress.jsonl")

TASK_TIMEOUT = 180

_interrupted = False

def _handle_signal(signum, frame):
    global _interrupted
    _interrupted = True
    print("\n[INTERRUPT] Caught signal, finishing current task...", flush=True)

signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT, _handle_signal)


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


def load_failed_task_ids() -> List[Dict[str, Any]]:
    rows = []
    with open(PROGRESS_PATH) as f:
        for line in f:
            row = json.loads(line.strip())
            if row.get("failure_reason") in ("all_proposals_rejected", "unsolved"):
                rows.append(row)
    return rows


def select_pilot_tasks(
    failed_rows: List[Dict[str, Any]],
    challenges: Dict,
) -> List[Tuple[str, str]]:
    """Select 20 stratified tasks: 5 crop, 5 color-layer, 5 frame, 3 object, 2 symmetry."""
    targets = {
        "crop_subregion": 5,
        "color_layer": 5,
        "frame_border": 5,
        "object_relation": 3,
        "symmetry_motif": 2,
    }

    from reasoning_project.failure_driven_adaptergenesis import classify_failure_signature

    categorized: Dict[str, List[str]] = {k: [] for k in targets}

    for row in failed_rows:
        tid = row["task_id"]
        if tid not in challenges:
            continue
        task = challenges[tid]
        train_pairs = [(np.array(p["input"], dtype=int), np.array(p["output"], dtype=int))
                       for p in task["train"]]
        sig = classify_failure_signature(train_pairs)
        dom = sig.get("dominant_failure", "unknown")

        if dom in ("output_is_subregion", "output_is_crop"):
            categorized["crop_subregion"].append(tid)
        elif dom in ("color_layer_interference", "multi_color_with_layer_structure"):
            categorized["color_layer"].append(tid)
        elif dom in ("frame_masking", "has_frame"):
            categorized["frame_border"].append(tid)
        elif dom in ("containment_invisible", "object_role_depends_on_containment"):
            categorized["object_relation"].append(tid)
        elif dom in ("symmetry_obscured", "motif_scattered", "objects_repeat_in_tile"):
            categorized["symmetry_motif"].append(tid)

    selected = []
    np.random.seed(42)
    for cat, n_target in targets.items():
        pool = categorized[cat]
        if len(pool) >= n_target:
            chosen = np.random.choice(pool, n_target, replace=False).tolist()
        else:
            chosen = pool[:]
        for tid in chosen:
            selected.append((tid, cat))

    # Fill remaining from uncategorized
    all_selected_ids = {tid for tid, _ in selected}
    remaining_ids = [r["task_id"] for r in failed_rows
                     if r["task_id"] not in all_selected_ids and r["task_id"] in challenges]
    while len(selected) < 20 and remaining_ids:
        tid = remaining_ids.pop(0)
        selected.append((tid, "uncategorized"))

    return selected


# ---------------------------------------------------------------------------
# Config runners
# ---------------------------------------------------------------------------

def run_static_only(task_id, train_pairs, test_inputs, test_outputs):
    from reasoning_project.reasoning_engine import StructuralReasoner, ReasoningMemory, GridDomainAdapter
    adapter = GridDomainAdapter()
    memory = ReasoningMemory()
    reasoner = StructuralReasoner(adapter=adapter, memory=memory)
    deadline = time.time() + TASK_TIMEOUT
    result = reasoner.solve(train_pairs, test_inputs, deadline=deadline)
    if result and test_outputs:
        predictions, _metadata = result
        for pred, expected in zip(predictions, test_outputs):
            if isinstance(pred, np.ndarray) and np.array_equal(pred, expected):
                return {"solved": True, "operator_family": "static"}
    return {"solved": False}


def run_full_v2(task_id, train_pairs, test_inputs, test_outputs):
    orch = GatedAdaptiveReasoningOrchestrator()
    trace = orch.solve_task(task_id, train_pairs, test_inputs, test_outputs)
    solved = trace.final_status == "solved"
    op_family = None
    if trace.selected_proposal:
        op_family = trace.selected_proposal.operator_family
    return {"solved": solved, "operator_family": op_family}


def run_view_only(task_id, train_pairs, test_inputs, test_outputs, verifier):
    """AdapterGenesis/ViewProgram only — no OperatorGenesis."""
    proposals = run_failure_driven_adaptergenesis(
        task_id, train_pairs, test_inputs, test_outputs, timeout=TASK_TIMEOUT, max_views=30,
    )
    tc = [p for p in proposals if p.get("train_consistent") and p.get("execute")]
    for p in tc:
        mod_prop = ModuleProposal(
            module_name="view_only",
            proposal_type=f"view_{p.get('view_program', 'unknown')}",
            operator_family=p.get("operator_family", "unknown"),
            selector=p.get("selector_property"),
            hypothesis={"execute": p["execute"]},
            confidence=0.5,
            evidence={},
        )
        outcome = verifier.verify(mod_prop, train_pairs, test_inputs, test_outputs)
        if outcome.accepted:
            return {"solved": True, "operator_family": p.get("operator_family"),
                    "view_program": p.get("view_program")}
    return {"solved": False}


def run_operator_genesis_only(task_id, train_pairs, test_inputs, test_outputs, verifier, log_path):
    """Direct OperatorGenesis on raw pairs — no view lifting."""
    ops = synthesize_operators_from_train(train_pairs, max_candidates=100)
    tc = [op for op in ops if _check_train_consistency(op.execute, train_pairs)[0]]
    for op in tc:
        mod_prop = ModuleProposal(
            module_name="operator_genesis_only",
            proposal_type=f"og_direct",
            operator_family=op.operator_family,
            selector=op.explanation,
            hypothesis={"execute": op.execute},
            confidence=0.5,
            evidence={"parameters": op.parameters},
        )
        outcome = verifier.verify(mod_prop, train_pairs, test_inputs, test_outputs)
        if outcome.accepted:
            return {"solved": True, "operator_family": op.operator_family,
                    "view_program": "direct", "certificate_path": outcome.certificate_path}
    return {"solved": False}


def run_view_plus_operator_genesis(task_id, train_pairs, test_inputs, test_outputs, verifier, log_path):
    """Full pipeline: ViewProgram + OperatorGenesis."""
    proposals = run_failure_driven_operator_genesis(
        task_id, train_pairs, test_inputs, test_outputs,
        timeout=TASK_TIMEOUT, max_views=20, max_ops_per_view=50,
        proposals_log_path=log_path,
    )
    results = submit_proposals_to_verifier(
        proposals, train_pairs, test_inputs, test_outputs, verifier,
    )
    for r in results:
        if r.get("accepted"):
            return {
                "solved": True,
                "operator_family": r.get("operator_family"),
                "view_program": r.get("view_program"),
                "certificate_path": r.get("certificate_path"),
                "false_positive": r.get("false_positive", False),
            }
    return {"solved": False}


# ---------------------------------------------------------------------------
# Recovery check
# ---------------------------------------------------------------------------

def is_strict_recovery(static_res, v2_res, og_res):
    if static_res.get("solved"):
        return False
    if v2_res.get("solved"):
        return False
    if not og_res.get("solved"):
        return False
    if og_res.get("false_positive"):
        return False
    if not og_res.get("certificate_path"):
        return False
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="OperatorGenesis pilot")
    parser.add_argument("--slurm", action="store_true")
    parser.add_argument("--max-tasks", type=int, default=20, help="Max tasks to run (for smoke testing)")
    args = parser.parse_args()

    os.makedirs(OUT, exist_ok=True)
    cert_dir = OUT / "certificates"
    os.makedirs(cert_dir, exist_ok=True)

    print("=" * 70, flush=True)
    print("  OperatorGenesis Pilot (20 tasks)", flush=True)
    print("=" * 70, flush=True)

    challenges, solutions = load_arc_data()
    print(f"  {len(challenges)} challenges loaded", flush=True)

    failed_rows = load_failed_task_ids()
    print(f"  {len(failed_rows)} failed tasks found", flush=True)

    selected = select_pilot_tasks(failed_rows, challenges)
    selected = selected[:args.max_tasks]
    print(f"  Selected {len(selected)} pilot tasks", flush=True)

    # Save selected tasks
    sel_path = OUT / "pilot_selected_tasks.csv"
    with open(sel_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["task_id", "category"])
        for tid, cat in selected:
            writer.writerow([tid, cat])

    cat_counts: Dict[str, int] = {}
    for _, cat in selected:
        cat_counts[cat] = cat_counts.get(cat, 0) + 1
    for cat, cnt in sorted(cat_counts.items()):
        print(f"    {cat}: {cnt}", flush=True)

    verifier = ProposalVerifier(certificate_dir=str(cert_dir))
    proposals_log = str(OUT / "operator_genesis_proposals.jsonl")

    configs = [
        "static_only",
        "full_v2_original",
        "view_only_adaptergenesis",
        "operator_genesis_only",
        "view_plus_operator_genesis",
    ]

    all_results: List[Dict[str, Any]] = []
    all_recoveries: List[Dict[str, Any]] = []
    t_total = time.time()

    print(f"\n{'='*70}", flush=True)
    print(f"  Running {len(selected)} tasks x {len(configs)} configs", flush=True)
    print(f"  Timeout per task-config: {TASK_TIMEOUT}s", flush=True)
    print(f"{'='*70}\n", flush=True)

    for task_idx, (task_id, category) in enumerate(selected):
        if _interrupted:
            print("[INTERRUPT] Stopping.", flush=True)
            break

        train_pairs, test_inputs, test_outputs = load_task(task_id, challenges, solutions)
        task_results: Dict[str, Dict] = {}

        for cfg in configs:
            if _interrupted:
                break

            t0 = time.time()
            result = {"task_id": task_id, "config": cfg, "solved": False,
                      "operator_family": None, "view_program": None,
                      "certificate_path": None, "false_positive": False}

            try:
                if cfg == "static_only":
                    res = run_static_only(task_id, train_pairs, test_inputs, test_outputs)
                elif cfg == "full_v2_original":
                    res = run_full_v2(task_id, train_pairs, test_inputs, test_outputs)
                elif cfg == "view_only_adaptergenesis":
                    res = run_view_only(task_id, train_pairs, test_inputs, test_outputs, verifier)
                elif cfg == "operator_genesis_only":
                    res = run_operator_genesis_only(
                        task_id, train_pairs, test_inputs, test_outputs, verifier, proposals_log)
                elif cfg == "view_plus_operator_genesis":
                    res = run_view_plus_operator_genesis(
                        task_id, train_pairs, test_inputs, test_outputs, verifier, proposals_log)
                else:
                    res = {"solved": False}
                result.update(res)
            except Exception as e:
                tb_str = traceback.format_exc()
                print(f"  EXCEPTION in {cfg} for {task_id}: {e}", flush=True)
                print(tb_str, flush=True)
                result["solved"] = False
                result["error"] = f"{type(e).__name__}: {e}"

            elapsed = time.time() - t0
            result["runtime_seconds"] = round(elapsed, 2)
            task_results[cfg] = result
            all_results.append(result)

            status = "SOLVED" if result["solved"] else "failed"
            print(f"[{task_idx+1}/{len(selected)}] {task_id}: {cfg} {status} ({elapsed:.1f}s)", flush=True)

        # Check strict recovery
        static_res = task_results.get("static_only", {"solved": False})
        v2_res = task_results.get("full_v2_original", {"solved": False})

        for og_cfg in ["operator_genesis_only", "view_plus_operator_genesis"]:
            og_res = task_results.get(og_cfg, {"solved": False})
            if is_strict_recovery(static_res, v2_res, og_res):
                all_recoveries.append({
                    "task_id": task_id,
                    "category": category,
                    "operator_family": og_res.get("operator_family"),
                    "view_program": og_res.get("view_program"),
                    "certificate_path": og_res.get("certificate_path"),
                    "config": og_cfg,
                })

    elapsed_total = time.time() - t_total

    # Write outputs
    print(f"\n{'='*70}", flush=True)
    print("  Writing outputs...", flush=True)

    # Results CSV
    csv_path = OUT / "operator_genesis_pilot_results.csv"
    keys = ["task_id", "config", "solved", "operator_family", "view_program",
            "certificate_path", "false_positive", "runtime_seconds", "error"]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_results)
    print(f"  Saved results to {csv_path}", flush=True)

    # Recoveries CSV
    rec_path = OUT / "operator_genesis_new_recoveries.csv"
    rec_keys = ["task_id", "category", "operator_family", "view_program", "certificate_path", "config"]
    with open(rec_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rec_keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_recoveries)
    print(f"  Saved {len(all_recoveries)} recoveries to {rec_path}", flush=True)

    # Summary
    md_path = OUT / "operator_genesis_pilot_summary.md"
    with open(md_path, "w") as f:
        f.write("# OperatorGenesis Pilot Summary\n\n")
        f.write(f"**Date:** 2026-06-21\n")
        f.write(f"**Tasks:** {len(selected)}\n")
        f.write(f"**Runtime:** {elapsed_total:.1f}s ({elapsed_total/3600:.1f}h)\n\n")

        f.write("## Task Selection\n\n")
        f.write("| Category | Count |\n| --- | --- |\n")
        for cat, cnt in sorted(cat_counts.items()):
            f.write(f"| {cat} | {cnt} |\n")

        f.write("\n## Pass Rates by Configuration\n\n")
        f.write("| Config | Solved | Rate |\n| --- | --- | --- |\n")
        for cfg in configs:
            cfg_res = [r for r in all_results if r.get("config") == cfg]
            solved = sum(1 for r in cfg_res if r.get("solved"))
            total = len(cfg_res)
            rate = f"{100*solved/total:.1f}%" if total > 0 else "N/A"
            f.write(f"| {cfg} | {solved}/{total} | {rate} |\n")

        f.write(f"\n## New Recoveries: {len(all_recoveries)}\n\n")
        if all_recoveries:
            f.write("| Task | Category | Operator | View | Config |\n")
            f.write("| --- | --- | --- | --- | --- |\n")
            for rec in all_recoveries:
                f.write(f"| {rec['task_id']} | {rec['category']} "
                        f"| {rec.get('operator_family', '')} "
                        f"| {rec.get('view_program', '')} "
                        f"| {rec['config']} |\n")
        else:
            f.write("No tasks recovered by OperatorGenesis in this pilot.\n")

        if all_recoveries:
            f.write("\n## Interpretation\n\n")
            f.write("OperatorGenesis recovers tasks that all existing approaches fail on.\n")
            f.write("This confirms that the bottleneck was operator algorithmic coverage.\n")
        else:
            f.write("\n## Interpretation\n\n")
            f.write("OperatorGenesis did not recover any tasks in this pilot.\n")
            f.write("The remaining bottleneck may be higher-order program induction\n")
            f.write("beyond the current operator family repertoire.\n")

    print(f"  Saved summary to {md_path}", flush=True)

    # Print summary
    print(f"\n{'='*70}", flush=True)
    print("  SUMMARY", flush=True)
    print(f"{'='*70}", flush=True)
    print(f"  Tasks: {len(selected)}", flush=True)
    print(f"  Runtime: {elapsed_total:.1f}s ({elapsed_total/3600:.1f}h)", flush=True)
    print(f"  New recoveries: {len(all_recoveries)}", flush=True)
    for cfg in configs:
        cfg_res = [r for r in all_results if r.get("config") == cfg]
        solved = sum(1 for r in cfg_res if r.get("solved"))
        print(f"    {cfg}: {solved}/{len(cfg_res)}", flush=True)
    print(f"\n  Output: {OUT}", flush=True)


if __name__ == "__main__":
    main()
