"""Unit tests for object_reasoning.correspondence (Sections 3.1 / 3.2).

Two layers:

1. Real dev-set pairs (STAGE1_REQUIREMENTS Section 7.1), one per required
   phenomenon:
     - 05f2a901: motion        (TRANSLATE deltas, S1 segmentation)
     - 0a2355a6: recolor       (RECOLOR-in-place deltas, S1)
     - 88a10436: copy          (one-to-many COPY, multicolor S3)
   Each asserts a NON-LOSSY correspondence (is_object_preserving, zero
   unreconciled pixels == exact re-render of the output grid from the
   extracted deltas) on EVERY train pair.

2. Synthetic micro-grids pinning each delta type's minimal-delta semantics
   (DELETE, COPY one-to-many, RECOLOR, TRANSLATE, COMPOSITE, REFLECT,
   ROTATE, SCALE up/down), the lossy flag, the reconciliation tolerance,
   alternative dedup/ordering, and ObjectDelta JSON round-trips.

No task-ID conditionals: task ids appear only as data-loading arguments.
"""
from __future__ import annotations

import json

import numpy as np
import pytest

from geocat_arc.data.arc_loader import load_task
from geocat_arc.perception.grid import Grid
from geocat_arc.object_reasoning import segmentation as seg
from geocat_arc.object_reasoning.correspondence import (
    MATCH_THRESHOLD,
    RECONCILE_TOLERANCE,
    WEIGHT_PROFILES,
    _predict_cells,
    delta_histogram,
    extract_deltas,
    match_pair,
    reconcile_with_pixels,
)
from geocat_arc.object_reasoning.types import (
    DeltaType,
    ObjectDelta,
    SegmentationVariant,
    to_grid_pairs,
)

S1 = SegmentationVariant.S1_SAME_COLOR_4
S3 = SegmentationVariant.S3_MULTICOLOR_4


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def grid(rows: list[list[int]]) -> Grid:
    return Grid(np.array(rows, dtype=np.int32))


def dev_pairs(task_id: str) -> list[tuple[Grid, Grid]]:
    task = load_task(task_id)
    return to_grid_pairs([(np.array(p.input), np.array(p.output))
                          for p in task.train])


def segmented(gin: Grid, gout: Grid, variant: SegmentationVariant):
    bg = seg.background_for(gin, variant)
    return seg.segment(gin, variant, bg), seg.segment(gout, variant, bg)


def alternatives(gin: Grid, gout: Grid, variant: SegmentationVariant,
                 pair_index: int = 0):
    in_objs, out_objs = segmented(gin, gout, variant)
    return match_pair(in_objs, out_objs, gin, gout, pair_index=pair_index)


def best(gin: Grid, gout: Grid, variant: SegmentationVariant,
         pair_index: int = 0):
    return alternatives(gin, gout, variant, pair_index)[0]


def rerender_from_deltas(corr, gout: Grid) -> np.ndarray:
    """Independent exact re-render check: apply the extracted deltas to the
    input objects on a fresh canvas (background = most frequent color of the
    cells no output object covers) and return the canvas."""
    out = gout.to_numpy()
    covered = set().union(*[o.cells for o in corr.output_objects]) \
        if corr.output_objects else set()
    uncovered = [int(out[r, c]) for r in range(out.shape[0])
                 for c in range(out.shape[1]) if (r, c) not in covered]
    bg = max(set(uncovered), key=uncovered.count) if uncovered \
        else int(gout.background_color)
    canvas = np.full(out.shape, bg, dtype=out.dtype)
    in_by_id = {o.id: o for o in corr.input_objects}
    for d in extract_deltas(corr):
        if d.delta_type is DeltaType.DELETE or d.input_object_id is None:
            continue
        for (r, c), col in _predict_cells(d, in_by_id[d.input_object_id]).items():
            if 0 <= r < out.shape[0] and 0 <= c < out.shape[1]:
                canvas[r, c] = col
    return canvas


def assert_non_lossy_exact(corr, gout: Grid) -> None:
    assert corr.is_object_preserving, \
        f"expected non-lossy correspondence, got {corr.unreconciled_pixels} " \
        f"unreconciled pixels (profile={corr.weights_profile})"
    assert corr.unreconciled_pixels == 0
    # Independent re-render must reproduce the output grid EXACTLY.
    assert np.array_equal(rerender_from_deltas(corr, gout), gout.to_numpy())


# ---------------------------------------------------------------------------
# Real dev-set pairs (Section 7.1)
# ---------------------------------------------------------------------------

class TestMotion05f2a901:
    """05f2a901: one object moves until adjacent to a fixed target (S1)."""

    @pytest.fixture(scope="class")
    def pairs(self):
        return dev_pairs("05f2a901")

    def test_non_lossy_exact_rerender_every_pair(self, pairs):
        for i, (gin, gout) in enumerate(pairs):
            corr = best(gin, gout, S1, pair_index=i)
            assert_non_lossy_exact(corr, gout)

    def test_deltas_are_one_translate_one_keep(self, pairs):
        for i, (gin, gout) in enumerate(pairs):
            corr = best(gin, gout, S1, pair_index=i)
            deltas = extract_deltas(corr)
            hist = delta_histogram(deltas)
            assert hist == {"translate": 1, "keep": 1}
            [tr] = [d for d in deltas if d.delta_type is DeltaType.TRANSLATE]
            assert tr.residual_pixels == 0
            assert (tr.params["dr"], tr.params["dc"]) != (0, 0)
            assert tr.pair_index == i
            assert len(tr.output_object_ids) == 1


class TestRecolor0a2355a6:
    """0a2355a6: every object recolors in place by an intrinsic feature (S1)."""

    @pytest.fixture(scope="class")
    def pairs(self):
        return dev_pairs("0a2355a6")

    def test_non_lossy_exact_rerender_every_pair(self, pairs):
        for i, (gin, gout) in enumerate(pairs):
            corr = best(gin, gout, S1, pair_index=i)
            assert_non_lossy_exact(corr, gout)

    def test_all_deltas_recolor_in_place(self, pairs):
        for i, (gin, gout) in enumerate(pairs):
            corr = best(gin, gout, S1, pair_index=i)
            deltas = extract_deltas(corr)
            assert deltas, "expected at least one object per pair"
            assert all(d.delta_type is DeltaType.RECOLOR for d in deltas)
            assert all(d.residual_pixels == 0 for d in deltas)
            # In-place: matched output object occupies the same cells.
            in_by_id = {o.id: o for o in corr.input_objects}
            out_by_id = {o.id: o for o in corr.output_objects}
            for d in deltas:
                assert in_by_id[d.input_object_id].cells \
                    == out_by_id[d.output_object_ids[0]].cells
                assert d.params["color"] in range(10)


class TestCopyMulticolor88a10436:
    """88a10436: a multicolor object is copied onto a marker; needs S3."""

    @pytest.fixture(scope="class")
    def pairs(self):
        return dev_pairs("88a10436")

    def test_non_lossy_exact_rerender_every_pair(self, pairs):
        for i, (gin, gout) in enumerate(pairs):
            corr = best(gin, gout, S3, pair_index=i)
            assert_non_lossy_exact(corr, gout)

    def test_one_to_many_copy_plus_marker_delete(self, pairs):
        for i, (gin, gout) in enumerate(pairs):
            corr = best(gin, gout, S3, pair_index=i)
            deltas = extract_deltas(corr)
            hist = delta_histogram(deltas)
            assert hist == {"copy": 1, "delete": 1}
            [cp] = [d for d in deltas if d.delta_type is DeltaType.COPY]
            assert cp.input_object_id is not None
            assert cp.params["k"] == 2
            assert len(cp.output_object_ids) == 2
            assert len(cp.params["placements"]) == 2
            assert cp.residual_pixels == 0
            # copies map lists ALL output ids of the source input object.
            assert corr.copies[cp.input_object_id] == cp.output_object_ids

    def test_lossy_alternative_still_returned_and_ordered_last(self, pairs):
        gin, gout = pairs[0]
        alts = alternatives(gin, gout, S3, pair_index=0)
        assert len(alts) >= 2, "motion vs default profiles should disagree"
        assert alts[0].unreconciled_pixels == 0
        assert alts[0].is_object_preserving
        assert alts[-1].unreconciled_pixels > 0
        assert not alts[-1].is_object_preserving
        # Deduplication: distinct alternatives have distinct match structure.
        keys = [(tuple(sorted((a, b) for a, b, _ in c.matches)),
                 tuple(sorted((k, tuple(v)) for k, v in c.copies.items())),
                 tuple(c.deleted_input_ids), tuple(c.created_output_ids))
                for c in alts]
        assert len(keys) == len(set(keys))


def test_delta_json_round_trip_on_all_dev_pairs():
    """Every extracted delta is JSON-native and round-trips exactly."""
    for task_id, variant in (("05f2a901", S1), ("0a2355a6", S1),
                             ("88a10436", S3)):
        for i, (gin, gout) in enumerate(dev_pairs(task_id)):
            for corr in alternatives(gin, gout, variant, pair_index=i):
                for d in extract_deltas(corr):
                    payload = json.dumps(d.to_dict())      # must not raise
                    back = ObjectDelta.from_dict(json.loads(payload))
                    assert back.to_dict() == d.to_dict()


# ---------------------------------------------------------------------------
# Synthetic minimal-delta semantics (one grid per delta type)
# ---------------------------------------------------------------------------

class TestSyntheticDeltas:
    def test_delete_unmatched_input(self):
        gin = grid([[2, 2, 0, 3],
                    [2, 2, 0, 0],
                    [0, 0, 0, 0]])
        gout = grid([[2, 2, 0, 0],
                     [2, 2, 0, 0],
                     [0, 0, 0, 0]])
        corr = best(gin, gout, S1)
        assert_non_lossy_exact(corr, gout)
        hist = delta_histogram(extract_deltas(corr))
        assert hist == {"keep": 1, "delete": 1}
        assert len(corr.deleted_input_ids) == 1

    def test_copy_one_to_many(self):
        gin = grid([[4, 0, 0, 0, 0, 0],
                    [4, 4, 0, 0, 0, 0],
                    [0, 0, 0, 0, 0, 0],
                    [0, 0, 0, 0, 0, 0]])
        gout = grid([[4, 0, 0, 0, 4, 0],
                     [4, 4, 0, 0, 4, 4],
                     [0, 0, 4, 0, 0, 0],
                     [0, 0, 4, 4, 0, 0]])
        corr = best(gin, gout, S1)
        assert_non_lossy_exact(corr, gout)
        deltas = extract_deltas(corr)
        assert delta_histogram(deltas) == {"copy": 1}
        [cp] = deltas
        assert cp.params["k"] == 3
        # Primary (in-place) match is listed first; placements are
        # bbox-origin offsets per placed copy.
        assert cp.params["placements"][0] == [0, 0]
        assert sorted(map(tuple, cp.params["placements"])) \
            == [(0, 0), (0, 4), (2, 2)]
        assert "colors" not in cp.params  # verbatim copies, no recolor

    def test_recolor_in_place(self):
        gin = grid([[0, 3, 3, 0],
                    [0, 3, 3, 0]])
        gout = grid([[0, 6, 6, 0],
                     [0, 6, 6, 0]])
        corr = best(gin, gout, S1)
        assert_non_lossy_exact(corr, gout)
        [d] = extract_deltas(corr)
        assert d.delta_type is DeltaType.RECOLOR
        assert d.params == {"color": 6}

    def test_translate_moved_same_shape_and_color(self):
        gin = grid([[5, 5, 0, 0, 0, 0],
                    [0, 5, 0, 0, 0, 0],
                    [0, 0, 0, 0, 0, 0]])
        gout = grid([[0, 0, 0, 0, 0, 0],
                     [0, 0, 0, 5, 5, 0],
                     [0, 0, 0, 0, 5, 0]])
        corr = best(gin, gout, S1)
        assert_non_lossy_exact(corr, gout)
        [d] = extract_deltas(corr)
        assert d.delta_type is DeltaType.TRANSLATE
        assert d.params == {"dr": 1, "dc": 3}

    def test_composite_translate_plus_recolor(self):
        # Same mask, moved by (1, 2), uniformly recolored 1 -> 5.
        gin = grid([[1, 1, 0, 0, 0],
                    [0, 1, 0, 0, 0],
                    [0, 0, 0, 0, 0]])
        gout = grid([[0, 0, 0, 0, 0],
                     [0, 0, 5, 5, 0],
                     [0, 0, 0, 5, 0]])
        corr = best(gin, gout, S1)
        assert_non_lossy_exact(corr, gout)
        [d] = extract_deltas(corr)
        assert d.delta_type is DeltaType.COMPOSITE
        parts = [ObjectDelta.from_dict(p) for p in d.params["parts"]]
        assert [p.delta_type for p in parts] \
            == [DeltaType.TRANSLATE, DeltaType.RECOLOR]
        assert parts[0].params == {"dr": 1, "dc": 2}
        assert parts[1].params == {"color": 5}

    def test_reflect_minimal_delta(self):
        # L-tromino [[1,0],[1,1]] -> vertical flip [[0,1],[1,1]] in place.
        gin = grid([[3, 0, 0],
                    [3, 3, 0],
                    [0, 0, 0]])
        gout = grid([[0, 3, 0],
                     [3, 3, 0],
                     [0, 0, 0]])
        corr = best(gin, gout, S1)
        assert_non_lossy_exact(corr, gout)
        [d] = extract_deltas(corr)
        assert d.delta_type is DeltaType.REFLECT
        assert d.params["axis"] == "vertical"
        assert (d.params["dr"], d.params["dc"]) == (0, 0)

    def test_rotate_minimal_delta(self):
        # Z-tetromino rotated 90 CCW; no reflection reproduces it.
        gin = grid([[5, 5, 0, 0],
                    [0, 5, 5, 0],
                    [0, 0, 0, 0]])
        gout = grid([[0, 5, 0, 0],
                     [5, 5, 0, 0],
                     [5, 0, 0, 0]])
        corr = best(gin, gout, S1)
        assert_non_lossy_exact(corr, gout)
        [d] = extract_deltas(corr)
        assert d.delta_type is DeltaType.ROTATE
        assert d.params["angle"] == 90

    def test_scale_up_minimal_delta(self):
        gin = grid([[7, 7, 0, 0],
                    [0, 0, 0, 0]])
        gout = grid([[7, 7, 7, 7],
                     [7, 7, 7, 7]])
        corr = best(gin, gout, S1)
        assert_non_lossy_exact(corr, gout)
        [d] = extract_deltas(corr)
        assert d.delta_type is DeltaType.SCALE
        assert d.params["factor"] == 2

    def test_scale_down_minimal_delta(self):
        gin = grid([[7, 7, 7, 7],
                    [7, 7, 7, 7]])
        gout = grid([[7, 7, 0, 0],
                     [0, 0, 0, 0]])
        corr = best(gin, gout, S1)
        assert_non_lossy_exact(corr, gout)
        [d] = extract_deltas(corr)
        assert d.delta_type is DeltaType.SCALE
        assert d.params["factor"] == -2


# ---------------------------------------------------------------------------
# Lossy flagging, tolerance, alternatives, degenerate inputs
# ---------------------------------------------------------------------------

class TestReconciliation:
    def test_genuinely_new_shape_marks_lossy_but_is_returned(self):
        gin = grid([[2, 0, 0, 0, 0],
                    [0, 0, 0, 0, 0],
                    [0, 0, 0, 0, 0]])
        gout = grid([[2, 0, 8, 8, 8],
                     [0, 0, 8, 8, 8],
                     [0, 0, 8, 8, 8]])
        alts = alternatives(gin, gout, S1)
        assert alts, "lossy pairs must still be returned"
        corr = alts[0]
        assert not corr.is_object_preserving
        assert corr.unreconciled_pixels == 9
        # The new shape surfaces as an orphan COPY with honest residual.
        orphans = [d for d in extract_deltas(corr) if d.input_object_id is None]
        assert len(orphans) == 1
        assert orphans[0].delta_type is DeltaType.COPY
        assert orphans[0].residual_pixels == 9
        assert corr.created_output_ids == orphans[0].output_object_ids

    def test_small_residue_within_tolerance_stays_preserving(self):
        # 3x4 rectangle moves far (24 changed px) + 1 stray created pixel
        # (25 changed total); 1 unreconciled <= 0.05 * 25.
        gin_np = np.zeros((6, 12), dtype=np.int32)
        gin_np[0:3, 0:4] = 2
        gout_np = np.zeros((6, 12), dtype=np.int32)
        gout_np[0:3, 8:12] = 2
        gout_np[5, 0] = 3
        corr = best(Grid(gin_np), Grid(gout_np), S1)
        assert corr.unreconciled_pixels == 1
        assert corr.is_object_preserving  # within RECONCILE_TOLERANCE

    def test_reconcile_returns_same_mutated_object(self):
        gin = grid([[1, 0], [0, 0]])
        gout = grid([[0, 0], [0, 1]])
        in_objs, out_objs = segmented(gin, gout, S1)
        [corr] = match_pair(in_objs, out_objs, gin, gout,
                            profiles=["default"])
        again = reconcile_with_pixels(corr, gin, gout)
        assert again is corr
        assert corr.unreconciled_pixels == 0

    def test_empty_grids_no_objects(self):
        gin = grid([[0, 0], [0, 0]])
        gout = grid([[0, 0], [0, 0]])
        alts = alternatives(gin, gout, S1)
        assert len(alts) == 1  # all profiles dedupe to one empty matching
        assert alts[0].is_object_preserving
        assert alts[0].unreconciled_pixels == 0
        assert extract_deltas(alts[0]) == []

    def test_explicit_profile_subset(self):
        gin = grid([[1, 0], [0, 0]])
        gout = grid([[0, 1], [0, 0]])
        alts = match_pair(*segmented(gin, gout, S1), gin, gout,
                          profiles=["motion"])
        assert len(alts) == 1
        assert alts[0].weights_profile == "motion"


class TestHistogramAndConstants:
    def test_delta_histogram_counts(self):
        deltas = [
            ObjectDelta(0, DeltaType.TRANSLATE, 0, [0], {"dr": 1, "dc": 0}),
            ObjectDelta(0, DeltaType.TRANSLATE, 1, [1], {"dr": 2, "dc": 0}),
            ObjectDelta(0, DeltaType.DELETE, 2, [], {}),
        ]
        assert delta_histogram(deltas) == {"translate": 2, "delete": 1}
        assert delta_histogram([]) == {}

    def test_contract_constants(self):
        assert MATCH_THRESHOLD == 0.1
        assert RECONCILE_TOLERANCE == 0.05
        assert set(WEIGHT_PROFILES) \
            == {"default", "motion", "recolor", "motion_recolor",
                "mirror_rows", "mirror_cols"}
        # mirror profiles: default weights, mirrored location frame only
        assert WEIGHT_PROFILES["mirror_rows"] == WEIGHT_PROFILES["default"]
        assert WEIGHT_PROFILES["mirror_cols"] == WEIGHT_PROFILES["default"]
        assert WEIGHT_PROFILES["default"] == (0.3, 0.2, 0.2, 0.3)
        assert WEIGHT_PROFILES["motion"][3] == 0.0      # location zeroed
        assert WEIGHT_PROFILES["recolor"][1] == 0.0     # color zeroed
        assert WEIGHT_PROFILES["motion_recolor"][1] == 0.0
        assert WEIGHT_PROFILES["motion_recolor"][3] == 0.0
        for w in WEIGHT_PROFILES.values():
            assert abs(sum(w) - 1.0) < 1e-9
