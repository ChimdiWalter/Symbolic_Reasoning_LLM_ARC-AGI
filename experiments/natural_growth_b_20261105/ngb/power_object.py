"""The honest expectation for the object arms (5 and 7), from the builder's source-half records only (amendment 2).

    python -I run.py power_object OUT_JSON

Reuse (arm 5): per family, the builder's out-of-sample newly-correct rate on the source half (tasks that were neither
the motivating nor the validating task of a promoted operation) times the held family size; families with no
out-of-sample source task (one operation fits every source task of the family) have no estimate and are reported as
such, with their held sizes. Construction (arm 7): per family, the builder's recovery rate on the source half
(units recovered with every test output correct over construction units; the retried candidates are exact on all
demonstrations and accepted by the declared proposal heuristic) times the held family size;
over-fitting is already in that rate (a fitting candidate that mispredicts counts as not recovered).
Matched static search at the object allowance (about 15 to 80 CPU-s per held task): its gains are unknown beyond the
4x search (23 1D-ARC tasks, 4 ConceptARC); two scenarios are simulated for arm 5 vs arm 4b: static gains equal to
the 4x search's (lower bound) and static re-solving the same families as reuse does (pessimistic for growth). Each
reuse simulation is run twice (amendment 3): with the four 1D-ARC families that have no out-of-sample estimate at
zero, and with them transferring at their source-half rate of correct tasks under the grown grammar.
A third static scenario (amendment 3, after the Kaggle rehearsal): matched static search's correct tasks on the
source half at the corrected allowances, measured by rehearsal 2's report (`checks/kaggle_rehearsal/
REHEARSAL_2_RESULTS.json`), per family, minus G0's, as the estimate of its held newly-correct tasks. Static search
uses no source solution, so its source-half rate estimates its held rate; reuse's source-half figures from the
rehearsal are in-sample and are not used.
Decisions are simulated as in ngb/power.py (Poisson draws per family, the pre-registered comparison with a reduced
bootstrap).
"""
import json
import os
import random
import sys

from ngb import env as E, power as PW, object_arm as OA
from ngrow import data as DT, analysis as AN

FEAS_A = os.path.join(E.STUDY_A, "feasibility", "FEASIBILITY.json")
REH2 = os.path.join(E.STUDY, "checks", "kaggle_rehearsal", "REHEARSAL_2_RESULTS.json")


def static_measured():
    """{(bench, family): (static_obj correct outputs, G0 correct outputs, tasks, outputs per task)} on the source
    half, from rehearsal 2's report (correct outputs per family; outputs per task per benchmark from its totals)."""
    res = E.load(REH2)
    bf, tb = res["descriptive"]["by_family"], res["totals_by_benchmark"]
    opt = {b: v["G0"]["outputs"] / v["G0"]["tasks"] for b, v in tb.items()}
    return {tuple(k.split("/", 1)): (v["correct_static_obj"], bf["obj_vs_G0"][k]["correct_G0"], v["tasks"],
                                     opt[k.split("/", 1)[0]])
            for k, v in bf["obj_vs_static_obj"].items()}


def main(out_path):
    sp = DT.split()
    fa = E.load(FEAS_A)["benchmarks"]
    per, lam_reuse, lam_reuse_static_4x, lam_reuse_static_same, lam_construct = [], {}, {}, {}, {}
    lam_reuse_t, lam_reuse_static_4x_t = {}, {}
    meas = static_measured()
    lam_reuse_static_m, lam_reuse_static_m_t = {}, {}
    unmeasured = []
    for b in DT.BENCHMARKS:
        reuse = E.load(os.path.join(E.REPO, OA.spec()["folder"], "runs", "v2", b, "reuse.json"))["by_family"]
        funnel = E.load(os.path.join(E.REPO, OA.spec()["folder"], "runs", "v2", "FUNNEL.json"))[b]["by_family"]
        for f, r in sp["benchmarks"][b]["families"].items():
            held, src = len(r["held"]), len(r["source"])
            rf = reuse.get(f, {})
            oos_t, oos_c = rf.get("out_of_sample_tasks", 0), rf.get("out_of_sample_newly_correct", 0)
            if oos_t:
                e_reuse = oos_c / oos_t * held
            else:
                e_reuse = None
                unmeasured.append({"bench": b, "family": f, "held_tasks": held,
                                   "source_grown_fit": rf.get("grown_fit"), "source_tasks": rf.get("tasks")})
            fu = funnel.get(f, {})
            units = fu.get("units", 0)
            e_con = fu.get("recovered_correct", 0) / units * held if units else 0.0
            x4 = sum(fa[b]["tasks"][t]["x4_correct"] > 0 and not fa[b]["tasks"][t]["base_fit"] for t in r["source"])
            e_static_4x = x4 / max(1, src) * held
            per.append({"bench": b, "family": f, "held_tasks": held, "source_tasks": src,
                        "reuse_out_of_sample_tasks": oos_t, "reuse_out_of_sample_newly_correct": oos_c,
                        "expected_held_reuse_newly_correct": None if e_reuse is None else round(e_reuse, 2),
                        "construction_units": units, "construction_recovered_correct": fu.get("recovered_correct", 0),
                        "expected_held_construction_correct": round(e_con, 2),
                        "expected_held_static_4x_correct": round(e_static_4x, 2)})
            er = e_reuse or 0.0
            # transfer scenario: a family without an out-of-sample source task transfers at its source-half rate of
            # correct tasks under the grown grammar (amendment 3)
            et = e_reuse if e_reuse is not None else \
                rf.get("grown_correct_outputs", 0) / max(1, rf.get("tasks", 1)) * held
            per[-1]["expected_held_reuse_if_unmeasured_transfer"] = round(et, 2)
            lam_reuse[(b, f)] = (er, 0.0)
            lam_reuse_static_4x[(b, f)] = (max(0.0, er - e_static_4x), max(0.0, e_static_4x - er))
            lam_reuse_t[(b, f)] = (et, 0.0)
            lam_reuse_static_4x_t[(b, f)] = (max(0.0, et - e_static_4x), max(0.0, e_static_4x - et))
            lam_reuse_static_same[(b, f)] = (0.0, 0.0)
            sc, g0c, n, opt = meas[(b, f)]
            e_static_m = max(0, sc - g0c) / opt / max(1, n) * held          # held tasks newly correct (task units)
            per[-1]["source_static_obj_correct"], per[-1]["source_G0_correct"] = sc, g0c
            per[-1]["expected_held_static_measured_newly_correct"] = round(e_static_m, 2)
            lam_reuse_static_m[(b, f)] = (max(0.0, er - e_static_m), max(0.0, e_static_m - er))
            lam_reuse_static_m_t[(b, f)] = (max(0.0, et - e_static_m), max(0.0, e_static_m - et))
            lam_construct[(b, f)] = (e_con, 0.0)
    held_sizes = {(r["bench"], r["family"]): r["held_tasks"] for r in per}
    rng = random.Random(20261106)
    sims = {}
    for name, lams in (("reuse_vs_G0", lam_reuse), ("reuse_vs_static_at_4x_gains", lam_reuse_static_4x),
                       ("reuse_vs_G0_if_unmeasured_transfer", lam_reuse_t),
                       ("reuse_vs_static_at_4x_gains_if_unmeasured_transfer", lam_reuse_static_4x_t),
                       ("reuse_vs_static_same_families", lam_reuse_static_same),
                       ("reuse_vs_static_measured_on_source", lam_reuse_static_m),
                       ("reuse_vs_static_measured_on_source_if_unmeasured_transfer", lam_reuse_static_m_t),
                       ("construction_vs_G0", lam_construct)):
        dec = {}
        for _ in range(PW.SIMS):
            d = PW.simulate(lams, held_sizes, rng)["decision"]
            dec[d] = dec.get(d, 0) + 1
        sims[name] = {k: round(v / PW.SIMS, 3) for k, v in dec.items()}
    out = {"per_family": per, "unmeasured_families": unmeasured,
           "expected_held_reuse_newly_correct_measured_families": round(sum(v[0] for v in lam_reuse.values()), 1),
           "unmeasured_held_tasks": sum(u["held_tasks"] for u in unmeasured),
           "expected_held_reuse_newly_correct_if_unmeasured_transfer": round(sum(v[0] for v in lam_reuse_t.values()), 1),
           "expected_held_construction_correct": round(sum(v[0] for v in lam_construct.values()), 1),
           "expected_held_static_4x_correct": round(sum(r["expected_held_static_4x_correct"] for r in per), 1),
           "expected_held_static_measured_newly_correct":
               round(sum(r["expected_held_static_measured_newly_correct"] for r in per), 1),
           "static_measured_from": os.path.relpath(REH2, E.STUDY),
           "simulated_decisions": sims, "simulations": PW.SIMS, "bootstrap_draws_in_simulation": PW.BOOT,
           "source_cost_cpu_s": {b: round(OA.source_cost(b), 1) for b in DT.BENCHMARKS},
           "registry_sizes": {b: len(OA.ops(b)) for b in DT.BENCHMARKS},
           "shuffled_registry": {b: OA.shuffled_ops(b)[1] for b in DT.BENCHMARKS}}
    E.dump(os.path.abspath(out_path), out)
    print(json.dumps({k: v for k, v in out.items() if k != "per_family"}, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:])
