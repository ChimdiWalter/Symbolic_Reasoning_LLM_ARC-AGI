"""Paired comparisons of exact recoveries.

Reused, read only: the CORA U6 statistics module (experiments/universality_boolean_bbm_20261103/u6/stats.py, frozen in
the U6 code freeze): Wilson 95% intervals, a cluster bootstrap over units (10,000 resamples from
numpy.random.default_rng(0), percentile 95% intervals) and Holm's procedure.
Added here: the exact McNemar test (two-sided binomial test on the discordant pairs).
"""
import math
import os
import sys

_U6 = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                   "universality_boolean_bbm_20261103")
if _U6 not in sys.path:
    sys.path.insert(0, _U6)
from u6 import stats as u6stats  # noqa: E402

U6_STATS_PATH = os.path.join(_U6, "u6", "stats.py")


def mcnemar_exact(b, c):
    """Two-sided exact McNemar p-value for b pairs (first arm only) against c pairs (second arm only)."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2.0 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def compare(rows, a, b, clusters="cluster"):
    """Exact recoveries of arm a against arm b on the same items, with a cluster bootstrap interval."""
    xa = {r["id"]: r["arms"][a]["exact"] for r in rows}
    xb = {r["id"]: r["arms"][b]["exact"] for r in rows}
    n = len(rows)
    only_a = sum(1 for i in xa if xa[i] and not xb[i])
    only_b = sum(1 for i in xa if xb[i] and not xa[i])
    units = sorted({r[clusters] for r in rows})
    num_a, num_b, den = {}, {}, {}
    for r in rows:
        u = r[clusters]
        num_a[u] = num_a.get(u, 0) + xa[r["id"]]
        num_b[u] = num_b.get(u, 0) + xb[r["id"]]
        den[u] = den.get(u, 0) + 1
    bs = u6stats.Bootstrap(units)
    d = u6stats.diff_of_ratios(bs, num_a, den, num_b, den)
    return {"arms": [a, b], "items": n, "clusters": len(units),
            "exact": [sum(xa.values()), sum(xb.values())],
            "rate": [sum(xa.values()) / n if n else None, sum(xb.values()) / n if n else None],
            "wilson95": [u6stats.wilson(sum(xa.values()), n), u6stats.wilson(sum(xb.values()), n)],
            "only_first": only_a, "only_second": only_b,
            "mcnemar_exact_p": mcnemar_exact(only_a, only_b),
            "difference": d["point"], "cluster_bootstrap_ci95": d["ci95"],
            "bootstrap_p_one_sided": d["p_one_sided"], "dropped_replicates": d["dropped_replicates"]}


def holm(pvals):
    return u6stats.holm(pvals)
