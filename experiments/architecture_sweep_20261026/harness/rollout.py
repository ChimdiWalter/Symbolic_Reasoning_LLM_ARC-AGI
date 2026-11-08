"""End-to-end (online) mode: rebuild a stored state live and let a policy act until STOP or the budget ends.

    st, ctx = rebuild(meta)                       # identical H0 to the stored episode (deterministic proposer/variant)
    final, log = rollout(st, ctx, policy, budget=60, max_steps=6, trace=DecisionLog(...))
A policy is a callable `policy(state) -> (action, scores or None)`, action = (kind, index[, mode]); it sees the State only (no labels, no answers).
Executions are requested through the shared per-task Runner (its cache may serve several arms; cost comparisons
use executions REQUESTED, which a cache hit does not reduce).
"""
import os
import pickle

from harness import actions as A
from harness import core as C
from harness import data as D
from harness import episodes as E
from harness import paths as P


CACHE = os.path.join(P.RUNS, "h0_cache")


def _proposed(task, split, tid):
    """The frozen proposer's executed programs and reserve for a task, cached on disk (deterministic, so a cache
    hit is identical to a rerun; it only saves CPU when several families or arms rebuild the same task)."""
    f = os.path.join(CACHE, f"{split}__{tid.replace(':', '_').replace('#', '_')}.pkl")
    if os.path.exists(f):
        with open(f, "rb") as fh:
            return pickle.load(fh)
    ctx = E.make_ctx(task)
    hyps, reserve = E.proposer(task, ctx)
    os.makedirs(CACHE, exist_ok=True)
    tmp = f"{f}.{os.getpid()}.tmp"                         # per-process temp name: concurrent screens may race
    with open(tmp, "wb") as fh:
        pickle.dump((hyps, reserve, ctx.n_req), fh)
    os.replace(tmp, f)
    return hyps, reserve, ctx.n_req


def rebuild(meta):
    """(State, ctx) for a stored episode meta, identical to the stored H0: same proposer, same P* rule, same
    `others`, and the variant RNG consumed over ALL variants in build order. ARC_eval_dev: natural state only."""
    from harness import build_episodes as B
    split, tid = meta["split"], meta["task_id"]
    if split.endswith("_syn"):
        fam, seed = tid[4:].split("#")
        task, truths, ptext = D.synthetic_task(fam, int(seed))
        others = [p for p in B.others_for(split) if C.L.render(p) != ptext]
    elif split == "ARC_eval_dev":
        task, truths, ptext, others = D.task_record(tid, split), None, None, []
    else:
        task, truths, ptext = D.task_record(tid, split), D.source_labels(split)[tid], None
        others = B.others_for(split + "_syn")
    hyps, reserve, n0 = _proposed(task, split, tid)
    ctx2 = E.make_ctx(task, [h.prog for h in E.initial_memory(hyps)])
    ctx2.n_req = n0
    if meta["variant"] == "natural":
        return C.State(task, E.initial_memory(hyps), reserve), ctx2
    pstar = None
    if ptext is not None:
        try:
            pstar = ctx2.execute(C.L.parse(ptext), "verified", rank=0)
        except Exception:                                   # noqa: BLE001
            pstar = None
        if pstar is not None and not (pstar.vs and C.score([pstar.preds], truths)["all1"]):
            pstar = None
    if pstar is None and truths is not None:
        pstar = E.find_pstar(hyps, truths)
    for vname, mem in E.variants(task, ctx2, hyps, reserve, pstar, others, E.seed_of(tid), B.VARIANTS):
        if vname == meta["variant"]:
            return C.State(task, mem, reserve), ctx2
    return None, ctx2


def rollout(state, ctx, policy, budget=60, max_steps=6, trace=None, mode="revise"):
    st = state.copy()
    st.budget = budget
    steps = []
    while st.steps < max_steps and st.budget > 0:
        act, scores = policy(st)
        m = mode
        if len(act) == 3:                                   # (kind, index, mode): the policy chose the revision mode
            act, m = act[:2], act[2]
        s2, eff = A.apply(st, act, ctx, m)
        if trace is not None:
            trace.decision(st, act, eff, scores)
        steps.append({"kind": act[0], "n_exec": eff["n_exec"], "new_behaviour": eff["new_behaviour"]})
        st = s2
        if act[0] == "STOP":
            break
    return st, steps
