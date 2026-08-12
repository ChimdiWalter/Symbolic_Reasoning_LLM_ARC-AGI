"""Tests for topological manifold memory system."""
from __future__ import annotations

import numpy as np
import pytest

from reasoning_project.manifold_memory import (
    Fiber,
    FiberBundle,
    GeodesicSolver,
    LocalChart,
    ManifoldMismatchTrigger,
    ManifoldPoint,
    ManifoldReasoningEngine,
    MemoryManifold,
    PersistentHomologyDetector,
    ReasoningTrajectory,
    TopologicalConsistencyLoss,
    TopologicalRetriever,
    TransitionMap,
    WorkingMemoryManifold,
    _cosine_similarity,
    _signature_similarity,
    _signature_to_embedding,
    encode_task_signature,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_grid(rows: int, cols: int, fill: int = 0) -> np.ndarray:
    return np.full((rows, cols), fill, dtype=int)


def _make_point(
    domain: str = "grid",
    embedding: np.ndarray | None = None,
    sig: dict | None = None,
    hypothesis: dict | None = None,
) -> ManifoldPoint:
    if embedding is None:
        embedding = np.random.default_rng(42).random(16)
    if sig is None:
        sig = {"object_count": 3, "color_count": 4, "has_separators": False}
    return ManifoldPoint(
        embedding=embedding,
        task_signature=sig,
        domain=domain,
        hypothesis=hypothesis,
    )


def _make_train_pairs():
    """Create simple 5x5 train pairs with two colored objects."""
    rng = np.random.default_rng(0)
    pairs = []
    for _ in range(3):
        inp = np.zeros((5, 5), dtype=int)
        inp[0:2, 0:2] = 1
        inp[3:5, 3:5] = 2
        out = inp.copy()
        out[out == 2] = 0  # Remove object 2
        pairs.append((inp, out))
    return pairs


# ---------------------------------------------------------------------------
# 1. ManifoldPoint creation and signature encoding
# ---------------------------------------------------------------------------

class TestManifoldPoint:
    def test_creation(self):
        p = _make_point()
        assert p.domain == "grid"
        assert p.embedding.shape == (16,)
        assert "object_count" in p.task_signature
        assert len(p.id) > 0

    def test_custom_metadata(self):
        p = ManifoldPoint(
            embedding=np.zeros(8),
            task_signature={"a": 1},
            domain="graph",
            metadata={"solved": True},
        )
        assert p.metadata["solved"] is True
        assert p.domain == "graph"


class TestEncodeTaskSignature:
    def test_basic_signature(self):
        pairs = _make_train_pairs()
        sig = encode_task_signature(pairs)
        assert "input_shape" in sig
        assert "output_shape" in sig
        assert "n_colors_in" in sig
        assert "n_objects" in sig
        assert "has_separators" in sig
        assert "has_symmetry" in sig
        assert "has_containment" in sig
        assert "has_holes" in sig
        assert "color_transform" in sig
        assert "object_count_change" in sig

    def test_size_changing_detected(self):
        inp = np.zeros((5, 5), dtype=int)
        out = np.zeros((3, 3), dtype=int)
        sig = encode_task_signature([(inp, out)])
        assert sig["size_changing"] is True

    def test_separator_detection(self):
        grid = np.zeros((5, 5), dtype=int)
        grid[2, :] = 3  # Full row separator
        out = grid.copy()
        sig = encode_task_signature([(grid, out)])
        assert sig["has_separators"] is True


# ---------------------------------------------------------------------------
# 2. LocalChart operations
# ---------------------------------------------------------------------------

class TestLocalChart:
    def test_add_and_stats(self):
        chart = LocalChart("c1", "spatial_reasoning", "grid")
        p1 = _make_point(embedding=np.array([1.0, 0.0, 0.0]))
        p2 = _make_point(embedding=np.array([0.0, 1.0, 0.0]))
        chart.add_point(p1)
        chart.add_point(p2)
        assert len(chart.points) == 2
        np.testing.assert_allclose(chart.center, [0.5, 0.5, 0.0])
        assert chart.radius > 0

    def test_project(self):
        chart = LocalChart("c1", "test", "grid")
        p1 = _make_point(embedding=np.array([2.0, 4.0]))
        p2 = _make_point(embedding=np.array([4.0, 6.0]))
        chart.add_point(p1)
        chart.add_point(p2)
        local = chart.project(p1)
        np.testing.assert_allclose(local, [-1.0, -1.0])

    def test_distance(self):
        chart = LocalChart("c1", "test", "grid")
        p1 = _make_point(embedding=np.array([0.0, 0.0]))
        p2 = _make_point(embedding=np.array([3.0, 4.0]))
        chart.add_point(p1)
        d = chart.distance(p1, p2)
        assert d == pytest.approx(5.0)

    def test_contains(self):
        chart = LocalChart("c1", "test", "grid")
        center_pt = _make_point(embedding=np.array([0.0, 0.0]))
        near_pt = _make_point(embedding=np.array([0.1, 0.0]))
        chart.add_point(center_pt)
        chart.add_point(near_pt)
        # Point near center should be contained
        query = _make_point(embedding=np.array([0.05, 0.0]))
        assert chart.contains(query)
        # Point far away should not be contained
        far_pt = _make_point(embedding=np.array([100.0, 100.0]))
        assert not chart.contains(far_pt)


# ---------------------------------------------------------------------------
# 3. MemoryManifold add/retrieve/gap detection
# ---------------------------------------------------------------------------

class TestMemoryManifold:
    def test_add_creates_chart(self):
        m = MemoryManifold()
        p = _make_point(embedding=np.array([1.0, 2.0, 3.0]))
        chart_id = m.add_point(p)
        assert chart_id in m.charts
        assert len(m.charts[chart_id].points) == 1

    def test_add_to_existing_chart(self):
        m = MemoryManifold(auto_chart_threshold=10.0)
        p1 = _make_point(embedding=np.array([1.0, 0.0]))
        p2 = _make_point(embedding=np.array([1.1, 0.0]))
        cid1 = m.add_point(p1)
        cid2 = m.add_point(p2)
        assert cid1 == cid2
        assert len(m.charts[cid1].points) == 2

    def test_add_creates_new_chart_when_far(self):
        m = MemoryManifold(auto_chart_threshold=1.0)
        p1 = _make_point(embedding=np.array([0.0, 0.0]))
        p2 = _make_point(embedding=np.array([100.0, 100.0]))
        cid1 = m.add_point(p1)
        cid2 = m.add_point(p2)
        assert cid1 != cid2

    def test_retrieve_topological(self):
        m = MemoryManifold(auto_chart_threshold=50.0)
        # Add some points with varied signatures
        for i in range(5):
            p = _make_point(
                embedding=np.array([float(i), 0.0]),
                sig={"object_count": i, "color_count": 3},
            )
            m.add_point(p)
        query = _make_point(
            embedding=np.array([2.5, 0.0]),
            sig={"object_count": 2, "color_count": 3},
        )
        results = m.retrieve_topological(query, k=3)
        assert len(results) == 3

    def test_detect_gaps(self):
        m = MemoryManifold(auto_chart_threshold=100.0)
        # Create a cluster + an outlier
        for i in range(5):
            m.add_point(_make_point(embedding=np.array([float(i) * 0.1, 0.0])))
        m.add_point(_make_point(embedding=np.array([50.0, 50.0])))
        gaps = m.detect_gaps()
        assert len(gaps) >= 1

    def test_geodesic_distance(self):
        m = MemoryManifold(auto_chart_threshold=100.0)
        for i in range(5):
            m.add_point(_make_point(embedding=np.array([float(i), 0.0])))
        a = _make_point(embedding=np.array([0.0, 0.0]))
        b = _make_point(embedding=np.array([4.0, 0.0]))
        geo = m.geodesic_distance(a, b)
        direct = np.linalg.norm(a.embedding - b.embedding)
        assert geo <= direct + 1e-6

    def test_get_active_charts(self):
        m = MemoryManifold(auto_chart_threshold=5.0)
        p = _make_point(embedding=np.array([1.0, 0.0]))
        m.add_point(p)
        active = m.get_active_charts(_make_point(embedding=np.array([1.0, 0.0])))
        assert len(active) >= 1


# ---------------------------------------------------------------------------
# 4. TopologicalRetriever structural similarity
# ---------------------------------------------------------------------------

class TestTopologicalRetriever:
    def test_retrieve_by_structure(self):
        m = MemoryManifold(auto_chart_threshold=100.0)
        # Two groups: separators vs no separators
        for i in range(3):
            m.add_point(_make_point(
                embedding=np.array([float(i), 0.0]),
                sig={"has_separators": True, "object_count": 5, "color_count": 3},
            ))
        for i in range(3):
            m.add_point(_make_point(
                embedding=np.array([float(i) + 10.0, 0.0]),
                sig={"has_separators": False, "object_count": 5, "color_count": 3},
            ))

        retriever = TopologicalRetriever()
        query = _make_point(
            embedding=np.array([5.0, 0.0]),  # equidistant in embedding
            sig={"has_separators": True, "object_count": 5, "color_count": 3},
        )
        results = retriever.retrieve(query, m, k=3)
        assert len(results) == 3
        sep_count = sum(1 for r in results if r.task_signature.get("has_separators") is True)
        assert sep_count >= 2


# ---------------------------------------------------------------------------
# 5. PersistentHomologyDetector basic computation
# ---------------------------------------------------------------------------

class TestPersistentHomologyDetector:
    def test_h0_components(self):
        detector = PersistentHomologyDetector()
        # Two clusters far apart
        points = [
            np.array([0.0, 0.0]),
            np.array([0.1, 0.0]),
            np.array([10.0, 0.0]),
            np.array([10.1, 0.0]),
        ]
        result = detector.compute_persistence(points)
        assert "H0" in result
        assert len(result["H0"]) > 0
        # Should have at least one long-lived component (the gap between clusters)
        lifetimes = [d - b for b, d in result["H0"]]
        assert max(lifetimes) > 5.0

    def test_find_gaps(self):
        m = MemoryManifold(auto_chart_threshold=100.0)
        for i in range(4):
            m.add_point(_make_point(embedding=np.array([float(i) * 0.1, 0.0])))
        m.add_point(_make_point(embedding=np.array([50.0, 0.0])))
        detector = PersistentHomologyDetector()
        gaps = detector.find_gaps(m)
        assert len(gaps) > 0
        assert any(g["type"] == "disconnected_region" for g in gaps)

    def test_uncertainty_score(self):
        m = MemoryManifold(auto_chart_threshold=100.0)
        for i in range(5):
            m.add_point(_make_point(embedding=np.array([float(i) * 0.1, 0.0])))
        detector = PersistentHomologyDetector()
        # Point near cluster should have low uncertainty
        near = _make_point(embedding=np.array([0.2, 0.0]))
        # Point far from cluster should have high uncertainty
        far = _make_point(embedding=np.array([100.0, 100.0]))
        u_near = detector.uncertainty_score(near, m)
        u_far = detector.uncertainty_score(far, m)
        assert u_far > u_near


# ---------------------------------------------------------------------------
# 6. WorkingMemoryManifold trajectory tracking
# ---------------------------------------------------------------------------

class TestWorkingMemoryManifold:
    def test_activate_and_trajectory(self):
        m = MemoryManifold(auto_chart_threshold=10.0)
        m.add_point(_make_point(embedding=np.array([1.0, 0.0])))
        wm = WorkingMemoryManifold(m)
        q = _make_point(embedding=np.array([1.0, 0.0]))
        charts = wm.activate(q)
        assert len(charts) >= 1
        assert len(wm.trajectory) == 1

    def test_step_updates_trajectory(self):
        m = MemoryManifold()
        wm = WorkingMemoryManifold(m)
        z0 = _make_point(embedding=np.array([1.0, 0.0]))
        wm.activate(z0)
        action = np.array([0.5, 0.0])
        z1 = wm.step(z0, action)
        assert len(wm.trajectory) == 2
        np.testing.assert_allclose(z1.embedding, [1.5, 0.0])

    def test_step_with_memory(self):
        m = MemoryManifold()
        wm = WorkingMemoryManifold(m)
        z0 = _make_point(embedding=np.array([1.0, 0.0]))
        wm.activate(z0)
        mem = _make_point(embedding=np.array([3.0, 0.0]))
        action = np.array([0.0, 0.0])
        z1 = wm.step(z0, action, retrieved_memory=mem)
        # 0.7 * (1.0 + 0.0) + 0.3 * 3.0 = 0.7 + 0.9 = 1.6
        np.testing.assert_allclose(z1.embedding, [1.6, 0.0])

    def test_convergence_detection(self):
        m = MemoryManifold()
        wm = WorkingMemoryManifold(m)
        z0 = _make_point(embedding=np.array([1.0, 0.0]))
        wm.activate(z0)
        # Take a tiny step
        z1 = wm.step(z0, np.array([0.01, 0.0]))
        assert wm.is_in_solution_region(z1, threshold=0.1)


# ---------------------------------------------------------------------------
# 7. ManifoldReasoningEngine end-to-end (mock solve)
# ---------------------------------------------------------------------------

class TestManifoldReasoningEngine:
    def test_encode_task(self):
        from reasoning_project.reasoning_engine import GridDomainAdapter
        adapter = GridDomainAdapter()
        engine = ManifoldReasoningEngine(adapter)
        pairs = _make_train_pairs()
        point = engine.encode_task(pairs)
        assert isinstance(point, ManifoldPoint)
        assert point.embedding.shape[0] > 0
        assert "n_objects" in point.task_signature

    def test_update_manifold(self):
        from reasoning_project.reasoning_engine import GridDomainAdapter
        adapter = GridDomainAdapter()
        engine = ManifoldReasoningEngine(adapter)
        pairs = _make_train_pairs()
        hyp = {"strategy": "discriminative_filter", "property": "is_largest"}
        chart_id = engine.update_manifold(pairs, hyp)
        assert chart_id in engine.manifold.charts
        assert len(engine.manifold.all_points) == 1

    def test_solve_integration(self):
        from reasoning_project.reasoning_engine import GridDomainAdapter
        adapter = GridDomainAdapter()
        engine = ManifoldReasoningEngine(adapter)
        pairs = _make_train_pairs()
        test_inputs = [pairs[0][0].copy()]
        # Engine may or may not solve depending on task complexity;
        # we just verify it runs without error
        result = engine.solve(pairs, test_inputs)
        # Either solved or returned None
        assert result is None or len(result) == 2


# ---------------------------------------------------------------------------
# 8. TopologicalConsistencyLoss safety check
# ---------------------------------------------------------------------------

class TestTopologicalConsistencyLoss:
    def test_compute_losses(self):
        old = MemoryManifold(auto_chart_threshold=100.0)
        new = MemoryManifold(auto_chart_threshold=100.0)
        # Same points in both
        for i in range(5):
            emb = np.array([float(i), 0.0])
            old.add_point(_make_point(embedding=emb.copy()))
            new.add_point(_make_point(embedding=emb.copy()))
        loss = TopologicalConsistencyLoss()
        result = loss.compute(old, new)
        assert "task_loss" in result
        assert "topo_loss" in result
        assert "geo_loss" in result
        assert "memory_loss" in result
        assert "total" in result

    def test_safe_update_identical(self):
        old = MemoryManifold(auto_chart_threshold=100.0)
        new = MemoryManifold(auto_chart_threshold=100.0)
        for i in range(5):
            emb = np.array([float(i), 0.0])
            old.add_point(_make_point(embedding=emb.copy()))
            new.add_point(_make_point(embedding=emb.copy()))
        loss = TopologicalConsistencyLoss()
        assert loss.is_safe_update(old, new)

    def test_unsafe_update_radical_change(self):
        old = MemoryManifold(auto_chart_threshold=100.0)
        new = MemoryManifold(auto_chart_threshold=100.0)
        for i in range(5):
            old.add_point(_make_point(embedding=np.array([float(i), 0.0])))
        # New manifold has completely different topology
        for i in range(5):
            new.add_point(_make_point(embedding=np.array([float(i) * 100.0, float(i) * 100.0])))
        loss = TopologicalConsistencyLoss(max_topo_change=0.01)
        assert not loss.is_safe_update(old, new)


# ---------------------------------------------------------------------------
# Additional: TransitionMap and helpers
# ---------------------------------------------------------------------------

class TestTransitionMap:
    def test_fallback_transfer(self):
        c1 = LocalChart("c1", "src", "grid")
        c2 = LocalChart("c2", "dst", "grid")
        c1.add_point(_make_point(embedding=np.array([1.0, 0.0])))
        c2.add_point(_make_point(embedding=np.array([5.0, 0.0])))
        tm = TransitionMap("c1", "c2")
        p = _make_point(embedding=np.array([2.0, 0.0]))
        result = tm.transfer(p, c1, c2)
        assert result.shape == (2,)


class TestHelpers:
    def test_cosine_similarity_identical(self):
        a = np.array([1.0, 2.0, 3.0])
        assert _cosine_similarity(a, a) == pytest.approx(1.0)

    def test_cosine_similarity_orthogonal(self):
        a = np.array([1.0, 0.0])
        b = np.array([0.0, 1.0])
        assert _cosine_similarity(a, b) == pytest.approx(0.0)

    def test_signature_similarity_identical(self):
        sig = {"object_count": 5, "color_count": 3, "has_separators": True}
        assert _signature_similarity(sig, sig) == pytest.approx(1.0)

    def test_signature_to_embedding_shape(self):
        sig = encode_task_signature(_make_train_pairs())
        emb = _signature_to_embedding(sig)
        assert emb.ndim == 1
        assert emb.shape[0] == 16  # 6 numeric + 4 shape + 5 bool + 1 color_transform


# ---------------------------------------------------------------------------
# 11. FIBER BUNDLE
# ---------------------------------------------------------------------------

class TestFiber:
    def test_empty_fiber(self):
        pt = _make_point()
        f = Fiber(pt)
        assert f.dimension == 0
        assert f.actions == []

    def test_add_action(self):
        pt = _make_point()
        f = Fiber(pt)
        action = np.ones(16)
        f.add_action(action)
        assert len(f.actions) == 1
        assert f.dimension == 16


class TestFiberBundle:
    def test_project(self):
        m = MemoryManifold()
        bundle = FiberBundle(m)
        pt = _make_point()
        action = np.zeros(16)
        total = (pt, action)
        assert bundle.project(total) is pt

    def test_fiber_at_creates(self):
        m = MemoryManifold()
        bundle = FiberBundle(m)
        pt = _make_point()
        fiber = bundle.fiber_at(pt)
        assert isinstance(fiber, Fiber)
        assert fiber.base_point is pt

    def test_lift(self):
        m = MemoryManifold()
        bundle = FiberBundle(m)
        pt = _make_point()
        action = np.ones(16)
        total = bundle.lift(pt, action)
        assert total[0] is pt
        np.testing.assert_array_equal(total[1], action)
        assert len(bundle.fiber_at(pt).actions) == 1

    def test_parallel_transport_identity(self):
        m = MemoryManifold()
        bundle = FiberBundle(m)
        pt_a = _make_point(embedding=np.array([1.0, 0.0, 0.0]))
        pt_b = _make_point(embedding=np.array([0.0, 1.0, 0.0]))
        action = np.array([0.5, 0.5, 0.5])
        transported = bundle.parallel_transport(action, pt_a, pt_b)
        np.testing.assert_array_equal(transported, action)

    def test_section(self):
        m = MemoryManifold()
        bundle = FiberBundle(m)
        pts = [_make_point(embedding=np.random.default_rng(i).random(8)) for i in range(3)]
        bundle.lift(pts[0], np.ones(8))
        result = bundle.section(pts)
        assert len(result) == 3
        assert result[0][1] is not None
        assert result[1][1] is None

    def test_curvature_at_empty(self):
        m = MemoryManifold()
        bundle = FiberBundle(m)
        pt = _make_point()
        curv = bundle.curvature_at(pt)
        assert curv == 0.0

    def test_curvature_at_with_points(self):
        m = MemoryManifold()
        bundle = FiberBundle(m)
        rng = np.random.default_rng(42)
        for i in range(5):
            m.add_point(_make_point(embedding=rng.random(8)))
        pt = _make_point(embedding=rng.random(8))
        curv = bundle.curvature_at(pt)
        assert isinstance(curv, float)
        assert curv >= 0.0


# ---------------------------------------------------------------------------
# 12. GEODESIC SOLVER
# ---------------------------------------------------------------------------

class TestReasoningTrajectory:
    def test_empty_trajectory(self):
        t = ReasoningTrajectory()
        assert t.length == 0.0
        assert t.energy == 0.0
        assert not t.converged

    def test_trajectory_length(self):
        t = ReasoningTrajectory()
        t.append(_make_point(embedding=np.array([0.0, 0.0])))
        t.append(_make_point(embedding=np.array([3.0, 4.0])))
        assert t.length == pytest.approx(5.0)

    def test_trajectory_energy(self):
        t = ReasoningTrajectory()
        t.append(_make_point(embedding=np.array([0.0, 0.0])))
        t.append(_make_point(embedding=np.array([1.0, 0.0])))
        assert t.energy == pytest.approx(1.0)


class TestGeodesicSolver:
    def test_solve_empty_manifold(self):
        m = MemoryManifold()
        solver = GeodesicSolver(m, max_steps=5)
        start = _make_point(embedding=np.array([0.0, 0.0, 0.0]))
        traj = solver.solve_geodesic(start)
        assert isinstance(traj, ReasoningTrajectory)
        assert len(traj.points) >= 1

    def test_solve_converges_to_target(self):
        m = MemoryManifold()
        target = _make_point(
            embedding=np.array([1.0, 1.0, 1.0]),
            hypothesis={"rule": "test"},
        )
        target.metadata["solved"] = True
        m.add_point(target)

        solver = GeodesicSolver(m, step_size=0.3, max_steps=50, convergence_threshold=0.1)
        start = _make_point(embedding=np.array([0.0, 0.0, 0.0]))
        traj = solver.solve_geodesic(start)
        assert traj.converged
        final = traj.points[-1].embedding
        dist = float(np.linalg.norm(final - target.embedding))
        assert dist < 0.5

    def test_solve_with_explicit_target(self):
        m = MemoryManifold()
        solver = GeodesicSolver(m, step_size=0.3, max_steps=30, convergence_threshold=0.1)
        start = _make_point(embedding=np.array([0.0, 0.0]))
        target = np.array([1.0, 1.0])
        traj = solver.solve_geodesic(start, target_embedding=target)
        assert len(traj.points) >= 2

    def test_curvature_mismatch_score(self):
        m = MemoryManifold()
        bundle = FiberBundle(m)
        rng = np.random.default_rng(99)
        for i in range(5):
            m.add_point(_make_point(embedding=rng.random(8)))
        solver = GeodesicSolver(m, bundle=bundle)
        pt = _make_point(embedding=rng.random(8))
        score = solver.curvature_mismatch_score(pt)
        assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# 13. MANIFOLD MISMATCH TRIGGER
# ---------------------------------------------------------------------------

class TestManifoldMismatchTrigger:
    def test_trigger_on_empty_manifold(self):
        m = MemoryManifold()
        trigger = ManifoldMismatchTrigger()
        pt = _make_point(embedding=np.array([1.0, 2.0, 3.0]))
        result = trigger.should_create_adapter(pt, m)
        assert result["triggered"] is True
        assert "no_chart_coverage" in result["reason"]

    def test_no_trigger_on_nearby_point(self):
        m = MemoryManifold()
        # Need 2+ points in chart so radius > 0
        m.add_point(_make_point(embedding=np.array([1.0, 1.0, 1.0])))
        m.add_point(_make_point(embedding=np.array([1.1, 1.1, 1.1])))
        trigger = ManifoldMismatchTrigger()
        query = _make_point(embedding=np.array([1.05, 1.05, 1.05]))
        result = trigger.should_create_adapter(query, m)
        assert result["scores"]["coverage_gap"] < 1.5

    def test_trigger_on_distant_point(self):
        m = MemoryManifold()
        m.add_point(_make_point(embedding=np.array([0.0, 0.0, 0.0])))
        m.add_point(_make_point(embedding=np.array([0.1, 0.1, 0.1])))
        trigger = ManifoldMismatchTrigger(coverage_threshold=1.0)
        query = _make_point(embedding=np.array([100.0, 100.0, 100.0]))
        result = trigger.should_create_adapter(query, m)
        assert result["triggered"] is True

    def test_trigger_with_bundle(self):
        m = MemoryManifold()
        bundle = FiberBundle(m)
        rng = np.random.default_rng(42)
        for i in range(5):
            m.add_point(_make_point(embedding=rng.random(4)))
        trigger = ManifoldMismatchTrigger()
        query = _make_point(embedding=rng.random(4))
        result = trigger.should_create_adapter(query, m, bundle=bundle)
        assert "curvature_z" in result["scores"]

    def test_trigger_scores_structure(self):
        m = MemoryManifold()
        trigger = ManifoldMismatchTrigger()
        pt = _make_point()
        result = trigger.should_create_adapter(pt, m)
        assert "triggered" in result
        assert "reason" in result
        assert "scores" in result
        assert "coverage_gap" in result["scores"]
        assert "topology_uncertainty" in result["scores"]
