"""Deterministic compiler-parity benchmark on already EXPOSED real ARC grids: every ncv2-g1 parity program (both test
files) on every demonstration input of the 60 dev60 tasks. AST-compiled and hand-written native dicts must give
identical results.

    python scripts/neural_cora_v2_parity_bench.py   # -> outputs/neural_cora_v2/parity_bench/dev60_demo_inputs_parity.json

Only demonstration inputs are read; there is no search, no fitting and no answers. So this is parity evidence (the
addendum's measure A), not G2. It also counts how often each construct changes a real grid or is undefined on it
(native EvalError).
"""
import importlib.util
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
OUT = os.path.join(HERE, "outputs", "neural_cora_v2", "parity_bench")


def main():
    spec = importlib.util.spec_from_file_location("parity", os.path.join(HERE, "tests", "test_neural_cora_v2_parity.py"))
    PT = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(PT)
    from cora_neural_v2 import bridge as B
    from cora_neural_v2.rast import parse_sexpr
    grids = PT.dev60_demo_inputs(60)
    per, mism = {}, []
    c0 = time.process_time()
    for name, src, expected in PT.all_parity_programs():
        ast = parse_sexpr(src)
        d = per.setdefault(name, {"executions": 0, "changed": 0, "eval_error": 0, "mismatch": 0})
        for key, g in grids:
            a, b = B.execute(ast, g), B.run_native_dict(expected, g)
            d["executions"] += 1
            if (a is None) != (b is None) or (a is not None and (a.shape != b.shape or not np.array_equal(a, b))):
                d["mismatch"] += 1
                mism.append([name, key])
            elif a is None:
                d["eval_error"] += 1
            elif a.shape != g.shape or not np.array_equal(a, g):
                d["changed"] += 1
    tot = {k: sum(v[k] for v in per.values()) for k in ("executions", "changed", "eval_error", "mismatch")}
    res = {"corpus": "dev60 demonstration inputs (exposed; no answers read)", "n_tasks": 60, "n_grids": len(grids),
           "n_programs": len(per), "totals": tot, "cpu_s": round(time.process_time() - c0, 1), "per_program": per,
           "mismatches": mism}
    os.makedirs(OUT, exist_ok=True)
    json.dump(res, open(os.path.join(OUT, "dev60_demo_inputs_parity.json"), "w"), indent=1)
    print(json.dumps({k: res[k] for k in ("n_grids", "n_programs", "totals", "cpu_s")}))
    sys.exit(1 if mism else 0)


if __name__ == "__main__":
    main()
