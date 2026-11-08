"""Test I scoring (EVALUATOR SIDE; reads evaluator_only/; nothing flows back to the system).

    python -m cgrow.evaluate RUN_ID PREP_ID PROC_ID GEN1_ID GEN2_ID

1. Level choice: the controller's decision on every system task against the truth (family tasks: operation; trim
   is a G0 macro at cost 10, so search is also correct there; decoys: search; previously solved: no failure); the
   proposer's stated LEVEL per arm.
2. Task-level recovery: an invention episode recovers its motivating task when a fitting proposal predicts the
   query output (pass@2), with the operation promoted or only task-local.
3. Cross-task reuse: every scored operation (by source hash) is added to G0 and the base search is run on its
   family's 6 excluded tasks (E); promoted operations also on the other 18 (transfer).
4. Agreement with the removed reference on the family's E inputs plus 40 seeded probe grids (all shared
   parameter values).
5. Kind: a G0 search on 12 probe grids (1M executions, 30 s cap) that reproduces the operation makes it a macro (witness and
   cost); otherwise an expansion within that bound.
6. C7 = G0 search with 20 times the base budget (CPU cap 60 s) on M and E tasks; C1 = whole programs written by
   the same model (2 samples + 2 repairs per task and seed) in the same sandbox.
7. Near-verbatim scan of every proposal against arc-dsl's dsl.py function bodies (token sequence ratio).
8. Paired comparisons on units (family, motivating task, seed): exact McNemar; bootstrap over units.
"""
import hashlib
import io
import json
import math
import os
import pickle
import random
import sys
import tokenize

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from cgrow import paths as P, lang0 as L0, search as S, invent as IV, episode as EP, probes as PR  # noqa: E402
from cgrow import experiment as X, controller as CT                                               # noqa: E402
from a2 import arcdsl as D                                                                         # noqa: E402

C7_FACTOR = 20
KIND_BUDGET = 1_000_000
REF_PROBES = PR.probe_grids(40, seed=99, min_side=2, max_side=10)


def g(x):
    return tuple(tuple(r) for r in x)


def correct(preds, outs):
    want = [g(y) for y in outs]
    return bool(preds) and any([g(p) for p in att] == want for att in preds)


def truth_level(t):
    if t["partition"] in ("M", "V", "E"):
        return {"operation", "search"} if t["family"] == "trim" else {"operation"}
    if t["partition"] == "D":
        return {"search"}
    return {None}


def tokens(src):
    out = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            if tok.type in (tokenize.NAME, tokenize.OP, tokenize.NUMBER):
                out.append(tok.string)
    except (tokenize.TokenError, IndentationError, SyntaxError):
        pass
    return out


def dsl_bodies():
    import ast
    _, _, src, _ = D.load()
    out = {}
    for f in ast.parse(src).body:
        if isinstance(f, ast.FunctionDef):
            body = [s for s in f.body if not (isinstance(s, ast.Expr) and isinstance(getattr(s, "value", None),
                                                                                     ast.Constant))]
            out[f.name] = tokens(ast.unparse(ast.Module(body=body, type_ignores=[])))
    return out


def near_verbatim(code, bodies, removed):
    import difflib
    tk = tokens(code)
    best = (0.0, None)
    for name, bt in bodies.items():
        if len(bt) < 12:
            continue
        r = difflib.SequenceMatcher(None, tk, bt, autojunk=False).ratio()
        if r > best[0]:
            best = (r, name)
    names = sorted({n for n in removed if n in tk})
    return {"max_ratio": round(best[0], 3), "closest_dsl_function": best[1], "removed_names_in_code": names}


def mcnemar(b, c):
    """Exact two-sided binomial test on discordant pairs b (first arm only) and c (second arm only)."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    p = sum(math.comb(n, i) for i in range(0, k + 1)) / 2 ** n
    return min(1.0, 2 * p)


def boot(diffs, n=10000, seed=1):
    if not diffs:
        return None
    r = random.Random(seed)
    m = len(diffs)
    means = sorted(sum(diffs[r.randrange(m)] for _ in range(m)) / m for _ in range(n))
    return [round(means[int(0.025 * n)], 3), round(means[int(0.975 * n)], 3)]


def op_from_episode(reply_text):
    prop = IV.parse(reply_text)
    IV.check(prop)
    return prop, IV.SandboxOp(prop)


def diag_scores(diag_id, gen2_id, ev, rem):
    """D0 (evaluator-only ceiling probe): per motivating task, the share of executable proposals that agree with the
    removed reference, and whether a proposal recovers the motivating task."""
    path = os.path.join(P.RUNS, diag_id, "diag_episodes.jsonl")
    if diag_id == "-" or not os.path.exists(path):
        return {}
    reps = X.load_replies(os.path.join(P.RUNS, gen2_id, "replies.jsonl"))
    e_ids = sorted(i for i, t in ev.items() if t["partition"] == "E")
    out = {}
    with open(path, encoding="utf-8") as f:
        rows = [json.loads(x) for x in f if x.strip()]
    for r in rows:
        tid, fam = r["task"], ev[r["task"]]["family"]
        ref = L0.reference_fn(fam)
        pvals = [tuple(p) for p in rem["params"][fam]]
        grids = [g(a) for t in e_ids if ev[t]["family"] == fam for a, _ in ev[t]["train"]] + list(REF_PROBES)
        rec = {"family": fam, "stages": {}, "agreements": [], "recovered": False}
        for row in r["rows"]:
            rec["stages"][row.get("outcome", "?")] = rec["stages"].get(row.get("outcome", "?"), 0) + 1
            if row.get("outcome") == "fits_motivating_task" and correct(row["retry"]["preds"], ev[tid]["test_outputs"]):
                rec["recovered"] = True
            if "check" not in row:
                continue
            try:
                prop, op = op_from_episode(reps[r["episode"]]["replies"][row["sample"]]["text"])
            except IV.Rejected:
                continue
            best = 0.0
            for p in pvals:
                ints = p if op.n_params == len(p) else ()
                if op.n_params != len(ints):
                    continue
                agree = tot = 0
                for x in grids:
                    try:
                        want = ref(x, *p)
                    except Exception:                                # noqa: BLE001
                        want = None
                    got = op.apply(x, ints)
                    if want is None and got is None:
                        continue
                    tot += 1
                    agree += want == got
                best = max(best, agree / tot if tot else 0.0)
            rec["agreements"].append(round(best, 3))
        out[r["episode"]] = rec
    return out


def main(run_id, prep_id, proc_id, gen1_id, gen2_id, diag_id="-"):
    rdir = os.path.join(P.RUNS, run_id)
    os.makedirs(rdir, exist_ok=True)
    ev = X.eval_tasks()
    rem = X.load_json(os.path.join(P.EVALUATOR_DIR, "REMOVED.json"))
    fams = rem["removed"]
    with open(os.path.join(P.RUNS, prep_id, "records.pkl"), "rb") as f:
        recs = pickle.load(f)
    plan = X.load_json(os.path.join(P.RUNS, prep_id, "plan.json"))["plan"]
    eps = {}
    with open(os.path.join(P.RUNS, proc_id, "episodes.jsonl"), encoding="utf-8") as f:
        for x in f:
            if x.strip():
                r = json.loads(x)
                eps[r["episode"]] = r
    rep1 = X.load_replies(os.path.join(P.RUNS, gen1_id, "replies.jsonl"))
    rep2 = X.load_replies(os.path.join(P.RUNS, gen2_id, "replies.jsonl")) if gen2_id != "-" else {}
    g0b = X.G0Builder()
    out = {"levels": {}, "episodes": {}, "ops": {}, "c7": {}, "c1": {}, "leak": {}, "units": []}
    cache_path = os.path.join(rdir, "eval_cache.pkl")
    cache = {}
    if os.path.exists(cache_path):
        with open(cache_path, "rb") as f:
            cache = pickle.load(f)

    def save_cache():
        with open(P.check_write(cache_path), "wb") as f:
            pickle.dump(cache, f)

    # 1. level choice
    lv = []
    for tid, r in recs.items():
        t = ev[tid]
        ok = r["level"] in truth_level(t)
        lv.append({"task": tid, "partition": t["partition"], "family": t["family"], "decision": r["decision"],
                   "level": r["level"], "right": ok})
    out["levels"]["controller"] = lv
    # 2-5. episodes and operations
    e_ids = sorted(i for i, t in ev.items() if t["partition"] == "E")
    bodies = dsl_bodies()
    for ep, er in sorted(eps.items()):
        tid, fam = er["task"], ev[er["task"]]["family"]
        replies = rep1[ep]["replies"]
        rec = {"arm": er["arm"], "task": tid, "family": fam, "seed": er["seed"], "n_fitting": er["n_fitting"],
               "promoted_sample": er["promoted_sample"], "prompt_tokens": er["prompt_tokens"],
               "gen_tokens": er["gen_tokens"], "gpu_s": er["gpu_s"], "cpu_s": er["cpu_s"], "stages": {},
               "stated_levels": [], "recovered_motivating": False, "recovered_by": None}
        for row in er["rows"]:
            rec["stages"][row.get("outcome", "?")] = rec["stages"].get(row.get("outcome", "?"), 0) + 1
            if row.get("fields"):
                rec["stated_levels"].append((row["fields"].get("LEVEL") or "").strip().lower()[:30])
            if row.get("outcome") == "fits_motivating_task" and correct(row["retry"]["preds"], ev[tid]["test_outputs"]):
                if not rec["recovered_motivating"]:
                    rec["recovered_motivating"], rec["recovered_by"] = True, row["sample"]
            if "code_sha256" in row:
                try:
                    prop = IV.parse(replies[row["sample"]]["text"])
                    out["leak"].setdefault(row["code_sha256"], near_verbatim(prop["code"], bodies, fams) |
                                           {"episode": ep, "sample": row["sample"]})
                except IV.Rejected:
                    pass
        # the operation to score: the promoted one, else the first that fits the motivating task (task-local)
        pick = er["promoted_sample"]
        status = "promoted" if pick is not None else None
        if pick is None:
            fit_rows = [r for r in er["rows"] if r.get("outcome") == "fits_motivating_task"]
            if fit_rows:
                pick = fit_rows[0]["sample"]
                status = (fit_rows[0].get("promotion") or {}).get("decision", "not_checked")
        rec["scored_op"] = {"sample": pick, "status": status}
        if pick is not None:
            prop, op = op_from_episode(replies[pick]["text"])
            key = hashlib.sha256(prop["code"].encode()).hexdigest()
            rec["scored_op"]["code_sha256"] = key
            if key not in cache:
                cache[key] = score_op(prop, op, ev, e_ids, fam, rem, g0b, transfer=(status == "promoted"))
                save_cache()
            rec["scored_op"]["family_of_motivating"] = fam
        out["episodes"][ep] = rec
    for key, v in cache.items():
        if key.startswith("c7:") or key.startswith("c1:"):
            continue
        out["ops"][key] = v
    # 6. C7 and C1
    for tid in sorted(i for i, t in ev.items() if t["partition"] in ("M", "E")):
        k = "c7:" + tid
        if k not in cache:
            t = X.as_task(ev[tid])
            r = S.run(g0b(), t["train"], t["test_inputs"], budget=S.BASE_BUDGET * C7_FACTOR, cpu_cap=60.0)
            cache[k] = {"fit": r["fit"], "correct": r["fit"] and correct(r["preds"], ev[tid]["test_outputs"]),
                        "program": r["program"], "level_complete": r["level_complete"], "cpu_s": r["cpu_s"],
                        "calls": r["calls"]}
            save_cache()
            print(json.dumps({"c7": tid, "fit": r["fit"], "cpu_s": r["cpu_s"]}), flush=True)
        out["c7"][tid] = cache[k]
    c1r1 = {}
    with open(os.path.join(P.RUNS, proc_id, "c1_round1.jsonl"), encoding="utf-8") as f:
        for x in f:
            if x.strip():
                r = json.loads(x)
                c1r1[r["job_id"]] = r
    sb = IV.SB.default()
    for jid, r in c1r1.items():
        tid, s = r["task"], jid.split("_")[2]
        ok = any(row.get("fit") and row.get("query_pred") is not None and
                 [g(row["query_pred"])] == [g(y) for y in ev[tid]["test_outputs"][:1]] for row in r["rows"])
        fits = sum(bool(row.get("fit")) for row in r["rows"])
        toks = sum(row["gen_tokens"] for row in r["rows"])
        for i in range(len(r["rows"])):
            rj = rep2.get(f"C1r2_{tid}_{s}_{i}")
            if not rj:
                continue
            toks += sum(x["gen_tokens"] for x in rj["replies"])
            code, err = X.c1_program(rj["replies"][0]["text"])
            if code is None:
                continue
            res = X.c1_run(code, X.as_task(ev[tid]), sb)
            fits += res["fit"]
            if res["fit"] and res["query_pred"] is not None and [res["query_pred"]] == [g(y) for y in
                                                                                     ev[tid]["test_outputs"][:1]]:
                ok = True
        out["c1"][f"{tid}_{s}"] = {"task": tid, "seed": s, "correct": ok, "fits": fits, "gen_tokens": toks,
                                   "partition": ev[tid]["partition"]}
    # 8. units and paired comparisons
    units = []
    for row in plan:
        if row["arm"] != "C5":
            continue
        tid, s = row["task"], row["seed"]
        u = {"task": tid, "family": ev[tid]["family"], "seed": s, "template": ev[tid]["template"],
             "decision": row["controller_decision"]}
        for arm in ("C2", "C3", "C5"):
            e = out["episodes"].get(f"{arm}_{tid}_s{s}")
            if e is None:
                u[arm] = None
                continue
            so = e["scored_op"]
            ops = out["ops"].get(so.get("code_sha256")) if so.get("code_sha256") else None
            reuse = ops["e_correct_same_family"] if ops and so["status"] == "promoted" else 0
            reuse_any_status = ops["e_correct_same_family"] if ops else 0
            u[arm] = {"recovered": e["recovered_motivating"], "promoted": so["status"] == "promoted",
                      "reuse_E": reuse, "reuse_E_if_kept": reuse_any_status,
                      "ref_agreement": ops["ref_agreement"] if ops else None, "kind": ops["kind"] if ops else None,
                      "gen_tokens": e["gen_tokens"], "prompt_tokens": e["prompt_tokens"]}
        u["C7"] = {"recovered": out["c7"][tid]["correct"]}
        c1 = out["c1"].get(f"{tid}_s{s}")
        u["C1"] = {"recovered": c1["correct"] if c1 else None}
        units.append(u)
    out["units"] = units
    comp = {}
    for a, b in (("C5", "C2"), ("C5", "C3"), ("C5", "C7"), ("C5", "C1"), ("C2", "C3")):
        for metric in ("recovered", "promoted", "reuse_any"):
            pairs = []
            for u in units:
                if u.get(a) is None or u.get(b) is None:
                    continue
                if metric == "reuse_any":
                    if b in ("C7", "C1"):
                        continue
                    va, vb = u[a]["reuse_E"] > 0, u[b]["reuse_E"] > 0
                elif metric == "promoted":
                    if b in ("C7", "C1"):
                        continue
                    va, vb = u[a]["promoted"], u[b]["promoted"]
                else:
                    va, vb = bool(u[a]["recovered"]), bool(u[b]["recovered"])
                pairs.append((va, vb))
            if not pairs:
                continue
            both = sum(x and y for x, y in pairs)
            bo = sum(x and not y for x, y in pairs)
            co = sum(y and not x for x, y in pairs)
            comp[f"{a}_vs_{b}:{metric}"] = {"units": len(pairs), "both": both, "only_" + a: bo, "only_" + b: co,
                                            "neither": len(pairs) - both - bo - co, "mcnemar_p": round(mcnemar(bo, co), 4),
                                            "diff_ci95": boot([int(x) - int(y) for x, y in pairs])}
        if b not in ("C7", "C1"):
            d = [u[a]["reuse_E"] - u[b]["reuse_E"] for u in units if u.get(a) and u.get(b)]
            if d:
                comp[f"{a}_vs_{b}:reuse_E_count"] = {"units": len(d), "mean_diff": round(sum(d) / len(d), 3),
                                                     "diff_ci95": boot(d)}
    out["comparisons"] = comp
    out["diag_D0"] = diag_scores(diag_id, gen2_id, ev, rem)
    # E-task view: C7 and C1 per E task
    out["e_tasks"] = {tid: {"family": ev[tid]["family"], "c7": out["c7"][tid]["correct"],
                            "c1": (out["c1"].get(f"{tid}_s0") or {}).get("correct")} for tid in e_ids}
    with P.open_write(os.path.join(rdir, "results.json")) as f:
        json.dump(out, f, indent=1, default=list)
    print(json.dumps({"comparisons": comp}, indent=1, default=list))


def score_op(prop, op, ev, e_ids, fam, rem, g0b, transfer=False):
    """Evaluator scoring of one operation: E solves (own family; all families when promoted), reference agreement,
    kind."""
    res = {"family_of_motivating": fam, "params": prop["params"], "e": {}, "transfer_scored": transfer}
    head = "f:inv_" + hashlib.sha256(prop["code"].encode()).hexdigest()[:10]
    for tid in e_ids:
        if not transfer and ev[tid]["family"] != fam:
            continue
        t = X.as_task(ev[tid])
        r = EP.retry(t, g0b, op, head)
        res["e"][tid] = {"fit": r["fit"], "correct": r["fit"] and correct(r["preds"], ev[tid]["test_outputs"]),
                         "family": ev[tid]["family"], "program": r["program"], "op_capped": r["op_capped"]}
    res["e_correct_same_family"] = sum(v["correct"] for v in res["e"].values() if v["family"] == fam)
    res["e_correct_other_families"] = sum(v["correct"] for v in res["e"].values() if v["family"] != fam)
    res["e_same_family_total"] = sum(1 for v in res["e"].values() if v["family"] == fam)
    # agreement with the removed reference of the motivating family
    ref = L0.reference_fn(fam)
    pvals = [tuple(p) for p in rem["params"][fam]]
    grids = [g(a) for tid in e_ids if ev[tid]["family"] == fam for a, _ in ev[tid]["train"]] + \
        [g(q) for tid in e_ids if ev[tid]["family"] == fam for q in ev[tid]["test_inputs"]] + list(REF_PROBES)
    best, best_tot, best_p = None, 0, None
    for p in pvals:
        # an operation with the family's parameter is compared at that parameter; a parameter-free operation is
        # compared with the reference at each parameter value (the best value is kept)
        ints = p if op.n_params == len(p) else ()
        if op.n_params != len(ints):
            continue
        agree = tot = 0
        for x in grids:
            try:
                want = ref(x, *p)
            except Exception:                                    # noqa: BLE001
                want = None
            got = op.apply(x, ints)
            if want is None and got is None:
                continue
            tot += 1
            agree += want == got
        if tot and (best is None or agree / tot > best):
            best, best_tot, best_p = agree / tot, tot, list(p)
    res["ref_agreement"] = round(best, 4) if best is not None else None
    res["ref_param"] = best_p
    tot = best_tot
    res["ref_compared"] = tot
    # kind: a G0 program reproducing the op on probe grids?
    wit = []
    for ints in EP.bindings(op)[:2]:
        pairs = [(x, op.apply(x, ints)) for x in EP.SIG_PROBES[:12]]
        pairs = [(x, y) for x, y in pairs if y is not None]
        if len(pairs) < 4:
            continue
        r = S.run(g0b(), pairs[:-1], [pairs[-1][0]], budget=KIND_BUDGET, cpu_cap=30.0, want=1)
        hit = r["fit"] and r["preds"] and r["preds"][0][0] == pairs[-1][1]
        wit.append({"binding": list(ints), "g0_program": r["program"] if hit else None,
                    "level_complete": r["level_complete"], "probes": len(pairs)})
    res["kind_witnesses"] = wit
    res["kind"] = "macro" if wit and all(w["g0_program"] for w in wit) else ("expansion" if wit else "undetermined")
    print(json.dumps({"op": head, "fam": fam, "e_same": res["e_correct_same_family"], "agree": res["ref_agreement"],
                      "kind": res["kind"]}), flush=True)
    return res


if __name__ == "__main__":
    main(*sys.argv[1:7])
