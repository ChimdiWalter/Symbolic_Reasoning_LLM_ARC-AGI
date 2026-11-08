"""U5 Amendment 9: a calibration-only diagnostic of the protocol's acceptance rule, stage by stage (the "acceptance
waterfall"). It repeats u5policy.verify's steps on one operator's space and counts what survives each step; it never
changes a decision, and nothing that produces a decision imports it.

    python -I u5waterfall.py <dataset> <operator>     (A's admission context: induction demos, validation queries)
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from u5policy import RASHOMON, select, verify    # noqa: E402,F401


def _guard_selection(space, prog, q):
    """The units a program's guard selects, before the executor's conflict rule (`select` minus `executed`)."""
    t, g = space.progs[prog]
    F, V = q["feats"][t], q["valid"][t]
    s = V.copy()
    pr = space.preds[t]
    for i in g:
        j, op, th = pr[i]
        s &= (F[:, j] < th) if op == "<" else (F[:, j] > th)
    return s


def waterfall(space, demo_parents_with_units, q, reverse_check=True):
    """Amendment 9: a calibration-only diagnostic of the protocol's acceptance rule (section 10), stage by stage, for
    one operator and one set of units q. It repeats verify's steps and counts what survives each: programs scored,
    conflicted, harmless, positive gain, admissible, FIT; the units selected by some FIT program and by every one (the
    near-top intersection); the leave-one-parent-out tops and their held-out harm; the intersection with them; the
    class agreement; the units the executor's conflict rule removes from the top program; verify's own status and
    accepted units. It never changes a decision."""
    U = len(q["valid"][0]) if q["valid"] else 0
    G = space.pooled_gain(np.ones(space.P, bool))
    nh = ~space.harm.any(1)
    adm = nh & (G > 1e-12) & (space.E > 0) & ~space.conflicted
    out = {"programs": len(space.progs), "conflicted": int(space.conflicted.sum()), "harmless": int(nh.sum()),
           "positive_pooled_gain": int((G > 1e-12).sum()), "admissible": int(adm.sum()), "units": U}
    fit, top = space.fit()
    out.update(fit=int(len(fit)), top=None if top is None else int(top))
    if top is None:
        out["stop"] = "NO_FIT"
        return out
    some, every = np.zeros(U, bool), np.ones(U, bool)
    for i in fit:
        s, _ = select(space, i, q)
        some |= s
        every &= s
    out.update(selected_by_some_fit=int(some.sum()), near_top_intersection=int(every.sum()))
    tops, loo_fail = [], 0
    for p in range(space.P):
        if space.base[p][0] + space.base[p][1] == 0:
            continue
        keep = np.ones(space.P, bool)
        keep[p] = False
        tp_ = space.fit(keep)[1]
        tops.append(tp_)
        loo_fail += int(tp_ is None or bool(space.harm[tp_, p]))
    fs = set(int(i) for i in fit)
    out.update(folds=len(tops), fold_tops_distinct=len({t for t in tops if t is not None}),
               fold_tops_outside_fit=sum(1 for t in tops if t is not None and t not in fs), folds_failing_loo=loo_fail)
    after = every.copy()
    for t in tops:
        if t is not None:
            after &= select(space, t, q)[0]
    out["intersection_with_fold_tops"] = int(after.sum())
    agree, cls0 = after.copy(), None
    for i in list(fit) + [t for t in tops if t is not None]:
        c = select(space, i, q)[1]
        cls0 = c if cls0 is None else cls0
        agree &= (c == cls0)
    out["after_class_agreement"] = int(agree.sum())
    raw = _guard_selection(space, top, q)
    ex = select(space, top, q)[0]
    out.update(top_guard_selected=int(raw.sum()), top_executed=int(ex.sum()),
               top_conflict_abstained=int((raw & ~ex).sum()))
    r = verify(space, demo_parents_with_units, q, reverse_check)
    out.update(verify_status=r["status"], accepted=int(r["accepted"].sum()))
    return out


def admission_context(ds, op):
    """The waterfall of `op` exactly where the admission validated it on A: the operators admitted before it in the
    specification order are applied first (none on LIVECell), then op's space on the induction parents and its units
    on the validation parents, as in u5induce.admit; the applied edits come from the executor's reconciliation."""
    import u5induce as IN
    import u5policy as P
    import u5run as RN
    W = RN.W
    ind = json.load(open(os.path.join(W, ds, "INDUCTION.json")))
    spec, adm = ind["CORA"]["specified"], ind["CORA"]["admitted"]
    before = [a for a in adm if spec.index(a) < spec.index(op)]
    D, Q = IN._sets(ds, ("induction",)), IN._sets(ds, ("validation",))
    RN.run_policy(before, D, Q)
    du = RN.set_units(D, op)
    sp = P.Space(du, D.base(), len(D.parents))
    npar = len(set(du["parent"].tolist())) if len(du["keys"]) else 0
    qu = RN.set_units(Q, op)
    out = {"dataset": ds, "operator": op, "admitted_before": before, "side": "calibration only",
           "demonstration_parents": len(D.parents), "query_parents": len(Q.parents),
           "queries": waterfall(sp, npar, qu), "demonstrations": waterfall(sp, npar, du)}
    r = P.verify(sp, npar, qu, True)
    out["applied_edits_on_queries"] = len(RN.apply_accepted(Q, op, qu["keys"], r["accepted"], r["theta"]))
    rd = P.verify(sp, npar, du, True)
    out["applied_edits_on_demonstrations"] = len(RN.apply_accepted(D, op, du["keys"], rd["accepted"], rd["theta"]))
    rec = [r_ for r_ in ind["CORA"]["trail"] if r_.get("op") == op]
    out["recorded_in_induction"] = rec[0]["policy"] if rec else None
    p = os.path.join(W, ds, f"WATERFALL_{op}.json")
    json.dump(out, open(p, "w"), indent=1, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o))
    E = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    json.dump(out, open(os.path.join(E, f"WATERFALL_{ds}_{op}.json"), "w"), indent=1,
              default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o))
    print(json.dumps({k: out[k] for k in ("queries", "applied_edits_on_queries", "applied_edits_on_demonstrations")}))
    return out


if __name__ == "__main__":
    admission_context(sys.argv[1], sys.argv[2])
