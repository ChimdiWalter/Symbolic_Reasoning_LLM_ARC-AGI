"""Corpus C4 v1 (SYNTHETIC), protocol section 5.

  python -m cora_fhr.corpus_c4 dev          -> outputs/cora_fhr/c4_dev.json (+ .sha256)
  python -m cora_fhr.corpus_c4 calibrate    -> rejection rates of the FINAL families on calibration seeds
                                              (19000+; never final tasks), for the preregistered F5 rule
  python -m cora_fhr.corpus_c4 final        -> REFUSED unless CORA_FHR_FINAL_FREEZE=1 (only at the freeze)

Each task: 3 demonstrations and 1 test, on 10-14 x 10-14 grids, background 0. The ground truth (a G-grow
expression or a stated rule), the family and the test output are evaluator-only fields; the solver view
(solver_view) carries training pairs and the test input only.

Growth (G) samples are rejected when a native growth mode explains any growing object or a cora_reach
setting reproduces the training instances (the protocol's B-rejection), so no G task is solvable by
selection from the frozen baseline.
"""
import hashlib
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "outputs", "cora_fhr")
sys.path.insert(0, HERE)
# the sealed native v23 flags: native's derived growth modes are gated by them, so the B-rejection check
# must see exactly what native v23 detects
for _k in [k for k in os.environ if k.startswith("ARC_")]:
    del os.environ[_k]
os.environ.update({"ARC_DIHEDRAL_FRAMES": "45", "ARC_GENERATIVE": "1", "ARC_PATTERN_DERIVE": "1",
                   "ARC_VARIANT_BUDGET": "1", "ARC_RAY_EXT": "1"})

from cora_fhr import ggrow as GG                                     # noqa: E402

S, T = GG.SOURCES.index, GG.TRANSFORMS.index
SEEDS = {"dev": 11000, "final": 11500, "calibrate": 19000}
SPLITS = {"dev": {"D1": 5, "D2": 5, "D3": 5, "N0": 3, "S": 3, "X": 3, "U": 3},
          # F3 replaced by the preregistered alternate F5: calibration (seeds 19000+, never final tasks) rejected
          # 86% of F3 samples as baseline-explainable, above the 50% rule (Amendment 1)
          "final": {"F1": 10, "F2": 10, "F5": 10, "F4": 10, "N0": 10, "S": 10, "X": 10, "U": 10}}
G_FAMILIES = ("D1", "D2", "D3", "F1", "F2", "F3", "F4", "F5")
OPP = {"N": "S", "S": "N", "E": "W", "W": "E"}


def family_expr(fam, rng):
    """The family's ground-truth expression with its per-task parameters."""
    d = str(rng.choice(["N", "S", "E", "W"]))
    diag = str(rng.choice(["NE", "NW", "SE", "SW"]))
    if fam == "D1":
        return ("d1", S(f"edge:{d}"), T(("ray", d, "obstacle")))
    if fam == "D2":
        return ("d2", S("self"), T(("reflect", d)), T(("shift", "unit", d)))
    if fam == "D3":
        return ("u", S("part_minority"), *sorted((T(("ring", 8)), T(("hull",)))))
    if fam == "F1":
        return ("d1", S("corners"), T(("ray", diag, "obstacle")))
    if fam == "F2":
        return ("d2", S("part_minority"), T(("ray", d, "border")), T(("ring", 4)))
    if fam == "F3":
        return ("d2", S("self"), T(("reflect", "V")), T(("repeat", "size", d)))
    if fam == "F4":
        d1, d2 = (str(x) for x in rng.choice(["N", "S", "E", "W", "NE", "NW", "SE", "SW"], 2, replace=False))
        return ("u", S("centre"), *sorted((T(("ray", d1, "border")), T(("ray", d2, "border")))))
    if fam == "F5":
        return ("d2", S("self"), T(("ring", 8)), T(("shift", "size", d)))
    if fam == "N0":
        return ("d1", S("self"), T(("ring", 8))) if rng.random() < 0.5 else ("d1", S("self"), T(("ray", d, "border")))
    if fam == "S":
        return ("d2", S("self"), T(("hull",)), T(("ring", 8)))
    if fam == "X":                                   # wrong-action control: its rule is applied in _demo
        return ("d1", S("self"), T(("ring", 8)))
    if fam == "U":                                   # truth: border or obstacle ray, 50/50; demos cannot tell
        return ("d1", S(f"edge:{d}"), T(("ray", d, "obstacle" if rng.random() < 0.5 else "border")))
    raise ValueError(fam)


def _shape(rng, n, two_colour, c1, c2):
    cells = {(0, 0)}
    while len(cells) < n:
        r, c = list(cells)[int(rng.integers(len(cells)))]
        dr, dc = ((-1, 0), (1, 0), (0, -1), (0, 1))[int(rng.integers(4))]
        cells.add((r + dr, c + dc))
    cells = sorted(cells)
    col = {p: c1 for p in cells}
    if two_colour:
        col[cells[int(rng.integers(len(cells)))]] = c2   # one minority cell
    return col


def _place(rng, G, shape, gap=2):
    H, W = G.shape
    rs, cs = [r for r, _ in shape], [c for _, c in shape]
    for _ in range(200):
        r0 = int(rng.integers(0, H - (max(rs) - min(rs))))
        c0 = int(rng.integers(0, W - (max(cs) - min(cs))))
        cells = {(r0 + r - min(rs), c0 + c - min(cs)): v for (r, c), v in shape.items()}
        if all(0 <= r < H and 0 <= c < W for r, c in cells) and not (
                G[max(0, min(r for r, _ in cells) - gap):max(r for r, _ in cells) + gap + 1,
                  max(0, min(c for _, c in cells) - gap):max(c for _, c in cells) + gap + 1] != 0).any():
            for p, v in cells.items():
                G[p] = v
            return cells
    return None


def _demo(rng, fam, expr, cols, H, W, want_obstacle=None):
    """One (input, output, growing objects) for the task's rule, or None."""
    grow_col, minor_col, add_col, dis_col = cols
    two = fam in ("D3", "F2")
    G = np.zeros((H, W), int)
    objs = []
    for _ in range(int(rng.integers(1, 3))):
        o = _place(rng, G, _shape(rng, int(rng.integers(2, 6)), two, grow_col, minor_col))
        if o is None:
            return None
        objs.append(o)
    if fam != "X" and rng.random() < 0.5:                          # a distractor that never grows
        if _place(rng, G, _shape(rng, int(rng.integers(2, 5)), False, dis_col, dis_col)) is None:
            return None
    if fam == "X":                                                 # wrong action: recolour by size, no growth
        out = G.copy()
        for o in objs:
            for p in o:
                out[p] = 1 + (len(o) % 9)
        return (G, out, []) if (out != G).any() else None
    added = [GG.evaluate(expr, GG.Ctx(o, G)) for o in objs]
    if any(not a for a in added) or sum(len(a) for a in added) != len(set().union(*added)):
        return None                                                # empty or overlapping growth
    if fam == "U":
        alt = ("d1", expr[1], T(("ray", GG.TRANSFORMS[expr[2]][1],
                                  "border" if GG.TRANSFORMS[expr[2]][2] == "obstacle" else "obstacle")))
        differs = any(GG.evaluate(alt, GG.Ctx(o, G)) != a for o, a in zip(objs, added))
        if differs != bool(want_obstacle):
            return None
    out = G.copy()
    for a in added:
        for p in a:
            out[p] = add_col
    return G, out, list(zip(objs, added))


def make_task(fam, seed):
    from cora_fhr import baseline as BL
    rng = np.random.default_rng(seed)
    for _attempt in range(400):
        expr = family_expr(fam, rng)
        H, W = (int(v) for v in rng.integers(10, 15, size=2))
        grow_col, minor_col, add_col, dis_col = (int(v) for v in rng.choice(np.arange(1, 10), 4, replace=False))
        demos = []
        for k in range(4):
            dm = _demo(rng, fam, expr, (grow_col, minor_col, add_col, dis_col), H, W,
                       want_obstacle=(k == 3) if fam == "U" else None)
            if dm is None:
                break
            demos.append(dm)
        if len(demos) < 4:
            continue
        train_inst = [(o, a, G) for G, _out, grows in demos[:3] for o, a in grows]
        rejected = None
        if fam in G_FAMILIES:
            if any(BL.native_explains(o, a, add_col, G) for o, a, G in train_inst):
                rejected = "native"
            elif BL.reach_setting(train_inst) is not None:
                rejected = "reach"
        elif fam == "N0" and not all(BL.native_explains(o, a, add_col, G) for o, a, G in train_inst):
            rejected = "not_native"
        elif fam == "S" and (any(BL.native_explains(o, a, add_col, G) for o, a, G in train_inst)
                             or BL.reach_setting(train_inst) is None):
            rejected = "not_reach_only"
        if rejected:
            yield {"rejected": rejected}
            continue
        yield {"task": {"family": fam, "seed": seed, "truth": GG.to_str(expr) if fam != "X" else "recolour_by_size",
                        "truth_pretty": GG.pretty(expr) if fam != "X" else "recolour_by_size",
                        "train": [[G.tolist(), out.tolist()] for G, out, _g in demos[:3]],
                        "test": [[demos[3][0].tolist(), demos[3][1].tolist()]]}}
        return


def build(split):
    tasks, rejections = {}, {}
    for fi, (fam, n) in enumerate(sorted(SPLITS[split].items())):
        rej = {}
        for k in range(n):
            seed = SEEDS[split] + 1000 * fi + k
            for res in make_task(fam, seed):
                if "rejected" in res:
                    rej[res["rejected"]] = rej.get(res["rejected"], 0) + 1
                else:
                    tasks[f"{split}_{fam}_{k:02d}"] = res["task"]
        rejections[fam] = rej
    return tasks, rejections


def solver_view(task):
    """What every arm may see: training pairs and test inputs."""
    return {"train": [{"input": a, "output": b} for a, b in task["train"]], "test": [{"input": a} for a, _b in task["test"]]}


def calibrate(n=20):
    """Rejection rate of each final family on calibration seeds (never final tasks)."""
    rates = {}
    for fi, fam in enumerate(("F1", "F2", "F3", "F4", "F5")):
        made, rej = 0, 0
        for k in range(n):
            for res in make_task(fam, SEEDS["calibrate"] + 1000 * fi + k):
                if "rejected" in res:
                    rej += 1
                else:
                    made += 1
        rates[fam] = {"made": made, "rejected_samples": rej, "rejection_rate": round(rej / max(1, rej + made), 3)}
    return rates


def main(argv):
    os.makedirs(OUT, exist_ok=True)
    if argv[0] == "calibrate":
        print(json.dumps(calibrate(), indent=1))
        return
    if argv[0] == "final" and os.environ.get("CORA_FHR_FINAL_FREEZE") != "1":
        sys.exit("the final split is sealed until the freeze (CORA_FHR_FINAL_FREEZE=1)")
    tasks, rejections = build(argv[0])
    text = json.dumps({"split": argv[0], "tasks": tasks, "rejections": rejections}, sort_keys=True)
    path = os.path.join(OUT, f"c4_{argv[0]}.json")
    open(path, "w").write(text)
    sha = hashlib.sha256(text.encode()).hexdigest()
    open(path + ".sha256", "w").write(sha + "\n")
    print(json.dumps({"split": argv[0], "tasks": len(tasks), "rejections": rejections, "sha256": sha}, indent=1))


if __name__ == "__main__":
    main(sys.argv[1:] or ["dev"])
