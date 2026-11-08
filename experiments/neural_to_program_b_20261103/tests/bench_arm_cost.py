"""CPU cost of one real Test B arm on synthetic random tasks of growing grid size (no real ARC data).

    python3 -I tests/bench_arm_cost.py OUT.json

Each case: three random demonstrations of an n x n grid to an n x n grid, a random test input, and a random target of
the same shape (a target no program is expected to fit, so the arm runs its base search, its typed holes and up to
three retries). The worker runs exactly as in a run: its own process, the production environment, os.wait4 receipt.
"""
import json
import os
import random
import subprocess
import sys
import tempfile
import time

EXP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, EXP)
from testb import common as C              # noqa: E402
from testb import driver as DR             # noqa: E402


def case(n, seed):
    rng = random.Random(seed)
    grid = lambda: [[rng.choice([0, 0, 0, 1, 2, 3, 4]) for _ in range(n)] for _ in range(n)]
    return {"arm": f"bench.{n}.neural", "stage": "primary", "name": "neural", "unit": f"bench.{n}", "task": "bench",
            "output": 0, "demos": [[grid(), grid()] for _ in range(3)], "x": grid(), "target": grid()}


def main(out):
    d = tempfile.mkdtemp(prefix="testb_bench_")
    rows = []
    for n in (6, 12, 20, 30):
        files = [os.path.join(d, f"{n}.{k}.json") for k in ("in", "out", "progress")]
        C.write_json_atomic(files[0], case(n, n))
        t0 = time.monotonic()
        p = subprocess.Popen([DR.Config().python, "-I", DR.Config().worker] + files, env=DR.child_env(DR.Config()))
        _, status, ru = os.wait4(p.pid, 0)
        res = C.load_json(files[1]) if os.path.exists(files[1]) else {}
        rows.append({"grid": f"{n}x{n}", "exit": os.waitstatus_to_exitcode(status), "outcome": res.get("outcome"),
                     "arm_cpu_s": round(ru.ru_utime + ru.ru_stime, 2), "wall_s": round(time.monotonic() - t0, 2),
                     "searches": [(s["search"], s["stop"], s["calls"], s["cpu_s"]) for s in res.get("searches", [])],
                     "hole_matching_operations": res.get("n_hole_matching_operations")})
        print(json.dumps(rows[-1]), flush=True)
    C.write_json_atomic(out, {"cases": rows, "note": "synthetic random tasks; production worker and environment"})


if __name__ == "__main__":
    main(sys.argv[1])
