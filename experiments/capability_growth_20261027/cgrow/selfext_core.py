"""Domain-neutral self-extension core (the S1 algorithm), driven by a domain plug-in. Used by U3 (lists) and,
through the grid plug-in, checked against S1's recorded outcomes.

Plug-in interface (attributes and methods):
  BASE_BUDGET, BASE_CPU, NOVELTY_BUDGET, NOVELTY_CPU, PROBE_FACTOR
  g0()                      -> a fresh starting grammar
  with_structure(st)        -> g0 plus the structure as one production (all its parameter values)
  search(g, train, qs, budget, cpu_cap, want) -> dict with fit, preds (two attempts), program, cpu_s, calls,
                               level_complete
  probes                    -> list of probe inputs (novelty gate)
  defined(v)                -> whether a structure output counts as defined
  structures(), seeded_order(seed), consistent(st, pairs) -> parameter values mapping every hole input to its target
  unary_ops(g)              -> {name: callable} unary operations of g (controller sketches); invertible ones are
                               found by probing with invert_tests
  similarity(x, y)          -> share of the target explained by the hole input (sketch ranking)

S1 rules kept identically: controller decision (deeper search at PROBE_FACTOR x the budget; a fit means
CONTINUE_PROGRAM_SEARCH, otherwise INVENT_NEW_OPERATION); sketches = identity, outer B(?(x)) and inner ?(A(x)) for
invertible unary operations, ranked by similarity, identity plus the two best kept; candidates = for each sketch
in rank order, every structure in the arm's order with its consistent parameter values (first occurrence kept);
gates = novelty (a witness for every defined parameter value means search shortcut), retry (at most M_RETRIES),
regression on previously solved tasks (lost fit or changed first prediction means rolled back), validation on the
pool (one new fit means promoted; none means quarantined); stop at the first promoted; S-enum stops once the
charged CPU reaches ENUM_CPU; cached results are charged at the CPU of their first computation.
"""
import time

M_RETRIES = 3
ENUM_CPU = 60.0


# ------------------------------------------------------------------ controller
def invertible(plugin, g):
    ops = plugin.unary_ops(g)
    out = {}
    for a, fa in ops.items():
        for b, fb in ops.items():
            try:
                if all(fb(fa(t)) == t for t in plugin.invert_tests) and any(fa(t) != t for t in plugin.invert_tests):
                    out[a] = b
                    break
            except Exception:                                            # noqa: BLE001
                continue
    return out


def sketches(plugin, g, train, extended=False):
    ops = plugin.unary_ops(g)
    inv = invertible(plugin, g)
    xs, ys = [a for a, _ in train], [b for _, b in train]
    cands = [{"form": "?(I)", "outer": None, "inner": None, "pairs": list(zip(xs, ys))}]

    def ok(pairs):
        return all(plugin.defined(x) and plugin.defined(y) for x, y in pairs)
    for b, binv in inv.items():
        try:
            p = [(x, ops[binv](y)) for x, y in zip(xs, ys)]
            if ok(p):
                cands.append({"form": "B(?(I))", "outer": b, "inner": None, "pairs": p})
        except Exception:                                                # noqa: BLE001
            pass
    inner_ops = list(ops) if extended else list(inv)
    if extended:
        for name, f in plugin.unary_ops_with_constants(g).items():
            if name not in ops:
                ops[name] = f
                inner_ops.append(name)
    for a in inner_ops:
        try:
            p = [(ops[a](x), y) for x, y in zip(xs, ys)]
            if ok(p):
                cands.append({"form": "?(A(I))", "outer": None, "inner": a, "pairs": p})
        except Exception:                                                # noqa: BLE001
            pass
    for c in cands:
        c["score"] = round(sum(plugin.similarity(x, y) for x, y in c["pairs"]) / len(c["pairs"]), 4)
    ident = cands[0]
    rest = sorted(cands[1:], key=lambda c: (-c["score"], c["outer"] or "", c["inner"] or ""))
    return sorted([ident] + rest[:2], key=lambda c: -c["score"])


def analyze(plugin, task, extended=False):
    g = plugin.g0()
    base = plugin.search(g, task["train"], task["test_inputs"], plugin.BASE_BUDGET, plugin.BASE_CPU, 2)
    rec = {"base": {k: base[k] for k in ("fit", "program", "level_complete", "stop", "calls", "cpu_s")},
           "base_preds": base["preds"]}
    if base["fit"]:
        rec.update(status="solved", decision="NONE", level=None)
        return rec
    deep = plugin.search(g, task["train"], task["test_inputs"], plugin.BASE_BUDGET * plugin.PROBE_FACTOR,
                         plugin.BASE_CPU * plugin.PROBE_FACTOR, 2)
    rec["probe_deeper_search"] = {k: deep[k] for k in ("fit", "program", "level_complete", "stop", "calls", "cpu_s")}
    rec["sketches"] = sketches(plugin, g, task["train"])
    rec["sketches_ext"] = sketches(plugin, g, task["train"], extended=True)
    if deep["fit"]:
        rec.update(status="solved_by_deeper_search", decision="CONTINUE_PROGRAM_SEARCH", level="search")
    else:
        rec.update(status="unresolved", decision="INVENT_NEW_OPERATION", level="operation")
    return rec


# ------------------------------------------------------------------ gates (cached and charged)
class Gates:
    def __init__(self, plugin, tasks, solved, base_preds, pool, cache=None):
        self.p, self.tasks, self.solved, self.base_preds, self.pool = plugin, tasks, solved, base_preds, pool
        self.c = cache if cache is not None else {"nov": {}, "retry": {}, "reg": {}}
        self.st = {s.sid: s for s in plugin.structures()}

    def novelty(self, sid):
        if sid not in self.c["nov"]:
            t0 = time.process_time()
            st, wit, defined = self.st[sid], [], 0
            for th in st.thetas():
                pairs = [(x, st(x, *th)) for x in self.p.probes]
                pairs = [(x, y) for x, y in pairs if y is not None and self.p.defined(y)]
                if len(pairs) < 4:
                    continue
                defined += 1
                r = self.p.search(self.p.g0(), pairs[:-1], [pairs[-1][0]], self.p.NOVELTY_BUDGET, self.p.NOVELTY_CPU, 1)
                if r["fit"] and r["preds"] and self.p.same(r["preds"][0][0], pairs[-1][1]):
                    wit.append({"theta": list(th), "program": r["program"]})
            self.c["nov"][sid] = {"duplicate": bool(defined) and len(wit) == defined, "witnesses": wit,
                                  "cpu_s": round(time.process_time() - t0, 3)}
        return self.c["nov"][sid]

    def retry(self, sid, tid):
        k = (sid, tid)
        if k not in self.c["retry"]:
            t = self.tasks[tid]
            r = self.p.search(self.p.with_structure(self.st[sid]), t["train"], t["test_inputs"], self.p.BASE_BUDGET,
                              self.p.BASE_CPU, 2)
            self.c["retry"][k] = {"fit": r["fit"], "preds": r["preds"], "program": r["program"], "cpu_s": r["cpu_s"],
                                  "calls": r["calls"]}
        return self.c["retry"][k]

    def regression(self, sid):
        if sid not in self.c["reg"]:
            t0 = time.process_time()
            lost, changed = [], []
            for tid in self.solved:
                r = self.retry(sid, tid)
                if not r["fit"]:
                    lost.append(tid)
                elif self.base_preds.get(tid) is not None and (not r["preds"] or self.base_preds[tid] not in r["preds"]):
                    changed.append(tid)
            self.c["reg"][sid] = {"lost_fit": lost, "changed_prediction": changed, "checked": len(self.solved),
                                  "cpu_s": round(time.process_time() - t0, 3)}
        return self.c["reg"][sid]

    def promote(self, sid, tid):
        reg = self.regression(sid)
        cpu = reg["cpu_s"]
        if reg["lost_fit"] or reg["changed_prediction"]:
            return {"decision": "rolled_back", "regression": reg, "validation": None, "cpu_s": cpu}
        tried, first = 0, None
        for q in self.pool:
            if q == tid:
                continue
            tried += 1
            r = self.retry(sid, q)
            cpu += r["cpu_s"]
            if r["fit"]:
                first = {"task": q, "program": r["program"]}
                break
        return {"decision": "promoted" if first else "quarantined", "regression": reg,
                "validation": {"tried": tried, "first_new_fit": first}, "cpu_s": round(cpu, 3)}


# ------------------------------------------------------------------ arms
def spec_candidates(plugin, order, sks):
    seen, out = set(), []
    for rank, sk in enumerate(sks):
        for st in order:
            if st.sid in seen:
                continue
            ths = plugin.consistent(st, sk["pairs"])
            if ths:
                seen.add(st.sid)
                out.append({"sid": st.sid, "thetas": [list(t) for t in ths], "sketch_rank": rank,
                            "sketch_form": sk["form"]})
    return out


def run_spec_unit(G, tid, cands):
    rows, retries, cpu, promoted = [], 0, 0.0, None
    for c in cands:
        nov = G.novelty(c["sid"])
        cpu += nov["cpu_s"]
        row = dict(c, duplicate=nov["duplicate"])
        if nov["duplicate"]:
            row["outcome"] = "search_shortcut"
            rows.append(row)
            continue
        if retries >= M_RETRIES:
            break
        retries += 1
        r = G.retry(c["sid"], tid)
        cpu += r["cpu_s"]
        row.update(fit=r["fit"], preds=r["preds"], program=r["program"])
        if r["fit"]:
            pr = G.promote(c["sid"], tid)
            cpu += pr["cpu_s"]
            row.update(promotion=pr["decision"], validation=pr["validation"],
                       regression={k: pr["regression"][k] for k in ("lost_fit", "changed_prediction", "checked")},
                       outcome="fits_motivating_task")
            rows.append(row)
            if pr["decision"] == "promoted":
                promoted = c["sid"]
                break
        else:
            row["outcome"] = "no_fit_on_motivating_task"
            rows.append(row)
    return {"rows": rows, "retries": retries, "cpu_s": round(cpu, 2), "promoted": promoted, "n_candidates": len(cands)}


def run_enum_unit(G, tid, order):
    rows, cpu, promoted, retries = [], 0.0, None, 0
    for st in order:
        if cpu >= ENUM_CPU:
            break
        nov = G.novelty(st.sid)
        cpu += nov["cpu_s"]
        if nov["duplicate"]:
            continue
        retries += 1
        r = G.retry(st.sid, tid)
        cpu += r["cpu_s"]
        if r["fit"]:
            pr = G.promote(st.sid, tid)
            cpu += pr["cpu_s"]
            rows.append({"sid": st.sid, "fit": True, "preds": r["preds"], "program": r["program"],
                         "promotion": pr["decision"], "outcome": "fits_motivating_task"})
            if pr["decision"] == "promoted":
                promoted = st.sid
                break
    return {"rows": rows, "retries": retries, "cpu_s": round(cpu, 2), "promoted": promoted, "structures_tried": retries}
