"""Step A.1: read-only secondary analysis of the frozen Step-A output.

Step A is accepted and is never rerun or altered; its output hash remains the
primary frozen result. This stage answers four questions the frozen cluster
key cannot, WITHOUT changing a single primary label:

  1 unique sources.  The reported 491 source-token mass summed per-cluster
    distinct counts, so a task contributing to several clusters was counted
    several times. Deduplicate.

  2 secondary class.  ``slot_learning`` was assigned by frozen precedence, so
    a record whose diagnostics ALSO show fitted-and-executed-but-wrong
    continuations carries semantic-failure evidence the precedence ordered
    away. Classify each frozen slot_learning record as PURE_SLOT (every
    considered continuation died at slot fitting) or MIXED_SLOT_SEMANTIC
    (some continuation got past fitting and still failed). The frozen
    failure_class field is never overwritten; this is a second column.

  3 within-cluster diversity.  The frozen key includes neither the frontier
    value signature nor the frontier AST, so 60 clusters sharing
    frontier_type=Set[Region] is not yet evidence of one semantic concept.
    Count distinct value signatures and distinct AST skeletons per eligible
    cluster.

  4 predicate audit.  The runner's ``_continues`` used canonical-string
    containment as a stand-in for structural subterm. Audit that equivalence
    against a genuine recursive predicate on the actual frozen frontier
    ASTs, and record the state of the frozen runner source itself.

Reads the pinned files, verifies their hashes against the pin FIRST, writes
one artifact, and pins its hash. Nothing else is touched.
"""
from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT = ROOT / "outputs" / "cora_breakthrough"
PIN = OUT / "level4_stepA_output_hash.txt"
RECORDS = OUT / "level4_stepA_frontier_records.jsonl"
CLUSTERS = OUT / "level4_stepA_clusters.json"
FOLDS = OUT / "level4_stepA_fold_summary.json"
RUNNER = ROOT / "scripts" / "cora_level4_stepA_extract.py"

import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location("stepA_extract", RUNNER)
R = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(R)

from level4_blind_runtime import env as E  # noqa: E402
from level4_blind_runtime import runtime as V  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_pin() -> dict:
    lines = PIN.read_text().splitlines()
    pinned = {parts[0]: parts[1] for parts in
              (line.split() for line in lines[1:]) if len(parts) == 2}
    checks = {name: sha256(OUT / name) == digest
              for name, digest in pinned.items()}
    if not all(checks.values()):
        raise SystemExit(f"ABORT: pinned Step-A output has changed: {checks}")
    return {"combined": lines[0], "files": checks}


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, default=str)


SHAPE_CHANGING = {"smaller", "larger", "other"}


def shape_bucket(record) -> str:
    relation = record["goal_delta_signature"].get("shape_relation")
    if relation == "same":
        return "same"
    if relation in SHAPE_CHANGING:
        return "shape_changing"
    return "varies_or_undefined"       # VARIES across the fold's pairs


def secondary_class(diagnostics: dict) -> str:
    """PURE_SLOT vs MIXED_SLOT_SEMANTIC, from frozen diagnostics only.

    PURE_SLOT: every considered continuation died at slot fitting -- no
    continuation was ever fitted, executed, or exact.
    MIXED_SLOT_SEMANTIC: at least one continuation got PAST fitting
    (slot_fits_ok, executed_not_exact or exact > 0), so semantic-failure
    evidence coexists with the slot failures the precedence reported.
    """
    past = (diagnostics.get("slot_fits_ok", 0)
            + diagnostics.get("executed_not_exact", 0)
            + diagnostics.get("exact", 0))
    if diagnostics.get("slot_fit_failures", 0) > 0 and past == 0:
        return "PURE_SLOT"
    if diagnostics.get("slot_fit_failures", 0) > 0:
        return "MIXED_SLOT_SEMANTIC"
    return "OTHER"                      # defensive; should not occur


# -- structural subterm, the genuine recursive predicate --------------------

def is_subterm(needle, haystack, env) -> bool:
    """needle == haystack, or needle is a subterm of one of its arguments."""
    if canonical(E.to_json(needle, env)) == canonical(E.to_json(haystack, env)):
        return True
    if not env.is_ast(haystack):
        return False
    return any(is_subterm(needle, arg, env) for arg in haystack[1]
               if env.is_ast(arg))


def audit_continues(asts: list, env) -> dict:
    """String-containment vs structural subterm, on skeletonized real terms.

    The runner asked: is the frontier's skeleton a subterm of the candidate's
    skeleton? and answered by substring containment of their canonical
    serializations. Test both directions of possible error on real frozen
    terms: containment without subterm (false continuation) and subterm
    without containment (missed continuation).
    """
    skeletons = []
    seen = set()
    for ast in asts:
        skel = R.skeleton(ast, env)
        key = canonical(E.to_json(skel, env))
        if key not in seen:
            seen.add(key)
            skeletons.append((key, skel))
    skeletons.sort(key=lambda ks: ks[0])

    pairs = disagreements = containments = subterms = 0
    examples = []
    n = len(skeletons)
    # deterministic sampling: every pair for small n, strided otherwise
    stride = max(1, (n * n) // 250_000)
    index = 0
    for i in range(n):
        for j in range(n):
            index += 1
            if index % stride:
                continue
            key_a, a = skeletons[i]
            key_b, b = skeletons[j]
            pairs += 1
            contained = key_a in key_b
            structural = is_subterm(a, b, env)
            containments += contained
            subterms += structural
            if contained != structural:
                disagreements += 1
                if len(examples) < 5:
                    examples.append({"needle": key_a[:200],
                                     "haystack": key_b[:200],
                                     "containment": contained,
                                     "structural": structural})
    return {"distinct_skeletons": n, "pairs_tested": pairs,
            "containment_positive": containments,
            "structural_positive": subterms,
            "disagreements": disagreements, "examples": examples}


def main() -> int:
    pin = verify_pin()
    print(f"pin verified: {pin['combined'][:16]}...  files "
          f"{sum(pin['files'].values())}/{len(pin['files'])}")

    manifest = json.loads((OUT / "level4_mechanism_inputs" /
                           "machine_manifest.json").read_text())
    env = R.build_env(manifest)

    clusters = json.loads(CLUSTERS.read_text())["clusters"]
    eligible = [c for c in clusters if c["eligible"]]
    eligible_keys = {(c["frontier_type"], c["goal_type"],
                      canonical(c["goal_delta_signature"]),
                      c["failure_class"]) for c in eligible}

    # ---- pass over the frozen records ------------------------------------
    records = 0
    slot_records = Counter()            # secondary class, record level
    slot_records_by_shape = Counter()   # (shape bucket, secondary class)
    source_secondary = defaultdict(set)     # token -> secondary classes seen
    source_shapes = defaultdict(set)        # token -> shape buckets seen
    eligible_sources = set()
    eligible_sources_by_class = defaultdict(set)
    all_failing_sources = set()
    per_cluster_value_sigs = defaultdict(set)
    per_cluster_skeletons = defaultdict(set)
    audit_asts, audit_seen = [], set()

    with RECORDS.open() as handle:
        for line in handle:
            row = json.loads(line)
            records += 1
            token = row["source_token"]
            all_failing_sources.add(token)
            key = (row["frontier_type"], row["goal_type"],
                   canonical(row["goal_delta_signature"]),
                   row["failure_class"])
            in_eligible = key in eligible_keys
            if in_eligible:
                eligible_sources.add(token)
                eligible_sources_by_class[row["failure_class"]].add(token)
                per_cluster_value_sigs[key].add(
                    canonical(row["frontier_value_signature"]))
                ast = V.from_json(row["frontier_ast"])
                skeleton_key = canonical(
                    E.to_json(R.skeleton(ast, env), env))
                per_cluster_skeletons[key].add(skeleton_key)
                if skeleton_key not in audit_seen and len(audit_seen) < 800:
                    audit_seen.add(skeleton_key)
                    audit_asts.append(ast)
            if row["failure_class"] == "slot_learning":
                second = secondary_class(row["diagnostics"])
                bucket = shape_bucket(row)
                slot_records[second] += 1
                slot_records_by_shape[(bucket, second)] += 1
                source_secondary[token].add(second)
                source_shapes[token].add(bucket)

    # ---- unique-source dedup ---------------------------------------------
    reported_mass = sum(c["distinct_source_tokens"] for c in eligible)
    dedup = {
        "reported_source_token_mass_sum_over_eligible_clusters": reported_mass,
        "unique_sources_across_eligible_clusters": len(eligible_sources),
        "unique_sources_by_frozen_class": {
            k: len(v) for k, v in sorted(eligible_sources_by_class.items())},
        "unique_failing_sources_in_all_records": len(all_failing_sources),
        "note": ("the mass sum double-counts a task appearing in several "
                 "eligible clusters; the unique counts here are the "
                 "deduplicated task-level quantities"),
    }

    # ---- secondary classification, record and source level ---------------
    def source_level(tokens_with_classes: dict) -> dict:
        all_pure = sum(1 for classes in tokens_with_classes.values()
                       if classes == {"PURE_SLOT"})
        any_mixed = sum(1 for classes in tokens_with_classes.values()
                        if "MIXED_SLOT_SEMANTIC" in classes)
        return {"sources": len(tokens_with_classes),
                "all_records_PURE_SLOT": all_pure,
                "any_record_MIXED_SLOT_SEMANTIC": any_mixed}

    by_shape_sources = {}
    for bucket in ("same", "shape_changing", "varies_or_undefined"):
        subset = {token: source_secondary[token]
                  for token, shapes in source_shapes.items()
                  if bucket in shapes}
        by_shape_sources[bucket] = source_level(subset)

    secondary = {
        "definition": {
            "PURE_SLOT": ("slot_fit_failures > 0 and no continuation was "
                          "fitted, executed or exact"),
            "MIXED_SLOT_SEMANTIC": ("slot_fit_failures > 0 and at least one "
                                    "continuation got past fitting "
                                    "(slot_fits_ok + executed_not_exact + "
                                    "exact > 0)"),
            "never_overwrites": "the frozen failure_class field is untouched",
        },
        "record_level": dict(slot_records),
        "record_level_by_shape": {
            f"{bucket}/{cls}": count for (bucket, cls), count
            in sorted(slot_records_by_shape.items())},
        "source_level_all_slot_learning": source_level(source_secondary),
        "source_level_by_shape": by_shape_sources,
    }

    # ---- within-cluster diversity ----------------------------------------
    diversity = []
    for c in eligible:
        key = (c["frontier_type"], c["goal_type"],
               canonical(c["goal_delta_signature"]), c["failure_class"])
        diversity.append({
            "frontier_type": c["frontier_type"],
            "failure_class": c["failure_class"],
            "goal_delta_signature": c["goal_delta_signature"],
            "distinct_source_tokens": c["distinct_source_tokens"],
            "records": c["records"],
            "distinct_frontier_value_signatures":
                len(per_cluster_value_sigs[key]),
            "distinct_frontier_ast_skeletons":
                len(per_cluster_skeletons[key]),
        })
    diversity.sort(key=lambda d: (-d["distinct_source_tokens"],
                                  -d["records"]))

    # ---- predicate audit --------------------------------------------------
    audit = audit_continues(audit_asts, env)
    runner_text = RUNNER.read_text()
    audit["frozen_runner_sha256"] = sha256(RUNNER)
    audit["matched_computations_in_frozen_runner"] = runner_text.count(
        "matched = [")
    audit["dead_overwritten_matched_in_frozen_runner"] = (
        runner_text.count("matched = [") > 1)
    audit["note"] = (
        "a mid-development version of the runner briefly contained two "
        "consecutive `matched = [...]` assignments, the first dead; that was "
        "removed BEFORE the freeze (recorded in ledger entry -116), and the "
        "frozen runner hashed here contains exactly one. The containment-vs-"
        "structural comparison above is the empirical trust test for the one "
        "that ran.")

    artifact = {
        "stage": "Level 4 Step A.1: read-only secondary analysis",
        "primary_result": {
            "output_hash": pin["combined"],
            "status": ("accepted, never rerun or altered; all counts here "
                       "are derived views of the pinned files"),
        },
        "wording_correction_of_record": (
            "Step A found a strong type-level concentration: 60/62 eligible "
            "cluster keys have frontier_type=Set[Region] and are labelled "
            "slot_learning under the frozen precedence. This identifies the "
            "first observed blocker along the current derivations, not a "
            "sufficient missing capability."),
        "inputs_verified": pin["files"],
        "records_read": records,
        "source_token_dedup": dedup,
        "secondary_classification": secondary,
        "eligible_cluster_diversity": diversity,
        "continues_predicate_audit": audit,
    }

    path = OUT / "level4_stepA1_analysis.json"
    path.write_text(json.dumps(artifact, indent=1))
    digest = sha256(path)
    (OUT / "level4_stepA1_hash.txt").write_text(digest + "\n")

    print(f"records read                {records}")
    print(f"unique eligible sources     {len(eligible_sources)} "
          f"(mass sum was {reported_mass})")
    print(f"secondary (records)         {dict(slot_records)}")
    print(f"secondary (sources)         "
          f"{secondary['source_level_all_slot_learning']}")
    for bucket, stats in by_shape_sources.items():
        print(f"  {bucket:22} {stats}")
    print(f"predicate audit             pairs {audit['pairs_tested']}  "
          f"disagreements {audit['disagreements']}")
    print(f"dead matched in frozen      "
          f"{audit['dead_overwritten_matched_in_frozen_runner']}")
    print()
    print("STEP A.1 FROZEN")
    print(f"artifact sha256 = {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
