#!/usr/bin/env python3
"""Kaggle ARC Prize submission adapter.

Usage: make_submission.py HARNESS_DIR CHALLENGES_JSON OUT_JSON

Policy (measured, RUN_HISTORY 2026-07-11):
  attempt_1 — the CERTIFIED program's render (harness object programs are
              LOO-certified; pipeline/geocat solves use their stored
              apply description via the harness solution store when
              available; fallback below otherwise).
  attempt_2 — the best stored near-solve PARTIAL program's render (the
              gate's best uncertified hypothesis; +18/1000 measured on
              training, all from loo-stage rows).
  fallback  — the test input unchanged (every task id MUST be present with
              both attempts; Kaggle requires it).

Emits Kaggle's exact schema: {task_id: [{"attempt_1": grid, "attempt_2":
grid}, ...]} with one entry per test input, in order.
"""
import glob
import json
import os
import sys

sys.path.insert(0, ".")
from geocat_arc.perception.grid import Grid
from geocat_arc.object_reasoning.types import ObjectProgram
from geocat_arc.object_reasoning.actions import render_program

harness_dir, challenges_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
challenges = json.load(open(challenges_path))

certified = {}
for f in glob.glob(f"{harness_dir}/object/programs/*.json"):
    tid = os.path.basename(f)[:-5]
    try:
        certified[tid] = ObjectProgram.from_dict(json.load(open(f)))
    except Exception:
        pass

partials = {}
for f in glob.glob(f"{harness_dir}/object/near_solve_parts/*.jsonl"):
    tid = os.path.basename(f)[:-6]
    try:
        r = json.loads(open(f).readline())
        pp = r.get("program_partial")
        if isinstance(pp, dict) and pp.get("rules"):
            partials[tid] = ObjectProgram.from_dict(pp)
    except Exception:
        pass


def render_or_none(prog, grid_rows):
    try:
        return render_program(prog, Grid.from_list(grid_rows)).to_list()
    except Exception:
        return None


submission = {}
n_cert = n_part = n_fallback = 0
for tid, task in challenges.items():
    entries = []
    for case in task["test"]:
        tin = case["input"]
        a1 = render_or_none(certified[tid], tin) if tid in certified else None
        a2 = render_or_none(partials[tid], tin) if tid in partials else None
        if a1 is None and a2 is not None:
            a1 = a2          # promote the partial when nothing certified
        if a1 is None:
            a1 = tin
            n_fallback += 1
        elif tid in certified:
            n_cert += 1
        if a2 is None:
            a2 = a1
        else:
            n_part += 1
        entries.append({"attempt_1": a1, "attempt_2": a2})
    submission[tid] = entries

json.dump(submission, open(out_path, "w"))
missing = set(challenges) - set(submission)
assert not missing, f"missing task ids: {sorted(missing)[:5]}"
print(f"submission -> {out_path}: {len(submission)} tasks "
      f"({n_cert} certified attempts, {n_part} partial attempts, "
      f"{n_fallback} fallback)")
