"""LAS-v1: can CORA select the useful LEVEL of abstraction from source-side
evidence alone, and does that beat concrete-schema reuse on disjoint tasks?

EVERYTHING SCIENTIFIC IS DECLARED HERE AND FROZEN BEFORE FINAL-TRANSFER IS OPENED.

Pools, three, disjoint, built before anything is measured
    SOURCE-ACQUIRE    namespace 9,100,000, 4 per family, 16 episodes
    SOURCE-VALIDATE   namespace 9,400,000, 4 per family, 16 episodes
    FINAL-TRANSFER    namespace 9,700,000, 6 per family, 24 episodes
    Target-identity overlap is required to be zero and is checked. Structural
    schema overlap is recorded separately rather than assumed impossible.

Acquisition policy, ONE, declared in advance
    Deterministic ordinary two-block constructive search, smallest-first over the
    fixed 57,600-candidate enumeration, 2,880 candidate fits per source episode.
    Every source search is charged, successful or not. Failure-guided ranking is
    not used, so nothing here bears on failure conditioning.

Grouping rule, frozen and mechanical
    Within each structural family: every unordered PAIR of distinct discovered
    structures, plus the full family group. No group is chosen by hand and none
    is selected after seeing transfer outcomes.

Abstraction lattice
    For each group, every mask that is a superset of the group's disagreement
    set. The minimal element is exactly the anti-unification, so anti-unification
    appears as ONE candidate rather than as the answer. Masks whose expansion
    exceeds MAX_EXPANSION are excluded and that exclusion is reported.

Selection objective, lexicographic, frozen before SOURCE-VALIDATE is scored
    1. maximize validation held-out correctness
    2. minimize validation wrong-but-demonstration-consistent count
    3. minimize total validation search cost
    4. minimize expansion size
    5. minimize description length (MDL)
    6. tie-break on the canonical schema string, deterministic

Retention, frozen
    Candidates with at least one validation held-out success, deduplicated by
    schema digest, taken in objective order, added while the cumulative expansion
    stays within RETAIN_EXPANSION_BUDGET, at most RETAIN_MAX concepts.

Target policies, one common budget, learned prior then ordinary fallback
    A ORDINARY, B CONCRETE, C R1, D R2, E LAS, F MATCHED-SPACE CONTROL.
    One unit is one concrete candidate fit. A concept expanding to n candidates
    costs n units if all are attempted. Candidates already tried are never
    retried. Held-out correctness never influences target-time search.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import platform
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "src")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from geocat_arc.object_reasoning import meta_ast as M            # noqa: E402
from geocat_arc.object_reasoning import meta_induction as MI     # noqa: E402
from cora_tti import abstraction_lattice as AL                   # noqa: E402
from cora_tti import constructive_vocabulary as CV               # noqa: E402
from cora_tti import failure_signal_study as FS                  # noqa: E402
from cora_tti import meta_baseline as MB                         # noqa: E402
from cora_tti import scoped_slot_fitting as SF                   # noqa: E402

#  ---------------- frozen constants ----------------
SOURCE_NS, VALIDATE_NS, TRANSFER_NS = 9_100_000, 9_400_000, 9_700_000
SOURCE_PER_FAMILY, VALIDATE_PER_FAMILY, TRANSFER_PER_FAMILY = 4, 4, 6
ACQUISITION_BUDGET = 2880
TARGET_BUDGET = 3000
MAX_EXPANSION = 400
RETAIN_EXPANSION_BUDGET = 1000
RETAIN_MAX = 8
VERSION = "LAS-v1"

parser = argparse.ArgumentParser()
parser.add_argument("--out", default=str(ROOT / "outputs" / "tti" / "las_v1"))
args = parser.parse_args()
OUT = Path(args.out)
OUT.mkdir(parents=True, exist_ok=True)
CONFIG = MB.BaselineConfig()
SPACE = FS.proposal_space()


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def git_head() -> str:
    try:
        return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.strip()
    except Exception:                                             # noqa: BLE001
        return "UNKNOWN"


#: DE-COLLISION RULE, declared before any transfer outcome is opened.
#: The schema space is finite, so two pools built from disjoint SEED namespaces
#: can still sample the same target SCHEMA. Pools are built in the fixed order
#: source, validate, transfer, and an episode whose target identity already
#: appears in an earlier pool is skipped and the seed scan continues. This
#: enforces the pinned zero-overlap requirement mechanically. It never inspects
#: outcomes and never prefers a task for being favourable. Every skip is counted
#: and reported.
COLLISION_SKIPS: list = []


def build_pool(namespace: int, per_family: int, label: str, taken: set) -> list:
    pool = []
    for family_index, family in enumerate(FS.STUDY_FAMILIES):
        found, attempt, skipped = 0, 0, 0
        while found < per_family and attempt < 8000:
            seed = namespace + family_index * 3_000_017 + attempt * 7919
            attempt += 1
            episode = FS.build_episode(seed, family)
            if episode is None:
                continue
            if episode.target_digest in taken:
                skipped += 1
                COLLISION_SKIPS.append({"pool": label, "family": CV.family_text(family),
                                        "seed": seed,
                                        "target_digest": episode.target_digest[:16]})
                continue
            taken.add(episode.target_digest)
            pool.append(episode)
            found += 1
        print(f"  {label} {CV.family_text(family)}: {found}/{per_family} "
              f"after {attempt} attempts ({skipped} skipped as schema collisions)",
              flush=True)
        if found < per_family:
            print(f"    SHORTFALL: {label} {CV.family_text(family)} reached only {found}",
                  flush=True)
    return pool


def score_program(program, heldout) -> dict:
    correct = defined = 0
    for grid_in, grid_out in heldout:
        rendered = M.evaluate(program, np.asarray(grid_in), MI.descriptors)
        if rendered is None:
            continue
        defined += 1
        correct += int(np.array_equal(rendered, np.asarray(grid_out)))
    return {"heldout_defined": defined, "heldout_total": len(heldout),
            "heldout_correct": defined == len(heldout) and correct == len(heldout),
            "undefined": defined < len(heldout)}


# ======================= STAGE 1: pools =======================
print("STAGE 1: building three disjoint pools", flush=True)
TAKEN: set = set()
SOURCE = build_pool(SOURCE_NS, SOURCE_PER_FAMILY, "source", TAKEN)
VALIDATE = build_pool(VALIDATE_NS, VALIDATE_PER_FAMILY, "validate", TAKEN)
TRANSFER = build_pool(TRANSFER_NS, TRANSFER_PER_FAMILY, "transfer", TAKEN)
pool_ids = {name: [e.target_digest for e in pool] for name, pool in
            (("source", SOURCE), ("validate", VALIDATE), ("transfer", TRANSFER))}
overlaps = {}
for a, b in itertools.combinations(pool_ids, 2):
    overlaps[f"{a}|{b}"] = sorted(set(pool_ids[a]) & set(pool_ids[b]))
print(f"pools: {len(SOURCE)}/{len(VALIDATE)}/{len(TRANSFER)} | "
      f"identity overlaps {{k: len(v) for k, v in overlaps.items()}}"
      .replace("{k: len(v) for k, v in overlaps.items()}",
               str({k: len(v) for k, v in overlaps.items()})), flush=True)
assert all(not v for v in overlaps.values()), f"pool identity overlap: {overlaps}"

# ======================= STAGE 2: acquisition =======================
print("\nSTAGE 2: SOURCE-ACQUIRE, ordinary constructive search, all charged", flush=True)
acquisition, acq_units, acq_started = [], 0, time.perf_counter()
for index, episode in enumerate(SOURCE):
    baseline = MB.run_baseline(episode.pairs, CONFIG)
    used, found = 0, None
    for candidate in SPACE:
        if used >= ACQUISITION_BUDGET:
            break
        used += 1
        outcome = SF.fit_outcome(FS.schema_of(candidate), episode.pairs,
                                 require_exact_replay=True)
        if outcome["status"] == "EXACT_DEMONSTRATION_FIT":
            found = FS.schema_of(candidate)
            break
    acq_units += used
    blocks = CV.blocks_from_ast(found) if found is not None else None
    acquisition.append({
        "source_index": index, "seed": episode.seed,
        "family": CV.family_text(episode.family),
        "baseline_solved_it": bool(baseline.exact),
        "search_units": used, "discovered": found is not None,
        "structure_digest": CV.digest(found) if found is not None else None,
        "structure_family": CV.family_text(CV.family(found)) if found is not None else None,
        "blocks": [[p, list(s), f] for p, s, f in blocks] if blocks else None,
        "information_dependencies": {
            "demonstrations_from_source_episode": index,
            "trace_from": None,
            "policy": "ordinary smallest-first constructive search"},
    })
    print(f"  src{index:02d} {CV.family_text(episode.family):6} "
          f"{'found' if found is not None else 'FAILED':6} {used:5}u", flush=True)
acq_seconds = time.perf_counter() - acq_started
discovered = [a for a in acquisition if a["discovered"]]
print(f"acquisition: {len(discovered)}/{len(SOURCE)} discovered, {acq_units} units", flush=True)

concrete = {}
for row in discovered:
    schema = CV.ast_from_blocks([(b[0], tuple(b[1]), b[2]) for b in row["blocks"]])
    concrete.setdefault(row["structure_digest"], {
        "digest": row["structure_digest"], "schema": schema,
        "structure_family": row["structure_family"], "sources": []})
    concrete[row["structure_digest"]]["sources"].append(row["source_index"])
CONCRETE = sorted(concrete.values(), key=lambda e: e["digest"])
print(f"concrete library: {len(CONCRETE)} distinct structures", flush=True)

# ======================= STAGE 3: abstraction lattice =======================
print("\nSTAGE 3: generating the abstraction lattice mechanically", flush=True)
lat_started = time.perf_counter()
by_family = defaultdict(list)
for entry in CONCRETE:
    by_family[entry["structure_family"]].append(entry)

groups = []
for family, entries in sorted(by_family.items()):
    for pair in itertools.combinations(range(len(entries)), 2):
        groups.append((f"{family}|pair{pair}", [entries[i] for i in pair]))
    if len(entries) > 2:
        groups.append((f"{family}|all", entries))
print(f"groups (frozen rule: all pairs plus the full family group): {len(groups)}", flush=True)

candidates, excluded_by_expansion = [], 0
for group_key, entries in groups:
    blocks = [CV.blocks_from_ast(e["schema"]) for e in entries]
    if not AL.compatible(blocks):
        continue
    full = AL.lattice_for(blocks, tuple(e["digest"] for e in entries),
                          tuple(s for e in entries for s in e["sources"]),
                          group_key, max_expansion=10 ** 9)
    kept = [a for a in full if a.expansion() <= MAX_EXPANSION]
    excluded_by_expansion += len(full) - len(kept)
    candidates.extend(kept)
#  deduplicate identical schemas, keeping the first by canonical order
seen, unique = set(), []
for abstraction in sorted(candidates, key=lambda a: (a.expansion(), a.mdl(), a.digest())):
    if abstraction.digest() in seen:
        continue
    seen.add(abstraction.digest())
    unique.append(abstraction)
CANDIDATES = unique
lat_seconds = time.perf_counter() - lat_started
print(f"candidate abstractions: {len(CANDIDATES)} unique "
      f"({excluded_by_expansion} masks excluded by the expansion cap {MAX_EXPANSION})",
      flush=True)

# ======================= STAGE 4: source-side validation =======================
print("\nSTAGE 4: SOURCE-VALIDATE, scoring every candidate", flush=True)
val_started, val_units_total = time.perf_counter(), 0
scored = []
for position, abstraction in enumerate(CANDIDATES):
    fits = heldout = wrong = undefined = 0
    units = 0
    for episode in VALIDATE:
        attempted = set()
        for instantiated in abstraction.instantiations():
            digest = CV.digest(instantiated)
            if digest in attempted:
                continue
            attempted.add(digest)
            units += 1
            outcome = SF.fit_outcome(instantiated, episode.pairs, require_exact_replay=True)
            if outcome["status"] == "EXACT_DEMONSTRATION_FIT":
                fits += 1
                score = score_program(outcome["program"], episode.heldout)
                if score["heldout_correct"]:
                    heldout += 1
                else:
                    wrong += 1
                undefined += int(score["undefined"])
                break
    val_units_total += units
    scored.append({"abstraction": abstraction, "validation": {
        "demo_fits": fits, "heldout_correct": heldout,
        "wrong_but_demo_consistent": wrong, "undefined": undefined,
        "search_units": units, "expansion": abstraction.expansion(),
        "mdl": abstraction.mdl()}})
    if (position + 1) % 20 == 0:
        print(f"  scored {position + 1}/{len(CANDIDATES)} ({val_units_total} units)", flush=True)
val_seconds = time.perf_counter() - val_started
print(f"validation: {val_units_total} units, {round(val_seconds,1)}s", flush=True)


def objective_key(item):
    """FROZEN lexicographic objective. Lower tuple sorts first, so successes are
    negated to make more of them better."""
    v = item["validation"]
    return (-v["heldout_correct"], v["wrong_but_demo_consistent"], v["search_units"],
            v["expansion"], v["mdl"], CV.canonical(item["abstraction"].schema))


eligible = [s for s in scored if s["validation"]["heldout_correct"] > 0]
ordered = sorted(eligible, key=objective_key)
LAS, cumulative = [], 0
for item in ordered:
    if len(LAS) >= RETAIN_MAX:
        break
    expansion = item["abstraction"].expansion()
    if cumulative + expansion > RETAIN_EXPANSION_BUDGET:
        continue
    LAS.append(item)
    cumulative += expansion
print(f"LAS retained {len(LAS)} concepts, cumulative expansion {cumulative} "
      f"(from {len(eligible)} eligible of {len(CANDIDATES)})", flush=True)

#  the previous experiment's two rules, reconstructed on THIS source pool via the
#  same adapter: the minimal mask of a grouping is exactly its anti-unification
def minimal_for(grouping) -> list:
    out = []
    for key, entries in sorted(grouping.items(), key=lambda kv: str(kv[0])):
        if len(entries) < 2:
            continue
        blocks = [CV.blocks_from_ast(e["schema"]) for e in entries]
        if not AL.compatible(blocks):
            continue
        mask = AL.disagreement(blocks)
        if not mask:
            continue
        abstraction = AL.build(f"min|{key}", blocks, mask,
                               tuple(e["digest"] for e in entries),
                               tuple(s for e in entries for s in e["sources"]), str(key))
        if abstraction is not None:
            out.append(abstraction)
    return out


r1_groups = defaultdict(list)
r2_groups = defaultdict(list)
for entry in CONCRETE:
    r1_groups[entry["structure_family"]].append(entry)
    r2_groups[(entry["structure_family"],
               CV.blocks_from_ast(entry["schema"])[0][0])].append(entry)
R1 = minimal_for(r1_groups)
R2 = minimal_for(r2_groups)
CONTROL = [c for c in (AL.matched_control(item["abstraction"], f"ctrl:{item['abstraction'].name}")
                       for item in LAS) if c is not None]
print(f"R1 concepts {len(R1)} expansions {[a.expansion() for a in R1]}", flush=True)
print(f"R2 concepts {len(R2)} expansions {[a.expansion() for a in R2]}", flush=True)
print(f"matched control {len(CONTROL)} expansions {[a.expansion() for a in CONTROL]}", flush=True)
assert sum(a.expansion() for a in CONTROL) == sum(i["abstraction"].expansion() for i in LAS), \
    "matched control cardinality differs from LAS"

# ======================= STAGE 5: FREEZE =======================
frozen = {
    "version": VERSION, "git_commit": git_head(),
    "code_hash": {"abstraction_lattice": AL.code_hash(),
                  "scoped_slot_fitting": hashlib.sha256(
                      (ROOT / "cora_tti" / "scoped_slot_fitting.py").read_bytes()).hexdigest()},
    "pinned": {"SOURCE_NS": SOURCE_NS, "VALIDATE_NS": VALIDATE_NS,
               "TRANSFER_NS": TRANSFER_NS,
               "per_family": [SOURCE_PER_FAMILY, VALIDATE_PER_FAMILY, TRANSFER_PER_FAMILY],
               "acquisition_budget": ACQUISITION_BUDGET, "target_budget": TARGET_BUDGET,
               "max_expansion": MAX_EXPANSION,
               "retain_expansion_budget": RETAIN_EXPANSION_BUDGET,
               "retain_max": RETAIN_MAX,
               "grouping_rule": "all unordered pairs within a structural family, plus the full family group",
               "objective": "lexicographic: max heldout, min wrong-but-demo-consistent, "
                            "min validation units, min expansion, min MDL, canonical tiebreak"},
    "pool_identities": pool_ids, "pool_overlaps": {k: v for k, v in overlaps.items()},
    "schema_collision_skips": COLLISION_SKIPS,
    "concrete": [{"digest": e["digest"], "structure_family": e["structure_family"],
                  "sources": e["sources"], "canonical": CV.canonical(e["schema"])}
                 for e in CONCRETE],
    "LAS": [dict(i["abstraction"].to_json(), validation=i["validation"]) for i in LAS],
    "R1": [a.to_json() for a in R1], "R2": [a.to_json() for a in R2],
    "CONTROL": [a.to_json() for a in CONTROL],
}
frozen_text = json.dumps(frozen, indent=1, sort_keys=True)
(OUT / "frozen.json").write_text(frozen_text)
FROZEN_HASH = sha(frozen_text)
(OUT / "frozen_hash.txt").write_text(FROZEN_HASH + "\n")
print(f"\nSTAGE 5: FROZEN sha256 {FROZEN_HASH[:16]} -- FINAL-TRANSFER now opens", flush=True)

# ======================= STAGE 6: final transfer =======================
def run_policy(prior_items, episode, budget):
    """Learned prior first, then ordinary fallback. One unit per concrete fit."""
    started = time.perf_counter()
    attempted, used, prior_used = set(), 0, 0
    found = phase = source = None
    demo_consistent_before_accept = 0

    def attempt(schema):
        nonlocal used
        digest = CV.digest(schema)
        if digest in attempted:
            return None
        attempted.add(digest)
        used += 1
        outcome = SF.fit_outcome(schema, episode.pairs, require_exact_replay=True)
        return outcome if outcome["status"] == "EXACT_DEMONSTRATION_FIT" else None

    for label, schema_iter in prior_items:
        if found is not None or used >= budget:
            break
        for schema in schema_iter:
            if used >= budget:
                break
            outcome = attempt(schema)
            if outcome is not None:
                found, phase, source = (schema, outcome["program"]), "prior", label
                break
    prior_used = used
    if found is None:
        for candidate in SPACE:
            if used >= budget:
                break
            outcome = attempt(FS.schema_of(candidate))
            if outcome is not None:
                found = (FS.schema_of(candidate), outcome["program"])
                phase, source = "fallback", "ordinary"
                break
    result = {"solved": found is not None, "units": used, "prior_units": prior_used,
              "fallback_units": used - prior_used, "phase": phase, "source": source,
              "seconds": round(time.perf_counter() - started, 3)}
    if found is not None:
        schema, program = found
        result["found_digest"] = CV.digest(schema)
        result["exact_ast_recovered"] = CV.digest(schema) == episode.target_digest
        result.update(score_program(program, episode.heldout))
        result["wrong_but_demo_consistent"] = not result["heldout_correct"]
    return result


def prior_of(kind):
    if kind == "A":
        return []
    if kind == "B":
        return [(e["digest"][:16], [e["schema"]]) for e in CONCRETE]
    if kind == "C":
        return [(a.name, list(a.instantiations())) for a in R1]
    if kind == "D":
        return [(a.name, list(a.instantiations())) for a in R2]
    if kind == "E":
        return [(i["abstraction"].name, list(i["abstraction"].instantiations())) for i in LAS]
    return [(a.name, list(a.instantiations())) for a in CONTROL]


POLICIES = {"A_ordinary": "A", "B_concrete": "B", "C_R1": "C",
            "D_R2": "D", "E_LAS": "E", "F_matched_control": "F"}
print("\nSTAGE 6: FINAL-TRANSFER", flush=True)
rows, transfer_started = [], time.perf_counter()
for index, episode in enumerate(TRANSFER):
    for name, kind in POLICIES.items():
        result = run_policy(prior_of(kind), episode, TARGET_BUDGET)
        rows.append({"target": index, "seed": episode.seed,
                     "family": CV.family_text(episode.family),
                     "policy": name, **result})
    done = [r for r in rows if r["target"] == index]
    print(f"  tgt{index:02d} {CV.family_text(episode.family):6} "
          + " ".join(f"{r['policy'][0]}{'Y' if r['solved'] else 'n'}/{r['units']}"
                     for r in done), flush=True)
transfer_seconds = time.perf_counter() - transfer_started

# ======================= STAGE 7: ablations =======================
print("\nSTAGE 7: ablations", flush=True)
by_policy = defaultdict(dict)
for row in rows:
    by_policy[row["policy"]][row["target"]] = row
ablations = []
for policy, kind, items in (("B_concrete", "B", CONCRETE), ("E_LAS", "E", LAS)):
    for index in range(len(TRANSFER)):
        before = by_policy[policy][index]
        ordinary = by_policy["A_ordinary"][index]
        changed = (before.get("heldout_correct") != ordinary.get("heldout_correct")
                   or before["units"] != ordinary["units"]
                   or before["solved"] != ordinary["solved"])
        if not (changed and before["solved"] and before["phase"] == "prior"):
            continue
        if kind == "B":
            remainder = [(e["digest"][:16], [e["schema"]]) for e in CONCRETE
                         if e["digest"][:16] != before["source"]]
        else:
            remainder = [(i["abstraction"].name, list(i["abstraction"].instantiations()))
                         for i in LAS if i["abstraction"].name != before["source"]]
        after = run_policy(remainder, TRANSFER[index], TARGET_BUDGET)
        ablations.append({
            "policy": policy, "removed": before["source"], "target": index,
            "family": before["family"],
            "fit_lost": before["solved"] and not after["solved"],
            "heldout_correctness_lost": bool(before.get("heldout_correct"))
                                        and not bool(after.get("heldout_correct")),
            "cost_increase": after["units"] - before["units"],
            "fallback_solution_changed": before["phase"] != after["phase"],
            "program_identity_changed": before.get("found_digest") != after.get("found_digest"),
            "before": {k: before.get(k) for k in ("solved", "units", "heldout_correct",
                                                  "found_digest", "phase")},
            "after": {k: after.get(k) for k in ("solved", "units", "heldout_correct",
                                                "found_digest", "phase")}})
        a = ablations[-1]
        print(f"  {policy} remove {str(before['source'])[:14]} tgt{index:02d}: "
              f"fit_lost={a['fit_lost']} heldout_lost={a['heldout_correctness_lost']} "
              f"cost+{a['cost_increase']} prog_changed={a['program_identity_changed']}", flush=True)

# ======================= report =======================
summary = {}
for policy in POLICIES:
    prows = [by_policy[policy][i] for i in range(len(TRANSFER))]
    fits = [r for r in prows if r["solved"]]
    summary[policy] = {
        "episodes": len(prows), "demonstration_fits": len(fits),
        "heldout_output_success": sum(1 for r in fits if r.get("heldout_correct")),
        "wrong_but_demo_consistent": sum(1 for r in fits if r.get("wrong_but_demo_consistent")),
        "undefined_predictions": sum(1 for r in fits if r.get("undefined")),
        "exact_ast_recovered": sum(1 for r in fits if r.get("exact_ast_recovered")),
        "solved_in_prior": sum(1 for r in fits if r["phase"] == "prior"),
        "solved_in_fallback": sum(1 for r in fits if r["phase"] == "fallback"),
        "total_units": sum(r["units"] for r in prows),
        "mean_units": round(sum(r["units"] for r in prows) / len(prows), 1),
        "total_seconds": round(sum(r["seconds"] for r in prows), 1),
        "budget_exhausted": sum(1 for r in prows if not r["solved"])}

report = {
    "version": VERSION, "git_commit": git_head(), "frozen_sha256": FROZEN_HASH,
    "environment": {"PYTHONHASHSEED": os.environ.get("PYTHONHASHSEED"),
                    "python": platform.python_version(), "numpy": np.__version__},
    "pinned": frozen["pinned"],
    "pools": {"sizes": {"source": len(SOURCE), "validate": len(VALIDATE),
                        "transfer": len(TRANSFER)},
              "identity_overlaps": {k: len(v) for k, v in overlaps.items()},
              "schema_collision_skips": len(COLLISION_SKIPS),
              "schema_collision_detail": COLLISION_SKIPS,
              "structural_schema_overlap_note": (
                  "the schema space is finite, so disjoint seed namespaces can still sample "
                  "the same target schema. Pools are built in the fixed order source, "
                  "validate, transfer and a colliding episode is skipped by a rule declared "
                  "before any transfer outcome. Every skip is counted above. Final "
                  "target-identity overlap is therefore zero by construction")},
    "acquisition": {"policy": "ordinary smallest-first constructive search",
                    "episodes": len(SOURCE), "discovered": len(discovered),
                    "failed": len(SOURCE) - len(discovered),
                    "units": acq_units, "seconds": round(acq_seconds, 1),
                    "concrete_library": len(CONCRETE), "per_source": acquisition},
    "lattice": {"groups": len(groups), "candidates": len(CANDIDATES),
                "excluded_by_expansion_cap": excluded_by_expansion,
                "seconds": round(lat_seconds, 1)},
    "validation": {"episodes": len(VALIDATE), "units": val_units_total,
                   "seconds": round(val_seconds, 1),
                   "eligible_candidates": len(eligible),
                   "scored": [{"name": s["abstraction"].name,
                               "expansion": s["abstraction"].expansion(),
                               **s["validation"]} for s in scored]},
    "libraries": {"concrete": len(CONCRETE), "LAS": len(LAS), "R1": len(R1), "R2": len(R2),
                  "control": len(CONTROL),
                  "LAS_detail": [dict(i["abstraction"].to_json(), validation=i["validation"])
                                 for i in LAS]},
    "summary": summary,
    "cost_accounting": {
        "acquisition_units": acq_units,
        "abstraction_generation_seconds": round(lat_seconds, 1),
        "source_validation_units": val_units_total,
        "final_transfer_units_by_policy": {p: summary[p]["total_units"] for p in POLICIES},
        "total_units_for_LAS": acq_units + val_units_total + summary["E_LAS"]["total_units"],
        "total_units_for_CONCRETE": acq_units + summary["B_concrete"]["total_units"],
        "note": ("CONCRETE pays acquisition only; LAS additionally pays lattice generation "
                 "and source validation. Ordinary search pays neither.")},
    "ablations": ablations,
    "full_pipeline_loo": "FULL-PIPELINE LOO NOT MEASURED",
    "transfer_seconds": round(transfer_seconds, 1),
    "rows": rows,
}
text = json.dumps(report, indent=1, sort_keys=True, default=str)
(OUT / "results.json").write_text(text)
(OUT / "results_hash.txt").write_text(sha(text) + "\n")

print("\n=== LAS-v1 SUMMARY ===")
print(f"{'policy':20}{'fit':>5}{'heldout':>9}{'wrong':>7}{'undef':>7}{'prior':>7}{'units':>9}")
for policy in POLICIES:
    s = summary[policy]
    print(f"{policy:20}{s['demonstration_fits']:>5}{s['heldout_output_success']:>9}"
          f"{s['wrong_but_demo_consistent']:>7}{s['undefined_predictions']:>7}"
          f"{s['solved_in_prior']:>7}{s['total_units']:>9}")
print(f"\nacquisition {acq_units}u | validation {val_units_total}u | frozen {FROZEN_HASH[:16]}")
print("sha256:", sha(text))
print("LAS_V1_DONE")
