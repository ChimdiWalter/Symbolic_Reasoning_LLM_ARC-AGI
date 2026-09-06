"""Actual fixed meta-search versus the 200-schema adapter (directive section 6).

The protocol-v2 admission law evaluates requirement 4 (fixed base failure)
with an ADAPTER, scoped_slot_fitting.base_search_with_scoped_fitter, rather
than with meta_induction.search itself. This script establishes, from the
executable, what the actual search enumerates and how the adapter relates to
it, reporting SET equality and ORDERING separately and never forcing the
count to 200.

What is compared
    actual   the hypothesis space meta_induction.search iterates: the product
             of its own PARTITIONS, PREDICATES and KEY_FEATURES containers in
             container order (the loop at meta_induction.search reads those
             three names directly; the module exposes no per-schema event, so
             the enumeration is derived from the identical containers and then
             cross-checked against SearchStats.hypotheses on a live call).
    adapter  scoped_slot_fitting.baseline_single_block_schemas(), which reads
             meta_ast.PARTITIONS / PREDICATES (sorted) and meta_ast.KEY_FEATURES.
    vocab    the frozen v1.1 manifest terminals through constructive_vocabulary.

Also recorded: the two procedures' post-enumeration differences (fitter,
success predicate, deduplication, deadline), because set equality of the
hypothesis space does not make the procedures identical.
"""
from __future__ import annotations

import hashlib
import inspect
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "src")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from geocat_arc.object_reasoning import meta_ast as M            # noqa: E402
from geocat_arc.object_reasoning import meta_induction as MI     # noqa: E402
from cora_tti import constructive_dataset as CD                  # noqa: E402
from cora_tti import constructive_vocabulary as CV               # noqa: E402
from cora_tti import scoped_slot_fitting as SF                   # noqa: E402


def triple_of(schema) -> tuple:
    partition = schema[1][0][1][0]
    predicate = schema[1][1][1][0]
    feature = schema[1][2][1][0][1][0]
    return (partition, predicate, feature)


def main(out_path: Path) -> dict:
    #  1. the actual search's iteration domains, read from the same module objects
    source = inspect.getsource(MI.search)
    assert "for partition in PARTITIONS" in source
    assert "for predicate in PREDICATES" in source
    assert "for feature in KEY_FEATURES" in source
    actual = [(p, q, f) for p in MI.PARTITIONS for q in MI.PREDICATES
              for f in MI.KEY_FEATURES]

    #  2. cross-check the count against a live call with a generous deadline
    pairs = []
    for d in range(4):
        grid = CD.generate_grid(70_000 + d)
        out = grid.copy()
        out[grid > 1] = 3
        if not np.array_equal(out, grid):
            pairs.append((grid, out))
    _, stats = MI.search(pairs, deadline=time.monotonic() + 600.0)
    live_hypotheses = int(stats.hypotheses)

    #  3. the adapter
    adapter = [triple_of(s) for s in SF.baseline_single_block_schemas()]

    #  4. the frozen vocabulary terminals
    v = CV.vocab()
    vocab_set = {(p, q, f) for p in v["partitions"] for q in v["predicates"]
                 for f in v["key_features"]}

    first_divergence = next((i for i, (a, b) in enumerate(zip(actual, adapter))
                             if a != b), None)
    report = {
        "actual_search": {
            "count": len(actual),
            "live_call_hypotheses": live_hypotheses,
            "count_confirmed_by_live_call": live_hypotheses == len(actual),
            "order_source": "container insertion order of meta_induction.PARTITIONS, "
                            "PREDICATES, KEY_FEATURES",
            "partitions_order": list(MI.PARTITIONS),
            "predicates_order": list(MI.PREDICATES),
            "key_features_order": list(MI.KEY_FEATURES),
        },
        "adapter": {
            "count": len(adapter),
            "order_source": "sorted(meta_ast.PARTITIONS), sorted(meta_ast.PREDICATES), "
                            "meta_ast.KEY_FEATURES",
            "partitions_order": sorted(M.PARTITIONS),
            "predicates_order": sorted(M.PREDICATES),
            "key_features_order": list(M.KEY_FEATURES),
        },
        "set_equality": {
            "actual_equals_adapter": set(actual) == set(adapter),
            "actual_equals_vocab": set(actual) == vocab_set,
            "adapter_equals_vocab": set(adapter) == vocab_set,
            "actual_minus_adapter": sorted(set(actual) - set(adapter)),
            "adapter_minus_actual": sorted(set(adapter) - set(actual)),
        },
        "ordering": {
            "identical_sequence": actual == adapter,
            "first_divergence_index": first_divergence,
            "note": "the actual search has no ranking among enumerated schemas beyond "
                    "deduplication by observational signature (fewest nodes kept) and "
                    "the final sort by (node count, repr); ordering matters only when a "
                    "deadline truncates enumeration",
        },
        "procedural_differences_beyond_the_hypothesis_set": {
            "fitter": {
                "actual": "meta_induction._induce_table with the two-witness rule "
                          "(require_fold_coverable=True)",
                "adapter": "scoped_slot_fitting.fit_induced_occurrences (strict, exact "
                           "replay required) then constraint-only for the R7 set",
                "parity_evidence": "tests/test_scoped_slot_parity.py (family (1,), "
                                   "verdict and rendering parity) plus the positive-coverage "
                                   "suite added in this block",
            },
            "success_predicate": {
                "actual": "observational_signature is not None (exact replay of every demo)",
                "adapter": "exact replay of every demo inside the strict fitter",
            },
            "deduplication": {
                "actual": "by rendered signature, cheapest kept",
                "adapter": "none (every exact schema is reported)",
            },
            "budget": {
                "actual": "wall-clock deadline (ARC_META_BUDGET_S, default 8 s) can truncate",
                "adapter": "fixed work limit: all enumerated schemas, no deadline",
            },
        },
        "verdict": None,
    }
    if report["set_equality"]["actual_equals_adapter"]:
        report["verdict"] = ("HYPOTHESIS_SET_EQUIVALENT; ordering "
                             + ("identical" if actual == adapter else "differs")
                             + "; procedures differ in fitter, deduplication and budget "
                             "(recorded above); the adapter is retained as the baseline "
                             "hypothesis generator with these differences declared")
    else:
        report["verdict"] = "RESTRICTED_BASELINE_ADAPTER (hypothesis sets differ)"
    text = json.dumps(report, indent=1, sort_keys=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text)
    report["sha256"] = hashlib.sha256(text.encode()).hexdigest()
    return report


if __name__ == "__main__":
    target = ROOT / "outputs" / "tti" / "constructive_v2_corrected" / "baseline_enumeration_identity.json"
    result = main(target)
    print(json.dumps({"set_equality": result["set_equality"],
                      "ordering": result["ordering"]["identical_sequence"],
                      "first_divergence_index": result["ordering"]["first_divergence_index"],
                      "actual_count": result["actual_search"]["count"],
                      "live_hypotheses": result["actual_search"]["live_call_hypotheses"],
                      "verdict": result["verdict"], "sha256": result["sha256"]}, indent=1))
