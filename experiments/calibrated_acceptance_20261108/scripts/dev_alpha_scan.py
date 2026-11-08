"""DEVELOPMENT ONLY (NuInsSeg calibration organs; no fresh image): the calibrated rule's certification for every one
of the 11 operators, alone on the starting segmentation of the 12 calibration organs, at several settings.
    dev_alpha_scan.py v1      the first version's semantics (in-fold limit = bound = a; bootstrap bounds at 0.05/3)
                              -> development/ALPHA_SCAN.json
    dev_alpha_scan.py final   the final rule (in-fold limit a; bound 0.60; organ-clustered t bounds at 0.05)
                              -> development/LAMBDA_SCAN_FINAL.json
<python environment>: python -I -B scripts/dev_alpha_scan.py MODE"""
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import caharness as H   # noqa: E402
import calrule as CR    # noqa: E402
import u5core as C      # noqa: E402
import u5policy as P    # noqa: E402
import u5run as RN      # noqa: E402

ALPHAS = (0.2, 0.3, 0.4, 0.5, 0.6, 0.75, 1.0)
MODE = sys.argv[1] if len(sys.argv) > 1 else "v1"


def main():
    t0 = time.process_time()
    D = CR.ImageParents(H.DS, H.cal_uids(), "S", True)
    organs = sorted(set(D.organ.values()))
    oi = {o: i for i, o in enumerate(organs)}
    org_idx = np.array([oi[D.organ[u]] for u in D.parents], int)
    out = {"label": "DEVELOPMENT: each operator alone on STRONG_NATIVE of the 12 NuInsSeg calibration organs "
                    "(236 images); level 0.05/3 one-sided", "alphas": list(ALPHAS), "operators": {}}
    for op in C.OPS:
        du = RN.set_units(D, op)
        if not len(du["keys"]):
            out["operators"][op] = {"units": 0}
            continue
        sp = P.Space(du, D.base(), len(D.parents))
        A, Hm, Bf = CR.judged_sums(sp, du)
        G = sp.pooled_gain(np.ones(sp.P, bool))
        ok = (A.sum(1) > 0) & ~sp.conflicted & (G > 1e-12)
        best = int(np.argmax(np.where(ok, G, -np.inf))) if ok.any() else None
        rec = {"units": len(du["keys"]), "programs": len(sp.progs),
               "best_in_sample": None if best is None else
               {"pooled_gain": float(G[best]), "accepted": int(A[best].sum()), "harmful": int(Hm[best].sum()),
                "beneficial": int(Bf[best].sum())}, "by_alpha": {}}
        for a in ALPHAS:
            if MODE == "v1":     # the first version: one value as in-fold limit and bound; bootstrap at 0.05 / 3
                r, final = CR.calibrate_op(sp, A, Hm, Bf, org_idx, len(organs), 3, alpha=a, lam=a,
                                           bounds_kind="bootstrap", level=CR.FWER / 3)
            else:                # the final version: in-fold limit a, bound 0.60, organ-clustered t bounds at 0.05
                r, final = CR.calibrate_op(sp, A, Hm, Bf, org_idx, len(organs), 3, alpha=CR.ALPHA, lam=a)
            rec["by_alpha"][str(a)] = {k: r[k] for k in ("status", "mean_gain", "lcb_gain", "harmful_rate",
                                                          "ucb_harmful_rate", "out_of_fold")}
        out["operators"][op] = rec
        print(op, {a: (v["status"], round(v["mean_gain"], 5), round(v["lcb_gain"], 5), v["harmful_rate"],
                       v["ucb_harmful_rate"], v["out_of_fold"]["accepted"]) for a, v in rec["by_alpha"].items()},
              flush=True)
    out["cpu_s"] = round(time.process_time() - t0, 1)
    out["mode"] = MODE
    H.jdump(out, os.path.join(H.ROOT, "development", "ALPHA_SCAN.json" if MODE == "v1" else "LAMBDA_SCAN_FINAL.json"))


if __name__ == "__main__":
    main()
