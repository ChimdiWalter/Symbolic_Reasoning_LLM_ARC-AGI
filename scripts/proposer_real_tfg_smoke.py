"""Real-failure smoke test for the Stage-B constructive AST proposer.

    real reasoner failure -> repaired TFG -> propose_ast -> candidate ASTs

Nothing is compiled, installed, re-run or scored. No hidden output is read.
Task set fixed by rule before any proposal was inspected: the first five, in
ascending order, of the eight tasks the repaired frontier audit classified as
carrying defined candidate-associated evidence.
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from cora_arc2026 import constructive_proposer as CP              # noqa: E402
from cora_arc2026 import engine_trace as ET                       # noqa: E402

TASKS = os.path.join(HERE, "data", "arc", "dev60_challenges.json")
OUT = os.path.join(HERE, "outputs", "proposer_smoke")

#: fixed before inspection, from records/FRONTIER_AUDIT_V2_20260923.md
INFORMATIVE = ["142ca369", "16b78196", "195c6913", "221dfab4", "247ef758",
               "271d71e2", "28a6681f", "2b83f449"]
CHOSEN = sorted(INFORMATIVE)[:5]
INTERFACE = ("Set[Region]", "Grid")
TOP_K = 5


def main():
    with open(TASKS) as handle:
        tasks = json.load(handle)
    os.makedirs(OUT, exist_ok=True)
    rows = []
    for index, task_id in enumerate(CHOSEN, 1):
        pairs = [(p["input"], p["output"]) for p in tasks[task_id]["train"]]
        got = ET.extract(task_id, pairs, budget_s=8.0)
        evidence = CP.read_evidence(got["tfg"])
        started = time.monotonic()
        cands = CP.propose_ast(got["tfg"], INTERFACE, k=TOP_K)
        elapsed = time.monotonic() - started
        row = {
            "task_token": f"dev{index:02d}",
            "solved_by_engine": got["solved"],
            "evidence": evidence.as_dict(),
            "candidates_emitted": len(cands),
            "proposal_runtime_s": round(elapsed, 4),
            "absent_from_k": sum(1 for c in cands if c.absent_from_k),
            "distinct_families": sorted({c.family_text for c in cands}),
            "candidates": [c.to_dict() for c in cands],
        }
        rows.append(row)
        print(f"[{index}/{len(CHOSEN)}] {row['task_token']} "
              f"emitted={len(cands)} absent_from_K={row['absent_from_k']} "
              f"families={','.join(row['distinct_families'])} "
              f"top_score={cands[0].score if cands else None} "
              f"{row['proposal_runtime_s']}s", flush=True)

    digests = [c["digest"] for r in rows for c in r["candidates"]]
    summary = {
        "interface": list(INTERFACE),
        "top_k": TOP_K,
        "beam": CP.BEAM,
        "tasks": len(rows),
        "total_candidates": len(digests),
        "distinct_candidates_across_tasks": len(set(digests)),
        "all_absent_from_k": all(c["absent_from_k"] for r in rows
                                 for c in r["candidates"]),
        "rows": rows,
    }
    path = os.path.join(OUT, "proposer_real_tfg_smoke.json")
    with open(path, "w") as handle:
        json.dump(summary, handle, indent=1, default=str)
    print(f"\ndistinct ASTs across the {len(rows)} tasks: "
          f"{summary['distinct_candidates_across_tasks']} of {len(digests)}")
    print("wrote", path)


if __name__ == "__main__":
    main()
