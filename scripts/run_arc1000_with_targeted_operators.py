"""Full ARC-1000 rerun with four targeted operator families integrated.

Verifies that the accounting-supported 44/1000 total holds under a full
integrated pipeline run with all four new operator families
(containment_depth_fill, separator_axis_reflect, separator_region_fill,
separator_track_move) enabled in the OperatorGenesis registry.

Same verifier/certificate/false-positive logic as the stable v2 baseline.
No test-output leakage during synthesis. No weakened ProposalVerifier.

Usage:
    source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate
    cd /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project
    PYTHONPATH=src python3.11 scripts/run_arc1000_with_targeted_operators.py
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

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from reasoning_project.adaptive_orchestrator import (
    GatedAdaptiveReasoningOrchestrator,
    OrchestratorConfig,
)
from reasoning_project.arc_adapter import load_arc_tasks

ARC_ROOT = Path(__file__).parent.parent / "data" / "arc"
PROJECT_ROOT = Path(__file__).parent.parent

OUTPUT_DIR = str(PROJECT_ROOT / "outputs" / "full_novel_reasoning_pipeline_v2" /
                 "arc1000_with_targeted_operators_2026_06_25")
CHECKPOINT_PATH = os.path.join(OUTPUT_DIR, "progress.jsonl")
CERT_DIR = os.path.join(OUTPUT_DIR, "certificates")

BASELINE_PROGRESS = str(PROJECT_ROOT / "outputs" / "full_novel_reasoning_pipeline_v2" /
                        "arc1000_after_stable_baseline_2026_06_16" / "progress.jsonl")

KNOWN_RECOVERIES = {
    "516b51b7": "containment_depth_fill",
    "84ba50d3": "separator_axis_reflect",
    "332202d5": "separator_region_fill",
    "5168d44c": "separator_track_move",
}

BASELINE_40 = {
    "00d62c1b", "08ed6ac7", "0b148d64", "1c786137", "1e0a9b12",
    "1f85a75f", "23b5c85d", "2a5f8217", "358ba94e", "3906de3d",
    "4347f46a", "496994bd", "50cb2852", "56ff96f3", "67385a82",
    "72ca375d", "810b9b61", "88a62173", "92e50de0", "9565186b",
    "a48eeaf7", "a5313dff", "a740d043", "ae58858e", "aedd82e4",
    "b1948b0a", "b2862040", "bb43febb", "be94b721", "c8f0f002",
    "cd3c21df", "d89b689b", "d9fac9be", "ddf7fa4f", "e0fb7511",
    "e98196ab", "e9ac8c9e", "ea32f347", "f25ffba3", "f5aa3634",
}


def load_v1_results(path: str = "outputs/full_arc1000_novel_pipeline/progress.jsonl") -> Dict[str, Dict]:
    results = {}
    if not os.path.exists(path):
        return results
    with open(path) as f:
        for line in f:
            if line.strip():
                row = json.loads(line)
                row["solved"] = (
                    row.get("final_config_that_solved") is not None or
                    row.get("operator_promoted", False) or
                    row.get("solved_by_static", False)
                )
                results[row.get("task_id", "")] = row
    return results


def load_checkpoint() -> set:
    completed = set()
    if os.path.exists(CHECKPOINT_PATH):
        with open(CHECKPOINT_PATH) as f:
            for line in f:
                if line.strip():
                    row = json.loads(line)
                    completed.add(row.get("task_id", ""))
    return completed


def main():
    print("=" * 70)
    print("  ARC-1000 Rerun with Targeted Operator Families")
    print(f"  {datetime.now().isoformat()}")
    print("=" * 70)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(CERT_DIR, exist_ok=True)

    print("\nLoading ARC tasks...")
    arc_task_list = load_arc_tasks(ARC_ROOT)
    tasks = {t.task_id: t for t in arc_task_list}
    task_ids = sorted(tasks.keys())
    print(f"  Loaded {len(task_ids)} tasks")

    print("\nLoading v1 results...")
    v1_results = load_v1_results()
    print(f"  Loaded {len(v1_results)} v1 results")

    completed = load_checkpoint()
    print(f"  Resuming: {len(completed)} tasks already completed")

    remaining = [tid for tid in task_ids if tid not in completed]
    print(f"  Remaining: {len(remaining)} tasks")
    print(f"  Known recoveries: {list(KNOWN_RECOVERIES.keys())}")
    print(f"  Baseline 40: {len(BASELINE_40)} tasks")

    config = OrchestratorConfig(
        timeout_per_task=420.0,
        output_dir=OUTPUT_DIR,
    )
    orch = GatedAdaptiveReasoningOrchestrator(config)

    solved_count = 0
    fp_count = 0
    new_solve_count = 0
    cert_count = 0
    error_count = 0
    t_start = time.time()

    with open(CHECKPOINT_PATH, "a") as progress_f:
        for i, task_id in enumerate(remaining):
            task = tasks[task_id]
            train_pairs = [(ex.input_grid, ex.output_grid)
                           for ex in task.train if ex.output_grid is not None]
            test_inputs = [ex.input_grid for ex in task.test]
            test_outputs = ([ex.output_grid for ex in task.test
                             if ex.output_grid is not None] or None)

            t0 = time.time()
            error_msg = None
            try:
                trace = orch.solve_task(task_id, train_pairs,
                                        test_inputs, test_outputs)
            except Exception as e:
                tb = traceback.format_exc()
                error_msg = f"{type(e).__name__}: {e}"
                print(f"  EXCEPTION on {task_id}: {error_msg}", flush=True)
                print(tb[:500], flush=True)
                error_count += 1
                trace = None

            elapsed_task = time.time() - t0

            v1_solved = v1_results.get(task_id, {}).get("solved", False)

            if trace is not None:
                v2_solved = trace.final_status == "solved"
                is_fp = (trace.verification.false_positive
                         if trace.verification else False)
                has_cert = (trace.verification.certificate_path is not None
                            if trace.verification else False)
                final_status = trace.final_status
                op_family = (trace.selected_proposal.operator_family
                             if trace.selected_proposal else None)
                mod_source = (trace.selected_proposal.module_name
                              if trace.selected_proposal else None)
                loo = (trace.verification.loo_passed
                       if trace.verification else None)
                proof_ob = (trace.verification.proof_obligations_passed
                            if trace.verification else None)
                falsif = (trace.verification.falsification_passed
                          if trace.verification else None)
                cert_path = (trace.verification.certificate_path
                             if trace.verification else None)
                reject_reason = (trace.verification.rejection_reason
                                 if trace.verification and not trace.verification.accepted
                                 else None)
                triggered = ",".join(trace.triggered_modules)
                skipped = json.dumps(trace.skipped_modules)
                runtime = trace.runtime_seconds
            else:
                v2_solved = False
                is_fp = False
                has_cert = False
                final_status = "error"
                op_family = None
                mod_source = None
                loo = None
                proof_ob = None
                falsif = None
                cert_path = None
                reject_reason = error_msg
                triggered = ""
                skipped = "{}"
                runtime = elapsed_task

            if v2_solved:
                solved_count += 1
            if is_fp:
                fp_count += 1
            if v2_solved and not v1_solved:
                new_solve_count += 1
            if has_cert:
                cert_count += 1

            in_baseline_40 = task_id in BASELINE_40
            is_targeted_recovery = task_id in KNOWN_RECOVERIES
            expected_recovery_family = KNOWN_RECOVERIES.get(task_id)

            row = {
                "task_id": task_id,
                "v1_solved": v1_solved,
                "v2_solved": v2_solved,
                "new_solve": v2_solved and not v1_solved,
                "domain": "arc",
                "modules_triggered": triggered,
                "modules_skipped": skipped,
                "adapter_genesis_used": "adapter_genesis" in triggered,
                "manifold_memory_used": "manifold_memory" in triggered,
                "near_solved_memory_used": "near_solved_memory" in triggered,
                "operator_memory_used": "operator_memory" in triggered,
                "neural_advisory_used": "neural_advisory" in triggered,
                "domain_morphism_used": "domain_morphism" in triggered,
                "frontier_operator_used": "frontier_operators" in triggered,
                "property_expansion_used": "property_expansion" in triggered,
                "operator_family": op_family,
                "module_source": mod_source,
                "LOO_passed": loo,
                "proof_obligations_passed": proof_ob,
                "falsification_passed": falsif,
                "certificate_emitted": has_cert,
                "certificate_path": cert_path,
                "false_positive": is_fp,
                "runtime_seconds": round(runtime, 2),
                "failure_reason": reject_reason or final_status,
                "in_baseline_40": in_baseline_40,
                "is_targeted_recovery": is_targeted_recovery,
                "expected_recovery_family": expected_recovery_family,
                "error": error_msg,
            }

            progress_f.write(json.dumps(row) + "\n")
            progress_f.flush()

            total_done = len(completed) + i + 1
            status_tag = ""
            if v2_solved:
                status_tag = f" SOLVED [{op_family}]"
            elif is_fp:
                status_tag = " FP_REJECTED"
            elif error_msg:
                status_tag = f" ERROR"

            if (i + 1) % 10 == 0 or v2_solved or is_fp or error_msg:
                print(f"[{total_done}/1000] {task_id} "
                      f"({runtime:.1f}s){status_tag}", flush=True)

            if (i + 1) % 100 == 0:
                elapsed = time.time() - t_start
                print(f"    -- checkpoint: {solved_count} solved, "
                      f"{new_solve_count} new, {fp_count} FP, "
                      f"{error_count} errors, {elapsed:.0f}s --", flush=True)

    elapsed_total = time.time() - t_start

    # ---- Post-run analysis ----
    print(f"\n{'='*70}")
    print(f"  POST-RUN ANALYSIS")
    print(f"{'='*70}", flush=True)

    all_rows = []
    with open(CHECKPOINT_PATH) as f:
        for line in f:
            if line.strip():
                all_rows.append(json.loads(line))

    total_solved = sum(1 for r in all_rows if r.get("v2_solved"))
    total_fp = sum(1 for r in all_rows if r.get("false_positive"))
    total_errors = sum(1 for r in all_rows if r.get("error"))
    total_certs = sum(1 for r in all_rows if r.get("certificate_emitted"))

    # Check baseline preservation
    baseline_preserved = []
    baseline_regressed = []
    for tid in BASELINE_40:
        r = next((r for r in all_rows if r["task_id"] == tid), None)
        if r and r.get("v2_solved"):
            baseline_preserved.append(tid)
        else:
            baseline_regressed.append(tid)

    # Check targeted recoveries
    recovery_results = {}
    for tid, expected_fam in KNOWN_RECOVERIES.items():
        r = next((r for r in all_rows if r["task_id"] == tid), None)
        if r:
            recovery_results[tid] = {
                "solved": r.get("v2_solved", False),
                "operator_family": r.get("operator_family"),
                "correct_family": r.get("operator_family") == expected_fam,
                "certificate": r.get("certificate_emitted", False),
            }
        else:
            recovery_results[tid] = {
                "solved": False, "operator_family": None,
                "correct_family": False, "certificate": False,
            }

    recoveries_passing = sum(1 for v in recovery_results.values()
                             if v["solved"] and v["correct_family"])

    # New solves beyond baseline+recoveries
    new_beyond = []
    for r in all_rows:
        if (r.get("v2_solved") and
                r["task_id"] not in BASELINE_40 and
                r["task_id"] not in KNOWN_RECOVERIES):
            new_beyond.append(r)

    # Determine overall pass
    all_baseline_preserved = len(baseline_regressed) == 0
    all_recoveries_pass = recoveries_passing == 4
    no_fp = total_fp == 0
    overall_pass = all_baseline_preserved and all_recoveries_pass and no_fp

    print(f"  Total tasks: {len(all_rows)}")
    print(f"  Total solved: {total_solved}")
    print(f"  Baseline preserved: {len(baseline_preserved)}/40")
    print(f"  Baseline regressions: {len(baseline_regressed)}")
    if baseline_regressed:
        for tid in baseline_regressed:
            print(f"    REGRESSED: {tid}")
    print(f"  Targeted recoveries: {recoveries_passing}/4")
    for tid, res in recovery_results.items():
        tag = "PASS" if res["solved"] and res["correct_family"] else "FAIL"
        print(f"    {tid} ({KNOWN_RECOVERIES[tid]}): "
              f"solved={res['solved']}, family={res['operator_family']}, "
              f"cert={res['certificate']} -> {tag}")
    print(f"  New solves beyond 44: {len(new_beyond)}")
    for r in new_beyond:
        print(f"    {r['task_id']}: {r.get('operator_family')}")
    print(f"  False positives: {total_fp}")
    print(f"  Errors: {total_errors}")
    print(f"  Certificates: {total_certs}")
    print(f"  Wall time: {elapsed_total:.0f}s ({elapsed_total/3600:.1f}h)")
    print(f"  Overall: {'PASS' if overall_pass else 'FAIL'}")
    print(f"{'='*70}", flush=True)

    # ---- Write summary.json ----
    summary = {
        "date": datetime.now().isoformat(),
        "total_tasks": len(all_rows),
        "total_solved": total_solved,
        "solve_rate": total_solved / max(len(all_rows), 1),
        "baseline_preserved": len(baseline_preserved),
        "baseline_regressed": len(baseline_regressed),
        "baseline_regressions": baseline_regressed,
        "targeted_recoveries_passing": recoveries_passing,
        "targeted_recovery_detail": recovery_results,
        "new_solves_beyond_44": len(new_beyond),
        "new_solve_ids": [r["task_id"] for r in new_beyond],
        "false_positives": total_fp,
        "errors": total_errors,
        "certificates_emitted": total_certs,
        "wall_time_seconds": round(elapsed_total, 1),
        "overall_pass": overall_pass,
    }
    with open(os.path.join(OUTPUT_DIR, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    print(f"Saved summary.json", flush=True)

    # ---- Write v2_baseline_vs_targeted_operator_comparison.csv ----
    comp_path = os.path.join(OUTPUT_DIR, "v2_baseline_vs_targeted_operator_comparison.csv")
    with open(comp_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["task_id", "baseline_solved", "rerun_solved",
                     "rerun_operator_family", "rerun_module_source",
                     "status"])
        for r in sorted(all_rows, key=lambda x: x["task_id"]):
            tid = r["task_id"]
            bl = tid in BASELINE_40
            rr = r.get("v2_solved", False)
            if bl and rr:
                status = "preserved"
            elif bl and not rr:
                status = "REGRESSION"
            elif not bl and rr and tid in KNOWN_RECOVERIES:
                status = "targeted_recovery"
            elif not bl and rr:
                status = "new_solve"
            else:
                status = "unsolved"
            w.writerow([tid, bl, rr,
                        r.get("operator_family", ""),
                        r.get("module_source", ""),
                        status])
    print(f"Saved v2_baseline_vs_targeted_operator_comparison.csv", flush=True)

    # ---- Write new_solve_table.csv ----
    ns_path = os.path.join(OUTPUT_DIR, "new_solve_table.csv")
    new_solves = [r for r in all_rows
                  if r.get("v2_solved") and r["task_id"] not in BASELINE_40]
    with open(ns_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["task_id", "operator_family", "module_source",
                     "is_targeted_recovery", "expected_family",
                     "LOO_passed", "proof_obligations_passed",
                     "falsification_passed", "certificate_emitted",
                     "runtime_seconds"])
        for r in sorted(new_solves, key=lambda x: x["task_id"]):
            w.writerow([
                r["task_id"], r.get("operator_family"), r.get("module_source"),
                r["task_id"] in KNOWN_RECOVERIES,
                KNOWN_RECOVERIES.get(r["task_id"], ""),
                r.get("LOO_passed"), r.get("proof_obligations_passed"),
                r.get("falsification_passed"), r.get("certificate_emitted"),
                r.get("runtime_seconds"),
            ])
    print(f"Saved new_solve_table.csv", flush=True)

    # ---- Write regression_table.csv ----
    reg_path = os.path.join(OUTPUT_DIR, "regression_table.csv")
    with open(reg_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["task_id", "baseline_solved", "rerun_solved",
                     "failure_reason", "error"])
        for tid in sorted(baseline_regressed):
            r = next((r for r in all_rows if r["task_id"] == tid), {})
            w.writerow([tid, True, r.get("v2_solved", False),
                        r.get("failure_reason", ""), r.get("error", "")])
    print(f"Saved regression_table.csv", flush=True)

    # ---- Write false_positive_audit.csv ----
    fpa_path = os.path.join(OUTPUT_DIR, "false_positive_audit.csv")
    fps = [r for r in all_rows if r.get("false_positive")]
    with open(fpa_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["task_id", "operator_family", "module_source",
                     "failure_reason"])
        for r in fps:
            w.writerow([r["task_id"], r.get("operator_family"),
                        r.get("module_source"), r.get("failure_reason")])
    print(f"Saved false_positive_audit.csv", flush=True)

    # ---- Write targeted_recovery_reproduction.csv ----
    trr_path = os.path.join(OUTPUT_DIR, "targeted_recovery_reproduction.csv")
    with open(trr_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["task_id", "expected_family", "solved",
                     "actual_family", "correct_family",
                     "LOO_passed", "proof_obligations_passed",
                     "falsification_passed", "certificate_emitted",
                     "certificate_path", "runtime_seconds", "PASS"])
        for tid, expected_fam in KNOWN_RECOVERIES.items():
            r = next((r for r in all_rows if r["task_id"] == tid), {})
            res = recovery_results.get(tid, {})
            passed = res.get("solved") and res.get("correct_family")
            w.writerow([
                tid, expected_fam,
                r.get("v2_solved", False),
                r.get("operator_family", ""),
                res.get("correct_family", False),
                r.get("LOO_passed"),
                r.get("proof_obligations_passed"),
                r.get("falsification_passed"),
                r.get("certificate_emitted"),
                r.get("certificate_path", ""),
                r.get("runtime_seconds"),
                passed,
            ])
    print(f"Saved targeted_recovery_reproduction.csv", flush=True)

    # ---- Write summary.md ----
    md_path = os.path.join(OUTPUT_DIR, "summary.md")
    with open(md_path, "w") as f:
        f.write("# ARC-1000 Rerun with Targeted Operator Families\n\n")
        f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d')}\n")
        f.write(f"**Wall time:** {elapsed_total:.0f}s ({elapsed_total/3600:.1f}h)\n")
        f.write(f"**Overall:** {'PASS' if overall_pass else 'FAIL'}\n\n")

        f.write("## Results\n\n")
        f.write(f"| Metric | Value |\n|--------|-------|\n")
        f.write(f"| Total tasks | {len(all_rows)} |\n")
        f.write(f"| Total solved | {total_solved} |\n")
        f.write(f"| Solve rate | {total_solved*100/max(len(all_rows),1):.1f}% |\n")
        f.write(f"| Baseline preserved | {len(baseline_preserved)}/40 |\n")
        f.write(f"| Baseline regressions | {len(baseline_regressed)} |\n")
        f.write(f"| Targeted recoveries | {recoveries_passing}/4 |\n")
        f.write(f"| New solves beyond 44 | {len(new_beyond)} |\n")
        f.write(f"| False positives | {total_fp} |\n")
        f.write(f"| Errors | {total_errors} |\n")
        f.write(f"| Certificates emitted | {total_certs} |\n\n")

        f.write("## Baseline Preservation\n\n")
        if baseline_regressed:
            f.write("**REGRESSIONS DETECTED:**\n\n")
            for tid in baseline_regressed:
                r = next((r for r in all_rows if r["task_id"] == tid), {})
                f.write(f"- `{tid}`: {r.get('failure_reason', 'unknown')}\n")
            f.write("\n")
        else:
            f.write("All 40 baseline solves preserved.\n\n")

        f.write("## Targeted Recovery Reproduction\n\n")
        f.write("| task_id | expected_family | solved | actual_family | "
                "correct | certificate | PASS |\n")
        f.write("|---------|-----------------|--------|---------------|"
                "---------|-------------|------|\n")
        for tid, expected_fam in KNOWN_RECOVERIES.items():
            res = recovery_results[tid]
            tag = "PASS" if res["solved"] and res["correct_family"] else "FAIL"
            f.write(f"| {tid} | {expected_fam} | {res['solved']} | "
                    f"{res['operator_family'] or ''} | "
                    f"{res['correct_family']} | {res['certificate']} | "
                    f"**{tag}** |\n")
        f.write("\n")

        if new_beyond:
            f.write("## New Solves Beyond 44\n\n")
            f.write("| task_id | operator_family | module_source |\n")
            f.write("|---------|-----------------|---------------|\n")
            for r in new_beyond:
                f.write(f"| {r['task_id']} | {r.get('operator_family', '')} "
                        f"| {r.get('module_source', '')} |\n")
            f.write("\n")

        if fps:
            f.write("## False Positives\n\n")
            for r in fps:
                f.write(f"- `{r['task_id']}`: {r.get('operator_family', '')} "
                        f"({r.get('failure_reason', '')})\n")
            f.write("\n")

        f.write("## Operator Family Breakdown\n\n")
        fam_counts: Dict[str, int] = {}
        for r in all_rows:
            if r.get("v2_solved"):
                fam = r.get("operator_family", "unknown")
                fam_counts[fam] = fam_counts.get(fam, 0) + 1
        f.write("| Family | Count |\n|--------|-------|\n")
        for fam, cnt in sorted(fam_counts.items(), key=lambda x: -x[1]):
            f.write(f"| {fam} | {cnt} |\n")
        f.write("\n")

    print(f"Saved summary.md", flush=True)

    # ---- Write claim_update_arc1000_targeted_operators.md ----
    claim_path = os.path.join(OUTPUT_DIR,
                              "claim_update_arc1000_targeted_operators.md")
    with open(claim_path, "w") as f:
        f.write("# ARC-1000 Targeted Operator Integration — Claim Update\n\n")
        f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d')}\n\n")

        if overall_pass:
            f.write("## Claim (Positive)\n\n")
            f.write("After integrating the four program-gap-guided operator "
                    "families into the full v2 pipeline, the ARC-1000 training "
                    "run preserves the original 40 verified solves and "
                    "reproduces the four targeted recoveries, yielding an "
                    f"official integrated score of {total_solved}/1000 with "
                    "zero accepted false positives.\n\n")
        else:
            f.write("## Claim (Negative)\n\n")
            f.write("The four targeted recoveries are individually and jointly "
                    "verified, but the full integrated ARC-1000 rerun revealed "
                    "integration failures; official score remains the previous "
                    "verified baseline until repaired.\n\n")
            if baseline_regressed:
                f.write(f"- Regressions: {len(baseline_regressed)} "
                        f"({', '.join(baseline_regressed)})\n")
            if total_fp > 0:
                f.write(f"- False positives: {total_fp}\n")
            if recoveries_passing < 4:
                f.write(f"- Targeted recoveries: {recoveries_passing}/4\n")
            f.write("\n")

        f.write("## Evidence\n\n")
        f.write(f"- Tasks: {len(all_rows)}\n")
        f.write(f"- Solved: {total_solved}\n")
        f.write(f"- Baseline preserved: {len(baseline_preserved)}/40\n")
        f.write(f"- Targeted recoveries: {recoveries_passing}/4\n")
        f.write(f"- New beyond 44: {len(new_beyond)}\n")
        f.write(f"- False positives: {total_fp}\n")
        f.write(f"- Errors: {total_errors}\n")
        f.write(f"- Certificates: {total_certs}\n")
        f.write(f"- Wall time: {elapsed_total:.0f}s\n")

    print(f"Saved claim_update_arc1000_targeted_operators.md", flush=True)

    print(f"\n{'='*70}")
    print(f"  ARC-1000 RERUN WITH TARGETED OPERATORS COMPLETE")
    print(f"  Overall: {'PASS' if overall_pass else 'FAIL'}")
    print(f"  Solved: {total_solved}/1000")
    print(f"  Output: {OUTPUT_DIR}/")
    print(f"{'='*70}", flush=True)


if __name__ == "__main__":
    main()
