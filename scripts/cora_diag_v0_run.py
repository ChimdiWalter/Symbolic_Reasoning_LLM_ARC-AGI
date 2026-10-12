"""Run automatic failure diagnosis v0 on the RECORDED traces of the four
failure-conditioned development tasks (4 full-data runs + 14 outer folds), then
audit it against the independent forensic reference with three controls.
Observation only: no engine run, no repair, nothing frozen is touched.

  python scripts/cora_diag_v0_run.py   -> outputs/cora_diag/records.jsonl, outputs/cora_diag/audit.json
"""
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
BUNDLE = os.path.join(HERE, "records", "pilot_v1", "dev_bundle.json")
TASKS = ("kf892487f1049", "k5a49896251a2", "k017955a77fc5", "k5991e227189e")


def build_units():
    from cora_diag import arc_adapter as AD
    from cora_reach import measure as M
    rows = {json.loads(x)["key"]: json.loads(x) for x in open(os.path.join(HERE, "outputs", "reach_v1", "measure_rows.jsonl")) if x.strip()}
    diag = {}
    for x in open(os.path.join(HERE, "outputs", "loo_v1", "diagnose_rows.jsonl")):
        if x.strip():
            r = json.loads(x)
            diag[r["key"]] = r
    census = json.load(open(os.path.join(HERE, "outputs", "loo_v1", "probe_equivalence.json")))["development"]
    bundle = json.load(open(BUNDLE))["tasks"]
    units = []
    for t in TASKS:
        train, tests = M.arrays(bundle[t])                  # inputs only are used below
        n = len(train)
        cen = census[t]["subsets"]
        units.append((f"{t}:full", AD.unit_observations(t, n, None, rows[t], diag.get(f"{t}:full"), cen,
                                                        [x.tolist() for x in tests])))
        for i in range(n):
            unl = [train[i][0].tolist()] + [x.tolist() for x in tests]   # the removed demonstration's INPUT + test inputs
            units.append((f"{t}:f{i}", AD.unit_observations(t, n, i, rows[t], diag.get(f"{t}:f{i}"), cen, unl)))
    return units


def score(pred, ref):
    """primary accuracy and set precision / recall over units."""
    keys = sorted(ref)
    acc = sum(1 for k in keys if pred[k]["primary"] == ref[k][0]) / len(keys)
    tp = sum(len(set(pred[k]["established"]) & ref[k][1]) for k in keys)
    fp = sum(len(set(pred[k]["established"]) - ref[k][1]) for k in keys)
    fn = sum(len(ref[k][1] - set(pred[k]["established"])) for k in keys)
    return {"primary_accuracy": round(acc, 3), "set_precision": round(tp / (tp + fp), 3) if tp + fp else None,
            "set_recall": round(tp / (tp + fn), 3) if tp + fn else None}


def main():
    from cora_pilot import isolation as ISO
    ISO.install(BUNDLE)
    sys.path.insert(0, os.path.join(HERE, "src"))
    from cora_diag.diagnose import diagnose
    from cora_diag.forensic_reference import REFERENCE
    units = build_units()
    pred = {k: diagnose(o) for k, o in units}
    real = score(pred, REFERENCE)
    rng = random.Random(20261012)
    keys, obs = [k for k, _ in units], [o for _, o in units]
    shuffled = []
    for _ in range(1000):
        perm = obs[:]
        rng.shuffle(perm)
        shuffled.append(score({k: diagnose(o) for k, o in zip(keys, perm)}, REFERENCE))
    majority = max({v[0] for v in REFERENCE.values()}, key=lambda c: sum(1 for v in REFERENCE.values() if v[0] == c))
    blind = score({k: {"primary": majority, "established": [majority] if majority else []} for k in keys}, REFERENCE)
    demo_only = score({k: diagnose({}) for k in keys}, REFERENCE)
    per_cat = {}
    for k in keys:
        for c in set(pred[k]["established"]) | REFERENCE[k][1]:
            d = per_cat.setdefault(c, {"tp": 0, "fp": 0, "fn": 0})
            inp, inr = c in pred[k]["established"], c in REFERENCE[k][1]
            d["tp" if inp and inr else ("fp" if inp else "fn")] += 1
    out = {"units": len(units), "v0": real, "per_category": per_cat,
           "controls": {"shuffled_traces": {"mean_primary_accuracy": round(sum(s["primary_accuracy"] for s in shuffled) / 1000, 3),
                                            "p_ge_real": sum(1 for s in shuffled if s["primary_accuracy"] >= real["primary_accuracy"]) / 1000},
                        "type_blind_majority": {"label": majority, **blind}, "demonstration_only": demo_only},
           "disagreements": [{"unit": k, "v0_primary": pred[k]["primary"], "reference_primary": REFERENCE[k][0],
                              "v0_set": pred[k]["established"], "reference_set": sorted(REFERENCE[k][1])}
                             for k in keys if pred[k]["primary"] != REFERENCE[k][0] or set(pred[k]["established"]) != REFERENCE[k][1]]}
    os.makedirs(os.path.join(HERE, "outputs", "cora_diag"), exist_ok=True)
    with open(os.path.join(HERE, "outputs", "cora_diag", "records.jsonl"), "w") as handle:
        for k, o in units:
            handle.write(json.dumps({"unit": k, "observations": o, **pred[k]}, sort_keys=True) + "\n")
    with open(os.path.join(HERE, "outputs", "cora_diag", "audit.json"), "w") as handle:
        json.dump(out, handle, indent=1, sort_keys=True)
    print(json.dumps({k: out[k] for k in ("units", "v0", "per_category", "controls")}, indent=1))


if __name__ == "__main__":
    main()
