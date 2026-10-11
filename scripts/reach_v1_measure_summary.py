"""Summary, verification and readiness of the reach v1 measurement run
(docs/CORA_REAL_TASK_REACH_DEV_v1.md, sections 5.1 and 6). Development: no
target is read.

  python scripts/reach_v1_measure_summary.py   -> outputs/reach_v1/measure_summary.json

Verification recomputes every path class from the recorded gates, the
leave-one-out verdict from its folds and the separation verdict from its
legs, and audits every isolation log; the readiness rule is the pilot's
section 12 rule, unchanged.
"""
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
OUT = os.path.join(HERE, "outputs", "reach_v1")
LOG = os.path.join(HERE, "logs", "reach_v1")

from cora_pilot import isolation as ISO                              # noqa: E402
from cora_reach import measure as M                                  # noqa: E402


def rows(path):
    out = {}
    if os.path.exists(path):
        for line in open(path):
            if line.strip():
                r = json.loads(line)
                out[r["key"]] = r
    return out


def recompute_class(r):
    if r.get("diagnosis", {}).get("class") == "RUN_ERROR" or "error" in r and "path_class" not in r:
        return "RUN_ERROR"
    if not r["fc"]["proposals"]:
        return "NO_PROPOSAL"
    if not r["gates"].get("compile"):
        return "COMPILER_FAILURE"
    failed = [cls for gate, cls in M.GATES if not r["gates"].get(gate)]
    return failed[0] if failed else "ACTIVATED"


def verify(meas, keys):
    problems = []
    missing = [k for k in keys if k not in meas]
    if missing:
        problems.append(f"missing rows: {len(missing)}")
    for k, r in meas.items():
        cls = recompute_class(r)
        if cls != r.get("path_class", "RUN_ERROR"):
            problems.append(f"{k}: path class {r.get('path_class')} != recomputed {cls}")
        if cls == "RUN_ERROR":
            continue
        if not r.get("restored"):
            problems.append(f"{k}: engine state not restored")
        if r["fc"]["proposals"] and r["gates"].get("compile"):
            folds = r["loo"]["folds"]
            if len(folds) != r["n_train"]:
                problems.append(f"{k}: {len(folds)} folds for {r['n_train']} demonstrations")
            if r["loo"]["passed"] != (bool(folds) and all(f["class"] == "SUCCESS" for f in folds)):
                problems.append(f"{k}: leave-one-out verdict")
            s = r["separation"]
            if s["separated"] != (s["non_renaming"] and s["non_caching"] and s["non_composition_bounded"]):
                problems.append(f"{k}: separation verdict")
            if s["non_composition_bounded"] != (not r["kalone"]["accepted"] and not r["matched"]["accepted"]):
                problems.append(f"{k}: separation leg iii")
            if r["activated"] != (r["path_class"] == "ACTIVATED"):
                problems.append(f"{k}: activation flag")
            if not r["with_e"].get("restored"):
                problems.append(f"{k}: bridge not restored after K + e")
    return problems


def main():
    tasks = json.load(open(os.path.join(HERE, "records", "pilot_v1", "dev_bundle.json")))["tasks"]
    keys = sorted(tasks)
    meas = rows(os.path.join(OUT, "measure_rows.jsonl"))
    census = rows(os.path.join(OUT, "census_rows.jsonl"))
    logs = sorted(f for f in os.listdir(LOG) if f.startswith("isolation_measure_0_"))
    iso_problems = {}
    for f in logs:
        p = ISO.audit_log(json.load(open(os.path.join(LOG, f))))
        if p:
            iso_problems[f] = p
    ok_rows = {k: r for k, r in meas.items() if r.get("path_class", "RUN_ERROR") != "RUN_ERROR"}
    fc = {k: r for k, r in ok_rows.items() if r["fc"]["proposals"]}
    installed = sorted(k for k, r in fc.items() if r["progression"].get("compile") and r["progression"].get("install"))
    activated = sorted(k for k, r in ok_rows.items() if r.get("activated"))
    progression = {s: sum(1 for r in ok_rows.values() if r["progression"].get(s)) for s in M.PROGRESSION}
    gates = {g: sum(1 for r in fc.values() if r["gates"].get(g)) for g, _c in M.GATES}
    fold_classes = Counter(f["class"] for r in fc.values() for f in r["loo"]["folds"])
    controls = {}
    for arm in M.CONTROL_ARMS:
        inst = [r["controls"][arm] for r in ok_rows.values() if r["controls"][arm]["class"] == "INSTALLED"]
        controls[arm] = {"proposed_tasks": sum(1 for r in ok_rows.values()
                                               if r["control_proposals"][arm]["proposals"]),
                         "installed": len(inst),
                         "accepted": sum(1 for c in inst if c["with_e"]["accepted"]),
                         "uses": sum(1 for c in inst if c["with_e"].get("uses")),
                         "same_extension_as_fc": sum(1 for c in inst if c["same_as_fc"])}
    per_task = {}
    for k, r in sorted(fc.items()):
        inv = r["invariant"]
        per_task[k] = {"census_class": (census.get(k, {}).get("diagnosis") or {}).get("class"),
                       "extension": {x: r["extension"][x] for x in ("name", "family", "params")},
                       "path_class": r["path_class"], "gates": r["gates"],
                       "loo": {"passed": r["loo"]["passed"], "folds_success": r["loo"]["folds_success"],
                               "fold_classes": [f["class"] for f in r["loo"]["folds"]],
                               "fold_same_as_full": [f.get("same_as_full") for f in r["loo"]["folds"]]},
                       "separation": r["separation"], "pool_size": r["pool"]["size"],
                       "kalone_accepted": r["kalone"]["accepted"], "matched_accepted": r["matched"]["accepted"],
                       "removed_equals_kalone": r["unchanged_baseline"],
                       "e_cells_per_test": (r["with_e"].get("support") or {}).get("e_cells_per_test"),
                       "controls": {a: {"class": r["controls"][a]["class"],
                                        "accepted": (r["controls"][a].get("with_e") or {}).get("accepted"),
                                        "same_as_fc": r["controls"][a].get("same_as_fc")}
                                    for a in M.CONTROL_ARMS},
                       "conditions_1_to_5": all(inv[c] is True for c in ("c1_failure_of_K",
                                                                           "c2_machine_generated_from_failure",
                                                                           "c3_typed_canonical_executable",
                                                                           "c4_bounded_separation",
                                                                           "c5_adaptive_loo")),
                       "seconds": r["seconds"]}
    loads = [x for r in meas.values() for x in (r.get("load_start") or [])[:1] + (r.get("load_end") or [])[:1]]
    census_ready = (len(census) == 60 and not any((r.get("diagnosis") or {}).get("class") == "RUN_ERROR"
                                                  for r in census.values())
                    and os.path.exists(os.path.join(LOG, "CENSUS_0_DONE")))
    run_errors = sorted(k for k, r in meas.items() if r.get("path_class", "RUN_ERROR") == "RUN_ERROR")
    ready = {"isolation_clean": bool(logs) and not iso_problems, "no_run_error": not run_errors and len(meas) == 60,
             "native_readiness_complete": census_ready, "loop_operable": len(installed) >= 1}
    out = {"rows": len(meas), "missing": [k for k in keys if k not in meas], "run_errors": run_errors,
           "verification_problems": verify(meas, keys), "isolation_logs": len(logs),
           "isolation_problems": iso_problems, "ready": ready, "READY": all(ready.values()),
           "saved_baseline": {"installed": 0, "activated": 0, "verified_proposals": 0, "commit": "ce123e8"},
           "installed": installed, "activated": activated,
           "path_classes": dict(Counter(r.get("path_class", "RUN_ERROR") for r in meas.values()).most_common()),
           "progression": progression, "gates_over_fc_tasks": gates, "fc_tasks": len(fc),
           "loo_fold_classes": dict(fold_classes), "controls": controls,
           "conditions_1_to_5_tasks": sorted(k for k, v in per_task.items() if v["conditions_1_to_5"]),
           "per_fc_task": per_task,
           "compute_s": {"total": round(sum(r.get("seconds") or 0 for r in meas.values()), 1),
                         "fc_tasks": round(sum(r["seconds"] for r in fc.values()), 1)},
           "load": {"min": min(loads) if loads else None, "max": max(loads) if loads else None}}
    with open(os.path.join(OUT, "measure_summary.json"), "w") as handle:
        json.dump(out, handle, indent=1, sort_keys=True)
    print(json.dumps({k: out[k] for k in ("rows", "READY", "ready", "installed", "activated", "path_classes",
                                          "progression", "gates_over_fc_tasks", "loo_fold_classes",
                                          "conditions_1_to_5_tasks", "verification_problems")}, indent=1))


if __name__ == "__main__":
    main()
