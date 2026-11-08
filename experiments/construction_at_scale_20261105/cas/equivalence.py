"""Plumbing check of the phase 2 runner on S1's own world (phase 1). It uses only S1's frozen tasks and records,
never a pilot or main task of this study.

    python -m cas.equivalence OUT_DIR

1. A copy of S1's inputs (REMOVED.json, TASKS_SYSTEM.json, TASKS_EVAL.json and the frozen controller records
   runs/prep_v4/records.pkl) is set up as a world folder.
2. Controller: cas.run_world.controller re-runs CORA's failure analysis on S1's 38 system tasks in a second copy;
   decisions and typed holes are compared with S1's frozen records.
3. Specification methods: cas.run_world.spec (S-hole, S-demo, S-shuffled, 11 motivating tasks x 3 seeds) is
   compared with S1's recorded units (runs/s1_run/units.json): candidate rows, outcomes, retries, promotions.
4. S-enum seed 0 with cas.run_world.enum; seeds 1 and 2 are copied from S1's record (CPU).
5. Matched search: S1's recorded results stand in; each recorded fit is re-run once at S1's budget to recover its
   two predictions (S1 kept none); excluded tasks had no matched search in S1 and are recorded as failed searches.
6. cas.run_world.evaluate and cas.analysis on this world; the primary contrast must equal S1's task-level record
   (S-hole 8 against matched search 5 of 11, discordant 4 : 1, p = 0.375). Revision 2 adds: committed outputs
   against reach, S-hole's complete charged CPU per task (the matched-search budget rule binds above 150 s), and
   the reuse and transfer searches with the grown grammars (S1 has no matched search on excluded tasks, so those
   pairs are against "not recovered").
Writes OUT_DIR/EQUIVALENCE.json.
"""
import json
import os
import pickle
import shutil
import sys

from cas import env as E
from cas import run_world as RW, analysis as AN                                # noqa: E402

FIELDS = ("sid", "outcome", "duplicate", "fit", "promotion", "sketch_rank")


def setup(wd):
    s1 = E.S1_DIR
    rem = E.load(os.path.join(s1, "evaluator_only", "REMOVED.json"))
    rem["families"] = list(rem["removed"])
    E.dump(os.path.join(wd, "evaluator_only", "REMOVED.json"), rem)
    for rel in ("partitions/TASKS_SYSTEM.json", "evaluator_only/TASKS_EVAL.json"):
        E.check_write(os.path.join(wd, rel))
        os.makedirs(os.path.dirname(os.path.join(wd, rel)), exist_ok=True)
        shutil.copyfile(os.path.join(s1, rel), os.path.join(wd, rel))
    E.dump(os.path.join(wd, "partitions", "PARTITIONS_MANIFEST.json"),
           {"world": "s1_world", "phase1_check": True, "note": "S1's own frozen tasks, for the plumbing check only",
            "tasks_system_sha256": E.sha256(os.path.join(wd, "partitions", "TASKS_SYSTEM.json")),
            "tasks_eval_sha256": E.sha256(os.path.join(wd, "evaluator_only", "TASKS_EVAL.json")),
            "removed_sha256": E.sha256(os.path.join(wd, "evaluator_only", "REMOVED.json"))})


def main(out_dir):
    out = {}
    wd = os.path.join(out_dir, "s1_world")
    setup(wd)
    rec_dst = os.path.join(wd, "runs", "prep_v4", "records.pkl")
    E.check_write(rec_dst)
    os.makedirs(os.path.dirname(rec_dst), exist_ok=True)
    shutil.copyfile(os.path.join(E.S1_DIR, "runs", "prep_v4", "records.pkl"), rec_dst)
    # 2. controller re-run in a second copy
    wd2 = os.path.join(out_dir, "s1_world_controller")
    setup(wd2)
    RW.verify_world(wd2)
    RW.controller(wd2)
    # the re-run's diagnosis CPU per task, charged to the arms (its decisions and holes equal S1's, checked below)
    E.check_write(os.path.join(wd, "runs", "prep_v4", "controller_summary.json"))
    shutil.copyfile(os.path.join(wd2, "runs", "prep_v4", "controller_summary.json"),
                    os.path.join(wd, "runs", "prep_v4", "controller_summary.json"))
    RW.verify_world(wd)
    with open(rec_dst, "rb") as f:
        old = pickle.load(f)
    with open(os.path.join(wd2, "runs", "prep_v4", "records.pkl"), "rb") as f:
        new = pickle.load(f)
    out["controller"] = {"tasks": len(old), "same_decision": sum(new[t]["decision"] == old[t]["decision"] for t in old),
                         "same_holes": sum(repr(new[t].get("sketches")) == repr(old[t].get("sketches")) for t in old)}
    print(json.dumps({"controller": out["controller"]}), flush=True)
    # 3. specification methods
    RW.spec(wd)
    mine = E.load(os.path.join(wd, "runs", "cas_arms", "units_spec.json"))
    s1u = E.load(os.path.join(E.S1_DIR, "runs", "s1_run", "units.json"))
    diffs, same = [], 0
    for k, v in sorted(mine.items()):
        o = s1u[k]
        a = [tuple(r.get(f) for f in FIELDS) for r in v["rows"]]
        b = [tuple(r.get(f) for f in FIELDS) for r in o["rows"]]
        ok = a == b and v["promoted"] == o["promoted"] and v["retries"] == o["retries"]
        same += ok
        if not ok:
            diffs.append(k)
    out["spec_units"] = {"compared": len(mine), "same": same, "differences": diffs}
    print(json.dumps({"spec_units": out["spec_units"]}), flush=True)
    # 4. S-enum seed 0 run; seeds 1 and 2 from S1's record
    RW.enum(wd, 0)
    e0 = E.load(os.path.join(wd, "runs", "cas_arms", "units_enum_s0.json"))
    out["enum_seed0"] = {"compared": len(e0), "same_promoted": sum(v["promoted"] == s1u[k]["promoted"] for k, v in e0.items()),
                         "differences": sorted(k for k, v in e0.items() if v["promoted"] != s1u[k]["promoted"])}
    for s in (1, 2):
        E.dump(os.path.join(wd, "runs", "cas_arms", f"units_enum_s{s}.json"),
               {k: v for k, v in s1u.items() if k.startswith("S-enum|") and k.endswith(f"|{s}")})
    # 5. matched search: S1's recorded results. S1 kept no predictions, so each recorded fit is re-run once with
    # S1's budget to recover its two predictions (deterministic: the program is checked to be S1's); excluded
    # tasks had no matched search in S1, so they are recorded as failed searches (not recovered)
    c7 = E.load(os.path.join(E.S1_DIR, "runs", "ib_c7m", "c7m.json"))
    from cgrow import experiment as X, search as S
    sys_t = X.system_tasks()
    rerun = {}
    for tid, v in sorted(c7.items()):
        r = dict(v, preds=[], budget_cpu_s=150.0, budget_reference_cpu_s=150.0, cpu_scale=1.0)
        if v.get("fit"):
            t = X.as_task(sys_t[tid])
            rr = S.run(X.G0Builder()(), t["train"], t["test_inputs"], budget=10 ** 9, cpu_cap=150.0)
            r["preds"] = (rr["preds"] or [])[:2]
            r["rerun_program_equal"] = rr["program"] == v.get("program")
            r["rerun_fit"] = bool(rr["fit"])
        rerun[tid] = r
    E.dump(os.path.join(wd, "runs", "cas_c7m", "c7m_M.json"), rerun)
    ev_all = X.eval_tasks()
    E.dump(os.path.join(wd, "runs", "cas_c7m", "c7m_E.json"),
           {t: {"fit": False, "child_failed": True, "preds": [], "budget_cpu_s": 150.0, "budget_reference_cpu_s": 150.0,
                "cpu_scale": 1.0, "cpu_s": None, "note": "no matched search on excluded tasks in S1"}
            for t, v in ev_all.items() if v["partition"] == "E"})
    out["c7m_rerun"] = {t: {"program_equal": r.get("rerun_program_equal"), "fit": r.get("rerun_fit")}
                        for t, r in rerun.items() if r.get("fit")}
    # 6. commit, evaluation and analysis (phase 1: the custody checks that need a kernel record are not strict)
    RW.commit(wd)
    RW.evaluate(wd)
    w = E.load(os.path.join(wd, "runs", "cas_eval", "world_results.json"))
    s1s = E.load(os.path.join(E.S1_DIR, "runs", "s1_eval", "struct_scores.json"))
    cmp = {}
    for sid, v in w["structures"].items():
        o = s1s.get(sid)
        if o is None:
            cmp[sid] = "not in S1's record"
            continue
        cmp[sid] = {"family_best": [v["family_best"], o["family_best"]], "kind": [v["kind"], o["kind"]],
                    "cast": [v["cast"], o["cast"]], "e_correct": [sorted(t for t, x in v["e_results"].items() if x),
                                                               sorted(o["e_correct"])]}
    out["structures"] = cmp
    AN.main(out_dir, [wd], strict=False)
    a = E.load(os.path.join(out_dir, "ANALYSIS.json"))
    pc = a["primary"]
    out["primary"] = {k: pc.get(k) for k in ("units", "both", "only_S-hole", "only_C7m", "neither",
                                               "mcnemar_p_conditional", "dependence_aware_ci95",
                                               "family_ci95_11_families", "source_clustered_ci95", "decision")}
    out["expected_primary"] = {"units": 11, "S-hole": 8, "C7m": 5, "only_S-hole": 4, "only_C7m": 1, "mcnemar_p": 0.375}
    out["secondary"] = {k: (v or {}).get("mcnemar_p_conditional") for k, v in a["secondary"].items()}
    # revision 2: committed outputs against reach, and growth's complete charged CPU against the matched budget
    out["committed_vs_reach"] = {"recovered_majority": a["descriptive"]["counts"]["majority"],
                                 "oracle_reach_majority": a["descriptive"]["oracle_reach_counts"]["majority"]}
    tot = {}
    for u in w["units"]:
        tot[u["task"]] = max((u["seeds"][s].get("S-hole", {}).get("charged_total_cpu_s") or 0) for s in u["seeds"])
    out["s_hole_charged_total_cpu_s_max_over_seeds"] = tot
    out["matched_budget_rule_would_bind"] = sorted(t for t, v in tot.items() if v > 150.0)
    out["cpu_accounting"] = w.get("cpu_accounting")
    E.dump(os.path.join(out_dir, "EQUIVALENCE.json"), out)
    print(json.dumps({"primary": out["primary"]}), flush=True)


if __name__ == "__main__":
    main(sys.argv[1])
