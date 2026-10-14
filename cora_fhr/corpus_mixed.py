"""Mixed-coverage development corpus for the causal failure-evidence test (DEVELOPMENT ONLY; not C4, not final).

  python -m cora_fhr.corpus_mixed            -> outputs/cora_fhr/mix_dev.json, plus a static feasibility report
                                                (outputs/cora_fhr/mix_dev_feasibility.json)

Every scene holds two kinds of growing object, with the same added colour:
- kind N: grows by ring(8)[self], a halo, which native CORA explains;
- kind G: grows by ring(8)[part_minority], a ring around its one minority cell, which native cannot express
  (the D3-effective rule).

The two families differ only in what separates the kinds:
- M1: colour. Kind N is single-coloured g1; kind G is g2 plus a minority cell m.
- M3: size only. Both kinds are g plus one minority cell m. Kind N has 5-6 cells, kind G 3-4. A blind
  clustering by colour signature cannot separate them.

The failure record (native's explained/memorized partition) is the information under test. The static
feasibility check uses the generator's knowledge only to report whether the design separates the arms:
- E-proxy: kind-G correspondences only;
- C'-proxy: all correspondences pooled;
- C''-proxy: grouped by colour signature.
It does not stand in for native's actual failure records; the pilot measures those.

Seeds are 13000+, disjoint from C4 dev (11000), final (11500), calibration (19000) and the audits (500000+).
The C4 generator and its sealed final split are imported, not modified.
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
SEED0 = 13000
SPLIT = {"M1": 4, "M3": 4}
RULE_N = ("d1", GG.SOURCES.index("self"), GG.TRANSFORMS.index(("ring", 8)))
RULE_G = ("d1", GG.SOURCES.index("part_minority"), GG.TRANSFORMS.index(("ring", 8)))


def _obj(rng, size, body, minor):
    col = C4._shape(rng, size, minor is not None, body, minor if minor is not None else body)
    return col


def _demo(rng, fam, cols, H, W):
    g1, g2, m, add = cols
    G = np.zeros((H, W), int)
    objs = []
    kinds = ["N"] * int(rng.integers(1, 3)) + ["G"] * int(rng.integers(1, 3))
    for k in kinds:
        if fam == "M1":
            shape = _obj(rng, int(rng.integers(2, 6)), g1, None) if k == "N" else _obj(rng, int(rng.integers(3, 6)), g2, m)
        else:
            shape = _obj(rng, int(rng.integers(5, 7)), g1, m) if k == "N" else _obj(rng, int(rng.integers(3, 5)), g1, m)
        o = C4._place(rng, G, shape)
        if o is None:
            return None
        objs.append((k, o))
    added = [GG.evaluate(RULE_N if k == "N" else RULE_G, GG.Ctx(o, G)) for k, o in objs]
    if any(not a for a in added) or sum(len(a) for a in added) != len(set().union(*added)):
        return None
    out = G.copy()
    for a in added:
        for p in a:
            out[p] = add
    return G, out, [(k, o, a) for (k, o), a in zip(objs, added)]


def make_task(fam, seed):
    from cora_fhr import baseline as BL
    rng = np.random.default_rng(seed)
    for _attempt in range(400):
        H, W = (int(v) for v in rng.integers(11, 16, size=2))
        cols = tuple(int(v) for v in rng.choice(np.arange(1, 10), 4, replace=False))
        demos = []
        for _k in range(4):
            dm = _demo(rng, fam, cols, H, W)
            if dm is None:
                break
            demos.append(dm)
        if len(demos) < 4:
            continue
        train = [(k, o, a, G) for G, _out, grows in demos[:3] for k, o, a in grows]
        kn = [(o, a, G) for k, o, a, G in train if k == "N"]
        kg = [(o, a, G) for k, o, a, G in train if k == "G"]
        if not all(BL.native_explains(o, a, cols[3], G) for o, a, G in kn):
            continue                                                   # kind N must be native-covered
        if any(BL.native_explains(o, a, cols[3], G) for o, a, G in kg) or BL.reach_setting(kg) is not None:
            continue                                                   # kind G must need construction
        return {"family": fam, "seed": seed, "truth_N": GG.pretty(RULE_N), "truth_G": GG.pretty(RULE_G),
                "train": [[G.tolist(), out.tolist()] for G, out, _g in demos[:3]],
                "test": [[demos[3][0].tolist(), demos[3][1].tolist()]],
                "_kinds": [[[k, sorted(o)] for k, o, _a in grows] for _G, _out, grows in demos]}
    return None


def feasibility(task):
    """Static, generator-side: does the design separate E from C' and C'' (proxies, not native records)?"""
    from cora_fhr.degeneracy_audit import components
    inst = {"N": [], "G": []}
    tests = []
    for di, (inp, out) in enumerate(task["train"] + task["test"]):
        G, Y = np.asarray(inp), np.asarray(out)
        for o in components(G):
            a = {(int(i), int(j)) for i, j in zip(*np.nonzero(Y != G))} & GG.Ctx(o, G).free
            near = {p for p in a if min(max(abs(p[0] - q[0]), abs(p[1] - q[1])) for q in o) <= 1}
            k = "G" if GG.evaluate(RULE_G, GG.Ctx(o, G)) == near else "N"
            (tests if di == 3 else inst[k]).append((k, o, near, G))
    for k in inst:
        inst[k] = [(o, a, G) for _k, o, a, G in inst[k]]
    e = GG.search(inst["G"])[0]
    c1 = GG.search(inst["N"] + inst["G"])[0]
    sig = {}
    for o, a, G in inst["N"] + inst["G"]:
        sig.setdefault(frozenset(o.values()), []).append((o, a, G))
    c2 = sorted((GG.pretty(x) for x in (GG.search(v)[0] for v in sig.values()) if x is not None))
    e_ok = e is not None and all(GG.evaluate(e, GG.Ctx(o, G)) == a for k, o, a, G in tests if k == "G")
    return {"E_proxy": GG.pretty(e) if e else None, "E_proxy_predicts_test_G": e_ok,
            "C1_pooled_proxy": GG.pretty(c1) if c1 else None, "C2_colour_signature_proxy": c2,
            "C2_separates": GG.pretty(RULE_G) in c2}


def main():
    tasks, feas = {}, {}
    for fi, (fam, n) in enumerate(sorted(SPLIT.items())):
        seed = SEED0 + 100 * fi
        while sum(t["family"] == fam for t in tasks.values()) < n:
            t = make_task(fam, seed)
            seed += 1
            if t is None:
                continue
            key = f"mix_{fam}_{sum(x['family'] == fam for x in tasks.values()):02d}"
            tasks[key] = t
            feas[key] = feasibility(t)
            print(key, feas[key], flush=True)
    json.dump({"generator": "corpus_mixed v1", "tasks": tasks}, open(os.path.join(OUT, "mix_dev.json"), "w"))
    json.dump(feas, open(os.path.join(OUT, "mix_dev_feasibility.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
