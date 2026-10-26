"""Version 5 search: version 4's (cora_neural_v2g4.search) with version 5 programs added to its constructed head.
It reads the demonstrations and the test inputs only.

**Budget**, exactly as version 4: `budget` candidate evaluations in all; the head gets at most `head_share` of them,
in order: inversion programs, version 4 part and ray programs, version 5 programs (construct.py), the geometry tier;
ncv2-g3's unchanged search gets the rest. Construction work is not a candidate evaluation: the record reports its
native selector checks (`construct_native_runs`) and rule-alone executions (`construct_rule_checks`) beside CPU time.
**Selection**: select.py (version 4's, readable for version 5 programs), with leave-one-out over what construction
derives without each demonstration.
"""
import time

from cora_neural_v2.rast import ASTError, to_sexpr
from cora_neural_v2g2 import grammar as G
from cora_neural_v2g3 import delta as D
from cora_neural_v2g3 import search as S3
from cora_neural_v2g3 import select as SEL
from cora_neural_v2g4 import construct as C4
from cora_neural_v2g4 import invert as INV
from cora_neural_v2g4 import program as PG
from cora_neural_v2g4 import search as S4
from cora_neural_v2g5 import construct as C5
from cora_neural_v2g5 import program as P5
from cora_neural_v2g5 import select as SEL5

GRAMMAR_VERSION = "ncv2-g5"


def head(task, construct_cpu_s=60.0):
    out = [(p, "g4_invert") for p, _ in INV.invert(task)] + [(p, "g4_construct") for p in C4.programs(task)] + \
        [(p, "g5_construct") for p in C5.programs(task, cpu_budget_s=construct_cpu_s)]
    seen = {p for p, _ in out}
    for p, origin in _geometry(task):
        if p not in seen:
            seen.add(p)
            out.append((p, origin))
    return out


def _geometry(task):
    """Version 4's geometry tier: (true) with each reflection, rotation and scaling, in every distinct view."""
    from cora_neural_v2 import search as G1S
    from cora_neural_v2.rast import N
    return [(N("program", (v, (N("rule", (N("true", ()), a)),), "keep", N("same_as_input", ()))), "g4_geometry")
            for v in G1S.distinct_views(task) for a in S4.GEOMETRY]


def render(prog):
    if isinstance(prog, P5.G5Program):
        return C5.sexpr(prog)
    return S4.render(prog)


def _fits(prog, train):
    if isinstance(prog, P5.G5Program):
        return P5.fits(prog, train)
    return S4._fits(prog, train)


def _execute(prog, grid):
    return P5.execute(prog, grid) if isinstance(prog, P5.G5Program) else S4._execute(prog, grid)


def search(task, budget, head_share=0.3, cpu_cap_s=None, select_cfg=None, loo=True, construct_cpu_s=60.0):
    train, tests = task["train"], task["test_inputs"]
    INV._EXISTS_CACHE.clear()
    c0, r0, k0 = time.process_time(), INV.RUNS["native"], P5.RUNS["checks"]
    fits, n = [], 0
    cap = int(head_share * budget)
    hd = head(task, construct_cpu_s)
    construct_runs, rule_checks = INV.RUNS["native"] - r0, P5.RUNS["checks"] - k0
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
    for s, at in zip(r3["programs"], r3["pred_at"]):
        prog = G.parse(s)
        if prog in head_fits:
            continue
        preds = [D.execute(prog, t) for t in tests]
        if all(p is not None for p in preds):
            fits.append({"prog": prog, "preds": preds, "at": n + at, "origin": "g3"})
    cfg = select_cfg or SEL.SelectConfig()

    def lite(reduced, b, preds=False):
        return [p for p, _ in INV.invert(reduced)] + C4.programs(reduced) + \
            C5.programs(reduced, cpu_budget_s=max(5.0, construct_cpu_s / 4))
    if loo:
        cfg = SEL.SelectConfig(**{**cfg.__dict__, "loo_budget": max(1, cfg.loo_budget)})
    r1, k1 = INV.RUNS["native"], P5.RUNS["checks"]
    ranked, chosen = SEL5.choose(fits, task, cfg, lite if loo else None)
    loo_runs, loo_checks = INV.RUNS["native"] - r1, P5.RUNS["checks"] - k1
    found, seen = [], set()
    for f in sorted(fits, key=lambda f: f["at"]):
        k = SEL.pred_key(f["preds"])
        if k not in seen:
            seen.add(k)
            found.append(f)
    origins = ("g4_invert", "g4_construct", "g5_construct", "g4_geometry")
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
            "head": {"constructed": len(hd), "evaluated": n, "fits": sum(f["origin"] != "g3" for f in fits),
                     "by_origin": {o: sum(h[1] == o for h in hd) for o in origins},
                     "construct_native_runs": construct_runs, "construct_rule_checks": rule_checks,
                     "loo_native_runs": loo_runs, "loo_rule_checks": loo_checks},
            "fit_origins": {o: sum(f["origin"] == o for f in fits) for o in sorted({f["origin"] for f in fits})},
            "stability": {render(r["prog"]): r["loo"] for r in ranked if r["loo"]},
            "selection": [{"program": render(r["prog"]), "at": r["at"], "origin": r["origin"],
                           "score": round(r["score"], 3), "loo": r["loo"]} for r in ranked[:8]],
            "g3": {k: r3[k] for k in ("n_candidates", "n_consistent", "first_fit_at", "origins", "state")},
            "cpu_s": round(time.process_time() - c0, 3)}
