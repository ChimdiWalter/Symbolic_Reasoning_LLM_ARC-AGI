"""Corpus C3 for cora_rep_growth v0 (plan section 7). Designed after G-rep v0
was committed (6870042). Synthetic and private.

  python -m cora_rep_growth.corpus_c3   -> outputs/rep_growth_v0/corpus.json

Each task: 3 training and 2 held-out demonstrations from one rule. The
held-out outputs are for the evaluator only.

Families:
- M_contain (development): hollow frames, each enclosing a content cell 3
  cells from the frame. Each frame takes the colour of its content. The
  frame and its content are one group under bbox_contains or near3; no
  native view joins them, since S7 joins only up to distance 2.
- M_shape (final): copies of 3-cell shapes in distinct colours. Every copy
  is recoloured to the number of copies of its shape (2-4). The group is
  formed by same_shape.
- M_row (final): single cells in a few rows, 2-3 per row and at least 3
  columns apart. The background between a row's first and last cell becomes
  8. The group is formed by same_row.
- Controls, in both splits with different seeds:
  - C_nat: a global colour swap, expected to be native-solvable, so
    construction must not fire or harm;
  - C_op: each object keeps its cells, which are recoloured by a
    checkerboard on bbox parity, so construction is the wrong action;
  - C_out: cells aligned on the same diagonal are joined along the diagonal
    with 8. Diagonal alignment is not in G-rep v0, so construction should
    not help.

Splits:
- dev: M_contain x 10, C_nat x 5, C_op x 5, C_out x 5 (seeds 8000 and up);
- final: M_shape x 15, M_row x 15, C_nat x 10, C_op x 10, C_out x 10
  (seeds 8500 and up).
"""
import hashlib
import json
import os

import numpy as np

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs", "rep_growth_v0", "corpus.json")
SPLITS = {"dev": {"M_contain": 10, "C_nat": 5, "C_op": 5, "C_out": 5},
          "final": {"M_shape": 15, "M_row": 15, "C_nat": 10, "C_op": 10, "C_out": 10}}
SEED0 = {"dev": 8000, "final": 8500}
SHAPES3 = [((0, 0), (0, 1), (0, 2)), ((0, 0), (1, 0), (2, 0)), ((0, 0), (0, 1), (1, 0)), ((0, 0), (1, 1), (2, 2)),
           ((0, 1), (1, 0), (1, 1))]


def _free(g, cells, gap):
    H, W = g.shape
    for r, c in cells:
        if not (0 <= r < H and 0 <= c < W):
            return False
        if (g[max(0, r - gap):r + gap + 1, max(0, c - gap):c + gap + 1] != 0).any():
            return False
    return True


def _place(rng, g, shape, colour, gap):
    h = max(r for r, _ in shape) + 1
    w = max(c for _, c in shape) + 1
    for _ in range(300):
        r0, c0 = int(rng.integers(0, g.shape[0] - h + 1)), int(rng.integers(0, g.shape[1] - w + 1))
        cells = [(r0 + r, c0 + c) for r, c in shape]
        if _free(g, cells, gap):
            for x in cells:
                g[x] = colour
            return cells
    return None


def _demo(rng, fam, param):
    for _ in range(300):
        if fam == "M_contain":
            g = np.zeros((16, 16), int)
            o = g.copy()
            ok = True
            for _k in range(int(rng.integers(2, 4))):
                fc, cc = (int(x) for x in rng.choice(np.arange(1, 9), 2, replace=False))
                frame = [(r, c) for r in range(7) for c in range(7) if r in (0, 6) or c in (0, 6)]
                cells = _place(rng, g, frame + [(3, 3)], 0, 1)
                if cells is None:
                    ok = False
                    break
                for x in cells[:-1]:
                    g[x] = fc
                    o[x] = cc
                g[cells[-1]] = cc
                o[cells[-1]] = cc
            if not ok:
                continue
        elif fam == "M_shape":
            g = np.zeros((14, 14), int)
            classes = rng.choice(len(SHAPES3), 2, replace=False)
            counts = rng.choice([2, 3, 4], 2, replace=False)
            placed, ok = [], True
            colours = iter(rng.permutation(np.arange(1, 10)))
            for si, n in zip(classes, counts):
                for _k in range(int(n)):
                    col = int(next(colours, 9))
                    cells = _place(rng, g, SHAPES3[int(si)], col, 1)
                    if cells is None:
                        ok = False
                        break
                    placed.append((cells, int(n)))
            if not ok:
                continue
            o = g.copy()
            for cells, n in placed:
                for x in cells:
                    o[x] = n
        elif fam == "M_row":
            g = np.zeros((12, 14), int)
            rows = sorted(rng.choice(np.arange(0, 12, 2), int(rng.integers(2, 4)), replace=False))
            o = g.copy()
            for r in rows:
                n = int(rng.integers(2, 4))
                cols = sorted(rng.choice(np.arange(0, 14), n, replace=False))
                if min(np.diff(cols)) < 3:
                    break
                for c in cols:
                    g[r, c] = int(rng.integers(1, 8))
            else:
                o = g.copy()
                for r in rows:
                    cs = np.nonzero(g[r])[0]
                    for c in range(cs.min(), cs.max() + 1):
                        if g[r, c] == 0:
                            o[r, c] = 8
                if (o == g).all():
                    continue
                return g, o
            continue
        elif fam == "C_nat":
            g = np.zeros((10, 10), int)
            for _k in range(int(rng.integers(2, 4))):
                _place(rng, g, SHAPES3[int(rng.integers(len(SHAPES3)))], int(rng.choice(param)), 1)
            a, b = param
            o = g.copy()
            o[g == a], o[g == b] = b, a
        elif fam == "C_op":
            g = np.zeros((10, 10), int)
            o = g.copy()
            for _k in range(int(rng.integers(2, 4))):
                h, w = int(rng.integers(2, 4)), int(rng.integers(2, 4))
                cells = _place(rng, g, [(r, c) for r in range(h) for c in range(w)], int(rng.integers(1, 8)), 1)
                if cells is None:
                    continue
                r0, c0 = cells[0]
                for (r, c) in cells:
                    o[r, c] = 9 if (r - r0 + c - c0) % 2 else g[r, c]
        else:                                                         # C_out
            g = np.zeros((12, 12), int)
            o = g.copy()
            r0, c0 = int(rng.integers(0, 4)), int(rng.integers(0, 4))
            d = int(rng.integers(4, 7))
            pts = [(r0, c0), (r0 + d, c0 + d)]
            for x in pts:
                g[x] = int(rng.integers(1, 8))
            o = g.copy()
            for t in range(1, d):
                o[r0 + t, c0 + t] = 8
            for _k in range(int(rng.integers(1, 3))):
                _place(rng, g, ((0, 0),), int(rng.integers(1, 8)), 2)
            o = np.where(o == 0, g, o)
        if not (o == g).all():
            return g, o
    raise RuntimeError(fam)


def corpus():
    tasks = []
    for split, fams in SPLITS.items():
        for fi, (fam, n) in enumerate(sorted(fams.items())):
            for s in range(n):
                seed = SEED0[split] + 100 * fi + s
                rng = np.random.default_rng(seed)
                param = tuple(int(x) for x in rng.choice(np.arange(1, 8), 2, replace=False)) if fam == "C_nat" else None
                demos = [_demo(rng, fam, param) for _ in range(5)]
                tasks.append({"id": f"{split}_{fam}_{s:02d}", "split": split, "family": fam, "seed": seed,
                              "train": [[a.tolist(), b.tolist()] for a, b in demos[:3]],
                              "heldout": [[a.tolist(), b.tolist()] for a, b in demos[3:]]})
    return tasks


def main():
    tasks = corpus()
    text = json.dumps({"version": "c3_v0", "splits": SPLITS, "tasks": tasks}, sort_keys=True)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w").write(text)
    print(json.dumps({"tasks": len(tasks), "sha256": hashlib.sha256(text.encode()).hexdigest()}))


if __name__ == "__main__":
    main()
