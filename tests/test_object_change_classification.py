"""Tests for the rich object-change classifier (_classify_object_changes)."""
from __future__ import annotations

import numpy as np
import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reasoning_project.reasoning_engine import (
    _classify_object_changes,
    _extract_objects_with_properties,
    ObjectChange,
    ObjectChangeClassification,
)
from reasoning_project.operator_semantics import (
    check_object_change_obligations,
)


def _make_grid(*rows):
    return np.array(rows, dtype=int)


class TestRemoveObject:
    def test_single_object_zeroed(self):
        inp = _make_grid([1, 0, 2], [0, 0, 0], [3, 0, 0])
        out = _make_grid([1, 0, 0], [0, 0, 0], [3, 0, 0])
        objs = _extract_objects_with_properties(inp)
        r = _classify_object_changes(objs, inp, out)
        assert r is not None
        assert r.has_two_groups
        assert 1 in r.removed
        assert 0 in r.kept
        assert 2 in r.kept

    def test_multiple_objects_zeroed(self):
        inp = _make_grid([1, 0, 2], [0, 0, 0], [3, 0, 4])
        out = _make_grid([1, 0, 0], [0, 0, 0], [3, 0, 0])
        objs = _extract_objects_with_properties(inp)
        r = _classify_object_changes(objs, inp, out)
        assert r is not None
        assert len(r.removed) == 2
        assert len(r.kept) == 2


class TestKeepUnchanged:
    def test_all_unchanged(self):
        inp = _make_grid([1, 0, 2], [0, 0, 0], [3, 0, 0])
        out = inp.copy()
        objs = _extract_objects_with_properties(inp)
        r = _classify_object_changes(objs, inp, out)
        assert r is not None
        assert len(r.kept) == 3
        assert not r.has_two_groups
        assert r.failure_reason == "no_changed_objects"


class TestRecolorInPlace:
    def test_single_pixel_recolor(self):
        inp = _make_grid([1, 0, 2], [0, 0, 0], [3, 0, 0])
        out = _make_grid([1, 0, 5], [0, 0, 0], [3, 0, 0])
        objs = _extract_objects_with_properties(inp)
        r = _classify_object_changes(objs, inp, out)
        assert r is not None
        assert 1 in r.recolored
        assert r.dominant_change == "recolored"

    def test_block_recolor(self):
        inp = np.zeros((6, 6), dtype=int)
        inp[0:2, 0:2] = 1
        inp[3:5, 3:5] = 2
        out = inp.copy()
        out[3:5, 3:5] = 7
        objs = _extract_objects_with_properties(inp)
        r = _classify_object_changes(objs, inp, out)
        assert r is not None
        assert len(r.recolored) == 1
        assert len(r.kept) == 1
        # Check the recolored object's colors
        recolored_change = [c for c in r.changes if c.change_type == "recolored"][0]
        assert 2 in recolored_change.source_colors
        assert 7 in recolored_change.target_colors


class TestMoveObject:
    def test_block_moved(self):
        inp = np.zeros((6, 6), dtype=int)
        inp[0:2, 0:2] = 1
        inp[4:6, 0:2] = 2
        out = np.zeros((6, 6), dtype=int)
        out[0:2, 0:2] = 1
        out[4:6, 3:5] = 2
        objs = _extract_objects_with_properties(inp)
        r = _classify_object_changes(objs, inp, out)
        assert r is not None
        assert len(r.moved) == 1
        moved_change = [c for c in r.changes if c.change_type == "moved"][0]
        assert moved_change.displacement == (0, 3)


class TestMoveAndRecolor:
    def test_block_moved_and_recolored(self):
        inp = np.zeros((8, 8), dtype=int)
        inp[0:3, 0:3] = 1
        inp[5:8, 0:3] = 2
        out = np.zeros((8, 8), dtype=int)
        out[0:3, 0:3] = 1
        out[5:8, 4:7] = 5  # same shape, different color, different position
        objs = _extract_objects_with_properties(inp)
        r = _classify_object_changes(objs, inp, out)
        assert r is not None
        # Should detect as moved_recolored (shape found with color-blind match)
        assert len(r.moved_recolored) == 1 or len(r.moved) == 1


class TestCopyObject:
    def test_object_copied_via_zeroing(self):
        # Object removed from original position, copy placed elsewhere
        inp = np.zeros((6, 6), dtype=int)
        inp[0:2, 0:2] = 1
        inp[4:6, 0:2] = 2
        out = np.zeros((6, 6), dtype=int)
        out[0:2, 0:2] = 1
        out[4:6, 0:2] = 0  # original zeroed
        out[4:6, 3:5] = 2  # exact copy at new position
        objs = _extract_objects_with_properties(inp)
        r = _classify_object_changes(objs, inp, out)
        assert r is not None
        # Should detect as moved (zeroed original + found elsewhere)
        assert len(r.moved) == 1

    def test_object_recolored_with_copy(self):
        # Object recolored in place AND copied elsewhere — classifier sees recolor
        inp = np.zeros((6, 6), dtype=int)
        inp[0:2, 0:2] = 1
        inp[4:6, 0:2] = 2
        out = np.zeros((6, 6), dtype=int)
        out[0:2, 0:2] = 1
        out[4:6, 0:2] = 5  # original recolored
        out[4:6, 3:5] = 2  # copy appeared
        objs = _extract_objects_with_properties(inp)
        r = _classify_object_changes(objs, inp, out)
        assert r is not None
        # Classifier sees recolor at original mask — valid per-mask classification
        assert len(r.recolored) == 1 or len(r.changed) >= 1


class TestAmbiguousTwoIdentical:
    def test_identical_objects(self):
        inp = np.zeros((6, 6), dtype=int)
        inp[0:2, 0:2] = 1
        inp[0:2, 3:5] = 1
        out = np.zeros((6, 6), dtype=int)
        out[0:2, 0:2] = 1
        out[0:2, 3:5] = 0  # one removed
        objs = _extract_objects_with_properties(inp)
        r = _classify_object_changes(objs, inp, out)
        assert r is not None
        # One kept, one removed (or moved — but shouldn't be ambiguous)
        assert r.has_two_groups


class TestShapeChanged:
    def test_shape_expansion_invisible_to_mask(self):
        # Object expands beyond its original mask — classifier only checks mask pixels
        inp = np.zeros((6, 6), dtype=int)
        inp[0:2, 0:2] = 1
        inp[3:5, 3:5] = 2
        out = np.zeros((6, 6), dtype=int)
        out[0:2, 0:2] = 1
        out[3:6, 3:6] = 2  # expanded beyond original 2x2 mask
        objs = _extract_objects_with_properties(inp)
        r = _classify_object_changes(objs, inp, out)
        assert r is not None
        # Both appear "kept" because original mask pixels are unchanged
        assert len(r.kept) == 2

    def test_shape_shrink_detected(self):
        # Object shrinks — some mask pixels become background
        inp = np.zeros((6, 6), dtype=int)
        inp[0:2, 0:2] = 1
        inp[3:5, 3:5] = 2
        out = np.zeros((6, 6), dtype=int)
        out[0:2, 0:2] = 1
        out[3, 3] = 2  # shrank from 2x2 to 1x1
        objs = _extract_objects_with_properties(inp)
        r = _classify_object_changes(objs, inp, out)
        assert r is not None
        assert len(r.kept) == 1
        # Shrunken object detected as changed (some mask pixels differ)
        assert len(r.changed) >= 1 or len(r.removed) >= 1


class TestBackgroundFillNotCopy:
    def test_background_fill(self):
        inp = np.zeros((5, 5), dtype=int)
        inp[0, 0] = 1
        inp[4, 4] = 2
        out = inp.copy()
        out[2, 2] = 3  # new pixel in background — not a copy of anything
        objs = _extract_objects_with_properties(inp)
        r = _classify_object_changes(objs, inp, out)
        assert r is not None
        # Objects 1 and 2 should be kept — no false copy classification
        assert len(r.copied) == 0
        assert len(r.moved) == 0


class TestDifferentSizes:
    def test_size_change_returns_none(self):
        inp = _make_grid([1, 2], [3, 4])
        out = _make_grid([1, 2, 0], [3, 4, 0], [0, 0, 0])
        objs = _extract_objects_with_properties(inp)
        r = _classify_object_changes(objs, inp, out)
        assert r is None


class TestEmptyObjects:
    def test_no_objects(self):
        inp = np.zeros((3, 3), dtype=int)
        out = np.zeros((3, 3), dtype=int)
        objs = _extract_objects_with_properties(inp)
        r = _classify_object_changes(objs, inp, out)
        assert r is None


class TestBackwardCompat:
    def test_as_kept_removed(self):
        inp = _make_grid([1, 0, 2], [0, 0, 0], [3, 0, 0])
        out = _make_grid([1, 0, 0], [0, 0, 0], [3, 0, 0])
        objs = _extract_objects_with_properties(inp)
        r = _classify_object_changes(objs, inp, out)
        kr = r.as_kept_removed()
        assert kr is not None
        kept, removed = kr
        assert 0 in kept
        assert 2 in kept
        assert 1 in removed

    def test_recolor_as_kept_removed(self):
        inp = _make_grid([1, 0, 2], [0, 0, 0], [3, 0, 0])
        out = _make_grid([1, 0, 5], [0, 0, 0], [3, 0, 0])
        objs = _extract_objects_with_properties(inp)
        r = _classify_object_changes(objs, inp, out)
        kr = r.as_kept_removed()
        assert kr is not None
        kept, removed = kr
        assert 0 in kept
        assert 2 in kept
        assert 1 in removed  # recolored objects go to group_b


class TestProofObligations:
    def test_recolor_preserves_shape(self):
        inp = _make_grid([1, 0, 2], [0, 0, 0], [3, 0, 0])
        out = _make_grid([1, 0, 5], [0, 0, 0], [3, 0, 0])
        objs = _extract_objects_with_properties(inp)
        r = _classify_object_changes(objs, inp, out)
        obligs = check_object_change_obligations(r, objs, inp, out)
        shape_obl = [o for o in obligs if o.obligation_id == "oc_recolor_preserves_shape"][0]
        assert shape_obl.status == "passed"

    def test_kept_unchanged(self):
        inp = _make_grid([1, 0, 2], [0, 0, 0], [3, 0, 0])
        out = _make_grid([1, 0, 0], [0, 0, 0], [3, 0, 0])
        objs = _extract_objects_with_properties(inp)
        r = _classify_object_changes(objs, inp, out)
        obligs = check_object_change_obligations(r, objs, inp, out)
        kept_obl = [o for o in obligs if o.obligation_id == "oc_non_target_unchanged"][0]
        assert kept_obl.status == "passed"

    def test_no_ambiguous(self):
        inp = _make_grid([1, 0, 2], [0, 0, 0], [3, 0, 0])
        out = _make_grid([1, 0, 0], [0, 0, 0], [3, 0, 0])
        objs = _extract_objects_with_properties(inp)
        r = _classify_object_changes(objs, inp, out)
        obligs = check_object_change_obligations(r, objs, inp, out)
        amb_obl = [o for o in obligs if o.obligation_id == "oc_ambiguous_rejected"][0]
        assert amb_obl.status == "passed"
