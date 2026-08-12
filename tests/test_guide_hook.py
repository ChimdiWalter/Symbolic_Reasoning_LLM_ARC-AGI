"""Tests for geocat_arc.object_reasoning.guide_hook.

(i)   hook returns {} when env off and imports no torch
(ii)  with env on + stub predictor, candidates are reordered stably
      and none dropped
(iii) exception in predictor -> {} and induction proceeds
"""
import os
import sys
import unittest
from unittest import mock

# Project root on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class _FakeGrid:
    """Minimal Grid stand-in for testing (to_list -> 2D list)."""
    def __init__(self, data):
        self._data = data

    def to_list(self):
        return self._data


def _make_pairs(n=2):
    """Return n synthetic (Grid, Grid) pairs."""
    return [(_FakeGrid([[i, i + 1], [i + 2, i + 3]]),
             _FakeGrid([[i + 4, i + 5], [i + 6, i + 7]]))
            for i in range(n)]


class TestGuideHookOff(unittest.TestCase):
    """When ARC_GUIDE is not set to '1', the hook must return {} and must
    NOT import torch (zero-cost gate)."""

    def setUp(self):
        # Ensure ARC_GUIDE is off
        self._orig = os.environ.pop("ARC_GUIDE", None)

    def tearDown(self):
        if self._orig is not None:
            os.environ["ARC_GUIDE"] = self._orig
        elif "ARC_GUIDE" in os.environ:
            del os.environ["ARC_GUIDE"]

    def test_returns_empty_when_off(self):
        from geocat_arc.object_reasoning.guide_hook import (
            kind_priority, _reset_for_test)
        _reset_for_test()
        result = kind_priority(_make_pairs())
        self.assertEqual(result, {})

    def test_no_torch_import_when_off(self):
        """torch must not be imported when the gate is off."""
        # Remove torch from sys.modules if present, run hook, check it
        # was NOT re-imported by the hook.
        saved = sys.modules.pop("torch", "SENTINEL")
        try:
            from geocat_arc.object_reasoning.guide_hook import (
                kind_priority, _reset_for_test)
            _reset_for_test()
            kind_priority(_make_pairs())
            self.assertNotIn("torch", sys.modules,
                             "torch was imported despite ARC_GUIDE being off")
        finally:
            if saved != "SENTINEL":
                sys.modules["torch"] = saved


class TestGuideHookStub(unittest.TestCase):
    """With ARC_GUIDE=1 and a stub predictor injected, the guide hook
    must return priorities and the inducer's _guide_sort_keys must
    reorder candidates stably with none dropped."""

    def setUp(self):
        os.environ["ARC_GUIDE"] = "1"

    def tearDown(self):
        os.environ.pop("ARC_GUIDE", None)
        from geocat_arc.object_reasoning.guide_hook import _reset_for_test
        _reset_for_test()

    def test_stub_returns_priorities(self):
        import geocat_arc.object_reasoning.guide_hook as gh
        gh._reset_for_test()

        # Inject a stub predictor
        class StubPredictor:
            def rank(self, task_dict):
                return {
                    "kinds": [("recolor", 0.9), ("translate", 0.7),
                              ("grow", 0.5), ("keep", 0.3),
                              ("delete", 0.1)],
                    "families": [],
                }
        gh._predictor = StubPredictor()

        result = gh.kind_priority(_make_pairs())
        self.assertIsInstance(result, dict)
        self.assertGreater(len(result), 0)
        self.assertAlmostEqual(result["recolor"], 0.9)
        self.assertAlmostEqual(result["translate"], 0.7)

    def test_candidates_reordered_stably_none_dropped(self):
        """_guide_sort_keys must reorder by descending probability,
        keep unknown kinds after known ones in their original order,
        and never drop any key."""
        from geocat_arc.object_reasoning.inducer import _guide_sort_keys

        keys = ["delete", "grow", "keep", "recolor", "translate",
                "zzz_unknown"]
        priority = {"recolor": 0.9, "translate": 0.7, "grow": 0.5,
                    "keep": 0.3, "delete": 0.1}

        sorted_keys = _guide_sort_keys(keys, priority)

        # None dropped
        self.assertEqual(set(sorted_keys), set(keys))
        self.assertEqual(len(sorted_keys), len(keys))

        # Known kinds: descending probability
        known_in_result = [k for k in sorted_keys if k in priority]
        self.assertEqual(known_in_result,
                         ["recolor", "translate", "grow", "keep", "delete"])

        # Unknown kinds appear after all known ones
        first_unknown_idx = sorted_keys.index("zzz_unknown")
        last_known_idx = max(sorted_keys.index(k) for k in priority)
        self.assertGreater(first_unknown_idx, last_known_idx)

    def test_empty_priority_preserves_order(self):
        """When guide_priority is empty, original order is preserved."""
        from geocat_arc.object_reasoning.inducer import _guide_sort_keys

        keys = ["delete", "grow", "keep", "recolor", "translate"]
        result = _guide_sort_keys(keys, {})
        self.assertEqual(result, keys)

    def test_stable_among_equal_probabilities(self):
        """Keys with equal probability keep their original relative order."""
        from geocat_arc.object_reasoning.inducer import _guide_sort_keys

        keys = ["alpha", "beta", "gamma"]
        priority = {"alpha": 0.5, "beta": 0.5, "gamma": 0.5}
        result = _guide_sort_keys(keys, priority)
        # All have the same probability, so original order is preserved
        self.assertEqual(result, keys)

    def test_tier2_tuple_keys(self):
        """Tier 2 group keys are tuples (delta_type_name, param_sig).
        The guide should extract the delta type name from the first
        element."""
        from geocat_arc.object_reasoning.inducer import _guide_sort_keys

        keys = [("delete", "{}"), ("recolor", '{"color":3}'),
                ("translate", '{"dr":1,"dc":0}')]
        priority = {"recolor": 0.9, "translate": 0.7, "delete": 0.1}
        result = _guide_sort_keys(keys, priority)
        dt_order = [k[0] for k in result]
        self.assertEqual(dt_order, ["recolor", "translate", "delete"])

    def test_cache_hit(self):
        """Second call with same pairs must use cache, not re-run."""
        import geocat_arc.object_reasoning.guide_hook as gh
        gh._reset_for_test()

        call_count = 0

        class CountingPredictor:
            def rank(self, task_dict):
                nonlocal call_count
                call_count += 1
                return {"kinds": [("recolor", 0.9)], "families": []}

        gh._predictor = CountingPredictor()
        pairs = _make_pairs()

        r1 = gh.kind_priority(pairs)
        r2 = gh.kind_priority(pairs)
        self.assertEqual(r1, r2)
        self.assertEqual(call_count, 1, "Second call should hit cache")


class TestGuideHookException(unittest.TestCase):
    """When the predictor raises, the hook must return {} and induction
    must proceed without error."""

    def setUp(self):
        os.environ["ARC_GUIDE"] = "1"

    def tearDown(self):
        os.environ.pop("ARC_GUIDE", None)
        from geocat_arc.object_reasoning.guide_hook import _reset_for_test
        _reset_for_test()

    def test_predictor_exception_returns_empty(self):
        import geocat_arc.object_reasoning.guide_hook as gh
        gh._reset_for_test()

        class ExplodingPredictor:
            def rank(self, task_dict):
                raise RuntimeError("GPU on fire")

        gh._predictor = ExplodingPredictor()
        result = gh.kind_priority(_make_pairs())
        self.assertEqual(result, {})

    def test_predictor_load_failure_returns_empty(self):
        """If GuidePredictor fails to construct, hook returns {}."""
        import geocat_arc.object_reasoning.guide_hook as gh
        gh._reset_for_test()

        # Patch the import so GuidePredictor raises
        with mock.patch.dict(sys.modules, {"guide": None,
                                           "guide.predict": None}):
            result = gh.kind_priority(_make_pairs())
            self.assertEqual(result, {})


if __name__ == "__main__":
    unittest.main()
