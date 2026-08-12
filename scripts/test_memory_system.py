#!/usr/bin/env python3
"""Test ReasoningMemory + StructuralReasoner on full ARC training set.

Verifies:
1. StructuralReasoner matches legacy solve_task_reasoning (no regressions)
2. Conjunction search finds new solves beyond single-property discrimination
3. Episodic recall works after accumulating episodes
4. 0 FP maintained with memory enabled
5. Memory grows (learned predicates, episodes)
"""
import json
import sys
import time
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reasoning_project.reasoning_engine import (
    GridDomainAdapter, StructuralReasoner, ReasoningMemory,
    solve_task_reasoning,
)


def load_arc_tasks(path):
    with open(path) as f:
        data = json.load(f)
    return data


def load_arc_solutions(path):
    with open(path) as f:
        return json.load(f)


def main():
    base = Path(__file__).resolve().parent.parent
    tasks = load_arc_tasks(base / "data/arc/arc-agi_training_challenges.json")
    solutions = load_arc_solutions(base / "data/arc/arc-agi_training_solutions.json")

    adapter = GridDomainAdapter()
    memory = ReasoningMemory()
    reasoner = StructuralReasoner(adapter, memory=memory)

    # Track results
    legacy_correct = []
    legacy_wrong = []
    reasoner_correct = []
    reasoner_wrong = []
    conjunction_solves = []
    new_solves = []  # solved by reasoner but not legacy

    task_ids = sorted(tasks.keys())
    n = len(task_ids)
    t0 = time.time()

    for idx, tid in enumerate(task_ids):
        task = tasks[tid]
        sol = solutions[tid]

        train_pairs = [
            (np.array(ex["input"]), np.array(ex["output"]))
            for ex in task["train"]
        ]
        test_inputs = [np.array(ex["input"]) for ex in task["test"]]
        test_outputs = [np.array(s) for s in sol]

        # Legacy path
        legacy_result = solve_task_reasoning(train_pairs, test_inputs)
        legacy_ok = False
        if legacy_result is not None:
            preds, meta = legacy_result
            if len(preds) == len(test_outputs):
                if all(np.array_equal(p, t) for p, t in zip(preds, test_outputs)):
                    legacy_ok = True
                    legacy_correct.append(tid)
                else:
                    legacy_wrong.append(tid)

        # StructuralReasoner path (with memory)
        reasoner_result = reasoner.solve(train_pairs, test_inputs)
        reasoner_ok = False
        if reasoner_result is not None:
            preds, meta = reasoner_result
            if len(preds) == len(test_outputs):
                if all(np.array_equal(p, t) for p, t in zip(preds, test_outputs)):
                    reasoner_ok = True
                    reasoner_correct.append((tid, meta))
                    if meta.get("learned"):
                        conjunction_solves.append((tid, meta))
                    if meta.get("source") == "episodic_recall":
                        conjunction_solves.append((tid, meta))
                else:
                    reasoner_wrong.append((tid, meta))

        if reasoner_ok and not legacy_ok:
            new_solves.append((tid, meta))

        if (idx + 1) % 100 == 0:
            elapsed = time.time() - t0
            print(f"  [{idx+1}/{n}] legacy={len(legacy_correct)} reasoner={len(reasoner_correct)} "
                  f"new={len(new_solves)} conj={len(conjunction_solves)} "
                  f"mem_preds={len(memory.learned_predicates)} episodes={len(memory.episodes)} "
                  f"({elapsed:.1f}s)")

    elapsed = time.time() - t0

    print("\n" + "="*70)
    print("REASONING MEMORY TEST RESULTS")
    print("="*70)
    print(f"Total tasks: {n}")
    print(f"Time: {elapsed:.1f}s")
    print()
    print(f"Legacy solve_task_reasoning:")
    print(f"  Correct: {len(legacy_correct)}")
    print(f"  Wrong (FP): {len(legacy_wrong)}")
    print()
    print(f"StructuralReasoner (with memory):")
    print(f"  Correct: {len(reasoner_correct)}")
    print(f"  Wrong (FP): {len(reasoner_wrong)}")
    print()
    print(f"New solves (reasoner only): {len(new_solves)}")
    for tid, meta in new_solves:
        print(f"  {tid}: {meta.get('strategy')} prop={meta.get('property', meta.get('filter_prop', '?'))}"
              f" learned={meta.get('learned', False)} source={meta.get('source', 'search')}")
    print()
    print(f"Conjunction solves: {len(conjunction_solves)}")
    for tid, meta in conjunction_solves:
        print(f"  {tid}: {meta}")
    print()
    print(f"Memory state:")
    print(f"  Learned predicates: {len(memory.learned_predicates)}")
    for name, props, mode in memory.learned_predicates:
        print(f"    {name} = {mode}({props})")
    print(f"  Episodes stored: {len(memory.episodes)}")
    print()

    if reasoner_wrong:
        print("FALSE POSITIVES:")
        for tid, meta in reasoner_wrong:
            print(f"  {tid}: {meta}")
    else:
        print("0 FALSE POSITIVES - SOUNDNESS MAINTAINED")

    # Regression check
    legacy_set = set(legacy_correct)
    reasoner_set = set(tid for tid, _ in reasoner_correct)
    regressions = legacy_set - reasoner_set
    if regressions:
        print(f"\nREGRESSIONS (legacy solved, reasoner didn't): {len(regressions)}")
        for tid in sorted(regressions):
            print(f"  {tid}")
    else:
        print("\n0 REGRESSIONS - all legacy solves preserved")


if __name__ == "__main__":
    main()
