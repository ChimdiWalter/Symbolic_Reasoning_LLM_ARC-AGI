"""FORENSIC (evaluator-only) expressibility ceiling for the 58-task pool. DEVELOPMENT; it uses the answers.

  python -m cora_fhr.oracle_expressibility [--corpus standin58] [--workers 2]
      -> outputs/cora_fhr/oracle_expressibility_<corpus>.json

For each task and each of native's 7 segmentation views, the question is whether one G-grow v1 expression,
applied to every object of the view, adds exactly the changed cells of the pairs. Two pair sets are tested:
- TRAIN: the training pairs only, which construction could see. Does a train-fit also give the correct test
  output?
- ALL: the training pairs plus the test pair with its TRUE answer. This is the ceiling: whether the language
  can express the task at all.

Classes:
- EXPRESSIBLE_AND_DETERMINED: some train-fit in some view predicts the test correctly;
- EXPRESSIBLE_NOT_DETERMINED: the ALL-fit exists, but no train-fit predicts the test;
- INEXPRESSIBLE: no single expression in any view reproduces all pairs.

This checks positions only (colours are not compared), so it is a necessary condition and an upper bound
on what construction could reach. The answers are read here for diagnosis only. Nothing feeds back into
any arm.
"""
import argparse
import json
import multiprocessing as mp
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
OUT = os.path.join(HERE, "outputs", "cora_fhr")


def _objects(grid, view):
    import geocat_arc.object_reasoning.segmentation as S
    from geocat_arc.object_reasoning.types import cell_colors_of
    from geocat_arc.perception.grid import Grid
    g = Grid(np.asarray(grid))
    return [{(int(r), int(c)): int(v) for (r, c), v in cell_colors_of(o).items()} for o in S.segment(g, view, S.background_for(g, view))]


def _fits(pairs, view, cap=3):
    """Canonical-first G-grow expressions whose per-object union equals each pair's changed cells (cached)."""
    from cora_fhr import ggrow as GG
    data = []
    for a, b in pairs:
        A, B = np.asarray(a), np.asarray(b)
        if A.shape != B.shape:
            return []
        objs = [o for o in _objects(a, view) if o]
        changed = {(int(r), int(c)) for r, c in zip(*np.nonzero(A != B))}
        data.append(([GG.Ctx(o, A) for o in objs], changed))
    cache = [[{} for _ in ctxs] for ctxs, _ in data]

    def r1(i, j, s, t):
        k = (s, t)
        if k not in cache[i][j]:
            x = data[i][0][j]
            cache[i][j][k] = GG.transform(GG.TRANSFORMS[t], GG.source(GG.SOURCES[s], x), x)
        return cache[i][j][k]

    found = []
    for e in GG.expressions():
        ok = True
        for i, (ctxs, changed) in enumerate(data):
            got = set()
            for j, x in enumerate(ctxs):
                if e[0] == "d1":
                    got |= GG.finalize(r1(i, j, e[1], e[2]), x)
                elif e[0] == "d2":
                    got |= GG.finalize(GG.transform(GG.TRANSFORMS[e[3]], r1(i, j, e[1], e[2]), x), x)
                else:
                    got |= GG.finalize(r1(i, j, e[1], e[2]) | r1(i, j, e[1], e[3]), x)
                if not got <= changed:
                    break
            if got != changed:
                ok = False
                break
        if ok:
            found.append(e)
            if cap is not None and len(found) >= cap:
                break
    return found


def _task(args):
    tid, task = args
    from cora_funnel import run as FR                                  # noqa: F401  (sealed flags)
    from cora_fhr import ggrow as GG
    from geocat_arc.object_reasoning.types import SegmentationVariant as V
    train = [(a, b) for a, b in task["train"]]
    test = [(a, b) for a, b in task["test"]]
    rec = {"key": tid, "views": {}}
    for view in V:
        fa = _fits(train + test, view)
        ft = _fits(train, view)
        det = False
        for e in ft:
            pred_ok = True
            for a, b in test:
                A, B = np.asarray(a), np.asarray(b)
                objs = [o for o in _objects(a, view) if o]
                got = set().union(*[GG.evaluate(e, GG.Ctx(o, A)) for o in objs]) if objs else set()
                if got != {(int(r), int(c)) for r, c in zip(*np.nonzero(A != B))}:
                    pred_ok = False
            det = det or pred_ok
        rec["views"][view.value] = {"all_fit": GG.pretty(fa[0]) if fa else None, "train_fits": len(ft),
                                    "train_fit_predicts_test": det}
    vs = rec["views"].values()
    rec["class"] = ("EXPRESSIBLE_AND_DETERMINED" if any(v["train_fit_predicts_test"] for v in vs) else
                    "EXPRESSIBLE_NOT_DETERMINED" if any(v["all_fit"] for v in vs) else "INEXPRESSIBLE")
    return rec


def main(argv=None):
    import collections
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="standin58")
    ap.add_argument("--workers", type=int, default=2)
    a = ap.parse_args(argv)
    tasks = json.load(open(os.path.join(OUT, f"{a.corpus}.json")))["tasks"]
    with mp.get_context("fork").Pool(a.workers, maxtasksperchild=4) as pool:
        recs = sorted(pool.imap_unordered(_task, sorted(tasks.items())), key=lambda r: r["key"])
    by = dict(collections.Counter(r["class"] for r in recs))
    json.dump({"label": "FORENSIC: evaluator-only, uses answers; positions only (an upper bound)", "by_class": by, "tasks": recs},
              open(os.path.join(OUT, f"oracle_expressibility_{a.corpus}.json"), "w"), indent=1)
    print(by)
    for r in recs:
        if r["class"] != "INEXPRESSIBLE":
            print(r["key"], r["class"], {v: x["all_fit"] for v, x in r["views"].items() if x["all_fit"]})


if __name__ == "__main__":
    main()


def colour_audit(corpus="standin58"):
    """Exhaustive colour check (2026-10-19 audit). For each position-expressible task, test EVERY fitting single
    expression in EVERY view, not just the first. Passing means the true added cells have one colour per object in
    every pair (what a single-colour growth action can produce). Also records whether that colour is constant
    across the task or equals the object's own (majority) colour. Evaluator-only."""
    from cora_funnel import run as FR                                  # noqa: F401
    from cora_fhr import ggrow as GG
    from geocat_arc.object_reasoning.types import SegmentationVariant as V
    ox = {r["key"]: r for r in json.load(open(os.path.join(OUT, f"oracle_expressibility_{corpus}.json")))["tasks"]}
    tasks = json.load(open(os.path.join(OUT, f"{corpus}.json")))["tasks"]
    out = {}
    for k, r in sorted(ox.items()):
        if r["class"] == "INEXPRESSIBLE":
            continue
        pairs = [(a, b) for a, b in tasks[k]["train"] + tasks[k]["test"]]
        res = {"fitting_examined": 0, "one_colour_per_object": 0, "constant_colour": 0, "object_colour": 0, "examples": []}
        for view in V:
            for e in _fits(pairs, view, cap=None):
                res["fitting_examined"] += 1
                single, cols, own = True, set(), True
                for a, b in pairs:
                    A, B = np.asarray(a), np.asarray(b)
                    for o in [o for o in _objects(a, view) if o]:
                        cells = GG.evaluate(e, GG.Ctx(o, A))
                        cs = {int(B[p]) for p in cells}
                        if len(cs) > 1:
                            single = False
                        cols |= cs
                        if cs and cs != {GG.Ctx(o, A).majority}:
                            own = False
                if single:
                    res["one_colour_per_object"] += 1
                    res["constant_colour"] += len(cols) == 1
                    res["object_colour"] += own
                    if len(res["examples"]) < 3:
                        res["examples"].append(f"{view.value}: {GG.pretty(e)}")
        out[k] = res
        print(k, res, flush=True)
    json.dump({"label": "FORENSIC colour audit: every fitting single expression in every view", "tasks": out},
              open(os.path.join(OUT, f"oracle_colour_audit_{corpus}.json"), "w"), indent=1)
