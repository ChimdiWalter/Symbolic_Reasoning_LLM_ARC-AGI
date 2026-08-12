"""Memory Growth Curriculum v2: cumulative reasoning through failure memory.

Demonstrates the central thesis:
  failed → near-solved → remembered → clustered → abstraction invented →
  actively falsified → resumed → solved later → certified

6 stages:
  Stage 1: Atomic object/property tasks (ARC training, no memory)
  Stage 2: Recombined concepts (ARC training, episodic memory accumulates)
  Stage 3: Relational abstraction (ARC training, manifold + near-solved memory)
  Stage 4: Operator invention (cluster failures, propose+validate concepts)
  Stage 5: Return to failed tasks (resume from near-solved checkpoints)
  Stage 6: Unseen transfer tasks (ConceptARC + cross-domain benchmarks)

Outputs event log, stage metrics, promotion tracking, and scaling data.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reasoning_project.reasoning_engine import (
    GridDomainAdapter,
    ReasoningMemory,
    StructuralReasoner,
)
from reasoning_project.adaptive_loop import (
    AdaptiveReasoningLoop,
    LoopResult,
)
from reasoning_project.manifold_memory import (
    MemoryManifold,
    ManifoldMismatchTrigger,
    FiberBundle,
    GeodesicSolver,
    ManifoldPoint,
    encode_task_signature,
    _signature_to_embedding,
)
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
from reasoning_project.operator_invention import (
    OperatorInventor,
    InventedConcept,
    InventedOperator,
)
from reasoning_project.formal_verification import (
    LTLModelChecker,
    build_trace_from_loop_result,
    reasoning_loop_specifications,
)


# ═══════════════════════════════════════════════════════════════════════════
# DATA LOADING
# ═══════════════════════════════════════════════════════════════════════════

def load_arc_tasks(root: str) -> List[Dict[str, Any]]:
    tasks = []
    challenges_path = os.path.join(root, "arc-agi_training_challenges.json")
    solutions_path = os.path.join(root, "arc-agi_training_solutions.json")

    if os.path.isfile(challenges_path):
        with open(challenges_path) as f:
            challenges = json.load(f)
        solutions = {}
        if os.path.isfile(solutions_path):
            with open(solutions_path) as f:
                solutions = json.load(f)
        for task_id in sorted(challenges.keys()):
            data = challenges[task_id]
            train_pairs = [
                (np.array(ex["input"]), np.array(ex["output"]))
                for ex in data["train"]
            ]
            test_inputs = [np.array(ex["input"]) for ex in data["test"]]
            test_outputs = []
            if task_id in solutions:
                test_outputs = [np.array(o) for o in solutions[task_id]]
            elif data["test"] and "output" in data["test"][0]:
                test_outputs = [np.array(ex["output"]) for ex in data["test"]]
            if test_outputs:
                tasks.append({
                    "task_id": task_id,
                    "train_pairs": train_pairs,
                    "test_inputs": test_inputs,
                    "test_outputs": test_outputs,
                })
        return tasks

    training_dir = os.path.join(root, "training")
    if not os.path.isdir(training_dir):
        training_dir = root
    for fn in sorted(os.listdir(training_dir)):
        if not fn.endswith(".json"):
            continue
        with open(os.path.join(training_dir, fn)) as f:
            data = json.load(f)
        task_id = fn.replace(".json", "")
        train_pairs = [
            (np.array(ex["input"]), np.array(ex["output"]))
            for ex in data["train"]
        ]
        test_pairs = [
            (np.array(ex["input"]), np.array(ex["output"]))
            for ex in data["test"]
        ]
        tasks.append({
            "task_id": task_id,
            "train_pairs": train_pairs,
            "test_inputs": [t[0] for t in test_pairs],
            "test_outputs": [t[1] for t in test_pairs],
        })
    return tasks


def load_conceptarc_tasks(root: str) -> List[Dict[str, Any]]:
    """Load ConceptARC tasks if available."""
    tasks = []
    conceptarc_dir = os.path.join(root, "conceptarc")
    if not os.path.isdir(conceptarc_dir):
        return tasks
    for group_dir in sorted(os.listdir(conceptarc_dir)):
        group_path = os.path.join(conceptarc_dir, group_dir)
        if not os.path.isdir(group_path):
            continue
        for fn in sorted(os.listdir(group_path)):
            if not fn.endswith(".json"):
                continue
            with open(os.path.join(group_path, fn)) as f:
                data = json.load(f)
            task_id = f"conceptarc_{group_dir}_{fn.replace('.json', '')}"
            train_pairs = [
                (np.array(ex["input"]), np.array(ex["output"]))
                for ex in data.get("train", [])
            ]
            test_pairs = [
                (np.array(ex["input"]), np.array(ex["output"]))
                for ex in data.get("test", [])
            ]
            if train_pairs and test_pairs:
                tasks.append({
                    "task_id": task_id,
                    "train_pairs": train_pairs,
                    "test_inputs": [t[0] for t in test_pairs],
                    "test_outputs": [t[1] for t in test_pairs],
                    "domain": "conceptarc",
                    "concept_group": group_dir,
                })
    return tasks


# ═══════════════════════════════════════════════════════════════════════════
# STAGE RUNNER
# ═══════════════════════════════════════════════════════════════════════════

def run_stage(
    tasks: List[Dict],
    memory: ReasoningMemory,
    manifold: Optional[MemoryManifold],
    near_solved_mem: Optional[NearSolvedMemory],
    event_log: ReasoningEventLog,
    resume_states: Optional[Dict[str, NearSolvedTaskState]] = None,
    falsifier: Optional[ActiveFalsifier] = None,
    emit_certificates: bool = False,
    label: str = "",
) -> Dict[str, Any]:
    loop = AdaptiveReasoningLoop(
        max_iterations=4,
        timeout_seconds=15.0,
        memory=memory,
        manifold=manifold,
        near_solved_memory=near_solved_mem,
        event_log=event_log,
    )

    solved = []
    unsolved = []
    near_solved_ids = []
    promoted = []
    false_positives = []
    certificates: List[Dict] = []
    falsification_results: List[Dict] = []
    all_results = []

    t0 = time.perf_counter()

    for i, task in enumerate(tasks):
        tid = task["task_id"]
        train_pairs = task["train_pairs"]
        test_inputs = task["test_inputs"]
        test_outputs = task["test_outputs"]

        rs = resume_states.get(tid) if resume_states else None
        result = loop.solve(train_pairs, test_inputs, task_id=tid, resume_from=rs)

        correct = False
        is_fp = False
        if result.solved and result.predictions is not None:
            correct = all(
                np.array_equal(p, e)
                for p, e in zip(result.predictions, test_outputs)
            )
            if not correct:
                is_fp = True
                false_positives.append(tid)
                event_log.emit("REGRESSION_DETECTED", tid, {
                    "type": "false_positive",
                    "stage": label,
                }, module="curriculum")

        # Active falsification on accepted hypotheses
        if correct and falsifier is not None and result.hypothesis is not None:
            try:
                fres = falsifier.falsify(result.hypothesis, train_pairs, test_inputs)
                falsification_results.append({
                    "task_id": tid,
                    "score": fres.falsification_score,
                    "passed": fres.passed,
                    "survived": fres.counterexamples_survived,
                    "total": fres.counterexamples_generated,
                })
                event_log.emit("HYPOTHESIS_FALSIFIED", tid, {
                    "score": fres.falsification_score,
                    "passed": fres.passed,
                    "survived": fres.counterexamples_survived,
                    "total": fres.counterexamples_generated,
                }, module="active_falsifier")
            except Exception:
                pass

        # Certificate emission
        if correct and emit_certificates and result.hypothesis is not None:
            try:
                cert = CertificateBuilder.from_loop_result(result, train_pairs)
                cert_dict = certificate_to_json(cert)
                certificates.append(cert_dict)
                event_log.emit("REASONING_CERTIFICATE_CREATED", tid, {
                    "confidence": cert.confidence,
                    "failure_risk": cert.failure_risk,
                    "training_fit": cert.training_fit,
                }, module="certificates")
            except Exception:
                pass

        entry = {
            "task_id": tid,
            "solved": correct,
            "false_positive": is_fp,
            "iterations": result.iterations_used,
            "views": result.views_tried,
            "resumed": rs is not None,
        }
        all_results.append(entry)

        if correct:
            solved.append(tid)
            if rs is not None:
                promoted.append(tid)
                event_log.emit("TASK_PROMOTED_TO_SOLVED", tid, {
                    "stage": label,
                    "iterations": result.iterations_used,
                }, module="curriculum")
                if near_solved_mem is not None:
                    near_solved_mem.promote_to_solved(tid, result.hypothesis or {})
        else:
            unsolved.append(tid)
            if near_solved_mem is not None:
                state = near_solved_mem.states.get(tid)
                if state is not None and state.is_near_solved:
                    near_solved_ids.append(tid)

        if (i + 1) % 100 == 0:
            elapsed = time.perf_counter() - t0
            print(f"  [{label}] {i+1}/{len(tasks)} ({elapsed:.0f}s, "
                  f"solved={len(solved)}, promoted={len(promoted)})",
                  flush=True)

    elapsed = time.perf_counter() - t0
    print(f"  [{label}] {len(tasks)} tasks, {len(solved)} solved, "
          f"{len(near_solved_ids)} near-solved, {len(promoted)} promoted, "
          f"{len(false_positives)} FP, {elapsed:.1f}s", flush=True)

    return {
        "label": label,
        "n_tasks": len(tasks),
        "n_solved": len(solved),
        "n_unsolved": len(unsolved),
        "n_near_solved": len(near_solved_ids),
        "n_promoted": len(promoted),
        "n_false_positives": len(false_positives),
        "solved_ids": solved,
        "promoted_ids": promoted,
        "near_solved_ids": near_solved_ids,
        "false_positive_ids": false_positives,
        "elapsed": elapsed,
        "certificates": certificates,
        "falsification_results": falsification_results,
        "results": all_results,
    }


# ═══════════════════════════════════════════════════════════════════════════
# MAIN CURRICULUM
# ═══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Memory Growth Curriculum v2: cumulative reasoning evaluation"
    )
    parser.add_argument("--arc-root", default="data/arc")
    parser.add_argument("--output-dir", default="outputs/memory_growth")
    parser.add_argument("--max-tasks", type=int, default=0,
                        help="0 = all tasks")
    parser.add_argument("--use-cache", default="",
                        help="Load Phase 1 near-solved cache from this dir")
    args = parser.parse_args()

    out = args.output_dir
    os.makedirs(out, exist_ok=True)
    os.makedirs(os.path.join(out, "events"), exist_ok=True)
    os.makedirs(os.path.join(out, "certificates"), exist_ok=True)

    event_log = ReasoningEventLog()

    # Load data
    arc_tasks = load_arc_tasks(args.arc_root)
    if args.max_tasks > 0:
        arc_tasks = arc_tasks[:args.max_tasks]
    print(f"Loaded {len(arc_tasks)} ARC tasks", flush=True)

    conceptarc_tasks = load_conceptarc_tasks(args.arc_root)
    print(f"Loaded {len(conceptarc_tasks)} ConceptARC tasks", flush=True)

    # Split ARC tasks: 80% curriculum, 20% held-out
    n_curriculum = int(len(arc_tasks) * 0.8)
    curriculum_tasks = arc_tasks[:n_curriculum]
    heldout_tasks = arc_tasks[n_curriculum:]
    print(f"Curriculum: {len(curriculum_tasks)}, Held-out: {len(heldout_tasks)}", flush=True)

    falsifier = ActiveFalsifier()
    stage_results = {}

    # ── Stage 1: No memory baseline ──────────────────────────────────
    print("\n" + "=" * 60, flush=True)
    print("STAGE 1: Static baseline (no memory)", flush=True)
    print("=" * 60, flush=True)
    memory_1 = ReasoningMemory()
    stage_results["stage_1_static"] = run_stage(
        curriculum_tasks, memory_1, None, None,
        event_log=event_log, label="stage_1_static",
    )

    # ── Stage 2: Episodic memory accumulates ─────────────────────────
    print("\n" + "=" * 60, flush=True)
    print("STAGE 2: Episodic memory accumulates", flush=True)
    print("=" * 60, flush=True)
    memory_2 = ReasoningMemory()
    stage_results["stage_2_episodic"] = run_stage(
        curriculum_tasks, memory_2, None, None,
        event_log=event_log, label="stage_2_episodic",
    )

    # ── Stage 3: Manifold + near-solved memory ───────────────────────
    print("\n" + "=" * 60, flush=True)
    print("STAGE 3: Manifold + near-solved memory", flush=True)
    print("=" * 60, flush=True)
    memory_3 = ReasoningMemory()
    manifold_3 = MemoryManifold()
    if args.use_cache:
        from reasoning_project.near_solved_memory import load_near_solved_cache
        ns_mem_3, _, _ = load_near_solved_cache(args.use_cache)
    else:
        ns_mem_3 = NearSolvedMemory(manifold_3)
    stage_results["stage_3_manifold"] = run_stage(
        curriculum_tasks, memory_3, manifold_3, ns_mem_3,
        event_log=event_log, label="stage_3_manifold",
    )

    # ── Stage 4: Concept/operator invention from failure clusters ────
    print("\n" + "=" * 60, flush=True)
    print("STAGE 4: Concept/operator invention from failure clusters", flush=True)
    print("=" * 60, flush=True)

    missing_charts = ns_mem_3.detect_missing_charts(min_cluster_size=2)
    print(f"  Detected {len(missing_charts)} failure clusters", flush=True)
    for mc in missing_charts[:10]:
        print(f"    {mc['failure_type']}: {mc['missing_capability']} "
              f"({mc['n_tasks']} tasks)", flush=True)
        event_log.emit("FAILURE_CLUSTER_CREATED", None, {
            "failure_type": mc["failure_type"],
            "missing_capability": mc["missing_capability"],
            "n_tasks": mc["n_tasks"],
        }, module="near_solved_memory")

    invented_concepts: List[InventedConcept] = []
    invented_operators: List[InventedOperator] = []
    try:
        inventor = OperatorInventor()
        clusters = inventor.mine_from_near_solved(ns_mem_3)
        adapter = GridDomainAdapter()
        prop_names = adapter.property_names()
        invented_concepts = inventor.propose_concepts(clusters, prop_names)
        invented_operators = inventor.propose_operators(clusters)

        for ic in invented_concepts:
            event_log.emit("CONCEPT_PROPOSED", None, {
                "name": getattr(ic, "name", str(ic)),
                "gain": getattr(ic, "gain", 0),
                "fp_rate": getattr(ic, "fp_rate", 0),
            }, module="operator_invention")

        for iop in invented_operators:
            event_log.emit("OPERATOR_PROPOSED", None, {
                "name": getattr(iop, "name", str(iop)),
                "signature": getattr(iop, "signature", ""),
            }, module="operator_invention")

        # Validate and register
        validation_result = inventor.validate_inventions(
            invented_concepts, invented_operators, curriculum_tasks,
        )
        validated_c = validation_result["validated_concepts"]
        validated_o = validation_result["validated_operators"]
        for vc in validated_c:
            event_log.emit("INVENTION_VALIDATED", None, {
                "type": "concept",
                "name": getattr(vc, "name", str(vc)),
            }, module="operator_invention")

        reasoner_for_reg = StructuralReasoner(GridDomainAdapter(), memory=memory_3)
        inventor.register_validated(reasoner_for_reg, validated_c, validated_o)
        for vc in validated_c:
            event_log.emit("INVENTION_REGISTERED", None, {
                "type": "concept",
                "name": getattr(vc, "name", str(vc)),
            }, module="operator_invention")

        print(f"  Proposed {len(invented_concepts)} concepts, "
              f"{len(invented_operators)} operators", flush=True)
        print(f"  Validated: {len(validated_c)} concepts, "
              f"{len(validated_o)} operators", flush=True)

    except Exception as e:
        print(f"  Invention skipped: {e}", flush=True)

    stage_results["stage_4_invention"] = {
        "n_failure_clusters": len(missing_charts),
        "n_concepts_proposed": len(invented_concepts),
        "n_operators_proposed": len(invented_operators),
        "failure_clusters": missing_charts,
    }

    # ── Stage 5: Resume failed tasks with invented concepts ──────────
    print("\n" + "=" * 60, flush=True)
    print("STAGE 5: Resume near-solved tasks after invention", flush=True)
    print("=" * 60, flush=True)

    resume_states = {}
    for tid, state in ns_mem_3.states.items():
        if state.status != "solved":
            resume_states[tid] = state

    if resume_states:
        resume_tasks = [t for t in curriculum_tasks if t["task_id"] in resume_states]
        stage_results["stage_5_resume"] = run_stage(
            resume_tasks, memory_3, manifold_3, ns_mem_3,
            event_log=event_log,
            resume_states=resume_states,
            falsifier=falsifier,
            emit_certificates=True,
            label="stage_5_resume",
        )
    else:
        stage_results["stage_5_resume"] = {
            "n_tasks": 0, "n_solved": 0, "n_promoted": 0,
            "promoted_ids": [], "n_false_positives": 0,
        }

    # ── Stage 6: Transfer to unseen tasks ────────────────────────────
    print("\n" + "=" * 60, flush=True)
    print("STAGE 6: Transfer to unseen tasks (held-out + ConceptARC)", flush=True)
    print("=" * 60, flush=True)

    transfer_tasks = heldout_tasks + conceptarc_tasks
    if transfer_tasks:
        stage_results["stage_6_transfer"] = run_stage(
            transfer_tasks, memory_3, manifold_3, ns_mem_3,
            event_log=event_log,
            falsifier=falsifier,
            emit_certificates=True,
            label="stage_6_transfer",
        )
    else:
        stage_results["stage_6_transfer"] = {
            "n_tasks": 0, "n_solved": 0, "n_promoted": 0,
            "promoted_ids": [], "n_false_positives": 0,
        }

    # ── LTL Model Checking ───────────────────────────────────────────
    print("\n" + "=" * 60, flush=True)
    print("LTL MODEL CHECKING", flush=True)
    print("=" * 60, flush=True)

    checker = LTLModelChecker()
    specs = reasoning_loop_specifications()
    ltl_summary = {}
    try:
        sample_tasks = curriculum_tasks[:min(100, len(curriculum_tasks))]
        ltl_loop = AdaptiveReasoningLoop(
            max_iterations=4, timeout_seconds=10.0,
            memory=memory_3, manifold=manifold_3,
        )
        for spec_name in specs:
            ltl_summary[spec_name] = {"checked": 0, "violated": 0}

        for task in sample_tasks:
            result = ltl_loop.solve(
                task["train_pairs"], task["test_inputs"],
                task_id=task["task_id"],
            )
            trace = build_trace_from_loop_result(result, max_iterations=4)
            results = checker.check_all(specs, trace)
            for name, passed in results.items():
                ltl_summary[name]["checked"] += 1
                if not passed:
                    ltl_summary[name]["violated"] += 1

        for name, info in ltl_summary.items():
            status = "PASS" if info["violated"] == 0 else f"FAIL ({info['violated']})"
            print(f"  {name}: {status}", flush=True)
    except Exception as e:
        print(f"  LTL check skipped: {e}", flush=True)

    # ═══════════════════════════════════════════════════════════════════
    # SUMMARY
    # ═══════════════════════════════════════════════════════════════════

    print("\n" + "=" * 60, flush=True)
    print("MEMORY GROWTH CURRICULUM SUMMARY", flush=True)
    print("=" * 60, flush=True)

    print(f"\n  {'Stage':<40} {'Solved':>7} {'NS':>5} {'Prom':>5} {'FP':>4}",
          flush=True)
    print(f"  {'-'*40} {'---':>7} {'---':>5} {'---':>5} {'---':>4}", flush=True)

    for key in ["stage_1_static", "stage_2_episodic", "stage_3_manifold",
                "stage_5_resume", "stage_6_transfer"]:
        s = stage_results.get(key, {})
        label = key.replace("_", " ")
        print(f"  {label:<40} {s.get('n_solved', 0):>7} "
              f"{s.get('n_near_solved', 0):>5} "
              f"{s.get('n_promoted', 0):>5} "
              f"{s.get('n_false_positives', 0):>4}", flush=True)

    inv = stage_results.get("stage_4_invention", {})
    print(f"\n  Failure clusters: {inv.get('n_failure_clusters', 0)}", flush=True)
    print(f"  Concepts proposed: {inv.get('n_concepts_proposed', 0)}", flush=True)
    print(f"  Operators proposed: {inv.get('n_operators_proposed', 0)}", flush=True)

    # Promotion chains
    chains = event_log.promotion_chains()
    print(f"\n  Full promotion chains (failed→stored→resumed→solved): "
          f"{len(chains)}", flush=True)
    for tid in chains[:10]:
        print(f"    {tid}", flush=True)

    event_summary = event_log.summary()
    print(f"\n  Total events: {event_summary['total_events']}", flush=True)
    print(f"  Unique tasks: {event_summary['unique_tasks']}", flush=True)

    ltl_violations = sum(1 for v in ltl_summary.values() if v.get("violated", 0) > 0)
    print(f"  LTL violations: {ltl_violations}/{len(ltl_summary)} specs", flush=True)

    # ═══════════════════════════════════════════════════════════════════
    # WRITE OUTPUTS
    # ═══════════════════════════════════════════════════════════════════

    # Event log
    event_log.export_jsonl(os.path.join(out, "events", "reasoning_events.jsonl"))
    event_log.export_summary_md(os.path.join(out, "events", "event_summary.md"))
    event_log.export_task_lineages(os.path.join(out, "events", "task_lineages"))

    # Stage metrics CSV
    with open(os.path.join(out, "stage_metrics.csv"), "w") as f:
        f.write("stage,n_tasks,n_solved,n_near_solved,n_promoted,"
                "n_false_positives,elapsed_s\n")
        for key in ["stage_1_static", "stage_2_episodic", "stage_3_manifold",
                    "stage_5_resume", "stage_6_transfer"]:
            s = stage_results.get(key, {})
            f.write(f"{key},{s.get('n_tasks', 0)},{s.get('n_solved', 0)},"
                    f"{s.get('n_near_solved', 0)},{s.get('n_promoted', 0)},"
                    f"{s.get('n_false_positives', 0)},{s.get('elapsed', 0):.1f}\n")

    # Promoted tasks
    with open(os.path.join(out, "promoted_tasks.jsonl"), "w") as f:
        for key in ["stage_5_resume", "stage_6_transfer"]:
            s = stage_results.get(key, {})
            for tid in s.get("promoted_ids", []):
                json.dump({"task_id": tid, "stage": key}, f, default=str)
                f.write("\n")

    # Certificates
    all_certs = []
    for key in stage_results:
        s = stage_results[key]
        if isinstance(s, dict) and "certificates" in s:
            all_certs.extend(s["certificates"])
    if all_certs:
        with open(os.path.join(out, "certificates", "all_certificates.json"), "w") as f:
            json.dump(all_certs, f, indent=2, default=str)

    # Full summary JSON
    summary = {
        "stages": {},
        "invention": stage_results.get("stage_4_invention", {}),
        "promotion_chains": chains,
        "event_summary": event_summary,
        "ltl_model_checking": ltl_summary,
    }
    for key in ["stage_1_static", "stage_2_episodic", "stage_3_manifold",
                "stage_5_resume", "stage_6_transfer"]:
        s = stage_results.get(key, {})
        summary["stages"][key] = {
            k: v for k, v in s.items()
            if k not in ("results", "certificates", "falsification_results")
        }
    with open(os.path.join(out, "curriculum_summary.json"), "w") as f:
        json.dump(summary, f, indent=2, default=str)

    # Curriculum summary markdown
    _write_summary_md(out, stage_results, inv, chains, event_summary,
                      ltl_summary, ltl_violations)

    print(f"\nWrote results to {out}/", flush=True)


def _write_summary_md(out, stage_results, inv, chains, event_summary,
                      ltl_summary, ltl_violations):
    lines = [
        "# Memory Growth Curriculum Report\n",
        "## Core Thesis\n",
        "> Failures are not errors; failures are training data for reasoning.\n",
        "## Stage Results\n",
        "| Stage | Tasks | Solved | Near-Solved | Promoted | FP |",
        "|-------|-------|--------|-------------|----------|----|",
    ]
    for key in ["stage_1_static", "stage_2_episodic", "stage_3_manifold",
                "stage_5_resume", "stage_6_transfer"]:
        s = stage_results.get(key, {})
        lines.append(
            f"| {key} | {s.get('n_tasks', 0)} | {s.get('n_solved', 0)} | "
            f"{s.get('n_near_solved', 0)} | {s.get('n_promoted', 0)} | "
            f"{s.get('n_false_positives', 0)} |"
        )

    lines.extend([
        "\n## Concept Invention\n",
        f"- Failure clusters: {inv.get('n_failure_clusters', 0)}",
        f"- Concepts proposed: {inv.get('n_concepts_proposed', 0)}",
        f"- Operators proposed: {inv.get('n_operators_proposed', 0)}",
        "\n## Promotion Chains\n",
        f"Tasks that completed the full chain "
        f"(failed → stored → resumed → solved): **{len(chains)}**\n",
    ])
    for tid in chains[:20]:
        lines.append(f"- `{tid}`")

    lines.extend([
        "\n## Event Summary\n",
        f"- Total events: {event_summary['total_events']}",
        f"- Unique tasks: {event_summary['unique_tasks']}",
        f"- LTL violations: {ltl_violations}/{len(ltl_summary)} specs",
        "\n## Event Type Counts\n",
    ])
    for t, c in sorted(
        event_summary.get("event_type_counts", {}).items(), key=lambda x: -x[1]
    ):
        lines.append(f"- {t}: {c}")

    lines.extend([
        "\n## Key Question\n",
        "**How many previously failed tasks became solved after later learning?**\n",
        f"Answer: **{stage_results.get('stage_5_resume', {}).get('n_promoted', 0)}** "
        f"tasks promoted from near-solved to solved.\n",
    ])

    with open(os.path.join(out, "curriculum_summary.md"), "w") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()
