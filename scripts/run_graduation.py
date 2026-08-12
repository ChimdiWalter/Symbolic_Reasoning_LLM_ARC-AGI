#!/usr/bin/env python3
"""R1 near-solve graduation pass — standalone runner.

Usage:
    ARC_GRADUATE=1 python3 scripts/run_graduation.py
    ARC_GRADUATE=1 python3 scripts/run_graduation.py --workers 2 --budget 60
    ARC_GRADUATE=1 python3 scripts/run_graduation.py --out-dir outputs/graduation_v1

Env-gated: ARC_GRADUATE must be set (zero cost when off).
Resumable: completed task_ids in <out-dir>/progress.jsonl are skipped.
Output: realtime JSONL to <out-dir>/graduation_results.jsonl + summary.json.
"""
import argparse
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

PROJECT_ROOT = os.environ.get(
    "ARC_PROJECT_ROOT",
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))


def _graduate_one(task_id: str, task_data: dict, parts_data: list[dict],
                  budget_s: float, v20_dir: str) -> dict:
    """Worker function: graduate one task (runs in subprocess)."""
    # Reimport inside worker (subprocess)
    os.environ["ARC_GRADUATE"] = "1"
    os.environ.setdefault("PYTHONPATH", PROJECT_ROOT)
    sys.path.insert(0, PROJECT_ROOT)

    import numpy as np
    from geocat_arc.perception.grid import Grid
    from geocat_arc.object_reasoning.graduation import (
        graduate_task, _GRADUATE_ON,
    )
    from geocat_arc.object_reasoning.types import NearSolveRecord

    # Reconstruct train pairs
    train_pairs = []
    for pair in task_data["train"]:
        gi = Grid(np.array(pair["input"], dtype=np.int32))
        go = Grid(np.array(pair["output"], dtype=np.int32))
        train_pairs.append((gi, go))

    # Reconstruct NearSolveRecords
    records = [NearSolveRecord.from_dict(d) for d in parts_data]

    # Set up the engine output dir for library loading etc.
    from geocat_arc.object_reasoning.engine import ObjectReasoningEngine
    engine_dir = os.path.join(v20_dir, "object")

    # Load learned verbs for the worker
    try:
        from geocat_arc.object_reasoning.synth_verbs import LearnedVerbRegistry
        from geocat_arc.object_reasoning.correspondence import set_learned_verbs
        set_learned_verbs(LearnedVerbRegistry.load(engine_dir))
    except Exception:
        pass

    result = graduate_task(task_id, records, train_pairs, budget_s=budget_s)
    return result.to_dict()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-dir", default=os.path.join(PROJECT_ROOT,
                    "outputs/graduation_r1"))
    ap.add_argument("--v20-dir", default=os.path.join(PROJECT_ROOT,
                    "outputs/unified_harness_v20"))
    ap.add_argument("--workers", type=int, default=2,
                    help="Max parallel workers (default 2; keep low on loaded machine)")
    ap.add_argument("--budget", type=float, default=60.0,
                    help="Per-task budget in seconds")
    ap.add_argument("--max-tasks", type=int, default=None)
    ap.add_argument("--task-ids", nargs="*", default=None,
                    help="Specific task IDs to try (default: all unsolved near-solves)")
    args = ap.parse_args()

    # Gate check
    if os.environ.get("ARC_GRADUATE", "") in ("", "0"):
        print("ERROR: ARC_GRADUATE env var not set. "
              "Set ARC_GRADUATE=1 to enable graduation.")
        sys.exit(1)

    v20_dir = Path(args.v20_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Load ARC challenges
    arc_data_dir = Path(PROJECT_ROOT) / "data" / "arc"
    with open(arc_data_dir / "arc-agi_training_challenges.json") as f:
        challenges = json.load(f)

    # Load solved set
    results_path = v20_dir / "results.json"
    solved_ids: set[str] = set()
    if results_path.exists():
        with open(results_path) as f:
            results = json.load(f)
        for s in results.get("solved", []):
            if isinstance(s, dict):
                solved_ids.add(s["task_id"])
            else:
                solved_ids.add(str(s))

    # Load near-solve parts
    parts_dir = v20_dir / "object" / "near_solve_parts"
    if not parts_dir.is_dir():
        print(f"ERROR: parts directory not found: {parts_dir}")
        sys.exit(1)

    # Build target list
    target_parts: dict[str, list[dict]] = {}
    for fname in sorted(os.listdir(parts_dir)):
        if not fname.endswith(".jsonl"):
            continue
        task_id = fname.replace(".jsonl", "")
        if task_id in solved_ids:
            continue
        if task_id not in challenges:
            continue
        if args.task_ids and task_id not in args.task_ids:
            continue
        records = []
        with open(parts_dir / fname) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        if records:
            target_parts[task_id] = records

    if args.max_tasks:
        target_ids = sorted(target_parts.keys())[:args.max_tasks]
        target_parts = {k: v for k, v in target_parts.items()
                        if k in target_ids}

    # Load resume state
    progress_path = out_dir / "graduation_results.jsonl"
    completed: set[str] = set()
    if progress_path.exists():
        with open(progress_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    completed.add(rec["task_id"])
                except (json.JSONDecodeError, KeyError):
                    continue

    remaining = {k: v for k, v in target_parts.items() if k not in completed}

    print(f"=== R1 NEAR-SOLVE GRADUATION ===")
    print(f"Total unsolved parts: {len(target_parts)}")
    print(f"Already attempted: {len(completed)}")
    print(f"Remaining: {len(remaining)}")
    print(f"Workers: {args.workers}, budget: {args.budget}s/task")
    print(f"Output: {out_dir}")
    sys.stdout.flush()

    if not remaining:
        print("Nothing to do.")
        _write_summary(out_dir, progress_path)
        return

    # Run graduation
    started = time.monotonic()
    graduated_count = 0
    attempted = 0

    results_file = open(progress_path, "a")

    if args.workers <= 1:
        # Sequential mode
        for task_id, parts_data in sorted(remaining.items()):
            task_data = challenges[task_id]
            attempted += 1
            print(f"[{attempted}/{len(remaining)}] {task_id} ...",
                  end=" ", flush=True)
            try:
                result = _graduate_one(task_id, task_data, parts_data,
                                       args.budget, str(v20_dir))
            except Exception as e:
                result = {"task_id": task_id, "graduated": False,
                          "error": str(e), "routes_tried": [],
                          "route": "", "time_s": 0}
            results_file.write(json.dumps(result) + "\n")
            results_file.flush()
            if result.get("graduated"):
                graduated_count += 1
                print(f"GRADUATED ({result.get('route', '?')})")
            else:
                print(f"no ({','.join(result.get('routes_tried', []))})")
            sys.stdout.flush()
    else:
        # Parallel mode
        with ProcessPoolExecutor(max_workers=args.workers) as executor:
            futures = {}
            for task_id, parts_data in sorted(remaining.items()):
                task_data = challenges[task_id]
                fut = executor.submit(
                    _graduate_one, task_id, task_data, parts_data,
                    args.budget, str(v20_dir))
                futures[fut] = task_id

            for fut in as_completed(futures):
                task_id = futures[fut]
                attempted += 1
                try:
                    result = fut.result(timeout=args.budget + 30)
                except Exception as e:
                    result = {"task_id": task_id, "graduated": False,
                              "error": str(e), "routes_tried": [],
                              "route": "", "time_s": 0}
                results_file.write(json.dumps(result) + "\n")
                results_file.flush()
                if result.get("graduated"):
                    graduated_count += 1
                    print(f"[{attempted}/{len(remaining)}] {task_id}: "
                          f"GRADUATED ({result.get('route', '?')})")
                else:
                    print(f"[{attempted}/{len(remaining)}] {task_id}: "
                          f"no ({','.join(result.get('routes_tried', []))})")
                sys.stdout.flush()

    results_file.close()
    elapsed = time.monotonic() - started

    print(f"\n=== GRADUATION COMPLETE ===")
    print(f"Attempted: {attempted}")
    print(f"Graduated: {graduated_count}")
    print(f"Wall time: {elapsed:.1f}s")
    sys.stdout.flush()

    _write_summary(out_dir, progress_path)


def _write_summary(out_dir: Path, progress_path: Path) -> None:
    """Write summary.json from the progress file."""
    results = []
    if progress_path.exists():
        with open(progress_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        results.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass

    graduated = [r for r in results if r.get("graduated")]
    route_hist: dict[str, int] = {}
    for r in graduated:
        route = r.get("route", "unknown")
        route_hist[route] = route_hist.get(route, 0) + 1

    summary = {
        "total_attempted": len(results),
        "graduated_count": len(graduated),
        "graduated_task_ids": [r["task_id"] for r in graduated],
        "route_histogram": route_hist,
        "mean_time_s": (sum(r.get("time_s", 0) for r in results)
                        / max(len(results), 1)),
    }
    summary_path = out_dir / "summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"Summary written to {summary_path}")


if __name__ == "__main__":
    main()
