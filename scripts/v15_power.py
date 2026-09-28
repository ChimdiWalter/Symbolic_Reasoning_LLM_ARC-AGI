"""Frozen v1.5 sample-size calculation.

Variance proxy from completed evidence: on the 42 included v1.4 twin groups,
the per-query hits of the v1.4 S0 (demonstration) and S7 (failure summary)
nearest-neighbour decisions, which are two decisions on the same queries.
Their discordance and the spread of their group-mean paired difference
stand in for the paired accuracy difference of two selectors, which is
conservative for a nested D against D+F comparison.

Power is that of the exact one-sided group-level sign-flip test at
alpha 0.01, simulated with a fixed seed: per query the paired difference is
+1, -1 or 0 with discordance d and mean delta, 8 queries per group, and no
within-group correlation (the proxy's measured correlation is 0.005).
Nothing here fits or scores a selector.
"""
from __future__ import annotations

import json
import os
import re
import statistics
import sys

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

DISCORDANCE = 0.414
SEED = 20260928
SIMS = 1000
ALPHA = 0.01


def signflip_p(units) -> float:
    units = np.asarray(units, dtype=np.int64)
    obs = int(units.sum())
    a = np.abs(units)
    total = int(a.sum())
    dist = np.zeros(2 * total + 1)
    dist[total] = 1.0
    for v in a:
        if v == 0:
            continue
        new = np.zeros_like(dist)
        new[:-v] += 0.5 * dist[v:]
        new[v:] += 0.5 * dist[:-v]
        dist = new
    return float(dist[obs + total:].sum())


def power(n, delta, d=DISCORDANCE, q=8, sims=SIMS, seed=SEED) -> float:
    rng = np.random.default_rng(seed)
    p_plus, p_minus = d / 2 + delta / 2, d / 2 - delta / 2
    hits = 0
    for _ in range(sims):
        u = rng.choice([2, -2, 0], size=(n, q), p=[p_plus, p_minus, 1 - d]).sum(axis=1)
        hits += signflip_p(u) < ALPHA
    return hits / sims


def proxy() -> dict:
    from cora_arc2026 import v14_loc as L
    cdir = os.path.join(HERE, "outputs", "tti", "v14_twin_corpus")
    recs = [json.load(open(os.path.join(cdir, n))) for n in sorted(os.listdir(cdir))
            if re.fullmatch(r"full\d{5}\.json", n)]
    inc, _ = L.first_admissions(recs)
    groups = sorted((r["group"] for r in inc), key=lambda g: g["group_digest"])
    with open(os.path.join(HERE, "outputs", "tti", "v13_calibration", "calibration.json")) as h:
        cal = json.load(h)
    diffs, per_q, a0, a7 = [], [], [], []
    for gi, g in enumerate(groups):
        h0 = L.group_stats(g["episodes"], "S0", cal, f"S0|{gi}")["hits"]
        h7 = L.group_stats(g["episodes"], "S7", cal, f"S7|{gi}")["hits"]
        d = [b - a for a, b in zip(h0, h7)]
        per_q += d
        diffs.append(sum(d) / 8)
        a0.append(sum(h0) / 8)
        a7.append(sum(h7) / 8)
    sd = statistics.stdev(diffs)
    vq = statistics.pvariance(per_q)
    return {"groups": len(groups), "s0_rate": round(statistics.mean(a0), 4),
            "s7_rate": round(statistics.mean(a7), 4),
            "discordance": round(sum(1 for x in per_q if x) / len(per_q), 4),
            "group_mean_sd": round(sd, 4),
            "within_group_correlation": round((sd ** 2 * 8 / vq - 1) / 7, 4)}


if __name__ == "__main__":
    print(json.dumps(proxy(), indent=1))
    for n in (256, 272, 288):
        print(n, power(n, 0.05))
    print("68 at 0.10", power(68, 0.10))
