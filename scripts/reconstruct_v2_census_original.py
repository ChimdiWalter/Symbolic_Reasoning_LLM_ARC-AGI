"""Reconstruct the ORIGINAL protocol-v2 feasibility census attempt by attempt.

Evidence-closure directive, sections 4 and 10. The original runner
(cora_tti/constructive_v2_feasibility.py at commit e5ef8b5) retained only
per-family outcome counts and two example summaries per family. This script
re-executes the same deterministic procedure under the PINNED code snapshot
and retains, for every one of the 840 attempts, the attempt identity, the
canonical schema identity, the terminal outcome and the recorded evidence,
plus the complete episode for every admitted attempt.

Labelling discipline
    * Every identity produced here is RECONSTRUCTED_FROM_PINNED_GENERATOR.
      No original per-attempt log existed; nothing here is a recovered log.
    * The original procedure is reproduced AS EXECUTED, including its inert
      guards (fresh empty seen/exclusion sets on every attempt). Uniqueness
      and historical overlap are analysed OFFLINE from the reconstructed
      identities; the admission procedure itself is not altered.
    * Outcomes can differ from the original counts wherever the original
      procedure depended on wall-clock deadlines (the 2 s blind-runtime TFG
      budget and the 120 s per-target budget). Differences are reported per
      family; a family whose counts differ is marked UNVERIFIED for any
      claim that depends on the attempt-level outcome.

Usage
    python3 scripts/reconstruct_v2_census_original.py \
        --code-root ../Reasoning_Project_tti_pin_e5ef8b5 \
        --out-dir outputs/tti/constructive_v2_reconstruction \
        --v1-exclusion outputs/tti/constructive_v1_1_target_exclusion.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--code-root", required=True,
                    help="detached snapshot of the commit that executed the census")
parser.add_argument("--out-dir", required=True)
parser.add_argument("--v1-exclusion", required=True,
                    help="v1.1 attempted-target digest set (derived, hashed)")
parser.add_argument("--expected-commit", default="e5ef8b5add2f31a37439a3bbbcbf8d0aaa02b724")
args = parser.parse_args()

CODE = Path(args.code_root).resolve()
OUT = Path(args.out_dir).resolve()
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "admitted").mkdir(exist_ok=True)

#  the pinned snapshot must be FIRST on sys.path so every import resolves there
for entry in (str(CODE), str(CODE / "src")):
    sys.path.insert(0, entry)

from cora_tti import constructive_dataset as CD                  # noqa: E402
from cora_tti import constructive_v2_dataset as V2               # noqa: E402
from cora_tti import constructive_v2_feasibility as F            # noqa: E402
from cora_tti import constructive_vocabulary as CV               # noqa: E402
from cora_tti import scoped_slot_fitting as SF                   # noqa: E402

for module in (CD, V2, F, CV, SF):
    resolved = Path(module.__file__).resolve()
    assert str(resolved).startswith(str(CODE)), f"{module.__name__} imported from {resolved}"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_head(root: Path) -> str:
    return subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                          capture_output=True, text=True, check=True).stdout.strip()


#  ---- code identity, checked against the frozen feasibility manifest ----
head = git_head(CODE)
assert head == args.expected_commit, f"snapshot HEAD {head} != {args.expected_commit}"
manifest_path = CODE / "outputs" / "tti" / "constructive_v2_feasibility_manifest.json"
manifest = json.loads(manifest_path.read_text())
original_results_path = CODE / "outputs" / "tti" / "constructive_v2_feasibility_results.json"
original = json.loads(original_results_path.read_text())
identity = {
    "label": "RECONSTRUCTED_FROM_PINNED_GENERATOR",
    "snapshot_commit": head,
    #  the v1.1 generator's concrete-table colour term calls hash(repr(value)),
    #  which Python salts per process unless PYTHONHASHSEED is fixed; the
    #  original census ran with it unset, so instantiations are not
    #  reproducible from the seeds alone (measured in this block)
    "PYTHONHASHSEED": os.environ.get("PYTHONHASHSEED", "unset"),
    "manifest_sha256": sha(manifest_path),
    "original_results_sha256": sha(original_results_path),
    "feasibility_runner_sha256": sha(Path(F.__file__)),
    "scoped_learner_sha256": SF.fitter_identity(),
    "v2_dataset_sha256": sha(Path(V2.__file__)),
    "matches_manifest": {
        "feasibility_runner": sha(Path(F.__file__)) == manifest["feasibility_runner_sha256"],
        "scoped_learner": SF.fitter_identity() == manifest["scoped_learner_sha256"],
        "v2_dataset": sha(Path(V2.__file__)) == manifest["v2_dataset_sha256"],
    },
    "constants_read_from_executed_runner": {
        "SEED_NAMESPACE": F.SEED_NAMESPACE,
        "ATTEMPTS_PER_FAMILY": F.ATTEMPTS_PER_FAMILY,
        "BUDGETS": F.BUDGETS,
    },
}
assert all(identity["matches_manifest"].values()), identity["matches_manifest"]

v1_exclusion_doc = json.loads(Path(args.v1_exclusion).read_text())
v1_exclusion = set(v1_exclusion_doc["digests"])
identity["v1_exclusion_sha256"] = sha(Path(args.v1_exclusion))
identity["v1_exclusion_size"] = len(v1_exclusion)

families = [tuple(f) for f in [*manifest["families_tested"]["training"],
                               *manifest["families_tested"]["structural_holdout"]]]

attempts_path = OUT / "attempts.jsonl"
attempts_path.write_text("")          # fresh reconstruction, never appended to an old one
rows = []
started_all = time.monotonic()
for family in families:
    holdout = CV.is_holdout_family(family)
    regime = "structural_holdout" if holdout else "train_pool"
    family_started = time.monotonic()
    for attempt in range(F.ATTEMPTS_PER_FAMILY):
        #  the seed expression EXACTLY as the executed runner computed it
        seed = F.SEED_NAMESPACE + attempt * 7919 + len(family) * 1013 + sum(family) * 37
        schema = CD.sample_target(seed, family)
        digest = CV.digest(schema)
        blocks = CV.blocks_from_ast(schema)
        t0 = time.monotonic()
        try:
            outcome, episode, evidence = V2.evaluate_target_v2(
                schema, seed=seed, split="feasibility", regime=regime,
                allowed_families=[family],
                seen_digests=set(), seen_train_digests=set(), v1_exclusion=set(),
                budgets=F.BUDGETS, row_index=attempt)
        except Exception as error:                                # noqa: BLE001
            outcome = f"{V2.INFRA_PREFIX}{type(error).__name__}"
            episode, evidence = None, {"infra_error": repr(error)}
        seconds = round(time.monotonic() - t0, 3)
        stage_times = evidence.get("stage_times", {})
        row = {
            "identity_label": "RECONSTRUCTED_FROM_PINNED_GENERATOR",
            "family": list(family), "family_text": CV.family_text(family),
            "attempt": attempt, "seed": seed, "regime": regime,
            "schema_digest": digest,
            "blocks": [[p, list(s), f] for p, s, f in blocks],
            "outcome": outcome,
            "stage_times": stage_times,
            #  base_search_solved AFTER stage r8 means the blind-runtime TFG
            #  search (a different reasoner) solved it, not the meta baseline
            "rejected_by_blind_runtime_tfg_search": bool(
                outcome == "base_search_solved" and "r8" in stage_times),
            "scoped_fit": evidence.get("scoped_fit"),
            "base_search": evidence.get("base_search"),
            "witness_equivalent_baselines": evidence.get("witness_equivalent_baselines"),
            "irreducibility": evidence.get("irreducibility"),
            "demo_diagnostic": evidence.get("demo_diagnostic"),
            "infra_error": evidence.get("infra_error"),
            "in_v1_1_exclusion": digest in v1_exclusion,
            "seconds": seconds,
        }
        if outcome == V2.ADMITTED:
            episode_path = OUT / "admitted" / f"{CV.family_text(family)}_{attempt:03d}.json"
            episode_path.write_text(json.dumps(episode, indent=1, sort_keys=True, default=str))
            row["episode_file"] = str(episode_path.relative_to(OUT))
            row["episode_sha256"] = sha(episode_path)
            row["tfg_digest"] = episode["tfg_digest"]
            row["probe_fingerprint"] = episode["probe_fingerprint"]
        rows.append(row)
        with attempts_path.open("a") as handle:
            handle.write(json.dumps(row, sort_keys=True, default=str) + "\n")
    counts = Counter(r["outcome"] for r in rows if tuple(r["family"]) == family)
    print(f"{CV.family_text(family):8} reconstructed {dict(sorted(counts.items()))} "
          f"{time.monotonic() - family_started:.1f}s", flush=True)

#  ---- offline analysis of identities (guards were inert in the original) ----
by_family = defaultdict(list)
for row in rows:
    by_family[row["family_text"]].append(row)

analysis = {"families": {}, "run_wide": {}}
all_digests = [r["schema_digest"] for r in rows]
admitted_rows = [r for r in rows if r["outcome"] == V2.ADMITTED]
for family_text, frows in by_family.items():
    digests = [r["schema_digest"] for r in frows]
    counts = Counter(r["outcome"] for r in frows)
    original_counts = original["families"][family_text]["outcomes"]
    adm = [r for r in frows if r["outcome"] == V2.ADMITTED]
    adm_digests = [r["schema_digest"] for r in adm]
    analysis["families"][family_text] = {
        "attempts": len(frows),
        "unique_schema_digests": len(set(digests)),
        "repeated_attempts": len(digests) - len(set(digests)),
        "attempts_overlapping_v1_1": sum(r["in_v1_1_exclusion"] for r in frows),
        "reconstructed_outcomes": dict(sorted(counts.items())),
        "original_outcomes": original_counts,
        "outcome_counts_match_original": dict(sorted(counts.items())) == dict(sorted(original_counts.items())),
        "admitted_attempts": len(adm),
        "admitted_distinct_schemas": len(set(adm_digests)),
        "admitted_overlapping_v1_1": sum(r["in_v1_1_exclusion"] for r in adm),
        "admitted_attempt_indices": [r["attempt"] for r in adm],
        "rejected_by_blind_runtime_tfg_search": sum(
            r["rejected_by_blind_runtime_tfg_search"] for r in frows),
        "seconds": round(sum(r["seconds"] for r in frows), 1),
    }

#  the (1,0)/(0,1) seed pairing: same numeric schedule
seed_schedules = {ft: [r["seed"] for r in frows] for ft, frows in by_family.items()}
paired = [(a, b) for a in seed_schedules for b in seed_schedules
          if a < b and seed_schedules[a] == seed_schedules[b]]
analysis["run_wide"] = {
    "attempts": len(rows),
    "unique_schema_digests": len(set(all_digests)),
    "attempts_overlapping_v1_1": sum(r["in_v1_1_exclusion"] for r in rows),
    "admitted_attempts": len(admitted_rows),
    "admitted_distinct_schemas": len({r["schema_digest"] for r in admitted_rows}),
    "admitted_overlapping_v1_1": sum(r["in_v1_1_exclusion"] for r in admitted_rows),
    "families_with_identical_seed_schedules": [list(p) for p in paired],
    "all_family_outcome_counts_match_original": all(
        v["outcome_counts_match_original"] for v in analysis["families"].values()),
    "seconds": round(time.monotonic() - started_all, 1),
}

summary = {"identity": identity, "analysis": analysis,
           "attempts_file": "attempts.jsonl",
           "attempts_sha256": sha(attempts_path)}
(OUT / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True))
print("RECONSTRUCTION_DONE", json.dumps(analysis["run_wide"]), flush=True)
