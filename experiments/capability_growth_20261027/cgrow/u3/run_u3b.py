"""Test U3b (u3b_list_functions/PROTOCOL.md): efficiency of failure-specified construction at MATCHED compute.

    python -m cgrow.u3.run_u3b build | arms | evaluate
Same data, DSL, schema language, enumerator, plug-in and shared core as U3 (cgrow/u3/run_u3.py helpers reused).
Each entry point first runs the provenance gate (cgrow/u3/u3b_gate.py) for its stage; the arms and the evaluation
read build and arms outputs only from bytes verified against their manifest or freeze.
"""
import hashlib
import itertools
import json
import os
import pickle
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, HERE)
from cgrow import paths as P, selfext_core as C                                   # noqa: E402
from cgrow.u3 import listdsl as LD, lschema as LS, plugin as PL, run_u3 as R3     # noqa: E402
from cgrow.u3 import u3b_gate as GATE                                             # noqa: E402

U3B = os.path.join(P.HERE, "u3b_list_functions")
SALT = "u3b-20261102"
EXCLUDE_OPS = ("take", "drop", "remove", "reverse")          # U3's deleted set: not candidates here
SEEDS = (0, 1, 2)
ARMS = ("S-hole-ext", "S-enum-MATCHED", "S-hole", "S-demo", "S-shuffled", "S-shuffled-ext", "S-enum")
ENUM_CPU = 60.0
GRID = (0.25, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 60.0)


def h(s):
    return hashlib.sha256((SALT + "|" + s).encode()).hexdigest()


def tree(t):
    return tuple(tree(x) if isinstance(x, list) else x for x in t) if isinstance(t, list) else t


# ------------------------------------------------------------------ build (evaluator role)
def build():
    out = os.path.join(U3B, "build")
    os.makedirs(out, exist_ok=True)
    data = R3.load(R3.DATA)
    full_path = os.path.join(out, "full_dsl_search.json")
    full = R3.load(full_path) if os.path.exists(full_path) else {}
    gfull = LD.Grammar(())
    for c in sorted(data):
        if c not in full:
            task, ys = R3.concept_task(data[c])
            r = LD.search(gfull, task["train"], task["test_inputs"])
            full[c] = {"fit": r["fit"], "correct": r["fit"] and R3.correct(r["preds"], ys), "program": r["program"],
                       "tree": r["program_tree"], "level": r["level_complete"], "cpu_s": r["cpu_s"]}
            R3.dump(full_path, full)
    solved = [c for c in sorted(data) if full[c]["correct"]]
    cands_ops = [o for o in LD.DELETABLE if o not in EXCLUDE_OPS]
    usage = {op: sum(LD.uses(tree(full[c]["tree"]), {op}) for c in solved) for op in cands_ops}
    chosen, gap_log = [], []
    for op in sorted(cands_ops, key=lambda o: (-usage[o], o)):
        if len(chosen) >= 4 or usage[op] == 0:
            break
        pg = PL.ListPlugin(tuple(chosen) + (op,))
        a, _, f = LD.OPS[op]
        defined = wit = 0
        for th in ([()] if a == ("L",) else [(k,) for k in range(10)]):
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
    u3plan = R3.load(os.path.join(R3.U3, "build", "plan.json"))
    u3fam = {c for op in u3plan["families"] for k in ("M", "V", "E") for c in u3plan["families"][op][k]}
    fam = {}
    for c in solved:
        used = [op for op in chosen if LD.uses(tree(full[c]["tree"]), {op})]
        if len(used) == 1:
            fam.setdefault(used[0], []).append(c)
    g0_path = os.path.join(out, "g0_search.json")
    g0 = R3.load(g0_path) if os.path.exists(g0_path) else {}
    for c in sorted(data):
        if c not in g0:
            task, ys = R3.concept_task(data[c])
            r = plug.search(plug.g0(), task["train"], task["test_inputs"], plug.BASE_BUDGET, plug.BASE_CPU, 2)
            g0[c] = {"fit": r["fit"], "correct": r["fit"] and R3.correct(r["preds"], ys), "program": r["program"],
                     "cpu_s": r["cpu_s"]}
            R3.dump(g0_path, g0)
    parts, assigned, ref_ok, d_checked = {}, set(), {}, {}
    for op in chosen:
        elig = []
        for c in sorted(fam.get(op, []), key=lambda c: h("fam:" + c)):
            if c in u3fam or g0[c]["fit"]:
                continue
            task, ys = R3.concept_task(data[c])
            r = plug.search(plug.with_reference(op), task["train"], task["test_inputs"], plug.BASE_BUDGET,
                            plug.BASE_CPU, 2)
            ref_ok[c] = bool(r["fit"] and R3.correct(r["preds"], ys))
            if ref_ok[c]:
                elig.append(c)
        parts[op] = {"M": elig[:R3.QUOTA_M], "V": elig[R3.QUOTA_M:R3.QUOTA_M + R3.QUOTA_V],
                     "E": elig[R3.QUOTA_M + R3.QUOTA_V:R3.QUOTA_M + R3.QUOTA_V + R3.QUOTA_E], "eligible": elig}
        assigned |= set(fam.get(op, []))
    rest = [c for c in sorted(data, key=lambda c: h("other:" + c)) if c not in assigned]
    U = [c for c in rest if g0[c]["correct"]][:R3.N_U]
    D = []
    for c in rest:
        if len(D) >= R3.N_D:
            break
        if g0[c]["fit"] or c in U:
            continue
        task, ys = R3.concept_task(data[c])
        r = plug.search(plug.g0(), task["train"], task["test_inputs"], plug.BASE_BUDGET * plug.PROBE_FACTOR,
                        plug.BASE_CPU * plug.PROBE_FACTOR, 2)
        d_checked[c] = bool(r["fit"] and R3.correct(r["preds"], ys))
        if d_checked[c]:
            D.append(c)
    system = sorted(set(U + D + [c for op in chosen for k in ("M", "V") for c in parts[op][k]]))
    excluded = sorted({c for op in chosen for c in parts[op]["E"]})
    tasks = {c: R3.concept_task(data[c])[0] for c in system + excluded}
    recs_path = os.path.join(out, "records.pkl")
    recs = {}
    if os.path.exists(recs_path):
        with open(recs_path, "rb") as f:
            recs = pickle.load(f)
    for c in system:
        if c not in recs:
            recs[c] = C.analyze(plug, tasks[c])
            if recs[c].get("sketches") is not None:           # specification cost, charged to the arms using it
                for key, ext in (("plain", False), ("ext", True)):
                    t0 = time.process_time()
                    C.sketches(plug, plug.g0(), tasks[c]["train"], extended=ext)
                    recs[c].setdefault("sketch_cpu", {})[key] = round(time.process_time() - t0, 4)
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
            if len(fams) > 1:
                nm = [d for d in parts[fams[(fi + 1) % len(fams)]]["M"] if d in mot]
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
        elif len(used) == 1 and c in u3fam:
            reason = "U3 family task (excluded from U3b families)"
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
    R3.dump(os.path.join(out, "concept_flow.json"), {"counts": counts, "concepts": flow})
    plan = {"deleted": chosen, "usage": usage, "gap_log": gap_log, "families": parts, "U": U, "D": D,
            "system": system, "excluded": excluded, "motivating": mot, "donor": donor, "partition_of": part_of,
            "family_of": family_of, "n_concepts": len(data), "full_dsl_solved": len(solved),
            "g0_solved": sum(v["correct"] for v in g0.values()), "excluded_u3_family_tasks": sorted(u3fam)}
    R3.dump(os.path.join(out, "plan.json"), plan)
    R3.dump(os.path.join(out, "tasks_system.json"), {c: tasks[c] for c in system})
    R3.dump(os.path.join(out, "tasks_eval.json"), {c: {"train": tasks[c]["train"], "test_inputs": tasks[c]["test_inputs"],
                                                       "test_outputs": R3.concept_task(data[c])[1],
                                                       "partition": part_of[c], "family": family_of.get(c)}
                                                   for c in system + excluded})
    write_build_manifest(out)
    print(json.dumps({"deleted": chosen, "motivating": len(mot), "system": len(system), "excluded": len(excluded)}),
          flush=True)


def write_build_manifest(out):
    """The sha256 of exactly the required construction outputs (GATE.BUILD_OUTPUTS), never of the manifest itself."""
    R3.dump(os.path.join(out, "BUILD_MANIFEST.json"),
            {"files_sha256": {f: R3.sha_file(os.path.join(out, f)) for f in GATE.BUILD_OUTPUTS}})


# ------------------------------------------------------------------ arms (system side)
def _verified_build():
    """Verify build/BUILD_MANIFEST.json (exactly the required outputs, each matching; on resume too) and load the
    plan, system tasks and records from the verified bytes only. Returns plan, tasks, recs, digests, manifest sha256."""
    probs, msha, files = GATE.build_check(U3B)
    if probs:
        raise SystemExit("build outputs failed verification: " + "; ".join(probs))
    b = os.path.join(U3B, "build")

    def rd(name):
        return GATE.read_verified(os.path.join(b, name), files[name])
    plan = json.loads(rd("plan.json"))
    tasks = {c: {"train": [(tuple(a), tuple(y)) for a, y in v["train"]], "test_inputs": [tuple(q) for q in v["test_inputs"]]}
             for c, v in json.loads(rd("tasks_system.json")).items()}
    recs = pickle.loads(rd("records.pkl"))
    return plan, tasks, recs, files, msha


def _gates(plan, plug, tasks, recs, cache):
    solved = [c for c in plan["system"] if recs[c]["status"] == "solved"]
    pool = sorted([c for c in plan["system"] if recs[c]["status"] != "solved"], key=lambda c: h("pool:" + c))
    return C.Gates(plug, tasks, solved, {c: recs[c]["base_preds"][0] for c in solved}, pool, cache)


def run_spec_unit_timed(G, tid, cands, spec_cpu):
    """The shared core's specification unit (same candidate order, gates, retry cap and stopping) with the cumulative
    charged CPU recorded at each retry's completion; the specification cost is charged first."""
    rows, retries, cpu, promoted = [], 0, spec_cpu, None
    for c in cands:
        nov = G.novelty(c["sid"])
        cpu += nov["cpu_s"]
        row = dict(c, duplicate=nov["duplicate"])
        if nov["duplicate"]:
            row["outcome"] = "search_shortcut"
            rows.append(row)
            continue
        if retries >= C.M_RETRIES:
            break
        retries += 1
        r = G.retry(c["sid"], tid)
        cpu += r["cpu_s"]
        row.update(fit=r["fit"], preds=r["preds"], program=r["program"], cpu_at_completion=round(cpu, 4))
        if r["fit"]:
            pr = G.promote(c["sid"], tid)
            cpu += pr["cpu_s"]
            row.update(promotion=pr["decision"], validation=pr["validation"], outcome="fits_motivating_task",
                       regression={k: pr["regression"][k] for k in ("lost_fit", "changed_prediction", "checked")},
                       cpu_after_promotion=round(cpu, 4))
            rows.append(row)
            if pr["decision"] == "promoted":
                promoted = c["sid"]
                break
        else:
            row["outcome"] = "no_fit_on_motivating_task"
            rows.append(row)
    return {"rows": rows, "retries": retries, "spec_cpu_s": round(spec_cpu, 4), "charged_cpu_s": round(cpu, 4),
            "promoted": promoted, "n_candidates": len(cands)}


def run_enum_unit_strict(G, tid, order, cap):
    """Blind enumeration with a STRICT cap: a stage (novelty, retry, promotion checks) is counted only if it completes
    within the cap; the first stage that would cross it ends the unit and is recorded as overshoot, never counted."""
    rows, cpu, promoted, retries, overshoot = [], 0.0, None, 0, None
    for st in order:
        nov = G.novelty(st.sid)
        if cpu + nov["cpu_s"] > cap:
            overshoot = {"sid": st.sid, "stage": "novelty", "would_reach": round(cpu + nov["cpu_s"], 4)}
            break
        cpu += nov["cpu_s"]
        if nov["duplicate"]:
            continue
        r = G.retry(st.sid, tid)
        if cpu + r["cpu_s"] > cap:
            overshoot = {"sid": st.sid, "stage": "retry", "would_reach": round(cpu + r["cpu_s"], 4)}
            break
        cpu += r["cpu_s"]
        retries += 1
        row = {"sid": st.sid, "fit": r["fit"], "preds": r["preds"] if r["fit"] else None,
               "program": r["program"], "cpu_at_completion": round(cpu, 4)}
        if r["fit"]:
            pr = G.promote(st.sid, tid)
            if cpu + pr["cpu_s"] > cap:
                row["promotion"] = "not_completed_within_cap"
                overshoot = {"sid": st.sid, "stage": "promotion", "would_reach": round(cpu + pr["cpu_s"], 4)}
                rows.append(row)
                break
            cpu += pr["cpu_s"]
            row.update(promotion=pr["decision"], cpu_after_promotion=round(cpu, 4),
                       regression={k: pr["regression"][k] for k in ("lost_fit", "changed_prediction", "checked")})
            rows.append(row)
            if pr["decision"] == "promoted":
                promoted = st.sid
                break
        else:
            rows.append(row)
    return {"rows": rows, "retries": retries, "charged_cpu_s": round(cpu, 4), "cap": cap, "overshoot": overshoot,
            "promoted": promoted, "spec_cpu_s": 0.0}


def arms():
    out = os.path.join(U3B, "arms")
    plan, tasks, recs, _, msha = _verified_build()            # before any build output is read
    if os.path.exists(os.path.join(out, "ARMS_FREEZE.json")):
        raise SystemExit("the arms were frozen earlier: they are verified, never rerun")
    os.makedirs(out, exist_ok=True)
    plug = PL.ListPlugin(tuple(plan["deleted"]))
    cpath = os.path.join(out, "gates.pkl")
    cache = None
    if os.path.exists(cpath):
        with open(cpath, "rb") as f:
            cache = pickle.load(f)
    G = _gates(plan, plug, tasks, recs, cache)
    upath = os.path.join(out, "units.json")
    units = R3.load(upath) if os.path.exists(upath) else {}
    for s in SEEDS:
        order = LS.seeded_order(s)
        for c in plan["motivating"]:
            for arm in ARMS:
                key = f"{arm}|{c}|{s}"
                if key in units:
                    continue
                if arm == "S-enum":
                    res = run_enum_unit_strict(G, c, order, ENUM_CPU)
                elif arm == "S-enum-MATCHED":
                    res = run_enum_unit_strict(G, c, order, units[f"S-hole-ext|{c}|{s}"]["charged_cpu_s"])
                else:
                    donor = plan["donor"].get(c)
                    if arm in ("S-shuffled", "S-shuffled-ext") and donor is None:
                        units[key] = {"skipped": "no donor"}
                        continue
                    src, kind = {"S-hole-ext": (c, "ext"), "S-hole": (c, "plain"), "S-demo": (c, "demo"),
                                 "S-shuffled": (donor, "plain"), "S-shuffled-ext": (donor, "ext")}[arm]
                    if kind == "demo":
                        sk, spec = [x for x in recs[c]["sketches"] if x["form"] == "?(I)"], 0.0
                    else:
                        sk = recs[src]["sketches_ext" if kind == "ext" else "sketches"]
                        spec = recs[src]["sketch_cpu"][kind]
                    t0 = time.process_time()
                    cands = C.spec_candidates(plug, order, sk)
                    spec += time.process_time() - t0
                    res = run_spec_unit_timed(G, c, cands, spec)
                    res["specification_from"] = src
                units[key] = dict(res, arm=arm, task=c, seed=s)
                R3.dump(upath, units)
                with open(P.check_write(cpath), "wb") as f:
                    pickle.dump(G.c, f)
                print(json.dumps({"unit": key, "promoted": res["promoted"], "charged": res["charged_cpu_s"]}), flush=True)
    c7path = os.path.join(out, "c7m.json")
    c7 = R3.load(c7path) if os.path.exists(c7path) else {}
    for c in plan["motivating"]:
        if c not in c7:
            r = plug.search(plug.g0(), tasks[c]["train"], tasks[c]["test_inputs"], 10 ** 9, R3.C7M_CPU, 2)
            c7[c] = {"fit": r["fit"], "preds": r["preds"], "program": r["program"], "cpu_s": r["cpu_s"]}
            R3.dump(c7path, c7)
    with open(P.check_write(cpath), "wb") as f:
        pickle.dump(G.c, f)
    R3.dump(upath, units)                                     # written even if there is no motivating task
    R3.dump(c7path, c7)
    R3.dump(os.path.join(out, "ARMS_FREEZE.json"), {"units_json_sha256": R3.sha_file(upath),
                                                    "c7m_json_sha256": R3.sha_file(c7path),
                                                    "build_manifest_sha256": msha,
                                                    "frozen_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})


# ------------------------------------------------------------------ evaluation (evaluator side)
def sign_flip_p(d):
    """Exact two-sided sign-flip permutation test of the mean paired difference (zeros dropped)."""
    d = [x for x in d if abs(x) > 1e-12]
    if not d:
        return 1.0
    obs = abs(sum(d))
    hits = sum(abs(sum(sg * x for sg, x in zip(signs, d))) >= obs - 1e-12
               for signs in itertools.product((1, -1), repeat=len(d)))
    return hits / 2 ** len(d)


def recovery_time(unit, outputs):
    """Charged CPU at the completion of the first retry that fits and predicts every query (None if none)."""
    ts = [r["cpu_at_completion"] for r in unit.get("rows", []) if r.get("fit") and "cpu_at_completion" in r
          and R3.correct(r.get("preds"), outputs)]
    return min(ts) if ts else None


def evaluate():
    b, ad = os.path.join(U3B, "build"), os.path.join(U3B, "arms")
    plan, tasks, recs, files, msha = _verified_build()        # before any build or arms output is read
    probs, asha, af = GATE.arms_check(U3B, msha)              # the arms freeze must name this build manifest
    if probs:
        raise SystemExit("arms outputs failed verification: " + "; ".join(probs))
    if os.path.exists(os.path.join(U3B, "eval", "EVAL_FREEZE.json")):
        raise SystemExit("the evaluation was frozen earlier: it is verified, never rerun")
    units = json.loads(GATE.read_verified(os.path.join(ad, "units.json"), af["units_json_sha256"]))
    c7 = json.loads(GATE.read_verified(os.path.join(ad, "c7m.json"), af["c7m_json_sha256"]))
    flow = json.loads(GATE.read_verified(os.path.join(b, "concept_flow.json"), files["concept_flow.json"]))
    # first evaluator access to task outputs, after every check above and from the verified bytes only
    ev = json.loads(GATE.read_verified(os.path.join(b, "tasks_eval.json"), files["tasks_eval.json"]))
    mot = plan["motivating"]
    outs = {c: [tuple(y) for y in ev[c]["test_outputs"]] for c in ev}
    t_rec, trial, admitted, promoted = {}, {}, {}, {}
    for key, u in units.items():
        arm, c, s = key.split("|")
        if "skipped" in u:
            continue
        k = (arm, c, int(s))
        t_rec[k] = recovery_time(u, outs[c])
        trial[k] = t_rec[k] is not None
        admitted[k] = any(r.get("fit") and r.get("promotion") in ("promoted", "quarantined") for r in u["rows"])
        promoted[k] = u.get("promoted") is not None
    for c in mot:
        for s in SEEDS:
            trial[("C7m", c, s)] = bool(c7[c]["fit"]) and R3.correct(c7[c]["preds"], outs[c])
    arms_all = ARMS + ("C7m",)

    def tl(a, table, rule="majority"):
        res = {}
        for c in mot:
            v = [table.get((a, c, s)) for s in SEEDS]
            if None not in v:
                res[c] = sum(v) >= 2 if rule == "majority" else any(v)
        return res

    def comp(a, bb, table=trial, rule="majority"):
        A, B = tl(a, table, rule), tl(bb, table, rule)
        ts = [c for c in mot if c in A and c in B]
        bo, co = sum(A[c] and not B[c] for c in ts), sum(B[c] and not A[c] for c in ts)
        return {"tasks": len(ts), "first": sum(A[c] for c in ts), "second": sum(B[c] for c in ts),
                "only_first": bo, "only_second": co, "exact_mcnemar_p": round(R3.mcnemar(bo, co), 4)}
    prim = comp("S-hole-ext", "S-enum-MATCHED")
    if len(mot) < 6:
        prim["decision"] = "underpowered (fewer than 6 motivating tasks)"
    elif prim["exact_mcnemar_p"] < 0.05 and prim["only_first"] > prim["only_second"]:
        prim["decision"] = "confirmed: guided construction recovers more tasks than blind enumeration at matched CPU"
    elif prim["exact_mcnemar_p"] < 0.05:
        prim["decision"] = "reversed: blind enumeration recovers more tasks at matched CPU"
    else:
        prim["decision"] = "not confirmed (p >= 0.05)"

    def within(arm, c, bgt):
        v = [t_rec.get((arm, c, s)) for s in SEEDS]
        return sum(x is not None and x <= bgt for x in v) >= 2
    curve = {"grid_cpu_s": list(GRID), "S-hole-ext": [sum(within("S-hole-ext", c, g) for c in mot) for g in GRID],
             "S-enum": [sum(within("S-enum", c, g) for c in mot) for g in GRID]}
    auc = {c: (sum(within("S-hole-ext", c, g) for g in GRID) / len(GRID),
               sum(within("S-enum", c, g) for g in GRID) / len(GRID)) for c in mot}
    d = [auc[c][0] - auc[c][1] for c in mot]
    auc_test = {"mean_auc_ext": round(sum(x for x, _ in auc.values()) / max(1, len(mot)), 4),
                "mean_auc_enum": round(sum(y for _, y in auc.values()) / max(1, len(mot)), 4),
                "mean_paired_difference": round(sum(d) / max(1, len(d)), 4), "exact_sign_flip_p": round(sign_flip_p(d), 4)}
    sec = {"S-hole-ext_vs_S-demo": comp("S-hole-ext", "S-demo")["exact_mcnemar_p"],
           "S-hole-ext_vs_S-shuffled-ext": comp("S-hole-ext", "S-shuffled-ext")["exact_mcnemar_p"],
           "AUC_S-hole-ext_vs_S-enum": auc_test["exact_sign_flip_p"]}
    holm, running = {}, 0.0
    for i, (k, pv) in enumerate(sorted(sec.items(), key=lambda kv: kv[1])):
        running = max(running, min(1.0, (len(sec) - i) * pv))
        holm[k] = round(running, 4)
    pairs = ["S-hole-ext_vs_S-enum-MATCHED", "S-hole-ext_vs_S-demo", "S-hole-ext_vs_S-shuffled-ext",
             "S-hole-ext_vs_S-shuffled", "S-hole-ext_vs_S-hole", "S-hole-ext_vs_S-enum", "S-hole-ext_vs_C7m",
             "S-enum_vs_C7m", "S-demo_vs_S-shuffled-ext"]
    comps = {k: {"majority": comp(*k.split("_vs_")), "any_seed": comp(*k.split("_vs_"), rule="any")} for k in pairs}
    stages = {a: {"trial_recovery": sum(tl(a, trial).values()),
                  "admitted": sum(tl(a, admitted).values()) if a != "C7m" else None,
                  "promoted": sum(tl(a, promoted).values()) if a != "C7m" else None} for a in arms_all}
    per_family = {}
    for op in plan["deleted"]:
        ts = [c for c in mot if plan["family_of"].get(c) == op]
        row = {"motivating": len(ts)}
        for a in arms_all:
            row[a] = sum(tl(a, trial).get(c, False) for c in ts)
        A, B = tl("S-hole-ext", trial), tl("S-enum-MATCHED", trial)
        row["ext_vs_matched_discordant"] = [sum(A.get(c, False) and not B.get(c, False) for c in ts),
                                            sum(B.get(c, False) and not A.get(c, False) for c in ts)]
        per_family[op] = row
    cpu = {a: round(sum(units[f"{a}|{c}|{s}"]["charged_cpu_s"] for c in mot for s in SEEDS
                        if "charged_cpu_s" in units.get(f"{a}|{c}|{s}", {})) / max(1, len(mot) * len(SEEDS)), 4)
           for a in ARMS}
    cpu["C7m"] = round(sum(c7[c]["cpu_s"] for c in mot) / max(1, len(mot)), 2)
    over = [u["overshoot"] for k, u in units.items() if k.startswith("S-enum-MATCHED|") and u.get("overshoot")]
    # the blind arms' charged CPU including each overshooting stage's work (work done, never counted)
    spent = {a: round(sum((units[f"{a}|{c}|{s}"].get("overshoot") or {}).get(
        "would_reach", units[f"{a}|{c}|{s}"]["charged_cpu_s"]) for c in mot for s in SEEDS) / max(1, len(mot) * len(SEEDS)), 4)
        for a in ("S-enum-MATCHED", "S-enum")}
    # excluded-task reuse of promoted structures (new evaluator work after the arms freeze; CPU recorded)
    t0 = time.process_time()
    plug = PL.ListPlugin(tuple(plan["deleted"]))
    by = LS.by_sid()
    reuse = {}
    for sid in sorted({u["promoted"] for u in units.values() if u.get("promoted")}):
        st, solved = by[sid], []
        for c in plan["excluded"]:
            tk = {"train": [(tuple(a), tuple(y)) for a, y in ev[c]["train"]], "test_inputs": [tuple(q) for q in ev[c]["test_inputs"]]}
            r = plug.search(plug.with_structure(st), tk["train"], tk["test_inputs"], plug.BASE_BUDGET, plug.BASE_CPU, 2)
            if r["fit"] and R3.correct(r["preds"], outs[c]):
                solved.append(c)
        agree = {}
        for op in plan["deleted"]:
            a_, _, f_ = LD.OPS[op]
            best = 0.0
            for th in ([()] if a_ == ("L",) else [(k,) for k in range(10)]):
                for sth in st.thetas():
                    okn = tot = 0
                    for x in plug.probes + [tuple(q) for e in plan["excluded"] for q in ev[e]["test_inputs"]]:
                        try:
                            w = LD.apply_op(f_, "L", [x] + list(th))
                        except LD.Undefined:
                            w = None
                        v = st(x, *sth)
                        if w is None and v is None:
                            continue
                        tot += 1
                        okn += w == v
                    if tot:
                        best = max(best, okn / tot)
            agree[op] = round(best, 3)
        match = max(agree, key=agree.get)
        reuse[sid] = {"agreement_with_deleted_ops": agree, "best_match": match, "excluded_solved": solved,
                      "excluded_same_family": [c for c in solved if ev[c]["family"] == match],
                      "excluded_tasks_of_family": [c for c in plan["excluded"] if ev[c]["family"] == match]}
    res = {"deleted": plan["deleted"], "motivating": mot, "n_motivating": len(mot), "primary": prim,
           "secondary_raw_p": sec, "secondary_holm_p": holm, "anytime_curve": curve, "auc_test": auc_test,
           "auc_per_task": auc, "comparisons": comps, "stages": stages, "per_family": per_family,
           "cpu_charged_per_unit": cpu, "matched_overshoots_not_counted": len(over),
           "blind_cpu_incl_overshoot_per_unit": spent, "pre_E_freeze": af,
           "reuse": reuse, "evaluator_reuse_cpu_s": round(time.process_time() - t0, 2),
           "vary_by_seed": {a: [c for c in mot if len({trial.get((a, c, s)) for s in SEEDS}) > 1] for a in arms_all},
           "construction": {k: plan[k] for k in ("n_concepts", "full_dsl_solved", "g0_solved", "usage", "gap_log")}}
    res["exploratory_pooled_with_U3"] = pooled_u3()
    os.makedirs(os.path.join(U3B, "eval"), exist_ok=True)
    rpath = os.path.join(U3B, "eval", "results.json")
    R3.dump(rpath, res)
    write_report(res, flow)
    R3.dump(os.path.join(U3B, "eval", "EVAL_FREEZE.json"),
            {"results_json_sha256": R3.sha_file(rpath), "arms_freeze_sha256": asha, "build_manifest_sha256": msha,
             "report_sha256_as_written": R3.sha_file(os.path.join(P.REPORTS, "TEST_U3B_REPORT.md")),
             "frozen_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    print(json.dumps({"primary": prim, "auc": auc_test}), flush=True)


def pooled_u3():
    """EXPLORATORY, post hoc: U3's tasks under U3b's contrasts, replayed from U3's frozen gate cache only (an entry
    missing from the cache makes that unit 'unavailable'; nothing is recomputed). U3 charged no specification CPU;
    the replay charges U3's recorded gate CPU only."""
    b = os.path.join(R3.U3, "build")
    plan = R3.load(os.path.join(b, "plan.json"))
    ev = R3.load(os.path.join(b, "tasks_eval.json"))
    units = R3.load(os.path.join(R3.U3, "arms", "units.json"))
    with open(os.path.join(R3.U3, "arms", "gates.pkl"), "rb") as f:
        cache = pickle.load(f)
    nov, ret, reg = cache["nov"], cache["retry"], cache["reg"]
    by = LS.by_sid()

    def ext_time(u, o):
        cum = 0.0
        for r in u["rows"]:
            if r["sid"] not in nov:
                return "unavailable"
            cum += nov[r["sid"]]["cpu_s"]
            if r.get("outcome") == "search_shortcut":
                continue
            if (r["sid"], u["task"]) not in ret:
                return "unavailable"
            cum += ret[(r["sid"], u["task"])]["cpu_s"]
            if r.get("fit") and R3.correct(r.get("preds"), o):
                return cum
        return None

    def enum_time(tid, seed, cap, o):
        cum = 0.0
        for st in LS.seeded_order(seed):
            if st.sid not in nov:
                return "unavailable"
            if cum + nov[st.sid]["cpu_s"] > cap:
                return None
            cum += nov[st.sid]["cpu_s"]
            if nov[st.sid]["duplicate"]:
                continue
            k = (st.sid, tid)
            if k not in ret:
                return "unavailable"
            if cum + ret[k]["cpu_s"] > cap:
                return None
            cum += ret[k]["cpu_s"]
            if ret[k]["fit"]:
                if R3.correct(ret[k]["preds"], o):
                    return cum
                return "unavailable"          # promotion replay not attempted (post hoc)
        return None
    out = {}
    for c in plan["motivating"]:
        o = [tuple(y) for y in ev[c]["test_outputs"]]
        per = []
        for s in SEEDS:
            u = dict(units[f"S-hole-ext|{c}|{s}"], task=c)
            te = ext_time(u, o)
            cap = u.get("cpu_s", 0.0)
            tm = enum_time(c, s, cap, o)
            per.append((te, tm))
        out[c] = {"S-hole-ext": [x for x, _ in per], "S-enum-MATCHED": [y for _, y in per]}
    ok = lambda v: sum(isinstance(x, float) for x in v) >= 2      # noqa: E731
    return {"label": "EXPLORATORY, post hoc: U3 replayed from its frozen cache (no recomputation)", "U3_units": out,
            "U3_ext": sum(ok(v["S-hole-ext"]) for v in out.values()),
            "U3_matched": sum(ok(v["S-enum-MATCHED"]) for v in out.values()),
            "unavailable": sum(x == "unavailable" for v in out.values() for x in v["S-hole-ext"] + v["S-enum-MATCHED"])}


def write_report(res, flow):
    p = res["primary"]
    L = ["# Test U3b report (written automatically by the detached chain)", "",
         "Protocol `u3b_list_functions/PROTOCOL.md` (frozen; `u3b_list_functions/PROTOCOL_FREEZE.json`). Results: "
         "`u3b_list_functions/eval/results.json`. Population: a conditional follow-up on the same 250 concepts as U3, "
         "with query outputs used to select operations and tasks; p-values are conditional and descriptive; "
         "selection within a known schema space.", "",
         f"Deleted (rule-selected, excluding U3's take, drop, remove, reverse): {', '.join(res['deleted'])}. "
         f"Motivating tasks: {res['n_motivating']}.", "",
         "## Primary: S-hole-ext vs S-enum-MATCHED (trial recovery, majority of 3 seeds, exact McNemar)", "",
         f"- {p['first']} vs {p['second']} of {p['tasks']} tasks; discordant {p['only_first']} : {p['only_second']}; "
         f"p = {p['exact_mcnemar_p']}. **Decision: {p['decision']}.**",
         f"- S-enum-MATCHED units that stopped on the strict cap (overshoot recorded, never counted): "
         f"{res['matched_overshoots_not_counted']}.",
         f"- Mean charged CPU-s per blind unit including the overshooting stage's work (done, never counted): "
         f"{res['blind_cpu_incl_overshoot_per_unit']}.", "",
         "## Secondary (Holm-adjusted)", "", "| test | raw p | Holm p |", "|---|---|---|"] + \
        [f"| {k} | {v} | {res['secondary_holm_p'][k]} |" for k, v in res["secondary_raw_p"].items()] + \
        ["", f"AUC (anytime trial recovery, completion-time CPU, grid {res['anytime_curve']['grid_cpu_s']}): {res['auc_test']}.",
         "", "| CPU-s per unit | " + " | ".join(str(g) for g in res["anytime_curve"]["grid_cpu_s"]) + " |",
         "|---|" + "---|" * len(res["anytime_curve"]["grid_cpu_s"]),
         "| S-hole-ext tasks | " + " | ".join(map(str, res["anytime_curve"]["S-hole-ext"])) + " |",
         "| S-enum tasks | " + " | ".join(map(str, res["anytime_curve"]["S-enum"])) + " |", "",
         "## Stages per arm (tasks, majority of seeds): trial recovery / admitted (passed regression) / promoted", "",
         "| arm | trial recovery | admitted | promoted |", "|---|---|---|---|"] + \
        [f"| {a} | {v['trial_recovery']} | {v['admitted']} | {v['promoted']} |" for a, v in res["stages"].items()] + \
        ["", f"Excluded-task reuse of promoted structures (scored after the arms freeze): {res['reuse']}.", "",
         "## All task-level comparisons (trial recovery)", "",
         "| comparison | rule | tasks | first | second | only first | only second | p |", "|---|---|---|---|---|---|---|---|"]
    for k, v in res["comparisons"].items():
        for rule in ("majority", "any_seed"):
            c = v[rule]
            L.append(f"| {k} | {rule} | {c['tasks']} | {c['first']} | {c['second']} | {c['only_first']} | "
                     f"{c['only_second']} | {c['exact_mcnemar_p']} |")
    L += ["", "## Per family (trial recovery, majority of seeds)", "", "| family | motivating | " +
          " | ".join(ARMS + ("C7m",)) + " | ext vs matched |", "|---|---|" + "---|" * (len(ARMS) + 2)]
    for op, r in res["per_family"].items():
        L.append(f"| {op} | {r['motivating']} | " + " | ".join(str(r[a]) for a in ARMS + ("C7m",)) +
                 f" | {r['ext_vs_matched_discordant'][0]} : {r['ext_vs_matched_discordant'][1]} |")
    L += ["", f"Mean charged CPU-s per unit (specification cost included): {res['cpu_charged_per_unit']}.", "",
          "## Flow of all 250 concepts", "", "| reason | concepts |", "|---|---|"]
    L += [f"| {k} | {v} |" for k, v in sorted(flow["counts"].items(), key=lambda kv: -kv[1])]
    ex = res["exploratory_pooled_with_U3"]
    L += ["", "## Exploratory (post hoc): U3 replayed with U3b's contrasts", "",
          f"- {ex['label']}: U3 S-hole-ext {ex['U3_ext']} vs replayed S-enum-MATCHED {ex['U3_matched']} of "
          f"{len(ex['U3_units'])}; unavailable replays {ex['unavailable']}.", "",
          "## Claim for the paper", "", "(Written by hand after verification.)", ""]
    with P.open_write(os.path.join(P.REPORTS, "TEST_U3B_REPORT.md")) as f:
        f.write("\n".join(L) + "\n")


if __name__ == "__main__":
    STAGE = {"build": "build", "arms": "arms", "evaluate": "eval"}[sys.argv[1]]
    BAD, _ = GATE.check(STAGE, P.HERE)                       # GO binding, source freeze, generated outputs
    if BAD:
        raise SystemExit(f"provenance gate before {STAGE}: " + "; ".join(BAD))
    {"build": build, "arms": arms, "evaluate": evaluate}[sys.argv[1]]()
