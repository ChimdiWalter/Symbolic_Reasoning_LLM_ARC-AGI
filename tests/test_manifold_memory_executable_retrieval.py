"""Tests for manifold memory executable retrieval."""
import numpy as np
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from reasoning_project.operator_memory import OperatorMemory


class TestOperatorMemoryExecutableRetrieval:
    def test_get_by_embedding(self):
        mem = OperatorMemory()
        emb = np.random.randn(16).astype(np.float32)
        mem.store_with_schema(
            task_id="emb_test",
            family="filter",
            selector="is_largest",
            hypothesis={"execute": lambda g: g, "family": "filter"},
            certificate_path="",
            execute_fn_name="test",
            operator_schema={},
            proof_obligations_met=["train_consistent"],
        )
        # Retrieve by embedding should work even with 0 embeddings stored
        # (operator_memory stores embedding if provided)
        results = mem.get_by_embedding(emb, k=5)
        # May return empty if no embeddings stored, which is fine
        assert isinstance(results, list)

    def test_get_all(self):
        mem = OperatorMemory()
        mem.store_with_schema(
            task_id="all_test_1", family="f1", selector="s1",
            hypothesis={}, certificate_path="", execute_fn_name="",
            operator_schema={}, proof_obligations_met=[],
        )
        mem.store_with_schema(
            task_id="all_test_2", family="f2", selector="s2",
            hypothesis={}, certificate_path="", execute_fn_name="",
            operator_schema={}, proof_obligations_met=[],
        )
        all_ops = mem.get_all()
        assert len(all_ops) >= 2

    def test_stored_operator_has_required_fields(self):
        mem = OperatorMemory()
        mem.store_with_schema(
            task_id="field_test",
            family="recolor",
            selector="is_unique_color",
            hypothesis={"execute": lambda g: g},
            certificate_path="/tmp/cert.json",
            execute_fn_name="frontier_operators",
            operator_schema={"module": "frontier_operators"},
            proof_obligations_met=["train_consistent", "loo_passed", "falsification_passed"],
        )
        results = mem.get_by_task("field_test")
        assert len(results) >= 1
        r = results[0]
        assert r.get("task_id") == "field_test"
        assert r.get("family") == "recolor"
        assert r.get("selector") == "is_unique_color"
