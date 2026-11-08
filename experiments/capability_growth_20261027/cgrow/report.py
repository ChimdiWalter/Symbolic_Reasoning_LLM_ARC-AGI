"""Tables for the Test I report from runs/<eval>/results.json (evaluator side).

    python -m cgrow.report EVAL_ID PROC_ID > reports/TEST_I_TABLES.md
"""
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from cgrow import paths as P, experiment as X     # noqa: E402

ARMS = ("C2", "C3", "C5")


def pct(a, b):
    return f"{a}/{b}" if b else "0/0"


def main(eval_id, proc_id):
    res = X.load_json(os.path.join(P.RUNS, eval_id, "results.json"))
    ev = X.eval_tasks()
    fams = X.load_json(os.path.join(P.EVALUATOR_DIR, "REMOVED.json"))["removed"]
    expr = {r["name"]: r for r in X.load_json(os.path.join(P.EVALUATOR_DIR, "expressibility_v1.json"))}
    eps = res["episodes"]
    ops = res["ops"]
    out = []
    # controller level choice
    lv = res["levels"]["controller"]
    out.append("## Controller: level chosen for each system task under G0\n")
    out.append("| set | tasks | decision counts | right level |")
    out.append("|---|---|---|---|")
    by = collections.defaultdict(list)
    for r in lv:
        by[(r["partition"], r["family"] or "-")].append(r)
    for k in sorted(by):
        rs = by[k]
        dec = collections.Counter(r["decision"] for r in rs)
        out.append(f"| {k[0]} {k[1]} | {len(rs)} | {', '.join(f'{d} {n}' for d, n in sorted(dec.items()))} | "
                   f"{sum(r['right'] for r in rs)}/{len(rs)} |")
    # per capability
    out.append("\n## Per capability (episodes pooled over the motivating tasks and seeds)\n")
    out.append("| capability | in G0 (evaluator) | arm | episodes | executable proposals | fit the motivating task | "
               "motivating recovered | promoted | E solved by the promoted op (same family) | reference agreement "
               "(promoted / first fitting) | kind |")
    out.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for f in fams:
        ex = expr.get(f, {})
        g0 = "macro at cost 10" if ex.get("found") else "no program within cost 12"
        for arm in ARMS:
            es = [e for e in eps.values() if e["family"] == f and e["arm"] == arm]
            n_prop = sum(sum(v for k, v in e["stages"].items()) for e in es)
            execd = sum(sum(v for k, v in e["stages"].items() if k in ("no_fit_on_motivating_task",
                                                                        "fits_motivating_task",
                                                                        "duplicate_of_G0_program")) for e in es)
            fit = sum(e["stages"].get("fits_motivating_task", 0) for e in es)
            rec = sum(e["recovered_motivating"] for e in es)
            prom = [e for e in es if e["scored_op"]["status"] == "promoted"]
            reuse = [ops[e["scored_op"]["code_sha256"]]["e_correct_same_family"] for e in prom
                     if e["scored_op"].get("code_sha256") in ops]
            agr = [ops[e["scored_op"]["code_sha256"]]["ref_agreement"] for e in es
                   if e["scored_op"].get("code_sha256") in ops]
            agr_p = [ops[e["scored_op"]["code_sha256"]]["ref_agreement"] for e in prom
                     if e["scored_op"].get("code_sha256") in ops]
            kinds = collections.Counter(ops[e["scored_op"]["code_sha256"]]["kind"] for e in prom
                                        if e["scored_op"].get("code_sha256") in ops)
            fmt = lambda xs: ("-" if not xs else f"{max(x or 0 for x in xs):.2f} max")       # noqa: E731
            out.append(f"| {f} | {g0} | {arm} | {len(es)} | {pct(execd, n_prop)} | {fit} | {pct(rec, len(es))} | "
                       f"{pct(len(prom), len(es))} | {sum(reuse)} over {len(prom)} ops (of {6 * len(prom)}) | "
                       f"{fmt(agr_p)} / {fmt(agr)} | {dict(kinds) or '-'} |")
    # failure stages
    out.append("\n## Where proposals stopped (all proposals, per arm)\n")
    stages = collections.defaultdict(collections.Counter)
    for e in eps.values():
        stages[e["arm"]].update(e["stages"])
    keys = sorted({k for c in stages.values() for k in c})
    out.append("| stage / outcome | " + " | ".join(ARMS) + " |")
    out.append("|---|" + "---|" * len(ARMS))
    for k in keys:
        out.append(f"| {k} | " + " | ".join(str(stages[a].get(k, 0)) for a in ARMS) + " |")
    # comparisons
    out.append("\n## Paired comparisons (units: motivating task x seed)\n")
    out.append("| comparison | units | both | first only | second only | neither | exact McNemar p | "
               "difference 95% CI |")
    out.append("|---|---|---|---|---|---|---|---|")
    for k, v in res["comparisons"].items():
        if "mean_diff" in v:
            out.append(f"| {k} | {v['units']} | | | | | | mean {v['mean_diff']} {v['diff_ci95']} |")
            continue
        a = k.split("_vs_")[0]
        b = k.split("_vs_")[1].split(":")[0]
        out.append(f"| {k} | {v['units']} | {v['both']} | {v['only_' + a]} | {v['only_' + b]} | {v['neither']} | "
                   f"{v['mcnemar_p']} | {v['diff_ci95']} |")
    # E tasks
    out.append("\n## Excluded tasks (E): C7 and the promoted operations\n")
    out.append("| family | E tasks | C7 (20x search) correct | promoted ops (any arm) solving at least one |")
    out.append("|---|---|---|---|")
    for f in fams:
        es_ = [t for t, v in res["e_tasks"].items() if v["family"] == f]
        c7 = sum(res["e_tasks"][t]["c7"] for t in es_)
        solved_by = set()
        for e in eps.values():
            if e["scored_op"]["status"] == "promoted" and e["scored_op"].get("code_sha256") in ops:
                for t, r in ops[e["scored_op"]["code_sha256"]]["e"].items():
                    if r["correct"] and ev[t]["family"] == f:
                        solved_by.add(t)
        out.append(f"| {f} | {len(es_)} | {c7} | {len(solved_by)} |")
    # leak scan
    lk = res["leak"]
    hi = [v for v in lk.values() if v["max_ratio"] >= 0.7]
    nm = [v for v in lk.values() if v["removed_names_in_code"]]
    out.append(f"\n## Leak scan\n\nDistinct proposal codes scanned: {len(lk)}; near-verbatim arc-dsl matches (token "
               f"ratio >= 0.70): {len(hi)}; codes using a removed primitive's name as an identifier: {len(nm)}.")
    for v in sorted(hi, key=lambda v: -v["max_ratio"])[:8]:
        out.append(f"- {v['episode']} sample {v['sample']}: ratio {v['max_ratio']} to dsl `{v['closest_dsl_function']}`")
    for v in nm[:8]:
        out.append(f"- {v['episode']} sample {v['sample']}: identifiers {v['removed_names_in_code']}")
    # cost
    tok = collections.Counter()
    gpu = collections.Counter()
    for e in eps.values():
        tok[e["arm"]] += e["gen_tokens"]
        gpu[e["arm"]] += e["gpu_s"]
    out.append("\n## Generation cost per arm\n")
    out.append("| arm | episodes | generated tokens | GPU-s | mean prompt tokens |")
    out.append("|---|---|---|---|---|")
    for a in ARMS:
        es = [e for e in eps.values() if e["arm"] == a]
        pt = [e["prompt_tokens"] for e in es if e["prompt_tokens"]]
        out.append(f"| {a} | {len(es)} | {tok[a]} | {round(gpu[a])} | {round(sum(pt) / max(1, len(pt)))} |")
    c1 = res["c1"]
    out.append(f"| C1 | {len(c1)} task-seeds | {sum(v['gen_tokens'] for v in c1.values())} | | |")
    print("\n".join(out))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
