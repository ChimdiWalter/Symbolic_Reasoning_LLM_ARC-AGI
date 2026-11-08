"""Reuse of the grown grammar on the SOURCE half (scorer side: opens source test outputs only).

    python -I run.py reuse OUT_DIR BENCH

The grown grammar G0 + registry (OUT_DIR/<BENCH>/registry.json) is run with the base search (150,000 executions,
20 CPU-s, two attempts) on every source task of the benchmark; G0's own answers come from the controller's records
(the same search). A task is FIT when a program reproduces every demonstration; a test output is CORRECT when
either attempt equals it (pass@2). Reports per task and in summary: fit and correct under G0 and under the grown
grammar, the tasks newly fit, newly correct and lost, and the CPU of the grown searches. With an empty registry
the grown grammar is G0 and nothing is searched again. Writes OUT_DIR/<BENCH>/reuse.json.
"""
import json
import os
import sys
import time

from objgrow import env as E, edits as ED, gates as GT, grow as GR
from ngrow import data as DT, plugin as PL, score as SC
from a2 import arcdsl as D                                                       # noqa: F401


def main(out_dir, bench):
    out_dir = os.path.abspath(out_dir)
    bdir = os.path.join(out_dir, bench)
    reg = E.load(os.path.join(bdir, "registry.json"))
    ops = [ED.ObjOp.from_json(reg["ops"][s]) for s in reg["registry"]]
    W = GR.setup(bench)
    recs, tasks = W["recs"], W["tasks"]
    ids = [t for b, f, t in DT.half("source", (bench,))]
    # in-sample tasks: the motivating task and the first validating task of every registry operation
    units = GR.load_units(bdir)
    in_sample = set()
    for tid, u in units.items():
        for row in u.get("rows", []):
            if row.get("promotion") == "promoted" and row["sid"] in reg["registry"]:
                in_sample.add(tid)
                first = (row.get("validation") or {}).get("first_new_fit")
                if first:
                    in_sample.add(first["task"])
    sol = SC.solutions(bench, ids)
    g0b = PL.G0Builder()
    plug = GT.ObjPlugin(g0b, ops)
    g = plug.g0()
    rows, t_all = {}, 0.0
    for tid in ids:
        r0 = recs[tid]["record"]
        base = SC.score_row(GR.as_preds(r0["base_preds"]) if r0["base"]["fit"] else None, sol[tid])
        row = {"family": recs[tid]["family"], "n_outputs": len(sol[tid]), "g0_fit": r0["base"]["fit"],
               "g0_correct": base["correct"], "g0_program": r0["base"]["program"]}
        if ops:
            t = tasks[tid]
            r = plug.search(g, t["train"], t["test_inputs"], plug.BASE_BUDGET, plug.BASE_CPU, 2)
            t_all += r["cpu_s"]
            sc = SC.score_row(r["preds"] if r["fit"] else None, sol[tid])
            row.update(grown_fit=r["fit"], grown_correct=sc["correct"], grown_program=r["program"],
                       grown_cpu_s=r["cpu_s"], grown_uses_op=bool(r["program"] and "obj_" in r["program"]),
                       grown_stop=r["stop"])
        else:
            row.update(grown_fit=r0["base"]["fit"], grown_correct=base["correct"], grown_program=r0["base"]["program"],
                       grown_cpu_s=0.0, grown_uses_op=False, grown_stop=None)
        row["in_sample"] = tid in in_sample
        rows[tid] = row
    summ = {"bench": bench, "tasks": len(ids), "outputs": sum(len(sol[t]) for t in ids), "registry": reg["registry"],
            "g0_tasks_fit": sum(r["g0_fit"] for r in rows.values()),
            "g0_tasks_correct_all_outputs": sum(r["g0_correct"] == r["n_outputs"] for r in rows.values()),
            "g0_outputs_correct": sum(r["g0_correct"] for r in rows.values()),
            "grown_tasks_fit": sum(r["grown_fit"] for r in rows.values()),
            "grown_tasks_correct_all_outputs": sum(r["grown_correct"] == r["n_outputs"] for r in rows.values()),
            "grown_outputs_correct": sum(r["grown_correct"] for r in rows.values()),
            "newly_fit": sorted(t for t, r in rows.items() if r["grown_fit"] and not r["g0_fit"]),
            "newly_correct_tasks": sorted(t for t, r in rows.items()
                                          if r["grown_correct"] == r["n_outputs"] and r["g0_correct"] < r["n_outputs"]),
            "lost_fit": sorted(t for t, r in rows.items() if r["g0_fit"] and not r["grown_fit"]),
            "lost_correct_outputs": sum(max(0, r["g0_correct"] - r["grown_correct"]) for r in rows.values()),
            "tasks_using_an_op": sorted(t for t, r in rows.items() if r["grown_uses_op"]),
            "grown_search_cpu_s": round(t_all, 2)}
    by_fam = {}
    held_sizes = {f: len(v["held"]) for f, v in DT.split()["benchmarks"][bench]["families"].items()}
    for t, r in rows.items():
        f = by_fam.setdefault(r["family"], {"tasks": 0, "g0_fit": 0, "grown_fit": 0, "g0_correct_outputs": 0,
                                             "grown_correct_outputs": 0, "out_of_sample_tasks": 0,
                                             "out_of_sample_newly_correct": 0, "held_tasks": held_sizes.get(r["family"], 0)})
        f["tasks"] += 1
        f["g0_fit"] += r["g0_fit"]
        f["grown_fit"] += r["grown_fit"]
        f["g0_correct_outputs"] += r["g0_correct"]
        f["grown_correct_outputs"] += r["grown_correct"]
        if not r["in_sample"]:
            f["out_of_sample_tasks"] += 1
            f["out_of_sample_newly_correct"] += (r["grown_correct"] == r["n_outputs"] and r["g0_correct"] < r["n_outputs"])
    # the held-half expectation: each family's out-of-sample newly-correct rate times its held size (reuse only)
    exp = 0.0
    for f, v in by_fam.items():
        if v["out_of_sample_tasks"]:
            v["expected_held_newly_correct"] = round(v["out_of_sample_newly_correct"] / v["out_of_sample_tasks"]
                                                     * v["held_tasks"], 2)
            exp += v["expected_held_newly_correct"]
    summ["in_sample_tasks"] = sorted(in_sample)
    summ["out_of_sample_newly_correct_tasks"] = sorted(t for t, r in rows.items() if not r["in_sample"] and
                                                       r["grown_correct"] == r["n_outputs"] and r["g0_correct"] < r["n_outputs"])
    summ["expected_held_newly_correct_tasks"] = round(exp, 1)
    summ["held_tasks"] = sum(held_sizes.values())
    E.dump(os.path.join(bdir, "reuse.json"), {"summary": summ, "by_family": by_fam, "tasks": rows})
    print(json.dumps(summ))


if __name__ == "__main__":
    main(*sys.argv[1:])
