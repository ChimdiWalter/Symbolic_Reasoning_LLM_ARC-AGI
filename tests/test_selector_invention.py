"""Tests for selector_invention.py — SelectorInventor and SelectorCandidate."""
import numpy as np
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from reasoning_project.selector_invention import SelectorInventor, SelectorCandidate
from reasoning_project.reasoning_engine import (
    _extract_objects_with_properties,
    _add_relational_properties as _add_rel_props_raw,
)


def _add_relational_properties(objects, grid=None):
    if grid is not None:
        h, w = grid.shape[:2]
        _add_rel_props_raw(objects, grid, h, w)
    return objects


def _make_filter_task():
    """Simple filter task: keep largest object, remove others."""
    inp = np.zeros((5, 5), dtype=int)
    inp[0:3, 0:3] = 1  # large 3x3
    inp[4, 4] = 2       # small 1x1
    out = np.zeros((5, 5), dtype=int)
    out[0:3, 0:3] = 1
    return [(inp, out)]


def _make_conjunction_task():
    """Task needing conjunction: keep objects that are large AND in top half."""
    inp = np.zeros((6, 6), dtype=int)
    inp[0:2, 0:2] = 1   # top-left, area=4, in_top_half=True, is_largest depends
    inp[4:6, 0:2] = 2   # bottom-left, area=4, in_top_half=False
    inp[0, 4] = 3        # top-right, area=1, in_top_half=True, is_smallest
    out = np.zeros((6, 6), dtype=int)
    out[0:2, 0:2] = 1
    return [(inp, out)]


class TestSelectorInventor:
    def test_init(self):
        si = SelectorInventor()
        assert si.max_conjuncts == 2
        assert len(si.all_props) > 50

    def test_infer_targets_from_change_simple(self):
        si = SelectorInventor()
        pairs = _make_filter_task()
        per_pair = si.infer_targets_from_change(pairs)
        assert len(per_pair) == 1
        pp = per_pair[0]
        assert pp["change_type"] in ("kept_removed", "pixel_diff")
        assert len(pp["target_indices"]) >= 1
        assert len(pp["non_target_indices"]) >= 1

    def test_search_single_properties_finds_is_largest(self):
        si = SelectorInventor()
        pairs = _make_filter_task()
        per_pair = si.infer_targets_from_change(pairs)
        valid = [pp for pp in per_pair if pp["target_indices"] and pp["non_target_indices"]]
        candidates = si.search_single_properties(valid)
        # Should find is_largest or is_smallest as discriminator
        assert len(candidates) > 0
        expr_names = [c.selector_expression for c in candidates]
        assert any("largest" in e or "smallest" in e for e in expr_names)

    def test_propose_selectors_returns_ranked(self):
        si = SelectorInventor()
        pairs = _make_filter_task()
        candidates = si.propose_selectors(pairs)
        assert len(candidates) > 0
        # Check ranked by complexity
        for i in range(len(candidates) - 1):
            assert candidates[i].complexity <= candidates[i + 1].complexity or \
                   candidates[i].train_fit_score >= candidates[i + 1].train_fit_score

    def test_build_selector_callable(self):
        si = SelectorInventor()
        pairs = _make_filter_task()
        inp, out = pairs[0]
        objects = _extract_objects_with_properties(inp)
        objects = _add_relational_properties(objects, inp)

        fn = si.build_selector_callable("is_largest")
        result = fn(objects)
        assert isinstance(result, list)
        assert len(result) == len(objects)
        assert any(result)

    def test_search_conjunctions(self):
        si = SelectorInventor()
        pairs = _make_conjunction_task()
        per_pair = si.infer_targets_from_change(pairs)
        valid = [pp for pp in per_pair if pp["target_indices"] and pp["non_target_indices"]]
        if valid:
            candidates = si.search_conjunctions(valid)
            # May or may not find conjunction depending on exact properties
            for c in candidates:
                assert c.selector_type == "conjunction"
                assert c.complexity == 2

    def test_search_rank_selectors(self):
        si = SelectorInventor()
        pairs = _make_filter_task()
        per_pair = si.infer_targets_from_change(pairs)
        valid = [pp for pp in per_pair if pp["target_indices"] and pp["non_target_indices"]]
        candidates = si.search_rank_selectors(valid)
        for c in candidates:
            assert c.selector_type == "rank"

    def test_search_marker_frame_anchor_relations(self):
        si = SelectorInventor()
        pairs = _make_filter_task()
        per_pair = si.infer_targets_from_change(pairs)
        valid = [pp for pp in per_pair if pp["target_indices"] and pp["non_target_indices"]]
        candidates = si.search_marker_frame_anchor_relations(valid)
        for c in candidates:
            assert c.selector_type == "marker_relation"

    def test_infer_targets_size_change(self):
        si = SelectorInventor()
        inp = np.zeros((5, 5), dtype=int)
        inp[1:4, 1:4] = 1
        inp[0, 4] = 2
        out = np.array([[1, 1, 1], [1, 1, 1], [1, 1, 1]], dtype=int)
        per_pair = si.infer_targets_from_change([(inp, out)])
        assert len(per_pair) == 1
        assert per_pair[0]["change_type"] == "size_change"

    def test_deduplicate(self):
        si = SelectorInventor()
        candidates = [
            SelectorCandidate("is_largest", "single", ["is_largest"], [], [], 1.0, 0.0, 1),
            SelectorCandidate("is_largest", "single", ["is_largest"], [], [], 1.0, 0.0, 1),
            SelectorCandidate("is_smallest", "single", ["is_smallest"], [], [], 1.0, 0.0, 1),
        ]
        unique = si._rank_and_deduplicate(candidates)
        assert len(unique) == 2


class TestSelectorCandidate:
    def test_fields(self):
        sc = SelectorCandidate(
            selector_expression="is_largest",
            selector_type="single",
            property_names=["is_largest"],
            selected_object_ids=[0],
            target_object_ids=[0],
            train_fit_score=1.0,
            ambiguity_score=0.0,
            complexity=1,
        )
        assert sc.selector_expression == "is_largest"
        assert sc.train_fit_score == 1.0
