"""Run baseline evaluation on real ARC tasks."""
from __future__ import annotations
import json
import time
from pathlib import Path
from geocat_arc.data.arc_loader import load_tasks
from geocat_arc.data.validate_arc import validate_task
from geocat_arc.perception.grid import Grid
from geocat_arc.perception.objects import extract_objects
from geocat_arc.perception.relations import build_relation_graph
from geocat_arc.perception.change_detection import detect_changes
from geocat_arc.bayesian_program_search.real_objective import normalized_cell_accuracy
from geocat_arc.bayesian_program_search.search_loop import bayesian_search


ARTIFACTS_DIR = Path(__file__).resolve().parent.parent / "artifacts" / "geocat_arc"


def run_baseline(
    split: str = "training",
    max_tasks: int = 50,
    max_search_iters: int = 20,
    output_dir: Path | None = None,
) -> dict:
    output_dir = output_dir or ARTIFACTS_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    tasks = load_tasks(split=split)[:max_tasks]

    results = {
        "tasks_attempted": 0,
        "tasks_solved": 0,
        "near_solved_count": 0,
        "exact_train_solve_rate": 0.0,
        "task_results": [],
    }
    failures = []

    start_time = time.time()

    for task in tasks:
        try:
            validate_task(task)
        except Exception as e:
            continue

        results["tasks_attempted"] += 1
        task_start = time.time()

        best_program, best_score, trace = bayesian_search(
            task, max_iterations=max_search_iters,
        )

        task_time = time.time() - task_start
        is_solved = best_score >= 1.95
        is_near_solved = not is_solved and best_score >= 0.8

        task_result = {
            "task_id": task.task_id,
            "best_score": float(best_score),
            "solved": bool(is_solved),
            "near_solved": bool(is_near_solved),
            "runtime_s": float(task_time),
            "iterations": int(len(trace.records)),
        }
        results["task_results"].append(task_result)

        if is_solved:
            results["tasks_solved"] += 1
        elif is_near_solved:
            results["near_solved_count"] += 1
        else:
            failures.append({
                "task_id": task.task_id,
                "best_score": float(best_score),
                "runtime_s": float(task_time),
            })

    total_time = time.time() - start_time
    attempted = results["tasks_attempted"]
    results["exact_train_solve_rate"] = results["tasks_solved"] / attempted if attempted > 0 else 0.0
    results["total_runtime_s"] = total_time

    with open(output_dir / "baseline_results.json", "w") as f:
        json.dump(results, f, indent=2)

    with open(output_dir / "baseline_failures.jsonl", "w") as f:
        for fail in failures:
            f.write(json.dumps(fail) + "\n")

    manifest = {
        "split": split,
        "max_tasks": max_tasks,
        "max_search_iters": max_search_iters,
        "total_runtime_s": total_time,
        "timestamp": time.time(),
    }
    with open(output_dir / "run_manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)

    return results


if __name__ == "__main__":
    results = run_baseline(max_tasks=10, max_search_iters=10)
    print(f"Attempted: {results['tasks_attempted']}")
    print(f"Solved: {results['tasks_solved']}")
    print(f"Near-solved: {results['near_solved_count']}")
    print(f"Solve rate: {results['exact_train_solve_rate']:.2%}")
