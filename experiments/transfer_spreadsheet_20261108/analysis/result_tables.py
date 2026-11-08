"""Tables for RESULT.md, computed from the held run's frozen outputs (runs/held/). Written after the freeze; it reads
the outputs and changes nothing. Usage: python3 -I analysis/result_tables.py <study>
Writes runs/held_analysis/RESULT_TABLES.json and prints a compact summary.

Items (the protocol's secondaries and the pre-run review's notes):
- held-check distribution; pieces per held task;
- searches stopped by the CPU cap, including retry searches (candidate rows);
- tasks that may show new ability: recovered by grown at the primary budget, by static at no budget;
- the split by source (forum against the benchmark-author families) and by training size;
- recoveries at about equal CPU. Matching rule (fixed here, before these tables were computed): for each base budget
  B, the grown arm's total CPU over the held tasks is matched to the static pass (static at 4 x B') whose total static
  CPU is nearest to it; ties go to the smaller B'.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from t2 import pieces as P, stats  # noqa: E402

ARMS = ("static", "grown", "shuffled", "classical", "grown_no_loo")
FAMILY = ("bikes", "univ_1", "univ_2", "univ_3", "univ_4", "univ_5", "univ_6")


def load(study):
    held = os.path.join(study, "runs", "held")
    summ = json.load(open(os.path.join(held, "summary.json")))
    recs = {}
    for b in summ["passes"]:
        p = os.path.join(held, f"records_B{b}.jsonl")
        if os.path.exists(p):
            recs[int(b)] = [json.loads(ln) for ln in open(p)]
    return summ, recs


def main(study):
    summ, recs = load(study)
    prim_b = summ["budgets"][0]
    prim = recs[prim_b]
    split = json.load(open(os.path.join(study, "split", "DEV_SPLIT.json")))
    tasks = {t["id"]: t for t in json.load(open(os.path.join(study, "data", "prepared", "tasks.json")))["tasks"]}
    held_ids = split["held_pool_tasks"]
    out = {"salt_in_summary": summ.get("salt"), "budgets": summ["budgets"]}
    # held checks
    nchk = [r["n_checks"] for r in prim]
    out["held_checks"] = {"tasks": len(nchk), "exactly_one": sum(1 for n in nchk if n == 1),
                          "one_by_k": {str(k): sum(1 for r in prim if r["n_checks"] == 1 and r["k_train"] == k)
                                       for k in (2, 3)},
                          "two_to_five": sum(1 for n in nchk if 2 <= n <= 5), "six_or_more": sum(1 for n in nchk if n >= 6),
                          "max": max(nchk), "total_checks": sum(nchk)}
    # pieces per task
    npieces = {i: sum(1 for _ in P.all_pieces(P.delims(tasks[i]["str_consts"]))) for i in held_ids}
    dev_max = max(sum(1 for _ in P.all_pieces(P.delims(tasks[i]["str_consts"]))) for i in split["dev_tasks"])
    out["pieces_per_held_task"] = {"min": min(npieces.values()), "max": max(npieces.values()),
                                   "above_development_max": sorted(i for i, n in npieces.items() if n > dev_max),
                                   "development_max": dev_max}
    # CPU-cap stops, including retries
    caps = {}
    for b, rs in recs.items():
        c = {"base": 0, "static": 0, "classical": 0, "grown_retries": 0, "shuffled_retries": 0, "retries_total": 0}
        for r in rs:
            c["base"] += r["base"]["stop"] == "cpu_cap"
            c["static"] += r["static"].get("stop") == "cpu_cap"
            c["classical"] += r["classical"].get("stop") == "cpu_cap"
            for arm in ("grown", "shuffled"):
                for row in r[arm].get("candidates", []) or []:
                    c["retries_total"] += 1
                    c[f"{arm}_retries"] += row.get("stop") == "cpu_cap"
        caps[str(b)] = c
    out["cpu_cap_stops"] = caps
    # new ability candidates
    static_any = {r["id"] for rs in recs.values() for r in rs if r["static"]["recovered"]}
    out["grown_primary_not_static_at_any_budget"] = sorted(r["id"] for r in prim if r["grown"]["recovered"]
                                                           and r["id"] not in static_any)
    out["static_budgets_used"] = sorted(4 * b for b in recs)
    out["complete_passes"] = {b: summ["passes"][b].get("complete") for b in summ["passes"]}
    # split by source and training size
    by = {}
    for b, rs in recs.items():
        d = {}
        for name, sel in (("forum", lambda r: r["id"] not in FAMILY), ("benchmark_author_families",
                                                                       lambda r: r["id"] in FAMILY),
                          ("train_2", lambda r: r["k_train"] == 2), ("train_3", lambda r: r["k_train"] == 3)):
            sub = [r for r in rs if sel(r)]
            d[name] = dict({a: sum(int(r[a]["recovered"]) for r in sub) for a in ARMS}, n=len(sub))
        by[str(b)] = d
    out["breakdowns"] = by
    # recoveries at about equal CPU
    tot = {b: {a: sum(r["cpu_s"][a] for r in rs) for a in ("static", "grown", "shuffled", "classical")}
           for b, rs in recs.items()}
    eq = []
    for b in sorted(recs):
        g_cpu = tot[b]["grown"]
        best = sorted(recs, key=lambda b2: (abs(tot[b2]["static"] - g_cpu), b2))[0]
        g = {r["id"]: int(r["grown"]["recovered"]) for r in recs[b]}
        s = {r["id"]: int(r["static"]["recovered"]) for r in recs[best]}
        ids = [i for i in g if i in s]
        cmp = stats.compare("grown", [g[i] for i in ids], "static", [s[i] for i in ids])
        eq.append({"grown_base_budget": b, "grown_cpu_s": round(g_cpu, 2), "static_base_budget": best,
                   "static_executions": 4 * best, "static_cpu_s": round(tot[best]["static"], 2),
                   "grown": cmp["a_right"], "static": cmp["b_right"], "grown_only": cmp["a_only"],
                   "static_only": cmp["b_only"], "mcnemar_exact_p": cmp["mcnemar_exact_p"], "n": cmp["n"]})
    out["equal_cpu"] = eq
    out["cpu_totals"] = {str(b): {a: round(v, 2) for a, v in t.items()} for b, t in tot.items()}
    # per-task primary outcomes (ids and flags only)
    out["primary_tasks"] = [{"id": r["id"], "k": r["k_train"], "checks": r["n_checks"], "base_fit": r["base"]["fit"],
                             **{a: int(r[a]["recovered"]) for a in ARMS}} for r in prim]
    od = os.path.join(study, "runs", "held_analysis")
    os.makedirs(od, exist_ok=True)
    with open(os.path.join(od, "RESULT_TABLES.json"), "w") as f:
        json.dump(out, f, indent=1, sort_keys=True)
    print(json.dumps({k: out[k] for k in ("salt_in_summary", "held_checks", "pieces_per_held_task", "cpu_cap_stops",
                                          "grown_primary_not_static_at_any_budget", "complete_passes",
                                          "equal_cpu")}, indent=0)[:4000])


if __name__ == "__main__":
    main(os.path.abspath(sys.argv[1]))
