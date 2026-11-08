"""U5 calibration-only steps after segmentation (PROTOCOL.md sections 6, 8.3, 9; Amendment 2). <python environment>, -I.
    u5induce.py gate DS                 taxonomy of S on calibration images, oracle gains, the gate -> GATE_DS.json
    u5induce.py induce DS ROLESET       specification and admission for CORA, FAILURE_BLIND x5, SHUFFLED x5
                                        (ROLESET = induction:validation parents of DS) -> work/DS/INDUCTION.json"""
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import u5core as C      # noqa: E402
import u5probe as PB    # noqa: E402
import u5run as RN      # noqa: E402
import u5tax as TX      # noqa: E402

W = RN.W
E = "/path/to/repository/experiments/universality_bio_grammar_20261103"
POST = ("DELETE", "SPLIT", "MERGE", "FILL", "GROW", "SHRINK")
SPEC_MIN_GAIN = 0.005
OP_OF_CLASS = {c: [o for o in C.OPS if C.CLASS[o] == c] for c in C.CLASSES}


def gate(ds):
    """Section 6 on all calibration images; per-class oracle gains on induction parents for section 8.3."""
    m = RN.man(ds)
    cal = sorted(u for u, v in m["images"].items() if v["side"] == "calibration")
    t0 = time.process_time()
    rows = {"all": {"base": [], "post": []}, "induction": {}}
    counts = {c: 0 for c in C.CLASSES}
    n_obj = n_err = 0
    ind_pairs = {c: [] for c in C.CLASSES}
    ind_base = []
    for u in cal:
        S = RN.lab(ds, "S", u)
        ref, ign = RN.refign(ds, u)
        info = TX.classify(S, ref, ign)
        cnt = info["cnt"]
        n_obj += int(cnt[1:].sum())
        n_err += int((cnt & ~info["tp"])[1:].sum())
        for c in info["cls"].values():
            counts[c] += 1
        counts["ADD"] += len(info["missed"])
        rows["all"]["base"].append((ref, S, ign))
        rows["all"]["post"].append((ref, TX.corrected(S, ref, info, set(POST)), ign))
        if m["images"][u]["role"] == "induction":
            ind_base.append((ref, S, ign))
            for c in C.CLASSES:
                ind_pairs[c].append((ref, TX.corrected(S, ref, info, {c}), ign))
    f_base = TX.pooled_f1(rows["all"]["base"])
    f_post = TX.pooled_f1(rows["all"]["post"])
    fi = TX.pooled_f1(ind_base)
    g = {"dataset": ds, "calibration_images": len(cal), "objects": n_obj, "error_share": n_err / max(n_obj, 1),
         "class_counts": counts, "baseline_pooled_f1": f_base, "oracle_pooled_f1": f_post, "oracle_gain": f_post - f_base,
         "induction_baseline_pooled_f1": fi,
         "induction_class_oracle_gain": {c: TX.pooled_f1(ind_pairs[c]) - fi for c in C.CLASSES},
         "criteria": {"error_share_min": 0.05, "oracle_gain_min": 0.01}, "cpu_s": round(time.process_time() - t0, 1)}
    g["PASS"] = bool(g["error_share"] >= 0.05 and g["oracle_gain"] >= 0.01)
    for p in (os.path.join(W, ds, "GATE.json"), os.path.join(E, f"GATE_{ds}.json")):
        json.dump(g, open(p, "w"), indent=1)
    print(json.dumps({k: g[k] for k in ("dataset", "error_share", "baseline_pooled_f1", "oracle_gain", "PASS")}))
    return g


# ------------------------------------------------------------------------------------------------ specification ----
def specify(ds, relabel=None):
    """Section 8.3. relabel: class -> class (SHUFFLED); applied to the failure records and to the oracle gains."""
    fr = PB.summarize(ds, "induction", relabel)
    g = json.load(open(os.path.join(W, ds, "GATE.json")))
    gains = dict(g["induction_class_oracle_gain"])
    if relabel is not None:
        gains = {relabel[c]: v for c, v in g["induction_class_oracle_gain"].items()}
    spec = []
    for c in sorted(C.CLASSES, key=lambda c: (-gains.get(c, 0.0), C.CLASSES.index(c))):
        s = fr["per_class"].get(c)
        if s and s["not_found_within_budget"] and gains.get(c, 0.0) >= SPEC_MIN_GAIN:
            spec += OP_OF_CLASS[c]
    return spec, fr, gains


# ------------------------------------------------------------------------------------------------ admission --------
def _sets(ds, roles, with_ref=True):
    m = RN.man(ds)
    return RN.ImgSet(ds, sorted(u for u, v in m["images"].items() if v["role"] in roles), "S", with_ref)


def _same_res(r1, r2):
    return r1 is not None and r2 is not None and C._same(r1, r2)


def _low_labels(ds, uid):
    """The low-threshold segmentation the policy used (u5run.ImgSet.low), or None if the dataset has none."""
    p = os.path.join(W, ds, "seg", "low", f"{uid}.npz")
    return np.load(p)["labels"].astype(np.int32) if os.path.exists(p) else None


def alias_share(ds, op, qlog, admitted, before):
    """Share of op's accepted validation edits reproduced by deletion, or by one or two edits of admitted operators
    (object operators, any theta) on the same object. `before[uid]` is the label image just before op (the final state
    of the run without op, which is identical up to op). Pair and candidate operators can only be reproduced by
    themselves, which are not yet admitted."""
    edits = [e for e in qlog if e["op"] == op]
    if not edits:
        return 0.0, 0
    hit = 0
    obj_ops = [a for a in admitted if a not in ("merge_pairs", "add_lowthresh")]
    for e in edits:
        L = before[e["uid"]]
        assert C.sha(L) == e["before_sha"]
        I = RN.inten(ds, e["uid"])
        img = C.Image(L, I, _low_labels(ds, e["uid"]))      # Amendment 8: add_lowthresh edits need the low labels
        key = tuple(e["key"]) if isinstance(e["key"], list) else e["key"]
        cs, objs, res, _ = C.result_of(img, op, key, e["theta"])
        if res is None:
            continue
        if len(res) == 0:
            hit += 1                                            # a deletion
            continue
        if op in ("merge_pairs", "add_lowthresh") or not obj_ops:
            continue
        hit += int(_reproduced(img, I, key, cs, res, obj_ops))
    return hit / len(edits), len(edits)


def _reproduced(img, I, key, cs, res, obj_ops):
    union = np.any(np.stack(res), axis=0)
    for a in obj_ops:
        for t1 in range(len(C.THETA[a])):
            cs1, _, r1, _ = C.result_of(img, a, key, t1)
            if r1 is None:
                continue
            if cs1 == cs and _same_res(r1, res):
                return True
            L1, ap = C.apply(img, a, [(key, t1)])
            if not ap:
                continue
            img1 = C.Image(L1, I, None)
            ids = [int(x) for x in np.unique(L1[cs][union]) if x]
            for b in obj_ops:
                for t2 in range(len(C.THETA[b])):
                    for o2 in ids:
                        L2, ap2 = C.apply(img1, b, [(o2, t2)])
                        if not ap2:
                            continue
                        new = [L2[cs] == v for v in np.unique(L2[cs][union]) if v]
                        if _same_res(new, res):
                            return True
    return False


def _work_delta(w0, w1):
    return {k: w1[k] - w0.get(k, 0) for k in w1}


def admit(ds, candidates, demo_roles=("induction",), val_roles=("validation",), rule="strict"):
    """Greedy admission (section 9). Returns (admitted, trail, cpu_s); the trail's last record holds the charged work
    (Amendment 3: candidate validations, policy runs, programs scored, exact matchings, CPU and wall). Amendment 8:
    `rule` selects the policy's acceptance rule (the default is the protocol's); the admission checks are the same."""
    admitted, trail = [], []
    t0, w0, wall0 = time.process_time(), RN.work_snapshot(), time.time()
    for op in candidates:
        if op in admitted:
            continue
        D0, Q0 = _sets(ds, demo_roles), _sets(ds, val_roles)
        res_0 = RN.run_policy(list(admitted), D0, Q0, rule=rule)
        Dw, Qw = _sets(ds, demo_roles), _sets(ds, val_roles)
        res_w = RN.run_policy(list(admitted) + [op], Dw, Qw, rule=rule)
        b_w, f_w = RN.score_set(Qw)
        b_0, f_0 = RN.score_set(Q0)
        pf = lambda b: np.where(b[:, 0] + b[:, 1] > 0, 2 * b[:, 2] / np.maximum(b[:, 0] + b[:, 1], 1e-12), 1.0)  # noqa
        d = pf(b_w) - pf(b_0)
        n_edits = sum(1 for e in res_w["query_log"] if e["op"] == op)
        ash, n_al = alias_share(ds, op, res_w["query_log"], admitted, Q0.L)
        ok = tuple(bool(x) for x in (n_edits >= 1, f_w > f_0 + 1e-12, int((d > 1e-12).sum()) > int((d < -1e-12).sum()),
                                     ash < 0.5))
        rec = {"op": op, "edits_on_validation": n_edits, "val_f1_without": f_0, "val_f1_with": f_w,
               "parents_better": int((d > 1e-12).sum()), "parents_worse": int((d < -1e-12).sum()),
               "alias_share": ash, "checks": dict(zip(("changes_outputs", "f1_rises", "more_better", "not_alias"), ok)),
               "admitted": all(ok), "policy": [r for r in res_w["ops"] if r["op"] == op]}
        trail.append(rec)
        if all(ok):
            admitted.append(op)
    cpu = time.process_time() - t0
    trail.append({"work": {"candidate_validations": len([r for r in trail if "op" in r]),
                           **_work_delta(w0, RN.work_snapshot()), "cpu_s": round(cpu, 1), "cpu_s_exact": cpu,
                           "wall_s": round(time.time() - wall0, 1)}})
    return admitted, trail, round(cpu, 1)


def _jsonable(o):
    """Amendment 6: numpy scalars and arrays in admission records are written as plain JSON values."""
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(f"not serializable: {type(o).__name__}")


def derangement(seed, items):
    rng = np.random.default_rng(seed)
    while True:
        p = list(rng.permutation(len(items)))
        if all(p[i] != i for i in range(len(items))):
            return {items[i]: items[p[i]] for i in range(len(items))}


def _exact_cpu(trail):
    w = [r for r in trail if "work" in r]
    return w[0]["work"].get("cpu_s_exact") if w else None


def induce(ds, rule="strict"):
    """Section 9 on A with the controls. Amendment 8: rule="tolerant" runs the same induction (same failure records,
    specification, candidate ceilings and control draws) with the CORA_TOLERANT acceptance rule and writes
    INDUCTION_TOLERANT.json; the protocol's INDUCTION.json is never rewritten by it."""
    t0 = time.process_time()
    out = {"dataset": ds, "rule": rule}
    spec, fr, gains = specify(ds)
    adm, trail, cpu = admit(ds, spec, rule=rule)
    out["CORA"] = {"specified": spec, "admitted": adm, "trail": trail, "admission_cpu_s": cpu,
                   "admission_cpu_s_exact": _exact_cpu(trail),
                   "failure_records": fr["per_class"], "probe_cpu_s": fr["probe_cpu_s"], "oracle_gains": gains}
    # Amendment 3: equal candidate-validation ceilings. Each control validates exactly as many candidate operators as
    # CORA did (n_spec), so the failure records are the only difference in what is tried.
    n_spec = len(spec)
    out["candidate_ceiling"] = n_spec
    out["FAILURE_BLIND"], out["SHUFFLED"] = {}, {}
    for r in range(1, 6):
        rng = np.random.default_rng(7000 + r)
        draw = [C.OPS[i] for i in rng.choice(len(C.OPS), size=n_spec, replace=False)] if n_spec else []
        a, tr, cp = admit(ds, draw, rule=rule)
        out["FAILURE_BLIND"][str(r)] = {"drawn": draw, "admitted": a, "trail": tr, "admission_cpu_s": cp,
                                        "admission_cpu_s_exact": _exact_cpu(tr)}
        rel = derangement(8000 + r, list(C.CLASSES))
        sp, frs, gs = specify(ds, rel)
        if len(sp) > n_spec:
            sp = sp[:n_spec]
        elif len(sp) < n_spec:
            rest = [o for o in C.OPS if o not in sp]
            pad = np.random.default_rng(9000 + r).permutation(len(rest))[:n_spec - len(sp)]
            sp = sp + [rest[i] for i in pad]
        a2, tr2, cp2 = admit(ds, sp, rule=rule)
        out["SHUFFLED"][str(r)] = {"relabel": rel, "specified_pinned": sp, "admitted": a2, "trail": tr2,
                                   "admission_cpu_s": cp2, "admission_cpu_s_exact": _exact_cpu(tr2)}
    out["cpu_s_total"] = round(time.process_time() - t0, 1)
    out["cora_induction_cpu_s"] = round(fr["probe_cpu_s"] + cpu, 1)
    out["cora_induction_cpu_s_unrounded"] = fr["probe_cpu_s"] + _exact_cpu(trail)   # probes as recorded (0.1 s)
    name = "INDUCTION.json" if rule == "strict" else "INDUCTION_TOLERANT.json"
    tmp = os.path.join(W, ds, name + ".tmp")
    json.dump(out, open(tmp, "w"), indent=1, default=_jsonable)
    os.replace(tmp, os.path.join(W, ds, name))                      # written whole or not at all
    print(json.dumps({"CORA": {"specified": spec, "admitted": adm},
                      "blind": {r: v["admitted"] for r, v in out["FAILURE_BLIND"].items()},
                      "shuffled": {r: v["admitted"] for r, v in out["SHUFFLED"].items()}}))
    return out


if __name__ == "__main__":
    cmd, ds = sys.argv[1], sys.argv[2]
    {"gate": gate, "induce": induce, "induce_tolerant": lambda d: induce(d, "tolerant")}[cmd](ds)
