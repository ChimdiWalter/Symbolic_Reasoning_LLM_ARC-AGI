"""LAS-R1 pre-outcome freeze: targets, exclusions, matched-null libraries.

This script produces NO outcomes. It builds and hashes everything that must be
fixed before the first replication target is scored, so the runner can refuse to
proceed if any of it changes.

Frozen here
    the 256 replication targets, 64 per family, from a new seed namespace;
    the prior-pool exclusion identities used to de-collide them;
    32 matched-null LAS libraries with identical masks, slot types and expansion
    cardinalities, whose constants come from a deterministic pseudo-random rule
    instead of from any source discovery;
    the statistical decision rule.

The LAS-v1 libraries themselves are NOT rebuilt. They are loaded from the
preserved artifact and their hash is verified.
"""
from __future__ import annotations

import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "src")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from geocat_arc.object_reasoning import meta_ast as M            # noqa: E402
from geocat_arc.object_reasoning import meta_induction as MI     # noqa: E402
from cora_tti import abstraction_lattice as AL                   # noqa: E402
from cora_tti import constructive_dataset as CD                  # noqa: E402
from cora_tti import constructive_vocabulary as CV               # noqa: E402
from cora_tti import failure_signal_study as FS                  # noqa: E402

#  ------------------- FROZEN CONSTANTS -------------------
NAMESPACE = 12_000_000            # never used by any earlier study in this line
PER_FAMILY = 64                   # 256 targets total
FAMILY_STRIDE, ATTEMPT_STRIDE = 3_000_017, 7919
SCAN_LIMIT = 20_000               # prospectively fixed; shortfalls are reported
TARGET_BUDGET = 3000
NULL_CONTROLS = 32
NULL_MASTER_SEED = 770_001
VERSION = "LAS-R1"

LAS_V1 = ROOT / "outputs" / "tti" / "las_v1"
OUT = ROOT / "outputs" / "tti" / "las_r1"
OUT.mkdir(parents=True, exist_ok=True)


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


# ---------------------------------------------------------------- step 1 ----
frozen_text = (LAS_V1 / "frozen.json").read_text()
frozen_hash = sha(frozen_text)
pinned = (LAS_V1 / "frozen_hash.txt").read_text().split()[0]
if frozen_hash != pinned:
    raise SystemExit(f"LAS-v1 frozen library hash {frozen_hash} != pinned {pinned}")
LASV1 = json.loads(frozen_text)
print(f"LAS-v1 frozen library verified: {frozen_hash[:16]}", flush=True)
print(f"  concrete {len(LASV1['concrete'])} | LAS {len(LASV1['LAS'])} | "
      f"R1 {len(LASV1['R1'])} | R2 {len(LASV1['R2'])}", flush=True)

# ---------------------------------------------------------------- step 2 ----
#  every prior synthetic target identity in this line of work
print("\nbuilding the prior-pool exclusion set", flush=True)
excluded: dict = {}


def note(digest: str, origin: str):
    excluded.setdefault(digest, []).append(origin)


for pool, ids in LASV1["pool_identities"].items():
    for digest in ids:
        note(digest, f"las_v1:{pool}")

for name, path in (("abstraction_transfer",
                    ROOT / "outputs" / "tti" / "abstraction_transfer" / "results.json"),
                   ("failure_signal_study",
                    ROOT / "outputs" / "tti" / "failure_signal_study" / "results.json")):
    if not path.exists():
        continue
    data = json.loads(path.read_text())
    seen = set()
    for row in data.get("rows", []):
        family = tuple(int(x) for x in row["family"].strip("()").split(",") if x != "")
        key = (row["seed"], family)
        if key in seen:
            continue
        seen.add(key)
        note(CV.digest(CD.sample_target(row["seed"], family)), name)
    #  the abstraction-transfer source pool is recorded per-source
    for row in data.get("acquisition", {}).get("per_source", []):
        family = tuple(int(x) for x in row["family"].strip("()").split(",") if x != "")
        note(CV.digest(CD.sample_target(row["seed"], family)), f"{name}:source")

print(f"  prior identities excluded: {len(excluded)}", flush=True)

# ---------------------------------------------------------------- step 3 ----
print("\nbuilding 256 replication targets (de-collision by identity only)", flush=True)
taken = set(excluded)
targets, skips, shortfalls = [], [], []
for family_index, family in enumerate(FS.STUDY_FAMILIES):
    found, attempt = 0, 0
    while found < PER_FAMILY and attempt < SCAN_LIMIT:
        seed = NAMESPACE + family_index * FAMILY_STRIDE + attempt * ATTEMPT_STRIDE
        attempt += 1
        episode = FS.build_episode(seed, family)
        if episode is None:
            continue
        if episode.target_digest in taken:
            skips.append({"seed": seed, "family": CV.family_text(family),
                          "digest": episode.target_digest[:16],
                          "reason": ("prior_pool" if episode.target_digest in excluded
                                     else "already_in_las_r1")})
            continue
        taken.add(episode.target_digest)
        targets.append({"index": len(targets), "seed": seed,
                        "family": CV.family_text(family),
                        "family_tuple": list(family),
                        "target_digest": episode.target_digest})
        found += 1
    print(f"  {CV.family_text(family)}: {found}/{PER_FAMILY} after {attempt} attempts "
          f"({sum(1 for s in skips if s['family'] == CV.family_text(family))} skipped)",
          flush=True)
    if found < PER_FAMILY:
        shortfalls.append({"family": CV.family_text(family), "obtained": found,
                           "requested": PER_FAMILY, "scan_limit": SCAN_LIMIT})
        print(f"    SHORTFALL RETAINED: {CV.family_text(family)} reached {found}", flush=True)

# ---------------------------------------------------------------- step 4 ----
#  32 matched-null libraries: identical masks, slot types and cardinalities;
#  constants drawn by a frozen deterministic rule with no source discoveries.
print(f"\nbuilding {NULL_CONTROLS} matched-null libraries", flush=True)
v = CV.vocab()
DOMAIN = {"partition": list(v["partitions"]), "predicate": list(v["predicates"]),
          "feature": list(v["key_features"])}


def concept_positions(schema):
    """Eligible positions and which are already slots, from the stored schema."""
    blocks = AL._concept_blocks(schema)
    return blocks


def build_null_library(control_index: int) -> tuple:
    """One null library. Returns (entries, rejections). A control is rejected only
    under the static legality rule that its rebuilt abstraction must have the same
    slot types and expansion as the LAS concept it mirrors."""
    rng = np.random.default_rng(NULL_MASTER_SEED + control_index)
    entries, rejections = [], []
    for record in LASV1["LAS"]:
        schema = M.ast_from_json(json.loads(record["canonical"]))
        blocks = concept_positions(schema)
        attempts = 0
        while True:
            attempts += 1
            new_blocks = []
            for partition, selects, feature in blocks:
                new_partition = (partition if AL._is_slot(partition)
                                 else DOMAIN["partition"][int(rng.integers(0, 4))])
                new_selects = tuple(
                    s if AL._is_slot(s) else DOMAIN["predicate"][int(rng.integers(0, 5))]
                    for s in selects)
                new_feature = (feature if AL._is_slot(feature)
                               else DOMAIN["feature"][int(rng.integers(0, 10))])
                new_blocks.append((new_partition, new_selects, new_feature))
            candidate = AL._schema_from(new_blocks)
            types = M.free_slot_types(candidate)
            enumerable = {s: t for s, t in types.items() if t in M.ENUMERABLE_TYPES}
            expansion = 1
            for slot_type in enumerable.values():
                expansion *= len(M.slot_domain(slot_type))
            tables_ok = all(types.get(f"?{i}") == "Map[FeatureValue,Colour]"
                            for i in range(record["n_blocks"]))
            if (enumerable == record["slot_types"] and expansion == record["expansion"]
                    and tables_ok):
                entries.append({"mirrors": record["name"],
                                "canonical": CV.canonical(candidate),
                                "slot_types": enumerable, "expansion": expansion,
                                "n_blocks": record["n_blocks"],
                                "attempts_to_legal": attempts})
                break
            rejections.append({"control": control_index, "mirrors": record["name"],
                               "attempt": attempts,
                               "reason": ("slot_types" if enumerable != record["slot_types"]
                                          else "expansion" if expansion != record["expansion"]
                                          else "table_slots")})
            if attempts > 200:
                raise SystemExit(f"control {control_index} could not produce a legal mirror")
    return entries, rejections


NULLS, ALL_REJECTIONS = [], []
for index in range(NULL_CONTROLS):
    entries, rejections = build_null_library(index)
    ALL_REJECTIONS.extend(rejections)
    payload = json.dumps(entries, sort_keys=True)
    NULLS.append({"control": index, "seed": NULL_MASTER_SEED + index,
                  "entries": entries, "sha256": sha(payload),
                  "total_expansion": sum(e["expansion"] for e in entries)})
las_total_expansion = sum(r["expansion"] for r in LASV1["LAS"])
for null in NULLS:
    assert null["total_expansion"] == las_total_expansion, "null cardinality differs"
    assert len(null["entries"]) == len(LASV1["LAS"]), "null concept count differs"
print(f"  {len(NULLS)} controls, each {len(LASV1['LAS'])} concepts, "
      f"total expansion {las_total_expansion} (identical to LAS)", flush=True)
print(f"  rejections under the static legality rule: {len(ALL_REJECTIONS)}", flush=True)

# ---------------------------------------------------------------- step 5 ----
DECISION_RULE = {
    "primary_endpoint": "HELDOUT_OUTPUT_SUCCESS over all replication targets",
    "primary_comparison": "LAS vs CONCRETE, paired by target",
    "verdict_ROBUSTLY_REPLICATED_iff": [
        "point estimate LAS minus CONCRETE held-out successes is strictly positive",
        "AND the lower bound of the 95 per cent paired bootstrap confidence "
        "interval on that difference is strictly greater than zero"],
    "bootstrap": {"resamples": 10000, "unit": "target", "seed": 20260908,
                  "interval": "percentile, 2.5 and 97.5"},
    "exact_test_reported_alongside": "two-sided exact McNemar on discordant pairs",
    "matched_null_criterion": (
        "LAS held-out success count strictly exceeds that of at least 31 of the 32 "
        "matched-null controls, i.e. exceeds at least 95 per cent of them"),
    "secondary_comparisons": ["LAS vs ORDINARY", "LAS vs R1", "LAS vs R2"],
    "family_stratification": "descriptive and exploratory only; the 256-target "
                             "paired comparison remains primary",
    "if_criterion_fails": "NOT ROBUSTLY REPLICATED; the rule is not redefined afterwards",
}

#  group-ablation partitions, defined mechanically BEFORE outcomes
top_concept = LASV1["LAS"][0]


def invariant_signature(record) -> str:
    """Canonical signature of a concept's FIXED positions: the constants it kept."""
    schema = M.ast_from_json(json.loads(record["canonical"]))
    parts = []
    for block_index, (partition, selects, feature) in enumerate(AL._concept_blocks(schema)):
        for kind, value in (("partition", partition), ("feature", feature)):
            if not AL._is_slot(value):
                parts.append(f"{kind}{block_index}={value}")
        for select_index, predicate in enumerate(selects):
            if not AL._is_slot(predicate):
                parts.append(f"predicate{block_index}.{select_index}={predicate}")
    return "|".join(sorted(parts))


top_signature = invariant_signature(top_concept)
top_group = top_concept["group_key"]
ABLATIONS = {
    "A_source_group": {
        "description": "remove every concept from the top concept's source-member group",
        "remove": [r["name"] for r in LASV1["LAS"] if r["group_key"] == top_group]},
    "B_invariant_signature": {
        "description": "remove every concept sharing the top concept's fixed invariant "
                       "signature under the canonical definition",
        "signature": top_signature,
        "remove": [r["name"] for r in LASV1["LAS"]
                   if invariant_signature(r) == top_signature]},
    "C_family_origin": {
        "description": "remove every LAS concept originating from family (0,0)",
        "remove": [r["name"] for r in LASV1["LAS"] if r["group_key"].startswith("(0,0)")]},
    "D_whole_LAS": {
        "description": "remove the complete LAS prior",
        "remove": [r["name"] for r in LASV1["LAS"]]},
}
for key, spec in ABLATIONS.items():
    spec["removes_count"] = len(spec["remove"])
    spec["equals_whole_prior"] = len(spec["remove"]) == len(LASV1["LAS"])
    print(f"  ablation {key}: removes {spec['removes_count']}/{len(LASV1['LAS'])}"
          f"{' (EQUALS whole-prior removal)' if spec['equals_whole_prior'] else ''}",
          flush=True)

# ---------------------------------------------------------------- write ----
frozen = {
    "version": VERSION,
    "las_v1_frozen_sha256": frozen_hash,
    "pinned": {"namespace": NAMESPACE, "per_family": PER_FAMILY,
               "family_stride": FAMILY_STRIDE, "attempt_stride": ATTEMPT_STRIDE,
               "scan_limit": SCAN_LIMIT, "target_budget": TARGET_BUDGET,
               "null_controls": NULL_CONTROLS, "null_master_seed": NULL_MASTER_SEED},
    "targets": targets, "target_count": len(targets),
    "shortfalls": shortfalls,
    "decollision_skips": skips, "decollision_skip_count": len(skips),
    "excluded_prior_identities": {"count": len(excluded),
                                  "origins": sorted({o for v in excluded.values() for o in v})},
    "null_controls": NULLS,
    "null_control_hashes": [n["sha256"] for n in NULLS],
    "null_legality_rejections": len(ALL_REJECTIONS),
    "decision_rule": DECISION_RULE,
    "ablation_partitions": ABLATIONS,
    "code_hashes": {
        "abstraction_lattice": AL.code_hash(),
        "scoped_slot_fitting": hashlib.sha256(
            (ROOT / "cora_tti" / "scoped_slot_fitting.py").read_bytes()).hexdigest(),
        "failure_signal_study": hashlib.sha256(
            (ROOT / "cora_tti" / "failure_signal_study.py").read_bytes()).hexdigest()},
}
text = json.dumps(frozen, indent=1, sort_keys=True)
(OUT / "frozen.json").write_text(text)
(OUT / "frozen_hash.txt").write_text(sha(text) + "\n")
print(f"\nLAS-R1 PRE-OUTCOME FREEZE sha256 {sha(text)}")
print(f"targets {len(targets)} | skips {len(skips)} | shortfalls {len(shortfalls)} | "
      f"nulls {len(NULLS)}")
print("FREEZE_DONE")
