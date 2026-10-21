"""syn-v4: the versioned, execution-verified synthetic generator for the ncv2-g4 study
(records/NEURAL_CORA_V2G4_PROTOCOL_20261021.md). Evaluation side only: no solver imports this module.

**Three executors make the expected outputs**, so the set is not only g4's own language:
- `g4`: the g4 executor (cora_neural_v2g4.program), for part, region, ray and mixed programs. A mixed program's base is
  a native ncv2 program, run by native CORA inside the g4 executor;
- `native`: native CORA (ncv2-g2 grammar, cora_neural_v2g2.grammar.execute), for whole-object controls and for the
  native generative operations (fill_interior, ray_until_obstacle, halo, fixed-length rays). Where g4 can express a
  native family, `PARITY` names the g4 program that should reproduce it, and prepare reports how often it does;
- `custom`: plain Python in this file, for changes that neither language is designed to express (gravity, a
  checkerboard of interior cells, a top-left marker).

**Separation before augmentation.** DEV and HELDOUT families differ by semantics (part kind, region, direction set,
stop rule, executor or operation), never only by seed. Augmentation (colours, shapes, counts, placement) lives in the
scenes. No program here is an ncv2-g2 or syn-v3 family program; the freeze also checks the tasks against both pools
by grid hash.

**Groups:** part, region, ray, mixed (the g4 targets); control (whole-object native programs, regression);
beyond (outside the g4 construction languages, to count false fits); trap (a memorizer from ncv2-g2's own generators
also fits and mispredicts, certified with syn-v3's helper); ambiguity (an alternative g4 program fits and disagrees,
certified by execution).

**Certification at generation:** every component of a multi-component program is necessary (dropping the base or any
rule breaks the fit); every demonstration and the test change some cell; trap and ambiguity families are certified as
above. A seed that cannot produce a certified task within the tries is recorded as missing at freeze and is never
replaced.

All families are written by the same author as g4. Gains on them are evidence about the designed languages, not about
real ARC tasks. HELDOUT families are for the frozen protocol only: do not run solvers on, tune on or inspect them
before the protocol is authorized.
"""
import zlib

import numpy as np

from cora_neural_v2.rast import N
from cora_neural_v2g2 import families as F2
from cora_neural_v2g2 import grammar as G
from cora_neural_v2g3 import families_v3 as V
from cora_neural_v2g4 import program as PG

VERSION = "syn-v4"
P = F2.P
SHAPES = dict(V.SHAPES,
              block9=[(r, c) for r in range(3) for c in range(3)],
              block12=[(r, c) for r in range(3) for c in range(4)],
              block15=[(r, c) for r in range(3) for c in range(5)],
              block16=[(r, c) for r in range(4) for c in range(4)],
              ring16=[(r, c) for r in range(4) for c in range(4) if r in (0, 3) or c in (0, 3)],
              cup=[(0, 0), (0, 2), (1, 0), (1, 1), (1, 2)],
              ell5=[(0, 0), (1, 0), (2, 0), (2, 1), (2, 2)],
              hbar5=[(0, c) for c in range(5)], vbar5=[(r, 0) for r in range(5)])
BLOCKS = ("block9", "block12", "block15", "block16")
SMALL = ("dot", "domino", "ell", "tee")
DIAG = ((1, 1), (1, -1), (-1, 1), (-1, -1))
L, R_, D_, U = (0, -1), (0, 1), (1, 0), (-1, 0)


def T(f, cmp, v):
    return N("test", (f, cmp, v))


TRUE = N("true", ())


def g4(rules, base=None, view="S1"):
    return PG.make(view, G.parse(P(base)) if base else None, rules)


def generative(kind, sel, gps):
    g = " ".join(f"(gp {k} {v})" for k, v in gps)
    return G.parse(f"(generative S1 (list (gen (gsel (list {sel})) (grule {kind} (list {g})))) over_input 0 #f none)")


# ------------------------------------------------------------------ scenes (augmentation lives here)
def parts(rng, spec, size):
    G_ = np.zeros(size, dtype=np.int64)
    for shape, colour in spec:
        if not F2._place(rng, G_, SHAPES[shape], colour):
            return None
    return G_


def _cols(rng, k, exclude=()):
    return [int(c) for c in rng.permutation([c for c in range(1, 10) if c not in exclude])[:k]]


def _pick(rng, names, k):
    return [str(s) for s in rng.choice(list(names), size=k)]


def _shuffle(rng, spec):
    return [spec[i] for i in rng.permutation(len(spec))]


def scene_blocks_small_plus(rng, role="demo"):
    c = _cols(rng, 4)
    spec = [(b, c[i]) for i, b in enumerate(_pick(rng, BLOCKS, 2))] + [("plus", c[2])] + \
        [(s, c[3]) for s in _pick(rng, SMALL, int(rng.integers(1, 3)))]
    return parts(rng, _shuffle(rng, spec), (14, 14))


def scene_blocks_concave(rng, role="demo"):
    c = _cols(rng, 4)
    spec = [(b, c[i]) for i, b in enumerate(_pick(rng, BLOCKS, 2))] + \
        [(s, c[2 + i % 2]) for i, s in enumerate(_pick(rng, ("ell5", "tee", "plus", "cup"), 2))]
    return parts(rng, _shuffle(rng, spec), (14, 14))


def scene_three_block_sizes(rng, role="demo"):
    c = _cols(rng, 4)
    spec = [("block9", c[0]), ("block12", c[1]), ("block16", c[2])] + [(s, c[3]) for s in _pick(rng, SMALL, 1)]
    return parts(rng, _shuffle(rng, spec), (15, 15))


def scene_rings_two_sizes(rng, role="demo"):
    c = _cols(rng, 4)
    spec = [("ring", c[0]), ("ring16", c[1])] + [(str(rng.choice(["ring", "ring16"])), c[2])] * int(rng.integers(0, 2)) + \
        [(s, c[3]) for s in _pick(rng, ("dot", "domino", "ell", "block9"), int(rng.integers(1, 3)))]
    return parts(rng, _shuffle(rng, spec), (14, 14))


def scene_concave_rings_blocks(rng, role="demo"):
    c = _cols(rng, 4)
    spec = [(s, c[i % 2]) for i, s in enumerate(_pick(rng, ("cup", "ell5", "tee", "ell"), 2))] + \
        [("ring", c[2]), (str(rng.choice(["block9", "square"])), c[3])]
    return parts(rng, _shuffle(rng, spec), (13, 13))


def scene_colour3_rings(rng, role="demo"):
    c = _cols(rng, 2, exclude=(3,))
    spec = [("ring", 3), (str(rng.choice(["ring", "ring16"])), c[0])] + \
        [(s, c[1]) for s in _pick(rng, ("dot", "domino", "ell", "tee"), int(rng.integers(1, 3)))]
    return parts(rng, _shuffle(rng, spec), (13, 13))


def scene_dots_and_blocks(rng, role="demo"):
    c = _cols(rng, 3)
    spec = [("dot", c[i % 2]) for i in range(int(rng.integers(2, 5)))] + [(b, c[2]) for b in _pick(rng, ("block9", "block12", "square"), int(rng.integers(1, 3)))]
    return parts(rng, _shuffle(rng, spec), (13, 13))


def scene_dots_and_blobs(rng, role="demo"):
    c = _cols(rng, 3)
    spec = [("dot", c[i % 2]) for i in range(int(rng.integers(2, 4)))] + [(s, c[2]) for s in _pick(rng, ("ell", "tee", "square", "ring"), 2)]
    return parts(rng, _shuffle(rng, spec), (13, 13))


def scene_colour6_dots(rng, role="demo"):
    c = _cols(rng, 2, exclude=(6,))
    spec = [("dot", 6)] * int(rng.integers(2, 4)) + [("dot", c[0])] * int(rng.integers(1, 3)) + \
        [(b, c[1]) for b in _pick(rng, ("block9", "square", "vbar3"), int(rng.integers(1, 3)))]
    return parts(rng, _shuffle(rng, spec), (13, 13))


def scene_dots_rings_blob(rng, role="demo"):
    c = _cols(rng, 3)
    spec = [("dot", c[0])] * int(rng.integers(1, 3)) + [("ring", c[1])] * int(rng.integers(1, 3)) + [(str(rng.choice(["ell", "tee"])), c[2])]
    return parts(rng, _shuffle(rng, spec), (13, 13))


def scene_lines_blocks(rng, role="demo"):
    c = _cols(rng, 3)
    spec = [(s, c[0]) for s in _pick(rng, ("hbar3", "vbar3", "hbar4"), int(rng.integers(1, 3)))] + \
        [(b, c[1]) for b in _pick(rng, ("block9", "block12"), int(rng.integers(1, 3)))] + [(str(rng.choice(["ell", "tee"])), c[2])]
    return parts(rng, _shuffle(rng, spec), (14, 14))


def scene_colour2_small(rng, role="demo"):
    c = _cols(rng, 2, exclude=(2, 1))
    spec = [(s, 2) for s in _pick(rng, ("dot", "domino"), int(rng.integers(1, 3)))] + \
        [(s, c[i % 2]) for i, s in enumerate(_pick(rng, ("dot", "ell", "square", "hbar3"), 2))]
    return parts(rng, _shuffle(rng, spec), (12, 12))


def scene_falling(rng, role="demo"):
    c = _cols(rng, 4)
    spec = [(s, c[i]) for i, s in enumerate(_pick(rng, ("dot", "domino", "ell", "square", "hbar3", "tee"), int(rng.integers(3, 5))))]
    return parts(rng, spec, (10, 10))


def scene_blocks_and_small(rng, role="demo"):
    c = _cols(rng, 3)
    spec = [(b, c[i]) for i, b in enumerate(_pick(rng, BLOCKS, 2))] + [(s, c[2]) for s in _pick(rng, SMALL, int(rng.integers(1, 3)))]
    return parts(rng, _shuffle(rng, spec), (14, 14))


def scene_trap_interior(rng, role="demo"):
    """Demonstrations: blocks and small objects, no plus. Test: a block, a plus (its centre has four neighbours)."""
    c = _cols(rng, 4)
    spec = [(b, c[i]) for i, b in enumerate(_pick(rng, BLOCKS, 2 if role == "demo" else 1))] + \
        [(s, c[2]) for s in _pick(rng, ("dot", "domino", "square"), int(rng.integers(1, 3)))]
    if role == "test":
        spec.append(("plus", c[3]))
    return parts(rng, _shuffle(rng, spec), (14, 14))


def scene_trap_corners(rng, role="demo"):
    """Demonstrations: blocks, dots and dominoes (no cell outside a block has two neighbours). Test: adds a bar."""
    c = _cols(rng, 4)
    spec = [(b, c[i]) for i, b in enumerate(_pick(rng, BLOCKS, 2 if role == "demo" else 1))] + \
        [(s, c[2]) for s in _pick(rng, ("dot", "domino"), int(rng.integers(1, 3)))]
    if role == "test":
        spec.append((str(rng.choice(["hbar4", "vbar4", "hbar5"])), c[3]))
    return parts(rng, _shuffle(rng, spec), (14, 14))


def scene_amb_dominoes(rng, role="demo"):
    """Demonstrations: the only lines are dominoes, and no other object has size 2. Test: adds a longer bar."""
    c = _cols(rng, 3)
    spec = [("domino", c[0])] * int(rng.integers(1, 3)) + [(s, c[1]) for s in _pick(rng, ("ell", "tee", "square", "ring"), 2)]
    if role == "test":
        spec.append((str(rng.choice(["hbar3", "vbar4", "hbar4"])), c[2]))
    return parts(rng, _shuffle(rng, spec), (13, 13))


def scene_amb_rings(rng, role="demo"):
    """Demonstrations: rings and convex objects only (holes = bounding-box background). Test: adds a concave object."""
    c = _cols(rng, 3)
    spec = [("ring", c[0])] * int(rng.integers(1, 3)) + [(s, c[1]) for s in _pick(rng, ("block9", "square", "dot", "hbar3"), 2)]
    if role == "test":
        spec.append((str(rng.choice(["cup", "ell5", "tee"])), c[2]))
    return parts(rng, _shuffle(rng, spec), (13, 13))


def scene_amb_thin(rng, role="demo"):
    """Demonstrations: thin objects only (border = whole). Test: adds a block with an interior."""
    c = _cols(rng, 3)
    spec = [(s, c[i % 2]) for i, s in enumerate(_pick(rng, ("dot", "domino", "hbar3", "vbar3", "ell"), int(rng.integers(3, 5))))]
    if role == "test":
        spec.append((str(rng.choice(["block9", "block12"])), c[2]))
    return parts(rng, _shuffle(rng, spec), (13, 13))


def scene_assorted(rng, role="demo"):
    return V.scene_assorted(rng, role)


# ------------------------------------------------------------------ custom executors (outside both languages)
def _components(A, bg=0):
    """4-connected single-colour components: [(colour, [cells])], in reading order."""
    seen = np.zeros(A.shape, dtype=bool)
    out = []
    for r0, c0 in zip(*np.nonzero(A != bg)):
        if seen[r0, c0]:
            continue
        k, stack, cells = A[r0, c0], [(r0, c0)], []
        seen[r0, c0] = True
        while stack:
            r, c = stack.pop()
            cells.append((int(r), int(c)))
            for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                rr, cc = r + dr, c + dc
                if 0 <= rr < A.shape[0] and 0 <= cc < A.shape[1] and not seen[rr, cc] and A[rr, cc] == k:
                    seen[rr, cc] = True
                    stack.append((rr, cc))
        out.append((int(k), cells))
    return out


def gravity_down(grid):
    """Every object falls straight down until it meets the bottom edge or another object (lowest objects first)."""
    A = np.asarray(grid)
    out = np.zeros_like(A)
    h = A.shape[0]
    for k, cells in sorted(_components(A), key=lambda kc: -max(r for r, _ in kc[1])):
        d = 0
        while all(r + d + 1 < h and out[r + d + 1, c] == 0 for r, c in cells):
            d += 1
        for r, c in cells:
            out[r + d, c] = k
    return out


def checker_interior(grid):
    """Interior cells (all four neighbours in the object) on even (row + column) become background."""
    A = np.asarray(grid)
    out = A.copy()
    for k, cells in _components(A):
        s = set(cells)
        for r, c in cells:
            if (r + c) % 2 == 0 and all((r + dr, c + dc) in s for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0))):
                out[r, c] = 0
    return out


def top_left_marker(grid):
    """The first cell (reading order) of every object becomes colour 1 (objects of colour 1 keep it)."""
    A = np.asarray(grid)
    out = A.copy()
    for k, cells in _components(A):
        r, c = min(cells)
        out[r, c] = 1
    return out


# ------------------------------------------------------------------ families
# name -> (split, group, executor kind, program, scene, extra): extra is None, "trap", or ("alt", g4 program)
FAMILIES = {
    # ---- DEV (development and unit tests; may be run and inspected) ----
    "v4d_part_border_all": ("dev", "part", "g4", g4([PG.PartRule(TRUE, "border", 5)]), scene_blocks_and_small, None),
    "v4d_part_endpoints_lines": ("dev", "part", "g4", g4([PG.PartRule(T("is_line", "==", True), "endpoints", 8)]), scene_lines_blocks, None),
    "v4d_reg_holes_own": ("dev", "region", "g4", g4([PG.PartRule(TRUE, "holes", "own")]), scene_rings_two_sizes, None),
    "v4d_ray_right_dots": ("dev", "ray", "g4", g4([PG.RayRule(T("size", "==", 1), (R_,), "obstacle", "own")]), scene_dots_and_blocks, None),
    "v4d_mix_recolour_then_interior": ("dev", "mixed", "g4", g4([PG.PartRule(T("size", ">=", 9), "interior", 2)],
                                                                 "(rule (test has_hole == #t) (recolor (color 6)))"), scene_concave_rings_blocks, None),
    "v4d_ctrl_holeless_recolour": ("dev", "control", "native", G.parse(P("(rule (test has_hole == #f) (recolor (color 7)))")), scene_rings_two_sizes, None),
    "v4d_beyond_top_left_custom": ("dev", "beyond", "custom", top_left_marker, scene_blocks_and_small, None),
    "v4d_trap_interior_size": ("dev", "trap", "g4", g4([PG.PartRule(T("size", ">=", 9), "interior", 1)]), scene_trap_interior, "trap"),
    "v4d_amb_border_or_whole": ("dev", "ambiguity", "g4", g4([PG.PartRule(TRUE, "border", 5)]), scene_amb_thin,
                                ("alt", g4([PG.PartRule(TRUE, "whole", 5)]))),
    # ---- HELDOUT (the frozen protocol only) ----
    "v4h_part_interior_large": ("heldout", "part", "g4", g4([PG.PartRule(T("size", ">=", 9), "interior", 2)]), scene_blocks_small_plus, None),
    "v4h_part_corners_rect": ("heldout", "part", "g4", g4([PG.PartRule(T("is_rectangle", "==", True), "corners", 4)]), scene_blocks_concave, None),
    "v4h_part_hollow_largest": ("heldout", "part", "g4", g4([PG.PartRule(T("size_rank", "==", 0), "interior", 0)]), scene_three_block_sizes, None),
    "v4h_reg_holes_big_rings": ("heldout", "region", "g4", g4([PG.PartRule(T("size", ">=", 12), "holes", 3)]), scene_rings_two_sizes, None),
    "v4h_reg_bbox_concave": ("heldout", "region", "g4", g4([PG.PartRule(T("has_hole", "==", False), "bbox_background", 7)]), scene_concave_rings_blocks, None),
    "v4h_reg_fill_interior_native": ("heldout", "region", "native", generative("fill_interior", "(sel_color 3)", [("color", 4)]), scene_colour3_rings, None),
    "v4h_ray_down_dots_own": ("heldout", "ray", "g4", g4([PG.RayRule(T("size", "==", 1), (D_,), "obstacle", "own")]), scene_dots_and_blocks, None),
    "v4h_ray_diagonal_through": ("heldout", "ray", "g4", g4([PG.RayRule(T("size", "==", 1), DIAG, "through", 5)]), scene_dots_and_blobs, None),
    "v4h_ray_left_until_obstacle_native": ("heldout", "ray", "native", generative("ray_until_obstacle", "(sel_color 6)", [("direction", "left")]), scene_colour6_dots, None),
    "v4h_mix_move_then_holes": ("heldout", "mixed", "g4", g4([PG.PartRule(T("has_hole", "==", True), "holes", 3)],
                                                             "(rule (test size == 1) (translate (vec 0 1)))"), scene_dots_rings_blob, None),
    "v4h_mix_delete_then_corners": ("heldout", "mixed", "g4", g4([PG.PartRule(T("size", ">=", 9), "corners", 8)],
                                                                 "(rule (test is_line == #t) (delete))"), scene_lines_blocks, None),
    "v4h_ctrl_rect_delete": ("heldout", "control", "native", G.parse(P("(rule (test is_rectangle == #t) (delete))")), scene_assorted, None),
    "v4h_ctrl_size3_recolour": ("heldout", "control", "native", G.parse(P("(rule (test size == 3) (recolor (color 9)))")), scene_assorted, None),
    "v4h_beyond_halo_native": ("heldout", "beyond", "native", generative("halo", "(sel_color 2)", [("color", 1)]), scene_colour2_small, None),
    "v4h_beyond_ray_length2_native": ("heldout", "beyond", "native", generative("ray", "(sel_color 2)", [("direction", "right"), ("length", 2)]), scene_colour2_small, None),
    "v4h_beyond_gravity_custom": ("heldout", "beyond", "custom", gravity_down, scene_falling, None),
    "v4h_beyond_checker_custom": ("heldout", "beyond", "custom", checker_interior, scene_blocks_and_small, None),
    "v4h_trap_interior_rect": ("heldout", "trap", "g4", g4([PG.PartRule(T("is_rectangle", "==", True), "interior", 1)]), scene_trap_interior, "trap"),
    "v4h_trap_corners_large": ("heldout", "trap", "g4", g4([PG.PartRule(T("size", ">=", 9), "corners", 5)]), scene_trap_corners, "trap"),
    "v4h_amb_endpoints_or_whole": ("heldout", "ambiguity", "g4", g4([PG.PartRule(T("is_line", "==", True), "endpoints", 6)]), scene_amb_dominoes,
                                   ("alt", g4([PG.PartRule(T("size", "==", 2), "whole", 6)]))),
    "v4h_amb_holes_or_bbox": ("heldout", "ambiguity", "g4", g4([PG.PartRule(TRUE, "holes", 3)]), scene_amb_rings,
                              ("alt", g4([PG.PartRule(TRUE, "bbox_background", 3)]))),
}

# native families that g4 can express: the g4 program that should reproduce the native outputs (reported by prepare)
PARITY = {
    "v4h_reg_fill_interior_native": g4([PG.PartRule(T("color", "==", 3), "holes", 4)]),
    "v4h_ray_left_until_obstacle_native": g4([PG.RayRule(T("color", "==", 6), (L,), "obstacle", "own")]),
}


def run(kind, prog, grid):
    """The output of a family program on a grid (numpy), or None."""
    try:
        if kind == "g4":
            out = PG.execute(prog, grid)
        elif kind == "native":
            out = G.execute(prog, grid)
        else:
            out = prog(np.asarray(grid))
    except Exception:                                              # noqa: BLE001 (no output)
        return None
    return None if out is None else np.asarray(out)


def _fits(kind, prog, train):
    for a, b in train:
        out = run(kind, prog, a)
        if out is None or out.shape != np.asarray(b).shape or not np.array_equal(out, b):
            return False
    return True


def certify_necessary(task, kind, prog):
    """Every component of a multi-component program is needed: dropping the base or any rule breaks the fit."""
    if kind == "native":
        return V.certify_necessary(task, prog)
    if kind != "g4":
        return True
    parts_ = ([PG.make(prog.view, None, prog.rules)] if prog.base is not None and prog.rules else []) + \
        [PG.make(prog.view, prog.base, prog.rules[:i] + prog.rules[i + 1:]) for i in range(len(prog.rules))
         if len(prog.rules) + (prog.base is not None) > 1]
    return not any(_fits("g4", p, task["train"]) for p in parts_)


def certify_alt(task, answer, alt):
    if not _fits("g4", alt, task["train"]):
        return False
    p = run("g4", alt, task["test_inputs"][0])
    return p is not None and not (p.shape == answer.shape and np.array_equal(p, answer))


def make_task(name, seed, n_demos=3, task_tries=25, pair_tries=200):
    """(task, expected test output) or None; deterministic in (VERSION, name, seed)."""
    split, group, kind, prog, scene, extra = FAMILIES[name]
    rng = np.random.default_rng(zlib.crc32(f"{VERSION}|{name}|{seed}".encode()))
    multi = kind == "g4" and len(prog.rules) + (prog.base is not None) > 1 or \
        kind == "native" and prog.op == "program" and len(prog.args[1]) > 1
    for _ in range(task_tries if (extra or multi) else 1):
        pairs = []
        for role in ["demo"] * n_demos + ["test"]:
            for _ in range(pair_tries):
                g = scene(rng, role)
                if g is None:
                    continue
                out = run(kind, prog, g.tolist())
                if out is None or (out.shape == g.shape and np.array_equal(out, g)):
                    continue
                pairs.append((g.tolist(), out.tolist()))
                break
        if len(pairs) < n_demos + 1:
            continue
        task = {"task_id": f"{VERSION}:{name}#{seed}", "family": name, "group": group,
                "train": pairs[:-1], "test_inputs": [pairs[-1][0]]}
        answer = np.asarray(pairs[-1][1])
        if multi and not certify_necessary(task, kind, prog):
            continue
        if extra == "trap" and not V.certify_trap(task, answer):
            continue
        if isinstance(extra, tuple) and not certify_alt(task, answer, extra[1]):
            continue
        return task, answer
    return None


def names(split, group=None):
    return [k for k, v in FAMILIES.items() if v[0] == split and (group is None or v[1] == group)]


def alternative(name):
    """The alternative g4 program of an ambiguity family, or None."""
    extra = FAMILIES[name][5]
    return extra[1] if isinstance(extra, tuple) else None


def parity(name, task, answer):
    """For a native family g4 can express: whether PARITY's g4 program reproduces every output (demonstrations and
    test), or None."""
    if name not in PARITY:
        return None
    pairs = list(task["train"]) + [(task["test_inputs"][0], answer.tolist())]
    return _fits("g4", PARITY[name], pairs)
