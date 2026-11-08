"""CPU speed benchmark: the factor that makes a CPU-time cap mean the same work on Athe and on a Kaggle kernel.

    python -I run.py bench OUT_JSON

A fixed, budget-bound search with no fit: A2's bottom-up search over G0 on 11 pairs that map each of the novelty
gate's 12 probe grids to the probe grid five places later (no program relates them), 200,000 executions, a CPU cap
that never binds. The execution count is fixed, so its CPU time measures the machine; a run that fits or stops early
is flagged. Five repeats; the median is the machine's value. The reference value
was measured on Athe in phase 1 (config/STUDY_CONFIG.json "bench_reference_cpu_s"). A kernel's factor is
median / reference, clipped to [0.5, 2]; it multiplies blind enumeration's 60 charged CPU-s per unit (the one
CPU-defined stop that binds; the searches' CPU caps stay at their frozen values and stop nothing in practice, since
every search ends on its execution budget). The matched static allowance is measured on the machine that runs it, so
it needs no factor.
"""
import json
import statistics
import sys
import time

from ngrow import env as E, plugin as PL
from cgrow import search as S                                                   # noqa: E402

REPEATS = 5


def run():
    P = [tuple(tuple(r) for r in g) for g in PL.SIG_PROBES[:12]]
    pairs = [(P[i], P[(i + 5) % 12]) for i in range(12)]
    g = PL.G0Builder()()
    rows = []
    for _ in range(REPEATS):
        t0 = time.process_time()
        r = S.run(g, pairs[:-1], [pairs[-1][0]], budget=200_000, cpu_cap=600.0, want=1)
        rows.append({"cpu_s": round(time.process_time() - t0, 3), "calls": r["calls"], "fit": r["fit"],
                     "level": r["level_complete"], "stop": r["stop"]})
    ok = all(not x["fit"] and x["stop"] == "budget" for x in rows)
    return {"median_cpu_s": statistics.median(x["cpu_s"] for x in rows), "valid": ok, "runs": rows}


def scale(reference_cpu_s, measured):
    return round(min(2.0, max(0.5, measured["median_cpu_s"] / reference_cpu_s)), 3)


def main(out_path):
    out = run()
    E.dump(out_path, out)
    print(json.dumps(out))


if __name__ == "__main__":
    main(*sys.argv[1:])
