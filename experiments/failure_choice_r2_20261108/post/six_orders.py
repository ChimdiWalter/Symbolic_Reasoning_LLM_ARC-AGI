"""Descriptive output after scoring (PROTOCOL.md section 7; never part of the decision rule): every fixed order of the
bank, the six permutations, at the binding budget T*, replayed with the frozen `contract.run_arm` on the committed
held measurements with no descriptor charge (as for C), and shown beside F and C from the committed ANALYSIS.json.

    PYTHONPATH=. python post/six_orders.py        (from the study folder, after runs/test/ANALYSIS.json is committed)

Checks first that the order equal to C's pre-registered static order reproduces C's committed result on every task.
Writes runs/test/SIX_ORDERS.json.
"""
import itertools
import json
import os
import sys

STUDY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, STUDY)

from fgc import arms as A                                                    # noqa: E402
from fgc import contract as K                                                # noqa: E402
from fgc.pipeline import load, dump, measurements, correct                   # noqa: E402


def main():
    R = load(os.path.join(STUDY, "config", "ROUTERS.json"))
    ev = load(os.path.join(STUDY, "runs", "test", "evaluator_only", "TEST_EVAL.json"))
    ms = measurements(os.path.join(STUDY, "runs", "test", "measure"))
    an = load(os.path.join(STUDY, "runs", "test", "ANALYSIS.json"))
    rows = {r["task"]: r for r in an["rows"]["1.0"]}
    ids = sorted(ms)
    if not (set(ids) == set(ev) == set(rows)):
        raise SystemExit("measured, labelled and scored tasks differ")
    caps = {"search": R["K_S"], "view": R["K_V"]}
    t_star = R["T_STAR"]
    static = "/".join(R["static_order"])
    causes = sorted({e["cause"] for e in ev.values()})
    orders = {}
    for order in itertools.permutations(K.BANK):
        ok = {t: correct(K.run_arm(ms[t], order, t_star, caps)[0], ev[t]["test_outputs"]) for t in ids}
        name = "/".join(order)
        if name == static and any(ok[t] != rows[t]["C"] for t in ids):
            raise SystemExit("the replay of C's static order differs from C's committed result")
        cst = A.contrast([{"family": ev[t]["family"], "F": rows[t]["F"], "O": ok[t]} for t in ids], "F", "O")
        orders[name] = {"correct": sum(ok.values()),
                        "by_cause": {c: sum(ok[t] for t in ids if ev[t]["cause"] == c) for c in causes},
                        "F_against_this_order": {k: cst[k] for k in ("only_F", "only_O", "mcnemar_p", "family_ci95")}}
    best = max(v["correct"] for v in orders.values())
    out = {"note": "descriptive only (PROTOCOL.md section 7); not part of the decision rule",
           "budget_calls": t_star, "tasks": len(ids),
           "tasks_by_cause": {c: sum(1 for t in ids if ev[t]["cause"] == c) for c in causes},
           "C_static_order": static, "C_replay_equals_committed_C": True,
           "committed_at_T_STAR": {a: an["by_budget"]["1.0"]["correct"][a] for a in ("C", "F", "H")},
           "fixed_orders": orders, "best_fixed_order_correct": best,
           "best_fixed_orders": sorted(k for k, v in orders.items() if v["correct"] == best)}
    dump(os.path.join(STUDY, "runs", "test", "SIX_ORDERS.json"), out)
    print(json.dumps({"best": out["best_fixed_orders"], "best_correct": best,
                      "committed": out["committed_at_T_STAR"],
                      "correct": {k: v["correct"] for k, v in orders.items()}}))


if __name__ == "__main__":
    main()
