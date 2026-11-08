"""Plumbing checks of the adapter (phase 1; no benchmark outcome is used).

    python -I run.py checks OUT_JSON

1. Probe grids: the plug-in's SIG_PROBES equal cgrow.episode.SIG_PROBES (the construction test's novelty probes).
2. Equivalence on the construction test's own world: this study's gates (validation cap, per-arm charge record) and
   plug-in, given the construction test's G0 (A2 minus compress, downscale, trim, upscale), its frozen controller
   records (runs/prep_v4/records.pkl) and its system tasks, rerun the three specification arms (S-hole, S-demo,
   S-shuffled) on its 11 motivating tasks for seeds 0, 1 and 2; every unit's promoted structure and recovery must
   equal the construction test's record (runs/s1_run/units.json). The validation cap (30) is above that world's
   pool (23 tasks), so it cannot bind there.
"""
import json
import os
import pickle
import sys

from ngrow import env as E, plugin as PL, grow as GR
from cgrow import selfext_core as C, schema as SG, lang0 as L0                   # noqa: E402

S1 = os.path.join(E.CGROW_DIR)


class S1G0Builder(PL.G0Builder):
    def __init__(self):
        rem = E.load(os.path.join(S1, "evaluator_only", "REMOVED.json"))["removed"]
        self.g = L0.build_g0(rem)
        self.sha = "s1-g0"


def correct(preds, outs):
    want = [tuple(tuple(r) for r in y) for y in outs]
    return bool(preds) and any([tuple(tuple(r) for r in g) for g in att] == want for att in preds)


def main(out_path):
    from cgrow import episode as EP                                             # loads the sandbox module (Athe only)
    probes_equal = [tuple(map(tuple, g)) for g in PL.SIG_PROBES] == [tuple(map(tuple, g)) for g in EP.SIG_PROBES]
    with open(os.path.join(S1, "runs", "prep_v4", "records.pkl"), "rb") as f:
        recs = pickle.load(f)
    sys_t = E.load(os.path.join(S1, "partitions", "TASKS_SYSTEM.json"))
    ev = E.load(os.path.join(S1, "evaluator_only", "TASKS_EVAL.json"))
    old = E.load(os.path.join(S1, "runs", "s1_run", "units.json"))
    tasks = {t: {"train": [(tuple(map(tuple, a)), tuple(map(tuple, b))) for a, b in v["train"]],
                 "test_inputs": [tuple(map(tuple, q)) for q in v["test_inputs"]]} for t, v in sys_t.items()}
    solved = [t for t, r in recs.items() if r["status"] == "solved"]
    pool = sorted([t for t, r in recs.items() if r["status"] != "solved"], key=lambda i: GR.h("pool:" + i))
    plug = PL.NaturalPlugin(S1G0Builder())
    G = GR.CappedGates(plug, tasks, solved, {t: recs[t]["base_preds"][0] for t in solved}, pool)
    G.solved_set = set(solved)
    tids = sorted([i for i, t in ev.items() if t["partition"] == "M" and recs[i]["decision"] == "INVENT_NEW_OPERATION"],
                  key=lambda i: (ev[i]["family"], ev[i]["template"], i))
    fams = sorted({t["family"] for t in ev.values() if t["family"]})
    mts = {f: sorted([i for i, t in ev.items() if t["family"] == f and t["partition"] == "M"],
                     key=lambda i: (ev[i]["template"], GR.h(i))) for f in fams}      # cgrow.s1.donors
    dn = {tid: mts[fams[(fi + 1) % len(fams)]][slot % len(mts[fams[(fi + 1) % len(fams)]])]
          for fi, f in enumerate(fams) for slot, tid in enumerate(mts[f])}
    rows, same = [], 0
    for s in (0, 1, 2):
        order = SG.seeded_order(s)
        for tid in tids:
            for arm in ("S-hole", "S-demo", "S-shuffled"):
                sk = recs[tid]["sketches"]
                if arm == "S-demo":
                    sk = [x for x in sk if x["form"] == "?(I)"]
                elif arm == "S-shuffled":
                    sk = recs[dn[tid]]["sketches"]
                res = C.run_spec_unit(G, tid, C.spec_candidates(plug, order, sk))
                o = old[f"{arm}|{tid}|{s}"]
                rec_new = any(r.get("fit") and correct(r.get("preds"), ev[tid]["test_outputs"]) for r in res["rows"])
                rec_old = any(r.get("fit") and correct(r.get("preds"), ev[tid]["test_outputs"]) for r in o["rows"])
                ok = rec_new == rec_old and res["promoted"] == o["promoted"] and res["retries"] == o["retries"]
                same += ok
                rows.append({"unit": f"{arm}|{tid}|{s}", "same": ok, "promoted_new": res["promoted"],
                             "promoted_old": o["promoted"], "recovered_new": rec_new, "recovered_old": rec_old})
                print(json.dumps(rows[-1]), flush=True)
    out = {"probe_grids_equal": probes_equal, "s1_world_spec_units_identical": [same, len(rows)], "rows": rows}
    E.dump(os.path.abspath(out_path), out)
    print(json.dumps({k: v for k, v in out.items() if k != "rows"}))


if __name__ == "__main__":
    main(*sys.argv[1:])
