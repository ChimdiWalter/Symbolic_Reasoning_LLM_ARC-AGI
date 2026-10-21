"""syn-v3: a fresh, versioned, execution-verified synthetic generator for the next ncv2-g3 experiment.

**Separation before augmentation.** Families are split into DEV and HELDOUT by their SEMANTICS (the generating
program), before any augmentation. Augmentation (scene seeds, object counts, grid placement) happens only inside a
family, so no HELDOUT semantics is ever seen in development. None of the 20 ncv2-g2 families (DEV or the spent
HELDOUT ten) and none of the v1 compositions is reused; the freeze stage of the runner checks the tasks against the
ncv2-g2 pool by hash.

**Mechanism groups** (each family belongs to one):
- composition: 2- and 3-rule programs whose rules explain disjoint change groups;
- binding: relational references (nearest / unique / largest) and bound composites;
- trap: the generating program is relational, and the task is kept only if some MEMORIZING candidate (a native pixel
  rule, an induced feature map or colour map, from ncv2-g2's own generators) also fits the demonstrations but
  mispredicts the test. This measures hypothesis selection under a known overfitting trap;
- ambiguity: an alternative simple program also fits the demonstrations and disagrees on the test (certified by
  execution). This measures whether two attempts cover both readings;
- additive: rules that add cells (copies, fill lines), alone or composed, since additive change dominates 7 of 40
  real tasks in the finished real-ARC check (records/NEURAL_CORA_V2G2_REALARC_REPORT_20261020.md, section 4);
- control: single-rule programs that ncv2-g2 already handles, for wrong-answer regressions.

Multi-rule tasks are kept only if every rule is necessary (dropping any rule breaks the fit), so a "composition" task is
never secretly single-rule.

All families are written by the same author as the generator and the solver: gains on them are evidence about the
designed grammar, not about real ARC tasks. HELDOUT families are for the frozen protocol only: do not run, tune on
or inspect them before it is authorized.
"""
import zlib

import numpy as np

from cora_neural_v2.rast import N
from cora_neural_v2g2 import families as F2
from cora_neural_v2g2 import grammar as G

VERSION = "syn-v3"
P = F2.P
SHAPES = dict(F2.SHAPES, block8=[(r, c) for r in range(2) for c in range(4)], plus=[(0, 1), (1, 0), (1, 1), (1, 2), (2, 1)])


def parts(rng, spec, size=(11, 11)):
    G_ = np.zeros(size, dtype=np.int64)
    for shape, colour in spec:
        if not F2._place(rng, G_, SHAPES[shape], colour):
            return None
    return G_


def _cols(rng, k):
    return [int(c) for c in rng.permutation([1, 2, 3, 4, 5, 6, 7, 8, 9])[:k]]


# ------------------------------------------------------------------ scenes (augmentation lives here)
def scene_assorted(rng, role="demo"):
    c = _cols(rng, 4)
    shapes = [str(s) for s in rng.choice(["dot", "domino", "square", "ell", "hbar3", "vbar3", "ring", "tee", "plus"],
                                         size=int(rng.integers(4, 7)))]
    return parts(rng, [(s, c[i % 4]) for i, s in enumerate(shapes)])


def scene_with_one_ring(rng, role="demo"):
    c = _cols(rng, 4)
    rest = [str(s) for s in rng.choice(["dot", "domino", "ell", "tee", "square"], size=int(rng.integers(2, 4)))]
    return parts(rng, [("ring", c[0])] + [(s, c[1 + i % 3]) for i, s in enumerate(rest)])


def scene_rings_and_blobs(rng, role="demo"):
    c = _cols(rng, 4)
    rings = [("ring", c[i]) for i in range(int(rng.integers(1, 3)))]
    blobs = [(str(s), c[2 + i % 2]) for i, s in enumerate(rng.choice(["dot", "domino", "ell", "tee"], size=int(rng.integers(2, 4))))]
    return parts(rng, rings + blobs)


def scene_border_and_inner(rng, role="demo"):
    """Some objects on the border, some inside, so that touches_border splits them."""
    g = scene_assorted(rng)
    if g is None:
        return None
    h, w = g.shape
    edge = np.zeros_like(g, dtype=bool)
    edge[0, :] = edge[-1, :] = edge[:, 0] = edge[:, -1] = True
    k = int(rng.integers(1, 10))
    for _ in range(40):
        r, cc = int(rng.integers(0, h)), int(rng.integers(0, w))
        if edge[r, cc] and not g[max(r - 1, 0):r + 2, max(cc - 1, 0):cc + 2].any():
            g[r, cc] = k
            return g
    return None


def scene_ambiguous_colour_size(rng, role="demo"):
    """Demonstrations: every colour-2 object is a dot and every dot is colour 2. Test: a colour-2 domino and a
    colour-3 dot break the tie."""
    if role == "demo":
        spec = [("dot", 2)] * int(rng.integers(1, 3)) + [(str(s), 3) for s in rng.choice(["domino", "ell", "tee"], size=2)]
    else:
        spec = [("domino", 2), ("dot", 3), ("dot", 2), ("ell", 3)]
    return parts(rng, [spec[i] for i in rng.permutation(len(spec))])


def scene_rect_and_others(rng, role="demo"):
    return F2.scene_rect_and_others(rng)


def scene_ambiguous_line_rect(rng, role="demo"):
    """Demonstrations: lines and non-rectangles only. Test: adds a square (a rectangle that is not a line)."""
    c = _cols(rng, 3)
    spec = [(str(s), c[0]) for s in rng.choice(["hbar3", "vbar3", "hbar4"], size=2)] + [(str(s), c[1]) for s in rng.choice(["ell", "tee", "ring"], size=2)]
    if role == "test":
        spec.append(("square", c[2]))
    return parts(rng, spec)


def scene_ambiguous_hole_size8(rng, role="demo"):
    """Demonstrations: the only 8-cell objects are rings. Test: adds an 8-cell block without a hole."""
    c = _cols(rng, 3)
    spec = [("ring", c[0])] + [(str(s), c[1]) for s in rng.choice(["dot", "domino", "ell", "tee"], size=2)]
    if role == "test":
        spec.append(("block8", c[2]))
    return parts(rng, spec, (12, 12))


# ------------------------------------------------------------------ certification (generation time, by execution)
def certify_alt(task, answer, alt):
    """An alternative program fits the demonstrations and disagrees on the test."""
    if not G.fit(alt, task["train"])[0]:
        return False
    p = G.execute(alt, task["test_inputs"][0])
    return p is not None and not (p.shape == answer.shape and np.array_equal(p, answer))


def memorizers(task):
    """Memorizing candidates from ncv2-g2's own generators, cheapest first: induced feature maps, the colour map, and
    native's pixel rule (induced exactly as `cora_neural_v2g2.search.class_candidates` induces it)."""
    from cora_neural_v2.constraints import evidence
    from cora_neural_v2g2 import search as S2
    train = task["train"]
    rule = lambda a: N("program", ("S1", (N("rule", (N("true", ()), a)),), "keep", N("same_as_input", ())))  # noqa: E731
    yield from (rule(a) for a, _, _ in S2.feature_map_actions(train))
    ev = evidence(train)
    if ev["recol_pairs"]:
        yield rule(N("recolor", (N("color_map", (tuple(sorted(ev["recol_pairs"])),)),)))
    from geocat_arc.object_reasoning.pixel_rules import induce_pixel_rule
    from geocat_arc.object_reasoning.types import to_grid_pairs
    with S2.v23_flags():
        try:
            pix = induce_pixel_rule(to_grid_pairs([(np.asarray(a), np.asarray(b)) for a, b in train]))
        except Exception:                                          # noqa: BLE001
            pix = None
    if pix is not None:
        try:
            yield G.decompile({"program_class": "reduction", "split": {"kind": "pixel_rule"}, "mode": pix["mode"], "params": pix})
        except Exception:                                          # noqa: BLE001 (not exposed in the grammar)
            pass


def certify_necessary(task, prog):
    """Every rule of a multi-rule program is needed: dropping any one breaks the fit on the demonstrations."""
    rules = prog.args[1] if prog.op == "program" else ()
    if len(rules) < 2:
        return True
    for i in range(len(rules)):
        less = N("program", (prog.args[0], rules[:i] + rules[i + 1:], prog.args[2], prog.args[3]))
        if G.fit(less, task["train"])[0]:
            return False
    return True


def certify_trap(task, answer):
    for m in memorizers(task):
        try:
            if G.fit(m, task["train"])[0]:
                p = G.execute(m, task["test_inputs"][0])
                if p is not None and not (p.shape == answer.shape and np.array_equal(p, answer)):
                    return True
        except Exception:                                          # noqa: BLE001
            continue
    return False


# ------------------------------------------------------------------ families: name -> (split, group, program, scene, alt)
FAMILIES = {
    # ---- DEV (development and unit tests) ----
    "v3d_comp_ring_delete_line_recolour": ("dev", "composition", P("(rule (test has_hole == #t) (delete)) (rule (test is_line == #t) (recolor (color 6)))"), scene_assorted, None),
    "v3d_comp_border_delete_rect_recolour": ("dev", "composition", P("(rule (test touches_border == #t) (delete)) (rule (test is_rectangle == #t) (recolor (color 8)))"), scene_border_and_inner, None),
    "v3d_bind_adopt_nearest_ring": ("dev", "binding", P("(rule (test has_hole == #f) (recolor (color_of (nearest (test has_hole == #t)))))"), scene_rings_and_blobs, None),
    "v3d_trap_line_most_common": ("dev", "trap", P("(rule (test is_line == #t) (recolor (most_common_color)))"), scene_assorted, "trap"),
    "v3d_amb_colour_or_size": ("dev", "ambiguity", P("(rule (test color == 2) (recolor (color 4)))"), scene_ambiguous_colour_size,
                               P("(rule (test size == 1) (recolor (color 4)))")),
    "v3d_ctrl_ring_recolour": ("dev", "control", P("(rule (test has_hole == #t) (recolor (color 2)))"), scene_rings_and_blobs, None),
    "v3d_add_copy_ring_down": ("dev", "additive", P("(rule (test has_hole == #t) (copy_offsets (list (vec 4 0))))"), scene_rings_and_blobs, None),
    # ---- HELDOUT (the frozen protocol only) ----
    "v3h_comp_line_move_ring_recolour": ("heldout", "composition", P("(rule (test is_line == #t) (translate (vec 0 1))) (rule (test has_hole == #t) (recolor (color 7)))"), scene_assorted, None),
    "v3h_comp_unique_delete_nonrect_recolour": ("heldout", "composition", P("(rule (test is_unique_color == #t) (delete)) (rule (test is_rectangle == #f) (recolor (color 9)))"), scene_assorted, None),
    "v3h_comp_three_rules": ("heldout", "composition", P("(rule (test has_hole == #t) (delete)) (rule (test is_line == #t) (recolor (color 6))) (rule (test is_rectangle == #t) (recolor (color 8)))"), scene_assorted, None),
    "v3h_comp_largest_delete_line_recolour": ("heldout", "composition", P("(rule (test size_rank == 0) (delete)) (rule (test is_line == #t) (recolor (color 5)))"), scene_assorted, None),
    "v3h_bind_rect_step_adopt": ("heldout", "binding", P("(rule_with (list (?t (nearest (test is_rectangle == #t)))) (test is_rectangle == #f) "
                                                         "(composite (list (translate (step_toward (var ?t))) (recolor (color_of (var ?t))))))"), scene_rect_and_others, None),
    "v3h_bind_largest_colour": ("heldout", "binding", P("(rule (true) (recolor (color_of (largest (true)))))"), scene_assorted, None),
    "v3h_bind_toward_unique_ring": ("heldout", "binding", P("(rule (test has_hole == #f) (translate (step_toward (unique (test has_hole == #t)))))"), scene_with_one_ring, None),
    "v3h_trap_ring_most_common": ("heldout", "trap", P("(rule (test has_hole == #t) (recolor (most_common_color)))"), scene_rings_and_blobs, "trap"),
    "v3h_trap_border_relational": ("heldout", "trap", P("(rule (test touches_border == #f) (recolor (color_of (nearest (test touches_border == #t)))))"), scene_border_and_inner, "trap"),
    "v3h_amb_line_or_rect": ("heldout", "ambiguity", P("(rule (test is_line == #t) (delete))"), scene_ambiguous_line_rect,
                             P("(rule (test is_rectangle == #t) (delete))")),
    "v3h_amb_hole_or_size8": ("heldout", "ambiguity", P("(rule (test has_hole == #t) (recolor (color 6)))"), scene_ambiguous_hole_size8,
                              P("(rule (test size == 8) (recolor (color 6)))")),
    "v3h_ctrl_border_recolour": ("heldout", "control", P("(rule (test touches_border == #t) (recolor (color 1)))"), scene_border_and_inner, None),
    "v3h_ctrl_unique_size_delete": ("heldout", "control", P("(rule (test is_unique_size == #t) (delete))"), scene_assorted, None),
    "v3h_add_copy_line_recolour_ring": ("heldout", "additive", P("(rule (test is_line == #t) (copy_offsets (list (vec 0 3)))) (rule (test has_hole == #t) (recolor (color 5)))"), scene_assorted, None),
    "v3h_add_fill_line_unique": ("heldout", "additive", P("(rule (test is_unique_color == #t) (fill_line horizontal (color 4) to_border))"), scene_assorted, None),
}


def make_task(name, seed, n_demos=3, task_tries=25, pair_tries=200):
    """(task, expected test output) or None; deterministic in (VERSION, name, seed). Certified families regenerate
    the whole task until it passes (at most `task_tries` times)."""
    split, group, src, scene, extra = FAMILIES[name]
    prog = G.parse(src)
    G.typecheck(prog)
    alt = G.parse(extra) if extra and extra != "trap" else None
    rng = np.random.default_rng(zlib.crc32(f"{VERSION}|{name}|{seed}".encode()))
    multi = prog.op == "program" and len(prog.args[1]) > 1
    for _ in range(task_tries if (extra or multi) else 1):
        pairs = []
        for role in ["demo"] * n_demos + ["test"]:
            for _ in range(pair_tries):
                g = scene(rng, role)
                if g is None:
                    continue
                out = G.execute(prog, g)
                if out is None or (out.shape == g.shape and np.array_equal(out, g)):
                    continue
                pairs.append((g.tolist(), out.tolist()))
                break
        if len(pairs) < n_demos + 1:
            continue
        task = {"task_id": f"{VERSION}:{name}#{seed}", "family": name, "group": group,
                "train": pairs[:-1], "test_inputs": [pairs[-1][0]]}
        answer = np.asarray(pairs[-1][1])
        if not certify_necessary(task, prog):
            continue
        if extra == "trap" and not certify_trap(task, answer):
            continue
        if alt is not None and not certify_alt(task, answer, alt):
            continue
        return task, answer
    return None


def names(split, group=None):
    return [k for k, v in FAMILIES.items() if v[0] == split and (group is None or v[1] == group)]


def alternative(name):
    extra = FAMILIES[name][4]
    return G.parse(extra) if extra and extra != "trap" else None
