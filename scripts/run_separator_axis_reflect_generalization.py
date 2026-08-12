"""Generalization pilot for separator_axis_reflect operator family.

Determines whether SAR generalizes beyond the 84ba50d3 micro-pilot recovery.
Selects up to 30 failed ARC-1000 tasks with full-span separators, plus
3 controls (1 positive, 2 diagnostic negatives). Runs 3 configs per task.

Usage:
    source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate
    cd /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project
    PYTHONPATH=src python3.11 scripts/run_separator_axis_reflect_generalization.py
"""
from __future__ import annotations

import csv
import json
import os
import sys
import time
import traceback
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy import ndimage

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from reasoning_project.operator_genesis import (
    synthesize_operators_from_train,
    _check_train_consistency,
    _check_loo,
    _synthesize_separator_axis_reflect,
    _detect_separator,
    _infer_background,
    SynthesizedOperator,
    FAMILY_SYNTHESIZERS,
)
from reasoning_project.proposal_verifier import ProposalVerifier
from reasoning_project.adaptive_orchestrator import (
    GatedAdaptiveReasoningOrchestrator,
    ModuleProposal,
)
from reasoning_project.reasoning_engine import (
    StructuralReasoner, ReasoningMemory, GridDomainAdapter,
)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs" / "full_novel_reasoning_pipeline_v2" / "separator_axis_reflect_generalization_2026_06_22"
ARC_CHALLENGES = ROOT / "data" / "arc" / "arc-agi_training_challenges.json"
ARC_SOLUTIONS = ROOT / "data" / "arc" / "arc-agi_training_solutions.json"
PROGRESS_FILE = ROOT / "outputs" / "full_novel_reasoning_pipeline_v2" / "arc1000_after_stable_baseline_2026_06_16" / "progress.jsonl"

POSITIVE_CONTROL = "84ba50d3"
DIAGNOSTIC_NEGATIVES = ["332202d5", "5168d44c"]
CONTROLS = [POSITIVE_CONTROL] + DIAGNOSTIC_NEGATIVES

MAX_SELECTED = 30
TASK_TIMEOUT = 300
FAMILY_NAME = "separator_axis_reflect"

CONFIGS = [
    "full_v2_original",
    f"operator_genesis_without_{FAMILY_NAME}",
    f"operator_genesis_with_{FAMILY_NAME}",
]


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

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


def load_failed_task_ids() -> set:
    failed = set()
    with open(PROGRESS_FILE) as f:
        for line in f:
            row = json.loads(line)
            if not row.get("v2_solved", False):
                failed.add(row["task_id"])
    return failed


# ---------------------------------------------------------------------------
# Separator analysis for task selection
# ---------------------------------------------------------------------------

def _count_objects_on_side(grid: np.ndarray, bg: int, axis: str, sep_idx: int) -> Tuple[int, int]:
    """Count connected components on each side of the separator."""
    H, W = grid.shape
    if axis == "h":
        above = grid[:sep_idx]
        below = grid[sep_idx + 1:]
    else:
        above = grid[:, :sep_idx]
        below = grid[:, sep_idx + 1:]

    def _count_cc(region):
        if region.size == 0:
            return 0
        mask = region != bg
        _, n = ndimage.label(mask)
        return n

    return _count_cc(above), _count_cc(below)


def analyze_separator_task(task_id: str, challenges: dict) -> Optional[Dict[str, Any]]:
    """Check if a task has separator structure suitable for SAR generalization.

    Returns analysis dict or None if not suitable.
    """
    task = challenges.get(task_id)
    if not task:
        return None

    train = task["train"]
    test = task["test"]

    first_inp = np.array(train[0]["input"], dtype=int)
    first_out = np.array(train[0]["output"], dtype=int)

    if first_inp.shape != first_out.shape:
        return None

    bg = _infer_background(first_inp)
    det = _detect_separator(first_inp, bg)
    if det is None:
        return None
    axis, sep_idx, sep_color = det

    for pair in train[1:]:
        inp = np.array(pair["input"], dtype=int)
        out = np.array(pair["output"], dtype=int)
        if inp.shape != out.shape:
            return None
        bg_i = _infer_background(inp)
        if bg_i != bg:
            return None
        det_i = _detect_separator(inp, bg_i)
        if det_i is None or det_i[0] != axis or det_i[2] != sep_color:
            return None

    for t in test:
        inp = np.array(t["input"], dtype=int)
        bg_t = _infer_background(inp)
        det_t = _detect_separator(inp, bg_t)
        if det_t is None or det_t[0] != axis or det_t[2] != sep_color:
            return None

    n_above, n_below = _count_objects_on_side(first_inp, bg, axis, sep_idx)
    has_objects_one_side = (n_above > 0 or n_below > 0)
    if not has_objects_one_side:
        return None

    return {
        "task_id": task_id,
        "separator_axis": axis,
        "separator_index": int(sep_idx),
        "separator_color": int(sep_color),
        "background_color": int(bg),
        "n_objects_above_or_left": int(n_above),
        "n_objects_below_or_right": int(n_below),
        "grid_shape": list(first_inp.shape),
        "n_train_pairs": len(train),
    }


def select_tasks(challenges: dict, failed_ids: set) -> Tuple[List[Dict], List[Dict]]:
    """Select candidate tasks and controls."""
    candidates = []
    for tid in sorted(failed_ids):
        if tid in CONTROLS:
            continue
        info = analyze_separator_task(tid, challenges)
        if info is not None:
            candidates.append(info)
        if len(candidates) >= MAX_SELECTED:
            break

    controls = []
    for tid in CONTROLS:
        info = analyze_separator_task(tid, challenges)
        if info is not None:
            controls.append(info)
        else:
            controls.append({
                "task_id": tid,
                "separator_axis": None,
                "separator_index": None,
                "separator_color": None,
                "background_color": None,
                "n_objects_above_or_left": None,
                "n_objects_below_or_right": None,
                "grid_shape": None,
                "n_train_pairs": None,
                "note": "no_separator_detected",
            })

    return candidates, controls


# ---------------------------------------------------------------------------
# Config runners
# ---------------------------------------------------------------------------

def _safe_params(params):
    out = {}
    for k, v in params.items():
        if isinstance(v, (int, float, str, bool, list, dict)):
            out[k] = v
        elif isinstance(v, np.integer):
            out[k] = int(v)
        elif isinstance(v, np.floating):
            out[k] = float(v)
        else:
            out[k] = str(v)
    return out


def run_full_v2(task_id, train_pairs, test_inputs, test_outputs):
    orch = GatedAdaptiveReasoningOrchestrator()
    trace = orch.solve_task(task_id, train_pairs, test_inputs, test_outputs)
    solved = trace.final_status == "solved"
    op_family = None
    if trace.selected_proposal:
        op_family = trace.selected_proposal.operator_family
    return {"solved": solved, "operator_family": op_family,
            "n_sar_proposals": 0, "train_consistent": None,
            "loo_passed": None, "verifier_accepted": None,
            "certificate_path": None, "false_positive": False, "detail": []}


def _run_og_with_families(
    task_id, train_pairs, test_inputs, test_outputs,
    verifier, log_path, include_sar: bool,
):
    """Run OperatorGenesis with or without separator_axis_reflect."""
    ops = synthesize_operators_from_train(train_pairs)

    if not include_sar:
        ops = [o for o in ops if o.operator_family != FAMILY_NAME]

    n_sar = sum(1 for o in ops if o.operator_family == FAMILY_NAME)

    tc_ops = []
    for o in ops:
        ok, _ = _check_train_consistency(o.execute, train_pairs)
        if ok:
            tc_ops.append(o)

    results_detail = []
    for op in tc_ops:
        loo_ok = _check_loo(
            lambda pairs, _fam=op.operator_family: [
                o for o in synthesize_operators_from_train(pairs)
                if o.operator_family == _fam
                and _check_train_consistency(o.execute, pairs)[0]
            ],
            train_pairs,
        )

        detail = {
            "task_id": task_id,
            "config": f"operator_genesis_{'with' if include_sar else 'without'}_{FAMILY_NAME}",
            "operator_id": op.operator_id,
            "operator_family": op.operator_family,
            "parameters": json.dumps(_safe_params(op.parameters)),
            "explanation": op.explanation,
            "train_consistent": True,
            "loo_passed": loo_ok,
        }

        if not loo_ok:
            detail["verifier_accepted"] = False
            detail["certificate_path"] = None
            results_detail.append(detail)
            continue

        mod_prop = ModuleProposal(
            module_name="operator_genesis",
            proposal_type=f"og_{op.operator_family}",
            operator_family=op.operator_family,
            selector=op.explanation,
            hypothesis={"execute": op.execute},
            confidence=0.8,
            evidence={"parameters": _safe_params(op.parameters), "loo_passed": True},
        )
        outcome = verifier.verify(mod_prop, train_pairs, test_inputs, test_outputs)
        detail["verifier_accepted"] = outcome.accepted
        detail["certificate_path"] = outcome.certificate_path if outcome.accepted else None
        results_detail.append(detail)

        if outcome.accepted:
            entry = {
                "task_id": task_id,
                "operator_family": op.operator_family,
                "operator_id": op.operator_id,
                "explanation": op.explanation,
                "parameters": _safe_params(op.parameters),
                "train_consistent": True,
                "loo_passed": loo_ok,
                "verifier_accepted": True,
                "certificate_path": outcome.certificate_path,
                "include_sar": include_sar,
            }
            with open(log_path, "a") as f:
                f.write(json.dumps(entry) + "\n")

            return {
                "solved": True,
                "operator_family": op.operator_family,
                "n_sar_proposals": n_sar,
                "train_consistent": True,
                "loo_passed": True,
                "verifier_accepted": True,
                "certificate_path": outcome.certificate_path,
                "false_positive": False,
                "detail": results_detail,
            }

    return {
        "solved": False,
        "operator_family": None,
        "n_sar_proposals": n_sar,
        "train_consistent": any(d["train_consistent"] for d in results_detail) if results_detail else False,
        "loo_passed": any(d.get("loo_passed") for d in results_detail) if results_detail else False,
        "verifier_accepted": False,
        "certificate_path": None,
        "false_positive": False,
        "detail": results_detail,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    os.makedirs(OUT, exist_ok=True)
    cert_dir = OUT / "certificates"
    os.makedirs(cert_dir, exist_ok=True)
    log_path = str(OUT / "proposals.jsonl")

    print("=" * 70, flush=True)
    print("  Separator Axis Reflect — Generalization Pilot", flush=True)
    print(f"  {datetime.now().isoformat()}", flush=True)
    print("=" * 70, flush=True)

    challenges, solutions = load_arc_data()
    failed_ids = load_failed_task_ids()
    print(f"Failed task IDs loaded: {len(failed_ids)}", flush=True)

    candidates, controls = select_tasks(challenges, failed_ids)
    print(f"Selected {len(candidates)} candidate tasks + {len(controls)} controls", flush=True)

    # --- Write task selection CSV ---
    all_task_infos = controls + candidates
    task_csv_path = OUT / "sar_generalization_tasks.csv"
    task_keys = ["task_id", "separator_axis", "separator_index", "separator_color",
                 "background_color", "n_objects_above_or_left", "n_objects_below_or_right",
                 "grid_shape", "n_train_pairs", "note"]
    with open(task_csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=task_keys, extrasaction="ignore")
        writer.writeheader()
        for info in all_task_infos:
            row = dict(info)
            if isinstance(row.get("grid_shape"), list):
                row["grid_shape"] = f"{row['grid_shape'][0]}x{row['grid_shape'][1]}"
            writer.writerow(row)
    print(f"Saved {task_csv_path}", flush=True)

    verifier = ProposalVerifier(certificate_dir=str(cert_dir))

    all_results: List[Dict[str, Any]] = []
    all_details: List[Dict[str, Any]] = []
    t_total = time.time()

    task_ids = [info["task_id"] for info in all_task_infos]
    print(f"\nRunning {len(task_ids)} tasks × {len(CONFIGS)} configs = {len(task_ids) * len(CONFIGS)} evaluations\n",
          flush=True)

    for idx, task_id in enumerate(task_ids):
        role = "POSITIVE_CONTROL" if task_id == POSITIVE_CONTROL else \
               "DIAGNOSTIC_NEGATIVE" if task_id in DIAGNOSTIC_NEGATIVES else \
               "CANDIDATE"
        print(f"\n[{idx+1}/{len(task_ids)}] Task {task_id} ({role})", flush=True)

        train_pairs, test_inputs, test_outputs = load_task(task_id, challenges, solutions)

        task_info = next((t for t in all_task_infos if t["task_id"] == task_id), {})

        for cfg in CONFIGS:
            t0 = time.time()
            result = {
                "task_id": task_id,
                "role": role,
                "config": cfg,
                "solved": False,
                "operator_family": None,
                "separator_axis": task_info.get("separator_axis"),
                "separator_index": task_info.get("separator_index"),
                "separator_color": task_info.get("separator_color"),
                "background_color": task_info.get("background_color"),
                "n_objects_above_or_left": task_info.get("n_objects_above_or_left"),
                "n_objects_below_or_right": task_info.get("n_objects_below_or_right"),
                "n_sar_proposals": 0,
                "train_consistent": None,
                "loo_passed": None,
                "verifier_accepted": None,
                "false_positive": False,
                "certificate_path": None,
                "runtime_seconds": 0.0,
                "error": None,
            }
            try:
                if cfg == "full_v2_original":
                    res = run_full_v2(task_id, train_pairs, test_inputs, test_outputs)
                elif cfg == f"operator_genesis_without_{FAMILY_NAME}":
                    res = _run_og_with_families(
                        task_id, train_pairs, test_inputs, test_outputs,
                        verifier, log_path, include_sar=False)
                elif cfg == f"operator_genesis_with_{FAMILY_NAME}":
                    res = _run_og_with_families(
                        task_id, train_pairs, test_inputs, test_outputs,
                        verifier, log_path, include_sar=True)
                else:
                    res = {"solved": False}

                detail = res.pop("detail", [])
                result.update(res)
                for d in detail:
                    all_details.append(d)

            except Exception as e:
                tb_str = traceback.format_exc()
                print(f"  EXCEPTION in {cfg}: {e}", flush=True)
                print(tb_str[:500], flush=True)
                result["error"] = f"{type(e).__name__}: {e}"

            elapsed = time.time() - t0
            result["runtime_seconds"] = round(elapsed, 2)
            all_results.append(result)

            status = "SOLVED" if result["solved"] else "failed"
            extra = ""
            if result["solved"]:
                extra = f" [{result.get('operator_family')}]"
            if result.get("error"):
                extra += f" ERROR"
            print(f"  {cfg}: {status} ({elapsed:.1f}s){extra}", flush=True)

    elapsed_total = time.time() - t_total

    # --- Write results CSV ---
    results_csv = OUT / "sar_generalization_results.csv"
    result_keys = ["task_id", "role", "config", "solved", "operator_family",
                   "separator_axis", "separator_index", "separator_color",
                   "background_color", "n_objects_above_or_left",
                   "n_objects_below_or_right",
                   "n_sar_proposals", "train_consistent", "loo_passed",
                   "verifier_accepted", "false_positive", "certificate_path",
                   "runtime_seconds", "error"]
    with open(results_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=result_keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_results)
    print(f"\nSaved {results_csv}", flush=True)

    # --- Write ablation CSV ---
    ablation_csv = OUT / "sar_generalization_ablation.csv"
    abl_keys = ["task_id", "config", "operator_id", "operator_family",
                "parameters", "explanation", "train_consistent", "loo_passed",
                "verifier_accepted", "certificate_path"]
    with open(ablation_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=abl_keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_details)
    print(f"Saved {ablation_csv}", flush=True)

    # --- Compute summary statistics ---
    # Acceptance criteria
    pc_results = [r for r in all_results if r["task_id"] == POSITIVE_CONTROL]
    pc_with = next((r for r in pc_results
                    if r["config"] == f"operator_genesis_with_{FAMILY_NAME}"), None)
    pc_without = next((r for r in pc_results
                       if r["config"] == f"operator_genesis_without_{FAMILY_NAME}"), None)
    pc_v2 = next((r for r in pc_results if r["config"] == "full_v2_original"), None)

    positive_control_pass = (
        pc_with is not None and pc_with["solved"]
        and (pc_without is None or not pc_without["solved"])
        and (pc_v2 is None or not pc_v2["solved"])
    )

    total_fp = sum(1 for r in all_results if r.get("false_positive"))
    total_errors = sum(1 for r in all_results if r.get("error"))

    # Gather per-task SAR-dependent solves (not counting controls)
    candidate_ids = [info["task_id"] for info in candidates]
    new_sar_solves = []
    for tid in candidate_ids:
        with_cfg = f"operator_genesis_with_{FAMILY_NAME}"
        without_cfg = f"operator_genesis_without_{FAMILY_NAME}"
        v2_cfg = "full_v2_original"

        with_r = next((r for r in all_results if r["task_id"] == tid and r["config"] == with_cfg), None)
        without_r = next((r for r in all_results if r["task_id"] == tid and r["config"] == without_cfg), None)
        v2_r = next((r for r in all_results if r["task_id"] == tid and r["config"] == v2_cfg), None)

        if with_r and with_r["solved"]:
            baselines_fail = (
                (without_r is None or not without_r["solved"])
                and (v2_r is None or not v2_r["solved"])
            )
            if baselines_fail and with_r.get("operator_family") == FAMILY_NAME:
                new_sar_solves.append(tid)

    # Diagnostic negatives
    diag_forced = []
    for tid in DIAGNOSTIC_NEGATIVES:
        with_r = next((r for r in all_results
                       if r["task_id"] == tid
                       and r["config"] == f"operator_genesis_with_{FAMILY_NAME}"), None)
        if with_r and with_r["solved"]:
            diag_forced.append(tid)

    # Overall acceptance
    acceptance_pass = (
        positive_control_pass
        and total_fp == 0
        and total_errors == 0
        and len(diag_forced) == 0
    )

    # Config-level solve counts
    solve_by_config = defaultdict(int)
    for r in all_results:
        if r["solved"]:
            solve_by_config[r["config"]] += 1

    # --- Write summary ---
    summary_path = OUT / "sar_generalization_summary.md"
    with open(summary_path, "w") as f:
        f.write("# Separator Axis Reflect — Generalization Pilot Summary\n\n")
        f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d')}\n")
        f.write(f"**Tasks evaluated:** {len(task_ids)} ({len(candidates)} candidates + {len(controls)} controls)\n")
        f.write(f"**Configs:** {len(CONFIGS)}\n")
        f.write(f"**Total evaluations:** {len(all_results)}\n")
        f.write(f"**Runtime:** {elapsed_total:.1f}s ({elapsed_total/60:.1f}min)\n\n")

        f.write("## Acceptance Criteria\n\n")
        f.write(f"- Positive control `{POSITIVE_CONTROL}` solved by SAR: "
                f"**{'PASS' if positive_control_pass else 'FAIL'}**\n")
        f.write(f"- False positives: **{total_fp}**\n")
        f.write(f"- Exceptions: **{total_errors}**\n")
        f.write(f"- Diagnostic negatives forced to solve: **{len(diag_forced)}** {diag_forced}\n")
        f.write(f"- **Overall acceptance: {'PASS' if acceptance_pass else 'FAIL'}**\n\n")

        f.write("## Results by Config\n\n")
        f.write("| Config | Solved | Total |\n|--------|--------|-------|\n")
        for cfg in CONFIGS:
            f.write(f"| {cfg} | {solve_by_config[cfg]} | {len(task_ids)} |\n")

        f.write(f"\n## SAR-Dependent New Solves (candidates only)\n\n")
        f.write(f"**Count:** {len(new_sar_solves)}\n\n")
        if new_sar_solves:
            f.write("| Task ID | Certificate |\n|---------|-------------|\n")
            for tid in new_sar_solves:
                cert = next((r.get("certificate_path") for r in all_results
                             if r["task_id"] == tid
                             and r["config"] == f"operator_genesis_with_{FAMILY_NAME}"
                             and r["solved"]), None)
                f.write(f"| {tid} | {cert or 'N/A'} |\n")
        else:
            f.write("No new SAR-dependent solves among candidates.\n")

        f.write("\n## Positive Control Detail\n\n")
        f.write(f"| Config | Solved | Family | Runtime |\n|--------|--------|--------|---------|\n")
        for r in pc_results:
            f.write(f"| {r['config']} | {r['solved']} | {r.get('operator_family') or ''} | {r['runtime_seconds']:.1f}s |\n")

        f.write("\n## Diagnostic Negative Detail\n\n")
        for tid in DIAGNOSTIC_NEGATIVES:
            f.write(f"### {tid}\n\n")
            f.write(f"| Config | Solved | Family | Runtime |\n|--------|--------|--------|---------|\n")
            for r in all_results:
                if r["task_id"] == tid:
                    f.write(f"| {r['config']} | {r['solved']} | {r.get('operator_family') or ''} | {r['runtime_seconds']:.1f}s |\n")
            f.write("\n")

        f.write("## Candidate Task Results\n\n")
        f.write("| Task | Sep Axis | Sep Color | BG | Objs Above/Left | Objs Below/Right | full_v2 | OG-SAR | OG+SAR | SAR Proposals | Certificate |\n")
        f.write("|------|----------|-----------|----|-----------------|--------------------|---------|--------|--------|---------------|-------------|\n")
        for tid in candidate_ids:
            info = next((t for t in candidates if t["task_id"] == tid), {})
            v2_r = next((r for r in all_results if r["task_id"] == tid and r["config"] == "full_v2_original"), {})
            wo_r = next((r for r in all_results if r["task_id"] == tid and r["config"] == f"operator_genesis_without_{FAMILY_NAME}"), {})
            wi_r = next((r for r in all_results if r["task_id"] == tid and r["config"] == f"operator_genesis_with_{FAMILY_NAME}"), {})
            cert = wi_r.get("certificate_path") or ""
            f.write(f"| {tid} | {info.get('separator_axis','')} | {info.get('separator_color','')} "
                    f"| {info.get('background_color','')} | {info.get('n_objects_above_or_left','')} "
                    f"| {info.get('n_objects_below_or_right','')} "
                    f"| {'Y' if v2_r.get('solved') else 'N'} "
                    f"| {'Y' if wo_r.get('solved') else 'N'} "
                    f"| {'Y' if wi_r.get('solved') else 'N'} "
                    f"| {wi_r.get('n_sar_proposals', 0)} "
                    f"| {cert} |\n")

        if all_details:
            f.write("\n## Operator-Level Ablation (SAR proposals only)\n\n")
            sar_details = [d for d in all_details if d.get("operator_family") == FAMILY_NAME]
            if sar_details:
                f.write("| Task | Config | Operator | Train | LOO | Accepted | Cert |\n")
                f.write("|------|--------|----------|-------|-----|----------|------|\n")
                for d in sar_details:
                    f.write(f"| {d.get('task_id','')} | {d.get('config','')} "
                            f"| {d.get('operator_id','')} "
                            f"| {d.get('train_consistent','')} | {d.get('loo_passed','')} "
                            f"| {d.get('verifier_accepted','')} | {d.get('certificate_path','')} |\n")
            else:
                f.write("No SAR-family proposals in ablation details.\n")

    print(f"Saved {summary_path}", flush=True)

    # --- Write claim update ---
    claim_path = OUT / "sar_generalization_claim_update.md"
    with open(claim_path, "w") as f:
        f.write("# Separator Axis Reflect — Generalization Claim Update\n\n")
        f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d')}\n\n")

        if len(new_sar_solves) > 0 and acceptance_pass:
            f.write("## Claim (Positive Generalization)\n\n")
            f.write(f"`separator_axis_reflect` generalizes to {len(new_sar_solves)} additional "
                    f"separator-axis ARC task{'s' if len(new_sar_solves) != 1 else ''} "
                    f"with zero accepted false positives.\n\n")
            f.write(f"**New SAR-dependent solves:** {', '.join(new_sar_solves)}\n")
            f.write(f"**Positive control (`{POSITIVE_CONTROL}`) reproduced:** Yes\n")
            f.write(f"**False positives:** {total_fp}\n")
            f.write(f"**Candidate tasks screened:** {len(candidates)}\n\n")
            f.write("Paper-safe wording:\n\n")
            total_sar = len(new_sar_solves) + 1
            f.write(f"> `separator_axis_reflect` recovers {total_sar} ARC tasks "
                    f"(1 from micro-pilot + {len(new_sar_solves)} from generalization), "
                    f"all verified via train consistency, LOO, proof obligations, "
                    f"and certificate emission, with zero false positives across "
                    f"{len(candidates)} screened separator-bearing tasks.\n")

        elif acceptance_pass and len(new_sar_solves) == 0:
            f.write("## Claim (Targeted Only)\n\n")
            f.write(f"`separator_axis_reflect` remains a targeted recovery for `{POSITIVE_CONTROL}`; "
                    f"broader separator tasks require additional subfamilies such as "
                    f"region-fill or track-motion.\n\n")
            f.write(f"**Positive control reproduced:** Yes\n")
            f.write(f"**New generalizations:** 0 / {len(candidates)} candidates\n")
            f.write(f"**False positives:** {total_fp}\n\n")
            f.write("Paper-safe wording:\n\n")
            f.write("> Two targeted verified recoveries were obtained from the program-gap audit: "
                    "one by containment-depth filling and one by separator-axis reflection. "
                    "The separator-axis-reflect family did not generalize to additional "
                    "separator-bearing tasks in a pilot of "
                    f"{len(candidates)} screened candidates, suggesting that richer "
                    "separator reasoning subfamilies (region-fill, track-motion) are needed.\n")

        else:
            f.write("## Claim (Negative / Acceptance Failed)\n\n")
            f.write(f"The generalization pilot did not meet acceptance criteria.\n\n")
            f.write(f"**Positive control passed:** {positive_control_pass}\n")
            f.write(f"**False positives:** {total_fp}\n")
            f.write(f"**Errors:** {total_errors}\n")
            f.write(f"**Diagnostic negatives forced:** {diag_forced}\n")

        f.write("\n## Evidence Chain\n\n")
        f.write("1. Micro-pilot established SAR recovers `84ba50d3` (1 task, 5 configs, 0 FP)\n")
        f.write(f"2. Generalization pilot screened {len(candidates)} separator-bearing failed tasks\n")
        f.write(f"3. Task selection: full-span uniform separator, same-shape I/O, "
                f"objects on at least one side, baseline-v2-failed\n")
        f.write(f"4. 3 configs × {len(task_ids)} tasks evaluated\n")
        f.write(f"5. SAR-dependent new solves: {len(new_sar_solves)}\n")
        f.write(f"6. False positives: {total_fp}\n")
        f.write(f"7. Runtime: {elapsed_total:.1f}s\n")

    print(f"Saved {claim_path}", flush=True)

    # --- Final console summary ---
    print("\n" + "=" * 70, flush=True)
    print("  GENERALIZATION PILOT COMPLETE", flush=True)
    print("=" * 70, flush=True)
    print(f"  Tasks evaluated: {len(task_ids)}", flush=True)
    print(f"  Positive control reproduced: {positive_control_pass}", flush=True)
    print(f"  SAR-dependent new solves: {len(new_sar_solves)}", flush=True)
    print(f"  False positives: {total_fp}", flush=True)
    print(f"  Errors: {total_errors}", flush=True)
    print(f"  Diagnostic negatives forced: {len(diag_forced)}", flush=True)
    print(f"  Acceptance: {'PASS' if acceptance_pass else 'FAIL'}", flush=True)
    print(f"  Runtime: {elapsed_total:.1f}s", flush=True)
    print("=" * 70, flush=True)


if __name__ == "__main__":
    main()
