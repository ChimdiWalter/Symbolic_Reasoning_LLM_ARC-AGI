"""cast_selective_v2: CAST v1 core modules with genuine leave-one-out, disagreement and stability evidence, explicit
statuses, per-call state reset, and a neural-first attempt-2 insertion rule. Does NOT inherit v1's confirmation claim.

    from cast_selective_v2 import evaluate, insert_attempt2
    rep = evaluate(task)                                  # evidence and per-policy acceptance for every query
    attempts = insert_attempt2(task, neural, policy="tier0")   # neural: [[a1, a2], ...] per query; a1 never changes

Modules (unchanged from cast_v1, same order): M4 symmetry completion (complete predictions only), M2 typed guarded
rewriting, L0 contract-guided search (depth 2, 1,000 executions).
Evidence per module, computed only for a module with a complete fitting candidate:
  folds          for each demonstration i: the module is re-run from scratch on the other demonstrations (state
                 cleared; the held-out output never enters generation, ordering, selection or caches), its SELECTED
                 (top-1) prediction on the held-out input is compared with the held-out output, and its predictions on
                 the real queries are recorded
  genuine_loo    every fold's top-1 prediction equals the held-out output (n_demos >= 2)
  v1_loo         the cast_v1 rule (held-out output among the fold's top 2) - kept for the B1 comparison only
  single_demo_folds   n_demos == 2 (each fold synthesised from ONE demonstration: weak evidence, labelled)
  query_disagreement  fitting programs of the full run disagree on a query (version-space ambiguity); B3 uses the
                      UNION over every module's fitting programs (union_disagreement), so a unanimous module is not
                      accepted while another module's fitting programs predict something else
  fold_agreement      every fold predicts the same query outputs as the full run
  restart_stable      a restart with the reversed enumeration order (views, parameters, instances) selects the same
                      query behaviour
Policies (per query): B1 = complete and v1_loo; B2 = complete and genuine_loo; B3 = B2 and no query disagreement and
fold agreement and restart stability. Fewer than two demonstrations: INSUFFICIENT_VALIDATION_EVIDENCE (never accepted).
Insertion: attempt 1 is always the neural answer. policy "tier0": attempt 2 is replaced only where the neural
attempt 2 is missing or identical to attempt 1 (dominance-safe under per-query best-of-two scoring), by the first
module's complete fitting candidate if it differs from attempt 1; "tier1:B1|B2|B3": attempt 2 is replaced wherever
that policy accepts a candidate that differs from attempt 1 (NOT safe: it can lose a correct neural attempt 2).
Any timeout, error, malformed input or off-main-thread call leaves the neural attempts unchanged.
"""
import signal
import threading
import time

import numpy as np

from . import absdom as D
from . import candidates as CA
from . import grids as G
from . import ops as O
from . import rewrite as RW
from . import search as SR
from . import symmetry as S

VERSION = "cast-selective-v2-1"
ORDER = ("m4", "m2", "l0")
POLICIES = ("B1", "B2", "B3")


class _Timeout(BaseException):
    pass


class _FoldTimeout(BaseException):
    pass


def _clear():
    RW._SCENES.clear()
    S._MAP_CACHE.clear()


# ------------------------------------------------------------------ modules (cast_v1 semantics; optional reversed order)
def _m4(task, reverse=False):
    op = S.SymComplete(0.5, 0.5)
    demos = [(np.asarray(x), np.asarray(y)) for x, y in task["train"]]
    qs = [np.asarray(q) for q in task["test_inputs"]]
    ctx = O.TaskCtx(task["train"], task["test_inputs"])
    thetas = op.domain(ctx)
    if reverse:
        thetas = list(reversed(thetas))
    fits = []
    for th in thetas:
        if any(not D.contains(op.fwd(D.alpha(x), th), y) for x, y in demos):
            continue
        ok = True
        for x, y in demos:
            out = op.apply(x, th)
            if out is None or out.shape != y.shape or not np.array_equal(out, y):
                ok = False
                break
        if not ok:
            continue
        preds, complete = [], []
        for q in qs:
            out = op.apply(q, th)
            preds.append(out)
            complete.append(out is not None and (op.last_trace or {}).get("status") == "COMPLETE")
        fits.append({"program": f"(symcomplete mask={th[0]} crop={th[1]})", "preds": preds, "complete": complete,
                     "cost": 1.0, "order": len(fits), "loo": 0.0})
    return [f for f in fits if all(f["complete"])] or [f for f in fits if any(f["complete"])]


def _m2(task, reverse=False):
    return RW.search(task, views=tuple(reversed(RW.VIEWS)) if reverse else RW.VIEWS)


def _l0(task, reverse=False):
    ctx = O.TaskCtx(task["train"], task["test_inputs"])
    s = SR.Searcher(ctx, O.L0, depth=2, mode="fwdbwd", max_exec=1000, oe=True, max_fits=32)
    if reverse:
        s.instances = list(reversed(s.instances))
    r = s.run()
    return [{"program": " ; ".join(f"{n}{th!r}" for n, th in f["program"]),
             "preds": [None if p is None else np.asarray(p) for p in f["preds"]],
             "complete": [p is not None for p in f["preds"]], "cost": float(len(f["program"])), "order": i}
            for i, f in enumerate(r["fits"])]


MODULES = {"m4": _m4, "m2": _m2, "l0": _l0}


def _ranked(module, task, reverse=False):
    fits = MODULES[module](task, reverse)
    demos = [(np.asarray(x), np.asarray(y)) for x, y in task["train"]]
    qs = [np.asarray(q) for q in task["test_inputs"]]
    groups = CA.rank(fits, {"train": demos, "test_inputs": qs})
    return groups, CA.attempts(groups, len(qs)), fits


def _key(g):
    return None if g is None else (tuple(np.asarray(g).shape), np.asarray(g).astype(np.int64).tobytes())


def _valid_answer(g, q, changes):
    if g is None or not G.valid_grid(np.asarray(g)):
        return False
    g, q = np.asarray(g), np.asarray(q)
    return not (changes and g.shape == q.shape and np.array_equal(g, q))


class _FoldCap:
    """A nested CPU budget for one fold, carved out of the call's remaining CPU budget (ITIMER_VIRTUAL)."""

    def __init__(self, fold_cpu_s):
        self.fold_cpu_s = fold_cpu_s

    def __enter__(self):
        self.remaining = signal.getitimer(signal.ITIMER_VIRTUAL)[0]
        if self.fold_cpu_s is not None:
            self.old = signal.signal(signal.SIGVTALRM, self._boom)
            budget = min(self.remaining, self.fold_cpu_s) if self.remaining > 0 else self.fold_cpu_s
            self.t0 = time.process_time()
            signal.setitimer(signal.ITIMER_VIRTUAL, budget)
        return self

    @staticmethod
    def _boom(signum, frame):                                  # noqa: ARG004
        raise _FoldTimeout()

    def __exit__(self, *exc):
        if self.fold_cpu_s is not None:
            used = time.process_time() - self.t0
            signal.setitimer(signal.ITIMER_VIRTUAL, 0)
            signal.signal(signal.SIGVTALRM, self.old)
            if self.remaining > 0:
                left = self.remaining - used
                if left <= 0:
                    raise _Timeout()
                signal.setitimer(signal.ITIMER_VIRTUAL, left)
        return False


def _module_evidence(module, t, changes, fold_cpu_s):
    groups, atts, fits = _ranked(module, t)
    nq = len(t["test_inputs"])
    ev = {"module": module, "n_fits": len(fits), "n_behaviours": len(groups), "status": "NO_CANDIDATE",
          "candidate": [None] * nq, "program": groups[0]["members"][0]["program"] if groups else None}
    if not groups:
        return ev
    top = groups[0]["preds"]
    comp = groups[0]["complete"]
    cand = [top[j] if (j < len(top) and comp and _valid_answer(top[j], t["test_inputs"][j], changes)) else None
            for j in range(nq)]
    ev["candidate"] = [None if g is None else np.asarray(g).astype(int).tolist() for g in cand]
    if not any(c is not None for c in cand):
        ev["status"] = "INCOMPLETE"
        return ev
    ev["pred_keys"] = [sorted({_key(g["preds"][j])[1].hex() + str(_key(g["preds"][j])[0]) for g in groups
                               if j < len(g["preds"]) and g["preds"][j] is not None}) for j in range(nq)]
    ev["query_disagreement"] = [len(k) > 1 for k in ev["pred_keys"]]
    n = len(t["train"])
    ev["n_demos"] = n
    if n < 2:
        ev["status"] = "INSUFFICIENT_VALIDATION_EVIDENCE"
        return ev
    folds = []
    for i in range(n):
        rest = [d for k, d in enumerate(t["train"]) if k != i]
        sub = {"task_id": "fold", "train": rest, "test_inputs": [t["train"][i][0]] + list(t["test_inputs"])}
        _clear()                                               # nothing cached across folds
        try:
            with _FoldCap(fold_cpu_s):
                _, fa, _ = _ranked(module, sub)
        except _FoldTimeout:
            ev["status"] = "TIMEOUT_IN_FOLD"
            ev["folds"] = folds
            return ev
        y = np.asarray(t["train"][i][1])
        top1 = fa[0][0] if fa[0] else None
        eq = lambda a: a is not None and np.asarray(a).shape == y.shape and np.array_equal(np.asarray(a), y)  # noqa: E731
        fq = [fa[1 + j][0] if fa[1 + j] else None for j in range(nq)]
        folds.append({"held_out": i, "top1_correct": eq(top1), "top2_correct": any(eq(a) for a in fa[0][:2]),
                      "query_agrees": [_key(fq[j]) == _key(cand[j]) for j in range(nq)]})
    ev["folds"] = folds
    ev["v1_loo"] = all(f["top2_correct"] for f in folds)
    ev["genuine_loo"] = all(f["top1_correct"] for f in folds)
    ev["single_demo_folds"] = n == 2
    ev["fold_agreement"] = [all(f["query_agrees"][j] for f in folds) for j in range(nq)]
    _clear()
    g2, _, _ = _ranked(module, t, reverse=True)
    ev["restart_stable"] = bool(g2) and [_key(p) for p in g2[0]["preds"]] == [_key(p) for p in top]
    ev["status"] = "EVIDENCE"
    return ev


def _accept(ev, j, policy):
    if ev.get("status") != "EVIDENCE" or ev["candidate"][j] is None:
        return False
    if policy == "B1":
        return ev["v1_loo"]
    if policy == "B2":
        return ev["genuine_loo"]
    if policy == "B3":
        return (ev["genuine_loo"] and not ev["union_disagreement"][j] and ev["fold_agreement"][j]
                and ev["restart_stable"])
    raise KeyError(policy)


def _norm(task):
    train = [(p["input"], p["output"]) if isinstance(p, dict) else (p[0], p[1]) for p in task["train"]]
    tests = task.get("test_inputs")
    if tests is None:
        tests = [x["input"] if isinstance(x, dict) else x for x in task["test"]]
    for g in [a for a, _ in train] + [b for _, b in train] + list(tests):
        if not G.valid_grid(np.asarray(g)):
            raise ValueError("invalid grid")
    return {"task_id": "task", "train": train, "test_inputs": list(tests)}


class _Caps:
    def __init__(self, cpu_s, wall_s):
        self.cpu_s, self.wall_s = cpu_s, wall_s

    def __enter__(self):
        def boom(signum, frame):                               # noqa: ARG001
            raise _Timeout()
        self.old = (signal.signal(signal.SIGVTALRM, boom), signal.signal(signal.SIGALRM, boom))
        self.old_t = (signal.setitimer(signal.ITIMER_VIRTUAL, self.cpu_s),
                      signal.setitimer(signal.ITIMER_REAL, self.wall_s))
        return self

    def __exit__(self, *exc):
        signal.setitimer(signal.ITIMER_VIRTUAL, 0)
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGVTALRM, self.old[0])
        signal.signal(signal.SIGALRM, self.old[1])
        for which, (val, interval) in ((signal.ITIMER_VIRTUAL, self.old_t[0]), (signal.ITIMER_REAL, self.old_t[1])):
            if val > 0:
                signal.setitimer(which, val, interval)
        return False


def evaluate(task, cpu_s=15.0, wall_s=30.0, fold_cpu_s=None):
    """Evidence for every module and query; never raises. rep["queries"][j] = {"candidate", "candidate_module",
    "accepted": {policy: grid or None}, "accepted_module": {policy: module}}."""
    n_test = len(task.get("test", task.get("test_inputs", [])) or [])
    rep = {"version": VERSION, "status": "OK", "n_demos": None, "modules": {},
           "queries": [{"candidate": None, "candidate_module": None, "accepted": {p: None for p in POLICIES},
                        "accepted_module": {p: None for p in POLICIES}} for _ in range(n_test)]}
    t0, w0 = time.process_time(), time.time()
    if threading.current_thread() is not threading.main_thread():
        rep["status"] = "NO_MAIN_THREAD"
        return rep
    _clear()
    try:
        with _Caps(cpu_s, wall_s):
            t = _norm(task)
            rep["n_demos"] = len(t["train"])
            changes = all(np.asarray(x).shape != np.asarray(y).shape or not np.array_equal(x, y) for x, y in t["train"])
            for module in ORDER:
                _clear()
                ev = _module_evidence(module, t, changes, fold_cpu_s)
                rep["modules"][module] = ev
                if ev["status"] == "TIMEOUT_IN_FOLD":
                    raise _FoldTimeout()
            union = [set() for _ in range(n_test)]
            for ev in rep["modules"].values():
                for j, ks in enumerate(ev.get("pred_keys") or []):
                    union[j] |= set(ks)
            rep["union_disagreement"] = [len(u) > 1 for u in union]
            for module in ORDER:
                ev = rep["modules"][module]
                ev["union_disagreement"] = rep["union_disagreement"]
                for j in range(n_test):
                    q = rep["queries"][j]
                    if q["candidate"] is None and ev["candidate"][j] is not None:
                        q["candidate"], q["candidate_module"] = ev["candidate"][j], module
                    for p in POLICIES:
                        if q["accepted"][p] is None and _accept(ev, j, p):
                            q["accepted"][p], q["accepted_module"][p] = ev["candidate"][j], module
    except _FoldTimeout:
        rep["status"] = "TIMEOUT_IN_FOLD"
    except _Timeout:
        rep["status"] = "TIMEOUT"
    except Exception as e:                                     # noqa: BLE001  fail-safe by contract
        rep["status"] = f"ERROR:{type(e).__name__}"
    finally:
        _clear()
    if rep["status"] != "OK":                                  # abstain everywhere on any failure
        for q in rep["queries"]:
            q.update(candidate=None, candidate_module=None, accepted={p: None for p in POLICIES},
                     accepted_module={p: None for p in POLICIES})
    rep["cpu_s"] = round(time.process_time() - t0, 3)
    rep["wall_s"] = round(time.time() - w0, 3)
    return rep


def insert_attempt2(task, neural, policy="tier0", report=None, **caps):
    """Final [[a1, a2], ...] per query. a1 is always neural[j][0]; on any failure the neural attempts are returned."""
    try:
        out = [list(x) + [None] * (2 - len(x)) if x else [None, None] for x in neural]
        rep = report if report is not None else evaluate(task, **caps)
        if rep["status"] != "OK":
            return out
        for j, q in enumerate(rep["queries"]):
            if j >= len(out):
                break
            a1, a2 = out[j][0], out[j][1]
            if policy == "tier0":
                g = q["candidate"]
                dup = a2 is None or (a1 is not None and _key(a1) == _key(a2))
                if dup and g is not None and _key(g) != _key(a1):
                    out[j][1] = g
            elif policy.startswith("tier1:"):
                g = q["accepted"][policy.split(":")[1]]
                if g is not None and _key(g) != _key(a1):
                    out[j][1] = g
            else:
                raise KeyError(policy)
        return out
    except Exception:                                          # noqa: BLE001
        return [list(x) if x else [None, None] for x in neural]
