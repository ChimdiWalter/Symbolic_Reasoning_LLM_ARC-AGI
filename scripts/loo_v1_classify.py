"""Classification of the adaptive LOO diagnosis (docs/CORA_REAL_TASK_LOO_STABILITY_v1.md
section 6), fixed before the diagnosis run and pinned by its manifest.

  python scripts/loo_v1_classify.py   -> outputs/loo_v1/diagnosis.json

First rule that applies, per outer fold: H5 RESOURCE, H1 IDENTIFIABILITY,
H3 EVIDENCE_INSTABILITY, H4 ORDERING, H2 RE-INDUCTION, H6
INSUFFICIENT_RELATION, UNRESOLVED. The same rules classify each full-data
rejection (arm A_E). Also: the outer against the inner (native) leave-one-
out, per task. Reads the diagnosis rows, the isolation logs and the
record; no target.
"""
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
OUT = os.path.join(HERE, "outputs", "loo_v1")
LOG = os.path.join(HERE, "logs", "loo_v1")
STAGE_ORDER = {"segmentation": 0, "matching": 1, "selector": 2, "parameter": 3, "loo": 4, None: 5}
HYPOTHESES = ("H5_RESOURCE", "H1_IDENTIFIABILITY", "H3_EVIDENCE_INSTABILITY", "H4_ORDERING",
              "H2_RE_INDUCTION", "H6_INSUFFICIENT_RELATION", "UNRESOLVED")


def identity(run):
    """The identity-frame induction of an engine run (the first traced one)."""
    ind = ((run or {}).get("trace") or {}).get("inductions") or []
    return ind[0] if ind else {}


def stage(run):
    if run is None:
        return "none"
    if run.get("accepted"):
        return None
    return identity(run).get("failure_stage") or run.get("failure_stage") or "unknown"


def rank(run):
    """Progress of a run: 5 accepted, 4 train-exact but rejected by the
    engine's leave-one-out, lower for earlier stages, -1 no run."""
    if run is None:
        return -1
    if run.get("accepted"):
        return 5
    return STAGE_ORDER.get(stage(run), -1)


def budget_hit(run):
    return bool(run and (run.get("timeout") or sum((run.get("deadline_hits") or {}).values())))


def nested(run):
    return any("'LOO'" in k for k in ((run or {}).get("deadline_hits") or {}))


def unexplained(run):
    ns = identity(run).get("near_solve") or {}
    return sum((u.get("count") or 0) for u in (ns.get("unexplained") or []))


def inner_loo(run):
    """The engine's own leave-one-out of the identity frame: folds, passed,
    and per fold the re-induced result."""
    ind = identity(run)
    loo = ind.get("loo") or {}
    out = {"folds": loo.get("folds"), "passed": loo.get("passed"), "failed": loo.get("failed")}
    tops = [x for x in (((run or {}).get("trace") or {}).get("inner_loo") or []) if x.get("ctx") == "('TOP',)"]
    if tops:
        out["fold_results"] = [{"hold": f.get("hold"), "n_sub": f.get("n_sub"), "engine_s": f.get("engine_s"),
                                "accepted": (f.get("result") or {}).get("accepted"),
                                "stage": (f.get("result") or {}).get("failure_stage"),
                                "train_fit": (f.get("result") or {}).get("train_fit_pixels")}
                               for f in tops[0]["folds"]]
    return out


def classify_fold(r):
    bw, bc = r["B_WALL"], r["B_CPU1"]
    ew, ec = bw.get("engine"), bc.get("engine")
    ev = {"B_WALL": {"selected": bw["selected"], "same_as_full": bw["same_as_full"], "stage": stage(ew),
                     "accepted": (ew or {}).get("accepted"), "heldout_exact": (ew or {}).get("heldout_exact"),
                     "budget_hit": budget_hit(ew), "nested_deadline": nested(ew), "timeout": (ew or {}).get("timeout"),
                     "cpu_share": (ew or {}).get("cpu_share"), "wall_s": (ew or {}).get("wall_s")},
          "B_CPU1": {"selected": bc["selected"], "same_as_full": bc["same_as_full"], "stage": stage(ec),
                     "accepted": (ec or {}).get("accepted"), "heldout_exact": (ec or {}).get("heldout_exact"),
                     "budget_hit": budget_hit(ec), "nested_deadline": nested(ec)},
          "extract_WALL": {k: bw["extract"].get(k) for k in ("instances", "demos", "timeout", "wall_s", "cpu_s",
                                                              "deadline_hits")},
          "extract_CPU1": {k: bc["extract"].get(k) for k in ("instances", "demos", "timeout", "wall_s", "cpu_s",
                                                              "deadline_hits")},
          "restricted_proposals": [p["name"] for p in r["restricted"]["proposals"]],
          "proposals_WALL": [(p["family"], p["variant"]) for p in bw["proposals"]],
          "heldout_distinguish_WALL": bw["heldout_distinguish"],
          "inner_loo_WALL": inner_loo(ew)}
    for arm in ("C_WALL", "C_CPU1"):
        c = r[arm]
        ev[arm] = "same as B" if c.get("same_as_B") else {
            "accepted": c["engine"]["accepted"], "heldout_exact": c["engine"].get("heldout_exact"),
            "stage": stage(c["engine"]), "budget_hit": budget_hit(c["engine"])}
    for arm in ("D_WALL", "E_WALL"):
        ev[arm] = {"accepted": r[arm]["accepted"], "heldout_exact": r[arm].get("heldout_exact"),
                   "stage": stage(r[arm]), "budget_s": r[arm]["budget_s"]}
    #  H5: the decisive run is resource-limited under WALL and not under CPU1
    if ew is not None and budget_hit(ew) and rank(ec) > rank(ew):
        return ("H5_RESOURCE", "NESTED_DEADLINE" if nested(ew) else "TOP_OR_CAP"), ev
    if ew is None and budget_hit(bw["extract"]) and bc["selected"] is not None:
        return ("H5_RESOURCE", "EXTRACTION"), ev
    if ew is None:
        if not r["restricted"]["proposals"]:
            variants = r["restricted"]["analysis"]["variants"].values()
            if not variants:
                return ("H1_IDENTIFIABILITY", "NO_INSTANCES"), ev
            if all(not v["support_ok"] for v in variants):
                return ("H1_IDENTIFIABILITY", "SUPPORT"), ev
            return ("H1_IDENTIFIABILITY", "NO_SINGLE_SETTING"), ev
        return ("H3_EVIDENCE_INSTABILITY", "REEXTRACTION_DIFFERS"), ev
    if not bw["same_as_full"]:
        names = [p["name"] for p in bw["proposals"]]
        dist = {d["name"]: d for d in bw["heldout_distinguish"]}
        sel, full = dist.get(bw["selected"]), dist.get(r["e_full"])
        if r["e_full"] in names and sel and full and full["reproduces"] == full["heldout_instances"] > 0 \
                and sel["reproduces"] < sel["heldout_instances"]:
            return ("H4_ORDERING", "HELDOUT_DISTINGUISHES"), ev
    if stage(ew) == "loo" and not budget_hit(ew):
        return ("H2_RE_INDUCTION", "INNER_LOO_REJECTS"), ev
    if stage(ew) in ("segmentation", "matching", "selector", "parameter") and unexplained(ew) > 0:
        return ("H6_INSUFFICIENT_RELATION", f"NO_TRAIN_EXACT_AT_{stage(ew).upper()}"), ev
    return ("UNRESOLVED", stage(ew)), ev


def classify_full(r):
    aw, ac = r["A_E_WALL"], r["A_E_CPU1"]
    ev = {"A_E_WALL": {"accepted": aw["accepted"], "uses": aw.get("uses"), "stage": stage(aw),
                       "budget_hit": budget_hit(aw), "nested_deadline": nested(aw), "timeout": aw["timeout"],
                       "frames_run": aw.get("frames_run"), "cpu_share": aw.get("cpu_share"), "wall_s": aw.get("wall_s")},
          "A_E_CPU1": {"accepted": ac["accepted"], "uses": ac.get("uses"), "stage": stage(ac),
                       "budget_hit": budget_hit(ac), "timeout": ac["timeout"], "wall_s": ac.get("wall_s"),
                       "cpu_s": ac.get("cpu_s")},
          "A_K_WALL": {"accepted": r["A_K_WALL"]["accepted"], "stage": stage(r["A_K_WALL"]),
                       "timeout": r["A_K_WALL"]["timeout"]},
          "A_K_CPU1": {"accepted": r["A_K_CPU1"]["accepted"], "stage": stage(r["A_K_CPU1"]),
                       "timeout": r["A_K_CPU1"]["timeout"]},
          "inner_loo_WALL": inner_loo(aw), "inner_loo_CPU1": inner_loo(ac),
          "substitutions_WALL": aw.get("substitutions")}
    if aw["accepted"]:
        return ("ACCEPTED", None), ev
    if budget_hit(aw) and rank(ac) > rank(aw):
        return ("H5_RESOURCE", "NESTED_DEADLINE" if nested(aw) else "TOP_OR_CAP"), ev
    if stage(aw) == "loo" and not budget_hit(aw):
        return ("H2_RE_INDUCTION", "INNER_LOO_REJECTS"), ev
    if stage(aw) in ("segmentation", "matching", "selector", "parameter") and unexplained(aw) > 0:
        return ("H6_INSUFFICIENT_RELATION", f"NO_TRAIN_EXACT_AT_{stage(aw).upper()}"), ev
    return ("UNRESOLVED", stage(aw)), ev


def main():
    from cora_pilot import isolation as ISO
    rows = {}
    for line in open(os.path.join(OUT, "diagnose_rows.jsonl")):
        if line.strip():
            r = json.loads(line)
            rows[r["key"]] = r
    record = json.load(open(os.path.join(LOG, "diagnose_0_record.json")))
    problems = []
    if sorted(rows) != sorted(record["units"]):
        problems.append("rows differ from the unit list")
    errors = sorted(k for k, r in rows.items() if r.get("class") == "RUN_ERROR")
    problems += [f"RUN_ERROR {k}" for k in errors]
    problems += [f"not restored {k}" for k, r in rows.items() if k not in errors and not r.get("restored")]
    for f in sorted(os.listdir(LOG)):
        if f.startswith("isolation_diagnose_"):
            problems += [f"{f}: {p}" for p in ISO.audit_log(json.load(open(os.path.join(LOG, f))))]
    folds, full = {}, {}
    for k, r in sorted(rows.items()):
        if k in errors:
            continue
        if r["kind"] == "fold":
            (h, sub), ev = classify_fold(r)
            folds[k] = {"task": r["task"], "fold": r["fold"], "hypothesis": h, "sub": sub, "evidence": ev,
                        "reach_v1_fold": r.get("reach_v1_fold")}
        else:
            (h, sub), ev = classify_full(r)
            full[k] = {"task": r["task"], "hypothesis": h, "sub": sub, "evidence": ev}
    out = {"problems": problems, "units": len(rows), "fold_hypotheses": dict(Counter(v["hypothesis"] for v in
                                                                                     folds.values())),
           "fold_sub": dict(Counter(f"{v['hypothesis']}:{v['sub']}" for v in folds.values())),
           "full_hypotheses": {k: (v["hypothesis"], v["sub"]) for k, v in full.items()},
           "folds": folds, "full": full}
    with open(os.path.join(OUT, "diagnosis.json"), "w") as handle:
        json.dump(out, handle, indent=1, sort_keys=True, default=str)
    print(json.dumps({k: out[k] for k in ("problems", "units", "fold_hypotheses", "fold_sub", "full_hypotheses")},
                     indent=1, default=str))


if __name__ == "__main__":
    main()
