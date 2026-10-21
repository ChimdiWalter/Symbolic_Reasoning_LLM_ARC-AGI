"""Per-family accounting of the ncv2-g2 synthetic study (descriptive; run after the frozen `score` stage).

    python scripts/neural_cora_v2g2_synthetic_accounting.py

Reads outputs/neural_cora_v2g2/synthetic_eval/{score.json,rows.jsonl}; prints the pooled numbers, a per-family table
(pass@2 at 1000/3000, correct coverage, new and lost solves, generator coverage, first-fit positions, CPU, truncations,
wrong attempts) and output hashes. It never changes the frozen decision.
"""
import hashlib
import json
import os
from collections import defaultdict

import numpy as np

R = "/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_arc2026/outputs/neural_cora_v2g2/synthetic_eval"
S = json.load(open(f"{R}/score.json"))
s, T = S["summary"], S["tasks"]
rows = {json.loads(l)["task_id"]: json.loads(l) for l in open(f"{R}/rows.jsonl")}
print("decision:", s["decision"], "| n:", s["n"], "| decision budget:", s["decision_budget"])
print("pooled:", json.dumps(s["pooled"]))
print("gains:", s["paired_gains_g2_over_g1"], "losses:", s["paired_losses"], "families better:", s["families_g2_better"], "/", s["n_families"])
print("median cpu:", s["median_cpu_s"], "generator coverage:", s["generator_coverage"])
fam = defaultdict(lambda: defaultdict(list))
for t in T:
    f = fam[t["family"]]
    for k in ("g1@1000", "g1@3000", "g2@1000", "g2@3000"):
        f[k + ":p2"].append(t[k]["pass@2"])
        f[k + ":cov"].append(t[k]["correct_coverage"])
        f[k + ":wrong"].append(t[k]["wrong_attempts"])
    f["gen_g1"].append(t["generator_coverage"]["g1"])
    f["gen_g2"].append(t["generator_coverage"]["g2"])
    f["ff"].append(t["g2_first_fit_at"])
    f["cpu1"].append(t["g1_cpu"])
    f["cpu2"].append(t["g2_cpu"])
    f["new"].append(t["g2@3000"]["pass@2"] and not t["g1@3000"]["pass@2"])
    f["lost"].append(t["g1@3000"]["pass@2"] and not t["g2@3000"]["pass@2"])
    r = rows[t["task_id"]]
    f["trunc1"].append(r["g1"]["state"].get("cpu_truncated", False))
    f["trunc2"].append(r["g2"]["state"].get("cpu_truncated", False))
print("\n| family | n | g1 p@2 1000/3000 | g2 p@2 1000/3000 | g2 cov 3000 | new | lost | gen cov g1/g2 | g2 first fit (median; none) | cpu g1/g2 median | trunc g1/g2 | g2 wrong attempts |")
for name, f in fam.items():
    n = len(f["ff"])
    ffs = [x for x in f["ff"] if x is not None]
    print(f"| {name} | {n} | {sum(f['g1@1000:p2'])}/{sum(f['g1@3000:p2'])} | {sum(f['g2@1000:p2'])}/{sum(f['g2@3000:p2'])} | "
          f"{sum(f['g2@3000:cov'])} | {sum(f['new'])} | {sum(f['lost'])} | {sum(f['gen_g1'])}/{sum(f['gen_g2'])} | "
          f"{int(np.median(ffs)) if ffs else '-'}; {n - len(ffs)} | {np.median(f['cpu1']):.1f}/{np.median(f['cpu2']):.1f} | "
          f"{sum(f['trunc1'])}/{sum(f['trunc2'])} | {sum(f['g2@3000:wrong'])} |")
tot1 = sum(r["g1"]["cpu_s"] for r in rows.values())
tot2 = sum(r["g2"]["cpu_s"] for r in rows.values())
print(f"\nCPU total: g1 {tot1:.0f} s, g2 {tot2:.0f} s ({(tot1 + tot2) / 3600:.2f} CPU-h)")
print("hashes:")
for fn in sorted(os.listdir(R)):
    p = f"{R}/{fn}"
    if os.path.isfile(p):
        print(" ", hashlib.sha256(open(p, "rb").read()).hexdigest()[:16], fn)
