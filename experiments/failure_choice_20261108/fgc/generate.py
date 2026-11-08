"""Evaluator side: the task sets of the failure-guided choice test, from the construction test's generator.

    python -m fgc.generate source          the source set (before the freeze): every motivating task of the source
                                           families in the three world copies, and fresh depth tasks of the source
                                           templates
    python -m fgc.generate test            the held test set (after the GO only; the gate's generate stage first):
                                           fresh missing-operation tasks of the held families and fresh depth tasks
                                           of the held templates, salted with the GO's digest

Causes (the generator's own label, evaluator-only; the system side never receives it):
- "operation": a task built on an operation removed from the world's G0 (the construction test's template filters:
  G0 plus the reference fits and predicts at the base budget, G0 alone finds no fit at the base budget). The fix is
  typed-hole construction.
- "search": a G0 program a(b(c(I))) of three different operations of the world's unary list that the base budget
  (150,000 calls) misses and a deeper search finds: G0 finds no fit at the base budget, and a search of at most
  DEPTH_HI calls finds a first fit that is correct. The fix is deeper search. Families: the world and the class of
  the outer operation a (source: a reflection or rotation; held: a crop, that is a half, compress or trim).
Both use the construction test's Builder unchanged (cas/generate.py): real ARC training INPUT grids only, its
filters, sha256 ordering by salt. Size caps: the construction test's worlds took 176 of the 187 pool sources whose
inputs are at most 12 x 12, so new tasks allow inputs up to 16 x 16 (outputs at most 16 x 16, as before); the source
missing-operation tasks are the construction test's own (12 x 12). A source is used once per study; held tasks use
no source of any world copy (any partition) or of the source set.
"""
import hashlib
import json
import os
import sys

from fgc import common as C
from fgc.common import E, D
from cas import generate as GEN                                              # noqa: E402
from cgrow import tasks as T                                                 # noqa: E402

I = ("I",)
DEPTH_HI = 4_000_000
CROPS = ("tophalf", "bottomhalf", "lefthalf", "righthalf", "compress", "trim")
T.MAX_SIDE_IN, T.MAX_SIDE_OUT = 16, 16          # new tasks only (see above)


def depth_templates(b, outer_class):
    ops = list(b.unary)
    outer = [a for a in ops if (a in CROPS) == (outer_class == "crop")]
    return [T.app(a, T.app(m, T.app(c, I))) for a in outer for m in ops for c in ops if len({a, m, c}) == 3]


def depth_task(b, tree, src):
    """S1's depth filter with a wider window: no G0 fit at the base budget; the first fit of a search of at most
    DEPTH_HI calls is correct. The construction test's run/size/triviality filters first."""
    xs = T.inputs_of(*src)
    if len(xs) < 3:
        return None
    outs = b.outputs(tree, xs)
    if outs is None or not T.small(xs, outs):
        return None
    demos = list(zip(xs[:-1], outs[:-1]))
    if any(a == o for a, o in demos) or len(set(outs[:-1])) == 1:
        return None
    base = GEN.S.run(b.g0, demos, [xs[-1]], budget=GEN.S.BASE_BUDGET, cpu_cap=1e9)
    if base["fit"]:
        return None
    deep = GEN.S.run(b.g0, demos, [xs[-1]], budget=DEPTH_HI, cpu_cap=1e9, want=1)
    if not (deep["fit"] and GEN.S.correct(deep, [outs[-1]])):
        return None
    return {"program": D.show(tree), "source": src[0], "train": demos, "test_inputs": [xs[-1]],
            "test_outputs": [outs[-1]], "depth_calls": deep["calls"]}


def used_sources():
    """Every source of every task of the three world copies (all partitions)."""
    out = set()
    for w in C.WORLDS:
        for t in C.load(os.path.join(C.world_dir(w), "evaluator_only", "TASKS_EVAL.json")).values():
            out.add(t["source"])
    return out


def builder(world, families, salt, used):
    cfg = C.config()
    wc = cfg["worlds"][world]
    wcfg = {"removed": wc["removed"], "families": families, "params": {x: wc["params"][x] for x in families},
            "salt": salt}
    gcfg = {"max_tries": cfg["max_tries"], "pools_file": cfg["pools_file"]}
    pool = GEN.pool_ids(gcfg, "main")
    return GEN.Builder(world, wcfg, gcfg, pool, set(used), set(), set())


def depth_tasks(b, templates, n, tag):
    tmpls = sorted(templates, key=lambda t: b.h(f"{tag}:" + D.show(t)))
    out = []
    for t in tmpls:
        if len(out) >= n:
            break
        for i, src in enumerate(b.next_source(f"{tag}:" + D.show(t))):
            if i >= 2:
                break
            r = depth_task(b, t, src)
            if r:
                b.used.add(src[0])
                out.append(r)
                print(json.dumps({"world": b.world, "cause": "search", "program": r["program"]}), flush=True)
                break
    return out


def opaque(world, src, program, kind):
    return "t" + hashlib.sha256(json.dumps([world, src, program, kind, "fgc"]).encode()).hexdigest()[:8]


def to_files(rows):
    system, ev = {}, {}
    for r in rows:
        tid = r["id"]
        system[tid] = {"train": [[C.as_lists(a), C.as_lists(o)] for a, o in r["train"]],
                       "test_inputs": [C.as_lists(q) for q in r["test_inputs"]]}
        ev[tid] = {"world": r["world"], "cause": r["cause"], "family": r["family"], "program": r.get("program"),
                   "source": r["source"], "template": r.get("template"), "depth_calls": r.get("depth_calls"),
                   "test_outputs": [C.as_lists(y) for y in r["test_outputs"]]}
    return system, ev


def source():
    cfg = C.config()
    used = used_sources()
    rows = []
    for w in C.WORLDS:
        sys_t = C.load(os.path.join(C.world_dir(w), "partitions", "TASKS_SYSTEM.json"))
        ev = C.load(os.path.join(C.world_dir(w), "evaluator_only", "TASKS_EVAL.json"))
        for tid, t in sorted(ev.items()):
            if t["partition"] == "M" and t["family"] in cfg["source_families"][w]:
                rows.append({"id": tid, "world": w, "cause": "operation", "family": f"{w}:{t['family']}",
                             "program": t.get("program"), "source": t["source"], "template": t.get("template"),
                             "train": [(D.to_grid(a), D.to_grid(o)) for a, o in sys_t[tid]["train"]],
                             "test_inputs": [D.to_grid(q) for q in sys_t[tid]["test_inputs"]],
                             "test_outputs": [D.to_grid(y) for y in t["test_outputs"]], "in_world": True})
        b = builder(w, [], cfg["source_salt"] + "-" + w, used)
        for r in depth_tasks(b, depth_templates(b, "reflect"), cfg["n_depth_source_per_world"], "srcdepth"):
            used.add(r["source"])
            rows.append({"id": opaque(w, r["source"], r["program"], "search"), "world": w, "cause": "search",
                         "family": f"{w}:depth-reflect", "program": r["program"], "source": r["source"],
                         "template": "depth-reflect", "train": r["train"], "test_inputs": r["test_inputs"],
                         "test_outputs": r["test_outputs"], "in_world": False, "depth_calls": r["depth_calls"]})
    return rows


def test(salt):
    cfg = C.config()
    used = used_sources()
    src = C.load(os.path.join(C.STUDY, "runs", "source", "evaluator_only", "SOURCE_EVAL.json"))
    used |= {t["source"] for t in src.values()}
    rows = []
    for w in C.WORLDS:
        fams = cfg["test_families"][w]
        b = builder(w, fams, salt + "-" + w, used)
        for x in fams:
            parts = b.build_family(x, {"M": cfg["test_quota"]}, part_names=("M",))
            for r in parts["M"]:
                rows.append({"id": opaque(w, r["source"], r["program"], "operation"), "world": w,
                             "cause": "operation", "family": f"{w}:{x}", "program": r["program"],
                             "source": r["source"], "template": r["template"], "train": r["train"],
                             "test_inputs": r["test_inputs"], "test_outputs": r["test_outputs"]})
        for r in depth_tasks(b, depth_templates(b, "crop"), cfg["n_depth_test_per_world"], "testdepth"):
            rows.append({"id": opaque(w, r["source"], r["program"], "search"), "world": w, "cause": "search",
                         "family": f"{w}:depth-crop", "program": r["program"], "source": r["source"],
                         "template": "depth-crop", "train": r["train"], "test_inputs": r["test_inputs"],
                         "test_outputs": r["test_outputs"], "depth_calls": r["depth_calls"]})
        used |= b.used
    return rows


def write(rows, sub, name):
    system, ev = to_files(rows)
    assert len(system) == len(rows), "duplicate task ids"
    d = os.path.join(C.STUDY, "runs", sub)
    worlds = {}
    for r in rows:
        worlds.setdefault(r["world"], []).append(r["id"])
    E.dump(os.path.join(d, f"{name}_SYSTEM.json"), system)
    E.dump(os.path.join(d, "evaluator_only", f"{name}_EVAL.json"), ev)
    man = {"system_sha256": E.sha256(os.path.join(d, f"{name}_SYSTEM.json")),
           "eval_sha256": E.sha256(os.path.join(d, "evaluator_only", f"{name}_EVAL.json")),
           "tasks_by_world": {w: sorted(v) for w, v in worlds.items()},
           "counts": {f"{r['family']}": sum(1 for x in rows if x["family"] == r["family"]) for r in rows}}
    E.dump(os.path.join(d, f"{name}_MANIFEST.json"), man)
    print(json.dumps({"tasks": len(rows), "counts": man["counts"]}))


if __name__ == "__main__":
    if sys.argv[1] == "source":
        write(source(), "source", "SOURCE")
    elif sys.argv[1] == "test":
        from fgc import gate
        salt = gate.claim_and_salt()
        write(test(salt), "test", "TEST")
