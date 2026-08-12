#!/usr/bin/env python3
"""Strong-form LOO gate for the per-task MDL solver v2.

Same protocol as loo_gate.py but uses the v2 equivariant solver.
For each task with N train pairs, retrains from scratch N times.
"""

import json
import os
import sys
import time

import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from mdl.solver_v2 import PerTaskMDLv2, MDLConfigV2


def loo_gate_v2(task, cfg, task_id="unknown"):
    """Run strong-form LOO gate on a single task using v2 solver.

    Returns dict with per-fold results and overall verdict.
    """
    train_pairs = task['train']
    n = len(train_pairs)
    per_fold = []
    t0 = time.time()

    for fold_idx in range(n):
        t_fold = time.time()
        loo_train = [train_pairs[j] for j in range(n) if j != fold_idx]
        held_out = train_pairs[fold_idx]

        loo_task = {
            'train': loo_train,
            'test': [{'input': held_out['input']}]
        }
        held_out_output = held_out['output']

        solver = PerTaskMDLv2(loo_task, cfg, solutions=[held_out_output])

        try:
            result = solver.solve()
            pred = result['test_preds'][0]
            held_out_correct = (pred == held_out_output)

            fold_result = {
                'fold_idx': fold_idx,
                'held_out_correct': held_out_correct,
                'train_exact': result['train_exact'],
                'wall_time': round(time.time() - t_fold, 2),
            }
        except Exception as e:
            fold_result = {
                'fold_idx': fold_idx,
                'held_out_correct': False,
                'train_exact': False,
                'error': str(e),
                'wall_time': round(time.time() - t_fold, 2),
            }

        per_fold.append(fold_result)
        status = "PASS" if fold_result['held_out_correct'] else "FAIL"
        print(f"  fold {fold_idx}/{n}: {status} "
              f"(train_exact={fold_result['train_exact']}, "
              f"{fold_result['wall_time']:.1f}s)", flush=True)

    folds_passed = sum(1 for f in per_fold if f['held_out_correct'])
    total_time = time.time() - t0

    return {
        'task_id': task_id,
        'folds_passed': folds_passed,
        'folds_total': n,
        'all_passed': folds_passed == n,
        'any_passed': folds_passed > 0,
        'per_fold': per_fold,
        'wall_time': round(total_time, 2),
        'version': 'v2',
    }


def main():
    """Run LOO gate v2 on tasks from a probe output or explicit list."""
    import argparse
    parser = argparse.ArgumentParser(
        description="Strong-form LOO gate (v2 solver)")
    parser.add_argument("--probe", default=None,
                        help="JSONL probe output to draw train-exact tasks from")
    parser.add_argument("--tasks", default=None,
                        help="Comma-separated task IDs")
    parser.add_argument("--tag", default="loo_gate_v2",
                        help="Output tag name")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-steps", type=int, default=3000)
    parser.add_argument("--device", default="cuda")
    args = parser.parse_args()

    # Load ARC data
    chal_path = os.path.join(PROJECT_ROOT, "data", "arc",
                             "arc-agi_training_challenges.json")
    sol_path = os.path.join(PROJECT_ROOT, "data", "arc",
                            "arc-agi_training_solutions.json")
    with open(chal_path) as f:
        challenges = json.load(f)
    with open(sol_path) as f:
        solutions = json.load(f)

    # Determine which tasks to gate
    if args.probe:
        probe_path = args.probe
        if not os.path.isabs(probe_path):
            probe_path = os.path.join(PROJECT_ROOT, probe_path)
        task_ids = []
        with open(probe_path) as f:
            for line in f:
                if line.strip():
                    rec = json.loads(line)
                    # Gate only train-exact tasks
                    if rec.get('train_exact'):
                        task_ids.append(rec['task_id'])
        print(f"Loaded {len(task_ids)} train-exact tasks from {args.probe}",
              flush=True)
    elif args.tasks:
        task_ids = args.tasks.split(",")
    else:
        print("ERROR: provide --probe or --tasks", file=sys.stderr)
        sys.exit(1)

    cfg = MDLConfigV2(
        max_steps=args.max_steps,
        device=args.device,
        seed=args.seed,
        log_interval=500,
    )

    out_dir = os.path.join(PROJECT_ROOT, "mdl", "outputs")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{args.tag}.jsonl")

    # Resume
    done = set()
    if os.path.exists(out_path):
        with open(out_path) as f:
            for line in f:
                if line.strip():
                    try:
                        rec = json.loads(line)
                        done.add(rec['task_id'])
                    except (json.JSONDecodeError, KeyError):
                        pass

    remaining = [t for t in task_ids if t not in done]
    print(f"LOO gate v2: {len(task_ids)} tasks, {len(done)} done, "
          f"{len(remaining)} remaining", flush=True)

    for idx, tid in enumerate(remaining):
        task = challenges[tid]
        n_pairs = len(task['train'])
        print(f"\n{'='*60}", flush=True)
        print(f"[{idx+1}/{len(remaining)}] Task {tid} "
              f"({n_pairs} pairs, {n_pairs} folds)", flush=True)

        result = loo_gate_v2(task, cfg, task_id=tid)

        with open(out_path, 'a') as f:
            f.write(json.dumps(result) + '\n')

        verdict = ("ALL PASSED" if result['all_passed']
                    else f"{result['folds_passed']}/{result['folds_total']} passed")
        print(f"  LOO RESULT: {verdict} wall={result['wall_time']:.1f}s",
              flush=True)

    # Summary
    print(f"\n{'='*60}", flush=True)
    print("LOO GATE V2 SUMMARY", flush=True)
    all_results = []
    with open(out_path) as f:
        for line in f:
            if line.strip():
                all_results.append(json.loads(line))

    any_pass_count = sum(1 for r in all_results if r.get('any_passed'))
    all_pass_count = sum(1 for r in all_results if r.get('all_passed'))
    print(f"  Total gated: {len(all_results)}", flush=True)
    print(f"  Any-fold pass: {any_pass_count}", flush=True)
    print(f"  All-fold pass: {all_pass_count}", flush=True)


if __name__ == "__main__":
    main()
