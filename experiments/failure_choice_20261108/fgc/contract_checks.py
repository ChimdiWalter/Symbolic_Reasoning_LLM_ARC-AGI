"""Source-only literal checks of the strong full-bank contract (fgc/contract.py), on invented tasks.

    python3 -I fgc/contract_checks.py OUT.json        (standard library; reads no task, label or measurement file)

Invented measurements with hand-computed outcomes (literal expectations), the real order functions of
fgc/pipeline.py on invented descriptors, and literal source checks of fgc/pipeline.py and fgc/arms.py:
1. one bank: every intervention any arm runs goes through contract.execute, on the current task's own measurement
   object (identity), and only interventions of BANK run;
2. one meter: every arm gets the same budget; no arm spends more; the base attempt is charged to every arm;
3. arms differ only in order: two arms with the same order give identical results on every invented task;
4. shuffled diagnosis changes only the descriptor: its order is the fixed router's order on the donor's descriptor,
   and it is executed on the current task's measurement; given the task's own descriptor it equals the fixed router;
5. donor demonstrations are never used: in the sealing code the donor appears only as an index into the
   descriptors, and every arm is executed with the current task's measurement;
6. nothing outside contract.py executes an intervention (no other code reads a measurement's search or construct
   record).
"""
import json
import os
import re
import sys

STUDY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, STUDY)
from fgc import contract as K                                    # noqa: E402
from fgc import pipeline as PL                                   # noqa: E402

G1, G2 = [[[[1]]]], [[[[2]]]]                                    # invented one-cell predictions


def meas(base_fit=False, base_calls=100, s_fit=True, s_calls=500, s_stop="fits", c_fit=True, c_calls=2000):
    return {"base": {"fit": base_fit, "calls": base_calls, "preds": G1 if base_fit else None},
            "search": {"fit": s_fit, "calls": s_calls, "stop": s_stop, "preds": G1 if s_fit else None},
            "construct": {"fit": c_fit, "calls": c_calls, "preds": G2 if c_fit else None}}


LITERAL = [
    # (label, measurement, order, budget, k_s, search_all, expected (preds, by, spent))
    ("search first, search fits", meas(), ("search", "construct"), 1000, 600, False, (G1, "search", 600)),
    ("construct first, cut off, search gets nothing", meas(), ("construct", "search"), 1000, 600, False,
     (None, None, 1000)),
    ("construct first, enough budget", meas(), ("construct", "search"), 3000, 600, False, (G2, "construct", 2100)),
    ("search fails at its cap, construct fits", meas(s_fit=False, s_calls=20_000_000, s_stop="budget"),
     ("search", "construct"), 3000, 600, False, (G2, "construct", 2700)),
    ("search fails at its cap, construct cut off", meas(s_fit=False, s_calls=20_000_000, s_stop="budget"),
     ("search", "construct"), 2500, 600, False, (None, None, 2500)),
    ("base fits", meas(base_fit=True), ("construct", "search"), 3000, 600, False, (G1, "base", 100)),
    ("arm B: search gets every remaining call", meas(s_calls=800), ("search",), 1000, 600, True, (G1, "search", 900)),
    ("bank cap: the same search misses under K_S", meas(s_calls=800), ("search", "construct"), 1000, 600, False,
     (None, None, 1000)),
    ("search exhausts its fragment early", meas(s_fit=False, s_calls=300, s_stop="max_size"),
     ("search", "construct"), 3000, 600, False, (G2, "construct", 2400)),
    ("no intervention (arm A)", meas(), (), 3000, 600, False, (None, None, 100)),
]

RULES = {"rules": [{"all": [{"feature": "closest_fraction", "at_least": 0.5}], "first": "search"}], "default_first": "construct"}


def desc(frac):
    return {"shape": "same", "identity_sketch": 0.3, "best_other_sketch": 0.2, "closest_fraction": frac,
            "level_complete": 5, "bank": 1000, "n_demos": 3, "area_ratio": 1.0, "colours_in": 3.0, "colours_out": 3.0}


def main(out):
    res = {"literal": {}, "properties": {}}
    for label, m, order, budget, k_s, sa, want in LITERAL:
        got = K.run_arm(m, order, budget, k_s, sa)
        res["literal"][label] = {"got": [got[0] is not None and got[0], got[1], got[2]], "ok": got == want}
    # invented task set: measurements, descriptors, donors
    tasks = {"tA": meas(), "tB": meas(s_fit=False, s_calls=20_000_000, s_stop="budget"),
             "tC": meas(c_fit=False, c_calls=1500), "tD": meas(base_fit=True), "tE": meas(s_calls=3000)}
    descs = {"tA": desc(0.9), "tB": desc(0.1), "tC": desc(0.7), "tD": desc(0.2), "tE": desc(0.4)}
    donor = PL.donor_of(sorted(tasks))
    calls = []
    orig = K.execute

    def spy(iv, m, meter, k_s, search_all=False):
        calls.append((iv, id(m), meter.budget))
        return orig(iv, m, meter, k_s, search_all)

    K.execute = spy
    try:
        per_arm = {}
        for t, m in tasks.items():
            orders = {"A": (), "B": ("search",), "C": ("search", "construct"), "D": PL.random_order(t),
                      "E": PL.route_fixed(descs[donor[t]], RULES), "F": PL.route_fixed(descs[t], RULES),
                      "E_own_descriptor": PL.route_fixed(descs[t], RULES)}
            for a, o in orders.items():
                start = len(calls)
                r = K.run_arm(m, o, 2500, 600, search_all=(a == "B"))
                ran = calls[start:]
                per_arm[(t, a)] = r
                res["properties"].setdefault("one_bank_current_task", []).append(
                    all(iv in K.BANK and mid == id(m) for iv, mid, _ in ran))
                res["properties"].setdefault("one_meter_same_budget", []).append(
                    all(b == 2500 for _, _, b in ran) and r[2] <= 2500 and r[2] >= m["base"]["calls"])
            res["properties"].setdefault("shuffled_is_router_on_donor_descriptor", []).append(
                orders["E"] == PL.route_fixed(descs[donor[t]], RULES) and donor[t] != t)
            res["properties"].setdefault("shuffled_with_own_descriptor_equals_router", []).append(
                per_arm[(t, "E_own_descriptor")] == per_arm[(t, "F")])
        for t in tasks:
            for o in (("search", "construct"), ("construct", "search")):
                same = [a for a in ("C", "D", "E", "F") if (("search", "construct") if a == "C" else
                                                            {"D": PL.random_order(t),
                                                             "E": PL.route_fixed(descs[donor[t]], RULES),
                                                             "F": PL.route_fixed(descs[t], RULES)}[a]) == o]
                vals = {repr(per_arm[(t, a)]) for a in same}
                res["properties"].setdefault("same_order_same_result", []).append(len(vals) <= 1)
    finally:
        K.execute = orig
    # literal source checks
    src = open(os.path.join(STUDY, "fgc", "pipeline.py"), encoding="utf-8").read()
    arms_src = open(os.path.join(STUDY, "fgc", "arms.py"), encoding="utf-8").read()
    run_calls = re.findall(r"K\.run_arm\(([^,]+),", src)
    res["properties"]["every_arm_runs_on_the_current_task"] = [bool(run_calls) and all(c.strip() == "ms[t]"
                                                                                         for c in run_calls)]
    donor_uses = re.findall(r"donor\[t\]", src)
    res["properties"]["donor_only_indexes_descriptors"] = [len(donor_uses) == len(re.findall(r"feats\[donor\[t\]\]",
                                                                                            src)) > 0]
    leaks = [p for p in (src, arms_src) if re.search(r"\[\"(search|construct)\"\]\s*\[", p)]
    res["properties"]["no_execution_outside_the_contract"] = [not leaks]
    res["properties"]["static_and_router_arms_share_execute"] = [src.count("K.run_arm(") >= 1 and
                                                                 "def execute" not in src and
                                                                 "def execute" not in arms_src]
    res["properties"] = {k: all(v) for k, v in res["properties"].items()}
    res["all_pass"] = all(v["ok"] for v in res["literal"].values()) and all(res["properties"].values())
    with open(out, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1, sort_keys=True, default=str)
        f.write("\n")
    print(json.dumps({"all_pass": res["all_pass"], "properties": res["properties"],
                      "literal_failures": [k for k, v in res["literal"].items() if not v["ok"]]}))


if __name__ == "__main__":
    main(sys.argv[1])
