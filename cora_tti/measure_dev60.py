"""S_base measurement: the real engine on frozen DEV-60, restart-tolerant.

Runs in 6 chunks of 10 tasks; each chunk writes its own report to
outputs/tti/dev60_base_chunks/, so a crash or session restart loses at most
one chunk and a relaunch skips finished chunks. The final merge writes
outputs/tti/dev60_base_v1.json with aggregate scores and engine statistics.
Launch detached:  nohup python3 cora_tti/measure_dev60.py > logs file 2>&1 &
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cora_tti import kaggle_emulator as KE                 # noqa: E402
from cora_tti.full_engine_solver import FullEngineSolver   # noqa: E402

CHUNKS_DIR = ROOT / "outputs" / "tti" / "dev60_base_chunks"
FINAL = ROOT / "outputs" / "tti" / "dev60_base_v1.json"
CHUNK = 10
BUDGET_PER_TASK_S = 480.0          # covers the 616 s outlier class via pooling


def main() -> int:
    CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
    dev = KE.load_split("dev")
    chunks = [dev[i:i + CHUNK] for i in range(0, len(dev), CHUNK)]
    for index, ids in enumerate(chunks):
        out = CHUNKS_DIR / f"chunk{index:02d}.json"
        if out.exists():
            print(f"chunk {index}: already done, skipping", flush=True)
            continue
        solver = FullEngineSolver()
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
             "predictions_sha256": report["predictions_sha256"]},
            indent=1, sort_keys=True))
        print(f"chunk {index}: pass@2 {report['score']['pass_at_2']} "
              f"wall {report['resources']['wall_s']}s", flush=True)

    #  merge
    rows = [json.loads(p.read_text()) for p in sorted(CHUNKS_DIR.glob("chunk*.json"))]
    per_task_scores: dict = {}
    walls, engine_totals = [], {"gate_accepted": 0, "hard_timeouts": 0,
                                "attempt1_present": 0, "attempt2_present": 0}
    for row in rows:
        per_task_scores.update(row["score"]["per_task"])
        walls.extend(t.get("wall_s", 0) for t in row["per_task"] if "wall_s" in t)
        for key in engine_totals:
            engine_totals[key] += row["engine"].get(key, 0)
    n = len(per_task_scores)
    summary = {
        "measurement": "S_base: real engine (v23 flags) on frozen DEV-60, chunked",
        "tasks": n,
        "pass_at_2": round(sum(per_task_scores.values()) / max(1, n), 6),
        "tasks_fully_correct": sum(1 for v in per_task_scores.values() if v == 1.0),
        "engine": engine_totals,
        "mean_task_wall_s": round(sum(walls) / max(1, len(walls)), 2),
        "median_task_wall_s": sorted(walls)[len(walls) // 2] if walls else 0,
        "max_task_wall_s": max(walls) if walls else 0,
        "total_wall_s": round(sum(r["resources"]["wall_s"] for r in rows), 1),
    }
    FINAL.write_text(json.dumps({"summary": summary,
                                 "per_task_scores": per_task_scores},
                                indent=1, sort_keys=True))
    print("S_BASE COMPLETE:", json.dumps(summary), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
