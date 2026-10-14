"""Generator semantic-degeneracy audit (DEVELOPMENT). Does a family's planted rule collapse to a simpler rule
on everything the generator produces?

  python -m cora_fhr.degeneracy_audit   -> outputs/cora_fhr/degeneracy_audit.json

1. D3 on the stored dev corpus.
   - For every object in every D3 demonstration and test pair, compare three things: the planted union
     union(ring8, hull)[part_minority], the constructed witness operator, and the recorded output.
   - Why they agree: _shape() gives each object exactly one minority cell (a 1-1 colour tie is still one
     cell). The hull of one cell is that cell, and finalize() removes it because it is occupied.
2. Multi-minority perturbations.
   - Objects with 2 or more minority cells, where hull can add free cells that ring8 misses.
   - Counts how often the constructed operator differs from the planted union.
3. Every family with a planted rule (the G families, and S).
   - Pools generated instances per parameter setting and lists every grammar expression that reproduces
     all of them.
   - A fit with fewer transforms than the truth is a SEMANTIC COLLAPSE. Another fit with the same number
     is an ALIAS.
   - Instances come from the generator with seeds outside every split (500000+). The sealed final split
     is neither generated nor read; this samples the families' generator, as calibrate() does.
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from cora_fhr import corpus_c4 as C4                                    # noqa: E402
from cora_fhr import ggrow as GG                                        # noqa: E402

OUT = os.path.join(HERE, "outputs", "cora_fhr")
WITNESS = os.path.join(HERE, "docs", "summit_demo_20261023", "data", "witness.json")
D3_TRUTH = C4.family_expr("D3", np.random.default_rng(0))
HULL = ("hull",)


def ntrans(e):
    return 1 if e[0] == "d1" else 2


def components(G):
    """8-connected non-background objects; the generator keeps objects at least 2 cells apart."""
    G = np.asarray(G)
    vals, counts = np.unique(G, return_counts=True)
    bg = int(min(zip(vals, counts), key=lambda vc: (-vc[1], vc[0]))[0])
    seen, objs = set(), []
    for r, c in zip(*np.nonzero(G != bg)):
        r, c = int(r), int(c)
        if (r, c) in seen:
            continue
        stack, o = [(int(r), int(c))], {}
        seen.add((r, c))
        while stack:
            p = stack.pop()
            o[p] = int(G[p])
            for i in (-1, 0, 1):
                for j in (-1, 0, 1):
                    q = (p[0] + i, p[1] + j)
                    if 0 <= q[0] < G.shape[0] and 0 <= q[1] < G.shape[1] and q not in seen and G[q] != bg:
                        seen.add(q)
                        stack.append(q)
        objs.append(o)
    return objs


def hull_extra(x):
    """Free cells the hull branch adds beyond the ring8 branch, for the part_minority source."""
    S = GG.source("part_minority", x)
    return GG.finalize(GG.transform(HULL, S, x), x) - GG.finalize(GG.transform(("ring", 8), S, x), x)


def d3_corpus(learned, corpus="c4_dev_v2"):
    tasks = json.load(open(os.path.join(OUT, f"{corpus}.json")))["tasks"]
    rows = []
    for key, t in sorted(tasks.items()):
        if t["family"] != "D3":
            continue
        truth = GG.from_str(t["truth"])
        r = {"key": key, "truth": t["truth_pretty"], "pairs": 0, "objects": 0, "minority_cells": {},
             "truth_eq_learned": 0, "hull_adds_cells": 0, "output_reproduced": 0}
        for kind, pairs in (("train", t["train"]), ("test", t["test"])):
            for inp, out in pairs:
                G, Y = np.asarray(inp), np.asarray(out)
                added_truth = set()
                for o in components(G):
                    x = GG.Ctx(o, G)
                    if x.n_colours < 2:
                        continue                                    # distractor: no minority part, adds nothing
                    r["objects"] += 1
                    m = str(len(GG.source("part_minority", x)))
                    r["minority_cells"][m] = r["minority_cells"].get(m, 0) + 1
                    a, b = GG.evaluate(truth, x), GG.evaluate(learned, x)
                    r["truth_eq_learned"] += a == b
                    r["hull_adds_cells"] += bool(hull_extra(x))
                    added_truth |= a
                r["pairs"] += 1
                r["output_reproduced"] += added_truth == {(int(i), int(j)) for i, j in zip(*np.nonzero(Y != G))}
        rows.append(r)
    return rows


def multi_minority(learned, n=1000, seed=600000):
    rng = np.random.default_rng(seed)
    res = {"objects": 0, "differ": 0, "by_k": {}}
    while res["objects"] < n:
        size = int(rng.integers(5, 10))
        k = int(rng.integers(2, (size - 1) // 2 + 1))              # minority stays the minority
        cells = {(0, 0)}
        while len(cells) < size:                                    # the same growth as C4._shape
            r, c = list(cells)[int(rng.integers(len(cells)))]
            dr, dc = ((-1, 0), (1, 0), (0, -1), (0, 1))[int(rng.integers(4))]
            cells.add((r + dr, c + dc))
        cells = sorted(cells)
        c1, c2 = (int(v) for v in rng.choice(np.arange(1, 10), 2, replace=False))
        col = {p: c1 for p in cells}
        for i in rng.choice(len(cells), k, replace=False):
            col[cells[int(i)]] = c2
        G = np.zeros((16, 16), int)
        o = C4._place(rng, G, col)
        if o is None:
            continue
        x = GG.Ctx(o, G)
        d = GG.evaluate(D3_TRUTH, x) != GG.evaluate(learned, x)
        res["objects"] += 1
        res["differ"] += d
        b = res["by_k"].setdefault(str(k), {"objects": 0, "differ": 0})
        b["objects"] += 1
        b["differ"] += d
    return res


def fitting(instances, cap=40):
    ctx = [GG.Ctx(o, G) for o, _a, G in instances]
    targets = [set(a) for _o, a, _G in instances]
    fits = []
    for e in GG.expressions():
        if all(GG.evaluate(e, x) == t for x, t in zip(ctx, targets)):
            fits.append(e)
            if len(fits) >= cap:
                break
    return fits


def family_audit(families=("D1", "D2", "D3", "F1", "F2", "F3", "F4", "F5", "S"), want=60):
    out = []
    for fam in families:
        settings = {}
        for i in range(600):
            e = C4.family_expr(fam, np.random.default_rng(500000 + i))
            settings.setdefault(GG.to_str(e), e)
        for si, (s, truth) in enumerate(sorted(settings.items())):
            rng = np.random.default_rng(700000 + 1000 * len(out) + si)
            inst, tries = [], 0
            while len(inst) < want and tries < 5000:
                tries += 1
                H, W = (int(v) for v in rng.integers(10, 15, size=2))
                cols = tuple(int(v) for v in rng.choice(np.arange(1, 10), 4, replace=False))
                dm = C4._demo(rng, fam, truth, cols, H, W, distractor=bool(rng.random() < 0.5))
                if dm is not None:
                    inst += [(o, a, dm[0]) for o, a in dm[2]]
            fits = fitting(inst)
            simpler = [e for e in fits if ntrans(e) < ntrans(truth)]
            alias = [e for e in fits if e != truth and ntrans(e) == ntrans(truth)]
            out.append({"family": fam, "truth": GG.pretty(truth), "instances": len(inst),
                        "fits_listed": len(fits), "fits_capped": len(fits) >= 40, "fits": [GG.pretty(e) for e in fits],
                        "verdict": "SEMANTIC_COLLAPSE" if simpler else ("ALIAS" if alias else "NONE"),
                        "simplest_equivalent": GG.pretty(fits[0]) if fits else None})
            print(fam, out[-1]["verdict"], GG.pretty(truth), "->", out[-1]["simplest_equivalent"], flush=True)
    return out


def main():
    w = json.load(open(WITNESS))
    learned = GG.from_str(w["operator"]["expr"])
    res = {"witness_operator": GG.pretty(learned), "d3_truth": GG.pretty(D3_TRUTH),
           "d3_corpus": d3_corpus(learned), "multi_minority": multi_minority(learned), "families": family_audit()}
    json.dump(res, open(os.path.join(OUT, "degeneracy_audit.json"), "w"), indent=1)
    print(json.dumps({k: res[k] for k in ("witness_operator", "d3_truth", "d3_corpus", "multi_minority")}, indent=1))


if __name__ == "__main__":
    main()
