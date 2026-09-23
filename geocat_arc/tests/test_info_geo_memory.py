"""Tests for information-geometric memory."""
import math
import pytest
import tempfile
import os
from geocat_arc.information_geometric_memory.belief_distribution import BeliefDistribution
from geocat_arc.information_geometric_memory.distance_metrics import (
    kl_divergence, js_divergence, hellinger_distance, fisher_rao_categorical,
)
from geocat_arc.information_geometric_memory.memory_atom import MemoryAtom
from geocat_arc.information_geometric_memory.memory_store import MemoryStore
from geocat_arc.information_geometric_memory.retrieval import retrieve_similar
from geocat_arc.information_geometric_memory.drift_monitor import DriftMonitor


class TestBeliefDistribution:
    def test_normalize(self):
        bd = BeliefDistribution({"a": 2.0, "b": 3.0})
        assert abs(sum(bd.probs.values()) - 1.0) < 1e-10

    def test_from_counts(self):
        bd = BeliefDistribution.from_counts({"x": 10, "y": 20, "z": 70})
        assert abs(bd["x"] - 0.1) < 1e-10
        assert abs(bd["y"] - 0.2) < 1e-10

    def test_uniform(self):
        bd = BeliefDistribution.uniform(["a", "b", "c"])
        for v in bd.probs.values():
            assert abs(v - 1/3) < 1e-10

    def test_entropy_uniform(self):
        bd = BeliefDistribution.uniform(["a", "b"])
        assert abs(bd.entropy() - math.log(2)) < 1e-10

    def test_serialization(self):
        bd = BeliefDistribution({"a": 0.3, "b": 0.7})
        d = bd.to_dict()
        bd2 = BeliefDistribution.from_dict(d)
        assert abs(bd2["a"] - bd["a"]) < 1e-10


class TestDistanceMetrics:
    def test_kl_self_zero(self):
        p = {"a": 0.5, "b": 0.5}
        assert kl_divergence(p, p) < 1e-6

    def test_kl_asymmetric(self):
        p = {"a": 0.9, "b": 0.1}
        q = {"a": 0.5, "b": 0.5}
        assert abs(kl_divergence(p, q) - kl_divergence(q, p)) > 1e-6

    def test_js_symmetric(self):
        p = {"a": 0.9, "b": 0.1}
        q = {"a": 0.1, "b": 0.9}
        assert abs(js_divergence(p, q) - js_divergence(q, p)) < 1e-10

    def test_js_self_zero(self):
        p = {"a": 0.5, "b": 0.5}
        assert js_divergence(p, p) < 1e-6

    def test_hellinger_self_zero(self):
        p = {"a": 0.5, "b": 0.5}
        assert hellinger_distance(p, p) < 1e-6

    def test_hellinger_range(self):
        p = {"a": 0.9, "b": 0.1}
        q = {"a": 0.1, "b": 0.9}
        h = hellinger_distance(p, q)
        assert 0 <= h <= 1

    def test_fisher_rao_self_zero(self):
        p = {"a": 0.5, "b": 0.5}
        assert fisher_rao_categorical(p, p) < 1e-6

    def test_fisher_rao_positive(self):
        p = {"a": 0.9, "b": 0.1}
        q = {"a": 0.1, "b": 0.9}
        assert fisher_rao_categorical(p, q) > 0


class TestMemoryAtom:
    def test_serialization_roundtrip(self):
        atom = MemoryAtom(
            task_id="test_001",
            status="solved",
            program_repr="segment -> render",
            operator_distribution=BeliefDistribution({"segment": 0.5, "render": 0.5}),
            score=1.5,
        )
        d = atom.to_dict()
        atom2 = MemoryAtom.from_dict(d)
        assert atom2.task_id == atom.task_id
        assert atom2.status == atom.status
        assert abs(atom2.score - atom.score) < 1e-10


class TestMemoryStore:
    def test_add_and_get(self):
        store = MemoryStore()
        atom = MemoryAtom(task_id="t1", status="solved")
        store.add(atom)
        assert store.get("t1") is atom
        assert store.get("t2") is None

    def test_solved_atoms(self):
        store = MemoryStore()
        store.add(MemoryAtom(task_id="t1", status="solved"))
        store.add(MemoryAtom(task_id="t2", status="failed"))
        assert len(store.solved_atoms()) == 1

    def test_save_load(self):
        store = MemoryStore()
        store.add(MemoryAtom(
            task_id="t1", status="solved",
            operator_distribution=BeliefDistribution({"a": 0.5, "b": 0.5}),
        ))
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            store.save(path)
            store2 = MemoryStore()
            store2.load(path)
            assert len(store2) == 1
            assert store2.get("t1").task_id == "t1"
        finally:
            os.unlink(path)


class TestRetrieval:
    def test_retrieve_closest(self):
        store = MemoryStore()
        store.add(MemoryAtom(
            task_id="t1", status="solved",
            operator_distribution=BeliefDistribution({"a": 0.9, "b": 0.1}),
        ))
        store.add(MemoryAtom(
            task_id="t2", status="solved",
            operator_distribution=BeliefDistribution({"a": 0.1, "b": 0.9}),
        ))

        query = BeliefDistribution({"a": 0.85, "b": 0.15})
        results = retrieve_similar(query, store, metric="js", top_k=2)
        assert len(results) == 2
        assert results[0][0].task_id == "t1"


class TestDriftMonitor:
    def test_no_drift_initially(self):
        dm = DriftMonitor()
        assert not dm.detect_drift()

    def test_detects_drift(self):
        dm = DriftMonitor(window_size=3)
        dm.record(BeliefDistribution({"a": 0.9, "b": 0.1}))
        dm.record(BeliefDistribution({"a": 0.9, "b": 0.1}))
        dm.record(BeliefDistribution({"a": 0.1, "b": 0.9}))
        assert dm.detect_drift(threshold=0.01)
