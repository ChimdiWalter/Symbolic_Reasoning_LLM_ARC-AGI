"""Test I orchestration. Each phase is resumable and writes under runs/<RUN_ID>/.

    python -m cgrow.experiment prep RUN_ID              controller on every system task under G0 (C0), plan, jobs
    python -m cgrow.proposer generate JOBS OUT          (GPU) proposals and C1 programs
    python -m cgrow.experiment process RUN_ID PREP GEN  invention episodes (system side), C1 round 1, C1 repair jobs

Roles. The harness plays the evaluator when it builds G0 from evaluator_only/REMOVED.json and when it picks the
motivating tasks and C3 donors from evaluator_only/TASKS_EVAL.json; everything passed to the controller, the
prompts and the episode code is system-visible: demonstrations, query inputs, the built grammar, search traces.
Arms: C2 failure-blind (puzzle only), C3 shuffled (another family's motivating task's failure report), C5 the
task's own failure report. Same model, prompt template, K, token cap, temperature, top-p and sampling seeds.
"""
import copy
import hashlib
import json
import os
import pickle
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from cgrow import paths as P, lang0 as L0, controller as CT, naming as NM, prompts as PM   # noqa: E402
from cgrow import invent as IV, episode as EP, registry as RG                              # noqa: E402

SEEDS = (0, 1)
ARMS = ("C2", "C3", "C5")
K = 4
K_C1 = 3
MAX_NEW = 640
TEMP, TOP_P = 0.8, 0.95


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def h(s):
    return hashlib.sha256(s.encode()).hexdigest()


def seed_of(*parts):
    return int(h("|".join(map(str, parts)))[:8], 16) & 0x7FFFFFFF


class G0Builder:
    """Builds G0 once (evaluator role) and hands out independent copies (system side adds productions)."""

    def __init__(self):
        rem = load_json(os.path.join(P.EVALUATOR_DIR, "REMOVED.json"))["removed"]
        self.g = L0.build_g0(rem)
        self.sha = h(json.dumps(sorted(p.head for p in self.g.prods)) + json.dumps(sorted(self.g.fn_leaves)))

    def __call__(self):
        g = copy.copy(self.g)
        g.prods, g.costs = list(self.g.prods), dict(self.g.costs)
        return g


def system_tasks():
    return load_json(os.path.join(P.PARTITIONS, "TASKS_SYSTEM.json"))


def eval_tasks():
    return load_json(os.path.join(P.EVALUATOR_DIR, "TASKS_EVAL.json"))


def as_task(t):
    return {"train": [(EP.grid(a), EP.grid(b)) for a, b in t["train"]],
            "test_inputs": [EP.grid(q) for q in t["test_inputs"]]}


# ------------------------------------------------------------------ prep
def prep(run_id):
    rdir = os.path.join(P.RUNS, run_id)
    g0b = G0Builder()
    sys_t = system_tasks()
    ev = eval_tasks()
    rec_path = os.path.join(rdir, "records.pkl")
    recs = {}
    if os.path.exists(rec_path):
        with open(rec_path, "rb") as f:
            recs = pickle.load(f)
    for tid in sorted(sys_t):
        if tid in recs:
            continue
        recs[tid] = CT.analyze(as_task(sys_t[tid]), g0b())
        print(json.dumps({"task": tid, "status": recs[tid]["status"], "decision": recs[tid]["decision"],
                          "cpu_s": recs[tid].get("cpu_s", recs[tid]["base"]["cpu_s"])}), flush=True)
        P.check_write(rec_path)
        with open(rec_path, "wb") as f:
            pickle.dump(recs, f)
    # C0 on E tasks (evaluator side, base budget): by construction no fit
    fams = sorted({t["family"] for t in ev.values() if t["family"]})
    mts = {f: sorted([i for i, t in ev.items() if t["family"] == f and t["partition"] == "M"],
                     key=lambda i: (ev[i]["template"], h(i))) for f in fams}
    plan, jobs = [], []
    names = {s: NM.Names(g0b.g, s) for s in SEEDS}
    for fi, f in enumerate(fams):
        for slot, tid in enumerate(mts[f]):
            donor_f = fams[(fi + 1) % len(fams)]
            donor = mts[donor_f][slot % len(mts[donor_f])]
            for s in SEEDS:
                for arm in ARMS:
                    ep = f"{arm}_{tid}_s{s}"
                    row = {"episode": ep, "arm": arm, "task": tid, "seed": s, "donor": donor if arm == "C3" else None,
                           "controller_decision": recs[tid]["decision"]}
                    plan.append(row)
                    if recs[tid]["decision"] != "INVENT_NEW_OPERATION":
                        continue
                    if arm == "C3" and recs[donor]["decision"] != "INVENT_NEW_OPERATION":
                        row["donor_note"] = "donor not a failure"
                    failure = {"C2": None, "C3": recs[donor] if recs[donor].get("hypotheses") else None,
                               "C5": recs[tid]}[arm]
                    msgs = PM.invent_messages(as_task(sys_t[tid]), names[s], g0b.g, failure)
                    jobs.append({"job_id": ep, "messages": msgs, "n": K, "max_new": MAX_NEW, "temperature": TEMP,
                                 "top_p": TOP_P, "seed": seed_of(tid, s)})
                jobs.append({"job_id": f"C1r1_{tid}_s{s}", "messages": PM.c1_messages(as_task(sys_t[tid])),
                             "n": K_C1, "max_new": MAX_NEW, "temperature": TEMP, "top_p": TOP_P,
                             "seed": seed_of(tid, s)})
    with P.open_write(os.path.join(rdir, "plan.json")) as f:
        json.dump({"plan": plan, "g0_sha256": g0b.sha, "seeds": SEEDS, "arms": ARMS, "K": K, "K_C1": K_C1,
                   "max_new": MAX_NEW, "temperature": TEMP, "top_p": TOP_P,
                   "names_sha256": {s: h(json.dumps(names[s].code, sort_keys=True)) for s in SEEDS}}, f, indent=1)
    with P.open_write(os.path.join(rdir, "jobs.jsonl")) as f:
        for j in jobs:
            f.write(json.dumps(j) + "\n")
    summ = {tid: {"status": r["status"], "decision": r["decision"], "level": r["level"],
                  "base_level": r["base"]["level_complete"], "closure_capped": r["base"]["closure_capped"],
                  "deeper_level": (r.get("probe_deeper_search") or {}).get("level_complete")} for tid, r in recs.items()}
    with P.open_write(os.path.join(rdir, "controller_summary.json")) as f:
        json.dump(summ, f, indent=1, sort_keys=True)
    print(json.dumps({"tasks": len(recs), "jobs": len(jobs), "episodes": sum(1 for p in plan if
                                                                          p["controller_decision"] ==
                                                                          "INVENT_NEW_OPERATION")}), flush=True)


# ------------------------------------------------------------------ evaluator-only diagnostic D0 (ceiling probe)
def oracle_jobs(prep_id, out_path, n_pairs=3):
    """D0: the C2 prompt plus the exact input/output behaviour of the removed operation on the motivating task's own
    grids (the argument the reference receives in the task's program, and its result). No name, no code. Seed 0
    only; not an arm, never registered; it measures whether the proposer can implement the operation when the
    specification is given."""
    from a2 import arcdsl as D
    ev = eval_tasks()
    sys_t = system_tasks()
    g0b = G0Builder()
    names = NM.Names(g0b.g, 0)
    with open(os.path.join(P.RUNS, prep_id, "records.pkl"), "rb") as f:
        recs = pickle.load(f)
    fns = D.guarded(D.load()[0])
    jobs = []
    for tid in sorted(i for i, t in ev.items() if t["partition"] == "M"):
        if recs[tid]["decision"] != "INVENT_NEW_OPERATION":
            continue
        t = ev[tid]
        ref = L0.reference_fn(t["family"])
        p = tuple(t["params"])
        xs = [EP.grid(a) for a, _ in t["train"]]
        args = [fns[t["op"]](x) for x in xs] if t["template"] == "T2" else xs
        pairs = [(a, ref(a, *p)) for a in args][:n_pairs]
        block = PM.spec_block(pairs, p[0] if p else None)
        msgs = PM.invent_messages(as_task(sys_t[tid]), names, g0b.g, None, extra=block)
        jobs.append({"job_id": f"D0_{tid}_s0", "messages": msgs, "n": K, "max_new": MAX_NEW, "temperature": TEMP,
                     "top_p": TOP_P, "seed": seed_of(tid, 0)})
    with P.open_write(out_path, "a") as f:
        for j in jobs:
            f.write(json.dumps(j) + "\n")
    print(json.dumps({"oracle_jobs": len(jobs)}), flush=True)


def process_diag(run_id, prep_id, gen_id):
    """System-side processing of the D0 replies (same checks and retry as an episode; no registry, no promotion)."""
    rdir = os.path.join(P.RUNS, run_id)
    g0b = G0Builder()
    sys_t = system_tasks()
    with open(os.path.join(P.RUNS, prep_id, "records.pkl"), "rb") as f:
        recs = pickle.load(f)
    reps = load_replies(os.path.join(P.RUNS, gen_id, "replies.jsonl"))
    out_path = os.path.join(rdir, "diag_episodes.jsonl")
    for jid in sorted(j for j in reps if j.startswith("D0_")):
        tid = jid.split("_")[1]
        res, _, _ = EP.process(jid, reps[jid]["replies"], as_task(sys_t[tid]), g0b, {}, [], {}, {}, max_candidates=0)
        res.update({"task": tid, "gen_tokens": sum(r["gen_tokens"] for r in reps[jid]["replies"])})
        with P.open_write(out_path, "a") as f:
            f.write(json.dumps(res, default=list) + "\n")
        print(json.dumps({"diag": jid, "n_fitting": res["n_fitting"]}), flush=True)


# ------------------------------------------------------------------ process
def load_replies(path):
    out = {}
    with open(path, encoding="utf-8") as f:
        for x in f:
            if x.strip():
                r = json.loads(x)
                out[r["job_id"]] = r
    return out


def c1_program(text):
    m = IV.CODE.search(text or "")
    if not m:
        return None, "no_code_block"
    code = m.group(1)
    try:
        chk = IV.GL.check(code)
    except IV.GL.GridFnError as e:
        return None, "check_" + e.kind
    if set(chk.primitives) - IV.ALLOWED_PRIMS:
        return None, "substrate_violation"
    return code, None


def c1_run(code, task, sb):
    outs, errs = [], []
    for a, _ in task["train"]:
        rep = sb.run(code, [list(r) for r in a], cpu_s=2.0)
        outs.append(IV._to_grid(rep["out"]) if rep.get("ok") else None)
        errs.append(None if rep.get("ok") else f"{rep.get('kind')}: {rep.get('message')}"[:160])
    fit = all(o == b for o, (_, b) in zip(outs, task["train"]))
    q = None
    if fit:
        rep = sb.run(code, [list(r) for r in task["test_inputs"][0]], cpu_s=2.0)
        q = IV._to_grid(rep["out"]) if rep.get("ok") else None
    return {"fit": fit, "query_pred": q, "outs": outs, "errors": errs}


def c1_feedback(task, res):
    lines = []
    for k, ((_, b), o, e) in enumerate(zip(task["train"], res["outs"], res["errors"]), 1):
        if e:
            lines.append(f"Example {k}: error {e}")
        elif o == b:
            lines.append(f"Example {k}: correct")
        else:
            lines.append(f"Example {k}: wrong; it returned\n{NM.grid_block(o)}")
    return "\n".join(lines)


def process(run_id, prep_id, gen_id, arms=ARMS, reg_prefix="testI"):
    rdir = os.path.join(P.RUNS, run_id)
    os.makedirs(rdir, exist_ok=True)
    g0b = G0Builder()
    sys_t = system_tasks()
    with open(os.path.join(P.RUNS, prep_id, "records.pkl"), "rb") as f:
        recs = pickle.load(f)
    plan = load_json(os.path.join(P.RUNS, prep_id, "plan.json"))
    reps = load_replies(os.path.join(P.RUNS, gen_id, "replies.jsonl"))
    solved = {tid: as_task(sys_t[tid]) for tid, r in recs.items() if r["status"] == "solved"}
    base_preds = {tid: recs[tid]["base_preds"][0] for tid in solved}
    unsolved = sorted([tid for tid, r in recs.items() if r["status"] != "solved"], key=lambda i: h("pool:" + i))
    ep_path = os.path.join(rdir, "episodes.jsonl")
    done = set()
    if os.path.exists(ep_path):
        with open(ep_path, encoding="utf-8") as f:
            done = {json.loads(x)["episode"] for x in f if x.strip()}
    cache_path = os.path.join(rdir, "promotion_cache.pkl")
    cache = {}
    if os.path.exists(cache_path):
        with open(cache_path, "rb") as f:
            cache = pickle.load(f)
    regs = {}
    for arm in arms:
        rp = os.path.join(P.REGISTRY_DIR, f"{reg_prefix}_{arm}.json")
        regs[arm] = RG.Registry(f"{reg_prefix}_{arm}", "arcdsl635de49-minus-hidden", g0b.sha)
        if os.path.exists(rp) and done:
            regs[arm].doc = load_json(rp)
    for row in plan["plan"]:
        ep = row["episode"]
        if ep in done or row["controller_decision"] != "INVENT_NEW_OPERATION":
            continue
        if ep not in reps:
            print(json.dumps({"episode": ep, "missing_replies": True}), flush=True)
            continue
        tid = row["task"]
        pool = [(i, as_task(sys_t[i])) for i in unsolved if i != tid]
        res, promoted, fitting = EP.process(ep, reps[ep]["replies"], as_task(sys_t[tid]), g0b, solved, pool,
                                            base_preds, cache)
        res.update({"arm": row["arm"], "task": tid, "seed": row["seed"], "donor": row["donor"],
                    "prompt_sha256": reps[ep]["prompt_sha256"],
                    "prompt_tokens": reps[ep]["replies"][0]["prompt_tokens"] if reps[ep]["replies"] else None,
                    "gen_tokens": sum(r["gen_tokens"] for r in reps[ep]["replies"]),
                    "gpu_s": round(sum(r["gpu_s"] for r in reps[ep]["replies"]), 2)})
        reg = regs[row["arm"]]
        for frow, prop, chk, tests, op, head in fitting[:EP_MAX]:
            dec = frow.get("promotion")
            if dec is None:
                continue
            ident = f"{prop['fields'].get('NAME', 'op')[:24].lower()}"
            ident = "".join(c if c.isalnum() else "_" for c in ident).strip("_") or "op"
            ident = f"{ident}_{frow['code_sha256'][:6]}" if ident[0].isalpha() else f"op_{frow['code_sha256'][:6]}"
            prov = {"run_id": run_id, "arm": row["arm"], "motivating_tasks": [tid],
                    "motivating_failures": [f"{prep_id}:{tid}"] if row["arm"] in ("C5", "C5n") else
                    ([f"{prep_id}:{row['donor']}"] if row["arm"] == "C3" else []),
                    "proposer": {"model": "Qwen3-4B-Instruct-2507 fp16", "seed": row["seed"], "sample": frow["sample"],
                                 "prompt_sha256": reps[ep]["prompt_sha256"]}, "parent": None}
            kind, kev = "undetermined", "kind is established after promotion by the probe-grid search (evaluation)"
            e = reg.entry(ident, prop, chk, [{"id": t["id"], "passed": t["passed"], "detail": t["detail"]}
                                             for t in IV.run_tests(op, prop["tests"])], prov, kind, kev,
                          "quarantined", "fits the motivating task", evidence={"motivating": tid})
            vname = f"G1.{ep}.{frow['sample']}"
            reg.version(vname, [ident], dec["regression"])
            if dec["decision"] == "rolled_back":
                reg.set_status(e, "rolled_back", "regression on previously solved tasks", vname, dec["regression"])
                reg.version(f"{vname}.rollback", [], dec["regression"], rollback_of=vname, removed=[f"{ident}@1"])
            elif dec["decision"] == "promoted":
                reg.set_status(e, "promoted", "useful beyond the motivating task, no regression", vname,
                               dec["validation"], scope="persistent")
                e["kind"] = "undetermined"
            else:
                reg.set_status(e, "quarantined", "no new fit on other unsolved tasks", vname, dec["validation"])
            e["validation"] = {"motivating": {"task": tid, "fit": True}, "held_out": dec.get("validation") or {},
                               "regression": dec["regression"]}
            frow["registry_id"] = ident
        with P.open_write(ep_path, "a") as f:
            f.write(json.dumps(res, default=list) + "\n")
        for arm, reg in regs.items():
            reg.save(os.path.join(P.REGISTRY_DIR, f"{reg_prefix}_{arm}.json"))
        with open(P.check_write(cache_path), "wb") as f:
            pickle.dump(cache, f)
        print(json.dumps({"episode": ep, "n_fitting": res["n_fitting"], "promoted": res["promoted_sample"],
                          "cpu_s": res["cpu_s"]}), flush=True)
    # C1 round 1 and repair jobs
    c1_path = os.path.join(rdir, "c1_round1.jsonl")
    c1_done = set()
    if os.path.exists(c1_path):
        with open(c1_path, encoding="utf-8") as f:
            c1_done = {json.loads(x)["job_id"] for x in f if x.strip()}
    evt = eval_tasks()
    sb = IV.SB.default()
    repair_jobs = []
    for jid, r in sorted(reps.items()):
        if not jid.startswith("C1r1_"):
            continue
        tid = jid.split("_")[1]
        task = as_task(sys_t[tid]) if tid in sys_t else as_task(evt[tid])
        rows, best = [], None
        for i, rep in enumerate(r["replies"]):
            code, err = c1_program(rep["text"])
            row = {"sample": i, "gen_tokens": rep["gen_tokens"], "error": err}
            if code is not None:
                res = c1_run(code, task, sb)
                cells = sum(sum(a == b for ra, rb in zip(o, y) for a, b in zip(ra, rb)) if o is not None and
                            len(o) == len(y) and len(o[0]) == len(y[0]) else 0
                            for o, (_, y) in zip(res["outs"], task["train"]))
                row.update({"fit": res["fit"], "query_pred": res["query_pred"], "cells_correct": cells})
                if not res["fit"] and (best is None or cells > best[0]):
                    best = (cells, code, res)
            rows.append(row)
        # one repair per task and seed (C1 = 3 samples + 1 repair = 4 generations, as K = 4 for invention):
        # the best executable non-fitting program with its execution feedback, else a fresh sample
        if not any(row.get("fit") for row in rows):
            s_ = jid.split("_")[2]
            if best is not None:
                msgs = PM.c1_repair_messages(task, best[1], c1_feedback(task, best[2]))
            else:
                msgs = PM.c1_messages(task)
            repair_jobs.append({"job_id": f"C1r2_{tid}_{s_}_0", "messages": msgs, "n": 1, "max_new": MAX_NEW,
                                "temperature": TEMP, "top_p": TOP_P, "seed": seed_of(tid, jid, "repair")})
        if jid not in c1_done:
            with P.open_write(c1_path, "a") as f:
                f.write(json.dumps({"job_id": jid, "task": tid, "rows": rows}, default=list) + "\n")
    with P.open_write(os.path.join(rdir, "c1_repair_jobs.jsonl")) as f:
        for j in repair_jobs:
            f.write(json.dumps(j) + "\n")
    print(json.dumps({"c1_repair_jobs": len(repair_jobs)}), flush=True)


EP_MAX = 2


if __name__ == "__main__":
    if sys.argv[1] == "prep":
        prep(sys.argv[2])
    elif sys.argv[1] == "process":
        process(sys.argv[2], sys.argv[3], sys.argv[4])
    elif sys.argv[1] == "oracle_jobs":
        oracle_jobs(sys.argv[2], sys.argv[3])
    elif sys.argv[1] == "process_diag":
        process_diag(sys.argv[2], sys.argv[3], sys.argv[4])
