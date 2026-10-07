"""Independent terminal verification of the v1.9 prospective engine-stability
test (run only after logs/V19_PROSPECTIVE_DONE exists). Written before any
prospective result exists.

1. The freeze is unchanged (manifest, implementation, dependencies, K*,
   K*', exclusion set).
2. Corpus integrity: N rows, indices 0..N-1, distinct seeds and digests,
   none in the exclusion set, inside the seed range, equal to the corpus
   law re-derived.
3. No leakage, no unexpected error, no duplicate row, run-once identity.
4. Every gate, witness leg and safety check recomputed from the rows by
   this file's own code and compared with the report.
Prints a JSON verdict; writes nothing else.
"""
import hashlib
import json
import math
import os
import sys

R_ = "/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_arc2026"
sys.path.insert(0, R_)
sys.path.insert(0, os.path.join(R_, "scripts"))
import v19_prospective as PR                                       # noqa: E402
import v18_corpus as CORPUS                                       # noqa: E402

checks, recomputed = {}, {}


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


problems, man = PR.freeze_problems()
checks["freeze_problems_empty"] = problems == []
report = json.load(open(PR.OUT))
rows = [json.loads(line) for line in open(PR.ROWS)]
start = json.load(open(PR.START))
marker = open(PR.MARKER).read().strip()
tasks = json.load(open(PR.TASKS))["tasks"]

# 2. corpus
excl = set(json.load(open(PR.EXCLUSION))["target_digests"])
byi = {}
for r in rows:
    byi.setdefault(r["i"], []).append(r)
checks["no_duplicate_rows"] = all(len(v) == 1 for v in byi.values())
rows = [v[0] for k, v in sorted(byi.items())]
checks["rows_N"] = len(rows) == PR.N_TASKS
checks["indices"] = [r["i"] for r in rows] == list(range(PR.N_TASKS))
checks["seeds_distinct"] = len({r["seed"] for r in rows}) == len(rows)
checks["digests_distinct"] = len({r.get("digest") for r in rows}) == len(rows)
checks["outside_exclusion"] = all(r.get("digest") not in excl for r in rows)
checks["seed_range"] = all(PR.SEED_BASE <= r["seed"] < PR.SEED_BASE + 100 * CORPUS.MAX_TRIES for r in rows)
law = CORPUS.tasks(PR.SEED_BASE, PR.N_TASKS, exclude_digests=excl, distinct=True)
checks["corpus_law_rederived"] = [(t["seed"], t["digest"]) for t in law] == [(r["seed"], r["digest"]) for r in rows]
checks["task_file_matches"] = [(t["seed"], t["digest"]) for t in tasks] == [(r["seed"], r["digest"]) for r in rows]

# 3. integrity
ok = [r for r in rows if "error" not in r]
checks["no_error_rows"] = len(ok) == len(rows)
checks["no_unexpected"] = report["unexpected"] == []
leak = sum(1 for r in ok for a in r["arms"].values() if a["class"] == "LEAKAGE_FAILURE") + \
    sum(1 for r in ok for k in ("loo_old", "loo_new") for f in r.get(k, {}).get("folds", [])
        if f.get("proposer_class") == "LEAKAGE_FAILURE")
checks["no_leakage"] = leak == 0 and report["leakage"] == 0
checks["marker_equals_outcome"] = marker == report["outcome"]
checks["manifest_in_report"] = report["manifest_sha256"] == sha(PR.MANIFEST) == start["manifest_sha256"]
#  erratum 01: resumes are logged when they happen; the report must carry them all
_rlog = [json.loads(x) for x in open(PR.RESUME_LOG) if x.strip()] if os.path.exists(PR.RESUME_LOG) else []
checks["resume_record_consistent"] = report.get("resumes") == _rlog
checks["workers_exited_cleanly"] = all(code == 0 for code in report.get("worker_exit_codes", []))
_rows_raw, _bad = [], 0
for _line in open(PR.ROWS):
    if _line.strip():
        try:
            json.loads(_line)
        except ValueError:
            _bad += 1
checks["unparsable_lines_equal"] = report.get("unparsable_lines") == _bad


# 4. recomputation
def sign_p(b, c):
    n = b + c
    return sum(math.comb(n, k) for k in range(b, n + 1)) / 2 ** n if n else 1.0


g1 = {}
for a in PR.G1_CONTROLS:
    b = sum(1 for r in ok if r["arms"]["FAILURE_CONDITIONED"]["useful"] and not r["arms"][a]["useful"])
    c = sum(1 for r in ok if r["arms"][a]["useful"] and not r["arms"]["FAILURE_CONDITIONED"]["useful"])
    g1[a] = {"a_only": b, "b_only": c, "p": sign_p(b, c), "pass": b > c and sign_p(b, c) < 0.05}
recomputed["G1"] = g1


def legs(r, which):
    if r["arms"]["FAILURE_CONDITIONED"]["class"] != "SELECTED":
        return None
    if "old" not in r:                       # selected but not compiled: P only (erratum 01)
        return {"B": False, "P": True, "U": False, "L": False, "T": False, "A": False}
    a_leg = not (r["baseline_3x"]["accepted"] and r["baseline_3x"]["heldout_exact"])
    if which == "new":
        return {"B": r["new_alone"]["accepted"] is False, "P": True, "U": bool(r["new_with"].get("uses")),
                "L": bool(r["loo_new"]["passed"]) and all(f["class"] == "SUCCESS" for f in r["loo_new"]["folds"]),
                "T": bool(r["new_with"]["heldout_exact"]), "A": a_leg}
    o = r["old"]
    return {"B": o["without"]["accepted"] is False, "P": True, "U": bool(o["uses"]),
            "L": bool(r["loo_old"]["passed"]) and all(f["class"] == "SUCCESS" for f in r["loo_old"]["folds"]),
            "T": bool(o["with"]["heldout_exact"]), "A": a_leg}


wn = [legs(r, "new") for r in ok]
wo = [legs(r, "old") for r in ok]
complete_new = sum(1 for x in wn if x and all(x.values()))
complete_old = sum(1 for x in wo if x and all(x.values()))
recomputed["complete_new"], recomputed["complete_old"] = complete_new, complete_old
recomputed["legs_new"] = {k: sum(1 for x in wn if x and x[k]) for k in "BPULTA"}
checks["witness_rows_match"] = all(
    (x is None and not r["witness_new"].get("complete")) or
    (x is not None and all(x[k] == bool(r["witness_new"].get(k, False)) for k in "BPULTA")
     and all(x.values()) == r["witness_new"]["complete"])
    for x, r in zip(wn, ok))
b = sum(1 for r in ok if r.get("loo_new", {}).get("passed") and not r.get("loo_old", {}).get("passed"))
c = sum(1 for r in ok if r.get("loo_old", {}).get("passed") and not r.get("loo_new", {}).get("passed"))
g3 = {"new_only": b, "old_only": c, "p": sign_p(b, c), "pass": b - c >= PR.DELTA_MIN and sign_p(b, c) < 0.05,
      "pairing_mismatches": sum(1 for r in ok for fo, fn in zip(r.get("loo_old", {}).get("folds", []),
                                                                r.get("loo_new", {}).get("folds", []))
                                if fo.get("selected") != fn.get("selected")
                                or fo.get("production") != fn.get("production"))}
recomputed["G3"] = g3
eng = [r for r in ok if "old" in r]
s = {
    "inert": all(r["new_alone"]["accepted"] == r["old"]["without"]["accepted"]
                 and r["new_alone"]["program_sha"] == r["old"]["without"]["program_sha"] for r in eng),
    "no_regression_full": all(r["new_with"]["accepted"] and r["new_with"]["heldout_exact"]
                              and (r["new_with"]["program_sha"] == r["old"]["with"]["program_sha"]
                                   if r["old"]["uses"] else True)
                              for r in eng if r["old"]["with"]["accepted"] and r["old"]["with"]["heldout_exact"]),
    "no_regression_folds": all(n["class"] == "SUCCESS" for r in eng
                               for o, n in zip(r["loo_old"]["folds"], r["loo_new"]["folds"]) if o["class"] == "SUCCESS"),
    "replays_training": all(r["new_with"].get("replays_training") is True for r in eng if r["new_with"]["accepted"]),
    "attribution": all(r["new_with"].get("direct_equals_engine") is True
                       for r in eng if r["new_with"]["accepted"] and r["new_with"].get("uses")),
    "restored": all(r.get("restored") for r in eng)}
def _wilson(k, n, z=1.959963984540054):
    if n == 0:
        return 0.0
    p = k / n
    return (p + z * z / (2 * n) - z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / (1 + z * z / n)


prec = {}
for side, fk, lk in (("old", "old", "loo_old"), ("new", "new_with", "loo_new")):
    fulls = [(r[fk]["with"] if side == "old" else r[fk]) for r in eng]
    acc = [x for x in fulls if x["accepted"]] + [f for r in eng for f in r[lk]["folds"] if f.get("accepted")]
    k = sum(1 for x in acc if x.get("heldout_exact"))
    prec[side] = {"certified": len(acc), "correct": k, "precision": k / len(acc) if acc else 1.0,
                  "wilson_lower": _wilson(k, len(acc))}
s["precision_floor"] = prec["new"]["precision"] >= PR.PRECISION_FLOOR
s["precision_noninferior"] = prec["new"]["precision"] >= prec["old"]["precision"] - PR.PRECISION_MARGIN
_dc = prec["new"]["correct"] - prec["old"]["correct"]
_dw = (prec["new"]["certified"] - prec["new"]["correct"]) - (prec["old"]["certified"] - prec["old"]["correct"])
s["marginal_precision"] = _dw <= 0 or _dw <= PR.MARGINAL_RATIO * max(_dc, 0)
recomputed["precision"] = prec
recomputed["G4"] = s
tr = [t for r in ok for t in r.get("reduced", {}).get("trials", [])]
recomputed["reduced"] = {side: {"true_accept": sum(1 for t in tr if t["kind"] == "RIGHT" and t[side]["accepted"] and t[side]["right_on_E"]),
                                "false_accept": sum(1 for t in tr if t["kind"] == "WRONG" and t[side]["accepted"] and not t[side]["right_on_E"])}
                         for side in ("old", "new")}
checks["reduced_equal"] = all(report["supplementary"]["reduced_control"][side][k] == recomputed["reduced"][side][k]
                              for side in ("old", "new") for k in ("true_accept", "false_accept"))
G1 = all(v["pass"] for v in g1.values())
G2 = complete_new >= PR.W_MIN
G3 = g3["pass"]
G4 = all(s.values())
out = ("REPAIR_UNSAFE" if not G4 else "ENGINE_STABILITY_REPAIR_ACCEPTED" if (G1 and G2 and G3) else
       "FAILURE_SPECIFICITY_LOST" if (G2 and G3) else "REPAIR_STABILIZES_BELOW_WITNESS_THRESHOLD" if G3 else
       "REPAIR_NOT_MATERIAL")
if leak:
    out = "PROPOSER_LEAKAGE"
recomputed["outcome"] = out
gates = report.get("gates", {})
checks["G1_equal"] = all(gates.get(f"G1_vs_{a.lower()}", {}).get("a_only") == g1[a]["a_only"]
                         and gates.get(f"G1_vs_{a.lower()}", {}).get("b_only") == g1[a]["b_only"]
                         and gates.get(f"G1_vs_{a.lower()}", {}).get("pass") == g1[a]["pass"]
                         and abs(gates.get(f"G1_vs_{a.lower()}", {}).get("p_one_sided", -1) - g1[a]["p"]) < 1e-15
                         for a in g1)
checks["G2_equal"] = gates.get("G2_witnesses_new", {}).get("complete") == complete_new and \
    gates.get("G2_witnesses_new", {}).get("pass") == G2 and \
    gates.get("G2_witnesses_new", {}).get("complete_old") == complete_old
checks["G3_equal"] = gates.get("G3_loo_stability", {}).get("new_only") == b and \
    gates.get("G3_loo_stability", {}).get("old_only") == c and gates.get("G3_loo_stability", {}).get("pass") == G3 and \
    gates.get("G3_loo_stability", {}).get("pairing_mismatches") == g3["pairing_mismatches"]
_strata = {}
for r in ok:
    mk = r.get("min_key_witnesses")
    key = "unknown" if not isinstance(mk, int) else ("3" if mk == 3 else (">=4" if mk >= 4 else f"{mk}"))
    o = _strata.setdefault(key, {"tasks": 0, "witnesses_new": 0, "witnesses_old": 0,
                                 "loo_new_passed": 0, "loo_old_passed": 0})
    o["tasks"] += 1
    o["witnesses_new"] += bool(r.get("witness_new", {}).get("complete"))
    o["witnesses_old"] += bool(r.get("witness_old", {}).get("complete"))
    o["loo_new_passed"] += bool(r.get("loo_new", {}).get("passed"))
    o["loo_old_passed"] += bool(r.get("loo_old", {}).get("passed"))
checks["strata_equal"] = report["supplementary"].get("witness_strata") == _strata
checks["G4_equal"] = gates.get("G4_safety", {}).get("checks") == s and gates.get("G4_safety", {}).get("pass") == G4
checks["precision_equal"] = all(gates.get("G4_safety", {}).get("precision", {}).get(side, {}).get(k) == prec[side][k]
                                for side in ("old", "new") for k in ("certified", "correct"))
checks["legs_equal"] = report["supplementary"]["legs_new"] == recomputed["legs_new"]
checks["outcome_equal"] = report["outcome"] == out
print(json.dumps({"all_checks_pass": all(checks.values()), "checks": checks, "recomputed": recomputed,
                  "report_outcome": report["outcome"]}, indent=1, default=str))
