"""Item-2 v1.8: feasibility arithmetic for the prospective thresholds.

Exact binomial computations only; no data beyond the development audit's
rates is read. Writes outputs/tti/v18_feasibility.json.
"""
from __future__ import annotations

import json
import math
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "outputs", "tti", "v18_feasibility.json")
N = int(sys.argv[1]) if len(sys.argv) > 1 else 24
W = int(sys.argv[2]) if len(sys.argv) > 2 else 12


def p_at_least(k, n, p):
    return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k, n + 1))


def sign_p(b, c):
    n = b + c
    return sum(math.comb(n, k) for k in range(b, n + 1)) / 2 ** n if n else 1.0


def main():
    dev = json.load(open(os.path.join(HERE, "outputs", "tti", "v18_dev_audit.json")))
    eng = dev["engine"]
    witness_rate = sum(1 for k in eng["real_loo_folds_success"] if k == 7) / eng["tasks"]
    out = {"N_TASKS": N, "W_MIN": W,
           "development": {"engine_tasks": eng["tasks"], "engine_success": eng["success"],
                           "real_loo_passed": eng["real_loo_passed"],
                           "complete_witness_rate_dev": witness_rate,
                           "fc_useful": dev["arms"]["FAILURE_CONDITIONED"]["selected_heldout_exact"],
                           "shuffled_useful": dev["arms"]["SHUFFLED_FRONTIER"]["selected_heldout_exact"],
                           "demo_only_useful": dev["arms"]["DEMO_ONLY"]["selected_heldout_exact"],
                           "tasks": dev["tasks"]},
           "G2_witnesses": {
               "rule": f"at least {W} of {N} tasks give a complete synthetic B/P/U/L/T/A witness",
               "size_under_null_rate_0.25": p_at_least(W, N, 0.25),
               "size_under_null_rate_0.33": p_at_least(W, N, 1 / 3),
               "power_at_rate_0.60": p_at_least(W, N, 0.60),
               "power_at_rate_0.75": p_at_least(W, N, 0.75),
               "power_at_dev_rate": p_at_least(W, N, witness_rate)},
           "G1_sign_test": {
               "rule": "one-sided exact sign test on tasks discordant in fitter-level usefulness, alpha 0.05",
               "min_discordant_for_alpha": next(b for b in range(1, 40) if sign_p(b, 0) < 0.05),
               "p_if_all_N_discordant_one_way": sign_p(N, 0),
               "dev_discordance_fc_vs_shuffled": [dev["arms"]["FAILURE_CONDITIONED"]["selected_heldout_exact"]
                                                  - 0, 0]},
           "runtime_estimate_minutes": {"per_task_dev_engine_mean_s": None, "note": "filled from dev rows"}}
    rows = [json.loads(l) for l in open(os.path.join(HERE, "outputs", "tti", "v18_dev_rows.jsonl"))]
    eng_rows = [r for r in rows if "engine" in r]
    per = []
    for r in eng_rows:
        s = sum(a["seconds"] for a in r["arms"].values())
        s += (r["engine"]["with"]["seconds"] or 0) + (r["engine"]["without"]["seconds"] or 0)
        s += sum((f.get("engine_seconds") or 0) + (f.get("proposer_seconds") or 0) for f in r["real_loo"]["folds"])
        per.append(s)
    mean = sum(per) / len(per) if per else None
    out["runtime_estimate_minutes"] = {"per_task_dev_engine_mean_s": round(mean, 1) if mean else None,
                                       "N_tasks_minutes": round(mean * N / 60, 1) if mean else None,
                                       "note": "development machine load about 40 on 24 CPUs"}
    with open(OUT, "w") as handle:
        handle.write(json.dumps(out, indent=1, sort_keys=True) + "\n")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
