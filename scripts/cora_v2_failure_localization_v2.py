"""Failure localization, second pass: instrumentation fixed, system untouched.

Corrections over the first pass, all of them to the DIAGNOSTIC only:

* the outside-policy probe now records executed_all_inputs, so an execution
  failure is never reported as a semantic mismatch;
* exhaustion is recorded explicitly (deadline, per-type cap, frontier cap,
  depth reached), so "no program found" is never silently upgraded into
  "no program exists";
* the verdict ladder separates router, constructibility, slot learning,
  execution and semantic mismatch as distinct outcomes;
* a type-reachability analysis over the frozen production graph answers the
  structural question directly: can any well-typed derivation place several
  independently positioned copies into one output grid;
* the Level-3 concept path is checked, so a transfer experiment cannot be
  run against the wrong baseline.

Nothing here changes grammar, learners, router, depth, budgets or search.
"""
from __future__ import annotations

import hashlib
import inspect
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from geocat_arc.object_reasoning import meta_search as S  # noqa: E402
from geocat_arc.object_reasoning import meta_v2 as V  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "cora_breakthrough"

TASKS = {"39e1d7f9": "template", "7e0986d6": "template", "fe45cba4": "template",
         "05269061": "lattice", "8eb1be9a": "lattice"}
EXPECTED = {"template": "template_placement", "lattice": "orbit_sequence"}
PROBE_SECONDS = 60.0


def verify_frozen():
    stamp = json.loads((OUT / "v2_conformant_stamp.json").read_text())
    drifted = [p for p, h in stamp["sha256"].items()
               if hashlib.sha256((ROOT / p).read_bytes()).hexdigest() != h]
    return stamp, drifted


def sweep(pairs, allowed, seconds):
    """Enumerate, fit, execute and compare; report what stopped us."""
    counts = {"constructed": 0, "slots_fitted": 0, "executed_all_inputs": 0,
              "exact_on_demos": 0}
    stats = S.SearchStats()
    started = time.monotonic()
    deadline = started + seconds
    example = None
    for ast in S.enumerate_asts(V.GRID, allowed, S.MAX_DEPTH, stats, deadline):
        if time.monotonic() > deadline:
            break
        counts["constructed"] += 1
        complete, _ = S.fit_slots(ast, pairs)
        if complete is None:
            continue
        counts["slots_fitted"] += 1
        rendered = [V.evaluate(complete, gi) for gi, _ in pairs]
        if any(r is None for r in rendered):
            continue
        counts["executed_all_inputs"] += 1
        if all(np.array_equal(r, go) for r, (_, go) in zip(rendered, pairs)):
            counts["exact_on_demos"] += 1
            if example is None:
                example = V.to_json(complete)
    elapsed = time.monotonic() - started
    counts["exhaustion"] = {
        "deadline_hit": elapsed >= seconds - 0.05,
        "seconds": round(elapsed, 2),
        "syntactic_generated": stats.syntactic,
        "per_type_cap": S.PER_TYPE_CAP,
        "per_type_cap_possibly_hit": stats.syntactic >= S.PER_TYPE_CAP,
        "frontier_cap": S.FRONTIER_CAP,
        "depth_searched": S.MAX_DEPTH,
        "enumeration_exhausted": (elapsed < seconds - 0.05
                                  and stats.syntactic < S.PER_TYPE_CAP),
    }
    counts["example"] = example
    return counts


def verdict_of(router_ok, frozen, probe):
    """Distinct outcomes; each rung is only reached if the one above passed."""
    if not router_ok:
        return "ROUTER_FAILURE"
    if frozen["constructed"] == 0 and probe["constructed"] == 0:
        return "NOT_CONSTRUCTIBLE"
    if frozen["exact_on_demos"] > 0:
        return "FOUND_UNDER_FROZEN_POLICY"
    if probe["exact_on_demos"] > 0:
        return "ROUTING_OR_SEARCH_POLICY_LOSS"
    if probe["slots_fitted"] == 0:
        return "SLOT_LEARNER_FAILURE"
    if probe["executed_all_inputs"] == 0:
        return "EXECUTION_FAILURE"
    if probe["exhaustion"]["enumeration_exhausted"]:
        return "SEMANTIC_EXPRESSIVITY_FAILURE_EXHAUSTIVE"
    return "SEMANTIC_MISMATCH_NOT_EXHAUSTIVE"


# --------------------------------------------------------------------------
# type reachability over the frozen production graph
# --------------------------------------------------------------------------

def reachable_types():
    """Types derivable from the terminal and induced vocabularies."""
    have = set(V.TERMINAL_VOCAB) | set(V.INDUCED_TYPES)
    changed = True
    while changed:
        changed = False
        for production in V.PRODUCTIONS.values():
            if production.result_type in have:
                continue
            if all(a in have for a in production.arg_types):
                have.add(production.result_type)
                changed = True
    return have


def multi_placement_derivable():
    """Can any well-typed derivation place SEVERAL copies into one grid?

    A multi-instance stamp needs a production whose argument is a SET of
    placements (or a set of grids to overlay), because one placement can
    only be stamped once.  This inspects the frozen production graph rather
    than the search, so the answer is structural.
    """
    set_of_placement = [name for name, p in V.PRODUCTIONS.items()
                        if any(a.startswith("Set[") and "Placed" in a
                               or a == "Set[Placement]" for a in p.arg_types)]
    produces_set_of_placement = [name for name, p in V.PRODUCTIONS.items()
                                 if p.result_type in ("Set[Placement]",
                                                      "Set[Placed]")]
    # a MapOver whose function yields a Placement would be the generic route
    mapover = V.PRODUCTIONS.get("MapOver")
    mapover_yields = mapover.result_type if mapover else None
    function_result = None
    for name, p in V.PRODUCTIONS.items():
        if p.result_type.startswith("Function["):
            function_result = p.result_type
    grid_from_many = [name for name, p in V.PRODUCTIONS.items()
                      if p.result_type == V.GRID
                      and any(a.startswith("Set[") for a in p.arg_types)]
    return {
        "productions_consuming_a_set_of_placements": set_of_placement,
        "productions_producing_a_set_of_placements": produces_set_of_placement,
        "MapOver_result_type": mapover_yields,
        "only_Function_type_available": function_result,
        "productions_making_a_Grid_from_a_set": grid_from_many,
        "multi_placement_derivable": bool(set_of_placement
                                          and produces_set_of_placement),
    }


def level3_path_check():
    """Does the Level-3 harness exercise V2, or the earlier V1 path?"""
    source = (ROOT / "scripts" / "cora_level3_transfer.py").read_text()
    uses_v1 = "meta_induction" in source
    uses_v2 = "meta_search" in source or "meta_v2" in source
    return {"imports_v1_meta_induction": uses_v1,
            "imports_v2_meta_search": uses_v2,
            "valid_v2_comparison": (uses_v2 and not uses_v1),
            "note": ("A Level-3 result is only causal if the concept condition "
                     "differs from the baseline ONLY by making concept_0001 "
                     "available; if this harness runs the V1 search it compares "
                     "V2 against V1 plus a concept, which is not the experiment.")}


def main():
    stamp, drifted = verify_frozen()
    if drifted:
        print("REFUSING TO RUN: build drifted from V2.0-CONFORMANT")
        for path in drifted:
            print("  drifted:", path)
        return
    print(f"build verified against {stamp['label']}\n")
    challenges = json.loads(
        (ROOT / "data" / "arc-agi_training_challenges.json").read_text())

    rows = []
    for task_id, family in TASKS.items():
        pairs = [(np.array(p["input"]), np.array(p["output"]))
                 for p in challenges[task_id]["train"]]
        routes = S.route(pairs)
        router_ok = EXPECTED[family] in routes
        frozen_allowed = set()
        for name in routes:
            frozen_allowed.update(S.SUBGRAMMARS.get(name, ()))
        frozen = sweep(pairs, frozen_allowed,
                       S.budget_s()) if frozen_allowed else {
            "constructed": 0, "slots_fitted": 0, "executed_all_inputs": 0,
            "exact_on_demos": 0, "exhaustion": {}, "example": None}
        probe = sweep(pairs, set(V.PRODUCTIONS), PROBE_SECONDS)
        row = {"task": task_id, "family": family, "routes": list(routes),
               "expected_subgrammar": EXPECTED[family],
               "router_offered_expected": router_ok,
               "frozen_policy": frozen, "diagnostic_probe": probe,
               "verdict": verdict_of(router_ok, frozen, probe)}
        rows.append(row)
        print(f"{task_id} [{family}] router_ok={router_ok}")
        for label, block in (("frozen", frozen), ("probe", probe)):
            print(f"    {label}: constructed {block['constructed']}, "
                  f"slots {block['slots_fitted']}, "
                  f"executed {block['executed_all_inputs']}, "
                  f"exact {block['exact_on_demos']}, "
                  f"exhausted={block['exhaustion'].get('enumeration_exhausted')}")
        print(f"    VERDICT: {row['verdict']}\n", flush=True)

    structural = multi_placement_derivable()
    level3 = level3_path_check()
    report = {"stamp": stamp["label"], "rows": rows,
              "type_reachability": {"reachable_types": sorted(reachable_types()),
                                    "multi_placement": structural},
              "level3_path": level3}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "v2_failure_localization_v2.json").write_text(
        json.dumps(report, indent=1, default=str))

    print("TYPE REACHABILITY: multi-instance placement derivable =",
          structural["multi_placement_derivable"])
    print("  productions producing a set of placements:",
          structural["productions_producing_a_set_of_placements"] or "NONE")
    print("  productions consuming a set of placements:",
          structural["productions_consuming_a_set_of_placements"] or "NONE")
    print("  MapOver result type:", structural["MapOver_result_type"])
    print("\nLEVEL 3 PATH:", json.dumps(
        {k: v for k, v in level3.items() if k != "note"}))

    print("\n| Task | Family | Router | Constructed | Slots fit | Executes | "
          "Exact | Exhaustive | Verdict |")
    print("|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        p = r["diagnostic_probe"]
        print(f"| {r['task']} | {r['family']} | "
              f"{'yes' if r['router_offered_expected'] else 'NO'} | "
              f"{p['constructed']} | {p['slots_fitted']} | "
              f"{p['executed_all_inputs']} | {p['exact_on_demos']} | "
              f"{p['exhaustion'].get('enumeration_exhausted')} | "
              f"{r['verdict']} |")


if __name__ == "__main__":
    main()
