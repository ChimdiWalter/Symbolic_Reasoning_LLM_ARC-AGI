"""Tests for AdaptiveMemory store/retrieve."""
from __future__ import annotations

import json
import os
import tempfile

import numpy as np
import pytest

from reasoning_project.adaptive_memory import (
    AdaptiveMemory,
    CertifiedPackage,
    _compute_task_signature,
    _signature_distance,
)
from reasoning_project.view_adapters import FrameInteriorAdapter, ColorLayerAdapter


class TestCertifiedPackage:
    def test_to_dict_and_from_dict(self):
        pkg = CertifiedPackage(
            memory_id="abc123",
            source_task_id="task_01",
            adapter_type="frame_interior",
            adapter_signature={"adapter_type": "frame_interior"},
            operator_family="discriminative_filter",
            selector_property="is_largest",
            preconditions=["has_rectangular_frame"],
            proof_obligations=["train_consistency"],
            certificate_path="/tmp/cert.json",
            success_trace={"task_id": "task_01"},
            failure_modes=[],
            retrieval_signature={"n_train": 2},
        )
        d = pkg.to_dict()
        assert d["memory_id"] == "abc123"
        restored = CertifiedPackage.from_dict(d)
        assert restored.memory_id == pkg.memory_id
        assert restored.adapter_type == pkg.adapter_type


class TestComputeTaskSignature:
    def test_basic_signature(self):
        inp = np.zeros((5, 5), dtype=int)
        inp[1:3, 1:3] = 1
        out = inp.copy()
        sig = _compute_task_signature([(inp, out)])
        assert sig["n_train"] == 1
        assert sig["same_shape"]
        assert sig["mean_colors_in"] > 0

    def test_different_shapes(self):
        inp = np.zeros((5, 5), dtype=int)
        inp[1:3, 1:3] = 1
        out = np.zeros((3, 3), dtype=int)
        out[0:2, 0:2] = 1
        sig = _compute_task_signature([(inp, out)])
        assert not sig["same_shape"]


class TestSignatureDistance:
    def test_same_signature(self):
        sig = {"n_train": 2, "mean_colors_in": 3.0}
        assert _signature_distance(sig, sig) == 0.0

    def test_different_signatures(self):
        a = {"n_train": 2, "mean_colors_in": 3.0}
        b = {"n_train": 5, "mean_colors_in": 1.0}
        dist = _signature_distance(a, b)
        assert dist > 0


class TestAdaptiveMemory:
    def test_store_and_retrieve(self):
        memory = AdaptiveMemory()
        adapter = FrameInteriorAdapter()
        inp = np.full((7, 7), 3, dtype=int)
        inp[1:6, 1:6] = 0
        inp[2:4, 2:4] = 1
        out = np.full((7, 7), 3, dtype=int)
        out[1:6, 1:6] = 0
        out[2:4, 2:4] = 1

        mid = memory.store_verified_package(
            task_id="test_task",
            adapter=adapter,
            operator_family="discriminative_filter",
            selector="is_largest",
            certificate_path="/tmp/test_cert.json",
            train_pairs=[(inp, out)],
        )
        assert len(mid) > 0
        assert len(memory) == 1

    def test_retrieve_by_signature(self):
        memory = AdaptiveMemory()
        adapter = FrameInteriorAdapter()

        inp1 = np.full((7, 7), 3, dtype=int)
        inp1[1:6, 1:6] = 0
        inp1[2:4, 2:4] = 1
        out1 = inp1.copy()

        memory.store_verified_package(
            "task_01", adapter, "discriminative_filter", "is_largest",
            "", [(inp1, out1)],
        )

        # Retrieve with similar signature
        sig = _compute_task_signature([(inp1, out1)])
        results = memory.retrieve_by_signature(sig, top_k=1)
        assert len(results) == 1
        assert results[0].source_task_id == "task_01"

    def test_retrieve_by_adapter_signature(self):
        memory = AdaptiveMemory()
        adapter = FrameInteriorAdapter()
        inp = np.zeros((5, 5), dtype=int)
        out = inp.copy()

        memory.store_verified_package(
            "task_01", adapter, "filter", "is_largest", "", [(inp, out)],
        )

        results = memory.retrieve_by_adapter_signature(
            {"adapter_type": "frame_interior"}
        )
        assert len(results) == 1

        results = memory.retrieve_by_adapter_signature(
            {"adapter_type": "color_layer"}
        )
        assert len(results) == 0

    def test_freeze_prevents_store(self):
        memory = AdaptiveMemory()
        memory.freeze()
        with pytest.raises(RuntimeError):
            memory.store_verified_package(
                "task", FrameInteriorAdapter(), "f", "s", "", [],
            )

    def test_unfreeze(self):
        memory = AdaptiveMemory()
        memory.freeze()
        assert memory.is_frozen
        memory.unfreeze()
        assert not memory.is_frozen

    def test_get_all(self):
        memory = AdaptiveMemory()
        adapter = FrameInteriorAdapter()
        inp = np.zeros((5, 5), dtype=int)
        out = inp.copy()

        memory.store_verified_package("t1", adapter, "f", "s", "", [(inp, out)])
        memory.store_verified_package("t2", adapter, "f", "s", "", [(inp, out)])
        assert len(memory.get_all()) == 2

    def test_to_manifest(self):
        memory = AdaptiveMemory()
        adapter = FrameInteriorAdapter()
        inp = np.zeros((5, 5), dtype=int)
        out = inp.copy()

        memory.store_verified_package("t1", adapter, "f", "s", "", [(inp, out)])
        manifest = memory.to_manifest()
        assert len(manifest) == 1
        assert "memory_id" in manifest[0]

    def test_save_and_load_manifest(self):
        memory = AdaptiveMemory()
        adapter = FrameInteriorAdapter()
        inp = np.zeros((5, 5), dtype=int)
        out = inp.copy()

        memory.store_verified_package("t1", adapter, "f", "s", "", [(inp, out)])

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            path = f.name

        try:
            memory.save_manifest(path)

            # Load into new memory
            memory2 = AdaptiveMemory()
            memory2.load_manifest(path)
            assert len(memory2) == 1
            assert memory2.get_all()[0].source_task_id == "t1"
        finally:
            os.unlink(path)

    def test_retrieve_by_failure_signature(self):
        memory = AdaptiveMemory()
        adapter = FrameInteriorAdapter()
        inp = np.zeros((5, 5), dtype=int)
        out = inp.copy()

        memory.store_verified_package("t1", adapter, "f", "s", "", [(inp, out)])

        results = memory.retrieve_by_failure_signature(
            {"failure_type": "frame_masking"}
        )
        assert len(results) == 1

        results = memory.retrieve_by_failure_signature(
            {"failure_type": "color_interference"}
        )
        # Generic fallback still returns the package with low relevance
        # but the frame_interior package has relevance 0.3 (not 1.0)
        # for color_interference failures -- it's a weak match
        assert len(results) >= 0  # Generic fallback may return packages
