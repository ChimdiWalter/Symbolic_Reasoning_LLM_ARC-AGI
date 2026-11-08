"""U2b analysis (U2B_PROTOCOL.md sections 4-7): rescore U2's frozen systems, read the FIT_ONLY / B1 / B2 ladder from U2's
saved system-b evidence, score the new MATCHED_SEARCH arms, cluster bootstrap (1D-ARC types, ConceptARC concepts; Mini-ARC
by task), primary and Holm-adjusted secondary contrasts. Writes results/U2B_RESULTS.json and results/U2B_SUMMARY.md.
Run: python3 -I u2b_analysis.py"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import score as SC  # noqa: E402  (U2's frozen scorer: outcomes of systems a, b, c)

E, DATA = SC.E, SC.DATA
BENCHES = ("concept_arc", "mini_arc", "1d_arc")
VARIANTS = ("real", "shuffled")
ARMS = ("O+ v2", "H-CAST (B3)", "O", "FIT_ONLY", "B1", "B2", "MATCHED_SEARCH", "MATCHED_SEARCH_LOO", "COPY")
R_ = 10000
CONTEXT = {"source": "Moskvichev, Odouard and Mitchell 2023, Table 1 (paper/REFERENCE_CHECK.md)",
           "first_place_arc_kaggle_mean_accuracy": 0.5125, "test_inputs": 480, "guesses_per_input": 3,
           "note": "context only, not a run arm; three guesses against our two attempts"}


def single(ans, inp, s):
    a = ans is not None and ans != inp
    c = a and ans == s
    return {"answered": a, "correct": bool(c), "pass2": bool(c or inp == s)}


def rows_for(bench, variant):
    ch = SC.load(os.path.join(DATA, "prepared", bench, f"{variant}.json"))
    sol = SC.load(os.path.join(DATA, "prepared", bench, "solutions_scorer_only", "solutions.json"))
    meta = SC.load(os.path.join(DATA, "prepared", bench, "meta.json"))
    out = {}
    for sy, arm in (("a", "O+ v2"), ("b", "H-CAST (B3)"), ("c", "O")):
        o = SC.outcomes(sy, os.path.join(SC.RUNS, f"{sy}_{bench}_{variant}"), ch, sol)
        out[arm] = {k: {"answered": v["answered"], "correct": v["correct"], "pass2": v["pass2"]} for k, v in o.items()}
    side = os.path.join(SC.RUNS, f"b_{bench}_{variant}", "side")
    u2b = os.path.join(SC.RUNS, f"u2b_{bench}_{variant}")
    for arm in ("FIT_ONLY", "B1", "B2", "MATCHED_SEARCH", "MATCHED_SEARCH_LOO", "COPY",
                "FIT_ONLY|same_B3", "B3|same_B3", "FIT_ONLY|same_B2", "B2|same_B2"):
        out[arm] = {}
    ident = {"B3_same_module_accepted": 0, "B3_grid_differs_from_candidate": 0,
             "B2_same_module_accepted": 0, "B2_grid_differs_from_candidate": 0}
    cpu = {"budget_s": 0.0, "main_cpu_s": 0.0, "fold_cpu_s": 0.0, "child_cpu_s": 0.0, "n_tasks": 0, "errors": 0}
    for tid, t in ch.items():
        ev = ((SC.load(os.path.join(side, f"{tid}.json"), {}) or {}).get("evidence") or {}).get("queries") or []
        bl = SC.load(os.path.join(u2b, f"{tid}.json"), None)
        if bl is not None:
            cpu["n_tasks"] += 1
            cpu["errors"] += not bl.get("ok", False)
            cpu["budget_s"] += float(bl.get("budget_s") or 0)
            cpu["main_cpu_s"] += float(bl.get("main_cpu_s") or 0)
            cpu["fold_cpu_s"] += sum(float(f.get("cpu_s") or 0) for f in bl.get("folds") or [])
            cpu["child_cpu_s"] += float(bl.get("child_cpu_s") or 0)
            cpu["killed_by_signal"] = cpu.get("killed_by_signal", 0) + (bl.get("signal") is not None)
            cpu["stopped_at_first_fit"] = cpu.get("stopped_at_first_fit", 0) + (bl.get("program") is not None)
        for j, x in enumerate(t["test"]):
            s, inp = sol[tid][j], x["input"]
            q = ev[j] if j < len(ev) and isinstance(ev[j], dict) else {}
            out["FIT_ONLY"][(tid, j)] = fo = single(q.get("candidate"), inp, s)
            out["B1"][(tid, j)] = single((q.get("accepted") or {}).get("B1"), inp, s)
            out["B2"][(tid, j)] = single((q.get("accepted") or {}).get("B2"), inp, s)
            none = {"answered": False, "correct": False, "pass2": False}
            for pol in ("B3", "B2"):                      # amendment 1: same-module diagnostics
                g = (q.get("accepted") or {}).get(pol)
                am = (q.get("accepted_module") or {}).get(pol)
                acc = single(g, inp, s)
                switched = acc["answered"] and am != q.get("candidate_module")
                keep = fo["answered"] and not switched
                out[f"FIT_ONLY|same_{pol}"][(tid, j)] = fo if keep else none
                out[f"{pol}|same_{pol}"][(tid, j)] = acc if keep else none
                if keep and acc["answered"]:
                    ident[f"{pol}_same_module_accepted"] += 1
                    ident[f"{pol}_grid_differs_from_candidate"] += g != q.get("candidate")
            a_ = (bl or {}).get("answer") if (bl or {}).get("ok") else None
            g = a_[j] if a_ and j < len(a_) else None
            out["MATCHED_SEARCH"][(tid, j)] = single(g, inp, s)
            out["MATCHED_SEARCH_LOO"][(tid, j)] = single(g if (bl or {}).get("loo_pass") else None, inp, s)
            out["COPY"][(tid, j)] = {"answered": False, "correct": False, "pass2": inp == s}
    clus = {k: (meta[k[0]]["group"] if meta[k[0]]["group"] else k[0]) for k in out["COPY"]}
    cpu["identity_checks"] = ident
    return out, clus, cpu


def cluster_sums(rows, clus):
    ids = sorted(set(clus.values()))
    ix = {c: i for i, c in enumerate(ids)}
    sums = {}
    for arm, rr in rows.items():
        m = np.zeros((len(ids), 4))
        for k, v in rr.items():
            i = ix[clus[k]]
            m[i] += (v["answered"], v["correct"], 1, v["pass2"])
        sums[arm] = m
    return ids, sums


def stat(vec, kind):
    a, c, n, p = vec[..., 0], vec[..., 1], vec[..., 2], vec[..., 3]
    with np.errstate(invalid="ignore", divide="ignore"):
        return {"precision": c / a, "coverage": a / n, "accuracy": c / n, "pass2": p / n}[kind]


def main():
    rng = np.random.default_rng(0)
    res = {"protocol_sha256": json.load(open(os.path.join(E, "U2B_FREEZE.json")))["u2b_protocol_sha256"],
           "context_conceptarc_published": CONTEXT, "benchmarks": {}, "cpu": {}, "primary": None, "secondary": {},
           "paired_vs_frozen": {}, "clusters": {}}
    data = {}
    for v in VARIANTS:
        for b in BENCHES:
            rows, clus, cpu = rows_for(b, v)
            ids, sums = cluster_sums(rows, clus)
            data[(b, v)] = (ids, sums)
            res["cpu"][f"{b}_{v}"] = {k: round(x, 2) if isinstance(x, float) else x for k, x in cpu.items()}
            res["clusters"][b] = {"n_clusters": len(ids), "unit": {"1d_arc": "task type", "concept_arc": "concept",
                                                                  "mini_arc": "task (unclustered)"}[b]}
    # one set of bootstrap draws, shared by every statistic (paired contrasts); stratified by benchmark
    draws = {}
    for v in VARIANTS:
        for b in BENCHES:
            n = len(data[(b, v)][0])
            idx = rng.integers(0, n, (R_, n))
            cnt = np.zeros((R_, n))
            np.add.at(cnt, (np.arange(R_)[:, None], idx), 1)
            draws[(b, v)] = cnt

    def rep(arm, v, benches):
        tot = sum(data[(b, v)][1][arm].sum(axis=0) for b in benches)
        boot = sum(draws[(b, v)] @ data[(b, v)][1][arm] for b in benches)
        return tot, boot

    def summary(arm, v, benches, kind):
        tot, boot = rep(arm, v, benches)
        x = stat(boot, kind)
        ok = np.isfinite(x)
        return {"point": float(stat(tot, kind)) if np.isfinite(stat(tot, kind)) else None,
                "ci95": [float(np.percentile(x[ok], 2.5)), float(np.percentile(x[ok], 97.5))] if ok.any() else None,
                "replicates_excluded": int((~ok).sum())}

    def contrast(arm1, arm2, v, benches, kind):
        t1, b1 = rep(arm1, v, benches)
        t2, b2 = rep(arm2, v, benches)
        d = stat(b1, kind) - stat(b2, kind)
        ok = np.isfinite(d)
        dd = d[ok]
        pt = stat(t1, kind) - stat(t2, kind)
        pg = float((1 + (dd <= 0).sum()) / (len(dd) + 1)) if len(dd) else None
        pl = float((1 + (dd >= 0).sum()) / (len(dd) + 1)) if len(dd) else None
        return {"arm1": arm1, "arm2": arm2, "kind": kind, "benchmarks": list(benches), "variant": v,
                "point": float(pt) if np.isfinite(pt) else None,
                "ci95": [float(np.percentile(dd, 2.5)), float(np.percentile(dd, 97.5))] if len(dd) else None,
                "p_one_sided_greater": pg, "p_two_sided": min(1.0, 2 * min(pg, pl)) if len(dd) else None,
                "replicates_excluded": int((~ok).sum())}

    for b in BENCHES:
        res["benchmarks"][b] = {}
        for v in VARIANTS:
            for arm in ARMS:
                tot = data[(b, v)][1][arm].sum(axis=0)
                res["benchmarks"][b][f"{arm} | {v}"] = {
                    "outputs": int(tot[2]), "answered": int(tot[0]), "correct": int(tot[1]),
                    **{k: summary(arm, v, (b,), k) for k in ("coverage", "precision", "accuracy", "pass2")}}
    for v in VARIANTS:
        res["benchmarks"].setdefault("pooled", {})
        for arm in ARMS:
            tot = sum(data[(b, v)][1][arm].sum(axis=0) for b in BENCHES)
            res["benchmarks"]["pooled"][f"{arm} | {v}"] = {
                "outputs": int(tot[2]), "answered": int(tot[0]), "correct": int(tot[1]),
                **{k: summary(arm, v, BENCHES, k) for k in ("coverage", "precision", "accuracy", "pass2")}}
    P = contrast("H-CAST (B3)", "FIT_ONLY", "real", BENCHES, "precision")
    P["decision"] = "B3_POLICY_RAISES_PRECISION" if P["ci95"] and P["ci95"][0] > 0 else "NOT_SHOWN"
    P["measures"] = "the whole selective B3 policy (module choice, leave-one-out, disagreement, fold agreement, restart)"
    res["primary"] = P
    sec = {"S1": ("B1", "FIT_ONLY", BENCHES, "precision"), "S2": ("H-CAST (B3)", "FIT_ONLY", ("concept_arc",), "precision"),
           "S3": ("H-CAST (B3)", "FIT_ONLY", ("mini_arc",), "precision"),
           "S4": ("H-CAST (B3)", "FIT_ONLY", ("1d_arc",), "precision"),
           "S5": ("H-CAST (B3)", "FIT_ONLY", BENCHES, "coverage"),
           "S6": ("MATCHED_SEARCH_LOO", "MATCHED_SEARCH", BENCHES, "precision"),
           "S7": ("FIT_ONLY", "MATCHED_SEARCH", BENCHES, "accuracy"),
           "S8": ("H-CAST (B3)", "MATCHED_SEARCH_LOO", BENCHES, "precision"),
           "S9": ("O+ v2", "MATCHED_SEARCH", BENCHES, "accuracy"),
           "S10": ("H-CAST (B3)", "MATCHED_SEARCH", BENCHES, "accuracy"),
           "S11": ("B2", "FIT_ONLY", BENCHES, "precision"),
           "S12": ("B3|same_B3", "FIT_ONLY|same_B3", BENCHES, "precision"),
           "S13": ("B2|same_B2", "FIT_ONLY|same_B2", BENCHES, "precision")}
    for k, (a1, a2, bs, kind) in sec.items():
        res["secondary"][k] = contrast(a1, a2, "real", bs, kind)
    order = sorted((c["p_two_sided"] if c["p_two_sided"] is not None else 1.0, k) for k, c in res["secondary"].items())
    run = 0.0
    for i, (p, k) in enumerate(order):
        run = max(run, min(1.0, (len(order) - i) * p))
        res["secondary"][k]["p_holm"] = run
        res["secondary"][k]["significant_holm_0.05"] = run < 0.05
    s11, s13 = res["secondary"]["S11"], res["secondary"]["S13"]
    # amendment 2: the gate also requires zero same-module grid mismatches (B2 and B3) on every REAL benchmark; a missing
    # count or a missing benchmark counts as a mismatch (fail-safe). One expression, using only bool, all, s11, s13 and res
    # outside any nested scope, so that it can be evaluated on its own (as the reviewers' probe does).
    res["loo_specific_wording_allowed"] = bool(
        all(c["significant_holm_0.05"] and c["point"] is not None and c["point"] > 0
            and c["ci95"] is not None and c["ci95"][0] > 0 for c in (s11, s13))
        and all((res["cpu"].get("concept_arc_real", {}).get("identity_checks", {}).get("B2_grid_differs_from_candidate", 1) == 0,
                 res["cpu"].get("concept_arc_real", {}).get("identity_checks", {}).get("B3_grid_differs_from_candidate", 1) == 0,
                 res["cpu"].get("mini_arc_real", {}).get("identity_checks", {}).get("B2_grid_differs_from_candidate", 1) == 0,
                 res["cpu"].get("mini_arc_real", {}).get("identity_checks", {}).get("B3_grid_differs_from_candidate", 1) == 0,
                 res["cpu"].get("1d_arc_real", {}).get("identity_checks", {}).get("B2_grid_differs_from_candidate", 1) == 0,
                 res["cpu"].get("1d_arc_real", {}).get("identity_checks", {}).get("B3_grid_differs_from_candidate", 1) == 0)))
    for arm in ("FIT_ONLY", "B1", "B2", "MATCHED_SEARCH", "MATCHED_SEARCH_LOO"):
        for ref in ("O+ v2", "H-CAST (B3)"):
            for kind in ("accuracy", "pass2"):
                res["paired_vs_frozen"][f"{arm} - {ref} | {kind}"] = {
                    b: contrast(arm, ref, "real", (b,), kind) for b in BENCHES} | {
                    "pooled": contrast(arm, ref, "real", BENCHES, kind)}
    os.makedirs(os.path.join(E, "results"), exist_ok=True)
    json.dump(res, open(os.path.join(E, "results", "U2B_RESULTS.json"), "w"), indent=1)

    def f3(x):
        return "n/a" if x is None else f"{x:.3f}"

    def ci(c):
        return "" if not c else f"[{c[0]:.3f}, {c[1]:.3f}]"
    L = ["# U2b results: controls for U2 (written by u2b_analysis.py)", "",
         f"Protocol sha256 {res['protocol_sha256']}. Intervals: bootstrap clustered by 1D-ARC type (14) and ConceptARC "
         "concept (16); Mini-ARC resampled by task (unclustered). 10,000 resamples.", ""]
    for b in BENCHES + ("pooled",):
        L += [f"## {b}", "", "| arm | variant | answered / outputs | coverage [95% CI] | correct | precision [95% CI] | "
              "pass@2 [95% CI] |", "|---|---|---|---|---|---|---|"]
        for arm in ARMS:
            for v in VARIANTS:
                s = res["benchmarks"][b][f"{arm} | {v}"]
                L.append(f"| {arm} | {v} | {s['answered']} / {s['outputs']} | {f3(s['coverage']['point'])} "
                         f"{ci(s['coverage']['ci95'])} | {s['correct']} | {f3(s['precision']['point'])} "
                         f"{ci(s['precision']['ci95'])} | {f3(s['pass2']['point'])} {ci(s['pass2']['ci95'])} |")
        L.append("")
    L += ["## Primary contrast", "", f"precision(H-CAST, B3) - precision(FIT_ONLY), REAL, pooled: {f3(P['point'])} "
          f"{ci(P['ci95'])}, one-sided p = {P['p_one_sided_greater']}: **{P['decision']}**", "",
          f"Measures: {P['measures']}. Leave-one-out-specific wording allowed (S11 and S13 both Holm-significant and "
          f"positive, and no same-module grid mismatch on any REAL benchmark): {res['loo_specific_wording_allowed']}.", "",
          "## Secondary contrasts (Holm over 13)", "", "| id | contrast | point | 95% CI | p two-sided | p Holm |",
          "|---|---|---|---|---|---|"]
    for k, c in res["secondary"].items():
        L.append(f"| {k} | {c['kind']}({c['arm1']}) - {c['kind']}({c['arm2']}), {'+'.join(c['benchmarks'])} | "
                 f"{f3(c['point'])} | {ci(c['ci95'])} | {f3(c['p_two_sided'])} | {f3(c['p_holm'])} |")
    L += ["", f"CPU of the new search arms per benchmark and variant: {json.dumps(res['cpu'])}", "",
          f"Context (not an arm): {json.dumps(CONTEXT)}"]
    open(os.path.join(E, "results", "U2B_SUMMARY.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L[-30:]))


if __name__ == "__main__":
    main()
