"""Compact development report: one table per family and arm, plus failure-type separation (DEVELOPMENT).

  python -m cora_fhr.dev_table [--corpus c4_dev_v2]   -> outputs/cora_fhr/dev_table_<corpus>.md / .json

Sources: the run (A, C, D, E), the B run (_B), the C' run (_C2), the ungated refold (_refold_ungated) and
the C'-vs-E audit, whichever exist. The answers come from cora_fhr.evaluate.answers, the evaluator side.
"""
import argparse
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
OUT = os.path.join(HERE, "outputs", "cora_fhr")


def rows(path):
    return {json.loads(l)["key"]: json.loads(l) for l in open(path)} if os.path.exists(path) else {}


def main(argv=None):
    from cora_fhr.evaluate import answers
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="c4_dev_v2")
    a = ap.parse_args(argv)
    ans = answers(a.corpus)
    main_rows = rows(os.path.join(OUT, f"rows_{a.corpus}.jsonl"))
    extra = {"B": rows(os.path.join(OUT, f"rows_{a.corpus}_B.jsonl")), "C2": rows(os.path.join(OUT, f"rows_{a.corpus}_C2.jsonl"))}
    refold = rows(os.path.join(OUT, f"rows_{a.corpus}_refold_ungated.jsonl"))
    audit_p = os.path.join(OUT, f"c2_audit_{a.corpus}.json")
    audit = {t["key"]: t for t in json.load(open(audit_p))["tasks"]} if os.path.exists(audit_p) else {}
    T = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    ftype = collections.defaultdict(collections.Counter)
    for key, r in main_rows.items():
        outs, fam = ans[key]
        a_ok = bool(r["arms"]["A"]["certified"]) and r["arms"]["A"]["committed"] == outs
        arms = dict(r["arms"])
        for x, src in extra.items():
            if key in src and x in src[key]["arms"]:
                arms[x] = src[key]["arms"][x]
        for arm, x in arms.items():
            c = T[fam][arm]
            c["attempted"] += 1
            if arm in ("A", "B"):
                c["certified"] += bool(x.get("certified"))
                c["correct"] += bool(x.get("certified")) and x.get("committed") == outs
                c["cpu_s"] += x.get("cpu_s") or 0
                continue
            top = x.get("top") or {}
            sel = (x.get("selected") or {}).get("novelty") or {}
            ext_cert = str(x.get("certified_by") or "").endswith("+extension")
            c["proposed"] += bool(x.get("proposals"))
            c["installed"] += bool(top)
            c["top_accepted_and_uses"] += bool(top.get("accepted") and top.get("uses"))
            c["full_LOO_passed"] += x.get("outcome") == "CERTIFIED_WITH_EXTENSION"
            c["ext_certified_correct"] += ext_cert and x.get("committed") == outs
            c["ext_certified_wrong"] += ext_cert and x.get("committed") != outs
            c["abstained_tie"] += x.get("outcome") == "ABSTAIN_TIE" or any(f.get("class") == "ABSTAIN_TIE" for f in x.get("folds") or [])
            c["lost_A_correct"] += a_ok and x.get("committed") != outs
            if sel.get("class"):
                c[f"novelty:{sel['class']}"] += 1
            c["cpu_s"] += x.get("cpu_s") or 0
            rf = (refold.get(key) or {}).get("arms", {}).get(arm)
            if rf:
                c["ungated_certified_correct"] += str(rf.get("certified_by") or "").endswith("+extension") and rf.get("committed") == outs
                c["ungated_certified_wrong"] += str(rf.get("certified_by") or "").endswith("+extension") and rf.get("committed") != outs
            folds = x.get("folds") or []
            if top.get("accepted") and top.get("uses") and x.get("outcome") != "ABSTAIN_TIE" and folds and not r["arms"]["A"]["certified"]:
                if all(f.get("accepted") and f.get("uses") and f.get("heldout_exact") for f in folds):
                    c["no_fold_tie_certified_correct"] += top.get("predictions") == outs
                    c["no_fold_tie_certified_wrong"] += top.get("predictions") != outs
        e = r["arms"].get("E", {})
        au = audit.get(key, {})
        if r["arms"]["A"]["certified"]:
            kind = "native_certified"
        elif au and not au.get("growth_correspondences"):
            kind = "matching (no growth correspondence)"
        elif e.get("outcome") == "NO_PROPOSAL":
            kind = "construction (evidence, no fitting operator)"
        elif e.get("outcome") in ("ENGINE_REJECTION", "ROUTING_FAILURE"):
            kind = "verification: native gate"
        elif e.get("outcome") in ("LOO_FAILURE", "ABSTAIN_TIE"):
            kind = "verification: adaptive LOO / tie"
        elif e.get("outcome") == "CERTIFIED_WITH_EXTENSION":
            kind = "PASSED"
        else:
            kind = str(e.get("outcome"))
        ftype[fam][kind] += 1
    cols = ["attempted", "certified", "correct", "proposed", "installed", "top_accepted_and_uses", "full_LOO_passed",
            "ext_certified_correct", "ext_certified_wrong", "abstained_tie", "lost_A_correct",
            "no_fold_tie_certified_correct", "no_fold_tie_certified_wrong", "ungated_certified_correct", "ungated_certified_wrong", "cpu_s"]
    lines = ["| family | arm | " + " | ".join(cols) + " | novelty |", "|" + "---|" * (len(cols) + 3)]
    for fam in sorted(T):
        for arm in ("A", "B", "C", "C2", "C3", "D", "E"):
            if arm not in T[fam]:
                continue
            c = T[fam][arm]
            nov = ", ".join(f"{k.split(':')[1]} {v}" for k, v in sorted(c.items()) if k.startswith("novelty:"))
            lines.append(f"| {fam} | {arm} | " + " | ".join(str(round(c[k] / 3600, 2)) + "h" if k == "cpu_s" else str(c[k]) for k in cols) + f" | {nov} |")
    lines += ["", "| family | arm E: failure type | tasks |", "|---|---|---|"]
    for fam in sorted(ftype):
        for k, v in sorted(ftype[fam].items()):
            lines.append(f"| {fam} | {k} | {v} |")
    md = "\n".join(lines)
    open(os.path.join(OUT, f"dev_table_{a.corpus}.md"), "w").write(md + "\n")
    json.dump({"table": {f: {arm: dict(c) for arm, c in d.items()} for f, d in T.items()},
               "failure_types": {f: dict(c) for f, c in ftype.items()}},
              open(os.path.join(OUT, f"dev_table_{a.corpus}.json"), "w"), indent=1)
    print(md)


if __name__ == "__main__":
    main()
