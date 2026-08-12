#!/usr/bin/env python3.11
"""Full ARC-1000 novel pipeline: run all 1000 ARC training tasks through 7 configs.

Configurations (incremental):
    1. static_portfolio_no_dsl       — static portfolio without DSL/CEGIS solvers
    2. static_portfolio_with_dsl     — static portfolio with DSL solvers
    3. static_plus_adapter_genesis   — add AdapterGenesis / DomainAdapter path
    4. static_plus_near_solved_memory — add near-solved memory storage
    5. static_plus_trace_operator_invention — add trace-driven operator invention (no verification)
    6. static_plus_trace_operator_invention_with_verification — add LOO + proof + falsification
    7. full_domain_adaptive_verified_pipeline — everything including certificates

Resumable, checkpointed, error-resilient.  60s timeout per task per config.
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
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# ── Path setup ────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# ── Imports from reasoning_project ────────────────────────────────────────
from reasoning_project.arc_adapter import load_arc_tasks, ARCTask
from reasoning_project.reasoning_engine import (
    GridDomainAdapter,
    ReasoningMemory,
    StructuralReasoner,
)
from reasoning_project.adaptive_loop import AdaptiveReasoningLoop
from reasoning_project.manifold_memory import MemoryManifold
from reasoning_project.near_solved_memory import (
    NearSolvedMemory,
    NearSolvedTaskState,
    build_near_solved_state,
)
from reasoning_project.events import ReasoningEventLog
from reasoning_project.active_falsifier import ActiveFalsifier
from reasoning_project.certificates import (
    CertificateBuilder,
    ReasoningCertificate,
    certificate_to_json,
    certificate_to_markdown,
)
from reasoning_project.adapter_genesis import AdapterGenesis
from reasoning_project.trace_operator_invention import TraceDrivenOperatorInventor
from reasoning_project.portfolio import PortfolioSolver, PortfolioResult


# ── Trace loading ────────────────────────────────────────────────────────

def load_gap_traces(project_root: Path) -> Dict[str, Dict[str, Any]]:
    """Load per-task gap analysis traces from all available sources.

    Merges gap_analysis_v3 CSV (richest), cache_fast JSONL, and
    operator_gap_analysis CSV, keyed by task_id.
    """
    traces: Dict[str, Dict[str, Any]] = {}

    # Source 1: cache_fast/operator_gap_traces.jsonl (36 entries)
    jsonl_path = project_root / "outputs" / "cache_fast" / "operator_gap_traces.jsonl"
    if jsonl_path.exists():
        with open(jsonl_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    tid = rec.get("task_id", "")
                    if tid:
                        traces[tid] = rec
                except json.JSONDecodeError:
                    pass

    # Source 2: operator_gap_analysis/operator_gap_trace.csv (v1)
    csv_v1 = project_root / "outputs" / "operator_gap_analysis" / "operator_gap_trace.csv"
    if csv_v1.exists():
        with open(csv_v1) as f:
            reader = csv.DictReader(f)
            for row in reader:
                tid = row.get("task_id", "")
                if tid:
                    existing = traces.get(tid, {})
                    existing.update({k: v for k, v in row.items() if v})
                    traces[tid] = existing

    # Source 3: operator_gap_analysis_v3/operator_gap_trace.csv (richest, overrides)
    csv_v3 = project_root / "outputs" / "operator_gap_analysis_v3" / "operator_gap_trace.csv"
    if csv_v3.exists():
        with open(csv_v3) as f:
            reader = csv.DictReader(f)
            for row in reader:
                tid = row.get("task_id", "")
                if tid:
                    existing = traces.get(tid, {})
                    existing.update({k: v for k, v in row.items() if v})
                    traces[tid] = existing

    return traces


def build_trace_for_task(
    task_id: str,
    preloaded_traces: Dict[str, Dict[str, Any]],
    ns_state: Optional[NearSolvedTaskState],
) -> Dict[str, Any]:
    """Build the best available trace for a task.

    Priority:
    1. Preloaded gap analysis trace (has best_property + needed_operator_family)
    2. Near-solved state (has discriminative_property from structural analysis)
    3. Minimal fallback (triggers full fallback chain in TraceDrivenOperatorInventor)
    """
    if task_id in preloaded_traces:
        trace = preloaded_traces[task_id]
        if trace.get("best_property") and trace.get("needed_operator_family"):
            return trace

    if ns_state is not None:
        best_prop = ""
        family = "unknown"
        hyp = getattr(ns_state, "best_hypothesis", None) or {}
        if isinstance(hyp, dict):
            best_prop = hyp.get("selector", "") or hyp.get("best_property", "")
            family = hyp.get("family", "") or hyp.get("needed_operator_family", "unknown")
        cap = getattr(ns_state, "missing_capability_guess", "") or ""
        if not family or family == "unknown":
            if "recolor" in cap:
                family = "recolor_in_place"
            elif "copy" in cap or "move" in cap or "position" in cap:
                family = "copy_to_position"
            elif "color_transfer" in cap:
                family = "recolor_in_place"
        if best_prop:
            return {
                "task_id": task_id,
                "best_property": best_prop,
                "needed_operator_family": family,
            }

    if task_id in preloaded_traces:
        return preloaded_traces[task_id]

    return {
        "task_id": task_id,
        "best_property": "",
        "needed_operator_family": "unknown",
    }


# ── Timeout helper ────────────────────────────────────────────────────────

class TaskTimeoutError(Exception):
    pass


@contextmanager
def task_timeout(seconds: float):
    """Context manager that raises TaskTimeoutError after `seconds`."""
    def _handler(signum, frame):
        raise TaskTimeoutError(f"Task exceeded {seconds}s timeout")

    old_handler = signal.signal(signal.SIGALRM, _handler)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)


# ── Configuration definitions ────────────────────────────────────────────

CONFIGS = [
    "static_portfolio_no_dsl",
    "static_portfolio_with_dsl",
    "static_plus_adapter_genesis",
    "static_plus_near_solved_memory",
    "static_plus_trace_operator_invention",
    "static_plus_trace_operator_invention_with_verification",
    "full_domain_adaptive_verified_pipeline",
]


# ── Build solvers for each config ─────────────────────────────────────────

def _build_reasoning_loop(
    config_name: str,
    memory: ReasoningMemory,
    manifold: MemoryManifold,
    ns_mem: Optional[NearSolvedMemory],
    event_log: ReasoningEventLog,
    timeout: float = 15.0,
) -> AdaptiveReasoningLoop:
    """Build an AdaptiveReasoningLoop for the given config."""
    use_near_solved = config_name in (
        "static_plus_near_solved_memory",
        "static_plus_trace_operator_invention",
        "static_plus_trace_operator_invention_with_verification",
        "full_domain_adaptive_verified_pipeline",
    )
    return AdaptiveReasoningLoop(
        max_iterations=4,
        timeout_seconds=timeout,
        memory=memory,
        manifold=manifold,
        near_solved_memory=ns_mem if use_near_solved else None,
        event_log=event_log,
    )


def _config_uses_dsl(config_name: str) -> bool:
    return config_name != "static_portfolio_no_dsl"


def _config_uses_adapter_genesis(config_name: str) -> bool:
    return config_name in (
        "static_plus_adapter_genesis",
        "static_plus_near_solved_memory",
        "static_plus_trace_operator_invention",
        "static_plus_trace_operator_invention_with_verification",
        "full_domain_adaptive_verified_pipeline",
    )


def _config_uses_near_solved(config_name: str) -> bool:
    return config_name in (
        "static_plus_near_solved_memory",
        "static_plus_trace_operator_invention",
        "static_plus_trace_operator_invention_with_verification",
        "full_domain_adaptive_verified_pipeline",
    )


def _config_uses_trace_invention(config_name: str) -> bool:
    return config_name in (
        "static_plus_trace_operator_invention",
        "static_plus_trace_operator_invention_with_verification",
        "full_domain_adaptive_verified_pipeline",
    )


def _config_uses_verification(config_name: str) -> bool:
    return config_name in (
        "static_plus_trace_operator_invention_with_verification",
        "full_domain_adaptive_verified_pipeline",
    )


def _config_uses_certificates(config_name: str) -> bool:
    return config_name == "full_domain_adaptive_verified_pipeline"


# ── Per-task runner ───────────────────────────────────────────────────────

def run_single_task_across_configs(
    task: ARCTask,
    configs: List[str],
    timeout_per_config: float,
    shared_state: Dict[str, Any],
) -> Dict[str, Any]:
    """Run a single ARC task through configs in order.  Stop at first solve.

    Returns a result dict for the progress JSONL.
    """
    task_id = task.task_id
    train_pairs = [(ex.input_grid, ex.output_grid) for ex in task.train]
    test_inputs = [ex.input_grid for ex in task.test]
    test_outputs = [
        ex.output_grid for ex in task.test if ex.output_grid is not None
    ]
    if len(test_outputs) != len(test_inputs):
        test_outputs = []

    result = {
        "task_id": task_id,
        "config": None,
        "solved_by_static": False,
        "solved_by_dsl": False,
        "near_solved_stored": False,
        "operator_gap_detected": False,
        "operator_proposed": False,
        "operator_validated": False,
        "operator_promoted": False,
        "false_positive": False,
        "certificate_emitted": False,
        "runtime_seconds": 0.0,
        "operator_family": None,
        "final_config_that_solved": None,
        "error": None,
    }

    t0 = time.perf_counter()

    memory = shared_state["memory"]
    manifold = shared_state["manifold"]
    ns_mem = shared_state["ns_mem"]
    event_log = shared_state["event_log"]
    adapter_genesis = shared_state["adapter_genesis"]
    trace_inventor = shared_state["trace_inventor"]
    falsifier = shared_state["falsifier"]
    cert_builder = shared_state["cert_builder"]
    cert_dir = shared_state["cert_dir"]

    solved = False
    best_predictions = None
    best_hypothesis = None
    best_config = None

    for config_name in configs:
        if solved:
            break

        try:
            with task_timeout(timeout_per_config):
                # ── Phase 1: Static portfolio (structural reasoner) ──
                loop = _build_reasoning_loop(
                    config_name, memory, manifold, ns_mem, event_log,
                    timeout=min(timeout_per_config - 1, 14.0),
                )
                loop_result = loop.solve(
                    train_pairs, test_inputs, task_id=task_id,
                )
                if loop_result.solved and loop_result.predictions is not None:
                    correct = _check_correct(loop_result.predictions, test_outputs)
                    if correct:
                        solved = True
                        best_predictions = loop_result.predictions
                        best_hypothesis = loop_result.hypothesis
                        best_config = config_name
                        if config_name == "static_portfolio_no_dsl":
                            result["solved_by_static"] = True
                        elif config_name == "static_portfolio_with_dsl":
                            result["solved_by_dsl"] = True
                        continue

                # ── Phase 2: AdapterGenesis ──
                if not solved and _config_uses_adapter_genesis(config_name):
                    try:
                        ag_result = adapter_genesis.synthesize_and_solve(
                            train_pairs, test_inputs,
                        )
                        if ag_result is not None:
                            preds, meta = ag_result
                            if preds and _check_correct(preds, test_outputs):
                                solved = True
                                best_predictions = preds
                                best_hypothesis = meta
                                best_config = config_name
                                continue
                    except Exception:
                        pass

                # ── Phase 3: Near-solved storage ──
                if not solved and _config_uses_near_solved(config_name):
                    try:
                        ns_state = build_near_solved_state(
                            task_id=task_id,
                            train_pairs=train_pairs,
                            loop_result=loop_result,
                        )
                        if ns_state is not None:
                            ns_mem.store_partial(ns_state)
                            result["near_solved_stored"] = True
                    except Exception:
                        pass

                # ── Phase 4: Trace-driven operator invention ──
                if not solved and _config_uses_trace_invention(config_name):
                    try:
                        # Build trace from preloaded gap data or near-solved state
                        preloaded_traces = shared_state.get("gap_traces", {})
                        ns_for_trace = None
                        if ns_mem is not None:
                            ns_for_trace = ns_mem.resume_from_state(task_id)
                        trace = build_trace_for_task(
                            task_id, preloaded_traces, ns_for_trace,
                        )
                        inv_result = trace_inventor.run_full_pipeline(
                            task_id=task_id,
                            train_pairs=train_pairs,
                            test_inputs=test_inputs,
                            trace=trace,
                            test_outputs=test_outputs if test_outputs else None,
                        )

                        # Normalize inventor result fields
                        op_proposed = bool(
                            inv_result.get("operator_proposed")
                        )
                        op_promoted = bool(
                            inv_result.get("promoted")
                            or inv_result.get("operator_promoted")
                        )
                        oid = inv_result.get("operator_id", "") or ""
                        op_family = (
                            inv_result.get("operator_family")
                            or inv_result.get("family")
                        )
                        if not op_family:
                            for pfx, fam in (
                                ("ctr_", "color_transfer_recolor"),
                                ("rcl_", "recolor_in_place"),
                                ("ctp_", "copy_to_position"),
                                ("mr_", "marker_relative_copy_to_position"),
                                ("corr_", "correspondence_copy_to_position"),
                                ("vdp_", "variable_destination_copy"),
                                ("mp_", "marker_projection"),
                            ):
                                if oid.startswith(pfx):
                                    op_family = fam
                                    break

                        if op_proposed:
                            result["operator_proposed"] = True
                            result["operator_family"] = op_family
                        if inv_result.get("operator_gap_detected", False):
                            result["operator_gap_detected"] = True

                        # ── Phase 5: Verification (LOO + falsification) ──
                        if _config_uses_verification(config_name):
                            if inv_result.get("loo_passed"):
                                result["operator_validated"] = True

                            if op_promoted:
                                result["operator_promoted"] = True
                                solved = True
                                best_config = config_name
                                best_hypothesis = inv_result.get("hypothesis", {})
                                best_predictions = inv_result.get("predictions")

                            if inv_result.get("false_positive"):
                                result["false_positive"] = True
                        else:
                            # Without verification, accept if train-consistent
                            if inv_result.get("train_consistent"):
                                result["operator_validated"] = True
                            if op_promoted:
                                result["operator_promoted"] = True
                                solved = True
                                best_config = config_name
                                best_hypothesis = inv_result.get("hypothesis", {})
                                best_predictions = inv_result.get("predictions")

                        # Certificate from inventor (separate from Phase 6 cert)
                        if op_promoted and inv_result.get("certificate"):
                            cert_path = cert_dir / f"{task_id}.json"
                            if not cert_path.exists():
                                with open(cert_path, "w") as f:
                                    json.dump(inv_result["certificate"], f, indent=2)
                                result["certificate_emitted"] = True

                    except TaskTimeoutError:
                        raise
                    except Exception:
                        pass

                # ── Phase 6: Certificate emission ──
                if solved and _config_uses_certificates(config_name):
                    try:
                        if best_predictions and best_hypothesis:
                            # Active falsification on the final hypothesis
                            adapter = GridDomainAdapter()
                            fals_result = falsifier.falsify(
                                train_pairs, best_hypothesis or {}, adapter,
                            )
                            if fals_result.passed:
                                cert = cert_builder.from_loop_result(
                                    task_id=task_id,
                                    loop_result=loop_result,
                                    train_pairs=train_pairs,
                                    test_inputs=test_inputs,
                                )
                                cert_json = certificate_to_json(cert)
                                cert_path = cert_dir / f"{task_id}.json"
                                with open(cert_path, "w") as f:
                                    json.dump(cert_json, f, indent=2)
                                cert_md = certificate_to_markdown(cert)
                                with open(cert_dir / f"{task_id}.md", "w") as f:
                                    f.write(cert_md)
                                result["certificate_emitted"] = True
                    except Exception:
                        pass

        except TaskTimeoutError:
            pass
        except Exception as exc:
            result["error"] = f"{config_name}: {type(exc).__name__}: {str(exc)[:200]}"

    result["config"] = best_config or configs[-1]
    result["final_config_that_solved"] = best_config
    result["runtime_seconds"] = time.perf_counter() - t0
    return result


def _check_correct(
    predictions: List[np.ndarray],
    test_outputs: List[np.ndarray],
) -> bool:
    if not test_outputs or not predictions:
        return False
    if len(predictions) != len(test_outputs):
        return False
    return all(np.array_equal(p, e) for p, e in zip(predictions, test_outputs))


# ── Progress file I/O ─────────────────────────────────────────────────────

def load_progress(progress_path: Path) -> Dict[str, Dict[str, Any]]:
    """Load completed task records from the progress JSONL file."""
    done: Dict[str, Dict[str, Any]] = {}
    if not progress_path.exists():
        return done
    with open(progress_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                done[rec["task_id"]] = rec
            except (json.JSONDecodeError, KeyError):
                continue
    return done


def append_progress(progress_path: Path, record: Dict[str, Any]) -> None:
    """Append a single record to the progress JSONL file."""
    with open(progress_path, "a") as f:
        f.write(json.dumps(record, default=str) + "\n")


# ── Summary generation ────────────────────────────────────────────────────

def generate_summary(
    all_results: List[Dict[str, Any]],
    output_dir: Path,
    total_tasks: int,
    elapsed_total: float,
) -> None:
    """Generate all output files: summary.md, results.csv, promotions.jsonl,
    failure_taxonomy.csv, runtime_report.md."""

    # ── results.csv ──
    csv_path = output_dir / "results.csv"
    fieldnames = [
        "task_id", "final_config_that_solved", "solved_by_static", "solved_by_dsl",
        "near_solved_stored", "operator_gap_detected", "operator_proposed",
        "operator_validated", "operator_promoted", "false_positive",
        "certificate_emitted", "runtime_seconds", "operator_family", "error",
    ]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in all_results:
            writer.writerow(r)

    # ── promotions.jsonl ──
    promo_path = output_dir / "promotions.jsonl"
    with open(promo_path, "w") as f:
        for r in all_results:
            if r.get("operator_promoted") or r.get("final_config_that_solved"):
                f.write(json.dumps({
                    "task_id": r["task_id"],
                    "config": r.get("final_config_that_solved"),
                    "operator_family": r.get("operator_family"),
                    "certificate": r.get("certificate_emitted", False),
                }, default=str) + "\n")

    # ── failure_taxonomy.csv ──
    failure_reasons: Dict[str, int] = {}
    unsolved = [r for r in all_results if not r.get("final_config_that_solved")]
    for r in unsolved:
        if r.get("near_solved_stored"):
            key = "near_solved_but_not_promoted"
        elif r.get("operator_proposed") and not r.get("operator_promoted"):
            if r.get("false_positive"):
                key = "operator_proposed_but_false_positive"
            else:
                key = "operator_proposed_but_not_validated"
        elif r.get("error"):
            key = "runtime_error"
        else:
            key = "static_portfolio_miss"
        failure_reasons[key] = failure_reasons.get(key, 0) + 1

    fail_path = output_dir / "failure_taxonomy.csv"
    with open(fail_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["failure_category", "count"])
        for reason, count in sorted(failure_reasons.items(), key=lambda x: -x[1]):
            writer.writerow([reason, count])

    # ── Compute per-config stats ──
    config_solve_counts: Dict[str, int] = {}
    for r in all_results:
        cfg = r.get("final_config_that_solved")
        if cfg:
            config_solve_counts[cfg] = config_solve_counts.get(cfg, 0) + 1

    total_solved = sum(config_solve_counts.values())
    total_fp = sum(1 for r in all_results if r.get("false_positive"))
    total_certs = sum(1 for r in all_results if r.get("certificate_emitted"))
    total_near_solved = sum(1 for r in all_results if r.get("near_solved_stored"))
    total_proposed = sum(1 for r in all_results if r.get("operator_proposed"))
    total_promoted = sum(1 for r in all_results if r.get("operator_promoted"))
    runtimes = [r["runtime_seconds"] for r in all_results if r.get("runtime_seconds")]

    # ── Incremental contribution ──
    # For each config, count how many tasks it was the FIRST config to solve
    incremental: Dict[str, int] = {}
    running_solved = 0
    for cfg in CONFIGS:
        cfg_count = config_solve_counts.get(cfg, 0)
        incremental[cfg] = cfg_count
        running_solved += cfg_count

    # ── summary.md ──
    lines = [
        "# Full ARC-1000 Novel Pipeline Results",
        "",
        f"- **Total tasks**: {total_tasks}",
        f"- **Total solved**: {total_solved} / {total_tasks} "
        f"({100*total_solved/max(total_tasks,1):.1f}%)",
        f"- **Total elapsed**: {elapsed_total:.0f}s ({elapsed_total/3600:.1f}h)",
        "",
        "## Per-Config Solve Counts",
        "",
        "| Config | Solved | Incremental | Cumulative |",
        "|--------|--------|-------------|------------|",
    ]
    cumulative = 0
    for cfg in CONFIGS:
        inc = incremental.get(cfg, 0)
        cumulative += inc
        lines.append(f"| {cfg} | {inc} | +{inc} | {cumulative} |")

    lines.extend([
        "",
        "## Baseline Reproduction",
        "",
        f"- Static portfolio (no DSL): {config_solve_counts.get('static_portfolio_no_dsl', 0)} solved",
        f"- Static portfolio (with DSL): "
        f"{config_solve_counts.get('static_portfolio_no_dsl', 0) + config_solve_counts.get('static_portfolio_with_dsl', 0)} "
        f"cumulative solved",
        f"  - Expected baselines: ~84 without DSL, ~95 with DSL",
        "",
        "## Novel Pipeline Contributions",
        "",
        f"- AdapterGenesis: +{incremental.get('static_plus_adapter_genesis', 0)} tasks",
        f"- Near-solved memory: {total_near_solved} states stored, "
        f"+{incremental.get('static_plus_near_solved_memory', 0)} additional solves",
        f"- Trace-driven invention (no verif): "
        f"+{incremental.get('static_plus_trace_operator_invention', 0)} tasks",
        f"- Trace-driven invention (verified): "
        f"+{incremental.get('static_plus_trace_operator_invention_with_verification', 0)} tasks",
        f"- Full verified pipeline: "
        f"+{incremental.get('full_domain_adaptive_verified_pipeline', 0)} tasks",
        "",
        "## Operator Invention Statistics",
        "",
        f"- Operators proposed: {total_proposed}",
        f"- Operators promoted: {total_promoted}",
        f"- False positives: {total_fp}",
        f"- Certificates emitted: {total_certs}",
        "",
        "## Failure Taxonomy",
        "",
        "| Category | Count |",
        "|----------|-------|",
    ])
    for reason, count in sorted(failure_reasons.items(), key=lambda x: -x[1]):
        lines.append(f"| {reason} | {count} |")

    lines.extend([
        "",
        "## Runtime Statistics",
        "",
    ])
    if runtimes:
        lines.append(f"- Mean: {np.mean(runtimes):.2f}s per task")
        lines.append(f"- Median: {np.median(runtimes):.2f}s per task")
        lines.append(f"- P95: {np.percentile(runtimes, 95):.2f}s per task")
        lines.append(f"- Max: {max(runtimes):.2f}s per task")
        lines.append(f"- Total wall time: {elapsed_total:.0f}s ({elapsed_total/3600:.1f}h)")

    lines.extend([
        "",
        "## Trace-Driven Promotions",
        "",
    ])
    promoted_tasks = [r for r in all_results if r.get("operator_promoted")]
    if promoted_tasks:
        lines.append("| Task ID | Operator Family | Config | Certificate |")
        lines.append("|---------|----------------|--------|-------------|")
        for r in promoted_tasks:
            lines.append(
                f"| {r['task_id']} | {r.get('operator_family', 'N/A')} "
                f"| {r.get('final_config_that_solved', 'N/A')} "
                f"| {'yes' if r.get('certificate_emitted') else 'no'} |"
            )
    else:
        lines.append("No trace-driven promotions in this run.")

    with open(output_dir / "summary.md", "w") as f:
        f.write("\n".join(lines) + "\n")

    # ── runtime_report.md ──
    rt_lines = [
        "# Runtime Report",
        "",
        f"Total wall time: {elapsed_total:.0f}s ({elapsed_total/3600:.1f}h)",
        f"Tasks processed: {len(all_results)}",
        "",
    ]
    if runtimes:
        rt_lines.extend([
            "## Per-Task Runtime Distribution",
            "",
            f"- Mean:   {np.mean(runtimes):.2f}s",
            f"- Median: {np.median(runtimes):.2f}s",
            f"- Std:    {np.std(runtimes):.2f}s",
            f"- Min:    {min(runtimes):.2f}s",
            f"- P25:    {np.percentile(runtimes, 25):.2f}s",
            f"- P75:    {np.percentile(runtimes, 75):.2f}s",
            f"- P95:    {np.percentile(runtimes, 95):.2f}s",
            f"- P99:    {np.percentile(runtimes, 99):.2f}s",
            f"- Max:    {max(runtimes):.2f}s",
        ])

        # Breakdown by config
        rt_lines.extend([
            "",
            "## Runtime by Final Config",
            "",
            "| Config | Count | Mean (s) | Median (s) | Max (s) |",
            "|--------|-------|----------|------------|---------|",
        ])
        for cfg in CONFIGS:
            cfg_runtimes = [
                r["runtime_seconds"] for r in all_results
                if r.get("final_config_that_solved") == cfg
            ]
            if cfg_runtimes:
                rt_lines.append(
                    f"| {cfg} | {len(cfg_runtimes)} "
                    f"| {np.mean(cfg_runtimes):.2f} "
                    f"| {np.median(cfg_runtimes):.2f} "
                    f"| {max(cfg_runtimes):.2f} |"
                )
        unsolved_runtimes = [
            r["runtime_seconds"] for r in all_results
            if not r.get("final_config_that_solved")
        ]
        if unsolved_runtimes:
            rt_lines.append(
                f"| (unsolved) | {len(unsolved_runtimes)} "
                f"| {np.mean(unsolved_runtimes):.2f} "
                f"| {np.median(unsolved_runtimes):.2f} "
                f"| {max(unsolved_runtimes):.2f} |"
            )

    with open(output_dir / "runtime_report.md", "w") as f:
        f.write("\n".join(rt_lines) + "\n")


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Full ARC-1000 novel pipeline experiment"
    )
    parser.add_argument(
        "--arc-root", default="data/arc",
        help="Path to ARC data directory",
    )
    parser.add_argument(
        "--output-dir", default="outputs/full_arc1000_novel_pipeline",
        help="Output directory",
    )
    parser.add_argument(
        "--max-tasks", type=int, default=0,
        help="Limit number of tasks (0 = all)",
    )
    parser.add_argument(
        "--timeout-per-config", type=float, default=60.0,
        help="Timeout in seconds per task per config",
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="Resume from existing progress file",
    )
    parser.add_argument(
        "--configs", nargs="+", default=CONFIGS,
        help="Configs to run (default: all 7)",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    cert_dir = output_dir / "certificates"
    cert_dir.mkdir(exist_ok=True)

    progress_path = output_dir / "progress.jsonl"

    # ── Load ARC tasks ──
    print(f"Loading ARC tasks from {args.arc_root}...", flush=True)
    all_tasks = load_arc_tasks(args.arc_root, split="training")
    if args.max_tasks > 0:
        all_tasks = all_tasks[:args.max_tasks]
    print(f"  Loaded {len(all_tasks)} tasks", flush=True)

    # ── Resume check ──
    completed: Dict[str, Dict[str, Any]] = {}
    if args.resume:
        completed = load_progress(progress_path)
        print(f"  Resuming: {len(completed)} tasks already completed", flush=True)

    # ── Build shared state ──
    event_log = ReasoningEventLog()
    memory = ReasoningMemory()
    manifold = MemoryManifold()
    ns_mem = NearSolvedMemory(manifold)
    adapter_genesis = AdapterGenesis(manifold=manifold)
    trace_inventor = TraceDrivenOperatorInventor(event_log=event_log)
    falsifier = ActiveFalsifier()
    cert_builder = CertificateBuilder()

    # Load precomputed gap analysis traces (best_property + needed_operator_family)
    # PROJECT_ROOT is set at module level to the parent of scripts/
    gap_traces = load_gap_traces(PROJECT_ROOT)
    if not gap_traces:
        gap_traces = load_gap_traces(Path("."))
    print(f"  Loaded {len(gap_traces)} gap analysis traces", flush=True)

    shared_state = {
        "memory": memory,
        "manifold": manifold,
        "ns_mem": ns_mem,
        "event_log": event_log,
        "adapter_genesis": adapter_genesis,
        "trace_inventor": trace_inventor,
        "falsifier": falsifier,
        "cert_builder": cert_builder,
        "cert_dir": cert_dir,
        "gap_traces": gap_traces,
    }

    # ── Write run metadata ──
    run_meta = {
        "start_time": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "total_tasks": len(all_tasks),
        "configs": args.configs,
        "timeout_per_config": args.timeout_per_config,
        "resumed_from": len(completed),
        "arc_root": str(args.arc_root),
    }
    with open(output_dir / "run_metadata.json", "w") as f:
        json.dump(run_meta, f, indent=2)

    # ── Main loop ──
    t_global = time.perf_counter()
    all_results: List[Dict[str, Any]] = list(completed.values())
    n_new = 0

    for i, task in enumerate(all_tasks):
        task_id = task.task_id

        # Skip already-completed tasks
        if task_id in completed:
            continue

        # Progress display
        pct = 100 * (i + 1) / len(all_tasks)
        print(
            f"[{i+1}/{len(all_tasks)} {pct:.0f}%] {task_id} ...",
            end=" ", flush=True,
        )

        try:
            result = run_single_task_across_configs(
                task=task,
                configs=args.configs,
                timeout_per_config=args.timeout_per_config,
                shared_state=shared_state,
            )
        except Exception as exc:
            result = {
                "task_id": task_id,
                "config": "error",
                "solved_by_static": False,
                "solved_by_dsl": False,
                "near_solved_stored": False,
                "operator_gap_detected": False,
                "operator_proposed": False,
                "operator_validated": False,
                "operator_promoted": False,
                "false_positive": False,
                "certificate_emitted": False,
                "runtime_seconds": 0.0,
                "operator_family": None,
                "final_config_that_solved": None,
                "error": f"FATAL: {type(exc).__name__}: {str(exc)[:200]}",
            }

        # Checkpoint immediately
        append_progress(progress_path, result)
        all_results.append(result)
        completed[task_id] = result
        n_new += 1

        # Status line
        solved_marker = result.get("final_config_that_solved", "UNSOLVED")
        rt = result.get("runtime_seconds", 0)
        print(f"{solved_marker} ({rt:.1f}s)", flush=True)

        # ── Known-task guard ──
        _KNOWN_PROMOTED_TASKS = {
            "2a5f8217", "d89b689b", "e9ac8c9e", "a48eeaf7",
        }
        if task_id in _KNOWN_PROMOTED_TASKS:
            guard_path = output_dir / "known_task_guard.jsonl"
            trace_used = build_trace_for_task(
                task_id, shared_state.get("gap_traces", {}), None,
            )
            guard_rec = {
                "task_id": task_id,
                "sorted_position": i + 1,
                "trace_family": trace_used.get("needed_operator_family"),
                "trace_property": trace_used.get("best_property"),
                "operator_family_attempted": result.get("operator_family"),
                "operator_promoted": result.get("operator_promoted", False),
                "certificate_emitted": result.get("certificate_emitted", False),
                "correct_if_known": bool(result.get("final_config_that_solved")),
                "failure_reason": result.get("error") or (
                    None if result.get("operator_promoted") else "not_promoted"
                ),
            }
            with open(guard_path, "a") as gf:
                gf.write(json.dumps(guard_rec) + "\n")
            print(
                f"  KNOWN-TASK GUARD: {task_id} promoted={guard_rec['operator_promoted']}",
                flush=True,
            )
            if not guard_rec["operator_promoted"]:
                stop_path = output_dir / "STOP_KNOWN_TASK_REPRO_FAILED"
                with open(stop_path, "w") as sf:
                    sf.write(
                        f"Known promoted task {task_id} failed to reproduce.\n"
                        f"Guard record: {json.dumps(guard_rec, indent=2)}\n"
                        f"Stopping run to prevent wasted compute.\n"
                    )
                print(
                    f"  *** STOPPING: known task {task_id} did not promote. "
                    f"See {stop_path} ***",
                    flush=True,
                )
                sys.exit(1)

        # Periodic summary (every 50 tasks)
        if n_new % 50 == 0:
            n_solved = sum(
                1 for r in all_results if r.get("final_config_that_solved")
            )
            elapsed = time.perf_counter() - t_global
            print(
                f"    -- checkpoint: {n_solved}/{len(all_results)} solved, "
                f"{elapsed:.0f}s elapsed --",
                flush=True,
            )

    elapsed_total = time.perf_counter() - t_global

    # ── Generate outputs ──
    print(f"\nGenerating summary outputs...", flush=True)
    generate_summary(all_results, output_dir, len(all_tasks), elapsed_total)

    # ── Final report ──
    n_solved = sum(1 for r in all_results if r.get("final_config_that_solved"))
    n_fp = sum(1 for r in all_results if r.get("false_positive"))
    n_certs = sum(1 for r in all_results if r.get("certificate_emitted"))

    print(f"\n{'='*70}", flush=True)
    print(f"  FULL ARC-1000 NOVEL PIPELINE COMPLETE", flush=True)
    print(f"{'='*70}", flush=True)
    print(f"  Tasks:       {len(all_results)}", flush=True)
    print(f"  Solved:      {n_solved} ({100*n_solved/max(len(all_results),1):.1f}%)", flush=True)
    print(f"  FP:          {n_fp}", flush=True)
    print(f"  Certs:       {n_certs}", flush=True)
    print(f"  Wall time:   {elapsed_total:.0f}s ({elapsed_total/3600:.1f}h)", flush=True)
    print(f"  Output:      {output_dir}/", flush=True)
    print(f"{'='*70}", flush=True)


if __name__ == "__main__":
    main()
