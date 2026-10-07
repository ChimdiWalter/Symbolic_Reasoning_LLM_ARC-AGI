"""Independent recomputation of the v1.9 prospective result from the raw rows
(written after the marker, separate from the script and the frozen verifier;
plain json and math only). Prints a comparison with the report."""
import collections, hashlib, json, math
R = "/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_arc2026"
rows_all = [json.loads(l) for l in open(f"{R}/outputs/tti/v19_prospective_rows.jsonl") if l.strip()]
rep = json.load(open(f"{R}/outputs/tti/v19_prospective_report.json"))
tasks = json.load(open(f"{R}/outputs/tti/v19_prospective_tasks.json"))["tasks"]
excl = set(json.load(open(f"{R}/outputs/tti/v19_prospective_exclusion.json"))["target_digests"])
out = {}
idx = [r["i"] for r in rows_all]
out["rows_total"] = len(rows_all)
out["duplicates"] = len(idx) - len(set(idx))
rows = sorted({r["i"]: r for r in rows_all}.values(), key=lambda r: r["i"])
ok = [r for r in rows if "error" not in r]
out["error_rows"] = len(rows) - len(ok)
out["indices_ok"] = [r["i"] for r in rows] == list(range(30))
out["seeds_distinct"] = len({r["seed"] for r in rows}) == 30
out["digests_distinct"] = len({r["digest"] for r in rows}) == 30
out["outside_exclusion"] = all(r["digest"] not in excl for r in rows)
out["seeds_in_880M_range"] = all(880_000_000 <= r["seed"] < 880_000_000 + 200_000 for r in rows)
out["rows_match_task_file"] = [(r["seed"], r["digest"]) for r in rows] == [(t["seed"], t["digest"]) for t in tasks]
out["leakage"] = sum(1 for r in ok for a in r["arms"].values() if a["class"] == "LEAKAGE_FAILURE") + \
    sum(1 for r in ok for k in ("loo_old", "loo_new") for f in r.get(k, {}).get("folds", []) if f.get("proposer_class") == "LEAKAGE_FAILURE")
def sp(b, c):
    n = b + c
    return sum(math.comb(n, k) for k in range(b, n + 1)) / 2 ** n if n else 1.0
g1 = {}
for a in ("SHUFFLED_FRONTIER", "BLIND"):
    b = sum(1 for r in ok if r["arms"]["FAILURE_CONDITIONED"]["useful"] and not r["arms"][a]["useful"])
    c = sum(1 for r in ok if r["arms"][a]["useful"] and not r["arms"]["FAILURE_CONDITIONED"]["useful"])
    g1[a] = {"main_only": b, "control_only": c, "p": sp(b, c), "pass": b > c and sp(b, c) < 0.05,
             "main_useful": sum(1 for r in ok if r["arms"]["FAILURE_CONDITIONED"]["useful"]),
             "control_useful": sum(1 for r in ok if r["arms"][a]["useful"])}
out["G1"] = g1
def legs(r, side):
    if r["arms"]["FAILURE_CONDITIONED"]["class"] != "SELECTED":
        return None
    if "old" not in r:
        return {"B": False, "P": True, "U": False, "L": False, "T": False, "A": False}
    a = not (r["baseline_3x"]["accepted"] and r["baseline_3x"]["heldout_exact"])
    if side == "new":
        loo = r["loo_new"]
        return {"B": not r["new_alone"]["accepted"], "P": True, "U": bool(r["new_with"].get("uses")),
                "L": loo["passed"] and all(f["class"] == "SUCCESS" for f in loo["folds"]),
                "T": bool(r["new_with"]["heldout_exact"]), "A": a}
    loo = r["loo_old"]
    return {"B": not r["old"]["without"]["accepted"], "P": True, "U": bool(r["old"]["uses"]),
            "L": loo["passed"] and all(f["class"] == "SUCCESS" for f in loo["folds"]),
            "T": bool(r["old"]["with"]["heldout_exact"]), "A": a}
ln = [legs(r, "new") for r in ok]; lo = [legs(r, "old") for r in ok]
out["legs_new"] = {k: sum(1 for x in ln if x and x[k]) for k in "BPULTA"}
out["legs_old"] = {k: sum(1 for x in lo if x and x[k]) for k in "BPULTA"}
out["G2_complete_new"] = sum(1 for x in ln if x and all(x.values()))
out["G2_complete_old"] = sum(1 for x in lo if x and all(x.values()))
b = sum(1 for r in ok if r.get("loo_new", {}).get("passed") and not r.get("loo_old", {}).get("passed"))
c = sum(1 for r in ok if r.get("loo_old", {}).get("passed") and not r.get("loo_new", {}).get("passed"))
out["G3"] = {"new_only": b, "old_only": c, "p": sp(b, c), "pass": b - c >= 6 and sp(b, c) < 0.05,
             "loo_old_passed": sum(1 for r in ok if r.get("loo_old", {}).get("passed")),
             "loo_new_passed": sum(1 for r in ok if r.get("loo_new", {}).get("passed")),
             "folds_success_old": sum(1 for r in ok for f in r.get("loo_old", {}).get("folds", []) if f["class"] == "SUCCESS"),
             "folds_success_new": sum(1 for r in ok for f in r.get("loo_new", {}).get("folds", []) if f["class"] == "SUCCESS"),
             "pairing_mismatches": sum(1 for r in ok for fo, fn in zip(r.get("loo_old", {}).get("folds", []), r.get("loo_new", {}).get("folds", []))
                                       if fo.get("selected") != fn.get("selected") or fo.get("production") != fn.get("production"))}
eng = [r for r in ok if "old" in r]
def prec(side):
    full = [(r["old"]["with"] if side == "old" else r["new_with"]) for r in eng]
    acc = [x for x in full if x["accepted"]] + [f for r in eng for f in r["loo_" + side]["folds"] if f.get("accepted")]
    k = sum(1 for x in acc if x.get("heldout_exact"))
    return {"certified": len(acc), "correct": k, "precision": k / len(acc) if acc else 1.0,
            "wrong_full": sum(1 for x in full if x["accepted"] and not x["heldout_exact"]),
            "wrong_folds": sum(1 for r in eng for f in r["loo_" + side]["folds"] if f.get("accepted") and not f.get("heldout_exact"))}
po, pn = prec("old"), prec("new")
dc, dw = pn["correct"] - po["correct"], (pn["certified"] - pn["correct"]) - (po["certified"] - po["correct"])
wrong = [w for r in eng for w in r.get("wrong_trials", [])]
g4 = {"inert": all(r["new_alone"]["accepted"] == r["old"]["without"]["accepted"] and r["new_alone"]["program_sha"] == r["old"]["without"]["program_sha"] for r in eng),
      "no_regression_full": all(r["new_with"]["accepted"] and r["new_with"]["heldout_exact"] and (r["new_with"]["program_sha"] == r["old"]["with"]["program_sha"] if r["old"]["uses"] else True)
                                for r in eng if r["old"]["with"]["accepted"] and r["old"]["with"]["heldout_exact"]),
      "no_regression_folds": all(fn["class"] == "SUCCESS" for r in eng for fo, fn in zip(r["loo_old"]["folds"], r["loo_new"]["folds"]) if fo["class"] == "SUCCESS"),
      "replays_training": all(r["new_with"].get("replays_training") is True for r in eng if r["new_with"]["accepted"]),
      "attribution": all(r["new_with"].get("direct_equals_engine") is True for r in eng if r["new_with"]["accepted"] and r["new_with"].get("uses")),
      "restored": all(r.get("restored") for r in eng),
      "precision_floor": pn["precision"] >= 0.95,
      "precision_noninferior": pn["precision"] >= po["precision"] - 0.02,
      "marginal_precision": dw <= 0 or dw <= 0.05 * max(dc, 0)}
out["G4"] = g4
out["precision_old"], out["precision_new"] = po, pn
out["added_correct"], out["added_wrong"] = dc, dw
out["seven_pair_wrong_trials"] = {"trials": len(wrong),
    "false_accept_old": sum(1 for w in wrong if w["old"]["accepted"] and not w["old"]["heldout_exact"]),
    "false_accept_new": sum(1 for w in wrong if w["new"]["accepted"] and not w["new"]["heldout_exact"]),
    "by_source": dict(collections.Counter(w["source"] for w in wrong))}
out["alone_events_differ"] = sum(1 for r in eng if r["new_alone"]["events"] != r["old"]["without"]["events"])
tr = [t for r in ok for t in r.get("reduced", {}).get("trials", [])]
red = {"trials": len(tr), "right_trials": sum(1 for t in tr if t["kind"] == "RIGHT"), "wrong_trials": sum(1 for t in tr if t["kind"] == "WRONG")}
for s in ("old", "new"):
    red[s] = {"true_accept": sum(1 for t in tr if t["kind"] == "RIGHT" and t[s]["accepted"] and t[s]["right_on_E"]),
              "false_accept": sum(1 for t in tr if t["kind"] == "WRONG" and t[s]["accepted"] and not t[s]["right_on_E"])}
red["wrong_tasks"] = len({r["i"] for r in ok for t in r.get("reduced", {}).get("trials", []) if t["kind"] == "WRONG"})
out["reduced"] = red
st = {}
for r in ok:
    mk = r.get("min_key_witnesses")
    key = "unknown" if not isinstance(mk, int) else ("3" if mk == 3 else (">=4" if mk >= 4 else str(mk)))
    o = st.setdefault(key, {"tasks": 0, "witnesses_new": 0, "witnesses_old": 0, "loo_new_passed": 0, "loo_old_passed": 0})
    o["tasks"] += 1; o["witnesses_new"] += bool(r["witness_new"].get("complete")); o["witnesses_old"] += bool(r["witness_old"].get("complete"))
    o["loo_new_passed"] += bool(r.get("loo_new", {}).get("passed")); o["loo_old_passed"] += bool(r.get("loo_old", {}).get("passed"))
out["strata"] = st
out["min_key_witnesses_values"] = dict(collections.Counter(str(r.get("min_key_witnesses")) for r in ok))
out["control_failures"] = sum(1 for r in ok if r.get("wrong_trials_failure") or (r.get("reduced") or {}).get("failure"))
out["levels"] = dict(collections.Counter((r["arms"]["FAILURE_CONDITIONED"].get("selection") or {}).get("level") for r in ok))
out["families"] = {f: {"tasks": sum(1 for r in ok if r["family"] == f), "witnesses_new": sum(1 for r in ok if r["family"] == f and r["witness_new"].get("complete")),
                       "witnesses_old": sum(1 for r in ok if r["family"] == f and r["witness_old"].get("complete"))} for f in sorted({r["family"] for r in ok})}
g1p = all(v["pass"] for v in g1.values()); g2p = out["G2_complete_new"] >= 19; g3p = out["G3"]["pass"]; g4p = all(g4.values())
oc = ("PROPOSER_LEAKAGE" if out["leakage"] else "REPAIR_UNSAFE" if not g4p else "ENGINE_STABILITY_REPAIR_ACCEPTED" if (g1p and g2p and g3p)
      else "FAILURE_SPECIFICITY_LOST" if (g2p and g3p) else "REPAIR_STABILIZES_BELOW_WITNESS_THRESHOLD" if g3p else "REPAIR_NOT_MATERIAL")
out["outcome"] = oc
g = rep["gates"]; sup = rep["supplementary"]
cmp = {"outcome": rep["outcome"] == oc,
       "G1": all(g[f"G1_vs_{a.lower()}"]["a_only"] == g1[a]["main_only"] and g[f"G1_vs_{a.lower()}"]["b_only"] == g1[a]["control_only"]
                 and g[f"G1_vs_{a.lower()}"]["pass"] == g1[a]["pass"] and abs(g[f"G1_vs_{a.lower()}"]["p_one_sided"] - g1[a]["p"]) < 1e-15 for a in g1),
       "G2": g["G2_witnesses_new"]["complete"] == out["G2_complete_new"] and g["G2_witnesses_new"]["complete_old"] == out["G2_complete_old"],
       "G3": all(g["G3_loo_stability"][k] == out["G3"][k] for k in ("new_only", "old_only", "pass", "pairing_mismatches")),
       "G4_checks": g["G4_safety"]["checks"] == g4,
       "precision": all(g["G4_safety"]["precision"][s][k] == v[k] for s, v in (("old", po), ("new", pn)) for k in ("certified", "correct", "wrong_full", "wrong_folds")),
       "added": g["G4_safety"]["precision"].get("added_correct") == dc and g["G4_safety"]["precision"].get("added_wrong") == dw,
       "legs_new": sup["legs_new"] == out["legs_new"], "legs_old": sup["legs_old"] == out["legs_old"],
       "strata": sup["witness_strata"] == st,
       "reduced": all(sup["reduced_control"][s][k] == red[s][k] for s in ("old", "new") for k in ("true_accept", "false_accept")),
       "control_failures": sup["control_failures"] == out["control_failures"],
       "no_duplicates_or_errors": rep["duplicate_rows"] == 0 and rep["unexpected"] == [] and out["duplicates"] == 0 and out["error_rows"] == 0,
       "no_resumes": rep["resumes"] == [], "workers_clean": rep["worker_exit_codes"] == [0, 0, 0, 0], "unparsable": rep["unparsable_lines"] == 0}
print(json.dumps({"recomputed": out, "agrees_with_report": cmp, "ALL_AGREE": all(cmp.values()),
                  "report_seconds": rep["seconds"]}, indent=1, default=str))
