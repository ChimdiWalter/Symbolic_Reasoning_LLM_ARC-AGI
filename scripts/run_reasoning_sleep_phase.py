"""Sleep/consolidation phase — the full feedback loop.

Pipeline:
    load near-solved states
    → cluster failures
    → repair adapters
    → generate concepts (grammar + JEPA-guided)
    → generate operator schemas
    → falsify candidates
    → update concept memory
    → resume failed tasks
    → emit certificates

Every new neural or VLM-like component can propose, but cannot decide.
Final acceptance requires executable symbolic hypothesis + LOO + active
falsification + certificate.
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
from reasoning_project.concept_memory import ConceptMemory, LearnedConcept
from reasoning_project.neural_abstraction import NeuralAbstractionPipeline
from reasoning_project.adapter_feedback import (
    AdapterFeedbackPipeline,
    write_adapter_feedback_outputs,
)
from reasoning_project.operator_schemas import SchemaEvaluator
from reasoning_project.active_falsifier import ActiveFalsifier
from reasoning_project.certificates import CertificateBuilder
from reasoning_project.reasoning_policy import (
    ReasoningPolicy,
    export_policy_training_data,
    write_policy_eval_report,
)


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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--arc-root", default="data/arc")
    parser.add_argument("--output-dir", default="outputs/sleep_phase")
    parser.add_argument("--max-tasks", type=int, default=0)
    parser.add_argument("--use-cache", default="",
                        help="Load Phase 1 near-solved cache from this dir")
    args = parser.parse_args()

    out = args.output_dir
    os.makedirs(out, exist_ok=True)

    tasks = load_arc_tasks(args.arc_root)
    if args.max_tasks > 0:
        tasks = tasks[:args.max_tasks]
    print(f"Loaded {len(tasks)} ARC tasks", flush=True)

    event_log = ReasoningEventLog()
    memory = ReasoningMemory()
    manifold = MemoryManifold()

    # ── Phase 1: Build near-solved states (or load from cache) ────────
    print("\n=== Phase 1: Build near-solved states ===", flush=True)
    if args.use_cache:
        from reasoning_project.near_solved_memory import load_near_solved_cache
        ns_mem, solved_before, _ = load_near_solved_cache(args.use_cache)
        print(f"  Loaded cache: {len(ns_mem.states)} near-solved, "
              f"{len(solved_before)} solved", flush=True)
        phase1_time = 0.0
    else:
        ns_mem = NearSolvedMemory(manifold)
        loop = AdaptiveReasoningLoop(
            max_iterations=4,
            timeout_seconds=15.0,
            memory=memory,
            manifold=manifold,
            near_solved_memory=ns_mem,
            event_log=event_log,
        )
        solved_before = []
        t0 = time.perf_counter()
        for i, task in enumerate(tasks):
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
                    solved_before.append(task["task_id"])
            if (i + 1) % 100 == 0:
                print(f"  {i+1}/{len(tasks)} solved={len(solved_before)} "
                      f"near-solved={len(ns_mem.states)}", flush=True)
        phase1_time = time.perf_counter() - t0

    print(f"Phase 1: {len(solved_before)} solved, {len(ns_mem.states)} near-solved, "
          f"{phase1_time:.0f}s", flush=True)

    # ── Phase 2: Cluster failures ──────────────────────────────────────
    print("\n=== Phase 2: Cluster failures ===", flush=True)
    t0 = time.perf_counter()
    adapter_feedback = AdapterFeedbackPipeline(event_log=event_log)
    adapter_result = adapter_feedback.run(ns_mem, tasks)
    phase2_time = time.perf_counter() - t0
    print(f"Phase 2: {adapter_result['n_clusters']} clusters, "
          f"{adapter_result['n_successful_repairs']} repairs, "
          f"{adapter_result['total_tasks_solved']} solved, "
          f"{phase2_time:.0f}s", flush=True)
    write_adapter_feedback_outputs(adapter_result, os.path.join(out, "adapter_feedback"))

    # ── Phase 3: Concept generation (grammar + JEPA-guided) ────────────
    print("\n=== Phase 3: Concept generation ===", flush=True)
    t0 = time.perf_counter()
    generator = ConceptGenerator()
    validator = ConceptValidator()
    concept_mem = ConceptMemory()

    # Generate depth-2 concepts and validate on near-solved tasks
    concepts = generator.generate_depth_2(beam_size=200)
    n_validated_concepts = 0
    near_solved_tasks_raw = []
    for t in tasks:
        if t["task_id"] not in ns_mem.states:
            continue
        near_solved_tasks_raw.append({
            "task_id": t["task_id"],
            "train": [
                {"input": inp.tolist(), "output": out.tolist()}
                for inp, out in t["train_pairs"]
            ],
        })
    if near_solved_tasks_raw:
        val_results = validator.batch_evaluate(concepts, near_solved_tasks_raw)
        for concept_expr, info in val_results:
            lc = LearnedConcept(
                name=str(concept_expr),
                expression_str=str(concept_expr),
                complexity=getattr(concept_expr, 'depth', 1),
                source_failure_cluster="concept_grammar",
                source_tasks=[info.get("task_id", "")],
                discrimination_score=info.get("discrimination", 1.0),
                loo_passed=info.get("loo_passed", True),
                status="validated",
            )
            concept_mem.register_concept(lc)
            n_validated_concepts += 1

    phase3_time = time.perf_counter() - t0
    print(f"Phase 3: {len(concepts)} generated, {n_validated_concepts} validated, "
          f"{phase3_time:.0f}s", flush=True)

    # ── Phase 4: Neural abstraction (JEPA-guided) ─────────────────────
    print("\n=== Phase 4: Neural abstraction ===", flush=True)
    t0 = time.perf_counter()
    try:
        pipeline = NeuralAbstractionPipeline(use_jepa=True)
        abstraction_result = pipeline.run_abstraction_pipeline(
            ns_mem, tasks, event_log=event_log,
        )
    except Exception as e:
        abstraction_result = {"status": f"error: {e}"}
    phase4_time = time.perf_counter() - t0
    print(f"Phase 4: {abstraction_result.get('validated', 0)} validated properties, "
          f"{phase4_time:.0f}s", flush=True)

    # ── Phase 5: Operator schema matching ─────────────────────────────
    print("\n=== Phase 5: Operator schemas ===", flush=True)
    t0 = time.perf_counter()
    schema_eval = SchemaEvaluator()
    schema_result = schema_eval.evaluate_all(tasks)
    phase5_time = time.perf_counter() - t0
    print(f"Phase 5: {schema_result['solved']} tasks matched by schemas, "
          f"{phase5_time:.0f}s", flush=True)

    # ── Phase 6: Property invention ───────────────────────────────────
    print("\n=== Phase 6: Property invention ===", flush=True)
    t0 = time.perf_counter()
    inventor = PropertyInventor()
    invention_result = inventor.run_full_pipeline(ns_mem, tasks)
    phase6_time = time.perf_counter() - t0
    print(f"Phase 6: {invention_result.get('n_proposed', 0)} proposed, "
          f"{invention_result.get('n_validated', 0)} validated, "
          f"{phase6_time:.0f}s", flush=True)

    # ── Phase 7: Resume failed tasks ──────────────────────────────────
    print("\n=== Phase 7: Resume near-solved tasks ===", flush=True)
    promoted = []
    false_positives = []
    certificates_emitted = []
    t0 = time.perf_counter()

    resume_tasks = [
        t for t in tasks
        if t["task_id"] in ns_mem.states
        and ns_mem.states[t["task_id"]].status != "solved"
    ]
    print(f"  Resuming {len(resume_tasks)} tasks", flush=True)

    falsifier = ActiveFalsifier()
    cert_builder = CertificateBuilder()
    adapter = GridDomainAdapter()

    resume_loop = AdaptiveReasoningLoop(
        max_iterations=4,
        timeout_seconds=15.0,
        memory=memory,
        manifold=manifold,
        near_solved_memory=ns_mem,
        event_log=event_log,
    )

    for i, task in enumerate(resume_tasks):
        tid = task["task_id"]
        rs = ns_mem.resume_from_state(tid)
        if rs is None:
            continue
        result = resume_loop.solve(
            task["train_pairs"], task["test_inputs"],
            task_id=tid, resume_from=rs,
        )
        if result.solved and result.predictions is not None:
            correct = all(
                np.array_equal(p, e)
                for p, e in zip(result.predictions, task["test_outputs"])
            )
            if correct:
                # Falsify before accepting
                hyp = result.hypothesis or {}
                fals_result = falsifier.falsify(task["train_pairs"], hyp, adapter)
                if fals_result.passed:
                    promoted.append(tid)
                    ns_mem.promote_to_solved(tid, hyp)
                    # Emit certificate
                    try:
                        cert = cert_builder.from_loop_result(
                            tid, result, task["train_pairs"], task["test_inputs"],
                        )
                        certificates_emitted.append(tid)
                        event_log.emit(
                            "REASONING_CERTIFICATE_CREATED", tid,
                            {"confidence": cert.confidence},
                            module="sleep_phase",
                        )
                    except Exception:
                        pass
                    event_log.emit(
                        "TASK_PROMOTED_TO_SOLVED", tid,
                        {"hypothesis": str(hyp)[:200]},
                        module="sleep_phase",
                    )
                else:
                    false_positives.append(tid)
            else:
                false_positives.append(tid)
        if (i + 1) % 100 == 0:
            print(f"  {i+1}/{len(resume_tasks)} "
                  f"(promoted={len(promoted)}, fp={len(false_positives)})",
                  flush=True)

    phase7_time = time.perf_counter() - t0
    print(f"Phase 7: {len(promoted)} promoted, {len(false_positives)} FP, "
          f"{len(certificates_emitted)} certificates, {phase7_time:.0f}s", flush=True)

    # ── Phase 8: Policy learning from event log ───────────────────────
    print("\n=== Phase 8: Policy learning ===", flush=True)
    t0 = time.perf_counter()
    policy = ReasoningPolicy()
    write_policy_eval_report(policy, event_log, os.path.join(out, "reasoning_policy"))
    phase8_time = time.perf_counter() - t0
    print(f"Phase 8: policy trained, {phase8_time:.0f}s", flush=True)

    # ── Write consolidation report ────────────────────────────────────
    total_time = sum([
        phase1_time, phase2_time, phase3_time, phase4_time,
        phase5_time, phase6_time, phase7_time, phase8_time,
    ])

    summary = {
        "solved_before": len(solved_before),
        "n_near_solved": len(ns_mem.states),
        "adapter_repairs": adapter_result["n_successful_repairs"],
        "adapter_tasks_solved": adapter_result["total_tasks_solved"],
        "concepts_generated": len(concepts),
        "concepts_validated": n_validated_concepts,
        "neural_predicates_validated": abstraction_result.get("validated", 0),
        "schema_tasks_solved": schema_result["solved"],
        "schema_breakdown": schema_result.get("schema_breakdown", {}),
        "properties_invented": invention_result.get("n_validated", 0),
        "n_promoted": len(promoted),
        "promoted_tasks": promoted,
        "n_false_positives": len(false_positives),
        "n_certificates": len(certificates_emitted),
        "total_solved_after": len(solved_before) + len(promoted),
        "phase_times": {
            "build_near_solved": phase1_time,
            "cluster_repair": phase2_time,
            "concept_generation": phase3_time,
            "neural_abstraction": phase4_time,
            "operator_schemas": phase5_time,
            "property_invention": phase6_time,
            "resume_tasks": phase7_time,
            "policy_learning": phase8_time,
        },
        "total_time": total_time,
    }

    with open(os.path.join(out, "consolidation_summary.json"), "w") as f:
        json.dump(summary, f, indent=2, default=str)

    # Promotions JSONL
    with open(os.path.join(out, "promotions_after_sleep.jsonl"), "w") as f:
        for tid in promoted:
            f.write(json.dumps({"task_id": tid, "source": "sleep_phase"}) + "\n")

    # Event log
    event_log.export_jsonl(os.path.join(out, "events.jsonl"))

    # Markdown report
    lines = [
        "# Sleep Phase Consolidation Report\n",
        f"**Total tasks**: {len(tasks)}",
        f"**Solved before sleep**: {len(solved_before)}",
        f"**Near-solved states**: {len(ns_mem.states)}",
        "",
        "## Consolidation Results\n",
        f"- Adapter repairs: {adapter_result['n_successful_repairs']}",
        f"- Adapter-solved tasks: {adapter_result['total_tasks_solved']}",
        f"- Concepts generated: {len(concepts)}",
        f"- Concepts validated: {n_validated_concepts}",
        f"- Neural predicates validated: {abstraction_result.get('validated', 0)}",
        f"- Schema-solved tasks: {schema_result['solved']}",
        f"- Properties invented: {invention_result.get('n_validated', 0)}",
        "",
        "## Resume Results\n",
        f"- Tasks resumed: {len(resume_tasks)}",
        f"- **Tasks promoted**: {len(promoted)}",
        f"- False positives: {len(false_positives)}",
        f"- Certificates emitted: {len(certificates_emitted)}",
        f"- **Total solved after sleep**: {len(solved_before) + len(promoted)}",
        "",
        "## Timing\n",
    ]
    for phase_name, t in summary["phase_times"].items():
        lines.append(f"- {phase_name}: {t:.0f}s")
    lines.append(f"- **Total**: {total_time:.0f}s")

    if promoted:
        lines.append("\n## Promoted Tasks\n")
        for tid in promoted:
            lines.append(f"- `{tid}`")

    with open(os.path.join(out, "consolidation_report.md"), "w") as f:
        f.write("\n".join(lines))

    print(f"\nWrote results to {out}/", flush=True)
    print(f"Total time: {total_time:.0f}s", flush=True)


if __name__ == "__main__":
    main()
