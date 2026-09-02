"""S_base+TTI measurement: real engine + ephemeral-concept fallback on DEV-60.

Chunked and restart-tolerant exactly like the S_base runner; per-chunk reports
in outputs/tti/dev60_tti_chunks/, final merge in outputs/tti/dev60_tti_v1.json
including the directive's required metrics (invention activations, gate
accepts, timing). Launch detached:
    nohup python3 cora_tti/measure_dev60_tti.py > logs/dev60_tti.log 2>&1 &
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cora_tti import kaggle_emulator as KE                 # noqa: E402
from cora_tti.tti_fallback import TTIEngineSolver          # noqa: E402

CHUNKS_DIR = ROOT / "outputs" / "tti" / "dev60_tti_chunks"
FINAL = ROOT / "outputs" / "tti" / "dev60_tti_v1.json"
CHUNK = 10
BUDGET_PER_TASK_S = 700.0


def main() -> int:
    CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
    dev = KE.load_split("dev")
    chunks = [dev[i:i + CHUNK] for i in range(0, len(dev), CHUNK)]
    for index, ids in enumerate(chunks):
        out = CHUNKS_DIR / f"chunk{index:02d}.json"
        if out.exists():
            print(f"chunk {index}: already done, skipping", flush=True)
            continue
        solver = TTIEngineSolver()
        cfg = KE.EmulatorConfig(budget_s=BUDGET_PER_TASK_S * len(ids),
                                role="dev")
        report = KE.run_files(
            ROOT / "data/arc/arc-agi_evaluation_challenges.json", solver, cfg,
            ROOT / "data/arc/arc-agi_evaluation_solutions.json",
            restrict_to=ids)
        out.write_text(json.dumps(
            {"ids": ids, "score": report["score"],
             "per_task": report["per_task"],
             "resources": report["resources"],
             "engine": solver.summary(),
             "tti": solver.tti_summary(),
             "tti_rows": solver.tti_records,
             "predictions_sha256": report["predictions_sha256"]},
            indent=1, sort_keys=True))
        print(f"chunk {index}: pass@2 {report['score']['pass_at_2']} "
              f"tti {json.dumps(solver.tti_summary())} "
              f"wall {report['resources']['wall_s']}s", flush=True)

    rows = [json.loads(p.read_text())
            for p in sorted(CHUNKS_DIR.glob("chunk*.json"))]
    per_task_scores: dict = {}
    activations = accepted = 0
    walls = []
    for row in rows:
        per_task_scores.update(row["score"]["per_task"])
        activations += row["tti"]["invention_activations"]
        accepted += row["tti"]["tti_gate_accepted"]
        walls.extend(r.get("wall_s", 0) for r in row["tti_rows"]
                     if "wall_s" in r)
    n = len(per_task_scores)
    summary = {
        "measurement": "S_base+TTI (v1 generic ephemeral schemas) on frozen DEV-60",
        "tasks": n,
        "pass_at_2": round(sum(per_task_scores.values()) / max(1, n), 6),
        "tasks_fully_correct": sum(1 for v in per_task_scores.values()
                                   if v == 1.0),
        "invention_activations": activations,
        "tti_gate_accepted": accepted,
        "mean_invention_wall_s": round(sum(walls) / max(1, len(walls)), 2)
        if walls else 0,
        "max_invention_wall_s": max(walls) if walls else 0,
        "total_wall_s": round(sum(r["resources"]["wall_s"] for r in rows), 1),
    }
    FINAL.write_text(json.dumps({"summary": summary,
                                 "per_task_scores": per_task_scores},
                                indent=1, sort_keys=True))
    print("S_TTI COMPLETE:", json.dumps(summary), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
