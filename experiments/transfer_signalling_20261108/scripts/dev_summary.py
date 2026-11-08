"""Paired development summary: exact held conditions per arm, exact McNemar (conditions, ignoring clustering), and a
paired bootstrap over tasks (clusters) for the difference in exact proportions (u6.stats.Bootstrap, 10,000 resamples).
Arguments: result files; join files with "+" to pool them."""
import json, math, os, sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "universality_boolean_bbm_20261103"))
from u6.stats import Bootstrap, diff_of_ratios  # noqa: E402


def mcnemar(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    p = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * p)


for path in sys.argv[1:]:
    R = [r for part in path.split("+") for r in json.load(open(part))["results"]]
    arms = list(R[0]["arms"])
    tot = {a: sum(h["exact"] for r in R for h in r["arms"][a]["held"].values()) for a in arms}
    n = sum(len(r["arms"]["static"]["held"]) for r in R)
    acc = {a: sum(1 for r in R if r["arms"][a].get("accepted")) for a in ("grown", "shuffled") if a in arms}
    print(f"{os.path.basename(path)} [development] tasks={len(R)} held conditions={n} "
          + " ".join(f"{a}={tot[a]}/{n}" for a in arms) + f" | accepted growth: {acc} of {len(R)} tasks")
    units = [r["task"] for r in R]
    bs = Bootstrap(units)
    for a, b_ in (("grown", "static"), ("grown", "shuffled"), ("shuffled", "static"), ("grown", "classical")):
        if a not in arms or b_ not in arms:
            continue
        b = sum(1 for r in R for k, h in r["arms"][a]["held"].items() if h["exact"] and not r["arms"][b_]["held"][k]["exact"])
        c = sum(1 for r in R for k, h in r["arms"][a]["held"].items() if not h["exact"] and r["arms"][b_]["held"][k]["exact"])
        num1 = {r["task"]: sum(h["exact"] for h in r["arms"][a]["held"].values()) for r in R}
        num2 = {r["task"]: sum(h["exact"] for h in r["arms"][b_]["held"].values()) for r in R}
        den = {r["task"]: len(r["arms"][a]["held"]) for r in R}
        ci = diff_of_ratios(bs, num1, den, num2, den)
        print(f"  {a} vs {b_}: wins {b}, losses {c}, exact McNemar p={mcnemar(b, c):.4f}; difference "
              f"{ci['point']:+.3f}, task-bootstrap 95% CI [{ci['ci95'][0]:+.3f}, {ci['ci95'][1]:+.3f}]")
