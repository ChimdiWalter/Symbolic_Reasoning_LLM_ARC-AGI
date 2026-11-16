"""Run the core-operations measurement. Author: Chimdi Walter Ndubuisi

    env PYTHONHASHSEED=0 python -s -B experiments/core_operations_20261113/run_all.py <outdir> [--ops a,b,c]
        [--budget-scale X] [--max-size N]

Deterministic (fixed seeds, PYTHONHASHSEED=0), resumable (finished operations are skipped), CPU only.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core                      # noqa: E402
import dslx                      # noqa: E402
import presets as P              # noqa: E402


def main(argv):
    if os.environ.get("PYTHONHASHSEED") != "0":
        sys.exit("run with PYTHONHASHSEED=0")
    args = list(argv)
    outdir = args.pop(0)
    opt = {"--ops": None, "--budget-scale": None, "--max-size": None}
    while args:
        k = args.pop(0)
        opt[k] = args.pop(0)
    L = dslx.load()
    ops = opt["--ops"].split(",") if opt["--ops"] else list(L["lib_order"])
    bad = [o for o in ops if o not in L["lib_order"]]
    if bad:
        sys.exit("unknown operations: %s" % bad)
    sc = float(opt["--budget-scale"]) if opt["--budget-scale"] else 1.0
    budgets = {k: v * sc for k, v in P.BUDGET_S.items()}
    ms = int(opt["--max-size"]) if opt["--max-size"] else None
    os.makedirs(outdir, exist_ok=True)
    for i, o in enumerate(ops):
        cpu = core.run_op(outdir, o, budgets, ms)
        print("%3d/%d %-14s cpu %.1fs" % (i + 1, len(ops), o, cpu), flush=True)
    s = core.summarize(outdir, set(ops))
    with open(os.path.join(outdir, "SUMMARY.json"), "w") as f:
        json.dump(s, f, indent=1, sort_keys=True)
    print("total cpu %.1fs; summary written" % s["total_cpu_s"])


if __name__ == "__main__":
    main(sys.argv[1:])
