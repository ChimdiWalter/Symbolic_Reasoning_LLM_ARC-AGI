"""Item-2 v1.6: dependence-aware sensitivity for gate C (supplementary).

The matched response shuffle gives each test query a donor from another test
group, so the per-group differences behind gate C are not independent. As in
the v1.5 delivery addendum, two tiers make the dependence explicit for the
P0 and P1 arms; this never changes the official result.

Tier 1: components of the donor graph of the official shuffle are the units;
exact sign flips over component sums; resolved only with MIN_UNITS units.
Tier 2: fixed within-family blocks of test groups (consecutive pairs by group
digest); donors matched by the frozen rule inside each block; exact sign
flips over block sums. Tier 2 governs only when tier 1 is unresolved.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
for v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[v] = "1"

from cora_arc2026 import v16_cfr as C                             # noqa: E402

S = C.S
MIN_UNITS = 30
OUT = os.path.join(HERE, "outputs", "tti", "v16_supp_dependence.json")


def _evaluator():
    spec = importlib.util.spec_from_file_location(
        "ev16_supp", os.path.join(HERE, "scripts", "evaluate_v16_cfr.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def donor_components(queries, pi):
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


def block_shuffle(queries, blocks):
    pi, skipped = [None] * len(queries), []
    for b in blocks:
        members = [i for i, q in enumerate(queries) if q["group"] in set(b)]
        amb = [i for i in members if queries[i]["ambiguous"]]
        if len(b) < 2 or len({queries[i]["group"] for i in amb}) < 2:
            skipped.append(b)
            continue
        sub = [queries[i] for i in members]
        try:
            local = C.response_shuffle(sub)
        except ValueError:
            skipped.append(b)
            continue
        for k, i in enumerate(members):
            pi[i] = members[local[k]]
    return pi, skipped


def verdict(values, alpha):
    k = len(values)
    if k < MIN_UNITS:
        return {"units": k, "verdict": "UNRESOLVED", "p_signflip": None, "sum": sum(values)}
    p = S.signflip_p(values)
    return {"units": k, "verdict": "SUPPORTED" if (sum(values) > 0 and p < alpha) else "NOT_SUPPORTED",
            "p_signflip": float(p), "sum": sum(values)}


def unit_sums(diff_by_group, units):
    return [sum(diff_by_group.get(g, 0) for g in unit) for unit in units]


def main():
    EV = _evaluator()
    with open(EV.MANIFEST) as handle:
        man = json.load(handle)
    if EV.verify_freeze(man):
        raise SystemExit("freeze problems, refusing")
    alpha = man["statistics"]["alpha"]
    train_inc, _ = EV.L.first_admissions(EV.load(EV.TRAIN_DIR))
    dev_groups = sorted((r["group"] for r in train_inc), key=lambda g: g["group_digest"])
    test_inc, _ = EV.L.first_admissions(EV.load(EV.TEST_DIR))
    test_groups = sorted((r["group"] for r in test_inc), key=lambda g: g["group_digest"])
    with open(EV.TRAIN_RESP) as handle:
        qdev = C.build_queries(dev_groups, EV.rmap(json.load(handle)))
    with open(EV.TEST_RESP) as handle:
        qte = C.build_queries(test_groups, EV.rmap(json.load(handle)))
    keep = set(EV.train_groups_of(dev_groups, qdev, man))
    qtr = [q for q in qdev if q["group"] in keep]
    fits = EV.fit_arms(qtr, man["P1_representation"])
    p0_keys = tuple(man["P0_keys"])
    units, _, pi, _ = EV.score_arms(fits, qte, p0_keys)
    report = {"supplementary": True, "arms": {}}
    comps = donor_components(qte, pi)
    blocks = fixed_blocks(test_groups)
    pi_block, skipped = block_shuffle(qte, blocks)
    kept_blocks = [b for b in blocks if any(pi_block[i] is not None for i, q in enumerate(qte) if q["group"] in set(b))]
    #  block-donor deltas for the two arms
    rva = C.d_rows(qte, fits["std_rep"])
    if fits["rep"] == "R2":
        _, dte = C.residualized(fits["qtr_rep"], qte, None, fits["std_rep"])
    else:
        dte = [q["delta"] for q in qte]
    dte_s = C.apply_scale(dte, fits["scale"])
    raw = [q["delta"] for q in qte]
    idx_ok = [i for i in range(len(qte)) if pi_block[i] is not None]
    sub = [qte[i] for i in idx_ok]
    remap = {i: k for k, i in enumerate(idx_ok)}
    pi_sub = [remap[pi_block[i]] for i in idx_ok]
    sh_raw = C.donor_deltas(sub, pi_sub, [raw[i] for i in idx_ok])
    sh_s = C.donor_deltas(sub, pi_sub, [dte_s[i] for i in idx_ok])
    for arm in ("P0", "P0_then_D", "P1"):
        own = units[arm]
        t1 = {}
        diff = {}
        for q, a, b in zip(qte, own, units[f"{arm}_SHUFFLED"]):
            if q["ambiguous"]:
                diff[q["group"]] = diff.get(q["group"], 0) + (a - b)
        t1 = verdict(unit_sums(diff, comps), alpha)
        t1["component_sizes"] = sorted((len(c) for c in comps), reverse=True)[:20]
        if arm == "P0":
            blk_units = [C.p0_units(q, d, p0_keys) for q, d in zip(sub, sh_raw)]
        elif arm == "P0_then_D":
            blk_units = [C.p0_units(q, d, p0_keys, fallback_units=units["D"][i])
                         for q, d, i in zip(sub, sh_raw, idx_ok)]
        else:
            blk_units = [s["units"] for s in C.score(fits["P1_SHUFFLED"], sub, [rva[i] for i in idx_ok], sh_s)]
        bdiff = {}
        for q, i, b in zip(sub, idx_ok, blk_units):
            if q["ambiguous"]:
                bdiff[q["group"]] = bdiff.get(q["group"], 0) + (own[i] - b)
        t2 = verdict(unit_sums(bdiff, kept_blocks), alpha)
        t2.update({"blocks": len(kept_blocks), "blocks_left_out": len(skipped),
                   "shuffle_fidelity": C.shuffle_fidelity(sub, pi_sub)})
        governing = "tier1" if t1["verdict"] != "UNRESOLVED" else "tier2"
        report["arms"][arm] = {"tier1_official_shuffle_components": t1,
                               "tier2_fixed_block_shuffle": t2, "governing_tier": governing,
                               "dependence_aware_gate_C": (t1 if governing == "tier1" else t2)["verdict"]}
    report["null_assumption"] = ("within a unit, own and donor responses exchangeable given what the "
                                 "fixed arms see; approximated by the matched shuffle, not guaranteed")
    report["mechanism_claim"] = "requires the later independent-task causal controls in every case"
    with open(sys.argv[1] if len(sys.argv) > 1 else OUT, "w") as handle:
        handle.write(json.dumps(report, indent=1, sort_keys=True) + "\n")
    print(json.dumps({a: report["arms"][a]["dependence_aware_gate_C"] for a in report["arms"]}))


if __name__ == "__main__":
    main()
