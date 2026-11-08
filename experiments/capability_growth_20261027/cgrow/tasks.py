"""Test I task construction (EVALUATOR SIDE; run once, before any arm).

Removed set R (evaluator-only): compress, downscale, trim, upscale. G0 = A2's grammar minus R. Expressibility on
probe grids (evaluator_only/expressibility_v1.json, 3M executions, cost level 12): compress and downscale have no
G0 equivalent; upscale has none within level 12 (a macro through hupscale/vupscale exists at a higher cost); trim
is a G0 macro at cost 10 (subgrid(inbox(asindices(I)), I)).

Family tasks for capability X: programs over real S_train / S_select INPUT grids (their outputs are never used):
    T1  X(I[, p])          T2  X(A(I)[, p])          T3  B(X(I[, p]))
A, B: G0 unary grid primitives; p: 2 or 3 for downscale / upscale. Kept only if (a) the program runs on every
input with valid grids, (b) X changes its argument on at least two thirds of the inputs, (c) no demonstration
output equals its input and the outputs are not all equal, (d) G_ref = G0 + X (Grid-only, cost 3) fits the
demonstrations and predicts the query at the base budget, and (e) G0 finds NO fitting program at the base budget.
So C0 = 0 and the reference ceiling = 1 by construction on M, V and E.
Partitions per family: M (3 motivating: one T1, one T2, one T3), V (2: one T2, one T3), E (6, evaluator-only:
two T1, two T2, two T3); composite templates are not shared between partitions; no source task is used twice.
Other sets: U = previously solved (G0 fits and predicts at the base budget): 8 derived from G0-only templates plus
real S_train tasks A2's base search solved, re-verified under G0; D = search-level decoys (G0-only programs that
the base budget misses and 4x the budget finds).
Size cap: input grids at most 12 x 12 and output grids at most 16 x 16 (family, U-derived and D tasks); at most
60 sources tried per template and parameter.
Order: sha256(SALT + candidate key); first qualifying candidates fill the quotas. Outputs:
    partitions/TASKS_SYSTEM.json        opaque ids, demonstrations and query inputs only (what the system sees)
    evaluator_only/TASKS_EVAL.json      families, programs, sources, query outputs, partition labels
    partitions/PARTITIONS_MANIFEST.json sha256 of both files, counts, construction cost
"""
import hashlib
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from cgrow import paths as P, lang0 as L0, search as S     # noqa: E402
from a2 import arcdsl as D                                   # noqa: E402
from harness import data as HD                               # noqa: E402

SALT = "cgrow-testI-20261027"
REMOVED = ("compress", "downscale", "trim", "upscale")
PARAMS = {"compress": [()], "trim": [()], "downscale": [(2,), (3,)], "upscale": [(2,), (3,)]}
CONST = {2: "TWO", 3: "THREE"}
UNARY = ("hmirror", "vmirror", "dmirror", "cmirror", "rot90", "rot180", "rot270", "tophalf", "bottomhalf",
         "lefthalf", "righthalf")
DIHEDRAL = ("hmirror", "vmirror", "dmirror", "cmirror", "rot90", "rot180", "rot270")
QUOTA = {"M": ("T1", "T2", "T3"), "V": ("T2", "T3"), "E": ("T1", "T1", "T2", "T2", "T3", "T3")}
N_U_DERIVED, N_U_REAL, N_D = 8, 6, 4
PROBE_FACTOR = 4
MAX_DEMOS = 4
MAX_SIDE_IN, MAX_SIDE_OUT = 12, 16   # input grids at most 12 x 12, output grids at most 16 x 16 (prompt length)


def h(s):
    return hashlib.sha256((SALT + "|" + s).encode()).hexdigest()


def app(name, *args):
    return ("f:" + name,) + tuple(args)


def x_tree(x, arg, p):
    return app(x, arg, *[("c:" + CONST[v],) for v in p])


def template(kind, x, p, op=None):
    I = ("I",)
    if kind == "T1":
        return x_tree(x, I, p), I
    if kind == "T2":
        inner = app(op, I)
        return x_tree(x, inner, p), inner
    if kind == "T3":
        return app(op, x_tree(x, I, p)), I
    raise ValueError(kind)


def sources():
    ids = [(t, "S_train") for t in HD.split_ids("S_train")] + [(t, "S_select") for t in HD.split_ids("S_select")]
    ids.sort(key=lambda s: h("src:" + s[0]))
    return ids


def small(xs, outs):
    return all(len(g) <= MAX_SIDE_IN and len(g[0]) <= MAX_SIDE_IN for g in xs) and \
        all(len(g) <= MAX_SIDE_OUT and len(g[0]) <= MAX_SIDE_OUT for g in outs)


def inputs_of(tid, split):
    rec = HD.task_record(tid, split)
    demos = [D.to_grid(a) for a, _ in rec["train"]][:MAX_DEMOS]
    return demos + [D.to_grid(rec["test_inputs"][0])]


class Builder:
    def __init__(self):
        dsl, consts, _, _ = D.load()
        self.ev = D.Evaluator(D.guarded(dsl), consts)
        self.g0 = L0.build_g0(REMOVED)
        self.gref = {}
        for x in REMOVED:
            g = L0.build_g0(REMOVED)
            L0.add_production(g, "f:" + x, L0.reference_fn(x), len(PARAMS[x][0]))
            self.gref[x] = g
        self.used = set()
        self.srcs = sources()
        self.log = {"candidates": 0, "filtered": {}, "searches": 0, "cpu_s": 0.0}
        self.cache = {}

    def _bump(self, why):
        self.log["filtered"][why] = self.log["filtered"].get(why, 0) + 1

    def outputs(self, tree, xs):
        try:
            outs = [self.ev.run(tree, x) for x in xs]
        except Exception:                                    # noqa: BLE001
            return None
        if not all(D.valid(o) and D.tag(o) == "G" and len(o) >= 1 and len(o[0]) >= 1 for o in outs):
            return None
        return outs

    def search(self, g, train, q, budget=S.BASE_BUDGET):
        self.log["searches"] += 1
        r = S.run(g, train, [q], budget=budget, cpu_cap=S.BASE_CPU * budget / S.BASE_BUDGET)
        self.log["cpu_s"] += r["cpu_s"]
        return r

    def family_task(self, x, kind, p, op, src):
        """A qualifying task dict or None (with the reason counted)."""
        self.log["candidates"] += 1
        tree, arg = template(kind, x, p, op)
        xs = inputs_of(*src)
        if len(xs) < 3:
            self._bump("few_inputs")
            return None
        outs = self.outputs(tree, xs)
        if outs is None:
            self._bump("does_not_run")
            return None
        if not small(xs, outs):
            self._bump("too_large")
            return None
        args = self.outputs(arg, xs) if arg != ("I",) else xs
        xa = self.outputs(x_tree(x, ("I",), p), args) if args is not None else None
        if xa is None or sum(a != b for a, b in zip(args, xa)) * 3 < 2 * len(xs):
            self._bump("x_degenerate")
            return None
        demos = list(zip(xs[:-1], outs[:-1]))
        if any(a == b for a, b in demos) or len(set(outs[:-1])) == 1:
            self._bump("trivial_outputs")
            return None
        ref = self.search(self.gref[x], demos, xs[-1])
        if not (ref["fit"] and S.correct(ref, [outs[-1]])):
            self._bump("reference_misses")
            return None
        base = self.search(self.g0, demos, xs[-1])
        if base["fit"]:
            self._bump("g0_fits")
            return None
        return {"family": x, "template": kind, "params": list(p), "op": op, "program": D.show(tree),
                "source": src[0], "source_split": src[1], "train": demos, "test_inputs": [xs[-1]],
                "test_outputs": [outs[-1]], "ref_program": ref["program"], "g0_level": base["level_complete"],
                "g0_stop": base["stop"], "g0_closure_capped": base["closure_capped"]}

    def next_source(self, key):
        for s in sorted(self.srcs, key=lambda s: h(key + ":" + s[0])):
            if s[0] not in self.used:
                yield s

    def build_family(self, x):
        comps = [("T2", a) for a in UNARY] + [("T3", b) for b in UNARY]
        comps.sort(key=lambda c: h(f"tmpl:{x}:{c[0]}:{c[1]}"))
        used_tmpl = set()
        parts = {}
        for part in ("M", "V", "E"):
            parts[part] = []
            for slot, kind in enumerate(QUOTA[part]):
                got = None
                if kind == "T1":
                    cands = [("T1", None)]
                else:
                    cands = [c for c in comps if c[0] == kind and c not in used_tmpl]
                for c in cands:
                    plist = sorted(PARAMS[x], key=lambda p: h(f"p:{x}:{part}:{slot}:{p}"))
                    tries = 0
                    for p in plist:
                        for src in self.next_source(f"{x}:{part}:{slot}:{c}:{p}"):
                            tries += 1
                            t = self.family_task(x, c[0], p, c[1], src)
                            if t is not None:
                                got = t
                                break
                            if tries >= 60:
                                break
                        if got:
                            break
                    if got:
                        if c[0] != "T1":
                            used_tmpl.add(c)
                        break
                if got is None:
                    raise RuntimeError(f"no qualifying task for {x} {part} {kind}")
                self.used.add(got["source"])
                got["partition"] = part
                parts[part].append(got)
                print(json.dumps({"family": x, "part": part, "program": got["program"], "source": got["source"]}),
                      flush=True)
        return parts

    def g0_task(self, tree, src, want_base, probe=False):
        xs = inputs_of(*src)
        if len(xs) < 3:
            return None
        outs = self.outputs(tree, xs)
        if outs is None or not small(xs, outs):
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
            deep = self.search(self.g0, demos, xs[-1], budget=S.BASE_BUDGET * PROBE_FACTOR)
            if not (deep["fit"] and S.correct(deep, [outs[-1]])):
                return None
        return {"family": None, "program": D.show(tree), "source": src[0], "source_split": src[1], "train": demos,
                "test_inputs": [xs[-1]], "test_outputs": [outs[-1]], "g0_program": base["program"]}

    def build_u_derived(self):
        I = ("I",)
        tmpls = [app(b, I) for b in UNARY] + [app(c, I, app(b, I)) for c in ("hconcat", "vconcat") for b in DIHEDRAL]
        tmpls.sort(key=lambda t: h("u:" + D.show(t)))
        out = []
        for t in tmpls:
            if len(out) >= N_U_DERIVED:
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

    def build_d(self):
        I = ("I",)
        tmpls = [app(c, app(b1, I), app(b2, I)) for c in ("hconcat", "vconcat") for b1 in DIHEDRAL for b2 in DIHEDRAL
                 if b1 < b2]
        tmpls += [app(a, app(b, app(c, I))) for a in ("tophalf", "lefthalf", "bottomhalf", "righthalf")
                  for b in DIHEDRAL for c in ("tophalf", "lefthalf", "righthalf", "bottomhalf") if a != c]
        tmpls.sort(key=lambda t: h("d:" + D.show(t)))
        out = []
        for t in tmpls:
            if len(out) >= N_D:
                break
            for i, src in enumerate(self.next_source("d:" + D.show(t))):
                if i >= 3:
                    break
                r = self.g0_task(t, src, want_base=False)
                if r:
                    self.used.add(src[0])
                    r["partition"] = "D"
                    out.append(r)
                    print(json.dumps({"part": "D", "program": r["program"]}), flush=True)
                    break
        return out

    def build_u_real(self):
        with open(os.path.join(P.SWEEP, "a2", "out", "traces.jsonl"), encoding="utf-8") as f:
            solved = [json.loads(x)["task_id"] for x in f if json.loads(x).get("correct")]
        labels = HD.source_labels("S_train")
        out = []
        for tid in sorted(solved, key=lambda t: h("ureal:" + t)):
            if len(out) >= N_U_REAL:
                break
            rec = HD.task_record(tid, "S_train")
            train = [(D.to_grid(a), D.to_grid(b)) for a, b in rec["train"]]
            qs = [D.to_grid(q) for q in rec["test_inputs"]]
            ys = [D.to_grid(y) for y in labels[tid]]
            r = S.run(self.g0, train, qs)
            self.log["searches"] += 1
            self.log["cpu_s"] += r["cpu_s"]
            if r["fit"] and S.correct(r, ys):
                out.append({"family": None, "program": None, "source": tid, "source_split": "S_train",
                            "train": train, "test_inputs": qs, "test_outputs": ys, "g0_program": r["program"],
                            "partition": "U", "real": True})
        return out


def opaque(t):
    return "t" + hashlib.sha256(json.dumps([t["source"], t.get("program"), t["partition"]]).encode()).hexdigest()[:8]


def main():
    t0 = time.process_time()
    b = Builder()
    tasks = []
    for x in REMOVED:
        parts = b.build_family(x)
        for part in ("M", "V", "E"):
            tasks += parts[part]
    tasks += b.build_d()
    tasks += b.build_u_derived()
    tasks += b.build_u_real()
    for t in tasks:
        t["id"] = opaque(t)
    assert len({t["id"] for t in tasks}) == len(tasks)

    def js(g):
        return [list(r) for r in g]
    system = {t["id"]: {"train": [[js(a), js(o)] for a, o in t["train"]], "test_inputs": [js(q) for q in t["test_inputs"]]}
              for t in tasks if t["partition"] != "E"}
    ev = {t["id"]: {k: v for k, v in t.items() if k not in ("train", "test_inputs", "test_outputs")}
          | {"train": [[js(a), js(o)] for a, o in t["train"]], "test_inputs": [js(q) for q in t["test_inputs"]],
             "test_outputs": [js(y) for y in t["test_outputs"]]} for t in tasks}
    os.makedirs(P.PARTITIONS, exist_ok=True)
    os.makedirs(P.EVALUATOR_DIR, exist_ok=True)
    sp = os.path.join(P.PARTITIONS, "TASKS_SYSTEM.json")
    ep = os.path.join(P.EVALUATOR_DIR, "TASKS_EVAL.json")
    with P.open_write(sp) as f:
        json.dump(system, f, sort_keys=True)
    with P.open_write(ep) as f:
        json.dump(ev, f, sort_keys=True, indent=0)
    with P.open_write(os.path.join(P.EVALUATOR_DIR, "REMOVED.json")) as f:
        json.dump({"removed": REMOVED, "params": {k: [list(p) for p in v] for k, v in PARAMS.items()},
                   "new_cost": L0.NEW_COST}, f, indent=1)
    counts = {}
    for t in tasks:
        k = (t["family"] or "-") + ":" + t["partition"]
        counts[k] = counts.get(k, 0) + 1

    def sha(path):
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    man = {"built_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "salt": SALT,
           "tasks_system_sha256": sha(sp), "tasks_eval_sha256": sha(ep),
           "removed_sha256": sha(os.path.join(P.EVALUATOR_DIR, "REMOVED.json")), "counts": counts,
           "system_ids": sorted(system), "construction": b.log | {"cpu_s": round(b.log["cpu_s"], 1),
                                                                   "process_cpu_s": round(time.process_time() - t0, 1)}}
    with P.open_write(os.path.join(P.PARTITIONS, "PARTITIONS_MANIFEST.json")) as f:
        json.dump(man, f, indent=1, sort_keys=True)
    print(json.dumps({"counts": counts, "log": man["construction"]}, indent=1))


if __name__ == "__main__":
    main()
