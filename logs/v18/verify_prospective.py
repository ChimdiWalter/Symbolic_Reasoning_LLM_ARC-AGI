"""Independent terminal verification of the v1.8 prospective test (run only
after logs/V18_PROSPECTIVE_DONE exists). Written before any result was read.

1. The freeze is unchanged (manifest, protocol, proposer, compiler, K*).
2. Corpus integrity: 30 rows, indices 0..29, distinct seeds and digests,
   none in the exclusion set, and equal to the corpus law re-derived.
3. No leakage, no unexpected error, run-once identity intact.
4. Every gate, witness leg and split recomputed from the rows by this
   file's own code and compared with the report.
Prints a JSON verdict; writes nothing else.
"""
import hashlib
import json
import math
import os
import sys

R = "/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_arc2026"
sys.path.insert(0, R)
sys.path.insert(0, os.path.join(R, "scripts"))
import v18_prospective as PR                                       # noqa: E402
import v18_corpus as CORPUS                                       # noqa: E402
from cora_arc2026 import v17_compiler as X                        # noqa: E402

checks, recomputed = {}, {}


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


# 1. freeze
problems, man = PR.freeze_problems()
checks["freeze_problems_empty"] = problems == []
checks["manifest_sha"] = sha(PR.MANIFEST) == "d64732cf54f91f70ce6f7be041956850d6cc85ca3986e4e08199401278db8731"
checks["protocol_sha"] = sha(os.path.join(R, "docs/CORA_TTI_NO_ORACLE_PROPOSER_v1.8.md")) == \
    "59e0889f65b0d2ed743697d0920b48ed121d0d5d031b3d0b8154eb1e36fbeb0f"
checks["proposer_sha"] = sha(os.path.join(R, "cora_arc2026/v18_proposer.py")) == \
    "8fbb08018814f31bb584b9fb1bf9eff03465bfab1f72bfbcb3a517ef046cdf07"
checks["compiler_sha"] = sha(os.path.join(R, "cora_arc2026/v17_compiler.py")).startswith("04c6b3a1")
checks["k_identity"] = X.k_identity() == "b009a9fb13402348a73c3e1ef187a82c2d42fb5175e5fed806e8d33d6b73e729"

report = json.load(open(PR.OUT))
rows = [json.loads(line) for line in open(PR.ROWS)]
start = json.load(open(PR.START))
launch = json.load(open(os.path.join(R, "logs/v18/prospective_launch.json")))
marker = open(PR.MARKER).read().strip()

# 2. corpus integrity
exclusion = set(json.load(open(PR.EXCLUSION))["target_digests"])
checks["rows_30"] = len(rows) == 30
checks["indices_0_29"] = sorted(r["i"] for r in rows) == list(range(30))
checks["seeds_distinct"] = len({r["seed"] for r in rows}) == len(rows)
checks["digests_distinct"] = len({r.get("digest") for r in rows}) == len(rows)
checks["outside_exclusion"] = all(r.get("digest") not in exclusion for r in rows)
checks["seed_range"] = all(860_000_000 <= r["seed"] < 860_000_000 + 100 * CORPUS.MAX_TRIES for r in rows)
law = CORPUS.tasks(CORPUS.PROSPECTIVE_BASE, 30, exclude_digests=exclusion, distinct=True)
checks["corpus_law_rederived"] = [(t["seed"], t["digest"]) for t in law] == \
    [(r["seed"], r.get("digest")) for r in sorted(rows, key=lambda r: r["i"])]

# 3. leakage, errors, run-once identity
ok = [r for r in rows if "error" not in r]
checks["no_error_rows"] = len(ok) == len(rows)
checks["no_unexpected"] = report["unexpected"] == []
leak = sum(1 for r in ok for a in r["arms"].values() if a["class"] == "LEAKAGE_FAILURE") + \
    sum(1 for r in ok for f in r.get("real_loo", {}).get("folds", []) if f.get("proposer_class") == "LEAKAGE_FAILURE")
checks["no_leakage"] = leak == 0 and report["leakage"] == 0
checks["single_writer"] = start["pid"] == launch["writer_pid"]
checks["no_resume"] = report.get("resumes", []) == []
checks["marker_equals_outcome"] = marker == report["outcome"]
checks["manifest_in_report"] = report["manifest_sha256"] == sha(PR.MANIFEST)


# 4. recomputation
def sign_p(b, c):
    n = b + c
    return sum(math.comb(n, k) for k in range(b, n + 1)) / 2 ** n if n else 1.0


arms = list(rows[0]["arms"]) if rows else []
useful = {a: sum(1 for r in ok if r["arms"][a]["useful"]) for a in arms}
recomputed["useful"] = useful
g1 = {}
for a in ("SHUFFLED_FRONTIER", "BLIND"):
    b = sum(1 for r in ok if r["arms"]["FAILURE_CONDITIONED"]["useful"] and not r["arms"][a]["useful"])
    c = sum(1 for r in ok if r["arms"][a]["useful"] and not r["arms"]["FAILURE_CONDITIONED"]["useful"])
    p = sign_p(b, c)
    g1[a] = {"a_only": b, "b_only": c, "p_one_sided": p, "pass": b > c and p < 0.05}
recomputed["G1"] = g1


def legs(r):
    if r["arms"]["FAILURE_CONDITIONED"]["class"] != "SELECTED":
        return {"B": False, "P": False, "U": False, "L": False, "T": False, "A": False}
    eng = r.get("engine", {})
    eng = eng if eng.get("class") != "COMPILE_FAILURE" else {}
    b3 = r.get("baseline_3x", {})
    folds = r.get("real_loo", {}).get("folds", [])
    return {"B": eng.get("without", {}).get("accepted") is False, "P": True,
            "U": bool(eng.get("uses")), "L": bool(folds) and all(f.get("class") == "SUCCESS" for f in folds),
            "T": bool(eng.get("with", {}).get("heldout_exact")),
            "A": not (b3.get("accepted") and b3.get("heldout_exact"))}


leg_rows = [legs(r) for r in ok]
complete = sum(1 for lg in leg_rows if all(lg.values()))
recomputed["witness_parts"] = {k: sum(1 for lg in leg_rows if lg[k]) for k in "BPULTA"}
recomputed["complete_witnesses"] = complete
recomputed["G2_pass"] = complete >= 15
checks["witness_rows_match"] = all(
    all(lg[k] == bool(r["witness"].get(k)) for k in "BPULTA") and all(lg.values()) == r["witness"]["complete"]
    for lg, r in zip(leg_rows, ok) if r["arms"]["FAILURE_CONDITIONED"]["class"] == "SELECTED")
g1_pass = all(v["pass"] for v in g1.values())
outcome = ("NO_ORACLE_PROPOSER_ACCEPTED" if g1_pass and recomputed["G2_pass"] else
           "PROPOSER_WORKS_BUT_NOT_FAILURE_SPECIFIC" if recomputed["G2_pass"] else
           "FAILURE_SPECIFIC_BUT_NOT_END_TO_END" if g1_pass else "NO_ORACLE_PROPOSER_NOT_ESTABLISHED")
if leak:
    outcome = "PROPOSER_LEAKAGE"
recomputed["outcome"] = outcome
fold_success = [r.get("real_loo", {}).get("folds_success") for r in ok]
recomputed["loo_folds_success"] = fold_success
recomputed["baseline_3x"] = {"accepted": sum(1 for r in ok if r.get("baseline_3x", {}).get("accepted")),
                             "reproduces_heldout": sum(1 for r in ok if r.get("baseline_3x", {}).get("accepted")
                                                       and r.get("baseline_3x", {}).get("heldout_exact")),
                             "ran": sum(1 for r in ok if "baseline_3x" in r)}
recomputed["seen_unseen"] = {s: {"tasks": sum(1 for r in ok if r["seen_structure"] == (s == "seen")),
                                 "witnesses": sum(1 for r, lg in zip(ok, leg_rows)
                                                  if r["seen_structure"] == (s == "seen") and all(lg.values()))}
                             for s in ("seen", "unseen")}
recomputed["by_family"] = {f: {"tasks": sum(1 for r in ok if r["family"] == f),
                               "witnesses": sum(1 for r, lg in zip(ok, leg_rows) if r["family"] == f and all(lg.values()))}
                           for f in sorted({r["family"] for r in ok})}
levels = {}
for r in ok:
    lv = (r["arms"]["FAILURE_CONDITIONED"].get("selection") or {}).get("level")
    levels[lv] = levels.get(lv, 0) + 1
recomputed["selection_levels"] = levels
recomputed["s6"] = {"new_capability_label": sum(1 for r in ok if r.get("s6", {}).get("new_capability")),
                    "C_probes_separated": sum(1 for r in ok if r.get("s6", {}).get("C_probes") == "SEPARATED")}
recomputed["classes"] = {a: {c: sum(1 for r in ok if r["arms"][a]["class"] == c)
                             for c in sorted({r["arms"][a]["class"] for r in ok})} for a in arms}

sup = report.get("supplementary", {})
gates = report.get("gates", {})
checks["useful_equal"] = sup.get("useful_by_arm") == useful
checks["G1_equal"] = all(gates.get(f"G1_vs_{a.lower()}", {}).get(k) == g1[a][k]
                         for a in g1 for k in ("a_only", "b_only", "pass")) and \
    all(abs(gates.get(f"G1_vs_{a.lower()}", {}).get("p_one_sided", -1) - g1[a]["p_one_sided"]) < 1e-15 for a in g1)
checks["G2_equal"] = gates.get("G2_witnesses", {}).get("complete") == complete and \
    gates.get("G2_witnesses", {}).get("pass") == recomputed["G2_pass"]
checks["witness_parts_equal"] = sup.get("witness_parts") == recomputed["witness_parts"]
checks["seen_unseen_equal"] = sup.get("seen_unseen") == recomputed["seen_unseen"]
checks["family_equal"] = sup.get("by_family") == recomputed["by_family"]
checks["levels_equal"] = {k: v for k, v in sup.get("selection_levels", {}).items() if v} == \
    {k: v for k, v in levels.items() if k is not None}
checks["s6_equal"] = sup.get("s6_descriptive") == recomputed["s6"]
checks["classes_equal"] = sup.get("classes_by_arm") == recomputed["classes"]
checks["outcome_equal"] = report["outcome"] == outcome

print(json.dumps({"all_checks_pass": all(checks.values()), "checks": checks, "recomputed": recomputed,
                  "report_outcome": report["outcome"], "report_seconds": report.get("seconds")},
                 indent=1, default=str))
