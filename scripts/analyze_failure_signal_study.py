"""Analyze the failure-signal study and emit the comparison the directive asks for.

Reports, separately and without merging them:
  * useful recovery within budget, per arm and per family;
  * held-out output correctness on grids never used for fitting;
  * exact AST recovery, kept apart because several programs can explain the
    same demonstrations;
  * cost, including the failure-extraction charge;
  * the paired comparison against unconditioned search, which is the matched
    budget unlearned baseline;
  * whether the shuffled control is distinguishable from the real trace, which
    is what decides if any measured advantage is about THIS task's failures.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--results",
                    default=str(ROOT / "outputs" / "tti" / "failure_signal_study" / "results.json"))
args = parser.parse_args()

data = json.loads(Path(args.results).read_text())
rows = data["rows"]
arms = data["arms"]
by_arm = defaultdict(list)
for row in rows:
    by_arm[row["arm"]].append(row)

episodes = sorted({r["episode"] for r in rows})
print(f"study {data['study_version']} | observer {data['observer_version']}")
print(f"commit {data['git_commit'][:12]} | episodes {len(episodes)} | "
      f"space {data['proposal_space_size']} | budget {data['budget_units_per_condition']}")
print(f"budget rule: {data.get('budget_rule')}")
print()

print("=== PRIMARY: useful recovery within budget ===")
print(f"{'arm':28} {'solved':>7} {'rate':>6} {'heldout_ok':>11} {'exact_ast':>10} "
      f"{'mean_total':>11} {'median_rank':>12}")
for arm in arms:
    s = data["summary"][arm]
    print(f"{arm:28} {s['useful_recovery']:>3}/{s['episodes']:<3} "
          f"{(s['useful_recovery_rate'] or 0):>6.2f} {s['heldout_output_correct']:>11} "
          f"{s['exact_ast_recovered']:>10} {str(s['mean_total_units_when_solved']):>11} "
          f"{str(s['median_rank_of_solution']):>12}")

print("\n=== PAIRED vs unconditioned search (the matched-budget unlearned baseline) ===")
base = {r["episode"]: r for r in by_arm["none"]}
for arm in arms:
    if arm == "none":
        continue
    better = worse = same = 0
    only_arm = only_base = 0
    deltas = []
    for row in by_arm[arm]:
        b = base[row["episode"]]
        if row["solved"] and b["solved"]:
            d = row["total_units"] - b["total_units"]
            deltas.append(d)
            if d < 0:
                better += 1
            elif d > 0:
                worse += 1
            else:
                same += 1
        elif row["solved"] and not b["solved"]:
            only_arm += 1
        elif b["solved"] and not row["solved"]:
            only_base += 1
    median = statistics.median(deltas) if deltas else None
    print(f"{arm:28} cheaper {better:2}  costlier {worse:2}  tied {same:2}  "
          f"solved_only_by_arm {only_arm:2}  solved_only_by_none {only_base:2}  "
          f"median_delta_units {median}")

print("\n=== SHUFFLED CONTROL: is the advantage about THIS task's failures? ===")
for rule in data["ranking_rules"]:
    real = {r["episode"]: r for r in by_arm[f"associated:{rule}"]}
    ctrl = {r["episode"]: r for r in by_arm[f"shuffled:{rule}"]}
    real_solved = sum(1 for r in real.values() if r["solved"])
    ctrl_solved = sum(1 for r in ctrl.values() if r["solved"])
    both = [(real[e], ctrl[e]) for e in real if real[e]["solved"] and ctrl[e]["solved"]]
    delta = [a["total_units"] - b["total_units"] for a, b in both]
    print(f"  rule {rule:14} associated solved {real_solved:2}  shuffled solved {ctrl_solved:2}  "
          f"median delta on both-solved {statistics.median(delta) if delta else None}")

print("\n=== BY FAMILY (solved / episodes) ===")
families = sorted(data["by_family"])
print(f"{'arm':28} " + "".join(f"{f:>9}" for f in families))
for arm in arms:
    cells = []
    for family in families:
        cell = data["by_family"][family][arm]
        cells.append(f"{cell['solved']}/{cell['episodes']}")
    print(f"{arm:28} " + "".join(f"{c:>9}" for c in cells))

print("\n=== COST ACCOUNTING ===")
oc = data["observer_cost"]
print(f"observer runtime, one episode: {oc['observation_seconds_one_episode']} s")
print(f"baseline runtime, one episode: {oc['baseline_seconds_one_episode']} s")
print(f"extraction charged to conditioned arms: {data['summary']['aggregate']['extraction_units']} units")
print(f"observer field coverage: {json.dumps(oc['coverage_report'])}")
print(f"total study wall clock: {data['total_seconds']} s")

print("\n=== EXACT AST RECOVERY, REPORTED SEPARATELY ===")
for arm in arms:
    solved = [r for r in by_arm[arm] if r["solved"]]
    exact = [r for r in solved if r["exact_ast_recovered"]]
    ho = [r for r in solved if r["heldout_correct"]]
    print(f"{arm:28} solved {len(solved):2}  heldout_correct {len(ho):2}  "
          f"exact_ast {len(exact):2}  "
          f"(a solved program that generalizes need not be the generator's schema)")

print("\n=== SANITY ===")
print("episodes where the baseline itself solved the task:",
      sum(1 for r in by_arm['none'] if r['baseline_solved_it']))
print("episodes where the baseline was incomplete:",
      sum(1 for r in by_arm['none'] if not r['baseline_complete']))
print("distinct found programs across arms:",
      len({r['found_digest'] for r in rows if r.get('found_digest')}))
