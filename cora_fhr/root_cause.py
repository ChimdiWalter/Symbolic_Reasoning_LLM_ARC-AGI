"""CORA-FHR proposal-bottleneck autopsy (DEVELOPMENT; read-only over retained rows unless --reextract).

  python -m cora_fhr.root_cause                 -> outputs/cora_fhr/root_cause_20261018.json (logs only)
  python -m cora_fhr.root_cause --reextract     -> + root_cause_reextract_20261018.json (declared dev60 cases)

Log mode classifies every case from the retained rows.
- The Kaggle committed rehearsal: `outputs/kaggle_deploy/cora_fhr_v1/run_v1/fhr_rows.jsonl`, 240 stand-in
  training tasks, 62 of which ran FHR.
- The 60 real development tasks: `outputs/cora_fhr/rows_dev60.jsonl`.

Observable at inference (the solver's own trace):
- native's failure stage;
- whether native's identity-frame induction recorded any single-colour memorized-growth (`pattern`)
  correspondence (E's evidence);
- per-view instance counts;
- extraction caps;
- the proposal outcome.

Evaluator-only (answers; dev60 only): the funnel category of native's run, from
`outputs/funnel_v0/eval_dev60_native_assets.json`.

The --reextract mode applies to a declared case set: every dev60 task where E had evidence but no proposal.
It re-runs only E's evidence extraction, the same code, on this machine. For every view it reports:
- the demonstrations covered (support needs at least 2);
- the joint G-grow fit;
- how many instances are expressible on their own.

The task is then classified as one of:
- INSUFFICIENT_SUPPORT;
- GROUPING_CONFLICT (instances expressible singly, not jointly);
- INEXPRESSIBLE (no G-grow expression reproduces even single instances: the declared language lacks the
  operation for that evidence; the enumeration is exhaustive);
- NOT_REPRODUCED (re-extraction differs from the logged evidence).

No answer is read in that mode.
"""
import argparse
import collections
import json
import multiprocessing as mp
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
OUT = os.path.join(HERE, "outputs", "cora_fhr")
REH = os.path.join(HERE, "outputs", "kaggle_deploy", "cora_fhr_v1", "run_v1", "fhr_rows.jsonl")
DEV = os.path.join(OUT, "rows_dev60.jsonl")
FUNNEL = os.path.join(HERE, "outputs", "funnel_v0", "eval_dev60_native_assets.json")
REJECT = ("ENGINE_REJECTION", "ROUTING_FAILURE", "LOO_FAILURE", "ABSTAIN_TIE")


def classify(row):
    E = row["arms"].get("E") or {}
    A = (row["arms"].get("A") or {}).get("run") or {}
    ev = E.get("evidence") or {}
    views = ev.get("views") or {}
    o = E.get("outcome")
    if row.get("error"):
        cls = "SOFTWARE_EXCEPTION"
    elif ev.get("why_empty"):
        cls = "RESOURCE_CAP_EXTRACTION"
    elif o == "CERTIFIED_WITH_EXTENSION":
        cls = "CERTIFIED"
    elif o in REJECT:
        cls = {"ENGINE_REJECTION": "PROPOSAL_NATIVE_REJECTION", "ROUTING_FAILURE": "PROPOSAL_NOT_ROUTED",
               "LOO_FAILURE": "PROPOSAL_RECONSTRUCTION_FAILURE", "ABSTAIN_TIE": "PROPOSAL_AMBIGUOUS"}[o]
    elif not views:
        cls = "NO_MEMORIZED_GROWTH_EVIDENCE"
    else:
        cls = "EVIDENCE_BUT_NO_OPERATOR"       # support vs grammar: undetermined from logs
    sel = (E.get("selected") or {})
    return {"key": row["key"], "class": cls, "outcome": o, "views": views,
            "max_view_instances": max(views.values()) if views else 0,
            "native_failure_stage": A.get("failure_stage"), "native_timeout": A.get("timeout"),
            "native_error": (str(A.get("error"))[:80] if A.get("error") else None),
            "proposal": sel.get("pretty"), "novelty": (sel.get("novelty") or {}).get("class"),
            "folds": [f.get("class") for f in (E.get("folds") or []) if isinstance(f, dict)],
            "E_cpu_s": E.get("cpu_s"), "A_cpu_s": (row["arms"].get("A") or {}).get("cpu_s")}


def log_mode():
    reh = [json.loads(x) for x in open(REH)]
    dev = [json.loads(x) for x in open(DEV)]
    funnel = {t["key"]: t["category"] for t in json.load(open(FUNNEL))["tasks"]}
    out = {"rehearsal": {"status": dict(collections.Counter(
        r.get("fhr") + (":" + r["reason"] if r.get("reason") else "") for r in reh)), "cases": []},
        "dev60": {"cases": []}}
    for r in reh:
        if r.get("fhr") == "ran":
            out["rehearsal"]["cases"].append(classify(r))
    for r in dev:
        c = classify(r)
        c["evaluator_only_funnel_category"] = funnel.get(r["key"])
        out["dev60"]["cases"].append(c)
    for part in ("rehearsal", "dev60"):
        cs = out[part]["cases"]
        out[part]["by_class"] = dict(collections.Counter(c["class"] for c in cs))
        out[part]["by_class_x_native_stage"] = {f"{k[0]} | {k[1]}": v for k, v in sorted(collections.Counter(
            (c["class"], str(c["native_failure_stage"])) for c in cs).items())}
    out["dev60"]["by_class_x_funnel"] = {f"{k[0]} | {k[1]}": v for k, v in sorted(collections.Counter(
        (c["class"], c["evaluator_only_funnel_category"]) for c in out["dev60"]["cases"]).items())}
    json.dump(out, open(os.path.join(OUT, "root_cause_20261018.json"), "w"), indent=1)
    for part in ("rehearsal", "dev60"):
        print(part, len(out[part]["cases"]), out[part]["by_class"])
    return out


def _reextract(args):
    key, view, logged = args
    import numpy as np
    from cora_fhr import construct as CS
    from cora_fhr import ggrow as GG
    from cora_fhr import measure as M
    from cora_pilot import native as N
    M.FR.cpu_clock()
    train = [(np.asarray(p["input"], dtype=int), np.asarray(p["output"], dtype=int)) for p in view["train"]]
    base = os.path.join(OUT, "engines_rootcause", key)
    raw, why = M.authentic_raw(train, N.prepare_object_dir(os.path.join(base, "extract")))
    groups = CS.group_reach_records(raw)
    rec = {"key": key, "why_empty": why, "views": {v: len(x) for v, x in groups.items()}, "logged_views": logged,
           "per_view": {}}
    rec["reproduced"] = rec["views"] == logged
    for v, insts in sorted(groups.items()):
        insts = insts[:CS.MAX_INSTANCES]
        demos = sorted({d for *_x, d, _c in insts if d is not None})
        trip = [(O, A, G) for O, A, G, _d, _c in insts]
        joint = GG.search(trip)[0] if len(demos) >= CS.SUPPORT_DEMOS else None
        single = sum(GG.search([t])[0] is not None for t in trip)
        rec["per_view"][v] = {"instances": len(insts), "demos": demos, "support_ok": len(demos) >= CS.SUPPORT_DEMOS,
                              "joint_fit": GG.pretty(joint) if joint else None, "singly_expressible": single}
    pv = rec["per_view"].values()
    if not rec["reproduced"]:
        rec["class"] = "NOT_REPRODUCED"
    elif not any(p["support_ok"] for p in pv):
        rec["class"] = "INSUFFICIENT_SUPPORT"
    elif any(p["joint_fit"] for p in pv if p["support_ok"]):
        rec["class"] = "JOINT_FIT_EXISTS"                 # would contradict the logged NO_PROPOSAL
    elif any(p["singly_expressible"] >= 2 for p in pv if p["support_ok"]):
        rec["class"] = "GROUPING_CONFLICT"
    else:
        rec["class"] = "INEXPRESSIBLE"
    return rec


def reextract_mode(out, workers):
    from cora_funnel import run as FR
    view = dict(FR.load("dev60"))
    cases = [(c["key"], view[c["key"]], c["views"]) for c in out["dev60"]["cases"] if c["class"] == "EVIDENCE_BUT_NO_OPERATOR"]
    print(f"re-extracting {len(cases)} declared dev60 cases", flush=True)
    res = []
    with mp.get_context("fork").Pool(workers, maxtasksperchild=1) as pool:
        for r in pool.imap_unordered(_reextract, cases):
            res.append(r)
            print(r["key"], r["class"], {v: (p["demos"], p["joint_fit"], p["singly_expressible"]) for v, p in r["per_view"].items()},
                  flush=True)
    summary = dict(collections.Counter(r["class"] for r in res))
    json.dump({"cases": sorted(res, key=lambda r: r["key"]), "by_class": summary},
              open(os.path.join(OUT, "root_cause_reextract_20261018.json"), "w"), indent=1)
    print("re-extraction:", summary)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--reextract", action="store_true")
    ap.add_argument("--workers", type=int, default=2)
    a = ap.parse_args(argv)
    out = log_mode()
    if a.reextract:
        reextract_mode(out, a.workers)


if __name__ == "__main__":
    main()
