"""Development on the SOURCE set only (revision 2, before its freeze): constants, the gap check, the learned router,
and the evidence used to write the fixed router's rules.

    python -m fgc.develop table              per-task failure features beside each intervention's outcome
    python -m fgc.develop constants          K_S, K_V, T_STAR, the static order and the static-versus-oracle gap
    python -m fgc.develop learn              trains the learned router into config/ROUTERS.json
    python -m fgc.develop power [N]          optimistic power of the primary from the source set
    python -m fgc.develop viewfill           the held view count expected per view quota, from source-side counts
                                             only, and the primary's power at the chosen quota
                                             (runs/dev/VIEW_FILL_ESTIMATE.json)

Pre-declared formulas:
- K_S (search's cap inside the bank) = the 90th percentile of the search's calls at its correct first fit over the
  source depth tasks; K_V (the view search's cap) = the same over the source view tasks; both rounded up to 250,000;
- T_STAR = the 75th percentile of the oracle arm's spent calls over the source tasks it solves within 20,000,000
  calls, rounded up to 250,000;
- STATIC_ORDER = the permutation of the bank with the most correct source tasks at T_STAR (ties: fewer mean calls,
  then the order construct, view, search);
- the gap check: the best static order's correct count against the oracle's, at every budget of the curve. A
  selection advantage is possible in principle only if the oracle solves more at the binding budget.
- the learned router: one L2-regularised logistic regression per intervention (fgc/arms.py), on the source tasks'
  failure features, predicting that the intervention alone commits a correct answer (search within K_S, view within
  K_V, construction within its own calls), trained once with fixed settings.
"""
import itertools
import json
import math
import os
import sys

from fgc import arms as A
from fgc import contract as K
from fgc.pipeline import measurements, load, dump, correct

STUDY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EV = os.path.join(STUDY, "runs", "source", "evaluator_only", "SOURCE_EVAL.json")
MEAS = os.environ.get("FGC_MEASURE", os.path.join(STUDY, "runs", "source", "measure"))
ROUTERS = os.path.join(STUDY, "config", "ROUTERS.json")
STEP = 250_000
PREF = ("construct", "view", "search")


def up(x):
    return int(math.ceil(x / STEP) * STEP)


def pct(xs, q):
    xs = sorted(xs)
    if not xs:
        return None
    k = (len(xs) - 1) * q
    lo, hi = int(math.floor(k)), int(math.ceil(k))
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def rows():
    ev, ms = load(EV), measurements(MEAS)
    out = []
    for t in sorted(ms):
        e, m = ev[t], ms[t]
        outs = e["test_outputs"]
        r = {"task": t, "family": e["family"], "cause": e["cause"], "f": A.features(m)}
        for iv in ("search", "view", "construct"):
            r[iv + "_correct"] = bool(m[iv]["fit"] and correct(m[iv]["preds"], outs))
            r[iv + "_calls"] = m[iv]["calls"]
            r[iv + "_fit"] = m[iv]["fit"]
        out.append(r)
    return out, ms, ev


def table():
    rs, _, _ = rows()
    for r in rs:
        f = r["f"]
        print(json.dumps({"family": r["family"], "cause": r["cause"], "shape": f["shape"], "same": f["same_size"],
                          "gap": round(f["view_count_gap"], 2), "gain": round(f["view_coverage_gain"], 2),
                          "bestcov": round(f["best_view_coverage"], 2), "closest": round(f["closest_fraction"], 2),
                          "ident": round(f["identity_sketch"], 2), "area": round(f["area_ratio"], 2),
                          "S": [r["search_correct"], r["search_calls"]], "V": [r["view_correct"], r["view_calls"]],
                          "Cn": [r["construct_correct"], r["construct_calls"]]}))


def solved(ms, ev, t, order, budget, caps):
    preds, by, s = K.run_arm(ms[t], order, budget, caps)
    return bool(preds and correct(preds, ev[t]["test_outputs"])), s


def constants():
    rs, ms, ev = rows()
    k_s = up(pct([r["search_calls"] for r in rs if r["cause"] == "search" and r["search_correct"]], 0.9))
    k_v = up(pct([r["view_calls"] for r in rs if r["cause"] == "view" and r["view_correct"]], 0.9))
    caps = {"search": k_s, "view": k_v}
    spent = []
    for r in rs:
        ok, s = solved(ms, ev, r["task"], A.rest(A.CAUSE_FIX[r["cause"]], PREF), 20_000_000, caps)
        if ok:
            spent.append(s)
    t_star = up(pct(spent, 0.75))
    score = {}
    for order in itertools.permutations(A.INTERVENTIONS):
        ok = calls = 0
        for r in rs:
            o, s = solved(ms, ev, r["task"], order, t_star, caps)
            ok += o
            calls += s
        score[order] = (ok, -calls / len(rs), -PREF.index(order[0]))
    static = max(score, key=lambda o: score[o])
    gap = {}
    for mult in A.BUDGET_MULTS:
        B = t_star * mult
        st = sum(solved(ms, ev, r["task"], static, B, caps)[0] for r in rs)
        orc = sum(solved(ms, ev, r["task"], A.rest(A.CAUSE_FIX[r["cause"]], static), B, caps)[0] for r in rs)
        best_any = max(sum(solved(ms, ev, r["task"], o, B, caps)[0] for r in rs)
                       for o in itertools.permutations(A.INTERVENTIONS))
        gap[str(mult)] = {"best_static_at_T_STAR_order": st, "best_static_at_this_budget": best_any, "oracle": orc}
    out = {"K_S": k_s, "K_V": k_v, "T_STAR": t_star, "static_order": list(static),
           "evidence": {"static_order_scores": {"/".join(o): [v[0], round(-v[1])] for o, v in score.items()},
                        "static_versus_oracle": gap, "oracle_spent_calls": sorted(spent), "tasks": len(rs),
                        "by_cause": {c: sum(1 for r in rs if r["cause"] == c) for c in sorted({r["cause"] for r in rs})}}}
    print(json.dumps(out, indent=1))
    return out


def learn(k_s, k_v, l2=1.0):
    rs, ms, _ = rows()
    X = [A.vector(r["f"]) for r in rs]
    ys = {"search": [1 if (r["search_correct"] and r["search_calls"] <= k_s) else 0 for r in rs],
          "view": [1 if (r["view_correct"] and r["view_calls"] <= k_v) else 0 for r in rs],
          "construct": [1 if r["construct_correct"] else 0 for r in rs]}
    model = {iv: A.train_logistic(X, ys[iv], l2=l2) for iv in A.INTERVENTIONS}
    model["features"] = list(A.NUMERIC) + [f"shape={s}" for s in A.SHAPES]
    model["training"] = {"tasks": len(rs), "positives": {iv: sum(ys[iv]) for iv in A.INTERVENTIONS}, "l2": l2,
                         "iterations": 3000, "learning_rate": 0.1,
                         "target": "the intervention alone commits a correct answer (search within K_S, view within K_V)"}
    return model


def power(n_sims=1000, seed=3):
    import random
    from fgc.pipeline import route_fixed
    rs, ms, ev = rows()
    R = load(ROUTERS)
    caps = {"search": R["K_S"], "view": R["K_V"]}
    out = {}
    for r in rs:
        f = r["f"]
        pf = solved(ms, ev, r["task"], route_fixed(f, R["fixed"]), R["T_STAR"], caps)[0]
        pc = solved(ms, ev, r["task"], tuple(R["static_order"]), R["T_STAR"], caps)[0]
        out[r["task"]] = (pf, pc, r["family"], r["cause"])
    fam = {}
    for t, (f, c, fa, ca) in out.items():
        fam.setdefault((ca, fa), []).append((f, c))
    by_cause = {}
    for (ca, fa), v in fam.items():
        by_cause.setdefault(ca, []).append(v)
    plan = {"operation": 6, "search": 3, "view": 9}                   # held families per cause
    rng = random.Random(seed)
    wins = 0
    per = {"operation": 6, "search": 8, "view": 2}
    for _ in range(n_sims):
        rows_ = []
        k = 0
        for ca, nf in plan.items():
            for _ in range(nf):
                fl = rng.choice(by_cause[ca])
                rows_ += [{"family": str(k), "F": f, "C": c} for (f, c) in [rng.choice(fl) for _ in range(per[ca])]]
                k += 1
        cst = A.contrast(rows_, "F", "C")
        wins += cst["mcnemar_p"] < 0.05 and bool(cst["family_ci95"]) and cst["family_ci95"][0] > 0
    src = A.contrast([{"family": v[2], "F": v[0], "C": v[1]} for v in out.values()], "F", "C")
    print(json.dumps({"source_F_vs_C": src, "optimistic_power": round(wins / n_sims, 3), "sims": n_sims}))


def viewfill(n_sims=1000, seed=3, mc=20000, quotas=(2, 3, 4, 5, 6), target=18):
    """The held view count expected per view quota, from source-side counts only, and the primary's power at the
    chosen quota (an amendment before the re-freeze: no held task is generated, no held operation is applied, and the
    held salt does not exist yet).

    - Source side. In the source build every view slot scanned its world's whole share (fewer sources than
      view_max_tries), so a slot of operation X under view v filled exactly when an unused eligible source passed X
      under v. Eligible depends on the grids only: at least three inputs, a colour absent from every input, every input
      within the size cap. Each eligible source is taken to pass X under v with a probability q_X, fitted by maximum
      likelihood to the source build's outcome per world, X and v (k slots, m filled: m passing sources if m < k, at
      least k otherwise), with the share's eligible count at the source cap of 16.
    - Remaining pool. The eligible sources of each world's held share (the held exclusions; the held cap of 20).
    - Held build, view tasks first. n slots per held operation per world, each with a view drawn uniformly; the three
      held operations take the three source rates in a random order; a view with c slots and P passing sources fills
      min(c, P); sharing of sources between operations is ignored. Scenarios: every eligible source passes at the
      fitted rate ("main"); sources with a side above 16 pass at half the rate ("half"); only sources of at most
      16 x 16 pass ("small_only").
    - Choice rule. The smallest quota whose expected count is at least `target` in both the main and the half
      scenario.
    - Power. The resampling of `power` (seed 3), with each held view family sized by one simulated held build at the
      chosen quota; missing-operation and depth families at their full quotas, as in `power`.
    """
    import bisect
    import hashlib
    import random
    from fgc import common as C
    from fgc import generate as G
    from fgc.pipeline import route_fixed
    from cas import generate as GEN
    from cgrow import tasks as T
    cfg = C.config()
    cap_src, cap_held = cfg["size_caps_new_tasks"]["source_view"], cfg["size_caps_new_tasks"]["held_all_causes"]
    pool = GEN.pool_ids({"pools_file": cfg["pools_file"]}, "main")
    grid = {}
    for s in pool:
        xs = T.inputs_of(*s)
        grid[s[0]] = (len(xs), max(max(len(g), len(g[0])) for g in xs), G.absent_colour(xs) is not None)

    def eligible(ids, cap):
        return sum(1 for i in ids if grid[i][0] >= 3 and grid[i][1] <= cap and grid[i][2])

    ev = load(EV)
    src_used = G.used_sources(include_r1_test=False)
    held_used = G.used_sources(include_r1_test=True) | {t["source"] for t in ev.values()}
    share = {}
    for k, w in enumerate(C.WORLDS):
        s_ids = [s[0] for s in pool if s[0] not in src_used and G.in_part(s, (k, len(C.WORLDS)))]
        h_ids = [s[0] for s in pool if s[0] not in held_used and G.in_part(s, (k, len(C.WORLDS)))]
        share[w] = {"source_share": len(s_ids), "source_eligible": eligible(s_ids, cap_src),
                    "held_share": len(h_ids), "held_eligible": eligible(h_ids, cap_held),
                    "held_eligible_at_most_16": eligible(h_ids, cap_src)}
    fills = {}
    for e in ev.values():
        if e["cause"] == "view":
            w, x = e["family"].split(":view-")
            fills[(w, x, e["view"])] = fills.get((w, x, e["view"]), 0) + 1
    groups = {}
    for w in C.WORLDS:
        salt = cfg["source_salt"] + "-" + w
        for x in cfg["view_source_ops"]:
            for slot in range(cfg["n_view_source_per_op"]):
                v = sorted(C.VIEWS, key=lambda v_: hashlib.sha256(
                    f"{salt}|srcview:{x}:{slot}:{v_}".encode()).hexdigest())[0]
                groups.setdefault((w, x, v), [0, 0])[0] += 1
    for key, g_ in groups.items():
        g_[1] = fills.get(key, 0)
    if sum(g_[1] for g_ in groups.values()) != sum(fills.values()):
        raise SystemExit("a source view task does not sit in a slot of its view")

    def pmf(m, n, q):
        return math.comb(n, m) * q ** m * (1 - q) ** (n - m)

    def loglik(x, q):
        tot = 0.0
        for (w, x_, v), (k, m) in groups.items():
            if x_ == x:
                n = share[w]["source_eligible"]
                p = pmf(m, n, q) if m < k else 1 - sum(pmf(j, n, q) for j in range(k))
                tot += math.log(max(p, 1e-300))
        return tot

    rate = {x: max((i / 10000 for i in range(1, 3001)), key=lambda q: loglik(x, q)) for x in cfg["view_source_ops"]}
    samplers = {}

    def binom(n, q, rng):
        if (n, q) not in samplers:
            acc, cdf = 0.0, []
            for j in range(n + 1):
                acc += pmf(j, n, q)
                cdf.append(acc)
            samplers[(n, q)] = cdf
        return min(bisect.bisect_left(samplers[(n, q)], rng.random()), n)

    scen = {"main": {w: [(share[w]["held_eligible"], 1.0)] for w in C.WORLDS},
            "half": {w: [(share[w]["held_eligible_at_most_16"], 1.0),
                         (share[w]["held_eligible"] - share[w]["held_eligible_at_most_16"], 0.5)] for w in C.WORLDS},
            "small_only": {w: [(share[w]["held_eligible_at_most_16"], 1.0)] for w in C.WORLDS},
            "source_build_check": {w: [(share[w]["source_eligible"], 1.0)] for w in C.WORLDS}}
    rates = [rate[x] for x in cfg["view_source_ops"]]

    def build(sc, n, rng):
        """One simulated held build: the view task count of each held view family (world, operation)."""
        out = []
        for w in C.WORLDS:
            perm = rates[:]
            rng.shuffle(perm)
            for q in perm:
                cnt = [0] * len(C.VIEWS)
                for _ in range(n):
                    cnt[rng.randrange(len(C.VIEWS))] += 1
                out.append(sum(min(c, sum(binom(N, q * m, rng) for N, m in scen[sc][w] if N > 0)) for c in cnt if c))
        return out

    def summary(sc, n):
        rng = random.Random(seed)
        tot = sorted(sum(build(sc, n, rng)) for _ in range(mc))
        return {"expected": round(sum(tot) / mc, 2), "p10": tot[mc // 10], "median": tot[mc // 2],
                "p_at_least_18": round(sum(t >= 18 for t in tot) / mc, 3),
                "p_at_least_9": round(sum(t >= 9 for t in tot) / mc, 3)}

    check = summary("source_build_check", cfg["n_view_source_per_op"])
    table = {sc: {str(n): summary(sc, n) for n in quotas} for sc in ("main", "half", "small_only")}
    chosen = next((n for n in quotas if table["main"][str(n)]["expected"] >= target
                   and table["half"][str(n)]["expected"] >= target), None)
    rs, ms, ev2 = rows()
    R = load(ROUTERS)
    caps = {"search": R["K_S"], "view": R["K_V"]}
    fam = {}
    for r in rs:
        pf = solved(ms, ev2, r["task"], route_fixed(r["f"], R["fixed"]), R["T_STAR"], caps)[0]
        pc = solved(ms, ev2, r["task"], tuple(R["static_order"]), R["T_STAR"], caps)[0]
        fam.setdefault(r["cause"], {}).setdefault(r["family"], []).append((pf, pc))
    by_cause = {c: list(v.values()) for c, v in fam.items()}

    def power_at(sc, n):
        rng = random.Random(seed)
        wins = 0
        for _ in range(n_sims):
            rows_, k = [], 0
            for ca, sizes in (("operation", [6] * 6), ("search", [8] * 3), ("view", build(sc, n, rng))):
                for m in sizes:
                    if m:
                        fl = rng.choice(by_cause[ca])
                        rows_ += [{"family": str(k), "F": f, "C": c} for (f, c) in [rng.choice(fl) for _ in range(m)]]
                    k += 1
            cst = A.contrast(rows_, "F", "C")
            wins += cst["mcnemar_p"] < 0.05 and bool(cst["family_ci95"]) and cst["family_ci95"][0] > 0
        return round(wins / n_sims, 3)

    power_ = {sc: power_at(sc, chosen) for sc in ("main", "half", "small_only")} if chosen else None
    out = {"method": viewfill.__doc__.strip(), "caps": {"source": cap_src, "held": cap_held}, "shares": share,
           "source_slots": {f"{w}:{x}:{v}": {"slots": k, "filled": m} for (w, x, v), (k, m) in sorted(groups.items())},
           "fitted_rate": rate, "source_build_check": {"observed": sum(fills.values()), "simulated": check},
           "held_view_count_by_quota": table, "target": target, "chosen_quota_per_operation_per_world": chosen,
           "power_at_chosen_quota": power_, "power_sims": n_sims, "monte_carlo": mc, "seed": seed}
    dump(os.path.join(STUDY, "runs", "dev", "VIEW_FILL_ESTIMATE.json"), out)
    print(json.dumps({"fitted_rate": rate, "check": check, "chosen": chosen, "power": power_,
                      "expected_at_chosen": {sc: table[sc][str(chosen)] for sc in table} if chosen else None}))


if __name__ == "__main__":
    if sys.argv[1] == "table":
        table()
    elif sys.argv[1] == "constants":
        constants()
    elif sys.argv[1] == "learn":
        R = load(ROUTERS)
        R["learned"] = learn(R["K_S"], R["K_V"])
        dump(ROUTERS, R)
        print(json.dumps(R["learned"]["training"]))
    elif sys.argv[1] == "power":
        power(int(sys.argv[2]) if len(sys.argv) > 2 else 1000)
    elif sys.argv[1] == "viewfill":
        viewfill()
