"""Tests for neuro-cognitive diagnostics — Hebbian memory, predictive error, vicarious reward, cognitive trace."""
import numpy as np
import pytest
from geocat_arc.neuro_cognitive.hebbian_memory import HebbianMemory
from geocat_arc.neuro_cognitive.predictive_error import (
    compute_prediction_error, localize_errors,
)
from geocat_arc.neuro_cognitive.vicarious_reward import VicariousReward
from geocat_arc.neuro_cognitive.cognitive_trace import CognitiveTrace


class TestHebbianMemory:
    def test_strengthen_on_success(self):
        mem = HebbianMemory(learning_rate=0.1)
        mem.update("HasColor", "Recolor", success=True)
        assert mem.get_strength("HasColor", "Recolor") > 0.0

    def test_weaken_on_failure(self):
        mem = HebbianMemory(learning_rate=0.1)
        mem.update("HasColor", "Recolor", success=True)
        mem.update("HasColor", "Recolor", success=True)
        strength_before = mem.get_strength("HasColor", "Recolor")
        mem.update("HasColor", "Recolor", success=False)
        assert mem.get_strength("HasColor", "Recolor") < strength_before

    def test_strength_never_negative(self):
        mem = HebbianMemory(learning_rate=0.5)
        for _ in range(20):
            mem.update("pred", "op", success=False)
        assert mem.get_strength("pred", "op") >= 0.0

    def test_unknown_association_zero(self):
        mem = HebbianMemory()
        assert mem.get_strength("unknown_pred", "unknown_op") == 0.0

    def test_top_associations(self):
        mem = HebbianMemory(learning_rate=0.1)
        mem.update("pred", "op_good", success=True)
        mem.update("pred", "op_good", success=True)
        mem.update("pred", "op_bad", success=True)
        top = mem.top_associations("pred", k=2)
        assert len(top) == 2
        assert top[0][0] == "op_good"
        assert top[0][1] > top[1][1]

    def test_decay(self):
        mem = HebbianMemory(learning_rate=0.1)
        mem.update("pred", "op", success=True)
        before = mem.get_strength("pred", "op")
        mem.decay(rate=0.5)
        after = mem.get_strength("pred", "op")
        assert after < before

    def test_serialization_roundtrip(self):
        mem = HebbianMemory(learning_rate=0.1)
        mem.update("pred1", "op1", success=True)
        mem.update("pred2", "op2", success=True)
        d = mem.to_dict()
        mem2 = HebbianMemory.from_dict(d)
        assert abs(mem2.get_strength("pred1", "op1") - mem.get_strength("pred1", "op1")) < 1e-10


class TestPredictiveError:
    def test_identical_grids_no_error(self):
        grid = [[1, 2], [3, 4]]
        pe = compute_prediction_error(grid, grid)
        assert pe.error_rate == 0.0
        assert len(pe.error_locations) == 0
        assert len(pe.localized_regions) == 0

    def test_all_wrong(self):
        pred = [[0, 0], [0, 0]]
        target = [[1, 1], [1, 1]]
        pe = compute_prediction_error(pred, target)
        assert pe.error_rate == 1.0
        assert len(pe.error_locations) == 4

    def test_partial_error(self):
        pred = [[1, 0], [0, 0]]
        target = [[1, 1], [1, 1]]
        pe = compute_prediction_error(pred, target)
        assert 0.0 < pe.error_rate < 1.0

    def test_error_regions_contiguous(self):
        pred = [
            [1, 1, 1, 1],
            [1, 0, 0, 1],
            [1, 0, 0, 1],
            [1, 1, 1, 1],
        ]
        target = [
            [1, 1, 1, 1],
            [1, 1, 1, 1],
            [1, 1, 1, 1],
            [1, 1, 1, 1],
        ]
        pe = compute_prediction_error(pred, target)
        assert len(pe.localized_regions) == 1
        r0, c0, r1, c1 = pe.localized_regions[0]
        assert (r0, c0) == (1, 1)
        assert (r1, c1) == (3, 3)

    def test_multiple_error_regions(self):
        pred = [
            [0, 1, 1, 0],
            [1, 1, 1, 1],
            [1, 1, 1, 1],
            [0, 1, 1, 0],
        ]
        target = [
            [1, 1, 1, 1],
            [1, 1, 1, 1],
            [1, 1, 1, 1],
            [1, 1, 1, 1],
        ]
        pe = compute_prediction_error(pred, target)
        assert len(pe.localized_regions) >= 2

    def test_localize_errors_directly(self):
        error_map = np.array([
            [True, False, False],
            [False, False, False],
            [False, False, True],
        ])
        regions = localize_errors(error_map)
        assert len(regions) == 2


class TestVicariousReward:
    def test_reward_increases_prior(self):
        vr = VicariousReward()
        initial = vr.get_prior("Segment")
        vr.reward("Segment", 1.0)
        assert vr.get_prior("Segment") > initial

    def test_penalize_decreases_prior(self):
        vr = VicariousReward()
        vr.reward("Segment", 5.0)
        before = vr.get_prior("Segment")
        vr.penalize("Segment", 2.0)
        assert vr.get_prior("Segment") < before

    def test_prior_stays_positive(self):
        vr = VicariousReward()
        for _ in range(50):
            vr.penalize("op", 10.0)
        assert vr.get_prior("op") > 0

    def test_normalize(self):
        vr = VicariousReward()
        vr.reward("op1", 3.0)
        vr.reward("op2", 7.0)
        vr.normalize()
        total = sum(v for _, v in vr.top_operators(k=100))
        assert abs(total - 1.0) < 1e-6

    def test_top_operators(self):
        vr = VicariousReward()
        vr.reward("op_good", 10.0)
        vr.reward("op_bad", 0.1)
        top = vr.top_operators(k=2)
        assert top[0][0] == "op_good"


class TestCognitiveTrace:
    def test_add_observe(self):
        ct = CognitiveTrace()
        ct.add_observe("t1", [[1, 2], [3, 4]], [[5, 6], [7, 8]])
        assert ct.num_steps == 1
        assert ct.steps[0].step_type == "observe"

    def test_add_predict(self):
        ct = CognitiveTrace()
        ct.add_predict("segment -> render", [[1, 2], [3, 4]])
        assert ct.num_steps == 1
        assert ct.steps[0].step_type == "predict"

    def test_add_compare(self):
        ct = CognitiveTrace()
        ct.add_compare(0.25, 2)
        assert ct.steps[0].data["error_rate"] == 0.25

    def test_add_update(self):
        ct = CognitiveTrace()
        ct.add_update({"p1|op1": 0.1}, {"op1": 0.5})
        assert ct.steps[0].step_type == "update"

    def test_add_verify(self):
        ct = CognitiveTrace()
        ct.add_verify(exact_match=True, score=1.0)
        assert ct.steps[0].data["exact_match"] is True

    def test_full_trace(self):
        ct = CognitiveTrace()
        ct.add_observe("t1", [[0]], [[1]])
        ct.add_predict("prog", [[0]])
        ct.add_compare(1.0, 1)
        ct.add_update({}, {})
        ct.add_verify(False, 0.0)
        assert ct.num_steps == 5

    def test_to_dict(self):
        ct = CognitiveTrace()
        ct.add_observe("t1", [[0]], [[1]])
        ct.add_verify(True, 1.0)
        d = ct.to_dict()
        assert "steps" in d
        assert len(d["steps"]) == 2
        assert d["steps"][0]["step_type"] == "observe"
        assert d["steps"][1]["step_type"] == "verify"
