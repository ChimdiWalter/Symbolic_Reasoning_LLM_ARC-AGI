"""Paired statistics: exact McNemar on held items and a family-cluster paired bootstrap interval."""
import math
import random


def mcnemar_exact(b, c):
    """Two-sided exact McNemar p value. b = items only arm A recovers, c = items only arm B recovers."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    p = 2.0 * sum(math.comb(n, i) for i in range(k + 1)) / 2.0 ** n
    return min(1.0, p)


def cluster_bootstrap(per_family, resamples, seed):
    """per_family: list of (successes A, successes B, items). Returns (difference, lo, hi) of the
    difference in exact recovery rate A - B, with a 95% percentile interval from resampling families."""
    if not per_family:
        return None, None, None
    ta = sum(x[0] for x in per_family)
    tb = sum(x[1] for x in per_family)
    tn = sum(x[2] for x in per_family)
    rng = random.Random(seed)
    F = len(per_family)
    diffs = []
    for _ in range(resamples):
        sa = sb = n = 0
        for _ in range(F):
            a, b, m = per_family[rng.randrange(F)]
            sa += a
            sb += b
            n += m
        diffs.append((sa - sb) / n if n else 0.0)
    diffs.sort()
    lo = diffs[int(math.floor(0.025 * resamples))]
    hi = diffs[int(math.ceil(0.975 * resamples)) - 1]
    return (ta - tb) / tn if tn else None, lo, hi


def compare(records, a, b, resamples, seed):
    """records: per-family dicts with 'held' lists of per-item arm results."""
    only_a = only_b = both = neither = 0
    per_family = []
    for fr in records:
        sa = sb = 0
        for h in fr["held"]:
            ea, eb = h[a]["exact"], h[b]["exact"]
            sa += ea
            sb += eb
            if ea and not eb:
                only_a += 1
            elif eb and not ea:
                only_b += 1
            elif ea and eb:
                both += 1
            else:
                neither += 1
        per_family.append((sa, sb, len(fr["held"])))
    d, lo, hi = cluster_bootstrap(per_family, resamples, seed)
    return {"arms": "%s minus %s" % (a, b), "only_%s" % a: only_a, "only_%s" % b: only_b, "both": both,
            "neither": neither, "mcnemar_exact_p": mcnemar_exact(only_a, only_b),
            "difference_in_exact_rate": d, "bootstrap95": [lo, hi], "families": len(per_family)}
