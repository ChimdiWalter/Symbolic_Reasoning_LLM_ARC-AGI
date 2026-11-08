"""CPU speed benchmark for the two CPU-time stops that depend on the machine (S-enum's 60 charged reference CPU-s
per unit and matched static search's 150 reference CPU-s per task; PROTOCOL.md section 10).

    python -m cas.bench OUT.json [lone|concurrent|both]        default both
    python -m cas.bench _one N                                 (internal: one process, N repeats, JSON on stdout)

The fixed search: A2's bottom-up search over S1's G0 (A2 grammar minus compress, downscale, trim and upscale) on
the 12 probe pairs of S1's novelty gate for the schema structure MAP:spread:spread:0 at k = 2 (S1's upscale
structure; S1's gate finds no G0 program for it), 200,000 executions, no CPU cap that binds. The execution count is
fixed, so its CPU time measures the machine.
- lone: 5 repeats in this process; the median is the machine's lone value.
- concurrent: 4 copies of the search run at the same time (the busiest stage of the kernel runs four processes),
  3 repeats each; the median of the 4 per-process medians is the machine's concurrent value. Hardware threads share
  cores, so a process gets fewer executions per CPU-second than when alone (finding 5 of the independent review).
The reference is Athe's lone value measured in phase 1 (config "bench_reference_cpu_s"). The factor applied to
both stops is r = concurrent value / reference, clipped to [1, 3] (the clip is one-sided on purpose: a machine
faster than Athe gives the search methods no more than their reference budgets; one more than three times slower,
under concurrency, gives them less, and the record shows it: every matched search records its executions per
CPU-second beside the benchmark's).
"""
import json
import os
import statistics
import subprocess
import sys
import time

from cas import env as E
from cgrow import lang0 as L0, search as S, episode as EP, schema as SG        # noqa: E402
from a2 import arcdsl as D                                                      # noqa: E402

LONE_REPEATS = 5
CONCURRENT_COPIES = 4
CONCURRENT_REPEATS = 3
CLIP = (1.0, 3.0)


def run(repeats):
    st = SG.by_sid()["MAP:spread:spread:0"]
    pairs = [(x, st(x, 2)) for x in EP.SIG_PROBES[:12]]
    pairs = [(x, y) for x, y in pairs if y is not None and D.valid(y)]
    g = L0.build_g0(("compress", "downscale", "trim", "upscale"))
    rows = []
    for _ in range(repeats):
        t0 = time.process_time()
        r = S.run(g, pairs[:-1], [pairs[-1][0]], budget=200_000, cpu_cap=600.0, want=1)
        rows.append({"cpu_s": round(time.process_time() - t0, 3), "calls": r["calls"], "fit": r["fit"],
                     "level": r["level_complete"]})
    return {"median_cpu_s": statistics.median(x["cpu_s"] for x in rows), "runs": rows}


def concurrent():
    procs = [subprocess.Popen([sys.executable, "-m", "cas.bench", "_one", str(CONCURRENT_REPEATS)], cwd=E.STUDY,
                              env=dict(os.environ), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
             for _ in range(CONCURRENT_COPIES)]
    outs = [json.loads(p.communicate()[0].strip().splitlines()[-1]) for p in procs]
    return {"copies": CONCURRENT_COPIES, "median_cpu_s": statistics.median(o["median_cpu_s"] for o in outs),
            "per_process": outs}


def scale(reference_cpu_s, measured):
    """The factor for the two stops: the concurrent median (lone when no concurrent run exists) over the reference."""
    m = measured.get("concurrent", measured.get("lone", measured))["median_cpu_s"]
    return round(min(CLIP[1], max(CLIP[0], m / reference_cpu_s)), 3)


if __name__ == "__main__":
    if sys.argv[1] == "_one":
        print(json.dumps(run(int(sys.argv[2]))))
    else:
        mode = sys.argv[2] if len(sys.argv) > 2 else "both"
        out = {"cpu_count": os.cpu_count()}
        if mode in ("lone", "both"):
            out["lone"] = run(LONE_REPEATS)
        if mode in ("concurrent", "both"):
            out["concurrent"] = concurrent()
        E.dump(sys.argv[1], out)
        print(json.dumps({k: (v["median_cpu_s"] if isinstance(v, dict) else v) for k, v in out.items()}))
