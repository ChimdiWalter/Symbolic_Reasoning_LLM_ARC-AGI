#!/usr/bin/env python3
"""Phase D: Deep memory-growth / cumulative-learning experiment.

Tests whether episodic memory, near-solved memory, failure clustering,
concept/operator invention, and resume actually help solve more tasks.

Stages:
  1. Static baseline
  2. Episodic memory
  3. Near-solved memory
  4. Failure clustering
  5. Concept/operator invention from failures
  6. Resume previously failed tasks
  7. Held-out transfer to unseen ARC/ConceptARC tasks
  8. Cross-domain transfer if available
"""
import argparse
import csv
import json
import numpy as np
import os
import sys
import time
import traceback
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reasoning_project.reasoning_engine import (
    StructuralReasoner, GridDomainAdapter, ReasoningMemory, WorkingMemory,
    solve_task_reasoning,
)
from reasoning_project.adaptive_loop import AdaptiveReasoningLoop
from reasoning_project.portfolio import PortfolioResult
from reasoning_project.near_solved_memory import NearSolvedMemory, NearSolvedTaskState
from reasoning_project.operator_invention import OperatorInventor
from reasoning_project.certificates import CertificateBuilder
from reasoning_project.arc_adapter import load_arc_tasks, arc_task_to_reasoning_task, evaluate_arc_prediction
from reasoning_project.evaluation import evaluate_prediction
from reasoning_project.events import ReasoningEventLog
from reasoning_project.utils import ensure_dir, utc_timestamp


@dataclass
class StageMetrics:
    stage: int
    stage_name: str
    tasks_attempted: int = 0
    tasks_solved: int = 0
    tasks_solved_new: int = 0
    near_solved_stored: int = 0
    failure_clusters: int = 0
    concepts_proposed: int = 0
    operators_proposed: int = 0
    operators_validated: int = 0
    promotions: int = 0
    false_positives: int = 0
    certificates: int = 0
    previously_failed_now_solved: int = 0
    reusable_abstractions: int = 0
    runtime_seconds: float = 0.0


@dataclass
class TaskResult:
    task_id: str
    stage: int
    solved: bool
    solver: Optional[str] = None
    near_solved: bool = False
    operator_proposed: bool = False
    operator_validated: bool = False
    operator_promoted: bool = False
    certificate_emitted: bool = False
    false_positive: bool = False
    runtime_seconds: float = 0.0
    failure_type: Optional[str] = None
    previously_failed: bool = False
    memory_assisted: bool = False


def load_checkpoint(output_dir: Path) -> dict:
    cp = output_dir / "checkpoint.json"
    if cp.exists():
        with open(cp) as f:
            return json.load(f)
    return {"completed_stages": [], "all_solved_ids": [], "all_failed_ids": []}


def save_checkpoint(output_dir: Path, state: dict):
    with open(output_dir / "checkpoint.json", "w") as f:
        json.dump(state, f, indent=2)


def run_static_baseline(tasks, adapter, max_tasks=200) -> Tuple[List[TaskResult], StageMetrics]:
    """Stage 1: Static portfolio, no memory."""
    metrics = StageMetrics(stage=1, stage_name="static_baseline")
    results = []
    reasoner = StructuralReasoner(adapter, memory=None)

    for i, (tid, task) in enumerate(tasks[:max_tasks]):
        t0 = time.time()
        try:
            train_pairs = [(ex["input"], ex["output"]) for ex in task["train"]]
            test_inputs = [ex["input"] for ex in task["test"]]
            result = reasoner.solve(train_pairs, test_inputs)
            solved = False
            meta = {}
            if result is not None:
                preds, meta = result
                if preds and "test" in task:
                    for pred, tst in zip(preds, task["test"]):
                        if tst.get("output") is not None and np.array_equal(pred, tst["output"]):
                            solved = True
                            break
                elif preds and meta.get("training_fit", 0) >= len(train_pairs):
                    solved = True
            rt = time.time() - t0
            results.append(TaskResult(
                task_id=tid, stage=1, solved=solved,
                solver=meta.get("solver") if solved else None,
                runtime_seconds=rt,
                failure_type=None if solved else meta.get("failure_type", "unknown"),
            ))
            if solved:
                metrics.tasks_solved += 1
        except Exception as e:
            rt = time.time() - t0
            results.append(TaskResult(
                task_id=tid, stage=1, solved=False,
                runtime_seconds=rt, failure_type=f"error:{type(e).__name__}",
            ))
        metrics.tasks_attempted += 1
        metrics.runtime_seconds += rt
    return results, metrics


def run_episodic_memory(tasks, adapter, prior_results, max_tasks=200) -> Tuple[List[TaskResult], StageMetrics]:
    """Stage 2: With episodic memory from stage 1 successes."""
    metrics = StageMetrics(stage=2, stage_name="episodic_memory")
    results = []
    solved_ids = {r.task_id for r in prior_results if r.solved}
    failed_ids = {r.task_id for r in prior_results if not r.solved}

    memory = ReasoningMemory()
    for r in prior_results:
        if r.solved:
            for tid, task in tasks:
                if tid == r.task_id:
                    train_pairs = [(ex["input"], ex["output"]) for ex in task["train"]]
                    sig = memory.compute_task_signature(adapter, train_pairs)
                    memory.store_episode(sig, {"solver": r.solver, "task_id": tid})
                    break

    reasoner = StructuralReasoner(adapter, memory=memory)

    for tid, task in tasks[:max_tasks]:
        if tid in solved_ids:
            continue
        t0 = time.time()
        try:
            train_pairs = [(ex["input"], ex["output"]) for ex in task["train"]]
            test_inputs = [ex["input"] for ex in task["test"]]
            result = reasoner.solve(train_pairs, test_inputs)
            solved = False
            meta = {}
            if result is not None:
                preds, meta = result
                if preds and "test" in task:
                    for pred, tst in zip(preds, task["test"]):
                        if tst.get("output") is not None and np.array_equal(pred, tst["output"]):
                            solved = True
                            break
                elif preds and meta.get("training_fit", 0) >= len(train_pairs):
                    solved = True
            rt = time.time() - t0
            mem_used = meta.get("memory_retrievals_used", 0) > 0
            results.append(TaskResult(
                task_id=tid, stage=2, solved=solved,
                solver=meta.get("solver") if solved else None,
                runtime_seconds=rt,
                failure_type=None if solved else meta.get("failure_type", "unknown"),
                previously_failed=tid in failed_ids,
                memory_assisted=mem_used,
            ))
            if solved:
                metrics.tasks_solved += 1
                if tid in failed_ids:
                    metrics.tasks_solved_new += 1
                    metrics.previously_failed_now_solved += 1
        except Exception as e:
            rt = time.time() - t0
            results.append(TaskResult(
                task_id=tid, stage=2, solved=False,
                runtime_seconds=rt, failure_type=f"error:{type(e).__name__}",
                previously_failed=tid in failed_ids,
            ))
        metrics.tasks_attempted += 1
        metrics.runtime_seconds += rt
    return results, metrics


def run_near_solved_memory(tasks, adapter, prior_results, max_tasks=200) -> Tuple[List[TaskResult], StageMetrics]:
    """Stage 3: Collect near-solved states."""
    metrics = StageMetrics(stage=3, stage_name="near_solved_memory")
    results = []
    solved_ids = {r.task_id for r in prior_results if r.solved}

    ns_memory = NearSolvedMemory()
    memory = ReasoningMemory()
    reasoner = StructuralReasoner(adapter, memory=memory)

    for tid, task in tasks[:max_tasks]:
        if tid in solved_ids:
            continue
        t0 = time.time()
        try:
            train_pairs = [(ex["input"], ex["output"]) for ex in task["train"]]
            test_inputs = [ex["input"] for ex in task["test"]]

            loop = AdaptiveReasoningLoop(adapter, memory=memory)
            loop_result = loop.run(train_pairs, test_inputs, max_iterations=3)

            solved = False
            if loop_result.solved and loop_result.predictions:
                if "test" in task:
                    for pred, tst in zip(loop_result.predictions, task["test"]):
                        if tst.get("output") is not None and np.array_equal(pred, tst["output"]):
                            solved = True
                            break
                else:
                    solved = True

            near_solved = False
            if not solved and loop_result.diagnosis_trace:
                last_diag = loop_result.diagnosis_trace[-1]
                if hasattr(last_diag, 'best_prop_score') and last_diag.best_prop_score and last_diag.best_prop_score > 0.5:
                    state = NearSolvedTaskState(
                        task_id=tid,
                        manifold_point=None,
                        active_chart=None,
                        best_hypothesis=loop_result.hypothesis if hasattr(loop_result, 'hypothesis') else None,
                        hypothesis_score=last_diag.best_prop_score,
                        train_fit=getattr(loop_result, 'training_fit', 0),
                        failure_type=last_diag.failure_type if hasattr(last_diag, 'failure_type') else "unknown",
                        proposed_repairs=[],
                    )
                    ns_memory.store_partial(state)
                    near_solved = True
                    metrics.near_solved_stored += 1

            rt = time.time() - t0
            results.append(TaskResult(
                task_id=tid, stage=3, solved=solved,
                near_solved=near_solved,
                runtime_seconds=rt,
                failure_type=None if solved else "near_solved" if near_solved else "not_near_solved",
            ))
            if solved:
                metrics.tasks_solved += 1
        except Exception as e:
            rt = time.time() - t0
            results.append(TaskResult(
                task_id=tid, stage=3, solved=False,
                runtime_seconds=rt, failure_type=f"error:{type(e).__name__}",
            ))
        metrics.tasks_attempted += 1
        metrics.runtime_seconds += rt

    return results, metrics


def run_failure_clustering(prior_results, ns_memory) -> Tuple[dict, StageMetrics]:
    """Stage 4: Cluster failures by type."""
    metrics = StageMetrics(stage=4, stage_name="failure_clustering")
    clusters = defaultdict(list)

    for r in prior_results:
        if not r.solved and r.failure_type:
            clusters[r.failure_type].append(r.task_id)

    metrics.failure_clusters = len(clusters)
    return dict(clusters), metrics


def run_concept_operator_invention(tasks, adapter, clusters, ns_memory, prior_results, max_tasks=200) -> Tuple[List[TaskResult], StageMetrics]:
    """Stage 5: Invent concepts/operators from failure clusters and near-solved states."""
    metrics = StageMetrics(stage=5, stage_name="concept_operator_invention")
    results = []
    solved_ids = {r.task_id for r in prior_results if r.solved}

    inventor = OperatorInventor()
    memory = ReasoningMemory()

    try:
        mined = inventor.mine_from_near_solved(ns_memory)
        for ftype, states in mined.items():
            metrics.failure_clusters += 1
    except Exception:
        mined = {}

    try:
        all_props = adapter.property_names() if hasattr(adapter, 'property_names') else []
        concepts = inventor.propose_concepts(mined, all_props) if mined else []
        metrics.concepts_proposed = len(concepts)
    except Exception:
        concepts = []

    reasoner = StructuralReasoner(adapter, memory=memory)

    try:
        operators = inventor.propose_operators(mined, reasoner) if mined else []
        metrics.operators_proposed = len(operators)
        for op in operators:
            if hasattr(op, 'validation_gain') and op.validation_gain > 0:
                metrics.operators_validated += 1
    except Exception:
        operators = []

    for tid, task in tasks[:max_tasks]:
        if tid in solved_ids:
            continue
        t0 = time.time()
        try:
            train_pairs = [(ex["input"], ex["output"]) for ex in task["train"]]
            test_inputs = [ex["input"] for ex in task["test"]]
            solve_result = reasoner.solve(train_pairs, test_inputs)
            solved = False
            meta = {}
            if solve_result is not None:
                preds, meta = solve_result
                if preds and "test" in task:
                    for pred, tst in zip(preds, task["test"]):
                        if tst.get("output") is not None and np.array_equal(pred, tst["output"]):
                            solved = True
                            break
            rt = time.time() - t0
            results.append(TaskResult(
                task_id=tid, stage=5, solved=solved,
                solver=meta.get("solver") if solved else None,
                operator_proposed=meta.get("operator_proposed", False),
                operator_validated=meta.get("operator_validated", False),
                operator_promoted=meta.get("operator_promoted", False),
                runtime_seconds=rt,
                previously_failed=True,
            ))
            if solved:
                metrics.tasks_solved += 1
                metrics.previously_failed_now_solved += 1
        except Exception as e:
            rt = time.time() - t0
            results.append(TaskResult(
                task_id=tid, stage=5, solved=False,
                runtime_seconds=rt, failure_type=f"error:{type(e).__name__}",
            ))
        metrics.tasks_attempted += 1
        metrics.runtime_seconds += rt
    return results, metrics


def run_resume_failed(tasks, adapter, all_results, ns_memory, max_tasks=100) -> Tuple[List[TaskResult], StageMetrics]:
    """Stage 6: Resume previously failed tasks with enriched state."""
    metrics = StageMetrics(stage=6, stage_name="resume_failed")
    results = []

    solved_ids = {r.task_id for r in all_results if r.solved}
    failed_ids = [r.task_id for r in all_results if not r.solved and r.near_solved]
    failed_set = set(failed_ids[:max_tasks])

    memory = ReasoningMemory()
    for r in all_results:
        if r.solved:
            for tid, task in tasks:
                if tid == r.task_id:
                    train_pairs = [(ex["input"], ex["output"]) for ex in task["train"]]
                    sig = memory.compute_task_signature(adapter, train_pairs)
                    memory.store_episode(sig, {"solver": r.solver, "task_id": tid})
                    break

    for tid, task in tasks:
        if tid not in failed_set:
            continue
        t0 = time.time()
        try:
            train_pairs = [(ex["input"], ex["output"]) for ex in task["train"]]
            test_inputs = [ex["input"] for ex in task["test"]]
            loop = AdaptiveReasoningLoop(adapter, memory=memory)
            loop_result = loop.run(train_pairs, test_inputs, max_iterations=5)
            solved = False
            if loop_result.solved and loop_result.predictions:
                if "test" in task:
                    for pred, tst in zip(loop_result.predictions, task["test"]):
                        if tst.get("output") is not None and np.array_equal(pred, tst["output"]):
                            solved = True
                            break
                else:
                    solved = True
            rt = time.time() - t0
            results.append(TaskResult(
                task_id=tid, stage=6, solved=solved,
                runtime_seconds=rt,
                previously_failed=True,
                memory_assisted=True,
            ))
            if solved:
                metrics.tasks_solved += 1
                metrics.previously_failed_now_solved += 1
        except Exception as e:
            rt = time.time() - t0
            results.append(TaskResult(
                task_id=tid, stage=6, solved=False,
                runtime_seconds=rt, failure_type=f"error:{type(e).__name__}",
            ))
        metrics.tasks_attempted += 1
        metrics.runtime_seconds += rt
    return results, metrics


def run_heldout_transfer(heldout_tasks, adapter, memory, max_tasks=100) -> Tuple[List[TaskResult], StageMetrics]:
    """Stage 7: Held-out transfer to unseen tasks."""
    metrics = StageMetrics(stage=7, stage_name="heldout_transfer")
    results = []
    reasoner = StructuralReasoner(adapter, memory=memory)

    for tid, task in heldout_tasks[:max_tasks]:
        t0 = time.time()
        try:
            train_pairs = [(ex["input"], ex["output"]) for ex in task["train"]]
            test_inputs = [ex["input"] for ex in task["test"]]
            solve_result = reasoner.solve(train_pairs, test_inputs)
            solved = False
            meta = {}
            if solve_result is not None:
                preds, meta = solve_result
                if preds and "test" in task:
                    for pred, tst in zip(preds, task["test"]):
                        if tst.get("output") is not None and np.array_equal(pred, tst["output"]):
                            solved = True
                            break
            rt = time.time() - t0
            results.append(TaskResult(
                task_id=tid, stage=7, solved=solved,
                solver=meta.get("solver") if solved else None,
                runtime_seconds=rt,
                memory_assisted=meta.get("memory_retrievals_used", 0) > 0,
            ))
            if solved:
                metrics.tasks_solved += 1
        except Exception as e:
            rt = time.time() - t0
            results.append(TaskResult(
                task_id=tid, stage=7, solved=False,
                runtime_seconds=rt, failure_type=f"error:{type(e).__name__}",
            ))
        metrics.tasks_attempted += 1
        metrics.runtime_seconds += rt
    return results, metrics


def run_cross_domain_transfer(adapter, memory, max_tasks=50) -> Tuple[List[TaskResult], StageMetrics]:
    """Stage 8: Cross-domain transfer if available."""
    metrics = StageMetrics(stage=8, stage_name="cross_domain_transfer")
    results = []

    try:
        from reasoning_project.benchmark_generator import GraphTaskGenerator
        from reasoning_project.domain_adapters import GraphDomainAdapter
        gen = GraphTaskGenerator(seed=42)
        graph_tasks = gen.generate(n_tasks=max_tasks)
        graph_adapter = GraphDomainAdapter()
        reasoner = StructuralReasoner(graph_adapter, memory=memory)

        for task in graph_tasks:
            tid = task.get("id", f"graph_{metrics.tasks_attempted}")
            t0 = time.time()
            try:
                train_pairs = [(ex["input"], ex["output"]) for ex in task["train"]]
                test_inputs = [ex["input"] for ex in task["test"]]
                solve_result = reasoner.solve(train_pairs, test_inputs)
                meta = {}
                solved = False
                if solve_result is not None:
                    preds, meta = solve_result
                    solved = preds is not None and len(preds) > 0 and meta.get("training_fit", 0) >= len(train_pairs)
                rt = time.time() - t0
                results.append(TaskResult(
                    task_id=tid, stage=8, solved=solved,
                    runtime_seconds=rt, memory_assisted=True,
                ))
                if solved:
                    metrics.tasks_solved += 1
            except Exception as e:
                rt = time.time() - t0
                results.append(TaskResult(
                    task_id=tid, stage=8, solved=False,
                    runtime_seconds=rt, failure_type=f"error:{type(e).__name__}",
                ))
            metrics.tasks_attempted += 1
            metrics.runtime_seconds += rt
    except ImportError:
        pass
    except Exception as e:
        print(f"  Cross-domain transfer failed: {e}")

    return results, metrics


def write_stage_metrics_csv(output_dir: Path, all_metrics: List[StageMetrics]):
    with open(output_dir / "stage_metrics.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "stage", "stage_name", "tasks_attempted", "tasks_solved", "tasks_solved_new",
            "near_solved_stored", "failure_clusters", "concepts_proposed",
            "operators_proposed", "operators_validated", "promotions",
            "false_positives", "certificates", "previously_failed_now_solved",
            "reusable_abstractions", "runtime_seconds",
        ])
        writer.writeheader()
        for m in all_metrics:
            writer.writerow(asdict(m))


def write_promoted_tasks(output_dir: Path, all_results: List[TaskResult]):
    promoted = [r for r in all_results if r.operator_promoted]
    with open(output_dir / "promoted_tasks.jsonl", "w") as f:
        for r in promoted:
            f.write(json.dumps(asdict(r)) + "\n")


def write_events(output_dir: Path, all_results: List[TaskResult]):
    with open(output_dir / "events.jsonl", "w") as f:
        for r in all_results:
            f.write(json.dumps(asdict(r)) + "\n")


def write_failure_clusters_json(output_dir: Path, clusters: dict):
    with open(output_dir / "failure_clusters.json", "w") as f:
        json.dump(clusters, f, indent=2)


def write_summary(output_dir: Path, all_metrics: List[StageMetrics], all_results: List[TaskResult], clusters: dict):
    cumulative_solved = set()
    stage_gains = []
    for m in all_metrics:
        stage_results = [r for r in all_results if r.stage == m.stage]
        new_solved = {r.task_id for r in stage_results if r.solved} - cumulative_solved
        cumulative_solved |= new_solved
        stage_gains.append((m.stage_name, len(new_solved), len(cumulative_solved)))

    memory_driven_solves = [r for r in all_results if r.solved and r.previously_failed and r.memory_assisted]
    resume_solves = [r for r in all_results if r.solved and r.previously_failed]

    lines = [
        "# Deep Memory Growth Curriculum — Summary",
        f"\nGenerated: {datetime.now().isoformat()}",
        "",
        "## Stage Progression",
        "",
        "| Stage | New Solved | Cumulative Solved |",
        "|-------|-----------|-------------------|",
    ]
    for name, new, cum in stage_gains:
        lines.append(f"| {name} | {new} | {cum} |")

    lines += [
        "",
        "## Key Results",
        "",
        f"- Total unique tasks solved: {len(cumulative_solved)}",
        f"- Previously failed tasks later solved: {len(resume_solves)}",
        f"- Memory-assisted solves: {len(memory_driven_solves)}",
        f"- Failure clusters identified: {len(clusters)}",
        "",
        "## Claim Assessment",
        "",
    ]

    if len(resume_solves) > 0:
        lines.append(f"**Supported:** Memory-driven resume solved {len(resume_solves)} previously failed tasks.")
    else:
        lines.append("**Not supported:** No previously failed tasks were solved by memory/invention/resume.")

    if len(memory_driven_solves) > 0:
        lines.append(f"**Supported:** {len(memory_driven_solves)} solves were memory-assisted.")
    else:
        lines.append("**Not supported:** No memory-assisted solves detected.")

    lines += [
        "",
        "## Failure Cluster Summary",
        "",
    ]
    for ftype, tids in sorted(clusters.items(), key=lambda x: -len(x[1])):
        lines.append(f"- {ftype}: {len(tids)} tasks")

    with open(output_dir / "summary.md", "w") as f:
        f.write("\n".join(lines) + "\n")


def main():
    parser = argparse.ArgumentParser(description="Deep memory-growth curriculum")
    parser.add_argument("--output-dir", default="outputs/deep_project_completion/memory_growth_deep")
    parser.add_argument("--arc-root", default="data/arc")
    parser.add_argument("--max-tasks-per-stage", type=int, default=200)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "certificates").mkdir(exist_ok=True)

    with open(output_dir / "status.json", "w") as f:
        json.dump({"status": "running", "started": utc_timestamp()}, f)

    import logging
    log_path = output_dir / "run.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(message)s",
        handlers=[logging.FileHandler(log_path), logging.StreamHandler()],
    )
    log = logging.getLogger(__name__)

    log.info("=== Deep Memory Growth Curriculum ===")
    log.info(f"Output: {output_dir}")

    checkpoint = load_checkpoint(output_dir) if args.resume else {"completed_stages": [], "all_solved_ids": [], "all_failed_ids": []}

    log.info("Loading ARC tasks...")
    arc_root = Path(args.arc_root)
    all_arc = load_arc_tasks(str(arc_root))
    task_list = [
        (t.task_id, {
            "train": [{"input": ex.input_grid, "output": ex.output_grid} for ex in t.train],
            "test": [{"input": ex.input_grid, "output": ex.output_grid} for ex in t.test],
        })
        for t in all_arc
    ]
    n = min(args.max_tasks_per_stage, len(task_list))

    train_tasks = task_list[:n]
    heldout_tasks = task_list[n:n + n // 2] if len(task_list) > n else []

    adapter = GridDomainAdapter()
    all_results: List[TaskResult] = []
    all_metrics: List[StageMetrics] = []
    ns_memory = NearSolvedMemory()
    clusters = {}

    # Stage 1: Static baseline
    if 1 not in checkpoint.get("completed_stages", []):
        log.info("--- Stage 1: Static baseline ---")
        s1_results, s1_metrics = run_static_baseline(train_tasks, adapter, max_tasks=n)
        all_results.extend(s1_results)
        all_metrics.append(s1_metrics)
        log.info(f"  Solved: {s1_metrics.tasks_solved}/{s1_metrics.tasks_attempted}")
        checkpoint["completed_stages"].append(1)
        save_checkpoint(output_dir, checkpoint)
    else:
        log.info("Stage 1 already complete, skipping")
        s1_metrics = StageMetrics(stage=1, stage_name="static_baseline")

    # Stage 2: Episodic memory
    if 2 not in checkpoint.get("completed_stages", []):
        log.info("--- Stage 2: Episodic memory ---")
        s2_results, s2_metrics = run_episodic_memory(train_tasks, adapter, all_results, max_tasks=n)
        all_results.extend(s2_results)
        all_metrics.append(s2_metrics)
        log.info(f"  Solved: {s2_metrics.tasks_solved}/{s2_metrics.tasks_attempted} (new: {s2_metrics.tasks_solved_new})")
        checkpoint["completed_stages"].append(2)
        save_checkpoint(output_dir, checkpoint)
    else:
        log.info("Stage 2 already complete, skipping")
        s2_metrics = StageMetrics(stage=2, stage_name="episodic_memory")

    # Stage 3: Near-solved memory
    if 3 not in checkpoint.get("completed_stages", []):
        log.info("--- Stage 3: Near-solved memory ---")
        s3_results, s3_metrics = run_near_solved_memory(train_tasks, adapter, all_results, max_tasks=n)
        all_results.extend(s3_results)
        all_metrics.append(s3_metrics)
        log.info(f"  Solved: {s3_metrics.tasks_solved}/{s3_metrics.tasks_attempted}, near-solved: {s3_metrics.near_solved_stored}")
        checkpoint["completed_stages"].append(3)
        save_checkpoint(output_dir, checkpoint)
    else:
        log.info("Stage 3 already complete, skipping")
        s3_metrics = StageMetrics(stage=3, stage_name="near_solved_memory")

    # Stage 4: Failure clustering
    if 4 not in checkpoint.get("completed_stages", []):
        log.info("--- Stage 4: Failure clustering ---")
        clusters, s4_metrics = run_failure_clustering(all_results, ns_memory)
        all_metrics.append(s4_metrics)
        log.info(f"  Clusters: {s4_metrics.failure_clusters}")
        checkpoint["completed_stages"].append(4)
        save_checkpoint(output_dir, checkpoint)
    else:
        log.info("Stage 4 already complete, skipping")

    # Stage 5: Concept/operator invention
    if 5 not in checkpoint.get("completed_stages", []):
        log.info("--- Stage 5: Concept/operator invention ---")
        s5_results, s5_metrics = run_concept_operator_invention(
            train_tasks, adapter, clusters, ns_memory, all_results, max_tasks=n
        )
        all_results.extend(s5_results)
        all_metrics.append(s5_metrics)
        log.info(f"  Solved: {s5_metrics.tasks_solved}/{s5_metrics.tasks_attempted}")
        log.info(f"  Concepts proposed: {s5_metrics.concepts_proposed}, operators: {s5_metrics.operators_proposed}")
        checkpoint["completed_stages"].append(5)
        save_checkpoint(output_dir, checkpoint)
    else:
        log.info("Stage 5 already complete, skipping")

    # Stage 6: Resume failed
    if 6 not in checkpoint.get("completed_stages", []):
        log.info("--- Stage 6: Resume previously failed ---")
        s6_results, s6_metrics = run_resume_failed(
            train_tasks, adapter, all_results, ns_memory, max_tasks=n // 2
        )
        all_results.extend(s6_results)
        all_metrics.append(s6_metrics)
        log.info(f"  Resumed solved: {s6_metrics.previously_failed_now_solved}")
        checkpoint["completed_stages"].append(6)
        save_checkpoint(output_dir, checkpoint)
    else:
        log.info("Stage 6 already complete, skipping")

    # Stage 7: Held-out transfer
    if 7 not in checkpoint.get("completed_stages", []):
        log.info("--- Stage 7: Held-out transfer ---")
        memory = ReasoningMemory()
        s7_results, s7_metrics = run_heldout_transfer(heldout_tasks, adapter, memory, max_tasks=n // 2)
        all_results.extend(s7_results)
        all_metrics.append(s7_metrics)
        log.info(f"  Held-out solved: {s7_metrics.tasks_solved}/{s7_metrics.tasks_attempted}")
        checkpoint["completed_stages"].append(7)
        save_checkpoint(output_dir, checkpoint)
    else:
        log.info("Stage 7 already complete, skipping")

    # Stage 8: Cross-domain transfer
    if 8 not in checkpoint.get("completed_stages", []):
        log.info("--- Stage 8: Cross-domain transfer ---")
        memory = ReasoningMemory()
        s8_results, s8_metrics = run_cross_domain_transfer(adapter, memory, max_tasks=50)
        all_results.extend(s8_results)
        all_metrics.append(s8_metrics)
        log.info(f"  Cross-domain solved: {s8_metrics.tasks_solved}/{s8_metrics.tasks_attempted}")
        checkpoint["completed_stages"].append(8)
        save_checkpoint(output_dir, checkpoint)
    else:
        log.info("Stage 8 already complete, skipping")

    # Write all outputs
    log.info("Writing outputs...")
    write_stage_metrics_csv(output_dir, all_metrics)
    write_promoted_tasks(output_dir, all_results)
    write_events(output_dir, all_results)
    write_failure_clusters_json(output_dir, clusters)
    write_summary(output_dir, all_metrics, all_results, clusters)

    with open(output_dir / "status.json", "w") as f:
        json.dump({"status": "completed", "finished": utc_timestamp()}, f)

    log.info("=== Done ===")


if __name__ == "__main__":
    main()
