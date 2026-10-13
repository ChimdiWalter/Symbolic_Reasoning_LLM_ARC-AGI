"""CORA-NVG Stage A evaluation: guide choices against the engine's own
promoted-view runs.

  python -m cora_neural_view.evaluate --split dev
      -> outputs/neural_view_v0/stageA_<split>.json

Per decision, the stratum comes from the reference (PROMOTE outcomes of the
cut views):
- warranted: some promotion is CORRECT;
- misleading: none is CORRECT, some is FALSE_ACCEPT;
- no_help: all REJECT.

The guide's outcome is the reference outcome of its chosen view, and
NO_CHANGE stays REJECT:
- gain = CORRECT;
- harm = FALSE_ACCEPT (a new false acceptance);
- net = gains - harms.

Random arms are averaged over their seeds. Paired comparisons use exact
two-sided McNemar tests on gain and on harm.
"""
import argparse
import json
import math
import os
from collections import defaultdict

OUTDIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs", "neural_view_v0")


def mcnemar(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    p = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * p)


def evaluate(split):
    rows = [json.loads(line) for line in open(os.path.join(OUTDIR, "reference_rows.jsonl"))]
    ref = defaultdict(dict)
    for r in rows:
        if r["kind"] == "run" and r["condition"].startswith("PROMOTE_"):
            ref[r["task"]][r["condition"][len("PROMOTE_"):]] = r["outcome"]
    g = [json.loads(line) for line in open(os.path.join(OUTDIR, f"guide_rows_{split}.jsonl"))]
    tasks = sorted({x["task"] for x in g})
    missing = [t for t in tasks if any(v not in ref[t] for v in next(x["options"] for x in g if x["task"] == t))]
    stratum = {}
    for t in tasks:
        o = ref[t].values()
        stratum[t] = "warranted" if "CORRECT" in o else ("misleading" if "FALSE_ACCEPT" in o else "no_help")
    by_arm = defaultdict(dict)
    for x in g:
        by_arm[x["arm"]][x["task"]] = x
    res = {}
    for arm, d in by_arm.items():
        out = {"gain": {}, "harm": {}, "abstain": {}, "top1_useful": {}}
        for t, x in d.items():
            oc = ref[t].get(x["choice"]) if x["choice"] else "REJECT"
            out["gain"][t] = oc == "CORRECT"
            out["harm"][t] = oc == "FALSE_ACCEPT"
            out["abstain"][t] = x["choice"] is None
            out["top1_useful"][t] = bool(x["ranking"]) and ref[t].get(x["ranking"][0]) == "CORRECT"
        res[arm] = out
    # random arms: mean over seeds
    rnd = [a for a in res if a.startswith("R") and a[1:].isdigit()]

    def summary(arm):
        o = res[arm]
        n = len(tasks)
        war = [t for t in tasks if stratum[t] == "warranted"]
        non = [t for t in tasks if stratum[t] != "warranted"]
        gains, harms = sum(o["gain"].values()), sum(o["harm"].values())
        tries = n - sum(o["abstain"].values())
        return {"decisions": n, "gains": gains, "harms": harms, "net": gains - harms,
                "abstentions": n - tries, "precision": round(gains / tries, 3) if tries else None,
                "recall_warranted": round(sum(o["gain"][t] for t in war) / len(war), 3) if war else None,
                "abstain_when_not_warranted": round(sum(o["abstain"][t] for t in non) / len(non), 3) if non else None,
                "harm_when_not_warranted": sum(o["harm"][t] for t in non),
                "top1_useful_warranted": round(sum(o["top1_useful"][t] for t in war) / len(war), 3) if war else None}
    table = {a: summary(a) for a in sorted(res)}
    if rnd:
        table["R_mean"] = {k: (round(sum(table[a][k] for a in rnd) / len(rnd), 3) if isinstance(table[rnd[0]][k], (int, float)) else None)
                           for k in table[rnd[0]]}
    pairs = {}
    for a, b in [("D", "C"), ("D", "E"), ("D", "F"), ("D", "B1"), ("D", "B2"), ("D", "B3"), ("C", "B1"),
                 ("D-CF", "C-CF"), ("D-CF", "E-CF"), ("D-CF", "B1"), ("J-C", "B2"), ("J-D", "J-C"), ("J-D", "J-E")]:
        if a in res and b in res:
            pg = [(res[a]["gain"][t], res[b]["gain"][t]) for t in tasks]
            ph = [(res[a]["harm"][t], res[b]["harm"][t]) for t in tasks]
            bg, cg = sum(x and not y for x, y in pg), sum(y and not x for x, y in pg)
            bh, ch = sum(x and not y for x, y in ph), sum(y and not x for x, y in ph)
            pairs[f"{a} vs {b}"] = {"gain_only_first": bg, "gain_only_second": cg, "p_gain": round(mcnemar(bg, cg), 4),
                                   "harm_only_first": bh, "harm_only_second": ch, "p_harm": round(mcnemar(bh, ch), 4)}
    stab = None
    if "D" in res and "D_perm1" in res:
        stab = {"D_choice_agreement": round(sum(by_arm["D"][t]["choice"] == by_arm["D_perm1"][t]["choice"] for t in tasks) / len(tasks), 3),
                "C_choice_agreement": round(sum(by_arm["C"][t]["choice"] == by_arm["C_perm1"][t]["choice"] for t in tasks) / len(tasks), 3)
                if "C_perm1" in res else None}
    cost = {a: {"seconds": round(sum(x["seconds"] for x in d.values()), 1),
                "tokens": sum((x["info"] or {}).get("tokens", 0) for x in d.values())} for a, d in by_arm.items()}
    counts = {s: sum(v == s for v in stratum.values()) for s in ("warranted", "misleading", "no_help")}
    out = {"split": split, "decisions": len(tasks), "strata": counts, "reference_missing": missing,
           "arms": table, "paired": pairs, "label_permutation_stability": stab, "cost": cost,
           "per_decision": {t: {"stratum": stratum[t], "reference": ref[t],
                                "choices": {a: by_arm[a][t]["choice"] for a in sorted(by_arm)}} for t in tasks}}
    json.dump(out, open(os.path.join(OUTDIR, f"stageA_{split}.json"), "w"), indent=1)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", required=True)
    o = evaluate(ap.parse_args().split)
    print(json.dumps({k: o[k] for k in ("split", "decisions", "strata", "reference_missing")}))
    for a, v in o["arms"].items():
        print(f"{a:8s} gains {v['gains']:>5} harms {v['harms']:>5} net {v['net']:>6} abst {v['abstentions']:>5} "
              f"prec {v['precision']} recall {v['recall_warranted']} top1 {v['top1_useful_warranted']} "
              f"abst|not-warr {v['abstain_when_not_warranted']} harm|not-warr {v['harm_when_not_warranted']}")
    for k, v in o["paired"].items():
        print(k, v)
    print("stability", o["label_permutation_stability"])
