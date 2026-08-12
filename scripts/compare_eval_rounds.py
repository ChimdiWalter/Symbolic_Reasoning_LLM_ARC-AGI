#!/usr/bin/env python3
"""Compare two eval-summary JSONs task-by-task (regression check between rounds).

Usage: python scripts/compare_eval_rounds.py OLD_SUMMARY NEW_SUMMARY
Prints headline deltas, per-task gains/losses, and exits 1 if any task that was
train_exact (or test_correct) in OLD lost that status in NEW.
"""
import json
import sys


def load(path: str) -> dict:
    j = json.load(open(path))
    return {t["task_id"]: t for t in j["per_task"]}, j


def flag(t: dict, key: str) -> bool:
    return bool(t.get(key))


def main() -> int:
    old_path, new_path = sys.argv[1], sys.argv[2]
    old, old_j = load(old_path)
    new, new_j = load(new_path)
    for label, j in (("OLD", old_j), ("NEW", new_j)):
        print(f"{label} {j['tag']}: train_exact={j['train_exact']} "
              f"test_correct={j['test_correct']} induced_fraction={j['induced_fraction']} "
              f"crashes={j['crashes']}")
    regressed = False
    for key in ("train_exact", "test_correct"):
        gains = [tid for tid in new if flag(new[tid], key) and not flag(old.get(tid, {}), key)]
        losses = [tid for tid in old if flag(old[tid], key) and tid in new and not flag(new[tid], key)]
        print(f"{key}: +{len(gains)} {sorted(gains)}  -{len(losses)} {sorted(losses)}")
        if losses:
            regressed = True
    stage_moves = []
    for tid in sorted(old):
        if tid in new and old[tid].get("failure_stage") != new[tid].get("failure_stage"):
            stage_moves.append(f"{tid}: {old[tid].get('failure_stage')} -> {new[tid].get('failure_stage')}")
    if stage_moves:
        print("failure-stage moves:")
        for m in stage_moves:
            print(" ", m)
    return 1 if regressed else 0


if __name__ == "__main__":
    sys.exit(main())
