"""Positive-coverage parity between the v1.1 learner and the scoped fitter
on the complete single-block family (directive section 7).

The existing parity suite (tests/test_scoped_slot_parity.py) uses one
transformation family and is dominated by negative verdicts. This script adds
the missing POSITIVE coverage: for every one of the 200 (1,) schemas, a
concrete program is instantiated deterministically from that very schema,
demonstrations are rendered, and both fitters are asked to recover it.

Reported, never inferred from one another:
    old successes, new successes, mutual failures,
    old-success/new-failure, old-failure/new-success, behaviour disagreements
plus per-terminal coverage: a partition, predicate or key feature that never
appears in a positive case is UNKNOWN, not a parity pass.

Old  = meta_induction.fit_induced_slots + observational_signature (v1.1)
New  = scoped_slot_fitting.fit_outcome, strict (exact replay required)
Also = whether meta_induction.search (the actual fixed search) returns an
       exact program for the same demonstrations.
"""
from __future__ import annotations

import hashlib
import json
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
from cora_tti import constructive_dataset as CD                  # noqa: E402
from cora_tti import constructive_v2c as V2C                     # noqa: E402
from cora_tti import scoped_slot_fitting as SF                   # noqa: E402

DEMO_SEED_SETS = (8_100_000, 8_200_000, 8_300_000)


def triple_of(schema):
    return (schema[1][0][1][0], schema[1][1][1][0], schema[1][2][1][0][1][0])


def old_verdict(schema, pairs):
    fitted = MI.fit_induced_slots(schema, pairs)
    if fitted is None:
        return "FIT_FAILURE", None
    if MI.observational_signature(fitted, pairs) is None:
        return "CONSTRAINT_CONSISTENT_BINDING", fitted
    return "EXACT_DEMONSTRATION_FIT", fitted


def main(out_path: Path) -> dict:
    schemas = SF.baseline_single_block_schemas()
    cases, unexercised = [], Counter()
    per_terminal_positive = {"partition": Counter(), "predicate": Counter(), "feature": Counter()}
    per_terminal_seen = {"partition": Counter(), "predicate": Counter(), "feature": Counter()}
    started = time.monotonic()
    for schema in schemas:
        partition, predicate, feature = triple_of(schema)
        for base in DEMO_SEED_SETS:
            seed = base + hash_free_index(partition, predicate, feature)
            grid_seeds = [seed * 97 + i for i in range(14)]
            concrete = V2C.instantiate_tables(schema, [CD.generate_grid(s) for s in grid_seeds[:6]])
            if concrete is None:
                unexercised["instantiation_undefined"] += 1
                continue
            pairs, _ = CD.render_demonstrations(concrete, grid_seeds, min_demos=3)
            if len(pairs) < 3:
                unexercised["fewer_than_3_demonstrations"] += 1
                continue
            for kind, name in (("partition", partition), ("predicate", predicate),
                               ("feature", feature)):
                per_terminal_seen[kind][name] += 1
            old_status, old_program = old_verdict(schema, pairs)
            new = SF.fit_outcome(schema, pairs)
            found, _stats = MI.search(pairs, deadline=time.monotonic() + 60.0)
            actual_exact = bool(found)
            disagreement = None
            if old_status == "EXACT_DEMONSTRATION_FIT" and new["status"] == "EXACT_DEMONSTRATION_FIT":
                for grid_in, _ in pairs:
                    a = M.evaluate(old_program, grid_in, MI.descriptors)
                    b = M.evaluate(new["program"], grid_in, MI.descriptors)
                    if (a is None) != (b is None) or (a is not None and not np.array_equal(a, b)):
                        disagreement = "rendering"
                        break
                for kind, name in (("partition", partition), ("predicate", predicate),
                                   ("feature", feature)):
                    per_terminal_positive[kind][name] += 1
            cases.append({"triple": [partition, predicate, feature], "seed": seed,
                          "demos": len(pairs), "old": old_status, "new": new["status"],
                          "new_code": new["code"], "actual_search_exact": actual_exact,
                          "behaviour_disagreement": disagreement})
    old_ok = sum(c["old"] == "EXACT_DEMONSTRATION_FIT" for c in cases)
    new_ok = sum(c["new"] == "EXACT_DEMONSTRATION_FIT" for c in cases)
    both = sum(c["old"] == "EXACT_DEMONSTRATION_FIT" == c["new"] for c in cases)
    old_only = [c for c in cases if c["old"] == "EXACT_DEMONSTRATION_FIT" != c["new"]]
    new_only = [c for c in cases if c["new"] == "EXACT_DEMONSTRATION_FIT" != c["old"]]
    mutual_fail = sum(c["old"] != "EXACT_DEMONSTRATION_FIT" and c["new"] != "EXACT_DEMONSTRATION_FIT"
                      for c in cases)
    actual_vs_new = Counter((c["actual_search_exact"], c["new"] == "EXACT_DEMONSTRATION_FIT")
                            for c in cases)
    coverage = {}
    for kind in per_terminal_seen:
        names = {"partition": sorted(M.PARTITIONS), "predicate": sorted(M.PREDICATES),
                 "feature": list(M.KEY_FEATURES)}[kind]
        coverage[kind] = {name: ("POSITIVE_COVERED" if per_terminal_positive[kind][name] > 0
                                 else "UNKNOWN")
                          for name in names}
        coverage[kind + "_positive_counts"] = dict(per_terminal_positive[kind])
        coverage[kind + "_exercised_counts"] = dict(per_terminal_seen[kind])
    report = {
        "schemas": len(schemas), "demo_seed_sets": list(DEMO_SEED_SETS),
        "cases_exercised": len(cases), "unexercised": dict(unexercised),
        "old_successes": old_ok, "new_successes": new_ok, "both_success": both,
        "mutual_failures": mutual_fail,
        "old_success_new_failure": len(old_only), "old_success_new_failure_cases": old_only[:20],
        "old_failure_new_success": len(new_only), "old_failure_new_success_cases": new_only[:20],
        "behaviour_disagreements": sum(1 for c in cases if c["behaviour_disagreement"]),
        "status_pairs": dict(Counter(f"old={c['old']}|new={c['new']}" for c in cases)),
        "actual_search_exact_vs_new_exact": {f"actual={a}|new={b}": n
                                             for (a, b), n in sorted(actual_vs_new.items())},
        "per_terminal_coverage": coverage,
        "fitter_identity": SF.fitter_identity(),
        "seconds": round(time.monotonic() - started, 1),
        "cases": cases,
    }
    text = json.dumps(report, indent=1, sort_keys=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text)
    report["sha256"] = hashlib.sha256(text.encode()).hexdigest()
    return report


def hash_free_index(partition: str, predicate: str, feature: str) -> int:
    """Deterministic small integer per triple without the salted hash."""
    digest = hashlib.sha256(f"{partition}|{predicate}|{feature}".encode()).hexdigest()
    return int(digest[:6], 16) % 50_000


if __name__ == "__main__":
    target = ROOT / "outputs" / "tti" / "constructive_v2_corrected" / "parity_positive_coverage.json"
    result = main(target)
    print(json.dumps({k: v for k, v in result.items()
                      if k not in ("cases", "old_success_new_failure_cases",
                                   "old_failure_new_success_cases", "per_terminal_coverage")},
                     indent=1))
    print(json.dumps(result["per_terminal_coverage"], indent=1))
