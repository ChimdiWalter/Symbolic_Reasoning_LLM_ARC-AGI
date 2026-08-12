"""Tests for neural_math module -- 6 neural-math components.

Covers:
- TypedDSL: valid/invalid program detection, enumeration count
- SheafConsistency: consistent/inconsistent assignments, optimization
- EquivariantFeatures: rotation invariance, color permutation invariance, Hu moments
- InvariantDiscovery: preserved/transformed property detection
- CounterfactualVerifier: invariance to irrelevant changes
- TopologicalLoss: H0/H1 computation, distance metric, persistence
- Integration: end-to-end typed search with invariant pruning
"""

from __future__ import annotations

import numpy as np
import pytest

from reasoning_project.neural_math import (
    TypeChecker,
    typed_enumerate,
    count_typed_programs,
    SheafConsistency,
    EquivariantFeatures,
    InvariantDiscovery,
    CounterfactualVerifier,
    TopologicalLoss,
    OP_SIGNATURES,
    TYPES,
)


# ====================================================================
# 1. TypedDSL tests
# ====================================================================

class TestTypedDSL:
    def test_valid_single_op(self):
        """extract_objects takes Grid -> Objects, and Grid is on the stack."""
        tc = TypeChecker()
        assert tc.is_valid_program(["extract_objects"]) is True

    def test_valid_two_op_pipeline(self):
        """extract_objects -> keep_largest: Grid -> Objects -> Object."""
        tc = TypeChecker()
        assert tc.is_valid_program(["extract_objects", "keep_largest"]) is True

    def test_invalid_program_wrong_input(self):
        """keep_largest needs Objects but stack only has Grid."""
        tc = TypeChecker()
        assert tc.is_valid_program(["keep_largest"]) is False

    def test_invalid_program_unknown_op(self):
        tc = TypeChecker()
        assert tc.is_valid_program(["nonexistent_op"]) is False

    def test_empty_program_valid(self):
        tc = TypeChecker()
        assert tc.is_valid_program([]) is True

    def test_output_type(self):
        tc = TypeChecker()
        assert tc.output_type(["extract_objects"]) == "Objects"
        assert tc.output_type(["extract_objects", "keep_largest"]) == "Object"
        assert tc.output_type(["keep_largest"]) is None  # invalid

    def test_typed_enumerate_depth1(self):
        """At depth 1, only operations that accept Grid should appear."""
        progs = list(typed_enumerate(max_depth=1))
        assert len(progs) > 0
        # extract_objects takes Grid, so it should be in the list.
        assert ["extract_objects"] in progs
        # keep_largest takes Objects -- should NOT be in depth-1 list.
        assert ["keep_largest"] not in progs

    def test_typed_enumerate_depth2_includes_composition(self):
        progs = list(typed_enumerate(max_depth=2))
        assert ["extract_objects", "keep_largest"] in progs
        assert ["extract_objects", "count"] in progs

    def test_count_typed_programs_ratio(self):
        """Type-valid programs should be a strict subset of all combos."""
        counts = count_typed_programs(max_depth=2)
        assert counts["valid"] > 0
        assert counts["valid"] < counts["total"]
        assert 0 < counts["ratio"] < 1.0


# ====================================================================
# 2. SheafConsistency tests
# ====================================================================

class TestSheafConsistency:
    def test_fully_consistent(self):
        """All nodes assigned the same value with equality constraint."""
        sheaf = SheafConsistency()
        sheaf.add_relation(0, 1, "same_color", lambda a, b: a == b)
        sheaf.add_relation(1, 2, "same_color", lambda a, b: a == b)
        assignment = {0: "red", 1: "red", 2: "red"}
        assert sheaf.check_global_consistency(assignment) == 1.0

    def test_partially_inconsistent(self):
        sheaf = SheafConsistency()
        sheaf.add_relation(0, 1, "same_color", lambda a, b: a == b)
        sheaf.add_relation(1, 2, "same_color", lambda a, b: a == b)
        assignment = {0: "red", 1: "red", 2: "blue"}
        score = sheaf.check_global_consistency(assignment)
        assert score == 0.5

    def test_detect_inconsistency(self):
        sheaf = SheafConsistency()
        sheaf.add_relation(0, 1, "same_color", lambda a, b: a == b)
        sheaf.add_relation(1, 2, "same_color", lambda a, b: a == b)
        assignment = {0: "red", 1: "red", 2: "blue"}
        violations = sheaf.detect_inconsistency(assignment)
        assert len(violations) == 1
        assert violations[0] == (1, 2, "same_color")

    def test_find_consistent_assignment(self):
        sheaf = SheafConsistency()
        sheaf.add_relation(0, 1, "same_color", lambda a, b: a == b)
        sheaf.add_relation(1, 2, "same_color", lambda a, b: a == b)
        candidates = {0: ["red", "blue"], 1: ["red", "blue"], 2: ["red", "blue"]}
        assignment = sheaf.find_consistent_assignment(candidates)
        score = sheaf.check_global_consistency(assignment)
        assert score == 1.0
        # All should be the same colour.
        vals = list(assignment.values())
        assert vals[0] == vals[1] == vals[2]


# ====================================================================
# 3. EquivariantFeatures tests
# ====================================================================

class TestEquivariantFeatures:
    def test_rotation_invariance_hu_moments(self):
        """Hu moments should be (approximately) invariant to 90-deg rotation."""
        mask = np.zeros((7, 7), dtype=np.float64)
        mask[1:6, 2:5] = 1.0  # vertical rectangle
        rotated = np.rot90(mask)

        hu_orig = EquivariantFeatures.object_invariants(mask)
        hu_rot = EquivariantFeatures.object_invariants(rotated)

        # Area, perimeter should be identical.
        assert hu_orig[0] == hu_rot[0]  # area
        assert hu_orig[1] == hu_rot[1]  # perimeter
        # Hu moments (indices 6-12) should be close.
        np.testing.assert_allclose(hu_orig[6:13], hu_rot[6:13], atol=1e-6)

    def test_color_permutation_invariance(self):
        """color_orbit should be identical under colour permutation."""
        grid_a = np.array([[1, 1, 2], [2, 3, 3], [0, 0, 0]], dtype=int)
        # Permute: 1->4, 2->5, 3->6
        grid_b = np.array([[4, 4, 5], [5, 6, 6], [0, 0, 0]], dtype=int)

        orbit_a = EquivariantFeatures.color_orbit(grid_a)
        orbit_b = EquivariantFeatures.color_orbit(grid_b)
        np.testing.assert_array_equal(orbit_a, orbit_b)

    def test_relation_invariants_shape(self):
        obj_a = np.zeros((5, 5), dtype=np.float64)
        obj_a[0:2, 0:2] = 1.0
        obj_b = np.zeros((5, 5), dtype=np.float64)
        obj_b[3:5, 3:5] = 1.0
        rel = EquivariantFeatures.relation_invariants(obj_a, obj_b)
        assert rel.shape == (7,)
        assert rel[1] == 1.0  # same size => ratio = 1
        assert rel[2] == 0.0  # no overlap

    def test_compute_grid_features(self):
        grid = np.array([[1, 0, 2], [0, 3, 0]], dtype=int)
        feats = EquivariantFeatures.compute(grid)
        assert feats.ndim == 1
        assert feats.shape[0] == 26  # 16 object + 10 colour orbit


# ====================================================================
# 4. InvariantDiscovery tests
# ====================================================================

class TestInvariantDiscovery:
    def test_preserved_properties(self):
        """Grid shape and object count preserved across pairs."""
        pairs = [
            (np.array([[1, 0], [0, 2]]), np.array([[3, 0], [0, 4]])),
            (np.array([[5, 0], [0, 6]]), np.array([[7, 0], [0, 8]])),
        ]
        disc = InvariantDiscovery()
        result = disc.discover(pairs)
        assert "grid_shape" in result["preserved"]
        assert "object_count" in result["preserved"]

    def test_transformed_property_detection(self):
        """total_nonzero_area doubles between input and output."""
        pairs = [
            (np.array([[1, 0], [0, 0]]), np.array([[1, 1], [0, 0]])),
            (np.array([[0, 2], [0, 0]]), np.array([[2, 2], [0, 0]])),
        ]
        disc = InvariantDiscovery()
        result = disc.discover(pairs)
        transformed_names = [t[0] for t in result["transformed"]]
        assert "total_nonzero_area" in transformed_names

    def test_prune_search_space(self):
        """Candidates violating preserved invariants should be removed."""
        disc = InvariantDiscovery()
        invariants = {"preserved": ["grid_shape"], "transformed": [], "irrelevant": []}
        candidates = [
            {"input": np.zeros((3, 3), dtype=int), "prediction": np.zeros((3, 3), dtype=int)},
            {"input": np.zeros((3, 3), dtype=int), "prediction": np.zeros((4, 4), dtype=int)},
        ]
        kept = disc.prune_search_space(candidates, invariants)
        assert len(kept) == 1


# ====================================================================
# 5. CounterfactualVerifier tests
# ====================================================================

class TestCounterfactualVerifier:
    def test_invariance_to_irrelevant(self):
        """A hypothesis that returns a constant output should be fully
        invariant to all irrelevant interventions."""
        grid = np.array([[1, 0, 0], [0, 2, 0], [0, 0, 3]], dtype=int)
        pairs = [(grid, np.ones((3, 3), dtype=int))]

        def constant_hypothesis(h, g):
            return np.ones((3, 3), dtype=int)

        cv = CounterfactualVerifier(rng=np.random.RandomState(0))
        score = cv.causal_score("unused", pairs, constant_hypothesis)
        assert score == 1.0

    def test_generate_counterfactual_types(self):
        grid = np.array([[1, 0], [0, 2]], dtype=int)
        cv = CounterfactualVerifier(rng=np.random.RandomState(0))
        for itype in CounterfactualVerifier.INTERVENTIONS:
            cf = cv.generate_counterfactual(grid, itype)
            assert isinstance(cf, np.ndarray)
            assert cf.size > 0

    def test_verify_returns_all_interventions(self):
        grid = np.array([[1, 0], [0, 2]], dtype=int)
        pairs = [(grid, grid.copy())]
        cv = CounterfactualVerifier(rng=np.random.RandomState(0))
        results = cv.verify("h", pairs, lambda h, g: g.copy())
        assert set(results.keys()) == set(CounterfactualVerifier.INTERVENTIONS)


# ====================================================================
# 6. TopologicalLoss tests
# ====================================================================

class TestTopologicalLoss:
    def test_single_component(self):
        grid = np.array([[1, 1, 0], [1, 1, 0], [0, 0, 0]], dtype=int)
        topo = TopologicalLoss.grid_topology(grid)
        assert topo["n_components"] == 1
        assert topo["n_holes"] == 0
        assert topo["euler_characteristic"] == 1

    def test_two_components(self):
        grid = np.array([[1, 0, 2], [0, 0, 0], [3, 0, 4]], dtype=int)
        topo = TopologicalLoss.grid_topology(grid)
        assert topo["n_components"] == 4
        assert topo["betti_0"] == 4

    def test_hole_detection(self):
        """A ring should have 1 hole."""
        grid = np.array([
            [0, 0, 0, 0, 0],
            [0, 1, 1, 1, 0],
            [0, 1, 0, 1, 0],
            [0, 1, 1, 1, 0],
            [0, 0, 0, 0, 0],
        ], dtype=int)
        topo = TopologicalLoss.grid_topology(grid)
        assert topo["n_components"] == 1
        assert topo["n_holes"] == 1
        assert topo["euler_characteristic"] == 0

    def test_distance_identical_grids(self):
        grid = np.array([[1, 0], [0, 1]], dtype=int)
        assert TopologicalLoss.topology_distance(grid, grid) == 0.0

    def test_distance_different_grids(self):
        a = np.array([[1, 0], [0, 0]], dtype=int)
        b = np.array([[1, 0], [0, 1]], dtype=int)
        assert TopologicalLoss.topology_distance(a, b) > 0.0

    def test_persistence_diagram(self):
        grid = np.array([[1, 2, 0], [0, 3, 0], [0, 0, 0]], dtype=int)
        diagram = TopologicalLoss.persistence_diagram(grid)
        assert isinstance(diagram, list)
        assert len(diagram) > 0
        for birth, death, dim in diagram:
            assert dim in (0, 1)
            assert birth <= death or death == float("inf")

    def test_topology_preserving_score_perfect(self):
        output = np.array([[1, 1], [1, 0]], dtype=int)
        score = TopologicalLoss.topology_preserving_score(output, output, output)
        assert score == 1.0


# ====================================================================
# Integration test
# ====================================================================

class TestIntegration:
    def test_typed_search_with_invariant_pruning(self):
        """End-to-end: enumerate typed programs, extract invariants from
        training pairs, and prune candidate predictions."""
        # 1. Enumerate typed programs (depth 1).
        programs = list(typed_enumerate(max_depth=1))
        assert len(programs) > 0

        # 2. Create training pairs where grid_shape is preserved.
        pairs = [
            (np.array([[1, 0], [0, 2]]), np.array([[3, 0], [0, 4]])),
            (np.array([[5, 0], [0, 6]]), np.array([[7, 0], [0, 8]])),
        ]

        # 3. Discover invariants.
        disc = InvariantDiscovery()
        invariants = disc.discover(pairs)
        assert "grid_shape" in invariants["preserved"]

        # 4. Create mock candidates -- one preserves all invariants, one breaks grid_shape.
        good_pred = np.array([[9, 0], [0, 8]])
        bad_pred = np.zeros((3, 3), dtype=int)
        bad_pred[0, 0] = 9
        bad_pred[2, 2] = 8
        candidates = [
            {"input": pairs[0][0], "prediction": good_pred},
            {"input": pairs[0][0], "prediction": bad_pred},
        ]
        pruned = disc.prune_search_space(candidates, invariants)
        assert len(pruned) == 1
        assert pruned[0]["prediction"].shape == (2, 2)

        # 5. TopologicalLoss sanity check on the surviving candidate.
        score = TopologicalLoss.topology_preserving_score(
            pairs[0][0], pairs[0][1], pruned[0]["prediction"]
        )
        assert 0.0 <= score <= 1.0
