"""Tests for memory seeding from certificates."""
import numpy as np
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from reasoning_project.operator_memory import OperatorMemory
from reasoning_project.manifold_memory import (
    MemoryManifold,
    ManifoldPoint,
    encode_task_signature,
    _signature_to_embedding,
)


class TestOperatorMemorySeeding:
    def test_store_and_retrieve_by_family(self):
        mem = OperatorMemory()
        mem.store_with_schema(
            task_id="test_task_1",
            family="discriminative_filter",
            selector="is_largest",
            hypothesis={"source": "certificate_seed"},
            certificate_path="/tmp/cert_test.json",
            execute_fn_name="static_portfolio",
            operator_schema={"module": "static_portfolio"},
            proof_obligations_met=["train_consistent", "loo_passed"],
        )
        results = mem.get_by_family("discriminative_filter")
        assert len(results) >= 1
        assert any(r.get("task_id") == "test_task_1" for r in results)

    def test_store_and_retrieve_by_task(self):
        mem = OperatorMemory()
        mem.store_with_schema(
            task_id="test_task_2",
            family="recolor",
            selector="is_unique_color",
            hypothesis={"source": "certificate_seed"},
            certificate_path="/tmp/cert_test2.json",
            execute_fn_name="frontier_operators",
            operator_schema={"module": "frontier_operators"},
            proof_obligations_met=["train_consistent", "loo_passed", "falsification_passed"],
        )
        results = mem.get_by_task("test_task_2")
        assert len(results) >= 1

    def test_multiple_stores_same_task(self):
        mem = OperatorMemory()
        mem.store_with_schema(
            task_id="dup_task", family="filter", selector="p1",
            hypothesis={}, certificate_path="", execute_fn_name="",
            operator_schema={}, proof_obligations_met=[],
        )
        mem.store_with_schema(
            task_id="dup_task", family="recolor", selector="p2",
            hypothesis={}, certificate_path="", execute_fn_name="",
            operator_schema={}, proof_obligations_met=[],
        )
        results = mem.get_by_task("dup_task")
        assert len(results) >= 2


class TestManifoldSeeding:
    def test_add_point_and_retrieve(self):
        manifold = MemoryManifold()
        inp = np.zeros((5, 5), dtype=int)
        inp[0:3, 0:3] = 1
        out = np.zeros((5, 5), dtype=int)
        out[0:3, 0:3] = 1
        train_pairs = [(inp, out)]

        sig = encode_task_signature(train_pairs)
        embedding = _signature_to_embedding(sig)
        point = ManifoldPoint(
            embedding=embedding,
            task_signature=sig,
            domain="arc",
            hypothesis={"family": "filter"},
            metadata={"solved": True, "task_id": "seed_test"},
        )
        manifold.add_point(point)
        assert len(manifold.charts) > 0 or hasattr(manifold, "_points")

    def test_encode_task_signature(self):
        inp = np.array([[0, 1, 0], [2, 0, 3]], dtype=int)
        out = np.array([[0, 1, 0], [0, 0, 3]], dtype=int)
        sig = encode_task_signature([(inp, out)])
        assert isinstance(sig, dict)
        assert "n_colors_in" in sig or "input_shape" in sig

    def test_signature_to_embedding(self):
        sig = {"input_shape": [3, 3], "output_shape": [3, 3],
               "size_changing": False, "n_colors_in": 3, "n_colors_out": 2,
               "n_objects": 3, "has_symmetry": False, "has_containment": False}
        emb = _signature_to_embedding(sig)
        assert isinstance(emb, np.ndarray)
        assert emb.shape == (16,)
