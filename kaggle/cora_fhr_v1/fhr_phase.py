"""CORA-FHR-v1: the failure-driven construction phase, run after the unchanged native harness.

  python fhr_phase.py --challenges C.json --progress progress.jsonl --out fhr_rows.jsonl \
      --start-deadline UNIX --hard-deadline UNIX [--workers 4]

Reads only training demonstrations and unlabelled test inputs. It never opens a solutions file.

For every task:
1. Applicability: every training pair keeps its grid size, and every changed cell was background in the
   input. This is additive growth, the only change G-grow can express.
2. If the harness's native object layer already certified the task, construction would not commit (the
   FHR commit rule), so the task is skipped.
3. The rest run `cora_fhr.measure.job` with arms ("E",), the exact code path of the development runs:
   - frozen native object layer (A);
   - native's own memorized-growth record (`pattern` fallbacks) as failure evidence;
   - G-grow construction;
   - reversible, identity-checked installation into the unchanged engine;
   - native gate and routing check;
   - tie abstention;
   - adaptive leave-one-out that rebuilds evidence, operator and extension in every fold;
   - commit only where A has no certificate.

Tasks start in a fixed order (smallest training grids first) until --start-deadline. The pool is
terminated at --hard-deadline. A task that is not reached keeps its native answers; the notebook records
it as "not_reached".
"""
import argparse
import json
import multiprocessing as mp
import os
import sys
import time

import numpy as np

CODE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, CODE)


def growth_shaped(task):
    added = 0
    for p in task["train"]:
        a, b = np.asarray(p["input"]), np.asarray(p["output"])
        if a.shape != b.shape:
            return False
        vals, cnt = np.unique(a, return_counts=True)
        bg = vals[int(np.argmax(cnt))]
        ch = a != b
        if (a[ch] != bg).any():
            return False
        added += int(ch.sum())
    return added > 0


def object_certified(progress):
    rows = {}
    if os.path.exists(progress):
        for line in open(progress):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            rows[r.get("task_id")] = bool((r.get("object") or {}).get("solved"))
    return rows


def _job(args):
    from cora_fhr import measure as M                                   # imports the sealed flags and CPU clock
    tid = args[0]
    try:
        return M.job(args)
    except BaseException as e:                                          # noqa: BLE001  a crash keeps native answers
        return {"key": tid, "arms": {}, "error": repr(e)[:400]}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--challenges", required=True)
    ap.add_argument("--progress", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--start-deadline", type=float, required=True)
    ap.add_argument("--hard-deadline", type=float, required=True)
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 4)
    ap.add_argument("--f_b", type=float, default=1.33)
    a = ap.parse_args(argv)
    challenges = json.load(open(a.challenges))
    for tid, t in challenges.items():                                   # leakage guard: inputs only
        assert all(set(x) == {"input"} for x in t["test"]), tid
    certified = object_certified(a.progress)
    eligible, skipped = [], {}
    for tid, t in challenges.items():
        if not growth_shaped(t):
            skipped[tid] = "not_growth_shaped"
        elif certified.get(tid):
            skipped[tid] = "native_object_certified"
        else:
            eligible.append(tid)
    eligible.sort(key=lambda k: (sum(np.asarray(p["input"]).size for p in challenges[k]["train"]), k))
    print(f"FHR: {len(challenges)} tasks, {len(eligible)} eligible, skipped {len(skipped)}", flush=True)
    done, started = set(), {}
    with open(a.out, "w") as fh:
        for tid, why in sorted(skipped.items()):
            fh.write(json.dumps({"key": tid, "fhr": "skipped", "reason": why}) + "\n")
        pool = mp.get_context("fork").Pool(a.workers, maxtasksperchild=1)
        queue = list(eligible)
        try:
            while queue or started:
                while queue and len(started) < a.workers and time.time() < a.start_deadline:
                    tid = queue.pop(0)
                    view = {"train": challenges[tid]["train"], "test": challenges[tid]["test"]}
                    started[tid] = pool.apply_async(_job, ((tid, view, ("E",), None, None, a.f_b),))
                if not queue or time.time() >= a.start_deadline:
                    queue_left = list(queue)
                    queue.clear()
                    for tid in queue_left:
                        fh.write(json.dumps({"key": tid, "fhr": "not_reached", "reason": "start_deadline"}) + "\n")
                for tid, res in list(started.items()):
                    if res.ready():
                        row = res.get()
                        row["fhr"] = "ran"
                        fh.write(json.dumps(row) + "\n")
                        fh.flush()
                        done.add(tid)
                        del started[tid]
                        e = row.get("arms", {}).get("E", {})
                        print(f"[{len(done)}/{len(eligible)}] {tid} E={e.get('outcome')} cpu={row.get('cpu_s')}s", flush=True)
                if time.time() >= a.hard_deadline:
                    for tid in started:
                        fh.write(json.dumps({"key": tid, "fhr": "not_reached", "reason": "hard_deadline"}) + "\n")
                    started.clear()
                    pool.terminate()
                    break
                time.sleep(2)
        finally:
            pool.terminate()
            pool.join()
    print(f"FHR phase done: {len(done)} ran", flush=True)


if __name__ == "__main__":
    main()
