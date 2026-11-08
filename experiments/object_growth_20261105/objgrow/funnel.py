"""The development funnel (scorer side for the motivating-task recovery counts: source test outputs only).

    python -I run.py funnel OUT_DIR [BENCH ...]

Per benchmark, from OUT_DIR/<BENCH>/{units.json, registry.json, reuse.json}:
- units (construction units: source failures where the controller decided to construct), holes (3 per unit);
- object correspondence: holes and units where every changed object of every pair is explained by a per-object
  edit and every appeared cell is written by one (full), or at least one changed object is explained (partial);
- verified candidates: holes and units with at least one operation that maps every hole pair exactly; of these,
  the ones passing leave-one-out (gated);
- gates: candidates gated, rejected as search shortcuts (a G0 program of cost at most 7 reproduces them on the
  probes), retried, fitting the motivating task, promoted, quarantined (task-local), rolled back;
- recovery: motivating tasks whose retry predicted every test output correctly (any gated candidate that fit;
  pass@2 of that search), promoted or task-local;
- registry (after the combined regression check) and reuse: tasks fit and test outputs correct under G0 and under
  G0 + registry on the whole source half, newly fit, newly correct, lost;
- CPU: construction (process CPU of the constructor), charged gate CPU (distinct results), reuse searches.
Writes OUT_DIR/FUNNEL.json and prints a Markdown table.
"""
import json
import os
import sys

from objgrow import env as E, grow as GR
from ngrow import data as DT, score as SC


def bench_funnel(out_dir, bench):
    bdir = os.path.join(out_dir, bench)
    units = GR.load_units(bdir)                       # units.json or the per-shard files of a kernel run
    reg = E.load(os.path.join(bdir, "registry.json")) if os.path.exists(os.path.join(bdir, "registry.json")) else None
    reuse = E.load(os.path.join(bdir, "reuse.json")) if os.path.exists(os.path.join(bdir, "reuse.json")) else None
    ids = sorted(units)
    sol = SC.solutions(bench, ids) if ids else {}
    f = {"units": len(units), "holes": 0, "holes_corr_full": 0, "holes_corr_partial": 0, "units_corr_full": 0,
         "units_corr_partial": 0, "holes_verified": 0, "units_verified": 0, "units_loo": 0, "candidates_verified": 0,
         "candidates_loo": 0, "gated": 0, "search_shortcut": 0, "novelty_undecidable": 0, "retried": 0,
         "fits_motivating": 0, "units_fit": 0, "promoted": 0, "quarantined": 0, "rolled_back": 0,
         "units_recovered_correct": 0, "units_recovered_correct_promoted": 0, "not_retried_cap": 0,
         "construction_cpu_s": 0.0, "charged_gate_cpu_s": 0.0, "process_cpu_s": 0.0, "executions_ops": 0,
         "executions_edits": 0, "segmentations": 0, "by_family": {}}
    for tid, u in units.items():
        fam = u["family"]
        bf = f["by_family"].setdefault(fam, {"units": 0, "corr_full": 0, "verified": 0, "loo": 0, "fit": 0,
                                             "promoted": 0, "recovered_correct": 0})
        bf["units"] += 1
        full = part = ver = 0
        for h in u["holes"]:
            f["holes"] += 1
            full += bool(h["correspondence"])
            part += bool(h["correspondence_partial"])
            ver += bool(h["candidates"])
        f["holes_corr_full"] += full
        f["holes_corr_partial"] += part
        f["holes_verified"] += ver
        f["units_corr_full"] += full > 0
        f["units_corr_partial"] += part > 0
        f["units_verified"] += ver > 0
        f["units_loo"] += u["n_candidates_loo"] > 0
        f["candidates_verified"] += u["n_candidates"]
        f["candidates_loo"] += u["n_candidates_loo"]
        bf["corr_full"] += full > 0
        bf["verified"] += ver > 0
        bf["loo"] += u["n_candidates_loo"] > 0
        f["construction_cpu_s"] += u["construction_cpu_s"]
        f["process_cpu_s"] += u["process_cpu_s"]
        f["charged_gate_cpu_s"] += u.get("charged_gate_cpu_s", 0.0)
        f["executions_ops"] += u["counts"]["op"]
        f["executions_edits"] += u["counts"]["edit"]
        f["segmentations"] += u["counts"]["segment"]
        fit_any = rec_any = rec_prom = False
        for row in u.get("rows", []):
            f["gated"] += 1
            f["search_shortcut"] += row["outcome"] == "search_shortcut"
            f["novelty_undecidable"] += bool(row.get("novelty_undecidable"))
            f["not_retried_cap"] += row["outcome"] == "not_retried_cap"
            if "fit" in row:
                f["retried"] += 1
            if row["outcome"] == "fits_motivating_task":
                f["fits_motivating"] += 1
                fit_any = True
                f[row["promotion"]] += 1
                ok = SC.score_row(row.get("preds"), sol[tid])["correct"] == len(sol[tid])
                rec_any |= ok
                rec_prom |= ok and row["promotion"] == "promoted"
        f["units_fit"] += fit_any
        f["units_recovered_correct"] += rec_any
        f["units_recovered_correct_promoted"] += rec_prom
        bf["fit"] += fit_any
        bf["promoted"] += u.get("promoted") is not None
        bf["recovered_correct"] += rec_any
    for k in ("construction_cpu_s", "charged_gate_cpu_s", "process_cpu_s"):
        f[k] = round(f[k], 1)
    f["registry"] = reg["registry"] if reg else None
    f["registry_size"] = len(reg["registry"]) if reg else None
    f["promoted_in_unit_order"] = len(reg["promoted_in_unit_order"]) if reg else None
    f["combined_regression_cpu_s"] = reg["combined_regression_cpu_s"] if reg else None
    f["reuse"] = reuse["summary"] if reuse else None
    return f


def table(F):
    rows = [("construction units", "units"), ("holes (3 per unit)", "holes"),
            ("holes with a full object correspondence", "holes_corr_full"),
            ("units with a full object correspondence", "units_corr_full"),
            ("units with a partial correspondence", "units_corr_partial"),
            ("holes with a verified candidate", "holes_verified"),
            ("units with a verified candidate", "units_verified"),
            ("units with a leave-one-out candidate", "units_loo"),
            ("candidates gated", "gated"), ("rejected as search shortcuts", "search_shortcut"),
            ("retried on the motivating task", "retried"), ("candidates fitting the motivating task", "fits_motivating"),
            ("units with a fitting candidate", "units_fit"),
            ("promoted (one new fit on another source failure)", "promoted"), ("quarantined (task-local)", "quarantined"),
            ("rolled back (regression)", "rolled_back"),
            ("units recovered: fitting candidate predicts every test output", "units_recovered_correct"),
            ("of which promoted", "units_recovered_correct_promoted"),
            ("registry after the combined regression check", "registry_size"),
            ("construction CPU-s (total)", "construction_cpu_s"), ("charged gate CPU-s (distinct results)", "charged_gate_cpu_s")]
    benches = list(F)
    out = ["| stage | " + " | ".join(benches) + " |", "|---|" + "---:|" * len(benches)]
    for label, k in rows:
        out.append(f"| {label} | " + " | ".join(str(F[b].get(k)) for b in benches) + " |")
    for label, k in (("G0: tasks fit; test outputs correct", ("g0_tasks_fit", "g0_outputs_correct")),
                     ("grown grammar: tasks fit; test outputs correct", ("grown_tasks_fit", "grown_outputs_correct")),
                     ("newly fit tasks; newly correct tasks; lost fits",
                      ("newly_fit", "newly_correct_tasks", "lost_fit")),
                     ("out-of-sample newly correct tasks; expected on the held half (reuse only); held tasks",
                      ("out_of_sample_newly_correct_tasks", "expected_held_newly_correct_tasks", "held_tasks"))):
        cells = []
        for b in benches:
            r = F[b].get("reuse")
            if not r:
                cells.append("-")
            else:
                cells.append("; ".join(str(len(r[x]) if isinstance(r[x], list) else r[x]) for x in k))
        out.append(f"| reuse on the source half, {label} | " + " | ".join(cells) + " |")
    return "\n".join(out)


def main(out_dir, *benches):
    out_dir = os.path.abspath(out_dir)
    benches = benches or DT.BENCHMARKS
    F = {b: bench_funnel(out_dir, b) for b in benches if os.path.isdir(os.path.join(out_dir, b))}
    E.dump(os.path.join(out_dir, "FUNNEL.json"), F)
    print(table(F))
    for b, f in F.items():
        print(f"\n{b} by family:")
        for fam, v in sorted(f["by_family"].items()):
            print("  ", fam, json.dumps(v))


if __name__ == "__main__":
    main(*sys.argv[1:])
