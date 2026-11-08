"""Sealing (system side) and scoring (evaluator side) of the failure-guided choice test.

    python -m fgc.pipeline seal  MEASURE_DIR OUT_DIR [--dev]   every arm's committed predictions at every budget,
                                                              label-blind; writes SEALED_PREDICTIONS.json and its
                                                              sha256 (SEALED_SHA256)
    python -m fgc.pipeline score SEALED_DIR EVAL.json MEASURE_DIR OUT_DIR [--dev]
                                                              scores the sealed predictions, adds the oracle arm
                                                              (it reads the generator's causes), and writes
                                                              ANALYSIS.json with the pre-registered decision

Without --dev both run under the GO gate (stages seal and score) on the held set. With --dev they run on the source
set, before the freeze, to develop the fixed router, train the learned router and set the budget constants.
The frozen constants and routers are in config/ROUTERS.json.
"""
import glob
import json
import os
import sys

from fgc import arms as A
from fgc import contract as K

STUDY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def sha(p):
    import hashlib
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def dump(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1, sort_keys=True)
        f.write("\n")


def measurements(d):
    out = {}
    for p in sorted(glob.glob(os.path.join(d, "**", "*.json"), recursive=True)):
        doc = load(p)
        if isinstance(doc, dict) and all(isinstance(v, dict) and "construct" in v for v in doc.values()):
            for k, v in doc.items():
                if k in out and out[k] != v:
                    raise SystemExit(f"task {k} measured twice with different results")
                out[k] = v
    return out


# ------------------------------------------------------------------ routers (system side; frozen in ROUTERS.json)
def _holds(c, f):
    v = f[c["feature"]]
    if "values" in c:
        return v in c["values"]
    if "at_least" in c:
        return v >= c["at_least"]
    if "at_most" in c:
        return v <= c["at_most"]
    return v < c["below"]


def route_fixed(f, rules):
    """The fixed evidence-based router: hand-written rules over failure features, in order; the first rule all of
    whose conditions hold gives the whole order of the bank; otherwise the default order."""
    for r in rules["rules"]:
        if all(_holds(c, f) for c in r["all"]):
            return tuple(r["order"])
    return tuple(rules["default_order"])


def route_learned(f, model, tie_order):
    """The learned router: the interventions in decreasing predicted probability that each alone commits a correct
    answer; ties in the static order."""
    x = A.vector(f)
    p = {iv: A.predict_logistic(model[iv], x) for iv in A.INTERVENTIONS}
    order = tuple(sorted(A.INTERVENTIONS, key=lambda iv: (-p[iv], tie_order.index(iv))))
    return order, p


def donor_of(ids):
    """Shuffled diagnosis: each task routes on the record of the next task in sha256 order (a derangement)."""
    order = sorted(ids, key=lambda t: A.h("donor:" + t))
    return {t: order[(i + 1) % len(order)] for i, t in enumerate(order)}


def random_order(t):
    """A uniformly random permutation of the bank per task, from sha256 of the task id and each intervention."""
    return tuple(sorted(A.INTERVENTIONS, key=lambda iv: A.h(f"random:{t}:{iv}")))


def seal(measure_dir, out_dir, dev=False):
    if not dev:
        sys.path.insert(0, os.path.join(STUDY, "fgc"))
        from fgc import gate
        if not gate.check("seal"):
            raise SystemExit("gate refused")
    R = load(os.path.join(STUDY, "config", "ROUTERS.json"))
    ms = measurements(measure_dir)
    ids = sorted(ms)
    feats = {t: A.features(ms[t]) for t in ids}
    donor = donor_of(ids)
    orders = {}
    probs = {}
    static = tuple(R["static_order"])
    for t in ids:
        g_order, p = route_learned(feats[t], R["learned"], static)
        probs[t] = p
        orders[t] = {"A": (), "B": ("search",), "C": static, "D": random_order(t),
                     "E": route_fixed(feats[donor[t]], R["fixed"]), "F": route_fixed(feats[t], R["fixed"]),
                     "G": g_order}
    caps = {"search": R["K_S"], "view": R["K_V"]}
    reads = {"E", "F", "G"}                                  # arms that read a failure descriptor pay its calls
    sealed = {"constants": {k: R[k] for k in ("K_S", "K_V", "T_STAR", "static_order")}, "budget_mults": A.BUDGET_MULTS,
              "orders": {t: {a: list(o) for a, o in orders[t].items()} for t in ids}, "learned_p": probs,
              "donor": donor, "features": feats, "arms": {}}
    for a in "ABCDEFG":
        sealed["arms"][a] = {}
        for mult in A.BUDGET_MULTS:
            B = R["T_STAR"] * mult
            col = {}
            for t in ids:
                preds, by, spent = K.run_arm(ms[t], orders[t][a], B, caps, search_all=(a == "B"),
                                             descriptor_calls=feats[t]["descriptor_calls"] if a in reads else 0)
                col[t] = {"preds": preds, "by": by, "calls": spent}
            sealed["arms"][a][str(mult)] = col
    p = os.path.join(out_dir, "SEALED_PREDICTIONS.json")
    dump(p, sealed)
    with open(os.path.join(out_dir, "SEALED_SHA256"), "w") as f:
        f.write(sha(p) + "\n")
    print(json.dumps({"tasks": len(ids), "sealed_sha256": sha(p)}))


def correct(preds, outs):
    if not preds:
        return False
    return any(att == outs for att in preds)


def score(sealed_dir, eval_path, measure_dir, out_dir, dev=False):
    if not dev:
        from fgc import gate
        if not gate.check("score"):
            raise SystemExit("gate refused")
    sp = os.path.join(sealed_dir, "SEALED_PREDICTIONS.json")
    with open(os.path.join(sealed_dir, "SEALED_SHA256")) as f:
        if sha(sp) != f.read().strip():
            raise SystemExit("sealed predictions differ from their digest")
    S = load(sp)
    ev = load(eval_path)
    ms = measurements(measure_dir)
    R = load(os.path.join(STUDY, "config", "ROUTERS.json"))
    ids = sorted(S["orders"])
    missing = [t for t in ev if t not in S["orders"]]
    if missing or set(ids) - set(ev):
        raise SystemExit(f"sealed tasks differ from the labelled set (missing {missing[:5]})")
    res = {"tasks": len(ids), "constants": S["constants"], "by_budget": {}}
    for mult in A.BUDGET_MULTS:
        rows = []
        for t in ids:
            e = ev[t]
            row = {"task": t, "family": e["family"], "cause": e["cause"]}
            for a in "ABCDEFG":
                c = S["arms"][a][str(mult)][t]
                row[a] = correct(c["preds"], e["test_outputs"])
                row[a + "_calls"] = c["calls"]
                row[a + "_by"] = c["by"]
            h_order = A.rest(A.CAUSE_FIX[e["cause"]], tuple(R["static_order"]))
            preds, by, spent = K.run_arm(ms[t], h_order, R["T_STAR"] * mult, {"search": R["K_S"], "view": R["K_V"]})
            row["H"], row["H_calls"], row["H_by"] = correct(preds, e["test_outputs"]), spent, by
            rows.append(row)
        acc = {a: sum(r[a] for r in rows) for a in A.ARMS}
        calls = {a: round(sum(r[a + "_calls"] for r in rows) / len(rows)) for a in A.ARMS}
        res["by_budget"][str(mult)] = {"correct": acc, "mean_calls": calls,
                                       "by_cause": {c: {a: sum(r[a] for r in rows if r["cause"] == c) for a in A.ARMS}
                                                    | {"tasks": sum(1 for r in rows if r["cause"] == c)}
                                                    for c in sorted({r["cause"] for r in rows})},
                                       "F_vs_C": A.contrast(rows, "F", "C")}
        res.setdefault("rows", {})[str(mult)] = rows
    rows = res["rows"]["1.0"]
    prim = A.contrast(rows, "F", "C")
    ci = prim["family_ci95"]
    prim["success"] = prim["mcnemar_p"] < 0.05 and bool(ci) and ci[0] > 0
    res["primary"] = prim
    sec_names = [("G", "C"), ("F", "E"), ("F", "D")]
    sec = {f"{a} vs {b}": A.contrast(rows, a, b) for a, b in sec_names}
    adj = A.holm([v["mcnemar_p"] for v in sec.values()])
    for (k, v), p in zip(sec.items(), adj):
        v["holm_p"] = p
        v["holds"] = p < 0.05 and bool(v["family_ci95"]) and v["family_ci95"][0] > 0
    res["secondary"] = sec
    curve = {m: res["by_budget"][str(m)]["F_vs_C"]["difference"] for m in A.BUDGET_MULTS}
    res["budget_curve"] = {"F_minus_C": curve, "prediction": "the advantage appears at binding budgets and shrinks "
                           "as the budget grows", "prediction_holds": (curve[4.0] or 0) < (curve[1.0] or 0)}
    # efficiency: work to reach the static arm's accuracy at the binding budget
    c_acc = res["by_budget"]["1.0"]["correct"]["C"]
    reach = {a: next((m for m in A.BUDGET_MULTS if res["by_budget"][str(m)]["correct"][a] >= c_acc), None)
             for a in ("C", "D", "E", "F", "G", "H")}
    diff = [r["F_calls"] - r["C_calls"] for r in rows]
    res["efficiency"] = {"smallest_budget_multiple_reaching_C_at_T_STAR": reach,
                         "mean_calls_at_T_STAR": res["by_budget"]["1.0"]["mean_calls"],
                         "F_minus_C_calls_mean": round(sum(diff) / len(diff)),
                         "F_minus_C_calls_family_ci95": calls_boot(rows)}
    res["decision"] = decide(res, rows)
    dump(os.path.join(out_dir, "ANALYSIS.json"), res)
    print(json.dumps({"primary": {k: prim[k] for k in ("tasks", "only_F", "only_C", "difference", "mcnemar_p",
                                                         "family_ci95", "success")}, "decision": res["decision"],
                      "correct_at_T_STAR": res["by_budget"]["1.0"]["correct"]}))


def calls_boot(rows, n=10000, seed=11):
    import random
    fams = sorted({r["family"] for r in rows})
    by = {f: [r["F_calls"] - r["C_calls"] for r in rows if r["family"] == f] for f in fams}
    rng = random.Random(seed)
    means = sorted(sum(d) / len(d) for d in ([x for f in (rng.choice(fams) for _ in fams) for x in by[f]]
                                            for _ in range(n)) if d)
    return [round(means[int(0.025 * len(means))]), round(means[int(0.975 * len(means))])]


def decide(res, rows):
    """The pre-registered outcome, the first that holds in this order."""
    p = res["primary"]
    if p["success"]:
        return "selection advantage: the fixed router beats the static full bank at the binding budget"
    ci = p["family_ci95"]
    if p["mcnemar_p"] < 0.05 and ci and ci[1] < 0:
        return "static bank better: the static full bank beats the fixed router at the binding budget"
    e = res["efficiency"]
    t_star = res["constants"]["T_STAR"]
    if (p["only_F"] >= p["only_C"]) and e["F_minus_C_calls_family_ci95"][1] < -0.05 * t_star:
        return "efficiency: the fixed router matches the static bank's accuracy with materially less work"
    cb = A.contrast(rows, "C", "B")
    res["capability_C_vs_B"] = cb
    if cb["mcnemar_p"] < 0.05 and cb["family_ci95"] and cb["family_ci95"][0] > 0:
        return "capability: the bank adds solved tasks over extra search at the binding budget; the choice does not"
    c4 = A.contrast(res["rows"]["4.0"], "C", "B")
    res["coverage_C_vs_B_at_4T"] = c4
    if c4["mcnemar_p"] < 0.05 and c4["family_ci95"] and c4["family_ci95"][0] > 0:
        return "coverage: the bank adds solved tasks over extra search only at four times the binding budget"
    return "none: no selection advantage, efficiency, capability or coverage effect"


if __name__ == "__main__":
    dev = "--dev" in sys.argv
    args = [a for a in sys.argv[2:] if a != "--dev"]
    if sys.argv[1] == "seal":
        seal(args[0], args[1], dev)
    elif sys.argv[1] == "score":
        score(args[0], args[1], args[2], args[3], dev)
