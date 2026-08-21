"""Replication: one unchanged mechanism, three families.

The search is never told which family a task belongs to.  It is given the
frozen typed grammar, the router picks sub-grammars from demonstration
evidence alone, and whatever is discovered is anti-unified by the same
generic procedure that produced concept_0001.

Experience split only.
"""
from __future__ import annotations

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

FAMILIES = {
    "computed_set": ["7b6016b9", "83302e8f"],
    "template": ["39e1d7f9", "7e0986d6", "fe45cba4"],
    "lattice": ["05269061", "8eb1be9a"],
}


def main():
    challenges = json.loads(
        (ROOT / "data" / "arc-agi_training_challenges.json").read_text())
    solutions = json.loads(
        (ROOT / "data" / "arc-agi_training_solutions.json").read_text())
    manifest = json.loads((ROOT / "outputs" / "lockbox" / "manifest.json").read_text())
    tasks = manifest["tasks"]
    split = ({t["task_id"]: t["split"] for t in tasks} if isinstance(tasks, list)
             else {k: v["split"] for k, v in tasks.items()})

    report = {}
    for family, ids in FAMILIES.items():
        rows = []
        for tid in ids:
            if split.get(tid) != "experience":
                rows.append({"task": tid, "outcome": "SKIPPED_NOT_EXPERIENCE"})
                continue
            pairs = [(np.array(p["input"]), np.array(p["output"]))
                     for p in challenges[tid]["train"]]
            started = time.monotonic()
            results, stats = S.routed_search(pairs)
            row = {"task": tid, "seconds": round(time.monotonic() - started, 2),
                   "routes": list(stats.routed_to),
                   "typed_hypotheses": stats.typed,
                   "semantic_classes": stats.semantic_classes,
                   "found": len(results)}
            if results:
                ast, evidence = results[0]
                got = V.evaluate(ast, np.array(challenges[tid]["test"][0]["input"]))
                row.update({
                    "outcome": "DISCOVERED",
                    "ast": V.to_json(ast),
                    "ops": sorted(set(V.concepts_used(ast))),
                    "slot_evidence": evidence,
                    "test_correct": bool(got is not None and np.array_equal(
                        got, np.array(solutions[tid][0]))),
                    # leave-one-out by rediscovery: the whole procedure re-run
                    "loo_by_rediscovery": _loo(pairs)})
            else:
                row["outcome"] = _diagnose(pairs, stats)
            rows.append(row)
            print(json.dumps({k: v for k, v in row.items() if k != "ast"}),
                  flush=True)
        report[family] = rows
    (OUT / "v2_replication.json").write_text(json.dumps(report, indent=1))

    discovered = {f: [r for r in rows if r.get("outcome") == "DISCOVERED"]
                  for f, rows in report.items()}
    print("\nSUMMARY")
    for family, rows in discovered.items():
        print(f"  {family}: {len(rows)}/{len(FAMILIES[family])} discovered, "
              f"{sum(1 for r in rows if r.get('test_correct'))} test-correct")


def _loo(pairs):
    """Re-run the entire discovery on N-1 pairs and predict the held-out."""
    passed = 0
    for held in range(len(pairs)):
        subset = [p for i, p in enumerate(pairs) if i != held]
        results, _ = S.routed_search(subset)
        if not results:
            continue
        grid_in, grid_out = pairs[held]
        got = V.evaluate(results[0][0], grid_in)
        if got is not None and np.array_equal(got, grid_out):
            passed += 1
    return f"{passed}/{len(pairs)}"


def _diagnose(pairs, stats):
    if not stats.routed_to:
        return "ROUTER_DECLINED"
    if stats.typed == 0:
        return "NO_TYPED_CANDIDATE"
    if stats.seconds >= S.budget_s() - 0.2:
        return "BUDGET_EXHAUSTED"
    return "NO_CANDIDATE_FIT_DEMONSTRATIONS"


if __name__ == "__main__":
    main()
