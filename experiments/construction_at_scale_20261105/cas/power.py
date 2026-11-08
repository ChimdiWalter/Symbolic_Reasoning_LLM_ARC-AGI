"""Power of the primary contrast at S1's observed effect (phase 1; no new run, S1's records only).

    python -m cas.power OUT.json

Primary contrast (PROTOCOL.md): CORA's own holes (S-hole) against matched static search (C7m) on motivating tasks,
a task counted as recovered when it is recovered in at least 2 of 3 seeds. Decision "S-hole beats matched search":
exact two-sided McNemar p < 0.05 AND the family-clustered bootstrap 95% interval (S1's percentile method, families
resampled with replacement) lies above 0. Decision "S1-sized advantage refuted": not the former, and the interval's
upper end lies below S1's observed difference, 3/11 = 0.273.

S1's observed effect, at task level (records/NOV1_S1_TASK_LEVEL_CORRECTION.md; units from
experiments/capability_growth_20261027/runs/s1_eval/results.json): of 11 tasks, both recovered 4, S-hole only 4,
matched search only 1, neither 2. Scenarios:
  A  tasks independent, with S1's pooled cell shares;
  B  S1's between-family heterogeneity: each new family copies one of S1's 4 families (drawn with replacement)
     and its tasks are drawn with replacement from that family's tasks (a nested bootstrap of S1's data);
  N  null (no effect): the two methods' outcomes exchanged at random within each task of scenario B, used for
     the chance of each decision when S-hole has no advantage.
Revision 2: the decision rule's bootstrap runs over the design's 8 clusters (W2's four families as one), in
simulate_clustered and simulate_design; simulate() keeps the 11-family version for comparison.
  C  design-based sensitivity (an assumption-laden model, not S1's observed effect): the 11 planned families with
     their worlds; S-hole's chance by template class from S1 (T1 3 of 3; composite with an invertible operation 5
     of 5; composite with a non-invertible operation 0 of 3; Jeffreys means 0.875, 0.917, 0.125); the composite's
     operation drawn from the world's list (invertible share W1 7/11, W2 3/9, W3 7/13); matched search's chance by
     family type from S1 (families with a G0 route found by the evaluator-only deep search, trim and upscale in S1:
     4 of 5, mean 0.75; other families: 1 of 6, mean 0.214); the two methods independent given these.
Each configuration: F families x m motivating tasks per family before the controller filter, each task kept as
motivating with probability q (S1: 11 of 12; the pilot's share is used when given), R simulated studies, B
bootstrap draws.
"""
import json
import math
import os
import sys

import numpy as np

from cas import env as E

S1_RESULTS = os.path.join(E.S1_DIR, "runs", "s1_eval", "results.json")
S1_EFFECT = 3 / 11


def s1_tasks():
    r = E.load(S1_RESULTS)
    per = {}
    for u in r["units"]:
        d = per.setdefault(u["task"], {"family": u["family"], "hole": 0, "c7m": 0})
        d["hole"] += bool(u["arms"]["S-hole"]["recovered"])
        d["c7m"] += bool(u["arms"]["C7m"]["recovered"])
    fams = {}
    for t, d in sorted(per.items()):
        fams.setdefault(d["family"], []).append((int(d["hole"] >= 2), int(d["c7m"] >= 2)))
    return fams


def committed_check(out_path):
    """The committed-output policy of revision 2 applied to S1's own units (runs/s1_run/units.json): per arm and
    task, the task-level counts under 'recovered' (committed outputs) and under 'reach' (any retried candidate),
    with the number of units holding more than one fitting candidate. If the counts agree with results.json, the
    power model (s1_tasks) is unchanged by the policy."""
    import os
    from cgrow import evaluate as EV
    units = E.load(os.path.join(E.S1_DIR, "runs", "s1_run", "units.json"))
    ev = E.load(os.path.join(E.S1_DIR, "evaluator_only", "TASKS_EVAL.json"))
    per, reach, multi = {}, {}, 0
    for k, v in units.items():
        arm, tid, s = k.split("|")
        outs = ev[tid]["test_outputs"]
        fits = [r for r in v["rows"] if r.get("fit")]
        multi += len(fits) > 1
        kept = next((r for kind in ("promoted", "quarantined") for r in fits if r.get("promotion") == kind), None)
        per.setdefault(arm, {}).setdefault(tid, {})[s] = bool(kept) and EV.correct((kept.get("preds") or [])[:2], outs)
        reach.setdefault(arm, {}).setdefault(tid, {})[s] = any(EV.correct(r.get("preds"), outs) for r in fits)
    rec = {"s1_units": len(units), "units_with_more_than_one_fitting_candidate": multi, "arms": {}}
    for arm in per:
        rec["arms"][arm] = {"committed_majority": sum(sum(d.values()) >= 2 for d in per[arm].values()),
                            "committed_all3": sum(all(d.values()) for d in per[arm].values()),
                            "reach_majority": sum(sum(d.values()) >= 2 for d in reach[arm].values()),
                            "reach_all3": sum(all(d.values()) for d in reach[arm].values())}
    rec["results_json_S-hole_majority"] = sum(h for h, _ in [x for f in s1_tasks().values() for x in f])
    rec["results_json_C7m_majority"] = sum(c for _, c in [x for f in s1_tasks().values() for x in f])
    E.dump(out_path, rec)
    print(json.dumps(rec))


def mcnemar_p(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def cluster_ci(fam_sum, fam_cnt, rng, B):
    F = len(fam_sum)
    pick = rng.integers(0, F, size=(B, F))
    cnt = fam_cnt[pick].sum(1)
    ok = cnt > 0
    means = np.sort(fam_sum[pick].sum(1)[ok] / cnt[ok])
    n = len(means)
    return means[int(0.025 * n)], means[int(0.975 * n)]


def simulate(scen, F, m, q, R, B, seed, s1):
    rng = np.random.default_rng(seed)
    fam_names = sorted(s1)
    pooled = [x for f in fam_names for x in s1[f]]
    out = {"positive": 0, "refuted": 0, "negative_sig": 0, "inconclusive": 0, "mean_n": 0.0, "mcnemar_only": 0}
    for _ in range(R):
        fam_sum, fam_cnt, b_tot, c_tot = np.zeros(F), np.zeros(F), 0, 0
        for f in range(F):
            src = pooled if scen == "A" else s1[fam_names[rng.integers(0, len(fam_names))]]
            n = rng.binomial(m, q)
            for _ in range(n):
                h, c = src[rng.integers(0, len(src))]
                if scen == "N" and rng.random() < 0.5:
                    h, c = c, h
                fam_sum[f] += h - c
                fam_cnt[f] += 1
                b_tot += h and not c
                c_tot += c and not h
        out["mean_n"] += fam_cnt.sum() / R
        p = mcnemar_p(b_tot, c_tot)
        lo, hi = cluster_ci(fam_sum, fam_cnt, rng, B)
        out["mcnemar_only"] += p < 0.05 and b_tot > c_tot
        if p < 0.05 and lo > 0:
            out["positive"] += 1
        elif p < 0.05 and hi < 0:
            out["negative_sig"] += 1
        elif hi < S1_EFFECT:
            out["refuted"] += 1
        else:
            out["inconclusive"] += 1
    return {k: (round(v / R, 3) if k != "mean_n" else round(v, 1)) for k, v in out.items()}


DESIGN = {"W1": {"families": ["compress", "downscale", "trim", "upscale"], "invertible_share": 7 / 11},
          "W2": {"families": ["dmirror", "cmirror", "rot90", "rot270"], "invertible_share": 3 / 9},
          "W3": {"families": ["hupscale", "vupscale", "switch"], "invertible_share": 7 / 13}}
P_HOLE = {"T1": 3.5 / 4, "inv": 5.5 / 6, "noninv": 0.5 / 4}
P_C7M = {"route": 4.5 / 6, "none": 1.5 / 7}


def simulate_design(m, q, R, B, seed, route_families):
    """Clusters as in the decision rule: W2's four families form one cluster."""
    rng = np.random.default_rng(seed)
    fams = [(w, f) for w, d in DESIGN.items() for f in d["families"]]
    cl_of = {(w, f): ("W2" if w == "W2" else f"{w}:{f}") for w, f in fams}
    cl_ids = sorted(set(cl_of.values()))
    kinds = ["T1", "T2", "T3"] * (m // 3) + ["T1", "T2", "T3"][:m % 3]
    out = {"positive": 0, "refuted": 0, "negative_sig": 0, "inconclusive": 0, "mean_n": 0.0, "mcnemar_only": 0}
    for _ in range(R):
        F = len(cl_ids)
        fam_sum, fam_cnt, b_tot, c_tot = np.zeros(F), np.zeros(F), 0, 0
        for (w, f) in fams:
            i = cl_ids.index(cl_of[(w, f)])
            pc = P_C7M["route" if f in route_families else "none"]
            for k in kinds:
                if rng.random() >= q:
                    continue
                if k == "T1":
                    ph = P_HOLE["T1"]
                else:
                    ph = P_HOLE["inv"] if rng.random() < DESIGN[w]["invertible_share"] else P_HOLE["noninv"]
                h, c = int(rng.random() < ph), int(rng.random() < pc)
                fam_sum[i] += h - c
                fam_cnt[i] += 1
                b_tot += h and not c
                c_tot += c and not h
        out["mean_n"] += fam_cnt.sum() / R
        p = mcnemar_p(b_tot, c_tot)
        lo, hi = cluster_ci(fam_sum, fam_cnt, rng, B)
        out["mcnemar_only"] += p < 0.05 and b_tot > c_tot
        if p < 0.05 and lo > 0:
            out["positive"] += 1
        elif p < 0.05 and hi < 0:
            out["negative_sig"] += 1
        elif hi < S1_EFFECT:
            out["refuted"] += 1
        else:
            out["inconclusive"] += 1
    return {k: (round(v / R, 3) if k != "mean_n" else round(v, 1)) for k, v in out.items()}


#: the planned families per cluster under the dependence-aware rule: W1 four clusters, W2 ONE cluster (its four
#: families are linked), W3 three clusters
CLUSTERS = [1, 1, 1, 1, 4, 1, 1, 1]


def simulate_clustered(scen, m, q, R, B, seed, s1, clusters=CLUSTERS):
    """Scenarios A, B and N as in simulate(), with the bootstrap over the design's clusters (W2's four families
    in one) instead of over families; the decision rule of PROTOCOL.md section 6 (revision 2)."""
    rng = np.random.default_rng(seed)
    fam_names = sorted(s1)
    pooled = [x for f in fam_names for x in s1[f]]
    out = {"positive": 0, "refuted": 0, "negative_sig": 0, "inconclusive": 0, "mean_n": 0.0, "mcnemar_only": 0}
    K = len(clusters)
    for _ in range(R):
        cl_sum, cl_cnt, b_tot, c_tot = np.zeros(K), np.zeros(K), 0, 0
        for k, nf in enumerate(clusters):
            for _ in range(nf):
                src = pooled if scen == "A" else s1[fam_names[rng.integers(0, len(fam_names))]]
                n = rng.binomial(m, q)
                for _ in range(n):
                    h, c = src[rng.integers(0, len(src))]
                    if scen == "N" and rng.random() < 0.5:
                        h, c = c, h
                    cl_sum[k] += h - c
                    cl_cnt[k] += 1
                    b_tot += h and not c
                    c_tot += c and not h
        out["mean_n"] += cl_cnt.sum() / R
        p = mcnemar_p(b_tot, c_tot)
        lo, hi = cluster_ci(cl_sum, cl_cnt, rng, B)
        out["mcnemar_only"] += p < 0.05 and b_tot > c_tot
        if p < 0.05 and lo > 0:
            out["positive"] += 1
        elif p < 0.05 and hi < 0:
            out["negative_sig"] += 1
        elif hi < S1_EFFECT:
            out["refuted"] += 1
        else:
            out["inconclusive"] += 1
    return {k: (round(v / R, 3) if k != "mean_n" else round(v, 1)) for k, v in out.items()}


def main_clustered(out_path, q=11 / 12, R=4000, B=2000, ms=(8, 9)):
    s1 = s1_tasks()
    res = {"rule": "dependence-aware: 8 clusters (W2's four families as one)", "clusters": CLUSTERS,
           "s1_families": s1, "q_motivating": q, "R": R, "B": B, "rows": []}
    for m in ms:
        for scen in ("A", "B", "N"):
            r = simulate_clustered(scen, m, q, R, B, seed=5000 + 10 * m + ord(scen), s1=s1)
            row = {"scenario": scen, "clusters": len(CLUSTERS), "families": sum(CLUSTERS), "m_per_family": m} | r
            res["rows"].append(row)
            print(json.dumps(row), flush=True)
            E.dump(out_path, res)


def main_design(out_path, route_families, q, R=4000, B=2000):
    res = {"scenario": "C", "route_families": route_families, "q_motivating": q, "R": R, "B": B, "rows": []}
    for m in (3, 6, 9):
        r = simulate_design(m, q, R, B, seed=7000 + m, route_families=route_families)
        row = {"scenario": "C", "families": sum(len(d["families"]) for d in DESIGN.values()), "m_per_family": m} | r
        res["rows"].append(row)
        print(json.dumps(row), flush=True)
        E.dump(out_path, res)


def main(out_path, q=11 / 12, R=4000, B=2000, Fs=(12, 14), ms=(3, 4, 5, 6, 7)):
    s1 = s1_tasks()
    res = {"s1_families": {f: v for f, v in s1.items()}, "q_motivating": q, "R": R, "B": B, "rows": []}
    for F in Fs:
        for m in ms:
            for scen in ("A", "B", "N"):
                r = simulate(scen, F, m, q, R, B, seed=1000 * F + 10 * m + ord(scen), s1=s1)
                row = {"scenario": scen, "families": F, "m_per_family": m} | r
                res["rows"].append(row)
                print(json.dumps(row), flush=True)
                E.dump(out_path, res)


if __name__ == "__main__":
    if sys.argv[1] == "committed":
        committed_check(sys.argv[2])
    elif sys.argv[1] == "clustered":
        # python -m cas.power clustered OUT.json [Q]      (the decision rule's 8 clusters; m = 8 and 9)
        main_clustered(sys.argv[2], *(float(a) for a in sys.argv[3:4]))
    elif sys.argv[1] == "design":
        # python -m cas.power design OUT.json Q FAMILY,FAMILY,...   (families with a G0 route at matched-search depth)
        main_design(sys.argv[2], [f for f in sys.argv[4].split(",") if f], float(sys.argv[3]))
    elif sys.argv[1] == "families":
        # python -m cas.power families OUT.json Q F,F,... [m,m,...]   (scenarios A, B, N for these family counts)
        ms = tuple(int(x) for x in sys.argv[5].split(",")) if len(sys.argv) > 5 else (4, 5, 6, 7)
        main(sys.argv[2], float(sys.argv[3]), Fs=tuple(int(x) for x in sys.argv[4].split(",")), ms=ms)
    else:
        main(sys.argv[1], *(float(a) for a in sys.argv[2:3]))
