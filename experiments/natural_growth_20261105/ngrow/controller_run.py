"""Stage A: the growth controller (cgrow/controller.py, unchanged) on tasks of one half, under G0.

    python -I run.py controller_run OUT_JSONL HALF [BENCH ...] [--limit N] [--shard I/K]

Per task (system side: demonstrations and test inputs only): base search (150,000 executions, 20 CPU-s), and when
it finds no fit: the deeper-search probe (4x the budget and the cap), the shape relation, the closest program and
the typed holes (the unreachable sketches identity ?(I), outer B(?(I)) and inner ?(A(I)) with B, A invertible G0
grid operations; identity plus the two best kept). Decision: CONTINUE_PROGRAM_SEARCH (the probe fits),
INVENT_NEW_OPERATION (no fit, at least two demonstrations), REQUEST_ADDITIONAL_ADMISSIBLE_EVIDENCE (fewer than two).
One JSON line per task, appended as soon as the task is done (resumable: finished tasks are skipped). Refuses the
held half unless the phase 2 gate passes.
"""
import json
import os
import sys
import time

from ngrow import env as E, data as DT, plugin as PL, gate as GT
from cgrow import controller as CT                                              # noqa: E402


def jsonable(rec):
    out = dict(rec)
    out.pop("hypotheses", None)
    cl = out.get("closest")
    if cl:
        cl = dict(cl)
        from a2 import arcdsl as D
        cl["program"] = D.show(cl.pop("program_tree"))
        out["closest"] = cl
    return out


def run(out_path, half, benches, limit=None, shard=None):
    if half != "source":
        GT.require_phase2()
    done = set()
    if os.path.exists(out_path):
        with open(out_path, encoding="utf-8") as f:
            done = {json.loads(x)["task"] for x in f if x.strip()}
    g0b = PL.G0Builder()
    rows = DT.half(half, benches)
    if shard:
        i, k = (int(x) for x in shard.split("/"))
        rows = [r for n, r in enumerate(rows) if n % k == i]
    if limit:
        rows = rows[:limit]
    cache = {}
    for b, fam, tid in rows:
        if tid in done:
            continue
        if b not in cache:
            cache = {b: DT.tasks(b)}
        task = cache[b][tid]
        t0, w0 = time.process_time(), time.time()
        rec = CT.analyze(task, g0b())
        row = {"bench": b, "family": fam, "task": tid, "g0_sha256": g0b.sha, "cpu_scale": PL.CPU_SCALE,
               "cpu_s": round(time.process_time() - t0, 3), "wall_s": round(time.time() - w0, 3),
               "n_demos": len(task["train"]), "n_test": len(task["test_inputs"]),
               "max_side": max(max(len(g), len(g[0])) for p in task["train"] for g in p),
               "record": jsonable(rec)}
        with E.open_write(out_path, "a") as f:
            f.write(json.dumps(row, default=list) + "\n")
        print(json.dumps({"task": tid, "bench": b, "status": rec["status"], "decision": rec["decision"],
                          "cpu_s": row["cpu_s"], "wall_s": row["wall_s"]}), flush=True)


def main(out_path, half, *rest):
    benches, limit, shard = [], None, None
    it = iter(rest)
    for a in it:
        if a == "--limit":
            limit = int(next(it))
        elif a == "--shard":
            shard = next(it)
        else:
            benches.append(a)
    run(os.path.abspath(out_path), half, tuple(benches) or DT.BENCHMARKS, limit, shard)


if __name__ == "__main__":
    main(*sys.argv[1:])
