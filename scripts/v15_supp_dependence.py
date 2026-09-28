"""Item-2 v1.5 delivery addendum (a): dependence-aware sensitivity for gate C.

Supplementary. It never changes the official v1.5 result and was frozen
before any v1.5 score was read (records/ITEM2_V15_DELIVERY_ADDENDUM.md).

The official matched shuffle gives each test query the failure evidence of a
query in another test group, so the per-group differences behind gate C are
not independent. This procedure makes the dependence explicit.

Tier 1. Link two test groups when any query of one receives failure evidence
from a query of the other. Connected components are the independent units.
The exact sign-flip test runs over component sums of the per-group unit
differences, D+F_ASSOC minus D+F_SHUFFLED, never over groups inside a
component. It is resolved only with at least MIN_UNITS components.

Tier 2. Fixed blocks of test groups: within each family, sorted by group
digest, consecutive pairs (a block of three takes an odd remainder). Donors
are matched by the frozen rule inside the block only, so blocks share no
evidence and are the independent units. The official D+F_SHUFFLED model is
scored with these donors; the exact sign-flip test runs over block sums.
Tier 2 is always reported and governs only when tier 1 is unresolved.

Null assumption for both tiers, stated as an assumption: within a unit, the
query's own failure evidence and its donor's are exchangeable given what the
fixed models see, so the unit's paired difference is symmetric about zero.
The matched shuffle approximates this (donor demonstrations differ); it does
not guarantee it. Only whole units are sign-flipped.

Either way, a strong failure-conditioning mechanism claim still requires the
later independent-task causal controls.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

MIN_UNITS = 30
OUT = os.path.join(HERE, "outputs", "tti", "v15_supp_dependence.json")


def _evaluator():
    spec = importlib.util.spec_from_file_location(
        "ev15_supp", os.path.join(HERE, "scripts", "evaluate_v15_selection.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def donor_components(queries, pi):
    """Components of the group graph induced by donor links."""
    groups = sorted({q["group"] for q in queries})
    parent = {g: g for g in groups}

    def find(g):
        while parent[g] != g:
            parent[g] = parent[parent[g]]
            g = parent[g]
        return g
    for i, q in enumerate(queries):
        a, b = find(q["group"]), find(queries[pi[i]]["group"])
        if a != b:
            parent[max(a, b)] = min(a, b)
    comps = {}
    for g in groups:
        comps.setdefault(find(g), []).append(g)
    return sorted(comps.values())


def fixed_blocks(groups):
    """Blocks of group indices: within each family, sorted by group digest,
    consecutive pairs; an odd remainder joins the family's last block."""
    by_family = {}
    for i, g in enumerate(groups):
        by_family.setdefault(str(g.get("anchor_family")), []).append(i)
    blocks = []
    for fam in sorted(by_family):
        idx = sorted(by_family[fam], key=lambda i: groups[i]["group_digest"])
        fam_blocks = [idx[k:k + 2] for k in range(0, len(idx) - len(idx) % 2, 2)]
        if len(idx) % 2:
            if fam_blocks:
                fam_blocks[-1].append(idx[-1])
            else:
                fam_blocks.append([idx[-1]])
        blocks += fam_blocks
    return blocks


def block_shuffle(S, queries, blocks):
    """The frozen matching rule applied inside each block only. A block of a
    single group (a family with one group) has no valid donor and is left
    out of tier 2, with the count reported."""
    pi = [None] * len(queries)
    skipped = []
    for b in blocks:
        members = [i for i, q in enumerate(queries) if q["group"] in set(b)]
        if len(b) < 2:
            skipped.append(b)
            continue
        sub = [queries[i] for i in members]
        local = S.matched_shuffle(sub)
        for k, i in enumerate(members):
            pi[i] = members[local[k]]
    return pi, skipped


def unit_sums(diff_by_group, units):
    return [sum(diff_by_group[g] for g in unit) for unit in units]


def verdict(S, values):
    k = len(values)
    if k < MIN_UNITS:
        return {"units": k, "verdict": "UNRESOLVED", "p_signflip": None,
                "sum": sum(values)}
    p = S.signflip_p(values)
    ok = sum(values) > 0 and p < S.ALPHA
    return {"units": k, "verdict": "SUPPORTED" if ok else "NOT_SUPPORTED",
            "p_signflip": float(p), "sum": sum(values)}


def main():
    EV = _evaluator()
    S, L = EV.S, EV.L
    with open(EV.MANIFEST) as handle:
        man = json.load(handle)
    freeze = EV.verify_freeze(man)
    if freeze:
        raise SystemExit(f"freeze problems, refusing: {freeze}")
    train_inc, _ = L.first_admissions(EV.load(EV.TRAIN_DIR))
    test_inc, _ = L.first_admissions(EV.load(EV.TEST_DIR))
    train_groups = sorted((r["group"] for r in train_inc), key=lambda g: g["group_digest"])
    test_groups = sorted((r["group"] for r in test_inc), key=lambda g: g["group_digest"])
    if len(test_groups) < S.FLOOR_GROUPS:
        raise SystemExit("below the floor; nothing to analyse")
    qtrain, qtest = S.build_queries(train_groups), S.build_queries(test_groups)
    pi_train, pi_test = S.matched_shuffle(qtrain), S.matched_shuffle(qtest)
    std = S.standardizer_for(qtrain, "F_S7")
    models = {}
    for cond in ("D+F_ASSOC", "D+F_SHUFFLED"):
        models[cond], info = S.fit_pairs(S.design(qtrain, cond, std, pi_train), qtrain)
        if not info["converged"]:
            raise SystemExit(f"fit did not converge: {cond}")

    def units(cond, pi):
        scored = S.score_queries(models[cond], S.design(qtest, cond, std, pi), qtest)
        return S.group_units(scored, qtest)[0]

    ua = units("D+F_ASSOC", pi_test)
    us = units("D+F_SHUFFLED", pi_test)
    diff = {g: a - b for g, a, b in zip(sorted({q["group"] for q in qtest}), ua, us)}
    comps = donor_components(qtest, pi_test)
    tier1 = verdict(S, unit_sums(diff, comps))
    tier1["component_sizes"] = sorted((len(c) for c in comps), reverse=True)[:20]

    blocks = fixed_blocks(test_groups)
    pi_block, skipped = block_shuffle(S, qtest, blocks)
    kept = [b for b in blocks if len(b) >= 2]
    keep_q = [i for i in range(len(qtest)) if pi_block[i] is not None]
    sub = [qtest[i] for i in keep_q]
    remap = {i: k for k, i in enumerate(keep_q)}
    pi_sub = [remap[pi_block[i]] for i in keep_q]
    sc_a = S.score_queries(models["D+F_ASSOC"], S.design(sub, "D+F_ASSOC", std, pi_sub), sub)
    sc_s = S.score_queries(models["D+F_SHUFFLED"], S.design(sub, "D+F_SHUFFLED", std, pi_sub), sub)
    bdiff = {}
    for q, a, b in zip(sub, sc_a, sc_s):
        bdiff[q["group"]] = bdiff.get(q["group"], 0) + a["units"] - b["units"]
    tier2 = verdict(S, unit_sums(bdiff, kept))
    tier2.update({"blocks": len(kept), "single_group_blocks_left_out": len(skipped),
                  "shuffle_fidelity": S.shuffle_fidelity(sub, pi_sub)})

    governing = "tier1" if tier1["verdict"] != "UNRESOLVED" else "tier2"
    report = {
        "supplementary": True,
        "official_accuracy_recomputed": {
            "D+F_ASSOC": round(sum(ua) / (S.UNITS_PER_GROUP * len(ua)), 6),
            "D+F_SHUFFLED": round(sum(us) / (S.UNITS_PER_GROUP * len(us)), 6)},
        "tier1_official_shuffle_components": tier1,
        "tier2_fixed_block_shuffle": tier2,
        "governing_tier": governing,
        "dependence_aware_gate_C": (tier1 if governing == "tier1" else tier2)["verdict"],
        "mechanism_claim": "requires the later independent-task causal controls in every case",
        "null_assumption": "within a unit, own and donor failure evidence exchangeable given what the fixed models see; approximated by the matched shuffle, not guaranteed",
    }
    with open(sys.argv[1] if len(sys.argv) > 1 else OUT, "w") as handle:
        handle.write(json.dumps(report, indent=1, sort_keys=True) + "\n")
    print(json.dumps({k: report[k] for k in ("governing_tier", "dependence_aware_gate_C")}))


if __name__ == "__main__":
    main()
