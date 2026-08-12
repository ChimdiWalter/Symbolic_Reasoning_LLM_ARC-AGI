#!/usr/bin/env python3
"""CLI batch runner for the per-task MDL solver v2.

Usage:
  python -m mdl.run_batch_v2 --tag probe_40_v2 --sample 40 --seed 7
  python -m mdl.run_batch_v2 --tag probe_40_v2 --from-probe mdl/outputs/probe_40.jsonl
  python -m mdl.run_batch_v2 --tag uncovered_100 --sample 100 --seed 7 \
         --exclude-ids certified_ids.json

Same CLI contract as run_batch.py with v2 defaults.
Writes per-task results to mdl/outputs/<tag>.jsonl (resumable).
"""

import argparse
import json
import os
import random
import sys
import time
import traceback

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from mdl.solver_v2 import PerTaskMDLv2, MDLConfigV2

DATA_DIR = os.path.join(PROJECT_ROOT, "data", "arc")
OUT_DIR = os.path.join(PROJECT_ROOT, "mdl", "outputs")


def load_tasks(split="training"):
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


def load_ids_from_jsonl(path):
    """Load task IDs from a JSONL file."""
    ids = []
    with open(path) as f:
        for line in f:
            if line.strip():
                try:
                    rec = json.loads(line)
                    ids.append(rec["task_id"])
                except (json.JSONDecodeError, KeyError):
                    pass
    return ids


def main():
    parser = argparse.ArgumentParser(description="MDL v2 batch solver")
    parser.add_argument("--tag", required=True, help="Output tag name")
    parser.add_argument("--tasks", default=None,
                        help="Comma-separated task IDs")
    parser.add_argument("--from-probe", default=None,
                        help="Load task IDs from a JSONL probe file")
    parser.add_argument("--sample", type=int, default=None,
                        help="Random sample N tasks")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for sampling AND training")
    parser.add_argument("--split", default="training",
                        choices=["training", "evaluation"])
    parser.add_argument("--max-steps", type=int, default=2000)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--beta-kl", type=float, default=0.1)
    parser.add_argument("--hidden-dim", type=int, default=48)
    parser.add_argument("--latent-dim", type=int, default=16)
    parser.add_argument("--lr", type=float, default=0.008)
    parser.add_argument("--exclude-ids", default=None,
                        help="JSON file with list of task IDs to exclude")
    parser.add_argument("--n-test-samples", type=int, default=8,
                        help="Number of z samples for majority voting")
    parser.add_argument("--gpu-mem-frac", type=float, default=None,
                        help="Limit GPU memory to this fraction (e.g. 0.35)")

    args = parser.parse_args()

    # Apply GPU memory limit if requested
    if args.gpu_mem_frac is not None and args.device.startswith("cuda"):
        import torch
        if torch.cuda.is_available():
            torch.cuda.set_per_process_memory_fraction(args.gpu_mem_frac)

    challenges, solutions = load_tasks(args.split)
    print(f"Loaded {len(challenges)} tasks from {args.split}", flush=True)

    # Select tasks
    if args.from_probe:
        probe_path = args.from_probe
        if not os.path.isabs(probe_path):
            probe_path = os.path.join(PROJECT_ROOT, probe_path)
        task_ids = load_ids_from_jsonl(probe_path)
        print(f"Loaded {len(task_ids)} task IDs from {args.from_probe}",
              flush=True)
    elif args.tasks:
        task_ids = [t for t in args.tasks.split(",") if t in challenges]
    elif args.sample:
        rng = random.Random(args.seed)
        all_ids = sorted(challenges.keys())

        # Exclude certified IDs if requested
        if args.exclude_ids:
            excl_path = args.exclude_ids
            if not os.path.isabs(excl_path):
                excl_path = os.path.join(PROJECT_ROOT, excl_path)
            with open(excl_path) as f:
                excl = set(json.load(f))
            all_ids = [t for t in all_ids if t not in excl]
            print(f"After excluding {len(excl)} IDs: {len(all_ids)} remain",
                  flush=True)

        task_ids = rng.sample(all_ids, min(args.sample, len(all_ids)))
    else:
        task_ids = sorted(challenges.keys())

    # Output
    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, f"{args.tag}.jsonl")
    done_ids = get_done_ids(out_path)
    remaining = [t for t in task_ids if t not in done_ids]

    print(f"Tasks: {len(task_ids)} total, {len(done_ids)} done, "
          f"{len(remaining)} remaining", flush=True)
    if not remaining:
        print("Nothing to do.", flush=True)
        return

    cfg = MDLConfigV2(
        max_steps=args.max_steps,
        device=args.device,
        seed=args.seed,
        beta_kl=args.beta_kl,
        hidden_dim=args.hidden_dim,
        latent_dim=args.latent_dim,
        lr=args.lr,
        n_test_samples=args.n_test_samples,
    )

    results_summary = {
        'total': len(remaining), 'train_exact': 0,
        'test_correct': 0, 'errors': 0,
    }
    t_global = time.time()

    for idx, tid in enumerate(remaining):
        print(f"\n{'='*60}", flush=True)
        print(f"[{idx+1}/{len(remaining)}] Task {tid}", flush=True)

        task = challenges[tid]
        sol = solutions.get(tid, None)

        try:
            solver = PerTaskMDLv2(task, cfg, solutions=sol)
            print(f"  params: {solver.n_params}, "
                  f"train_pairs: {solver.n_train}, "
                  f"size_strategy: {solver.size_strategy}", flush=True)

            result = solver.solve()

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
                'final_ce': (round(result['final_ce'], 4)
                             if result['final_ce'] is not None else None),
                'final_kl': (round(result['final_kl'], 4)
                             if result['final_kl'] is not None else None),
                'version': 'v2',
            }

            with open(out_path, 'a') as f:
                f.write(json.dumps(record) + '\n')

            if result['train_exact']:
                results_summary['train_exact'] += 1
            if result['test_correct'] and any(result['test_correct']):
                results_summary['test_correct'] += 1

            any_correct = (result['test_correct']
                           and any(result['test_correct']))
            print(f"  RESULT: train_exact={result['train_exact']}, "
                  f"test_correct={any_correct}, "
                  f"wall={result['wall_time']:.1f}s, "
                  f"strategy={result['test_strategy']}", flush=True)

        except Exception as e:
            print(f"  ERROR: {e}", flush=True)
            traceback.print_exc()
            results_summary['errors'] += 1
            record = {
                'task_id': tid,
                'error': str(e),
                'train_exact': False,
                'test_correct': None,
                'wall_time': 0,
                'version': 'v2',
            }
            with open(out_path, 'a') as f:
                f.write(json.dumps(record) + '\n')

    total_time = time.time() - t_global
    print(f"\n{'='*60}", flush=True)
    print(f"BATCH SUMMARY ({args.tag}, v2):", flush=True)
    print(f"  Total tasks: {results_summary['total']}", flush=True)
    print(f"  Train exact: {results_summary['train_exact']}", flush=True)
    print(f"  Test correct: {results_summary['test_correct']}", flush=True)
    print(f"  Errors: {results_summary['errors']}", flush=True)
    print(f"  Total wall time: {total_time:.1f}s "
          f"({total_time/60:.1f}min)", flush=True)
    print(f"  Avg per task: "
          f"{total_time/max(1,results_summary['total']):.1f}s", flush=True)


if __name__ == "__main__":
    main()
