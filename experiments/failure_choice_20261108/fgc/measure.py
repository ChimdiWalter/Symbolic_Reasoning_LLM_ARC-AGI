"""System side: measure, once per task, the base attempt, its failure record, and each intervention of the bank.

    python -m fgc.measure WORLD TASKS_SYSTEM.json OUT.json [TASK_ID ...]

Every cost is counted in primitive executions ("calls", A2's own count of executed primitives), a deterministic
quantity: the same task gives the same calls on any machine, so the arms can be replayed exactly at any budget from
these records (fgc/arms.py). CPU seconds are recorded beside it. No search stops on CPU time here: every CPU cap
is set out of reach, so only the call budgets bind.

Per task (only the task's demonstrations and query inputs are read; never a label, a cause or a family):
1. base: S1's base search over the world's G0 at S1's base budget (150,000 calls), with the closest-program record.
2. failure record (no deeper probe): S1's controller helpers on the base failure: shape relation, closest program
   (cells correct, residual), and the typed-hole sketches (identity ?(I), outer B(?(I)), inner ?(A(I))) with their
   scores. S1's controller also runs a 4x deeper search before deciding; that probe is the search intervention
   itself, so it is NOT part of the failure record here.
3. search intervention: the same G0 search from the start, one fit wanted, up to MEASURE_CALLS calls; records the
   calls at its first fit (or that it found none within the cap).
4. construct intervention: S1's typed-hole construction (S-hole) from this task's own sketches: specification
   enumeration over the 211 structures in seed-0 order, then S1's gates (novelty, retry at the base budget,
   regression on every base-solved task of the world, validation on the world's other unsolved tasks), at most 3
   retries; the label-blind commit (promoted structure, else the first quarantined one). Its gates run with an empty
   cache for every task, so its count is the complete work of construction on that task: every call of every
   search its gates run, plus one call for every application of a structure to a grid outside a search (the
   specification enumeration and the novelty gate's probe pairs).
"""
import json
import os
import sys
import time

from fgc import common as C
from fgc.common import E, X, CT, S, SG, s1, D

MEASURE_CALLS = 20_000_000      # cap of the measured search intervention (covers arm B up to 4x the binding budget)
NO_CPU_CAP = 1e9                # CPU caps out of reach: only call budgets bind


class _Count:
    calls = 0
    in_search = 0


_ORIG_RUN = S.run
_ORIG_STRUCTURE_CALL = SG.Structure.__call__


def _counted_run(*a, **k):
    if len(a) > 4:                                   # cpu_cap given positionally
        a = a[:4] + (NO_CPU_CAP,) + a[5:]
    else:
        k = dict(k, cpu_cap=NO_CPU_CAP)
    _Count.in_search += 1
    try:
        r = _ORIG_RUN(*a, **k)
    finally:
        _Count.in_search -= 1
    _Count.calls += int(r.get("calls") or 0)
    return r


def _counted_structure_call(self, g, *th):
    """A structure applied to a grid outside a search (the specification enumeration over the 211 structures,
    the novelty gate's probe pairs) counts one call; inside a search A2 already counts it."""
    if not _Count.in_search:
        _Count.calls += 1
    return _ORIG_STRUCTURE_CALL(self, g, *th)


S.run = _counted_run            # every search the frozen gates make is counted (module attribute, read at call time)
SG.Structure.__call__ = _counted_structure_call


class FreshGates(s1.Gates):
    """S1's gates (unchanged methods) with an in-memory cache that is emptied before every task and never written,
    so that each task's construction is charged its complete work."""

    def save(self, force=False):
        return None

    def reset(self):
        self.c = {"nov": {}, "retry": {}, "reg": {}}


def committed_outputs(rows):
    fits = [r for r in rows if r.get("fit")]
    for kind in ("promoted", "quarantined"):
        kept = [r for r in fits if r.get("promotion") == kind]
        if kept:
            return (kept[0].get("preds") or [])[:2], kind, kept[0].get("sid")
    return None, None, None


def lists(preds):
    return [[C.as_lists(g) for g in att] for att in preds] if preds else None


def failure_record(task, g, base):
    train, qs = task["train"], task["test_inputs"]
    t0 = time.process_time()
    rec = {"n_demos": len(train), "shape_relation": CT.shape_relation(train)}
    if "partial" in base and base["partial"]:
        k, res = CT.residual(base["partial"], train)
        cells = sum(len(y) * len(y[0]) for _, y in train)
        rec["closest"] = {"cells_correct": base["partial"]["cells_correct"], "cells_total": cells,
                          "program": base["partial"]["program"]}
    else:
        rec["closest"] = None
    sk, _ = CT.sketches(train, g)
    rec["sketches"] = [{"form": c["form"], "outer": c["outer"], "inner": c["inner"], "score": c["score"],
                        "pairs": [[C.as_lists(a), C.as_lists(b)] for a, b in c["pairs"]]} for c in sk]
    ins = [a for a, _ in train]
    outs = [b for _, b in train]
    rec["sizes"] = {"in": [[len(a), len(a[0])] for a in ins], "out": [[len(b), len(b[0])] for b in outs],
                    "query": [[len(q), len(q[0])] for q in qs]}
    rec["colours"] = {"in": [len({v for r in a for v in r}) for a in ins], "out": [len({v for r in b for v in r})
                                                                                for b in outs]}
    rec["cpu_s"] = round(time.process_time() - t0, 4)
    return rec


def measure_task(tid, sys_task, g0b, G, order, measure_calls=MEASURE_CALLS):
    task = X.as_task(sys_task)
    train, qs = task["train"], task["test_inputs"]
    out = {"task": tid}
    # 1. base
    _Count.calls = 0
    t0 = time.process_time()
    base = S.run(g0b(), train, qs, budget=S.BASE_BUDGET, cpu_cap=NO_CPU_CAP, track_partial=True)
    out["base"] = {"fit": bool(base["fit"]), "preds": lists(base["preds"]), "program": base["program"],
                   "calls": int(base["calls"]), "level_complete": base["level_complete"], "stop": base["stop"],
                   "closure_capped": base["closure_capped"], "bank": base["bank"],
                   "cpu_s": round(time.process_time() - t0, 3)}
    # 2. failure record (no probe)
    out["record"] = failure_record(task, g0b(), base)
    # 3. search intervention (from the start, one fit, up to measure_calls)
    t0 = time.process_time()
    deep = S.run(g0b(), train, qs, budget=measure_calls, cpu_cap=NO_CPU_CAP, want=1)
    out["search"] = {"fit": bool(deep["fit"]), "preds": lists(deep["preds"]), "program": deep["program"],
                     "calls": int(deep["calls"]), "stop": deep["stop"], "level_complete": deep["level_complete"],
                     "closure_capped": deep["closure_capped"], "cap_calls": measure_calls,
                     "cpu_s": round(time.process_time() - t0, 3)}
    # 4. construct intervention (fresh gates: complete work counted)
    G.reset()
    G.sys_t[tid] = sys_task
    sk = out["record"]["sketches"]
    sk_grids = [{"form": c["form"], "outer": c["outer"], "inner": c["inner"], "score": c["score"],
                 "pairs": c["pairs"]} for c in sk]
    _Count.calls = 0
    t0 = time.process_time()
    cands = s1.spec_candidates(order, sk_grids)
    res = s1.run_spec_unit(G, tid, cands)
    preds, kind, sid = committed_outputs(res["rows"])
    out["construct"] = {"fit": preds is not None, "preds": lists(preds) if preds else None, "kind": kind,
                        "structure": sid, "calls": int(_Count.calls), "retries": res["retries"],
                        "n_candidates": res["n_candidates"],
                        "rows": [{k: r.get(k) for k in ("sid", "outcome", "fit", "promotion", "sketch_form")}
                                 for r in res["rows"]],
                        "cpu_s": round(time.process_time() - t0, 3)}
    return out


def main(world, tasks_path, out_path, ids=None):
    P = E.use_world(C.world_dir(world))
    sys_tasks = C.load(tasks_path)
    ids = ids or sorted(sys_tasks)
    done = C.load(out_path) if os.path.exists(out_path) else {}
    g0b = X.G0Builder()
    G = FreshGates(os.path.join(P.RUNS, "fgc_unused_gates.pkl"))
    order = SG.seeded_order(0)
    for tid in ids:
        if tid in done:
            continue
        t0 = time.time()
        r = measure_task(tid, sys_tasks[tid], g0b, G, order)
        r["world"] = world
        r["wall_s"] = round(time.time() - t0, 1)
        done[tid] = r
        E.dump(out_path, done)
        print(json.dumps({"task": tid, "base_fit": r["base"]["fit"], "search_fit": r["search"]["fit"],
                          "search_calls": r["search"]["calls"], "construct_fit": r["construct"]["fit"],
                          "construct_calls": r["construct"]["calls"], "wall_s": r["wall_s"]}), flush=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:] or None)
