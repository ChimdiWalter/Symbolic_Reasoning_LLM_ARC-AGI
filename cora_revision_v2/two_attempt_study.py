"""How would v2's prediction tiers interact with native's two Kaggle attempts? EVALUATOR-SIDE study on exposed tasks.
No submission is made.

  python -m cora_revision_v2.two_attempt_study   -> outputs/cora_revision_v2/two_attempt_study_<tag>.json

**Native attempts** are the recorded ones:
- the 240-task Kaggle committed run (`outputs/kaggle_deploy/cora_fhr_v1/run_v1/submission_native.json`) for standin58;
- the frozen native_v1 notebook on dev60 (`outputs/funnel_v0/harness_dev60/working/submission.json`).

v2's rows come from the engineering run. Only CERTIFIED and EXPLORATORY predictions are used; DISCOURAGED and NONE
never enter an attempt.

**Policies:**
- P0: native only.
- CERT: a v2 CERTIFIED answer becomes attempt 1. Native's attempt 1 moves to attempt 2.
- FILL: a v2 EXPLORATORY answer goes only into an attempt 2 that is a [[0]] placeholder or duplicates attempt 1.
- REPLACE2: a v2 EXPLORATORY answer always replaces native's attempt 2.
- V2FIRST: a v2 EXPLORATORY answer becomes attempt 1. Native's attempt 1 moves to attempt 2.

**Scoring.** A test output counts if either attempt equals it. A task scores the fraction of its test outputs that
count, as on Kaggle. Gains and losses are reported against P0. Certified and exploratory contributions stay separate.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
OUT = os.path.join(HERE, "outputs", "cora_revision_v2")
NATIVE = {"standin58": os.path.join(HERE, "outputs", "kaggle_deploy", "cora_fhr_v1", "run_v1", "submission_native.json"),
          "dev60": os.path.join(HERE, "outputs", "funnel_v0", "harness_dev60", "working", "submission.json")}
POLICIES = ("P0", "CERT", "FILL", "REPLACE2", "V2FIRST")


def merged(policy, nat, row):
    """Per test output: the two attempts submitted under `policy`."""
    tier, att = row.get("tier"), row.get("attempts") or []
    out = []
    for i, a in enumerate(nat):
        a1, a2 = a["attempt_1"], a["attempt_2"]
        v = att[i][0] if i < len(att) and att[i] else None
        if policy == "CERT" and tier == "CERTIFIED" and v is not None:
            a1, a2 = v, a1
        elif tier == "EXPLORATORY" and v is not None:
            if policy == "FILL" and (a2 == [[0]] or a2 == a1):
                a2 = v
            elif policy == "REPLACE2":
                a2 = v
            elif policy == "V2FIRST":
                a1, a2 = v, a1
        out.append((a1, a2))
    return out


def study(corpus, tag="eng"):
    from cora_fhr.evaluate import answers
    nat = json.load(open(NATIVE[corpus]))
    rows = {json.loads(l)["key"]: json.loads(l) for l in open(os.path.join(OUT, f"rows_{corpus}_{tag}.jsonl")) if l.strip()}
    ans = answers(corpus)
    res = {p: {"score": 0.0, "tasks_full": 0, "gained": [], "lost": []} for p in POLICIES}
    base = {}
    for k in sorted(rows):
        truth = ans[k][0]
        for p in POLICIES:
            m = merged(p, nat[k], rows[k])
            hit = [o in pair for o, pair in zip(truth, m)]
            s = sum(hit) / len(truth)
            res[p]["score"] += s
            res[p]["tasks_full"] += all(hit)
            if p == "P0":
                base[k] = s
            elif s > base[k]:
                res[p]["gained"].append(k)
            elif s < base[k]:
                res[p]["lost"].append(k)
    for p in POLICIES:
        res[p]["score"] = round(res[p]["score"], 3)
    n_dup = sum(a["attempt_2"] == a["attempt_1"] for k in rows for a in nat[k])
    n_ph = sum(a["attempt_2"] == [[0]] for k in rows for a in nat[k])
    return {"corpus": corpus, "n_tasks": len(rows), "native_attempt2_duplicates": n_dup, "native_attempt2_placeholders": n_ph,
            "policies": res}


def main():
    out = {"label": "EVALUATOR-SIDE, exposed tasks, in-sample; no submission",
           "studies": [study(c) for c in ("standin58", "dev60") if os.path.exists(os.path.join(OUT, f"rows_{c}_eng.jsonl"))]}
    json.dump(out, open(os.path.join(OUT, "two_attempt_study_eng.json"), "w"), indent=1)
    for s in out["studies"]:
        print(s["corpus"], s["n_tasks"], "dup", s["native_attempt2_duplicates"], "placeholder", s["native_attempt2_placeholders"])
        for p, r in s["policies"].items():
            print(f"  {p:9s} score {r['score']:6.3f} full {r['tasks_full']:3d} gained {r['gained']} lost {r['lost']}")


if __name__ == "__main__":
    main()
