"""Induce operator schemas from failure clusters."""
from __future__ import annotations
from .failure_atom import FailureAtom


def induce_schema(cluster: list[FailureAtom]) -> dict:
    if not cluster:
        return {}

    avg_error = sum(a.error_rate for a in cluster) / len(cluster)

    all_keys = set()
    for a in cluster:
        all_keys.update(a.failure_distribution.keys())

    avg_dist = {}
    for k in all_keys:
        vals = [a.failure_distribution.get(k, 0.0) for a in cluster]
        avg_dist[k] = sum(vals) / len(vals)

    dominant_failure = max(avg_dist, key=avg_dist.get) if avg_dist else "unknown"

    if dominant_failure == "missing_operator":
        suggested_name = "inferred_transform"
        input_types = ["OBJECT"]
        output_type = "OBJECT"
    elif dominant_failure == "wrong_parameter":
        suggested_name = "adjusted_param_transform"
        input_types = ["OBJECT", "VECTOR"]
        output_type = "OBJECT"
    else:
        suggested_name = "generic_repair"
        input_types = ["GRID"]
        output_type = "GRID"

    return {
        "name": suggested_name,
        "input_types": input_types,
        "output_type": output_type,
        "common_error_pattern": dominant_failure,
        "avg_error_rate": avg_error,
        "cluster_size": len(cluster),
        "confidence": 1.0 - avg_error,
        "failure_distribution": avg_dist,
    }
