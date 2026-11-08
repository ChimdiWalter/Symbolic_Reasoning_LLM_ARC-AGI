"""Test I-b (PROTOCOL_TEST_IB.md): more seeds, sketch ablation C5n, matched search C7m, parametric merge.

    python -m cgrow.testib prep RUN_ID SRC_PREP        plan + generation jobs (records copied from SRC_PREP)
    python -m cgrow.testib process RUN_ID PREP GEN      invention episodes, registries registry/testIb_<arm>.json
    python -m cgrow.testib c7m RUN_ID PREP              matched G0 search, 150 CPU-s per motivating task
    python -m cgrow.testib merge RUN_ID PREP PROC       parametric merge over each arm's Test I + I-b memory
    python -m cgrow.testib evaluate RUN_ID ...          evaluator scoring, tables, reports/TEST_IB_REPORT.md
"""
import json
import os
import pickle
import shutil
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from cgrow import paths as P, experiment as X, naming as NM, prompts as PM     # noqa: E402

SEEDS = (2, 3, 4)
ARMS = ("C2", "C5", "C5n", "C3")


def prep(run_id, src_prep):
    rdir = os.path.join(P.RUNS, run_id)
    os.makedirs(rdir, exist_ok=True)
    P.check_write(os.path.join(rdir, "records.pkl"))
    shutil.copyfile(os.path.join(P.RUNS, src_prep, "records.pkl"), os.path.join(rdir, "records.pkl"))
    with open(os.path.join(rdir, "records.pkl"), "rb") as f:
        recs = pickle.load(f)
    g0b = X.G0Builder()
    sys_t = X.system_tasks()
    ev = X.eval_tasks()
    fams = sorted({t["family"] for t in ev.values() if t["family"]})
    mts = {f: sorted([i for i, t in ev.items() if t["family"] == f and t["partition"] == "M"],
                     key=lambda i: (ev[i]["template"], X.h(i))) for f in fams}
    names = {s: NM.Names(g0b.g, s) for s in SEEDS}
    plan, jobs = [], []
    for s in SEEDS:
        for fi, f in enumerate(fams):
            for slot, tid in enumerate(mts[f]):
                donor_f = fams[(fi + 1) % len(fams)]
                donor = mts[donor_f][slot % len(mts[donor_f])]
                for arm in ARMS:
                    ep = f"{arm}_{tid}_s{s}"
                    plan.append({"episode": ep, "arm": arm, "task": tid, "seed": s,
                                 "donor": donor if arm == "C3" else None, "controller_decision": recs[tid]["decision"]})
                    if recs[tid]["decision"] != "INVENT_NEW_OPERATION":
                        continue
                    failure = {"C2": None, "C3": recs[donor], "C5": recs[tid], "C5n": recs[tid]}[arm]
                    msgs = PM.invent_messages(X.as_task(sys_t[tid]), names[s], g0b.g, failure,
                                              sketches=(arm != "C5n"))
                    jobs.append({"job_id": ep, "messages": msgs, "n": X.K, "max_new": X.MAX_NEW,
                                 "temperature": X.TEMP, "top_p": X.TOP_P, "seed": X.seed_of(tid, s)})
    with P.open_write(os.path.join(rdir, "plan.json")) as f:
        json.dump({"plan": plan, "g0_sha256": g0b.sha, "seeds": SEEDS, "arms": ARMS, "K": X.K, "max_new": X.MAX_NEW,
                   "temperature": X.TEMP, "top_p": X.TOP_P,
                   "names_sha256": {s: X.h(json.dumps(names[s].code, sort_keys=True)) for s in SEEDS}}, f, indent=1)
    with P.open_write(os.path.join(rdir, "jobs.jsonl")) as f:
        for j in jobs:
            f.write(json.dumps(j) + "\n")
    print(json.dumps({"jobs": len(jobs), "plan_rows": len(plan)}), flush=True)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "prep":
        prep(sys.argv[2], sys.argv[3])
    else:
        import cgrow.testib_rest as R                       # noqa: E402  (written after the freeze)
        getattr(R, cmd)(*sys.argv[2:])
