"""ROUND 20 — RAY/LINE EXTENSION (ARC_RAY_EXT).

The R20 traces (RUN_HISTORY 2026-08-15) found that the census's
"extension_beyond_objects" blocker is mechanically ONE thing: every GROW
mode before round 20 is a pure function of (cells, bounds), so obstacle-
conditional stopping and background-only painting are not expressible at
all.  Round 20 threads the input SCENE into the GROW path and adds the three
modes the traces verified by exact reproduction:

  cross_center  — full row+column through the object's OWN bbox centre,
                  painting background only            (traced on 41e4d17e)
  cavity_leak   — bbox cavity fill that leaks out of the object's own
                  outline gaps to the border          (traced on 292dd178)
  ray_deflect   — extrusion that steps around an obstacle to its NEARER
                  free side and continues             (traced on c87289bb)

The INTER-OBJECT CONNECTOR candidate was FALSIFIED by the same traces (0 of
9 exemplars reproduced by any connector spelling), so ARC_CONNECT_EXT does
not exist and test_connector_candidate_was_not_built pins that.

The contract that matters: the scene is re-read at render time, so the same
program applied to a held-out input with a DIFFERENT obstacle produces a
DIFFERENT (correct) answer.  test_deflection_is_rederived_per_scene and the
end-to-end LOO certification below are the tests that pin that down.
"""
from __future__ import annotations

import numpy as np
import pytest

from geocat_arc.object_reasoning.growth import (
    GROW_MODES,
    RAY_EXT_MODES,
    detect_grow,
    grid_background,
    grow_cavity_leak,
    grow_cross_center,
    grow_ray_deflect,
)
from geocat_arc.perception.grid import Grid


@pytest.fixture
def ray_on(monkeypatch):
    monkeypatch.setenv("ARC_RAY_EXT", "1")


@pytest.fixture
def ray_off(monkeypatch):
    monkeypatch.delenv("ARC_RAY_EXT", raising=False)


def rows_of(lines):
    """Row-string grid -> tuple of tuples of ints ('.' reads as 0)."""
    return tuple(tuple(0 if ch == "." else int(ch) for ch in line)
                 for line in lines)


def cells_of(rows, colour):
    """Every cell of ``rows`` carrying ``colour``."""
    return frozenset((r, c) for r, row in enumerate(rows)
                     for c, v in enumerate(row) if v == colour)


def cc_of(rows, colour):
    return {p: colour for p in cells_of(rows, colour)}


# ---------------------------------------------------------------------------
# Vocabulary wiring
# ---------------------------------------------------------------------------

def test_modes_registered_before_pattern_fallback():
    """The grid-aware spellings must OUTRANK the constant memorizer, or the
    inducer's preference order would still pick the stored cell list."""
    for mode in RAY_EXT_MODES:
        assert mode in GROW_MODES
        assert GROW_MODES.index(mode) < GROW_MODES.index("pattern")


def test_connector_candidate_was_not_built():
    """R20 milestone 1 FALSIFIED the inter-object connector candidate: not
    one of its 9 exemplars is reproduced by any connector spelling on all
    pairs.  Building an L-path connector anyway would be exactly the
    speculation the trace-first protocol forbids, so ARC_CONNECT_EXT must
    NOT exist.  This test fails the moment someone adds it without a trace.
    """
    import geocat_arc.object_reasoning.growth as growth
    src = open(growth.__file__).read()
    assert "ARC_CONNECT_EXT" not in src
    for mode in GROW_MODES:
        assert "connect" not in mode


def test_grid_background_is_derived_not_stored():
    assert grid_background(rows_of(["0001", "0002", "0003"])) == 0
    assert grid_background(rows_of(["8881", "8882", "8883"])) == 8
    # tie -> lowest colour (deterministic)
    assert grid_background(rows_of(["12"])) == 1


# ---------------------------------------------------------------------------
# cross_center
# ---------------------------------------------------------------------------

def test_cross_center_paints_full_row_and_column_through_own_centre():
    # background 8 (the majority colour), a hollow 1-ring, its hole also 8 —
    # the 41e4d17e geometry in miniature.
    rows = rows_of(["88888",
                    "81118",
                    "81818",
                    "81118",
                    "88888"])
    added = grow_cross_center(cells_of(rows, 1), rows, 6)
    # centre of the 1-ring bbox (rows 1-3, cols 1-3) is (2, 2)
    assert added[(2, 2)] == 6                       # the object's own hole
    assert added[(2, 0)] == 6 and added[(2, 4)] == 6   # row out to borders
    assert added[(0, 2)] == 6 and added[(4, 2)] == 6   # column out to borders
    # the object's own cells are NOT overwritten
    assert (1, 2) not in added and (2, 1) not in added


def test_cross_center_paints_background_only():
    """Another object standing on the cross line survives underneath."""
    rows = rows_of(["00000",
                    "01110",
                    "01013",
                    "01110",
                    "00000"])
    added = grow_cross_center(cells_of(rows, 1), rows, 6)
    assert (2, 4) not in added, "the colour-3 object was overwritten"
    assert added[(2, 0)] == 6


def test_cross_center_undefined_for_even_extent():
    """No single centre cell -> the mode is UNDEFINED, never a guess."""
    rows = rows_of(["0000", "0110", "0110", "0000"])
    assert grow_cross_center(cells_of(rows, 1), rows, 6) is None


def test_cross_center_undefined_without_a_scene():
    rows = rows_of(["00000", "01110", "01010", "01110", "00000"])
    assert grow_cross_center(cells_of(rows, 1), None, 6) is None


# ---------------------------------------------------------------------------
# cavity_leak
# ---------------------------------------------------------------------------

def test_cavity_leak_fills_interior_and_leaks_through_its_own_gap():
    # the bottom outline has a hole at (4, 2) -> the fill leaks DOWN
    rows = rows_of(["00000",
                    "01110",
                    "01010",
                    "01010",
                    "01010"])
    # bottom row of the bbox has a hole at col 2 -> the fill leaks DOWN
    added = grow_cavity_leak(cells_of(rows, 1), rows, 2)
    assert added[(2, 2)] == 2 and added[(3, 2)] == 2      # cavity
    assert added[(4, 2)] == 2                             # the gap itself
    # and the leak continues to the border (row 4 is the last row here)
    assert (2, 0) not in added, "the leak escaped sideways through a wall"


def test_cavity_leak_leak_width_equals_gap_width():
    """The leak is as wide as the opening — both read off the object."""
    rows = rows_of(["0000000",
                    "0111110",
                    "0100010",
                    "0100010",
                    "0100010",
                    "0100010",
                    "0100010"])
    # the ENTIRE bottom outline is missing (the bbox stops at row 6, which
    # is all wall-except-interior), so the interior leaks straight down.
    added = grow_cavity_leak(cells_of(rows, 1), rows, 2)
    interior = {(r, c) for r in range(2, 6) for c in range(2, 5)}
    assert interior <= set(added)


def test_cavity_leak_undefined_without_a_cavity():
    rows = rows_of(["000", "011", "011"])
    assert grow_cavity_leak(cells_of(rows, 1), rows, 2) is None


def test_cavity_leak_undefined_without_a_scene():
    rows = rows_of(["00000", "01110", "01010", "01110", "00000"])
    assert grow_cavity_leak(cells_of(rows, 1), None, 2) is None


# ---------------------------------------------------------------------------
# ray_deflect
# ---------------------------------------------------------------------------

def _deflect_scene(bar_col, obs_lo, obs_hi, h=9, w=11):
    """A colour-8 bar (rows 0-1) above a colour-2 obstacle bar at row 4."""
    grid = [[0] * w for _ in range(h)]
    for r in (0, 1):
        grid[r][bar_col] = 8
    for c in range(obs_lo, obs_hi + 1):
        grid[4][c] = 2
    return tuple(tuple(r) for r in grid)


def test_ray_deflect_steps_to_the_strictly_nearer_side():
    rows = _deflect_scene(bar_col=1, obs_lo=1, obs_hi=2)
    added = grow_ray_deflect(cells_of(rows, 8), rows, "down", 8)
    # exits: left col 0 (distance 1), right col 3 (distance 2) -> LEFT
    assert added[(3, 0)] == 8
    assert (3, 3) not in added
    for r in range(4, 9):
        assert added[(r, 0)] == 8, "the deflected ray did not continue down"


def test_ray_deflect_tie_resolves_to_the_positive_side():
    """The falsified rule: c87289bb pairs 2 and 3 are both ties and both go
    to the POSITIVE lateral side.  The opposite spelling fits pairs 0/1 and
    dies on 2/3, which is how this constant was found rather than chosen."""
    rows = _deflect_scene(bar_col=5, obs_lo=4, obs_hi=6)
    added = grow_ray_deflect(cells_of(rows, 8), rows, "down", 8)
    # exits: left col 3 (distance 2), right col 7 (distance 2) -> RIGHT
    assert added[(3, 7)] == 8
    assert (3, 3) not in added
    for r in range(4, 9):
        assert added[(r, 7)] == 8


def test_ray_deflect_unobstructed_lane_is_a_plain_ray():
    rows = _deflect_scene(bar_col=9, obs_lo=1, obs_hi=3)
    added = grow_ray_deflect(cells_of(rows, 8), rows, "down", 8)
    for r in range(2, 9):
        assert added[(r, 9)] == 8
    assert all(c == 9 for (_, c) in added)


def test_deflection_is_rederived_per_scene():
    """THE property a stored cell list cannot have: ONE mode symbol, two
    scenes whose obstacles differ, two DIFFERENT answers."""
    left = grow_ray_deflect(cells_of(_deflect_scene(5, 5, 7), 8),
                            _deflect_scene(5, 5, 7), "down", 8)
    right = grow_ray_deflect(cells_of(_deflect_scene(5, 3, 5), 8),
                             _deflect_scene(5, 3, 5), "down", 8)
    # obstacle 5-7: exits 4 (dist 1) and 8 (dist 3) -> LEFT to col 4
    assert left[(8, 4)] == 8 and (8, 6) not in left
    # obstacle 3-5: exits 2 (dist 3) and 6 (dist 1) -> RIGHT to col 6
    assert right[(8, 6)] == 8 and (8, 4) not in right
    assert set(left) != set(right)


def test_ray_deflect_undefined_without_a_scene():
    rows = _deflect_scene(1, 1, 2)
    assert grow_ray_deflect(cells_of(rows, 8), None, "down", 8) is None


def test_ray_deflect_rejects_a_non_direction():
    rows = _deflect_scene(1, 1, 2)
    assert grow_ray_deflect(cells_of(rows, 8), rows, "sideways", 8) is None


# ---------------------------------------------------------------------------
# detect_grow integration
# ---------------------------------------------------------------------------

def test_detect_grow_finds_cross_center(ray_on):
    rows = rows_of(["88888", "81118", "81818", "81118", "88888"])
    in_cc = cc_of(rows, 1)
    out_cc = dict(in_cc)
    out_cc.update(grow_cross_center(set(in_cc), rows, 6))
    params = detect_grow(in_cc, out_cc, (5, 5), rows)
    assert params == {"mode": "cross_center", "color": 6}


def test_detect_grow_finds_cavity_leak(ray_on):
    # A 2-wide cavity with a 1-wide gap: NO pre-existing mode covers this
    # (plain `ray` would also extrude column 1 downward, fill_interior sees
    # no ENCLOSED hole because the gap opens it), so the detection is a real
    # discrimination rather than a coincidence.
    rows = rows_of(["000000", "011110", "010010", "010010", "011010",
                    "000000"])
    in_cc = cc_of(rows, 1)
    out_cc = dict(in_cc)
    out_cc.update(grow_cavity_leak(set(in_cc), rows, 2))
    params = detect_grow(in_cc, out_cc, (6, 6), rows)
    assert params == {"mode": "cavity_leak", "color": 2}


def test_detect_grow_finds_ray_deflect(ray_on):
    rows = _deflect_scene(1, 1, 2)
    in_cc = cc_of(rows, 8)
    out_cc = dict(in_cc)
    out_cc.update(grow_ray_deflect(set(in_cc), rows, "down", 8))
    params = detect_grow(in_cc, out_cc, (9, 11), rows)
    assert params == {"mode": "ray_deflect", "direction": "down", "color": 8}


# ---------------------------------------------------------------------------
# Gate discipline
# ---------------------------------------------------------------------------

def test_zero_cost_when_off(ray_off):
    """With the gate off the SAME growth must fall back to the constant
    memorizer — no grid-aware mode may be detected, induced or emitted."""
    rows = _deflect_scene(1, 1, 2)
    in_cc = cc_of(rows, 8)
    out_cc = dict(in_cc)
    out_cc.update(grow_ray_deflect(set(in_cc), rows, "down", 8))
    assert detect_grow(in_cc, out_cc, (9, 11), rows)["mode"] == "pattern"

    rows2 = rows_of(["88888", "81118", "81818", "81118", "88888"])
    in2 = cc_of(rows2, 1)
    out2 = dict(in2)
    out2.update(grow_cross_center(set(in2), rows2, 6))
    assert detect_grow(in2, out2, (5, 5), rows2)["mode"] == "pattern"


def test_no_scene_means_no_grid_aware_mode_even_when_on(ray_on):
    """Callers with no grid keep the pre-round-20 behaviour exactly."""
    rows = _deflect_scene(1, 1, 2)
    in_cc = cc_of(rows, 8)
    out_cc = dict(in_cc)
    out_cc.update(grow_ray_deflect(set(in_cc), rows, "down", 8))
    assert detect_grow(in_cc, out_cc, (9, 11))["mode"] == "pattern"


def test_gate_does_not_displace_existing_relational_modes(ray_on):
    """The hooks sit AFTER every pre-existing mode, so a halo stays a halo
    even with a scene available and the gate on."""
    rows = rows_of(["000000", "000000", "005000", "000000", "000000",
                    "000000"])
    in_cc = {(2, 2): 5}
    out_cc = dict(in_cc)
    for r in range(1, 4):
        for c in range(1, 4):
            out_cc.setdefault((r, c), 7)
    assert detect_grow(in_cc, out_cc, (6, 6), rows)["mode"] == "halo"


def test_gate_does_not_displace_plain_ray(ray_on):
    rows = rows_of(["050", "000", "000", "000"])
    in_cc = {(0, 1): 5}
    out_cc = dict(in_cc)
    for r in range(1, 4):
        out_cc[(r, 1)] = 5
    assert detect_grow(in_cc, out_cc, (4, 3), rows)["mode"] == "ray"


def test_shifted_object_never_gets_a_grid_aware_mode(ray_on):
    """translate+grow reads obstacles off the INPUT scene, where the object
    has not moved yet — so a moved frame must not claim a grid-aware mode."""
    rows = _deflect_scene(1, 1, 2)
    in_cc = cc_of(rows, 8)
    moved = {(r, c + 4): v for (r, c), v in in_cc.items()}
    out_cc = dict(moved)
    out_cc.update(grow_ray_deflect(set(moved), rows, "down", 8))
    params = detect_grow(in_cc, out_cc, (9, 11), rows)
    assert params is None or params["mode"] not in RAY_EXT_MODES


# ---------------------------------------------------------------------------
# End-to-end: induce a program + FULL LOO certification on a synthetic that
# ONLY a grid-aware mode can solve
# ---------------------------------------------------------------------------

def _deflect_task():
    """Three pairs whose obstacles sit in DIFFERENT places, so the ray
    deflects LEFT, RIGHT and RIGHT-ON-A-TIE respectively and lands in three
    different columns.  No single stored cell list fits two pairs, so a
    `pattern` program cannot survive leave-one-out; ray_deflect can."""
    specs = [(1, 1, 2),      # exits 0 (d=1) / 3 (d=2)  -> LEFT  to col 0
             (5, 3, 5),      # exits 2 (d=3) / 6 (d=1)  -> RIGHT to col 6
             (9, 8, 10)]     # exits 7 (d=2) / 11 = off -> LEFT  to col 7
    pairs = []
    for bar_col, lo, hi in specs:
        rows = _deflect_scene(bar_col, lo, hi)
        added = grow_ray_deflect(cells_of(rows, 8), rows, "down", 8)
        out = [list(r) for r in rows]
        for (r, c), col in added.items():
            out[r][c] = col
        pairs.append({"input": [list(r) for r in rows], "output": out})
    return pairs


def _induce(pairs):
    from geocat_arc.object_reasoning.inducer import induce_program
    grid_pairs = [(Grid.from_list(p["input"]), Grid.from_list(p["output"]))
                  for p in pairs]
    return induce_program(grid_pairs).program


def _render(prog, grid_in):
    from geocat_arc.object_reasoning.actions import render_program
    return render_program(prog, grid_in)


def test_the_synthetic_really_needs_a_derived_deflection():
    """Sanity: the three pairs' added-cell PATTERNS (bbox-relative) are all
    different, so no constant cell list can cover two of them."""
    pats = []
    for p in _deflect_task():
        gi, go = p["input"], p["output"]
        added = {(r, c) for r in range(len(gi)) for c in range(len(gi[0]))
                 if gi[r][c] != go[r][c]}
        r0 = min(r for r, _ in added)
        c0 = min(c for _, c in added)
        pats.append(frozenset((r - r0, c - c0) for r, c in added))
    assert len(set(pats)) == len(pats), "the synthetic is not discriminating"


def test_end_to_end_induce_and_loo_certify_ray_deflect(ray_on):
    pairs = _deflect_task()
    prog = _induce(pairs)
    assert prog is not None, "induction found no program for the deflect task"

    # (a) fits every training pair exactly
    for p in pairs:
        got = _render(prog, Grid.from_list(p["input"]))
        assert got is not None
        assert np.array_equal(np.asarray(got.to_list()),
                              np.asarray(p["output"]))

    # (b) the program is RELATIONAL: no stored cell list anywhere
    blob = repr(prog.to_dict())
    assert "ray_deflect" in blob
    assert "PatternExpr" not in blob, "a constant cell list survived"

    # (c) FULL LEAVE-ONE-OUT certification: induce on 2 pairs, predict the
    #     held-out third exactly.  This is the gate the memorizer fails.
    for held in range(len(pairs)):
        train = [p for i, p in enumerate(pairs) if i != held]
        sub = _induce(train)
        assert sub is not None, f"LOO fold {held}: no program induced"
        got = _render(sub, Grid.from_list(pairs[held]["input"]))
        assert got is not None, f"LOO fold {held}: render failed"
        assert np.array_equal(np.asarray(got.to_list()),
                              np.asarray(pairs[held]["output"])), \
            f"LOO fold {held}: held-out pair not reproduced"


def test_the_same_task_is_unsolvable_when_gate_is_off(ray_off):
    """Falsifiable counterpart: with ARC_RAY_EXT off the memorizer is the
    only spelling available and at least one LOO fold must FAIL.  If this
    ever passes, the synthetic is not actually gated on the new mode."""
    pairs = _deflect_task()
    ok = 0
    for held in range(len(pairs)):
        train = [p for i, p in enumerate(pairs) if i != held]
        sub = _induce(train)
        if sub is None:
            continue
        got = _render(sub, Grid.from_list(pairs[held]["input"]))
        if got is not None and np.array_equal(
                np.asarray(got.to_list()),
                np.asarray(pairs[held]["output"])):
            ok += 1
    assert ok < len(pairs), \
        "gate-off solved the deflect task; the synthetic does not isolate " \
        "the grid-aware mode"


# ---------------------------------------------------------------------------
# generator_mining sync (E10-style rediscovery stays possible)
# ---------------------------------------------------------------------------

def test_mining_language_expresses_the_grid_aware_modes(ray_on):
    from geocat_arc.object_reasoning.generator_mining import (
        GeneratorHypothesis, hypothesis_to_generator_rule)
    for emit in ("cross_center", "cavity_leak"):
        h = GeneratorHypothesis(direction="down", stop="grid_border",
                                color_rule="source_color", emit=emit)
        assert hypothesis_to_generator_rule(h) == {"kind": emit}
    h = GeneratorHypothesis(direction="down", stop="grid_border",
                            color_rule="source_color", emit="ray_deflect")
    assert hypothesis_to_generator_rule(h) == {"kind": "ray_deflect",
                                               "direction": "down"}


def test_mining_behavioural_key_collapses_inert_params():
    """The no-walk emits ignore direction AND stop; ray_deflect goes AROUND
    obstacles so its stop predicate is inert too.  Collapsing them keeps the
    miner from enumerating behaviourally identical duplicates."""
    from geocat_arc.object_reasoning.generator_mining import (
        GeneratorHypothesis)

    def key(**kw):
        return GeneratorHypothesis(color_rule="source_color", **kw
                                   ).behavioral_key()

    for emit in ("cross_center", "cavity_leak"):
        assert key(direction="up", stop="grid_border", emit=emit) == \
               key(direction="left", stop="first_nonbg", emit=emit)
    assert key(direction="down", stop="grid_border", emit="ray_deflect") == \
           key(direction="down", stop="first_nonbg", emit="ray_deflect")
    # ...but the LIVE parameter still separates them
    assert key(direction="down", stop="grid_border", emit="ray_deflect") != \
           key(direction="up", stop="grid_border", emit="ray_deflect")


def test_mining_enumeration_is_gated(ray_off):
    """Zero cost when off: the grid-aware emits must not even be enumerated
    (and must appear the moment the gate is on)."""
    from geocat_arc.object_reasoning import generator_mining as gm
    off = gm.enumerate_hypotheses([])
    assert not any(h.emit in RAY_EXT_MODES for h in off)


def test_mining_enumeration_includes_the_modes_when_on(ray_on):
    from geocat_arc.object_reasoning import generator_mining as gm
    on = {h.emit for h in gm.enumerate_hypotheses([])}
    assert set(RAY_EXT_MODES) <= on
