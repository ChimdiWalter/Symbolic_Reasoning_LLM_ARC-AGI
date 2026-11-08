"""U5 policy freeze (calibration only), decisions on evaluation parents (after the hold), and the evaluator
(PROTOCOL.md sections 11 to 14; Amendments 1 and 2). <python environment>, python -I.
    u5eval.py roles                  assign A, B, C from eligibility and gates -> work/ROLES.json
    u5eval.py freeze                 in-domain induction on B and C, final fits, ALL_ON, MATCHED_SEARCH -> POLICY_FREEZE
    u5eval.py strong_eval DS         STRONG_NATIVE on the evaluation images (after their segmentation)
    u5eval.py decide                 every arm on every target's evaluation parents; DECISIONS_FROZEN.json
    u5eval.py evaluate               open the evaluator; results/RESULTS.json and results/SUMMARY.md"""
import hashlib
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import u5core as C      # noqa: E402
import u5data as UD     # noqa: E402
import u5induce as IN   # noqa: E402
import u5run as RN      # noqa: E402
import u5static as ST   # noqa: E402

W, E = RN.W, IN.E
ORDER = ("livecell", "nuinsseg", "monusac", "fnc")          # Amendment 4 adds MoNuSAC before FNC (ineligible)
DEC = os.path.join(W, "decisions")
RES = os.path.join(E, "results")
MIN_CAL, MIN_EV = 10, 15
RND = 0.05                  # Amendment 7: half a unit of a CPU value written to one decimal
# Amendment 9: a CORA calibration CPU built from records without exact CPU carries, besides three one-decimal and one
# two-decimal roundings (0.155 s), the 0.001 s rounding of each probe child before summation (at most 7 classes x 40
# tasks = 280 children, 0.140 s): at least 0.295 s in all. The legacy slack is 0.30 s.
LEGACY_SLACK_S = 0.30
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()      # noqa: E731


def jdump(x, p):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(x, open(p, "w"), indent=1, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o))


def uids(ds, side=None, roles=None):
    m = RN.man(ds)["images"]
    return sorted(u for u, v in m.items() if (side is None or v["side"] == side) and (roles is None or v["role"] in roles))


# ------------------------------------------------------------------------------------------------ roles ------------
def roles():
    out = {"ineligible": {"fluoecoli": "file names are bare indices and the COCO records carry no source image "
                                       "(Amendment 2, section 1)"}, "unsuitable": {}, "order": list(ORDER)}
    # Amendment 3: FNC's coarsest encoded unit (the animal) gives 22 groups, fewer than 10 + 15
    ok = []
    for ds in ORDER:
        m = RN.man(ds)
        nc, ne = len(m["parents"]["calibration"]), m.get("n_evaluation_parents_with_images",
                                                           len(m["parents"]["evaluation"]))
        if nc < MIN_CAL or ne < MIN_EV:
            out["ineligible"][ds] = f"parents {nc}/{ne}"
            continue
        gp = os.path.join(W, ds, "GATE.json")
        if not os.path.exists(gp):
            out.setdefault("pending", []).append(ds)          # added later by freeze_target (Amendment 4)
            continue
        g = json.load(open(gp))
        if not g["PASS"]:
            out["unsuitable"][ds] = {k: g[k] for k in ("error_share", "oracle_gain")}
            continue
        ok.append(ds)
    out["A"] = ok[0] if ok else None
    out["targets"] = ok[1:3]
    jdump(out, os.path.join(W, "ROLES.json"))
    print(json.dumps(out))
    return out


# ------------------------------------------------------------------------------------------------ freeze -----------
def final_fit(ds, grammar):
    """The section 10 policy fitted on all calibration parents of ds (no queries): top program per operator, CPU."""
    D = RN.ImgSet(ds, uids(ds, "calibration"), "S", True)
    r = RN.run_policy(list(grammar), D, None)
    return {"ops": r["ops"], "cpu_s": r["cpu_s"]}


def freeze():
    ro = json.load(open(os.path.join(W, "ROLES.json")))
    A = ro["A"]
    ind = json.load(open(os.path.join(W, A, "INDUCTION.json")))
    pf = {"roles": ro, "grammars": {"CORA": ind["CORA"]["admitted"], "CORA_FULL": list(C.OPS),
                                    "FAILURE_BLIND": {r: v["admitted"] for r, v in ind["FAILURE_BLIND"].items()},
                                    "SHUFFLED": {r: v["admitted"] for r, v in ind["SHUFFLED"].items()}},
          "induction_sha256": sha(os.path.join(W, A, "INDUCTION.json")), "targets": {}}
    a_ind_cpu = ind["cora_induction_cpu_s"]
    for X in [A] + ro["targets"]:
        t = {}
        if X != A:
            spec, fr, gains = IN.specify(X)
            adm, trail, cpu = IN.admit(X, spec)
            t["INDOMAIN"] = {"specified": spec, "admitted": adm, "trail": trail, "admission_cpu_s": cpu,
                             "failure_records": fr["per_class"], "probe_cpu_s": fr["probe_cpu_s"]}
        ff = final_fit(X, pf["grammars"]["CORA"])
        t["CORA_final_fit"] = ff
        cora_cpu = ff["cpu_s"] + a_ind_cpu
        t["CORA_calibration_cpu_s"] = round(cora_cpu, 1)
        t["CORA_calibration_cpu_s_recorded_sum"] = cora_cpu         # Amendment 9: components as recorded (rounded)
        t["CORA_calibration_cpu_s_conservative_upper"] = cora_cpu + LEGACY_SLACK_S
        t["ALL_ON"] = ST.fit_all_on(X, uids(X, "calibration"))
        t["MATCHED_SEARCH"] = ST.fit_matched(X, uids(X, "calibration"), cora_cpu)
        pf["targets"][X] = t
        jdump(pf, os.path.join(W, "POLICY_FREEZE.json"))
    pf["frozen_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    jdump(pf, os.path.join(W, "POLICY_FREEZE.json"))
    jdump(pf, os.path.join(E, "POLICY_FREEZE.json"))
    print(json.dumps({X: {"cora_cpu": v["CORA_calibration_cpu_s"], "all_on_f1": v["ALL_ON"]["cal_f1"],
                          "matched": {k: v["MATCHED_SEARCH"][k] for k in ("cal_f1", "cpu_s", "stopped")},
                          "indomain": v.get("INDOMAIN", {}).get("admitted")} for X, v in pf["targets"].items()}))


def _freeze_one(X, A, ind, pf):
    a_ind_cpu = ind["cora_induction_cpu_s"]
    t = {}
    if X != A:
        spec, fr, gains = IN.specify(X)
        adm, trail, cpu = IN.admit(X, spec)
        t["INDOMAIN"] = {"specified": spec, "admitted": adm, "trail": trail, "admission_cpu_s": cpu,
                         "failure_records": fr["per_class"], "probe_cpu_s": fr["probe_cpu_s"]}
    ff = final_fit(X, pf["grammars"]["CORA"])
    t["CORA_final_fit"] = ff
    cora_cpu = ff["cpu_s"] + a_ind_cpu
    t["CORA_calibration_cpu_s"] = round(cora_cpu, 1)
    t["CORA_calibration_cpu_s_recorded_sum"] = cora_cpu
    t["CORA_calibration_cpu_s_conservative_upper"] = cora_cpu + LEGACY_SLACK_S
    t["ALL_ON"] = ST.fit_all_on(X, uids(X, "calibration"))
    t["MATCHED_SEARCH"] = ST.fit_matched(X, uids(X, "calibration"), cora_cpu)
    return t


def freeze_target(X):
    """Amendment 4: add a transfer target whose calibration finished after the main freeze."""
    pf = json.load(open(os.path.join(W, "POLICY_FREEZE.json")))
    ro = pf["roles"]
    m = RN.man(X)
    g = json.load(open(os.path.join(W, X, "GATE.json")))
    nc = len(m["parents"]["calibration"])
    ne = m.get("n_evaluation_parents_with_images", len(m["parents"]["evaluation"]))
    if nc < MIN_CAL or ne < MIN_EV:
        ro.setdefault("ineligible", {})[X] = f"parents {nc}/{ne}"
    elif not g["PASS"]:
        ro.setdefault("unsuitable", {})[X] = {k: g[k] for k in ("error_share", "oracle_gain")}
    elif X != ro["A"] and X not in ro["targets"] and len(ro["targets"]) < 2:
        ind = json.load(open(os.path.join(W, ro["A"], "INDUCTION.json")))
        pf["targets"][X] = _freeze_one(X, ro["A"], ind, pf)
        ro["targets"] = ro["targets"] + [X]
    if X in ro.get("pending", []):
        ro["pending"] = [d for d in ro["pending"] if d != X]
    pf["roles"] = ro
    pf["frozen_utc_" + X] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    jdump(ro, os.path.join(W, "ROLES.json"))
    jdump(pf, os.path.join(W, "POLICY_FREEZE.json"))
    jdump(pf, os.path.join(E, "POLICY_FREEZE.json"))
    print(json.dumps({"roles": ro}))


def strong_eval(ds):
    RN.strong_native(ds, "evaluation")


# ------------------------------------------------------------------------------------------------ decisions --------
def _save_arm(X, arm, labels, log, extra=None):
    d = os.path.join(DEC, X)
    os.makedirs(d, exist_ok=True)
    np.savez_compressed(os.path.join(d, f"{arm}.npz"), **{u: labels[u] for u in sorted(labels)})
    jdump({"arm": arm, "log": log, **(extra or {})}, os.path.join(d, f"{arm}.json"))
    return {"labels": sha(os.path.join(d, f"{arm}.npz")), "log": sha(os.path.join(d, f"{arm}.json"))}


FROZEN2 = os.path.join(W, "DECISIONS_FROZEN_SECONDARY.json")


def decide(scope="primary"):
    """Amendment 6: PRIMARY arms (NATIVE, TUNED, STRONG_NATIVE, ALL_ON, MATCHED_SEARCH, CORA, FAILURE_BLIND x5,
    SHUFFLED x5, on A and every transfer target) are decided and frozen first; SECONDARY arms (CORA_FULL,
    CORA_INDOMAIN, PROGRAM_TRANSFER, NEURAL_PROPOSER) afterwards, by the same frozen code and policy, with no access to
    evaluation references (the Reader guard), into DECISIONS_FROZEN_SECONDARY.json."""
    pf = json.load(open(os.path.join(W, "POLICY_FREEZE.json")))
    ro = pf["roles"]
    A = ro["A"]
    frozen = {"scope": scope, "policy_freeze": sha(os.path.join(W, "POLICY_FREEZE.json")), "arms": {}}
    for X in [A] + ro["targets"]:
        cal, ev = uids(X, "calibration"), uids(X, "evaluation")
        fr = frozen["arms"].setdefault(X, {})
        t = pf["targets"][X]
        if scope == "primary":
            for arm, stage in (("NATIVE", "native"), ("TUNED", "tuned"), ("STRONG_NATIVE", "S")):
                fr[arm] = _save_arm(X, arm, {u: RN.lab(X, stage, u) for u in ev}, [])
            Q = RN.ImgSet(X, ev, "S", False)
            t0 = time.process_time()
            log = ST.apply_all_on(Q, t["ALL_ON"]["values"])
            fr["ALL_ON"] = _save_arm(X, "ALL_ON", Q.L, log, {"apply_cpu_s": round(time.process_time() - t0, 1)})
            Q = RN.ImgSet(X, ev, "S", False)
            log = ST.apply_program(Q, t["MATCHED_SEARCH"]["program"])
            fr["MATCHED_SEARCH"] = _save_arm(X, "MATCHED_SEARCH", Q.L, log)
            grams = {"CORA": pf["grammars"]["CORA"]}
            grams.update({f"FAILURE_BLIND_{r}": g for r, g in pf["grammars"]["FAILURE_BLIND"].items()})
            grams.update({f"SHUFFLED_{r}": g for r, g in pf["grammars"]["SHUFFLED"].items()})
        else:
            grams = {"CORA_FULL": pf["grammars"]["CORA_FULL"]}
            if X != A:
                grams["CORA_INDOMAIN"] = t["INDOMAIN"]["admitted"]
        for arm, g in grams.items():
            D, Q = RN.ImgSet(X, cal, "S", True), RN.ImgSet(X, ev, "S", False)
            r = RN.run_policy(list(g), D, Q)
            fr[arm] = _save_arm(X, arm, Q.L, r["query_log"], {"grammar": g, "ops": r["ops"],
                                                              "query_stats": r["query_stats"], "cpu_s": r["cpu_s"]})
        if scope == "secondary":
            pp = os.path.join(RN.DATA, "proposals", f"proposals_{X}.json")
            pz = os.path.join(W, "PROPOSALS_FROZEN.json")
            if os.path.exists(pp) and os.path.exists(pz) and json.load(open(pz)).get(f"proposals_{X}.json") == sha(pp):
                D, Q = RN.ImgSet(X, cal, "S", True), RN.ImgSet(X, ev, "S", False)
                r = RN.run_policy_proposals(json.load(open(pp)), D, Q)
                fr["NEURAL_PROPOSER"] = _save_arm(X, "NEURAL_PROPOSER", Q.L, r["query_log"],
                                                  {"ops": r["ops"], "query_stats": r["query_stats"],
                                                   "discarded_by_schema": r["discarded_by_schema"], "cpu_s": r["cpu_s"]})
            if X != A:                                   # descriptive: A's top programs without demonstrations
                prog = [{"op": o["op"], "theta_index": o["top"]["theta_index"], "guard": o["top"]["guard"]}
                        for o in pf["targets"][A]["CORA_final_fit"]["ops"] if o.get("top") and o["status"] == "EVIDENCE"]
                Q = RN.ImgSet(X, ev, "S", False)
                log = ST.apply_program(Q, prog)
                fr["PROGRAM_TRANSFER"] = _save_arm(X, "PROGRAM_TRANSFER", Q.L, log, {"program": prog})
        jdump(frozen, os.path.join(W, f"DECISIONS_PARTIAL_{scope}.json"))
    frozen["frozen_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    jdump(frozen, UD.FROZEN if scope == "primary" else FROZEN2)
    print("decisions frozen", scope, {X: list(v) for X, v in frozen["arms"].items()})


# ------------------------------------------------------------------------------------------------ Amendment 8 ------
def _tolerant_fit(X, grammar):
    """CORA_TOLERANT's final fit on all calibration parents of X, with its unrounded CPU."""
    D = RN.ImgSet(X, uids(X, "calibration"), "S", True)
    t0 = time.process_time()
    r = RN.run_policy(list(grammar), D, None, rule="tolerant")
    return {"ops": r["ops"], "cpu_s": r["cpu_s"], "cpu_s_exact": time.process_time() - t0}


def _tolerant_entry(X, A, ind_t):
    """The tolerant in-domain admission (targets only, same failure records and checks) and the final fit."""
    t = {}
    if X != A:
        spec, fr, gains = IN.specify(X)
        adm, trail, cpu = IN.admit(X, spec, rule="tolerant")
        t["INDOMAIN_TOLERANT"] = {"specified": spec, "admitted": adm, "trail": trail, "admission_cpu_s": cpu,
                                  "failure_records": fr["per_class"], "probe_cpu_s": fr["probe_cpu_s"]}
    ff = _tolerant_fit(X, ind_t["CORA"]["admitted"])
    t["CORA_TOLERANT_final_fit"] = ff
    # Amendment 9: the tolerant record's "cora_induction_cpu_s_unrounded" is a recorded sum (its probe CPU carries the
    # same per-child and final roundings), so it gets the legacy slack too
    rs = ff["cpu_s_exact"] + ind_t["cora_induction_cpu_s_unrounded"]
    t["CORA_TOLERANT_calibration_cpu_s"] = round(rs, 1)
    t["CORA_TOLERANT_calibration_cpu_s_recorded_sum"] = rs
    t["CORA_TOLERANT_calibration_cpu_s_conservative_upper"] = rs + LEGACY_SLACK_S
    return t


def freeze_tolerant():
    """Amendment 8: the CORA_TOLERANT policy on A and both transfer targets, from A's tolerant induction. The shared
    comparators (ALL_ON, MATCHED_SEARCH) and the protocol's freeze are not changed."""
    pf = json.load(open(os.path.join(W, "POLICY_FREEZE.json")))
    ro = pf["roles"]
    A = ro["A"]
    indp = os.path.join(W, A, "INDUCTION_TOLERANT.json")
    ind_t = json.load(open(indp))
    pft = {"roles": ro, "note": TOLERANT_NOTE, "induction_tolerant_sha256": sha(indp),
           "policy_freeze_sha256": sha(os.path.join(W, "POLICY_FREEZE.json")),
           "grammars": {"CORA_TOLERANT": ind_t["CORA"]["admitted"],
                        "FAILURE_BLIND_TOLERANT": {r: v["admitted"] for r, v in ind_t["FAILURE_BLIND"].items()},
                        "SHUFFLED_TOLERANT": {r: v["admitted"] for r, v in ind_t["SHUFFLED"].items()}},
           "targets": {}}
    for X in [A] + ro["targets"]:
        pft["targets"][X] = _tolerant_entry(X, A, ind_t)
        jdump(pft, PF_TOL)
    pft["frozen_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    jdump(pft, PF_TOL)
    jdump(pft, os.path.join(E, "POLICY_FREEZE_TOLERANT.json"))
    print(json.dumps({"grammar": pft["grammars"]["CORA_TOLERANT"],
                      "indomain": {X: v.get("INDOMAIN_TOLERANT", {}).get("admitted") for X, v in pft["targets"].items()},
                      "cpu": {X: v["CORA_TOLERANT_calibration_cpu_s"] for X, v in pft["targets"].items()}}))


def _tolerant_grams(pft, tX):
    g = {"CORA_TOLERANT": pft["grammars"]["CORA_TOLERANT"]}
    if tX is not None and "INDOMAIN_TOLERANT" in tX:
        g["CORA_TOLERANT_INDOMAIN"] = tX["INDOMAIN_TOLERANT"]["admitted"]
    g.update({f"FAILURE_BLIND_TOLERANT_{r}": v for r, v in pft["grammars"]["FAILURE_BLIND_TOLERANT"].items()})
    g.update({f"SHUFFLED_TOLERANT_{r}": v for r, v in pft["grammars"]["SHUFFLED_TOLERANT"].items()})
    return g


def _decide_grams(X, grams, cal, ev, rule, fr):
    for arm, g in grams.items():
        D, Q = RN.ImgSet(X, cal, "S", True), RN.ImgSet(X, ev, "S", False)
        r = RN.run_policy(list(g), D, Q, rule=rule)
        fr[arm] = _save_arm(X, arm, Q.L, r["query_log"], {"grammar": g, "ops": r["ops"], "rule": rule,
                                                          "query_stats": r["query_stats"], "cpu_s": r["cpu_s"]})


def decide_tolerant():
    """Amendment 8: CORA_TOLERANT, CORA_TOLERANT_INDOMAIN and the tolerant controls on A and both targets, decided by
    the frozen tolerant policy with no access to evaluation references, into DECISIONS_FROZEN_TOLERANT.json."""
    pft = json.load(open(PF_TOL))
    ro = pft["roles"]
    frozen = {"scope": "tolerant", "policy_freeze_tolerant": sha(PF_TOL), "arms": {}}
    for X in [ro["A"]] + ro["targets"]:
        fr = frozen["arms"].setdefault(X, {})
        _decide_grams(X, _tolerant_grams(pft, pft["targets"][X]), uids(X, "calibration"), uids(X, "evaluation"),
                      "tolerant", fr)
        jdump(frozen, os.path.join(W, "DECISIONS_PARTIAL_tolerant.json"))
    frozen["frozen_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    jdump(frozen, FROZEN_TOL)
    print("decisions frozen tolerant", {X: list(v) for X, v in frozen["arms"].items()})


# ---------------------------------------------------------------- Amendment 8: private targets (outside git) -------
def _pdir(X, *a):
    """Private target folders: mode 0700, inside the data folder, never under git."""
    d = os.path.join(W, X, *a)
    os.makedirs(d, mode=0o700, exist_ok=True)
    os.chmod(d, 0o700)
    return d


def freeze_private(X):
    """Amendment 8: a private target gets every entry of a transfer target (in-domain admission, CORA's final fit,
    ALL_ON, MATCHED_SEARCH on CORA's CPU) and the tolerant entries, from the frozen policies of A. Written to its
    private folder; the protocol's and the tolerant freeze files are not changed."""
    pf = json.load(open(os.path.join(W, "POLICY_FREEZE.json")))
    A = pf["roles"]["A"]
    ind = json.load(open(os.path.join(W, A, "INDUCTION.json")))
    ind_t = json.load(open(os.path.join(W, A, "INDUCTION_TOLERANT.json")))
    t = _freeze_one(X, A, ind, pf)
    t.update(_tolerant_entry(X, A, ind_t))
    out = {"note": PRIVATE_NOTE, "target": X, "policy_freeze_sha256": sha(os.path.join(W, "POLICY_FREEZE.json")),
           "policy_freeze_tolerant_sha256": sha(PF_TOL) if os.path.exists(PF_TOL) else None,
           "frozen_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "targets": {X: t}}
    jdump(out, os.path.join(_pdir(X), "POLICY_FREEZE_PRIVATE.json"))
    print(json.dumps({"indomain": t["INDOMAIN"]["admitted"], "indomain_tolerant": t["INDOMAIN_TOLERANT"]["admitted"],
                      "all_on_cal_f1": t["ALL_ON"]["cal_f1"], "matched_cal_f1": t["MATCHED_SEARCH"]["cal_f1"]}))


def decide_private(X):
    """Amendment 8: every primary, secondary and tolerant arm on the private target's evaluation and sensitivity
    images, with no access to their references, into its private DECISIONS_FROZEN_PRIVATE.json."""
    pf = json.load(open(os.path.join(W, "POLICY_FREEZE.json")))
    pft = json.load(open(PF_TOL))
    pp = json.load(open(os.path.join(_pdir(X), "POLICY_FREEZE_PRIVATE.json")))
    t = pp["targets"][X]
    A = pf["roles"]["A"]
    _pdir("decisions", X)
    os.chmod(os.path.join(W, "decisions", X), 0o700)
    cal = uids(X, "calibration")
    ev = sorted(uids(X, "evaluation") + uids(X, "sensitivity"))
    frozen = {"scope": "private", "note": PRIVATE_NOTE, "policy_freeze_private": sha(os.path.join(W, X,
              "POLICY_FREEZE_PRIVATE.json")), "arms": {X: {}}}
    fr = frozen["arms"][X]
    for arm, stage in (("NATIVE", "native"), ("TUNED", "tuned"), ("STRONG_NATIVE", "S")):
        fr[arm] = _save_arm(X, arm, {u: RN.lab(X, stage, u) for u in ev}, [])
    Q = RN.ImgSet(X, ev, "S", False)
    fr["ALL_ON"] = _save_arm(X, "ALL_ON", Q.L, ST.apply_all_on(Q, t["ALL_ON"]["values"]))
    Q = RN.ImgSet(X, ev, "S", False)
    fr["MATCHED_SEARCH"] = _save_arm(X, "MATCHED_SEARCH", Q.L, ST.apply_program(Q, t["MATCHED_SEARCH"]["program"]))
    grams = {"CORA": pf["grammars"]["CORA"], "CORA_FULL": pf["grammars"]["CORA_FULL"],
             "CORA_INDOMAIN": t["INDOMAIN"]["admitted"]}
    grams.update({f"FAILURE_BLIND_{r}": g for r, g in pf["grammars"]["FAILURE_BLIND"].items()})
    grams.update({f"SHUFFLED_{r}": g for r, g in pf["grammars"]["SHUFFLED"].items()})
    _decide_grams(X, grams, cal, ev, "strict", fr)
    _decide_grams(X, _tolerant_grams(pft, t), cal, ev, "tolerant", fr)
    prog = [{"op": o["op"], "theta_index": o["top"]["theta_index"], "guard": o["top"]["guard"]}
            for o in pf["targets"][A]["CORA_final_fit"]["ops"] if o.get("top") and o["status"] == "EVIDENCE"]
    Q = RN.ImgSet(X, ev, "S", False)
    fr["PROGRAM_TRANSFER"] = _save_arm(X, "PROGRAM_TRANSFER", Q.L, ST.apply_program(Q, prog), {"program": prog})
    frozen["frozen_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    jdump(frozen, os.path.join(_pdir(X), "DECISIONS_FROZEN_PRIVATE.json"))
    print("decisions frozen private", len(fr), "arms")


def evaluate_private(X):
    """Amendment 8: the private target's labels for CORA and CORA_TOLERANT, on its primary evaluation leaves and, as
    the sensitivity analysis, with the twin leaves added; aggregate results in its private folder only."""
    pf = json.load(open(os.path.join(W, "POLICY_FREEZE.json")))
    pp = json.load(open(os.path.join(W, X, "POLICY_FREEZE_PRIVATE.json")))
    t = pp["targets"][X]
    A = pf["roles"]["A"]
    res = _pdir(X, "results_private")
    base = {"frozen": [os.path.join(W, X, "DECISIONS_FROZEN_PRIVATE.json")], "datasets": [X], "pf": pf,
            "roles": {"A": A, "targets": [], "private_target": X}, "transfer": False, "res": res}
    tol_t = {"MATCHED_SEARCH": t["MATCHED_SEARCH"], "CORA_calibration_cpu_s": t["CORA_TOLERANT_calibration_cpu_s"],
             "CORA_calibration_cpu_s_recorded_sum": t["CORA_TOLERANT_calibration_cpu_s_recorded_sum"],
             "CORA_calibration_cpu_s_conservative_upper": t["CORA_TOLERANT_calibration_cpu_s_conservative_upper"]}
    ind_t = json.load(open(os.path.join(W, A, "INDUCTION_TOLERANT.json")))
    out = {}
    for tag, sides in (("primary", ("evaluation",)), ("sensitivity", ("evaluation", "sensitivity"))):
        out[f"CORA_{tag}"] = _evaluate({**base, "scope": f"private_{tag}", "main": "CORA", "fams": FAMS,
                                        "induction": os.path.join(W, A, "INDUCTION.json"),
                                        "grammar": pf["grammars"]["CORA"], "target": lambda _X: t, "sides": sides,
                                        "note": PRIVATE_NOTE, "out": (f"RESULTS_PRIVATE_{tag}.json",
                                                                      f"SUMMARY_PRIVATE_{tag}.md")})
        out[f"CORA_TOLERANT_{tag}"] = _evaluate({**base, "scope": f"private_tolerant_{tag}", "main": "CORA_TOLERANT",
                                                 "fams": FAMS_TOL, "extra_others": ("CORA", "CORA_TOLERANT_INDOMAIN"),
                                                 "induction": os.path.join(W, A, "INDUCTION_TOLERANT.json"),
                                                 "grammar": ind_t["CORA"]["admitted"], "target": lambda _X: tol_t,
                                                 "sides": sides, "note": PRIVATE_NOTE + "; " + TOLERANT_NOTE,
                                                 "out": (f"RESULTS_PRIVATE_TOLERANT_{tag}.json",
                                                         f"SUMMARY_PRIVATE_TOLERANT_{tag}.md")})
    for f in os.listdir(res):
        os.chmod(os.path.join(res, f), 0o600)
    print(json.dumps({k: v["datasets"][X]["label"] for k, v in out.items()}))


# ------------------------------------------------------------------------------------------------ evaluator --------
def boot(dv, B_=10000):
    dv = np.asarray(dv, float)
    m = dv[np.random.default_rng(0).integers(0, len(dv), (B_, len(dv)))].mean(axis=1)
    return {"mean": float(dv.mean()), "ci95": [float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))],
            "p_one_sided_bootstrap": float((1 + (m <= 0).sum()) / (B_ + 1)),
            "parents_better_worse_equal": [int((dv > 1e-12).sum()), int((dv < -1e-12).sum()),
                                           int((np.abs(dv) <= 1e-12).sum())]}


def holm(ps):
    """Holm step-down adjusted p-values (Amendment 3: for separately asserted contrasts; the labels are conjunction
    tests and need no adjustment)."""
    keys = sorted(ps, key=lambda k: ps[k])
    out, run = {}, 0.0
    for i, k in enumerate(keys):
        run = max(run, min(1.0, (len(keys) - i) * ps[k]))
        out[k] = run
    return out


def boot_groups(dv, groups, B_=10000):
    """Cluster bootstrap over groups of parents (sensitivity: wells, animals)."""
    dv = np.asarray(dv, float)
    gs = sorted(set(groups))
    gi = {g: [i for i, x in enumerate(groups) if x == g] for g in gs}
    rng = np.random.default_rng(0)
    ms = []
    for _ in range(B_):
        pick = rng.integers(0, len(gs), len(gs))
        idx = [i for k in pick for i in gi[gs[k]]]
        ms.append(dv[idx].mean())
    return {"mean": float(dv.mean()), "ci95": [float(np.percentile(ms, 2.5)), float(np.percentile(ms, 97.5))],
            "groups": len(gs)}


def cboot_ratio(num, den, B_=10000):
    num, den = np.asarray(num, float), np.asarray(den, float)
    point = float(num.sum() / den.sum()) if den.sum() > 0 else None
    idx = np.random.default_rng(0).integers(0, len(num), (B_, len(num)))
    n_, d_ = num[idx].sum(axis=1), den[idx].sum(axis=1)
    ok = d_ > 0
    if point is None or not ok.any():
        return {"point": point, "ci95": None, "excluded_zero_denominator": int((~ok).sum())}
    r = n_[ok] / d_[ok]
    return {"point": point, "ci95": [float(np.percentile(r, 2.5)), float(np.percentile(r, 97.5))],
            "excluded_zero_denominator": int((~ok).sum())}


def _low(X, u):
    p = os.path.join(W, X, "seg", "low", f"{u}.npz")
    return np.load(p)["labels"].astype(np.int32) if os.path.exists(p) else None


def _replay(X, arm, ev, refs, ign):
    """Judge every logged edit alone against the reference, replaying the log from S; check the final states."""
    rec = json.load(open(os.path.join(DEC, X, f"{arm}.json")))
    final = np.load(os.path.join(DEC, X, f"{arm}.npz"))
    state = {u: RN.lab(X, "S", u) for u in ev}
    judged = {u: [0, 0, 0] for u in ev}                        # beneficial, harmful, neutral
    steps = []
    for e in rec["log"]:
        if e["uid"] not in state:                  # Amendment 8: decided on a side this scope does not score
            continue
        if not steps or steps[-1][0] != e["op"] or any(x["uid"] == e["uid"] and x["before_sha"] != e["before_sha"]
                                                        for x in steps[-1][1]):
            steps.append((e["op"], []))
        steps[-1][1].append(e)
    for op, entries in steps:
        per = {}
        for e in entries:
            per.setdefault(e["uid"], []).append(e)
        for u, es in per.items():
            assert C.sha(state[u]) == es[0]["before_sha"], (X, arm, u)
            low = _low(X, u)
            img = C.Image(state[u], RN.inten(X, u), low, refs[u], ign[u])
            th = es[0].get("theta_value")
            acc = []
            for e in es:
                key = tuple(e["key"]) if isinstance(e["key"], list) else e["key"]
                cs, objs, res, ws = C.result_of(img, op, key, e["theta"], th)
                if res is None:
                    continue
                dtp, dn = img.effect(objs, cs, res)
                k = 0 if (dtp > 0 or (dtp == 0 and dn < 0)) else (1 if (dtp < 0 or (dtp == 0 and dn > 0)) else 2)
                judged[u][k] += 1
                acc.append((key, e["theta"]))
            img2 = C.Image(state[u], RN.inten(X, u), low)
            state[u], _ = C.apply(img2, op, acc, th)
    for u in ev:
        assert np.array_equal(state[u], final[u]), (X, arm, u, "replay differs from the frozen labels")
    return judged, rec


def _cpu_bounds(x, exact=None, slack=RND):
    """Amendment 7: (low, high) bounds on a true CPU value. An unrounded value is exact; a rounded record x is widened
    by its rounding slack, so rounding near zero can only make a comparator unmatched, never matched."""
    if exact is not None:
        return float(exact), float(exact)
    return max(float(x) - slack, 0.0), float(x) + slack


def _ratio(a, b, zero_both=1.0):
    return a / b if b > 0 else (zero_both if a == 0 else float("inf"))


def work_match(ind):
    """Amendment 5: the failure-blind and shuffled controls are work-matched to CORA's admission only if every seed
    validated the same number of candidates and its measured admission CPU is within a factor of 2 of CORA's.
    Amendment 7: the factor of 2 must hold for every value consistent with the one-decimal CPU records (unrounded values
    are used when recorded)."""
    def cands(trail):
        w = [r for r in trail if "work" in r]
        return w[0]["work"]["candidate_validations"] if w else None
    c_cpu, c_n = ind["CORA"]["admission_cpu_s"], cands(ind["CORA"]["trail"])
    c_lo, c_hi = _cpu_bounds(c_cpu, ind["CORA"].get("admission_cpu_s_exact"))
    rows = {}
    for k in ("FAILURE_BLIND", "SHUFFLED"):
        for s, v in ind[k].items():
            cpu, n = v["admission_cpu_s"], cands(v["trail"])
            lo, hi = _cpu_bounds(cpu, v.get("admission_cpu_s_exact"))
            ratio = _ratio(cpu, c_cpu)
            r_lo, r_hi = _ratio(lo, c_hi), _ratio(hi, c_lo)
            rows[f"{k}_{s}"] = {"cpu_s": cpu, "candidates": n, "cpu_ratio_to_cora": ratio,
                                "cpu_ratio_bounds": [r_lo, r_hi],
                                "matched": bool(n == c_n and 0.5 <= r_lo and r_hi <= 2.0)}
    return {"cora_admission_cpu_s": c_cpu, "cora_candidates": c_n, "controls": rows,
            "all_matched": all(r["matched"] for r in rows.values()) if rows else False}


def cora_cpu_upper(tgt):
    """Amendment 9: the conservative upper bound of CORA's calibration CPU on a target. In order: the recorded
    conservative upper; a recorded sum (named "_unrounded" by Amendments 7 and 8, whose components are rounded) plus
    the legacy slack; the one-decimal total plus the legacy slack and its own rounding."""
    if tgt.get("CORA_calibration_cpu_s_conservative_upper") is not None:
        return float(tgt["CORA_calibration_cpu_s_conservative_upper"]), "conservative_upper"
    for k in ("CORA_calibration_cpu_s_recorded_sum", "CORA_calibration_cpu_s_unrounded"):
        if tgt.get(k) is not None:
            return float(tgt[k]) + LEGACY_SLACK_S, k + " + legacy slack"
    return float(tgt["CORA_calibration_cpu_s"]) + LEGACY_SLACK_S + RND, "one-decimal total + legacy slack + 0.05"


def matched_search_work(ms, tgt):
    """Amendment 7: MATCHED_SEARCH is work-matched if its unrounded CPU is at least half of CORA's calibration CPU,
    taken at the upper end of its rounding bound, or if its full schedule completed with no in-step budget stop.
    Amendment 9: that upper end is `cora_cpu_upper` (legacy slack 0.30 s for every record without exact CPU)."""
    cpu_lo, _ = _cpu_bounds(ms["cpu_s"], ms.get("cpu_s_exact"))
    cora_hi, basis = cora_cpu_upper(tgt)
    by_cpu = bool(cpu_lo >= 0.5 * cora_hi)
    w = ms.get("work", {})
    sched = [list(s) for s in ms.get("schedule", ST.SCHEDULE)]
    full = bool(ms["stopped"] == "schedule exhausted" and w.get("stopped_inside_step", 0) == 0 and
                [list(s) for s in w.get("stages_completed", [])] == sched)
    return bool(by_cpu or full), {"cpu_s_low": cpu_lo, "cora_cpu_s_high": cora_hi, "cora_cpu_s_high_basis": basis,
                                  "by_cpu": by_cpu, "full_schedule_completed": full}


NEED = ("ABSTAIN_ALL", "ALL_ON", "MATCHED_SEARCH", "FAILURE_BLIND", "SHUFFLED")


def claim_label(n_ev_parents, n_cal_parents, accepted_edits, con, main="CORA", need=NEED):
    """The protocol's per-dataset label from the held contrasts (rule unchanged; a function since Amendment 7).
    Amendment 8: `main` and `need` name the arm and its comparators (CORA_TOLERANT and its tolerant controls)."""
    if n_ev_parents < MIN_EV or n_cal_parents < MIN_CAL:
        return "INSUFFICIENT_PARENTS"
    if accepted_edits == 0:
        return "NON_DEGRADATION_ONLY"
    if con[f"{main} - ABSTAIN_ALL"]["f1"]["ci95"][1] < 0:
        return "HARMFUL"
    if any(f"{main} - {c}" not in con for c in need):
        return "INCOMPLETE_CONTROLS"
    if all(con[f"{main} - {c}"]["f1"]["ci95"][0] > 0 for c in need):
        return "CROSS_DOMAIN_USEFUL"
    if con[f"{main} - ABSTAIN_ALL"]["f1"]["ci95"][0] > 0:
        return "GAIN_OVER_STRONG_NATIVE_ONLY"
    return "NO_MEASURED_GAIN"


def gated_label(label, controls_matched, ms_matched):
    """Amendments 5 and 7: CROSS_DOMAIN_USEFUL needs every comparator work-matched. Unmatched failure-blind or
    shuffled controls, or an underworked MATCHED_SEARCH, give INCOMPLETE_CONTROLS. Applied before the transfer block
    reads the per-target labels, so no unmatched target can enter the learned-transfer conjunction."""
    if label == "CROSS_DOMAIN_USEFUL" and not (controls_matched and ms_matched):
        return "INCOMPLETE_CONTROLS"
    return label


def evidence_gate(controls_matched, ms_matched, beats_blind_and_shuffled):
    """Amendment 7: the failure-evidence diagnostic is SUPPORTED only when every comparator's work is matched."""
    if not controls_matched:
        return "WITHHELD_UNMATCHED_WORK"
    if not ms_matched:
        return "WITHHELD_UNMATCHED_MATCHED_SEARCH"
    return "SUPPORTED" if beats_blind_and_shuffled else "NOT_SUPPORTED"


def alias_gate(ind):
    """Amendment 5: True only if every admitted operator's alias check actually ran (at least one accepted validation
    edit compared) and passed; False if nothing was admitted, since no comparison ran."""
    adm = ind["CORA"]["admitted"]
    if not adm:
        return False, "no operator admitted, so no alias comparison ran"
    recs = {r["op"]: r for r in ind["CORA"]["trail"] if "op" in r}
    ok = all(a in recs and recs[a]["edits_on_validation"] >= 1 and recs[a]["checks"]["not_alias"] for a in adm)
    return bool(ok), {a: (recs[a]["edits_on_validation"], recs[a]["alias_share"]) for a in adm if a in recs}


def transfer_block(per_parent_f1, labels, targets, main="CORA", need=NEED):
    """Amendment 5: the learned-transfer conjunction only with exactly two eligible targets; one target gives the
    descriptive TRANSFER_SINGLE_TARGET, none gives INSUFFICIENT_TARGETS. Amendment 8: `main` and `need` as in
    claim_label."""
    out = {}
    if len(targets) == 0:
        out["status"] = "INSUFFICIENT_TARGETS"
        return out
    rng = np.random.default_rng(0)
    for c in need:
        d = {X: per_parent_f1[X][main] - per_parent_f1[X][c] for X in targets if c in per_parent_f1[X]}
        if not d:
            continue
        ms = [np.mean([v[rng.integers(0, len(v), len(v))].mean() for v in d.values()]) for _ in range(10000)]
        key = f"{main} - {c} (" + ("mean of the two targets, stratified" if len(targets) == 2 else
                                   f"single target {targets[0]}") + ")"
        out[key] = {"mean": float(np.mean([v.mean() for v in d.values()])),
                    "ci95": [float(np.percentile(ms, 2.5)), float(np.percentile(ms, 97.5))]}
    if len(targets) == 2:
        out["status"] = "TWO_TARGETS"
        out["LEARNED_TRANSFER"] = all(labels[X] == "CROSS_DOMAIN_USEFUL" for X in targets)
    else:
        out["status"] = "TRANSFER_SINGLE_TARGET"
        out["single_target_label_descriptive"] = labels[targets[0]]
    return out


FROZEN_TOL = os.path.join(W, "DECISIONS_FROZEN_TOLERANT.json")
PF_TOL = os.path.join(W, "POLICY_FREEZE_TOLERANT.json")
TOLERANT_NOTE = ("calibration-informed secondary arm, added after the empty LIVECell grammar was observed, before any "
                 "evaluation outcome; it never replaces the primary CORA label")
PRIVATE_NOTE = "private data; not publicly reproducible"
FAMS = ("FAILURE_BLIND", "SHUFFLED")
FAMS_TOL = ("FAILURE_BLIND_TOLERANT", "SHUFFLED_TOLERANT")
OTHERS = ("ABSTAIN_ALL", "NATIVE", "TUNED", "ALL_ON", "MATCHED_SEARCH", "FAILURE_BLIND", "SHUFFLED", "CORA_FULL",
          "CORA_INDOMAIN", "PROGRAM_TRANSFER", "NEURAL_PROPOSER")


def _tolerant_target(X, pft, ms):
    """CORA_TOLERANT's calibration CPU on X (A's tolerant induction plus its final fit on X) and the shared
    MATCHED_SEARCH record, in the fields matched_search_work reads."""
    t = pft["targets"][X]
    return {"MATCHED_SEARCH": ms, "CORA_calibration_cpu_s": t["CORA_TOLERANT_calibration_cpu_s"],
            "CORA_calibration_cpu_s_recorded_sum": t["CORA_TOLERANT_calibration_cpu_s_recorded_sum"],
            "CORA_calibration_cpu_s_conservative_upper": t["CORA_TOLERANT_calibration_cpu_s_conservative_upper"]}


def evaluate(scope="primary"):
    """Amendment 6: the primary scope scores DECISIONS_FROZEN.json and writes RESULTS.json and SUMMARY.md; the
    secondary scope scores the union with DECISIONS_FROZEN_SECONDARY.json and writes RESULTS_SECONDARY.json and
    SUMMARY_SECONDARY.md (the primary files are not rewritten). Amendment 8: the tolerant scope scores CORA_TOLERANT
    against the shared comparators and its own tolerant controls (RESULTS_TOLERANT.json)."""
    pfp = os.path.join(W, "POLICY_FREEZE.json")
    pf = json.load(open(pfp))
    cfg = {"scope": scope, "frozen": [UD.FROZEN], "main": "CORA", "fams": FAMS, "pf": pf, "roles": pf["roles"],
           "induction": os.path.join(W, pf["roles"]["A"], "INDUCTION.json"),
           "grammar": pf["grammars"]["CORA"], "target": lambda X: pf["targets"][X],
           "sides": ("evaluation",), "res": RES, "transfer": True,
           "out": ("RESULTS.json", "SUMMARY.md") if scope == "primary" else
                  ("RESULTS_SECONDARY.json", "SUMMARY_SECONDARY.md")}
    if scope == "secondary":
        cfg["frozen"] = [UD.FROZEN, FROZEN2]
    if scope == "tolerant":
        pft = json.load(open(PF_TOL))
        ind = json.load(open(os.path.join(W, pf["roles"]["A"], "INDUCTION_TOLERANT.json")))
        cfg.update(frozen=[UD.FROZEN, FROZEN_TOL], main="CORA_TOLERANT", fams=FAMS_TOL, note=TOLERANT_NOTE,
                   extra_others=("CORA", "CORA_TOLERANT_INDOMAIN"),
                   induction=os.path.join(W, pf["roles"]["A"], "INDUCTION_TOLERANT.json"),
                   grammar=ind["CORA"]["admitted"],
                   target=lambda X: _tolerant_target(X, pft, pf["targets"][X]["MATCHED_SEARCH"]),
                   out=("RESULTS_TOLERANT.json", "SUMMARY_TOLERANT.md"))
    return _evaluate(cfg)


def _evaluate(cfg):
    frozen = {"arms": {}}
    for f in cfg["frozen"]:
        for X, arms in json.load(open(f))["arms"].items():
            frozen["arms"].setdefault(X, {}).update(arms)
    if cfg.get("datasets") is not None:
        frozen["arms"] = {X: v for X, v in frozen["arms"].items() if X in cfg["datasets"]}
    for X, arms in frozen["arms"].items():
        for arm, h in arms.items():
            assert sha(os.path.join(DEC, X, f"{arm}.npz")) == h["labels"], (X, arm)
            assert sha(os.path.join(DEC, X, f"{arm}.json")) == h["log"], (X, arm)
    M, fams = cfg["main"], cfg["fams"]
    need = ("ABSTAIN_ALL", "ALL_ON", "MATCHED_SEARCH") + tuple(fams)
    others = tuple(dict.fromkeys([c if c not in FAMS else fams[FAMS.index(c)] for c in OTHERS if c != M] +
                                 list(cfg.get("extra_others", ()))))
    out = {"roles": cfg["roles"], "datasets": {}, "transfer": {}}
    per_parent_f1 = {}
    for X, arms in frozen["arms"].items():
        rd = UD.Reader(X)
        rd.open_evaluator()
        ev = sorted(u for side in cfg["sides"] for u in uids(X, side))
        mf = RN.man(X)["images"]
        refs, ign = {}, {}
        for u in ev:
            shape = RN.lab(X, "S", u).shape
            r = rd.ref(u, shape)
            g = rd.ignore(u, shape)
            refs[u] = C.drop_ignored(r, g) if g is not None else r
            ign[u] = g
        parents = sorted({mf[u]["parent"] for u in ev})
        pidx = {p: i for i, p in enumerate(parents)}
        nS = np.zeros(len(parents))
        for u in ev:
            nS[pidx[mf[u]["parent"]]] += int(C.counted_mask(RN.lab(X, "S", u), ign[u])[1:].sum())
        res = {"n_parents": {"calibration": len(RN.man(X)["parents"]["calibration"]), "evaluation": len(parents)},
               "n_images": len(ev), "arms": {}}
        F1, AP = {}, {}
        for arm in arms:
            lab = np.load(os.path.join(DEC, X, f"{arm}.npz"))
            cnt = np.zeros((len(parents), 2 + len(C.THRESH)))
            for u in ev:
                pr = C.drop_ignored(lab[u], ign[u]) if ign[u] is not None else lab[u]
                c = C.counts(refs[u], pr)
                cnt[pidx[mf[u]["parent"]]] += [c["n_ref"], c["n_pred"]] + c["tp_at"]
            f1 = np.array([C.f1_of(r[0], r[1], r[2]) for r in cnt])
            ap = np.array([C.ap_of(r[0], r[1], r[2:]) for r in cnt])
            F1[arm], AP[arm] = f1, ap
            tot = cnt.sum(0)
            s = {"pooled_f1": C.f1_of(tot[0], tot[1], tot[2]), "pooled_ap": C.ap_of(tot[0], tot[1], tot[2:]),
                 "mean_parent_f1": float(f1.mean()), "mean_parent_ap": float(ap.mean())}
            if arm not in ("NATIVE", "TUNED", "STRONG_NATIVE"):
                judged, rec = _replay(X, arm, ev, refs, ign)
                jb = np.zeros((len(parents), 3))
                for u, v in judged.items():
                    jb[pidx[mf[u]["parent"]]] += v
                acc = jb.sum(1)
                s.update({"accepted_edits": int(acc.sum()), "beneficial": int(jb[:, 0].sum()),
                          "harmful": int(jb[:, 1].sum()), "neutral": int(jb[:, 2].sum()),
                          "edit_precision": cboot_ratio(jb[:, 0], acc), "harmful_rate": cboot_ratio(jb[:, 1], acc),
                          "coverage": cboot_ratio(acc, nS)})
                if "query_stats" in rec:
                    un, ab = np.zeros(len(parents)), np.zeros(len(parents))
                    for op, st in rec["query_stats"].items():
                        for u, (n_u, n_ab, n_acc) in st.items():
                            if u not in refs:
                                continue                    # decided on a side this scope does not score
                            un[pidx[mf[u]["parent"]]] += n_u
                            ab[pidx[mf[u]["parent"]]] += n_ab
                    s["abstention_share"] = cboot_ratio(ab, un)
                    s["ops"] = rec.get("ops")
                    s["cpu_s"] = rec.get("cpu_s")
            res["arms"][arm] = s
        for k in fams:
            ks = [a for a in F1 if a.startswith(k + "_") and a[len(k) + 1:].isdigit()]
            if ks:
                F1[k] = np.mean([F1[a] for a in ks], axis=0)
                AP[k] = np.mean([AP[a] for a in ks], axis=0)
        F1["ABSTAIN_ALL"], AP["ABSTAIN_ALL"] = F1["STRONG_NATIVE"], AP["STRONG_NATIVE"]
        con = {}
        for c in others:
            if c in F1:
                con[f"{M} - {c}"] = {"f1": boot(F1[M] - F1[c]), "ap": boot(AP[M] - AP[c])}
        for a in F1:
            if a not in (M, "ABSTAIN_ALL", "STRONG_NATIVE"):
                con[f"{a} - ABSTAIN_ALL"] = {"f1": boot(F1[a] - F1["ABSTAIN_ALL"])}
        res["contrasts"] = con
        fam = [f"{M} - {c}" for c in need if f"{M} - {c}" in con]
        res["holm_adjusted_p_separate_contrasts"] = holm({k: con[k]["f1"]["p_one_sided_bootstrap"] for k in fam})
        # sensitivity: coarser clusters (Amendment 3: LIVECell cell lines over its well parents)
        if X == "livecell":
            grp = [p.split("|")[0] for p in parents]
            res["sensitivity_coarser_clusters"] = {f"{M} - {c}": boot_groups(F1[M] - F1[c], grp)
                                                   for c in need if c in F1}
        cora = res["arms"][M]
        label = claim_label(len(parents), res["n_parents"]["calibration"], cora["accepted_edits"], con, M, need)
        res["label"] = res["label_before_work_gates"] = label
        adm = cfg["grammar"]
        ind = json.load(open(cfg["induction"]))
        wm = work_match(ind)
        al_ok, al_info = alias_gate(ind)
        tgt = cfg["target"](X)
        ms = tgt["MATCHED_SEARCH"]
        cora_cpu = tgt["CORA_calibration_cpu_s"]
        ms_matched, ms_info = matched_search_work(ms, tgt)                    # Amendment 7
        ops_rec = {o["op"]: o for o in (cora.get("ops") or [])}
        beats = lambda c: con.get(f"{M} - {c}", {}).get("f1", {}).get("ci95", [0, 0])[0] > 0   # noqa: E731
        res["work_match"] = {"controls": wm, "matched_search": {"cpu_s": ms["cpu_s"], "cora_cpu_s": cora_cpu,
                                                               "stopped": ms["stopped"], "matched": ms_matched,
                                                               **ms_info}}
        res["growth_gates"] = {
            "a_access_and_matched_work": {"matched_search_matched": ms_matched, "controls_matched": wm["all_matched"]},
            "b_admitted": adm, "b_useful_construction": {op: ops_rec.get(op, {}).get("query_applied", 0) for op in adm},
            "c_alias_checked": al_ok, "c_alias_detail": al_info,
            "d_changes_held_outputs": cora["accepted_edits"] > 0,
            "e_beats_matched_static": bool(beats("MATCHED_SEARCH") and beats("ALL_ON")),
            "beats_blind_and_shuffled": bool(beats(fams[0]) and beats(fams[1]))}
        g = res["growth_gates"]
        res["growth_supported"] = bool(adm and g["c_alias_checked"] and g["d_changes_held_outputs"] and
                                       g["e_beats_matched_static"] and g["beats_blind_and_shuffled"] and
                                       ms_matched and wm["all_matched"])
        res["failure_evidence_gate"] = evidence_gate(wm["all_matched"], ms_matched, g["beats_blind_and_shuffled"])
        res["label"] = label = gated_label(label, wm["all_matched"], ms_matched)   # before the transfer block
        if cfg.get("note"):
            res["note"] = cfg["note"]
        out["datasets"][X] = res
        per_parent_f1[X] = F1
    tg = [X for X in cfg["roles"]["targets"] if X in out["datasets"]] if cfg["transfer"] else []
    if cfg["transfer"]:
        out["transfer"] = transfer_block(per_parent_f1, {X: out["datasets"][X]["label"] for X in tg}, tg, M, need)
    os.makedirs(cfg["res"], exist_ok=True)
    out["scope"] = cfg["scope"]
    if cfg.get("note"):
        out["note"] = cfg["note"]
    jdump(out, os.path.join(cfg["res"], cfg["out"][0]))
    summary(out, cfg["out"][1], cfg["res"])
    return out


def summary(out, name="SUMMARY.md", res=None):
    L = ["# U5 results (written by u5eval.py evaluate)", "",
         f"Roles: A = {out['roles']['A']}, targets = {out['roles']['targets']}; ineligible = "
         f"{list(out['roles'].get('ineligible', {}))}; unsuitable = {list(out['roles'].get('unsuitable', {}))}.", ""]
    for X, r in out["datasets"].items():
        L += [f"## {X}: label {r['label']}; growth supported: {r['growth_supported']}", "",
              f"Parents: {r['n_parents']}; evaluation images {r['n_images']}.", "",
              "| arm | pooled F1 | mean parent F1 | pooled AP | edits | beneficial | harmful | edit precision [95% CI] | "
              "coverage |", "|---|---|---|---|---|---|---|---|---|"]
        for a, s in r["arms"].items():
            ep = s.get("edit_precision") or {}
            cv = s.get("coverage") or {}
            ept = "" if not ep else (f"{ep['point']:.3f} {ep['ci95']}" if ep.get("point") is not None else "undefined")
            cvt = "" if not cv or cv.get("point") is None else f"{cv['point']:.4f}"
            L.append(f"| {a} | {s['pooled_f1']:.4f} | {s['mean_parent_f1']:.4f} | {s['pooled_ap']:.4f} | "
                     f"{s.get('accepted_edits', '')} | {s.get('beneficial', '')} | {s.get('harmful', '')} | {ept} | {cvt} |")
        L += ["", "| contrast (per parent) | F1 mean [95% CI] better/worse/equal |", "|---|---|"]
        for k, v in r["contrasts"].items():
            f = v["f1"]
            L.append(f"| {k} | {f['mean']:+.4f} [{f['ci95'][0]:+.4f}, {f['ci95'][1]:+.4f}] "
                     f"{f['parents_better_worse_equal']} |")
        L.append("")
    title = {"TWO_TARGETS": "Transfer to the two targets (conjunction; pooled contrasts descriptive)",
             "TRANSFER_SINGLE_TARGET": "Transfer to a single target (TRANSFER_SINGLE_TARGET, descriptive)",
             "INSUFFICIENT_TARGETS": "Transfer: INSUFFICIENT_TARGETS"}.get(out["transfer"].get("status"), "Transfer")
    L += [f"## {title}", ""] + [f"- {k}: {v}" for k, v in out["transfer"].items()]
    if out.get("note"):
        L += ["", f"Note: {out['note']}."]
    open(os.path.join(RES if res is None else res, name), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "strong_eval":
        strong_eval(sys.argv[2])
    elif cmd == "freeze_target":
        freeze_target(sys.argv[2])
    elif cmd in ("decide", "evaluate"):
        if cmd == "decide" and sys.argv[2:] == ["tolerant"]:
            decide_tolerant()
        else:
            {"decide": decide, "evaluate": evaluate}[cmd](sys.argv[2] if len(sys.argv) > 2 else "primary")
    elif cmd in ("freeze_private", "decide_private", "evaluate_private"):
        {"freeze_private": freeze_private, "decide_private": decide_private,
         "evaluate_private": evaluate_private}[cmd](sys.argv[2])
    else:
        {"roles": roles, "freeze": freeze, "freeze_tolerant": freeze_tolerant}[cmd]()
