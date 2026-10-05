"""Independent post-run verification of the v1.7 acceptance report.

Checks: the freeze is intact; the rows file equals the report's tasks; S1
to S6, the outcome and the supplementary counts recomputed by separate code
from the rows; the fixture selection re-derived under PYTHONHASHSEED=0 with
the same seeds, families and compiled production names; the run's
environment record. Writes nothing except its own stdout.
"""
import hashlib
import json
import os
import sys

R = "/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_arc2026"
sys.path.insert(0, R)
sys.path.insert(0, R + "/scripts")
import v17_acceptance as A                                         # noqa: E402

checks = {}
problems, man = A.freeze_problems()
checks["freeze_intact"] = problems == []
rep = json.load(open(A.OUT))
rows = [json.loads(line) for line in open(A.ROWS)]
norm = lambda x: json.dumps(x, sort_keys=True, default=str)        # noqa: E731
checks["rows_equal_report_tasks"] = [norm(r) for r in rows] == [norm(t) for t in rep["tasks"]]
checks["manifest_sha_matches"] = rep["manifest_sha256"] == hashlib.sha256(open(A.MANIFEST, "rb").read()).hexdigest()
start = json.load(open(A.START))
checks["environment_k_star"] = (start["environment"] == {"PYTHONHASHSEED": "0"} and start["hash_randomization"] == 0
                                and rep["conditions_at_end"]["environment"] == {"PYTHONHASHSEED": "0"})

ok = [r for r in rows if "error" not in r]
n_ok = len(ok) == 6 and len(rows) == 6
s1 = n_ok and all(r["S1_compiles_deterministic_reload"] for r in ok) and ok[0].get("fresh_process_identical") is True
s3 = n_ok and all(r["attribution"]["residue"] == 0 and r["attribution"]["direct_disagreements"] == 0
                  and r["attribution"]["label_anomalies"] == 0 for r in ok)
necessary = [r for r in ok if r["ablation"]["verdict"] == "EXTENSION_NECESSARY_AND_USED"
             and r["ablation"]["with"]["heldout_exact"] is True
             and r["ablation"]["with"]["accepted"] is True and r["ablation"]["without"]["accepted"] is False]
loo_pass = [r for r in ok if all(f["status"] == "RUN" and f["accepted"] and f["uses_extension"]
                                 and f["heldout_exact"] for f in r["adaptive_loo"]["folds"])
            and len(r["adaptive_loo"]["folds"]) == 7]
s6 = n_ok and all(r["witness"]["status"] == "SEPARATED" for r in ok)
recomputed = {"S1": s1, "S2": rep["conditions"]["S2"], "S3": s3, "S4": len(necessary) >= 5,
              "S5": len(loo_pass) >= 5, "S6": s6}
checks["conditions_recomputed_equal"] = {k: v for k, v in recomputed.items() if k != "S2"} == \
    {k: v for k, v in rep["conditions"].items() if k != "S2"}
checks["S2_restoration_errors_absent"] = all(r.get("error") != "RESTORATION_FAILURE" for r in rows)
outcome = ("COMPILER_DEFECTIVE" if not (recomputed["S1"] and recomputed["S2"] and recomputed["S3"] and recomputed["S6"])
           else "COMPILER_INTEGRATION_INCOMPLETE" if not (recomputed["S4"] and recomputed["S5"])
           else "COMPILER_ACCEPTED")
checks["outcome_recomputed_equal"] = outcome == rep["outcome"] and rep["unexpected"] == []
checks["supplementary_3x"] = sum(1 for r in necessary if r["baseline_3x"]["accepted"] is False) \
    == rep["supplementary"]["necessary_at_3x_baseline"]
checks["engine_dirs_removed"] = all(r["ablation"][a]["engine_dir_removed"] for r in ok for a in ("with", "without")) \
    and all(r["baseline_3x"]["engine_dir_removed"] for r in ok)

tasks = A.fixtures()
checks["fixtures_rederived"] = [(t["seed"], t["family"]) for t in tasks] == [(r["seed"], r["family"]) for r in rows]
names = [A.X.compile_extension(A.X.make_input(t["schema"]))["name"] for t in tasks]
checks["names_rederived"] = names == [r["name"] for r in rows]

print(json.dumps({"checks": checks, "all_pass": all(v is True for v in checks.values()),
                  "recomputed": recomputed, "outcome": outcome, "S4_tasks": len(necessary),
                  "S5_tasks": len(loo_pass)}, indent=1))
