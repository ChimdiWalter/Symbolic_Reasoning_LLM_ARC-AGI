"""Engineering check for U3: the domain-neutral core (cgrow/selfext_core.py) driven by a grid plug-in reruns S1's
arms on S1's frozen inputs and is compared unit by unit with S1's recorded outcomes (runs/s1_run/units.json).
Specification arms stop by a retry cap and must match exactly; S-enum stops on measured CPU (60 s charged), so its
outcomes may differ from S1's run and are reported separately.

    python -m cgrow.u3.s1_equivalence OUT_DIR
"""
import json
import os
import pickle
import sys

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, HERE)
from cgrow import paths as P, selfext_core as C, experiment as X, schema as SG, search as S     # noqa: E402
from cgrow import lang0 as L0, episode as EP, s1 as S1, evaluate as EV                           # noqa: E402
from a2 import arcdsl as D                                                                       # noqa: E402


class GridPlugin:
    BASE_BUDGET, BASE_CPU = S.BASE_BUDGET, S.BASE_CPU
    NOVELTY_BUDGET, NOVELTY_CPU = EP.DUP_BUDGET, 10.0
    PROBE_FACTOR = 4

    def __init__(self):
        self.b = X.G0Builder()
        self.probes = EP.SIG_PROBES[:12]

    def g0(self):
        return self.b()

    def with_structure(self, st):
        def fn(grid, *ints):
            if D.tag(grid) != "G":
                raise D.Bad("type")
            if st.param and (len(ints) != 1 or type(ints[0]) is not int or ints[0] not in SG.KS):
                raise D.Bad("param")
            out = st(grid, *ints)
            if out is None or not D.valid(out) or D.tag(out) != "G":
                raise D.Bad("undefined")
            return out
        g = self.g0()
        L0.add_production(g, "f:sig_" + st.sid.replace(":", "_"), fn, 1 if st.param else 0)
        return g

    def search(self, g, train, qs, budget, cpu_cap, want):
        return S.run(g, train, qs, budget=budget, cpu_cap=cpu_cap, want=want)

    @staticmethod
    def defined(v):
        return v is not None and D.valid(v)

    @staticmethod
    def same(a, b):
        return a == b

    structures = staticmethod(SG.structures)
    seeded_order = staticmethod(SG.seeded_order)

    @staticmethod
    def consistent(st, pairs):
        return SG.consistent(st, [(EP.grid(a), EP.grid(b)) for a, b in pairs])


def main(out_dir):
    out = os.path.join(P.HERE, out_dir)
    os.makedirs(out, exist_ok=True)
    ev, recs, tids = S1.motivating()
    dn = S1.donors(ev)
    units_s1 = X.load_json(os.path.join(P.RUNS, "s1_run", "units.json"))
    sys_t = X.system_tasks()
    tasks = {t: X.as_task(sys_t[t]) for t in sys_t}
    plug = GridPlugin()
    solved = [t for t, r in recs.items() if r["status"] == "solved"]
    G = C.Gates(plug, tasks, solved, {t: recs[t]["base_preds"][0] for t in solved},
                sorted([t for t, r in recs.items() if r["status"] != "solved"], key=lambda i: X.h("pool:" + i)))
    rows, match = [], {"spec": [0, 0], "enum": [0, 0]}
    for s in S1.SEEDS:
        order = SG.seeded_order(s)
        for tid in tids:
            for arm in S1.ARMS:
                old = units_s1[f"{arm}|{tid}|{s}"]
                if arm == "S-enum":
                    res = C.run_enum_unit(G, tid, order)
                else:
                    sk, o = recs[tid]["sketches"], order
                    if arm == "S-demo":
                        sk = [x for x in sk if x["form"] == "?(I)"]
                    elif arm == "S-shuffled":
                        sk = recs[dn[tid]]["sketches"]
                    elif arm == "S1F" and old.get("form") and old["form"]["family"] in S1.FAMILY_OF:
                        fam, prm = S1.FAMILY_OF[old["form"]["family"]], old["form"]["param"]
                        o = [x for x in order if x.family == fam and x.param == prm] + \
                            [x for x in order if not (x.family == fam and x.param == prm)]
                    res = C.run_spec_unit(G, tid, C.spec_candidates(plug, o, sk))
                rec_new = any(r.get("fit") and EV.correct(r.get("preds"), ev[tid]["test_outputs"]) for r in res["rows"])
                rec_old = any(r.get("fit") and EV.correct(r.get("preds"), ev[tid]["test_outputs"]) for r in old["rows"])
                same = rec_new == rec_old and res["promoted"] == old["promoted"]
                k = "enum" if arm == "S-enum" else "spec"
                match[k][0] += same
                match[k][1] += 1
                rows.append({"unit": f"{arm}|{tid}|{s}", "same": same, "promoted_old": old["promoted"],
                             "promoted_new": res["promoted"], "retries_old": old["retries"],
                             "retries_new": res["retries"]})
                print(json.dumps(rows[-1]), flush=True)
    summ = {"spec_arms_units_matching": match["spec"], "s_enum_units_matching": match["enum"],
            "note": "specification arms must match exactly; S-enum stops on measured CPU and may differ"}
    with P.open_write(os.path.join(out, "equivalence.json")) as f:
        json.dump({"summary": summ, "rows": rows}, f, indent=1)
    print(json.dumps(summ), flush=True)


if __name__ == "__main__":
    main(sys.argv[1])
