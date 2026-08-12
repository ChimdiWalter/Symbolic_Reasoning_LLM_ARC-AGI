#!/usr/bin/env python3
"""Post-hoc library promotion over a finished harness run's object artifacts.

Reconstructs an ObjectEngine from a harness output dir (accepted programs in
object/programs/*.json, near-solve rows in object/near_solve_parts/*.jsonl),
fills the train-pair cache from the ARC TRAINING inputs only (no test grids
ever enter the engine), then runs engine.promote_and_validate(): fragment
mining (>= 3 distinct accepted programs), Section-5.4 validation, and failure-
cluster invention — all through the normal induction path.

Usage:
  python scripts/run_library_promotion.py --harness-dir outputs/unified_harness_v2 \
      --out-dir outputs/object_reasoning_promotion_v2
"""
import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--harness-dir", default="outputs/unified_harness_v2")
    ap.add_argument("--out-dir", default="outputs/object_reasoning_promotion_v2")
    args = ap.parse_args()

    from geocat_arc.object_reasoning.engine import ObjectReasoningEngine

    harness = Path(args.harness_dir) / "object"
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Merge per-task near-solve parts into the engine's store file.
    store_path = out_dir / "near_solves.jsonl"
    parts = sorted((harness / "near_solve_parts").glob("*.jsonl"))
    with open(store_path, "w") as out:
        for p in parts:
            out.write(p.read_text())
    print(f"merged {len(parts)} near-solve part files -> {store_path}")

    engine = ObjectReasoningEngine(out_dir)

    programs = sorted((harness / "programs").glob("*.json"))
    for p in programs:
        engine.accepted[p.stem] = json.loads(p.read_text())
    print(f"loaded {len(programs)} accepted programs")

    with open(Path("data/arc/arc-agi_training_challenges.json")) as f:
        challenges = json.load(f)
    cached = 0
    for tid in set(engine.accepted) | {r.task_id
                                       for r in engine.near_solve_store.load_all()}:
        task = challenges.get(tid)
        if task is None:
            continue
        engine._train_cache[tid] = [
            (np.array(pair["input"], dtype=np.int32),
             np.array(pair["output"], dtype=np.int32))
            for pair in task["train"]]
        cached += 1
    print(f"cached train pairs for {cached} tasks (train split only, no test grids)")

    registered = engine.promote_and_validate()
    print(f"promote_and_validate registered: {registered}")
    print(f"library file: {out_dir / 'library.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
