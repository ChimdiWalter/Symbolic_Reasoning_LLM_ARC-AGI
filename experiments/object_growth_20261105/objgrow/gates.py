"""The promotion gates for object-level candidates: the construction test's gates (cgrow/selfext_core.py Gates:
retry, regression, validation; cached and charged at the CPU of the first computation), with the novelty gate of
this study, on the natural-task plug-in (ngrow/plugin.py: A2's full arc-dsl grammar as G0, A2's search).

An added operation is one production (Grid) -> Grid, head "f:obj_<10 hex>", cost 3 and charge 1 (the existing
protocol's cost rules for an added structure).

Novelty. A candidate is rejected as a search shortcut when a G0 program of cost at most NOVELTY_MAX_COST (A2's
integer cost levels), found by A2's search within NOVELTY_BUDGET executions and NOVELTY_CPU seconds on the probe
grids (the construction test's 12 seeded probe grids plus the unit's own demonstration inputs), reproduces the
candidate on every probe where it is defined and predicts it on the last one. Fewer than 4 defined probes: the gate
cannot decide and the candidate passes (recorded).
Retry: the unit's task searched again with G0 plus the candidate at the base budget (at most M_RETRIES per unit).
Regression: on U, the benchmark's source tasks G0 solves at the base budget (a lost fit or a changed first
prediction means rolled back). Validation: the benchmark's other unsolved source tasks in sha256("pool:" + id)
order, at most V_MAX tried; one new fit means promoted, none means quarantined (task-local).
"""
import time

from objgrow import env as E                                                     # noqa: F401  (import paths)
from objgrow import edits as ED
from ngrow import plugin as PL
from cgrow import lang0 as L0, selfext_core as C
from a2 import bus as B, arcdsl as D

NOVELTY_MAX_COST = 7
NOVELTY_BUDGET, NOVELTY_CPU = 200_000, 10.0
V_MAX = 30
M_RETRIES = 3
ADDED_COST = L0.NEW_COST                       # 3


class ObjPlugin(PL.NaturalPlugin):
    """The natural plug-in with object-level operations as productions (a grown grammar = G0 + ops)."""

    def __init__(self, g0b=None, ops=()):
        super().__init__(g0b)
        self.ops = list(ops)

    def g0(self):
        g = self.b()
        for op in self.ops:
            L0.add_production(g, op.head, ED.production_fn(op), 0, cost=ADDED_COST)
        return g

    def with_structure(self, op):
        g = self.g0()
        L0.add_production(g, op.head, ED.production_fn(op), 0, cost=ADDED_COST)
        return g

    def novelty_search(self, g, pairs, qs):
        t0 = time.process_time()
        r = B.search(g, pairs, qs, budget=NOVELTY_BUDGET, max_size=NOVELTY_MAX_COST, cpu_cap=NOVELTY_CPU, want=1)
        return {"fit": bool(r.solved), "program": D.show(r.program) if r.program else None,
                "preds": [[tuple(tuple(row) for row in g_) for g_ in att] for att in r.preds] if r.preds else None,
                "level_complete": r.level, "stop": r.stop, "calls": r.calls,
                "cpu_s": round(time.process_time() - t0, 3)}


class ObjGates(C.Gates):
    """The core's cached gates over object-level operations registered on demand (sid -> op)."""

    def __init__(self, plugin, tasks, solved, base_preds, pool, cache=None):
        self.p, self.tasks, self.solved, self.base_preds, self.pool = plugin, tasks, solved, base_preds, pool
        self.c = cache if cache is not None else {"nov": {}, "retry": {}, "reg": {}, "ops": {}}
        self.c.setdefault("ops", {})
        self.st = {}
        for sid, d in self.c["ops"].items():
            self.st[sid] = ED.ObjOp.from_json(d)
        self.used = set()
        self.solved_set = set(solved)

    def register(self, op):
        self.st[op.sid] = op
        self.c["ops"][op.sid] = op.to_json()

    def novelty(self, sid, tid=None):
        k = (sid, tid)
        self.used.add(("nov", sid, tid))
        if k not in self.c["nov"]:
            t0 = time.process_time()
            op = self.st[sid]
            probes = list(self.p.probes) + ([x for x, _ in self.tasks[tid]["train"]] if tid else [])
            pairs = [(x, op(x)) for x in probes]
            pairs = [(x, y) for x, y in pairs if y is not None and self.p.defined(y)]
            if len(pairs) < 4:
                self.c["nov"][k] = {"duplicate": False, "undecidable": True, "defined": len(pairs),
                                    "witness": None, "cpu_s": round(time.process_time() - t0, 3)}
            else:
                r = self.p.novelty_search(self.p.g0(), pairs[:-1], [pairs[-1][0]])
                dup = bool(r["fit"] and r["preds"] and self.p.same(r["preds"][0][0], pairs[-1][1]))
                self.c["nov"][k] = {"duplicate": dup, "undecidable": False, "defined": len(pairs),
                                    "witness": r["program"] if dup else None, "level_complete": r["level_complete"],
                                    "cpu_s": round(time.process_time() - t0, 3)}
        return self.c["nov"][k]

    def retry(self, sid, tid):
        if tid not in self.solved_set:
            self.used.add(("retry", sid, tid))
        return super().retry(sid, tid)

    def regression(self, sid):
        self.used.add(("reg", sid))
        return super().regression(sid)

    def promote(self, sid, tid):
        reg = self.regression(sid)
        cpu = reg["cpu_s"]
        if reg["lost_fit"] or reg["changed_prediction"]:
            return {"decision": "rolled_back", "regression": reg, "validation": None, "cpu_s": cpu}
        tried, first = 0, None
        for q in self.pool:
            if q == tid:
                continue
            if tried >= V_MAX:
                break
            tried += 1
            r = self.retry(sid, q)
            cpu += r["cpu_s"]
            if r["fit"]:
                first = {"task": q, "program": r["program"]}
                break
        return {"decision": "promoted" if first else "quarantined", "regression": reg,
                "validation": {"tried": tried, "first_new_fit": first}, "cpu_s": round(cpu, 3)}

    def charged(self, keys):
        tot = 0.0
        for k in keys:
            if k[0] == "nov":
                tot += self.c["nov"][(k[1], k[2])]["cpu_s"]
            elif k[0] == "retry":
                tot += self.c["retry"][(k[1], k[2])]["cpu_s"]
            else:
                tot += self.c["reg"][k[1]]["cpu_s"]
        return round(tot, 3)


def run_unit(G, tid, cands):
    """The construction test's unit loop (selfext_core.run_spec_unit) over object-level candidates."""
    rows, retries, cpu, promoted = [], 0, 0.0, None
    for c in cands:
        op = c["op"]
        G.register(op)
        nov = G.novelty(op.sid, tid)
        cpu += nov["cpu_s"]
        row = {"sid": op.sid, "head": op.head, "expr": op.expr(), "hole_rank": c["hole_rank"],
               "hole_form": c["hole_form"], "view": c.get("view"), "loo": c["loo"], "group": c["group"],
               "duplicate": nov["duplicate"], "novelty_undecidable": nov.get("undecidable", False),
               "novelty_witness": nov.get("witness")}
        if nov["duplicate"]:
            row["outcome"] = "search_shortcut"
            rows.append(row)
            continue
        if retries >= M_RETRIES:
            row["outcome"] = "not_retried_cap"
            rows.append(row)
            continue
        retries += 1
        r = G.retry(op.sid, tid)
        cpu += r["cpu_s"]
        row.update(fit=r["fit"], preds=r["preds"], program=r["program"], retry_cpu_s=r["cpu_s"])
        if r["fit"]:
            pr = G.promote(op.sid, tid)
            cpu += pr["cpu_s"]
            row.update(promotion=pr["decision"], validation=pr["validation"],
                       regression={k: pr["regression"][k] for k in ("lost_fit", "changed_prediction", "checked")},
                       outcome="fits_motivating_task")
            rows.append(row)
            if pr["decision"] == "promoted":
                promoted = op.sid
                break
        else:
            row["outcome"] = "no_fit_on_motivating_task"
            rows.append(row)
    return {"rows": rows, "retries": retries, "gate_cpu_s": round(cpu, 3), "promoted": promoted,
            "n_candidates": len(cands)}
