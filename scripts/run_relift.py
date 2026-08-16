#!/usr/bin/env python3
"""R2 relational relift pass -- standalone runner.

Loads the 194 parameter-overfit near-solve programs (train-perfect but
LOO-fail) and attempts to RE-EXPRESS each constant/extensional parameter
as a relational or feature expression, keeping the program train-perfect,
then full LOO recertification.

Usage:
    ARC_RELIFT=1 python3.12 scripts/run_relift.py
    ARC_RELIFT=1 python3.12 scripts/run_relift.py --budget 30 --max-tasks 10
    ARC_RELIFT=1 python3.12 scripts/run_relift.py --task-ids 00dbd492 045e512c

Env-gated: ARC_RELIFT=1 required (zero cost when off).
Resumable: completed task_ids in output JSONL are skipped.
Output: realtime JSONL to outputs/r2_relift/relift_results.jsonl.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = os.environ.get(
    "ARC_PROJECT_ROOT",
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-dir", default=os.path.join(
        PROJECT_ROOT, "outputs/r2_relift"))
    ap.add_argument("--graduation-results", default=os.path.join(
        PROJECT_ROOT,
        "outputs/graduation_r1_contention/graduation_results.jsonl"))
    ap.add_argument("--near-solve-dir", default=os.path.join(
        PROJECT_ROOT,
        "outputs/unified_harness_v10/object/near_solve_parts"))
    ap.add_argument("--budget", type=float, default=60.0,
                    help="Per-task budget in seconds (default 60)")
    ap.add_argument("--max-tasks", type=int, default=None,
                    help="Max tasks to process (default: all)")
    ap.add_argument("--task-ids", nargs="*", default=None,
                    help="Specific task IDs to process")
    args = ap.parse_args()

    # Env gate
    if os.environ.get("ARC_RELIFT", "") in ("", "0"):
        print("ERROR: ARC_RELIFT env var not set. "
              "Set ARC_RELIFT=1 to enable the relift pass.",
              file=sys.stderr)
        sys.exit(1)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    results_path = out_dir / "relift_results.jsonl"

    # -----------------------------------------------------------------------
    # 1. Load graduation results -- filter for graduated=false + partial_fit=1.0
    # -----------------------------------------------------------------------
    grad_path = Path(args.graduation_results)
    if not grad_path.exists():
        print(f"ERROR: graduation results not found: {grad_path}",
              file=sys.stderr)
        sys.exit(1)

    target_task_ids: list[str] = []
    with open(grad_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            if not d.get("graduated", True) and d.get("partial_fit") == 1.0:
                target_task_ids.append(d["task_id"])

    if args.task_ids:
        target_task_ids = [t for t in args.task_ids
                           if t in set(target_task_ids)]
    if args.max_tasks:
        target_task_ids = target_task_ids[:args.max_tasks]

    print(f"Relift targets: {len(target_task_ids)} tasks "
          f"(parameter-overfit, train-perfect but LOO-fail)")

    # -----------------------------------------------------------------------
    # 2. Load ARC challenges + solutions
    # -----------------------------------------------------------------------
    arc_data_dir = Path(PROJECT_ROOT) / "data" / "arc"
    with open(arc_data_dir / "arc-agi_training_challenges.json") as f:
        challenges = json.load(f)
    solutions_path = arc_data_dir / "arc-agi_training_solutions.json"
    solutions = {}
    if solutions_path.exists():
        with open(solutions_path) as f:
            solutions = json.load(f)

    # -----------------------------------------------------------------------
    # 3. Load near-solve parts
    # -----------------------------------------------------------------------
    near_solve_dir = Path(args.near_solve_dir)
    if not near_solve_dir.is_dir():
        print(f"ERROR: near-solve parts dir not found: {near_solve_dir}",
              file=sys.stderr)
        sys.exit(1)

    # -----------------------------------------------------------------------
    # 4. Resumability -- load already-done task IDs
    # -----------------------------------------------------------------------
    done_ids: set[str] = set()
    if results_path.exists():
        with open(results_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                    done_ids.add(d["task_id"])
                except (json.JSONDecodeError, KeyError):
                    continue
    if done_ids:
        print(f"Resuming: {len(done_ids)} tasks already done, "
              f"skipping them")
    remaining = [t for t in target_task_ids if t not in done_ids]
    print(f"Tasks to process: {len(remaining)}")

    # -----------------------------------------------------------------------
    # 5. Import engine components (after path setup)
    # -----------------------------------------------------------------------
    import numpy as np
    from geocat_arc.perception.grid import Grid
    from geocat_arc.object_reasoning.relift import relift_program

    # -----------------------------------------------------------------------
    # 6. Process each task
    # -----------------------------------------------------------------------
    total = len(remaining)
    success_count = 0
    loo_pass_count = 0
    lifted_any = 0
    errors = 0
    t_start = time.monotonic()

    for idx, task_id in enumerate(remaining):
        t_task = time.monotonic()

        # Load task data
        if task_id not in challenges:
            print(f"  [{idx+1}/{total}] {task_id}: SKIP (not in challenges)")
            continue

        task_data = challenges[task_id]
        train_pairs = []
        for pair in task_data["train"]:
            gi = Grid(np.array(pair["input"], dtype=np.int32))
            go = Grid(np.array(pair["output"], dtype=np.int32))
            train_pairs.append((gi, go))

        # Load best near-solve record for this task
        ns_path = near_solve_dir / f"{task_id}.jsonl"
        if not ns_path.exists():
            print(f"  [{idx+1}/{total}] {task_id}: SKIP (no near-solve part)")
            continue

        program_dict = None
        best_fit = -1.0
        with open(ns_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    fit = rec.get("train_fit_pixels", 0.0)
                    if fit >= best_fit and rec.get("program_partial"):
                        best_fit = fit
                        program_dict = rec["program_partial"]
                except (json.JSONDecodeError, KeyError):
                    continue

        if program_dict is None:
            print(f"  [{idx+1}/{total}] {task_id}: SKIP (no program_partial)")
            continue

        # Run relift
        try:
            result = relift_program(
                program_dict, train_pairs,
                task_id=task_id, budget_s=args.budget)
        except Exception as exc:
            result_dict = {
                "task_id": task_id,
                "success": False,
                "error": f"exception: {exc}",
                "time_s": time.monotonic() - t_task,
            }
            with open(results_path, "a") as f:
                f.write(json.dumps(result_dict) + "\n")
            errors += 1
            print(f"  [{idx+1}/{total}] {task_id}: ERROR ({exc})")
            continue

        result_dict = result.to_dict()
        with open(results_path, "a") as f:
            f.write(json.dumps(result_dict) + "\n")

        status = "FAIL"
        if result.success:
            success_count += 1
            status = "SUCCESS (LOO passed)"
        elif result.constants_lifted > 0:
            lifted_any += 1
            if result.loo_passed:
                loo_pass_count += 1
                status = "LIFTED (LOO passed but not full success?)"
            else:
                status = (f"LIFTED {result.constants_lifted}/"
                          f"{result.constants_total} but LOO failed")
        elif result.error:
            status = f"FAIL ({result.error})"

        elapsed = result.time_s
        print(f"  [{idx+1}/{total}] {task_id}: {status} "
              f"({elapsed:.1f}s)")

    # -----------------------------------------------------------------------
    # 7. Summary
    # -----------------------------------------------------------------------
    total_time = time.monotonic() - t_start
    print(f"\n{'='*60}")
    print(f"Relift pass complete")
    print(f"  Total tasks processed: {total}")
    print(f"  Success (relifted + LOO passed): {success_count}")
    print(f"  Lifted some constants (LOO failed): {lifted_any}")
    print(f"  Errors: {errors}")
    print(f"  Wall time: {total_time:.1f}s")
    print(f"  Results: {results_path}")

    # Write summary
    summary = {
        "total_tasks": total,
        "success_count": success_count,
        "lifted_any": lifted_any,
        "errors": errors,
        "wall_time_s": total_time,
        "budget_per_task_s": args.budget,
    }
    summary_path = out_dir / "relift_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"  Summary: {summary_path}")


if __name__ == "__main__":
    main()
