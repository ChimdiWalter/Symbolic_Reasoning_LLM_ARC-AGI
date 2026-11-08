"""Typed synthesis state shared by all five families.

A State holds: the visible task (demonstrations and query inputs; never a withheld or hidden output), a capped
hypothesis memory, the current two attempts, the action history and the remaining budget. Every hypothesis is a CORA
program executed by CORA's own executor (`llm_writer.cora_exec.run` through `search.common.Runner`).

- strict version space (vs=True): programs that reproduce EVERY visible demonstration (status FITS);
- search frontier (vs=False): failed or partial programs, labelled separately (never called a version space).
Demonstration-equivalent programs that predict different query outputs are all kept (distinct behaviour keys);
identical-looking states are not merged (equal visible outputs do not prove semantic equivalence).
"""
import hashlib
import json
import zlib

import numpy as np

from harness import paths as P

P.ensure_import_paths()
from llm_writer.search import common as SC   # noqa: E402

SC.ensure_paths()
from llm_writer.search import lang as LG      # noqa: E402

L = LG.get("cora")
CAP = 32
FOCUS = 5
CLASSES = ("program", "seq", "g4program", "symmetry_completion", "pixel_rule", "counting", "generative",
           "panel_reduction")
VIEWS = ("S1", "S2", "S3", "S4", "S5", "S6", "S7")
KINDS = ("FILL:PARAMETER", "FILL:SELECTOR", "FILL:TRANSFORM", "FILL:OUTPUT", "FILL:REPRESENTATION", "MUT:COMPOSE",
         "MUT:SUBTREE", "COMMIT", "NEW", "STOP")
PER_HYP = KINDS[:8]
TOKEN_DIM = 60
GLOBAL_DIM = 34
N_OPHASH = 16


def gkey(g):
    return hashlib.sha1(json.dumps(np.asarray(g).tolist()).encode()).hexdigest()[:16]


def walk_ops(prog):
    """Operator names of a CORA AST (rast N, G4Program, part/ray rules), depth-first."""
    from cora_neural_v2.rast import N
    from cora_neural_v2g4 import program as PG
    ops, depth = [], [0]

    def w(x, d):
        depth[0] = max(depth[0], d)
        if isinstance(x, N):
            ops.append(x.op)
            for a in x.args:
                w(a, d + 1)
        elif isinstance(x, PG.G4Program):
            ops.append("g4program")
            if x.base is not None:
                w(x.base, d + 1)
            for r in x.rules:
                w(r, d + 1)
        elif isinstance(x, (PG.PartRule, PG.RayRule)):
            ops.append(type(x).__name__)
            w(x.sel, d + 1)
        elif isinstance(x, tuple):
            for a in x:
                w(a, d)
    w(prog, 0)
    return ops, depth[0]


class Hyp:
    """One executed hypothesis (immutable after construction)."""
    __slots__ = ("key", "prog", "text", "status", "vs", "acc", "acc_min", "exact", "shape_ok", "prec", "rec",
                 "broken", "remaining", "jac", "preds", "qkey", "dkey", "origin", "parent", "op", "rank", "cpu", "size",
                 "depth", "cls", "view", "nrules", "default_delete", "render_other", "ophash", "lineage")

    def __init__(self, res, origin, parent=None, op=None, rank=0, lineage=0):
        ex = res.ex
        self.key, self.prog, self.origin, self.parent, self.op = res.key, res.prog, origin, parent, op
        self.text = L.render(res.prog) if res.prog is not None else ""
        self.status, self.vs, self.rank, self.cpu, self.lineage = ex.status, ex.status == "FITS", rank, res.cpu, lineage
        per = ex.per_demo or []
        accs, ex_, sh, pr, rc, br, rm = [], [], [], [], [], [], []
        for p in per:
            if p.get("shape_ok"):
                cells = max(1, p.get("cells") or 1)
                accs.append(1.0 - (p.get("wrong") or 0) / cells)
                ex_.append(1.0 if not p.get("wrong") else 0.0)
                sh.append(1.0)
                pr.append(p.get("precision") or 0.0)
                rc.append(p.get("recall") or 0.0)
                br.append((p.get("broken") or 0) / cells)
                rm.append((p.get("remaining") or 0) / cells)
            else:
                accs.append(0.0), ex_.append(0.0), sh.append(0.0), pr.append(0.0), rc.append(0.0)
                br.append(0.0), rm.append(0.0)
        m = (lambda v: float(np.mean(v)) if v else 0.0)
        self.acc, self.acc_min, self.exact, self.shape_ok = m(accs), (min(accs) if accs else 0.0), m(ex_), m(sh)
        self.prec, self.rec, self.broken, self.remaining = m(pr), m(rc), m(br), m(rm)
        den = (ex.fixed or 0) + (ex.broken or 0) + (ex.remaining or 0)
        self.jac = 1.0 if self.vs else ((ex.fixed or 0) / den if den else 0.0)   # changed-cell Jaccard (same-shape)
        self.preds = [np.asarray(p).tolist() for p in ex.preds] if self.vs and ex.preds else None
        self.qkey = SC.behaviour_key(self.preds) if self.preds else None
        outs = getattr(ex, "outs", None) or []
        self.dkey = hashlib.sha1("#".join("none" if o is None else gkey(o) for o in outs).encode()).hexdigest()[:16]
        ops, self.depth = walk_ops(res.prog) if res.prog is not None else ([], 0)
        self.size = len(ops)
        top = ops[0] if ops else "none"
        self.cls = top if top in CLASSES else "other"
        self.view = getattr(res.prog, "view", None) if top == "g4program" else (
            res.prog.args[0] if top == "program" and res.prog.args and isinstance(res.prog.args[0], str) else None)
        self.nrules = ops.count("rule") + ops.count("rule_with") + ops.count("PartRule") + ops.count("RayRule")
        self.default_delete = 1.0 if top == "program" and "delete" in str(res.prog.args[2:3]) else 0.0
        self.render_other = 1.0 if top == "program" and "same_as_input" not in str(res.prog.args[3:4]) else 0.0
        h = np.zeros(N_OPHASH, np.float32)
        for o in ops:
            h[zlib.crc32(o.encode()) % N_OPHASH] += 1.0
        self.ophash = h / max(1.0, h.sum())


class State:
    """Hypothesis memory plus attempts, history and budget. Copy-on-write lists (one-step outcomes branch cheaply)."""

    def __init__(self, task, hyps, reserve=(), budget=60, attempts=None, history=(), steps=0, committed=None):
        self.task = task                       # visible task only
        self.hyps = list(hyps)
        self.reserve = list(reserve)           # the frozen proposer's next programs (NEW consumes them in order)
        self.budget, self.steps, self.committed = budget, steps, committed
        self.history = list(history)
        self.attempts = list(attempts) if attempts is not None else self.default_attempts()

    def copy(self):
        return State(self.task, self.hyps, self.reserve, self.budget, self.attempts, self.history, self.steps,
                     self.committed)

    # -------------------------------------------------- version space / frontier
    def vs(self):
        return [h for h in self.hyps if h.vs]

    def behaviours(self):
        """Distinct query behaviours of the strict version space, in proposer order (first member represents)."""
        seen, out = set(), []
        for h in sorted(self.vs(), key=lambda x: x.rank):
            if h.qkey not in seen:
                seen.add(h.qkey)
                out.append(h)
        return out

    def default_attempts(self):
        return [h.qkey for h in self.behaviours()[:2]]

    def preds_of(self, qkey):
        for h in self.hyps:
            if h.qkey == qkey:
                return h.preds
        return None

    def focus(self):
        """The hypotheses that per-hypothesis actions may target (fixed rule, bounds cost): up to two distinct VS
        behaviours (proposer order), the proposer's two top-ranked frontier members, then frontier members by
        changed-cell Jaccard (identity-like programs score 0), FOCUS in all."""
        fr = [h for h in self.hyps if not h.vs and h.status != "INVALID"]
        cand = self.behaviours()[:2] + sorted(fr, key=lambda x: x.rank)[:2] + sorted(fr, key=lambda x: (-x.jac, -x.acc,
                                                                                                          x.rank))
        out, seen = [], set()
        for h in cand:
            if h.key not in seen:
                seen.add(h.key)
                out.append(h)
        return out[:FOCUS]

    def add(self, new):
        """Insert executed hypotheses (dedup by canonical key only); enforce CAP by dropping the weakest frontier
        members, then VS members whose behaviour is already represented; distinct VS behaviours are never dropped."""
        have = {h.key for h in self.hyps}
        self.hyps = self.hyps + [h for h in new if h.key not in have]
        if len(self.hyps) <= CAP:
            return
        beh = {h.key for h in self.behaviours()}
        keep = [h for h in self.hyps if h.key in beh or h.qkey in self.attempts]
        rest = sorted([h for h in self.hyps if h.key not in {k.key for k in keep}],
                      key=lambda x: (not x.vs, -x.jac, -x.acc, x.rank))
        self.hyps = (keep + rest)[:max(CAP, len(keep))]

    def hash(self):
        s = json.dumps([gkey(a) + gkey(b) for a, b in self.task["train"]] + [gkey(t) for t in self.task["test_inputs"]]
                       + sorted(h.key for h in self.hyps) + list(map(str, self.attempts)) + [self.budget, self.steps])
        return hashlib.sha256(s.encode()).hexdigest()[:20]

    # -------------------------------------------------- features (observations only)
    def token_features(self):
        hs, n = self.hyps, max(1, len(self.hyps))
        vs = [h for h in hs if h.vs]
        nvs = max(1, len(vs))
        dcount, qcount = {}, {}
        for h in hs:
            dcount[h.dkey] = dcount.get(h.dkey, 0) + 1
        for h in vs:
            qcount[h.qkey] = qcount.get(h.qkey, 0) + 1
        major = max(qcount, key=qcount.get) if qcount else None
        acted = {}
        for a in self.history:
            acted[a["target"]] = acted.get(a["target"], 0) + 1
        qin = [np.asarray(t) for t in self.task["test_inputs"]]
        X = np.zeros((len(hs), TOKEN_DIM), np.float32)
        for i, h in enumerate(hs):
            x = X[i]
            x[0] = h.vs
            x[1], x[2], x[3] = h.status == "INCOMPLETE", h.status == "ERROR", h.status == "INVALID"
            x[4], x[5], x[6], x[7] = h.acc, h.acc_min, h.exact, h.shape_ok
            x[8], x[9], x[10], x[11] = h.prec, h.rec, h.broken, h.remaining
            x[12], x[13] = min(h.size, 80) / 40.0, min(h.nrules, 8) / 4.0
            x[14] = h.jac
            if h.cls in CLASSES:
                x[15 + CLASSES.index(h.cls)] = 1.0
            x[23] = h.cls == "other"
            if h.view in VIEWS:
                x[24 + VIEWS.index(h.view)] = 1.0
            x[31] = h.view not in VIEWS
            x[32], x[33] = h.default_delete, h.render_other
            x[34] = min(h.rank, 64) / 32.0
            x[35] = dcount[h.dkey] / n
            if h.vs:
                x[36] = qcount[h.qkey] / nvs
                x[37] = h.qkey == major
                ch, same = [], []
                for p, q in zip(h.preds, qin):
                    p = np.asarray(p)
                    same.append(p.shape == q.shape)
                    ch.append(float((p != q).mean()) if p.shape == q.shape else 1.0)
                x[38], x[39] = float(np.mean(ch)), float(np.mean(same))
            x[40] = bool(self.attempts) and h.qkey == self.attempts[0]
            x[41] = len(self.attempts) > 1 and h.qkey == self.attempts[1]
            x[42], x[43] = min(h.lineage, 3) / 3.0, min(acted.get(h.key, 0), 3) / 3.0
            x[44:44 + N_OPHASH] = h.ophash
        return X

    def relations(self):
        """Pairwise agreement: [same visible outputs, same query behaviour (both in the version space)]."""
        hs = self.hyps
        d = np.array([h.dkey for h in hs])
        q = np.array([h.qkey if h.vs else f"~{i}" for i, h in enumerate(hs)])
        return np.stack([(d[:, None] == d[None, :]), (q[:, None] == q[None, :])], -1).astype(np.float32)

    def global_features(self, budget0=60):
        hs, vs, beh = self.hyps, self.vs(), self.behaviours()
        g = np.zeros(GLOBAL_DIM, np.float32)
        g[0], g[1], g[2] = len(hs) / CAP, len(vs) / CAP, min(len(beh), 8) / 8.0
        if vs:
            c = np.array([sum(1 for h in vs if h.qkey == b.qkey) for b in beh], float)
            p = c / c.sum()
            g[3] = float(-(p * np.log(p)).sum())
        g[4] = max([h.acc for h in hs], default=0.0)
        g[5], g[6] = len(vs) == 0, len(beh) >= 2
        g[7], g[8] = self.budget / max(1, budget0), min(self.steps, 6) / 6.0
        tr = self.task["train"]
        g[9] = len(tr) / 5.0
        g[10] = any(np.asarray(a).shape != np.asarray(b).shape for a, b in tr)
        g[11] = float(np.mean([np.asarray(b).size for _, b in tr])) / 900.0
        for a in self.history:
            k = KINDS.index(a["kind"])
            if k < 9:
                g[12 + k] += 1.0 / 3.0
                g[22 + k] += (1.0 / 3.0) if a.get("new_behaviour") else 0.0
        g[32] = len(self.reserve) / 24.0
        g[33] = bool(self.attempts)
        return g

    def available(self):
        """[(kind, hyp index or -1)] in a fixed order: per-hypothesis actions on the focus set, COMMIT on distinct VS
        behaviours not already first, NEW while the proposer reserve lasts, STOP always."""
        idx = {h.key: i for i, h in enumerate(self.hyps)}
        acts = []
        for h in self.focus():
            for k in PER_HYP[:7]:
                acts.append((k, idx[h.key]))
        for h in self.behaviours()[:6]:
            if not self.attempts or h.qkey != self.attempts[0]:
                acts.append(("COMMIT", idx[h.key]))
        if self.reserve:
            acts.append(("NEW", -1))
        acts.append(("STOP", -1))
        return acts


def attempts_preds(state):
    return [state.preds_of(q) for q in state.attempts]


def score(preds_list, truths):
    """Exact pass@k bookkeeping against withheld truths (labels are passed in; they are never part of a state).
    Returns per-output pass@2, all-output pass@2, all-output pass@1."""
    per = []
    for j, t in enumerate(truths):
        T = np.asarray(t)
        per.append(any(p is not None and j < len(p) and np.asarray(p[j]).shape == T.shape and
                       np.array_equal(np.asarray(p[j]), T) for p in preds_list[:2]))
    p1 = bool(preds_list) and preds_list[0] is not None and all(
        np.asarray(preds_list[0][j]).shape == np.asarray(t).shape and np.array_equal(np.asarray(preds_list[0][j]),
                                                                                      np.asarray(t))
        for j, t in enumerate(truths))
    return {"per_output": per, "all2": bool(per) and all(per), "all1": bool(p1), "frac2": float(np.mean(per)) if per else 0.0}
