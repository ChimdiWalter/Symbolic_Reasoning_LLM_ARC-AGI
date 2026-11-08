"""Stage B: growth on one benchmark's SOURCE half (construction from failures, promotion, registry).

    python -I run.py grow CONTROLLER_JSONL[,MORE...] OUT_DIR BENCH [ARM ...]

The construction test's algorithm (cgrow/selfext_core.py, unchanged), driven by the natural-task plug-in:
- Units: the benchmark's source tasks on which the controller decided INVENT_NEW_OPERATION, in (family, id) order.
  Every unit starts from G0 (as in the construction test).
- Arms:
    S-hole      the task's own typed holes (its ranked sketches) -> candidates -> gates   (GROWTH, the main arm)
    S-demo      demonstrations only: the identity sketch, whose holes are the demonstrations themselves
    S-shuffled  the holes of a donor failure from another family (DONOR rule below)
    S-enum      blind enumeration: structures in the seed order, no holes, until 60 charged CPU-s per unit
  Structure order: SIGMA's seed-0 order for every arm.
- Gates (one cache per benchmark, shared by the arms; deterministic): novelty (no G0 program within 200,000
  executions on 12 probe grids reproduces the structure at every defined parameter value), retry of the unit's task
  with G0 + the structure at the base budget (at most 3 per unit), regression on U (the benchmark's source tasks G0
  solves at the base budget: a lost fit or a changed first prediction means rolled back), validation on the pool
  (the benchmark's other unsolved source tasks in sha256("pool:"+id) order, at most V_MAX tried: one new fit means
  promoted, none means quarantined). The unit stops at its first promoted structure.
- Registry per arm: promoted structures in unit order, without repeats. The grown grammar G_arm = G0 + registry. A
  final combined regression check runs G_arm on every task of U; while any fit is lost or any first prediction
  changes, the most recently added structure is removed and the check repeats.
- Charged CPU: every gate result carries the process CPU of its first computation; an arm is charged each distinct
  gate result it used once (so the charge does not depend on the order in which arms share the cache).
DONOR rule: the benchmark's INVENT units ordered by sha256("donor:"+id); a unit's donor is the next unit in that
cyclic order whose family differs (Mini-ARC, one pool: the next unit).
Writes OUT_DIR/<BENCH>/{units.json, registry.json, gates.pkl}. Resumable (finished units are skipped).
"""
import hashlib
import json
import os
import pickle
import sys
import time

from ngrow import env as E, data as DT, plugin as PL
from cgrow import selfext_core as C, schema as SG                               # noqa: E402

ARMS = ("S-hole", "S-demo", "S-shuffled", "S-enum")
SEED = 0
V_MAX = 30
C.ENUM_CPU = 60.0 * PL.CPU_SCALE          # blind enumeration's 60 CPU-s per unit, in this machine's CPU-seconds


def h(s):
    return hashlib.sha256(s.encode()).hexdigest()


def as_preds(att_list):
    """JSON predictions (attempts of lists of grids) -> the search's tuple form."""
    if att_list is None:
        return None
    return [[tuple(tuple(r) for r in g) for g in att] for att in att_list]


def load_records(paths, bench):
    recs = {}
    for p in paths.split(","):
        with open(p, encoding="utf-8") as f:
            for x in f:
                if x.strip():
                    r = json.loads(x)
                    if r["bench"] == bench:
                        recs[r["task"]] = r
    return recs


class CappedGates(C.Gates):
    """The shared core's gates with (1) validation capped at V_MAX pool tasks, (2) a record of the distinct gate
    results each arm used (for its charged CPU)."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.used = set()

    def novelty(self, sid):
        self.used.add(("nov", sid))
        return super().novelty(sid)

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
                tot += self.c["nov"][k[1]]["cpu_s"]
            elif k[0] == "retry":
                tot += self.c["retry"][(k[1], k[2])]["cpu_s"]
            else:
                tot += self.c["reg"][k[1]]["cpu_s"]
        return round(tot, 3)


def combined_regression(plug_g0b, registry, tasks, solved, base_preds):
    """G0 + registry on every task of U; drop the most recently added structure until nothing is lost."""
    reg = list(registry)
    rounds = []
    while reg:
        t0 = time.process_time()
        plug = PL.NaturalPlugin(plug_g0b, reg)
        g = plug.g0()
        lost, changed = [], []
        for tid in solved:
            t = tasks[tid]
            r = plug.search(g, t["train"], t["test_inputs"], plug.BASE_BUDGET, plug.BASE_CPU, 2)
            if not r["fit"]:
                lost.append(tid)
            elif base_preds.get(tid) is not None and (not r["preds"] or base_preds[tid] not in r["preds"]):
                changed.append(tid)
        rounds.append({"registry": list(reg), "lost_fit": lost, "changed_prediction": changed,
                       "cpu_s": round(time.process_time() - t0, 3)})
        if not lost and not changed:
            break
        reg = reg[:-1]
    return reg, rounds


def setup(ctrl_paths, bench):
    recs = load_records(ctrl_paths, bench)
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
    dorder = sorted(units, key=lambda t: h("donor:" + t))
    donor = {}
    for i, t in enumerate(dorder):
        for j in range(1, len(dorder)):
            c = dorder[(i + j) % len(dorder)]
            if fam[c] != fam[t] or bench == "mini_arc":
                donor[t] = c
                break
    return {"recs": recs, "fam": fam, "tasks": tasks, "solved": solved, "base_preds": base_preds, "pool": pool,
            "units": units, "donor": donor}


def run(ctrl_paths, out_dir, bench, arms=ARMS, enum_per_family=None, shard=None):
    """Process the units of the given arms. shard 'I/K': only units with index % K == I, into units.shardIofK.json
    and gates.shardIofK.pkl (started from a copy of gates.pkl when that exists); without a shard the registry is
    built at the end."""
    bdir = os.path.join(out_dir, bench)
    os.makedirs(bdir, exist_ok=True)
    W = setup(ctrl_paths, bench)
    recs, fam, units, donor = W["recs"], W["fam"], W["units"], W["donor"]
    tag = "" if not shard else ".shard" + shard.replace("/", "of")
    g0b = PL.G0Builder()
    plug = PL.NaturalPlugin(g0b)
    gates_path = os.path.join(bdir, f"gates{tag}.pkl")
    cache = None
    for p in (gates_path, os.path.join(bdir, "gates.pkl")):
        if os.path.exists(p):
            with open(p, "rb") as f:
                cache = pickle.load(f)
            break
    G = CappedGates(plug, W["tasks"], W["solved"], W["base_preds"], W["pool"], cache)
    G.solved_set = set(W["solved"])
    out_path = os.path.join(bdir, f"units{tag}.json")
    done = E.load(out_path) if os.path.exists(out_path) else {}
    order = SG.seeded_order(SEED)

    def save():
        with open(E.check_write(gates_path + ".tmp"), "wb") as f:
            pickle.dump(G.c, f)
        os.replace(gates_path + ".tmp", gates_path)
        E.dump(out_path, done)

    sample = set(units)
    if enum_per_family:
        sample = set()
        for f in sorted(set(fam[t] for t in units)):
            sample |= set([t for t in units if fam[t] == f][:enum_per_family])
    mine = units
    if shard:
        i, k = (int(x) for x in shard.split("/"))
        mine = [t for n, t in enumerate(units) if n % k == i]
    for arm in arms:
        for tid in mine:
            key = f"{arm}|{tid}"
            if key in done or (arm == "S-enum" and tid not in sample):
                continue
            G.used = set()
            t0 = time.process_time()
            rec = {"arm": arm, "task": tid, "family": fam[tid], "seed": SEED}
            sk = recs[tid]["record"]["sketches"]
            if arm == "S-enum":
                res = C.run_enum_unit(G, tid, order)
            else:
                if arm == "S-demo":
                    sk = [x for x in sk if x["form"] == "?(I)"]
                elif arm == "S-shuffled":
                    sk = recs[donor[tid]]["record"]["sketches"] if tid in donor else []
                    rec["donor"] = donor.get(tid)
                res = C.run_spec_unit(G, tid, C.spec_candidates(plug, order, sk))
            rec.update(res)
            rec["used_keys"] = sorted([list(k) for k in G.used])
            rec["charged_distinct_cpu_s"] = G.charged(G.used)
            rec["process_cpu_s"] = round(time.process_time() - t0, 3)
            done[key] = rec
            save()
            print(json.dumps({"unit": key, "candidates": res.get("n_candidates"), "retries": res["retries"],
                              "promoted": res["promoted"], "cpu_s": res["cpu_s"]}), flush=True)
    save()
    if not shard:
        build_registry(ctrl_paths, out_dir, bench)


def build_registry(ctrl_paths, out_dir, bench):
    """Merge every units*.json and gates*.pkl of the benchmark (first occurrence wins) and write registry.json."""
    bdir = os.path.join(out_dir, bench)
    W = setup(ctrl_paths, bench)
    units, solved = W["units"], W["solved"]
    done, cache = {}, {"nov": {}, "retry": {}, "reg": {}}
    for fn in sorted(os.listdir(bdir)):
        p = os.path.join(bdir, fn)
        if fn.startswith("units") and fn.endswith(".json"):
            for k, v in E.load(p).items():
                done.setdefault(k, v)
        elif fn.startswith("gates") and fn.endswith(".pkl"):
            with open(p, "rb") as f:
                c = pickle.load(f)
            for part in cache:
                for k, v in c[part].items():
                    cache[part].setdefault(k, v)
    g0b = PL.G0Builder()
    G = CappedGates(PL.NaturalPlugin(g0b), W["tasks"], solved, W["base_preds"], W["pool"], cache)
    G.solved_set = set(solved)
    reg_doc = {"bench": bench, "seed": SEED, "v_max": V_MAX, "g0_sha256": g0b.sha, "n_units": len(units),
               "n_solved_U": len(solved), "n_pool": len(W["pool"]), "donors": W["donor"], "arms": {}}
    for arm in ARMS:
        ran = [t for t in units if f"{arm}|{t}" in done]
        if not ran:
            continue
        promoted = []
        for tid in ran:
            p = done[f"{arm}|{tid}"]["promoted"]
            if p and p not in promoted:
                promoted.append(p)
        keys = set()
        for tid in ran:
            keys |= {tuple(k) for k in done[f"{arm}|{tid}"]["used_keys"]}
        final, rounds = combined_regression(g0b, promoted, W["tasks"], solved, W["base_preds"]) if promoted \
            else ([], [])
        reg_doc["arms"][arm] = {"units_run": len(ran), "complete": len(ran) == len(units),
                                "promoted_in_unit_order": promoted, "registry": final, "combined_regression": rounds,
                                "construction_cpu_s": G.charged(keys),
                                "combined_regression_cpu_s": round(sum(r["cpu_s"] for r in rounds), 3)}
    E.dump(os.path.join(bdir, "registry.json"), reg_doc)
    print(json.dumps({"bench": bench, "registries": {a: v["registry"] for a, v in reg_doc["arms"].items()}}),
          flush=True)


def main(ctrl_paths, out_dir, bench, *rest):
    """rest: arm names; --enum-per-family K (phase 1 feasibility sample of blind enumeration); --shard I/K;
    or the single word 'registry' (merge shards and build the registries)."""
    if rest == ("registry",):
        return build_registry(ctrl_paths, os.path.abspath(out_dir), bench)
    arms, k, shard = [], None, None
    it = iter(rest)
    for a in it:
        if a == "--enum-per-family":
            k = int(next(it))
        elif a == "--shard":
            shard = next(it)
        else:
            arms.append(a)
    run(ctrl_paths, os.path.abspath(out_dir), bench, tuple(arms) or ARMS, k, shard)


if __name__ == "__main__":
    main(*sys.argv[1:])
