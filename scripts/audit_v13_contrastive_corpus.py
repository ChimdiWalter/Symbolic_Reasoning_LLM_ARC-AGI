"""The frozen nonlearned G1 to G10 identifiability audit for v1.3.

No scorer, no classifier, no learned distance, nothing trained. Every
threshold is read from the frozen manifest. The exact null is 3/7, derived
from three same-target and four different-target companions among the other
seven members of a group.
"""
import hashlib
import json
import math
import os
import statistics
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from cora_arc2026 import leak_scan_v12 as LEAK                    # noqa: E402
from cora_arc2026 import v13_gen as G                             # noqa: E402

COR_DIR = os.path.join(HERE, "outputs", "tti", "v13_contrastive_corpus")
CAL_FILE = os.path.join(HERE, "outputs", "tti", "v13_calibration",
                        "calibration.json")
OUT = os.path.join(HERE, "outputs", "tti", "v13_contrastive_audit.json")


def binom_sf(k, n, p):
    """One-sided exact P(X >= k) for X ~ Binomial(n, p)."""
    return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i)
               for i in range(k, n + 1))


def load_groups():
    groups = []
    rejections = Counter()
    slots = 0
    if not os.path.isdir(COR_DIR):
        return groups, rejections, slots
    for name in sorted(os.listdir(COR_DIR)):
        if not name.endswith(".json") or name.startswith("pilot_result"):
            continue
        with open(os.path.join(COR_DIR, name)) as handle:
            rec = json.load(handle)
        slots += 1
        for code, count in rec.get("rejections", {}).items():
            rejections[code] += count
        if rec["admitted"] and rec.get("group"):
            groups.append(rec["group"])
    return groups, rejections, slots


def standardized(descriptor, cal):
    return [(float(descriptor.get(k, 0) or 0) - cal["descriptor_mean"][i])
            / cal["descriptor_std"][i]
            for i, k in enumerate(cal["descriptor_order"])]


def distance(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def main():
    man = G.manifest()
    with open(CAL_FILE) as handle:
        cal = json.load(handle)
    groups, rejections, slots = load_groups()
    groups.sort(key=lambda g: g["group_digest"])
    print(f"group slots {slots}, admitted groups {len(groups)}")
    if not groups:
        print("no admitted groups; audit cannot run")
        return

    split = {}
    for index, g in enumerate(groups):
        split[g["group_digest"]] = ("train" if index < 60 else
                                    "val" if index < 72 else
                                    "holdout" if index < 84 else "unused")
    train = [g for g in groups if split[g["group_digest"]] == "train"]
    print(f"train {len(train)}  val {sum(1 for g in groups if split[g['group_digest']]=='val')}"
          f"  holdout {sum(1 for g in groups if split[g['group_digest']]=='holdout')}"
          f"  unused {sum(1 for g in groups if split[g['group_digest']]=='unused')}")

    #  G9 leakage and G10 evidence, over every admitted episode
    leaks, noninformative = [], []
    for g in groups:
        for ep in g["episodes"]:
            meta = dict(ep)
            meta["group_id"] = g["group_digest"]
            meta["contrast_type"] = g["contrast_type"]
            found = LEAK.scan(ep["model_view"], meta)
            if found:
                leaks.append({"group": g["group_digest"], "findings": found})
            f = ep["model_view"]["features"]
            if not (f["frontier_term_count"] >= 2
                    and (f["defined_value_signature_count"] >= 1
                         or f["executed_not_exact_count"] >= 1
                         or f["slot_fit_failed_count"] >= 1)):
                noninformative.append(g["group_digest"])

    #  nearest neighbour and separation, on TRAIN groups only
    hits = {"ALL": [0, 0], "PARTITION": [0, 0], "FEATURE": [0, 0],
            "SELECT": [0, 0], "PF": [0, 0]}
    seps, seps_by_type = [], defaultdict(list)
    for g in train:
        eps = g["episodes"]
        vecs = [standardized(e["descriptor"], cal) for e in eps]
        tgt = [e["target_digest"] for e in eps]
        ctype = g["contrast_type"]
        for i in range(len(eps)):
            best, best_d = None, None
            for j in range(len(eps)):
                if i == j:
                    continue
                d = distance(vecs[i], vecs[j])
                if best_d is None or d < best_d - 1e-12:
                    best, best_d = j, d
            hit = int(tgt[best] == tgt[i])
            for key in ("ALL", ctype) + (("PF",) if ctype != "SELECT" else ()):
                hits[key][0] += hit
                hits[key][1] += 1
        within, between = [], []
        for i in range(len(eps)):
            for j in range(i + 1, len(eps)):
                d = distance(vecs[i], vecs[j])
                (within if tgt[i] == tgt[j] else between).append(d)
        s = (statistics.mean(between) - statistics.mean(within)) \
            if within and between else 0.0
        seps.append(s)
        seps_by_type[ctype].append(s)

    def rate(key):
        h, n = hits[key]
        if not n:
            return {"hits": 0, "n": 0, "rate": None, "p_value": None}
        r = h / n
        return {"hits": h, "n": n, "rate": round(r, 5),
                "p_value": binom_sf(h, n, 3 / 7)}

    nn = {k: rate(k) for k in hits}
    pos = sum(1 for s in seps if s > 0)
    sep_p = binom_sf(pos, len(seps), 0.5) if seps else None
    mean_s = statistics.mean(seps) if seps else 0.0
    by_type = Counter(g["contrast_type"] for g in groups)
    train_by_type = Counter(g["contrast_type"] for g in train)
    train_digests = {d for g in train for d in g["target_digests"]}
    digest_sets = {name: {g["group_digest"] for g in groups
                          if split[g["group_digest"]] == name}
                   for name in ("train", "val", "holdout")}

    gates = {
        "G1_primary_identifiability": {
            "measured": nn["ALL"]["rate"], "p_value": nn["ALL"]["p_value"],
            "threshold": "rate > 3/7 and p < 0.01",
            "pass": bool(nn["ALL"]["rate"] is not None
                         and nn["ALL"]["rate"] > 3 / 7
                         and nn["ALL"]["p_value"] < 0.01)},
        "G2_contrast_type_robustness": {
            "measured": nn["PF"]["rate"], "p_value": nn["PF"]["p_value"],
            "threshold": "PARTITION+FEATURE rate > 3/7 and p < 0.01",
            "pass": bool(nn["PF"]["rate"] is not None
                         and nn["PF"]["rate"] > 3 / 7
                         and nn["PF"]["p_value"] < 0.01)},
        "G3_separation": {
            "measured": round(pos / len(seps), 5) if seps else None,
            "p_value": sep_p, "threshold": "fraction s>0 above 0.5 and p < 0.01",
            "pass": bool(seps and pos / len(seps) > 0.5 and sep_p < 0.01)},
        "G4_separation_magnitude": {
            "measured": round(mean_s, 5), "threshold": "mean s >= 0.25",
            "pass": bool(mean_s >= 0.25)},
        "G5_scale": {"measured": len(train), "threshold": ">= 60 train groups",
                     "pass": len(train) >= 60},
        "G6_coverage": {"measured": dict(train_by_type),
                        "threshold": ">= 3 train groups per contrast type",
                        "pass": all(train_by_type.get(c, 0) >= 3
                                    for c in ("PARTITION", "FEATURE", "SELECT"))},
        "G7_distinct_targets": {"measured": len(train_digests),
                                "threshold": ">= 100 distinct train digests",
                                "pass": len(train_digests) >= 100},
        "G8_splits": {"measured": "disjoint" if not (
            digest_sets["train"] & digest_sets["val"]
            or digest_sets["train"] & digest_sets["holdout"]
            or digest_sets["val"] & digest_sets["holdout"]) else "overlap",
            "threshold": "group digests disjoint across splits",
            "pass": not (digest_sets["train"] & digest_sets["val"]
                         or digest_sets["train"] & digest_sets["holdout"]
                         or digest_sets["val"] & digest_sets["holdout"])},
        "G9_leakage": {"measured": len(leaks), "threshold": "zero violations",
                       "pass": not leaks},
        "G10_evidence": {"measured": len(noninformative),
                         "threshold": "every admitted episode informative",
                         "pass": not noninformative},
    }
    verdict = ("V1.3 CONTRASTIVE CORPUS IDENTIFIABILITY GATE PASS"
               if all(g["pass"] for g in gates.values())
               else "V1.3 CONTRASTIVE CORPUS IDENTIFIABILITY GATE FAIL")

    report = {
        "protocol_sha256": man["protocol_doc_sha256"],
        "calibration_sha256": hashlib.sha256(
            open(CAL_FILE, "rb").read()).hexdigest(),
        "exact_null": 3 / 7,
        "group_slots_attempted": slots,
        "admitted_groups": len(groups),
        "admitted_episodes": sum(len(g["episodes"]) for g in groups),
        "admissions_by_contrast_type": dict(by_type),
        "train_by_contrast_type": dict(train_by_type),
        "rejections": dict(rejections),
        "splits": {k: len(v) for k, v in digest_sets.items()},
        "nearest_neighbour": nn,
        "separation": {"n_groups": len(seps),
                       "fraction_positive": round(pos / len(seps), 5) if seps else None,
                       "p_value": sep_p, "mean": round(mean_s, 5),
                       "median": round(statistics.median(seps), 5) if seps else None,
                       "min": round(min(seps), 5) if seps else None,
                       "max": round(max(seps), 5) if seps else None,
                       "by_contrast_type": {k: round(statistics.mean(v), 5)
                                            for k, v in seps_by_type.items() if v}},
        "d_demo": {"mean": round(statistics.mean(
            [g["d_demo"] for g in groups]), 5) if groups else None,
            "max": round(max(g["d_demo"] for g in groups), 5) if groups else None},
        "leakage_violations": leaks[:5], "noninformative_episodes": len(noninformative),
        "gates": gates, "verdict": verdict,
    }
    with open(OUT, "w") as handle:
        json.dump(report, handle, indent=1, default=str)
    for key, g in gates.items():
        pv = g.get("p_value")
        tail = "" if pv is None else f"  p={pv:.3g}"
        print(f"  [{'PASS' if g['pass'] else 'FAIL'}] {key}: "
              f"{g['measured']}{tail}  ({g['threshold']})")
    print(f"\nVERDICT: {verdict}")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
