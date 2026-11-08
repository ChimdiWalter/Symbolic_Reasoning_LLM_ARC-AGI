"""Development check on ARC training tasks: the constructor on a seeded sample of the project's S_train split.

    python -I run.py arctrain OUT_DIR [--n N] [--retry]

S_train is the project's training split of the pinned ARC-AGI-2 public training file (harness/data.py; the sealed
confirmation split is never touched). The sample is the first N tasks in sha256("arctrain:" + id) order. Per task:
G0's base search (150,000 executions, 20 CPU-s, as the controller); on a failure, the controller's typed holes
(cgrow.controller.sketches: identity plus the two best invertible decompositions) and the object-level constructor
on each. With --retry, every leave-one-out candidate (at most 3 per task, as the gates' retry cap) is tried by the
base search with G0 plus the operation, and its two attempts are scored against the task's test outputs (the
training labels, scorer side). No promotion, no registry: this is a development reading of the constructor on
ARC-style tasks, not an experiment arm. Writes OUT_DIR/arctrain.json (resumable).
"""
import hashlib
import json
import os
import sys
import time

from objgrow import env as E, construct as CS, edits as ED, gates as GT, grow as GR
from ngrow import plugin as PL, score as SC
from cgrow import controller as CT, search as S
from harness import data as HD
from a2 import arcdsl as D


def main(out_dir, *rest):
    n, retry = 60, False
    it = iter(rest)
    for a in it:
        if a == "--n":
            n = int(next(it))
        elif a == "--retry":
            retry = True
    out_dir = os.path.abspath(out_dir)
    path = os.path.join(out_dir, "arctrain.json")
    done = E.load(path) if os.path.exists(path) else {}
    ids = sorted(HD.split_ids("S_train"), key=lambda t: hashlib.sha256(("arctrain:" + t).encode()).hexdigest())[:n]
    labels = HD.source_labels("S_train")
    g0b = PL.G0Builder()
    plug = GT.ObjPlugin(g0b)
    fns = D.guarded(D.load()[0])
    for tid in ids:
        if tid in done:
            continue
        rec = HD.task_record(tid, "S_train")
        task = {"train": [(E.grid(a), E.grid(b)) for a, b in rec["train"]],
                "test_inputs": [E.grid(q) for q in rec["test_inputs"]]}
        outs = [E.grid(y) for y in labels[tid]]
        t0 = time.process_time()
        g = g0b()
        base = S.run(g, task["train"], task["test_inputs"], budget=S.BASE_BUDGET, cpu_cap=S.BASE_CPU)
        row = {"task": tid, "n_demos": len(task["train"]), "base_fit": base["fit"], "base_cpu_s": base["cpu_s"],
               "base_correct": SC.score_row(base["preds"] if base["fit"] else None, outs)["correct"],
               "n_outputs": len(outs)}
        if not base["fit"]:
            sks, _ = CT.sketches(task["train"], g)
            skd = [{"form": c["form"], "outer": c["outer"], "inner": c["inner"], "score": c["score"],
                    "pairs": c["pairs"]} for c in sks]
            con = GR.construct_unit({"sketches": skd}, task, fns)
            row.update(holes=[{k: v for k, v in h.items() if k != "views"} for h in con["holes"]],
                       counts=con["counts"], construction_cpu_s=con["construction_cpu_s"],
                       n_candidates=len(con["candidates"]),
                       n_candidates_loo=sum(1 for c in con["candidates"] if c["loo"]),
                       correspondence=any(h["correspondence"] for h in con["holes"]),
                       correspondence_partial=any(h["correspondence_partial"] for h in con["holes"]))
            if retry:
                rows = []
                for c in [c for c in con["candidates"] if c["loo"]][:GT.M_RETRIES]:
                    op = c["op"]
                    r = plug.search(plug.with_structure(op), task["train"], task["test_inputs"], plug.BASE_BUDGET,
                                    plug.BASE_CPU, 2)
                    sc = SC.score_row(r["preds"] if r["fit"] else None, outs)
                    rows.append({"sid": op.sid, "expr": op.expr(), "fit": r["fit"], "program": r["program"],
                                 "correct": sc["correct"], "cpu_s": r["cpu_s"], "hole_rank": c["hole_rank"]})
                row["retries"] = rows
                row["recovered"] = any(x["fit"] and x["correct"] == len(outs) for x in rows)
        row["process_cpu_s"] = round(time.process_time() - t0, 3)
        done[tid] = row
        E.dump(path, done)
        print(json.dumps({k: row.get(k) for k in ("task", "base_fit", "n_candidates", "n_candidates_loo",
                                                   "recovered", "process_cpu_s")}), flush=True)
    rows = list(done.values())
    fails = [r for r in rows if not r["base_fit"]]
    summ = {"sampled": len(rows), "g0_fit": sum(r["base_fit"] for r in rows),
            "g0_correct_all_outputs": sum(r["base_correct"] == r["n_outputs"] for r in rows),
            "failures": len(fails), "correspondence": sum(bool(r.get("correspondence")) for r in fails),
            "correspondence_partial": sum(bool(r.get("correspondence_partial")) for r in fails),
            "verified": sum(r.get("n_candidates", 0) > 0 for r in fails),
            "loo": sum(r.get("n_candidates_loo", 0) > 0 for r in fails),
            "retried": sum(1 for r in fails if r.get("retries")),
            "retry_fit": sum(any(x["fit"] for x in r.get("retries", [])) for r in fails),
            "recovered_correct": sum(bool(r.get("recovered")) for r in fails),
            "cpu_s": round(sum(r["process_cpu_s"] for r in rows), 1)}
    E.dump(os.path.join(out_dir, "arctrain_summary.json"), summ)
    print(json.dumps(summ))


if __name__ == "__main__":
    main(*sys.argv[1:])
