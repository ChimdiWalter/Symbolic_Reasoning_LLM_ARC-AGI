#!/usr/bin/env python3
"""Round-18 generator mining: extract residuals, mine generators,
run M3b admission, and the E10 rediscovery experiment.

Usage:
    # Full mining run (substrate + mine + admit + E10):
    python scripts/run_generator_mining.py --mode full

    # E10 rediscovery experiment only:
    python scripts/run_generator_mining.py --mode e10

    # Substrate extraction only:
    python scripts/run_generator_mining.py --mode substrate

    # Mining on existing substrate:
    python scripts/run_generator_mining.py --mode mine
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ["ARC_GENERATIVE"] = "1"

from geocat_arc.data.arc_loader import load_task, list_task_ids
from geocat_arc.perception.grid import Grid
from geocat_arc.object_reasoning.generator_mining import (
    AdmittedGenerator,
    extract_residuals_for_task,
    mine_generators,
    admit_generator_m3b,
    cluster_residuals,
    load_residuals,
    save_residuals,
    save_admitted_generators,
    load_admitted_generators,
    run_e10_experiment,
    R17B_DISABLED_KINDS,
)


# The 35-task fused probe set (from R17b probe)
FUSED_PROBE_TASKS = [
    "03560426", "05a7bcf2", "0e671a1a", "0f63c0b9", "178fcbfb",
    "212895b5", "21f83797", "23581191", "29700607", "2b9ef948",
    "363442ee", "508bd3b6", "54d9e175", "58e15b12", "5e6bbc0b",
    "5ffb2104", "673ef223", "692cd3b6", "696d4842", "6ffe8f07",
    "7e2bad24", "87ab05b8", "94be5b80", "992798f6", "a2fd1cf0",
    "a64e4611", "af902bf9", "c62e2108", "cb227835", "d22278a0",
    "d4a91cb9", "db93a21d", "dc2e9a9d", "e7639916", "f3b10344",
]

# E10 target tasks (tasks that use the R17b modes)
E10_TASKS = ["178fcbfb", "23581191", "05a7bcf2"]

OUTPUT_DIR = ROOT / "outputs" / "generator_mining"
RESIDUAL_PATH = OUTPUT_DIR / "residuals.jsonl"
LEARNED_GEN_DIR = ROOT / "outputs" / "learned_generators"
LEARNED_GEN_PATH = LEARNED_GEN_DIR / "learned_generators.json"


def _load_task_pairs(task_id: str) -> list:
    """Load a task and return Grid pairs for the generative inducer."""
    task = load_task(task_id)
    pairs = []
    for tp in task.train:
        gi = Grid.from_list(tp.input)
        go = Grid.from_list(tp.output)
        pairs.append((gi, go))
    return pairs


def run_substrate(task_ids: list[str]) -> list:
    """Extract residual-paint substrate for all fused-signature tasks."""
    print("=" * 60)
    print("SUBSTRATE EXTRACTION")
    print("=" * 60)

    # Clear existing residuals for a fresh run
    if RESIDUAL_PATH.exists():
        RESIDUAL_PATH.unlink()

    all_residuals = []
    for i, task_id in enumerate(task_ids):
        print(f"\n[{i+1}/{len(task_ids)}] {task_id}...")
        try:
            pairs = _load_task_pairs(task_id)
            recs = extract_residuals_for_task(task_id, pairs)
            if recs:
                save_residuals(recs, RESIDUAL_PATH)
                all_residuals.extend(recs)
                print(f"  -> {len(recs)} residual records")
            else:
                print(f"  -> no residuals (train-perfect or no fusion)")
        except Exception as e:
            print(f"  ERROR: {e}")

    print(f"\nTotal residual records: {len(all_residuals)}")
    print(f"Tasks with residuals: "
          f"{len(set(r.task_id for r in all_residuals))}")
    return all_residuals


def run_mine(residuals: list = None) -> list:
    """Run mining on the residual substrate."""
    if residuals is None:
        print("Loading residuals from disk...")
        residuals = load_residuals(RESIDUAL_PATH)
        print(f"  Loaded {len(residuals)} records")

    if not residuals:
        print("No residuals to mine.")
        return []

    print("\n" + "=" * 60)
    print("CLUSTERING")
    print("=" * 60)
    clusters = cluster_residuals(residuals)
    for geo, recs in sorted(clusters.items(), key=lambda x: -len(x[1])):
        tasks = set(r.task_id for r in recs)
        print(f"  {geo}: {len(recs)} records from {len(tasks)} tasks")

    print("\n" + "=" * 60)
    print("MINING GENERATORS")
    print("=" * 60)
    mined = mine_generators(residuals, max_hypotheses=5000)
    print(f"  Hypotheses with support: {len(mined)}")

    for hyp, supporting in mined[:20]:
        tasks = set(r.task_id for r in supporting)
        print(f"    {hyp.signature()}: "
              f"{len(supporting)} instances, {len(tasks)} tasks")

    return mined


def run_admit(mined: list, task_ids: list[str]) -> list:
    """Run M3b admission on mined generators."""
    if not mined:
        print("No mined generators to admit.")
        return []

    print("\n" + "=" * 60)
    print("M3b ADMISSION")
    print("=" * 60)

    # Load all task pairs for LOO
    task_pairs = {}
    for task_id in task_ids:
        try:
            task_pairs[task_id] = _load_task_pairs(task_id)
        except Exception:
            pass

    admitted: list[AdmittedGenerator] = []
    for hyp, supporting in mined:
        gen = admit_generator_m3b(hyp, supporting, task_pairs, k_delta=2)
        if gen is not None:
            admitted.append(gen)
            print(f"  ADMITTED: {hyp.signature()} "
                  f"(tasks: {gen.supporting_tasks})")

    print(f"\nTotal admitted: {len(admitted)}")

    if admitted:
        save_admitted_generators(admitted, LEARNED_GEN_PATH)
        print(f"Saved to {LEARNED_GEN_PATH}")

    return admitted


def run_e10(task_ids: list[str] = None) -> dict:
    """Run the E10 rediscovery experiment."""
    if task_ids is None:
        task_ids = E10_TASKS

    task_pairs = {}
    for task_id in task_ids:
        try:
            task_pairs[task_id] = _load_task_pairs(task_id)
        except Exception as e:
            print(f"  Could not load {task_id}: {e}")

    e10_dir = OUTPUT_DIR / "e10"
    return run_e10_experiment(task_pairs, task_ids, e10_dir)


def main():
    parser = argparse.ArgumentParser(
        description="Round-18 generator mining")
    parser.add_argument("--mode", default="full",
                        choices=["full", "substrate", "mine", "admit",
                                 "e10"],
                        help="Which phase to run")
    parser.add_argument("--tasks", nargs="*", default=None,
                        help="Specific task IDs (default: fused probe)")
    args = parser.parse_args()

    task_ids = args.tasks or FUSED_PROBE_TASKS
    start = time.time()

    print(f"Mode: {args.mode}")
    print(f"Tasks: {len(task_ids)}")
    print(f"Output: {OUTPUT_DIR}")
    print()

    if args.mode == "substrate":
        run_substrate(task_ids)

    elif args.mode == "mine":
        run_mine()

    elif args.mode == "admit":
        residuals = load_residuals(RESIDUAL_PATH)
        mined = mine_generators(residuals)
        run_admit(mined, task_ids)

    elif args.mode == "e10":
        run_e10()

    elif args.mode == "full":
        residuals = run_substrate(task_ids)
        mined = run_mine(residuals)
        admitted = run_admit(mined, task_ids)

        print("\n" + "=" * 60)
        print("E10 REDISCOVERY EXPERIMENT")
        print("=" * 60)
        verdict = run_e10()

        # Summary
        elapsed = time.time() - start
        print("\n" + "=" * 60)
        print("ROUND 18 SUMMARY")
        print("=" * 60)
        print(f"  Substrate: {len(residuals)} residual records")
        clusters = cluster_residuals(residuals)
        print(f"  Clusters: {len(clusters)}")
        print(f"  Mined with support: {len(mined)}")
        print(f"  Admitted generators: {len(admitted)}")
        print(f"  E10 cross_line: "
              f"{verdict.get('rediscovered_cross_line', False)}")
        print(f"  E10 ray_through: "
              f"{verdict.get('rediscovered_ray_through_absorbed', False)}")
        print(f"  E10 23581191 re-cert: "
              f"{verdict.get('recertified_23581191', False)}")
        print(f"  Elapsed: {elapsed:.1f}s")

        # Save summary
        summary = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "n_residuals": len(residuals),
            "n_clusters": len(clusters),
            "cluster_sizes": {k: len(v) for k, v in clusters.items()},
            "n_mined_with_support": len(mined),
            "n_admitted": len(admitted),
            "admitted_signatures": [g.hypothesis.signature()
                                    for g in admitted],
            "e10_verdict": verdict,
            "elapsed_s": elapsed,
        }
        summary_path = OUTPUT_DIR / "r18_summary.json"
        summary_path.write_text(json.dumps(summary, indent=2))
        print(f"\nSummary saved to {summary_path}")


if __name__ == "__main__":
    main()
