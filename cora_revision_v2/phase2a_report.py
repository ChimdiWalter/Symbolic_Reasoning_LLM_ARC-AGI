"""Phase 2a report: the analyses the directive asks for, computed AFTER `phase2a evaluate`.

  python -m cora_revision_v2.phase2a_report   -> outputs/cora_revision_v2/phase2a_evaluator/phase2a_report.json

Inputs: the frozen arm rows (`phase2a/rows_{A,B,V}.jsonl`) and the evaluator's per-task verdicts (`phase2a_evaluator/
phase2a_eval.json`). It reads no answer file itself and changes nothing. It adds:
- per-arm correct and wrong counts;
- tasks A or B solve that V does not;
- V's diagnosis, tier and fold-outcome distributions, and its disagreements;
- CPU and wall time per arm;
- a check that no row carries an output field it should not.

The GO decision is the evaluator's, under the frozen rule, and is copied here unchanged.
"""
import collections
import json
import os
import statistics as st
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "outputs", "cora_revision_v2", "phase2a")
EVAL = os.path.join(HERE, "outputs", "cora_revision_v2", "phase2a_evaluator")


def rows(arm):
    return {r["key"]: r for r in (json.loads(l) for l in open(os.path.join(OUT, f"rows_{arm}.jsonl")) if l.strip())}


def main():
    ev = json.load(open(os.path.join(EVAL, "phase2a_eval.json")))
    per = ev["per_task"]
    R = {a: rows(a) for a in ("A", "B", "V")}
    rep = {"GO": ev["GO"], "go_checks": ev["go_checks"], "coverage": ev["coverage"], "n": ev["n"]}
    for a in ("A", "B"):
        cert = [k for k, r in R[a].items() if r.get("certified")]
        rep[a] = {"certified": len(cert), "certified_correct": sum(per[k][f"{a}_correct"] for k in cert),
                  "certified_wrong": sum(not per[k][f"{a}_correct"] for k in cert),
                  "cpu_s_mean": round(st.mean((r.get("run") or {}).get("cpu_s", 0) or 0 for r in R[a].values()), 1),
                  "wall_s_mean": round(st.mean(r.get("wall_s", 0) for r in R[a].values()), 1),
                  "timeouts": sum(bool((r.get("run") or {}).get("timeout")) for r in R[a].values()),
                  "errors": sum(bool(r.get("error")) for r in R[a].values())}
    v = R["V"]
    rep["V"] = {"tiers": ev["V_tiers"], "certified_correct": ev["V_certified_correct"],
                "certified_wrong": ev["V_certified_wrong"], "exploratory_correct": ev["V_exploratory_correct"],
                "exploratory_wrong": ev["V_exploratory_wrong"], "discouraged_correct": ev["V_discouraged_correct"],
                "diagnoses": dict(collections.Counter(r.get("diagnosis") for r in v.values())),
                "primary_actions": dict(collections.Counter((r.get("diagnoses") or [{}])[0].get("next_action")
                                                            for r in v.values())),
                "fold_outcomes": dict(collections.Counter(
                    (d.get("outcome") if d.get("outcome") != "UNPREDICTABLE" else d.get("cause"))
                    for r in v.values() for d in (r.get("fold_detail") or []))),
                "disagreements": sum(r.get("diagnosis") == "MANY_CONSISTENT_DISAGREE" for r in v.values()),
                "cpu_s_mean": round(st.mean((r.get("cpu_reason_s") or 0) + (r.get("cpu_diagnose_s") or 0) for r in v.values()), 1),
                "wall_s_mean": round(st.mean(r.get("wall_s", 0) for r in v.values()), 1),
                "resource_rows": sum(r.get("diagnosis") in ("RESOURCE_LIMIT", "ERROR") or bool(r.get("error"))
                                     for r in v.values())}
    rep["new_correct_certified"] = ev["new_correct_certified"]
    rep["new_correct_exploratory"] = ev["new_correct_exploratory"]
    rep["solved_by_A_or_B_not_by_V"] = ev["solved_by_A_or_B_not_by_V"]
    rep["lost_in_a_native_first_combination"] = 0      # V only adds where A and B have no answer; nothing is displaced
    leak = 0
    for a in ("A", "B", "V"):
        for r in R[a].values():
            txt = json.dumps(r)
            leak += any(k in txt for k in ('"test_output', '"solution', '"answer'))
    rep["rows_with_answer_fields"] = leak
    json.dump(rep, open(os.path.join(EVAL, "phase2a_report.json"), "w"), indent=1)
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    sys.exit(main())
