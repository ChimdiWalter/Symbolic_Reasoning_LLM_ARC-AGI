"""Object-level growth on one benchmark's SOURCE half: construction from the controller's typed holes, gates,
registry.

    python -I run.py grow OUT_DIR BENCH [--limit N] [--shard I/K] [--units id,id,...] [--no-gates]

Units: the benchmark's source tasks on which the growth controller decided INVENT_NEW_OPERATION (its phase 1
records, read-only), in (family, id) order. Every unit starts from G0. Per unit: the typed holes in the
controller's rank order; per hole the object-level constructor (construct.py) gives verified candidates; the
candidates of all holes (holes in rank order, within a hole by agreement group then simplicity, repeats dropped)
that pass leave-one-out go to the gates (gates.py); the unit stops at its first promoted operation.
Registry: promoted operations in unit order without repeats; a final combined regression check (G0 + registry on
U; while a fit is lost or a first prediction changes, the most recently added operation is removed).
Charged CPU: construction (process CPU of the constructor) plus each distinct gate result used (at the CPU of its
first computation). Writes OUT_DIR/<BENCH>/{units.json, registry.json}; the gate cache goes to
logs/cache/<BENCH>_gates.pkl. Resumable (finished units are skipped).
"""
import hashlib
import json
import os
import pickle
import sys
import time

from objgrow import env as E, construct as CS, edits as ED, gates as GT
from ngrow import data as DT, plugin as PL
from a2 import arcdsl as D

SEED = 0


def h(s):
    return hashlib.sha256(s.encode()).hexdigest()


def as_preds(att_list):
    if att_list is None:
        return None
    return [[tuple(tuple(r) for r in g) for g in att] for att in att_list]


def setup(bench):
    recs = E.controller_records(bench)
    src = {t for b, f, t in DT.half("source", (bench,))}
    fam = {t: f for b, f, t in DT.half("source", (bench,))}
    missing = sorted(src - set(recs))
    if missing:
        raise SystemExit(f"controller records missing for {len(missing)} source tasks of {bench}")
    if set(recs) - src:
        raise SystemExit("records include tasks outside the source half")
    all_tasks = DT.tasks(bench)
    tasks = {t: all_tasks[t] for t in src}
    solved = sorted(t for t in src if recs[t]["record"]["status"] == "solved")
    base_preds = {t: as_preds(recs[t]["record"]["base_preds"])[0] for t in solved}
    pool = sorted([t for t in src if recs[t]["record"]["status"] != "solved"], key=lambda i: h("pool:" + i))
    units = sorted([t for t in src if recs[t]["record"]["decision"] == "INVENT_NEW_OPERATION"],
                   key=lambda t: (fam[t], t))
    return {"recs": recs, "fam": fam, "tasks": tasks, "solved": solved, "base_preds": base_preds, "pool": pool,
            "units": units}


def hole_test_inputs(sk, task, fns):
    """The inputs on which a hole's candidates are compared for agreement: the task's test inputs, transformed by
    the hole's inner operation when it has one."""
    qs = list(task["test_inputs"])
    if sk.get("inner"):
        try:
            qs = [fns[sk["inner"]](q) for q in qs]
        except Exception:                                        # noqa: BLE001
            return []
    return [q for q in qs if D.tag(q) == "G"]


def construct_unit(rec, task, fns):
    """All holes of a unit through the constructor: candidates (leave-one-out passing first) and hole records."""
    t0 = time.process_time()
    holes, cands, seen = [], [], set()
    counts = {"segment": 0, "edit": 0, "op": 0}
    for rank, sk in enumerate(rec["sketches"]):
        pairs = [(E.grid(a), E.grid(b)) for a, b in sk["pairs"]]
        got, hrec = CS.hole_candidates(pairs, hole_test_inputs(sk, task, fns))
        for k in counts:
            counts[k] += hrec["counts"][k]
        hrec.update(rank=rank, form=sk["form"], outer=sk.get("outer"), inner=sk.get("inner"), score=sk.get("score"),
                    candidates=[{"sid": c["op"].sid, "expr": c["op"].expr(), "loo": c["loo"], "group": c["group"],
                                 "view": c.get("view"), "proposing": c["proposing"]} for c in got])
        holes.append(hrec)
        for c in got:
            if c["op"].sid not in seen:
                seen.add(c["op"].sid)
                c["hole_rank"], c["hole_form"] = rank, sk["form"]
                cands.append(c)
    return {"holes": holes, "candidates": cands, "counts": counts,
            "construction_cpu_s": round(time.process_time() - t0, 3)}


def run(out_dir, bench, limit=None, shard=None, only=None, gates=True):
    bdir = os.path.join(out_dir, bench)
    os.makedirs(bdir, exist_ok=True)
    W = setup(bench)
    recs, fam, units = W["recs"], W["fam"], W["units"]
    tag = "" if not shard else ".shard" + shard.replace("/", "of")
    g0b = PL.G0Builder()
    plug = GT.ObjPlugin(g0b)
    fns = D.guarded(D.load()[0])
    cache_path = os.path.join(E.STUDY, "logs", "cache", f"{bench}_gates{tag}.pkl")
    # seeded from every cache file of the benchmark (its own shard file first; a gate result is a pure function
    # of (operation, task), so prior files from an earlier run of the same gates are reused, not recomputed)
    cache = load_cache(bench, first=cache_path)
    G = GT.ObjGates(plug, W["tasks"], W["solved"], W["base_preds"], W["pool"], cache)
    out_path = os.path.join(bdir, f"units{tag}.json")
    done = E.load(out_path) if os.path.exists(out_path) else {}

    def save():
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(E.check_write(cache_path + ".tmp"), "wb") as f:
            pickle.dump(G.c, f)
        os.replace(cache_path + ".tmp", cache_path)
        E.dump(out_path, done)

    mine = units
    if shard:
        i, k = (int(x) for x in shard.split("/"))
        mine = [t for n, t in enumerate(units) if n % k == i]
    if only:
        mine = [t for t in mine if t in only]
    if limit:
        mine = mine[:limit]
    for tid in mine:
        if tid in done:
            continue
        G.used = set()
        t0 = time.process_time()
        row = {"task": tid, "family": fam[tid], "seed": SEED, "n_demos": recs[tid]["n_demos"]}
        con = construct_unit(recs[tid]["record"], W["tasks"][tid], fns)
        row.update(holes=con["holes"], counts=con["counts"], construction_cpu_s=con["construction_cpu_s"],
                   n_candidates=len(con["candidates"]), n_candidates_loo=sum(1 for c in con["candidates"] if c["loo"]))
        if gates:
            cands = [c for c in con["candidates"] if c["loo"]]
            res = GT.run_unit(G, tid, cands)
            row.update(res)
            row["used_keys"] = sorted([list(k) for k in G.used], key=str)
            row["charged_gate_cpu_s"] = G.charged(G.used)
        row["process_cpu_s"] = round(time.process_time() - t0, 3)
        done[tid] = row
        save()
        print(json.dumps({"unit": tid, "family": fam[tid], "candidates": row["n_candidates"],
                          "loo": row["n_candidates_loo"], "promoted": row.get("promoted"),
                          "retries": row.get("retries"), "cpu_s": row["process_cpu_s"]}), flush=True)
    save()
    if not shard and gates:
        build_registry(out_dir, bench)


def combined_regression(g0b, ops, tasks, solved, base_preds):
    reg = list(ops)
    rounds = []
    while reg:
        t0 = time.process_time()
        plug = GT.ObjPlugin(g0b, reg)
        g = plug.g0()
        lost, changed = [], []
        for tid in solved:
            t = tasks[tid]
            r = plug.search(g, t["train"], t["test_inputs"], plug.BASE_BUDGET, plug.BASE_CPU, 2)
            if not r["fit"]:
                lost.append(tid)
            elif base_preds.get(tid) is not None and (not r["preds"] or base_preds[tid] not in r["preds"]):
                changed.append(tid)
        rounds.append({"registry": [op.sid for op in reg], "lost_fit": lost, "changed_prediction": changed,
                       "cpu_s": round(time.process_time() - t0, 3)})
        if not lost and not changed:
            break
        reg = reg[:-1]
    return reg, rounds


def load_units(bdir):
    done = {}
    for fn in sorted(os.listdir(bdir)):
        if fn.startswith("units") and fn.endswith(".json"):
            for k, v in E.load(os.path.join(bdir, fn)).items():
                done.setdefault(k, v)
    return done


def load_cache(bench, first=None):
    """Merge every gate cache file of the benchmark (logs/cache/<bench>_gates*.pkl; `first` takes priority)."""
    cache = {"nov": {}, "retry": {}, "reg": {}, "ops": {}}
    cdir = os.path.join(E.STUDY, "logs", "cache")
    paths = []
    if first and os.path.exists(first):
        paths.append(first)
    if os.path.isdir(cdir):
        paths += [os.path.join(cdir, fn) for fn in sorted(os.listdir(cdir))
                  if fn.startswith(f"{bench}_gates") and fn.endswith(".pkl") and os.path.join(cdir, fn) != first]
    for p in paths:
        with open(p, "rb") as f:
            c = pickle.load(f)
        for part in cache:
            for k, v in c.get(part, {}).items():
                cache[part].setdefault(k, v)
    return cache


def build_registry(out_dir, bench):
    bdir = os.path.join(out_dir, bench)
    W = setup(bench)
    units, solved = W["units"], W["solved"]
    done = load_units(bdir)
    cache = load_cache(bench)
    g0b = PL.G0Builder()
    G = GT.ObjGates(GT.ObjPlugin(g0b), W["tasks"], solved, W["base_preds"], W["pool"], cache)
    ran = [t for t in units if t in done and "rows" in done[t]]
    promoted = []
    for tid in ran:
        p = done[tid]["promoted"]
        if p and p not in promoted:
            promoted.append(p)
    keys = set()
    for tid in ran:
        keys |= {tuple(k) for k in done[tid]["used_keys"]}
    ops = [G.st[s] for s in promoted]
    final, rounds = combined_regression(g0b, ops, W["tasks"], solved, W["base_preds"]) if ops else ([], [])
    doc = {"bench": bench, "seed": SEED, "v_max": GT.V_MAX, "novelty_max_cost": GT.NOVELTY_MAX_COST,
           "added_cost": GT.ADDED_COST, "g0_sha256": g0b.sha, "n_units": len(units), "units_run": len(ran),
           "complete": len(ran) == len(units), "n_solved_U": len(solved), "n_pool": len(W["pool"]),
           "promoted_in_unit_order": promoted, "registry": [op.sid for op in final],
           "ops": {op.sid: op.to_json() for op in final}, "combined_regression": rounds,
           "construction_cpu_s": round(sum(done[t]["construction_cpu_s"] for t in ran), 3),
           "gate_cpu_s_distinct": G.charged(keys),
           "combined_regression_cpu_s": round(sum(r["cpu_s"] for r in rounds), 3)}
    E.dump(os.path.join(bdir, "registry.json"), doc)
    print(json.dumps({"bench": bench, "registry": doc["registry"], "promoted": len(promoted)}), flush=True)


def main(out_dir, bench, *rest):
    if rest == ("registry",):
        return build_registry(os.path.abspath(out_dir), bench)
    limit, shard, only, gates = None, None, None, True
    it = iter(rest)
    for a in it:
        if a == "--limit":
            limit = int(next(it))
        elif a == "--shard":
            shard = next(it)
        elif a == "--units":
            only = set(next(it).split(","))
        elif a == "--no-gates":
            gates = False
        else:
            raise SystemExit(f"unknown argument {a}")
    run(os.path.abspath(out_dir), bench, limit, shard, only, gates)


if __name__ == "__main__":
    main(*sys.argv[1:])
