"""A code-only, offline ARC-AGI-2 inference scaffold for ncv2-g3 (Phase 7). DESIGN AND ENGINEERING ONLY: nothing here
submits anything. Design notes: docs/NEURAL_CORA_G3_COMPETITION_SCAFFOLD.md.

    python kaggle/cora_g3_scaffold/scaffold.py CHALLENGES.json OUT_DIR [--deadline-h 11.0] [--task-cpu-s 120]

Guarantees:
- offline: ncv2-g3 is symbolic, so no model or network is needed;
- every task id and every test input gets exactly `attempt_1` and `attempt_2`, each a valid grid (1-30 x 1-30, ints
  0-9). The submission is pre-filled with a safe fallback (the test input), then overwritten task by task and written
  atomically after each task, so a crash or a timeout never leaves a malformed or missing file;
- budgets: a per-task CPU cap (the search's own `cpu_cap_s`) inside a global wall-clock deadline that shrinks the cap
  when time runs short and stops starting tasks near the end;
- provenance: the code tree hash, the Python and numpy versions, and for every output its origin (an ncv2-g3 program
  in S-expression form, or `fallback`). Execution traces stay in `provenance.json`, never in the submission;
- no third-party solver code. A future NVARC-checkpoint-assisted arm would add the checkpoint's licence and
  attribution to `provenance.json` (kaggle/NVARC_NOTICE.md) and must not ship upstream code.
"""
import hashlib
import json
import os
import platform
import sys
import time
import traceback

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if HERE not in sys.path:
    sys.path.insert(0, HERE)


def grid_ok(g):
    return (isinstance(g, list) and 1 <= len(g) <= 30 and all(isinstance(r, list) and 1 <= len(r) <= 30 for r in g)
            and len({len(r) for r in g}) == 1 and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9
                                                      for r in g for v in r))


def validate(sub, challenges):
    """[(task id, test index, problem)]; empty when the submission is well formed for these challenges."""
    bad = []
    for tid, task in challenges.items():
        entries = sub.get(tid)
        if not isinstance(entries, list) or len(entries) != len(task["test"]):
            bad.append((tid, None, "missing task or wrong number of test entries"))
            continue
        for i, e in enumerate(entries):
            if not isinstance(e, dict) or set(e) != {"attempt_1", "attempt_2"}:
                bad.append((tid, i, "entry must have exactly attempt_1 and attempt_2"))
            elif not (grid_ok(e["attempt_1"]) and grid_ok(e["attempt_2"])):
                bad.append((tid, i, "invalid grid"))
    return bad


def fallback(challenges):
    return {tid: [{"attempt_1": t["input"], "attempt_2": t["input"]} for t in task["test"]] for tid, task in challenges.items()}


def tree_sha(root, pats=("cora_neural_v2", "cora_neural_v2g2", "cora_neural_v2g3")):
    h = hashlib.sha256()
    for p in pats:
        for dp, _, fs in sorted(os.walk(os.path.join(root, p))):
            for f in sorted(fs):
                if f.endswith(".py"):
                    h.update(f.encode())
                    h.update(open(os.path.join(dp, f), "rb").read())
    return h.hexdigest()


def atomic_dump(obj, path):
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(obj, fh)
    os.replace(tmp, path)


def solve_task(task, budget, cpu_cap_s):
    """Two attempts per test input from ncv2-g3, with the program behind each (demonstrations and inputs only)."""
    from cora_neural_v2g3 import search as S3
    t = {"train": [(p["input"], p["output"]) for p in task["train"]], "test_inputs": [x["input"] for x in task["test"]]}
    r = S3.search(t, budget, cpu_cap_s=cpu_cap_s)
    out = []
    for i, x in enumerate(task["test"]):
        grids = r["attempts_by_test"][i] if i < len(r["attempts_by_test"]) else []
        att = [(g, p) for g, p in zip(grids, r["attempt_programs"]) if grid_ok(g)]
        att = (att + [(x["input"], "fallback")] * 2)[:2] if att else [(x["input"], "fallback")] * 2
        if len(att) == 2 and att[1][1] == "fallback" and att[0][1] != "fallback":
            att[1] = att[0]                                    # one program only: repeat it rather than the input
        out.append(({"attempt_1": att[0][0], "attempt_2": att[1][0]}, [att[0][1], att[1][1]]))
    trace = {k: r[k] for k in ("n_candidates", "n_consistent", "first_fit_at", "origins", "cpu_s", "state")}
    return out, trace


def run(challenges_path, out_dir, deadline_h=11.0, task_cpu_s=120.0, budget=3000, solve=solve_task, clock=time.monotonic):
    t0 = clock()
    challenges = json.load(open(challenges_path))
    os.makedirs(out_dir, exist_ok=True)
    sub_path, prov_path = os.path.join(out_dir, "submission.json"), os.path.join(out_dir, "provenance.json")
    sub = fallback(challenges)
    atomic_dump(sub, sub_path)
    prov = {"solver": "ncv2-g3", "code_tree_sha256": tree_sha(HERE), "python": platform.python_version(),
            "numpy": np.__version__, "settings": {"deadline_h": deadline_h, "task_cpu_s": task_cpu_s, "budget": budget},
            "third_party_models": [], "tasks": {}}
    deadline = t0 + deadline_h * 3600
    ids = sorted(challenges)
    for k, tid in enumerate(ids):
        left = deadline - clock()
        if left < 60:                                          # never start a task in the last minute
            prov["tasks"][tid] = {"status": "skipped_deadline"}
            continue
        cap = min(task_cpu_s, max(5.0, left / max(1, len(ids) - k)))
        try:
            entries, trace = solve(challenges[tid], budget, cap)
            sub[tid] = [e for e, _ in entries]
            prov["tasks"][tid] = {"status": "ok", "origins": [o for _, o in entries], "trace": trace, "cpu_cap_s": round(cap, 1)}
        except Exception:                                      # noqa: BLE001 (the fallback stays in place)
            prov["tasks"][tid] = {"status": "error", "error": traceback.format_exc(limit=3)}
        bad = validate({tid: sub[tid]}, {tid: challenges[tid]})
        if bad:
            sub[tid] = fallback({tid: challenges[tid]})[tid]
            prov["tasks"][tid]["repaired"] = [b[2] for b in bad]
        atomic_dump(sub, sub_path)
    assert not validate(sub, challenges)
    prov["wall_s"] = round(clock() - t0, 1)
    atomic_dump(prov, prov_path)
    return sub, prov


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("challenges")
    ap.add_argument("out_dir")
    ap.add_argument("--deadline-h", type=float, default=11.0)
    ap.add_argument("--task-cpu-s", type=float, default=120.0)
    ap.add_argument("--budget", type=int, default=3000)
    a = ap.parse_args()
    run(a.challenges, a.out_dir, a.deadline_h, a.task_cpu_s, a.budget)
