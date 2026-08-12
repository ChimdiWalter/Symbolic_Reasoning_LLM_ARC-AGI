#!/usr/bin/env python3
"""Strong-form LOO gate for the per-task MDL solver.

For each task with N train pairs, retrain from scratch N times. In fold i,
the train set is the N-1 OTHER pairs, the "test" is pair i's input, and
we require exact match on pair i's output.

This is the STRONG form of the gate (same protocol as the symbolic engine):
the model is retrained from scratch per fold, so it tests whether the
learned rule generalizes to unseen examples, not just whether a fixed model
memorized them.

Scientific question: does LOO-all-folds-pass separate test-correct tasks
from test-wrong tasks for a per-task neural learner?
"""

import json
import os
import sys
import time

import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from mdl.solver import PerTaskMDL, MDLConfig


def loo_gate(task, cfg, task_id="unknown"):
    """Run strong-form LOO gate on a single task.

    Returns dict with:
      folds_passed: int
      folds_total: int
      per_fold: list of {fold_idx, held_out_correct, train_exact, wall_time}
      all_passed: bool
      wall_time: float
    """
    train_pairs = task['train']
    n = len(train_pairs)
    per_fold = []
    t0 = time.time()

    for fold_idx in range(n):
        t_fold = time.time()
        # Build LOO task: N-1 train pairs, held-out pair as test
        loo_train = [train_pairs[j] for j in range(n) if j != fold_idx]
        held_out = train_pairs[fold_idx]

        loo_task = {
            'train': loo_train,
            'test': [{'input': held_out['input']}]
        }

        # The solution for scoring
        held_out_output = held_out['output']

        # Retrain from scratch
        solver = PerTaskMDL(loo_task, cfg, solutions=[held_out_output])

        try:
            result = solver.solve()
            pred = result['test_preds'][0]

            # Check exact match
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
        'per_fold': per_fold,
        'wall_time': round(total_time, 2),
    }


def main():
    """Run LOO gate on specified tasks."""
    # Tasks to test: 3 test-correct + 5 test-wrong-but-train-exact
    test_correct_ids = ['794b24be', 'a699fb00', 'a79310a0']
    test_wrong_ids = ['662c240a', 'ea9794b1', '13f06aa5', '95755ff2', '140c817e']
    all_ids = test_correct_ids + test_wrong_ids

    # Load data
    chal_path = os.path.join(PROJECT_ROOT, "data", "arc",
                             "arc-agi_training_challenges.json")
    sol_path = os.path.join(PROJECT_ROOT, "data", "arc",
                            "arc-agi_training_solutions.json")
    with open(chal_path) as f:
        challenges = json.load(f)
    with open(sol_path) as f:
        solutions = json.load(f)

    # Config: same as probe run
    cfg = MDLConfig(
        max_steps=2000,
        device="cuda",
        seed=42,
        log_interval=500,  # less verbose for LOO
    )

    # Output
    out_dir = os.path.join(PROJECT_ROOT, "mdl", "outputs")
    out_path = os.path.join(out_dir, "loo_gate.jsonl")

    # Check for already-done tasks
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

    remaining = [tid for tid in all_ids if tid not in done]
    print(f"LOO gate: {len(all_ids)} tasks, {len(done)} done, "
          f"{len(remaining)} remaining", flush=True)

    for idx, tid in enumerate(remaining):
        is_tc = tid in test_correct_ids
        label = "TEST-CORRECT" if is_tc else "TEST-WRONG"
        task = challenges[tid]
        n_pairs = len(task['train'])

        print(f"\n{'='*60}", flush=True)
        print(f"[{idx+1}/{len(remaining)}] Task {tid} ({label}, "
              f"{n_pairs} pairs, {n_pairs} folds)", flush=True)

        result = loo_gate(task, cfg, task_id=tid)
        result['is_test_correct'] = is_tc
        result['label'] = label

        # Append to output
        with open(out_path, 'a') as f:
            f.write(json.dumps(result) + '\n')

        verdict = "ALL PASSED" if result['all_passed'] else \
                  f"{result['folds_passed']}/{result['folds_total']} passed"
        print(f"  LOO RESULT: {verdict} ({label}) "
              f"wall={result['wall_time']:.1f}s", flush=True)

    # Summary
    print(f"\n{'='*60}", flush=True)
    print("LOO GATE SUMMARY", flush=True)
    print(f"{'='*60}", flush=True)

    all_results = []
    with open(out_path) as f:
        for line in f:
            if line.strip():
                all_results.append(json.loads(line))

    for r in all_results:
        label = r.get('label', '?')
        verdict = "ALL PASSED" if r['all_passed'] else \
                  f"{r['folds_passed']}/{r['folds_total']} passed"
        print(f"  {r['task_id']} ({label:>12}): LOO {verdict} "
              f"[wall={r['wall_time']:.1f}s]", flush=True)

    # Separation analysis
    tc_tasks = [r for r in all_results if r.get('is_test_correct')]
    tw_tasks = [r for r in all_results if not r.get('is_test_correct')]
    tc_loo_pass = sum(1 for r in tc_tasks if r['all_passed'])
    tw_loo_pass = sum(1 for r in tw_tasks if r['all_passed'])

    print(f"\nSEPARATION:")
    print(f"  Test-correct tasks that LOO-pass: {tc_loo_pass}/{len(tc_tasks)}")
    print(f"  Test-wrong tasks that LOO-pass:   {tw_loo_pass}/{len(tw_tasks)}")

    if tc_loo_pass > 0 and tw_loo_pass == 0:
        print("  => CLEAN SEPARATION: LOO gate correctly identifies "
              "test-correct tasks")
    elif tc_loo_pass == 0:
        print("  => LOO gate too strict: rejects even test-correct tasks")
    else:
        print(f"  => PARTIAL separation: LOO precision = "
              f"{tc_loo_pass}/{tc_loo_pass + tw_loo_pass}")


if __name__ == "__main__":
    main()
