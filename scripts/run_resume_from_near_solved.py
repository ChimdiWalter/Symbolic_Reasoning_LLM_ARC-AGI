"""Resume near-solved ARC tasks using invented concepts.

Standalone stage 5: loads near-solved states from prior pipeline outputs,
runs concept invention, then attempts to resume each near-solved task with
the extended property language.

Outputs:
  outputs/resume/resume_report.md
  outputs/resume/resume_metrics.json
  outputs/resume/promoted_tasks.jsonl
"""
from __future__ import annotations

import json
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
    _all_property_names,
    _extract_objects_with_properties,
    _classify_kept_removed,
)
from reasoning_project.concept_grammar import (
    ConceptExpression,
    ConceptGenerator,
    ConceptValidator,
    _scene_from_objects,
)
from reasoning_project.concept_memory import ConceptMemory, LearnedConcept
from reasoning_project.near_solved_memory import NearSolvedMemory, NearSolvedTaskState
from reasoning_project.adaptive_loop import AdaptiveReasoningLoop
from reasoning_project.manifold_memory import MemoryManifold
from reasoning_project.events import ReasoningEventLog


class ExtendedGridAdapter(GridDomainAdapter):
    def __init__(self, learned_concepts=None):
        super().__init__()
        self._learned = learned_concepts or []

    def property_names(self):
        base = super().property_names()
        return base + [name for name, _ in self._learned]

    def get_property(self, obj, prop):
        for name, expr in self._learned:
            if prop == name:
                scene = obj.get("_scene")
                if scene is None:
                    return False
                return expr.evaluate(obj, scene)
        return super().get_property(obj, prop)

    def extract_objects(self, scene):
        objects = super().extract_objects(scene)
        scene_dict = _scene_from_objects(objects, scene)
        for obj in objects:
            obj["_scene"] = scene_dict
        return objects


def load_arc_tasks(arc_root: Path, max_tasks: int = 0) -> List[Dict]:
    tasks = []
    challenges_file = arc_root / "arc-agi_training_challenges.json"
    solutions_file = arc_root / "arc-agi_training_solutions.json"
    solutions = {}
    if solutions_file.exists():
        with open(solutions_file) as f:
            solutions = json.load(f)
    if challenges_file.exists():
        with open(challenges_file) as f:
            data = json.load(f)
        for tid, task_data in sorted(data.items()):
            task = {"task_id": tid, **task_data}
            if tid in solutions:
                for i, test_pair in enumerate(task.get("test", [])):
                    if "output" not in test_pair and i < len(solutions[tid]):
                        test_pair["output"] = solutions[tid][i]
            tasks.append(task)
            if max_tasks > 0 and len(tasks) >= max_tasks:
                break
        return tasks
    # Fallback: per-task JSON files in training/ dir
    training_dir = arc_root / "training"
    if not training_dir.exists():
        print(f"  [WARN] No ARC data at {arc_root}")
        return tasks
    files = sorted(training_dir.glob("*.json"))
    if max_tasks > 0:
        files = files[:max_tasks]
    for f in files:
        with open(f) as fh:
            data = json.load(fh)
        tasks.append({"task_id": f.stem, **data})
    return tasks


def build_near_solved_states(
    tasks: List[Dict], max_tasks: int = 200,
) -> Tuple[NearSolvedMemory, Dict[str, Dict]]:
    """Run static solver on tasks, store failures as near-solved states."""
    manifold = MemoryManifold()
    ns_mem = NearSolvedMemory(manifold)
    memory = ReasoningMemory()
    task_lookup: Dict[str, Dict] = {}

    for i, task in enumerate(tasks[:max_tasks]):
        tid = task["task_id"]
        train_pairs = [(np.array(p["input"]), np.array(p["output"])) for p in task["train"]]
        test_inputs = [np.array(p["input"]) for p in task.get("test", [])]

        if len(train_pairs) < 2:
            continue

        adapter = GridDomainAdapter()
        reasoner = StructuralReasoner(adapter, memory=memory, min_train=2)
        result = reasoner.solve(train_pairs, test_inputs)

        if result is None:
            loop = AdaptiveReasoningLoop(
                max_iterations=3, timeout_seconds=15.0,
                memory=memory, manifold=manifold, near_solved_memory=ns_mem,
            )
            loop.solve(train_pairs, test_inputs, task_id=tid)
            task_lookup[tid] = task

        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{min(len(tasks), max_tasks)} "
                  f"near-solved={len(ns_mem.states)}", flush=True)

    return ns_mem, task_lookup


def invent_concepts_for_cluster(
    cluster_tasks: List[Dict], base_props: set,
) -> List[Tuple[str, ConceptExpression, LearnedConcept]]:
    """Generate and validate concepts for a failure cluster."""
    generator = ConceptGenerator()
    validator = ConceptValidator()
    results = []

    concepts = generator.generate_from_failure_cluster(cluster_tasks)
    for concept in concepts:
        if concept.type_signature != "Object->Bool":
            continue
        if concept.name in base_props or concept.complexity <= 1:
            continue

        for task in cluster_tasks:
            disc = validator.training_discrimination_score(concept, task)
            if disc >= 1.0:
                loo = validator.loo_validate(concept, task)
                if loo:
                    lc = LearnedConcept(
                        name=concept.name,
                        expression_str=concept.to_string(),
                        complexity=concept.complexity,
                        source_failure_cluster="resume",
                        source_tasks=[task["task_id"]],
                        loo_passed=True,
                        discrimination_score=1.0,
                        status="validated",
                    )
                    results.append((task["task_id"], concept, lc))
                    break

    return results


def attempt_resume(
    task: Dict,
    learned_concepts: List[Tuple[str, ConceptExpression]],
) -> Optional[Dict]:
    """Try to solve a task with the extended adapter."""
    train_pairs = [(np.array(p["input"]), np.array(p["output"])) for p in task["train"]]
    test_inputs = [np.array(p["input"]) for p in task.get("test", [])]
    test_outputs = [np.array(p["output"]) for p in task.get("test", [])]

    if not test_outputs:
        return None

    adapter = ExtendedGridAdapter(learned_concepts=learned_concepts)
    memory = ReasoningMemory()
    reasoner = StructuralReasoner(adapter, memory=memory, min_train=2)
    result = reasoner.solve(train_pairs, test_inputs)

    if result is not None:
        preds, meta = result
        correct = all(np.array_equal(p, t) for p, t in zip(preds, test_outputs))
        if correct:
            return {
                "task_id": task["task_id"],
                "strategy": meta.get("strategy", "unknown"),
                "property": meta.get("property", "unknown"),
                "concepts_used": [name for name, _ in learned_concepts],
            }
    return None


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Resume near-solved tasks")
    parser.add_argument("--arc-root", default="data/arc")
    parser.add_argument("--output-dir", default="outputs/resume")
    parser.add_argument("--max-tasks", type=int, default=200)
    parser.add_argument("--use-cache", default="",
                        help="Load Phase 1 near-solved cache from this dir")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    arc_root = Path(args.arc_root)

    print("=" * 60)
    print("RESUME FROM NEAR-SOLVED STATES")
    print("=" * 60)
    t0 = time.time()

    # Load tasks
    print("\nLoading ARC tasks...", flush=True)
    tasks = load_arc_tasks(arc_root, max_tasks=args.max_tasks)
    print(f"  Loaded {len(tasks)} tasks")

    # Phase 1: Build near-solved states (or load from cache)
    print("\n--- Phase 1: Build near-solved states ---", flush=True)
    if args.use_cache:
        from reasoning_project.near_solved_memory import load_near_solved_cache
        ns_mem, _, _ = load_near_solved_cache(args.use_cache)
        task_lookup = {t["task_id"]: t for t in tasks if t["task_id"] in ns_mem.states}
        print(f"  Loaded cache: {len(ns_mem.states)} near-solved", flush=True)
    else:
        ns_mem, task_lookup = build_near_solved_states(tasks, max_tasks=args.max_tasks)
    n_near_solved = len(ns_mem.states)
    print(f"  Near-solved states: {n_near_solved}")

    if n_near_solved == 0:
        print("\nNo near-solved states found. Exiting.")
        metrics = {"n_tasks": len(tasks), "n_near_solved": 0, "promotions": 0}
        with open(output_dir / "resume_metrics.json", "w") as f:
            json.dump(metrics, f, indent=2)
        return

    # Phase 2: Concept invention
    print("\n--- Phase 2: Concept invention ---", flush=True)
    base_props = set(_all_property_names())
    cluster_tasks = [task_lookup[tid] for tid in ns_mem.states if tid in task_lookup]
    inventions = invent_concepts_for_cluster(cluster_tasks[:50], base_props)
    print(f"  Concepts invented: {len(inventions)}")

    # Phase 3: Attempt resume
    print("\n--- Phase 3: Resume with invented concepts ---", flush=True)
    promoted = []
    all_concepts = [(lc.name, expr) for _, expr, lc in inventions]

    for tid in list(ns_mem.states.keys()):
        if tid not in task_lookup:
            continue
        task = task_lookup[tid]

        # Try with task-specific concept first
        task_concepts = [(lc.name, expr) for t_id, expr, lc in inventions if t_id == tid]
        if task_concepts:
            result = attempt_resume(task, task_concepts)
            if result is not None:
                promoted.append(result)
                continue

        # Try with all invented concepts
        if all_concepts:
            result = attempt_resume(task, all_concepts)
            if result is not None:
                promoted.append(result)

    print(f"  Promotions: {len(promoted)}")

    # Write outputs
    elapsed = time.time() - t0
    metrics = {
        "n_tasks": len(tasks),
        "n_near_solved": n_near_solved,
        "n_concepts_invented": len(inventions),
        "n_promoted": len(promoted),
        "promoted_task_ids": [p["task_id"] for p in promoted],
        "elapsed_seconds": elapsed,
    }

    with open(output_dir / "resume_metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)

    with open(output_dir / "promoted_tasks.jsonl", "w") as f:
        for p in promoted:
            f.write(json.dumps(p) + "\n")

    lines = [
        "# Resume from Near-Solved States\n",
        f"- Tasks loaded: {len(tasks)}",
        f"- Near-solved states: {n_near_solved}",
        f"- Concepts invented: {len(inventions)}",
        f"- **Promotions: {len(promoted)}**",
        f"- Elapsed: {elapsed:.0f}s\n",
    ]
    if promoted:
        lines.append("\n## Promoted Tasks\n")
        for p in promoted:
            lines.append(f"- `{p['task_id']}` via {p['strategy']}, "
                         f"property={p['property']}, concepts={p['concepts_used']}")
    if inventions:
        lines.append("\n## Invented Concepts\n")
        for tid, expr, lc in inventions:
            lines.append(f"- `{lc.name}` = `{lc.expression_str}` (from task {tid})")

    with open(output_dir / "resume_report.md", "w") as f:
        f.write("\n".join(lines))

    print(f"\nDone in {elapsed:.0f}s. Outputs: {output_dir}")


if __name__ == "__main__":
    main()
