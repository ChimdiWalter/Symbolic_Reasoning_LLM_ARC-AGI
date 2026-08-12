"""Run the unified evaluation harness (Stage 0) — pipeline + GeoCat merged.

Usage:
    python scripts/run_unified_harness.py                      # all 1000 tasks
    python scripts/run_unified_harness.py --subset-file F      # subset run
    python scripts/run_unified_harness.py --workers 20 --out-dir outputs/unified_harness_v1

--subset-file accepts either a JSON list of task ids or a JSON object with a
"task_ids" key.  Runs are resumable: completed task_ids in
<out-dir>/progress.jsonl are skipped on restart.
"""
import argparse
import json
import os
import sys
import time

PROJECT_ROOT = os.environ.get(
    "ARC_PROJECT_ROOT",
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--subset-file", default=None,
                    help="JSON list of task ids (or object with 'task_ids')")
    ap.add_argument("--out-dir",
                    default=os.path.join(PROJECT_ROOT, "outputs/unified_harness_v1"))
    ap.add_argument("--workers", type=int, default=20)
    ap.add_argument("--timeout-per-task", type=float, default=60.0)
    ap.add_argument("--per-layer-timeout", type=float, default=8.0)
    ap.add_argument("--max-tasks", type=int, default=None)
    ap.add_argument("--run-id", default=None,
                    help="Run identifier stamped into near-solve rows "
                         "(default: launch timestamp)")
    ap.add_argument("--global-budget-s", type=float, default=None,
                    help="TOTAL wall-clock budget (s) for the whole run — "
                         "per-task budgets rescale to the remaining clock "
                         "(Kaggle 12h notebook governor)")
    ap.add_argument("--emit-predictions", action="store_true",
                    help="persist test renders per task in progress.jsonl "
                         "(attempt_1 = solving layer, attempt_2 = best "
                         "uncertified object partial) — the Kaggle path")
    ap.add_argument("--split", default="training",
                    choices=("training", "evaluation"),
                    help="ARC split (paper E3 frozen transfer uses "
                         "'evaluation'; the SYSTEM is identical — data "
                         "path only)")
    args = ap.parse_args()

    from harness.run_harness import run_harness

    with open(os.path.join(PROJECT_ROOT,
                           f"data/arc/arc-agi_{args.split}_challenges.json")) as f:
        challenges = json.load(f)
    try:
        with open(os.path.join(
                PROJECT_ROOT,
                f"data/arc/arc-agi_{args.split}_solutions.json")) as f:
            solutions = json.load(f)
    except FileNotFoundError:
        solutions = {}
    # Kaggle: no solutions exist — layers treat None as 'no offline scoring'
    solutions = {tid: solutions.get(tid) for tid in challenges}

    if args.subset_file:
        with open(args.subset_file) as f:
            subset = json.load(f)
        task_ids = subset["task_ids"] if isinstance(subset, dict) else subset
        missing = [t for t in task_ids if t not in challenges]
        if missing:
            raise SystemExit(f"subset contains unknown task ids: {missing[:5]}")
    else:
        task_ids = sorted(challenges.keys())
    if args.max_tasks:
        task_ids = task_ids[: args.max_tasks]

    config = {
        "run_id": args.run_id or time.strftime("%Y-%m-%dT%H:%M:%S"),
        "timeout_per_task": args.timeout_per_task,
        "per_layer_timeout": args.per_layer_timeout,
        "submission_mode": True,
        "subset_file": args.subset_file,
        "data": f"arc-agi_{args.split} ({len(challenges)} tasks)",
        "emit_predictions": bool(args.emit_predictions),
        "global_budget_s": args.global_budget_s,
    }
    run_harness(challenges, solutions, task_ids,
                out_dir=args.out_dir, workers=args.workers, config=config)


if __name__ == "__main__":
    main()
