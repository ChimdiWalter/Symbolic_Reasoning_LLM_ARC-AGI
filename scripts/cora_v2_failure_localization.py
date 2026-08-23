"""Read-only failure localization for the template and lattice negatives.

Runs against the exact V2.0-CONFORMANT hashes and refuses to run if any of
them has moved.  Nothing here changes grammar, learners, router, search
parameters, depth or budgets: every probe reads the frozen system and
reports which layer the failure belongs to.

For each task it separates five layers:

    router            did the right subgrammar get offered at all
    constructible     does the frozen grammar contain any AST, within the
                      frozen depth, that even executes on these inputs
    slots_fit         does a learner accept the induced slots of any of them
    executes          does a fully instantiated candidate run on every input
    exact_demos       does any candidate reproduce every demonstration

A "diagnostic probe" section additionally searches the union of all
subgrammars with a longer deadline.  That is deliberately OUTSIDE the frozen
policy and its results are never used as a solve: it exists only to tell a
routing or ranking loss apart from a genuine expressive boundary.
"""
from __future__ import annotations

import hashlib
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


def verify_frozen():
    """Refuse to run unless the build matches the V2.0-CONFORMANT stamp."""
    stamp = json.loads((OUT / "v2_conformant_stamp.json").read_text())
    drifted = []
    for path, expected in stamp["sha256"].items():
        actual = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
        if actual != expected:
            drifted.append(path)
    return stamp, drifted


def pairs_of(task):
    return [(np.array(p["input"]), np.array(p["output"]))
            for p in task["train"]]


def localize(task_id, task):
    pairs = pairs_of(task)
    report = {"task": task_id, "family": TASKS[task_id],
              "n_pairs": len(pairs)}

    # -- layer 1: routing -------------------------------------------------
    signature = S.failure_signature(pairs)
    routes = S.route(pairs)
    report["signature"] = {k: v for k, v in signature.items()
                           if k != "changed_cell_count"}
    report["routes"] = list(routes)
    wanted = {"template": "template_placement", "lattice": "orbit_sequence"}
    report["expected_subgrammar"] = wanted[TASKS[task_id]]
    report["router_offered_expected"] = wanted[TASKS[task_id]] in routes

    # -- layers 2 to 5, under the FROZEN policy ---------------------------
    counts = {"constructed": 0, "slots_fitted": 0, "executed_all_inputs": 0,
              "exact_on_demos": 0}
    stats_total = S.SearchStats()
    for name in routes:
        allowed = set(S.SUBGRAMMARS.get(name, ()))
        stats = S.SearchStats()
        deadline = time.monotonic() + S.budget_s() / max(len(routes), 1)
        for ast in S.enumerate_asts(V.GRID, allowed, S.MAX_DEPTH, stats,
                                    deadline):
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
            if all(np.array_equal(r, go)
                   for r, (_, go) in zip(rendered, pairs)):
                counts["exact_on_demos"] += 1
        stats_total.syntactic += stats.syntactic
    report["frozen_policy"] = counts

    # -- diagnostic probe, OUTSIDE the frozen policy ----------------------
    # Union of every subgrammar, longer deadline.  Never counts as a solve;
    # it only separates a routing or ranking loss from an expressive limit.
    probe = {"constructed": 0, "slots_fitted": 0, "exact_on_demos": 0,
             "example": None}
    stats = S.SearchStats()
    deadline = time.monotonic() + 60.0
    for ast in S.enumerate_asts(V.GRID, set(V.PRODUCTIONS), S.MAX_DEPTH,
                                stats, deadline):
        if time.monotonic() > deadline:
            break
        probe["constructed"] += 1
        complete, _ = S.fit_slots(ast, pairs)
        if complete is None:
            continue
        probe["slots_fitted"] += 1
        rendered = [V.evaluate(complete, gi) for gi, _ in pairs]
        if any(r is None for r in rendered):
            continue
        if all(np.array_equal(r, go) for r, (_, go) in zip(rendered, pairs)):
            probe["exact_on_demos"] += 1
            if probe["example"] is None:
                probe["example"] = V.to_json(complete)
    report["diagnostic_probe"] = probe

    # -- verdict ----------------------------------------------------------
    if not report["router_offered_expected"]:
        verdict = "ROUTER_DID_NOT_OFFER_EXPECTED_SUBGRAMMAR"
    elif probe["exact_on_demos"] > 0 and counts["exact_on_demos"] == 0:
        verdict = "RANKING_OR_ROUTING_LOSS"
    elif counts["exact_on_demos"] > 0:
        verdict = "FOUND_UNDER_FROZEN_POLICY"
    elif probe["slots_fitted"] == 0 and counts["slots_fitted"] == 0:
        verdict = "INDUCED_SLOT_FAILURE"
    elif probe["constructed"] > 0:
        verdict = "EXECUTES_BUT_NEVER_MATCHES_DEMONSTRATIONS"
    else:
        verdict = "NOT_CONSTRUCTIBLE_WITHIN_FROZEN_DEPTH"
    report["verdict"] = verdict
    return report


def main():
    stamp, drifted = verify_frozen()
    if drifted:
        print("REFUSING TO RUN: build has drifted from V2.0-CONFORMANT")
        for path in drifted:
            print("  drifted:", path)
        return
    print(f"build verified against {stamp['label']} "
          f"({stamp['conformance']})\n")
    challenges = json.loads(
        (ROOT / "data" / "arc-agi_training_challenges.json").read_text())
    rows = []
    for task_id in TASKS:
        report = localize(task_id, challenges[task_id])
        rows.append(report)
        frozen = report["frozen_policy"]
        probe = report["diagnostic_probe"]
        print(f"{task_id} [{report['family']}] routes={report['routes']} "
              f"expected_offered={report['router_offered_expected']}")
        print(f"    frozen: constructed {frozen['constructed']}, "
              f"slots_fitted {frozen['slots_fitted']}, "
              f"executed {frozen['executed_all_inputs']}, "
              f"exact {frozen['exact_on_demos']}")
        print(f"    probe:  constructed {probe['constructed']}, "
              f"slots_fitted {probe['slots_fitted']}, "
              f"exact {probe['exact_on_demos']}")
        print(f"    VERDICT: {report['verdict']}\n", flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "v2_failure_localization.json").write_text(
        json.dumps({"stamp": stamp["label"], "rows": rows}, indent=1))

    print("| Task | Family | Router | Constructible | Slots fit | Executes | "
          "Exact demos | Failure |")
    print("|---|---|---|---|---|---|---|---|")
    for r in rows:
        f = r["frozen_policy"]
        print(f"| {r['task']} | {r['family']} | "
              f"{'yes' if r['router_offered_expected'] else 'NO'} | "
              f"{'yes' if f['constructed'] else 'no'} | "
              f"{'yes' if f['slots_fitted'] else 'no'} | "
              f"{'yes' if f['executed_all_inputs'] else 'no'} | "
              f"{'yes' if f['exact_on_demos'] else 'no'} | "
              f"{r['verdict']} |")


if __name__ == "__main__":
    main()
