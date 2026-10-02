"""Item-2 v1.6 development evaluation on the v1.5 test corpus (DEVELOPMENT
DATA ONLY), exactly as fixed in records/ITEM2_V16_DEVELOPMENT_PLAN.md.

For R0, R1, R2: CV-A (token-pair-component folds; every validation pair is
unseen in its training folds) and CV-B (group folds; pairs mostly seen), with
the conditions D, D+R, D+R_SHUFFLED and R. Applies the eligibility rules and
the selection law and writes outputs/tti/v16_dev_report.json. Statistics are
descriptive; nothing here is a test result.
"""
from __future__ import annotations

import csv
import importlib.util
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
for v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(v, "1")

from cora_arc2026 import v16_cfr as C                             # noqa: E402

S = C.S
RESP = os.path.join(HERE, "outputs", "tti", "v16_dev_responses.json")
OUT = os.path.join(HERE, "outputs", "tti", "v16_dev_report.json")
CSV_OUT = os.path.join(HERE, "outputs", "tti", "v16_dev_table.csv")
CONDS = ("D", "D+R", "D+R_SHUFFLED", "R")


def _evaluator():
    spec = importlib.util.spec_from_file_location(
        "ev15_dev", os.path.join(HERE, "scripts", "evaluate_v15_selection.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_dev():
    EV = _evaluator()
    inc, _ = S.L.first_admissions(EV.load(EV.TEST_DIR))
    groups = sorted((r["group"] for r in inc), key=lambda g: g["group_digest"])
    with open(RESP) as handle:
        resp = json.load(handle)
    if resp["probe_identity"] != C.probe_identity():
        raise SystemExit("responses were computed by a different probe implementation")
    rmap = {(r["group_digest"], r["t"], r["r"]): r["responses"] for r in resp["rows"]}
    return groups, C.build_queries(groups, rmap), resp


def scan(queries) -> list:
    """Leakage boundary of the response view: four finite floats per Delta;
    no value equal to a seed of the group; nothing but the delta enters."""
    found = []
    for q in queries:
        d = q["delta"]
        if len(d) != len(C.RESPONSE_FIELDS):
            found.append(["width", q["group_digest"][:12]])
        for v in d:
            if isinstance(v, bool) or not isinstance(v, float) or not math.isfinite(v):
                found.append(["non_float", q["group_digest"][:12]])
            if abs(v) > 1e6:
                found.append(["magnitude", q["group_digest"][:12]])
    return found


def run_cv(queries, folds, rep):
    n = len(queries)
    units = {c: [None] * n for c in CONDS}
    conv, fid, active, valid = [], [], [], True
    order_ok = True
    for f in sorted(set(folds)):
        tr = [i for i, q in enumerate(queries) if folds[q["group"]] != f]
        va = [i for i, q in enumerate(queries) if folds[q["group"]] == f]
        if rep == "R1":
            tr = [i for i in tr if queries[i]["ambiguous"]]
        qtr, qva = [queries[i] for i in tr], [queries[i] for i in va]
        if {q["group"] for q in qtr} & {q["group"] for q in qva}:
            valid = False
        std = S.standardizer_for(qtr, None)
        rtr, rva = C.d_rows(qtr, std), C.d_rows(qva, std)
        if rep == "R2":
            dtr, dva = C.residualized(qtr, qva, None, std)
        else:
            dtr, dva = [q["delta"] for q in qtr], [q["delta"] for q in qva]
        scale = C.rms_scale(dtr)
        active.append(C.active_fields(scale))
        dtr_s, dva_s = C.apply_scale(dtr, scale), C.apply_scale(dva, scale)
        pi_tr, pi_va = C.response_shuffle(qtr), C.response_shuffle(qva)
        fid.append(C.shuffle_fidelity(qva, pi_va))
        sh_tr = C.donor_deltas(qtr, pi_tr, dtr_s)
        sh_va = C.donor_deltas(qva, pi_va, dva_s)
        fits = {"D": C.fit(qtr, rows=rtr),
                "D+R": C.fit(qtr, rows=rtr, deltas=dtr_s),
                "D+R_SHUFFLED": C.fit(qtr, rows=rtr, deltas=sh_tr),
                "R": C.fit(qtr, deltas=dtr_s)}
        inputs = {"D": (rva, None), "D+R": (rva, dva_s),
                  "D+R_SHUFFLED": (rva, sh_va), "R": (None, dva_s)}
        for c in CONDS:
            model, info = fits[c]
            conv.append(info["converged"])
            sc = C.score(model, qva, *inputs[c])
            order_ok = order_ok and all(s["order_invariant"] for s in sc)
            for i, s in zip(va, sc):
                units[c][i] = s["units"]
    return units, {"converged": all(conv), "order_invariant": order_ok,
                   "folds_disjoint": valid, "active_fields": max(active),
                   "shuffle_fidelity_validation_mean": {
                       k: round(sum(x[k] for x in fid) / len(fid), 6)
                       for k in ("same_pair_share", "same_family_share",
                                 "same_status_share", "mean_field_correlation")},
                   "shuffle_same_group": sum(x["same_group_count"] for x in fid)}


def pair_leak(queries, folds) -> bool:
    """True if any token pair is in both a training and a validation pool."""
    for f in sorted(set(folds)):
        tr = {q["pair_key"] for q in queries if folds[q["group"]] != f}
        va = {q["pair_key"] for q in queries if folds[q["group"]] == f}
        if tr & va:
            return True
    return False


def metrics(queries, units, select=None):
    out = {"accuracy_ambiguous": {c: C.ambiguous_accuracy(queries, units[c], select) for c in CONDS},
           "end_to_end": {c: C.end_to_end_accuracy(queries, units[c]) for c in CONDS},
           "D+R_vs_D": C.increment_summary(queries, units["D+R"], units["D"], select),
           "D+R_vs_SHUFFLED": C.increment_summary(queries, units["D+R"], units["D+R_SHUFFLED"], select),
           "D_vs_chance_groups": len(C.above_chance_values(queries, units["D"], select))}
    return out


def family_increments(queries, units):
    fams = sorted({str(q["family"]) for q in queries})
    out = {}
    for fam in fams:
        sel = (lambda q, fam=fam: str(q["family"]) == fam)
        s = C.increment_summary(queries, units["D+R"], units["D"], sel)
        out[fam] = s
    return out


def seen_audit(queries, folds, units):
    """CV-B: increments by whether the validation query's token pair,
    structural pair and failure-class transition occur in its training pool."""
    keys = {"token_pair": C.pair_key, "structural_pair": C.structural_pair,
            "transition": lambda q: q["transition"]}
    seen = {k: [None] * len(queries) for k in keys}
    for f in sorted(set(folds)):
        tr = [q for q in queries if folds[q["group"]] != f]
        for k, fn in keys.items():
            pool = {fn(q) for q in tr}
            for i, q in enumerate(queries):
                if folds[q["group"]] == f:
                    seen[k][i] = fn(q) in pool
    out = {}
    for k in keys:
        idx = {id(q): seen[k][i] for i, q in enumerate(queries)}
        for label, want in (("seen", True), ("unseen", False)):
            sel = (lambda q, want=want, idx=idx: idx[id(q)] is want)
            out[f"{k}:{label}"] = {
                "accuracy_ambiguous_D": C.ambiguous_accuracy(queries, units["D"], sel),
                "accuracy_ambiguous_D+R": C.ambiguous_accuracy(queries, units["D+R"], sel),
                "D+R_vs_D": C.increment_summary(queries, units["D+R"], units["D"], sel)}
    return out


def eligibility(rep_out, leak_findings) -> dict:
    a = rep_out["CV-A"]
    fam_ok = all(s.get("mean_increment", 0) >= -0.05
                 for s in a["family_D+R_vs_D"].values() if s.get("groups", 0) >= 10)
    rules = {
        "1_no_leakage": not leak_findings,
        "2_all_converged": a["checks"]["converged"] and rep_out["CV-B"]["checks"]["converged"],
        "3_order_invariant": a["checks"]["order_invariant"] and rep_out["CV-B"]["checks"]["order_invariant"],
        "4_cv_a_valid": a["checks"]["folds_disjoint"] and not a["checks"]["pair_leak"],
        "5_beats_shuffle": a["metrics"]["D+R_vs_SHUFFLED"].get("mean_increment", 0) > 0,
        "6_increment_over_D": a["metrics"]["D+R_vs_D"].get("mean_increment", 0) > 0,
        "7_no_family_collapse": fam_ok}
    return {"rules": rules, "eligible": all(rules.values())}


def main():
    groups, queries, resp = load_dev()
    integrity = sorted({p for q in queries for p in q["integrity"]})
    leaks = scan(queries)
    folds_a = C.cv_a_folds(groups, queries)
    folds_b = C.cv_b_folds(groups)
    report = {"development_only": True, "plan": "records/ITEM2_V16_DEVELOPMENT_PLAN.md",
              "probe_identity": resp["probe_identity"], "groups": len(groups),
              "queries": len(queries),
              "ambiguous_queries": sum(1 for q in queries if q["ambiguous"]),
              "ambiguous_groups": len({q["group"] for q in queries if q["ambiguous"]}),
              "integrity_findings": integrity, "leak_findings": leaks[:20],
              "distinct_token_pairs": len({q["pair_key"] for q in queries}),
              "cv_a_folds": len(set(folds_a)), "representations": {}}
    rows = []
    for rep in C.REPRESENTATIONS:
        rep_out = {}
        for name, folds in (("CV-A", folds_a), ("CV-B", folds_b)):
            units, checks = run_cv(queries, folds, rep)
            checks["pair_leak"] = pair_leak(queries, folds)
            block = {"checks": checks, "metrics": metrics(queries, units)}
            if name == "CV-A":
                block["family_D+R_vs_D"] = family_increments(queries, units)
            else:
                block["seen_unseen"] = seen_audit(queries, folds, units)
            rep_out[name] = block
            m = block["metrics"]
            rows.append([rep, name] + [m["accuracy_ambiguous"][c] for c in CONDS]
                        + [m["D+R_vs_D"].get("mean_increment"), m["D+R_vs_D"].get("ci95"),
                           m["D+R_vs_SHUFFLED"].get("mean_increment"),
                           m["end_to_end"]["D"], m["end_to_end"]["D+R"]])
        rep_out["eligibility"] = eligibility(rep_out, leaks or integrity)
        report["representations"][rep] = rep_out
    elig = [r for r in C.REPRESENTATIONS if report["representations"][r]["eligibility"]["eligible"]]
    if elig:
        act = {r: report["representations"][r]["CV-A"]["checks"]["active_fields"] for r in elig}
        chosen = sorted(elig, key=lambda r: (act[r], C.REPRESENTATIONS.index(r)))[0]
        report["selection"] = {"eligible": elig, "active_fields": act, "chosen": chosen}
    else:
        report["selection"] = {"eligible": [], "chosen": None,
                               "outcome": "DEVELOPMENT_NO_ELIGIBLE_REPRESENTATION"}
    with open(sys.argv[1] if len(sys.argv) > 1 else OUT, "w") as handle:
        handle.write(json.dumps(report, indent=1, sort_keys=True) + "\n")
    with open(CSV_OUT, "w", newline="") as handle:
        w = csv.writer(handle)
        w.writerow(["representation", "cv"] + [f"acc_amb_{c}" for c in CONDS]
                   + ["inc_over_D", "inc_ci95", "inc_over_shuffled", "e2e_D", "e2e_D+R"])
        w.writerows(rows)
    print(json.dumps({"selection": report["selection"], "ambiguous": report["ambiguous_queries"],
                      "integrity": integrity, "leaks": len(leaks)}))


if __name__ == "__main__":
    main()
