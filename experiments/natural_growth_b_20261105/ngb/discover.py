"""Stage 1 (source halves only): discovery with extra budget. For every source task, the base search (150,000
executions, 20 CPU-s) and, when it finds no fit, the search at 4x (600,000 executions, 80 CPU-s); the first fitting
program's tree is kept. These are the first two steps of the phase 1 controller, re-run here so that the trees and
the discovery CPU are this study's own records (phase 1 kept only the program text).

    python -I run.py discover OUT_JSONL [BENCH ...] [--shard I/K]

One JSON line per task, appended as soon as it is done (resumable). Refuses anything but the source half.
"""
import json
import os
import sys
import time

from ngb import env as E
from ngb import ops as OP
from ngrow import data as DT                                                    # noqa: E402
from cgrow import search as S                                                   # noqa: E402

PROBE_FACTOR = 4


def jtree(t):
    return [t[0]] + [jtree(c) for c in t[1:]] if len(t) > 1 else [t[0]]


def tree(j):
    return (j[0],) + tuple(tree(c) for c in j[1:])


def read_jsonl(path):
    out = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for x in f:
                if x.strip():
                    r = json.loads(x)
                    out[r["task"]] = r
    return out


def run(out_path, benches, shard=None):
    done = set(read_jsonl(out_path))
    g0b = OP.G0Builder()
    rows = DT.half("source", benches)
    if shard:
        i, k = (int(x) for x in shard.split("/"))
        rows = [r for n, r in enumerate(rows) if n % k == i]
    cache = {}
    for b, fam, tid in rows:
        if tid in done:
            continue
        if b not in cache:
            cache = {b: DT.tasks(b)}
        t = cache[b][tid]
        t0 = time.process_time()
        base = S.run(g0b(), t["train"], t["test_inputs"])
        row = {"bench": b, "family": fam, "task": tid, "g0_sha256": g0b.sha, "n_demos": len(t["train"]),
               "base": {k: base[k] for k in ("fit", "program", "stop", "calls", "level_complete", "cpu_s")},
               "x4": None, "found_at": "base" if base["fit"] else None,
               "tree": jtree(base["program_tree"]) if base["fit"] else None,
               "preds": base["preds"] if base["fit"] else None}
        if not base["fit"]:
            deep = S.run(g0b(), t["train"], t["test_inputs"], budget=S.BASE_BUDGET * PROBE_FACTOR,
                         cpu_cap=S.BASE_CPU * PROBE_FACTOR)
            row["x4"] = {k: deep[k] for k in ("fit", "program", "stop", "calls", "level_complete", "cpu_s")}
            if deep["fit"]:
                row.update(found_at="x4", tree=jtree(deep["program_tree"]), preds=deep["preds"])
        row["cpu_s"] = round(time.process_time() - t0, 3)
        with E.open_write(out_path, "a") as f:
            f.write(json.dumps(row, default=list) + "\n")
        print(json.dumps({"task": tid, "found_at": row["found_at"], "program": (row["base"]["program"] if
                          row["found_at"] == "base" else (row["x4"] or {}).get("program")), "cpu_s": row["cpu_s"]}),
              flush=True)


def main(out_path, *rest):
    benches, shard = [], None
    it = iter(rest)
    for a in it:
        if a == "--shard":
            shard = next(it)
        else:
            benches.append(a)
    run(os.path.abspath(out_path), tuple(benches) or DT.BENCHMARKS, shard)


if __name__ == "__main__":
    main(*sys.argv[1:])
