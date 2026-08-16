"""ROUND 19 — EXTENSIONAL PATTERN DERIVATION (ARC_PATTERN_DERIVE).

The R19 traces found that 43% of divergent tasks fail because GROW falls
back to mode=pattern, which stores LITERAL bbox-relative cell coordinates.
These tests cover the three DERIVED modes that replace it:

  periodic_self   — repeat the object at its OWN internal period
  periodic_bbox   — repeat the object at its OWN bbox extent
  frame_minority  — solid ring, thickness = minority-cell COUNT, colour =
                    that minority colour

The contract that matters: every parameter is recomputed from the object at
render time, so a held-out pair with a DIFFERENT object gets a DIFFERENT
(correct) answer.  test_period_is_rederived_per_object and the end-to-end
LOO certification below are the tests that actually pin that down.
"""
from __future__ import annotations

import os

import numpy as np
import pytest

from geocat_arc.object_reasoning.growth import (
    GROW_MODES,
    PATTERN_DERIVE_MODES,
    detect_grow,
    grow_frame_minority,
    grow_periodic,
    self_period,
)
from geocat_arc.perception.grid import Grid


@pytest.fixture
def derive_on(monkeypatch):
    monkeypatch.setenv("ARC_PATTERN_DERIVE", "1")


@pytest.fixture
def derive_off(monkeypatch):
    monkeypatch.delenv("ARC_PATTERN_DERIVE", raising=False)


def cc_of(rows, bg=0):
    """{(r, c): colour} for every non-background cell of a row-string grid.
    '.' is always empty; digits equal to ``bg`` are empty too."""
    return {(r, c): int(v) for r, row in enumerate(rows)
            for c, v in enumerate(row) if v != "." and int(v) != bg}


# ---------------------------------------------------------------------------
# Vocabulary wiring
# ---------------------------------------------------------------------------

def test_modes_registered_before_pattern_fallback():
    """The derived spellings must OUTRANK the constant memorizer, or the
    inducer's preference order would still pick the cell list."""
    for mode in PATTERN_DERIVE_MODES:
        assert mode in GROW_MODES
        assert GROW_MODES.index(mode) < GROW_MODES.index("pattern")


# ---------------------------------------------------------------------------
# self_period
# ---------------------------------------------------------------------------

def test_self_period_finds_true_horizontal_period():
    # "1221221" is 3-periodic; the strict occupancy+colour test must not be
    # fooled into reporting 1 or 2.
    cc = cc_of(["1221221"])
    assert self_period(cc, "h") == 3


def test_self_period_rejects_aperiodic_object():
    assert self_period(cc_of(["12345"]), "h") is None


def test_self_period_requires_occupancy_agreement_not_just_colour():
    # Same colour everywhere, but the HOLES break every short period:
    # occupancy must count, else p=1 would be accepted.
    cc = cc_of(["1.1.1"])
    assert self_period(cc, "h") == 2


# ---------------------------------------------------------------------------
# periodic_self / periodic_bbox rendering
# ---------------------------------------------------------------------------

def test_periodic_self_continues_to_border():
    cc = cc_of(["1221221"])            # period 3, cols 0..6
    added = grow_periodic(cc, "right", (1, 13), "self")
    assert added is not None
    # cols 7..12 filled by continuing the period; nothing before col 7
    assert min(c for _, c in added) == 7
    assert max(c for _, c in added) == 12
    # col 7 continues the cycle: col 7 <- col 4 = '2'
    assert added[(0, 7)] == 2
    assert added[(0, 9)] == 1          # col 9 <- col 6 = '1'


def test_periodic_bbox_tiles_at_own_bbox_extent():
    # A 2-row block with NO internal period tiles upward at its own height.
    cc = cc_of([".....", ".....", "12...", "34..."])
    added = grow_periodic(cc, "up", (4, 5), "bbox")
    assert added == {(0, 0): 1, (0, 1): 2, (1, 0): 3, (1, 1): 4}


def test_periodic_carries_source_colours_not_a_constant():
    cc = cc_of(["12", "34"])
    added = grow_periodic(cc, "down", (4, 2), "bbox")
    assert added == {(2, 0): 1, (2, 1): 2, (3, 0): 3, (3, 1): 4}


def test_periodic_stops_at_grid_border_and_clips():
    # 2-row diagonal domino: bbox height 2, so copies land at rows 2/3 then
    # 4/5.  Row 5 is off-grid, so that copy is CLIPPED, not dropped whole.
    cc = cc_of(["1.", ".1"])
    added = grow_periodic(cc, "down", (5, 2), "bbox")
    assert set(added) == {(2, 0), (3, 1), (4, 0)}


def test_periodic_returns_none_when_undefined():
    cc = cc_of(["12345"])
    assert grow_periodic(cc, "right", (1, 10), "self") is None   # no period
    assert grow_periodic(cc, "sideways", (1, 10), "bbox") is None
    assert grow_periodic({}, "right", (5, 5), "bbox") is None


def test_period_is_rederived_per_object():
    """THE POINT OF THE ROUND: one mode symbol, different objects, different
    periods.  A stored cell list could not do this."""
    a = grow_periodic(cc_of(["1212"]), "right", (1, 8), "self")
    b = grow_periodic(cc_of(["123123"]), "right", (1, 12), "self")
    assert self_period(cc_of(["1212"]), "h") == 2
    assert self_period(cc_of(["123123"]), "h") == 3
    assert a is not None and b is not None
    assert a != b


# ---------------------------------------------------------------------------
# frame_minority
# ---------------------------------------------------------------------------

def test_frame_minority_thickness_equals_minority_count():
    # 3x3 block of 4s with ONE cell of 3 -> ring of thickness 1, colour 3.
    cc = cc_of(["....", ".444", ".434", ".444"], bg=0)
    added = grow_frame_minority(cc, (7, 7))
    assert added is not None
    assert set(added.values()) == {3}
    # bbox rows 1..3 cols 1..3 grown by 1 -> ring rows 0..4 cols 0..4 minus bbox
    assert len(added) == 5 * 5 - 3 * 3
    assert (0, 0) in added and (4, 4) in added
    assert (2, 2) not in added


def _block_with_minorities(n_minor):
    """A 4x4 block of 4s at rows/cols 3..6 carrying ``n_minor`` cells of
    colour 2 — the 52fd389e shape, with room for the ring."""
    cc = {(r, c): 4 for r in range(3, 7) for c in range(3, 7)}
    for i in range(n_minor):
        cc[(3 + i, 3 + i)] = 2
    return cc


def test_frame_minority_thickness_scales_with_count():
    # TWO minority cells -> thickness 2, THREE -> thickness 3 (the counting
    # relation traced on 52fd389e across four objects).
    for n in (2, 3):
        cc = _block_with_minorities(n)
        added = grow_frame_minority(cc, (20, 20))
        assert added is not None
        assert set(added.values()) == {2}
        assert len(added) == (4 + 2 * n) ** 2 - 4 * 4


def test_frame_minority_undefined_cases():
    # single colour -> no minority
    assert grow_frame_minority(cc_of(["44", "44"]), (9, 9)) is None
    # three colours -> ambiguous
    assert grow_frame_minority(cc_of(["12", "34"]), (9, 9)) is None
    # tie -> no unambiguous minority
    assert grow_frame_minority(cc_of(["12"]), (9, 9)) is None
    # ring would leave the grid -> undefined, NOT silently clipped (clipping
    # would let the mode fit train pairs it cannot reproduce)
    assert grow_frame_minority(cc_of([".444", ".434", ".444"]), (3, 4)) is None


# ---------------------------------------------------------------------------
# detect_grow integration + the env gate
# ---------------------------------------------------------------------------

def test_detect_grow_finds_periodic_self(derive_on):
    in_cc = cc_of(["1221221"])
    added = grow_periodic(in_cc, "right", (1, 13), "self")
    out_cc = dict(in_cc)
    out_cc.update(added)
    params = detect_grow(in_cc, out_cc, (1, 13))
    assert params == {"mode": "periodic_self", "direction": "right"}


def test_detect_grow_finds_periodic_bbox(derive_on):
    in_cc = cc_of([".....", ".....", "12...", "34..."])
    out_cc = dict(in_cc)
    out_cc.update(grow_periodic(in_cc, "up", (4, 5), "bbox"))
    params = detect_grow(in_cc, out_cc, (4, 5))
    assert params == {"mode": "periodic_bbox", "direction": "up"}


def test_detect_grow_finds_frame_minority(derive_on):
    # thickness 2: a thickness-1 ring is indistinguishable from halo(conn=8),
    # which is tried first and legitimately wins there.
    in_cc = _block_with_minorities(2)
    out_cc = dict(in_cc)
    out_cc.update(grow_frame_minority(in_cc, (20, 20)))
    params = detect_grow(in_cc, out_cc, (20, 20))
    assert params == {"mode": "frame_minority"}


def test_zero_cost_when_off(derive_off):
    """With the gate off the SAME growth must fall back to the constant
    memorizer — no derived mode may be detected, induced or emitted."""
    in_cc = cc_of(["1221221"])
    out_cc = dict(in_cc)
    out_cc.update(grow_periodic(in_cc, "right", (1, 13), "self"))
    params = detect_grow(in_cc, out_cc, (1, 13))
    assert params["mode"] == "pattern"

    in_cc2 = _block_with_minorities(2)
    out_cc2 = dict(in_cc2)
    out_cc2.update(grow_frame_minority(in_cc2, (20, 20)))
    assert detect_grow(in_cc2, out_cc2, (20, 20))["mode"] == "pattern"


def test_gate_does_not_displace_existing_relational_modes(derive_on):
    """The hooks sit AFTER every pre-existing mode, so a halo stays a halo
    even when a derived mode could also cover it."""
    in_cc = {(2, 2): 5}
    out_cc = dict(in_cc)
    for r in range(1, 4):
        for c in range(1, 4):
            out_cc.setdefault((r, c), 7)
    assert detect_grow(in_cc, out_cc, (6, 6))["mode"] == "halo"


# ---------------------------------------------------------------------------
# End-to-end: induce a program + FULL LOO certification on a synthetic that
# ONLY a derived mode can solve
# ---------------------------------------------------------------------------

def _periodic_task():
    """Three pairs whose strips have DIFFERENT periods (2, 3, 4) and
    DIFFERENT colours.  No single stored cell list fits more than one pair,
    so a `pattern` program cannot survive leave-one-out; periodic_self can.
    """
    W = 12
    pairs = []
    for motif in ([1, 2], [3, 4, 5], [6, 7, 8, 9]):
        p = len(motif)
        row_in = [0] * W
        for i in range(2 * p):                 # two visible periods
            row_in[i] = motif[i % p]
        row_out = [motif[i % p] for i in range(W)]
        pairs.append({"input": [row_in], "output": [row_out]})
    return pairs


def _induce(pairs):
    """Induce and return the ObjectProgram (None when induction found none)."""
    from geocat_arc.object_reasoning.inducer import induce_program
    grid_pairs = [(Grid.from_list(p["input"]), Grid.from_list(p["output"]))
                  for p in pairs]
    return induce_program(grid_pairs).program


def _render(prog, grid_in):
    from geocat_arc.object_reasoning.actions import render_program
    return render_program(prog, grid_in)


def test_end_to_end_induce_and_loo_certify_periodic(derive_on):
    pairs = _periodic_task()
    prog = _induce(pairs)
    assert prog is not None, "induction found no program for the periodic task"

    # (a) fits every training pair exactly
    for p in pairs:
        got = _render(prog, Grid.from_list(p["input"]))
        assert got is not None
        assert np.array_equal(np.asarray(got.to_list()),
                              np.asarray(p["output"]))

    # (b) the program is RELATIONAL: no stored cell list anywhere
    blob = repr(prog.to_dict())
    assert "periodic_self" in blob or "periodic_bbox" in blob
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


def test_the_same_task_is_unsolvable_when_gate_is_off(derive_off):
    """Falsifiable counterpart: with ARC_PATTERN_DERIVE off, the memorizer is
    the only spelling available and at least one LOO fold must FAIL.  If this
    ever passes, the synthetic is not actually gated on the new mode."""
    pairs = _periodic_task()
    ok = 0
    for held in range(len(pairs)):
        train = [p for i, p in enumerate(pairs) if i != held]
        sub = _induce(train)
        if sub is None:
            continue
        got = _render(sub, Grid.from_list(pairs[held]["input"]))
        if got is not None and np.array_equal(np.asarray(got.to_list()),
                                              np.asarray(pairs[held]["output"])):
            ok += 1
    assert ok < len(pairs), \
        "gate-off solved the periodic task; the synthetic does not isolate " \
        "the derived mode"


# ---------------------------------------------------------------------------
# generator_mining sync (E10-style rediscovery stays possible)
# ---------------------------------------------------------------------------

def test_mining_language_expresses_the_derived_modes(derive_on):
    from geocat_arc.object_reasoning.generator_mining import (
        GeneratorHypothesis, hypothesis_to_generator_rule)
    h = GeneratorHypothesis(direction="right", stop="grid_border",
                            color_rule="source_color", emit="periodic_self")
    assert hypothesis_to_generator_rule(h) == {"kind": "periodic_self",
                                               "direction": "right"}
    f = GeneratorHypothesis(direction="up", stop="grid_border",
                            color_rule="source_color", emit="frame_minority")
    assert hypothesis_to_generator_rule(f) == {"kind": "frame_minority"}


def test_mining_behavioural_key_collapses_inert_params():
    from geocat_arc.object_reasoning.generator_mining import GeneratorHypothesis
    a = GeneratorHypothesis(direction="up", stop="grid_border",
                            color_rule="source_color", emit="frame_minority")
    b = GeneratorHypothesis(direction="left", stop="first_nonbg",
                            color_rule="source_color", emit="frame_minority")
    assert a.behavioral_key() == b.behavioral_key()
    # ...but direction stays live for the periodic emits
    c = GeneratorHypothesis(direction="up", stop="grid_border",
                            color_rule="source_color", emit="periodic_bbox")
    d = GeneratorHypothesis(direction="down", stop="grid_border",
                            color_rule="source_color", emit="periodic_bbox")
    assert c.behavioral_key() != d.behavioral_key()


def test_generative_kind_renders(derive_on):
    from geocat_arc.object_reasoning.generative import _apply_generator
    from geocat_arc.object_reasoning.types import MultiColorObject
    cells = frozenset({(0, 0), (0, 1), (0, 2), (0, 3)})
    obj = MultiColorObject(id=0, color=1, cells=cells,
                           bounding_box=(0, 0, 0, 3),
                           cell_colors={(0, 0): 1, (0, 1): 2,
                                        (0, 2): 1, (0, 3): 2})
    added = _apply_generator({"kind": "periodic_self", "direction": "right"},
                             obj, (1, 8))
    assert added == {(0, 4): 1, (0, 5): 2, (0, 6): 1, (0, 7): 2}
