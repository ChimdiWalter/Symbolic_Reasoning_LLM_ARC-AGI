"""ncv2-g4 search (first slice): a constructed head, then the unchanged ncv2-g3 search, then evidence-aware selection.
It reads the demonstrations and the test inputs only.

**Budget.** `budget` candidate evaluations in all, so ncv2-g4 and ncv2-g3 compare at equal candidate counts:
- the HEAD gets at most `head_share` of them: inversion programs (invert.py: rules built from object correspondences),
  then g4 programs (construct.py: part, region and ray rules covering the changed cells, alone or after a partial
  inversion program; at most 64), then the geometry tier, `(true)` × {reflect, rotate, scale} × views (at most 63
  programs). The tier gives cheap single rules the early chance that ncv2-g2's two-first order denies them;
- ncv2-g3 (`cora_neural_v2g3.search`, unchanged and imported) gets the rest.

Native runs that construction spends (selector checks, local checks) are not candidate evaluations; the record
reports them (`head.construct_native_runs`) beside the CPU time.

**Selection** (select.py: ncv2-g3's, with features that read g4 programs) ranks every fit from both. Parameter
leave-one-out is the stability feature: the share of n-1 demonstration subsets from which construction derives the
program again. Programs that only the search found get no stability term.
"""
import time

import numpy as np

from cora_neural_v2 import search as G1S
from cora_neural_v2.rast import ASTError, N, to_sexpr
from cora_neural_v2g2 import grammar as G
from cora_neural_v2g3 import delta as D
from cora_neural_v2g3 import search as S3
from cora_neural_v2g3 import select as SEL
from cora_neural_v2g4 import construct as C
from cora_neural_v2g4 import invert as INV
from cora_neural_v2g4 import program as PG
from cora_neural_v2g4 import select as SEL4

GRAMMAR_VERSION = "ncv2-g4"
GEOMETRY = [N("reflect", (N("axis", (a,)),)) for a in ("horizontal", "vertical", "diag_main", "diag_anti")] + \
    [N("rotate", (N("angle", (k,)),)) for k in (90, 180, 270)] + [N("scale", (N("int", (k,)),)) for k in (2, 3)]


def head(task):
    """Constructed candidates, in order: inversion, g4 part and ray programs, then the geometry tier."""
    out = [(p, "g4_invert") for p, _ in INV.invert(task)] + [(p, "g4_construct") for p in C.programs(task)]
    seen = {p for p, _ in out}
    for v in G1S.distinct_views(task):
        for a in GEOMETRY:
            p = N("program", (v, (N("rule", (N("true", ()), a)),), "keep", N("same_as_input", ())))
            if p not in seen:
                seen.add(p)
                out.append((p, "g4_geometry"))
    return out


def render(prog):
    return C.sexpr(prog) if isinstance(prog, PG.G4Program) else to_sexpr(prog)


def _fits(prog, train):
    if isinstance(prog, PG.G4Program):
        return PG.fits(prog, train)
    return D.fits(D.deltas(prog, train, stop_early=True), len(train))


def _execute(prog, grid):
    return PG.execute(prog, grid) if isinstance(prog, PG.G4Program) else D.execute(prog, grid)


def search(task, budget, head_share=0.3, cpu_cap_s=None, select_cfg=None, loo=True):
    train, tests = task["train"], task["test_inputs"]
    INV._EXISTS_CACHE.clear()                                      # per-task accounting, as in a fresh worker
    c0, r0 = time.process_time(), INV.RUNS["native"]
    fits, n = [], 0
    cap = int(head_share * budget)
    hd = head(task)
    construct_runs = INV.RUNS["native"] - r0
    for prog, origin in hd[:cap]:
        if cpu_cap_s is not None and time.process_time() - c0 > cpu_cap_s:
            break
        n += 1
        try:
            ok = _fits(prog, train)
        except ASTError:
            continue
        if ok:
            preds = [_execute(prog, t) for t in tests]
            if all(p is not None for p in preds):
                fits.append({"prog": prog, "preds": preds, "at": n, "origin": origin})
    left_cpu = None if cpu_cap_s is None else max(1.0, cpu_cap_s - (time.process_time() - c0))
    r3 = S3.search(task, budget - n, cpu_cap_s=left_cpu)
    head_fits = {f["prog"] for f in fits}
    for s, at in zip(r3["programs"], r3["pred_at"]):                # ncv2-g3's kept fits, one per distinct prediction
        prog = G.parse(s)
        if prog in head_fits:
            continue
        preds = [D.execute(prog, t) for t in tests]
        if all(p is not None for p in preds):
            fits.append({"prog": prog, "preds": preds, "at": n + at, "origin": "g3"})
    cfg = select_cfg or SEL.SelectConfig()

    def lite(reduced, b, preds=False):                              # LOO: what construction derives without a demonstration
        return [p for p, _ in INV.invert(reduced)] + C.programs(reduced)
    if loo:
        cfg = SEL.SelectConfig(**{**cfg.__dict__, "loo_budget": max(1, cfg.loo_budget)})
    r1 = INV.RUNS["native"]
    ranked, chosen = SEL4.choose(fits, task, cfg, lite if loo else None)
    loo_runs = INV.RUNS["native"] - r1
    found, seen = [], set()
    for f in sorted(fits, key=lambda f: f["at"]):
        k = SEL.pred_key(f["preds"])
        if k not in seen:
            seen.add(k)
            found.append(f)
    return {"grammar": GRAMMAR_VERSION,
            "attempts": [c["preds"][0].tolist() for c in chosen],
            "attempts_by_test": [[c["preds"][t].tolist() for c in chosen] for t in range(len(tests))],
            "attempts_found": [f["preds"][0].tolist() for f in found[:2]],
            "attempt_programs": [render(c["prog"]) for c in chosen],
            "predictions": [f["preds"][0].tolist() for f in found[:50]],
            "pred_at": [f["at"] for f in found[:50]],
            "programs": [render(f["prog"]) for f in found[:50]],
            "first_fit_at": min((f["at"] for f in fits), default=None),
            "n_candidates": n + r3["n_candidates"], "n_consistent": len(fits), "n_distinct_predictions": len(found),
            "head": {"constructed": len(hd), "evaluated": n, "fits": sum(f["origin"].startswith("g4") for f in fits),
                     "by_origin": {o: sum(h[1] == o for h in hd) for o in ("g4_invert", "g4_construct", "g4_geometry")},
                     "construct_native_runs": construct_runs, "loo_native_runs": loo_runs},
            "fit_origins": {o: sum(f["origin"] == o for f in fits) for o in sorted({f["origin"] for f in fits})},
            "stability": {render(r["prog"]): r["loo"] for r in ranked if r["loo"]},
            "selection": [{"program": render(r["prog"]), "at": r["at"], "origin": r["origin"],
                           "score": round(r["score"], 3), "loo": r["loo"]} for r in ranked[:8]],
            "g3": {k: r3[k] for k in ("n_candidates", "n_consistent", "first_fit_at", "origins", "state")},
            "cpu_s": round(time.process_time() - c0, 3)}
