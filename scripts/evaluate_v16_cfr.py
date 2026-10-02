"""Item-2 v1.6: the sealed evaluator of the prospective bounded-repair test.

Reads the frozen manifest, verifies every freeze pin, audits the prospective
corpus against the frozen laws, checks the responses, builds the queries,
fits the learned arms on the frozen training resource only, applies the P0
rule, computes every arm and control on the verification-ambiguous test
population, applies the frozen gates and the classification ladder, and
writes one report. `--integrity-only` stops after the audit and prints no
score. Deterministic: single-threaded BLAS, fixed orders, exact tests.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sys

for v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[v] = "1"

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from cora_arc2026 import v14_loc as L                             # noqa: E402
from cora_arc2026 import v15_sel as S                             # noqa: E402
from cora_arc2026 import v16_cfr as C                             # noqa: E402

G, CV = S.G, S.CV
PROTOCOL = os.path.join(HERE, "docs", "CORA_TTI_CANDIDATE_FAILURE_RESPONSE_v1.6.md")
MANIFEST = os.path.join(HERE, "outputs", "tti", "candidate_failure_response_v16_manifest.json")
TRAIN_DIR = os.path.join(HERE, "outputs", "tti", "v15_test_corpus")
TEST_DIR = os.path.join(HERE, "outputs", "tti", "v16_test_corpus")
TRAIN_RESP = os.path.join(HERE, "outputs", "tti", "v16_dev_responses.json")
TEST_RESP = os.path.join(HERE, "outputs", "tti", "v16_test_responses.json")
EXCLUSION = os.path.join(HERE, "outputs", "tti", "v16_exclusion_digests.json")
RECORD = re.compile(r"^full(\d{5})\.json$")
OUT_DEFAULT = os.path.join(HERE, "outputs", "tti", "v16_cfr_report.json")
INTEGRITY_ONLY = "--integrity-only" in sys.argv[1:]
TEST_BASE = 500_000_000
ARMS = ("D", "P0", "P0_SHUFFLED", "P0_SWAPPED", "P0_then_D", "P0_then_D_SHUFFLED",
        "P0_then_D_SWAPPED", "P1", "P1_SHUFFLED", "P1_SWAPPED", "R", "P2", "F_S7")


def sha256(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def verify_freeze(man):
    p = []
    if sha256(PROTOCOL) != man["protocol_doc_sha256"]:
        p.append("protocol")
    with open(MANIFEST + ".sha256") as handle:
        if handle.read().split()[0] != sha256(MANIFEST):
            p.append("manifest")
    for rel, digest in sorted(man["implementation_sha256"].items()):
        if sha256(os.path.join(HERE, rel)) != digest:
            p.append(rel)
    for name, root in sorted(L.dependency_roots(HERE).items()):
        if L.tree_digest(root) != man["dependency_tree_sha256"][name]:
            p.append(f"dependency:{name}")
    for path, digest in sorted(man["external_file_sha256"].items()):
        if sha256(path) != digest:
            p.append(path)
    if L.runtime_versions() != man["runtime_versions"]:
        p.append("runtime_versions")
    tr = man["training_resource"]
    if sha256(os.path.join(HERE, tr["hash_list"])) != tr["hash_list_sha256"]:
        p.append("training_hash_list")
    else:
        with open(os.path.join(HERE, tr["hash_list"])) as handle:
            for line in handle:
                digest, name = line.split()
                if sha256(os.path.join(TRAIN_DIR, name)) != digest:
                    p.append(f"training:{name}")
    if sha256(TRAIN_RESP) != tr["responses_sha256"]:
        p.append("training_responses")
    return p


def load(dirname):
    names = sorted(n for n in os.listdir(dirname) if RECORD.match(n))
    out = []
    for n in names:
        path = os.path.join(dirname, n)
        with open(path) as handle:
            rec = json.load(handle)
        rec["_sha256"] = sha256(path)
        out.append(rec)
    return out


def test_integrity(records, man, exclusion) -> list:
    """Every frozen law of the prospective corpus (the v1.5 audit with the
    v1.6 seed base and exclusion set); any finding blocks the audit."""
    p = []
    ex_targets, ex_groups = exclusion
    if [r["slot"] for r in records] != list(range(len(records))):
        p.append("slots_not_contiguous")
    if any(n.endswith(".tmp") for n in os.listdir(TEST_DIR)):
        p.append("partial_file")
    man_sha = sha256(MANIFEST)
    for r in records:
        tag = f"slot{r['slot']}"
        if r.get("environment") != man["environment"]["required_snapshot"]:
            p.append(f"{tag}:environment")
        if r.get("runtime_versions") != man["runtime_versions"]:
            p.append(f"{tag}:runtime_versions")
        if r.get("freeze_ok") is not True:
            p.append(f"{tag}:freeze")
        if r.get("engine_state_problems"):
            p.append(f"{tag}:engine_state")
        if r.get("manifest_sha256") != man_sha:
            p.append(f"{tag}:manifest")
        if r.get("started_since_first_start_s", 1e18) > man["caps"]["wall_clock_s"]:
            p.append(f"{tag}:cap")
    seen_g, seen_t = set(), set()
    for r in [r for r in records if r["admitted"]]:
        g, slot, tag = r["group"], r["slot"], f"slot{r['slot']}"
        fam = S.FAMILIES[slot % len(S.FAMILIES)]
        if g["contrast_type"] != "FEATURE" or g["anchor_family"] != fam:
            p.append(f"{tag}:family_or_type")
        off = g["pair_seed"] - TEST_BASE - slot * S.SLOT_STRIDE
        attempt, rem = divmod(off, S.ATTEMPT_STRIDE)
        if rem or not 0 <= attempt < S.ATTEMPTS_PER_SLOT:
            p.append(f"{tag}:pair_seed")
            continue
        anchor = S.CD.sample_target(g["pair_seed"], G.parse_family(fam))
        contrast = G.contrast_target(anchor, "FEATURE", rotation=attempt)
        if contrast is None or [CV.digest(anchor), CV.digest(contrast)] != g["target_digests"]:
            p.append(f"{tag}:derivation")
            continue
        want = {0: [list(t) for t in CV.tokens_from_ast(anchor)],
                1: [list(t) for t in CV.tokens_from_ast(contrast)]}
        if any(e.get("target_tokens") != want.get(e.get("target_index")) for e in g["episodes"]):
            p.append(f"{tag}:target_tokens")
        if not L.twin_law(anchor, contrast)[0]:
            p.append(f"{tag}:twin_law")
        if G.group_digest(*g["target_digests"]) != g["group_digest"]:
            p.append(f"{tag}:group_digest")
        if g["group_digest"] in ex_groups or set(g["target_digests"]) & ex_targets:
            p.append(f"{tag}:excluded_digest")
        if g["group_digest"] in seen_g or set(g["target_digests"]) & seen_t:
            p.append(f"{tag}:repeated_digest")
        seen_g.add(g["group_digest"])
        seen_t.update(g["target_digests"])
        eps = g["episodes"]
        cells = sorted((e["target_index"], e["replicate_index"]) for e in eps)
        if cells != sorted((t, k) for t in (0, 1) for k in range(S.REPLICATES)):
            p.append(f"{tag}:design_cells")
            continue
        for e in eps:
            if e["target_digest"] != g["target_digests"][e["target_index"]]:
                p.append(f"{tag}:episode_digest")
            if e["seed"] not in S.episode_seeds(g["pair_seed"], e["target_index"]):
                p.append(f"{tag}:seed_law")
        if len({e["seed"] for e in eps}) != len(eps):
            p.append(f"{tag}:seeds_not_distinct")
        inputs = [json.dumps([d["input"] for d in e["demonstrations"]]) for e in eps]
        if len(set(inputs)) != len(inputs):
            p.append(f"{tag}:inputs_shared")
    return p


def corpus_binding(records) -> str:
    """sha256 over the admitted records' file hashes in slot order; the same
    computation as v16_responses.compute, so a response file is bound to the
    exact corpus it was computed from."""
    recs = sorted((r for r in records if r.get("admitted")), key=lambda r: r["slot"])
    return hashlib.sha256("".join(r["_sha256"] for r in recs).encode()).hexdigest()


def response_integrity(groups, resp, man, which, binding=None) -> list:
    p = []
    if binding is not None and resp.get("admitted_records_sha256") != binding:
        p.append(f"{which}:responses_not_bound_to_corpus")
    if resp["probe_identity"] != man["probe_identity"] or resp["probe_identity"] != C.probe_identity():
        p.append(f"{which}:probe_identity")
    if resp["fitter_identity"] != man["fitter_identity"]:
        p.append(f"{which}:fitter_identity")
    if not resp["state_restored_every_group"]:
        p.append(f"{which}:state_not_restored")
    if resp.get("order_check_passed") is False:
        p.append(f"{which}:order_check_failed")
    have = {(r["group_digest"], r["t"], r["r"]) for r in resp["rows"]}
    want = {(g["group_digest"], e["target_index"], e["replicate_index"])
            for g in groups for e in g["episodes"]}
    if want - have:
        p.append(f"{which}:missing_responses:{len(want - have)}")
    if have - want:
        p.append(f"{which}:extra_responses:{len(have - want)}")
    return p


def rmap(resp):
    return {(r["group_digest"], r["t"], r["r"]): r["responses"] for r in resp["rows"]}


def train_groups_of(groups, queries, man):
    """The frozen training resource: development groups whose token pair is
    not held out (plan section 11)."""
    pk = {}
    for q in queries:
        pk.setdefault(q["group"], q["pair_key"])
    keep = [i for i in range(len(groups)) if not C.heldout_pair(pk[i])]
    if man["training_resource"]["groups"] != len(keep):
        raise SystemExit(f"training resource has {len(keep)} groups, manifest says "
                         f"{man['training_resource']['groups']}")
    return keep


def fit_arms(qtr, rep):
    """Every learned arm, fitted on the training resource only."""
    qtr_rep = [q for q in qtr if q["ambiguous"]] if rep == "R1" else qtr
    std_all = S.standardizer_for(qtr, None)
    std_rep = S.standardizer_for(qtr_rep, None)
    std15 = S.standardizer_for(qtr, "F_S7")
    out = {"std_all": std_all, "std_rep": std_rep, "std15": std15, "rep": rep, "info": {}}
    rtr_all = C.d_rows(qtr, std_all)
    rtr = C.d_rows(qtr_rep, std_rep)
    if rep == "R2":
        dtr, _ = C.residualized(qtr_rep, [], None, std_rep)
    else:
        dtr = [q["delta"] for q in qtr_rep]
    out["scale"] = C.rms_scale(dtr)
    dtr_s = C.apply_scale(dtr, out["scale"])
    pi_tr = C.response_shuffle(qtr_rep)
    sh_tr = C.donor_deltas(qtr_rep, pi_tr, dtr_s)
    out["shuffle_fidelity_train"] = C.shuffle_fidelity(qtr_rep, pi_tr)
    for name, args in (("D", dict(queries=qtr, rows=rtr_all)),
                       ("P1", dict(queries=qtr_rep, rows=rtr, deltas=dtr_s)),
                       ("P1_SHUFFLED", dict(queries=qtr_rep, rows=rtr, deltas=sh_tr)),
                       ("R", dict(queries=qtr_rep, deltas=dtr_s))):
        model, info = C.fit(**args)
        out[name] = model
        out["info"][name] = info
    m, info = S.fit_pairs(S.design(qtr, "D+F_ASSOC", std15), qtr)
    out["P2"], out["info"]["P2"] = m, info
    m, info = S.fit_pairs(S.design(qtr, "F_ASSOC", std15), qtr)
    out["F_S7"], out["info"]["F_S7"] = m, info
    out["qtr_rep"] = qtr_rep
    return out


def score_arms(fits, qte, p0_keys):
    rep = fits["rep"]
    rva_all = C.d_rows(qte, fits["std_all"])
    rva = C.d_rows(qte, fits["std_rep"])
    if rep == "R2":
        _, dte = C.residualized(fits["qtr_rep"], qte, None, fits["std_rep"])
    else:
        dte = [q["delta"] for q in qte]
    dte_s = C.apply_scale(dte, fits["scale"])
    pi = C.response_shuffle(qte)
    sh = C.donor_deltas(qte, pi, dte_s)
    sw = [[-v for v in d] for d in dte_s]
    raw = [q["delta"] for q in qte]
    raw_sh = C.donor_deltas(qte, pi, raw)
    raw_sw = [[-v for v in d] for d in raw]
    sc = {"D": C.score(fits["D"], qte, rva_all, None),
          "P1": C.score(fits["P1"], qte, rva, dte_s),
          "P1_SHUFFLED": C.score(fits["P1_SHUFFLED"], qte, rva, sh),
          "P1_SWAPPED": C.score(fits["P1"], qte, rva, sw),
          "R": C.score(fits["R"], qte, None, dte_s),
          "P2": S.score_queries(fits["P2"], S.design(qte, "D+F_ASSOC", fits["std15"]), qte),
          "F_S7": S.score_queries(fits["F_S7"], S.design(qte, "F_ASSOC", fits["std15"]), qte)}
    units = {k: [s["units"] for s in v] for k, v in sc.items()}
    order_ok = all(s["order_invariant"] for v in sc.values() for s in v)
    units["P0"] = [C.p0_units(q, d, p0_keys) for q, d in zip(qte, raw)]
    units["P0_SHUFFLED"] = [C.p0_units(q, d, p0_keys) for q, d in zip(qte, raw_sh)]
    units["P0_SWAPPED"] = [C.p0_units(q, d, p0_keys) for q, d in zip(qte, raw_sw)]
    units["P0_then_D"] = [C.p0_units(q, d, p0_keys, fallback_units=u)
                          for q, d, u in zip(qte, raw, units["D"])]
    units["P0_then_D_SHUFFLED"] = [C.p0_units(q, d, p0_keys, fallback_units=u)
                                   for q, d, u in zip(qte, raw_sh, units["D"])]
    units["P0_then_D_SWAPPED"] = [C.p0_units(q, d, p0_keys, fallback_units=u)
                                  for q, d, u in zip(qte, raw_sw, units["D"])]
    return units, order_ok, pi, {"ties_P1": sum(1 for s in sc["P1"] if s["tie"]),
                                 "nll": {k: round(sum(s["nll"] for s in v) / len(v), 6)
                                         for k, v in sc.items()},
                                 "shuffle_fidelity_test": C.shuffle_fidelity(qte, pi)}


def arm_gates(qte, units, arm, man, unseen):
    """Gates A to D, H and T for one arm on the ambiguous population."""
    alpha, dmin = man["statistics"]["alpha"], man["statistics"]["delta_min"]
    above = C.above_chance_values(qte, units[arm])
    p_a = float(S.signflip_p(above)) if above else 1.0
    vs_d = C.increment_summary(qte, units[arm], units["D"])
    shuf = f"{arm}_SHUFFLED"
    vs_s = C.increment_summary(qte, units[arm], units[shuf]) if shuf in units else {}
    tg = man["transfer_gate"]
    vs_d_un = C.increment_summary(qte, units[arm], units["D"], unseen)
    above_un = C.above_chance_values(qte, units[arm], unseen)
    p_a_un = float(S.signflip_p(above_un)) if above_un else 1.0
    g = {"A_above_chance": sum(above) > 0 and p_a < alpha,
         "B_beats_demo": vs_d.get("mean_increment", 0) > 0 and vs_d.get("p_signflip", 1) < alpha,
         "C_beats_shuffle": vs_s.get("mean_increment", 0) > 0 and vs_s.get("p_signflip", 1) < alpha,
         "D_min_effect": vs_d.get("mean_increment", -1) >= dmin,
         "H_nonnegative_on_ambiguous": vs_d.get("mean_increment", -1) >= 0,
         "T_transfer": (vs_d_un.get("groups", 0) >= tg["min_unseen_groups"]
                        and vs_d_un.get("mean_increment", 0) > 0
                        and sum(above_un) > 0 and p_a_un < tg["alpha_above_chance"]),
         "B_fails_decisively": (vs_d.get("p_signflip", 1) >= alpha
                                and vs_d.get("upper95_one_sided", 1) < dmin),
         "C_fails_decisively": (vs_s.get("p_signflip", 1) >= alpha
                                and vs_s.get("upper95_one_sided", 1) < dmin) if vs_s else False,
         "p": {"A": p_a, "B": vs_d.get("p_signflip"), "C": vs_s.get("p_signflip"),
               "A_unseen": p_a_un, "B_unseen": vs_d_un.get("p_signflip")},
         "vs_D": vs_d, "vs_shuffled": vs_s, "vs_D_unseen": vs_d_un,
         "accuracy_ambiguous": C.ambiguous_accuracy(qte, units[arm]),
         "accuracy_ambiguous_unseen": C.ambiguous_accuracy(qte, units[arm], unseen),
         "end_to_end": C.end_to_end_accuracy(qte, units[arm])}
    g["primary_pass"] = all(g[k] for k in ("A_above_chance", "B_beats_demo", "C_beats_shuffle",
                                             "D_min_effect", "H_nonnegative_on_ambiguous"))
    g["full_pass"] = g["primary_pass"] and g["T_transfer"]
    return g


PASS_NAMES = {"P0": ("PURE_CFR_SELECTION_GENERALIZES", "PURE_CFR_FAMILIAR_PAIRS_ONLY"),
              "P0_then_D": ("PURE_RULE_WITH_DEMONSTRATION_FALLBACK_GENERALIZES",
                            "PURE_RULE_WITH_DEMONSTRATION_FALLBACK_FAMILIAR_PAIRS_ONLY"),
              "P1": ("HYBRID_CFR_SELECTION_GENERALIZES", "HYBRID_CFR_FAMILIAR_PAIRS_ONLY")}
GATED_ARMS = ("P0", "P0_then_D", "P1")


def classify(gates, n_amb_groups, man, blocked, converged):
    """First rule wins. Only the *_GENERALIZES classes license the compiler;
    the headline follows the arm (P0 pure; P0_then_D a pure rule with a
    learned fallback, so hybrid; P1 hybrid)."""
    caps, floor = man["caps"], man["caps"]["floor_ambiguous_groups"]
    if blocked or not converged:
        return "MIXED_OR_INCONCLUSIVE", "audit, leakage, order, overlap or convergence failure"
    if n_amb_groups < floor:
        return "MIXED_OR_INCONCLUSIVE", "below the ambiguous-group floor; no statistic interpreted"
    for arm in GATED_ARMS:
        if gates[arm]["full_pass"]:
            return PASS_NAMES[arm][0], f"{arm} passes A to D, H and T"
    for arm in GATED_ARMS:
        if gates[arm]["primary_pass"]:
            return PASS_NAMES[arm][1], f"{arm} passes A to D and H but not the transfer gate"
    for arm in GATED_ARMS:
        g = gates[arm]
        if g["A_above_chance"] and g["B_beats_demo"] and g["C_beats_shuffle"] and not g["D_min_effect"]:
            return "CFR_INCREMENT_SIGNIFICANT_BELOW_FLOOR", f"{arm} passes A, B, C at alpha but its increment is below delta_min; does not license the compiler"
    if n_amb_groups < caps["target_ambiguous_groups"]:
        return "MIXED_OR_INCONCLUSIVE", "negative below the powered ambiguous-group count"
    if all(gates[a]["C_fails_decisively"] for a in GATED_ARMS):
        return "CANDIDATE_RESPONSE_NOT_EPISODE_SPECIFIC", "every gated arm fails C decisively"
    if all(gates[a]["B_fails_decisively"] for a in GATED_ARMS):
        return "CANDIDATE_INTERVENTION_NO_INCREMENT_OVER_DEMONSTRATIONS", "every gated arm fails B decisively"
    return "MIXED_OR_INCONCLUSIVE", "no rule applies"


def p0_selective(qte, units, p0_keys):
    """Reported, not gated: P0's coverage (share of ambiguous queries on which
    it decides) and its precision on those queries, against D on the same
    queries, with the exact above-chance test over group sums."""
    dec = lambda q: C.p0_choice(q["delta"], p0_keys) != 0
    n_amb = sum(1 for q in qte if q["ambiguous"])
    n_dec = sum(1 for q in qte if q["ambiguous"] and dec(q))
    above = C.above_chance_values(qte, units["P0"], dec)
    return {"coverage": round(n_dec / n_amb, 6) if n_amb else None, "decided_queries": n_dec,
            "decided_groups": len(above),
            "precision_P0": C.ambiguous_accuracy(qte, units["P0"], dec),
            "accuracy_D_same_queries": C.ambiguous_accuracy(qte, units["D"], dec),
            "accuracy_P0_SHUFFLED_same_queries": C.ambiguous_accuracy(qte, units["P0_SHUFFLED"], dec),
            "p_above_chance": float(S.signflip_p(above)) if above else None,
            "P0_vs_D_on_decided": C.increment_summary(qte, units["P0"], units["D"], dec)}


def write(report):
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    target = args[0] if args else OUT_DEFAULT
    with open(target, "w") as handle:
        handle.write(json.dumps(report, indent=1, sort_keys=True, default=str) + "\n")


def main():
    with open(MANIFEST) as handle:
        man = json.load(handle)
    freeze = verify_freeze(man)
    exclusion = S.load_exclusion(EXCLUSION)
    train_recs = load(TRAIN_DIR)
    train_inc, train_exc = L.first_admissions(train_recs)
    dev_groups = sorted((r["group"] for r in train_inc), key=lambda g: g["group_digest"])
    test_recs = load(TEST_DIR)
    test_inc, test_exc = L.first_admissions(test_recs)
    test_groups = sorted((r["group"] for r in test_inc), key=lambda g: g["group_digest"])
    integrity = test_integrity(test_recs, man, exclusion)
    if test_exc:
        integrity.append("test_duplicate_admission")
    if len(dev_groups) != man["development_resource"]["groups"]:
        integrity.append("development_group_count")
    with open(TRAIN_RESP) as handle:
        train_resp = json.load(handle)
    test_resp = None
    if os.path.exists(TEST_RESP):
        with open(TEST_RESP) as handle:
            test_resp = json.load(handle)
        integrity += response_integrity(test_groups, test_resp, man, "test",
                                        corpus_binding(test_recs))
    else:
        integrity.append("test_responses_missing")
    integrity += response_integrity(dev_groups, train_resp, man, "train",
                                    corpus_binding(train_recs))
    tr_t = {d for g in dev_groups for d in g["target_digests"]}
    tr_g = {g["group_digest"] for g in dev_groups}
    te_t = {d for g in test_groups for d in g["target_digests"]}
    te_g = {g["group_digest"] for g in test_groups}
    overlap = sorted((tr_t & te_t) | (tr_g & te_g))
    report = {"protocol_doc_sha256": man["protocol_doc_sha256"],
              "development_groups": len(dev_groups), "test_slots": len(test_recs),
              "test_groups": len(test_groups), "freeze_problems": freeze,
              "integrity_problems": integrity[:50], "train_test_overlap": overlap,
              "test_responses_sha256": sha256(TEST_RESP) if test_resp else None}
    blocked = bool(freeze or integrity or overlap)
    qdev = qte = []
    leaks = []
    if not blocked:
        qdev = C.build_queries(dev_groups, rmap(train_resp))
        qte = C.build_queries(test_groups, rmap(test_resp))
        leaks = [[q["group_digest"][:12], q["t"], q["r"], q["integrity"]]
                 for q in qdev + qte if q["integrity"]]
        for q in qdev + qte:
            if len(q["delta"]) != len(C.RESPONSE_FIELDS) or any(
                    isinstance(v, bool) or not isinstance(v, float) or not math.isfinite(v)
                    for v in q["delta"]):
                leaks.append([q["group_digest"][:12], "delta_shape"])
    report["leaks"] = leaks[:50]
    blocked = blocked or bool(leaks)
    amb_groups = len({q["group"] for q in qte if q["ambiguous"]})
    report["ambiguous_test_queries"] = sum(1 for q in qte if q["ambiguous"])
    report["ambiguous_test_groups"] = amb_groups
    if INTEGRITY_ONLY:
        ok = not blocked
        print(json.dumps({k: report[k] for k in ("development_groups", "test_slots", "test_groups",
                                                  "ambiguous_test_groups", "freeze_problems",
                                                  "integrity_problems", "train_test_overlap", "leaks")}, indent=1))
        print("INTEGRITY", "PASS" if ok else "FAIL")
        sys.exit(0 if ok else 1)
    if blocked:
        report["verdict"] = "AUDIT_BLOCKED"
        report["classification"] = {"classification": "MIXED_OR_INCONCLUSIVE", "reason": "audit blocked"}
        write(report)
        print("AUDIT_BLOCKED")
        return
    if amb_groups < man["caps"]["floor_ambiguous_groups"]:
        report["verdict"] = "MIXED_OR_INCONCLUSIVE"
        report["classification"] = {"classification": "MIXED_OR_INCONCLUSIVE",
                                    "reason": "below the ambiguous-group floor; no statistic computed"}
        write(report)
        print("BELOW FLOOR", amb_groups)
        return
    keep = train_groups_of(dev_groups, qdev, man)
    qtr = [q for q in qdev if q["group"] in set(keep)]
    train_pairs = {q["pair_key"] for q in qtr}
    unseen = lambda q: q["pair_key"] not in train_pairs
    fits = fit_arms(qtr, man["P1_representation"])
    #  rule 0 reads the arms the classification depends on; the reporting-only
    #  arms (R, P2, F_S7) are recorded but cannot void the verdict (erratum 1)
    converged = all(fits["info"][a]["converged"] for a in ("D", "P1", "P1_SHUFFLED"))
    converged_all = all(i["converged"] for i in fits["info"].values())
    units, order_ok, pi, extra = score_arms(fits, qte, tuple(man["P0_keys"]))
    report.update({"fits": fits["info"], "fits_converged": converged, "fits_converged_all_arms": converged_all,
                   "order_invariant": order_ok,
                   "P1_representation": man["P1_representation"], "P0_keys": man["P0_keys"],
                   "active_response_fields": C.active_fields(fits["scale"]),
                   "training_groups": len(keep), "training_queries": len(qtr),
                   "unseen_pair_test_groups": len({q["group"] for q in qte if unseen(q)}),
                   "unseen_pair_ambiguous_groups": len({q["group"] for q in qte if unseen(q) and q["ambiguous"]}),
                   "shuffle_fidelity": {"train": fits["shuffle_fidelity_train"],
                                        "test": extra["shuffle_fidelity_test"]},
                   "nll": extra["nll"]})
    gates = {arm: arm_gates(qte, units, arm, man, unseen) for arm in ("P0", "P0_then_D", "P1", "P2")}
    report["gates"] = gates
    report["P0_selective"] = p0_selective(qte, units, tuple(man["P0_keys"]))
    report["arms"] = {arm: {"accuracy_ambiguous": C.ambiguous_accuracy(qte, units[arm]),
                            "accuracy_ambiguous_unseen": C.ambiguous_accuracy(qte, units[arm], unseen),
                            "end_to_end": C.end_to_end_accuracy(qte, units[arm])} for arm in ARMS}
    report["comparisons"] = {
        "P0_vs_P2": C.increment_summary(qte, units["P0"], units["P2"]),
        "P1_vs_P2": C.increment_summary(qte, units["P1"], units["P2"]),
        "P2_vs_D": C.increment_summary(qte, units["P2"], units["D"]),
        "P0_vs_P0_SWAPPED": C.increment_summary(qte, units["P0"], units["P0_SWAPPED"]),
        "P0_then_D_vs_SWAPPED": C.increment_summary(qte, units["P0_then_D"], units["P0_then_D_SWAPPED"]),
        "P1_vs_P1_SWAPPED": C.increment_summary(qte, units["P1"], units["P1_SWAPPED"]),
        "R_vs_chance_groups": C.above_chance_values(qte, units["R"]),
        "P0_decided_share": round(sum(1 for q in qte if q["ambiguous"] and C.p0_choice(q["delta"], tuple(man["P0_keys"])) != 0)
                                  / max(1, sum(1 for q in qte if q["ambiguous"])), 6)}
    fams = sorted({str(q["family"]) for q in qte})
    report["by_family"] = {f: {arm: C.increment_summary(qte, units[arm], units["D"], (lambda q, f=f: str(q["family"]) == f))
                               for arm in ("P0", "P1")} for f in fams}
    report["P0_key_diagnostics"] = C.p0_key_diagnostics(qte, [q["delta"] for q in qte])
    report["transitions"] = sorted({q["transition"] for q in qte if q["ambiguous"]})
    report["donor_permutation_sha256"] = hashlib.sha256(json.dumps(pi).encode()).hexdigest()
    cls, why = classify(gates, amb_groups, man, not order_ok, converged)
    report["classification"] = {"classification": cls, "reason": why,
                                "ambiguous_groups": amb_groups,
                                "powered": amb_groups >= man["caps"]["target_ambiguous_groups"]}
    report["verdict"] = cls
    write(report)
    print(json.dumps({"verdict": cls, "reason": why, "ambiguous_groups": amb_groups,
                      "P0": gates["P0"]["accuracy_ambiguous"], "D": report["arms"]["D"]["accuracy_ambiguous"],
                      "P1": gates["P1"]["accuracy_ambiguous"], "P2": gates["P2"]["accuracy_ambiguous"]}))


if __name__ == "__main__":
    main()
