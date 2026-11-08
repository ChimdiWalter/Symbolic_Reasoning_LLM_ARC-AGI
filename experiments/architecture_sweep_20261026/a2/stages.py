"""A2 stages after `traces` (see run_a2.py). Every stage reads S_train material only, except eval (cohort search)
and score (source labels of S_select / S_train; ARC_eval_dev predictions are scored by a separate process)."""
import collections
import hashlib
import json
import math
import os
import random

from harness import data as HD
from a2 import arcdsl as D
from a2 import bus as B
from a2 import grammars as GR
from a2 import library as LB
from a2 import runlog as RL
from a2.run_a2 import CFG, OUT, STATUS, corpus, correct, per_output, resume_cmd

ARMS = ("lib_free", "compression", "blind", "control", "shuffled", "authentic", "authentic_ranked")
#: primary promotion = MDL greedy for every pool; the trained ranker orders the authentic pool (ablation);
#: the control is matched to the primary authentic library. ARC_eval_dev runs the arms below only.
EVAL_DEV_ARMS = ("lib_free", "compression", "authentic", "control")


def h8(s):
    return int(hashlib.sha256(s.encode()).hexdigest()[:8], 16)


def jt(t):
    return [t[0]] + [jt(c) for c in t[1:]]


def tj(j):
    return (j[0],) + tuple(tj(c) for c in j[1:])


def save(name, obj):
    with RL.P.open_allowed(os.path.join(OUT, name), mode="w") as f:
        json.dump(obj, f)


def load(name):
    with RL.P.open_allowed(os.path.join(OUT, name)) as f:
        return json.load(f)


def train_material():
    trees, split = corpus()
    tr = sorted(t for t in trees if split[t] == "S_train")
    traces = {r["task_id"]: r for r in RL.read_jsonl(os.path.join(OUT, "traces.jsonl"))}
    missing = [t for t in tr if t not in traces]
    if missing:
        raise SystemExit(f"traces incomplete: {len(missing)} tasks missing")
    return trees, tr, traces


def reached_pred(tree, flags):
    d = {}
    for s, f in zip(B.subtrees(tree), flags):
        d[s] = d.get(s, False) or f == "1"
    return lambda s: d.get(s, True)


def height(t):
    return 1 + max((height(c) for c in t[1:]), default=0)


def cone_q(tree, flags):
    ds = LB.depths(tree)
    un = [ds[s] for s, f in zip(B.subtrees(tree), flags) if f == "0"]
    return (max(un) + 1) / height(tree) if un else 0.0


def folds_of(ids):
    man = HD.manifest()
    cl = man.get("cluster_of", {})
    return {t: h8("a2fold:" + cl.get(t, t)) % CFG["folds"] for t in ids}


# ------------------------------------------------------------------ pools
def make_pools(trees, ids, traces, rng):
    ts = [trees[t] for t in ids]
    failed = [t for t in ids if not traces[t]["correct"]]
    comp = LB.candidates_compression(ts, rng)
    auth_items = [(trees[t], reached_pred(trees[t], traces[t]["reached"])) for t in failed]
    auth, n_auth_frag = LB.candidates_from_cones(auth_items, rng)
    perm = list(ids)
    while True:                                          # a derangement: no task keeps its own trace
        rng.shuffle(perm)
        if all(a != b for a, b in zip(ids, perm)):
            break
    shuf_items = []
    for a, b in zip(ids, perm):
        if traces[b]["correct"]:
            continue
        q = cone_q(trees[b], traces[b]["reached"])
        ta = trees[a]
        thr = math.ceil(q * height(ta))
        ds = LB.depths(ta)
        shuf_items.append((ta, lambda s, _d=ds, _t=thr: _d.get(s, 0) >= _t))
    shuf, _ = LB.candidates_from_cones(shuf_items, rng)
    blind = LB.candidates_blind(ts, rng, n_frag=n_auth_frag)
    return {"compression": comp, "authentic": auth, "shuffled": shuf, "blind": blind}, \
        {"failed": len(failed), "shuffled_items": len(shuf_items)}


def stage_pools():
    trees, tr, traces = train_material()
    run = RL.Run("a2", "pools", STATUS, dict(CFG), resume_cmd("pools")).start()
    rng = random.Random(CFG["seed"])
    fo = folds_of(tr)
    doc = {"folds": {t: fo[t] for t in tr}, "pools": {}, "meta": {}}
    for k in list(range(CFG["folds"])) + ["all"]:
        ids = [t for t in tr if k == "all" or fo[t] != k]
        pools, meta = make_pools(trees, ids, traces, rng)
        doc["pools"][str(k)] = {p: sorted([jt(b), a] for b, a in v) for p, v in pools.items()}
        doc["meta"][str(k)] = dict(meta, sizes={p: len(v) for p, v in pools.items()}, n_ids=len(ids))
    save("pools.json", doc)
    run.extra = {"meta": doc["meta"]["all"]}
    run.finish("OK")


# ------------------------------------------------------------------ features and labels
def static_tokens(body, sigs):
    """Pre-order tokens; a parameter is tokenized with the annotation of the slot it fills."""
    out = []

    def walk(t, ann):
        h = t[0]
        out.append("#:" + ann if h[0] == "#" else h)
        if h.startswith("f:"):
            s = sigs.get(h[2:], [])
            for i, c in enumerate(t[1:]):
                walk(c, s[i] if i < len(s) else "Any")
        else:
            for c in t[1:]:
                walk(c, "Any")
    walk(body, "Any")
    return out


def numeric(body, arity, gain, nprog, n_ids):
    sub = B.subtrees(body)
    prims = sum(1 for s in sub if s[0].startswith("f:") or s[0] == "@")
    consts = sum(1 for s in sub if s[0].startswith("c:"))
    fns = sum(1 for s in sub if s[0].startswith("fn:"))
    return [arity, D.size(body), prims, height(body), consts, fns, math.log1p(max(gain, 0)), math.log1p(nprog),
            nprog / max(1, n_ids), (max(gain, 0) / max(1, nprog))]


def stage_labels():
    trees, tr, traces = train_material()
    pools = load("pools.json")
    run = RL.Run("a2", "labels", STATUS, dict(CFG), resume_cmd("labels")).start()
    sigs = D.prim_signatures()
    fo = pools["folds"]
    rows = []
    for k in list(range(CFG["folds"])) + ["all"]:
        ind = [t for t in tr if k == "all" or fo[t] != k]
        ho = [t for t in tr if k != "all" and fo[t] == k]
        idx_ind = LB.node_index([trees[t] for t in ind])
        idx_ho = LB.node_index([trees[t] for t in ho]) if ho else {}
        cands = {}
        for p, lst in pools["pools"][str(k)].items():
            for bj, a in lst:
                key = json.dumps(bj)
                cands.setdefault(key, [tj(bj), a, set()])[2].add(p)
        for key, (body, a, ps) in cands.items():
            g_ind, n_ind = LB.utility(body, a, idx_ind)
            row = {"fold": str(k), "body": jt(body), "arity": a, "pools": sorted(ps),
                   "tokens": static_tokens(body, sigs), "x": numeric(body, a, g_ind + D.size(body), n_ind, len(ind)),
                   "u_ind": g_ind}
            if ho:
                g_ho, n_ho = LB.utility(body, a, idx_ho)
                row["y"] = math.log1p(max(0, g_ho + D.size(body)))      # held-out savings (body cost not charged)
                row["n_ho"] = n_ho
            rows.append(row)
    save("labels.json", {"rows": rows})
    run.extra = {"rows": len(rows), "train_rows": sum(1 for r in rows if "y" in r)}
    run.finish("OK")


# ------------------------------------------------------------------ libraries
def probe_bank(trees, tr, n=24):
    dsl, consts, _, _ = D.load()
    vals = collections.defaultdict(list)
    for tid in tr[:n]:
        g = D.to_grid(HD.task_record(tid, "S_train")["train"][0][0])
        vals["G"].append(g)
        objs = dsl["objects"](g, True, False, True)
        if objs:
            vals["S"].append(objs)
            o = next(iter(objs))
            vals["O"].append(o)
            vals["X"].append(dsl["toindices"](o))
        vals["Z"].append(dsl["palette"](g))
    vals["I"] = [0, 1, 2, 3, 5]
    vals["B"] = [True, False]
    vals["T"] = [(1, 1), (0, 1), (1, 0), (2, 2)]
    vals["F"] = [dsl[n] for n in ("identity", "size", "color", "vmirror", "toindices", "first")]
    return vals


def probes_fn(bank, rng):
    def gen(ptags, arity):
        for _ in range(40):
            args = []
            for k in range(arity):
                opts = [t for t in (ptags[k] if ptags and ptags[k] else ["G"]) if bank.get(t)]
                if not opts:
                    break
                args.append(rng.choice(bank[rng.choice(sorted(opts))]))
            if len(args) == arity:
                yield args
    return gen


def finalize(defs, trees, tr, rng, bank, cost_from=None):
    """Attach runtime parameter tags (S_train instances; static annotation tags when no instance) and names."""
    dsl, consts, _, _ = D.load()
    ev = D.Evaluator(dsl, consts)
    sigs = D.prim_signatures()
    xs_of = [[D.to_grid(HD.task_record(t, "S_train")["train"][0][0])] for t in tr]
    out = []
    for i, (body, a) in enumerate(defs):
        tags = LB.param_tags(body, a, [trees[t] for t in tr], xs_of, ev)
        stat = _static_param_tags(body, a, sigs)
        ptags = [sorted(tags[k] - {"U"}) or sorted(stat[k]) for k in range(a)]
        out.append(["d%02d" % i, a, body, ptags])
    return out


def _static_param_tags(body, a, sigs):
    tags = [set() for _ in range(a)]

    def walk(t):
        if t[0].startswith("f:"):
            s = sigs.get(t[0][2:], [])
            for i, c in enumerate(t[1:]):
                if c[0][0] == "#":
                    tags[int(c[0][1:])] |= set(D.arg_tags(s[i] if i < len(s) else "Any"))
                walk(c)
        else:
            for c in t[1:]:
                walk(c)
    walk(body)
    return [t or {"G"} for t in tags]


def greedy(cands, trees_list, K, order=None, max_checks=600, log=None):
    """Select up to K definitions in `order` (or by marginal MDL gain when order is None), each accepted only if
    it lowers the corpus description length given those already selected (gate 3). `log`: decision rows
    (state hash -> features -> available -> selected -> change -> effects -> cost)."""
    def dec(avail, sel, before, after, checks_):
        if log is not None:
            st = hashlib.sha256(json.dumps([jt(d[2]) for d in lib]).encode()).hexdigest()[:12]
            log.append({"state_hash": st, "features": {"library_size": len(lib), "corpus_dl": before},
                        "available": [json.dumps(jt(c[0])) for c in avail][:40],
                        "selected": json.dumps(jt(sel[0])) if sel else "STOP",
                        "change": "add definition" if sel else "none",
                        "effects": {"dl_before": before, "dl_after": after}, "cost": {"dl_evaluations": checks_}})
    lib = []
    base_dl = LB.corpus_dl(trees_list, [])
    cur = base_dl
    checks = 0
    if order is None:                                    # lazy greedy MDL
        idx = LB.node_index(trees_list)
        scored = sorted(cands, key=lambda c: -LB.utility(c[0], c[1], idx)[0])[:300]
        while len(lib) < K and scored and checks < max_checks:
            best, bestdl = None, cur
            for c in scored[:40]:
                checks += 1
                dl = LB.corpus_dl(trees_list, lib + [("t", c[1], c[0], None)])
                if dl < bestdl:
                    best, bestdl = c, dl
            if best is None:
                dec(scored[:40], None, cur, cur, checks)
                break
            dec(scored[:40], best, cur, bestdl, checks)
            lib.append(("t", best[1], best[0], None))
            scored.remove(best)
            cur = bestdl
    else:
        for c in order:
            if len(lib) >= K or checks >= max_checks:
                break
            checks += 1
            dl = LB.corpus_dl(trees_list, lib + [("t", c[1], c[0], None)])
            dec([c], c if dl < cur else None, cur, min(dl, cur), checks)
            if dl < cur:
                lib.append(("t", c[1], c[0], None))
                cur = dl
    return [(d[2], d[1]) for d in lib], base_dl, cur


def stage_libraries():
    trees, tr, traces = train_material()
    pools = load("pools.json")["pools"]["all"]
    scores = load("ranker_scores.json")["scores"]          # body json -> mean ranker score (3 seeds)
    run = RL.Run("a2", "libraries", STATUS, dict(CFG), resume_cmd("libraries")).start()
    rng = random.Random(CFG["seed"] + 1)
    tl = [trees[t] for t in tr]
    K = CFG["K"]
    dsl, consts, _, _ = D.load()
    bank = probe_bank(trees, tr)
    gen = probes_fn(bank, rng)
    sigs = D.prim_signatures()

    idx_all = LB.node_index(tl)

    def pool(name):
        return [(tj(b), a) for b, a in pools[name]
                if LB.lint(tj(b)) and (LB.MIN_REUSE <= 1 or LB.utility(tj(b), a, idx_all)[1] >= LB.MIN_REUSE)
                and LB.exec_check(tj(b), a, _static_param_tags(tj(b), a, sigs), gen, D.guarded(dsl), consts)]
    out, stats = {}, {}
    p_auth, p_shuf, p_blind = pool("authentic"), pool("shuffled"), pool("blind")
    # success compression = the best failure-free compressor: every failure-free candidate (repeated fragments,
    # anti-unifications, and the blind fragments) under the same MDL objective
    p_comp = sorted(set(pool("compression")) | set(p_blind), key=lambda c: json.dumps(jt(c[0])))
    stats["gated_pool_sizes"] = {"compression": len(p_comp), "authentic": len(p_auth), "shuffled": len(p_shuf),
                                 "blind": len(p_blind)}

    def by_rank(p):
        return sorted(p, key=lambda c: (-scores.get(json.dumps(jt(c[0])), -1e9), D.size(c[0]), json.dumps(jt(c[0]))))
    logs = {a: [] for a in ("compression", "authentic", "shuffled", "blind", "authentic_ranked")}
    sel = {"compression": greedy(p_comp, tl, K, log=logs["compression"]),
           "authentic": greedy(p_auth, tl, K, log=logs["authentic"]),
           "shuffled": greedy(p_shuf, tl, K, log=logs["shuffled"]), "blind": greedy(p_blind, tl, K, log=logs["blind"]),
           "authentic_ranked": greedy(p_auth, tl, K, order=by_rank(p_auth), log=logs["authentic_ranked"])}
    save("promotion_decisions.json", logs)
    for arm, (defs, dl0, dl1) in sel.items():
        out[arm] = finalize(defs, trees, tr, rng, bank)
        stats[arm] = {"n": len(defs), "dl_base": dl0, "dl_lib": dl1 + sum(D.size(b) for b, _ in defs),
                      "dl_programs": dl1}
    # matched valid random control (arity, body size, parameter tags; prior cost copied from the authentic library)
    g_auth = GR.build(tl, [tuple(d) for d in out["authentic"]])
    prims = sorted({h[2:] for t in tl for h in {s[0] for s in B.subtrees(t)} if h.startswith("f:")})
    fnl = sorted({s[0] for t in tl for s in B.subtrees(t) if s[0].startswith("fn:")})
    cn = sorted(consts)
    ctrl, ctrl_cost = [], {}
    for name, a, body, ptags in out["authentic"]:
        for _ in range(30):
            rb = LB.random_body(rng, prims, sigs, fnl, cn, consts, ptags, D.size(body))
            if rb is not None and LB.lint(rb) and LB.exec_check(rb, a, ptags, gen, D.guarded(dsl), consts):
                ctrl.append(["c" + name[1:], a, rb, ptags])
                ctrl_cost["L:c" + name[1:]] = g_auth.costs.get("L:" + name, 4)
                break
    out["control"] = ctrl
    stats["control"] = {"n": len(ctrl), "matched_to": "authentic", "cost_override": ctrl_cost}
    lib_doc = {arm: [[n, a, jt(b), pt] for n, a, b, pt in defs] for arm, defs in out.items()}
    lib_doc["_stats"] = stats
    lib_doc["_control_costs"] = ctrl_cost
    save("libraries.json", lib_doc)
    run.extra = {"stats": {k: (v if not isinstance(v, dict) else {kk: vv for kk, vv in v.items()
                                                                   if kk != "cost_override"})
                           for k, v in stats.items()}}
    run.finish("OK")


# ------------------------------------------------------------------ cohorts, grammars, eval
def cohort_ids(name):
    man = HD.manifest()
    cl = man.get("cluster_of", {})
    if name in ("S_select_A", "S_select_B"):
        ids = HD.split_ids("S_select")
        half = "A" if name.endswith("A") else "B"
        return sorted(t for t in ids if ("A" if h8("a2sel:" + cl.get(t, t)) % 2 == 0 else "B") == half)
    if name == "E_trainU":
        trees, split = corpus()
        ids = [t for t in HD.split_ids("S_train") if t not in trees]
        return sorted(ids, key=lambda t: h8("a2u:" + t))[:40]
    if name == "ARC_eval_dev":
        return list(HD.split_ids("ARC_eval_dev"))
    raise KeyError(name)


def arm_grammar(arm, tl, libs):
    if arm == "lib_free":
        return GR.build(tl)
    defs = [(n, a, tj(b), pt) for n, a, b, pt in libs[arm]]
    over = libs.get("_control_costs") if arm == "control" else None
    return GR.build(tl, defs, cost_override=over)


def stage_eval(cohort, arms=None):
    trees, split = corpus()
    tr = sorted(t for t in trees if split[t] == "S_train")
    tl = [trees[t] for t in tr]
    libs = load("libraries.json")
    ids = cohort_ids(cohort)
    split_name = "ARC_eval_dev" if cohort == "ARC_eval_dev" else ("S_select" if cohort.startswith("S_select")
                                                                  else "S_train")
    path = os.path.join(OUT, f"eval_{cohort}.jsonl")
    done = {(r["arm"], r["task_id"]) for r in RL.read_jsonl(path)}
    lib_hash = hashlib.sha256(json.dumps(libs, sort_keys=True).encode()).hexdigest()[:16]
    run = RL.Run("a2", "eval_" + cohort, STATUS, dict(CFG, cohort=cohort, n=len(ids), library_hash=lib_hash),
                 resume_cmd("eval", cohort)).start()
    arms = tuple(arms.split(",")) if arms else (EVAL_DEV_ARMS if cohort == "ARC_eval_dev" else ARMS)
    grams = {arm: arm_grammar(arm, tl, libs) for arm in arms}
    for tid in ids:
        task = HD.task_record(tid, split_name)
        for arm in arms:
            if (arm, tid) in done:
                continue
            r = B.search(grams[arm], task["train"], task["test_inputs"], CFG["budget"], cpu_cap=CFG["cpu_cap"],
                         max_fn=CFG["max_fn"], want=2)
            used = sorted(LB.uses(r.program, collections.Counter())) if r.program else []
            rec = {"arm": arm, "task_id": tid, "fit": r.solved, "calls": r.calls, "first_fit_calls": r.first_fit_calls,
                   "cpu_s": round(r.cpu_s, 3), "level": r.level, "stop": r.stop, "program": r.as_dict()["program"],
                   "lib_used": used, "preds": r.as_dict()["preds"]}
            RL.append_jsonl(path, rec)
    run.extra = {"records": len(RL.read_jsonl(path))}
    run.finish("OK")


def stage_ranker():
    from a2 import ranker
    ranker.run()


def stage_canary():
    """Three canaries, every arm: a reachable correct case (an S_train task the base search solved), a
    wrong-but-fitting case (base fit the demonstrations but missed the source test output) and a no-change case
    (identity task built from an S_train task's inputs: outputs = inputs)."""
    trees, split = corpus()
    tr = sorted(t for t in trees if split[t] == "S_train")
    tl = [trees[t] for t in tr]
    traces = {r["task_id"]: r for r in RL.read_jsonl(os.path.join(OUT, "traces.jsonl"))}
    libs = load("libraries.json")
    labels = HD.source_labels("S_train")
    reach = sorted(t for t in tr if traces[t]["correct"])[:1]
    amb = sorted(t for t in tr if traces[t]["solved_demo"] and not traces[t]["correct"])[:1]
    cases = [("reachable", t, HD.task_record(t, "S_train"), labels[t]) for t in reach] + \
            [("ambiguous", t, HD.task_record(t, "S_train"), labels[t]) for t in amb]
    src = HD.task_record(tr[-1], "S_train")
    ident = {"task_id": "identity:" + tr[-1], "train": [(x, x) for x, _ in src["train"]],
             "test_inputs": src["test_inputs"]}
    cases.append(("no_change", ident["task_id"], ident, src["test_inputs"]))
    run = RL.Run("a2", "eval_canary", STATUS, dict(CFG, cases=[c[1] for c in cases]), resume_cmd("canary")).start()
    rows = []
    for arm in ARMS:
        g = arm_grammar(arm, tl, libs)
        for kind, tid, task, truths in cases:
            r = B.search(g, task["train"], task["test_inputs"], CFG["budget"], cpu_cap=CFG["cpu_cap"],
                         max_fn=CFG["max_fn"], want=2)
            ok = correct(r.preds, truths)
            rows.append({"arm": arm, "case": kind, "task_id": tid, "fit": r.solved, "correct": ok,
                         "program": D.show(r.program) if r.program else None, "calls": r.calls,
                         "first_fit_calls": r.first_fit_calls})
    save("canary.json", rows)
    run.extra = {"rows": len(rows), "correct": sum(r["correct"] for r in rows)}
    run.finish("OK")
