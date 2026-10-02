"""Item-2 v1.6 development evaluation on the v1.5 test corpus (DEVELOPMENT
DATA ONLY), exactly as fixed in records/ITEM2_V16_DEVELOPMENT_PLAN.md,
sections 1 to 13.

Arms: P0 PURE_CFR (deterministic rule, no fit), P0_then_D, P1 HYBRID_CFR
(D + response, R0/R1/R2), P2 PASSIVE_V15 (D + F_S7), D, F_S7 alone.
Controls: donor response (frontier replaced), swapped response (identity
destroyed). CV-A (token-pair-component folds; every validation pair unseen)
and CV-B (group folds; pairs mostly seen). Writes outputs/tti/v16_dev_report
.json and a CSV. Statistics are descriptive; nothing here is a test result.
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
#: conditions that depend on the representation
REP_CONDS = ("P1", "P1_SHUFFLED", "P1_SWAPPED", "R")
#: conditions shared by every representation
BASE_CONDS = ("D", "P0", "P0_SHUFFLED", "P0_SWAPPED", "P0_then_D", "P2", "F_S7")
CONDS = BASE_CONDS + REP_CONDS


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
    if not resp["state_restored_every_group"]:
        raise SystemExit("a probe did not restore state")
    rmap = {(r["group_digest"], r["t"], r["r"]): r["responses"] for r in resp["rows"]}
    return groups, C.build_queries(groups, rmap), resp


def scan(queries) -> list:
    """Leakage boundary of the response view: four finite floats per Delta."""
    found = []
    for q in queries:
        d = q["delta"]
        if len(d) != len(C.RESPONSE_FIELDS):
            found.append(["width", q["group_digest"][:12]])
        for v in d:
            if isinstance(v, bool) or not isinstance(v, float) or not math.isfinite(v):
                found.append(["non_float", q["group_digest"][:12]])
    return found


def run_cv(queries, folds, rep):
    n = len(queries)
    units = {c: [None] * n for c in CONDS}
    conv, fid, active, valid, order_ok = [], [], [], True, True
    for f in sorted(set(folds)):
        tr_all = [i for i, q in enumerate(queries) if folds[q["group"]] != f]
        va = [i for i, q in enumerate(queries) if folds[q["group"]] == f]
        tr = [i for i in tr_all if queries[i]["ambiguous"]] if rep == "R1" else tr_all
        qtr, qva, qtr_all = [queries[i] for i in tr], [queries[i] for i in va], [queries[i] for i in tr_all]
        if {q["group"] for q in qtr_all} & {q["group"] for q in qva}:
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
        sh_tr, sh_va = C.donor_deltas(qtr, pi_tr, dtr_s), C.donor_deltas(qva, pi_va, dva_s)
        sw_va = [[-v for v in d] for d in dva_s]
        raw_va = [q["delta"] for q in qva]
        raw_sh_va = C.donor_deltas(qva, pi_va, raw_va)
        raw_sw_va = [[-v for v in d] for d in raw_va]
        #  v1.5 passive arms on the same training resource
        std15 = S.standardizer_for(qtr_all, "F_S7")
        m_p2, i_p2 = S.fit_pairs(S.design(qtr_all, "D+F_ASSOC", std15), qtr_all)
        m_f, i_f = S.fit_pairs(S.design(qtr_all, "F_ASSOC", std15), qtr_all)
        fits = {"D": C.fit(qtr_all, rows=C.d_rows(qtr_all, S.standardizer_for(qtr_all, None))),
                "P1": C.fit(qtr, rows=rtr, deltas=dtr_s),
                "P1_SHUFFLED": C.fit(qtr, rows=rtr, deltas=sh_tr),
                "R": C.fit(qtr, deltas=dtr_s)}
        std_all = S.standardizer_for(qtr_all, None)
        rva_all = C.d_rows(qva, std_all)
        for c, (m, info) in fits.items():
            conv.append(info["converged"])
        conv += [i_p2["converged"], i_f["converged"]]
        sc = {"D": C.score(fits["D"][0], qva, rva_all, None),
              "P1": C.score(fits["P1"][0], qva, rva, dva_s),
              "P1_SHUFFLED": C.score(fits["P1_SHUFFLED"][0], qva, rva, sh_va),
              "P1_SWAPPED": C.score(fits["P1"][0], qva, rva, sw_va),
              "R": C.score(fits["R"][0], qva, None, dva_s),
              "P2": S.score_queries(m_p2, S.design(qva, "D+F_ASSOC", std15), qva),
              "F_S7": S.score_queries(m_f, S.design(qva, "F_ASSOC", std15), qva)}
        for c, rows in sc.items():
            order_ok = order_ok and all(s["order_invariant"] for s in rows)
            for i, s in zip(va, rows):
                units[c][i] = s["units"]
        for i, q, d, dsh, dsw in zip(va, qva, raw_va, raw_sh_va, raw_sw_va):
            units["P0"][i] = C.p0_units(q, d)
            units["P0_SHUFFLED"][i] = C.p0_units(q, dsh)
            units["P0_SWAPPED"][i] = C.p0_units(q, dsw)
            units["P0_then_D"][i] = C.p0_units(q, d, fallback_units=units["D"][i])
    return units, {"converged": all(conv), "order_invariant": order_ok,
                   "folds_disjoint": valid, "active_fields": max(active),
                   "shuffle_fidelity_validation_mean": {
                       k: round(sum(x[k] for x in fid) / len(fid), 6)
                       for k in ("same_pair_share", "same_family_share",
                                 "same_status_share", "mean_field_correlation")},
                   "shuffle_same_group": sum(x["same_group_count"] for x in fid)}


def pair_leak(queries, folds) -> bool:
    for f in sorted(set(folds)):
        tr = {q["pair_key"] for q in queries if folds[q["group"]] != f}
        va = {q["pair_key"] for q in queries if folds[q["group"]] == f}
        if tr & va:
            return True
    return False


def metrics(queries, units, select=None):
    inc = lambda a, b: C.increment_summary(queries, units[a], units[b], select)
    return {"accuracy_ambiguous": {c: C.ambiguous_accuracy(queries, units[c], select) for c in CONDS},
            "end_to_end": {c: C.end_to_end_accuracy(queries, units[c]) for c in CONDS},
            "P0_vs_D": inc("P0", "D"), "P0_vs_P0_SHUFFLED": inc("P0", "P0_SHUFFLED"),
            "P0_vs_P2": inc("P0", "P2"), "P0_then_D_vs_D": inc("P0_then_D", "D"),
            "P1_vs_D": inc("P1", "D"), "P1_vs_P1_SHUFFLED": inc("P1", "P1_SHUFFLED"),
            "P1_vs_P2": inc("P1", "P2"), "P2_vs_D": inc("P2", "D"),
            "P0_decided_share": round(sum(1 for q, u, d in zip(queries, units["P0"], units["D"])
                                          if q["ambiguous"] and (select is None or select(q))
                                          and C.p0_choice(q["delta"]) != 0)
                                      / max(1, sum(1 for q in queries if q["ambiguous"]
                                                   and (select is None or select(q)))), 6)}


def family_increments(queries, units, a, b):
    out = {}
    for fam in sorted({str(q["family"]) for q in queries}):
        sel = (lambda q, fam=fam: str(q["family"]) == fam)
        out[fam] = C.increment_summary(queries, units[a], units[b], sel)
    return out


def seen_audit(queries, folds, units):
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
                "accuracy_ambiguous": {c: C.ambiguous_accuracy(queries, units[c], sel)
                                       for c in ("D", "P0", "P1", "P2")},
                "P0_vs_D": C.increment_summary(queries, units["P0"], units["D"], sel),
                "P1_vs_D": C.increment_summary(queries, units["P1"], units["D"], sel)}
    return out


def eligibility(rep_out, findings) -> dict:
    """P1 representation eligibility, plan section 10."""
    a = rep_out["CV-A"]
    fam_ok = all(s.get("mean_increment", 0) >= -0.05
                 for s in a["family_P1_vs_D"].values() if s.get("groups", 0) >= 10)
    rules = {"1_no_leakage": not findings,
             "2_all_converged": a["checks"]["converged"] and rep_out["CV-B"]["checks"]["converged"],
             "3_order_invariant": a["checks"]["order_invariant"] and rep_out["CV-B"]["checks"]["order_invariant"],
             "4_cv_a_valid": a["checks"]["folds_disjoint"] and not a["checks"]["pair_leak"],
             "5_beats_shuffle": a["metrics"]["P1_vs_P1_SHUFFLED"].get("mean_increment", 0) > 0,
             "6_increment_over_D": a["metrics"]["P1_vs_D"].get("mean_increment", 0) > 0,
             "7_no_family_collapse": fam_ok}
    return {"rules": rules, "eligible": all(rules.values())}


def p0_development(queries, units_a, folds_a) -> dict:
    """P0 has nothing to select; this reports it and applies the one
    permitted development action: dropping a constant key."""
    deltas = [q["delta"] for q in queries]
    idx = {k: i for i, k in enumerate(C.RESPONSE_FIELDS)}
    constant = [k for k in C.P0_KEYS
                if all(abs(d[idx[k]]) <= C.P0_TOL for d, q in zip(deltas, queries) if q["ambiguous"])]
    fam = family_increments(queries, units_a, "P0", "D")
    return {"keys_in_order": list(C.P0_KEYS), "signs": list(C.P0_SIGNS),
            "constant_keys_dropped": constant,
            "key_diagnostics_ambiguous": C.p0_key_diagnostics(queries, deltas),
            "family_P0_vs_D": fam,
            "no_family_collapse": all(s.get("mean_increment", 0) >= -0.05
                                      for s in fam.values() if s.get("groups", 0) >= 10)}


def main():
    groups, queries, resp = load_dev()
    integrity = sorted({p for q in queries for p in q["integrity"]})
    leaks = scan(queries)
    folds_a, folds_b = C.cv_a_folds(groups, queries), C.cv_b_folds(groups)
    amb = [q for q in queries if q["ambiguous"]]
    report = {"development_only": True, "plan": "records/ITEM2_V16_DEVELOPMENT_PLAN.md",
              "probe_identity": resp["probe_identity"], "groups": len(groups),
              "queries": len(queries), "ambiguous_queries": len(amb),
              "ambiguous_groups": len({q["group"] for q in amb}),
              "ambiguous_by_family": {f: sum(1 for q in amb if str(q["family"]) == f)
                                      for f in sorted({str(q["family"]) for q in queries})},
              "transitions_ambiguous": sorted({q["transition"] for q in amb}),
              "integrity_findings": integrity, "leak_findings": leaks[:20],
              "distinct_token_pairs": len({q["pair_key"] for q in queries}),
              "heldout_pairs_rule": {"prefix": C.HELDOUT_PREFIX, "first_hex": C.HELDOUT_FIRST_HEX,
                                     "heldout_pairs": sorted({q["pair_key"] for q in queries if C.heldout_pair(q["pair_key"])}),
                                     "heldout_groups": len({q["group"] for q in queries if C.heldout_pair(q["pair_key"])})},
              "cv_a_folds": len(set(folds_a)), "representations": {}}
    rows = []
    for rep in C.REPRESENTATIONS:
        rep_out = {}
        for name, folds in (("CV-A", folds_a), ("CV-B", folds_b)):
            units, checks = run_cv(queries, folds, rep)
            checks["pair_leak"] = pair_leak(queries, folds)
            block = {"checks": checks, "metrics": metrics(queries, units)}
            if name == "CV-A":
                block["family_P1_vs_D"] = family_increments(queries, units, "P1", "D")
                if rep == "R0":
                    report["P0_development"] = p0_development(queries, units, folds_a)
            else:
                block["seen_unseen"] = seen_audit(queries, folds, units)
            rep_out[name] = block
            m = block["metrics"]
            rows.append([rep, name] + [m["accuracy_ambiguous"][c] for c in CONDS]
                        + [m["P0_vs_D"].get("mean_increment"), m["P1_vs_D"].get("mean_increment"),
                           m["P1_vs_P1_SHUFFLED"].get("mean_increment"), m["P2_vs_D"].get("mean_increment")])
        rep_out["eligibility"] = eligibility(rep_out, leaks or integrity)
        report["representations"][rep] = rep_out
    elig = [r for r in C.REPRESENTATIONS if report["representations"][r]["eligibility"]["eligible"]]
    if elig:
        act = {r: report["representations"][r]["CV-A"]["checks"]["active_fields"] for r in elig}
        chosen = sorted(elig, key=lambda r: (act[r], C.REPRESENTATIONS.index(r)))[0]
        report["P1_selection"] = {"eligible": elig, "active_fields": act, "chosen": chosen}
    else:
        report["P1_selection"] = {"eligible": [], "chosen": None,
                                  "outcome": "DEVELOPMENT_NO_ELIGIBLE_REPRESENTATION"}
    with open(sys.argv[1] if len(sys.argv) > 1 else OUT, "w") as handle:
        handle.write(json.dumps(report, indent=1, sort_keys=True) + "\n")
    with open(CSV_OUT, "w", newline="") as handle:
        w = csv.writer(handle)
        w.writerow(["representation", "cv"] + [f"acc_amb_{c}" for c in CONDS]
                   + ["P0_vs_D", "P1_vs_D", "P1_vs_shuffled", "P2_vs_D"])
        w.writerows(rows)
    a0 = report["representations"]["R0"]["CV-A"]["metrics"]
    print(json.dumps({"ambiguous": len(amb), "integrity": integrity, "leaks": len(leaks),
                      "P0_amb_acc": a0["accuracy_ambiguous"]["P0"], "D_amb_acc": a0["accuracy_ambiguous"]["D"],
                      "P2_amb_acc": a0["accuracy_ambiguous"]["P2"], "P0_vs_D": a0["P0_vs_D"],
                      "P1_selection": report["P1_selection"]}))


if __name__ == "__main__":
    main()
