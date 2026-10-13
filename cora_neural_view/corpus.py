"""CORA-NVG synthetic corpus v0. Synthetic only, no ARC data.

  python -m cora_neural_view.corpus     -> outputs/neural_view_v0/corpus.json

Twelve new rule families. None of the negative-probe or P3 families is
reused. Each family is built to need a different representation:
- a colour layer, where all cells of one colour form one object although
  disconnected;
- a diagonal multicolour object;
- a proximity cluster, where cells one empty cell apart form one object.

The corpus also contains:
- rules with no consistent mapping, so no representation helps and changing
  views is wrong;
- native-solvable controls.

The design target of each family is documentation only and never reaches a
guide.

Each task has 3 training demonstrations and 2 held-out demonstrations from
one rule. The held-out OUTPUTS belong to the evaluator; guides see the
held-out inputs as unlabelled inputs.

Splits are by family: the final families are held out whole.
"""
import hashlib
import json
import os

import numpy as np

DEV = ("d_layer_size", "d_diag_drop", "d_cluster_fill8", "d_noise_cell", "d_colour_swap", "d_row_stripe")
FINAL = ("f_layer_frame", "f_layer_corner", "f_diag_mirror", "f_cluster_frame", "f_noise_shift", "f_colour_cycle")
SEEDS = {"dev": range(7000, 7008), "final": range(7100, 7114)}
DESIGN_TARGET = {"d_layer_size": "colour layer", "f_layer_frame": "colour layer", "f_layer_corner": "colour layer",
                 "d_diag_drop": "diagonal multicolour", "f_diag_mirror": "diagonal multicolour",
                 "d_cluster_fill8": "proximity cluster", "f_cluster_frame": "proximity cluster",
                 "d_noise_cell": "none (no consistent rule)", "f_noise_shift": "none (no consistent rule)",
                 "d_colour_swap": "native control", "f_colour_cycle": "native control", "d_row_stripe": "native control"}
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs", "neural_view_v0", "corpus.json")


def _shape(rng, size):
    """A random 4-connected shape of `size` cells, anchored at (0, 0)."""
    cells = {(0, 0)}
    while len(cells) < size:
        r, c = sorted(cells)[int(rng.integers(len(cells)))]
        dr, dc = [(0, 1), (1, 0), (0, -1), (-1, 0)][int(rng.integers(4))]
        cells.add((r + dr, c + dc))
    mr, mc = min(r for r, _ in cells), min(c for _, c in cells)
    return {(r - mr, c - mc) for r, c in cells}


def _put(rng, g, cells, colour, gap, rows=None, cols=None):
    """Place `cells` (relative) where the box around them, widened by `gap`,
    is empty, so pieces are at least gap + 1 apart (Chebyshev); within an
    optional row or column band. `colour` is an int or a dict cell -> colour."""
    H, W = g.shape
    h, w = max(r for r, _ in cells) + 1, max(c for _, c in cells) + 1
    r_lo, r_hi = rows or (0, H)
    c_lo, c_hi = cols or (0, W)
    for _ in range(300):
        if r_hi - h < r_lo or c_hi - w < c_lo:
            return None
        r0, c0 = int(rng.integers(r_lo, r_hi - h + 1)), int(rng.integers(c_lo, c_hi - w + 1))
        box = g[max(0, r0 - gap):r0 + h + gap, max(0, c0 - gap):c0 + w + gap]
        if (box == 0).all():
            placed = {(r0 + r, c0 + c) for r, c in cells}
            for (r, c), (pr, pc) in zip(sorted(cells), sorted(placed)):
                g[pr, pc] = colour if isinstance(colour, (int, np.integer)) else colour[(r, c)]
            return placed
    return None


def _bbox(cells):
    rs, cs = [r for r, _ in cells], [c for _, c in cells]
    return min(rs), max(rs), min(cs), max(cs)


def _layers(rng, g, colours, n_pieces, piece_sizes, bands=None):
    """Colour layers: each colour as several pieces at least 3 apart, so that
    no connectivity or proximity view joins pieces. Returns colour -> cells."""
    out = {}
    for i, col in enumerate(colours):
        cells = set()
        for _ in range(n_pieces[i]):
            p = _put(rng, g, _shape(rng, int(rng.choice(piece_sizes))), int(col), gap=2,
                     rows=bands[i] if bands else None)
            if p is None:
                return None
            cells |= p
        out[int(col)] = cells
    return out


# Shape templates are sorted tuples, never set literals: a set's iteration order
# can differ between a fresh compile and cached bytecode, and the generator
# must not depend on it.
STAIRS = [((0, 0), (1, 1), (2, 2)), ((0, 2), (1, 1), (2, 0)), ((0, 0), (1, 1), (2, 0)),
          ((0, 0), (1, 1), (2, 2), (3, 1)), ((0, 1), (1, 0), (2, 1), (3, 2))]


def _diag_object(rng):
    """A diagonal multicolour object: cells touch only at corners, with two
    alternating colours, so that same-colour and 4-connected views split it."""
    cells = set(STAIRS[int(rng.integers(len(STAIRS)))])
    c1, c2 = (int(x) for x in rng.choice(np.arange(1, 9), 2, replace=False))
    return cells, {x: (c1 if k % 2 == 0 else c2) for k, x in enumerate(sorted(cells))}


CLUSTERS = [((0, 0), (0, 2), (2, 0)), ((0, 0), (0, 4), (2, 2)), ((0, 0), (0, 2), (2, 0), (2, 2)),
            ((0, 2), (2, 0), (2, 4)), ((0, 0), (2, 0), (2, 2), (4, 0))]


def _cluster(rng):
    """A proximity cluster: single cells exactly one empty cell apart, in
    mixed colours, so that only the proximity view groups them."""
    cells = CLUSTERS[int(rng.integers(len(CLUSTERS)))]
    return set(cells), {x: int(rng.integers(1, 8)) for x in cells}


def _objects(rng, g, n, gap=1):
    objs = []
    for _ in range(n):
        p = _put(rng, g, _shape(rng, int(rng.integers(1, 5))), int(rng.integers(1, 8)), gap=gap)
        if p is None:
            return None
        objs.append(p)
    return objs


def _demo(rng, family, task_param):
    for _ in range(200):
        if family in ("d_layer_size", "f_layer_frame", "f_layer_corner"):
            g = np.zeros((12, 12), int)
            k = 2 if family == "f_layer_frame" else int(rng.integers(2, 4))
            colours = rng.choice(np.arange(1, 9), k, replace=False)
            bands = [(0, 6), (6, 12)] if family == "f_layer_frame" else None
            lay = _layers(rng, g, colours, [int(rng.integers(2, 4)) for _ in range(k)], [1, 1, 2], bands)
            if lay is None:
                continue
            o = g.copy()
            if family == "d_layer_size":
                counts = [len(v) for v in lay.values()]
                if len(set(counts)) < len(counts) or max(counts) > 9:
                    continue
                for col, cells in lay.items():
                    for x in cells:
                        o[x] = len(cells)
            elif family == "f_layer_frame":
                for col, cells in lay.items():
                    r0, r1, c0, c1 = _bbox(cells)
                    if r1 - r0 < 1 or c1 - c0 < 1:
                        break
                    for r in range(r0, r1 + 1):
                        for c in range(c0, c1 + 1):
                            if (r in (r0, r1) or c in (c0, c1)) and g[r, c] == 0:
                                o[r, c] = col
                else:
                    pass
                if any(_bbox(c)[1] - _bbox(c)[0] < 1 or _bbox(c)[3] - _bbox(c)[2] < 1 for c in lay.values()):
                    continue
            else:                                                     # f_layer_corner
                corners = [(_bbox(c)[0], _bbox(c)[2]) for c in lay.values()]
                if len(set(corners)) < len(corners):
                    continue
                for x in corners:
                    o[x] = 9
        elif family in ("d_diag_drop", "f_diag_mirror"):
            g = np.zeros((10, 10), int)
            objs = []
            bands = [(0, 5), (5, 10)] if family == "d_diag_drop" else [(0, 10)] * int(rng.integers(2, 4))
            for b in bands:
                cells, colour = _diag_object(rng)
                p = _put(rng, g, cells, colour, gap=2, cols=b if family == "d_diag_drop" else None,
                         rows=(0, 7) if family == "d_diag_drop" else None)
                if p is None:
                    break
                objs.append(p)
            if len(objs) < len(bands):
                continue
            o = np.zeros_like(g)
            ok = True
            for p in objs:
                r0, r1, c0, c1 = _bbox(p)
                for (r, c) in p:
                    if family == "d_diag_drop":
                        nr, nc = r + (9 - r1), c
                    else:
                        nr, nc = r, c0 + c1 - c
                    if o[nr, nc] != 0:
                        ok = False
                    o[nr, nc] = g[r, c]
            if not ok:
                continue
        elif family in ("d_cluster_fill8", "f_cluster_frame"):
            g = np.zeros((12, 12), int)
            objs = []
            for _ in range(int(rng.integers(2, 4))):
                cells, colour = _cluster(rng)
                p = _put(rng, g, cells, colour, gap=3 if family == "f_cluster_frame" else 2)
                if p is None:
                    break
                objs.append(p)
            if len(objs) < 2:
                continue
            o = g.copy()
            for p in objs:
                r0, r1, c0, c1 = _bbox(p)
                for r in range(r0 - (family == "f_cluster_frame"), r1 + 1 + (family == "f_cluster_frame")):
                    for c in range(c0 - (family == "f_cluster_frame"), c1 + 1 + (family == "f_cluster_frame")):
                        if not (0 <= r < 12 and 0 <= c < 12) or g[r, c] != 0:
                            continue
                        inside = r0 <= r <= r1 and c0 <= c <= c1
                        if (family == "d_cluster_fill8" and inside) or (family == "f_cluster_frame" and not inside):
                            o[r, c] = 8
        elif family in ("d_noise_cell", "f_noise_shift", "d_colour_swap", "f_colour_cycle", "d_row_stripe"):
            g = np.zeros((10, 10), int)
            objs = _objects(rng, g, int(rng.integers(2, 4)))
            if objs is None:
                continue
            o = g.copy()
            if family == "d_noise_cell":
                free = np.argwhere(g == 0)
                r, c = free[int(rng.integers(len(free)))]
                o[r, c] = 9
            elif family == "f_noise_shift":
                p = objs[int(rng.integers(len(objs)))]
                dr, dc = [(-1, 0), (1, 0), (0, -1), (0, 1)][int(rng.integers(4))]
                moved = {(r + dr, c + dc) for r, c in p}
                if any(not (0 <= r < 10 and 0 <= c < 10) for r, c in moved) or \
                        any(g[x] != 0 and x not in p for x in moved):
                    continue
                for x in p:
                    o[x] = 0
                for (r, c) in p:
                    o[r + dr, c + dc] = g[r, c]
            elif family == "d_colour_swap":
                a, b = task_param
                if not ((g == a).any() and (g == b).any()):
                    continue
                o[g == a], o[g == b] = b, a
            elif family == "f_colour_cycle":
                o[g > 0] = g[g > 0] % 8 + 1
            else:                                                     # d_row_stripe
                for p in objs:
                    if min(r for r, _ in p) >= 5:
                        for x in p:
                            o[x] = 5
                if (o == g).all():
                    continue
        else:
            raise ValueError(family)
        if not (o == g).all():
            return g, o
    raise RuntimeError(f"{family}: no demonstration after 200 tries")


def task(family, seed):
    rng = np.random.default_rng(seed)
    param = tuple(int(x) for x in rng.choice(np.arange(1, 8), 2, replace=False)) if family == "d_colour_swap" else None
    demos = [_demo(rng, family, param) for _ in range(5)]
    split = "dev" if family in DEV else "final"
    return {"id": f"{family}_{seed}", "family": family, "split": split, "seed": seed,
            "train": [[a.tolist(), b.tolist()] for a, b in demos[:3]],
            "heldout": [[a.tolist(), b.tolist()] for a, b in demos[3:]]}


def corpus():
    return [task(f, s) for split, fams in (("dev", DEV), ("final", FINAL)) for f in fams for s in SEEDS[split]]


def main():
    tasks = corpus()
    text = json.dumps({"version": "nvg_corpus_v0", "families": {"dev": DEV, "final": FINAL},
                       "seeds": {k: [v.start, v.stop] for k, v in SEEDS.items()},
                       "design_target": DESIGN_TARGET, "tasks": tasks}, sort_keys=True)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w").write(text)
    print(json.dumps({"tasks": len(tasks), "dev": sum(t["split"] == "dev" for t in tasks),
                      "final": sum(t["split"] == "final" for t in tasks),
                      "sha256": hashlib.sha256(text.encode()).hexdigest()}))


if __name__ == "__main__":
    main()
