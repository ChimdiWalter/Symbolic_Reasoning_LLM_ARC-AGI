"""Sealed Item-2 v1.5 evaluation: conditional failure-conditioned selection.

Checks the freeze, the training resource (the 42 included v1.4 twin groups,
hash-listed) and the test corpus (new independent-input groups), then fits
every frozen condition on the training resource and scores the test groups,
runs the twin positive control by grouped cross-validation, applies the
frozen gates and ladder, and writes one deterministic report. If any
integrity check fails, no statistic is computed. Run twice; the two reports
must be byte-identical.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from cora_arc2026 import v14_loc as L                             # noqa: E402
from cora_arc2026 import v15_sel as S                             # noqa: E402

G, CV = S.G, S.CV
PROTOCOL = os.path.join(HERE, "docs",
                        "CORA_TTI_FAILURE_CONDITIONED_SELECTION_v1.5.md")
MANIFEST = os.path.join(HERE, "outputs", "tti",
                        "failure_conditioned_selection_v15_manifest.json")
TRAIN_DIR = os.path.join(HERE, "outputs", "tti", "v14_twin_corpus")
TEST_DIR = os.path.join(HERE, "outputs", "tti", "v15_test_corpus")
RECORD = re.compile(r"^full(\d{5})\.json$")
OUT_DEFAULT = os.path.join(HERE, "outputs", "tti", "v15_selection_report.json")
INTEGRITY_ONLY = "--integrity-only" in sys.argv[1:]


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
    return p


def load(dirname):
    names = sorted(n for n in os.listdir(dirname) if RECORD.match(n))
    out = []
    for n in names:
        with open(os.path.join(dirname, n)) as handle:
            out.append(json.load(handle))
    return out


def test_integrity(records, man, exclusion) -> list:
    """Every frozen law of the test corpus; any finding blocks the audit."""
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
    admitted = [r for r in records if r["admitted"]]
    seen_g, seen_t = set(), set()
    for r in admitted:
        g, slot, tag = r["group"], r["slot"], f"slot{r['slot']}"
        fam = S.FAMILIES[slot % len(S.FAMILIES)]
        if g["contrast_type"] != "FEATURE" or g["anchor_family"] != fam:
            p.append(f"{tag}:family_or_type")
        off = g["pair_seed"] - S.TEST_BASE - slot * S.SLOT_STRIDE
        attempt, rem = divmod(off, S.ATTEMPT_STRIDE)
        if rem or not 0 <= attempt < S.ATTEMPTS_PER_SLOT:
            p.append(f"{tag}:pair_seed")
            continue
        anchor = S.CD.sample_target(g["pair_seed"], G.parse_family(fam))
        contrast = G.contrast_target(anchor, "FEATURE", rotation=attempt)
        if [CV.digest(anchor), CV.digest(contrast)] != g["target_digests"]:
            p.append(f"{tag}:derivation")
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
        by = {(e["target_index"], e["replicate_index"]): e for e in eps}
        try:
            S.differing_step(by[(0, 0)]["target_tokens"], by[(1, 0)]["target_tokens"])
        except ValueError:
            p.append(f"{tag}:not_one_token")
        if len({json.dumps(e["structural_family"]) for e in eps}) != 1 or \
                len({e["schema_mdl"] for e in eps}) != 1:
            p.append(f"{tag}:family_or_mdl")
    return p


def run_condition(cond, q_fit, q_eval, std, pi_fit, pi_eval, eval_pi=None):
    rows_fit = S.design(q_fit, cond, std, pi_fit)
    model, info = S.fit_pairs(rows_fit, q_fit)
    rows_eval = S.design(q_eval, cond, std, eval_pi if eval_pi is not None else pi_eval)
    scored = S.score_queries(model, rows_eval, q_eval)
    return model, info, scored


def metrics(scored, queries):
    acc, nll, mar = S.group_units(scored, queries)
    n = len(scored)
    return {"acc_units": acc,
            "accuracy": round(sum(s["units"] for s in scored) / (2 * n), 6),
            "nll": round(sum(s["nll"] for s in scored) / n, 6),
            "margin": round(sum(s["margin"] for s in scored) / n, 6),
            "tie_rate": round(sum(1 for s in scored if s["tie"]) / n, 6),
            "order_invariant": all(s["order_invariant"] for s in scored),
            "group_nll": nll}


def paired(a_units, b_units):
    return [x - y for x, y in zip(a_units, b_units)]


def main():
    with open(MANIFEST) as handle:
        man = json.load(handle)
    freeze = verify_freeze(man)
    exclusion = S.load_exclusion()
    train_recs = load(TRAIN_DIR)
    train_inc, train_exc = L.first_admissions(train_recs)
    train_groups = sorted((r["group"] for r in train_inc), key=lambda g: g["group_digest"])
    test_recs = load(TEST_DIR)
    test_inc, test_exc = L.first_admissions(test_recs)
    test_groups = sorted((r["group"] for r in test_inc), key=lambda g: g["group_digest"])
    integrity = test_integrity(test_recs, man, exclusion)
    if len(train_groups) != man["training_resource"]["groups"]:
        integrity.append("training_group_count")
    if test_exc:
        integrity.append("test_duplicate_admission")
    tr_t = {d for g in train_groups for d in g["target_digests"]}
    tr_g = {g["group_digest"] for g in train_groups}
    te_t = {d for g in test_groups for d in g["target_digests"]}
    te_g = {g["group_digest"] for g in test_groups}
    overlap = sorted((tr_t & te_t) | (tr_g & te_g))
    report = {"protocol_doc_sha256": man["protocol_doc_sha256"],
              "train_groups": len(train_groups), "test_slots": len(test_recs),
              "test_groups": len(test_groups),
              "freeze_problems": freeze, "integrity_problems": integrity[:50],
              "train_test_overlap": overlap}
    leaks, qtrain, qtest = [], [], []
    if not (freeze or integrity or overlap):
        qtrain = S.build_queries(train_groups)
        qtest = S.build_queries(test_groups)
        for qs, groups in ((qtrain, train_groups), (qtest, test_groups)):
            for q in qs:
                g = groups[q["group"]]
                f = S.scan_view(q["views"], {
                    "digests": list(g["target_digests"]) + [g["group_digest"]],
                    "seeds": [g["pair_seed"]] + [e["seed"] for e in g["episodes"]]})
                if f:
                    leaks.append([g["group_digest"][:12], q["t"], q["r"], f])
    report["leaks"] = leaks[:50]
    if INTEGRITY_ONLY:
        ok = not (freeze or integrity or overlap or leaks)
        print(json.dumps({k: report[k] for k in ("train_groups", "test_slots", "test_groups",
                                                  "freeze_problems", "integrity_problems",
                                                  "train_test_overlap", "leaks")}, indent=1))
        print("INTEGRITY", "PASS" if ok else "FAIL")
        sys.exit(0 if ok else 1)
    if freeze or integrity or overlap or leaks:
        report["verdict"] = "AUDIT_BLOCKED"
        report["classification"] = {"classification": "MIXED_OR_INCONCLUSIVE",
                                    "reason": "integrity"}
        write(report)
        print("AUDIT BLOCKED", freeze, integrity[:10], overlap[:5], leaks[:5])
        return

    pi_train, pi_test = S.matched_shuffle(qtrain), S.matched_shuffle(qtest)
    results, fits = {}, {}
    for fblock in ("F_S7", "F_NOVSIG", "F_SEARCH"):
        std = S.standardizer_for(qtrain, fblock)
        conds = [c for c, (_, fb, _) in S.CONDITIONS.items() if fb == fblock]
        if fblock == "F_S7":
            conds = ["D", "D_AGG"] + conds
        for cond in conds:
            _, info, scored = run_condition(cond, qtrain, qtest, std, pi_train, pi_test)
            results[cond] = metrics(scored, qtest)
            results[cond]["_scored"] = scored
            fits[cond] = info
    order_ok = all(results[c]["order_invariant"] for c in results)

    # twin positive control: grouped cross-validation on the training resource
    folds = S.twin_folds(train_groups)
    twin = {c: [None] * len(train_groups) for c in S.PRIMARY + ("D+F_TWINSWAP",)}
    for k in range(S.TWIN_FOLDS):
        fit_g = [g for i, g in enumerate(train_groups) if folds[i] != k]
        held_i = [i for i in range(len(train_groups)) if folds[i] == k]
        held_g = [train_groups[i] for i in held_i]
        if not held_g:
            continue
        qf, qh = S.build_queries(fit_g), S.build_queries(held_g)
        std = S.standardizer_for(qf, "F_S7")
        pf, ph = S.matched_shuffle(qf), S.matched_shuffle(qh)
        swap = [next(j for j, o in enumerate(qh) if o["group"] == q["group"]
                     and o["r"] == q["r"] and o["t"] != q["t"]) for q in qh]
        models = {}
        for cond in S.PRIMARY:
            models[cond], _, scored = run_condition(cond, qf, qh, std, pf, ph)
            acc, _, _ = S.group_units(scored, qh)
            for local, gi in enumerate(held_i):
                twin[cond][gi] = acc[local]
        rows = S.design(qh, "D+F_SHUFFLED", std, swap)
        scored = S.score_queries(models["D+F_ASSOC"], rows, qh)
        acc, _, _ = S.group_units(scored, qh)
        for local, gi in enumerate(held_i):
            twin["D+F_TWINSWAP"][gi] = acc[local]

    test_block = {"acc": results["D+F_ASSOC"]["acc_units"],
                  "d_demo": paired(results["D+F_ASSOC"]["acc_units"], results["D"]["acc_units"]),
                  "d_shuffle": paired(results["D+F_ASSOC"]["acc_units"],
                                      results["D+F_SHUFFLED"]["acc_units"])}
    twin_block = {"acc": twin["D+F_ASSOC"],
                  "d_demo": paired(twin["D+F_ASSOC"], twin["D"]),
                  "d_shuffle": paired(twin["D+F_ASSOC"], twin["D+F_SHUFFLED"])}
    gate_out = S.gates(test_block, twin_block)
    cls = S.classify(gate_out, len(test_groups), True, order_ok, True, True)

    # descriptive: would plain verification decide the pair?
    decided = [q["other_fits"] is False for q in qtest]
    amb = [i for i, q in enumerate(qtest) if q["other_fits"] is True]
    verification = {"queries": len(qtest),
                    "other_candidate_fails": sum(decided),
                    "ambiguous_both_fit": len(amb)}
    for cond in S.PRIMARY:
        sc = results[cond]["_scored"]
        verification[f"accuracy_on_ambiguous_{cond}"] = round(
            sum(sc[i]["units"] for i in amb) / (2 * len(amb)), 6) if amb else None

    scale = S.UNITS_PER_GROUP
    report.update({
        "leaks": [],
        "order_invariant": order_ok,
        "conditions": {c: {k: v for k, v in m.items() if k not in ("_scored", "acc_units", "group_nll")}
                       for c, m in sorted(results.items())},
        "fits": fits,
        "test_comparisons": {
            "D+F_ASSOC_vs_chance": S.summary([u - scale // 2 for u in test_block["acc"]], scale),
            "D+F_ASSOC_vs_D": S.summary(test_block["d_demo"], scale),
            "D+F_ASSOC_vs_D+F_SHUFFLED": S.summary(test_block["d_shuffle"], scale),
            "F_ASSOC_vs_D": S.summary(paired(results["F_ASSOC"]["acc_units"], results["D"]["acc_units"]), scale),
            "D_vs_D_AGG": S.summary(paired(results["D"]["acc_units"], results["D_AGG"]["acc_units"]), scale),
            "D+F_NOVSIG_vs_D": S.summary(paired(results["D+F_NOVSIG"]["acc_units"], results["D"]["acc_units"]), scale),
            "D+F_NOVSIG_vs_shuffled": S.summary(paired(results["D+F_NOVSIG"]["acc_units"],
                                                       results["D+F_NOVSIG_SHUFFLED"]["acc_units"]), scale),
            "D+F_SEARCH_vs_D": S.summary(paired(results["D+F_SEARCH"]["acc_units"], results["D"]["acc_units"]), scale),
            "D+F_SEARCH_vs_shuffled": S.summary(paired(results["D+F_SEARCH"]["acc_units"],
                                                       results["D+F_SEARCH_SHUFFLED"]["acc_units"]), scale),
            "nll_D_minus_D+F_ASSOC": round(sum(a - b for a, b in zip(results["D"]["group_nll"],
                                                                      results["D+F_ASSOC"]["group_nll"]))
                                           / len(test_groups), 6),
            "nll_SHUFFLED_minus_D+F_ASSOC": round(sum(a - b for a, b in zip(results["D+F_SHUFFLED"]["group_nll"],
                                                                             results["D+F_ASSOC"]["group_nll"]))
                                                  / len(test_groups), 6)},
        "twin_control": {
            "accuracy": {c: round(sum(v) / (scale * len(v)), 6) for c, v in twin.items()},
            "D+F_ASSOC_vs_D": S.summary(twin_block["d_demo"], scale),
            "D+F_ASSOC_vs_D+F_SHUFFLED": S.summary(twin_block["d_shuffle"], scale),
            "D+F_ASSOC_vs_TWINSWAP": S.summary(paired(twin["D+F_ASSOC"], twin["D+F_TWINSWAP"]), scale)},
        "verification_diagnostic": verification,
        "gates": gate_out,
        "classification": cls,
        "verdict": cls["classification"],
    })
    write(report)
    print("CLASSIFICATION", cls["classification"], cls["reason"])


def write(report):
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    target = args[0] if args else OUT_DEFAULT
    with open(target, "w") as handle:
        handle.write(json.dumps(report, sort_keys=True, indent=1, default=float) + "\n")


if __name__ == "__main__":
    main()
