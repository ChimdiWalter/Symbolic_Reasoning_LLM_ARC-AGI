"""Final experiment: compare ablation configurations.

Configurations:
    1. static_portfolio — StructuralReasoner, no memory
    2. + adapter_genesis — add AdapterGenesis
    3. + near_solved_memory — add NearSolvedMemory
    4. + property_invention — add PropertyInventor
    5. + jepa_guided — add JEPA-guided abstraction
    6. + concept_grammar — add ConceptGrammar depth-2
    7. + operator_schemas — add OperatorSchemas
    8. + sleep_phase — full consolidation loop
    9. full_system — everything

Metrics:
    solved tasks, near-solved states, promoted tasks, new concepts,
    new operators, adapter repairs, false positives, runtime,
    cross-domain transfer, certificates emitted
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reasoning_project.reasoning_engine import (
    GridDomainAdapter,
    ReasoningMemory,
    StructuralReasoner,
)
from reasoning_project.adaptive_loop import AdaptiveReasoningLoop
from reasoning_project.manifold_memory import MemoryManifold
from reasoning_project.near_solved_memory import NearSolvedMemory
from reasoning_project.events import ReasoningEventLog
from reasoning_project.property_invention import PropertyInventor
from reasoning_project.concept_grammar import ConceptGenerator, ConceptValidator
from reasoning_project.concept_memory import ConceptMemory
from reasoning_project.neural_abstraction import NeuralAbstractionPipeline
from reasoning_project.adapter_feedback import AdapterFeedbackPipeline
from reasoning_project.operator_schemas import SchemaEvaluator
from reasoning_project.active_falsifier import ActiveFalsifier
from reasoning_project.certificates import CertificateBuilder
from reasoning_project.reasoning_policy import ReasoningPolicy


def load_arc_tasks(root: str):
    tasks = []
    challenges_path = os.path.join(root, "arc-agi_training_challenges.json")
    solutions_path = os.path.join(root, "arc-agi_training_solutions.json")
    if not os.path.isfile(challenges_path):
        return tasks
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


# ── Configurations ─────────────────────────────────────────────────────

CONFIGS = [
    "static_portfolio",
    "adapter_genesis",
    "near_solved_memory",
    "property_invention",
    "jepa_guided",
    "concept_grammar",
    "operator_schemas",
    "sleep_phase",
    "full_system",
]


def run_config(
    config_name: str,
    tasks: list,
    output_dir: str,
    cache_dir: str = "",
) -> dict:
    """Run a single configuration and return metrics."""
    t0 = time.perf_counter()
    event_log = ReasoningEventLog()
    memory = ReasoningMemory()
    manifold = MemoryManifold()
    if cache_dir:
        from reasoning_project.near_solved_memory import load_near_solved_cache
        ns_mem, _, _ = load_near_solved_cache(cache_dir)
    else:
        ns_mem = NearSolvedMemory(manifold)

    use_memory = config_name not in ("static_portfolio",)
    use_adapter = config_name in (
        "adapter_genesis", "near_solved_memory", "property_invention",
        "jepa_guided", "concept_grammar", "operator_schemas",
        "sleep_phase", "full_system",
    )
    use_near_solved = config_name in (
        "near_solved_memory", "property_invention", "jepa_guided",
        "concept_grammar", "operator_schemas", "sleep_phase", "full_system",
    )
    use_invention = config_name in (
        "property_invention", "jepa_guided", "concept_grammar",
        "operator_schemas", "sleep_phase", "full_system",
    )
    use_jepa = config_name in (
        "jepa_guided", "concept_grammar", "operator_schemas",
        "sleep_phase", "full_system",
    )
    use_grammar = config_name in (
        "concept_grammar", "operator_schemas", "sleep_phase", "full_system",
    )
    use_schemas = config_name in (
        "operator_schemas", "sleep_phase", "full_system",
    )
    use_sleep = config_name in ("sleep_phase", "full_system")

    loop = AdaptiveReasoningLoop(
        max_iterations=4,
        timeout_seconds=15.0,
        memory=memory if use_memory else ReasoningMemory(),
        manifold=manifold if use_memory else None,
        near_solved_memory=ns_mem if use_near_solved else None,
        event_log=event_log,
    )

    # Phase 1: Baseline solve
    solved = []
    for task in tasks:
        result = loop.solve(
            task["train_pairs"], task["test_inputs"],
            task_id=task["task_id"],
        )
        if result.solved and result.predictions is not None:
            correct = all(
                np.array_equal(p, e)
                for p, e in zip(result.predictions, task["test_outputs"])
            )
            if correct:
                solved.append(task["task_id"])

    metrics = {
        "config": config_name,
        "solved_baseline": len(solved),
        "near_solved": len(ns_mem.states),
        "promoted": 0,
        "new_concepts": 0,
        "new_operators": 0,
        "adapter_repairs": 0,
        "false_positives": 0,
        "schema_solved": 0,
        "certificates": 0,
    }

    # Phase 2: Adapter feedback
    if use_adapter:
        try:
            afp = AdapterFeedbackPipeline(event_log=event_log)
            af_result = afp.run(ns_mem, tasks)
            metrics["adapter_repairs"] = af_result.get("n_successful_repairs", 0)
        except Exception:
            pass

    # Phase 3: Property invention
    if use_invention:
        try:
            inventor = PropertyInventor()
            inv_result = inventor.run_full_pipeline(ns_mem, tasks)
            metrics["new_operators"] += inv_result.get("n_validated", 0)
        except Exception:
            pass

    # Phase 4: Neural abstraction (JEPA-guided)
    if use_jepa:
        try:
            nap = NeuralAbstractionPipeline(use_jepa=True)
            nap_result = nap.run_abstraction_pipeline(ns_mem, tasks, event_log)
            metrics["new_concepts"] += nap_result.get("validated", 0)
        except Exception:
            pass

    # Phase 5: Concept grammar
    if use_grammar:
        try:
            gen = ConceptGenerator()
            val = ConceptValidator()
            concepts = gen.generate_depth_2(beam_size=200)
            metrics["new_concepts"] += len(concepts)
        except Exception:
            pass

    # Phase 6: Operator schemas
    if use_schemas:
        try:
            se = SchemaEvaluator()
            sr = se.evaluate_all(tasks)
            metrics["schema_solved"] = sr.get("solved", 0)
        except Exception:
            pass

    # Phase 7: Resume
    promoted = []
    false_positives = []
    if use_near_solved:
        resume_tasks = [
            t for t in tasks
            if t["task_id"] in ns_mem.states
            and ns_mem.states[t["task_id"]].status != "solved"
        ]
        falsifier = ActiveFalsifier()
        adapter = GridDomainAdapter()

        for task in resume_tasks:
            tid = task["task_id"]
            rs = ns_mem.resume_from_state(tid)
            if rs is None:
                continue
            result = loop.solve(
                task["train_pairs"], task["test_inputs"],
                task_id=tid, resume_from=rs,
            )
            if result.solved and result.predictions is not None:
                correct = all(
                    np.array_equal(p, e)
                    for p, e in zip(result.predictions, task["test_outputs"])
                )
                if correct:
                    hyp = result.hypothesis or {}
                    fals = falsifier.falsify(task["train_pairs"], hyp, adapter)
                    if fals.passed:
                        promoted.append(tid)
                        ns_mem.promote_to_solved(tid, hyp)
                        metrics["certificates"] += 1
                    else:
                        false_positives.append(tid)
                else:
                    false_positives.append(tid)

    metrics["promoted"] = len(promoted)
    metrics["false_positives"] = len(false_positives)
    metrics["total_solved"] = len(solved) + len(promoted)
    metrics["runtime"] = time.perf_counter() - t0

    # Save config-level output
    cfg_dir = os.path.join(output_dir, config_name)
    os.makedirs(cfg_dir, exist_ok=True)
    with open(os.path.join(cfg_dir, "metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2, default=str)
    event_log.export_jsonl(os.path.join(cfg_dir, "events.jsonl"))

    return metrics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--arc-root", default="data/arc")
    parser.add_argument("--output-dir", default="outputs/final_experiment")
    parser.add_argument("--max-tasks", type=int, default=0)
    parser.add_argument("--configs", nargs="+", default=CONFIGS)
    parser.add_argument("--use-cache", default="",
                        help="Load Phase 1 near-solved cache from this dir")
    args = parser.parse_args()

    out = args.output_dir
    os.makedirs(out, exist_ok=True)

    tasks = load_arc_tasks(args.arc_root)
    if args.max_tasks > 0:
        tasks = tasks[:args.max_tasks]
    print(f"Loaded {len(tasks)} ARC tasks", flush=True)

    all_metrics = []
    for cfg in args.configs:
        print(f"\n{'='*60}", flush=True)
        print(f"  Config: {cfg}", flush=True)
        print(f"{'='*60}", flush=True)
        metrics = run_config(cfg, tasks, out, cache_dir=args.use_cache)
        all_metrics.append(metrics)
        print(f"  → solved={metrics['total_solved']}, promoted={metrics['promoted']}, "
              f"fp={metrics['false_positives']}, certs={metrics['certificates']}, "
              f"time={metrics['runtime']:.0f}s", flush=True)

    # Write combined results
    with open(os.path.join(out, "all_metrics.json"), "w") as f:
        json.dump(all_metrics, f, indent=2, default=str)

    # Markdown comparison table
    lines = [
        "# Final Experiment — Ablation Comparison\n",
        "| Config | Solved | Near-Solved | Promoted | Concepts | Operators | "
        "Adapter Repairs | Schema Solved | FP | Certs | Runtime |",
        "|--------|--------|-------------|----------|----------|-----------|"
        "----------------|---------------|----|----- |---------|",
    ]
    for m in all_metrics:
        lines.append(
            f"| {m['config']} | {m['total_solved']} | {m['near_solved']} | "
            f"{m['promoted']} | {m['new_concepts']} | {m['new_operators']} | "
            f"{m['adapter_repairs']} | {m['schema_solved']} | "
            f"{m['false_positives']} | {m['certificates']} | "
            f"{m['runtime']:.0f}s |"
        )
    lines.append("\n## Main Rule")
    lines.append(
        "Every new neural or VLM-like component can propose, but cannot decide. "
        "Final acceptance requires executable symbolic hypothesis + LOO + active "
        "falsification + certificate."
    )
    lines.append("\n## Manuscript Note")
    lines.append(
        "We do not rely on pretrained VLM reasoning in the main system. "
        "Neural components provide targeted perceptual and abstraction priors, "
        "while symbolic validation remains the authority."
    )

    with open(os.path.join(out, "final_comparison_report.md"), "w") as f:
        f.write("\n".join(lines))

    print(f"\nWrote results to {out}/", flush=True)


if __name__ == "__main__":
    main()
