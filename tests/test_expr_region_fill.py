"""Expression-grammar round: computed-region pattern productions.

The productions must be inert with ARC_EXPR_GRAMMAR unset, must compute
their regions from the object (never store cells), and must round-trip
through serialization like every other parameter expression.
"""
from __future__ import annotations

from geocat_arc.object_reasoning.expressions import Expr, PatternExpr
from geocat_arc.object_reasoning.growth import (
    HOLE_FEATURES,
    _expr_grammar_enabled,
    _hole_fill_observation,
    enclosed_hole_offsets,
    enclosed_hole_regions,
    grow_fill_holes,
    hole_feature_value,
)


class _Obj:
    """Minimal stand-in carrying the only attribute these helpers read."""

    def __init__(self, cells):
        self.cells = frozenset(cells)


RING = _Obj({(1, 1), (1, 2), (1, 3), (2, 1), (2, 3), (3, 1), (3, 2), (3, 3)})
TWO_HOLES = _Obj({(0, 0), (0, 1), (0, 2), (0, 3), (0, 4),
                  (1, 0), (1, 2), (1, 4),
                  (2, 0), (2, 1), (2, 2), (2, 3), (2, 4)})
SOLID = _Obj({(0, 0), (0, 1), (1, 0), (1, 1)})


class TestRegionExtraction:
    def test_ring_encloses_one_cell(self):
        assert enclosed_hole_offsets(RING, None) == ((1, 1),)

    def test_solid_block_encloses_nothing(self):
        assert enclosed_hole_offsets(SOLID, None) == ()
        assert enclosed_hole_regions(SOLID) == []

    def test_regions_are_separate_components(self):
        regions = enclosed_hole_regions(TWO_HOLES)
        assert regions == [frozenset({(1, 1)}), frozenset({(1, 3)})]

    def test_region_keys_are_computed_not_stored(self):
        region = enclosed_hole_regions(TWO_HOLES)[0]
        assert hole_feature_value(region, "area") == 1
        assert hole_feature_value(region, "hw") == (1, 1)
        assert hole_feature_value(region, "shape") == ((0, 0),)


class TestFillHoles:
    def test_fills_every_region_from_the_table(self):
        added = grow_fill_holes(TWO_HOLES, "area", {1: 7})
        assert added == {(1, 1): 7, (1, 3): 7}

    def test_unknown_key_contributes_no_cells(self):
        assert grow_fill_holes(TWO_HOLES, "area", {99: 7}) is None

    def test_undefined_without_an_enclosed_region(self):
        assert grow_fill_holes(SOLID, "area", {1: 7}) is None


class TestObservation:
    def test_observation_is_hashable_and_serializable(self):
        obs = _hole_fill_observation(RING.cells, {(2, 2): 7})
        assert obs is not None and obs["mode"] == "fill_holes"
        table = dict(obs["hole_colors"])
        assert set(table) <= set(HOLE_FEATURES)
        hash(obs["hole_colors"])          # raw params feed signature keys

    def test_cells_outside_every_region_reject(self):
        assert _hole_fill_observation(RING.cells, {(2, 2): 7, (9, 9): 3}) is None

    def test_partial_region_fill_rejects(self):
        # only one of the two holes filled solid is fine; half a hole is not
        big = _Obj({(0, 0), (0, 1), (0, 2), (0, 3),
                    (1, 0), (1, 3),
                    (2, 0), (2, 3),
                    (3, 0), (3, 1), (3, 2), (3, 3)})
        assert _hole_fill_observation(big.cells, {(1, 1): 5}) is None


class TestGating:
    def test_gate_reads_env_at_call_time(self, monkeypatch):
        monkeypatch.delenv("ARC_EXPR_GRAMMAR", raising=False)
        assert _expr_grammar_enabled() is False
        monkeypatch.setenv("ARC_EXPR_GRAMMAR", "1")
        assert _expr_grammar_enabled() is True

    def test_observation_only_offered_through_detect_when_gated(self,
                                                                monkeypatch):
        # two enclosed regions filled with DIFFERENT colours: the existing
        # single-colour modes cannot spell it, so this is the case the
        # per-region production exists for.
        from geocat_arc.object_reasoning.growth import detect_grow
        holed = _Obj({(0, 0), (0, 1), (0, 2), (0, 3), (0, 4), (0, 5),
                      (1, 0), (1, 2), (1, 5),
                      (2, 0), (2, 1), (2, 2), (2, 3), (2, 4), (2, 5)})
        in_cc = {c: 3 for c in holed.cells}
        out_cc = dict(in_cc)
        out_cc[(1, 1)] = 7                      # 1-cell region
        out_cc[(1, 3)] = out_cc[(1, 4)] = 6     # 2-cell region, other colour
        monkeypatch.delenv("ARC_EXPR_GRAMMAR", raising=False)
        off = detect_grow(in_cc, out_cc, (5, 5))
        assert off is not None and off["mode"] == "pattern"   # memorized
        monkeypatch.setenv("ARC_EXPR_GRAMMAR", "1")
        on = detect_grow(in_cc, out_cc, (5, 5))
        assert on is not None and on["mode"] == "fill_holes"
        # keyed on a computed region feature (here the region's position
        # within the object distinguishes them), never on stored cells
        assert dict(on["hole_colors"])


class TestSerialization:
    def test_pattern_exprs_round_trip(self):
        for expr in (PatternExpr(op="enclosed_holes"),
                     PatternExpr(op="hole_map", args=("area", ((1, 7),)))):
            assert Expr.from_dict(expr.to_dict()) == expr

    def test_size_counts_table_entries_not_cells(self):
        assert PatternExpr(op="enclosed_holes").size == 1
        assert PatternExpr(op="hole_map",
                           args=("area", ((1, 7), (4, 3)))).size == 3
