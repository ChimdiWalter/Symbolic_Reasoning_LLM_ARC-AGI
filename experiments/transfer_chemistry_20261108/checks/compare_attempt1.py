"""Post-run check (the delta reviewer's optional check): the rerun's first family records must equal attempt 1's
records, field by field, ignoring cpu_s. Prints and writes only the verdict, never an outcome."""
import json, os

STUDY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(p):
    out = []
    for line in open(os.path.join(STUDY, p)):
        r = json.loads(line)
        r.pop("cpu_s", None)
        out.append(r)
    return out


a1 = load("runs/score_attempt1/families.jsonl")
a2 = load("runs/score/families.jsonl")
res = {"attempt1_records": len(a1), "rerun_records": len(a2),
       "first_records_equal_ignoring_cpu_s": [a1[i] == a2[i] for i in range(min(len(a1), len(a2)))],
       "same_family_keys": [a1[i]["family"] == a2[i]["family"] for i in range(min(len(a1), len(a2)))]}
res["verdict"] = "MATCH" if res["first_records_equal_ignoring_cpu_s"] and all(res["first_records_equal_ignoring_cpu_s"]) \
    and len(a1) <= len(a2) else "MISMATCH"
json.dump(res, open(os.path.join(STUDY, "checks", "compare_attempt1.json"), "w"), indent=1)
print(json.dumps(res))
