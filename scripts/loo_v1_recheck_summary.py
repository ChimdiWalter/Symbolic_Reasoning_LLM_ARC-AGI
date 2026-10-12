"""Summary of the development recheck (docs/CORA_REAL_TASK_LOO_STABILITY_v1_AMENDMENT_1.md),
written before the recheck ran.

  python scripts/loo_v1_recheck_summary.py   -> outputs/loo_v1/recheck_summary.json

Per arm (ORIGINAL = reach v1, SUCCESSOR = reach v2): proposals,
installations, acceptances, use, replay, adaptive leave-one-out (folds and
tasks), support, path classes, false acceptances, restoration, REMOVED and
MATCHED, separation, conditions 1 to 5, compute; K alone across the arms;
and the screen of protocol section 10 on the SUCCESSOR arm. No target.
"""
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
OUT = os.path.join(HERE, "outputs", "loo_v1")
LOG = os.path.join(HERE, "logs", "loo_v1")


def jsonl(path):
    return [json.loads(l) for l in open(path) if l.strip()]


def conditions(r, census_class):
    if not (r.get("fc") or {}).get("proposals"):
        return {"c1": None, "c2": False, "c3": False, "c4": False, "c5": False, "all": False}
    g, pr = r["gates"], r["progression"]
    c = {"c1": census_class != "NATIVE_CERTIFIED" and not r["kalone"]["accepted"],
         "c2": bool(pr["candidate"]), "c3": bool(g.get("compile") and pr.get("install")),
         "c4": bool((r.get("separation") or {}).get("separated")), "c5": bool(g.get("loo"))}
    c["all"] = all(c[k] for k in ("c1", "c2", "c3", "c4", "c5"))
    return c


def arm_summary(rows, census):
    ok = [r for r in rows if r.get("class") != "RUN_ERROR" and "path_class" in r]
    fc = [r for r in ok if r["fc"]["proposals"]]
    folds = [f for r in fc if "loo" in r for f in r["loo"]["folds"]]
    false_acc = [(r["task"], f["fold"]) for r in fc if "loo" in r for f in r["loo"]["folds"]
                 if f.get("accepted") and f.get("uses") and not f.get("heldout_exact")]
    cond = {r["task"]: conditions(r, (census.get(r["task"], {}).get("diagnosis") or {}).get("class")) for r in fc}
    out = {"rows": len(rows), "run_errors": sorted(r["key"] for r in rows if r not in ok),
           "path_classes": dict(Counter(r["path_class"] for r in ok)),
           "progression": {k: sum(1 for r in ok if r["progression"].get(k)) for k in
                           ("usable_trace", "candidate", "type_check", "exact_demo_fit", "compile", "install",
                            "engine_acceptance", "use", "adaptive_loo", "activation")},
           "gates_over_fc_tasks": dict(Counter(g for r in fc for g, v in r["gates"].items() if v)),
           "fc_tasks": len(fc), "loo_fold_classes": dict(Counter(f["class"] for f in folds)),
           "loo_folds_success": sum(1 for f in folds if f["class"] == "SUCCESS"), "loo_folds": len(folds),
           "loo_tasks_passed": sorted(r["task"] for r in fc if r["gates"].get("loo")),
           "false_acceptances": false_acc,
           "activated": sorted(r["task"] for r in ok if r.get("activated")),
           "restored_all": all(r.get("restored") for r in ok),
           "removed_equals_kalone": sum(1 for r in fc if r.get("unchanged_baseline")),
           "matched_accepted": sum(1 for r in fc if (r.get("matched") or {}).get("accepted")),
           "separated": sorted(r["task"] for r in fc if (r.get("separation") or {}).get("separated")),
           "conditions": cond, "conditions_1_to_5": sorted(k for k, c in cond.items() if c["all"]),
           "controls": {arm: {"installed": sum(1 for r in ok if r["controls"][arm]["class"] == "INSTALLED"),
                              "accepted_with_e_used": sum(1 for r in ok if (r["controls"][arm].get("with_e") or {})
                                                          .get("uses"))} for arm in ("DEMO_ONLY", "SHUFFLED_FAILURE")},
           "seconds": round(sum(r.get("seconds") or 0 for r in ok), 1),
           "per_fc_task": {r["task"]: {"path_class": r["path_class"], "gates": r["gates"],
                                       "folds": [(f["fold"], f["class"], f.get("selected_variant"), f.get("same_as_full"),
                                                  f.get("accepted"), f.get("uses"), f.get("heldout_exact"))
                                                 for f in r["loo"]["folds"]] if "loo" in r else None,
                                       "variant_first": (r.get("with_e") or {}).get("variant_first"),
                                       "with_e": {k: (r.get("with_e") or {}).get(k) for k in
                                                  ("accepted", "uses", "failure_stage", "timeout", "seconds")},
                                       "seconds": r["seconds"]} for r in fc}}
    return out


def main():
    from cora_pilot import isolation as ISO
    rows = jsonl(os.path.join(OUT, "recheck_rows.jsonl"))
    census = {r["key"]: r for r in jsonl(os.path.join(HERE, "outputs", "reach_v1", "census_rows.jsonl"))}
    record = json.load(open(os.path.join(LOG, "recheck_0_record.json")))
    iso = {}
    for f in sorted(os.listdir(LOG)):
        if f.startswith("isolation_recheck_"):
            p = ISO.audit_log(json.load(open(os.path.join(LOG, f))))
            iso[f] = p
    by_arm = {arm: [r for r in rows if r.get("arm") == arm or r["key"].endswith("|" + arm)]
              for arm in ("ORIGINAL", "SUCCESSOR")}
    arms = {arm: arm_summary(v, census) for arm, v in by_arm.items()}
    ka = {}
    idx = {arm: {r["task"]: r for r in v if "kalone" in r} for arm, v in by_arm.items()}
    for t in sorted(set(idx["ORIGINAL"]) & set(idx["SUCCESSOR"])):
        a, b = idx["ORIGINAL"][t]["kalone"], idx["SUCCESSOR"][t]["kalone"]
        ka[t] = all(a.get(x) == b.get(x) for x in ("accepted", "program_sha", "predictions"))
    s = arms["SUCCESSOR"]
    passing = s["conditions_1_to_5"]
    screen = {"conditions_1_to_5_tasks": passing, "at_least_one": bool(passing),
              "isolation_clean": bool(iso) and not any(iso.values()),
              "no_run_error": not s["run_errors"] and not arms["ORIGINAL"]["run_errors"],
              "k_alone_unchanged": all(ka.values()) if ka else None,
              "attribution_exact": all(s["per_fc_task"][t]["gates"].get("attribution") for t in passing),
              "restoration": s["restored_all"], "matched_recorded": s["fc_tasks"] == sum(
                  1 for r in by_arm["SUCCESSOR"] if r.get("fc", {}).get("proposals") and "matched" in r)}
    screen["PASS"] = bool(screen["at_least_one"] and screen["isolation_clean"] and screen["no_run_error"]
                          and screen["k_alone_unchanged"] is not False and screen["attribution_exact"]
                          and screen["restoration"] and screen["matched_recorded"])
    out = {"units": len(rows), "record": record, "isolation_problems": {k: v for k, v in iso.items() if v},
           "isolation_logs": len(iso), "arms": arms, "k_alone_equal_across_arms": ka, "screen": screen}
    with open(os.path.join(OUT, "recheck_summary.json"), "w") as handle:
        json.dump(out, handle, indent=1, sort_keys=True, default=str)
    short = {arm: {k: a[k] for k in ("rows", "run_errors", "path_classes", "fc_tasks", "loo_fold_classes",
                                     "loo_folds_success", "loo_folds", "loo_tasks_passed", "false_acceptances",
                                     "activated", "conditions_1_to_5", "seconds")} for arm, a in arms.items()}
    print(json.dumps({"units": len(rows), "arms": short, "k_alone_equal": ka, "screen": screen}, indent=1,
                     default=str))


if __name__ == "__main__":
    main()
