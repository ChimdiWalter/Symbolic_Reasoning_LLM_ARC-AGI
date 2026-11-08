"""U5 dry run of decide + evaluate on CALIBRATION data only, to exercise the code paths before the evaluation hold is
released: validation parents play the evaluation role, induction parents the calibration role; references come from
the calibration store. Writes only to a scratch folder. Usage: python3 -I dryrun.py DS SCRATCH_DIR [grammar ops...]"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import u5core as C      # noqa: E402
import u5eval as EV     # noqa: E402
import u5run as RN      # noqa: E402
import u5static as ST   # noqa: E402


def main(ds, scratch, grammar):
    EV.DEC = os.path.join(scratch, "decisions")
    EV.RES = os.path.join(scratch, "results")
    cal = EV.uids(ds, roles=("induction",))
    ev = EV.uids(ds, roles=("validation",))
    X = ds
    labels = {}
    Q = RN.ImgSet(X, ev, "S", False)
    a = ST.fit_all_on(X, cal)
    log = ST.apply_all_on(Q, a["values"])
    EV._save_arm(X, "ALL_ON", Q.L, log)
    D, Q = RN.ImgSet(X, cal, "S", True), RN.ImgSet(X, ev, "S", False)
    r = RN.run_policy(list(grammar), D, Q)
    EV._save_arm(X, "CORA", Q.L, r["query_log"], {"ops": r["ops"], "query_stats": r["query_stats"]})
    EV._save_arm(X, "STRONG_NATIVE", {u: RN.lab(X, "S", u) for u in ev}, [])
    refs, ign = {}, {}
    for u in ev:
        refs[u], ign[u] = RN.refign(X, u)
    for arm in ("ALL_ON", "CORA"):
        judged, rec = EV._replay(X, arm, ev, refs, ign)
        print(arm, "edits judged (beneficial, harmful, neutral):", np.sum(list(judged.values()), axis=0).tolist())
    for arm in ("STRONG_NATIVE", "ALL_ON", "CORA"):
        lab = np.load(os.path.join(EV.DEC, X, f"{arm}.npz"))
        nr = npd = tp = 0
        for u in ev:
            pr = C.drop_ignored(lab[u], ign[u]) if ign[u] is not None and ign[u].any() else lab[u]
            c = C.counts(refs[u], pr)
            nr, npd, tp = nr + c["n_ref"], npd + c["n_pred"], tp + c["tp_at"][0]
        print(arm, "pooled F1 on validation parents", round(C.f1_of(nr, npd, tp), 4))
    print(json.dumps(r["ops"])[:800])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3:])
