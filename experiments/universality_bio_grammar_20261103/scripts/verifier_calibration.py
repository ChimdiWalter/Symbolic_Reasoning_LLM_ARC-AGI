"""Calibration-only check of neural proposals against U5's packet (INTERFACE.md section 4). numpy only.
Usage (inside the packet folder): python3 -I verifier_calibration.py proposals_<dataset>.json <dataset>
Each operator's proposals are verified on S's single-step unit tables by the section 10 rule (policy.py); the report
gives, per operator, the status and the number of calibration units accepted. It reads no held-out data."""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import policy as P   # noqa: E402  (a copy of U5's u5policy.py)


def load_units(ds, op, T):
    z = np.load(os.path.join(HERE, ds, f"units_{op}.npz"))
    u = {"parent": z["parent"], "feats": {}, "valid": {}, "cls": {}, "dTP": {}, "dN": {}, "conflicts": {}}
    for t in range(T):
        for k in ("feats", "valid", "cls", "dTP", "dN", "conflicts"):
            u[k][t] = z[f"{k}_t{t}"]
    return u


def main(path, ds):
    card = json.load(open(os.path.join(HERE, "grammar_card.json")))
    base = json.load(open(os.path.join(HERE, ds, "base.json")))
    prop = json.load(open(path))
    ops = {o["name"]: o for o in card["operators"]}
    report, bad = {}, 0
    for op in card["canonical_order"]:
        progs = []
        for p in prop.get("programs", []):
            if p.get("operator") != op:
                continue
            feats = ops[op]["features"]
            try:
                t = int(p["theta_index"])
                assert 0 <= t < len(ops[op]["theta_grid"])
                g = [(feats.index(f), c, float(q)) for f, c, q in p["guard"]]
                assert len(g) <= 2 and all(c in ("<", ">") for _, c, _ in g) and len({j for j, _, _ in g}) == len(g)
                progs.append((t, g))
            except Exception:                                # noqa: BLE001
                bad += 1
        if not progs:
            continue
        u = load_units(ds, op, len(ops[op]["theta_grid"]))
        sp = P.ProposedSpace(u, base["base_n_ref_n_pred_tp"], len(base["parents"]), progs[:2000])
        npar = len(set(u["parent"].tolist()))
        res = P.verify(sp, npar, u)
        report[op] = {"proposals": len(progs), "status": res["status"], "fit": int(res["fit"]),
                      "calibration_units_accepted": int(res["accepted"].sum())}
    print(json.dumps({"dataset": ds, "discarded_by_schema": bad, "operators": report}, indent=1))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
