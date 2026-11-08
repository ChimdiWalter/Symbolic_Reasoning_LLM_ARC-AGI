"""The honest expectation and power, from the source-half numbers only (phase 1).

    python -I run.py power LIB_DIR OUT_JSON

Expected held-half gains of the library arm over G0, per family: the leave-one-source-out fits (solved source tasks
that G0 plus the library built from the OTHER source solutions solves at base) plus the reach fits (source failures
beyond 4x that G0 plus the library solves at base), scaled by held/source tasks of the family. Matched static
search's expected gains over G0: the tasks the 4x search found (the allowance is above 4x the base CPU), scaled the
same way. The decision rule is simulated: per family, Poisson draws of the expected discordant counts, a synthetic
held table, the pre-registered comparison (exact test and family-clustered bootstrap, 2,000 draws here) and its
decision; 300 simulations.
"""
import json
import os
import random
import sys

from ngb import env as E
from ngrow import data as DT, analysis as AN

SIMS, BOOT = 300, 2000


def pois(rng, lam):
    if lam <= 0:
        return 0
    L, k, p = pow(2.718281828459045, -lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= L:
            return k
        k += 1


def simulate(lams, held_sizes, rng):
    """lams: {(bench, family): (lam_only_A, lam_only_B)}; returns the comparison's decision for one draw."""
    rows = []
    for (b, f), (la, lb) in lams.items():
        n = held_sizes[(b, f)]
        a_only, b_only = min(n, pois(rng, la)), min(n, pois(rng, lb))
        for i in range(n):
            cl = f if b != "mini_arc" else f"{f}:{i}"
            rows.append({"bench": b, "cluster": cl, "A": 1 if i < a_only else 0,
                         "B": 1 if a_only <= i < a_only + b_only else 0})
    old = AN.DRAWS
    AN.DRAWS = BOOT
    try:
        return AN.compare(rows, "A", "B")
    finally:
        AN.DRAWS = old


FEAS_A = os.path.join(E.STUDY_A, "feasibility", "FEASIBILITY.json")


def expected(lib_dir):
    """Per family: expected held tasks on which (a) the library beats G0, (b) the library beats matched static
    search, (c) matched static search beats the library; from the source half, scaled by held/source tasks.
    Library correct outputs per source task: the leave-one-source-out run (tasks solved at 4x) or the reach run
    (failures). Static's: study A's 4x-probe correct outputs (its allowance is above 4x the base CPU; failures beyond
    4x are counted as 0 for static, which favours the library). Base-solved tasks are solved by every arm."""
    sp = DT.split()
    fa = E.load(FEAS_A)["benchmarks"]
    rows = []
    for b in DT.BENCHMARKS:
        ins = E.load(os.path.join(lib_dir, b, "insample.json"))
        for f, r in sp["benchmarks"][b]["families"].items():
            scale = len(r["held"]) / max(1, len(r["source"]))
            a = bs = sa = 0
            for t in r["source"]:
                ta = fa[b]["tasks"][t]
                if ta["base_fit"]:
                    continue
                if t in ins["loso"]:
                    lib_c, st_c = ins["loso"][t]["correct"], ta["x4_correct"]
                else:
                    lib_c, st_c = ins["reach"][t]["correct"], 0
                a += lib_c > 0
                bs += lib_c > st_c
                sa += st_c > lib_c
            rows.append({"bench": b, "family": f, "source_tasks": len(r["source"]), "held_tasks": len(r["held"]),
                         "source_library_beats_G0": a, "source_library_beats_static": bs,
                         "source_static_beats_library": sa, "scale": round(scale, 3),
                         "expected_held_library_beats_G0": round(a * scale, 2),
                         "expected_held_library_beats_static": round(bs * scale, 2),
                         "expected_held_static_beats_library": round(sa * scale, 2)})
    return rows


def main(lib_dir, out_path):
    rows = expected(lib_dir)
    held_sizes = {(r["bench"], r["family"]): r["held_tasks"] for r in rows}
    lam_lib = {(r["bench"], r["family"]): (r["expected_held_library_beats_G0"], 0.0) for r in rows}
    lam_static = {(r["bench"], r["family"]): (r["expected_held_library_beats_static"],
                                              r["expected_held_static_beats_library"]) for r in rows}
    rng = random.Random(20261105)
    dec_lib, dec_static = {}, {}
    for _ in range(SIMS):
        d = simulate(lam_lib, held_sizes, rng)["decision"]
        dec_lib[d] = dec_lib.get(d, 0) + 1
        d2 = simulate(lam_static, held_sizes, rng)["decision"]
        dec_static[d2] = dec_static.get(d2, 0) + 1
    libs = {b: E.load(os.path.join(lib_dir, b, "library.json")) for b in DT.BENCHMARKS}
    out = {"per_family": [r for r in rows if r["source_library_beats_G0"] or r["source_static_beats_library"]
                          or r["source_library_beats_static"]],
           "libraries": {b: {"size": v["counts"]["library"], "operations": [o["program"] for o in v["library"]],
                             "cpu_s": v["cpu_s"]} for b, v in libs.items()},
           "expected_held_library_beats_G0": round(sum(v[0] for v in lam_lib.values()), 2),
           "expected_held_library_beats_static": round(sum(v[0] for v in lam_static.values()), 2),
           "expected_held_static_beats_library": round(sum(v[1] for v in lam_static.values()), 2),
           "min_discordant_tasks_for_p_below_0.05": AN.min_discordant_for_significance(),
           "simulated_decisions_library_vs_G0": {k: round(v / SIMS, 3) for k, v in dec_lib.items()},
           "simulated_decisions_library_vs_matched_static": {k: round(v / SIMS, 3) for k, v in dec_static.items()},
           "simulations": SIMS, "bootstrap_draws_in_simulation": BOOT}
    E.dump(os.path.abspath(out_path), out)
    print(json.dumps({k: v for k, v in out.items() if k not in ("per_family", "libraries")}, indent=1))
    print(json.dumps(out["per_family"], indent=0))


if __name__ == "__main__":
    main(*sys.argv[1:])
