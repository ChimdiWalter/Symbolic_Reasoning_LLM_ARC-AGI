#!/usr/bin/env python3
"""CLI batch runner for the per-task MDL solver.

Usage:
  python -m mdl.run_batch --tag smoke_12 --tasks TASK1,TASK2,...
  python -m mdl.run_batch --tag probe_40 --sample 40 --seed 7
  python -m mdl.run_batch --tag eval_full --split eval

Writes per-task results to mdl/outputs/<tag>.jsonl in realtime (one JSON
line per task, appended). Resumable: skips task IDs already in the output.
"""

import argparse
import json
import os
import random
import sys
import time
import traceback

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from mdl.solver import PerTaskMDL, MDLConfig


DATA_DIR = os.path.join(PROJECT_ROOT, "data", "arc")
OUT_DIR = os.path.join(PROJECT_ROOT, "mdl", "outputs")


def load_tasks(split="training"):
    """Load ARC challenge and solution files."""
    chal_path = os.path.join(DATA_DIR, f"arc-agi_{split}_challenges.json")
    sol_path = os.path.join(DATA_DIR, f"arc-agi_{split}_solutions.json")

    with open(chal_path) as f:
        challenges = json.load(f)

    solutions = {}
    if os.path.exists(sol_path):
        with open(sol_path) as f:
            solutions = json.load(f)

    return challenges, solutions


def get_done_ids(out_path):
    """Get set of task IDs already processed."""
    done = set()
    if os.path.exists(out_path):
        with open(out_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        rec = json.loads(line)
                        done.add(rec["task_id"])
                    except (json.JSONDecodeError, KeyError):
                        pass
    return done


def main():
    parser = argparse.ArgumentParser(description="MDL batch solver")
    parser.add_argument("--tag", required=True, help="Output tag name")
    parser.add_argument("--tasks", default=None,
                        help="Comma-separated task IDs")
    parser.add_argument("--sample", type=int, default=None,
                        help="Random sample N tasks")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for sampling")
    parser.add_argument("--split", default="training",
                        choices=["training", "evaluation"],
                        help="ARC split to use")
    parser.add_argument("--max-steps", type=int, default=2000,
                        help="Max training steps per task")
    parser.add_argument("--device", default="cuda",
                        help="Device (cuda/cpu)")
    parser.add_argument("--beta-kl", type=float, default=0.1,
                        help="KL weight")
    parser.add_argument("--hidden-dim", type=int, default=48,
                        help="Conv hidden dim")
    parser.add_argument("--latent-dim", type=int, default=24,
                        help="Latent code dim")
    parser.add_argument("--lr", type=float, default=0.008,
                        help="Learning rate")

    args = parser.parse_args()

    # Load data
    challenges, solutions = load_tasks(args.split)
    print(f"Loaded {len(challenges)} tasks from {args.split}", flush=True)

    # Select tasks
    if args.tasks:
        task_ids = args.tasks.split(",")
        # Validate
        for tid in task_ids:
            if tid not in challenges:
                print(f"WARNING: task {tid} not found in {args.split}",
                      flush=True)
        task_ids = [t for t in task_ids if t in challenges]
    elif args.sample:
        rng = random.Random(args.seed)
        all_ids = sorted(challenges.keys())
        task_ids = rng.sample(all_ids, min(args.sample, len(all_ids)))
    else:
        task_ids = sorted(challenges.keys())

    # Output file
    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, f"{args.tag}.jsonl")
    done_ids = get_done_ids(out_path)
    remaining = [t for t in task_ids if t not in done_ids]

    print(f"Tasks: {len(task_ids)} total, {len(done_ids)} done, "
          f"{len(remaining)} remaining", flush=True)

    if not remaining:
        print("Nothing to do.", flush=True)
        return

    # Config
    cfg = MDLConfig(
        max_steps=args.max_steps,
        device=args.device,
        seed=args.seed,
        beta_kl=args.beta_kl,
        hidden_dim=args.hidden_dim,
        latent_dim=args.latent_dim,
        lr=args.lr,
    )

    # Process tasks
    results_summary = {
        'total': len(remaining),
        'train_exact': 0,
        'test_correct': 0,
        'errors': 0,
    }
    t_global = time.time()

    for idx, tid in enumerate(remaining):
        print(f"\n{'='*60}", flush=True)
        print(f"[{idx+1}/{len(remaining)}] Task {tid}", flush=True)

        task = challenges[tid]
        sol = solutions.get(tid, None)

        try:
            solver = PerTaskMDL(task, cfg, solutions=sol)
            print(f"  params: {solver.n_params}, "
                  f"train_pairs: {solver.n_train}, "
                  f"size_strategy: {solver.size_strategy}", flush=True)

            result = solver.solve()

            # Record
            record = {
                'task_id': tid,
                'train_exact': result['train_exact'],
                'test_correct': result['test_correct'],
                'test_preds': result['test_preds'],
                'wall_time': round(result['wall_time'], 2),
                'train_time': round(result['train_time'], 2),
                'n_params': result['n_params'],
                'size_strategy': result['size_strategy'],
                'test_strategy': result['test_strategy'],
                'n_train_pairs': result['n_train_pairs'],
                'final_ce': round(result['final_ce'], 4)
                           if result['final_ce'] is not None else None,
                'final_kl': round(result['final_kl'], 4)
                           if result['final_kl'] is not None else None,
            }

            # Append to output file
            with open(out_path, 'a') as f:
                f.write(json.dumps(record) + '\n')

            # Update summary
            if result['train_exact']:
                results_summary['train_exact'] += 1
            if result['test_correct'] and any(result['test_correct']):
                results_summary['test_correct'] += 1

            any_correct = (result['test_correct'] and
                           any(result['test_correct']))
            print(f"  RESULT: train_exact={result['train_exact']}, "
                  f"test_correct={any_correct}, "
                  f"wall={result['wall_time']:.1f}s, "
                  f"strategy={result['test_strategy']}", flush=True)

        except Exception as e:
            print(f"  ERROR: {e}", flush=True)
            traceback.print_exc()
            results_summary['errors'] += 1
            # Write error record
            record = {
                'task_id': tid,
                'error': str(e),
                'train_exact': False,
                'test_correct': None,
                'wall_time': 0,
            }
            with open(out_path, 'a') as f:
                f.write(json.dumps(record) + '\n')

    total_time = time.time() - t_global
    print(f"\n{'='*60}", flush=True)
    print(f"BATCH SUMMARY ({args.tag}):", flush=True)
    print(f"  Total tasks: {results_summary['total']}", flush=True)
    print(f"  Train exact: {results_summary['train_exact']}", flush=True)
    print(f"  Test correct: {results_summary['test_correct']}", flush=True)
    print(f"  Errors: {results_summary['errors']}", flush=True)
    print(f"  Total wall time: {total_time:.1f}s "
          f"({total_time/60:.1f}min)", flush=True)
    print(f"  Avg per task: {total_time/max(1,results_summary['total']):.1f}s",
          flush=True)


if __name__ == "__main__":
    main()
