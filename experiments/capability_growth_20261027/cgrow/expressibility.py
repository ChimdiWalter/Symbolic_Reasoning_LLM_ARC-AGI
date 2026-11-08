"""Evaluator-side check before task construction: is a candidate removed primitive expressible in G0 (G minus R)
by a short composition? Runs A2's bottom-up search on probe grids -> reference outputs. Writes
evaluator_only/expressibility_<tag>.json. Usage: python -m cgrow.expressibility TAG budget cpu_cap
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from cgrow import paths as P, lang0 as L0, probes as PR   # noqa: E402
from a2 import bus as B, arcdsl as D                     # noqa: E402

CANDS = [("compress", ("compress",), ()), ("trim", ("trim",), ()), ("downscale", ("downscale",), (2,)),
         ("downscale", ("downscale",), (3,)), ("upscale", ("upscale",), (2,)), ("upscale", ("upscale",), (3,)),
         ("upscale", ("upscale", "hupscale", "vupscale"), (2,)), ("hmirror", ("hmirror",), ()),
         ("tophalf", ("tophalf",), ()), ("cmirror", ("cmirror",), ()), ("rot270", ("rot270",), ())]


def main(tag, budget, cpu_cap):
    grids = PR.probe_grids(10)
    rows = []
    for name, removed, params in CANDS:
        g = L0.build_g0(removed)
        ref = L0.reference_fn(name)
        pairs = []
        for x in grids:
            try:
                pairs.append((x, ref(x, *params)))
            except Exception:                                   # noqa: BLE001
                pass
        t0 = time.process_time()
        r = B.search(g, pairs[:-1], [pairs[-1][0]], budget=budget, max_size=30, cpu_cap=cpu_cap, want=1)
        ok = bool(r.solved) and r.preds and tuple(map(tuple, r.preds[0][0])) == pairs[-1][1]
        rows.append({"name": name, "removed": removed, "params": params, "n_probes": len(pairs),
                     "found": r.fits[:2], "query_ok": ok, "level": r.level, "stop": r.stop, "calls": r.calls,
                     "cpu_s": round(time.process_time() - t0, 1)})
        print(json.dumps(rows[-1]), flush=True)
    os.makedirs(P.EVALUATOR_DIR, exist_ok=True)
    with P.open_write(os.path.join(P.EVALUATOR_DIR, f"expressibility_{tag}.json")) as f:
        json.dump(rows, f, indent=1)


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]), float(sys.argv[3]))
