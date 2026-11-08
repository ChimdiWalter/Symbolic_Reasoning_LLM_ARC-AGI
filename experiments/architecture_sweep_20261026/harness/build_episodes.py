"""Shared preparation job: episode states and one-step action outcomes for every split (resumable, SIGTERM-safe).

    python -m harness.build_episodes --out runs/episodes_v1 --stages S_train_syn S_select_syn S_train S_select ARC_eval_dev

Stages: synthetic splits (families x seeds x variants), real source splits (natural + verified-program variants;
labels = source test outputs), ARC_eval_dev (natural states only; NO labels in this process: the resulting attempts
of every action are written to reach_predictions.jsonl for the separate scorer's reachability audit).
A task already listed in <stage>.done.txt is skipped; shards flush every FLUSH tasks and on SIGTERM.
"""
import argparse
import json
import os
import signal
import sys
import time

from harness import actions as A
from harness import core as C
from harness import data as D
from harness import episodes as E
from harness import guard as GD
from harness import ledger as LG
from harness import paths as P

VARIANTS = ("natural", "correct", "corrupt1", "corrupt2", "wrongrep", "unrelated")
FLUSH = 10
TASK_CPU_S = {"syn": 60, "source": 60, "ARC_eval_dev": 120}
STOP = {"flag": False}


def _term(signum, frame):                                  # noqa: ARG001
    STOP["flag"] = True


def others_for(split_syn):
    out = []
    for fam in D.split_ids(split_syn):
        try:
            out.append(C.L.parse(D.family_program_text(fam)))
        except Exception:                                   # noqa: BLE001
            pass
    return out


def eval_reach_rows(task, out_f):
    """ARC_eval_dev: the natural state and the attempts every action would produce (no labels here)."""
    ctx = E.make_ctx(task)
    hyps, reserve = E.proposer(task, ctx)
    mem = E.initial_memory(hyps)
    ctx = E.make_ctx(task, [h.prog for h in mem])
    st = C.State(task, mem, reserve)
    beh = {h.qkey: h.preds for h in st.vs()}
    rows = []
    for act in st.available():
        s2, eff = A.apply(st, act, ctx)
        for h in s2.vs():
            beh.setdefault(h.qkey, h.preds)
        rows.append({"a": list(act), "attempts": s2.attempts, "n_exec": eff["n_exec"], "new_beh": eff["new_behaviour"]})
        # every new version-space behaviour (not only the attempts) is recorded: oracle coverage of the menu
    rec = {"task_id": task["task_id"], "state_hash": st.hash(), "n_hyp": len(mem), "n_vs": len(st.vs()),
           "base_attempts": st.attempts, "rows": rows, "behaviours": beh, "n_exec": ctx.n_req}
    out_f.write(json.dumps(rec) + "\n")
    out_f.flush()
    return st, ctx


def timeout(out, stage, tid):
    with P.open_allowed(os.path.join(out, stage, "timeouts.txt"), mode="a") as f:
        f.write(tid + "\n")


def run_stage(stage, out, seeds, limit=None):
    t0 = time.process_time()
    W = E.ShardWriter(os.path.join(out, stage), stage)
    n_tasks = n_states = 0
    pend = []
    if stage.endswith("_syn"):
        others = others_for(stage)
        work = [(fam, s) for fam in D.split_ids(stage) for s in range(seeds[stage])]
        for fam, s in work:
            tid = f"syn:{fam}#{s}"
            if tid in W.done or STOP["flag"]:
                continue
            r = D.synthetic_task(fam, s)
            if r is not None:
                task, truths, ptext = r
                ot = [p for p in others if C.L.render(p) != ptext]
                nb = len(W.buf)
                try:
                    with GD.cpu_limit(TASK_CPU_S["syn"]):
                        st = E.build_task(task, truths, ptext, ot, VARIANTS, E.seed_of(tid), W, stage, fam)
                    n_states += st["states"]
                except GD.TaskTimeout:
                    del W.buf[nb:]
                    timeout(out, stage, tid)
            pend.append(tid)
            n_tasks += 1
            if len(pend) >= FLUSH:
                W.flush(pend)
                pend = []
    elif stage in ("S_train", "S_select"):
        labels = D.source_labels(stage)
        others = others_for(stage + "_syn")
        for task in D.load_split(stage, limit):
            tid = task["task_id"]
            if tid in W.done or STOP["flag"]:
                continue
            truths = labels[tid]
            nb = len(W.buf)
            try:
                with GD.cpu_limit(TASK_CPU_S["source"]):
                    st = E.build_task(task, truths, None, others, VARIANTS, E.seed_of(tid), W, stage)
            except GD.TaskTimeout:
                del W.buf[nb:]
                timeout(out, stage, tid)
                pend.append(tid)
                continue
            n_states += st["states"]
            with P.open_allowed(os.path.join(out, stage, "pstar.jsonl"), mode="a") as f:
                f.write(json.dumps({"task_id": tid, "pstar": st["pstar"], "cpu": round(st["cpu"], 3),
                                    "n_exec": st["n_exec"]}) + "\n")
            pend.append(tid)
            n_tasks += 1
            if len(pend) >= FLUSH:
                W.flush(pend)
                pend = []
    elif stage == "ARC_eval_dev":
        os.makedirs(os.path.join(out, stage), exist_ok=True)
        with P.open_allowed(os.path.join(out, stage, "reach_predictions.jsonl"), mode="a") as f:
            for task in D.load_split(stage, limit):
                tid = task["task_id"]
                if tid in W.done or STOP["flag"]:
                    continue
                try:
                    with GD.cpu_limit(TASK_CPU_S["ARC_eval_dev"]):
                        st, _ = eval_reach_rows(task, f)
                except GD.TaskTimeout:
                    timeout(out, stage, tid)
                    pend.append(tid)
                    continue
                W.add({"state_id": f"{tid}|natural", "task_id": tid, "split": stage, "family": None,
                       "variant": "natural", "state_hash": st.hash(), "n_hyp": len(st.hyps), "n_vs": len(st.vs()),
                       "attempts": st.attempts, "has_pstar": None}, E.observation(st), {"base": None, "rows": None})
                pend.append(tid)
                n_tasks += 1
                n_states += 1
                if len(pend) >= FLUSH:
                    W.flush(pend)
                    pend = []
    W.flush(pend)
    LG.append({"run_id": f"episodes:{stage}", "family": "SHARED", "kind": "prep", "status": "STAGE",
               "tasks": n_tasks, "states": n_states, "cpu_h_stage": round((time.process_time() - t0) / 3600, 4),
               "interrupted": STOP["flag"]})
    return n_tasks, n_states


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--stages", nargs="+", required=True)
    ap.add_argument("--seeds_train_syn", type=int, default=8)
    ap.add_argument("--seeds_select_syn", type=int, default=4)
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    signal.signal(signal.SIGTERM, _term)
    out = a.out if os.path.isabs(a.out) else os.path.join(P.EXP, a.out)
    seeds = {"S_train_syn": a.seeds_train_syn, "S_select_syn": a.seeds_select_syn}
    for stage in a.stages:
        n = run_stage(stage, out, seeds, a.limit)
        print(stage, "tasks", n[0], "states", n[1], flush=True)
        if STOP["flag"]:
            sys.exit(3)


if __name__ == "__main__":
    main()
