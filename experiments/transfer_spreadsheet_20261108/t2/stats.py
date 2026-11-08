"""Paired statistics for the primary: exact McNemar test and a paired bootstrap 95% interval."""
import math
import random


def mcnemar_exact(b, c):
    """Two-sided exact McNemar p-value from the discordant counts b and c."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def paired_bootstrap(x, y, reps=10000, seed=20261108):
    """95% percentile interval of mean(x) - mean(y) over tasks resampled with replacement."""
    n = len(x)
    if n == 0:
        return [None, None]
    rng = random.Random(seed)
    d = [a - b for a, b in zip(x, y)]
    stats = []
    for _ in range(reps):
        s = 0
        for _ in range(n):
            s += d[rng.randrange(n)]
        stats.append(s / n)
    stats.sort()
    return [stats[int(0.025 * reps)], stats[int(0.975 * reps) - 1]]


def compare(name_a, a, name_b, b):
    """a, b: lists of 0/1 per task (same order)."""
    n = len(a)
    only_a = sum(1 for p, q in zip(a, b) if p and not q)
    only_b = sum(1 for p, q in zip(a, b) if q and not p)
    lo, hi = paired_bootstrap(a, b)
    return {"a": name_a, "b": name_b, "n": n, "a_right": sum(a), "b_right": sum(b), "a_only": only_a,
            "b_only": only_b, "difference": (sum(a) - sum(b)) / n if n else None, "ci95_bootstrap": [lo, hi],
            "mcnemar_exact_p": mcnemar_exact(only_a, only_b)}


def holm(pvals, alpha=0.05):
    """Holm step-down adjusted p-values (same order as given) and rejections at family-wise alpha."""
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    adj, running = [None] * m, 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * pvals[i]))
        adj[i] = running
    return adj, [a < alpha for a in adj]
