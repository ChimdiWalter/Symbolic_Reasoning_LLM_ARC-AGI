"""Transparent rules-based revision controller (DEVELOPMENT baseline: it selects an action and executes
nothing).

  python -m cora_fhr.revision_controller   -> outputs/cora_fhr/revision_controller_decisions_20261018.json

It maps an **observable** failure state to one typed action, with the rule that fired. It is a
hand-written baseline from the root-cause autopsy (records/CORA_REVISION_ROOT_CAUSE_20261018.md), not a
learned policy and not evidence of automatic repair.

**Reads only** the fields in OBSERVABLE:
- native's own run record;
- E's evidence summary and proposal outcome;
- the read-only re-extraction diagnostics.

It never reads answers, evaluator categories or generator labels.

Actions:
- NONE: native certified; keep its answer.
- ENGINE_ERROR: a software exception, recorded and never counted as reasoning. The CPU `hard_cap` is a
  resource limit, not an error.
- RETRY_SEARCH: a budget-limited stage: an extraction cap, or native fitted but its leave-one-out rejected.
- REVISE_REPRESENTATION: native failed at segmentation or matching. No such revision is implemented, so it
  is selected but unavailable.
- CONSTRUCT_OR_REVISE_PROGRAM: the evidence is jointly expressible (the existing FHR path).
- CONSTRUCT_WITH_GUARD: the evidence is expressible per instance but not jointly. This is a hypothesis
  only; nothing is implemented.
- ABSTAIN_OR_REQUEST_EVIDENCE: the evidence is unsupported or inexpressible, or nothing applies.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
OUT = os.path.join(HERE, "outputs", "cora_fhr")

ACTIONS = ("NONE", "ENGINE_ERROR", "RETRY_SEARCH", "REVISE_REPRESENTATION", "CONSTRUCT_OR_REVISE_PROGRAM",
           "CONSTRUCT_WITH_GUARD", "ABSTAIN_OR_REQUEST_EVIDENCE")
OBSERVABLE = ("native_accepted", "native_failure_stage", "native_error", "native_timeout", "evidence_views",
              "evidence_cap", "proposal_outcome", "diag_support_ok", "diag_joint_fit", "diag_singly_expressible")
AVAILABLE = {"NONE", "ENGINE_ERROR", "RETRY_SEARCH", "CONSTRUCT_OR_REVISE_PROGRAM", "ABSTAIN_OR_REQUEST_EVIDENCE"}


def decide(state):
    """state: a dict; only the OBSERVABLE keys are read. Returns {action, rule, available}."""
    s = {k: state.get(k) for k in OBSERVABLE}
    if s["native_error"]:
        a, rule = "ENGINE_ERROR", "native raised"
    elif s["native_accepted"]:
        a, rule = "NONE", "native certified"
    elif s["evidence_cap"]:
        a, rule = "RETRY_SEARCH", "evidence extraction hit its CPU cap"
    elif s["evidence_views"]:
        if s["diag_support_ok"] is False:
            a, rule = "ABSTAIN_OR_REQUEST_EVIDENCE", "growth evidence from fewer than 2 demonstrations"
        elif s["diag_joint_fit"]:
            a, rule = "CONSTRUCT_OR_REVISE_PROGRAM", "evidence jointly expressible"
        elif s["diag_singly_expressible"]:
            a, rule = "CONSTRUCT_WITH_GUARD", "instances expressible singly, not jointly"
        elif s["diag_support_ok"] is None:
            a, rule = "CONSTRUCT_OR_REVISE_PROGRAM", "evidence present; diagnostics absent (the existing FHR path decides)"
        else:
            a, rule = "ABSTAIN_OR_REQUEST_EVIDENCE", "evidence inexpressible in the declared grammar"
    elif s["native_timeout"]:
        a, rule = "RETRY_SEARCH", "native search hit its CPU cap; no growth evidence"
    elif s["native_failure_stage"] == "loo":
        a, rule = "RETRY_SEARCH", "native fitted but its leave-one-out rejected; no growth evidence"
    elif s["native_failure_stage"] in ("segmentation", "matching"):
        a, rule = "REVISE_REPRESENTATION", f"native failed at {s['native_failure_stage']}; no growth evidence"
    else:
        a, rule = "ABSTAIN_OR_REQUEST_EVIDENCE", "no applicable revision"
    assert a in ACTIONS
    return {"action": a, "rule": rule, "available": a in AVAILABLE}


def state_from(row, diag=None):
    """Observable state from a measure/fhr row, plus optional read-only diagnostics (root_cause_reextract)."""
    E = row["arms"].get("E") or {}
    A = (row["arms"].get("A") or {}).get("run") or {}
    ev = E.get("evidence") or {}
    st = {"native_accepted": bool(A.get("accepted")), "native_failure_stage": A.get("failure_stage"),
          "native_error": (A.get("error") not in (None, "", "hard_cap")) or bool(row.get("error")),
          "native_timeout": bool(A.get("timeout")) or A.get("error") == "hard_cap",
          "evidence_views": ev.get("views") or {}, "evidence_cap": ev.get("why_empty"),
          "proposal_outcome": E.get("outcome"),
          "diag_support_ok": None, "diag_joint_fit": None, "diag_singly_expressible": None}
    if diag:
        pv = diag["per_view"].values()
        st["diag_support_ok"] = any(p["support_ok"] for p in pv)
        st["diag_joint_fit"] = any(p["joint_fit"] for p in pv if p["support_ok"])
        st["diag_singly_expressible"] = any(p["singly_expressible"] >= 2 for p in pv if p["support_ok"])
    return st


def main():
    import collections
    reh = [json.loads(x) for x in open(os.path.join(HERE, "outputs", "kaggle_deploy", "cora_fhr_v1", "run_v1", "fhr_rows.jsonl"))]
    dev = [json.loads(x) for x in open(os.path.join(OUT, "rows_dev60.jsonl"))]
    rx = os.path.join(OUT, "root_cause_reextract_20261018.json")
    diags = {c["key"]: c for c in json.load(open(rx))["cases"]} if os.path.exists(rx) else {}
    out = {}
    for name, rows in (("rehearsal_62", [r for r in reh if r.get("fhr") == "ran"]), ("dev60", dev)):
        dec = [dict(key=r["key"], **decide(state_from(r, diags.get(r["key"])))) for r in rows]
        out[name] = {"by_action": dict(collections.Counter(d["action"] for d in dec)),
                     "by_rule": dict(collections.Counter(d["rule"] for d in dec)), "decisions": dec}
        print(name, out[name]["by_action"])
    json.dump(out, open(os.path.join(OUT, "revision_controller_decisions_20261018.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
