"""Phase 2: can V2.1 reproduce the already-established Level-1 result?

Only the two source tasks, and not merely "does it solve them": full V2.1
discovery, ordinary leave-one-out by complete rediscovery, and held-out test
correctness. If either fails, only implementation bugs may be fixed; the
semantic contract is frozen.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from geocat_arc.object_reasoning import meta_v21 as V  # noqa: E402
from geocat_arc.object_reasoning import meta_v21_search as S  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "cora_breakthrough"
SOURCES = ("7b6016b9", "83302e8f")


def main():
    challenges = json.loads(
        (ROOT / "data" / "arc-agi_training_challenges.json").read_text())
    solutions = json.loads(
        (ROOT / "data" / "arc-agi_training_solutions.json").read_text())
    rows = []
    for task_id in SOURCES:
        task = challenges[task_id]
        pairs = [(np.array(p["input"]), np.array(p["output"]))
                 for p in task["train"]]
        started = time.monotonic()
        results, stats = S.search(pairs)
        row = {"task": task_id, "found": len(results),
               "seconds": round(time.monotonic() - started, 2),
               "stats": stats.as_dict()}
        if results:
            ast, evidence = results[0]
            passed, folds = S.loo_by_rediscovery(pairs)
            predicted = V.evaluate(ast, np.array(task["test"][0]["input"]))
            row.update({
                "ast": V.to_json(ast),
                "ops": sorted(set(V.concepts_used(ast))),
                "slot_evidence": evidence,
                "loo_by_rediscovery": f"{passed}/{folds}",
                "loo_passed": passed == folds,
                "test_correct": bool(predicted is not None and np.array_equal(
                    predicted, np.array(solutions[task_id][0])))})
        rows.append(row)
        print(json.dumps({k: v for k, v in row.items() if k != "ast"}),
              flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "v21_phase2_sources.json").write_text(json.dumps(rows, indent=1))
    ok = [r for r in rows if r.get("loo_passed") and r.get("test_correct")]
    print(f"\nreproduced with LOO and test-correct: {len(ok)}/{len(SOURCES)}")


if __name__ == "__main__":
    main()
