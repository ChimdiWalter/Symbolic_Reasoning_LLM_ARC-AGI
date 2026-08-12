#!/usr/bin/env python3
"""Automated post-run flake repair + delta (the documented remedy, scripted).

Usage: repair_and_delta.py NEW_DIR BASE_DIR
1. Diff NEW_DIR/results.json vs BASE_DIR's solved set.
2. Every LOST task gets the documented remedy: its rows are stripped from
   progress.jsonl / near_solves.jsonl (with .bak) and the harness re-runs
   resumably at --workers 2 (solo, no contention).
3. Re-diff; tasks still lost after the solo retry are flagged REAL
   REGRESSION (exit 1).  Prints the final delta; exit 0 = clean.
"""
import json
import subprocess
import sys

new_dir, base_dir = sys.argv[1], sys.argv[2]


def solved(p):
    s = json.load(open(p))["solved"]
    return {t["task_id"] for t in s} if s and isinstance(s[0], dict) else set(s)


base = solved(f"{base_dir}/results.json")
new = solved(f"{new_dir}/results.json")
lost = sorted(base - new)
gained = sorted(new - base)
print(f"in-run: {len(new)} | lost {lost} | gained {gained}", flush=True)

if lost:
    for fn in ("progress.jsonl", "near_solves.jsonl"):
        path = f"{new_dir}/{fn}"
        lines = open(path).readlines()
        open(path + ".bak", "w").writelines(lines)
        keep = [l for l in lines
                if json.loads(l).get("task_id") not in set(lost)]
        open(path, "w").writelines(keep)
    run_id = json.load(open(f"{new_dir}/results.json"))["config"]["run_id"]
    rc = subprocess.call(
        [sys.executable, "scripts/run_unified_harness.py", "--workers", "2",
         "--out-dir", new_dir, "--run-id", run_id])
    print(f"solo rerun rc={rc}", flush=True)

new2 = solved(f"{new_dir}/results.json")
still_lost = sorted(base - new2)
print(f"FINAL: {len(new2)} | still lost: {still_lost} | "
      f"gained: {sorted(new2 - base)}")
if still_lost:
    print("REAL REGRESSION — investigate before accepting this run")
    sys.exit(1)
