"""The bounded, executable action menu (identical for every family and arm).

Per-hypothesis actions on a focus hypothesis h (CORA's typed operators, `llm_writer.search.mutate_cora` and
`llm_writer.search.complete`):
  MUT:PARAMETER / SELECTOR / TRANSFORM / OUTPUT  change a binding or a fragment: re-open the typed slots of that
                                                 operator family and fill them from the demonstration-derived domain
                                                 (`complete.cora_holes`), seeded slot order, round robin, K_ENUM fills
  MUT:REPRESENTATION                             alter the object view (same enumeration over view slots)
  MUT:COMPOSE                                    add/drop/swap a rule, wrap, seq (K_MUT seeded typed proposals)
  MUT:SUBTREE                                    combine fragments: a typed subtree from another memory program
  COMPLETE                                       joint completion of two re-opened slots (`complete._fill_pair`;
                                                 seeded slot pairs, K_COMPLETE programs)
  COMMIT                                         make h's behaviour the first attempt (no execution)
Global: NEW (the frozen proposer's next K_NEW programs: bounded exploration / restart) and STOP.

Every random choice is seeded by (state hash, target key, kind), so the same state and action always produce the
same executable change in every arm (fixed-state replay). Revision semantics of the two attempts:
  mode "revise"   : a new version-space behaviour becomes attempt 1, the old attempt 1 becomes attempt 2;
  mode "preserve" : a new behaviour only replaces attempt 2 (attempt 1 is kept).
Costs are counted in executions requested (cache hits included) and CPU seconds actually spent.
"""
import random
import zlib

from harness import core as C
from llm_writer.search import common as SC
from llm_writer.search import complete as CO
from llm_writer.search import mutate_cora as MC

K_ENUM = 8
K_MUT = 4
K_COMPLETE = 8
K_NEW = 6
ENUM_FAMS = ("PARAMETER", "SELECTOR", "TRANSFORM", "OUTPUT", "REPRESENTATION")


class Ctx:
    """Per-task executor context: CORA's Runner (cache + CPU accounting) and the demonstration-derived library."""

    def __init__(self, task, progs=()):
        self.task = task
        self.runner = SC.Runner(task, "cora")
        try:
            self.lib = MC.Library(task, progs)
        except Exception:                                   # noqa: BLE001
            self.lib = MC.Library(task, ())
        self.n_req = 0
        self._holes = {}

    def holes(self, h):
        if h.key not in self._holes:
            try:
                self._holes[h.key] = CO.cora_holes(h.prog, self.lib)
            except Exception:                               # noqa: BLE001
                self._holes[h.key] = []
        return self._holes[h.key]

    def execute(self, prog, origin, parent=None, op=None, rank=0, lineage=0):
        self.n_req += 1
        res, _ = self.runner.run(prog, origin, parent, op)
        return C.Hyp(res, origin, parent, op, rank, lineage)


def _seed(*xs):
    return zlib.crc32("|".join(map(str, xs)).encode())


def _mutants(h, family, rng, lib, k):
    out = []
    if not MC.mutable(h.prog):
        return out
    for _ in range(k):
        child, label = MC.propose(h.prog, family.split(":")[1], rng, lib)
        if child is not None:
            out.append((child, label))
    return out


def _round_robin(gens, k, label):
    out = []
    while gens and len(out) < k:
        nxt = []
        for g in gens:
            try:
                out.append((next(g), label))
                nxt.append(g)
            except StopIteration:
                pass
            if len(out) >= k:
                break
        gens = nxt
    return out


def _enum_family(h, family, rng, ctx, k):
    holes = [x for x in ctx.holes(h) if x[1] == family]
    rng.shuffle(holes)
    return _round_robin([CO._fill(h.prog, x[3]) for x in holes], k, family)      # noqa: SLF001


def _pairs(h, rng, ctx, k):
    holes = ctx.holes(h)
    if len(holes) < 2:
        return []
    idx = [(a, b) for a in range(len(holes)) for b in range(a + 1, len(holes))]
    rng.shuffle(idx)
    out = []
    for a, b in idx:
        for p in CO._fill_pair(h.prog, holes[a][3], holes[b][3], 2):              # noqa: SLF001
            out.append((p, "COMPLETE"))
            if len(out) >= k:
                return out
    return out


def apply(state, action, ctx, mode="revise"):
    """(new state, effect record). `action` = (kind, hyp index or -1)."""
    kind, i = action
    s = state.copy()
    s.steps += 1
    eff = {"kind": kind, "target": state.hyps[i].key if i >= 0 else None, "n_exec": 0, "cpu": 0.0, "new": [],
           "new_behaviour": False, "attempts_before": list(state.attempts)}
    cpu0, req0 = ctx.runner.cpu, ctx.n_req
    if kind == "STOP":
        pass
    elif kind == "COMMIT":
        q = state.hyps[i].qkey
        s.attempts = [q] + [a for a in state.attempts if a != q][:1]
        s.committed = q
    else:
        if kind == "NEW":
            progs = [(p, "NEW") for p in s.reserve[:K_NEW]]
            s.reserve = s.reserve[K_NEW:]
            parent, lin = None, 0
        else:
            h = state.hyps[i]
            rng = random.Random(_seed(state.hash(), h.key, kind))
            fam = kind.split(":")[-1]
            if kind == "COMPLETE":
                progs = _pairs(h, rng, ctx, K_COMPLETE)
            elif fam in ENUM_FAMS:
                progs = _enum_family(h, fam, rng, ctx, K_ENUM)
            else:
                progs = _mutants(h, kind, rng, ctx.lib, K_MUT)
            parent, lin = h.key, h.lineage + 1
        base_rank = max([x.rank for x in state.hyps], default=0) + 1
        new = []
        for j, (p, label) in enumerate(progs):
            hh = ctx.execute(p, "act:" + kind, parent, label, base_rank + j, lin)
            new.append(hh)
        have_q = {h.qkey for h in state.hyps if h.vs}
        newq = []
        for hh in new:
            if hh.vs and hh.qkey not in have_q and hh.qkey not in newq:
                newq.append(hh.qkey)
        s.add(new)
        if newq:
            eff["new_behaviour"] = True
            if mode == "revise" or not state.attempts:
                s.attempts = ([newq[0]] + [a for a in state.attempts if a != newq[0]])[:2]
            else:
                s.attempts = (state.attempts[:1] + [newq[0]])[:2]
        eff["new"] = [{"key": hh.key, "status": hh.status, "acc": round(hh.acc, 4), "vs": hh.vs, "op": hh.op}
                      for hh in new]
    eff["n_exec"] = ctx.n_req - req0
    eff["cpu"] = round(ctx.runner.cpu - cpu0, 5)
    s.budget = state.budget - eff["n_exec"]
    eff["attempts_after"] = list(s.attempts)
    s.history = state.history + [{"kind": kind, "target": eff["target"], "new_behaviour": eff["new_behaviour"]}]
    return s, eff


def action_name(state, action):
    k, i = action
    return k if i < 0 else f"{k}@{state.hyps[i].key[:10]}"
