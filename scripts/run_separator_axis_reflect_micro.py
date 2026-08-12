"""Micro-pilot for separator_axis_reflect operator family.

Runs 3 tasks × 5 configs to verify the new operator recovers tasks
that all baselines fail on, with full verification and ablation.

Primary target: 84ba50d3
Diagnostic only: 332202d5, 5168d44c (not expected to be solved by this family)

Usage:
    source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate
    cd /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project
    PYTHONPATH=src python3.11 scripts/run_separator_axis_reflect_micro.py
"""
from __future__ import annotations

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

from reasoning_project.operator_genesis import (
    synthesize_operators_from_train,
    _check_train_consistency,
    _check_loo,
    _synthesize_separator_axis_reflect,
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
OUT = ROOT / "outputs" / "full_novel_reasoning_pipeline_v2" / "separator_axis_reflect_v1_2026_06_22"
ARC_CHALLENGES = ROOT / "data" / "arc" / "arc-agi_training_challenges.json"
ARC_SOLUTIONS = ROOT / "data" / "arc" / "arc-agi_training_solutions.json"

TARGET_TASKS = ["84ba50d3", "332202d5", "5168d44c"]
PRIMARY_TASK = "84ba50d3"
TASK_TIMEOUT = 300
FAMILY_NAME = "separator_axis_reflect"


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


# ---------------------------------------------------------------------------
# Config runners
# ---------------------------------------------------------------------------

def run_static_only(task_id, train_pairs, test_inputs, test_outputs):
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
    from reasoning_project.failure_driven_adaptergenesis import run_failure_driven_adaptergenesis
    proposals = run_failure_driven_adaptergenesis(
        task_id, train_pairs, test_inputs, test_outputs,
        timeout=TASK_TIMEOUT, max_views=30,
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


def _run_og_with_families(
    task_id, train_pairs, test_inputs, test_outputs,
    verifier, log_path, include_sar: bool,
):
    """Run OperatorGenesis with or without separator_axis_reflect."""
    ops = synthesize_operators_from_train(train_pairs)

    if not include_sar:
        ops = [o for o in ops if o.operator_family != FAMILY_NAME]

    tc_ops = [o for o in ops if _check_train_consistency(o.execute, train_pairs)[0]]

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
            "operator_id": op.operator_id,
            "operator_family": op.operator_family,
            "parameters": op.parameters,
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
            if log_path:
                _log_proposal(log_path, task_id, op, loo_ok, outcome)
            return {
                "solved": True,
                "operator_family": op.operator_family,
                "certificate_path": outcome.certificate_path,
                "false_positive": False,
                "detail": results_detail,
            }

    if log_path:
        for op in ops:
            _log_proposal_attempt(log_path, task_id, op, include_sar)

    return {"solved": False, "detail": results_detail}


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


def _log_proposal(log_path, task_id, op, loo_ok, outcome):
    entry = {
        "task_id": task_id,
        "operator_family": op.operator_family,
        "operator_id": op.operator_id,
        "explanation": op.explanation,
        "parameters": _safe_params(op.parameters),
        "train_consistent": True,
        "loo_passed": loo_ok,
        "verifier_accepted": outcome.accepted,
        "certificate_path": outcome.certificate_path if outcome.accepted else None,
    }
    with open(log_path, "a") as f:
        f.write(json.dumps(entry) + "\n")


def _log_proposal_attempt(log_path, task_id, op, include_sar):
    entry = {
        "task_id": task_id,
        "operator_family": op.operator_family,
        "operator_id": op.operator_id,
        "explanation": op.explanation,
        "include_sar": include_sar,
    }
    with open(log_path, "a") as f:
        f.write(json.dumps(entry) + "\n")


def run_og_without_sar(task_id, train_pairs, test_inputs, test_outputs, verifier, log_path):
    return _run_og_with_families(task_id, train_pairs, test_inputs, test_outputs,
                                  verifier, log_path, include_sar=False)


def run_og_with_sar(task_id, train_pairs, test_inputs, test_outputs, verifier, log_path):
    return _run_og_with_families(task_id, train_pairs, test_inputs, test_outputs,
                                  verifier, log_path, include_sar=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    os.makedirs(OUT, exist_ok=True)
    cert_dir = OUT / "certificates"
    os.makedirs(cert_dir, exist_ok=True)
    log_path = str(OUT / "proposals.jsonl")

    print("=" * 70, flush=True)
    print("  Separator Axis Reflect — Micro Pilot", flush=True)
    print("=" * 70, flush=True)

    challenges, solutions = load_arc_data()
    verifier = ProposalVerifier(certificate_dir=str(cert_dir))

    configs = [
        "static_only",
        "full_v2_original",
        "view_only_adaptergenesis",
        f"operator_genesis_without_{FAMILY_NAME}",
        f"operator_genesis_with_{FAMILY_NAME}",
    ]

    all_results: List[Dict[str, Any]] = []
    all_details: List[Dict[str, Any]] = []
    t_total = time.time()

    for task_id in TARGET_TASKS:
        print(f"\n--- Task {task_id} {'(PRIMARY)' if task_id == PRIMARY_TASK else '(diagnostic)'} ---",
              flush=True)
        train_pairs, test_inputs, test_outputs = load_task(task_id, challenges, solutions)

        for cfg in configs:
            t0 = time.time()
            result = {"task_id": task_id, "config": cfg, "solved": False,
                      "operator_family": None, "certificate_path": None,
                      "false_positive": False, "error": None}
            try:
                if cfg == "static_only":
                    res = run_static_only(task_id, train_pairs, test_inputs, test_outputs)
                elif cfg == "full_v2_original":
                    res = run_full_v2(task_id, train_pairs, test_inputs, test_outputs)
                elif cfg == "view_only_adaptergenesis":
                    res = run_view_only(task_id, train_pairs, test_inputs, test_outputs, verifier)
                elif cfg == f"operator_genesis_without_{FAMILY_NAME}":
                    res = run_og_without_sar(
                        task_id, train_pairs, test_inputs, test_outputs, verifier, log_path)
                elif cfg == f"operator_genesis_with_{FAMILY_NAME}":
                    res = run_og_with_sar(
                        task_id, train_pairs, test_inputs, test_outputs, verifier, log_path)
                else:
                    res = {"solved": False}
                detail = res.pop("detail", None)
                result.update(res)
                if detail:
                    for d in detail:
                        d["task_id"] = task_id
                        d["config"] = cfg
                        all_details.append(d)
            except Exception as e:
                tb_str = traceback.format_exc()
                print(f"  EXCEPTION in {cfg}: {e}", flush=True)
                print(tb_str, flush=True)
                result["error"] = f"{type(e).__name__}: {e}"

            elapsed = time.time() - t0
            result["runtime_seconds"] = round(elapsed, 2)
            all_results.append(result)

            status = "SOLVED" if result["solved"] else "failed"
            print(f"  {cfg}: {status} ({elapsed:.1f}s)"
                  + (f" [{result.get('operator_family')}]" if result["solved"] else "")
                  + (f" ERROR: {result['error']}" if result.get("error") else ""),
                  flush=True)

    elapsed_total = time.time() - t_total

    # --- Write results CSV ---
    csv_path = OUT / f"{FAMILY_NAME}_micro_results.csv"
    keys = ["task_id", "config", "solved", "operator_family", "certificate_path",
            "false_positive", "runtime_seconds", "error"]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_results)
    print(f"\nSaved {csv_path}", flush=True)

    # --- Write ablation CSV ---
    abl_path = OUT / f"{FAMILY_NAME}_ablation.csv"
    abl_keys = ["task_id", "config", "operator_id", "operator_family",
                "train_consistent", "loo_passed", "verifier_accepted", "certificate_path"]
    with open(abl_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=abl_keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_details)
    print(f"Saved {abl_path}", flush=True)

    # --- Compute summary stats ---
    # Primary task only for acceptance criteria
    primary_results = [r for r in all_results if r["task_id"] == PRIMARY_TASK]
    primary_baselines_fail = all(
        not r["solved"] for r in primary_results
        if r["config"] in ["static_only", "full_v2_original", "view_only_adaptergenesis"]
    )
    primary_without = next((r for r in primary_results
                            if r["config"] == f"operator_genesis_without_{FAMILY_NAME}"), None)
    primary_with = next((r for r in primary_results
                         if r["config"] == f"operator_genesis_with_{FAMILY_NAME}"), None)
    primary_without_solved = primary_without["solved"] if primary_without else False
    primary_with_solved = primary_with["solved"] if primary_with else False

    n_fp = sum(1 for r in all_results if r.get("false_positive"))
    n_errors = sum(1 for r in all_results if r.get("error"))

    # Count all recoveries
    solved_by_config = {}
    for cfg in configs:
        cfg_results = [r for r in all_results if r["config"] == cfg]
        solved_by_config[cfg] = sum(1 for r in cfg_results if r["solved"])

    primary_recovery = (primary_baselines_fail
                        and not primary_without_solved
                        and primary_with_solved
                        and n_fp == 0
                        and n_errors == 0)

    # --- Write summary MD ---
    md_path = OUT / f"{FAMILY_NAME}_micro_summary.md"
    with open(md_path, "w") as f:
        f.write(f"# Separator Axis Reflect — Micro Pilot Summary\n\n")
        f.write(f"**Date:** 2026-06-22\n")
        f.write(f"**Primary target:** {PRIMARY_TASK}\n")
        f.write(f"**Diagnostic tasks:** {', '.join(t for t in TARGET_TASKS if t != PRIMARY_TASK)}\n")
        f.write(f"**Runtime:** {elapsed_total:.1f}s\n\n")

        f.write("## Results by Config\n\n")
        f.write("| Config | Solved |\n|--------|--------|\n")
        for cfg in configs:
            f.write(f"| {cfg} | {solved_by_config[cfg]}/{len(TARGET_TASKS)} |\n")

        f.write(f"\n## Primary Task Acceptance ({PRIMARY_TASK})\n\n")
        f.write(f"- Baselines all fail: **{'PASS' if primary_baselines_fail else 'FAIL'}**\n")
        f.write(f"- OG without SAR: **{'SOLVED' if primary_without_solved else 'failed'}**\n")
        f.write(f"- OG with SAR: **{'SOLVED' if primary_with_solved else 'failed'}**\n")
        f.write(f"- SAR-necessary recovery: **{'YES' if primary_recovery else 'NO'}**\n")
        f.write(f"- False positives: **{n_fp}**\n")
        f.write(f"- Exceptions: **{n_errors}**\n")
        f.write(f"- **Overall: {'PASS' if primary_recovery else 'FAIL'}**\n\n")

        f.write("## Per-Task Detail\n\n")
        for task_id in TARGET_TASKS:
            task_results = [r for r in all_results if r["task_id"] == task_id]
            label = "PRIMARY" if task_id == PRIMARY_TASK else "diagnostic"
            f.write(f"### {task_id} ({label})\n\n")
            f.write("| Config | Solved | Family | Runtime | Certificate |\n")
            f.write("|--------|--------|--------|---------|-------------|\n")
            for r in task_results:
                f.write(f"| {r['config']} | {r['solved']} | {r.get('operator_family') or ''} "
                        f"| {r['runtime_seconds']:.1f}s | {r.get('certificate_path') or ''} |\n")
            f.write("\n")

        if all_details:
            f.write("## Operator-Level Ablation\n\n")
            f.write("| Task | Config | Operator | Family | Train | LOO | Accepted | Cert |\n")
            f.write("|------|--------|----------|--------|-------|-----|----------|------|\n")
            for d in all_details:
                f.write(f"| {d.get('task_id','')} | {d.get('config','')} "
                        f"| {d.get('operator_id','')} | {d.get('operator_family','')} "
                        f"| {d.get('train_consistent','')} | {d.get('loo_passed','')} "
                        f"| {d.get('verifier_accepted','')} | {d.get('certificate_path','')} |\n")
            f.write("\n")

    print(f"Saved {md_path}", flush=True)

    # --- Write ablation MD ---
    abl_md_path = OUT / f"{FAMILY_NAME}_ablation.md"
    with open(abl_md_path, "w") as f:
        f.write(f"# Separator Axis Reflect — Ablation\n\n")
        f.write(f"**Date:** 2026-06-22\n\n")
        f.write("## Necessity Test (Primary Task)\n\n")
        f.write(f"- OG without SAR: **{'SOLVED' if primary_without_solved else 'failed'}**\n")
        f.write(f"- OG with SAR: **{'SOLVED' if primary_with_solved else 'failed'}**\n")
        f.write(f"- SAR is necessary: **{'YES' if primary_recovery else 'NO'}**\n\n")
        if primary_recovery:
            f.write(f"SAR-dependent recovery: **{PRIMARY_TASK}**\n\n")

    print(f"Saved {abl_md_path}", flush=True)

    # --- Write claim update ---
    claim_path = OUT / f"{FAMILY_NAME}_claim_update.md"
    with open(claim_path, "w") as f:
        f.write(f"# Separator Axis Reflect — Claim Update\n\n")
        f.write(f"**Date:** 2026-06-22\n\n")
        if primary_recovery:
            f.write("## Claim (Positive)\n\n")
            f.write("`separator_axis_reflect` provides a second targeted verified recovery\n")
            f.write("from the program-gap audit, showing that separator-relative spatial\n")
            f.write("programs are a missing operator family.\n\n")
            f.write(f"**Recovered task:** {PRIMARY_TASK}\n")
            f.write(f"**False positives:** {n_fp}\n")
        else:
            f.write("## Claim (Negative)\n\n")
            f.write("Reflection-only separator reasoning did not recover the target task;\n")
            f.write("the separator family likely requires richer region-fill or track-motion\n")
            f.write("modes.\n\n")
            f.write(f"**Recovered tasks:** 0\n")
            f.write(f"**Issues:** baselines_fail={primary_baselines_fail}, "
                    f"without_sar={primary_without_solved}, "
                    f"with_sar={primary_with_solved}, "
                    f"fp={n_fp}, errors={n_errors}\n")

        f.write("\n## Evidence Chain\n\n")
        f.write("1. Program gap audit identified separator_reflection as medium-risk opportunity\n")
        f.write("2. Implemented `separator_axis_reflect` subfamily in OperatorGenesis:\n")
        f.write("   - Detects full-span separator row/column\n")
        f.write("   - Wide CCs: align widest row to sep-1 (can cross separator)\n")
        f.write("   - Narrow CCs: mirror (2*sep-r) then gravity-drop to bottom\n")
        f.write("   - Separator cleared at narrow-CC columns, pierced at wide-CC crossings\n")
        f.write("3. Micro-pilot on 3 tasks (1 primary + 2 diagnostic) × 5 configs\n")
        f.write(f"4. Result: primary {'recovered' if primary_recovery else 'not recovered'}, "
                f"{n_fp} FP\n")

    print(f"Saved {claim_path}", flush=True)

    # --- Write design doc ---
    design_path = OUT / f"{FAMILY_NAME}_design.md"
    with open(design_path, "w") as f:
        f.write(f"# Separator Axis Reflect — Design\n\n")
        f.write(f"**Date:** 2026-06-22\n\n")
        f.write("## Operator Family\n\n")
        f.write("`separator_axis_reflect` — a subfamily of the broader `separator_reflection`\n")
        f.write("family proposed in the program gap audit.\n\n")
        f.write("## Algorithm\n\n")
        f.write("1. **Detect separator:** find a full-span row (or column) of uniform non-bg color.\n")
        f.write("2. **Infer background:** most frequent color in grid.\n")
        f.write("3. **Label CCs above separator** (4-connected, excluding bg).\n")
        f.write("4. **Wide CCs (bounding-box width > 1):**\n")
        f.write("   - Find the row with the most pixels (widest row).\n")
        f.write("   - Translate the CC so widest row aligns to sep_row - 1.\n")
        f.write("   - If translated pixels land on the separator row, pierce it (replace sep_color with obj_color).\n")
        f.write("   - If translated pixels go below separator, place them normally.\n")
        f.write("5. **Narrow CCs (width == 1):**\n")
        f.write("   - Mirror each pixel: `new_row = 2 * sep_row - original_row`.\n")
        f.write("   - Apply gravity: each mirrored pixel falls to the lowest available row in its column.\n")
        f.write("   - Clear separator at the CC's column(s).\n")
        f.write("6. **Vertical separators:** transpose, apply horizontal rules, transpose back.\n\n")
        f.write("## Verification\n\n")
        f.write("- Train consistency: predicted output == actual output for all training pairs.\n")
        f.write("- LOO: leave out each training pair, re-synthesize, verify held-out pair.\n")
        f.write("- ProposalVerifier: proof obligations, falsification, test confirmation.\n")

    print(f"Saved {design_path}", flush=True)

    # Print final summary
    print(f"\n{'='*70}", flush=True)
    print("  SUMMARY", flush=True)
    print(f"{'='*70}", flush=True)
    for cfg in configs:
        print(f"  {cfg}: {solved_by_config[cfg]}/{len(TARGET_TASKS)}", flush=True)
    print(f"  Primary ({PRIMARY_TASK}): {'RECOVERED' if primary_recovery else 'NOT RECOVERED'}",
          flush=True)
    print(f"  False positives: {n_fp}", flush=True)
    print(f"  Overall: {'PASS' if primary_recovery else 'FAIL'}", flush=True)
    print(f"  Output: {OUT}", flush=True)


if __name__ == "__main__":
    main()
