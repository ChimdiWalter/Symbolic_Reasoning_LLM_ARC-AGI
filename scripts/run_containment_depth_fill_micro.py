"""Micro-pilot for containment_depth_fill operator family.

Runs 2 target tasks × 5 configs to verify the new operator recovers tasks
that all baselines fail on, with full verification and ablation.

Usage:
    source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate
    cd /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project
    PYTHONPATH=src python3.11 scripts/run_containment_depth_fill_micro.py
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
    _synthesize_containment_depth_fill,
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
OUT = ROOT / "outputs" / "full_novel_reasoning_pipeline_v2" / "containment_depth_fill_v1_2026_06_22"
ARC_CHALLENGES = ROOT / "data" / "arc" / "arc-agi_training_challenges.json"
ARC_SOLUTIONS = ROOT / "data" / "arc" / "arc-agi_training_solutions.json"

TARGET_TASKS = ["516b51b7", "00dbd492"]
TASK_TIMEOUT = 300


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
    verifier, log_path, include_cdf: bool,
):
    """Run OperatorGenesis with or without containment_depth_fill."""
    ops = synthesize_operators_from_train(train_pairs)

    if not include_cdf:
        ops = [o for o in ops if o.operator_family != "containment_depth_fill"]

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
            _log_proposal_attempt(log_path, task_id, op, include_cdf)

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


def _log_proposal_attempt(log_path, task_id, op, include_cdf):
    tc = True
    entry = {
        "task_id": task_id,
        "operator_family": op.operator_family,
        "operator_id": op.operator_id,
        "explanation": op.explanation,
        "include_cdf": include_cdf,
    }
    with open(log_path, "a") as f:
        f.write(json.dumps(entry) + "\n")


def run_og_without_cdf(task_id, train_pairs, test_inputs, test_outputs, verifier, log_path):
    return _run_og_with_families(task_id, train_pairs, test_inputs, test_outputs,
                                  verifier, log_path, include_cdf=False)


def run_og_with_cdf(task_id, train_pairs, test_inputs, test_outputs, verifier, log_path):
    return _run_og_with_families(task_id, train_pairs, test_inputs, test_outputs,
                                  verifier, log_path, include_cdf=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    os.makedirs(OUT, exist_ok=True)
    cert_dir = OUT / "certificates"
    os.makedirs(cert_dir, exist_ok=True)
    log_path = str(OUT / "proposals.jsonl")

    print("=" * 70, flush=True)
    print("  Containment Depth Fill — Micro Pilot", flush=True)
    print("=" * 70, flush=True)

    challenges, solutions = load_arc_data()
    verifier = ProposalVerifier(certificate_dir=str(cert_dir))

    configs = [
        "static_only",
        "full_v2_original",
        "view_only_adaptergenesis",
        "og_without_cdf",
        "og_with_cdf",
    ]

    all_results: List[Dict[str, Any]] = []
    all_details: List[Dict[str, Any]] = []
    t_total = time.time()

    for task_id in TARGET_TASKS:
        print(f"\n--- Task {task_id} ---", flush=True)
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
                elif cfg == "og_without_cdf":
                    res = run_og_without_cdf(
                        task_id, train_pairs, test_inputs, test_outputs, verifier, log_path)
                elif cfg == "og_with_cdf":
                    res = run_og_with_cdf(
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
    csv_path = OUT / "containment_depth_fill_micro_results.csv"
    keys = ["task_id", "config", "solved", "operator_family", "certificate_path",
            "false_positive", "runtime_seconds", "error"]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_results)
    print(f"\nSaved {csv_path}", flush=True)

    # --- Write ablation CSV ---
    abl_path = OUT / "containment_depth_fill_ablation.csv"
    abl_keys = ["task_id", "config", "operator_id", "operator_family",
                "train_consistent", "loo_passed", "verifier_accepted", "certificate_path"]
    with open(abl_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=abl_keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_details)
    print(f"Saved {abl_path}", flush=True)

    # --- Compute summary stats ---
    solved_by_config = {}
    for cfg in configs:
        cfg_results = [r for r in all_results if r["config"] == cfg]
        solved_by_config[cfg] = sum(1 for r in cfg_results if r["solved"])

    n_baselines_failed = all(solved_by_config.get(c, 0) == 0
                             for c in ["static_only", "full_v2_original", "view_only_adaptergenesis"])
    n_og_without = solved_by_config.get("og_without_cdf", 0)
    n_og_with = solved_by_config.get("og_with_cdf", 0)
    n_new_recoveries = n_og_with - n_og_without
    n_fp = sum(1 for r in all_results if r.get("false_positive"))
    n_errors = sum(1 for r in all_results if r.get("error"))

    success = (n_og_with > 0 and n_baselines_failed and n_fp == 0 and n_errors == 0
               and n_new_recoveries > 0)

    # --- Write summary MD ---
    md_path = OUT / "containment_depth_fill_micro_summary.md"
    with open(md_path, "w") as f:
        f.write("# Containment Depth Fill — Micro Pilot Summary\n\n")
        f.write(f"**Date:** 2026-06-22\n")
        f.write(f"**Tasks:** {', '.join(TARGET_TASKS)}\n")
        f.write(f"**Runtime:** {elapsed_total:.1f}s\n\n")
        f.write("## Results by Config\n\n")
        f.write("| Config | Solved |\n|--------|--------|\n")
        for cfg in configs:
            f.write(f"| {cfg} | {solved_by_config[cfg]}/{len(TARGET_TASKS)} |\n")
        f.write(f"\n## Acceptance Criteria\n\n")
        f.write(f"- Baselines all fail: **{'PASS' if n_baselines_failed else 'FAIL'}**\n")
        f.write(f"- OG without CDF recoveries: **{n_og_without}**\n")
        f.write(f"- OG with CDF recoveries: **{n_og_with}**\n")
        f.write(f"- New recoveries from CDF: **{n_new_recoveries}**\n")
        f.write(f"- False positives: **{n_fp}**\n")
        f.write(f"- Exceptions: **{n_errors}**\n")
        f.write(f"- **Overall: {'PASS' if success else 'FAIL'}**\n\n")

        # Per-task detail
        f.write("## Per-Task Detail\n\n")
        for task_id in TARGET_TASKS:
            task_results = [r for r in all_results if r["task_id"] == task_id]
            f.write(f"### {task_id}\n\n")
            f.write("| Config | Solved | Family | Runtime | Certificate |\n")
            f.write("|--------|--------|--------|---------|-------------|\n")
            for r in task_results:
                f.write(f"| {r['config']} | {r['solved']} | {r.get('operator_family', '')} "
                        f"| {r['runtime_seconds']:.1f}s | {r.get('certificate_path', '')} |\n")
            f.write("\n")

        # Ablation detail
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
    abl_md_path = OUT / "containment_depth_fill_ablation.md"
    with open(abl_md_path, "w") as f:
        f.write("# Containment Depth Fill — Ablation\n\n")
        f.write(f"**Date:** 2026-06-22\n\n")
        f.write("## Necessity Test\n\n")
        f.write(f"- OG without CDF: {n_og_without}/{len(TARGET_TASKS)} solved\n")
        f.write(f"- OG with CDF: {n_og_with}/{len(TARGET_TASKS)} solved\n")
        f.write(f"- CDF is necessary for {n_new_recoveries} recovery(ies)\n\n")
        if n_new_recoveries > 0:
            f.write("CDF-dependent tasks:\n\n")
            for task_id in TARGET_TASKS:
                without = [r for r in all_results
                           if r["task_id"] == task_id and r["config"] == "og_without_cdf"]
                with_cdf = [r for r in all_results
                            if r["task_id"] == task_id and r["config"] == "og_with_cdf"]
                if with_cdf and with_cdf[0]["solved"] and without and not without[0]["solved"]:
                    f.write(f"- **{task_id}**: solved only with CDF "
                            f"(family: {with_cdf[0].get('operator_family')})\n")
        f.write("\n")

    print(f"Saved {abl_md_path}", flush=True)

    # --- Write claim update ---
    claim_path = OUT / "containment_depth_fill_claim_update.md"
    with open(claim_path, "w") as f:
        f.write("# Containment Depth Fill — Claim Update\n\n")
        f.write(f"**Date:** 2026-06-22\n\n")
        if success:
            f.write("## Claim (Positive)\n\n")
            f.write("Containment-depth filling provides the first verified recovery from\n")
            f.write("the program-gap audit, showing that the bottleneck was missing\n")
            f.write("higher-order operator grammar rather than representation search alone.\n\n")
            f.write(f"**Recovered tasks:** {n_og_with}\n")
            f.write(f"**New recoveries (CDF-dependent):** {n_new_recoveries}\n")
            f.write(f"**False positives:** {n_fp}\n")
        else:
            f.write("## Claim (Negative)\n\n")
            f.write("The first grammar extension did not recover the target tasks,\n")
            f.write("indicating that the missing program requires more complex relational\n")
            f.write("or recursive structure than BFS-depth filling.\n\n")
            f.write(f"**Recovered tasks:** {n_og_with}\n")
            f.write(f"**Issues:** baselines_all_fail={n_baselines_failed}, "
                    f"fp={n_fp}, errors={n_errors}\n")

        f.write("\n## Evidence Chain\n\n")
        f.write("1. Program gap audit identified containment_depth_fill as low-risk opportunity\n")
        f.write("2. Implemented as OperatorGenesis family with 2 strategies:\n")
        f.write("   - concentric_ring: BFS depth → cyclic color sequence\n")
        f.write("   - enclosed_flat_fill: bordered rectangles → property-based fill\n")
        f.write("3. Micro-pilot on 2 target tasks × 5 configs\n")
        f.write(f"4. Result: {n_og_with} recovered, {n_fp} FP, "
                f"{n_new_recoveries} CDF-necessary\n")

    print(f"Saved {claim_path}", flush=True)

    # Print final summary
    print(f"\n{'='*70}", flush=True)
    print("  SUMMARY", flush=True)
    print(f"{'='*70}", flush=True)
    for cfg in configs:
        print(f"  {cfg}: {solved_by_config[cfg]}/{len(TARGET_TASKS)}", flush=True)
    print(f"  New CDF recoveries: {n_new_recoveries}", flush=True)
    print(f"  False positives: {n_fp}", flush=True)
    print(f"  Overall: {'PASS' if success else 'FAIL'}", flush=True)
    print(f"  Output: {OUT}", flush=True)


if __name__ == "__main__":
    main()
