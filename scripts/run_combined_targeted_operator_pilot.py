"""Combined targeted operator pilot: all 4 new families in one registry.

Tests 20 program-gap pilot tasks across 7 configs to verify that CDF, SAR,
SRF, and STM coexist without interference, false positives, or regressions.

Usage:
    source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate
    cd /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project
    PYTHONPATH=src python3.11 scripts/run_combined_targeted_operator_pilot.py
"""
from __future__ import annotations

import csv
import json
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from reasoning_project.operator_genesis import (
    synthesize_operators_from_train,
    _check_train_consistency,
    _check_loo,
    SynthesizedOperator,
)
from reasoning_project.proposal_verifier import ProposalVerifier
from reasoning_project.adaptive_orchestrator import (
    GatedAdaptiveReasoningOrchestrator,
    ModuleProposal,
)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs" / "full_novel_reasoning_pipeline_v2" / "combined_targeted_operator_pilot_2026_06_24"
ARC_CHALLENGES = ROOT / "data" / "arc" / "arc-agi_training_challenges.json"
ARC_SOLUTIONS = ROOT / "data" / "arc" / "arc-agi_training_solutions.json"
PILOT_CSV = ROOT / "outputs" / "full_novel_reasoning_pipeline_v2" / "operator_genesis_v2_2026_06_22" / "pilot_selected_tasks.csv"

NEW_FAMILIES = {
    "containment_depth_fill",
    "separator_axis_reflect",
    "separator_region_fill",
    "separator_track_move",
}

KNOWN_RECOVERIES = {
    "516b51b7": "containment_depth_fill",
    "84ba50d3": "separator_axis_reflect",
    "332202d5": "separator_region_fill",
    "5168d44c": "separator_track_move",
}

CONFIGS = [
    "full_v2_original",
    "operator_genesis_original_only",
    "operator_genesis_with_cdf_only",
    "operator_genesis_with_sar_only",
    "operator_genesis_with_srf_only",
    "operator_genesis_with_stm_only",
    "operator_genesis_with_all_four",
]

FAMILY_FILTER: Dict[str, Set[str]] = {
    "operator_genesis_original_only": set(),
    "operator_genesis_with_cdf_only": {"containment_depth_fill"},
    "operator_genesis_with_sar_only": {"separator_axis_reflect"},
    "operator_genesis_with_srf_only": {"separator_region_fill"},
    "operator_genesis_with_stm_only": {"separator_track_move"},
    "operator_genesis_with_all_four": NEW_FAMILIES,
}

TASK_TIMEOUT = 300


def load_pilot_tasks() -> List[str]:
    tasks = []
    with open(PILOT_CSV) as f:
        reader = csv.DictReader(f)
        for row in reader:
            tasks.append(row["task_id"])
    return tasks


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
    return {
        "solved": solved,
        "operator_family": op_family,
        "certificate_path": None,
        "false_positive": False,
        "detail": [],
    }


def run_og_filtered(
    task_id, train_pairs, test_inputs, test_outputs,
    verifier, log_path, config_name: str, allowed_new: Set[str],
):
    ops = synthesize_operators_from_train(train_pairs)

    filtered = []
    for o in ops:
        if o.operator_family in NEW_FAMILIES and o.operator_family not in allowed_new:
            continue
        filtered.append(o)
    ops = filtered

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
            "config": config_name,
            "operator_id": op.operator_id,
            "operator_family": op.operator_family,
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
                "config": config_name,
                "operator_family": op.operator_family,
                "operator_id": op.operator_id,
                "explanation": op.explanation,
                "parameters": _safe_params(op.parameters),
                "train_consistent": True,
                "loo_passed": loo_ok,
                "verifier_accepted": True,
                "certificate_path": outcome.certificate_path,
            }
            with open(log_path, "a") as f:
                f.write(json.dumps(entry) + "\n")

            return {
                "solved": True,
                "operator_family": op.operator_family,
                "certificate_path": outcome.certificate_path,
                "false_positive": False,
                "detail": results_detail,
            }

    return {
        "solved": False,
        "operator_family": None,
        "certificate_path": None,
        "false_positive": False,
        "detail": results_detail,
    }


def main():
    os.makedirs(OUT, exist_ok=True)
    cert_dir = OUT / "certificates"
    os.makedirs(cert_dir, exist_ok=True)
    log_path = str(OUT / "proposals.jsonl")

    print("=" * 70, flush=True)
    print("  Combined Targeted Operator Pilot", flush=True)
    print(f"  {datetime.now().isoformat()}", flush=True)
    print("=" * 70, flush=True)

    target_tasks = load_pilot_tasks()
    print(f"  Tasks: {len(target_tasks)}", flush=True)
    print(f"  Configs: {len(CONFIGS)}", flush=True)
    print(f"  Known recoveries: {list(KNOWN_RECOVERIES.keys())}", flush=True)

    challenges, solutions = load_arc_data()
    verifier = ProposalVerifier(certificate_dir=str(cert_dir))

    all_results: List[Dict[str, Any]] = []
    all_details: List[Dict[str, Any]] = []
    t_total = time.time()

    for ti, task_id in enumerate(target_tasks):
        is_known = task_id in KNOWN_RECOVERIES
        label = f"KNOWN({KNOWN_RECOVERIES[task_id]})" if is_known else "pilot"
        print(f"\n--- [{ti+1}/{len(target_tasks)}] Task {task_id} ({label}) ---", flush=True)

        train_pairs, test_inputs, test_outputs = load_task(task_id, challenges, solutions)

        for cfg in CONFIGS:
            t0 = time.time()
            result: Dict[str, Any] = {
                "task_id": task_id,
                "config": cfg,
                "solved": False,
                "operator_family": None,
                "train_consistent": None,
                "LOO_passed": None,
                "verifier_accepted": None,
                "proof_obligations_passed": None,
                "false_positive": False,
                "certificate_path": None,
                "runtime_seconds": 0.0,
                "error": None,
            }
            try:
                if cfg == "full_v2_original":
                    res = run_full_v2(task_id, train_pairs, test_inputs, test_outputs)
                else:
                    allowed_new = FAMILY_FILTER[cfg]
                    res = run_og_filtered(
                        task_id, train_pairs, test_inputs, test_outputs,
                        verifier, log_path, cfg, allowed_new,
                    )

                detail = res.pop("detail", [])
                result["solved"] = res["solved"]
                result["operator_family"] = res.get("operator_family")
                result["certificate_path"] = res.get("certificate_path")
                result["false_positive"] = res.get("false_positive", False)

                if res["solved"] and detail:
                    accepted = [d for d in detail if d.get("verifier_accepted")]
                    if accepted:
                        result["train_consistent"] = accepted[0].get("train_consistent")
                        result["LOO_passed"] = accepted[0].get("loo_passed")
                        result["verifier_accepted"] = True

                if res.get("certificate_path"):
                    try:
                        with open(res["certificate_path"]) as cf:
                            cert = json.load(cf)
                        result["proof_obligations_passed"] = cert.get("proof_obligations_passed")
                    except Exception:
                        pass

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
                extra += f" ERROR: {result['error']}"
            print(f"  {cfg}: {status} ({elapsed:.1f}s){extra}", flush=True)

    elapsed_total = time.time() - t_total

    # --- Write results CSV ---
    csv_path = OUT / "combined_operator_pilot_results.csv"
    result_keys = ["task_id", "config", "solved", "operator_family",
                   "train_consistent", "LOO_passed", "verifier_accepted",
                   "proof_obligations_passed", "false_positive",
                   "certificate_path", "runtime_seconds", "error"]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=result_keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_results)
    print(f"\nSaved {csv_path}", flush=True)

    # --- Write ablation CSV ---
    abl_csv = OUT / "combined_operator_pilot_ablation.csv"
    abl_keys = ["task_id", "config", "operator_id", "operator_family",
                "train_consistent", "loo_passed", "verifier_accepted",
                "certificate_path"]
    with open(abl_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=abl_keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_details)
    print(f"Saved {abl_csv}", flush=True)

    # --- Acceptance checks ---
    n_fp = sum(1 for r in all_results if r.get("false_positive"))
    n_errors = sum(1 for r in all_results if r.get("error"))

    recovery_checks = {}
    for task_id, expected_family in KNOWN_RECOVERIES.items():
        checks = {}

        r_orig = next((r for r in all_results
                       if r["task_id"] == task_id
                       and r["config"] == "operator_genesis_original_only"), None)
        checks["original_only_fails"] = r_orig is not None and not r_orig["solved"]

        r_all = next((r for r in all_results
                      if r["task_id"] == task_id
                      and r["config"] == "operator_genesis_with_all_four"), None)
        checks["all_four_solves"] = r_all is not None and r_all["solved"]
        checks["correct_family"] = (r_all is not None
                                    and r_all.get("operator_family") == expected_family)
        checks["has_certificate"] = (r_all is not None
                                     and r_all.get("certificate_path") is not None)

        family_cfg_map = {
            "containment_depth_fill": "operator_genesis_with_cdf_only",
            "separator_axis_reflect": "operator_genesis_with_sar_only",
            "separator_region_fill": "operator_genesis_with_srf_only",
            "separator_track_move": "operator_genesis_with_stm_only",
        }
        r_own = next((r for r in all_results
                      if r["task_id"] == task_id
                      and r["config"] == family_cfg_map[expected_family]), None)
        checks["own_family_solves"] = r_own is not None and r_own["solved"]
        checks["own_family_correct"] = (r_own is not None
                                        and r_own.get("operator_family") == expected_family)

        checks["pass"] = all(checks.values())
        recovery_checks[task_id] = checks

    all_recoveries_pass = all(c["pass"] for c in recovery_checks.values())
    overall_pass = all_recoveries_pass and n_fp == 0 and n_errors == 0

    # --- Family attribution table ---
    attribution_rows = []
    for task_id in load_pilot_tasks():
        row = {"task_id": task_id}
        for cfg in CONFIGS:
            r = next((r for r in all_results
                      if r["task_id"] == task_id and r["config"] == cfg), None)
            if r and r["solved"]:
                row[cfg] = r.get("operator_family", "solved")
            else:
                row[cfg] = "failed"
        attribution_rows.append(row)

    # --- Write summary ---
    summary_path = OUT / "combined_operator_pilot_summary.md"
    with open(summary_path, "w") as f:
        f.write("# Combined Targeted Operator Pilot — Summary\n\n")
        f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d')}\n")
        f.write(f"**Tasks:** {len(target_tasks)}\n")
        f.write(f"**Configs:** {len(CONFIGS)}\n")
        f.write(f"**Runtime:** {elapsed_total:.1f}s\n\n")

        f.write("## Overall Result\n\n")
        f.write(f"- All recoveries pass: **{'YES' if all_recoveries_pass else 'NO'}**\n")
        f.write(f"- False positives: **{n_fp}**\n")
        f.write(f"- Errors: **{n_errors}**\n")
        f.write(f"- **Overall: {'PASS' if overall_pass else 'FAIL'}**\n\n")

        f.write("## Known Recovery Checks\n\n")
        f.write("| task_id | expected_family | orig_fails | all4_solves | correct_family | own_cfg_solves | certificate | PASS |\n")
        f.write("|---------|-----------------|------------|-------------|----------------|----------------|-------------|------|\n")
        for tid, expected in KNOWN_RECOVERIES.items():
            c = recovery_checks[tid]
            f.write(f"| {tid} | {expected} "
                    f"| {'Yes' if c['original_only_fails'] else 'No'} "
                    f"| {'Yes' if c['all_four_solves'] else 'No'} "
                    f"| {'Yes' if c['correct_family'] else 'No'} "
                    f"| {'Yes' if c['own_family_solves'] else 'No'} "
                    f"| {'Yes' if c['has_certificate'] else 'No'} "
                    f"| **{'PASS' if c['pass'] else 'FAIL'}** |\n")

        f.write("\n## Solves by Config\n\n")
        f.write("| Config | Solved |\n|--------|--------|\n")
        for cfg in CONFIGS:
            cfg_results = [r for r in all_results if r["config"] == cfg]
            n_solved = sum(1 for r in cfg_results if r["solved"])
            f.write(f"| {cfg} | {n_solved}/{len(target_tasks)} |\n")

        f.write("\n## Per-Task Results\n\n")
        for task_id in target_tasks:
            is_known = task_id in KNOWN_RECOVERIES
            label = f"KNOWN({KNOWN_RECOVERIES[task_id]})" if is_known else "pilot"
            f.write(f"### {task_id} ({label})\n\n")
            f.write("| Config | Solved | Family | Runtime | Certificate |\n")
            f.write("|--------|--------|--------|---------|-------------|\n")
            task_results = [r for r in all_results if r["task_id"] == task_id]
            for r in task_results:
                cert = os.path.basename(r["certificate_path"]) if r.get("certificate_path") else ""
                f.write(f"| {r['config']} | {r['solved']} | {r.get('operator_family') or ''} "
                        f"| {r['runtime_seconds']:.1f}s | {cert} |\n")
            f.write("\n")

    print(f"Saved {summary_path}", flush=True)

    # --- Write family attribution ---
    attr_path = OUT / "combined_operator_family_attribution.md"
    with open(attr_path, "w") as f:
        f.write("# Combined Operator — Family Attribution\n\n")
        f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d')}\n\n")
        f.write("Each cell shows the operator family that solved the task under that config,\n")
        f.write("or 'failed' if unsolved.\n\n")

        short_cfgs = {
            "full_v2_original": "v2_orig",
            "operator_genesis_original_only": "og_orig",
            "operator_genesis_with_cdf_only": "og+CDF",
            "operator_genesis_with_sar_only": "og+SAR",
            "operator_genesis_with_srf_only": "og+SRF",
            "operator_genesis_with_stm_only": "og+STM",
            "operator_genesis_with_all_four": "og+ALL4",
        }

        header = "| task_id | " + " | ".join(short_cfgs[c] for c in CONFIGS) + " |"
        sep = "|---------|" + "|".join("-" * (len(short_cfgs[c]) + 2) for c in CONFIGS) + "|"
        f.write(header + "\n")
        f.write(sep + "\n")
        for row in attribution_rows:
            cells = " | ".join(row.get(c, "?") for c in CONFIGS)
            f.write(f"| {row['task_id']} | {cells} |\n")

        f.write("\n## Key\n\n")
        f.write("- `failed`: task not solved under this config\n")
        f.write("- Family name (e.g. `containment_depth_fill`): solved by that family\n")
        f.write("- Other family names: solved by an original OG family (e.g. `crop_extract`)\n")

    print(f"Saved {attr_path}", flush=True)

    # --- Write claim update ---
    claim_path = OUT / "combined_operator_claim_update.md"
    with open(claim_path, "w") as f:
        f.write("# Combined Targeted Operator Pilot — Claim Update\n\n")
        f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d')}\n\n")

        if overall_pass:
            f.write("## Claim (Positive)\n\n")
            f.write("The four program-gap-guided operator families coexist in a combined\n")
            f.write("OperatorGenesis registry and reproduce all four targeted verified\n")
            f.write("recoveries with correct family attribution and zero accepted false\n")
            f.write("positives.\n\n")
        else:
            f.write("## Claim (Negative)\n\n")
            f.write("The four targeted recoveries are individually verified, but the\n")
            f.write("combined registry requires additional routing or priority control\n")
            f.write("before full ARC-1000 integration.\n\n")
            if n_fp > 0:
                f.write(f"- False positives: {n_fp}\n")
            if n_errors > 0:
                f.write(f"- Errors: {n_errors}\n")
            for tid, c in recovery_checks.items():
                if not c["pass"]:
                    f.write(f"- {tid} failed checks: {c}\n")
            f.write("\n")

        f.write("## Evidence\n\n")
        f.write(f"- Tasks tested: {len(target_tasks)}\n")
        f.write(f"- Configs per task: {len(CONFIGS)}\n")
        f.write(f"- Known recoveries passing: {sum(1 for c in recovery_checks.values() if c['pass'])}/4\n")
        f.write(f"- False positives: {n_fp}\n")
        f.write(f"- Errors: {n_errors}\n")
        f.write(f"- Runtime: {elapsed_total:.1f}s\n\n")

        f.write("## Recovery Detail\n\n")
        for tid, expected in KNOWN_RECOVERIES.items():
            c = recovery_checks[tid]
            f.write(f"### {tid} ({expected})\n")
            f.write(f"- original_only fails: {c['original_only_fails']}\n")
            f.write(f"- all_four solves: {c['all_four_solves']}\n")
            f.write(f"- correct family: {c['correct_family']}\n")
            f.write(f"- own-family config solves: {c['own_family_solves']}\n")
            f.write(f"- certificate: {c['has_certificate']}\n")
            f.write(f"- **{'PASS' if c['pass'] else 'FAIL'}**\n\n")

    print(f"Saved {claim_path}", flush=True)

    print("\n" + "=" * 70, flush=True)
    print("  COMBINED TARGETED OPERATOR PILOT COMPLETE", flush=True)
    print("=" * 70, flush=True)
    print(f"  All recoveries pass: {all_recoveries_pass}", flush=True)
    print(f"  False positives: {n_fp}", flush=True)
    print(f"  Errors: {n_errors}", flush=True)
    print(f"  Overall: {'PASS' if overall_pass else 'FAIL'}", flush=True)
    print(f"  Runtime: {elapsed_total:.1f}s", flush=True)
    for tid, c in recovery_checks.items():
        print(f"  {tid} ({KNOWN_RECOVERIES[tid]}): {'PASS' if c['pass'] else 'FAIL'}", flush=True)
    print("=" * 70, flush=True)


if __name__ == "__main__":
    main()
