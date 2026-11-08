"""Evaluator side: the task sets of the failure-guided choice test, revision 2 (three causes).

    python -m fgc.generate source      the source set (before the freeze): revision 1's source set (the construction
                                       test's motivating tasks of the five source families and the 27 depth tasks)
                                       and fresh wrong-view tasks of the source view families
    python -m fgc.generate test        the held set (after this revision's GO only; the gate's generate stage
                                       first): fresh tasks of every held family, salted with the GO's digest; in
                                       each world view tasks first, then missing-operation and depth tasks

Causes (the generator's own label, evaluator-only; the system side never receives it):
- "operation": a task built on an operation removed from the world's G0 (the construction test's template filters:
  G0 plus the reference fits and predicts at the base budget; G0 alone finds no fit at the base budget). The fix is
  typed-hole construction.
- "search": a G0 program a(b(c(I))) of three different operations of the world's unary list such that G0 finds no
  fit at the base budget and a G0 search of at most DEPTH_HI calls finds a first fit that is correct. The fix is
  deeper search. Families: the world and the class of the outer operation a (source: a reflection or rotation;
  held: a crop, that is a half, compress or trim).
- "view": X applied to every object of the grid under an alternative arc-dsl object view, painted in one colour:
  fill(I, c, mapply(X, objects(I, u, d, b))) (underfill for X = backdrop), with (u, d, b) one of the four
  alternative views and c the smallest colour absent from every input grid of the source. Filters: the program runs
  on every input and its outputs are valid and within the size caps; no demonstration output equals its input and
  the outputs are not all equal; the default view (True, False, True) gives a different output on at least two
  thirds of the inputs; G0 finds no fit at the base budget; a G0 search of at most DEPTH_HI calls finds no correct
  fit (the depth fix does not solve it); and the view search (fgc/views.py) of at most VIEW_HI calls finds a first fit
  that is correct. The fix is the view intervention. Families: the world and X (source: box, backdrop, delta; held:
  outbox, corners, inbox). These are whole-grid transformations of every object; no object is selected by attribute.
Every task uses the construction test's Builder (cas/generate.py) unchanged for its sources and filters: real ARC
training INPUT grids only, sha256 ordering by salt. Size caps for new tasks: inputs and outputs at most 16 x 16 for
source view tasks (as revision 1's depth tasks); held tasks allow 20 x 20 (the pool's smaller sources are used up),
for every cause alike. A source is used once per study; held tasks use no source of any world copy (any partition),
of either revision's source set, or of revision 1's held set.
"""
import hashlib
import json
import os
import sys

from fgc import common as C
from fgc.common import E, D
from fgc import views as V
from cas import generate as GEN                                              # noqa: E402
from cgrow import tasks as T                                                 # noqa: E402

I = ("I",)
DEPTH_HI = 4_000_000
VIEW_HI = 4_000_000
CROPS = ("tophalf", "bottomhalf", "lefthalf", "righthalf", "compress", "trim")
VIEW_OPS = {"box": "fill", "backdrop": "underfill", "delta": "fill", "outbox": "fill", "corners": "fill",
            "inbox": "fill"}
CONST = GEN.CONST
R1 = os.path.join(os.path.dirname(C.STUDY), "failure_choice_20261108")


def caps(side):
    T.MAX_SIDE_IN, T.MAX_SIDE_OUT = side, side


def depth_templates(b, outer_class):
    ops = list(b.unary)
    outer = [a for a in ops if (a in CROPS) == (outer_class == "crop")]
    return [T.app(a, T.app(m, T.app(c, I))) for a in outer for m in ops for c in ops if len({a, m, c}) == 3]


def trivial(xs, outs):
    demos = list(zip(xs[:-1], outs[:-1]))
    return any(a == o for a, o in demos) or len(set(outs[:-1])) == 1


def depth_task(b, tree, src):
    xs = T.inputs_of(*src)
    if len(xs) < 3:
        return None
    outs = b.outputs(tree, xs)
    if outs is None or not T.small(xs, outs) or trivial(xs, outs):
        return None
    demos = list(zip(xs[:-1], outs[:-1]))
    base = GEN.S.run(b.g0, demos, [xs[-1]], budget=GEN.S.BASE_BUDGET, cpu_cap=1e9)
    if base["fit"]:
        return None
    deep = GEN.S.run(b.g0, demos, [xs[-1]], budget=DEPTH_HI, cpu_cap=1e9, want=1)
    if not (deep["fit"] and GEN.S.correct(deep, [outs[-1]])):
        return None
    return {"program": D.show(tree), "source": src[0], "train": demos, "test_inputs": [xs[-1]],
            "test_outputs": [outs[-1]], "depth_calls": deep["calls"]}


def view_tree(x, flags, colour):
    objs = T.app("objects", I, *[("c:T",) if f else ("c:F",) for f in flags])
    return T.app(VIEW_OPS[x], I, ("c:" + CONST[colour],), T.app("mapply", ("fn:" + x,), objs))


def absent_colour(xs):
    present = {v for g in xs for r in g for v in r}
    return next((c for c in range(10) if c not in present), None)


FILTERED = {}


def _why(r):
    FILTERED[r] = FILTERED.get(r, 0) + 1
    return None


def view_task(b, x, view, src):
    xs = T.inputs_of(*src)
    if len(xs) < 3:
        return _why("few_inputs")
    colour = absent_colour(xs)
    if colour is None:
        return _why("no_absent_colour")
    tree = view_tree(x, C.VIEWS[view], colour)
    outs = b.outputs(tree, xs)
    if outs is None or not T.small(xs, outs):
        return _why("does_not_run_or_too_large")
    if trivial(xs, outs):
        return _why("trivial_outputs")
    dflt = b.outputs(view_tree(x, C.DEFAULT_VIEW, colour), xs)
    if dflt is not None and sum(d != o for d, o in zip(dflt, outs)) * 3 < 2 * len(xs):
        return _why("default_view_suffices")
    demos = list(zip(xs[:-1], outs[:-1]))
    base = GEN.S.run(b.g0, demos, [xs[-1]], budget=GEN.S.BASE_BUDGET, cpu_cap=1e9)
    if base["fit"]:
        return _why("g0_base_fits")
    vs = V.view_search(b.g0, demos, [xs[-1]], VIEW_HI)
    if not (vs["fit"] and vs["raw_preds"] and any(list(att) == [outs[-1]] for att in vs["raw_preds"])):
        return _why("view_search_misses")
    deep = GEN.S.run(b.g0, demos, [xs[-1]], budget=DEPTH_HI, cpu_cap=1e9, want=1)
    if deep["fit"] and GEN.S.correct(deep, [outs[-1]]):
        return _why("deep_search_solves")
    return {"program": D.show(tree), "source": src[0], "train": demos, "test_inputs": [xs[-1]],
            "test_outputs": [outs[-1]], "view_calls": vs["calls"], "view": view, "colour": colour}


def used_sources(include_r1_test=True):
    out = set()
    for w in C.WORLDS:
        for t in C.load(os.path.join(C.world_dir(w), "evaluator_only", "TASKS_EVAL.json")).values():
            out.add(t["source"])
    for p in (os.path.join(C.STUDY, "runs", "source", "evaluator_only", "SOURCE_EVAL_R1.json"),
              os.path.join(R1, "runs", "test", "evaluator_only", "TEST_EVAL.json")):
        if os.path.exists(p) and (include_r1_test or "SOURCE" in p):
            out |= {t["source"] for t in C.load(p).values()}
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


def in_part(src, part):
    """Sources split disjointly between parallel generators: part (k, m) keeps sha256(id) mod m == k."""
    return part is None or int(hashlib.sha256(src[0].encode()).hexdigest()[:8], 16) % part[1] == part[0]


def view_tasks(b, x, n, tag, max_tries=40, part=None):
    """n tasks of view family X: each slot draws its view by hash, then tries sources in hash order."""
    out = []
    for slot in range(n):
        view = sorted(C.VIEWS, key=lambda v: b.h(f"{tag}:{x}:{slot}:{v}"))[0]
        tried = 0
        for src in b.next_source(f"{tag}:{x}:{slot}"):
            if not in_part(src, part):
                continue
            tried += 1
            if tried > max_tries:
                break
            r = view_task(b, x, view, src)
            if r:
                b.used.add(src[0])
                out.append(r)
                print(json.dumps({"world": b.world, "cause": "view", "family": x, "view": view,
                                  "program": r["program"]}), flush=True)
                break
    return out


def opaque(world, src, program, kind):
    return "t" + hashlib.sha256(json.dumps([world, src, program, kind, "fgc-r2"]).encode()).hexdigest()[:8]


def to_files(rows):
    system, ev = {}, {}
    for r in rows:
        tid = r["id"]
        system[tid] = {"train": [[C.as_lists(a), C.as_lists(o)] for a, o in r["train"]],
                       "test_inputs": [C.as_lists(q) for q in r["test_inputs"]]}
        ev[tid] = {"world": r["world"], "cause": r["cause"], "family": r["family"], "program": r.get("program"),
                   "source": r["source"], "template": r.get("template"), "depth_calls": r.get("depth_calls"),
                   "view": r.get("view"), "view_calls": r.get("view_calls"),
                   "test_outputs": [C.as_lists(y) for y in r["test_outputs"]]}
    return system, ev


def source_r1_rows():
    sys_r1 = C.load(os.path.join(C.STUDY, "runs", "source", "SOURCE_SYSTEM_R1.json"))
    ev_r1 = C.load(os.path.join(C.STUDY, "runs", "source", "evaluator_only", "SOURCE_EVAL_R1.json"))
    rows = []
    for tid in sorted(ev_r1):
        e = ev_r1[tid]
        rows.append({"id": tid, "world": e["world"], "cause": e["cause"], "family": e["family"],
                     "program": e.get("program"), "source": e["source"], "template": e.get("template"),
                     "depth_calls": e.get("depth_calls"),
                     "train": [(D.to_grid(a), D.to_grid(o)) for a, o in sys_r1[tid]["train"]],
                     "test_inputs": [D.to_grid(q) for q in sys_r1[tid]["test_inputs"]],
                     "test_outputs": [D.to_grid(y) for y in e["test_outputs"]]})
    return rows


def source_view_rows(w, part):
    """One world's source view tasks, from its disjoint share of the pool (parallel generators)."""
    cfg = C.config()
    caps(16)
    used = used_sources(include_r1_test=False)
    b = builder(w, [], cfg["source_salt"] + "-" + w, used)
    rows = []
    for x in cfg["view_source_ops"]:
        for r in view_tasks(b, x, cfg["n_view_source_per_op"], "srcview", part=part,
                            max_tries=cfg.get("view_max_tries", 40)):
            rows.append({"id": opaque(w, r["source"], r["program"], "view"), "world": w, "cause": "view",
                         "family": f"{w}:view-{x}", "program": r["program"], "source": r["source"],
                         "template": "view-" + x, "train": r["train"], "test_inputs": r["test_inputs"],
                         "test_outputs": r["test_outputs"], "view": r["view"], "view_calls": r["view_calls"]})
    return rows


def source():
    rows = source_r1_rows()
    for k, w in enumerate(C.WORLDS):
        rows += source_view_rows(w, (k, len(C.WORLDS)))
    return rows


def test_view_rows(b, w, cfg):
    """One world's held view tasks (generated first, so that every source of the world's share is open to them)."""
    rows = []
    for x in cfg["view_test_ops"]:
        for r in view_tasks(b, x, cfg["n_view_test_per_op"], "testview", part=None,
                            max_tries=cfg.get("view_max_tries", 40)):
            rows.append({"id": opaque(w, r["source"], r["program"], "view"), "world": w, "cause": "view",
                         "family": f"{w}:view-{x}", "program": r["program"], "source": r["source"],
                         "template": "view-" + x, "train": r["train"], "test_inputs": r["test_inputs"],
                         "test_outputs": r["test_outputs"], "view": r["view"], "view_calls": r["view_calls"]})
    return rows


def test_world_rows(w, salt, part):
    """One world's held tasks, from its disjoint share of the pool (parallel generators, after the GO): view tasks
    first, then missing-operation tasks, then depth tasks."""
    cfg = C.config()
    caps(20)
    used = used_sources(include_r1_test=True)
    used |= {t["source"] for t in C.load(os.path.join(C.STUDY, "runs", "source", "evaluator_only",
                                                       "SOURCE_EVAL.json")).values()}
    fams = cfg["test_families"][w]
    b = builder(w, fams, salt + "-" + w, used)
    orig = b.next_source
    b.next_source = lambda key: (s_ for s_ in orig(key) if in_part(s_, part))
    rows = test_view_rows(b, w, cfg)
    for x in fams:
        parts = b.build_family(x, {"M": cfg["test_quota"]}, part_names=("M",))
        for r in parts["M"]:
            rows.append({"id": opaque(w, r["source"], r["program"], "operation"), "world": w, "cause": "operation",
                         "family": f"{w}:{x}", "program": r["program"], "source": r["source"],
                         "template": r["template"], "train": r["train"], "test_inputs": r["test_inputs"],
                         "test_outputs": r["test_outputs"]})
    for r in depth_tasks(b, depth_templates(b, "crop"), cfg["n_depth_test_per_world"], "testdepth"):
        rows.append({"id": opaque(w, r["source"], r["program"], "search"), "world": w, "cause": "search",
                     "family": f"{w}:depth-crop", "program": r["program"], "source": r["source"],
                     "template": "depth-crop", "train": r["train"], "test_inputs": r["test_inputs"],
                     "test_outputs": r["test_outputs"], "depth_calls": r["depth_calls"]})
    return rows


def merge_parts(paths):
    system, ev = {}, {}
    for p in paths:
        d = C.load(p)
        if set(d["system"]) & set(system):
            raise SystemExit("a task id appears in two parts")
        system.update(d["system"])
        ev.update(d["eval"])
    srcs = [e["source"] for e in ev.values()]
    if len(srcs) != len(set(srcs)):
        raise SystemExit("a source serves two held tasks")
    return system, ev


def test(salt):
    cfg = C.config()
    caps(20)
    used = used_sources(include_r1_test=True)
    used |= {t["source"] for t in C.load(os.path.join(C.STUDY, "runs", "source", "evaluator_only",
                                                       "SOURCE_EVAL.json")).values()}
    rows = []
    for w in C.WORLDS:
        fams = cfg["test_families"][w]
        b = builder(w, fams, salt + "-" + w, used)
        rows += test_view_rows(b, w, cfg)
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


def write_sets(system, ev, sub, name):
    d = os.path.join(C.STUDY, "runs", sub)
    worlds, counts = {}, {}
    for t, e in ev.items():
        worlds.setdefault(e["world"], []).append(t)
        counts[e["family"]] = counts.get(e["family"], 0) + 1
    E.dump(os.path.join(d, f"{name}_SYSTEM.json"), system)
    E.dump(os.path.join(d, "evaluator_only", f"{name}_EVAL.json"), ev)
    man = {"system_sha256": E.sha256(os.path.join(d, f"{name}_SYSTEM.json")),
           "eval_sha256": E.sha256(os.path.join(d, "evaluator_only", f"{name}_EVAL.json")),
           "tasks_by_world": {w: sorted(v) for w, v in sorted(worlds.items())}, "counts": dict(sorted(counts.items()))}
    E.dump(os.path.join(d, f"{name}_MANIFEST.json"), man)
    print(json.dumps({"tasks": len(ev), "counts": man["counts"]}))


def write(rows, sub, name):
    system, ev = to_files(rows)
    assert len(system) == len(rows), "duplicate task ids"
    write_sets(system, ev, sub, name)


def save_rows(path, rows):
    system, ev = to_files(rows)
    E.dump(path, {"system": system, "eval": ev})


def merge_source(parts):
    """revision 1's source rows plus the saved per-world view rows, written as the source set."""
    rows = source_r1_rows()
    system, ev = to_files(rows)
    for p in parts:
        d = C.load(p)
        system.update(d["system"])
        ev.update(d["eval"])
    return system, ev


if __name__ == "__main__":
    if sys.argv[1] == "source":
        write(source(), "source", "SOURCE")
    elif sys.argv[1] == "source_world":                 # parallel: one world's view rows into runs/source/parts/
        k = C.WORLDS.index(sys.argv[2])
        save_rows(os.path.join(C.STUDY, "runs", "source", "parts", f"view_{sys.argv[2]}.json"),
                  source_view_rows(sys.argv[2], (k, len(C.WORLDS))))
        print(json.dumps({"filtered": FILTERED}), flush=True)
    elif sys.argv[1] == "test_merge":                   # after the kernel: every world's held rows into runs/test/
        system, ev = merge_parts([os.path.join(C.STUDY, "runs", "test_parts", f"test_{w}.json") for w in C.WORLDS])
        write_sets(system, ev, "test", "TEST")
    elif sys.argv[1] == "source_merge":                 # revision 1's source rows plus every world's view rows
        system, ev = merge_source([os.path.join(C.STUDY, "runs", "source", "parts", f"view_{w}.json")
                                   for w in C.WORLDS])
        write_sets(system, ev, "source", "SOURCE")
    elif sys.argv[1] == "test":
        from fgc import gate
        salt = gate.claim_and_salt()
        write(test(salt), "test", "TEST")
