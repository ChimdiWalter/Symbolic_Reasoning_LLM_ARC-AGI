"""REMA-inspired bounded latent failure diagnostics for candidate trajectories."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence

import numpy as np


def _as_matrix(vectors: Sequence[Sequence[float]]) -> np.ndarray:
    arr = np.asarray(vectors, dtype=float)
    if arr.ndim != 2:
        raise ValueError("Expected a 2D matrix of latent vectors")
    return arr


def nearest_success_distance(
    success_vectors: Sequence[Sequence[float]],
    query_vectors: Sequence[Sequence[float]],
    k: int = 3,
) -> np.ndarray:
    success = _as_matrix(success_vectors)
    query = _as_matrix(query_vectors)
    if success.shape[0] == 0:
        return np.full((query.shape[0],), np.inf, dtype=float)
    distances = []
    for query_row in query:
        deltas = success - query_row
        norms = np.linalg.norm(deltas, axis=1)
        k_smallest = np.sort(norms)[: max(1, min(int(k), len(norms)))]
        distances.append(float(np.mean(k_smallest)))
    return np.asarray(distances, dtype=float)


def latent_separability_score(
    success_vectors: Sequence[Sequence[float]],
    failure_vectors: Sequence[Sequence[float]],
) -> float:
    success = _as_matrix(success_vectors)
    failure = _as_matrix(failure_vectors)
    if success.shape[0] == 0 or failure.shape[0] == 0:
        return 0.0
    success_center = success.mean(axis=0)
    failure_center = failure.mean(axis=0)
    numerator = float(np.linalg.norm(success_center - failure_center))
    denominator = float(np.mean(np.linalg.norm(success - success_center, axis=1)) + np.mean(np.linalg.norm(failure - failure_center, axis=1)))
    return numerator / max(1e-8, denominator)


def divergence_step(
    trajectory_vectors: Sequence[Sequence[float]],
    success_vectors: Sequence[Sequence[float]],
    k: int = 3,
    threshold: Optional[float] = None,
) -> Optional[int]:
    trajectory = _as_matrix(trajectory_vectors)
    success = _as_matrix(success_vectors)
    if trajectory.shape[0] == 0 or success.shape[0] == 0:
        return None
    success_threshold = threshold
    if success_threshold is None:
        self_distances = nearest_success_distance(success, success, k=k)
        success_threshold = float(np.mean(self_distances) + np.std(self_distances))
    distances = nearest_success_distance(success, trajectory, k=k)
    for index, value in enumerate(distances.tolist()):
        if value > float(success_threshold):
            return index
    return None


def summarize_reasoning_manifold(
    success_vectors: Sequence[Sequence[float]],
    failure_vectors: Sequence[Sequence[float]],
    trajectory_vectors: Optional[Sequence[Sequence[float]]] = None,
    k: int = 3,
) -> Dict[str, Any]:
    success = _as_matrix(success_vectors)
    failure = _as_matrix(failure_vectors)
    summary: Dict[str, Any] = {
        "success_count": int(success.shape[0]),
        "failure_count": int(failure.shape[0]),
        "k": int(k),
        "separability_score": latent_separability_score(success, failure) if success.size and failure.size else 0.0,
        "failure_distance_mean": float(np.mean(nearest_success_distance(success, failure, k=k))) if success.size and failure.size else 0.0,
        "success_self_distance_mean": float(np.mean(nearest_success_distance(success, success, k=k))) if success.size else 0.0,
    }
    if trajectory_vectors is not None:
        trajectory = _as_matrix(trajectory_vectors)
        summary["trajectory_length"] = int(trajectory.shape[0])
        summary["divergence_step"] = divergence_step(trajectory, success, k=k)
    return summary
