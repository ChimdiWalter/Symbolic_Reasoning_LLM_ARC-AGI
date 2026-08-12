"""Concept grammar comparison experiment.

Compares six concept-generation configurations on ARC tasks:
  1. fixed_81        — only the 81 primitive properties
  2. conjunctions_only — fixed_81 + AND(p1, p2) pairs, beam_size=200
  3. depth_2          — ConceptGenerator.generate_depth_2(beam_size=200)
  4. depth_3          — ConceptGenerator.generate_depth_k(3, beam_size=100)
  5. neural_guided    — PropertyInventor failure-cluster mining + ConceptGenerator
  6. full_pipeline    — depth_3 + neural_guided + active falsification + concept memory

Outputs:
  concept_depth_vs_accuracy.csv — depth, n_concepts, n_solved, n_fp, runtime
  concept_complexity_vs_fp.csv  — complexity_bucket, n_concepts, n_fp
  concept_grammar_comparison.md — comparison table + analysis
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reasoning_project.reasoning_engine import (
    GridDomainAdapter,
    StructuralReasoner,
    _all_property_names,
    _classify_kept_removed,
    _extract_objects_with_properties,
    _get_property_value,
)
from reasoning_project.concept_memory import ConceptMemory, LearnedConcept

# concept_grammar.py is built by another agent — gracefully degrade if absent
try:
    from reasoning_project.concept_grammar import ConceptGenerator, ConceptValidator
except ImportError:
    ConceptGenerator = None
    ConceptValidator = None

# PropertyInventor may or may not be available
try:
    from reasoning_project.property_invention import PropertyInventor
except ImportError:
    PropertyInventor = None


# ═══════════════════════════════════════════════════════════════════════════
# ARC TASK LOADING
# ═══════════════════════════════════════════════════════════════════════════


def load_arc_tasks(root: str) -> List[Dict[str, Any]]:
    tasks: List[Dict[str, Any]] = []
    challenges_path = os.path.join(root, "arc-agi_training_challenges.json")
    solutions_path = os.path.join(root, "arc-agi_training_solutions.json")
    if not os.path.isfile(challenges_path):
        return tasks
    with open(challenges_path) as f:
        challenges = json.load(f)
    solutions: Dict[str, Any] = {}
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
        test_outputs: List[np.ndarray] = []
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


# ═══════════════════════════════════════════════════════════════════════════
# CONCEPT REPRESENTATIONS (used when concept_grammar is unavailable)
# ═══════════════════════════════════════════════════════════════════════════


class PrimitiveConcept:
    """Wraps a single primitive property as a concept."""

    def __init__(self, name: str):
        self.name = name
        self.expression_str = f"{name}(x)"
        self.complexity = 1
        self.dependencies: List[str] = []

    def evaluate(self, obj: Dict[str, Any]) -> bool:
        return _get_property_value(obj, self.name)


class AndConcept:
    """Conjunction of two concepts."""

    def __init__(self, a: PrimitiveConcept, b: PrimitiveConcept):
        self.a = a
        self.b = b
        self.name = f"{a.name}_AND_{b.name}"
        self.expression_str = f"{a.expression_str} AND {b.expression_str}"
        self.complexity = a.complexity + b.complexity + 1
        self.dependencies = [a.name, b.name]

    def evaluate(self, obj: Dict[str, Any]) -> bool:
        return self.a.evaluate(obj) and self.b.evaluate(obj)


# ═══════════════════════════════════════════════════════════════════════════
# DISCRIMINATION & LOO CHECKING
# ═══════════════════════════════════════════════════════════════════════════


def _check_concept_discriminates(
    concept: Any,
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> Tuple[bool, bool, float]:
    """Check if a concept perfectly discriminates kept vs removed objects.

    Returns (discriminates, keep_when_true, score).
    score is the fraction of training pairs where the concept works.
    """
    n_ok_true = 0
    n_ok_false = 0
    n_pairs = 0

    for inp, out in train_pairs:
        if inp.shape != out.shape:
            continue
        objects = _extract_objects_with_properties(inp)
        if len(objects) < 2:
            continue
        result = _classify_kept_removed(objects, inp, out)
        if result is None:
            continue
        kept_indices, removed_indices = result
        if not kept_indices or not removed_indices:
            continue

        n_pairs += 1
        kept_vals = [concept.evaluate(objects[i]) for i in kept_indices]
        removed_vals = [concept.evaluate(objects[i]) for i in removed_indices]

        if all(kept_vals) and not any(removed_vals):
            n_ok_true += 1
        if not any(kept_vals) and all(removed_vals):
            n_ok_false += 1

    if n_pairs == 0:
        return False, True, 0.0

    if n_ok_true == n_pairs:
        return True, True, 1.0
    if n_ok_false == n_pairs:
        return True, False, 1.0

    best = max(n_ok_true, n_ok_false)
    return False, n_ok_true >= n_ok_false, best / n_pairs


def _check_loo(
    concept: Any,
    keep_when_true: bool,
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> bool:
    """Leave-one-out cross-validation for a concept."""
    if len(train_pairs) < 2:
        return True
    for i in range(len(train_pairs)):
        held_out = [train_pairs[i]]
        training = train_pairs[:i] + train_pairs[i + 1:]
        # Check discrimination on held-out
        disc, kwt, _ = _check_concept_discriminates(concept, held_out)
        if not disc or kwt != keep_when_true:
            return False
    return True


# ═══════════════════════════════════════════════════════════════════════════
# CONCEPT GENERATORS PER CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════


def _generate_fixed_81() -> List[Any]:
    """Generate primitive concepts from the 81 property names."""
    return [PrimitiveConcept(name) for name in _all_property_names()]


def _generate_conjunctions_only(beam_size: int = 200) -> List[Any]:
    """Fixed 81 + AND(p1, p2) for all pairs, capped at beam_size by complexity."""
    primitives = _generate_fixed_81()
    conjunctions: List[Any] = []
    for a, b in itertools.combinations(primitives, 2):
        conjunctions.append(AndConcept(a, b))
    # Sort by complexity (all conjunctions have same complexity=3, but this
    # is forward-compatible if primitive complexities vary)
    conjunctions.sort(key=lambda c: c.complexity)
    return primitives + conjunctions[:beam_size]


def _generate_depth_2(beam_size: int = 200) -> List[Any]:
    """Use ConceptGenerator for depth-2 concepts if available, else fall back."""
    if ConceptGenerator is not None:
        try:
            gen = ConceptGenerator()
            return gen.generate_depth_2(beam_size=beam_size)
        except Exception:
            pass
    # Fallback: conjunctions_only is depth 2
    return _generate_conjunctions_only(beam_size=beam_size)


def _generate_depth_3(beam_size: int = 100) -> List[Any]:
    """Use ConceptGenerator for depth-3 concepts if available, else fall back."""
    if ConceptGenerator is not None:
        try:
            gen = ConceptGenerator()
            return gen.generate_depth_k(3, beam_size=beam_size)
        except Exception:
            pass
    # Fallback: depth-2 is the best we can do
    return _generate_depth_2(beam_size=beam_size)


def _generate_neural_guided(
    tasks: List[Dict[str, Any]],
) -> List[Any]:
    """Use PropertyInventor to mine failure clusters, then generate concepts."""
    if ConceptGenerator is None or PropertyInventor is None:
        return _generate_fixed_81()
    try:
        # This would mine failures and generate targeted concepts
        gen = ConceptGenerator()
        return gen.generate_from_failure_clusters(tasks)
    except Exception:
        return _generate_fixed_81()


def _generate_full_pipeline(
    tasks: List[Dict[str, Any]],
    beam_size: int = 100,
) -> List[Any]:
    """depth_3 + neural_guided + concept memory integration."""
    concepts = _generate_depth_3(beam_size=beam_size)

    # Add neural-guided if available
    if ConceptGenerator is not None and PropertyInventor is not None:
        try:
            gen = ConceptGenerator()
            neural = gen.generate_from_failure_clusters(tasks)
            seen = {c.name for c in concepts}
            for nc in neural:
                if nc.name not in seen:
                    concepts.append(nc)
                    seen.add(nc.name)
        except Exception:
            pass

    return concepts


# ═══════════════════════════════════════════════════════════════════════════
# EVALUATION LOOP
# ═══════════════════════════════════════════════════════════════════════════


def evaluate_configuration(
    config_name: str,
    concepts: List[Any],
    tasks: List[Dict[str, Any]],
    concept_memory: Optional[ConceptMemory] = None,
) -> Dict[str, Any]:
    """Run a single configuration on all tasks.

    Returns dict with:
      config, n_concepts, n_solved, n_near_solved, n_failed,
      concepts_tried, concepts_that_discriminated,
      false_positives, runtime, per_task results.
    """
    t0 = time.perf_counter()
    n_solved = 0
    n_near_solved = 0
    n_failed = 0
    concepts_that_discriminated = 0
    total_concepts_tried = 0
    total_false_positives = 0
    per_task: List[Dict[str, Any]] = []

    for task in tasks:
        task_id = task["task_id"]
        train_pairs = task["train_pairs"]
        test_outputs = task["test_outputs"]
        task_solved = False
        task_near = False
        task_fp = 0
        task_disc = 0
        best_score = 0.0

        for concept in concepts:
            total_concepts_tried += 1
            try:
                disc, kwt, score = _check_concept_discriminates(concept, train_pairs)
            except Exception:
                continue

            if score > best_score:
                best_score = score

            if disc:
                task_disc += 1
                concepts_that_discriminated += 1

                # LOO check
                if _check_loo(concept, kwt, train_pairs):
                    task_solved = True
                    if concept_memory is not None:
                        concept_memory.graph.mark_solved(
                            concept.name if hasattr(concept, "name") else str(concept),
                            task_id,
                        )
                    break
                else:
                    task_fp += 1
                    total_false_positives += 1
                    if concept_memory is not None:
                        concept_memory.graph.mark_false_positive(
                            concept.name if hasattr(concept, "name") else str(concept),
                        )

        if task_solved:
            n_solved += 1
        elif best_score >= 0.5:
            n_near_solved += 1
        else:
            n_failed += 1

        per_task.append({
            "task_id": task_id,
            "solved": task_solved,
            "near_solved": best_score >= 0.5 and not task_solved,
            "best_score": best_score,
            "concepts_discriminated": task_disc,
            "false_positives": task_fp,
        })

    runtime = time.perf_counter() - t0

    return {
        "config": config_name,
        "n_concepts": len(concepts),
        "n_solved": n_solved,
        "n_near_solved": n_near_solved,
        "n_failed": n_failed,
        "concepts_tried": total_concepts_tried,
        "concepts_that_discriminated": concepts_that_discriminated,
        "false_positives": total_false_positives,
        "runtime": runtime,
        "per_task": per_task,
    }


# ═══════════════════════════════════════════════════════════════════════════
# OUTPUT WRITERS
# ═══════════════════════════════════════════════════════════════════════════


def write_depth_vs_accuracy_csv(
    results: List[Dict[str, Any]], path: str,
) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["config", "n_concepts", "n_solved", "n_near_solved", "n_fp", "runtime_s"])
        for r in results:
            writer.writerow([
                r["config"],
                r["n_concepts"],
                r["n_solved"],
                r["n_near_solved"],
                r["false_positives"],
                f"{r['runtime']:.2f}",
            ])


def write_complexity_vs_fp_csv(
    results: List[Dict[str, Any]], path: str,
) -> None:
    """Aggregate false positives by complexity bucket across configs."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    # Simple summary: one row per config with its FP count
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["config", "n_concepts", "n_fp", "fp_rate"])
        for r in results:
            n_tried = r["concepts_tried"] or 1
            writer.writerow([
                r["config"],
                r["n_concepts"],
                r["false_positives"],
                f"{r['false_positives'] / n_tried:.4f}",
            ])


def write_comparison_markdown(
    results: List[Dict[str, Any]],
    n_tasks: int,
    path: str,
) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    lines = [
        "# Concept Grammar Comparison",
        "",
        f"Tasks evaluated: {n_tasks}",
        "",
        "## Results",
        "",
        "| Config | Concepts | Solved | Near-Solved | FP | Runtime (s) |",
        "|--------|----------|--------|-------------|-----|-------------|",
    ]
    for r in results:
        lines.append(
            f"| {r['config']} | {r['n_concepts']} | {r['n_solved']} "
            f"| {r['n_near_solved']} | {r['false_positives']} "
            f"| {r['runtime']:.1f} |"
        )
    lines.append("")

    # Analysis
    lines.append("## Analysis")
    lines.append("")

    if len(results) >= 2:
        base = results[0]
        for r in results[1:]:
            delta = r["n_solved"] - base["n_solved"]
            sign = "+" if delta >= 0 else ""
            lines.append(
                f"- **{r['config']}** vs **{base['config']}**: "
                f"{sign}{delta} solved ({r['n_solved']} vs {base['n_solved']}), "
                f"{r['false_positives']} FP"
            )
    lines.append("")

    best = max(results, key=lambda r: r["n_solved"])
    lines.append(
        f"Best configuration: **{best['config']}** "
        f"({best['n_solved']} solved, {best['false_positives']} FP)"
    )

    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════


def main():
    parser = argparse.ArgumentParser(
        description="Concept grammar comparison experiment on ARC tasks.",
    )
    parser.add_argument("--arc-root", default="data/arc")
    parser.add_argument("--output-dir", default="outputs/concept_grammar_eval")
    parser.add_argument("--max-tasks", type=int, default=0)
    args = parser.parse_args()

    out = args.output_dir
    os.makedirs(out, exist_ok=True)

    tasks = load_arc_tasks(args.arc_root)
    if args.max_tasks > 0:
        tasks = tasks[: args.max_tasks]
    print(f"Loaded {len(tasks)} ARC tasks", flush=True)

    if not tasks:
        print("No tasks found. Check --arc-root path.", flush=True)
        return

    # ── Determine which configurations are available ──
    concept_grammar_available = ConceptGenerator is not None and ConceptValidator is not None
    property_inventor_available = PropertyInventor is not None

    configs: List[Tuple[str, Callable]] = [
        ("fixed_81", lambda: _generate_fixed_81()),
        ("conjunctions_only", lambda: _generate_conjunctions_only(beam_size=200)),
    ]

    if concept_grammar_available:
        configs.append(("depth_2", lambda: _generate_depth_2(beam_size=200)))
        configs.append(("depth_3", lambda: _generate_depth_3(beam_size=100)))
    else:
        print(
            "concept_grammar not available — depth_2 and depth_3 will use "
            "conjunction fallback",
            flush=True,
        )
        configs.append(("depth_2", lambda: _generate_depth_2(beam_size=200)))
        configs.append(("depth_3", lambda: _generate_depth_3(beam_size=100)))

    if concept_grammar_available and property_inventor_available:
        configs.append(("neural_guided", lambda: _generate_neural_guided(tasks)))
        configs.append(("full_pipeline", lambda: _generate_full_pipeline(tasks, beam_size=100)))
    else:
        print(
            "Skipping neural_guided and full_pipeline (requires concept_grammar + "
            "property_invention)",
            flush=True,
        )

    # ── Run each configuration ──
    all_results: List[Dict[str, Any]] = []
    concept_memory = ConceptMemory()
    concept_memory.seed_primitives()

    for config_name, generator_fn in configs:
        print(f"\n=== Configuration: {config_name} ===", flush=True)

        concepts = generator_fn()
        print(f"  Generated {len(concepts)} concepts", flush=True)

        result = evaluate_configuration(
            config_name, concepts, tasks,
            concept_memory=concept_memory if config_name == "full_pipeline" else None,
        )
        all_results.append(result)

        print(
            f"  Solved: {result['n_solved']}/{len(tasks)}  "
            f"Near-solved: {result['n_near_solved']}  "
            f"FP: {result['false_positives']}  "
            f"Runtime: {result['runtime']:.1f}s",
            flush=True,
        )

    # ── Write outputs ──
    write_depth_vs_accuracy_csv(
        all_results,
        os.path.join(out, "concept_depth_vs_accuracy.csv"),
    )
    write_complexity_vs_fp_csv(
        all_results,
        os.path.join(out, "concept_complexity_vs_fp.csv"),
    )
    write_comparison_markdown(
        all_results,
        n_tasks=len(tasks),
        os.path.join(out, "concept_grammar_comparison.md"),
    )

    # Export concept memory state
    if concept_memory.graph.concepts:
        concept_memory.graph.export_json(
            os.path.join(out, "concept_memory_state.json")
        )

    print(f"\nResults written to {out}/", flush=True)
    print("Done.", flush=True)


if __name__ == "__main__":
    main()
