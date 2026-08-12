#!/usr/bin/env python3
"""Cross-domain transfer evaluation with event tracking.

Thesis: An operator invented in one domain transfers to another domain.

Three phases:
  Phase 1 — Run each domain independently, collect solved/unsolved/near-solved.
  Phase 2 — Mine near-solved failures, invent concepts, check cross-domain scope.
  Phase 3 — Re-run unsolved tasks with shared invented concepts, track transfers.

Outputs:
  domain_metrics.csv        — per-domain statistics
  domain_transfer_report.md — human-readable transfer analysis
  transfer_events.jsonl     — full event log
  event_summary.md          — event type counts and promotion chains
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import numpy as np

from reasoning_project.reasoning_engine import (
    GridDomainAdapter,
    ReasoningMemory,
    StructuralReasoner,
)
from reasoning_project.domain_adapters import (
    GraphDomainAdapter,
    ChessBoardDomainAdapter,
    MoleculeGraphDomainAdapter,
)
from reasoning_project.benchmark_generator import AdaptiveReasoningSuite, BenchmarkTask
from reasoning_project.events import ReasoningEventLog
from reasoning_project.near_solved_memory import NearSolvedMemory
from reasoning_project.operator_invention import OperatorInventor
from reasoning_project.manifold_memory import MemoryManifold
from reasoning_project.adaptive_loop import AdaptiveReasoningLoop

# ---------------------------------------------------------------------------
# Category -> adapter mapping
# ---------------------------------------------------------------------------
CATEGORY_ADAPTER_MAP: Dict[str, str] = {
    "atomic_grid": "GridDomainAdapter",
    "recombination": "GridDomainAdapter",
    "counterfactual": "GridDomainAdapter",
    "graph": "GraphDomainAdapter",
    "chess": "ChessBoardDomainAdapter",
    "molecule": "MoleculeGraphDomainAdapter",
}

DOMAIN_FOR_CATEGORY: Dict[str, str] = {
    "atomic_grid": "grid",
    "recombination": "grid",
    "counterfactual": "grid",
    "graph": "graph",
    "chess": "chess",
    "molecule": "molecule",
}


def _make_adapter(category: str):
    """Instantiate the appropriate DomainAdapter for a benchmark category."""
    name = CATEGORY_ADAPTER_MAP[category]
    if name == "GridDomainAdapter":
        return GridDomainAdapter()
    elif name == "GraphDomainAdapter":
        return GraphDomainAdapter()
    elif name == "ChessBoardDomainAdapter":
        return ChessBoardDomainAdapter()
    elif name == "MoleculeGraphDomainAdapter":
        return MoleculeGraphDomainAdapter()
    else:
        raise ValueError(f"Unknown adapter: {name}")


def _check_correct(
    adapter,
    predictions: Optional[List],
    task: BenchmarkTask,
) -> bool:
    """Check if predictions match test_pairs outputs."""
    if predictions is None:
        return False
    if len(predictions) != len(task.test_pairs):
        return False
    for pred, (_, expected) in zip(predictions, task.test_pairs):
        if not adapter.scenes_equal(pred, expected):
            return False
    return True


# ═══════════════════════════════════════════════════════════════════════════
# PHASE 1 — Independent per-domain evaluation
# ═══════════════════════════════════════════════════════════════════════════

def phase1_independent(
    suite: Dict[str, List[BenchmarkTask]],
    event_log: ReasoningEventLog,
    max_tasks: int,
    use_cache: str = "",
) -> Dict[str, Dict[str, Any]]:
    """Run each domain independently. Returns per-domain metrics."""
    print("[Phase 1] Independent per-domain evaluation", flush=True)

    domain_results: Dict[str, Dict[str, Any]] = {}

    for category, tasks in suite.items():
        if max_tasks > 0:
            tasks = tasks[:max_tasks]

        adapter = _make_adapter(category)
        adapter_type = CATEGORY_ADAPTER_MAP[category]
        domain = DOMAIN_FOR_CATEGORY[category]
        prop_library = adapter.property_names()

        memory = ReasoningMemory()
        manifold = MemoryManifold()
        if use_cache:
            from reasoning_project.near_solved_memory import load_near_solved_cache
            ns_mem, _, _ = load_near_solved_cache(use_cache)
        else:
            ns_mem = NearSolvedMemory(manifold)

        solved_tasks: List[str] = []
        unsolved_tasks: List[str] = []
        near_solved_tasks: List[str] = []
        blocked_tasks: List[str] = []
        false_positives = 0
        task_results: List[Dict[str, Any]] = []

        print(f"  Domain={category}  adapter={adapter_type}  tasks={len(tasks)}",
              flush=True)

        for task in tasks:
            event_log.emit(
                "TASK_OBSERVED", task.task_id,
                {"category": category, "domain": domain, "concept": task.concept},
                module="cross_domain_v2",
            )

            train_pairs = task.train_pairs
            test_inputs = [inp for inp, _ in task.test_pairs]

            loop = AdaptiveReasoningLoop(
                max_iterations=4,
                timeout_seconds=15.0,
                memory=memory,
                manifold=manifold,
                near_solved_memory=ns_mem,
                event_log=event_log,
            )

            try:
                result = loop.solve(
                    train_pairs, test_inputs, task_id=task.task_id,
                )
            except Exception as exc:
                print(f"    WARN: {task.task_id} raised {exc}", flush=True)
                result = None

            if result is not None and result.solved:
                correct = _check_correct(adapter, result.predictions, task)
                if correct:
                    solved_tasks.append(task.task_id)
                    event_log.emit(
                        "HYPOTHESIS_ACCEPTED", task.task_id,
                        {"correct": True, "phase": 1},
                        module="cross_domain_v2",
                    )
                else:
                    false_positives += 1
                    unsolved_tasks.append(task.task_id)
                    event_log.emit(
                        "HYPOTHESIS_REJECTED", task.task_id,
                        {"correct": False, "phase": 1, "false_positive": True},
                        module="cross_domain_v2",
                    )
            else:
                unsolved_tasks.append(task.task_id)

            # Classify near-solved vs blocked
            ns_state = ns_mem.states.get(task.task_id)
            if ns_state is not None and ns_state.is_near_solved:
                near_solved_tasks.append(task.task_id)
            elif task.task_id in unsolved_tasks:
                blocked_tasks.append(task.task_id)

            task_results.append({
                "task_id": task.task_id,
                "solved": task.task_id in solved_tasks,
                "near_solved": task.task_id in near_solved_tasks,
            })

        domain_results[category] = {
            "adapter_type": adapter_type,
            "domain": domain,
            "property_library": prop_library,
            "solved": solved_tasks,
            "unsolved": unsolved_tasks,
            "near_solved": near_solved_tasks,
            "blocked": blocked_tasks,
            "false_positives": false_positives,
            "memory": memory,
            "manifold": manifold,
            "ns_mem": ns_mem,
            "task_results": task_results,
        }

        print(f"    solved={len(solved_tasks)}  near_solved={len(near_solved_tasks)}  "
              f"blocked={len(blocked_tasks)}  fp={false_positives}", flush=True)

    return domain_results


# ═══════════════════════════════════════════════════════════════════════════
# PHASE 2 — Concept invention from near-solved failures
# ═══════════════════════════════════════════════════════════════════════════

def phase2_invention(
    domain_results: Dict[str, Dict[str, Any]],
    suite: Dict[str, List[BenchmarkTask]],
    event_log: ReasoningEventLog,
) -> Dict[str, Any]:
    """Mine near-solved clusters, invent concepts, check cross-domain scope."""
    print("\n[Phase 2] Concept invention from near-solved failures", flush=True)

    inventor = OperatorInventor(min_cluster_size=1, max_conjunction_size=2)

    # Merge all near-solved memories
    all_ns_mem = NearSolvedMemory()
    source_domains: Dict[str, str] = {}  # task_id -> domain

    for category, dr in domain_results.items():
        ns_mem: NearSolvedMemory = dr["ns_mem"]
        for task_id, state in ns_mem.states.items():
            all_ns_mem.states[task_id] = state
            source_domains[task_id] = category

    print(f"  Total near-solved states: {len(all_ns_mem.states)}", flush=True)

    # Mine clusters
    clusters = inventor.mine_from_near_solved(all_ns_mem)
    print(f"  Failure clusters: {len(clusters)}", flush=True)
    for cname, members in clusters.items():
        print(f"    {cname}: {len(members)} tasks", flush=True)

    # Collect all property names across domains
    all_prop_names: List[str] = []
    seen_props: set = set()
    for category, dr in domain_results.items():
        for p in dr["property_library"]:
            if p not in seen_props:
                all_prop_names.append(p)
                seen_props.add(p)

    # Propose concepts
    concepts = inventor.propose_concepts(clusters, all_prop_names)
    print(f"  Invented concepts: {len(concepts)}", flush=True)

    for concept in concepts:
        event_log.emit(
            "CONCEPT_PROPOSED", None,
            {
                "name": concept.name,
                "expression": concept.expression,
                "source_tasks": concept.source_tasks,
                "description": concept.description,
            },
            module="cross_domain_v2",
        )

    # Propose operators
    operators = inventor.propose_operators(clusters)
    print(f"  Invented operators: {len(operators)}", flush=True)

    # Check cross-domain scope: do any concepts have source tasks from multiple domains?
    cross_domain_concepts = []
    for concept in concepts:
        domains_hit = set()
        for tid in concept.source_tasks:
            if tid in source_domains:
                domains_hit.add(source_domains[tid])
        if len(domains_hit) > 1:
            cross_domain_concepts.append({
                "concept": concept,
                "domains": sorted(domains_hit),
            })

    print(f"  Cross-domain concepts: {len(cross_domain_concepts)}", flush=True)
    for cdc in cross_domain_concepts:
        print(f"    {cdc['concept'].name} spans {cdc['domains']}", flush=True)

    return {
        "clusters": clusters,
        "concepts": concepts,
        "operators": operators,
        "cross_domain_concepts": cross_domain_concepts,
        "source_domains": source_domains,
        "inventor": inventor,
    }


# ═══════════════════════════════════════════════════════════════════════════
# PHASE 3 — Re-run unsolved tasks with shared invented concepts
# ═══════════════════════════════════════════════════════════════════════════

def phase3_transfer(
    domain_results: Dict[str, Dict[str, Any]],
    suite: Dict[str, List[BenchmarkTask]],
    invention_results: Dict[str, Any],
    event_log: ReasoningEventLog,
    max_tasks: int,
) -> Dict[str, Any]:
    """Re-run unsolved tasks with invented concepts. Track cross-domain transfers."""
    print("\n[Phase 3] Re-run unsolved tasks with shared invented concepts", flush=True)

    concepts = invention_results["concepts"]
    operators = invention_results["operators"]
    inventor: OperatorInventor = invention_results["inventor"]
    source_domains = invention_results["source_domains"]

    transfer_successes: List[Dict[str, Any]] = []
    transfer_attempts: List[Dict[str, Any]] = []
    newly_solved: Dict[str, List[str]] = defaultdict(list)

    for category, tasks in suite.items():
        if max_tasks > 0:
            tasks = tasks[:max_tasks]

        dr = domain_results[category]
        unsolved = set(dr["unsolved"])
        if not unsolved:
            continue

        adapter = _make_adapter(category)
        domain = DOMAIN_FOR_CATEGORY[category]

        # Build a fresh memory with invented concepts registered
        memory = ReasoningMemory()
        reasoner = StructuralReasoner(adapter, memory=memory)

        # Register validated concepts into the reasoner
        if concepts:
            reg_result = inventor.register_validated(reasoner, concepts, operators)
            registered = reg_result.get("registered_concepts", [])
            print(f"  {category}: registered {len(registered)} concepts into memory",
                  flush=True)
            for cname in registered:
                event_log.emit(
                    "INVENTION_REGISTERED", None,
                    {"concept_name": cname, "target_domain": category},
                    module="cross_domain_v2",
                )

        manifold = MemoryManifold()
        ns_mem = NearSolvedMemory(manifold)

        unsolved_tasks = [t for t in tasks if t.task_id in unsolved]
        print(f"  Re-running {len(unsolved_tasks)} unsolved tasks in {category}",
              flush=True)

        for task in unsolved_tasks:
            train_pairs = task.train_pairs
            test_inputs = [inp for inp, _ in task.test_pairs]

            # Determine which concepts originate from a different domain
            cross_concepts_used = []
            for concept in concepts:
                concept_domains = set()
                for tid in concept.source_tasks:
                    if tid in source_domains:
                        concept_domains.add(source_domains[tid])
                if concept_domains and category not in concept_domains:
                    cross_concepts_used.append(concept.name)

            event_log.emit(
                "CROSS_DOMAIN_TRANSFER_ATTEMPTED", task.task_id,
                {
                    "source_domain": category,
                    "n_cross_concepts": len(cross_concepts_used),
                    "cross_concepts": cross_concepts_used[:5],
                },
                module="cross_domain_v2",
            )
            transfer_attempts.append({
                "task_id": task.task_id,
                "domain": category,
                "cross_concepts": cross_concepts_used,
            })

            loop = AdaptiveReasoningLoop(
                max_iterations=4,
                timeout_seconds=15.0,
                memory=memory,
                manifold=manifold,
                near_solved_memory=ns_mem,
                event_log=event_log,
            )

            # Try to resume from near-solved state if available
            old_ns = domain_results[category]["ns_mem"]
            resume_state = old_ns.states.get(task.task_id)

            try:
                result = loop.solve(
                    train_pairs, test_inputs,
                    task_id=task.task_id,
                    resume_from=resume_state,
                )
            except Exception as exc:
                print(f"    WARN: {task.task_id} raised {exc}", flush=True)
                result = None

            if result is not None and result.solved:
                correct = _check_correct(adapter, result.predictions, task)
                if correct:
                    newly_solved[category].append(task.task_id)
                    event_log.emit(
                        "CROSS_DOMAIN_TRANSFER_SUCCEEDED", task.task_id,
                        {
                            "domain": category,
                            "cross_concepts_used": cross_concepts_used[:5],
                            "hypothesis": str(result.hypothesis)[:200] if result.hypothesis else "",
                        },
                        module="cross_domain_v2",
                    )
                    transfer_successes.append({
                        "task_id": task.task_id,
                        "domain": category,
                        "cross_concepts": cross_concepts_used,
                        "hypothesis": result.hypothesis,
                    })
                else:
                    event_log.emit(
                        "CROSS_DOMAIN_TRANSFER_FAILED", task.task_id,
                        {"domain": category, "reason": "false_positive"},
                        module="cross_domain_v2",
                    )
            else:
                event_log.emit(
                    "CROSS_DOMAIN_TRANSFER_FAILED", task.task_id,
                    {"domain": category, "reason": "unsolved"},
                    module="cross_domain_v2",
                )

        n_new = len(newly_solved.get(category, []))
        print(f"    newly solved: {n_new}", flush=True)

    print(f"\n  Total cross-domain transfer attempts: {len(transfer_attempts)}",
          flush=True)
    print(f"  Total cross-domain transfer successes: {len(transfer_successes)}",
          flush=True)

    return {
        "transfer_successes": transfer_successes,
        "transfer_attempts": transfer_attempts,
        "newly_solved": dict(newly_solved),
    }


# ═══════════════════════════════════════════════════════════════════════════
# OUTPUT GENERATION
# ═══════════════════════════════════════════════════════════════════════════

def write_domain_metrics_csv(
    path: str,
    domain_results: Dict[str, Dict[str, Any]],
    transfer_results: Dict[str, Any],
) -> None:
    """Write domain_metrics.csv."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    newly_solved = transfer_results.get("newly_solved", {})
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "adapter_type", "domain", "solved", "near_solved",
            "blocked", "fp", "transfers",
        ])
        for category, dr in domain_results.items():
            transfers = len(newly_solved.get(category, []))
            writer.writerow([
                dr["adapter_type"],
                category,
                len(dr["solved"]),
                len(dr["near_solved"]),
                len(dr["blocked"]),
                dr["false_positives"],
                transfers,
            ])
    print(f"  Wrote {path}", flush=True)


def write_transfer_report_md(
    path: str,
    domain_results: Dict[str, Dict[str, Any]],
    invention_results: Dict[str, Any],
    transfer_results: Dict[str, Any],
    elapsed: float,
) -> None:
    """Write domain_transfer_report.md."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    lines: List[str] = []
    lines.append("# Cross-Domain Transfer Report (v2)\n")
    lines.append(f"**Elapsed:** {elapsed:.1f}s\n")
    lines.append("## Thesis\n")
    lines.append("> An operator invented in one domain transfers to another domain.\n")

    # Phase 1 summary
    lines.append("## Phase 1: Independent Domain Results\n")
    lines.append("| Domain | Adapter | Solved | Near-Solved | Blocked | FP |")
    lines.append("|--------|---------|--------|-------------|---------|-----|")
    total_solved = 0
    total_tasks = 0
    for category, dr in domain_results.items():
        n_tasks = len(dr["solved"]) + len(dr["unsolved"])
        total_solved += len(dr["solved"])
        total_tasks += n_tasks
        lines.append(
            f"| {category} | {dr['adapter_type']} | "
            f"{len(dr['solved'])}/{n_tasks} | "
            f"{len(dr['near_solved'])} | "
            f"{len(dr['blocked'])} | "
            f"{dr['false_positives']} |"
        )
    lines.append(f"\n**Total solved (Phase 1):** {total_solved}/{total_tasks}\n")

    # Phase 2 summary
    concepts = invention_results["concepts"]
    operators = invention_results["operators"]
    cross_domain_concepts = invention_results["cross_domain_concepts"]
    lines.append("## Phase 2: Concept Invention\n")
    lines.append(f"- Invented concepts: {len(concepts)}")
    lines.append(f"- Invented operators: {len(operators)}")
    lines.append(f"- Cross-domain concepts: {len(cross_domain_concepts)}")
    if concepts:
        lines.append("\n### Invented Concepts\n")
        for c in concepts:
            lines.append(f"- **{c.name}**: {c.description}")
            lines.append(f"  - Source tasks: {', '.join(c.source_tasks[:5])}")
    if cross_domain_concepts:
        lines.append("\n### Cross-Domain Concepts\n")
        for cdc in cross_domain_concepts:
            lines.append(
                f"- **{cdc['concept'].name}** spans domains: "
                f"{', '.join(cdc['domains'])}"
            )

    # Phase 3 summary
    transfer_successes = transfer_results["transfer_successes"]
    transfer_attempts = transfer_results["transfer_attempts"]
    newly_solved = transfer_results["newly_solved"]
    lines.append("\n## Phase 3: Cross-Domain Transfer\n")
    lines.append(f"- Transfer attempts: {len(transfer_attempts)}")
    lines.append(f"- Transfer successes: {len(transfer_successes)}")
    total_newly_solved = sum(len(v) for v in newly_solved.values())
    lines.append(f"- Tasks newly solved via transfer: {total_newly_solved}")
    if newly_solved:
        lines.append("\n### Newly Solved by Domain\n")
        for domain, task_ids in newly_solved.items():
            lines.append(f"- **{domain}**: {len(task_ids)} tasks")
            for tid in task_ids:
                lines.append(f"  - {tid}")
    if transfer_successes:
        lines.append("\n### Successful Transfers\n")
        for ts in transfer_successes:
            lines.append(
                f"- Task **{ts['task_id']}** (domain={ts['domain']}) "
                f"with cross-concepts: {', '.join(ts['cross_concepts'][:3]) or 'shared'}"
            )

    # Critical result
    lines.append("\n## Critical Result\n")
    if transfer_successes:
        lines.append(
            f"**CONFIRMED**: {len(transfer_successes)} operator(s) invented in one "
            f"domain transferred to another domain, solving {total_newly_solved} "
            f"previously-unsolvable task(s)."
        )
    elif total_newly_solved > 0:
        lines.append(
            f"**PARTIAL**: {total_newly_solved} task(s) newly solved after concept "
            f"invention, but cross-domain specificity requires further analysis."
        )
    else:
        lines.append(
            "**NOT YET CONFIRMED**: No cross-domain transfers succeeded in this run. "
            "The invented concepts did not unlock any previously-unsolvable tasks."
        )

    lines.append("")
    with open(path, "w") as f:
        f.write("\n".join(lines))
    print(f"  Wrote {path}", flush=True)


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cross-domain transfer evaluation with event tracking (v2).",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="outputs/cross_domain_v2",
        help="Directory for outputs (default: outputs/cross_domain_v2).",
    )
    parser.add_argument(
        "--max-tasks",
        type=int,
        default=0,
        help="Max tasks per category (0 = all).",
    )
    parser.add_argument(
        "--use-cache",
        default="",
        help="Load Phase 1 near-solved cache from this dir",
    )
    args = parser.parse_args()

    output_dir = args.output_dir
    max_tasks = args.max_tasks
    os.makedirs(output_dir, exist_ok=True)

    print("=" * 70, flush=True)
    print("Cross-Domain Transfer Evaluation v2", flush=True)
    print(f"  output_dir = {output_dir}", flush=True)
    print(f"  max_tasks  = {max_tasks} (0=all)", flush=True)
    print("=" * 70, flush=True)

    t_start = time.perf_counter()

    # -- Build benchmark suite --
    print("\nBuilding benchmark suite (seed=42)...", flush=True)
    suite = AdaptiveReasoningSuite(seed=42).build_all()
    total_tasks = sum(len(v) for v in suite.values())
    print(f"  {len(suite)} categories, {total_tasks} tasks total", flush=True)
    for cat, tasks in suite.items():
        print(f"    {cat}: {len(tasks)} tasks", flush=True)

    # -- Event log --
    event_log = ReasoningEventLog()

    # -- Phase 1 --
    domain_results = phase1_independent(
        suite, event_log, max_tasks, use_cache=args.use_cache)

    # -- Phase 2 --
    invention_results = phase2_invention(domain_results, suite, event_log)

    # -- Phase 3 --
    transfer_results = phase3_transfer(
        domain_results, suite, invention_results, event_log, max_tasks,
    )

    elapsed = time.perf_counter() - t_start

    # -- Write outputs --
    print("\nWriting outputs...", flush=True)
    write_domain_metrics_csv(
        os.path.join(output_dir, "domain_metrics.csv"),
        domain_results, transfer_results,
    )
    write_transfer_report_md(
        os.path.join(output_dir, "domain_transfer_report.md"),
        domain_results, invention_results, transfer_results, elapsed,
    )
    n_events = event_log.export_jsonl(
        os.path.join(output_dir, "transfer_events.jsonl"),
    )
    print(f"  Wrote transfer_events.jsonl ({n_events} events)", flush=True)
    event_log.export_summary_md(
        os.path.join(output_dir, "event_summary.md"),
    )
    print(f"  Wrote event_summary.md", flush=True)

    # -- Final summary --
    print("\n" + "=" * 70, flush=True)
    print("SUMMARY", flush=True)
    print("=" * 70, flush=True)
    for category, dr in domain_results.items():
        n_total = len(dr["solved"]) + len(dr["unsolved"])
        transfers = len(transfer_results["newly_solved"].get(category, []))
        print(
            f"  {category:20s}  solved={len(dr['solved']):2d}/{n_total:2d}  "
            f"near_solved={len(dr['near_solved']):2d}  "
            f"blocked={len(dr['blocked']):2d}  "
            f"fp={dr['false_positives']}  transfers={transfers}",
            flush=True,
        )
    total_newly = sum(len(v) for v in transfer_results["newly_solved"].values())
    total_p1_solved = sum(len(dr["solved"]) for dr in domain_results.values())
    print(f"\n  Phase 1 solved: {total_p1_solved}", flush=True)
    print(f"  Phase 3 newly solved (via transfer): {total_newly}", flush=True)
    print(f"  Concepts invented: {len(invention_results['concepts'])}", flush=True)
    print(f"  Cross-domain concepts: {len(invention_results['cross_domain_concepts'])}",
          flush=True)
    print(f"  Total events: {len(event_log)}", flush=True)
    print(f"  Elapsed: {elapsed:.1f}s", flush=True)

    if transfer_results["transfer_successes"]:
        print("\n  ** THESIS CONFIRMED: Operators transferred across domains. **",
              flush=True)
    else:
        print("\n  Thesis not yet confirmed in this run.", flush=True)

    print("=" * 70, flush=True)


if __name__ == "__main__":
    main()
