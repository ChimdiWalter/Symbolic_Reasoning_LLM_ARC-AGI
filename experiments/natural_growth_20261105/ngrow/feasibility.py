"""Phase 1 feasibility summary on the SOURCE halves (evaluator side: opens source test outputs only).

    python -I run.py feasibility CONTROLLER_JSONL[,MORE] GROW_DIR OUT_JSON

Per benchmark and family: G0's solved counts at the base budget and at 4x; the controller's decisions; typed holes
(the controller's sketches) per failure; localisable failures (the controller's partial-fit criterion, PROTOCOL.md
section 4); constructible holes (a schema structure maps every hole input exactly to its target); the construction
funnel of each arm (candidates, novelty, retries, fits, correct motivating predictions, promotions, registry); CPU
per unit; and the in-sample reuse of each registry on the other source failures (base search with G0 + registry;
the motivating and validating tasks of each promoted structure excluded).
"""
import json
import os
import statistics
import sys

from ngrow import env as E, data as DT, plugin as PL, score as SC, grow as GR
from cgrow import selfext_core as C, schema as SG, search as S                 # noqa: E402


def q(xs, f):
    xs = sorted(xs)
    if not xs:
        return None
    return round(xs[min(len(xs) - 1, int(f * len(xs)))], 3)


def cpu_stats(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return None
    return {"n": len(xs), "mean": round(statistics.mean(xs), 3), "median": round(statistics.median(xs), 3),
            "p90": q(xs, 0.9), "max": round(max(xs), 3), "total": round(sum(xs), 1)}


def localises(rec):
    cl = rec.get("closest")
    return bool(cl) and cl["cells_correct"] >= 1


def summarise(ctrl_paths, grow_dir, out_path):
    out = {"benchmarks": {}, "note": "source halves only; held halves untouched"}
    g0b = PL.G0Builder()
    order = SG.seeded_order(GR.SEED)
    plug = PL.NaturalPlugin(g0b)
    for b in DT.BENCHMARKS:
        recs = GR.load_records(ctrl_paths, b)
        src = DT.half("source", (b,))
        ids = [t for _, _, t in src]
        if set(ids) - set(recs):
            out["benchmarks"][b] = {"incomplete": len(set(ids) - set(recs))}
            continue
        sol = SC.solutions(b, ids)
        fam = {t: f for _, f, t in src}
        rows = {}
        for t in ids:
            r = recs[t]["record"]
            base = SC.score_row(r.get("base_preds") if r["base"]["fit"] else None, sol[t])
            deep = r.get("probe_deeper_search") or {}
            dp = r.get("probe_deeper_preds") if deep.get("fit") else None
            d4 = SC.score_row(dp, sol[t]) if not r["base"]["fit"] else base
            sk = r.get("sketches") or []
            cand_all = C.spec_candidates(plug, order, sk) if r["decision"] == "INVENT_NEW_OPERATION" else []
            cand_demo = C.spec_candidates(plug, order, [x for x in sk if x["form"] == "?(I)"]) \
                if r["decision"] == "INVENT_NEW_OPERATION" else []
            rows[t] = {"family": fam[t], "n_outputs": len(sol[t]), "status": r["status"], "decision": r["decision"],
                       "base_fit": r["base"]["fit"], "base_correct": base["correct"],
                       "base_answered": base["answered"], "x4_fit": bool(r["base"]["fit"] or deep.get("fit")),
                       "x4_correct": d4["correct"], "x4_answered": d4["answered"],
                       "n_holes": len(sk), "localises": localises(r) if not r["base"]["fit"] else None,
                       "closest_share": (round(r["closest"]["cells_correct"] / r["closest"]["cells_total"], 4)
                                         if r.get("closest") else None),
                       "constructible": bool(cand_all), "n_candidates": len(cand_all),
                       "candidates": [c["sid"] for c in cand_all], "constructible_demo_only": bool(cand_demo),
                       "cpu_s": recs[t]["cpu_s"], "base_stop": r["base"]["stop"],
                       "base_level": r["base"]["level_complete"], "base_cpu_s": r["base"]["cpu_s"],
                       "x4_cpu_s": deep.get("cpu_s"), "x4_stop": deep.get("stop"), "x4_level": deep.get("level_complete")}
        grow = None
        gp = os.path.join(grow_dir, b, "units.json")
        if os.path.exists(gp):
            units = E.load(gp)
            reg = E.load(os.path.join(grow_dir, b, "registry.json")) \
                if os.path.exists(os.path.join(grow_dir, b, "registry.json")) else None
            grow = {}
            for arm in GR.ARMS:
                us = {k.split("|", 1)[1]: v for k, v in units.items() if k.startswith(arm + "|")}
                if not us:
                    continue
                fit_rows = {t: [x for x in u["rows"] if x.get("fit")] for t, u in us.items()}
                correct = {t: any(SC.score_row(x.get("preds"), sol[t])["correct"] == len(sol[t]) for x in fr)
                           for t, fr in fit_rows.items()}
                correct_out = {t: max([SC.score_row(x.get("preds"), sol[t])["correct"] for x in fr] or [0])
                               for t, fr in fit_rows.items()}
                grow[arm] = {
                    "units": len(us),
                    "units_with_candidates": sum(1 for u in us.values() if u.get("n_candidates")),
                    "candidates": sum(u.get("n_candidates") or 0 for u in us.values()),
                    "search_shortcuts": sum(1 for u in us.values() for x in u["rows"]
                                            if x.get("outcome") == "search_shortcut"),
                    "retries": sum(u["retries"] for u in us.values()),
                    "units_with_fit": sum(1 for t in us if fit_rows[t]),
                    "units_motivating_all_outputs_correct": sum(correct.values()),
                    "motivating_correct_outputs": sum(correct_out.values()),
                    "units_promoted": sum(1 for u in us.values() if u["promoted"]),
                    "promoted_structures": sorted({u["promoted"] for u in us.values() if u["promoted"]}),
                    "rolled_back": sum(1 for u in us.values() for x in u["rows"] if x.get("promotion") == "rolled_back"),
                    "quarantined": sum(1 for u in us.values() for x in u["rows"] if x.get("promotion") == "quarantined"),
                    "registry": (reg or {}).get("arms", {}).get(arm, {}).get("registry"),
                    "construction_cpu_s_distinct": (reg or {}).get("arms", {}).get(arm, {}).get("construction_cpu_s"),
                    "charged_cpu_per_unit": cpu_stats([u["cpu_s"] for u in us.values()]),
                    "process_cpu_per_unit": cpu_stats([u["process_cpu_s"] for u in us.values()])}
        fails = [t for t in ids if not rows[t]["base_fit"]]
        inv = [t for t in ids if rows[t]["decision"] == "INVENT_NEW_OPERATION"]
        summ = {
            "tasks": len(ids), "outputs": sum(rows[t]["n_outputs"] for t in ids),
            "g0_base": {"tasks_fit": sum(rows[t]["base_fit"] for t in ids),
                        "correct_outputs": sum(rows[t]["base_correct"] for t in ids),
                        "answered_outputs": sum(rows[t]["base_answered"] for t in ids)},
            "g0_4x": {"tasks_fit": sum(rows[t]["x4_fit"] for t in ids),
                      "correct_outputs": sum(rows[t]["x4_correct"] for t in ids),
                      "answered_outputs": sum(rows[t]["x4_answered"] for t in ids)},
            "decisions": {d: sum(1 for t in ids if rows[t]["decision"] == d) for d in
                          ("NONE", "PRESERVE_COMPETING_HYPOTHESES", "CONTINUE_PROGRAM_SEARCH", "INVENT_NEW_OPERATION",
                           "REQUEST_ADDITIONAL_ADMISSIBLE_EVIDENCE")},
            "base_failures": len(fails),
            "localisable_failures": sum(1 for t in fails if rows[t]["localises"]),
            "localisable_invent_failures": sum(1 for t in inv if rows[t]["localises"]),
            "invent_failures": len(inv),
            "holes_per_invent_failure": cpu_stats([rows[t]["n_holes"] for t in inv]),
            "invent_failures_with_constructible_hole": sum(1 for t in inv if rows[t]["constructible"]),
            "invent_failures_constructible_identity_hole_only": sum(1 for t in inv if rows[t]["constructible_demo_only"]),
            "candidate_structures": sorted({s for t in inv for s in rows[t]["candidates"]}),
            "controller_cpu_per_task": cpu_stats([rows[t]["cpu_s"] for t in ids]),
            "base_cpu_per_task": cpu_stats([rows[t]["base_cpu_s"] for t in ids]),
            "x4_cpu_per_failure": cpu_stats([rows[t]["x4_cpu_s"] for t in fails]),
            "base_stops": {s: sum(1 for t in ids if rows[t]["base_stop"] == s)
                           for s in sorted({rows[t]["base_stop"] for t in ids})},
            "x4_stops": {s: sum(1 for t in fails if rows[t]["x4_stop"] == s)
                         for s in sorted({str(rows[t]["x4_stop"]) for t in fails})},
            "base_level_complete": cpu_stats([rows[t]["base_level"] for t in ids]),
            "x4_level_complete": cpu_stats([rows[t]["x4_level"] for t in fails]),
            "construction": grow}
        fams = {}
        for t in ids:
            f = rows[t]["family"]
            a = fams.setdefault(f, {"tasks": 0, "base_correct": 0, "x4_correct": 0, "outputs": 0, "invent": 0,
                                    "localisable_failures": 0, "constructible": 0})
            a["tasks"] += 1
            a["outputs"] += rows[t]["n_outputs"]
            a["base_correct"] += rows[t]["base_correct"]
            a["x4_correct"] += rows[t]["x4_correct"]
            a["invent"] += rows[t]["decision"] == "INVENT_NEW_OPERATION"
            a["localisable_failures"] += bool(rows[t]["localises"])
            a["constructible"] += rows[t]["constructible"]
        summ["families"] = fams
        out["benchmarks"][b] = {"summary": summ, "tasks": rows}
    E.dump(out_path, out)
    brief = {b: {k: v for k, v in r["summary"].items() if k not in ("families", "construction")}
             for b, r in out["benchmarks"].items() if "summary" in r}
    print(json.dumps(brief, indent=1))


def main(ctrl_paths, grow_dir, out_path):
    summarise(ctrl_paths, os.path.abspath(grow_dir), os.path.abspath(out_path))


if __name__ == "__main__":
    main(*sys.argv[1:])
