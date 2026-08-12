"""Comprehensive tests for the perception bridge module.

Tests cover all 4 components + the integrated pipeline + helper functions.
All tests run without neural checkpoints (rule-based / fallback paths).
"""

import numpy as np
import pytest

from reasoning_project.perception_bridge import (
    JEPAPerceptionGuide,
    NeuralPerceptionPipeline,
    SlotPerceptionAdapter,
    SpatialRelationLearner,
    TaskPerception,
    WorldModelSimulator,
    SimulationResult,
    _detect_containment,
    _detect_separators,
)
from reasoning_project.reasoning_engine import GridDomainAdapter


# ═══════════════════════════════════════════════════════════════════════════
# SYNTHETIC GRID FACTORIES
# ═══════════════════════════════════════════════════════════════════════════

def _make_scattered_grid():
    """10x10 grid with many (>6) small scattered objects of different colors."""
    g = np.zeros((10, 10), dtype=int)
    # 7 distinct single-cell objects
    g[1, 1] = 1
    g[1, 5] = 2
    g[3, 8] = 3
    g[5, 2] = 4
    g[6, 6] = 5
    g[8, 1] = 6
    g[8, 8] = 7
    return g


def _make_separator_grid():
    """10x10 grid divided into quadrants by separator lines (color 5)."""
    g = np.zeros((10, 10), dtype=int)
    g[4, :] = 5   # horizontal separator at row 4
    g[:, 4] = 5   # vertical separator at col 4
    # Objects in each quadrant
    g[1, 1] = 1
    g[1, 6] = 2
    g[6, 1] = 3
    g[6, 6] = 4
    return g


def _make_nested_grid():
    """10x10 grid with a large rectangle containing a smaller one inside."""
    g = np.zeros((10, 10), dtype=int)
    # Outer rectangle (color 1): rows 1-8, cols 1-8
    g[1:9, 1:9] = 1
    # Inner "hole" (color 0) to break them apart
    g[3:7, 3:7] = 0
    # Inner rectangle (color 2): rows 4-6, cols 4-6
    g[4:6, 4:6] = 2
    return g


def _make_single_object_grid():
    """10x10 grid with exactly one connected-component object."""
    g = np.zeros((10, 10), dtype=int)
    g[3:6, 3:6] = 3  # single 3x3 block
    return g


def _make_nonzero_bg_grid():
    """10x10 grid where the most frequent color (background) is 7, not 0."""
    g = np.full((10, 10), 7, dtype=int)
    g[2:4, 2:4] = 1
    g[6:8, 6:8] = 3
    return g


def _make_two_object_grid(color_a=1, color_b=2):
    """10x10 grid with two well-separated objects."""
    g = np.zeros((10, 10), dtype=int)
    g[1:3, 1:3] = color_a  # 2x2 block top-left
    g[6:9, 6:9] = color_b  # 3x3 block bottom-right
    return g


def _make_filter_pair():
    """Input has two objects; output keeps only one (removes the other)."""
    inp = _make_two_object_grid(1, 2)
    out = inp.copy()
    out[1:3, 1:3] = 0  # remove the first object
    return inp, out


def _make_recolor_pair():
    """Input has two same-color objects; output recolors one (positions unchanged).
    same_color goes from True (both color 1) to False (1 vs 4)."""
    g = np.zeros((10, 10), dtype=int)
    g[1:3, 1:3] = 1  # 2x2 object A
    g[6:9, 6:9] = 1  # 3x3 object B — same color
    inp = g
    out = inp.copy()
    out[1:3, 1:3] = 4  # recolor object A → 4
    return inp, out


def _make_no_separator_grid():
    """Grid with no separator lines."""
    g = np.zeros((10, 10), dtype=int)
    g[2, 2] = 1
    g[7, 7] = 2
    return g


def _make_no_containment_grid():
    """Grid with two separate non-overlapping objects (no containment)."""
    return _make_two_object_grid(1, 2)


# ═══════════════════════════════════════════════════════════════════════════
# 1. JEPAPerceptionGuide — RULE-BASED FALLBACK
# ═══════════════════════════════════════════════════════════════════════════

class TestJEPAPerceptionGuideRuleBased:
    """Tests for the rule-based fallback path (no checkpoint)."""

    def test_scattered_objects_layout(self):
        guide = JEPAPerceptionGuide()
        g = _make_scattered_grid()
        perc = guide.analyze([(g, g)])
        assert perc.layout_type == "scattered"
        assert perc.estimated_object_count > 6

    def test_grid_with_separators_layout(self):
        guide = JEPAPerceptionGuide()
        g = _make_separator_grid()
        perc = guide.analyze([(g, g)])
        assert perc.layout_type == "grid_of_cells"
        assert perc.has_separators > 0

    def test_nested_objects_layout(self):
        guide = JEPAPerceptionGuide()
        g = _make_nested_grid()
        perc = guide.analyze([(g, g)])
        assert perc.layout_type == "nested"
        assert perc.has_containment > 0

    def test_single_object_layout(self):
        guide = JEPAPerceptionGuide()
        g = _make_single_object_grid()
        perc = guide.analyze([(g, g)])
        assert perc.layout_type == "single_object"
        assert perc.estimated_object_count <= 1.5

    def test_nonzero_bg_detection(self):
        guide = JEPAPerceptionGuide()
        g = _make_nonzero_bg_grid()
        perc = guide.analyze([(g, g)])
        assert perc.bg_is_zero < 1.0

    def test_confidence_is_half_for_rule_based(self):
        guide = JEPAPerceptionGuide()
        g = _make_scattered_grid()
        perc = guide.analyze([(g, g)])
        assert perc.confidence == 0.5

    def test_multiple_pairs_averaged(self):
        """Object count is averaged across all training pairs."""
        guide = JEPAPerceptionGuide()
        g1 = _make_scattered_grid()   # >6 objects
        g2 = _make_single_object_grid()  # 1 object
        perc = guide.analyze([(g1, g1), (g2, g2)])
        # Average of ~7 and 1 ≈ 4
        assert 1 < perc.estimated_object_count < 7


# ═══════════════════════════════════════════════════════════════════════════
# 2. VIEW SUGGESTION
# ═══════════════════════════════════════════════════════════════════════════

class TestViewSuggestion:

    def test_separators_suggest_color_cc_first(self):
        guide = JEPAPerceptionGuide()
        perc = TaskPerception(
            layout_type="grid_of_cells",
            has_separators=1.0,
            bg_is_zero=1.0,
        )
        views = guide.suggest_views(perc)
        assert views[0] == "color_cc"

    def test_nested_suggest_color_cc_first(self):
        guide = JEPAPerceptionGuide()
        perc = TaskPerception(
            layout_type="nested",
            has_containment=1.0,
            bg_is_zero=1.0,
        )
        views = guide.suggest_views(perc)
        assert views[0] == "color_cc"

    def test_single_object_suggest_per_color_first(self):
        guide = JEPAPerceptionGuide()
        perc = TaskPerception(
            layout_type="single_object",
            bg_is_zero=1.0,
        )
        views = guide.suggest_views(perc)
        assert views[0] == "per_color"

    def test_nonzero_bg_suggests_majority_bg_early(self):
        guide = JEPAPerceptionGuide()
        perc = TaskPerception(
            layout_type="scattered",
            bg_is_zero=0.0,
        )
        views = guide.suggest_views(perc)
        assert views[0] == "majority_bg"

    def test_all_standard_views_included(self):
        """Every standard view name must appear in the suggestion list."""
        guide = JEPAPerceptionGuide()
        perc = TaskPerception(layout_type="scattered", bg_is_zero=1.0)
        views = guide.suggest_views(perc)
        for v in ["color_cc", "per_color", "monochrome", "majority_bg", "slot"]:
            assert v in views


# ═══════════════════════════════════════════════════════════════════════════
# 3. SpatialRelationLearner
# ═══════════════════════════════════════════════════════════════════════════

class TestSpatialRelationLearner:

    def test_preservation_detection(self):
        """If objects don't move between input and output, spatial relations
        like distance should be preserved."""
        learner = SpatialRelationLearner()
        adapter = GridDomainAdapter()
        inp = _make_two_object_grid(1, 2)
        out = inp.copy()  # identical — all relations preserved
        result = learner.discover_relevant_relations(adapter, [(inp, out)])
        assert "preserved" in result
        assert "changed" in result
        assert len(result["preserved"]) > 0

    def test_changed_detection_on_recolor(self):
        """When an object is recolored, same_color relation should change."""
        learner = SpatialRelationLearner()
        adapter = GridDomainAdapter()
        inp, out = _make_recolor_pair()
        result = learner.discover_relevant_relations(adapter, [(inp, out)])
        # same_color should be in changed because one object changed color
        assert "same_color" in result["changed"]

    def test_discriminative_ranking_returns_list(self):
        learner = SpatialRelationLearner()
        adapter = GridDomainAdapter()
        inp, out = _make_filter_pair()
        scores = learner.rank_discriminative_relations(adapter, [(inp, out)])
        assert isinstance(scores, list)
        assert len(scores) > 0
        # Each entry is (relation_name, score)
        for name, score in scores:
            assert isinstance(name, str)
            assert isinstance(score, float)

    def test_discriminative_ranking_sorted_descending(self):
        learner = SpatialRelationLearner()
        adapter = GridDomainAdapter()
        inp, out = _make_filter_pair()
        scores = learner.rank_discriminative_relations(adapter, [(inp, out)])
        if len(scores) >= 2:
            for i in range(len(scores) - 1):
                assert scores[i][1] >= scores[i + 1][1]

    def test_empty_pairs_returns_empty(self):
        learner = SpatialRelationLearner()
        adapter = GridDomainAdapter()
        result = learner.discover_relevant_relations(adapter, [])
        assert result["preserved"] == []
        assert result["changed"] == []
        assert result["n_pairs_analyzed"] == 0


# ═══════════════════════════════════════════════════════════════════════════
# 4. SlotPerceptionAdapter — FALLBACK
# ═══════════════════════════════════════════════════════════════════════════

class TestSlotPerceptionAdapterFallback:

    def test_falls_back_without_model(self):
        adapter = SlotPerceptionAdapter()
        assert adapter.slot_model is None
        g = _make_two_object_grid()
        objs = adapter.extract_objects(g)
        assert len(objs) == 2

    def test_extract_objects_returns_proper_dicts(self):
        adapter = SlotPerceptionAdapter()
        g = _make_two_object_grid()
        objs = adapter.extract_objects(g)
        required_keys = {"label", "mask", "primary_color", "area", "bbox", "center_r", "center_c"}
        for obj in objs:
            assert required_keys.issubset(obj.keys()), f"Missing keys: {required_keys - obj.keys()}"

    def test_classify_kept_removed_works(self):
        adapter = SlotPerceptionAdapter()
        inp, out = _make_filter_pair()
        objs = adapter.extract_objects(inp)
        result = adapter.classify_kept_removed(objs, inp, out)
        assert result is not None
        kept, removed = result
        assert len(kept) == 1
        assert len(removed) == 1

    def test_reconstruct_filtered_works(self):
        adapter = SlotPerceptionAdapter()
        inp = _make_two_object_grid()
        objs = adapter.extract_objects(inp)
        # Keep only second object
        keep_mask = [False, True]
        result = adapter.reconstruct_filtered(inp, objs, keep_mask)
        # First object region should be zeroed out
        assert result[1, 1] == 0
        assert result[2, 2] == 0
        # Second object should remain
        assert np.any(result[6:9, 6:9] != 0)

    def test_property_names_returns_nonempty_list(self):
        adapter = SlotPerceptionAdapter()
        names = adapter.property_names()
        assert isinstance(names, list)
        assert len(names) > 0

    def test_scenes_equal(self):
        adapter = SlotPerceptionAdapter()
        a = _make_two_object_grid()
        b = a.copy()
        assert adapter.scenes_equal(a, b) is True
        b[0, 0] = 9
        assert adapter.scenes_equal(a, b) is False

    def test_same_structure(self):
        adapter = SlotPerceptionAdapter()
        a = np.zeros((5, 5), dtype=int)
        b = np.zeros((5, 5), dtype=int)
        c = np.zeros((3, 7), dtype=int)
        assert adapter.same_structure(a, b) is True
        assert adapter.same_structure(a, c) is False


# ═══════════════════════════════════════════════════════════════════════════
# 5. WorldModelSimulator — WITHOUT MODEL
# ═══════════════════════════════════════════════════════════════════════════

class TestWorldModelSimulatorNoModel:

    def test_default_scores(self):
        sim = WorldModelSimulator()
        assert sim.world_model is None
        inp = _make_two_object_grid()
        out = inp.copy()
        result = sim.simulate_hypothesis(out, inp, [(inp, out)])
        assert isinstance(result, SimulationResult)
        assert result.agreement_score == 0.5
        assert result.confidence == 0.0
        assert result.predicted_output is None

    def test_rank_hypotheses_returns_all(self):
        sim = WorldModelSimulator()
        inp = _make_two_object_grid()
        c1 = (inp.copy(), {"name": "h1"})
        c2 = (inp.copy(), {"name": "h2"})
        results = sim.rank_hypotheses([c1, c2], inp, [(inp, inp)])
        assert len(results) == 2
        for r in results:
            assert isinstance(r, SimulationResult)

    def test_rank_hypotheses_sorted_by_agreement(self):
        """All have 0.5 agreement, so order doesn't matter but they all appear."""
        sim = WorldModelSimulator()
        inp = _make_two_object_grid()
        candidates = [(inp.copy(), {"i": i}) for i in range(5)]
        results = sim.rank_hypotheses(candidates, inp, [(inp, inp)])
        assert len(results) == 5
        for i in range(len(results) - 1):
            assert results[i].agreement_score >= results[i + 1].agreement_score


# ═══════════════════════════════════════════════════════════════════════════
# 6. NeuralPerceptionPipeline
# ═══════════════════════════════════════════════════════════════════════════

class TestNeuralPerceptionPipeline:

    def test_constructs_with_no_checkpoints(self):
        pipeline = NeuralPerceptionPipeline()
        assert pipeline.jepa_guide is not None
        assert pipeline.slot_adapter is not None
        assert pipeline.relation_learner is not None
        assert pipeline.world_simulator is not None

    def test_from_checkpoints_no_paths(self):
        pipeline = NeuralPerceptionPipeline.from_checkpoints()
        assert pipeline.jepa_guide is not None
        assert pipeline.slot_adapter is not None

    def test_analyze_task_returns_expected_keys(self):
        pipeline = NeuralPerceptionPipeline()
        inp = _make_two_object_grid()
        out = inp.copy()
        result = pipeline.analyze_task([(inp, out)])
        expected_keys = {
            "perception", "relations", "discriminative_relations",
            "suggested_views", "has_neural_perception", "has_world_model",
        }
        assert expected_keys.issubset(result.keys())

    def test_analyze_task_perception_is_task_perception(self):
        pipeline = NeuralPerceptionPipeline()
        inp = _make_two_object_grid()
        result = pipeline.analyze_task([(inp, inp)])
        assert isinstance(result["perception"], TaskPerception)

    def test_get_slot_adapter_returns_adapter(self):
        pipeline = NeuralPerceptionPipeline()
        adapter = pipeline.get_slot_adapter()
        assert isinstance(adapter, SlotPerceptionAdapter)

    def test_no_neural_perception_flag(self):
        pipeline = NeuralPerceptionPipeline()
        result = pipeline.analyze_task([(_make_two_object_grid(), _make_two_object_grid())])
        assert result["has_neural_perception"] is False
        assert result["has_world_model"] is False

    def test_score_hypothesis_delegates_to_world_sim(self):
        pipeline = NeuralPerceptionPipeline()
        inp = _make_two_object_grid()
        out = inp.copy()
        result = pipeline.score_hypothesis(out, inp, [(inp, out)])
        assert isinstance(result, SimulationResult)
        assert result.agreement_score == 0.5


# ═══════════════════════════════════════════════════════════════════════════
# 7. HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

class TestHelperFunctions:

    def test_detect_separators_with_separators(self):
        g = _make_separator_grid()
        assert _detect_separators(g, bg=0) is True

    def test_detect_separators_without_separators(self):
        g = _make_no_separator_grid()
        assert _detect_separators(g, bg=0) is False

    def test_detect_containment_with_containment(self):
        g = _make_nested_grid()
        assert _detect_containment(g, bg=0) is True

    def test_detect_containment_without_containment(self):
        g = _make_no_containment_grid()
        assert _detect_containment(g, bg=0) is False

    def test_detect_separators_edge_only_ignored(self):
        """Rows/cols at position 0 or last should not count as separators."""
        g = np.zeros((5, 5), dtype=int)
        g[0, :] = 3  # edge row — should NOT be detected as separator
        g[-1, :] = 3
        assert _detect_separators(g, bg=0) is False

    def test_detect_containment_single_object(self):
        """Single object means no containment."""
        g = _make_single_object_grid()
        assert _detect_containment(g, bg=0) is False
