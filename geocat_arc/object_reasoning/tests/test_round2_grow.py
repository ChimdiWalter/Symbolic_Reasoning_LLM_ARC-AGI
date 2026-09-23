"""Round-2 GROW delta family: geometry, detection, rendering, induction.

Covers STAGE2 round-2 lever 1: growth.py mode geometry; detect_grow raw-param
extraction in _minimal_delta; apply_grow rendering; end-to-end induce_program
on synthetic grow tasks (LOO-gated); serialization round-trip through a fresh
parse; and the no-regression guarantee that non-grow deltas are unchanged.
"""
import json

import numpy as np
import pytest

from geocat_arc.perception.grid import Grid
from geocat_arc.object_reasoning.growth import (
    GROW_MODES,
    added_pattern,
    detect_grow,
    grow_fill_interior,
    grow_halo,
    grow_ray,
    interior_cells,
    pattern_cells,
)
from geocat_arc.object_reasoning.types import (
    ActionRule,
    DeltaType,
    ObjectProgram,
)
from geocat_arc.object_reasoning.expressions import (
    ColorExpr,
    DirectionExpr,
    GrowModeExpr,
    PatternExpr,
    ScalarExpr,
)
from geocat_arc.object_reasoning.inducer import induce_program
from geocat_arc.object_reasoning.actions import render_program


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------

def test_interior_cells_ring():
    ring = {(0, 0), (0, 1), (0, 2), (1, 0), (1, 2), (2, 0), (2, 1), (2, 2)}
    assert interior_cells(ring) == {(1, 1)}


def test_interior_cells_open_shape_has_none():
    lshape = {(0, 0), (1, 0), (2, 0), (2, 1), (2, 2)}
    assert interior_cells(lshape) == set()


def test_grow_halo_conn4_vs_conn8():
    cell = {(2, 2)}
    h4 = grow_halo(cell, 5, 4, (5, 5))
    h8 = grow_halo(cell, 5, 8, (5, 5))
    assert set(h4) == {(1, 2), (3, 2), (2, 1), (2, 3)}
    assert set(h8) == {(r, c) for r in (1, 2, 3) for c in (1, 2, 3)} - cell
    assert all(v == 5 for v in h8.values())


def test_grow_halo_clips_to_bounds():
    h = grow_halo({(0, 0)}, 3, 4, (2, 2))
    assert set(h) == {(0, 1), (1, 0)}


def test_grow_ray_to_border_and_fixed():
    cells = {(2, 2), (2, 3)}
    to_border = grow_ray(cells, "down", 7, None, (6, 6))
    assert set(to_border) == {(r, c) for r in (3, 4, 5) for c in (2, 3)}
    fixed = grow_ray(cells, "right", 7, 1, (6, 6))
    assert set(fixed) == {(2, 4)}  # (2,3)+right is (2,4); (2,2)+right in obj


def test_pattern_round_trip():
    in_cells = {(4, 4), (4, 5)}
    added = {(3, 4): 2, (5, 5): 8}
    pat = added_pattern(in_cells, added)
    assert pattern_cells(in_cells, pat) == added


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

def test_detect_grow_fill_interior():
    ring = {(r, c): 3 for (r, c) in
            {(0, 0), (0, 1), (0, 2), (1, 0), (1, 2), (2, 0), (2, 1), (2, 2)}}
    out = dict(ring)
    out[(1, 1)] = 6
    p = detect_grow(ring, out, (5, 5))
    assert p == {"mode": "fill_interior", "color": 6}


def test_detect_grow_halo():
    cc = {(2, 2): 4}
    out = dict(cc)
    out.update(grow_halo({(2, 2)}, 1, 4, (5, 5)))
    p = detect_grow(cc, out, (5, 5))
    assert p == {"mode": "halo", "color": 1, "conn": 4}


def test_detect_grow_ray_to_border():
    cc = {(1, 1): 5}
    out = dict(cc)
    out.update(grow_ray({(1, 1)}, "down", 5, None, (4, 3)))
    p = detect_grow(cc, out, (4, 3))
    assert p == {"mode": "ray", "direction": "down", "color": 5}


def test_detect_grow_ray_fixed_length():
    cc = {(0, 1): 5}
    out = dict(cc)
    out.update(grow_ray({(0, 1)}, "down", 2, 2, (8, 3)))
    p = detect_grow(cc, out, (8, 3))
    assert p["mode"] == "ray" and p["direction"] == "down" \
        and p["length"] == 2 and p["color"] == 2


def test_detect_grow_pattern_fallback():
    cc = {(2, 2): 3}
    out = dict(cc)
    out[(2, 4)] = 7  # detached diagonal-ish addition: no mode matches
    out[(4, 2)] = 7
    p = detect_grow(cc, out, (6, 6))
    assert p["mode"] == "pattern"
    # round 4: uniform-color additions use the color-abstracted encoding
    # (mask offsets + color slot) so induction can fill the color
    # relationally instead of memorizing it
    assert p["color"] == 7
    assert pattern_cells(set(cc), p["pattern"], p["color"]) \
        == {(2, 4): 7, (4, 2): 7}


def test_detect_grow_rejects_non_superset():
    cc = {(1, 1): 3, (1, 2): 3}
    out = {(1, 1): 3, (2, 5): 3}     # lost a cell -> not growth
    assert detect_grow(cc, out, (6, 6)) is None
    out2 = {(1, 1): 4, (1, 2): 4, (1, 3): 4}  # recolored base -> not growth
    assert detect_grow(cc, out2, (6, 6)) is None
    assert detect_grow(cc, dict(cc), (6, 6)) is None  # no addition


# ---------------------------------------------------------------------------
# Rendering (apply_grow through a one-rule program)
# ---------------------------------------------------------------------------

def _grow_program(action_params: dict) -> ObjectProgram:
    from geocat_arc.object_reasoning.types import (OutputSpec, SelectorRule,
                                                   ObjectRule,
                                                   SegmentationVariant)
    from geocat_arc.object_reasoning.expressions import PredExpr
    rule = ObjectRule(
        selector=SelectorRule(predicate=PredExpr(op="true", args=()),
                              literals=0),
        action=ActionRule(delta_type=DeltaType.GROW, params=action_params))
    return ObjectProgram(segmentation_variant=SegmentationVariant("S1"),
                         rules=[rule],
                         default_action=ActionRule(delta_type=DeltaType.KEEP),
                         output_spec=OutputSpec(mode="same_as_input"))


def test_apply_grow_ray_renders():
    grid = Grid.from_list([[0, 0, 0],
                           [0, 5, 0],
                           [0, 0, 0]])
    prog = _grow_program({
        "mode": GrowModeExpr(op="const", args=("ray",)),
        "color": ColorExpr(op="const", args=(5,)),
        "direction": DirectionExpr(op="const", args=("down",)),
    })
    out = render_program(prog, grid)
    assert out.to_list() == [[0, 0, 0],
                             [0, 5, 0],
                             [0, 5, 0]]


def test_apply_grow_fill_interior_renders():
    grid = Grid.from_list([[3, 3, 3],
                           [3, 0, 3],
                           [3, 3, 3]])
    prog = _grow_program({
        "mode": GrowModeExpr(op="const", args=("fill_interior",)),
        "color": ColorExpr(op="const", args=(6,)),
    })
    out = render_program(prog, grid)
    assert out.to_list()[1][1] == 6


# ---------------------------------------------------------------------------
# End-to-end induction (the acceptance path, LOO-gated)
# ---------------------------------------------------------------------------

def _pairs(specs):
    return [(Grid.from_list(i), Grid.from_list(o)) for i, o in specs]


def test_induce_ray_to_border_task():
    """Every object emits a ray of its own color to the bottom border —
    to-border spelling must induce and pass LOO (3 folds)."""
    def make(col, r, c, h=6, w=6):
        gi = [[0] * w for _ in range(h)]
        gi[r][c] = col
        go = [row[:] for row in gi]
        for rr in range(r + 1, h):
            go[rr][c] = col
        return gi, go

    pairs = _pairs([make(3, 1, 1), make(4, 2, 4), make(6, 0, 2)])
    res = induce_program(pairs)
    assert res.program is not None, res.failure_stage
    assert res.loo.passed == res.loo.folds == 3
    dts = {r.action.delta_type for r in res.program.rules}
    assert DeltaType.GROW in dts
    # generalization: unseen position/color
    gi, go = _pairs([make(8, 1, 3)])[0]
    assert render_program(res.program, gi).to_list() == go.to_list()


def test_induce_fill_interior_task():
    """Hollow rectangles get their interior filled with a fixed color."""
    def make(r0, c0, h=7, w=7):
        gi = [[0] * w for _ in range(h)]
        for c in range(c0, c0 + 3):
            gi[r0][c] = 3
            gi[r0 + 2][c] = 3
        gi[r0 + 1][c0] = 3
        gi[r0 + 1][c0 + 2] = 3
        go = [row[:] for row in gi]
        go[r0 + 1][c0 + 1] = 8
        return gi, go

    pairs = _pairs([make(0, 0), make(2, 3), make(4, 1)])
    res = induce_program(pairs)
    assert res.program is not None, res.failure_stage
    assert res.loo.passed == res.loo.folds == 3
    gi, go = _pairs([make(1, 2)])[0]
    assert render_program(res.program, gi).to_list() == go.to_list()


def test_grow_program_serialization_round_trip():
    def make(col, r, c):
        gi = [[0] * 5 for _ in range(5)]
        gi[r][c] = col
        go = [row[:] for row in gi]
        for rr in range(r + 1, 5):
            go[rr][c] = col
        return gi, go

    pairs = _pairs([make(3, 1, 1), make(4, 2, 3), make(6, 0, 2)])
    res = induce_program(pairs)
    assert res.program is not None
    blob = json.dumps(res.program.to_dict())
    prog2 = ObjectProgram.from_dict(json.loads(blob))
    gi, go = _pairs([make(9, 1, 2)])[0]
    assert render_program(prog2, gi).to_list() == go.to_list()


def test_non_grow_deltas_unchanged():
    """A plain translate task must still induce TRANSLATE (no GROW leak)."""
    def make(r, c):
        gi = [[0] * 6 for _ in range(6)]
        gi[r][c] = 2
        go = [[0] * 6 for _ in range(6)]
        go[r][c + 2] = 2
        return gi, go

    pairs = _pairs([make(1, 1), make(3, 2), make(4, 0)])
    res = induce_program(pairs)
    assert res.program is not None
    dts = {r.action.delta_type for r in res.program.rules}
    assert DeltaType.GROW not in dts


def test_pattern_mdl_never_outranks_generative():
    """A memorized k-cell PatternExpr must cost k bound literals + k size
    (the 3ac3eb23/623ea044 regression: a GROW pattern memorizer outranked
    the COPY-period generative program and then failed LOO)."""
    from geocat_arc.object_reasoning.inducer import _expr_value_bound_count
    pat = PatternExpr(op="const",
                      args=(tuple((((i, 0), 4)) for i in range(12)),))
    assert pat.size == 13
    assert _expr_value_bound_count(pat) == 12
    vec = ScalarExpr(op="const", args=(2,))
    assert vec.size < pat.size
    assert _expr_value_bound_count(vec) < _expr_value_bound_count(pat)


def test_periodic_copy_still_beats_grow_pattern():
    """End-to-end guard for the regression: periodic spawn along a column
    must induce COPY (period mode), not a GROW pattern memorizer."""
    def make(c):
        gi = [[0] * 5 for _ in range(9)]
        gi[0][c] = 3
        go = [row[:] for row in gi]
        for r in (2, 4, 6, 8):
            go[r][c] = 3
        return gi, go

    pairs = _pairs([make(1), make(2), make(3)])
    res = induce_program(pairs)
    assert res.program is not None, res.failure_stage
    dts = {r.action.delta_type for r in res.program.rules}
    assert DeltaType.GROW not in dts


# ---------------------------------------------------------------------------
# Round 3: relational growth modes (symmetry_complete / mirror_edge)
# ---------------------------------------------------------------------------

def test_grow_symmetry_complete_geometry():
    from geocat_arc.object_reasoning.growth import grow_symmetry_complete
    # L-shape missing its mirror half across the vertical bbox axis
    cc = {(0, 0): 3, (1, 0): 3, (2, 0): 3, (2, 1): 5, (2, 2): 3}
    added = grow_symmetry_complete(cc, "vertical")
    assert added == {(0, 2): 3, (1, 2): 3}
    # colors carried from mirrored SOURCE cells, not uniform
    cc2 = {(0, 0): 3, (0, 2): 3, (1, 0): 5}
    assert grow_symmetry_complete(cc2, "vertical") == {(1, 2): 5}
    # diagonal undefined on non-square bbox
    assert grow_symmetry_complete({(0, 0): 1, (0, 3): 1}, "diag_main") is None


def test_grow_mirror_edge_geometry():
    from geocat_arc.object_reasoning.growth import grow_mirror_edge
    cc = {(1, 1): 4, (2, 1): 4, (2, 2): 7}
    added = grow_mirror_edge(cc, "right", (6, 6))
    assert added == {(1, 4): 4, (2, 4): 4, (2, 3): 7}
    # out-of-bounds reflection -> undefined
    assert grow_mirror_edge({(0, 0): 2}, "up", (5, 5)) is None


def test_detect_grow_prefers_symmetry_over_pattern():
    cc = {(0, 0): 3, (1, 0): 3, (2, 0): 3, (2, 1): 3, (2, 2): 3}
    out = dict(cc)
    out.update({(0, 2): 3, (1, 2): 3})   # = vertical symmetry completion
    p = detect_grow(cc, out, (8, 8))
    assert p == {"mode": "symmetry_complete", "axis": "vertical"}


def test_induce_symmetry_completion_task():
    """Half-symmetric shapes complete themselves — relational spelling must
    induce, pass LOO, and generalize to an unseen shape (the anti-memorization
    property the 418 constant-pattern rejects lack)."""
    def make(cells, h=8, w=8):
        gi = [[0] * w for _ in range(h)]
        for (r, c), col in cells.items():
            gi[r][c] = col
        from geocat_arc.object_reasoning.growth import grow_symmetry_complete
        added = grow_symmetry_complete(cells, "vertical")
        go = [row[:] for row in gi]
        for (r, c), col in added.items():
            go[r][c] = col
        return gi, go

    # 4-connected shapes (S1 must see ONE object per grid) with a genuine
    # asymmetric half across the vertical bbox axis
    shape1 = {(1, 1): 3, (2, 1): 3, (3, 1): 3, (3, 2): 3, (3, 3): 3}
    shape2 = {(4, 2): 6, (5, 2): 6, (5, 3): 6, (5, 4): 6}
    shape3 = {(0, 0): 8, (1, 0): 8, (1, 1): 8, (1, 2): 8, (0, 2): 8,
              (1, 3): 8, (1, 4): 8}
    pairs = _pairs([make(shape1), make(shape2), make(shape3)])
    res = induce_program(pairs)
    assert res.program is not None, res.failure_stage
    assert res.loo.passed == res.loo.folds == 3
    # unseen shape + color generalizes
    unseen = {(2, 2): 9, (3, 2): 9, (4, 2): 9, (4, 3): 9}
    gi, go = _pairs([make(unseen)])[0]
    assert render_program(res.program, gi).to_list() == go.to_list()


# ---------------------------------------------------------------------------
# Round 4: translate+grow (moved objects that also gain cells)
# ---------------------------------------------------------------------------

def test_detect_translate_grow():
    cc = {(1, 1): 5}
    # moved down 2, then ray up to border... simplest: moved and haloed
    moved = {(3, 1): 5}
    out = dict(moved)
    out.update(grow_halo({(3, 1)}, 2, 4, (6, 6)))
    p = detect_grow(cc, out, (6, 6))
    assert p is not None and p["mode"] == "halo" and p["color"] == 2
    assert (p["dr"], p["dc"]) == (2, 0)


def test_detect_translate_grow_rejects_wrong_shift():
    cc = {(1, 1): 5, (1, 2): 5}
    out = {(3, 3): 5, (3, 4): 7}   # shifted but recolored -> not grow
    assert detect_grow(cc, out, (8, 8)) is None


def test_apply_translate_grow_renders():
    from geocat_arc.object_reasoning.expressions import VecExpr
    grid = Grid.from_list([[0, 0, 0],
                           [5, 0, 0],
                           [0, 0, 0]])
    prog = _grow_program({
        "mode": GrowModeExpr(op="const", args=("ray",)),
        "color": ColorExpr(op="const", args=(5,)),
        "direction": DirectionExpr(op="const", args=("right",)),
        "vector": VecExpr(op="const", args=(1, 1)),
    })
    out = render_program(prog, grid)
    assert out.to_list() == [[0, 0, 0],
                             [0, 0, 0],
                             [0, 5, 5]]


def test_induce_translate_grow_task():
    """Objects move one step down AND emit a ray to the right border —
    translate+grow must induce and pass LOO."""
    def make(col, r, c, h=6, w=6):
        gi = [[0] * w for _ in range(h)]
        gi[r][c] = col
        go = [[0] * w for _ in range(h)]
        for cc_ in range(c, w):
            go[r + 1][cc_] = col
        return gi, go

    pairs = _pairs([make(3, 1, 1), make(4, 2, 3), make(6, 0, 2)])
    res = induce_program(pairs)
    assert res.program is not None, res.failure_stage
    assert res.loo.passed == res.loo.folds == 3
    gi, go = _pairs([make(8, 3, 2)])[0]
    assert render_program(res.program, gi).to_list() == go.to_list()


def test_translate_grow_rejects_pattern_mode():
    """A MOVED object with an arbitrary added-cell pattern must NOT type as
    GROW (matching artifact; the 1-cell memorizer would steal the canonical
    ranking from true composed programs — the two-pass regression)."""
    cc = {(1, 6): 8, (2, 6): 8, (3, 6): 8}
    out = {(1, 4): 8, (2, 4): 8, (3, 4): 8, (2, 3): 2}  # wall moved + ball
    assert detect_grow(cc, out, (5, 10)) is None
    # unmoved pattern growth is still legal
    out2 = dict(cc); out2[(0, 0)] = 2
    p = detect_grow(cc, out2, (5, 10))
    assert p is not None and p["mode"] == "pattern" and "dr" not in p
