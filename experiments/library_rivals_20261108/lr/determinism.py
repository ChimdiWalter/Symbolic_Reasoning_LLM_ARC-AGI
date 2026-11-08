"""Determinism check: two dry runs in separate interpreters (python -I: different hash seeds) must give identical
rows (fit, program, executions, level, stop, predictions).

    python3 -I run.py determinism checks/dry_run checks/dry_run_repeat     writes checks/DETERMINISM.json
"""
import glob
import json
import os

from lr import env as E

KEYS = ("fit", "program", "calls", "level_complete", "stop", "preds")


def main(a_dir, b_dir):
    n = d = fits = 0
    diffs = []
    for p in sorted(glob.glob(os.path.join(a_dir, "rows", "*", "*.jsonl"))):
        q = os.path.join(b_dir, os.path.relpath(p, a_dir))
        ra = {json.loads(x)["task"]: json.loads(x) for x in open(p, encoding="utf-8") if x.strip()}
        rb = {json.loads(x)["task"]: json.loads(x) for x in open(q, encoding="utf-8") if x.strip()}
        for t, r in ra.items():
            n += 1
            fits += bool(r["fit"])
            if t not in rb or any(r[k] != rb[t][k] for k in KEYS):
                d += 1
                diffs.append(os.path.relpath(p, a_dir) + ":" + t)
    out = {"runs": [os.path.relpath(a_dir, E.STUDY), os.path.relpath(b_dir, E.STUDY)], "rows_compared": n,
           "rows_with_a_fit": fits, "rows_differing": d, "differing": diffs[:20], "keys": list(KEYS)}
    E.dump(os.path.join(E.STUDY, "checks", "DETERMINISM.json"), out)
    print(json.dumps(out))
