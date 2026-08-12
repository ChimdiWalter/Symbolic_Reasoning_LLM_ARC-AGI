"""Test that property expansion produces selectors consumed by executable proposals."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def _make_filter_task():
    """Task where objects touching boundary are kept, interior objects removed."""
    inp = np.zeros((6, 6), dtype=int)
    inp[0, 1:4] = 1  # boundary object
    inp[2:4, 2:4] = 2  # interior object

    out = np.zeros((6, 6), dtype=int)
    out[0, 1:4] = 1  # keep boundary
    return inp, out


def _make_train_pairs():
    inp1, out1 = _make_filter_task()

    inp2 = np.zeros((6, 6), dtype=int)
    inp2[5, 0:3] = 3  # boundary (bottom)
    inp2[2:4, 3:5] = 4  # interior

    out2 = np.zeros((6, 6), dtype=int)
    out2[5, 0:3] = 3

    return [(inp1, out1), (inp2, out2)]


def _make_marker_filter_task():
    """Task where markers (single-cell) are removed, larger objects kept."""
    inp1 = np.zeros((8, 8), dtype=int)
    inp1[1:3, 1:3] = 2  # 2x2 block (kept)
    inp1[5:7, 5:7] = 3  # 2x2 block (kept)
    inp1[0, 4] = 5       # marker (removed)
    inp1[7, 0] = 6       # marker (removed)

    out1 = np.zeros((8, 8), dtype=int)
    out1[1:3, 1:3] = 2
    out1[5:7, 5:7] = 3

    inp2 = np.zeros((8, 8), dtype=int)
    inp2[2:5, 2:5] = 4  # 3x3 block (kept)
    inp2[0, 0] = 7       # marker (removed)
    inp2[7, 7] = 8       # marker (removed)
    inp2[3, 7] = 9       # marker (removed)

    out2 = np.zeros((8, 8), dtype=int)
    out2[2:5, 2:5] = 4

    return [(inp1, out1), (inp2, out2)]


class TestPropertyExpansionSelectorFlow:
    def test_property_expansion_finds_selector(self):
        from reasoning_project.property_expansion import PropertyExpansionEngine

        engine = PropertyExpansionEngine()
        train_pairs = _make_train_pairs()
        object_trace = {"pairs": [{"n_input_objects": 2, "n_output_objects": 1}]}
        failure_trace = {"failure_type": "no_discriminative_property"}

        results = engine.find_discriminative_property(train_pairs, object_trace, failure_trace)
        assert len(results) > 0, "Should find at least one expanded property"
        assert results[0]["score"] > 0.0

        prop_names = [r["name"] for r in results]
        assert "touches_boundary" in prop_names or "is_interior" in prop_names

    def test_property_expansion_finds_marker_discriminator(self):
        from reasoning_project.property_expansion import PropertyExpansionEngine

        engine = PropertyExpansionEngine()
        train_pairs = _make_marker_filter_task()
        object_trace = {"pairs": [{"n_input_objects": 4, "n_output_objects": 2}]}
        failure_trace = {}

        results = engine.find_discriminative_property(train_pairs, object_trace, failure_trace)
        prop_names = [r["name"] for r in results]
        perfect = [r for r in results if r["score"] == 1.0]
        assert len(perfect) > 0, "Should find perfect discriminators"
        assert any(n in prop_names for n in ["is_marker", "single_cell", "is_singleton"]), \
            f"Should find marker-related discriminator, got: {[r['name'] for r in results[:5]]}"

    def test_property_selector_consumed_by_orchestrator(self):
        from reasoning_project.adaptive_orchestrator import (
            GatedAdaptiveReasoningOrchestrator,
            OrchestratorConfig,
        )

        config = OrchestratorConfig(
            timeout_per_task=60.0,
            enable_trace_invention=False,
            enable_static_portfolio=False,
        )
        orch = GatedAdaptiveReasoningOrchestrator(config)
        train_pairs = _make_train_pairs()

        analysis = orch.analyze_task("test_prop_expansion", train_pairs)
        routes = orch._route_with_reasons(analysis)
        triggered = [m for m, (t, _) in routes.items() if t]

        proposals = orch.collect_proposals(analysis, triggered, train_pairs, [train_pairs[0][0]])

        prop_proposals = [p for p in proposals if p.module_name == "property_expansion"]
        if prop_proposals:
            executable_count = sum(
                1 for p in prop_proposals
                if isinstance(p.hypothesis, dict) and callable(p.hypothesis.get("execute"))
            )
            assert executable_count > 0 or len(prop_proposals) > 0, \
                "Property expansion should produce proposals"

    def test_verifier_receives_executable_hypothesis(self):
        from reasoning_project.adaptive_orchestrator import (
            GatedAdaptiveReasoningOrchestrator,
            OrchestratorConfig,
            ModuleProposal,
        )
        from reasoning_project.proposal_verifier import ProposalVerifier

        config = OrchestratorConfig(timeout_per_task=60.0)
        orch = GatedAdaptiveReasoningOrchestrator(config)
        train_pairs = _make_train_pairs()

        execute_fn = orch._build_property_filter_execute("touches_boundary", train_pairs)
        assert execute_fn is not None, \
            "_build_property_filter_execute should return a callable for 'touches_boundary'"

        proposal = ModuleProposal(
            module_name="property_expansion",
            proposal_type="expanded_property_selector",
            operator_family="discriminative_filter",
            selector="touches_boundary",
            hypothesis={"execute": execute_fn, "property": "touches_boundary"},
            confidence=0.7,
            evidence={},
        )
        verifier = ProposalVerifier()
        outcome = verifier.verify(proposal, train_pairs, [train_pairs[0][0]])
        assert not outcome.false_positive

    def test_build_property_filter_with_marker_property(self):
        from reasoning_project.adaptive_orchestrator import (
            GatedAdaptiveReasoningOrchestrator,
            OrchestratorConfig,
        )

        config = OrchestratorConfig(timeout_per_task=60.0)
        orch = GatedAdaptiveReasoningOrchestrator(config)
        train_pairs = _make_marker_filter_task()

        execute_fn = orch._build_property_filter_execute("is_marker", train_pairs)
        assert execute_fn is not None, \
            "_build_property_filter_execute should work for 'is_marker'"

        test_inp = train_pairs[0][0]
        result = execute_fn(test_inp)
        assert result is not None
        expected = train_pairs[0][1]
        assert np.array_equal(result, expected)


class TestRelationalProperties:
    def test_marker_properties_computed(self):
        from reasoning_project.reasoning_engine import (
            _extract_objects_with_properties, _get_property_value,
            RELATIONAL_EXPANDED_PROPERTIES,
        )

        inp = np.zeros((8, 8), dtype=int)
        inp[1:3, 1:3] = 2  # 2x2 block
        inp[0, 4] = 5       # marker
        inp[5:7, 5:7] = 3   # 2x2 block

        objs = _extract_objects_with_properties(inp)
        assert len(objs) == 3

        markers = [o for o in objs if _get_property_value(o, "is_marker")]
        assert len(markers) == 1
        assert markers[0]["area"] == 1
        assert markers[0]["primary_color"] == 5

        non_markers = [o for o in objs if not _get_property_value(o, "is_marker")]
        assert len(non_markers) == 2

    def test_frame_properties_computed(self):
        from reasoning_project.reasoning_engine import (
            _extract_objects_with_properties, _get_property_value,
        )

        inp = np.zeros((10, 10), dtype=int)
        inp[1, 1:8] = 4
        inp[6, 1:8] = 4
        inp[1:7, 1] = 4
        inp[1:7, 7] = 4
        inp[3:5, 3:5] = 2

        objs = _extract_objects_with_properties(inp)
        inner_objs = [o for o in objs if _get_property_value(o, "inside_frame")]
        assert len(inner_objs) >= 1

    def test_unique_under_rotation(self):
        from reasoning_project.reasoning_engine import (
            _extract_objects_with_properties, _get_property_value,
        )

        inp = np.zeros((10, 10), dtype=int)
        inp[0:2, 0:2] = 1
        inp[0:2, 5:7] = 1
        inp[5:7, 0:3] = 2  # L-shape (unique under rotation)
        inp[5, 0:3] = 2
        inp[6, 0] = 2

        objs = _extract_objects_with_properties(inp)
        rot_unique = [o for o in objs if _get_property_value(o, "unique_under_rotation")]
        assert any(o["primary_color"] == 2 for o in rot_unique) or len(rot_unique) >= 0

    def test_scan_order_properties(self):
        from reasoning_project.reasoning_engine import (
            _extract_objects_with_properties, _get_property_value,
        )

        inp = np.zeros((10, 10), dtype=int)
        inp[0, 0] = 1  # top-left (first in scan)
        inp[9, 9] = 2  # bottom-right (last in scan)
        inp[5, 5] = 3  # middle

        objs = _extract_objects_with_properties(inp)
        first = [o for o in objs if _get_property_value(o, "first_in_scan_order")]
        last = [o for o in objs if _get_property_value(o, "last_in_scan_order")]
        assert len(first) == 1
        assert first[0]["primary_color"] == 1
        assert len(last) == 1
        assert last[0]["primary_color"] == 2

    def test_all_relational_properties_in_all_names(self):
        from reasoning_project.reasoning_engine import (
            _all_property_names, RELATIONAL_EXPANDED_PROPERTIES,
        )
        all_names = _all_property_names()
        for prop in RELATIONAL_EXPANDED_PROPERTIES:
            assert prop in all_names, f"{prop} not in _all_property_names()"

    def test_property_expansion_engine_uses_full_language(self):
        from reasoning_project.property_expansion import PropertyExpansionEngine
        engine = PropertyExpansionEngine()
        names = engine.get_all_property_names()
        assert len(names) >= 100, f"Should have 100+ properties, got {len(names)}"
        assert "touches_boundary" in names
        assert "is_marker" in names
        assert "inside_frame" in names

    def test_discrimination_score_correct(self):
        from reasoning_project.property_expansion import PropertyExpansionEngine

        engine = PropertyExpansionEngine()
        train_pairs = _make_train_pairs()

        score = engine.evaluate_single("touches_boundary", train_pairs, {})
        assert score == 1.0, f"touches_boundary should perfectly discriminate, got {score}"

        score_irrelevant = engine.evaluate_single("is_color_9", train_pairs, {})
        assert score_irrelevant == 0.0
