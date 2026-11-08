"""Test U3 (u3_list_functions/PROTOCOL.md): S1's failure-specified construction on BIG-bench list_functions.

    python -m cgrow.u3.run_u3 build              construction: full-DSL search, deletion rule, partitions, records
    python -m cgrow.u3.run_u3 arms               all arms through cgrow/selfext_core.py
    python -m cgrow.u3.run_u3 evaluate           task-level scoring, results.json, reports/TEST_U3_REPORT.md
Outputs under u3_list_functions/ (build/, arms/, eval/) and reports/.
"""
import hashlib
import json
import math
import os
import pickle
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, HERE)
from cgrow import paths as P, selfext_core as C                          # noqa: E402
from cgrow.u3 import listdsl as LD, lschema as LS, plugin as PL          # noqa: E402

U3 = os.path.join(P.HERE, "u3_list_functions")
DATA = os.path.join(U3, "data", "concepts.json")
SALT = "u3-20261102"
N_DEMO, N_QUERY = 5, 3
N_DELETE = 4
QUOTA_M, QUOTA_V, QUOTA_E = 3, 2, 6
N_U, N_D = 14, 4
SEEDS = (0, 1, 2)
C7M_CPU = 150.0
ARMS = ("S-hole", "S-hole-ext", "S-demo", "S-shuffled", "S-enum")


def h(s):
    return hashlib.sha256((SALT + "|" + s).encode()).hexdigest()


def sha_file(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def dump(path, obj):
    with P.open_write(path) as f:
        json.dump(obj, f, indent=1, sort_keys=True, default=list)


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def concept_task(ex):
    tr = [(tuple(a), tuple(b)) for a, b in ex[:N_DEMO]]
    qs = [tuple(a) for a, _ in ex[N_DEMO:N_DEMO + N_QUERY]]
    ys = [tuple(b) for _, b in ex[N_DEMO:N_DEMO + N_QUERY]]
    return {"train": tr, "test_inputs": qs}, ys


def correct(preds, ys):
    return bool(preds) and any([tuple(p) for p in att] == [tuple(y) for y in ys] for att in preds)


# ------------------------------------------------------------------ build (evaluator role, before any arm)
def build():
    out = os.path.join(U3, "build")
    os.makedirs(out, exist_ok=True)
    data = load(DATA)
    full_path = os.path.join(out, "full_dsl_search.json")
    full = load(full_path) if os.path.exists(full_path) else {}
    gfull = LD.Grammar(())
    for c in sorted(data):
        if c in full:
            continue
        task, ys = concept_task(data[c])
        r = LD.search(gfull, task["train"], task["test_inputs"])
        full[c] = {"fit": r["fit"], "correct": r["fit"] and correct(r["preds"], ys), "program": r["program"],
                   "tree": r["program_tree"], "level": r["level_complete"], "cpu_s": r["cpu_s"]}
        dump(full_path, full)
    solved = [c for c in sorted(data) if full[c]["correct"]]

    def tree(t):
        return tuple(tree(x) if isinstance(x, list) else x for x in t) if isinstance(t, list) else t
    usage = {op: sum(LD.uses(tree(full[c]["tree"]), {op}) for c in solved) for op in LD.DELETABLE}
    plug_full = PL.ListPlugin(())
    chosen, gap_log = [], []
    for op in sorted(LD.DELETABLE, key=lambda o: (-usage[o], o)):
        if len(chosen) >= N_DELETE:
            break
        if usage[op] == 0:
            break
        pg = PL.ListPlugin(tuple(chosen) + (op,))
        a, r, f = LD.OPS[op]
        thetas = [()] if a == ("L",) else [(k,) for k in range(10)]
        defined, wit = 0, 0
        for th in thetas:
            pairs = []
            for x in pg.probes:
                try:
                    pairs.append((x, LD.apply_op(f, "L", [x] + list(th))))
                except LD.Undefined:
                    pass
            if len(pairs) < 4:
                continue
            defined += 1
            res = pg.search(pg.g0(), pairs[:-1], [pairs[-1][0]], pg.NOVELTY_BUDGET, pg.NOVELTY_CPU, 1)
            wit += bool(res["fit"] and res["preds"] and tuple(res["preds"][0][0]) == tuple(pairs[-1][1]))
        gap = not (defined and wit == defined)
        gap_log.append({"op": op, "usage": usage[op], "defined_values": defined, "reproduced_values": wit, "gap": gap})
        if gap:
            chosen.append(op)
    plug = PL.ListPlugin(tuple(chosen))
    fam = {}
    for c in solved:
        t = tree(full[c]["tree"])
        used = [op for op in chosen if LD.uses(t, {op})]
        if len(used) == 1:
            fam.setdefault(used[0], []).append(c)
    g0_path = os.path.join(out, "g0_search.json")
    g0 = load(g0_path) if os.path.exists(g0_path) else {}
    for c in sorted(data):
        if c in g0:
            continue
        task, ys = concept_task(data[c])
        r = plug.search(plug.g0(), task["train"], task["test_inputs"], plug.BASE_BUDGET, plug.BASE_CPU, 2)
        g0[c] = {"fit": r["fit"], "correct": r["fit"] and correct(r["preds"], ys), "program": r["program"],
                 "cpu_s": r["cpu_s"]}
        dump(g0_path, g0)
    parts, assigned, ref_ok, d_checked = {}, set(), {}, {}
    for op in chosen:
        elig = []
        for c in sorted(fam.get(op, []), key=lambda c: h("fam:" + c)):
            if g0[c]["fit"]:
                continue
            task, ys = concept_task(data[c])
            r = plug.search(plug.with_reference(op), task["train"], task["test_inputs"], plug.BASE_BUDGET,
                            plug.BASE_CPU, 2)
            ref_ok[c] = bool(r["fit"] and correct(r["preds"], ys))
            if ref_ok[c]:
                elig.append(c)
        parts[op] = {"M": elig[:QUOTA_M], "V": elig[QUOTA_M:QUOTA_M + QUOTA_V],
                     "E": elig[QUOTA_M + QUOTA_V:QUOTA_M + QUOTA_V + QUOTA_E], "eligible": elig}
        assigned |= set(fam.get(op, []))           # every concept of the family stays out of U and D
    rest = [c for c in sorted(data, key=lambda c: h("other:" + c)) if c not in assigned]
    U = [c for c in rest if g0[c]["correct"]][:N_U]
    D = []
    for c in rest:
        if len(D) >= N_D:
            break
        if g0[c]["fit"] or c in U:
            continue
        task, ys = concept_task(data[c])
        r = plug.search(plug.g0(), task["train"], task["test_inputs"], plug.BASE_BUDGET * plug.PROBE_FACTOR,
                        plug.BASE_CPU * plug.PROBE_FACTOR, 2)
        d_checked[c] = bool(r["fit"] and correct(r["preds"], ys))
        if d_checked[c]:
            D.append(c)
    system = sorted(set(U + D + [c for op in chosen for k in ("M", "V") for c in parts[op][k]]))
    excluded = sorted({c for op in chosen for c in parts[op]["E"]})
    tasks = {c: concept_task(data[c])[0] for c in system + excluded}
    recs_path = os.path.join(out, "records.pkl")
    recs = {}
    if os.path.exists(recs_path):
        with open(recs_path, "rb") as f:
            recs = pickle.load(f)
    for c in system:
        if c not in recs:
            recs[c] = C.analyze(plug, tasks[c])
            with open(P.check_write(recs_path), "wb") as f:
                pickle.dump(recs, f)
    part_of = {c: "U" for c in U} | {c: "D" for c in D}
    family_of = {}
    for op in chosen:
        for k in ("M", "V", "E"):
            for c in parts[op][k]:
                part_of[c], family_of[c] = k, op
    mot = [c for op in chosen for c in parts[op]["M"] if recs[c]["decision"] == "INVENT_NEW_OPERATION"]
    fams = [op for op in chosen if any(c in mot for c in parts[op]["M"])]
    donor = {}
    for fi, op in enumerate(fams):
        for slot, c in enumerate([c for c in parts[op]["M"] if c in mot]):
            nxt = fams[(fi + 1) % len(fams)] if len(fams) > 1 else None
            if nxt is None:
                continue
            nm = [d for d in parts[nxt]["M"] if d in mot]
            donor[c] = nm[slot] if slot < len(nm) else nm[0]
    flow = {}
    for c in sorted(data):
        t = tree(full[c]["tree"]) if full[c]["tree"] is not None else None
        used = [op for op in chosen if t is not None and LD.uses(t, {op})]
        if c in part_of:
            reason = {"M": "motivating-partition family task", "V": "validation-partition family task",
                      "E": "excluded (evaluation) family task", "U": "previously solved (U)", "D": "decoy (D)"}[part_of[c]]
        elif not full[c]["fit"]:
            reason = "full DSL: no fitting program at the base budget"
        elif not full[c]["correct"]:
            reason = "full DSL: fits the demonstrations but mispredicts the queries"
        elif len(used) > 1:
            reason = "shortest full-DSL program uses more than one deleted operation"
        elif len(used) == 1 and g0[c]["fit"]:
            reason = "uses a deleted operation but G0 already fits at the base budget"
        elif len(used) == 1 and c in ref_ok and not ref_ok[c]:
            reason = "G0 plus the deleted operation does not fit and predict at the base budget"
        elif len(used) == 1 and c in ref_ok:
            reason = "eligible family task beyond the M/V/E quota"
        elif g0[c]["correct"]:
            reason = "solved by G0 but beyond the U quota of 14"
        elif g0[c]["fit"]:
            reason = "G0 fits but mispredicts the queries"
        elif c in d_checked:
            reason = "G0 misses at the base budget and at 4x"
        else:
            reason = "G0 misses at the base budget; not examined for D (quota filled)"
        flow[c] = {"full_fit": full[c]["fit"], "full_correct": full[c]["correct"], "deleted_ops_used": used,
                   "g0_fit": g0[c]["fit"], "g0_correct": g0[c]["correct"], "reference_ok": ref_ok.get(c),
                   "partition": part_of.get(c), "reason": reason}
    counts = {}
    for v in flow.values():
        counts[v["reason"]] = counts.get(v["reason"], 0) + 1
    dump(os.path.join(out, "concept_flow.json"), {"counts": counts, "concepts": flow,
                                                  "filters": {"full_dsl_fit": sum(v["full_fit"] for v in flow.values()),
                                                              "full_dsl_correct": len(solved),
                                                              "single_deleted_op": sum(len(v["deleted_ops_used"]) == 1
                                                                                       and v["full_correct"]
                                                                                       for v in flow.values()),
                                                              "g0_no_fit_and_reference_ok": sum(bool(x) for x in
                                                                                                ref_ok.values())}})
    plan = {"deleted": chosen, "usage": usage, "gap_log": gap_log, "families": parts, "U": U, "D": D,
            "system": system, "excluded": excluded, "motivating": mot, "donor": donor, "partition_of": part_of,
            "family_of": family_of, "n_concepts": len(data), "full_dsl_solved": len(solved),
            "g0_solved": sum(v["correct"] for v in g0.values())}
    dump(os.path.join(out, "plan.json"), plan)
    dump(os.path.join(out, "tasks_system.json"), {c: tasks[c] for c in system})
    ev = {c: {"train": tasks[c]["train"], "test_inputs": tasks[c]["test_inputs"],
              "test_outputs": concept_task(data[c])[1], "partition": part_of[c], "family": family_of.get(c)}
          for c in system + excluded}
    dump(os.path.join(out, "tasks_eval.json"), ev)
    man = {f: sha_file(os.path.join(out, f)) for f in sorted(os.listdir(out))}
    dump(os.path.join(out, "BUILD_MANIFEST.json"), {"files_sha256": man,
                                                    "built_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    print(json.dumps({"deleted": chosen, "motivating": len(mot), "system": len(system), "excluded": len(excluded),
                      "U": len(U), "D": len(D), "full_solved": len(solved)}), flush=True)


# ------------------------------------------------------------------ arms (system side)
def _gates(plan, plug, tasks, recs, cache):
    solved = [c for c in plan["system"] if recs[c]["status"] == "solved"]
    base_preds = {c: recs[c]["base_preds"][0] for c in solved}
    pool = sorted([c for c in plan["system"] if recs[c]["status"] != "solved"], key=lambda c: h("pool:" + c))
    return C.Gates(plug, tasks, solved, base_preds, pool, cache)


def arms():
    b = os.path.join(U3, "build")
    out = os.path.join(U3, "arms")
    os.makedirs(out, exist_ok=True)
    plan = load(os.path.join(b, "plan.json"))
    tasks = {c: {"train": [tuple(map(tuple, p)) for p in v["train"]], "test_inputs": [tuple(q) for q in v["test_inputs"]]}
             for c, v in load(os.path.join(b, "tasks_system.json")).items()}
    for c in tasks:
        tasks[c]["train"] = [(tuple(a), tuple(y)) for a, y in tasks[c]["train"]]
    with open(os.path.join(b, "records.pkl"), "rb") as f:
        recs = pickle.load(f)
    plug = PL.ListPlugin(tuple(plan["deleted"]))
    cpath = os.path.join(out, "gates.pkl")
    cache = None
    if os.path.exists(cpath):
        with open(cpath, "rb") as f:
            cache = pickle.load(f)
    G = _gates(plan, plug, tasks, recs, cache)
    upath = os.path.join(out, "units.json")
    units = load(upath) if os.path.exists(upath) else {}
    for s in SEEDS:
        order = LS.seeded_order(s)
        for c in plan["motivating"]:
            for arm in ARMS:
                key = f"{arm}|{c}|{s}"
                if key in units:
                    continue
                if arm == "S-enum":
                    res = C.run_enum_unit(G, c, order)
                else:
                    if arm == "S-shuffled":
                        d = plan["donor"].get(c)
                        if d is None:
                            units[key] = {"skipped": "no donor"}
                            continue
                        sk = recs[d]["sketches"]
                    elif arm == "S-demo":
                        sk = [x for x in recs[c]["sketches"] if x["form"] == "?(I)"]
                    elif arm == "S-hole-ext":
                        sk = recs[c]["sketches_ext"]
                    else:
                        sk = recs[c]["sketches"]
                    res = C.run_spec_unit(G, c, C.spec_candidates(plug, order, sk))
                units[key] = dict(res, arm=arm, task=c, seed=s)
                dump(upath, units)
                with open(P.check_write(cpath), "wb") as f:
                    pickle.dump(G.c, f)
                print(json.dumps({"unit": key, "promoted": res["promoted"], "cpu_s": res["cpu_s"]}), flush=True)
    c7path = os.path.join(out, "c7m.json")
    c7 = load(c7path) if os.path.exists(c7path) else {}
    for c in plan["motivating"]:
        if c in c7:
            continue
        r = plug.search(plug.g0(), tasks[c]["train"], tasks[c]["test_inputs"], 10 ** 9, C7M_CPU, 2)
        c7[c] = {"fit": r["fit"], "preds": r["preds"], "program": r["program"], "cpu_s": r["cpu_s"],
                 "level_complete": r["level_complete"], "calls": r["calls"]}
        dump(c7path, c7)
    with open(P.check_write(cpath), "wb") as f:
        pickle.dump(G.c, f)


# ------------------------------------------------------------------ evaluation (evaluator side)
def mcnemar(b, c):
    n = b + c
    return 1.0 if n == 0 else min(1.0, 2 * sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n)


def evaluate():
    b = os.path.join(U3, "build")
    plan = load(os.path.join(b, "plan.json"))
    ev = load(os.path.join(b, "tasks_eval.json"))
    units = load(os.path.join(U3, "arms", "units.json"))
    c7 = load(os.path.join(U3, "arms", "c7m.json"))
    # amendment 1, item 6: candidates, parameters, promotions and predictions are frozen before any E outcome
    pre_e = {"units_json_sha256": sha_file(os.path.join(U3, "arms", "units.json")),
             "c7m_json_sha256": sha_file(os.path.join(U3, "arms", "c7m.json")),
             "recorded_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    with open(os.path.join(b, "records.pkl"), "rb") as f:
        recs = pickle.load(f)
    plug = PL.ListPlugin(tuple(plan["deleted"]))
    tasks = {c: {"train": [(tuple(a), tuple(y)) for a, y in ev[c]["train"]],
                 "test_inputs": [tuple(q) for q in ev[c]["test_inputs"]]} for c in ev}
    cache = None
    cpath = os.path.join(U3, "arms", "gates.pkl")
    if os.path.exists(cpath):
        with open(cpath, "rb") as f:
            cache = pickle.load(f)
    G = _gates(plan, plug, {c: tasks[c] for c in plan["system"]}, recs, cache)
    mot = plan["motivating"]
    rec = {}
    for key, u in units.items():
        arm, c, s = key.split("|")
        if "skipped" in u:
            continue
        rec[(arm, c, int(s))] = any(r.get("fit") and correct(r.get("preds"), ev[c]["test_outputs"]) for r in u["rows"])
    for c in mot:
        for s in SEEDS:
            rec[("C7m", c, s)] = bool(c7[c]["fit"]) and correct(c7[c]["preds"], ev[c]["test_outputs"])
    arms_all = ARMS + ("C7m",)
    vary = {a: [c for c in mot if len({rec.get((a, c, s)) for s in SEEDS}) > 1] for a in arms_all}

    def task_level(a, rule):
        out = {}
        for c in mot:
            v = [rec.get((a, c, s)) for s in SEEDS]
            if any(x is None for x in v):
                continue
            out[c] = sum(v) >= 2 if rule == "majority" else any(v)
        return out

    def comp(a, bb, rule="majority"):
        A, B = task_level(a, rule), task_level(bb, rule)
        ts = [c for c in mot if c in A and c in B]
        bo = sum(A[c] and not B[c] for c in ts)
        co = sum(B[c] and not A[c] for c in ts)
        return {"tasks": len(ts), "first": sum(A[c] for c in ts), "second": sum(B[c] for c in ts),
                "only_first": bo, "only_second": co, "exact_mcnemar_p": round(mcnemar(bo, co), 4)}
    secondary = [("S-hole-ext", "S-shuffled"), ("S-hole", "S-demo"), ("S-hole-ext", "S-demo"), ("S-hole", "C7m"),
                 ("S-hole-ext", "C7m"), ("S-hole", "S-enum"), ("S-enum", "C7m")]
    comps = {f"{a}_vs_{bb}": {"majority": comp(a, bb), "any_seed": comp(a, bb, "any")}
             for a, bb in [("S-hole", "S-shuffled")] + secondary}
    # Holm adjustment within the secondary list (majority rule)
    sec = sorted([(comps[f"{a}_vs_{bb}"]["majority"]["exact_mcnemar_p"], f"{a}_vs_{bb}") for a, bb in secondary])
    m, running = len(sec), 0.0
    for i, (pv, k) in enumerate(sec):
        running = max(running, min(1.0, (m - i) * pv))
        comps[k]["majority"]["holm_p"] = round(running, 4)
    prim = comps["S-hole_vs_S-shuffled"]["majority"]
    if len(mot) < 6:
        prim["decision"] = "underpowered (fewer than 6 motivating tasks)"
    elif prim["exact_mcnemar_p"] < 0.05 and prim["only_first"] > prim["only_second"]:
        prim["decision"] = "replicated: CORA's specification beats a shuffled specification"
    elif prim["exact_mcnemar_p"] < 0.05:
        prim["decision"] = "reversed: the shuffled specification is better"
    else:
        prim["decision"] = "not replicated (p >= 0.05)"
    promoted = sorted({u["promoted"] for u in units.values() if u.get("promoted")})
    by = LS.by_sid()
    sscore = {}
    e_tasks = plan["excluded"]
    for sid in promoted:
        st = by[sid]
        solved_e = []
        for c in e_tasks:
            r = plug.search(plug.with_structure(st), tasks[c]["train"], tasks[c]["test_inputs"], plug.BASE_BUDGET,
                            plug.BASE_CPU, 2)
            if r["fit"] and correct(r["preds"], ev[c]["test_outputs"]):
                solved_e.append(c)
        agree = {}
        for op in plan["deleted"]:
            a, _, f = LD.OPS[op]
            ths = [()] if a == ("L",) else [(k,) for k in range(10)]
            best = 0.0
            for th in ths:
                for sth in (st.thetas() if st.param else [()]):
                    ok = tot = 0
                    for x in plug.probes + [tuple(q) for c in e_tasks for q in ev[c]["test_inputs"]]:
                        try:
                            w = LD.apply_op(f, "L", [x] + list(th))
                        except LD.Undefined:
                            w = None
                        v = st(x, *sth)
                        if w is None and v is None:
                            continue
                        tot += 1
                        ok += w == v
                    if tot:
                        best = max(best, ok / tot)
            agree[op] = round(best, 3)
        wit = []
        for th in st.thetas()[:2]:
            prs = [(x, st(x, *th)) for x in plug.probes]
            prs = [(x, y) for x, y in prs if y is not None]
            if len(prs) < 4:
                continue
            r = plug.search(plug.g0(), prs[:-1], [prs[-1][0]], 1_000_000, 30.0, 1)
            wit.append(bool(r["fit"] and r["preds"] and tuple(r["preds"][0][0]) == tuple(prs[-1][1])))
        sscore[sid] = {"excluded_solved": solved_e,
                       "excluded_same_family": [c for c in solved_e if ev[c]["family"] ==
                                                max(agree, key=agree.get)],
                       "agreement_with_deleted_ops": agree, "best_match": max(agree, key=agree.get),
                       "kind": ("G0 witness within 1M executions on the probe lists (macro)" if wit and all(wit) else
                                ("no G0 witness under the declared budget and probes" if wit else "undetermined"))}
    fam_of = plan["family_of"]
    per_family = {}
    for op in plan["deleted"]:
        ts = [c for c in mot if fam_of.get(c) == op]
        row = {"motivating": len(ts)}
        for a in arms_all:
            tl = task_level(a, "majority")
            row[a] = sum(tl.get(c, False) for c in ts)
        A, B = task_level("S-hole", "majority"), task_level("S-shuffled", "majority")
        row["S-hole_vs_S-shuffled_discordant"] = [sum(A.get(c, False) and not B.get(c, False) for c in ts),
                                                 sum(B.get(c, False) and not A.get(c, False) for c in ts)]
        A2 = task_level("S-hole-ext", "majority")
        row["S-hole-ext_vs_S-shuffled_discordant"] = [sum(A2.get(c, False) and not B.get(c, False) for c in ts),
                                                     sum(B.get(c, False) and not A2.get(c, False) for c in ts)]
        per_family[op] = row
    cpu = {a: round(sum(units[f"{a}|{c}|{s}"]["cpu_s"] for c in mot for s in SEEDS
                        if f"{a}|{c}|{s}" in units and "cpu_s" in units[f"{a}|{c}|{s}"]) /
                    max(1, sum(1 for c in mot for s in SEEDS if f"{a}|{c}|{s}" in units)), 2) for a in ARMS}
    cpu["C7m"] = round(sum(c7[c]["cpu_s"] for c in mot) / max(1, len(mot)), 2)
    with open(P.check_write(cpath), "wb") as f:
        pickle.dump(G.c, f)
    res = {"deleted": plan["deleted"], "motivating": mot, "n_motivating": len(mot), "vary_by_seed": vary,
           "task_level": {a: {r: task_level(a, r) for r in ("majority", "any")} for a in arms_all},
           "comparisons": comps, "primary": prim, "promoted_structures": sscore, "cpu_per_unit": cpu,
           "per_family": per_family, "pre_E_freeze": pre_e,
           "p_value_label": "task-level exact McNemar p-values are conditional and descriptive: the families share "
                            "sketch rules, donors and promoted structures, so tasks are not independent mechanisms",
           "rolled_back": sum(1 for u in units.values() for r in u.get("rows", []) if r.get("promotion") == "rolled_back"),
           "search_shortcuts": sum(1 for u in units.values() for r in u.get("rows", [])
                                   if r.get("outcome") == "search_shortcut"),
           "construction": {k: plan[k] for k in ("n_concepts", "full_dsl_solved", "g0_solved", "usage", "gap_log")}}
    os.makedirs(os.path.join(U3, "eval"), exist_ok=True)
    dump(os.path.join(U3, "eval", "results.json"), res)
    write_report(res, plan)
    print(json.dumps({"primary": prim}), flush=True)


def write_report(res, plan):
    L = ["# Test U3 report (written automatically by the detached chain)", "",
         "Protocol `u3_list_functions/PROTOCOL.md` (frozen; sha256 in `u3_list_functions/PROTOCOL_FREEZE.json`). "
         "Data: BIG-bench list_functions (Apache-2.0), evaluation only. Results: `u3_list_functions/eval/results.json`.",
         "", f"Deleted operations (rule-selected): {', '.join(res['deleted'])}. Motivating tasks: {res['n_motivating']}. "
         f"Arms whose outcome varies by seed: { {a: len(v) for a, v in res['vary_by_seed'].items()} }.", "",
         "## Primary (task level, majority of 3 seeds): S-hole vs S-shuffled", "",
         f"- {res['primary']}", "", "## All comparisons (task level; exact two-sided McNemar)", "",
         "| comparison | rule | tasks | first | second | first only | second only | p | Holm p (secondary) |",
         "|---|---|---|---|---|---|---|---|---|"]
    for k, v in res["comparisons"].items():
        for rule in ("majority", "any_seed"):
            c = v[rule]
            L.append(f"| {k} | {rule} | {c['tasks']} | {c['first']} | {c['second']} | {c['only_first']} | "
                     f"{c['only_second']} | {c['exact_mcnemar_p']} | {c.get('holm_p', '')} |")
    L += ["", "## Recovered tasks per arm (majority / any seed)", ""]
    for a, v in res["task_level"].items():
        L.append(f"- {a}: {sum(v['majority'].values())}/{len(v['majority'])} majority, "
                 f"{sum(v['any'].values())}/{len(v['any'])} any seed")
    L += ["", f"Mean charged CPU-s per unit: {res['cpu_per_unit']}. Rolled back: {res['rolled_back']}. "
          f"Search shortcuts rejected: {res['search_shortcuts']}.", "", "## Promoted structures (evaluator)", "",
          "| structure | best-matching deleted operation | agreement | excluded tasks solved (all / same family) | kind |",
          "|---|---|---|---|---|"]
    for sid, v in sorted(res["promoted_structures"].items()):
        L.append(f"| {sid} | {v['best_match']} | {v['agreement_with_deleted_ops'][v['best_match']]} | "
                 f"{len(v['excluded_solved'])} / {len(v['excluded_same_family'])} | {v['kind']} |")
    L += ["", "## Per deleted-operation family (task level, majority of 3 seeds)", "",
          "| family | motivating | " + " | ".join(ARMS + ("C7m",)) + " | S-hole vs S-shuffled (only : only) | "
          "S-hole-ext vs S-shuffled |", "|---|---|" + "---|" * (len(ARMS) + 3)]
    for op, r in res["per_family"].items():
        L.append(f"| {op} | {r['motivating']} | " + " | ".join(str(r[a]) for a in ARMS + ("C7m",)) +
                 f" | {r['S-hole_vs_S-shuffled_discordant'][0]} : {r['S-hole_vs_S-shuffled_discordant'][1]} | "
                 f"{r['S-hole-ext_vs_S-shuffled_discordant'][0]} : {r['S-hole-ext_vs_S-shuffled_discordant'][1]} |")
    flow = load(os.path.join(U3, "build", "concept_flow.json"))
    L += ["", "## Flow of all 250 concepts", "", f"Filters: {flow['filters']}.", "",
          "| reason | concepts |", "|---|---|"] + [f"| {k} | {v} |" for k, v in sorted(flow["counts"].items(),
                                                                                    key=lambda kv: -kv[1])]
    L += ["", f"Construction: {res['construction']['n_concepts']} concepts; full DSL solves "
          f"{res['construction']['full_dsl_solved']}; G0 solves {res['construction']['g0_solved']}.",
          f"Pre-E freeze: {res['pre_E_freeze']}.", "", "## Scope of the inference (amendment 1)", "",
          "- The motivating tasks were selected through the full DSL's query-correct shortest programs and G0 plus the "
          "deleted operation's query correctness: a conditional operation-removal population chosen by an oracle, not "
          "an independent or unbiased BIG-bench benchmark. No general benchmark accuracy is claimed.",
          f"- {res['p_value_label']}. Seeds are within-task replicates.",
          "- A bounded failed G0 search is not proof of new expressivity; constructed structures are members of a "
          "known, pre-registered space (selection within a known space).",
          "- C7m (150 CPU-s) and S-enum (60 charged CPU-s) are comparisons at different actual costs, not matched "
          "consumed work; see the CPU line above.",
          "- Underpowered status of the primary test cannot be overridden by the secondary extension.", "",
          "## Claim for the paper", "", "(Written by hand after verification; see the verification section.)", ""]
    with P.open_write(os.path.join(P.REPORTS, "TEST_U3_REPORT.md")) as f:
        f.write("\n".join(L) + "\n")


if __name__ == "__main__":
    {"build": build, "arms": arms, "evaluate": evaluate}[sys.argv[1]]()
