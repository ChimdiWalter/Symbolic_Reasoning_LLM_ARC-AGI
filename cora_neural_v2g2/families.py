"""Execution-verified synthetic task families for ncv2-g2.

Each family is a known ncv2-g2 program plus a scene generator. A task is made by running the program through native
CORA on fresh scenes, so every demonstration is native-valid by construction.
- DEV families are used by the unit tests and may be looked at during development.
- HELDOUT families are reserved for the frozen protocol (records/NEURAL_CORA_V2G2_SYNTHETIC_PROTOCOL_20261020.md).
  Do not run, tune on or inspect them before that protocol is executed.
All families are designed by the same author as the generator, so a coverage gain on them is evidence of generator
completeness within the designed grammar, not of real-ARC coverage.
"""
import zlib

import numpy as np

from cora_neural_v2g2 import grammar as G


# ------------------------------------------------------------------ scenes
def _free(G_, cells):
    h, w = G_.shape
    for r, c in cells:
        if not (0 <= r < h and 0 <= c < w) or G_[max(r - 1, 0):r + 2, max(c - 1, 0):c + 2].any():
            return False
    return True


def _place(rng, G_, shape_cells, colour, tries=60):
    h, w = G_.shape
    for _ in range(tries):
        r0, c0 = int(rng.integers(0, h)), int(rng.integers(0, w))
        cells = [(r0 + dr, c0 + dc) for dr, dc in shape_cells]
        if _free(G_, cells):
            for r, c in cells:
                G_[r, c] = colour
            return True
    return False


SHAPES = {"dot": [(0, 0)], "domino": [(0, 0), (0, 1)], "square": [(0, 0), (0, 1), (1, 0), (1, 1)],
          "ell": [(0, 0), (1, 0), (1, 1)], "hbar3": [(0, 0), (0, 1), (0, 2)], "vbar3": [(0, 0), (1, 0), (2, 0)],
          "hbar4": [(0, 0), (0, 1), (0, 2), (0, 3)], "vbar4": [(0, 0), (1, 0), (2, 0), (3, 0)],
          "ring": [(0, 0), (0, 1), (0, 2), (1, 0), (1, 2), (2, 0), (2, 1), (2, 2)], "tee": [(0, 0), (0, 1), (0, 2), (1, 1)]}


def scene_parts(rng, parts, size=(10, 10)):
    """parts: [(shape name, colour)]. Non-touching placement; None if it does not fit."""
    G_ = np.zeros(size, dtype=np.int64)
    for shape, colour in parts:
        if not _place(rng, G_, SHAPES[shape], colour):
            return None
    return G_


def scene_lines_and_blobs(rng):
    cols = [int(c) for c in rng.permutation([1, 2, 3, 4, 6, 7])[:4]]
    lines = [str(rng.choice(["hbar3", "vbar3", "hbar4", "vbar4"])) for _ in range(2)]
    blobs = [str(rng.choice(["square", "ell", "tee"])) for _ in range(int(rng.integers(2, 4)))]
    return scene_parts(rng, [(lines[0], cols[0]), (lines[1], cols[1])] + [(b, cols[2 + i % 2]) for i, b in enumerate(blobs)], (11, 11))


def scene_one_line_and_blobs(rng):
    """Exactly one line, so that `(unique (test is_line == #t))` is defined."""
    cols = [int(c) for c in rng.permutation([1, 2, 3, 4, 6, 7])[:3]]
    line = str(rng.choice(["hbar3", "vbar3", "hbar4", "vbar4"]))
    blobs = [str(rng.choice(["square", "ell", "tee"])) for _ in range(int(rng.integers(2, 4)))]
    return scene_parts(rng, [(line, cols[0])] + [(b, cols[1 + i % 2]) for i, b in enumerate(blobs)], (11, 11))


def scene_rect_and_others(rng):
    cols = [int(c) for c in rng.permutation([1, 2, 3, 4, 6, 7])[:4]]
    return scene_parts(rng, [("square", cols[0]), ("ring", cols[1]), ("ell", cols[2]), ("tee", cols[3])], (11, 11))


def scene_mixed(rng):
    cols = [int(c) for c in rng.choice([1, 2, 3, 4, 5], size=5)]
    shapes = [str(s) for s in rng.choice(["dot", "domino", "square", "ell", "hbar3", "ring", "tee"], size=5)]
    return scene_parts(rng, list(zip(shapes, cols)), (11, 11))


def scene_sizes_123(rng):
    """Every scene holds sizes 1, 2 and 3, so the demonstrations determine the whole size -> colour map."""
    shapes = ["dot", "domino", "ell", str(rng.choice(["dot", "domino", "ell"]))]
    return scene_parts(rng, [(s, 3) for s in rng.permutation(shapes)], (10, 10))


def scene_symmetric(rng, kind):
    n = 7
    G_ = np.zeros((n, n), dtype=np.int64)
    for _ in range(int(rng.integers(5, 9))):
        r, c, colour = int(rng.integers(0, n)), int(rng.integers(0, n)), int(rng.integers(1, 5))
        orbit = {(r, c), (r, n - 1 - c)} if kind == "lr" else {(r, c), (n - 1 - r, c)} if kind == "ud" else \
            {(r, c), (r, n - 1 - c), (n - 1 - r, c), (n - 1 - r, n - 1 - c), (c, r), (c, n - 1 - r), (n - 1 - c, r), (n - 1 - c, n - 1 - r)}
        for rr, cc in orbit:
            G_[rr, cc] = colour
    full = G_.copy()
    nz = np.argwhere(G_)
    if len(nz) < 4:
        return None
    for i in rng.choice(len(nz), size=min(3, len(nz) // 3), replace=False):
        G_[tuple(nz[i])] = 0
    return G_ if not np.array_equal(G_, full) else None


def scene_sparse(rng, colour=1, density=0.3, size=(8, 8)):
    return (rng.random(size) < density).astype(np.int64) * colour


def scene_filled_majority(rng):
    h, w = int(rng.integers(3, 5)), int(rng.integers(3, 5))
    cols = [int(c) for c in rng.permutation([1, 2, 3, 4, 6, 7, 8])[:3]]
    G_ = rng.choice(cols[1:], size=(h, w))
    k = h * w // 2 + 1
    idx = rng.choice(h * w, size=k, replace=False)
    G_.flat[idx] = cols[0]
    return G_.astype(np.int64)


def scene_unique_colour(rng):
    h, w = int(rng.integers(3, 5)), int(rng.integers(3, 5))
    cols = [int(c) for c in rng.permutation([1, 2, 3, 4, 6, 7, 8])[:3]]
    G_ = rng.choice(cols[1:], size=(h, w)).astype(np.int64)
    G_.flat[int(rng.integers(0, h * w))] = cols[0]
    return G_ if (G_ == cols[1]).sum() > 1 and (G_ == cols[2]).sum() > 1 else None


def scene_dots(rng, colours=(2, 3), size=(9, 9)):
    parts = [("dot", int(rng.choice(colours))) for _ in range(int(rng.integers(2, 4)))]
    return scene_parts(rng, parts, size)


def scene_two_panels(rng, sep=5):
    h, w = int(rng.integers(3, 5)), int(rng.integers(3, 5))
    a = scene_sparse(rng, 1, 0.4, (h, w))
    b = scene_sparse(rng, 2, 0.4, (h, w))
    return np.concatenate([a, np.full((h, 1), sep), b], axis=1).astype(np.int64)


# ------------------------------------------------------------------ families
P = lambda rules, view="S1", default="keep", render="(same_as_input)": f"(program {view} (list {rules}) {default} {render})"   # noqa: E731

FAMILIES = {
    # ---- DEV ----
    "relational_feature_recolour": ("dev", P("(rule (test is_line == #f) (recolor (color_of (nearest (test is_line == #t)))))"), scene_lines_and_blobs),
    "negated_selector_delete": ("dev", P("(rule (test is_rectangle == #f) (delete))"), scene_mixed),
    "most_common_recolour": ("dev", P("(rule (test color == 3) (recolor (most_common_color)))"), scene_mixed),
    "feature_map_recolour": ("dev", P("(rule (true) (recolor (feature_map size (list (1 4) (2 5) (3 6)))))"), scene_sizes_123),
    "bind_approach_adopt": ("dev", P("(rule_with (list (?t (nearest (test is_line == #t)))) (test is_line == #f) "
                                     "(composite (list (translate (step_toward (var ?t))) (recolor (color_of (var ?t))))))"), scene_lines_and_blobs),
    "symmetry_completion": ("dev", "(symmetry_completion d4)", lambda rng: scene_symmetric(rng, "d4")),
    "pixel_neighbor_count": ("dev", "(pixel_rule neighbor_count (list (entry (key_count 0 2) 8) (entry (key_count 0 3) 8) (entry (key_count 0 4) 8)))",
                             lambda rng: scene_sparse(rng, 1, 0.35)),
    "counting_majority": ("dev", "(counting majority_color)", scene_filled_majority),
    "generative_ray": ("dev", "(generative S1 (list (gen (gsel (list (sel_color 2))) (grule ray (list (gp direction right))))) over_input 0 #f none)",
                       lambda rng: scene_dots(rng)),
    "panel_overlay": ("dev", "(panel_reduction (split_separator 5) (overlay overlay_first))", scene_two_panels),
    # ---- HELDOUT (frozen protocol only) ----
    "h_rect_relational_recolour": ("heldout", P("(rule (test is_rectangle == #f) (recolor (color_of (nearest (test is_rectangle == #t)))))"), scene_rect_and_others),
    "h_border_relational_move": ("heldout", P("(rule (test touches_border == #f) (translate (step_toward (nearest (test touches_border == #t)))))"), scene_mixed),
    "h_two_rule_features": ("heldout", P("(rule (test is_line == #t) (delete)) (rule (test has_hole == #t) (recolor (color 4)))"), scene_mixed),
    "h_least_common_recolour": ("heldout", P("(rule (test color == 5) (recolor (least_common_color)))"), scene_mixed),
    "h_symmetry_lr": ("heldout", "(symmetry_completion horizontal)", lambda rng: scene_symmetric(rng, "lr")),
    "h_pixel_color_swap": ("heldout", "(pixel_rule color_swap (list (entry (key_color 1) 2) (entry (key_color 2) 1)))",
                           lambda rng: scene_sparse(rng, 1, 0.3) + scene_sparse(rng, 2, 0.2) * (scene_sparse(rng, 1, 0.3) == 0)),
    "h_counting_unique": ("heldout", "(counting unique_color)", scene_unique_colour),
    "h_generative_row_line": ("heldout", "(generative S1 (list (gen (gsel (list (sel_color 3))) (grule row_line (list)))) over_input 0 #f none)",
                              lambda rng: scene_dots(rng, (2, 3))),
    "h_panel_select_most": ("heldout", "(panel_reduction (split_separator 5) (select_panel most_nonbg))", scene_two_panels),
    "h_bind_unique": ("heldout", P("(rule_with (list (?t (unique (test is_line == #t)))) (test is_line == #f) "
                                   "(composite (list (translate (step_toward (var ?t))) (recolor (color_of (var ?t))))))"), scene_one_line_and_blobs),
}


def make_task(name, seed, n_demos=3):
    """(task, expected test output) or None, from family `name`; deterministic in (name, seed)."""
    split, src, scene = FAMILIES[name]
    prog = G.parse(src)
    G.typecheck(prog)
    rng = np.random.default_rng(zlib.crc32(f"{name}|{seed}".encode()))
    pairs, tries = [], 0
    while len(pairs) < n_demos + 1 and tries < 300:
        tries += 1
        g = scene(rng)
        if g is None:
            continue
        out = G.execute(prog, g)
        if out is None or (out.shape == g.shape and np.array_equal(out, g)):
            continue
        pairs.append((g.tolist(), out.tolist()))
    if len(pairs) < n_demos + 1:
        return None
    return ({"task_id": f"{name}#{seed}", "family": name, "train": pairs[:-1], "test_inputs": [pairs[-1][0]]},
            np.asarray(pairs[-1][1]))


def names(split):
    return [k for k, v in FAMILIES.items() if v[0] == split]
