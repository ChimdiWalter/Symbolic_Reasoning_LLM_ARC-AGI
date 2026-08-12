"""Topological Manifold Memory for adaptive structural reasoning.

Represents reasoning memory as a learned manifold where retrieval is
movement through structured space. Points encode task signatures,
local charts group related reasoning domains, and transition maps
enable cross-domain transfer. Persistent homology detects capability
gaps in the manifold.
"""
from __future__ import annotations

import uuid
import numpy as np
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from reasoning_project.reasoning_engine import (
    DomainAdapter,
    ReasoningMemory,
    StructuralReasoner,
    WorkingMemory,
)


# ═══════════════════════════════════════════════════════════════════════════
# 1. MANIFOLD POINT
# ═══════════════════════════════════════════════════════════════════════════

class ManifoldPoint:
    """A point on the memory manifold representing a reasoning state."""

    def __init__(
        self,
        embedding: np.ndarray,
        task_signature: Dict[str, Any],
        domain: str = "grid",
        hypothesis: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.embedding = np.asarray(embedding, dtype=np.float64)
        self.task_signature = dict(task_signature)
        self.domain = domain
        self.hypothesis = hypothesis
        self.metadata = metadata or {}
        self.id = str(uuid.uuid4())

    def __repr__(self) -> str:
        return f"ManifoldPoint(domain={self.domain!r}, id={self.id[:8]})"


# ═══════════════════════════════════════════════════════════════════════════
# 2. LOCAL CHART
# ═══════════════════════════════════════════════════════════════════════════

class LocalChart:
    """A local coordinate system for a reasoning domain."""

    def __init__(
        self,
        chart_id: str,
        name: str,
        domain_type: str = "grid",
    ):
        self.chart_id = chart_id
        self.name = name
        self.domain_type = domain_type
        self.points: List[ManifoldPoint] = []
        self.center: np.ndarray = np.zeros(0)
        self.radius: float = 0.0

    def _recompute_stats(self) -> None:
        """Recompute center and radius from current points."""
        if not self.points:
            self.center = np.zeros(0)
            self.radius = 0.0
            return
        embeddings = np.array([p.embedding for p in self.points])
        self.center = embeddings.mean(axis=0)
        dists = np.linalg.norm(embeddings - self.center, axis=1)
        self.radius = float(dists.max()) if len(dists) > 0 else 0.0

    def add_point(self, point: ManifoldPoint) -> None:
        """Add a point and recompute chart statistics."""
        self.points.append(point)
        self._recompute_stats()

    def project(self, point: ManifoldPoint) -> np.ndarray:
        """Project a point into local chart coordinates (offset from center)."""
        if self.center.size == 0:
            return point.embedding.copy()
        return point.embedding - self.center

    def distance(self, a: ManifoldPoint, b: ManifoldPoint) -> float:
        """Compute distance between two points using the chart-local metric."""
        local_a = self.project(a)
        local_b = self.project(b)
        return float(np.linalg.norm(local_a - local_b))

    def contains(self, point: ManifoldPoint) -> bool:
        """Check if a point falls within this chart's radius."""
        if self.center.size == 0 or point.embedding.shape != self.center.shape:
            return False
        dist = float(np.linalg.norm(point.embedding - self.center))
        # Use 1.5x radius as soft boundary
        return dist <= self.radius * 1.5 + 1e-9

    def __repr__(self) -> str:
        return f"LocalChart({self.name!r}, {len(self.points)} pts)"


# ═══════════════════════════════════════════════════════════════════════════
# 3. TRANSITION MAP
# ═══════════════════════════════════════════════════════════════════════════

class TransitionMap:
    """Maps between overlapping charts for cross-domain transfer."""

    def __init__(
        self,
        source_chart: str,
        target_chart: str,
        transform: Optional[Callable[[np.ndarray], np.ndarray]] = None,
        overlap_points: Optional[List[ManifoldPoint]] = None,
    ):
        self.source_chart = source_chart
        self.target_chart = target_chart
        self.overlap_points = overlap_points or []
        self._transform = transform
        self._learned_matrix: Optional[np.ndarray] = None

    def _learn_transform(self, source_chart: LocalChart, target_chart: LocalChart) -> None:
        """Learn a linear transform from overlap points projected into both charts."""
        if len(self.overlap_points) < 2:
            return
        source_coords = np.array([source_chart.project(p) for p in self.overlap_points])
        target_coords = np.array([target_chart.project(p) for p in self.overlap_points])
        # Least-squares linear map: target = source @ M
        try:
            self._learned_matrix, _, _, _ = np.linalg.lstsq(
                source_coords, target_coords, rcond=None,
            )
        except np.linalg.LinAlgError:
            self._learned_matrix = None

    def transfer(
        self,
        point: ManifoldPoint,
        from_chart: LocalChart,
        to_chart: LocalChart,
    ) -> np.ndarray:
        """Transform a point from one chart's coordinates to another's."""
        local = from_chart.project(point)
        if self._transform is not None:
            return self._transform(local)
        if self._learned_matrix is not None:
            return local @ self._learned_matrix
        # Fallback: offset-based transfer
        return local + to_chart.center - from_chart.center if to_chart.center.size > 0 else local


# ═══════════════════════════════════════════════════════════════════════════
# 4. MEMORY MANIFOLD
# ═══════════════════════════════════════════════════════════════════════════

class MemoryManifold:
    """The full manifold atlas: charts + transition maps."""

    def __init__(self, auto_chart_threshold: float = 2.0):
        self.charts: Dict[str, LocalChart] = {}
        self.transitions: List[TransitionMap] = []
        self._auto_chart_threshold = auto_chart_threshold

    def add_point(self, point: ManifoldPoint, chart_id: Optional[str] = None) -> str:
        """Add a point to the manifold, auto-assigning to best chart or creating one."""
        if chart_id is not None and chart_id in self.charts:
            self.charts[chart_id].add_point(point)
            return chart_id

        # Find best existing chart
        best_chart_id = self._find_best_chart(point)
        if best_chart_id is not None:
            self.charts[best_chart_id].add_point(point)
            return best_chart_id

        # Create new chart
        new_id = f"chart_{len(self.charts)}_{point.domain}"
        chart = LocalChart(
            chart_id=new_id,
            name=f"auto_{point.domain}_{len(self.charts)}",
            domain_type=point.domain,
        )
        chart.add_point(point)
        self.charts[new_id] = chart
        return new_id

    def _find_best_chart(self, point: ManifoldPoint) -> Optional[str]:
        """Find the chart whose center is closest to this point within threshold."""
        best_id = None
        best_dist = float("inf")
        for cid, chart in self.charts.items():
            if chart.center.size == 0 or chart.center.shape != point.embedding.shape:
                continue
            dist = float(np.linalg.norm(point.embedding - chart.center))
            if dist < best_dist:
                best_dist = dist
                best_id = cid
        if best_id is not None and best_dist <= self._auto_chart_threshold:
            return best_id
        return None

    def retrieve_topological(
        self, query_point: ManifoldPoint, k: int = 5,
    ) -> List[ManifoldPoint]:
        """Retrieve structurally relevant memories using task_signature similarity."""
        all_points = []
        for chart in self.charts.values():
            all_points.extend(chart.points)
        if not all_points:
            return []

        scored = []
        for p in all_points:
            sig_sim = _signature_similarity(query_point.task_signature, p.task_signature)
            emb_sim = _cosine_similarity(query_point.embedding, p.embedding)
            combined = sig_sim * 0.6 + emb_sim * 0.4
            scored.append((combined, p))
        scored.sort(key=lambda x: -x[0])
        return [p for _, p in scored[:k]]

    def detect_gaps(self, n_bins: int = 10) -> List[Dict[str, Any]]:
        """Find regions of the manifold with low point density (capability gaps)."""
        all_embeddings = []
        for chart in self.charts.values():
            for p in chart.points:
                all_embeddings.append(p.embedding)
        if len(all_embeddings) < 3:
            return []

        embeddings = np.array(all_embeddings)
        # Build pairwise distance matrix
        n = len(embeddings)
        dists = np.zeros((n, n))
        for i in range(n):
            for j in range(i + 1, n):
                d = np.linalg.norm(embeddings[i] - embeddings[j])
                dists[i, j] = d
                dists[j, i] = d

        # Find sparse regions: points whose k-nearest neighbor is far
        k_nn = min(3, n - 1)
        gaps = []
        for i in range(n):
            sorted_dists = np.sort(dists[i])
            knn_dist = sorted_dists[k_nn] if k_nn < n else sorted_dists[-1]
            gaps.append({
                "point_index": i,
                "knn_distance": float(knn_dist),
                "embedding": embeddings[i],
            })

        # Return only points in the sparsest quarter
        gaps.sort(key=lambda g: -g["knn_distance"])
        n_gaps = max(1, n // 4)
        return gaps[:n_gaps]

    def geodesic_distance(self, a: ManifoldPoint, b: ManifoldPoint) -> float:
        """Approximate shortest path through the manifold via chart hops."""
        # Direct distance as starting estimate
        direct = float(np.linalg.norm(a.embedding - b.embedding))

        all_points = []
        for chart in self.charts.values():
            all_points.extend(chart.points)
        if len(all_points) < 2:
            return direct

        # Build graph: each point connected to its k nearest neighbors
        embeddings = np.array([p.embedding for p in all_points])
        # Add query points
        all_emb = np.vstack([a.embedding.reshape(1, -1), b.embedding.reshape(1, -1), embeddings])
        n = len(all_emb)

        # Pairwise distance matrix
        dist_matrix = np.full((n, n), np.inf)
        for i in range(n):
            dist_matrix[i, i] = 0.0
        k_conn = min(5, n - 1)
        for i in range(n):
            dists_i = np.linalg.norm(all_emb - all_emb[i], axis=1)
            neighbors = np.argsort(dists_i)[1:k_conn + 1]
            for j in neighbors:
                d = dists_i[j]
                dist_matrix[i, j] = d
                dist_matrix[j, i] = d

        # Floyd-Warshall for shortest paths
        for k_node in range(n):
            for i in range(n):
                for j in range(n):
                    if dist_matrix[i, k_node] + dist_matrix[k_node, j] < dist_matrix[i, j]:
                        dist_matrix[i, j] = dist_matrix[i, k_node] + dist_matrix[k_node, j]

        geo = dist_matrix[0, 1]
        return float(min(direct, geo))

    def get_active_charts(self, query: ManifoldPoint) -> List[str]:
        """Return chart IDs relevant for this query (by containment or proximity)."""
        active = []
        for cid, chart in self.charts.items():
            if chart.center.size == 0 or chart.center.shape != query.embedding.shape:
                continue
            if chart.contains(query):
                active.append(cid)
        # If none contain it, return the closest chart
        if not active and self.charts:
            best_id = self._find_best_chart(query)
            if best_id is not None:
                active.append(best_id)
        return active

    @property
    def all_points(self) -> List[ManifoldPoint]:
        """Return all points across all charts."""
        pts = []
        for chart in self.charts.values():
            pts.extend(chart.points)
        return pts


# ═══════════════════════════════════════════════════════════════════════════
# 5. WORKING MEMORY MANIFOLD
# ═══════════════════════════════════════════════════════════════════════════

class WorkingMemoryManifold:
    """Per-task dynamic workspace on the manifold."""

    def __init__(self, manifold: MemoryManifold):
        self.manifold = manifold
        self.active_charts: Set[str] = set()
        self.trajectory: List[ManifoldPoint] = []
        self._converged = False

    def activate(self, query_point: ManifoldPoint) -> Set[str]:
        """Select relevant charts based on task signature and proximity."""
        chart_ids = self.manifold.get_active_charts(query_point)
        self.active_charts = set(chart_ids)
        if not self.trajectory:
            self.trajectory.append(query_point)
        return self.active_charts

    def step(
        self,
        current_state: ManifoldPoint,
        action: np.ndarray,
        retrieved_memory: Optional[ManifoldPoint] = None,
    ) -> ManifoldPoint:
        """Compute next state z_{t+1} = F(z_t, a_t, m_t)."""
        z = current_state.embedding + action
        if retrieved_memory is not None:
            # Blend with retrieved memory (weighted average)
            z = 0.7 * z + 0.3 * retrieved_memory.embedding
        new_point = ManifoldPoint(
            embedding=z,
            task_signature=current_state.task_signature.copy(),
            domain=current_state.domain,
            hypothesis=current_state.hypothesis,
            metadata={"step": len(self.trajectory)},
        )
        self.trajectory.append(new_point)
        return new_point

    def is_in_solution_region(self, state: ManifoldPoint, threshold: float = 0.3) -> bool:
        """Check if trajectory has converged to a solution region."""
        if len(self.trajectory) < 2:
            return False
        # Converged if last step moved very little
        prev = self.trajectory[-2] if len(self.trajectory) >= 2 else self.trajectory[-1]
        delta = float(np.linalg.norm(state.embedding - prev.embedding))
        if delta < threshold:
            self._converged = True
        return self._converged


# ═══════════════════════════════════════════════════════════════════════════
# 6. TOPOLOGICAL RETRIEVER
# ═══════════════════════════════════════════════════════════════════════════

class TopologicalRetriever:
    """Retrieval that respects manifold structure and task signatures."""

    SIG_WEIGHT = 0.6
    EMB_WEIGHT = 0.4

    SIGNATURE_KEYS = [
        "object_count", "color_count", "has_separators", "size_changing",
        "has_symmetry", "has_containment", "has_holes",
    ]

    def retrieve(
        self,
        query: ManifoldPoint,
        manifold: MemoryManifold,
        k: int = 5,
    ) -> List[ManifoldPoint]:
        """Retrieve points close in structural similarity, not just embedding distance."""
        all_points = manifold.all_points
        if not all_points:
            return []

        scored = []
        for p in all_points:
            sig_sim = _signature_similarity(query.task_signature, p.task_signature)
            emb_sim = _cosine_similarity(query.embedding, p.embedding)
            score = self.SIG_WEIGHT * sig_sim + self.EMB_WEIGHT * emb_sim
            scored.append((score, p))
        scored.sort(key=lambda x: -x[0])
        return [p for _, p in scored[:k]]


# ═══════════════════════════════════════════════════════════════════════════
# 7. PERSISTENT HOMOLOGY DETECTOR
# ═══════════════════════════════════════════════════════════════════════════

class _UnionFind:
    """Union-Find data structure for persistent homology computation."""

    def __init__(self, n: int):
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, x: int, y: int) -> bool:
        """Union two sets, return True if they were disjoint."""
        rx, ry = self.find(x), self.find(y)
        if rx == ry:
            return False
        if self.rank[rx] < self.rank[ry]:
            rx, ry = ry, rx
        self.parent[ry] = rx
        if self.rank[rx] == self.rank[ry]:
            self.rank[rx] += 1
        return True


class PersistentHomologyDetector:
    """Simplified persistent homology for gap detection via Vietoris-Rips."""

    def compute_persistence(
        self, points: List[np.ndarray],
    ) -> Dict[str, List[Tuple[float, float]]]:
        """Compute H0 (connected components) and H1 (loops) persistence pairs."""
        if len(points) < 2:
            return {"H0": [], "H1": []}

        embeddings = np.array(points)
        n = len(embeddings)

        # Build pairwise distance matrix
        dist_matrix = np.zeros((n, n))
        edges = []
        for i in range(n):
            for j in range(i + 1, n):
                d = float(np.linalg.norm(embeddings[i] - embeddings[j]))
                dist_matrix[i, j] = d
                dist_matrix[j, i] = d
                edges.append((d, i, j))
        edges.sort()

        # H0: track component merges using union-find (Kruskal-like)
        uf = _UnionFind(n)
        birth_time = [0.0] * n  # each point born at 0
        h0_pairs: List[Tuple[float, float]] = []

        for d, i, j in edges:
            ri, rj = uf.find(i), uf.find(j)
            if ri != rj:
                # Component with later birth dies
                if birth_time[ri] >= birth_time[rj]:
                    dying_root = ri
                else:
                    dying_root = rj
                h0_pairs.append((birth_time[dying_root], d))
                uf.union(i, j)

        # H1: simplified loop detection via triangle check
        h1_pairs: List[Tuple[float, float]] = []
        if n >= 3:
            # Sort edges by length, look for cycle-completing edges
            adj: Dict[int, Set[int]] = {i: set() for i in range(n)}
            for d, i, j in edges:
                # Check if i and j are already connected via short path
                # Simple: check if they share a neighbor
                common = adj[i] & adj[j]
                if common:
                    # Cycle detected — the birth is the max of the two
                    # existing edges, death is this edge's distance
                    for c in common:
                        birth = max(dist_matrix[i, c], dist_matrix[j, c])
                        death = d
                        if death > birth:
                            h1_pairs.append((birth, death))
                            break
                adj[i].add(j)
                adj[j].add(i)

        return {"H0": h0_pairs, "H1": h1_pairs}

    def find_gaps(self, manifold: MemoryManifold) -> List[Dict[str, Any]]:
        """Find sparse regions in the manifold where reasoning capability is low."""
        all_points = manifold.all_points
        if len(all_points) < 3:
            return []

        embeddings = [p.embedding for p in all_points]
        persistence = self.compute_persistence(embeddings)

        # Long-lived H0 components indicate disconnected regions
        gaps = []
        for birth, death in persistence["H0"]:
            lifetime = death - birth
            if lifetime > 0:
                gaps.append({
                    "type": "disconnected_region",
                    "birth": birth,
                    "death": death,
                    "lifetime": lifetime,
                })

        # Long-lived H1 features indicate holes in coverage
        for birth, death in persistence["H1"]:
            lifetime = death - birth
            if lifetime > 0:
                gaps.append({
                    "type": "coverage_hole",
                    "birth": birth,
                    "death": death,
                    "lifetime": lifetime,
                })

        gaps.sort(key=lambda g: -g["lifetime"])
        return gaps

    def uncertainty_score(self, query: ManifoldPoint, manifold: MemoryManifold) -> float:
        """High score if query is in a gap region (far from known points)."""
        all_points = manifold.all_points
        if not all_points:
            return 1.0

        dists = [
            float(np.linalg.norm(query.embedding - p.embedding))
            for p in all_points
        ]
        min_dist = min(dists)
        mean_dist = float(np.mean(dists))
        # Normalize: high if minimum distance is large relative to mean
        if mean_dist < 1e-12:
            return 0.0
        return float(np.clip(min_dist / mean_dist, 0.0, 1.0))


# ═══════════════════════════════════════════════════════════════════════════
# 8. MANIFOLD REASONING ENGINE
# ═══════════════════════════════════════════════════════════════════════════

class ManifoldReasoningEngine:
    """Wraps StructuralReasoner with manifold-based memory."""

    def __init__(
        self,
        adapter: DomainAdapter,
        manifold: Optional[MemoryManifold] = None,
        memory: Optional[ReasoningMemory] = None,
    ):
        self.adapter = adapter
        self.manifold = manifold or MemoryManifold()
        self.memory = memory or ReasoningMemory()
        self.reasoner = StructuralReasoner(adapter, memory=self.memory)
        self.retriever = TopologicalRetriever()
        self.homology = PersistentHomologyDetector()

    def solve(
        self,
        train_pairs: List[Tuple[Any, Any]],
        test_inputs: List[Any],
        domain_adapter: Optional[DomainAdapter] = None,
    ) -> Optional[Tuple[List[Any], Dict[str, Any]]]:
        """Solve with manifold-guided memory retrieval and trajectory tracking."""
        adapter = domain_adapter or self.adapter

        # 1. Encode task as initial manifold point
        z0 = self.encode_task(train_pairs)

        # 2. Activate relevant charts (working memory)
        wm = WorkingMemoryManifold(self.manifold)
        wm.activate(z0)

        # 3. Retrieve structurally similar past solutions
        retrieved = self.retriever.retrieve(z0, self.manifold, k=5)

        # 4. Run StructuralReasoner (or domain-appropriate solver)
        reasoner = StructuralReasoner(adapter, memory=self.memory)
        result = reasoner.solve(train_pairs, test_inputs)

        # 5. Record trajectory and update manifold
        meta = {}
        if result is not None:
            predictions, hypothesis = result
            meta = dict(hypothesis)
            meta["manifold_active_charts"] = list(wm.active_charts)
            meta["manifold_retrieved_count"] = len(retrieved)
            meta["uncertainty"] = self.homology.uncertainty_score(z0, self.manifold)
            self.update_manifold(train_pairs, hypothesis)
            return predictions, meta

        # Record even failed attempts for gap detection
        self.manifold.add_point(ManifoldPoint(
            embedding=z0.embedding,
            task_signature=z0.task_signature,
            domain=z0.domain,
            hypothesis=None,
            metadata={"solved": False},
        ))
        return None

    def encode_task(self, train_pairs: List[Tuple[Any, Any]]) -> ManifoldPoint:
        """Encode a task as a ManifoldPoint from structural features."""
        sig = encode_task_signature(train_pairs)
        embedding = _signature_to_embedding(sig)
        return ManifoldPoint(
            embedding=embedding,
            task_signature=sig,
            domain="grid",
            hypothesis=None,
            metadata={"n_train": len(train_pairs)},
        )

    def update_manifold(
        self, train_pairs: List[Tuple[Any, Any]], hypothesis: Dict[str, Any],
    ) -> str:
        """Add a new point (and potentially create a new chart) after solving."""
        sig = encode_task_signature(train_pairs)
        embedding = _signature_to_embedding(sig)
        point = ManifoldPoint(
            embedding=embedding,
            task_signature=sig,
            domain="grid",
            hypothesis=hypothesis,
            metadata={"solved": True},
        )
        return self.manifold.add_point(point)


# ═══════════════════════════════════════════════════════════════════════════
# 9. TOPOLOGICAL CONSISTENCY LOSS
# ═══════════════════════════════════════════════════════════════════════════

class TopologicalConsistencyLoss:
    """Validates that memory updates preserve manifold topology."""

    def __init__(self, max_topo_change: float = 0.5):
        self._max_topo_change = max_topo_change
        self._homology = PersistentHomologyDetector()

    def compute(
        self, old_manifold: MemoryManifold, new_manifold: MemoryManifold,
    ) -> Dict[str, float]:
        """Measure topology change between old and new manifold states."""
        task_loss = self._task_loss(old_manifold, new_manifold)
        topo_loss = self._topo_loss(old_manifold, new_manifold)
        geo_loss = self._geo_loss(old_manifold, new_manifold)
        memory_loss = self._memory_loss(old_manifold, new_manifold)
        total = task_loss + topo_loss + geo_loss + memory_loss
        return {
            "task_loss": task_loss,
            "topo_loss": topo_loss,
            "geo_loss": geo_loss,
            "memory_loss": memory_loss,
            "total": total,
        }

    def _task_loss(self, old: MemoryManifold, new: MemoryManifold) -> float:
        """Measure change in task coverage."""
        old_n = len(old.all_points)
        new_n = len(new.all_points)
        if old_n == 0:
            return 0.0
        return abs(new_n - old_n) / max(old_n, 1.0) * 0.1

    def _topo_loss(self, old: MemoryManifold, new: MemoryManifold) -> float:
        """Persistence diagram distance between old and new."""
        old_emb = [p.embedding for p in old.all_points]
        new_emb = [p.embedding for p in new.all_points]
        if len(old_emb) < 2 or len(new_emb) < 2:
            return 0.0
        old_pers = self._homology.compute_persistence(old_emb)
        new_pers = self._homology.compute_persistence(new_emb)
        # Bottleneck-like distance: compare H0 lifetimes
        old_lifetimes = sorted([d - b for b, d in old_pers["H0"]], reverse=True)
        new_lifetimes = sorted([d - b for b, d in new_pers["H0"]], reverse=True)
        max_len = max(len(old_lifetimes), len(new_lifetimes))
        if max_len == 0:
            return 0.0
        # Pad with zeros
        old_lifetimes.extend([0.0] * (max_len - len(old_lifetimes)))
        new_lifetimes.extend([0.0] * (max_len - len(new_lifetimes)))
        return float(max(abs(a - b) for a, b in zip(old_lifetimes, new_lifetimes)))

    def _geo_loss(self, old: MemoryManifold, new: MemoryManifold) -> float:
        """Measure geodesic distance preservation for shared points."""
        # Compare chart center positions
        old_centers = []
        new_centers = []
        for cid in old.charts:
            if cid in new.charts:
                oc = old.charts[cid].center
                nc = new.charts[cid].center
                if oc.size > 0 and nc.size > 0 and oc.shape == nc.shape:
                    old_centers.append(oc)
                    new_centers.append(nc)
        if not old_centers:
            return 0.0
        shifts = [float(np.linalg.norm(o - n)) for o, n in zip(old_centers, new_centers)]
        return float(np.mean(shifts))

    def _memory_loss(self, old: MemoryManifold, new: MemoryManifold) -> float:
        """Measure chart structure preservation (number of charts change)."""
        old_n = len(old.charts)
        new_n = len(new.charts)
        if old_n == 0:
            return 0.0
        return abs(new_n - old_n) / max(old_n, 1.0) * 0.2

    def is_safe_update(
        self, old: MemoryManifold, new: MemoryManifold,
    ) -> bool:
        """True if topology is preserved within acceptable bounds."""
        losses = self.compute(old, new)
        return losses["topo_loss"] <= self._max_topo_change


# ═══════════════════════════════════════════════════════════════════════════
# 10. TASK SIGNATURE ENCODING
# ═══════════════════════════════════════════════════════════════════════════

def encode_task_signature(
    train_pairs: List[Tuple[Any, Any]],
) -> Dict[str, Any]:
    """Extract structural features from train pairs for manifold embedding."""
    sig: Dict[str, Any] = {}

    if not train_pairs:
        return sig

    inp0, out0 = train_pairs[0]
    inp_arr = np.asarray(inp0)
    out_arr = np.asarray(out0)

    # Shapes
    sig["input_shape"] = list(inp_arr.shape)
    sig["output_shape"] = list(out_arr.shape)
    sig["size_changing"] = inp_arr.shape != out_arr.shape

    # Colors
    in_colors = set(int(v) for v in np.unique(inp_arr))
    out_colors = set(int(v) for v in np.unique(out_arr))
    sig["n_colors_in"] = len(in_colors)
    sig["n_colors_out"] = len(out_colors)

    # Objects via connected components (non-background)
    sig["n_objects"] = _count_objects(inp_arr)

    # Separators
    sig["has_separators"] = _has_separators(inp_arr)

    # Symmetry
    sig["has_symmetry"] = _has_symmetry(inp_arr)

    # Containment
    sig["has_containment"] = _has_containment(inp_arr)

    # Holes
    sig["has_holes"] = _has_holes(inp_arr)

    # Color transform type
    sig["color_transform"] = _classify_color_transform(in_colors, out_colors)

    # Object count change across pairs
    obj_counts_in = []
    obj_counts_out = []
    for inp, out in train_pairs:
        obj_counts_in.append(_count_objects(np.asarray(inp)))
        obj_counts_out.append(_count_objects(np.asarray(out)))
    mean_in = np.mean(obj_counts_in) if obj_counts_in else 0
    mean_out = np.mean(obj_counts_out) if obj_counts_out else 0
    sig["object_count_change"] = float(mean_out - mean_in)

    # Aggregate over all pairs
    sig["object_count"] = float(np.mean(obj_counts_in)) if obj_counts_in else 0.0
    sig["color_count"] = sig["n_colors_in"]

    return sig


def _count_objects(grid: np.ndarray, background: int = 0) -> int:
    """Count connected components of non-background cells."""
    if grid.ndim < 2:
        return 0
    mask = grid != background
    if not mask.any():
        return 0
    from scipy import ndimage as _ndi
    labeled, n = _ndi.label(mask)
    return int(n)


def _has_separators(grid: np.ndarray) -> bool:
    """Check if any full row or column is a single non-background color."""
    if grid.ndim < 2:
        return False
    rows, cols = grid.shape
    for r in range(rows):
        row = grid[r, :]
        unique = np.unique(row)
        if len(unique) == 1 and unique[0] != 0:
            return True
    for c in range(cols):
        col = grid[:, c]
        unique = np.unique(col)
        if len(unique) == 1 and unique[0] != 0:
            return True
    return False


def _has_symmetry(grid: np.ndarray) -> bool:
    """Check horizontal, vertical, or diagonal symmetry."""
    if grid.ndim < 2:
        return False
    # Horizontal
    if np.array_equal(grid, grid[::-1, :]):
        return True
    # Vertical
    if np.array_equal(grid, grid[:, ::-1]):
        return True
    # Diagonal (only for square)
    if grid.shape[0] == grid.shape[1]:
        if np.array_equal(grid, grid.T):
            return True
    return False


def _has_containment(grid: np.ndarray, background: int = 0) -> bool:
    """Check if any object fully contains another (simple bounding-box check)."""
    if grid.ndim < 2:
        return False
    from scipy import ndimage as _ndi
    mask = grid != background
    if not mask.any():
        return False
    labeled, n = _ndi.label(mask)
    if n < 2:
        return False

    bboxes = []
    for i in range(1, n + 1):
        positions = np.argwhere(labeled == i)
        r_min, c_min = positions.min(axis=0)
        r_max, c_max = positions.max(axis=0)
        bboxes.append((r_min, c_min, r_max, c_max))

    for i, (r1, c1, r2, c2) in enumerate(bboxes):
        for j, (r3, c3, r4, c4) in enumerate(bboxes):
            if i == j:
                continue
            # Check if bbox j is fully inside bbox i
            if r1 < r3 and c1 < c3 and r2 > r4 and c2 > c4:
                return True
    return False


def _has_holes(grid: np.ndarray, background: int = 0) -> bool:
    """Check if any object is hollow (has background pixels enclosed by object)."""
    if grid.ndim < 2:
        return False
    from scipy import ndimage as _ndi
    mask = grid != background
    if not mask.any():
        return False
    # Fill holes and compare
    filled = _ndi.binary_fill_holes(mask)
    return bool(np.any(filled != mask))


def _classify_color_transform(in_colors: set, out_colors: set) -> str:
    """Classify the color relationship between input and output."""
    if in_colors == out_colors:
        return "same"
    if len(out_colors) < len(in_colors) and out_colors.issubset(in_colors):
        return "reduced"
    if len(out_colors) > len(in_colors) and in_colors.issubset(out_colors):
        return "expanded"
    return "permuted"


# ═══════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two vectors, clipped to [0, 1]."""
    a = a.flatten()
    b = b.flatten()
    if a.shape != b.shape:
        # Pad shorter to match
        max_len = max(len(a), len(b))
        a = np.pad(a, (0, max_len - len(a)))
        b = np.pad(b, (0, max_len - len(b)))
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na < 1e-12 or nb < 1e-12:
        return 0.0
    return float(np.clip(np.dot(a, b) / (na * nb), 0.0, 1.0))


def _signature_similarity(a: Dict[str, Any], b: Dict[str, Any]) -> float:
    """Compute structural similarity between two task signatures."""
    keys = [
        "object_count", "color_count", "has_separators", "size_changing",
        "has_symmetry", "has_containment", "has_holes", "n_colors_in",
        "n_colors_out", "n_objects", "object_count_change",
    ]
    matches = 0
    total = 0
    for k in keys:
        va = a.get(k)
        vb = b.get(k)
        if va is None and vb is None:
            continue
        total += 1
        if va is None or vb is None:
            continue
        if isinstance(va, bool) and isinstance(vb, bool):
            if va == vb:
                matches += 1
        elif isinstance(va, (int, float)) and isinstance(vb, (int, float)):
            denom = max(abs(va), abs(vb), 1.0)
            if abs(va - vb) / denom < 0.3:
                matches += 1
        elif va == vb:
            matches += 1

    if total == 0:
        return 0.0
    return matches / total


def _signature_to_embedding(sig: Dict[str, Any]) -> np.ndarray:
    """Convert a task signature dict to a fixed-length feature vector."""
    features = []

    # Numeric features (normalized)
    features.append(float(sig.get("n_colors_in", 0)) / 10.0)
    features.append(float(sig.get("n_colors_out", 0)) / 10.0)
    features.append(float(sig.get("n_objects", 0)) / 20.0)
    features.append(float(sig.get("object_count", 0)) / 20.0)
    features.append(float(sig.get("color_count", 0)) / 10.0)
    features.append(float(sig.get("object_count_change", 0)) / 10.0)

    # Shape features
    in_shape = sig.get("input_shape", [0, 0])
    out_shape = sig.get("output_shape", [0, 0])
    features.append(float(in_shape[0]) / 30.0 if len(in_shape) > 0 else 0.0)
    features.append(float(in_shape[1]) / 30.0 if len(in_shape) > 1 else 0.0)
    features.append(float(out_shape[0]) / 30.0 if len(out_shape) > 0 else 0.0)
    features.append(float(out_shape[1]) / 30.0 if len(out_shape) > 1 else 0.0)

    # Boolean features
    features.append(1.0 if sig.get("size_changing", False) else 0.0)
    features.append(1.0 if sig.get("has_separators", False) else 0.0)
    features.append(1.0 if sig.get("has_symmetry", False) else 0.0)
    features.append(1.0 if sig.get("has_containment", False) else 0.0)
    features.append(1.0 if sig.get("has_holes", False) else 0.0)

    # Color transform encoding
    ct = sig.get("color_transform", "same")
    ct_map = {"same": 0.0, "reduced": 0.25, "expanded": 0.5, "permuted": 0.75}
    features.append(ct_map.get(ct, 0.0))

    return np.array(features, dtype=np.float64)


# ═══════════════════════════════════════════════════════════════════════════
# 11. FIBER BUNDLE FRAMING
# ═══════════════════════════════════════════════════════════════════════════

class Fiber:
    """A fiber F_b over a base point b — the task-specific action/hypothesis space."""

    def __init__(self, base_point: ManifoldPoint, actions: Optional[List[np.ndarray]] = None):
        self.base_point = base_point
        self.actions = actions or []

    def add_action(self, action: np.ndarray) -> None:
        self.actions.append(np.asarray(action, dtype=np.float64))

    @property
    def dimension(self) -> int:
        return self.actions[0].shape[0] if self.actions else 0


class FiberBundle:
    """Fiber bundle E = (E, B, π, F) over the memory manifold.

    Formalizes reasoning as movement through a total space E where:
    - B (base space) = MemoryManifold of task signatures
    - F_b (fiber at b) = hypothesis/action space for task b
    - π: E → B = projection from (task, hypothesis) to task signature
    - Structure group G acts on fibers via gauge transforms (chart transitions)

    A reasoning trajectory γ: [0,1] → E decomposes into:
    - Base path π∘γ: [0,1] → B (task-space navigation)
    - Fiber lift: vertical displacement in F (hypothesis refinement)
    """

    def __init__(self, base_manifold: MemoryManifold):
        self.base = base_manifold
        self._fibers: Dict[str, Fiber] = {}
        self._local_trivializations: Dict[str, Callable] = {}

    def project(self, total_point: Tuple[ManifoldPoint, np.ndarray]) -> ManifoldPoint:
        """π: E → B — project from total space to base."""
        return total_point[0]

    def fiber_at(self, base_point: ManifoldPoint) -> Fiber:
        """Return (or create) the fiber over a base point."""
        pid = base_point.id
        if pid not in self._fibers:
            self._fibers[pid] = Fiber(base_point)
        return self._fibers[pid]

    def lift(
        self, base_point: ManifoldPoint, action: np.ndarray,
    ) -> Tuple[ManifoldPoint, np.ndarray]:
        """Horizontal lift: given base point and action, produce total-space point."""
        fiber = self.fiber_at(base_point)
        fiber.add_action(action)
        return (base_point, action)

    def parallel_transport(
        self,
        action: np.ndarray,
        from_point: ManifoldPoint,
        to_point: ManifoldPoint,
    ) -> np.ndarray:
        """Transport an action vector along the base manifold.

        Uses the connection (transition maps) to move hypotheses
        between chart neighborhoods.
        """
        for tm in self.base.transitions:
            src_chart = self.base.charts.get(tm.source_chart)
            tgt_chart = self.base.charts.get(tm.target_chart)
            if src_chart is None or tgt_chart is None:
                continue
            if src_chart.contains(from_point) and tgt_chart.contains(to_point):
                return tm.transfer(
                    ManifoldPoint(embedding=action, task_signature={}, domain="action"),
                    src_chart, tgt_chart,
                )
        # Fallback: identity transport
        return action.copy()

    def section(
        self, base_points: List[ManifoldPoint],
    ) -> List[Tuple[ManifoldPoint, Optional[np.ndarray]]]:
        """A global section s: B → E — assign best known action to each base point."""
        result = []
        for bp in base_points:
            fiber = self._fibers.get(bp.id)
            if fiber and fiber.actions:
                result.append((bp, fiber.actions[-1]))
            else:
                result.append((bp, None))
        return result

    def curvature_at(self, point: ManifoldPoint, epsilon: float = 0.1) -> float:
        """Estimate local curvature via holonomy defect.

        Parallel-transports a test vector around a small loop and
        measures the deviation from identity — nonzero implies curvature.
        """
        test_action = np.ones_like(point.embedding) * epsilon
        neighbors = self.base.retrieve_topological(point, k=3)
        if len(neighbors) < 2:
            return 0.0

        transported = test_action.copy()
        path = [point] + neighbors[:2] + [point]
        for i in range(len(path) - 1):
            transported = self.parallel_transport(transported, path[i], path[i + 1])

        holonomy_defect = float(np.linalg.norm(transported - test_action))
        return holonomy_defect


# ═══════════════════════════════════════════════════════════════════════════
# 12. GEODESIC REASONING SOLVER
# ═══════════════════════════════════════════════════════════════════════════

class ReasoningTrajectory:
    """A trajectory γ: [0,T] → M_mem representing a reasoning process.

    Formal statement: reasoning over a task is a path γ through the memory
    manifold M_mem from initial embedding z_0 to a solution region S ⊂ M_mem.
    The optimal reasoning process corresponds to the geodesic (shortest path)
    from z_0 to S, minimizing the energy functional:

        E(γ) = ∫₀ᵀ ‖γ'(t)‖² dt + λ·V(γ(t))

    where V(γ(t)) is a potential penalizing deviation from known-solution regions.
    """

    def __init__(self):
        self.points: List[ManifoldPoint] = []
        self.energies: List[float] = []
        self._converged = False

    @property
    def length(self) -> float:
        """Arc length of the trajectory."""
        if len(self.points) < 2:
            return 0.0
        total = 0.0
        for i in range(1, len(self.points)):
            total += float(np.linalg.norm(
                self.points[i].embedding - self.points[i - 1].embedding
            ))
        return total

    @property
    def energy(self) -> float:
        """Kinetic energy ∫‖γ'‖² (discrete approximation)."""
        if len(self.points) < 2:
            return 0.0
        total = 0.0
        for i in range(1, len(self.points)):
            delta = self.points[i].embedding - self.points[i - 1].embedding
            total += float(np.dot(delta, delta))
        return total

    def append(self, point: ManifoldPoint, step_energy: float = 0.0) -> None:
        self.points.append(point)
        self.energies.append(step_energy)

    @property
    def converged(self) -> bool:
        return self._converged


class GeodesicSolver:
    """Frames task solving as finding the geodesic from z_0 to solution region S.

    Given:
    - z_0: initial task embedding on M_mem
    - S ⊂ M_mem: solution region (neighborhood of known successful solves)
    - Potential V: penalty for leaving known-competence regions

    Finds γ* = argmin_γ E(γ) subject to γ(0)=z_0, γ(T)∈S via gradient flow:
        z_{t+1} = z_t - η·∇E(z_t) + memory_retrieval_correction
    """

    def __init__(
        self,
        manifold: MemoryManifold,
        bundle: Optional[FiberBundle] = None,
        potential_weight: float = 0.3,
        step_size: float = 0.1,
        max_steps: int = 20,
        convergence_threshold: float = 0.05,
    ):
        self.manifold = manifold
        self.bundle = bundle or FiberBundle(manifold)
        self.potential_weight = potential_weight
        self.step_size = step_size
        self.max_steps = max_steps
        self.convergence_threshold = convergence_threshold
        self._retriever = TopologicalRetriever()
        self._homology = PersistentHomologyDetector()

    def _potential(self, point: ManifoldPoint) -> float:
        """V(z): high in sparse/unknown regions, low near known solutions."""
        return self._homology.uncertainty_score(point, self.manifold)

    def _gradient(self, point: ManifoldPoint, target: np.ndarray) -> np.ndarray:
        """Compute ∇E = kinetic gradient + potential gradient."""
        kinetic_grad = point.embedding - target
        norm = np.linalg.norm(kinetic_grad)
        if norm > 1e-12:
            kinetic_grad = kinetic_grad / norm

        # Potential gradient: move toward nearest known solution
        neighbors = self._retriever.retrieve(point, self.manifold, k=3)
        if neighbors:
            nearest = neighbors[0]
            potential_grad = point.embedding - nearest.embedding
            pnorm = np.linalg.norm(potential_grad)
            if pnorm > 1e-12:
                potential_grad = potential_grad / pnorm
        else:
            potential_grad = np.zeros_like(point.embedding)

        return kinetic_grad + self.potential_weight * potential_grad

    def solve_geodesic(
        self,
        start: ManifoldPoint,
        target_embedding: Optional[np.ndarray] = None,
    ) -> ReasoningTrajectory:
        """Find the geodesic path from start to solution region.

        If target_embedding is None, uses the nearest known-successful point
        as the target.
        """
        trajectory = ReasoningTrajectory()
        trajectory.append(start, 0.0)

        if target_embedding is None:
            solved_points = [
                p for p in self.manifold.all_points
                if p.metadata.get("solved", False)
            ]
            if solved_points:
                dists = [
                    float(np.linalg.norm(start.embedding - p.embedding))
                    for p in solved_points
                ]
                target_embedding = solved_points[int(np.argmin(dists))].embedding
            else:
                target_embedding = start.embedding.copy()

        current = start
        for step in range(self.max_steps):
            grad = self._gradient(current, target_embedding)
            new_embedding = current.embedding - self.step_size * grad

            retrieved = self._retriever.retrieve(current, self.manifold, k=1)
            if retrieved:
                memory_correction = 0.1 * (retrieved[0].embedding - new_embedding)
                new_embedding = new_embedding + memory_correction

            new_point = ManifoldPoint(
                embedding=new_embedding,
                task_signature=current.task_signature.copy(),
                domain=current.domain,
                hypothesis=current.hypothesis,
                metadata={"step": step + 1},
            )

            step_energy = float(np.dot(
                new_embedding - current.embedding,
                new_embedding - current.embedding,
            )) + self.potential_weight * self._potential(new_point)
            trajectory.append(new_point, step_energy)

            dist_to_target = float(np.linalg.norm(new_embedding - target_embedding))
            if dist_to_target < self.convergence_threshold:
                trajectory._converged = True
                break

            if step > 0:
                delta = float(np.linalg.norm(
                    new_embedding - current.embedding
                ))
                if delta < self.convergence_threshold * 0.1:
                    trajectory._converged = True
                    break

            current = new_point

        return trajectory

    def curvature_mismatch_score(self, point: ManifoldPoint) -> float:
        """Measure how much local curvature deviates from average.

        High mismatch signals that existing adapters may be inadequate for
        this region of task space.
        """
        local_curvature = self.bundle.curvature_at(point)

        all_curvatures = []
        for p in self.manifold.all_points[:50]:
            all_curvatures.append(self.bundle.curvature_at(p))

        if not all_curvatures:
            return local_curvature

        mean_curv = float(np.mean(all_curvatures))
        std_curv = float(np.std(all_curvatures)) + 1e-12
        z_score = abs(local_curvature - mean_curv) / std_curv
        return float(np.clip(z_score / 3.0, 0.0, 1.0))


# ═══════════════════════════════════════════════════════════════════════════
# 13. CURVATURE/TOPOLOGY MISMATCH TRIGGER
# ═══════════════════════════════════════════════════════════════════════════

class ManifoldMismatchTrigger:
    """Triggers adapter creation when curvature, chart coverage, or topological
    mismatch crosses a threshold.

    Three trigger conditions (any sufficient):
    1. Curvature mismatch: local curvature z-score > curvature_threshold
       → task is in a geometrically distinct region, existing adapters extrapolate
    2. Chart coverage gap: query falls outside all chart radii
       → no existing chart describes this task type
    3. Topological mismatch: persistent homology detects a hole/disconnection
       near the query → structural gap in learned competence
    """

    def __init__(
        self,
        curvature_threshold: float = 0.6,
        coverage_threshold: float = 1.5,
        topology_lifetime_threshold: float = 0.5,
    ):
        self.curvature_threshold = curvature_threshold
        self.coverage_threshold = coverage_threshold
        self.topology_lifetime_threshold = topology_lifetime_threshold
        self._homology = PersistentHomologyDetector()

    def should_create_adapter(
        self,
        query: ManifoldPoint,
        manifold: MemoryManifold,
        bundle: Optional[FiberBundle] = None,
    ) -> Dict[str, Any]:
        """Evaluate whether a new adapter should be synthesized for this task.

        Returns a dict with:
        - triggered: bool (whether any threshold was exceeded)
        - reason: str (which condition triggered)
        - scores: dict of individual mismatch scores
        """
        scores: Dict[str, float] = {}
        reasons: List[str] = []

        # 1. Curvature mismatch
        if bundle is not None:
            curvature = bundle.curvature_at(query)
            all_curvatures = []
            for p in manifold.all_points[:50]:
                all_curvatures.append(bundle.curvature_at(p))
            if all_curvatures:
                mean_c = float(np.mean(all_curvatures))
                std_c = float(np.std(all_curvatures)) + 1e-12
                z = abs(curvature - mean_c) / std_c
                scores["curvature_z"] = z
                if z > self.curvature_threshold * 3.0:
                    reasons.append("curvature_mismatch")
            else:
                scores["curvature_z"] = 0.0
        else:
            scores["curvature_z"] = 0.0

        # 2. Chart coverage gap
        active = manifold.get_active_charts(query)
        if not active:
            scores["coverage_gap"] = 1.0
            reasons.append("no_chart_coverage")
        else:
            chart = manifold.charts[active[0]]
            if chart.center.size > 0 and query.embedding.shape == chart.center.shape:
                dist = float(np.linalg.norm(query.embedding - chart.center))
                relative = dist / (chart.radius + 1e-12)
                scores["coverage_gap"] = float(np.clip(relative, 0.0, 2.0))
                if relative > self.coverage_threshold:
                    reasons.append("chart_boundary_exceeded")
            else:
                scores["coverage_gap"] = 0.0

        # 3. Topological mismatch
        uncertainty = self._homology.uncertainty_score(query, manifold)
        scores["topology_uncertainty"] = uncertainty
        if uncertainty > self.topology_lifetime_threshold:
            reasons.append("topology_gap")

        gaps = self._homology.find_gaps(manifold)
        long_lived = [g for g in gaps if g["lifetime"] > self.topology_lifetime_threshold]
        scores["n_topology_gaps"] = float(len(long_lived))

        triggered = len(reasons) > 0
        return {
            "triggered": triggered,
            "reason": ", ".join(reasons) if reasons else "none",
            "scores": scores,
        }
