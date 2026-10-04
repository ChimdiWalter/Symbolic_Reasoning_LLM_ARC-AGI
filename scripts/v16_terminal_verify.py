"""Item-2 v1.6 terminal verification (supplementary; written and committed
2026-10-04, before any prospective outcome existed).

Runs after the frozen post-generation runner writes logs/V16_POSTGEN_DONE.
It never changes a frozen artifact and records no verdict. It checks, in
order, and only then reads any scientific value:
  1. freeze: manifest hash file, protocol, implementation files, dependency
     trees, runtime versions (skipped only in synthetic tests);
  2. the three sealed reports are byte-identical, and their freeze,
     integrity, leakage and overlap lists are empty;
  3. the test responses: probe and fitter identities, state restoration,
     the order recheck, and the binding hash recomputed here from the
     corpus files;
  4. the corpus: contiguous slots, freeze_ok on every record, no excluded or
     repeated digest, test digests disjoint from the development digests;
  5. an independent recomputation of the primary arm P0 and the second arm
     P0_then_D from the raw responses: its own presentation order, its own
     P0 rule, its own conditional-logit fit of D (on the frozen D_RICH
     feature extraction), its own exact sign-flip test, interval and
     ladder. Gate C reuses the frozen donor matching. P1 is checked for
     internal gate arithmetic only; if the class depends on P1, a session
     recheck is required and flagged.
Writes outputs/tti/v16_terminal_verification.json, a result table (CSV) and
figure-ready data, and the marker logs/V16_TERMINAL_VERIFIED or
logs/V16_TERMINAL_DISCREPANCY.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import re
import sys
from fractions import Fraction

for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_v] = "1"

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

#  the order and signs the protocol fixes for P0, restated here independently
P0_ORDER = ("loo_exact", "loo_cell_error", "loo_fit_fail", "table_entries")
P0_SIGN = {"loo_exact": 1, "loo_cell_error": -1, "loo_fit_fail": -1, "table_entries": -1}
FIELDS = ("loo_exact", "loo_fit_fail", "loo_cell_error", "table_entries")
TOL = 1e-9
TIE = 1e-12
LAMBDA = 0.01
RECORD = re.compile(r"^full(\d{5})\.json$")
PASS = {"P0": ("PURE_CFR_SELECTION_GENERALIZES", "PURE_CFR_FAMILIAR_PAIRS_ONLY"),
        "P0_then_D": ("PURE_RULE_WITH_DEMONSTRATION_FALLBACK_GENERALIZES",
                      "PURE_RULE_WITH_DEMONSTRATION_FALLBACK_FAMILIAR_PAIRS_ONLY"),
        "P1": ("HYBRID_CFR_SELECTION_GENERALIZES", "HYBRID_CFR_FAMILIAR_PAIRS_ONLY")}
GATED = ("P0", "P0_then_D", "P1")


def default_cfg():
    t = os.path.join(HERE, "outputs", "tti")
    return {"manifest": os.path.join(t, "candidate_failure_response_v16_manifest.json"),
            "protocol": os.path.join(HERE, "docs", "CORA_TTI_CANDIDATE_FAILURE_RESPONSE_v1.6.md"),
            "dev_dir": os.path.join(t, "v15_test_corpus"), "test_dir": os.path.join(t, "v16_test_corpus"),
            "dev_resp": os.path.join(t, "v16_dev_responses.json"),
            "test_resp": os.path.join(t, "v16_test_responses.json"),
            "exclusion": os.path.join(t, "v16_exclusion_digests.json"),
            "reports": [os.path.join(t, f"v16_cfr_report{s}.json") for s in ("", "_pass1", "_pass2")],
            "out": os.path.join(t, "v16_terminal_verification.json"),
            "csv": os.path.join(t, "v16_result_table.csv"),
            "figure": os.path.join(t, "v16_result_figure_data.json"),
            "marker_dir": os.path.join(HERE, "logs"), "test_base": 500_000_000,
            "skip_freeze": False}


def sha(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def records(dirname):
    out = []
    for n in sorted(x for x in os.listdir(dirname) if RECORD.match(x)):
        p = os.path.join(dirname, n)
        with open(p) as handle:
            r = json.load(handle)
        r["_sha"] = sha(p)
        out.append(r)
    return out


def first_admissions(recs):
    seen, groups = set(), []
    for r in sorted(recs, key=lambda r: r["slot"]):
        if r.get("admitted") and r["group"]["group_digest"] not in seen:
            seen.add(r["group"]["group_digest"])
            groups.append(r["group"])
    return sorted(groups, key=lambda g: g["group_digest"])


def binding(recs):
    adm = sorted((r for r in recs if r.get("admitted")), key=lambda r: r["slot"])
    return hashlib.sha256("".join(r["_sha"] for r in adm).encode()).hexdigest()


def differing(tokens_a, tokens_b):
    ta, tb = [tuple(t) for t in tokens_a], [tuple(t) for t in tokens_b]
    d = [i for i, (x, y) in enumerate(zip(ta, tb)) if x != y]
    if len(d) != 1 or len(ta) != len(tb):
        raise ValueError("pair must differ in exactly one token")
    return ta[d[0]], tb[d[0]]


def own_queries(groups, rmap):
    """Queries rebuilt here: presentation, truth, pair key, ambiguity, Delta."""
    out = []
    for gi, g in enumerate(groups):
        by = {(e["target_index"], e["replicate_index"]): e for e in g["episodes"]}
        ca, cb = differing(by[(0, 0)]["target_tokens"], by[(1, 0)]["target_tokens"])
        pk = json.dumps(sorted([list(ca), list(cb)]))
        for e in sorted(g["episodes"], key=lambda x: (x["target_index"], x["replicate_index"])):
            key = hashlib.sha256(json.dumps(e["demonstrations"], sort_keys=True).encode()).hexdigest()
            first, second = sorted((ca, cb), key=lambda t: hashlib.sha256(
                f"v15-cand|{key}|{json.dumps(list(t))}".encode()).hexdigest())
            er = rmap[(g["group_digest"], e["target_index"], e["replicate_index"])]
            role = {ca: "anchor", cb: "contrast"}
            rf, rs = er[role[first]]["response"], er[role[second]]["response"]
            out.append({"group": gi, "group_digest": g["group_digest"], "pair_key": pk,
                        "family": g.get("anchor_family"), "t": e["target_index"], "r": e["replicate_index"],
                        "cands": (first, second), "truth": ca if e["target_index"] == 0 else cb,
                        "ambiguous": bool(er["anchor"]["fits_all"] and er["contrast"]["fits_all"]),
                        "delta": [round(rf[k] - rs[k], 12) for k in FIELDS]})
    return out


def p0_decision(delta, keys):
    idx = {k: i for i, k in enumerate(FIELDS)}
    for k in keys:
        v = delta[idx[k]] * P0_SIGN[k]
        if v > TOL:
            return 1
        if v < -TOL:
            return -1
    return 0


def units_of(q, choice):
    if choice == 0:
        return 1
    return 2 if (q["cands"][0] if choice > 0 else q["cands"][1]) == q["truth"] else 0


def fit_d(rows, queries, tokens):
    """Conditional logit with per-token weight rows: minimize
    -(1/n) sum log sigma((w_true - w_false) . x) + LAMBDA ||W||^2 (Newton)."""
    import numpy as np
    tix = {t: i for i, t in enumerate(tokens)}
    X = np.asarray(rows, float)
    n, dim = X.shape
    Z = np.zeros((n, len(tokens) * dim))
    for i, q in enumerate(queries):
        a = tix[q["truth"]]
        b = tix[q["cands"][1] if q["cands"][0] == q["truth"] else q["cands"][0]]
        Z[i, a * dim:(a + 1) * dim] += X[i]
        Z[i, b * dim:(b + 1) * dim] -= X[i]
    th = np.zeros(Z.shape[1])
    step = np.ones(1)
    for _ in range(100):
        p = 1.0 / (1.0 + np.exp(-(Z @ th)))
        g = -(Z.T @ (1.0 - p)) / n + 2.0 * LAMBDA * th
        H = (Z.T * (p * (1.0 - p))) @ Z / n + 2.0 * LAMBDA * np.eye(Z.shape[1])
        step = np.linalg.solve(H, g)
        th -= step
        if float(np.max(np.abs(step))) < 1e-12:
            break
    return th.reshape(len(tokens), dim), float(np.max(np.abs(step))) < 1e-12


def d_units(W, rows, queries, tokens):
    import numpy as np
    tix = {t: i for i, t in enumerate(tokens)}
    out = []
    for x, q in zip(rows, queries):
        s = float((W[tix[q["cands"][0]]] - W[tix[q["cands"][1]]]) @ np.asarray(x, float))
        out.append(units_of(q, 0 if abs(s) <= TIE else (1 if s > 0 else -1)))
    return out


def signflip(values):
    counts, nz = {0: 1}, 0
    for v in values:
        v = abs(int(v))
        if v == 0:
            continue
        nz += 1
        nxt = {}
        for s, c in counts.items():
            nxt[s + v] = nxt.get(s + v, 0) + c
            nxt[s - v] = nxt.get(s - v, 0) + c
        counts = nxt
    obs = sum(int(v) for v in values)
    return float(Fraction(sum(c for s, c in counts.items() if s >= obs), 2 ** nz))


def summary(queries, ua, ub, sel=None):
    by, cnt = {}, {}
    for q, a, b in zip(queries, ua, ub):
        if q["ambiguous"] and (sel is None or sel(q)):
            by[q["group"]] = by.get(q["group"], 0) + (a - b)
            cnt[q["group"]] = cnt.get(q["group"], 0) + 1
    if not by:
        return {"groups": 0, "queries": 0}
    gs = sorted(by)
    vals = [by[g] for g in gs]
    m = sum(cnt.values())
    est = (sum(vals) / 2.0) / m
    res = [v / 2.0 - est * cnt[g] for v, g in zip(vals, gs)]
    k = len(vals)
    se = math.sqrt((k / (k - 1)) * sum(r * r for r in res) / m ** 2) if k > 1 else 0.0
    return {"groups": k, "queries": m, "mean_increment": round(est, 6),
            "ci95": [round(est - 1.959964 * se, 6), round(est + 1.959964 * se, 6)],
            "upper95_one_sided": round(est + 1.644854 * se, 6), "p_signflip": signflip(vals)}


def above(queries, u, sel=None):
    by = {}
    for q, x in zip(queries, u):
        if q["ambiguous"] and (sel is None or sel(q)):
            by[q["group"]] = by.get(q["group"], 0) + (x - 1)
    return [by[g] for g in sorted(by)]


def accuracy(queries, u, sel=None):
    t = c = 0
    for q, x in zip(queries, u):
        if q["ambiguous"] and (sel is None or sel(q)):
            t, c = t + x, c + 1
    return round(t / (2 * c), 6) if c else None


def gates_for(queries, u, ud, ush, man, unseen):
    a_, d_ = man["statistics"]["alpha"], man["statistics"]["delta_min"]
    ab = above(queries, u)
    pa = signflip(ab) if ab else 1.0
    vd = summary(queries, u, ud)
    vs = summary(queries, u, ush)
    vdu = summary(queries, u, ud, unseen)
    abu = above(queries, u, unseen)
    pau = signflip(abu) if abu else 1.0
    tg = man["transfer_gate"]
    g = {"A_above_chance": sum(ab) > 0 and pa < a_,
         "B_beats_demo": vd.get("mean_increment", 0) > 0 and vd.get("p_signflip", 1) < a_,
         "C_beats_shuffle": vs.get("mean_increment", 0) > 0 and vs.get("p_signflip", 1) < a_,
         "D_min_effect": vd.get("mean_increment", -1) >= d_,
         "H_nonnegative_on_ambiguous": vd.get("mean_increment", -1) >= 0,
         "T_transfer": (vdu.get("groups", 0) >= tg["min_unseen_groups"] and vdu.get("mean_increment", 0) > 0
                        and sum(abu) > 0 and pau < tg["alpha_above_chance"]),
         "B_fails_decisively": vd.get("p_signflip", 1) >= a_ and vd.get("upper95_one_sided", 1) < d_,
         "C_fails_decisively": vs.get("p_signflip", 1) >= a_ and vs.get("upper95_one_sided", 1) < d_,
         "p_A": pa, "vs_D": vd, "vs_shuffled": vs, "vs_D_unseen": vdu,
         "accuracy_ambiguous": accuracy(queries, u), "accuracy_ambiguous_unseen": accuracy(queries, u, unseen)}
    g["primary_pass"] = all(g[k] for k in ("A_above_chance", "B_beats_demo", "C_beats_shuffle",
                                             "D_min_effect", "H_nonnegative_on_ambiguous"))
    g["full_pass"] = g["primary_pass"] and g["T_transfer"]
    return g


def ladder(g, n_amb, man, blocked, converged):
    caps = man["caps"]
    if blocked or not converged:
        return "MIXED_OR_INCONCLUSIVE"
    if n_amb < caps["floor_ambiguous_groups"]:
        return "MIXED_OR_INCONCLUSIVE"
    for a in GATED:
        if g[a]["full_pass"]:
            return PASS[a][0]
    for a in GATED:
        if g[a]["primary_pass"]:
            return PASS[a][1]
    for a in GATED:
        x = g[a]
        if x["A_above_chance"] and x["B_beats_demo"] and x["C_beats_shuffle"] and not x["D_min_effect"]:
            return "CFR_INCREMENT_SIGNIFICANT_BELOW_FLOOR"
    if n_amb < caps["target_ambiguous_groups"]:
        return "MIXED_OR_INCONCLUSIVE"
    if all(g[a]["C_fails_decisively"] for a in GATED):
        return "CANDIDATE_RESPONSE_NOT_EPISODE_SPECIFIC"
    if all(g[a]["B_fails_decisively"] for a in GATED):
        return "CANDIDATE_INTERVENTION_NO_INCREMENT_OVER_DEMONSTRATIONS"
    return "MIXED_OR_INCONCLUSIVE"


def gate_arithmetic(g, man):
    """Do a report arm's gate booleans follow from its own stated numbers?"""
    a_, d_ = man["statistics"]["alpha"], man["statistics"]["delta_min"]
    vd, vs = g.get("vs_D", {}), g.get("vs_shuffled", {}) or {}
    want = {"B_beats_demo": vd.get("mean_increment", 0) > 0 and (vd.get("p_signflip") or 1) < a_,
            "D_min_effect": vd.get("mean_increment", -1) >= d_,
            "H_nonnegative_on_ambiguous": vd.get("mean_increment", -1) >= 0,
            "B_fails_decisively": (vd.get("p_signflip") or 1) >= a_ and vd.get("upper95_one_sided", 1) < d_}
    if vs:
        want["C_beats_shuffle"] = vs.get("mean_increment", 0) > 0 and (vs.get("p_signflip") or 1) < a_
        want["C_fails_decisively"] = (vs.get("p_signflip") or 1) >= a_ and vs.get("upper95_one_sided", 1) < d_
    want["primary_pass"] = all(g[k] for k in ("A_above_chance", "B_beats_demo", "C_beats_shuffle",
                                                "D_min_effect", "H_nonnegative_on_ambiguous"))
    want["full_pass"] = want["primary_pass"] and g["T_transfer"]
    return {k: v for k, v in want.items() if bool(g.get(k)) != bool(v)}


def freeze_checks(man, cfg):
    """The freeze pins, checked from the files on disk."""
    from cora_arc2026 import v14_loc as L
    out = []

    def add(name, ok, detail=""):
        out.append({"check": name, "ok": bool(ok), "detail": detail})
    with open(cfg["manifest"] + ".sha256") as handle:
        add("manifest_hash_file", handle.read().split()[0] == sha(cfg["manifest"]))
    add("protocol_hash", sha(cfg["protocol"]) == man["protocol_doc_sha256"])
    bad = [r for r, d in man["implementation_sha256"].items() if sha(os.path.join(HERE, r)) != d]
    add("implementation_hashes", not bad, bad[:5])
    badt = [n for n, r in L.dependency_roots(HERE).items() if L.tree_digest(r) != man["dependency_tree_sha256"][n]]
    add("dependency_trees", not badt, badt)
    add("runtime_versions", L.runtime_versions() == man["runtime_versions"])
    add("p0_order_matches_manifest", tuple(man["P0_keys"]) == P0_ORDER
        and list(man["P0_signs"]) == [P0_SIGN[k] for k in P0_ORDER])
    return out


def close(a, b, tol=1.5e-6):
    if a is None or b is None:
        return a is b
    return abs(float(a) - float(b)) <= tol


def verify(cfg):
    checks, notes = [], []

    def check(name, ok, detail=""):
        checks.append({"check": name, "ok": bool(ok), "detail": detail})
        return ok

    with open(cfg["manifest"]) as handle:
        man = json.load(handle)
    from cora_arc2026 import v14_loc as L
    from cora_arc2026 import v15_sel as S
    from cora_arc2026 import v16_cfr as C
    #  1. freeze
    if not cfg["skip_freeze"]:
        for c in freeze_checks(man, cfg):
            checks.append(c)
    #  2. the sealed reports
    raw = [open(p, "rb").read() for p in cfg["reports"]]
    check("reports_byte_identical", len(set(raw)) == 1, [sha(p)[:16] for p in cfg["reports"]])
    rep = json.loads(raw[0])
    for k in ("freeze_problems", "integrity_problems", "leaks", "train_test_overlap"):
        check(f"report_{k}_empty", rep.get(k) == [], rep.get(k))
    check("report_not_audit_blocked", rep.get("verdict") != "AUDIT_BLOCKED", rep.get("verdict"))
    if rep.get("verdict") == "AUDIT_BLOCKED" or "gates" not in rep:
        return {"checks": checks, "report_classification": rep.get("classification"),
                "status": "REPORT_HAS_NO_GATES", "notes": ["the report holds no gate values"]}, rep, None
    #  3. responses
    with open(cfg["test_resp"]) as handle:
        tresp = json.load(handle)
    with open(cfg["dev_resp"]) as handle:
        dresp = json.load(handle)
    trec, drec = records(cfg["test_dir"]), records(cfg["dev_dir"])
    for name, resp, recs in (("test", tresp, trec), ("dev", dresp, drec)):
        check(f"{name}_probe_identity", resp["probe_identity"] == man["probe_identity"])
        check(f"{name}_fitter_identity", resp["fitter_identity"] == man["fitter_identity"])
        check(f"{name}_state_restored", resp.get("state_restored_every_group") is True)
        check(f"{name}_responses_bound_to_corpus", resp.get("admitted_records_sha256") == binding(recs),
              [str(resp.get("admitted_records_sha256"))[:16], binding(recs)[:16]])
    check("test_order_recheck_passed", tresp.get("order_check_passed") is True, tresp.get("order_check_episodes"))
    #  4. corpus
    slots = [r["slot"] for r in trec]
    check("test_slots_contiguous", slots == list(range(len(slots))), len(slots))
    if not cfg["skip_freeze"]:
        check("test_freeze_ok_every_record", all(r.get("freeze_ok") is True for r in trec))
    with open(cfg["exclusion"]) as handle:
        ex = json.load(handle)
    ex_t, ex_g = set(ex["target_digests"]), set(ex["group_digests"])
    tg, dg = first_admissions(trec), first_admissions(drec)
    dup = len([r for r in trec if r.get("admitted")]) - len(tg)
    check("test_no_repeated_group", dup == 0, dup)
    tt = {d for g in tg for d in g["target_digests"]}
    check("test_no_excluded_digest", not ({g["group_digest"] for g in tg} & ex_g) and not (tt & ex_t))
    dt = {d for g in dg for d in g["target_digests"]}
    check("test_disjoint_from_development", not (tt & dt) and not ({g["group_digest"] for g in tg}
                                                                   & {g["group_digest"] for g in dg}))
    seen_t = []
    for g in tg:
        seen_t += g["target_digests"]
    check("test_targets_unique", len(seen_t) == len(set(seen_t)))
    #  5. independent recomputation of P0 and P0_then_D
    rm = lambda resp: {(r["group_digest"], r["t"], r["r"]): r["responses"] for r in resp["rows"]}
    qte = own_queries(tg, rm(tresp))
    qdev = own_queries(dg, rm(dresp))
    ref_te = C.build_queries(tg, rm(tresp))
    agree = all(a["cands"] == tuple(b["cands"]) and a["truth"] == b["truth"] and a["pair_key"] == b["pair_key"]
                and a["ambiguous"] == b["ambiguous"] and a["delta"] == b["delta"]
                for a, b in zip(qte, ref_te)) and len(qte) == len(ref_te)
    check("own_queries_match_frozen_queries", agree, len(qte))
    n_amb_q = sum(1 for q in qte if q["ambiguous"])
    n_amb_g = len({q["group"] for q in qte if q["ambiguous"]})
    check("ambiguous_counts_match_report", n_amb_q == rep["ambiguous_test_queries"]
          and n_amb_g == rep["ambiguous_test_groups"], [n_amb_q, n_amb_g])
    held = lambda pk: hashlib.sha256(("v16-heldout|" + pk).encode()).hexdigest()[0] in "01234"
    train_groups = {q["group"] for q in qdev if not held(q["pair_key"])}
    train_pairs = {q["pair_key"] for q in qdev if q["group"] in train_groups}
    check("training_group_count", len(train_groups) == man["training_resource"]["groups"], len(train_groups))
    unseen = lambda q: q["pair_key"] not in train_pairs
    n_unseen_amb = len({q["group"] for q in qte if q["ambiguous"] and unseen(q)})
    check("unseen_ambiguous_count_matches_report", n_unseen_amb == rep["unseen_pair_ambiguous_groups"], n_unseen_amb)
    check("transfer_minimum_met", n_unseen_amb >= man["transfer_gate"]["min_unseen_groups"],
          [n_unseen_amb, man["transfer_gate"]["min_unseen_groups"]])
    #  D: frozen feature extraction, own fit and scoring
    dq = C.build_queries(dg, rm(dresp))
    qtr_ref = [q for q in dq if q["group"] in train_groups]
    std = S.standardizer_for(qtr_ref, None)
    tokens = S.feature_tokens()
    W, conv = fit_d(S.design(qtr_ref, "D", std), [q for q in qdev if q["group"] in train_groups], tokens)
    check("own_D_fit_converged", conv)
    ud = d_units(W, S.design(ref_te, "D", std), qte, tokens)
    keys = tuple(k for k in P0_ORDER if k in man["P0_keys"])
    dec = [p0_decision(q["delta"], keys) for q in qte]
    u0 = [units_of(q, c) for q, c in zip(qte, dec)]
    u0d = [x if c != 0 else y for x, c, y in zip(u0, dec, ud)]
    pi = C.response_shuffle(ref_te)
    donor = []
    for i, q in enumerate(qte):
        j = pi[i]
        d = list(qte[j]["delta"])
        if qte[j]["pair_key"] == q["pair_key"] and qte[j]["cands"][0] != q["cands"][0]:
            d = [-v for v in d]
        donor.append(d)
    decs = [p0_decision(d, keys) for d in donor]
    u0s = [units_of(q, c) for q, c in zip(qte, decs)]
    u0ds = [x if c != 0 else y for x, c, y in zip(u0s, decs, ud)]
    u0w = [units_of(q, -c) for q, c in zip(qte, dec)]
    mine = {"P0": gates_for(qte, u0, ud, u0s, man, unseen),
            "P0_then_D": gates_for(qte, u0d, ud, u0ds, man, unseen)}
    recomputed = {"D_accuracy_ambiguous": accuracy(qte, ud), "P0_swapped_accuracy": accuracy(qte, u0w),
                  "P0_coverage": round(sum(1 for q, c in zip(qte, dec) if q["ambiguous"] and c != 0) / max(1, n_amb_q), 6),
                  "arms": mine}
    check("D_accuracy_matches_report", close(recomputed["D_accuracy_ambiguous"], rep["arms"]["D"]["accuracy_ambiguous"]),
          [recomputed["D_accuracy_ambiguous"], rep["arms"]["D"]["accuracy_ambiguous"]])
    check("P0_swapped_matches_report", close(recomputed["P0_swapped_accuracy"], rep["arms"]["P0_SWAPPED"]["accuracy_ambiguous"]))
    check("P0_coverage_matches_report", close(recomputed["P0_coverage"], rep["P0_selective"]["coverage"]))
    for arm in ("P0", "P0_then_D"):
        r, m = rep["gates"][arm], mine[arm]
        for k in ("A_above_chance", "B_beats_demo", "C_beats_shuffle", "D_min_effect",
                  "H_nonnegative_on_ambiguous", "T_transfer", "B_fails_decisively",
                  "C_fails_decisively", "primary_pass", "full_pass"):
            check(f"{arm}_{k}_recomputes", bool(r[k]) == bool(m[k]), [r[k], m[k]])
        check(f"{arm}_accuracy_recomputes", close(r["accuracy_ambiguous"], m["accuracy_ambiguous"]),
              [r["accuracy_ambiguous"], m["accuracy_ambiguous"]])
        for blk in ("vs_D", "vs_shuffled", "vs_D_unseen"):
            ok = close(r[blk].get("mean_increment"), m[blk].get("mean_increment")) and \
                 close(r[blk].get("p_signflip"), m[blk].get("p_signflip"), 1e-9) and \
                 close(r[blk].get("upper95_one_sided"), m[blk].get("upper95_one_sided"))
            check(f"{arm}_{blk}_recomputes", ok, [r[blk].get("mean_increment"), m[blk].get("mean_increment"),
                                                  r[blk].get("p_signflip"), m[blk].get("p_signflip")])
    for arm in ("P0", "P0_then_D", "P1", "P2"):
        wrong = gate_arithmetic(rep["gates"][arm], man)
        check(f"{arm}_gate_arithmetic_consistent", not wrong, wrong)
    check("report_order_invariant", rep.get("order_invariant") is True)
    check("report_gated_fits_converged", rep.get("fits_converged") is True)
    g_all = {"P0": mine["P0"], "P0_then_D": mine["P0_then_D"], "P1": rep["gates"]["P1"]}
    cls = ladder(g_all, n_amb_g, man, False, rep.get("fits_converged") is True and rep.get("order_invariant") is True)
    rcls = rep["classification"]["classification"]
    check("classification_recomputes", cls == rcls, [rcls, cls])
    depends_on_p1 = rcls.startswith("HYBRID_CFR") or (
        rcls == "CFR_INCREMENT_SIGNIFICANT_BELOW_FLOOR" and not any(
            mine[a]["A_above_chance"] and mine[a]["B_beats_demo"] and mine[a]["C_beats_shuffle"] for a in ("P0", "P0_then_D")))
    if depends_on_p1:
        notes.append("the class rests on P1, whose fit was not independently re-implemented here; recheck P1 in a session")
    return {"checks": checks, "recomputed": recomputed, "classification_recomputed": cls,
            "classification_report": rep["classification"], "class_depends_on_P1": depends_on_p1,
            "notes": notes}, rep, man


def tables(rep, cfg):
    arms = rep.get("arms", {})
    rows = []
    for arm in sorted(arms):
        g = rep.get("gates", {}).get(arm, {})
        vd, vs = g.get("vs_D", {}), g.get("vs_shuffled", {}) or {}
        rows.append({"arm": arm, "accuracy_ambiguous": arms[arm]["accuracy_ambiguous"],
                     "accuracy_ambiguous_unseen": arms[arm]["accuracy_ambiguous_unseen"],
                     "end_to_end": arms[arm]["end_to_end"],
                     "increment_over_D": vd.get("mean_increment"), "increment_ci95": vd.get("ci95"),
                     "p_over_D": vd.get("p_signflip"), "increment_over_control": vs.get("mean_increment"),
                     "p_over_control": vs.get("p_signflip"),
                     "gates": {k: g.get(k) for k in ("A_above_chance", "B_beats_demo", "C_beats_shuffle",
                                                       "D_min_effect", "H_nonnegative_on_ambiguous",
                                                       "T_transfer")} if g else None})
    with open(cfg["csv"], "w", newline="") as handle:
        w = csv.writer(handle)
        w.writerow(["arm", "accuracy_ambiguous", "accuracy_ambiguous_unseen", "end_to_end",
                    "increment_over_D", "ci95_low", "ci95_high", "p_over_D",
                    "increment_over_control", "p_over_control"])
        for r in rows:
            ci = r["increment_ci95"] or [None, None]
            w.writerow([r["arm"], r["accuracy_ambiguous"], r["accuracy_ambiguous_unseen"], r["end_to_end"],
                        r["increment_over_D"], ci[0], ci[1], r["p_over_D"],
                        r["increment_over_control"], r["p_over_control"]])
    with open(cfg["figure"], "w") as handle:
        handle.write(json.dumps({"arms": rows, "by_family": rep.get("by_family"),
                                 "P0_selective": rep.get("P0_selective"),
                                 "population": {k: rep.get(k) for k in (
                                     "test_groups", "test_slots", "ambiguous_test_queries",
                                     "ambiguous_test_groups", "unseen_pair_ambiguous_groups",
                                     "training_groups")},
                                 "classification": rep.get("classification")}, indent=1, sort_keys=True) + "\n")


def main(cfg=None):
    cfg = cfg or default_cfg()
    result, rep, man = verify(cfg)
    ok = all(c["ok"] for c in result["checks"])
    result["all_checks_pass"] = ok
    result["written_before_outcomes"] = "2026-10-04"
    with open(cfg["out"], "w") as handle:
        handle.write(json.dumps(result, indent=1, sort_keys=True, default=str) + "\n")
    if rep is not None and "gates" in rep:
        tables(rep, cfg)
    marker = "V16_TERMINAL_VERIFIED" if ok else "V16_TERMINAL_DISCREPANCY"
    with open(os.path.join(cfg["marker_dir"], marker), "w") as handle:
        failed = [c["check"] for c in result["checks"] if not c["ok"]]
        handle.write(json.dumps({"failed_checks": failed, "notes": result.get("notes", [])}) + "\n")
    print(json.dumps({"all_checks_pass": ok, "failed": [c["check"] for c in result["checks"] if not c["ok"]],
                      "class_depends_on_P1": result.get("class_depends_on_P1"),
                      "checks": len(result["checks"])}))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
