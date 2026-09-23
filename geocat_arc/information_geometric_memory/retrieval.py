"""Memory retrieval by distributional distance."""
from __future__ import annotations
from .belief_distribution import BeliefDistribution
from .memory_atom import MemoryAtom
from .memory_store import MemoryStore
from . import distance_metrics as dm


METRIC_FNS = {
    "kl": dm.kl_divergence,
    "js": dm.js_divergence,
    "hellinger": dm.hellinger_distance,
    "fisher_rao": dm.fisher_rao_categorical,
}


def retrieve_similar(
    query_distribution: BeliefDistribution,
    memory_store: MemoryStore,
    metric: str = "js",
    top_k: int = 10,
    distribution_field: str = "operator_distribution",
) -> list[tuple[MemoryAtom, float]]:
    metric_fn = METRIC_FNS.get(metric, dm.js_divergence)
    q = query_distribution.probs

    scored = []
    for atom in memory_store.all_atoms():
        stored_dist = getattr(atom, distribution_field, None)
        if stored_dist is None:
            continue
        p = stored_dist.probs
        if not p:
            continue
        dist = metric_fn(q, p)
        scored.append((atom, dist))

    scored.sort(key=lambda x: x[1])
    return scored[:top_k]
