"""Prospective abstraction-transfer experiment.

EVERYTHING BELOW IS PINNED BEFORE ANY TRANSFER OUTCOME IS OBSERVED.

Pools, disjoint namespaces, built before measurement
    SOURCE    namespace 8_100_000, 4 episodes per family, 16 total
    TRANSFER  namespace 8_900_000, 6 episodes per family, 24 total
    The 24 episodes of the earlier study, and every episode inspected before
    today, are development evidence and appear in neither pool.

Acquisition policy, ONE fixed policy
    Ordinary constructive search: smallest-first over the fixed 57600-candidate
    two-block enumeration, budget 2880 candidate fits per source episode.
    EVERY source search is charged, successful or not. Failure-guided ranking is
    deliberately not used, because the completed study found it was not superior
    overall; using ordinary search here therefore establishes nothing about
    failure conditioning.

Abstraction rules, BOTH declared in advance and BOTH measured
    R1  group discovered structures by structural family, anti-unify all members
    R2  group by (structural family, partition of block 0), anti-unify members
    R1 was observed on DEVELOPMENT evidence, before this run and before any
    transfer outcome, to generalize every terminal position and so to expand to
    the whole family subspace, making its concept identical to the unlearned
    control. That observation is a source-side property, not a transfer outcome.
    R1 is retained and reported rather than dropped.

Target-time policies, common budget of 3000 candidate fits
    A  ordinary search alone
    B  concrete library first, then ordinary search with the remainder
    C  learned concepts first, then ordinary search with the remainder
    D  unlearned control concepts first, then ordinary search with the remainder
    Same fitter, executor, acceptance rule and output selection throughout.
    Every fit is charged, including failed lookups. Already attempted programs
    are never re-attempted. A concept costs one unit per enumerable binding.
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

from geocat_arc.object_reasoning import meta_ast as M            # noqa: E402
from cora_tti import abstraction_transfer as AT                  # noqa: E402
from cora_tti import constructive_vocabulary as CV               # noqa: E402
from cora_tti import failure_signal_study as FS                  # noqa: E402
from cora_tti import meta_baseline as MB                         # noqa: E402
from cora_tti import scoped_slot_fitting as SF                   # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument("--source-namespace", type=int, default=8_100_000)
parser.add_argument("--transfer-namespace", type=int, default=8_900_000)
parser.add_argument("--source-per-family", type=int, default=4)
parser.add_argument("--transfer-per-family", type=int, default=6)
parser.add_argument("--acquisition-budget", type=int, default=2880)
parser.add_argument("--target-budget", type=int, default=3000)
parser.add_argument("--out", default=str(ROOT / "outputs" / "tti" / "abstraction_transfer"))
args = parser.parse_args()

OUT = Path(args.out)
OUT.mkdir(parents=True, exist_ok=True)
CONFIG = MB.BaselineConfig()
SPACE = FS.proposal_space()


def git_head() -> str:
    try:
        return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.strip()
    except Exception:                                             # noqa: BLE001
        return "UNKNOWN"


def build_pool(namespace: int, per_family: int, label: str) -> list:
    pool = []
    for family_index, family in enumerate(FS.STUDY_FAMILIES):
        found, attempt = 0, 0
        while found < per_family and attempt < 6000:
            seed = namespace + family_index * 3_000_017 + attempt * 7919
            attempt += 1
            episode = FS.build_episode(seed, family)
            if episode is None:
                continue
            pool.append(episode)
            found += 1
        print(f"  {label} {CV.family_text(family)}: {found}/{per_family} "
              f"after {attempt} attempts", flush=True)
    return pool


print("building pools (before any measurement)...", flush=True)
SOURCE = build_pool(args.source_namespace, args.source_per_family, "source")
TRANSFER = build_pool(args.transfer_namespace, args.transfer_per_family, "transfer")
source_digests = {e.target_digest for e in SOURCE}
transfer_digests = {e.target_digest for e in TRANSFER}
overlap = sorted(source_digests & transfer_digests)
print(f"source {len(SOURCE)} | transfer {len(TRANSFER)} | "
      f"identity overlap {len(overlap)}", flush=True)

# --------------------------------------------------------------------------
# acquisition: ONE policy, every search charged
# --------------------------------------------------------------------------
print("\nacquisition (ordinary constructive search on each source episode)...", flush=True)
acquisition = []
acq_units_total = 0
acq_started = time.perf_counter()
for index, episode in enumerate(SOURCE):
    baseline = MB.run_baseline(episode.pairs, CONFIG)
    used, found = 0, None
    for candidate in SPACE:
        if used >= args.acquisition_budget:
            break
        used += 1
        outcome = SF.fit_outcome(FS.schema_of(candidate), episode.pairs,
                                 require_exact_replay=True)
        if outcome["status"] == "EXACT_DEMONSTRATION_FIT":
            found = FS.schema_of(candidate)
            break
    acq_units_total += used
    blocks = CV.blocks_from_ast(found) if found is not None else None
    acquisition.append({
        "source_index": index, "seed": episode.seed,
        "family": CV.family_text(episode.family),
        "baseline_solved_it": bool(baseline.exact),
        "baseline_complete": baseline.complete(),
        "search_units": used, "discovered": found is not None,
        "structure_digest": CV.digest(CV.ast_from_blocks(blocks)) if blocks else None,
        "structure_family": CV.family_text(CV.family(CV.ast_from_blocks(blocks))) if blocks else None,
        "blocks": [[p, list(s), f] for p, s, f in blocks] if blocks else None,
    })
    print(f"  src{index:02d} {CV.family_text(episode.family):6} "
          f"{'found' if found is not None else 'FAILED':6} {used:5}u", flush=True)
acq_seconds = time.perf_counter() - acq_started
discovered = [a for a in acquisition if a["discovered"]]
print(f"acquisition: {len(discovered)}/{len(SOURCE)} discovered, "
      f"{acq_units_total} units charged in total", flush=True)

# --------------------------------------------------------------------------
# concrete library and the two declared abstraction rules
# --------------------------------------------------------------------------
concrete = {}
for row in discovered:
    schema = CV.ast_from_blocks([(b[0], tuple(b[1]), b[2]) for b in row["blocks"]])
    concrete.setdefault(row["structure_digest"], {
        "digest": row["structure_digest"], "schema": schema,
        "structure_family": row["structure_family"], "sources": []})
    concrete[row["structure_digest"]]["sources"].append(row["source_index"])
CONCRETE = sorted(concrete.values(), key=lambda e: e["digest"])
print(f"\nconcrete library: {len(CONCRETE)} distinct structures", flush=True)


def group_R1(entries) -> dict:
    groups = defaultdict(list)
    for entry in entries:
        groups[entry["structure_family"]].append(entry)
    return groups


def group_R2(entries) -> dict:
    groups = defaultdict(list)
    for entry in entries:
        blocks = CV.blocks_from_ast(entry["schema"])
        groups[(entry["structure_family"], blocks[0][0])].append(entry)
    return groups


CONCEPTS = {}
for rule_name, grouper in (("R1_family", group_R1), ("R2_family_and_first_partition", group_R2)):
    built = []
    for key, entries in sorted(grouper(CONCRETE).items(), key=lambda kv: str(kv[0])):
        concept = AT.abstract_group(
            f"{rule_name}:{key}", [e["schema"] for e in entries],
            tuple(sorted({s for e in entries for s in e["sources"]})))
        if concept is not None:
            built.append(concept)
    CONCEPTS[rule_name] = built
    print(f"{rule_name}: {len(built)} concepts, expansions "
          f"{[c.expansion() for c in built]}", flush=True)

CONTROLS = {rule: [AT.control_concept(c, f"ctrl:{c.name}") for c in concepts]
            for rule, concepts in CONCEPTS.items()}
for rule in CONTROLS:
    identical = sum(1 for a, b in zip(CONCEPTS[rule], CONTROLS[rule])
                    if CV.canonical(a.schema) == CV.canonical(b.schema))
    print(f"{rule}: control concepts identical to learned: {identical}/{len(CONTROLS[rule])}",
          flush=True)

#  ---- freeze the libraries BEFORE any transfer outcome is opened ----
frozen = {
    "concrete": [{k: v for k, v in e.items() if k != "schema"} |
                 {"canonical": CV.canonical(e["schema"])} for e in CONCRETE],
    "concepts": {rule: [c.to_json() for c in concepts] for rule, concepts in CONCEPTS.items()},
    "controls": {rule: [c.to_json() for c in controls] for rule, controls in CONTROLS.items()},
}
frozen_text = json.dumps(frozen, indent=1, sort_keys=True)
(OUT / "frozen_libraries.json").write_text(frozen_text)
frozen_hash = hashlib.sha256(frozen_text.encode()).hexdigest()
(OUT / "frozen_libraries_hash.txt").write_text(frozen_hash + "\n")
print(f"\nlibraries FROZEN, sha256 {frozen_hash[:16]}", flush=True)

# --------------------------------------------------------------------------
# transfer
# --------------------------------------------------------------------------
print("\ntransfer...", flush=True)
rows = []
transfer_started = time.perf_counter()
for index, episode in enumerate(TRANSFER):
    baseline = MB.run_baseline(episode.pairs, CONFIG)
    arms = [("A_ordinary", None, None)]
    arms.append(("B_concrete_then_ordinary", CONCRETE, None))
    for rule in CONCEPTS:
        arms.append((f"C_concepts_then_ordinary[{rule}]", None, CONCEPTS[rule]))
        arms.append((f"D_control_then_ordinary[{rule}]", None, CONTROLS[rule]))
    for name, library, concepts in arms:
        policy = ("A_ordinary" if name.startswith("A") else
                  "B_concrete_then_ordinary" if name.startswith("B") else
                  "C_concepts_then_ordinary" if name.startswith("C") else
                  "D_control_then_ordinary")
        result = AT.run_policy(policy, episode, args.target_budget,
                               library or [], concepts or [], SPACE)
        rows.append({"transfer_index": index, "seed": episode.seed,
                     "family": CV.family_text(episode.family),
                     "arm": name,
                     "baseline_solved_it": bool(baseline.exact),
                     "baseline_complete": baseline.complete(),
                     "target_digest": episode.target_digest, **result})
    done = [r for r in rows if r["transfer_index"] == index]
    print(f"  tgt{index:02d} {CV.family_text(episode.family):6} "
          + " ".join(f"{r['arm'].split('_')[0]}{'Y' if r['solved'] else 'n'}/{r['units']}"
                     for r in done), flush=True)
transfer_seconds = time.perf_counter() - transfer_started

# --------------------------------------------------------------------------
# summary
# --------------------------------------------------------------------------
ARMS = sorted({r["arm"] for r in rows})
summary = {}
for arm in ARMS:
    arm_rows = [r for r in rows if r["arm"] == arm]
    fits = [r for r in arm_rows if r["solved"]]
    summary[arm] = {
        "episodes": len(arm_rows),
        "demonstration_fits": len(fits),
        "heldout_output_success": sum(1 for r in fits if r.get("heldout_correct")),
        "undefined_heldout": sum(1 for r in fits
                                 if r.get("heldout_defined") is not None
                                 and r["heldout_defined"] < r["heldout_total"]),
        "exact_ast_recovered": sum(1 for r in fits if r.get("exact_ast_recovered")),
        "solved_in_prior_phase": sum(1 for r in fits if r["phase"] == "prior"),
        "solved_in_fallback": sum(1 for r in fits if r["phase"] == "fallback"),
        "mean_units_all_episodes": round(sum(r["units"] for r in arm_rows) / len(arm_rows), 1),
        "total_units_all_episodes": sum(r["units"] for r in arm_rows),
        "mean_prior_units": round(sum(r["prior_units"] for r in arm_rows) / len(arm_rows), 1),
        "budget_exhausted": sum(1 for r in arm_rows if not r["solved"]),
        "total_seconds": round(sum(r["seconds"] for r in arm_rows), 1),
    }

report = {
    "experiment_version": AT.EXPERIMENT_VERSION,
    "git_commit": git_head(), "code_hash": AT.experiment_code_hash(),
    "environment": {"PYTHONHASHSEED": os.environ.get("PYTHONHASHSEED"),
                    "python": platform.python_version()},
    "pinned_before_measurement": {
        "source_namespace": args.source_namespace,
        "transfer_namespace": args.transfer_namespace,
        "source_per_family": args.source_per_family,
        "transfer_per_family": args.transfer_per_family,
        "acquisition_budget_units": args.acquisition_budget,
        "target_budget_units": args.target_budget,
        "acquisition_policy": "ordinary constructive search, smallest-first, all searches charged",
        "abstraction_rules": ["R1_family", "R2_family_and_first_partition"],
        "proposal_space": len(SPACE)},
    "pools": {"source_episodes": len(SOURCE), "transfer_episodes": len(TRANSFER),
              "source_target_digests": len(source_digests),
              "transfer_target_digests": len(transfer_digests),
              "identity_overlap_between_pools": len(overlap),
              "overlap_digests": [d[:16] for d in overlap]},
    "acquisition": {
        "episodes": len(SOURCE), "discovered": len(discovered),
        "failed_searches": len(SOURCE) - len(discovered),
        "units_charged_total": acq_units_total,
        "units_charged_on_failures": sum(a["search_units"] for a in acquisition
                                         if not a["discovered"]),
        "seconds": round(acq_seconds, 1),
        "concrete_library_size": len(CONCRETE),
        "per_source": acquisition},
    "libraries": {"frozen_sha256": frozen_hash,
                  "concrete": len(CONCRETE),
                  "concepts": {r: [c.to_json() for c in cs] for r, cs in CONCEPTS.items()},
                  "controls_identical_to_learned": {
                      r: sum(1 for a, b in zip(CONCEPTS[r], CONTROLS[r])
                             if CV.canonical(a.schema) == CV.canonical(b.schema))
                      for r in CONCEPTS}},
    "summary": summary,
    "transfer_seconds": round(transfer_seconds, 1),
    "rows": rows,
}
text = json.dumps(report, indent=1, sort_keys=True, default=str)
(OUT / "results.json").write_text(text)
(OUT / "results_hash.txt").write_text(hashlib.sha256(text.encode()).hexdigest() + "\n")

print("\n=== SUMMARY ===")
print(f"{'arm':44}{'fit':>5}{'heldout':>9}{'exactAST':>10}{'prior':>7}{'fallback':>10}{'meanUnits':>11}")
for arm in ARMS:
    s = summary[arm]
    print(f"{arm:44}{s['demonstration_fits']:>5}{s['heldout_output_success']:>9}"
          f"{s['exact_ast_recovered']:>10}{s['solved_in_prior_phase']:>7}"
          f"{s['solved_in_fallback']:>10}{s['mean_units_all_episodes']:>11}")
print("\nsha256:", hashlib.sha256(text.encode()).hexdigest())
print("ABSTRACTION_TRANSFER_DONE")
