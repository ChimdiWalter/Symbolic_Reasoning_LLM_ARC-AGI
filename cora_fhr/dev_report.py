"""Development integrity-gate report for CORA-FHR (evaluator side; reads eval_c4_dev*.json and the rows).

  python -m cora_fhr.dev_report [--tag ...]   -> outputs/cora_fhr/dev_report<tag>.json

It reports:
- per family and arm: outcomes, correct, gains, counted gains, new certified-wrong, lost A-correct;
- end-to-end fold evidence: every fold that ran an INSTALLED extension, with its selection, same_as_full,
  acceptance, use and held-out exactness;
- novelty classes of every proposal;
- CPU per arm, and f_B = the median over development G tasks of E's CPU divided by A's CPU.
"""
import argparse
import collections
import json
import os
import statistics as st
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
OUT = os.path.join(HERE, "outputs", "cora_fhr")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="")
    a = ap.parse_args(argv)
    ev = json.load(open(os.path.join(OUT, f"eval_c4_dev{a.tag}.json")))
    rows = {json.loads(l)["key"]: json.loads(l) for l in open(os.path.join(OUT, f"rows_c4_dev{a.tag}.jsonl"))}
    fam_arm = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    novelty = collections.defaultdict(collections.Counter)
    folds_installed, ratios = [], []
    for t in ev["per_task"]:
        fam = t["family"]
        for arm, r in t["arms"].items():
            c = fam_arm[fam][arm]
            c["tasks"] += 1
            c[f"outcome:{r['outcome'] or ('certified' if r['certified_by'] else 'none')}"] += 1
            for k in ("correct", "gain", "counted_gain", "new_certified_wrong", "lost_A_correct"):
                c[k] += bool(r[k])
        row = rows[t["key"]]
        for arm in ("C", "C2", "D", "E"):
            rr = row["arms"].get(arm)
            if not rr:
                continue
            for p in rr.get("proposals") or []:
                novelty[arm][(p.get("novelty") or {}).get("class")] += 1
            for f in rr.get("folds") or []:
                if f.get("accepted") is not None:                       # this fold installed and ran an extension
                    folds_installed.append({"task": t["key"], "arm": arm, "fold": f["fold"], "class": f["class"],
                                            "selected": (f.get("selected") or {}).get("pretty"),
                                            "same_as_full": f.get("same_as_full"), "accepted": f.get("accepted"),
                                            "uses": f.get("uses"), "heldout_exact": f.get("heldout_exact"),
                                            "restored": f.get("restored")})
        if fam.startswith("D") and "E" in row["arms"]:
            a_cpu, e_cpu = row["arms"]["A"]["cpu_s"], row["arms"]["E"].get("cpu_s")
            if a_cpu and e_cpu is not None:
                ratios.append((e_cpu + a_cpu) / a_cpu)                   # E's total = A's run plus its own work
    out = {"tier": "DEVELOPMENT", "arms_total": ev["arms"],
           "by_family": {f: {arm: dict(c) for arm, c in arms.items()} for f, arms in sorted(fam_arm.items())},
           "novelty_of_proposals": {arm: dict(c) for arm, c in novelty.items()},
           "folds_with_installed_extension": folds_installed,
           "fold_classes": dict(collections.Counter(f["class"] for f in folds_installed)),
           "f_B": {"ratios": [round(r, 2) for r in ratios], "median": round(st.median(ratios), 2) if ratios else None}}
    json.dump(out, open(os.path.join(OUT, f"dev_report{a.tag}.json"), "w"), indent=1)
    print(json.dumps({k: v for k, v in out.items() if k != "folds_with_installed_extension"}, indent=1))
    print("folds with an installed extension:", len(folds_installed))
    for f in folds_installed:
        print("  ", f)


if __name__ == "__main__":
    main()
