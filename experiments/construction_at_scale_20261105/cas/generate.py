"""Task generator of the construction test at scale (EVALUATOR SIDE; phase 2 runs it once, before any arm).

    python -m cas.generate build      (phase 2, after the GO gate) every world, in config order, from the main pool,
                                      into runs/generated/<world>/
    (the pilot uses the same Builder through cas/pilot.py, on the pilot pool only)

It is S1's generator (experiments/capability_growth_20261027/cgrow/tasks.py, read-only) with the removed set, the
parameters and the source pool taken from the study configuration instead of module constants. Unchanged from S1:
the three templates T1 X(I[, p]), T2 X(A(I)[, p]), T3 B(X(I[, p])), with A and B among G0's unary grid operations of
S1's list; real ARC training INPUT grids only (their outputs are never used); the five filters (the program runs
on every input; X changes its argument on at least two thirds of the inputs; no demonstration output equals its
input and the outputs are not all equal; G0 + the reference fits the demonstrations and predicts the query at the
base budget; G0 finds NO fit at the base budget); inputs at most 12 x 12 and outputs at most 16 x 16; at most 60
candidates per template slot; composite templates not shared between partitions; no source used twice; decoys D
(G0 programs the base budget misses and 4x finds) and previously solved tasks U (derived and real), re-verified
under each world's G0. Order: sha256(salt + key).

Changes, each needed for more families:
1. Worlds. Each world has its own G0 = A2 grammar minus that world's removed set (as S1), its own tasks, U and D.
   A and B range over S1's unary list (11 operations) plus compress and trim, minus the world's removed operations
   (in S1's world this is exactly S1's list).
2. Colour parameters. For switch (exchange two colours), p = the two most frequent colours over the source's input
   grids (ties to the smaller colour), written with arc-dsl's colour constants; S1's integer parameters (2, 3) keep
   their constants.
3. Unfilled slots. A slot with no qualifying candidate after its tries is recorded as unfilled; S1 raised an error.
4. Pools. Sources come only from the configured pool (ARC training ids, no evaluation task); each world has its own
   used-set, so no source serves two tasks of one world; a source that serves a motivating task of one world serves
   no task of another world, of any partition (global exclusion, so the primary contrast has no cross-world source
   link): every world's real U sources are excluded while motivating tasks are built, and motivating sources are
   excluded from every later task of the other worlds; the other partitions (V, E, D, U) of different worlds may
   share a source. Order: real U tasks reserved per world; then the motivating tasks of every world, worlds in the
   configured m_build_order (the most size-constrained first) and families in the configured order; then V, E, D
   and derived U per world.
5. Opaque ids include the world name.
Outputs per world (OUT_ROOT/<world>/): partitions/TASKS_SYSTEM.json, evaluator_only/TASKS_EVAL.json,
evaluator_only/REMOVED.json, partitions/PARTITIONS_MANIFEST.json, in S1's formats.
"""
import hashlib
import json
import os
import sys
import time

from cas import env as E                                                       # noqa: F401  (paths first)
from cgrow import lang0 as L0, search as S, tasks as T                         # noqa: E402
from a2 import arcdsl as D                                                      # noqa: E402
from harness import data as HD                                                  # noqa: E402

CANDIDATE_UNARY = T.UNARY + ("compress", "trim")    # S1's 11 composite operations and its two parameter-free removed ones
S1_DIHEDRAL = T.DIHEDRAL
CONST = {0: "ZERO", 1: "ONE", 2: "TWO", 3: "THREE", 4: "FOUR", 5: "FIVE", 6: "SIX", 7: "SEVEN", 8: "EIGHT", 9: "NINE"}
SOURCE_COLOURS = "source_colours"


def x_tree(x, arg, p):
    return T.app(x, arg, *[("c:" + CONST[v],) for v in p])


def template(kind, x, p, op=None):
    I = ("I",)
    if kind == "T1":
        return x_tree(x, I, p), I
    if kind == "T2":
        inner = T.app(op, I)
        return x_tree(x, inner, p), inner
    if kind == "T3":
        return T.app(op, x_tree(x, I, p)), I
    raise ValueError(kind)


def source_colours(xs):
    cnt = [0] * 10
    for g in xs:
        for r in g:
            for v in r:
                cnt[v] += 1
    top = sorted(range(10), key=lambda c: (-cnt[c], c))[:2]
    if cnt[top[1]] == 0:
        return None
    return tuple(sorted(top))


class Builder:
    def __init__(self, world, wcfg, cfg, pool_ids, used, reserved, global_m=None):
        self.world, self.w, self.cfg = world, wcfg, cfg
        self.global_m = set() if global_m is None else global_m   # sources of any world's motivating tasks
        self.m_exclude = set()                    # while building motivating tasks: every world's reserved real U
        self.used_tmpl = {}
        self.salt = wcfg["salt"]
        self.removed = tuple(wcfg["removed"])
        self.unary = tuple(u for u in CANDIDATE_UNARY if u not in self.removed)
        self.dihedral = tuple(u for u in S1_DIHEDRAL if u not in self.removed)
        dsl, consts, _, _ = D.load()
        self.ev = D.Evaluator(D.guarded(dsl), consts)
        self.g0 = L0.build_g0(self.removed)
        self.gref = {}
        for x in wcfg["families"]:
            g = L0.build_g0(self.removed)
            L0.add_production(g, "f:" + x, L0.reference_fn(x), self.n_params(x))
            self.gref[x] = g
        self.used, self.reserved = used, reserved
        self.pool = pool_ids
        self.srcs = sorted(pool_ids, key=lambda s: self.h("src:" + s[0]))
        self.log = {"candidates": 0, "filtered": {}, "searches": 0, "cpu_s": 0.0, "unfilled": [],
                    "by_slot": {}}

    def h(self, s):
        return hashlib.sha256((self.salt + "|" + s).encode()).hexdigest()

    def n_params(self, x):
        p = self.w["params"][x]
        return 2 if p == SOURCE_COLOURS else len(p[0])

    def plist(self, x, part, slot, xs=None):
        p = self.w["params"][x]
        if p == SOURCE_COLOURS:
            return None
        return sorted([tuple(v) for v in p], key=lambda v: self.h(f"p:{x}:{part}:{slot}:{v}"))

    def _bump(self, why, key=None):
        self.log["filtered"][why] = self.log["filtered"].get(why, 0) + 1
        if key is not None:
            d = self.log["by_slot"].setdefault(key, {})
            d[why] = d.get(why, 0) + 1

    def outputs(self, tree, xs):
        try:
            outs = [self.ev.run(tree, x) for x in xs]
        except Exception:                                                       # noqa: BLE001
            return None
        if not all(D.valid(o) and D.tag(o) == "G" and len(o) >= 1 and len(o[0]) >= 1 for o in outs):
            return None
        return outs

    def search(self, g, train, q, budget=S.BASE_BUDGET):
        self.log["searches"] += 1
        r = S.run(g, train, [q], budget=budget, cpu_cap=S.BASE_CPU * budget / S.BASE_BUDGET)
        self.log["cpu_s"] += r["cpu_s"]
        return r

    def family_task(self, x, kind, p, op, src, key=None):
        """A qualifying task dict or None (with the reason counted). p None: colours from the source (switch)."""
        self.log["candidates"] += 1
        xs = T.inputs_of(*src)
        if len(xs) < 3:
            self._bump("few_inputs", key)
            return None
        if p is None:
            p = source_colours(xs)
            if p is None:
                self._bump("few_colours", key)
                return None
        tree, arg = template(kind, x, p, op)
        outs = self.outputs(tree, xs)
        if outs is None:
            self._bump("does_not_run", key)
            return None
        if not T.small(xs, outs):
            self._bump("too_large", key)
            return None
        args = self.outputs(arg, xs) if arg != ("I",) else xs
        xa = self.outputs(x_tree(x, ("I",), p), args) if args is not None else None
        if xa is None or sum(a != b for a, b in zip(args, xa)) * 3 < 2 * len(xs):
            self._bump("x_degenerate", key)
            return None
        demos = list(zip(xs[:-1], outs[:-1]))
        if any(a == b for a, b in demos) or len(set(outs[:-1])) == 1:
            self._bump("trivial_outputs", key)
            return None
        ref = self.search(self.gref[x], demos, xs[-1])
        if not (ref["fit"] and S.correct(ref, [outs[-1]])):
            self._bump("reference_misses", key)
            return None
        base = self.search(self.g0, demos, xs[-1])
        if base["fit"]:
            self._bump("g0_fits", key)
            return None
        self._bump("kept", key)
        return {"world": self.world, "family": x, "template": kind, "params": list(p), "op": op,
                "program": D.show(tree), "source": src[0], "source_split": src[1], "train": demos,
                "test_inputs": [xs[-1]], "test_outputs": [outs[-1]], "ref_program": ref["program"],
                "g0_level": base["level_complete"], "g0_stop": base["stop"],
                "g0_closure_capped": base["closure_capped"]}

    def next_source(self, key):
        for s in sorted(self.srcs, key=lambda s: self.h(key + ":" + s[0])):
            if s[0] not in self.used and s[0] not in self.reserved and s[0] not in self.global_m and \
                    s[0] not in self.m_exclude:
                yield s

    def build_family(self, x, quota, part_names=("M", "V", "E")):
        comps = [("T2", a) for a in self.unary] + [("T3", b) for b in self.unary]
        comps.sort(key=lambda c: self.h(f"tmpl:{x}:{c[0]}:{c[1]}"))
        used_tmpl = self.used_tmpl.setdefault(x, set())      # composite templates not shared between partitions
        parts = {}
        max_tries = self.cfg["max_tries"]
        for part in part_names:
            parts[part] = []
            for slot, kind in enumerate(quota[part]):
                got = None
                cands = [("T1", None)] if kind == "T1" else [c for c in comps if c[0] == kind and c not in used_tmpl]
                for c in cands:
                    plist = self.plist(x, part, slot) or [None]
                    tries = 0                                   # at most max_tries candidates per template, in all
                    for p in plist:
                        if tries >= max_tries:
                            break
                        for src in self.next_source(f"{x}:{part}:{slot}:{c}:{p}"):
                            if tries >= max_tries:
                                break
                            tries += 1
                            t = self.family_task(x, c[0], p, c[1], src, key=f"{x}:{c[0]}")
                            if t is not None:
                                got = t
                                break
                        if got:
                            break
                    if got:
                        if c[0] != "T1":
                            used_tmpl.add(c)
                        break
                if got is None:
                    self.log["unfilled"].append({"family": x, "partition": part, "slot": slot, "kind": kind})
                    continue
                self.used.add(got["source"])
                got["partition"] = part
                parts[part].append(got)
                print(json.dumps({"world": self.world, "family": x, "part": part, "program": got["program"],
                                  "source": got["source"]}), flush=True)
        return parts

    def g0_task(self, tree, src, want_base):
        xs = T.inputs_of(*src)
        if len(xs) < 3:
            return None
        outs = self.outputs(tree, xs)
        if outs is None or not T.small(xs, outs):
            return None
        demos = list(zip(xs[:-1], outs[:-1]))
        if any(a == b for a, b in demos) or len(set(outs[:-1])) == 1:
            return None
        base = self.search(self.g0, demos, xs[-1])
        ok = base["fit"] and S.correct(base, [outs[-1]])
        if want_base:
            if not ok:
                return None
        else:
            if base["fit"]:
                return None
            deep = self.search(self.g0, demos, xs[-1], budget=S.BASE_BUDGET * T.PROBE_FACTOR)
            if not (deep["fit"] and S.correct(deep, [outs[-1]])):
                return None
        return {"world": self.world, "family": None, "program": D.show(tree), "source": src[0],
                "source_split": src[1], "train": demos, "test_inputs": [xs[-1]], "test_outputs": [outs[-1]],
                "g0_program": base["program"]}

    def build_u_derived(self, n):
        I = ("I",)
        tmpls = [T.app(b, I) for b in self.unary] + [T.app(c, I, T.app(b, I)) for c in ("hconcat", "vconcat")
                                                     for b in self.dihedral]
        tmpls.sort(key=lambda t: self.h("u:" + D.show(t)))
        out = []
        for t in tmpls:
            if len(out) >= n:
                break
            for i, src in enumerate(self.next_source("u:" + D.show(t))):
                if i >= 6:
                    break
                r = self.g0_task(t, src, want_base=True)
                if r:
                    self.used.add(src[0])
                    r["partition"] = "U"
                    out.append(r)
                    break
        return out

    def build_d(self, n):
        I = ("I",)
        tmpls = [T.app(c, T.app(b1, I), T.app(b2, I)) for c in ("hconcat", "vconcat") for b1 in self.dihedral
                 for b2 in self.dihedral if b1 < b2]
        tmpls += [T.app(a, T.app(b, T.app(c, I))) for a in ("tophalf", "lefthalf", "bottomhalf", "righthalf")
                  for b in self.dihedral for c in ("tophalf", "lefthalf", "righthalf", "bottomhalf") if a != c]
        tmpls.sort(key=lambda t: self.h("d:" + D.show(t)))
        out = []
        for t in tmpls:
            if len(out) >= n:
                break
            for i, src in enumerate(self.next_source("d:" + D.show(t))):
                if i >= 3:
                    break
                r = self.g0_task(t, src, want_base=False)
                if r:
                    self.used.add(src[0])
                    r["partition"] = "D"
                    out.append(r)
                    print(json.dumps({"world": self.world, "part": "D", "program": r["program"]}), flush=True)
                    break
        return out

    def build_u_real(self, n, solved):
        labels = HD.source_labels("S_train")
        pool = {s[0] for s in self.pool if s[1] == "S_train"}          # A2's traces and the labels are S_train's
        out = []
        for tid in sorted((t for t in set(solved) if t in pool), key=lambda t: self.h("ureal:" + t)):
            if len(out) >= n:
                break
            if tid in self.used:
                continue
            rec = HD.task_record(tid, "S_train")
            train = [(D.to_grid(a), D.to_grid(b)) for a, b in rec["train"]]
            qs = [D.to_grid(q) for q in rec["test_inputs"]]
            ys = [D.to_grid(y) for y in labels[tid]]
            r = S.run(self.g0, train, qs)
            self.log["searches"] += 1
            self.log["cpu_s"] += r["cpu_s"]
            if r["fit"] and S.correct(r, ys):
                self.reserved.add(tid)
                out.append({"world": self.world, "family": None, "program": None, "source": tid,
                            "source_split": "S_train", "train": train, "test_inputs": qs, "test_outputs": ys,
                            "g0_program": r["program"], "partition": "U", "real": True})
        return out


def a2_solved():
    with open(os.path.join(E.SWEEP, "a2", "out", "traces.jsonl"), encoding="utf-8") as f:
        return [json.loads(x)["task_id"] for x in f if x.strip() and json.loads(x).get("correct")]


def opaque(t):
    key = json.dumps([t["world"], t["source"], t.get("program"), t["partition"]])
    return "t" + hashlib.sha256(key.encode()).hexdigest()[:8]


def pool_ids(cfg, which):
    pools = E.load(os.path.join(E.STUDY, cfg["pools_file"]))
    split_of = pools["split_of"]
    return [(t, split_of[t]) for t in pools[which]]


def js(g):
    return [list(r) for r in g]


def write_world(out_root, world, wcfg, tasks, log, cfg):
    wd = os.path.join(out_root, world)
    for t in tasks:
        t["id"] = opaque(t)
    assert len({t["id"] for t in tasks}) == len(tasks)
    system = {t["id"]: {"train": [[js(a), js(o)] for a, o in t["train"]], "test_inputs": [js(q) for q in t["test_inputs"]]}
              for t in tasks if t["partition"] != "E"}
    ev = {t["id"]: {k: v for k, v in t.items() if k not in ("train", "test_inputs", "test_outputs")}
          | {"train": [[js(a), js(o)] for a, o in t["train"]], "test_inputs": [js(q) for q in t["test_inputs"]],
             "test_outputs": [js(y) for y in t["test_outputs"]]} for t in tasks}
    sp = os.path.join(wd, "partitions", "TASKS_SYSTEM.json")
    ep = os.path.join(wd, "evaluator_only", "TASKS_EVAL.json")
    rp = os.path.join(wd, "evaluator_only", "REMOVED.json")
    with E.open_write(sp) as f:
        json.dump(system, f, sort_keys=True)
    with E.open_write(ep) as f:
        json.dump(ev, f, sort_keys=True, indent=0)
    with E.open_write(rp) as f:
        json.dump({"removed": list(wcfg["removed"]), "families": list(wcfg["families"]), "params": wcfg["params"],
                   "new_cost": L0.NEW_COST}, f, indent=1)
    counts = {}
    for t in tasks:
        k = (t["family"] or "-") + ":" + t["partition"]
        counts[k] = counts.get(k, 0) + 1
    man = {"built_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "world": world, "salt": wcfg["salt"],
           "tasks_system_sha256": E.sha256(sp), "tasks_eval_sha256": E.sha256(ep), "removed_sha256": E.sha256(rp),
           "counts": counts, "system_ids": sorted(system), "construction": log | {"cpu_s": round(log["cpu_s"], 1)}}
    E.dump(os.path.join(wd, "partitions", "PARTITIONS_MANIFEST.json"), man)
    return man


def build(config_path, out_root, which="main"):
    t0 = time.process_time()
    cfg = E.load(config_path)
    pool = pool_ids(cfg, which)
    solved = a2_solved()
    out = {}
    worlds = list(cfg["world_order"])
    global_m = set()                             # a source that serves a motivating task of one world serves no
    builders, tasks = {}, {}                     # task of another world (the primary has no cross-world link)
    for world in worlds:
        wcfg = cfg["worlds"][world]
        builders[world] = Builder(world, wcfg, cfg, pool, set(), set(), global_m)   # one used-set per world
        tasks[world] = builders[world].build_u_real(cfg["n_u_real"], solved)       # reserved before the families
    reserved_all = set().union(*(b.reserved for b in builders.values()))           # every world's real U sources
    for world in cfg.get("m_build_order", worlds):                                  # motivating tasks first
        b = builders[world]
        b.m_exclude = reserved_all                # no motivating task uses any world's real U source (rule 6)
        for x in cfg["worlds"][world]["families"]:
            parts = b.build_family(x, cfg["quota"], part_names=("M",))
            tasks[world] += parts["M"]
            global_m.update(t["source"] for t in parts["M"])
        b.m_exclude = set()
    for world in worlds:                                                            # then the other partitions
        b, wcfg = builders[world], cfg["worlds"][world]
        for x in wcfg["families"]:
            parts = b.build_family(x, cfg["quota"], part_names=("V", "E"))
            tasks[world] += parts["V"] + parts["E"]
        tasks[world] += b.build_d(cfg["n_d"])
        tasks[world] += b.build_u_derived(cfg["n_u_derived"])
        man = write_world(out_root, world, wcfg, tasks[world], b.log, cfg)
        out[world] = {"counts": man["counts"], "unfilled": b.log["unfilled"], "cpu_s": round(b.log["cpu_s"], 1)}
        print(json.dumps({"world": world, "counts": man["counts"], "unfilled": b.log["unfilled"]}), flush=True)
    uses = {}
    for world in worlds:
        for t in tasks[world]:
            uses.setdefault(t["source"], set()).add((world, t["partition"]))
    for src, u in uses.items():                  # rule 6 in full: a motivating source serves no task of another world
        mw = {w for w, part in u if part == "M"}
        assert not (mw and len({w for w, _ in u}) > 1), f"rule 6 broken by source {src}: {sorted(u)}"
    out["motivating_sources_disjoint_across_worlds"] = True
    out["process_cpu_s"] = round(time.process_time() - t0, 1)
    out["pool"] = which
    E.dump(os.path.join(out_root, "BUILD_SUMMARY.json"), out)


if __name__ == "__main__":
    if sys.argv[1] == "build":                        # phase 2 only: the GO gate first (one use)
        from cas import gate
        if not gate.check("generate"):
            raise SystemExit(1)
        build(os.path.join(E.STUDY, "config", "STUDY_CONFIG.json"), os.path.join(E.STUDY, "runs", "generated"))
    elif sys.argv[1] == "dry_run_pilot":              # phase 1 check of the build path, pilot pool only
        build(sys.argv[2], sys.argv[3], which="pilot")
