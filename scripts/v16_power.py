"""Item-2 v1.6: exact-test power for the prospective ambiguous population.

The group unit is the integer sum, over a group's verification-ambiguous
queries, of the half-credit unit differences between two arms. Group sizes
(ambiguous queries per group) and the discordance rate (share of ambiguous
queries on which the two arms disagree) come from the DEVELOPMENT report;
the effect is a parameter. Per disagreeing query the difference is +2 or
-2, with P(+2) chosen so that the mean per-query increment equals the
effect. Power = share of simulations with exact one-sided sign-flip
p < alpha; also the joint share with mean >= delta_min (gates B and D).

    v16_power.py <dev_report.json> [out.json]
"""
from __future__ import annotations

import json
import os
import random
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from cora_arc2026 import v15_sel as S                             # noqa: E402

SEED = 20261002
SIMS = 1000
ALPHA = 0.01
DELTA_MIN = 0.05


def group_sizes_from(report):
    """Ambiguous queries per group in the development set."""
    fam = report["ambiguous_by_family"]
    #  the report stores totals; the per-group sizes are rebuilt from the
    #  development queries when available, else a conservative uniform 1..8
    sizes = report.get("ambiguous_group_sizes")
    if sizes:
        return sizes
    return list(range(1, 9))


def power(sizes, discordance, effect, n_groups, sims=SIMS, alpha=ALPHA, seed=SEED):
    rng = random.Random(seed)
    p_plus = (discordance + effect) / 2.0          # mean per query = 2*(p+ - p-) /2 = effect
    p_minus = discordance - p_plus
    if p_minus < 0:
        raise ValueError("effect exceeds the discordance rate")
    hits = joint = 0
    for _ in range(sims):
        vals, total_q, total_sum = [], 0, 0
        for _ in range(n_groups):
            m = rng.choice(sizes)
            s = 0
            for _ in range(m):
                u = rng.random()
                s += 2 if u < p_plus else (-2 if u < discordance else 0)
            vals.append(s)
            total_q += m
            total_sum += s
        p = S.signflip_p(vals)
        ok = p < alpha and total_sum > 0
        hits += ok
        joint += ok and (total_sum / (2.0 * total_q) >= DELTA_MIN)
    return hits / sims, joint / sims


def main():
    with open(sys.argv[1]) as handle:
        rep = json.load(handle)
    sizes = group_sizes_from(rep)
    disc = rep.get("P0_discordance_with_D", 0.5)
    out = {"seed": SEED, "sims": SIMS, "alpha": ALPHA, "delta_min": DELTA_MIN,
           "group_sizes_source": "development report", "discordance": disc, "table": []}
    for effect in (0.05, 0.075, 0.10, 0.125, 0.15):
        for n in (60, 90, 120, 150, 180, 240):
            try:
                pw, jt = power(sizes, disc, effect, n)
            except ValueError:
                continue
            out["table"].append({"effect": effect, "ambiguous_groups": n,
                                 "power_B": pw, "power_B_and_D": jt})
            print(f"effect {effect:.3f} groups {n:4d} power_B {pw:.3f} joint_B_D {jt:.3f}")
    if len(sys.argv) > 2:
        with open(sys.argv[2], "w") as handle:
            handle.write(json.dumps(out, indent=1) + "\n")


if __name__ == "__main__":
    main()
