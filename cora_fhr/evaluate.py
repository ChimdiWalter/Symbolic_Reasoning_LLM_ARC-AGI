"""Independent evaluator for CORA-FHR: the only FHR code that reads answers (protocol section 6).

  python -m cora_fhr.evaluate --corpus c4_dev [--tag ...]   -> outputs/cora_fhr/eval_<corpus><tag>.json

For every task and arm it reports:
- the committed output, certified by A or by an installed extension;
- whether that output is correct on the held-out test.

A gain is a task where the arm's committed output is correct and A had no correct certified output.

Counted gains, for P1, also require:
- an extension certificate (`certified_by` "<arm>+extension");
- the operator novelty class NEW_COMPOSITION;
- every adaptive-LOO fold SUCCESS;
- the accepted program using the extension (P6, P7).

Harms are new certified-wrong outputs and lost A-correct outputs. P1-P7 and the decision label are computed
for the final split. The development split reports the same numbers, labelled DEVELOPMENT, with no decision.
"""
import argparse
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
OUT = os.path.join(HERE, "outputs", "cora_fhr")
PARAMS = os.path.join(HERE, "records", "cora_fhr_v1_frozen_parameters.json")


def answers(corpus):
    if corpus in ("c4_dev", "c4_final"):
        d = json.load(open(os.path.join(OUT, f"{corpus}.json")))
        return {k: ([b for _a, b in t["test"]], t["family"]) for k, t in d["tasks"].items()}
    if corpus == "dev60":
        from cora_funnel.evaluate import answers as fa
        return fa("dev60")
    raise ValueError(corpus)


def exact(preds, outs):
    return isinstance(preds, list) and len(preds) == len(outs) and all(p is not None and p == o for p, o in zip(preds, outs))


def counted(r):
    """An extension-certified commit that meets P6/P7 and is NEW_COMPOSITION."""
    sel = r.get("selected") or {}
    folds = r.get("folds") or []
    return (str(r.get("certified_by", "")).endswith("+extension") and (sel.get("novelty") or {}).get("class") == "NEW_COMPOSITION"
            and folds and all(f.get("class") == "SUCCESS" for f in folds) and (r.get("top") or {}).get("uses"))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--tag", default="")
    a = ap.parse_args(argv)
    rows = [json.loads(l) for l in open(os.path.join(OUT, f"rows_{a.corpus}{a.tag}.jsonl"))]
    ans = answers(a.corpus)
    per, fam_tab = [], collections.defaultdict(lambda: collections.Counter())
    for row in rows:
        outs, fam = ans[row["key"]]
        A = row["arms"]["A"]
        a_ok = bool(A["certified"]) and exact(A["committed"], outs)
        rec = {"key": row["key"], "family": fam, "A_correct": a_ok, "arms": {}}
        for arm, r in row["arms"].items():
            ok = r.get("committed") is not None and exact(r["committed"], outs)
            by = r.get("certified_by") if arm in "CDE" else ("A" if r.get("certified") else None)
            ext_cert = str(by or "").endswith("+extension")
            rec["arms"][arm] = {"correct": ok, "certified_by": by, "outcome": r.get("outcome"),
                                "gain": ok and not a_ok, "counted_gain": bool(ok and not a_ok and arm in "CDE" and counted(r)),
                                "new_certified_wrong": bool(ext_cert and not ok),
                                "lost_A_correct": bool(a_ok and not ok),
                                "selected": (r.get("selected") or {}).get("pretty"),
                                "novelty": ((r.get("selected") or {}).get("novelty") or {}).get("class"),
                                "cpu_s": r.get("cpu_s")}
            fam_tab[fam][f"{arm}_correct"] += ok
            fam_tab[fam][f"{arm}_counted_gain"] += rec["arms"][arm]["counted_gain"]
        fam_tab[fam]["tasks"] += 1
        per.append(rec)
    arms = sorted({x for r in per for x in r["arms"]})
    tot = {arm: {"correct": sum(r["arms"][arm]["correct"] for r in per if arm in r["arms"]),
                 "gains": sum(r["arms"][arm]["gain"] for r in per if arm in r["arms"]),
                 "counted_gains": sum(r["arms"][arm]["counted_gain"] for r in per if arm in r["arms"]),
                 "new_certified_wrong": sum(r["arms"][arm]["new_certified_wrong"] for r in per if arm in r["arms"]),
                 "lost_A_correct": sum(r["arms"][arm]["lost_A_correct"] for r in per if arm in r["arms"]),
                 "outcomes": dict(collections.Counter(r["arms"][arm]["outcome"] for r in per if arm in r["arms"])),
                 "cpu_h": round(sum((r["arms"][arm]["cpu_s"] or 0) for r in per if arm in r["arms"]) / 3600, 2)}
           for arm in arms}
    out = {"corpus": a.corpus, "tier": "FINAL" if a.corpus == "c4_final" else "DEVELOPMENT",
           "tasks": len(per), "arms": tot, "by_family": {k: dict(v) for k, v in sorted(fam_tab.items())}, "per_task": per}
    if a.corpus == "c4_final":
        th = json.load(open(PARAMS))["thresholds"]
        g = [r for r in per if r["family"].startswith("F")]
        E = {r["key"] for r in g if r["arms"].get("E", {}).get("counted_gain")}
        famE = {r["family"] for r in g if r["key"] in E}
        B_also = sum(1 for r in g if r["key"] in E and r["arms"].get("B", {}).get("correct"))
        C_n = sum(1 for r in g if r["arms"].get("C", {}).get("counted_gain"))
        D_n = sum(1 for r in g if r["arms"].get("D", {}).get("counted_gain"))
        harms = tot.get("E", {}).get("new_certified_wrong", 0) + tot.get("E", {}).get("lost_A_correct", 0)
        P = {"P1": len(E) >= th["P1_min_gains"] and len(famE) >= th["P1_min_families"],
             "P2": B_also <= th["P2_max_gains_also_solved_by_B"],
             "P3": len(E) - C_n >= th["P3_min_margin_over_C"],
             "P4": len(E) - D_n >= th["P4_min_margin_over_D"],
             "P5": harms == 0, "P6": True, "P7": True}           # P6/P7 are part of `counted`
        # extension-certified gains through an already-available operator (Amendment 1, label-order clarification)
        sel_gains = sum(1 for r in g if r["arms"].get("E", {}).get("gain")
                        and str(r["arms"]["E"].get("certified_by", "")).endswith("+extension")
                        and r["arms"]["E"].get("novelty") in ("AVAILABLE_REACH", "AVAILABLE_NATIVE"))
        if not P["P5"]:
            label = "UNSAFE"
        elif len(E) < 3:
            label = "SELECTION_ONLY" if sel_gains >= 3 else "NO_GAIN"
        elif not P["P2"]:
            label = "SEARCH_SUFFICIENT"
        elif P["P1"] and P["P4"] and not P["P3"]:
            label = "COMPOSITIONAL_GROWTH_WITHOUT_EVIDENCE_EFFECT"
        elif all(P.values()):
            label = "CAPABILITY_GROWTH_DEMONSTRATED"
        else:
            label = "MORE_EVIDENCE_REQUIRED"
        out["criteria"] = {"E_counted_gains": len(E), "E_families": sorted(famE), "B_also": B_also, "C_counted": C_n,
                           "D_counted": D_n, "E_harms": harms, "P": P, "label": label}
    json.dump(out, open(os.path.join(OUT, f"eval_{a.corpus}{a.tag}.json"), "w"), indent=1)
    print(json.dumps({k: v for k, v in out.items() if k != "per_task"}, indent=1))


if __name__ == "__main__":
    main()
