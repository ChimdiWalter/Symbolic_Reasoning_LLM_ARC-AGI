"""Run the reasoning engine on ARC tasks — infers rules, doesn't match templates."""
from __future__ import annotations
import json
import time
from pathlib import Path
import numpy as np

from geocat_arc.data.arc_loader import load_tasks
from geocat_arc.data.validate_arc import validate_task
from geocat_arc.reasoning.reasoning_engine import ReasoningEngine


ARTIFACTS_DIR = Path(__file__).resolve().parent.parent / "artifacts" / "geocat_arc"


def run_reasoning_evaluation(
    split: str = "training",
    max_tasks: int = 400,
    output_dir: Path | None = None,
) -> dict:
    output_dir = output_dir or ARTIFACTS_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    tasks = load_tasks(split=split)[:max_tasks]
    engine = ReasoningEngine()

    results = {
        "tasks_attempted": 0,
        "tasks_solved": 0,
        "tasks_loo_validated": 0,
        "near_solved_count": 0,
        "task_results": [],
        "strategy_counts": {},
    }

    start_time = time.time()

    for task in tasks:
        try:
            validate_task(task)
        except Exception:
            continue

        results["tasks_attempted"] += 1

        train_pairs = [
            (np.array(p.input, dtype=np.int32), np.array(p.output, dtype=np.int32))
            for p in task.train
        ]

        result = engine.solve(task.task_id, train_pairs)

        task_result = {
            "task_id": task.task_id,
            "solved": result.solution is not None and result.solution.is_exact,
            "strategy": result.solution.strategy if result.solution else None,
            "train_accuracy": float(result.best_accuracy),
            "loo_score": float(result.solution.loo_score) if result.solution else 0.0,
            "dominant_pattern": result.profile.dominant_pattern,
            "strategies_tried": len(result.strategies_tried),
            "near_solves": len(result.near_solves),
        }
        results["task_results"].append(task_result)

        if task_result["solved"]:
            results["tasks_solved"] += 1
            strategy = result.solution.strategy
            results["strategy_counts"][strategy] = results["strategy_counts"].get(strategy, 0) + 1
            if result.solution.loo_score >= 1.0:
                results["tasks_loo_validated"] += 1
        elif result.best_accuracy >= 0.8:
            results["near_solved_count"] += 1

    total_time = time.time() - start_time
    attempted = results["tasks_attempted"]
    results["solve_rate"] = results["tasks_solved"] / attempted if attempted > 0 else 0.0
    results["total_runtime_s"] = total_time

    with open(output_dir / "reasoning_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)

    return results


if __name__ == "__main__":
    results = run_reasoning_evaluation(max_tasks=400)
    print(f"Attempted: {results['tasks_attempted']}")
    print(f"Solved: {results['tasks_solved']}")
    print(f"LOO-validated: {results['tasks_loo_validated']}")
    print(f"Near-solved (>0.8): {results['near_solved_count']}")
    print(f"Solve rate: {results['solve_rate']:.2%}")
    print(f"Runtime: {results['total_runtime_s']:.1f}s")
    print()
    print("Strategy breakdown:")
    for strategy, count in sorted(results["strategy_counts"].items(), key=lambda x: -x[1]):
        print(f"  {strategy}: {count}")
