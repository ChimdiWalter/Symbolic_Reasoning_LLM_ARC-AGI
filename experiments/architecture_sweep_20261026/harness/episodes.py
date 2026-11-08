"""Shared episode builder: states from verified source programs, plus the observed outcome of EVERY available action.

Frozen proposer: CORA's native enumerator (`cora_neural_v2g2.search.enumerate_programs`, demonstrations and query
inputs only). The first N_EXEC programs are executed; the strict version space and the best frontier members (up to
CAP) form the initial memory H0; the next N_RESERVE programs are the reserve that NEW consumes.

Verified source program P*: synthetic tasks: the family's own program (execution-verified by construction); real
S_train / S_select tasks: the first proposer program that fits all demonstrations AND reproduces the source test
outputs (a source-training label used only for this check and for outcome labels).

Episode variants (one state each; labels are on withheld examples only):
  natural    H0 as proposed (no injection)
  correct    P* present at rank 0 (already-correct case: any displacing revision is harmful)
  corrupt1   P* removed; two single-mutation faults of P* at ranks 0-1 (local faults; repairable in one step)
  corrupt2   P* removed; one fault built from two successive mutations (partially repairable)
  wrongrep   P* removed; a REPRESENTATION fault of P* (wrong object view)
  unrelated  P* removed; verified programs of OTHER source tasks of the same split at ranks 0-2 (wrong structures)
Withheld examples: synthetic: n_withheld generated pairs; real: the task's test pairs (source labels). Visible = all
demonstrations (as in deployment). Outcomes go to a separate file from observations (`*.outcomes.jsonl`).
"""
import json
import os
import random
import time
import zlib

import numpy as np

from harness import actions as A
from harness import core as C
from harness import paths as P

N_EXEC = 96
N_RESERVE = 24
GEN_DEADLINE_S = 2.0
GUARD_S = 2.0


def proposer(task, ctx, n_exec=N_EXEC, n_reserve=N_RESERVE):
    from cora_neural_v2g2 import search as G2S
    progs = []
    try:
        for p, _ in G2S.enumerate_programs(task, n_exec + n_reserve, gen_deadline_s=GEN_DEADLINE_S):
            progs.append(p)
    except Exception:                                       # noqa: BLE001 (an enumerator failure = empty proposal)
        pass
    hyps = [ctx.execute(p, "enum", rank=r) for r, p in enumerate(progs[:n_exec])]
    return hyps, progs[n_exec:]


def initial_memory(hyps):
    seen, out = set(), []
    top = {h.key for h in sorted([h for h in hyps if not h.vs], key=lambda x: x.rank)[:2]}
    for h in sorted(hyps, key=lambda x: (not x.vs, x.key not in top, x.rank if x.vs else -x.jac, -x.acc, x.rank)):
        if h.key in seen or h.status == "INVALID":
            continue
        seen.add(h.key)
        out.append(h)
    return out[:C.CAP]


def make_ctx(task, progs=()):
    ctx = A.Ctx(task, progs)
    ctx.runner.guard_s = GUARD_S
    return ctx


def corruptions(pstar, ctx, rng, families, depth=1, n=1, tries=20):
    from llm_writer.search import mutate_cora as MC
    out = []
    if not MC.mutable(pstar.prog):
        return out
    for _ in range(tries):
        if len(out) >= n:
            break
        prog, labels = pstar.prog, []
        for _d in range(depth):
            fam = rng.choice(families)
            child, lab = MC.propose(prog, fam, rng, ctx.lib)
            if child is None:
                break
            prog, labels = child, labels + [lab]
        if len(labels) < depth:
            continue
        h = ctx.execute(prog, "fault", pstar.key, "+".join(labels))
        if h.key != pstar.key and h.qkey != pstar.qkey and h.status != "INVALID":
            out.append(h)
    return out


def rerank(hyps, first):
    """Place `first` at ranks 0.. and shift the rest (ranks are the proposer order used by the default attempts)."""
    import copy
    out = []
    for j, h in enumerate(first):
        hh = copy.copy(h)
        hh.rank = j
        out.append(hh)
    for h in hyps:
        hh = copy.copy(h)
        hh.rank = h.rank + len(first)
        out.append(hh)
    return out


def variants(task, ctx, hyps, reserve, pstar, others, seed, kinds):
    rng = random.Random(seed)
    base = initial_memory(hyps)
    out = []
    if "natural" in kinds:
        out.append(("natural", base))
    if pstar is None:
        return out
    without = [h for h in base if h.key != pstar.key]
    fams = ["PARAMETER", "SELECTOR", "TRANSFORM", "OUTPUT", "COMPOSE"]
    if "correct" in kinds:
        out.append(("correct", initial_memory(rerank(without, [pstar]))))
    if "corrupt1" in kinds:
        f = corruptions(pstar, ctx, rng, fams, 1, 2)
        if f:
            out.append(("corrupt1", initial_memory(rerank(without, f))))
    if "corrupt2" in kinds:
        f = corruptions(pstar, ctx, rng, fams, 2, 1)
        if f:
            out.append(("corrupt2", initial_memory(rerank(without, f))))
    if "wrongrep" in kinds:
        f = corruptions(pstar, ctx, rng, ["REPRESENTATION"], 1, 1)
        if f:
            out.append(("wrongrep", initial_memory(rerank(without, f))))
    if "unrelated" in kinds and others:
        picks = rng.sample(others, min(3, len(others)))
        f = [ctx.execute(p, "foreign", rank=j) for j, p in enumerate(picks)]
        f = [h for h in f if h.status != "INVALID" and h.key != pstar.key]
        if f:
            out.append(("unrelated", initial_memory(rerank(without, f))))
    return out


def qh(q):
    import hashlib
    return None if q is None else hashlib.sha1(q.encode()).hexdigest()[:12]


def outcomes(state, ctx, truths=None, mode="revise"):
    """One-step outcome of every available action from `state`: the resulting attempts (behaviour hashes) and the
    predictions of every behaviour named. Labels are attached only when `truths` is given (source splits); for
    ARC_eval_dev the separate scorer process labels the same record."""
    beh = {}

    def rec(s):
        out = []
        for q in s.attempts:
            h = qh(q)
            out.append(h)
            if h not in beh:
                beh[h] = s.preds_of(q)
        return out
    res = {"base_att": rec(state), "rows": [], "beh": beh}
    for act in state.available():
        s2, eff = A.apply(state, act, ctx, mode)
        res["rows"].append({"a": [act[0], act[1]], "att": rec(s2), "n_exec": eff["n_exec"], "cpu": eff["cpu"],
                            "new_beh": eff["new_behaviour"], "n_new_fit": sum(1 for x in eff["new"] if x["vs"])})
    if truths is not None:
        label(res, truths)
    return res


def label(res, truths):
    """Exact labels of an outcome record against withheld truths (in place)."""
    def sc(att):
        return C.score([res["beh"][h] for h in att], truths)
    b = sc(res["base_att"])
    res["base"] = {k: b[k] for k in ("all2", "all1", "frac2")}
    for r in res["rows"]:
        s = sc(r["att"])
        r.update(y2=s["all2"], y1=s["all1"], f2=s["frac2"], gain2=int(s["all2"]) - int(b["all2"]),
                 harm2=bool(b["all2"] and not s["all2"]), harm1=bool(b["all1"] and not s["all1"]))
    return res


def observation(state):
    return {"tokens": state.token_features(), "rel": state.relations(), "glob": state.global_features(),
            "actions": [[k, i] for k, i in state.available()]}


class ShardWriter:
    """Observations (npz + jsonl) and outcomes (separate jsonl) per shard; resumable by task id."""

    def __init__(self, out_dir, name):
        self.dir = out_dir
        os.makedirs(out_dir, exist_ok=True)
        self.name = name
        self.idx_path = os.path.join(out_dir, f"{name}.done.txt")
        self.done = set(open(self.idx_path).read().split()) if os.path.exists(self.idx_path) else set()
        self.buf = []
        self.n_shard = len([f for f in os.listdir(out_dir) if f.startswith(name + ".") and f.endswith(".npz")])

    def add(self, meta, obs, outc):
        self.buf.append((meta, obs, outc))

    def flush(self, task_ids):
        if self.buf:
            k = f"{self.name}.{self.n_shard:04d}"
            toks = [o["tokens"] for _, o, _ in self.buf]
            rels = [o["rel"] for _, o, _ in self.buf]
            np.savez_compressed(os.path.join(self.dir, k + ".npz"),
                                tokens=np.concatenate(toks) if toks else np.zeros((0, C.TOKEN_DIM), np.float32),
                                rel=np.concatenate([r.reshape(-1, 2) for r in rels]) if rels else np.zeros((0, 2)),
                                glob=np.stack([o["glob"] for _, o, _ in self.buf]),
                                n_hyp=np.array([o["tokens"].shape[0] for _, o, _ in self.buf]))
            with P.open_allowed(os.path.join(self.dir, k + ".jsonl"), mode="w") as f:
                for m, o, _ in self.buf:
                    f.write(json.dumps(dict(m, actions=o["actions"])) + "\n")
            with P.open_allowed(os.path.join(self.dir, k + ".outcomes.jsonl"), mode="w") as f:
                for m, _, oc in self.buf:
                    f.write(json.dumps({"state_id": m["state_id"], **oc}) + "\n")
            self.n_shard += 1
            self.buf = []
        with P.open_allowed(self.idx_path, mode="a") as f:
            for t in task_ids:
                f.write(t + "\n")
        self.done |= set(task_ids)


def seed_of(*xs):
    return zlib.crc32("|".join(map(str, xs)).encode())


def find_pstar(hyps, truths):
    for h in sorted([h for h in hyps if h.vs], key=lambda x: x.rank):
        if C.score([h.preds], truths)["all1"]:
            return h
    return None


def build_task(task, truths, pstar_text, others, kinds, seed, writer, split, family=None):
    """All variant states of one task; returns stats. `others`: verified programs of other tasks (same split)."""
    t0 = time.process_time()
    ctx = make_ctx(task)
    hyps, reserve = proposer(task, ctx)
    n0 = ctx.n_req
    ctx = make_ctx(task, [h.prog for h in initial_memory(hyps)])
    pstar = None
    if pstar_text is not None:
        try:
            pstar = ctx.execute(C.L.parse(pstar_text), "verified", rank=0)
        except Exception:                                   # noqa: BLE001
            pstar = None
        if pstar is not None and (truths is None or not (pstar.vs and C.score([pstar.preds], truths)["all1"])):
            pstar = None
    if pstar is None and truths is not None:
        pstar = find_pstar(hyps, truths)
    n_states = 0
    for vname, mem in variants(task, ctx, hyps, reserve, pstar, others, seed, kinds):
        st = C.State(task, mem, reserve)
        oc = outcomes(st, ctx, truths)
        sid = f"{task['task_id']}|{vname}"
        meta = {"state_id": sid, "task_id": task["task_id"], "split": split, "family": family, "variant": vname,
                "state_hash": st.hash(), "n_hyp": len(mem), "n_vs": len(st.vs()), "attempts": st.attempts,
                "has_pstar": pstar is not None}
        writer.add(meta, observation(st), oc)
        n_states += 1
    return {"task_id": task["task_id"], "states": n_states, "pstar": pstar.text if pstar is not None else None,
            "cpu": time.process_time() - t0, "n_exec": n0 + ctx.n_req}
