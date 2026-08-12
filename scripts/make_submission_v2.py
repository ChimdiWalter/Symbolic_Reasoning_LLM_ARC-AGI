#!/usr/bin/env python3
"""Kaggle submission builder v2 — from emit-predictions progress rows.

Usage: make_submission_v2.py PROGRESS_JSONL CHALLENGES_JSON OUT_JSON

attempt_1 = solving layer's persisted render (any layer);
attempt_2 = best uncertified object partial render (E2-measured 0.91
            precision for feature/relational; emitted regardless of class —
            best-of-2 scoring makes extra attempts free);
fallback  = the test input unchanged (every task id must be present).
"""
import json
import sys

progress_path, challenges_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
challenges = json.load(open(challenges_path))
preds = {}
for line in open(progress_path):
    d = json.loads(line)
    if d.get("predictions"):
        preds[d["task_id"]] = d["predictions"]

sub = {}
n1 = n2 = nf = 0
for tid, task in challenges.items():
    p = preds.get(tid) or {}
    a1s = p.get("attempt_1")
    a2s = p.get("attempt_2")
    entries = []
    for i, case in enumerate(task["test"]):
        a1 = a1s[i] if a1s and i < len(a1s) and a1s[i] else None
        a2 = a2s[i] if a2s and i < len(a2s) and a2s[i] else None
        if a1 is None and a2 is not None:
            a1 = a2
        if a1 is None:
            a1 = case["input"]
            nf += 1
        else:
            n1 += 1
        if a2 is None:
            a2 = a1
        else:
            n2 += 1
        entries.append({"attempt_1": a1, "attempt_2": a2})
    sub[tid] = entries
json.dump(sub, open(out_path, "w"))
assert set(sub) == set(challenges)
print(f"submission -> {out_path}: {len(sub)} tasks | attempt_1 real {n1}, "
      f"attempt_2 real {n2}, fallback {nf}")
