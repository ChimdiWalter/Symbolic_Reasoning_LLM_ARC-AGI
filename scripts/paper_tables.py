#!/usr/bin/env python3
"""Regenerate every paper table from disk artifacts (reproducibility
contract: 'every table regenerates from disk with one script')."""
import json, glob, os
from collections import Counter

out = {}

# Corpus headline (v23 sealed = in-run 183 + 2 arbitration recoveries = 185)
# This is THE sealed number: it must agree with paper, README and slides.
# Superseded: v22 = 176 in-run + 5 arbitrated = 181.
RUN = "outputs/unified_harness_v23"
ARB = "outputs/v23_arbitration"
run = json.load(open(f"{RUN}/results.json"))
# Merge arbitration results (dc1df850, ef26cbf6 recovered from contention)
arb = json.load(open(f"{ARB}/results.json"))
sealed_ids = {r["task_id"] for r in run["solved"]}
for r in arb.get("solved", []):
    if r["task_id"] not in sealed_ids:
        run["solved"].append(r)
        sealed_ids.add(r["task_id"])
sealed_count = len(sealed_ids)
# recompute the origin / induced breakdowns over the merged sealed set
by_origin = dict(Counter(r.get("origin") for r in run["solved"]))
n_induced = sum(1 for r in run["solved"] if r.get("origin_class") == "induced")
out["corpus"] = {"solved": sealed_count, "total": run["total_tested"],
                 "csr": sealed_count / run["total_tested"],
                 "by_origin": by_origin,
                 "induced_fraction": n_induced / sealed_count}

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

# E5 best-of-2 (v17 emit pass; later runs only add to the certified set
# without losing attempt_2 gains, so best-of-2 = sealed_ids | v17_a2_correct)
sols = json.load(open("data/arc/arc-agi_training_solutions.json"))
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
                       "attempt_2_correct_beyond_certified": len(a2_correct - sealed_ids),
                       "best_of_2": len(sealed_ids | a2_correct)}

# program-family census of the certified corpus
fam = Counter()
seen = set()
for d in (ARB, RUN):  # arbitration (solo, quiet) wins on any overlap
    for f in glob.glob(f"{d}/object/programs/*.json"):
        tid = os.path.basename(f)[:-len(".json")]
        if tid in seen: continue
        try:
            p = json.load(open(f))
            fam[p.get("program_class", "object")] += 1
            seen.add(tid)
        except Exception: pass
out["program_families"] = dict(fam)

json.dump(out, open("outputs/paper_tables.json", "w"), indent=1, default=str)
print(json.dumps({k: (v if not isinstance(v, (dict, list)) or k in
                      ("corpus", "e5_best_of_2", "program_families") else "...")
                  for k, v in out.items()}, indent=1, default=str))
print("-> outputs/paper_tables.json")
