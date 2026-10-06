"""v1.9 feasibility: the prospective thresholds, from development rates only.

Inputs (exact binomial arithmetic, no prospective v1.9 data exists):
- outputs/tti/v19_repair_dev_report.json: K*' and K* complete-witness
  rates and adaptive leave-one-out discordance on the 30 development tasks;
- the v1.8 prospective complete-witness count under the old logic (11 of
  30), used ONLY as the null rate that G2 must reject (a rate to beat, not
  a tuning target);
- the v1.8 development G1 discordance (records/ITEM2_V18_FEASIBILITY.md:
  transplant 14 of 40, BLIND 10 of 40, no reverse), G1 being a
  proposer-level gate the repair does not touch.

Rules fixed here, before any prospective task exists:
- N_TASKS = 30 (the v1.8 corpus size; runtime bounded);
- W_MIN = the smallest W with P(X >= W | p0) <= 0.01, p0 = the larger of
  the old-logic rates (v1.8 prospective 11/30, development K* rate);
- DELTA_MIN = ceil(0.2 * N_TASKS): a material improvement is a net gain of
  at least a fifth of the tasks;
- the design is feasible only if G2 power at the development K*' rate
  minus 0.15 is at least 0.80 and G3 power at the development discordance
  is at least 0.80; otherwise the record says so and the thresholds stand.
"""
import json
import math
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEV = os.path.join(HERE, "outputs", "tti", "v19_repair_dev_report.json")
ROWS = os.path.join(HERE, "outputs", "tti", "v19_repair_dev_rows.jsonl")
OUT = os.path.join(HERE, "outputs", "tti", "v19_feasibility.json")
N = 30


def tail(k, n, p):
    return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k, n + 1))


def sign_p(b, c):
    n = b + c
    return sum(math.comb(n, k) for k in range(b, n + 1)) / 2 ** n if n else 1.0


def g_power(n, q, r, delta=0, alpha=0.05):
    """P(b - c >= delta and sign_p(b, c) < alpha) with each task discordant
    for the first arm with probability q and the second with probability r."""
    tot = 0.0
    for b in range(n + 1):
        for c in range(n - b + 1):
            pr = (math.factorial(n) / (math.factorial(b) * math.factorial(c) * math.factorial(n - b - c))
                  * q ** b * r ** c * (1 - q - r) ** (n - b - c))
            if b - c >= delta and sign_p(b, c) < alpha:
                tot += pr
    return tot


def main():
    dev = json.load(open(DEV))
    t = dev["tasks"]
    p_new = dev["witness_new"] / t
    p_old_dev = dev["witness_old"] / t
    p0 = max(11 / 30, p_old_dev)
    w_min = next(w for w in range(N + 1) if tail(w, N, p0) <= 0.01)
    delta = math.ceil(0.2 * N)
    st_new, st_old = dev["stability_new"], dev["stability_old"]
    #  adaptive leave-one-out discordance on development tasks, from the rows
    rows = [json.loads(line) for line in open(ROWS)]
    rows = [x for x in rows if x.get("status") != "RUN_ERROR"]
    new_only = sum(1 for x in rows if x["loo_new"]["passed"] and not x["loo_old"]["passed"])
    old_only = sum(1 for x in rows if x["loo_old"]["passed"] and not x["loo_new"]["passed"])
    q, r = new_only / t, old_only / t
    out = {
        "N_TASKS": N, "W_MIN": w_min, "DELTA_MIN": delta,
        "inputs": {"development_tasks": t, "witness_new_dev": dev["witness_new"],
                   "witness_old_dev": dev["witness_old"], "witness_old_v18_prospective": "11 of 30",
                   "p0_null": p0, "loo_new_only_dev": new_only, "loo_old_only_dev": old_only,
                   "stability_new": st_new, "stability_old": st_old},
        "G2": {"rule": "W_MIN = smallest W with P(X >= W | p0) <= 0.01",
               "size_at_p0": tail(w_min, N, p0),
               "power_at_dev_rate": tail(w_min, N, p_new),
               "power_at_dev_rate_minus_0.15": tail(w_min, N, max(0.0, p_new - 0.15)),
               "power_at_dev_rate_minus_0.25": tail(w_min, N, max(0.0, p_new - 0.25))},
        "G3": {"rule": "b - c >= DELTA_MIN and one-sided sign p < 0.05",
               "power_at_dev_discordance": g_power(N, q, r, delta),
               "power_if_gain_halves": g_power(N, q / 2, r, delta),
               "size_no_gain_q_r_0.05": g_power(N, 0.05, 0.05, delta),
               "size_no_gain_q_r_0.15": g_power(N, 0.15, 0.15, delta)},
        "G1": {"note": "proposer-level gate, unchanged by the repair; v1.8 development discordance",
               "power_vs_transplant": g_power(N, 14 / 40, 0.0),
               "power_vs_blind": g_power(N, 10 / 40, 0.0),
               "power_if_advantage_shrinks_q0.15": g_power(N, 0.15, 0.0)},
    }
    out["feasible"] = (out["G2"]["power_at_dev_rate_minus_0.15"] >= 0.80
                       and out["G3"]["power_at_dev_discordance"] >= 0.80)
    json.dump(out, open(OUT, "w"), indent=1, sort_keys=True)
    print(json.dumps(out, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
