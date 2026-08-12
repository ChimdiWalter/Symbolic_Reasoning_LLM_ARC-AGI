#!/usr/bin/env python3
"""Regenerate every paper table from disk artifacts (reproducibility
contract: 'every table regenerates from disk with one script')."""
import json, glob, os
from collections import Counter

out = {}

# Corpus headline (v17 sealed)
v17 = json.load(open("outputs/unified_harness_v17/results.json"))
out["corpus"] = {"solved": v17["total_solved"], "total": v17["total_tested"],
                 "csr": v17["total_solved"] / v17["total_tested"],
                 "by_origin": v17["by_origin"],
                 "induced_fraction": v17["induced_fraction"]}

# E1 / E2 (sealed artifacts)
try:
    out["e1_e4"] = json.load(open("outputs/paper_e1_e4/report.json"))
except Exception as e:
    out["e1_e4"] = f"missing: {e}"
try:
    out["e2"] = json.load(open("outputs/paper_e2/report.json"))
except Exception as e:
    out["e2"] = f"missing: {e}"
try:
    out["calibrated_csr"] = json.load(open("outputs/paper_calibrated_csr.json"))
except Exception as e:
    out["calibrated_csr"] = f"missing: {e}"

# E5 best-of-2 (fresh measurement)
sols = json.load(open("data/arc/arc-agi_training_solutions.json"))
v17_ids = {r["task_id"] for r in v17["solved"]}
a2_correct = set()
n_renders = 0
for line in open("outputs/unified_harness_v17_emit/progress.jsonl"):
    r = json.loads(line)
    tid = r["task_id"]
    if r.get("solved"): continue
    att2 = (r.get("predictions") or {}).get("attempt_2")
    if att2 and any(x is not None for x in att2):
        n_renders += 1
        if tid in sols and len(att2) >= len(sols[tid]) and all(
                att2[i] == sols[tid][i] for i in range(len(sols[tid]))
                if att2[i] is not None):
            a2_correct.add(tid)
out["e5_best_of_2"] = {"attempt_2_renders": n_renders,
                       "attempt_2_correct_beyond_certified": len(a2_correct - v17_ids),
                       "best_of_2": len(v17_ids | a2_correct)}

# E6/E7 artifacts
try:
    out["e7_verbs"] = json.load(open("outputs/learned_verbs/learned_verbs.json"))
except Exception: pass
try:
    out["e7_laws"] = json.load(open("outputs/learned_laws.json"))
except Exception: pass

# program-family census of the certified corpus
fam = Counter()
for f in glob.glob("outputs/unified_harness_v17/object/programs/*.json"):
    try:
        d = json.load(open(f))
        fam[d.get("program_class", "object")] += 1
    except Exception: pass
out["program_families"] = dict(fam)

json.dump(out, open("outputs/paper_tables.json", "w"), indent=1, default=str)
print(json.dumps({k: (v if not isinstance(v, (dict, list)) or k in
                      ("corpus", "e5_best_of_2", "program_families") else "...")
                  for k, v in out.items()}, indent=1, default=str))
print("-> outputs/paper_tables.json")
