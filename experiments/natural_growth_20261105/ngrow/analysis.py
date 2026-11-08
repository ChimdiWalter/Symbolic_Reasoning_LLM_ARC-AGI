"""Pre-registered statistics (PROTOCOL.md section 7). Standard library only.

Paired comparison of two arms A and B over the same tasks:
- per task, d = (correct test outputs under A) - (correct test outputs under B); d is in {-1, 0, 1} for one-output
  tasks and in {-3, ..., 3} for ConceptARC's three-output tasks;
- exact McNemar (sign) test: n_A = tasks with d > 0, n_B = tasks with d < 0; two-sided exact binomial p-value on
  n_A out of n_A + n_B at 1/2 (identical to the exact McNemar test when every task has one output);
- effect: the total difference in correct outputs, sum(d), with a family-clustered bootstrap 95% interval: clusters
  are families (ConceptARC concepts, 1D-ARC types) and, for Mini-ARC (one pool), single tasks; clusters are
  resampled with replacement within each benchmark (stratified), 10,000 draws, random.Random(20261105), percentile
  interval (2.5%, 97.5%).
Decision: "A beats B" if p < alpha and the interval's lower end is above 0; "B beats A" if p < alpha and the upper end
is below 0; "tie" if n_A == n_B; otherwise "inconclusive".
Holm's step-down adjustment over the secondary family. Wilson 95% intervals for proportions.
"""
import math
import random

DRAWS = 10_000
BOOT_SEED = 20261105


def binom_two_sided(k, n):
    if n == 0:
        return 1.0
    lo = min(k, n - k)
    tail = sum(math.comb(n, i) for i in range(lo + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def wilson(k, n, z=1.959963984540054):
    if n == 0:
        return [None, None]
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    hw = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [round(c - hw, 4), round(c + hw, 4)]


def cluster_boot(rows, key="d", draws=DRAWS, seed=BOOT_SEED):
    """rows: dicts with bench, cluster and the per-task value `key`. Percentile 95% interval of the sum."""
    strata = {}
    for r in rows:
        strata.setdefault(r["bench"], {}).setdefault(r["cluster"], []).append(r[key])
    sums = {b: [sum(v) for _, v in sorted(cl.items())] for b, cl in sorted(strata.items())}
    rng = random.Random(seed)
    stats = []
    for _ in range(draws):
        tot = 0
        for b, s in sums.items():
            n = len(s)
            tot += sum(s[rng.randrange(n)] for _ in range(n))
        stats.append(tot)
    stats.sort()
    return [stats[int(0.025 * draws)], stats[int(0.975 * draws) - 1]]


def compare(rows, a, b, alpha=0.05):
    """rows: per task {bench, cluster, <arm>: correct count, ...} restricted to the analysed population."""
    rs = [dict(r, d=r[a] - r[b]) for r in rows if r.get(a) is not None and r.get(b) is not None]
    na = sum(1 for r in rs if r["d"] > 0)
    nb = sum(1 for r in rs if r["d"] < 0)
    p = binom_two_sided(na, na + nb)
    ci = cluster_boot(rs) if rs else [0, 0]
    if na == nb:
        dec = "tie"
    elif p < alpha and ci[0] > 0:
        dec = f"{a} beats {b}"
    elif p < alpha and ci[1] < 0:
        dec = f"{b} beats {a}"
    else:
        dec = "inconclusive"
    return {"tasks": len(rs), "correct_" + a: sum(r[a] for r in rs), "correct_" + b: sum(r[b] for r in rs),
            "tasks_only_" + a: na, "tasks_only_" + b: nb, "exact_mcnemar_p": round(p, 6),
            "sum_difference": sum(r["d"] for r in rs), "family_cluster_ci95": ci, "decision": dec}


def holm(pvals):
    """{name: p} -> {name: Holm-adjusted p}."""
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    m, out, run = len(items), {}, 0.0
    for i, (k, p) in enumerate(items):
        run = max(run, min(1.0, (m - i) * p))
        out[k] = round(run, 6)
    return out


def power_sim(lam_a, lam_b, draws=20_000, alpha=0.05, seed=7):
    """P(exact McNemar p < alpha and n_A > n_B) when n_A ~ Poisson(lam_a), n_B ~ Poisson(lam_b)."""
    rng = random.Random(seed)

    def pois(lam):
        if lam <= 0:
            return 0
        L, k, p = math.exp(-lam), 0, 1.0
        while True:
            p *= rng.random()
            if p <= L:
                return k
            k += 1
    hit = 0
    for _ in range(draws):
        x, y = pois(lam_a), pois(lam_b)
        if x > y and binom_two_sided(x, x + y) < alpha:
            hit += 1
    return round(hit / draws, 4)


def min_discordant_for_significance(alpha=0.05):
    """Smallest n with binom_two_sided(n, n) < alpha (all discordant tasks favour one arm)."""
    n = 1
    while binom_two_sided(n, n) >= alpha:
        n += 1
    return n
