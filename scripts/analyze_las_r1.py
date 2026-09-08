"""LAS-R1 analysis. Frozen and committed BEFORE any replication outcome exists.

Applies the pre-declared decision rule from the LAS-R1 freeze without
modification. Reads rows only; computes nothing that could change the rule.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "tti" / "las_r1"
FROZEN = json.loads((OUT / "frozen.json").read_text())
RULE = FROZEN["decision_rule"]
PRIMARY = ["A_ordinary", "B_concrete", "C_R1", "D_R2", "E_LAS"]


def load_rows():
    rows = defaultdict(dict)
    for line in (OUT / "rows.jsonl").read_text().splitlines():
        if line.strip():
            row = json.loads(line)
            rows[row["policy"]][row["target"]] = row
    return rows


def heldout_vector(rows, policy, targets):
    return np.array([1 if rows[policy][t].get("heldout_correct") else 0 for t in targets])


def paired_bootstrap(a: np.ndarray, b: np.ndarray, resamples: int, seed: int):
    """Percentile interval on the paired difference in success COUNTS."""
    rng = np.random.default_rng(seed)
    n = len(a)
    diffs = np.empty(resamples)
    for index in range(resamples):
        pick = rng.integers(0, n, n)
        diffs[index] = (a[pick].sum() - b[pick].sum())
    return float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5)), diffs


def exact_mcnemar(a: np.ndarray, b: np.ndarray):
    """Two-sided exact binomial test on discordant pairs."""
    b_only = int(np.sum((a == 1) & (b == 0)))
    c_only = int(np.sum((a == 0) & (b == 1)))
    n = b_only + c_only
    if n == 0:
        return b_only, c_only, 1.0
    k = min(b_only, c_only)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) / (2 ** n)
    return b_only, c_only, min(1.0, 2 * tail)


def compare(rows, targets, policy, comparator, resamples, seed):
    a = heldout_vector(rows, policy, targets)
    b = heldout_vector(rows, policy=comparator, targets=targets)
    low, high, _ = paired_bootstrap(a, b, resamples, seed)
    wins, losses, p = exact_mcnemar(a, b)
    return {"policy": policy, "comparator": comparator,
            "policy_heldout": int(a.sum()), "comparator_heldout": int(b.sum()),
            "difference": int(a.sum() - b.sum()),
            "policy_wins": wins, "comparator_wins": losses,
            "both_correct": int(np.sum((a == 1) & (b == 1))),
            "both_wrong": int(np.sum((a == 0) & (b == 0))),
            "bootstrap_ci_95": [round(low, 3), round(high, 3)],
            "ci_lower_above_zero": low > 0,
            "exact_mcnemar_two_sided_p": round(p, 6)}


def main() -> dict:
    rows = load_rows()
    targets = sorted(rows["A_ordinary"])
    complete = [p for p in PRIMARY if len(rows.get(p, {})) == len(targets)]
    if len(complete) != len(PRIMARY):
        raise SystemExit(f"incomplete primary policies: {set(PRIMARY) - set(complete)}")
    boot = RULE["bootstrap"]
    report = {"targets": len(targets), "decision_rule": RULE}

    #  ---- per-policy descriptive table ----
    summary = {}
    for policy in PRIMARY:
        prows = [rows[policy][t] for t in targets]
        fits = [r for r in prows if r["solved"]]
        summary[policy] = {
            "demonstration_fits": len(fits),
            "heldout_correct": sum(1 for r in fits if r.get("heldout_correct")),
            "wrong_but_demo_consistent": sum(1 for r in fits
                                             if r.get("wrong_but_demo_consistent")),
            "undefined": sum(1 for r in fits if r.get("undefined")),
            "budget_exhausted": sum(1 for r in prows if not r["solved"]),
            "exact_ast": sum(1 for r in fits if r.get("exact_ast_recovered")),
            "prior_phase_fits": sum(1 for r in fits if r["phase"] == "prior"),
            "fallback_fits": sum(1 for r in fits if r["phase"] == "fallback"),
            "total_units": sum(r["units"] for r in prows),
            "mean_units": round(sum(r["units"] for r in prows) / len(prows), 1),
            "prior_seconds": round(sum(r["prior_seconds"] for r in prows), 1),
            "fallback_seconds": round(sum(r["fallback_seconds"] for r in prows), 1),
            "total_seconds": round(sum(r["seconds"] for r in prows), 1)}
    report["summary"] = summary

    #  ---- primary and secondary paired comparisons ----
    report["primary"] = compare(rows, targets, "E_LAS", "B_concrete",
                                boot["resamples"], boot["seed"])
    report["secondary"] = [compare(rows, targets, "E_LAS", c, boot["resamples"], boot["seed"])
                           for c in ("A_ordinary", "C_R1", "D_R2")]

    #  ---- the pre-declared verdict ----
    primary = report["primary"]
    replicated = primary["difference"] > 0 and primary["ci_lower_above_zero"]
    report["verdict"] = "ROBUSTLY REPLICATED" if replicated else "NOT ROBUSTLY REPLICATED"
    report["verdict_basis"] = {
        "difference_positive": primary["difference"] > 0,
        "ci_lower_bound_above_zero": primary["ci_lower_above_zero"],
        "rule": RULE["verdict_ROBUSTLY_REPLICATED_iff"]}

    #  ---- matched-null distribution ----
    null_names = sorted(p for p in rows if p.startswith("NULL_"))
    nulls = [n for n in null_names if len(rows[n]) == len(targets)]
    if nulls:
        las_heldout = summary["E_LAS"]["heldout_correct"]
        las_units = summary["E_LAS"]["total_units"]
        dist = []
        for name in nulls:
            nrows = [rows[name][t] for t in targets]
            fits = [r for r in nrows if r["solved"]]
            dist.append({
                "control": name,
                "heldout_correct": sum(1 for r in fits if r.get("heldout_correct")),
                "demonstration_fits": len(fits),
                "wrong_but_demo_consistent": sum(1 for r in fits
                                                 if r.get("wrong_but_demo_consistent")),
                "undefined": sum(1 for r in fits if r.get("undefined")),
                "total_units": sum(r["units"] for r in nrows),
                "prior_phase_fits": sum(1 for r in fits if r["phase"] == "prior"),
                "fallback_fits": sum(1 for r in fits if r["phase"] == "fallback"),
                "total_seconds": round(sum(r["seconds"] for r in nrows), 1)})
        beaten = sum(1 for d in dist if las_heldout > d["heldout_correct"])
        cheaper = sum(1 for d in dist if las_units < d["total_units"])
        values = sorted(d["heldout_correct"] for d in dist)
        report["matched_null"] = {
            "controls_complete": len(nulls),
            "las_heldout": las_heldout,
            "null_heldout_min": values[0], "null_heldout_max": values[-1],
            "null_heldout_mean": round(sum(values) / len(values), 2),
            "null_heldout_median": values[len(values) // 2],
            "controls_strictly_beaten_by_las": beaten,
            "criterion_at_least_31_of_32": beaten >= 31,
            "las_units": las_units,
            "controls_more_expensive_than_las": cheaper,
            "distribution": dist}
    else:
        report["matched_null"] = {"controls_complete": 0,
                                 "note": "null controls not run or incomplete"}

    #  ---- per-family, descriptive only ----
    families = sorted({rows["A_ordinary"][t]["family"] for t in targets})
    report["per_family"] = {}
    for family in families:
        ftargets = [t for t in targets if rows["A_ordinary"][t]["family"] == family]
        report["per_family"][family] = {
            "targets": len(ftargets),
            **{p: {"heldout": sum(1 for t in ftargets
                                  if rows[p][t].get("heldout_correct")),
                   "fits": sum(1 for t in ftargets if rows[p][t]["solved"]),
                   "units": sum(rows[p][t]["units"] for t in ftargets)}
               for p in PRIMARY}}
    report["per_family_note"] = RULE["family_stratification"]

    #  ---- bounded search-reach witnesses ----
    witnesses = []
    for t in targets:
        ordinary, las = rows["A_ordinary"][t], rows["E_LAS"][t]
        if not ordinary["solved"] and las["solved"]:
            witnesses.append({"target": t, "family": ordinary["family"],
                              "las_units": las["units"],
                              "las_heldout_correct": las.get("heldout_correct"),
                              "las_phase": las["phase"], "las_source": las["source"]})
    report["bounded_search_reach_witnesses"] = {
        "count": len(witnesses), "detail": witnesses,
        "label": "BOUNDED SEARCH-REACH WITNESS",
        "not_a_claim_of": ["semantic expressivity gain", "Level-3B",
                           "semantic invention"]}

    #  ---- discordance detail ----
    def discord(policy, comparator):
        return {
            f"{policy}_correct_{comparator}_wrong":
                [t for t in targets if rows[policy][t].get("heldout_correct")
                 and not rows[comparator][t].get("heldout_correct")],
            f"{comparator}_correct_{policy}_wrong":
                [t for t in targets if rows[comparator][t].get("heldout_correct")
                 and not rows[policy][t].get("heldout_correct")]}
    report["discordance"] = {"vs_ordinary": discord("E_LAS", "A_ordinary"),
                             "vs_concrete": discord("E_LAS", "B_concrete")}

    text = json.dumps(report, indent=1, sort_keys=True, default=str)
    (OUT / "analysis.json").write_text(text)
    (OUT / "analysis_hash.txt").write_text(hashlib.sha256(text.encode()).hexdigest() + "\n")
    return report


if __name__ == "__main__":
    result = main()
    print(f"targets {result['targets']}")
    print(f"\n{'policy':14}{'fit':>6}{'heldout':>9}{'wrong':>7}{'undef':>7}"
          f"{'exhaust':>9}{'prior':>7}{'units':>10}")
    for policy in PRIMARY:
        s = result["summary"][policy]
        print(f"{policy:14}{s['demonstration_fits']:>6}{s['heldout_correct']:>9}"
              f"{s['wrong_but_demo_consistent']:>7}{s['undefined']:>7}"
              f"{s['budget_exhausted']:>9}{s['prior_phase_fits']:>7}{s['total_units']:>10}")
    p = result["primary"]
    print(f"\nPRIMARY  LAS {p['policy_heldout']} vs CONCRETE {p['comparator_heldout']} "
          f"| diff {p['difference']} | 95% CI {p['bootstrap_ci_95']} "
          f"| McNemar wins {p['policy_wins']}/{p['comparator_wins']} p={p['exact_mcnemar_two_sided_p']}")
    for s in result["secondary"]:
        print(f"  vs {s['comparator']:12} diff {s['difference']:+3} CI {s['bootstrap_ci_95']} "
              f"p={s['exact_mcnemar_two_sided_p']}")
    mn = result["matched_null"]
    if mn.get("controls_complete"):
        print(f"\nMATCHED NULL: LAS {mn['las_heldout']} beats {mn['controls_strictly_beaten_by_las']}"
              f"/{mn['controls_complete']} controls (need 31) | null range "
              f"{mn['null_heldout_min']}-{mn['null_heldout_max']} mean {mn['null_heldout_mean']}")
    print(f"\nreach witnesses: {result['bounded_search_reach_witnesses']['count']}")
    print(f"\nVERDICT: {result['verdict']}")
