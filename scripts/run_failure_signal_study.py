"""Run the bounded failure-signal study and write its result.

Episodes come from a FRESH seed namespace, disjoint from the corrected census
and from the 13 inspected examples, which remain development evidence only.

Every condition gets the same total budget in candidate-fit units, and the
failure-extraction cost is charged to the conditions that use it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "src")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from cora_tti import candidate_trace as CT                       # noqa: E402
from cora_tti import failure_signal_study as FS                  # noqa: E402
from cora_tti import meta_baseline as MB                         # noqa: E402
from cora_tti import constructive_vocabulary as CV               # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument("--seed-namespace", type=int, default=6_500_000,
                    help="EVALUATION namespace; 6_100_000 was the development one")
parser.add_argument("--episodes-per-family", type=int, default=6)
parser.add_argument("--budget-units", type=int, default=2880)
parser.add_argument("--out", default=str(ROOT / "outputs" / "tti" / "failure_signal_study"))
args = parser.parse_args()

OUT = Path(args.out)
OUT.mkdir(parents=True, exist_ok=True)
CONFIG = MB.BaselineConfig()


def git_head() -> str:
    try:
        return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.strip()
    except Exception:                                             # noqa: BLE001
        return "UNKNOWN"


#  ---- fresh episodes, built before any measurement ----
print("building fresh episodes...", flush=True)
episodes = []
for family_index, family in enumerate(FS.STUDY_FAMILIES):
    found, attempt = 0, 0
    while found < args.episodes_per_family and attempt < 4000:
        seed = args.seed_namespace + family_index * 3_000_017 + attempt * 7919
        attempt += 1
        episode = FS.build_episode(seed, family)
        if episode is None:
            continue
        episodes.append(episode)
        found += 1
    print(f"  {CV.family_text(family)}: {found} episodes after {attempt} attempts", flush=True)

if not episodes:
    raise SystemExit("no episodes could be built")

#  a fixed proposal space, identical for every condition and episode
space = FS.proposal_space()
print(f"proposal space: {len(space)} two-block candidates", flush=True)
print(f"episodes: {len(episodes)} | budget: {args.budget_units} units/condition", flush=True)

#  ---- run every condition on every episode ----
rows = []
traces = {}
started_all = time.perf_counter()
for index, episode in enumerate(episodes):
    trace = MB.run_baseline(episode.pairs, CONFIG)
    traces[index] = trace
for index, episode in enumerate(episodes):
    trace = traces[index]
    #  the shuffled control uses the NEXT episode's trace: same shape, same cost,
    #  wrong task. Deterministic, so the control is reproducible.
    other = traces[(index + 1) % len(episodes)]
    for condition in FS.CONDITIONS:
        rules = (FS.RANKING_RULES if condition in ("associated", "shuffled")
                 else ("individual",))
        for rule in rules:
            result = FS.run_condition(
                condition, episode.pairs, trace, args.budget_units,
                episode.target_digest, episode.heldout,
                other_trace=other if condition == "shuffled" else None,
                candidates=space, rule=rule)
            row = {"episode": index, "seed": episode.seed,
                   "family": CV.family_text(episode.family),
                   "arm": f"{condition}:{rule}" if condition in ("associated", "shuffled")
                          else condition,
                   "baseline_solved_it": bool(trace.exact),
                   "baseline_complete": trace.complete(),
                   **{k: v for k, v in result.__dict__.items()}}
            rows.append(row)
    done = [r for r in rows if r["episode"] == index]
    print(f"  ep{index:02d} {CV.family_text(episode.family)} "
          + " ".join(f"{r['arm']}={'Y' if r['solved'] else 'n'}"
                     f"/{r['total_units']}" for r in done), flush=True)

#  ---- summarize ----
ARMS = ["none", "aggregate", "associated:individual", "associated:complementary",
        "shuffled:individual", "shuffled:complementary"]
summary = {}
for condition in ARMS:
    crows = [r for r in rows if r["arm"] == condition]
    solved = [r for r in crows if r["solved"]]
    heldout_ok = [r for r in solved if r["heldout_correct"]]
    exact_ast = [r for r in solved if r["exact_ast_recovered"]]
    summary[condition] = {
        "episodes": len(crows),
        "useful_recovery": len(solved),
        "useful_recovery_rate": round(len(solved) / len(crows), 4) if crows else None,
        "heldout_output_correct": len(heldout_ok),
        "heldout_correct_rate_of_solved": (round(len(heldout_ok) / len(solved), 4)
                                           if solved else None),
        "exact_ast_recovered": len(exact_ast),
        "exact_ast_rate_of_solved": (round(len(exact_ast) / len(solved), 4)
                                     if solved else None),
        "median_total_units_when_solved": (
            sorted(r["total_units"] for r in solved)[len(solved) // 2] if solved else None),
        "mean_total_units_when_solved": (
            round(sum(r["total_units"] for r in solved) / len(solved), 1) if solved else None),
        "mean_search_units_when_solved": (
            round(sum(r["units_used"] for r in solved) / len(solved), 1) if solved else None),
        "extraction_units": crows[0]["extraction_units"] if crows else None,
        "median_rank_of_solution": (
            sorted(r["rank_of_solution"] for r in solved)[len(solved) // 2] if solved else None),
        "total_seconds": round(sum(r["seconds"] for r in crows), 2),
    }

by_family = defaultdict(dict)
for condition in ARMS:
    for family in FS.STUDY_FAMILIES:
        text = CV.family_text(family)
        frows = [r for r in rows if r["arm"] == condition and r["family"] == text]
        by_family[text][condition] = {
            "episodes": len(frows),
            "solved": sum(1 for r in frows if r["solved"]),
            "heldout_correct": sum(1 for r in frows if r["heldout_correct"])}

#  observer cost accounting, measured on one episode
sample_trace = traces[0]
observed = CT.observe(sample_trace)
report = {
    "study_version": FS.STUDY_VERSION,
    "observer_version": CT.OBSERVER_VERSION,
    "git_commit": git_head(),
    "code_hash": FS.study_code_hash(),
    "baseline_config_digest": CONFIG.digest(),
    "environment": {"PYTHONHASHSEED": os.environ.get("PYTHONHASHSEED"),
                    "python": platform.python_version()},
    "seed_namespace": args.seed_namespace,
    "episodes": len(episodes),
    "episodes_per_family_requested": args.episodes_per_family,
    "proposal_space_size": len(space),
    "budget_units_per_condition": args.budget_units,
    "budget_note": ("one unit is one candidate fit attempt; the failure-extraction "
                    "cost (the baseline's 200 hypotheses) is charged to every "
                    "condition that reads a failure representation"),
    "budget_rule": ("declared BEFORE any measurement: 5 per cent of the 57600-candidate "
                    "proposal space, i.e. 2880 units, identical for every condition"),
    "conditions": list(FS.CONDITIONS),
    "arms": ARMS,
    "ranking_rules": list(FS.RANKING_RULES),
    "development_namespace": 6100000,
    "summary": summary,
    "by_family": {k: dict(v) for k, v in by_family.items()},
    "observer_cost": {
        "observation_seconds_one_episode": round(observed.observation_seconds, 5),
        "baseline_seconds_one_episode": round(sample_trace.seconds, 3),
        "coverage_report": observed.coverage_report()},
    "data_access": {
        "proposer_receives": ["demonstrations", "the constructive grammar",
                              "the condition's failure representation"],
        "proposer_never_receives": ["target schema", "target tables", "target digest",
                                    "family label", "generator metadata",
                                    "held-out grids"],
        "scoring_only": ["target_digest for exact-AST reporting",
                         "held-out grids for output correctness"]},
    "total_seconds": round(time.perf_counter() - started_all, 1),
    "rows": rows,
}
text = json.dumps(report, indent=1, sort_keys=True, default=str)
(OUT / "results.json").write_text(text)
(OUT / "results_hash.txt").write_text(hashlib.sha256(text.encode()).hexdigest() + "\n")

print("\n=== SUMMARY ===")
for condition in ARMS:
    s = summary[condition]
    print(f"{condition:26} solved {s['useful_recovery']:2}/{s['episodes']:2}  "
          f"heldout_ok {s['heldout_output_correct']:2}  exact_ast {s['exact_ast_recovered']:2}  "
          f"mean_total_units {s['mean_total_units_when_solved']}  "
          f"median_rank {s['median_rank_of_solution']}")
print("\nsha256:", hashlib.sha256(text.encode()).hexdigest())
print("STUDY_DONE")
