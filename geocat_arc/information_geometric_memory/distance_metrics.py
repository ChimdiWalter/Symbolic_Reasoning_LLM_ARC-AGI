"""Information-geometric distance metrics between distributions."""
from __future__ import annotations
import math

EPS = 1e-12


def _aligned_probs(p: dict[str, float], q: dict[str, float]) -> tuple[list[float], list[float]]:
    all_keys = sorted(set(p.keys()) | set(q.keys()))
    pv = [p.get(k, 0.0) for k in all_keys]
    qv = [q.get(k, 0.0) for k in all_keys]
    return pv, qv


def _smooth(probs: list[float], eps: float = EPS) -> list[float]:
    result = [max(p, eps) for p in probs]
    total = sum(result)
    return [p / total for p in result]


def kl_divergence(p: dict[str, float], q: dict[str, float]) -> float:
    pv, qv = _aligned_probs(p, q)
    pv = _smooth(pv)
    qv = _smooth(qv)
    return sum(pi * math.log(pi / qi) for pi, qi in zip(pv, qv))


def js_divergence(p: dict[str, float], q: dict[str, float]) -> float:
    pv, qv = _aligned_probs(p, q)
    pv = _smooth(pv)
    qv = _smooth(qv)
    m = [(pi + qi) / 2.0 for pi, qi in zip(pv, qv)]
    kl_pm = sum(pi * math.log(pi / mi) for pi, mi in zip(pv, m))
    kl_qm = sum(qi * math.log(qi / mi) for qi, mi in zip(qv, m))
    return (kl_pm + kl_qm) / 2.0


def hellinger_distance(p: dict[str, float], q: dict[str, float]) -> float:
    pv, qv = _aligned_probs(p, q)
    pv = _smooth(pv)
    qv = _smooth(qv)
    s = sum((math.sqrt(pi) - math.sqrt(qi)) ** 2 for pi, qi in zip(pv, qv))
    return math.sqrt(s / 2.0)


def fisher_rao_categorical(p: dict[str, float], q: dict[str, float]) -> float:
    pv, qv = _aligned_probs(p, q)
    pv = _smooth(pv)
    qv = _smooth(qv)
    cos_val = sum(math.sqrt(pi * qi) for pi, qi in zip(pv, qv))
    cos_val = min(cos_val, 1.0)
    return 2.0 * math.acos(cos_val)
