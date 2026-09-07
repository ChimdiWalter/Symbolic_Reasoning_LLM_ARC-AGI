"""Complete paired analysis of the finished failure-signal study.

Reads the saved result only. It runs no episode, changes no ranking rule, and
never reruns the measurement.
"""
from __future__ import annotations

import glob
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "src")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from geocat_arc.object_reasoning import meta_ast as M            # noqa: E402
from cora_tti import constructive_dataset as CD                  # noqa: E402
from cora_tti import constructive_vocabulary as CV               # noqa: E402
from cora_tti import failure_signal_study as FS                  # noqa: E402

RESULTS = ROOT / "outputs" / "tti" / "failure_signal_study" / "results.json"
data = json.loads(RESULTS.read_text())
rows = data["rows"]
arms = data["arms"]
by_arm = defaultdict(dict)
for row in rows:
    by_arm[row["arm"]][row["episode"]] = row
episodes = sorted({r["episode"] for r in rows})
n = len(episodes)

out = {"episodes": n, "arms": arms}

# -------------------------------------------------- episode population ----
pop = {}
ep_meta = {}
for e in episodes:
    row = by_arm["none"][e]
    family = tuple(int(x) for x in row["family"].strip("()").split(",") if x != "")
    schema = CD.sample_target(row["seed"], family)
    ep_meta[e] = {"seed": row["seed"], "family": row["family"],
                  "target_digest": CV.digest(schema),
                  "baseline_solved_it": row["baseline_solved_it"],
                  "baseline_complete": row["baseline_complete"]}
pop["baseline_solved_the_episode"] = [e for e in episodes if ep_meta[e]["baseline_solved_it"]]
pop["baseline_completed_and_failed"] = [e for e in episodes
                                        if not ep_meta[e]["baseline_solved_it"]
                                        and ep_meta[e]["baseline_complete"]]
pop["baseline_incomplete"] = [e for e in episodes if not ep_meta[e]["baseline_complete"]]

#  overlap with development evidence: the development namespace and the v2c census
dev_digests = set()
for family_index, family in enumerate(FS.STUDY_FAMILIES):
    for attempt in range(400):
        seed = 6_100_000 + attempt * 7919
        dev_digests.add(CV.digest(CD.sample_target(seed, family)))
census_digests = set()
for path in glob.glob(str(ROOT / "outputs" / "tti" / "constructive_v2_corrected"
                          / "admitted" / "*.json")):
    census_digests.add(json.loads(Path(path).read_text())["target_digest"])
eval_digests = {ep_meta[e]["target_digest"] for e in episodes}
pop["evaluation_target_digests"] = len(eval_digests)
pop["distinct_evaluation_targets"] = len(eval_digests)
pop["overlap_with_development_namespace"] = sorted(
    e for e in episodes if ep_meta[e]["target_digest"] in dev_digests)
pop["overlap_with_v2c_census_admitted"] = sorted(
    e for e in episodes if ep_meta[e]["target_digest"] in census_digests)
pop["conditions_enforced_by_build_episode"] = [
    "the sampled target instantiates (concrete tables derivable)",
    "at least 3 demonstrations render, defined and non-trivial",
    "the target itself fits exactly under the scoped fitter",
    "at least 4 held-out grids render defined and non-trivial outputs",
]
pop["conditions_NOT_enforced_by_build_episode"] = [
    "the single-block baseline must fail (recorded per episode, not required)",
    "local irreducibility of the target",
    "historical exclusion against the v1.1 attempted set",
    "run-wide duplicate exclusion",
    "frozen-probe coverage floor",
    "witness separation",
]
out["population"] = pop

# ------------------------------------------------------ paired outcomes ----
def block(subset, label):
    res = {}
    base = by_arm["none"]
    for arm in arms:
        r = [by_arm[arm][e] for e in subset]
        fits = [x for x in r if x["solved"]]
        ho = [x for x in fits if x["heldout_correct"]]
        undefined = [x for x in fits
                     if x["heldout_defined"] is not None
                     and x["heldout_defined"] < x["heldout_total"]]
        exact = [x for x in fits if x["exact_ast_recovered"]]
        wins = losses = ties = only_arm = only_base = 0
        deltas = []
        for e in subset:
            a, b = by_arm[arm][e], base[e]
            if a["solved"] and b["solved"]:
                d = a["total_units"] - b["total_units"]
                deltas.append(d)
                wins += d < 0
                losses += d > 0
                ties += d == 0
            elif a["solved"]:
                only_arm += 1
            elif b["solved"]:
                only_base += 1
        res[arm] = {
            "episodes": len(subset),
            "DEMONSTRATION_FIT_FOUND": len(fits),
            "HELDOUT_OUTPUT_SUCCESS": len(ho),
            "heldout_success_over_all_episodes": f"{len(ho)}/{len(subset)}",
            "fits_with_undefined_heldout_predictions": len(undefined),
            "exact_ast_recovered": len(exact),
            "budget_exhausted_episodes": len(subset) - len(fits),
            "total_units_all_episodes": sum(x["total_units"] for x in r),
            "mean_units_all_episodes": round(sum(x["total_units"] for x in r) / len(r), 1),
            "mean_units_when_fit_found": (round(sum(x["total_units"] for x in fits) / len(fits), 1)
                                          if fits else None),
            "vs_none_cheaper": wins, "vs_none_costlier": losses, "vs_none_tied": ties,
            "vs_none_fit_only_by_arm": only_arm, "vs_none_fit_only_by_none": only_base,
            "vs_none_median_delta_units": statistics.median(deltas) if deltas else None,
        }
    return {"label": label, "episode_ids": list(subset), "arms": res}


out["all_episodes"] = block(episodes, "all 24 episodes")
out["baseline_failed_subset"] = block(pop["baseline_completed_and_failed"],
                                      "EXPLORATORY SUBGROUP: episodes where the "
                                      "single-block baseline completed and failed")

# --------------------------------------------- real trace versus control ----
control = {}
for rule in data["ranking_rules"]:
    real, ctrl = by_arm[f"associated:{rule}"], by_arm[f"shuffled:{rule}"]
    both = [e for e in episodes if real[e]["solved"] and ctrl[e]["solved"]]
    real_only = [e for e in episodes if real[e]["solved"] and not ctrl[e]["solved"]]
    ctrl_only = [e for e in episodes if ctrl[e]["solved"] and not real[e]["solved"]]
    control[rule] = {
        "real_fits": sum(1 for e in episodes if real[e]["solved"]),
        "shuffled_fits": sum(1 for e in episodes if ctrl[e]["solved"]),
        "real_heldout": sum(1 for e in episodes if real[e]["heldout_correct"]),
        "shuffled_heldout": sum(1 for e in episodes if ctrl[e]["heldout_correct"]),
        "fit_by_real_only": real_only, "fit_by_shuffled_only": ctrl_only,
        "both": both,
        "median_delta_units_when_both": (
            statistics.median([real[e]["total_units"] - ctrl[e]["total_units"] for e in both])
            if both else None)}
out["real_versus_shuffled"] = control

# ------------------------------------------------------------ per family ----
per_family = defaultdict(dict)
for family in sorted({ep_meta[e]["family"] for e in episodes}):
    eps = [e for e in episodes if ep_meta[e]["family"] == family]
    for arm in arms:
        r = [by_arm[arm][e] for e in eps]
        per_family[family][arm] = {
            "episodes": len(eps),
            "fits": sum(1 for x in r if x["solved"]),
            "heldout": sum(1 for x in r if x["heldout_correct"])}
out["per_family"] = {k: dict(v) for k, v in per_family.items()}

# ------------------------------------------------ the found programs ----
found = {}
for e in episodes:
    entry = {}
    for arm in arms:
        row = by_arm[arm][e]
        if not row["solved"]:
            continue
        schema = M.ast_from_json(row["found_schema_json"])
        entry[arm] = {
            "found_family": CV.family_text(CV.family(schema)),
            "found_digest": row["found_digest"][:16],
            "is_generator_schema": row["exact_ast_recovered"],
            "rank": row["rank_of_solution"],
            "search_units": row["units_used"],
            "extraction_units": row["extraction_units"],
            "total_units": row["total_units"],
            "heldout_correct": row["heldout_correct"],
            "heldout_defined": f"{row['heldout_defined']}/{row['heldout_total']}",
            "seconds_excluding_baseline": round(row["seconds"], 2)}
    found[e] = {"target_family": ep_meta[e]["family"],
                "target_digest": ep_meta[e]["target_digest"][:16],
                "baseline_solved_it": ep_meta[e]["baseline_solved_it"],
                "arms": entry}
out["per_episode_found_programs"] = found

# ---------------------------------------------------- oracle union note ----
union = [e for e in episodes if any(by_arm[a][e]["solved"] for a in arms)]
union_ho = [e for e in episodes if any(by_arm[a][e]["heldout_correct"] for a in arms)]
out["oracle_union"] = {
    "episodes_fit_by_at_least_one_arm": len(union),
    "episodes_heldout_correct_by_at_least_one_arm": len(union_ho),
    "warning": ("this is an ORACLE UNION over separately budgeted arms. It is not a "
                "deployable system score: a real portfolio must fix its allocation "
                "without knowing which arm will succeed, and would divide one budget "
                "rather than give each arm a full one")}

# -------------------------------------------------------------- costs ----
out["cost_interpretation"] = {
    "budget_unit": "one candidate fit attempt; NOT wall clock",
    "extraction_charged_units": 200,
    "single_vs_two_block_fit_cost": ("one baseline fit is single-block and one proposal "
                                     "fit is two-block; they are counted as one unit each "
                                     "and are NOT established to cost the same"),
    "seconds_field_excludes_baseline": True,
    "seconds_field_note": ("run_condition.seconds measures ranking, fitting and held-out "
                           "scoring inside that call. The baseline trace was computed "
                           "BEFORE the call, so its execution time is not included and "
                           "must not be read as end-to-end cost"),
    "observer_seconds_one_episode": data["observer_cost"]["observation_seconds_one_episode"],
    "baseline_seconds_one_episode": data["observer_cost"]["baseline_seconds_one_episode"],
    "incremental_vs_complete": ("if the parent solver has already run the baseline, the "
                                "incremental cost of reusing its trace is the observer's "
                                "parse alone. If it has not, the complete-pipeline cost "
                                "includes the whole baseline enumeration"),
    "ranking_cost_note": ("every conditioned arm ranks the full 57600-candidate space "
                          "before its first fit; that sort is inside seconds but is not "
                          "charged in fit units"),
    "total_study_wall_clock_seconds": data["total_seconds"],
}

text = json.dumps(out, indent=1, sort_keys=True, default=str)
target = ROOT / "outputs" / "tti" / "failure_signal_study" / "final_analysis.json"
target.write_text(text)

#  ---- console summary ----
print("=== POPULATION ===")
print("episodes:", n, "| distinct target digests:", pop["distinct_evaluation_targets"])
print("baseline solved the episode:", pop["baseline_solved_the_episode"])
print("baseline completed and failed:", len(pop["baseline_completed_and_failed"]), "episodes")
print("overlap with development namespace:", pop["overlap_with_development_namespace"])
print("overlap with v2c census admitted:", pop["overlap_with_v2c_census_admitted"])
print()
for label, key in (("ALL 24 EPISODES", "all_episodes"),
                   ("SUBGROUP: baseline completed and failed", "baseline_failed_subset")):
    b = out[key]
    print(f"=== {label} (n={len(b['episode_ids'])}) ===")
    print(f"{'arm':28}{'fit':>6}{'heldout':>9}{'undef':>7}{'exactAST':>9}"
          f"{'exhaust':>9}{'meanUnitsAll':>14}{'vs none +/-':>13}")
    for arm in arms:
        a = b["arms"][arm]
        print(f"{arm:28}{a['DEMONSTRATION_FIT_FOUND']:>6}{a['HELDOUT_OUTPUT_SUCCESS']:>9}"
              f"{a['fits_with_undefined_heldout_predictions']:>7}{a['exact_ast_recovered']:>9}"
              f"{a['budget_exhausted_episodes']:>9}{a['mean_units_all_episodes']:>14}"
              f"{str(a['vs_none_fit_only_by_arm']) + '/' + str(a['vs_none_fit_only_by_none']):>13}")
    print()
print("=== REAL vs SHUFFLED ===")
for rule, c in control.items():
    print(f"  {rule:14} real fits {c['real_fits']:2} (heldout {c['real_heldout']:2})  "
          f"shuffled fits {c['shuffled_fits']:2} (heldout {c['shuffled_heldout']:2})  "
          f"real-only {c['fit_by_real_only']}  shuffled-only {c['fit_by_shuffled_only']}")
print()
print("=== EPISODE 18 ===")
print(json.dumps(found[18], indent=1))
print()
print("=== ORACLE UNION ===")
print(json.dumps(out["oracle_union"], indent=1))
print("\nwritten:", target)
