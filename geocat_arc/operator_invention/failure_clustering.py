"""Cluster near-solved failures by similarity."""
from __future__ import annotations
import numpy as np
from .failure_atom import FailureAtom


def failure_distance(a: FailureAtom, b: FailureAtom) -> float:
    rate_dist = abs(a.error_rate - b.error_rate)

    all_keys = set(a.failure_distribution.keys()) | set(b.failure_distribution.keys())
    if all_keys:
        dist_diff = sum(
            abs(a.failure_distribution.get(k, 0) - b.failure_distribution.get(k, 0))
            for k in all_keys
        ) / len(all_keys)
    else:
        dist_diff = 0.0

    return 0.5 * rate_dist + 0.5 * dist_diff


def cluster_failures(
    atoms: list[FailureAtom],
    distance_threshold: float = 0.3,
) -> list[list[FailureAtom]]:
    if not atoms:
        return []

    n = len(atoms)
    assigned = [False] * n
    clusters = []

    for i in range(n):
        if assigned[i]:
            continue
        cluster = [atoms[i]]
        assigned[i] = True

        for j in range(i + 1, n):
            if assigned[j]:
                continue
            if failure_distance(atoms[i], atoms[j]) < distance_threshold:
                cluster.append(atoms[j])
                assigned[j] = True

        clusters.append(cluster)

    return clusters
