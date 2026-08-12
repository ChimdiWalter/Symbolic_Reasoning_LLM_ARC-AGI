#!/usr/bin/env python3.11
"""Debug a single task through the full ARC-1000 runner path with verbose logging.

Runs the exact same code path as run_full_arc1000_novel_pipeline.py for one task,
logging every intermediate step to diagnose divergence from the direct
TraceDrivenOperatorInventor.run_full_pipeline() path.

Usage:
    PYTHONPATH=src python3.11 scripts/debug_full_runner_known_task.py --task-id 2a5f8217
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from reasoning_project.arc_adapter import load_arc_tasks
from reasoning_project.trace_operator_invention import TraceDrivenOperatorInventor
from reasoning_project.events import ReasoningEventLog
from reasoning_project.reasoning_engine import ReasoningMemory, GridDomainAdapter
from reasoning_project.manifold_memory import MemoryManifold
from reasoning_project.near_solved_memory import NearSolvedMemory, build_near_solved_state
from reasoning_project.adapter_genesis import AdapterGenesis
from reasoning_project.active_falsifier import ActiveFalsifier
from reasoning_project.certificates import CertificateBuilder, certificate_to_json

from run_full_arc1000_novel_pipeline import (
    run_single_task_across_configs,
    CONFIGS,
    load_gap_traces,
    build_trace_for_task,
    _config_uses_trace_invention,
    _config_uses_verification,
    _config_uses_adapter_genesis,
    _config_uses_near_solved,
    _build_reasoning_loop,
    TaskTimeoutError,
    task_timeout,
)


def main():
    parser = argparse.ArgumentParser(description="Debug full-runner for a single known task")
    parser.add_argument("--task-id", required=True, help="ARC task ID to debug")
    parser.add_argument("--arc-root", default="data/arc", help="ARC data directory")
    parser.add_argument("--timeout", type=float, default=60.0, help="Timeout per config")
    args = parser.parse_args()

    task_id = args.task_id
    out_dir = PROJECT_ROOT / "outputs" / "full_arc1000_novel_pipeline" / f"debug_{task_id}"
    out_dir.mkdir(parents=True, exist_ok=True)
    cert_dir = out_dir / "certs"
    cert_dir.mkdir(exist_ok=True)

    events: List[Dict[str, Any]] = []

    def log(msg: str, data: Optional[Dict[str, Any]] = None):
        entry = {"t": time.time(), "msg": msg}
        if data:
            entry["data"] = data
        events.append(entry)
        print(f"  {msg}", flush=True)

    # ── Load task ──
    print(f"Loading ARC tasks from {args.arc_root}...", flush=True)
    all_tasks = load_arc_tasks(args.arc_root, split="training")
    task_map = {t.task_id: t for t in all_tasks}
    task = task_map.get(task_id)
    if task is None:
        print(f"ERROR: task {task_id} not found")
        sys.exit(1)

    log(f"task_id: {task_id}")

    train_pairs = [(ex.input_grid, ex.output_grid) for ex in task.train]
    test_inputs = [ex.input_grid for ex in task.test]
    test_outputs = [ex.output_grid for ex in task.test if ex.output_grid is not None]
    if len(test_outputs) != len(test_inputs):
        test_outputs = []

    log(f"train_pairs count: {len(train_pairs)}")
    log(f"test_inputs count: {len(test_inputs)}")
    log(f"test_outputs available: {bool(test_outputs)} (count={len(test_outputs)})")

    for i, (inp, out) in enumerate(train_pairs):
        log(f"train[{i}]: input={inp.shape} dtype={inp.dtype}, output={out.shape}")
    for i, ti in enumerate(test_inputs):
        log(f"test_input[{i}]: shape={ti.shape} dtype={ti.dtype}")

    # ── Build shared state ──
    event_log = ReasoningEventLog()
    memory = ReasoningMemory()
    manifold = MemoryManifold()
    ns_mem = NearSolvedMemory(manifold)
    adapter_genesis = AdapterGenesis(manifold=manifold)
    trace_inventor = TraceDrivenOperatorInventor(event_log=event_log)
    falsifier = ActiveFalsifier()
    cert_builder = CertificateBuilder()

    gap_traces = load_gap_traces(PROJECT_ROOT)
    if not gap_traces:
        gap_traces = load_gap_traces(Path("."))
    log(f"gap_traces loaded: {len(gap_traces)}")

    trace = build_trace_for_task(task_id, gap_traces, None)
    log(f"trace_family: {trace.get('needed_operator_family')}")
    log(f"trace_property: {trace.get('best_property')}")

    shared_state = {
        "memory": memory, "manifold": manifold, "ns_mem": ns_mem,
        "event_log": event_log, "adapter_genesis": adapter_genesis,
        "trace_inventor": trace_inventor, "falsifier": falsifier,
        "cert_builder": cert_builder, "cert_dir": cert_dir,
        "gap_traces": gap_traces,
    }

    # ── A: Direct inventor path ──
    print(f"\n=== Path A: Direct TraceDrivenOperatorInventor.run_full_pipeline ===", flush=True)
    inventor_a = TraceDrivenOperatorInventor(event_log=ReasoningEventLog())
    t0 = time.perf_counter()
    try:
        direct_result = inventor_a.run_full_pipeline(
            task_id=task_id,
            train_pairs=train_pairs,
            test_inputs=test_inputs,
            trace=trace,
            test_outputs=test_outputs if test_outputs else None,
        )
        elapsed_a = time.perf_counter() - t0
        log(f"Direct path: promoted={direct_result.get('promoted')}, "
            f"operator_id={direct_result.get('operator_id')}, "
            f"loo_passed={direct_result.get('loo_passed')}, "
            f"elapsed={elapsed_a:.3f}s",
            {"result": {k: str(v)[:200] for k, v in direct_result.items()}})
    except Exception as e:
        elapsed_a = time.perf_counter() - t0
        log(f"Direct path EXCEPTION: {type(e).__name__}: {e}", {"traceback": traceback.format_exc()})
        direct_result = None

    # ── B: Full runner path ──
    print(f"\n=== Path B: Full runner (run_single_task_across_configs) ===", flush=True)
    t0 = time.perf_counter()
    try:
        runner_result = run_single_task_across_configs(
            task=task,
            configs=CONFIGS,
            timeout_per_config=args.timeout,
            shared_state=shared_state,
        )
        elapsed_b = time.perf_counter() - t0
        log(f"Full runner: operator_promoted={runner_result.get('operator_promoted')}, "
            f"operator_family={runner_result.get('operator_family')}, "
            f"config={runner_result.get('final_config_that_solved')}, "
            f"elapsed={elapsed_b:.1f}s",
            {"result": runner_result})
    except Exception as e:
        elapsed_b = time.perf_counter() - t0
        log(f"Full runner EXCEPTION: {type(e).__name__}: {e}", {"traceback": traceback.format_exc()})
        runner_result = None

    # ── C: Per-config instrumented run ──
    print(f"\n=== Path C: Instrumented per-config breakdown ===", flush=True)
    trace_configs = [c for c in CONFIGS if _config_uses_trace_invention(c)]
    # Reset inventor state
    trace_inventor2 = TraceDrivenOperatorInventor(event_log=ReasoningEventLog())
    ns_mem2 = NearSolvedMemory(manifold)

    for config_name in trace_configs:
        print(f"\n--- Config: {config_name} ---", flush=True)
        tc0 = time.perf_counter()
        try:
            with task_timeout(args.timeout):
                phase1_t = time.perf_counter()
                loop = _build_reasoning_loop(
                    config_name, memory, manifold, ns_mem2, event_log,
                    timeout=min(args.timeout - 1, 14.0),
                )
                loop_result = loop.solve(train_pairs, test_inputs, task_id=task_id)
                log(f"Phase 1 (reasoning loop): {time.perf_counter()-phase1_t:.1f}s, solved={loop_result.solved}")

                if _config_uses_adapter_genesis(config_name):
                    phase2_t = time.perf_counter()
                    try:
                        ag_result = adapter_genesis.synthesize_and_solve(train_pairs, test_inputs)
                        log(f"Phase 2 (adapter genesis): {time.perf_counter()-phase2_t:.1f}s, result={ag_result is not None}")
                    except Exception as e:
                        log(f"Phase 2 exception: {type(e).__name__}: {str(e)[:100]}")

                if _config_uses_near_solved(config_name):
                    phase3_t = time.perf_counter()
                    try:
                        ns_state = build_near_solved_state(
                            task_id=task_id, train_pairs=train_pairs, loop_result=loop_result,
                        )
                        if ns_state is not None:
                            ns_mem2.store_partial(ns_state)
                        log(f"Phase 3 (near-solved): {time.perf_counter()-phase3_t:.1f}s, stored={ns_state is not None}")
                    except Exception as e:
                        log(f"Phase 3 exception: {type(e).__name__}: {str(e)[:100]}")

                remaining = args.timeout - (time.perf_counter() - tc0)
                log(f"Time remaining before Phase 4: {remaining:.1f}s")

                phase4_t = time.perf_counter()
                try:
                    ns_for_trace = ns_mem2.resume_from_state(task_id)
                    trace2 = build_trace_for_task(task_id, gap_traces, ns_for_trace)
                    log(f"Trace: family={trace2.get('needed_operator_family')}, prop={trace2.get('best_property')}")

                    inv_result = trace_inventor2.run_full_pipeline(
                        task_id=task_id,
                        train_pairs=train_pairs,
                        test_inputs=test_inputs,
                        trace=trace2,
                        test_outputs=test_outputs if test_outputs else None,
                    )
                    log(f"Phase 4: {time.perf_counter()-phase4_t:.1f}s, "
                        f"proposed={inv_result.get('operator_proposed')}, "
                        f"promoted={inv_result.get('promoted')}, "
                        f"operator_id={inv_result.get('operator_id')}, "
                        f"loo={inv_result.get('loo_passed')}, "
                        f"rejection={inv_result.get('rejection_reason')}")

                    if inv_result.get("promoted"):
                        log("PASS: Task promoted through full-runner path")
                        break
                except TaskTimeoutError:
                    log(f"Phase 4: TIMEOUT after {time.perf_counter()-phase4_t:.1f}s")
                    raise
                except Exception as e:
                    log(f"Phase 4: EXCEPTION after {time.perf_counter()-phase4_t:.1f}s: "
                        f"{type(e).__name__}: {str(e)[:200]}")
                    log(f"Phase 4 traceback: {traceback.format_exc()}")

        except TaskTimeoutError:
            log(f"Config timeout after {time.perf_counter()-tc0:.1f}s")
        except Exception as exc:
            log(f"Config exception: {type(exc).__name__}: {str(exc)[:200]}")

    # ── Generate outputs ──
    print(f"\n=== Generating debug outputs ===", flush=True)

    # path_diff.md
    lines = [
        f"# Path Comparison: {task_id}",
        "",
        "## Path A: Direct TraceDrivenOperatorInventor.run_full_pipeline()",
        "",
    ]
    if direct_result:
        lines.append(f"- promoted: {direct_result.get('promoted')}")
        lines.append(f"- operator_id: {direct_result.get('operator_id')}")
        lines.append(f"- loo_passed: {direct_result.get('loo_passed')}")
        lines.append(f"- elapsed: {elapsed_a:.3f}s")
    else:
        lines.append("- FAILED (exception)")

    lines.extend(["", "## Path B: Full runner (run_single_task_across_configs)", ""])
    if runner_result:
        lines.append(f"- operator_promoted: {runner_result.get('operator_promoted')}")
        lines.append(f"- operator_family: {runner_result.get('operator_family')}")
        lines.append(f"- final_config: {runner_result.get('final_config_that_solved')}")
        lines.append(f"- certificate_emitted: {runner_result.get('certificate_emitted')}")
        lines.append(f"- elapsed: {elapsed_b:.1f}s")
    else:
        lines.append("- FAILED (exception)")

    lines.extend([
        "",
        "## Root Cause Analysis",
        "",
    ])
    if runner_result and runner_result.get("operator_promoted"):
        lines.append("Both paths agree: task promoted successfully.")
    elif runner_result and not runner_result.get("operator_promoted") and direct_result and direct_result.get("promoted"):
        lines.append("DIVERGENCE: Direct path promotes but full runner does not.")
        lines.append("")
        lines.append("Likely cause: exception in Phase 4 swallowed by `except Exception: pass`.")
    else:
        lines.append("Further investigation needed.")

    with open(out_dir / "path_diff.md", "w") as f:
        f.write("\n".join(lines) + "\n")

    # full_runner_debug.md
    md_lines = [f"# Full Runner Debug: {task_id}", ""]
    for ev in events:
        md_lines.append(f"- {ev['msg']}")
    with open(out_dir / "full_runner_debug.md", "w") as f:
        f.write("\n".join(md_lines) + "\n")

    # raw_inv_result.json
    if direct_result:
        safe_result = {}
        for k, v in direct_result.items():
            if isinstance(v, np.ndarray):
                safe_result[k] = v.tolist()
            elif isinstance(v, list) and v and isinstance(v[0], np.ndarray):
                safe_result[k] = [a.tolist() for a in v]
            else:
                safe_result[k] = v
        with open(out_dir / "raw_inv_result.json", "w") as f:
            json.dump(safe_result, f, indent=2, default=str)

    # event_log.jsonl
    with open(out_dir / "event_log.jsonl", "w") as f:
        for ev in events:
            safe_ev = {k: v for k, v in ev.items() if k != "data"}
            if "data" in ev:
                safe_ev["data"] = {
                    k: str(v)[:500] for k, v in ev["data"].items()
                }
            f.write(json.dumps(safe_ev, default=str) + "\n")

    # ── Final verdict ──
    print(f"\n{'='*60}", flush=True)
    a_ok = direct_result and direct_result.get("promoted")
    b_ok = runner_result and runner_result.get("operator_promoted")
    print(f"  Direct path:    {'PASS' if a_ok else 'FAIL'}", flush=True)
    print(f"  Full runner:    {'PASS' if b_ok else 'FAIL'}", flush=True)
    print(f"  Paths agree:    {'YES' if a_ok == b_ok else 'NO — DIVERGENCE'}", flush=True)
    print(f"  Output:         {out_dir}/", flush=True)
    print(f"{'='*60}", flush=True)

    sys.exit(0 if b_ok else 1)


if __name__ == "__main__":
    main()
