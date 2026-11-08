"""Test I-b steps after generation (PROTOCOL_TEST_IB.md). Called through cgrow.testib:

    process RUN PREP GEN | c7m RUN PREP | merge RUN PREP PROC | evaluate RUN PREP PROC GEN C7M MERGE |
    pilot RUN PREP PROC GEN | status_section
"""
import ast
import collections
import hashlib
import json
import os
import pickle
import random
import resource
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from cgrow import paths as P, experiment as X, episode as EP, invent as IV, lang0 as L0, search as S   # noqa: E402
from cgrow import evaluate as EV, registry as RG, testib as TB                                          # noqa: E402
from a2 import arcdsl as D                                                                              # noqa: E402

C7M_CPU = 150.0
C7M_MEM_GB = 12
ARMS_ALL = ("C2", "C5", "C5n", "C3")


def _dump(path, obj):
    with P.open_write(path) as f:
        json.dump(obj, f, indent=1, default=list)


def _ledger_ib():
    from harness import ledger as LG
    gpu = cpu = 0.0
    for r in LG.read(P.LEDGER):
        if r.get("family") == "CGROW" and str(r.get("run_id", "")).startswith("ib_") and \
                r.get("status") not in ("START", "WAITING", "SKIPPED"):
            gpu += r.get("gpu_wall_h") or 0.0
            cpu += r.get("cpu_h") or 0.0
    return round(gpu, 3), round(cpu, 3)


# ------------------------------------------------------------------ process
def process(run_id, prep_id, gen_id):
    X.process(run_id, prep_id, gen_id, arms=TB.ARMS, reg_prefix="testIb")


# ------------------------------------------------------------------ C7m: matched search
def c7m_one(tid):
    lim = C7M_MEM_GB * (1 << 30)
    resource.setrlimit(resource.RLIMIT_AS, (lim, lim))
    t = X.as_task(X.system_tasks()[tid])
    g0b = X.G0Builder()
    try:
        r = S.run(g0b(), t["train"], t["test_inputs"], budget=10 ** 9, cpu_cap=C7M_CPU)
        out = {k: r[k] for k in ("fit", "program", "level_complete", "stop", "calls", "cpu_s", "closure_capped")}
        out["preds"] = r["preds"]
    except MemoryError:
        out = {"fit": False, "memory_capped": True}
    print("C7M_RESULT " + json.dumps(out, default=list), flush=True)


def c7m(run_id, prep_id):
    path = os.path.join(P.RUNS, run_id, "c7m.json")
    res = X.load_json(path) if os.path.exists(path) else {}
    with open(os.path.join(P.RUNS, prep_id, "records.pkl"), "rb") as f:
        recs = pickle.load(f)
    ev = X.eval_tasks()
    tids = sorted(t for t, v in ev.items() if v["partition"] == "M" and recs[t]["decision"] == "INVENT_NEW_OPERATION")
    for tid in tids:
        if tid in res:
            continue
        p = subprocess.run([sys.executable, "-m", "cgrow.testib", "c7m_one", tid], cwd=HERE, capture_output=True,
                           text=True, timeout=C7M_CPU * 6)
        line = [x for x in p.stdout.splitlines() if x.startswith("C7M_RESULT ")]
        r = json.loads(line[-1][11:]) if line else {"fit": False, "memory_capped": True, "rc": p.returncode,
                                                     "stderr": p.stderr[-300:]}
        r["correct"] = bool(r.get("fit")) and EV.correct(r.get("preds"), ev[tid]["test_outputs"])
        r.pop("preds", None)
        res[tid] = r
        _dump(path, res)
        print(json.dumps({"c7m": tid, "fit": r.get("fit"), "correct": r["correct"], "cpu_s": r.get("cpu_s"),
                          "level": r.get("level_complete")}), flush=True)


# ------------------------------------------------------------------ parametric merge (system side)
class _Lit(ast.NodeTransformer):
    def __init__(self, c):
        self.c, self.hit = c, False

    def visit_Constant(self, node):
        if type(node.value) is int and node.value == self.c:
            self.hit = True
            return ast.copy_location(ast.Name(id="pn", ctx=ast.Load()), node)
        return node


def _abstract(code, c):
    """Replace every integer literal c by a new parameter pn of new_op; None if c does not occur."""
    mod = ast.parse(code)
    if any(isinstance(x, ast.Name) and x.id == "pn" for x in ast.walk(mod)):
        return None
    t = _Lit(c)
    mod = t.visit(mod)
    if not t.hit:
        return None
    for st in mod.body:
        if isinstance(st, ast.FunctionDef) and st.name == "new_op":
            if len(st.args.args) != 1:
                return None
            st.args.args.append(ast.arg(arg="pn"))
    ast.fix_missing_locations(mod)
    return ast.unparse(mod)


def _behaviour(op, ints):
    return tuple(op.apply(x, ints) for x in EP.SIG_PROBES)


def _same(a, b):
    both = [(x, y) for x, y in zip(a, b) if x is not None or y is not None]
    return bool(both) and all(x == y for x, y in both) and sum(x is not None for x, _ in both) >= 10


def merge(run_id, prep_id, proc_id):
    g0b = X.G0Builder()
    sys_t = X.system_tasks()
    with open(os.path.join(P.RUNS, prep_id, "records.pkl"), "rb") as f:
        recs = pickle.load(f)
    solved = {t: X.as_task(sys_t[t]) for t, r in recs.items() if r["status"] == "solved"}
    base_preds = {t: recs[t]["base_preds"][0] for t in solved}
    pool = [(i, X.as_task(sys_t[i])) for i in sorted([t for t, r in recs.items() if r["status"] != "solved"],
                                                    key=lambda i: X.h("pool:" + i))]
    out = {}
    for arm in ARMS_ALL:
        entries = []
        for pref in ("testI", "testIb"):
            rp = os.path.join(P.REGISTRY_DIR, f"{pref}_{arm}.json")
            if os.path.exists(rp):
                for e in X.load_json(rp)["entries"]:
                    if e["status"] in ("promoted", "quarantined") and not e["parameters"]:
                        entries.append((pref, e))
        beh = []
        for pref, e in entries:
            op = IV.SandboxOp({"code": e["implementation"]["source"], "params": []})
            beh.append(_behaviour(op, ()))
        reg = RG.Registry(f"testIb_{arm}_merged", "arcdsl635de49-minus-hidden", g0b.sha)
        merged, seen = [], set()
        for k, (pref, e) in enumerate(entries):
            src = e["implementation"]["source"]
            lits = sorted({n.value for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Constant)
                           and type(n.value) is int and 2 <= n.value <= 9})
            for c in lits:
                code = _abstract(src, c)
                if code is None:
                    continue
                prop = {"code": code, "params": [{"name": "pn", "lo": 2, "hi": 9}], "tests": [],
                        "fields": {"SEMANTICS": f"parametric generalization (constant {c} -> n) of {e['id']}",
                                   "PRECONDITIONS": "none"}}
                try:
                    IV.check(prop)
                except IV.Rejected:
                    continue
                op = IV.SandboxOp(prop)
                if not _same(_behaviour(op, (c,)), beh[k]):
                    continue
                support = {c: [e["id"]]}
                bc = {c2: _behaviour(op, (c2,)) for c2 in range(2, 10) if c2 != c}
                for j, (pref2, e2) in enumerate(entries):
                    if j == k:
                        continue
                    for c2, b2 in bc.items():
                        if _same(b2, beh[j]):
                            support.setdefault(c2, []).append(e2["id"])
                if len(support) < 2:
                    continue
                lo, hi = min(support), max(support)
                prop["params"] = [{"name": "pn", "lo": lo, "hi": hi}]
                op = IV.SandboxOp(prop)
                sig = EP.signature(op)
                if sig in seen:
                    continue
                seen.add(sig)
                head = "f:inv_" + hashlib.sha256(code.encode()).hexdigest()[:10]
                dec = EP.promote_checks(op, head, g0b, solved, pool, base_preds)
                ident = f"param_{hashlib.sha256(code.encode()).hexdigest()[:8]}"
                chk = IV.check(prop)
                ent = reg.entry(ident, prop, chk, [], {"arm": arm, "run_id": run_id, "motivating_tasks": [],
                                                       "parent": ", ".join(f"{i}@1" for v in support.values()
                                                                           for i in v),
                                                       "motivating_failures": []},
                                "undetermined", "kind established by the evaluator's probe search", "quarantined",
                                "constant abstraction supported by instances at " + ", ".join(map(str, sorted(support))))
                vname = f"G2.merge.{arm}.{ident}"
                reg.version(vname, [ident], dec["regression"])
                status = dec["decision"]
                reg.set_status(ent, status if status != "quarantined" else "quarantined",
                               {"promoted": "merged capability passes regression and validation",
                                "rolled_back": "regression on previously solved tasks",
                                "quarantined": "no new fit on unsolved tasks"}[status], vname, dec.get("validation"),
                               scope="persistent" if status == "promoted" else None)
                merged.append({"id": ident, "arm": arm, "from": e["id"], "constant": c, "support": support,
                               "domain": [lo, hi], "decision": status, "regression": dec["regression"],
                               "validation": dec.get("validation"), "code": code,
                               "code_sha256": hashlib.sha256(code.encode()).hexdigest()})
                print(json.dumps({"merged": ident, "arm": arm, "support": support, "decision": status}), flush=True)
        reg.save(os.path.join(P.REGISTRY_DIR, f"testIb_{arm}_merged.json"))
        out[arm] = {"entries_considered": len(entries), "merged": merged}
    _dump(os.path.join(P.RUNS, run_id, "merge.json"), out)


# ------------------------------------------------------------------ evaluation (evaluator side)
def _agreement(op, fam, rem, grids):
    """Best agreement with the removed reference over the family's parameter values, and the per-value table."""
    ref = L0.reference_fn(fam)
    table = {}
    for p in [tuple(x) for x in rem["params"][fam]]:
        ints = p if op.n_params == len(p) else ()
        if op.n_params != len(ints):
            continue
        agree = tot = 0
        for x in grids:
            try:
                want = ref(x, *p)
            except Exception:                                            # noqa: BLE001
                want = None
            got = op.apply(x, ints)
            if want is None and got is None:
                continue
            tot += 1
            agree += want == got
        table[str(list(p))] = round(agree / tot, 4) if tot else None
    vals = [v for v in table.values() if v is not None]
    return (max(vals) if vals else None), table


def _spec_correct(tests, fam, rem):
    """The proposal's own TESTS agree with the reference at one family parameter on every test it accepts."""
    ref = L0.reference_fn(fam)
    if not isinstance(tests, (list, tuple)):
        return None
    best = None
    for p in [tuple(x) for x in rem["params"][fam]]:
        n_ok = n = 0
        for t in tests[:12]:
            try:
                if len(t) == 2:
                    x, y = IV._to_grid(t[0]), IV._to_grid(t[1])
                elif len(t) == 3:
                    x, y = IV._to_grid(t[0]), IV._to_grid(t[2])
                else:
                    continue
            except (TypeError, ValueError):
                continue
            if x is None or y is None:
                continue
            try:
                want = ref(x, *p)
            except Exception:                                            # noqa: BLE001
                continue
            n += 1
            n_ok += want == y
        if n:
            ok = n_ok == n
            best = ok if best is None else (best or ok)
    return best


def _cluster_boot(units, a, b, metric, n=10000, seed=7):
    fams = sorted({u["family"] for u in units})
    by = {f: [u for u in units if u["family"] == f and u.get(a) and u.get(b)] for f in fams}
    r = random.Random(seed)
    means = []
    for _ in range(n):
        pick = [r.choice(fams) for _ in fams]
        d = [int(bool(u[a][metric])) - int(bool(u[b][metric])) for f in pick for u in by[f]]
        if d:
            means.append(sum(d) / len(d))
    means.sort()
    return [round(means[int(0.025 * len(means))], 3), round(means[int(0.975 * len(means))], 3)] if means else None


def _compare(units, a, b, metric="recovered"):
    pairs = [(bool(u[a][metric]), bool(u[b][metric])) for u in units if u.get(a) and u.get(b)]
    if not pairs:
        return None
    bo = sum(x and not y for x, y in pairs)
    co = sum(y and not x for x, y in pairs)
    both = sum(x and y for x, y in pairs)
    return {"units": len(pairs), "both": both, "only_" + a: bo, "only_" + b: co,
            "neither": len(pairs) - both - bo - co, "mcnemar_p": round(EV.mcnemar(bo, co), 4),
            "mean_diff": round((bo - co) / len(pairs), 3),
            "unit_ci95": EV.boot([int(x) - int(y) for x, y in pairs]),
            "family_ci95": _cluster_boot(units, a, b, metric)}


def evaluate(run_id, prep_id, proc_id, gen_id, c7m_id, merge_id):
    rdir = os.path.join(P.RUNS, run_id)
    ev = X.eval_tasks()
    rem = X.load_json(os.path.join(P.EVALUATOR_DIR, "REMOVED.json"))
    plan = X.load_json(os.path.join(P.RUNS, prep_id, "plan.json"))["plan"]
    reps = X.load_replies(os.path.join(P.RUNS, gen_id, "replies.jsonl"))
    eps = {}
    with open(os.path.join(P.RUNS, proc_id, "episodes.jsonl"), encoding="utf-8") as f:
        for x in f:
            if x.strip():
                r = json.loads(x)
                eps[r["episode"]] = r
    c7m = X.load_json(os.path.join(P.RUNS, c7m_id, "c7m.json"))
    mg = X.load_json(os.path.join(P.RUNS, merge_id, "merge.json"))
    g0b = X.G0Builder()
    e_ids = sorted(i for i, t in ev.items() if t["partition"] == "E")
    cache_path = os.path.join(rdir, "eval_cache.pkl")
    cache = {}
    if os.path.exists(cache_path):
        with open(cache_path, "rb") as f:
            cache = pickle.load(f)
    else:
        src = os.path.join(P.RUNS, "eval_v1", "eval_cache.pkl")
        if os.path.exists(src):
            with open(src, "rb") as f:
                cache = {k: v for k, v in pickle.load(f).items() if not k.startswith("c7:")}

    def save_cache():
        with open(P.check_write(cache_path), "wb") as f:
            pickle.dump(cache, f)

    bodies = EV.dsl_bodies()
    fam_grids = {f: [EV.g(a) for t in e_ids if ev[t]["family"] == f for a, _ in ev[t]["train"]] +
                 [EV.g(q) for t in e_ids if ev[t]["family"] == f for q in ev[t]["test_inputs"]] + list(EV.REF_PROBES)
                 for f in rem["removed"]}
    stage = collections.defaultdict(collections.Counter)
    leak = {}
    out_eps = {}
    for ep, er in sorted(eps.items()):
        tid, fam, arm = er["task"], ev[er["task"]]["family"], er["arm"]
        replies = reps[ep]["replies"]
        rec = {"arm": arm, "task": tid, "family": fam, "seed": er["seed"], "spec_correct": 0, "executable": 0,
               "impl_correct": 0, "recovered": False, "n_fitting": er["n_fitting"],
               "gen_tokens": er["gen_tokens"], "prompt_tokens": er["prompt_tokens"], "gpu_s": er["gpu_s"]}
        for row in er["rows"]:
            stage[arm][row.get("outcome", "?")] += 1
            try:
                prop = IV.parse(replies[row["sample"]]["text"])
            except IV.Rejected:
                continue
            if _spec_correct(prop["tests"], fam, rem):
                rec["spec_correct"] += 1
            if "code_sha256" in row:
                leak.setdefault(row["code_sha256"], EV.near_verbatim(prop["code"], bodies, rem["removed"]) |
                                {"episode": ep, "sample": row["sample"]})
            if row.get("outcome") in ("no_fit_on_motivating_task", "fits_motivating_task"):
                rec["executable"] += 1
                k = "agree:" + fam + ":" + row["code_sha256"]
                if k not in cache:
                    try:
                        IV.check(prop)
                        cache[k] = _agreement(IV.SandboxOp(prop), fam, rem, fam_grids[fam])
                    except IV.Rejected:
                        cache[k] = (None, {})
                if (cache[k][0] or 0) >= 0.99:
                    rec["impl_correct"] += 1
            if row.get("outcome") == "fits_motivating_task" and EV.correct(row["retry"]["preds"],
                                                                            ev[tid]["test_outputs"]):
                rec["recovered"] = True
        pick = er["promoted_sample"]
        status = "promoted" if pick is not None else None
        if pick is None:
            fr = [r for r in er["rows"] if r.get("outcome") == "fits_motivating_task"]
            if fr:
                pick, status = fr[0]["sample"], (fr[0].get("promotion") or {}).get("decision", "not_checked")
        rec["op_status"] = status
        rec["reuse_E"] = 0
        if pick is not None:
            prop, op = EV.op_from_episode(replies[pick]["text"])
            key = hashlib.sha256(prop["code"].encode()).hexdigest()
            if key not in cache:
                cache[key] = EV.score_op(prop, op, ev, e_ids, fam, rem, g0b, transfer=(status == "promoted"))
                save_cache()
            sc = cache[key]
            rec.update({"op_sha256": key, "op_kind": sc["kind"], "op_agreement": sc["ref_agreement"],
                        "reuse_E": sc["e_correct_same_family"] if status == "promoted" else 0,
                        "reuse_E_if_kept": sc["e_correct_same_family"]})
        out_eps[ep] = rec
    save_cache()
    # units (seeds 2-4)
    units = []
    for row in plan:
        if row["arm"] != "C5":
            continue
        tid, s = row["task"], row["seed"]
        u = {"task": tid, "family": ev[tid]["family"], "seed": s, "template": ev[tid]["template"],
             "decision": row["controller_decision"]}
        for arm in TB.ARMS:
            e = out_eps.get(f"{arm}_{tid}_s{s}")
            u[arm] = None if e is None else {"recovered": e["recovered"], "promoted": e["op_status"] == "promoted",
                                             "reuse_any": e["reuse_E"] > 0, "reuse_E": e["reuse_E"],
                                             "spec_any": e["spec_correct"] > 0, "impl_any": e["impl_correct"] > 0}
        cm = c7m.get(tid)
        u["C7m"] = None if cm is None else {"recovered": cm["correct"]}
        if u["C5"] is not None:
            units.append(u)
    comp = {"primary_C5_vs_C2": _compare(units, "C5", "C2")}
    for a, b in (("C5", "C5n"), ("C5", "C3"), ("C5", "C7m"), ("C5n", "C2"), ("C2", "C3")):
        comp[f"{a}_vs_{b}:recovered"] = _compare(units, a, b)
    for a, b in (("C5", "C2"), ("C5", "C5n")):
        for m in ("promoted", "reuse_any", "spec_any", "impl_any"):
            comp[f"{a}_vs_{b}:{m}"] = _compare(units, a, b, m)
    pc = comp["primary_C5_vs_C2"]
    pc["decision"] = ("C5 beats C2" if pc and pc["mcnemar_p"] < 0.05 and pc["family_ci95"] and pc["family_ci95"][0] > 0
                      else ("tie" if pc and pc["only_C5"] == pc["only_C2"] else "inconclusive"))
    # pooled seeds 0-4 (secondary): Test I units from eval_v1
    pooled = list(units)
    r1 = os.path.join(P.RUNS, "eval_v1", "results.json")
    if os.path.exists(r1):
        for u in X.load_json(r1)["units"]:
            v = {"task": u["task"], "family": u["family"], "seed": u["seed"]}
            for arm in ("C2", "C3", "C5"):
                v[arm] = None if u.get(arm) is None else {"recovered": u[arm]["recovered"], "promoted": u[arm]["promoted"]}
            v["C5n"] = None
            if v["C5"] is not None:
                pooled.append(v)
    comp["pooled_seeds0to4_C5_vs_C2"] = _compare(pooled, "C5", "C2")
    comp["pooled_seeds0to4_C5_vs_C3"] = _compare(pooled, "C5", "C3")
    # merged operations
    merged_scores = {}
    for arm, v in mg.items():
        for m in v["merged"]:
            prop = {"code": m["code"], "params": [{"name": "pn", "lo": m["domain"][0], "hi": m["domain"][1]}],
                    "tests": [], "fields": {}}
            op = IV.SandboxOp(prop)
            fams = sorted({ev[t]["family"] for t in e_ids})
            best_f, best = None, -1
            for f in fams:
                a, tab = _agreement(op, f, rem, fam_grids[f])
                if (a or 0) > best:
                    best_f, best, best_tab = f, a or 0, tab
            k = "merged:" + m["code_sha256"]
            if k not in cache:
                cache[k] = EV.score_op(prop, op, ev, e_ids, best_f, rem, g0b, transfer=True)
                save_cache()
            sc = cache[k]
            merged_scores[m["id"]] = {"arm": arm, "family": best_f, "agreement_by_param": best_tab,
                                      "decision": m["decision"], "support": m["support"], "domain": m["domain"],
                                      "e_same_family": sc["e_correct_same_family"], "e_total": sc["e_same_family_total"],
                                      "e_other": sc["e_correct_other_families"], "kind": sc["kind"]}
    per_cap = {}
    for f in rem["removed"]:
        per_cap[f] = {}
        for arm in TB.ARMS:
            es = [e for e in out_eps.values() if e["family"] == f and e["arm"] == arm]
            per_cap[f][arm] = {"episodes": len(es), "spec_units": sum(e["spec_correct"] > 0 for e in es),
                               "impl_units": sum(e["impl_correct"] > 0 for e in es),
                               "recovered": sum(e["recovered"] for e in es),
                               "promoted": sum(e["op_status"] == "promoted" for e in es),
                               "reuse_E": sum(e["reuse_E"] for e in es),
                               "kinds": dict(collections.Counter(e.get("op_kind") for e in es
                                                                 if e["op_status"] == "promoted"))}
        per_cap[f]["C7m"] = sum(1 for t, v in c7m.items() if ev[t]["family"] == f and v["correct"])
    rolled = sum(1 for e in eps.values() for r in e["rows"] if (r.get("promotion") or {}).get("decision") == "rolled_back")
    res = {"units": units, "comparisons": comp, "per_capability": per_cap, "stages": {a: dict(c) for a, c in stage.items()},
           "episodes": out_eps, "merged": merged_scores, "c7m": c7m, "rolled_back_candidates": rolled,
           "leak": {"scanned": len(leak), "near_verbatim_ge_0.70": sum(v["max_ratio"] >= 0.7 for v in leak.values()),
                    "removed_names": sum(bool(v["removed_names_in_code"]) for v in leak.values())},
           "budget_ib": dict(zip(("gpu_h", "cpu_h"), _ledger_ib()))}
    _dump(os.path.join(rdir, "results.json"), res)
    write_report(res)
    print(json.dumps({"primary": comp["primary_C5_vs_C2"]}), flush=True)


def _fmt(c):
    if not c:
        return "n/a"
    a, b = [k[5:] for k in c if k.startswith("only_")]
    return (f"{c['units']} units: both {c['both']}, {a} only {c['only_' + a]}, {b} only {c['only_' + b]}, neither "
            f"{c['neither']}; exact McNemar p = {c['mcnemar_p']}; mean difference {c['mean_diff']} (units "
            f"{c['unit_ci95']}, family-clustered {c['family_ci95']})")


def write_report(res):
    comp, pc = res["comparisons"], res["per_capability"]
    L = ["# Test I-b report (written automatically by the detached chain)", "",
         "Protocol `PROTOCOL_TEST_IB.md` (frozen, sha256 in `partitions/TEST_IB_FREEZE.json`). Capability recovery, "
         "seeds 2-4, arms C2 (failure-blind), C5 (own failure report), C5n (C5 without sketches), C3 (shuffled), C7m "
         "(G0 search, 150 CPU-s per task). Results: `runs/ib_eval/results.json`; registries `registry/testIb_*.json`.",
         "", "## Primary comparison (decision rule: exact McNemar p < 0.05 and family-clustered interval above 0)", "",
         f"- C5 vs C2, motivating recovery: {_fmt(comp['primary_C5_vs_C2'])}.",
         f"- **Decision: {comp['primary_C5_vs_C2']['decision'] if comp['primary_C5_vs_C2'] else 'n/a'}.**", "",
         "## Secondary comparisons (no decision weight)", ""]
    for k in ("C5_vs_C5n:recovered", "C5_vs_C3:recovered", "C5_vs_C7m:recovered", "C5n_vs_C2:recovered",
              "C2_vs_C3:recovered", "C5_vs_C5n:promoted", "C5_vs_C2:promoted", "C5_vs_C2:reuse_any", "C5_vs_C2:spec_any",
              "C5_vs_C2:impl_any", "pooled_seeds0to4_C5_vs_C2", "pooled_seeds0to4_C5_vs_C3"):
        L.append(f"- {k}: {_fmt(comp.get(k))}.")
    L += ["", "## Outcome stages per capability (units with at least one: correct specification / correct "
          "implementation / recovered / promoted; reuse = excluded same-family tasks solved by promoted operations)", "",
          "| capability | arm | episodes | spec | impl | recovered | promoted | reuse E | kinds |", "|---|---|---|---|---|---|---|---|---|"]
    for f, v in pc.items():
        for arm in TB.ARMS:
            a = v[arm]
            L.append(f"| {f} | {arm} | {a['episodes']} | {a['spec_units']} | {a['impl_units']} | {a['recovered']} | "
                     f"{a['promoted']} | {a['reuse_E']} | {a['kinds'] or '-'} |")
        L.append(f"| {f} | C7m (150 CPU-s search) | - | | | {v['C7m']} task(s) | | | |")
    L += ["", f"Diagnosis: the controller decision is unchanged from Test I (INVENT on all 11 motivating tasks used). "
          f"Regression avoidance: {res['rolled_back_candidates']} candidate(s) rolled back. Search shortcuts rejected by "
          f"the novelty gate: " + ", ".join(f"{a} {res['stages'].get(a, {}).get('duplicate_of_G0_program', 0)}"
                                            for a in TB.ARMS) + ". New relations: 0 (Grid -> Grid interface).", "",
          "## Parametric merge", ""]
    if res["merged"]:
        for k, m in res["merged"].items():
            L.append(f"- {k} ({m['arm']}): support {m['support']}, domain {m['domain']}, decision {m['decision']}; "
                     f"agreement with the {m['family']} reference by parameter {m['agreement_by_param']}; excluded "
                     f"tasks solved {m['e_same_family']}/{m['e_total']} same family, {m['e_other']} other; kind {m['kind']}.")
    else:
        L.append("- No merge: no arm held two instances of one operation differing only in a constant.")
    L += ["", f"Leak scan: {res['leak']['scanned']} distinct codes, {res['leak']['near_verbatim_ge_0.70']} near-verbatim "
          f"arc-dsl, {res['leak']['removed_names']} using a removed name. Test I-b budget (ledger, runs ib_*): "
          f"{res['budget_ib']['gpu_h']} GPU-h, {res['budget_ib']['cpu_h']} CPU-h (ceiling 2.7 / 3.5).", ""]
    os.makedirs(P.REPORTS, exist_ok=True)
    with P.open_write(os.path.join(P.REPORTS, "TEST_IB_REPORT.md")) as f:
        f.write("\n".join(L) + "\n")
    tables = [x for x in L if x.startswith("|") or x.startswith("- C5") or x.startswith("- pooled") or
              x.startswith("- C2") or x.startswith("- **Decision")]
    with P.open_write(os.path.join(P.REPORTS, "TEST_IB_TABLES.md")) as f:
        f.write("# Test I-b tables (written automatically; full text in TEST_IB_REPORT.md)\n\n" +
                "\n".join(tables) + "\n")


# ------------------------------------------------------------------ exploratory pilot
def pilot(run_id, prep_id, proc_id, gen_id):
    out_path = os.path.join(P.RUNS, run_id, "pilot.json")
    gpu, cpu = _ledger_ib()
    if gpu >= 2.5 or cpu >= 3.2:
        _dump(out_path, {"skipped": f"budget gate: Test I-b used {gpu} GPU-h, {cpu} CPU-h"})
        return
    ev = X.eval_tasks()
    rem = X.load_json(os.path.join(P.EVALUATOR_DIR, "REMOVED.json"))
    sys_t = X.system_tasks()
    g0b = X.G0Builder()
    dsl, consts, _, _ = D.load()
    evl = D.Evaluator(D.guarded(dsl), consts)
    srcs = [("process_v1", "gen1c"), (proc_id, gen_id)]
    rows, seen = [], set()
    t0 = time.process_time()
    for proc, gen in srcs:
        reps = X.load_replies(os.path.join(P.RUNS, gen, "replies.jsonl"))
        with open(os.path.join(P.RUNS, proc, "episodes.jsonl"), encoding="utf-8") as f:
            eps = [json.loads(x) for x in f if x.strip()]
        for er in eps:
            tid, fam = er["task"], ev[er["task"]]["family"]
            for i, rep in enumerate(reps[er["episode"]]["replies"]):
                try:
                    prop = IV.parse(rep["text"])
                except IV.Rejected:
                    continue
                tests = prop["tests"] if isinstance(prop["tests"], list) else []
                pairs = []
                for t in tests[:6]:
                    try:
                        if len(t) == 2:
                            x, y = IV._to_grid(t[0]), IV._to_grid(t[1])
                        else:
                            continue
                    except (TypeError, ValueError):
                        continue
                    if x is not None and y is not None:
                        pairs.append((x, y))
                key = (tid, repr(pairs))
                if len(pairs) < 2 or key in seen:
                    continue
                seen.add(key)
                spec_ok = _spec_correct(tests, fam, rem)
                r = S.run(g0b(), pairs[:-1], [pairs[-1][0]], budget=200_000, cpu_cap=5.0, want=1)
                row = {"episode": er["episode"], "sample": i, "task": tid, "family": fam, "spec_correct": spec_ok,
                       "completion": None, "recovered": False}
                if r["fit"] and r["preds"] and r["preds"][0][0] == pairs[-1][1]:
                    tree = r["program_tree"]
                    row["completion"] = r["program"]

                    def macro(grid, _t=tree):
                        v = evl.run(_t, grid)
                        if D.tag(v) != "G":
                            raise D.Bad("not a grid")
                        return v
                    g1 = g0b()
                    L0.add_production(g1, "f:inv_macro", macro, 0)
                    t = X.as_task(sys_t[tid])
                    rr = S.run(g1, t["train"], t["test_inputs"])
                    row["recovered"] = rr["fit"] and EV.correct(rr["preds"], ev[tid]["test_outputs"])
                    row["retry_program"] = rr["program"]
                rows.append(row)
                if time.process_time() - t0 > 1500:
                    break
    summ = collections.defaultdict(collections.Counter)
    for r in rows:
        summ[r["family"]]["specs"] += 1
        summ[r["family"]]["spec_correct"] += bool(r["spec_correct"])
        summ[r["family"]]["completed"] += r["completion"] is not None
        summ[r["family"]]["completed_and_spec_correct"] += r["completion"] is not None and bool(r["spec_correct"])
        summ[r["family"]]["recovered"] += r["recovered"]
    out = {"label": "EXPLORATORY, outside the causal test", "rows": rows,
           "summary": {f: dict(c) for f, c in summ.items()}, "cpu_s": round(time.process_time() - t0, 1)}
    _dump(out_path, out)
    lines = ["", "## Exploratory pilot: neural specification + symbolic completion over G0 (outside the causal test)", "",
             "Each distinct proposal's TESTS (at least two well-formed) were completed by a G0 search; a found program "
             "was added as a macro and the motivating task retried. G0 cannot express compress, downscale or upscale "
             "within cost 12, so only macros are possible.", "",
             "| family | distinct specs | specs correct (evaluator) | completed over G0 | completed and correct spec | "
             "motivating task recovered |", "|---|---|---|---|---|---|"]
    for f, c in sorted(out["summary"].items()):
        lines.append(f"| {f} | {c.get('specs', 0)} | {c.get('spec_correct', 0)} | {c.get('completed', 0)} | "
                     f"{c.get('completed_and_spec_correct', 0)} | {c.get('recovered', 0)} |")
    with P.open_write(os.path.join(P.REPORTS, "TEST_IB_REPORT.md"), "a") as f:
        f.write("\n".join(lines) + "\n")


# ------------------------------------------------------------------ status section of PROGRESS.md
def status_section():
    p = os.path.join(P.HERE, "PROGRESS.md")
    with open(p, encoding="utf-8") as f:
        s = f.read()
    head = s.split("## Current status (for 31 Oct)")[0].rstrip() + "\n\n"
    rp = os.path.join(P.RUNS, "ib_eval", "results.json")
    lines = ["## Current status (for 31 Oct)", "", f"Updated {time.strftime('%d %b %H:%MZ', time.gmtime())} by the "
             "Test I-b chain.", "- **Test I: DONE** (`reports/TEST_I_REPORT.md`): units recovered of 22: C5 6, C2 2, "
             "C1 2, C3 0, C7 0; C5 vs C2 p = 0.125."]
    if os.path.exists(rp):
        r = X.load_json(rp)
        pc = r["comparisons"]["primary_C5_vs_C2"]
        lines.append(f"- **Test I-b: DONE** (`reports/TEST_IB_REPORT.md`). Primary C5 vs C2: {_fmt(pc)}. "
                     f"Decision: **{pc['decision']}**. Budget {r['budget_ib']}.")
        for k in ("C5_vs_C5n:recovered", "C5_vs_C7m:recovered", "pooled_seeds0to4_C5_vs_C2"):
            lines.append(f"  - {k}: {_fmt(r['comparisons'].get(k))}")
        lines.append(f"  - merged parametric operations: {len(r['merged'])} "
                     f"({', '.join(m['decision'] for m in r['merged'].values()) or 'none'})")
    else:
        lines.append("- Test I-b: evaluation output missing; see `runs/ib_chain/run.status`.")
    pp = os.path.join(P.RUNS, "ib_pilot", "pilot.json")
    if os.path.exists(pp):
        q = X.load_json(pp)
        lines.append(f"- Exploratory pilot: {q.get('skipped') or q.get('summary')}")
    lines.append("- Next: the coordinator reads `reports/TEST_IB_REPORT.md`; no further run is authorized.")
    with P.open_write(p) as f:
        f.write(head + "\n".join(lines) + "\n")
