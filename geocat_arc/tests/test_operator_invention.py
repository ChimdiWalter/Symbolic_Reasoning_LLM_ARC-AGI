"""Tests for operator invention — failure atoms, clustering, verification, promotion."""
import pytest
import tempfile
import os
import numpy as np
from geocat_arc.operator_invention.failure_atom import FailureAtom
from geocat_arc.operator_invention.failure_clustering import cluster_failures, failure_distance
from geocat_arc.operator_invention.invented_operator import InventedOperator
from geocat_arc.operator_invention.verifier import verify_operator, generate_certificate
from geocat_arc.operator_invention.promotion_registry import PromotionRegistry, PromotionError


class TestFailureAtom:
    def test_from_prediction_identical(self):
        grid = [[1, 2], [3, 4]]
        atom = FailureAtom.from_prediction("t1", "prog", [grid], [grid])
        assert atom.error_rate == 0.0

    def test_from_prediction_all_wrong(self):
        pred = [[0, 0], [0, 0]]
        target = [[1, 1], [1, 1]]
        atom = FailureAtom.from_prediction("t2", "prog", [pred], [target])
        assert atom.error_rate == 1.0

    def test_from_prediction_partial(self):
        pred = [[1, 0], [0, 0]]
        target = [[1, 1], [1, 1]]
        atom = FailureAtom.from_prediction("t3", "prog", [pred], [target])
        assert 0.0 < atom.error_rate < 1.0

    def test_error_maps_created(self):
        pred = [[1, 0], [0, 1]]
        target = [[1, 1], [1, 1]]
        atom = FailureAtom.from_prediction("t4", "prog", [pred], [target])
        assert len(atom.cell_error_maps) == 1
        assert atom.cell_error_maps[0].shape == (2, 2)

    def test_failure_distribution_populated(self):
        pred = [[0]]
        target = [[1]]
        atom = FailureAtom.from_prediction("t5", "prog", [pred], [target])
        assert len(atom.failure_distribution) > 0
        assert sum(atom.failure_distribution.values()) > 0


class TestFailureClustering:
    def _make_atom(self, task_id, error_rate, dist=None):
        if dist is None:
            dist = {"missing_operator": 0.5, "wrong_parameter": 0.5}
        return FailureAtom(
            task_id=task_id,
            candidate_program_repr="prog",
            predicted_outputs=[[[0]]],
            target_outputs=[[[1]]],
            error_rate=error_rate,
            failure_distribution=dist,
        )

    def test_empty_input(self):
        assert cluster_failures([]) == []

    def test_single_atom(self):
        clusters = cluster_failures([self._make_atom("t1", 0.5)])
        assert len(clusters) == 1
        assert len(clusters[0]) == 1

    def test_groups_similar(self):
        atoms = [
            self._make_atom("t1", 0.1),
            self._make_atom("t2", 0.12),
            self._make_atom("t3", 0.9),
        ]
        clusters = cluster_failures(atoms, distance_threshold=0.3)
        assert len(clusters) == 2

    def test_failure_distance_identical(self):
        a = self._make_atom("t1", 0.5)
        assert failure_distance(a, a) == 0.0


class TestInventedOperator:
    def test_apply_with_fn(self):
        op = InventedOperator(
            name="double", input_types=["int"], output_type="int",
            preconditions=[], postconditions=[], source_cluster_ids=[],
            apply_fn=lambda x: x * 2,
        )
        assert op.apply(5) == 10

    def test_apply_without_fn_raises(self):
        op = InventedOperator(
            name="noop", input_types=[], output_type="int",
            preconditions=[], postconditions=[], source_cluster_ids=[],
        )
        with pytest.raises(RuntimeError):
            op.apply(1)

    def test_to_dict(self):
        op = InventedOperator(
            name="op1", input_types=["GRID"], output_type="GRID",
            preconditions=["has_objects"], postconditions=["modified"],
            source_cluster_ids=["c1"],
        )
        d = op.to_dict()
        assert d["name"] == "op1"
        assert d["input_types"] == ["GRID"]


class TestVerifier:
    def test_verify_passing(self):
        op = InventedOperator(
            name="inc", input_types=["int"], output_type="int",
            preconditions=[], postconditions=[], source_cluster_ids=[],
            apply_fn=lambda x: x + 1,
        )
        cases = [
            {"input": 1, "expected_output": 2},
            {"input": 10, "expected_output": 11},
        ]
        result = verify_operator(op, cases)
        assert result.passed
        assert result.exact_matches == 2
        assert result.total == 2

    def test_verify_failing(self):
        op = InventedOperator(
            name="wrong", input_types=["int"], output_type="int",
            preconditions=[], postconditions=[], source_cluster_ids=[],
            apply_fn=lambda x: x,
        )
        cases = [{"input": 1, "expected_output": 2}]
        result = verify_operator(op, cases)
        assert not result.passed

    def test_verify_no_apply_fn(self):
        op = InventedOperator(
            name="noop", input_types=[], output_type="int",
            preconditions=[], postconditions=[], source_cluster_ids=[],
        )
        result = verify_operator(op, [{"input": 1, "expected_output": 1}])
        assert not result.passed

    def test_generate_certificate(self):
        op = InventedOperator(
            name="inc", input_types=["int"], output_type="int",
            preconditions=[], postconditions=[], source_cluster_ids=[],
            apply_fn=lambda x: x + 1,
        )
        cases = [{"input": 1, "expected_output": 2}]
        result = verify_operator(op, cases)
        cert = generate_certificate(op, result)
        assert cert["verified"] is True
        assert cert["operator_name"] == "inc"


class TestPromotionRegistry:
    def test_register_verified(self):
        reg = PromotionRegistry()
        op = InventedOperator(
            name="op1", input_types=[], output_type="int",
            preconditions=[], postconditions=[], source_cluster_ids=[],
        )
        cert = {"verified": True}
        reg.register(op, cert)
        assert reg.is_promoted("op1")
        assert len(reg) == 1

    def test_reject_unverified(self):
        reg = PromotionRegistry()
        op = InventedOperator(
            name="op2", input_types=[], output_type="int",
            preconditions=[], postconditions=[], source_cluster_ids=[],
        )
        cert = {"verified": False}
        with pytest.raises(PromotionError):
            reg.register(op, cert)
        assert not reg.is_promoted("op2")

    def test_get_promoted(self):
        reg = PromotionRegistry()
        op = InventedOperator(
            name="op1", input_types=[], output_type="int",
            preconditions=[], postconditions=[], source_cluster_ids=[],
        )
        reg.register(op, {"verified": True})
        promoted = reg.get_promoted()
        assert len(promoted) == 1
        assert promoted[0].name == "op1"

    def test_save_load_roundtrip(self):
        reg = PromotionRegistry()
        op = InventedOperator(
            name="op1", input_types=["GRID"], output_type="GRID",
            preconditions=["p1"], postconditions=["q1"],
            source_cluster_ids=["c1"],
        )
        reg.register(op, {"verified": True, "exact_matches": 3, "total_tests": 3})

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            reg.save(path)
            reg2 = PromotionRegistry()
            reg2.load(path)
            assert len(reg2) == 1
            assert reg2.is_promoted("op1")
        finally:
            os.unlink(path)
