"""CORA's own synthetic task families for the Neural-CORA pilot (generator ncv1-gen0). No third-party data.

Each family samples one typed hypothesis (`ir.Hypothesis`) and random object scenes. Native `render_program` computes
every output, so every task is execution-validated by construction. Families are split by COMPOSITION:
- TRAIN families use single rules and three two-rule compositions.
- HELD-OUT families pair the same selector and action types in ways never seen in training. Examples: a line drawn
  from objects chosen by size, not colour; a slide applied to one colour, not to everything; new two-rule pairings.
  No held-out family uses a component value class that training lacks, so the test is compositional, not recognition
  of a new symbol.

Scenes:
- 8-12 x 8-12 grids, background 0;
- 3-6 single-coloured objects of 1-4 cells from a fixed shape set;
- no two objects touch, even diagonally, so native's connectivity views agree;
- one 3-colour palette per task, so colour selectors are meaningful.

Degenerate tasks are rejected, so every demonstration and the test change. Each non-trivial selector picks some
objects but not all. In two-rule tasks both rules fire in at least two demonstrations and in the test. A moved
object stays in the grid and overlaps nothing.

The solver sees the demonstrations and the test input only. Test outputs are written to a separate answers file that
only the evaluator reads.
"""
import zlib

import numpy as np

from cora_neural_v1 import interp as I
from cora_neural_v1.ir import Hypothesis, Rule

GEN_VERSION = "ncv1-gen0"
SHAPES = ([(0, 0)], [(0, 0), (0, 1)], [(0, 0), (1, 0)], [(0, 0), (0, 1), (1, 0), (1, 1)], [(0, 0), (0, 1), (0, 2)],
          [(0, 0), (1, 0), (2, 0)], [(0, 0), (1, 0), (1, 1)], [(0, 0), (0, 1), (1, 1)])
SMALL_VECTORS = ((0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (-1, -1), (0, 2), (2, 0), (1, -1), (-1, 1))
DIRS = ("up", "down", "left", "right")
AXES = ("horizontal", "vertical", "both")


def _pal(rng):
    return [int(c) for c in rng.choice(np.arange(1, 10), size=5, replace=False)]   # 3 object colours + 2 targets


def _fam(name, rng, P):
    """The hypothesis of family `name`. P = 5 distinct colours: P[0..2] object colours, P[3..4] fresh targets."""
    a, c2, c3, t1, t2 = P
    k = int(rng.integers(1, 5))                           # a size that the scene generator will guarantee
    v = tuple(int(x) for x in SMALL_VECTORS[int(rng.integers(len(SMALL_VECTORS)))])
    d = DIRS[int(rng.integers(4))]
    ax = AXES[int(rng.integers(3))]
    R = Rule
    table = {
        # ---- TRAIN: single rules
        "T_recolor_by_colour": ((R(("color", a), ("recolor", t1)),), "keep"),
        "T_delete_by_size": ((R(("size", k), ("delete",)),), "keep"),
        "T_translate_by_colour": ((R(("color", a), ("translate",) + v),), "keep"),
        "T_line_by_colour": ((R(("color", a), ("fill_line", ax, t1)),), "keep"),
        "T_recolor_largest": ((R(("size_rank", 0), ("recolor", t1)),), "keep"),
        "T_slide_all": ((R(("true", None), ("slide", d)),), "keep"),
        "T_keep_only_colour": ((R(("color", a), ("keep",)),), "delete"),
        "T_delete_by_colour": ((R(("color", a), ("delete",)),), "keep"),
        # ---- TRAIN: compositions
        "T_recolor_then_delete": ((R(("color", a), ("recolor", t1)), R(("size", k), ("delete",))), "keep"),
        "T_line_then_recolor": ((R(("color", a), ("fill_line", ax, t1)), R(("true", None), ("recolor", t2))), "keep"),
        "T_translate_then_delete": ((R(("color", a), ("translate",) + v), R(("size", k), ("delete",))), "keep"),
        # ---- HELD-OUT: the same component types, new pairings
        "H_line_by_size": ((R(("size", k), ("fill_line", ax, t1)),), "keep"),
        "H_slide_by_colour": ((R(("color", a), ("slide", d)),), "keep"),
        "H_delete_largest": ((R(("size_rank", 0), ("delete",)),), "keep"),
        "H_recolor_then_line": ((R(("color", a), ("recolor", t1)), R(("color", c2), ("fill_line", ax, t2))), "keep"),
        "H_slide_then_recolor": ((R(("color", a), ("slide", d)), R(("true", None), ("recolor", t1))), "keep"),
        "H_delete_then_translate": ((R(("size", k), ("delete",)), R(("color", a), ("translate",) + v)), "keep"),
        "H_line_keep_only": ((R(("color", a), ("fill_line", ax, t1)),), "delete"),
    }
    rules, default = table[name]
    return Hypothesis("S1", rules, default, origin={"generator": GEN_VERSION, "family": name})


TRAIN_FAMILIES = tuple(f for f in ("T_recolor_by_colour", "T_delete_by_size", "T_translate_by_colour",
                                   "T_line_by_colour", "T_recolor_largest", "T_slide_all", "T_keep_only_colour",
                                   "T_delete_by_colour", "T_recolor_then_delete", "T_line_then_recolor",
                                   "T_translate_then_delete"))
HELDOUT_FAMILIES = tuple(f for f in ("H_line_by_size", "H_slide_by_colour", "H_delete_largest", "H_recolor_then_line",
                                     "H_slide_then_recolor", "H_delete_then_translate", "H_line_keep_only"))


def _scene(rng, P, need_size=None):
    """A random grid with 3-6 objects in colours P[0..2]; at least two colours used; objects never touch."""
    H, W = int(rng.integers(8, 13)), int(rng.integers(8, 13))
    G = np.zeros((H, W), dtype=np.int64)
    occ = np.zeros((H + 2, W + 2), dtype=bool)
    n = int(rng.integers(3, 7))
    placed, cols = 0, []
    shapes = list(range(len(SHAPES)))
    for attempt in range(200):
        if placed == n:
            break
        if need_size is not None and placed == 0:
            cand = [i for i in shapes if len(SHAPES[i]) == need_size]
            si = int(rng.choice(cand))
        else:
            si = int(rng.integers(len(SHAPES)))
        sh = SHAPES[si]
        r0, c0 = int(rng.integers(0, H)), int(rng.integers(0, W))
        cells = [(r0 + dr, c0 + dc) for dr, dc in sh]
        if any(r >= H or c >= W for r, c in cells):
            continue
        if any(occ[r:r + 3, c:c + 3].any() for r, c in cells):     # 8-neighbourhood free (occ is padded by 1)
            continue
        col = P[placed % 3] if placed < 3 else P[int(rng.integers(0, 3))]
        for r, c in cells:
            G[r, c] = col
            occ[r + 1, c + 1] = True
        placed += 1
        cols.append(col)
    if placed < 3 or len(set(cols)) < 2:
        return None
    return G


def _objects_s1(G):
    from geocat_arc.object_reasoning.segmentation import segment
    from geocat_arc.object_reasoning.types import SegmentationVariant as V
    from geocat_arc.perception.grid import Grid
    return segment(Grid(np.asarray(G, dtype=np.int32)), V("S1"))


def _moves_clean(h, A):
    """Movement rules may not clip or merge objects. Replay only the movements (every other action becomes keep,
    with the default kept); the non-background cell count must be unchanged."""
    if not any(r.action[0] in ("translate", "slide") for r in h.rules):
        return True
    moves = tuple(r if r.action[0] in ("translate", "slide") else Rule(r.selector, ("keep",)) for r in h.rules)
    out = I.run(Hypothesis(h.variant, moves, "keep"), A)
    return out is not None and int((out != 0).sum()) == int((np.asarray(A) != 0).sum())


def make_task(family, seed, n_train=3):
    """One execution-validated task, or None if the family could not be realized from this seed."""
    rng = np.random.default_rng([zlib.crc32(family.encode()), seed])
    P = _pal(rng)
    h = _fam(family, rng, P)
    need = None
    for r in h.rules:
        if r.selector[0] == "size":
            need = r.selector[1]
    pairs = []
    tries = 0
    while len(pairs) < n_train + 1 and tries < 80:
        tries += 1
        G = _scene(rng, P, need_size=need)
        if G is None:
            continue
        out = I.run(h, G)
        if out is None or np.array_equal(out, G) or not _moves_clean(h, G):
            continue
        if not _rules_fire(h, G):
            continue
        pairs.append((G.tolist(), out.tolist()))
    if len(pairs) < n_train + 1:
        return None
    return {"task_id": f"{family}_{seed}", "family": family, "generator": GEN_VERSION, "seed": int(seed),
            "train": pairs[:n_train], "test": pairs[n_train:], "program": h.to_dict()}


def _rules_fire(h, G):
    """Every rule must change the grid here: removing it from the program changes the output."""
    base = I.run(h, G)
    if base is None:
        return False
    if len(h.rules) == 1:
        sel = h.rules[0].selector
        if sel[0] == "true":
            return True
        # the selector must not select everything when the default keeps the rest (otherwise 'true' is an alias)
        alt = Hypothesis(h.variant, (Rule(("true", None), h.rules[0].action),), h.default)
        out_true = I.run(alt, G)
        return out_true is None or not np.array_equal(out_true, base)
    for i in range(len(h.rules)):
        rest = tuple(r for j, r in enumerate(h.rules) if j != i)
        alt = Hypothesis(h.variant, rest, h.default)
        out = I.run(alt, G)
        if out is not None and np.array_equal(out, base):
            return False
    return True
