"""Phase 2 scoring and analysis (refused without the GO), run on Athe after the kernels' outputs are downloaded and
their manifests verified. Writes RESULTS.json and REPORT.md into RUN_DIR (PROTOCOL.md sections 6 and 7).

    python -I run.py report RUN_DIR [ARC2_RUN_DIR]
"""
import glob
import json
import os
import sys

from ngrow import env as E, data as DT, gate as GT, score as SC, analysis as AN

HELD_ARMS = ("G0", "S-hole", "S-shuffled", "S-demo", "S-enum", "static")
MISSING = {}
NAMES = {"G0": "G0 alone", "S-hole": "growth from the system's own holes", "S-shuffled": "shuffled holes",
         "S-demo": "demonstrations only", "S-enum": "blind enumeration", "static": "matched static search"}


def rows_of(run_dir, sub, arm):
    out = {}
    for p in sorted(glob.glob(os.path.join(run_dir, sub, f"{arm}.jsonl")) +
                    glob.glob(os.path.join(run_dir, sub, f"{arm}.shard*.jsonl"))):
        with open(p, encoding="utf-8") as f:
            for x in f:
                if x.strip():
                    r = json.loads(x)
                    out.setdefault(r["task"], r)
    return out


def localises(g0_row):
    """Primary population: G0's base search found no fit and its partial fit gets >= 1 demonstration cell right."""
    pf = g0_row.get("partial_fit")
    return (not g0_row["fit"]) and bool(pf) and pf["cells_correct"] >= 1


def held_table(run_dir):
    tab = []
    for b in DT.BENCHMARKS:
        ids = [t for _, _, t in DT.half("held", (b,))]
        fam = {t: f for _, f, t in DT.half("held", (b,))}
        sol = SC.solutions(b, ids)
        arms = {a: rows_of(run_dir, os.path.join("held", b), a) for a in HELD_ARMS}
        for a, rs in arms.items():
            MISSING[f"{b}/{a}"] = len(set(ids) - set(rs))
        for t in ids:
            r = {"bench": b, "family": fam[t], "task": t, "cluster": fam[t] if b != "mini_arc" else t,
                 "n_outputs": len(sol[t]), "primary": t in arms["G0"] and localises(arms["G0"][t])}
            for a in HELD_ARMS:
                if t not in arms[a]:                   # missing: reported, never imputed
                    r[a] = r[a + "_answered"] = r[a + "_wrong"] = r[a + "_cpu_s"] = None
                    continue
                sc = SC.score_row(arms[a][t]["preds"] if arms[a][t]["fit"] else None, sol[t])
                r[a] = sc["correct"]
                r[a + "_answered"] = sc["answered"]
                r[a + "_wrong"] = sc["answered"] - sc["correct"]
                r[a + "_cpu_s"] = arms[a][t].get("cpu_s")
            tab.append(r)
    return tab


def arc2_table(run_dir):
    sol = SC.arc2_solutions()
    arms = {a: rows_of(run_dir, "arc2", a) for a in ("G0", "growth", "static")}
    tab = []
    for t in sorted(sol):
        r = {"bench": "arc_agi_2_eval", "task": t, "cluster": t, "n_outputs": len(sol[t])}
        for a, rs in arms.items():
            if t not in rs:                            # missing: reported, never imputed
                MISSING[f"arc2/{a}"] = MISSING.get(f"arc2/{a}", 0) + 1
                r[a] = r[a + "_answered"] = None
                continue
            sc = SC.score_row(rs[t]["preds"] if rs[t]["fit"] else None, sol[t])
            r[a], r[a + "_answered"] = sc["correct"], sc["answered"]
        tab.append(r)
    return tab


def totals(rows, arm):
    rows = [r for r in rows if r.get(arm) is not None]
    n = sum(r["n_outputs"] for r in rows)
    c = sum(r[arm] for r in rows)
    a = sum(r[arm + "_answered"] for r in rows)
    return {"outputs": n, "correct": c, "answered": a, "precision": round(c / a, 4) if a else None,
            "precision_wilson95": AN.wilson(c, a), "accuracy_wilson95": AN.wilson(c, n)}


def main(run_dir, arc2_dir=None):
    GT.require_phase2()
    tab = held_table(run_dir)
    prim = [r for r in tab if r["primary"]]
    res = {"missing_tasks_per_arm": dict(MISSING),
           "populations": {"primary_tasks": len(prim), "all_tasks": len(tab),
                           "primary_by_benchmark": {b: sum(1 for r in prim if r["bench"] == b) for b in DT.BENCHMARKS}},
           "totals": {"primary": {a: totals(prim, a) for a in HELD_ARMS}, "all": {a: totals(tab, a) for a in HELD_ARMS}}}
    res["primary"] = AN.compare(prim, "S-hole", "static")
    wrong = [dict(r, w_g=r["S-hole_wrong"], w_s=r["static_wrong"]) for r in tab]
    sec = {"S1_all_tasks_growth_vs_static": AN.compare(tab, "S-hole", "static"),
           "S2_growth_vs_shuffled": AN.compare(prim, "S-hole", "S-shuffled"),
           "S3_growth_vs_blind_enumeration": AN.compare(prim, "S-hole", "S-enum"),
           "S4_wrong_answers_growth_vs_static": AN.compare(wrong, "w_g", "w_s")}
    for b in DT.BENCHMARKS:
        sec[f"S5_{b}_growth_vs_static"] = AN.compare([r for r in prim if r["bench"] == b], "S-hole", "static")
    if arc2_dir:
        a2 = arc2_table(arc2_dir)
        res["arc_agi_2"] = {"totals": {a: totals(a2, a) for a in ("G0", "growth", "static")},
                            "exposure": "used in earlier development and gates of the project; not a fresh test"}
        sec["S6_arc_agi_2_growth_vs_static"] = AN.compare(a2, "growth", "static")
    adj = AN.holm({k: v["exact_mcnemar_p"] for k, v in sec.items()})
    for k in sec:
        sec[k]["holm_p"] = adj[k]
    res["secondary"] = sec
    res["descriptive"] = {f"{x}_vs_{y}": AN.compare(prim, x, y) for x, y in
                          (("S-hole", "G0"), ("static", "G0"), ("S-enum", "G0"), ("S-hole", "S-demo"))}
    E.dump(os.path.join(run_dir, "RESULTS.json"), res)
    L = ["# Natural-task growth test: results (written by ngrow/report.py)", "",
         f"Primary population (held tasks where G0 fails and its failure localises): {len(prim)} of {len(tab)}.", "",
         "| arm | primary correct | primary answered | all correct | all answered | precision (all) |",
         "|---|---|---|---|---|---|"]
    for a in HELD_ARMS:
        p, q = res["totals"]["primary"][a], res["totals"]["all"][a]
        L.append(f"| {NAMES[a]} | {p['correct']} | {p['answered']} | {q['correct']} | {q['answered']} | {q['precision']} |")
    pc = res["primary"]
    L += ["", f"**Primary (growth from holes vs matched static, primary population): {pc['decision']}**; "
          f"tasks only growth {pc['tasks_only_S-hole']}, only static {pc['tasks_only_static']}, exact McNemar "
          f"p = {pc['exact_mcnemar_p']}, total difference {pc['sum_difference']}, family-clustered 95% interval "
          f"{pc['family_cluster_ci95']}.", "", "Secondary (Holm-adjusted):", ""]
    for k, v in sec.items():
        L.append(f"- {k}: {v['decision']}, p = {v['exact_mcnemar_p']}, Holm p = {v['holm_p']}, difference "
                 f"{v['sum_difference']}, interval {v['family_cluster_ci95']}")
    with E.open_write(os.path.join(run_dir, "REPORT.md")) as f:
        f.write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main(*sys.argv[1:])
