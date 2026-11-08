"""Calibrated-acceptance study harness (PROTOCOL.md). <python environment>, python -I. Every U5 module is imported read-only from
U5's frozen scripts folder; U5's data folder is only read.
    caharness.py pool SCOPE ARM...     run arms, each in its own process (CONFIG workers at a time)
    caharness.py arm SCOPE ARM         one arm (used by pool)
    caharness.py matched SCOPE         MATCHED_SEARCH (fit on calibration with CALIBRATED's measured CPU; held: apply)
    caharness.py dev_score             development scoring on NuInsSeg validation organs (calibration organs only)
    caharness.py strong_native_held    STRONG_NATIVE on the held PUMA ROIs (after GO and segmentation)
    caharness.py freeze_decisions      check the held run's calibration records against the freeze; hash decisions
    caharness.py evaluate              open the held references; results/RESULTS.json and results/SUMMARY.md
SCOPE: final (all 12 calibration organs as demonstrations, no queries: the frozen policy and its CPU), dev
(induction organs as demonstrations, validation organs as queries), held (all 12 organs as demonstrations, the held
PUMA ROIs as queries; after GO only)."""
import hashlib
import json
import os
import subprocess
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
R = "/path/to/repository"
U5S = os.path.join(R, "experiments/universality_bio_grammar_20261103/scripts")
U1S = os.path.join(R, "experiments/universality_submitted_pkg_20261101/scripts")
for p in (U5S, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)
import u5core as C      # noqa: E402
import u5eval as E5     # noqa: E402  (boot, holm, cboot_ratio: unchanged)
import u5induce as IN   # noqa: E402
import u5policy as P    # noqa: E402
import u5run as RN      # noqa: E402
import u5static as ST   # noqa: E402
import cadata as CD     # noqa: E402
import calrule as CR    # noqa: E402

ROOT = CD.ROOT
CFG = json.load(open(os.path.join(ROOT, "CONFIG.json")))
K = int(CFG["operator_budget_K"])
DS = "nuinsseg"
CALW = os.path.join(CD.WORK, "cal")
DEC = os.path.join(CD.PW, "decisions")
RES = os.path.join(ROOT, "results")
U5_RULE = os.path.join(RN.W, DS, "seg", "STRONG_NATIVE_RULE.json")
U5_POLICY = os.path.join(RN.W, "POLICY_FREEZE.json")               # U5's frozen policies (sha256 a67326dc...)
U5_POLICY_SHA = "a67326dc798066e63093bb22930f7c3456ac0fa50cf7e763c0e8f19a485b45d3"
CORA_ARMS = ["STRICT", "TOLERANT", "CALIBRATED"] + [f"CAL_BLIND_{r}" for r in range(1, 6)] + \
    [f"CAL_SHUFFLED_{r}" for r in range(1, 6)]
PRIMARY_ARMS = ["STRONG_NATIVE", "CALIBRATED"] + [f"CAL_BLIND_{r}" for r in range(1, 6)]
FROZEN_CHECK = ("STRICT", "TOLERANT", "CALIBRATED")
sha = lambda p: CD.file_sha(p)                     # noqa: E731


def jdump(x, p):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    json.dump(x, open(tmp, "w"), indent=1, default=lambda o: o.tolist() if hasattr(o, "tolist") else
              (bool(o) if isinstance(o, np.bool_) else str(o)))
    os.replace(tmp, p)


def cal_uids(roles=("induction", "validation")):
    m = RN.man(DS)["images"]
    return sorted(u for u, v in m.items() if v["side"] == "calibration" and v["role"] in roles)


def seed_of(kind, r, scope):
    """Control seeds: development uses U5's fixed seeds; the held run uses seeds from the GO salt (PROTOCOL 5.3)."""
    if scope != "held":
        return {"blind": 7000, "shuffled": 8000, "pad": 9000}[kind] + r
    salt = CD.held()["salt"]
    return int(hashlib.sha256(f"{salt}:{kind}:{r}".encode()).hexdigest()[:8], 16)


def grammar(arm, scope):
    spec = IN.specify(DS)[0]
    if arm in ("STRICT", "TOLERANT", "CALIBRATED"):
        return spec[:K], {"source": "failure evidence (u5induce.specify on NuInsSeg)", "specified": spec}
    kind, r = arm.rsplit("_", 1)
    r = int(r)
    if kind == "CAL_BLIND":
        s = seed_of("blind", r, scope)
        rng = np.random.default_rng(s)
        return [C.OPS[i] for i in rng.choice(len(C.OPS), size=K, replace=False)], {"source": "uniform draw", "seed": s}
    if kind == "CAL_SHUFFLED":
        s = seed_of("shuffled", r, scope)
        rel = IN.derangement(s, list(C.CLASSES))
        sp = IN.specify(DS, rel)[0]
        if len(sp) >= K:
            g = sp[:K]
        else:
            rest = [o for o in C.OPS if o not in sp]
            ps = seed_of("pad", r, scope)
            g = sp + [rest[i] for i in np.random.default_rng(ps).permutation(len(rest))[:K - len(sp)]]
        return g, {"source": "deranged failure records", "seed": s, "relabel": rel, "specified": sp}
    raise KeyError(arm)


def rule_of(arm):
    return {"STRICT": "strict", "TOLERANT": "tolerant"}.get(arm, "calibrated")


# ------------------------------------------------------------------------------------------------ held images ------
class PumaSet(RN.ImgSet):
    """The held PUMA ROIs as a U5 image set for decisions (no references). Each ROI is its own parent."""

    def __init__(self, uids, stage="S", labels=None, share=None):
        self.ds, self.uids, self.with_ref = "puma", list(uids), False
        self.parent = {u: u for u in self.uids}
        self.parents = sorted(self.uids)
        self.pidx = {u: i for i, u in enumerate(self.parents)}
        self.L = {u: (labels[u] if labels else puma_lab(stage, u)) for u in self.uids}
        if share is not None:
            self._I, self._low, self._ref = share._I, share._low, share._ref
        else:
            self._I, self._low, self._ref = {}, {}, {}
        self._img = {}
        self._img_parent = share._img if share is not None else None

    def I(self, u):
        if u not in self._I:
            self._I[u] = np.load(os.path.join(CD.PW, "int", f"{u}.npy")).astype(np.float32)
        return self._I[u]

    def low(self, u):
        if u not in self._low:
            self._low[u] = puma_lab("low", u)
        return self._low[u]

    def ref(self, u):
        raise PermissionError("decisions never read references")


def puma_lab(stage, u):
    return np.load(os.path.join(CD.PW, "seg", stage, f"{u}.npz"))["labels"].astype(np.int32)


def held_uids():
    return sorted(CD.held()["held"])


# ------------------------------------------------------------------------------------------------ arms -------------
def run_arm(scope, arm):
    t_wall = time.time()
    g, info = grammar(arm, scope)
    rule = rule_of(arm)
    roles_d = ("induction",) if scope == "dev" else ("induction", "validation")
    demo_u = cal_uids(roles_d)
    if rule == "calibrated":
        D = CR.ImageParents(DS, demo_u, "S", True)
    else:
        D = RN.ImgSet(DS, demo_u, "S", True)
    Q = None
    if scope == "dev":
        Q = RN.ImgSet(DS, cal_uids(("validation",)), "S", False)
    elif scope == "held":
        Q = PumaSet(held_uids())
    w0 = RN.work_snapshot()
    if rule == "calibrated":
        r = CR.run_calibrated(list(g), D, Q, K=K)
    else:
        r = RN.run_policy(list(g), D, Q, rule=rule)
    rec = {"arm": arm, "scope": scope, "rule": rule, "grammar": g, "grammar_info": info, "ops": r["ops"],
           "cpu_s": r["cpu_s"], "cpu_s_exact": r.get("cpu_s_exact", r["cpu_s"]), "wall_s": round(time.time() - t_wall, 1),
           "work": {k: v - w0.get(k, 0) for k, v in RN.work_snapshot().items()},
           "demo_images": len(demo_u), "demo_edits": len(r["demo_log"]),
           "query_log": r["query_log"], "query_stats": r["query_stats"], "demo_f1_after": RN.score_set(D)[1],
           "demo_f1_before": RN.score_set(RN.ImgSet(DS, demo_u, "S", True))[1]}
    if scope == "final":
        jdump(rec, os.path.join(CALW, "final", f"{arm}.json"))
    elif scope == "dev":
        np.savez_compressed(os.path.join(_mk(CALW, "dev"), f"{arm}.npz"), **{u: Q.L[u] for u in sorted(Q.L)})
        jdump(rec, os.path.join(CALW, "dev", f"{arm}.json"))
    else:
        _save_decision(arm, Q.L, rec)
    print(json.dumps({"arm": arm, "scope": scope, "grammar": g, "cpu_s": rec["cpu_s"],
                      "ops": [(o["op"], o["status"]) for o in r["ops"]], "query_edits": len(r["query_log"])}))
    return rec


def _mk(*a):
    p = os.path.join(*a)
    os.makedirs(p, exist_ok=True)
    return p


def _save_decision(arm, labels, rec):
    _mk(DEC)
    np.savez_compressed(os.path.join(DEC, f"{arm}.npz"), **{u: labels[u] for u in sorted(labels)})
    jdump({**rec, "log": rec.get("query_log", rec.get("log", []))}, os.path.join(DEC, f"{arm}.json"))


def matched(scope):
    """MATCHED_SEARCH (U5 u5static.fit_matched, unchanged): beam search over all 11 operators, no verification, with
    CALIBRATED's measured calibration CPU of the same scope as its budget. Held: the frozen final program is applied."""
    if scope == "held":
        fp = os.path.join(CALW, "final", "MATCHED_SEARCH.json")
        assert sha(fp) == json.load(open(os.path.join(ROOT, "FREEZE.json")))["calibration_records"]["MATCHED_SEARCH.json"]
        fin = json.load(open(fp))
        Q = PumaSet(held_uids())
        t0 = time.process_time()
        log = ST.apply_program(Q, fin["program"])
        _save_decision("MATCHED_SEARCH", Q.L, {"arm": "MATCHED_SEARCH", "program": fin["program"], "log": log,
                                                "apply_cpu_s": round(time.process_time() - t0, 1)})
        return
    cal = json.load(open(os.path.join(CALW, scope, "CALIBRATED.json")))
    budget = float(cal["cpu_s_exact"]) + float(CFG["probe_cpu_charged_s"])   # its run plus U5's failure probes
    demo_u = cal_uids(("induction",) if scope == "dev" else ("induction", "validation"))
    ms = ST.fit_matched(DS, demo_u, budget)
    rec = {"arm": "MATCHED_SEARCH", "scope": scope, **ms, "calibrated_cpu_budget_s": budget}
    if scope == "dev":
        Q = RN.ImgSet(DS, cal_uids(("validation",)), "S", False)
        rec["query_log"] = ST.apply_program(Q, ms["program"])
        np.savez_compressed(os.path.join(_mk(CALW, "dev"), "MATCHED_SEARCH.npz"), **{u: Q.L[u] for u in sorted(Q.L)})
    jdump(rec, os.path.join(CALW, scope, "MATCHED_SEARCH.json"))
    print(json.dumps({k: rec[k] for k in ("program", "cal_f1", "baseline_cal_f1", "cpu_s", "budget_s", "stopped")}))


def matched_u5():
    """MATCHED_SEARCH_U5 (descriptive): U5's frozen NuInsSeg MATCHED_SEARCH program, fitted by U5 on the same 12
    calibration organs with 858 CPU-s (not compute-matched here), applied unchanged to the held ROIs."""
    assert sha(U5_POLICY) == U5_POLICY_SHA
    prog = json.load(open(U5_POLICY))["targets"][DS]["MATCHED_SEARCH"]["program"]
    Q = PumaSet(held_uids())
    t0 = time.process_time()
    log = ST.apply_program(Q, prog)
    _save_decision("MATCHED_SEARCH_U5", Q.L, {"arm": "MATCHED_SEARCH_U5", "program": prog, "log": log,
                                               "source": "U5 POLICY_FREEZE.json targets.nuinsseg.MATCHED_SEARCH",
                                               "apply_cpu_s": round(time.process_time() - t0, 1)})


def pool(scope, arms):
    """Each arm in its own process (no shared unit cache, so each arm's CPU is its own), CONFIG workers at a time."""
    py = sys.executable
    env = dict(os.environ, OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1")
    todo, run, status = list(arms), [], {}
    while todo or run:
        while todo and len(run) < int(CFG["workers"]):
            a = todo.pop(0)
            lg = open(os.path.join(_mk(CALW, "logs"), f"{scope}_{a}.log"), "w")
            run.append((a, subprocess.Popen([py, "-I", "-B", os.path.abspath(__file__), "arm", scope, a], stdout=lg,
                                             stderr=subprocess.STDOUT, env=env), lg))
        time.sleep(5)
        for x in list(run):
            if x[1].poll() is not None:
                status[x[0]] = x[1].returncode
                x[2].close()
                run.remove(x)
    print(json.dumps({"scope": scope, "exit_codes": status}))
    if any(v != 0 for v in status.values()):
        sys.exit(1)


# ------------------------------------------------------------------------------------------------ scoring ----------
def _judge_replay(start, log, img_of, final):
    """U5's replay (u5eval._replay, re-expressed for any image source): every logged edit is judged alone against the
    reference on the state just before its operator; the replayed final states must equal the frozen labels."""
    state = {u: start[u].copy() for u in start}
    judged = {u: [0, 0, 0] for u in start}                    # beneficial, harmful, neutral
    steps = []
    for e in log:
        if e["uid"] not in state:
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
            assert C.sha(state[u]) == es[0]["before_sha"], (u, op)
            img = img_of(u, state[u], True)
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
            state[u], _ = C.apply(img_of(u, state[u], False), op, acc, th)
    for u in start:
        assert np.array_equal(state[u], final[u]), (u, "replay differs from the frozen labels")
    return judged


def score_arms(uids, labels, refs, ign, logs, start, img_of, groups=None):
    """Per-image counts, F1 and AP; judged edits; per-image contrasts. labels: arm -> {uid: L}."""
    out, F1, AP, JB = {}, {}, {}, {}
    for arm, L in labels.items():
        cnt = np.zeros((len(uids), 2 + len(C.THRESH)))
        for i, u in enumerate(uids):
            pr = C.drop_ignored(L[u], ign[u]) if ign[u] is not None else L[u]
            c = C.counts(refs[u], pr)
            cnt[i] = [c["n_ref"], c["n_pred"]] + c["tp_at"]
        F1[arm] = np.array([C.f1_of(r[0], r[1], r[2]) for r in cnt])
        AP[arm] = np.array([C.ap_of(r[0], r[1], r[2:]) for r in cnt])
        tot = cnt.sum(0)
        s = {"pooled_f1": C.f1_of(tot[0], tot[1], tot[2]), "pooled_ap": C.ap_of(tot[0], tot[1], tot[2:]),
             "mean_image_f1": float(F1[arm].mean()), "mean_image_ap": float(AP[arm].mean()), "images": len(uids)}
        if arm in logs:
            jd = _judge_replay(start, logs[arm], img_of, L)
            jb = np.array([jd[u] for u in uids], float)
            acc = jb.sum(1)
            JB[arm] = jb
            s.update({"accepted_edits": int(acc.sum()), "beneficial": int(jb[:, 0].sum()), "harmful": int(jb[:, 1].sum()),
                      "neutral": int(jb[:, 2].sum()), "edit_precision": E5.cboot_ratio(jb[:, 0], acc),
                      "harmful_rate": E5.cboot_ratio(jb[:, 1], acc),
                      "harm_share_of_decisive": E5.cboot_ratio(jb[:, 1], jb[:, 0] + jb[:, 1])})
        out[arm] = s
    return out, F1, AP, JB


def boot_strata(dv, groups, B_=10000):
    """Sensitivity: bootstrap of the mean per-image difference resampled within strata (primary, metastatic for
    PUMA; organs for the development queries), default_rng(0)."""
    dv = np.asarray(dv, float)
    gs = sorted(set(groups))
    idx = {g: np.array([i for i, x in enumerate(groups) if x == g]) for g in gs}
    rng = np.random.default_rng(0)
    ms = np.zeros(B_)
    for g in gs:
        ii = idx[g]
        ms += dv[ii[rng.integers(0, len(ii), (B_, len(ii)))]].sum(axis=1)
    ms /= len(dv)
    return {"mean": float(dv.mean()), "ci95": [float(np.percentile(ms, 2.5)), float(np.percentile(ms, 97.5))],
            "strata": {g: {"n": int(len(idx[g])), "mean": float(dv[idx[g]].mean())} for g in gs}}


def family_mean(F, prefix):
    ks = sorted(a for a in F if a.startswith(prefix + "_") and a[len(prefix) + 1:].isdigit())
    return (np.mean([F[a] for a in ks], axis=0), ks) if ks else (None, [])


def contrasts(F1, AP, main="CALIBRATED", groups=None):
    con = {}
    for fam in ("CAL_BLIND", "CAL_SHUFFLED"):
        m, ks = family_mean(F1, fam)
        if m is not None:
            F1[fam] = m
            AP[fam] = family_mean(AP, fam)[0]
    for c in ("STRONG_NATIVE", "CAL_BLIND", "CAL_SHUFFLED", "STRICT", "TOLERANT", "MATCHED_SEARCH", "MATCHED_SEARCH_U5",
              "NATIVE", "TUNED"):
        if c in F1 and main in F1:
            con[f"{main} - {c}"] = {"f1": E5.boot(F1[main] - F1[c]), "ap": E5.boot(AP[main] - AP[c])}
            if groups is not None:
                con[f"{main} - {c}"]["f1_stratified"] = boot_strata(F1[main] - F1[c], groups)
    for a in F1:
        if a not in (main, "STRONG_NATIVE", "NATIVE", "TUNED") and "STRONG_NATIVE" in F1:
            con[f"{a} - STRONG_NATIVE"] = {"f1": E5.boot(F1[a] - F1["STRONG_NATIVE"])}
    return con


def dev_score():
    """Development numbers (NuInsSeg validation organs; calibration data only). Labelled DEVELOPMENT everywhere."""
    val = cal_uids(("validation",))
    refs, ign = {}, {}
    for u in val:
        refs[u], ign[u] = RN.refign(DS, u)
    start = {u: RN.lab(DS, "S", u) for u in val}
    low = lambda u: (np.load(os.path.join(RN.W, DS, "seg", "low", f"{u}.npz"))["labels"].astype(np.int32)  # noqa: E731
                     if os.path.exists(os.path.join(RN.W, DS, "seg", "low", f"{u}.npz")) else None)

    def img_of(u, L, with_ref):
        return C.Image(L, RN.inten(DS, u), low(u), refs[u], ign[u]) if with_ref else C.Image(L, RN.inten(DS, u), low(u))

    labels, logs = {"STRONG_NATIVE": start}, {}
    arms = [a for a in CORA_ARMS + ["MATCHED_SEARCH"] if os.path.exists(os.path.join(CALW, "dev", f"{a}.npz"))]
    recs = {}
    for a in arms:
        labels[a] = np.load(os.path.join(CALW, "dev", f"{a}.npz"))          # read lazily, image by image
        recs[a] = json.load(open(os.path.join(CALW, "dev", f"{a}.json")))
        logs[a] = recs[a]["query_log"]
    mf = RN.man(DS)["images"]
    organs = [mf[u]["parent"] for u in val]
    s, F1, AP, JB = score_arms(val, labels, refs, ign, logs, start, img_of)
    con = contrasts(F1, AP, groups=organs)
    out = {"label": "DEVELOPMENT (NuInsSeg calibration organs only: demonstrations = 6 induction organs, queries = 6 "
                    "validation organs; no fresh image)", "images": len(val), "organs": sorted(set(organs)),
           "arms": s, "contrasts": con,
           "arm_records": {a: {"grammar": r.get("grammar"), "cpu_s": r.get("cpu_s"),
                               "ops": [{k: o.get(k) for k in ("op", "status", "mean_gain", "lcb_gain", "harmful_rate",
                                                               "ucb_harmful_rate", "final_program_text",
                                                               "query_accepted", "fit", "top")} for o in r.get("ops", [])]
                               if "ops" in r else None, "program": r.get("program")} for a, r in recs.items()}}
    jdump(out, os.path.join(ROOT, "development", "DEV_RESULTS.json"))
    print(json.dumps({a: {k: v.get(k) for k in ("pooled_f1", "mean_image_f1", "accepted_edits", "beneficial", "harmful")}
                      for a, v in s.items()}))
    print(json.dumps({k: v["f1"]["mean"] for k, v in con.items()}))


# ------------------------------------------------------------------------------------------------ held run ---------
def strong_native_held():
    """U5's STRONG_NATIVE rule chosen on NuInsSeg calibration (contact_ge 3), applied unchanged to the held ROIs with
    U5's feature code (u5run.strong_native's steps, writing into this study's folder)."""
    for p in (R, U1S):
        if p not in sys.path:
            sys.path.insert(0, p)
    import adapter as AD
    from cora_cross_domain_transfer.adapters import bbbc039 as B
    rule = tuple(json.load(open(U5_RULE))["rule"])
    _mk(CD.PW, "seg", "S")
    for u in held_uids():
        L = puma_lab("tuned", u)
        I = np.load(os.path.join(CD.PW, "int", f"{u}.npy")).astype(np.float32)
        F = B.Features(L, I)
        d = AD.rule_deletes(rule, {k: np.asarray(F.get(k), float) for k in AD.FEATS})
        x = L.copy()
        x[d[L]] = 0
        np.savez_compressed(os.path.join(CD.PW, "seg", "S", f"{u}.npz"), labels=C.relabel(x))
    print("STRONG_NATIVE held", rule, len(held_uids()))


def _strip(o):
    """Calibration-side fields that must equal the freeze (statuses, programs, bounds)."""
    keep = ("op", "status", "fit", "top", "demo_accepted", "demo_applied", "final_program_text", "lcb_gain",
            "ucb_harmful_rate", "mean_gain", "harmful_rate", "fold_programs")
    return {k: o.get(k) for k in keep}


def freeze_decisions():
    """After every held arm is decided: the calibration-side records of STRICT, TOLERANT and CALIBRATED must equal
    the frozen ones (FREEZE.json); then every decision file is hashed into DECISIONS_FROZEN.json, before any held
    reference is decoded."""
    fz = json.load(open(os.path.join(ROOT, "FREEZE.json")))
    mism = {}
    for a in FROZEN_CHECK:
        held = json.load(open(os.path.join(DEC, f"{a}.json")))
        fin = json.load(open(os.path.join(CALW, "final", f"{a}.json")))
        assert sha(os.path.join(CALW, "final", f"{a}.json")) == fz["calibration_records"][f"{a}.json"], a
        if [_strip(o) for o in held["ops"]] != [_strip(o) for o in fin["ops"]]:
            mism[a] = {"held": [_strip(o) for o in held["ops"]], "frozen": [_strip(o) for o in fin["ops"]]}
    if mism:
        jdump(mism, os.path.join(CD.PW, "FROZEN_MISMATCH.json"))
        raise SystemExit("calibration-side records differ from the freeze: stop before any reference is decoded")
    for arm, stage in (("NATIVE", "native"), ("TUNED", "tuned"), ("STRONG_NATIVE", "S")):
        L = {u: puma_lab(stage, u) for u in held_uids()}
        _save_decision(arm, L, {"arm": arm, "log": []})
    arms = sorted(f[:-5] for f in os.listdir(DEC) if f.endswith(".json"))
    fr = {"arms": {a: {"labels": sha(os.path.join(DEC, f"{a}.npz")), "log": sha(os.path.join(DEC, f"{a}.json"))}
                   for a in arms},
          "held_manifest": sha(CD.HELD_MANIFEST), "freeze": sha(os.path.join(ROOT, "FREEZE.json")),
          "frozen_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    jdump(fr, CD.DECISIONS_FROZEN)
    print("decisions frozen", arms)


def evaluate():
    fr = json.load(open(CD.DECISIONS_FROZEN))
    for a, hh in fr["arms"].items():
        assert sha(os.path.join(DEC, f"{a}.npz")) == hh["labels"], a
        assert sha(os.path.join(DEC, f"{a}.json")) == hh["log"], a
    rd = CD.Reader()
    rd.open_evaluator()
    uids = held_uids()
    m = CD.held()
    refs, ign, nref_poly = {}, {}, {}
    for u in uids:
        shape = puma_lab("S", u).shape
        refs[u], nref_poly[u] = rd.reference(u, shape)
        ign[u] = None
    start = {u: puma_lab("S", u) for u in uids}
    I_ = {}

    def img_of(u, L, with_ref):
        if u not in I_:
            I_[u] = np.load(os.path.join(CD.PW, "int", f"{u}.npy")).astype(np.float32)
        lo = puma_lab("low", u)
        return C.Image(L, I_[u], lo, refs[u], None) if with_ref else C.Image(L, I_[u], lo)

    labels, logs = {}, {}
    for a in fr["arms"]:
        labels[a] = np.load(os.path.join(DEC, f"{a}.npz"))                 # read lazily, image by image
        if a not in ("NATIVE", "TUNED", "STRONG_NATIVE"):
            logs[a] = json.load(open(os.path.join(DEC, f"{a}.json")))["log"]
    strata = [m["held"][u] for u in uids]
    s, F1, AP, JB = score_arms(uids, labels, refs, ign, logs, start, img_of)
    con = contrasts(F1, AP, groups=strata)
    p1 = con["CALIBRATED - STRONG_NATIVE"]["f1"]["p_one_sided_bootstrap"]
    p2 = con["CALIBRATED - CAL_BLIND"]["f1"]["p_one_sided_bootstrap"] if "CALIBRATED - CAL_BLIND" in con else 1.0
    holm = E5.holm({"P1": p1, "P2": p2})
    lev = float(CFG["primary_test_level_holm_one_sided"])
    cal = s["CALIBRATED"]
    hr = cal.get("harmful_rate", {}).get("point")
    alpha = float(CFG["alpha_harmful_rate"])
    edits = cal.get("accepted_edits", 0)
    c1 = con["CALIBRATED - STRONG_NATIVE"]["f1"]
    if edits == 0:
        label = "NON_DEGRADATION_ONLY"
    elif c1["ci95"][1] < 0:
        label = "HARMFUL"
    elif holm["P1"] <= lev and c1["ci95"][0] > 0 and hr is not None and hr <= alpha:
        label = "SUPPORTED"
    elif holm["P1"] <= lev and c1["ci95"][0] > 0:
        label = "GAIN_BUT_BOUND_EXCEEDED"
    elif hr is not None and hr <= alpha:
        label = "BOUND_HELD_NO_MEASURED_GAIN"
    else:
        label = "NO_MEASURED_GAIN"
    c2 = con.get("CALIBRATED - CAL_BLIND", {}).get("f1")
    out = {"dataset": "puma held ROIs", "n_images": len(uids), "strata": {k: strata.count(k) for k in CD.STRATA},
           "reference_objects": int(sum(int(refs[u].max()) for u in uids)), "arms": s, "contrasts": con,
           "primary": {"P1": "CALIBRATED - STRONG_NATIVE (mean per-image F1)", "P1_holm_p": holm["P1"],
                       "P1_ci95": c1["ci95"], "P1_mean": c1["mean"], "harmful_rate": hr, "alpha": alpha,
                       "harmful_rate_ci95": cal.get("harmful_rate", {}).get("ci95"), "label": label,
                       "P2": "CALIBRATED - CAL_BLIND (mean of 5 seeds)", "P2_holm_p": holm["P2"],
                       "P2_ci95": None if c2 is None else c2["ci95"], "P2_mean": None if c2 is None else c2["mean"],
                       "FAILURE_EVIDENCE_MATTERS": bool(c2 is not None and holm["P2"] <= lev and c2["ci95"][0] > 0),
                       "test_level_holm_one_sided": lev},
           "decisions_frozen": sha(CD.DECISIONS_FROZEN), "evaluated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    jdump(out, os.path.join(RES, "RESULTS.json"))
    _summary(out)
    print(json.dumps(out["primary"]))


def _summary(out):
    L = ["# Calibrated acceptance on fresh held PUMA ROIs: results", "",
         f"Written by `scripts/caharness.py evaluate` at {out['evaluated_utc']}. Held ROIs: {out['n_images']} "
         f"({out['strata']}); reference nuclei: {out['reference_objects']}.", "", "## Primary", ""]
    p = out["primary"]
    L += [f"- Label: **{p['label']}**.",
          f"- P1, CALIBRATED minus STRONG_NATIVE, mean per-image F1: {p['P1_mean']:+.4f} "
          f"[{p['P1_ci95'][0]:+.4f}, {p['P1_ci95'][1]:+.4f}] over {out['n_images']} images; Holm-adjusted one-sided "
          f"p {p['P1_holm_p']:.4f} (level {p['test_level_holm_one_sided']}).",
          f"- Harmful-edit rate of CALIBRATED: {p['harmful_rate']} (95% CI {p['harmful_rate_ci95']}); "
          f"calibrated bound {p['alpha']}.",
          f"- P2, CALIBRATED minus CAL_BLIND: {p['P2_mean']} (95% CI {p['P2_ci95']}); Holm-adjusted p {p['P2_holm_p']:.4f};"
          f" failure evidence matters: {p['FAILURE_EVIDENCE_MATTERS']}.", "", "## Arms", "",
          "| arm | pooled F1 | mean image F1 | accepted edits | beneficial | harmful | harmful rate |",
          "|---|---|---|---|---|---|---|"]
    for a, s in out["arms"].items():
        hr = s.get("harmful_rate", {}) or {}
        L.append(f"| {a} | {s['pooled_f1']:.4f} | {s['mean_image_f1']:.4f} | {s.get('accepted_edits', '')} | "
                 f"{s.get('beneficial', '')} | {s.get('harmful', '')} | {hr.get('point', '')} |")
    L += ["", "## Contrasts (per-image F1; 95% bootstrap over images, 10,000 resamples)", "",
          "| contrast | mean [95% CI] | images better/worse/equal |", "|---|---|---|"]
    for k, v in out["contrasts"].items():
        f = v["f1"]
        L.append(f"| {k} | {f['mean']:+.4f} [{f['ci95'][0]:+.4f}, {f['ci95'][1]:+.4f}] | "
                 f"{'/'.join(str(x) for x in f['parents_better_worse_equal'])} |")
    open(os.path.join(RES, "SUMMARY.md"), "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "pool":
        pool(sys.argv[2], sys.argv[3:])
    elif cmd == "arm":
        run_arm(sys.argv[2], sys.argv[3])
    elif cmd == "matched":
        matched(sys.argv[2])
    elif cmd == "matched_u5":
        matched_u5()
    else:
        {"dev_score": dev_score, "strong_native_held": strong_native_held, "freeze_decisions": freeze_decisions,
         "evaluate": evaluate}[cmd]()
