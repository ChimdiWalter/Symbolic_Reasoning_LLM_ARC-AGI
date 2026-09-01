"""Two-attempt selection and complementarity measurement (phase P2; plan §IX).

ARC grants exactly two predictions per test input and scores their UNION, so
the objective is P(A1 correct OR A2 correct) — never the top-2 of one ranked
list, which wastes the second attempt on a correlated near-duplicate of the
first.

Policy implemented here:

    Attempt 1 (CORA-Cert):    the highest-confidence candidate.
    Attempt 2 (CORA-Explore): the best ERROR-DIVERSE alternative — the
        highest-confidence candidate whose predicted grid DIFFERS from
        attempt 1, preferring a different explanation source; only when no
        differing candidate exists does it fall back to rank 2.

Candidates carry a `source` label (e.g. "certified", "uncertified",
"invented_production", "other_view", "neural_fallback") so complementarity can
be measured per source pair. `complementarity_report` scores the naive top-2
policy against the diversity policy on the same pools — the measurement the
master plan requires before any policy claim.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class Candidate:
    prediction: Any                  # grid (list of lists) or None
    confidence: float
    source: str = "unlabelled"


def _key(grid) -> str:
    return repr(grid)


def pick_attempts(pool: Sequence[Candidate]) -> tuple:
    """(attempt_1, attempt_2) predictions from one candidate pool."""
    ranked = sorted([c for c in pool if c.prediction is not None],
                    key=lambda c: (-c.confidence, c.source, _key(c.prediction)))
    if not ranked:
        return None, None
    first = ranked[0]
    differing = [c for c in ranked[1:] if _key(c.prediction) != _key(first.prediction)]
    if not differing:
        return first.prediction, (ranked[1].prediction if len(ranked) > 1 else None)
    other_source = [c for c in differing if c.source != first.source]
    second = (other_source or differing)[0]
    return first.prediction, second.prediction


def pick_top2(pool: Sequence[Candidate]) -> tuple:
    """The naive baseline: rank 1 and rank 2 of the same list."""
    ranked = sorted([c for c in pool if c.prediction is not None],
                    key=lambda c: (-c.confidence, c.source, _key(c.prediction)))
    a1 = ranked[0].prediction if ranked else None
    a2 = ranked[1].prediction if len(ranked) > 1 else None
    return a1, a2


def _hit(attempts: tuple, solution) -> bool:
    return any(a is not None and a == solution for a in attempts)


def complementarity_report(pools: Mapping[str, Sequence[Candidate]],
                           solutions: Mapping[str, Any]) -> dict:
    """Score naive-top2 vs diversity policy over pools of candidates.

    pools/solutions are keyed by an opaque output id (task+test-index); the
    report never branches on the key's content."""
    n = len(pools)
    naive_hits = diverse_hits = a1_hits = 0
    rescued, lost = [], []
    source_pairs: dict = {}
    for key in sorted(pools):
        pool, solution = pools[key], solutions[key]
        naive = pick_top2(pool)
        diverse = pick_attempts(pool)
        a1_hits += naive[0] is not None and naive[0] == solution
        nh, dh = _hit(naive, solution), _hit(diverse, solution)
        naive_hits += nh
        diverse_hits += dh
        if dh and not nh:
            rescued.append(key)
        if nh and not dh:
            lost.append(key)
        if dh and diverse[1] is not None and diverse[1] == solution \
                and (diverse[0] is None or diverse[0] != solution):
            ranked = sorted([c for c in pool if c.prediction is not None],
                            key=lambda c: (-c.confidence, c.source,
                                           _key(c.prediction)))
            winner = next(c for c in ranked
                          if c.prediction == solution)
            pair = (ranked[0].source, winner.source)
            source_pairs[pair] = source_pairs.get(pair, 0) + 1
    return {
        "n_outputs": n,
        "attempt1_only": a1_hits / max(1, n),
        "naive_top2": naive_hits / max(1, n),
        "diversity_policy": diverse_hits / max(1, n),
        "rescued_by_diversity": rescued,
        "lost_by_diversity": lost,
        "second_attempt_win_source_pairs": {f"{a}->{b}": c for (a, b), c
                                            in sorted(source_pairs.items())},
    }
