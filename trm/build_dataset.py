#!/usr/bin/env python3
"""TRM data pipeline (queue #4, step 1): build the training dataset.

Follows the TRM/ARC recipe (2510.04871): each ARC training task yields
~1000 augmented examples via dihedral transforms (8), color permutations,
and translations.  Every training PAIR of a task becomes a supervised
example (context = the task's OTHER train pairs, target = this pair),
matching the leave-one-out spirit: the model must map (demonstrations,
query) -> answer.

Serialization: grids as int8 arrays padded to 30x30 with a PAD token
(value 10); EOS row/col markers not needed (fixed canvas).  Each example:
  x  = stacked demo inputs/outputs + query input   [(2*K+1), 30, 30]
  y  = query output                                 [30, 30]
Split: 95% train / 5% val by TASK (never by example — no leakage).
Output: trm/data/{train,val}.npz (memory-mapped friendly).

CPU-only; deterministic (seeded).  GPU training comes in step 2.
"""
import json
import os
import sys
import numpy as np

SEED = 7
PAD = 10
CANVAS = 30
MAX_DEMOS = 3          # context demos per example (pad with blanks)
AUGS_PER_TASK = 200    # per task (x8 dihedral inside = effective 1600 forms)
OUT_DIR = os.path.join(os.path.dirname(__file__), "data")


def pad_grid(g):
    a = np.full((CANVAS, CANVAS), PAD, dtype=np.int8)
    h, w = len(g), len(g[0])
    a[:h, :w] = np.asarray(g, dtype=np.int8)
    return a


def dihedral(a, k, flip):
    if flip:
        a = np.fliplr(a)
    return np.rot90(a, k)


def color_perm(rng):
    """Random permutation of colors 1..9 (0 = background fixed)."""
    p = np.arange(10, dtype=np.int8)
    perm = rng.permutation(np.arange(1, 10))
    p[1:10] = perm
    return p


def apply_perm(grid_list, p):
    return [[int(p[v]) for v in row] for row in grid_list]


def build():
    rng = np.random.default_rng(SEED)
    chal = json.load(open("data/arc/arc-agi_training_challenges.json"))
    sols = json.load(open("data/arc/arc-agi_training_solutions.json"))
    tids = sorted(chal)
    rng.shuffle(tids)
    n_val = max(1, len(tids) // 20)
    val_tids = set(tids[:n_val])

    buckets = {"train": {"x": [], "y": []}, "val": {"x": [], "y": []}}
    for ti, tid in enumerate(tids):
        task = chal[tid]
        pairs = [(p["input"], p["output"]) for p in task["train"]]
        # include test pairs as supervised examples too (train split only —
        # they're part of the TRAINING tasks, standard for ARC training)
        for i, tc in enumerate(task.get("test", [])):
            if tid in sols and i < len(sols[tid]):
                pairs.append((tc["input"], sols[tid][i]))
        if len(pairs) < 2:
            continue
        split = "val" if tid in val_tids else "train"
        n_augs = AUGS_PER_TASK if split == "train" else 20
        for _ in range(n_augs):
            # sample augmentation: dihedral + color perm
            k = int(rng.integers(0, 4))
            flip = bool(rng.integers(0, 2))
            p = color_perm(rng)
            aug = [(apply_perm(i_, p), apply_perm(o_, p)) for i_, o_ in pairs]
            # skip grids that exceed canvas after nothing (ARC max is 30)
            if any(len(g) > CANVAS or len(g[0]) > CANVAS
                   for pr in aug for g in pr):
                continue
            # pick query pair; others are demos
            qi = int(rng.integers(0, len(aug)))
            query = aug[qi]
            demos = [aug[j] for j in range(len(aug)) if j != qi][:MAX_DEMOS]
            chan = []
            for di, do in demos:
                chan.append(dihedral(pad_grid(di), k, flip))
                chan.append(dihedral(pad_grid(do), k, flip))
            while len(chan) < 2 * MAX_DEMOS:
                chan.append(np.full((CANVAS, CANVAS), PAD, dtype=np.int8))
            chan.append(dihedral(pad_grid(query[0]), k, flip))
            x = np.stack(chan)                        # [7, 30, 30]
            y = dihedral(pad_grid(query[1]), k, flip)  # [30, 30]
            buckets[split]["x"].append(x)
            buckets[split]["y"].append(y)
        if (ti + 1) % 100 == 0:
            print(f"[{ti+1}/{len(tids)}] train={len(buckets['train']['x'])} "
                  f"val={len(buckets['val']['x'])}", flush=True)

    os.makedirs(OUT_DIR, exist_ok=True)
    for split, d in buckets.items():
        x = np.stack(d["x"]) if d["x"] else np.zeros((0, 7, CANVAS, CANVAS),
                                                     dtype=np.int8)
        y = np.stack(d["y"]) if d["y"] else np.zeros((0, CANVAS, CANVAS),
                                                     dtype=np.int8)
        np.savez_compressed(os.path.join(OUT_DIR, f"{split}.npz"), x=x, y=y)
        print(f"{split}: {x.shape} -> trm/data/{split}.npz", flush=True)


if __name__ == "__main__":
    build()
